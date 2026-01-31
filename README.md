# ARES: Automated Recursive Evidence Synthesis

An autonomous multi-agent system designed to perform large-scale meta-analysis, thematic synthesis, and adversarial gap analysis on research literature (specifically hypertension) using **System 2 Cognitive Architectures**.

## 🚀 Overview

ARES simulates a virtual research laboratory where specialized AI agents collaborate to ingest research papers, debate findings, and autonomously publish rigorous review articles. The system utilizes a **Double-Loop Learning** paradigm, where qualitative performance metrics are used to optimize agent behavior in real-time.

To maximize efficiency and throughput, ARES employs **Redis Stack** for vector memory storage and semantic caching, and **PostgreSQL** for robust document management.

## 📋 Requirements & Prerequisites

### Hardware Specifications
ARES runs local LLMs via **Ollama**, which requires significant hardware resources for optimal performance:

*   **GPU (Critical):** NVIDIA GPU with at least **12GB VRAM** (e.g., RTX 3060 12GB, 3080, 4090).
    *   *Why?* The system uses models like `command-r` which require substantial memory to handle the large context windows (32k+) used in research synthesis.
*   **CPU:** Modern Multi-core Processor (Intel i7/Ryzen 7 or equivalent).
*   **RAM:** 32GB recommended.
    *   *Why?* Redis Vector Store and concurrent agent processing benefit from high system memory.
*   **Storage:** SSD with at least 50GB free space (for Docker images and LLM weights).

### Software Stack
*   **Python:** 3.8+
*   **Docker:** Required for running Redis Stack.
*   **PostgreSQL:** 13+ (Local or Remote).
*   **Ollama:** Must be installed and running locally.
*   **Vector Store:** Redis Stack (via Docker).

## 🛠 Installation & Setup

### 1. LLM Setup (Ollama)
ARES is optimized for local inference using Ollama.
1.  [Install Ollama](https://ollama.ai/).
2.  Pull the required models:
    ```bash
    ollama pull command-r:latest
    ollama pull qwen3-embedding:0.6b
    ```

### 2. Database Setup (PostgreSQL)
ARES requires a PostgreSQL database to store the raw text and metadata of research papers.
1.  Install PostgreSQL.
2.  Create a database (e.g., `hypertension_db`).
3.  Initialize the schema:
    ```bash
    psql -U your_username -d hypertension_db -f schema.sql
    ```

### 3. Infrastructure Setup (Redis Stack)
Run the Redis Stack container for vector search and semantic caching.
```bash
docker run -d --name redis-stack-ares -p 6380:6379 -p 8001:8001 redis/redis-stack:latest
```

### 4. Configuration
Create a `.env` file in the root directory:
```ini
# LLM Configuration (Ollama)
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=command-r:latest
EMBEDDING_MODEL=qwen3-embedding:0.6b

# Database Configuration
DB_HOST=localhost
DB_NAME=hypertension_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432
```

## 🔄 The ARES Pipeline

1.  **Taxonomy Refinement:** On new runs, the system dynamically restructures `taxonomy.yml` using the LLM to create an optimal research framework for the defined topic.
2.  **Ingestion:** Researcher reads a paper from Postgres and generates a summary (cached via Redis).
3.  **Audit:** Dr. Matrix extracts claims into `living_knowledge_graph.json` and flags methodological gaps.
4.  **Logic Check:** Dr. Logic critiques the batch for "Behavioral Fallacies" and proposes "Architecture Cures."
5.  **Invention:** Dr. Genesis designs a "Fix" protocol in `living_protocols.json`.
6.  **Memory Retrieval:** Agents query the Redis Vector Store to find relevant past studies.
7.  **Discussion:** Agents debate the batch findings using retrieved context.
8.  **Publication:** Meta-Reviewer synthesizes a "Special Issue."
9.  **Evaluation:** The Senior Editor grades the output, closing the recursive loop.

## 👥 Specialized Agent Roles

*   **Dr. Analysis (The Synthesizer):** Focuses on data-supported patterns.
*   **The Investigator (The Auditor):** Attacks logical leaps ("correlation != causation").
*   **Dr. Matrix (The Epistemic Mapper):** Maps the Knowledge Graph and flags "Title-Bait".
*   **Dr. Logic (The Philosopher):** Applies causal analysis to expose the "Illusion of Choice".
*   **Dr. Genesis (The Research Architect):** Generates new study protocols.
*   **Meta-Reviewer (Editor-in-Chief):** Synthesizes insights into "Special Issues".

## 🏃 Running the System

1.  **Start Simulation:**
    ```bash
    python3 src/main.py
    ```
    *(The system will automatically initialize the vector indexes and refine the research taxonomy on new runs.)*

2.  **Audit Performance:**
    ```bash
    python3 ares_console.py
    ```

3.  **Archive Results:**
    ```bash
    python3 snapshot.py save [run_name]
    ```

## 📑 Outputs

*   `living_meta_analysis.md`: The master narrative.
*   `living_knowledge_graph.json`: Structured evidence database.
*   `living_protocols.json`: Autonomous future research proposals.
*   `special_issue_*.md`: Journal-style deep-dives.
