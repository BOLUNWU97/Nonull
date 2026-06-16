"""
钉钉客户端测试 / Tests for the real DingTalk client.

mock httpx, $0, 无网络。重点验证加签 (HMAC-SHA256)、发消息、access_token、
回调验签 (SHA1) 与 AES 解密。真实联调需配 NONULL_DINGTALK_WEBHOOK/SECRET 等。
"""
import base64
import hashlib
import hmac
import json

import pytest

from channels.dingtalk_client import (
    DingTalkWebhookBot, DingTalkAppClient, DingTalkCrypto, DingResult,
)


class _MockResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


class _MockClient:
    def __init__(self, payload, capture=None):
        self._payload = payload
        self._capture = capture
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def post(self, url, json=None, headers=None, params=None):
        if self._capture is not None:
            self._capture.append({"url": url, "json": json, "headers": headers})
        return _MockResp(self._payload)


# ── 自定义机器人 webhook + 加签 ──────────────────────────────────

class TestWebhookBot:
    def test_sign_appends_timestamp_and_sign(self):
        """加签 URL 含 timestamp + sign 参数。"""
        bot = DingTalkWebhookBot(webhook="https://oapi.dingtalk.com/robot/send?access_token=abc",
                                 secret="SECtest")
        url = bot._signed_url()
        assert "timestamp=" in url
        assert "sign=" in url
        assert "access_token=abc" in url

    def test_sign_correctness(self):
        """加签算法正确: base64(hmac_sha256(secret, ts\\nsecret))。"""
        secret = "SECmysecret"
        bot = DingTalkWebhookBot(webhook="https://x.com/send", secret=secret)
        url = bot._signed_url()
        # 解出 url 里的 timestamp 和 sign, 重新算一遍核对
        import urllib.parse as up
        qs = up.parse_qs(up.urlparse(url).query)
        ts = qs["timestamp"][0]
        sign_in_url = qs["sign"][0]  # parse_qs 已解码 → 原始 base64
        string_to_sign = f"{ts}\n{secret}"
        h = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256)
        expected = base64.b64encode(h.digest()).decode()  # 原始 base64 (不再 quote_plus)
        assert sign_in_url == expected

    def test_no_secret_no_sign(self):
        """无 secret 时不加签 (URL 不变)。"""
        bot = DingTalkWebhookBot(webhook="https://x.com/send")
        assert bot._signed_url() == "https://x.com/send"

    def test_send_text_success(self, monkeypatch):
        import channels.dingtalk_client as dc
        capture = []
        monkeypatch.setattr(dc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 0, "errmsg": "ok"}, capture))
        bot = DingTalkWebhookBot(webhook="https://x.com/send", secret="s")
        result = bot.send_text("你好世界")
        assert result.success
        assert capture[0]["json"]["msgtype"] == "text"
        assert capture[0]["json"]["text"]["content"] == "你好世界"

    def test_send_text_at_all(self, monkeypatch):
        import channels.dingtalk_client as dc
        capture = []
        monkeypatch.setattr(dc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 0}, capture))
        bot = DingTalkWebhookBot(webhook="https://x.com/send")
        bot.send_text("通知", at_all=True)
        assert capture[0]["json"]["at"]["isAtAll"] is True

    def test_send_markdown(self, monkeypatch):
        import channels.dingtalk_client as dc
        capture = []
        monkeypatch.setattr(dc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 0}, capture))
        bot = DingTalkWebhookBot(webhook="https://x.com/send")
        bot.send_markdown("标题", "## 内容")
        assert capture[0]["json"]["msgtype"] == "markdown"
        assert capture[0]["json"]["markdown"]["title"] == "标题"

    def test_send_error(self, monkeypatch):
        import channels.dingtalk_client as dc
        monkeypatch.setattr(dc.httpx, "Client",
                            lambda *a, **k: _MockClient({"errcode": 310000, "errmsg": "sign not match"}))
        bot = DingTalkWebhookBot(webhook="https://x.com/send", secret="s")
        result = bot.send_text("hi")
        assert not result.success
        assert result.code == 310000
        assert "sign not match" in result.error

    def test_no_webhook_configured(self, monkeypatch):
        monkeypatch.delenv("NONULL_DINGTALK_WEBHOOK", raising=False)
        bot = DingTalkWebhookBot()
        result = bot.send_text("hi")
        assert not result.success
        assert "未配置" in result.error

    def test_network_error(self, monkeypatch):
        import channels.dingtalk_client as dc
        class _Boom:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def post(self, *a, **k): raise dc.httpx.ConnectError("no net")
        monkeypatch.setattr(dc.httpx, "Client", lambda *a, **k: _Boom())
        bot = DingTalkWebhookBot(webhook="https://x.com/send")
        result = bot.send_text("hi")
        assert not result.success
        assert "ConnectError" in result.error


# ── 企业应用 access_token ────────────────────────────────────────

class TestAppClient:
    def test_get_token(self, monkeypatch):
        import channels.dingtalk_client as dc
        monkeypatch.setattr(dc.httpx, "Client",
                            lambda *a, **k: _MockClient({"accessToken": "tok-123", "expireIn": 7200}))
        app = DingTalkAppClient(app_key="ding_x", app_secret="sec")
        assert app.get_access_token() == "tok-123"

    def test_token_cached(self, monkeypatch):
        import channels.dingtalk_client as dc
        calls = []
        def mk(*a, **k):
            calls.append(1)
            return _MockClient({"accessToken": "t", "expireIn": 7200})
        monkeypatch.setattr(dc.httpx, "Client", mk)
        app = DingTalkAppClient(app_key="x", app_secret="y")
        app.get_access_token()
        app.get_access_token()
        assert len(calls) == 1

    def test_no_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("NONULL_DINGTALK_APP_KEY", raising=False)
        monkeypatch.delenv("NONULL_DINGTALK_APP_SECRET", raising=False)
        app = DingTalkAppClient()
        with pytest.raises(RuntimeError, match="未配置"):
            app.get_access_token()

    def test_send_to_robot(self, monkeypatch):
        import channels.dingtalk_client as dc
        app = DingTalkAppClient(app_key="x", app_secret="y")
        app._token = "cached"; app._token_expire_at = 9_999_999_999
        capture = []
        monkeypatch.setattr(dc.httpx, "Client",
                            lambda *a, **k: _MockClient({"processQueryKey": "pqk-1"}, capture))
        result = app.send_to_robot("robot_x", ["user1"], "你好")
        assert result.success
        assert capture[0]["json"]["robotCode"] == "robot_x"
        assert "你好" in capture[0]["json"]["msgParam"]


# ── 回调验签 + AES 解密 ──────────────────────────────────────────

class TestCrypto:
    def test_verify_signature(self):
        """SHA1 验签: sorted(token,ts,nonce,encrypt) 拼接。"""
        crypto = DingTalkCrypto(token="mytoken", aes_key="a" * 43, corp_id="corp")
        ts, nonce, encrypt = "1700000000", "nonce123", "ENCRYPTED"
        params = sorted(["mytoken", ts, nonce, encrypt])
        expected = hashlib.sha1("".join(params).encode()).hexdigest()
        assert crypto.verify_signature(ts, nonce, encrypt, expected) is True
        assert crypto.verify_signature(ts, nonce, encrypt, "wrong") is False

    def test_aes_decrypt_roundtrip(self):
        """AES 解密往返 (构造钉钉格式密文 → 解密)。"""
        crypto_cryptography = pytest.importorskip("cryptography")
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        import os as _os

        aes_key_b64 = base64.b64encode(_os.urandom(32)).decode()[:43]
        crypto = DingTalkCrypto(token="t", aes_key=aes_key_b64)
        key = crypto._key

        # 构造钉钉密文: random16 + len(4,big) + msg + corp_id, PKCS7 填充
        msg = '{"EventType":"chat_bot_message","text":{"content":"hi"}}'
        msg_bytes = msg.encode("utf-8")
        content = _os.urandom(16) + len(msg_bytes).to_bytes(4, "big") + msg_bytes + b"corpid"
        pad_len = 16 - (len(content) % 16)
        content += bytes([pad_len]) * pad_len
        iv = key[:16]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        enc = cipher.encryptor()
        ct = enc.update(content) + enc.finalize()
        encrypt_b64 = base64.b64encode(ct).decode()

        decrypted = crypto.decrypt(encrypt_b64)
        assert decrypted == msg
