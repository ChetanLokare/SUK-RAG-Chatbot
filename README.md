# 🎓 SUK RAG – Shivaji University Knowledge Assistant

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector%20store-orange)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

A retrieval-augmented generation (RAG) chatbot that answers questions about **Shivaji University** using documents (PDFs, web pages, spreadsheets, ZIP archives) that an administrator uploads. Answers are grounded in the retrieved documents and come with citations that open the original source.

> The assistant answers **only from the retrieved documents**. If the documents do not contain the answer, it says so instead of guessing.

---

## 📑 Table of Contents

- [Features](#-features)
- [How It Works](#-how-it-works)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Configuration](#-configuration)
- [Adding Knowledge](#-adding-knowledge)
- [API Overview](#-api-overview)
- [Running the Tests](#-running-the-tests)
- [Security Notes](#-security-notes)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)
- [Author](#-author)

---

## ✨ Features

**For students and visitors**

- 💬 Chat interface for asking questions about the university
- 🌐 Multilingual: **English, Hindi and Marathi**
- 🔗 Follow-up questions work (for example, "and the fees?") using the chat history
- 📎 Citations with page numbers that open the source document
- 🛡️ Grounded answers with an answer guard that avoids made-up facts

**For administrators**

- 🔐 Secure admin login (bcrypt password hash + JWT, with login lockout after repeated failures)
- 📥 Add knowledge from URLs, PDFs, CSV/Excel files and ZIP archives
- 🗂️ Source registry with categories, approve/disable/delete and bulk actions
- ⚙️ Per-source ingestion, bulk ingestion and refresh scheduling
- 📊 Vector store stats, delete and rebuild tools
- 📤 Export the source list as JSON or TXT

**Under the hood**

- 🔎 Hybrid search: vector similarity + BM25 keyword scoring + metadata boosts
- 🧠 Multilingual embeddings and OCR for scanned documents
- 🕒 Temporal ranking so newer notices and results are preferred
- 🧩 Context compression and adaptive top-k retrieval
- 🔁 LLM fallback: OpenAI first, Google Gemini if it fails
- 🚦 Concurrency limit on the heavy `/query` pipeline

---

## 🧠 How It Works

```
Question ──> hybrid search (vectors + BM25 + boosts) ──> compress context
         ──> build grounded prompt ──> LLM (OpenAI -> Gemini) ──> answer guard ──> answer + citations
```

1. **Follow-up handling:** short follow-ups borrow the previous question for *search only*; the LLM still sees the user's real question.
2. **Retrieval:** the query is run against ChromaDB (vector search) and re-scored with BM25 and section/source/query boosts.
3. **Compression:** the best chunks are trimmed to a small, relevant context.
4. **Generation:** a grounded prompt is sent to OpenAI (`gpt-4o-mini`), with automatic fallback to Gemini (`gemini-2.5-flash`).
5. **Answer guard:** weak or empty answers get one grounded retry, then fall back to sentences extracted from the context, and finally to a fixed "please check the official website" message. It never falls back to inventing facts.
6. **Citations:** unique sources and page numbers are returned alongside the answer.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, Uvicorn |
| Vector database | ChromaDB |
| Registry database | SQLite via SQLAlchemy |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers) |
| Keyword search | `rank-bm25` |
| LLM providers | OpenAI (`gpt-4o-mini`), Google Gemini (`gemini-2.5-flash`) |
| Document parsing | pdfplumber, pdf2image, OpenCV, pytesseract (OCR), pandas, openpyxl |
| Web crawling | requests, BeautifulSoup, lxml, Playwright (for JavaScript-heavy pages) |
| Knowledge graph | NetworkX |
| Auth | PyJWT, bcrypt |
| Frontend | React 19, Vite 7, React Router 7, react-markdown, react-pdf |

---

## 📁 Project Structure

```text
SUK-RAG-Chatbot/
├── backend/
│   ├── api/          # HTTP routes: query, search, pdf viewer, faq, admin_*
│   ├── auth/         # password hashing, JWT, admin dependency
│   ├── citation/     # locate cited passages inside source documents
│   ├── core/         # config, database, Chroma client, answer synthesis + guard
│   ├── crawler/      # site knowledge mapping
│   ├── graph/        # entity extraction and university knowledge graph
│   ├── ingestion/    # per-type ingesters (pdf, url, tabular, zip), chunkers, indexer
│   ├── registry/     # SQLAlchemy models + repository (source registry)
│   ├── retrieval/    # adaptive top-k, context compression, temporal ranking
│   ├── search/       # hybrid search (vector + BM25 + boosts)
│   ├── services/     # LLM service, FAQ, memory, timeline, table helpers
│   ├── utils/        # query normalization, language detection, file resolver
│   ├── _archive/     # superseded code kept for reference (see its README)
│   └── main.py       # FastAPI application entry point
├── frontend/
│   └── src/
│       ├── user/     # public chat UI
│       └── admin/    # admin login and dashboard
├── scripts/
│   └── make_admin_credentials.py
├── tests/            # unit tests
├── data/             # runtime data (created automatically, ignored by git)
├── .env.example
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- An **OpenAI** and/or **Google Gemini** API key
- **Git**

### 1. Clone the repository

```bash
git clone https://github.com/ChetanLokare/SUK-RAG-Chatbot.git
cd SUK-RAG-Chatbot
```

### 2. Backend setup

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

> The first run downloads the multilingual embedding model, so it can take a few minutes. `torch` and `sentence-transformers` are large installs.

If you want to crawl JavaScript-rendered pages, install the Playwright browser once:

```bash
playwright install chromium
```

### 3. Secrets (`.env`)

```bash
copy .env.example .env           # Linux/macOS: cp .env.example .env
```

Fill in `OPENAI_API_KEY` and/or `GEMINI_API_KEY`, then create the admin login:

```bash
python scripts/make_admin_credentials.py
```

Paste the printed `ADMIN_PASSWORD_HASH` (**keep the single quotes**, because the hash contains `$` characters) and `JWT_SECRET_KEY` lines into `.env`.

Without them, admin login is disabled and a warning is printed at startup.

### 4. Run the backend

```bash
uvicorn backend.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

The database tables are created automatically on startup.

### 5. Run the frontend

```bash
cd frontend
copy .env.example .env           # Linux/macOS: cp .env.example .env
npm install
npm run dev
```

Open:

- Chat: http://localhost:5173
- Admin dashboard: http://localhost:5173/admin

### 6. System dependencies (not installable with pip)

These are only needed for OCR and PDF rendering of scanned documents.

**Tesseract OCR** (scanned PDFs and images): https://github.com/UB-Mannheim/tesseract/wiki

- Install the `eng`, `hin` and `mar` language data
- Add it to your `PATH`
- Verify with `tesseract --list-langs`

**Poppler** (PDF rendering): https://github.com/oschwartz10612/poppler-windows/releases

- Add its `bin` folder to your `PATH`
- Verify with `pdfinfo -v`

On Linux/macOS, install both with your package manager (for example `apt install tesseract-ocr poppler-utils` or `brew install tesseract poppler`).

---

## ⚙️ Configuration

### Backend (`.env` in the project root)

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | Primary LLM provider | none |
| `GEMINI_API_KEY` | Fallback LLM provider | none |
| `ADMIN_USERNAME` | Admin login name | `admin` |
| `ADMIN_PASSWORD_HASH` | bcrypt hash of the admin password (from the script) | none (login disabled) |
| `JWT_SECRET_KEY` | Secret used to sign login tokens | none (login disabled) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Admin session length | `480` |
| `CORS_ORIGINS` | Allowed frontend origins, comma separated | `http://localhost:5173,http://127.0.0.1:5173` |
| `MAX_CONCURRENT_QUERIES` | `/query` requests processed at once | `4` |
| `QUERY_QUEUE_WAIT_SECONDS` | How long an extra request waits for a free slot | `15` |
| `ENVIRONMENT` | `development` prints extra startup debug info | `development` |

Tip: on a weak, CPU-only machine, lower `MAX_CONCURRENT_QUERIES` to `1` or `2`.

### Frontend (`frontend/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_URL` | URL of the backend API | `http://localhost:8000` |

---

## 📚 Adding Knowledge

1. Log in at `/admin` with your admin credentials.
2. Add a **source**: a URL, PDF, CSV/Excel file, or ZIP archive.
3. Choose a **category**: `general`, `academics`, `departments`, `admissions`, `exams`, `results`, `notices`, `events`, `scholarships`, `research`, or `library`.
4. **Ingest** the source. It is parsed, split into chunks and stored in ChromaDB. Sources stay `pending` until you ingest them.
5. Ask a question on the chat page and check the citations.

Use the vector panel in the dashboard to view stats, delete entries, or rebuild the index.

---

## 🔌 API Overview

Full interactive documentation is available at `/docs` when the backend is running.

**Public**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/query` | Ask a question (`question`, optional `category`, `language`, `top_k`, `history`) |
| `GET` | `/search/` | Search the knowledge base directly |
| `GET` | `/faq/` | List generated FAQs |
| `GET` | `/faq/{source_id}` | FAQs for one source |
| `GET` | `/pdf/{filename}` | Open a cited source document |
| `GET` | `/health` | Health check |

**Admin (requires login)**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/admin/auth/login` | Log in and receive a token |
| `GET` | `/admin/auth/me` | Check the current session |
| `GET` | `/admin/sources/` | List sources |
| `POST` | `/admin/sources/{id}/ingest` | Ingest one source |
| `POST` | `/admin/sources/bulk/{approve,disable,delete,category,ingest}` | Bulk actions |
| `GET` | `/admin/sources/export/{json,txt}` | Export the source list |
| `POST` | `/admin/upload/{url,pdf,csv,excel,zip}` | Add new sources |
| `GET` | `/admin/vector/stats` | Vector store statistics |
| `DELETE` | `/admin/vector/delete` | Delete vector entries |
| `POST` | `/admin/vector/rebuild` | Rebuild the vector index |

**Example**

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the admission requirements?", "category": "admissions"}'
```

---

## 🧪 Running the Tests

```bash
python -m unittest discover -s tests -t . -v
```

The tests cover the answer guard, conversation handling and query normalization.

---

## 🔐 Security Notes

- Never commit `.env`. It is listed in `.gitignore`; only `.env.example` is tracked.
- Admin passwords are stored as bcrypt hashes, never in plain text.
- Failed admin logins are rate limited per client IP (5 failures, then a 5-minute lockout).
- Set `CORS_ORIGINS` to your real frontend domain(s) in production.
- Serve the app over **HTTPS** in production.
- Keep your API keys private and rotate them if they are ever exposed.
- Uploaded documents and the vector database live in `data/`, which is excluded from git.

---

## 🩺 Troubleshooting

| Problem | Fix |
|---|---|
| Admin login is disabled | Set `ADMIN_PASSWORD_HASH` and `JWT_SECRET_KEY` in `.env`, then restart |
| Login fails with a valid password | Make sure the hash in `.env` is wrapped in **single quotes** |
| `tesseract is not recognized` | Install Tesseract and add it to `PATH`, then reopen the terminal |
| `pdfinfo` not found / PDF pages not rendering | Install Poppler and add its `bin` folder to `PATH` |
| CORS errors in the browser | Add your frontend URL to `CORS_ORIGINS` |
| "The system is busy right now" | Raise `MAX_CONCURRENT_QUERIES` or `QUERY_QUEUE_WAIT_SECONDS` |
| Answers say the information was not found | Make sure the relevant source is **ingested**, not just `pending` |
| First startup is slow | The embedding model is being downloaded once |

---

## 🔮 Roadmap

- Automated tests for the API endpoints and ingestion pipeline
- Docker setup for one-command deployment
- Persistent, distributed rate limiting
- Scheduled automatic re-crawling of sources
- Answer feedback (thumbs up/down) from users
- Admin analytics for popular and unanswered questions

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Chetan Lokare**

- GitHub: [@ChetanLokare](https://github.com/ChetanLokare)
- LinkedIn: [Chetan Lokare](https://www.linkedin.com/in/chetan-lokare-50ba65175)

---

*Built as a learning project using FastAPI, ChromaDB and React.*
