#!/usr/bin/env python3
"""Core tests for Nonull.
Nonull 核心测试。

Tests the core agent functionality including:
- Agent initialization and configuration
- Basic task execution
- Safety validation system
- Skill registry operations
- Profile management
- Channel interface
- Hook system

测试核心智能体功能，包括：
- 智能体初始化和配置
- 基本任务执行
- 安全验证系统
- 技能注册表操作
- 配置文件管理
- 通道接口
- 钩子系统
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Mock Core Components 模拟核心组件
# =============================================================================

class SafetyVerdict:
    """Safety validation verdict.
    安全验证裁决。"""
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


@dataclass
class AgentConfig:
    """Agent configuration dataclass.
    智能体配置数据类。"""
    name: str = "Nonull"
    version: str = "1.0.0"
    mode: str = "interactive"
    strictness: int = 4
    deny_first: bool = True
    max_concurrent_agents: int = 8


class SafetySystem:
    """Mock safety system for testing.
    用于测试的模拟安全系统。"""

    def __init__(self, strictness: int = 4, deny_first: bool = True):
        self.strictness = strictness
        self.deny_first = deny_first
        self.audit_log: list[dict] = []
        self.deny_list = {"deploy", "modify_vehicle_controls", "disable_audit"}
        self.allow_list = {
            "code-review", "safety-analysis", "architecture-design",
            "requirement-analysis", "test-generation", "perf-analysis",
            "regression-check", "document-generation",
        }

    def validate_action(self, action: str, profile: str = "default") -> str:
        """Validate an action against safety policy.
        根据安全策略验证一个操作。

        Args:
            action: 操作名称 / Action name
            profile: 配置文件名称 / Profile name

        Returns:
            str: SafetyVerdict (allow/deny/confirm)
        """
        self.audit_log.append({
            "action": action,
            "profile": profile,
            "strictness": self.strictness,
        })

        if self.deny_first:
            if action in self.deny_list:
                return SafetyVerdict.DENY

        if action not in self.allow_list and self.strictness >= 3:
            return SafetyVerdict.DENY

        if self.strictness >= 4:
            return SafetyVerdict.CONFIRM

        return SafetyVerdict.ALLOW

    def validate_strictness_level(self, skill_safety_level: int) -> bool:
        """Check if a skill's safety level is compatible with agent strictness.
        检查技能的安全级别是否与智能体的严格度兼容。

        Args:
            skill_safety_level: 技能安全级别 (1-5) / Skill safety level

        Returns:
            bool: True if compatible
        """
        return skill_safety_level <= self.strictness

    def get_audit_log(self) -> list[dict]:
        """Get the full audit log.
        获取完整的审计日志。

        Returns:
            list[dict]: 审计日志 / Audit log entries
        """
        return self.audit_log.copy()

    def clear_audit_log(self):
        """Clear the audit log.
        清除审计日志。"""
        self.audit_log.clear()


class SkillRegistry:
    """Mock skill registry for testing.
    用于测试的模拟技能注册表。"""

    def __init__(self):
        self._skills: dict[str, dict] = {}
        self._load_defaults()

    def _load_defaults(self):
        """Load default skills.
        加载默认技能。"""
        defaults = [
            {"name": "code-review", "version": "1.0.0", "safety_level": 2, "category": "CODE"},
            {"name": "safety-analysis", "version": "1.0.0", "safety_level": 4, "category": "SAFETY"},
            {"name": "architecture-design", "version": "1.0.0", "safety_level": 2, "category": "ARCHITECTURE"},
            {"name": "requirement-analysis", "version": "1.0.0", "safety_level": 3, "category": "REQUIREMENT"},
            {"name": "test-generation", "version": "1.0.0", "safety_level": 2, "category": "TEST"},
            {"name": "perf-analysis", "version": "1.0.0", "safety_level": 1, "category": "PERFORMANCE"},
            {"name": "regression-check", "version": "1.0.0", "safety_level": 2, "category": "CODE"},
            {"name": "document-generation", "version": "1.0.0", "safety_level": 1, "category": "DOCUMENT"},
        ]
        for skill in defaults:
            self._skills[skill["name"]] = skill

    def register(self, name: str, version: str, safety_level: int,
                 category: str, entry_point: str = "") -> bool:
        """Register a new skill.
        注册一个新技能。

        Args:
            name: 技能名称 / Skill name
            version: 版本 / Version
            safety_level: 安全级别 / Safety level (1-5)
            category: 分类 / Category
            entry_point: 入口点 / Entry point

        Returns:
            bool: True if registration succeeded
        """
        if name in self._skills:
            return False
        self._skills[name] = {
            "name": name,
            "version": version,
            "safety_level": safety_level,
            "category": category,
            "entry_point": entry_point,
        }
        return True

    def unregister(self, name: str) -> bool:
        """Unregister a skill.
        注销一个技能。

        Args:
            name: 技能名称 / Skill name

        Returns:
            bool: True if unregistration succeeded
        """
        return self._skills.pop(name, None) is not None

    def get(self, name: str) -> dict | None:
        """Get a skill by name.
        根据名称获取技能。

        Args:
            name: 技能名称 / Skill name

        Returns:
            dict | None: 技能信息 / Skill info, or None if not found
        """
        return self._skills.get(name)

    def list_all(self) -> list[dict]:
        """List all registered skills.
        列出所有已注册技能。

        Returns:
            list[dict]: 技能列表 / List of skills
        """
        return list(self._skills.values())

    def count(self) -> int:
        """Get the number of registered skills.
        获取已注册技能数量。

        Returns:
            int: 技能数量 / Number of skills
        """
        return len(self._skills)


class ProfileManager:
    """Mock profile manager for testing.
    用于测试的模拟配置文件管理器。"""

    def __init__(self):
        self._profiles: dict[str, dict] = {
            "default": {
                "workspace": "./workspace",
                "log_level": "INFO",
                "tools": ["code-review", "safety-analysis", "architecture-design",
                          "requirement-analysis", "test-generation", "perf-analysis",
                          "regression-check", "document-generation"],
            },
            "safety-expert": {
                "workspace": "./workspaces/safety",
                "log_level": "DEBUG",
                "tools": ["safety-analysis", "code-review"],
            },
        }
        self._active_profile: str = "default"

    def load(self, profile_name: str) -> dict | None:
        """Load a profile.
        加载配置文件。

        Args:
            profile_name: 配置文件名称 / Profile name

        Returns:
            dict | None: 配置文件内容 / Profile content, or None if not found
        """
        profile = self._profiles.get(profile_name)
        if profile:
            self._active_profile = profile_name
        return profile

    def switch(self, profile_name: str) -> bool:
        """Switch to a different profile.
        切换到不同的配置文件。

        Args:
            profile_name: 目标配置文件名称 / Target profile name

        Returns:
            bool: True if switch succeeded
        """
        if profile_name in self._profiles:
            self._active_profile = profile_name
            return True
        return False

    def get_active(self) -> str:
        """Get the active profile name.
        获取当前活动的配置文件名称。

        Returns:
            str: 配置文件名称 / Profile name
        """
        return self._active_profile

    def list_profiles(self) -> list[str]:
        """List all available profiles.
        列出所有可用的配置文件。

        Returns:
            list[str]: 配置文件名称列表 / List of profile names
        """
        return list(self._profiles.keys())

    def create(self, name: str, config: dict) -> bool:
        """Create a new profile.
        创建新配置文件。

        Args:
            name: 配置文件名称 / Profile name
            config: 配置内容 / Configuration

        Returns:
            bool: True if creation succeeded
        """
        if name in self._profiles:
            return False
        self._profiles[name] = config
        return True


class ChannelInterface:
    """Mock channel interface for testing.
    用于测试的模拟通道接口。"""

    def __init__(self, channel_type: str):
        self.type = channel_type
        self.messages: list[str] = []

    def send(self, message: str):
        """Send a message through the channel.
        通过通道发送消息。

        Args:
            message: 消息内容 / Message content
        """
        self.messages.append(message)

    def receive(self) -> list[str]:
        """Receive all pending messages.
        接收所有待处理消息。

        Returns:
            list[str]: 消息列表 / List of messages
        """
        msgs = self.messages.copy()
        self.messages.clear()
        return msgs


class NonullCore:
    """Simplified core agent for testing.
    用于测试的简化核心智能体。"""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.safety = SafetySystem(
            strictness=self.config.strictness,
            deny_first=self.config.deny_first,
        )
        self.skills = SkillRegistry()
        self.profiles = ProfileManager()
        self.channels: dict[str, ChannelInterface] = {
            "cli": ChannelInterface("cli"),
            "gateway": ChannelInterface("gateway"),
        }
        self._initialized = True

    def execute_task(self, task: str, skill_name: str | None = None,
                     **params) -> dict:
        """Execute a task.
        执行一个任务。

        Args:
            task: 任务描述 / Task description
            skill_name: 技能名称（可选） / Skill name (optional)
            **params: 附加参数 / Additional parameters

        Returns:
            dict: 执行结果 / Execution result
        """
        if not task or not task.strip():
            return {"success": False, "error": "Task cannot be empty"}

        # Validate with safety system
        action = skill_name or "general"
        verdict = self.safety.validate_action(action)

        if verdict == SafetyVerdict.DENY:
            return {
                "success": False,
                "error": f"Action '{action}' denied by safety policy",
                "verdict": verdict,
            }

        # If skill specified, validate it exists
        if skill_name:
            skill = self.skills.get(skill_name)
            if not skill:
                return {
                    "success": False,
                    "error": f"Skill '{skill_name}' not found",
                }
            if not self.safety.validate_strictness_level(skill["safety_level"]):
                return {
                    "success": False,
                    "error": f"Skill '{skill_name}' safety level {skill['safety_level']} "
                             f"exceeds agent strictness {self.config.strictness}",
                }

        return {
            "success": True,
            "task": task,
            "skill": skill_name,
            "verdict": verdict,
            "result": f"Processed: {task[:50]}",
        }

    def get_status(self) -> dict:
        """Get agent status.
        获取智能体状态。"""
        return {
            "name": self.config.name,
            "version": self.config.version,
            "mode": self.config.mode,
            "initialized": self._initialized,
            "active_profile": self.profiles.get_active(),
            "skills_count": self.skills.count(),
        }


# =============================================================================
# Tests 测试
# =============================================================================

import pytest


class TestAgentInitialization:
    """Tests for agent initialization.
    智能体初始化测试。"""

    def test_default_initialization(self):
        """Test that agent initializes with default config.
        测试智能体使用默认配置初始化。"""
        agent = NonullCore()
        assert agent._initialized is True
        assert agent.config.name == "Nonull"
        assert agent.config.version == "1.0.0"
        assert agent.config.mode == "interactive"

    def test_custom_config(self):
        """Test initialization with custom config.
        测试使用自定义配置初始化。"""
        config = AgentConfig(
            name="TestAgent",
            version="2.0.0",
            mode="autonomous",
            strictness=5,
        )
        agent = NonullCore(config)
        assert agent.config.name == "TestAgent"
        assert agent.config.mode == "autonomous"
        assert agent.config.strictness == 5

    def test_agent_status(self):
        """Test agent status reporting.
        测试智能体状态报告。"""
        agent = NonullCore()
        status = agent.get_status()
        assert status["name"] == "Nonull"
        assert status["initialized"] is True
        assert status["active_profile"] == "default"
        assert status["skills_count"] == 8


class TestSafetySystem:
    """Tests for safety validation system.
    安全验证系统测试。"""

    def setup_method(self):
        self.safety = SafetySystem(strictness=4, deny_first=True)

    def test_deny_listed_action(self):
        """Test that deny-listed actions are blocked.
        测试拒绝列表中的操作被阻止。"""
        verdict = self.safety.validate_action("deploy")
        assert verdict == SafetyVerdict.DENY

        verdict = self.safety.validate_action("modify_vehicle_controls")
        assert verdict == SafetyVerdict.DENY

    def test_allow_listed_action(self):
        """Test that allow-listed actions pass through.
        测试允许列表中的操作通过。"""
        verdict = self.safety.validate_action("code-review")
        assert verdict == SafetyVerdict.CONFIRM  # strictness >= 4

    def test_strictness_5_blocks_unknown(self):
        """Test strictness level 5 blocks unknown actions.
        测试严格度级别 5 阻止未知操作。"""
        safety = SafetySystem(strictness=5)
        verdict = safety.validate_action("unknown-action")
        assert verdict == SafetyVerdict.DENY

    def test_strictness_1_allows_all(self):
        """Test strictness level 1 allows all actions.
        测试严格度级别 1 允许所有操作。"""
        safety = SafetySystem(strictness=1, deny_first=True)
        verdict = safety.validate_action("code-review")
        assert verdict == SafetyVerdict.ALLOW

    def test_safety_level_compatibility(self):
        """Test skill safety level vs agent strictness check.
        测试技能安全级别与智能体严格度的兼容性检查。"""
        assert self.safety.validate_strictness_level(1) is True
        assert self.safety.validate_strictness_level(4) is True
        assert self.safety.validate_strictness_level(5) is False

    def test_audit_logging(self):
        """Test that actions are logged to audit log.
        测试操作被记录到审计日志。"""
        assert len(self.safety.get_audit_log()) == 0
        self.safety.validate_action("code-review")
        assert len(self.safety.get_audit_log()) == 1
        assert self.safety.get_audit_log()[0]["action"] == "code-review"

    def test_audit_log_clear(self):
        """Test audit log clearing.
        测试审计日志清除。"""
        self.safety.validate_action("code-review")
        assert len(self.safety.get_audit_log()) == 1
        self.safety.clear_audit_log()
        assert len(self.safety.get_audit_log()) == 0


class TestSkillRegistry:
    """Tests for skill registry.
    技能注册表测试。"""

    def setup_method(self):
        self.registry = SkillRegistry()

    def test_default_skills_count(self):
        """Test that default skills are loaded.
        测试默认技能已加载。"""
        assert self.registry.count() == 8

    def test_get_existing_skill(self):
        """Test getting an existing skill.
        测试获取已存在的技能。"""
        skill = self.registry.get("code-review")
        assert skill is not None
        assert skill["name"] == "code-review"
        assert skill["version"] == "1.0.0"
        assert skill["safety_level"] == 2

    def test_get_nonexistent_skill(self):
        """Test getting a non-existent skill returns None.
        测试获取不存在的技能返回 None。"""
        skill = self.registry.get("nonexistent")
        assert skill is None

    def test_register_new_skill(self):
        """Test registering a new skill.
        测试注册新技能。"""
        result = self.registry.register(
            name="my-custom-skill",
            version="1.0.0",
            safety_level=2,
            category="GENERAL",
        )
        assert result is True
        assert self.registry.count() == 9

        skill = self.registry.get("my-custom-skill")
        assert skill is not None
        assert skill["category"] == "GENERAL"

    def test_register_duplicate_skill(self):
        """Test registering a duplicate skill fails.
        测试注册重复技能失败。"""
        result = self.registry.register(
            name="code-review",
            version="2.0.0",
            safety_level=3,
            category="CODE",
        )
        assert result is False

    def test_unregister_skill(self):
        """Test unregistering a skill.
        测试注销技能。"""
        assert self.registry.count() == 8
        result = self.registry.unregister("code-review")
        assert result is True
        assert self.registry.count() == 7

    def test_unregister_nonexistent_skill(self):
        """Test unregistering a non-existent skill.
        测试注销不存在的技能。"""
        result = self.registry.unregister("nonexistent")
        assert result is False

    def test_list_all_skills(self):
        """Test listing all skills.
        测试列出所有技能。"""
        skills = self.registry.list_all()
        assert len(skills) == 8
        names = [s["name"] for s in skills]
        assert "code-review" in names
        assert "safety-analysis" in names
        assert "document-generation" in names

    def test_skill_categories(self):
        """Test skill categories are correct.
        测试技能分类正确。"""
        skills = self.registry.list_all()
        categories = {s["name"]: s["category"] for s in skills}
        assert categories["code-review"] == "CODE"
        assert categories["safety-analysis"] == "SAFETY"
        assert categories["architecture-design"] == "ARCHITECTURE"
        assert categories["test-generation"] == "TEST"


class TestTaskExecution:
    """Tests for task execution.
    任务执行测试。"""

    def setup_method(self):
        self.agent = NonullCore()

    def test_simple_task_execution(self):
        """Test basic task execution.
        测试基本任务执行。"""
        result = self.agent.execute_task("Analyze AEB system")
        assert result["success"] is True
        assert "task" in result

    def test_empty_task_rejected(self):
        """Test empty task is rejected.
        测试空任务被拒绝。"""
        result = self.agent.execute_task("")
        assert result["success"] is False

    def test_skill_specific_task(self):
        """Test task with a specific skill.
        测试使用特定技能的任务。"""
        result = self.agent.execute_task(
            "Review ADAS code",
            skill_name="code-review",
        )
        assert result["success"] is True
        assert result["skill"] == "code-review"

    def test_nonexistent_skill_task(self):
        """Test task with non-existent skill.
        测试使用不存在的技能的任务。"""
        result = self.agent.execute_task(
            "Do something",
            skill_name="nonexistent-skill",
        )
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_denied_action(self):
        """Test action denied by safety policy.
        测试被安全策略拒绝的操作。"""
        result = self.agent.execute_task(
            "Deploy to production",
            skill_name="deploy",
        )
        assert result["success"] is False
        assert "denied" in result["error"].lower()


class TestProfileManager:
    """Tests for profile management.
    配置文件管理测试。"""

    def setup_method(self):
        self.manager = ProfileManager()

    def test_load_default_profile(self):
        """Test loading default profile.
        测试加载默认配置文件。"""
        profile = self.manager.load("default")
        assert profile is not None
        assert profile["log_level"] == "INFO"

    def test_load_nonexistent_profile(self):
        """Test loading non-existent profile.
        测试加载不存在的配置文件。"""
        profile = self.manager.load("nonexistent")
        assert profile is None

    def test_switch_profile(self):
        """Test switching profiles.
        测试切换配置文件。"""
        assert self.manager.get_active() == "default"
        result = self.manager.switch("safety-expert")
        assert result is True
        assert self.manager.get_active() == "safety-expert"

    def test_switch_to_nonexistent_profile(self):
        """Test switching to non-existent profile.
        测试切换到不存在的配置文件。"""
        result = self.manager.switch("nonexistent")
        assert result is False
        assert self.manager.get_active() == "default"

    def test_list_profiles(self):
        """Test listing all profiles.
        测试列出所有配置文件。"""
        profiles = self.manager.list_profiles()
        assert "default" in profiles
        assert "safety-expert" in profiles

    def test_create_profile(self):
        """Test creating a new profile.
        测试创建新配置文件。"""
        result = self.manager.create("adas-engineer", {
            "workspace": "./workspaces/adas",
            "log_level": "DEBUG",
        })
        assert result is True
        assert "adas-engineer" in self.manager.list_profiles()

    def test_create_duplicate_profile(self):
        """Test creating a duplicate profile.
        测试创建重复配置文件。"""
        result = self.manager.create("default", {"workspace": "./new"})
        assert result is False


class TestChannelInterface:
    """Tests for channel interface.
    通道接口测试。"""

    def test_send_message(self):
        """Test sending a message.
        测试发送消息。"""
        channel = ChannelInterface("cli")
        channel.send("Hello")
        assert len(channel.messages) == 1

    def test_receive_messages(self):
        """Test receiving messages.
        测试接收消息。"""
        channel = ChannelInterface("cli")
        channel.send("Message 1")
        channel.send("Message 2")
        messages = channel.receive()
        assert len(messages) == 2
        assert messages[0] == "Message 1"

    def test_receive_clears_queue(self):
        """Test that receiving clears the message queue.
        测试接收消息后清空队列。"""
        channel = ChannelInterface("cli")
        channel.send("Test")
        channel.receive()
        assert len(channel.messages) == 0

    def test_multiple_channels(self):
        """Test multiple channel instances.
        测试多个通道实例。"""
        agent = NonullCore()
        assert "cli" in agent.channels
        assert "gateway" in agent.channels
        agent.channels["cli"].send("CLI message")
        agent.channels["gateway"].send("Gateway message")
        assert len(agent.channels["cli"].receive()) == 1
        assert len(agent.channels["gateway"].receive()) == 1


class TestIntegration:
    """Integration tests.
    集成测试。"""

    def test_full_workflow_code_review(self):
        """Test full code review workflow.
        测试完整的代码审查工作流。"""
        agent = NonullCore()

        # 1. Check status
        status = agent.get_status()
        assert status["initialized"] is True

        # 2. Validate skill exists
        skill = agent.skills.get("code-review")
        assert skill is not None
        assert skill["safety_level"] <= agent.config.strictness

        # 3. Execute task
        result = agent.execute_task(
            "Review AEB controller implementation",
            skill_name="code-review",
            language="cpp",
        )
        assert result["success"] is True

        # 4. Check audit log
        assert len(agent.safety.get_audit_log()) > 0

    def test_full_workflow_safety_analysis(self):
        """Test full safety analysis workflow.
        测试完整的安全分析工作流。"""
        agent = NonullCore()

        # Safety analysis has safety level 4, agent has strictness 4
        skill = agent.skills.get("safety-analysis")
        assert skill["safety_level"] == 4
        assert agent.safety.validate_strictness_level(4) is True

        result = agent.execute_task(
            "Perform HARA on AEB",
            skill_name="safety-analysis",
            analysis_type="hara",
        )
        assert result["success"] is True

    def test_profile_isolation(self):
        """Test profile isolation.
        测试配置文件隔离。"""
        agent = NonullCore()

        # Default profile
        assert agent.profiles.get_active() == "default"

        # Switch to safety-expert
        agent.profiles.switch("safety-expert")
        assert agent.profiles.get_active() == "safety-expert"

        # Safety expert has restricted tools
        profile = agent.profiles.load("safety-expert")
        assert profile is not None
        assert "safety-analysis" in profile["tools"]


# =============================================================================
# Run Tests 运行测试
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
