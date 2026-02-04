# B.Tech Final Year Project: Hallucination-Mitigated Intent-Based Networking

## 5-Month Implementation Plan (Realistic Scope)

**Project Type**: B.Tech Final Year Project  
**Duration**: 5 months  
**Team Size**: 1-2 students  
**Complexity**: Proof-of-Concept (Not Full Research System)

---

## Executive Summary

This project implements a **minimal viable proof-of-concept** for hallucination-mitigated network configuration generation. Rather than the comprehensive 15-month research plan, we focus on demonstrating core concepts with simplified architecture that can be completed within a B.Tech timeline.

**Key Difference**: Demonstrate feasibility with 1-2 vendor platforms, not comprehensive multi-vendor support.

---

## 1. REALISTIC SCOPE FOR 5 MONTHS

### What You CAN Complete in 5 Months:

✅ **Single Vendor Focus** (Cisco IOS-XE OR Juniper JunOS - pick one)
✅ **Simplified Two-Tier Validation** (Batfish + Basic GNS3)
✅ **Core RAG Pipeline** (ChromaDB + Llama 3 via API)
✅ **10-20 Test Scenarios** (Not 500)
✅ **Basic Web UI** for supervisory gate
✅ **Thesis/Report** (40-60 pages)

### What You CANNOT Complete:

❌ Multi-vendor coordination (too complex)
❌ Full 3-tier validation (Containerlab adds unnecessary complexity)
❌ 500 test intents (too time-consuming)
❌ Fine-tuning (not needed with RAG-only approach)
❌ Industry partnerships (requires longer timeline)
❌ Multiple baselines (just compare vs vanilla LLM)

---

## 2. SIMPLIFIED ARCHITECTURE (5-Month Version)

```
┌─────────────────────────────────────────────────────────────┐
│                 SIMPLIFIED SYSTEM ARCHITECTURE              │
└─────────────────────────────────────────────────────────────┘

Intent (Natural Language)
         ↓
┌────────────────────────┐
│  Intent Parser         │ → Structured JSON
│  (Simple NER)          │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│  RAG Retrieval         │ → Top 5 command references
│  (ChromaDB)            │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│  LLM Generator         │ → CLI Configuration
│  (Llama 3 via API)     │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│  Validation Layer      │
│  (Batfish → GNS3)      │
└──────────┬─────────────┘
           ↓
    ┌──────────────┐
    │  Web UI      │ → Approve/Reject
    │  (Flask)     │
    └──────────────┘
```

---

## 3. 5-MONTH TIMELINE (Realistic)

### **Month 1: Foundation & Setup**
**Week 1-2: Environment Setup**
- Install Python, dependencies (LangChain, ChromaDB, Flask)
- Set up Llama 3 API access (Groq/Together AI - free tiers available)
- Install GNS3 locally or use GNS3 VM
- Install Batfish (Docker container)
- **Deliverable**: Working development environment

**Week 3-4: Data Collection**
- Download Cisco IOS-XE documentation (pick ONE version, e.g., 17.6)
- Extract 100-200 pages of command reference
- Create initial chunking strategy (simple paragraph-based)
- **Deliverable**: 500+ document chunks in ChromaDB

**Milestone M1**: RAG pipeline can retrieve command syntax

---

### **Month 2: Core RAG Pipeline**
**Week 1-2: Intent Parsing**
- Build simple intent parser (regex + keyword matching)
- Map 5-10 common intents:
  - "Configure interface GigabitEthernet0/1 with IP 192.168.1.1/24"
  - "Set up OSPF on router"
  - "Create ACL to block traffic from 10.0.0.0/8"
- **Deliverable**: Intent → structured JSON converter

**Week 3-4: Configuration Generation**
- Build prompt template for LLM
- Integrate RAG retrieval into generation
- Test with 20 simple intents
- **Deliverable**: Working config generator (CLI output)

**Milestone M2**: Can generate configs for basic scenarios

---

### **Month 3: Validation Layer**
**Week 1-2: Batfish Integration**
- Learn Batfish Python API
- Implement basic static checks:
  - Syntax validation
  - Undefined reference detection
  - Simple ACL analysis
- **Deliverable**: Batfish catches 80% of errors automatically

**Week 3-4: GNS3 Integration**
- Create simple 2-3 router topology in GNS3
- Implement config deployment via GNS3 API
- Build basic reachability test (ping between routers)
- **Deliverable**: Can validate configs in virtual environment

**Milestone M3**: Two-tier validation working (Batfish + GNS3)

---

### **Month 4: UI & Integration**
**Week 1-2: Web Interface**
- Build Flask web app
- Create simple pages:
  - Intent input form
  - Generated config display
  - Validation results view
  - Approve/Reject buttons
- **Deliverable**: Functional web UI

**Week 3-4: End-to-End Integration**
- Connect all components
- Test complete workflow: Intent → Config → Validation → Approval
- Create 10-15 test scenarios covering:
  - Interface configuration
  - Static routing
  - OSPF setup
  - Basic ACLs
- **Deliverable**: Working end-to-end system

**Milestone M4**: Complete system operational

---

### **Month 5: Evaluation & Documentation**
**Week 1-2: Evaluation**
- Compare your system vs. vanilla LLM (ChatGPT/Llama 3 without RAG)
- Metrics to measure:
  - Hallucination rate (commands not in docs)
  - Time to generate
  - Validation pass rate
  - 1-2 tables in thesis showing results
- **Deliverable**: Evaluation results

**Week 3-4: Documentation & Thesis**
- Write B.Tech thesis (40-60 pages):
  - Chapter 1: Introduction
  - Chapter 2: Literature Review (5-6 papers)
  - Chapter 3: System Design (your architecture)
  - Chapter 4: Implementation
  - Chapter 5: Testing & Results
  - Chapter 6: Conclusion
- Create presentation (PPT)
- Prepare demo video (2-3 minutes)
- **Deliverable**: Complete thesis + presentation

**Final Milestone**: Project submission ready

---

## 4. SIMPLIFIED COMPONENTS (B.Tech Level)

### **Vendor Choice: PICK ONE**
**Option A: Cisco IOS-XE** (Recommended)
- More documentation available
- Larger community
- Easier to find GNS3 images

**Option B: Juniper JunOS**
- Cleaner CLI structure
- Better YAML/JSON support
- Good for structured configs

**DO NOT try both** - doubles the complexity.

---

### **Simplified RAG**
**Instead of 3-tier chunking, use:**
```python
# Simple but effective for B.Tech
def chunk_document(text):
    """Split by paragraphs, keep command examples together"""
    chunks = []
    for paragraph in text.split('\n\n'):
        if 'command' in paragraph.lower() or paragraph.strip().startswith('ip'):
            chunks.append(paragraph)
    return chunks
```

**Vector DB: ChromaDB** (easiest to set up)
```python
import chromadb
client = chromadb.Client()
collection = client.create_collection("cisco_commands")
```

---

### **Simplified Validation**
**Tier 1: Batfish** (catches most errors without VMs)
```python
def validate_with_batfish(config):
    # Check for undefined references
    # Check ACL shadowing
    # 100ms response time
    pass
```

**Tier 2: GNS3** (simple topology)
```python
def validate_with_gns3(config):
    # Deploy to 2-router topology
    # Run ping test
    # Check routing table
    # 2-3 minutes response time
    pass
```

**Skip Containerlab** - adds complexity without clear benefit for B.Tech scope.

---

### **Simplified Intent Types (Pick 5)**

1. **Interface Configuration**
   - "Configure interface Gig0/1 with IP 192.168.1.1 mask 255.255.255.0"

2. **Static Routing**
   - "Add route to 10.0.0.0/8 via 192.168.1.254"

3. **OSPF Setup**
   - "Enable OSPF process 1 on all interfaces in area 0"

4. **Basic ACL**
   - "Block all traffic from 172.16.0.0/16"

5. **VLAN Configuration**
   - "Create VLAN 10 named SALES"

**That's it** - 5 intent types, fully working, is better than 20 half-working.

---

## 5. REALISTIC RESOURCES FOR B.TECH

### **Hardware** (What you likely have access to):
- **Laptop**: 16GB RAM, decent CPU (no GPU needed!)
- **OR**: University lab computers
- **NO**: A100 GPUs, server farms (not needed for proof-of-concept)

### **Software** (All Free/Open Source):
- Python 3.10+
- ChromaDB (pip install)
- LangChain (pip install)
- Flask (pip install)
- GNS3 (free download)
- Batfish (Docker, free)
- Llama 3 via Groq API (free tier: 1M tokens/day)

### **Data** (Publicly Available):
- Cisco documentation (free on cisco.com)
- 1 vendor, 1 OS version (100-200 pages)
- No need for 50K configs

### **Costs**: **₹0 - ₹2,000** (mostly API credits if free tier exceeded)

---

## 6. THESIS STRUCTURE (B.Tech Format)

### **Chapter 1: Introduction** (8-10 pages)
- Problem statement (hallucinations in LLM configs)
- Motivation (15-20% outages from config errors)
- Objectives (reduce hallucinations via RAG + validation)
- Scope (single vendor, proof-of-concept)

### **Chapter 2: Literature Review** (10-12 pages)
- 5-6 papers on:
  - RAG systems
  - Intent-based networking
  - Network configuration validation
  - LLM hallucinations
- Summary table comparing approaches

### **Chapter 3: System Design** (10-12 pages)
- Architecture diagram
- Component descriptions
- Data flow
- RAG pipeline design
- Validation tier design

### **Chapter 4: Implementation** (8-10 pages)
- Tech stack
- Code snippets (key algorithms)
- UI screenshots
- Setup instructions

### **Chapter 5: Testing & Results** (8-10 pages)
- Test scenarios (your 5 intent types)
- Comparison table: Your System vs. Vanilla LLM
- Metrics: Hallucination rate, accuracy, time
- Screenshots of working system

### **Chapter 6: Conclusion** (3-4 pages)
- Summary of achievements
- Limitations (be honest!)
- Future work (multi-vendor, more intents, etc.)

**Total**: 47-58 pages (perfect for B.Tech)

---

## 7. WHAT MAKES THIS A "GOOD" B.TECH PROJECT?

### **Strengths**:
✅ **Current Topic**: LLMs + Networking = very relevant
✅ **Practical Impact**: Addresses real industry problem
✅ **Technical Depth**: Combines NLP + Systems + Networking
✅ **Demonstrable**: Can show working system in demo
✅ **Novel**: RAG for network configs is cutting-edge
✅ **Achievable**: Scope fits 5-month timeline

### **Presentation Points**:
- Show live demo: Intent → Config → Validation
- Highlight comparison: "Without RAG, LLM made errors X, Y, Z. With RAG, zero errors."
- Emphasize cost: "₹0 implementation using open-source tools"
- Show real Cisco configs working in GNS3

---

## 8. RISKS & MITIGATION

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| GNS3 setup issues | High | Start immediately, use GNS3 VM, ask in forums |
| LLM API limits | Medium | Use free tier efficiently, cache responses |
| Documentation parsing | Medium | Start with manual chunking, automate later |
| Time overrun | Medium | Focus on 5 core intents, add more if time permits |
| Too ambitious | High | **Scope down early** - better to have working MVP |

---

## 9. WEEK-BY-WEEK CHECKLIST

### Month 1
- [ ] Week 1: Install all software
- [ ] Week 2: Download vendor docs, parse 100 pages
- [ ] Week 3: ChromaDB populated with 500 chunks
- [ ] Week 4: RAG retrieval working (test queries)

### Month 2
- [ ] Week 1: Intent parser for 3 intents
- [ ] Week 2: Intent parser for 5 intents
- [ ] Week 3: LLM prompt template
- [ ] Week 4: Generate first working config

### Month 3
- [ ] Week 1: Learn Batfish API
- [ ] Week 2: Batfish validation integrated
- [ ] Week 3: GNS3 topology setup
- [ ] Week 4: GNS3 validation integrated

### Month 4
- [ ] Week 1: Flask web app skeleton
- [ ] Week 2: UI pages complete
- [ ] Week 3: End-to-end integration
- [ ] Week 4: Test all 5 intent types

### Month 5
- [ ] Week 1: Run evaluations, collect metrics
- [ ] Week 2: Write thesis (Chapters 1-3)
- [ ] Week 3: Write thesis (Chapters 4-6)
- [ ] Week 4: Create PPT, prepare demo, submit

---

## 10. ALTERNATIVE: EVEN SIMPLER VERSION (If Struggling)

If 5 months feels tight, further simplify to:

**Ultra-Minimal Scope**:
- 1 vendor (Cisco)
- 3 intent types (Interface, Routing, ACL)
- Validation: Batfish only (skip GNS3)
- No web UI (command-line tool)
- Thesis: 30-40 pages

**Still valuable** - demonstrates core RAG concept!

---

## CONCLUSION

**Yes, this is completable in 5 months for a B.Tech project IF you:**
1. **Scope down aggressively** (single vendor, 5 intents, 2-tier validation)
2. **Use existing tools** (don't build from scratch)
3. **Focus on working demo** (not comprehensive research)
4. **Start immediately** (Month 1 is critical)
5. **Be ready to cut features** (add complexity only if ahead of schedule)

**This is actually an excellent B.Tech project** because:
- It's technically challenging but achievable
- Uses current technology (LLMs, RAG)
- Has practical applications
- Results are demonstrable
- Can lead to publications later (if you want to pursue research)

**Recommended Next Steps**:
1. Pick ONE vendor (Cisco recommended)
2. Set up environment this week
3. Get GNS3 working before anything else
4. Create simple proof-of-concept by end of Month 1

**Questions to ask me**:
- "Which vendor should I pick?" (Cisco - more resources)
- "Should I use ChatGPT API or Llama 3?" (Llama 3 via Groq - free tier)
- "What if I can't get GNS3 working?" (Use Batfish only + pyATS for validation)

Want me to create:
1. **Detailed setup guide** for Month 1?
2. **Code templates** to get started?
3. **Sample thesis outline** with chapter breakdowns?

Let me know what would help you get started!