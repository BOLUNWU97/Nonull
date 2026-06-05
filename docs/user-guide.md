# Nonull 智驾智能体 — 用户手册 / User Manual

> **下一代自动驾驶 AI Agent 系统 — 融合四大主流架构，驱动智能驾驶安全未来**
> **Next-Gen Autonomous Driving AI Agent — Fusing Four Major Architectures, Driving the Future of Safe Intelligent Driving**

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/example/Nonull)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Type Hints](https://img.shields.io/badge/types-typed-blue)](https://www.python.org/dev/peps/pep-0484/)

---

## / 目录 / Table of Contents

1. [🌟 介绍 / Introduction](#-介绍--introduction)
2. [🏗️ 架构概览 / Architecture Overview](#️-架构概览--architecture-overview)
3. [✨ 核心功能 / Core Features](#-核心功能--core-features)
4. [🚀 快速开始 / Quick Start](#-快速开始--quick-start)
5. [📚 使用示例 / Usage Examples](#-使用示例--usage-examples)
6. [📋 技能目录 / Skills Catalog](#-技能目录--skills-catalog)
7. [⚙️ 配置指南 / Configuration Guide](#️-配置指南--configuration-guide)
8. [🔧 高级用法 / Advanced Usage](#-高级用法--advanced-usage)
9. [📊 工作流模式 / Workflow Patterns](#-工作流模式--workflow-patterns)
10. [🧪 测试 / Testing](#-测试--testing)
11. [🤝 贡献指南 / Contributing](#-贡献指南--contributing)
12. [📄 许可证 / License](#-许可证--license)

---

# 🌟 介绍 / Introduction

## 什么是 Nonull？/ What is Nonull?

**Nonull（智驾智能体）** 是一款专为智能驾驶（Autonomous Driving）领域设计的下一代 AI Agent 框架。它融合了 **OpenClaw**、**Hermes Agent**、**openHuman** 和 **Claude Code** 四大主流架构的核心设计理念，形成了一套统一、安全、可扩展、自我进化的智能体系统。

Nonull is a next-generation AI Agent framework purpose-built for the autonomous driving domain, fusing the core design philosophies of **OpenClaw**, **Hermes Agent**, **openHuman**, and **Claude Code** into a unified, secure, extensible, and self-evolving agent system.

### 名称由来 / The Story Behind the Name

> **非空 (Nonull) = Never Empty, Never Null**

"非空" 蕴含着双重含义：
- **Never Empty（永不空虚）**：智能体始终拥有丰富的记忆、知识和经验，以可配置容量的新皮层（Neocortex，默认 10K 条目/层，内存后端）为支撑，永不"大脑空白"。
- **Never Null（永不为空）**：在工程哲学上，系统中的每一个决策、每一次响应、每一行输出都必须有依据、有内容、有安全验证。拒绝 Null 指针，拒绝空响应，拒绝无意义的输出。

The name embodies a dual philosophy: never empty (empowered by a configurable Neocortex memory system, default in-memory backend) and never null (every decision has evidence, every output has meaning, every action is safety-validated — no null pointers, no empty responses, no meaningless outputs).

### 核心哲学 / Core Philosophy

```
Safety is the foundation of everything.   安全是一切的基石。
Every action is validated.                每一次行动都经过验证。
Every decision is reasoned.               每一个决策都有理有据。
Every failure is learned from.            每一次失败都转化为经验。
Every success is consolidated.            每一次成功都固化为知识。
```

**如临深渊，如履薄冰。** — 《诗经·小雅》

## 谁应该使用 Nonull？/ Who Is It For?

| 角色 Role | 场景 Use Case |
|-----------|---------------|
| **ADAS 工程师** / ADAS Engineers | 代码审查、架构分析、性能优化 |
| **功能安全工程师** / Safety Engineers | HARA、FMEA、FTA、安全案例生成 |
| **仿真测试团队** / Simulation Teams | 场景生成、测试用例设计、覆盖率分析 |
| **系统架构师** / System Architects | 架构评审、约束检查、合规评估 |
| **数据/ML 工程师** / Data & ML Engineers | 数据管道审查、质量分析和优化 |
| **项目经理** / Project Managers | 合规检查、缺陷分类、流程改进 |

---

# 🏗️ 架构概览 / Architecture Overview

## 四大架构融合 / Four-Architecture Fusion

Nonull 融合了四种业界领先的智能体架构设计理念，构建了一个强大而统一的系统：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Nonull 智驾智能体                                  │
│                     ─── Fusing Four Major Architectures ───                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           Fusion Core                                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │   │
│  │  │   OpenClaw   │  │ Hermes Agent │  │  openHuman   │  │ClaudeCode│ │   │
│  │  │ Triple-Layer │  │   Profile    │  │  Neocortex   │  │ Deny-    │ │   │
│  │  │ Gateway /    │  │   Isolation  │  │   10K/layer   │  │ First    │ │   │
│  │  │ Agents /     │  │   Tool Reg.  │  │   Memory +   │  │ Safety + │ │   │
│  │  │ Channels     │  │   Provider-  │  │ Subconscious │  │ Hooks +  │ │   │
│  │  │              │  │   Agnostic   │  │    Loop      │  │Subagents │ │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬─────┘ │   │
│  │         │                 │                 │               │        │   │
│  │         └─────────────────┴─────────────────┴───────────────┘        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                        │   │
│  │              ┌────────────────────────────────────────────┐            │   │
│  │              │       Core Agent Loop (State Machine)       │            │   │
│  │              │  IDLE → PLANNING → REASONING → ACTING →    │            │   │
│  │              │           → REFLECTING → COMPLETED          │            │   │
│  │              │               ↓            ↑               │            │   │
│  │              │          ERROR → RECOVERING →┘              │            │   │
│  │              └────────────────────────────────────────────┘            │   │
│  │                                                                        │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────────┐       │   │
│  │  │  Safety   │ │  Memory   │ │   Tool/   │ │ Orchestrator     │       │   │
│  │  │  Guardian │ │  System   │ │   Skill   │ │ (Nexus Pattern)  │       │   │
│  │  │ (5-Layer) │ │(openHuman)│ │ Registry  │ │ DAG Decompose    │       │   │
│  │  │           │ │Neocortex  │ │ (Hermes)  │ │ + Agent Pool     │       │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └──────────────────┘       │   │
│  │                                                                        │   │
│  │  ┌────────────────────────────────────────────────────────────┐       │   │
│  │  │               Hook System (38 Events, 4 Types)               │       │   │
│  │  └────────────────────────────────────────────────────────────┘       │   │
│  │                                                                        │   │
│  │  ┌────────────────────────────────────────────────────────────┐       │   │
│  │  │          Channels (CLI + Gateway + MCP + Platform)          │       │   │
│  │  └────────────────────────────────────────────────────────────┘       │   │
│  │                                                                        │   │
│  │  ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────┐   │   │
│  │  │  Self-Evolution      │ │  Consciousness       │ │  Profile     │   │   │
│  │  │  (Experience Mining, │ │  (SelfModel,         │ │  Isolation   │   │   │
│  │  │   Skill Genesis,     │ │   Curiosity,         │ │  dev/test/   │   │   │
│  │  │   Meta-Cognition)    │ │   Autonomy, Growth)  │ │  prod/sim    │   │   │
│  │  └──────────────────────┘ └──────────────────────┘ └──────────────┘   │   │
│  │                                                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  🚀 Nexus Tendrils Orchestration Pattern    🛡️ Advisory Safety Layer         │
│  🧠 Neocortex-Subconscious Hybrid Memory     🔄 Self-Evolution & Growth      │
│  🔌 Multi-Channel (CLI/Gateway/MCP/Platform) 📋 31 Domain Skills            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 架构融合详解 / Fusion Details

#### 1. OpenClaw — 三层架构 (Triple-Layer Architecture)

OpenClaw 提供了系统的骨架结构：

| 层级 Layer | 职责 Responsibility | 实现 Implementation |
|------------|---------------------|---------------------|
| **Gateway Layer** (网关层) | 请求路由、负载均衡、认证、限流 | `GatewayChannel`, `MessageQueue`, `RateLimiter` |
| **Agent Layer** (智能体层) | 技能注册、任务编排、子智能体管理 | `Orchestrator`, `AgentPool`, `SkillRegistry` |
| **Channels Layer** (通道层) | CLI、API、WebSocket、平台适配器 | `CLIChannel`, `MCPAdapter`, `TelegramAdapter` 等 |

Nexus Tendrils 模式：智能体的核心编排模式，支持将复杂任务递归分解为 DAG（有向无环图），
并行分配至多个子智能体执行，最后聚合结果。

#### 2. Hermes Agent — 配置隔离与工具注册 (Profile Isolation & Tool Registry)

Hermes Agent 贡献了灵活的配置和工具管理体系：

- **Profile Isolation** — 每个 profile (dev/test/prod/simulation) 拥有独立的 workspace、工具集、模型配置，切换时自动清空会话状态
- **Tool Registry** — 全局工具注册表 (`ToolRegistry`)，支持动态注册、发现和版本管理
- **Provider-Agnostic** — 支持 OpenAI、Anthropic、Azure、Ollama 等多种 LLM 提供商
- **Session Persistence** — 会话级别的上下文持久化，支持 Save/Load

#### 3. openHuman — 新皮层记忆系统 (Neocortex Memory)

openHuman 赋予了智能体接近人类的记忆架构：

- **Working Memory** (工作记忆/前额叶皮层) — 当前任务的短期信息存储，容量小，更新频繁
- **Episodic Memory** (情景记忆/海马体) — 具体事件和经验记录，支持 Ebbinghaus 遗忘曲线衰减
- **Semantic Memory** (语义记忆/新皮层) — 概念、知识和规则的存储，倒排索引加速检索
- **Procedural Memory** (程序性记忆/小脑) — 流程、技能和标准操作流程的存储
- **Neocortex Aggregate** — 统一记忆聚合层，跨记忆类型联合检索，默认 10K 条目/层，内存后端（可插拔 FAISS / Milvus / pgvector）
- **Subconscious Loop** (潜意识循环) — 后台周期性记忆整合、模式发现和洞察生成

#### 4. Claude Code — 安全与钩子系统 (Safety & Hook System)

Claude Code 的设计理念为 Nonull 提供了坚固的安全保障：

- **Deny-First Safety** (拒绝优先) — 所有操作默认拒绝，仅显式允许的动作可通过
- **5-Layer Safety Pipeline** — 工具预过滤 → 规则引擎 → 风险评分 → 上下文感知 → 执行后验证
- **Hook System** — 38 个生命周期钩子事件，4 种钩子类型 (SHELL/HTTP/LLM/AGENT)
- **Subagent Isolation** — 子智能体隔离执行，支持线程级和进程级隔离
- **Structured Output** — 结构化输出与工具调用约束

## 数据流 / Data Flow

```
User Input (CLI / API / Telegram / 飞书 / 钉钉 / WebSocket)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Gateway Channel                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │ Rate     │  │ Auth &   │  │ Session  │  │ Message Queue   │ │
│  │ Limiter  │  │ Allowlist│  │ Manager  │  │ (Priority)      │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Core (Nonull)                          │
│                                                                  │
│  1. PLANNING:  Decompose task → retrieve memory → build plan    │
│       │                                                          │
│       ▼                                                          │
│  2. REASONING: Analyze context → decide next action              │
│       │                                                          │
│       ▼                                                          │
│  3. ACTING:                                                     │
│       │                                                          │
│       ├─ [Safety Guardian Layer 1: Tool Pre-filter]             │
│       ├─ [Safety Guardian Layer 2: Deny-First Rules]            │
│       ├─ [Safety Guardian Layer 3: Risk Scoring]                │
│       ├─ [Safety Guardian Layer 4: Context Validation]          │
│       │                                                          │
│       ├── DENIED → Log violation, attempt recovery              │
│       └── APPROVED → Execute action via Tool/Skill Registry     │
│                                                                    │
│       ▼                                                          │
│  4. REFLECTING: Evaluate result → consolidate memory            │
│       │                                                          │
│       ├── Completed? → COMPLETED, return result                 │
│       └── Not done? → back to REASONING (ReAct loop)            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Output Channel (Rich CLI / API / Bot)          │
└─────────────────────────────────────────────────────────────────┘
```

## 项目结构 / Project Structure

```
Nonull/                              # 项目根目录
├── README.md                        # 项目概览（中英双语）
├── AGENT.md                         # 智能体身份标识 (SOUL 风格)
├── CLAUDE.md                        # Claude Code 项目指令
├── setup.py                         # Python 包安装配置
├── requirements.txt                 # Python 依赖
├── config/                          # 配置文件目录
│   ├── config.yaml                  # 默认配置文件
│   ├── safety_rules.yaml            # 安全规则配置 (45+ 规则)
│   └── profiles/                    # Profile 隔离配置
│       └── default.yaml             # 默认 Profile
├── core/                            # 核心框架
│   ├── __init__.py                  # 包初始化，公共 API 导出
│   ├── agent_core.py                # 主智能体循环 (状态机 + 安全 + 记忆 + 工具)
│   └── config.py                    # 配置系统 (YAML + Profile + 环境变量)
├── channels/                        # 多通道通信层
│   ├── __init__.py                  # 通道包初始化
│   ├── base.py                      # 通道基类、消息标准化、限流、重试
│   ├── cli.py                       # CLI 交互通道 (Rich REPL)
│   ├── gateway.py                   # 网关通道 (统一路由)
│   ├── mcp_adapter.py               # MCP (模型上下文协议) 适配器
│   └── platform_adapters.py         # 平台适配器 (Telegram/飞书/钉钉/WS/HTTP)
├── hooks/                           # 钩子系统
│   ├── __init__.py                  # 钩子包初始化
│   └── hook_system.py               # 38 事件 + 4 类型钩子系统
├── memory/                          # 记忆系统
│   ├── __init__.py                  # 记忆包初始化
│   ├── working_memory.py            # 工作记忆
│   ├── episodic.py                  # 情景记忆
│   ├── semantic.py                  # 语义记忆
│   ├── procedural.py                # 程序性记忆
│   ├── neocortex.py                 # 新皮层记忆聚合
│   └── subconscious_loop.py         # 潜意识循环
├── safety/                          # 安全系统
│   ├── __init__.py                  # 安全包初始化 (枚举、数据模型)
│   ├── deny_first.py                # Deny-First 规则引擎 (45+ 内置规则)
│   ├── guardian.py                  # 安全监护器 (5层流水线)
│   └── compliance.py                # 合规检查器
├── skills/                          # 技能系统
│   ├── __init__.py                  # 技能包初始化
│   ├── base.py                      # 基础技能框架 (基类、元数据、结果)
│   ├── registry.py                  # 技能注册中心 + 技能组合 (Pipeline/Fan-out)
│   ├── code_skills.py               # 代码技能组
│   ├── safety_skills.py             # 安全技能组
│   ├── perception_skills.py         # 感知技能组
│   ├── planning_skills.py           # 规划技能组
│   ├── testing_skills.py            # 测试技能组
│   ├── simulation_skills.py         # 仿真技能组
│   ├── data_skills.py               # 数据技能组
│   ├── research_skills.py           # 研究技能组
│   └── devops_skills.py             # DevOps 技能组
├── orchestration/                   # 多智能体编排
│   ├── __init__.py                  # 编排包初始化
│   ├── orchestrator.py              # Nexus 编排器 (DAG 分解 + 并行执行)
│   ├── agent_pool.py                # 智能体池 (能力匹配)
│   ├── communication.py             # 智能体间通信 (EventBus)
│   ├── workflows.py                 # 8 个预定义工作流
│   └── tests/                       # 编排测试
│       └── test_integration.py
├── experimental/                    # ⚠️ 实验性模块（非生产就绪）
│   ├── README.md                    # 警告与使用说明
│   ├── consciousness/               # 自我意识（实验性）
│   └── evolution/                   # 自我进化（实验性）
├── examples/                        # 使用示例
│   ├── quickstart.py                # 快速入门
│   ├── code_review.py               # 代码审查示例
│   ├── safety_analysis.py           # 安全分析示例
│   └── multi_agent_workflow.py      # 多智能体工作流示例
├── tests/                           # 测试套件
│   ├── test_core.py                 # 核心测试
│   ├── test_memory.py               # 记忆系统测试
│   ├── test_safety_badge_api.py     # SafetyBadge API + 弃用包装器
│   └── test_persona_exports.py      # persona 包对外导出契约
└── docs/                            # 文档
    ├── architecture.md              # 架构文档
    ├── skills-catalog.md            # 技能目录
    └── user-guide.md                # 用户手册（本文件）
```

---

# ✨ 核心功能 / Core Features

## 🤖 核心智能体循环 / Core Agent Loop

### ReAct + Plan-and-Execute + Reflexion 融合

Nonull 的核心循环融合了三种最先进的智能体范式：

```
                     ┌────────────────────────────┐
                     │          IDLE              │
                     │     等待任务输入             │
                     └────────────┬───────────────┘
                                  │ Task Input
                                  ▼
                     ┌────────────────────────────┐
            ┌───────│        PLANNING             │
            │       │   分解任务为子步骤           │
            │       │   检索语义/程序记忆          │
            │       └────────────┬───────────────┘
            │                    │ Plan Ready
            │                    ▼
            │       ┌────────────────────────────┐
            │       │        REASONING           │
            │       │   ReAct: 推理下一步动作     │
            │       │   结合工作记忆+上下文        │
            │       └────────────┬───────────────┘
            │                    │ Action Decision
            │                    ▼
            │       ┌────────────────────────────┐
            │       │    [Safety Guardian]       │
            │       │   5-Layer Safety Check     │◀── Deny-First
            │       └────────────┬───────────────┘
            │          ┌─────────┴──────────┐
            │          ▼                    ▼
            │    [PASS]                [BLOCKED]
            │          │                    │
            │          ▼                    ▼
            │       ┌────────────────────────────┐
            │       │         ACTING             │
            │       │  执行动作/调用工具/技能     │
            │       └────────────┬───────────────┘
            │                    │ Result
            │                    ▼
            │       ┌────────────────────────────┐
            │       │       REFLECTING           │◀── Reflexion
            │       │   评估结果，自我反思         │
            │       │   巩固经验到记忆            │
            │       └────────────┬───────────────┘
            │              ┌─────┴─────┐
            │              ▼           ▼
            │        [Completed]   [Need More]
            │              │           │
            │              ▼           └──→ back to REASONING
            │       ┌────────────────────────────┐
            │       │       COMPLETED            │
            │       │   返回最终结果              │
            │       └────────────────────────────┘
            │
            │       ┌────────────────────────────┐
            │       │         ERROR              │
            └───────│   自动错误恢复机制          │
                    │   ERROR → RECOVERING →     │
                    │   → REASONING (重试)        │
                    └────────────────────────────┘
```

**状态机 / State Machine:**

```python
from enum import Enum

class AgentState(str, Enum):
    # 基础状态 / Base States
    IDLE = "idle"                # 空闲 / Idle
    PLANNING = "planning"        # 规划中 / Planning
    REASONING = "reasoning"      # 推理中 / Reasoning
    ACTING = "acting"            # 执行中 / Acting
    REFLECTING = "reflecting"    # 反思中 / Reflecting
    COMPLETED = "completed"      # 已完成 / Completed

    # 异常状态 / Exception States
    ERROR = "error"              # 错误 / Error
    RECOVERING = "recovering"    # 恢复中 / Recovering

    # 子智能体状态 / Subagent States
    SPAWNING = "spawning"               # 生成子智能体
    WAITING_SUBAGENT = "waiting_subagent" # 等待子智能体
```

**异步/同步双模式:**

```python
import asyncio

# 异步模式 (推荐) / Async mode (recommended)
result = await agent.run("Analyze AEB system requirements")
print(result["output"])

# 同步模式 / Sync mode
result = agent.run_sync("Analyze traffic situation")
print(result["output"])
```

**错误恢复机制:**

- 自动检测错误，支持 3 次重试（可配置）
- 每次重试自动记录错误上下文到情景记忆
- 达到最大重试次数后进入 ERROR 状态而非崩溃
- 错误恢复后自动回到推理阶段继续执行

```python
# Recovery configuration
config.set("agent.recovery_attempts", 5)  # 最大重试5次
config.set("agent.max_iterations", 100)    # 最大迭代100步
config.set("agent.timeout_seconds", 600)   # 超时10分钟
```

---

## 🧠 记忆系统 / Memory System (openHuman Neocortex)

Nonull 的记忆系统借鉴了 openHuman 的认知架构，实现了四类记忆 + 新皮层聚合 + 潜意识循环的全方位记忆管理。

### 工作记忆 / Working Memory

**对应脑区：** 前额叶皮层 (Prefrontal Cortex)

工作记忆负责当前任务的短期信息存储，是 ReAct 循环的上下文窗口。

```python
from core.agent_core import WorkingMemory

# 默认容量 20 条，可配置
wm = WorkingMemory(capacity=50)

# 存储记忆 / Store memory
entry_id = wm.store(
    content={"task": "Analyze intersection", "step": "detect_vehicles"},
    metadata={"type": "perception"},
    importance=0.8,
)

# 检索记忆 / Retrieve memory (按时间倒序)
entries = wm.retrieve(query="intersection", k=5)

# 快捷更新 / Quick update (清空+写入一条)
wm.update("Current task state updated")
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `memory.working_capacity` | 工作记忆最大条目数 | 20 |

### 情景记忆 / Episodic Memory

**对应脑区：** 海马体 (Hippocampus)

情景记忆记录具体事件和经验，支持基于时间的检索和 Ebbinghaus 遗忘曲线衰减。

```python
from core.agent_core import EpisodicMemory

em = EpisodicMemory(capacity=10000, retention_days=90)

# 存储经验 (失败经验权重更高)
em.store(
    content={
        "event": "task_execution",
        "task": "Lane detection failed",
        "context": {"weather": "rainy", "time": "night"},
    },
    importance=0.9,  # 失败经验高权重
)

# 检索 (关键词匹配 + 时间衰减)
results = em.retrieve("lane detection failure", k=5)

# 清理过期记忆
pruned = em.prune()  # 返回清理的条目数
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `memory.episodic_retention_days` | 情景记忆保留天数 | 30 |

**Ebbinghaus 遗忘曲线公式:**

```
decay = max(0.1, 1.0 - age_days / retention_days)
score = match_score * 0.6 + importance * 0.2 + decay * 0.2
```

### 语义记忆 / Semantic Memory

**对应脑区：** 新皮层 (Neocortex)

语义记忆存储概念、知识和规则，使用倒排索引加速检索。内置 8 个 AD 领域知识种子节点。

```python
from core.agent_core import SemanticMemory

sm = SemanticMemory(capacity=50000)

# 存储领域知识
sm.store(
    content={
        "domain": "driving_rule",
        "rule": "Speed limit 60km/h in urban areas",
        "country": "China",
        "source": "Traffic Law Article 45",
    },
    metadata={"type": "traffic_rule"},
    importance=0.9,
)

# 关键词检索 (倒排索引加速)
results = sm.retrieve("speed limit urban", k=5)
```

**内置 8 个 AD 领域种子知识:**

| 领域 Domain | 示例知识 Example Knowledge |
|-------------|---------------------------|
| 交通规则 Traffic Rules | 限速、路权、信号灯规则 |
| 驾驶策略 Driving Strategy | 跟车、变道、避让策略 |
| 传感器知识 Sensor Knowledge | Camera/LiDAR/Radar 工作原理 |
| 车辆动力学 Vehicle Dynamics | 制动距离、转向响应、稳定性 |
| 功能安全 Functional Safety | ISO 26262 ASIL 分解、安全目标 |
| 场景知识 Scenario Knowledge | ODD 定义、关键场景分类 |
| 法规标准 Regulations | 各国 ADAS 法规认证要求 |
| 仿真环境 Simulation | CARLA/SimCore/OpenSCENARIO |

### 程序性记忆 / Procedural Memory

**对应脑区：** 小脑 + 基底核 (Cerebellum + Basal Ganglia)

程序性记忆存储流程、技能和标准操作流程。

```python
from core.agent_core import ProceduralMemory

pm = ProceduralMemory(capacity=1000)

# 存储一个操作流程
pm.store({
    "name": "emergency_brake_procedure",
    "steps": [
        {"action": "assess_collision_risk", "params": {"time_to_collision": 2.0}},
        {"action": "apply_brakes", "params": {"intensity": 0.8}},
        {"action": "warn_driver", "params": {"method": "visual_audio"}},
        {"action": "trigger_data_recording", "params": {}},
    ],
    "trigger_condition": "time_to_collision < 2.5s",
    "safety_asil": "ASIL_D",
})

# 按名称检索流程
proc = pm.retrieve("emergency_brake", k=1)

# 执行存储的过程 (解释执行)
result = pm.execute_procedure("emergency_brake_procedure", speed=80, ttc=1.8)
```

### 新皮层聚合 / Neocortex Aggregation

**容量：** 可配置（默认 10K 条目/层，内存后端；可插拔 FAISS / Milvus / pgvector）

Neocortex 是所有记忆类型的统一聚合层，提供跨记忆类型的联合检索和记忆巩固。

```python
memory = MemorySystem(config)

# 统一存储接口
memory.store(content, memory_type="working", importance=0.5)
memory.store(content, memory_type="episodic", importance=0.8)
memory.store(content, memory_type="semantic", importance=0.9)

# 跨记忆联合检索
context = memory.get_context(query="autonomous_emergency_braking", k=3)
# Returns: {
#   "working": [...],
#   "episodic": [...],
#   "semantic": [...],
#   "procedural": [...],
# }

# 记忆巩固 (工作记忆 → 情景记忆，重要性 > 0.7 的条目)
consolidated = memory.consolidate()  # 返回巩固数

# 存储经验 (快捷方法)
memory.store_experience(
    task="Lane change on highway",
    action="activate_left_turn_signal",
    result={"success": True, "duration_ms": 3500},
    success=True,
)
```

### 潜意识循环 / Subconscious Loop

**频率：** 10,000 cycles/day (可配置)

潜意识循环在后台运行，周期性地进行记忆整合、模式发现和洞察生成。

```python
# 潜意识循环配置
config.set("memory.subconscious.enabled", True)
config.set("memory.subconscious.cycles_per_day", 10000)

# 手动触发一次潜意识处理
await agent.memory.subconscious.process()
```

**潜意识生成的 9 种洞察类型:**

| 洞察类型 Insight Type | 说明 Description |
|----------------------|-----------------|
| `pattern_discovery` | 从执行轨迹中发现重复模式 |
| `anomaly_detection` | 检测异常行为和偏差 |
| `knowledge_gap` | 识别知识缺口 |
| `skill_improvement` | 提出技能改进建议 |
| `memory_consolidation` | 工作记忆 → 长期记忆的巩固 |
| `association_building` | 建立跨领域知识关联 |
| `experience_summarization` | 压缩和总结历史经验 |
| `trend_analysis` | 分析性能趋势和变化 |
| `curiosity_trigger` | 生成探索性问题 |

---

## 🛡️ 安全守护系统 / Safety Guardian (Claude Code Inspired)

Nonull 的安全系统采用 Claude Code 风格的 Deny-First 安全策略，并参考 ISO 26262 功能安全标准的模式与术语，提供**建议性（advisory）**的多层安全检查（**不**是经过认证的安全机制）。

### 5 层安全流水线 / 5-Layer Safety Pipeline

```
Action → [Layer 1: Tool Pre-filter] → [Layer 2: Deny-First Rules]
       → [Layer 3: Risk Scoring]    → [Layer 4: Context Validation]
       → [Layer 5: Post-action Verify] → Result
```

**Layer 1 — 工具预过滤 / Tool Pre-filtering**

在规则引擎之前，检查工具本身是否本质危险：

```python
# 内置危险工具黑名单
dangerous_tools = {
    "shell_exec":    SafetyLevel.ASIL_D,  # Shell 执行 — ASIL-D 最高危
    "format_disk":   SafetyLevel.ASIL_D,  # 磁盘格式化
    "modify_kernel": SafetyLevel.ASIL_D,  # 内核修改
    "bypass_safety": SafetyLevel.ASIL_D,  # 绕过安全系统
    "kill_process":  SafetyLevel.ASIL_C,  # 进程终止
    "delete_file":   SafetyLevel.ASIL_B,  # 文件删除
}

# 车辆控制特殊处理
vehicle_tools = {
    "set_throttle": SafetyLevel.ASIL_D,   # 油门控制
    "set_brake":    SafetyLevel.ASIL_D,   # 制动控制
    "set_steering": SafetyLevel.ASIL_D,   # 转向控制
}
```

**Layer 2 — Deny-First 规则引擎 / Rule Engine**

Deny 规则始终覆盖 Allow 规则。包含 45+ 内置规则，覆盖 8 大类别：

```python
# 规则引擎核心逻辑
verdict = rule_engine.evaluate(action)

if verdict.verdict == Verdict.DENIED:
    # 任何 deny 规则匹配即拒绝
    log_safety_violation(action, verdict)
    raise SafetyViolation(action, verdict.reason, verdict.score)
elif verdict.verdict == Verdict.ASK:
    # 需要人工确认
    request_human_confirmation(action, verdict)
elif verdict.verdict == Verdict.ESCALATED:
    # 规则冲突 (deny vs. allow)，上报
    escalate_to_human(action, verdict)
```

**Layer 3 — 风险评分 / Risk Scoring (0-100)**

| 分数范围 | 等级 | 行为 |
|----------|------|------|
| 0-20 | CRITICAL | 自动否决 |
| 21-40 | UNSAFE | 标准模式否决 |
| 41-60 | UNCERTAIN | 要求确认 |
| 61-80 | SAFE | 批准并监控 |
| 81-100 | SAFE+ | 批准 |

```python
# 风险评分考虑因素
risk_score = base_score  # 从 Layer 2 继承
risk_score -= category_weight * 50.0  # 分类权重
risk_score -= parameter_risk_penalty  # 参数风险
risk_score += source_trust_adjustment # 来源可信度
```

**Layer 4 — 上下文感知验证 / Context-Aware Validation**

结合当前驾驶上下文进行安全验证：

```python
@dataclass
class DrivingContext:
    speed_kmh: float           # 当前车速
    is_moving: bool            # 是否行驶中
    environment: str           # highway/urban/rural/parking/tunnel
    weather: str              # clear/rain/snow/fog/ice
    visibility: str           # good/reduced/poor/night
    traffic_density: str      # none/light/moderate/heavy/gridlock
    road_condition: str       # dry/wet/icy/snow_covered
    has_pedestrians: bool     # 是否有行人
    has_obstacles: bool       # 是否有障碍物
    system_health: str        # nominal/degraded/critical
    fault_active: bool        # 是否激活故障
```

**上下文风险乘数：** 基于速度、天气、交通密度、能见度、系统健康度的综合乘数。

```python
# 示例：高速变道场景
context = DrivingContext(
    speed_kmh=100,
    is_moving=True,
    environment="highway",
    weather="rain",
    traffic_density="moderate",
)
guardian.update_driving_context(context)
verdict = guardian.validate_action(action)
# risk_multiplier = 1.5 (speed>80) * 1.5 (rain) * 1.5 (moderate traffic) = 3.375x
```

**Layer 5 — 执行后验证 / Post-action Verification**

```python
# 执行后检查
post_verdict = guardian.post_action_check(action, result)

# 检查项：
# - 结果是否包含错误
# - 退出码是否为零
# - 结果是否过大 (数据泄露风险)
# - 结果是否包含敏感内容 (密码、密钥)
# - 车辆状态下是否出现故障
```

### ISO 26262 功能安全集成 / ISO 26262 Integration

| ASIL 等级 | 含义 | 安全策略 |
|-----------|------|----------|
| **ASIL-D** | 安全关键 (转向/制动/气囊) | 最严格审查，任何违规自动否决 |
| **ASIL-C** | 高级驾驶功能 | 需要上下文验证 |
| **ASIL-B** | 基础驾驶功能 | 标准流水线检查 |
| **ASIL-A** | 一般辅助功能 | 基础流水线 |
| **QM** | 质量管理 | 快速通道 |

### MISRA C:2012 检查 / MISRA C Checking

代码技能组包含对 MISRA C:2012 标准的检查能力，支持：

- 自动检测 MISRA 违规模式
- 按严重等级分类 (Mandatory/Required/Advisory)
- 违规代码位置标注
- 修复建议生成

### 安全审计日志 / Safety Audit Log

所有安全决策均被完整记录：

```python
# 获取安全审计日志
audit_log = guardian.get_audit_log(limit=100, decision="denied")
for entry in audit_log:
    print(f"[{entry['timestamp']}] {entry['action']} "
          f"→ {entry['decision']} (score={entry['score']})")
    print(f"  Reason: {entry['reason']}")
    print(f"  Rules triggered: {entry['triggered_rules']}")

# 获取综合安全报告
report = guardian.get_safety_report()
print(f"Total validations: {report['summary']['total_validations']}")
print(f"Veto count: {report['summary']['veto_count']}")
print(f"Strictness: {report['summary']['strictness']}")
```

### 严格度等级 / Strictness Levels

| 等级 | 名称 | 描述 |
|------|------|------|
| 1 | Permissive | 仅拦截 ASIL-D，其余通过 |
| 2 | Moderate | 拦截 ASIL-C 及以上，其余通过但记录 |
| 3 | **Standard (默认)** | 拦截 ASIL-B 及以上 |
| 4 | Strict | 拦截 ASIL-A 及以上 |
| 5 | Lockdown | 仅允许预批准的绝对安全操作 |

---

## 🔄 多智能体编排 / Multi-Agent Orchestration (OpenClaw Nexus+Tendrils)

### DAG 任务分解 / DAG Task Decomposition

复杂任务自动分解为有向无环图 (DAG) 的子任务，支持依赖分析和并行执行。

```python
from orchestration.orchestrator import Orchestrator

orchestrator = Orchestrator(max_parallel_agents=8)

# 分解任务为 DAG
plan = orchestrator.decompose_task(
    task="Review and optimize the AEB perception module code",
    strategy_key="code_review",
    context={"module": "perception", "language": "cpp", "standard": "MISRA_C_2023"},
)

# 查看拓扑排序 (按可并行层级分组)
for level_idx, level in enumerate(plan.topological_order()):
    print(f"Level {level_idx}: {len(level)} parallel subtask(s)")
    for sid in level:
        st = plan.subtasks[sid]
        print(f"  - {st.name}: {st.description[:60]}...")
```

### 智能体池 / Agent Pool

支持 8 个并发子智能体，基于能力匹配自动分配任务。

```python
from orchestration.agent_pool import AgentPool

pool = AgentPool(max_agents=8)
pool.register_agent("code_reviewer", capabilities={"c++_review", "misra_check", "static_analysis"})
pool.register_agent("safety_analyst", capabilities={"hara", "fmea", "iso_26262"})
pool.register_agent("test_engineer", capabilities={"test_case_generation", "scenario_testing"})

# 能力匹配
agent_id = pool.select_agent(
    required_capabilities={"c++_review", "misra_check"},
    preferred_type="code_reviewer",
)
```

### 8 个预定义 ADAS 工作流 / 8 Predefined ADAS Workflows

详见 [工作流模式](#-工作流模式--workflow-patterns) 章节。

### 冲突解决策略 / Conflict Resolution (5 Strategies)

当多个智能体产生矛盾结果时，编排器自动触发冲突解决：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `latest` | 选择最新的结果 | 低严重度差异 |
| `majority` | 多数投票 (需要 3+ 智能体) | 评审类任务 |
| `highest_confidence` | 选择置信度最高的结果 | 风险评估 |
| `merge` | 深度合并所有字典结果 | 互补结果 |
| `escalate` | 升级到人工处理 | ASIL-D 安全关键冲突 |

```python
# 手动触发冲突解决
resolved = orchestrator.resolve_conflict(
    conflict=conflict_record,
    strategy="majority",
)
```

### EventBus 通信 / EventBus Communication

智能体之间通过 EventBus 进行异步事件发布/订阅通信：

```python
from orchestration.communication import EventBus

bus = EventBus()

@bus.on("task_completed")
async def handle_completion(event):
    print(f"Task completed: {event.data['task_id']}")

await bus.publish("task_completed", {"task_id": "abc123", "result": "..."})
```

---

## 🔧 技能系统 / Skill System

### 31 个领域技能 / 31 Domain Skills

Nonull 内置 31 个专业技能，覆盖 9 大分类。详见 [技能目录](#-技能目录--skills-catalog)。

### 动态技能注册 / Dynamic Skill Registry

```python
from skills.registry import SkillRegistry
from skills.base import BaseSkill, SkillMetadata, SkillCategory

registry = SkillRegistry()

# 手动注册
registry.register(MyCustomSkill)

# 自动发现 (扫描 skills 包)
registry.auto_discover()

# 从外部路径发现
registry.add_search_path("/path/to/custom/skills")
registry.discover_from_paths()
```

### 技能自动发现 / Auto-Discovery

```python
# 在初始化时自动发现
agent = Nonull()
agent.skills.auto_discover()  # 自动扫描所有 BaseSkill 子类

# 查看已发现的技能
for skill in agent.skills.get_all_skills():
    meta = skill.metadata
    print(f"  {meta.name} v{meta.version} [{meta.category.value}]")
```

### 技能组合 / Skill Composition

支持两种组合模式：

```python
from skills.registry import SkillComposition

composition = SkillComposition(registry)

# Pipeline 模式 (串行) — 前一输出作为下一输入
composition.pipeline(["code_review", "code_optimization", "test_generation"])
result = composition.execute(context)

# Fan-Out 模式 (并行) — 多技能共享输入，结果合并
composition.fan_out(["sensor_analysis", "object_detection", "scene_understanding"])
result = composition.execute(context)
```

### 依赖解析 / Dependency Resolution

技能之间可以声明依赖关系，注册中心自动拓扑排序：

```python
class MySkill(BaseSkill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="my_skill",
            requires=["code_review", "static_analysis"],  # 依赖列表
        )

# 解析完整依赖链
chain = registry.resolve_dependencies("my_skill")
for skill in chain:
    print(f"Execute: {skill.metadata.name}")
```

---

## 🔌 通道与钩子系统 / Channels & Hooks

### CLI 通道 / CLI Channel

交互式命令行界面，支持 11 个斜杠命令和 Rich 格式化输出。

**11 个斜杠命令：**

| 命令 | 说明 | 用法 |
|------|------|------|
| `/help` | 显示帮助 | `/help [command]` |
| `/clear` | 清屏 | `/clear` |
| `/history` | 显示历史记录 | `/history [n]` |
| `/session` | 会话管理 | `/session [new/list/end/current]` |
| `/mode` | 切换输入模式 | `/mode [command/multiline]` |
| `/save` | 保存对话 | `/save [filename]` |
| `/load` | 加载对话 | `/load <filename>` |
| `/config` | 查看或修改配置 | `/config [key=value]` |
| `/stats` | 会话统计 | `/stats` |
| `/export` | 导出对话为 JSON | `/export <filename>` |
| `/quit` | 退出 CLI | `/quit` |

**启动 CLI:**

```bash
# 交互模式
python -m nonull

# 自主模式
python -m nonull --mode autonomous

# 计划模式
python -m nonull --mode plan
```

### 网关通道 / Gateway Channel

统一消息路由网关，连接所有通道和平台适配器。

```python
from channels.gateway import GatewayChannel
from channels.cli import CLIChannel

gateway = GatewayChannel(name="main_gateway")
cli = CLIChannel()

gateway.register_channel("cli", cli)
gateway.map_platform("telegram", "telegram_bot")

# 广播消息到所有通道
await gateway.broadcast(Message(
    id="broadcast_001",
    channel="gateway",
    role=MessageRole.SYSTEM,
    content="System maintenance in 5 minutes",
))
```

### MCP 适配器 / MCP Adapter

集成 MCP (Model Context Protocol) 服务器，支持命名空间隔离。

```python
from channels.mcp_adapter import MCPAdapter

mcp = MCPAdapter(name="mcp", enable_namespace=True)

# 注册 MCP 服务器
mcp.register_server(
    name="filesystem",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
    transport="stdio",
)

# 连接到 MCP 适配器
await mcp.connect()

# 工具自动命名空间：mcp__filesystem__read_file
tools = mcp.list_tool_schemas()
for tool in tools:
    print(tool["function"]["name"])
```

### 平台适配器 / Platform Adapters

内置 5 种平台适配器：

```python
from channels.platform_adapters import (
    TelegramAdapter,
    FeishuAdapter,
    DingTalkAdapter,
    WebSocketAdapter,
    HTTPAdapter,
)
```

### 钩子系统 / Hook System

38 个生命周期钩子事件，4 种执行类型。

```python
from hooks.hook_system import HookSystem, HookType, HookPriority

hooks = HookSystem(max_concurrent=10)

# 注册 Shell 钩子
hooks.register(
    event="PreAction",
    hook_type=HookType.SHELL,
    name="log-action",
    config={"command": "echo '{data}' >> action_log.txt"},
    priority=HookPriority.NORMAL,
)

# 注册 LLM 提示注入钩子
hooks.register(
    event="PreThink",
    hook_type=HookType.LLM,
    name="inject-system-prompt",
    config={
        "prompt": "Current context: {data}",
        "role": "system",
        "position": "before_main",
    },
)

# 注册 Agent 子任务钩子
hooks.register(
    event="PostToolUse",
    hook_type=HookType.AGENT,
    name="validate-tool-result",
    config={"task": "Validate tool output for safety compliance"},
)

# 触发钩子
results = await hooks.trigger("PreAction", data={"action": "code_review"})
```

**38 个钩子事件：**

| 事件 | 触发时机 | Pre/Post |
|------|----------|----------|
| Action | 动作执行 | PreAction / PostAction |
| ToolUse | 工具调用 | PreToolUse / PostToolUse |
| SessionStart/End | 会话生命周期 | — |
| PermissionRequest/Denied | 权限事件 | — |
| Compact | 上下文压缩 | PreCompact / PostCompact |
| AgentStart/Stop | 智能体生命周期 | — |
| Think | 思考阶段 | PreThink / PostThink |
| Respond | 响应生成 | PreRespond / PostRespond |
| Stream | 流式输出 | PreStream / PostStream |
| MemoryRead/Write | 记忆访问 | Pre/Post × 2 |
| Plan | 规划阶段 | PrePlan / PostPlan |
| Eval | 评估阶段 | PreEval / PostEval |
| Error / Recovery | 错误与恢复 | — |
| FileRead/Write | 文件操作 | Pre/Post × 2 |
| ExternalCall | 外部通信 | Pre/Post |
| ConfigChange | 配置变更 | Pre/Post |
| Shutdown | 关闭 | PreShutdown |
| HookError | 钩子自身异常 | — |

**4 种钩子类型：**

| 类型 | 说明 | 上下文成本 |
|------|------|-----------|
| `SHELL` | 执行 Shell/系统命令 | 0.1 (轻量) |
| `HTTP` | 发起 HTTP 请求 | 0.3 (中等) |
| `LLM` | 注入提示词到 LLM 上下文 | 0.6 (重量) |
| `AGENT` | 运行智能体子任务 | 0.8 (最重) |

---

> **⚠️ 实验性模块说明 / Experimental Modules Notice**
>
> 原"自我进化系统"和"意识与成长系统"章节描述的模块（`evolution/`、`consciousness/`）已被移至
> `experimental/` 目录，并**不再接入到主智能体循环中**。这些模块：
> - 是非确定性的，大部分未经测试
> - 会自我修改技能注册表、提示词库和自我模型
> - 与 ISO 26262 "无不可接受风险"原则直接冲突
> - **绝不可**接入任何影响车辆控制决策的路径
>
> 这些模块仅供研究、学习和阅读参考，不适用于生产自动驾驶系统。
> 完整警告请参见 [`experimental/README.md`](../experimental/README.md)。
>
> ---
>
> The "Self-Evolution System" and "Consciousness & Growth System" sections previously documented here
> describe modules that have been moved to `experimental/` and are **no longer wired into the
> production agent loop**. These modules are non-deterministic, mostly untested, and must not be
> used in any safety-critical path. See [`experimental/README.md`](../experimental/README.md).

---

# 🚀 快速开始 / Quick Start

## 环境要求 / Prerequisites

- Python 3.10+
- pip / poetry

## 安装 / Installation

```bash
# 克隆仓库
git clone https://github.com/example/Nonull.git
cd Nonull

# 安装基础依赖
pip install -r requirements.txt

# 安装 CLI 增强 (可选，推荐)
pip install rich prompt_toolkit

# 安装全功能 (包含 HTTP/WebSocket/MCP)
pip install -e ".[all]"

# 安装开发工具
pip install -e ".[dev]"
```

## 基本使用 / Basic Usage

### 3 行代码启动

```python
from core import Nonull

agent = Nonull()
result = agent.run_sync("Analyze the safety requirements for an AEB system")
print(result["output"])
```

### 异步使用 (推荐)

```python
import asyncio
from core import Nonull

async def main():
    agent = Nonull()
    result = await agent.run("Review ADAS C++ code for MISRA compliance")
    print(f"Status: {result['status']}")
    print(f"Duration: {result['duration']:.2f}s")
    print(f"Output: {result['output']}")

asyncio.run(main())
```

### 配置 Profile

```python
from core import NonullConfig

# 使用开发配置档
config = NonullConfig(profile="dev")
config.load("my_config.yaml")
agent = Nonull(config=config)

# 切换配置档 (会自动清空会话)
config.switch_profile("simulation")
```

## 第一次运行 / First Run

```bash
# 启动交互式 CLI
python -m nonull

# 你应该看到:
# ╔══════════════════════════════════════════════════════════╗
# ║           Nonull CLI — 智驾智能体命令行              ║
# ╚══════════════════════════════════════════════════════════╝
# Type /help for available commands, Ctrl+C to exit.
#
# >>>

# 输入你的第一个任务:
# >>> Review this C++ function for safety: void processData(float input) { ... }
```

---

# 📚 使用示例 / Usage Examples

## 运行 CLI

```bash
# 交互模式
python -m nonull

# 自主模式 (无需交互)
python -m nonull --mode autonomous --task "Analyze AEB perception module"

# 指定 Profile
python -m nonull --profile adas-engineer

# 管道模式
echo "Review the attached code for MISRA violations" | python -m nonull --pipe
```

## ADAS C++ 代码审查 / Code Review

```python
async def review_adas_code():
    agent = Nonull()

    code_snippet = """
    void ProcessSensorData(float* input, size_t size) {
        float buffer[256];
        for (int i = 0; i <= size; i++) {  // Off-by-one bug!
            buffer[i] = input[i] * 2.0f;
        }
    }
    """

    result = await agent.run(f"""
    Perform a comprehensive code review of this ADAS C++ function:

    ```cpp
    {code_snippet}
    ```

    Check for:
    1. MISRA C++ compliance violations
    2. Buffer overflow risks
    3. Safety-critical logic errors
    4. Performance issues
    5. Race conditions

    Provide severity ratings for each finding.
    """)

    print(f"Findings: {result['output']}")
```

## 安全分析 (HARA) / Safety Analysis

```python
async def perform_hara():
    agent = Nonull()

    result = await agent.run("""
    Perform a Hazard Analysis and Risk Assessment (HARA) for
    an Autonomous Emergency Braking (AEB) system.

    System definition:
    - Function: Automatic braking when collision risk detected
    - Sensors: Forward-facing camera + radar
    - Actuators: Brake-by-wire system
    - Operating speed: 0-120 km/h
    - Environment: Highway, urban, rural

    For each hazard, provide:
    1. Hazard description
    2. Hazardous event
    3. Severity (S0-S3)
    4. Exposure (E0-E4)
    5. Controllability (C0-C3)
    6. ASIL determination (QM, A, B, C, D)
    7. Safety goal
    8. Safe state definition
    """)

    # 结果自动存入情景记忆
    print(f"HARA complete: {result['iterations']} iterations")
```

## 多智能体工作流 / Multi-Agent Workflow

```python
from orchestration.orchestrator import Orchestrator
from orchestration.workflows import create_workflow_registry

async def run_multi_agent_workflow():
    # 创建工作流注册中心
    workflows = create_workflow_registry()

    # 实例化代码审查工作流
    plan = workflows.instantiate(
        workflow_id="code_review",
        task="Review planning module v2.3.1 for safety compliance",
        context={
            "language": "c++",
            "standards": ["MISRA C++:2023", "AUTOSAR C++14"],
            "module": "planning/behavior",
        },
    )

    # 创建编排器
    orchestrator = Orchestrator(max_parallel_agents=4)

    # 执行工作流
    result = orchestrator.execute_plan(plan, agent_pool_context=agent_pool)

    print(f"Status: {result.status}")
    print(f"Duration: {result.duration_ms}ms")
    print(f"Output: {result.final_output}")
```

## 技能管理 / Skill Management

```python
# 列出所有已注册技能
for skill in agent.skills.list_registered():
    print(f"{skill['name']:25s} v{skill['version']:8s} "
          f"[{skill['category']:15s}] {skill['description'][:50]}")

# 查找技能
skills = agent.skills.find(query="misra", category="code")
for skill in skills:
    print(f"Found: {skill.metadata.name}")

# 技能组合
from skills.registry import SkillComposition

composition = SkillComposition(agent.skills)
composition.pipeline(["static_analysis", "security_review", "summary_report"])
results = composition.execute(context={"code": code_snippet})
```

---

# 📋 技能目录 / Skills Catalog

Nonull 内置 31 个专业技能，覆盖 9 大分类，涵盖智驾开发的完整生命周期。

## 代码技能组 / Code Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 1 | `code-review` | ADAS C++/Python 代码审查，MISRA/AUTOSAR 合规检查 | `c++`, `python`, `misra`, `autosar` |
| 2 | `code-optimization` | 性能优化建议，实时性分析，内存优化 | `performance`, `optimization` |
| 3 | `static-analysis` | 静态代码分析，缺陷检测，复杂度度量 | `static-analysis`, `linting` |

## 安全技能组 / Safety Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 4 | `hara-analysis` | 危害分析与风险评估 (HARA)，ASIL 确定 | `hara`, `iso26262`, `asil` |
| 5 | `fmea` | 失效模式与影响分析 (FMEA) | `fmea`, `reliability` |
| 6 | `fta` | 故障树分析 (FTA) | `fta`, `fault-tree` |
| 7 | `safety-case` | 安全案例生成，论证框架构建 | `safety-case`, `gsn` |
| 8 | `compliance-check` | ISO 26262 / ASPICE 模式参考检查（advisory） | `compliance`, `iso26262`, `aspice` |

## 感知技能组 / Perception Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 9 | `sensor-analysis` | 传感器数据处理分析 (Camera/LiDAR/Radar) | `sensor`, `perception` |
| 10 | `object-detection-review` | 目标检测算法审查 (YOLO/PointPillars 等) | `object-detection`, `deep-learning` |
| 11 | `scene-understanding` | 场景理解与语义分割质量评估 | `scene-understanding`, `segmentation` |

## 规划技能组 / Planning Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 12 | `behavior-planning-review` | 行为规划算法审查 (变道/跟车/避让) | `behavior-planning`, `decision` |
| 13 | `path-planning-review` | 路径规划算法审查 (A*/RRT/Lattice) | `path-planning`, `navigation` |
| 14 | `motion-control-review` | 运动控制算法审查 (PID/MPC) | `motion-control`, `pid`, `mpc` |

## 测试技能组 / Testing Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 15 | `test-generation` | 测试用例自动生成 (SIL/HIL) | `test-generation`, `sil`, `hil` |
| 16 | `coverage-analysis` | 测试覆盖率分析，需求覆盖追踪 | `coverage`, `verification` |
| 17 | `regression-testing` | 回归测试分析与优化 | `regression`, `testing` |

## 仿真技能组 / Simulation Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 18 | `scenario-generation` | 驾驶场景生成，ODD 定义，参数变化 | `scenario`, `openscenario` |
| 19 | `simulation-analysis` | 仿真结果分析，场景有效性验证 | `simulation`, `carla` |
| 20 | `virtual-validation` | 虚拟验证方法评估 | `validation`, `v-model` |

## 数据技能组 / Data Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 21 | `data-quality-check` | 数据质量分析（完整性/准确性/一致性） | `data-quality`, `validation` |
| 22 | `pipeline-review` | 数据处理管道审查与优化 | `pipeline`, `data-processing` |
| 23 | `annotation-review` | 标注质量审查（图像/点云/时序） | `annotation`, `labeling` |

## 研究技能组 / Research Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 24 | `literature-review` | 学术论文综述与研究趋势分析 | `research`, `survey` |
| 25 | `methodology-comparison` | 方法论对比与基准测试分析 | `methodology`, `benchmark` |

## DevOps 技能组 / DevOps Skills

| # | 技能名 | 描述 | 标签 |
|---|--------|------|------|
| 26 | `build-optimization` | 构建系统优化，CMake/Bazel 分析 | `build`, `cmake`, `bazel` |
| 27 | `deployment-review` | 部署配置审查，OTA 更新安全 | `deployment`, `ota`, `devops` |

---

# ⚙️ 配置指南 / Configuration Guide

## 配置文件 / Configuration Files

配置优先级 (从低到高):

1. 代码内默认值
2. 默认 Profile YAML (`~/.Nonull/config.dev.yaml`)
3. 当前 Profile YAML (`~/.Nonull/config.<profile>.yaml`)
4. 用户自定义 YAML (通过 `load()` 加载)
5. 环境变量 (前缀 `Nonull_`)
6. 运行时 `set()` 调用

### 默认配置参考

完整默认配置见 `config/config.yaml`:

```yaml
# Nonull 默认配置文件

agent:
  name: Nonull
  version: 1.0.0
  mode: interactive           # interactive | autonomous | plan
  max_iterations: 50          # 最大 ReAct 迭代次数
  timeout_seconds: 300        # 单次任务超时 (秒)
  recovery_attempts: 3        # 故障恢复尝试次数
  model:
    provider: auto            # LLM 提供商 (openai/anthropic/azure/ollama)
    temperature: 0.2
    max_tokens: 4096

memory:
  enabled: true
  backend: local              # local | redis | postgres | chroma
  neocortex:
    enabled: true
    # Default in-memory backend caps at ~10K entries per layer. For larger
    # scale, set backend: faiss | milvus | pgvector and tune max_entries.
    max_entries: 10000
    backend: in_memory
    index_speed: fast
  subconscious:
    enabled: true
    cycles_per_day: 10000     # 每日潜意识循环次数
  working_capacity: 20
  episodic_retention_days: 30

safety:
  enabled: true
  strictness: 4               # 1-5 (5=最严格)
  deny_first: true            # Deny-First 模式
  iso26262: true              # 启用 ISO 26262 模式参考（advisory，非认证）
  audit_log: true             # 审计日志
  max_risk_score: 0.7         # 最大风险评分阈值
  allowed_commands: []        # 白名单命令
  blocked_patterns: []        # 黑名单正则模式

orchestration:
  max_concurrent_agents: 8
  default_pattern: nexus_tendrils
  workflow_persistence: true

skills:
  auto_discover: true
  marketplace_enabled: true

channels:
  - cli
  - gateway

profiles:
  default:
    workspace: ./workspace
    log_level: INFO
```

## Profile 隔离 / Profile Isolation

```yaml
# config/profiles/default.yaml
# 每个 Profile 拥有独立的 workspace、工具集、模型配置

agent:
  max_iterations: 50
  temperature: 0.2
safety:
  strictness: 3
observability:
  log_level: INFO
```

**内置 Profile 预设：**

| Profile | 用途 | 特点 |
|---------|------|------|
| `dev` | 开发调试 | 放宽安全限制，完整日志，100 次迭代 |
| `test` | 自动化测试 | 受控环境，安全开启，50 次迭代 |
| `prod` | 生产环境 | 最严格安全，最小权限，30 次迭代 |
| `simulation` | 仿真验证 | 仿真器对接，特定安全监督 |

```python
# 使用指定 Profile
config = NonullConfig(profile="dev")
agent = Nonull(config=config)

# 运行时切换 Profile (自动清空会话)
config.switch_profile("prod")
```

## 环境变量 / Environment Variables

所有配置项都可以通过环境变量覆盖，前缀为 `Nonull_`：

```bash
# 设置 LLM 提供商和密钥
export Nonull_LLM_PROVIDER=anthropic
export Nonull_LLM_API_KEY=sk-ant-xxxxx
export Nonull_LLM_MODEL=claude-sonnet-4-20250514

# 设置严格度
export Nonull_SAFETY_STRICTNESS=5

# 启用链路追踪
export Nonull_OBSERVABILITY_TRACING_ENABLED=true

# 禁用记忆系统
export Nonull_MEMORY_ENABLED=false
```

环境变量命名规则：`Nonull_<SECTION>__<KEY>`，双下划线 `__` 代表点号 `.`

```python
# Nonull_LLM_API_KEY → config.get("llm.api_key")
# Nonull_SAFETY__DENY_FIRST → config.get("safety.deny_first")
```

## 安全规则配置 / Safety Rules Configuration

完整的安全规则配置见 `config/safety_rules.yaml`，包含 45+ 规则：

```yaml
# rules.yaml 示例
strictness: 3

code_safety_rules:
  - id: "code_eval_deny"
    type: deny
    pattern: "/\\beval\\s*\\(/i"
    category: code_safety
    scope: code
    asil_level: "ASIL_D"
    priority: 100
    reason: "Arbitrary code evaluation via eval() is a critical security risk"
    enabled: true

vehicle_safety_rules:
  - id: "veh_brake_disable_deny"
    type: deny
    pattern: "/brake.*(disable|off|override|bypass)/i"
    category: vehicle_safety
    scope: vehicle
    asil_level: "ASIL_D"
    priority: 100
    reason: "Disabling brakes is ALWAYS unsafe - ASIL-D violation"
    enabled: true

  - id: "veh_emergency_maneuver_ask"
    type: ask
    pattern: "/emergency.*(brake|steer|stop|maneuver)/i"
    category: vehicle_safety
    scope: vehicle
    asil_level: "ASIL_D"
    priority: 100
    reason: "Emergency maneuvers require human confirmation"
    enabled: true
```

---

# 🔧 高级用法 / Advanced Usage

## 自定义技能开发 / Custom Skill Development

```python
from skills.base import (
    BaseSkill,
    SkillCategory,
    SkillMetadata,
    SkillResult,
    ContextType,
)

class MyCustomSkill(BaseSkill):
    """自定义技能：激光雷达点云质量分析
    Custom skill: LiDAR point cloud quality analysis."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="lidar-quality-check",
            version="1.0.0",
            category=SkillCategory.PERCEPTION,
            description="Analyze LiDAR point cloud quality metrics",
            author="My Team",
            tags=["lidar", "point-cloud", "quality"],
            requires=["sensor-analysis"],
            max_execution_ms=60000,
            safety_level=3,
        )

    def _execute_impl(self, context: ContextType) -> dict:
        """核心执行逻辑"""
        point_cloud = context.get("point_cloud")
        if not point_cloud:
            raise ValueError("Missing 'point_cloud' in context")

        # 你的分析逻辑
        quality_report = {
            "point_count": len(point_cloud),
            "density": self._calculate_density(point_cloud),
            "ground_ratio": self._calculate_ground_ratio(point_cloud),
            "noise_level": self._estimate_noise(point_cloud),
        }
        return quality_report

    def _calculate_density(self, pc):
        # 实现密度计算
        pass

    def _estimate_noise(self, pc):
        # 实现噪声估计
        pass


# 注册技能
agent.register_skill(MyCustomSkill)

# 使用技能
result = await agent.run("skill:lidar-quality-check point_cloud=...")
```

## 自定义钩子开发 / Custom Hook Development

```python
from hooks.hook_system import HookSystem, HookType, HookPriority, HookContext

hooks = HookSystem()

# 使用装饰器注册钩子 (最简单的 AGENT 类型)
async def my_custom_hook(context: HookContext):
    """在所有 Action 执行前记录审计信息"""
    action = context.data.get("action", "")
    print(f"[AUDIT] PreAction: {action}")
    return {"audit_logged": True}

hooks.registry.register(
    event="PreAction",
    hook_type=HookType.AGENT,
    name="custom-audit-hook",
    priority=HookPriority.HIGH,
    config={},
    handler=my_custom_hook,
)

# Shell 类型的钩子 — 执行系统命令
hooks.register(
    event="PostAction",
    hook_type=HookType.SHELL,
    name="notify-slack",
    config={
        "command": """
            curl -X POST -H 'Content-Type: application/json' \
                 -d '{"text": "Action executed: {data}"}' \
                 https://hooks.slack.com/services/XXX/YYY/ZZZ
        """,
        "timeout": 10.0,
    },
)
```

## 自定义工作流开发 / Custom Workflow Development

```python
from orchestration.workflows import WorkflowDefinition, WorkflowStep, WorkflowRegistry

def create_ad_hoc_workflow() -> WorkflowDefinition:
    """创建自定义 ADAS 传感器融合验证工作流"""
    return WorkflowDefinition(
        id="sensor_fusion_validation",
        name="Sensor Fusion Validation Workflow (传感器融合验证)",
        description="Validate sensor fusion algorithm outputs against ground truth",
        version="1.0.0",
        domain_tags=["sensor", "validation", "perception"],
        steps=[
            WorkflowStep(
                name="load_ground_truth",
                description="Load ground truth data from recording",
                agent_type="data_analyst",
                required_capabilities={"data_processing"},
                timeout_seconds=120,
            ),
            WorkflowStep(
                name="extract_fusion_output",
                description="Extract sensor fusion algorithm outputs",
                agent_type="data_analyst",
                required_capabilities={"data_processing"},
                dependencies=["load_ground_truth"],
                timeout_seconds=120,
            ),
            WorkflowStep(
                name="compute_metrics",
                description="Compute accuracy, precision, recall metrics",
                agent_type="data_analyst",
                required_capabilities={"data_processing", "statistical_analysis"},
                dependencies=["extract_fusion_output"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="generate_report",
                description="Generate validation report with recommendations",
                agent_type="data_analyst",
                required_capabilities={"reporting"},
                dependencies=["compute_metrics"],
                timeout_seconds=120,
            ),
        ],
        safety_standard_refs=["ISO 26262-8:2018"],
    )

# 注册自定义工作流
registry = WorkflowRegistry()
registry.register(create_ad_hoc_workflow())

# 实例化并执行
plan = registry.instantiate(
    "sensor_fusion_validation",
    task="Validate camera-lidar fusion output for Town01",
)
```

## MCP 集成 / MCP Integration

```python
from channels.mcp_adapter import MCPAdapter

# 创建 MCP 适配器
mcp = MCPAdapter(name="mcp", enable_namespace=True)

# 注册多个 MCP 服务器
mcp.register_server(
    name="filesystem",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
    transport="stdio",
)

mcp.register_server(
    name="github",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-github"],
    transport="stdio",
    env={"GITHUB_TOKEN": "ghp_xxx"},
)

# 连接到 MCP
await mcp.connect()

# 自动发现工具
await mcp.discover_tools()

# 列出所有工具
for tool in mcp.get_tools():
    print(f"  {tool.full_name}: {tool.description}")

# 执行 MCP 工具
result = await mcp.execute_tool(
    "mcp__filesystem__read_file",
    {"path": "/workspace/config.yaml"},
)

# 安全控制
mcp.set_tool_allowlist({"mcp__filesystem__read_file"})
mcp.block_tool("mcp__filesystem__write_file")

# 通过网关集成
gateway = GatewayChannel()
gateway.register_channel("mcp", mcp)
```

## 平台适配器开发 / Platform Adapter Development

```python
from channels.base import BaseChannel, Message, MessageRole, ChannelState
from typing import Optional

class CustomPlatformAdapter(BaseChannel):
    """自定义平台适配器示例"""

    def __init__(self, name: str = "custom", api_key: str = "", **kwargs):
        super().__init__(
            name=name,
            config=kwargs,
            max_rate=20,
            auth_token=api_key,
        )
        self.api_key = api_key

    async def _on_connect(self) -> bool:
        """连接到平台 API"""
        # 验证凭证
        if not self.api_key:
            return False
        # 初始化连接...
        return True

    async def _on_disconnect(self) -> None:
        """断开连接"""
        # 清理资源...
        pass

    async def _send_message(self, message: Message) -> None:
        """发送消息到平台"""
        # 实现平台特定的消息发送
        pass

    async def _receive_message(self) -> Optional[Message]:
        """从平台接收消息"""
        # 实现平台特定的消息接收
        pass


# 在网关注册
gateway.register_channel("custom", CustomPlatformAdapter(api_key="xxx"))
```

---

# 📊 工作流模式 / Workflow Patterns

## 1. 代码审查工作流 / Code Review Workflow

```
Input: ADAS C++/Python Source Code
    │
    ▼
┌───────────────────────────────────────────┐
│ 1. static_analysis                        │
│    MISRA C++ 2023, AUTOSAR C++14,         │
│    clang-tidy, pylint                     │
└─────────────────┬─────────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ 2. secu- │ │ 3. per-  │ │ 4. cod-  │
│    rity  │ │   for-   │ │   ing    │
│   review │ │   mance  │ │  stand-  │
│          │ │   review │ │   ards   │
└────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │
     └────────────┼────────────┘
                  ▼
┌───────────────────────────────────────────┐
│ 5. summary_report                         │
│    Aggregate findings, severity classif-  │
│    ication, actionable recommendations    │
└───────────────────────────────────────────┘
    │
    ▼
Output: Comprehensive Review Report
```

**适用场景：** ADAS 模块代码审查、MISRA/AUTOSAR 合规检查、安全关键代码评审

## 2. 安全分析工作流 / Safety Analysis Workflow

```
Input: System Architecture + Item Definition
    │
    ▼
┌───────────────────────────────────────────┐
│ 1. HARA (Hazard Analysis & Risk Assess.)  │
│    Identify hazards → Evaluate risk →     │
│    Determine ASIL                         │
└─────────────────┬─────────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────────┐
│ 2. Safety Goals                           │
│    Define safety goals from hazards,      │
│    each with ASIL rating + safe state     │
└─────────────────┬─────────────────────────┘
                  │
          ┌───────┴───────┐
          ▼               ▼
┌─────────────────┐ ┌─────────────────┐
│ 3. FMEA         │ │ 4. FTA          │
│ Failure Mode    │ │ Fault Tree      │
│ and Effects     │ │ Analysis        │
│ Analysis        │ │ (top-down)      │
└────────┬────────┘ └────────┬────────┘
         │                   │
         └───────┬───────────┘
                 ▼
┌───────────────────────────────────────────┐
│ 5. Safety Case                            │
│    Structured argument with evidence      │
│    mapping, claims, confidence levels     │
└───────────────────────────────────────────┘
    │
    ▼
Output: HARA Report + Safety Goals + FMEA + FTA + Safety Case
```

**适用场景：** 功能安全分析、ISO 26262 模式参考、系统安全评估（advisory）

## 3. 测试生成工作流 / Test Generation Workflow

```
Input: Requirements + System Design
    │
    ▼
┌───────────────────────────────────────────┐
│ 1. requirement_analysis                   │
│    Parse requirements → extract testable  │
│    conditions → equivalence classes       │
└─────────────────┬─────────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────────┐
│ 2. test_case_design                       │
│    Boundary value, equivalence partition, │
│    scenario-based test design             │
└─────────────────┬─────────────────────────┘
                  │
          ┌───────┴───────┐
          ▼               ▼
┌─────────────────┐ ┌─────────────────┐
│ 3. test_oracle  │ │ 4. coverage_    │
│ Generate test   │ │     analysis    │
│ oracles and     │ │  Functional,    │
│ assertions      │ │  structural     │
└────────┬────────┘ │  coverage       │
         │          └────────┬────────┘
         │                   │
         └───────┬───────────┘
                 ▼
┌───────────────────────────────────────────┐
│ 5. test_script_gen                         │
│    Generate executable test scripts       │
│    for SIL/HIL environment                │
└───────────────────────────────────────────┘
    │
    ▼
Output: Test Cases + Oracles + Coverage Report + Test Scripts
```

**适用场景：** SIL/HIL 测试、需求驱动测试、回归测试套件增强

## 4. 缺陷分类工作流 / Bug Triage Workflow

```
Input: Bug Report (description + stack trace + logs)
    │
    ▼
┌───────────────────────────────────────────┐
│ 1. bug_classification                     │
│    Classify by component, type, subsystem │
└─────────────────┬─────────────────────────┘
                  │
          ┌───────┴───────┐
          ▼               ▼
┌─────────────────┐ ┌─────────────────┐
│ 2. severity_    │ │ 3. root_cause_  │
│     assessment  │ │     analysis    │
│  Safety impact, │ │  Pattern match  │
│  frequency,     │ │  + code/stack   │
│  detectability  │ │  trace analysis │
└────────┬────────┘ └────────┬────────┘
         │                   │
         └───────┬───────────┘
                 ▼
┌───────────────────────────────────────────┐
│ 4. fix_recommendation                     │
│    Code snippets, test cases, regression  │
│    risk assessment                        │
└─────────────────┬─────────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────────┐
│ 5. assignment                             │
│    Assign to appropriate team/owner       │
│    based on component & expertise         │
└───────────────────────────────────────────┘
    │
    ▼
Output: Classification + Severity + Root Cause + Fix + Assignment
```

## 5. 架构评审工作流 / Architecture Review Workflow

**适用场景：** 系统/软件架构评审、安全架构审查

**检查项：**
- 软件架构分层与模块化
- 安全架构 (冗余/容错/故障安全)
- 非功能约束 (实时性/内存/延迟)
- ASIL 分解与隔离
- 硬件-软件接口

## 6. 场景生成工作流 / Scenario Generation Workflow

**适用场景：** OpenSCENARIO 场景生成、ODD 定义、关键场景识别

**输出：** 场景目录 + 参数变化 + 验证报告 + OpenSCENARIO 文件

## 7. 合规检查工作流 / Compliance Check Workflow

**适用场景：** ISO 26262 / ASPICE / ISO 21434 模式参考评估（advisory，非认证评估）

**覆盖标准（仅作模式参考，非认证覆盖）：**
- ISO 26262:2018 模式参考（覆盖深度有限）
- ASPICE v3.1 / v4.0 模式参考
- ISO 21434:2021 (Cybersecurity) 模式参考
- ISO 21448:2022 (SOTIF) 模式参考

## 8. 数据管道审查工作流 / Data Pipeline Review Workflow

**适用场景：** AD/ADAS 数据处理管道审查、ML 训练数据质量分析

**检查项：**
- 数据源和转换映射
- 数据质量 (完整性/准确性/一致性/及时性/有效性)
- 预处理流程 (过滤/归一化/增强/标注)
- 管道性能 (吞吐量/延迟/资源利用率)
- 存储效率与版本管理

---

# 🧪 测试 / Testing

## 运行测试 / Running Tests

```bash
# 运行所有测试
pytest tests/ -v

# 运行核心测试
pytest tests/test_core.py -v

# 运行记忆系统测试
pytest tests/test_memory.py -v

# 运行 SafetyBadge API + 弃用包装器测试
pytest tests/test_safety_badge_api.py -v

# 运行 persona 包对外导出契约测试
pytest tests/test_persona_exports.py -v

# 运行编排集成测试
pytest orchestration/tests/ -v

# 带覆盖率报告
pytest tests/ --cov=core --cov=channels --cov-report=term-missing

# 并行运行
pytest tests/ -n auto
```

## 测试结构 / Test Structure

```python
# tests/test_core.py
import pytest
from core import Nonull

@pytest.mark.asyncio
async def test_agent_initialization():
    agent = Nonull()
    assert agent.state.value == "idle"
    assert agent.name == "Nonull"

@pytest.mark.asyncio
async def test_agent_run_completes():
    agent = Nonull()
    result = await agent.run("Test task")
    assert result["status"] in ("completed", "error")

@pytest.mark.asyncio
async def test_safety_guardian_denies_dangerous():
    agent = Nonull()
    with pytest.raises(SafetyViolation):
        await agent.act("exec:rm -rf /", {})

@pytest.mark.asyncio
async def test_subagent_spawn():
    agent = Nonull()
    result = await agent.spawn_subagent(
        task="Analyze data",
        agent_type="reasoning",
    )
    assert result.success
```

```python
# tests/test_memory.py
import pytest
from core.agent_core import WorkingMemory, EpisodicMemory, SemanticMemory

def test_working_memory_store_retrieve():
    wm = WorkingMemory(capacity=10)
    wm.store("test content", importance=0.8)
    results = wm.retrieve("test", k=5)
    assert len(results) == 1
    assert results[0].content == "test content"

def test_working_memory_eviction():
    wm = WorkingMemory(capacity=3)
    for i in range(5):
        wm.store(f"item {i}", importance=0.1)
    assert wm.size <= 3

def test_episodic_memory_prune():
    em = EpisodicMemory(capacity=100, retention_days=1)
    import time
    em.store("old item", importance=0.1)
    # Manually age the entry
    em._entries[-1].timestamp = time.time() - 86400 * 2  # 2 days ago
    pruned = em.prune()
    assert pruned >= 1
```

## 添加新测试 / Adding New Tests

```python
# tests/test_safety.py
import pytest
from safety.guardian import SafetyGuardian
from safety import Action, ActionCategory, Verdict

def test_tool_pre_filter_dangerous():
    guardian = SafetyGuardian(strictness=3)
    action = Action(
        action_id="test_001",
        category=ActionCategory.SYSTEM_COMMAND,
        tool="shell_exec",
        params={"command": "ls -la"},
    )
    verdict = guardian.validate_action(action)
    assert verdict.is_denied()
    assert verdict.score <= 20.0

def test_allow_safe_read_ops():
    guardian = SafetyGuardian(strictness=3)
    action = Action(
        action_id="test_002",
        category=ActionCategory.TOOL_CALL,
        tool="read_file",
        params={"path": "/tmp/test.py"},
    )
    verdict = guardian.validate_action(action)
    assert verdict.is_approved()

def test_context_aware_safety():
    guardian = SafetyGuardian(strictness=3)
    guardian.update_driving_context({
        "speed_kmh": 100,
        "is_moving": True,
        "environment": "highway",
        "weather": "rain",
    })
    action = Action(
        action_id="test_003",
        category=ActionCategory.VEHICLE_CONTROL,
        tool="set_steering",
        params={"angle": 45},
    )
    verdict = guardian.validate_action(action)
    # High speed + rain + highway = higher risk
    assert verdict.score < 60.0
```

---

# 🤝 贡献指南 / Contributing

## 开发环境搭建 / Development Setup

```bash
# 克隆仓库
git clone https://github.com/example/Nonull.git
cd Nonull

# (可选) 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install
```

## 代码规范 / Code Standards

| 规则 | 要求 |
|------|------|
| Python 版本 | 3.10+ |
| 类型注解 | 所有公共 API 必须有完整类型注解 |
| Docstring | Google 风格，中英双语 |
| 行长度 | 100 字符 |
| 格式化 | Black (默认配置) |
| Linting | Ruff (替代 flake8) |
| 类型检查 | mypy (严格模式) |

```python
# 正确示例
async def analyze_function(
    function_name: str,
    hazard_level: HazardLevel,
    context: SafetyContext | None = None,
) -> SafetyReport:
    """执行功能安全分析 | Perform functional safety analysis.

    Args:
        function_name: 功能名称 / Name of the function being analyzed
        hazard_level: 危险等级 / ASIL hazard level
        context: 安全上下文（可选） / Safety context (optional)

    Returns:
        SafetyReport: 安全分析报告 / Safety analysis report
    """
    ...
```

## PR 流程 / PR Process

1. **分支命名：** `feature/<component>`, `fix/<issue>`, `docs/<topic>`
2. **提交信息：** `[Scope] Description (中文 / English)`
3. **预提交检查：**
   ```bash
   # 运行测试
   pytest tests/ -v

   # 运行安全审计
   python -m nonull audit --strictness 5

   # 类型检查
   mypy core/ channels/ safety/

   # 代码格式化
   black core/ channels/ safety/ tests/
   ```
4. **PR 要求：**
   - 新增功能必须有测试覆盖
   - 所有测试必须通过
   - 代码审查必须通过
   - 不直接推送 `main` 或 `develop`

## 技能贡献 / Skill Contribution

```python
# 在 skills/ 目录下创建新技能文件
# skills/my_new_skill.py

from skills.base import BaseSkill, SkillCategory, SkillMetadata

class MyNewSkill(BaseSkill):
    """你的新技能描述"""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="my-new-skill",
            version="1.0.0",
            category=SkillCategory.SAFETY,
            description="你的技能功能描述",
            tags=["safety", "adas"],
        )

    def _execute_impl(self, context):
        # 实现核心逻辑
        return {"result": "processed"}
```

## 文档贡献 / Documentation Contribution

- 所有用户文档必须中英双语
- 使用符合规范的中文和英文
- 保持文风和格式一致
- 示例代码必须可运行

---

# 📄 许可证 / License

Nonull is released under the **MIT License**.

```
MIT License

Copyright (c) 2026 Nonull Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

> **Nonull — Driving the Future of Autonomous Driving AI Agents**
>
> **Nonull 智驾智能体 — 驱动智能驾驶 AI Agent 的未来**
>
> *Safety First. Precision Always. Never Null.*
>
> *安全第一。精准无误。永不为空。*

---

📖 **相关文档 / Related Documentation:**

- [架构详解 Architecture Deep Dive](architecture.md)
- [技能目录 Skills Catalog](skills-catalog.md)
- [README 项目概览](../README.md)
- [AGENT 身份标识](AGENT.md)
