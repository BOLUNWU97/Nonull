"""
Nonull — Package Setup
================================
智能体包配置 | Nonull Package Configuration

Nonull (智驾智能体) is a next-generation multi-channel agent framework
featuring a multi-channel gateway system, 20+ platform adapters, and a
28-hook lifecycle system. Inspired by OpenClaw's gateway architecture,
Hermes Agent's platform adapters, and Claude Code's hook lifecycle.

Nonull (智驾智能体) 是新一代多通道智能体框架，具有多通道网关系统、
20+ 平台适配器和 28 钩子生命周期系统。受 OpenClaw 的网关架构、
Hermes Agent 的平台适配器和 Claude Code 的钩子生命周期启发。

Core modules:
    channels      — Multi-channel communication gateway with platform adapters
    hooks         — Lifecycle hook system with 28 events and 4 execution types
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from setuptools import find_packages, setup

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent.resolve()

def _get_version() -> str:
    """Read version from core package __init__.
    从 core 包的 __init__ 读取版本号。"""
    init_path = HERE / "core" / "__init__.py"
    if init_path.exists():
        content = init_path.read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    return "0.1.0"

def _get_long_description() -> str:
    """Get the long description from README if available.
    如果存在 README 则获取长描述。"""
    readme_path = HERE / "README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding="utf-8")
    return "Nonull - Multi-Channel Agent Framework / 多通道智能体框架"


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------

INSTALL_REQUIRES = [
    # Core
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "numpy>=1.24",

    # CLI channel extras (optional, but recommended):
    # "rich>=13.0.0",         # Rich text formatting
    # "prompt_toolkit>=3.0.0", # Enhanced REPL

    # HTTP client (optional, for HTTP-based adapters):
    # "aiohttp>=3.9.0",       # Async HTTP client/server
    # "httpx>=0.25.0",        # Alternative HTTP client

    # WebSocket (optional):
    # "websockets>=12.0",     # WebSocket server/client

    # MCP (optional):
    # "mcp>=1.0.0",           # Model Context Protocol client

    # Feishu/Lark (optional):
    # "lark-oapi>=1.0.0",     # Feishu Open API SDK

    # DingTalk (optional):
    # "dingtalk-sdk>=2.0.0",  # DingTalk SDK
]

EXTRAS_REQUIRE = {
    "cli": [
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0",
    ],
    "http": [
        "aiohttp>=3.9.0",
    ],
    "websocket": [
        "websockets>=12.0",
    ],
    "mcp": [
        "mcp>=1.0.0",
    ],
    "telegram": [
        "python-telegram-bot>=20.0",
    ],
    "feishu": [
        "lark-oapi>=1.0.0",
    ],
    "dingtalk": [
        "dingtalk-sdk>=2.0.0",
    ],
    "all": [
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0",
        "aiohttp>=3.9.0",
        "websockets>=12.0",
        "mcp>=1.0.0",
    ],
    "dev": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "mypy>=1.0.0",
        "ruff>=0.1.0",
        "pre-commit>=3.0.0",
    ],
}

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup(
    name="Nonull",
    version=_get_version(),
    author="Nonull Team",
    author_email="dev@Nonull.ai",
    description=(
        "Nonull - Multi-Channel Agent Framework / 多通道智能体框架. "
        "Multi-channel gateway + 20+ platform adapters + 28 lifecycle hooks."
    ),
    long_description=_get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/BOLUNWU97/nonull",
    project_urls={
        "Documentation": "https://github.com/BOLUNWU97/nonull",
        "Source": "https://github.com/BOLUNWU97/nonull",
        "Bug Tracker": "https://github.com/BOLUNWU97/nonull/issues",
    },
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Communications :: Chat",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Typing :: Typed",
    ],
    python_requires=">=3.10",
    packages=find_packages(
        exclude=["tests", "tests.*", "docs", "docs.*", "examples", "examples.*"]
    ),
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points={
        "console_scripts": [
            "Nonull=channels.cli:main",
        ],
    },
    zip_safe=False,
)
