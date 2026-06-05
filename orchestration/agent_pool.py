"""
Agent Pool — Tendrils Pattern Core (代理池 — Tendrils 模式核心)
================================================================

The Agent Pool implements the Tendrils pattern from OpenClaw: a dynamic,
capability-indexed registry of agent instances that can be spawned, tracked,
load-balanced, and terminated on demand.

Each agent in the pool is a "tendril" — a lightweight, focused worker with a
well-defined capability set. The pool manages:

  - **Capability Registry**: Every agent declares its capabilities. The pool
    provides O(1) lookup of agents by capability vector.
  - **Dynamic Spawning**: Agents can be created on demand (mapping to Claude
    Code subagent spawning or Hermes Agent delegation).
  - **Load Balancing**: Incoming subtasks are distributed across eligible
    agents using configurable strategies (round-robin, least-loaded, random).
  - **Lifecycle Management**: Agents transition through a defined state
    machine: ``idle -> busy -> draining -> terminated``.
  - **Communication Channels**: Each agent is reachable via a virtual
    communication channel (backed by the EventBus).

Agent Types (代理类型)::

    +------------------+--------------------------------------------------+
    | Agent Type       | Domain                                           |
    +------------------+--------------------------------------------------+
    | Orchestrator     | Task decomposition, coordination, aggregation     |
    | CodeReviewer     | C++/Python ADAS code review, static analysis      |
    | SafetyAnalyst    | HARA, FMEA, FTA, safety case generation           |
    | TestEngineer     | SIL/HIL test case generation, coverage analysis   |
    | DataAnalyst      | Log analysis, performance metrics, anomaly detect |
    | ResearchAgent    | Literature survey, algorithm research, prototyping|
    | DevOpsAgent      | CI/CD pipeline, deployment, container management  |
    +------------------+--------------------------------------------------+

ISO 26262 / ASPICE Alignment:
    - Agent capability declarations include safety integrity levels (ASIL)
    - The pool maintains an audit log of all agent assignments
    - Draining ensures in-flight safety tasks are not interrupted abruptly
"""

from __future__ import annotations

import enum
import logging
import random
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ===================================================================
# Enums & Constants
# ===================================================================

class AgentType(str, enum.Enum):
    """
    Categorization of agent roles within the orchestration system.

    Each agent type maps to a domain expertise area in the autonomous
    driving software development lifecycle.
    """

    ORCHESTRATOR = "orchestrator"           # 编排器
    CODE_REVIEWER = "code_reviewer"         # 代码审查员
    SAFETY_ANALYST = "safety_analyst"       # 安全分析师
    TEST_ENGINEER = "test_engineer"         # 测试工程师
    DATA_ANALYST = "data_analyst"           # 数据分析师
    RESEARCH_AGENT = "research_agent"       # 研究代理
    DEVOPS_AGENT = "devops_agent"           # DevOps 代理


class AgentStatus(str, enum.Enum):
    """
    Lifecycle states for an agent in the pool.

    .. code-block::

        idle ──> busy ──> draining ──> terminated
          ^        |
          +--------+
    """

    IDLE = "idle"                       # Ready to accept work
    BUSY = "busy"                       # Currently executing a task
    DRAINING = "draining"              # Finishing current task, no new tasks
    TERMINATED = "terminated"          # Removed from pool


class LoadBalanceStrategy(str, enum.Enum):
    """Strategies for distributing work across available agents."""

    ROUND_ROBIN = "round_robin"         # Cyclic assignment (循环分配)
    LEAST_LOADED = "least_loaded"       # Pick agent with fewest active tasks (最少负载)
    RANDOM = "random"                   # Uniform random selection (随机选择)
    CAPABILITY_WEIGHTED = "capability_weighted"  # Weighted by capability match score


# Default capability definitions per agent type
DEFAULT_CAPABILITIES: Dict[AgentType, Set[str]] = {
    AgentType.ORCHESTRATOR: {
        "task_decomposition", "dag_management", "result_aggregation",
        "conflict_resolution", "planning", "coordination",
    },
    AgentType.CODE_REVIEWER: {
        "c++_review", "python_review", "static_analysis",
        "coding_standards", "misra_check", "autosar_check",
        "performance_analysis", "security_review",
    },
    AgentType.SAFETY_ANALYST: {
        "hara", "fmea", "fta", "safety_case", "risk_assessment",
        "iso_26262", "asil_determination", "safety_goal_definition",
    },
    AgentType.TEST_ENGINEER: {
        "test_case_generation", "sil_testing", "hil_testing",
        "coverage_analysis", "regression_testing", "scenario_testing",
        "mutation_testing", "requirement_based_testing",
    },
    AgentType.DATA_ANALYST: {
        "data_processing", "log_analysis", "anomaly_detection",
        "statistical_analysis", "visualization", "metric_computation",
        "time_series_analysis", "performance_benchmarking",
    },
    AgentType.RESEARCH_AGENT: {
        "literature_review", "algorithm_survey", "prototyping",
        "experiment_design", "paper_analysis", "state_of_art_review",
        "novelty_assessment", "comparative_analysis",
    },
    AgentType.DEVOPS_AGENT: {
        "ci_cd_pipeline", "containerization", "infrastructure_as_code",
        "deployment_automation", "monitoring", "release_management",
        "environment_provisioning", "artifact_management",
    },
}


# ===================================================================
# Data Types
# ===================================================================

@dataclass
class AgentRecord:
    """
    Record of a single agent managed by the pool.

    Attributes:
        id: Unique agent identifier.
        name: Human-readable name.
        agent_type: The agent's role category.
        capabilities: Set of capability strings this agent provides.
        status: Current lifecycle status.
        current_task_id: The subtask ID this agent is working on (or None).
        task_history: List of task IDs this agent has completed.
        metadata: Arbitrary key-value store.
        spawned_at: When the agent was created.
        last_heartbeat: Timestamp of last activity.
        total_tasks_completed: Lifetime task count.
        total_execution_seconds: Cumulative execution time.
        confidence_score: Agent reliability score (0.0 - 1.0).
        communication_channel: Channel identifier for message routing.
        max_concurrent_tasks: Maximum simultaneous tasks this agent handles.
        active_task_count: Number of currently active tasks.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    agent_type: AgentType = AgentType.ORCHESTRATOR
    capabilities: Set[str] = field(default_factory=set)
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    task_history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    spawned_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_heartbeat: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_tasks_completed: int = 0
    total_execution_seconds: float = 0.0
    confidence_score: float = 0.9
    communication_channel: Optional[str] = None
    max_concurrent_tasks: int = 1
    active_task_count: int = 0

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"AgentRecord(id={self.id[:8]}, name={self.name!r}, "
            f"type={self.agent_type.value}, status={self.status.value})"
        )


@dataclass
class CapabilityMap:
    """
    Mapping from capability strings to sets of agent IDs.

    Provides O(1) agent lookup for any given capability.
    """

    _map: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add(self, agent_id: str, capabilities: Set[str]) -> None:
        """Register an agent's capabilities."""
        for cap in capabilities:
            self._map[cap].add(agent_id)

    def remove(self, agent_id: str, capabilities: Set[str]) -> None:
        """Remove an agent's capability entries."""
        for cap in capabilities:
            self._map[cap].discard(agent_id)

    def get_agents_for_capability(self, capability: str) -> Set[str]:
        """Get all agent IDs that provide a specific capability."""
        return self._map.get(capability, set())

    def get_agents_for_capabilities(self, capabilities: Set[str]) -> Dict[str, Set[str]]:
        """
        Get agent mappings for multiple capabilities.

        Returns a dict of capability -> set of agent IDs.
        """
        return {
            cap: self.get_agents_for_capability(cap)
            for cap in capabilities
        }

    def find_agents_covering_all(
        self, required: Set[str]
    ) -> Set[str]:
        """
        Find agent IDs that cover *all* required capabilities.

        Returns the intersection of agents across all required capabilities.
        """
        if not required:
            return set()
        result: Optional[Set[str]] = None
        for cap in required:
            agents = self._map.get(cap, set())
            if not agents:
                return set()
            if result is None:
                result = set(agents)
            else:
                result &= agents
        return result or set()

    def find_agents_covering_any(
        self, required: Set[str]
    ) -> Set[str]:
        """Find agents that cover *any* of the required capabilities."""
        result: Set[str] = set()
        for cap in required:
            result |= self._map.get(cap, set())
        return result

    def score_agent(
        self, agent_id: str, required: Set[str]
    ) -> float:
        """
        Compute a capability match score (0.0 - 1.0) for an agent against
        a set of required capabilities.

        score = |agent_capabilities ∩ required| / |required|
        """
        if not required:
            return 0.0
        agent_caps = self._get_agent_all_capabilities(agent_id)
        if not agent_caps:
            return 0.0
        matched = len(agent_caps & required)
        return matched / len(required)

    def _get_agent_all_capabilities(self, agent_id: str) -> Set[str]:
        """Reverse-lookup all capabilities for a given agent ID."""
        result: Set[str] = set()
        for cap, agents in self._map.items():
            if agent_id in agents:
                result.add(cap)
        return result

    def clear(self) -> None:
        """Remove all mappings."""
        self._map.clear()

    def __len__(self) -> int:
        return sum(len(v) for v in self._map.values())

    def __repr__(self) -> str:
        return (
            f"CapabilityMap({len(self._map)} capabilities, "
            f"{len(self)} agent-capability edges)"
        )


# ===================================================================
# Agent Spawning (Tendrils)
# ===================================================================

AgentSpawnerFn = Callable[[AgentType, Set[str], Dict[str, Any]], str]
"""
Signature for an agent spawning function.

Args:
    agent_type: The type of agent to spawn.
    capabilities: The capabilities the agent should have.
    config: Additional configuration.

Returns:
    The spawned agent's ID.
"""


class AgentSpawner:
    """
    Handles dynamic spawning and termination of agent instances.

    In production, this delegates to Claude Code subagent spawning or
    Hermes Agent delegation. For testing/development, it creates in-process
    agent records.
    """

    def __init__(self) -> None:
        self._spawn_fns: Dict[AgentType, AgentSpawnerFn] = {}

    def register_spawner(
        self, agent_type: AgentType, fn: AgentSpawnerFn
    ) -> None:
        """Register a custom spawner function for a specific agent type."""
        self._spawn_fns[agent_type] = fn
        logger.debug("Spawner registered for %s", agent_type.value)

    def spawn(
        self,
        agent_type: AgentType,
        capabilities: Set[str],
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Spawn a new agent of the given type.

        Uses the registered spawner function, or falls back to an in-process
        default that generates a UUID.

        Args:
            agent_type: Type of agent to spawn.
            capabilities: Capabilities for the new agent.
            config: Optional spawning configuration.

        Returns:
            The spawned agent's unique ID.
        """
        fn = self._spawn_fns.get(agent_type)
        if fn:
            return fn(agent_type, capabilities, config or {})

        # Default: return a UUID (in-process simulation)
        agent_id = uuid.uuid4().hex
        logger.info(
            "In-process agent spawned: id=%s, type=%s, capabilities=%s",
            agent_id[:8],
            agent_type.value,
            sorted(capabilities),
        )
        return agent_id

    def terminate(self, agent_id: str) -> bool:
        """
        Terminate an agent (no-op in default implementation).

        Override with actual subagent teardown logic.

        Returns:
            True if termination was successful.
        """
        logger.info("Agent %s terminated (default no-op)", agent_id[:8])
        return True


# ===================================================================
# Agent Pool
# ===================================================================

class AgentPool:
    """
    Dynamic agent registry and lifecycle manager (Tendrils pattern).

    The AgentPool is the central registry of all available agents. It
    manages capability indexing, load-balanced assignment, lifecycle
    tracking, and communication channel routing.

    Thread Safety:
        All public methods are thread-safe. Internal state is protected
        by a reentrant lock.

    Usage::

        pool = AgentPool()

        # Register a pre-existing agent
        pool.register_agent(agent_record)

        # Spawn a new agent dynamically
        agent_id = pool.spawn_agent(AgentType.CODE_REVIEWER)

        # Select an agent for a subtask
        agent_id = pool.select_agent({"c++_review", "misra_check"})

        # Execute a task on a specific agent
        result = pool.execute_on_agent(agent_id, task_data)

        # Get load statistics
        stats = pool.get_load_stats()
    """

    def __init__(
        self,
        max_agents: int = 50,
        auto_spawn: bool = True,
        spawner: Optional[AgentSpawner] = None,
    ) -> None:
        """
        Initialize the agent pool.

        Args:
            max_agents: Maximum number of concurrent agents.
            auto_spawn: If True, automatically spawn a default set of agents
                on first use.
            spawner: Custom AgentSpawner instance. If None, a default one
                is created.
        """
        self._lock = threading.RLock()
        self._max_agents = max_agents
        self._auto_spawn = auto_spawn
        self._auto_spawned = False

        # Core data structures
        self._agents: Dict[str, AgentRecord] = {}
        self._capability_map = CapabilityMap()

        # Spawning
        self._spawner = spawner or AgentSpawner()

        # Load balancing
        self._rr_counter: Dict[str, int] = defaultdict(int)
        self._balance_strategy = LoadBalanceStrategy.ROUND_ROBIN

        # Agent count per type
        self._type_counts: Dict[AgentType, int] = defaultdict(int)

        # Event callbacks
        self._on_register: List[Callable[[AgentRecord], None]] = []
        self._on_deregister: List[Callable[[AgentRecord], None]] = []
        self._on_status_change: List[
            Callable[[AgentRecord, AgentStatus, AgentStatus], None]
        ] = []

        logger.info(
            "AgentPool initialized (max_agents=%d, auto_spawn=%s)",
            max_agents,
            auto_spawn,
        )

    # ------------------------------------------------------------------
    # Agent Registration / Deregistration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        agent: AgentRecord,
        auto_dedup: bool = True,
    ) -> str:
        """
        Register an existing agent record with the pool.

        Args:
            agent: The agent record to register.
            auto_dedup: If True and an agent with the same ID exists,
                it is replaced.

        Returns:
            The agent ID.

        Raises:
            ValueError: If an agent with the same ID exists and
                ``auto_dedup`` is False.
        """
        with self._lock:
            if agent.id in self._agents:
                if auto_dedup:
                    self._deregister_agent_locked(agent.id)
                else:
                    raise ValueError(
                        f"Agent {agent.id[:8]} already registered"
                    )

            self._agents[agent.id] = agent
            self._capability_map.add(agent.id, agent.capabilities)
            self._type_counts[agent.agent_type] += 1

            for hook in self._on_register:
                self._safe_call_hook(hook, agent)

            logger.info(
                "Agent registered: id=%s, name=%s, type=%s, "
                "capabilities=%d",
                agent.id[:8],
                agent.name,
                agent.agent_type.value,
                len(agent.capabilities),
            )
            return agent.id

    def deregister_agent(self, agent_id: str) -> bool:
        """
        Remove an agent from the pool.

        Args:
            agent_id: The agent to remove.

        Returns:
            True if the agent was removed, False if not found.
        """
        with self._lock:
            return self._deregister_agent_locked(agent_id)

    def _deregister_agent_locked(self, agent_id: str) -> bool:
        """Internal deregistration (lock must be held)."""
        agent = self._agents.pop(agent_id, None)
        if agent is None:
            return False

        self._capability_map.remove(agent.id, agent.capabilities)
        self._type_counts[agent.agent_type] -= 1

        for hook in self._on_deregister:
            self._safe_call_hook(hook, agent)

        logger.debug("Agent deregistered: %s", agent_id[:8])
        return True

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """Get an agent record by ID."""
        with self._lock:
            return self._agents.get(agent_id)

    def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        status: Optional[AgentStatus] = None,
    ) -> List[AgentRecord]:
        """
        List agents, optionally filtered by type and/or status.

        Args:
            agent_type: Filter by agent type.
            status: Filter by current status.

        Returns:
            A list of matching AgentRecord instances.
        """
        with self._lock:
            result = list(self._agents.values())
            if agent_type is not None:
                result = [a for a in result if a.agent_type == agent_type]
            if status is not None:
                result = [a for a in result if a.status == status]
            return result

    # ------------------------------------------------------------------
    # Dynamic Spawning
    # ------------------------------------------------------------------

    def spawn_agent(
        self,
        agent_type: AgentType,
        name: Optional[str] = None,
        extra_capabilities: Optional[Set[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Dynamically spawn a new agent and register it.

        Args:
            agent_type: Type of agent to create.
            name: Optional human-readable name.
            extra_capabilities: Additional capabilities beyond defaults.
            config: Configuration passed to the spawner.

        Returns:
            The new agent's ID.

        Raises:
            RuntimeError: If the pool has reached max_agents.
        """
        with self._lock:
            if len(self._agents) >= self._max_agents:
                raise RuntimeError(
                    f"Agent pool full ({self._max_agents} max). "
                    f"Consider draining idle agents first."
                )

            capabilities = set(DEFAULT_CAPABILITIES.get(agent_type, set()))
            if extra_capabilities:
                capabilities |= extra_capabilities

            agent_id = self._spawner.spawn(
                agent_type, capabilities, config
            )

            agent_name = name or f"{agent_type.value}_{agent_id[:8]}"

            record = AgentRecord(
                id=agent_id,
                name=agent_name,
                agent_type=agent_type,
                capabilities=capabilities,
                status=AgentStatus.IDLE,
                metadata=config or {},
            )

            self._agents[agent_id] = record
            self._capability_map.add(agent_id, capabilities)
            self._type_counts[agent_type] += 1

            for hook in self._on_register:
                self._safe_call_hook(hook, record)

            logger.info(
                "Agent spawned: id=%s, name=%s, type=%s",
                agent_id[:8],
                agent_name,
                agent_type.value,
            )
            return agent_id

    def ensure_agent_type(
        self,
        agent_type: AgentType,
        min_count: int = 1,
    ) -> List[str]:
        """
        Ensure at least *min_count* agents of a given type exist.

        Spawns new agents if the current count is below *min_count*.

        Args:
            agent_type: The agent type to ensure.
            min_count: Minimum number of agents required.

        Returns:
            List of agent IDs (existing + newly spawned).
        """
        with self._lock:
            existing = [
                a.id
                for a in self._agents.values()
                if a.agent_type == agent_type
            ]
            to_spawn = max(0, min_count - len(existing))
            for _ in range(to_spawn):
                new_id = self.spawn_agent(agent_type)
                existing.append(new_id)

            if to_spawn > 0:
                logger.info(
                    "Ensured %d agents of type %s (spawned %d)",
                    min_count,
                    agent_type.value,
                    to_spawn,
                )
            return existing

    # ------------------------------------------------------------------
    # Agent Selection (Load-Balanced Assignment)
    # ------------------------------------------------------------------

    def select_agent(
        self,
        required_capabilities: Set[str],
        preferred_type: Optional[str] = None,
        strategy: Optional[LoadBalanceStrategy] = None,
        min_confidence: float = 0.0,
    ) -> str:
        """
        Select the best agent for a given set of capability requirements.

        The selection process:
          1. Find agents that cover all required capabilities
          2. If none, find agents that cover any required capabilities
          3. If ``preferred_type`` is set, prefer agents of that type
          4. Apply the load-balancing strategy to pick one
          5. Auto-spawn if no agent is found and ``auto_spawn`` is True

        Args:
            required_capabilities: Capabilities the agent must provide.
            preferred_type: Optional agent type preference.
            strategy: Load-balancing strategy. Defaults to the pool's
                current strategy.
            min_confidence: Minimum confidence score threshold.

        Returns:
            Selected agent ID.

        Raises:
            RuntimeError: If no suitable agent is found and auto-spawn fails.
        """
        with self._lock:
            strategy = strategy or self._balance_strategy

            # Ensure auto-spawn of common types
            if self._auto_spawn and not self._auto_spawned:
                self._auto_spawn_defaults()
                self._auto_spawned = True

            # Find candidate agents
            candidates = self._capability_map.find_agents_covering_all(
                required_capabilities
            )

            # Fall back to partial match
            if not candidates:
                candidates = self._capability_map.find_agents_covering_any(
                    required_capabilities
                )

            if not candidates:
                # Auto-spawn an agent of preferred type
                if self._auto_spawn and preferred_type:
                    try:
                        atype = AgentType(preferred_type)
                        new_id = self.spawn_agent(atype)
                        logger.info(
                            "Auto-spawned %s agent %s for capability gap",
                            preferred_type,
                            new_id[:8],
                        )
                        return new_id
                    except (ValueError, RuntimeError):
                        pass

                raise RuntimeError(
                    f"No agent found with capabilities {required_capabilities}. "
                    f"Available types: {dict(self._type_counts)}"
                )

            # Filter to preferred type if specified
            if preferred_type:
                type_filtered = {
                    aid
                    for aid in candidates
                    if self._agents[aid].agent_type.value == preferred_type
                }
                if type_filtered:
                    candidates = type_filtered

            # Filter by confidence
            if min_confidence > 0.0:
                candidates = {
                    aid
                    for aid in candidates
                    if self._agents[aid].confidence_score >= min_confidence
                }
                if not candidates:
                    raise RuntimeError(
                        f"No candidate meets min_confidence={min_confidence}"
                    )

            # Pick one agent via load-balancing strategy
            candidate_list = list(candidates)
            agent_id = self._apply_strategy(candidate_list, strategy)

            logger.debug(
                "Agent selected: %s (from %d candidates, strategy=%s)",
                agent_id[:8],
                len(candidate_list),
                strategy.value,
            )
            return agent_id

    # ------------------------------------------------------------------
    # Agent Execution
    # ------------------------------------------------------------------

    def assign_task(self, agent_id: str, task_id: str) -> bool:
        """
        Mark an agent as busy with a specific task.

        Args:
            agent_id: The agent to assign.
            task_id: The task/subtask ID.

        Returns:
            True if the assignment succeeded, False if the agent is
            already busy or not found.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                logger.warning("Agent %s not found for assignment", agent_id[:8])
                return False

            if agent.status == AgentStatus.TERMINATED:
                logger.warning("Agent %s is terminated", agent_id[:8])
                return False

            if agent.status == AgentStatus.DRAINING and agent.active_task_count >= 1:
                logger.warning("Agent %s is draining", agent_id[:8])
                return False

            old_status = agent.status
            agent.active_task_count += 1
            agent.current_task_id = task_id
            agent.last_heartbeat = datetime.now(timezone.utc).isoformat()

            if agent.active_task_count >= agent.max_concurrent_tasks:
                self._set_status(agent, AgentStatus.BUSY, old_status)

            return True

    def complete_task(
        self,
        agent_id: str,
        task_id: str,
        execution_seconds: float = 0.0,
        success: bool = True,
    ) -> None:
        """
        Mark a task as complete on the given agent.

        Args:
            agent_id: The agent that completed the task.
            task_id: The completed task ID.
            execution_seconds: How long the task took.
            success: Whether the task succeeded.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return

            old_status = agent.status
            agent.active_task_count = max(0, agent.active_task_count - 1)
            agent.task_history.append(task_id)
            agent.total_execution_seconds += execution_seconds

            if success:
                agent.total_tasks_completed += 1

            agent.current_task_id = None
            agent.last_heartbeat = datetime.now(timezone.utc).isoformat()

            # Transition status
            if agent.active_task_count == 0:
                if agent.status == AgentStatus.DRAINING:
                    # Draining complete → terminate
                    self._set_status(agent, AgentStatus.TERMINATED, old_status)
                    self._deregister_agent_locked(agent_id)
                    logger.info(
                        "Agent %s drained and terminated", agent_id[:8]
                    )
                else:
                    self._set_status(agent, AgentStatus.IDLE, old_status)

    # ------------------------------------------------------------------
    # Load Balancing
    # ------------------------------------------------------------------

    def set_load_balance_strategy(
        self, strategy: LoadBalanceStrategy
    ) -> None:
        """Set the load-balancing strategy for agent selection."""
        with self._lock:
            self._balance_strategy = strategy
            logger.info("Load balance strategy set to %s", strategy.value)

    def get_load_stats(self) -> Dict[str, Any]:
        """
        Return load statistics for the pool.

        Returns:
            Dictionary with agent counts per type, status distribution,
            and per-agent load metrics.
        """
        with self._lock:
            total = len(self._agents)
            by_type: Dict[str, int] = {}
            by_status: Dict[str, int] = {}
            idle_count = 0
            busy_count = 0

            for agent in self._agents.values():
                by_type[agent.agent_type.value] = (
                    by_type.get(agent.agent_type.value, 0) + 1
                )
                by_status[agent.status.value] = (
                    by_status.get(agent.status.value, 0) + 1
                )
                if agent.status == AgentStatus.IDLE:
                    idle_count += 1
                elif agent.status == AgentStatus.BUSY:
                    busy_count += 1

            return {
                "total_agents": total,
                "max_agents": self._max_agents,
                "by_type": by_type,
                "by_status": by_status,
                "idle": idle_count,
                "busy": busy_count,
                "utilization_pct": (
                    (busy_count / total * 100) if total > 0 else 0.0
                ),
                "balance_strategy": self._balance_strategy.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_capability_coverage(self) -> Dict[str, int]:
        """
        Return how many agents provide each capability.

        Useful for identifying capability gaps in the pool.
        """
        with self._lock:
            return {
                cap: len(agents)
                for cap, agents in self._capability_map._map.items()
            }

    # ------------------------------------------------------------------
    # Agent Lifecycle Management
    # ------------------------------------------------------------------

    def drain_agent(self, agent_id: str) -> bool:
        """
        Gracefully drain an agent: finish current task, then terminate.

        Args:
            agent_id: The agent to drain.

        Returns:
            True if the drain was initiated.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return False

            old_status = agent.status
            if agent.active_task_count == 0:
                self._set_status(agent, AgentStatus.TERMINATED, old_status)
                self._deregister_agent_locked(agent_id)
                logger.info("Agent %s terminated (no active tasks)", agent_id[:8])
            else:
                self._set_status(agent, AgentStatus.DRAINING, old_status)
                logger.info(
                    "Agent %s draining (%d active tasks)",
                    agent_id[:8],
                    agent.active_task_count,
                )
            return True

    def heartbeat(self, agent_id: str) -> bool:
        """
        Record a heartbeat for an agent (keeps it alive).

        Args:
            agent_id: The agent sending a heartbeat.

        Returns:
            True if the agent exists and was updated.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return False
            agent.last_heartbeat = datetime.now(timezone.utc).isoformat()
            return True

    def reap_stale_agents(
        self, max_idle_seconds: int = 300
    ) -> List[str]:
        """
        Terminate agents that have been idle for too long.

        Args:
            max_idle_seconds: Maximum allowed idle time.

        Returns:
            List of terminated agent IDs.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            reaped: List[str] = []

            for agent_id, agent in list(self._agents.items()):
                if agent.status != AgentStatus.IDLE:
                    continue
                last = datetime.fromisoformat(agent.last_heartbeat)
                idle_seconds = (now - last).total_seconds()
                if idle_seconds > max_idle_seconds:
                    old_status = agent.status
                    self._set_status(
                        agent, AgentStatus.TERMINATED, old_status
                    )
                    self._deregister_agent_locked(agent_id)
                    reaped.append(agent_id)
                    logger.info(
                        "Agent %s reaped (idle %.0fs > %ds)",
                        agent_id[:8],
                        idle_seconds,
                        max_idle_seconds,
                    )

            if reaped:
                logger.info(
                    "Reaped %d stale agents", len(reaped)
                )
            return reaped

    # ------------------------------------------------------------------
    # Event Hooks
    # ------------------------------------------------------------------

    def on_register(self, hook: Callable[[AgentRecord], None]) -> None:
        """Register a callback fired when an agent is registered."""
        self._on_register.append(hook)

    def on_deregister(self, hook: Callable[[AgentRecord], None]) -> None:
        """Register a callback fired when an agent is deregistered."""
        self._on_deregister.append(hook)

    def on_status_change(
        self,
        hook: Callable[[AgentRecord, AgentStatus, AgentStatus], None],
    ) -> None:
        """
        Register a callback fired when an agent changes status.

        The hook receives ``(agent, old_status, new_status)``.
        """
        self._on_status_change.append(hook)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _apply_strategy(
        self,
        candidates: List[str],
        strategy: LoadBalanceStrategy,
    ) -> str:
        """Apply the load-balancing strategy to pick one agent."""
        if strategy == LoadBalanceStrategy.ROUND_ROBIN:
            # Pick or initialize counter
            for aid in candidates:
                self._rr_counter.setdefault(aid, 0)
            # Find the least-recently-used candidate
            min_count = min(self._rr_counter[aid] for aid in candidates)
            tied = [aid for aid in candidates if self._rr_counter[aid] == min_count]
            chosen = random.choice(tied)
            self._rr_counter[chosen] += 1
            return chosen

        elif strategy == LoadBalanceStrategy.LEAST_LOADED:
            # Pick agent with fewest active tasks
            return min(
                candidates,
                key=lambda aid: (
                    self._agents[aid].active_task_count
                    if aid in self._agents
                    else float("inf")
                ),
            )

        elif strategy == LoadBalanceStrategy.CAPABILITY_WEIGHTED:
            # Weighted random: agents with higher confidence get more weight
            weights = []
            for aid in candidates:
                agent = self._agents.get(aid)
                w = agent.confidence_score if agent else 0.1
                weights.append(max(w, 0.01))
            total = sum(weights)
            normalized = [w / total for w in weights]
            return random.choices(candidates, weights=normalized, k=1)[0]

        else:
            # RANDOM (default)
            return random.choice(candidates)

    def _set_status(
        self,
        agent: AgentRecord,
        new_status: AgentStatus,
        old_status: AgentStatus,
    ) -> None:
        """Update agent status and fire hooks."""
        agent.status = new_status
        for hook in self._on_status_change:
            self._safe_call_hook(hook, agent, old_status, new_status)

    def _auto_spawn_defaults(self) -> None:
        """Auto-spawn one agent of each type on first use."""
        for atype in AgentType:
            if atype != AgentType.ORCHESTRATOR:
                try:
                    self.spawn_agent(atype)
                except RuntimeError as exc:
                    logger.warning(
                        "Auto-spawn failed for %s: %s",
                        atype.value,
                        exc,
                    )
                    break

    @staticmethod
    def _safe_call_hook(hook: Callable, *args: Any) -> None:
        """Call a hook safely, logging any exceptions."""
        try:
            hook(*args)
        except Exception as exc:
            logger.warning("Hook %s raised: %s", hook.__name__, exc)


# ===================================================================
# Convenience Factory
# ===================================================================

def create_agent_pool(
    max_agents: int = 50,
    auto_spawn: bool = True,
    pre_spawn_agents: Optional[List[AgentType]] = None,
) -> AgentPool:
    """
    Convenience factory for creating a pre-configured AgentPool.

    Args:
        max_agents: Maximum concurrent agents.
        auto_spawn: If True, auto-spawn default agent set on first use.
        pre_spawn_agents: If provided, spawn one agent of each listed type
            immediately.

    Returns:
        A ready-to-use AgentPool instance.
    """
    pool = AgentPool(max_agents=max_agents, auto_spawn=auto_spawn)

    if pre_spawn_agents:
        for atype in pre_spawn_agents:
            try:
                pool.spawn_agent(atype)
                logger.debug(
                    "Pre-spawned agent of type %s", atype.value
                )
            except RuntimeError as exc:
                logger.warning(
                    "Pre-spawn failed for %s: %s",
                    atype.value,
                    exc,
                )

    logger.info(
        "AgentPool factory created instance (max=%d, auto_spawn=%s, "
        "pre_spawn=%s)",
        max_agents,
        auto_spawn,
        [t.value for t in (pre_spawn_agents or [])],
    )
    return pool
