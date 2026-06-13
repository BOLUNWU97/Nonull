"""
Subagent management — 子智能体管理 (isolation + lifecycle).
Extracted from agent_core.py.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional

# 本地导入
from .config import NonullConfig
from .errors import SubagentError

logger = logging.getLogger("Nonull.agent")


# ===================================================================
# 子智能体 / Subagent  (Claude Code 子智能体隔离)
# ===================================================================


@dataclass
class SubagentSpec:
    """
    子智能体规格 / Subagent Specification.

    Attributes:
        task:          子任务描述
        agent_type:    子智能体类型 (reasoning / acting / reflexion / data)
        config_override: 配置覆盖
        timeout:       超时时间（秒）
        isolation:     隔离级别
        parent_id:     父智能体 ID
    """
    task: str
    agent_type: str = "reasoning"
    config_override: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 120.0
    isolation: str = "process"
    parent_id: str = ""


@dataclass
class SubagentResult:
    """
    子智能体执行结果 / Subagent Execution Result.

    Attributes:
        subagent_id: 子智能体 ID
        success:     是否成功
        output:      输出内容
        error:       错误信息
        duration:    执行耗时（秒）
        state:       最终状态
        artifacts:   产物路径
    """
    subagent_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    state: str = "completed"
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subagent_id": self.subagent_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "state": self.state,
            "artifacts": self.artifacts,
        }


class SubagentManager:
    """
    子智能体管理器 / Subagent Manager.

    管理子智能体的生命周期：生成、监控、通信、回收。
    实现 Claude Code 风格的子进程隔离。
    """

    def __init__(self, config: Optional[NonullConfig] = None) -> None:
        cfg = config or NonullConfig.instance()
        self._max_children = cfg.get("subagent.max_children", 5)
        self._default_timeout = cfg.get("subagent.child_timeout_seconds", 120.0)
        self._isolation = cfg.get("subagent.isolation_level", "process")
        self._children: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    async def spawn(
        self,
        spec: SubagentSpec,
        parent_context: Optional[Dict[str, Any]] = None,
    ) -> SubagentResult:
        """
        生成子智能体 / Spawn a subagent.

        Args:
            spec:           子智能体规格
            parent_context: 父智能体上下文

        Returns:
            子智能体执行结果
        """
        subagent_id = f"sub_{uuid.uuid4().hex[:12]}"
        spec.parent_id = spec.parent_id or subagent_id

        # 检查容量
        with self._lock:
            if len(self._children) >= self._max_children:
                raise SubagentError(
                    f"子智能体数量已达上限 ({self._max_children})"
                )
            self._children[subagent_id] = {
                "id": subagent_id,
                "spec": spec,
                "status": "spawning",
                "started_at": time.time(),
            }

        timeout = spec.timeout or self._default_timeout
        start = time.time()

        logger.info(
            "生成子智能体: id=%s type=%s task=%s",
            subagent_id, spec.agent_type, spec.task[:80],
        )

        try:
            # 根据隔离级别执行
            if self._isolation == "thread":
                result = await self._run_in_thread(subagent_id, spec)
            else:
                # 默认在同一进程中隔离运行
                result = await self._run_in_process(subagent_id, spec)

            duration = time.time() - start

            output = SubagentResult(
                subagent_id=subagent_id,
                success=True,
                output=result,
                duration=duration,
                state="completed",
            )
            self._update_status(subagent_id, "completed")
            logger.info("子智能体完成: id=%s duration=%.2fs", subagent_id, duration)
            return output

        except asyncio.TimeoutError:
            duration = time.time() - start
            self._update_status(subagent_id, "timeout")
            logger.warning("子智能体超时: id=%s timeout=%.1fs", subagent_id, timeout)
            return SubagentResult(
                subagent_id=subagent_id,
                success=False,
                error=f"Timeout after {timeout}s",
                duration=duration,
                state="timeout",
            )

        except Exception as e:
            duration = time.time() - start
            self._update_status(subagent_id, "error")
            logger.exception("子智能体异常: id=%s", subagent_id)
            return SubagentResult(
                subagent_id=subagent_id,
                success=False,
                error=str(e),
                duration=duration,
                state="error",
            )

        finally:
            with self._lock:
                if subagent_id in self._children:
                    self._children[subagent_id]["ended_at"] = time.time()

    async def _run_in_thread(self, subagent_id: str, spec: SubagentSpec) -> Any:
        """在线程中运行子智能体 / Run subagent in thread."""
        loop = asyncio.get_event_loop()
        # 在线程池中运行
        return await loop.run_in_executor(
            None,
            self._execute_subagent_task,
            spec,
        )

    async def _run_in_process(self, subagent_id: str, spec: SubagentSpec) -> Any:
        """在进程中运行子智能体 / Run subagent in process."""
        # 当前实现为协程内直接执行，未来可通过 multiprocessing 实现进程隔离
        return await asyncio.wait_for(
            self._execute_subagent_task_async(spec),
            timeout=spec.timeout or self._default_timeout,
        )

    def _execute_subagent_task(self, spec: SubagentSpec) -> Any:
        """同步执行子智能体任务 / Execute subagent task synchronously."""
        # 占位实现 - 实际项目中接入 LLM 调用
        return {
            "status": "simulated",
            "task": spec.task,
            "agent_type": spec.agent_type,
            "result": f"Simulated result for: {spec.task[:50]}",
        }

    async def _execute_subagent_task_async(self, spec: SubagentSpec) -> Any:
        """异步执行子智能体任务 / Execute subagent task asynchronously."""
        # 占位实现 - 实际项目中接入 LLM 调用链
        await asyncio.sleep(0.1)  # 模拟计算
        return {
            "status": "simulated_async",
            "task": spec.task,
            "agent_type": spec.agent_type,
            "result": f"Async simulated result for: {spec.task[:50]}",
        }

    def _update_status(self, subagent_id: str, status: str) -> None:
        with self._lock:
            if subagent_id in self._children:
                self._children[subagent_id]["status"] = status

    def get_child(self, subagent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._children.get(subagent_id)

    def list_children(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": c["id"],
                    "type": c["spec"].agent_type,
                    "status": c["status"],
                    "task": c["spec"].task[:60],
                }
                for c in self._children.values()
            ]

    def cleanup(self) -> int:
        """清理已完成的子智能体 / Clean up completed children."""
        with self._lock:
            before = len(self._children)
            self._children = {
                k: v for k, v in self._children.items()
                if v.get("status") not in ("completed", "error", "timeout")
            }
            return before - len(self._children)

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for c in self._children.values()
                if c.get("status") in ("spawning", "running")
            )


__all__ = ["SubagentSpec", "SubagentResult", "SubagentManager"]
