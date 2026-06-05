"""
ADVISORY SAFETY — does not perform certified compliance assessments. The
ISO 26262, MISRA, ASPICE, and ISO 21434 checks in this file are PATTERN
MATCHING against published rule templates and clause text, NOT certified
compliance assessments. See README §Disclaimer and `safety.disclaimer:
advisory_only` in config.

Automotive Compliance Checker
==============================

ISO 26262 Functional Safety + ASPICE + MISRA + ISO 21434 compliance.

This module provides comprehensive compliance checking for autonomous driving
AI agents against automotive industry standards.

Standards Covered:
    - ISO 26262: Road vehicles — Functional safety (Parts 1-12)
    - ASPICE: Automotive SPICE process capability
    - MISRA C/C++: Coding guidelines for safety-critical systems
    - ISO 21434: Road vehicles — Cybersecurity engineering
    - Safety Case: Structured argument for system safety

Each compliance check maps to specific clauses in the relevant standard
and produces a ComplianceResult with pass/fail status and detailed findings.

Author: Nonull Safety Team
Version: 1.0.0
"""

from __future__ import annotations

import enum
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from safety import SafetyLevel, Verdict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ComplianceStandard(enum.Enum):
    """Automotive compliance standards."""
    ISO_26262 = "ISO 26262"
    ASPICE = "ASPICE"
    MISRA_C = "MISRA C"
    MISRA_CPP = "MISRA C++"
    ISO_21434 = "ISO 21434"
    SAFETY_CASE = "Safety Case"


class Severity(enum.IntEnum):
    """Severity of a compliance finding."""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ComplianceStatus(enum.Enum):
    """Status of a compliance check."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "n/a"
    NOT_CHECKED = "not_checked"


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class ComplianceFinding:
    """A single compliance finding."""
    finding_id: str
    standard: ComplianceStandard
    clause: str           # e.g., "ISO 26262-3:2018, Clause 7.4.2"
    severity: Severity
    status: ComplianceStatus
    title: str
    description: str
    recommendation: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.standard, str):
            for std in ComplianceStandard:
                if std.value == self.standard or std.name == self.standard:
                    self.standard = std
                    break
        if isinstance(self.severity, int):
            try:
                self.severity = Severity(self.severity)
            except ValueError:
                self.severity = Severity.MEDIUM
        if isinstance(self.status, str):
            try:
                self.status = ComplianceStatus(self.status)
            except ValueError:
                self.status = ComplianceStatus.NOT_CHECKED


@dataclass
class ComplianceResult:
    """Result of a compliance check."""
    standard: ComplianceStandard
    status: ComplianceStatus
    findings: List[ComplianceFinding] = field(default_factory=list)
    summary: str = ""
    score: float = 0.0            # 0.0 to 100.0
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def is_pass(self) -> bool:
        return self.status == ComplianceStatus.PASS

    def has_critical(self) -> bool:
        return any(f.severity == Severity.CRITICAL and f.status == ComplianceStatus.FAIL
                   for f in self.findings)

    def get_findings_by_severity(self, severity: Severity) -> List[ComplianceFinding]:
        return [f for f in self.findings if f.severity == severity]


@dataclass
class SafetyCase:
    """A structured safety case — argument that system is acceptably safe."""
    title: str
    goal: str
    arguments: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    is_valid: bool = False
    validated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# ISO 26262 Hazard Analysis and Risk Assessment (HARA)
# ---------------------------------------------------------------------------


@dataclass
class Hazard:
    """A hazard identified through HARA per ISO 26262-3."""
    hazard_id: str
    description: str
    situation: str                         # Operational situation
    severity: int                          # S0-S3 (0-3)
    exposure: int                          # E0-E4 (0-4)
    controllability: int                   # C0-C3 (0-3)
    asil: SafetyLevel = SafetyLevel.QM
    safety_goal: str = ""
    safety_measure: str = ""

    def calculate_asil(self) -> SafetyLevel:
        """Calculate ASIL from S/E/C parameters per ISO 26262-3 Table 2."""
        s = self.severity
        e = self.exposure
        c = self.controllability

        # Simplified ASIL determination matrix based on ISO 26262-3
        if s == 0:
            return SafetyLevel.QM
        if s == 1:
            if e == 0:
                return SafetyLevel.QM
            if e == 1:
                return SafetyLevel.QM if c <= 1 else SafetyLevel.ASIL_A
            if e == 2:
                return SafetyLevel.ASIL_A if c <= 2 else SafetyLevel.ASIL_B
            if e >= 3:
                return SafetyLevel.ASIL_B
        if s == 2:
            if e == 0:
                return SafetyLevel.QM
            if e == 1:
                return SafetyLevel.ASIL_A if c <= 1 else SafetyLevel.ASIL_B
            if e == 2:
                return SafetyLevel.ASIL_B if c <= 2 else SafetyLevel.ASIL_C
            if e >= 3:
                return SafetyLevel.ASIL_C
        if s == 3:
            if e == 0:
                return SafetyLevel.QM
            if e == 1:
                if c <= 1:
                    return SafetyLevel.ASIL_B
                return SafetyLevel.ASIL_C
            if e == 2:
                if c <= 1:
                    return SafetyLevel.ASIL_C
                return SafetyLevel.ASIL_D
            if e >= 3:
                if c == 0:
                    return SafetyLevel.ASIL_D
                return SafetyLevel.ASIL_D  # Always ASIL-D for S3+E3+
        return SafetyLevel.QM

    def __post_init__(self):
        if self.asil == SafetyLevel.QM:
            self.asil = self.calculate_asil()


# ---------------------------------------------------------------------------
# Compliance Checker
# ---------------------------------------------------------------------------


class ComplianceChecker:
    """Comprehensive automotive compliance checker.

    Checks agent actions and system state against:
        - ISO 26262 functional safety
        - ASPICE process capability
        - MISRA C/C++ coding standards
        - ISO 21434 cybersecurity
        - Safety case validation

    Thread-safe with per-standard locking.

    Usage:
        checker = ComplianceChecker()
        iso_result = checker.check_iso_26262(action)
        misra_result = checker.check_misra(code_snippet)
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._findings_log: List[ComplianceFinding] = []
        self._safety_cases: Dict[str, SafetyCase] = {}
        self._hazards: List[Hazard] = []

    # ------------------------------------------------------------------
    # ISO 26262 Functional Safety Checks
    # ------------------------------------------------------------------

    def check_iso_26262(self, action: Any) -> ComplianceResult:
        """Check an action against ISO 26262 functional safety requirements.

        Evaluates:
            - Part 3: Hazard analysis and risk assessment
            - Part 4: System-level safety requirements
            - Part 5: Hardware-level requirements
            - Part 6: Software-level requirements
            - Part 7: Production and operation
        """
        findings = []
        score = 100.0

        action_str = str(action)
        action_lower = action_str.lower()

        # ISO 26262-3: Hazard analysis
        if any(word in action_lower for word in ["brake", "steer", "throttle", "accelerat"]):
            findings.append(ComplianceFinding(
                finding_id="iso26262-3-001",
                standard="ISO 26262",
                clause="ISO 26262-3:2018, Clause 7.4 — HARA",
                severity=Severity.HIGH,
                status=ComplianceStatus.WARNING,
                title="Safety-critical vehicle control action",
                description=(
                    f"Action involves safety-critical vehicle control ({action_str}). "
                    f"Requires HARA per ISO 26262-3."
                ),
                recommendation="Ensure action is covered by HARA and safety goals",
            ))
            score -= 20.0

        # ISO 26262-6: Software safety
        if "override" in action_lower or "bypass" in action_lower:
            findings.append(ComplianceFinding(
                finding_id="iso26262-6-001",
                standard="ISO 26262",
                clause="ISO 26262-6:2018, Clause 7.4 — Software safety requirements",
                severity=Severity.CRITICAL,
                status=ComplianceStatus.FAIL,
                title="Software override detected",
                description=(
                    "Software override or bypass pattern detected. "
                    "ISO 26262-6 requires safety mechanisms for override functions."
                ),
                recommendation="Implement safe override with ASIL-D compliant mechanism",
            ))
            score -= 30.0

        # ISO 26262-4: System safety
        if "disable" in action_lower:
            findings.append(ComplianceFinding(
                finding_id="iso26262-4-001",
                standard="ISO 26262",
                clause="ISO 26262-4:2018, Clause 6.4 — System design",
                severity=Severity.HIGH,
                status=ComplianceStatus.FAIL,
                title="Function disable without safety concept",
                description=(
                    "Disabling a function without a system-level safety concept "
                    "violates ISO 26262-4 requirements."
                ),
                recommendation="Define degradation concept before allowing disable",
            ))
            score -= 25.0

        # ISO 26262-5: Hardware safety
        if any(sensor in action_lower for sensor in ["sensor", "camera", "lidar", "radar", "ultrasonic"]):
            findings.append(ComplianceFinding(
                finding_id="iso26262-5-001",
                standard="ISO 26262",
                clause="ISO 26262-5:2018, Clause 8 — Hardware architecture",
                severity=Severity.MEDIUM,
                status=ComplianceStatus.WARNING,
                title="Sensor-related action",
                description=(
                    "Sensor-related action detected. "
                    "ISO 26262-5 requires hardware fault detection coverage."
                ),
                recommendation="Verify sensor fault detection coverage ≥ 90%",
            ))
            score -= 15.0

        # Timing / deadline check (ISO 26262-6, Annex B)
        if any(word in action_lower for word in ["timeout", "deadline", "latency", "response_time"]):
            findings.append(ComplianceFinding(
                finding_id="iso26262-6-002",
                standard="ISO 26262",
                clause="ISO 26262-6:2018, Annex B — Timing monitoring",
                severity=Severity.MEDIUM,
                status=ComplianceStatus.WARNING,
                title="Timing-critical action detected",
                description="Real-time constraints must be verified per ISO 26262-6 timing monitoring.",
                recommendation="Verify worst-case execution time meets deadline",
            ))
            score -= 10.0

        # Freedom from interference (ISO 26262-6, Clause 7.4.13)
        if any(word in action_lower for word in ["shared_memory", "dma", "direct_access"]):
            findings.append(ComplianceFinding(
                finding_id="iso26262-6-003",
                standard="ISO 26262",
                clause="ISO 26262-6:2018, Clause 7.4.13 — Freedom from interference",
                severity=Severity.HIGH,
                status=ComplianceStatus.FAIL,
                title="Potential interference between software elements",
                description=(
                    "Direct memory access may cause interference between "
                    "software elements of different ASIL levels."
                ),
                recommendation="Implement memory protection and partitioning",
            ))
            score -= 25.0

        # Determine overall status
        critical_fails = [f for f in findings if f.severity == Severity.CRITICAL]
        high_fails = [f for f in findings if f.severity == Severity.HIGH and f.status == ComplianceStatus.FAIL]

        if critical_fails:
            status = ComplianceStatus.FAIL
        elif high_fails:
            status = ComplianceStatus.FAIL
        elif findings:
            status = ComplianceStatus.WARNING
        else:
            status = ComplianceStatus.PASS

        result = ComplianceResult(
            standard=ComplianceStandard.ISO_26262,
            status=status,
            findings=findings,
            summary=(
                f"ISO 26262 check: {len(findings)} finding(s) "
                f"({len(critical_fails)} critical, {len(high_fails)} high)"
            ),
            score=max(0.0, score),
        )

        with self._lock:
            self._findings_log.extend(findings)

        return result

    # ------------------------------------------------------------------
    # MISRA C/C++ Checks
    # ------------------------------------------------------------------

    def check_misra(self, code: str, language: str = "c") -> ComplianceResult:
        """Check code snippet against MISRA C or C++ guidelines.

        MISRA C:2012 (Amendment 2) — 16 mandatory, 93 required, 79 advisory rules
        MISRA C++:2023 — Comprehensive C++ safety rules

        This is a simplified static analysis — production use would integrate
        with a full MISRA checker (e.g., PC-lint, Coverity, QAC).
        """
        findings = []
        score = 100.0
        violations = []

        # MISRA C:2012 Rule 1.1 (Required) — No implementation-defined behavior
        impl_defined = re.findall(
            r'\b(char|short|int|long|float|double)\s+\w+\s*=\s*\d+\s*[+*-]\s*\d+',
            code
        )
        for match in impl_defined[:3]:
            violations.append(("MISRA C:2012 Rule 1.1", "Implementation-defined behavior", Severity.HIGH, match))

        # MISRA C:2012 Rule 10.1 (Required) — Boolean type restrictions
        if re.search(r'\bif\s*\(\s*\w+\s*=\s*\w+\s*\)', code):
            violations.append(("MISRA C:2012 Rule 10.1", "Assignment in boolean context", Severity.HIGH, ""))

        # MISRA C:2012 Rule 11.3 (Required) — Cast between pointer types
        ptr_casts = re.findall(r'\(\s*\w+\s*\*\s*\)', code)
        if ptr_casts:
            violations.append(("MISRA C:2012 Rule 11.3", f"Pointer type cast: {ptr_casts[0]}", Severity.MEDIUM, ptr_casts[0]))

        # MISRA C:2012 Rule 12.1 (Advisory) — Operator precedence
        complex_expr = re.findall(r'\w+\s*[+\-*/]\s*\w+\s*[+\-*/]\s*\w+', code)
        if complex_expr:
            violations.append(("MISRA C:2012 Rule 12.1", "Complex expression without parentheses", Severity.LOW, complex_expr[0]))

        # MISRA C:2012 Rule 13.3 (Required) — Full expression evaluation
        if re.search(r'\breturn\s+\w+\s*\+\s*\w+\s*\+\s*\w+', code):
            violations.append(("MISRA C:2012 Rule 13.3", "Multiple side effects in return", Severity.MEDIUM, ""))

        # MISRA C:2012 Rule 14.3 (Required) — Controlling expression is true/false
        if re.search(r'\bwhile\s*\(\s*\d+\s*\)', code):
            violations.append(("MISRA C:2012 Rule 14.3", "Controlling expression is constant", Severity.HIGH, ""))

        # MISRA C:2012 Rule 15.5 (Advisory) — Single function exit
        returns = list(re.finditer(r'\breturn\b', code))
        if len(returns) > 1:
            violations.append(("MISRA C:2012 Rule 15.5", f"Multiple return statements ({len(returns)})", Severity.LOW, ""))

        # MISRA C:2012 Rule 16.3 (Required) — Switch with default
        if re.search(r'\bswitch\b', code) and not re.search(r'\bdefault\b', code):
            violations.append(("MISRA C:2012 Rule 16.3", "Switch without default clause", Severity.MEDIUM, ""))

        # MISRA C:2012 Rule 17.3 (Mandatory) — No implicit function declaration
        if re.search(r'\bmalloc\b', code):
            violations.append(("MISRA C:2012 Rule 17.3", "malloc requires <stdlib.h> include", Severity.HIGH, ""))

        # MISRA C:2012 Rule 21.10 (Required) — No stdlib.h abort functions
        if re.search(r'\b(abort|exit|getenv|system)\b', code):
            violations.append(("MISRA C:2012 Rule 21.10", "Use of stdlib.h prohibited function", Severity.HIGH, ""))

        # MISRA C++:2023 Rule 0-1-1 (Required) — No dead code
        if re.search(r'/\*.*\*/', code) and re.search(r'#if\s+0', code):
            violations.append(("MISRA C++:2023 Rule 0-1-1", "Dead code via #if 0", Severity.MEDIUM, ""))

        # Convert violations to findings
        for rule, desc, sev, snippet in violations:
            findings.append(ComplianceFinding(
                finding_id=f"misra_{hash(rule) % 100000:05d}",
                standard=ComplianceStandard.MISRA_C if language.lower() == "c" else ComplianceStandard.MISRA_CPP,
                clause=rule,
                severity=sev,
                status=ComplianceStatus.FAIL,
                title=f"MISRA violation: {desc[:60]}",
                description=desc + (f" (snippet: {snippet[:80]})" if snippet else ""),
                recommendation=f"Review and fix {rule} violation",
            ))
            score -= {Severity.CRITICAL: 15, Severity.HIGH: 10, Severity.MEDIUM: 5, Severity.LOW: 2}.get(sev, 5)

        # Determine status
        high_or_critical = [f for f in findings if f.severity >= Severity.HIGH]
        status = ComplianceStatus.FAIL if high_or_critical else (
            ComplianceStatus.WARNING if findings else ComplianceStatus.PASS
        )

        if not findings:
            findings.append(ComplianceFinding(
                finding_id="misra_clean",
                standard=ComplianceStandard.MISRA_C if language.lower() == "c" else ComplianceStandard.MISRA_CPP,
                clause="General",
                severity=Severity.INFO,
                status=ComplianceStatus.PASS,
                title="No MISRA violations detected",
                description="Code passed MISRA static analysis checks.",
            ))

        result = ComplianceResult(
            standard=ComplianceStandard.MISRA_C if language.lower() == "c" else ComplianceStandard.MISRA_CPP,
            status=status,
            findings=findings,
            summary=f"MISRA check: {len(violations)} violation(s) found",
            score=max(0.0, score),
        )

        with self._lock:
            self._findings_log.extend(findings)

        return result

    # ------------------------------------------------------------------
    # ASPICE Process Compliance
    # ------------------------------------------------------------------

    def check_aspice(self, process_area: str, artifacts: Dict[str, Any]) -> ComplianceResult:
        """Check compliance against ASPICE process areas.

        ASPICE v3.1 defines process capability levels 0-5 across multiple
        process areas (SYS.1-5, SWE.1-6, SUP.1-10, ACQ.1-4, MAN.1-5).

        Args:
            process_area: ASPICE process area (e.g., "SWE.1", "SYS.2")
            artifacts: Dict of process artifacts and their status
        """
        findings = []
        score = 100.0

        aspice_requirements = {
            "SWE.1": {
                "title": "Software Requirements Analysis",
                "base_practices": [
                    ("BP1", "Specify software requirements", 10.0),
                    ("BP2", "Structure software requirements", 10.0),
                    ("BP3", "Analyze software requirements", 15.0),
                    ("BP4", "Analyze impact on other requirements", 10.0),
                    ("BP5", "Ensure bidirectional traceability", 15.0),
                    ("BP6", "Ensure consistency", 10.0),
                ]
            },
            "SWE.2": {
                "title": "Software Architectural Design",
                "base_practices": [
                    ("BP1", "Describe software architecture", 10.0),
                    ("BP2", "Allocate software requirements", 10.0),
                    ("BP3", "Define interfaces", 10.0),
                    ("BP4", "Describe dynamic behavior", 10.0),
                    ("BP5", "Verify software architecture", 15.0),
                ]
            },
            "SWE.3": {
                "title": "Software Detailed Design and Unit Construction",
                "base_practices": [
                    ("BP1", "Design software units", 10.0),
                    ("BP2", "Define unit interfaces", 10.0),
                    ("BP3", "Describe dynamic behavior of units", 10.0),
                    ("BP4", "Verify software units", 15.0),
                    ("BP5", "Develop software units", 10.0),
                    ("BP6", "Ensure bidirectional traceability", 10.0),
                ]
            },
            "SWE.4": {
                "title": "Software Unit Verification",
                "base_practices": [
                    ("BP1", "Define unit verification strategy", 10.0),
                    ("BP2", "Define unit test specification", 10.0),
                    ("BP3", "Execute unit tests", 15.0),
                    ("BP4", "Summarize unit test results", 10.0),
                ]
            },
            "SWE.5": {
                "title": "Software Integration and Integration Test",
                "base_practices": [
                    ("BP1", "Define integration strategy", 10.0),
                    ("BP2", "Define integration test specification", 10.0),
                    ("BP3", "Integrate software units", 10.0),
                    ("BP4", "Execute integration tests", 15.0),
                    ("BP5", "Summarize integration test results", 10.0),
                ]
            },
            "SWE.6": {
                "title": "Software Qualification Test",
                "base_practices": [
                    ("BP1", "Define qualification test specification", 10.0),
                    ("BP2", "Test software", 15.0),
                    ("BP3", "Summarize test results", 10.0),
                ]
            },
        }

        if process_area not in aspice_requirements:
            return ComplianceResult(
                standard=ComplianceStandard.ASPICE,
                status=ComplianceStatus.NOT_APPLICABLE,
                findings=[ComplianceFinding(
                    finding_id="aspice_unknown",
                    standard=ComplianceStandard.ASPICE,
                    clause=f"ASPICE {process_area}",
                    severity=Severity.INFO,
                    status=ComplianceStatus.NOT_CHECKED,
                    title=f"Unknown ASPICE process area: {process_area}",
                    description=f"ASPICE process area {process_area} is not recognized.",
                )],
                summary=f"ASPICE: {process_area} not recognized",
                score=0.0,
            )

        reqs = aspice_requirements[process_area]
        for bp_id, bp_desc, bp_weight in reqs["base_practices"]:
            artifact_key = f"{process_area}_{bp_id}"
            artifact_status = artifacts.get(artifact_key, "missing")

            if artifact_status == "implemented":
                findings.append(ComplianceFinding(
                    finding_id=f"aspice_{process_area}_{bp_id}",
                    standard=ComplianceStandard.ASPICE,
                    clause=f"ASPICE {process_area} {bp_id}",
                    severity=Severity.INFO,
                    status=ComplianceStatus.PASS,
                    title=f"{bp_id}: {bp_desc}",
                    description=f"Base practice {bp_id} is implemented.",
                ))
                score += bp_weight
            elif artifact_status == "partial":
                findings.append(ComplianceFinding(
                    finding_id=f"aspice_{process_area}_{bp_id}",
                    standard=ComplianceStandard.ASPICE,
                    clause=f"ASPICE {process_area} {bp_id}",
                    severity=Severity.MEDIUM,
                    status=ComplianceStatus.WARNING,
                    title=f"{bp_id}: {bp_desc} (partial)",
                    description=f"Base practice {bp_id} is partially implemented.",
                    recommendation=f"Complete the implementation of {bp_desc}",
                ))
                score += bp_weight * 0.5
            else:
                findings.append(ComplianceFinding(
                    finding_id=f"aspice_{process_area}_{bp_id}",
                    standard=ComplianceStandard.ASPICE,
                    clause=f"ASPICE {process_area} {bp_id}",
                    severity=Severity.HIGH,
                    status=ComplianceStatus.FAIL,
                    title=f"{bp_id}: {bp_desc} (missing)",
                    description=f"Base practice {bp_id} is not implemented.",
                    recommendation=f"Implement {bp_desc} to meet ASPICE requirements",
                ))

        # Normalize score to 0-100
        max_possible = sum(w for _, _, w in reqs["base_practices"])
        score = min(100.0, (score / max_possible) * 100.0)

        has_fails = any(f.status == ComplianceStatus.FAIL for f in findings)
        status = ComplianceStatus.FAIL if has_fails else (
            ComplianceStatus.WARNING if any(f.status == ComplianceStatus.WARNING for f in findings)
            else ComplianceStatus.PASS
        )

        result = ComplianceResult(
            standard=ComplianceStandard.ASPICE,
            status=status,
            findings=findings,
            summary=f"ASPICE {process_area} ({reqs['title']}): {sum(1 for f in findings if f.status == ComplianceStatus.FAIL)} missing, {sum(1 for f in findings if f.status == ComplianceStatus.WARNING)} partial",
            score=round(score, 1),
        )

        with self._lock:
            self._findings_log.extend(findings)

        return result

    # ------------------------------------------------------------------
    # ISO 21434 Cybersecurity Checks
    # ------------------------------------------------------------------

    def check_iso_21434(self, action: Any) -> ComplianceResult:
        """Check an action against ISO 21434 cybersecurity requirements.

        ISO 21434: Road vehicles — Cybersecurity engineering.
        Evaluates TARA (Threat Analysis and Risk Assessment) compliance.
        """
        findings = []
        score = 100.0
        action_str = str(action)
        action_lower = action_str.lower()

        # ISO 21434 Clause 9: Cybersecurity concept
        if any(word in action_lower for word in ["network", "can_bus", "ethernet", "lin_bus", "flexray"]):
            findings.append(ComplianceFinding(
                finding_id="iso21434-9-001",
                standard="ISO 21434",
                clause="ISO 21434:2021, Clause 9 — Cybersecurity concept",
                severity=Severity.HIGH,
                status=ComplianceStatus.WARNING,
                title="In-vehicle network communication",
                description=(
                    "In-vehicle network communication requires cybersecurity concept "
                    "per ISO 21434 Clause 9."
                ),
                recommendation="Ensure communication is protected per cybersecurity concept",
            ))
            score -= 20.0

        # ISO 21434 Clause 10: Cyber threat analysis (TARA)
        if "ota" in action_lower or "over-the-air" in action_lower or "wireless" in action_lower:
            findings.append(ComplianceFinding(
                finding_id="iso21434-10-001",
                standard="ISO 21434",
                clause="ISO 21434:2021, Clause 10 — Threat analysis",
                severity=Severity.CRITICAL,
                status=ComplianceStatus.FAIL,
                title="Wireless/OTA communication without TARA",
                description=(
                    "Wireless or OTA communication without completed TARA "
                    "violates ISO 21434 Clause 10."
                ),
                recommendation="Complete threat analysis before OTA operations",
            ))
            score -= 30.0

        # ISO 21434 Clause 11: Cybersecurity requirements
        if any(word in action_lower for word in ["ecu", "firmware", "flash", "update"]) and \
           any(word in action_lower for word in ["write", "modify", "flash", "reprogram"]):
            findings.append(ComplianceFinding(
                finding_id="iso21434-11-001",
                standard="ISO 21434",
                clause="ISO 21434:2021, Clause 11 — Cybersecurity requirements",
                severity=Severity.HIGH,
                status=ComplianceStatus.WARNING,
                title="ECU firmware modification",
                description=(
                    "ECU firmware modification requires cybersecurity requirements "
                    "per ISO 21434 Clause 11."
                ),
                recommendation="Verify secure boot and authenticated updates",
            ))
            score -= 20.0

        # ISO 21434 Clause 14: Validation
        if "release" in action_lower or "deploy" in action_lower:
            findings.append(ComplianceFinding(
                finding_id="iso21434-14-001",
                standard="ISO 21434",
                clause="ISO 21434:2021, Clause 14 — Validation",
                severity=Severity.MEDIUM,
                status=ComplianceStatus.WARNING,
                title="Release without cybersecurity validation",
                description=(
                    "Release or deployment without cybersecurity validation "
                    "per ISO 21434 Clause 14."
                ),
                recommendation="Complete cybersecurity validation before release",
            ))
            score -= 15.0

        # ISO 21434 Clause 15: Incident response
        if any(word in action_lower for word in ["anomaly", "attack", "intrusion", "breach", "compromise"]):
            findings.append(ComplianceFinding(
                finding_id="iso21434-15-001",
                standard="ISO 21434",
                clause="ISO 21434:2021, Clause 15 — Incident response",
                severity=Severity.HIGH,
                status=ComplianceStatus.WARNING,
                title="Security incident without response plan",
                description=(
                    "Security incident response requires established process "
                    "per ISO 21434 Clause 15."
                ),
                recommendation="Ensure incident response plan is activated",
            ))
            score -= 15.0

        # ISO 21434 Clause 8: Cybersecurity management
        if any(word in action_lower for word in ["third_party", "external", "vendor", "supplier"]):
            findings.append(ComplianceFinding(
                finding_id="iso21434-8-001",
                standard="ISO 21434",
                clause="ISO 21434:2021, Clause 8 — Cybersecurity management",
                severity=Severity.MEDIUM,
                status=ComplianceStatus.WARNING,
                title="External/supplier interaction without cybersecurity assessment",
                description=(
                    "External party interaction requires cybersecurity management "
                    "per ISO 21434 Clause 8."
                ),
                recommendation="Perform supplier cybersecurity assessment",
            ))
            score -= 10.0

        # Determine status
        critical_fails = [f for f in findings if f.severity == Severity.CRITICAL]
        status = ComplianceStatus.FAIL if critical_fails else (
            ComplianceStatus.WARNING if findings else ComplianceStatus.PASS
        )

        result = ComplianceResult(
            standard=ComplianceStandard.ISO_21434,
            status=status,
            findings=findings,
            summary=f"ISO 21434 check: {len(findings)} finding(s) ({len(critical_fails)} critical)",
            score=max(0.0, score),
        )

        with self._lock:
            self._findings_log.extend(findings)

        return result

    # ------------------------------------------------------------------
    # Safety Case Management
    # ------------------------------------------------------------------

    def create_safety_case(self, case_id: str, title: str, goal: str) -> SafetyCase:
        """Create a new safety case.

        A safety case is a structured argument, supported by evidence,
        that a system is acceptably safe for a given application.
        """
        case = SafetyCase(
            title=title,
            goal=goal,
        )
        with self._lock:
            self._safety_cases[case_id] = case
        logger.info("Safety case created: %s - %s", case_id, title)
        return case

    def add_argument(self, case_id: str, argument: str) -> bool:
        """Add an argument to a safety case."""
        with self._lock:
            case = self._safety_cases.get(case_id)
            if case is None:
                return False
            case.arguments.append(argument)
            return True

    def add_evidence(self, case_id: str, evidence: str) -> bool:
        """Add evidence to a safety case."""
        with self._lock:
            case = self._safety_cases.get(case_id)
            if case is None:
                return False
            case.evidence.append(evidence)
            return True

    def add_assumption(self, case_id: str, assumption: str) -> bool:
        """Add an assumption to a safety case."""
        with self._lock:
            case = self._safety_cases.get(case_id)
            if case is None:
                return False
            case.assumptions.append(assumption)
            return True

    def validate_safety_case(self, case_id: str) -> Optional[ComplianceResult]:
        """Validate a safety case for completeness and soundness.

        A valid safety case must have:
            - At least one clear safety goal
            - Arguments linking the goal to evidence
            - Sufficient evidence
            - Documented assumptions
        """
        with self._lock:
            case = self._safety_cases.get(case_id)
            if case is None:
                return None

        findings = []
        score = 100.0

        # Check goal is defined
        if not case.goal:
            findings.append(ComplianceFinding(
                finding_id="sc_goal_missing",
                standard=ComplianceStandard.SAFETY_CASE,
                clause="Safety Case — Goal Definition",
                severity=Severity.CRITICAL,
                status=ComplianceStatus.FAIL,
                title="Safety goal is missing",
                description="A safety case must have at least one clear safety goal.",
                recommendation="Define the top-level safety goal of the system.",
            ))
            score -= 40.0

        # Check arguments
        if not case.arguments:
            findings.append(ComplianceFinding(
                finding_id="sc_args_missing",
                standard=ComplianceStandard.SAFETY_CASE,
                clause="Safety Case — Argumentation",
                severity=Severity.HIGH,
                status=ComplianceStatus.FAIL,
                title="No arguments provided",
                description="Safety case must include arguments linking goal to evidence.",
                recommendation="Add structured arguments (e.g., GSN notation) to the safety case.",
            ))
            score -= 30.0
        else:
            findings.append(ComplianceFinding(
                finding_id="sc_args_ok",
                standard=ComplianceStandard.SAFETY_CASE,
                clause="Safety Case — Argumentation",
                severity=Severity.INFO,
                status=ComplianceStatus.PASS,
                title=f"{len(case.arguments)} argument(s) defined",
                description=f"Safety case has {len(case.arguments)} arguments.",
            ))
            score += min(20.0, len(case.arguments) * 5.0)

        # Check evidence
        if not case.evidence:
            findings.append(ComplianceFinding(
                finding_id="sc_evidence_missing",
                standard=ComplianceStandard.SAFETY_CASE,
                clause="Safety Case — Evidence",
                severity=Severity.HIGH,
                status=ComplianceStatus.FAIL,
                title="No evidence provided",
                description="Safety case must include evidence supporting the arguments.",
                recommendation="Add evidence (test results, analyses, reviews) to support each argument.",
            ))
            score -= 30.0
        else:
            findings.append(ComplianceFinding(
                finding_id="sc_evidence_ok",
                standard=ComplianceStandard.SAFETY_CASE,
                clause="Safety Case — Evidence",
                severity=Severity.INFO,
                status=ComplianceStatus.PASS,
                title=f"{len(case.evidence)} evidence item(s)",
                description=f"Safety case has {len(case.evidence)} evidence items.",
            ))
            score += min(20.0, len(case.evidence) * 5.0)

        # Check assumptions
        if not case.assumptions:
            findings.append(ComplianceFinding(
                finding_id="sc_assumptions_missing",
                standard=ComplianceStandard.SAFETY_CASE,
                clause="Safety Case — Assumptions",
                severity=Severity.MEDIUM,
                status=ComplianceStatus.WARNING,
                title="No assumptions documented",
                description=(
                    "Safety case should document assumptions. "
                    "Undocumented assumptions weaken the safety argument."
                ),
                recommendation="Document all assumptions that the safety case depends on.",
            ))
            score -= 10.0

        # Determine validity
        has_goal = bool(case.goal)
        has_arguments = bool(case.arguments)
        has_evidence = bool(case.evidence)
        is_valid = has_goal and has_arguments and has_evidence

        case.is_valid = is_valid
        case.validated_at = datetime.utcnow().isoformat()

        status = ComplianceStatus.PASS if is_valid else ComplianceStatus.FAIL
        result = ComplianceResult(
            standard=ComplianceStandard.SAFETY_CASE,
            status=status,
            findings=findings,
            summary=f"Safety case validation: {'VALID' if is_valid else 'INVALID'} (score: {score:.1f}/100)",
            score=max(0.0, min(100.0, score)),
        )

        with self._lock:
            self._findings_log.extend(findings)

        return result

    # ------------------------------------------------------------------
    # Hazard Analysis and Risk Assessment (HARA)
    # ------------------------------------------------------------------

    def add_hazard(self, hazard: Hazard) -> None:
        """Add a hazard from HARA."""
        hazard.asil = hazard.calculate_asil()
        with self._lock:
            self._hazards.append(hazard)
        logger.info(
            "Hazard added: %s (S%d/E%d/C%d -> %s)",
            hazard.hazard_id, hazard.severity, hazard.exposure,
            hazard.controllability, hazard.asil.name,
        )

    def get_hazards_by_asil(self, asil: SafetyLevel) -> List[Hazard]:
        """Get all hazards at or above a given ASIL level."""
        return [h for h in self._hazards if h.asil.value >= asil.value]

    def get_hara_summary(self) -> Dict[str, Any]:
        """Get a summary of the hazard analysis."""
        return {
            "total_hazards": len(self._hazards),
            "by_asil": {
                level.name: sum(1 for h in self._hazards if h.asil == level)
                for level in SafetyLevel
            },
            "highest_asil": max((h.asil for h in self._hazards), default=SafetyLevel.QM).name,
        }

    # ------------------------------------------------------------------
    # Comprehensive Compliance Report
    # ------------------------------------------------------------------

    def comprehensive_check(self, action: Any, code: Optional[str] = None,
                            aspice_area: Optional[str] = None,
                            aspice_artifacts: Optional[Dict[str, Any]] = None) -> Dict[str, ComplianceResult]:
        """Run all applicable compliance checks on an action.

        This is the main entry point for comprehensive compliance evaluation.

        Args:
            action: The agent action to check.
            code: Optional code snippet for MISRA checking.
            aspice_area: Optional ASPICE process area to check.
            aspice_artifacts: Optional ASPICE artifact statuses.

        Returns:
            Dict mapping standard names to ComplianceResults.
        """
        results = {}

        # ISO 26262
        results["ISO 26262"] = self.check_iso_26262(action)

        # ISO 21434
        results["ISO 21434"] = self.check_iso_21434(action)

        # MISRA (if code provided)
        if code:
            results["MISRA C"] = self.check_misra(code, language="c")

        # ASPICE (if area provided)
        if aspice_area:
            results[f"ASPICE {aspice_area}"] = self.check_aspice(
                aspice_area, aspice_artifacts or {}
            )

        return results

    def get_compliance_report(self) -> Dict[str, Any]:
        """Get a complete compliance report with all findings."""
        with self._lock:
            return {
                "total_findings": len(self._findings_log),
                "by_status": {
                    status.value: sum(1 for f in self._findings_log if f.status == status)
                    for status in ComplianceStatus
                },
                "by_severity": {
                    sev.name: sum(1 for f in self._findings_log if f.severity == sev)
                    for sev in Severity
                },
                "by_standard": {
                    std.value: sum(1 for f in self._findings_log if f.standard == std)
                    for std in ComplianceStandard
                },
                "critical_findings": [
                    {
                        "id": f.finding_id,
                        "standard": f.standard.value,
                        "clause": f.clause,
                        "title": f.title,
                        "description": f.description,
                    }
                    for f in self._findings_log
                    if f.severity >= Severity.HIGH and f.status == ComplianceStatus.FAIL
                ],
                "hara_summary": self.get_hara_summary(),
                "safety_cases": {
                    cid: {
                        "title": sc.title,
                        "goal": sc.goal,
                        "valid": sc.is_valid,
                        "num_arguments": len(sc.arguments),
                        "num_evidence": len(sc.evidence),
                        "num_assumptions": len(sc.assumptions),
                    }
                    for cid, sc in self._safety_cases.items()
                },
            }
