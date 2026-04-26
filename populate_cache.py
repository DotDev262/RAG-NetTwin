
import json
import os
from pathlib import Path
from datetime import datetime

def populate():
    latest_file = "results/paper_evaluation_tiered_latest.json"
    if not os.path.exists(latest_file):
        print("Latest results not found.")
        return

    with open(latest_file, "r") as f:
        data = json.load(f)

    rag_cache = {}
    vanilla_cache = {}
    
    # We need to simulate the key generation logic from run_paper_eval.py
    # key = f"{intent.vendor}_{intent.protocol}_{intent.action}_{hash}"
    # Since we don't have the original intent object easily, we'll need to be careful.
    # Actually, the evaluator just uses get_intent_key(intent)
    
    # Let's see if we can just run the evaluator and have it save what it has.
    # But wait, it already ran and didn't save.
    
    print(f"Read {len(data['results'])} results from {latest_file}")
    
    # Re-running the eval script with the fix should save the caches IF it hits the hits.
    # But it currently checks self.rag_cache which is empty.

    # I'll just write a script that reconstructs the caches from the report.
    # The key in RAG cache is the intent text + metadata hash.
    # It might be easier to just MODIFY run_paper_eval.py to LOAD from the latest report as a fallback.

if __name__ == "__main__":
    populate()
