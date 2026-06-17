"""
渠道客户端测试 (Telegram / 企业微信 / QQ) + audio_transcribe / Channel + audio tests.

mock httpx, $0, 无网络。覆盖 token、发消息、消息解析、加签/验签、降级。
真实联调需各平台凭证 (见各 client docstring)。
"""
import json

import pytest

from channels.telegram_client import TelegramClient, TelegramMessage
from channels.wecom_client import WeComWebhookBot, WeComAppClient
from channels.qq_client import QQBotClient


class _MockResp:
    def __init__(self, payload, content=b"x"):
        self._p = payload
        self.content = content
    def raise_for_status(self): pass
    def json(self): return self._p


class _MockClient:
    def __init__(self, payload, capture=None):
        self._payload = payload
        self._capture = capture
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def post(self, url, json=None, params=None, headers=None):
        if self._capture is not None:
            self._capture.append({"url": url, "json": json, "params": params, "headers": headers})
        return _MockResp(self._payload)
    def get(self, url, params=None, headers=None):
        if self._capture is not None:
            self._capture.append({"url": url, "params": params})
        return _MockResp(self._payload)


# ── Telegram ─────────────────────────────────────────────────────

class TestTelegram:
    def test_get_me(self, monkeypatch):
        import channels.telegram_client as tc
        monkeypatch.setattr(tc.httpx, "Client",
                            lambda *a, **k: _MockClient({"ok": True, "result": {"username": "mybot"}}))
        client = TelegramClient(bot_token="123:ABC")
        r = client.get_me()
        assert r.success
        assert r.data["username"] == "mybot"

    def test_send_message(self, monkeypatch):
        import channels.telegram_client as tc
        capture = []
        monkeypatch.setattr(tc.httpx, "Client",
                            lambda *a, **k: _MockClient({"ok": True, "result": {"message_id": 5}}, capture))
        client = TelegramClient(bot_token="123:ABC")
        r = client.send_message(chat_id=999, text="你好", parse_mode="Markdown")
        assert r.success
        assert capture[0]["json"]["chat_id"] == 999
        assert capture[0]["json"]["text"] == "你好"
        assert capture[0]["json"]["parse_mode"] == "Markdown"

    def test_api_error(self, monkeypatch):
        import channels.telegram_client as tc
        monkeypatch.setattr(tc.httpx, "Client",
                            lambda *a, **k: _MockClient({"ok": False, "description": "chat not found"}))
        client = TelegramClient(bot_token="123:ABC")
        r = client.send_message(chat_id=1, text="x")
        assert not r.success
        assert "chat not found" in r.error

    def test_no_token(self, monkeypatch):
        monkeypatch.delenv("NONULL_TELEGRAM_BOT_TOKEN", raising=False)
        client = TelegramClient()
        r = client.get_me()
        assert not r.success
        assert "未配置" in r.error

    def test_parse_updates(self):
        client = TelegramClient(bot_token="123:ABC")
        updates = [{
            "update_id": 100,
            "message": {"message_id": 7, "text": "审查代码",
                        "chat": {"id": 555}, "from": {"id": 888, "username": "alice"}},
        }, {
            "update_id": 101,  # 非文本消息应跳过
            "message": {"message_id": 8, "photo": [], "chat": {"id": 555}, "from": {"id": 888}},
        }]
        msgs = client.parse_updates(updates)
        assert len(msgs) == 1
        assert msgs[0].text == "审查代码"
        assert msgs[0].chat_id == 555
        assert msgs[0].username == "alice"

    def test_get_updates_tracks_offset(self, monkeypatch):
        import channels.telegram_client as tc
        monkeypatch.setattr(tc.httpx, "Client",
                            lambda *a, **k: _MockClient({"ok": True, "result": [{"update_id": 50}]}))
        client = TelegramClient(bot_token="123:ABC")
        client.get_updates()
        assert client._last_update_id == 50

    def test_webhook_update_parse(self):
        client = TelegramClient(bot_token="123:ABC")
        body = {"update_id": 1, "message": {"message_id": 1, "text": "hi",
                "chat": {"id": 1}, "from": {"id": 2, "username": "bob"}}}
        msg = client.parse_webhook_update(body)
        assert msg.text == "hi"


# ── 企业微信 / WeCom ─────────────────────────────────────────────

class TestWeComWebhook:
    def test_send_text(self, monkeypatch):
        import channels.wecom_client as wc
        capture = []
        monkeypatch.setattr(wc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 0, "errmsg": "ok"}, capture))
        bot = WeComWebhookBot(webhook="https://qyapi.weixin.qq.com/webhook/send?key=x")
        r = bot.send_text("你好", mentioned_list=["@all"])
        assert r.success
        assert capture[0]["json"]["msgtype"] == "text"
        assert capture[0]["json"]["text"]["mentioned_list"] == ["@all"]

    def test_send_markdown(self, monkeypatch):
        import channels.wecom_client as wc
        capture = []
        monkeypatch.setattr(wc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 0}, capture))
        bot = WeComWebhookBot(webhook="https://x.com/send?key=x")
        bot.send_markdown("## 标题")
        assert capture[0]["json"]["msgtype"] == "markdown"

    def test_error(self, monkeypatch):
        import channels.wecom_client as wc
        monkeypatch.setattr(wc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 93000, "errmsg": "invalid webhook"}))
        bot = WeComWebhookBot(webhook="https://x.com/send?key=x")
        r = bot.send_text("hi")
        assert not r.success
        assert r.code == 93000

    def test_no_webhook(self, monkeypatch):
        monkeypatch.delenv("NONULL_WECOM_WEBHOOK", raising=False)
        bot = WeComWebhookBot()
        r = bot.send_text("hi")
        assert not r.success
        assert "未配置" in r.error


class TestWeComApp:
    def test_get_token(self, monkeypatch):
        import channels.wecom_client as wc
        monkeypatch.setattr(wc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 0, "access_token": "wt", "expires_in": 7200}))
        app = WeComAppClient(corp_id="ww1", corp_secret="s", agent_id=1000002)
        assert app.get_access_token() == "wt"

    def test_token_cached(self, monkeypatch):
        import channels.wecom_client as wc
        calls = []
        def mk(*a, **k):
            calls.append(1)
            return _MockClient({"errcode": 0, "access_token": "t", "expires_in": 7200})
        monkeypatch.setattr(wc.httpx, "Client", mk)
        app = WeComAppClient(corp_id="ww1", corp_secret="s")
        app.get_access_token(); app.get_access_token()
        assert len(calls) == 1

    def test_no_credentials(self, monkeypatch):
        monkeypatch.delenv("NONULL_WECOM_CORP_ID", raising=False)
        monkeypatch.delenv("NONULL_WECOM_CORP_SECRET", raising=False)
        app = WeComAppClient()
        with pytest.raises(RuntimeError, match="未配置"):
            app.get_access_token()

    def test_send_text(self, monkeypatch):
        import channels.wecom_client as wc
        app = WeComAppClient(corp_id="ww1", corp_secret="s", agent_id=42)
        app._token = "cached"; app._token_expire_at = 9_999_999_999
        capture = []
        monkeypatch.setattr(wc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 0}, capture))
        r = app.send_text("@all", "通知")
        assert r.success
        assert capture[0]["json"]["agentid"] == 42
        assert capture[0]["json"]["text"]["content"] == "通知"


# ── QQ 官方机器人 ────────────────────────────────────────────────

class TestQQBot:
    def test_get_token(self, monkeypatch):
        import channels.qq_client as qc
        monkeypatch.setattr(qc.httpx, "Client",
                            lambda *a, **k: _MockClient({"access_token": "qt", "expires_in": 7200}))
        client = QQBotClient(app_id="123", client_secret="s")
        assert client.get_access_token() == "qt"

    def test_token_cached(self, monkeypatch):
        import channels.qq_client as qc
        calls = []
        def mk(*a, **k):
            calls.append(1)
            return _MockClient({"access_token": "t", "expires_in": 7200})
        monkeypatch.setattr(qc.httpx, "Client", mk)
        client = QQBotClient(app_id="123", client_secret="s")
        client.get_access_token(); client.get_access_token()
        assert len(calls) == 1

    def test_no_credentials(self, monkeypatch):
        monkeypatch.delenv("NONULL_QQ_APP_ID", raising=False)
        monkeypatch.delenv("NONULL_QQ_CLIENT_SECRET", raising=False)
        client = QQBotClient()
        with pytest.raises(RuntimeError, match="未配置"):
            client.get_access_token()

    def test_send_channel_message(self, monkeypatch):
        import channels.qq_client as qc
        client = QQBotClient(app_id="123", client_secret="s")
        client._access_token = "cached"; client._token_expire_at = 9_999_999_999
        capture = []
        monkeypatch.setattr(qc.httpx, "Client",
                            lambda *a, **k: _MockClient({"id": "msg_1"}, capture))
        r = client.send_channel_message("chan_x", "你好", msg_id="recv_1")
        assert r.success
        assert capture[0]["json"]["content"] == "你好"
        assert capture[0]["json"]["msg_id"] == "recv_1"  # 被动回复

    def test_send_group_message(self, monkeypatch):
        import channels.qq_client as qc
        client = QQBotClient(app_id="123", client_secret="s")
        client._access_token = "c"; client._token_expire_at = 9_999_999_999
        capture = []
        monkeypatch.setattr(qc.httpx, "Client",
                            lambda *a, **k: _MockClient({"id": "m"}, capture))
        r = client.reply_group_message("grp_x", "recv_2", "收到")
        assert r.success
        assert capture[0]["json"]["msg_type"] == 0
        assert capture[0]["json"]["msg_id"] == "recv_2"

    def test_api_error(self, monkeypatch):
        import channels.qq_client as qc
        client = QQBotClient(app_id="123", client_secret="s")
        client._access_token = "c"; client._token_expire_at = 9_999_999_999
        monkeypatch.setattr(qc.httpx, "Client",
                            lambda *a, **k: _MockClient({"code": 11253, "message": "invalid msg_id"}))
        r = client.send_channel_message("c", "x", msg_id="bad")
        assert not r.success
        assert r.code == 11253


# ── audio_transcribe 降级 ────────────────────────────────────────

class TestAudioTranscribe:
    def test_file_not_found(self):
        from skills.multimodal.audio_skills import AudioTranscribeStubSkill
        skill = AudioTranscribeStubSkill()
        skill.activate()
        r = skill.execute({"path": "/nonexistent/audio.wav"})
        assert r.success  # skill 本身成功执行 (返回结构化错误)
        assert "not found" in r.data["error"].lower()

    def test_no_backend_graceful(self, monkeypatch, tmp_path):
        """无 whisper 库 + 无 key → 优雅降级 (明确提示, 不假转写)。"""
        from skills.multimodal.audio_skills import AudioTranscribeStubSkill
        # 造一个真实存在的空文件
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"RIFF....WAVE")
        monkeypatch.delenv("NONULL_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # 强制 whisper import 失败
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *a, **k):
            if name == "whisper":
                raise ImportError("no whisper")
            return real_import(name, *a, **k)
        monkeypatch.setattr(builtins, "__import__", fake_import)
        skill = AudioTranscribeStubSkill()
        skill.activate()
        r = skill.execute({"path": str(audio)})
        assert r.success
        assert r.data["transcript"] == ""
        assert "no ASR backend" in r.data["error"]
        assert "hint" in r.data  # 给出启用方法

    def test_metadata_not_stub(self):
        from skills.multimodal.audio_skills import AudioTranscribeStubSkill
        meta = AudioTranscribeStubSkill().metadata
        assert "DEMO STUB" not in meta.description
        assert meta.version == "0.2.0"
