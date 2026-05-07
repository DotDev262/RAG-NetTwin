#!/usr/bin/env python3
"""
Download additional Cisco IOS-XE documentation
Expands the RAG corpus with more configuration guides
"""

import requests
from pathlib import Path
import time

# Additional Cisco documentation URLs discovered
ADDITIONAL_DOCS = {
    # Configuration Guides
    "catalyst_9300_config_guide_17_6": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9300/software/release/17-6/configuration_guide/b-176-9300-cg.pdf",
        "title": "Cisco IOS-XE 17.6 Configuration Guide - Catalyst 9300",
        "estimated_size_mb": 25.0,
    },
    "catalyst_9500_config_guide_17_6": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9500/software/release/17-6/configuration_guide/b-176-9500-cg.pdf",
        "title": "Cisco IOS-XE 17.6 Configuration Guide - Catalyst 9500",
        "estimated_size_mb": 22.0,
    },
    "catalyst_9200_config_guide_17_6": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9200/software/release/17-6/configuration_guide/consolidated/b-176-9200-cg.pdf",
        "title": "Cisco IOS-XE 17.6 Configuration Guide - Catalyst 9200",
        "estimated_size_mb": 28.0,
    },
    "programmability_guide_17_6": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/176/b_176_programmability_cg.pdf",
        "title": "Cisco IOS-XE 17.6 Programmability Configuration Guide",
        "estimated_size_mb": 8.0,
    },
    # Feature-specific guides (optional, download if time permits)
    "wireless_controller_17_6": {
        "url": "https://www.cisco.com/c/en/us/td/docs/wireless/controller/ewc/17-6/config-guide/ewc_cg_17_6.pdf",
        "title": "Cisco Wireless Controller Config Guide - IOS XE 17.6",
        "estimated_size_mb": 15.0,
        "optional": True,
    },
}


def download_pdf(doc_name: str, doc_info: dict, output_dir: str = "data/raw_docs"):
    """Download a single PDF document"""

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
            print("[ERROR] 404 Not Found - URL may have changed")
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

    print("CISCO IOS-XE ADDITIONAL DOCUMENTATION DOWNLOADER")
    print("=" * 80)
    print(f"Output directory: {output_dir.absolute()}")

    # Separate required and optional docs
    required_docs = {
        k: v for k, v in ADDITIONAL_DOCS.items() if not v.get("optional", False)
    }
    optional_docs = {
        k: v for k, v in ADDITIONAL_DOCS.items() if v.get("optional", False)
    }

    print(f"\nRequired documents: {len(required_docs)}")
    print(f"Optional documents: {len(optional_docs)}")

    # Download required docs
    success_count = 0
    total_size = 0

    print("\n" + "=" * 80)
    print("DOWNLOADING REQUIRED DOCUMENTS")
    print("=" * 80)

    for doc_name, doc_info in required_docs.items():
        if download_pdf(doc_name, doc_info, output_dir):
            success_count += 1
            total_size += doc_info["estimated_size_mb"]

        # Wait between downloads
        if doc_name != list(required_docs.keys())[-1]:
            print("\nWaiting 3 seconds before next download...")
            time.sleep(3)

    # Optionally download optional docs
    if optional_docs and success_count == len(required_docs):
        print("\n" + "=" * 80)
        print("OPTIONAL DOCUMENTS AVAILABLE")
        print("=" * 80)
        print("Required downloads complete!")
        print(f"\nOptional documents available ({len(optional_docs)}):")
        for doc_name, doc_info in optional_docs.items():
            print(f"  - {doc_info['title']}")

    # Summary
    print("\n" + "=" * 80)
    print(
        f"DOWNLOAD SUMMARY: {success_count}/{len(required_docs)} required PDFs downloaded"
    )
    print(f"Estimated total size: {total_size:.1f} MB")
    print("=" * 80)

    # List all downloaded files
    print("\nDownloaded files:")
    pdf_files = sorted(output_dir.glob("*.pdf"))
    total_actual_size = 0
    for pdf in pdf_files:
        size_mb = pdf.stat().st_size / (1024 * 1024)
        total_actual_size += size_mb
        print(f"  {pdf.name}: {size_mb:.1f} MB")

    print(f"\nTotal documentation: {len(pdf_files)} PDFs, {total_actual_size:.1f} MB")

    if success_count > 0:
        print("\nNext steps:")
        print("  1. Extract text from PDFs")
        print("  2. Chunk into 500+ chunks")
        print("  3. Store in ChromaDB")


if __name__ == "__main__":
    main()
