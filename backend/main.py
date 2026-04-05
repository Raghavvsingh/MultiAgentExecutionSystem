"""OrchestAI - Multi-Agent Task Execution System for Competitive Analysis."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db, check_db_connection
from backend.routes.analysis import router as analysis_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting OrchestAI...")

    # Check database connection
    db_ok = check_db_connection()
    if db_ok:
        logger.info("Database connection successful")
        init_db()
    else:
        logger.error("Database connection failed!")

    yield

    # Shutdown
    logger.info("Shutting down OrchestAI...")


app = FastAPI(
    title="OrchestAI",
    description="Multi-Agent Task Execution System for Competitive Analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# ✅ CORS FIX (important for Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all (safe for demo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "OrchestAI",
        "version": "1.0.0",
        "description": "Multi-Agent Task Execution System for Competitive Analysis",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    db_ok = check_db_connection()
    return {
        "status": "healthy" if db_ok else "unhealthy",
        "database": "connected" if db_ok else "disconnected",
    }


if __name__ == "__main__":
    import uvicorn

    # ✅ FIXED path (VERY IMPORTANT)
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=3001,
        reload=settings.debug,
        log_level="info",
    )
