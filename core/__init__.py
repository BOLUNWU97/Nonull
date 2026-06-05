"""
Nonull (智驾智能体) - Core Framework Package
====================================================

融合架构 (Fusion Architecture):
  - OpenClaw: Gateway/Agents/Channels 三层架构, SOUL.md 身份体系, Nexus+Tendrils
  - Hermes Agent: 提供商无关, 工具注册表, 配置档隔离, 会话持久化
  - openHuman: 新皮层记忆, 潜意识循环
  - Claude Code: 拒绝优先安全, 钩子系统, 子智能体隔离, 压缩

@package: core
@version: 0.1.0
@since:   2026-06-05
"""

# Single source of truth for the project version
__version__ = "0.1.0"

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# Version info
__author__ = "Nonull Team"
__license__ = "MIT"
__description__ = "Autonomous Driving AI Agent Framework (自动驾驶AI智能体框架)"

# Enumerate public API
__all__: List[str] = [
    # Config
    "NonullConfig",
    # Core agent
    "Nonull",
    # States
    "AgentState",
    "AgentStatus",
    # Memory
    "BaseMemory",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    # Safety
    "SafetyGuardian",
    "SafetyViolation",
    # Tools / Skills
    "ToolRegistry",
    "BaseTool",
    "SkillRegistry",
    "BaseSkill",
    # Subagent
    "SubagentSpec",
    "SubagentResult",
    # Hooks
    "HookRegistry",
    "HookPoint",
]

# ---------------------------------------------------------------------------
# Enums / Types
# ---------------------------------------------------------------------------

from enum import Enum, auto


class AgentState(str, Enum):
    """智能体状态枚举 / Agent state enumeration."""
    IDLE = "idle"
    PLANNING = "planning"
    REASONING = "reasoning"
    ACTING = "acting"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"
    RECOVERING = "recovering"


class AgentStatus:
    """智能体状态快照 / Agent status snapshot.

    Attributes:
        state:      当前状态
        session_id: 当前会话标识
        task:       正在处理的任务
        progress:   进度信息
        error:      错误信息（如有）
        started_at: 开始时间戳
    """

    def __init__(
        self,
        state: AgentState = AgentState.IDLE,
        session_id: str = "",
        task: str = "",
        progress: Dict[str, Any] = None,
        error: Optional[str] = None,
        started_at: Optional[float] = None,
    ) -> None:
        self.state = state
        self.session_id = session_id
        self.task = task
        self.progress = progress or {}
        self.error = error
        self.started_at = started_at

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dict."""
        return {
            "state": self.state.value,
            "session_id": self.session_id,
            "task": self.task,
            "progress": self.progress,
            "error": self.error,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentStatus":
        """从字典反序列化 / Deserialize from dict."""
        return cls(
            state=AgentState(data.get("state", "idle")),
            session_id=data.get("session_id", ""),
            task=data.get("task", ""),
            progress=data.get("progress", {}),
            error=data.get("error"),
            started_at=data.get("started_at"),
        )


# ---------------------------------------------------------------------------
# Lazy imports for sub-modules
# ---------------------------------------------------------------------------

def _lazy_import(module_name: str, class_name: str):
    """延迟导入 / Lazy import helper."""
    import importlib
    module = importlib.import_module(f".{module_name}", package=__package__)
    return getattr(module, class_name)


def NonullConfig(*args, **kwargs):
    """延迟初始化的配置类 / Lazily initialized config class."""
    cls = _lazy_import("config", "NonullConfig")
    return cls(*args, **kwargs)


def Nonull(*args, **kwargs):
    """延迟初始化的智能体主类 / Lazily initialized agent core class."""
    cls = _lazy_import("agent_core", "Nonull")
    return cls(*args, **kwargs)


def SafetyGuardian(*args, **kwargs):
    """延迟初始化的安全监护类 / Lazily initialized safety guardian class."""
    cls = _lazy_import("agent_core", "SafetyGuardian")
    return cls(*args, **kwargs)


# Re-export commonly used symbols from sub-modules via lazy accessors
# for IDE support we also provide direct references when sub-modules loaded.

def __getattr__(name: str):
    """支持顶级包属性访问 / Support top-level package attribute access."""
    _MAPPING = {
        "AgentState": ("agent_core", "AgentState"),
        "AgentStatus": ("agent_core", "AgentStatus"),
        "BaseMemory": ("agent_core", "BaseMemory"),
        "WorkingMemory": ("agent_core", "WorkingMemory"),
        "EpisodicMemory": ("agent_core", "EpisodicMemory"),
        "SemanticMemory": ("agent_core", "SemanticMemory"),
        "ProceduralMemory": ("agent_core", "ProceduralMemory"),
        "SafetyGuardian": ("agent_core", "SafetyGuardian"),
        "SafetyViolation": ("agent_core", "SafetyViolation"),
        "ToolRegistry": ("agent_core", "ToolRegistry"),
        "BaseTool": ("agent_core", "BaseTool"),
        "SkillRegistry": ("agent_core", "SkillRegistry"),
        "BaseSkill": ("agent_core", "BaseSkill"),
        "SubagentSpec": ("agent_core", "SubagentSpec"),
        "SubagentResult": ("agent_core", "SubagentResult"),
        "HookRegistry": ("agent_core", "HookRegistry"),
        "HookPoint": ("agent_core", "HookPoint"),
    }
    if name in _MAPPING:
        mod, cls_name = _MAPPING[name]
        return _lazy_import(mod, cls_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
