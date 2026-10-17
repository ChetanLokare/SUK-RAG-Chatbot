# backend/main.py

import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# CORE IMPORTS
# ============================================================

from backend.core.database import init_db
from backend.core.config import (
    BASE_DIR,
    SQLITE_DB_PATH,
    CHROMA_DIR,
    CSV_DIR,
    PDF_DIR,
    EXCEL_DIR,
    ZIP_DIR,
    CORS_ORIGINS,
)
from backend.auth.security import auth_is_configured

# ============================================================
# API ROUTERS
# ============================================================

from backend.api import (
    admin_auth,
    admin_sources,
    admin_uploads,
    admin_vector,
)

from backend.api import query
from backend.api.faq import router as faq_router
from backend.api.search import router as search_router
from backend.api.pdf_viewer import router as pdf_router


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown lifecycle.
    """

    print("\n==============================")
    print("🚀 SUK RAG SYSTEM STARTING")
    print("==============================")

    # --------------------------------------------------------
    # Initialize database
    # --------------------------------------------------------

    init_db()

    if not auth_is_configured():
        print("⚠️  ADMIN AUTH NOT CONFIGURED: admin login is disabled.")
        print("    Set ADMIN_PASSWORD_HASH and JWT_SECRET_KEY in .env")
        print("    (run: python scripts/make_admin_credentials.py)")

    # --------------------------------------------------------
    # Debug information
    # --------------------------------------------------------

    print("📂 BASE_DIR:", BASE_DIR.resolve())
    print("🗄 SQLITE_DB_PATH:", SQLITE_DB_PATH.resolve())
    print("📦 CHROMA_DIR:", CHROMA_DIR.resolve())
    print("📑 CSV_DIR:", CSV_DIR.resolve())
    print("📄 PDF_DIR:", PDF_DIR.resolve())
    print("📊 EXCEL_DIR:", EXCEL_DIR.resolve())
    print("🗜 ZIP_DIR:", ZIP_DIR.resolve())
    print("🔧 WORKING DIR:", os.getcwd())

    print("✅ Startup complete\n")

    yield

    print("\n🛑 SUK RAG SYSTEM SHUTDOWN\n")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="SUK RAG System",
    description="Shivaji University Knowledge Assistant",
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================================
# CORS (FOR FRONTEND / ADMIN PANEL)
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # set CORS_ORIGINS in .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

# Admin APIs
app.include_router(admin_auth.router)
app.include_router(admin_sources.router)
app.include_router(admin_uploads.router)
app.include_router(admin_vector.router)

# Public APIs
app.include_router(query.router)
app.include_router(search_router)
app.include_router(faq_router)

# Document viewer (citations)
app.include_router(pdf_router)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health", tags=["System"])
def health_check():
    """
    System health endpoint.
    Useful for uptime monitoring.
    """

    return {
        "status": "ok",
        "database": str(SQLITE_DB_PATH.resolve()),
        "chroma_dir": str(CHROMA_DIR.resolve()),
        "working_dir": os.getcwd(),
    }