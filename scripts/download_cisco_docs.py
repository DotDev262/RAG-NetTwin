#!/usr/bin/env python3
"""
Cisco IOS-XE Documentation Downloader
Downloads command reference documentation from Cisco's public website
"""

import requests
from pathlib import Path
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import json
from datetime import datetime


class CiscoDocDownloader:
    """Download Cisco IOS-XE documentation"""

    def __init__(self, output_dir: str = "data/raw_docs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Headers to mimic browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Documentation URLs from Perplexity
        self.doc_urls = {
            "catalyst_9300_cmdref_17_6": {
                "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9300/software/release/17-6/command_reference/b_176_9300_cr.html",
                "title": "Catalyst 9300 Command Reference 17.6",
                "platform": "catalyst9300",
                "version": "17.6",
            },
            "catalyst_9500_cmdref_17_6": {
                "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9500/software/release/17-6/command_reference/b_176_9500_cr.html",
                "title": "Catalyst 9500 Command Reference 17.6",
                "platform": "catalyst9500",
                "version": "17.6",
            },
        }

        self.download_log = []

    def download_html_doc(self, doc_name: str, save_as_text: bool = True):
        """
        Download HTML documentation and optionally convert to text

        Args:
            doc_name: Key from self.doc_urls
            save_as_text: If True, also save as plain text for easier processing
        """
        if doc_name not in self.doc_urls:
            print(f"Error: Unknown document '{doc_name}'")
            return False

        doc_info = self.doc_urls[doc_name]
        url = doc_info["url"]

        print(f"\nDownloading: {doc_info['title']}")
        print(f"URL: {url}")

        try:
            # Download HTML
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            # Save HTML
            html_filename = f"{doc_name}.html"
            html_path = self.output_dir / html_filename

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            print(f"[OK] Saved HTML: {html_path}")

            # Convert to text if requested
            if save_as_text:
                text_content = self.html_to_text(response.text, url)
                text_filename = f"{doc_name}.txt"
                text_path = self.output_dir / text_filename

                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

                print(f"[OK] Saved text: {text_path}")
                print(f"  Size: {len(text_content):,} characters")

            # Log download
            self.download_log.append(
                {
                    "doc_name": doc_name,
                    "title": doc_info["title"],
                    "url": url,
                    "html_file": str(html_path),
                    "text_file": str(text_path) if save_as_text else None,
                    "timestamp": datetime.now().isoformat(),
                    "size_bytes": len(response.text),
                    "status": "success",
                }
            )

            return True

        except requests.exceptions.RequestException as e:
            print(f"[FAIL] Failed to download {doc_name}: {e}")

            self.download_log.append(
                {
                    "doc_name": doc_name,
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed",
                    "error": str(e),
                }
            )

            return False

    def html_to_text(self, html_content: str, base_url: str) -> str:
        """
        Convert HTML to clean text while preserving structure

        Args:
            html_content: Raw HTML string
            base_url: Base URL for resolving relative links

        Returns:
            Clean text content
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()

        # Extract text with better formatting
        lines = []

        # Get title
        title = soup.find("title")
        if title:
            lines.append(f"# {title.get_text(strip=True)}\n")

        # Process main content areas
        # Cisco docs usually have content in article or main tags
        content_areas = soup.find_all(
            ["article", "main", "div"],
            class_=lambda x: x and ("content" in x.lower() if x else False),
        )

        if not content_areas:
            # Fallback to body
            content_areas = [soup.find("body")]

        for area in content_areas:
            if not area:
                continue

            # Get all text elements
            for elem in area.find_all(
                ["h1", "h2", "h3", "h4", "p", "pre", "code", "li"]
            ):
                text = elem.get_text(strip=True)

                if not text:
                    continue

                # Add formatting based on element type
                if elem.name in ["h1", "h2"]:
                    lines.append(f"\n## {text}\n")
                elif elem.name == "h3":
                    lines.append(f"\n### {text}\n")
                elif elem.name == "h4":
                    lines.append(f"\n#### {text}\n")
                elif elem.name == "pre":
                    # Code blocks - preserve formatting
                    lines.append(f"\n```\n{text}\n```\n")
                elif elem.name == "code":
                    # Inline code
                    lines.append(f"`{text}`")
                elif elem.name == "li":
                    # List items
                    lines.append(f"- {text}")
                else:
                    # Regular paragraphs
                    lines.append(text)

        # Join lines and clean up
        text = "\n".join(lines)

        # Clean up extra whitespace
        text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

        # Add metadata header
        header = f"""Source: {base_url}
Downloaded: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Format: Cisco IOS-XE Command Reference

{"=" * 80}

"""

        return header + text

    def download_all(self):
        """Download all configured documents"""
        print("=" * 80)
        print("CISCO IOS-XE DOCUMENTATION DOWNLOADER")
        print("=" * 80)
        print(f"\nOutput directory: {self.output_dir.absolute()}")
        print(f"Documents to download: {len(self.doc_urls)}\n")

        success_count = 0

        for doc_name in self.doc_urls:
            if self.download_html_doc(doc_name, save_as_text=True):
                success_count += 1

            # Be polite - wait between requests
            time.sleep(2)

        # Save download log
        log_path = self.output_dir / "download_log.json"
        with open(log_path, "w") as f:
            json.dump(self.download_log, f, indent=2)

        print("\n" + "=" * 80)
        print(f"DOWNLOAD COMPLETE: {success_count}/{len(self.doc_urls)} successful")
        print(f"Log saved to: {log_path}")
        print("=" * 80)

        return success_count

    def verify_downloads(self):
        """Verify downloaded files exist and have content"""
        print("\n" + "=" * 80)
        print("VERIFYING DOWNLOADS")
        print("=" * 80)

        for entry in self.download_log:
            if entry["status"] != "success":
                continue

            html_path = Path(entry["html_file"])
            text_path = Path(entry["text_file"]) if entry["text_file"] else None

            html_size = html_path.stat().st_size if html_path.exists() else 0
            text_size = (
                text_path.stat().st_size if text_path and text_path.exists() else 0
            )

            print(f"\n{entry['doc_name']}:")
            print(
                f"  HTML: {html_size:,} bytes {'[OK]' if html_size > 1000 else '[FAIL]'}"
            )
            if text_path:
                print(
                    f"  Text: {text_size:,} bytes {'[OK]' if text_size > 1000 else '[FAIL]'}"
                )


def main():
    """Main entry point"""
    downloader = CiscoDocDownloader()

    # Download all documents
    success_count = downloader.download_all()

    # Verify downloads
    downloader.verify_downloads()

    if success_count == 0:
        print("\n[WARNING] No documents were downloaded successfully!")
        print("This could be due to:")
        print("  - Network connectivity issues")
        print("  - Cisco website blocking automated requests")
        print("  - URLs being moved or changed")
        print("\nAlternative: Try manually downloading from:")
        print(
            "  https://www.cisco.com/c/en/us/support/ios-nx-os-software/ios-xe-17/products-command-reference-list.html"
        )
    else:
        print(f"\n[SUCCESS] Downloaded {success_count} document(s)")
        print(f"\nNext steps:")
        print("  1. Check data/raw_docs/ directory")
        print("  2. Review downloaded text files")
        print("  3. Run chunking pipeline")


if __name__ == "__main__":
    main()
