"""
QQ 官方机器人客户端 / Official QQ Bot client.

真实可运行的 QQ 开放平台机器人 API 实现 (非占位壳), 基于 httpx。

注意: QQ **个人号**无官方 API。这里实现的是 QQ 开放平台官方机器人
(https://bot.q.qq.com) —— 腾讯官方支持, 用于频道/群的机器人。

覆盖:
  - app_access_token 获取/缓存/刷新 (appid + clientSecret)
  - 主动发频道消息 / 群消息
  - 被动回复 (用收到消息的 msg_id, 免费额度)
  - 回调事件签名验证 (Ed25519)

环境变量:
  NONULL_QQ_APP_ID / NONULL_QQ_CLIENT_SECRET / NONULL_QQ_TOKEN

参考: https://bot.q.qq.com/wiki/develop/api-v2/

@module: channels.qq_client
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("Nonull.channels.qq")

_QQ_BASE = "https://api.sgroup.qq.com"
_QQ_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"


@dataclass
class QQResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    code: int = 0


@dataclass
class QQMessage:
    """解析后的 QQ 机器人消息 / A parsed incoming QQ bot message."""
    msg_id: str
    channel_id: str = ""
    group_id: str = ""
    author_id: str = ""
    content: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class QQBotClient:
    """QQ 官方机器人客户端 (真实 HTTP) / Official QQ bot client (real HTTP).

    Usage:
        client = QQBotClient(app_id="123", client_secret="xxx")
        token = client.get_access_token()
        client.send_channel_message(channel_id="...", content="你好")
        client.reply_group_message(group_openid="...", msg_id="...", content="收到")
    """

    def __init__(self, app_id: Optional[str] = None, client_secret: Optional[str] = None,
                 token: Optional[str] = None, timeout: float = 15.0):
        self.app_id = app_id or os.environ.get("NONULL_QQ_APP_ID", "")
        self.client_secret = client_secret or os.environ.get("NONULL_QQ_CLIENT_SECRET", "")
        self.token = token or os.environ.get("NONULL_QQ_TOKEN", "")
        self.timeout = timeout
        self._access_token = ""
        self._token_expire_at = 0.0
        self._token_lock = threading.Lock()  # token 缓存并发保护

    def get_access_token(self, force: bool = False) -> str:
        """获取 app_access_token (缓存 + 刷新, 有效期 ~7200s, 线程安全)。"""
        now = time.time()
        if not force and self._access_token and now < self._token_expire_at - 300:
            return self._access_token
        if not self.app_id or not self.client_secret:
            raise RuntimeError("QQ app_id / client_secret 未配置")
        with self._token_lock:  # 双检锁防多线程 thundering herd
            now = time.time()
            if not force and self._access_token and now < self._token_expire_at - 300:
                return self._access_token
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(_QQ_TOKEN_URL, json={
                    "appId": self.app_id, "clientSecret": self.client_secret})
                r.raise_for_status()
                data = r.json()
            if "access_token" not in data:
                raise RuntimeError(f"获取 access_token 失败: {data}")
            self._access_token = data["access_token"]
            self._token_expire_at = now + int(data.get("expires_in", 7200))
            logger.info("QQ access_token 已刷新 (expires_in=%ss)", data.get("expires_in"))
            return self._access_token

    def _auth_headers(self) -> Dict[str, str]:
        # QQ v2 用 QQBot <app_access_token> 鉴权头
        return {"Authorization": f"QQBot {self.get_access_token()}",
                "Content-Type": "application/json"}

    def _post(self, endpoint: str, payload: Dict) -> QQResult:
        url = f"{_QQ_BASE}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, headers=self._auth_headers(), json=payload)
                status = r.status_code
                try:
                    data = r.json() if r.content else {}
                except ValueError:
                    # 非 JSON 响应 (网关 502 HTML 等): 透出状态码 + 原文
                    return QQResult(success=False, code=status,
                                    error=f"HTTP {status}: {r.text[:200]}")
        except Exception as e:
            return QQResult(success=False, error=f"{type(e).__name__}: {e}")
        # 4xx/5xx 即便 JSON 体无 code 也算失败 (之前会误判成功)
        if status >= 400:
            return QQResult(success=False, code=status,
                            error=(data.get("message") if isinstance(data, dict) else "") or f"HTTP {status}",
                            data=data if isinstance(data, dict) else {})
        # QQ 成功返回含 id; 失败含 code/message
        if isinstance(data, dict) and data.get("code"):
            return QQResult(success=False, code=data.get("code", -1),
                            error=data.get("message", "unknown"), data=data)
        return QQResult(success=True, data=data if isinstance(data, dict) else {})

    # ── 频道消息 / Channel (guild) messages ──────────────────────

    def send_channel_message(self, channel_id: str, content: str,
                             msg_id: Optional[str] = None) -> QQResult:
        """发频道消息 / Send a channel (guild) message.

        msg_id: 传入收到消息的 id → 被动回复 (免费); 不传 → 主动推送 (有额度限制)。
        """
        payload: Dict[str, Any] = {"content": content}
        if msg_id:
            payload["msg_id"] = msg_id
        return self._post(f"/channels/{channel_id}/messages", payload)

    # ── 群消息 / Group messages (v2) ─────────────────────────────

    def send_group_message(self, group_openid: str, content: str,
                           msg_id: Optional[str] = None, msg_seq: int = 1) -> QQResult:
        """发群消息 / Send a group message (v2 API).

        msg_type=0 文本。msg_id 传入则为被动回复。
        """
        payload: Dict[str, Any] = {"content": content, "msg_type": 0}
        if msg_id:
            payload["msg_id"] = msg_id
            payload["msg_seq"] = msg_seq
        return self._post(f"/v2/groups/{group_openid}/messages", payload)

    def reply_group_message(self, group_openid: str, msg_id: str, content: str,
                            msg_seq: int = 1) -> QQResult:
        """被动回复群消息 (用收到的 msg_id)。

        msg_seq: QQ 要求同一 msg_id 的多次回复 msg_seq 必须唯一, 否则被去重丢弃。
        对同一条消息多次回复时调用方需递增 msg_seq。
        """
        return self.send_group_message(group_openid, content, msg_id=msg_id, msg_seq=msg_seq)

    # ── 回调验签 (Ed25519) ───────────────────────────────────────

    def _ed25519_private_key(self):
        """从 client_secret 派生 Ed25519 私钥 (seed 填充到 32 字节)。"""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        if not self.client_secret:
            raise RuntimeError("QQ client_secret 未配置, 无法验签")
        seed = self.client_secret
        while len(seed) < 32:
            seed = (seed + seed)[:32]
        return Ed25519PrivateKey.from_private_bytes(seed.encode("utf-8")[:32])

    def sign_validation(self, plain_token: str, event_ts: str) -> str:
        """QQ webhook URL 验证 (op=13): 签名 event_ts+plain_token 返回 hex。

        QQ 配置回调地址时先发验证请求, bot 必须用私钥签名 (event_ts + plain_token)
        并在响应体返回 {plain_token, signature}。缺这一步 webhook 永远验证不过。
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa
        except ImportError:
            raise RuntimeError("QQ 验证需要 cryptography: pip install cryptography")
        priv = self._ed25519_private_key()
        sig = priv.sign(event_ts.encode("utf-8") + plain_token.encode("utf-8"))
        return sig.hex()

    def verify_signature(self, event_ts: str, body: bytes,
                         signature_hex: str) -> bool:
        """验证 QQ 回调事件签名 (Ed25519) / Verify inbound event signature.

        验证 sign(event_ts + body)。需要 cryptography。
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa
        except ImportError:
            raise RuntimeError("QQ 回调验签需要 cryptography: pip install cryptography")
        priv = self._ed25519_private_key()
        pub = priv.public_key()
        message = event_ts.encode("utf-8") + body
        try:
            pub.verify(bytes.fromhex(signature_hex), message)
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<QQBotClient app_id={self.app_id}>"
