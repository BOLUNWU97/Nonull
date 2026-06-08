"""
Async Sub-Agents — Deep Agents v0.5 style non-blocking delegation.

Allows the main agent to delegate tasks to sub-agents that run in isolated
context windows. Sub-agents execute asynchronously and return results when done.
"""
from __future__ import annotations
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("Nonull.sub_agent")


@dataclass
class SubAgentTask:
    """A task to be executed by a sub-agent."""
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"  # pending | running | completed | failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AsyncSubAgent:
    """A sub-agent that executes a task in an isolated context.

    Usage:
        agent = AsyncSubAgent(name="code-reviewer")
        agent.bind_executor(my_function)
        task = SubAgentTask(description="Review this code", context={"code": "..."})
        await agent.submit(task)
        result = await agent.wait_for_result(task.id)
    """

    def __init__(self, name: str = "sub_agent"):
        self.name = name
        self._executor: Optional[Callable] = None
        self._tasks: Dict[str, SubAgentTask] = {}
        self._running: Dict[str, asyncio.Task] = {}

    def bind_executor(self, func: Callable):
        """Bind a function that executes tasks."""
        self._executor = func

    async def submit(self, task: SubAgentTask) -> str:
        """Submit a task for async execution (non-blocking)."""
        if self._executor is None:
            raise RuntimeError(f"No executor bound to {self.name}")

        task.status = "running"
        self._tasks[task.id] = task

        async def _run():
            try:
                if asyncio.iscoroutinefunction(self._executor):
                    result = await self._executor(task)
                else:
                    result = await asyncio.to_thread(self._executor, task)
                task.status = "completed"
                task.result = result if isinstance(result, dict) else {"output": str(result)}
            except Exception as e:
                task.status = "failed"
                task.error = f"{type(e).__name__}: {e}"
                logger.exception("Sub-agent %s task %s failed", self.name, task.id)

        self._running[task.id] = asyncio.create_task(_run())
        logger.info("Sub-agent %s submitted task %s", self.name, task.id)
        return task.id

    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[SubAgentTask]:
        """Get the result of a task, optionally waiting for completion."""
        if task_id not in self._tasks:
            return None
        if task_id in self._running:
            try:
                await asyncio.wait_for(self._running[task_id], timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Task %s timed out after %ss", task_id, timeout)
        return self._tasks[task_id]

    def get_status(self, task_id: str) -> Optional[str]:
        """Get the status of a task without waiting."""
        task = self._tasks.get(task_id)
        return task.status if task else None

    def list_tasks(self, status: Optional[str] = None) -> List[SubAgentTask]:
        """List all tasks, optionally filtered by status."""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())


class SubAgentPool:
    """A pool of named sub-agents for delegating tasks.

    Usage:
        pool = SubAgentPool()
        pool.register("reviewer", AsyncSubAgent("reviewer"))
        pool.register("researcher", AsyncSubAgent("researcher"))
        task_id = await pool.submit("reviewer", SubAgentTask(description="..."))
    """

    def __init__(self):
        self._agents: Dict[str, AsyncSubAgent] = {}

    def register(self, name: str, agent: AsyncSubAgent):
        self._agents[name] = agent

    def get(self, name: str) -> Optional[AsyncSubAgent]:
        return self._agents.get(name)

    async def submit(self, agent_name: str, task: SubAgentTask) -> str:
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"No sub-agent named '{agent_name}'")
        return await agent.submit(task)

    async def submit_and_wait(self, agent_name: str, task: SubAgentTask,
                              timeout: float = 30.0) -> Optional[SubAgentTask]:
        task_id = await self.submit(agent_name, task)
        agent = self._agents[agent_name]
        return await agent.get_result(task_id, timeout=timeout)

    def get_all_status(self) -> Dict[str, List[Dict]]:
        return {
            name: [{"id": t.id, "status": t.status} for t in agent.list_tasks()]
            for name, agent in self._agents.items()
        }
