"""SQLAlchemy database models for OrchestAI."""

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from backend.database import Base


class RunStatus(str, enum.Enum):
    """Status of an analysis run."""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    PENDING_USER_REVIEW = "pending_user_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    """Status of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked_by_failed_dependency"
    SKIPPED = "skipped"


class Run(Base):
    """Analysis run record."""
    __tablename__ = "runs"
    
    id = Column(String(36), primary_key=True)
    goal = Column(Text, nullable=False)
    goal_type = Column(String(50))  # comparison, single_entity, startup_idea
    status = Column(String(30), default=RunStatus.PENDING.value)
    current_task_id = Column(String(50), nullable=True)
    
    # Results
    final_report = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    tasks = relationship("Task", back_populates="run", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="run", cascade="all, delete-orphan")
    cost_tracking = relationship("CostTracking", back_populates="run", uselist=False, cascade="all, delete-orphan")


class Task(Base):
    """Task record within a run."""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), nullable=False)  # Task identifier like T1, T2
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    
    # Task details
    task_description = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    depends_on = Column(JSON, default=list)  # List of task IDs
    order_index = Column(Integer, default=0)
    
    # Execution state
    status = Column(String(40), default=TaskStatus.PENDING.value)
    retries = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Output
    output = Column(JSON, nullable=True)
    sources = Column(JSON, default=list)
    confidence = Column(Float, nullable=True)
    
    # Validation
    validation_score = Column(Float, nullable=True)
    validation_issues = Column(JSON, default=list)
    
    # Error tracking
    error = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    run = relationship("Run", back_populates="tasks")


class Log(Base):
    """Log entry for observability."""
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(50), nullable=True)
    
    # Log details
    agent = Column(String(50), nullable=False)
    level = Column(String(20), default="info")  # debug, info, warning, error
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    
    # Metrics
    latency_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    run = relationship("Run", back_populates="logs")


class CostTracking(Base):
    """Cost tracking for a run."""
    __tablename__ = "cost_tracking"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Token usage
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Costs
    estimated_cost_usd = Column(Float, default=0.0)
    
    # Search API usage
    tavily_searches = Column(Integer, default=0)
    
    # Metadata
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    run = relationship("Run", back_populates="cost_tracking")
