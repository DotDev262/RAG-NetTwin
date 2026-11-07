"""
Developer CLI Utility for LLM-Assisted Rule Encoder (rule_encoder/cli.py).

Provides a command-line interface:
python -m src.rule_encoder.cli --source rfc2328.txt --vendor-pair cisco,juniper --output config/alignment_rules_registry.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.rule_encoder.ingest import DocumentIngestionEngine
from src.rule_encoder.extractor import RuleExtractionEngine
from src.rule_encoder.validator import RuleRegistryValidator
from src.utils import setup_logger

logger = setup_logger("RuleEncoderCLI")


def main():
    parser = argparse.ArgumentParser(
        description="Compile-time LLM-Assisted Rule Encoder for RAG-NetTwin v2."
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        required=True,
        help="Path to technical specification file (PDF, TXT, RFC, HTML) or directory.",
    )
    parser.add_argument(
        "--vendor-pair",
        "-v",
        type=str,
        default="cisco,juniper",
        help="Comma-separated vendor pair to align syntax for (default: 'cisco,juniper').",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="config/alignment_rules_registry.json",
        help="Target output path for compiled static alignment registry.",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model identifier to use for extraction (defaults to configured system LLM).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run ingestion and extraction without writing registry to disk.",
    )

    args = parser.parse_args()
    source_path = Path(args.source)
    if not source_path.exists():
        logger.error(f"Error: Source '{source_path}' does not exist.")
        sys.exit(1)

    vendors = [v.strip().lower() for v in args.vendor_pair.split(",") if v.strip()]
    logger.info(f"Target vendors: {vendors}")

    # Step 1: Ingestion & Chunking
    ingestor = DocumentIngestionEngine()
    if source_path.is_file():
        files_to_process = [source_path]
    else:
        files_to_process = [
            p for p in source_path.glob("**/*")
            if p.suffix.lower() in [".txt", ".pdf", ".html", ".md", ".rfc"]
        ]

    logger.info(f"Found {len(files_to_process)} file(s) to process.")
    all_chunks = []
    for fp in files_to_process:
        try:
            chunks = ingestor.ingest_document(fp)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Skipping {fp.name}: {e}")

    logger.info(f"Total parameter-relevant chunks: {len(all_chunks)}")
    if not all_chunks:
        logger.error("No parameter-relevant chunks found in source documents.")
        sys.exit(1)

    # Step 2: Structured LLM Extraction
    extractor = RuleExtractionEngine(model_name=args.model)
    logger.info("Extracting alignment schema rules from chunks...")
    extracted_rules = extractor.extract_from_corpus(all_chunks, target_vendors=vendors)
    logger.info(f"Extracted {len(extracted_rules)} candidate rules.")

    # Step 3: Validation & Compilation
    validator = RuleRegistryValidator(registry_output_path=args.output)
    verified_rules, report = validator.validate_corpus(extracted_rules)

    print("\n" + "=" * 60)
    print("RULE ENCODER COMPILATION REPORT")
    print("=" * 60)
    print(f"Total Candidate Rules Extracted: {report.total_rules_evaluated}")
    print(f"Verified & Mathematically Consistent Rules: {report.verified_rules_count}")
    print(f"Validation Status: {'PASS' if report.is_valid else 'WARNINGS/ERRORS DETECTED'}")

    if report.issues:
        print("\nIntegrity Issues / Warnings:")
        for iss in report.issues:
            print(f"  [{iss.severity}] [{iss.rule_id}] {iss.message}")

    if not args.dry_run:
        out_file = validator.compile_and_save_registry(verified_rules)
        print(f"\n[+] Compiled Registry written to: {out_file.resolve()}")
    else:
        print("\n[*] Dry-run specified. Skipping writing to disk.")


if __name__ == "__main__":
    main()
