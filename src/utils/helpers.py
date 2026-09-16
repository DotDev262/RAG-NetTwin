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
    Includes chunk provenance, command-to-source mapping, retrieval quality
    metrics, full grounding context, search queries, and audit trail instructions.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_text = (
        re.sub(r"[^\w\s-]", "", intent.original_text[:30]).strip().replace(" ", "_")
    )
    filename = f"audit_{timestamp}_{safe_text}.md"
    filepath = os.path.join(output_dir, filename)

    # Load chunk index for metadata enrichment
    chunks_index: Dict[str, Any] = {}
    chunks_file = os.path.join("data", "processed_chunks", "all_chunks.json")
    if os.path.exists(chunks_file):
        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                chunks_index = {c["id"]: c for c in json.load(f)}
        except Exception as e:
            logger.warning(f"Could not load chunks index for audit enrichment: {e}")

    # Collect all chunk IDs referenced across all devices for the global audit trail
    all_chunk_ids: set = set()

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
            all_chunk_ids.update(s for s in sources if not s.startswith("BASE_"))
            report.append(f"- **Cited sources ({len(sources)}):** {', '.join(sources)}")
        else:
            report.append(
                "- *No documentation retrieved (Lite path used or no matches).*"
            )

        valid_ids = data.get("valid_source_ids", [])
        if valid_ids:
            all_chunk_ids.update(v for v in valid_ids if not v.startswith("BASE_"))

        report.append(
            f"#### Generated Configuration\n```\n{data.get('config', 'N/A')}\n```"
        )

        # Confidence score
        confidence = data.get("confidence")
        if confidence is not None:
            report.append(f"\n**Confidence Score:** {confidence}")

        # Command-to-Source Mapping (from blocks)
        blocks = data.get("blocks", [])
        if blocks:
            report.append("\n#### Command-to-Source Mapping")
            report.append("| Command | Source IDs |")
            report.append("|---------|-----------|")
            for block in blocks:
                cmds = block.get("commands", [])
                block_sources = block.get("source_ids", [])
                if cmds and block_sources:
                    cmd_display = cmds[0] if len(cmds) == 1 else f"{cmds[0]} (+{len(cmds) - 1} more)"
                    report.append(f"| `{cmd_display}` | {', '.join(block_sources)} |")
            if not any(b.get("source_ids") for b in blocks):
                report.append("| *(no block-level source attribution)* | |")

        if "validation" in data:
            val = data["validation"]
            report.append("\n#### Validation Results (Tier 1)")
            report.append(f"- **Status:** {val.get('status')}")
            if val.get("issues"):
                report.append("- **Issues found:**")
                for issue in val["issues"]:
                    report.append(f"  - [{issue['type']}] {issue['details']}")

    # Section: Chunk Provenance
    if all_chunk_ids:
        report.append("\n## 3. Chunk Provenance")
        report.append("| Chunk ID | Source File | Pages | Vendor | OS Version | Tier |")
        report.append("|----------|-------------|-------|--------|------------|------|")
        for cid in sorted(all_chunk_ids):
            meta = chunks_index.get(cid, {})
            source_file = meta.get("source_file", "Unknown")
            page_range = meta.get("page_range", [])
            pages = f"{page_range[0]}-{page_range[1]}" if len(page_range) >= 2 else str(page_range[0]) if page_range else "N/A"
            vendor = meta.get("vendor", "Unknown")
            os_ver = meta.get("os_version", "Unknown")
            tier = meta.get("tier", "N/A")
            report.append(f"| `{cid}` | {source_file} | {pages} | {vendor} | {os_ver} | {tier} |")

    # Section: Retrieval Quality Metrics
    trace = configs.get("_trace", {})
    retrieval_results = trace.get("retrieval_results", {})
    if retrieval_results:
        report.append("\n## 4. Retrieval Quality Metrics")
        for dev_name, results in retrieval_results.items():
            if not results:
                continue
            report.append(f"\n### {dev_name}")
            distances = [r.get("distance") for r in results if r.get("distance") is not None]
            rerank_scores = [r.get("rerank_score") for r in results if r.get("rerank_score") is not None]
            tiers = [r.get("tier") for r in results if r.get("tier") is not None]

            if distances:
                avg_dist = sum(distances) / len(distances)
                report.append(f"- **Avg Distance:** {avg_dist:.4f} (lower = more relevant)")
            if rerank_scores:
                avg_rerank = sum(rerank_scores) / len(rerank_scores)
                report.append(f"- **Avg Rerank Score:** {avg_rerank:.4f} (higher = more relevant)")
            if tiers:
                tier_counts = {}
                for t in tiers:
                    tier_counts[t] = tier_counts.get(t, 0) + 1
                report.append(f"- **Tier Distribution:** {dict(sorted(tier_counts.items()))}")
            report.append(f"- **Chunks Retrieved:** {len(results)}")

            report.append("\n| Chunk ID | Tier | Distance | Rerank Score | Preview |")
            report.append("|----------|------|----------|--------------|---------|")
            for r in results:
                rid = r.get("id", "N/A")
                rtier = r.get("tier", "N/A")
                rdist = f"{r.get('distance', 'N/A'):.4f}" if r.get("distance") is not None else "N/A"
                rrank = f"{r.get('rerank_score', 'N/A'):.4f}" if r.get("rerank_score") is not None else "N/A"
                preview = r.get("text_preview", "")[:60]
                report.append(f"| `{rid}` | {rtier} | {rdist} | {rrank} | {preview} |")

    # Section: Search Queries
    if trace:
        report.append("\n## 5. Search Queries")
        base_query = trace.get("base_query", "")
        expanded = trace.get("expanded_queries", [])
        if base_query:
            report.append(f"- **Base Query:** `{base_query}`")
        if expanded:
            report.append("- **Expanded Queries:**")
            for q in expanded:
                report.append(f"  - `{q}`")

    # Section: Full Grounding Context
    for device_name, data in configs.items():
        if device_name is not None and device_name.startswith("_"):
            continue
        grounding_ctx = data.get("grounding_context", "")
        if grounding_ctx:
            if "## 6" not in "\n".join(report):
                report.append("\n## 6. Full Grounding Context")
            report.append(f"\n### {device_name}")
            report.append("```")
            report.append(grounding_ctx)
            report.append("```")

    # Section: Sanity Check Warnings
    sanity = configs.get("_sanity_check", {})
    warnings = sanity.get("warnings", [])
    if warnings:
        report.append("\n## 7. Sanity Check Warnings")
        for w in warnings:
            report.append(f"- {w}")

    # Section: Audit Trail Instructions
    report.append("\n## Audit Trail — Trace Back to Source Documentation")
    report.append(
        "To inspect any chunk used in this generation, run the audit demo script:\n"
    )
    if all_chunk_ids:
        sample_ids = sorted(all_chunk_ids)[:5]
        for cid in sample_ids:
            report.append(f"  `uv run python scripts/audit_demo.py {cid}`")
        if len(all_chunk_ids) > 5:
            report.append(f"  *(+{len(all_chunk_ids) - 5} more chunks — see Chunk Provenance above)*")
    report.append(
        "\nOr use interactive mode:\n"
        "  `uv run python scripts/audit_demo.py`\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    return filepath
