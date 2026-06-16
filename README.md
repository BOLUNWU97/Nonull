<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&height=220&color=gradient&customColorList=12,20,24&text=Nonull&fontSize=90&fontColor=ffffff&fontAlignY=38&desc=Universal%20AI%20Agent%20Framework&descSize=20&descAlignY=60&animation=fadeIn"/>

<p>
  <img src="https://img.shields.io/badge/version-0.3.0-1f6feb?style=flat-square"/>
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/tests-839_passing-2ea043?style=flat-square&logo=pytest&logoColor=white"/>
  <img src="https://img.shields.io/badge/license-MIT-eac54f?style=flat-square"/>
  <img src="https://img.shields.io/badge/safety-advisory_only-f0883e?style=flat-square"/>
</p>

<p>
  <img src="https://img.shields.io/badge/3_execution_modes-1f6feb?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/multi--model_scheduling-8957e5?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/4--layer_memory-1a7f37?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/58_skills-bf3989?style=for-the-badge"/>
</p>

<p><b>🇨🇳 中文</b> · <a href="#-english">English</a></p>

<h3>一个有记忆、会路由、能协作的领域无关 AI Agent 框架</h3>
<p><i>A domain-agnostic AI agent framework with persistent memory, intelligent model routing, and multi-model collaboration.</i></p>

</div>

---

> [!IMPORTANT]
> **声明 / Disclaimer** — Nonull 是一个**建议性（advisory）的工程开发助手**，**不是**经过 ISO 26262 / ASIL-D 认证的车规级安全产品。其"安全层"参考 ISO 26262 / MISRA / ASPICE 的**模式与术语**做风险提示，但**不实现** ASIL-D 的抗干扰、MC/DC 覆盖、形式化验证等条款。**请勿用于量产部署、安全关键决策，或替代任何认证安全机制。**
>
> Nonull is an **advisory engineering assistant**, **not** an ISO 26262 / ASIL-D certified safety product. The safety layer references standards' *patterns and terminology* for risk hints only. **Do not use for production deployment, safety-critical decisions, or as a substitute for certified safety mechanisms.**

<br>

## 📋 目录

- [60 秒认识](#-60-秒认识) · [三种执行模式](#-三种执行模式) · [多模型混合调度](#-多模型混合调度)
- [记忆系统](#-记忆系统) · [技能库（58 个）](#-技能库58-个) · [安全层](#-安全层) · [架构](#-架构)
- [快速开始](#-快速开始) · [项目结构](#-项目结构) · [状态与诚实清单](#-状态与诚实清单) · [English](#-english)

<br>

## ⚡ 60 秒认识

Nonull 把**任务**交给最合适的执行方式和模型，自己记住做过什么，并在需要时让多个模型协作。

```python
from core import Nonull

agent = Nonull()

# 复杂多步任务 → 结构化认知循环（规划/推理/行动/反思）
await agent.run("分析 AEB 系统的安全需求")

# 工具驱动任务 → ReAct 循环（LLM 自主选工具）
await agent.run_react("算 15×23 再统计这句话的字数", tools=[calc, word_count])

# 任意任务 → 多模型混合调度（自动选模型，超复杂任务多模型协作）
r = await agent.run_hybrid("帮我设计一个分布式限流方案")
print(r["schedule_mode"])   # "single" | "collaboration"
print(r["model_used"])      # 用了哪个/几个模型
```

三种模式背靠**同一个 agent 实例**，共享 LLM 客户端、成本追踪、记忆（召回+存储）、安全层，返回**统一格式**。

<br>

## 🚀 三种执行模式

| 模式 | 方法 | 内核 | 适用场景 |
|------|------|------|---------|
| 🧩 **结构化循环** | `run()` | 五阶段状态机 `PLAN → REASON → ACT → REFLECT`（ReAct + Plan-and-Execute + Reflexion 融合）+ 失败恢复 | 复杂多步任务，需要规划/反思/记忆召回 |
| 🔁 **ReAct 循环** | `run_react()` | `AgentLoop`：while 循环 + LLM 完全控制流（Reason→Act→Observe）+ async 工具 + circuit-breaker + timeout | 工具驱动任务，LLM 自主选工具 |
| 🌐 **混合调度** | `run_hybrid()` | `HybridScheduler`：自动分类路由 + 单模型分发 / 多模型协作 | 任意任务，让框架自动决定用哪个/几个模型 |

**统一返回格式**（三种模式都有）：
```python
{ "status", "output", "iterations", "duration", "cost", "mode", "error", ... }
```

<details>
<summary><b>AgentLoop（ReAct 内核）的真实能力</b></summary>

- **async / sync 工具**：自动 `await` 协程工具（HTTP/DB 等），不会返回未执行的 coroutine
- **circuit-breaker**：同一工具连续失败 ≥3 次 → 提示 LLM 换路，防止烧光 max_steps
- **timeout 保护**：`asyncio.wait_for` + 每步让出 event loop，LLM 挂起时能真正中断
- **context trimming**：messages 超阈值时丢弃中间轮、保留首尾，防 context 撑爆
- **成本追踪**：每次调用记入共享 `CostTracker`
- **参数 schema 推断**：从函数签名推断工具参数，弱模型也不会漏参数
</details>

<br>

## 🌐 多模型混合调度

`multimodel/` 包：接入多厂商大模型，按任务**复杂度 / 隐私 / 成本 / 速度**自动路由，超复杂任务自动多模型协作。

```
┌──────────────────────── HybridScheduler（统一门面）─────────────────────────┐
│                                                                            │
│   TaskRouter          ModelDispatcher          MultiModelCollaborator       │
│   ─────────           ───────────────          ─────────────────────       │
│   分类 + 路由          多Key轮询 + 重试           拆解 → 并行 → 交叉校验 → 汇总   │
│   简单→小模型           降级 + 负载均衡            （仅超复杂任务）              │
│   复杂→强模型           调用日志                                              │
│   隐私→本地                                                                  │
│        └──────────────────── ModelRegistry（模型管理层）────────────────────┘ │
│              ModelEntry × N  +  KeyRotator × N（每模型一个多Key轮询器）        │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │ 复用纯 httpx 的 OpenAI 兼容 client
        ┌────────────────────────────┼────────────────────────────┐
   云端 API                       本地部署                      LiteLLM 网关
   OpenAI / Claude               Ollama                       （可选，统一所有厂商）
   DeepSeek / 通义千问            LM Studio
```

| 层 | 组件 | 能力 |
|---|---|---|
| 模型管理 | `ModelRegistry` `KeyRotator` | 多厂商注册 + 多 API Key 轮询 + 冷却跳过（429/401） |
| 智能路由 | `TaskRouter` | 启发式分类（代码/长度/关键词/隐私）+ 质量/成本/速度策略 |
| 调用分发 | `ModelDispatcher` | 多 Key 轮询 + 失败重试 + 模型降级 + 负载均衡 + 调用日志 |
| 多模型协作 | `MultiModelCollaborator` | 超复杂任务：强模型拆解 → 子任务并行 → 跨模型交叉校验 → 汇总整合 |
| 统一门面 | `HybridScheduler` | 一个 `aschedule()` 串联以上全部 |

> **设计取舍**：内置 client 是纯 httpx 打 OpenAI 兼容端点，而 Ollama / LM Studio / DeepSeek / 通义千问（兼容模式）/ LiteLLM / vLLM **都暴露 OpenAI 兼容 `/chat/completions`** —— 所以一个 client 全覆盖，**不强依赖 LiteLLM**。想用 LiteLLM 网关，把 `base_url` 指向网关即可，代码零改动。

📖 完整集成文档（架构 / 配置 / 路由 / 分发 / 协作 / 接入 / 报错 7 节）：[`multimodel/INTEGRATION_GUIDE.md`](multimodel/INTEGRATION_GUIDE.md)

<br>

## 🧠 记忆系统

四层记忆 + 新皮层协调 + 后台潜意识循环，跨会话持久化（`save_state` / `load_state`）。

| 层 | 类 | 存什么 | 召回 / 遗忘 |
|---|---|---|---|
| 工作记忆 | `WorkingMemory` | 滑动上下文窗口 + token 预算（软 4000 / 硬 8000）+ 摘要缓冲 | 优先级淘汰 + 可选摘要回调 |
| 情景记忆 | `EpisodicMemory` | 事件/场景/调试会话（带 strength、importance、embedding） | **真实艾宾浩斯遗忘**（`strength *= exp(-rate·hours)`）+ 余弦相似度×重要度×强度召回 |
| 语义记忆 | `SemanticMemory` | 知识节点 + 关系图（内置 8 条 ADAS 知识种子） | 余弦相似度×置信度查询 + 关系图游走 |
| 程序记忆 | `ProceduralMemory` | 技能定义 + 执行轨迹（EMA 成功率） | 余弦相似度找技能 + 频率统计发现模式 |
| 新皮层 | `Neocortex` | 协调四层 + 倒排关键词索引 + n-gram 向量索引 | **混合召回**（关键词 + n-gram 向量）+ prune / consolidate / 持久化 |
| 潜意识 | `SubconsciousLoop` | 后台线程生成洞察 | 9 类洞察生成器（模式/联系/类比/…），可 start/stop/pause |

> **诚实说明**：召回是 **n-gram 关键词 + 向量混合**，**不是** transformer 语义嵌入。真正的语义嵌入 / FAISS / Chroma / Redis 需要你提供 `embedder=` 或后端 —— 框架默认零依赖、纯内存实现。跨会话记忆连续性已端到端验证（Agent A 存 → Agent B 跨会话逐字召回）。

<br>

## 🔧 技能库（58 个）

全部**自动发现注册**，按领域无关 / ADAS / 多模态 / 创意等分类。

<table>
<tr><th>分类</th><th>数量</th><th>技能（invoke 名）</th></tr>
<tr><td>🌐 <b>Web</b></td><td>3</td><td><code>web_fetch</code> · <code>web_search</code>⚠️ · <code>link_extractor</code></td></tr>
<tr><td>📊 <b>数据</b></td><td>4</td><td><code>json_formatter</code> · <code>csv_parser</code> · <code>text_statistics</code> · <code>diff</code></td></tr>
<tr><td>💻 <b>代码（通用）</b></td><td>3</td><td><code>regex_tester</code> · <code>json_schema_generator</code> · <code>code_counter</code></td></tr>
<tr><td>📄 <b>文档</b></td><td>3</td><td><code>markdown_to_html</code> · <code>readme_skeleton</code> · <code>docstring_generator</code></td></tr>
<tr><td>🌍 <b>翻译</b></td><td>2</td><td><code>language_detector</code>⚠️ · <code>translation_prompt</code></td></tr>
<tr><td>🔨 <b>工具</b></td><td>4</td><td><code>uuid_generator</code> · <code>hash</code> · <code>timestamp</code> · <code>base64</code></td></tr>
<tr><td>🖼️ <b>多模态</b></td><td>7</td><td><code>image_info</code> · <code>image_resize</code> · <code>image_base64</code> · <code>pdf_info</code> · <code>pdf_extract_text</code> · <code>audio_info</code> · <code>audio_transcribe</code>⚠️</td></tr>
<tr><td>💡 <b>创意/效率/学习</b></td><td>8</td><td><code>brainstorm</code> · <code>metaphor_generator</code> · <code>story_plot</code> · <code>pomodoro_schedule</code> · <code>eisenhower_matrix</code> · <code>flashcard_generator</code> · <code>quiz_generator</code> · <code>spaced_repetition</code></td></tr>
<tr><td>📁 <b>文件系统</b></td><td>6</td><td><code>file_read</code> · <code>file_write</code> · <code>file_edit</code> · <code>glob</code> · <code>grep</code> · <code>list_dir</code></td></tr>
<tr><td>⚙️ <b>执行</b></td><td>1</td><td><code>code_runner</code></td></tr>
<tr><td>🚗 <b>ADAS 感知</b></td><td>4</td><td><code>sensor_analysis</code> · <code>perception_model_review</code> · <code>sensor_calibration</code> · <code>object_detection_review</code></td></tr>
<tr><td>🚗 <b>ADAS 规划</b></td><td>3</td><td><code>route_planning</code> · <code>behavior_planning</code> · <code>trajectory_optimization</code></td></tr>
<tr><td>🛡️ <b>ADAS 安全</b></td><td>4</td><td><code>hara_analysis</code> · <code>fmea</code> · <code>iso26262_check</code> · <code>safety_case</code></td></tr>
<tr><td>🎮 <b>ADAS 仿真</b></td><td>3</td><td><code>scenario_generation</code> · <code>carla_runner</code> · <code>edge_case</code></td></tr>
<tr><td>🔧 <b>ADAS 工程</b></td><td>16</td><td>code_review/optimization/refactoring/bug_detection · log_analysis · test_case_design · sil/hil/regression_test · paper_analysis · sota_tracking · cicd · deployment · monitoring …</td></tr>
</table>

> ⚠️ 标注的是 **stub / demo**：`web_search`、`audio_transcribe`、`language_detector` 当前返回占位结果 + 警告（接真实 API / 模型后即可用）。`image_resize` / `pdf_extract_text` 在缺 Pillow / pypdf 时降级。**其余均为真实实现，graceful 降级、不抛异常。**

```python
# 技能自动发现，按名调用
from skills.registry import SkillRegistry
reg = SkillRegistry()
reg.auto_discover()
result = reg.get("brainstorm").execute({"topic": "智能家居", "count": 5})
```

<br>

## 🛡️ 安全层

Nonull 实际使用 `core/safety.py` 的 **`SafetyGuardian`** —— 一个 **3 步建议性门控**：

1. **正则黑名单** — `block_pattern()` 拦截危险模式（始终先于放行）
2. **命令白名单** — 不在白名单的动作类型加风险分
3. **上下文风险评分** — `_evaluate_context_risk` 启发式打分 vs `max_risk_score`（默认 0.7，deny-first 起步 0.5）

`text:` 文本输出**跳过内容评分**（agent 的回答讨论 "write/delete" 概念不会被误拦）。**无 ASIL 分级 —— 纯建议性。**

> `safety/` 包里另有一个 5 层管线 `SafetyGuardian`（含 ASIL 枚举），但**生产代码不使用它**（仅测试 / CI 引用）—— 属于参考实现，不要混淆。

<br>

## 🏗️ 架构

融合四种业界智能体架构的设计理念：

| 架构 | 借鉴 | 在 Nonull 的体现 |
|------|------|-----------------|
| 🦞 **OpenClaw** | 三层分离 | Gateway / Agent / Channels 三层 |
| 🏛️ **Hermes Agent** | 配置隔离 | Profile 隔离（dev/test/prod/sim）+ 工具注册表 |
| 🧠 **openHuman** | 新皮层记忆 | 四层记忆 + 潜意识循环 + 遗忘曲线 |
| 🔐 **Claude Code** | Deny-First 安全 | 建议性安全门控 + 41 钩子事件 + SubAgent 隔离 |

**多 Agent 编排**（`orchestration/`）：`Orchestrator` 做 DAG 任务分解，8 个预置工作流（code_review / safety_analysis / test_generation / bug_triage / architecture_review / scenario_generation / compliance_check / data_pipeline_review），通过注入的 `executor_fn` 执行（LLM 在 agent 侧，编排器本身回调驱动）。

**钩子系统**（`hooks/`）：41 个钩子事件 × 4 种类型（SHELL / HTTP / LLM / AGENT）。

<br>

## 📦 快速开始

```bash
# 安装
pip install -e .

# 配置 LLM（复制模板填 key）
cp .env.example .env
#   NONULL_LLM_API_KEY=sk-your-key-here
#   NONULL_LLM_PROVIDER=openai            # 可选
#   NONULL_LLM_MODEL=gpt-4o               # 可选
#   NONULL_LLM_API_BASE=https://...       # 可选（本地模型/兼容端点）

# 运行 CLI
nonull                # pip 安装后
python -m nonull      # 任何时候
```

无 key 时 CLI 仍可用斜杠命令（`/help` `/stats` `/session` …），只是不能跑 LLM agent。

**多模型配置**：编辑 [`multimodel/nonull_models.yaml`](multimodel/nonull_models.yaml) 的 `models:` 段（加一条即注册一个模型）。LiteLLM 网关配置见 [`multimodel/litellm_config.yaml`](multimodel/litellm_config.yaml)。

<br>

## 📂 项目结构

```
nonull/
├── core/                 # 🤖 核心引擎
│   ├── agent_core.py     #    Nonull 主类 + 三种执行模式（run/run_react/run_hybrid）
│   ├── agent_loop.py     #    AgentLoop —— ReAct 内核（async工具/circuit-breaker/timeout）
│   ├── memory_system.py  #    记忆系统门面（Neocortex + 潜意识）
│   ├── safety.py         #    SafetyGuardian（实际使用的 3 步建议性门控）
│   ├── llm_client.py     #    纯 httpx 的 OpenAI 兼容 client（多 provider + fallback）
│   ├── cost_tracker.py   #    成本追踪（按模型计价 + 预算）
│   └── config.py         #    配置系统（YAML + 环境变量）
│
├── multimodel/           # 🌐 多模型混合调度（v0.3.0）
│   ├── registry.py       #    ModelRegistry + KeyRotator（多Key轮询）
│   ├── router.py         #    TaskRouter（分类路由 + 策略）
│   ├── dispatcher.py     #    ModelDispatcher（重试/降级/负载均衡/日志）
│   ├── collaborator.py   #    MultiModelCollaborator（拆解/并行/校验/汇总）
│   ├── scheduler.py      #    HybridScheduler（统一门面）
│   └── INTEGRATION_GUIDE.md
│
├── memory/               # 🧠 四层记忆
│   ├── working_memory.py · episodic.py · semantic.py · procedural.py
│   ├── neocortex.py      #    新皮层聚合（混合召回）
│   └── subconscious_loop.py
│
├── skills/               # 🔧 58 个技能（自动发现）
│   ├── registry.py · code/data/testing/research/devops_skills.py
│   └── core/             #    通用 + 多模态 + 创意 + 文件系统 + 执行
│
├── domains/              # 🌍 领域包（adas / general）
│   └── adas/             #    14 技能 + 36 场景 + 3 人格 + CoPilot
│
├── orchestration/        # 🔄 多 Agent 编排（DAG + 8 工作流）
├── safety/               # 🛡️ 5 层管线（参考实现，未接入生产）
├── channels/             # 🔌 CLI / Gateway / MCP（平台适配器为 stub）
├── hooks/                # 🪝 41 钩子事件 × 4 类型
├── persona/              # 👤 人格系统（→ domains/adas 的兼容 re-export）
├── experimental/         # 🧪 自我进化 / 自我意识（⚠️ 非生产就绪）
├── examples/ · tests/ · docs/ · config/
```

<br>

## 📊 状态与诚实清单

| 指标 | 值 |
|---|---|
| 测试 | **839 passing** / 848（9 skipped） |
| 执行模式 | 3（`run` / `run_react` / `run_hybrid`） |
| 技能 | 58 个注册类（自动发现） |
| 多模型 | OpenAI / Claude / DeepSeek / 通义千问 / Ollama / LM Studio（OpenAI 兼容；可选 LiteLLM 网关） |
| Python | 3.10+ |
| 状态 | **Alpha — 内部试点就绪** |

**✅ 真实可用**：三种执行模式 · 多模型路由+协作 · 四层记忆+跨会话召回 · 成本追踪 · 安全门控 · 50+ 真实技能 · 多 Agent 编排

**⚠️ stub / 需补全**：`web_search` / `audio_transcribe` / `language_detector`（占位）· channels 平台适配器（飞书/钉钉/Telegram 缺真实 HTTP 实现）· 语义召回（需自带 embedder）

**❌ 不适用**：量产车辆部署 · 安全关键决策 · 任何影响车辆控制的路径 · 合规认证

<br>

---

<div align="center">

### Nonull = 非空 = Never Null

<i>每一个决策都有依据，不空想。<br>
每一次响应都有内容，不空答。<br>
每一个动作都经过安全验证，不出错。</i>

<b>如临深渊，如履薄冰。</b> — 《诗经·小雅》

</div>

---

<h2 id="-english">🌐 English</h2>

**Nonull** is a domain-agnostic AI agent framework with three interchangeable execution modes, intelligent multi-model scheduling, a four-layer memory system, and 58 auto-discovered skills.

**Three execution modes** (one agent instance, shared LLM/cost/memory/safety):
- `run(task)` — structured 5-phase loop (Plan → Reason → Act → Reflect)
- `run_react(task, tools)` — ReAct loop where the LLM owns control flow (async tools, circuit-breaker, timeout)
- `run_hybrid(task)` — multi-model scheduling: auto-route by complexity/privacy/cost/speed, multi-model collaboration for super-complex tasks

**Multi-model scheduling** (`multimodel/`): multi-vendor models (OpenAI / Claude / DeepSeek / Qwen / Ollama / LM Studio) via a pure-httpx OpenAI-compatible client — **no hard LiteLLM dependency**; point `base_url` at a LiteLLM gateway if you want one. Auto routing + multi-key rotation + retry/fallback + multi-model collaboration (decompose → parallel → cross-check → synthesize).

**Memory**: four layers (working / episodic / semantic / procedural) + Neocortex coordinator + background subconscious loop. Episodic has **real Ebbinghaus decay**; recall is **hybrid keyword + n-gram vector** (not transformer-semantic — bring your own `embedder=` for that). Cross-session continuity verified end-to-end.

**Safety**: `core/safety.py` `SafetyGuardian` — a 3-step advisory gate (regex blocklist → command allowlist → context-risk scoring). **Advisory only, no ASIL.**

**Honest status**: 839 tests passing. Stubs to flag: `web_search` / `audio_transcribe` / `language_detector` (placeholders), platform channel adapters (Feishu/DingTalk/Telegram lack real HTTP impl), semantic recall (needs a user-supplied embedder). **Not for production vehicle deployment or safety-critical decisions.**

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=waving&height=120&color=gradient&customColorList=12,20,24&section=footer"/>
</div>
