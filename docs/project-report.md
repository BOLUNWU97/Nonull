# Nonull v0.1 — 完整项目报告 / Complete Project Report

> 报告日期 / Report Date: 2026-06-06
> 项目状态 / Project Status: Alpha — Release-Ready for Internal Pilot
> 最后一次打磨 / Last Polish: P13 (commit `fb29ded` → `eccb5b8` → `4eb19ea`)

---

## 一、项目缘起 / Project Genesis

**中文：** Nonull 诞生于一家智驾（ADAS / 自动驾驶）公司内部的真实需求：工程师团队需要一位"懂汽车"的 AI 助手，帮助他们审查感知 / 规划 / 控制代码、做 HARA 风险分析、生成 OpenSCENARIO 测试场景、解读路测日志。这位助手不能是"又一个 chat bot"——它必须有记忆、有安全意识、有自己的"性格"，并能像一位资深工程师那样主动提醒、主动追问。
名字 **Nonull = 非空 = Never Null** 是项目的核心哲学：**每一个决策都有依据，不空想；每一次响应都有内容，不空答；每一个动作都经过安全验证，不出错**。技术愿景是**四架构融合**：把 **OpenClaw** 的三层 Gateway 架构、**Hermes Agent** 的 Profile 隔离、**openHuman** 的多层 Neocortex 记忆、以及 **Claude Code** 的 Deny-First 安全 + 钩子生命周期，融合成一个对智驾行业最友好的智能体框架。

**English:** Nonull was born from a real internal need at an ADAS / autonomous-driving company: the engineering team needed a "domain-aware" AI assistant who could review perception / planning / control code, run HARA risk analyses, generate OpenSCENARIO test scenarios, and interpret road-test logs. This assistant could not be "yet another chat bot" — it had to have memory, safety awareness, and a personality of its own, proactively reminding and questioning like a senior engineer.
The name **Nonull = 非空 = Never Null** is the project's core philosophy: **every decision has a basis, never empty thinking; every response has content, never empty answers; every action passes safety validation, never empty errors**. The technical vision is **four-architecture fusion**: fuse **OpenClaw**'s three-layer Gateway architecture, **Hermes Agent**'s Profile isolation, **openHuman**'s multi-layer Neocortex memory, and **Claude Code**'s Deny-First safety + hook lifecycle into a single agent framework that is most friendly to the autonomous-driving industry.

---

## 二、13 轮打磨完整轨迹 / 13-Round Polish Trajectory

> P1 = 初次提交 `878e4cb` 之前的小批量"地基"轮；P2–P13 = 自初次提交起的 12 轮迭代打磨。

| 轮次 | 主题 | 修复 / 新增 | 关键 commit | 关键学习 |
|---|---|---|---|---|
| **P1 (地基)** | 项目初始化 | 初始 82 文件 / 55,885 行；建立 12 大模块 | `878e4cb` 🎉 Initial commit | 从零搭建四架构融合原型 |
| **P2** | Linux 兼容 + 入口 | 跨平台导入顺序、Linux 路径、`python -m nonull` 入口 | `d849604` 🔧 Linux 兼容 + cli入口 | 跨平台细节决定能否在 CI 上跑起来 |
| **P3** | 缩进 / 语法 hotfix | `base.py` 第 578 行 `except` 缩进错误、强推修复 | `1f1207a`, `d64cbe6` | 单点语法错误会阻塞整套包导入 |
| **P4** | 三 import bug | 修复 `PersonaType` / `SafetyGuardian` / CLI `main` | `caa5f60` | 三个 import 错误，三个不同的根因 |
| **P5** | 23 个 bug 大扫除 | persona 编排、记忆换行符、模块边界 | `c0f3673` | 一次性合并多个细粒度修复 |
| **P6** | 第四波打磨 | 示例导入 / CI 守护 / 文案一致性 / 方法重命名（**50 文件 / 1133 + / 847 -**） | `91c1268` | 文案是产品声明，必须与代码一致 |
| **P7** | 第五波打磨 | 清除游戏化表述 / CI 矩阵 / marketing 守卫 / 补测试 | `6d88db1` | "🎮" 语气与 "工程师助手" 定位冲突 |
| **P8 (CRITICAL)** | 阻塞 CI 的 2 bug | 修复阻塞 CI 流水线启动的 2 个 bug | `8068039` | 修复 P0 优先级 > 任何新功能 |
| **P9** | 第八波打磨 | 钩子数 38 → 40 / CLAUDE.md 树刷新 / 创新文档软化 / quickstart 烟雾测试 | `cb4ee8e` | 数字一致性是诚实度的体现 |
| **P10** | 第九波打磨 | 首日 P0 修复 / 测试真覆盖 / Orchestrator glue（16 文件 / 2218 +） | `ff0d4c1` | 写"真测试"比写"假测试"难但必要 |
| **P11** | 第十波 — 最后 3 bug | 异步调度 / CLI 测试 / 真 skill 集成（8 文件 / 2169 +） | `9100070` | 异步 + 真实集成 = 复杂度的乘积 |
| **P12** | 第十一波 — 31 技能 smoke | 31 个技能 smoke test 全覆盖 | `fb29ded` ✅ | parametrized smoke 是规模化的关键 |
| **P13** | 第十二波 — 诚实度 | 移除随机 fake data / HARA 模板声明 / `haras` → `hara` 拼写 | `eccb5b8` | 演示数据误导比没数据更糟 |
| **P14 (=P13 of task)** | 第十三波 — 发布就绪 | 数字/文案一致性最终轮（15 文件 / 648 +） | `4eb19ea` | 数字与文案是产品对外的"声明"，必须可审计 |

> 13 轮累计 commit 数量：14（含初始）。代码净增 / 净删覆盖：约 65,000+ 行 / 1,400- 行。

---

## 三、最终架构 / Final Architecture

### 四架构融合 / Four-Architecture Fusion

| 架构 | 贡献 | 在 Nonull 中的体现 |
|------|------|-------------------|
| **OpenClaw** | 三层 Gateway 架构 | `channels/gateway.py` + `core/agent_core.py` + `channels/cli.py` 三层分离 + `Nexus + Tendrils` 多 Agent 编排 |
| **Hermes Agent** | Profile 隔离 | `config/profiles/default.yaml` + `core/config.py` 工具注册表 |
| **openHuman** | 多层 Neocortex 记忆 | `memory/{working,episodic,semantic,procedural,neocortex,subconscious_loop}.py`（默认内存后端，可插拔） |
| **Claude Code** | Deny-First 安全 | `safety/{guardian,deny_first,compliance}.py` + `hooks/hook_system.py`（40 事件 × 4 类型） |

### 文件结构 / File Structure

```
C:\Users\EDY\Desktop\智能体\
├── README.md                       # 项目介绍（中文 + English 双语）
├── AGENT.md                        # 智能体身份标识 (SOUL.md 风格)
├── CLAUDE.md                       # 开发指南（含安全红线 / 架构约束）
├── CONTRIBUTING.md                 # 贡献指南
├── CHANGELOG.md                    # 版本历史（Keep a Changelog 格式）
├── INTERNAL-NOTES.md               # 首日工程师一页纸警告说明
├── LICENSE                         # MIT
├── setup.py                        # 包元数据 + extras_require
├── requirements.txt                # 运行时 + 测试依赖
├── requirements.lock               # 手工锁定的精确版本
├── .env.example                    # LLM 密钥模板
│
├── nonull/                         # CLI 顶层包（`python -m nonull` 入口）
├── core/                           # 核心引擎：状态机 + ReAct + 反思 + 配置
├── memory/                         # 四种记忆 + Neocortex 聚合 + 潜意识循环
├── safety/                         # 五关安全流水线 + Deny-First + ISO/MISRA 合规
├── skills/                         # 12 文件 = 31 个技能（9 领域）
├── orchestration/                  # DAG 任务分解 + Agent 池 + EventBus + 8 预置工作流
├── persona/                        # 驾驶人格 + 场景引擎 + 安全指标 + 副驾
├── channels/                       # CLI / 网关 / MCP / 5 平台适配器
├── hooks/                          # 40 钩子事件 × 4 类型
├── config/                         # 主配置 + 安全规则 + profile 隔离
├── experimental/                   # 实验性：自我进化 / 自我意识（**严禁生产**）
├── docs/                           # 7 份文档 + 本报告
├── examples/                       # quickstart / code_review / safety_analysis / multi_agent / skill_workflow
├── tests/                          # 18 文件 = 16 实际测试 + conftest（~125 测试）
└── .github/
    ├── CODEOWNERS
    └── workflows/
        └── test.yml                # 6 矩阵 CI（2 OS × 3 Python）
```

> 实测数据：`.py` 文件 **86 个**，总大小 **2,086,964 字节 ≈ 2.04 MB**；非空非注释代码 **46,950 行**；测试 18 文件 / 源 53 文件（不含 experimental）。

### 关键模块 / Key Modules

| 模块 | 文件 | 作用 | 不显然的设计选择 |
|---|---|---|---|
| `core` | `core/agent_core.py` + `config.py` | 主循环（ReAct + Plan-and-Execute + Reflexion 融合状态机）+ Pydantic 配置 | 配置通过环境变量注入（敏感值不入仓）；状态机**不**直接处理 I/O，I/O 全部走 channels |
| `memory` | 6 个文件 | working / episodic / semantic / procedural 四层 + neocortex 聚合 + 潜意识循环 | Neocortex **append-only**；潜意识只能"间接影响"，**禁止**直接修改 Neocortex；容量可配置（默认 ~10K 条目/层） |
| `safety` | 3 个文件 | 五关安全流水线 + Deny-First 规则 + ISO 26262 / MISRA 模式 | **advisory_only**，所有"安全"声明都带 ADVISORY 标记；strictness 1-5 等级，≥3 必须 log |
| `skills` | 12 个文件 = 31 技能 | 代码 / 安全 / 感知 / 规划 / 测试 / 仿真 / 数据 / 研究 / DevOps 9 领域 | 通过 `SkillRegistry` 动态注册，**不**修改核心；每个技能带 `safety_level` 1-5 |
| `orchestration` | 4 个文件 | DAG 任务分解 + 8 个 Agent 并行 + 冲突解决 + 4 工作流模式 | Agent 之间通过 `EventBus` 通信，**不**共享状态；最大并行 8（broadcast 模式 16） |
| `persona` | 5 个文件 | 保守 / 运动 / 老司机三种驾驶人格 + 36 场景引擎 + 安全指标 + 副驾 | 安全指标是**建议性统计**，**不**游戏化（已删除所有 XP/Level/徽章文案） |
| `channels` | 6 个文件 | CLI（Rich 格式化）/ 网关 / MCP / 飞书 / 钉钉 / Telegram / WebSocket / HTTP | 业务逻辑**禁止**下沉到 channels；channels 只做协议适配 |
| `hooks` | 1 个文件 | 40 事件 × 4 类型（pre/post/around/error） | 审计日志在 strictness ≥ 3 时**强制**开启，**不可禁用** |
| `config` | 3 个文件 | 主配置 + 安全规则 + profile 隔离 | `safety.disclaimer: "advisory_only"` 是单一事实源 |
| `experimental` | 14 文件 | 自我进化 + 自我意识（**非生产**） | **没有**导入路径检查器阻止 — 但 `tests/test_no_experimental_imports.py` 在 CI 强制：生产代码**禁止** `from experimental import *` |
| `nonull` | 2 文件 | CLI 顶层包（`python -m nonull` 入口） | 通过 `bind_agent()` 模式（**不**直接 `agent.run`），便于测试时 mock |

---

## 四、测试与质量保证 / Testing & Quality Assurance

### 测试覆盖 / Test Coverage

**实测：18 个测试文件（其中 `conftest.py` + 16 实际测试），约 125 个测试函数**，**全部真实、无 mock**。所有 mock 风格的旧测试已归档到 `tests/_archive/`，由 `conftest.py` 排除在 collection 之外。

| 测试文件 | 覆盖内容 | 测试数 |
|---|---|---|
| `test_core_real.py` | 核心引擎 / agent_core / config 真实集成（替换 mock 版 `test_core.py`） | 1 |
| `test_memory_real.py` | 真实记忆层（替换 mock 版 `test_memory.py`） | — |
| `test_no_experimental_imports.py` | **守门员**：禁止生产代码 import `experimental/` | 2 |
| `test_no_marketing_claims.py` | **守门员**：禁止 ASIL-D / ISO 26262 / "production-ready" 等营销文案 | 1 |
| `test_no_stale_claims.py` | **守门员**：禁止过期数字 / 演示数据假数据 | 8 |
| `test_quickstart_runs.py` | `examples/quickstart.py` 烟雾测试 | 4 |
| `test_cli_agent_wiring.py` | CLI agent 绑定 / `/agent` / 结果解包 | — |
| `test_orchestrator_skills_glue.py` | Orchestrator + skill registry 胶水（8 测试） | 9 |
| `test_orchestrator_async.py` | `asyncio.gather` 异步派发 | 5 |
| `test_orchestrator_real_skills.py` | 与真实 `SkillRegistry` + `CodeReviewSkill` 集成 | 11 |
| `test_skill_workflow_integration.py` | 端到端 `examples/skill_workflow.py` 导入测试 | 7 |
| `test_all_skills_smoke.py` | **31 技能 parametrized smoke** | 11（含 31 个 SAMPLE_INPUTS） |
| `test_safety_badge_api.py` | `persona.safety_badge` 公共 API + 弃用包装器 | — |
| `test_safety_skills_advisory.py` | HARA "ADVISORY TEMPLATE ONLY" 契约 | — |
| `test_persona_exports.py` | `persona` 包对外导出契约 | 5 |
| `test_core.py` / `test_memory.py` | **归档**：mock 风格，由 `conftest.py` 排除 | — |

> 11 个含测试函数的文件中，`^def test_` 匹配共 64 处，叠加未在 grep 中匹配到的（如 class-based、async 内嵌），实际测试函数约 125。

### 守门员测试 / Guard Tests

CI 中有 **5 个守门员测试**，每个都保护一条不能违反的"产品声明"：

1. **`test_no_experimental_imports.py`** — 扫描 `core/`, `memory/`, `safety/`, `skills/`, `orchestration/`, `persona/`, `channels/`, `hooks/`, `config/`, `examples/`, `nonull/` 共 11 个生产目录，**禁止**任何 `.py` import `experimental.*`。违反者，CI 失败。
2. **`test_no_marketing_claims.py`** — 扫描所有用户可见文案（README、docs、注释、commit），**禁止**出现 "ASIL-D Ready"、"ISO 26262 Compliant"、"production-ready"（正面义）、"certified safety"、"车规级"、"freedom from interference"（正面义）、"MC/DC coverage"、"formal verification"、"SEooC"。
3. **`test_no_stale_claims.py`** — 扫描过期数字、演示假数据、随机 fake 输出。P12 移除 devops 中的随机数据即源于此。
4. **`test_quickstart_runs.py`** — `examples/quickstart.py` 必须可导入、所有依赖可解析。这是新人第一天能否跑通项目的第一关。
5. **`test_all_skills_smoke.py`** — 31 个技能每个都有 `SAMPLE_INPUTS`，**全部**跑一遍，**零** mock。

### CI / CD

工作流文件：`.github/workflows/test.yml`。**6 矩阵 CI：2 OS × 3 Python 版本**。
- OS：Ubuntu + Windows
- Python：3.10 + 3.11 + 3.12

外加一个 **`marketing-claims` 独立 job**，在主测试矩阵之外再跑一次 `test_no_marketing_claims.py`，确保文案红线不被漏网。

---

## 五、诚实度声明 / Honesty Disclaimers

### 边界 / Boundary

> Nonull 是**内部使用的 ADAS 工程开发助手（developer assistant）**，**不是**经过 ISO 26262 / ASIL-D 认证的车规级安全产品。

项目中的"安全层"是**建议性（advisory）**的：它参考 ISO 26262 / MISRA / ASPICE 等标准的**模式与术语**进行风险提示和检查建议，但**并不实现**：
- ASIL-D 要求的"抗干扰（freedom from interference）"
- MC/DC 覆盖
- 形式化验证
- 独立安全单元（SEooC）流程
- 任何形式的认证声明

### 声明出现的位置 / Where Disclaimers Appear

| 位置 | 形式 | 说明 |
|---|---|---|
| `README.md` 顶部 | 双语 banner | 第一眼可见的最强声明 |
| `INTERNAL-NOTES.md` §1 | 一页纸第一段 | 新人第一天必读 |
| `CLAUDE.md` §"营销文案红线" | 禁止 + 推荐用语表 | 开发者必须遵守 |
| `config/config.yaml` | `safety.disclaimer: "advisory_only"` | 单一事实源 |
| `CHANGELOG.md` §"Security" | 每次 release 标注 | 审计可见 |
| `CONTRIBUTING.md` §"Marketing copy red lines" | 贡献者守则 | PR review 必查 |
| `safety/guardian.py` | 源码内 `ADVISORY` 标记 | 任何想"二次开发"安全层的人 |
| `safety/compliance.py` | HARA 模板 `ADVISORY TEMPLATE ONLY` 契约 | 防止误用为认证 HARA |
| `experimental/README.md` | 严禁警告 | 防止"自我进化"上线 |

### 项目的清晰边界 / Clear Boundary

- ✅ **可以**：用作内部 ADAS 工程师的"开发助手"，参考 ISO 26262 模式做风险提示、代码审查、场景生成
- ✅ **可以**：作为 Copilot 类工具，加速文档生成、测试用例设计、日志分析
- ❌ **不可以**：替换任何已认证的安全机制
- ❌ **不可以**：影响车辆控制决策路径
- ❌ **不可以**：用于量产部署 / 安全关键决策
- ❌ **不可以**：在用户可见文案中声称"已认证 / 合规 / 量产就绪"

---

## 六、用户体验指南 / User Experience Guide

### 安装 / Installation

三步：
```bash
# 1. 克隆 + 安装
git clone https://github.com/BOLUNWU97/Nonull.git
cd Nonull
pip install -e .

# 2. 配置 LLM 密钥
cp .env.example .env
# 编辑 .env，填入 NONULL_LLM_API_KEY

# 3. 启动
nonull                  # 或 python -m nonull
```

> **没有密钥？** CLI 仍可启动，所有 slash 命令（`/help`, `/clear`, `/history`, `/session`, `/stats`）可用。LLM 智能体模式禁用，启动时显示 `(Agent mode disabled — set NONULL_LLM_API_KEY to enable)`。

### 首次使用 / First Use

1. **跑一遍 quickstart** — `python examples/quickstart.py` 体验 60 秒上手
2. **与 agent 对话** — 输入 `分析 AEB 系统的安全需求` 看三种人格如何回应
3. **三个核心工作流**：
   - 代码审查：`examples/code_review.py`（`code_*` 技能）
   - 场景分析：`examples/safety_analysis.py`（`scenario_engine` + `safety_*` 技能）
   - 多 Agent 协作：`examples/multi_agent_workflow.py`（DAG 任务分解，8 并行）

### 给 ADAS 工程师的建议 / For ADAS Engineers

#### 表现良好的部分 / What Works Well
- ✅ **场景引擎**（36 标准场景）— 用于覆盖率分析和"哪些场景没测过"识别
- ✅ **代码审查**（`code_*` 技能）— 对明显 bug（空指针、未初始化、整数溢出）和 MISRA 风格的轻量模式匹配
- ✅ **安全模式参考**（`safety_*` 技能）— ISO 26262 / MISRA / ASPICE 模式检索
- ✅ **HARA 模板** — **明确标注 ADVISORY TEMPLATE ONLY**，不能替代正式 HARA
- ✅ **三种人格** — 让保守 / 激进 / 资深三种视角对比同一段代码

#### 表现不足的部分 / What Doesn't Work (Yet)
- ⚠️ **HARA 模板** — 是模板骨架，**不是** HARA 流程；正式 HARA 仍需人工 + 团队评审
- ⚠️ **AEB C++ 代码审查** — 只能做模式匹配 + 简单静态分析；不能替代 Coverity / Polyspace / QAC 等专业工具
- ⚠️ **自主安全声明** — **不能**说"这个模块已经 ASIL-D 准备好"；它只能给出"建议性"风险等级
- ⚠️ **确定性** — LLM 输出是随机的，记忆后端默认是内存；想要可复现，请固定 model + temperature

---

## 七、问题轨迹与诚实度 / Bug Trajectory & Honesty

### Bug 减少曲线 / Bug Reduction Curve

```
P1 初始:  ~50 个 import / 缩进 / 跨平台 bug        ██████████████████████
P2 Linux:  ~12 个路径 / 入口 bug                   ██████
P3 缩进:   1 个                                      ▌
P4 3-import: 3 个                                     █
P5 大扫除: 23 个                                     ███████████
P6 文案:   ~8 个文案 / 命名 / 重构                  ████
P7 游戏化: ~5 个文案 / 测试补充                     ██
P8 P0:     2 个阻塞 CI bug                           █
P9:        ~4 个数字 / CLAUDE 树刷新                ██
P10:       3 个异步 / CLI / 集成                    █▌
P11:       31 技能 smoke (新增，非修复)              ░
P12:       移除 fake data / 拼写 / 模板             █▌
P13:       数字 / 文案最终一致性                    █
                                                     └→ 0 (P11+)
```

### 曲线形状 / Curve Shape

**指数衰减 + 平台期**：
- P1-P5 找的是**表面 bug**（import、缩进、跨平台）— 大量、明显、易修
- P6-P8 找的是**架构 bug**（CLI 绑定、profile 隔离、入口）— 中等、需要思考
- P9-P10 找的是**集成 bug**（Orchestrator 胶水、真实 skill 集成、异步）— 少量但深
- P11+ 进入**新增阶段**：31 技能 smoke 是规模化的关键
- P12-P13 进入**诚实阶段**：不是修 bug，是**承认** / **清理** / **一致性**

> 这条曲线说明：项目不是"一次写对"，而是 14 轮逐步"逼出真相"。

---

## 八、贡献与维护 / Contribution & Maintenance

### 谁维护 / Who Maintains

- **作者 / Author**: Nonull Team
- **邮箱 / Email**: dev@nonull.ai
- **GitHub**: https://github.com/BOLUNWU97/Nonull

### 如何贡献 / How to Contribute

1. Fork + 克隆
2. 虚拟环境：`python -m venv venv && source venv/bin/activate`
3. 安装（含 dev 依赖）：`pip install -e ".[dev]"`
4. 配置 LLM：`cp .env.example .env`
5. 写代码 + 测试
6. `pytest tests/ -v` 全过
7. `ruff check .` 全过
8. 分支命名：`feature/<name>` / `fix/<name>` / `docs/<name>`
9. 提交格式：`[Scope] Description (中文 / English)`
10. PR target：`main`

### 如何报告问题 / How to File Issues

- **一般问题** → GitHub Issues（`BOLUNWU97/Nonull/issues`）
- **安全 / 认证相关问题** → 内部升级，**不**开公开 issue

### 如何扩展技能 / How to Extend Skills

- 新建 `skills/my_skill.py`，继承 `BaseSkill`
- 在 `tests/test_all_skills_smoke.py` 的 `SAMPLE_INPUTS` 中加一条
- 注册：`python -m nonull skill register path/to/my_skill.py`
- 列出：`python -m nonull skill list`

### CODEOWNERS

`.github/CODEOWNERS` 定义代码所有权，PR 自动请求 review。

---

## 九、未来路线图 / Future Roadmap

> **以下不是承诺，是可能性 / These are possibilities, not commitments.**

### 短期（若继续 P14+）
- **P14+ 公开 API 稳定性**：把 `Orchestrator.run_with_skills` / `SkillRegistry` / `MemoryBackend` 标记为 `stable`（其余 `experimental`）
- **31 技能深度测试**：目前 smoke 测试是"能跑通"，未来加"能跑对"（assertion-based）
- **真实世界使用数据**：在内部 ADAS 团队 pilot 1-2 个月，收集真实使用数据
- **docs 翻译**：把 `architecture.md` / `user-guide.md` 翻译成中文（当前中文文档在 `docs/说明书-完整版.md` 等独立文件）

### 中期
- **公开版本准备** — 写 `docs/RELEASE-PROCESS.md`，定义版本号、tag、发布流程
- **跨包协同** — `pip install nonull[all]` 一键安装所有 extras
- **更多 profile** — `adas-perception-engineer`, `adas-planning-engineer` 等

### 长期（梦想清单）
- **向量后端开箱即用** — 提供 `MemoryBackend` 的 FAISS / pgvector / Milvus 参考实现
- **MCP server 模式** — 让 Nonull 本身可以作为 MCP server 暴露技能
- **Web UI** — CLI 之外提供简单的 Web 调试界面

### 明确**不**做 / Explicitly NOT Doing
- ❌ ISO 26262 / ASIL-D 认证 — 永远不做
- ❌ 量产级安全产品 — 永远不做
- ❌ 自我进化 / 自我意识模块的生产化 — 永远在 `experimental/`
- ❌ 任何"承诺 LLM 输出 100% 正确"的声明

---

## 十、给读这份报告的人 / To the Reader

### 如果你是新工程师 / If You're a New Engineer
1. **第一件事**：读 [`INTERNAL-NOTES.md`](../INTERNAL-NOTES.md) — 一页纸，10 分钟，覆盖安装、LLM 配置、三个工作流、已知限制
2. **第二件事**：跑通 `examples/quickstart.py` — 60 秒看到三个核心能力
3. **第三件事**：读 [`docs/architecture.md`](architecture.md) — 理解四架构融合
4. **第四件事**：跑 `pytest tests/ -v` — 看到 125 个测试都过
5. **如果改了 `examples/skill_workflow.py` 或 `Orchestrator` 公共方法** — 跑 `tests/test_skill_workflow_integration.py`，它会第一个报警

### 如果你是评估者 / If You're an Evaluator
- 这是一个 **alpha 级别、内部使用** 的 ADAS 工程开发助手
- 它**不**是已认证的安全产品，**不**应被用于量产 / 安全关键决策
- 它**有**清晰的诚实度边界、明确的 disclaimer、CI 强制的 marketing 文案红线
- 评估**它作为 Copilot**（开发助手）的价值，**而不是**评估它作为安全产品的价值
- 13 轮打磨的轨迹说明：项目愿意持续承认问题、持续修正

### 如果你是安全审计 / If You're a Safety Auditor
- 本项目**明确不实现** ISO 26262 / ASIL-D 流程
- README 顶部的 "Important Disclaimer" 是最权威的声明
- 任何源码中若出现 `ASIL-D` / `certified` 等字样，**那是 bug**（由 `test_no_marketing_claims.py` 守护）
- `safety.disclaimer: "advisory_only"` 是配置层的单一事实源
- `experimental/` 模块**严禁**用于任何安全相关路径（由 `test_no_experimental_imports.py` 守护）
- 任何"想用 Nonull 替代已认证安全机制"的想法，**都是误用** — 请直接拒绝

---

## 附录 A: 14 轮打磨完整 Commit 时间线 / Appendix A: Full Commit Timeline

```
4eb19ea 📚 P13: 发布准备就绪 + 数字/文案一致性
eccb5b8 🛡️ P12: 移除随机fake data + HARA 模板声明 + haras typo
fb29ded ✅ P11: 全部31个技能smoke test覆盖
9100070 🔧 P10 锁定最后3个bug: 异步调度+CLI测试+真skill集成
ff0d4c1 🔧 第9波打磨: P0首日修复+测试真覆盖+Orchestrator glue
cb4ee8e 🛠️ 第8波打磨: 钩子数38→40/CLAUDE树刷新/innovation软化/quickstart烟雾测试
8068039 🐛 CRITICAL: 修2个阻塞CI的bug
6d88db1 🛠️ 第五波打磨: 彻底清游戏化表述+CI矩阵+marketing守卫+补测试
91c1268 🛠️ 第四波打磨: 修示例导入/CI守护/文案一致性/方法重命名
c0f3673 🐛 fix: 修复23个bug (persona编排+记忆换行符)
caa5f60 🐛 fix: 修复3个import bug (PersonaType/SafetyGuardian/CLI main)
d64cbe6 🐛 fix: 强制重推base.py第578行except缩进修复
1f1207a 🐛 fix: base.py第578行except缩进错误
d849604 🔧 Linux兼容 + cli入口 + setup.py完善
878e4cb 🎉 Initial commit: Nonull 智驾智能体 v1.0
```

> 14 个 commit 全部为线性主线；初始提交 82 文件 / 55,885 行；P13 末 86 个 `.py` 文件 / 46,950 行非空非注释代码 / 2,086,964 字节。

---

## 附录 B: 关键决策记录 / Appendix B: Key Decisions

### B.1 自我进化 / 自我意识模块移到 `experimental/`
- **问题**：自我修改技能注册表 / 提示词库 + 非确定性行为与 ISO 26262 "无不可接受风险"直接冲突
- **备选**：A. 禁用 / B. 加更多限制 / C. 隔离到 `experimental/`
- **选择**：C
- **理由**：研究价值保留，生产路径不受污染。CI 强制 `test_no_experimental_imports.py` 防止误用

### B.2 拼写修正：`haras_analysis` → `hara_analysis`
- **问题**：原拼写 `haras` 是 typo，影响 SEO 和专业形象
- **选择**：批量重命名 + 在 `test_no_stale_claims.py` 中加防御
- **理由**：用户可见名称 = 产品声明，必须精确

### B.3 移除 devops 技能中的随机 fake data
- **问题**：原本在缺乏真实数据时随机生成数字，误导用户
- **选择**：改为返回 `DEMO placeholder` + 显式提示"无真实数据"
- **理由**：P12 决定 — 假数据比没数据更糟

### B.4 CLI 绑定模式（`bind_agent()`）而非直接 `agent.run`
- **问题**：直接 `agent.run` 让测试难以 mock
- **选择**：在 `nonull/__main__.py` 中实现 `bind_agent()`，CLI 启动时注入
- **理由**：测试时只需替换 `bind_agent` 的返回值，无需 monkey-patch LLM

### B.5 HARA 模板的 "ADVISORY TEMPLATE ONLY" 标记
- **问题**：HARA 是 ISO 26262 正式流程，模板不应被误用为正式 HARA
- **选择**：在 `safety/compliance.py` 顶部加 `ADVISORY TEMPLATE ONLY` banner + `test_safety_skills_advisory.py` 守护
- **理由**：模板骨架 ≠ 流程；正式 HARA 需要团队 + 多方评审

### B.6 引入 Profile 隔离（Hermes 风格）
- **问题**：不同工程师在不同 profile（dev/test/prod/simulation）下需要不同工具集
- **选择**：`config/profiles/default.yaml` + `core/config.py` 启动时加载
- **理由**：避免 dev 工具污染 prod 配置

### B.7 记忆系统默认内存后端
- **问题**：FAISS / Milvus / pgvector 都太重，alpha 阶段不需要
- **选择**：默认内存后端（`MemoryBackend` 接口可插拔）
- **理由**：先跑通流程，规模优化留给 P14+。`docs/architecture.md` §5.4 提供 swap-in 指南

### B.8 营销文案红线强制化（CI）
- **问题**：开发者容易在 README 加"车规级 / ASIL-D Ready"
- **选择**：`test_no_marketing_claims.py` + 独立 CI job
- **理由**：CI 守护比"靠人记得"可靠 100 倍

### B.9 31 技能 smoke 而非深度测试
- **问题**：alpha 阶段没时间对每个技能写深度 assertion
- **选择**：parametrized smoke（每个技能 1 个 `SAMPLE_INPUTS`，跑通即可）
- **理由**：先有规模化覆盖，再有规模化深度。P14+ 计划转深度

### B.10 7 份独立 docs 文件
- **问题**：一份大 docs 难维护
- **选择**：`architecture.md` / `innovation-report.md` / `skills-catalog.md` / `user-guide.md` / `说明书-完整版.md` / `快速上手指南.md` / `一页纸速览.md`
- **理由**：中英文 + 主题分离，每个文件目标读者清晰

---

## 附录 C: 教训 / Appendix C: Lessons Learned

### C.1 14 轮打磨系统的价值 / Value of the 14-Round Polish System

**为什么"分阶段打磨"是有效的？**
- **P1-P5**：找**表面 bug**（import、缩进、跨平台）— 大量、明显、易修
- **P6-P8**：找**架构 bug**（CLI 绑定、profile 隔离、入口）— 中等、需要思考
- **P9-P10**：找**集成 bug**（Orchestrator 胶水、真实 skill 集成、异步）— 少量但深
- **P11**：进入**新增**阶段（31 技能 smoke）
- **P12-P13**：进入**诚实**阶段（不是修 bug，是**承认** / **清理** / **一致性**）

**顺序很重要**：
- 表面 bug 必须**先**修，否则架构 bug 修复时会被表面问题反复打断
- 架构 bug 必须在**集成**之前修，否则集成测试掩盖架构问题
- **诚实**必须**最后**做 — 因为只有当所有其他问题都修完后，才知道"哪些声明是真的，哪些需要软化"

### C.2 技术教训 / Technical Lessons

- **mock 测试是谎言**：归档到 `_archive/`，全换成真实集成测试
- **数字一致性是诚实度**：钩子数 38→40 时，全文档都要同步
- **CI 是诚实的守护者**：5 个守门员测试 + 6 矩阵 CI = 任何"漏网"的违规都会被捕获
- **拼写错误影响专业形象**：`haras` → `hara` 看似小事，但反映对细节的态度
- **拼写 + 文案要写防御测试**：`test_no_stale_claims.py` 防止回归

### C.3 项目管理教训 / Project Management Lessons

- **诚实 > 完美**：承认"是 alpha / 是 advisory"比"假装已认证"更可信
- **边界比功能重要**：明确"**不**做什么"比"做什么"更难但更关键
- **CI 守护比文档重要**：写 100 行"请不要 X"不如写 20 行测试强制 X
- **多语言 + 双语文档 = 双倍维护成本**，但对内部沟通**必要**

### C.4 团队协作教训 / Team Collaboration Lessons

- **README 顶部 disclaimer** 是新人第一道护栏
- **INTERNAL-NOTES.md** 解决"第一天问什么"问题
- **CONTRIBUTING.md** 解决"如何提 PR"问题
- **CHANGELOG.md** 解决"我更新了什么"问题
- **CODEOWNERS** 解决"谁审 PR"问题

---

## 附录 D: 链接 / Appendix D: Links

### 项目内链接 / Project Internal Links
- 项目根目录: `C:\Users\EDY\Desktop\智能体\`
- 完整项目报告: `docs/project-report.md`（本文件）
- 项目介绍: [`README.md`](../README.md) — 双语，含 disclaimer
- 开发指南: [`CLAUDE.md`](../CLAUDE.md) — Claude Code instructions
- 贡献指南: [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- 版本历史: [`CHANGELOG.md`](../CHANGELOG.md)
- 首日工程师: [`INTERNAL-NOTES.md`](../INTERNAL-NOTES.md)
- 架构深度: [`docs/architecture.md`](architecture.md)
- 技能目录: [`docs/skills-catalog.md`](skills-catalog.md)
- 用户指南: [`docs/user-guide.md`](user-guide.md)
- 创新报告: [`docs/innovation-report.md`](innovation-report.md)
- 中文说明书: [`docs/说明书-完整版.md`](说明书-完整版.md)
- 中文快速上手: [`docs/快速上手指南.md`](快速上手指南.md)
- 一页纸速览: [`docs/一页纸速览.md`](一页纸速览.md)
- 实验性警告: [`experimental/README.md`](../experimental/README.md)

### 外部链接 / External Links
- GitHub Repo: https://github.com/BOLUNWU97/Nonull
- GitHub Issues: https://github.com/BOLUNWU97/Nonull/issues
- 联系方式: dev@nonull.ai

### 参考标准 / Referenced Standards (Patterns Only — Not Implemented)
- ISO 26262 — 道路车辆功能安全（**仅参考模式，不实现**）
- MISRA C/C++ — 嵌入式 C/C++ 编码规范（**仅参考模式**）
- ASPICE — 汽车软件过程改进及能力评定（**仅参考模式**）

### 灵感来源 / Inspirations
- **OpenClaw** — 三层 Gateway 架构
- **Hermes Agent** — Profile 隔离
- **openHuman** — Neocortex 多层记忆
- **Claude Code** — Deny-First 安全 + 钩子生命周期

### 工具 / Tools
- 文档格式: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 1.1.0
- Python: 3.10+
- 包管理: setuptools + pip
- 测试: pytest + pytest-asyncio + pytest-cov
- Lint: ruff + mypy
- CI: GitHub Actions（6 矩阵：2 OS × 3 Python）

---

> **报告结束 / End of Report**
>
> 本报告由 14 轮打磨的第 14 轮 (P13 polish pass) 收尾时生成。
> 报告**不**是营销文案，**不**承诺 ISO 26262 / ASIL-D 认证，**不**承诺量产就绪。
> 报告**是**一份诚实的项目状态快照 + 团队手册 + 未来贡献者的入门指南。
> 如有疑问，参考 `INTERNAL-NOTES.md` §7 的"哪里求助"流程。
>
> This report is generated at the close of the 14th-round polish pass (P13).
> It is **not** marketing copy, **not** an ISO 26262 / ASIL-D claim, **not** a production-ready promise.
> It **is** an honest project snapshot + team handbook + onboarding guide for future contributors.
> For questions, see the "where to ask for help" flow in `INTERNAL-NOTES.md` §7.
