# Contributing to Nonull

Thank you for your interest in contributing!

## Development setup

1. Fork and clone the repository
2. Install Python 3.10+
3. Create a virtualenv: `python -m venv venv && source venv/bin/activate`
4. Install in editable mode: `pip install -e ".[dev]"`
5. Set up your LLM API key: `cp .env.example .env` and fill in

## Code style

- Python 3.10+, type hints required on public APIs
- Bilingual docstrings (Chinese + English) per CLAUDE.md §"编码约定"
- Run `ruff check .` before committing
- Follow PEP 8 with 100-character line limit

## Testing

- All new code must have tests in `tests/`
- Tests must pass: `pytest tests/ -v`
- If adding a new skill, add an entry to `SAMPLE_INPUTS` in `tests/test_all_skills_smoke.py`
- If changing the public API, update both the docstring and the relevant test

## Marketing copy red lines

Per CLAUDE.md §"营销文案红线", do NOT use these phrases in code, docs, or commit messages:
- "ASIL-D Ready"
- "ISO 26262 Compliant"
- "production-ready" (in positive sense)
- "certified safety"
- "车规级"
- "freedom from interference" (in positive sense)
- "MC/DC coverage"
- "formal verification"
- "SEooC"

Safe alternatives:
- "Advisory Safety"
- "Advisory pattern check"
- "alpha / internal pilot"
- "DEMO placeholder"
- "internal ADAS engineering assistant"

## Submitting a PR

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes with tests
3. Run all tests: `pytest tests/ -v`
4. Run lint: `ruff check .`
5. Commit with `[Scope] Description (中文 / English)` format
6. Push and open a PR against `main`

## Code of conduct

Be respectful, be honest about what's working and what isn't, and prioritize
the project's safety disclaimers over marketing claims.

## Where to ask

- For questions about contributing, open an issue
- For safety/cert escalations, see INTERNAL-NOTES.md
