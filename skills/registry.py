"""
Skill Registry - 技能注册中心

动态加载、发现、组合和管理技能的核心注册表。
Core registry for dynamic loading, discovery, composition, and management of skills.
"""

from __future__ import annotations

import os
import sys
import importlib
import inspect
import logging
import pkgutil
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from skills.base import (
    BaseSkill,
    SkillCategory,
    SkillMetadata,
    SkillResult,
    SkillException,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 技能注册中心 / Skill Registry
# =============================================================================


class SkillRegistry:
    """
    技能注册中心 - 管理所有技能的注册、查找、生命周期。
    Skill Registry - manages registration, lookup, and lifecycle of all skills.

    功能 / Features:
        - 手动注册 / Manual registration
        - 自动发现扫描 / Auto-discovery scanning
        - 按名称/分类/关键词检索 / Search by name/category/keyword
        - 任务匹配 / Task-driven skill matching
        - 依赖解析 / Dependency resolution

    使用示例 / Usage:
        registry = SkillRegistry()
        registry.register(MySkill)
        registry.auto_discover()
        skill = registry.get_skill("code_review")
        result = skill.execute(context={...})
    """

    def __init__(self):
        # skill_name -> skill_instance 映射
        self._skills: Dict[str, BaseSkill] = {}

        # skill_name -> skill_class (延迟实例化用)
        self._skill_classes: Dict[str, Type[BaseSkill]] = {}

        # legacy_alias -> canonical_skill_name
        # 用于保留旧名称（typo、改名）以兼容旧调用方
        # Used to preserve old names (typos, renames) for backward compat.
        # Resolved in get_skill() with a deprecation warning.
        self._legacy_aliases: Dict[str, str] = {}

        # 分类索引 / Category index
        self._category_index: Dict[SkillCategory, List[str]] = {
            cat: [] for cat in SkillCategory
        }

        # 标签索引 / Tag index
        self._tag_index: Dict[str, List[str]] = {}

        # 搜索路径 / Plugin search paths
        self._search_paths: List[str] = []

        # 失败模块记录 / Track modules that failed during auto-discovery.
        # Each entry is a dict with at least: module, error.
        # Auto-discovery must never hard-fail; broken modules are isolated
        # and surfaced via get_diagnostics() so demos and examples keep
        # running even when one skill file is malformed.
        self._broken_modules: List[Dict[str, Any]] = []

        # 注册记录器 / Logger
        self.logger = logging.getLogger(f"{__name__}.SkillRegistry")

    # -------------------------------------------------------------------------
    # 注册与注销 / Register & Unregister
    # -------------------------------------------------------------------------

    def register(
        self,
        skill_class: Type[BaseSkill],
        instance: Optional[BaseSkill] = None,
    ) -> BaseSkill:
        """
        注册一个技能类。
        Register a skill class.

        Args:
            skill_class: 技能类 / Skill class to register.
            instance:    可选，预先创建的实例 / Optional pre-created instance.

        Returns:
            BaseSkill: 注册的技能实例 / Registered skill instance.

        Raises:
            TypeError: 如果 skill_class 不是 BaseSkill 的子类。
            ValueError: 如果技能名已存在。
        """
        if not (isinstance(skill_class, type) and issubclass(skill_class, BaseSkill)):
            raise TypeError(
                f"skill_class must be a subclass of BaseSkill, got {skill_class}"
            )

        # 通过空实例获取元数据 / Get metadata via temporary instance
        temp_instance = instance or skill_class()
        meta = temp_instance.metadata

        if meta.name in self._skills:
            raise ValueError(
                f"Skill '{meta.name}' is already registered. "
                f"Use unregister() first or register with a different name."
            )

        # 如果传入了实例则直接使用，否则暂存类以便延迟实例化
        if instance is not None:
            self._skills[meta.name] = instance
            # 如果未激活则自动激活 / Auto-activate if not active
            if not instance.is_active:
                instance.activate()
        else:
            self._skill_classes[meta.name] = skill_class

        # 向后兼容：注册时同时记录 LEGACY_ALIASES（如果技能类定义了）。
        # Backward compat: record LEGACY_ALIASES if the skill class defines
        # them. Aliases are resolved in get_skill() with a deprecation
        # warning; they are NOT added to the canonical name map or to
        # get_all_skills() output, so duplicate-name invariants still hold.
        legacy_aliases = getattr(skill_class, "LEGACY_ALIASES", ()) or ()
        for alias in legacy_aliases:
            if not alias or alias == meta.name:
                continue
            if alias in self._skills or alias in self._skill_classes:
                # An alias that collides with a real registered name is
                # an error; the real registration wins.
                self.logger.warning(
                    f"Legacy alias '{alias}' for skill '{meta.name}' "
                    f"is already registered as a real skill name; "
                    f"alias will NOT override the real registration."
                )
                continue
            self._legacy_aliases[alias] = meta.name
            self.logger.info(
                f"Registered legacy alias '{alias}' -> '{meta.name}'."
            )

        # 更新索引 / Update indexes
        self._update_indexes(meta)

        self.logger.info(
            f"Registered skill '{meta.name}' (v{meta.version}, "
            f"category={meta.category.value})"
        )

        return self._skills.get(meta.name) or temp_instance

    def unregister(self, skill_name: str) -> None:
        """
        注销一个技能。
        Unregister a skill by name.

        Args:
            skill_name: 要注销的技能名 / Name of the skill to unregister.

        Raises:
            KeyError: 如果技能不存在。
        """
        # 兼容：用别名注销时也能找到规范名。
        # Resolve alias -> canonical so we can clean both sides.
        canonical = self._legacy_aliases.get(skill_name, skill_name)

        if (
            canonical not in self._skills
            and canonical not in self._skill_classes
        ):
            raise KeyError(f"Skill '{skill_name}' is not registered.")

        # 停用并移除实例 / Deactivate and remove instance
        if canonical in self._skills:
            skill = self._skills.pop(canonical)
            try:
                skill.deactivate()
            except Exception as e:
                self.logger.warning(
                    f"Error during deactivation of '{canonical}': {e}"
                )

        # 移除类引用 / Remove class reference
        self._skill_classes.pop(canonical, None)

        # 清理指向该规范名的所有别名 / Drop any legacy aliases pointing here
        stale_aliases = [
            alias
            for alias, target in self._legacy_aliases.items()
            if target == canonical
        ]
        for alias in stale_aliases:
            self._legacy_aliases.pop(alias, None)

        # 清理索引 / Clean up indexes
        self._rebuild_indexes()

        self.logger.info(f"Unregistered skill '{canonical}'.")

    def register_from_instance(self, skill: BaseSkill) -> BaseSkill:
        """
        从已创建的实例注册技能。
        Register a skill from an existing instance.

        Args:
            skill: 已实例化的技能对象 / Instantiated skill object.

        Returns:
            BaseSkill: 注册的技能实例 / Registered skill instance.
        """
        if not isinstance(skill, BaseSkill):
            raise TypeError(f"Expected BaseSkill instance, got {type(skill)}")

        meta = skill.metadata
        if meta.name in self._skills:
            raise ValueError(f"Skill '{meta.name}' is already registered.")

        self._skills[meta.name] = skill
        if not skill.is_active:
            skill.activate()

        self._update_indexes(meta)

        self.logger.info(
            f"Registered skill instance '{meta.name}' (v{meta.version})"
        )
        return skill

    # -------------------------------------------------------------------------
    # 查询方法 / Query Methods
    # -------------------------------------------------------------------------

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        按名称获取技能实例（延迟实例化）。
        Get a skill instance by name (lazy instantiation).

        Args:
            name: 技能名 / Skill name.

        Returns:
            BaseSkill 实例或 None / BaseSkill instance or None.

        Notes:
            如果 ``name`` 是一个已弃用的 LEGACY_ALIASES 别名（非已注册
            的真实技能名），会记录 DeprecationWarning 并解析到规范名。
            If ``name`` is a LEGACY_ALIASES alias (not a real registered
            name), a deprecation warning is logged and the request is
            transparently resolved to the canonical name.
        """
        # 向后兼容别名：旧名称（typo / 重命名）解析为规范名。
        # Backward compat: legacy aliases resolve to canonical name.
        if (
            name in self._legacy_aliases
            and name not in self._skills
            and name not in self._skill_classes
        ):
            canonical = self._legacy_aliases[name]
            self.logger.warning(
                f"Skill name '{name}' is a deprecated alias for "
                f"'{canonical}'. Use '{canonical}' instead."
            )
            return self.get_skill(canonical)

        # 直接返回已缓存的实例 / Return cached instance
        if name in self._skills:
            return self._skills[name]

        # 延迟实例化 / Lazy instantiation
        if name in self._skill_classes:
            try:
                instance = self._skill_classes[name]()
                instance.activate()
                self._skills[name] = instance
                return instance
            except Exception as e:
                self.logger.error(
                    f"Failed to instantiate skill '{name}': {e}"
                )
                return None

        return None

    def get_skill_require_activate(self, name: str) -> Optional[BaseSkill]:
        """
        获取技能并确保已激活。
        Get a skill and ensure it is active.
        """
        skill = self.get_skill(name)
        if skill is not None and not skill.is_active:
            skill.activate()
        return skill

    def get_all_skills(self) -> List[BaseSkill]:
        """
        获取所有已注册的技能实例。
        Get all registered skill instances (lazy instantiation).

        Returns:
            技能实例列表 / List of BaseSkill instances.
        """
        # 确保所有类都被实例化 / Ensure all classes are instantiated
        for name in list(self._skill_classes.keys()):
            self.get_skill(name)

        return list(self._skills.values())

    def find(self, query: str = "", category: Optional[SkillCategory] = None) -> List[BaseSkill]:
        """
        通过关键词或分类查找技能。
        Find skills by keyword or category.

        Args:
            query:    搜索关键词（匹配名称、描述、标签） / Search keyword.
            category: 按分类筛选 / Filter by category.

        Returns:
            匹配的技能实例列表 / List of matching skill instances.
        """
        results: List[BaseSkill] = []

        for skill in self.get_all_skills():
            meta = skill.metadata

            # 分类过滤 / Category filter
            if category is not None and meta.category != category:
                continue

            if not query:
                results.append(skill)
                continue

            # 关键词匹配 / Keyword matching
            query_lower = query.lower()
            if (
                query_lower in meta.name.lower()
                or query_lower in meta.description.lower()
                or any(query_lower in tag.lower() for tag in meta.tags)
            ):
                results.append(skill)

        return results

    def find_by_trigger(self, context: Dict[str, Any]) -> Optional[BaseSkill]:
        """
        根据上下文自动匹配最适合的技能。
        Automatically match the most suitable skill based on context.

        匹配策略 / Matching strategy:
            1. 检查 context 中的 'task_type' 字段
            2. 检查 context 中的 'keywords' 字段
            3. 检查 context 中的 'skill_name' 直接指定

        Args:
            context: 执行上下文 / Execution context.

        Returns:
            最佳匹配的技能或 None / Best matching skill or None.
        """
        if not context:
            return None

        # 1. 直接指定技能名 / Direct skill name specification
        skill_name = context.get("skill_name", "")
        if skill_name:
            skill = self.get_skill(skill_name)
            if skill is not None:
                return skill

        # 2. 根据任务类型匹配 / Match by task type
        task_type = context.get("task_type", "")
        if task_type:
            # 尝试精确匹配任务类型到技能名 / Try exact match
            skill = self.get_skill(task_type)
            if skill is not None:
                return skill

            # 模糊匹配 / Fuzzy match by description/tags
            candidates = self.find(query=task_type)
            if candidates:
                return candidates[0]

        # 3. 根据关键词匹配 / Match by keywords
        keywords = context.get("keywords", [])
        if isinstance(keywords, list) and keywords:
            best_match: Optional[BaseSkill] = None
            best_score = 0
            for skill in self.get_all_skills():
                meta = skill.metadata
                score = 0
                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower in meta.name.lower():
                        score += 3
                    if kw_lower in meta.description.lower():
                        score += 2
                    if any(kw_lower in tag.lower() for tag in meta.tags):
                        score += 1
                if score > best_score:
                    best_score = score
                    best_match = skill

            if best_match and best_score > 0:
                return best_match

        return None

    def get_skills_by_category(self, category: SkillCategory) -> List[BaseSkill]:
        """
        获取指定分类的所有技能。
        Get all skills in a specific category.
        """
        return [s for s in self.get_all_skills() if s.metadata.category == category]

    def skill_count(self) -> int:
        """获取注册的技能总数 / Get total number of registered skills."""
        return len(self._skills) + len(self._skill_classes)

    # -------------------------------------------------------------------------
    # 依赖解析 / Dependency Resolution
    # -------------------------------------------------------------------------

    def resolve_dependencies(
        self, skill_name: str, visited: Optional[Set[str]] = None
    ) -> List[BaseSkill]:
        """
        解析技能的依赖链（拓扑排序）。
        Resolve the dependency chain of a skill (topological order).

        Args:
            skill_name: 需要解析依赖的技能名 / Skill name to resolve.
            visited:    已访问集合（避免循环依赖） / Visited set.

        Returns:
            按执行顺序排列的技能列表 / Skills in execution order.

        Raises:
            ValueError: 如果存在循环依赖或依赖缺失。
        """
        if visited is None:
            visited = set()

        if skill_name in visited:
            raise ValueError(
                f"Circular dependency detected for skill '{skill_name}'"
            )

        skill = self.get_skill(skill_name)
        if skill is None:
            raise ValueError(
                f"Skill '{skill_name}' not found, cannot resolve dependencies."
            )

        visited.add(skill_name)
        result: List[BaseSkill] = []
        meta = skill.metadata

        for dep_name in meta.requires:
            chain = self.resolve_dependencies(dep_name, visited.copy())
            for dep_skill in chain:
                if dep_skill not in result:
                    result.append(dep_skill)

        if skill not in result:
            result.append(skill)

        return result

    # -------------------------------------------------------------------------
    # 自动发现 / Auto Discovery
    # -------------------------------------------------------------------------

    def auto_discover(self, package_path: Optional[str] = None) -> int:
        """
        自动扫描并注册所有 BaseSkill 子类。
        Auto-scan and register all BaseSkill subclasses.

        本方法采用"逐模块隔离"策略：即使某个技能模块在导入或注册阶段
        抛出异常，本次自动发现也不会被中断——失败模块会被记录到
        ``self._broken_modules``，调用方可通过 ``get_diagnostics()`` 查看。
        This method uses a per-module isolation strategy: if a single
        skill module raises during import or registration, auto-discovery
        will continue with the remaining modules. Failures are recorded in
        ``self._broken_modules`` and surfaced via ``get_diagnostics()``.

        Args:
            package_path: 扫描的包路径（默认扫描 skills 包及其子包）。
                          Package path to scan; defaults to the skills package.

        Returns:
            新注册的技能数量 / Number of newly registered skills.
        """
        if package_path is None:
            # 默认扫描当前包 / Default to scanning current package
            package_path = os.path.dirname(os.path.abspath(__file__))

        # 每次 auto_discover 都重新开始统计 / Reset diagnostics per call
        self._broken_modules = []

        count = 0
        sys.path.insert(0, os.path.dirname(package_path))

        for importer, modname, ispkg in pkgutil.iter_modules(
            [package_path], prefix="skills."
        ):
            if modname == "skills.base" or modname == "skills.registry":
                continue
            try:
                module = importlib.import_module(modname)
                count += self._register_from_module(module, module_name=modname)
            except Exception as e:
                # 记录失败模块但继续扫描 / Record but keep going
                self._broken_modules.append(
                    {
                        "module": modname,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )
                self.logger.warning(
                    f"Failed to load module '{modname}': {e}"
                )

        # 摘要日志 / Summary log so operators can see at a glance which
        # modules were skipped without trawling debug output.
        if self._broken_modules:
            broken_names = ", ".join(
                entry["module"] for entry in self._broken_modules
            )
            self.logger.warning(
                f"Auto-discovery completed with {len(self._broken_modules)} "
                f"broken module(s) skipped: [{broken_names}]. "
                f"Registered {count} skill(s). "
                f"Call get_diagnostics() for details."
            )
        else:
            self.logger.info(
                f"Auto-discovery completed cleanly: registered {count} skill(s)."
            )

        return count

    def _register_from_module(
        self,
        module,
        module_name: Optional[str] = None,
    ) -> int:
        """
        从模块中发现并注册 BaseSkill 子类。
        Discover and register BaseSkill subclasses from a module.

        本方法对每一次 ``inspect.getmembers`` 迭代都做了 try/except 隔离，
        以避免单个有问题的技能类（例如 import 时副作用抛错、
        ``__init_subclass__`` 自爆、或 ``metadata`` 属性访问失败）拖垮
        整个 ``auto_discover`` 调用。所有失败都会记录到
        ``self._broken_modules`` 而不是直接抛出。
        Each iteration of ``inspect.getmembers`` is wrapped in its own
        try/except block so a single problematic skill class — e.g. one
        whose import-time side effect raises, whose ``__init_subclass__``
        blows up, or whose ``metadata`` property access fails — will
        NOT take down the entire ``auto_discover`` call. Failures are
        recorded into ``self._broken_modules`` instead of propagating.

        Args:
            module:      目标模块 / Target module object.
            module_name: 可选的模块名（用于诊断）/ Optional module name for diagnostics.

        Returns:
            成功注册的技能数 / Number of skills successfully registered.
        """
        count = 0
        if module_name is None:
            module_name = getattr(module, "__name__", "<unknown>")

        try:
            members = list(inspect.getmembers(module, inspect.isclass))
        except Exception as e:
            # 整个模块无法枚举（如模块级 import 失败） / The whole module
            # is un-introspectable. Record and bail out of this module.
            self._broken_modules.append(
                {
                    "module": module_name,
                    "error": f"getmembers() failed: {e}",
                    "error_type": type(e).__name__,
                }
            )
            self.logger.warning(
                f"Could not introspect module '{module_name}': {e}"
            )
            return 0

        for name, obj in members:
            # 逐类隔离 / Per-class isolation: 一类坏了不影响其他类。
            try:
                if (
                    obj is not BaseSkill
                    and issubclass(obj, BaseSkill)
                    and not inspect.isabstract(obj)
                ):
                    self.register(obj)
                    count += 1
            except (TypeError, ValueError) as e:
                # 注册阶段的预期错误 / Expected registration errors
                self.logger.debug(
                    f"Skipping '{name}' in '{module_name}': {e}"
                )
            except Exception as e:
                # 任何其它异常（例如 import 副作用、metadata 属性崩溃、
                # __init_subclass__ 抛出） / Any other exception
                # (import side effects, metadata access crashes,
                # __init_subclass__ explosions, etc.)
                self._broken_modules.append(
                    {
                        "module": module_name,
                        "skill": name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )
                self.logger.warning(
                    f"Failed to register '{name}' from '{module_name}': {e}"
                )
        return count

    def get_diagnostics(self) -> Dict[str, Any]:
        """
        返回自动发现的诊断信息。
        Return diagnostics from the last ``auto_discover`` (or
        ``discover_from_paths``) call.

        Returns:
            Dict 形如 / Dict shaped like::

                {
                    "successful": [skill_name, ...],   # 成功注册的技能名
                    "broken":     [                   # 失败模块/技能明细
                        {
                            "module":     "skills.foo",
                            "skill":      "FooSkill" | None,
                            "error":      "human readable message",
                            "error_type": "ImportError",
                        },
                        ...
                    ],
                    "summary": {
                        "successful_count": int,
                        "broken_count":     int,
                        "total_count":      int,  # successful + broken
                    },
                }

        Notes:
            该方法不会触发新的发现，只反映上一次 ``auto_discover`` /
            ``discover_from_paths`` 的结果。
            This method does NOT trigger a new discovery; it only
            reflects the last ``auto_discover`` / ``discover_from_paths``
            call.
        """
        successful: List[str] = list(self._skills.keys()) + list(
            self._skill_classes.keys()
        )

        summary = {
            "successful_count": len(successful),
            "broken_count": len(self._broken_modules),
            "total_count": len(successful) + len(self._broken_modules),
        }

        return {
            "successful": successful,
            "broken": list(self._broken_modules),
            "summary": summary,
        }

    def add_search_path(self, path: str) -> None:
        """
        添加技能插件搜索路径。
        Add a plugin search path for skill discovery.
        """
        if os.path.isdir(path) and path not in self._search_paths:
            self._search_paths.append(path)
            self.logger.info(f"Added search path: {path}")

    def discover_from_paths(self) -> int:
        """
        从所有搜索路径中发现技能。
        Discover skills from all registered search paths.
        """
        count = 0
        for path in self._search_paths:
            if not os.path.isdir(path):
                continue
            sys.path.insert(0, os.path.dirname(path))
            for importer, modname, ispkg in pkgutil.iter_modules([path]):
                try:
                    module = importlib.import_module(modname)
                    count += self._register_from_module(module)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load plugin module '{modname}': {e}"
                    )
        return count

    # -------------------------------------------------------------------------
    # 索引管理 / Index Management
    # -------------------------------------------------------------------------

    def _update_indexes(self, meta: SkillMetadata) -> None:
        """更新分类和标签索引 / Update category and tag indexes."""
        # 分类索引 / Category index
        if meta.category in self._category_index:
            if meta.name not in self._category_index[meta.category]:
                self._category_index[meta.category].append(meta.name)
        else:
            self._category_index[meta.category] = [meta.name]

        # 标签索引 / Tag index
        for tag in meta.tags:
            tag_lower = tag.lower()
            if tag_lower not in self._tag_index:
                self._tag_index[tag_lower] = []
            if meta.name not in self._tag_index[tag_lower]:
                self._tag_index[tag_lower].append(meta.name)

    def _rebuild_indexes(self) -> None:
        """重建所有索引 / Rebuild all indexes."""
        self._category_index = {cat: [] for cat in SkillCategory}
        self._tag_index.clear()

        all_names = set(self._skills.keys()) | set(self._skill_classes.keys())

        for name in all_names:
            skill = self.get_skill(name)
            if skill is not None:
                self._update_indexes(skill.metadata)

    # -------------------------------------------------------------------------
    # 批量操作 / Batch Operations
    # -------------------------------------------------------------------------

    def register_all(self, skill_classes: List[Type[BaseSkill]]) -> int:
        """
        批量注册多个技能。
        Register multiple skills at once.
        """
        count = 0
        for cls in skill_classes:
            try:
                self.register(cls)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to register {cls.__name__}: {e}")
        return count

    def activate_all(self) -> None:
        """激活所有已注册的技能 / Activate all registered skills."""
        for skill in self.get_all_skills():
            if not skill.is_active:
                try:
                    skill.activate()
                except Exception as e:
                    self.logger.error(f"Failed to activate '{skill.metadata.name}': {e}")

    def deactivate_all(self) -> None:
        """停用所有技能 / Deactivate all skills."""
        for skill in self._skills.values():
            try:
                skill.deactivate()
            except Exception as e:
                self.logger.warning(
                    f"Error deactivating '{skill.metadata.name}': {e}"
                )

    def clear(self) -> None:
        """清空注册中心所有技能 / Clear all skills from the registry."""
        self.deactivate_all()
        self._skills.clear()
        self._skill_classes.clear()
        self._legacy_aliases.clear()
        self._category_index = {cat: [] for cat in SkillCategory}
        self._tag_index.clear()
        self.logger.info("Registry cleared.")

    # -------------------------------------------------------------------------
    # 序列化 / Serialization
    # -------------------------------------------------------------------------

    def list_registered(self) -> List[Dict[str, Any]]:
        """列出所有注册技能的元数据信息 / List metadata for all registered skills."""
        result = []
        for skill in self.get_all_skills():
            result.append(skill.metadata.to_dict())
        return result

    def __contains__(self, name: str) -> bool:
        return (
            name in self._skills
            or name in self._skill_classes
            or name in self._legacy_aliases
        )

    def __len__(self) -> int:
        return self.skill_count()

    def __repr__(self) -> str:
        return (
            f"<SkillRegistry skills={self.skill_count()} "
            f"active={len(self._skills)} pending={len(self._skill_classes)}>"
        )


# =============================================================================
# 技能组合 / Skill Composition
# =============================================================================


class SkillComposition:
    """
    技能组合 - 将多个技能串行或并行编排执行。
    Skill Composition - orchestrates multiple skills in serial or parallel.

    支持两种模式 / Supports two modes:
        - Pipeline (串行): 前一技能的输出作为后一技能的输入。
          Pipeline (serial): previous output -> next input.
        - FanOut (并行): 多个技能共享同一输入，结果合并。
          FanOut (parallel): multiple skills share input, results merged.

    使用示例 / Usage:
        composition = SkillComposition(registry)
        # 串行管道 / Serial pipeline
        composition.pipeline(["code_review", "code_optimization"])
        result = composition.execute(context)

        # 并行扇出 / Parallel fan-out
        composition.fan_out(["sensor_analysis", "object_detection_review"])
        result = composition.execute(context)
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._pipeline: List[str] = []
        self._mode: str = "pipeline"  # "pipeline" | "fan_out"
        self.logger = logging.getLogger(f"{__name__}.SkillComposition")

    def pipeline(self, skill_names: List[str]) -> "SkillComposition":
        """
        设置串行执行管道。
        Set a serial execution pipeline.

        Args:
            skill_names: 按执行顺序排列的技能名列表。
                         Skills in execution order.

        Returns:
            self (链式调用 / chaining).
        """
        self._validate_skills(skill_names)
        self._pipeline = skill_names
        self._mode = "pipeline"
        return self

    def fan_out(self, skill_names: List[str]) -> "SkillComposition":
        """
        设置并行扇出执行。
        Set a parallel fan-out execution.

        Args:
            skill_names: 并行执行的技能名列表。

        Returns:
            self (链式调用 / chaining).
        """
        self._validate_skills(skill_names)
        self._pipeline = skill_names
        self._mode = "fan_out"
        return self

    def _validate_skills(self, skill_names: List[str]) -> None:
        """验证所有技能是否存在 / Validate that all skills exist."""
        for name in skill_names:
            skill = self.registry.get_skill(name)
            if skill is None:
                raise ValueError(
                    f"Skill '{name}' is not registered in the registry."
                )

    def execute(self, context: Dict[str, Any]) -> Dict[str, SkillResult]:
        """
        执行组合技能。
        Execute the composed skills.

        Args:
            context: 执行上下文 / Execution context.

        Returns:
            Dict[str, SkillResult]: 技能名到执行结果的映射。
        """
        if not self._pipeline:
            raise RuntimeError("No skills composed. Call pipeline() or fan_out() first.")

        if self._mode == "pipeline":
            return self._execute_pipeline(context)
        else:
            return self._execute_fan_out(context)

    def _execute_pipeline(self, context: Dict[str, Any]) -> Dict[str, SkillResult]:
        """串行执行管道 / Execute skills in serial pipeline."""
        results: Dict[str, SkillResult] = {}
        current_context = dict(context)

        # 依赖解析 / Dependency resolution
        ordered_skills: List[str] = []
        visited: Set[str] = set()
        for name in self._pipeline:
            try:
                chain = self.registry.resolve_dependencies(name, visited)
                for s in chain:
                    if s.metadata.name not in ordered_skills:
                        ordered_skills.append(s.metadata.name)
                visited.update(s.metadata.name for s in chain)
            except ValueError as e:
                self.logger.warning(f"Dependency resolution for '{name}': {e}")

        # 按解析后的顺序执行 / Execute in resolved order
        for skill_name in ordered_skills:
            if skill_name not in self._pipeline:
                continue
            skill = self.registry.get_skill(skill_name)
            if skill is None:
                continue
            try:
                result = skill.execute(current_context)
                results[skill_name] = result
                if result.success and result.data is not None:
                    # 将输出注入下一技能的输入 / Pass output as next input
                    if isinstance(result.data, dict):
                        current_context.update(result.data)
                    else:
                        current_context["_last_result"] = result.data
            except Exception as e:
                results[skill_name] = SkillResult.failure(
                    error=str(e), skill_name=skill_name
                )
                break  # 管道中断 / Pipeline break

        return results

    def _execute_fan_out(self, context: Dict[str, Any]) -> Dict[str, SkillResult]:
        """并行扇出执行 / Execute skills in parallel fan-out."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: Dict[str, SkillResult] = {}

        with ThreadPoolExecutor(max_workers=len(self._pipeline)) as executor:
            future_to_name = {}
            for name in self._pipeline:
                skill = self.registry.get_skill(name)
                if skill is not None:
                    future = executor.submit(skill.execute, context.copy())
                    future_to_name[future] = name

            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = SkillResult.failure(
                        error=str(e), skill_name=name
                    )

        return results

    def __repr__(self) -> str:
        return (
            f"<SkillComposition mode={self._mode} "
            f"skills={self._pipeline}>"
        )
