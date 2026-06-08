"""Tests for core/sub_agent.py — Deep Agents v0.5 style async sub-agents."""
import asyncio
import pytest
from core.sub_agent import AsyncSubAgent, SubAgentTask, SubAgentPool


class TestSubAgentTask:
    def test_default_id(self):
        t = SubAgentTask()
        assert t.id.startswith("task_")
        assert t.status == "pending"

    def test_custom_fields(self):
        t = SubAgentTask(description="test", context={"key": "val"})
        t.result = {"ok": True}
        assert t.result["ok"]


class TestAsyncSubAgent:
    @pytest.mark.asyncio
    async def test_submit_and_complete(self):
        agent = AsyncSubAgent(name="test")

        async def echo(task):
            await asyncio.sleep(0.01)
            return {"echo": task.description}

        agent.bind_executor(echo)
        task = SubAgentTask(description="hello")
        task_id = await agent.submit(task)
        assert task_id == task.id
        assert task.status == "running"

        result = await agent.get_result(task_id, timeout=5.0)
        assert result.status == "completed"
        assert result.result["echo"] == "hello"

    @pytest.mark.asyncio
    async def test_sync_executor(self):
        agent = AsyncSubAgent(name="sync")

        def sync_func(task):
            return {"sync": True}

        agent.bind_executor(sync_func)
        task_id = await agent.submit(SubAgentTask(description="sync"))
        result = await agent.get_result(task_id, timeout=5.0)
        assert result.status == "completed"
        assert result.result["sync"] is True

    @pytest.mark.asyncio
    async def test_task_failure_is_caught(self):
        agent = AsyncSubAgent(name="failing")

        async def fail(task):
            raise ValueError("Intentional failure")

        agent.bind_executor(fail)
        task_id = await agent.submit(SubAgentTask(description="fail"))
        result = await agent.get_result(task_id, timeout=5.0)
        assert result.status == "failed"
        assert "ValueError" in result.error

    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self):
        agent = AsyncSubAgent(name="lister")

        async def quick(task):
            return {"done": True}

        agent.bind_executor(quick)
        await agent.submit(SubAgentTask(description="a"))
        await agent.submit(SubAgentTask(description="b"))
        await asyncio.sleep(0.1)
        completed = agent.list_tasks(status="completed")
        assert len(completed) == 2

    @pytest.mark.asyncio
    async def test_get_status_without_waiting(self):
        agent = AsyncSubAgent(name="status")

        async def slow(task):
            await asyncio.sleep(1)

        agent.bind_executor(slow)
        tid = await agent.submit(SubAgentTask(description="slow"))
        status = agent.get_status(tid)
        assert status == "running" or status == "pending"


class TestSubAgentPool:
    @pytest.mark.asyncio
    async def test_register_and_submit(self):
        pool = SubAgentPool()
        agent = AsyncSubAgent(name="worker")

        async def work(task):
            return {"processed": task.description}

        agent.bind_executor(work)
        pool.register("worker", agent)
        assert pool.get("worker") is agent

        task = SubAgentTask(description="pool test")
        task_id = await pool.submit("worker", task)
        assert task_id == task.id

    @pytest.mark.asyncio
    async def test_submit_and_wait(self):
        pool = SubAgentPool()
        agent = AsyncSubAgent(name="waiter")

        async def quick(task):
            return {"result": 42}

        agent.bind_executor(quick)
        pool.register("waiter", agent)

        task = SubAgentTask(description="wait test")
        result = await pool.submit_and_wait("waiter", task, timeout=5.0)
        assert result.status == "completed"
        assert result.result["result"] == 42

    @pytest.mark.asyncio
    async def test_get_all_status(self):
        pool = SubAgentPool()
        agent = AsyncSubAgent(name="a")

        async def nop(task):
            return {}

        agent.bind_executor(nop)
        pool.register("a", agent)
        await pool.submit("a", SubAgentTask(description="x"))
        await asyncio.sleep(0.05)
        statuses = pool.get_all_status()
        assert "a" in statuses
