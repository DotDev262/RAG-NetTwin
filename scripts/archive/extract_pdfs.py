#!/usr/bin/env python3
"""
Extract text from all PDF documentation
Processes Cisco and Juniper PDFs into clean text files
"""

import pypdf
from pathlib import Path
from typing import List, Dict, Tuple, Any
import re
from tqdm import tqdm  # type: ignore


class PDFExtractor:
    """Extract and clean text from PDF files"""

    def __init__(
        self, input_dir: str = "data/raw_docs", output_dir: str = "data/processed"
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.extraction_stats: List[Dict[str, Any]] = []

    def extract_pdf(self, pdf_path: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from a single PDF

        Returns:
            (cleaned_text, stats_dict)
        """
        print(f"\nProcessing: {pdf_path.name}")

        text_content: List[str] = []
        stats: Dict[str, Any] = {
            "file": pdf_path.name,
            "total_pages": 0,
            "extracted_pages": 0,
            "total_chars": 0,
            "commands_found": 0,
        }

        try:
            with open(pdf_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)
                stats["total_pages"] = len(pdf_reader.pages)

                print(f"  Total pages: {stats['total_pages']}")

                # Extract text from each page
                for page_num, page in enumerate(
                    tqdm(pdf_reader.pages, desc="  Extracting", leave=False)
                ):
                    try:
                        page_text = page.extract_text()

                        if (
                            page_text and len(page_text.strip()) > 50
                        ):  # Skip near-empty pages
                            # Add page separator
                            text_content.append(f"\n{'=' * 80}\n")
                            text_content.append(f"PAGE {page_num + 1}\n")
                            text_content.append(f"{'=' * 80}\n\n")
                            text_content.append(page_text)
                            stats["extracted_pages"] += 1

                    except Exception as e:
                        print(f"    Warning: Error on page {page_num + 1}: {e}")
                        continue

            # Combine all text
            full_text = "\n".join(text_content)

            # Clean the text
            cleaned_text = self.clean_text(full_text)
            stats["total_chars"] = len(cleaned_text)
            stats["commands_found"] = len(self.extract_commands(cleaned_text))

            print(
                f"  [OK] Extracted {stats['extracted_pages']}/{stats['total_pages']} pages"
            )
            print(f"  [OK] Total characters: {stats['total_chars']:,}")
            print(f"  [OK] Commands found: {stats['commands_found']}")

            return cleaned_text, stats

        except Exception as e:
            print(f"  [ERROR] Error processing PDF: {e}")
            return "", {**stats, "error": str(e)}

    def clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove page headers/footers (common patterns)
        text = re.sub(r"\n\s*\d+\s+of\s+\d+\s*\n", "\n", text)
        text = re.sub(r"\n\s*Cisco Systems.*\n", "\n", text)
        text = re.sub(r"\n\s*Chapter \d+.*\n", "\n", text, flags=re.IGNORECASE)

        # Fix spacing around commands
        text = re.sub(
            r"(\n\s*)(ip|interface|router|vlan|access-list)(\s+)",
            r"\n\2\3",
            text,
            flags=re.IGNORECASE,
        )

        # Remove isolated numbers (likely page numbers)
        text = re.sub(r"\n\s*\d+\s*\n", "\n", text)

        return text.strip()

    def extract_commands(self, text: str) -> List[str]:
        """Extract potential CLI commands from text"""
        commands = []

        # Common Cisco IOS command patterns
        patterns = [
            r"\b(ip\s+\w+(?:\s+\w+){0,3})\b",
            r"\b(interface\s+\w+)\b",
            r"\b(router\s+\w+)\b",
            r"\b(vlan\s+\d+)\b",
            r"\b(access-list\s+\w+)\b",
            r"\b(route-map\s+\w+)\b",
            r"\b(hostname\s+\w+)\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            commands.extend(matches)

        return list(set(commands))  # Remove duplicates

    def process_all_pdfs(self) -> Dict:
        """Process all PDFs in the input directory"""

        print("=" * 80)
        print("PDF TEXT EXTRACTION")
        print("=" * 80)
        print(f"\nInput directory: {self.input_dir.absolute()}")
        print(f"Output directory: {self.output_dir.absolute()}\n")

        # Find all PDFs
        pdf_files = list(self.input_dir.glob("*.pdf"))

        if not pdf_files:
            print("[ERROR] No PDF files found!")
            return {"success": False, "error": "No PDFs found"}

        print(f"Found {len(pdf_files)} PDF files:\n")
        for pdf in sorted(pdf_files):
            size_mb = pdf.stat().st_size / (1024 * 1024)
            print(f"  - {pdf.name} ({size_mb:.1f} MB)")

        print("\n" + "=" * 80)
        print("STARTING EXTRACTION")
        print("=" * 80)

        # Process each PDF
        total_chars = 0
        total_pages = 0

        for pdf_path in sorted(pdf_files):
            print(f"\n{'=' * 80}")

            # Extract text
            text, stats = self.extract_pdf(pdf_path)

            if text:
                # Save extracted text
                output_file = self.output_dir / f"{pdf_path.stem}.txt"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(text)

                print(f"  [OK] Saved to: {output_file}")
                total_chars += int(stats.get("total_chars", 0))
                total_pages += int(stats.get("extracted_pages", 0))

            self.extraction_stats.append(stats)

            # Small delay between files
            import time

            time.sleep(0.5)

        # Summary
        print("\n" + "=" * 80)
        print("EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"\nTotal PDFs processed: {len(pdf_files)}")
        print(f"Total pages extracted: {total_pages}")
        print(f"Total characters: {total_chars:,}")
        print(f"Average per PDF: {total_chars // len(pdf_files):,} chars")

        # Save summary
        summary_file = self.output_dir / "extraction_summary.txt"
        with open(summary_file, "w") as f:
            f.write("PDF EXTRACTION SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            for stat in self.extraction_stats:
                f.write(f"File: {stat['file']}\n")
                f.write(
                    f"  Pages: {stat.get('extracted_pages', 0)}/{stat.get('total_pages', 0)}\n"
                )
                f.write(f"  Characters: {stat.get('total_chars', 0):,}\n")
                f.write(f"  Commands: {stat.get('commands_found', 0)}\n")
                if "error" in stat:
                    f.write(f"  Error: {stat['error']}\n")
                f.write("\n")

        print(f"\n[OK] Summary saved to: {summary_file}")

        return {
            "success": True,
            "total_pdfs": len(pdf_files),
            "total_pages": total_pages,
            "total_chars": total_chars,
            "output_dir": str(self.output_dir),
        }


def main():
    """Main entry point"""
    extractor = PDFExtractor()
    result = extractor.process_all_pdfs()

    if result["success"]:
        print("\n[SUCCESS] Text extraction complete!")
        print("\nNext: Run chunking pipeline to create 500+ chunks")
    else:
        print("\n[FAILED] Extraction failed!")


if __name__ == "__main__":
    main()
