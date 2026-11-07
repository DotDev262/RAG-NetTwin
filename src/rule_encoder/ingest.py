"""
Document Ingestion & Chunking Module for Rule Encoder (rule_encoder/ingest.py).

Accepts raw text or PDF documents (RFCs, vendor CLI Command References, Feature Guides)
and chunks the technical specifications into semantically meaningful blocks focusing on
protocol parameters, syntax constraints, and inter-vendor behavior.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.utils import setup_logger

logger = setup_logger("RuleEncoderIngest")


class DocumentChunk(BaseModel):
    """Semantically meaningful chunk extracted from technical specification."""
    chunk_id: str
    source_name: str
    section_title: str = "General"
    content: str
    protocol_hint: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentIngestionEngine:
    """
    Ingests RFC specifications, vendor command references, and feature guides
    and chunks them into protocol parameter and alignment-focused segments.
    """

    def __init__(self, max_chunk_tokens: int = 1500):
        self.max_chunk_tokens = max_chunk_tokens

    def ingest_document(self, file_path: str | Path) -> List[DocumentChunk]:
        """
        Ingests a document (text, markdown, html, or PDF) and returns semantically chunked blocks.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Source document not found: {path}")

        logger.info(f"Ingesting technical specification: {path.name}")
        ext = path.suffix.lower()

        if ext in [".txt", ".md", ".json", ".rfc"]:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
        elif ext == ".pdf":
            raw_text = self._extract_pdf_text(path)
        elif ext in [".html", ".htm"]:
            raw_text = self._extract_html_text(path)
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

        return self.chunk_technical_spec(raw_text, source_name=path.name)

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extracts text from PDF using available tools with graceful fallback."""
        try:
            from src.data_processing.pdf_extractor import extract_text_from_pdf
            pages = extract_text_from_pdf(str(pdf_path), use_hybrid=False)
            full_text = "\n\n".join(p.get("text", "") for p in pages)
            if full_text.strip():
                return full_text
        except Exception as e:
            logger.warning(f"Standard PDF extraction failed ({e}), attempting fallback...")

        # Fallback raw extraction if needed
        try:
            with open(pdf_path, "rb") as f:
                raw_bytes = f.read()
                # Clean extract ASCII text streams if tools fail
                text_chunks = re.findall(rb"\(([^\(\)]+)\)\s*Tj", raw_bytes)
                if text_chunks:
                    return b"\n".join(text_chunks).decode("latin-1", errors="ignore")
        except Exception as e2:
            logger.error(f"Failed fallback PDF extraction: {e2}")

        return ""

    def _extract_html_text(self, html_path: Path) -> str:
        """Cleans and extracts text from HTML command reference files."""
        with open(html_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        clean = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def chunk_technical_spec(self, text: str, source_name: str) -> List[DocumentChunk]:
        """
        Chunks technical text along RFC/Command reference section boundaries
        (e.g., Section headers, command syntax blocks, timer specifications).
        """
        chunks: List[DocumentChunk] = []

        # Split along RFC / Command Reference structural markers:
        # 1. RFC section numbers (e.g., "9.5. Sending Hello Packets", "4.1. Global Parameters")
        # 2. Markdown headers (##, ###)
        # 3. CLI Command titles (e.g. "Command Default", "Syntax Description", "ip ospf hello-interval")
        header_pattern = re.compile(
            r"(?m)^(?:(?:\d+\.(?:\d+\.)*\s+[A-Z][^\n]+)|(?:#{1,4}\s+[^\n]+)|(?:(?:Command Default|Syntax Description|Usage Guidelines|Syntax|Command Syntax)\b[^\n]*))"
        )

        matches = list(header_pattern.finditer(text))
        if not matches:
            # Fallback: chunk by paragraph blocks
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            cur_block: List[str] = []
            cur_len = 0
            chunk_idx = 1
            for p in paragraphs:
                cur_block.append(p)
                cur_len += len(p)
                if cur_len > 2500:
                    content_str = "\n\n".join(cur_block)
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{source_name}_chunk_{chunk_idx:03d}",
                            source_name=source_name,
                            section_title=f"Section {chunk_idx}",
                            content=content_str,
                            protocol_hint=self._detect_protocol(content_str),
                        )
                    )
                    chunk_idx += 1
                    cur_block = []
                    cur_len = 0
            if cur_block:
                content_str = "\n\n".join(cur_block)
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{source_name}_chunk_{chunk_idx:03d}",
                        source_name=source_name,
                        section_title=f"Section {chunk_idx}",
                        content=content_str,
                        protocol_hint=self._detect_protocol(content_str),
                    )
                )
            return chunks

        # Section-bounded chunking
        for i in range(len(matches)):
            start_pos = matches[i].start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            title = matches[i].group(0).strip("# ").strip()
            section_content = text[start_pos:end_pos].strip()

            if len(section_content) < 50:
                continue

            # Check if section discusses protocol parameters, syntax, timers, or constraints
            protocol = self._detect_protocol(section_content)
            is_relevant = self._is_parameter_relevant(section_content)

            if is_relevant:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{source_name}_sec_{i+1:03d}",
                        source_name=source_name,
                        section_title=title,
                        content=section_content[:6000],  # Bound context window safely
                        protocol_hint=protocol,
                        metadata={"header": title, "length": len(section_content)},
                    )
                )

        return chunks

    def _detect_protocol(self, text: str) -> Optional[str]:
        """Detects primary protocol discussed in chunk."""
        t_lower = text.lower()
        if "ospf" in t_lower:
            return "OSPF"
        if "bgp" in t_lower:
            return "BGP"
        if "rip" in t_lower:
            return "RIP"
        if "isis" in t_lower or "is-is" in t_lower:
            return "IS-IS"
        if "vlan" in t_lower or "ethernet" in t_lower:
            return "INTERFACE"
        return "GENERAL"

    def _is_parameter_relevant(self, text: str) -> bool:
        """Determines if chunk contains parameter constraints or syntax information."""
        keywords = [
            "interval", "timer", "hello", "dead", "area", "as-number", "remote-as",
            "autonomous-system", "md5", "authentication", "metric", "cost", "mtu",
            "subnet", "mask", "mismatch", "adjacency", "neighbor", "peer", "syntax",
            "command", "must match", "same value", "identical"
        ]
        t_lower = text.lower()
        return any(k in t_lower for k in keywords)
