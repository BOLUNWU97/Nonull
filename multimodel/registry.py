"""
多模型管理层 / Multi-model registry.

抹平多厂商大模型差异: 云端 API (OpenAI/Claude/DeepSeek/通义千问) + 本地部署
(Ollama/LM Studio)。每个模型注册为一条 ModelEntry, 携带能力标签 (tier)、成本、
延迟、隐私级别、多 API Key 池, 供 TaskRouter 路由 + ModelDispatcher 调用。

设计取舍:
- 复用项目已有的 core.llm_client.LLMClient (纯 httpx, 打 OpenAI 兼容端点)。
  Ollama/LM Studio/LiteLLM/vLLM 都暴露 OpenAI 兼容 /chat/completions, 所以一个
  client 类即可覆盖全部 —— 不强依赖 litellm。若想用 LiteLLM 网关, 把 base_url
  指向 LiteLLM 代理 (见 config.yaml) 即可, 代码零改动。
- 每个 ModelEntry 维护自己的 LLMClient 池 (多 Key → 多 client), 由 KeyRotator
  轮询, 实现多 Key 负载均衡。

@module: multimodel.registry
"""
from __future__ import annotations

import itertools
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Nonull.multimodel.registry")


def _expand_env(value: Any) -> Any:
    """展开 ${VAR} / $VAR 环境变量 / Expand env-var references in config strings.

    P0 修复: nonull_models.yaml 用 ${DEEPSEEK_API_KEY_1} 占位真实 Key, 但
    yaml.safe_load 不展开, 直接传给 client 会导致 "${...}" 字面量当 Key →
    所有云端调用 401。本函数递归展开 str / list / dict 里的 ${VAR}。
    未定义的变量展开为空串 (而非保留字面量), 避免假 Key 泄漏式调用。
    """
    if isinstance(value, str):
        def _sub(m):
            return os.environ.get(m.group(1) or m.group(2), "")
        return re.sub(r"\$\{(\w+)\}|\$(\w+)", _sub, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


class ModelTier(str, Enum):
    """模型能力档位 / Model capability tier (drives routing)."""
    SMALL = "small"      # 小模型: 低成本低延迟, 简单任务 (问答/翻译/闲聊)
    MEDIUM = "medium"    # 中端: 平衡
    LARGE = "large"      # 强模型: 复杂任务 (长文档/代码/推理/方案)
    LOCAL = "local"      # 本地部署 (Ollama/LM Studio), 隐私优先


class PrivacyLevel(str, Enum):
    """隐私级别 / Privacy level."""
    PUBLIC = "public"        # 可走云端
    INTERNAL = "internal"    # 内网数据, 强制本地
    CONFIDENTIAL = "confidential"  # 机密, 仅本地 + 审计


@dataclass
class ModelEntry:
    """单个模型的注册项 / A registered model.

    Attributes:
        name:        路由用的逻辑名 (如 "fast-local", "reasoner")
        model_id:    厂商模型 ID (如 "gpt-4o", "deepseek-chat", "qwen-max", "llama3.1")
        provider:    厂商标识 (openai/claude/deepseek/qwen/ollama/lmstudio/litellm)
        base_url:    OpenAI 兼容端点
        api_keys:    多 Key 池 (本地模型可为 [""] 或 ["ollama"])
        tier:        能力档位 (路由依据)
        privacy:     该模型可处理的最高隐私级别
        cost_per_1k_in/out: 成本 (USD/1K token), 用于成本优先级路由
        avg_latency_ms: 平均延迟 (用于速度优先级路由)
        priority:    手动优先级 (越大越优先, 同档位内排序)
        max_tokens / context_window / temperature: 调用参数
        is_local:    是否本地部署 (隐私强制路由用)
        enabled:     是否启用
    """
    name: str
    model_id: str
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_keys: List[str] = field(default_factory=list)
    tier: ModelTier = ModelTier.MEDIUM
    privacy: PrivacyLevel = PrivacyLevel.PUBLIC
    cost_per_1k_in: float = 0.0
    cost_per_1k_out: float = 0.0
    avg_latency_ms: float = 1000.0
    priority: int = 0
    max_tokens: int = 4096
    context_window: int = 128_000
    temperature: float = 0.2
    is_local: bool = False
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        # 本地模型隐私级别至少 INTERNAL
        if self.is_local and self.privacy == PrivacyLevel.PUBLIC:
            self.privacy = PrivacyLevel.INTERNAL
        if not self.api_keys:
            # 本地模型常无需 key, 给个占位避免空池
            self.api_keys = ["local"] if self.is_local else [""]


class KeyRotator:
    """多 API Key 轮询器 / Round-robin rotator over a key pool (thread-safe).

    每个模型的多 Key 由本类轮询, 实现负载均衡 + 配额分摊。支持临时禁用
    (某 Key 触发 429/401 时), 跳过冷却中的 Key。
    """

    def __init__(self, keys: List[str]):
        self._keys = list(keys) or [""]
        self._cycle = itertools.cycle(range(len(self._keys)))
        self._cooldown: Dict[int, float] = {}  # idx -> 解冻时间戳
        self._lock = threading.Lock()

    def next_key(self, now: float) -> str:
        """取下一个可用 Key (跳过冷却中的)。/ Next available key, skipping cooled-down ones."""
        with self._lock:
            n = len(self._keys)
            for _ in range(n):
                idx = next(self._cycle)
                until = self._cooldown.get(idx, 0.0)
                if until <= now:
                    return self._keys[idx]
            # 全部冷却中: 返回冷却最早结束的
            idx = min(self._cooldown, key=self._cooldown.get) if self._cooldown else 0
            return self._keys[idx]

    def cooldown_key(self, key: str, until: float) -> None:
        """把某 Key 冷却到 until (如 429 Retry-After)。/ Cool down a key until a timestamp."""
        with self._lock:
            try:
                idx = self._keys.index(key)
                self._cooldown[idx] = until
            except ValueError:
                pass


class ModelRegistry:
    """模型注册表 / Central registry of all available models.

    Usage:
        reg = ModelRegistry()
        reg.register(ModelEntry(name="reasoner", model_id="deepseek-reasoner", ...))
        reg = ModelRegistry.from_config(config)  # 从 NonullConfig 的 models.* 段加载
        entry = reg.get("reasoner")
        for e in reg.by_tier(ModelTier.LARGE): ...
    """

    def __init__(self):
        self._models: Dict[str, ModelEntry] = {}
        self._rotators: Dict[str, KeyRotator] = {}

    def register(self, entry: ModelEntry) -> "ModelRegistry":
        self._models[entry.name] = entry
        self._rotators[entry.name] = KeyRotator(entry.api_keys)
        logger.info("注册模型 / registered model: %s (%s, tier=%s, local=%s)",
                    entry.name, entry.model_id, entry.tier.value, entry.is_local)
        return self

    def get(self, name: str) -> Optional[ModelEntry]:
        return self._models.get(name)

    def rotator(self, name: str) -> Optional[KeyRotator]:
        return self._rotators.get(name)

    def all(self) -> List[ModelEntry]:
        return [e for e in self._models.values() if e.enabled]

    def by_tier(self, tier: ModelTier) -> List[ModelEntry]:
        """按档位取模型, 同档位内按 priority 降序。"""
        out = [e for e in self.all() if e.tier == tier]
        return sorted(out, key=lambda e: e.priority, reverse=True)

    def local_models(self) -> List[ModelEntry]:
        """所有本地模型 (隐私强制路由用)。"""
        return sorted([e for e in self.all() if e.is_local],
                      key=lambda e: e.priority, reverse=True)

    def cheapest(self, candidates: Optional[List[ModelEntry]] = None) -> Optional[ModelEntry]:
        pool = candidates or self.all()
        if not pool:
            return None
        return min(pool, key=lambda e: e.cost_per_1k_in + e.cost_per_1k_out)

    def fastest(self, candidates: Optional[List[ModelEntry]] = None) -> Optional[ModelEntry]:
        pool = candidates or self.all()
        if not pool:
            return None
        return min(pool, key=lambda e: e.avg_latency_ms)

    @classmethod
    def from_config(cls, config: Any) -> "ModelRegistry":
        """从 NonullConfig 的 models.* 段构建 / Build from config's models section.

        期望 config.get_section("models") 返回:
            {"reasoner": {"model_id": "...", "provider": "...", "api_keys": [...], ...}, ...}
        """
        reg = cls()
        try:
            models_cfg = config.get_section("models") if hasattr(config, "get_section") else {}
        except Exception:
            models_cfg = {}
        if not models_cfg:
            logger.warning("config 无 models 段, 注册表为空 / no models section in config")
            return reg
        for name, spec in models_cfg.items():
            if not isinstance(spec, dict):
                continue
            try:
                # 展开 ${ENV_VAR}: api_keys / api_key / base_url 都可能含环境变量
                raw_keys = spec.get("api_keys") or ([spec["api_key"]] if spec.get("api_key") else [])
                api_keys = [k for k in _expand_env(raw_keys) if k] or (
                    ["local"] if spec.get("is_local") else []
                )
                reg.register(ModelEntry(
                    name=name,
                    model_id=spec.get("model_id", name),
                    provider=spec.get("provider", "openai"),
                    base_url=_expand_env(spec.get("base_url", "https://api.openai.com/v1")),
                    api_keys=api_keys,
                    tier=ModelTier(spec.get("tier", "medium")),
                    privacy=PrivacyLevel(spec.get("privacy", "public")),
                    cost_per_1k_in=float(spec.get("cost_per_1k_in", 0.0)),
                    cost_per_1k_out=float(spec.get("cost_per_1k_out", 0.0)),
                    avg_latency_ms=float(spec.get("avg_latency_ms", 1000.0)),
                    priority=int(spec.get("priority", 0)),
                    max_tokens=int(spec.get("max_tokens", 4096)),
                    context_window=int(spec.get("context_window", 128_000)),
                    temperature=float(spec.get("temperature", 0.2)),
                    is_local=bool(spec.get("is_local", False)),
                    enabled=bool(spec.get("enabled", True)),
                    tags=spec.get("tags", []),
                ))
            except Exception as e:
                logger.warning("注册模型 %s 失败 / failed to register %s: %s", name, name, e)
        return reg

    def __len__(self) -> int:
        return len(self._models)

    def __repr__(self) -> str:
        return f"<ModelRegistry models={len(self._models)} tiers={[t.value for t in ModelTier]}>"
