"""
Nonull 智驾智能体 — Top-level package
======================================
Entry point: from nonull import Nonull, NonullConfig
CLI: python -m nonull
"""
__version__ = "0.1.0"

# Lazy re-exports to avoid heavy import cost
def __getattr__(name):
    if name == "Nonull":
        from core import Nonull
        return Nonull
    if name == "NonullConfig":
        from core import NonullConfig
        return NonullConfig
    raise AttributeError(f"module 'nonull' has no attribute {name!r}")
