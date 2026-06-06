"""
Nonull 领域包 / Domain Packages
================================

Nonull 框架本身**领域无关**。所有领域知识（包括智驾/医疗/法律/金融等）
都以可插拔"领域包"的形式存在于 `domains/` 子目录中。

Nonull framework is **domain-agnostic**. All domain knowledge (ADAS/medical/legal/finance)
lives in pluggable "domain packages" under `domains/` subdirectories.

每个领域包必须实现 `DomainPackage` 协议：
Each domain package must implement the `DomainPackage` protocol.

内置领域：
- `domains/adas/` — 智驾/ADAS 领域 (built-in default)
- `domains/general/` — 通用 fallback domain (always loaded)

Usage:
    from domains import DomainRegistry, load_default_domains
    from domains.adas import ADASDomain

    registry = DomainRegistry()
    registry.register(ADASDomain())
    registry.activate("adas")

    # Now ADAS-specific skills/personas/scenarios become available
"""
from typing import Protocol, List, runtime_checkable
from dataclasses import dataclass, field


@dataclass
class DomainMetadata:
    """领域元数据 / Domain metadata."""
    name: str           # 'adas', 'medical', 'general'
    display_name: str   # '智驾 / ADAS'
    description: str
    version: str = "0.1.0"
    author: str = "Nonull Team"
    safety_profile: str = "advisory"  # 'advisory' | 'regulated-medical' | 'safety-critical'
    requires_disclaimers: List[str] = field(default_factory=list)


@runtime_checkable
class DomainPackage(Protocol):
    """所有领域包必须实现此协议。

    A domain package registers its skills, personas, scenarios, and any
    domain-specific safety context with the Nonull core.
    """

    @property
    def metadata(self) -> DomainMetadata: ...

    def register(self, registry: 'DomainRegistry') -> None:
        """注册本领域的所有组件到主注册表。
        Register all domain components with the main registry.
        """
        ...

    def get_safety_disclaimers(self) -> List[str]:
        """返回领域特定的安全免责声明（会附加到核心disclaimer后面）。"""
        ...


# Lazy re-export of the registry to avoid an import cycle (domains/__init__.py
# is imported by domains/registry.py via the DomainPackage annotation above).
def __getattr__(name: str):
    if name in {"DomainRegistry", "load_default_domains"}:
        from . import registry as _registry
        return getattr(_registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DomainMetadata",
    "DomainPackage",
    "DomainRegistry",
    "load_default_domains",
]
