"""
Agent Loop — 标准 agentic 循环 / Standard agentic loop.

Agent Loop 模式: LLM + system prompt + tools 在一个 while 循环里, LLM 完全
控制流程。每一步: LLM 推理 → 选择工具 (或给出最终答案) → 执行工具 → 观察
结果 → 重复, 直到 LLM 给出最终答案 (无 tool_call) 或达到 max_steps。

这是与 Nonull.run() 的结构化五阶段循环 (plan/reason/act/reflect) 互补的
另一种模式: 更纯粹、工具为中心、LLM 完全掌控控制流 —— 即业界所说的
"agent = while loop + tools" (ReAct: Reason → Act → Observe)。

The agentic-loop pattern: an LLM, a system prompt, and tools inside a while
loop where the model controls the flow. Each step the LLM reasons, picks a
tool (or gives a final answer), executes it, observes the result, and loops
until it returns a final answer (no tool_call) or hits max_steps. This
complements Nonull.run()'s structured 5-phase loop with a purer, tool-centric
ReAct loop where the LLM fully owns control flow.

@module: core.agent_loop
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("Nonull.agent_loop")

DEFAULT_SYSTEM_PROMPT = (
    "You are an autonomous agent operating in a loop. You have tools available. "
    "Each turn, EITHER call a tool to make progress OR give your final answer. "
    "When the task is complete, respond with the final answer and DO NOT call any "
    "tool — that signals the loop to terminate. Reason briefly before each action."
)


@dataclass
class LoopStep:
    """单步循环记录 / A single step of the agent loop."""
    step: int
    thought: str          # LLM 推理 (assistant content) / LLM reasoning
    action: str           # 'tool:<name>' 或 'final' / tool invoked or 'final'
    observation: str      # 工具结果或最终答案 / tool result or final answer

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "thought": self.thought[:200],
            "action": self.action,
            "observation": self.observation[:200],
        }


@dataclass
class AgentLoopResult:
    """Agent Loop 运行结果 / Result of an agent loop run."""
    output: str                              # 最终答案 / final answer
    steps: List[LoopStep] = field(default_factory=list)
    completed: bool = False                  # True=LLM 自然终止, False=max_steps 截断
    tool_calls: int = 0
    error: Optional[str] = None

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def truncated(self) -> bool:
        """是否因 max_steps 截断 (未自然完成)."""
        return not self.completed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output": self.output,
            "completed": self.completed,
            "truncated": self.truncated,
            "total_steps": self.total_steps,
            "tool_calls": self.tool_calls,
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
        }


class AgentLoop:
    """标准 agentic 循环 / Standard agentic loop (while loop + tools).

    Usage:
        loop = AgentLoop(llm_client, tools=[search_fn, calc_fn], max_steps=8)
        result = await loop.run("What's 23 * 47 then summarize the result?")
        print(result.output, result.total_steps)

    终止条件 / Termination:
      - LLM 返回无 tool_call → 视为最终答案, 自然完成 (completed=True)
      - 达到 max_steps → 截断 (completed=False, truncated=True)

    工具 / Tools: 每个工具是 callable(**kwargs) -> Any, 或带 .name/.execute 的对象。
    """

    def __init__(
        self,
        llm_client: Any,
        tools: Optional[List[Union[Callable, Any]]] = None,
        system_prompt: str = "",
        max_steps: int = 10,
        cost_tracker: Any = None,
        max_context_messages: int = 20,
    ):
        self.llm = llm_client
        self.tools = tools or []
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_steps = max_steps
        # 可选成本追踪器: 与 Nonull 共享时注入, 让两种循环模式成本统一记账。
        self.cost_tracker = cost_tracker
        # context trimming: messages 超此数时丢弃中间轮 (保留首 system+user
        # + 末尾最近几轮), 防 verbose tool 结果撑爆 context window。
        self.max_context_messages = max_context_messages

    # ── 工具定义 (转 OpenAI tool schema) ──────────────────────────

    def _tool_definitions(self) -> List[Any]:
        """把工具列表转成 LLM 能理解的 tool 定义 / Build tool defs for the LLM."""
        from .llm_client import ToolDefinition
        defs = []
        for t in self.tools:
            name = getattr(t, "name", None) or getattr(t, "__name__", None)
            if name is None:
                continue
            desc = getattr(t, "description", "") or (getattr(t, "__doc__", "") or "")[:100]
            params = getattr(t, "parameters", None)
            if params is None and callable(t):
                # plain-function 工具: 从签名推断 schema, 让 LLM 知道参数名
                # (而非空 properties, 那样弱模型会瞎猜/漏参数)
                params = self._infer_schema(t)
            elif params is None:
                params = {"type": "object", "properties": {}}
            defs.append(ToolDefinition(name=name, description=desc, parameters=params))
        return defs

    @staticmethod
    def _infer_schema(func: Callable) -> Dict[str, Any]:
        """从函数签名推断 JSON Schema (简单版, 参数默认 string).

        plain-function 工具无 .parameters 属性时用, 让 LLM 知道参数名
        (而非空 schema)。生产级应据类型注解推断, 这里 demo 级默认 string。

        Infers a JSON schema from the signature so the LLM knows parameter
        names (instead of an empty properties object that makes weak models
        guess/omit args). Production-grade would map type hints; demo-grade
        defaults all params to string.
        """
        import inspect
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for pname, param in inspect.signature(func).parameters.items():
            if param.kind == inspect.Parameter.VAR_KEYWORD:  # **kwargs
                continue
            if pname == "self":
                continue
            properties[pname] = {"type": "string"}
            if param.default is inspect.Parameter.empty:
                required.append(pname)
        schema: Dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    async def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """执行一个工具 (sync 或 async), 返回结果字符串 / Execute a tool (sync or async)."""
        import inspect
        tool = None
        for t in self.tools:
            tname = getattr(t, "name", None) or getattr(t, "__name__", None)
            if tname == name:
                tool = t
                break
        if tool is None:
            return f"Error: tool '{name}' not found"
        try:
            if callable(tool):
                if inspect.iscoroutinefunction(tool):
                    result = await tool(**args)
                else:
                    result = tool(**args)
            elif hasattr(tool, "execute"):
                if inspect.iscoroutinefunction(tool.execute):
                    result = await tool.execute(**args)
                else:
                    result = tool.execute(**args)
            else:
                return f"Error: tool '{name}' is not callable"
            return str(result)
        except Exception as e:
            logger.warning("tool '%s' raised: %s", name, e)
            return f"Error: {type(e).__name__}: {e}"

    # ── 主循环 / The loop ────────────────────────────────────────

    async def run(self, task: str, **llm_kwargs) -> AgentLoopResult:
        """运行 agent loop 直到完成或 max_steps / Run the loop to completion or max_steps."""
        from .llm_client import LLMMessage

        messages: List[Any] = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=task),
        ]
        steps: List[LoopStep] = []
        tool_defs = self._tool_definitions()
        completed = False
        error: Optional[str] = None
        # circuit-breaker: 跟踪每个工具的连续失败次数, 防止 LLM 重复调同一个
        # 失败工具烧光 max_steps (如 calc 坏参数 → error → LLM 重试同样参数 → error)。
        tool_fail_counts: Dict[str, int] = {}

        try:
            for step_num in range(1, self.max_steps + 1):
                # 让出 event loop: chat 是同步阻塞调用, 不让出则外层
                # asyncio.wait_for 的 timeout 无法抢占 (event loop 被阻塞)。
                # Yield so asyncio.wait_for's timeout can fire between steps.
                await asyncio.sleep(0)
                # 1) LLM 决策 (推理 + 选工具或给答案)
                response = self.llm.chat(
                    messages,
                    tools=tool_defs or None,
                    **llm_kwargs,
                )
                # 成本追踪: 与 Nonull 共享 cost_tracker 时, 两种循环模式统一记账
                if self.cost_tracker is not None:
                    try:
                        self.cost_tracker.record(
                            getattr(response, "model", None) or "unknown",
                            getattr(response, "prompt_tokens", 0),
                            getattr(response, "completion_tokens", 0),
                        )
                    except Exception:
                        pass
                thought = response.content or ""

                # 2) 无 tool_call → 最终答案 → 自然终止
                if not getattr(response, "has_tool_calls", False) or not response.tool_calls:
                    steps.append(LoopStep(
                        step=step_num, thought=thought,
                        action="final", observation=thought,
                    ))
                    completed = True
                    logger.info("AgentLoop 完成: step %d (自然终止)", step_num)
                    break

                # 3) 有 tool_call → 执行 + observe → 继续循环
                messages.append(LLMMessage(
                    role="assistant", content=thought, tool_calls=response.tool_calls,
                ))
                for tc in response.tool_calls:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    name = fn.get("name", "")
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                    except json.JSONDecodeError:
                        args = {"_raw": args_raw}
                    obs = await self._execute_tool(name, args)
                    # circuit-breaker: 同工具连续失败 >=3 次 → 提示 LLM 换路
                    # (防烧光 max_steps 重试同一个坏工具调用)
                    if obs.startswith("Error:"):
                        tool_fail_counts[name] = tool_fail_counts.get(name, 0) + 1
                        if tool_fail_counts[name] >= 3:
                            obs = (
                                f"Error: tool '{name}' has failed "
                                f"{tool_fail_counts[name]} times consecutively — it appears "
                                f"broken or misused. Try a DIFFERENT approach or give your "
                                f"final answer without this tool."
                            )
                    else:
                        tool_fail_counts[name] = 0  # 成功则重置
                    steps.append(LoopStep(
                        step=step_num, thought=thought,
                        action=f"tool:{name}", observation=obs,
                    ))
                    messages.append(LLMMessage.tool(
                        content=obs, tool_call_id=tc.get("id", f"call_{step_num}"), name=name,
                    ))
                logger.info("AgentLoop step %d: 执行 %d 个工具", step_num, len(response.tool_calls))

                # context trimming: messages 超阈值时丢弃中间轮, 保留首 (system+user)
                # + 末尾最近几轮。防 verbose tool 结果撑爆 context window。
                # 末尾从第一个 assistant 开始, 保证 tool results 有对应 tool_calls。
                if len(messages) > self.max_context_messages:
                    tail = messages[-self.max_context_messages:]
                    for i, m in enumerate(tail):
                        if getattr(m, "role", "") == "assistant":
                            tail = tail[i:]
                            break
                    messages = messages[:2] + tail
                    logger.info(
                        "AgentLoop context trim: %d -> %d messages",
                        self.max_context_messages + 2, len(messages),
                    )

        except Exception as e:
            logger.exception("AgentLoop 异常终止")
            error = str(e)

        tool_call_count = sum(1 for s in steps if s.action.startswith("tool:"))
        output = steps[-1].observation if steps else ""
        # strip 模型推理块 (MiniMax-M3 / DeepSeek-R1 的 <think>...</think>),
        # 否则 output 含推理链而非干净最终答案。
        # Strip model reasoning blocks so output is the clean final answer.
        import re
        output = re.sub(r"<think>.*?(?:</think>|$)", "", output, flags=re.DOTALL).strip()

        return AgentLoopResult(
            output=output,
            steps=steps,
            completed=completed,
            tool_calls=tool_call_count,
            error=error,
        )

    def __repr__(self) -> str:
        return f"<AgentLoop tools={len(self.tools)} max_steps={self.max_steps}>"
