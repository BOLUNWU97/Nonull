"""
Base Skill Framework - 基础技能框架

定义技能系统的核心抽象基类、元数据模型和结果类型。
Defines the core abstract base class, metadata model, and result types for the skill system.
"""

from __future__ import annotations

import abc
import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 技能类别枚举 / Skill Category Enum
# =============================================================================


class SkillCategory(str, enum.Enum):
    """技能分类 / Skill classification."""

    CODE = "code"                     # 代码审查优化 / Code review & optimization
    PERCEPTION = "perception"         # 感知算法 / Perception algorithms
    PLANNING = "planning"             # 规划决策 / Planning & decision
    TESTING = "testing"               # 测试验证 / Testing & validation
    SAFETY = "safety"                 # 功能安全 / Functional safety
    SIMULATION = "simulation"         # 仿真模拟 / Simulation
    DATA = "data"                     # 数据处理 / Data processing
    RESEARCH = "research"             # 学术研究 / Academic research
    DEVOPS = "devops"                 # 运维部署 / DevOps & deployment
    GENERAL = "general"               # 通用技能 / General purpose


# =============================================================================
# 技能元数据 / Skill Metadata
# =============================================================================


@dataclass
class SkillMetadata:
    """
    技能元数据，记录技能的基本信息。
    Skill metadata recording basic information about a skill.

    Attributes:
        name:            技能唯一标识名 / Unique skill name
        version:         版本号 (semver) / Version string (semver)
        category:        技能分类 / Skill category
        description:     功能描述 / Functional description
        author:          作者 / Author
        tags:            标签列表 / Tags for search
        requires:        依赖的其他技能名列表 / Required skill names
        input_schema:    JSON Schema 定义输入格式 / Input JSON schema
        output_schema:   JSON Schema 定义输出格式 / Output JSON schema
        max_execution_ms:最大执行时间(毫秒) / Max execution time in ms
        safety_level:    安全等级 1-5 / Safety level 1-5
    """

    name: str
    version: str = "1.0.0"
    category: SkillCategory = SkillCategory.GENERAL
    description: str = ""
    author: str = "Nonull"
    tags: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    max_execution_ms: int = 30000
    safety_level: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """将元数据转为字典 / Serialize metadata to dict."""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category.value,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "requires": self.requires,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "max_execution_ms": self.max_execution_ms,
            "safety_level": self.safety_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillMetadata":
        """从字典恢复元数据 / Deserialize metadata from dict."""
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            category=SkillCategory(data.get("category", "general")),
            description=data.get("description", ""),
            author=data.get("author", "Nonull"),
            tags=data.get("tags", []),
            requires=data.get("requires", []),
            input_schema=data.get("input_schema"),
            output_schema=data.get("output_schema"),
            max_execution_ms=data.get("max_execution_ms", 30000),
            safety_level=data.get("safety_level", 1),
        )


# =============================================================================
# 技能结果 / Skill Result
# =============================================================================


@dataclass
class SkillMetrics:
    """
    技能执行指标 / Skill execution metrics.

    Attributes:
        start_time:      开始时间戳 / Start timestamp (epoch ms)
        end_time:        结束时间戳 / End timestamp (epoch ms)
        duration_ms:     执行耗时(毫秒) / Duration in milliseconds
        cpu_usage:       CPU 使用率 / CPU usage estimate
        memory_usage:    内存使用量(KB) / Memory usage in KB
        call_count:      调用次数 / Number of calls
    """

    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    call_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "call_count": self.call_count,
        }


@dataclass
class SkillResult:
    """
    技能执行结果 / Skill execution result.

    Attributes:
        success:       是否成功 / Whether execution succeeded
        data:          执行输出数据 / Execution output data
        error:         错误信息(失败时) / Error message (on failure)
        metrics:       执行性能指标 / Performance metrics
        safety_score:  安全评分 0.0-1.0 / Safety score 0.0-1.0
        warnings:      警告列表 / Warning messages
        skill_name:    执行该结果的技能名 / Name of the skill executed
    """

    success: bool = True
    data: Any = None
    error: Optional[str] = None
    metrics: SkillMetrics = field(default_factory=SkillMetrics)
    safety_score: float = 1.0
    warnings: List[str] = field(default_factory=list)
    skill_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """将结果转为字典 / Serialize result to dict."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metrics": self.metrics.to_dict(),
            "safety_score": self.safety_score,
            "warnings": self.warnings,
            "skill_name": self.skill_name,
        }

    @classmethod
    def failure(
        cls,
        error: str,
        skill_name: str = "",
        warnings: Optional[List[str]] = None,
    ) -> "SkillResult":
        """快速创建失败结果 / Quickly create a failure result."""
        return cls(
            success=False,
            error=error,
            skill_name=skill_name,
            warnings=warnings or [],
            safety_score=0.0,
        )

    @classmethod
    def success_result(
        cls,
        data: Any = None,
        skill_name: str = "",
        safety_score: float = 1.0,
        warnings: Optional[List[str]] = None,
    ) -> "SkillResult":
        """快速创建成功结果 / Quickly create a success result."""
        return cls(
            success=True,
            data=data,
            skill_name=skill_name,
            safety_score=safety_score,
            warnings=warnings or [],
        )


# =============================================================================
# 技能异常 / Skill Exception
# =============================================================================


class SkillException(Exception):
    """
    技能执行过程中的基础异常。
    Base exception for skill execution errors.
    """

    def __init__(
        self,
        message: str,
        skill_name: str = "",
        error_code: str = "SKILL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.skill_name = skill_name
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class SkillValidationError(SkillException):
    """输入/输出验证失败 / Input/output validation failure."""
    def __init__(self, message: str, skill_name: str = ""):
        super().__init__(message, skill_name, "VALIDATION_ERROR")


class SkillTimeoutError(SkillException):
    """技能执行超时 / Skill execution timeout."""
    def __init__(self, message: str, skill_name: str = ""):
        super().__init__(message, skill_name, "TIMEOUT_ERROR")


class SkillSafetyError(SkillException):
    """安全验证失败 / Safety validation failure."""
    def __init__(self, message: str, skill_name: str = ""):
        super().__init__(message, skill_name, "SAFETY_ERROR")


# =============================================================================
# 基础技能抽象类 / Base Skill Abstract Class
# =============================================================================

ContextType = Dict[str, Any]
HookFunc = Callable[[ContextType], Optional[ContextType]]


class BaseSkill(abc.ABC):
    """
    所有技能的抽象基类。
    Abstract base class for all skills.

    生命周期 / Lifecycle:
        __init__ -> activate() -> [pre_execute -> execute -> post_execute]* -> deactivate()

    使用示例 / Usage:
        class MySkill(BaseSkill):
            @property
            def metadata(self) -> SkillMetadata:
                return SkillMetadata(name="my_skill", category=SkillCategory.GENERAL)

            def _execute_impl(self, context: ContextType) -> Any:
                return {"result": "processed"}
    """

    def __init__(self):
        # 技能唯一实例ID / Unique instance ID
        self._instance_id: str = uuid.uuid4().hex[:12]
        # 激活状态 / Activation state
        self._active: bool = False
        # 性能指标累加器 / Performance metrics accumulator
        self._metrics: SkillMetrics = SkillMetrics()
        # 前置钩子 / Pre-execution hooks
        self._pre_hooks: List[HookFunc] = []
        # 后置钩子 / Post-execution hooks
        self._post_hooks: List[HookFunc] = []
        # 安全验证钩子 / Safety validation hooks
        self._safety_hooks: List[HookFunc] = []
        # 日志记录器 / Logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"Skill initialized: {self.__class__.__name__} [{self._instance_id}]")

    # -------------------------------------------------------------------------
    # 子类必须实现的抽象属性 / Abstract property subclasses must implement
    # -------------------------------------------------------------------------

    @property
    @abc.abstractmethod
    def metadata(self) -> SkillMetadata:
        """返回技能元数据 / Return skill metadata."""
        ...

    # -------------------------------------------------------------------------
    # 生命周期管理 / Lifecycle Management
    # -------------------------------------------------------------------------

    def activate(self) -> None:
        """
        激活技能，进行初始化资源配置。
        Activate the skill, initializing resources.
        """
        if self._active:
            self.logger.warning(f"Skill {self.metadata.name} already active.")
            return
        self._active = True
        self._metrics.call_count = 0
        self.logger.info(
            f"Skill activated: {self.metadata.name} v{self.metadata.version}"
        )

    def deactivate(self) -> None:
        """
        停用技能，释放资源。
        Deactivate the skill, releasing resources.
        """
        if not self._active:
            return
        self._active = False
        self.logger.info(
            f"Skill deactivated: {self.metadata.name} "
            f"(total calls: {self._metrics.call_count})"
        )

    @property
    def is_active(self) -> bool:
        """技能是否已激活 / Whether the skill is active."""
        return self._active

    @property
    def instance_id(self) -> str:
        """技能实例唯一ID / Unique instance ID."""
        return self._instance_id

    # -------------------------------------------------------------------------
    # 钩子管理 / Hook Management
    # -------------------------------------------------------------------------

    def add_pre_hook(self, hook: HookFunc) -> None:
        """添加前置执行钩子 / Add a pre-execution hook."""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: HookFunc) -> None:
        """添加后置执行钩子 / Add a post-execution hook."""
        self._post_hooks.append(hook)

    def add_safety_hook(self, hook: HookFunc) -> None:
        """添加安全验证钩子 / Add a safety validation hook."""
        self._safety_hooks.append(hook)

    def clear_hooks(self) -> None:
        """清除所有钩子 / Clear all hooks."""
        self._pre_hooks.clear()
        self._post_hooks.clear()
        self._safety_hooks.clear()

    # -------------------------------------------------------------------------
    # 核心执行方法 / Core Execute Method
    # -------------------------------------------------------------------------

    def execute(self, context: ContextType) -> SkillResult:
        """
        执行技能（包含完整的生命周期、钩子、计时和验证）。
        Execute the skill with full lifecycle, hooks, timing, and validation.

        Args:
            context: 执行上下文字典 / Execution context dictionary.

        Returns:
            SkillResult: 执行结果 / Execution result.
        """
        skill_name = self.metadata.name

        # 安全检查 / Safety check
        if not self._active:
            return SkillResult.failure(
                error=f"Skill '{skill_name}' is not activated. Call activate() first.",
                skill_name=skill_name,
            )

        # 输入验证 / Input validation
        try:
            self._validate_input(context)
        except SkillValidationError as e:
            self.logger.error(f"Input validation failed: {e}")
            return SkillResult.failure(
                error=str(e), skill_name=skill_name
            )

        # 初始化指标 / Initialize metrics
        metrics = SkillMetrics(
            start_time=time.time() * 1000,
            call_count=self._metrics.call_count + 1,
        )
        self._metrics.call_count += 1
        warnings: List[str] = []
        safety_score: float = 1.0

        try:
            # 前置钩子 / Pre-execution hooks
            ctx = context
            for hook in self._pre_hooks:
                result = hook(ctx)
                if result is not None:
                    ctx = result

            # 安全验证钩子 / Safety validation hooks
            for hook in self._safety_hooks:
                result = hook(ctx)
                if result is not None and isinstance(result, dict):
                    score = result.get("safety_score", 1.0)
                    if score < 0.5:
                        raise SkillSafetyError(
                            f"Safety hook rejected execution (score={score})",
                            skill_name=skill_name,
                        )
                    safety_score = min(safety_score, score)
                    if result.get("warnings"):
                        warnings.extend(result["warnings"])

            # 执行超时监控 / Execution with timeout monitoring
            start_real = time.time()
            data = self._execute_with_timeout(ctx)
            elapsed_ms = (time.time() - start_real) * 1000

            # 更新指标 / Update metrics
            metrics.end_time = time.time() * 1000
            metrics.duration_ms = elapsed_ms

            # 输出验证 / Output validation
            self._validate_output(data)

            # 后置钩子 / Post-execution hooks
            for hook in self._post_hooks:
                result = hook({"context": ctx, "result": data})
                if result is not None and isinstance(result, dict):
                    if "warnings" in result:
                        warnings.extend(result["warnings"])

            self.logger.info(
                f"Skill '{skill_name}' executed successfully in {elapsed_ms:.1f}ms"
            )

            return SkillResult(
                success=True,
                data=data,
                metrics=metrics,
                safety_score=safety_score,
                warnings=warnings,
                skill_name=skill_name,
            )

        except SkillTimeoutError as e:
            self.logger.error(f"Skill '{skill_name}' timed out: {e}")
            return SkillResult.failure(error=str(e), skill_name=skill_name)

        except SkillSafetyError as e:
            self.logger.error(f"Skill '{skill_name}' safety violation: {e}")
            return SkillResult.failure(error=str(e), skill_name=skill_name)

        except SkillValidationError as e:
            self.logger.error(f"Skill '{skill_name}' output validation failed: {e}")
            return SkillResult.failure(error=str(e), skill_name=skill_name)

        except Exception as e:
            self.logger.exception(
                f"Skill '{skill_name}' unexpected error: {e}"
            )
            return SkillResult.failure(
                error=f"Unexpected error: {e}",
                skill_name=skill_name,
                warnings=warnings,
            )

    # -------------------------------------------------------------------------
    # 子类必须实现的核心逻辑 / Core Logic Subclasses Must Implement
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    def _execute_impl(self, context: ContextType) -> Any:
        """
        技能的核心执行逻辑。
        Core execution logic of the skill.

        Args:
            context: 执行上下文 / Execution context.

        Returns:
            执行结果数据 / Execution result data.
        """
        ...

    # -------------------------------------------------------------------------
    # 可选的验证方法 / Optional Validation Methods
    # -------------------------------------------------------------------------

    def _validate_input(self, context: ContextType) -> None:
        """
        验证输入上下文。子类可覆盖。
        Validate the input context. Subclasses may override.
        """
        pass

    def _validate_output(self, data: Any) -> None:
        """
        验证输出数据。子类可覆盖。
        Validate the output data. Subclasses may override.
        """
        pass

    # -------------------------------------------------------------------------
    # 内部方法 / Internal Methods
    # -------------------------------------------------------------------------

    def _execute_with_timeout(self, context: ContextType) -> Any:
        """
        带超时控制的执行（简单实现，Python GIL 下为粗略超时）。
        Execute with timeout control (simple approach).

        生产环境建议使用 multiprocessing 或 asyncio 实现精确超时。
        For production, consider multiprocessing or asyncio for precise timeout.
        """
        max_ms = self.metadata.max_execution_ms
        if max_ms <= 0:
            return self._execute_impl(context)

        import threading

        result_container: list = []
        error_container: list = []
        completed = threading.Event()

        def target():
            try:
                res = self._execute_impl(context)
                result_container.append(res)
            except Exception as e:
                error_container.append(e)
            finally:
                completed.set()

        thread = threading.Thread(target=target, daemon=True)
        thread.start()

        if not completed.wait(timeout=max_ms / 1000.0):
            raise SkillTimeoutError(
                f"Skill '{self.metadata.name}' exceeded max execution time "
                f"{max_ms}ms",
                skill_name=self.metadata.name,
            )

        if error_container:
            raise error_container[0]

        return result_container[0]

    # -------------------------------------------------------------------------
    # 工具方法 / Utility Methods
    # -------------------------------------------------------------------------

    def get_metrics(self) -> SkillMetrics:
        """获取技能执行指标 / Get execution metrics."""
        return self._metrics

    def reset_metrics(self) -> None:
        """重置指标 / Reset metrics."""
        self._metrics = SkillMetrics()
        self._metrics.call_count = 0

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"name={self.metadata.name!r} "
            f"active={self._active} "
            f"calls={self._metrics.call_count}>"
        )
