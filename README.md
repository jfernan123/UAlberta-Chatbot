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
- **Case-insensitive query handling** (mdp → MDP, honours → Honors, etc.)
- **LangChain tools for on-demand course information** (prerequisites, sequences, searches)
- **Course dependency graph** with MATH and STAT prerequisites (178 courses)
- **Graduate/Senior level course detection** (400-level, 500-level)

## Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) installed
- assuming `uv` dependency management, but .lock and .toml left out for other environment users
- Data files (pre-configured):
  - `data/pages_math.json` - 137 scraped pages
  - `data/course_graph.json` - 178 courses (120 MATH + 58 STAT) with prerequisites
  - `data/evaluation_history.json` - Evaluation run history
  - `db/` - Chroma vector database

## Setup

### 1. Install Dependencies

If using `uv`:
```bash
uv sync
```

### 2. Install Ollama

Follow instructions at https://ollama.com


### 3. Start Ollama Server

```bash
ollama serve
```

### 3. Pull Models

```bash
ollama pull qwen3:0.6b
ollama pull nomic-embed-text
```

## Usage

### Quick Start (Recommended)

The repository comes pre-configured with relevant Math & Stats data (`data/pages_math.json`).

```bash
# Create or rebuild vector database (uses pages_math.json by default)
uv run python make_db.py

# Run CLI chatbot
uv run python chatbot.py

# Or run web UI
uv run streamlit run app.py
```

### Rebuilding the Database

If you modify the data source, rebuild the database:

```bash
# With default data (pages_math.json)
uv run python make_db.py

# With custom data
uv run python make_db.py --input data/your_data.json

# Verbose output
uv run python make_db.py -v
```

### Filter Priority Patterns (for web_crawler output)

When using `filter_crawler.py` to process crawled URLs:

| Priority | Pattern | Description |
|----------|---------|-------------|
| 1 | `/undergraduate-studies/programs/` | Program pages |
| 2 | `/undergraduate-studies/courses/` | Course pages |
| 3 | `/graduate-studies/` | Graduate info |
| 4 | `calendar.ualberta.ca` + MATH/STAT | Calendar MATH/STAT pages |
| 5 | MDP program | Modeling, Data & Predictions |

```bash
# Filter crawled URLs (requires raw_html/ from web_crawler)
uv run python filter_crawler.py --input-dir raw_html --max-urls 50
```

### Course Dependency Graph

The chatbot includes structured course information that helps answer questions about:
- First-year courses (100-level)
- Second-year courses (200-level)
- Course prerequisites and alternatives
- MATH and STAT course sequences
- Course levels clarified: 100=Year 1, 200=Year 2, etc.

#### How It Works
Course data is stored in `data/course_graph.json` and loaded via LangChain tools on-demand, not in the prompt. This prevents context bloat and ensures accurate prerequisite information.

#### Course Sequences Supported
- **Engineering**: MATH 100 → MATH 101 → MATH 209
- **Honors**: MATH 117 → MATH 118 → MATH 217
- **Regular Life Sciences**: MATH 134 → MATH 136
- **Regular Math/Physical Sciences**: MATH 144 → MATH 146
- **Regular Business**: MATH 154 → MATH 156
- **Applied Statistics**: STAT 151 → STAT 252 → STAT 266 → STAT 372 → STAT 378
- **Probability**: STAT 265 → STAT 371 → STAT 471

#### Commands
```bash
# Build/update course graph
python course_graph.py

# Query specific course
python course_graph.py --query "MATH 100"

# List all courses
python course_graph.py --list
```

> **Note:** Course terminology clarification:
> - "Undergraduate" = course level (100-400), not first-year students
> - "Graduate" = 500+ level courses
> - Course numbers indicate year level: 100=Year 1, 200=Year 2, etc.

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
| `parsers.py` | Shared BeautifulSoup parsing logic |
| `filter_crawler.py` | Filters crawled URLs by priority patterns |
| `filter_suite.py` | Experiment runner for testing filter configs |
| `course_graph.py` | Builds course dependency graph from calendar data |
| `course_tools.py` | LangChain tools for on-demand course lookups |
| `make_db.py` | Create vector DB from scraped data |
| `chunker.py` | Chunks JSON for embedding |
| `vector_store.py` | Chroma vector database |
| `retriever.py` | Hybrid BM25 + vector retrieval |
| `chatbot.py` | RAG chain with qwen3:0.6b and course tools |
| `app.py` | Streamlit web UI |
| `evaluation.py` | Evaluation suite with 17 test cases |
| `feedback.py` | User feedback collection |
| `analytics.py` | Feedback analysis & reporting |

> **IMPORTANT:** The retriever (`retriever.py`) and vector DB (`db/`) must use the same data source. By default, both use `data/pages_math.json`. If you rebuild the DB with different data, update `retriever.py` accordingly.

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

This runs 20 test cases and reports:
- **Retrieval Precision@4** - Quality of document retrieval (target: >0.8)
- **Keyword Coverage** - Does response contain expected keywords?
- **ROUGE-L** - String similarity with reference
- **Overall Score** - Weighted combination of metrics

### Test Cases (20 total)

The evaluation includes questions on:
- First-year courses (Calculus, Linear Algebra, Statistics)
- Program differences (Honors vs Major)
- Double majors and minors
- Student support resources
- Program-specific questions (Statistics overview, Mathematics overview)
- **Course prerequisites** (5 test cases added)
- **Year-level queries** (3 test cases added)
  - Graduate MATH courses
  - Senior STAT courses
  - Graduate courses (both)

### Current Results

Using the combined Math & Stats + Calendar data (137 pages) with LangChain course tools:

```
Metrics (averaged across 20 test cases):
  - Retrieval Precision@4:     1.000
  - Keyword Coverage:          0.674
  - ROUGE-L:                  0.057
  - Overall Score:             0.587

By Category:
  - prerequisites: 0.656 (best)
  - programs: 0.577
  - courses: 0.559
  - level_specific: 0.553
  - support: 0.517
```

### Test Case Updates (Apr 2026)

Added 3 NEW test cases for graduate/senior level queries:
- "What graduate MATH courses are available?"
- "What senior STAT courses are available?"
- "What graduate courses are there?"

Also added prompt instructions to ensure Decima Robinson Support Centre is mentioned when asking about student help.

The hybrid approach (BM25 + vector) with LangChain course tools provides high-quality retrieval and accurate prerequisite information.

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

## Future Work

### Router Agent
Add a routing agent to classify questions and route to specialized retrieval. This would improve topic-specific accuracy for questions about specific programs (Statistics, Mathematics, etc.).

### Reinforcement Learning on User Responses
Implement RL-based improvement using explicit thumbs up/down feedback to weight retrieval results. This would let the system learn which content sources are most helpful based on user satisfaction.

### Additional Program Content
Continue expanding scraped pages to cover more UAlberta Math & Stats programs and course catalog details.

### Course Graph Enhancements (Done ✓)
- Course prerequisites extracted for **178 courses** (120 MATH + 58 STAT)
- Implemented as LangChain tools with on-demand retrieval
- Added prerequisite test cases to evaluation suite
- Added graduate/senior level course detection (400-level, 500-level)
- Test cases: "What graduate MATH courses?", "What senior STAT courses?"

## License

This project is MIT Licensed.

**Streamlit** is Apache 2.0 licensed - see [Streamlit License](https://github.com/streamlit-io/streamlit/blob/master/LICENSE)

