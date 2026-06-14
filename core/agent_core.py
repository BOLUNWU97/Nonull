"""
ADVISORY SAFETY — The deny-first validation and risk-scoring code
(SafetyGuardian, now in core/safety.py; re-exported here) is an ADVISORY
software gate. Risk scores and the
"max_risk_score" threshold are developer-configured heuristics, NOT certified
ISO 26262 ASIL-D (or any ASIL) classifications. The "deny-first" label is
borrowed from Claude Code's security pattern, not from a certified safety
process. See README §Disclaimer and `safety.disclaimer: advisory_only` in
config.

Nonull - 主智能体循环 (Main Agent Loop)
================================================

融合架构核心 (Fusion Architecture Core):
  - OpenClaw: Gateway/Agents/Channels 三层, SOUL identity, Nexus+Tendrils
  - Hermes Agent: Provider-agnostic, tool registry, profile isolation, session persistence
  - openHuman: Neocortex memory (working/episodic/semantic/procedural), subconscious loop
  - Claude Code: Deny-first safety, hook system, subagent isolation, compaction

状态机 (State Machine):
  IDLE → PLANNING → REASONING → ACTING → REFLECTING → COMPLETED
                                    ↓                    ↑
                                 ERROR → RECOVERING → REFLECTING

@module: core.agent_core
"""

import asyncio
import json
import logging
import os
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# 本地导入
from .config import NonullConfig
from .cost_tracker import CostTracker, BudgetExceeded

logger = logging.getLogger("Nonull.agent")

# ===================================================================
# 常量 / Constants
# ===================================================================

DEFAULT_SESSION_DIR = os.path.join(os.path.expanduser("~"), ".Nonull", "sessions")


class _StepFailed:
    """步骤失败哨兵 / Sentinel marking a failed step in the run loop.

    _safe_execute_step 返回此哨兵（而非抛出异常）以便主循环 continue。
    Returned by _safe_execute_step instead of raising, so the run loop
    can continue with the state already set (RECOVERING→REASONING or ERROR).
    """
    __slots__ = ()

    def __repr__(self) -> str:
        return "<STEP_FAILED>"

    def __bool__(self) -> bool:
        return False


_STEP_FAILED = _StepFailed()

# ===================================================================
# 模块化重构 / Modular refactor (2026-06)
# 以下类已抽取到独立模块，此处 re-export 保持向后兼容。
# These classes were extracted into dedicated modules; re-exported
# here so `from core.agent_core import X` keeps working.
# ===================================================================

from .states import AgentState
from .errors import (
    NonullError,
    SafetyViolation,
    RecoveryFailedError,
    SubagentError,
    HookExecutionError,
)
from .safety import SafetyGuardian
# 单条记忆类 + 4 个简化记忆层 (core.memory_legacy):仅作 ImportError 兜底。
# Single-entry memory classes + 4 simplified memory layers (core.memory_legacy):
# ImportError fallback only.
from .memory_legacy import (
    MemoryEntry,
    BaseMemory,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
)
# MemorySystem 指向完整实现 (Neocortex + SubconsciousLoop),与 Nonull 实例
# 实际使用的版本一致。legacy 聚合器仍可经 core.memory_legacy.MemorySystem 显式获取。
# MemorySystem points at the full implementation (Neocortex + SubconsciousLoop),
# matching what the Nonull instance actually uses. The legacy aggregator remains
# reachable via core.memory_legacy.MemorySystem explicitly.
from .memory_system import MemorySystem
from .registries import BaseTool, ToolRegistry, BaseSkill, SkillRegistry
from .subagents import SubagentSpec, SubagentResult, SubagentManager
from .hooks import HookPoint, HookRegistry


# ===================================================================
# 主智能体 / Main Agent
# ===================================================================


class Nonull:
    """
    Nonull - 自动驾驶AI智能体核心类
    ========================================

    融合架构核心 (Fusion Architecture Core):
      - OpenClaw: 三层智能体架构
      - Hermes Agent: 配置档隔离 + 工具注册表
      - openHuman: 新皮层记忆 + 潜意识循环
      - Claude Code: 拒绝优先安全 + 钩子系统 + 子智能体隔离

    状态机 (State Machine):
      IDLE → PLANNING → REASONING → ACTING → REFLECTING → COMPLETED
                                        ↓                    ↑
                                     ERROR → RECOVERING → REFLECTING

    双语文档 / Bilingual Documentation:
      所有公共方法同时包含中文和英文 docstring。
      代码注释以中文为主，关键术语附英文。

    Usage::
        agent = Nonull()
        result = await agent.run("Analyze traffic situation at intersection A")
        status = agent.get_status()
        agent.save_state("./checkpoint.json")
    """

    def __init__(
        self,
        config: Optional[NonullConfig] = None,
        session_id: Optional[str] = None,
        name: str = "Nonull",
    ) -> None:
        """
        初始化智能体 / Initialize agent.

        Args:
            config:     配置实例（自动使用默认配置）
            session_id: 会话 ID（自动生成）
            name:       智能体名称
        """
        # ── 配置 / Configuration ──
        self._config = config or NonullConfig.instance()
        self._name: str = name
        self._session_id: str = session_id or f"session_{uuid.uuid4().hex[:12]}"

        # ── 状态 / State ──
        self._state: AgentState = AgentState.IDLE
        self._previous_state: Optional[AgentState] = None
        self._current_task: str = ""
        self._iteration: int = 0
        self._max_iterations: int = self._config.get("agent.max_iterations", 50)
        self._timeout: float = self._config.get("agent.timeout_seconds", 300.0)
        self._recovery_attempts: int = self._config.get("agent.recovery_attempts", 3)
        self._error_count: int = 0
        self._started_at: Optional[float] = None

        # ── 安全 / Safety ──
        self._safety: SafetyGuardian = SafetyGuardian(self._config)

        # ── 记忆 / Memory ──
        # 优先使用 memory/ 包的完整 Neocortex 后端；如果不可用，回退到简化版
        try:
            from .memory_system import MemorySystem as _FullMemorySystem
            self._memory: MemorySystem = _FullMemorySystem(self._config)
        except ImportError:
            # core.memory_system 不可用时回退到轻量 legacy 实现
            # Fall back to the lightweight legacy MemorySystem if the full
            # memory_system module (Neocortex + SubconsciousLoop) cannot import.
            from .memory_legacy import MemorySystem as _LegacyMemorySystem
            self._memory = _LegacyMemorySystem(self._config)

        # ── 工具 / Tools ──
        self._tool_registry: ToolRegistry = ToolRegistry()

        # ── 技能 / Skills ──
        self._skill_registry: SkillRegistry = SkillRegistry()

        # ── 子智能体 / Subagents ──
        self._subagent_mgr: SubagentManager = SubagentManager(self._config)

        # ── 钩子 / Hooks ──
        self._hooks: HookRegistry = HookRegistry()

        # ── 成本追踪 / Cost tracking ──
        self._cost_tracker: CostTracker = CostTracker()

        # ── LLM Client (optional, for real agent mode) ──
        # 本地导入 LLM client（不在顶层导入以避免不必要的依赖）
        from .llm_client import LLMClient, LLMConfig, LLMMessage
        # 用 LLMConfig.from_env() 加载 .env + NONULL_LLM_* 环境变量。
        # 它正确处理 NONULL_LLM_API_BASE 等 (NonullConfig 不自动加载 .env,
        # 且用不同的 env 变量名后缀, 导致 Nonull() 拿不到 key)。
        # NonullConfig 的显式设置可覆盖。
        # Load via LLMConfig.from_env() (auto-loads .env + NONULL_LLM_* vars);
        # NonullConfig does not auto-load .env. Explicit config overrides.
        llm_cfg = LLMConfig.from_env()
        if self._config.get("llm.api_key", ""):
            llm_cfg.api_key = self._config.get("llm.api_key")
        if self._config.get("llm.base_url", ""):
            llm_cfg.base_url = self._config.get("llm.base_url")
        # 仅当 NonullConfig 显式配置了非默认模型时才覆盖 from_env() 的结果。
        # NonullConfig 不区分 "显式设置" 与 "schema 默认值" (llm.model 默认 'gpt-4o'),
        # 若无条件覆盖会把 from_env() 从 .env 加载的正确模型 (如 MiniMax-M3)
        # 回写为过时默认 'gpt-4o'。
        # Only override the model when NonullConfig was explicitly given a
        # non-default model; NonullConfig does not distinguish explicit values
        # from schema defaults (llm.model defaults to 'gpt-4o'), so a blind
        # override would clobber the correct model loaded from .env by from_env().
        _DEFAULT_LLM_MODEL = "gpt-4o"
        _cfg_model = self._config.get("llm.model", "")
        if _cfg_model and _cfg_model != _DEFAULT_LLM_MODEL:
            llm_cfg.model = _cfg_model
        if llm_cfg.api_key:
            self._llm_client: Optional[LLMClient] = LLMClient(llm_cfg)
        else:
            self._llm_client = None
        # ── Enhancements (optional, for consciousness/evolution integration) ──
        self._enhancements: Optional[Any] = None

        # ── 运行上下文 / Execution context ──
        self._context: Dict[str, Any] = {
            "session_id": self._session_id,
            "config_snapshot": self._config.snapshot().all(),
            "started_at": None,
            "task_history": [],
            "action_history": [],
            "reflection_history": [],
        }

        # ── 步骤历史 / Step history ──
        self._steps: List[Dict[str, Any]] = []

        # ── 异步锁 / Async lock ──
        self._lock = asyncio.Lock()

        # ── 日志 / Logging ──
        self._setup_logging()

        logger.info(
            "Nonull 已初始化 | name=%s session=%s state=%s",
            self._name, self._session_id, self._state.value,
        )

    # ─────────────────────────────────────────────────────────────
    # 属性 / Properties
    # ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> AgentState:
        """当前状态 / Current state."""
        return self._state

    @property
    def session_id(self) -> str:
        """会话 ID / Session ID."""
        return self._session_id

    @property
    def name(self) -> str:
        """智能体名称 / Agent name."""
        return self._name

    @property
    def memory(self) -> MemorySystem:
        """记忆系统引用 / Memory system reference."""
        return self._memory

    @property
    def safety(self) -> SafetyGuardian:
        """安全监护器引用 / Safety guardian reference."""
        return self._safety

    @property
    def tools(self) -> ToolRegistry:
        """工具注册表引用 / Tool registry reference."""
        return self._tool_registry

    @property
    def skills(self) -> SkillRegistry:
        """技能注册表引用 / Skill registry reference."""
        return self._skill_registry

    @property
    def hooks(self) -> HookRegistry:
        """钩子注册表引用 / Hook registry reference."""
        return self._hooks

    @property
    def llm_client(self) -> Optional["LLMClient"]:
        """LLM client reference (None if not configured)."""
        return self._llm_client

    # ─────────────────────────────────────────────────────────────
    # System Prompt Builder
    # ─────────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """构建系统提示词 / Build system prompt (output contract + stop conditions).

        v2 (2026-06): 输出契约 + 停止条件 + 修正 tool/skill 指令 bug。
        技能/工具不再硬塞 system prompt (省 token), 改由 plan/reason 按需注入。
        """
        return (
            "You are Nonull, a domain-agnostic task-execution agent.\n"
            "You operate in a REASON → ACT → REFLECT loop until a task is complete.\n"
            "\n"
            "OUTPUT CONTRACT (violations trigger retry):\n"
            "  - Output ONLY a single valid JSON object per turn.\n"
            "  - Start with { and end with }. No prose, no markdown fences, nothing outside the JSON.\n"
            "  - Double-quote all strings. No trailing commas, no comments.\n"
            "\n"
            "STOP CONDITIONS — finish (call \"complete\") when ANY is true:\n"
            "  - The task deliverable is produced and verified.\n"
            "  - You have retried the same action 3+ times without progress.\n"
            "  - A required tool/skill does not exist and cannot be substituted.\n"
            "\n"
            "ACTION PREFIXES (exact — 'tool:' takes a TOOL name, 'skill:' takes a SKILL name):\n"
            "  - 'complete'                  finish the task\n"
            "  - 'text:<output>'             free-text output\n"
            "  - 'skill:<skill_name> k=v'    call a registered SKILL\n"
            "  - 'tool:<tool_name> k=v'      call a registered TOOL\n"
            "\n"
            "SAFETY: You are an advisory development assistant, NOT a certified safety\n"
            "system. Never claim ASIL-D / ISO 26262 compliance. Flag uncertain outputs.\n"
            "Match the user's language (Chinese or English)."
        )

    def _parse_llm_json(self, text: str, fallback: Dict[str, Any] = None) -> Dict[str, Any]:
        """解析 LLM 输出为 JSON, 容错降级 / Parse LLM output as JSON, gracefully degrade.

        使用 structured_output.extract_json (处理 markdown ```json 块、裸 JSON、
        多 JSON 对象), 比本地贪婪正则更健壮。失败返回 fallback 或最小兜底。
        Uses structured_output.extract_json (handles markdown blocks, bare JSON,
        multiple objects) — more robust than a local greedy regex.
        """
        from .structured_output import extract_json
        parsed = extract_json(text) if text else None
        if isinstance(parsed, dict):
            return parsed
        if fallback:
            logger.warning(
                "JSON 解析失败, 使用 fallback / parse failed, using fallback: %s",
                (text or "")[:80],
            )
            return fallback
        return {"raw": text, "parsed": False}

    # ─────────────────────────────────────────────────────────────
    # LLM 调用辅助 / LLM call helpers (unified chat + cost + parse)
    # ─────────────────────────────────────────────────────────────

    @property
    def cost_tracker(self) -> CostTracker:
        """成本追踪器（只读）/ The cost tracker (read-only)."""
        return self._cost_tracker

    def _record_llm_cost(self, response: Any) -> None:
        """记录一次 LLM 调用成本 (best-effort) / Record an LLM call's cost.

        记账失败绝不影响 agent 主流程; 预算超限只告警不中断。
        Cost tracking never breaks the main loop; budget breach only warns.
        """
        try:
            usage = getattr(response, "usage", None)
            if not usage:
                return
            # response.model 是权威来源 (LLMClient 的 config 存于私有 _config)
            # response.model is authoritative; LLMClient holds config privately
            model = getattr(response, "model", None) or "unknown"
            self._cost_tracker.record(
                model,
                getattr(response, "prompt_tokens", 0),
                getattr(response, "completion_tokens", 0),
            )
        except BudgetExceeded:
            logger.warning("LLM 成本预算超限 / cost budget exceeded")
        except Exception:
            # 记账失败绝不上抛 / never let cost tracking break the loop
            logger.debug("cost tracking skipped", exc_info=True)

    def _llm_chat_and_parse(
        self,
        messages: List[Any],
        max_tokens: int,
        fallback: Dict[str, Any],
        json_mode: bool = True,
    ) -> Dict[str, Any]:
        """统一 LLM 调用 + 成本记账 + JSON 解析 / Unified LLM call + cost + parse.

        消除 plan/reason/reflect 三处重复的 chat→parse 模式, 同时记账成本。
        默认 json_mode=True 强约束 JSON 输出 (OpenAI 兼容端点 response_format)。
        Eliminates the repeated chat→parse pattern while recording cost.
        json_mode defaults True to force valid JSON output.
        """
        response = self._llm_client.chat(messages, max_tokens=max_tokens, json_mode=json_mode)
        self._record_llm_cost(response)
        return self._parse_llm_json(response.content, fallback=fallback)

    # ─────────────────────────────────────────────────────────────
    # 主入口 / Main Entry Point
    # ─────────────────────────────────────────────────────────────

    async def run(
        self,
        task_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        主入口：运行智能体处理任务 / Main entry: run agent to process a task.

        完整的 ReAct + Plan-and-Execute + Reflexion 循环：
          1. PLAN:    分解任务为子步骤
          2. REASON:  基于当前状态和记忆推理
          3. ACT:     通过安全监护执行动作
          4. REFLECT: 反思结果并更新记忆
          5. 循环 1-4 直到完成或超时

        Args:
            task_input: 任务描述 / Task description
            context:    可选的初始上下文 / Optional initial context

        Returns:
            {
                "status":     最终状态,
                "output":     最终输出,
                "steps":      执行步骤,
                "iterations": 迭代次数,
                "duration":   总耗时（秒）,
                "error":      错误信息（如有）
            }
        """
        async with self._lock:
            if self._state not in (AgentState.IDLE, AgentState.COMPLETED, AgentState.ERROR):
                return {
                    "status": self._state.value,
                    "error": f"智能体正在运行中 (当前状态: {self._state.value})",
                }

            self._reset_for_new_task(task_input, context)
            self._set_state(AgentState.PLANNING)

        # 总计时
        overall_start = time.time()

        try:
            while self._iteration < self._max_iterations:
                self._iteration += 1
                logger.info(
                    "=== 迭代 %d/%d | 状态: %s | 任务: %s ===",
                    self._iteration, self._max_iterations,
                    self._state.value, self._current_task[:60],
                )

                # ── 1) PLANNING ────────────────────────────────
                if self._state == AgentState.PLANNING:
                    plan = await self._safe_execute_step(
                        self.plan, self._current_task
                    )
                    if plan is _STEP_FAILED:
                        continue  # 状态已被设置为 REASONING(重试) 或 ERROR(终止)
                    self._context["plan"] = plan
                    self._set_state(AgentState.REASONING)

                # ── 2) REASONING ──────────────────────────────
                elif self._state == AgentState.REASONING:
                    reason_result = await self._safe_execute_step(
                        self.reason, self._context
                    )
                    if reason_result is _STEP_FAILED:
                        continue
                    self._context["reasoning"] = reason_result
                    self._set_state(AgentState.ACTING)

                # ── 3) ACTING ─────────────────────────────────
                elif self._state == AgentState.ACTING:
                    action = self._context.get("reasoning", {}).get("next_action", "")
                    if not action:
                        action = "complete"
                    act_result = await self._safe_execute_step(
                        self.act, action, self._context
                    )
                    if act_result is _STEP_FAILED:
                        continue
                    self._context["last_result"] = act_result
                    self._context["action_history"].append({
                        "iteration": self._iteration,
                        "action": action,
                        "result": act_result,
                    })
                    self._set_state(AgentState.REFLECTING)

                # ── 4) REFLECTING ─────────────────────────────
                elif self._state == AgentState.REFLECTING:
                    reflection = await self._safe_execute_step(
                        self.reflect, self._context
                    )
                    if reflection is _STEP_FAILED:
                        continue
                    self._context["reflection_history"].append({
                        "iteration": self._iteration,
                        "reflection": reflection,
                    })

                    # 判断是否完成
                    if reflection.get("completed", False):
                        self._set_state(AgentState.COMPLETED)
                        break
                    else:
                        # 继续循环：回到推理阶段
                        self._set_state(AgentState.REASONING)

                # ── 5) COMPLETED / ERROR ──────────────────────
                else:
                    break

                # 超时检查
                if time.time() - overall_start > self._timeout:
                    logger.warning("任务超时 (%.1fs)", self._timeout)
                    self._set_state(AgentState.ERROR)
                    self._context["error"] = f"Task timeout after {self._timeout}s"
                    break

            # 循环结束
            if self._state not in (AgentState.COMPLETED, AgentState.ERROR):
                if self._iteration >= self._max_iterations:
                    self._set_state(AgentState.COMPLETED)
                    self._context["output"] = "Max iterations reached, forced completion"

        except Exception as e:
            logger.exception("运行异常 / Runtime error")
            self._set_state(AgentState.ERROR)
            self._context["error"] = str(e)

        finally:
            duration = time.time() - overall_start
            async with self._lock:
                self._context["duration"] = duration

            # 钩子: 关闭
            await self._hooks.execute(HookPoint.ON_SHUTDOWN, context=self._context)

            logger.info(
                "任务完成 | state=%s iterations=%d duration=%.2fs",
                self._state.value, self._iteration, duration,
            )

        return {
            "status": self._state.value,
            "output": self._context.get("output"),
            "plan": self._context.get("plan"),
            "steps": len(self._steps),
            "iterations": self._iteration,
            "duration": duration,
            "error": self._context.get("error"),
        }

    # ─────────────────────────────────────────────────────────────
    # 核心步骤 / Core Steps
    # ─────────────────────────────────────────────────────────────

    async def plan(self, task: str) -> Dict[str, Any]:
        """
        规划阶段：分解任务为可执行的子步骤 / Plan: decompose task into executable steps.

        Uses real LLM to generate structured subtasks. Falls back to simulated
        planning if LLM client is not configured.
        """
        await self._hooks.execute(HookPoint.PRE_PLAN, context={"task": task})
        from .llm_client import LLMMessage

        # 检索相关的语义记忆和程序性记忆
        similar_tasks = self._memory.semantic.retrieve(task, k=3)
        procedures = self._memory.procedural.retrieve(task, k=2)

        # 构建规划上下文
        plan_context = {
            "task": task,
            "similar_past_tasks": [str(e.content)[:200] for e in similar_tasks],
            "available_procedures": [str(e.content)[:200] for e in procedures],
            "available_skills": self._skill_registry.list_skills(),
            "available_tools": self._tool_registry.list_tools(),
        }

        # === Real LLM-powered planning ===
        plan_data = {}
        if self._llm_client:
            try:
                system_prompt = self._build_system_prompt()
                relevant_tools = plan_context["available_tools"][:10]
                relevant_skills = [s["name"] for s in plan_context["available_skills"][:10]]
                user_prompt = (
                    f"TASK: {task}\n\n"
                    f"Past similar tasks: {[t[:80] for t in plan_context['similar_past_tasks']]}\n"
                    f"Available tools: {relevant_tools}\n"
                    f"Available skills: {relevant_skills}\n\n"
                    "Decompose into 2-5 subtasks. Each subtask must be independently verifiable.\n"
                    "Return ONLY:\n"
                    '{"subtasks": [{"id": "s1", "description": "<verb + object>", '
                    '"verify": "<how to check it is done>", "tool": "<tool_name or null>"}], '
                    '"strategy": "sequential", "estimated_steps": <int>}\n\n'
                    "Rules:\n"
                    "- 'description' must start with a verb (analyze, generate, check, ...).\n"
                    "- 'verify' is mandatory — state the success check, not 'done'.\n"
                    "- 'tool' must be a real name from the list, or null.\n"
                    "- 'strategy' must be exactly 'sequential' or 'parallel'."
                )

                plan_data = self._llm_chat_and_parse(
                    [
                        LLMMessage(role="system", content=system_prompt),
                        LLMMessage(role="user", content=user_prompt),
                    ],
                    max_tokens=2048,
                    fallback={"subtasks": [], "strategy": "sequential", "estimated_steps": 1},
                )

                subtasks = plan_data.get("subtasks", [])
                if not subtasks:
                    subtasks = self._fallback_plan(task)
                    logger.warning("LLM returned empty subtasks, using fallback")

            except Exception as e:
                logger.warning("LLM planning failed (%s), using fallback", e)
                subtasks = self._fallback_plan(task)
        else:
            # No LLM: use fallback simulation
            subtasks = self._fallback_plan(task)

        plan_result = {
            "task": task,
            "subtasks": subtasks,
            "strategy": plan_data.get("strategy", "plan_and_execute"),
            "estimated_steps": len(subtasks),
            "context": plan_context,
        }

        # 存储到工作记忆
        self._memory.working.store(
            plan_result, metadata={"type": "plan"}, importance=0.8
        )

        await self._hooks.execute(HookPoint.POST_PLAN, context=plan_result)
        logger.info("规划完成: %d 个子步骤 (LLM=%s)", len(subtasks), bool(self._llm_client))
        return plan_result

    async def reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        推理阶段：基于当前状态决定下一步动作 / Reason: decide next action based on state.

        Uses real LLM for ReAct-style reasoning. Falls back to simulated reasoning
        if LLM client is not configured.
        """
        await self._hooks.execute(HookPoint.PRE_REASON, context=context)
        from .llm_client import LLMMessage

        # 获取记忆上下文
        mem_context = self._memory.get_context(
            query=context.get("task", ""), k=3
        )

        # 构建推理输入
        reasoning_input = {
            "task": self._current_task,
            "plan": context.get("plan"),
            "last_result": str(context.get("last_result", ""))[:500],
            "last_action": str(context.get("action_history", [None])[-1])[-200:] if context.get("action_history") else None,
            "reflections": [str(r.get("reflection", ""))[-200:] for r in context.get("reflection_history", [])[-3:]],
            "working_memory": [str(e.content)[:100] for e in mem_context.get("working", [])],
            "episodic_memory": [str(e.content)[:500] for e in mem_context.get("episodic", [])],
            "semantic_knowledge": [str(e.content)[:500] for e in mem_context.get("semantic", [])],
            "available_skills": self._skill_registry.list_skills(),
            "available_tools": self._tool_registry.list_tools(),
            "iteration": self._iteration,
        }

        # 循环检测: 最近连续相同动作数 / loop detection (consecutive dup actions)
        action_history = context.get("action_history", [])
        dup_count = 0
        if action_history:
            last_act = action_history[-1].get("action", "")
            for a in reversed(action_history):
                if last_act and a.get("action") == last_act:
                    dup_count += 1
                else:
                    break

        # === Real LLM-powered reasoning ===
        if self._llm_client:
            try:
                near_limit = reasoning_input["iteration"] > self._max_iterations * 0.7
                user_prompt = (
                    f"TASK: {reasoning_input['task']}\n"
                    f"ITERATION: {reasoning_input['iteration']}/{self._max_iterations}"
                    f"{'  (WARNING: near iteration limit — wrap up)' if near_limit else ''}\n"
                    f"LAST ACTION: {reasoning_input['last_action']}\n"
                    f"LAST RESULT: {reasoning_input['last_result']}\n"
                    f"DUPLICATE ACTION COUNT: {dup_count}"
                    f"{'  (YOU ARE LOOPING — must change approach or complete)' if dup_count >= 2 else ''}\n"
                    f"Relevant past experience (episodic memory): {reasoning_input['episodic_memory'][:2]}\n"
                    f"Relevant knowledge (semantic memory): {reasoning_input['semantic_knowledge'][:2]}\n"
                    f"Recent reflections: {reasoning_input['reflections'][:2]}\n"
                    f"Plan: {json.dumps(reasoning_input['plan'], ensure_ascii=False)[:400] if reasoning_input['plan'] else 'None'}\n\n"
                    "Choose the next action. Return ONLY:\n"
                    '{"next_action": "<complete | text:<output> | skill:<name> k=v | tool:<name> k=v>", '
                    '"reasoning": "<1 sentence why>", "confidence": <0.0-1.0>, '
                    '"subtask_id": "<subtask this advances, or null>"}\n\n'
                    "Decision rules:\n"
                    "- If all subtasks verified AND output produced -> \"complete\".\n"
                    "- If DUPLICATE ACTION COUNT >= 3 -> you MUST pick \"complete\" or a different tool.\n"
                    "- 'tool:' is followed by a TOOL name; 'skill:' by a SKILL name.\n"
                    "- Never repeat an action you already tried this run."
                )

                system_prompt = (
                    "Reasoning turn. Follow the OUTPUT CONTRACT (single JSON object). "
                    "Pick exactly one action; avoid repeating prior actions."
                )

                reason_result = self._llm_chat_and_parse(
                    [
                        LLMMessage(role="system", content=system_prompt),
                        LLMMessage(role="user", content=user_prompt),
                    ],
                    max_tokens=2048,
                    fallback={
                        "next_action": "text:Proceeding with analysis step.",
                        "reasoning": "Fallback reasoning",
                        "confidence": 0.5,
                    },
                )

            except Exception as e:
                logger.warning("LLM reasoning failed (%s), using fallback", e)
                reason_result = {
                    "next_action": "text:Proceeding with analysis step.",
                    "reasoning": f"Fallback reasoning due to LLM error: {e}",
                    "confidence": 0.3,
                }
        else:
            # No LLM: use fallback simulation
            reason_result = self._fallback_reason(reasoning_input)

        await self._hooks.execute(HookPoint.POST_REASON, context=reason_result)
        logger.debug("推理结果: action=%s confidence=%.2f", reason_result.get("next_action"), reason_result.get("confidence", 0))
        return reason_result

    async def act(self, action: str, context: Dict[str, Any]) -> Any:
        """
        执行阶段：通过安全监护执行动作 / Act: execute action through safety guardian.

        所有动作在执行前都必须经过 Safety Guardian 的校验。

        Args:
            action:  要执行的动作描述
            context: 当前上下文

        Returns:
            执行结果

        Raises:
            SafetyViolation: 动作被安全系统拒绝
        """
        # 钩子: 执行前
        await self._hooks.execute(HookPoint.PRE_ACT, context={"action": action})

        # 安全校验 (Deny-first)
        is_safe, risk, reason = self._safety.validate(action, context)
        await self._hooks.execute(
            HookPoint.POST_SAFETY_CHECK,
            context={"action": action, "safe": is_safe, "risk": risk, "reason": reason},
        )

        if not is_safe:
            logger.warning("安全拦截: %s (risk=%.2f, reason=%s)", action, risk, reason)
            self._memory.store_experience(
                self._current_task, action,
                {"safety_blocked": True, "reason": reason}, success=False,
            )
            raise SafetyViolation(action=action, reason=reason, risk_score=risk)

        # 执行动作
        try:
            result = await self._execute_action(action, context)
        except Exception as e:
            logger.exception("动作执行失败: %s", action)
            self._memory.store_experience(
                self._current_task, action, {"error": str(e)}, success=False,
            )
            raise

        # 记录到情景记忆
        self._memory.store_experience(self._current_task, action, result, success=True)

        # 钩子: 执行后
        await self._hooks.execute(HookPoint.POST_ACT, context={"action": action, "result": result})

        logger.info("动作执行成功: %s", action[:80])
        return result

    async def reflect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        反思阶段：评估结果并改进策略 (Reflexion 模式) / Reflect: evaluate and improve.

        Uses real LLM for honest self-assessment. Falls back to heuristic evaluation
        if LLM client is not configured.
        """
        await self._hooks.execute(HookPoint.PRE_REFLECT, context=context)
        from .llm_client import LLMMessage

        last_result = context.get("last_result", {})
        action_history = context.get("action_history", [])
        plan = context.get("plan", {})

        reflection_input = {
            "task": self._current_task,
            "plan": str(plan)[:500],
            "action_history": [f"iter {a.get('iteration', '?')}: {a.get('action', '')}" for a in action_history[-5:]],
            "last_result": str(last_result)[:500],
            "iterations_used": self._iteration,
            "max_iterations": self._max_iterations,
        }

        # === Real LLM-powered reflection ===
        if self._llm_client:
            try:
                near_limit = reflection_input["iterations_used"] >= reflection_input["max_iterations"] * 0.9
                user_prompt = (
                    f"TASK: {reflection_input['task']}\n"
                    f"Plan: {reflection_input['plan']}\n"
                    f"Actions taken ({len(reflection_input['action_history'])}):\n" +
                    "\n".join(f"  - {a}" for a in reflection_input['action_history'][-3:]) +
                    f"\nLast result: {reflection_input['last_result'][:300]}\n"
                    f"Iterations used: {reflection_input['iterations_used']}/{reflection_input['max_iterations']}"
                    f"{'  (AT LIMIT — set completed=true now)' if near_limit else ''}\n\n"
                    "Evaluate honestly. Return ONLY:\n"
                    '{"completed": <bool>, "summary": "<2 sentences>", '
                    '"verified_subtasks": ["<ids>"], "blockers": ["<specific obstacle> or []], '
                    '"score": <0.0-1.0>, "next_hint": "<if not completed, what to try next>"}\n\n'
                    "Decision rules:\n"
                    "- 'completed': true ONLY if the deliverable is produced and checkable.\n"
                    "- If not completed, 'next_hint' is mandatory.\n"
                    "- If at iteration limit, set completed=true (score reflects actual quality)."
                )

                reflection = self._llm_chat_and_parse(
                    [
                        LLMMessage(role="system", content="Reflection turn. Follow the OUTPUT CONTRACT. Be honest about gaps; do not claim completion unless the deliverable exists."),
                        LLMMessage(role="user", content=user_prompt),
                    ],
                    max_tokens=2048,
                    fallback={
                        "completed": len(action_history) >= 3,
                        "summary": f"Executed {len(action_history)} actions.",
                        "issues": [],
                        "improvements": [],
                        "score": min(1.0, len(action_history) / 5),
                    },
                )

            except Exception as e:
                logger.warning("LLM reflection failed (%s), using fallback", e)
                reflection = {
                    "completed": len(action_history) >= 3,
                    "summary": f"LLM failed: {e}",
                    "issues": [str(e)],
                    "score": 0.3,
                }
        else:
            # No LLM: use fallback simulation
            reflection = self._fallback_reflection(reflection_input)

        # 如果反思发现重要经验，存入语义记忆
        if reflection.get("score", 0.5) < 0.3 or reflection.get("issues"):
            self._memory.semantic.store(
                {
                    "type": "reflection_insight",
                    "task": self._current_task,
                    "issues": reflection.get("issues"),
                    "improvements": reflection.get("improvements"),
                },
                importance=0.8,
            )

        await self._hooks.execute(HookPoint.POST_REFLECT, context=reflection)
        logger.info(
            "反思完成: completed=%s score=%.2f issues=%d",
            reflection.get("completed"), reflection.get("score", 0),
            len(reflection.get("issues", [])),
        )
        return reflection

    # ─────────────────────────────────────────────────────────────
    # 子智能体 / Subagent
    # ─────────────────────────────────────────────────────────────

    async def spawn_subagent(
        self,
        task: str,
        agent_type: str = "reasoning",
        config_override: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> SubagentResult:
        """
        生成子智能体处理子任务 / Spawn subagent for subtask.

        Claude Code 风格的子智能体隔离执行。

        Args:
            task:            子任务描述
            agent_type:      子智能体类型 (reasoning / acting / reflexion / data)
            config_override: 配置覆盖（如不同的模型参数）
            timeout:         超时时间（秒）

        Returns:
            子智能体执行结果
        """
        prev_state = self._state
        self._set_state(AgentState.SPAWNING)
        try:
            spec = SubagentSpec(
                task=task,
                agent_type=agent_type,
                config_override=config_override or {},
                timeout=timeout or 120.0,
                parent_id=self._session_id,
            )

            await self._hooks.execute(
                HookPoint.PRE_SPAWN,
                context={"spec": spec, "parent": self._session_id},
            )

            parent_ctx = {
                "session_id": self._session_id,
                "task": self._current_task,
                "context": self._context,
            }
            result = await self._subagent_mgr.spawn(spec, parent_ctx)

            await self._hooks.execute(
                HookPoint.POST_SPAWN,
                context={"result": result},
            )

            logger.info(
                "子智能体完成: %s type=%s success=%s",
                result.subagent_id, agent_type, result.success,
            )
            return result

        finally:
            self._set_state(prev_state if prev_state != AgentState.SPAWNING else AgentState.REASONING)

    # ─────────────────────────────────────────────────────────────
    # 状态管理 / State Management
    # ─────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体当前状态 / Get current agent status.

        Returns:
            包含状态、会话、任务、进度等信息的字典
        """
        # ── 记忆大小 / Memory sizes (适配新旧后端) ──
        try:
            memory_sizes = {
                "working": self._memory.working.context_window.get_item_count(),
                "episodic": len(self._memory.episodic.episodes) if self._memory.episodic else 0,
                "semantic": len(self._memory.semantic.nodes) if self._memory.semantic else 0,
                "procedural": len(self._memory.procedural.skills) if self._memory.procedural else 0,
            }
        except Exception:
            memory_sizes = {"working": 0, "episodic": 0, "semantic": 0, "procedural": 0}

        return {
            "state": self._state.value,
            "previous_state": self._previous_state.value if self._previous_state else None,
            "session_id": self._session_id,
            "name": self._name,
            "current_task": self._current_task,
            "iteration": self._iteration,
            "max_iterations": self._max_iterations,
            "error_count": self._error_count,
            "started_at": self._started_at,
            "duration": time.time() - self._started_at if self._started_at else 0,
            "memory_sizes": memory_sizes,
            "tools_available": self._tool_registry.count,
            "skills_available": self._skill_registry.count,
            "subagents_active": self._subagent_mgr.active_count,
            "hooks_registered": sum(
                len(v) for v in self._hooks.list_hooks().values()
            ),
            "safety_violations": self._safety.violation_count,
            "backend_memory": getattr(self._memory, "backend_name", "unknown"),
            "cost": self._cost_tracker.summary(),
        }

    def _set_state(self, new_state: AgentState) -> None:
        """
        设置新状态并触发钩子 / Set new state and fire hook.

        Args:
            new_state: 目标状态
        """
        self._previous_state = self._state
        self._state = new_state
        logger.debug(
            "状态变更: %s -> %s",
            self._previous_state.value if self._previous_state else "None",
            new_state.value,
        )
        # 触发状态变更钩子 (不等待)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._hooks.execute(
                    HookPoint.ON_STATE_CHANGE,
                    context={
                        "from": self._previous_state.value if self._previous_state else None,
                        "to": new_state.value,
                        "agent": self._name,
                    },
                )
            )
        except RuntimeError:
            pass

    # ─────────────────────────────────────────────────────────────
    # 持久化 / Persistence  (Hermes Agent 风格)
    # ─────────────────────────────────────────────────────────────

    async def save_state(self, path: Optional[str] = None) -> str:
        """
        保存智能体状态到磁盘 / Save agent state to disk.

        序列化当前状态、记忆、上下文和步骤历史。

        Args:
            path: 保存路径（默认 ~/.Nonull/sessions/<session_id>.json）

        Returns:
            保存的文件路径
        """
        path = path or os.path.join(
            DEFAULT_SESSION_DIR, f"{self._session_id}.json"
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # 记忆持久化: 优先用 Neocortex 完整序列化 (working/episodic/semantic/procedural)
        # 注意: 必须用 neocortex.to_dict() (完整四层), 而非 self._memory.to_dict()
        # (后者只返回 stats)。之前用错了, 导致记忆从未真正持久化。
        # Memory: use full Neocortex serialization (4 layers), NOT
        # MemorySystem.to_dict() (which only returns stats).
        memory_data = None
        neocortex = getattr(self._memory, "neocortex", None)
        if neocortex is not None and hasattr(neocortex, "to_dict"):
            try:
                memory_data = neocortex.to_dict()
            except Exception as e:
                logger.warning("Neocortex 序列化失败, 跳过记忆持久化 / serialize failed: %s", e)

        state_data = {
            "version": "0.1.0",
            "session_id": self._session_id,
            "name": self._name,
            "state": self._state.value,
            "current_task": self._current_task,
            "iteration": self._iteration,
            "max_iterations": self._max_iterations,
            "error_count": self._error_count,
            "started_at": self._started_at,
            "context": self._sanitize_for_serialization(self._context),
            "steps": self._sanitize_for_serialization(self._steps),
            "memory": memory_data,
            "saved_at": time.time(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info("状态已保存: %s (%d bytes)", path, os.path.getsize(path))
        return path

    async def load_state(self, path: str) -> bool:
        """
        从磁盘加载智能体状态 / Load agent state from disk.

        Args:
            path: 状态文件路径

        Returns:
            是否成功加载
        """
        if not os.path.isfile(path):
            logger.error("状态文件不存在: %s", path)
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            self._session_id = state_data.get("session_id", self._session_id)
            self._name = state_data.get("name", self._name)
            self._state = AgentState(state_data.get("state", "idle"))
            self._current_task = state_data.get("current_task", "")
            self._iteration = state_data.get("iteration", 0)
            self._max_iterations = state_data.get("max_iterations", 50)
            self._error_count = state_data.get("error_count", 0)
            self._started_at = state_data.get("started_at")
            self._context = state_data.get("context", self._context)
            self._steps = state_data.get("steps", [])

            # 恢复记忆: 优先用 Neocortex 完整重建 (含索引), 兼容旧格式逐条 store
            # Restore memory: prefer full Neocortex rebuild (with index);
            # fall back to legacy per-entry store for old save formats.
            memory_data = state_data.get("memory")
            if isinstance(memory_data, dict) and "working" in memory_data and "episodic" in memory_data:
                try:
                    from memory import Neocortex
                    restored = Neocortex.from_dict(memory_data)
                    if hasattr(self._memory, "neocortex"):
                        self._memory.neocortex = restored
                        logger.info("Neocortex 记忆已恢复 (完整重建) / memory restored (full rebuild)")
                except Exception as e:
                    logger.warning("Neocortex 恢复失败, 记忆可能不完整 / restore failed: %s", e)
            elif isinstance(memory_data, dict):
                # 旧格式兼容: 逐条 store / legacy format: per-entry store
                for layer in ("working", "episodic"):
                    for entry_data in memory_data.get(layer, []):
                        try:
                            self._memory.store(
                                entry_data["content"],
                                memory_type=layer,
                                metadata=entry_data.get("metadata"),
                                importance=entry_data.get("importance", 0.5),
                            )
                        except Exception:
                            pass

            logger.info("状态已加载: %s (session=%s)", path, self._session_id)
            return True

        except Exception as e:
            logger.exception("状态加载失败: %s", path)
            return False

    # ─────────────────────────────────────────────────────────────
    # 注册 / Registration helpers
    # ─────────────────────────────────────────────────────────────

    def register_tool(self, tool: BaseTool) -> "Nonull":
        """注册工具 / Register a tool."""
        self._tool_registry.register(tool)
        return self

    def register_skill(self, skill: BaseSkill) -> "Nonull":
        """注册技能 / Register a skill."""
        self._skill_registry.register(skill)
        return self

    def register_hook(
        self,
        hook_point: HookPoint,
        handler: Callable[..., Any],
        name: Optional[str] = None,
        priority: int = 100,
    ) -> "Nonull":
        """注册钩子 / Register a hook."""
        self._hooks.register(hook_point, handler, name=name, priority=priority)
        return self

    def allow_command(self, command: str) -> "Nonull":
        """添加安全白名单命令 / Add command to safety allowlist."""
        self._safety.allow_command(command)
        return self

    # ─────────────────────────────────────────────────────────────
    # 内部方法 / Internal Methods
    # ─────────────────────────────────────────────────────────────

    def _reset_for_new_task(
        self, task: str, context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """重置为新任务 / Reset for new task."""
        self._current_task = task
        self._iteration = 0
        self._error_count = 0
        self._started_at = time.time()
        self._steps = []
        self._context = {
            "session_id": self._session_id,
            "config_snapshot": self._config.snapshot().all(),
            "started_at": self._started_at,
            "task": task,
            "plan": None,
            "reasoning": None,
            "last_result": None,
            "action_history": [],
            "reflection_history": [],
            "error": None,
            "output": None,
            **(context or {}),
        }
        # 清空工作记忆但保留情景/语义
        self._memory.working.clear()
        # 记录新任务到情景记忆
        self._memory.episodic.store(
            {"event": "task_start", "task": task, "timestamp": self._started_at},
            importance=0.6,
        )
        logger.info("新任务开始: %s", task[:100])

    async def _safe_execute_step(
        self, step_fn: Callable[..., Any], *args: Any, **kwargs: Any,
    ) -> Any:
        """
        安全执行单步，带错误处理和恢复 / Safely execute a single step.

        失败时返回 _STEP_FAILED 哨兵值（而非抛出异常），调用方应检查哨兵并
        continue 主循环 —— 状态已由本方法设置（RECOVERING→REASONING 重试,
        或 ERROR 终止）。
        On failure returns the _STEP_FAILED sentinel instead of raising, so the
        run loop can continue: state has already been set to REASONING (retry)
        or ERROR (give up) by this method.

        Args:
            step_fn: 步骤函数
            *args, **kwargs: 传递给步骤函数的参数

        Returns:
            步骤执行结果，或失败时返回 _STEP_FAILED / Step result or _STEP_FAILED
        """
        try:
            if asyncio.iscoroutinefunction(step_fn):
                return await step_fn(*args, **kwargs)
            else:
                return step_fn(*args, **kwargs)
        except SafetyViolation as e:
            logger.warning("步骤被安全系统拦截: %s", e)
            self._error_count += 1
            self._context["error"] = str(e)
            self._context["last_safety_violation"] = {
                "action": e.action,
                "reason": e.reason,
                "risk_score": e.risk_score,
            }
            if self._error_count >= self._recovery_attempts:
                self._set_state(AgentState.ERROR)
            else:
                self._set_state(AgentState.RECOVERING)
                await self._attempt_recovery(e)
            return _STEP_FAILED

        except (NonullError, asyncio.TimeoutError) as e:
            logger.error("步骤执行失败: %s", e)
            self._error_count += 1
            self._context["error"] = str(e)
            if self._error_count >= self._recovery_attempts:
                self._set_state(AgentState.ERROR)
            else:
                self._set_state(AgentState.RECOVERING)
                await self._attempt_recovery(e)
            return _STEP_FAILED

        except Exception as e:
            logger.exception("步骤未预期异常: %s", e)
            self._error_count += 1
            self._context["error"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            if self._error_count >= self._recovery_attempts:
                self._set_state(AgentState.ERROR)
            else:
                self._set_state(AgentState.RECOVERING)
                await self._attempt_recovery(e)
            return _STEP_FAILED

    def _diagnose_failure(self, error: Exception) -> Optional[Dict[str, Any]]:
        """用 LLM 诊断失败原因, 决定恢复策略 / Diagnose a failure to guide recovery.

        替代盲回 REASONING: 先判断错误瞬时还是永久, 决定重试/换路/放弃。
        Replaces the blind REASONING fallback: classify the error and decide
        retry / try-alternative / give-up. Returns None if LLM unavailable.
        """
        if not self._llm_client:
            return None
        try:
            from .llm_client import LLMMessage
            last_action = ""
            hist = self._context.get("action_history") or []
            if hist:
                last_action = str(hist[-1].get("action", ""))
            user_prompt = (
                "A step just FAILED. Diagnose before retrying.\n\n"
                f"FAILED ACTION: {last_action[:200]}\n"
                f"ERROR: {str(error)[:300]}\n"
                f"ATTEMPT: {self._error_count}/{self._recovery_attempts}\n\n"
                "Return ONLY:\n"
                '{"diagnosis": "<root cause, 1 sentence>", "should_retry": <bool>, '
                '"alternative_action": "<different next_action or null>", '
                '"adjustment": "<what to change>"}\n\n'
                "Rules:\n"
                "- 'should_retry': false for permanent errors (auth, missing tool, invalid input).\n"
                "- 'alternative_action' must DIFFER from the failed action.\n"
                "- After 2+ failed retries, prefer should_retry=false."
            )
            return self._llm_chat_and_parse(
                [
                    LLMMessage(role="system", content="Failure diagnosis turn. Follow the OUTPUT CONTRACT. Be decisive."),
                    LLMMessage(role="user", content=user_prompt),
                ],
                max_tokens=256,
                fallback={
                    "diagnosis": "diagnosis unavailable",
                    "should_retry": True,
                    "alternative_action": None,
                    "adjustment": None,
                },
            )
        except Exception as e:
            logger.debug("failure diagnosis skipped: %s", e)
            return None

    async def _attempt_recovery(self, error: Exception) -> bool:
        """
        尝试从错误中恢复 / Attempt recovery from error.

        Args:
            error: 发生的异常

        Returns:
            恢复是否成功
        """
        if self._error_count > self._recovery_attempts:
            logger.warning(
                "恢复次数已耗尽 (%d/%d)，放弃恢复 / Recovery attempts exhausted",
                self._error_count, self._recovery_attempts,
            )
            return False

        logger.info(
            "尝试恢复 (attempt %d/%d)...",
            self._error_count, self._recovery_attempts,
        )
        # 记录错误到情景记忆
        try:
            self._memory.episodic.store(
                {
                    "event": "recovery_attempt",
                    "error": str(error),
                    "attempt": self._error_count,
                    "state": self._previous_state.value if self._previous_state else None,
                },
                importance=0.9,
            )
        except Exception:
            pass
        # RECOVERING 诊断: 先分析错误再决定恢复策略 (替代盲回 REASONING)
        # Diagnose before retrying — replaces the blind REASONING fallback.
        diagnosis = self._diagnose_failure(error)
        if diagnosis and not diagnosis.get("should_retry", True):
            logger.warning(
                "恢复诊断建议放弃 / diagnosis advises giving up: %s",
                str(diagnosis.get("diagnosis", ""))[:120],
            )
            return False
        if diagnosis and diagnosis.get("alternative_action"):
            self._context["recovery_hint"] = diagnosis
        # 回到推理阶段重试
        self._set_state(AgentState.REASONING)
        return True

    async def _execute_action(self, action: str, context: Dict[str, Any]) -> Any:
        """
        执行具体动作 / Execute concrete action.

        根据动作描述决定是调用工具、执行命令还是返回结果。

        Args:
            action:  动作描述
            context: 上下文

        Returns:
            动作结果
        """
        # 记录步骤
        self._steps.append({
            "iteration": self._iteration,
            "action": action,
            "timestamp": time.time(),
        })

        # 解析动作类型
        if action.startswith("tool:"):
            # 工具调用: tool:tool_name arg1=val1 arg2=val2
            parts = action[5:].strip().split(maxsplit=1)
            tool_name = parts[0]
            tool_args = {}
            if len(parts) > 1:
                # 简单参数解析 (生产环境应使用结构化格式)
                for arg_part in parts[1].split():
                    if "=" in arg_part:
                        k, v = arg_part.split("=", 1)
                        tool_args[k] = v
            return await self._tool_registry.execute(tool_name, **tool_args)

        elif action.startswith("text:"):
            # 文本输出: text:<自由文本> — 这是智能体产出最终交付物的主要途径。
            # 之前 text: 动作落入通用 else 分支, 文本从未写入 context["output"],
            # 导致 run() 返回的 output 永远为空。
            # text:<free text> — the primary way the agent emits a deliverable.
            # Previously text: actions fell through to the generic else and the
            # text was never written to context["output"], so run() always
            # returned output=None.
            output_text = action[len("text:"):].strip()
            self._context["output"] = output_text
            return {"status": "text_output", "output": output_text}

        elif action.startswith("skill:"):
            # 技能调用: skill:skill_name key=val ...
            parts = action[6:].strip().split(maxsplit=1)
            skill_name = parts[0]
            skill_args = {}
            if len(parts) > 1:
                for arg_part in parts[1].split():
                    if "=" in arg_part:
                        k, v = arg_part.split("=", 1)
                        skill_args[k] = v
            return await self._skill_registry.execute(skill_name, context, **skill_args)

        elif action == "complete":
            # 完成
            return {"status": "completed", "message": "Task completed by agent decision"}

        else:
            # 通用动作（生产环境应接入 LLM 调用）
            return {
                "status": "executed",
                "action": action,
                "message": f"Action executed: {action[:100]}",
            }

    def _fallback_plan(self, task: str) -> List[Dict[str, Any]]:
        """
        Fallback task plan when LLM is not available.
        当 LLM 不可用时使用的备用任务计划。
        """
        return [
            {
                "id": f"step_{i}",
                "description": f"Analyze: {task[:50]}",
                "dependencies": [] if i == 1 else [f"step_{i-1}"],
                "skill_or_tool": None,
            }
            for i in range(1, 4)
        ]

    def _fallback_reason(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback reasoning when LLM is not available."""
        task = input_data.get("task", "")
        last_result = input_data.get("last_result")

        if last_result and str(last_result).find("completed") != -1:
            return {
                "next_action": "complete",
                "reasoning": "Task appears completed based on last result.",
                "confidence": 0.9,
            }

        # 查找是否有可用的工具
        skills = input_data.get("available_skills", [])
        if skills:
            skill = skills[0]
            return {
                "next_action": f"skill:{skill['name']}",
                "reasoning": f"Using skill {skill['name']} to process task.",
                "confidence": 0.7,
            }

        return {
            "next_action": f"text:Analyzing: {task[:50]}",
            "reasoning": "Proceeding with text analysis step.",
            "confidence": 0.6,
        }

    def _fallback_reflection(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback reflection when LLM is not available."""
        action_count = len(input_data.get("action_history", []))
        return {
            "completed": action_count >= 3,
            "summary": f"Executed {action_count} actions.",
            "issues": [] if action_count < 5 else ["Too many iterations"],
            "improvements": ["Optimize tool selection"] if action_count > 3 else [],
            "score": min(1.0, action_count / 5),
        }

    def _setup_logging(self) -> None:
        """配置日志 / Setup logging."""
        log_level = self._config.get("observability.log_level", "INFO")
        log_file = self._config.get("observability.log_file", "")

        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        if log_file:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            fh.setFormatter(formatter)
            logger.addHandler(fh)

    @staticmethod
    def _sanitize_for_serialization(obj: Any) -> Any:
        """清理对象以便序列化 / Sanitize object for serialization."""
        if isinstance(obj, dict):
            return {k: Nonull._sanitize_for_serialization(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [Nonull._sanitize_for_serialization(v) for v in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

    # ─────────────────────────────────────────────────────────────
    # 同步入口 / Synchronous Entry
    # ─────────────────────────────────────────────────────────────

    def run_sync(
        self,
        task: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Execute a task by calling the LLM synchronously.

        Returns a dict with keys:
          - 'output': the LLM's response text
          - 'model': the model used
          - 'usage': token usage dict
          - 'duration_ms': how long the call took
          - 'task': the original task

        Falls back to a "no LLM configured" message if api_key is empty.
        """
        import time
        from core.llm_client import LLMClient, LLMConfig, LLMMessage

        start = time.time()
        cfg = LLMConfig.from_env()
        if not cfg.api_key:
            return {
                "output": (
                    "[Nonull] LLM not configured. Set NONULL_LLM_API_KEY to enable the agent.\n"
                    "Other channels (slash commands, skills, scenarios) still work."
                ),
                "model": "none",
                "usage": {},
                "duration_ms": 0.0,
                "task": task,
                "status": "no_llm",
            }

        client = LLMClient(cfg)
        sys_prompt = system_prompt or (
            "You are Nonull, a domain-agnostic AI agent assistant. "
            "You have access to 31+ domain skills across multiple verticals (ADAS, "
            "general programming, data analysis, etc.). When asked to perform a task, "
            "decide which skills to use and explain your reasoning. "
            "ADVISORY: you are a development assistant, not a certified safety system. "
            "Always suggest the user verify critical outputs."
        )

        try:
            resp = client.simple_chat(
                user_message=task,
                system_message=sys_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            return {
                "output": f"[Nonull] LLM call failed: {type(e).__name__}: {e}",
                "model": cfg.model,
                "usage": {},
                "duration_ms": (time.time() - start) * 1000,
                "task": task,
                "status": "error",
            }

        return {
            "output": resp,
            "model": cfg.model,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},  # filled in by client
            "duration_ms": (time.time() - start) * 1000,
            "task": task,
            "status": "ok",
        }

    def __repr__(self) -> str:
        return (
            f"<Nonull name={self._name!r} "
            f"session={self._session_id[:12]} "
            f"state={self._state.value} "
            f"iteration={self._iteration}>"
        )
