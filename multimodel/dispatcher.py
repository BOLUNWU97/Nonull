"""
模型调用分发层 / Model dispatch & invocation layer.

把 RoutingDecision 落实为真实调用: 复用 core.llm_client.LLMClient (纯 httpx,
OpenAI 兼容), 叠加 多 Key 轮询 + 失败重试 + 负载均衡 + 调用日志。

执行链:
  TaskRouter.route() → RoutingDecision → ModelDispatcher.dispatch()
    → KeyRotator 取 Key → 构造 LLMClient → chat()
    → 失败: 重试 (退避) / 换 Key / 模型降级 → 记录 CallLog

@module: multimodel.dispatcher
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .registry import ModelEntry, ModelRegistry, KeyRotator

logger = logging.getLogger("Nonull.multimodel.dispatcher")


@dataclass
class CallLog:
    """单次调用日志 / One invocation's log record."""
    model_name: str
    model_id: str
    provider: str
    key_index_used: int
    attempts: int
    success: bool
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    error: Optional[str] = None
    fell_back_to: Optional[str] = None  # 降级到的模型名

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class DispatchResult:
    """分发调用结果 / Result of a dispatched call."""
    content: str
    model_used: str
    success: bool
    log: CallLog
    raw: Any = None


class CallLogger:
    """调用日志收集器 / Collects CallLog records (in-memory ring + logger)."""

    def __init__(self, max_records: int = 1000):
        self._records: List[CallLog] = []
        self._max = max_records

    def record(self, log: CallLog) -> None:
        self._records.append(log)
        if len(self._records) > self._max:
            self._records = self._records[-self._max:]
        lvl = logging.INFO if log.success else logging.WARNING
        logger.log(
            lvl,
            "调用 %s(%s) key#%d attempts=%d success=%s latency=%.0fms cost=$%.5f%s",
            log.model_name, log.model_id, log.key_index_used, log.attempts,
            log.success, log.latency_ms, log.cost,
            f" fallback→{log.fell_back_to}" if log.fell_back_to else "",
        )

    def records(self) -> List[CallLog]:
        return list(self._records)

    def summary(self) -> Dict[str, Any]:
        if not self._records:
            return {"total_calls": 0}
        total = len(self._records)
        ok = sum(1 for r in self._records if r.success)
        by_model: Dict[str, int] = {}
        total_cost = 0.0
        for r in self._records:
            by_model[r.model_name] = by_model.get(r.model_name, 0) + 1
            total_cost += r.cost
        return {
            "total_calls": total,
            "success": ok,
            "failed": total - ok,
            "success_rate": round(ok / total, 3),
            "by_model": by_model,
            "total_cost": round(total_cost, 5),
        }


class ModelDispatcher:
    """模型调用分发器 / Dispatches calls with retry/rotation/balancing/logging.

    Usage:
        dispatcher = ModelDispatcher(registry, cost_tracker=agent._cost_tracker)
        result = dispatcher.dispatch(entry, messages)
        print(result.content, result.log.to_dict())

    特性:
      - 多 Key 轮询: 每次调用从该模型的 KeyRotator 取下一个 Key
      - 失败重试: 指数退避, 可换 Key (429/5xx)
      - 模型降级: 同档位/medium 备选模型 (fallback_chain)
      - 调用日志: 每次调用记 CallLog, 接入 CostTracker
    """

    def __init__(
        self,
        registry: ModelRegistry,
        cost_tracker: Any = None,
        call_logger: Optional[CallLogger] = None,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ):
        self.registry = registry
        self.cost_tracker = cost_tracker
        self.call_logger = call_logger or CallLogger()
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client_cache: Dict[str, Any] = {}  # (model_name, key) -> LLMClient
        self._cache_lock = threading.Lock()       # 保护 _client_cache (并行 dispatch)

    def _get_client(self, entry: ModelEntry, api_key: str) -> Any:
        """取/建该 (模型, Key) 的 LLMClient (缓存复用连接池, 线程安全)。"""
        cache_key = f"{entry.name}::{api_key[-6:] if api_key else 'local'}"
        # 加锁 check-then-set: collaborator/scheduler 并行 dispatch 到线程池,
        # 无锁会让两个线程为同一 key 各建一个 client → 丢失一个 → 泄漏 socket。
        with self._cache_lock:
            if cache_key in self._client_cache:
                return self._client_cache[cache_key]
            from core.llm_client import LLMClient, LLMConfig
            cfg = LLMConfig(
                api_key=api_key,
                base_url=entry.base_url,
                model=entry.model_id,
                provider=entry.provider,
                max_tokens=entry.max_tokens,
                temperature=entry.temperature,
                context_window=entry.context_window,
                timeout=entry.timeout,  # 推理模型(长<think>)需更长超时, 避免误判超时走重试
                max_retries=0,  # 重试由 dispatcher 控制, 避免双层重试
            )
            client = LLMClient(cfg)
            self._client_cache[cache_key] = client
            return client

    def close(self) -> None:
        """关闭所有缓存的 LLMClient (释放 httpx 连接池) / Close all cached clients.

        幂等。Nonull.close() / HybridScheduler.close() 会调用本方法, 避免
        每个用过 hybrid 的实例泄漏 N 个 socket。
        """
        with self._cache_lock:
            for client in self._client_cache.values():
                try:
                    if hasattr(client, "close"):
                        client.close()
                except Exception:
                    logger.debug("关闭 client 失败", exc_info=True)
            self._client_cache.clear()

    def _fallback_chain(self, entry: ModelEntry) -> List[ModelEntry]:
        """该模型失败后的降级链 / Fallback models when entry fails repeatedly."""
        # 同档位其他模型 → medium 档 → 任意 (去重, 排除自己)
        from .registry import ModelTier
        chain: List[ModelEntry] = []
        seen = {entry.name}
        for pool in (self.registry.by_tier(entry.tier),
                     self.registry.by_tier(ModelTier.MEDIUM),
                     self.registry.all()):
            for e in pool:
                if e.name not in seen and e.enabled:
                    chain.append(e)
                    seen.add(e.name)
        return chain

    def dispatch(
        self,
        entry: ModelEntry,
        messages: List[Any],
        *,
        json_mode: bool = False,
        allow_fallback: bool = True,
        **chat_kwargs,
    ) -> DispatchResult:
        """分发调用一个模型, 带重试/轮询/降级/日志。

        Args:
            entry: 目标模型
            messages: LLMMessage 列表 (或 dict)
            json_mode: 是否强制 JSON 输出
            allow_fallback: 失败后是否降级到备选模型
        """
        result = self._dispatch_one(entry, messages, json_mode, **chat_kwargs)
        if result.success or not allow_fallback:
            return result

        # 降级链
        for alt in self._fallback_chain(entry):
            logger.warning("模型 %s 失败, 降级到 %s / falling back %s→%s",
                           entry.name, alt.name, entry.name, alt.name)
            alt_result = self._dispatch_one(alt, messages, json_mode, **chat_kwargs)
            # 注意: _dispatch_one 内部已 record 过 alt_result.log, 这里只补标记,
            # 不重复 record (否则 CallLogger total_calls/cost 翻倍)。
            alt_result.log.fell_back_to = alt.name
            if alt_result.success:
                return alt_result
        return result

    def _dispatch_one(
        self,
        entry: ModelEntry,
        messages: List[Any],
        json_mode: bool,
        **chat_kwargs,
    ) -> DispatchResult:
        """对单个模型调用 (含多 Key 轮询 + 重试)。"""
        rotator: Optional[KeyRotator] = self.registry.rotator(entry.name)
        attempts = 0
        last_err: Optional[str] = None
        key_idx_used = 0
        start = time.time()

        from core.llm_client import (
            LLMAuthError, LLMRateLimitError, LLMServerError, LLMError,
        )

        for attempt in range(self.max_retries + 1):
            attempts = attempt + 1
            now = time.time()
            api_key = rotator.next_key(now) if rotator else (entry.api_keys[0] if entry.api_keys else "")
            try:
                key_idx_used = entry.api_keys.index(api_key) if api_key in entry.api_keys else 0
            except (ValueError, AttributeError):
                key_idx_used = 0

            try:
                client = self._get_client(entry, api_key)
                resp = client.chat(messages, json_mode=json_mode, **chat_kwargs)
                latency = (time.time() - start) * 1000.0
                content = getattr(resp, "content", "") or ""
                pt = getattr(resp, "prompt_tokens", 0) or 0
                ct = getattr(resp, "completion_tokens", 0) or 0
                cost = 0.0
                if self.cost_tracker is not None:
                    try:
                        cost = self.cost_tracker.record(entry.model_id, pt, ct)
                    except Exception:
                        pass
                log = CallLog(
                    model_name=entry.name, model_id=entry.model_id, provider=entry.provider,
                    key_index_used=key_idx_used, attempts=attempts, success=True,
                    latency_ms=latency, prompt_tokens=pt, completion_tokens=ct, cost=cost,
                )
                self.call_logger.record(log)
                return DispatchResult(content=content, model_used=entry.name,
                                      success=True, log=log, raw=resp)

            except LLMRateLimitError as e:
                # 429: 冷却该 Key, 换下一个 Key 重试
                last_err = f"RateLimit: {e}"
                retry_after = getattr(e, "retry_after", None) or (self.backoff_base * (2 ** attempt))
                if rotator and api_key:
                    rotator.cooldown_key(api_key, time.time() + float(retry_after))
                logger.warning("429 限流, key#%d 冷却 %.1fs, 重试 / rate-limited, cooling key",
                               key_idx_used, float(retry_after))
                time.sleep(min(float(retry_after), 5.0))
            except LLMServerError as e:
                last_err = f"ServerError: {e}"
                time.sleep(self.backoff_base * (2 ** attempt))
            except LLMAuthError as e:
                # 401/403: 该 Key 坏了, 冷却很久, 换 Key (但不退避)
                last_err = f"AuthError: {e}"
                if rotator and api_key:
                    rotator.cooldown_key(api_key, time.time() + 3600.0)
                logger.error("认证失败 key#%d, 冷却 1h / auth failed, cooling key", key_idx_used)
            except (LLMError, Exception) as e:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(self.backoff_base * (2 ** attempt))

        # 全部重试失败
        latency = (time.time() - start) * 1000.0
        log = CallLog(
            model_name=entry.name, model_id=entry.model_id, provider=entry.provider,
            key_index_used=key_idx_used, attempts=attempts, success=False,
            latency_ms=latency, error=last_err,
        )
        self.call_logger.record(log)
        return DispatchResult(content="", model_used=entry.name, success=False, log=log)
