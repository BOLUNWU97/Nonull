
<p align="center">
  <img src="https://img.shields.io/badge/Nonull-全领域智能体-Universal-FF6B35?style=for-the-badge&logo=autoprefixer&logoColor=white"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.3.0-blue?style=flat-square"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-green?style=flat-square&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square"/>
  <img src="https://img.shields.io/badge/tests-839%20passing-success?style=flat-square"/>
  <img src="https://img.shields.io/badge/Advisory%20Safety-orange?style=flat-square"/>
  <img src="https://img.shields.io/badge/multi--model-hybrid%20scheduling-FF6B35?style=flat-square"/>
  <img src="https://img.shields.io/badge/status-alpha-orange?style=flat-square"/>
  <img src="https://img.shields.io/badge/domains-ADAS%20%2B%20General-6C63FF?style=flat-square"/>
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
  🌍 通用领域 AI 智能体，内置智驾、通用技能、LLM 接入
</h3>

<p align="center">
  <i>Universal Domain AI Agent — with built-in ADAS, general-purpose skills, and LLM integration.</i>
</p>

<br>

---

<h2 align="center">✨ 一句话认识 Nonull ✨</h2>

<p align="center">
  <b>Nonull</b> 是面向<b>任意领域</b>的下一代 AI 智能体框架。<br>
  内置<b>智驾（ADAS）领域</b>与<b>通用领域</b>，自带 50+ 技能、四层记忆、五关安全、LLM 接入、Web UI、评估套件。<br>
  领域无关，<b>有记忆、有安全意识、有自己的性格</b>。
</p>

<br>

> **📌 重要声明 / Important Disclaimer**
>
> Nonull 是一个**内部使用的 ADAS 工程开发助手（developer assistant）**，**不是**经过 ISO 26262 / ASIL-D 认证的车规级（非车规级）安全产品。
>
> 本项目中的"安全层 / safety layer"是**建议性（advisory）**的：它参考 ISO 26262 / MISRA / ASPICE 等标准的**模式与术语**进行风险提示和检查建议，但**并不实现** ASIL-D 要求的"抗干扰（freedom from interference）"、"MC/DC 覆盖"、"形式化验证"、"独立安全单元（SEooC）流程"等条款。
>
> **请勿将本项目用于任何量产部署、安全关键决策，或替代经过认证的安全机制。**
>
> ---
>
> Nonull is an **internal ADAS engineering assistant** — **not** an ISO 26262 / ASIL-D product and **not** a certified safety product. The safety layer is **advisory only** (not certified safety) — it references ISO 26262 / MISRA / ASPICE patterns and terminology for risk hints, but does **not** implement ASIL-D requirements such as freedom from interference, MC/DC coverage, formal verification, or SEooC processes. **Do not use this project for production deployment, safety-critical decisions, or as a substitute for any non-certified, non-production-ready advisory reference. This is a pattern reference, not a certified safety mechanism.**

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

<h2 align="center">🌍 All Domains / 全领域</h2>

<p align="center">
  <b>Nonull is domain-agnostic.</b> ADAS is one of many built-in domains.<br>
  <b>Nonull 是领域无关的。</b> 智驾（ADAS）只是众多内置领域之一。
</p>

Each domain provides:
- Domain-specific skills
- Domain-specific personas (e.g., ADAS: Conservative/Sporty/Veteran)
- Domain-specific scenarios (e.g., ADAS: 36 driving scenarios)
- Domain-specific safety disclaimers

### Built-in Domains / 内置领域

| Domain | Status | Contents / 内容 |
|---|---|---|
| `general` | ✅ Always loaded | Neutral defaults, no domain-specific knowledge / 中性默认，无领域知识 |
| `adas` | ✅ Default-on | 13 ADAS skills, 36 scenarios, 3 personas, HARA templates / 13 个智驾技能，36 个场景，3 种人格，HARA 模板 |

### Adding Your Own Domain / 添加自定义领域

```python
from domains import DomainPackage, DomainMetadata

class MyDomain:
    @property
    def metadata(self):
        return DomainMetadata(name="my", display_name="...", description="...")

    def register(self, registry):
        # Register your skills
        registry.register_skill(MySkill())

    def get_safety_disclaimers(self):
        return ["My domain: not for clinical use."]
```

### Domain-Agnostic Skills (skills/core/)

21 skills that work for ANY domain:
- **Web (3)**: `web_fetch`, `web_search`, `link_extractor`
- **Data (4)**: `json_formatter`, `csv_parser`, `text_statistics`, `diff`
- **Code (3)**: `regex_tester`, `json_schema_generator`, `code_counter`
- **Documentation (3)**: `markdown_to_html`, `readme_skeleton`, `docstring_generator`
- **Translation (2)**: `language_detector`, `translation_prompt`
- **Utilities (4)**: `uuid_generator`, `hash`, `timestamp`, `base64`
- **Multimodal (7)**: `image_info`, `image_resize`, `image_base64`, `pdf_info`, `pdf_extract_text`, `audio_info`, `audio_transcribe`
- **Creative (3)**: `brainstorm`, `metaphor_generator`, `story_plot`
- **Productivity (2)**: `pomodoro_schedule`, `eisenhower_matrix`
- **Learning (3)**: `flashcard_generator`, `quiz_generator`, `spaced_repetition`

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
  <img src="https://img.shields.io/badge/12%20Slash%20Commands-Ready-success?style=flat-square"/>
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

<br>

---

<h2 align="center">🚀 三种执行模式 + 多模型混合调度（v0.3.0 新增）</h2>

<p align="center">
  同一个 <code>Nonull</code> 实例，三种可互换的执行模式，共享 LLM / 成本 / 记忆 / 安全。<br>
  <i>One agent instance, three interchangeable execution modes, sharing LLM / cost / memory / safety.</i>
</p>

<br>

| 模式 | 方法 | 适用场景 | 特性 |
|------|------|---------|------|
| 🧩 **结构化循环** | `agent.run(task)` | 复杂多步任务（需规划/反思/记忆召回） | 五阶段状态机 plan→reason→act→reflect + 恢复机制 |
| 🔁 **ReAct 循环** | `agent.run_react(task, tools)` | 工具驱动任务（LLM 自主选工具） | while 循环 + LLM 完全控制流 + async 工具 + circuit-breaker |
| 🌐 **混合调度** | `agent.run_hybrid(task)` | 任意任务（自动路由 + 超复杂协作） | 自动分类路由 + 多模型协作 + 多 Key 轮询 |

<br>

```python
from core import Nonull

agent = Nonull()

# 模式 1: 结构化认知循环
result = await agent.run("分析 AEB 系统的安全需求")

# 模式 2: ReAct 工具循环
result = await agent.run_react("算 15×23 再统计字数", tools=[calc, word_count])

# 模式 3: 多模型混合调度（自动选模型 + 超复杂任务多模型协作）
result = await agent.run_hybrid("帮我设计一个分布式限流方案")
print(result["schedule_mode"])   # "single" | "collaboration"
print(result["model_used"])      # 用了哪个/几个模型
```

<h3 align="center">🌐 多模型混合调度（<code>multimodel/</code>）</h3>

<p align="center">
  接入多厂商大模型，自动按任务复杂度/隐私/成本/速度路由，超复杂任务多模型协作。<br>
  <i>Multi-vendor models with automatic routing by complexity/privacy/cost/speed, plus multi-model collaboration.</i>
</p>

| 层 | 组件 | 职责 |
|---|---|---|
| **模型管理层** | `ModelRegistry` + `KeyRotator` | 多厂商注册（OpenAI/Claude/DeepSeek/通义千问 + 本地 Ollama/LM Studio）+ 多 Key 轮询 |
| **智能路由层** | `TaskRouter` | 简单→小模型 / 复杂→强模型 / 隐私→本地；质量/成本/速度策略 |
| **调用封装层** | `ModelDispatcher` | 多 Key 轮询 + 失败重试 + 模型降级 + 负载均衡 + 调用日志 |
| **多模型协作层** | `MultiModelCollaborator` | 超复杂任务：拆解 → 并行 → 交叉校验 → 汇总 |
| **统一门面** | `HybridScheduler` | 一个入口串联以上全部 |

- **不强依赖 LiteLLM**：内置 client 是纯 httpx 打 OpenAI 兼容端点，Ollama/LM Studio/DeepSeek/通义千问/LiteLLM/vLLM 一个 client 全覆盖。想用 LiteLLM 网关就把 `base_url` 指向网关，代码零改动。
- 完整文档见 [`multimodel/INTEGRATION_GUIDE.md`](multimodel/INTEGRATION_GUIDE.md)（架构图 / 配置 / 路由 / 分发 / 协作 / 接入 / 报错 7 节）。

<br>

---

<h2 align="center">🎯 核心功能一览</h2>

<br>

<div align="center">

| 模块 | 一句话描述 | 状态 |
|------|-----------|:----:|
| 🤖 **核心引擎** | ReAct + 规划 + 反思 融合状态机（三种执行模式可互换） | ✅ |
| 🌐 **多模型调度** | 多厂商接入 + 智能路由 + 多模型协作 + 多Key轮询 | ✅ 🆕 |
| 🧠 **记忆系统** | 工作/情景/知识/技能 四种记忆 + 潜意识 + 跨会话召回闭环 | ✅ |
| 🛡️ **安全卫士** | ISO 26262 模式参考 + Deny-First + 五关检查（建议性，非认证） | ✅ |
| 💰 **成本追踪** | 按模型计价 + 预算上限 + 调用日志 | ✅ 🆕 |
| 🔧 **50+ 个技能** | 31 个 ADAS 专属 + 19 个通用 (web/data/code/docs/translation/utilities) + 8 个创意 (brainstorm/pomodoro/flashcards/...) | ✅ |
| 🔄 **多Agent** | DAG 任务分解 + 8 个 Agent 并行 + 冲突解决 | ✅ |
| 👤 **驾驶人格** | 🛡️ 保守派 / 🚀 运动派 / 🧓 老司机 | ✅ |
| 🧠 **场景思维** | 36 个标准场景自动关联 + 覆盖率分析 | ✅ |
| 📊 **安全指标** | 安全指标记录与统计（建议性，非游戏化） | ✅ |
| 👋 **副驾模式** | 主动风险提醒 + 每日简报 | ✅ |
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

<h2 align="center">🏗️ Adding Your Own Domain (添加你自己的领域)</h2>

<p align="center">
  Nonull is <b>domain-agnostic</b>. ADAS is just one built-in domain. To add your own:
</p>

```python
# domains/my_domain/__init__.py
from domains import DomainPackage, DomainMetadata

class MyDomain:
    @property
    def metadata(self):
        return DomainMetadata(
            name="medical",
            display_name="医疗 / Medical",
            description="Medical domain (or whatever you want).",
            safety_profile="regulated-medical",  # 'advisory' | 'regulated-medical' | 'safety-critical'
        )

    def register(self, registry):
        # Register your skills/personas/scenarios
        from domains.my_domain.skills import MySkill
        registry.register_skill(MySkill())

    def get_safety_disclaimers(self):
        return ["Medical domain: not for clinical use without review."]
```

```python
# main.py
from domains import load_default_domains
reg = load_default_domains()
reg.deactivate('adas')  # turn off ADAS if you don't need it
# Or register your own:
reg.register(MyDomain())
reg.activate('medical')
```

That's it. Your domain's skills become available alongside (or instead of) the built-ins.

The built-in domains are:
- `domains/adas/` — 智驾 / ADAS (default)
- `domains/general/` — always-active fallback (cannot be deactivated)

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

<h2 align="center">🎨 Creative / Productivity / Learning Skills</h2>

<br>

<p align="center">
  Nonull 越来越像一个"next-gen 智能体"：除了 ADAS 专属技能和通用工具，
  它还配备了 8 个 <b>创意 / 效率 / 学习</b> 技能（来自 <code>skills/creative/</code>）。
</p>

<p align="center">
  <i>Beyond the 31 ADAS-specific skills and 19 general-purpose utilities,
  Nonull ships 8 additional <b>creative / productivity / learning</b> skills
  (<code>skills/creative/</code>) — making it feel like a next-gen agent.</i>
</p>

<br>

<div align="center">

| 分类 | 技能 | 用途 |
|------|------|------|
| 💡 **创意激发 / Ideation** | `brainstorm` | 用 7 种经典头脑风暴技术（SCAMPER、六顶思考帽、最坏想法、类比、Reversal、First Principles）针对主题生成创意 |
| 💡 **创意激发 / Ideation** | `metaphor_generator` | 为抽象概念生成隐喻 / 类比（"X is like ___ because both ___"） |
| 💡 **创意激发 / Ideation** | `story_plot` | 用 4 种叙事结构（Three-Act / Hero's Journey / Freytag / 起承转合）生成故事骨架 |
| ⏱️ **效率 / Productivity** | `pomodoro_schedule` | 把任务列表拆成 25 分钟番茄钟 + 5/15 分钟休息的节奏表 |
| ⏱️ **效率 / Productivity** | `eisenhower_matrix` | 把任务按"紧急/重要"四象限分类（Do / Schedule / Delegate / Eliminate） |
| 📚 **学习 / Learning** | `flashcard_generator` | 从一段文本中生成 N 张 Q&A 抽认卡（Anki 风格） |
| 📚 **学习 / Learning** | `quiz_generator` | 从一段文本中生成 N 道多选题（1 正确 + 3 干扰） |
| 📚 **学习 / Learning** | `spaced_repetition` | 为一组记忆项生成 Leitner 间隔重复复习计划（1/3/7/14/30/60/120 天） |

</div>

<br>

```python
# 5 秒钟上手 / 5-second start
from skills.creative.idea_skills import BrainstormSkill
from skills.creative.learning_skills import FlashcardGeneratorSkill

# 用 3 种头脑风暴技术为某个主题生成 5 个创意
result = BrainstormSkill().execute({"topic": "smart home for elderly", "count": 5})
for idea in result.data["ideas"]:
    print(idea)

# 把一段关于光合作用的文字切成 10 张抽认卡
cards = FlashcardGeneratorSkill().execute({
    "text": "Photosynthesis converts CO2 and H2O into glucose using sunlight.",
    "count": 10,
})
print(cards.data["instruction"])
```

<br>

---

<h2 align="center">🌍 Internationalization (i18n) / 多语言支持</h2>

<br>

<p align="center">
  Nonull 用户面字符串已支持中英双语切换，存放在 <code>i18n/__init__.py</code>。
</p>

```python
from i18n import t, set_lang

# 默认英文 / English by default
print(t("welcome"))            # "Nonull — Universal AI Agent"

# 切到中文 / Switch to Chinese
set_lang("zh")
print(t("welcome"))            # "Nonull — 通用 AI 智能体"
print(t("skills_loaded", n=8)) # "已加载 8 个技能"

# Per-call 覆盖 / Per-call override
print(t("welcome", lang="en")) # "Nonull — Universal AI Agent"
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
├── 📁 skills/                # 🔧 50 个技能 (31 ADAS + 19 通用)
│   ├── registry.py           #    动态注册中心
│   ├── code_skills.py        #    代码技能组
│   ├── safety_skills.py      #    (P15 移至 domains/adas/skills/)
│   ├── perception_skills.py  #    (P15 移至 domains/adas/skills/)
│   ├── planning_skills.py    #    (P15 移至 domains/adas/skills/)
│   ├── testing_skills.py     #    测试技能组
│   ├── simulation_skills.py  #    (P15 移至 domains/adas/skills/)
│   ├── data_skills.py        #    数据技能组
│   ├── research_skills.py    #    研究技能组
│   ├── devops_skills.py      #    DevOps 技能组
│   └── core/                 #    P16: 19 个通用领域无关技能
│       ├── web_skills.py          #    web_fetch / web_search / link_extractor
│       ├── data_skills.py         #    json_formatter / csv_parser / text_statistics / diff
│       ├── code_skills.py         #    regex_tester / json_schema_generator / code_counter
│       ├── documentation_skills.py #    markdown_to_html / readme_skeleton / docstring_generator
│       ├── translation_skills.py  #    language_detector / translation_prompt
│       └── utilities_skills.py    #    uuid_generator / hash / timestamp / base64
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
├── 📁 multimodel/            # 🌐 多模型混合调度（v0.3.0 新增）
│   ├── registry.py           #    模型注册表 + 多Key轮询 (KeyRotator)
│   ├── router.py             #    任务分类路由 (简单/复杂/隐私 + 策略)
│   ├── dispatcher.py         #    单模型分发 (重试/降级/负载均衡/日志)
│   ├── collaborator.py       #    超复杂任务多模型协作
│   ├── scheduler.py          #    HybridScheduler 统一门面
│   ├── litellm_config.yaml   #    LiteLLM 网关配置 (可选)
│   ├── nonull_models.yaml    #    模型注册配置
│   └── INTEGRATION_GUIDE.md  #    7 节完整集成文档
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
  <a href="docs/llm-setup.md">
    <img src="https://img.shields.io/badge/🔌-LLM%20Setup-00BFA5?style=for-the-badge"/>
  </a>
</p>

<br>

---

<h2 align="center">🧑‍💻 Internal use guide</h2>

<p align="center">
  First day on the team? Start with the one-page warning sheet:
  <a href="INTERNAL-NOTES.md"><b>INTERNAL-NOTES.md</b></a>.<br>
  It covers first install, LLM setup, the three workflows every new
  engineer uses (code review, scenario coverage, multi-agent),
  known limitations, and where to ask for help.<br>
  <i>Advisory only — does not replace the disclaimer above.</i>
</p>

<br>

The example `examples/skill_workflow.py` (one-shot AEB review) is
guarded by an end-to-end smoke test at
[`tests/test_skill_workflow_integration.py`](tests/test_skill_workflow_integration.py).
It imports the example, auto-discovers the real `SkillRegistry`,
verifies the `code_review` skill is present, instantiates the
`Orchestrator`, and pins the public
`Orchestrator.run_with_skills` signature. Run it with:

```bash
pytest tests/test_skill_workflow_integration.py -v
```

If you change `examples/skill_workflow.py` or the orchestrator's
public method shape, this test is the first thing CI will flag.

<br>

---

<h2 align="center">🔗 Project Links / 项目链接</h2>

<p align="center">
  <a href="CONTRIBUTING.md">
    <img src="https://img.shields.io/badge/📝-CONTRIBUTING-FF6B35?style=for-the-badge"/>
  </a>
  <a href="CHANGELOG.md">
    <img src="https://img.shields.io/badge/📜-CHANGELOG-6C63FF?style=for-the-badge"/>
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/⚖️-LICENSE-yellow?style=for-the-badge"/>
  </a>
  <a href="INTERNAL-NOTES.md">
    <img src="https://img.shields.io/badge/🧑‍💻-INTERNAL%20NOTES-00C9A7?style=for-the-badge"/>
  </a>
</p>

| File | Purpose | 用途 |
|------|---------|------|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development setup, code style, testing, PR process, marketing red lines | 开发环境、代码风格、测试、PR 流程、营销文案红线 |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history in [Keep a Changelog](https://keepachangelog.com/) format | [Keep a Changelog](https://keepachangelog.com/) 格式的发布历史 |
| [`LICENSE`](LICENSE) | MIT license terms | MIT 许可证条款 |
| [`INTERNAL-NOTES.md`](INTERNAL-NOTES.md) | One-page warning sheet for first-day engineers | 首日工程师一页纸警告说明 |

<p align="center">
  <i>All four files are advisory documentation. The binding safety
  disclaimer is at the top of this README.</i>
</p>

<br>

---

## 📊 Project Status (2026-06-16)

| Metric | Value |
|---|---|
| Tests passing | 839 / 848 (9 skipped — see CHANGELOG) |
| Execution modes | 3 — `run()` structured / `run_react()` ReAct / `run_hybrid()` multi-model |
| Multi-model | OpenAI / Claude / DeepSeek / 通义千问 / Ollama / LM Studio (via OpenAI-compatible client; optional LiteLLM gateway) |
| Skills | 50+ (31 ADAS + 19 general) |
| Python | 3.10+ |
| LLM | Any OpenAI-compatible endpoint (OpenAI / DeepSeek / MiniMax / Ollama / vLLM / LiteLLM) |
| Status | **Alpha — internal pilot ready** |

**Read this carefully:** Nonull is an **advisory** development assistant, not a certified safety product. It is suitable for:
- ✅ Internal ADAS engineering productivity
- ✅ Code review scaffolding
- ✅ Scenario planning assistance
- ✅ LLM integration demos

It is **NOT** suitable for:
- ❌ Production deployment in any vehicle
- ❌ Safety-critical decisions
- ❌ Any path that influences a vehicle control decision
- ❌ Compliance certification

See `docs/project-report.md` for the complete 14-round polish history and the real test report.

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
  <tr><td>🤖 Core Engine</td><td>ReAct + Plan-and-Execute + Reflexion fused state machine — 3 interchangeable modes: <code>run()</code> / <code>run_react()</code> / <code>run_hybrid()</code></td></tr>
  <tr><td>🌐 Multi-Model Scheduling</td><td>Multi-vendor models + auto routing (complexity/privacy/cost/speed) + multi-model collaboration + multi-key rotation (<code>multimodel/</code>)</td></tr>
  <tr><td>🧠 Memory System</td><td>Working/Episodic/Semantic/Procedural + Neocortex + cross-session recall (configurable capacity, default in-memory backend)</td></tr>
  <tr><td>🛡️ Safety Guardian</td><td>ISO 26262 pattern refs + Deny-First + 5-layer advisory pipeline (not certified)</td></tr>
  <tr><td>💰 Cost Tracking</td><td>Per-model pricing + budget cap + call logging</td></tr>
  <tr><td>🔧 50 Skills</td><td>31 ADAS-specific (Code/Safety/Perception/Planning/Testing/Simulation/Data/Research/DevOps) + 19 general-purpose (Web/Data/Code/Docs/Translation/Utilities) under <code>skills/core/</code></td></tr>
  <tr><td>👤 Driving Persona</td><td>Conservative 🛡️ / Sporty 🚀 / Veteran 🧓 — three characters</td></tr>
  <tr><td>🧠 Scenario Engine</td><td>36 built-in driving scenarios + coverage analysis</td></tr>
  <tr><td>📊 Safety Metrics</td><td>Safety metrics tracking (advisory, not gamified)</td></tr>
  <tr><td>🔌 Multi-Channel</td><td>CLI / API / MCP / Telegram / Feishu / DingTalk</td></tr>
</table>

<br>

> **Note**: Self-evolution and self-awareness modules are <b>experimental</b> and have been moved to <code>experimental/</code>. They are not wired into the production agent loop and must not be used in any safety-critical path. See <a href="experimental/README.md">experimental/README.md</a> for warnings.
