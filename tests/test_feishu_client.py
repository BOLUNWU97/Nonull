"""
飞书客户端测试 / Tests for the real Feishu client.

不依赖真实飞书服务 (mock httpx): 测 token 获取/缓存、发消息、事件回调
(challenge 验证 + AES 解密往返 + 签名验证 + 消息事件解析)。$0, 无网络。
真实联调需配 NONULL_FEISHU_APP_ID/APP_SECRET (见 examples/feishu_bot_demo.py)。
"""
import base64
import hashlib
import json

import pytest

from channels.feishu_client import (
    FeishuClient, FeishuCrypto, FeishuMessage, FeishuResult,
)


# ── 加密往返 (验证解密逻辑正确) ──────────────────────────────────

def _aes_encrypt(plaintext: str, encrypt_key: str) -> str:
    """构造飞书格式的加密密文 (用于测试解密往返)。需要 cryptography。"""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import os as _os
    key = hashlib.sha256(encrypt_key.encode()).digest()
    iv = _os.urandom(16)
    data = plaintext.encode("utf-8")
    pad_len = 16 - (len(data) % 16)
    data += bytes([pad_len]) * pad_len  # PKCS7
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor()
    ct = enc.update(data) + enc.finalize()
    return base64.b64encode(iv + ct).decode()


cryptography = pytest.importorskip("cryptography", reason="飞书解密需 cryptography")


class TestFeishuCrypto:
    def test_decrypt_roundtrip(self):
        """加密 → 解密 往返一致 (验证 AES-256-CBC + PKCS7 正确)。"""
        key = "test_encrypt_key_12345"
        crypto = FeishuCrypto(key)
        original = '{"type":"event","event":{"hello":"世界"}}'
        encrypted = _aes_encrypt(original, key)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_verify_signature(self):
        """签名验证: sha256(timestamp+nonce+key+body)。"""
        key = "mykey"
        crypto = FeishuCrypto(key)
        ts, nonce, body = "1700000000", "abc123", b'{"x":1}'
        sig = hashlib.sha256((ts + nonce + key).encode() + body).hexdigest()
        assert crypto.verify_signature(ts, nonce, body, sig) is True
        assert crypto.verify_signature(ts, nonce, body, "wrong") is False

    def test_decrypt_rejects_bad_padding(self):
        """P0 修复: 非法 PKCS7 填充被拒绝 (攻击者构造密文不会静默返回错误数据)。"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        import os as _os
        key_str = "k"
        crypto = FeishuCrypto(key_str)
        key = hashlib.sha256(key_str.encode()).digest()
        iv = _os.urandom(16)
        # 构造填充字节错误的明文: 末字节 pad_len=5, 但前面 5 字节不全是 5
        # (块必须是 16 倍数; 这里用 32 字节, 末尾 b"\x01\x02\x03\x04\x05" → pad_len=5 但 padding[-5:] != 5*5)
        bad = b"hello world data" + b"abcdefghijk" + bytes([1, 2, 3, 4, 5])  # 16+11+5 = 32
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        enc = cipher.encryptor()
        ct = enc.update(bad) + enc.finalize()
        import base64 as _b64
        with pytest.raises(ValueError, match="PKCS7"):
            crypto.decrypt(_b64.b64encode(iv + ct).decode())


# ── token 获取/缓存 (mock httpx) ─────────────────────────────────

class _MockResp:
    def __init__(self, payload):
        self._p = payload
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


class TestTokenManagement:
    def test_get_token_success(self, monkeypatch):
        import channels.feishu_client as fc
        monkeypatch.setattr(fc.httpx, "Client",
                            lambda *a, **k: _MockClient({"code": 0, "tenant_access_token": "t-abc", "expire": 7200}))
        client = FeishuClient(app_id="cli_x", app_secret="sec")
        token = client.get_tenant_access_token()
        assert token == "t-abc"

    def test_token_cached(self, monkeypatch):
        """第二次调用用缓存, 不再请求。"""
        import channels.feishu_client as fc
        calls = []
        def mk(*a, **k):
            calls.append(1)
            return _MockClient({"code": 0, "tenant_access_token": "t1", "expire": 7200})
        monkeypatch.setattr(fc.httpx, "Client", mk)
        client = FeishuClient(app_id="cli_x", app_secret="sec")
        client.get_tenant_access_token()
        client.get_tenant_access_token()  # 应命中缓存
        assert len(calls) == 1

    def test_token_error_raises(self, monkeypatch):
        import channels.feishu_client as fc
        monkeypatch.setattr(fc.httpx, "Client",
                            lambda *a, **k: _MockClient({"code": 99991663, "msg": "app not found"}))
        client = FeishuClient(app_id="bad", app_secret="bad")
        with pytest.raises(RuntimeError, match="获取 token 失败"):
            client.get_tenant_access_token()

    def test_no_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("NONULL_FEISHU_APP_ID", raising=False)
        monkeypatch.delenv("NONULL_FEISHU_APP_SECRET", raising=False)
        client = FeishuClient()
        with pytest.raises(RuntimeError, match="未配置"):
            client.get_tenant_access_token()

    def test_expired_token_refreshes(self, monkeypatch):
        """token 临近过期 → 重新请求 (不用过期缓存)。"""
        import channels.feishu_client as fc
        calls = []
        def mk(*a, **k):
            calls.append(1)
            return _MockClient({"code": 0, "tenant_access_token": f"t{len(calls)}", "expire": 7200})
        monkeypatch.setattr(fc.httpx, "Client", mk)
        client = FeishuClient(app_id="x", app_secret="y")
        client._token = "old-token"
        client._token_expire_at = 100.0  # 已过期 (远早于 now)
        token = client.get_tenant_access_token()
        assert token == "t1"  # 重新请求了, 不是 old-token
        assert len(calls) == 1

    def test_force_refresh(self, monkeypatch):
        """force=True 强制刷新, 即便缓存有效。"""
        import channels.feishu_client as fc
        calls = []
        def mk(*a, **k):
            calls.append(1)
            return _MockClient({"code": 0, "tenant_access_token": "fresh", "expire": 7200})
        monkeypatch.setattr(fc.httpx, "Client", mk)
        client = FeishuClient(app_id="x", app_secret="y")
        client._token = "valid"; client._token_expire_at = 9_999_999_999
        token = client.get_tenant_access_token(force=True)
        assert token == "fresh"
        assert len(calls) == 1


# ── 发消息 (mock httpx) ──────────────────────────────────────────

class TestSendMessage:
    def _client_with_token(self, monkeypatch, send_payload, capture=None):
        import channels.feishu_client as fc
        # token 请求和发消息请求都走同一 mock; token 先被缓存
        client = FeishuClient(app_id="cli_x", app_secret="sec")
        client._token = "cached-token"
        client._token_expire_at = 9_999_999_999  # 远期, 用缓存
        monkeypatch.setattr(fc.httpx, "Client",
                            lambda *a, **k: _MockClient(send_payload, capture))
        return client

    def test_send_text_success(self, monkeypatch):
        capture = []
        client = self._client_with_token(
            monkeypatch, {"code": 0, "data": {"message_id": "om_x"}}, capture)
        result = client.send_text("ou_user", "你好世界")
        assert result.success
        assert result.data["message_id"] == "om_x"
        # 验证请求体: msg_type=text, content 含文本
        sent = capture[0]["json"]
        assert sent["msg_type"] == "text"
        assert "你好世界" in sent["content"]
        assert capture[0]["params"]["receive_id_type"] == "open_id"

    def test_send_text_api_error(self, monkeypatch):
        client = self._client_with_token(
            monkeypatch, {"code": 230001, "msg": "invalid receive_id"})
        result = client.send_text("bad_id", "hi")
        assert not result.success
        assert result.code == 230001
        assert "invalid receive_id" in result.error

    def test_send_card(self, monkeypatch):
        capture = []
        client = self._client_with_token(
            monkeypatch, {"code": 0, "data": {}}, capture)
        card = {"config": {"wide_screen_mode": True}, "elements": []}
        result = client.send_card("oc_chat", card, receive_id_type="chat_id")
        assert result.success
        assert capture[0]["json"]["msg_type"] == "interactive"

    def test_send_post(self, monkeypatch):
        """发富文本 post 消息。"""
        capture = []
        client = self._client_with_token(
            monkeypatch, {"code": 0, "data": {"message_id": "om_p"}}, capture)
        post = {"zh_cn": {"title": "标题", "content": [[{"tag": "text", "text": "正文"}]]}}
        result = client.send_post("ou_user", post)
        assert result.success
        assert capture[0]["json"]["msg_type"] == "post"
        assert "标题" in capture[0]["json"]["content"]

    def test_reply_message(self, monkeypatch):
        """回复指定消息。"""
        capture = []
        client = self._client_with_token(
            monkeypatch, {"code": 0, "data": {"message_id": "om_r"}}, capture)
        result = client.reply("om_original", "这是回复")
        assert result.success
        assert "om_original" in capture[0]["url"]
        assert "这是回复" in capture[0]["json"]["content"]

    def test_send_network_error(self, monkeypatch):
        import channels.feishu_client as fc
        client = FeishuClient(app_id="x", app_secret="y")
        client._token = "t"; client._token_expire_at = 9_999_999_999
        class _Boom:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def post(self, *a, **k): raise fc.httpx.ConnectError("no net")
        monkeypatch.setattr(fc.httpx, "Client", lambda *a, **k: _Boom())
        result = client.send_text("ou_x", "hi")
        assert not result.success
        assert "ConnectError" in result.error


# ── 事件回调 / Event callback ────────────────────────────────────

class TestEventCallback:
    def test_url_verification_plaintext(self):
        """明文 URL 验证 → 返回 challenge。"""
        client = FeishuClient(app_id="x", app_secret="y")
        body = json.dumps({"type": "url_verification", "challenge": "ch-123",
                           "token": "vt"}).encode()
        result = client.handle_event(body)
        assert result["challenge"] == "ch-123"

    def test_url_verification_token_mismatch(self):
        client = FeishuClient(app_id="x", app_secret="y", verification_token="correct")
        body = json.dumps({"type": "url_verification", "challenge": "ch",
                           "token": "wrong"}).encode()
        result = client.handle_event(body)
        assert result["type"] == "error"

    def test_encrypted_event_decryption(self):
        """加密事件 → 解密 → 解析。"""
        key = "evt_encrypt_key"
        client = FeishuClient(app_id="x", app_secret="y", encrypt_key=key)
        inner = {"type": "url_verification", "challenge": "secret-challenge"}
        encrypted = _aes_encrypt(json.dumps(inner), key)
        body = json.dumps({"encrypt": encrypted}).encode()
        result = client.handle_event(body)
        assert result["challenge"] == "secret-challenge"

    def test_encrypted_without_key_errors(self):
        client = FeishuClient(app_id="x", app_secret="y")  # 无 encrypt_key
        body = json.dumps({"encrypt": "anything"}).encode()
        result = client.handle_event(body)
        assert result["type"] == "error"
        assert "encrypt_key" in result["error"]

    def test_message_event_parsing(self):
        """im.message.receive_v1 事件 → FeishuMessage。"""
        client = FeishuClient(app_id="x", app_secret="y")
        event_body = {
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_sender"}, "sender_type": "user"},
                "message": {
                    "message_id": "om_123", "chat_id": "oc_456",
                    "message_type": "text",
                    "content": json.dumps({"text": "帮我审查代码"}),
                },
            },
        }
        result = client.handle_event(json.dumps(event_body).encode())
        assert result["type"] == "event"
        msg = result["message"]
        assert isinstance(msg, FeishuMessage)
        assert msg.text == "帮我审查代码"
        assert msg.sender_id == "ou_sender"
        assert msg.chat_id == "oc_456"
        assert msg.msg_type == "text"

    def test_invalid_json_event(self):
        client = FeishuClient(app_id="x", app_secret="y")
        result = client.handle_event(b"not json{{{")
        assert result["type"] == "error"
