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
    """Audio transcription via Whisper (local) or OpenAI API.

    Backends (auto-selected):
      - openai-whisper (local, no key): if `openai-whisper` is installed, runs a
        local Whisper model (model size via NONULL_WHISPER_MODEL, default "base").
      - OpenAI API (key): if NONULL_LLM_API_KEY/OPENAI_API_KEY set and openai SDK
        present, uses the hosted whisper-1 transcription.
      - graceful fallback: if neither is available, returns a clear actionable
        message (not a silent fake transcript).
    """

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="audio_transcribe",
            version="0.2.0",
            category=SkillCategory.GENERAL,
            description="Transcribe audio to text via local Whisper (no key) or OpenAI API. "
                        "Falls back with a clear message if no ASR backend is installed.",
            tags=["audio", "transcribe", "asr", "speech-to-text"],
            author="Nonull Team",
            safety_level=2,
        )

    def _validate_input(self, context):
        if not context.get("path"):
            raise ValueError("'path' required")

    def _execute_impl(self, context):
        from pathlib import Path as _Path
        path = _Path(context["path"])
        if not path.exists():
            return {"path": str(path), "transcript": "", "error": f"File not found: {path}"}

        language = context.get("language")  # 可选: 指定语言加速/提准
        backend = context.get("backend")    # 可选: "whisper" | "openai"

        # 后端 1: 本地 openai-whisper (无需 key)
        if backend in (None, "whisper"):
            result = self._try_local_whisper(path, language)
            if result is not None:
                return result

        # 后端 2: OpenAI API (需 key)
        if backend in (None, "openai"):
            result = self._try_openai_api(path, language)
            if result is not None:
                return result

        # 优雅降级: 明确告知如何启用 (不返回假转写)
        return {
            "path": str(path),
            "transcript": "",
            "error": "no ASR backend available",
            "hint": ("Install a backend: `pip install openai-whisper` (local, no key) "
                     "or set NONULL_LLM_API_KEY + `pip install openai` for the hosted API."),
        }

    _whisper_model_cache = {}  # model_name -> loaded model (跨调用复用, 类级)

    def _try_local_whisper(self, path, language):
        """本地 Whisper 转写; 库不存在返回 None (让上层降级)。"""
        try:
            import whisper  # openai-whisper
        except ImportError:
            return None
        import os as _os
        model_name = _os.environ.get("NONULL_WHISPER_MODEL", "base")
        try:
            # 模型缓存: load_model 是秒级~分钟级磁盘+计算开销, 每次转写都重载会
            # 病态地慢。按 model_name 缓存复用。
            model = self._whisper_model_cache.get(model_name)
            if model is None:
                model = whisper.load_model(model_name)
                self._whisper_model_cache[model_name] = model
            kwargs = {"language": language} if language else {}
            result = model.transcribe(str(path), **kwargs)
            return {
                "path": str(path),
                "transcript": result.get("text", "").strip(),
                "language": result.get("language", language or ""),
                "backend": f"local-whisper:{model_name}",
                "segments": len(result.get("segments", [])),
            }
        except Exception as e:
            return {"path": str(path), "transcript": "",
                    "error": f"whisper failed: {type(e).__name__}: {e}"}

    _openai_client_cache = {}  # api_key -> OpenAI client (跨调用复用, 类级)

    def _try_openai_api(self, path, language):
        """OpenAI 托管 whisper-1 转写; 无 key/库返回 None。"""
        import os as _os
        api_key = _os.environ.get("NONULL_LLM_API_KEY") or _os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None
        try:
            # client 按 api_key 缓存复用, 避免每次转写都重建
            client = self._openai_client_cache.get(api_key)
            if client is None:
                client = OpenAI(api_key=api_key)
                self._openai_client_cache[api_key] = client
            with open(path, "rb") as f:
                kwargs = {"language": language} if language else {}
                tr = client.audio.transcriptions.create(model="whisper-1", file=f, **kwargs)
            return {
                "path": str(path),
                "transcript": getattr(tr, "text", "").strip(),
                "backend": "openai:whisper-1",
            }
        except Exception as e:
            return {"path": str(path), "transcript": "",
                    "error": f"openai transcription failed: {type(e).__name__}: {e}"}
