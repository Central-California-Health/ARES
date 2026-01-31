# ARES: Automated Recursive Evidence Synthesis

An autonomous multi-agent system designed to perform large-scale meta-analysis, thematic synthesis, and adversarial gap analysis on hypertension research literature using **System 2 Cognitive Architectures**.

## 🚀 Overview

ARES (formerly GEMINI) simulates a virtual research laboratory where specialized AI agents collaborate to ingest research papers, debate findings, and autonomously publish rigorous review articles. The system utilizes a **Double-Loop Learning** paradigm, where qualitative performance metrics are used to optimize agent behavior in real-time.

To maximize efficiency and GPU throughput, ARES now employs **Redis Stack** for vector memory storage and semantic caching, offloading retrieval tasks from the CPU.

### Key Features
- **System 2 Architecture:** Unlike standard LLM summarizers, ARES employs adversarial audit loops that force the system to "pause and reflect" on methodological flaws.
- **High-Performance Memory (Redis Stack):** Uses **RediSearch (HNSW Vector Index)** to retrieve relevant memories instantly, replacing slow CPU-based cosine similarity calculations.
- **Semantic Caching:** Caches deterministic LLM outputs (e.g., prompt templates) in Redis to prevent redundant GPU generation, reducing latency to near-zero for repeated queries.
- **Recursive Learning Loop:** Performance grades (Synthesis, Criticality, Voice) are stored in `feedback_history.json` and injected as "Directives" into future runs.
- **Epistemic Auditing (Dr. Matrix):** Automatically extracts variables and identifies "Epistemic Gaps" (e.g., causal claims in title vs. observational design).
- **Generative Research Design (Dr. Genesis):** Autonomously designs "Gold Standard" protocols to solve the limitations identified in the current literature.

## 👥 Specialized Agent Roles

- **Dr. Analysis (The Synthesizer):** Focuses on data-supported patterns and mandatory limitation extraction.
- **The Investigator (The Auditor):** An adversarial agent that attacks logical leaps and enforces "correlation != causation."
- **Dr. Matrix (The Epistemic Mapper):** Maps the Knowledge Graph and flags "Title-Bait" (Mismatch between claim and evidence).
- **Dr. Logic (The Philosopher):** Applies a "So What?" causal analysis to expose the "Illusion of Choice" and propose structural over behavioral solutions.
- **Dr. Genesis (The Research Architect):** Generates new study protocols to fix the gaps identified by the audit loop.
- **Meta-Reviewer (Editor-in-Chief):** Synthesizes insights into "Special Issues" and undergoes multi-turn self-critique.

## 🔄 The ARES Pipeline

1. **Ingestion:** Researcher reads a paper and generates a summary (cached via Redis).
2. **Audit:** Dr. Matrix extracts claims into `living_knowledge_graph.json` and flags methodological gaps.
3. **Logic Check:** Dr. Logic critiques the batch for "Behavioral Fallacies" and proposes "Architecture Cures."
4. **Invention:** Dr. Genesis designs a "Fix" protocol in `living_protocols.json`.
5. **Memory Retrieval:** Agents query the Redis Vector Store to find relevant past studies.
6. **Discussion:** Agents debate the batch findings using retrieved context.
7. **Publication:** Meta-Reviewer synthesizes a "Special Issue."
8. **Evaluation:** The Senior Editor grades the output, closing the recursive loop.

## 🛠 Project Structure

```text
/
├── src/
│   ├── agents/
│   │   ├── researcher.py      # Core research loop
│   │   ├── matrix.py          # Dr. Matrix (Knowledge Graph)
│   │   ├── logic.py           # Dr. Logic (Causal Philosophy)
│   │   ├── genesis.py         # Dr. Genesis (Protocol Designer)
│   │   ├── memory.py          # Redis Vector Store & Retrieval
│   │   ├── llm.py             # LLM Interface with Semantic Caching
│   │   ├── compiler.py        # Meta-Analysis generator
│   │   └── ...
├── ares_console.py            # Manual Head-to-Head Auditor (Console)
├── extract_claims.py          # Standalone Knowledge Graph generator
├── run_logic.py               # Standalone Logic Manifesto generator
├── run_genesis.py             # Standalone Protocol generator
├── snapshot.py                # Versioning and Experiment Archiving
├── living_meta_analysis.md    # Master synthesis
├── living_knowledge_graph.json # Structured claims & gaps
├── living_logic_manifesto.md  # Philosophical critique of causality
└── living_protocols.json      # Autonomous study designs
```

## 🏃 Running the System

### 1. Infrastructure Setup (Redis Stack)
Ensure Docker is installed, then run the Redis Stack container for vector search and caching:
```bash
docker run -d --name redis-stack-ares -p 6380:6379 -p 8001:8001 redis/redis-stack:latest
```
- **Port 6380:** Redis Vector Store & Cache (mapped to avoid conflicts with default 6379).
- **Port 8001:** RedisInsight Dashboard (View your vectors at `http://localhost:8001`).

### 2. Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Execution
1. **Start Simulation:** `python3 src/main.py`
   *(The system will automatically initialize the vector indexes on the first run.)*
2. **Audit Performance:** `python3 ares_console.py`
3. **Archive Results:** `python3 snapshot.py save [run_name]`

## 📑 Outputs

- **`living_meta_analysis.md`**: The master narrative.
- **`living_knowledge_graph.json`**: The structured evidence database.
- **`living_protocols.json`**: Autonomous future research proposals.
- **`special_issue_*.md`**: Journal-style deep-dives.
