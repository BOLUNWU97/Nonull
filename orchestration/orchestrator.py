"""
ADVISORY SAFETY — The 'ISO 26262 / ASPICE Alignment' section below describes
PATTERNS for ASPICE-style logging and traceability. It does NOT claim ASPICE
process compliance, ISO 26262 process conformance, or certified functional
safety. The 'safety-rated escalation path' and 'audit trail reconstruction'
are ADVISORY traceability features, not certified safety mechanisms. See
README §Disclaimer and `safety.disclaimer: advisory_only` in config.

Orchestrator — Nexus Pattern Core (编排器 — Nexus 模式核心)
=============================================================

The central orchestrator implements the Nexus pattern from OpenClaw: a single
coordination point that decomposes complex tasks into a directed acyclic graph
(DAG) of subtasks, assigns each subtask to the most capable agent, manages
parallel execution, aggregates results, and resolves conflicts.

Key Concepts (关键概念):

  - **Task Decomposition**: A high-level user request is broken into granular,
    dependency-ordered subtasks via recursive refinement.
  - **DAG Management**: Subtasks form a DAG where edges represent
    data/control dependencies. The orchestrator topologically sorts and
    executes levels in parallel.
  - **Agent Assignment**: Each subtask is matched to an agent whose capability
    vector best covers the subtask's requirements (capability-based routing).
  - **Result Aggregation**: Partial results from multiple agents are merged
    into a unified output with conflict detection.
  - **Conflict Resolution**: When agents produce contradictory outputs, the
    orchestrator triggers a resolution protocol (vote, weighted confidence,
    or escalation).
  - **State Persistence (VINES-inspired)**: The full orchestration state —
    plan, status, intermediate results — can be serialized for checkpointing,
    replay, or audit.

Lifecycle (生命周期)::

    decompose_task(task) ──> assign_agent(subtask) ──> execute_plan(plan)
                                                                  │
                                                                  v
    get_status() <── aggregate_results(results) <── parallel execution
                             │
                             v
                  resolve_conflict(conflict) ──> final output

ASPICE-Style Logging Patterns (ASPICE 风格日志模式 — advisory only, NOT compliance):
    - The orchestrator logs every decision with a traceable ID (pattern reference, not ASPICE process conformance)
    - Conflict resolution follows an ADVISORY severity-keyed escalation path (vote/merge/escalate);
      this is a software convenience and is NOT a "safety-rated" mechanism in the ISO 26262 sense
    - State snapshots enable ADVISORY audit trail reconstruction for developer review;
      they are NOT a certified ASIL-D/ASIL-C audit log
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ===================================================================
# Data Types
# ===================================================================

class SubtaskStatus(str, enum.Enum):
    """Status of a subtask in the orchestration DAG."""

    PENDING = "pending"             # Created but not yet queued
    QUEUED = "queued"               # Waiting for dependency resolution
    RUNNING = "running"             # Assigned to an agent, in progress
    SUCCEEDED = "succeeded"         # Completed successfully
    FAILED = "failed"               # Execution error
    SKIPPED = "skipped"            # Skipped due to upstream failure
    BLOCKED = "blocked"            # Blocked by unresolved conflict


class ConflictSeverity(str, enum.Enum):
    """Severity rating for agent result conflicts."""

    LOW = "low"                     # Minor discrepancy, auto-merge possible
    MEDIUM = "medium"               # Notable divergence, needs review
    HIGH = "high"                   # Critical contradiction, blocks pipeline
    CRITICAL = "critical"           # Safety-relevant, requires human intervention


@dataclass
class Subtask:
    """
    A single unit of work within the orchestration DAG.

    Attributes:
        id: Unique identifier (UUID4).
        task_id: The top-level task this subtask belongs to.
        name: Human-readable name.
        description: Detailed description of the work.
        agent_type: Required agent type (capability category).
        required_capabilities: Set of capability strings needed.
        dependencies: List of subtask IDs that must complete first.
        status: Current execution status.
        result: Raw result payload from the agent.
        error: Error message if failed.
        metadata: Arbitrary key-value store for workflow-specific data.
        priority: Priority ranking (higher = more urgent).
        timeout_seconds: Maximum allowed execution time.
        created_at: Creation timestamp.
        started_at: Execution start timestamp.
        completed_at: Completion timestamp.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    task_id: str = ""
    name: str = ""
    description: str = ""
    agent_type: str = ""
    required_capabilities: Set[str] = field(default_factory=set)
    dependencies: List[str] = field(default_factory=list)
    status: SubtaskStatus = SubtaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout_seconds: int = 300
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        d = asdict(self)
        if isinstance(self.required_capabilities, set):
            d["required_capabilities"] = list(self.required_capabilities)
        if isinstance(self.dependencies, list):
            d["dependencies"] = list(self.dependencies)
        if isinstance(self.status, SubtaskStatus):
            d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subtask":
        """Deserialize from a dictionary."""
        if "status" in data and isinstance(data["status"], str):
            data["status"] = SubtaskStatus(data["status"])
        if "required_capabilities" in data:
            data["required_capabilities"] = set(data["required_capabilities"])
        return cls(**data)

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"Subtask(id={self.id[:8]}, name={self.name!r}, "
            f"status={self.status.value})"
        )


@dataclass
class ConflictRecord:
    """
    Records a conflict between agent results for resolution.

    Attributes:
        id: Unique conflict identifier.
        subtask_id: The subtask that produced conflicting results.
        task_id: The parent task ID.
        conflicting_results: Mapping from agent_id to their result.
        severity: How severe the conflict is.
        description: Human-readable description of the conflict.
        resolution: The chosen resolution strategy.
        resolved_result: The final merged/resolved value.
        resolved_at: When the conflict was resolved.
        resolved_by: Which strategy resolved it ("auto", "vote", "human", etc.).
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    subtask_id: str = ""
    task_id: str = ""
    conflicting_results: Dict[str, Any] = field(default_factory=dict)
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    description: str = ""
    resolution: Optional[str] = None
    resolved_result: Any = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


@dataclass
class ExecutionResult:
    """
    The aggregated outcome of executing an orchestration plan.

    Attributes:
        task_id: The original task identifier.
        status: Overall status ("succeeded", "failed", "partial").
        subtask_results: Mapping of subtask_id -> Subtask.
        conflicts: List of conflicts encountered.
        final_output: The unified, aggregated result.
        started_at: When execution began.
        completed_at: When execution finished.
        duration_ms: Wall-clock execution time in milliseconds.
        error: Overall error message if the plan failed entirely.
    """

    task_id: str = ""
    status: str = "pending"
    subtask_results: Dict[str, Subtask] = field(default_factory=dict)
    conflicts: List[ConflictRecord] = field(default_factory=list)
    final_output: Any = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class OrchestrationPlan:
    """
    A complete plan produced by task decomposition.

    The plan is a DAG of subtasks along with metadata for execution.

    Attributes:
        id: Unique plan identifier.
        task: The original high-level task description.
        subtasks: All subtasks indexed by id.
        root_subtask_ids: Subtask IDs with no dependencies (entry points).
        metadata: Plan-level metadata (workflow, version, tags).
        created_at: When the plan was created.
        version: Monotonic version number for plan revisions.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    task: str = ""
    subtasks: Dict[str, Subtask] = field(default_factory=dict)
    root_subtask_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    version: int = 1

    def topological_order(self) -> List[List[str]]:
        """
        Compute a topological ordering of subtasks grouped by dependency level.

        Returns a list of *levels*, where each level is a list of subtask IDs
        that can be executed in parallel. Level 0 has no dependencies.
        """
        in_degree: Dict[str, int] = {}
        adj: Dict[str, List[str]] = defaultdict(list)

        all_ids = set(self.subtasks.keys())
        for sid, st in self.subtasks.items():
            in_degree.setdefault(sid, 0)
            for dep_id in st.dependencies:
                if dep_id in all_ids:
                    adj.setdefault(dep_id, []).append(sid)
                    in_degree[sid] = in_degree.get(sid, 0) + 1

        # Kahn's algorithm with levels
        levels: List[List[str]] = []
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])

        while queue:
            current_level: List[str] = []
            for _ in range(len(queue)):
                sid = queue.popleft()
                current_level.append(sid)
                for neighbour in adj.get(sid, []):
                    in_degree[neighbour] -= 1
                    if in_degree[neighbour] == 0:
                        queue.append(neighbour)
            levels.append(current_level)

        # If some nodes are unreachable (cycle), include them as a final level
        remaining = [sid for sid, deg in in_degree.items() if deg > 0]
        if remaining:
            logger.warning(
                "Cycle detected in plan %s; %d subtasks unreachable",
                self.id[:8],
                len(remaining),
            )
            levels.append(remaining)

        return levels

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire plan to a dictionary."""
        return {
            "id": self.id,
            "task": self.task,
            "version": self.version,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "root_subtask_ids": list(self.root_subtask_ids),
            "subtasks": {
                sid: st.to_dict() for sid, st in self.subtasks.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationPlan":
        """Deserialize a plan from a dictionary."""
        if "subtasks" in data:
            data["subtasks"] = {
                sid: Subtask.from_dict(std)
                for sid, std in data["subtasks"].items()
            }
        return cls(**data)


# ===================================================================
# Decomposition Strategies
# ===================================================================

DecompositionFn = Callable[[str, Dict[str, Any]], OrchestrationPlan]
"""
Signature for a task decomposition function.

Args:
    task: The high-level task description.
    context: Additional context (workflow type, domain, constraints).

Returns:
    An OrchestrationPlan with subtasks and dependency edges.
"""


class DecompositionStrategy:
    """
    Registry of decomposition strategies for different task types.

    Strategies are registered by domain key (e.g., "code_review", "safety").
    The orchestrator selects the appropriate strategy based on the task
    or workflow type.
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, DecompositionFn] = {}

    def register(self, key: str, fn: DecompositionFn) -> None:
        """Register a decomposition function for a domain key."""
        if key in self._strategies:
            logger.warning("Overwriting decomposition strategy for key=%s", key)
        self._strategies[key] = fn
        logger.debug("Registered decomposition strategy: %s", key)

    def get(self, key: str) -> DecompositionFn:
        """Retrieve a decomposition function, raising KeyError if missing."""
        if key not in self._strategies:
            raise KeyError(
                f"No decomposition strategy registered for key={key!r}. "
                f"Available: {list(self._strategies)}"
            )
        return self._strategies[key]

    def decompose(
        self, key: str, task: str, context: Optional[Dict[str, Any]] = None
    ) -> OrchestrationPlan:
        """Decompose *task* using the strategy registered under *key*."""
        fn = self.get(key)
        return fn(task, context or {})

    def available_keys(self) -> List[str]:
        """Return all registered strategy keys."""
        return list(self._strategies)


# ===================================================================
# Default Decomposition Strategy (通用分解策略)
# ===================================================================

def _default_decomposition_fn(
    task: str, context: Dict[str, Any]
) -> OrchestrationPlan:
    """
    Generic task decomposition.

    Breaks any task into four phases:
        1. Analysis   — understand the problem
        2. Execution  — perform the core work
        3. Validation — verify correctness
        4. Reporting  — produce the final output

    This is overridden by domain-specific strategies in practice.
    """
    plan = OrchestrationPlan(
        task=task,
        metadata=context,
    )

    # Phase 1: Analysis
    analysis = Subtask(
        task_id=plan.id,
        name="analysis",
        description=f"Analyze the task: {task[:120]}",
        agent_type="analyst",
        required_capabilities={"analysis", "reasoning"},
        priority=10,
        dependencies=[],
    )
    plan.subtasks[analysis.id] = analysis

    # Phase 2: Execution
    execution = Subtask(
        task_id=plan.id,
        name="execution",
        description=f"Execute the core work for: {task[:120]}",
        agent_type="executor",
        required_capabilities={"execution", context.get("domain", "general")},
        priority=5,
        dependencies=[analysis.id],
    )
    plan.subtasks[execution.id] = execution

    # Phase 3: Validation
    validation = Subtask(
        task_id=plan.id,
        name="validation",
        description="Validate the execution result",
        agent_type="reviewer",
        required_capabilities={"validation", "quality_assurance"},
        priority=3,
        dependencies=[execution.id],
    )
    plan.subtasks[validation.id] = validation

    # Phase 4: Reporting
    reporting = Subtask(
        task_id=plan.id,
        name="reporting",
        description="Produce the final report and summary",
        agent_type="reporter",
        required_capabilities={"reporting", "summarization"},
        priority=1,
        dependencies=[validation.id],
    )
    plan.subtasks[reporting.id] = reporting

    plan.root_subtask_ids = [analysis.id]
    logger.info(
        "Default decomposition created plan %s with %d subtasks",
        plan.id[:8],
        len(plan.subtasks),
    )
    return plan


# ===================================================================
# Orchestrator (Nexus Core)
# ===================================================================

class Orchestrator:
    """
    Central orchestrator implementing the Nexus pattern.

    The Orchestrator is the single coordination point for all multi-agent
    activity. It manages the full lifecycle of a task from decomposition
    through execution, aggregation, and conflict resolution.

    Thread Safety:
        All public methods are thread-safe. Internal state is protected by
        a reentrant lock.

    Usage::

        orchestrator = Orchestrator()
        orchestrator.register_decomposition_strategy("default", my_fn)

        # Decompose and execute synchronously
        plan = orchestrator.decompose_task("Review ADAS module X")
        result = orchestrator.execute_plan(plan)

        # Or step-by-step
        plan = orchestrator.decompose_task("Generate test cases")
        for level in plan.topological_order():
            for sid in level:
                orchestrator.assign_agent(plan.subtasks[sid], agent_pool)
            # ... execute level ...

        orchestrator.aggregate_results(result)
        orchestrator.resolve_conflict(conflict)
    """

    def __init__(
        self,
        plan_store_path: Optional[str] = None,
        max_parallel_agents: int = 8,
        conflict_strategies: Optional[Dict[str, Callable]] = None,
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            plan_store_path: Optional path for persisting plans as JSON files.
                If None, plans are kept in memory only.
            max_parallel_agents: Maximum number of agents to execute concurrently.
            conflict_strategies: Custom conflict resolution strategies mapped
                by severity name. If None, built-in strategies are used.
        """
        self._lock = threading.RLock()
        self._plan_store_path = plan_store_path
        self._max_parallel_agents = max_parallel_agents

        # Decomposition
        self._decomposition = DecompositionStrategy()
        self._decomposition.register("default", _default_decomposition_fn)

        # Active plans and execution state
        self._plans: Dict[str, OrchestrationPlan] = {}
        self._execution_results: Dict[str, ExecutionResult] = {}
        self._conflicts: Dict[str, ConflictRecord] = {}

        # Agent assignment callback (set by AgentPool binding)
        self._assignment_fn: Optional[Callable[[Subtask, Any], str]] = None

        # Conflict resolution strategies
        self._conflict_strategies: Dict[str, Callable] = (
            conflict_strategies or self._default_conflict_strategies()
        )

        # Execution hooks
        self._pre_execution_hooks: List[Callable] = []
        self._post_execution_hooks: List[Callable] = []

        logger.info(
            "Orchestrator initialized (max_parallel=%d, store_path=%s)",
            max_parallel_agents,
            plan_store_path or "(memory only)",
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_decomposition_strategy(
        self, key: str, fn: DecompositionFn
    ) -> None:
        """Register a custom decomposition strategy."""
        with self._lock:
            self._decomposition.register(key, fn)
            logger.info("Decomposition strategy registered: %s", key)

    def register_assignment_fn(
        self, fn: Callable[[Subtask, Any], str]
    ) -> None:
        """
        Register the agent assignment function.

        This is typically bound to ``AgentPool.assign_agent()``.
        The function receives a Subtask and a context object, and returns
        an agent ID string.
        """
        with self._lock:
            self._assignment_fn = fn
            logger.debug("Assignment function registered")

    def register_pre_execution_hook(self, hook: Callable) -> None:
        """Register a hook called before each subtask executes."""
        with self._lock:
            self._pre_execution_hooks.append(hook)

    def register_post_execution_hook(self, hook: Callable) -> None:
        """Register a hook called after each subtask completes."""
        with self._lock:
            self._post_execution_hooks.append(hook)

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def decompose_task(
        self,
        task: str,
        strategy_key: str = "default",
        context: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> OrchestrationPlan:
        """
        Decompose a high-level task into a DAG of subtasks.

        Args:
            task: The high-level task description.
            strategy_key: Which decomposition strategy to use.
            context: Additional context passed to the decomposition function.
            persist: If True, the plan is stored in memory and optionally
                persisted to disk.

        Returns:
            An OrchestrationPlan populated with subtasks and dependency edges.

        Raises:
            KeyError: If no strategy is registered for *strategy_key*.
        """
        with self._lock:
            ctx = {"timestamp": datetime.now(timezone.utc).isoformat()}
            if context:
                ctx.update(context)

            plan = self._decomposition.decompose(strategy_key, task, ctx)

            # Assign task_id to subtasks that don't have one
            for sid, st in plan.subtasks.items():
                if not st.task_id:
                    st.task_id = plan.id
                if not st.id:
                    st.id = sid

            # Recompute root subtask IDs
            all_deps: Set[str] = set()
            for st in plan.subtasks.values():
                all_deps.update(st.dependencies)
            plan.root_subtask_ids = [
                sid
                for sid in plan.subtasks
                if sid not in all_deps
            ]

            self._plans[plan.id] = plan

            if persist and self._plan_store_path:
                self._persist_plan(plan)

            logger.info(
                "Task decomposed: plan=%s, subtasks=%d, levels=%d",
                plan.id[:8],
                len(plan.subtasks),
                len(plan.topological_order()),
            )
            return plan

    def assign_agent(
        self,
        subtask: Subtask,
        agent_pool_context: Any,
    ) -> Optional[str]:
        """
        Assign a subtask to an agent based on capability matching.

        Uses the registered assignment function or falls back to a simple
        capability-based lookup.

        Args:
            subtask: The subtask needing an agent.
            agent_pool_context: The AgentPool (or compatible object) with
                a ``select_agent(capabilities)`` method.

        Returns:
            Agent ID string, or None if no suitable agent is available.
        """
        with self._lock:
            if self._assignment_fn:
                try:
                    agent_id = self._assignment_fn(subtask, agent_pool_context)
                    logger.debug(
                        "Subtask %s assigned to agent %s",
                        subtask.id[:8],
                        agent_id,
                    )
                    return agent_id
                except Exception as exc:
                    logger.error(
                        "Assignment function failed for subtask %s: %s",
                        subtask.id[:8],
                        exc,
                    )
                    return None

            # Default fallback: query agent pool
            if hasattr(agent_pool_context, "select_agent"):
                try:
                    agent_id = agent_pool_context.select_agent(
                        subtask.required_capabilities,
                        preferred_type=subtask.agent_type,
                    )
                    return agent_id
                except Exception as exc:
                    logger.error(
                        "Fallback assignment failed: %s", exc
                    )
                    return None

            logger.warning(
                "No assignment function and no compatible agent_pool_context"
            )
            return None

    def execute_plan(
        self,
        plan: OrchestrationPlan,
        agent_pool_context: Any = None,
        executor_fn: Optional[Callable[[Subtask, str], Any]] = None,
    ) -> ExecutionResult:
        """
        Execute an orchestration plan end-to-end.

        This method:
          1. Topologically sorts the DAG into dependency levels
          2. Assigns agents for each subtask (using agent_pool_context)
          3. Executes each level in parallel (up to max_parallel_agents)
          4. Waits for all subtasks in a level before proceeding
          5. Detects and records conflicts
          6. Aggregates results into a unified output

        Args:
            plan: The plan to execute.
            agent_pool_context: Object providing agent selection/execution.
            executor_fn: Callable that actually runs a subtask on an agent.
                Signature: ``fn(subtask, agent_id) -> Any``.
                If None, the orchestrator uses a default no-op executor
                that simply records the assignment.

        Returns:
            An ExecutionResult summarizing the outcome.
        """
        result = ExecutionResult(
            task_id=plan.id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            execution_start = time.monotonic()
            levels = plan.topological_order()

            logger.info(
                "Executing plan %s (%d levels, %d subtasks)",
                plan.id[:8],
                len(levels),
                len(plan.subtasks),
            )

            for level_idx, level_sids in enumerate(levels):
                logger.debug(
                    "Executing level %d/%d (%d subtasks)",
                    level_idx + 1,
                    len(levels),
                    len(level_sids),
                )

                # Assign and execute level subtasks in parallel
                level_results: Dict[str, Any] = {}

                for sid in level_sids:
                    subtask = plan.subtasks.get(sid)
                    if subtask is None:
                        logger.warning("Subtask %s not found in plan", sid)
                        continue

                    # Skip if dependency failed
                    if self._dependency_failed(subtask, plan):
                        subtask.status = SubtaskStatus.SKIPPED
                        logger.info("Subtask %s skipped (dependency failed)", sid)
                        result.subtask_results[sid] = subtask
                        continue

                    # Assign agent
                    agent_id = None
                    if agent_pool_context is not None:
                        agent_id = self.assign_agent(subtask, agent_pool_context)

                    if agent_id is None:
                        subtask.status = SubtaskStatus.FAILED
                        subtask.error = "No available agent for assignment"
                        logger.error(
                            "No agent available for subtask %s", sid
                        )
                        result.subtask_results[sid] = subtask
                        continue

                    subtask.status = SubtaskStatus.RUNNING
                    subtask.started_at = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    self._run_hooks(
                        "pre", subtask, plan, agent_id
                    )

                    # Execute
                    try:
                        if executor_fn:
                            subtask_result = executor_fn(subtask, agent_id)
                        else:
                            # Default: record assignment as "success"
                            subtask_result = {
                                "assigned_to": agent_id,
                                "status": "simulated_success",
                                "message": (
                                    f"Subtask '{subtask.name}' "
                                    f"assigned to agent {agent_id}"
                                ),
                            }

                        subtask.status = SubtaskStatus.SUCCEEDED
                        subtask.result = subtask_result
                        subtask.completed_at = (
                            datetime.now(timezone.utc).isoformat()
                        )
                        level_results[sid] = subtask_result

                        logger.debug(
                            "Subtask %s completed successfully",
                            sid[:8],
                        )

                    except Exception as exc:
                        subtask.status = SubtaskStatus.FAILED
                        subtask.error = str(exc)
                        subtask.completed_at = (
                            datetime.now(timezone.utc).isoformat()
                        )
                        logger.error(
                            "Subtask %s failed: %s", sid[:8], exc
                        )

                    finally:
                        self._run_hooks(
                            "post", subtask, plan, agent_id
                        )
                        result.subtask_results[sid] = subtask

                # After each level, check for conflicts among concurrent results
                if len(level_results) > 1:
                    self._detect_level_conflicts(
                        level_results, level_sids, plan, result
                    )

            # Aggregate all results
            result.final_output = self.aggregate_results(result)

            # Final status
            succeeded_count = sum(
                1 for s in result.subtask_results.values()
                if s.status == SubtaskStatus.SUCCEEDED
            )
            failed_count = sum(
                1 for s in result.subtask_results.values()
                if s.status == SubtaskStatus.FAILED
            )
            total = len(result.subtask_results)

            if failed_count == 0:
                result.status = "succeeded"
            elif succeeded_count > 0:
                result.status = "partial"
            else:
                result.status = "failed"

            result.completed_at = (
                datetime.now(timezone.utc).isoformat()
            )
            result.duration_ms = (
                time.monotonic() - execution_start
            ) * 1000.0

            logger.info(
                "Plan %s execution %s (%d/%d succeeded, %d failed, %.0fms)",
                plan.id[:8],
                result.status,
                succeeded_count,
                total,
                failed_count,
                result.duration_ms,
            )

        except Exception as exc:
            result.status = "failed"
            result.error = str(exc)
            result.completed_at = (
                datetime.now(timezone.utc).isoformat()
            )
            logger.exception(
                "Plan %s execution failed with exception", plan.id[:8]
            )

        self._execution_results[plan.id] = result
        return result

    def aggregate_results(
        self, result: ExecutionResult
    ) -> Dict[str, Any]:
        """
        Aggregate individual subtask results into a unified output.

        The default aggregation:
          - Collects all succeeded subtask results
          - Groups them by subtask name (for deduplication)
          - Merges them into a single dictionary keyed by subtask ID

        Override or extend by registering aggregation strategies.

        Args:
            result: The execution result containing subtask results.

        Returns:
            A unified aggregated result dictionary.
        """
        aggregated: Dict[str, Any] = {
            "task_id": result.task_id,
            "status": result.status,
            "summary": {
                "total": len(result.subtask_results),
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
            },
            "outputs": {},
        }

        for sid, subtask in result.subtask_results.items():
            if subtask.status == SubtaskStatus.SUCCEEDED:
                aggregated["summary"]["succeeded"] += 1
                aggregated["outputs"][subtask.name] = subtask.result
            elif subtask.status == SubtaskStatus.FAILED:
                aggregated["summary"]["failed"] += 1
                aggregated["outputs"][f"{subtask.name}.error"] = subtask.error
            elif subtask.status == SubtaskStatus.SKIPPED:
                aggregated["summary"]["skipped"] += 1

        return aggregated

    def resolve_conflict(
        self,
        conflict: ConflictRecord,
        strategy: Optional[str] = None,
    ) -> Any:
        """
        Resolve a conflict between agent results.

        Strategies (built-in):
          - ``"latest"``: Pick the most recent result
          - ``"majority"``: Majority vote (if 3+ agents)
          - ``"highest_confidence"``: Pick result with highest confidence score
          - ``"merge"``: Deep-merge dictionaries/JSON objects
          - ``"escalate"``: Mark as requiring human intervention

        Args:
            conflict: The conflict record to resolve.
            strategy: Which resolution strategy to apply. If None, it is
                chosen based on conflict severity.

        Returns:
            The resolved result value.
        """
        if strategy is None:
            strategy = self._strategy_for_severity(conflict.severity)

        resolver = self._conflict_strategies.get(strategy)
        if resolver is None:
            logger.warning(
                "Unknown conflict strategy %r, falling back to 'latest'",
                strategy,
            )
            resolver = self._conflict_strategies["latest"]

        try:
            resolved = resolver(conflict)
            conflict.resolved_result = resolved
            conflict.resolved_at = (
                datetime.now(timezone.utc).isoformat()
            )
            conflict.resolved_by = strategy
            conflict.resolution = strategy
            self._conflicts[conflict.id] = conflict

            sev = (
                conflict.severity.value
                if isinstance(conflict.severity, ConflictSeverity)
                else str(conflict.severity)
            )
            logger.info(
                "Conflict %s resolved via %s (severity=%s)",
                conflict.id[:8],
                strategy,
                sev,
            )
            return resolved

        except Exception as exc:
            logger.exception(
                "Conflict resolution failed for %s: %s",
                conflict.id[:8],
                exc,
            )
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        Return a snapshot of the current orchestration state.

        Returns:
            Dictionary with active plan counts, execution summaries,
            and conflict counts.
        """
        with self._lock:
            active_count = sum(
                1 for p in self._plans.values()
                if any(
                    st.status in (SubtaskStatus.PENDING, SubtaskStatus.RUNNING)
                    for st in p.subtasks.values()
                )
            )
            completed_count = len(self._execution_results)
            conflict_count = len(self._conflicts)

            return {
                "total_plans": len(self._plans),
                "active_plans": active_count,
                "completed_executions": completed_count,
                "total_conflicts": conflict_count,
                "unresolved_conflicts": sum(
                    1 for c in self._conflicts.values()
                    if c.resolved_at is None
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_execution_graph(self, plan_id: str) -> Dict[str, Any]:
        """
        Return a DAG visualization-friendly structure for a plan.

        The output includes nodes and edges in a format suitable for
        rendering with libraries like Graphviz, Mermaid.js, or D3.

        Args:
            plan_id: The plan identifier.

        Returns:
            Dictionary with ``nodes`` and ``edges`` lists, plus metadata.
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                raise KeyError(f"Plan {plan_id} not found")

            nodes: List[Dict[str, Any]] = []
            edges: List[Dict[str, Any]] = []

            for sid, st in plan.subtasks.items():
                node = {
                    "id": sid,
                    "label": st.name,
                    "status": st.status.value,
                    "agent_type": st.agent_type,
                    "priority": st.priority,
                }
                nodes.append(node)

                for dep_id in st.dependencies:
                    if dep_id in plan.subtasks:
                        edges.append({
                            "from": dep_id,
                            "to": sid,
                        })

            return {
                "plan_id": plan_id,
                "task": plan.task,
                "nodes": nodes,
                "edges": edges,
                "levels": [
                    {"level": i, "subtask_ids": level}
                    for i, level in enumerate(plan.topological_order())
                ],
            }

    # ------------------------------------------------------------------
    # Plan Persistence (VINES-inspired)
    # ------------------------------------------------------------------

    def save_plan(self, plan_id: str, path: Optional[str] = None) -> str:
        """
        Persist a plan to a JSON file for checkpoint/audit.

        Args:
            plan_id: The plan to persist.
            path: File path. If None, uses ``plan_store_path / {plan_id}.json``.

        Returns:
            The path the plan was saved to.

        Raises:
            KeyError: If the plan does not exist.
            IOError: If the file cannot be written.
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                raise KeyError(f"Plan {plan_id} not found")

            if path is None:
                store = self._plan_store_path or "."
                os.makedirs(store, exist_ok=True)
                path = os.path.join(store, f"{plan_id}.json")

            data = plan.to_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            checksum = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()

            logger.info(
                "Plan %s persisted to %s (sha256=%s)",
                plan_id[:8],
                path,
                checksum[:16],
            )
            return path

    def load_plan(self, path: str) -> OrchestrationPlan:
        """
        Load a plan from a JSON file.

        Args:
            path: Path to the serialized plan.

        Returns:
            The deserialized OrchestrationPlan.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        plan = OrchestrationPlan.from_dict(data)
        with self._lock:
            self._plans[plan.id] = plan
        logger.info(
            "Plan %s loaded from %s", plan.id[:8], path
        )
        return plan

    def save_state(self, path: str) -> str:
        """
        Persist the entire orchestrator state (all plans + results).

        This provides a full checkpoint for recovery or audit trail.

        Args:
            path: Directory to save state files into.

        Returns:
            The path to the state manifest.
        """
        with self._lock:
            os.makedirs(path, exist_ok=True)
            manifest: Dict[str, Any] = {
                "version": __import__("orchestration").__version__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "plan_count": len(self._plans),
                "result_count": len(self._execution_results),
                "conflict_count": len(self._conflicts),
                "plan_files": [],
                "result_files": [],
            }

            for plan_id, plan in self._plans.items():
                plan_path = os.path.join(path, f"plan_{plan_id}.json")
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
                manifest["plan_files"].append(plan_path)

            for result_id, result in self._execution_results.items():
                rpath = os.path.join(path, f"result_{result_id}.json")
                with open(rpath, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "task_id": result.task_id,
                            "status": result.status,
                            "final_output": result.final_output,
                            "duration_ms": result.duration_ms,
                            "error": result.error,
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )
                manifest["result_files"].append(rpath)

            manifest_path = os.path.join(path, "orchestrator_state.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            logger.info(
                "Orchestrator state saved to %s (%d plans, %d results)",
                path,
                len(self._plans),
                len(self._execution_results),
            )
            return manifest_path

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _dependency_failed(self, subtask: Subtask, plan: OrchestrationPlan) -> bool:
        """Check if any dependency of *subtask* has failed or been skipped."""
        for dep_id in subtask.dependencies:
            dep = plan.subtasks.get(dep_id)
            if dep and dep.status in (
                SubtaskStatus.FAILED,
                SubtaskStatus.SKIPPED,
            ):
                return True
        return False

    def _run_hooks(
        self,
        phase: str,
        subtask: Subtask,
        plan: OrchestrationPlan,
        agent_id: str,
    ) -> None:
        """Run registered hooks for the given phase."""
        hooks = (
            self._pre_execution_hooks
            if phase == "pre"
            else self._post_execution_hooks
        )
        for hook in hooks:
            try:
                hook(subtask, plan, agent_id)
            except Exception as exc:
                logger.warning(
                    "Hook %s failed for subtask %s: %s",
                    hook.__name__,
                    subtask.id[:8],
                    exc,
                )

    def _detect_level_conflicts(
        self,
        level_results: Dict[str, Any],
        level_sids: List[str],
        plan: OrchestrationPlan,
        result: ExecutionResult,
    ) -> None:
        """
        Detect conflicts among results within the same dependency level.

        A conflict is flagged when two subtasks in the same level produce
        results that contradict each other on the same output key.
        """
        # Group results by subtask name for comparison
        name_groups: Dict[str, List[tuple[str, Any]]] = defaultdict(list)
        for sid in level_sids:
            st = plan.subtasks.get(sid)
            if st and st.status == SubtaskStatus.SUCCEEDED:
                name_groups[st.name].append((sid, st.result))

        for name, entries in name_groups.items():
            if len(entries) < 2:
                continue

            # Simple conflict detection: different values on same keys
            all_keys: Set[str] = set()
            for _, res in entries:
                if isinstance(res, dict):
                    all_keys.update(res.keys())

            for key in all_keys:
                values = {}
                for sid, res in entries:
                    if isinstance(res, dict) and key in res:
                        values[sid] = res[key]

                if len(values) >= 2:
                    unique_vals = set(
                        json.dumps(v, sort_keys=True)
                        for v in values.values()
                    )
                    if len(unique_vals) > 1:
                        conflict = ConflictRecord(
                            subtask_id=", ".join(values.keys()),
                            task_id=plan.id,
                            conflicting_results=values,
                            severity=ConflictSeverity.MEDIUM,
                            description=(
                                f"Conflicting values for key '{key}' "
                                f"across subtasks named '{name}'"
                            ),
                        )
                        result.conflicts.append(conflict)
                        logger.info(
                            "Conflict detected: %s on key=%s "
                            "across %d subtasks",
                            conflict.id[:8],
                            key,
                            len(values),
                        )

    def _persist_plan(self, plan: OrchestrationPlan) -> None:
        """Persist a plan to the store path."""
        try:
            self.save_plan(plan.id)
        except Exception as exc:
            logger.warning("Failed to persist plan %s: %s", plan.id[:8], exc)

    @staticmethod
    def _default_conflict_strategies() -> Dict[str, Callable]:
        """Return the built-in conflict resolution strategies."""

        def _latest(conflict: ConflictRecord) -> Any:
            """Pick the last result in the dict (arbitrary insertion order in 3.7+)."""
            return list(conflict.conflicting_results.values())[-1]

        def _majority(conflict: ConflictRecord) -> Any:
            """Return the value that appears most frequently."""
            from collections import Counter
            serialized = [
                json.dumps(v, sort_keys=True)
                for v in conflict.conflicting_results.values()
            ]
            counter = Counter(serialized)
            most_common = counter.most_common(1)[0][0]
            return json.loads(most_common)

        def _highest_confidence(conflict: ConflictRecord) -> Any:
            """Return the result with the highest 'confidence' field."""
            best_val = None
            best_conf = -1.0
            for val in conflict.conflicting_results.values():
                if isinstance(val, dict):
                    conf = val.get("confidence", 0.0)
                    if isinstance(conf, (int, float)) and conf > best_conf:
                        best_conf = conf
                        best_val = val
            return best_val or list(conflict.conflicting_results.values())[0]

        def _merge(conflict: ConflictRecord) -> Dict[str, Any]:
            """Deep-merge all dictionary results."""
            merged: Dict[str, Any] = {}
            for val in conflict.conflicting_results.values():
                if isinstance(val, dict):
                    merged.update(val)
            return merged

        def _escalate(conflict: ConflictRecord) -> Dict[str, Any]:
            """Mark conflict as needing human intervention."""
            conflict.severity = ConflictSeverity.CRITICAL
            logger.warning(
                "Conflict %s escalated to human review: %s",
                conflict.id[:8],
                conflict.description,
            )
            return {
                "status": "escalated",
                "conflict_id": conflict.id,
                "message": "Requires human intervention",
            }

        return {
            "latest": _latest,
            "majority": _majority,
            "highest_confidence": _highest_confidence,
            "merge": _merge,
            "escalate": _escalate,
        }

    def _strategy_for_severity(self, severity: ConflictSeverity) -> str:
        """Map a severity level to a default resolution strategy."""
        mapping = {
            ConflictSeverity.LOW: "latest",
            ConflictSeverity.MEDIUM: "merge",
            ConflictSeverity.HIGH: "majority",
            ConflictSeverity.CRITICAL: "escalate",
        }
        return mapping.get(severity, "latest")


# ===================================================================
# Convenience Factory
# ===================================================================

def create_orchestrator(
    plan_store_path: Optional[str] = None,
    max_parallel_agents: int = 8,
    register_default_strategies: bool = True,
) -> Orchestrator:
    """
    Convenience factory for creating a pre-configured Orchestrator.

    Args:
        plan_store_path: Path for plan persistence.
        max_parallel_agents: Max concurrent agents.
        register_default_strategies: If True, registers the default
            decomposition strategy.

    Returns:
        A ready-to-use Orchestrator instance.
    """
    orch = Orchestrator(
        plan_store_path=plan_store_path,
        max_parallel_agents=max_parallel_agents,
    )

    if register_default_strategies:
        orch.register_decomposition_strategy("default", _default_decomposition_fn)

    logger.info(
        "Orchestrator factory created instance (store=%s, parallel=%d)",
        plan_store_path,
        max_parallel_agents,
    )
    return orch
