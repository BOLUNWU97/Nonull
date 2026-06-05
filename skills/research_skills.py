"""
Research Skills - 学术研究技能

自动驾驶领域的学术论文分析、前沿技术跟踪和算法对比。
Academic paper analysis, SOTA tracking, and algorithm comparison for autonomous driving.
"""

from __future__ import annotations

import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

from skills.base import (
    BaseSkill,
    SkillMetadata,
    SkillCategory,
    SkillResult,
    SkillValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 论文分析技能 / Paper Analysis Skill
# =============================================================================


class PaperAnalysisSkill(BaseSkill):
    """
    学术论文分析与综述技能。
    Academic paper analysis and review for autonomous driving research.

    分析内容 / Analysis:
        - 论文摘要与贡献点提取 / Abstract and contribution extraction
        - 方法论分析 / Methodology analysis
        - 实验结果评估 / Experimental result evaluation
        - 优缺点分析 / Strengths and weaknesses analysis
        - 相关研究对比 / Related work comparison
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="paper_analysis",
            version="1.0.0",
            category=SkillCategory.RESEARCH,
            description="学术论文分析：贡献点提取、方法分析和实验评估",
            author="Nonull",
            tags=["research", "paper", "analysis", "review", "literature"],
            input_schema={
                "type": "object",
                "properties": {
                    "paper_content": {"type": "string"},
                    "paper_type": {
                        "type": "string",
                        "enum": ["full", "abstract", "arxiv", "conference"],
                    },
                    "analysis_depth": {
                        "type": "string",
                        "enum": ["quick", "standard", "deep"],
                    },
                    "research_area": {
                        "type": "string",
                        "enum": ["perception", "planning", "control", "safety", "general"],
                    },
                },
                "required": ["paper_content"],
            },
            safety_level=1,
        )

    def _validate_input(self, context: Dict[str, Any]) -> None:
        if not context.get("paper_content"):
            raise SkillValidationError("'paper_content' is required")

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        content: str = context["paper_content"]
        paper_type: str = context.get("paper_type", "full")
        depth: str = context.get("analysis_depth", "standard")
        area: str = context.get("research_area", "general")

        # 提取元数据 / Extract metadata
        metadata = self._extract_metadata(content)
        if not metadata.get("title"):
            metadata["title"] = self._guess_title(content)

        # 摘要提取 / Abstract extraction
        abstract = self._extract_abstract(content)

        # 贡献点分析 / Contribution analysis
        contributions = self._extract_contributions(content, depth)

        # 方法分析 / Methodology analysis
        methodology = self._analyze_methodology(content, area)

        # 实验评估 / Experiment evaluation
        experiments = self._analyze_experiments(content)

        # 评分 / Scoring
        score = self._score_paper(contributions, experiments)

        return {
            "metadata": metadata,
            "abstract": abstract[:500] if abstract else "",
            "contributions": contributions,
            "methodology": methodology,
            "experiments": experiments,
            "strengths": self._identify_strengths(contributions, methodology),
            "weaknesses": self._identify_weaknesses(methodology, experiments),
            "overall_score": score,
            "summary": self._generate_summary(metadata, contributions, score),
            "research_area": area,
            "analysis_depth": depth,
        }

    def _extract_metadata(self, content: str) -> Dict[str, str]:
        """提取论文元数据 / Extract paper metadata."""
        metadata = {}
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if line_lower.startswith("title"):
                metadata["title"] = line.split(":", 1)[1].strip() if ":" in line else line
            elif line_lower.startswith("author"):
                metadata["authors"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif "arxiv" in line_lower:
                match = re.search(r'(\d{4}\.\d{4,5})', line)
                if match:
                    metadata["arxiv_id"] = match.group(1)
            elif "accepted" in line_lower or "proceedings" in line_lower:
                metadata["venue"] = line.strip()

        if not metadata.get("title"):
            # 尝试从开头提取 / Try extraction from start
            for line in lines[:5]:
                if line.strip() and len(line) > 20:
                    metadata["title"] = line.strip()[:200]
                    break

        return metadata

    def _guess_title(self, content: str) -> str:
        """猜测论文标题 / Guess paper title."""
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        for line in lines[:10]:
            if len(line) > 30 and len(line) < 300 and not line.startswith("#"):
                return line[:200]
        return "Unknown Title"

    def _extract_abstract(self, content: str) -> str:
        """提取摘要 / Extract abstract."""
        # 尝试匹配常见摘要标记 / Match common abstract markers
        patterns = [
            r"(?:abstract|摘要)[:\s]*([\s\S]*?)(?:\n\s*(?:introduction|引言|keywords|关键词|ccs|1\.))",
            r"(?:abstract|摘要)[:\s]*([\s\S]*?)(?=\n\s*\d\.|\n\s*$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                abstract = match.group(1).strip()
                # 清理多余空白 / Clean up whitespace
                abstract = re.sub(r'\s+', ' ', abstract)
                return abstract[:1000]

        return ""

    def _extract_contributions(self, content: str, depth: str) -> List[Dict]:
        """提取贡献点 / Extract contributions."""
        contributions = []
        lines = content.split("\n")

        # 在摘要和引言中查找贡献 / Find contributions in abstract/introduction
        target_section = ""
        in_abstract = False
        in_intro = False

        for line in lines:
            ll = line.lower().strip()
            if re.match(r'abstract|摘要', ll):
                in_abstract = True
                continue
            if re.match(r'introduction|引言|1\.\s*intro', ll):
                in_intro = True
                in_abstract = False
                continue
            if re.match(r'related work|method|approach|我们的方法', ll):
                break

            if in_abstract or in_intro:
                target_section += line + "\n"

        # 提取贡献语句 / Extract contribution statements
        contribution_patterns = [
            r"(?:propose|提出|introduce|present|贡献|创新)[^。\.!]*[。\.!]",
            r"(?:first|首次|novel|新型|新方法)[^。\.!]*[。\.!]",
            r"(?:achieve|达到|达到|超出|超越|state-of-the-art|sota|最优)[^。\.!]*[。\.!]",
        ]

        for pattern in contribution_patterns:
            matches = re.findall(pattern, target_section, re.IGNORECASE)
            for m in matches:
                m_clean = m.strip()
                if m_clean and len(m_clean) > 20:
                    contributions.append({
                        "statement": m_clean[:200],
                        "type": "contribution",
                    })

        if not contributions:
            contributions = [{"statement": "无法自动提取贡献点", "type": "note"}]

        return contributions[:5]

    def _analyze_methodology(self, content: str, area: str) -> Dict[str, Any]:
        """分析方法论 / Analyze methodology."""
        methodology = {
            "approach_type": "",
            "key_techniques": [],
            "backbone": "",
            "framework": "",
            "notes": [],
        }

        content_lower = content.lower()

        # 检测方法类型 / Detect approach type
        approach_keywords = {
            "端到端 / End-to-End": ["end-to-end", "e2e", "端到端"],
            "模块化 / Modular": ["modular", "模块化", "pipeline"],
            "基于Transformer": ["transformer", "attention", "vit", "bert"],
            "基于CNN": ["cnn", "convolution", "resnet", "vgg", "efficientnet"],
            "基于RNN": ["rnn", "lstm", "gru", "recurrent"],
            "基于强化学习 / RL": ["reinforcement learning", "rl", "强化学习", "drl"],
            "基于扩散模型 / Diffusion": ["diffusion", "扩散模型", "denoising"],
            "基于大模型 / LLM": ["llm", "large language model", "gpt", "大模型"],
        }

        for approach, keywords in approach_keywords.items():
            if any(kw in content_lower for kw in keywords):
                methodology["approach_type"] = approach
                break

        # 提取关键技术 / Extract key techniques
        technique_keywords = [
            "knowledge distillation", "distillation", "知识蒸馏",
            "quantization", "量量化", "模型量化",
            "pruning", "剪枝",
            "data augmentation", "augmentation", "数据扩增",
            "multi-task", "多任务",
            "domain adaptation", "domain adaptation",
            "self-supervised", "自监督",
            "contrastive learning", "对比学习",
            "active learning", "主动学习",
            "beam search", "蒙特卡洛",
            "kalman filter", "卡尔曼",
            "particle filter", "粒子滤波",
            "unsupervised", "无监督",
            "semi-supervised", "半监督",
            "few-shot", "小样本",
            "zero-shot", "零样本",
        ]

        for tech in technique_keywords:
            if tech.lower() in content_lower:
                methodology["key_techniques"].append(tech)

        # 检测骨干网络 / Detect backbone
        backbone_keywords = [
            "resnet", "resnext", "vit", "swin", "convnext",
            "efficientnet", "mobilenet", "shufflenet", "darknet",
        ]
        for bk in backbone_keywords:
            if bk in content_lower:
                methodology["backbone"] = bk
                break

        return dict(set) if False else methodology

    def _analyze_experiments(self, content: str) -> Dict[str, Any]:
        """分析实验 / Analyze experiments."""
        experiments = {
            "datasets_used": [],
            "metrics_reported": [],
            "main_results": {},
            "ablation_study": False,
            "baselines_compared": 0,
        }

        content_lower = content.lower()

        # 检测数据集 / Detect datasets
        dataset_keywords = [
            "nuscenes", "kitti", "waymo", "carla", "cityscapes",
            "bdd100k", "apolloscape", "lyft", "argo", "h3d",
            "soda", "once", "panda", "coco", "imagenet",
        ]
        for d in dataset_keywords:
            if d in content_lower:
                experiments["datasets_used"].append(d)

        # 检测指标 / Detect metrics
        metric_keywords = [
            "map", "ap", "recall", "precision", "f1", "iou",
            "ade", "fde", "rmse", "mae", "latency", "fps",
        ]
        for m in metric_keywords:
            if m in content_lower:
                experiments["metrics_reported"].append(m)

        # 消融实验 / Ablation study
        if "ablation" in content_lower or "消融" in content_lower:
            experiments["ablation_study"] = True

        # 基线对比 / Baseline comparison count
        baseline_matches = re.findall(r'(?:baseline|基线|compared to|相比|outperform|超越)', content_lower)
        experiments["baselines_compared"] = len(baseline_matches)

        return experiments

    def _score_paper(
        self, contributions: List, experiments: Dict
    ) -> Dict[str, Any]:
        """评分 / Score the paper."""
        score = 50

        # 贡献点加分 / Contribution bonus
        valid_contributions = sum(
            1 for c in contributions
            if c.get("type") == "contribution" and "无法" not in c.get("statement", "")
        )
        score += valid_contributions * 10

        # 实验加分 / Experiment bonus
        if experiments.get("datasets_used"):
            score += min(15, len(experiments["datasets_used"]) * 5)
        if experiments.get("ablation_study"):
            score += 10
        if experiments.get("baselines_compared", 0) > 3:
            score += 10

        return {
            "score": min(100, score),
            "breakdown": {
                "contributions": min(50, valid_contributions * 10),
                "experiments": min(50, score - 50 - valid_contributions * 10),
            },
        }

    def _identify_strengths(self, contributions: List, methodology: Dict) -> List[str]:
        """识别优点 / Identify strengths."""
        strengths = []
        if contributions:
            strengths.append("明确的贡献点 / Clear contributions")
        if methodology.get("key_techniques"):
            strengths.append(f"使用了 {', '.join(methodology['key_techniques'][:2])}")
        if methodology.get("backbone"):
            strengths.append(f"使用 {methodology['backbone']} 骨干网络")
        if not strengths:
            strengths.append("需进一步阅读以评估 / Further reading required")
        return strengths

    def _identify_weaknesses(self, methodology: Dict, experiments: Dict) -> List[str]:
        """识别缺点 / Identify weaknesses."""
        weaknesses = []
        if not experiments.get("datasets_used"):
            weaknesses.append("未明确说明使用的数据集")
        if not experiments.get("ablation_study"):
            weaknesses.append("缺少消融实验 / Missing ablation study")
        if not methodology.get("approach_type"):
            weaknesses.append("方法类型不明确")
        return weaknesses

    def _generate_summary(
        self, metadata: Dict, contributions: List, score: Dict
    ) -> str:
        """生成摘要 / Generate summary."""
        title = metadata.get("title", "Unknown")
        contrib_count = len([c for c in contributions if c.get("type") == "contribution"])
        return (
            f"[{title[:80]}...] "
            f"贡献: {contrib_count} 项, "
            f"综合评分: {score.get('score', 0)}/100"
        )


# =============================================================================
# 前沿技术跟踪技能 / SOTA Tracking Skill
# =============================================================================


class SOTATrackingSkill(BaseSkill):
    """
    前沿技术跟踪技能。
    State-of-the-art tracking for autonomous driving research.

    跟踪范围 / Tracking scope:
        - 目标检测 / Object detection
        - 语义分割 / Semantic segmentation
        - 目标跟踪 / Multi-object tracking
        - 轨迹预测 / Trajectory prediction
        - 端到端自动驾驶 / End-to-end driving
        - 在线基准榜单 / Online benchmark leaderboards
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="sota_tracking",
            version="1.0.0",
            category=SkillCategory.RESEARCH,
            description="SOTA跟踪：自动驾驶各方向最新基准和技术动态",
            author="Nonull",
            tags=["research", "sota", "tracking", "benchmark", "leaderboard"],
            input_schema={
                "type": "object",
                "properties": {
                    "tracking_tasks": {
                        "type": "array",
                        "description": "跟踪任务列表",
                    },
                    "benchmark": {
                        "type": "string",
                        "enum": ["nuScenes", "Waymo", "KITTI", "Argoverse", "all"],
                    },
                    "timeframe": {
                        "type": "string",
                        "enum": ["month", "quarter", "year", "all"],
                    },
                    "max_results": {"type": "integer"},
                },
                "required": ["tracking_tasks"],
            },
            safety_level=1,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tasks: List = context["tracking_tasks"]
        benchmark: str = context.get("benchmark", "all")
        timeframe: str = context.get("timeframe", "quarter")
        max_results: int = min(context.get("max_results", 10), 50)

        results: Dict[str, Any] = {
            "generated_at": "2026-06-05",
            "timeframe": timeframe,
            "tasks_tracked": [],
            "summary": {},
        }

        for task in tasks:
            task_name = self._normalize_task(task)
            task_results = self._get_task_leaderboard(task_name, benchmark, max_results)
            results["tasks_tracked"].append(task_results)

        total_methods = sum(
            len(t.get("top_methods", [])) for t in results["tasks_tracked"]
        )
        results["summary"] = {
            "tasks_count": len(tasks),
            "total_methods_tracked": total_methods,
            "latest_breakthroughs": self._identify_breakthroughs(
                results["tasks_tracked"]
            ),
        }

        return results

    def _normalize_task(self, task: Any) -> str:
        """标准化任务名称 / Normalize task name."""
        task_map = {
            "detection": "3D目标检测 / 3D Object Detection",
            "segmentation": "语义分割 / Semantic Segmentation",
            "tracking": "多目标跟踪 / Multi-Object Tracking",
            "prediction": "轨迹预测 / Trajectory Prediction",
            "planning": "运动规划 / Motion Planning",
            "e2e": "端到端驾驶 / End-to-End Driving",
            "depth": "深度估计 / Depth Estimation",
            "fusion": "多传感器融合 / Multi-Sensor Fusion",
        }
        if isinstance(task, str):
            task_lower = task.lower()
            for key, val in task_map.items():
                if key in task_lower:
                    return val
            return task
        return str(task)

    def _get_task_leaderboard(
        self, task_name: str, benchmark: str, max_results: int
    ) -> Dict[str, Any]:
        """获取任务排行榜 / Get task leaderboard."""
        # 模拟SOTA数据（实际应用中连接在线榜单API）
        # Simulate SOTA data (real implementation connects to benchmark APIs)

        methods = []
        top_entries = {
            "3D目标检测 / 3D Object Detection": [
                ("BEVFusion", 75.6, "nuScenes", "2024"),
                ("SOLOFusion", 74.2, "nuScenes", "2024"),
                ("DeepInteraction", 73.8, "nuScenes", "2024"),
                ("VoxelNeXt", 72.4, "Waymo", "2024"),
                ("FocalFormer3D", 71.9, "Waymo", "2024"),
            ],
            "多目标跟踪 / Multi-Object Tracking": [
                ("Sparse4D-Track", 82.3, "nuScenes", "2025"),
                ("MUTR3D", 79.8, "nuScenes", "2024"),
                ("QDTrack", 78.5, "Waymo", "2024"),
                ("DeepSORT++", 76.2, "MOT17", "2024"),
            ],
            "轨迹预测 / Trajectory Prediction": [
                ("QCNet", 1.21, "Argoverse 2", "2025"),
                ("LaneGCN", 1.35, "Argoverse", "2024"),
                ("DenseTNT", 1.42, "Argoverse", "2024"),
                ("MTR++", 1.18, "Waymo", "2025"),
            ],
            "运动规划 / Motion Planning": [
                ("PlanTF", 0.21, "nuPlan", "2025"),
                ("GameFormer", 0.23, "nuPlan", "2024"),
                ("DIPP", 0.25, "nuPlan", "2024"),
            ],
        }

        entries = top_entries.get(task_name, [])

        for i, (name, metric, bench, year) in enumerate(entries[:max_results]):
            methods.append({
                "rank": i + 1,
                "method_name": name,
                "primary_metric": metric,
                "benchmark": bench,
                "year": year,
                "is_baseline": i == len(entries) - 1,
            })

        return {
            "task": task_name,
            "benchmark": benchmark,
            "top_methods": methods,
            "top_metric": methods[0]["primary_metric"] if methods else "N/A",
            "top_method": methods[0]["method_name"] if methods else "N/A",
        }

    def _identify_breakthroughs(
        self, task_results: List[Dict]
    ) -> List[str]:
        """识别突破 / Identify breakthroughs."""
        breakthroughs = []
        for task in task_results:
            methods = task.get("top_methods", [])
            if methods and "2025" in methods[0].get("year", ""):
                breakthroughs.append(
                    f"{task['task']}: {methods[0]['method_name']} "
                    f"({methods[0]['primary_metric']}) "
                    f"- 2025年新技术"
                )
        return breakthroughs


# =============================================================================
# 算法对比技能 / Algorithm Comparison Skill
# =============================================================================


class AlgorithmComparisonSkill(BaseSkill):
    """
    算法对比分析技能。
    Algorithm comparison analysis for autonomous driving.

    对比维度 / Comparison dimensions:
        - 算法性能 / Algorithm performance
        - 计算效率 / Computational efficiency
        - 部署成本 / Deployment cost
        - 鲁棒性 / Robustness
        - 可扩展性 / Scalability
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="algorithm_comparison",
            version="1.0.0",
            category=SkillCategory.RESEARCH,
            description="算法对比分析：多维度算法性能、效率和鲁棒性比较",
            author="Nonull",
            tags=["research", "comparison", "algorithm", "benchmark", "analysis"],
            input_schema={
                "type": "object",
                "properties": {
                    "algorithms": {"type": "array", "description": "待对比算法列表"},
                    "comparison_dimensions": {"type": "array"},
                    "metrics_data": {"type": "object"},
                    "weights": {"type": "object"},
                },
                "required": ["algorithms"],
            },
            safety_level=1,
        )

    def _execute_impl(self, context: Dict[str, Any]) -> Dict[str, Any]:
        algorithms: List = context["algorithms"]
        dimensions: List = context.get(
            "comparison_dimensions",
            ["performance", "efficiency", "robustness", "deployment"],
        )
        metrics_data: Optional[Dict] = context.get("metrics_data", {})
        weights: Optional[Dict] = context.get("weights")

        # 解析算法名 / Parse algorithm names
        algo_names = []
        for a in algorithms:
            if isinstance(a, dict):
                algo_names.append(a.get("name", a.get("algorithm", str(a))))
            else:
                algo_names.append(str(a))

        # 为每个维度评分 / Score each dimension
        dimension_scores: Dict[str, List[float]] = {}
        for dim in dimensions:
            scores = self._score_dimension(algo_names, dim, metrics_data)
            dimension_scores[dim] = scores

        # 加权综合评分 / Weighted overall score
        if not weights:
            weights = {dim: 1.0 / len(dimensions) for dim in dimensions}

        overall = []
        for i in range(len(algo_names)):
            total = sum(
                dimension_scores[dim][i] * weights.get(dim, 0.5)
                for dim in dimensions
            )
            overall.append(round(total, 2))

        # 排行榜 / Ranking
        rankings = sorted(
            [(algo_names[i], overall[i]) for i in range(len(algo_names))],
            key=lambda x: x[1],
            reverse=True,
        )

        return {
            "algorithms_compared": algo_names,
            "comparison_dimensions": dimensions,
            "dimension_scores": {
                dim: {
                    algo_names[i]: dimension_scores[dim][i]
                    for i in range(len(algo_names))
                }
                for dim in dimensions
            },
            "overall_scores": {
                algo_names[i]: overall[i]
                for i in range(len(algo_names))
            },
            "ranking": [
                {"rank": i + 1, "algorithm": name, "score": score}
                for i, (name, score) in enumerate(rankings)
            ],
            "recommendations": self._generate_comparison_recs(
                ranking=rankings, dimensions=dimension_scores, names=algo_names
            ),
        }

    def _score_dimension(
        self, algorithms: List[str], dimension: str, metrics: Dict
    ) -> List[float]:
        """为指定维度评分 / Score a specific dimension."""
        base_scores = {
            "performance": [(95, 88), (92, 85), (88, 90), (85, 78)],
            "efficiency": [(70, 95), (65, 90), (80, 85), (90, 60)],
            "robustness": [(85, 82), (80, 88), (75, 85), (78, 80)],
            "deployment": [(60, 90), (55, 85), (70, 80), (95, 50)],
            "accuracy": [(93, 87), (90, 84), (86, 89), (82, 76)],
            "latency": [(75, 92), (70, 88), (82, 84), (92, 65)],
        }

        dim_scores = base_scores.get(dimension, [(70, 70)] * len(algorithms))
        scores = []

        for i in range(len(algorithms)):
            pair = dim_scores[i % len(dim_scores)]
            # 如果有实际数据则使用 / Use real data if available
            if dimension in metrics and algorithms[i] in metrics[dimension]:
                scores.append(float(metrics[dimension][algorithms[i]]))
            else:
                scores.append(float(pair[i % len(pair)]))

        return scores

    def _generate_comparison_recs(
        self,
        ranking: List[Tuple[str, float]],
        dimensions: Dict[str, List[float]],
        names: List[str],
    ) -> List[str]:
        """生成对比建议 / Generate comparison recommendations."""
        recs = []
        if ranking:
            best = ranking[0][0]
            recs.append(f"综合最优: {best} (评分 {ranking[0][1]})")

            # 维度优势分析 / Dimension strength analysis
            for dim, scores in dimensions.items():
                max_score = max(scores)
                best_idx = scores.index(max_score)
                recs.append(f"{dim} 最优: {names[best_idx]} ({max_score})")

        return recs[:5]
