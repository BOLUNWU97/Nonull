"""Tests for multimodal skills / 多模态技能测试."""
import os
import sys
import struct
import tempfile
import wave
from pathlib import Path

import pytest

# Ensure project root is importable when running pytest from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.registry import SkillRegistry
from skills.base import BaseSkill, SkillResult


# ---------------------------------------------------------------------------
# Helpers / 辅助函数
# ---------------------------------------------------------------------------


def _make_minimal_png(width: int = 100, height: int = 200) -> Path:
    """Create a minimal valid PNG file (no PIL needed) for testing.

    Builds: signature + IHDR chunk (length + type + data + crc) + IEND chunk.
    """
    png_signature = b"\x89PNG\r\n\x1a\n"
    # IHDR data: 13 bytes - width(4) height(4) bit_depth(1) color_type(1)
    #            compression(1) filter(1) interlace(1)
    ihdr_data = struct.pack(
        ">IIBBBBB", width, height, 8, 2, 0, 0, 0
    )  # 8-bit RGB
    ihdr_crc = b"\x00" * 4  # fake CRC (PNG parsers may not check this)
    ihdr = (
        struct.pack(">I", len(ihdr_data))
        + b"IHDR"
        + ihdr_data
        + ihdr_crc
    )
    # IEND chunk
    iend = struct.pack(">I", 0) + b"IEND" + b"\x00" * 4

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(png_signature)
    tmp.write(ihdr)
    tmp.write(iend)
    tmp.close()
    return Path(tmp.name)


def _make_minimal_jpeg(width: int = 320, height: int = 240) -> Path:
    """Create a minimal JPEG file (SOI + SOF0 + EOI)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    # SOI
    tmp.write(b"\xff\xd8")
    # SOF0 marker (length 11, 8-bit precision)
    sof_data = struct.pack(">BHH", 8, height, width) + b"\x03\x01\x00\x02\x11\x03"
    tmp.write(b"\xff\xc0")
    tmp.write(struct.pack(">H", len(sof_data) + 2))
    tmp.write(sof_data)
    # EOI
    tmp.write(b"\xff\xd9")
    tmp.close()
    return Path(tmp.name)


def _make_minimal_gif(width: int = 50, height: int = 30) -> Path:
    """Create a minimal GIF89a file (header + logical screen descriptor)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
    tmp.write(b"GIF89a")
    tmp.write(struct.pack("<HH", width, height))  # logical screen size
    tmp.write(b"\x00" * 3)  # packed field, bg color, aspect ratio
    tmp.close()
    return Path(tmp.name)


def _make_minimal_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> Path:
    """Create a minimal valid WAV file (sine wave)."""
    n_frames = int(duration_s * sample_rate)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 1-second silence (all zeros)
        wf.writeframes(b"\x00" * (n_frames * 2))
    return Path(tmp.name)


def _make_minimal_pdf(n_pages: int = 3) -> Path:
    """Create a minimal PDF with the given number of /Type /Page entries."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(b"%PDF-1.4\n")
    body = b"1 0 obj\n<<>>\nendobj\n"
    # Append enough /Type /Page markers to estimate page count
    for _ in range(n_pages):
        body += b"<< /Type /Page /Parent 0 0 R >>\n"
    tmp.write(body)
    tmp.write(b"%%EOF\n")
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Image skills
# ---------------------------------------------------------------------------


def test_image_info_png():
    """ImageInfoSkill should report width/height/format for a PNG."""
    from skills.multimodal.image_skills import ImageInfoSkill

    path = _make_minimal_png(100, 200)
    try:
        skill = ImageInfoSkill()
        skill.activate()
        result = skill.execute({"path": str(path)})
        assert result.success
        assert result.data["format"] == "png"
        assert result.data["width"] == 100
        assert result.data["height"] == 200
    finally:
        path.unlink()


def test_image_info_jpeg():
    """ImageInfoSkill should report width/height/format for a JPEG."""
    from skills.multimodal.image_skills import ImageInfoSkill

    path = _make_minimal_jpeg(320, 240)
    try:
        skill = ImageInfoSkill()
        skill.activate()
        result = skill.execute({"path": str(path)})
        assert result.success
        assert result.data["format"] == "jpeg"
        assert result.data["width"] == 320
        assert result.data["height"] == 240
    finally:
        path.unlink()


def test_image_info_gif():
    """ImageInfoSkill should report width/height/format for a GIF."""
    from skills.multimodal.image_skills import ImageInfoSkill

    path = _make_minimal_gif(50, 30)
    try:
        skill = ImageInfoSkill()
        skill.activate()
        result = skill.execute({"path": str(path)})
        assert result.success
        assert result.data["format"] == "gif"
        assert result.data["width"] == 50
        assert result.data["height"] == 30
    finally:
        path.unlink()


def test_image_info_missing_file():
    """ImageInfoSkill should report an error if the file is missing."""
    from skills.multimodal.image_skills import ImageInfoSkill

    skill = ImageInfoSkill()
    skill.activate()
    result = skill.execute({"path": "/no/such/file.png"})
    assert result.success
    assert "error" in result.data


def test_image_base64_round_trip():
    """ImageBase64Skill should encode and the size should match base64 length."""
    import base64 as _b64
    from skills.multimodal.image_skills import ImageBase64Skill

    path = _make_minimal_png(10, 10)
    try:
        skill = ImageBase64Skill()
        skill.activate()
        result = skill.execute({"path": str(path)})
        assert result.success
        # Mime type should include image/<ext>
        assert result.data["mime_type"].startswith("image/")
        # Round-trip the base64
        decoded = _b64.b64decode(result.data["base64"])
        assert decoded == path.read_bytes()
    finally:
        path.unlink()


def test_image_resize_stub():
    """If Pillow is not installed, ImageResizeSkill returns a stub warning."""
    from skills.multimodal.image_skills import ImageResizeSkill

    skill = ImageResizeSkill()
    skill.activate()
    # Force the stub path by making Pillow import fail
    import builtins
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PIL.Image" or name.startswith("PIL"):
            raise ImportError("fake: PIL not available")
        return original_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        result = skill.execute({"path": "/x.png", "width": 100})
        assert result.success
        assert result.data.get("stub") is True
    finally:
        builtins.__import__ = original_import


# ---------------------------------------------------------------------------
# PDF skills
# ---------------------------------------------------------------------------


def test_pdf_info_valid():
    """PdfInfoSkill should report valid + page count estimate."""
    from skills.multimodal.pdf_skills import PdfInfoSkill

    path = _make_minimal_pdf(n_pages=3)
    try:
        skill = PdfInfoSkill()
        skill.activate()
        result = skill.execute({"path": str(path)})
        assert result.success
        assert result.data["valid"] is True
        assert "pdf_version" in result.data
        assert result.data["page_count_estimate"] == 3
    finally:
        path.unlink()


def test_pdf_info_invalid():
    """PdfInfoSkill should flag non-PDF data as invalid."""
    from skills.multimodal.pdf_skills import PdfInfoSkill

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(b"NOT A PDF")
    tmp.close()
    try:
        skill = PdfInfoSkill()
        skill.activate()
        result = skill.execute({"path": tmp.name})
        assert result.success
        assert result.data["valid"] is False
    finally:
        Path(tmp.name).unlink()


def test_pdf_info_missing_file():
    """PdfInfoSkill should report an error if the file is missing."""
    from skills.multimodal.pdf_skills import PdfInfoSkill

    skill = PdfInfoSkill()
    skill.activate()
    result = skill.execute({"path": "/no/such/file.pdf"})
    assert result.success
    assert "error" in result.data


# ---------------------------------------------------------------------------
# Audio skills
# ---------------------------------------------------------------------------


def test_audio_info_wav():
    """AudioInfoSkill should report channels, sample rate, duration."""
    from skills.multimodal.audio_skills import AudioInfoSkill

    path = _make_minimal_wav(duration_s=1.0, sample_rate=16000)
    try:
        skill = AudioInfoSkill()
        skill.activate()
        result = skill.execute({"path": str(path)})
        assert result.success
        assert result.data["channels"] == 1
        assert result.data["sample_width_bytes"] == 2
        assert result.data["frame_rate_hz"] == 16000
        assert abs(result.data["duration_seconds"] - 1.0) < 0.01
    finally:
        path.unlink()


def test_audio_info_invalid_wav():
    """AudioInfoSkill should report an error on bad WAV data."""
    from skills.multimodal.audio_skills import AudioInfoSkill

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(b"not a wav file")
    tmp.close()
    try:
        skill = AudioInfoSkill()
        skill.activate()
        result = skill.execute({"path": tmp.name})
        assert result.success
        assert "error" in result.data
    finally:
        Path(tmp.name).unlink()


def test_audio_transcribe_stub():
    """AudioTranscribeStubSkill now uses a real ASR backend (Whisper/OpenAI).

    With no backend installed and a non-existent file, it should degrade
    gracefully: empty transcript plus an explanatory ``error`` (never a fake
    transcript and never a silent STUB warning).
    """
    from skills.multimodal.audio_skills import AudioTranscribeStubSkill

    skill = AudioTranscribeStubSkill()
    skill.activate()
    result = skill.execute({"path": "/tmp/somefile.wav"})
    assert result.success
    assert result.data["transcript"] == ""
    assert "error" in result.data
    assert result.data["error"]


# ---------------------------------------------------------------------------
# Registry / auto-discovery
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    """A single registry instance for the whole multimodal test module."""
    reg = SkillRegistry()
    reg.auto_discover()
    return reg


@pytest.mark.parametrize(
    "skill_name",
    [
        "image_info",
        "image_resize",
        "image_base64",
        "pdf_info",
        "pdf_extract_text",
        "audio_info",
        "audio_transcribe",
    ],
)
def test_multimodal_skill_is_registered(registry, skill_name):
    """All multimodal skills should be discoverable via the registry."""
    skill = registry.get_skill(skill_name)
    assert skill is not None, f"Skill '{skill_name}' not found in registry"
    assert isinstance(skill, BaseSkill)


def test_multimodal_skill_input_inventory_complete(registry):
    """Mirror the global SAMPLE_INPUTS contract: every multimodal skill must be testable.

    These skills need a real file on disk, so we only check that they accept
    the documented 'path' input via the BaseSkill validation layer.
    """
    for name in (
        "image_info",
        "image_resize",
        "image_base64",
        "pdf_info",
        "pdf_extract_text",
        "audio_info",
        "audio_transcribe",
    ):
        skill = registry.get_skill(name)
        assert skill is not None, f"{name} not registered"
        # Calling execute() with an empty context should fail validation
        # (path is required) and return a SkillResult with success=False.
        result = skill.execute({})
        assert isinstance(result, SkillResult)
        assert result.success is False, (
            f"Skill {name!r} should fail validation on empty context"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
