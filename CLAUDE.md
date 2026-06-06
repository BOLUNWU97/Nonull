# Nonull — Claude Code Project Instructions

You are working on **Nonull**, an extensible, **domain-agnostic** AI Agent framework. The framework core itself contains no domain knowledge. Domain-specific content (autonomous driving, medical, legal, finance, etc.) lives in pluggable **domain packages** under `domains/`.

The four-architecture fusion (**OpenClaw**, **Hermes Agent**, **openHuman**, **Claude Code**) is the core engineering foundation. ADAS / 智驾 is shipped as a **built-in domain package** (`domains/adas/`) and is not part of the core.

---

## / 核心原则 / Core Principles

1. **领域无关 / Domain-Agnostic** — The Nonull core (memory, channels, hooks, safety, orchestration) contains **no domain-specific knowledge**. All domain content (e.g. ADAS driving scenarios, ISO 26262 templates, driving personas) lives in `domains/<name>/` packages that implement the `DomainPackage` protocol. The ADAS domain is one such built-in package; new users can deactivate it or add their own.
2. **四架构融合优先** — All core design decisions must respect and leverage the fusion of OpenClaw, Hermes Agent, openHuman, and Claude Code patterns. Do not break the architectural consistency of the core.
3. **安全第一 / Safety First** — Apply deny-first safety logic. Never bypass safety checks. The safety layer in this project is **advisory only** (see disclaimer below) — it does **not** implement ISO 26262 ASIL-D requirements.
4. **双语文档 / Bilingual Documentation** — All user-facing documentation MUST be in both Chinese and English.
5. **技能驱动 / Skill-Driven** — Extend functionality through skills registered in the tool registry, not by modifying core agent code.
6. **测试覆盖 / Test Coverage** — Core tests and memory tests must pass before any commit.

---

## / 🚨 营销文案红线 / Marketing Copy Red Lines

**Never claim ISO 26262 / ASIL-D compliance in user-facing copy.** Nonull is an internal ADAS engineering assistant — **not** a certified safety product. The following claims are forbidden in README, docs, comments, commit messages, badges, or any user-facing output:

- ❌ Forbidden positive claim forms (we do **not** use any of these labels). This project is **not** an ASIL-D Ready product, **not** an ISO 26262 Compliant product, **not** a 功能安全认证 product, **not** a 车规级 product (advisory only).
- ❌ Forbidden positive claims (we do **not** make any of these). This project is **not** production-ready, **not** 量产, advisory only.
- ❌ Forbidden positive claims (we do **not** make any of these). This project is **not** a certified safety mechanism; **not** a certified safety element (advisory pattern references only).
- ❌ Forbidden positive claims (we do **not** make any of these). Any badge, image, or text implying formal ISO 26262 / ASIL-D / ASPICE certification — **not** certified, **not** endorsed.
- ❌ Forbidden positive claims (we do **not** make any of these): "MC/DC 覆盖", "形式化验证", "SEooC", "freedom from interference" — these describe certified safety processes that this project does **not** implement (advisory pattern references only, **not** certified safety processes).

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
├── CLAUDE.md               # This file — Claude Code instructions
├── AGENT.md                # Agent entrypoint notes
├── setup.py                # Package setup / install metadata
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore rules
├── nonull/                 # Top-level package (lowercase) — CLI entrypoint
│   ├── __init__.py
│   └── __main__.py
├── core/                   # Core engine (domain-agnostic)
│   ├── __init__.py
│   ├── agent_core.py
│   ├── config.py
│   ├── safety_metrics.py   # Generic safety metrics (P15: moved out of persona/)
│   └── persona_orchestrator.py # Generic persona-orchestrator (P15: moved out of persona/)
├── memory/                 # Memory system (openHuman-style)
│   ├── __init__.py
│   ├── working_memory.py
│   ├── episodic.py
│   ├── semantic.py
│   ├── procedural.py
│   ├── neocortex.py
│   └── subconscious_loop.py
├── safety/                 # Safety guardian (advisory only)
│   ├── __init__.py
│   ├── guardian.py
│   ├── deny_first.py
│   └── compliance.py
├── domains/                # Pluggable domain packages (P15)
│   ├── __init__.py         # DomainPackage protocol + DomainMetadata
│   ├── registry.py         # DomainRegistry + load_default_domains()
│   ├── general/            # Always-active fallback domain
│   │   └── __init__.py     #   GeneralDomain
│   └── adas/               # Built-in 智驾 / ADAS domain
│       ├── __init__.py     #   ADASDomain + re-exports
│       ├── personas.py     #   (moved from persona/driving_persona.py)
│       ├── scenarios.py    #   (moved from persona/scenario_engine.py)
│       ├── copilot.py      #   (moved from persona/co_pilot.py)
│       └── skills/
│           ├── __init__.py
│           ├── safety.py     # (moved from skills/safety_skills.py)
│           ├── simulation.py # (moved from skills/simulation_skills.py)
│           ├── perception.py # (moved from skills/perception_skills.py)
│           └── planning.py   # (moved from skills/planning_skills.py)
├── skills/                 # Generic (non-ADAS) skills + ADAS shim
│   ├── __init__.py         # Backward-compat shim (lazy-loads ADAS skills from domains/adas/skills/)
│   ├── base.py
│   ├── registry.py
│   ├── code_skills.py      # Code review / optimization / refactoring / bug detection
│   ├── data_skills.py      # Log / pipeline / annotation analysis
│   ├── devops_skills.py    # CI / CD / monitoring
│   ├── research_skills.py
│   ├── testing_skills.py
│   └── core/               # P16: 19 general-purpose, domain-agnostic skills
│       ├── __init__.py
│       ├── web_skills.py          # web_fetch / web_search / link_extractor
│       ├── data_skills.py         # json_formatter / csv_parser / text_statistics / diff
│       ├── code_skills.py         # regex_tester / json_schema_generator / code_counter
│       ├── documentation_skills.py # markdown_to_html / readme_skeleton / docstring_generator
│       ├── translation_skills.py  # language_detector / translation_prompt
│       └── utilities_skills.py    # uuid_generator / hash / timestamp / base64
├── orchestration/          # Multi-agent orchestration
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── agent_pool.py
│   ├── communication.py
│   └── workflows.py
├── persona/                # Backward-compat shim (P15)
│   └── __init__.py         # Lazy re-exports of the moved classes
├── channels/               # Communication channels (CLI / MCP / gateways)
│   ├── __init__.py
│   ├── base.py
│   ├── cli.py
│   ├── gateway.py
│   ├── mcp_adapter.py
│   └── platform_adapters.py
├── hooks/                  # Lifecycle hooks
│   ├── __init__.py
│   └── hook_system.py
├── config/                 # Configuration files
│   ├── config.yaml         # Main configuration (now with `domains:` section)
│   ├── safety_rules.yaml   # Safety policy rules
│   └── profiles/           # Profile isolation (Hermes-style)
│       └── default.yaml
├── experimental/           # DO NOT USE — research only
│   ├── README.md
│   ├── consciousness/      # Self-evolving memory (experimental)
│   └── evolution/          # Self-evolution (experimental)
├── docs/                   # Documentation (see Documentation section below)
├── examples/               # Usage examples
│   ├── quickstart.py
│   ├── code_review.py
│   ├── safety_analysis.py
│   └── multi_agent_workflow.py
├── tests/                  # Test suite (see Tests section below)
└── .github/
    ├── CODEOWNERS
    └── workflows/
        └── test.yml
```

---

## / 文档 / Documentation

All user-facing documentation lives in `docs/` and is bilingual where required:

- `docs/architecture.md` — System architecture, layer boundaries, memory model
- `docs/skills-catalog.md` — Catalog of all available skills
- `docs/user-guide.md` — End-user guide (English)
- `docs/innovation-report.md` — Innovation highlights and design rationale
- `docs/说明书-完整版.md` — 完整中文说明书
- `docs/快速上手指南.md` — 中文快速上手指南
- `docs/一页纸速览.md` — 一页纸速览 (one-page cheat sheet)
- `experimental/README.md` — Experimental module warnings
- `README.md` — Top-level project overview (Chinese + English)
- `AGENT.md` — Agent entrypoint / operating notes

---

## / 测试 / Tests

Test suite lives in `tests/` (12 files, all run by CI via `.github/workflows/test.yml`):

- `tests/test_core_real.py` — Real core engine / agent_core / config tests (replaces mock-based `test_core.py`)
- `tests/test_memory_real.py` — Real memory layer tests (replaces mock-based `test_memory.py`)
- `tests/test_no_experimental_imports.py` — **Guard test** — enforces no production code imports from `experimental/`
- `tests/test_safety_badge_api.py` — Persona safety_badge public API contract
- `tests/test_persona_exports.py` — Persona module exports / surface checks
- `tests/test_domain_registry.py` — Domain registry: register / activate / deactivate / disclaimers
- `tests/test_no_marketing_claims.py` — Guard test — enforces no forbidden ISO 26262 / ASIL-D / "production-ready" marketing claims in user-facing copy (not production-ready, advisory only)
- `tests/test_quickstart_runs.py` — Smoke test that `examples/quickstart.py` imports resolve
- `tests/test_cli_agent_wiring.py` — CLI agent wiring (bind_agent, /agent, result unwrapping)
- `tests/test_orchestrator_skills_glue.py` — Orchestrator + skill registry glue (8 tests)
- `tests/test_orchestrator_async.py` — Async dispatch via asyncio.gather
- `tests/test_orchestrator_real_skills.py` — Integration with real SkillRegistry and real CodeReviewSkill
- `tests/test_skill_workflow_integration.py` — End-to-end `examples/skill_workflow.py` import test
- `tests/test_all_skills_smoke.py` — 50-skill smoke test with parametrized SAMPLE_INPUTS
- `tests/test_general_skills.py` — Per-skill tests for the 19 general-purpose skills in `skills/core/`
- `tests/test_safety_skills_advisory.py` — HARA "ADVISORY TEMPLATE ONLY" contract
- `tests/test_no_stale_claims.py` — Stale-number and demo-data guard
- `tests/_archive/` — Archived mock-based tests, excluded from collection by `conftest.py`

Run all tests:

```bash
pytest tests/ -v
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

## / 技能组织 / Skill Organization

Total skills shipped in P16: **50**

- **31 ADAS-specific skills** in `domains/adas/skills/` (perception / planning / safety / simulation / code / data / research / devops / testing — the original 9-category ADAS set).
- **19 general-purpose (domain-agnostic) skills** in `skills/core/`:
  - **Web (3)**: `web_fetch`, `web_search`, `link_extractor`
  - **Data (4)**: `json_formatter`, `csv_parser`, `text_statistics`, `diff`
  - **Code (3)**: `regex_tester`, `json_schema_generator`, `code_counter`
  - **Documentation (3)**: `markdown_to_html`, `readme_skeleton`, `docstring_generator`
  - **Translation (2)**: `language_detector`, `translation_prompt`
  - **Utilities (4)**: `uuid_generator`, `hash`, `timestamp`, `base64`

The ADAS skills were moved to `domains/adas/skills/` in **P15**; the `skills/__init__.py` is now a backward-compat shim that lazy-loads the ADAS classes via PEP 562 `__getattr__`. General-purpose skills remain under `skills/core/` and are eagerly importable.

All 50 skills are auto-discovered by `SkillRegistry.auto_discover()` and pass `tests/test_all_skills_smoke.py`.

## / 领域包开发指南 / Domain Package Development Guide

P15 introduces the **domain abstraction layer**: the core (memory, channels,
hooks, safety, orchestration) is **domain-agnostic**. Domain knowledge
lives in `domains/<name>/` packages that implement the `DomainPackage`
protocol defined in `domains/__init__.py`.

Built-in domains:

- `domains/adas/` — 智驾 / ADAS (default, can be deactivated)
- `domains/general/` — Always-active fallback (cannot be deactivated)

### How to add your own domain / 如何加自己的领域

A working 10-line example that adds a hypothetical `medical` domain:

```python
# domains/medical/__init__.py
from domains import DomainPackage, DomainMetadata

class MedicalDomain:
    @property
    def metadata(self) -> DomainMetadata:
        return DomainMetadata(
            name="medical",
            display_name="医疗 / Medical",
            description="Medical knowledge support (advisory).",
            safety_profile="regulated-medical",  # 'advisory' | 'regulated-medical' | 'safety-critical'
            requires_disclaimers=[
                "医疗领域：所有输出仅供研发参考，不构成临床建议。",
                "Medical domain: outputs are advisory only, not clinical advice.",
            ],
        )

    def register(self, registry) -> None:
        # Defer imports to keep the domain package's import cost low
        from domains.medical.skills import DrugInteractionSkill
        registry.register_skill(DrugInteractionSkill())

    def get_safety_disclaimers(self):
        return self.metadata.requires_disclaimers
```

```python
# main.py
from domains import load_default_domains, DomainRegistry
from domains.medical import MedicalDomain

reg = load_default_domains()         # 'general' + 'adas'
reg.register(MedicalDomain())          # add yours
reg.activate("medical")                # turn it on
reg.deactivate("adas")                 # (optional) drop ADAS if not needed

# Per-domain safety disclaimers:
for line in reg.get_all_disclaimers():
    print(line)
```

Rules of thumb:

- Domain packages must NOT import from `core/`, `memory/`, `safety/`, or
  other domain packages. The dependency arrow only goes **core ← domain**.
- The `general` domain is always active and cannot be deactivated.
- A domain's `safety_profile` must be one of `advisory`, `regulated-medical`,
  or `safety-critical`. The core safety layer is always advisory-only;
  the profile is a label, not a permission grant.
- New domain packages should pass `tests/test_domain_registry.py`'s
  contract: register / activate / deactivate / disclaimers behave as
  documented.

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
