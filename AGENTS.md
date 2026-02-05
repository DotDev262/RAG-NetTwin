# AGENTS.md - Project Context for RAG-NetTwin

**Project Name**: Hallucination-Mitigated Intent-Based Networking (RAG-NetTwin)  
**Type**: B.Tech Final Year Project with Journal Publication Goal  
**Timeline**: 10 Months (5 months implementation + 5 months paper)  
**Last Updated**: February 4, 2026  

---

## 🎯 PROJECT OVERVIEW

**Objective**: Build a system that generates network configurations from natural language intents while minimizing LLM hallucinations through RAG + multi-tier validation.

**Key Innovation**: OS Version-Locked RAG with Three-Tier Validation  
**Target**: <2% hallucination rate (vs 20-30% for vanilla LLMs)

**Core Components**:
1. Hierarchical RAG (Tier 1, 2, 3 chunking)
2. Intent Parser with OS version locking
3. Multi-vendor coordination (Cisco + Juniper)
4. Three-tier validation: Batfish → Containerlab → GNS3
5. Supervisory gate with human-in-the-loop

---

## 📋 CURRENT STATUS

**Phase**: Ready to start Week 1 implementation  
**Documents Created**:
- ✅ RESEARCH_PLAN.md (Complete, updated)
- ✅ WEEK1-2_IMPLEMENTATION_GUIDE.md (Ready to use)
- ✅ BTECH_5MONTH_PLAN.md (Reference)
- ✅ JOURNAL_5MONTH_PLAN.md (Reference)

**Next Action**: Environment setup + data collection (Week 1-2)

---

## 🔧 KEY ARCHITECTURAL DECISIONS

### 1. **RAG-Only Approach** (NO Fine-Tuning)
- Use Llama 3.1 70B via Groq API (free tier)
- No model fine-tuning on network configs
- All commands come from retrieved vendor docs
- **Why**: Eliminates training data hallucinations, reproducible

### 2. **"Hallucination-Mitigated" NOT "Zero"**
- Theoretical lower bound: 0.1-0.5% (due to retrieval limits)
- Target: <2% hallucination rate
- Honest about limitations in paper

### 3. **Three-Tier Validation**
```
Tier 1: Batfish Static Analysis (~100ms, catches 80%)
Tier 2: Containerlab Emulation (~30s, protocol tests)
Tier 3: GNS3 Full Simulation (~3-5min, traffic tests)
```
- Progressive validation based on risk

### 4. **Single Vendor Focus for Implementation**
- Start with Cisco IOS-XE 17.6
- Add Juniper later if time permits
- Quality > breadth

### 5. **Zero Budget Constraint**
- All tools are free/open-source
- Groq API free tier (1M tokens/day)
- Personal laptop sufficient (16GB RAM)
- GNS3 VIOS images (free)
- **Total cost**: ₹0-500

---

## 📅 TIMELINE (10-Month Phased)

### **Phase 1: Implementation (5 months, 35-40 hrs/week)**
- **Month 1**: RAG pipeline, ChromaDB, 500+ chunks
- **Month 2**: Version-locked RAG, multi-vendor coordination
- **Month 3**: Batfish + Containerlab integration
- **Month 4**: GNS3 integration, Flask UI
- **Month 5**: End-to-end system, basic testing

### **Phase 2: Paper (5 months, 15-25 hrs/week)**
- **Month 6**: 100-200 test intents
- **Month 7**: 4 baselines comparison
- **Month 8**: Ablation studies, error analysis
- **Month 9**: Paper writing (15-20 pages)
- **Month 10**: Submission

**Target Journal**: IEEE Internet Computing or Journal of Network and Systems Management

---

## 🏗️ TECH STACK

### **Core**:
- **Language**: Python 3.10+
- **Vector DB**: ChromaDB (local)
- **LLM**: Llama 3.1 70B via Groq API (free tier)
- **RAG**: LangChain
- **Web UI**: FastAPI (Backend) + React or Simple HTML/JS

### **Validation**:
- **Tier 1**: Batfish (Docker container)
- **Tier 2**: Containerlab (Docker-based)
- **Tier 3**: GNS3 (local VM)

### **Utilities**:
- **PDF Processing**: pypdf, pdfplumber
- **Embeddings**: sentence-transformers (all-MiniLM)
- **Testing**: pytest
- **Docs**: Markdown, Jupyter notebooks

---

## 📁 PROJECT STRUCTURE

```
ragnet-ibn/
├── data/
│   ├── raw_docs/           # Cisco PDFs
│   ├── processed_chunks/   # JSON chunks
│   ├── configs/           # Generated configs
│   └── chroma_db/         # Vector database
├── src/
│   ├── data_processing/   # PDF extraction, chunking
│   ├── rag/              # Vector store, retrieval
│   ├── parser/           # Intent parser
│   └── validation/       # Batfish, Containerlab, GNS3
├── ui/
│   ├── frontend/         # HTML/JS dashboard
│   └── backend/          # FastAPI API
├── tests/               # Test scripts
├── notebooks/          # Jupyter experiments
├── results/            # Evaluation results
├── docs/              # Research documents
│   ├── RESEARCH_PLAN.md
│   ├── WEEK1-2_IMPLEMENTATION_GUIDE.md
│   └── AGENTS.md (this file)
└── requirements.txt
```

---

## ⚙️ IMMEDIATE NEXT STEPS (Week 1)

### **Day 1-2: Environment**
```bash
# 1. Create project directory
mkdir -p ~/Projects/ragnet-ibn
cd ~/Projects/ragnet-ibn

# 2. Setup Python virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 3. Install dependencies
pip install chromadb langchain pypdf sentence-transformers flask

# 4. Setup Groq API
# - Go to https://console.groq.com/
# - Create free account
# - Save API key to .env file
```

### **Day 3-4: Data Collection**
- Download Cisco IOS-XE 17.6 documentation
  - Command Reference
  - Configuration Guide
  - OSPF Guide
  - ACL Guide
- Save to `data/raw_docs/`

### **Day 5-7: Processing**
- Implement PDF extraction
- Hierarchical chunking (Tier 1, 2, 3)
- Store in ChromaDB

### **Day 8-14: Verification**
- 500+ chunks in database
- Test retrieval with queries
- Verify chunk quality

**Week 2 Deliverable**: Working RAG pipeline with 500+ chunks

---

## 🔑 CRITICAL SUCCESS FACTORS

1. **Start GNS3 setup EARLY** - It's the most complex component
2. **Document everything** - Keep daily log of progress
3. **Test continuously** - Don't wait until Month 5 to test
4. **Be ready to cut features** - Better working system than perfect system
5. **Commit to git daily** - Backup everything

---

## 🚨 COMMON PITFALLS TO AVOID

1. **Don't try to support 10 vendors** - Stick to 1-2
2. **Don't build perfect UI** - Functional is fine
3. **Don't wait to evaluate** - Test from Day 1
4. **Don't use all API tokens in Week 1** - Spread usage across months
5. **Don't skip documentation** - You'll forget why you made decisions

---

## 📊 EVALUATION PLAN (For Phase 2)

### **Baselines to Compare**:
1. Vanilla LLM (no RAG)
2. RAG without version lock
3. Template-based (Jinja2)
4. ChatGPT-4
5. Human engineers (mid-level)
6. Single-tier validation (GNS3 only)

### **Metrics**:
- Hallucination rate (<2% target)
- Syntactic accuracy (>99% target)
- Semantic correctness (>95% target)
- Intent fidelity (>98% target)
- Validation latency (<30s routine, <5min complex)

### **Statistical Tests**:
- t-tests for significance
- Confidence intervals
- 5 runs per baseline for variance

---

## 📝 PAPER STRUCTURE (Target: 15-20 pages)

1. **Abstract** (150 words)
2. **Introduction** (2 pages) - Problem, solution, contributions
3. **Related Work** (3 pages) - 10-12 papers
4. **System Design** (3 pages) - Architecture, innovations
5. **Implementation** (2 pages) - Tech stack, brief
6. **Evaluation** (5 pages) - Extensive results, baselines
7. **Discussion** (1 page) - Limitations, threats
8. **Conclusion** (0.5 pages)

---

## 🎓 B.TECH THESIS vs JOURNAL PAPER

**B.Tech Thesis** (Month 5):
- 40-60 pages
- Broad system description
- Basic evaluation (20-30 tests)
- Graduation requirement

**Journal Paper** (Month 10):
- 15-20 pages
- ONE focused contribution
- Extensive evaluation (100+ tests)
- Statistical rigor
- Publication goal

**Strategy**: Extract journal paper from thesis, don't write two separate documents.

---

## 💡 KEY INSIGHTS TO REMEMBER

1. **This is research** - It's okay if things don't work first time
2. **Focus on contribution** - Version-locked RAG is your novel idea
3. **Evaluation sells the paper** - 4 baselines, statistics, ablation
4. **Documentation is research** - Track everything
5. **Journal reviewers want rigor** - Not just "it works"

---

## 📞 IF STUCK

**Technical Issues**:
- GNS3 problems → Check GNS3 forums, use simpler topology
- API limits → Switch to Ollama (local LLM)
- Retrieval quality → Adjust chunk size, try different embeddings

**Conceptual Issues**:
- Version-locking not working → Simplify to single version
- Multi-vendor too complex → Focus on one vendor
- Timeline slipping → Cut Containerlab, use Batfish + GNS3 only

**Motivation Issues**:
- Review Week 1-2 guide
- Run checkpoint script
- Remember: 10 months is doable, 5 months is possible

---

## ✅ CHECKPOINT: READY TO START?

Before beginning Week 1, verify:
- [ ] Read RESEARCH_PLAN.md completely
- [ ] Read WEEK1-2_IMPLEMENTATION_GUIDE.md
- [ ] Have 16GB+ RAM laptop
- [ ] Have 50GB free storage
- [ ] Can dedicate 35-40 hrs/week for Phase 1
- [ ] Faculty advisor approved the plan
- [ ] Git repository initialized

**If all checked**: Start Day 1 immediately!

---

## 🎯 END GOAL

**After 10 months**:
- ✅ Working system demonstrating version-locked RAG
- ✅ <2% hallucination rate achieved
- ✅ Journal paper submitted
- ✅ B.Tech degree completed
- ✅ Strong research portfolio for future

**This is achievable.** Stay focused, document everything, ask for help when stuck.

---

**Questions? Review the main documents**:
1. RESEARCH_PLAN.md - Full technical details
2. WEEK1-2_IMPLEMENTATION_GUIDE.md - Day-by-day instructions
3. This file - Quick reference

**Last reminder**: Start Week 1 TODAY. Momentum is everything!
