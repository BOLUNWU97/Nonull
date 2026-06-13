"""
Tool & Skill registries — 工具与技能注册表 (Hermes Agent style).
Extracted from agent_core.py.

@module: core.registries
"""

import inspect
import logging
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Nonull.agent")

# ===================================================================
# 工具注册表 / Tool Registry  (Hermes Agent 风格)
# ===================================================================


class BaseTool(ABC):
    """
    工具基类 / Base Tool Class.

    所有可执行工具继承此类，自动注册到 ToolRegistry。
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    requires_safety_check: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower()

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """执行工具逻辑 / Execute tool logic."""
        ...

    def to_spec(self) -> Dict[str, Any]:
        """返回工具规范（用于 LLM 函数调用）/ Return tool spec for LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def __repr__(self) -> str:
        return f"<BaseTool name={self.name!r}>"


class ToolRegistry:
    """
    工具注册表 / Tool Registry.

    管理所有可用的工具，支持注册、注销、查找和批量执行。
    Hermes Agent 风格的工具管理。
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._lock = Lock()

    def register(self, tool: BaseTool) -> "ToolRegistry":
        """
        注册工具 / Register a tool.

        Args:
            tool: 工具实例

        Returns:
            self (支持链式调用)
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"工具必须继承 BaseTool: {type(tool)}")
        with self._lock:
            if tool.name in self._tools:
                logger.warning("工具 %s 已存在，将被覆盖", tool.name)
            self._tools[tool.name] = tool
            logger.debug("工具已注册: %s", tool.name)
        return self

    def unregister(self, name: str) -> bool:
        """注销工具 / Unregister a tool."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                return True
            return False

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具 / Get tool by name."""
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """列出所有工具名称 / List all tool names."""
        with self._lock:
            return sorted(self._tools.keys())

    def specs(self) -> List[Dict[str, Any]]:
        """返回所有工具的 LLM 规范 / Return spec list for LLM."""
        with self._lock:
            return [t.to_spec() for t in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> Any:
        """
        执行工具 / Execute a tool.

        Args:
            name:   工具名称
            **kwargs: 工具参数

        Returns:
            执行结果

        Raises:
            KeyError: 工具不存在
        """
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"工具不存在: {name} / Tool not found: {name}")
        logger.info("执行工具: %s | args=%s", name, kwargs)
        result = await tool.execute(**kwargs)
        logger.debug("工具结果 %s: %s", name, str(result)[:200])
        return result

    @property
    def count(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={list(self._tools.keys())}>"


# ===================================================================
# 技能注册表 / Skill Registry
# ===================================================================


class BaseSkill(ABC):
    """
    技能基类 / Base Skill Class.

    比工具更高层次的封装，可包含多个工具调用和推理逻辑。
    支持动态加载和卸载。
    """

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    dependencies: List[str] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower()

    @abstractmethod
    async def execute(self, context: Dict[str, Any], **kwargs: Any) -> Any:
        """执行技能 / Execute the skill."""
        ...

    def validate_context(self, context: Dict[str, Any]) -> bool:
        """验证上下文是否满足执行条件 / Validate context."""
        return True

    def __repr__(self) -> str:
        return f"<BaseSkill name={self.name!r} v{self.version}>"


class SkillRegistry:
    """
    技能注册表 / Skill Registry.

    管理技能的生命周期：注册、加载、卸载、执行。
    支持动态发现和依赖解析。
    """

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}
        self._lock = Lock()

    def register(self, skill) -> "SkillRegistry":
        """注册技能 / Register a skill.

        Accept both core.agent_core.BaseSkill and skills.base.BaseSkill
        (duck-type check instead of strict isinstance).
        """
        name = getattr(skill, 'name', None)
        if name is None or name == '':
            metadata = getattr(skill, 'metadata', None)
            if metadata is not None:
                name = getattr(metadata, 'name', None)

        if not name or not callable(getattr(skill, 'execute', None)):
            raise TypeError(f"技能必须有 name 和 execute: {type(skill)}")

        if not getattr(skill, 'name', None) and name:
            skill.name = name

        with self._lock:
            if name in self._skills:
                logger.warning("技能 %s 已存在，将被覆盖", name)
            self._skills[name] = skill
            logger.info("技能已注册: %s v%s", name, getattr(skill, 'version', '?'))
        return self

    def unregister(self, name: str) -> bool:
        """卸载技能 / Unregister a skill."""
        with self._lock:
            if name in self._skills:
                del self._skills[name]
                return True
            return False

    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        with self._lock:
            result = []
            for s in self._skills.values():
                name = getattr(s, 'name', '')
                if not name:
                    meta = getattr(s, 'metadata', None)
                    name = getattr(meta, 'name', '?') if meta else '?'
                result.append({
                    "name": name,
                    "version": getattr(s, 'version', '?'),
                    "description": getattr(s, 'description', ''),
                })
            return result

    async def execute(self, name: str, context: Dict[str, Any],
                      **kwargs: Any) -> Any:
        """执行技能 / Execute a skill (handles both sync and async)."""
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"技能不存在: {name}")
        if hasattr(skill, 'validate_context') and not skill.validate_context(context):
            raise ValueError(f"技能 {name} 上下文验证失败")
        logger.info("执行技能: %s", name)
        result = skill.execute(context, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    @property
    def count(self) -> int:
        return len(self._skills)

    def __contains__(self, name: object) -> bool:
        """Allow ``name in registry`` syntax."""
        return isinstance(name, str) and name in self._skills

    def __iter__(self):
        """Iterate over registered skills (yields BaseSkill instances)."""
        with self._lock:
            return iter(list(self._skills.values()))

    def __len__(self) -> int:
        return self.count

    def __repr__(self) -> str:
        return f"<SkillRegistry skills={list(self._skills.keys())}>"


__all__ = ["BaseTool", "ToolRegistry", "BaseSkill", "SkillRegistry"]
