# Graph Report - src  (2026-05-15)

## Corpus Check
- 39 files · ~23,897 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 452 nodes · 569 edges · 66 communities (32 shown, 34 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 95 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5a63e45b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]

## God Nodes (most connected - your core abstractions)
1. `VectorStore` - 36 edges
2. `IntentParser` - 19 edges
3. `ConfigGenerator` - 18 edges
4. `GNS3Validator` - 18 edges
5. `StructuredIntent` - 18 edges
6. `MultiVendorCoordinator` - 11 edges
7. `InventoryResolver` - 10 edges
8. `CommandBlock` - 10 edges
9. `DeviceConfigOutput` - 10 edges
10. `DSPyIntentParser` - 9 edges

## Surprising Connections (you probably didn't know these)
- `refine()` --calls--> `clean_cli_prose()`  [INFERRED]
  rag/config_generator.py → utils/text.py
- `VectorStore` --uses--> `Settings`  [INFERRED]
  rag/vector_store.py → config.py
- `reindex_with_cli_focus()` --calls--> `VectorStore`  [INFERRED]
  data_processing/cli_chunker.py → rag/vector_store.py
- `CLIExtractor` --uses--> `VectorStore`  [INFERRED]
  data_processing/cli_extractor.py → rag/vector_store.py
- `reindex_cli_chunks()` --calls--> `VectorStore`  [INFERRED]
  data_processing/cli_extractor.py → rag/vector_store.py

## Communities (66 total, 34 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (41): BaseModel, EnsembleEngine, EnsembleJudgeResponse, EnsembleResult, Ensemble engine for multi-model voting.     Generates configs using multiple mod, 1. Generate candidates from multiple models.         2. Use a judge to compare a, HallucinationReport, Hallucination Detection Module for RAG-NetTwin.  This module detects common LLM (+33 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (20): BlastRadiusAnalyzer, Analyzes the 'Blast Radius' of a network change by comparing pre/post states (Re, Uses an LLM to diff the network states and summarize the impact., GNS3Exporter, Exports a StructuredIntent to a GNS3 project file (.gns3).     This enables "Top, Converts the StructuredIntent into a GNS3 project JSON structure and writes to d, Community-Aware Retrieval (SOTA GraphRAG):         Identifies the community clus, Community-Aware Retrieval (SOTA GraphRAG):         Identifies the community clus (+12 more)

### Community 2 - "Community 2"
Cohesion: 0.1
Nodes (14): GNS3Validator, PortManager, Pushes configurations to a set of nodes., Manages free ports for GNS3 nodes to avoid conflicts., Captures a snapshot of the network state for Blast Radius analysis (Recommendati, Polls the console of all nodes until a prompt is detected.         Returns True, Finds existing project by name or creates a new one., Deletes all nodes and links in the current project for a clean slate. (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (17): BaseSettings, Loads the specialized documentation knowledge graph from the graphify-out direct, Loads the specialized documentation knowledge graph from the graphify-docs direc, Loads the specialized documentation knowledge graph from the graphify-docs direc, Builds the BM25 index from current ChromaDB contents., Builds the BM25 index from current ChromaDB contents., Builds the BM25 index from current ChromaDB contents., Initialize the VectorStore.          Args:             persist_dir: Optional cus (+9 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (16): generate_audit_report(), Decorator for exponential backoff on RateLimitErrors., Generates a structured Markdown 'Grounding Audit Report' for an intent., with_retry(), calculate_mrr(), calculate_ndcg(), Calculates Normalized Discounted Cumulative Gain (NDCG) for a single relevant it, Calculates Mean Reciprocal Rank (MRR). (+8 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (11): CacheManager, Manages evaluation results caching on disk., Check if a cache entry is expired based on its status., HallucinationDetector, Verifies that all numeric identifiers in the config were authorized.         Tar, Robust grounding check: verifies if config tokens are present in documentation, Detects common LLM hallucinations in network configurations.      This detector, Detect hallucinations in a generated configuration. (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (14): LLM Provider Module Re-exports., _get_gemini_llm(), _get_groq_llm(), _get_llamacpp_llm(), get_llm(), get_structured_llm(), LLMProvider, LLM Provider Module for RAG-NetTwin.  This module provides a factory pattern for (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (13): ABC, NetworkValidator, NetworkValidator, Returns metadata about the validation tier., Abstract Base Class for all network configuration validators., BatfishValidator, Batfish Validator Module for RAG-NetTwin.  This module provides Tier 1 static an, Validates a set of network device configurations. (+5 more)

### Community 8 - "Community 8"
Cohesion: 0.15
Nodes (13): IntentParser, _legacy_parse_with_retry(), _parse_chunk(), Saves processed intents to disk., Original LangChain-based parsing logic (Fallback) with optional retry logic., Original LangChain-based parsing logic without retry logic., Original LangChain-based parsing logic (Fallback) with optional retry logic., Original LangChain-based parsing logic without retry logic. (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (13): Vector Store Module for RAG-NetTwin.  This module manages the ChromaDB vector da, Add chunks to vector database in batches.          This method processes chunks, Add chunks to vector database in batches with CPU throttling.          Args:, Add chunks to vector database in batches with CPU throttling.          Args:, Manages ChromaDB vector database for RAG.      This class provides an interface, Manages ChromaDB vector database for RAG.      This class provides an interface, Efficiency Phase 1: Semantic Intent Cache.         Adds a parsed intent to the s, Efficiency Phase 1: Semantic Intent Cache.         Adds a parsed intent to the s (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (11): InteroperabilityConstraint, MultiVendorCoordinator, NetworkMasterPlan, Represents a shared parameter that must match across different vendors., Uses an LLM to pre-calculate a consistent network plan for all devices., Performs a post-generation check to see if all configs respected the constraints, Performs a post-generation check to see if all configs respected the constraints, Proposed global parameters for a multi-device intent. (+3 more)

### Community 11 - "Community 11"
Cohesion: 0.16
Nodes (8): DSPyIntentParser, InventoryResolver, Inventory Resolver Module for RAG-NetTwin.  This module resolves device metadata, Uses NAPALM to fetch real version info from a device.          This method conne, Resolves device metadata (vendor, OS, version) from an inventory.      This clas, Initialize the InventoryResolver.          Args:             inventory_path: Opt, Load local inventory mapping from JSON file.          Returns:             Dicti, Main entry point to resolve device facts.          This method attempts to resol

### Community 12 - "Community 12"
Cohesion: 0.16
Nodes (11): CLIExtractor, CLI-Focused Chunk Extractor for RAG-NetTwin.  This module extracts individual CL, Extract CLI commands from plain text.          This method scans the input text, Extract CLI commands from a PDF file.          This method reads a PDF, extracts, Re-index the vector store with CLI-focused chunks.      This is a standalone fun, Extracts CLI commands from documentation PDFs.      This class uses regex patter, reindex_cli_chunks(), extract_text_from_pdf() (+3 more)

### Community 13 - "Community 13"
Cohesion: 0.18
Nodes (13): extract_cli_examples(), extract_semantic_chunks(), process_file_with_cli_extraction(), Enhanced CLI-Focused Chunker for RAG-NetTwin.  This module extracts CLI command, Extract CLI command examples with context from text.      This function uses mul, Extract CLI command examples with context from text.      This function uses mul, Extracts high-level semantic chunks (Recommendation 1).     Tier 2: Semantic Par, Extracts high-level semantic chunks (Recommendation 1).     Tier 2: Semantic Par (+5 more)

### Community 14 - "Community 14"
Cohesion: 0.17
Nodes (9): Retrieve relevant chunks for a query.          This is the core retrieval method, Retrieve relevant chunks for a query.          This is the core retrieval method, Retrieve relevant chunks for a query.          This is the core retrieval method, Performs Hybrid Search using Reciprocal Rank Fusion (RRF).         Combines Sema, Internal hybrid retrieval logic., Performs Hybrid Search using Reciprocal Rank Fusion (RRF).         Combines Sema, Performs Hybrid Search using Reciprocal Rank Fusion (RRF).         Combines Sema, Internal hybrid retrieval logic. (+1 more)

### Community 16 - "Community 16"
Cohesion: 0.31
Nodes (6): JsonFormatter, LogEntry, Strict schema for research and system logs., JSON log formatter using Pydantic for schema enforcement., Configures a structured logger., setup_logger()

### Community 17 - "Community 17"
Cohesion: 0.36
Nodes (7): Enum, IntentSignature, Translate a natural language network intent into a structured format.     You mu, ActionType, BatchStructuredIntent, DeviceIntent, StructuredIntent

### Community 18 - "Community 18"
Cohesion: 0.33
Nodes (5): _dspy_parse_with_retry(), Internal DSPy call with optional retry logic., Internal DSPy call with optional retry logic., Internal DSPy call without retry logic., Internal DSPy call without retry logic.

### Community 19 - "Community 19"
Cohesion: 0.29
Nodes (5): Adds examples to the few-shot collection.         Each example should have 'inte, Adds examples to the few-shot collection.         Each example should have 'inte, Adds examples to the few-shot collection.         Each example should have 'inte, Adds Intent-to-Config examples to the gold standard collection.         Examples, Adds Intent-to-Config examples to the gold standard collection.         Examples

### Community 21 - "Community 21"
Cohesion: 0.33
Nodes (4): Translates a batch of NL texts into StructuredIntent objects in parallel chunks., Translates a batch of NL texts into StructuredIntent objects in parallel chunks., Translates NL text to StructuredIntent object using DSPy., Translates NL text to StructuredIntent object using DSPy.

### Community 22 - "Community 22"
Cohesion: 0.5
Nodes (3): Retrieves the most similar intent-to-json examples., Retrieves the most similar intent-to-json examples., Retrieves the most similar intent-to-json examples.

### Community 23 - "Community 23"
Cohesion: 0.5
Nodes (3): Retrieves the most similar Intent-to-Config examples for a vendor., Retrieves the most similar Intent-to-Config examples for a vendor., Retrieves the most similar Intent-to-Config examples for a vendor.

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (3): Adds a successfully generated configuration to the semantic cache., Adds a successfully generated configuration to the semantic cache., Adds a successfully generated configuration to the semantic cache.

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (3): Get database statistics.          Returns basic statistics about the vector stor, Get database statistics.          Returns basic statistics about the vector stor, Get database statistics.          Returns basic statistics about the vector stor

### Community 26 - "Community 26"
Cohesion: 0.5
Nodes (3): Reorders chunks to put most relevant information at the beginning and end., Reorders chunks to put most relevant information at the beginning and end., Reorders chunks to put most relevant information at the beginning and end.

## Knowledge Gaps
- **230 isolated node(s):** `Configuration Module for RAG-NetTwin.  This module defines system-wide settings`, `System-wide settings for RAG-NetTwin using Pydantic V2.`, `Ensure required keys are present for the selected LLM provider.`, `High-Accuracy PDF Text Extractor for RAG-NetTwin.  This module uses OpenDataLoad`, `Extracts text from a PDF file using OpenDataLoader.      Args:         pdf_path:` (+225 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `VectorStore` connect `Community 9` to `Community 0`, `Community 1`, `Community 3`, `Community 5`, `Community 8`, `Community 11`, `Community 12`, `Community 13`, `Community 14`, `Community 17`, `Community 19`, `Community 22`, `Community 23`, `Community 24`, `Community 25`, `Community 26`?**
  _High betweenness centrality (0.343) - this node is a cross-community bridge._
- **Why does `StructuredIntent` connect `Community 17` to `Community 0`, `Community 1`, `Community 2`, `Community 7`, `Community 8`, `Community 11`, `Community 18`, `Community 21`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Why does `IntentParser` connect `Community 8` to `Community 1`, `Community 9`, `Community 11`, `Community 17`, `Community 18`, `Community 21`, `Community 27`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `VectorStore` (e.g. with `CLIExtractor` and `IntentSignature`) actually correct?**
  _`VectorStore` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `str` (e.g. with `reindex_with_cli_focus()` and `.analyze()`) actually correct?**
  _`str` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `IntentParser` (e.g. with `StructuredIntent` and `BatchStructuredIntent`) actually correct?**
  _`IntentParser` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `ConfigGenerator` (e.g. with `EnsembleResult` and `EnsembleJudgeResponse`) actually correct?**
  _`ConfigGenerator` has 10 INFERRED edges - model-reasoned connections that need verification._