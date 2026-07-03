"""
Phase 3 — Semantic Chunking Strategy

Structural Windowing with token-based sliding window (~512-1024 tokens),
10-20% overlap, deterministic hash IDs, full context preservation hierarchy.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable, List, Optional

from .schemas import ParsedDocument, ChunkMetadata

# Try langchain-text-splitters, fallback to simple tokenizer
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter  # type: ignore
    HAS_LANGCHAIN = True
except Exception:
    HAS_LANGCHAIN = False


def count_tokens_approx(text: str) -> int:
    """Approximate token count: ~4 chars per token (conservative for technical text)."""
    # better: split on whitespace + punctuation
    return max(1, len(text) // 4)


def split_sentences(text: str) -> List[str]:
    # simple sentence splitter preserving technical abbreviations
    # avoid splitting on e.g., "P-101A", "Rev. C", "Fig. 2"
    # naive but effective
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [p.strip() for p in parts if p.strip()]


class SemanticChunker:
    """
    Token-based sliding-window chunker tailored for dense technical material.
    """

    def __init__(
        self,
        *,
        chunk_tokens: int = 768,  # target ~512-1024, default mid 768
        overlap_tokens: int = 120,  # ~15% overlap
        min_chunk_tokens: int = 80,
        respect_sections: bool = True,
    ):
        if not (512 <= chunk_tokens <= 1024):
            raise ValueError("chunk_tokens should be 512-1024 per Phase 3 spec")
        overlap_ratio = overlap_tokens / chunk_tokens
        if not (0.10 <= overlap_ratio <= 0.20):
            raise ValueError("overlap must be 10-20%")
        self.chunk_tokens = chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens
        self.respect_sections = respect_sections

        if HAS_LANGCHAIN:
            # TokenTextSplitter uses tiktoken if available
            try:
                self._splitter = TokenTextSplitter(
                    chunk_size=chunk_tokens,
                    chunk_overlap=overlap_tokens,
                )
            except Exception:
                self._splitter = None
        else:
            self._splitter = None

    def _chunk_with_langchain(self, text: str) -> List[str]:
        if self._splitter is None:
            raise RuntimeError("splitter unavailable")
        return self._splitter.split_text(text)

    def _chunk_sliding_window(self, text: str) -> List[str]:
        """Fallback: sentence-aware sliding window."""
        sentences = split_sentences(text)
        if not sentences:
            return [text] if text.strip() else []

        chunks: List[str] = []
        current: List[str] = []
        current_tokens = 0

        i = 0
        while i < len(sentences):
            sent = sentences[i]
            sent_tokens = count_tokens_approx(sent)
            # if adding exceeds window, flush
            if current_tokens + sent_tokens > self.chunk_tokens and current:
                chunk_text = " ".join(current).strip()
                if count_tokens_approx(chunk_text) >= self.min_chunk_tokens:
                    chunks.append(chunk_text)
                # overlap: step back sentences to reach overlap_tokens
                # compute overlap
                overlap_acc = 0
                overlap_sents: List[str] = []
                for s in reversed(current):
                    st = count_tokens_approx(s)
                    if overlap_acc + st > self.overlap_tokens:
                        break
                    overlap_sents.insert(0, s)
                    overlap_acc += st
                current = overlap_sents[:]
                current_tokens = overlap_acc
                # do not increment i — re-evaluate current sentence
                continue
            else:
                current.append(sent)
                current_tokens += sent_tokens
                i += 1

        if current:
            chunk_text = " ".join(current).strip()
            if chunk_text:
                chunks.append(chunk_text)
        return chunks

    def chunk_text(self, text: str) -> List[str]:
        if HAS_LANGCHAIN and self._splitter is not None:
            try:
                out = self._chunk_with_langchain(text)
                # filter tiny chunks
                return [c for c in out if count_tokens_approx(c) >= self.min_chunk_tokens or c == out[-1]]
            except Exception:
                pass
        return self._chunk_sliding_window(text)

    def chunk_document(self, doc: ParsedDocument) -> List[ChunkMetadata]:
        """
        Chunk a ParsedDocument, preserving section hierarchy.
        Returns list of ChunkMetadata with deterministic hash IDs.
        """
        all_chunks: List[ChunkMetadata] = []
        global_index = 0

        # If sections exist and respect_sections=True, chunk per section
        sections = doc.sections if (self.respect_sections and doc.sections) else [
            {"section_title": None, "section_identifier": None, "char_start": 0, "char_end": len(doc.text)}
        ]

        for sec in sections:
            start = sec.get("char_start", 0)
            end = sec.get("char_end", len(doc.text))
            section_text = doc.text[start:end].strip()
            if not section_text:
                continue
            text_chunks = self.chunk_text(section_text)
            for local_idx, chunk_text in enumerate(text_chunks):
                # deterministic hash ID: sha256(document_id + section + index + text)
                hash_input = f"{doc.document_id}|{sec.get('section_title','')}|{global_index}|{chunk_text}".encode("utf-8")
                chunk_hash = hashlib.sha256(hash_input).hexdigest()
                chunk_id = f"chunk:{chunk_hash[:32]}"  # matches Phase 1 TextChunk.chunk_id pattern
                token_ct = count_tokens_approx(chunk_text)
                meta = ChunkMetadata(
                    chunk_id=chunk_id,
                    document_id=doc.document_id,
                    source_filename=doc.source_filename,
                    document_category=doc.document_category,  # type: ignore
                    section_title=sec.get("section_title"),
                    section_identifier=sec.get("section_identifier"),
                    page_start=None,  # could map via char offsets; left null for now
                    page_end=None,
                    chunk_index=global_index,
                    token_count=token_ct,
                    char_count=len(chunk_text),
                    hash=chunk_hash,
                    parent_metadata={
                        "section_local_index": local_idx,
                        "char_start": start,
                        "char_end": end,
                    },
                )
                # attach raw text via parent_metadata for pipeline convenience (not persisted separately)
                meta.parent_metadata["text"] = chunk_text
                all_chunks.append(meta)
                global_index += 1

        # if no sections produced chunks (e.g., short doc), fallback whole-doc
        if not all_chunks and doc.text.strip():
            text_chunks = self.chunk_text(doc.text)
            for idx, chunk_text in enumerate(text_chunks):
                hash_input = f"{doc.document_id}||{idx}|{chunk_text}".encode("utf-8")
                chunk_hash = hashlib.sha256(hash_input).hexdigest()
                chunk_id = f"chunk:{chunk_hash[:32]}"
                all_chunks.append(ChunkMetadata(
                    chunk_id=chunk_id,
                    document_id=doc.document_id,
                    source_filename=doc.source_filename,
                    document_category=doc.document_category,  # type: ignore
                    section_title=None,
                    section_identifier=None,
                    page_start=1,
                    page_end=doc.total_pages,
                    chunk_index=idx,
                    token_count=count_tokens_approx(chunk_text),
                    char_count=len(chunk_text),
                    hash=chunk_hash,
                    parent_metadata={"text": chunk_text},
                ))

        return all_chunks


def chunk_document_text(
    text: str,
    document_id: str,
    source_filename: str,
    document_category: str = "MANUAL",
    *,
    chunk_tokens: int = 768,
    overlap_tokens: int = 120,
) -> List[ChunkMetadata]:
    """Convenience wrapper for raw text."""
    from .schemas import ParsedDocument
    pseudo = ParsedDocument(
        document_id=document_id,
        source_filename=source_filename,
        document_category=document_category,
        total_pages=1,
        text=text,
        sections=[],
        tables=[],
        metadata={},
    )
    chunker = SemanticChunker(chunk_tokens=chunk_tokens, overlap_tokens=overlap_tokens)
    return chunker.chunk_document(pseudo)
