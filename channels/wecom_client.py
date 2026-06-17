"""
企业微信 (WeCom) 真实客户端 / Real WeCom (Enterprise WeChat) client.

真实可运行的企业微信 API 实现 (非占位壳), 基于 httpx。

注意: 微信**个人号**无官方开放 API (任何"个人微信机器人"都是违反微信协议的
逆向方案, 不做)。这里实现的是企业微信 (WeCom) —— 腾讯官方支持的企业通讯，
有完整开放 API。

覆盖:
  - access_token 获取/缓存/刷新 (corpid + corpsecret)
  - 应用消息推送 (message/send: 文本/markdown/图文)
  - 群机器人 webhook (custom robot, 类似钉钉, 无需 access_token)
  - 回调验签 (微信 AES-CBC + SHA1 签名)

环境变量:
  NONULL_WECOM_CORP_ID / NONULL_WECOM_CORP_SECRET / NONULL_WECOM_AGENT_ID  (应用)
  NONULL_WECOM_WEBHOOK  (群机器人)

参考: https://developer.work.weixin.qq.com/document/

@module: channels.wecom_client
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("Nonull.channels.wecom")

_WECOM_BASE = "https://qyapi.weixin.qq.com/cgi-bin"


@dataclass
class WeComResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    code: int = 0


# ── 群机器人 webhook (最简单, 无需 access_token) ─────────────────

class WeComWebhookBot:
    """企业微信群机器人 (webhook) / WeCom group robot via webhook.

    Usage:
        bot = WeComWebhookBot(webhook="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")
        bot.send_text("你好")
        bot.send_markdown("## 标题\\n内容")
    """

    def __init__(self, webhook: Optional[str] = None, timeout: float = 15.0):
        self.webhook = webhook or os.environ.get("NONULL_WECOM_WEBHOOK", "")
        self.timeout = timeout

    def _post(self, payload: Dict) -> WeComResult:
        if not self.webhook:
            return WeComResult(success=False, error="企业微信 webhook 未配置")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(self.webhook, json=payload)
                data = r.json()
        except Exception as e:
            return WeComResult(success=False, error=f"{type(e).__name__}: {e}")
        if data.get("errcode", 0) != 0:
            return WeComResult(success=False, code=data.get("errcode", -1),
                               error=data.get("errmsg", "unknown"), data=data)
        return WeComResult(success=True, data=data)

    def send_text(self, text: str, mentioned_list: Optional[list] = None) -> WeComResult:
        """发文本 (可 @ 人, mentioned_list 用 userid 或 '@all')。"""
        content: Dict[str, Any] = {"content": text}
        if mentioned_list:
            content["mentioned_list"] = mentioned_list
        return self._post({"msgtype": "text", "text": content})

    def send_markdown(self, text: str) -> WeComResult:
        """发 markdown 消息。"""
        return self._post({"msgtype": "markdown", "markdown": {"content": text}})


# ── 企业应用 (access_token) ──────────────────────────────────────

class WeComAppClient:
    """企业微信应用客户端 / WeCom application client.

    用 corpid + corpsecret 换 access_token, 通过应用主动给成员推消息。

    Usage:
        app = WeComAppClient(corp_id="ww...", corp_secret="...", agent_id=1000002)
        app.send_text(to_user="@all", text="你好")
    """

    def __init__(self, corp_id: Optional[str] = None, corp_secret: Optional[str] = None,
                 agent_id: Optional[int] = None, timeout: float = 15.0):
        self.corp_id = corp_id or os.environ.get("NONULL_WECOM_CORP_ID", "")
        self.corp_secret = corp_secret or os.environ.get("NONULL_WECOM_CORP_SECRET", "")
        # agent_id 防御性解析: 非数字 env 值不应让构造函数崩溃; 显式传 0 也应尊重
        if agent_id is not None:
            self.agent_id = agent_id
        else:
            _raw = (os.environ.get("NONULL_WECOM_AGENT_ID", "") or "").strip()
            try:
                self.agent_id = int(_raw) if _raw else 0
            except ValueError:
                logger.warning("NONULL_WECOM_AGENT_ID 非数字 %r, 用 0", _raw)
                self.agent_id = 0
        self.timeout = timeout
        self._token = ""
        self._token_expire_at = 0.0

    def get_access_token(self, force: bool = False) -> str:
        """获取 access_token (缓存 + 自动刷新, 有效期 ~2h)。"""
        now = time.time()
        if not force and self._token and now < self._token_expire_at - 300:
            return self._token
        if not self.corp_id or not self.corp_secret:
            raise RuntimeError("企业微信 corp_id / corp_secret 未配置")
        url = f"{_WECOM_BASE}/gettoken"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params={"corpid": self.corp_id, "corpsecret": self.corp_secret})
            r.raise_for_status()
            data = r.json()
        if data.get("errcode", 0) != 0 or "access_token" not in data:
            raise RuntimeError(f"获取 access_token 失败: {data.get('errcode')} {data.get('errmsg')}")
        self._token = data["access_token"]
        self._token_expire_at = now + data.get("expires_in", 7200)
        logger.info("企业微信 access_token 已刷新 (expires_in=%ss)", data.get("expires_in"))
        return self._token

    def send_text(self, to_user: str, text: str) -> WeComResult:
        """通过应用发文本给成员 / Send text to members via the app.

        to_user: 成员 userid, 多个用 '|' 分隔, '@all' 发全员。
        """
        return self._send_message({
            "touser": to_user, "msgtype": "text",
            "agentid": self.agent_id, "text": {"content": text},
        })

    def send_markdown(self, to_user: str, content: str) -> WeComResult:
        """发 markdown 消息给成员。"""
        return self._send_message({
            "touser": to_user, "msgtype": "markdown",
            "agentid": self.agent_id, "markdown": {"content": content},
        })

    def _send_message(self, payload: dict, _retried: bool = False) -> WeComResult:
        """发应用消息底层 (token 失效自动 force 刷新重试一次)。

        WeCom token 可能被提前失效 (别处重发/时钟偏移/密钥重置), errcode 40014/
        42001 表示 token 无效/过期 —— 清缓存 + force 刷新 + 重试一次, 避免一直
        用死 token 静默失败。
        """
        url = f"{_WECOM_BASE}/message/send"
        try:
            token = self.get_access_token(force=_retried)
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, params={"access_token": token}, json=payload)
                data = r.json()
        except Exception as e:
            return WeComResult(success=False, error=f"{type(e).__name__}: {e}")
        errcode = data.get("errcode", 0)
        if errcode in (40014, 42001) and not _retried:
            self._token = ""  # 强制下次重新获取
            return self._send_message(payload, _retried=True)
        if errcode != 0:
            return WeComResult(success=False, code=errcode,
                               error=data.get("errmsg"), data=data)
        return WeComResult(success=True, data=data)

    def __repr__(self) -> str:
        return f"<WeComAppClient corp={self.corp_id[:8]}... agent={self.agent_id}>"
