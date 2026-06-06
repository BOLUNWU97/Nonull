"""Tests for the evaluation framework."""
from evaluation.benchmarks import get_benchmark
from evaluation.runner import run_benchmark


def test_benchmark_v1_has_tasks():
    bench = get_benchmark("v1")
    assert len(bench) >= 10
    assert any(t.category == "adversarial" for t in bench)
    assert any(t.difficulty == "hard" for t in bench)


def test_run_benchmark_runs():
    result = run_benchmark("v1", verbose=False)
    assert result["total"] >= 10
    assert result["passed"] >= 0
    assert 0 <= result["pass_rate"] <= 1


def test_benchmark_categories_diverse():
    bench = get_benchmark("v1")
    categories = {t.category for t in bench}
    assert len(categories) >= 4  # code, data, utilities, adversarial, etc.
