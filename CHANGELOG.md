# Changelog

All notable changes to Nonull will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
