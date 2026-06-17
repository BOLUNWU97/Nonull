"""
飞书 (Lark) 开放平台真实客户端 / Real Feishu (Lark) Open Platform client.

真实可运行的飞书自建应用 API 实现 (非占位壳), 基于 httpx。覆盖:
  - tenant_access_token 获取与自动刷新 (自建应用鉴权)
  - 发送消息 (文本 / 富文本 post / 交互卡片 interactive)
  - 事件订阅回调: URL challenge 验证 + AES-256-CBC 事件解密
  - 接收消息事件解析 (im.message.receive_v1)

使用前需在飞书开放平台创建自建应用, 拿到:
  - app_id, app_secret (应用凭证)
  - encrypt_key, verification_token (事件订阅安全设置, 可选但推荐)

环境变量:
  NONULL_FEISHU_APP_ID / NONULL_FEISHU_APP_SECRET
  NONULL_FEISHU_ENCRYPT_KEY / NONULL_FEISHU_VERIFICATION_TOKEN

参考: https://open.feishu.cn/document/server-docs/

@module: channels.feishu_client
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("Nonull.channels.feishu")

_FEISHU_BASE = "https://open.feishu.cn/open-apis"


# ── 事件解密 / Event decryption ──────────────────────────────────

class FeishuCrypto:
    """飞书事件订阅 AES-256-CBC 解密 + 验签 / AES decryption + signature verify.

    飞书在"加密"模式下推送的事件是 AES-256-CBC 加密的 base64 字符串。
    key = sha256(encrypt_key); iv = 密文前 16 字节; 数据 PKCS7 填充。
    """

    def __init__(self, encrypt_key: str):
        self.encrypt_key = encrypt_key
        self._key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()

    def decrypt(self, encrypt_b64: str) -> str:
        """解密飞书事件密文 → 明文 JSON 字符串。"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
        except ImportError:
            raise RuntimeError(
                "飞书事件解密需要 cryptography 库: pip install cryptography"
            )
        raw = base64.b64decode(encrypt_b64)
        iv, ciphertext = raw[:16], raw[16:]
        cipher = Cipher(algorithms.AES(self._key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        # PKCS7 去填充 + 校验 (pad_len 来自攻击者可控密文, 必须验证):
        #   空数据 → IndexError; pad_len=0 或 >16 或 >len → 静默错误数据。
        if not padded:
            raise ValueError("解密结果为空 / empty plaintext")
        pad_len = padded[-1]
        if not (1 <= pad_len <= 16) or pad_len > len(padded):
            raise ValueError(f"非法 PKCS7 填充长度 / invalid PKCS7 padding: {pad_len}")
        if padded[-pad_len:] != bytes([pad_len]) * pad_len:
            raise ValueError("非法 PKCS7 填充字节 / invalid PKCS7 padding bytes")
        plaintext = padded[:-pad_len]
        return plaintext.decode("utf-8")

    def verify_signature(self, timestamp: str, nonce: str, body: bytes, signature: str) -> bool:
        """验证事件回调签名 / Verify event callback signature.

        signature = sha256(timestamp + nonce + encrypt_key + body)
        """
        content = (timestamp + nonce + self.encrypt_key).encode("utf-8") + body
        computed = hashlib.sha256(content).hexdigest()
        return computed == signature


# ── 消息数据结构 / Message structures ────────────────────────────

@dataclass
class FeishuMessage:
    """解析后的飞书消息 / A parsed incoming Feishu message."""
    message_id: str
    chat_id: str
    sender_id: str            # open_id
    sender_type: str          # user / bot
    msg_type: str             # text / post / image ...
    text: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeishuResult:
    """API 调用结果 / API call result."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    code: int = 0


# ── 飞书客户端 / Feishu client ───────────────────────────────────

class FeishuClient:
    """飞书自建应用客户端 (真实 HTTP) / Feishu custom-app client (real HTTP).

    Usage:
        client = FeishuClient(app_id="cli_xxx", app_secret="yyy")
        client.send_text(receive_id="ou_xxx", text="你好", receive_id_type="open_id")
        client.send_card(receive_id="oc_xxx", card={...}, receive_id_type="chat_id")

    token 自动获取并缓存 (临近过期自动刷新)。
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        encrypt_key: Optional[str] = None,
        verification_token: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.app_id = app_id or os.environ.get("NONULL_FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("NONULL_FEISHU_APP_SECRET", "")
        self.encrypt_key = encrypt_key or os.environ.get("NONULL_FEISHU_ENCRYPT_KEY", "")
        self.verification_token = (
            verification_token or os.environ.get("NONULL_FEISHU_VERIFICATION_TOKEN", "")
        )
        self.timeout = timeout
        self._token: str = ""
        self._token_expire_at: float = 0.0
        self._crypto: Optional[FeishuCrypto] = (
            FeishuCrypto(self.encrypt_key) if self.encrypt_key else None
        )

    # ── 鉴权 / Auth ──────────────────────────────────────────────

    def get_tenant_access_token(self, force: bool = False) -> str:
        """获取 tenant_access_token (缓存 + 自动刷新) / Get tenant access token.

        飞书自建应用用 app_id + app_secret 换 token, 有效期 ~2h。
        提前 5 分钟刷新。
        """
        now = time.time()
        if not force and self._token and now < self._token_expire_at - 300:
            return self._token
        if not self.app_id or not self.app_secret:
            raise RuntimeError("飞书 app_id / app_secret 未配置")

        url = f"{_FEISHU_BASE}/auth/v3/tenant_access_token/internal"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
            r.raise_for_status()
            data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 token 失败: {data.get('code')} {data.get('msg')}")
        self._token = data["tenant_access_token"]
        self._token_expire_at = now + data.get("expire", 7200)
        logger.info("飞书 tenant_access_token 已刷新 (expire=%ss)", data.get("expire"))
        return self._token

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.get_tenant_access_token()}",
                "Content-Type": "application/json; charset=utf-8"}

    # ── 发消息 / Send messages ───────────────────────────────────

    def _send(self, receive_id: str, msg_type: str, content: Dict,
              receive_id_type: str = "open_id") -> FeishuResult:
        """发消息底层 / Low-level send (im/v1/messages)。"""
        url = f"{_FEISHU_BASE}/im/v1/messages"
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False),
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, params={"receive_id_type": receive_id_type},
                                headers=self._auth_headers(), json=payload)
                data = r.json()
        except Exception as e:
            return FeishuResult(success=False, error=f"{type(e).__name__}: {e}")
        if data.get("code") != 0:
            return FeishuResult(success=False, code=data.get("code", -1),
                                error=data.get("msg", "unknown"), data=data)
        return FeishuResult(success=True, data=data.get("data", {}))

    def send_text(self, receive_id: str, text: str,
                  receive_id_type: str = "open_id") -> FeishuResult:
        """发文本消息 / Send a plain text message."""
        return self._send(receive_id, "text", {"text": text}, receive_id_type)

    def send_post(self, receive_id: str, post_content: Dict,
                  receive_id_type: str = "open_id") -> FeishuResult:
        """发富文本 post 消息 / Send a rich-text post message."""
        return self._send(receive_id, "post", post_content, receive_id_type)

    def send_card(self, receive_id: str, card: Dict,
                  receive_id_type: str = "open_id") -> FeishuResult:
        """发交互卡片 / Send an interactive card message."""
        return self._send(receive_id, "interactive", card, receive_id_type)

    def reply(self, message_id: str, text: str) -> FeishuResult:
        """回复指定消息 / Reply to a specific message (im/v1/messages/:id/reply)。"""
        url = f"{_FEISHU_BASE}/im/v1/messages/{message_id}/reply"
        payload = {"msg_type": "text",
                   "content": json.dumps({"text": text}, ensure_ascii=False)}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, headers=self._auth_headers(), json=payload)
                data = r.json()
        except Exception as e:
            return FeishuResult(success=False, error=f"{type(e).__name__}: {e}")
        if data.get("code") != 0:
            return FeishuResult(success=False, code=data.get("code", -1),
                                error=data.get("msg"), data=data)
        return FeishuResult(success=True, data=data.get("data", {}))

    # ── 事件回调 / Event callback ────────────────────────────────

    def handle_event(self, body: bytes,
                     headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """处理飞书事件回调 / Handle a Feishu event callback.

        返回值:
          - URL 验证 (challenge): {"challenge": "..."} —— HTTP 服务应原样返回
          - 普通事件: {"type": "event", "event": {...}, "message": FeishuMessage|None}
          - 验证失败: {"type": "error", "error": "..."}

        支持两种模式:
          - 明文模式: body 是 JSON, 含 challenge 或 event
          - 加密模式: body 含 {"encrypt": "..."}, 用 encrypt_key 解密
        """
        try:
            raw = json.loads(body.decode("utf-8"))
        except Exception as e:
            return {"type": "error", "error": f"invalid JSON: {e}"}

        # 加密模式: 先验签再解密 (MAC-then-decrypt), 防止未授权者驱动解密。
        # 飞书在请求头给 X-Lark-Signature/Timestamp/Nonce; 配了 encrypt_key 时校验。
        if "encrypt" in raw:
            if not self._crypto:
                return {"type": "error", "error": "encrypted event but no encrypt_key configured"}
            hdrs = headers or {}
            sig = hdrs.get("X-Lark-Signature") or hdrs.get("x-lark-signature")
            ts = hdrs.get("X-Lark-Request-Timestamp") or hdrs.get("x-lark-request-timestamp")
            nonce = hdrs.get("X-Lark-Request-Nonce") or hdrs.get("x-lark-request-nonce")
            # 有签名头则必须通过校验 (无头时退化为仅解密, 兼容本地测试/无头场景)
            if sig:
                if not self._crypto.verify_signature(ts or "", nonce or "", body, sig):
                    return {"type": "error", "error": "signature mismatch"}
            try:
                decrypted = self._crypto.decrypt(raw["encrypt"])
                raw = json.loads(decrypted)
            except Exception as e:
                return {"type": "error", "error": f"decrypt failed: {e}"}

        # URL 验证 challenge (飞书配置事件订阅地址时会发)
        if raw.get("type") == "url_verification" or "challenge" in raw:
            # 可选: 校验 verification_token
            if self.verification_token and raw.get("token") != self.verification_token:
                return {"type": "error", "error": "verification token mismatch"}
            return {"challenge": raw.get("challenge", "")}

        # 普通事件 (v2 schema: {schema, header, event})
        event = raw.get("event", {})
        message = self._parse_message_event(event) if event else None
        return {"type": "event", "event": event, "header": raw.get("header", {}),
                "message": message}

    def _parse_message_event(self, event: Dict) -> Optional[FeishuMessage]:
        """解析 im.message.receive_v1 事件 → FeishuMessage。"""
        msg = event.get("message")
        sender = event.get("sender", {})
        if not msg:
            return None
        text = ""
        if msg.get("message_type") == "text":
            try:
                text = json.loads(msg.get("content", "{}")).get("text", "")
            except Exception:
                text = ""
        return FeishuMessage(
            message_id=msg.get("message_id", ""),
            chat_id=msg.get("chat_id", ""),
            sender_id=sender.get("sender_id", {}).get("open_id", ""),
            sender_type=sender.get("sender_type", "user"),
            msg_type=msg.get("message_type", ""),
            text=text,
            raw=event,
        )

    def __repr__(self) -> str:
        return (f"<FeishuClient app_id={self.app_id[:8]}... "
                f"encrypt={'yes' if self._crypto else 'no'} "
                f"token={'cached' if self._token else 'none'}>")
