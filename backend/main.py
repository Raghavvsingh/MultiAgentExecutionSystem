"""OrchestAI - Multi-Agent Task Execution System for Competitive Analysis."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db, check_db_connection
from backend.routes.analysis import router as analysis_router

# ----------------------------
# Logging Configuration
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ----------------------------
# Lifespan (Startup / Shutdown)
# ----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting OrchestAI...")

    # Database check
    try:
        db_ok = check_db_connection()
        if db_ok:
            logger.info("✅ Database connection successful")
            init_db()
        else:
            logger.error("❌ Database connection failed")
    except Exception as e:
        logger.error(f"DB Error: {e}")

    yield

    logger.info("🛑 Shutting down OrchestAI...")

# ----------------------------
# FastAPI App
# ----------------------------
app = FastAPI(
    title="OrchestAI",
    description="Multi-Agent Task Execution System for Competitive Analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# ----------------------------
# CORS (IMPORTANT for Vercel)
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for production restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Routes
# ----------------------------
app.include_router(analysis_router)

# ----------------------------
# Health + Root
# ----------------------------
@app.get("/")
async def root():
    return {
        "name": "OrchestAI",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    try:
        db_ok = check_db_connection()
        return {
            "status": "healthy" if db_ok else "unhealthy",
            "database": "connected" if db_ok else "disconnected",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# ENTRY POINT (LOCAL ONLY)
# ----------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        log_level="info",
    )
