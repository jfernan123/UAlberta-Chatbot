# UAlberta Math & Stats Chatbot

RAG chatbot for the University of Alberta Department of Mathematical and Statistical Sciences. Answers questions about courses, prerequisites, programs, and graduate admissions.

## How It Works

```
User question
     ↓
[classify]  →  [retrieve]  →  [grade]  →  [generate]  →  Answer + Sources
                   ↑______________|
                  (retry with rewritten query if context is weak)
```

- **Classify** — LLM identifies the question type (prereq / courses / program requirements / admissions / general)
- **Retrieve** — calls structured course tools (JSON) + hybrid BM25 + vector search
- **Grade** — LLM checks if the retrieved context is sufficient; retries with a rewritten query if not
- **Generate** — produces the answer with source URLs appended

## Setup

### 1. Install dependencies

```bash
conda activate stat541
pip install langchain langchain-anthropic langchain-chroma langchain-ollama langgraph anthropic sentence-transformers
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

On Windows:
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

### 3. Build the vector database

```bash
python -m retrieval.make_db                        # delete old DB and rebuild (ollama embeddings)
python -m retrieval.make_db --embedding sentence   # use BGE instead of Ollama
python -m retrieval.make_db --embedding openai     # use OpenAI
python -m retrieval.make_db -v                     # verbose — shows chunk counts
```

Always does a full delete + rebuild from scratch. Reads `data/pages_math.json`, `data/pages_calendar.json`, and `data/pages_synthetic.json`.

---

## Running the Chatbot

### LangGraph chatbot (recommended)

```bash
python chatbot_graph.py                              # defaults: claude + ollama embeddings
python chatbot_graph.py --provider ollama            # use local qwen3 instead of Claude
python chatbot_graph.py --embedding sentence         # use BGE embeddings instead of Ollama
python chatbot_graph.py --provider ollama --embedding sentence
```

### Original chatbot (unchanged, for reference)

```bash
python chatbot.py                                    # defaults: ollama + ollama embeddings
python chatbot.py --provider claude                  # use Claude instead of local qwen3
python chatbot.py --embedding sentence
```

### Bare-bones CLI (no tools, raw retriever + Anthropic API)

```bash
python simple_chat.py
```

### Web UI

```bash
streamlit run app.py
```

---

## Running the Test Suite

```bash
python tests/run_suite.py
```

Runs 40 test questions and saves results to `tests/results/results_<timestamp>.ipynb`. Open the notebook in VS Code to read through answers and source URLs.

The suite is split into three tiers:
- **Easy** — direct prerequisite lookups, course listings, Decima Robinson
- **Medium** — program requirements, program comparisons, graduate admissions
- **Hard** — path planning, career outcomes, research opportunities, edge cases

---

## Data Pipeline

If you need to rebuild the data from scratch (e.g. after re-scraping):

```bash
# 1. Filter the math dept pages
python data/filter_math.py

# 2. Filter the calendar pages
python data/filter_calendar.py

# 3. Generate synthetic bridge documents
python data/generate_synthetic.py

# 4. Rebuild the vector DB (always deletes old DB first)
python -m retrieval.make_db -v
```

| File | What it does |
|---|---|
| `data/pages_math.json` | Scraped math dept website (87 pages) |
| `data/pages_calendar.json` | Scraped UAlberta calendar — MATH/STAT courses + program pages (182 pages) |
| `data/pages_synthetic.json` | Consolidated summary docs for hard queries (MSc application, honors requirements, etc.) |
| `data/course_graph.json` | Structured course data — 178 courses with prerequisites and sequences |

---

## Architecture

### Chatbot files

| File | Purpose |
|---|---|
| `chatbot_graph.py` | LangGraph chatbot — classify → retrieve → grade → generate |
| `chatbot.py` | Original chatbot with keyword-based routing (teammate's version) |
| `simple_chat.py` | Minimal CLI using raw Anthropic SDK + retriever |
| `app.py` | Streamlit web UI |

### Retrieval

| File | Purpose |
|---|---|
| `retrieval/retriever.py` | Hybrid retriever — RRF fusion of BM25 + ChromaDB |
| `retrieval/vector_store.py` | ChromaDB setup and rebuild logic |
| `retrieval/make_db.py` | CLI to build the vector DB from the 3 data files |
| `retrieval/chunker.py` | Splits pages into 2000-char chunks with 200-char overlap |
| `retrieval/embeddings.py` | Embedding model config (nomic-embed-text via Ollama) |

### Course tools

| File | Purpose |
|---|---|
| `courses/course_tools.py` | LangChain tools: prerequisites, course listings, program requirements |
| `courses/course_graph.py` | Builds `course_graph.json` from calendar data |

Tools available:
- `get_course_prerequisites` — returns raw prerequisite text from calendar (preserves OR/AND logic)
- `get_stat_courses` / `get_math_courses` — full course listings
- `get_courses_by_level` — filter by department and year level
- `get_course_sequence` — ordered pathway for a stream (engineering, honors, etc.)
- `get_program_requirements` — full unit requirements for Honors/Major/Minor in Math or Statistics
- `search_courses` — keyword search across course names

### Tests

| File | Purpose |
|---|---|
| `tests/run_suite.py` | Runs all 40 questions, saves timestamped `.ipynb` to `tests/results/` |
| `tests/test_suite.py` | Question lists (EASY / MEDIUM / HARD) |

---

## Model

Embeddings are controlled by the `EMBEDDING_PROVIDER` environment variable:

| `EMBEDDING_PROVIDER` | Model | Requires |
|---|---|---|
| `ollama` (default) | `nomic-embed-text` | Ollama running locally |
| `sentence` | `BAAI/bge-small-en-v1.5` | `pip install sentence-transformers` |
| `openai` | `text-embedding-3-small` | OpenAI API key |

**After switching embedding providers, rebuild the vector DB** — embeddings from different models are incompatible:

```bash
python -m retrieval.make_db -v
```

Both `chatbot.py` and `chatbot_graph.py` support two LLM backends, controlled by the `LLM_PROVIDER` environment variable (or the hardcoded default at the top of each file):

| File | Default |
|---|---|
| `chatbot.py` | `ollama` (qwen3:0.6b) |
| `chatbot_graph.py` | `claude` (Claude Haiku) |

```powershell
# Windows — run with Claude
$env:LLM_PROVIDER = "claude"; python chatbot_graph.py

# Windows — run with Ollama
$env:LLM_PROVIDER = "ollama"; python chatbot_graph.py
```

```bash
# Mac/Linux
LLM_PROVIDER=ollama python chatbot_graph.py
LLM_PROVIDER=claude python chatbot.py
```

### Using Claude (default)

Requires an Anthropic API key. Set it before running:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Mac/Linux
$env:ANTHROPIC_API_KEY = "sk-ant-..."  # Windows PowerShell
```

### Using Ollama (local, free)

Requires [Ollama](https://ollama.com) installed and running:

```bash
ollama serve
ollama pull qwen3:0.6b
ollama pull nomic-embed-text  # only needed if EMBEDDING_PROVIDER=ollama (default)
```

Then set `LLM_PROVIDER = "ollama"` in the chatbot file.
