"""
DomainRegistry — manages which domain packages are loaded.
"""
from typing import Dict, List, TYPE_CHECKING
from . import DomainPackage, DomainMetadata

if TYPE_CHECKING:
    # Only for type checking; the actual import is deferred to avoid cycles.
    pass


class DomainRegistry:
    """Manages active domain packages and dispatches safety disclaimers.

    Acts as a thin coordinator between domain packages and the rest of
    the Nonull core. It does NOT itself contain domain knowledge — it
    dispatches calls to whatever domains the user has loaded.
    """

    def __init__(self):
        self._domains: Dict[str, DomainPackage] = {}
        self._active: List[str] = []
        self._default_domains = ["general"]  # always loaded

    # ---- Registration ----

    def register(self, domain: DomainPackage) -> None:
        """Register a domain package.

        The package is added to the catalog but not yet activated.
        """
        if not hasattr(domain, "metadata") or not hasattr(domain, "register"):
            raise TypeError(
                f"{type(domain).__name__} does not implement DomainPackage protocol"
            )
        self._domains[domain.metadata.name] = domain

    def register_skill(self, skill_class_or_instance) -> None:
        """Default ``register_skill`` no-op shim.

        A domain's ``register()`` may receive a registry that doesn't
        implement a full skill-registration protocol. The default ADAS
        domain calls this when no real skill registry is plugged in.
        Domains can override by passing a richer registry to ``activate``.
        """
        # The real registration is performed by the SkillRegistry wired
        # into the domain. This method exists so that DomainPackage
        # ``register()`` implementations can call ``registry.register_skill``
        # without crashing when the registry passed in is a plain
        # DomainRegistry instance.
        return None

    # ---- Activation ----

    def activate(self, name: str) -> None:
        """Activate a domain.

        Idempotent: activating an already-active domain is a no-op.
        """
        if name not in self._domains:
            raise KeyError(
                f"Domain {name!r} not registered. Available: {list(self._domains)}"
            )
        if name in self._active:
            return
        self._domains[name].register(self)
        self._active.append(name)

    def deactivate(self, name: str) -> None:
        """Deactivate a domain.

        'general' is always active and cannot be deactivated.
        """
        if name == "general":
            raise ValueError("Cannot deactivate 'general' domain")
        if name in self._active:
            self._active.remove(name)

    # ---- Queries ----

    def get_active(self) -> List[DomainPackage]:
        return [self._domains[n] for n in self._active]

    def get_active_metadata(self) -> List[DomainMetadata]:
        return [self._domains[n].metadata for n in self._active]

    def is_active(self, name: str) -> bool:
        return name in self._active

    def is_registered(self, name: str) -> bool:
        return name in self._domains

    def get_all_disclaimers(self) -> List[str]:
        out: List[str] = []
        for name in self._active:
            out.extend(self._domains[name].get_safety_disclaimers())
        return out

    def list_available(self) -> List[str]:
        return list(self._domains.keys())

    def __repr__(self) -> str:
        return (
            f"<DomainRegistry available={list(self._domains)} "
            f"active={self._active}>"
        )


def load_default_domains() -> DomainRegistry:
    """Load the built-in domains: 'general' + 'adas'.

    New users get ADAS by default. Power users can deactivate it.
    """
    from domains.general import GeneralDomain
    from domains.adas import ADASDomain

    reg = DomainRegistry()
    reg.register(GeneralDomain())
    reg.register(ADASDomain())
    reg.activate("general")
    reg.activate("adas")
    return reg
