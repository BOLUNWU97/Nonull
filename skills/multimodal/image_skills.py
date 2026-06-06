"""
Image processing skills / 图像处理技能

These are general-purpose: they don't do OCR or face detection specifically.
They produce METADATA about images that an LLM can use.
"""
from __future__ import annotations
import base64
import io
import struct
from pathlib import Path
from typing import Any, Dict, List
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class ImageInfoSkill(BaseSkill):
    """Extract basic metadata from an image file (no LLM/OCR required)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="image_info",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Read basic metadata (format, size, mode) from a PNG/JPEG/GIF file. No OCR.",
            tags=["image", "metadata", "png", "jpeg", "gif"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("path"):
            raise ValueError("'path' is required")

    def _execute_impl(self, context):
        path = Path(context["path"])
        if not path.exists():
            return {"error": f"File not found: {path}"}

        data = path.read_bytes()
        info = {"path": str(path), "size_bytes": len(data), "format": "unknown"}

        # PNG
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            info["format"] = "png"
            # IHDR chunk is at bytes 8-29
            if len(data) >= 24:
                width, height = struct.unpack(">II", data[16:24])
                info["width"] = width
                info["height"] = height
        # JPEG
        elif data[:2] == b"\xff\xd8":
            info["format"] = "jpeg"
            # Scan for SOF marker
            i = 2
            while i < len(data) - 9:
                if data[i] == 0xff and data[i+1] in (0xc0, 0xc1, 0xc2):
                    h, w = struct.unpack(">HH", data[i+5:i+9])
                    info["width"] = w
                    info["height"] = h
                    break
                i += 1
        # GIF
        elif data[:6] in (b"GIF87a", b"GIF89a"):
            info["format"] = "gif"
            w, h = struct.unpack("<HH", data[6:10])
            info["width"] = w
            info["height"] = h
        # BMP
        elif data[:2] == b"BM":
            info["format"] = "bmp"
            w, h = struct.unpack("<ii", data[18:26])
            info["width"] = abs(w)
            info["height"] = abs(h)
        # WebP
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            info["format"] = "webp"

        return info


class ImageResizeSkill(BaseSkill):
    """Resize an image to a target width/height (keeps aspect ratio if only width given)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="image_resize",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Resize a PNG/JPEG image. Requires Pillow if installed; otherwise stub.",
            tags=["image", "resize", "thumbnail"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("path"):
            raise ValueError("'path' required")
        if not (context.get("width") or context.get("height")):
            raise ValueError("'width' or 'height' required")

    def _execute_impl(self, context):
        try:
            from PIL import Image
        except ImportError:
            return {
                "warning": "Pillow not installed. Install with: pip install Pillow",
                "stub": True,
            }
        path = Path(context["path"])
        img = Image.open(path)
        orig_w, orig_h = img.size
        target_w = context.get("width")
        target_h = context.get("height")
        if target_w and not target_h:
            target_h = int(orig_h * target_w / orig_w)
        elif target_h and not target_w:
            target_w = int(orig_w * target_h / orig_h)
        img2 = img.resize((target_w, target_h), Image.LANCZOS)
        out_path = Path(context.get("output", str(path.with_stem(f"{path.stem}_{target_w}x{target_h}"))))
        img2.save(out_path)
        return {
            "input_path": str(path),
            "output_path": str(out_path),
            "original_size": (orig_w, orig_h),
            "new_size": (target_w, target_h),
        }


class ImageBase64Skill(BaseSkill):
    """Encode an image as base64 (for sending to multimodal LLMs)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="image_base64",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Encode an image file as base64 (for multimodal LLM input).",
            tags=["image", "base64", "llm", "multimodal"],
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
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return {
            "path": str(path),
            "mime_type": "image/" + path.suffix.lstrip(".").lower(),
            "size_bytes": len(data),
            "base64": b64,
        }
