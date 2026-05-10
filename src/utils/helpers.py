import os
import re
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("RAG-NetTwin.Helpers")


def with_retry(max_retries=5, initial_sleep=5):
    """
    Decorator for exponential backoff on RateLimitErrors.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    e_str = str(e).lower()
                    if "rate_limit" in e_str or "429" in e_str:
                        retries += 1
                        # Groq 429 often needs a bit more time
                        sleep_time = initial_sleep * (2 ** (retries - 1))
                        logger.warning(
                            f"Rate limit hit in {func.__name__}. Retrying in {sleep_time}s... ({retries}/{max_retries})"
                        )
                        time.sleep(sleep_time)
                    else:
                        raise e
            return func(*args, **kwargs)  # Last try

        return wrapper

    return decorator


def generate_audit_report(
    intent: Any, configs: Dict[str, Any], output_dir: str = "results/audits"
) -> str:
    """
    Generates a structured Markdown 'Grounding Audit Report' for an intent.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_text = (
        re.sub(r"[^\w\s-]", "", intent.original_text[:30]).strip().replace(" ", "_")
    )
    filename = f"audit_{timestamp}_{safe_text}.md"
    filepath = os.path.join(output_dir, filename)
    report = [
        "# Grounding Audit Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Original Intent:** {intent.original_text}",
        "\n## 1. Structured Intent Analysis",
        f"- **Protocol:** {intent.protocol}",
        f"- **Action:** {intent.action}",
        f"- **Parameters:** `{json.dumps(intent.parameters)}`",
        "\n## 2. Generation & Grounding Details",
    ]
    for device_name, data in configs.items():
        if device_name is not None and device_name.startswith("_"):
            continue
        report.append(f"### Device: {device_name}")
        report.append(f"#### Reasoning Path\n{data.get('reasoning', 'N/A')}")

        report.append("#### Retrieved Documentation Snippets")
        sources = data.get("retrieved_sources", [])
        if sources:
            report.append(f"- **Sources used:** {', '.join(sources)}")
        else:
            report.append(
                "- *No documentation retrieved (Lite path used or no matches).*"
            )
        report.append(
            f"#### Generated Configuration\n```\n{data.get('config', 'N/A')}\n```"
        )

        if "validation" in data:
            val = data["validation"]
            report.append("#### Validation Results (Tier 1)")
            report.append(f"- **Status:** {val.get('status')}")
            if val.get("issues"):
                report.append("- **Issues found:**")
                for issue in val["issues"]:
                    report.append(f"  - [{issue['type']}] {issue['details']}")
    with open(filepath, "w") as f:
        f.write("\n".join(report))
    return filepath
