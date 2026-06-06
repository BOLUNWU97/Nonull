"""
PDF skills / PDF 处理技能
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from skills.base import BaseSkill, SkillMetadata, SkillCategory


class PdfInfoSkill(BaseSkill):
    """Extract basic info from a PDF file (header only, no library needed)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="pdf_info",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Extract basic info from a PDF file header (version, page count estimate).",
            tags=["pdf", "metadata", "document"],
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
        info: Dict[str, Any] = {"path": str(path), "size_bytes": len(data)}
        if data[:4] != b"%PDF":
            return {**info, "valid": False, "error": "Not a valid PDF header"}
        info["valid"] = True
        # Find version: prefer the standard "%%PDF-1.x" comment in the
        # first ~1KB; fall back to the bare "%PDF" header on the first line.
        pdf_version = "unknown"
        try:
            head = data[:1024].decode("latin-1", errors="ignore")
            for line in head.splitlines():
                line = line.strip()
                if line.startswith("%PDF-"):
                    pdf_version = line[len("%PDF-"):].strip()
                    break
                if line.startswith("%PDF") and not line.startswith("%%"):
                    pdf_version = line[len("%PDF"):].strip() or "unknown"
                    break
        except (IndexError, UnicodeDecodeError):
            pass
        info["pdf_version"] = pdf_version
        # Estimate page count by counting /Type /Page (rough)
        info["page_count_estimate"] = data.count(b"/Type /Page") + data.count(b"/Type/Page")
        return info


class PdfExtractTextSkill(BaseSkill):
    """Extract text from a PDF (requires pypdf)."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="pdf_extract_text",
            version="0.1.0",
            category=SkillCategory.GENERAL,
            description="Extract text from each page of a PDF. Requires pypdf (install separately).",
            tags=["pdf", "text", "extract", "ocr"],
            author="Nonull Team",
            safety_level=1,
        )

    def _validate_input(self, context):
        if not context.get("path"):
            raise ValueError("'path' required")

    def _execute_impl(self, context):
        try:
            import pypdf
        except ImportError:
            return {
                "warning": "pypdf not installed. Install with: pip install pypdf",
                "stub": True,
            }
        path = Path(context["path"])
        reader = pypdf.PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                pages.append({"page": i + 1, "text": text, "char_count": len(text)})
            except Exception as e:
                pages.append({"page": i + 1, "error": str(e)})
        return {
            "page_count": len(pages),
            "pages": pages,
            "total_chars": sum(p.get("char_count", 0) for p in pages),
        }
