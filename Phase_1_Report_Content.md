# PHASE 1 REPORT: VERSION-AWARE RAG FOR RELIABLE NETWORK CLI SYNTHESIS

## CHAPTER-1: INTRODUCTION

### 1.1 BACKGROUND OF STUDY: THE IBN PARADIGM AND NORTHBOUND CHALLENGE
Intent-Based Networking (IBN) represents a shift in network management, aiming to automate the full lifecycle of network services. It translates high-level business policies into device-specific configurations. However, the "Northbound" interface—the translation of abstract intents into vendor-specific CLI commands—remains a source of operational complexity, especially in heterogeneous environments with multiple vendors and operating systems.

### 1.2 PROBLEM IDENTIFICATION: THE RELIABILITY CRISIS IN AI-DRIVEN NETWORKING
Human error is the primary cause of network outages. Current AI models used for translation exhibit a high failure rate (approximately 36% syntax failure rate) when generating low-level CLI. This reliability crisis necessitates a more grounded and verifiable approach to configuration synthesis.

### 1.3 PROBLEM STATEMENT: HALLUCINATION AND VERSION INCONSISTENCY IN CLI SYNTHESIS
Generalist LLMs often produce hallucinated or syntactically invalid commands and introduce version inconsistencies. There is a lack of deterministic grounding in authoritative vendor documentation and a failure to provide robust, real-time verification mechanisms for configurations intended for autonomous deployment.

### 1.4 TECHNICAL FAILURE MODES: SYNTACTIC FABRICATION, VERSION POLLUTION, AND SEMANTIC DRIFT
Failures in AI-driven synthesis manifest in three primary modes: 
1. **Syntactic Fabrication**: Generating commands that do not exist.
2. **Version Pollution**: Mixing commands from incompatible OS versions.
3. **Semantic Drift**: Syntactically correct but operationally incorrect configurations that fail to implement the user's intent.

### 1.5 SCOPE OF WORK: HETEROGENEOUS ENVIRONMENTS AND PROTOCOL FOCUS
The study focuses on heterogeneous environments including Cisco IOS-XE (17.6) and Juniper JunOS (22.4). The protocol focus is primarily on OSPF and BGP routing, alongside ACL and VLAN management.

### 1.6 SIGNIFICANCE: ACHIEVING RELIABILITY-FIRST AI AND AUDIT-READY SYNTHESIS
The proposed system aims for a zero hallucination rate via authoritative grounding and shifts from probabilistic guesses to verifiable, grounded CLI. This "Reliability-First" approach solves the high syntax failure rates of generalist models.

### 1.7 OBJECTIVES: KNOWLEDGE GROUNDING, STATIC VERIFICATION, AND AUDIT TRAILS
The primary objectives are to:
1. Develop a Version-Aware RAG architecture using metadata filtering.
2. Eliminate syntax fabrication by achieving a 0% hallucination rate.
3. Utilize Batfish as a deterministic Syntactic Verification Gate.
4. Provide a Grounding Audit Trail with command-level citations.

### 1.8 BENEFITS OF AUDIT-READY CLI GENERATION AND DETERMINISTIC GATING
Audit-ready synthesis allows for instant source verification by human reviewers, reducing the "Last Mile" search effort. Deterministic gating via static analysis catches errors before they reach production hardware.

### 1.9 SYSTEM MODULES OVERVIEW
The system consists of an Intent Parser, a Version-Aware RAG retrieval pipeline, a Config Generator, a Verification Gate, and an Audit Trail engine.

### 1.10 ATTENTION AND CONTEXT HANDLING IN LARGE LANGUAGE MODELS
The system leverages the self-attention mechanisms of LLMs (like Llama 3.1) while managing context window limitations through hierarchical documentation chunking.

### 1.11 EVALUATION PROTOCOL, VALIDATION AND EMPIRICAL OUTCOMES
Validation is performed against a benchmark of 23 complex intents. Empirical outcomes show an 87% syntactic validity and a 0% hallucination rate.

---

## CHAPTER-2: LITERATURE REVIEW

### 2.1 OVERVIEW OF RESEARCH IN INTENT-BASED NETWORK AUTOMATION
Current research focuses on automating network security, management, and orchestration (Bringhenti et al., 2024; Boutouchent et al., 2024).

### 2.2 INTENT-BASED ARCHITECTURES AND ORCHESTRATION FRAMEWORKS
Architectures like AMANOS propose closed-loop orchestration for 5G, while others target SDN policies (Njah et al., 2024). However, many ignore firmware-level syntax drift.

### 2.3 RETRIEVAL-AUGMENTED GENERATION (RAG) FOR TECHNICAL KNOWLEDGE
RAG is used for industrial knowledge management (Chen et al., 2025) and network intent translation (Wang et al., 2025). Gaps remain in deterministic syntactic validation.

### 2.4 LLM-BASED INTENT ABSTRACTION AND SYNTHESIS MODELS
Models like LLNet (Angi et al., 2025) and GIA (Kou et al., 2025) have advanced intent-to-policy translation but often lack version-aware grounding or last-mile CLI syntax.

### 2.5 LIMITATIONS OF CURRENT TECHNIQUES
#### 2.5.1 VERSION POLLUTION: INCONSISTENT OS RELEASE CONSTRAINTS
Existing systems mix deprecated and current commands due to a lack of version constraints.
#### 2.5.2 THE "BLACK BOX" PROBLEM: ABSENCE OF GROUNDING PROVENANCE
Generated configurations lack documentation citations, forcing manual verification.
#### 2.5.3 PROBABILISTIC FALLIBILITY: LACK OF DETERMINISTIC SYNTACTIC GATING
Pure LLM inference lacks secondary deterministic gates like Batfish.
#### 2.5.4 "SAFETY WASHING" IN HITL: INADEQUATE REVIEWER COGNITIVE TOOLS
"Human in the Loop" often serves as a disclaimer rather than a safety mechanism without proper auditing tools.

### 2.6 LITERATURE SUMMARY TABLE

| Paper No | Authors and Year | Paper Title | Journal Name | Methods Used | Key Findings | Research Gaps |
|:---:|:---|:---|:---|:---|:---|:---|
| 1 | Bringhenti et al. (2024) | Automation for Network Security Configuration | ACM Computing Surveys | Formal verification, MaxSMT, ILP optimization | Categorizes formal policy translation to NSF rules | Lacks Syntactic Validator for vendor-specific CLI |
| 2 | Boutouchent et al. (2024) | AMANOS: Intent-Driven Management | IEEE Comm. Magazine | NLU, Ontology-based models, ML | Proposes closed-loop orchestration for 5G Core | Fails to address physical hardware Syntax Drift |
| 3 | Njah et al. (2024) | AI-Driven Intent-Based Network Architecture | IEEE Comm. Magazine | LLM fine-tuning (BERT), NER, MADRL | BERT-based intent refinement and activation logic | Targets SDN policies rather than Native CLI synthesis |
| 4 | Kerboeuf et al. (2024) | Design Methodology for 6G E2E System | IEEE Open Journal | Architectural blueprinting, E2E modeling | Outlines blueprint for 6G intent-driven automation | Ignores Firmware-level Syntax Drift at the edge |
| 5 | Haj Hussein et al. (2025) | Intelligent IBN Slicing for IoT Systems | IEEE Trans. on NSM | Literature survey, taxonomy definition | Vision for IoT slice management and orchestration | Overlooks Syntactic Synthesis for multi-vendor devices |
| 6 | Chen et al. (2025) | RAG for Industrial Knowledge Management | Computer Standards & Interfaces | RAG, BM25, Cross-encoder, GPT-4 | Metadata-aware RAG for industrial technical manuals | Generates NL text, not machine-executable code |
| 7 | Wang et al. (2025) | Hierarchical Index Retrieval RAG | IEEE Trans. on Mobile Computing | RAG with HIR, Mixture of Experts (MoE) | Combined RAG with hardware manuals for policy | Lacks Deterministic Syntactic Validator for tokens |
| 8 | Su et al. (2024) | Hybrid RAG-Empowered Multimodal LLM | IEEE IoT Journal | Hybrid Multimodal RAG, Cross-chain | Secure medical IoT data management via RAG | Addresses data privacy, not Intent-to-CLI translation |
| 9 | Zhang et al. (2024) | Interactive AI With RAG for Networking | IEEE Network | Interactive AI, RAG, Chain-of-Thought | RAG-assisted AI for network optimization | Assistant for math; generates no structural CLI configs |
| 10 | Alabbasi et al. (2025) | TeleOracle: Fine-Tuned RAG | IEEE IoT Journal | RAG with SLM (Phi-2), LoRA, SelfExtend | SLM-based RAG aligned to 3GPP for technical Q&A | Strictly for Q&A; lacks a Synthesis Engine |
| 11 | Jacobs et al. (2025) | Establishing Trust for NL in IBN | IEEE Trans. on NSM | NER (Bi-LSTM), Ambiguity Detection | LUMI pipeline for NL-to-Policy via Nile | Compiles to intermediate languages, not Native CLI |
| 12 | Kou et al. (2025) | GIA: Generative Intent Abstraction | IEEE Trans. on CCN | LLM code generation, Subgraph isomorphism | LLM-enabled structural policy graphs | Lacks Version-Aware Grounding for specific tokens |
| 13 | Mekrache et al. (2024) | Intent-Based Management of Next-Gen Networks | IEEE Network | LLM (CodeLlama), Few-Shot, RAG | NL-to-JSON translation for 5G descriptors | Targets JSON objects; provides no Last-Mile syntax |
| 14 | Orozco et al. (2025) | Intent-Based Service Provisioning for Cobots | IEEE Trans. on NSM | Intent decomposition, Hierarchical state machines | Business intent-to-3GPP JSON translation | Stops at JSON level; fails to account for Syntax Drift |
| 15 | Angi et al. (2025) | LLNet: Instructing Softwarized Devices | IEEE Trans. on NSM | Small Language Models, QLoRA, Few-shot | SLM-based approach for programmable devices | Targets abstract APIs; ignores CLI Syntactic Volatility |
| 16 | Mehmood et al. (2025) | Knowledge-Driven Intent Life-Cycle | IEEE Trans. on NSM | Knowledge Graph Embedding (KG2E), NER | KGs for metadata-aware intent life-cycle | Lacks Token-level granularity for CLI synthesis |
| 17 | Maatouk et al. (2025) | TeleQnA: Benchmark for LLMs in Telecom | IEEE Network | Automated QnA generation, Text embeddings | 10,000-question benchmark for telecom proficiency | Focuses on evaluation; lacks a Synthesis Engine |
| 18 | Brodimas et al. (2025) | IBN Orchestration Using Agentic-AI | IEEE Open Journal | Multi-Agent System, Model Context Protocol | Multi-agent framework for Infrastructure-as-Code | Generates K8s syntax vs. Legacy Physical CLI |
| 19 | Haj Hussein et al. (2025) | Privacy-Preserving Intelligent IBN Slicing | IEEE IoT Journal | Deep Q-Networks (DQNs), PPNO | Privacy-preserving slicing for cross-domain IoT | Lacks Low-level CLI Accuracy for edge gateways |
| 20 | Huang et al. (2024) | LLMs for Networking: Applications | IEEE Network | Domain-adapted fine-tuning, RAG, CoT | Surveyed LLM techniques for capacity planning | Lacks Syntactic Validator for safe hardware execution |

### 2.7 RESEARCH GAP AND NEED FOR THE PROPOSED SYSTEM
There is a clear need for a system that enforces version locking, provides a verifiable audit trail, and utilizes a deterministic syntactic gate to ensure production-grade reliability.

---

## CHAPTER-3: DATASET DESCRIPTION

### 3.1 OVERVIEW OF THE VENDOR DOCUMENTATION DATASET
The dataset consists of verified documentation from official Cisco and Juniper sources.

### 3.2 SUPPLEMENTARY USE OF COMMAND REFERENCES AND CONFIGURATION GUIDES
Command References and Configuration Guides provide the granular syntax and contextual examples required for synthesis.

### 3.3 DATASET COMPOSITION AND VENDOR-SPECIFIC DISTRIBUTION
The knowledge base includes 10,333 chunks derived from over 50,000 pages of vendor manuals.

### 3.4 ANNOTATION METHODOLOGY AND METADATA TAGGING FOR VERSION LOCKING
Each chunk is tagged with metadata including `vendor`, `os_version`, `cli_mode`, and a `reference_id`.

### 3.5 CHALLENGES REPRESENTED IN THE HETEROGENEOUS DATASET
Challenges include varying documentation styles, overlapping command hierarchies, and syntax drift across OS versions.

### 3.6 DATASET PREPROCESSING AND HIERARCHICAL CHUNKING PIPELINE
Documentation is split into three tiers:
1. **Tier 1**: Command syntax (50-150 tokens).
2. **Tier 2**: Configuration patterns (300-500 tokens).
3. **Tier 3**: Troubleshooting/Feature guides (1000-2000 tokens).

### 3.7 DATASET PARTITIONING AND TEST INTENT SYNTHESIS
A custom benchmark of 23 complex intents (OSPF, BGP, ACL, VLAN) was constructed for evaluation.

---

## CHAPTER-4: BACKGROUND

### 4.1 PRINCIPLES OF INTENT-BASED NETWORKING (IBN)
IBN focuses on abstraction, allowing operators to define "what" is needed rather than "how" to configure it.

### 4.2 LARGE LANGUAGE MODELS (LLMS) IN TECHNICAL DOMAINS
LLMs demonstrate strong context understanding but require grounding to be effective in specialized technical domains like networking.

### 4.3 EVOLUTION OF RETRIEVAL-AUGMENTED GENERATION (RAG)
RAG addresses LLM hallucinations by injecting retrieved, authoritative context into the prompt window.

### 4.4 VECTOR DATABASES AND EMBEDDING TECHNIQUES (CHROMADB)
ChromaDB is used to store and retrieve document embeddings created via models like `bge-small-en-v1.5`.

### 4.5 DETERMINISTIC STATIC ANALYSIS: THE BATFISH ENGINE
Batfish is a configuration analysis tool that provides deterministic validation of syntax and logical structure without live hardware.

---

## CHAPTER-5: METHODOLOGY

### 5.1 OVERVIEW OF THE PROPOSED SYSTEM ARCHITECTURE
The architecture follows a modular pipeline: Intent Parsing -> Version-Aware RAG -> CLI Synthesis -> Syntactic Gating.

### 5.2 INTENT PARSING AND STRUCTURED EXTRACTION
Natural language is converted into structured JSON using Pydantic models to ensure parameter integrity.

### 5.3 DATA PREPROCESSING AND CHUNKING LOGIC
Documentation is hierarchically chunked to preserve command-to-mode relationships.

### 5.4 MODEL ARCHITECTURE – LLM SYNTHESIS ENGINE
The synthesis engine uses Llama 3.1 (8B) via the Groq API for low-latency inference.

### 5.5 VERSION-AWARE RETRIEVAL MODULE
Retrieval uses "hard filters" on metadata (vendor/version) followed by semantic similarity search.

### 5.6 SYNTACTIC VERIFICATION GATE (BATFISH LINTER)
Configurations are passed through Batfish; if errors are found, the system attempts up to 3 automated refinements.

### 5.7 GROUNDING AUDIT TRAIL AND CITATION ENGINE
For every command block, the engine embeds a comment citing the specific `reference_id` from the documentation.

### 5.8 IMPLEMENTATION AND PROTOTYPE DETAILS
The prototype is a Python application integrating LangChain, ChromaDB, and Batfish.

---

## CHAPTER-6: EVALUATION METRICS

### 6.1 OVERVIEW OF EVALUATION METRICS IN CONFIGURATION SYNTHESIS
Metrics measure syntactic correctness, factual grounding, and semantic intent alignment.

### 6.2 SYNTACTIC VALIDITY AND BATFISH PASS RATES
Percentage of generated configurations that pass all Batfish static analysis checks.

### 6.3 HALLUCINATION-FREE RATE AND GROUNDING ACCURACY
The percentage of synthesized commands that are found in verified vendor documentation.

### 6.4 SEMANTIC FAITHFULNESS AND INTENT MAPPING
Measures how accurately the synthesized CLI maps to the specific parameters provided in the user intent.

### 6.5 CRITICAL FAILURE RATE (CFR) AND SILENT ERROR DETECTION
Quantifies "silent" semantic errors that pass syntax checks but fail operational requirements.

---

## CHAPTER-7: EXPERIMENTAL RESULTS

### 7.1 PHASE 1 PERFORMANCE COMPARISON: PROPOSED SYSTEM VS. VANILLA LLM
The proposed system achieved 87.0% syntactic validity compared to 64.0% for the vanilla baseline.

### 7.2 ANALYSIS OF HALLUCINATION REDUCTION (0% SYNTAX FABRICATION)
Authoritative grounding effectively eliminated syntax fabrication (0.0% vs 4.3%).

### 7.3 SYNTACTIC VALIDITY RESULTS (87.0% SUCCESS RATE)
Validation via Batfish confirmed a 23% improvement in syntactic correctness over baseline models.

### 7.4 EVALUATION OF SEMANTIC DRIFT AND CRITICAL FAILURES
The system identified a 17.4% Critical Failure Rate, a significant reduction from the 36%+ seen in generalist models.

### 7.5 ANALYSIS OF THE GROUNDING AUDIT TRAIL UTILITY
The audit trail achieved a 49,000:1 cognitive compression ratio, greatly simplifying human verification.

---

## CHAPTER-8: CONCLUSION AND FUTURE WORK

### 8.1 CONCLUSION
Phase 1 demonstrates that version-aware RAG combined with deterministic gating can successfully eliminate CLI hallucinations and significantly improve the reliability of intent translation.

### 8.2 FUTURE WORK
- **Phase 2**: Integration of GNS3 for dynamic Digital Twin testing and operational validation.
- **Phase 3**: Development of a feedback-driven self-correction mechanism using structured log parsing.

---

## CHAPTER-9: REFERENCES
*(Refer to Slide 21-22 for full IEEE bibliography)*
