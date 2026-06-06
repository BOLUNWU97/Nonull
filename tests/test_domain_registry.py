"""Tests for the domain abstraction layer introduced in P15.

These tests pin the contract of ``domains.DomainRegistry`` and the
``DomainPackage`` protocol so that future changes (e.g. P16 actually
wiring domain packages into the SkillRegistry) can't silently break the
abstraction. They exercise:

* the registry's register / activate / deactivate lifecycle
* the prohibition on deactivating the ``general`` fallback
* the disclaimer aggregation across active domains
* loading the built-in defaults via ``load_default_domains``
* basic structural checks on the ``DomainPackage`` protocol
* compatibility with a fake, third-party domain package
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List

import pytest

# Make project root importable regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domains import (
    DomainMetadata,
    DomainPackage,
    DomainRegistry,
    load_default_domains,
)
from domains.general import GeneralDomain
from domains.adas import ADASDomain


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


class FakeDomain:
    """A trivial third-party-style domain package for testing.

    Mirrors what a real medical/legal/finance package would do: a class
    with a ``metadata`` property, a ``register(registry)`` method, and a
    ``get_safety_disclaimers()`` method.
    """

    def __init__(self, name: str = "fake", disclaimers: List[str] | None = None):
        self._disclaimers = disclaimers or [f"Fake domain {name} disclaimer."]
        self.register_calls: List[DomainRegistry] = []
        self._meta = DomainMetadata(
            name=name,
            display_name=f"Fake {name}",
            description="A fake domain for testing.",
            safety_profile="advisory",
            requires_disclaimers=list(self._disclaimers),
        )

    @property
    def metadata(self) -> DomainMetadata:
        return self._meta

    def register(self, registry: DomainRegistry) -> None:
        self.register_calls.append(registry)

    def get_safety_disclaimers(self) -> List[str]:
        return list(self._disclaimers)


class NotADomain:
    """A class that intentionally does NOT implement DomainPackage."""
    pass


# ---------------------------------------------------------------------------
# Protocol / metadata tests
# ---------------------------------------------------------------------------


class TestDomainPackageProtocol:
    """The protocol surface itself should be importable and well-typed."""

    def test_domain_metadata_is_dataclass(self):
        meta = DomainMetadata(
            name="x",
            display_name="X",
            description="d",
        )
        assert meta.name == "x"
        assert meta.version == "0.1.0"  # default
        assert meta.safety_profile == "advisory"  # default

    def test_domain_package_is_runtime_checkable(self):
        # DomainPackage is a Protocol decorated with @runtime_checkable, so
        # isinstance() should return True for conforming classes.
        assert isinstance(GeneralDomain(), DomainPackage)
        assert isinstance(ADASDomain(), DomainPackage)
        assert isinstance(FakeDomain(), DomainPackage)

    def test_non_domain_rejected_by_isinstance(self):
        assert not isinstance(NotADomain(), DomainPackage)


# ---------------------------------------------------------------------------
# DomainRegistry: registration
# ---------------------------------------------------------------------------


class TestDomainRegistration:
    def test_register_adds_to_available(self):
        reg = DomainRegistry()
        reg.register(FakeDomain(name="alpha"))
        assert "alpha" in reg.list_available()
        assert not reg.is_active("alpha")
        assert not reg.is_registered("nonexistent")

    def test_register_rejects_non_package(self):
        reg = DomainRegistry()
        with pytest.raises(TypeError):
            reg.register(NotADomain())

    def test_double_register_keeps_latest(self):
        reg = DomainRegistry()
        a = FakeDomain(name="dup")
        b = FakeDomain(name="dup")
        reg.register(a)
        reg.register(b)
        # The registry keeps the latest object under the same name.
        assert reg._domains["dup"] is b


# ---------------------------------------------------------------------------
# DomainRegistry: activation
# ---------------------------------------------------------------------------


class TestDomainActivation:
    def test_activate_marks_active(self):
        reg = DomainRegistry()
        domain = FakeDomain(name="x")
        reg.register(domain)
        reg.activate("x")
        assert reg.is_active("x")
        assert domain in reg.get_active()

    def test_activate_calls_register(self):
        reg = DomainRegistry()
        domain = FakeDomain(name="x")
        reg.register(domain)
        reg.activate("x")
        # The registry MUST have called domain.register(registry) once.
        assert domain.register_calls == [reg]

    def test_activate_unknown_raises(self):
        reg = DomainRegistry()
        with pytest.raises(KeyError) as exc_info:
            reg.activate("ghost")
        assert "ghost" in str(exc_info.value)

    def test_activate_is_idempotent(self):
        reg = DomainRegistry()
        domain = FakeDomain(name="x")
        reg.register(domain)
        reg.activate("x")
        reg.activate("x")
        # Calling register() on a re-activate should NOT happen again.
        assert len(domain.register_calls) == 1

    def test_activate_after_deactivate_re_runs_register(self):
        reg = DomainRegistry()
        domain = FakeDomain(name="x")
        reg.register(domain)
        reg.activate("x")
        reg.deactivate("x")
        reg.activate("x")
        assert len(domain.register_calls) == 2


# ---------------------------------------------------------------------------
# DomainRegistry: deactivation
# ---------------------------------------------------------------------------


class TestDomainDeactivation:
    def test_deactivate_removes_from_active(self):
        reg = DomainRegistry()
        domain = FakeDomain(name="x")
        reg.register(domain)
        reg.activate("x")
        reg.deactivate("x")
        assert not reg.is_active("x")
        assert domain not in reg.get_active()
        # Domain remains registered (you can re-activate).
        assert reg.is_registered("x")

    def test_cannot_deactivate_general(self):
        reg = DomainRegistry()
        reg.register(GeneralDomain())
        reg.activate("general")
        with pytest.raises(ValueError) as exc_info:
            reg.deactivate("general")
        assert "general" in str(exc_info.value).lower()

    def test_deactivate_inactive_is_noop(self):
        reg = DomainRegistry()
        reg.register(FakeDomain(name="inactive"))
        # Never activated, so deactivating should be a no-op (no exception).
        reg.deactivate("inactive")
        assert not reg.is_active("inactive")


# ---------------------------------------------------------------------------
# DomainRegistry: queries
# ---------------------------------------------------------------------------


class TestDomainQueries:
    def test_get_active_metadata_returns_in_activation_order(self):
        reg = DomainRegistry()
        reg.register(GeneralDomain())
        reg.register(FakeDomain(name="x"))
        reg.register(FakeDomain(name="y"))
        reg.activate("general")
        reg.activate("x")
        reg.activate("y")
        names = [m.name for m in reg.get_active_metadata()]
        assert names == ["general", "x", "y"]

    def test_get_all_disclaimers_concatenates_active(self):
        reg = DomainRegistry()
        reg.register(GeneralDomain())
        reg.register(FakeDomain(
            name="x",
            disclaimers=["X-line-1", "X-line-2"],
        ))
        reg.activate("general")
        reg.activate("x")
        all_disc = reg.get_all_disclaimers()
        # general provides its own lines; x provides its two.
        assert any("通用领域" in line for line in all_disc)
        assert "X-line-1" in all_disc
        assert "X-line-2" in all_disc
        # Inactive domains must NOT contribute.
        reg.register(FakeDomain(
            name="inactive",
            disclaimers=["INACTIVE-MARKER"],
        ))
        assert "INACTIVE-MARKER" not in reg.get_all_disclaimers()

    def test_list_available_includes_unactivated(self):
        reg = DomainRegistry()
        reg.register(GeneralDomain())
        reg.register(FakeDomain(name="a"))
        reg.register(FakeDomain(name="b"))
        reg.activate("a")
        # list_available returns ALL registered domains, not just active.
        assert set(reg.list_available()) == {"general", "a", "b"}


# ---------------------------------------------------------------------------
# load_default_domains
# ---------------------------------------------------------------------------


class TestLoadDefaultDomains:
    def test_load_default_activates_general_and_adas(self):
        reg = load_default_domains()
        assert reg.is_active("general")
        assert reg.is_active("adas")
        assert "general" in reg.list_available()
        assert "adas" in reg.list_available()

    def test_load_default_disclaimers_include_adas(self):
        reg = load_default_domains()
        all_disc = reg.get_all_disclaimers()
        # ADAS domain MUST contribute its advisory disclaimer.
        assert any("ADAS" in line for line in all_disc)
        # General domain MUST contribute its general advisory.
        assert any("通用领域" in line for line in all_disc)

    def test_default_adas_can_be_deactivated(self):
        reg = load_default_domains()
        reg.deactivate("adas")
        assert not reg.is_active("adas")
        assert reg.is_active("general")
        # Its disclaimer is gone too.
        all_disc = reg.get_all_disclaimers()
        assert not any("ADAS" in line for line in all_disc)

    def test_default_general_cannot_be_deactivated(self):
        reg = load_default_domains()
        with pytest.raises(ValueError):
            reg.deactivate("general")


# ---------------------------------------------------------------------------
# Built-in domains: structural smoke tests
# ---------------------------------------------------------------------------


class TestBuiltinDomains:
    def test_general_domain_metadata(self):
        d = GeneralDomain()
        assert d.metadata.name == "general"
        assert d.metadata.safety_profile == "advisory"
        # Display name is bilingual.
        assert "通用" in d.metadata.display_name

    def test_general_domain_disclaimers_non_empty(self):
        d = GeneralDomain()
        disc = d.get_safety_disclaimers()
        assert len(disc) >= 1
        # Has at least one Chinese and one English line.
        assert any(any('一' <= c <= '鿿' for c in line) for line in disc)
        assert any(line == line.encode("ascii", "ignore").decode("ascii").strip()
                   and line.strip() for line in disc)

    def test_adas_domain_metadata(self):
        d = ADASDomain()
        assert d.metadata.name == "adas"
        assert d.metadata.safety_profile == "advisory"
        assert "智驾" in d.metadata.display_name or "ADAS" in d.metadata.display_name

    def test_adas_domain_disclaimers_advisory_only(self):
        d = ADASDomain()
        disc = d.get_safety_disclaimers()
        assert len(disc) >= 1
        # ADAS disclaimers must mention "advisory" or "模板" (template) or
        # "certification" — they MUST NOT claim compliance.
        joined = " ".join(disc).lower()
        assert (
            "advisory" in joined
            or "模板" in " ".join(disc)
            or "template" in joined
            or "certification" in joined
        )

    def test_adas_register_hooks_skill_registration(self):
        """ADASDomain.register() must tolerate a non-skill-aware registry.

        The default DomainRegistry.register_skill is a no-op shim. The
        ADAS register() call should NOT crash when given a bare
        DomainRegistry — it should iterate the ADAS skill classes and
        call registry.register_skill on each.
        """
        reg = DomainRegistry()
        d = ADASDomain()
        # Should not raise.
        d.register(reg)
        # The ADASDomain metadata is unchanged after register().
        assert d.metadata.name == "adas"


# ---------------------------------------------------------------------------
# Multi-domain composition
# ---------------------------------------------------------------------------


class TestMultiDomainComposition:
    def test_third_party_domain_activates_alongside_adas(self):
        reg = load_default_domains()
        third = FakeDomain(
            name="legal",
            disclaimers=["Legal domain: not legal advice."],
        )
        reg.register(third)
        reg.activate("legal")
        active = reg.get_active()
        names = [d.metadata.name for d in active]
        assert "general" in names
        assert "adas" in names
        assert "legal" in names
        # Disclaimer from the third party shows up.
        assert any("legal advice" in line.lower() for line in reg.get_all_disclaimers())

    def test_disable_one_domain_keep_others(self):
        reg = load_default_domains()
        third = FakeDomain(name="legal")
        reg.register(third)
        reg.activate("legal")
        reg.deactivate("adas")
        names = [d.metadata.name for d in reg.get_active()]
        assert "adas" not in names
        assert "general" in names
        assert "legal" in names
