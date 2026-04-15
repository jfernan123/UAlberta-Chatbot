# UAlberta-Chatbot

A RAG chatbot for University of Alberta Math & Statistics department using local LLMs (no API costs).

## Features

- Web scraping of UAlberta Math & Stats pages → JSON
- Chroma vector database for semantic search
- Local LLM inference via Ollama (qwen3:0.6b)
- Continuous chat UI (press Enter to submit)
- User feedback collection with 👍/👎 ratings
- Analytics dashboard for response improvement
- CLI and web interface

## Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) installed

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Install Ollama

Follow instructions at https://ollama.com

### 3. Pull Models

```bash
ollama pull qwen3:0.6b
ollama pull nomic-embed-text
```

### 4. Start Ollama Server

```bash
ollama serve
```

## Usage

### Scrape Data

```bash
uv run python scraper.py
```

This saves scraped content to `data/pages.json`.

### Create Vector DB

```bash
uv run python -c "
from chunker import chunk_json
from vector_store import create_vector_db
chunks = chunk_json('data/pages.json')
create_vector_db(chunks)
"
```

### Run Web UI

```bash
uv run streamlit run app.py
```

Then open http://localhost:8501 in your browser.
- Type a question and press Enter to submit
- Click 👍 or 👎 to rate responses
- See your chat history scrolling up
- Click "Clear Chat History" to start fresh

### Run CLI

```bash
uv run python chatbot.py
```

## Architecture

| File | Purpose |
|------|---------|
| `scraper.py` | Scrapes UAlberta pages → JSON |
| `chunker.py` | Chunks JSON/text for embedding |
| `vector_store.py` | Chroma vector database |
| `retriever.py` | Loads vector DB for retrieval |
| `chatbot.py` | RAG chain with qwen3:0.6b |
| `app.py` | Streamlit web UI (chat interface) |
| `feedback.py` | User feedback collection |
| `analytics.py` | Feedback analysis & reporting |
| `evaluation.py` | Evaluation suite with metrics |

## Feedback & Analytics

### User Feedback
Users can rate responses with 👍/👎 buttons directly in the chat UI. Feedback is stored in `data/feedback.json`.

```bash
# View feedback data
cat data/feedback.json
```

### Analytics
Run analytics to see improvement recommendations:

```bash
uv run python analytics.py
```

This generates:
- Positive/negative feedback counts
- Category breakdown (courses, programs, support)
- Questions needing attention
- Improvement recommendations

### Sample Output

```
--- FEEDBACK BY CATEGORY ---
  COURSES: Positive: 0%, Negative: 100%
  PROGRAMS: Positive: 80%, Negative: 20%

--- RECOMMENDATIONS ---
  ❌ Category 'courses' has more negative than positive feedback. 
     Consider adding more courses content.
```

## Evaluation

Run the evaluation suite to test the chatbot:

```bash
uv run python evaluation.py
```

This runs 8 test cases and reports:
- **Retrieval Precision@4** - Quality of document retrieval (target: >0.8)
- **Keyword Coverage** - Does response contain expected keywords?
- **ROUGE-L** - String similarity with reference
- **Overall Score** - Weighted combination of metrics

### Sample Results

```
Metrics (averaged across 8 test cases):
  - Retrieval Precision@4:     0.875
  - Keyword Coverage:          0.533
  - ROUGE-L:                   0.062
  - Overall Score:             0.494

By Category:
  - programs: 0.616 (n=4)
  - support: 0.538 (n=1)
  - courses: 0.317 (n=3)
```

## Model Options

This repo uses qwen3:0.6b by default. Other options:

### Qwen (recommended for reasoning)

```bash
ollama pull qwen3:1.7b  # Better quality, ~6GB RAM
ollama pull qwen3:8b    # Best quality, ~16GB RAM
```

### Llama (alternative)

```bash
ollama pull llama3.1:8b  # ~16GB RAM
```

To switch models, update `chatbot.py`:

```python
llm = ChatOllama(model="llama3.1:8b", temperature=0)
```

## License

This project is MIT Licensed.

**Streamlit** is Apache 2.0 licensed - see [Streamlit License](https://github.com/streamlit-io/streamlit/blob/master/LICENSE)