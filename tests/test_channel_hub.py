"""
统一渠道调度中心测试 / Tests for ChannelHub.

验证 5 渠道统一闭环 (收消息 → 跑 agent/handler → 回复), mock 客户端, $0。
"""
import json

import pytest

from channels.channel_hub import ChannelHub, IncomingMessage, OutgoingReply


class _FakeAgent:
    """假 agent: run 返回固定 output。"""
    def __init__(self, output="agent 回复"):
        self.output = output
        self.calls = []
    async def run(self, task):
        self.calls.append(task)
        return {"output": f"{self.output}: {task}"}


# ── handler / agent 桥接 ─────────────────────────────────────────

class TestHandler:
    async def test_agent_bridge(self):
        hub = ChannelHub(agent=_FakeAgent())
        msg = IncomingMessage(channel="test", text="你好")
        reply = await hub._run_handler(msg)
        assert "你好" in reply

    async def test_custom_handler_sync(self):
        hub = ChannelHub(handler=lambda m: f"echo:{m.text}")
        reply = await hub._run_handler(IncomingMessage(channel="t", text="hi"))
        assert reply == "echo:hi"

    async def test_custom_handler_async(self):
        async def h(m):
            return f"async:{m.text}"
        hub = ChannelHub(handler=h)
        reply = await hub._run_handler(IncomingMessage(channel="t", text="x"))
        assert reply == "async:x"

    async def test_no_agent_no_handler_echoes(self):
        hub = ChannelHub()
        reply = await hub._run_handler(IncomingMessage(channel="t", text="ping"))
        assert "ping" in reply

    async def test_handler_error_caught(self):
        def boom(m):
            raise ValueError("boom")
        hub = ChannelHub(handler=boom)
        reply = await hub._run_handler(IncomingMessage(channel="t", text="x"))
        assert "出错" in reply or "boom" in reply
        assert hub.metrics()["errors"] == 1

    async def test_reply_truncated(self):
        hub = ChannelHub(handler=lambda m: "x" * 5000, max_reply_len=100)
        reply = await hub._run_handler(IncomingMessage(channel="t", text="x"))
        assert len(hub._truncate(reply)) == 100


# ── 注册渠道 ─────────────────────────────────────────────────────

class TestRegistration:
    def test_register_all(self):
        hub = ChannelHub()
        hub.register_feishu(app_id="x", app_secret="y")
        hub.register_telegram(bot_token="123:abc")
        hub.register_wecom(corp_id="ww", corp_secret="s")
        hub.register_qq(app_id="1", client_secret="s")
        assert set(hub.channels) == {"feishu", "telegram", "wecom", "qq"}

    def test_client_accessor(self):
        hub = ChannelHub()
        hub.register_telegram(bot_token="123:abc")
        assert hub.client("telegram") is not None
        assert hub.client("nonexistent") is None

    def test_chained_registration(self):
        hub = (ChannelHub()
               .register_feishu(app_id="x", app_secret="y")
               .register_telegram(bot_token="t"))
        assert len(hub.channels) == 2


# ── 飞书闭环 ─────────────────────────────────────────────────────

class TestFeishuFlow:
    async def test_url_verification(self):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_feishu(app_id="x", app_secret="y")
        body = json.dumps({"type": "url_verification", "challenge": "ch1"}).encode()
        result = await hub.handle_feishu_event(body)
        assert result["challenge"] == "ch1"

    async def test_message_runs_agent_and_replies(self, monkeypatch):
        agent = _FakeAgent("已处理")
        hub = ChannelHub(agent=agent)
        hub.register_feishu(app_id="x", app_secret="y")
        # mock client.reply 捕获回复
        replies = []
        client = hub.client("feishu")
        class _R: success = True
        monkeypatch.setattr(client, "reply", lambda mid, text: replies.append((mid, text)) or _R())
        body = json.dumps({
            "schema": "2.0", "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_1"}, "sender_type": "user"},
                "message": {"message_id": "om_1", "chat_id": "oc_1",
                            "message_type": "text", "content": json.dumps({"text": "审查代码"})},
            },
        }).encode()
        result = await hub.handle_feishu_event(body)
        assert result["code"] == 0
        assert len(replies) == 1
        assert "审查代码" in replies[0][1]  # agent 处理了原文
        assert agent.calls == ["审查代码"]
        assert hub.metrics()["replied"] == 1

    async def test_not_registered(self):
        hub = ChannelHub()
        result = await hub.handle_feishu_event(b"{}")
        assert "error" in result


# ── Telegram 闭环 ────────────────────────────────────────────────

class TestTelegramFlow:
    async def test_poll_runs_agent_and_replies(self, monkeypatch):
        agent = _FakeAgent("回复")
        hub = ChannelHub(agent=agent)
        hub.register_telegram(bot_token="123:abc")
        client = hub.client("telegram")
        # mock get_updates 返回一条消息, send_message 捕获
        from channels.telegram_client import TelegramResult
        monkeypatch.setattr(client, "get_updates",
                            lambda timeout=25: TelegramResult(success=True, data=[{
                                "update_id": 1,
                                "message": {"message_id": 9, "text": "翻译",
                                            "chat": {"id": 555}, "from": {"id": 7, "username": "u"}},
                            }]))
        sent = []
        class _R: success = True
        monkeypatch.setattr(client, "send_message",
                            lambda cid, text, **kw: sent.append((cid, text)) or _R())
        count = await hub.poll_telegram_once()
        assert count == 1
        assert sent[0][0] == 555
        assert "翻译" in sent[0][1]

    async def test_webhook_update(self, monkeypatch):
        agent = _FakeAgent()
        hub = ChannelHub(agent=agent)
        hub.register_telegram(bot_token="123:abc")
        client = hub.client("telegram")
        sent = []
        class _R: success = True
        monkeypatch.setattr(client, "send_message",
                            lambda cid, text, **kw: sent.append((cid, text)) or _R())
        body = {"update_id": 1, "message": {"message_id": 2, "text": "hi",
                "chat": {"id": 99}, "from": {"id": 1, "username": "a"}}}
        result = await hub.handle_telegram_webhook(body)
        assert result["ok"]
        assert len(sent) == 1


# ── QQ 闭环 ──────────────────────────────────────────────────────

class TestQQFlow:
    async def test_channel_message(self, monkeypatch):
        agent = _FakeAgent()
        hub = ChannelHub(agent=agent)
        hub.register_qq(app_id="1", client_secret="s")
        client = hub.client("qq")
        sent = []
        from channels.qq_client import QQResult
        monkeypatch.setattr(client, "send_channel_message",
                            lambda cid, text, msg_id=None: sent.append((cid, text)) or QQResult(success=True))
        result = await hub.handle_qq_message("channel", "chan_1", "你好", msg_id="m1")
        assert result["code"] == 0
        assert sent[0][0] == "chan_1"


# ── 主动推送 ─────────────────────────────────────────────────────

class TestPush:
    def test_push_telegram(self, monkeypatch):
        hub = ChannelHub()
        hub.register_telegram(bot_token="123:abc")
        client = hub.client("telegram")
        sent = []
        class _R: success = True
        monkeypatch.setattr(client, "send_message",
                            lambda cid, text, **kw: sent.append((cid, text)) or _R())
        hub.push("telegram", "555", "主动通知")
        assert sent[0][1] == "主动通知"

    def test_push_unregistered_channel(self):
        hub = ChannelHub()
        result = hub.push("feishu", "x", "hi")
        assert not result.success

    def test_metrics(self):
        hub = ChannelHub(agent=_FakeAgent())
        m = hub.metrics()
        assert set(m.keys()) == {"received", "handled", "replied", "errors"}

    def test_repr(self):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_telegram(bot_token="t")
        assert "telegram" in repr(hub)
