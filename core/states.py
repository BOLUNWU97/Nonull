"""
Agent states — 智能体状态枚举. Extracted from agent_core.py for modularity.
"""

from enum import Enum


class AgentState(str, Enum):
    """
    智能体状态枚举 / Agent State Enumeration.

    融合 ReAct + Plan-and-Execute + Reflexion 的生命周期状态。
    """
    # ── 基础状态 ──────────────────────────────────────────────
    IDLE = "idle"                     # 空闲 / Idle
    PLANNING = "planning"             # 规划中 / Planning
    REASONING = "reasoning"           # 推理中 / Reasoning
    ACTING = "acting"                 # 执行中 / Acting
    REFLECTING = "reflecting"         # 反思中 / Reflecting
    COMPLETED = "completed"           # 已完成 / Completed
    # ── 异常状态 ──────────────────────────────────────────────
    ERROR = "error"                   # 错误 / Error
    RECOVERING = "recovering"         # 恢复中 / Recovering
    # ── 子智能体状态 ──────────────────────────────────────────
    SPAWNING = "spawning"             # 生成子智能体 / Spawning subagent
    WAITING_SUBAGENT = "waiting_subagent"  # 等待子智能体 / Waiting for subagent


__all__ = ["AgentState"]
