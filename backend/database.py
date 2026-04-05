"""Database connection and session management with SQLite fallback."""

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
import logging
import os
import time

from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Try NeonDB first, fallback to SQLite if it fails
database_url = settings.database_url
use_sqlite = False

if database_url and "neon" in database_url.lower():
    # Convert postgres:// to postgresql:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Remove channel_binding parameter for compatibility
    if "channel_binding=require" in database_url:
        database_url = database_url.replace("&channel_binding=require", "").replace("?channel_binding=require&", "?").replace("?channel_binding=require", "")
    
    # Test connection before using
    try:
        test_engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to NeonDB successfully")
    except Exception as e:
        logger.warning(f"NeonDB connection failed: {e}. Falling back to SQLite.")
        use_sqlite = True
else:
    use_sqlite = True

if use_sqlite:
    # Use SQLite for local development
    sqlite_path = os.path.join(os.path.dirname(__file__), "orchestai.db")
    database_url = f"sqlite:///{sqlite_path}"
    logger.info(f"Using SQLite database: {sqlite_path}")

# Create engine based on database type
if use_sqlite:
    engine = create_engine(
        database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},  # SQLite specific
    )
else:
    engine = create_engine(
        database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,  # Recycle connections every 5 minutes to avoid stale connections
        pool_timeout=30,  # Timeout for getting a connection from the pool
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    )

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


@contextmanager
def get_db_session(max_retries=3, retry_delay=1):
    """Get database session with retry logic for connection errors."""
    # Phase 1: Establish connection with retries
    session = None
    last_error = None
    
    for attempt in range(max_retries):
        session = SessionLocal()
        try:
            # Test the connection
            session.execute(text("SELECT 1"))
            break  # Connection successful
        except (OperationalError, DBAPIError) as e:
            session.close()
            last_error = e
            error_msg = str(e).lower()
            
            # Check if it's a connection-related error worth retrying
            if any(x in error_msg for x in ["connection", "closed", "terminated", "server"]):
                logger.warning(f"Database connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    engine.dispose()  # Dispose the pool to force new connections
                    continue
            raise
    else:
        # If we exhausted all retries, raise the last error
        if last_error:
            logger.error(f"Database connection failed after {max_retries} retries: {last_error}")
            raise last_error
    
    # Phase 2: Use session (no retry around yield)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")


def check_db_connection():
    """Check database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def is_using_sqlite():
    """Check if using SQLite fallback."""
    return use_sqlite
