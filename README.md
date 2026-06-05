
<p align="center">
  <img src="https://img.shields.io/badge/Nonull-智驾智能体-FF6B35?style=for-the-badge&logo=autoprefixer&logoColor=white"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue?style=flat-square"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-green?style=flat-square&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square"/>
  <img src="https://img.shields.io/badge/Advisory%20Safety-orange?style=flat-square"/>
  <img src="https://img.shields.io/badge/Advisory%20Checks-yellow?style=flat-square"/>
  <img src="https://img.shields.io/badge/status-alpha-orange?style=flat-square"/>
</p>

<p align="center">
  <b>🇨🇳 中文</b> · 
  <a href="#english">English</a>
</p>

<br>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=200&color=0:FF6B35,100:1A1A2E&text=Nonull&fontSize=80&fontColor=white&animation=fadeIn&section=header"/>
</p>

<h3 align="center">
  🚗 有性格 · 有记忆 · 有安全的智驾 AI 工程师
</h3>

<p align="center">
  <i>An AI engineer for autonomous driving — with personality, memory, and safety awareness.</i>
</p>

<br>

---

<h2 align="center">✨ 一句话认识 Nonull ✨</h2>

<p align="center">
  <b>Nonull</b> 是专为 <b>智能驾驶行业</b> 设计的下一代 AI 智能体。<br>
  它像一位经验丰富的资深工程师，帮你审查代码、分析安全、设计测试、生成场景。<br>
  而且它<b>有记忆、有安全意识、有自己的性格</b>。
</p>

<br>

> **📌 重要声明 / Important Disclaimer**
>
> Nonull 是一个**内部使用的 ADAS 工程开发助手（developer assistant）**，**不是**经过 ISO 26262 / ASIL-D 认证的车规级安全产品。
>
> 本项目中的"安全层 / safety layer"是**建议性（advisory）**的：它参考 ISO 26262 / MISRA / ASPICE 等标准的**模式与术语**进行风险提示和检查建议，但**并不实现** ASIL-D 要求的"抗干扰（freedom from interference）"、"MC/DC 覆盖"、"形式化验证"、"独立安全单元（SEooC）流程"等条款。
>
> **请勿将本项目用于任何量产部署、安全关键决策，或替代经过认证的安全机制。**
>
> ---
>
> Nonull is an **internal ADAS engineering assistant**, **not** an ISO 26262 / ASIL-D certified safety product. The safety layer in this project is **advisory only** — it references ISO 26262 / MISRA / ASPICE patterns and terminology for risk hints, but does **not** implement ASIL-D requirements such as freedom from interference, MC/DC coverage, formal verification, or SEooC processes. **Do not use this project for production deployment, safety-critical decisions, or as a substitute for certified safety mechanisms.**

<br>

<div align="center">

```
"帮我审查这个 AEB 模块的代码"     →  🛡️  MISRA 规范检查 + Bug 定位 + 优化建议
"对紧急制动系统做 HARA 分析"     →  📋  ISO 26262 标准分析 + ASIL 等级
"生成雨天夜间行人横穿场景"       →  🌧️  标准 OpenSCENARIO 场景文件
"分析今天路测日志有什么问题"     →  📊  异常模式识别 + 关键问题汇总
```

</div>

<br>

---

<h2 align="center">🔥 它和别的 AI 有什么不一样？</h2>

<br>

<table align="center">
  <tr>
    <th width="120">对比项</th>
    <th width="250">其他 AI Agent</th>
    <th width="350"><b>🚀 Nonull</b></th>
  </tr>
  <tr>
    <td align="center">🧠 <b>记忆</b></td>
    <td align="center">聊完就忘，每次都是新会话</td>
    <td align="center"><b>四种记忆系统</b>，可配置容量（默认 10K 条目），越用越懂你</td>
  </tr>
  <tr>
    <td align="center">🛡️ <b>安全</b></td>
    <td align="center">你说啥它做啥，没有安全检查</td>
    <td align="center"><b>五关安全建议</b> + ASIL 风险提示（开发助手级，非认证）</td>
  </tr>
  <tr>
    <td align="center">👤 <b>性格</b></td>
    <td align="center">一个风格到底，冷冰冰</td>
    <td align="center"><b>三种驾驶人格</b>：保守派 🛡️ / 运动派 🚀 / 老司机 🧓</td>
  </tr>
  <tr>
    <td align="center">📊 <b>反馈</b></td>
    <td align="center">没有反馈机制</td>
    <td align="center"><b>安全指标记录</b>（基础反馈统计，建议性，非游戏化进度）</td>
  </tr>
</table>

<br>

---

<h2 align="center">🏗️ 四大架构融合</h2>

<p align="center">
  Nonull 融合了业界四种领先的智能体架构，取长补短：
</p>

<br>

<p align="center">
  <img src="https://img.shields.io/badge/OpenClaw-Triple--Layer-FF6B35?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Hermes%20Agent-Profile%20Isolation-6C63FF?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/openHuman-Neocortex%20Memory-00C9A7?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Claude%20Code-Deny--First%20Safety-FF6B6B?style=for-the-badge"/>
</p>

<br>

| 架构 | 贡献 | 在 Nonull 中的体现 |
|------|------|-------------------|
| 🦞 **OpenClaw** | 三层架构 | Gateway / Agent / Channels 三层分离 + Nexus+Tendrils 编排 |
| 🏛️ **Hermes Agent** | 配置隔离 | Profile 隔离（dev/test/prod/simulation）+ 工具注册表 |
| 🧠 **openHuman** | 记忆系统 | Neocortex 多层记忆 + 潜意识循环 + 遗忘曲线（默认内存实现，可插拔后端） |
| 🔐 **Claude Code** | 安全体系 | Deny-First 安全 + 40 个钩子事件 + SubAgent 隔离 |

<br>

---

<h2 align="center">⚡ 60 秒上手</h2>

<br>

<h3 align="left">📦 Installation / 安装</h3>

```bash
# Install (after git clone)
pip install -e .

# Run
nonull                    # after pip install
python -m nonull          # any time
```

<h3 align="left">🔐 Set up environment / 配置环境变量</h3>

To run the LLM agent, you need an API key. Copy the example file and fill in your key:

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit .env and set your key
#    (on Windows: notepad .env, or use any editor)
NONULL_LLM_API_KEY=sk-your-key-here

# Optional: pick a different provider / model
# NONULL_LLM_PROVIDER=openai
# NONULL_LLM_MODEL=gpt-4o
# NONULL_LLM_API_BASE=https://api.openai.com/v1
```

**Without a key?** The CLI still works for slash commands (`/help`, `/clear`, `/history`, `/session`, `/stats`, etc.) — you just can't run the LLM agent. On startup you'll see:

```
(Agent mode disabled — set NONULL_LLM_API_KEY to enable)
```

<p align="center">
  <img src="https://img.shields.io/badge/CLI-Rich%20Formatting-FF6B35?style=flat-square"/>
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/11%20Slash%20Commands-Ready-success?style=flat-square"/>
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/Multi--line-Supported-blue?style=flat-square"/>
</p>

<h3 align="left">🐍 在代码中使用</h3>

```python
from core import Nonull

agent = Nonull()
result = agent.run_sync("分析 AEB 系统的安全需求")
print(result["output"])
```

<br>

---

<h2 align="center">🎯 核心功能一览</h2>

<br>

<div align="center">

| 模块 | 一句话描述 | 状态 |
|------|-----------|:----:|
| 🤖 **核心引擎** | ReAct + 规划 + 反思 融合状态机 | ✅ |
| 🧠 **记忆系统** | 工作/情景/知识/技能 四种记忆 + 潜意识 | ✅ |
| 🛡️ **安全卫士** | ISO 26262 + Deny-First + 五关检查流水线 | ✅ |
| 🔧 **31 个技能** | 覆盖代码/安全/感知/规划/测试/仿真/数据/研究/DevOps 9 大领域 | ✅ |
| 🔄 **多Agent** | DAG 任务分解 + 8 个 Agent 并行 + 冲突解决 | ✅ |
| 👤 **驾驶人格** | 🛡️ 保守派 / 🚀 运动派 / 🧓 老司机 | ✅ 🆕 |
| 🧠 **场景思维** | 36 个标准场景自动关联 + 覆盖率分析 | ✅ 🆕 |
| 📊 **安全指标** | 安全指标记录与统计（建议性，非游戏化） | ✅ 🆕 |
| 👋 **副驾模式** | 主动风险提醒 + 每日简报 | ✅ 🆕 |
| 🔌 **多通道** | CLI / API / MCP / 飞书 / 钉钉 / Telegram | ✅ |

</div>

<br>

---

<h2 align="center">🧪 实验性功能</h2>

<p align="center">
  <b>⚠️ 警告 / WARNING</b>：以下模块是<strong>实验性的</strong>，未达到生产环境要求。<br>
  The following modules are <strong>experimental</strong> and not production-ready.
</p>

<div align="center">

| 模块 | 描述 | 风险 |
|------|------|------|
| 🧬 **自我进化**（`experimental/evolution/`） | 经验挖掘 / 技能创生 / 元认知 / 提示词优化 | 会自我修改技能注册表和提示词库 |
| 🌟 **自我意识**（`experimental/consciousness/`） | SelfModel / 好奇心 / 自主成长 / 意识循环 | 非确定性、行为不可预测 |

</div>

<p align="center">
  <b>绝对不要</b>将实验性模块接入任何<strong>影响车辆控制决策</strong>的路径。<br>
  它们与 ISO 26262 的"无不可接受风险"原则直接冲突。<br><br>
  <b>Never</b> wire experimental modules into any path that influences a vehicle control decision.<br>
  They directly conflict with ISO 26262's "freedom from unacceptable risk" principle.
</p>

<p align="center">
  详见 <a href="experimental/README.md">experimental/README.md</a>
</p>

<br>

---

<h2 align="center">👤 独有特色：驾驶人格系统</h2>

<br>

<table align="center">
  <tr>
    <th width="33%">🛡️ 保守派工程师</th>
    <th width="33%">🚀 运动派工程师</th>
    <th width="33%">🧓 老司机</th>
  </tr>
  <tr>
    <td align="center"><i>"这个场景的边界条件考虑了吗？"</i></td>
    <td align="center"><i>"这个模块还有 30% 的优化空间！"</i></td>
    <td align="center"><i>"这种情况我见过，通常是..."</i></td>
  </tr>
  <tr>
    <td><b>风格：</b>谨慎、稳妥、重视冗余</td>
    <td><b>风格：</b>激进、追求极限、创新</td>
    <td><b>风格：</b>经验丰富、直觉锐利</td>
  </tr>
  <tr>
    <td><b>适合：</b>安全分析、量产项目审查</td>
    <td><b>适合：</b>性能优化、算法评估</td>
    <td><b>适合：</b>场景分析、异常诊断</td>
  </tr>
</table>

<br>

```python
from persona import PersonaOrchestrator, PersonaType

# 同一段代码，三种人格三种看法
for p in [PersonaType.CONSERVATIVE, PersonaType.SPORTY, PersonaType.VETERAN]:
    ai = PersonaOrchestrator(p)
    info = ai.get_current_persona()
    print(f"[{info['name']}] {info['phrase']}")
```

<br>

---

<h2 align="center">📂 项目结构</h2>

<br>

```
📁 nonull/
├── 📄 README.md              # 项目介绍（就是你正在看的这个）
├── 📄 AGENT.md               # 智能体身份标识 (SOUL.md 风格)
├── 📄 CLAUDE.md              # 开发指南
├── 📄 requirements.txt       # 依赖
├── 📄 setup.py               # 安装配置
│
├── 📁 core/                  # 🤖 核心引擎
│   ├── agent_core.py         #    主循环（状态机 + ReAct + 反思）
│   └── config.py             #    配置系统
│
├── 📁 memory/                # 🧠 记忆系统
│   ├── working_memory.py     #    工作记忆（前额叶）
│   ├── episodic.py           #    情景记忆（海马体）
│   ├── semantic.py           #    语义记忆（新皮层）
│   ├── procedural.py         #    程序性记忆（小脑）
│   ├── neocortex.py          #    新皮层聚合（默认内存后端，可插拔）
│   └── subconscious_loop.py  #    潜意识循环
│
├── 📁 safety/                # 🛡️ 安全卫士
│   ├── guardian.py           #    五层安全流水线
│   ├── deny_first.py         #    Deny-First 规则引擎
│   └── compliance.py         #    ISO 26262 / MISRA 合规
│
├── 📁 skills/                # 🔧 31 个技能
│   ├── registry.py           #    动态注册中心
│   ├── code_skills.py        #    代码技能组
│   ├── safety_skills.py      #    安全技能组
│   ├── perception_skills.py  #    感知技能组
│   ├── planning_skills.py    #    规划技能组
│   ├── testing_skills.py     #    测试技能组
│   ├── simulation_skills.py  #    仿真技能组
│   ├── data_skills.py        #    数据技能组
│   ├── research_skills.py    #    研究技能组
│   └── devops_skills.py      #    DevOps 技能组
│
├── 📁 persona/               # 👤 独有：人格系统
│   ├── driving_persona.py    #    三种驾驶人格
│   ├── scenario_engine.py    #    场景思维引擎（36 场景）
│   ├── safety_badge.py       #    安全指标记录系统
│   ├── co_pilot.py           #    副驾主动提醒
│   └── persona_orchestrator.py #  人格编排器
│
├── 📁 orchestration/         # 🔄 多 Agent 编排
│   ├── orchestrator.py       #    DAG 任务分解
│   ├── agent_pool.py         #    Agent 池
│   ├── communication.py      #    EventBus 通信
│   └── workflows.py          #    8 个预置工作流
│
├── 📁 experimental/          # 🧪 实验性模块（⚠️ 非生产就绪）
│   ├── README.md             #    警告与使用说明
│   ├── consciousness/        #    🌟 自我意识（实验性）
│   └── evolution/            #    🌱 自我进化（实验性）
│
├── 📁 channels/              # 🔌 通信通道
│   ├── cli.py                #    CLI 交互（Rich 格式化）
│   ├── gateway.py            #    网关路由
│   ├── mcp_adapter.py        #    MCP 协议适配
│   └── platform_adapters.py  #    飞书/钉钉/Telegram/WebSocket/HTTP 5 个适配器
│
├── 📁 hooks/                 # 🪝 钩子系统
│   └── hook_system.py        #    40 钩子事件 × 4 类型
│
├── 📁 docs/                  # 📚 文档
│   ├── 说明书-完整版.md       #    完整使用说明书
│   ├── 一页纸速览.md          #    一分钟看完
│   ├── 快速上手指南.md        #    两分钟上手
│   └── architecture.md       #    架构深度解析
│
├── 📁 examples/              # 📖 使用示例
│   ├── quickstart.py         #    快速入门
│   ├── code_review.py        #    代码审查
│   ├── safety_analysis.py    #    安全分析
│   └── multi_agent_workflow.py #  多 Agent 工作流
│
├── 📁 tests/                 # 🧪 测试
│   ├── test_core.py                      # 核心测试
│   ├── test_memory.py                    # 记忆系统测试
│   ├── test_safety_badge_api.py          # SafetyBadge API + 弃用包装器
│   └── test_persona_exports.py           # persona 包对外导出契约
│
└── 📁 config/                # ⚙️ 配置
    ├── config.yaml
    └── safety_rules.yaml
```

<br>

---

<h2 align="center">📖 文档导航</h2>

<br>

<p align="center">
  <a href="docs/说明书-完整版.md">
    <img src="https://img.shields.io/badge/📖-完整说明书-FF6B35?style=for-the-badge"/>
  </a>
  <a href="docs/一页纸速览.md">
    <img src="https://img.shields.io/badge/📄-一页纸速览-6C63FF?style=for-the-badge"/>
  </a>
  <a href="docs/快速上手指南.md">
    <img src="https://img.shields.io/badge/🚀-快速上手-00C9A7?style=for-the-badge"/>
  </a>
  <a href="docs/architecture.md">
    <img src="https://img.shields.io/badge/🏗️-架构文档-FF6B6B?style=for-the-badge"/>
  </a>
</p>

<br>

---

<h2 align="center">🏅 Nonull = 非空 = Never Null</h2>

<p align="center">
  <i>"每一个决策都有依据，不空想。<br>
  每一次响应都有内容，不空答。<br>
  每一个动作都经过安全验证，不出错。"</i>
</p>

<br>

<p align="center">
  <b>如临深渊，如履薄冰。</b> — 《诗经·小雅》
</p>

<br>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=120&color=0:1A1A2E,100:FF6B35&section=footer"/>
</p>

---

<h2 id="english" align="center">🌐 English</h2>

<p align="center">
  <b>Nonull</b> is a next-generation AI agent built for the <b>autonomous driving industry</b>.<br>
  It's like a seasoned senior engineer — reviewing code, analyzing safety, designing tests, and generating scenarios.<br>
  With <b>memory, safety awareness, and a unique personality</b>.
</p>

<br>

<table align="center">
  <tr>
    <th>Feature</th>
    <th>Description</th>
  </tr>
  <tr><td>🤖 Core Engine</td><td>ReAct + Plan-and-Execute + Reflexion fused state machine</td></tr>
  <tr><td>🧠 Memory System</td><td>Working/Episodic/Semantic/Procedural + Neocortex (configurable capacity, default in-memory backend)</td></tr>
  <tr><td>🛡️ Safety Guardian</td><td>ISO 26262 + Deny-First + 5-layer safety pipeline</td></tr>
  <tr><td>🔧 31 Skills</td><td>9 categories: Code/Safety/Perception/Planning/Testing/Simulation/Data/Research/DevOps</td></tr>
  <tr><td>👤 Driving Persona</td><td>Conservative 🛡️ / Sporty 🚀 / Veteran 🧓 — three characters</td></tr>
  <tr><td>🧠 Scenario Engine</td><td>36 built-in driving scenarios + coverage analysis</td></tr>
  <tr><td>📊 Safety Metrics</td><td>Safety metrics tracking (advisory, not gamified)</td></tr>
  <tr><td>🔌 Multi-Channel</td><td>CLI / API / MCP / Telegram / Feishu / DingTalk</td></tr>
</table>

<br>

> **Note**: Self-evolution and self-awareness modules are <b>experimental</b> and have been moved to <code>experimental/</code>. They are not wired into the production agent loop and must not be used in any safety-critical path. See <a href="experimental/README.md">experimental/README.md</a> for warnings.
