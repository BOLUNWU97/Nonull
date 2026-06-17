"""
渠道 webhook 服务测试 / Tests for the FastAPI webhook server.

用 FastAPI TestClient 打真实路由 (无真实平台 API, FakeAgent + mock client),
验证 health / 飞书 challenge / Telegram webhook / QQ op=13 URL 验证 + 普通消息。
"""
import json

import pytest

fastapi = pytest.importorskip("fastapi", reason="webhook 服务需 fastapi")
from fastapi.testclient import TestClient

from channels.channel_hub import ChannelHub
from channels.webhook_server import build_app


class _FakeAgent:
    async def run(self, task):
        return {"output": f"agent: {task}"}


def _client(hub):
    return TestClient(build_app(hub))


class TestHealth:
    def test_health(self):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_telegram(bot_token="123:abc")
        c = _client(hub)
        r = c.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "telegram" in data["channels"]
        assert "metrics" in data


class TestFeishuRoute:
    def test_url_challenge(self):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_feishu(app_id="x", app_secret="y")
        c = _client(hub)
        r = c.post("/feishu/event",
                   json={"type": "url_verification", "challenge": "ch_abc"})
        assert r.status_code == 200
        assert r.json()["challenge"] == "ch_abc"

    def test_message_event(self, monkeypatch):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_feishu(app_id="x", app_secret="y")
        client = hub.client("feishu")
        replies = []
        class _R: success = True
        monkeypatch.setattr(client, "reply",
                            lambda mid, text: replies.append(text) or _R())
        c = _client(hub)
        event = {
            "schema": "2.0", "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou"}, "sender_type": "user"},
                "message": {"message_id": "om", "chat_id": "oc",
                            "message_type": "text", "content": json.dumps({"text": "hello"})},
            },
        }
        r = c.post("/feishu/event", json=event)
        assert r.status_code == 200
        assert r.json()["code"] == 0
        assert len(replies) == 1
        assert "hello" in replies[0]


class TestTelegramRoute:
    def test_webhook(self, monkeypatch):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_telegram(bot_token="123:abc")
        client = hub.client("telegram")
        sent = []
        class _R: success = True
        monkeypatch.setattr(client, "send_message",
                            lambda cid, text, **kw: sent.append((cid, text)) or _R())
        c = _client(hub)
        update = {"update_id": 1, "message": {"message_id": 2, "text": "hi",
                  "chat": {"id": 77}, "from": {"id": 1, "username": "u"}}}
        r = c.post("/telegram/webhook", json=update)
        assert r.status_code == 200
        assert r.json()["ok"]
        assert sent[0][0] == 77


class TestQQRoute:
    def test_url_verification_op13(self, monkeypatch):
        """QQ op=13 URL 验证: 用私钥签名 plain_token 返回。"""
        pytest.importorskip("cryptography")
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_qq(app_id="1", client_secret="mysecret")
        c = _client(hub)
        r = c.post("/qq/webhook", json={
            "op": 13, "d": {"plain_token": "ptk", "event_ts": "1700000000"}})
        assert r.status_code == 200
        data = r.json()
        assert data["plain_token"] == "ptk"
        assert len(data["signature"]) == 128  # Ed25519 hex

    def test_group_message(self, monkeypatch):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_qq(app_id="1", client_secret="s")
        client = hub.client("qq")
        from channels.qq_client import QQResult
        sent = []
        monkeypatch.setattr(client, "reply_group_message",
                            lambda gid, mid, text, **kw: sent.append((gid, text)) or QQResult(success=True))
        c = _client(hub)
        r = c.post("/qq/webhook", json={
            "op": 0, "t": "GROUP_AT_MESSAGE_CREATE",
            "d": {"group_openid": "grp1", "content": "你好", "id": "m1"}})
        assert r.status_code == 200
        assert sent[0][0] == "grp1"

    def test_invalid_json(self):
        hub = ChannelHub(agent=_FakeAgent())
        hub.register_qq(app_id="1", client_secret="s")
        c = _client(hub)
        r = c.post("/qq/webhook", content=b"not json{{{")
        assert r.status_code == 200
        assert r.json()["code"] == -1


class TestServerBuild:
    def test_build_app_returns_app(self):
        hub = ChannelHub(agent=_FakeAgent())
        app = build_app(hub)
        assert app is not None
        # 路由都注册了
        paths = {r.path for r in app.routes}
        assert "/feishu/event" in paths
        assert "/telegram/webhook" in paths
        assert "/qq/webhook" in paths
        assert "/health" in paths
