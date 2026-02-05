# RAG-NetTwin: Next Steps & Resumption Guide

## 🚀 Immediate Priority
**Run the Evaluation Suite**:
Once your Groq API rate limit resets (usually after 60 minutes), run the benchmark to collect the first batch of comparative data.
```bash
uv run python src/evaluation/evaluator.py
```
*Note: The system is now tuned to retrieve 15 chunks (10 Tier-1, 5 Tier-2) and provide pure CLI output with minimal explanation.*

## 🛠️ Ongoing Implementation Tasks
1. **Full Batfish Integration**:
   - Start the Batfish Docker container: `docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish`
   - Run `tests/test_validation.py` to verify static analysis works.
   
2. **Dashboard Testing**:
   - Run the backend: `uv run python ui/backend/main.py`
   - Open `ui/frontend/index.html` to test the multi-tier validation UI visually.

3. **GNS3 Automation (Tier 3)**:
   - Continue implementing the `GNS3Validator` logic to push configs via Telnet/Console API.

4. **Multi-Vendor Coordination**:
   - Create more complex multi-vendor scenarios in `tests/test_multi_vendor.py` (e.g., BGP or static routing between Cisco and Juniper).

## 📝 Research Data Collection
- **Target**: Run the `evaluator.py` with 50+ diverse intents.
- **Analysis**: Compare `results/benchmark_report.json` outputs. Use the citations (`! Based on [chunk_...]`) to prove grounding in your journal paper.

---
**Status**: Phase 1 Scaffolding Complete. Ingestion Complete (1,690 chunks). Multi-Vendor logic active.
**Last Action**: Optimized ConfigGenerator for high-precision retrieval.
