"""
统一渠道调度中心 / Unified channel hub.

把 5 个平台客户端 (飞书/钉钉/Telegram/企业微信/QQ) 统一到一个接口:
标准化的「收消息 → 跑 agent → 回消息」闭环, 一套代码全渠道适配。

设计:
  - IncomingMessage: 所有平台收到的消息归一化为同一结构 (channel/user/chat/text)
  - ChannelHub: 注册多个渠道客户端, 事件进来 → 归一化 → 跑 handler (默认接 agent)
    → 把结果按各平台的 API 发回去。
  - 每个平台的 client 已实现真实 HTTP (见 channels/*_client.py), Hub 只做编排。

用法:
    hub = ChannelHub(agent=my_nonull_agent)
    hub.register_feishu(app_id=..., app_secret=..., encrypt_key=...)
    hub.register_telegram(bot_token=...)
    # FastAPI 路由里:
    result = await hub.handle_feishu_event(body, headers)   # 自动跑 agent + 回复
    # 或 Telegram 长轮询:
    await hub.poll_telegram_once()

@module: channels.channel_hub
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("Nonull.channels.hub")


@dataclass
class IncomingMessage:
    """归一化的入站消息 / Normalized inbound message across all platforms."""
    channel: str          # "feishu" | "dingtalk" | "telegram" | "wecom" | "qq"
    text: str
    user_id: str = ""     # 发送者标识 (open_id / user_id / chat id)
    chat_id: str = ""     # 会话标识 (用于回复)
    message_id: str = ""  # 原消息 id (用于被动回复)
    extra: Dict[str, Any] = field(default_factory=dict)  # 平台特有字段 (group_openid 等)
    raw: Any = None


@dataclass
class OutgoingReply:
    """统一回复结构 / Unified reply (Hub 据此调各平台 API 发送)。"""
    text: str
    success: bool = True


# handler 签名: (IncomingMessage) -> str | Awaitable[str]
HandlerType = Callable[[IncomingMessage], Any]


class ChannelHub:
    """统一渠道调度中心 / Unified multi-platform channel hub.

    把入站消息归一化后交给一个 handler (默认: 跑 Nonull agent), 再把回复按各
    平台 API 发回。一套 handler 逻辑, 全渠道复用。
    """

    def __init__(self, agent: Any = None, handler: Optional[HandlerType] = None,
                 max_reply_len: int = 2000):
        """
        agent: Nonull 实例 (有 .run(task) -> {output}); 提供则默认 handler 跑它。
        handler: 自定义消息处理函数 (覆盖默认 agent 行为)。
        """
        self.agent = agent
        self.handler = handler
        self.max_reply_len = max_reply_len
        self._clients: Dict[str, Any] = {}    # channel -> client
        self._metrics: Dict[str, int] = {"received": 0, "handled": 0, "replied": 0, "errors": 0}

    # ── 注册渠道 / Register channels ─────────────────────────────

    def register_feishu(self, **kwargs) -> "ChannelHub":
        from channels.feishu_client import FeishuClient
        self._clients["feishu"] = FeishuClient(**kwargs)
        logger.info("已注册飞书渠道 / feishu channel registered")
        return self

    def register_dingtalk(self, **kwargs) -> "ChannelHub":
        from channels.dingtalk_client import DingTalkClient
        self._clients["dingtalk"] = DingTalkClient(**kwargs)
        logger.info("已注册钉钉渠道 / dingtalk channel registered")
        return self

    def register_telegram(self, **kwargs) -> "ChannelHub":
        from channels.telegram_client import TelegramClient
        self._clients["telegram"] = TelegramClient(**kwargs)
        logger.info("已注册 Telegram 渠道 / telegram channel registered")
        return self

    def register_wecom(self, **kwargs) -> "ChannelHub":
        from channels.wecom_client import WeComAppClient
        self._clients["wecom"] = WeComAppClient(**kwargs)
        logger.info("已注册企业微信渠道 / wecom channel registered")
        return self

    def register_qq(self, **kwargs) -> "ChannelHub":
        from channels.qq_client import QQBotClient
        self._clients["qq"] = QQBotClient(**kwargs)
        logger.info("已注册 QQ 渠道 / qq channel registered")
        return self

    def client(self, channel: str) -> Any:
        return self._clients.get(channel)

    @property
    def channels(self) -> List[str]:
        return list(self._clients.keys())

    # ── 核心: 跑 handler / Run handler ───────────────────────────

    async def _run_handler(self, msg: IncomingMessage) -> str:
        """跑消息处理逻辑 (handler 优先, 否则 agent, 否则回显)。"""
        self._metrics["handled"] += 1
        try:
            if self.handler is not None:
                result = self.handler(msg)
                if hasattr(result, "__await__"):
                    result = await result
                return str(result)
            if self.agent is not None:
                run_result = await self.agent.run(msg.text)
                return str(run_result.get("output") or "（无输出）")
            return f"收到: {msg.text}"
        except Exception as e:
            self._metrics["errors"] += 1
            logger.exception("handler 执行失败 / handler failed")
            return f"处理出错: {type(e).__name__}: {e}"

    def _truncate(self, text: str) -> str:
        return text[: self.max_reply_len]

    # ── 飞书 / Feishu ────────────────────────────────────────────

    async def handle_feishu_event(self, body: bytes,
                                  headers: Optional[Dict] = None) -> Dict[str, Any]:
        """处理飞书事件回调 (URL 验证 / 消息 → agent → reply)。"""
        client = self._clients.get("feishu")
        if not client:
            return {"error": "feishu not registered"}
        result = client.handle_event(body, headers)
        if "challenge" in result:
            return {"challenge": result["challenge"]}
        if result.get("type") == "error":
            return {"code": -1, "error": result["error"]}
        fm = result.get("message")
        if fm and fm.text and fm.sender_type == "user":
            self._metrics["received"] += 1
            msg = IncomingMessage(channel="feishu", text=fm.text,
                                  user_id=fm.sender_id, chat_id=fm.chat_id,
                                  message_id=fm.message_id, raw=fm)
            reply = self._truncate(await self._run_handler(msg))
            r = client.reply(fm.message_id, reply)
            if getattr(r, "success", False):
                self._metrics["replied"] += 1
        return {"code": 0}

    # ── 钉钉 / DingTalk ──────────────────────────────────────────

    async def handle_dingtalk_event(self, body: bytes,
                                    headers: Optional[Dict] = None) -> Dict[str, Any]:
        """处理钉钉事件回调。"""
        client = self._clients.get("dingtalk")
        if not client:
            return {"error": "dingtalk not registered"}
        result = client.handle_event(body, headers) if hasattr(client, "handle_event") else {}
        if result.get("type") == "error":
            return {"code": -1, "error": result["error"]}
        dm = result.get("message")
        if dm and getattr(dm, "text", ""):
            self._metrics["received"] += 1
            msg = IncomingMessage(channel="dingtalk", text=dm.text,
                                  user_id=getattr(dm, "sender_id", ""),
                                  chat_id=getattr(dm, "conversation_id", ""),
                                  raw=dm)
            reply = self._truncate(await self._run_handler(msg))
            if hasattr(client, "send_text") and msg.chat_id:
                client.send_text(msg.chat_id, reply)
                self._metrics["replied"] += 1
        return {"code": 0}

    # ── Telegram ─────────────────────────────────────────────────

    async def poll_telegram_once(self, timeout: int = 25) -> int:
        """Telegram 长轮询一轮: 拉更新 → 每条跑 agent → 回复。返回处理条数。"""
        client = self._clients.get("telegram")
        if not client:
            return 0
        result = client.get_updates(timeout=timeout)
        if not result.success:
            return 0
        count = 0
        for tm in client.parse_updates(result.data):
            self._metrics["received"] += 1
            msg = IncomingMessage(channel="telegram", text=tm.text,
                                  user_id=str(tm.user_id), chat_id=str(tm.chat_id),
                                  message_id=str(tm.message_id), raw=tm)
            reply = self._truncate(await self._run_handler(msg))
            r = client.send_message(tm.chat_id, reply, reply_to_message_id=tm.message_id)
            if getattr(r, "success", False):
                self._metrics["replied"] += 1
            count += 1
        return count

    async def handle_telegram_webhook(self, body: Dict) -> Dict[str, Any]:
        """处理 Telegram webhook 推送的单条 Update。"""
        client = self._clients.get("telegram")
        if not client:
            return {"error": "telegram not registered"}
        tm = client.parse_webhook_update(body)
        if tm and tm.text:
            self._metrics["received"] += 1
            msg = IncomingMessage(channel="telegram", text=tm.text,
                                  user_id=str(tm.user_id), chat_id=str(tm.chat_id),
                                  message_id=str(tm.message_id), raw=tm)
            reply = self._truncate(await self._run_handler(msg))
            r = client.send_message(tm.chat_id, reply, reply_to_message_id=tm.message_id)
            if getattr(r, "success", False):
                self._metrics["replied"] += 1
        return {"ok": True}

    # ── QQ ───────────────────────────────────────────────────────

    async def handle_qq_message(self, msg_type: str, target_id: str,
                                text: str, msg_id: str = "") -> Dict[str, Any]:
        """处理 QQ 消息 (msg_type: 'channel' | 'group') → agent → 回复。"""
        client = self._clients.get("qq")
        if not client:
            return {"error": "qq not registered"}
        self._metrics["received"] += 1
        msg = IncomingMessage(channel="qq", text=text, chat_id=target_id,
                              message_id=msg_id, extra={"msg_type": msg_type})
        reply = self._truncate(await self._run_handler(msg))
        if msg_type == "channel":
            r = client.send_channel_message(target_id, reply, msg_id=msg_id or None)
        else:
            r = client.reply_group_message(target_id, msg_id, reply) if msg_id \
                else client.send_group_message(target_id, reply)
        if getattr(r, "success", False):
            self._metrics["replied"] += 1
        return {"code": 0}

    # ── 主动推送 (任意渠道统一接口) ──────────────────────────────

    def push(self, channel: str, target: str, text: str, **kwargs) -> Any:
        """主动推消息到指定渠道 / Proactively push a message to a channel.

        target 含义随渠道而定: 飞书=open_id/chat_id, telegram=chat_id,
        wecom=userid, qq=channel_id。
        """
        client = self._clients.get(channel)
        if not client:
            return OutgoingReply(text="", success=False)
        text = self._truncate(text)
        if channel == "feishu":
            return client.send_text(target, text, **kwargs)
        if channel == "telegram":
            return client.send_message(target, text, **kwargs)
        if channel == "wecom":
            return client.send_text(target, text)
        if channel == "dingtalk":
            return client.send_text(target, text) if hasattr(client, "send_text") else None
        if channel == "qq":
            return client.send_channel_message(target, text)
        return OutgoingReply(text="", success=False)

    def metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    def __repr__(self) -> str:
        return f"<ChannelHub channels={self.channels} agent={'yes' if self.agent else 'no'}>"
