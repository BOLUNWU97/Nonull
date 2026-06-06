"""
Audio skills / 音频处理技能
"""
from __future__ import annotations
import wave
import struct
from pathlib import Path
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class AudioInfoSkill(BaseSkill):
    """Read WAV file metadata."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="audio_info",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Read metadata from a WAV file (channels, sample rate, duration).",
            tags=["audio", "wav", "metadata"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("path"):
            raise ValueError("'path' required")

    def _execute_impl(self, context):
        path = Path(context["path"])
        if not path.exists():
            return {"error": f"File not found: {path}"}
        try:
            with wave.open(str(path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / rate if rate else 0
                return {
                    "path": str(path),
                    "channels": wf.getnchannels(),
                    "sample_width_bytes": wf.getsampwidth(),
                    "frame_rate_hz": rate,
                    "frames": frames,
                    "duration_seconds": round(duration, 3),
                }
        except wave.Error as e:
            return {"error": f"Not a valid WAV file: {e}"}


class AudioTranscribeStubSkill(BaseSkill):
    """Audio transcription (STUB — requires Whisper or other ASR)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="audio_transcribe",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Transcribe audio to text. DEMO STUB — wire to Whisper, Google STT, or Azure Speech.",
            tags=["audio", "transcribe", "asr", "speech-to-text"],
            author="Nonull Team",
            safety_level=2,
        )

    def _validate_input(self, context):
        if not context.get("path"):
            raise ValueError("'path' required")

    def _execute_impl(self, context):
        return {
            "path": context["path"],
            "transcript": "",
            "warning": (
                "Audio transcription is a STUB. To enable, install and integrate "
                "an ASR engine: openai-whisper, faster-whisper, Google STT, etc."
            ),
        }
