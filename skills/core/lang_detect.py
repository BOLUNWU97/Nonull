"""
零依赖语言检测引擎 / Zero-dependency language detection engine.

基于 Unicode 脚本判定 + 拉丁系语言的字符 n-gram / 停用词指纹, 区分:
  中文 zh · 日文 ja · 韩文 ko · 俄文 ru · 阿拉伯文 ar · 希腊文 el · 泰文 th ·
  英 en · 德 de · 法 fr · 西 es · 葡 pt · 意 it · 荷 nl

方法 (真实语言检测的简化经典做法, 无外部依赖):
  1. **脚本判定**: 非拉丁文字 (CJK/西里尔/阿拉伯/希腊/泰/假名/谚文) 直接按
     Unicode 区间高置信度判定; 并用日文假名/韩文谚文把 CJK 细分为 ja/ko/zh。
  2. **拉丁系区分**: 对拉丁字母语言, 用两路信号投票 —
     (a) 特殊字符/变音符号 (ñ→es, ß/ä/ü→de, ç/é/è→fr/pt, ã/õ→pt …)
     (b) 高频停用词指纹 (the/and→en, der/und→de, le/la/et→fr, el/de/que→es …)
  3. 综合打分给出 language + confidence + 候选分布。

这不是神经网络级别的检测器, 但对成段文本 (>20 字符) 准确度高, 且完全零依赖。

@module: skills.core.lang_detect
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Tuple

# ── 非拉丁脚本 Unicode 区间 ──────────────────────────────────────
_SCRIPT_RANGES = {
    "han":      r"[一-鿿㐀-䶿]",      # 汉字
    "hiragana": r"[぀-ゟ]",                    # 平假名 (日文标志)
    "katakana": r"[゠-ヿ]",                    # 片假名 (日文)
    "hangul":   r"[가-힯ᄀ-ᇿ]",       # 谚文 (韩文)
    "cyrillic": r"[Ѐ-ӿ]",                    # 西里尔 (俄文等)
    "arabic":   r"[؀-ۿݐ-ݿ]",       # 阿拉伯文
    "greek":    r"[Ͱ-Ͽ]",                    # 希腊文
    "thai":     r"[฀-๿]",                    # 泰文
    "hebrew":   r"[֐-׿]",                    # 希伯来文
    "latin":    r"[a-zA-ZÀ-ɏ]",              # 拉丁 (含变音符号)
}

# ── 拉丁系语言: 特征变音符号 ─────────────────────────────────────
_DIACRITIC_HINTS = {
    "es": "ñ¿¡áíóúü",
    "de": "äöüß",
    "fr": "àâçéèêëîïôûùüœ",
    "pt": "ãõâêôçáéí",
    "it": "àèéìòù",
    "nl": "ëïĳ",
}

# ── 拉丁系语言: 高频停用词指纹 ───────────────────────────────────
_STOPWORD_HINTS = {
    "en": {"the", "and", "is", "are", "of", "to", "in", "that", "it", "with", "for", "you", "this", "have"},
    "de": {"der", "die", "das", "und", "ist", "ein", "eine", "nicht", "mit", "für", "den", "von", "auch", "sich"},
    "fr": {"le", "la", "les", "et", "est", "un", "une", "des", "que", "pour", "dans", "avec", "sur", "pas"},
    "es": {"el", "la", "los", "las", "y", "es", "un", "una", "que", "de", "para", "con", "por", "como"},
    "pt": {"o", "a", "os", "as", "e", "é", "um", "uma", "que", "de", "para", "com", "não", "uma"},
    "it": {"il", "la", "lo", "le", "e", "è", "un", "una", "che", "di", "per", "con", "non", "sono"},
    "nl": {"de", "het", "een", "en", "is", "van", "dat", "die", "niet", "met", "voor", "op", "te", "zijn"},
}


def _script_counts(text: str) -> Dict[str, int]:
    return {name: len(re.findall(pat, text)) for name, pat in _SCRIPT_RANGES.items()}


def _latin_language(text: str) -> Tuple[str, float, Dict[str, float]]:
    """在拉丁字母文本中区分具体语言 (英/德/法/西/葡/意/荷)。"""
    low = text.lower()
    scores: Dict[str, float] = {lang: 0.0 for lang in _STOPWORD_HINTS}

    # 信号 1: 变音符号 (强信号)
    for lang, chars in _DIACRITIC_HINTS.items():
        hits = sum(low.count(c) for c in chars)
        if hits:
            scores.setdefault(lang, 0.0)
            scores[lang] += hits * 3.0

    # 信号 2: 停用词指纹 (主力信号)
    words = re.findall(r"[a-zà-ÿ]+", low)
    wset = Counter(words)
    total_words = max(len(words), 1)
    for lang, stops in _STOPWORD_HINTS.items():
        hit = sum(wset[w] for w in stops)
        scores[lang] += (hit / total_words) * 10.0

    if not any(scores.values()):
        return "en", 0.3, scores  # 无信号默认英文 (拉丁系最常见)

    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1.0
    conf = scores[best] / total
    return best, conf, scores


# 非拉丁脚本 → 语言 的直接映射 (高置信度)
_SCRIPT_LANG = {
    "cyrillic": "ru", "arabic": "ar", "greek": "el", "thai": "th", "hebrew": "he",
}


def detect_language(text: str) -> Dict:
    """检测文本主要语言 / Detect the dominant language of text.

    Returns:
        {language, confidence, scripts, candidates}
        language ∈ {zh, ja, ko, ru, ar, el, th, he, en, de, fr, es, pt, it, nl, unknown}
    """
    if not text or not text.strip():
        return {"language": "unknown", "confidence": 0.0, "scripts": {}, "candidates": {}}

    sc = _script_counts(text)
    total_script = sum(sc.values()) or 1

    # 1) 日文: 有假名 → ja (假名是日文独有, 即便混汉字)
    if sc["hiragana"] + sc["katakana"] > 0:
        kana = sc["hiragana"] + sc["katakana"]
        conf = min(1.0, (kana + sc["han"]) / total_script)
        return {"language": "ja", "confidence": round(conf, 3),
                "scripts": sc, "candidates": {"ja": conf}}

    # 2) 韩文: 有谚文 → ko
    if sc["hangul"] > 0:
        conf = sc["hangul"] / total_script
        return {"language": "ko", "confidence": round(conf, 3),
                "scripts": sc, "candidates": {"ko": conf}}

    # 3) 中文: 有汉字且无假名/谚文 → zh
    if sc["han"] > 0:
        conf = sc["han"] / total_script
        return {"language": "zh", "confidence": round(conf, 3),
                "scripts": sc, "candidates": {"zh": conf}}

    # 4) 其他非拉丁脚本直接判定
    for script, lang in _SCRIPT_LANG.items():
        if sc[script] > 0 and sc[script] >= sc["latin"]:
            conf = sc[script] / total_script
            return {"language": lang, "confidence": round(conf, 3),
                    "scripts": sc, "candidates": {lang: conf}}

    # 5) 拉丁系: 细分具体语言
    if sc["latin"] > 0:
        lang, conf, scores = _latin_language(text)
        # 候选分布归一化
        s_total = sum(scores.values()) or 1.0
        candidates = {k: round(v / s_total, 3) for k, v in sorted(
            scores.items(), key=lambda x: x[1], reverse=True) if v > 0}
        return {"language": lang, "confidence": round(conf, 3),
                "scripts": sc, "candidates": candidates}

    return {"language": "unknown", "confidence": 0.0, "scripts": sc, "candidates": {}}
