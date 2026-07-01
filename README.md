# jd-analyzer

A CLI tool that analyzes job descriptions using OpenAI GPT-4o-mini and scores them against a candidate profile. Extracts structured data from `.txt` JD files, stores results in a local SQLite database, and generates aggregate reports.

It also includes a small RAG (retrieval-augmented generation) pipeline: ingest `.txt`/`.pdf` documents (resumes, JDs, notes) into a local ChromaDB vector store, then ask natural-language questions grounded in that content with source citations.

---

## Features

- Extracts company, role, level, required skills, tech stack, red flags, culture signals, and more
- Scores each JD against your personal candidate profile with a weighted breakdown
- Deduplicates files using MD5 hashing — re-running the same file is a no-op
- Supports single files or entire folders of JDs
- Stores all results in a local SQLite database
- Generates aggregate reports: skill frequency, tech stack trends, match score summary, level breakdown, red flags
- Ingests `.txt`/`.pdf` documents into a local ChromaDB vector store (chunked with `tiktoken`, embedded with `text-embedding-3-small`), skipping files already ingested
- Answers natural-language questions grounded in ingested documents, citing the source file(s) used

---

## Project Structure

```
job-search-ai/
├── src/
│   ├── main.py          # CLI entrypoint (Click)
│   ├── extractor.py     # OpenAI extraction logic (JD -> structured JSON)
│   ├── storage.py       # SQLite read/write functions
│   ├── reports.py       # Aggregate report generation
│   ├── ingestor.py      # Chunks + embeds documents into ChromaDB
│   ├── retriever.py     # Embeds a query and retrieves top-k relevant chunks
│   └── responder.py     # Builds a grounded prompt and calls GPT-4o-mini
├── documents/
│   └── jds/              # Place your .txt/.pdf job description files here
├── data/                          # Auto-created, gitignored
│   ├── jds.db                     # SQLite database
│   ├── chroma/                    # ChromaDB vector store
│   └── ingested_files.json        # Tracks which files have been ingested (dedup)
├── candidate_profile.yaml        # Public template — edit with your profile
├── candidate_profile.local.yaml  # Your private profile (gitignored)
├── .env                 # Your API key (gitignored)
├── .env.example         # API key template
└── requirements.txt
```

---

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd jd-analyzer
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your OpenAI API key

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder:

```
OPENAI_API_KEY=your_openai_api_key_here
```

### 5. Set up your candidate profile

Copy the template and fill in your details:

```bash
cp candidate_profile.yaml candidate_profile.local.yaml
```

Edit `candidate_profile.local.yaml`:

```yaml
name: Your Name
years_of_experience: "5+"
current_level: Senior Software Engineer

core_stack:
  - Python
  - AWS
  - Docker

domain:
  - SaaS
  - distributed systems

target_roles:
  - Staff Engineer at AI-focused companies

preferences:
  - remote friendly
  - small team

dealbreakers:
  - fully on-site
  - more than 25% travel

ai_experience: beginner
```

> `candidate_profile.local.yaml` is gitignored. The public `candidate_profile.yaml` template is committed and contains no personal information.

---

## Adding Job Descriptions

Place job description text files in the `documents/jds/` directory. Plain text, one file per JD. Filenames are saved to the database for reference.

```
documents/jds/
├── stripe_staff_engineer.txt
├── openai_forward_deployed.txt
└── example.txt
```

---

## Commands

All commands are run from the `src/` directory:

```bash
cd src
```

Or use the full path from the project root:

```bash
python src/main.py <command>
```

---

### `add` — Extract and save a job description

**Single file:**

```bash
python main.py add ../documents/jds/stripe_staff_engineer.txt
```

**Entire folder (processes all `.txt` files recursively):**

```bash
python main.py add ../documents/jds/
```

Each file is hashed before sending to OpenAI. If a file has already been processed, it is skipped automatically:

```
Saved  Staff Engineer  at  Stripe  (id: 3)
Skipped stripe_staff_engineer.txt (already processed)

Summary: 1 processed, 1 skipped
```

---

### `list` — Show all saved jobs

```bash
python main.py list
```

Prints a table with ID, company, role, and date saved:

```
╭────┬──────────┬─────────────────────┬────────────╮
│ ID │ Company  │ Role                │ Date       │
├────┼──────────┼─────────────────────┼────────────┤
│  3 │ Stripe   │ Staff Engineer      │ 2025-06-29 │
│  2 │ OpenAI   │ Fwd Deployed Eng    │ 2025-06-28 │
╰────┴──────────┴─────────────────────┴────────────╯
```

---

### `show` — Show full details for a job

```bash
python main.py show 3       # show job with id 3
python main.py show         # show the most recently saved job
```

Displays all extracted fields plus a score breakdown table:

```
╭─ Staff Engineer at Stripe ──────────────────────────────╮
│ Level: Staff                                             │
│ Experience: 7 years                                      │
│ Match score: 74/100                                      │
│ Summary: ...                                             │
│                                                          │
│ Required skills:                                         │
│   • Distributed systems                                  │
│   • Python or Go                                         │
│ ...                                                      │
╰──────────────────────────────────────────────────────────╯

╭─ Score Breakdown ────────────────────────────────────────────────────────╮
│  Component            Score   Reason                                     │
│  Tech stack match     22/30   Python and AWS overlap well                │
│  Seniority match      18/20   Targets Staff/L6 explicitly                │
│  Domain relevance     14/20   SaaS background transferable               │
│  AI skill gap         10/15   Some LLM experience preferred              │
│  Culture / logistics  10/15   Remote-friendly, IC role                   │
╰──────────────────────────────────────────────────────────────────────────╯
```

---

### `report` — Aggregate report across all saved jobs

```bash
python main.py report
```

Prints six sections:

| Section | What it shows |
|---|---|
| Required Skills Frequency | Top 15 skills ranked by how many JDs mention them |
| Tech Stack Frequency | Top 10 technologies across all JDs |
| Match Score Summary | Average, highest, and lowest scores with company/role |
| Experience Summary | Average years of experience requested |
| Red Flags | All unique red flags ranked by frequency |
| Level Breakdown | Count of Junior / Mid / Senior / Staff / Principal roles |

---

### `ingest` — Ingest documents into the vector store

```bash
python main.py ingest ../documents/Harish_Gujja_Resume.pdf
python main.py ingest ../documents/       # processes all .txt/.pdf files recursively
```

Loads `.txt`/`.pdf` files, chunks them (500 tokens, 50 token overlap, via `tiktoken`), embeds each chunk with `text-embedding-3-small`, and stores the chunks + embeddings in a local ChromaDB collection at `data/chroma/`. Files are hashed (MD5) and tracked in `data/ingested_files.json`, so re-running `ingest` on an already-ingested file is a no-op:

```
Ingested Harish_Gujja_Resume.pdf
Skipped adobe_senior_ai_platform_engineer.txt (already ingested)

Summary: 1 ingested, 1 skipped, 0 failed
```

---

### `ask` — Ask a question grounded in your ingested documents

```bash
python main.py ask "What skills does the candidate need for AI platform engineering roles?"
```

Embeds your question, retrieves the top 5 most relevant chunks across all ingested documents, and asks GPT-4o-mini to answer using only that context. Prints the answer plus the source file(s) it drew from:

```
╭─ Answer ──────────────────────────────────────────────────╮
│ Candidates need experience with LLM orchestration, ...     │
╰──────────────────────────────────────────────────────────╯
╭─ Sources ─────────────────────────────────────────────────╮
│ • adobe_senior_ai_platform_engineer.txt                    │
│ • kai_senior_swe_ai_platform.txt                            │
╰──────────────────────────────────────────────────────────╯
```

Note: retrieval ranks the top 5 chunks globally by embedding similarity across *all* ingested files (not per-file), so results can skew toward whichever documents are most semantically similar to the question — it isn't a keyword or title match.

---

## Gitignored Files

These files are never committed:

| File | Reason |
|---|---|
| `.env` | Contains your OpenAI API key |
| `candidate_profile.local.yaml` | Contains your personal profile |
| `data/` | Local SQLite database, ChromaDB vector store, and ingestion manifest |
| `venv/` | Virtual environment |

---

## Scoring Model

Each JD is scored 0–100 against your candidate profile using five weighted components:

| Component | Weight | What it measures |
|---|---|---|
| Tech stack match | 30 | Overlap between job's required tech and your core stack |
| Seniority match | 20 | How well the role level aligns with your current level |
| Domain relevance | 20 | How useful your background is for this specific role |
| AI skill gap | 15 | How much AI/ML expertise is required vs. your level |
| Culture & logistics | 15 | Remote, travel limits, IC vs. management, red flags |

The `match_score` field is the sum of all five component scores.
