"""
Experience Mining Engine — 经验挖掘引擎
=========================================

从历史执行轨迹中学习成功/失败模式，提取工作流、最佳实践和常见错误修复方案。
灵感来源于 openHunters 的潜意识学习和 Reflexion 的自我反思机制。

Learns from past execution traces by analyzing successful/failed patterns,
extracting common workflows, best practices, and recurring mistake solutions.
Inspired by openHunters' subconscious learning and Reflexion self-improvement.

Typical usage::

    miner = ExperienceMiner()
    patterns = miner.mine_traces(traces)
    skills = miner.extract_skill_patterns(traces)
    improvements = miner.identify_improvements(traces)
"""

from __future__ import annotations

import ast
import hashlib
import logging
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------

class TraceStatus(Enum):
    """执行轨迹状态 / Execution trace status."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    ERROR = "error"


@dataclass
class TraceStep:
    """执行轨迹中的单个步骤 / A single step within an execution trace."""
    action: str
    tool: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    status: TraceStatus = TraceStatus.SUCCESS
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "tool": self.tool,
            "input": self.input,
            "output": repr(self.output)[:500] if self.output else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionTrace:
    """完整的执行轨迹 / A complete execution trace."""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task: str = ""
    task_type: str = "unknown"
    steps: List[TraceStep] = field(default_factory=list)
    overall_status: TraceStatus = TraceStatus.SUCCESS
    total_duration_ms: float = 0.0
    final_output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def add_step(self, step: TraceStep) -> None:
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "task": self.task,
            "task_type": self.task_type,
            "steps": [s.to_dict() for s in self.steps],
            "overall_status": self.overall_status.value,
            "total_duration_ms": self.total_duration_ms,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class ExtractedPattern:
    """从轨迹中提取的模式 / A pattern extracted from traces."""
    pattern_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    pattern_type: str = "workflow"  # workflow | skill | mistake | best_practice
    confidence: float = 0.0
    frequency: int = 0
    steps_sequence: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    outcome: Optional[str] = None
    source_traces: List[str] = field(default_factory=list)
    generalization: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "pattern_type": self.pattern_type,
            "confidence": self.confidence,
            "frequency": self.frequency,
            "steps_sequence": self.steps_sequence,
            "conditions": self.conditions,
            "outcome": self.outcome,
            "source_traces": self.source_traces,
            "generalization": self.generalization,
            "tags": self.tags,
            "created_at": self.created_at,
        }


@dataclass
class ImprovementSuggestion:
    """改进建议 / An improvement suggestion derived from traces."""
    suggestion_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    description: str = ""
    category: str = ""  # efficiency | safety | accuracy | reliability
    severity: str = "medium"  # critical | high | medium | low
    source_traces: List[str] = field(default_factory=list)
    suggested_action: str = ""
    expected_benefit: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "source_traces": self.source_traces,
            "suggested_action": self.suggested_action,
            "expected_benefit": self.expected_benefit,
        }


@dataclass
class KnowledgeItem:
    """从经验中提取的知识项 / A knowledge item extracted from experience."""
    knowledge_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str = ""
    source: str = ""  # semantic | episodic | procedural
    confidence: float = 0.0
    category: str = ""
    tags: List[str] = field(default_factory=list)
    related_skills: List[str] = field(default_factory=list)
    source_trace_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    accessed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "category": self.category,
            "tags": self.tags,
            "related_skills": self.related_skills,
            "source_trace_ids": self.source_trace_ids,
            "created_at": self.created_at,
            "accessed_count": self.accessed_count,
        }


# ---------------------------------------------------------------------------
# Pattern Clustering
# ---------------------------------------------------------------------------

class PatternCluster:
    """将相似模式聚类为泛化知识 / Clusters similar patterns into generalized knowledge.

    使用基于动作序列的相似度度量来分组模式。
    Uses action-sequence-based similarity metrics to group patterns.
    """

    def __init__(self, similarity_threshold: float = 0.65):
        self.similarity_threshold = similarity_threshold
        self.clusters: Dict[str, List[ExtractedPattern]] = {}
        self._cluster_id_counter: int = 0

    def _sequence_signature(self, steps: List[Dict[str, Any]]) -> str:
        """生成步骤序列的哈希签名 / Generate a hash signature for a sequence of steps."""
        actions = [s.get("action", "") for s in steps]
        tools = [s.get("tool", "") or "" for s in steps]
        raw = "->".join(f"{a}:{t}" for a, t in zip(actions, tools))
        return hashlib.md5(raw.encode()).hexdigest()

    def _sequence_similarity(
        self, seq_a: List[Dict[str, Any]], seq_b: List[Dict[str, Any]]
    ) -> float:
        """计算两个步骤序列之间的相似度 / Compute similarity between two step sequences.

        使用最长公共子序列 (LCS) 距离作为度量。
        Uses Longest Common Subsequence (LCS) distance.
        """
        if not seq_a or not seq_b:
            return 0.0

        actions_a = [s.get("action", "") for s in seq_a]
        actions_b = [s.get("action", "") for s in seq_b]

        m, n = len(actions_a), len(actions_b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if actions_a[i - 1] == actions_b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        lcs_len = dp[m][n]
        return lcs_len / max(m, n) if max(m, n) > 0 else 0.0

    def add_pattern(self, pattern: ExtractedPattern) -> Optional[str]:
        """向聚类中添加模式，返回集群ID / Add a pattern to a cluster, returning cluster ID."""
        for cluster_id, patterns in self.clusters.items():
            representative = patterns[0]
            sim = self._sequence_similarity(
                pattern.steps_sequence, representative.steps_sequence
            )
            if sim >= self.similarity_threshold:
                patterns.append(pattern)
                return cluster_id

        # 创建新集群 / Create new cluster
        self._cluster_id_counter += 1
        cid = f"cluster_{self._cluster_id_counter:04d}"
        self.clusters[cid] = [pattern]
        return cid

    def get_generalized_patterns(self) -> List[ExtractedPattern]:
        """从每个聚类生成泛化模式 / Generate generalized patterns from each cluster."""
        generalized: List[ExtractedPattern] = []
        for cluster_id, patterns in self.clusters.items():
            if not patterns:
                continue

            rep = patterns[0]
            conf = sum(p.confidence for p in patterns) / len(patterns)
            freq = sum(p.frequency for p in patterns)

            # 合并源轨迹 / Merge source traces
            all_sources: List[str] = []
            for p in patterns:
                all_sources.extend(p.source_traces)

            # 合并标签 / Merge tags
            tag_counter: Counter = Counter()
            for p in patterns:
                tag_counter.update(p.tags)

            generalized.append(ExtractedPattern(
                name=f"{rep.name}_generalized",
                description=f"泛化自 {len(patterns)} 个模式 | Generalized from {len(patterns)} patterns",
                pattern_type=rep.pattern_type,
                confidence=round(conf, 4),
                frequency=freq,
                steps_sequence=rep.steps_sequence,
                conditions=rep.conditions,
                outcome=rep.outcome,
                source_traces=list(set(all_sources)),
                generalization=f"cluster: {cluster_id}",
                tags=[t for t, _ in tag_counter.most_common(10)],
            ))
        return generalized


# ---------------------------------------------------------------------------
# Confidence Scorer
# ---------------------------------------------------------------------------

class ConfidenceScorer:
    """为提取的模式和知识计算置信度分数 / Computes confidence scores for extracted patterns and knowledge.

    考虑因素：频率、多样性、一致性、时效性。
    Factors: frequency, diversity, consistency, recency.
    """

    @staticmethod
    def score_pattern(
        occurrences: int,
        unique_sources: int,
        consistency_ratio: float,
        max_occurrences: int = 100,
    ) -> float:
        """计算模式置信度 / Compute pattern confidence score (0.0 ~ 1.0)."""
        freq_factor = min(occurrences / max_occurrences, 1.0) * 0.4
        diversity_factor = min(unique_sources / 10, 1.0) * 0.3
        consistency_factor = consistency_ratio * 0.3

        return round(min(freq_factor + diversity_factor + consistency_factor, 1.0), 4)

    @staticmethod
    def score_knowledge(
        frequency: int,
        cross_validation_count: int,
        recency_days: float,
    ) -> float:
        """计算知识置信度 / Compute knowledge confidence score."""
        freq_score = min(frequency / 20, 1.0) * 0.3
        cross_score = min(cross_validation_count / 5, 1.0) * 0.4
        recency_score = max(0, 1.0 - recency_days / 30) * 0.3

        return round(min(freq_score + cross_score + recency_score, 1.0), 4)


# ---------------------------------------------------------------------------
# Experience Miner
# ---------------------------------------------------------------------------

class ExperienceMiner:
    """经验挖掘引擎 — 从执行轨迹中提取可复用的知识。

    Experience Mining Engine — extracts reusable knowledge from execution traces.

    负责：
    - 分析成功/失败模式
    - 提取常见工作流
    - 识别反复出现的错误及其修复方案
    - 对模式进行聚类和泛化
    - 对提取的知识进行置信度评分
    """

    def __init__(
        self,
        similarity_threshold: float = 0.65,
        min_pattern_occurrences: int = 2,
        enable_clustering: bool = True,
    ):
        self.similarity_threshold = similarity_threshold
        self.min_pattern_occurrences = min_pattern_occurrences
        self.enable_clustering = enable_clustering

        self._cluster = PatternCluster(similarity_threshold)
        self._scorer = ConfidenceScorer()

        # 存储已提取的模式和知识 / Store extracted patterns and knowledge
        self.patterns: Dict[str, ExtractedPattern] = {}
        self.knowledge_base: Dict[str, KnowledgeItem] = {}
        self.suggestions: Dict[str, ImprovementSuggestion] = {}

        # 统计 / Statistics
        self.stats: Dict[str, Any] = {
            "total_traces_analyzed": 0,
            "successful_traces": 0,
            "failed_traces": 0,
            "patterns_extracted": 0,
            "knowledge_items": 0,
            "improvements_found": 0,
        }

        logger.info("ExperienceMiner initialized | 经验挖掘引擎已初始化")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mine_traces(self, traces: List[ExecutionTrace]) -> List[ExtractedPattern]:
        """从一组执行轨迹中挖掘模式。

        Analyze a batch of execution traces and extract reusable patterns.

        Args:
            traces: 执行轨迹列表 / List of execution traces

        Returns:
            提取的模式列表 / List of extracted patterns
        """
        logger.info(f"Mining {len(traces)} traces | 挖掘 {len(traces)} 条轨迹")

        # 更新统计 / Update stats
        self.stats["total_traces_analyzed"] += len(traces)
        for t in traces:
            if t.overall_status == TraceStatus.SUCCESS:
                self.stats["successful_traces"] += 1
            else:
                self.stats["failed_traces"] += 1

        # Step 1: 提取基础模式 / Extract basic patterns
        raw_patterns: List[ExtractedPattern] = []
        for trace in traces:
            raw_patterns.extend(self._extract_patterns_from_trace(trace))

        # Step 2: 泛化模式 / Generalize patterns via clustering
        generalized: List[ExtractedPattern] = []
        if self.enable_clustering and raw_patterns:
            for p in raw_patterns:
                self._cluster.add_pattern(p)
            generalized = self._cluster.get_generalized_patterns()

        # Step 3: 合并去重 / Merge and deduplicate
        merged = self._merge_patterns(raw_patterns + generalized)

        # Step 4: 过滤低置信度 / Filter low-confidence patterns
        filtered = [
            p for p in merged
            if p.frequency >= self.min_pattern_occurrences
        ]

        # 存储 / Store
        for p in filtered:
            self.patterns[p.pattern_id] = p
        self.stats["patterns_extracted"] = len(self.patterns)

        logger.info(
            f"Mined {len(filtered)} patterns from {len(traces)} traces | "
            f"从 {len(traces)} 条轨迹中挖掘到 {len(filtered)} 个模式"
        )
        return filtered

    def extract_skill_patterns(
        self, traces: List[ExecutionTrace]
    ) -> List[ExtractedPattern]:
        """提取适合转化为技能的模式。

        Extract patterns that are suitable for conversion into skills.

        筛选条件：工作流模式、高置信度、至少3步动作序列。
        Filters: workflow patterns, high confidence, at least 3 action steps.

        Args:
            traces: 执行轨迹列表 / List of execution traces

        Returns:
            适合技能化的模式列表 / Patterns suitable for skill-ification
        """
        all_patterns = self.mine_traces(traces)
        skill_worthy: List[ExtractedPattern] = []

        for p in all_patterns:
            conditions_met = (
                p.pattern_type == "workflow"
                and p.confidence >= 0.5
                and len(p.steps_sequence) >= 3
            )
            if conditions_met:
                skill_worthy.append(p)

        logger.info(
            f"Found {len(skill_worthy)} skill-worthy patterns | "
            f"发现 {len(skill_worthy)} 个适合技能化的模式"
        )
        return skill_worthy

    def identify_improvements(
        self, traces: List[ExecutionTrace]
    ) -> List[ImprovementSuggestion]:
        """识别基于轨迹的改进建议。

        Identify improvement suggestions based on trace analysis.

        Args:
            traces: 执行轨迹列表 / List of execution traces

        Returns:
            改进建议列表 / List of improvement suggestions
        """
        suggestions: List[ImprovementSuggestion] = []

        # 分析失败模式 / Analyze failure patterns
        failure_traces = [
            t for t in traces
            if t.overall_status in (TraceStatus.FAILURE, TraceStatus.ERROR)
        ]
        if failure_traces:
            suggestions.extend(
                self._analyze_failure_patterns(failure_traces)
            )

        # 分析效率瓶颈 / Analyze efficiency bottlenecks
        efficiency_suggestions = self._analyze_efficiency(traces)
        suggestions.extend(efficiency_suggestions)

        # 分析安全违规 / Analyze safety violations
        safety_suggestions = self._analyze_safety(traces)
        suggestions.extend(safety_suggestions)

        # 存储 / Store
        for s in suggestions:
            self.suggestions[s.suggestion_id] = s
        self.stats["improvements_found"] = len(self.suggestions)

        logger.info(
            f"Identified {len(suggestions)} improvements | "
            f"识别到 {len(suggestions)} 条改进建议"
        )
        return suggestions

    def extract_knowledge(
        self, episodes: List[ExecutionTrace]
    ) -> List[KnowledgeItem]:
        """从执行片段中提取语义知识。

        Extract knowledge items from execution episodes for semantic memory.

        Args:
            episodes: 执行片段列表 / List of execution episodes

        Returns:
            知识项列表 / List of knowledge items
        """
        items: List[KnowledgeItem] = []

        for episode in episodes:
            item = self._trace_to_knowledge(episode)
            if item:
                items.append(item)
                self.knowledge_base[item.knowledge_id] = item

        self.stats["knowledge_items"] = len(self.knowledge_base)

        logger.info(
            f"Extracted {len(items)} knowledge items from {len(episodes)} episodes | "
            f"从 {len(episodes)} 个片段中提取了 {len(items)} 条知识"
        )
        return items

    def get_statistics(self) -> Dict[str, Any]:
        """获取挖掘统计信息 / Get mining statistics."""
        return dict(self.stats)

    def reset(self) -> None:
        """重置所有已学习的模式和知识 / Reset all learned patterns and knowledge."""
        self.patterns.clear()
        self.knowledge_base.clear()
        self.suggestions.clear()
        self._cluster = PatternCluster(self.similarity_threshold)
        self.stats = {
            "total_traces_analyzed": 0,
            "successful_traces": 0,
            "failed_traces": 0,
            "patterns_extracted": 0,
            "knowledge_items": 0,
            "improvements_found": 0,
        }
        logger.info("ExperienceMiner reset | 经验挖掘引擎已重置")

    # ------------------------------------------------------------------
    # Internal: Pattern Extraction
    # ------------------------------------------------------------------

    def _extract_patterns_from_trace(
        self, trace: ExecutionTrace
    ) -> List[ExtractedPattern]:
        """从单条轨迹中提取所有可能的模式。

        Extract all possible patterns from a single trace.
        """
        patterns: List[ExtractedPattern] = []
        steps_dict = [s.to_dict() for s in trace.steps]

        if not steps_dict:
            return patterns

        # 1) 完整轨迹作为工作流模式 / Entire trace as workflow pattern
        outcome = "success" if trace.overall_status == TraceStatus.SUCCESS else "failure"
        workflow_pattern = ExtractedPattern(
            name=f"workflow_{trace.task_type}_{outcome}",
            description=f"完整工作流: {trace.task[:80]} | Complete workflow",
            pattern_type="workflow",
            confidence=0.8 if trace.overall_status == TraceStatus.SUCCESS else 0.3,
            frequency=1,
            steps_sequence=steps_dict,
            outcome=outcome,
            source_traces=[trace.trace_id],
            tags=["workflow", trace.task_type, outcome],
        )
        patterns.append(workflow_pattern)

        # 2) 成功子序列 / Successful subsequences (consecutive successful steps)
        if trace.overall_status == TraceStatus.SUCCESS:
            for i in range(len(steps_dict)):
                for j in range(i + 2, len(steps_dict) + 1):
                    sub = steps_dict[i:j]
                    sub_outcomes = [s.get("status", "success") for s in sub]
                    if all(st == "success" for st in sub_outcomes):
                        sub_pattern = ExtractedPattern(
                            name=f"subworkflow_{trace.task_type}_{i}_{j}",
                            description=f"成功子序列 ({i}:{j}) | Successful subsequence",
                            pattern_type="workflow",
                            confidence=0.6,
                            frequency=1,
                            steps_sequence=sub,
                            outcome="success",
                            source_traces=[trace.trace_id],
                            tags=["subsequence", "success", trace.task_type],
                        )
                        patterns.append(sub_pattern)

        # 3) 错误模式 / Error patterns
        for step_dict in steps_dict:
            if step_dict.get("status") == "error" and step_dict.get("error"):
                error_pattern = ExtractedPattern(
                    name=f"error_{trace.task_type}",
                    description=f"错误: {step_dict['error'][:100]} | Error pattern",
                    pattern_type="mistake",
                    confidence=0.9,
                    frequency=1,
                    steps_sequence=[step_dict],
                    outcome="error",
                    source_traces=[trace.trace_id],
                    tags=["error", trace.task_type],
                )
                patterns.append(error_pattern)

        # 4) 工具使用模式 / Tool usage patterns
        tool_usage: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for step_dict in steps_dict:
            tool = step_dict.get("tool")
            if tool:
                tool_usage[tool].append(step_dict)

        for tool, usages in tool_usage.items():
            if len(usages) >= 2:
                tool_pattern = ExtractedPattern(
                    name=f"tool_{tool}_{trace.task_type}",
                    description=f"工具使用模式: {tool} | Tool usage pattern",
                    pattern_type="best_practice",
                    confidence=0.5,
                    frequency=len(usages),
                    steps_sequence=usages,
                    outcome="success" if all(
                        u.get("status") == "success" for u in usages
                    ) else "mixed",
                    source_traces=[trace.trace_id],
                    tags=["tool", tool, trace.task_type],
                )
                patterns.append(tool_pattern)

        return patterns

    def _merge_patterns(
        self, patterns: List[ExtractedPattern]
    ) -> List[ExtractedPattern]:
        """合并同类型模式，加权累加频率 / Merge equivalent patterns with weighted frequency."""
        merged_map: Dict[str, ExtractedPattern] = {}

        for p in patterns:
            # 使用描述和类型作为合并键 / Use description + type as merge key
            key = f"{p.pattern_type}::{p.name}"
            if key in merged_map:
                existing = merged_map[key]
                existing.frequency += p.frequency
                existing.confidence = max(existing.confidence, p.confidence)
                existing.source_traces.extend(p.source_traces)
                existing.source_traces = list(set(existing.source_traces))
                existing.tags = list(set(existing.tags + p.tags))
            else:
                merged_map[key] = p

        return list(merged_map.values())

    # ------------------------------------------------------------------
    # Internal: Improvement Analysis
    # ------------------------------------------------------------------

    def _analyze_failure_patterns(
        self, failure_traces: List[ExecutionTrace]
    ) -> List[ImprovementSuggestion]:
        """分析失败轨迹以生成改进建议。

        Analyze failure traces to generate improvement suggestions.
        """
        suggestions: List[ImprovementSuggestion] = []

        # 按错误类型分组 / Group by error type
        error_counter: Counter = Counter()
        error_traces: Dict[str, List[ExecutionTrace]] = defaultdict(list)

        for trace in failure_traces:
            error_key = trace.error or "unknown_error"
            error_counter[error_key] += 1
            error_traces[error_key].append(trace)

        # 为常见错误生成建议 / Generate suggestions for frequent errors
        for error_key, count in error_counter.most_common(5):
            if count >= self.min_pattern_occurrences:
                samples = error_traces[error_key]
                suggestions.append(ImprovementSuggestion(
                    title=f"修复频繁错误: {error_key[:60]} | Fix frequent error",
                    description=(
                        f"错误 '{error_key[:100]}' 出现了 {count} 次 | "
                        f"Error occurred {count} times"
                    ),
                    category="reliability",
                    severity="high" if count > 5 else "medium",
                    source_traces=[t.trace_id for t in samples],
                    suggested_action=f"分析并修复 {error_key[:60]} 模式",
                    expected_benefit=f"预计可减少 {count} 次同类错误",
                ))

        return suggestions

    def _analyze_efficiency(
        self, traces: List[ExecutionTrace]
    ) -> List[ImprovementSuggestion]:
        """分析效率瓶颈 / Analyze efficiency bottlenecks."""
        suggestions: List[ImprovementSuggestion] = []

        # 查找异常耗时的步骤 / Find abnormally long steps
        all_durations: List[float] = []
        step_durations: Dict[str, List[float]] = defaultdict(list)

        for trace in traces:
            for step in trace.steps:
                if step.duration_ms > 0:
                    all_durations.append(step.duration_ms)
                    step_durations[step.action].append(step.duration_ms)

        if not all_durations:
            return suggestions

        avg_duration = sum(all_durations) / len(all_durations)
        threshold = avg_duration * 3  # 3x average is concerning

        for action, durations in step_durations.items():
            slow_count = sum(1 for d in durations if d > threshold)
            if slow_count >= 2:
                suggestions.append(ImprovementSuggestion(
                    title=f"性能优化: {action} | Performance optimization",
                    description=(
                        f"'{action}' 有 {slow_count} 次执行超出正常耗时 ({threshold:.0f}ms) | "
                        f"{slow_count} executions exceeded threshold"
                    ),
                    category="efficiency",
                    severity="medium",
                    source_traces=[],
                    suggested_action=f"优化 {action} 的执行效率",
                    expected_benefit="减少响应时间，提升用户体验",
                ))

        return suggestions

    def _analyze_safety(
        self, traces: List[ExecutionTrace]
    ) -> List[ImprovementSuggestion]:
        """分析安全违规 / Analyze safety violations."""
        suggestions: List[ImprovementSuggestion] = []
        safety_keywords = ["delete", "drop", "rm -rf", "remove", "overwrite"]

        for trace in traces:
            for step in trace.steps:
                inp_str = str(step.input).lower()
                for kw in safety_keywords:
                    if kw in inp_str:
                        suggestions.append(ImprovementSuggestion(
                            title=f"安全检查: {kw} 操作 | Safety check: {kw}",
                            description=(
                                f"检测到潜在危险操作 '{kw}' 在轨迹 {trace.trace_id[:8]} | "
                                f"Potentially dangerous operation detected"
                            ),
                            category="safety",
                            severity="critical",
                            source_traces=[trace.trace_id],
                            suggested_action=f"为 '{kw}' 操作添加确认机制",
                            expected_benefit="防止误操作导致数据丢失",
                        ))
                        break  # One suggestion per trace

        return suggestions

    # ------------------------------------------------------------------
    # Internal: Knowledge Extraction
    # ------------------------------------------------------------------

    def _trace_to_knowledge(
        self, episode: ExecutionTrace
    ) -> Optional[KnowledgeItem]:
        """将执行片段转换为知识项 / Convert an execution episode to a knowledge item."""
        if not episode.steps:
            return None

        # 根据任务类型和结果构建知识 / Build knowledge from task type and result
        success_ratio = sum(
            1 for s in episode.steps if s.status == TraceStatus.SUCCESS
        ) / max(len(episode.steps), 1)

        knowledge_content = (
            f"当执行 '{episode.task_type}' 类型任务时，"
            f"遵循 {len(episode.steps)} 步流程，成功率为 {success_ratio:.0%}。"
            f"关键步骤: {' -> '.join(s.action for s in episode.steps[:5])}。"
        )

        return KnowledgeItem(
            content=knowledge_content,
            source="episodic",
            confidence=success_ratio * 0.8,
            category=episode.task_type,
            tags=[episode.task_type, episode.overall_status.value],
            source_trace_ids=[episode.trace_id],
        )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def create_trace(
    task: str,
    task_type: str,
    steps: List[TraceStep],
    status: TraceStatus = TraceStatus.SUCCESS,
) -> ExecutionTrace:
    """快速创建执行轨迹的便捷函数 / Convenience function to create an execution trace."""
    trace = ExecutionTrace(
        task=task,
        task_type=task_type,
        overall_status=status,
    )
    for step in steps:
        trace.add_step(step)
    trace.total_duration_ms = sum(s.duration_ms for s in steps)
    return trace
