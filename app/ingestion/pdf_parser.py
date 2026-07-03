"""
Phase 3 — Document Ingestion & Advanced Text Parsing

Multi-format extraction engine with layout-aware cleansing.
Handles: PDF (pypdf / pdfplumber / PyMuPDF), plain text, maintenance logs.
"""

from __future__ import annotations

import re
import hashlib
import logging
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass

from .schemas import ParsedDocument

logger = logging.getLogger(__name__)

DocumentCategory = Literal["MANUAL", "SOP", "SPEC_SHEET", "MAINTENANCE_LOG", "INCIDENT_REPORT"]


HEADER_FOOTER_PATTERNS = [
    re.compile(r"^\s*Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*\d+\s*$", re.MULTILINE),  # isolated page numbers
    re.compile(r"^\s*Confidential\s*[-–]\s*.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Industrial Operating Brain.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*SOP[-\s]\d+.*Rev.*$", re.IGNORECASE | re.MULTILINE),
    # running headers commonly ALL CAPS short line repeated
    re.compile(r"^\s*[A-Z0-9 _\-/]{8,60}\s*$", re.MULTILINE),
]

INDEX_LISTING_PATTERN = re.compile(
    r"(?m)^(?:\s*(?:\d+\.)+\s+[A-Z].{5,80}?\.+\s*\d+\s*$|^\s*Table of Contents.*$)",
    re.IGNORECASE
)

MULTI_SPACE = re.compile(r"[ \t]{2,}")
MULTI_NEWLINE = re.compile(r"\n{3,}")


def _strip_headers_footers(text: str) -> str:
    cleaned = text
    for pat in HEADER_FOOTER_PATTERNS:
        cleaned = pat.sub("", cleaned)
    # remove index / TOC lines
    cleaned = INDEX_LISTING_PATTERN.sub("", cleaned)
    # normalize whitespace
    cleaned = MULTI_SPACE.sub(" ", cleaned)
    cleaned = MULTI_NEWLINE.sub("\n\n", cleaned)
    return cleaned.strip()


def _detect_sections(text: str) -> list[dict]:
    """Very light structural section detection for technical manuals."""
    sections: list[dict] = []
    # Match headings like "1. Introduction", "2.3 Bearing Lubrication", "SOP-114", etc.
    heading_re = re.compile(r"(?m)^(\d+(?:\.\d+){0,3}\s+[A-Z][^\n]{3,120}|[A-Z][A-Z\s\-]{5,60}|SOP[-\s]?\d+.*)$")
    matches = list(heading_re.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        title = m.group(1).strip()
        if len(title) > 120:
            continue
        sections.append({
            "section_identifier": title.split()[0] if title and title[0].isdigit() else None,
            "section_title": title,
            "char_start": start,
            "char_end": end,
        })
    return sections


def _extract_with_pypdf(pdf_path: Path) -> tuple[str, list[dict], int]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:
        raise RuntimeError("pypdf not installed") from e

    reader = PdfReader(str(pdf_path))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    full_text = "\n\n".join(pages_text)
    return full_text, [], len(pages_text)


def _extract_with_pdfplumber(pdf_path: Path) -> tuple[str, list[dict], int]:
    try:
        import pdfplumber  # type: ignore
    except Exception as e:
        raise RuntimeError("pdfplumber not installed") from e

    text_parts: list[str] = []
    tables: list[dict] = []
    page_count = 0
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)
        for idx, page in enumerate(pdf.pages, start=1):
            t = page.extract_text() or ""
            text_parts.append(t)
            # structural table handling
            try:
                page_tables = page.extract_tables()
                for ti, tbl in enumerate(page_tables or []):
                    if not tbl:
                        continue
                    # clean table to JSON-serializable
                    clean_rows = [[str(cell or "").strip() for cell in row] for row in tbl if any(cell for cell in row)]
                    if clean_rows:
                        tables.append({
                            "page": idx,
                            "table_index": ti,
                            "rows": clean_rows,
                            "json": clean_rows,  # for downstream JSON string conversion
                        })
                        # append structural text representation
                        text_parts.append("\n[TABLE_START]\n" + "\n".join([" | ".join(r) for r in clean_rows]) + "\n[TABLE_END]\n")
            except Exception:
                continue
    return "\n\n".join(text_parts), tables, page_count


def _extract_with_pymupdf(pdf_path: Path) -> tuple[str, list[dict], int]:
    try:
        import fitz  # PyMuPDF # type: ignore
    except Exception as e:
        raise RuntimeError("pymupdf not installed") from e

    doc = fitz.open(str(pdf_path))
    texts: list[str] = []
    tables: list[dict] = []
    for i in range(len(doc)):
        page = doc[i]
        texts.append(page.get_text("text"))
    return "\n\n".join(texts), tables, len(doc)


def extract_text_from_pdf(pdf_path: str | Path) -> tuple[str, list[dict], int]:
    """
    Multi-engine fallback: pdfplumber (best for tables) -> pymupdf -> pypdf
    Returns: (raw_text, tables, page_count)
    """
    path = Path(pdf_path)
    errors = []
    for extractor, name in [
        (_extract_with_pdfplumber, "pdfplumber"),
        (_extract_with_pymupdf, "pymupdf"),
        (_extract_with_pypdf, "pypdf"),
    ]:
        try:
            text, tables, pages = extractor(path)
            if text and text.strip():
                logger.info("pdf extraction succeeded via %s (%d pages)", name, pages)
                return text, tables, pages
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
    raise RuntimeError(f"All PDF extractors failed: {'; '.join(errors)}")


def clean_technical_text(raw_text: str) -> str:
    """Layout-aware cleansing: strip headers/footers/page numbers/index listings."""
    return _strip_headers_footers(raw_text)


def parse_document(
    file_path: str | Path,
    *,
    document_category: DocumentCategory = "MANUAL",
    document_id: Optional[str] = None,
    site_code: str = "SRP",
) -> ParsedDocument:
    """
    Parse a technical manual / SOP / spec sheet into clean text + metadata.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    tables: list[dict] = []
    total_pages = 1

    if suffix == ".pdf":
        raw_text, tables, total_pages = extract_text_from_pdf(path)
    elif suffix in {".txt", ".md", ".log"}:
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
        total_pages = raw_text.count("\f") + 1
    else:
        # attempt plain text fallback
        try:
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            raise ValueError(f"Unsupported file type: {suffix}")

    cleaned = clean_technical_text(raw_text)
    sections = _detect_sections(cleaned)

    # document_id deterministic: document:<source_type>:<checksum_or_filename>
    if document_id is None:
        checksum = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]
        source_type = document_category
        doc_slug = path.stem.replace(" ", "_").upper()
        document_id = f"document:{source_type}:{doc_slug}:{checksum}"

    # normalize tables to JSON strings for downstream
    import json
    for t in tables:
        t["json_string"] = json.dumps(t.get("rows", []), separators=(",", ":"))

    return ParsedDocument(
        document_id=document_id,
        source_filename=path.name,
        document_category=document_category,
        total_pages=total_pages,
        text=cleaned,
        sections=sections,
        tables=tables,
        metadata={
            "site_code": site_code,
            "char_count": len(cleaned),
            "section_count": len(sections),
            "table_count": len(tables),
            "source_path": str(path),
        },
    )


# Convenience CLI
if __name__ == "__main__":
    import sys, json
    fp = sys.argv[1] if len(sys.argv) > 1 else "sample_manual.pdf"
    try:
        doc = parse_document(fp, document_category="SOP")
        print(json.dumps(doc.model_dump(), indent=2, default=str)[:4000])
    except Exception as e:
        print(f"Parse failed: {e}", file=sys.stderr)
        sys.exit(1)
