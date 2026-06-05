#!/usr/bin/env python3
"""Nonull Multi-Agent Workflow Example 多智能体工作流示例.

This example demonstrates how to orchestrate multiple sub-agents
using the Nexus Tendrils pattern for complex ADAS analysis tasks.

本示例演示如何使用 Nexus Tendrils 模式编排多个子智能体
以完成复杂的 ADAS 分析任务。
"""

import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Data Models 数据模型
# =============================================================================

class AgentStatus(Enum):
    """Agent execution status / 智能体执行状态."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubAgent:
    """Represents a sub-agent in the orchestration.
    表示编排中的一个子智能体。"""
    agent_id: str
    name: str
    task: str
    skill: str
    params: dict
    status: AgentStatus = AgentStatus.PENDING
    result: dict = field(default_factory=dict)
    started_at: float = 0.0
    completed_at: float = 0.0

    @property
    def duration_ms(self) -> float:
        """Get execution duration in milliseconds.
        获取执行持续时间（毫秒）。"""
        if self.completed_at > 0 and self.started_at > 0:
            return round((self.completed_at - self.started_at) * 1000, 1)
        return 0.0


class WorkflowPattern(Enum):
    """Supported workflow patterns / 支持的工作流模式."""
    NEXUS_TENDRILS = "nexus_tendrils"
    SEQUENTIAL = "sequential"
    CONSENSUS = "consensus"
    BROADCAST = "broadcast"


# =============================================================================
# Orchestration Engine 编排引擎
# =============================================================================

class OrchestrationEngine:
    """Multi-agent orchestration engine.
    多智能体编排引擎。"""

    def __init__(self, max_concurrent: int = 8):
        self.max_concurrent = max_concurrent
        self.sub_agents: list[SubAgent] = []
        self.pattern = WorkflowPattern.NEXUS_TENDRILS

    def decompose_task(self, main_task: str) -> list[dict]:
        """Decompose a complex task into sub-tasks.
        将复杂任务分解为子任务。

        Args:
            main_task: 主任务描述 / Main task description

        Returns:
            list[dict]: 子任务列表 / List of sub-tasks
        """
        # Simulate task decomposition 模拟任务分解
        return [
            {
                "name": "System Context",
                "task": "Analyze system boundaries and interfaces",
                "skill": "architecture-design",
                "params": {"focus": "context"},
            },
            {
                "name": "Functional Analysis",
                "task": "Analyze functional requirements and behavior",
                "skill": "requirement-analysis",
                "params": {"focus": "functional"},
            },
            {
                "name": "Safety Analysis",
                "task": "Perform hazard analysis and risk assessment",
                "skill": "safety-analysis",
                "params": {"analysis_type": "hara"},
            },
            {
                "name": "Architecture Review",
                "task": "Review software architecture for compliance",
                "skill": "architecture-design",
                "params": {"focus": "compliance"},
            },
            {
                "name": "Code Quality",
                "task": "Evaluate code quality and best practices",
                "skill": "code-review",
                "params": {"focus": "best_practice"},
            },
        ]

    async def execute_sub_agent(
        self, sub_agent: SubAgent, result_callback: Callable = None
    ) -> SubAgent:
        """Execute a single sub-agent task.
        执行单个子智能体任务。

        Args:
            sub_agent: 子智能体 / Sub-agent to execute
            result_callback: 结果回调 / Optional result callback

        Returns:
            SubAgent: 执行完成的子智能体 / Completed sub-agent
        """
        sub_agent.status = AgentStatus.RUNNING
        sub_agent.started_at = time.time()

        # Simulate execution time (different per skill) 模拟执行时间
        execution_time = {
            "architecture-design": 0.8,
            "requirement-analysis": 1.2,
            "safety-analysis": 2.0,
            "code-review": 1.5,
        }.get(sub_agent.skill, 1.0)

        await asyncio.sleep(execution_time)

        # Simulate result 模拟结果
        sub_agent.result = {
            "skill": sub_agent.skill,
            "task": sub_agent.task,
            "status": "passed",
            "findings": [
                f"Finding 1 from {sub_agent.name}",
                f"Finding 2 from {sub_agent.name}",
            ],
            "score": round(85 + (hash(sub_agent.agent_id) % 10), 1),
        }

        sub_agent.status = AgentStatus.COMPLETED
        sub_agent.completed_at = time.time()

        if result_callback:
            result_callback(sub_agent)

        return sub_agent

    async def orchestrate_nexus_tendrils(
        self, main_task: str
    ) -> dict:
        """Nexus Tendrils orchestration pattern.
        Nexus Tendrils 编排模式。

        Decomposes the main task and executes sub-agents in parallel.
        分解主任务并并行执行子智能体。

        Args:
            main_task: 主任务 / Main task description

        Returns:
            dict: 编排结果 / Orchestration result
        """
        print(f"\n[NEXUS TENDRILS] Decomposing task 分解任务:")
        print(f"  Main 主任务: {main_task}")

        # Decompose 分解任务
        sub_tasks = self.decompose_task(main_task)
        self.sub_agents = []

        for i, sub in enumerate(sub_tasks):
            agent = SubAgent(
                agent_id=f"agent-{i+1:03d}",
                name=sub["name"],
                task=sub["task"],
                skill=sub["skill"],
                params=sub["params"],
            )
            self.sub_agents.append(agent)

        print(f"  Sub-agents created 子智能体创建: {len(self.sub_agents)}")
        for a in self.sub_agents:
            print(f"    [{a.agent_id}] {a.name} — skill: {a.skill}")

        # Execute in parallel 并行执行
        print(f"\n[NEXUS TENDRILS] Executing sub-agents in parallel 并行执行...")
        print(f"  Max concurrent 最大并发: {self.max_concurrent}")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_execute(agent: SubAgent) -> SubAgent:
            async with semaphore:
                return await self.execute_sub_agent(agent)

        start_time = time.time()
        tasks = [bounded_execute(agent) for agent in self.sub_agents]
        completed_agents = await asyncio.gather(*tasks)
        total_duration = round((time.time() - start_time) * 1000, 1)

        # Synthesize results 综合结果
        return self._synthesize_results(completed_agents, total_duration)

    async def orchestrate_sequential(self, tasks: list[dict]) -> dict:
        """Sequential orchestration pattern.
        顺序编排模式。

        Args:
            tasks: 任务列表 / List of tasks to execute sequentially

        Returns:
            dict: 编排结果 / Orchestration result
        """
        print(f"\n[SEQUENTIAL] Starting sequential pipeline 开始顺序流水线...")
        results = []
        start_time = time.time()

        for i, task in enumerate(tasks):
            agent = SubAgent(
                agent_id=f"seq-{i+1:03d}",
                name=task.get("name", f"Step {i+1}"),
                task=task.get("task", ""),
                skill=task.get("skill", "general"),
                params=task.get("params", {}),
            )
            print(f"  Step {i+1}: {agent.name} ({agent.skill})")
            result = await self.execute_sub_agent(agent)
            results.append(result)

        total_duration = round((time.time() - start_time) * 1000, 1)
        return self._synthesize_results(results, total_duration)

    def _synthesize_results(
        self, agents: list[SubAgent], duration_ms: float
    ) -> dict:
        """Synthesize individual results into a unified report.
        将各个结果综合为统一报告。

        Args:
            agents: 完成的子智能体列表 / Completed sub-agents
            duration_ms: 总执行时间 / Total execution time

        Returns:
            dict: 综合报告 / Synthesized report
        """
        scores = []
        findings = []
        total_findings = 0

        for agent in agents:
            if agent.result:
                scores.append(agent.result.get("score", 0))
                findings.extend(agent.result.get("findings", []))
                total_findings += len(agent.result.get("findings", []))

        overall_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        return {
            "pattern": self.pattern.value,
            "total_agents": len(agents),
            "total_duration_ms": duration_ms,
            "overall_score": overall_score,
            "total_findings": total_findings,
            "agent_results": [
                {
                    "id": a.agent_id,
                    "name": a.name,
                    "skill": a.skill,
                    "status": a.status.value,
                    "duration_ms": a.duration_ms,
                    "findings": a.result.get("findings", []) if a.result else [],
                    "score": a.result.get("score", 0) if a.result else 0,
                }
                for a in agents
            ],
            "synthesized_findings": findings[:10],  # Top 10 findings
            "summary": {
                "agents_completed": sum(1 for a in agents if a.status == AgentStatus.COMPLETED),
                "agents_failed": sum(1 for a in agents if a.status == AgentStatus.FAILED),
                "average_score": overall_score,
            },
        }


# =============================================================================
# Demo Functions 演示功能
# =============================================================================

async def demo_nexus_tendrils():
    """Demonstrate Nexus Tendrils pattern.
    演示 Nexus Tendrils 模式。"""
    print("\n" + "=" * 70)
    print("Demo: Nexus Tendrils Orchestration Nexus Tendrils 编排")
    print("=" * 70)

    engine = OrchestrationEngine(max_concurrent=8)
    engine.pattern = WorkflowPattern.NEXUS_TENDRILS

    result = await engine.orchestrate_nexus_tendrils(
        "Analyze the AEB system software architecture for ISO 26262 compliance"
    )

    _print_orchestration_result(result)
    return result


async def demo_sequential():
    """Demonstrate Sequential pipeline pattern.
    演示顺序流水线模式。"""
    print("\n" + "=" * 70)
    print("Demo: Sequential Pipeline 顺序流水线")
    print("=" * 70)

    engine = OrchestrationEngine()
    engine.pattern = WorkflowPattern.SEQUENTIAL

    tasks = [
        {"name": "Requirements Input", "task": "Parse requirements", "skill": "requirement-analysis"},
        {"name": "Safety Analysis", "task": "Run HARA", "skill": "safety-analysis"},
        {"name": "Report Generation", "task": "Generate report", "skill": "document-generation"},
    ]

    result = await engine.orchestrate_sequential(tasks)
    _print_orchestration_result(result)
    return result


async def demo_consensus():
    """Demonstrate Consensus review pattern.
    演示共识审查模式。"""
    print("\n" + "=" * 70)
    print("Demo: Consensus Review 共识审查")
    print("=" * 70)

    engine = OrchestrationEngine(max_concurrent=3)
    engine.pattern = WorkflowPattern.CONSENSUS

    # Three agents review the same code from different perspectives
    # 三个智能体从不同角度审查同一段代码
    reviewers = [
        {"name": "Safety Expert", "task": "Review safety compliance", "skill": "safety-analysis",
         "params": {"focus": "safety"}},
        {"name": "Performance Engineer", "task": "Review performance impact", "skill": "perf-analysis",
         "params": {"focus": "performance"}},
        {"name": "Domain Expert", "task": "Review domain correctness", "skill": "code-review",
         "params": {"focus": "correctness"}},
    ]

    # Simulate parallel consensus review
    semaphore = asyncio.Semaphore(engine.max_concurrent)

    async def run_reviewer(task: dict) -> SubAgent:
        async with semaphore:
            agent = SubAgent(
                agent_id=f"reviewer-{uuid.uuid4().hex[:4]}",
                name=task["name"],
                task=task["task"],
                skill=task["skill"],
                params=task.get("params", {}),
            )
            return await engine.execute_sub_agent(agent)

    start_time = time.time()
    tasks = [run_reviewer(t) for t in reviewers]
    completed = await asyncio.gather(*tasks)
    duration = round((time.time() - start_time) * 1000, 1)

    # Consensus synthesis 共识综合
    all_pass = all(
        a.result.get("status") == "passed" for a in completed if a.result
    )

    result = engine._synthesize_results(completed, duration)
    result["consensus_verdict"] = "PASS" if all_pass else "REVIEW_REQUIRED"

    _print_orchestration_result(result)
    print(f"  Consensus Verdict 共识裁决: {result['consensus_verdict']}")
    return result


def _print_orchestration_result(result: dict):
    """Print orchestration result in a formatted way.
    以格式化方式打印编排结果。"""
    summary = result["summary"]
    print(f"\n{'─' * 50}")
    print("Orchestration Results 编排结果")
    print(f"{'─' * 50}")
    print(f"  Pattern 模式: {result['pattern']}")
    print(f"  Total Agents 智能体总数: {result['total_agents']}")
    print(f"  Completed 完成: {summary['agents_completed']}")
    print(f"  Failed 失败: {summary['agents_failed']}")
    print(f"  Duration 耗时: {result['total_duration_ms']} ms")
    print(f"  Average Score 平均分: {summary['average_score']}/100")
    print(f"  Total Findings 发现问题: {result['total_findings']}")

    print(f"\n  Agent Details 智能体详情:")
    for agent in result["agent_results"]:
        status_icon = "+" if agent["status"] == "completed" else "!"
        print(f"    [{status_icon}] {agent['id']} {agent['name']}: "
              f"{agent['score']}/100 ({agent['duration_ms']}ms)")
        for finding in agent["findings"]:
            print(f"      - {finding}")


# =============================================================================
# Main 主程序
# =============================================================================

async def main():
    """Main entry point.
    主入口点。"""
    print(r"""
    ╔══════════════════════════════════════════════════════════╗
    ║           Nonull 智驾智能体                       ║
    ║           Multi-Agent Workflow 多智能体工作流             ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    print("Available Patterns 可用模式:")
    print("  1. Nexus Tendrils — Parallel decomposition, parallel execution")
    print("     并行分解，并行执行")
    print("  2. Sequential — Linear pipeline")
    print("     线性流水线")
    print("  3. Consensus — Multi-perspective review")
    print("     多角度审查")

    # Run all three demos 运行所有三个演示
    nexus_result = await demo_nexus_tendrils()
    seq_result = await demo_sequential()
    consensus_result = await demo_consensus()

    # Comparison 对比
    print(f"\n{'=' * 70}")
    print("Pattern Comparison 模式对比")
    print(f"{'=' * 70}")
    print(f"  {'Pattern':<20} {'Agents':<10} {'Duration(ms)':<15} {'Score':<10}")
    print(f"  {'-'*20} {'-'*10} {'-'*15} {'-'*10}")
    print(f"  {'Nexus Tendrils':<20} {nexus_result['total_agents']:<10} "
          f"{nexus_result['total_duration_ms']:<15} {nexus_result['overall_score']:<10}")
    print(f"  {'Sequential':<20} {seq_result['total_agents']:<10} "
          f"{seq_result['total_duration_ms']:<15} {seq_result['overall_score']:<10}")
    print(f"  {'Consensus':<20} {consensus_result['total_agents']:<10} "
          f"{consensus_result['total_duration_ms']:<15} {consensus_result['overall_score']:<10}")

    print("\nMulti-agent workflow demo complete! 多智能体工作流演示完成！")
    print("\nKey Takeaways 关键要点:")
    print("  1. Nexus Tendrils is best for complex, decomposable tasks")
    print("     Nexus Tendrils 最适合复杂的可分解任务")
    print("  2. Sequential is best for linear dependency chains")
    print("     顺序模式最适合线性依赖链")
    print("  3. Consensus is best for review and validation tasks")
    print("     共识模式最适合审查和验证任务")


if __name__ == "__main__":
    asyncio.run(main())
