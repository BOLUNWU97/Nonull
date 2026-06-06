"""
Nonull — Package Setup
================================
智能体包配置 | Nonull Package Configuration

Nonull (智驾智能体) is a next-generation multi-channel agent framework
featuring a multi-channel gateway system, 5 built-in platform adapters
(Telegram / Feishu / DingTalk / WebSocket / HTTP), and a 40-hook lifecycle
system. Inspired by OpenClaw's gateway architecture, Hermes Agent's
platform adapters, and Claude Code's hook lifecycle.

Nonull (智驾智能体) 是新一代多通道智能体框架，具有多通道网关系统、
5 个内置平台适配器（Telegram / 飞书 / 钉钉 / WebSocket / HTTP）和
40 钩子生命周期系统。受 OpenClaw 的网关架构、Hermes Agent 的平台
适配器和 Claude Code 的钩子生命周期启发。

Core modules:
    channels      — Multi-channel communication gateway with 5 built-in platform adapters
    hooks         — Lifecycle hook system with 40 events and 4 execution types
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
    如果存在 README 则获取长描述。

    The README is the primary long description. The supplementary
    project files (CONTRIBUTING, CHANGELOG, INTERNAL-NOTES) are
    referenced inline so that PyPI / GitHub visitors can find
    development, history, and onboarding docs in one place.
    """
    readme_path = HERE / "README.md"
    contributing_path = HERE / "CONTRIBUTING.md"
    changelog_path = HERE / "CHANGELOG.md"
    internal_notes_path = HERE / "INTERNAL-NOTES.md"

    if readme_path.exists():
        body = readme_path.read_text(encoding="utf-8")
    else:
        body = "Nonull - Multi-Channel Agent Framework / 多通道智能体框架"

    extras = []
    if contributing_path.exists():
        extras.append(
            "\n\n## Contributing / 贡献指南\n\n"
            "See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, "
            "code style, testing, and the marketing copy red lines."
        )
    if changelog_path.exists():
        extras.append(
            "\n\n## Release history / 发布历史\n\n"
            "See [CHANGELOG.md](CHANGELOG.md) for the full release history "
            "(Keep a Changelog format)."
        )
    if internal_notes_path.exists():
        extras.append(
            "\n\n## First-day setup / 首日上手\n\n"
            "New engineers should read [INTERNAL-NOTES.md](INTERNAL-NOTES.md) "
            "for LLM setup, the three workflows, and known limitations."
        )

    return body + "".join(extras)


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------

INSTALL_REQUIRES = [
    # Core
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "numpy>=1.24",

    # CLI rich formatting (default install — CLI is the primary entrypoint)
    "rich>=13.0",

    # HTTP client for LLM provider integrations (default install)
    "httpx>=0.27,<0.29",

    # CLI channel extras (optional — prompt_toolkit is heavier):
    # "prompt_toolkit>=3.0.0", # Enhanced REPL

    # HTTP client/server (optional, for HTTP-based adapters):
    # "aiohttp>=3.9.0",       # Async HTTP client/server

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
    "web": [
        "fastapi>=0.100",
        "uvicorn>=0.23",
        "jinja2>=3.1",
    ],
    "all": [
        "prompt_toolkit>=3.0.0",
        "aiohttp>=3.9.0",
        "websockets>=12.0",
        "mcp>=1.0.0",
        "python-telegram-bot>=20.0",
        "lark-oapi>=1.0.0",
        "dingtalk-sdk>=2.0.0",
        "fastapi>=0.100",
        "uvicorn>=0.23",
        "jinja2>=3.1",
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
    name="nonull",
    version=_get_version(),
    author="Nonull Team",
    author_email="dev@nonull.ai",
    description=(
        "Nonull - Multi-Channel Agent Framework / 多通道智能体框架. "
        "Multi-channel gateway + 5 built-in platform adapters + 40 lifecycle hooks."
    ),
    long_description=_get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/BOLUNWU97/Nonull",
    project_urls={
        "Documentation": "https://github.com/BOLUNWU97/Nonull",
        "Source": "https://github.com/BOLUNWU97/Nonull",
        "Bug Tracker": "https://github.com/BOLUNWU97/Nonull/issues",
    },
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
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
        exclude=[
            "tests", "tests.*",
            "docs", "docs.*",
            "examples", "examples.*",
            "experimental", "experimental.*",
            "consciousness", "consciousness.*",
            "evolution", "evolution.*",
            # P15: domain packages (domains, domains.adas, domains.general)
            # are picked up by find_packages automatically — they are part
            # of the shipped package set and need no explicit allowlist.
        ]
    ),
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points={
        "console_scripts": [
            "nonull=channels.cli:main",
        ],
    },
    zip_safe=False,
)
