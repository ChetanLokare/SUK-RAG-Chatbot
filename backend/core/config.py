# backend/core/config.py

from pathlib import Path
import os

from dotenv import load_dotenv


# ======================================================
# PROJECT ROOT (ABSOLATE + SAFE)
# ======================================================

# backend/core/config.py → go up 3 levels → project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load secrets from .env files (never commit these).
# Real environment variables always win over .env values.
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "backend" / ".env")


# ======================================================
# APP INFO
# ======================================================

APP_NAME = "SUK RAG System"


# ======================================================
# DATA ROOT (ALWAYS ABSOLUTE)
# ======================================================

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ======================================================
# FILE STORAGE DIRECTORIES
# ======================================================

PDF_DIR = DATA_DIR / "pdfs"
EXCEL_DIR = DATA_DIR / "excels"
CSV_DIR = DATA_DIR / "csvs"
ZIP_DIR = DATA_DIR / "zips"
DOWNLOAD_DIR = DATA_DIR / "downloads"
CHROMA_DIR = DATA_DIR / "chroma"
LOGS_DIR = DATA_DIR / "logs"

for folder in [
    PDF_DIR,
    EXCEL_DIR,
    CSV_DIR,
    ZIP_DIR,
    DOWNLOAD_DIR,
    CHROMA_DIR,
    LOGS_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)


# ======================================================
# DATABASE (ABSOLUTE + SAFE)
# ======================================================

SQLITE_DB_PATH = DATA_DIR / "suk_rag.db"

# Always resolve to absolute path
DATABASE_URL = f"sqlite:///{SQLITE_DB_PATH.resolve()}"


# ======================================================
# CRAWLER SETTINGS
# ======================================================

MAX_CRAWL_DEPTH = 3
CRAWL_RATE_LIMIT_SECONDS = 0.5
DOMAIN_RESTRICT = True


# ======================================================
# LLM KEYS
# ======================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


# ======================================================
# ADMIN AUTH (all values come from .env)
# ======================================================

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# bcrypt hash of the admin password.
# Generate with:  python scripts/make_admin_credentials.py
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

# Secret used to sign login tokens (JWT). Keep it long and random.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Login brute-force protection (per client IP, in memory)
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 300


# ======================================================
# CORS (comma-separated list of allowed frontend origins)
# ======================================================

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]


# ======================================================
# ENVIRONMENT
# ======================================================

ENV = os.getenv("ENVIRONMENT", "development")
DEBUG = ENV.lower() == "development"


# ======================================================
# QUERY CONCURRENCY
# ======================================================

# How many /query requests may run the heavy pipeline at once.
# Extra requests wait up to QUERY_QUEUE_WAIT_SECONDS before getting a
# "busy" reply. Lower MAX_CONCURRENT_QUERIES on a weak CPU-only machine.
MAX_CONCURRENT_QUERIES = max(1, int(os.getenv("MAX_CONCURRENT_QUERIES", "4")))
QUERY_QUEUE_WAIT_SECONDS = float(os.getenv("QUERY_QUEUE_WAIT_SECONDS", "15"))


# ======================================================
# STARTUP DEBUG (CRITICAL FOR PATH ISSUES)
# ======================================================

if DEBUG:
    print("\n===== SUK RAG CONFIG LOADED =====")
    print("BASE_DIR:", BASE_DIR.resolve())
    print("DATA_DIR:", DATA_DIR.resolve())
    print("SQLITE_DB_PATH:", SQLITE_DB_PATH.resolve())
    print("CHROMA_DIR:", CHROMA_DIR.resolve())
    print("==================================\n")
