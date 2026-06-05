# Nonull Architecture 架构文档

> **融合 OpenClaw + Hermes Agent + openHuman + Claude Code 的统一智驾智能体架构**
> **Unified Autonomous Driving Agent Architecture Fusing OpenClaw, Hermes Agent, openHuman, and Claude Code**

---

## / 目录 / Table of Contents

1. [架构总览 / Architecture Overview](#1-架构总览--architecture-overview)
2. [四架构融合 / Four-Architecture Fusion](#2-四架构融合--four-architecture-fusion)
   - [2.1 OpenClaw 三层架构](#21-openclaw-三层架构--openclaw-triple-layer)
   - [2.2 Hermes Agent 配置文件隔离](#22-hermes-agent-配置文件隔离--hermes-agent-profile-isolation)
   - [2.3 openHuman 认知架构](#23-openhuman-认知架构--openhuman-cognitive-architecture)
   - [2.4 Claude Code 安全与钩子系统](#24-claude-code-安全与钩子系统--claude-code-safety-and-hooks)
3. [组件描述 / Component Descriptions](#3-组件描述--component-descriptions)
4. [数据流 / Data Flow](#4-数据流--data-flow)
5. [记忆系统 / Memory System](#5-记忆系统--memory-system)
6. [安全系统 / Safety System](#6-安全系统--safety-system)
7. [技能系统 / Skill System](#7-技能系统--skill-system)
8. [工作流模式 / Workflow Patterns](#8-工作流模式--workflow-patterns)
9. [配置体系 / Configuration System](#9-配置体系--configuration-system)

---

## 1. 架构总览 / Architecture Overview

### ASCII 架构图 / ASCII Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Nonull                                   │
│                          ────────────────                                   │
│    "Fusing OpenClaw + Hermes Agent + openHuman + Claude Code"              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        GATEWAY LAYER  (网关层)                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Request     │  │  Auth &      │  │  Rate        │              │   │
│  │  │  Router      │  │  Validation  │  │  Limiter     │              │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │   │
│  │         │                 │                 │                       │   │
│  │  ┌──────┴─────────────────┴─────────────────┴───────┐              │   │
│  │  │              Load Balancer / Dispatcher           │              │   │
│  │  └──────────────────────┬───────────────────────────┘              │   │
│  └─────────────────────────┼───────────────────────────────────────────┘   │
│                            │                                                │
│  ┌─────────────────────────┼───────────────────────────────────────────┐   │
│  │                  AGENT LAYER  (智能体层)  ◄── Hermes Profile        │   │
│  │                            │                      Isolation         │   │
│  │  ┌────────────────────────┴──────────────────────┐                 │   │
│  │  │            Orchestration Engine                │                 │   │
│  │  │  ┌──────────────┐  ┌──────────────┐          │                 │   │
│  │  │  │ Nexus        │  │ Sequential   │          │                 │   │
│  │  │  │ Tendrils     │  │ Pipeline     │          │                 │   │
│  │  │  └──────────────┘  └──────────────┘          │                 │   │
│  │  │  ┌──────────────┐  ┌──────────────┐          │                 │   │
│  │  │  │ Consensus    │  │ Broadcast    │          │                 │   │
│  │  │  └──────────────┘  └──────────────┘          │                 │   │
│  │  └────────────────────┬─────────────────────────┘                 │   │
│  │                       │                                            │   │
│  │  ┌────────────────────┴─────────────────────────┐                 │   │
│  │  │           Skill Registry (工具注册表)          │                 │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐     │                 │   │
│  │  │  │ code-    │ │ safety-  │ │ arch-    │     │                 │   │
│  │  │  │ review   │ │ analysis │ │ design   │     │                 │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘     │                 │   │
│  │  └─────────────────────────────────────────────┘                 │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────┐     │   │
│  │  │           Sub-Agent Manager (子智能体管理器)              │     │   │
│  │  │  Agent A ◄──► Agent B ◄──► Agent C ◄──► Agent D       │     │   │
│  │  └─────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────┬───────────────────────────────────────────┘   │
│                            │                                                │
│  ┌─────────────────────────┼───────────────────────────────────────────┐   │
│  │               CHANNELS LAYER  (通道层)                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │     CLI      │  │   Gateway    │  │  WebSocket   │              │   │
│  │  │   Interface  │  │     API      │  │  Stream      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     MEMORY SYSTEM  (记忆系统)                        │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────┐  ┌────────────────────┐    │   │
│  │  │         NEOCORTEX  (新皮质)          │  │  SUBCONSCIOUS     │    │   │
│  │  │  ┌──────────┐ ┌──────────┐         │  │  (潜意识)          │    │   │
│  │  │  │ Episodic │ │ Semantic │         │  │  ┌────────────┐   │    │   │
│  │  │  │  Memory  │ │  Memory  │         │  │  │ Periodic   │   │    │   │
│  │  │  └──────────┘ └──────────┘         │  │  │ Consolid.  │   │    │   │
│  │  │  ┌──────────┐ ┌──────────┐         │  │  └────────────┘   │    │   │
│  │  │  │Procedural│ │  Index   │         │  │  ┌────────────┐   │    │   │
│  │  │  │  Memory  │ │  Store   │         │  │  │ Pattern    │   │    │   │
│  │  │  └──────────┘ └──────────┘         │  │  │ Discovery  │   │    │   │
│  │  └─────────────────────────────────────┘  │  └────────────┘   │    │   │
│  │                                           └────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     SAFETY SYSTEM  (安全系统)                        │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Deny-First  │  │  ISO 26262   │  │  Audit Log   │              │   │
│  │  │  Validator   │  │  Compliance  │  │  Engine      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │  ┌──────────────┐  ┌──────────────┐                               │   │
│  │  │  Strictness  │  │  Pre/Post    │                               │   │
│  │  │  Levels 1-5  │  │  Hooks      │                               │   │
│  │  └──────────────┘  └──────────────┘                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 四架构融合 / Four-Architecture Fusion

### 2.1 OpenClaw 三层架构 / OpenClaw Triple-Layer

Nonull 采纳了 OpenClaw 的严格三层分离架构，确保每一层都有清晰的职责边界。

Nonull adopts OpenClaw's strict three-layer separation architecture, ensuring clear responsibility boundaries for each layer.

#### Gateway Layer (网关层)

```
Gateway Layer Responsibilities:
├── Request Routing        — route requests to appropriate agent profiles
├── Authentication         — validate API keys, tokens, session IDs
├── Rate Limiting          — enforce per-profile/per-channel rate limits
├── Load Balancing         — distribute workload across agent instances
└── Protocol Translation   — HTTP ↔ internal message format
```

**Key Components:**
- `RequestRouter` — matches incoming requests to registered agent profiles
- `AuthValidator` — pluggable authentication (API key, OAuth, mTLS)
- `RateLimiter` — token bucket algorithm, configurable per channel
- `LoadBalancer` — round-robin or least-connections distribution

**Constraints:**
- Gateway layer MUST NOT contain business logic or domain knowledge
- Gateway layer MUST NOT directly access memory or skill systems
- All gateway operations must complete within 100ms

#### Agent Layer (智能体层)

```
Agent Layer Responsibilities:
├── Task Decomposition     — break complex tasks into sub-tasks
├── Skill Orchestration    — select and invoke appropriate skills
├── Sub-Agent Management   — create, monitor, and collect sub-agents
├── Context Management     — maintain conversation/session context
└── Result Synthesis       — aggregate sub-agent results into coherent output
```

**Key Components:**
- `OrchestrationEngine` — manages workflow patterns (nexus_tendrils, sequential, etc.)
- `SkillRegistry` — global registry of all installed skills
- `SubAgentManager` — lifecycle management for sub-agents
- `ContextManager` — session-level context tracking

**Constraints:**
- Agent Layer MUST NOT directly handle I/O (delegate to Channels)
- Agent Layer MUST validate all skill outputs through safety system
- Maximum 8 concurrent sub-agents per orchestration

#### Channels Layer (通道层)

```
Channels Layer Responsibilities:
├── CLI Interface          — interactive terminal session
├── Gateway API            — RESTful HTTP API
├── WebSocket Stream       — real-time bidirectional communication
├── Input Parsing          — parse and normalize user input
└── Output Formatting      — format agent responses for the channel
```

**Key Components:**
- `CLIChannel` — rich terminal interface with `rich` library
- `APIChannel` — FastAPI-based REST API
- `WSChannel` — WebSocket streaming for real-time updates
- `OutputFormatter` — channel-aware output formatting

**Constraints:**
- Channels Layer MUST NOT contain domain logic
- Channels Layer MUST pass all input through safety validation
- Each channel operates in its own async event loop

### 2.2 Hermes Agent 配置文件隔离 / Hermes Agent Profile Isolation

借鉴 Hermes Agent 的设计模式，Nonull 实现了完整的配置文件隔离系统。

Drawing from Hermes Agent's design patterns, Nonull implements a complete profile isolation system.

#### Profile Structure

```
profiles/
├── default.yaml           # 默认配置 / Default profile (always loadable)
├── adas-engineer.yaml     # ADAS 工程师 / ADAS engineer profile
├── safety-expert.yaml     # 安全专家 / Safety expert profile
├── test-engineer.yaml     # 测试工程师 / Test engineer profile
└── manager.yaml           # 项目经理 / Project manager profile
```

#### Profile Schema

```yaml
profile:
  name: "adas-engineer"          # 配置文件名称 / Profile name
  description: "ADAS 工程师工作配置 / ADAS engineer workspace"

workspace:
  path: "./workspaces/adas"      # 独立工作目录 / Isolated workspace
  max_size: "10GB"               # 工作区上限 / Workspace size limit

model:
  provider: "anthropic"          # 模型提供商 / Model provider
  model_id: "claude-sonnet-4"    # 模型 ID / Model ID
  temperature: 0.2               # 温度参数 / Temperature
  max_tokens: 8192               # 最大 Token 数 / Max tokens

tools:
  allowed: ["code-review", "safety-analysis", "arch-design"]  # 允许的工具集
  blocked: ["deploy", "modify-vehicle-controls"]               # 禁止的工具集

logging:
  level: "DEBUG"                 # 日志级别 / Log level
  audit: true                    # 审计日志 / Audit logging

memory:
  neocortex_namespace: "adas"    # 新皮质隔离命名空间 / Neocortex namespace
  subconscious_enabled: true     # 潜意识循环 / Subconscious loop
```

#### Isolation Guarantees

| Aspect | Isolation Mechanism |
|---|---|
| Workspace | Each profile has its own working directory |
| Tools | Per-profile allow/block lists for tool access |
| Memory | Namespace-based isolation in Neocortex |
| Model | Independent model configuration per profile |
| Context | Full context reset on profile switch |
| Audit | Independent audit log per profile |

### 2.3 openHuman 认知架构 / openHuman Cognitive Architecture

Nonull 借鉴了 openHuman 的双系统认知架构，将记忆分为新皮质 (Neocortex) 和潜意识 (Subconscious) 两部分。

Nonull borrows openHuman's dual-system cognitive architecture, dividing memory into Neocortex and Subconscious systems.

#### Neocortex (新皮质) — 长期记忆 / Long-Term Memory

```
Neocortex Memory Architecture
┌─────────────────────────────────────────────────────────┐
│                   NEOCORTEX (1B tokens)                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Episodic Memory (情景记忆)           │   │
│  │  Stores task executions, user interactions,      │   │
│  │  and their outcomes with timestamps and context   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Semantic Memory (语义记忆)           │   │
│  │  Stores domain knowledge, concepts, facts,       │   │
│  │  and learned relationships in the ADAS domain     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │             Procedural Memory (程序记忆)          │   │
│  │  Stores skill execution patterns, workflow       │   │
│  │  templates, and best-practice procedures          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │                Index Store (索引存储)             │   │
│  │  Vector embeddings for fast similarity search    │   │
│  │  over all memory types (FAISS-based)             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Neocortex Properties:**
- Append-only: once written, memories are immutable
- Capacity: 1 billion tokens (hard limit)
- Index: FAISS-based vector index with cosine similarity
- Retrieval: hybrid (keyword + semantic) search
- Namespace isolation per profile

#### Subconscious (潜意识) — 后台循环 / Background Loop

```
Subconscious Loop (10,000 cycles/day)
┌─────────────────────────────────────────────────────────┐
│                   SUBCONSCIOUS                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Cycle 1: Memory Consolidation                          │
│  ├── Scan recent episodic memories                      │
│  ├── Identify patterns across episodes                  │
│  ├── Extract semantic knowledge                          │
│  └── Update semantic memory with new insights           │
│                                                         │
│  Cycle 2: Pattern Discovery                             │
│  ├── Cluster similar task executions                    │
│  ├── Identify recurring failure modes                   │
│  ├── Discover optimization opportunities                 │
│  └── Update procedural memory with new patterns         │
│                                                         │
│  Cycle 3: Memory Pruning                                │
│  ├── Identify low-utility memories                      │
│  ├── Apply importance scoring                           │
│  ├── Compress or consolidate low-value entries          │
│  └── Free capacity for new memories                     │
│                                                         │
│  Cycle 4: Anomaly Detection                             │
│  ├── Compare current behavior to historical patterns    │
│  ├── Flag statistically unusual outcomes                │
│  ├── Generate anomaly reports                           │
│  └── Alert safety system if critical deviations found   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Subconscious Properties:**
- Runs as a background async task
- 10,000 cycles per day default (configurable)
- Read-only access to Neocortex (never modifies directly)
- Outputs are proposals, not commands (agent must accept)
- Anomaly detection can trigger safety system alerts

#### Memory Indexing

```python
# Pseudocode: Neocortex Index Flow
class NeocortexIndex:
    def __init__(self, capacity: int = 1_000_000_000):
        self.episodic = EpisodicStore(capacity // 3)
        self.semantic = SemanticStore(capacity // 3)
        self.procedural = ProceduralStore(capacity // 3)
        self.index = FAISSIndex(dimension=1536)  # embedding dimension

    async def store(self, memory: Memory) -> str:
        # 1. Embed the memory content
        embedding = await self.embed(memory.content)

        # 2. Store in the appropriate memory type store
        mem_id = await self._type_store(memory).add(memory)

        # 3. Index the embedding
        await self.index.add(mem_id, embedding)

        # 4. Trigger subconscious consolidation signal
        await self.signal_consolidation(memory)

        return mem_id

    async def retrieve(self, query: str, top_k: int = 10) -> list[Memory]:
        # 1. Embed query
        query_emb = await self.embed(query)

        # 2. Similarity search
        mem_ids, scores = await self.index.search(query_emb, top_k)

        # 3. Retrieve full memories
        memories = []
        for mem_id in mem_ids:
            memory = await self._fetch(mem_id)
            memories.append(memory)

        return memories
```

### 2.4 Claude Code 安全与钩子系统 / Claude Code Safety and Hooks

Nonull 借鉴 Claude Code 的安全设计模式，实现了拒绝优先的安全策略和完整的钩子系统。

Nonull adopts Claude Code's safety design patterns, implementing a deny-first safety policy and comprehensive hook system.

#### Deny-First Safety (拒绝优先安全策略)

```
Safety Validation Flow:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Request  │───►│ Deny-    │───►│ Strict-  │───►│ Audit    │
│          │    │ First    │    │ ness     │    │ Log      │
│ Action   │    │ Check    │    │ Eval     │    │          │
└──────────┘    └────┬─────┘    └────┬─────┘    └──────────┘
                     │               │
                     ▼               ▼
                  ALLOWED?       LEVEL OK?
                  No → DENY      No → DENY
                  Yes → NEXT     Yes → NEXT
```

**Strictness Levels:**

| Level | Name | Behavior |
|---|---|---|
| 1 | Minimal | Allow all, log only errors |
| 2 | Basic | Block known dangerous patterns, log warnings |
| 3 | Standard | Block all unregistered tools, log all actions |
| 4 | High | Require explicit confirmation for all tool calls, full audit |
| 5 | Maximum | Deny everything by default, explicit allow-list only, comprehensive audit |

#### ISO 26262 Compliance

Nonull 的安全系统遵循 ISO 26262 功能安全标准：

The safety system follows ISO 26262 functional safety standards:

```
ISO 26262 Implementation:
├── Part 3: Hazard Analysis (HARA)
│   ├── Hazard identification
│   ├── Hazard classification (ASIL A-D)
│   └── Safety goals definition
│
├── Part 4: System-Level
│   ├── Technical safety requirements
│   ├── System design validation
│   └── Safety validation
│
├── Part 5: Hardware-Level
│   └── (Delegated to vehicle platform)
│
├── Part 6: Software-Level
│   ├── Software safety requirements
│   ├── Software architectural design
│   ├── Software unit testing
│   └── Software integration testing
│
└── Part 8: Support Processes
    ├── Configuration management
    ├── Change management
    ├── Verification
    └── Documentation
```

#### Hook System (钩子系统)

```
Hook Execution Order:
Pre-hooks → Validation → Execution → Post-hooks → Audit

Example Hook Chain:
┌────────────────────────────────────────────────────┐
│                  SKILL EXECUTION                    │
├────────────────────────────────────────────────────┤
│                                                     │
│  PRE-HOOKS:                                         │
│  ├── validate_input(parameters) → bool              │
│  ├── check_privileges(profile, skill) → bool        │
│  ├── rate_limit_check(channel) → bool               │
│  └── memory_context_inject(context) → Context       │
│                                                     │
│  VALIDATION:                                        │
│  ├── safety_validator(action) → SafetyVerdict      │
│  └── strictness_filter(verdict) → bool              │
│                                                     │
│  EXECUTION:                                         │
│  └── skill.execute(context, params) → Result        │
│                                                     │
│  POST-HOOKS:                                        │
│  ├── validate_output(result) → bool                 │
│  ├── memory_store(context, result) → None           │
│  ├── notify_subscribers(event) → None               │
│  └── format_output(result, channel) → Response      │
│                                                     │
│  AUDIT:                                             │
│  └── audit_log.write(Record) → None                 │
│                                                     │
└────────────────────────────────────────────────────┘
```

**Hook Registration:**

```python
from Nonull.hooks import hook, HookPriority

@hook("pre.skill.execute", priority=HookPriority.HIGH)
async def validate_input(context: HookContext) -> bool:
    """验证技能输入 | Validate skill input."""
    if not context.params.get("function_name"):
        await context.reject("Function name is required")
        return False
    return True
```

---

## 3. 组件描述 / Component Descriptions

### Core Components

| Component | Description | 描述 |
|---|---|---|
| `Nonull` | Main agent class — entry point for all interactions | 主智能体类，所有交互的入口 |
| `OrchestrationEngine` | Manages workflow patterns and sub-agent lifecycle | 管理工作流模式和子智能体生命周期 |
| `SkillRegistry` | Global registry for all skills with versioning | 全局技能注册表，支持版本管理 |
| `MemorySystem` | Dual-system memory (Neocortex + Subconscious) | 双系统记忆（新皮质 + 潜意识） |
| `SafetySystem` | Deny-first safety with ISO 26262 compliance | 拒绝优先安全系统，ISO 26262 合规 |
| `ChannelManager` | Multi-channel I/O abstraction | 多通道 I/O 抽象层 |
| `ProfileManager` | Hermes-style profile isolation | Hermes 风格的配置文件隔离管理 |
| `HookManager` | Pre/post execution hook system | 执行前后钩子系统 |
| `SubAgentManager` | Sub-agent creation, monitoring, and result collection | 子智能体创建、监控和结果收集 |
| `ContextManager` | Session and profile context tracking | 会话和配置文件上下文追踪 |

### Component Interaction Diagram

```
User Input
    │
    ▼
┌──────────┐     ┌────────────┐     ┌──────────────┐
│ Channel  │────►│  Gateway   │────►│   Profile    │
│ (CLI/API)│     │  Layer     │     │   Manager    │
└──────────┘     └─────┬──────┘     └──────┬───────┘
                       │                   │
                       ▼                   ▼
                 ┌────────────┐     ┌──────────────┐
                 │  Safety    │     │  Context     │
                 │  System    │     │  Manager     │
                 └──────┬─────┘     └──────┬───────┘
                        │                  │
                        ▼                  ▼
                 ┌──────────────────────────────┐
                 │    Orchestration Engine       │
                 │  ┌────────────────────────┐   │
                 │  │  Nexus Tendrils (default)│   │
                 │  │  Sequential / Consensus │   │
                 │  │  Broadcast              │   │
                 │  └───────────┬────────────┘   │
                 └──────────────┼────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
         ┌──────────┐   ┌──────────┐   ┌──────────┐
         │  Skill   │   │  Skill   │   │  Skill   │
         │ Registry │   │  Exec 1  │   │  Exec 2  │
         └────┬─────┘   └────┬─────┘   └────┬─────┘
              │              │               │
              ▼              ▼               ▼
         ┌──────────────────────────────────────┐
         │           Memory System               │
         │  ┌──────────┐  ┌────────────────┐    │
         │  │ Neocortex │  │  Subconscious  │    │
         │  └──────────┘  └────────────────┘    │
         └──────────────────────────────────────┘
```

---

## 4. 数据流 / Data Flow

### 4.1 Simple Request Flow (简单请求流)

```
User: "Review this ADAS C++ code"
  │
  │  1. CLI Channel receives input
  ▼
CLIChannel.parse("Review this ADAS C++ code")
  │
  │  2. Gateway routes to default profile
  ▼
RequestRouter.route("default", input)
  │
  │  3. Safety validation (deny-first)
  ▼
SafetySystem.validate("code-review", strictness=4)
  │  └── Pre-hooks run: validate_input, check_privileges
  │
  │  4. Profile isolation applied
  ▼
ProfileManager.load("default")
  │  └── Workspace, tools, model config loaded
  │
  │  5. Context injection from memory
  ▼
MemorySystem.retrieve(context="adas c++ review")
  │  └── Neocortex: find similar past reviews
  │
  │  6. Orchestration decides pattern
  ▼
OrchestrationEngine.dispatch("code-review", pattern="sequential")
  │  └── Single skill execution (no sub-agents needed)
  │
  │  7. Skill execution
  ▼
SkillRegistry.get("code-review").execute(code)
  │  └── Analyzes code, produces review comments
  │
  │  8. Post-hooks and memory storage
  ▼
PostHooks: validate_output → memory_store → format_output
  │
  │  9. Audit log
  ▼
AuditLog.write(record)
  │
  │  10. Response to user
  ▼
User: "Found 3 critical issues and 5 warnings..."
```

### 4.2 Complex Workflow Flow (复杂工作流流)

```
User: "Perform a full HARA on the AEB system"
  │
  │  1-4. Same as simple flow through safety and profile
  ▼
OrchestrationEngine.dispatch("safety-analysis", pattern="nexus_tendrils")
  │
  │  5. Task decomposition
  ▼
Decompose: ["Identify hazards", "Classify ASIL", "Define safety goals",
            "Verify coverage", "Generate report"]
  │
  │  6. Spawn sub-agents (up to 8 concurrent)
  ▼
SubAgentManager.spawn_batch([
  SubAgent("Identify hazards", skill="safety-analysis", params={...}),
  SubAgent("Classify ASIL", skill="safety-analysis", params={...}),
  SubAgent("Define safety goals", skill="safety-analysis", params={...}),
  SubAgent("Verify coverage", skill="safety-analysis", params={...}),
  SubAgent("Generate report", skill="document-generation", params={...}),
])
  │
  │  7. Each sub-agent follows its own flow
  ▼
  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
  │  A  │  │  B  │  │  C  │  │  D  │  │  E  │
  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘
     │        │        │        │        │
     └────────┴────────┴────────┴────────┘
                        │
                        ▼
               ResultSynthesis.aggregate()
                        │
                        ▼
                  FinalReport
                        │
                        ▼
                  PostHooks → Audit → User
```

---

## 5. 记忆系统 / Memory System

### 5.1 System Architecture (系统架构)

```
┌──────────────────────────────────────────────────────────────┐
│                    MEMORY SYSTEM                              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                  NEOCORTEX (新皮质)                    │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │  Episodic    │  │  Semantic    │  Capacity: 1B   │    │
│  │  │  Store       │  │  Store       │  tokens total   │    │
│  │  │              │  │              │                 │    │
│  │  │  • Task logs │  │  • Domain    │  Append-only    │    │
│  │  │  • Outcomes  │  │    knowledge │  Immutable      │    │
│  │  │  • Sessions  │  │  • Concepts  │                 │    │
│  │  │  • Errors    │  │  • Patterns  │  FAISS index    │    │
│  │  └──────────────┘  └──────────────┘  1536d          │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │  Procedural  │  │  Index       │                 │    │
│  │  │  Store       │  │  Store       │                 │    │
│  │  │              │  │  (FAISS)     │                 │    │
│  │  │  • Workflows │  │              │                 │    │
│  │  │  • Templates │  │  • Embedding │                 │    │
│  │  │  • Patterns  │  │  • Metadata  │                 │    │
│  │  └──────────────┘  └──────────────┘                 │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │               SUBCONSCIOUS (潜意识)                    │    │
│  │                                                       │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │        Background Loop (10,000 cycles/day)    │    │    │
│  │  │                                              │    │    │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │    │    │
│  │  │  │Memory   │  │Pattern  │  │Anomaly  │     │    │    │
│  │  │  │Consolid.│  │Discover │  │Detect   │     │    │    │
│  │  │  └─────────┘  └─────────┘  └─────────┘     │    │    │
│  │  │  ┌────────────────────────────────────┐    │    │    │
│  │  │  │   Importance Scorer & Pruner       │    │    │    │
│  │  │  └────────────────────────────────────┘    │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │               WORKING MEMORY (工作记忆)                │    │
│  │                                                       │    │
│  │  • Session context (volatile, cleared on profile      │    │
│  │    switch or session end)                             │    │
│  │  • Current task state                                 │    │
│  │  • Active sub-agent results (temporary)               │    │
│  │  • Priority queue for subconscious signals            │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Memory Operations (记忆操作)

| Operation | Description | Async | Cacheable |
|---|---|---|---|
| `store(memory)` | Write to Neocortex (append-only) | Yes | No |
| `retrieve(query, k)` | Search Neocortex by similarity | Yes | Yes (5min) |
| `recall(episode_id)` | Exact recall of specific episode | Yes | Yes |
| `consolidate()` | Trigger subconscious cycle | Yes | N/A |
| `forget_session()` | Clear working memory only | No | N/A |
| `prune(threshold)` | Compress low-importance memories | Yes | N/A |

### 5.3 Memory Capacity Management (容量管理)

```python
# Capacity management strategy
class CapacityManager:
    def __init__(self, max_tokens: int = 1_000_000_000):
        self.max_tokens = max_tokens
        self.watermark_high = int(max_tokens * 0.85)  # 850M
        self.watermark_low = int(max_tokens * 0.60)   # 600M

    async def check_capacity(self, current_usage: int) -> CapacityAction:
        if current_usage >= self.max_tokens:
            return CapacityAction.BLOCK  # Cannot write
        elif current_usage >= self.watermark_high:
            return CapacityAction.PRUNE  # Trigger pruning
        elif current_usage >= self.watermark_low:
            return CapacityAction.WARN   # Log warning
        else:
            return CapacityAction.OK     # Normal operation

    async def prune(self, store: MemoryStore) -> int:
        """Remove or compress low-importance memories."""
        candidates = await store.find_low_importance(ratio=0.1)
        freed = 0
        for mem in candidates:
            if mem.importance < 0.2:
                # Remove entirely
                await store.delete(mem.id)
                freed += mem.token_count
            elif mem.importance < 0.5:
                # Compress: keep summary only
                summary = await self.summarize(mem.content)
                await store.update(mem.id, content=summary)
                freed += mem.token_count - len(summary)
        return freed
```

---

## 6. 安全系统 / Safety System

### 6.1 Architecture (架构)

```
┌──────────────────────────────────────────────────────────────┐
│                      SAFETY SYSTEM                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │            DENY-FIRST VALIDATOR (拒绝优先验证器)       │    │
│  │                                                       │    │
│  │  Input: (action, params, profile, channel)            │    │
│  │  Process:                                              │    │
│  │    1. Is action in global deny-list? → DENY           │    │
│  │    2. Is action in profile deny-list? → DENY          │    │
│  │    3. Is action in global allow-list? → CONTINUE      │    │
│  │    4. Is action in profile allow-list? → CONTINUE     │    │
│  │    5. Strictness >= 4 → request confirmation          │    │
│  │    6. Strictness == 5 → require explicit allow        │    │
│  │  Output: SafetyVerdict(ALLOW | DENY | CONFIRM)        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │           ISO 26262 COMPLIANCE MODULE                  │    │
│  │                                                       │    │
│  │  • HARA (Hazard Analysis and Risk Assessment)         │    │
│  │  • ASIL classification (A, B, C, D)                   │    │
│  │  • Safety goal definition and validation              │    │
│  │  • Functional safety requirement traceability         │    │
│  │  • Safety case generation                             │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              AUDIT LOG ENGINE (审计日志引擎)            │    │
│  │                                                       │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │    │
│  │  │  SQLite     │  │  JSON       │  │  Structured │  │    │
│  │  │  Storage    │  │  Export     │  │  Query API  │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │    │
│  │                                                       │    │
│  │  Log Entry Format:                                    │    │
│  │  {                                                     │    │
│  │    "timestamp": "2026-06-05T10:30:00Z",              │    │
│  │    "action": "code-review",                            │    │
│  │    "profile": "default",                               │    │
│  │    "channel": "cli",                                   │    │
│  │    "strictness": 4,                                    │    │
│  │    "verdict": "ALLOW",                                 │    │
│  │    "duration_ms": 1234,                                │    │
│  │    "input_hash": "sha256:...",                         │    │
│  │    "output_hash": "sha256:...",                        │    │
│  │    "sub_agent_count": 3                                │    │
│  │  }                                                     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              HOOK EXECUTOR (钩子执行器)                │    │
│  │                                                       │    │
│  │  Registry of pre/post hooks with priority ordering    │    │
│  │  Hooks can: REJECT | MODIFY | PASS | LOG              │    │
│  │  Pre-hooks: input validation, privilege check         │    │
│  │  Post-hooks: output validation, memory store          │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Safety Levels Configuration (安全级别配置)

```yaml
safety:
  strictness: 4
  deny_first: true
  iso26262: true
  audit_log: true

  # Deny lists (global)
  global_deny:
    - action: "modify_vehicle_controls"
      reason: "Direct vehicle control modification is prohibited"
    - action: "deploy_to_production"
      reason: "Production deployment requires separate CI/CD pipeline"
    - action: "disable_audit"
      reason: "Audit log cannot be disabled"

  # Allow lists (global)
  global_allow:
    - action: "code-review"
    - action: "safety-analysis"
    - action: "architecture-design"
    - action: "requirement-analysis"
    - action: "test-generation"
    - action: "perf-analysis"
    - action: "regression-check"
    - action: "document-generation"

  # Strictness-specific rules
  rules:
    level_4:
      require_confirmation: true
      max_sub_agents: 8
      max_tokens_per_call: 16384
      log_all_inputs: true
      log_all_outputs: true
    level_5:
      allow_list_only: true
      max_sub_agents: 4
      max_tokens_per_call: 8192
      require_approval_queue: true
      real_time_audit_stream: true
```

### 6.3 Safety Integration Points (安全集成点)

```
Integration Points:
├── Channel Input    → SafetySystem.validate_input()
├── Skill Dispatch   → SafetySystem.validate_action()
├── Sub-Agent Create → SafetySystem.validate_spawn()
├── Memory Write     → SafetySystem.validate_memory()
├── Profile Switch   → SafetySystem.validate_switch()
├── Config Change    → SafetySystem.validate_config()
└── Model Call       → SafetySystem.validate_prompt()
```

---

## 7. 技能系统 / Skill System

### 7.1 Architecture (架构)

```
┌──────────────────────────────────────────────────────────────┐
│                     SKILL SYSTEM                              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │               SKILL REGISTRY (技能注册表)              │    │
│  │                                                       │    │
│  │  Skills are stored in a global registry with:         │    │
│  │  • name (unique identifier)                           │    │
│  │  • version (semantic versioning)                      │    │
│  │  • description (bilingual)                            │    │
│  │  • safety_level (1-5)                                 │    │
│  │  • dependencies (Python packages)                     │    │
│  │  • entry_point (Python module path)                   │    │
│  │                                                       │    │
│  │  Operations: register, unregister, list, get, update  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │            SKILL EXECUTION FLOW                        │    │
│  │                                                       │    │
│  │  1. Resolve: find skill in registry by name           │    │
│  │  2. Validate: check safety_level <= agent strictness  │    │
│  │  3. Load: import skill module dynamically             │    │
│  │  4. Prepare: inject context and parameters            │    │
│  │  5. Execute: run skill (sync or async)                │    │
│  │  6. Validate output: post-execution checks            │    │
│  │  7. Store: save to episodic memory                    │    │
│  │  8. Return: formatted result                           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │            SKILL DISCOVERY (技能发现)                  │    │
│  │                                                       │    │
│  │  • Auto-discover: scan configured paths for skills    │    │
│  │  • Marketplace: download skills from remote registry  │    │
│  │  • Manual install: register by file path              │    │
│  │  • Version resolution: handle dependency conflicts    │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 Skill Base Class (技能基类)

```python
# Nonull/skill_base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Any


class SafetyLevel(IntEnum):
    """技能安全级别 / Skill safety level (1=minimal, 5=maximum)."""
    MINIMAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    MAXIMUM = 5


class SkillCategory(IntEnum):
    """技能分类 / Skill category."""
    CODE = auto()
    SAFETY = auto()
    ARCHITECTURE = auto()
    REQUIREMENT = auto()
    TEST = auto()
    PERFORMANCE = auto()
    DOCUMENT = auto()
    GENERAL = auto()


@dataclass
class SkillManifest:
    """技能清单 / Skill manifest."""
    name: str
    version: str
    description: str                # Bilingual: "中文 / English"
    category: SkillCategory
    safety_level: SafetyLevel
    requires: list[str]             # Python dependencies
    author: str = "Nonull"
    entry_point: str = ""
    auto_discover: bool = True


class BaseSkill(ABC):
    """Base class for all Nonull skills."""

    manifest: SkillManifest

    @abstractmethod
    async def execute(self, context: "SkillContext", **params: Any) -> "SkillResult":
        """执行技能逻辑 | Execute the skill logic.

        Args:
            context: 执行上下文 / Execution context
            **params: 技能参数 / Skill parameters

        Returns:
            SkillResult: 执行结果 / Execution result
        """
        ...
```

### 7.3 Built-in Skills (内置技能)

| Skill | Category | Safety Level | Description |
|---|---|---|---|
| `code-review` | CODE | 2 | Review ADAS C/C++/Python code |
| `safety-analysis` | SAFETY | 4 | HARA, FMEA, FTA analysis |
| `architecture-design` | ARCHITECTURE | 2 | System architecture design |
| `requirement-analysis` | REQUIREMENT | 3 | Requirements traceability |
| `test-generation` | TEST | 2 | Automatic test case generation |
| `perf-analysis` | PERFORMANCE | 1 | Performance profiling |
| `regression-check` | CODE | 2 | Regression impact analysis |
| `document-generation` | DOCUMENT | 1 | Documentation generation |

---

## 8. 工作流模式 / Workflow Patterns

### 8.1 Nexus Tendrils (默认模式)

Nexus Tendrils 是最强大的工作流模式，通过动态分形分解将复杂任务拆解为多个子任务并行执行。

Nexus Tendrils is the most powerful workflow pattern, decomposing complex tasks through dynamic fractal decomposition and executing sub-tasks in parallel.

```
Input: "Analyze the software architecture of the AEB system"

Decomposition:
├── 1. System Context Analysis
│   ├── 1.1 Identify system boundaries
│   ├── 1.2 Identify external interfaces
│   └── 1.3 Identify safety requirements
├── 2. Software Architecture Review
│   ├── 2.1 Layer structure analysis
│   ├── 2.2 Component interaction analysis
│   └── 2.3 Data flow analysis
├── 3. Safety Architecture Evaluation
│   ├── 3.1 ASIL decomposition check
│   ├── 3.2 Freedom-from-interference analysis
│   └── 3.3 Safety mechanism identification
├── 4. Standards Compliance Check
│   ├── 4.1 ISO 26262 part 6 compliance
│   ├── 4.2 ASPICE compliance
│   └── 4.3 Coding standards compliance
└── 5. Report Generation
    ├── 5.1 Findings compilation
    ├── 5.2 Risk assessment
    └── 5.3 Recommendations

Execution: Up to 8 sub-agents in parallel
Synthesis: Aggregated report with cross-references
```

### 8.2 Sequential Pipeline

```
Input → [Skill A] → [Skill B] → [Skill C] → Output

Example: Safety Analysis Pipeline
Input: "AEB system requirements"
  │
  ▼
[requirement-analysis]
  │  Parse requirements, extract safety-relevant items
  ▼
[safety-analysis (HARA)]
  │  Identify hazards, classify ASIL
  ▼
[safety-analysis (FMEA)]
  │  Analyze failure modes and effects
  ▼
[document-generation]
  │  Generate safety report
  ▼
Output: Complete safety analysis report
```

### 8.3 Consensus Review

```
Input: "Review this braking algorithm"

┌───────────────────────────────────────┐
│  Sub-Agent 1: Functional Safety Expert │
│  Focus: ISO 26262 compliance           │
├───────────────────────────────────────┤
│  Sub-Agent 2: Performance Engineer     │
│  Focus: Real-time constraints          │
├───────────────────────────────────────┤
│  Sub-Agent 3: Domain Expert            │
│  Focus: Braking physics correctness    │
└───────────┬───────────┬───────────────┘
            │           │
            ▼           ▼
      ┌──────────────────────┐
      │   Consensus Engine   │
      │   ────────────────   │
      │   1. Compare findings │
      │   2. Resolve conflicts│
      │   3. Priority ranking │
      │   4. Final verdict    │
      └──────────────────────┘
```

### 8.4 Broadcast

```
Input: "Research latest ADAS sensor technologies"

┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Radar    │ │  LiDAR   │ │  Camera  │ │ Ultrasonic│
│  Research │ │ Research │ │ Research │ │ Research  │
└─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘
      │            │            │            │
      └────────────┴────────────┴────────────┘
                        │
                  ┌─────┴─────┐
                  │  Summary  │
                  │ Synthesis │
                  └───────────┘
```

### Pattern Selection Guide

| Task Type | Recommended Pattern | Max Agents |
|---|---|---|
| Code review | Sequential or Consensus | 3-5 |
| Safety analysis | Nexus Tendrils | 5-8 |
| Architecture design | Nexus Tendrils | 5-8 |
| Requirements analysis | Sequential | 2-3 |
| Test generation | Broadcast | 4-8 |
| Performance analysis | Sequential | 2-3 |
| Research / Exploration | Broadcast | 4-16 |
| Document generation | Sequential | 1-2 |

---

## 9. 配置体系 / Configuration System

### 9.1 Configuration Hierarchy (配置层级)

```
Configuration Resolution Order:
1. Default values (hardcoded)
2. config/config.yaml (global defaults)
3. config/profiles/<name>.yaml (profile-specific, overrides global)
4. Environment variables (overrides everything)
5. CLI arguments (highest priority)

Example Resolution:
agent.mode:
  - Default: "interactive"
  - config.yaml: "interactive"
  - profile adas.yaml: "autonomous"
  - env: NONULL_MODE="plan"
  - CLI: --mode plan
  → Final: "plan"
```

### 9.2 Configuration Schema (配置模式)

```python
# Nonull/config/schema.py
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AgentMode(str, Enum):
    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"
    PLAN = "plan"


class ModelConfig(BaseModel):
    provider: str = "auto"
    temperature: float = 0.2
    max_tokens: int = 4096


class NeocortexConfig(BaseModel):
    enabled: bool = True
    capacity: int = 1_000_000_000  # 1B tokens
    index_speed: str = "fast"


class SubconsciousConfig(BaseModel):
    enabled: bool = True
    cycles_per_day: int = 10_000


class MemoryConfig(BaseModel):
    neocortex: NeocortexConfig = Field(default_factory=NeocortexConfig)
    subconscious: SubconsciousConfig = Field(default_factory=SubconsciousConfig)


class SafetyConfig(BaseModel):
    strictness: int = Field(default=4, ge=1, le=5)
    deny_first: bool = True
    iso26262: bool = True
    audit_log: bool = True


class OrchestrationConfig(BaseModel):
    max_concurrent_agents: int = 8
    default_pattern: str = "nexus_tendrils"
    workflow_persistence: bool = True


class SkillsConfig(BaseModel):
    auto_discover: bool = True
    marketplace_enabled: bool = True


class ChannelConfig(BaseModel):
    type: str  # "cli" | "gateway"


class ProfileConfig(BaseModel):
    workspace: str = "./workspace"
    log_level: str = "INFO"


class AgentConfig(BaseModel):
    name: str = "Nonull"
    version: str = "1.0.0"
    mode: AgentMode = AgentMode.INTERACTIVE
    model: ModelConfig = Field(default_factory=ModelConfig)


class RootConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    channels: list[ChannelConfig] = [ChannelConfig(type="cli")]
    profiles: dict[str, ProfileConfig] = {
        "default": ProfileConfig()
    }
```

---

> **Architecture is the foundation. Fusion is the strength. Safety is the commitment.**
> **架构是基础。融合是力量。安全是承诺。**
