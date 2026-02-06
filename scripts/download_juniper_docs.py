#!/usr/bin/env python3
"""
Download Juniper JunOS Documentation
Adds to the RAG corpus with Juniper-specific content
"""

import requests
from pathlib import Path
import time

# Juniper JunOS Documentation URLs
JUNIPER_DOCS = {
    "junos_cli_user_guide": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/cli/cli.pdf",
        "title": "Junos OS CLI User Guide",
        "estimated_size_mb": 8.0,
    },
    "junos_user_access_guide": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/user-access/user-access.pdf",
        "title": "Junos OS User Access and Authentication Administration Guide",
        "estimated_size_mb": 5.0,
    },
    "junos_routing_guide": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/routing/routing.pdf",
        "title": "Junos OS Routing Protocols Guide",
        "estimated_size_mb": 12.0,
    },
    "junos_interfaces_guide": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/interfaces/interfaces.pdf",
        "title": "Junos OS Interfaces Fundamentals",
        "estimated_size_mb": 6.0,
    },
}


def download_juniper_pdf(
    doc_name: str, doc_info: dict, output_dir: str = "data/raw_docs"
):
    """Download a single Juniper PDF"""

    url = doc_info["url"]
    output_path = Path(output_dir) / f"{doc_name}.pdf"

    # Skip if already exists
    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"[SKIP] {doc_name} already exists ({size_mb:.1f} MB)")
        return True

    print(f"\n{'=' * 80}")
    print(f"Downloading: {doc_info['title']}")
    print(f"Expected size: ~{doc_info['estimated_size_mb']} MB")
    print(f"{'=' * 80}\n")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        print("Starting download...")
        response = requests.get(url, headers=headers, stream=True, timeout=180)

        if response.status_code == 404:
            print(f"[ERROR] 404 Not Found - URL may have changed: {url}")
            return False

        response.raise_for_status()

        # Get total size
        total_size = int(response.headers.get("content-length", 0))
        if total_size > 0:
            print(f"File size: {total_size / (1024 * 1024):.2f} MB")
        else:
            print("File size: Unknown")

        # Download with progress
        downloaded = 0
        chunk_size = 8192
        last_mb = 0

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Print progress every 1MB
                    current_mb = downloaded // (1024 * 1024)
                    if current_mb > last_mb:
                        last_mb = current_mb
                        if total_size > 0:
                            pct = (downloaded / total_size) * 100
                            print(f"  Progress: {current_mb} MB ({pct:.1f}%)")
                        else:
                            print(f"  Progress: {current_mb} MB")

        actual_size = output_path.stat().st_size
        print(f"\n[SUCCESS] Saved to: {output_path}")
        print(f"  Actual size: {actual_size / (1024 * 1024):.2f} MB")

        return True

    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Failed to download: {e}")
        # Clean up partial download
        if output_path.exists():
            output_path.unlink()
        return False


def main():
    """Main entry point"""
    output_dir = Path("data/raw_docs")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("JUNIPER JUNOS DOCUMENTATION DOWNLOADER")
    print("=" * 80)
    print(f"Output directory: {output_dir.absolute()}")
    print(f"Documents to download: {len(JUNIPER_DOCS)}\n")

    success_count = 0
    total_size = 0

    for doc_name, doc_info in JUNIPER_DOCS.items():
        if download_juniper_pdf(doc_name, doc_info, output_dir):
            success_count += 1
            total_size += doc_info["estimated_size_mb"]

        # Wait between downloads
        if doc_name != list(JUNIPER_DOCS.keys())[-1]:
            print("\nWaiting 3 seconds before next download...")
            time.sleep(3)

    print("\n" + "=" * 80)
    print(f"DOWNLOAD SUMMARY: {success_count}/{len(JUNIPER_DOCS)} PDFs downloaded")
    print(f"Estimated total size: {total_size:.1f} MB")
    print("=" * 80)

    # List all PDFs in directory
    print("\nAll documentation files:")
    pdf_files = sorted(output_dir.glob("*.pdf"))
    cisco_count = sum(
        1
        for p in pdf_files
        if "catalyst" in p.name.lower() or "cisco" in p.name.lower()
    )
    juniper_count = sum(
        1 for p in pdf_files if "junos" in p.name.lower() or "juniper" in p.name.lower()
    )

    total_actual_size = 0
    for pdf in pdf_files:
        size_mb = pdf.stat().st_size / (1024 * 1024)
        total_actual_size += size_mb
        vendor = (
            "[CISCO]"
            if "catalyst" in pdf.name.lower()
            else "[JUNIPER]"
            if "junos" in pdf.name.lower()
            else "[OTHER]"
        )
        print(f"  {vendor} {pdf.name}: {size_mb:.1f} MB")

    print(
        f"\nTotal library: {len(pdf_files)} PDFs ({cisco_count} Cisco, {juniper_count} Juniper)"
    )
    print(f"Total size: {total_actual_size:.1f} MB")

    if success_count > 0:
        print("\nNext steps:")
        print("  1. Run extract_pdfs.py to extract text")
        print("  2. Run chunking pipeline")
        print("  3. Rebuild ChromaDB with new content")


if __name__ == "__main__":
    main()
