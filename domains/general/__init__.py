"""
通用领域 / General Domain
=========================

Always loaded. Provides neutral, non-domain-specific skills and defaults.
"""
from typing import List

from domains import DomainPackage, DomainMetadata


class GeneralDomain:
    """Always-active domain. Cannot be deactivated.

    Holds no domain-specific knowledge; exists so that the DomainRegistry
    always has at least one active package (and so that ``load_default_domains``
    can guarantee a non-empty activation set even on a fresh install).
    """

    @property
    def metadata(self) -> DomainMetadata:
        return DomainMetadata(
            name="general",
            display_name="通用 / General",
            description=(
                "Neutral defaults. Always available regardless of which "
                "specialized domain is active."
            ),
            safety_profile="advisory",
        )

    def register(self, registry) -> None:
        # Will be expanded in P16 to register general-purpose skills.
        return None

    def get_safety_disclaimers(self) -> List[str]:
        return [
            "通用领域：所有技能均为建议性，输出需由用户审核后使用。",
            "General domain: all skills are advisory; outputs require user review.",
        ]


__all__ = ["GeneralDomain"]
