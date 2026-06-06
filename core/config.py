"""
Nonull - 配置系统 (Configuration System)
=================================================

融合 Hermes Agent 的配置档隔离与 Profile 管理理念，支持：
  - YAML 配置文件读取
  - 环境变量覆盖（最高优先级）
  - 多 Profile 隔离（开发/测试/生产/仿真）
  - 默认值兜底
  - 不可变配置快照

Hermes-inspired profile isolation + environment variable integration.

@module: core.config
"""

import os
import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from datetime import datetime

import yaml

logger = logging.getLogger("Nonull.config")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".Nonull")
_ENV_PREFIX = "Nonull_"
_PROFILES = ("dev", "test", "prod", "simulation")
_DEFAULT_PROFILE = "dev"

# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

_CONFIG_SCHEMA: Dict[str, Dict[str, Any]] = {
    "agent": {
        "type": dict,
        "default": {},
        "description": "智能体核心配置 / Agent core configuration",
    },
    "agent.name": {
        "type": str,
        "default": "Nonull",
        "description": "智能体名称 / Agent name",
    },
    "agent.max_iterations": {
        "type": int,
        "default": 50,
        "description": "最大迭代次数 / Maximum ReAct iterations",
    },
    "agent.timeout_seconds": {
        "type": (int, float),
        "default": 300.0,
        "description": "单次任务超时（秒）/ Task timeout in seconds",
    },
    "agent.session_timeout_minutes": {
        "type": int,
        "default": 60,
        "description": "会话超时（分钟）/ Session timeout in minutes",
    },
    "agent.recovery_attempts": {
        "type": int,
        "default": 3,
        "description": "故障恢复尝试次数 / Error recovery attempts",
    },
    "agent.temperature": {
        "type": float,
        "default": 0.2,
        "description": "LLM 温度参数 / LLM temperature",
    },
    ###########################################################################
    # LLM Provider
    ###########################################################################
    "llm": {
        "type": dict,
        "default": {},
        "description": "LLM 提供商配置 / LLM provider configuration",
    },
    "llm.provider": {
        "type": str,
        "default": "openai",
        "description": "LLM 提供商名称 (openai / anthropic / azure / ollama / …)",
    },
    "llm.model": {
        "type": str,
        "default": "gpt-4o",
        "description": "模型名称 / Model name",
    },
    "llm.api_key": {
        "type": str,
        "default": "",
        "description": "API 密钥 / API key (推荐使用环境变量)",
        "sensitive": True,
    },
    "llm.base_url": {
        "type": str,
        "default": "",
        "description": "API 基础 URL / API base URL",
    },
    "llm.max_tokens": {
        "type": int,
        "default": 4096,
        "description": "最大生成 Token 数 / Max output tokens",
    },
    ###########################################################################
    # Memory
    ###########################################################################
    "memory": {
        "type": dict,
        "default": {},
        "description": "记忆系统配置 / Memory system configuration",
    },
    "memory.enabled": {
        "type": bool,
        "default": True,
        "description": "是否启用记忆系统 / Enable memory system",
    },
    "memory.backend": {
        "type": str,
        "default": "local",
        "description": "记忆后端 (local / redis / postgres / chroma)",
    },
    "memory.working_capacity": {
        "type": int,
        "default": 20,
        "description": "工作记忆容量 / Working memory capacity (items)",
    },
    "memory.episodic_retention_days": {
        "type": int,
        "default": 30,
        "description": "情景记忆保留天数 / Episodic memory retention (days)",
    },
    "memory.vector_dim": {
        "type": int,
        "default": 256,
        "description": (
            "向量维度 / Vector embedding dimension. The default in-memory "
            "EmbeddingProvider uses 256-dim n-gram hashing. The previous "
            "1536-dim default assumed sentence-transformers, which is NOT "
            "installed by default. If you plug in a real embedder, set this "
            "to match its output dim."
        ),
    },
    ###########################################################################
    # Safety Guardian
    ###########################################################################
    "safety": {
        "type": dict,
        "default": {},
        "description": "安全监护配置 / Safety Guardian configuration",
    },
    "safety.enabled": {
        "type": bool,
        "default": True,
        "description": "启用安全监护 / Enable safety guardian",
    },
    "safety.deny_first": {
        "type": bool,
        "default": True,
        "description": "拒绝优先模式 (Claude Code 风格) / Deny-first mode",
    },
    "safety.allowed_commands": {
        "type": list,
        "default": [],
        "description": "允许的命令白名单 / Allowed command allowlist",
    },
    "safety.blocked_patterns": {
        "type": list,
        "default": [],
        "description": "拦截的正则模式 / Blocked regex patterns",
    },
    "safety.max_risk_score": {
        "type": float,
        "default": 0.7,
        "description": "最大风险评分 / Maximum allowed risk score",
    },
    ###########################################################################
    # Subagent
    ###########################################################################
    "subagent": {
        "type": dict,
        "default": {},
        "description": "子智能体配置 / Subagent configuration",
    },
    "subagent.max_children": {
        "type": int,
        "default": 5,
        "description": "最大子智能体数量 / Max subagent count",
    },
    "subagent.child_timeout_seconds": {
        "type": (int, float),
        "default": 120.0,
        "description": "子智能体超时 / Subagent timeout",
    },
    "subagent.isolation_level": {
        "type": str,
        "default": "process",
        "description": "隔离级别 (thread / process / container)",
    },
    ###########################################################################
    # Hooks
    ###########################################################################
    "hooks": {
        "type": dict,
        "default": {},
        "description": "钩子系统配置 / Hook system configuration",
    },
    "hooks.enabled": {
        "type": bool,
        "default": True,
        "description": "启用钩子系统 / Enable hook system",
    },
    "hooks.pre_plan": {
        "type": list,
        "default": [],
        "description": "规划前钩子 / Pre-plan hooks",
    },
    "hooks.post_act": {
        "type": list,
        "default": [],
        "description": "执行后钩子 / Post-act hooks",
    },
    ###########################################################################
    # Observability
    ###########################################################################
    "observability": {
        "type": dict,
        "default": {},
        "description": "可观测性配置 / Observability configuration",
    },
    "observability.log_level": {
        "type": str,
        "default": "INFO",
        "description": "日志级别 / Log level",
    },
    "observability.log_file": {
        "type": str,
        "default": "",
        "description": "日志文件路径 / Log file path (empty=stderr)",
    },
    "observability.tracing_enabled": {
        "type": bool,
        "default": False,
        "description": "启用链路追踪 / Enable distributed tracing",
    },
    "observability.metrics_port": {
        "type": int,
        "default": 9090,
        "description": "指标暴露端口 / Metrics exposition port",
    },
    ###########################################################################
    # Driving domain
    ###########################################################################
    "driving": {
        "type": dict,
        "default": {},
        "description": "自动驾驶领域配置 / Autonomous driving domain config",
    },
    "driving.simulator": {
        "type": str,
        "default": "carla",
        "description": "仿真器类型 (carla / simcore / airsim / custom)",
    },
    "driving.sim_host": {
        "type": str,
        "default": "localhost",
        "description": "仿真器主机 / Simulator host",
    },
    "driving.sim_port": {
        "type": int,
        "default": 2000,
        "description": "仿真器端口 / Simulator port",
    },
    "driving.sensor_config": {
        "type": dict,
        "default": {},
        "description": "传感器配置 / Sensor configuration",
    },
    "driving.map_name": {
        "type": str,
        "default": "Town01",
        "description": "默认地图 / Default map name",
    },
    "driving.weather": {
        "type": str,
        "default": "ClearNoon",
        "description": "默认天气 / Default weather preset",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS: Set[str] = {
    key for key, meta in _CONFIG_SCHEMA.items()
    if meta.get("sensitive")
}


def _flatten_dict(d: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    """将嵌套字典展平为点号分隔的扁平字典 / Flatten nested dict."""
    items: Dict[str, Any] = {}
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key))
        else:
            items[new_key] = v
    return items


def _unflatten_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """将点号分隔的扁平字典还原为嵌套字典 / Unflatten dotted dict."""
    result: Dict[str, Any] = {}
    for key, value in d.items():
        parts = key.split(".")
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并两个字典 / Deep merge two dicts."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Config Class
# ---------------------------------------------------------------------------


class NonullConfig:
    """
    Nonull 配置类 / Nonull Configuration
    =====================================================

    配置优先级 (从低到高 / lowest to highest priority):
      1. 代码内默认值 (Defaults)
      2. 默认 Profile YAML
      3. 当前 Profile YAML
      4. 用户自定义 YAML
      5. 环境变量 (前缀 Nonull_)
      6. 运行时 set() 调用

    使用示例 / Usage::

        config = NonullConfig(profile="dev")
        config.load("path/to/config.yaml")
        api_key = config.get("llm.api_key")
        config.set("llm.temperature", 0.3)
        snapshot = config.snapshot()
    """

    _instances: Dict[str, "NonullConfig"] = {}
    _lock = threading.Lock()

    # ------------------------------------------------------------------
    # 工厂 / Factory
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls, profile: str = _DEFAULT_PROFILE) -> "NonullConfig":
        """获取指定 Profile 的单例 / Get singleton for a profile."""
        with cls._lock:
            if profile not in cls._instances:
                cls._instances[profile] = cls(profile=profile)
            return cls._instances[profile]

    @classmethod
    def reset_all(cls) -> None:
        """重置所有单例（测试用）/ Reset all singletons (testing)."""
        with cls._lock:
            cls._instances.clear()

    # ------------------------------------------------------------------
    # 构造 / Constructor
    # ------------------------------------------------------------------

    def __init__(
        self,
        profile: str = _DEFAULT_PROFILE,
        config_dir: Optional[str] = None,
        env_prefix: str = _ENV_PREFIX,
    ) -> None:
        """
        初始化配置 / Initialize configuration.

        Args:
            profile:      配置档名称 (dev / test / prod / simulation)
            config_dir:   配置文件目录 (默认 ~/.Nonull)
            env_prefix:   环境变量前缀 (默认 Nonull_)
        """
        if profile not in _PROFILES:
            logger.warning("未知 Profile '%s'，将使用默认值", profile)
            profile = _DEFAULT_PROFILE

        self._profile: str = profile
        self._config_dir: str = config_dir or _DEFAULT_CONFIG_DIR
        self._env_prefix: str = env_prefix
        self._data: Dict[str, Any] = {}
        self._frozen: bool = False
        self._loaded_files: List[str] = []
        self._load_timestamp: Optional[datetime] = None

        # 1) 加载默认值
        self._load_defaults()
        # 2) 加载 Profile 默认配置
        self._load_profile_default()
        # 3) 加载环境变量
        self._load_env_vars()

        logger.debug(
            "NonullConfig 已初始化 | profile=%s | config_dir=%s",
            profile, config_dir,
        )

    # ------------------------------------------------------------------
    # 内部加载 / Internal loading
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        """加载代码内默认值 / Load code defaults."""
        for key, meta in _CONFIG_SCHEMA.items():
            if "." not in key:  # 顶层 key 暂不设置，由子项覆盖
                continue
            self._set_raw(key, copy.deepcopy(meta["default"]))

    def _load_profile_default(self) -> None:
        """加载当前 Profile 的默认 YAML / Load profile default YAML."""
        path = os.path.join(self._config_dir, f"config.{self._profile}.yaml")
        if os.path.isfile(path):
            self._load_yaml_file(path)

    def _load_env_vars(self) -> None:
        """加载环境变量 (Nonull_*) / Load environment variables."""
        prefix = self._env_prefix
        for env_key, env_val in os.environ.items():
            if not env_key.startswith(prefix):
                continue
            # Nonull_LLM_API_KEY → llm.api_key
            config_key = env_key[len(prefix):].lower().replace("__", ".")
            # 尝试 JSON 解析
            try:
                parsed = json.loads(env_val)
            except (json.JSONDecodeError, TypeError):
                parsed = env_val
            self._set_raw(config_key, parsed)
            logger.debug("环境变量覆盖: %s = %s", config_key, _mask_sensitive(config_key, str(parsed)))

    def _load_yaml_file(self, path: str) -> None:
        """加载单个 YAML 文件 / Load a single YAML file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
            flat = _flatten_dict(yaml_data)
            for key, value in flat.items():
                self._set_raw(key, value)
            self._loaded_files.append(path)
            logger.info("已加载配置: %s (%d 项)", path, len(flat))
        except FileNotFoundError:
            logger.debug("配置文件不存在: %s", path)
        except yaml.YAMLError as e:
            logger.error("YAML 解析错误 %s: %s", path, e)
        except Exception as e:
            logger.exception("加载配置异常 %s: %s", path, e)

    def _set_raw(self, key: str, value: Any) -> None:
        """原始 set（绕过冻结检查）/ Raw set bypassing frozen check."""
        if key in _CONFIG_SCHEMA:
            expected_type = _CONFIG_SCHEMA[key]["type"]
            if not isinstance(value, expected_type):
                try:
                    value = expected_type(value)
                except (TypeError, ValueError):
                    logger.warning(
                        "配置项 %s 类型不匹配 (期望 %s, 得到 %s)，跳过",
                        key, expected_type.__name__, type(value).__name__,
                    )
                    return
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    # ------------------------------------------------------------------
    # 公共接口 / Public API
    # ------------------------------------------------------------------

    # ---- 加载 ----

    def load(self, path: str) -> "NonullConfig":
        """
        加载用户自定义配置文件 / Load user custom config file.

        Args:
            path: YAML 配置文件路径

        Returns:
            self (支持链式调用)
        """
        self._assert_not_frozen()
        self._load_yaml_file(path)
        self._load_env_vars()  # 环境变量始终覆盖
        return self

    def load_dict(self, data: Dict[str, Any]) -> "NonullConfig":
        """
        从字典加载配置 / Load config from dict.

        Args:
            data: 配置字典

        Returns:
            self (支持链式调用)
        """
        self._assert_not_frozen()
        flat = _flatten_dict(data)
        for key, value in flat.items():
            self._set_raw(key, value)
        return self

    def reload(self) -> "NonullConfig":
        """
        重新加载所有配置文件 / Reload all config files.

        保留运行时 set 的值，重新加载 YAML 和环境变量。
        """
        self._assert_not_frozen()
        # 保留运行时的 set
        runtime_overrides = copy.deepcopy(self._data)
        self._data = {}
        self._loaded_files = []
        self._load_defaults()
        self._load_profile_default()
        self._load_env_vars()
        # 重新应用运行时覆盖
        flat = _flatten_dict(runtime_overrides)
        for key, value in flat.items():
            self._set_raw(key, value)
        self._load_timestamp = datetime.now()
        logger.info("配置已重新加载")
        return self

    # ---- 读取 ----

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项 / Get a config value.

        Args:
            key:     点号分隔的配置键 (如 "llm.api_key")
            default: 默认值

        Returns:
            配置值
        """
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def get_section(self, prefix: str) -> Dict[str, Any]:
        """
        获取整个配置段 / Get a config section as nested dict.

        Args:
            prefix: 段前缀 (如 "llm")

        Returns:
            该段落的嵌套字典
        """
        result = self.get(prefix, {})
        if not isinstance(result, dict):
            return {}
        return copy.deepcopy(result)

    def all(self) -> Dict[str, Any]:
        """
        获取完整配置的深拷贝 / Get full config deep copy.

        Returns:
            嵌套配置字典
        """
        return copy.deepcopy(self._data)

    def all_flat(self) -> Dict[str, Any]:
        """
        获取扁平化配置 / Get flattened config.

        Returns:
            { "llm.api_key": "...", ... }
        """
        return _flatten_dict(self._data)

    def keys(self) -> Set[str]:
        """获取所有配置键集合 / Get all config keys."""
        return set(_flatten_dict(self._data).keys())

    # ---- 写入 ----

    def set(self, key: str, value: Any) -> "NonullConfig":
        """
        设置配置项（运行时覆盖）/ Set a config value (runtime override).

        Args:
            key:   点号分隔的配置键
            value: 值

        Returns:
            self (支持链式调用)
        """
        self._assert_not_frozen()
        self._set_raw(key, value)
        return self

    def update(self, data: Dict[str, Any]) -> "NonullConfig":
        """
        批量更新配置 / Batch update config.

        Args:
            data: 配置字典

        Returns:
            self
        """
        self._assert_not_frozen()
        flat = _flatten_dict(data)
        for key, value in flat.items():
            self._set_raw(key, value)
        return self

    # ---- 冻结 / 快照 ----

    def freeze(self) -> "NonullConfig":
        """
        冻结配置，防止进一步修改 / Freeze config against further changes.

        Returns:
            self
        """
        self._frozen = True
        self._load_timestamp = datetime.now()
        logger.info("配置已冻结")
        return self

    def snapshot(self) -> "NonullConfig":
        """
        创建当前配置的不可变快照 / Create immutable snapshot.

        Returns:
            新的冻结配置实例
        """
        snap = NonullConfig.__new__(NonullConfig)
        snap._profile = self._profile
        snap._config_dir = self._config_dir
        snap._env_prefix = self._env_prefix
        snap._data = copy.deepcopy(self._data)
        snap._frozen = True
        snap._loaded_files = list(self._loaded_files)
        snap._load_timestamp = datetime.now()
        return snap

    # ---- Profile ----

    @property
    def profile(self) -> str:
        """当前 Profile 名称 / Current profile name."""
        return self._profile

    def switch_profile(self, profile: str) -> "NonullConfig":
        """
        切换 Profile 并重新加载 / Switch profile and reload.

        Args:
            profile: 目标 Profile 名称

        Returns:
            self
        """
        if profile not in _PROFILES:
            raise ValueError(f"未知 Profile: {profile}，可选: {_PROFILES}")
        self._assert_not_frozen()
        self._profile = profile
        self.reload()
        return self

    @classmethod
    def available_profiles(cls) -> tuple:
        """可用的 Profile 列表 / List available profiles."""
        return _PROFILES

    # ---- 序列化 ----

    def to_yaml(self, path: Optional[str] = None) -> Optional[str]:
        """
        导出配置为 YAML / Export config to YAML.

        Args:
            path: 可选的文件路径

        Returns:
            YAML 字符串（如果未指定路径）
        """
        yaml_str = yaml.safe_dump(
            self._data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        if path:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(yaml_str)
            logger.info("配置已导出至: %s", path)
            return None
        return yaml_str

    def to_json(self, path: Optional[str] = None, pretty: bool = True) -> Optional[str]:
        """
        导出配置为 JSON / Export config to JSON.

        Args:
            path:   可选的文件路径
            pretty: 是否美化输出

        Returns:
            JSON 字符串（如果未指定路径）
        """
        indent = 2 if pretty else None
        json_str = json.dumps(self._data, indent=indent, ensure_ascii=False, default=str)
        if path:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.info("配置已导出至: %s", path)
            return None
        return json_str

    # ---- 诊断 ----

    def validate(self) -> List[str]:
        """
        校验配置完整性 / Validate config integrity.

        Returns:
            错误信息列表（空列表表示校验通过）
        """
        errors: List[str] = []
        for key, meta in _CONFIG_SCHEMA.items():
            if "." not in key:
                continue
            value = self.get(key, _SENTINEL)
            if value is _SENTINEL:
                errors.append(f"缺少必需配置项: {key}")
                continue
            expected = meta["type"]
            if not isinstance(value, expected):
                errors.append(
                    f"配置项 {key} 类型错误: 期望 {expected.__name__}, 得到 {type(value).__name__}"
                )
        return errors

    def summary(self) -> Dict[str, Any]:
        """
        获取配置摘要（脱敏敏感字段）/ Get config summary (sensitive fields masked).

        Returns:
            摘要字典
        """
        flat = self.all_flat()
        return {
            "profile": self._profile,
            "frozen": self._frozen,
            "loaded_files": list(self._loaded_files),
            "entries": len(flat),
            "keys": sorted(flat.keys()),
            "preview": {
                k: _mask_sensitive(k, str(v)) for k, v in list(flat.items())[:20]
            },
        }

    def __repr__(self) -> str:
        return (
            f"<NonullConfig profile={self._profile!r} "
            f"frozen={self._frozen} entries={len(self.all_flat())}>"
        )

    # ---- 内部 ----

    def _assert_not_frozen(self) -> None:
        if self._frozen:
            raise RuntimeError("配置已冻结，无法修改 / Config is frozen, cannot modify")

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return self.get(key, _SENTINEL) is not _SENTINEL


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------

class _Missing:
    def __repr__(self):
        return "<MISSING>"


_SENTINEL = _Missing()


def _mask_sensitive(key: str, value: str) -> str:
    """脱敏敏感字段 / Mask sensitive fields."""
    if any(sk in key for sk in _SENSITIVE_KEYS):
        if len(value) > 8:
            return value[:4] + "****" + value[-4:]
        return "****"
    return value
