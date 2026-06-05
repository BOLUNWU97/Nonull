# Nonull — Claude Code Project Instructions

You are working on **Nonull (智驾智能体)**, a domain-specific AI Agent framework for autonomous driving that fuses four major architectures: **OpenClaw**, **Hermes Agent**, **openHuman**, and **Claude Code**.

---

## / 核心原则 / Core Principles

1. **四架构融合优先** — All design decisions must respect and leverage the fusion of OpenClaw, Hermes Agent, openHuman, and Claude Code patterns. Do not break the architectural consistency.
2. **安全第一 / Safety First** — Apply deny-first safety logic. Never bypass safety checks. The safety layer in this project is **advisory only** (see disclaimer below) — it does **not** implement ISO 26262 ASIL-D requirements.
3. **双语文档 / Bilingual Documentation** — All user-facing documentation MUST be in both Chinese and English.
4. **技能驱动 / Skill-Driven** — Extend functionality through skills registered in the tool registry, not by modifying core agent code.
5. **测试覆盖 / Test Coverage** — Core tests and memory tests must pass before any commit.

---

## / 🚨 营销文案红线 / Marketing Copy Red Lines

**Never claim ISO 26262 / ASIL-D compliance in user-facing copy.** Nonull is an internal ADAS engineering assistant — **not** a certified safety product. The following claims are forbidden in README, docs, comments, commit messages, badges, or any user-facing output:

- ❌ "ASIL-D Ready" / "ISO 26262 Compliant" / "功能安全认证" / "车规级"
- ❌ "production-ready" / "量产就绪" / "可上车的安全产品"
- ❌ "certified safety mechanism" / "certified safety element"
- ❌ Any badge, image, or text implying formal ISO 26262 / ASIL-D / ASPICE certification
- ❌ "MC/DC 覆盖", "形式化验证", "SEooC", "freedom from interference" — these describe certified safety processes that this project does **not** implement

**Acceptable alternatives**:

- ✅ "Advisory safety layer" / "建议性安全层" / "开发助手级安全检查"
- ✅ "ISO 26262 / MISRA / ASPICE pattern references" / "基于标准模式，不是认证"
- ✅ "Risk hints and check templates" / "风险提示与检查模板"
- ✅ "Internal developer assistant" / "内部开发助手"

If a user asks for safety/ISO 26262 features, always state clearly that the project's safety support is **advisory only** and must not be relied on for production or safety-critical decisions.

**在用户可见的文案中，绝不可声称 ISO 26262 / ASIL-D 合规。** 详见 `config/config.yaml` 中的 `safety.disclaimer: "advisory_only"` 设置。

---

## / 文件结构规则 / File Structure Rules

```
Nonull/
├── README.md               # Project overview (Chinese + English)
├── CLAUDE.md                # This file — Claude Code instructions
├── requirements.txt         # Python dependencies
├── config/
│   ├── config.yaml          # Main configuration
│   └── profiles/            # Profile isolation (Hermes-style)
│       └── default.yaml
├── docs/
│   ├── architecture.md      # Architecture documentation
│   └── skills-catalog.md    # Skills catalog
├── examples/                # Usage examples
│   ├── quickstart.py
│   ├── code_review.py
│   ├── safety_analysis.py
│   └── multi_agent_workflow.py
└── tests/                   # Test suite
    ├── test_core.py
    └── test_memory.py
```

---

## / 编码约定 / Coding Conventions

### Python Style

- Use Python 3.10+ type hints consistently
- Follow PEP 8 with 100-character line limit
- Use Google-style docstrings (中文 + English)
- Async-first for I/O operations; sync for CPU-bound tasks
- All public APIs must have type annotations

```python
async def analyze_safety(
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

### Configuration

- YAML for configuration files
- Use `pydantic.BaseModel` for all config models
- Sensitive values via environment variables, not config files

### Testing

- pytest with async support
- Use `pytest-asyncio` for async tests
- Mock external tools/skills in tests
- Memory system tests must verify both Neocortex and Subconscious
- **Guard test**: `tests/test_no_experimental_imports.py` enforces that no production code under `core/`, `memory/`, `safety/`, `skills/`, `orchestration/`, `persona/`, `channels/`, `hooks/`, `config/`, `examples/`, or `nonull/` may import from `experimental/`. This is run automatically by CI.

---

## / ⚠️ Experimental Modules

The `experimental/` directory contains modules that are **NOT production-ready**:

- `experimental/consciousness/` — Self-evolving memory (experimental)
- `experimental/evolution/` — Self-evolution (越用越聪明) (experimental)

These modules:
- Are non-deterministic and mostly untested
- Implement self-modifying/self-aware behavior
- Are incompatible with ISO 26262 "freedom from unacceptable risk"
- Must NOT be wired into any safety-critical pipeline

Do not import from these modules in any code that touches a vehicle control decision.
For autonomous driving contexts, treat them as opt-in research code only.

See `experimental/README.md` for full warnings.

---

## / 架构约束 / Architecture Constraints

### OpenClaw Layer Rules

| Layer | Responsibility | Constraint |
|---|---|---|
| Gateway | Routing, auth, rate limiting | Must not contain business logic |
| Agent | Skill orchestration, task decomposition | Must not directly handle I/O |
| Channels | CLI, API, WebSocket adapters | Must not contain domain logic |

### Hermes Profile Rules

- Each profile is fully isolated: own workspace, tools, model config
- Profile switching must clear all session state
- Default profile must always be loadable

### openHuman Memory Rules

- Neocortex: append-only, immutable after write
- Subconscious: periodic consolidation, never modify Neocortex directly
- Memory capacity is configurable, default ~10K entries per layer (in-memory backend; see docs/architecture.md §5.4 for swap-in backends)

### Claude Code Safety Rules

- All tool invocations go through deny-first validation
- Safety strictness levels 1-5 (5 = maximum)
- Every user interaction must be logged at strictness >= 3
- Never disable audit logging

---

## / 技能开发指南 / Skill Development Guide

### Skill Structure

```python
# skills/my_skill.py
from skills.base import BaseSkill

class MySkill(BaseSkill):
    """技能名称 | Skill name (中文 + English)."""

    name = "my-skill"
    description = "技能描述 | Skill description"
    version = "1.0.0"
    requires = ["dependency1>=1.0"]
    safety_level = 2  # 1-5 safety strictness required

    async def execute(self, context: SkillContext, **params) -> SkillResult:
        ...
```

### Skill Registration

```bash
# Register a skill
python -m nonull skill register path/to/my_skill.py

# List installed skills
python -m nonull skill list

# Unregister a skill
python -m nonull skill remove my-skill
```

---

## / 工作流模式 / Workflow Patterns

Use the appropriate pattern based on task complexity:

| Pattern | Use Case | Max Agents |
|---|---|---|
| `nexus_tendrils` | Complex multi-step tasks (default) | 8 |
| `sequential` | Linear pipeline tasks | N |
| `consensus` | Review/validation tasks | 5 |
| `broadcast` | Parallel exploration tasks | 16 |

---

## / 安全规则 / Safety Rules

1. **Never** execute code that modifies vehicle control systems without explicit user consent and safety level >= 4
2. **Never** bypass the `deny_first` safety check
3. **Always** log safety-relevant decisions with full context
4. **Never** disable or reduce `audit_log` in production
5. **Always** validate that skill safety_level <= configured agent strictness

---

## / 记忆系统维护 / Memory System Maintenance

```bash
# Inspect Neocortex memory
python -m nonull memory inspect --type neocortex

# Run subconscious consolidation manually
python -m nonull memory consolidate

# Clear session memory (does NOT affect Neocortex)
python -m nonull memory clear-session

# Check memory usage
python -m nonull memory usage
```

---

## / 常用命令 / Common Commands

```bash
# Run agent in interactive mode
python -m nonull

# Run with a specific profile
python -m nonull --profile adas-engineer

# Run tests
pytest tests/ -v

# Run safety audit
python -m nonull audit --strictness 5

# Generate architecture documentation
python -m nonull docs generate
```

---

## / Git 工作流 / Git Workflow

- Branch naming: `feature/<skill-or-component>`, `fix/<issue>`, `docs/<topic>`
- Commit messages: `[Scope] Description (中文 / English)`
- Pre-commit: run `pytest tests/` and `python -m nonull audit`
- Pre-commit: `pytest tests/test_no_experimental_imports.py` must pass — no production code may import from `experimental/`
- No direct pushes to `main` or `develop`

---

> **Nonull | 智驾智能体 — Safety, Fusion, Intelligence**
