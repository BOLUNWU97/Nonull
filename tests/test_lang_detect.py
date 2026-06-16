"""
零依赖语言检测测试 / Tests for the zero-dependency language detector.

验证真实检测能力 (非占位): 脚本判定 (CJK/西里尔/阿拉伯等) + 拉丁系区分
(英/德/法/西/葡/意/荷)。$0, 无外部依赖。
"""
import pytest

from skills.core.lang_detect import detect_language


class TestScriptDetection:
    """非拉丁脚本判定。"""

    def test_chinese(self):
        r = detect_language("今天天气很好，我们去公园散步吧。")
        assert r["language"] == "zh"
        assert r["confidence"] > 0.5

    def test_japanese_kana(self):
        """有假名 → 日文 (即使混汉字)。"""
        r = detect_language("これはテストです。今日はいい天気ですね。")
        assert r["language"] == "ja"

    def test_korean(self):
        r = detect_language("안녕하세요. 오늘 날씨가 좋네요.")
        assert r["language"] == "ko"

    def test_russian(self):
        r = detect_language("Привет, как дела? Сегодня хорошая погода.")
        assert r["language"] == "ru"

    def test_arabic(self):
        r = detect_language("مرحبا، كيف حالك؟ الطقس جميل اليوم.")
        assert r["language"] == "ar"

    def test_greek(self):
        r = detect_language("Γεια σας, τι κάνετε; Ωραίος καιρός σήμερα.")
        assert r["language"] == "el"

    def test_chinese_vs_japanese_disambiguation(self):
        """纯汉字无假名 → 中文; 有假名 → 日文。"""
        zh = detect_language("我喜欢学习编程和算法")
        ja = detect_language("プログラミングが好きです")
        assert zh["language"] == "zh"
        assert ja["language"] == "ja"


class TestLatinLanguages:
    """拉丁系语言区分 (停用词 + 变音符号指纹)。"""

    def test_english(self):
        r = detect_language("The quick brown fox jumps over the lazy dog and it is a nice day.")
        assert r["language"] == "en"

    def test_german(self):
        r = detect_language("Der schnelle braune Fuchs ist nicht müde und das Wetter ist schön.")
        assert r["language"] == "de"

    def test_french(self):
        r = detect_language("Le chat est sur la table et le chien est dans le jardin avec une balle.")
        assert r["language"] == "fr"

    def test_spanish(self):
        r = detect_language("El gato está en la mesa y el perro está en el jardín con una pelota.")
        assert r["language"] == "es"

    def test_german_umlaut_signal(self):
        """变音符号 ä/ö/ü/ß 是德文强信号。"""
        r = detect_language("Schöne Grüße über die Straße für die Bücher.")
        assert r["language"] == "de"

    def test_english_not_misclassified(self):
        r = detect_language("I have been working on this project for a long time with great results.")
        assert r["language"] == "en"


class TestEdgeCases:
    def test_empty(self):
        r = detect_language("")
        assert r["language"] == "unknown"
        assert r["confidence"] == 0.0

    def test_whitespace_only(self):
        r = detect_language("   \n\t  ")
        assert r["language"] == "unknown"

    def test_numbers_only(self):
        """纯数字/符号 → 拉丁系兜底或 unknown, 不崩。"""
        r = detect_language("12345 67890 !@#$%")
        assert "language" in r

    def test_mixed_returns_dominant(self):
        """中英混合, 中文占多 → zh。"""
        r = detect_language("这是一段中文文本 with a little English mixed in 但主要是中文内容很多")
        assert r["language"] == "zh"

    def test_result_structure(self):
        r = detect_language("hello world")
        assert set(r.keys()) >= {"language", "confidence", "scripts", "candidates"}


class TestSkillIntegration:
    """通过 LanguageDetectorSkill 调用。"""

    def test_skill_execute(self):
        from skills.core.translation_skills import LanguageDetectorSkill
        skill = LanguageDetectorSkill()
        skill.activate()
        result = skill.execute({"text": "Bonjour le monde, comment allez-vous aujourd'hui?"})
        assert result.success
        assert result.data["language"] == "fr"

    def test_skill_metadata_not_demo(self):
        """metadata 描述不再标 DEMO (真实实现)。"""
        from skills.core.translation_skills import LanguageDetectorSkill
        meta = LanguageDetectorSkill().metadata
        assert "DEMO" not in meta.description
        assert meta.version == "0.2.0"

    def test_skill_backward_compat_field(self):
        """保留 char_distribution 字段 (向后兼容)。"""
        from skills.core.translation_skills import LanguageDetectorSkill
        skill = LanguageDetectorSkill()
        skill.activate()
        result = skill.execute({"text": "hello world"})
        assert "char_distribution" in result.data
