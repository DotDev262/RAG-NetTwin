
import json
import os
from datetime import datetime

def recover():
    latest_file = "results/paper_evaluation_tiered_latest.json"
    if not os.path.exists(latest_file):
        print("Latest results not found.")
        return

    with open(latest_file, "r") as f:
        data = json.load(f)

    rag_cache = {}
    vanilla_cache = {}
    
    timestamp = datetime.now().isoformat()
    
    for res in data['results']:
        scenario = res['scenario']
        
        if 'rag_nettwin' in res:
            rag_cache[scenario] = {
                "value": res['rag_nettwin'],
                "timestamp": timestamp,
                "mode_tag": "tiered"
            }
            
        if 'vanilla' in res:
            vanilla_cache[scenario] = {
                "value": res['vanilla'],
                "timestamp": timestamp,
                "mode_tag": "vanilla"
            }
            
    with open("results/rag_cache.json", "w") as f:
        json.dump(rag_cache, f, indent=2)
        
    with open("results/vanilla_cache.json", "w") as f:
        json.dump(vanilla_cache, f, indent=2)
        
    print(f"Recovered {len(rag_cache)} RAG entries and {len(vanilla_cache)} vanilla entries.")

if __name__ == "__main__":
    recover()
