#!/usr/bin/env python3
"""
Download Cisco IOS-XE PDF Documentation
Extracts PDF URLs from HTML landing pages and downloads them
"""

import requests
from pathlib import Path
import re
from urllib.parse import urljoin
import time

# PDF URLs discovered from HTML pages
PDF_URLS = {
    "catalyst_9300_cmdref_17_6": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9300/software/release/17-6/command_reference/b_176_9300_cr.pdf",
        "title": "Cisco IOS-XE 17.6 Command Reference - Catalyst 9300",
        "size_mb": 15.35,
    },
    "catalyst_9500_cmdref_17_6": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9500/software/release/17-6/command_reference/b_176_9500_cr.pdf",
        "title": "Cisco IOS-XE 17.6 Command Reference - Catalyst 9500",
        "size_mb": 15.0,  # Estimated
    },
}


def download_pdf(doc_name: str, output_dir: str = "data/raw_docs"):
    """Download a single PDF document"""

    if doc_name not in PDF_URLS:
        print(f"[ERROR] Unknown document: {doc_name}")
        return False

    doc_info = PDF_URLS[doc_name]
    url = doc_info["url"]
    output_path = Path(output_dir) / f"{doc_name}.pdf"

    print(f"\n{'=' * 80}")
    print(f"Downloading: {doc_info['title']}")
    print(f"Expected size: ~{doc_info['size_mb']} MB")
    print(f"URL: {url}")
    print(f"{'=' * 80}\n")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        print("Starting download...")
        response = requests.get(url, headers=headers, stream=True, timeout=120)
        response.raise_for_status()

        # Get total size
        total_size = int(response.headers.get("content-length", 0))
        if total_size > 0:
            print(f"File size: {total_size / (1024 * 1024):.2f} MB")

        # Download with progress
        downloaded = 0
        chunk_size = 8192

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Print progress every 1MB
                    if downloaded % (1024 * 1024) < chunk_size:
                        mb = downloaded / (1024 * 1024)
                        if total_size > 0:
                            pct = (downloaded / total_size) * 100
                            print(f"  Downloaded: {mb:.1f} MB ({pct:.1f}%)")
                        else:
                            print(f"  Downloaded: {mb:.1f} MB")

        actual_size = output_path.stat().st_size
        print(f"\n[SUCCESS] Saved to: {output_path}")
        print(f"  Actual size: {actual_size / (1024 * 1024):.2f} MB")

        return True

    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Failed to download: {e}")
        return False


def main():
    """Main entry point"""
    output_dir = Path("data/raw_docs")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("CISCO IOS-XE PDF DOCUMENTATION DOWNLOADER")
    print("=" * 80)

    success_count = 0

    for doc_name in PDF_URLS:
        if download_pdf(doc_name, output_dir):
            success_count += 1

        # Wait between downloads
        if doc_name != list(PDF_URLS.keys())[-1]:
            print("\nWaiting 5 seconds before next download...")
            time.sleep(5)

    print("\n" + "=" * 80)
    print(f"DOWNLOAD SUMMARY: {success_count}/{len(PDF_URLS)} PDFs downloaded")
    print("=" * 80)

    if success_count > 0:
        print("\nNext steps:")
        print("  1. Verify PDFs in data/raw_docs/ directory")
        print("  2. Extract text from PDFs using pdf_extractor.py")
        print("  3. Process into ChromaDB")


if __name__ == "__main__":
    main()
