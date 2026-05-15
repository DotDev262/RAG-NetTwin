"""
High-Accuracy PDF Text Extractor for RAG-NetTwin.

This module uses OpenDataLoader (Hybrid Mode) to convert network
documentation PDFs into structured Markdown. It preserves tables,
reading order, and document hierarchy.

Requirements:
- Java 11+ installed and on PATH
- opendataloader-pdf[hybrid] python package
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from opendataloader_pdf import convert  # type: ignore

from src.utils import setup_logger

logger = setup_logger("PDFExtractor")


def extract_text_from_pdf(
    pdf_path: str, use_hybrid: bool = False
) -> List[Dict[str, Any]]:
    """
    Extracts text from a PDF file using OpenDataLoader.

    Args:
        pdf_path: Path to the PDF file.
        use_hybrid: If True, uses docling-fast hybrid backend for layout-aware extraction.

    Returns:
        List of dictionaries with page content split by '---'.
    """
    logger.info(f"Extracting text from {pdf_path} (hybrid={use_hybrid})...")

    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(pdf_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            # Configure hybrid parameters
            # Note: hybrid mode requires a backend, 'docling-fast' is the standard
            hybrid_param = "docling-fast" if use_hybrid else "off"

            convert(
                input_path=[pdf_path],
                output_dir=tmp_dir,
                format=["markdown"],
                hybrid=hybrid_param,
                markdown_page_separator="---",  # Force explicit page markers
                quiet=True,
            )

            pdf_stem = Path(pdf_path).stem
            md_file = Path(tmp_dir) / f"{pdf_stem}.md"

            if not md_file.exists():
                md_files = list(Path(tmp_dir).glob("*.md"))
                if md_files:
                    md_file = md_files[0]
                else:
                    raise FileNotFoundError(
                        f"Markdown output not generated in {tmp_dir}"
                    )

            with open(md_file, "r", encoding="utf-8") as f:
                full_text = f.read()

            pages = []
            sections = full_text.split("---")

            for i, section in enumerate(sections):
                if section.strip():
                    pages.append(
                        {
                            "page": i + 1,
                            "text": section.strip(),
                        }
                    )

            if not pages:
                pages.append({"page": 1, "text": full_text})

            logger.info(
                f"Successfully extracted {len(pages)} sections from {Path(pdf_path).name}"
            )
            return pages

        except Exception as e:
            logger.error(f"Extraction failed for {pdf_path}: {e}")
            raise RuntimeError(f"OpenDataLoader error: {e}")


if __name__ == "__main__":
    # Test extraction
    test_pdf = "data/raw_docs/catalyst_9300_cmdref_17_6.pdf"
    if os.path.exists(test_pdf):
        try:
            # Use use_hybrid=False for quick verification without server overhead
            pages = extract_text_from_pdf(test_pdf, use_hybrid=False)
            print(f"Extracted {len(pages)} sections.")
            if pages:
                print("\n--- Snippet ---")
                print(pages[0]["text"][:500])
        except Exception as e:
            print(f"Error during test: {e}")
