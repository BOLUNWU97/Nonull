"""
钉钉 (DingTalk) 真实客户端 / Real DingTalk client.

真实可运行的钉钉 API 实现 (非占位壳), 基于 httpx。覆盖钉钉两种机器人形态:

  1. **自定义机器人 webhook** (DingTalkWebhookBot): 群里加的自定义机器人, 用
     webhook URL + 加签 secret。最简单, 无需企业应用。支持文本/markdown/
     ActionCard。HMAC-SHA256 加签防伪造。

  2. **企业内部应用** (DingTalkAppClient): 用 AppKey + AppSecret 换 access_token,
     可主动发消息给用户/群、处理回调事件。

事件回调验签: 钉钉用 AES 加密回调 (与飞书类似但格式不同), 这里实现 token 校验
+ AES 解密。

环境变量:
  NONULL_DINGTALK_WEBHOOK / NONULL_DINGTALK_SECRET  (自定义机器人)
  NONULL_DINGTALK_APP_KEY / NONULL_DINGTALK_APP_SECRET  (企业应用)

参考: https://open.dingtalk.com/document/orgapp

@module: channels.dingtalk_client
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("Nonull.channels.dingtalk")

_DING_BASE = "https://api.dingtalk.com"
_DING_OAPI = "https://oapi.dingtalk.com"


@dataclass
class DingResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    code: int = 0


# ── 自定义机器人 webhook (加签) ──────────────────────────────────

class DingTalkWebhookBot:
    """钉钉自定义机器人 (webhook + 加签) / Custom robot via webhook + HMAC sign.

    Usage:
        bot = DingTalkWebhookBot(webhook="https://oapi.dingtalk.com/robot/send?access_token=xxx",
                                 secret="SECxxx")
        bot.send_text("你好")
        bot.send_markdown("标题", "## 正文\\n- 项目")
    """

    def __init__(self, webhook: Optional[str] = None, secret: Optional[str] = None,
                 timeout: float = 15.0):
        self.webhook = webhook or os.environ.get("NONULL_DINGTALK_WEBHOOK", "")
        self.secret = secret or os.environ.get("NONULL_DINGTALK_SECRET", "")
        self.timeout = timeout

    def _signed_url(self) -> str:
        """钉钉加签: timestamp + HMAC-SHA256(secret) → 附加到 URL。

        sign = base64(hmac_sha256(secret, f"{timestamp}\\n{secret}"))
        防止 webhook 被盗用 (钉钉安全设置选"加签"时必须)。
        """
        if not self.secret:
            return self.webhook
        ts = str(round(time.time() * 1000))
        string_to_sign = f"{ts}\n{self.secret}"
        h = hmac.new(self.secret.encode("utf-8"),
                     string_to_sign.encode("utf-8"), hashlib.sha256)
        sign = urllib.parse.quote_plus(base64.b64encode(h.digest()))
        sep = "&" if "?" in self.webhook else "?"
        return f"{self.webhook}{sep}timestamp={ts}&sign={sign}"

    def _post(self, payload: Dict) -> DingResult:
        if not self.webhook:
            return DingResult(success=False, error="钉钉 webhook 未配置")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(self._signed_url(), json=payload,
                                headers={"Content-Type": "application/json"})
                data = r.json()
        except Exception as e:
            return DingResult(success=False, error=f"{type(e).__name__}: {e}")
        # 钉钉成功 errcode=0
        if data.get("errcode", 0) != 0:
            return DingResult(success=False, code=data.get("errcode", -1),
                              error=data.get("errmsg", "unknown"), data=data)
        return DingResult(success=True, data=data)

    def send_text(self, text: str, at_mobiles: Optional[list] = None,
                  at_all: bool = False) -> DingResult:
        """发文本 (可 @ 人)。"""
        payload = {"msgtype": "text", "text": {"content": text},
                   "at": {"atMobiles": at_mobiles or [], "isAtAll": at_all}}
        return self._post(payload)

    def send_markdown(self, title: str, text: str, at_all: bool = False) -> DingResult:
        """发 markdown 消息。"""
        payload = {"msgtype": "markdown",
                   "markdown": {"title": title, "text": text},
                   "at": {"isAtAll": at_all}}
        return self._post(payload)

    def send_action_card(self, title: str, text: str,
                         btn_title: str, btn_url: str) -> DingResult:
        """发 ActionCard (带单按钮)。"""
        payload = {"msgtype": "actionCard",
                   "actionCard": {"title": title, "text": text,
                                  "singleTitle": btn_title, "singleURL": btn_url}}
        return self._post(payload)


# ── 企业内部应用 (access_token) ──────────────────────────────────

class DingTalkAppClient:
    """钉钉企业内部应用客户端 / DingTalk enterprise app client.

    用 AppKey + AppSecret 换 access_token, 可主动发消息、查用户等。

    Usage:
        app = DingTalkAppClient(app_key="ding_xxx", app_secret="yyy")
        token = app.get_access_token()
        app.send_to_robot(robot_code="...", user_ids=["..."], text="你好")
    """

    def __init__(self, app_key: Optional[str] = None, app_secret: Optional[str] = None,
                 timeout: float = 15.0):
        self.app_key = app_key or os.environ.get("NONULL_DINGTALK_APP_KEY", "")
        self.app_secret = app_secret or os.environ.get("NONULL_DINGTALK_APP_SECRET", "")
        self.timeout = timeout
        self._token = ""
        self._token_expire_at = 0.0

    def get_access_token(self, force: bool = False) -> str:
        """获取 access_token (缓存 + 自动刷新, 有效期 ~2h)。"""
        now = time.time()
        if not force and self._token and now < self._token_expire_at - 300:
            return self._token
        if not self.app_key or not self.app_secret:
            raise RuntimeError("钉钉 app_key / app_secret 未配置")
        url = f"{_DING_BASE}/v1.0/oauth2/accessToken"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json={"appKey": self.app_key,
                                       "appSecret": self.app_secret})
            r.raise_for_status()
            data = r.json()
        if "accessToken" not in data:
            raise RuntimeError(f"获取 access_token 失败: {data}")
        self._token = data["accessToken"]
        self._token_expire_at = now + data.get("expireIn", 7200)
        logger.info("钉钉 access_token 已刷新 (expireIn=%ss)", data.get("expireIn"))
        return self._token

    def send_to_robot(self, robot_code: str, user_ids: list, text: str) -> DingResult:
        """通过企业机器人发消息给指定用户 (oToMessages/batchSend)。"""
        url = f"{_DING_BASE}/v1.0/robot/oToMessages/batchSend"
        payload = {
            "robotCode": robot_code,
            "userIds": user_ids,
            "msgKey": "sampleText",
            "msgParam": json.dumps({"content": text}, ensure_ascii=False),
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, headers={
                    "x-acs-dingtalk-access-token": self.get_access_token(),
                    "Content-Type": "application/json",
                }, json=payload)
                data = r.json()
        except Exception as e:
            return DingResult(success=False, error=f"{type(e).__name__}: {e}")
        if "processQueryKey" in data:
            return DingResult(success=True, data=data)
        return DingResult(success=False, error=str(data), data=data)


# ── 回调验签 / Callback verification ─────────────────────────────

class DingTalkCrypto:
    """钉钉回调 AES 解密 + 验签 / DingTalk callback AES decryption.

    钉钉回调用 AES-256-CBC (PKCS7), key = base64decode(aes_key + "="), 32 字节。
    密文格式: base64(random16 + msg_len(4, 大端) + msg + corp_id)。
    """

    def __init__(self, token: str, aes_key: str, corp_id: str = ""):
        self.token = token
        self.corp_id = corp_id
        self._key = base64.b64decode(aes_key + "=")

    def verify_signature(self, timestamp: str, nonce: str, encrypt: str, signature: str) -> bool:
        """验签: sha1(sorted(token, timestamp, nonce, encrypt))。"""
        params = sorted([self.token, timestamp, nonce, encrypt])
        sha = hashlib.sha1()
        sha.update("".join(params).encode("utf-8"))
        return sha.hexdigest() == signature

    def decrypt(self, encrypt_b64: str) -> str:
        """解密钉钉回调密文 → 明文 JSON。"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
        except ImportError:
            raise RuntimeError("钉钉回调解密需要 cryptography: pip install cryptography")
        raw = base64.b64decode(encrypt_b64)
        iv = self._key[:16]
        cipher = Cipher(algorithms.AES(self._key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(raw) + decryptor.finalize()
        pad_len = padded[-1]
        content = padded[:-pad_len]
        # 跳过前 16 随机字节, 读 4 字节大端长度
        msg_len = int.from_bytes(content[16:20], "big")
        msg = content[20:20 + msg_len].decode("utf-8")
        return msg
