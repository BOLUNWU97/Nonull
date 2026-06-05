"""Pytest configuration for the Nonull test suite.

The `tests/_archive/` directory holds the OLD `test_core.py` and
`test_memory.py` files that defined a parallel mock implementation. They
are kept for reference but MUST NOT be auto-collected by pytest (they
would either fail on missing imports or pass for the wrong reasons).
We exclude that directory from collection here.
"""

from __future__ import annotations

# Paths (relative to this file) that pytest should not try to collect.
# The leading "_" already hints at "private" — pytest respects this via
# the `collect_ignore_glob` hook, but we make it explicit and discoverable.
collect_ignore_glob = [
    "_archive/*",
    "_archive/**/*",
]
