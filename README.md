# SUK RAG – Shivaji University Knowledge Assistant

A retrieval-augmented chatbot that answers questions about Shivaji University
from documents (PDFs, web pages, spreadsheets) that an admin uploads.

- **Backend:** FastAPI, ChromaDB (vectors), SQLite (source registry), OpenAI with Gemini fallback
- **Frontend:** React + Vite (public chat UI and an admin dashboard)
- **Languages:** English, Hindi, Marathi (multilingual embeddings + OCR)

## How it works

```
Question ──> hybrid search (vectors + BM25 + boosts) ──> compress context
         ──> build grounded prompt ──> LLM (OpenAI -> Gemini) ──> answer guard ──> answer + citations
```

The assistant answers **only from the retrieved documents**. If they do not
contain the answer it says so instead of guessing. Short follow-up questions
("and the fees?") use the chat history the frontend sends.

## Setup

### 1. Backend

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

### 2. Secrets (`.env`)

```bash
copy .env.example .env           # Linux/macOS: cp .env.example .env
```

Fill in `OPENAI_API_KEY` / `GEMINI_API_KEY`, then create the admin login:

```bash
python scripts/make_admin_credentials.py
```

Paste the printed `ADMIN_PASSWORD_HASH` (keep the single quotes) and
`JWT_SECRET_KEY` lines into `.env`. Without them admin login is disabled and a
warning is printed at startup. **Never commit `.env`** (it is in `.gitignore`).

### 3. Run the backend

```bash
uvicorn backend.main:app --reload
```

API docs: http://127.0.0.1:8000/docs. The database tables are created
automatically on startup.

### 4. Frontend

```bash
cd frontend
copy .env.example .env           # VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:5173 (chat) and http://localhost:5173/admin (dashboard).

### 5. System dependencies (not installable with pip)

- **Tesseract OCR** (scanned PDFs, images): https://github.com/UB-Mannheim/tesseract/wiki
  - install the `eng`, `hin`, `mar` language data, add it to PATH, verify with `tesseract --list-langs`
- **Poppler** (PDF rendering/tables): https://github.com/oschwartz10612/poppler-windows/releases
  - add its `bin` folder to PATH, verify with `pdfinfo -v`

Optional spaCy models: `python -m spacy download en_core_web_sm`

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY`, `GEMINI_API_KEY` | LLM providers | none |
| `ADMIN_USERNAME` | admin login name | `admin` |
| `ADMIN_PASSWORD_HASH`, `JWT_SECRET_KEY` | admin login (from the script above) | none (login disabled) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | admin session length | `480` |
| `CORS_ORIGINS` | allowed frontend origins, comma separated | localhost:5173 |
| `MAX_CONCURRENT_QUERIES` | `/query` requests processed at once | `4` |
| `QUERY_QUEUE_WAIT_SECONDS` | how long an extra request waits for a free slot | `15` |

## Adding knowledge

Log in to the admin dashboard and add URLs, PDFs, CSV/Excel files or ZIPs.
Each becomes a *source*; ingesting a source parses it, splits it into chunks and
stores them in ChromaDB. Sources stay `pending` until you ingest them.

## Project layout

```
backend/
  api/         HTTP routes (query, search, pdf viewer, faq, admin_*)
  auth/        password hashing, JWT, admin dependency
  core/        config, database, answer synthesis + guard, conversation helpers
  search/      hybrid search (vector + BM25 + boosts)
  retrieval/   top-k choice, context compression, temporal ranking
  ingestion/   per-type ingesters (pdf, url, tabular, zip) and the indexer
  registry/    SQLAlchemy models + repository
  services/    LLM service and helpers
  _archive/    superseded code kept for reference (see its README)
frontend/      React app (src/user = chat, src/admin = dashboard)
scripts/       make_admin_credentials.py
tests/         unit tests
data/          runtime data (ignored by git)
```

## Tests

```bash
python -m unittest discover -s tests -t . -v
```
