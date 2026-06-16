"""
飞书机器人接入 demo / Feishu bot integration demo.

展示如何用 FeishuClient 把 Nonull agent 接到飞书: 收到飞书消息 → 跑 agent →
把结果发回飞书。本 demo 不启动真实 HTTP 服务器 (那需要公网回调地址), 而是
演示完整的调用链, 并提供一个可直接嵌入 FastAPI/Flask 的事件处理函数样例。

真实部署步骤:
  1. 飞书开放平台 (https://open.feishu.cn) 创建"自建应用"
  2. 拿到 App ID / App Secret, 配到环境变量:
       NONULL_FEISHU_APP_ID=cli_xxx
       NONULL_FEISHU_APP_SECRET=xxx
     (可选, 加密模式) NONULL_FEISHU_ENCRYPT_KEY / NONULL_FEISHU_VERIFICATION_TOKEN
  3. 开通"机器人"能力 + 添加 im:message 权限
  4. 事件订阅填你的回调地址 (如 https://your-server/feishu/event),
     把本文件的 feishu_event_handler 接到该路由
  5. 把机器人加进群 / 私聊, 发消息即可

Run (不需真实凭证, 演示调用链):  python examples/feishu_bot_demo.py
"""
import asyncio
import json
import os

from channels.feishu_client import FeishuClient, FeishuMessage


# ── 事件处理函数 (可直接嵌入 FastAPI/Flask) ──────────────────────

async def feishu_event_handler(client: FeishuClient, body: bytes,
                               headers: dict, agent=None) -> dict:
    """处理一个飞书事件回调 / Handle one Feishu event callback.

    嵌入 FastAPI 示例:
        @app.post("/feishu/event")
        async def feishu_event(request: Request):
            body = await request.body()
            result = await feishu_event_handler(client, body, dict(request.headers), agent)
            if "challenge" in result:
                return {"challenge": result["challenge"]}  # URL 验证
            return {"code": 0}
    """
    result = client.handle_event(body, headers)

    # URL 验证: 原样返回 challenge
    if "challenge" in result:
        return {"challenge": result["challenge"]}

    if result.get("type") == "error":
        return {"code": -1, "error": result["error"]}

    # 普通消息事件: 跑 agent, 回复
    msg: FeishuMessage = result.get("message")
    if msg and msg.text and msg.sender_type == "user":
        # 跑 agent (若提供)
        if agent is not None:
            agent_result = await agent.run(msg.text)
            reply_text = agent_result.get("output") or "（无输出）"
        else:
            reply_text = f"收到: {msg.text}"
        # 回复到原消息
        client.reply(msg.message_id, reply_text[:2000])

    return {"code": 0}


async def main() -> None:
    print("=" * 64)
    print("🤖 飞书机器人接入 demo / Feishu bot integration demo")
    print("=" * 64)

    app_id = os.environ.get("NONULL_FEISHU_APP_ID", "")
    client = FeishuClient()  # 从环境变量读凭证

    if not app_id:
        print("\n⚠️  未配置飞书凭证 (NONULL_FEISHU_APP_ID 为空)。")
        print("   以下演示事件处理链路 (不发真实请求):\n")

        # 1) 演示 URL 验证事件处理
        print("─" * 64)
        print("【1】URL 验证事件 (飞书配置回调地址时发送)")
        verify_body = json.dumps({
            "type": "url_verification", "challenge": "ch_demo_123",
        }).encode()
        result = client.handle_event(verify_body)
        print(f"   输入: url_verification challenge")
        print(f"   输出: {result}  ← 飞书要求原样返回 challenge ✅")

        # 2) 演示消息事件解析
        print("\n" + "─" * 64)
        print("【2】消息事件解析 (用户发消息给机器人)")
        msg_body = json.dumps({
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_demo"}, "sender_type": "user"},
                "message": {
                    "message_id": "om_demo", "chat_id": "oc_demo",
                    "message_type": "text",
                    "content": json.dumps({"text": "帮我审查这段代码"}),
                },
            },
        }).encode()
        result = client.handle_event(msg_body)
        msg = result["message"]
        print(f"   解析出消息: text='{msg.text}'")
        print(f"             sender={msg.sender_id}, chat={msg.chat_id}")
        print(f"             → 这里会调 agent.run(text) 并 client.reply(...)")

        print("\n" + "=" * 64)
        print("✅ 事件链路演示完成。配置飞书凭证后可真实收发消息。")
        print("   完整接入步骤见本文件顶部 docstring。")
        print("=" * 64)
        return

    # 有凭证: 真实测试 token + 发消息
    print(f"\n✅ 检测到飞书凭证 (app_id={app_id[:8]}...)")
    try:
        token = client.get_tenant_access_token()
        print(f"✅ tenant_access_token 获取成功: {token[:12]}...")
        print("   (要真实发消息, 取消下面注释并填 receive_id)")
        # result = client.send_text("ou_xxx", "你好, 我是 Nonull 机器人")
        # print(f"   发送结果: {result.success}")
    except Exception as e:
        print(f"❌ token 获取失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
