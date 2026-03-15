import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

def load_eval_file(path: str) -> Dict[str, Any]:
    with open(path, 'r') as f:
        data = json.load(f)
        # Handle both old format (list) and new format (dict with metadata)
        if isinstance(data, list):
            return {"metadata": {"timestamp": "old"}, "results": data}
    return data

def calculate_metrics(results: List[Dict]) -> Dict[str, Dict[str, float]]:
    metrics = {}
    for mode in ["vanilla", "rag_locked"]:
        mode_data = [r[mode] for r in results if mode in r and "status" not in r[mode]]
        if not mode_data:
            continue
            
        valid_count = sum(1 for d in mode_data if d["validation"]["status"] == "PASS")
        cfr_count = sum(1 for d in mode_data if d.get("cfr", False))
        cit_val = sum(d.get("citation_validity", 0.0) for d in mode_data) / len(mode_data)
        
        metrics[mode] = {
            "Syntactic Validity": valid_count / len(mode_data),
            "Hallucination Rate": 1 - (valid_count / len(mode_data)),
            "CFR": cfr_count / len(mode_data),
            "Citation Validity": cit_val
        }
    return metrics

def compare_runs(baseline_path: str, latest_path: str):
    baseline = load_eval_file(baseline_path)
    latest = load_eval_file(latest_path)
    
    b_metrics = calculate_metrics(baseline["results"])
    l_metrics = calculate_metrics(latest["results"])
    
    print(f"\nComparing Baseline ({baseline['metadata']['timestamp']}) vs Latest ({latest['metadata']['timestamp']})")
    print(f"Latest Model: {latest['metadata'].get('gemini_model', 'N/A')}")
    print(f"Prompt Version: {latest['metadata'].get('prompt_version', 'N/A')}\n")
    
    comparison = []
    for mode in l_metrics:
        if mode not in b_metrics: continue
        for metric, val in l_metrics[mode].items():
            b_val = b_metrics[mode][metric]
            diff = val - b_val
            
            # For Hallucination and CFR, negative is good
            trend = "🟢" if diff < 0 else "🔴"
            if metric in ["Syntactic Validity", "Citation Validity"]:
                trend = "🟢" if diff > 0 else "🔴"
            if abs(diff) < 0.001: trend = "⚪"
            
            comparison.append({
                "Mode": mode,
                "Metric": metric,
                "Baseline": f"{b_val*100:.1f}%",
                "Latest": f"{val*100:.1f}%",
                "Delta": f"{diff*100:+.1f}%",
                "Trend": trend
            })
            
    df = pd.DataFrame(comparison)
    print(df.to_string(index=False))

if __name__ == "__main__":
    history_dir = Path("results/history")
    if not history_dir.exists() or len(list(history_dir.glob("*.json"))) < 2:
        print("Need at least 2 evaluation runs in results/history/ to compare.")
        sys.exit(0)
        
    runs = sorted(list(history_dir.glob("*.json")))
    compare_runs(str(runs[0]), str(runs[-1]))
