# Changelog

All notable changes to Nonull will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-06-16

### Multi-Model Hybrid Scheduling + Deep Optimization

The headline of this release is a new `multimodel/` package — multi-vendor model
scheduling with automatic routing and multi-model collaboration — plus two new
execution modes (`run_react`, `run_hybrid`) and an audit-driven pass that fixed real
resource leaks and correctness bugs. **839 tests passing.**

#### Added — Execution modes
- `core/agent_loop.py` — `AgentLoop`, a standard ReAct while-loop (LLM owns control
  flow). async/sync tool execution, per-tool circuit-breaker (≥3 consecutive failures
  → hint the LLM to switch), `asyncio.wait_for` timeout with per-step event-loop yield,
  context trimming, signature-inferred tool schemas, shared cost tracking.
- `Nonull.run_react(task, tools, max_steps)` — ReAct execution mode; same instance,
  shared LLM/cost/memory, run()-compatible return format.
- `Nonull.run_hybrid(task, *, strategy, privacy, force_single)` — multi-model
  scheduling mode via `HybridScheduler`.

#### Added — `multimodel/` package (multi-model hybrid scheduling)
- `registry.py` — `ModelRegistry` + `ModelEntry` + `KeyRotator` (multi-API-key
  round-robin with 429/401 cooldown-skip). Cloud (OpenAI/Claude/DeepSeek/Qwen) +
  local (Ollama/LM Studio). `${ENV_VAR}` expansion in config.
- `router.py` — `TaskRouter`: heuristic complexity classification (code/length/
  keywords) + privacy detection (forces local) + quality/cost/speed strategies.
- `dispatcher.py` — `ModelDispatcher`: multi-key rotation + retry + model fallback +
  load balancing + call logging. Thread-safe client cache with `close()`.
- `collaborator.py` — `MultiModelCollaborator`: super-complex tasks decompose →
  parallel execute → cross-model verification → synthesize.
- `scheduler.py` — `HybridScheduler` unified facade.
- `litellm_config.yaml` + `nonull_models.yaml` + `INTEGRATION_GUIDE.md` (7-section
  integration doc). No hard LiteLLM dependency — the pure-httpx OpenAI-compatible
  client covers all providers; point base_url at a LiteLLM gateway if desired.
- `tests/test_multimodel.py` — 29 tests. `examples/multimodel_demo.py` — real-LLM
  routing + collaboration demo.

#### Added — Lifecycle & memory
- `Nonull.close()` + `__enter__/__exit__/__aenter__/__aexit__`, `MemorySystem.close()`
  — stop the SubconsciousLoop daemon thread + httpx client (fixes a per-instance
  thread+socket leak).
- `MemorySystem.prune()` wired into `run()` end — prevents unbounded memory growth.
- Memory recall chain (cross-session continuity): `_extract_memory_finding` +
  `_best_memory_findings` + recency fallback in `get_context`. Verified end-to-end
  (Agent A stores → Agent B recalls verbatim in a fresh session).

#### Fixed
- **P0 resource leak**: SubconsciousLoop thread + httpx client never closed.
- **P1 correctness**: `run()` returned `output=None` when finishing via the "complete"
  action — now backfills from reflection summary / last result.
- **P1**: empty-task guard on `run()`/`run_react()` (was wasting iterations).
- **P0 (multimodel)**: `${ENV_VAR}` in model config wasn't expanded → literal string
  passed as API key → every cloud call would 401. Now expanded in `from_config`.
- **P1 (multimodel)**: dispatcher client-cache data race under parallel dispatch
  (added lock) + cached clients never closed (added `close()` chain into Nonull.close).
- **Safety over-sensitivity**: `text:` agent output was content-risk-scored, so a code
  review *discussing* "write/delete" got falsely blocked. `text:` now passes the
  blocklist but skips content scoring.
- `<think>` reasoning blocks from MiniMax/DeepSeek-R1 stripped from JSON + final output.
- `run_react` timeout was a no-op (sync chat blocked the event loop) — fixed with a
  per-step `await asyncio.sleep(0)` yield.

#### Tests
- 690 → **839 passing** (9 skipped). New: multimodel (29), agent_loop (28),
  deep_optimization (13), memory_recall_unit (16), core_safety (15).

---

## [Unreleased] - 0.2.2

### Deep Optimization & Cleanup (2026-06-13)

**Critical fix:** the Neocortex memory subsystem never actually ran. `EpisodeType`
was never exported from `memory/__init__.py`, so `core.memory_system` silently fell
back to a stub backend on every launch. Fixed — the full memory system (Ebbinghaus
decay, vector retrieval, SubconsciousLoop) is now active for the first time since it
was written.

#### Added
- `core/cost_tracker.py` — LLM cost & token tracking (per-model aggregation, budget
  limits, fuzzy model matching, atomic persistence). 20 tests.
- `core/persistence.py` — atomic JSON write infrastructure (temp-file + os.replace).
- `tests/test_agent_e2e_offline.py` — offline end-to-end agent loop (MockLLM, no API
  key); first test that drives the full plan→reason→act→reflect cycle.
- `to_dict/from_dict/save/load` on SessionMemory, KnowledgeGraph, PromptRegistry.
- LLM client hardening: classified errors (auth / rate-limit / server / request),
  429 Retry-After, model fallback chain, streaming+tools (`chat_stream_full`).

#### Changed / Refactored
- Split `core/agent_core.py` 2858→1451 lines into 7 modules (`states`, `errors`,
  `safety`, `registries`, `subagents`, `hooks`, `memory_legacy`), all re-exported
  for backward compatibility.
- `MemorySystem` re-export now points at the full implementation (was legacy) —
  eliminates the silent three-way name confusion between re-export, Nonull instance,
  and test docstring.
- `_safe_execute_step` returns a sentinel instead of re-raising — the
  RECOVERING→REASONING recovery path now actually runs instead of being bypassed.
- Removed 13 dead imports + dead `TypeVar("T")` from agent_core (split residue).

#### Fixed
- `memory/__init__.py` missing `EpisodeType` export (memory system activation).
- ISO 26262 positive-voice claims in docs (architecture.md, user-guide.md, README.md).
- Non-existent API references in docs (`claude-sonnet-4`, `SafetyLevel.ASIL_D`,
  `CoPilot.get_daily_brief`).
- `llm_client` reading `.env` without UTF-8 encoding (broke on Windows GBK default).
- `eval_judge` CUSTOM metric name auto-selection.
- Removed self-attribution ("MiniMax M3 verified") from README; aligned Python badge
  to the actual 3.10+ requirement.

#### Tests
- ~690 passing (up from 351/431 in P23). The agent main loop now has end-to-end
  regression coverage that would have caught the dormant-memory bug immediately.

### Real-World Test Verification (P23)

**Date:** 2026-06-06
**Python:** 3.13.0 (first real Python run after 14 rounds of polish)

#### Test results (multi-role, multi-dimensional)

| Metric | Value |
|---|---|
| Test files | 22 |
| Test classes | 34 |
| Test functions | 431 |
| **Passed** | **351 (81.4%)** |
| Failed | 46 |
| Errors | 33 |
| Skipped | 1 |

**By role:**
- Imports: 0 collection errors
- Unit tests: 165 pass / 12 fail
- Integration: 25 pass / 4 fail / 25 errors
- Orchestrator: 63 pass / 3 fail / 8 errors
- Smoke tests: 97 pass / 28 fail / 1 skip
- Full suite: 351 pass / 46 fail / 33 errors

### Fixed (P23)

| Bug | File:line | Fix |
|---|---|---|
| `Tuple` not defined | `core/config.py:714` | Added `Tuple` to typing import |
| `_REGISTRY` dataclass issue | `domains/adas/personas.py:49` | Changed to `ClassVar[Dict]` |
| Malformed docstring | `channels/cli.py:369` | Replaced raw triple-quote docstring content |
| ClassVar on `_REGISTRY` | `domains/adas/personas.py` | Added `ClassVar` import |
| Real persona classes | `domains/adas/personas.py` | Added real `ConservativePersona`/`SportyPersona`/`VeteranPersona` |

### Known limitations (alpha)

**82% green is real**. The remaining 18% cluster in:
1. **Test code issues** (mock path wrong, expected values off, missing methods) — ~30%
2. **Marketing copy violations in docs** (~5% — README/CLAUDE still contain "ISO 26262 Compliant" or "production-ready" in positive context)
3. **Real code issues** (memory layer return shape, hooks calling signature, etc.) — ~30%
4. **API mismatches** between test and code — ~30%

**Honest verdict:** Nonull v0.2.x is a real working framework that the team can use, but it is **not** a polished, fully-tested, public-release product. It requires:
- 6-10 hours of focused fix-up work to reach 95%+
- A round of real ADAS engineer use to surface remaining edge cases
- Honest documentation about its current state (not "production-ready")

### Changed
- `domains/adas/personas.py` uses `ClassVar[Dict]` properly for the registry
- `channels/cli.py` docstring is well-formed

### Notes
- The 81.4% test pass rate on Python 3.13 is the first time anyone has **actually executed** the test suite. Previous 14 rounds of polish were static review only.
- This is **expected and good**: the project had a pretense of "zero bugs" based on static review, but the real test run surfaced real issues that static review missed.
- The user (Nonull owner) installed Python 3.13 on their workstation, ran the test suite, and got these results. This is the **most important** verification step in the project's history.

## [Unreleased] - 0.2.0

### Added - Domain Abstraction (P15)
- New `domains/` package: `domains/__init__.py`, `domains/registry.py`, `domains/general/`, `domains/adas/`
- `DomainPackage` protocol + `DomainRegistry` for pluggable domain-specific skills/personas/scenarios
- ADAS is now a built-in default domain; users can register custom domains
- `load_default_domains()` factory

### Added - LLM Client (P15)
- New `core/llm_client.py`: OpenAI-compatible sync + async client
- Supports any provider (OpenAI, Anthropic, DeepSeek, MiniMax, Ollama, vLLM, custom)
- `Nonull.run_sync()` now actually calls the LLM over HTTP
- Configurable via env vars: `NONULL_LLM_API_KEY`, `NONULL_LLM_PROVIDER`, `NONULL_LLM_MODEL`, `NONULL_LLM_API_BASE`
- `docs/llm-setup.md` with provider-specific setup

### Added - General-Purpose Skills (P16)
- 21 new domain-agnostic skills across:
  - `skills/core/web_skills.py` (web_fetch, web_search stub, link_extractor)
  - `skills/core/data_skills.py` (json_formatter, csv_parser, text_statistics, diff)
  - `skills/core/code_skills.py` (regex_tester, json_schema_generator, code_counter)
  - `skills/core/documentation_skills.py` (markdown_to_html, readme_skeleton, docstring_generator)
  - `skills/core/translation_skills.py` (language_detector, translation_prompt)
  - `skills/core/utilities_skills.py` (uuid_generator, hash, timestamp, base64)

### Added - Skill Execution Backends (P16)
- `skills/execution/` package with 4 backends:
  - `inline` (default, in-process)
  - `subprocess` (separate process, timeout)
  - `docker` (full container isolation)
  - `http` (remote skill service)
- `CodeRunnerSkill` exposes user code execution

### Added - Multimodal Skills (P18)
- `skills/multimodal/image_skills.py` (image_info, image_resize, image_base64)
- `skills/multimodal/pdf_skills.py` (pdf_info, pdf_extract_text)
- `skills/multimodal/audio_skills.py` (audio_info, audio_transcribe stub)

### Added - Creative Skills (P20)
- `skills/creative/idea_skills.py` (brainstorm, metaphor_generator, story_plot)
- `skills/creative/productivity_skills.py` (pomodoro_schedule, eisenhower_matrix)
- `skills/creative/learning_skills.py` (flashcard_generator, quiz_generator, spaced_repetition)

### Added - Web UI (P19)
- `channels/web.py`: FastAPI-based web interface
- Endpoints: `/`, `/api/skills`, `/api/scenarios`, `/api/domains`, `/api/agent/chat`, `/api/agent/status`, `/ws/chat`
- Bilingual dark-theme UI (Chinese + English)
- WebSocket support for real-time chat
- Install via `pip install -e ".[web]"`

### Added - i18n Support (P20)
- `i18n/` module with English + Chinese translations
- Module-level `t(key, lang)` helper

### Added - Evaluation Framework (P21)
- `evaluation/` package: 15+ benchmark tasks across 6 categories
- Categories: code, data, utilities, multimodal, documentation, adversarial
- Includes adversarial tests for huge input, empty input, control chars, path traversal
- `run_benchmark("v1")` returns pass rate and per-task results

### Changed
- `persona/` skills (scenario_engine, driving_persona, co_pilot) moved to `domains/adas/` (ADAS-specific)
- `persona/safety_badge.py` → `core/safety_metrics.py` (now generic, domain-agnostic)
- `persona/persona_orchestrator.py` → `core/persona_orchestrator.py`
- ADAS skills (safety_skills, simulation_skills, perception_skills, planning_skills) moved to `domains/adas/skills/`
- `persona/__init__.py` maintains backward-compat lazy re-exports
- README now leads with "全领域 / Universal" rather than "智驾 / ADAS"
- `requirements.txt`: httpx upper bound `<0.29`, pydantic `<3.0`, etc.
- `setup.py`: optional extras for `web` (fastapi, uvicorn, jinja2)

### Deprecated
- Direct imports from `persona.scenario_engine`, `persona.driving_persona`, etc. Use `from domains.adas import ...` instead. Backward-compat aliases will be removed in v0.4.

### Fixed
- C++ code review still regex-based (real AEB defects not caught); deferred to P24+
- Real `SkillRegistry` integration test now in `tests/test_orchestrator_real_skills.py`

### Security
- `.env` (with API key) is gitignored
- `NONULL_LLM_API_KEY` only read from env, never logged
- 4 guard tests: experimental imports, marketing claims, quickstart imports, stale claims

---

## [0.1.0] - 2026-06-06

### Added
- Core agent framework with ReAct + Plan-and-Execute + Reflexion fusion
- Four-memory system (working, episodic, semantic, procedural) with Neocortex aggregator
- 31 domain skills across 9 categories (code, safety, perception, planning, testing, simulation, data, research, devops)
- Multi-agent orchestration with DAG decomposition and conflict resolution
- Hook system with 40 lifecycle events and 4 execution types
- 5 channel adapters (CLI, gateway, MCP, plus 5 platform integrations)
- 3 driving personas (Conservative, Sporty, Veteran) with tone-shifted output
- 36-scenario library with coverage analysis
- Safety metrics tracking system (advisory, not gamified)
- Co-pilot mode for proactive alerts
- Safety Guardian (5-layer, advisory, not ISO 26262 certified)
- 2-3-2-1 CI matrix: Ubuntu + Windows × Python 3.10/3.11/3.12
- Three guard tests: experimental imports, marketing claims, quickstart imports
- 11 test files, 110+ real tests
- INTERNAL-NOTES.md for new engineers
- ADVISORY disclaimers throughout README, CLAUDE.md, and all skill files

### Changed
- N/A (initial alpha release)

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- All safety-related code is explicitly marked ADVISORY
- No automated CI job makes ISO 26262 / ASIL-D claims
- Marketing copy red lines enforced via tests/test_no_marketing_claims.py
