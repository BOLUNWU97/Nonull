"""
Internationalization (i18n) for Nonull / 多语言支持

Currently supports: en (English), zh (Chinese).
"""
from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": "Nonull — Universal AI Agent",
        "agent_disabled": "(Agent mode disabled — set NONULL_LLM_API_KEY to enable)",
        "no_agent": "[No agent bound — using fallback message]",
        "thinking": "Thinking...",
        "session_started": "Session started",
        "session_ended": "Session ended",
        "skills_loaded": "{n} skills loaded",
        "domain_active": "Active domain: {name}",
        "experimental_warning": "⚠️ Experimental feature — not production ready",
        "advisory_disclaimer": "ADVISORY ONLY — not a certified safety system",
    },
    "zh": {
        "welcome": "Nonull — 通用 AI 智能体",
        "agent_disabled": "（智能体模式未启用 — 设置 NONULL_LLM_API_KEY 启用）",
        "no_agent": "（未绑定智能体 — 使用回退消息）",
        "thinking": "思考中...",
        "session_started": "会话已开始",
        "session_ended": "会话已结束",
        "skills_loaded": "已加载 {n} 个技能",
        "domain_active": "当前领域: {name}",
        "experimental_warning": "⚠️ 实验性功能 — 未达到生产标准",
        "advisory_disclaimer": "仅作建议 — 不是经过认证的安全系统",
    },
}


class I18N:
    """Tiny i18n helper. Defaults to en if a key is missing."""

    def __init__(self, default_lang: str = "en"):
        self.default_lang = default_lang if default_lang in TRANSLATIONS else "en"

    def t(self, key: str, lang: str = None, **kwargs) -> str:
        lang = lang or self.default_lang
        if lang not in TRANSLATIONS:
            lang = "en"
        text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))
        try:
            return text.format(**kwargs)
        except KeyError:
            return text

    def set_lang(self, lang: str) -> None:
        if lang in TRANSLATIONS:
            self.default_lang = lang


_default = I18N()


def t(key: str, lang: str = None, **kwargs) -> str:
    """Module-level shortcut."""
    return _default.t(key, lang, **kwargs)


def set_lang(lang: str) -> None:
    _default.set_lang(lang)
