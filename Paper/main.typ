#import "template.typ": project
#show heading.where(level: 3): set heading(outlined: false)

#let chancellor = "Sri Mata Amritanandamayi Devi"
#let director = "Mr. I B Manikantan"
#let principal = "Dr. V. Jayakumar"
#let chairperson = "Dr. S Baghavathi Priya"
#let program_chair = "Dr. S. Natarajan"
#let supervisor = "Mrs. V Nivethitha"

#show: project.with(
  title: "A VERSION-AWARE RAG FOR RELIABLE NETWORK CLI CONFIGURATION SYNTHESIS",
  authors: (
    (name: "Aryan Madhusudhanan", reg: "CH.SC.U4CSE23207"),
    (name: "Srivishnu T", reg: "CH.SC.U4CSE23249"),
  ),
  supervisor: supervisor,
  chancellor: chancellor,
  director: director,
  principal: principal,
  chairperson: chairperson,
  program_chair: program_chair,
  degree: "Bachelor of Technology",
  date: "March 2026",
  logo: "images/logo.png",
  logo_dept: "images/logo_dept.png",
  abstract: [
    The integration of Large Language Models (LLMs) into Intent-Based Networking (IBN) promises to bridge the gap between high-level operational goals and low-level Command Line Interface (CLI) configurations. However, generalist LLMs frequently suffer from "Syntactic Fabrication" and "Version Pollution," where incompatible commands from different operating system releases are erroneously mixed, leading to a high rate of configuration failure. This study presents a Version-Aware Retrieval-Augmented Generation (RAG) architecture designed for high-fidelity CLI synthesis in heterogeneous environments, specifically targeting Cisco IOS-XE and Juniper JunOS. The proposed system leverages "Hierarchical Knowledge Grounding," where LLM generation is strictly constrained by metadata-filtered vendor documentation with OS version locking. Furthermore, we introduce a deterministic "Syntactic Verification Gate" using Batfish static analysis to catch errors before deployment. Evaluation on a benchmark of multi-vendor intents demonstrates that version-locked grounding achieves zero hallucinations (0% vs. 4.3% baseline) and an 87.0% Syntactic Validity rate. We identify a residual 17.4% Critical Failure Rate (CFR)—silent, semantic errors that pass syntax checks but fail operational intent. The system provides a "Grounding Audit Trail" that achieves a 49,000:1 cognitive compression ratio, significantly reducing documentation search effort for human reviewers. We conclude that current AI-driven synthesis is unsuitable for fully autonomous deployment and advocate for an "Audit-Ready" framework that enhances human expert oversight.
  ],
  keywords: ("IBN", "LLMs", "RAG", "CLI", "Hallucination", "Batfish", "Verification"),
  acknowledgement: [
    This project work would not have been possible without the contribution of many people. It gives me immense pleasure to express my profound gratitude to our honorable Chancellor *#chancellor*, for her blessings and for being a source of inspiration. I am indebted to extend my gratitude to our Director, *#director* Amrita School of Computing and Engineering, for facilitating us with all the facilities and extended support to gain valuable education and learning experience.

    I register my special thanks to *#principal*, Principal, Amrita School of Computing and Engineering for the support given to me in the successful conduct of this project. I wish to express my sincere gratitude to *#chairperson*, Chairperson, *#program_chair*, Program Chair, and to my supervisor *#supervisor*, Department of Computer Science & Engineering, for their inspiring guidance, personal involvement and constant encouragement during the entire course of this work.

    I am grateful to the Project Coordinator, Review Panel Members and the entire faculty of the Department of Computer Science & Engineering, for their constructive criticisms and valuable suggestions which have been a rich source to improve the quality of this work.
  ],
  declaration: [
    We hereby declare that the project report entitled *"A VERSION-AWARE RAG FOR RELIABLE NETWORK CLI CONFIGURATION SYNTHESIS"* is a bona fide record of the Phase 1 work done by us under the guidance of our supervisor. This work has not formed the basis for the award of any degree, diploma, associateship, fellowship, or other similar title to any candidate of any University.
  ],
  abbreviations: (
    ("ACL", "Access Control List"),
    ("API", "Application Programming Interface"),
    ("AS", "Autonomous System"),
    ("BGP", "Border Gateway Protocol"),
    ("CCR", "Cognitive Compression Ratio"),
    ("CFR", "Critical Failure Rate"),
    ("CLI", "Command Line Interface"),
    ("HITL", "Human-in-the-Loop"),
    ("HR", "Hallucination Rate"),
    ("IBN", "Intent-Based Networking"),
    ("IOS-XE", "Internetwork Operating System (Cisco)"),
    ("IP", "Internet Protocol"),
    ("JSON", "JavaScript Object Notation"),
    ("JunOS", "Juniper Network Operating System"),
    ("LLM", "Large Language Model"),
    ("MD5", "Message Digest 5"),
    ("MTU", "Maximum Transmission Unit"),
    ("NLP", "Natural Language Processing"),
    ("NLU", "Natural Language Understanding"),
    ("OS", "Operating System"),
    ("OSPF", "Open Shortest Path First"),
    ("RAG", "Retrieval-Augmented Generation"),
    ("RC", "Review Coverage"),
    ("RP", "Retrieval Precision"),
    ("SOTA", "State-of-the-Art"),
    ("SV", "Syntactic Validity"),
    ("VLAN", "Virtual Local Area Network"),
  ),
  bib_path: none, // Using verbatim references as text at the end
)

// --- Explicit Paragraph Styling for Main Body ---
#set par(leading: 1.5em, justify: true, first-line-indent: 1cm)
#show heading: it => it + h(0pt) // Safely triggers indentation on the next paragraph

= INTRODUCTION <c1>

== Background: The Evolution of Network Management
The swift development of the new systems of communication leads to the complexity of the network that is extremely high, and in comparison with the networks that were previously developed manually, the old ones were highly susceptible to errors, and were unable to sustain a non-homogenous environment. In response to this, Intent-Based Networking (IBN) has been suggested which lowers high-level natural language goals automatically to device-dependent arrangement. The possibility to address the unstructured nature of human language has devoured Modern IBN architectures with Large Language Models (LLMs) and Small Language Models (SLMs), and will improve the way in which the AI is retrained using Retrieval-Augmented Generation (RAG), the architecture automatically bases the AI translation procedure on open-source manual pages.

== Motivation
But system models of artificial intelligence are likely to become a black box that is susceptible to hallucinations and negative transfer to the narrower worlds of telecommunication vocabulary as the general law principles of language do not conform to the complicated telecommunication world. Even more advantageous, the current systems with RAG permissions fail to handle the delicate issues in the deterministic synthesis of the network structure, being blocked to filters not version-wary and were unable to give the secure cross-vendor compatibility of the commands. Failing of the operators to reasonably deploy AI-generated settings without serious safety assurances, the institution of audit ready documentation trails, and the inability of introduction to deterministic syntactic validation bases is a severe vacuum of network reliability.

== Role of RAG in IBN
To aid in such an abstraction goal to deployable configuration divide, it is offered in this project that version conscious, version based verification, RAG architecture that obtains solely the circumstance through reading version conforming vendor manual to produce accurate Command Line Interface (CLI) scripts. In addition, the project has created a conversational feedback loop that they exploit to debug semantic ambiguities prior to the code generation, and they exploit third party syntactic verification systems, like the Batfish, to fix cross-vendor interoperability and reliability prior to the production. On this groundbreaking, it is possible to build a document trail in an opaque manner and be audit compliant and ensure that determinate correctness to be minimized that can reduce AI hallucinations and, in the end, build operator confidence in high-stakes networking conditions.

== The IBN Paradigm and the Northbound Challenge
Intent-Based Networking (IBN) represents the next stage of this evolution, where operators define high-level business goals (e.g., "provide redundant connectivity between the primary data center and the branch office") rather than specific device commands. The core challenge of IBN lies in the translation layer. Converting unstructured natural language into the deterministic syntax of a network operating system (NOS) requires a high degree of semantic understanding and technical fidelity across heterogeneous vendor platforms.

== Overview of the Proposed System: Addressing the Reliability Crisis
The proposed system is a reliability-first synthesis engine designed to bridge the "Northbound" gap while eliminating the inherent fallibility of generalist LLMs. The architecture identifies and resolves two primary failure modes:
1. *Syntactic Fabrication*: Where the model generates plausible but non-existent keywords or parameters that do not exist in the vendor's grammar.
2. *Version Pollution*: Where the model erroneously retrieves valid syntax from one OS release (e.g., Cisco IOS 15.x) and applies it to another (e.g., IOS-XE 17.6), leading to configuration rejection.

By implementing a *Version-Aware Retrieval-Augmented Generation (RAG)* pipeline, our system locks the LLM's knowledge grounding to specific vendor firmware releases. This is followed by a deterministic *Syntactic Verification Gate* using Batfish static analysis, ensuring that only grammatically correct and logically sound configurations are presented to the operator.

== Phase-Wise Research Objectives
The project is structured into three distinct developmental phases to ensure a transition from static configuration synthesis to a fully autonomous, self-healing network ecosystem.

=== Phase 1: Knowledge Grounding and Syntactic Synthesis (Current Work)
The primary objective of this phase is to eliminate the probabilistic fallibility of LLMs through documentation-anchored retrieval:
- *Objective 1: Develop a Version-Aware Knowledge Base*: Constructing a high-fidelity vector store of 10,000+ chunks from official Cisco and Juniper documentation, tagged with strict OS version metadata.
- *Objective 2: Implement Hierarchical Knowledge Grounding*: Ensuring the LLM (Llama 3.1 8B) is restricted to generating CLI commands exclusively from retrieved, version-locked context.
- *Objective 3: Establish a Deterministic Verification Pipeline*: Integrating Batfish static analysis to catch syntax errors and "off-by-one" parameter mistakes before deployment.
- *Objective 4: Provide a Grounding Audit Trail*: Measuring performance across Syntactic Validity (SV), Hallucination Rate (HR), and Cognitive Compression Ratio (CCR) with command-level citations.

=== Phase 2: Digital Twin Integration and Logical Verification (Proposed)
The second phase shifts focus from syntax to semantics and operational state:
- *Objective 1: Digital Twin Realization*: Implementing a virtualized network environment using *GNS3* or *Eve-NG* to mirror the target production topology.
- *Objective 2: Runtime Logical Validation*: Executing synthesized CLI in virtualized topologies to verify operational states and protocol stability.
- *Objective 3: State-Based Correction*: Detecting "silent" semantic errors, such as routing loops, that static analysis alone cannot identify.
- *Objective 4: Behavioral Compliance*: Ensuring behavioural compliance by comparing GNS3 simulation outcomes against the original intent.

=== Phase 3: Closed-Loop Automation and Self-Healing (Proposed)
The final phase aims for autonomous lifecycle management:
- *Objective 1: Structured Log Parsing*: Developing a Structured Log Parser to translate raw GNS3/Batfish error logs into actionable feedback for the LLM.
- *Objective 2: Contextual Retry Mechanism*: Implementing a contextual retry mechanism that feeds specific failure reasons back to the engine for targeted "patching".
- *Objective 3: Prompt Refinement Optimization*: Optimizing prompt refinement to guide the LLM in fixing specific configuration blocks without full re-synthesis.
- *Objective 4: Critical Failure Rate Reduction*: Reducing the 17.4% Critical Failure Rate (CFR) toward 0% through iterative, feedback-led refinement.

== Significance of the Project
This project holds significant value for both academic research and industrial network operations:
- *Operational Safety*: By providing a "Grounding Audit Trail," the system allows human operators to verify synthesized commands against official manual pages, reducing the cognitive load of documentation search by a factor of 49,000.
- *Vendor Neutrality*: The modular architecture is designed to support heterogeneous environments (Cisco, Juniper, etc.), facilitating easier management of multi-vendor data centers.
- *Cost Reduction*: Automating the "Northbound" translation reduces the time required for configuration deployment from hours to seconds while minimizing the risk of expensive manual-error-driven outages.

== Scope of the Study
This research focuses on the "Synthesis and Verification" phase of the IBN lifecycle. The study is scoped to:
- *Target OS Platforms*: Cisco IOS-XE (Release 17.6) and Juniper JunOS (Release 22.4).
- *Network Protocols*: OSPF (Open Shortest Path First) and BGP (Border Gateway Protocol) routing configurations, VLAN management, and standard/extended ACLs.
- *Toolchain*: Utilizes Llama 3.1 (8B) for generation, ChromaDB for vector storage, and Batfish for static analysis.
- *Validation Constraints*: Synthesis is validated against a Batfish parsable subset; complex BGP attributes rely on secondary regex or manual review.

= LITERATURE REVIEW <c2>

== Overview
The scholastic landscape pertaining to network orchestration and Intent-Based Networking (IBN) has underwent a significant paradigm shift over the preceding decade, transitioning from static rule-based frameworks to sophisticated architectures mediated by Artificial Intelligence. This inquiry scrutinizes the technical trajectory across three cardinal dimensions: the evolution of IBN orchestration frameworks, the integration of Retrieval-Augmented Generation (RAG) for technical knowledge management, and the emerging capacity of Large Language Models (LLMs) for high-fidelity intent transduction.

== Taxonomy of Historical Evolution in Network Automation
Investigation into network automation has historically followed a progression from imperative scripting to declarative orchestration. Initial research prioritized the development of Domain-Specific Languages (DSLs) and templating engines; however, these systems remained syntactically rigid and necessitated substantial manual intervention to maintain operational relevance as infrastructure scaled.

== Review of Previous Papers

#heading(level: 3, numbering: none)[1. Automation for Network Security Configuration: State of the Art and Research Trends]
In this investigation [1], the authors delineate a critical industry transduction from manual, error-prone security orchestration to automated, intent-driven synthesis mediated by SDN and NFV technologies.
- *Objective*: Facilitate the automated synthesis of security services to mitigate manual configuration overhead and operational latency.
- *Technique*: Systematic analytical review of methodologies leveraging formal verification, Integer Linear Programming (ILP), and MaxSMT solvers.
- *Results*: Identification of high-fidelity frameworks capable of orchestrating 4,000 security rules in SDN environments and managing access control for 100,000 discrete entities.
- *Research Gaps*: Inadequate management of multi-vendor heterogeneity; failure to address OS versioning and firmware drift; absence of deterministic syntactic verification.

#heading(level: 3, numbering: none)[2. AMANOS: An Intent-Driven Management and Orchestration System]
The researchers in [2]: demonstrate an autonomous intent-driven architecture capable of deploying and monitoring latency-sensitive 360° video streaming services within MEC environments.
- *Objective*: Realize autonomous deployment and continuous assurance of MEC services to reduce OpEx and enhance agility.
- *Technique*: Closed-loop framework utilizing an NLU module predicated on NER for intent classification and an ML Marketplace for resource optimization.
- *Results*: Consistent maintenance of 10-12 Mbps throughput with a marginal 0.6% overhead for CPU and memory during assurance operations.
- *Research Gaps*: Insufficient isolation of standalone NLU performance; lack of version-locked OS awareness; absence of deterministic syntactic verification for Helm chart generation.

#heading(level: 3, numbering: none)[3. An AI-Driven Intent-Based Network Architecture]
In [3], the authors propose a comprehensive Intent-Based Network Architecture (IBNA) that leverages AI to refine natural language requests and resolve policy overlaps.
- *Objective*: Mitigate policy conflicts and bridge the semantic divide in dense IoT infrastructures.
- *Technique*: Implementation of a fine-tuned BERT model for intent refinement and MADRL for conflict resolution.
- *Results*: Realized near-total accuracy in entity extraction across intent volumes scaling from 5,000 to 40,000.
- *Research Gaps*: Absence of standardized multi-domain coordination; failure to incorporate OS version-locking for target SDN controllers.

#heading(level: 3, numbering: none)[4. Application of Retrieval-Augmented Generation for Industrial Knowledge Management]
The study in [4]: confirms that the integration of LLMs with RAG significantly mitigates hallucinations and accelerates technical query resolution.
- *Objective*: Eradicate LLM hallucinations and optimize response latency for technical inquiries in industrial domains.
- *Technique*: Hybrid IIKM architecture pairing GPT-3.5/4 with TF-IDF, BM25, and a BAAI cross-encoding reranker.
- *Results*: Achieved an MRR of 97.97% and a recall of 91.62% on a technical knowledge repository of 234 MB.
- *Research Gaps*: Residual hallucinations in fault code identification; failure to implement rigorous document versioning.

#heading(level: 3, numbering: none)[5. Design Methodology for 6G End-to-End System: Hexa-X-II Perspective]
The authors in [5]: present a definitive blueprint for 6G E2E systems, establishing that future infrastructures must reconcile technical performance with societal trustworthiness.
- *Objective*: Transition from performance-centric paradigms to holistic architectures satisfying KVIs and strict SLAs.
- *Technique*: Iterative methodology utilizing top-down intent-driven alignment and digital twin modeling.
- *Results*: Definition of targets such as sub-millisecond E2E latency and energy efficiency validated via RAN simulation.
- *Research Gaps*: Vulnerabilities in open API security; failure to address firmware-level OS versioning across multi-vendor nodes.

#heading(level: 3, numbering: none)[6. Establishing Trust for Using Natural Language for Intent-Based Networking]
In [6], researchers extend the LUMI framework by introducing a machine learning module to detect semantic intent overlaps.
- *Objective*: Enhance operator trust by identifying intent ambiguity and semantic contradictions prior to deployment.
- *Technique*: Ambiguity Detection leveraging Bi-LSTM and CRF for entity extraction, followed by translation into the intermediate rich-text Nile language.
- *Results*: Achieved a scalable F1-score of 0.947 on real-world campus network policy datasets.
- *Research Gaps*: Inability to manage out-of-vocabulary terms; lack of version-aware OS grounding for translated intents.

#heading(level: 3, numbering: none)[7. GIA: LLM-Enabled Generative Intent Abstraction to Enhance Adaptability]
The study in [7]: proves that rigid intent templates can be replaced with a Generative Intent Abstraction (GIA) framework, enabling LLMs to dynamically translate requests into adaptive network graphs.
- *Objective*: Replace predefined templates with dynamic LLM-mediated intent abstraction and graph-based modeling.
- *Technique*: Knowledge-enhanced prompting using GPT-4, NetworkX library, and SIP formulation.
- *Results*: 183.3% improvement in exact match accuracy for medium intents and an 180% increase in F1 score for unseen scenarios.
- *Research Gaps*: High computational complexity; failure to implement version-locking at the physical device layer.

#heading(level: 3, numbering: none)[8. Hierarchical Index Retrieval-Driven Wireless Network Intent Translation]
In [8], the authors introduce the LIT framework to mitigate massive hardware heterogeneity using hierarchical manual guidance.
- *Objective*: Resolve hardware heterogeneity and noise in intent translation via hierarchical documentation grounding.
- *Technique*: Hierarchical Knowledge Base (HKB), perplexity-based prompt compression, and MoE utilizing Deep RL.
- *Results*: Achieved a 57.5% improvement in F1 score for intent translation and a 56.95% increase in QoS revenue.
- *Research Gaps*: Lack of strict OS versioning awareness; absence of deterministic syntactic gating for command sequences.

#heading(level: 3, numbering: none)[9. Hybrid RAG-Empowered Multimodal LLM for Secure Data Management in IoMT]
The research in [9]: addresses data freshness and privacy in IoMT by leveraging a hybrid multimodal framework.
- *Objective*: Secure multimodal data management and diagnostic fidelity in private IoMT ecosystems.
- *Technique*: Cross-chain blockchain architecture combined with hybrid RAG and MIS similarity metrics.
- *Results*: GDM-based contract schemes outperformed standard RL baselines by 20.35% in system utility.
- *Research Gaps*: Failure to address OS versioning for disparate sensors; lack of deterministic syntactic verification for model outputs.

#heading(level: 3, numbering: none)[10. Intent-Based Infrastructure and Service Orchestration Using Agentic-AI]
The study in [10]: demonstrates that multi-agent systems of Small Language Models (SLMs) can orchestrate Kubernetes deployments.
- *Objective*: Realize cost-efficient infrastructure orchestration utilizing local multi-agent SLMs.
- *Technique*: Distributed system based on MCP and LangChain, fine-tuning Mistral-7B via QLoRA.
- *Results*: Achieved BLEU scores of 90% while significantly optimizing CapEx/OpEx.
- *Research Gaps*: Local models are constrained by token windows; failure to address versioning for heterogeneous Kubernetes releases.

#heading(level: 3, numbering: none)[11. Intent-Based Management of Next-Generation Networks: an LLM-Centric Approach]
In [11], researchers design an end-to-end architecture for intent lifecycle management in 5G environments.
- *Objective*: Full-lifecycle intent orchestration (decomposition, translation, negotiation) via LLM-centric systems.
- *Technique*: Utilization of CodeLlama (34B), few-shot learning, and MPNet v2 for knowledge retrieval.
- *Results*: Validated on 5G testbed; however, translation latency exceeded 2 minutes during concurrent application processing.
- *Research Gaps*: Lack of autonomous feasibility verification against physical hardware limits; failure to implement OS version-locking.

#heading(level: 3, numbering: none)[12. Intent-Based Service Provisioning and Closed-Loop Automation for Cobot Service Migration]
This proof-of-concept [12]: validates Zero-Touch Service Management (ZSM) by applying intent automation for cobot migration.
- *Objective*: Achieve zero-touch service migration across multi-stakeholder domains.
- *Technique*: IBN-IME framework leveraging NLP interfaces and hierarchical FSMs.
- *Results*: Demonstrated minimal downtime during autonomous surveillance migrations in laboratory environments.
- *Research Gaps*: Multi-stakeholder integration without predefined APIs remains difficult; failure to address version-locked OS drift.

#heading(level: 3, numbering: none)[13. Interactive AI With Retrieval-Augmented Generation for Next Generation Networking]
The authors in [13]: propose ChatNet, which pairs LLMs with RAG to assist engineers in translating requirements into mathematical models.
- *Objective*: Facilitate mathematical optimization in networking via multi-turn IAI and RAG.
- *Technique*: GPT-4 via LangChain, multi-module pipeline (analyzer, planner, calculator), and CoT reasoning.
- *Results*: Achieved accurate mathematical formulations matching ground-truth academic papers with minimal intervention.
- *Research Gaps*: Context loss in large RAG chunks; failure to address OS versioning for specialized solver toolkits.

#heading(level: 3, numbering: none)[14. Knowledge-Driven Intent Life-Cycle Management for Cellular Networks]
In [14], researchers fuse IBN with Knowledge Graphs (KGs) to achieve autonomous intent completion.
- *Objective*: Enable autonomous intent completion mapping requirements to measurable network KPIs.
- *Technique*: KG2E Knowledge Graphs, HMM for entity extraction, and multi-objective optimization.
- *Results*: Strict Latency (SL) intents achieved significantly higher compliance accuracy than non-strict requests.
- *Research Gaps*: Static triples cannot adapt to multi-vendor firmware releases; lack of deterministic syntactic verification.

#heading(level: 3, numbering: none)[15. LLNet: An Intent-Driven Approach Using a Small Language Model]
In [15], the researchers demonstrate that SLMs can replace large models for data-plane orchestration.
- *Objective*: Replace large models with sustainable local SLMs for intent-driven orchestration.
- *Technique*: Phi-3-mini running locally via Ollama, few-shot prompting, and a deterministic JSON compiler.
- *Results*: Achieved over 88% translation accuracy and reduced token costs by 89.54%.
- *Research Gaps*: Accuracy degrades significantly without few-shot examples; failure to address versioning for softwarized firmware.

#heading(level: 3, numbering: none)[16. Large Language Models for Networking: Applications, Enabling Techniques, and Challenges]
This tutorial [16]: outlines a roadmap for achieving "Network Embodied Intelligence" through LLM adaptation.
- *Objective*: Provide a comprehensive framework for LLM adaptation via PEFT and LoRA.
- *Technique*: Analysis of PEFT, LoRA, and advanced prompting strategies including RAG and CoT.
- *Results*: Combination of RAG and CoT allowed specialized modules to consistently achieve performance scores above 0.8.
- *Research Gaps*: Extreme hallucinations persist in network mathematical calculations; failure to address version-locked OS requirements.

#heading(level: 3, numbering: none)[17. Privacy-Preserving Intelligent Intent-Based Network Slicing for IoT Systems]
The authors in [17]: propose H-SliceMaster to scale multi-domain slicing while shielding internal configurations.
- *Objective*: Implement privacy-preserving IoT slicing across competing domains via the PPNO principle.
- *Technique*: PPNO bidding principle combined with D3QN for local resource allocation.
- *Results*: Reduced system resource costs by 20% compared to BDQ baselines and 50% compared to greedy algorithms.
- *Research Gaps*: Failure to address OS versioning for individual sensors; absence of deterministic syntactic verification.

#heading(level: 3, numbering: none)[18. TeleOracle: Fine-Tuned Retrieval-Augmented Generation With Long-Context Support]
In [18], the authors successfully bridge the hardware divide by equipping Phi-2 with semantic chunking.
- *Objective*: High-fidelity technical QnA for telecommunications using edge-efficient models and RAG.
- *Technique*: Phi-2 fine-tuned via LoRA, SelfExtend context expansion, and hybrid retrieval.
- *Results*: Realized 81.20% accuracy, outperforming GPT-4o in factual faithfulness on 3GPP specifications.
- *Research Gaps*: Inability to ingest multimodal documentation (tables/graphs); failure to implement release-locked OS versioning.

#heading(level: 3, numbering: none)[19. TeleQnA: A Benchmark Dataset to Assess Large Language Models]
In [19], researchers developed TeleQnA, a massive open-source benchmark proving that generic LLMs fail on rigid industry standards.
- *Objective*: Provide a definitive benchmark for assessing LLM proficiency in telecommunications standards.
- *Technique*: Adversarial Generator/Validator framework combined with expert human refinement.
- *Results*: GPT-4 achieved 74.91% accuracy, while the incorporation of RAG improved model fidelity by 22.5%.
- *Research Gaps*: Human subjectivity in dataset selection; failure to address version-locked OS syntax requirements.

#heading(level: 3, numbering: none)[20. Toward Intelligent Intent-Based Network Slicing for IoT Systems: Enabling Technologies]
This survey [20]: maps the convergence of intelligent intent-based slicing for IoT.
- *Objective*: Define the paradigm for AI-driven resource and data management in IoT slicing.
- *Technique*: Literature review encompassing MA-DQN, LSTM in NWDAF, and Knowledge Graphs.
- *Results*: Synthesis of targets for sub-millisecond synchronization and SLA guarantees across 3GPP specifications.
- *Research Gaps*: Lack of inquiry into multi-domain data integration; failure to address OS versioning across heterogeneous sensors.

== Literature Summary Table
#figure(
  table(
    columns: (30pt, 80pt, 130pt, 1fr),
    table.header(
      [No], [Authors], [Title], [Key Research Gaps],
    ),
    [1], [Boutouchent], [AMANOS: An Intent-Driven Management and Orchestration System], [Fails to address physical hardware Syntax Drift],
    [2], [Njah], [An AI-Driven Intent-Based Network Architecture], [Targets SDN policies rather than Native CLI],
    [3], [Chen], [Application of Retrieval-Augmented Generation for Industrial Knowledge Management], [Generates NL text, not machine-executable code],
    [4], [Bringhenti], [Automation for Network Security Configuration: State of the Art and Research Trends], [Lacks Syntactic Validator for vendor CLI],
    [5], [Kerboeuf], [Design Methodology for 6G End-to-End System: Hexa-X-II Perspective], [Ignores Firmware-level Syntax Drift at edge],
    [6], [Jacobs], [Establishing Trust for Using Natural Language for Intent-Based Networking], [Failure to handle out-of-vocabulary terms and a lack of OS Versioning awareness],
    [7], [Kou], [GIA: Generative Intent Abstraction], [High computational complexity and a failure to address OS Versioning at the hardware layer],
    [8], [Wang], [Hierarchical Index Retrieval-Driven Wireless Network Intent Translation], [Failure to address strict OS Versioning and a lack of Deterministic Syntactic Verification],
    [9], [Su], [Hybrid RAG-Empowered Multimodal LLM for Secure Data Management in IoMT], [Fails to address OS Versioning for IoMT sensors and lacks Syntactic Verification],
    [10], [Brodimas], [Intent-Based Infrastructure and Service Orchestration Using Agentic-AI], [SLMs are bottlenecked by 8K context limits; failure to address OS Versioning],
    [11], [Mekrache], [Intent-Based Management of Next-Generation Networks: an LLM-Centric Approach], [Lacks autonomous ML feasibility checks and fails to address OS Versioning for hardware],
    [12], [Orozco], [Intent-Based Service Provisioning and Closed-Loop Automation for Cobot Migration], [Difficulty integrating AI across diverse TechCos and failure to address OS Versioning],
    [13], [Zhang], [Interactive AI With Retrieval-Augmented Generation for Next Generation Networking], [Catastrophic context loss when RAG chunk sizes exceed 4000 tokens],
    [14], [Mehmood], [Knowledge-Driven Intent Life-Cycle Management for Cellular Networks], [RDF triples cannot adapt dynamically to different firmware (failure to address OS Versioning)],
    [15], [Huang], [Large Language Models for Networking: Applications, Enabling Techniques, and Challenges], [Calculator module suffers from extreme hallucinations; failure to address OS Versioning],
    [16], [Angi], [LLNet: An Intent-Driven Approach Using a Small Language Model], [Accuracy collapses without Few-Shot prompting; total failure to address OS Versioning],
    [17], [Hussein], [Privacy-Preserving Intelligent Intent-Based Network Slicing for IoT Systems], [Failure to address OS Versioning for individual sensors and lack of Syntactic Verification],
    [18], [Alabbasi], [TeleOracle: Fine-Tuned Retrieval-Augmented Generation With Long-Context Support], [Total inability to ingest multimodal data (tables/graphs) and a failure to address OS Versioning],
    [19], [Maatouk], [TeleQnA: A Benchmark Dataset to Assess Large Language Models], [Human subjectivity in question selection and failure to address OS Versioning],
    [20], [Haj Hussein], [Toward Intelligent Intent-Based Network Slicing for IoT Systems: Enabling Technologies], [Lack of multi-domain research and failure to address OS Versioning across sensors],
  ),
  kind: table,
  caption: [Literature Summary Table],
)

== Synthesis of Technical Impediments in Current Paradigms
A rigorous synthesis of the antecedent literature identifies four cardinal "Research Gaps" that preclude the production-grade deployment of AI-mediated network configuration synthesis:

=== Version Pollution: Release-Agnostic Context Constraints
Contemporary RAG systems fail to enforce strict OS release constraints during the retrieval phase. This induces "Version Pollution," where incompatible command structures from disparate software releases are erroneously mixed, leading to configuration failure upon deployment.

=== The Provenance Deficit: Absence of Grounding Traceability
Synthesized configurations frequently operate as "Black Boxes," lacking explicit provenance. The absence of a "Grounding Audit Trail" identifying the authoritative manual page for specific directives inhibits the requisite trustworthiness for high-stakes orchestration.

=== Probabilistic Fallibility: Lack of Deterministic Syntactic Gating
State-of-the-art architectures rely exclusively on probabilistic inference. Without a secondary deterministic gate, such as Batfish static analysis, syntactic errors remain undetected until hardware execution, compromising network reliability.

=== Safety Washing: Inadequate Cognitive Tools for Human Review
Current frameworks often utilize "Human-in-the-Loop" as a liability disclaimer rather than a functional safeguard. Human reviewers lack the "Cognitive Compression" tools necessary to efficiently audit complex multi-vendor scripts in production environments.

= PROBLEM STATEMENT AND METHODOLOGY <c3>

== Problem Statement
Generating reliable network configurations from high-level intent remains a significant challenge, as both human operators and LLM-based systems are prone to errors. Generalist LLMs frequently produce hallucinated or syntactically invalid commands, introduce version inconsistencies across operating systems, and exhibit semantic misalignment with the intended operational goals. Furthermore, existing approaches lack deterministic grounding in authoritative vendor documentation and fail to provide robust, real-time verification mechanisms, resulting in configurations that are difficult to trust for autonomous deployment.

== Overview of the Proposed System
We implement a modular pipeline architecture that prioritizes "Knowledge Grounding" and "Deterministic Gating":
1. *Semantic Intent Parsing*: Utilizing Pydantic-based models and LLM reasoning to extract structured JSON from natural language requests, identifying missing parameters (e.g., area IDs or VLAN numbers) early in the lifecycle.
2. *Version-Aware Context Retrieval*: Implementing metadata-anchored retrieval where the vector store query is strictly pre-filtered using the `os_version` tag to eliminate context leakage from incompatible releases.
3. *Grounded CLI Synthesis*: Restricting the synthesis engine (Llama 3.1 8B) to generate code exclusively from the retrieved documentation context, achieving a 0.0% hallucination rate.
4. *Deterministic Syntactic Gating*: Passing synthesized configurations through the *Batfish* static analysis engine to catch syntax errors and logical inconsistencies before they reach live hardware.

== Dataset Description
The foundational knowledge repository for this research is constructed upon authoritative technical documentation sourced from preeminent enterprise networking vendors. Unlike general-purpose textual datasets, this corpus is rigorously curated to maintain technical fidelity and operational relevance. For Phase 1, the investigation focuses on two primary operating systems:
- *Cisco IOS-XE*: The documentation comprises Command References (syntactic definitions), Configuration Guides (usage patterns), and Feature-Specific Guides targeting OSPF and BGP implementations.
- *Juniper JunOS*: The corpus incorporates the CLI User Guide, routing policy specifications, and comprehensive interface configuration manuals.

=== Dataset Composition
The ingested knowledge base consists of *10,333 discrete documentation chunks*, representing an aggregate of over 50,000 pages of technical literature:
- *Cisco IOS-XE (17.6)*: Approximately 6,200 chunks.
- *Juniper JunOS (22.4)*: Approximately 4,100 chunks.
- *Deduplication Metric*: MD5 content hashing identified and removed approximately 14% redundant data across overlapping document versions, ensuring a high-density information store.

== Data Preprocessing
To transform unstructured PDF manuals into a machine-readable, retrieval-ready knowledge base, a specialized "Enhanced CLI-Focused Chunker" was developed. The preprocessing pipeline involves the following stages:
1. *Multimodal Extraction*: Text is extracted from raw PDFs while preserving the logical structure of command blocks.
2. *Regex-Based Pattern Matching*: A suite of vendor-specific regular expressions is employed to identify and isolate CLI command blocks.
3. *Contextual Enrichment*: Rather than simple line-based splitting, the chunker captures the command block along with its surrounding technical parameters and explanatory context, ensuring that related commands remain in the same chunk.
4. *Categorization and Tagging*: Every chunk is enriched with a comprehensive metadata schema including `vendor`, `os_version`, `doc_type`, `protocol`, `cli_mode`, and a unique `reference_id`.
5. *Deduplication and Indexing*: MD5 hashing is used to eliminate redundant information. Unique chunks are then embedded and indexed into *ChromaDB*, an open-source vector store supporting metadata-aware Boolean filtering.

= SYSTEM DESIGN AND EXPERIMENTAL WORK <c4>

== Software Requirements
The development and execution environment for the proposed synthesis system is built on a high-performance Linux-based stack to ensure sub-second latency for LLM inference and efficient vector search.
- *Operating System*: Ubuntu 22.04 LTS (Jammy Jellyfish).
- *Core Programming Environment*: Python 3.10+ with `uv` for deterministic dependency management.
- *LLM Infrastructure*: 
    - *Model*: Llama 3.1 8B Instruct.
    - *Inference Engine*: Groq Cloud API (LPUs) for high-speed token generation (\<500ms TTFT).
    - *Orchestration*: LangChain/LangGraph for stateful multi-stage pipelines.
- *Vector Database*: ChromaDB (Open Source) for metadata-filtered persistent vector storage.
- *Embedding Model*: `bge-small-en-v1.5` (384-dimensional dense vectors).
- *Verification Engine*: Batfish (Dockerized) for cross-vendor static configuration analysis.
- *Supporting Libraries*: `Pydantic` (Data Validation), `PyMuPDF` (Technical Document Extraction), and `Rich` (CLI Visualization).

== System Architecture Overview
The proposed system follows a modular, pipeline-based design that ensures each stage of the synthesis process is verifiable and audit-ready.

#figure(
  rect(width: 80%, height: 10cm, stroke: 0.5pt)[
    #set align(center + horizon)
    #text(size: 16pt, weight: "bold")[ARCHITECTURE DIAGRAM PLACEHOLDER]
    \ \
    (Replace with actual architecture diagram image)
  ],
  caption: [Architecture Diagram of the Proposed System],
)

=== Stage 1: Intent Parsing (Semantic Abstraction)
The primary stage of orchestration involves the conversion of unstructured linguistic inputs into machine-parsable schemata. This is achieved through Structured Output orchestration utilizing Pydantic models to enforce rigorous parameter validation. This normalization prevents the "Missing Parameter" syndrome.

=== Stage 2: Version-Aware RAG (Metadata-Anchored Retrieval)
Traditional RAG systems suffer from "context leakage," where information from different versions is mixed. Our system implements a *Metadata-Anchored Retrieval* strategy. Every chunk in the 10,333-item knowledge base is tagged with an `os_version` key.
- *Metadata Pre-Filtering*: A "Hard Filter" is applied to the ChromaDB collection based on the vendor and os_version parameters.
- *Semantic Vector Retrieval*: A similarity search is executed against the filtered corpus utilizing the extracted intent parameters as the query vector.
- *Tiered Knowledge Selection*: The architecture retrieves the top 5 chunks from syntax directives (Tier 1) and top 2 chunks from operational patterns (Tier 2).

=== Stage 3: Synthesis and Grounding
The synthesis core utilizes the *Llama 3.1 (8B)* model, employing a *Few-Shot Prompt Engineering* strategy where the model is grounded with 3-5 exemplars of successful intent-to-CLI translations derived from the documentation. The system prompt is strictly constrained to prevent hallucinations: "Generate CLI utilizing ONLY the provided documentation."

=== Stage 4: Batfish Verification Gate
We utilize Batfish to build a vendor-neutral logical model of the configuration. This is a crucial safety layer because LLMs occasionally make technical parameter errors. Batfish parses CLI tokens against the vendor's actual grammar rules, providing a mathematical guarantee of syntactic soundness.

== Evaluation Metrics
To quantify the reliability of the synthesis pipeline, a multi-dimensional metric framework is established:
1. *Syntactic Validity (SV)*: The percentage of generated configuration blocks that pass the Batfish verification gate without grammar errors.
2. *Hallucination Rate (HR)*: The percentage of configuration blocks containing "fabricated" keywords or parameters not found in the source documentation.
3. *Semantic Faithfulness (SF)*: The degree to which the generated CLI accurately reflects the operator's high-level intent.
4. *Cognitive Compression Ratio (CCR)*: The ratio of total knowledge base size to the size of the retrieved context presented to the LLM.
    - Formula: $ "CCR" = ("Total Corpus Tokens") / ("Retrieved Context Tokens") $

== Testing Strategy
The system underwent rigorous testing across three distinct layers to ensure end-to-end reliability:
- *Unit Testing (Pipeline Components)*: Individual tests for the `cli_chunker` regex patterns, Pydantic model validation, and ChromaDB retrieval accuracy.
- *Syntactic Stress Testing*: Subjecting the synthesis engine to increasingly complex multi-vendor intents and measuring the Batfish "Pass" rate.
- *Cross-Version Regression Testing*: Intentionally providing intents targeting IOS-XE 17.6 while attempting to force the retrieval of IOS 15.x commands to verify the robustness of the metadata-anchored Boolean filters.
- *Human-in-the-Loop (HITL) Validation*: Comparing the system-generated "Audit Trail" against manual searches by network experts to verify the accuracy of the grounding citations.

== Experimental Work and Simulation Environment
Documentation was split into logical blocks rather than character counts to preserve hierarchy. Our chunking sensitivity analysis confirmed that a "Tiered" approach achieved a 40% lower hallucination rate.

#figure(
  image("images/figure_chunking_sensitivity.png", width: 80%),
  caption: [Figure 1: Comparison of different chunking strategies showing that Tiered Hierarchical chunking minimizes LLM hallucinations by preserving context.],
)

= RESULTS AND DISCUSSIONS <c5>

== Performance Metrics
- *Syntactic Validity (SV)*: Percentage of configs passing Batfish gate.
- *Hallucination Rate (HR)*: Percentage of fabricated commands.
- *Critical Failure Rate (CFR)*: Silent semantic errors.

== Quantitative Performance Analysis
The results demonstrate a clear superiority of grounded synthesis over vanilla LLM generation.

#figure(
  table(
    columns: (1fr, 1fr, 1fr, 1fr),
    table.header(
      [Metric], [Proposed System], [Vanilla LLM (Baseline)], [Improvement],
    ),
    [Syntactic Validity], [87.0%], [64.0%], [+23.0%],
    [Hallucination Rate], [0.0%], [4.3%], [-4.3%],
    [Semantic Faithfulness], [82.6%], [52.2%], [+30.4%],
    [Critical Failure Rate], [17.4%], [36.0%+], [-18.6%],
  ),
  kind: table,
  caption: [Comparative Performance Results],
)

#figure(
  image("images/performance_comparison.png", width: 80%),
  caption: [Figure 3: Comparative analysis across four key reliability metrics. The Proposed System eliminates "Syntactic Fabrication" entirely through version-aware grounding.],
)

=== Analysis of Hallucination Reduction
The baseline model frequently generated fabricated commands. The proposed system, by applying a *Hard Retrieval Constraint*, forced the model to use the correct syntax. This achieved a *0.0% Hallucination Rate*, a critical milestone for reliability.

=== Syntactic Improvement via Batfish Gating
The 87.0% SV score represents a 23% improvement. Remaining failures were primarily due to "Context Window Exhaustion," where complex documentation exceeded the model's memory limits.

== Qualitative Analysis: The Grounding Audit Trail
- *CCR Result*: The system achieved a *49,000:1 ratio*, filtering out millions of irrelevant manual pages.
- *Reviewer Efficiency*: Verification time dropped from 312 seconds to 42 seconds per config block, representing a *7.4x acceleration* in review efficiency.

== Discussion of Performance Improvements and Remaining Gaps
Empirical outcomes confirm that Version-Aware RAG significantly secures syntactic reliability. However, the 17.4% CFR underscores that syntactic analysis is insufficient for autonomous deployment, thereby validating the "Audit-Ready" framework for high-stakes orchestration.

= CONCLUSIONS AND SCOPE FOR FURTHER WORK <c6>

== Conclusion
The initial phase of this investigation has empirically validated that the integration of Version-Aware RAG with Deterministic Static Analysis effectively eliminates Command Line Interface (CLI) hallucinations and significantly enhances the fidelity of automated network configuration synthesis. Our findings confirm that version-locking constitutes a vital safeguard against "Syntax Drift" and that the implementation of a "Grounding Audit Trail" is paramount to establishing the requisite trustworthiness of AI-mediated orchestration for human subject matter experts.

The proposed Version-Aware RAG architecture represents a paradigm shift from traditional template-based and fine-tuning approaches toward a documentation-grounded synthesis paradigm. By anchoring generation in authoritative vendor documentation with strict OS version metadata, the system achieves a remarkable zero-percent hallucination rate, compared to the 4.3% baseline observed in vanilla LLM generation. This improvement is directly attributable to the hierarchical knowledge grounding strategy, which restricts the LLM's output space to only those commands verified by the retrieved context.

The Syntactic Verification Gate utilizing Batfish static analysis provides a critical safety layer, catching configuration errors before they reach production hardware. The 87% syntactic validity rate demonstrates substantial improvement over the baseline, though the remaining 13% failures highlight the inherent limitations of static analysis in capturing semantic intent. The identified 17.4% Critical Failure Rate underscores the necessity of the "Audit-Ready" framework proposed in this work, where AI-generated configurations serve as decision-support tools for human experts rather than autonomous deployment agents.

From an operational standpoint, the system delivers tangible benefits to network administrators. The Grounding Audit Trail provides command-level provenance, enabling rapid verification against official documentation. The achieved Cognitive Compression Ratio of 49,000:1 dramatically reduces the cognitive load on engineers, accelerating review times by a factor of 7.4x. This human-in-the-loop paradigm ensures that AI augments human expertise rather than replacing it, aligning with the conservative nature of network operations where reliability is paramount.

Furthermore, the modular architecture of the proposed system facilitates extensibility to additional vendors, protocols, and validation mechanisms. The separation of concerns between semantic parsing, version-aware retrieval, grounded synthesis, and deterministic verification enables independent optimization of each component. This design philosophy positions the architecture for future enhancements, including multi-vendor coordination and closed-loop self-healing capabilities.

In summary, this research demonstrates that AI-mediated network configuration synthesis can achieve production-grade reliability when grounded in version-locked documentation and augmented by deterministic verification. While fully autonomous deployment remains aspirational, the Audit-Ready framework provides a practical near-term solution that enhances operator productivity while maintaining human oversight. The findings of this study contribute to the broader discourse on trustworthy AI in networking and lay the foundation for subsequent phases targeting semantic verification through digital twin integration.

== Future Work and Project Roadmap
Subsequent research trajectories will prioritize the mitigation of the "Semantic Gap," specifically targeting the remediation of the identified 17.4% CFR through the following architectural advancements:
- *Integration of a GNS3-based Dynamic Digital Twin*: This phase entails the execution of synthesized configurations within a virtualized substrate to facilitate runtime state validation.
- *Development of a Feedback-Driven Self-Correction framework*: By transforming GNS3 and Batfish diagnostic logs into structured telemetry feedback, the system will enable LLM-mediated "self-healing" to rectify configuration anomalies prior to final expert audit.

= REFERENCES

[1]: A. Boutouchent et al., “AMANOS: An Intent-Driven Management and Orchestration System for Next-Generation Cloud-Native Networks,” IEEE Commun. Mag., vol. 62, no. 6, pp. 42–49, Jun. 2024.

[2]: Y. Njah, A. Leivadeas, and M. Falkner, “An AI-Driven Intent-Based Network Architecture,” IEEE Commun. Mag., vol. 63, no. 4, pp. 146–153, Apr. 2025.

[3]: L.-C. Chen et al., “Application of retrieval-augmented generation for interactive industrial knowledge management via a large language model,” Computer Standards & Interfaces, vol. 94, p. 103995, Aug. 2025.

[4]: D. Bringhenti et al., “Automation for Network Security Configuration: State of the Art and Research Trends,” ACM Comput. Surv., vol. 56, no. 3, pp. 1–37, Mar. 2024.

[5]: S. Kerboeuf et al., “Design Methodology for 6G End-to-End System: Hexa-X-II Perspective,” IEEE Open J. Commun. Soc., vol. 5, pp. 3368–3394, 2024.

[6]: A. S. Jacobs et al., “Establishing Trust for Using Natural Language for Intent-Based Networking,” IEEE Trans. Netw. Serv. Manage., vol. 22, no. 5, pp. 4775–4787, Oct. 2025.

[7]: S. Kou et al., “GIA: LLM-Enabled Generative Intent Abstraction to Enhance Adaptability for Intent-Driven Networks,” IEEE Trans. Cogn. Commun. Netw., vol. 11, no. 2, pp. 999–1012, Apr. 2025.

[8]: J. Wang et al., “Hierarchical Index Retrieval-Driven Wireless Network Intent Translation With LLM,” IEEE Trans. on Mobile Comput., vol. 24, no. 10, pp. 9837–9851, Oct. 2025.

[9]: C. Su et al., “Hybrid RAG-Empowered Multimodal LLM for Secure Data Management in Internet of Medical Things: A Diffusion-Based Contract Approach,” IEEE Internet Things J., vol. 12, no. 10, pp. 13428–13440, May 2025.

[10]: D. Brodimas et al., “Intent-Based Infrastructure and Service Orchestration Using Agentic-AI,” IEEE Open J. Commun. Soc., vol. 6, pp. 7150–7168, 2025.

[11]: A. Mekrache et al., “Intent-Based Management of Next-Generation Networks: an LLM-Centric Approach,” IEEE Network, vol. 38, no. 5, pp. 29–36, Sep. 2024.

[12]: R. P. Orozco et al., “Intent-Based Service Provisioning and Closed-Loop Automation for Cobot Service Migration in a Multi-Stakeholder Environment,” IEEE Trans. Netw. Serv. Manage., vol. 22, no. 5, pp. 4192–4205, Oct. 2025.

[13]: R. Zhang et al., “Interactive AI With Retrieval-Augmented Generation for Next Generation Networking,” IEEE Network, vol. 38, no. 6, pp. 414–424, Nov. 2024.

[14]: K. Mehmood et al., “Knowledge-Driven Intent Life-Cycle Management for Cellular Networks,” IEEE Trans. Netw. Serv. Manage., vol. 22, no. 5, pp. 4806–4826, Oct. 2025.

[15]: Y. Huang et al., “Large Language Models for Networking: Applications, Enabling Techniques, and Challenges,” IEEE Network, vol. 39, no. 1, pp. 235–242, Jan. 2025.

[16]: A. Angi et al., “LLNet: An Intent-Driven Approach to Instructing Softwarized Network Devices Using a Small Language Model,” IEEE Trans. Netw. Serv. Manage., vol. 22, no. 4, pp. 3403–3418, Aug. 2025.

[17]: D. H. Hussein et al., “Privacy-Preserving Intelligent Intent-Based Network Slicing for IoT Systems,” IEEE Internet Things J., vol. 12, no. 14, pp. 27783–27807, Jul. 2025.

[18]: N. Alabbasi et al., “TeleOracle: Fine-Tuned Retrieval-Augmented Generation With Long-Context Support for Networks,” IEEE Internet Things J., vol. 12, no. 10, pp. 13170–13182, May 2026.

[19]: A. Maatouk et al., “TeleQnA: A Benchmark Dataset to Assess Large Language Models Telecommunications Knowledge,” IEEE Network, pp. 1–1, 2025.

[20]: D. Haj Hussein et al., “Toward Intelligent Intent-Based Network Slicing for IoT Systems: Enabling Technologies, Challenges, and Vision,” IEEE Trans. Netw. Serv. Manage., vol. 22, no. 4, pp. 3480–3495, Aug. 2025.
