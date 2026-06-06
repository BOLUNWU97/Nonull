"""
Web UI Channel / Web 通道

A FastAPI-based web interface for Nonull. Provides:
- A chat interface
- A skills browser
- A scenarios visualizer
- An agent state inspector
- A metrics dashboard
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


def create_app(agent=None, skill_registry=None, domain_registry=None) -> "FastAPI":
    """Create the FastAPI app for the Nonull web UI."""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed. Install with: pip install fastapi uvicorn jinja2")

    app = FastAPI(
        title="Nonull",
        description="Universal AI Agent Framework",
        version="0.1.0",
    )

    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse(content=INDEX_HTML)

    @app.get("/api/skills")
    async def list_skills() -> Dict[str, Any]:
        if skill_registry is None:
            return {"skills": [], "total": 0}
        skills = skill_registry.get_all_skills()
        return {
            "total": len(skills),
            "skills": [
                {
                    "name": s.metadata.name,
                    "version": s.metadata.version,
                    "category": s.metadata.category.value if hasattr(s.metadata.category, "value") else str(s.metadata.category),
                    "description": s.metadata.description,
                    "tags": s.metadata.tags,
                    "safety_level": s.metadata.safety_level,
                }
                for s in skills
            ],
        }

    @app.get("/api/scenarios")
    async def list_scenarios() -> Dict[str, Any]:
        # Try to load ADAS scenarios if available
        try:
            from domains.adas.scenarios import ScenarioEngine
            eng = ScenarioEngine()
            return {"scenarios": eng._all_scenarios() if hasattr(eng, "_all_scenarios") else []}
        except ImportError:
            return {"scenarios": []}

    @app.get("/api/domains")
    async def list_domains() -> Dict[str, Any]:
        if domain_registry is None:
            return {"domains": []}
        return {
            "domains": [
                {"name": d.metadata.name, "display_name": d.metadata.display_name, "description": d.metadata.description}
                for d in domain_registry.get_active()
            ]
        }

    @app.get("/api/agent/status")
    async def agent_status() -> Dict[str, Any]:
        if agent is None:
            return {"status": "not_loaded"}
        return {
            "status": "ready" if agent else "unbound",
            "state": getattr(agent, "state", "unknown") if agent else "no_agent",
        }

    @app.post("/api/agent/chat")
    async def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
        message = payload.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="'message' is required")
        if agent is None:
            return {"response": "[No agent bound]", "status": "no_agent"}
        try:
            if hasattr(agent, "run_sync"):
                result = agent.run_sync(message)
                return {"response": result.get("output", str(result)), "status": result.get("status", "ok")}
            return {"response": f"[Agent {type(agent).__name__} has no run_sync]", "status": "error"}
        except Exception as e:
            return {"response": f"Error: {e}", "status": "error"}

    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                if msg.get("type") == "chat" and agent is not None:
                    result = agent.run_sync(msg.get("message", ""))
                    await websocket.send_text(json.dumps({
                        "type": "response",
                        "data": result.get("output", str(result)),
                    }))
                elif msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            pass

    return app


INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Nonull — Universal AI Agent</title>
    <style>
        :root {
            --bg: #0e1117;
            --bg2: #161b22;
            --fg: #c9d1d9;
            --accent: #ff6b35;
            --accent2: #00c9a7;
            --border: #30363d;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
            background: var(--bg); color: var(--fg);
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        header { border-bottom: 1px solid var(--border); padding-bottom: 1rem; margin-bottom: 2rem; }
        h1 { color: var(--accent); font-size: 2.5rem; }
        h2 { color: var(--accent2); margin: 1.5rem 0 0.5rem; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
        .card {
            background: var(--bg2); border: 1px solid var(--border);
            border-radius: 8px; padding: 1rem; margin-bottom: 1rem;
        }
        .skill-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 0.5rem; margin-top: 0.5rem;
        }
        .skill-tag {
            background: var(--bg); border: 1px solid var(--accent);
            border-radius: 4px; padding: 0.3rem 0.6rem; font-size: 0.85rem;
        }
        .skill-tag.code { border-color: #6c63ff; }
        .skill-tag.safety { border-color: #ff6b6b; }
        .skill-tag.data { border-color: #00c9a7; }
        textarea, input {
            width: 100%; padding: 0.5rem; background: var(--bg);
            border: 1px solid var(--border); color: var(--fg);
            border-radius: 4px; font-family: inherit;
        }
        button {
            background: var(--accent); color: white; border: none;
            padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;
            margin-top: 0.5rem;
        }
        button:hover { opacity: 0.85; }
        #chat-log { height: 300px; overflow-y: auto; background: var(--bg); padding: 0.5rem; border-radius: 4px; }
        .chat-msg { margin-bottom: 0.5rem; padding: 0.3rem; border-radius: 4px; }
        .chat-msg.user { background: var(--bg2); }
        .chat-msg.bot { background: var(--bg2); border-left: 2px solid var(--accent); }
        .disclaimer { color: #ff6b6b; font-size: 0.85rem; margin-top: 1rem; padding: 0.5rem; border-left: 2px solid #ff6b6b; }
        .stats { display: flex; gap: 1rem; margin-top: 0.5rem; }
        .stat { background: var(--bg); padding: 0.5rem 1rem; border-radius: 4px; }
        .stat-value { color: var(--accent); font-size: 1.5rem; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Nonull — 智驾智能体 / Universal AI Agent</h1>
            <p>一个领域无关的 AI Agent 框架，融合 4 大架构，内置 30+ 技能</p>
            <div class="disclaimer">
                ⚠️ ADVISORY ONLY — Nonull is an internal development assistant, NOT a certified safety product.
                Do not use for production deployment or safety-critical decisions.
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <h2>💬 聊天 / Chat</h2>
                <div id="chat-log"></div>
                <textarea id="chat-input" rows="2" placeholder="问点什么... Ask anything..."></textarea>
                <button onclick="sendChat()">发送 / Send</button>
            </div>

            <div class="card">
                <h2>📊 状态 / Status</h2>
                <div class="stats" id="stats-grid">
                    <div class="stat"><div class="stat-value" id="stat-skills">--</div><div>技能 / Skills</div></div>
                    <div class="stat"><div class="stat-value" id="stat-scenarios">--</div><div>场景 / Scenarios</div></div>
                    <div class="stat"><div class="stat-value" id="stat-domains">--</div><div>领域 / Domains</div></div>
                </div>
                <button onclick="loadStats()">刷新 / Refresh</button>
            </div>
        </div>

        <div class="card">
            <h2>🛠️ 技能 / Skills</h2>
            <div class="skill-grid" id="skill-grid"></div>
        </div>

        <div class="card">
            <h2>🌍 领域 / Domains</h2>
            <div id="domain-list"></div>
        </div>
    </div>

    <script>
        async function loadStats() {
            try {
                const [skills, scenarios, domains] = await Promise.all([
                    fetch('/api/skills').then(r => r.json()),
                    fetch('/api/scenarios').then(r => r.json()),
                    fetch('/api/domains').then(r => r.json()),
                ]);
                document.getElementById('stat-skills').textContent = skills.total || 0;
                document.getElementById('stat-scenarios').textContent = (scenarios.scenarios || []).length;
                document.getElementById('stat-domains').textContent = (domains.domains || []).length;
                const grid = document.getElementById('skill-grid');
                grid.innerHTML = '';
                (skills.skills || []).forEach(s => {
                    const tag = document.createElement('div');
                    tag.className = 'skill-tag ' + (s.category || 'general').toLowerCase();
                    tag.title = s.description;
                    tag.textContent = s.name + ' v' + s.version;
                    grid.appendChild(tag);
                });
                const dlist = document.getElementById('domain-list');
                dlist.innerHTML = '';
                (domains.domains || []).forEach(d => {
                    const el = document.createElement('div');
                    el.innerHTML = `<strong>${d.display_name}</strong>: ${d.description}`;
                    dlist.appendChild(el);
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function sendChat() {
            const input = document.getElementById('chat-input');
            const log = document.getElementById('chat-log');
            const msg = input.value.trim();
            if (!msg) return;

            const userDiv = document.createElement('div');
            userDiv.className = 'chat-msg user';
            userDiv.textContent = '👤 ' + msg;
            log.appendChild(userDiv);
            input.value = '';

            try {
                const resp = await fetch('/api/agent/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg}),
                });
                const data = await resp.json();
                const botDiv = document.createElement('div');
                botDiv.className = 'chat-msg bot';
                botDiv.textContent = '🤖 ' + (data.response || '(no response)');
                log.appendChild(botDiv);
                log.scrollTop = log.scrollHeight;
            } catch (e) {
                const errDiv = document.createElement('div');
                errDiv.className = 'chat-msg bot';
                errDiv.textContent = '🤖 Error: ' + e.message;
                log.appendChild(errDiv);
            }
        }

        document.getElementById('chat-input').addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
        });

        loadStats();
    </script>
</body>
</html>"""


def _resolve_host(default: str = "127.0.0.1") -> str:
    """Resolve the bind host from NONULL_WEB_HOST env var (or default)."""
    return os.environ.get("NONULL_WEB_HOST", default)


def _resolve_port(default: int = 8765) -> int:
    """Resolve the bind port from NONULL_WEB_PORT env var (or default).

    Invalid values (non-integer, out of range) fall back to the default
    rather than raising at startup time.
    """
    raw = os.environ.get("NONULL_WEB_PORT")
    if not raw:
        return default
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return default
    if not (1 <= port <= 65535):
        return default
    return port


def main(agent=None, skill_registry=None, domain_registry=None, host: Optional[str] = None, port: Optional[int] = None):
    """Launch the web UI.

    Host / port resolution order:
        1. Explicit `host` / `port` arguments.
        2. `NONULL_WEB_HOST` / `NONULL_WEB_PORT` environment variables.
        3. Default (`127.0.0.1:8765`).
    """
    if not FASTAPI_AVAILABLE:
        raise SystemExit("FastAPI not installed. Run: pip install fastapi uvicorn jinja2")
    app = create_app(agent, skill_registry, domain_registry)
    bind_host = host if host is not None else _resolve_host()
    bind_port = port if port is not None else _resolve_port()
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")


if __name__ == "__main__":
    main()
