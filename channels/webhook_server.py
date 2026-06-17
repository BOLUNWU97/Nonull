"""
渠道 webhook 服务 / Channel webhook server (FastAPI).

把 ChannelHub 暴露成真实可运行的 HTTP 服务: 各平台的事件回调地址指向这里的
路由, 消息进来自动跑 agent 并回复。生产部署的最后一公里。

路由:
  POST /feishu/event       飞书事件订阅回调 (含 URL challenge)
  POST /dingtalk/event     钉钉事件回调
  POST /telegram/webhook   Telegram webhook
  POST /qq/webhook         QQ 官方机器人回调 (含 op=13 URL 验证)
  GET  /health             健康检查 + 渠道/指标

用法:
    from channels.channel_hub import ChannelHub
    from channels.webhook_server import build_app
    hub = ChannelHub(agent=my_agent)
    hub.register_feishu(...).register_telegram(...)
    app = build_app(hub)
    # uvicorn:  uvicorn channels.webhook_server:app  (或传 hub 自建)
    #   import uvicorn; uvicorn.run(build_app(hub), host="0.0.0.0", port=8000)

依赖: pip install -e ".[web]"  (fastapi + uvicorn)

@module: channels.webhook_server
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("Nonull.channels.webhook_server")

# 模块级导入 FastAPI 类型, 让 PEP 563 字符串注解 (Request 等) 能被
# FastAPI 的 get_type_hints 解析到 (否则 Request 落在 build_app 局部作用域,
# 解析失败会被当成 query 参数 → 422)。fastapi 缺失时延迟到 build_app 报错。
try:
    from fastapi import FastAPI, Request, Response
except ImportError:  # pragma: no cover - 仅在未装 fastapi 时
    FastAPI = Request = Response = None  # type: ignore


def build_app(hub: Any):
    """用一个已配置好渠道的 ChannelHub 构建 FastAPI app / Build the FastAPI app.

    分离构造函数 (而非模块级 app) 让测试可注入不同 hub, 也支持多实例。
    """
    if FastAPI is None:
        raise RuntimeError(
            "webhook 服务需要 fastapi: pip install -e '.[web]'"
        )

    app = FastAPI(title="Nonull Channel Webhooks", version="1.0.0")

    @app.get("/health")
    async def health():
        return {"status": "ok", "channels": hub.channels, "metrics": hub.metrics()}

    # ── 飞书 / Feishu ────────────────────────────────────────────
    @app.post("/feishu/event")
    async def feishu_event(request: Request):
        body = await request.body()
        result = await hub.handle_feishu_event(body, dict(request.headers))
        # URL 验证: 原样返回 challenge
        if "challenge" in result:
            return {"challenge": result["challenge"]}
        return result

    # ── 钉钉 / DingTalk ──────────────────────────────────────────
    @app.post("/dingtalk/event")
    async def dingtalk_event(request: Request):
        body = await request.body()
        return await hub.handle_dingtalk_event(body, dict(request.headers))

    # ── Telegram ─────────────────────────────────────────────────
    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request):
        body = await request.json()
        return await hub.handle_telegram_webhook(body)

    # ── QQ ───────────────────────────────────────────────────────
    @app.post("/qq/webhook")
    async def qq_webhook(request: Request):
        body = await request.body()
        try:
            payload = json.loads(body)
        except Exception:
            return {"code": -1, "error": "invalid JSON"}
        # QQ URL 验证 (op=13): 用私钥签名 plain_token 返回
        if payload.get("op") == 13:
            client = hub.client("qq")
            d = payload.get("d", {})
            plain_token = d.get("plain_token", "")
            event_ts = d.get("event_ts", "")
            if client and plain_token:
                try:
                    sig = client.sign_validation(plain_token, event_ts)
                    return {"plain_token": plain_token, "signature": sig}
                except Exception as e:
                    return {"code": -1, "error": f"sign failed: {e}"}
            return {"code": -1, "error": "qq not registered or missing plain_token"}
        # 普通事件: 解析消息类型 + 跑 agent
        d = payload.get("d", {})
        event_type = payload.get("t", "")  # 如 AT_MESSAGE_CREATE / GROUP_AT_MESSAGE_CREATE
        content = (d.get("content", "") or "").strip()
        msg_id = d.get("id", "")
        if "GROUP" in event_type:
            target = d.get("group_openid", "")
            return await hub.handle_qq_message("group", target, content, msg_id)
        else:
            target = d.get("channel_id", "")
            return await hub.handle_qq_message("channel", target, content, msg_id)

    logger.info("Nonull webhook 服务构建完成, 渠道: %s", hub.channels)
    return app


def run(hub: Any, host: str = "0.0.0.0", port: int = 8000) -> None:
    """直接起 uvicorn 服务 / Run the uvicorn server directly."""
    try:
        import uvicorn
    except ImportError as e:
        raise RuntimeError("需要 uvicorn: pip install -e '.[web]'") from e
    uvicorn.run(build_app(hub), host=host, port=port)
