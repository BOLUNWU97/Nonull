"""
Nonull - Multi-Agent Orchestration System (智驾智能体 - 多智能体编排系统)
================================================================================

Design Philosophy: OpenClaw's Nexus+Tendrils Pattern + Claude Code Subagent System + Hermes Agent Delegation

This package implements a production-grade multi-agent orchestration framework for
autonomous driving AI agent workflows. It provides:

  - **Nexus Orchestrator**: Central DAG-based task decomposition, agent assignment,
    parallel execution coordination, result aggregation, and conflict resolution.
  - **Agent Pool**: Dynamic agent registry with capability-based routing, load
    balancing, and lifecycle management.
  - **Predefined Workflows**: Domain-specific pipelines for ADAS code review,
    safety analysis, test generation, bug triage, architecture review, scenario
    generation, compliance checking, and data pipeline review.
  - **Communication Layer**: Pub/sub event bus, message-passing protocol, shared
    workspace, and agent-addressed routing.

Architecture Overview (架构概述)::

    +-------------------+       +-------------------+       +-------------------+
    |                   |       |                   |       |                   |
    |   Orchestrator    |<----->|    Agent Pool     |<----->| Agent Instances   |
    |   (Nexus)         |       |   (Tendrils)      |       | (Claude Subagents)|
    |                   |       |                   |       |                   |
    +--------+----------+       +-------------------+       +-------------------+
             |
             v
    +-------------------+       +-------------------+
    |   Workflows       |       |  Communication    |
    | (Domain Pipelines)|       |  (Event Bus/WS)   |
    +-------------------+       +-------------------+

References:
    - OpenClaw Nexus Pattern: Centralized orchestration with dynamic agent binding
    - Claude Code Subagent System: Hierarchical agent spawning with capability injection
    - Hermes Agent Delegation: Structured delegation with context propagation
    - ISO 26262 / ASPICE: Functional safety standards for automotive systems
"""

from __future__ import annotations

import logging
from typing import Any

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "1.0.0"
__author__ = "Nonull Team"
__license__ = "Proprietary - Nonull (智驾智能体)"

# ---------------------------------------------------------------------------
# Package-level logger
# ---------------------------------------------------------------------------
logger: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Convenience re-exports
# ---------------------------------------------------------------------------
from orchestration.orchestrator import (
    Orchestrator,
    OrchestrationPlan,
    Subtask,
    SubtaskStatus,
    ConflictRecord,
    ConflictSeverity,
    ExecutionResult,
    create_orchestrator,
)
from orchestration.agent_pool import (
    AgentPool,
    AgentRecord,
    AgentType,
    AgentStatus,
    CapabilityMap,
    create_agent_pool,
)
from orchestration.workflows import (
    WorkflowRegistry,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStatus,
    create_workflow_registry,
    register_default_workflows,
    # Concrete workflow factories
    create_code_review_workflow,
    create_safety_analysis_workflow,
    create_test_generation_workflow,
    create_bug_triage_workflow,
    create_architecture_review_workflow,
    create_scenario_generation_workflow,
    create_compliance_check_workflow,
    create_data_pipeline_review_workflow,
)
from orchestration.communication import (
    EventBus,
    Message,
    MessagePriority,
    MessageType,
    SharedWorkspace,
    AgentAddress,
    create_communication_layer,
)

__all__: list[str] = [
    # Core orchestrator
    "Orchestrator",
    "OrchestrationPlan",
    "Subtask",
    "SubtaskStatus",
    "ConflictRecord",
    "ConflictSeverity",
    "ExecutionResult",
    "create_orchestrator",
    # Agent pool
    "AgentPool",
    "AgentRecord",
    "AgentType",
    "AgentStatus",
    "CapabilityMap",
    "create_agent_pool",
    # Workflows
    "WorkflowRegistry",
    "WorkflowDefinition",
    "WorkflowStep",
    "WorkflowStatus",
    "create_workflow_registry",
    "register_default_workflows",
    "create_code_review_workflow",
    "create_safety_analysis_workflow",
    "create_test_generation_workflow",
    "create_bug_triage_workflow",
    "create_architecture_review_workflow",
    "create_scenario_generation_workflow",
    "create_compliance_check_workflow",
    "create_data_pipeline_review_workflow",
    # Communication
    "EventBus",
    "Message",
    "MessagePriority",
    "MessageType",
    "SharedWorkspace",
    "AgentAddress",
    "create_communication_layer",
]
