"""Helper to run the eval benchmark and write to a log file."""
import sys
import os
import io

# Suppress logs
import logging
logging.disable(logging.CRITICAL)

log_path = r"C:\Users\EDY\Desktop\智能体\test_eval_log.txt"

# Capture stdout
out = io.StringIO()
err = io.StringIO()
sys.stdout = out
sys.stderr = err

try:
    # Add project root to path
    project_root = r"C:\Users\EDY\Desktop\智能体"
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from evaluation.benchmarks import get_benchmark
    from evaluation.runner import run_benchmark

    # 1. Verify the benchmark suite
    bench = get_benchmark("v1")
    print(f"Total benchmark tasks: {len(bench)}")
    cats = sorted({t.category for t in bench})
    print(f"Categories ({len(cats)}): {cats}")
    diffs = sorted({t.difficulty for t in bench})
    print(f"Difficulties ({len(diffs)}): {diffs}")

    # 2. Run the full benchmark (this triggers skill discovery)
    print("\n--- Running benchmark ---")
    result = run_benchmark("v1", verbose=False)
    print(f"Total: {result['total']}")
    print(f"Passed: {result['passed']}")
    print(f"Pass rate: {result['pass_rate']:.2%}")

    # 3. Per-task results
    print("\n--- Per-task results ---")
    for r in result["results"]:
        status = "PASS" if r.get("passed") else "FAIL"
        err_info = r.get("error", r.get("note", ""))
        print(f"  {status} {r['task_id']}: {err_info}")

    # 4. Run pytest-style tests manually
    print("\n--- test_benchmark_v1_has_tasks ---")
    assert len(bench) >= 10, f"expected >=10 tasks, got {len(bench)}"
    assert any(t.category == "adversarial" for t in bench)
    assert any(t.difficulty == "hard" for t in bench)
    print("  PASS")

    print("\n--- test_run_benchmark_runs ---")
    assert result["total"] >= 10
    assert result["passed"] >= 0
    assert 0 <= result["pass_rate"] <= 1
    print("  PASS")

    print("\n--- test_benchmark_categories_diverse ---")
    assert len(cats) >= 4
    print("  PASS")

    print("\nAll checks passed.")
except Exception as e:
    import traceback
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("STDOUT:\n")
        f.write(out.getvalue())
        f.write("\n\nSTDERR:\n")
        f.write(err.getvalue())
    print(f"Wrote log to {log_path}")
