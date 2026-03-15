# Knowledge Grounded Intent Translation: A Version-Aware RAG Architecture for Hallucination-Mitigated CLI Synthesis in Heterogeneous IBN

**Abstract**  
The integration of Large Language Models (LLMs) into Intent-Based Networking (IBN) promises to bridge the gap between high-level operational goals and low-level CLI configurations. However, LLMs frequently suffer from "hallucinations" and "version pollution," where incompatible commands are erroneously mixed. This paper presents a **Version-Aware Retrieval-Augmented Generation (RAG)** architecture designed as an **Expert-in-the-Loop Diagnostic Tool** for high-fidelity CLI synthesis in heterogeneous environments (Cisco IOS-XE and Juniper JunOS). Our approach leverages **Hierarchical Knowledge Grounding**, where LLM generation is strictly constrained by metadata-filtered vendor documentation. We introduce a **Syntactic Verification Gate** using the Batfish static analysis engine to provide deterministic feedback. While version-locked grounding reduces syntactic hallucinations by 94%, we identify a **2.8% Critical Failure Rate (CFR)**—silent, semantic errors that pass syntactic checks but fail operational intent. We conclude that current AI-driven synthesis is unsuitable for autonomous deployment and instead propose a **Grounding Audit** framework that surfaces authoritative documentation citations to assist human expert review; a pilot study suggests up to a **35% reduction** in verification latency.

---

## 1. Introduction

Intent-Based Networking (IBN) seeks to automate the lifecycle of network services by translating high-level business "intents" into device-specific configurations. While modern LLMs show promise in CLI synthesis, their application in critical network infrastructure is hindered by **non-deterministic, silent failure modes**:
1.  **Syntactic Fabrication**: Generating commands that do not exist.
2.  **Version Incompatibility**: Using parameters or hierarchies not present in the target OS version.
3.  **Semantic Drift (Silent Failures)**: Generating syntactically valid code that fails to implement the user's intent or violates safety policies.

We argue that current LLM-based systems for networking suffer from a **"Safety-Washing"** problem, where "Human-in-the-Loop" (HITL) is used as a liability transfer rather than a true safety mechanism. We propose a **Knowledge Grounded Intent Translation** framework that shifts the paradigm from *autonomous generation* to **Audit-Ready Synthesis**. By "grounding" the LLM in a version-locked vector database and enforcing a syntactic gate, we provide a deterministic filter and an **Audit Trail** of authoritative documentation chunks for every synthesized command.

---

## 2. System Architecture

The architecture consists of three modules: the **Intent Translator**, the **Version-Aware RAG Pipeline**, and the **Syntactic Verification Gate**.

### 2.1 Intent Translation & Structuring
User intents are first processed into a **Structured Intent (Pydantic Schema)**. This enforces an "OS Version Lock" (e.g., Cisco IOS-XE 17.6), which serves as the primary filter for all subsequent retrieval operations.

### 2.2 Version-Aware RAG (Knowledge Grounding)
The core of our system is a **Hierarchical Vector Store** (ChromaDB) containing verified chunks of vendor documentation.
-   **Metadata Filtering**: Our system applies a **hard filter** at the retrieval layer: `vendor == {intent.vendor}` AND `os_version == {intent.version}`. This ensures the LLM's context window contains *only* valid commands for the target platform.
-   **Coordinated Retrieval (Heuristic)**: For multi-device intents (e.g., OSPF between Cisco and Juniper), the system retrieves documentation for *all* involved vendors simultaneously. This provides the LLM with the context needed to attempt parameter alignment (e.g., matching Hello timers), though we emphasize this is a **probabilistic heuristic** rather than a deterministic mechanistic coordination. **We explicitly advise Tier 2 (Emulation) validation for all heterogeneous configurations to ensure protocol interoperability.**
-   **Grounding Audit Trail**: For every command block generated, the system embeds a comment citing the specific **Reference ID** and **Metadata (Vendor/Version)** of the source documentation chunk.

### 2.3 Syntactic Verification Gate (Tier 1)
We implement a **Syntactic Verification Gate** powered by **Batfish**.
-   **Static Analysis**: The generated config is parsed to detect syntax errors and undefined references.
-   **Fail-Safe Policy (Batfish Coverage)**: In our evaluation of Cisco IOS-XE 17.6 features, we observed an **8.2% Unsupported Command Rate** in Batfish. To mitigate risk, the system defaults to a **"REJECT_FOR_MANUAL_REVIEW"** status for any command not supported by the Batfish parser. **Operators should expect approximately 10% of synthesized commands to require manual review due to these coverage gaps.** This ensures the gate remains a deterministic filter rather than a "fail-open" vulnerability.

---

## 3. Methodology

### 3.1 Data Engineering
We constructed a corpus of 50,000+ pages from official Cisco and Juniper references. We used a **Semantic-Aware PDF Extraction** pipeline to preserve the hierarchy of CLI commands, ensuring that sub-mode commands (e.g., under `interface` or `router ospf`) are stored with their parent context.

### 3.2 Failure Mode Analysis & The "Silent Failure" Problem
To address the safety concerns inherent in LLM-based systems, we categorize failure modes into three tiers:
1.  **Syntactic Failures**: Detected by the Batfish Syntactic Gate (e.g., typos, invalid hierarchies).
2.  **Grounding Failures**: Detected by the RAG pipeline when documentation is insufficient ("INSUFFICIENT_CONTEXT").
3.  **Semantic Failures (Critical)**: Syntactically valid configurations that fail to implement the intent (e.g., MTU mismatch, incorrect timer alignment).

Our evaluation includes a **Critical Failure Rate (CFR)** metric to quantify these "silent failures." We hypothesize that **Reviewer Fatigue** is a significant bottleneck: as syntactic accuracy increases (99.4%), human reviewers may become less vigilant. To combat this, we introduce the **Citation-Validity Metric**, measuring the presence of authoritative citations. Note that this metric evaluates the *linkage* to documentation rather than the semantic correctness of the command itself.

---

## 4. Results & Discussion

### 4.1 Quantitative Evaluation
| Metric | Vanilla LLM | Unfiltered RAG | **Version-Aware RAG (Ours)** |
| :--- | :--- | :--- | :--- |
| **Hallucination Rate** | 23.1% | 8.4% | **1.2%** |
| **Syntactic Validity** | 71.2% | 88.5% | **99.4%** |
| **Critical Failure Rate (CFR)** | 12.5% | 5.2% | **2.8%** |
| **Citation Validity** | N/A | 72.4% | **98.2%** |

While version-locked grounding reduces hallucinations to 1.2%, the **2.8% CFR** highlights the inherent risks. However, the **98.2% Citation Validity** provides a high-confidence audit trail, allowing experts to verify "ground truth" without manual documentation searches.

### 4.2 Human Behavior & Utility Study
We conducted a preliminary pilot study with 5 network engineers. Key findings include:
-   **Time-to-Verification**: Pilot results suggest that experts using the Grounding Audit Trail verified configurations **up to 35% faster** than those reviewing Vanilla LLM outputs, as citations allowed for immediate "Fact Checking" against authoritative chunks.
-   **Vigilance Retention**: Explicit citations reduced "blind trust" by forcing the reviewer to periodically cross-reference the generated config with the surfaced documentation chunk.
-   **Value Proposition**: The primary utility of RAG-NetTwin is as a **Knowledge-Retrieval Accelerator**, reducing the search latency for complex CLI syntax from minutes to seconds.

---

## 5. Conclusion & Future Work

This paper introduced a **Version-Aware RAG Architecture** that provides a grounded and verifiable bridge from intent to configuration. While we demonstrate a significant reduction in syntactic hallucinations, the remaining **2.8% CFR** confirms that LLMs are currently unsuitable for autonomous network control. Future work will integrate **Tier 2 (Emulation)** and **Tier 3 (Simulation)** validation to automate the detection of semantic failures, moving from a probabilistic model to a **Safe-by-Construction** IBN framework.

---

**Keywords**: Intent-Based Networking (IBN), Large Language Models (LLMs), RAG, Hallucination Mitigation, Network Safety, Batfish.
