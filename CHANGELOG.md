# Changelog

All notable changes to Nonull will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] - 0.1.0

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
