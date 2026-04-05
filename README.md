# FinSight — Autonomous Financial Research Agent

<div align="center">

![FinSight Banner](https://img.shields.io/badge/FinSight-Autonomous%20Financial%20Research-00d4ff?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDJDNi40OCAyIDIgNi40OCAyIDEyczQuNDggMTAgMTAgMTAgMTAtNC40OCAxMC0xMFMxNy41MiAyIDEyIDJ6IiBmaWxsPSIjMDBkNGZmIi8+PC9zdmc+)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-1C3A5F?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-FF6B35?style=flat-square)](https://www.trychroma.com)
[![Groq](https://img.shields.io/badge/Groq-Llama%203.1%2070B-F55036?style=flat-square)](https://groq.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**A production-grade multi-agent system that autonomously researches public companies by ingesting SEC filings, embedding them into a vector store, and generating structured analyst-style reports — with zero inference cost.**

[Live Demo](https://fin-sight-full.vercel.app/) · [Backend API](https://huggingface.co/spaces/ayush0910/finsight-api) · [Report a Bug](../../issues)

</div>

---

## What is FinSight?

FinSight is not a chatbot wrapper. It is an **agentic pipeline** that replicates the workflow of an equity research analyst:

1. **Fetches** 10-K and 10-Q filings directly from the SEC EDGAR API
2. **Chunks and embeds** them into a ChromaDB vector store using local BGE-small embeddings
3. **Decomposes** a natural language query into targeted sub-questions
4. **Retrieves** the most relevant chunks via vector similarity search with MMR
5. **Drafts** an analysis with inline source citations
6. **Validates** every numerical claim against the source documents
7. **Retries** if inconsistencies are found (up to 3 iterations)
8. **Generates** a structured analyst report: executive summary, key metrics, risk factors, YoY trends, and investment thesis

The key differentiator is the **stateful agentic loop** built with LangGraph — the system decides which documents to fetch, which sections to prioritize, and validates its own outputs for numerical consistency before returning a final answer.

---

## Demo

<div align="center">

| Company Search & Ingestion | Live Agent Trace | Analyst Report |
|:---:|:---:|:---:|
| Fetch SEC filings for any S&P 500 ticker | Watch the agent decompose, retrieve, draft, and validate in real time | 5-tab report: Summary · Metrics · Risks · YoY Chart · Thesis |

</div>

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│   CompanySearch → QueryPanel → AgentTrace → ReportViewer        │
│                   (SSE streaming)                               │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP / Server-Sent Events
┌─────────────────────▼───────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  /api/research/ingest  ·  /api/research/query  ·  /api/report   │
└──────────┬───────────────────────────┬──────────────────────────┘
           │                           │
┌──────────▼──────────┐   ┌────────────▼────────────────────────┐
│  Ingestion Pipeline │   │       LangGraph Agent Graph         │
│                     │   │                                      │
│  SEC EDGAR API      │   │  ┌─────────────────────────────┐    │
│       ↓             │   │  │  query_decomposer_node      │    │
│  Document Processor │   │  │         ↓                   │    │
│  (chunking, section │   │  │  retriever_node             │    │
│   tagging)          │   │  │         ↓                   │    │
│       ↓             │   │  │  analyst_node               │    │
│  BGE-small (local)  │   │  │         ↓                   │    │
│  Embeddings         │   │  │  validator_node ──────┐     │    │
│       ↓             │   │  │         ↓             │     │    │
│  ChromaDB           │   │  │  report_generator     │ ←───┘    │
│  Vector Store       │   │  │  (if valid)           │ retry     │
└─────────────────────┘   │  └─────────────────────────────┘    │
                           │           ↑                         │
                           │     Groq Llama 3.1 70B              │
                           └─────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| LLM | Groq — Llama 3.1 70B | Inference (free tier, ~14,400 req/day) |
| Agent Orchestration | LangGraph + LangChain | Stateful multi-agent loop |
| Embeddings | BGE-small-en-v1.5 (local) | Zero-cost semantic search |
| Vector Store | ChromaDB | Persistent chunk storage and retrieval |
| Data Source | SEC EDGAR API | Free public 10-K/10-Q filings |
| Backend | FastAPI + Uvicorn | REST API + SSE streaming |
| Experiment Tracking | MLflow | Prompt versioning and run logging |
| Frontend | React 18 + TypeScript | UI |
| Styling | Tailwind CSS | Dark terminal aesthetic |
| Charts | Recharts | YoY financial trend visualization |
| Backend Deployment | Hugging Face Spaces | Free hosting |
| Frontend Deployment | Vercel | Free hosting |

**Total inference cost: $0.** The entire stack runs on free tiers.

---

## Project Structure

```
finsight/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app + lifespan
│   │   ├── models.py                # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── research.py          # /ingest, /query, /report routes
│   │   │   └── companies.py         # /companies routes
│   │   ├── ingestion/
│   │   │   ├── sec_fetcher.py       # SEC EDGAR API client
│   │   │   ├── document_processor.py # Chunking + section tagging
│   │   │   ├── vector_store.py      # ChromaDB wrapper
│   │   │   └── pipeline.py          # Orchestrated ingestion flow
│   │   └── agents/
│   │       ├── state.py             # ResearchState TypedDict
│   │       ├── tools.py             # LangChain @tool definitions
│   │       ├── nodes.py             # LangGraph node functions
│   │       ├── graph.py             # StateGraph definition + FinSightAgent
│   │       ├── prompts.py           # All PromptTemplate objects
│   │       └── mlflow_tracker.py    # Experiment logging
│   ├── scripts/
│   │   ├── benchmark.py             # 50-question QA evaluation
│   │   └── qa_dataset.json          # Ground truth QA pairs (AAPL 2023)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Root layout + state
│   │   ├── index.css                # Global styles + animations
│   │   ├── components/
│   │   │   ├── CompanySearch.tsx    # Ticker input + ingestion progress
│   │   │   ├── AgentTrace.tsx       # Live pipeline visualization
│   │   │   ├── QueryPanel.tsx       # Query input + SSE streaming
│   │   │   └── ReportViewer.tsx     # 5-tab analyst report
│   │   └── services/
│   │       └── api.ts               # Typed API client
│   └── Dockerfile
└── docker-compose.yml
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Groq API key](https://console.groq.com) (free)

### 1. Clone

```bash
git clone https://github.com/yourusername/finsight.git
cd finsight
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create `.env` in `/backend`:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
SEC_USER_AGENT=Your Name youremail@gmail.com
CHROMA_PERSIST_DIR=./chroma_db
MLFLOW_TRACKING_URI=./mlruns
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`

### 3. Frontend setup

```bash
cd frontend
npm install
```

Create `.env` in `/frontend`:

```env
REACT_APP_API_URL=http://localhost:8000
```

Start the frontend:

```bash
npm start
```

Open `http://localhost:3000`

### 4. Docker (optional)

```bash
docker-compose up --build
```

---

## Usage

### Ingest a company

1. Enter a ticker symbol (e.g. `AAPL`) in the search panel
2. Click **Analyze** — the system fetches the last 3 years of 10-K/10-Q filings from SEC EDGAR, chunks them, embeds them locally, and stores them in ChromaDB
3. Wait for the ingestion progress bar to complete (~30–90 seconds depending on filing size)

### Run a query

Once a company is indexed, type any natural language question or use a preset:

- **Key Risk Factors** — extracts and ranks risks by severity
- **Revenue Growth** — YoY revenue breakdown by segment
- **Full Report** — complete 5-section analyst report
- **YoY Comparison** — key financial metrics over time

Watch the **Agent Trace** panel on the left to see the live pipeline: query decomposition → retrieval → analysis → validation → report generation.

### View the report

The **Analyst Report** tab contains:

| Tab | Content |
|---|---|
| Summary | 3-sentence executive summary |
| Metrics | Sortable table with color-coded YoY changes |
| Risks | Ranked list with HIGH / MEDIUM / LOW severity |
| YoY Chart | Area chart — revenue, net income, gross margin |
| Thesis | Bull case vs bear case side-by-side |

Click any citation pill `[Doc X]` in the response to open the source chunk drawer.

---

## Benchmarking

To reproduce the evaluation metrics:

```bash
cd backend

# First ingest Apple
python -c "
import asyncio
from app.ingestion.pipeline import IngestionPipeline
asyncio.run(IngestionPipeline().ingest_company('AAPL', years=3))
"

# Run benchmark
python scripts/benchmark.py
```

This evaluates FinSight against a naive RAG baseline on 50 hand-labeled financial QA pairs from the Apple 2023 10-K, measuring:

- **Answer accuracy** (exact match + fuzzy match)
- **Numerical accuracy** (within 1% tolerance)
- **Retrieval precision** (avg relevance score)
- **End-to-end latency**

---

## Deployment

### Backend → Hugging Face Spaces

1. Create a new Space with **Docker** SDK
2. Push the `/backend` directory
3. Add secrets in Space settings: `GROQ_API_KEY`, `SEC_USER_AGENT`
4. ChromaDB persists to Space storage

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
```

Set environment variable in Vercel dashboard:
```
REACT_APP_API_URL=https://your-space.hf.space
```

---

## MLflow Experiment Tracking

```bash
cd backend
mlflow ui --port 5001
```

Open `http://localhost:5001` to view logged runs, compare prompt versions, and track token usage and latency across experiments.

---

## Roadmap

- [ ] Add support for earnings call transcripts (via Whisper transcription)
- [ ] Implement company-to-company comparative analysis
- [ ] Add LLM re-ranking for retrieval (cross-encoder)
- [ ] Export reports as formatted PDF
- [ ] Persistent user sessions with report history

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with LangGraph · ChromaDB · Groq · FastAPI · React

**SEC EDGAR data is public domain. This tool is for research and educational purposes only. Not financial advice.**

</div>
