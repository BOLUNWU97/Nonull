# tests/_archive/ — Archived test files (DO NOT COLLECT)

This directory holds the **old** `test_core.py` and `test_memory.py` files
that were archived on the 9th-pass cleanup (2026-06-05).

本目录保存的是被归档的旧测试文件。

## Why they were archived / 归档原因

The previous `tests/test_core.py` (834 lines, 27 KB) and
`tests/test_memory.py` (907 lines, 32 KB) **did not test the real
`core/` and `memory/` packages at all**. Instead, they defined a parallel
mock implementation (their own `NonullCore`, `SafetySystem`, `SkillRegistry`,
`NeocortexStore`, `SubconsciousProcessor`, `MemorySystem`, etc.) inside the
test file, and then tested *those*.

This gave a false sense of coverage: pytest reported "all green" because
the in-file mocks were trivially correct, while the real production code
in `core/agent_core.py`, `core/config.py`, and the `memory/` package was
never exercised.

之前的 `test_core.py` 和 `test_memory.py` 并没有真正测试 `core/` 和
`memory/` 包，而是在文件内部定义了一套并行的 Mock 实现并测试那些 Mock。
这会让测试显示通过但实际生产代码完全未被覆盖。

## What replaced them / 替代品

| Old (mocked)                  | New (real)                       |
| ----------------------------- | -------------------------------- |
| `tests/test_core.py`          | `tests/test_core_real.py`        |
| `tests/test_memory.py`        | `tests/test_memory_real.py`      |

The new files import directly from `core.agent_core`, `core.config`, and
the `memory/` package. They are picked up by `pytest tests/ -v` and by
CI (see `.github/workflows/test.yml` and `tests/test_quickstart_runs.py`).

新文件 `test_core_real.py` 和 `test_memory_real.py` 直接从真实的
`core/` 和 `memory/` 包导入并测试，会被 pytest 和 CI 自动运行。

## Why we keep the old files at all / 为什么不直接删除

1. **Historical context** — They document the *intended* surface area of
   the agent and memory modules at the time they were written. The new
   tests cover a subset of that surface, and the archived files act as a
   checklist of behaviours that may still need to be tested.

2. **Reference for future contributors** — Anyone adding a new test
   should look at the old file to see what the original author thought
   the module was supposed to do, then write a corresponding real test.

3. **No behavioural coupling** — The archived files are excluded from
   pytest collection (see `tests/conftest.py` → `collect_ignore_glob`).
   They cannot accidentally pass or fail CI.

保留这些文件作为历史参考和未来贡献者的检查清单。它们不会影响 CI
（已被 `tests/conftest.py` 排除）。

## What NOT to do / 注意事项

- **Do not `git mv` these files back into `tests/`.** They are the wrong
  tests and would re-introduce the false-coverage problem.
- **Do not import from these files in real tests.** If you need a mock,
  define it locally in the test file or use `unittest.mock.MagicMock`.
- **Do not delete these files** without a corresponding replacement that
  covers at least the same set of public APIs.

— Nonull team, 2026-06-05
