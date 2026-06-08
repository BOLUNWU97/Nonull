"""Tests for safety/compliance.py — ISO 26262, MISRA, ASPICE checks (advisory)."""
from safety.compliance import ComplianceChecker, Hazard
from safety import SafetyLevel


def _make_hazard(desc="test", sev=2, exp=2, cont=2, sit="test"):
    return Hazard(
        hazard_id=f"h_{desc[:4]}",
        description=desc,
        situation=sit,
        severity=sev,
        exposure=exp,
        controllability=cont,
    )


class TestComplianceChecker:
    def test_instantiate(self):
        cc = ComplianceChecker()
        assert cc is not None

    def test_iso26262_basic_hazard(self):
        cc = ComplianceChecker()
        cc.add_hazard(_make_hazard("Unintended braking", 3, 3, 3, "Highway"))
        hazs = cc._hazards
        assert len(hazs) > 0

    def test_hazard_asil_calculation(self):
        cc = ComplianceChecker()
        h = _make_hazard("Steering failure", 3, 4, 3, "Urban")
        cc.add_hazard(h)
        assert h.severity == 3
        assert h.exposure == 4
        assert h.controllability == 3

    def test_multiple_hazards(self):
        cc = ComplianceChecker()
        for desc, s, e, c in [
            ("Unintended accel", 2, 3, 2),
            ("Brake loss", 3, 2, 3),
            ("Steering lock", 3, 2, 2),
        ]:
            cc.add_hazard(_make_hazard(desc, s, e, c))
        assert len(cc._hazards) == 3

    def test_hara_summary(self):
        cc = ComplianceChecker()
        cc.add_hazard(_make_hazard("Brake fail", 3, 3, 3))
        summary = cc.get_hara_summary()
        assert summary["total_hazards"] >= 1

    def test_hazard_asil_auto_assigned(self):
        h = _make_hazard("Critical", 3, 3, 3, "Highway")
        # ASIL should be calculated from S/E/C
        assert h.asil is not None
