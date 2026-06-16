"""
multimodel — 多模型混合调度 + 多智能体协同 / Multi-model hybrid scheduling.

把多厂商大模型 (云端 OpenAI/Claude/DeepSeek/通义千问 + 本地 Ollama/LM Studio)
统一接入 Nonull, 提供:
  - ModelRegistry:        多模型 + 多 Key 注册表
  - TaskRouter:           任务自动分类路由 (简单→小模型, 复杂→强模型, 隐私→本地)
  - ModelDispatcher:      单模型调用 (多 Key 轮询 + 重试 + 降级 + 日志)
  - MultiModelCollaborator: 超复杂任务多模型协作 (拆解+并行+交叉校验+汇总)
  - HybridScheduler:      统一门面, Nonull 的单一接入点

快速开始:
    from multimodel import HybridScheduler
    scheduler = HybridScheduler.from_config(config, cost_tracker=tracker)
    result = await scheduler.aschedule("帮我设计一个分布式限流方案")

@package: multimodel
"""
from .registry import (
    ModelRegistry, ModelEntry, ModelTier, PrivacyLevel, KeyRotator,
)
from .router import (
    TaskRouter, RoutingDecision, RoutingStrategy, TaskComplexity,
)
from .dispatcher import (
    ModelDispatcher, DispatchResult, CallLog, CallLogger,
)
from .collaborator import (
    MultiModelCollaborator, CollaborationResult, SubTask,
)
from .scheduler import HybridScheduler, ScheduleResult

__all__ = [
    "ModelRegistry", "ModelEntry", "ModelTier", "PrivacyLevel", "KeyRotator",
    "TaskRouter", "RoutingDecision", "RoutingStrategy", "TaskComplexity",
    "ModelDispatcher", "DispatchResult", "CallLog", "CallLogger",
    "MultiModelCollaborator", "CollaborationResult", "SubTask",
    "HybridScheduler", "ScheduleResult",
]

__version__ = "0.1.0"
