"""
Telegram 真实客户端 / Real Telegram Bot client.

真实可运行的 Telegram Bot API 实现 (非占位壳), 基于 httpx。覆盖:
  - getMe 验证 bot token
  - sendMessage (文本 / Markdown / HTML)
  - getUpdates (长轮询接收消息)
  - setWebhook / deleteWebhook (webhook 模式)
  - 解析 Update → TelegramMessage

环境变量: NONULL_TELEGRAM_BOT_TOKEN

参考: https://core.telegram.org/bots/api

@module: channels.telegram_client
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("Nonull.channels.telegram")


@dataclass
class TelegramMessage:
    """解析后的 Telegram 消息 / A parsed incoming Telegram message."""
    update_id: int
    message_id: int
    chat_id: int
    user_id: int
    username: str
    text: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TelegramResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class TelegramClient:
    """Telegram Bot 客户端 (真实 HTTP) / Telegram Bot client (real HTTP).

    Usage:
        client = TelegramClient(bot_token="123456:ABC...")
        client.send_message(chat_id=123, text="你好")
        updates = client.get_updates()           # 长轮询
        for msg in client.parse_updates(updates.data):
            ...
    """

    def __init__(self, bot_token: Optional[str] = None, timeout: float = 30.0):
        self.bot_token = bot_token or os.environ.get("NONULL_TELEGRAM_BOT_TOKEN", "")
        self.timeout = timeout
        self._base = f"https://api.telegram.org/bot{self.bot_token}"
        self._last_update_id = 0

    def _call(self, method: str, params: Optional[Dict] = None,
              timeout: Optional[float] = None) -> TelegramResult:
        """调用 Bot API 方法 / Call a Bot API method.

        timeout: 覆盖本次请求的 httpx 超时。长轮询 (getUpdates) 必须传一个
        大于服务端 hold 时间的超时, 否则 httpx 读超时会先于服务端返回触发,
        导致大量空轮询报 ReadTimeout 并丢消息。
        """
        if not self.bot_token:
            return TelegramResult(success=False, error="Telegram bot_token 未配置")
        url = f"{self._base}/{method}"
        eff_timeout = timeout if timeout is not None else self.timeout
        try:
            with httpx.Client(timeout=eff_timeout) as client:
                r = client.post(url, json=params or {})
                try:
                    data = r.json()
                except ValueError:
                    return TelegramResult(success=False,
                                          error=f"HTTP {r.status_code}: non-JSON response")
        except Exception as e:
            return TelegramResult(success=False, error=f"{type(e).__name__}: {e}")
        if not data.get("ok"):
            # 429 限流: 透出 retry_after, 让调用方退避而非空转
            retry = (data.get("parameters") or {}).get("retry_after")
            desc = data.get("description", "unknown")
            err = f"{desc} (retry_after={retry})" if retry else desc
            return TelegramResult(success=False, data=data, error=err)
        return TelegramResult(success=True, data=data.get("result", {}))

    # ── 验证 / Verify ────────────────────────────────────────────

    def get_me(self) -> TelegramResult:
        """验证 token, 返回 bot 信息 / Verify token via getMe."""
        return self._call("getMe")

    # ── 发消息 / Send ────────────────────────────────────────────

    def send_message(self, chat_id: int | str, text: str,
                     parse_mode: Optional[str] = None,
                     reply_to_message_id: Optional[int] = None) -> TelegramResult:
        """发文本消息 / Send a text message.

        parse_mode: None / "Markdown" / "MarkdownV2" / "HTML"
        """
        params: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_to_message_id:
            params["reply_to_message_id"] = reply_to_message_id
        return self._call("sendMessage", params)

    # ── 接收 / Receive ───────────────────────────────────────────

    def get_updates(self, offset: Optional[int] = None,
                    timeout: int = 0, limit: int = 100) -> TelegramResult:
        """长轮询拉取更新 / Long-poll for updates (getUpdates).

        offset 默认用上次最大 update_id + 1 (确认已处理的消息)。
        """
        params = {
            "offset": offset if offset is not None else self._last_update_id + 1,
            "timeout": timeout, "limit": limit,
        }
        # httpx 读超时必须严格大于服务端长轮询 hold 时间, 否则空轮询会先 ReadTimeout。
        http_timeout = self.timeout if timeout == 0 else float(timeout) + 10.0
        result = self._call("getUpdates", params, timeout=http_timeout)
        # 更新 last_update_id
        if result.success and isinstance(result.data, list):
            for upd in result.data:
                self._last_update_id = max(self._last_update_id, upd.get("update_id", 0))
        return result

    def parse_updates(self, updates: List[Dict]) -> List[TelegramMessage]:
        """解析 getUpdates 返回 → TelegramMessage 列表 (只取文本消息)。"""
        out: List[TelegramMessage] = []
        for upd in updates or []:
            msg = upd.get("message") or upd.get("edited_message")
            if not msg or "text" not in msg:
                continue
            chat = msg.get("chat", {})
            user = msg.get("from", {})
            out.append(TelegramMessage(
                update_id=upd.get("update_id", 0),
                message_id=msg.get("message_id", 0),
                chat_id=chat.get("id", 0),
                user_id=user.get("id", 0),
                username=user.get("username", "") or user.get("first_name", ""),
                text=msg.get("text", ""),
                raw=upd,
            ))
        return out

    # ── Webhook ──────────────────────────────────────────────────

    def set_webhook(self, url: str, secret_token: Optional[str] = None) -> TelegramResult:
        """设置 webhook / Register a webhook URL."""
        params: Dict[str, Any] = {"url": url}
        if secret_token:
            params["secret_token"] = secret_token
        return self._call("setWebhook", params)

    def delete_webhook(self) -> TelegramResult:
        """删除 webhook (回到长轮询模式)。"""
        return self._call("deleteWebhook")

    def parse_webhook_update(self, body: Dict) -> Optional[TelegramMessage]:
        """解析单个 webhook 推送的 Update → TelegramMessage。"""
        msgs = self.parse_updates([body])
        return msgs[0] if msgs else None

    def __repr__(self) -> str:
        tok = self.bot_token.split(":")[0] if ":" in self.bot_token else "none"
        return f"<TelegramClient bot_id={tok}>"
