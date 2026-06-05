"""
程序记忆模块 / Procedural Memory Module (技能与工具 / Skills & Tools)

管理与自动驾驶相关的技能执行流程、工作流模式、工具使用知识。
Manages skill execution workflows, tool usage patterns, and procedural knowledge.

设计要点 / Design Highlights:
    - 技能定义与版本管理 / Skill definition with versioning
    - 执行轨迹记录 / Execution trace logging
    - 工作流模式发现 / Workflow pattern discovery
    - 技能推荐系统 / Skill recommendation based on context
    - 可复现的执行步骤 / Reproducible execution steps

设计灵感 / Design Inspirations:
    - 认知科学中的程序记忆 / Procedural memory in cognitive science
    - "如何做"的知识而非"是什么" / "How-to" vs "What-is" knowledge
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .episodic import EmbeddingProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 枚举与数据结构 / Enums & Data Structures
# ---------------------------------------------------------------------------

class SkillCategory(Enum):
    """技能分类 / Skill categories."""
    PERCEPTION = "perception"                   # 感知处理 / Perception processing
    LOCALIZATION = "localization"               # 定位 / Localization
    PLANNING = "planning"                       # 规划 / Planning
    CONTROL = "control"                         # 控制 / Control
    SIMULATION = "simulation"                   # 仿真 / Simulation
    DEBUGGING = "debugging"                     # 调试 / Debugging
    TESTING = "testing"                         # 测试 / Testing
    DEPLOYMENT = "deployment"                   # 部署 / Deployment
    DATA_PROCESSING = "data_processing"         # 数据处理 / Data processing
    ANALYSIS = "analysis"                       # 分析 / Analysis
    CODE_GEN = "code_generation"                # 代码生成 / Code generation
    REVIEW = "review"                           # 审查 / Code review
    OTHER = "other"                             # 其他 / Other


@dataclass
class SkillStep:
    """技能执行步骤 / A single step within a skill.

    Attributes:
        step_id:      步骤标识 / Step identifier
        description:  步骤描述 / Step description
        command:      命令或代码块 / Command or code block
        expected_outcome: 预期结果 / Expected outcome
        timeout:      超时秒数 / Timeout in seconds
        critical:     是否关键步骤（失败则终止）/ Whether step is critical
    """
    description: str
    command: str = ""
    expected_outcome: str = ""
    timeout: int = 300
    critical: bool = True
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class Skill:
    """技能定义 / A skill definition.

    Attributes:
        skill_id:     唯一标识符 / Unique identifier
        name:         技能名称 / Skill name
        description:  技能描述 / Description
        category:     技能分类 / Skill category
        steps:        执行步骤列表 / Execution steps
        tags:         标签 / Tags
        version:      版本号 / Version
        author:       作者 / Author
        prerequisites: 前置技能 ID 列表 / Prerequisite skill IDs
        inputs:       输入描述 / Input description
        outputs:      输出描述 / Output description
        success_rate: 历史成功率 / Historical success rate
        exec_count:   执行次数 / Execution count
        avg_duration: 平均执行时长（秒）/ Average duration (seconds)
        created_at:   创建时间 / Creation timestamp
        updated_at:   更新时间 / Last updated timestamp
        metadata:     附加元数据 / Additional metadata
    """
    name: str
    description: str
    category: SkillCategory = SkillCategory.OTHER
    steps: List[SkillStep] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "system"
    prerequisites: List[str] = field(default_factory=list)
    inputs: str = ""
    outputs: str = ""
    success_rate: float = 1.0
    exec_count: int = 0
    avg_duration: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def step_count(self) -> int:
        """步骤数 / Number of steps."""
        return len(self.steps)

    @property
    def is_reliable(self) -> bool:
        """技能是否可靠（高频 + 高成功率）/ Whether skill is reliable."""
        return self.exec_count >= 5 and self.success_rate >= 0.85

    def add_step(self, step: SkillStep) -> None:
        """添加执行步骤 / Add an execution step."""
        self.steps.append(step)
        self.updated_at = time.time()

    def update_success(self, duration: float, succeeded: bool) -> None:
        """更新执行统计 / Update execution statistics.

        Args:
            duration:  执行时长（秒）/ Execution duration
            succeeded: 是否成功 / Whether succeeded
        """
        self.exec_count += 1
        # 指数移动平均 / Exponential moving average
        alpha = 0.1
        current_rate = 1.0 if succeeded else 0.0
        self.success_rate = (1 - alpha) * self.success_rate + alpha * current_rate
        self.avg_duration = (1 - alpha) * self.avg_duration + alpha * duration
        self.updated_at = time.time()


@dataclass
class ExecutionTrace:
    """技能执行轨迹 / A record of skill execution.

    Attributes:
        trace_id:     轨迹标识符 / Trace identifier
        skill_id:     技能 ID / Skill ID
        skill_name:   技能名称 / Skill name (denormalized)
        inputs:       输入参数 / Input parameters
        outputs:      输出结果 / Output results
        steps_taken:  已执行的步骤 / Steps executed
        current_step: 当前步骤索引 / Current step index
        status:       执行状态 / Execution status
        started_at:   开始时间 / Start timestamp
        completed_at: 完成时间 / Completion timestamp
        duration:     执行时长（秒）/ Duration (seconds)
        error:        错误信息 / Error message
        metadata:     附加元数据 / Additional metadata
    """
    skill_id: str
    skill_name: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    steps_taken: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    status: str = "pending"           # pending / running / completed / failed / aborted
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def complete(self, outputs: Optional[Dict[str, Any]] = None) -> None:
        """标记执行为完成 / Mark execution as completed."""
        self.status = "completed"
        self.completed_at = time.time()
        self.duration = self.completed_at - self.started_at
        if outputs:
            self.outputs.update(outputs)

    def fail(self, error: str) -> None:
        """标记执行为失败 / Mark execution as failed."""
        self.status = "failed"
        self.completed_at = time.time()
        self.duration = self.completed_at - self.started_at
        self.error = error

    def snapshot(self) -> Dict[str, Any]:
        """获取轨迹快照 / Get trace snapshot."""
        return {
            "trace_id": self.trace_id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "status": self.status,
            "current_step": self.current_step,
            "total_steps": len(self.steps_taken),
            "duration": self.duration,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# 程序记忆主类 / Procedural Memory
# ---------------------------------------------------------------------------

class ProceduralMemory:
    """程序记忆 — 技能与流程管理 / Procedural memory for skills and workflows.

    管理"如何做"的知识，包括技能定义、执行轨迹、工作流模式。
    Manages "how-to" knowledge: skills, execution traces, workflow patterns.

    Attributes:
        name:         记忆名称 / Memory name
        skills:       技能存储 / Skill storage
        traces:       执行轨迹存储 / Execution trace storage
        embedder:     嵌入提供者（用于技能检索）/ Embedding provider
        auto_patterns: 自动发现工作流模式 / Auto-discover workflow patterns
    """

    def __init__(
        self,
        name: str = "default",
        embedder: Optional[EmbeddingProvider] = None,
        auto_patterns: bool = True,
    ):
        self.name = name
        self.embedder = embedder or EmbeddingProvider(dim=256)
        self.auto_patterns = auto_patterns
        self.skills: Dict[str, Skill] = {}
        self.traces: Dict[str, ExecutionTrace] = {}
        self._category_index: Dict[str, List[str]] = defaultdict(list)
        self._tag_index: Dict[str, List[str]] = defaultdict(list)
        self._pattern_cache: Optional[List[Dict[str, Any]]] = None
        self._lock: Any = None

    # ------------------------------------------------------------------
    # 技能管理 / Skill Management
    # ------------------------------------------------------------------

    def register_skill(self, skill: Skill) -> str:
        """注册一个新技能 / Register a new skill.

        Args:
            skill: 技能定义 / Skill definition

        Returns:
            技能 ID / Skill ID
        """
        self.skills[skill.skill_id] = skill
        self._category_index[skill.category.value].append(skill.skill_id)
        for tag in skill.tags:
            self._tag_index[tag].append(skill.skill_id)
        self._pattern_cache = None  # 使模式缓存失效 / Invalidate pattern cache

        logger.info(
            "Registered skill '%s' v%s category=%s steps=%d",
            skill.name, skill.version, skill.category.value, skill.step_count,
        )
        return skill.skill_id

    def create_skill(
        self,
        name: str,
        description: str,
        category: SkillCategory = SkillCategory.OTHER,
        steps: Optional[List[SkillStep]] = None,
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
        **kwargs,
    ) -> Skill:
        """创建并注册新技能 / Create and register a new skill.

        Args:
            name:        技能名称 / Skill name
            description: 技能描述 / Description
            category:    技能分类 / Category
            steps:       执行步骤列表 / Execution steps
            tags:        标签 / Tags
            version:     版本号 / Version
            **kwargs:    附加参数 / Additional keyword arguments

        Returns:
            创建的 Skill 对象 / Created Skill object
        """
        skill = Skill(
            name=name,
            description=description,
            category=category,
            steps=steps or [],
            tags=tags or [],
            version=version,
            **kwargs,
        )
        self.register_skill(skill)
        return skill

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """按 ID 获取技能 / Get a skill by ID.

        Args:
            skill_id: 技能 ID / Skill ID

        Returns:
            Skill 对象或 None / Skill object or None
        """
        return self.skills.get(skill_id)

    def find_skill(self, name: str) -> Optional[Skill]:
        """按名称查找技能（精确匹配）/ Find a skill by exact name.

        Args:
            name: 技能名称 / Skill name

        Returns:
            Skill 对象或 None / Skill or None
        """
        for skill in self.skills.values():
            if skill.name == name:
                return skill
        return None

    def find_skills(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[SkillCategory] = None,
    ) -> List[Skill]:
        """语义搜索技能 / Semantic search for skills.

        Args:
            query:    查询文本 / Query text
            top_k:    返回结果数 / Number of results
            category: 分类筛选 / Filter by category

        Returns:
            匹配的技能列表 / Matching skills
        """
        query_vec = self.embedder.encode(query)

        if category:
            candidate_ids = self._category_index.get(category.value, [])
        else:
            candidate_ids = list(self.skills.keys())

        scored = []
        for sid in candidate_ids:
            skill = self.skills.get(sid)
            if skill is None:
                continue
            skill_text = f"{skill.name} {skill.description} {' '.join(skill.tags)}"
            skill_vec = self.embedder.encode(skill_text)
            sim = float(np.dot(query_vec, skill_vec))
            # 综合：相似度 + 成功率加成 / Combined: similarity + reliability boost
            combined = sim * (0.7 + 0.3 * skill.success_rate)
            scored.append((combined, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:top_k]]

    def get_skills_by_category(self, category: SkillCategory) -> List[Skill]:
        """按分类获取技能 / Get all skills in a category.

        Args:
            category: 技能分类 / Skill category

        Returns:
            技能列表 / List of skills
        """
        return [
            self.skills[sid] for sid in self._category_index.get(category.value, [])
            if sid in self.skills
        ]

    def get_skills_by_tag(self, tag: str) -> List[Skill]:
        """按标签获取技能 / Get all skills with a given tag.

        Args:
            tag: 标签 / Tag

        Returns:
            技能列表 / List of skills
        """
        return [
            self.skills[sid] for sid in self._tag_index.get(tag, [])
            if sid in self.skills
        ]

    def recommend_skills(self, context: str, top_k: int = 3) -> List[Skill]:
        """根据上下文推荐相关技能 / Recommend skills based on context.

        Args:
            context: 当前上下文描述 / Current context description
            top_k:   推荐数 / Number of recommendations

        Returns:
            推荐的技能列表 / Recommended skills
        """
        return self.find_skills(context, top_k=top_k)

    # ------------------------------------------------------------------
    # 执行轨迹 / Execution Traces
    # ------------------------------------------------------------------

    def start_execution(
        self,
        skill_id: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Optional[ExecutionTrace]:
        """开始技能执行 / Start a skill execution.

        Args:
            skill_id: 技能 ID / Skill ID
            inputs:   输入参数 / Input parameters

        Returns:
            创建的 ExecutionTrace 或 None（技能不存在）/ Trace or None
        """
        skill = self.skills.get(skill_id)
        if skill is None:
            logger.error("Cannot start execution: skill %s not found", skill_id[:8])
            return None

        trace = ExecutionTrace(
            skill_id=skill_id,
            skill_name=skill.name,
            inputs=inputs or {},
            steps_taken=[
                {"step_id": s.step_id, "description": s.description, "status": "pending"}
                for s in skill.steps
            ],
            status="running",
        )
        self.traces[trace.trace_id] = trace
        logger.info("Started execution trace %s for skill '%s'", trace.trace_id[:8], skill.name)
        return trace

    def complete_execution(
        self,
        trace_id: str,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[ExecutionTrace]:
        """完成技能执行 / Complete a skill execution.

        Args:
            trace_id: 轨迹 ID / Trace ID
            outputs:  输出结果 / Output results
            error:    错误信息（如果有）/ Error message (if failed)

        Returns:
            ExecutionTrace 或 None / Trace or None
        """
        trace = self.traces.get(trace_id)
        if trace is None:
            return None

        if error:
            trace.fail(error)
            duration = trace.duration or 0.0
            if trace.skill_id in self.skills:
                self.skills[trace.skill_id].update_success(duration, succeeded=False)
        else:
            trace.complete(outputs)
            duration = trace.duration or 0.0
            if trace.skill_id in self.skills:
                self.skills[trace.skill_id].update_success(duration, succeeded=True)

        logger.info(
            "Execution %s for '%s': %s (%.2fs)",
            trace_id[:8], trace.skill_name, trace.status, trace.duration or 0.0,
        )
        return trace

    def get_recent_traces(self, n: int = 10) -> List[ExecutionTrace]:
        """获取最近的执行轨迹 / Get most recent execution traces.

        Args:
            n: 返回数 / Number of traces

        Returns:
            轨迹列表 / List of traces
        """
        sorted_traces = sorted(
            self.traces.values(),
            key=lambda t: t.started_at,
            reverse=True,
        )
        return sorted_traces[:n]

    def get_failed_traces(self, n: int = 10) -> List[ExecutionTrace]:
        """获取失败的执行轨迹 / Get failed execution traces.

        Args:
            n: 返回数 / Number of traces

        Returns:
            失败的轨迹列表 / List of failed traces
        """
        failed = [t for t in self.traces.values() if t.status == "failed"]
        failed.sort(key=lambda t: t.completed_at or 0, reverse=True)
        return failed[:n]

    # ------------------------------------------------------------------
    # 工作流模式 / Workflow Patterns
    # ------------------------------------------------------------------

    def discover_patterns(self) -> List[Dict[str, Any]]:
        """发现常用工作流模式 / Discover common workflow patterns.

        分析执行轨迹，发现频繁共现的技能序列。
        Analyzes execution traces to find frequent skill sequences.

        Returns:
            模式列表 / List of discovered patterns
        """
        if not self.auto_patterns:
            return []

        if self._pattern_cache is not None:
            return self._pattern_cache

        # 按时间排序的执行序列 / Execution sequences sorted by time
        sequences: Dict[str, List[str]] = defaultdict(list)
        for trace in self.traces.values():
            # 这里可以做更复杂的序列分析 / Complex sequence analysis here
            pass

        patterns = []
        # 按分类统计技能使用频率 / Frequency by category
        category_freq = defaultdict(int)
        for skill in self.skills.values():
            category_freq[skill.category.value] += skill.exec_count

        # 发现最常用的技能 / Most frequently used skills
        top_skills = sorted(
            self.skills.values(),
            key=lambda s: s.exec_count,
            reverse=True,
        )[:5]

        for skill in top_skills:
            if skill.exec_count > 0:
                patterns.append({
                    "type": "frequent_skill",
                    "skill_id": skill.skill_id,
                    "skill_name": skill.name,
                    "exec_count": skill.exec_count,
                    "success_rate": skill.success_rate,
                    "avg_duration": skill.avg_duration,
                    "confidence": min(
                        1.0,
                        skill.exec_count / 20 * skill.success_rate,
                    ),
                })

        self._pattern_cache = patterns
        return patterns

    # ------------------------------------------------------------------
    # 内置技能 / Built-in Skills
    # ------------------------------------------------------------------

    def _register_builtin_skills(self) -> None:
        """注册内置自动驾驶相关技能 / Register built-in AD-related skills."""
        builtin_skills = [
            Skill(
                name="carla_scenario_test",
                description="在 CARLA 模拟器中运行指定场景测试 / Run a scenario test in CARLA simulator",
                category=SkillCategory.SIMULATION,
                tags=["CARLA", "simulation", "scenario", "testing"],
                steps=[
                    SkillStep(description="加载 CARLA 地图和场景 / Load CARLA map and scenario"),
                    SkillStep(description="初始化传感器套件 / Initialize sensor suite"),
                    SkillStep(description="启动自动驾驶 Agent / Start autonomous driving agent"),
                    SkillStep(description="执行场景并记录数据 / Execute scenario and log data"),
                    SkillStep(description="评估性能指标 / Evaluate performance metrics"),
                ],
                version="1.0.0",
                inputs="场景配置文件路径 / Scenario config file path",
                outputs="性能评估报告 / Performance evaluation report",
            ),
            Skill(
                name="ros2_build_and_test",
                description="构建并测试 ROS 2 功能包 / Build and test ROS 2 packages",
                category=SkillCategory.DEPLOYMENT,
                tags=["ROS 2", "build", "colcon", "testing"],
                steps=[
                    SkillStep(description="检查依赖 / Check dependencies"),
                    SkillStep(description="使用 colcon 构建 / Build with colcon"),
                    SkillStep(description="运行单元测试 / Run unit tests"),
                    SkillStep(description="运行集成测试 / Run integration tests"),
                    SkillStep(description="生成测试报告 / Generate test report"),
                ],
                version="1.0.0",
            ),
            Skill(
                name="analyze_perception_failure",
                description="分析感知模块故障根因 / Analyze perception module failure root cause",
                category=SkillCategory.DEBUGGING,
                tags=["perception", "debugging", "LiDAR", "camera"],
                steps=[
                    SkillStep(description="收集日志和 rosbag / Collect logs and rosbags"),
                    SkillStep(description="可视化传感器数据 / Visualize sensor data"),
                    SkillStep(description="检查感知输出（检测/跟踪）/ Inspect perception outputs"),
                    SkillStep(description="比对 GT 数据 / Compare against ground truth"),
                    SkillStep(description="定位故障模式 / Localize failure mode"),
                ],
                version="1.0.0",
            ),
            Skill(
                name="review_ad_code",
                description="审查自动驾驶代码的安全性/合规性 / Review autonomous driving code for safety/compliance",
                category=SkillCategory.REVIEW,
                tags=["code review", "safety", "ISO 26262", "ASPICE"],
                steps=[
                    SkillStep(description="检查功能安全合规 (ISO 26262) / Check functional safety compliance"),
                    SkillStep(description="验证 ASPICE 流程覆盖 / Verify ASPICE process coverage"),
                    SkillStep(description="检查传感器数据处理管道 / Review sensor data pipeline"),
                    SkillStep(description="安全边界和异常处理审计 / Audit safety boundaries and error handling"),
                    SkillStep(description="生成审查报告 / Generate review report"),
                ],
                version="1.0.0",
            ),
        ]

        for skill in builtin_skills:
            self.register_skill(skill)

    # ------------------------------------------------------------------
    # 统计与序列化 / Stats & Serialization
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """获取程序记忆统计 / Get procedural memory statistics."""
        category_counts = defaultdict(int)
        total_execs = 0
        total_failures = 0
        for skill in self.skills.values():
            category_counts[skill.category.value] += 1
            total_execs += skill.exec_count
            total_failures += skill.exec_count - int(skill.exec_count * skill.success_rate)

        failed_traces = sum(1 for t in self.traces.values() if t.status == "failed")

        return {
            "name": self.name,
            "total_skills": len(self.skills),
            "total_traces": len(self.traces),
            "category_distribution": dict(category_counts),
            "total_executions": total_execs,
            "total_failures": total_failures,
            "failed_traces": failed_traces,
            "avg_success_rate": (
                sum(s.success_rate for s in self.skills.values()) / len(self.skills)
                if self.skills else 0.0
            ),
            "patterns_found": len(self.discover_patterns()),
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 / Serialize to dictionary."""
        skills_dict = {}
        for sid, skill in self.skills.items():
            skills_dict[sid] = {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category.value,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "description": s.description,
                        "command": s.command,
                        "expected_outcome": s.expected_outcome,
                        "timeout": s.timeout,
                        "critical": s.critical,
                    }
                    for s in skill.steps
                ],
                "tags": skill.tags,
                "version": skill.version,
                "author": skill.author,
                "prerequisites": skill.prerequisites,
                "inputs": skill.inputs,
                "outputs": skill.outputs,
                "success_rate": skill.success_rate,
                "exec_count": skill.exec_count,
                "avg_duration": skill.avg_duration,
                "created_at": skill.created_at,
                "updated_at": skill.updated_at,
                "metadata": skill.metadata,
            }

        traces_dict = {}
        for tid, trace in self.traces.items():
            traces_dict[tid] = {
                "trace_id": trace.trace_id,
                "skill_id": trace.skill_id,
                "skill_name": trace.skill_name,
                "inputs": trace.inputs,
                "outputs": trace.outputs,
                "steps_taken": trace.steps_taken,
                "current_step": trace.current_step,
                "status": trace.status,
                "started_at": trace.started_at,
                "completed_at": trace.completed_at,
                "duration": trace.duration,
                "error": trace.error,
                "metadata": trace.metadata,
            }

        return {
            "name": self.name,
            "skills": skills_dict,
            "traces": traces_dict,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        embedder: Optional[EmbeddingProvider] = None,
    ) -> "ProceduralMemory":
        """从字典反序列化 / Deserialize from dictionary."""
        pm = cls(name=data.get("name", "default"), embedder=embedder, auto_patterns=False)
        for sid, skill_data in data.get("skills", {}).items():
            steps = [
                SkillStep(
                    step_id=s.get("step_id", ""),
                    description=s["description"],
                    command=s.get("command", ""),
                    expected_outcome=s.get("expected_outcome", ""),
                    timeout=s.get("timeout", 300),
                    critical=s.get("critical", True),
                )
                for s in skill_data.get("steps", [])
            ]
            skill = Skill(
                skill_id=skill_data.get("skill_id", sid),
                name=skill_data["name"],
                description=skill_data["description"],
                category=SkillCategory(skill_data.get("category", "other")),
                steps=steps,
                tags=skill_data.get("tags", []),
                version=skill_data.get("version", "1.0.0"),
                author=skill_data.get("author", "system"),
                prerequisites=skill_data.get("prerequisites", []),
                inputs=skill_data.get("inputs", ""),
                outputs=skill_data.get("outputs", ""),
                success_rate=skill_data.get("success_rate", 1.0),
                exec_count=skill_data.get("exec_count", 0),
                avg_duration=skill_data.get("avg_duration", 0.0),
                created_at=skill_data.get("created_at", time.time()),
                updated_at=skill_data.get("updated_at", time.time()),
                metadata=skill_data.get("metadata", {}),
            )
            pm.skills[sid] = skill
            pm._category_index[skill.category.value].append(sid)
            for tag in skill.tags:
                pm._tag_index[tag].append(sid)

        for tid, trace_data in data.get("traces", {}).items():
            trace = ExecutionTrace(
                trace_id=trace_data.get("trace_id", tid),
                skill_id=trace_data["skill_id"],
                skill_name=trace_data["skill_name"],
                inputs=trace_data.get("inputs", {}),
                outputs=trace_data.get("outputs", {}),
                steps_taken=trace_data.get("steps_taken", []),
                current_step=trace_data.get("current_step", 0),
                status=trace_data.get("status", "pending"),
                started_at=trace_data.get("started_at", time.time()),
                completed_at=trace_data.get("completed_at"),
                duration=trace_data.get("duration"),
                error=trace_data.get("error"),
                metadata=trace_data.get("metadata", {}),
            )
            pm.traces[tid] = trace

        pm.auto_patterns = data.get("auto_patterns", True)
        if not data.get("skills"):
            pm._register_builtin_skills()
        return pm

    def __repr__(self) -> str:
        return (
            f"<ProceduralMemory '{self.name}' "
            f"skills={len(self.skills)} "
            f"traces={len(self.traces)}>"
        )
