.PHONY: help install install-dev install-all test test-fast test-cov \
        run web eval lint format clean build publish

help:
	@echo "Nonull — Universal AI Agent Framework"
	@echo ""
	@echo "Usage:"
	@echo "  make install       Install runtime deps"
	@echo "  make install-dev   Install dev + test deps"
	@echo "  make install-all   Install all extras (web, llm, mcp, etc.)"
	@echo "  make test          Run full test suite"
	@echo "  make test-fast     Run only smoke tests"
	@echo "  make test-cov      Run tests with coverage"
	@echo "  make run           Launch interactive CLI"
	@echo "  make web           Launch web UI on :8765"
	@echo "  make eval          Run benchmark suite"
	@echo "  make lint          Run ruff"
	@echo "  make format        Auto-format with ruff"
	@echo "  make clean         Remove build artifacts"
	@echo "  make build         Build sdist + wheel"
	@echo ""

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[all,dev,web]"

test:
	pytest tests/ -v

test-fast:
	pytest tests/test_all_skills_smoke.py tests/test_quickstart_runs.py tests/test_no_experimental_imports.py -v

test-cov:
	pytest tests/ -v --cov=core --cov=skills --cov=orchestration --cov=persona --cov=safety --cov=memory --cov=hooks --cov=channels --cov=domains --cov=i18n --cov=evaluation --cov-report=term-missing

run:
	python -m nonull

web:
	python -m nonull --channel web

eval:
	pytest tests/test_evaluation.py -v -s

lint:
	ruff check core/ memory/ safety/ skills/ orchestration/ persona/ channels/ hooks/ domains/ i18n/ evaluation/ nonull/

format:
	ruff format core/ memory/ safety/ skills/ orchestration/ persona/ channels/ hooks/ domains/ i18n/ evaluation/ nonull/

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache

build: clean
	python -m build

publish: build
	twine upload dist/*
