"""
Predefined Workflows for Autonomous Driving (自动驾驶预定义工作流)
==================================================================

This module defines domain-specific workflows for the Nonull system.
Each workflow is a template that the Orchestrator instantiates as an
OrchestrationPlan — a DAG of subtasks tailored to a specific autonomous
driving engineering activity.

Workflows (工作流)::

    1. Code Review Workflow     — Review C++/Python code for ADAS modules
    2. Safety Analysis Workflow — HARA, FMEA, FTA, safety case generation
    3. Test Generation Workflow — Generate SIL/HIL test cases from requirements
    4. Bug Triage Workflow      — Classify, prioritize, and assign bugs
    5. Architecture Review      — Review system/software architecture
    6. Scenario Generation      — Generate driving scenarios for simulation
    7. Compliance Check         — ISO 26262 / ASPICE compliance assessment
    8. Data Pipeline Review     — Review data processing and ML pipelines

Each workflow is defined as a ``WorkflowDefinition`` containing:
    - Unique ID and name
    - Description and domain tags
    - A factory function that produces an ``OrchestrationPlan``
    - Suggested agent types for each step
    - Expected input/output schema

ISO 26262 / ASPICE Alignment:
    - Workflows include traceability to safety standards
    - Safety-related workflows enforce ASIL decomposition
    - Output artifacts conform to work product templates
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from orchestration.orchestrator import (
    OrchestrationPlan,
    Subtask,
    DecompositionFn,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Data Types
# ===================================================================

class WorkflowStatus(str, enum.Enum):
    """Lifecycle status of a workflow instance."""

    PENDING = "pending"             # Defined but not started
    RUNNING = "running"             # Execution in progress
    COMPLETED = "completed"         # Successfully finished
    FAILED = "failed"               # Execution failed
    CANCELLED = "cancelled"         # Cancelled by user/system


@dataclass
class WorkflowStep:
    """
    A single step within a workflow definition.

    Attributes:
        name: Step name (e.g., "static_analysis").
        description: What this step does.
        agent_type: Required agent type.
        required_capabilities: Capabilities the agent must have.
        dependencies: Names of steps that must complete first.
        timeout_seconds: Max execution time.
        metadata: Additional configuration for this step.
    """

    name: str = ""
    description: str = ""
    agent_type: str = ""
    required_capabilities: Set[str] = field(default_factory=set)
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """
    A complete workflow template.

    Attributes:
        id: Unique identifier.
        name: Human-readable name.
        description: Detailed description.
        version: Version string.
        domain_tags: Tags for categorization (e.g., "safety", "testing").
        steps: Ordered list of workflow steps.
        decomposition_fn: Function that builds an OrchestrationPlan from
            a task description and this WorkflowDefinition.
        expected_inputs: Description of expected input data.
        expected_outputs: Description of expected output artifacts.
        safety_standard_refs: References to safety standards (ISO 26262, etc.).
        metadata: Arbitrary additional metadata.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    domain_tags: List[str] = field(default_factory=list)
    steps: List[WorkflowStep] = field(default_factory=list)
    decomposition_fn: Optional[DecompositionFn] = None
    expected_inputs: str = ""
    expected_outputs: str = ""
    safety_standard_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ===================================================================
# Workflow Registry
# ===================================================================

WorkflowFactory = Callable[[], WorkflowDefinition]
"""Signature for a workflow factory function."""


class WorkflowRegistry:
    """
    Registry of all available workflow definitions.

    Supports registration by ID and lookup for the Orchestrator to
    instantiate a plan.
    """

    def __init__(self) -> None:
        self._workflows: Dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        """Register a workflow definition."""
        if workflow.id in self._workflows:
            logger.warning(
                "Overwriting workflow %s", workflow.id
            )
        self._workflows[workflow.id] = workflow
        logger.info(
            "Workflow registered: %s (v%s, %d steps)",
            workflow.id,
            workflow.version,
            len(workflow.steps),
        )

    def get(self, workflow_id: str) -> WorkflowDefinition:
        """Get a workflow by ID."""
        wf = self._workflows.get(workflow_id)
        if wf is None:
            raise KeyError(
                f"Workflow {workflow_id!r} not found. "
                f"Available: {list(self._workflows)}"
            )
        return wf

    def list_workflows(
        self,
        domain_tag: Optional[str] = None,
    ) -> List[WorkflowDefinition]:
        """List all workflows, optionally filtered by domain tag."""
        if domain_tag is None:
            return list(self._workflows.values())
        return [
            wf
            for wf in self._workflows.values()
            if domain_tag in wf.domain_tags
        ]

    def instantiate(
        self,
        workflow_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationPlan:
        """
        Instantiate a workflow as an OrchestrationPlan.

        Uses the workflow's decomposition function to build the plan.
        If no custom decomposition function is set, a default one is
        generated from the workflow's step definitions.

        Args:
            workflow_id: The workflow to instantiate.
            task: The specific task/input for this instance.
            context: Additional context.

        Returns:
            An OrchestrationPlan ready for execution.

        Raises:
            KeyError: If the workflow_id is not registered.
        """
        wf = self.get(workflow_id)

        if wf.decomposition_fn:
            plan = wf.decomposition_fn(task, context or {})
        else:
            plan = self._default_decompose(wf, task, context or {})

        plan.metadata["workflow_id"] = workflow_id
        plan.metadata["workflow_name"] = wf.name
        plan.metadata["workflow_version"] = wf.version

        logger.info(
            "Instantiated workflow %s as plan %s (%d subtasks)",
            workflow_id,
            plan.id[:8],
            len(plan.subtasks),
        )
        return plan

    @staticmethod
    def _default_decompose(
        wf: WorkflowDefinition,
        task: str,
        context: Dict[str, Any],
    ) -> OrchestrationPlan:
        """Convert workflow steps into an OrchestrationPlan."""
        plan = OrchestrationPlan(
            task=task,
            metadata={
                "workflow_id": wf.id,
                "workflow_name": wf.name,
                **context,
            },
        )

        step_name_to_id: Dict[str, str] = {}

        for step in wf.steps:
            subtask = Subtask(
                task_id=plan.id,
                name=step.name,
                description=step.description,
                agent_type=step.agent_type,
                required_capabilities=step.required_capabilities,
                timeout_seconds=step.timeout_seconds,
                metadata=step.metadata,
            )

            # Resolve dependency names to subtask IDs
            for dep_name in step.dependencies:
                dep_id = step_name_to_id.get(dep_name)
                if dep_id:
                    subtask.dependencies.append(dep_id)

            plan.subtasks[subtask.id] = subtask
            step_name_to_id[step.name] = subtask.id

        # Compute root subtask IDs
        all_deps: Set[str] = set()
        for st in plan.subtasks.values():
            all_deps.update(st.dependencies)
        plan.root_subtask_ids = [
            sid
            for sid in plan.subtasks
            if sid not in all_deps
        ]

        return plan


# ===================================================================
# Workflow 1: Code Review Workflow (代码审查工作流)
# ===================================================================

def create_code_review_workflow() -> WorkflowDefinition:
    """
    Create the Code Review workflow for ADAS C++/Python code.

    Steps:
        1. static_analysis    — Run static analysis (MISRA, AUTOSAR)
        2. security_review    — Identify security vulnerabilities
        3. performance_review — Analyze performance characteristics
        4. coding_standards   — Check coding standards compliance
        5. summary_report     — Aggregate findings into a review report

    Inputs:
        - Source code repository path or diff
        - Coding standards configuration (MISRA C++ 2023, AUTOSAR C++14)
        - Review scope (full file, changed lines, specific modules)

    Outputs:
        - Static analysis findings with severity classification
        - Security vulnerability report
        - Performance regression analysis
        - Standards compliance score
        - Overall review summary with actionable recommendations
    """
    return WorkflowDefinition(
        id="code_review",
        name="Code Review Workflow (代码审查)",
        description=(
            "Comprehensive code review for ADAS software modules. "
            "Includes static analysis, security review, performance analysis, "
            "and coding standards compliance checking for C++ and Python code."
        ),
        version="2.0.0",
        domain_tags=["development", "quality", "adas"],
        steps=[
            WorkflowStep(
                name="static_analysis",
                description=(
                    "Run static analysis tools (MISRA C++ 2023, AUTOSAR C++14, "
                    "clang-tidy, pylint) on the target code."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "static_analysis", "misra_check",
                    "autosar_check",
                },
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="security_review",
                description=(
                    "Identify security vulnerabilities including buffer "
                    "overflows, injection flaws, and insecure data handling."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "python_review", "security_review",
                },
                dependencies=["static_analysis"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="performance_review",
                description=(
                    "Analyze performance characteristics: algorithmic "
                    "complexity, memory usage, real-time constraints."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "performance_analysis",
                },
                dependencies=["static_analysis"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="coding_standards",
                description=(
                    "Check compliance with coding standards including "
                    "naming conventions, documentation, and style guides."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "python_review", "coding_standards",
                },
                dependencies=["static_analysis"],
                timeout_seconds=180,
            ),
            WorkflowStep(
                name="summary_report",
                description=(
                    "Aggregate all findings into a comprehensive review "
                    "report with severity classification and recommendations."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "python_review", "reporting",
                },
                dependencies=[
                    "security_review",
                    "performance_review",
                    "coding_standards",
                ],
                timeout_seconds=120,
            ),
        ],
        expected_inputs=(
            "Source code (C++/Python), review scope configuration, "
            "coding standards profile"
        ),
        expected_outputs=(
            "Static analysis findings, security report, performance analysis, "
            "standards compliance score, review summary"
        ),
        safety_standard_refs=["MISRA C++ 2023", "AUTOSAR C++14", "ISO 26262-6"],
    )


# ===================================================================
# Workflow 2: Safety Analysis Workflow (安全分析工作流)
# ===================================================================

def create_safety_analysis_workflow() -> WorkflowDefinition:
    """
    Create the Safety Analysis workflow.

    Steps:
        1. hara           — Hazard Analysis and Risk Assessment
        2. safety_goals   — Define safety goals from hazards
        3. fmea           — Failure Mode and Effects Analysis
        4. fta            — Fault Tree Analysis
        5. safety_case    — Generate safety case argument

    ISO 26262 Alignment:
        - Part 3: Concept phase → HARA
        - Part 4: Product development → FMEA/FTA
        - Part 10: Safety case
    """
    return WorkflowDefinition(
        id="safety_analysis",
        name="Safety Analysis Workflow (安全分析)",
        description=(
            "Comprehensive safety analysis following ISO 26262. "
            "Performs HARA, FMEA, FTA, and generates a structured "
            "safety case with ASIL decomposition."
        ),
        version="2.1.0",
        domain_tags=["safety", "iso26262", "adas"],
        steps=[
            WorkflowStep(
                name="hara",
                description=(
                    "Hazard Analysis and Risk Assessment: identify "
                    "potential hazards, evaluate risk, determine ASIL levels."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "hara", "risk_assessment", "iso_26262",
                    "asil_determination",
                },
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="safety_goals",
                description=(
                    "Define safety goals from identified hazards. "
                    "Each safety goal includes ASIL rating and safe state."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "safety_goal_definition", "iso_26262",
                },
                dependencies=["hara"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="fmea",
                description=(
                    "Failure Mode and Effects Analysis: identify failure "
                    "modes, causes, effects, and mitigation measures."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "fmea", "risk_assessment", "iso_26262",
                },
                dependencies=["safety_goals"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="fta",
                description=(
                    "Fault Tree Analysis: top-down analysis of system "
                    "failures using boolean logic and probability."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "fta", "risk_assessment", "iso_26262",
                },
                dependencies=["safety_goals"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="safety_case",
                description=(
                    "Generate a structured safety case argument with "
                    "evidence mapping, claims, and confidence levels."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "safety_case", "iso_26262",
                },
                dependencies=["fmea", "fta"],
                timeout_seconds=480,
            ),
        ],
        expected_inputs=(
            "System architecture description, item definition, "
            "operational situations, failure modes catalog"
        ),
        expected_outputs=(
            "HARA report with ASIL determination, safety goals, "
            "FMEA worksheet, FTA diagrams, safety case argument"
        ),
        safety_standard_refs=[
            "ISO 26262-1:2018", "ISO 26262-3:2018",
            "ISO 26262-4:2018", "ISO 26262-9:2018", "ISO 26262-10:2018",
        ],
    )


# ===================================================================
# Workflow 3: Test Generation Workflow (测试生成工作流)
# ===================================================================

def create_test_generation_workflow() -> WorkflowDefinition:
    """
    Create the Test Generation workflow for SIL/HIL testing.

    Steps:
        1. requirement_analysis  — Parse and analyze requirements
        2. test_case_design      — Design test cases from requirements
        3. test_oracle           — Generate test oracles/assertions
        4. coverage_analysis     — Analyze functional coverage
        5. test_script_gen       — Generate executable test scripts

    Supports:
        - Requirement-based testing (RBT)
        - Scenario-based testing
        - Coverage-driven test generation
        - Regression test suite augmentation
    """
    return WorkflowDefinition(
        id="test_generation",
        name="Test Generation Workflow (测试生成)",
        description=(
            "Generate SIL (Software-in-the-Loop) and HIL "
            "(Hardware-in-the-Loop) test cases from requirements. "
            "Includes test oracles, coverage analysis, and executable "
            "test script generation."
        ),
        version="2.0.0",
        domain_tags=["testing", "sil", "hil", "validation"],
        steps=[
            WorkflowStep(
                name="requirement_analysis",
                description=(
                    "Parse requirements documents, extract testable "
                    "conditions, and identify equivalence classes."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "test_case_generation",
                    "requirement_based_testing",
                },
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="test_case_design",
                description=(
                    "Design test cases using boundary value analysis, "
                    "equivalence partitioning, and scenario-based methods."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "test_case_generation", "scenario_testing",
                },
                dependencies=["requirement_analysis"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="test_oracle",
                description=(
                    "Generate test oracles and assertions to verify "
                    "expected behavior and safety constraints."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "test_case_generation",
                },
                dependencies=["test_case_design"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="coverage_analysis",
                description=(
                    "Analyze functional, structural, and requirement "
                    "coverage. Identify gaps and suggest additional tests."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "coverage_analysis", "test_case_generation",
                },
                dependencies=["test_case_design"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="test_script_gen",
                description=(
                    "Generate executable test scripts for the target "
                    "SIL/HIL environment."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "test_case_generation", "sil_testing", "hil_testing",
                },
                dependencies=["test_oracle", "coverage_analysis"],
                timeout_seconds=600,
            ),
        ],
        expected_inputs=(
            "Requirements specification, system design, "
            "test environment configuration, coverage targets"
        ),
        expected_outputs=(
            "Test cases with oracles, coverage report, "
            "executable test scripts for SIL/HIL platforms"
        ),
        safety_standard_refs=[
            "ISO 26262-4:2018", "ISO 26262-6:2018",
            "ISO 26262-8:2018",
        ],
    )


# ===================================================================
# Workflow 4: Bug Triage Workflow (缺陷分类工作流)
# ===================================================================

def create_bug_triage_workflow() -> WorkflowDefinition:
    """
    Create the Bug Triage workflow.

    Steps:
        1. bug_classification    — Classify bug by type/component
        2. severity_assessment   — Assess severity and priority
        3. root_cause_analysis   — Analyze root cause
        4. fix_recommendation    — Generate fix recommendation
        5. assignment            — Assign to appropriate team

    Supports:
        - Automated bug classification using ML
        - Severity based on safety impact (ISO 26262)
        - Root cause analysis with FMEA integration
    """
    return WorkflowDefinition(
        id="bug_triage",
        name="Bug Triage Workflow (缺陷分类)",
        description=(
            "Automated bug triaging for ADAS software. Classifies bugs, "
            "assesses severity with safety context, performs root cause "
            "analysis, and recommends fixes."
        ),
        version="1.2.0",
        domain_tags=["quality", "development", "maintenance"],
        steps=[
            WorkflowStep(
                name="bug_classification",
                description=(
                    "Classify the bug by component, type (logic, memory, "
                    "timing, safety), and affected subsystem."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "test_case_generation",
                },
                timeout_seconds=120,
            ),
            WorkflowStep(
                name="severity_assessment",
                description=(
                    "Assess severity based on safety impact, frequency, "
                    "and detectability. Map to ASIL if applicable."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "risk_assessment", "iso_26262",
                },
                dependencies=["bug_classification"],
                timeout_seconds=180,
            ),
            WorkflowStep(
                name="root_cause_analysis",
                description=(
                    "Analyze root cause using defect pattern matching "
                    "and code/stack trace analysis."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "python_review", "static_analysis",
                },
                dependencies=["bug_classification"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="fix_recommendation",
                description=(
                    "Generate fix recommendations with code snippets, "
                    "test cases, and regression risk assessment."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "python_review",
                },
                dependencies=["root_cause_analysis", "severity_assessment"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="assignment",
                description=(
                    "Assign the bug to the appropriate team/owner "
                    "based on component, severity, and expertise."
                ),
                agent_type="orchestrator",
                required_capabilities={
                    "coordination", "task_decomposition",
                },
                dependencies=["fix_recommendation"],
                timeout_seconds=60,
            ),
        ],
        expected_inputs=(
            "Bug report (description, stack trace, logs, environment)"
        ),
        expected_outputs=(
            "Classification tags, severity score, root cause analysis, "
            "fix recommendation, assignment decision"
        ),
        safety_standard_refs=["ISO 26262-8:2018"],
    )


# ===================================================================
# Workflow 5: Architecture Review Workflow (架构评审工作流)
# ===================================================================

def create_architecture_review_workflow() -> WorkflowDefinition:
    """
    Create the Architecture Review workflow.

    Steps:
        1. architecture_extraction  — Extract architecture from docs/code
        2. pattern_analysis         — Analyze architectural patterns
        3. constraint_check         — Check non-functional constraints
        4. safety_architecture      — Review safety architecture
        5. review_report            — Generate architecture review report

    Covers:
        - Software architecture (ISO 26262-6)
        - System architecture (ISO 262KW-4)
        - Safety architecture (ISO 26262-9)
        - Hardware-software interface
    """
    return WorkflowDefinition(
        id="architecture_review",
        name="Architecture Review Workflow (架构评审)",
        description=(
            "Review system and software architecture for ADAS platforms. "
            "Analyzes patterns, checks constraints, reviews safety "
            "architecture, and generates a comprehensive review report."
        ),
        version="1.1.0",
        domain_tags=["architecture", "design", "safety"],
        steps=[
            WorkflowStep(
                name="architecture_extraction",
                description=(
                    "Extract architecture descriptions from design "
                    "documents, models, and code structure."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "python_review",
                },
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="pattern_analysis",
                description=(
                    "Analyze architectural patterns (layered, "
                    "microservice, event-driven) and their suitability."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "c++_review", "python_review", "static_analysis",
                },
                dependencies=["architecture_extraction"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="constraint_check",
                description=(
                    "Check non-functional constraints: real-time, "
                    "memory, latency, throughput, reliability."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "performance_analysis",
                },
                dependencies=["architecture_extraction"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="safety_architecture",
                description=(
                    "Review safety architecture: fault tolerance, "
                    "redundancy, fail-safe mechanisms, ASIL decomposition."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "iso_26262", "fmea", "fta",
                },
                dependencies=["pattern_analysis"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="review_report",
                description=(
                    "Aggregate findings into an architecture review "
                    "report with recommendations and risk assessment."
                ),
                agent_type="code_reviewer",
                required_capabilities={
                    "reporting",
                },
                dependencies=["constraint_check", "safety_architecture"],
                timeout_seconds=180,
            ),
        ],
        expected_inputs=(
            "Architecture documentation, design models, source code, "
            "constraint specifications"
        ),
        expected_outputs=(
            "Architecture review report, pattern analysis, constraint "
            "compliance matrix, safety architecture assessment"
        ),
        safety_standard_refs=[
            "ISO 26262-4:2018", "ISO 26262-6:2018", "ISO 26262-9:2018",
        ],
    )


# ===================================================================
# Workflow 6: Scenario Generation Workflow (场景生成工作流)
# ===================================================================

def create_scenario_generation_workflow() -> WorkflowDefinition:
    """
    Create the Scenario Generation workflow for driving simulation.

    Steps:
        1. operational_domain  — Define operational design domain (ODD)
        2. scenario_design     — Design driving scenarios
        3. parameter_variation — Generate parameter variations
        4. scenario_validation — Validate scenario feasibility
        5. scenario_export     — Export to simulation format (OpenSCENARIO)

    Supports:
        - ODD-based scenario parameterization
        - Critical scenario identification (edge cases)
        - Scenario variation for ML training data augmentation
        - OpenSCENARIO / ASAM OpenX standards
    """
    return WorkflowDefinition(
        id="scenario_generation",
        name="Scenario Generation Workflow (场景生成)",
        description=(
            "Generate driving scenarios for simulation-based testing. "
            "Covers operational design domain definition, scenario "
            "design, parameter variation, and export to standard formats."
        ),
        version="1.3.0",
        domain_tags=["testing", "simulation", "scenarios", "validation"],
        steps=[
            WorkflowStep(
                name="operational_domain",
                description=(
                    "Define the Operational Design Domain (ODD): "
                    "environmental conditions, road types, traffic "
                    "patterns, and speed ranges."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "scenario_testing",
                },
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="scenario_design",
                description=(
                    "Design driving scenarios based on ODD, including "
                    "nominal, critical, and edge-case scenarios."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "scenario_testing", "test_case_generation",
                },
                dependencies=["operational_domain"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="parameter_variation",
                description=(
                    "Generate parameter variations for each scenario: "
                    "speed, weather, lighting, traffic density, etc."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "scenario_testing",
                },
                dependencies=["scenario_design"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="scenario_validation",
                description=(
                    "Validate scenario feasibility, completeness, "
                    "and coverage of the ODD."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "scenario_testing", "coverage_analysis",
                },
                dependencies=["parameter_variation"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="scenario_export",
                description=(
                    "Export scenarios to OpenSCENARIO or other "
                    "simulation-compatible formats."
                ),
                agent_type="test_engineer",
                required_capabilities={
                    "scenario_testing",
                },
                dependencies=["scenario_validation"],
                timeout_seconds=180,
            ),
        ],
        expected_inputs=(
            "ODD specification, scenario catalog, parameter ranges, "
            "simulation platform configuration"
        ),
        expected_outputs=(
            "Scenario catalog with parameter variations, validation "
            "report, OpenSCENARIO export files"
        ),
        safety_standard_refs=[
            "ISO 26262-4:2018", "ISO 21448:2022 (SOTIF)",
            "ASAM OpenSCENARIO",
        ],
    )


# ===================================================================
# Workflow 7: Compliance Check Workflow (合规检查工作流)
# ===================================================================

def create_compliance_check_workflow() -> WorkflowDefinition:
    """
    Create the Compliance Check workflow for ISO 26262 / ASPICE.

    Steps:
        1. standard_mapping     — Map artifacts to standard requirements
        2. gap_analysis         — Identify compliance gaps
        3. evidence_collection  — Collect evidence for each requirement
        4. assessment           — Assess compliance level
        5. improvement_plan     — Generate improvement recommendations

    Covers:
        - ISO 26262:2018 (all parts)
        - ASPICE v3.1 / v4.0
        - Automotive Cybersecurity (ISO 21434)
        - SOTIF (ISO 21448)
    """
    return WorkflowDefinition(
        id="compliance_check",
        name="Compliance Check Workflow (合规检查)",
        description=(
            "Assess compliance with automotive standards including "
            "ISO 26262 (functional safety), ASPICE (process capability), "
            "ISO 21434 (cybersecurity), and ISO 21448 (SOTIF)."
        ),
        version="1.2.0",
        domain_tags=["compliance", "safety", "quality", "aspice"],
        steps=[
            WorkflowStep(
                name="standard_mapping",
                description=(
                    "Map project artifacts and work products to "
                    "standard-specific requirements and outcomes."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "iso_26262", "risk_assessment",
                },
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="gap_analysis",
                description=(
                    "Identify gaps between current state and "
                    "standard requirements, including missing artifacts, "
                    "incomplete coverage, and process gaps."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "iso_26262", "risk_assessment",
                },
                dependencies=["standard_mapping"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="evidence_collection",
                description=(
                    "Collect evidence artifacts for each standard "
                    "requirement: documents, review records, test results."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "iso_26262",
                },
                dependencies=["gap_analysis"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="assessment",
                description=(
                    "Assess compliance level per standard/requirement. "
                    "Generate compliance matrix with rating scale."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "iso_26262", "risk_assessment",
                },
                dependencies=["evidence_collection"],
                timeout_seconds=480,
            ),
            WorkflowStep(
                name="improvement_plan",
                description=(
                    "Generate prioritized improvement recommendations "
                    "with effort estimates and responsible parties."
                ),
                agent_type="safety_analyst",
                required_capabilities={
                    "iso_26262",
                },
                dependencies=["assessment"],
                timeout_seconds=300,
            ),
        ],
        expected_inputs=(
            "Project documentation, process evidence, work products, "
            "current compliance status"
        ),
        expected_outputs=(
            "Compliance matrix, gap analysis report, evidence catalog, "
            "assessment results, improvement roadmap"
        ),
        safety_standard_refs=[
            "ISO 26262-1:2018 through ISO 26262-12:2018",
            "ASPICE v3.1 / v4.0",
            "ISO 21434:2021",
            "ISO 21448:2022",
        ],
    )


# ===================================================================
# Workflow 8: Data Pipeline Review Workflow (数据管道审查工作流)
# ===================================================================

def create_data_pipeline_review_workflow() -> WorkflowDefinition:
    """
    Create the Data Pipeline Review workflow.

    Steps:
        1. pipeline_mapping      — Map data sources and transformations
        2. data_quality_check    — Analyze data quality metrics
        3. preprocessing_review  — Review preprocessing steps
        4. pipeline_performance  — Evaluate pipeline performance
        5. optimization_report   — Generate optimization recommendations

    Covers:
        - Data ingestion and validation
        - Data preprocessing for ML training
        - Annotation pipeline review
        - Data versioning and lineage
        - Storage efficiency
    """
    return WorkflowDefinition(
        id="data_pipeline_review",
        name="Data Pipeline Review Workflow (数据管道审查)",
        description=(
            "Review data processing pipelines for autonomous driving "
            "data, including ingestion, preprocessing, annotation, "
            "and storage. Identifies quality issues, performance "
            "bottlenecks, and optimization opportunities."
        ),
        version="1.0.0",
        domain_tags=["data", "ml", "pipeline", "quality"],
        steps=[
            WorkflowStep(
                name="pipeline_mapping",
                description=(
                    "Map data sources, transformations, and sinks. "
                    "Document data flow and lineage."
                ),
                agent_type="data_analyst",
                required_capabilities={
                    "data_processing",
                },
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="data_quality_check",
                description=(
                    "Analyze data quality metrics: completeness, "
                    "accuracy, consistency, timeliness, and validity."
                ),
                agent_type="data_analyst",
                required_capabilities={
                    "data_processing", "statistical_analysis",
                },
                dependencies=["pipeline_mapping"],
                timeout_seconds=600,
            ),
            WorkflowStep(
                name="preprocessing_review",
                description=(
                    "Review preprocessing steps: filtering, normalization, "
                    "augmentation, and labeling quality."
                ),
                agent_type="data_analyst",
                required_capabilities={
                    "data_processing", "statistical_analysis",
                },
                dependencies=["pipeline_mapping"],
                timeout_seconds=480,
            ),
            WorkflowStep(
                name="pipeline_performance",
                description=(
                    "Evaluate pipeline throughput, latency, resource "
                    "utilization, and scalability characteristics."
                ),
                agent_type="data_analyst",
                required_capabilities={
                    "data_processing", "performance_benchmarking",
                },
                dependencies=["data_quality_check", "preprocessing_review"],
                timeout_seconds=300,
            ),
            WorkflowStep(
                name="optimization_report",
                description=(
                    "Generate optimization recommendations for data "
                    "quality, throughput, and cost efficiency."
                ),
                agent_type="data_analyst",
                required_capabilities={
                    "data_processing", "reporting",
                },
                dependencies=["pipeline_performance"],
                timeout_seconds=180,
            ),
        ],
        expected_inputs=(
            "Pipeline configuration, data samples, quality metrics, "
            "performance data"
        ),
        expected_outputs=(
            "Pipeline map, data quality report, preprocessing assessment, "
            "performance analysis, optimization recommendations"
        ),
        safety_standard_refs=["ISO 26262-8:2018 (configuration)"],
    )


# ===================================================================
# Default Workflow Registration
# ===================================================================

def register_default_workflows(
    registry: Optional[WorkflowRegistry] = None,
) -> WorkflowRegistry:
    """
    Register all built-in workflows and return the registry.

    Args:
        registry: An existing registry to populate. If None, a new one
            is created.

    Returns:
        The populated WorkflowRegistry.
    """
    if registry is None:
        registry = WorkflowRegistry()

    factories: List[WorkflowFactory] = [
        create_code_review_workflow,
        create_safety_analysis_workflow,
        create_test_generation_workflow,
        create_bug_triage_workflow,
        create_architecture_review_workflow,
        create_scenario_generation_workflow,
        create_compliance_check_workflow,
        create_data_pipeline_review_workflow,
    ]

    for factory in factories:
        try:
            wf = factory()
            registry.register(wf)
        except Exception as exc:
            logger.error(
                "Failed to register workflow from %s: %s",
                factory.__name__,
                exc,
            )

    logger.info(
        "Registered %d default workflows",
        len(registry.list_workflows()),
    )
    return registry


# ===================================================================
# Convenience: Create all workflows with a single call
# ===================================================================

def create_workflow_registry() -> WorkflowRegistry:
    """
    Create and populate a WorkflowRegistry with all built-in workflows.

    This is the recommended entry point for most use cases.

    Returns:
        A WorkflowRegistry containing all 8 built-in workflows.
    """
    return register_default_workflows(WorkflowRegistry())
