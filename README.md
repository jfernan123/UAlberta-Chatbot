# UAlberta-Chatbot

A RAG chatbot for University of Alberta Math & Statistics department using local LLMs (no API costs).

## Features

- Web scraping of UAlberta Math & Stats pages → JSON
- Chroma vector database for semantic search
- Local LLM inference via Ollama (qwen3:0.6b)
- Streamlit web UI + CLI interface

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
| `app.py` | Streamlit web UI |

## Model Options

For better quality (requires more RAM):

```bash
ollama pull qwen3:1.7b
# Then update chatbot.py to use model="qwen3:1.7b"
```