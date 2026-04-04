"""Pydantic schemas for request/response validation and agent communication."""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ============== Enums ==============

class GoalType(str, Enum):
    COMPARISON = "comparison"
    SINGLE_ENTITY = "single_entity"
    IDEA_ANALYSIS = "idea_analysis"
    MARKET_ANALYSIS = "market_analysis"
    FEATURE_COMPARISON = "feature_comparison"
    PRICING_ANALYSIS = "pricing_analysis"
    POSITIONING_ANALYSIS = "positioning_analysis"
    GAP_ANALYSIS = "gap_analysis"
    FEASIBILITY_ANALYSIS = "feasibility_analysis"
    TREND_ANALYSIS = "trend_analysis"
    USER_ANALYSIS = "user_analysis"
    GTM_STRATEGY = "gtm_strategy"
    INVESTMENT_ANALYSIS = "investment_analysis"
    # Legacy alias
    STARTUP_IDEA = "idea_analysis"


class RunStatusEnum(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    PENDING_USER_REVIEW = "pending_user_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked_by_failed_dependency"
    SKIPPED = "skipped"


class CoordinatorAction(str, Enum):
    PROCEED = "proceed"
    RETRY = "retry"
    SKIP = "skip"
    REPLAN = "replan"
    ESCALATE = "escalate"
    COMPLETE = "complete"
    FAIL = "fail"


# ============== Planner Schemas ==============

class PlannedTask(BaseModel):
    """A single task in the planned DAG."""
    id: str = Field(..., description="Unique task identifier (e.g., T1, T2)")
    task: str = Field(..., description="Clear task description")
    depends_on: List[str] = Field(default_factory=list, description="List of task IDs this depends on")
    reason: str = Field(..., description="Why this task is needed")
    
    @validator('task')
    def task_not_vague(cls, v):
        vague_words = ['analyze', 'study', 'look at', 'check', 'review']
        if len(v.split()) < 4:
            raise ValueError("Task description too vague - needs more detail")
        return v


class GoalClassification(BaseModel):
    """Goal classification result."""
    type: GoalType
    domain: str = Field(..., description="Domain like fitness, fintech, SaaS, etc.")
    entities: List[str] = Field(default_factory=list, description="Extracted entities")
    focus: str = Field(..., description="Main focus of analysis")
    has_ai_component: bool = Field(default=False, description="Whether AI/tech differentiation exists")
    target_users: Optional[str] = Field(default=None, description="Target user segment if detected")


class TaskPlan(BaseModel):
    """Complete task plan from planner agent."""
    tasks: List[PlannedTask] = Field(..., min_length=4, max_length=5)
    goal_type: GoalType
    classification: Optional[GoalClassification] = None
    
    @validator('tasks')
    def validate_dag(cls, tasks):
        task_ids = {t.id for t in tasks}
        for task in tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    raise ValueError(f"Task {task.id} depends on unknown task {dep}")
        # Check for cycles using DFS
        def has_cycle(task_id, visited, rec_stack, adj):
            visited.add(task_id)
            rec_stack.add(task_id)
            for neighbor in adj.get(task_id, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack, adj):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(task_id)
            return False
        
        adj = {t.id: [] for t in tasks}
        for task in tasks:
            for dep in task.depends_on:
                adj[dep].append(task.id)
        
        visited = set()
        for task in tasks:
            if task.id not in visited:
                if has_cycle(task.id, visited, set(), adj):
                    raise ValueError("Task plan contains cycles")
        return tasks


# ============== Executor Schemas ==============

class SearchQuery(BaseModel):
    """Search query for Tavily."""
    query: str
    search_depth: Literal["basic", "advanced"] = "basic"
    max_results: int = 5


class SearchResult(BaseModel):
    """A single search result."""
    title: str
    url: str
    content: str
    score: float = 0.0


class AnalysisCaseType(str, Enum):
    """Type of analysis being performed (from MASTER GREYBOX PROMPT)."""
    STARTUP_IDEA = "startup_idea"
    SINGLE_COMPANY = "single_company"
    COMPETITOR_COMPARISON = "competitor_comparison"


class VerdictType(str, Enum):
    """Final verdict options (MASTER GREYBOX PROMPT requirement)."""
    YES = "YES"
    NO = "NO"
    CONDITIONAL = "CONDITIONAL"


class ComparisonRow(BaseModel):
    """Single row in comparison table (MASTER GREYBOX structured output)."""
    attribute: str
    entity_a: str
    entity_b: Optional[str] = None
    winner: Optional[str] = Field(default=None, description="Explicit winner for this attribute")
    explanation: Optional[str] = Field(default=None, description="Why this winner")


class ComparisonTable(BaseModel):
    """Structured comparison table (MANDATORY per MASTER GREYBOX PROMPT)."""
    rows: List[ComparisonRow] = Field(..., min_length=3, description="At least 3 comparison dimensions")
    case_type: AnalysisCaseType
    
    @validator('rows')
    def validate_comparisons(cls, v, values):
        """Ensure comparisons are meaningful."""
        if not v:
            raise ValueError("Comparison table cannot be empty - MANDATORY per MASTER GREYBOX")
        # Check no generic attributes
        generic_attrs = ["general", "overall", "other"]
        for row in v:
            if row.attribute.lower() in generic_attrs:
                raise ValueError(f"Generic attribute '{row.attribute}' not allowed - be specific")
        return v


class FinalVerdict(BaseModel):
    """Final decision (MANDATORY per MASTER GREYBOX PROMPT)."""
    verdict: VerdictType
    strong_arguments: List[str] = Field(..., min_length=2, max_length=3, 
                                        description="2-3 strong supporting arguments")
    major_risk: str = Field(..., min_length=10, description="Single critical failure point")
    conditions_for_success: Optional[List[str]] = Field(default=None,
                                                         description="Required if verdict is CONDITIONAL")
    
    @validator('conditions_for_success')
    def conditional_requires_conditions(cls, v, values):
        """If verdict is CONDITIONAL, must have conditions."""
        if values.get('verdict') == VerdictType.CONDITIONAL and not v:
            raise ValueError("CONDITIONAL verdict MUST include conditions_for_success")
        return v


class GreyboxTaskOutput(BaseModel):
    """
    McKinsey-grade task output following MASTER GREYBOX PROMPT structure.
    EVERY task must follow this exact structure.
    """
    # Required sections (per MASTER GREYBOX PROMPT)
    summary: str = Field(..., min_length=50, max_length=300, 
                        description="2-3 crisp sentences maximum")
    
    key_findings: List[str] = Field(..., min_length=3, 
                                   description="Specific bullets, NOT generic")
    
    comparison: ComparisonTable = Field(..., 
                                       description="MANDATORY comparison - even for single entity")
    
    data_points: List[str] = Field(default_factory=list,
                                  description="Real data OR 'No reliable data available'")
    
    limitations: List[str] = Field(..., min_length=1,
                                  description="What data is missing, assumptions made")
    
    key_insight: str = Field(..., min_length=20,
                            description="ONE sharp, NON-OBVIOUS insight (NOT generic)")
    
    strategic_implication: str = Field(..., min_length=20,
                                      description="Clear action: DO X because Y")
    
    # Additional required fields
    biggest_risk: str = Field(..., min_length=15,
                            description="Single critical failure point")
    
    competitors_identified: Dict[str, List[str]] = Field(
        default_factory=lambda: {"direct": [], "indirect": []},
        description="Real company names only - NO placeholders"
    )
    
    sources: List[str] = Field(default_factory=list,
                              description="URLs from search results")
    
    # Confidence (dynamically calculated - NOT hardcoded)
    confidence: float = Field(ge=0.0, le=1.0,
                            description="0.0-1.0 based on data quality, NOT hardcoded")
    
    confidence_factors: Optional[Dict[str, float]] = Field(
        default=None,
        description="Breakdown: search_quality, data_availability, source_credibility, comparison_depth"
    )
    
    # Optional for final task only
    final_verdict: Optional[FinalVerdict] = Field(default=None,
                                                 description="Required for final task only")
    
    @validator('key_insight')
    def insight_not_generic(cls, v):
        """Enforce anti-generic rule from MASTER GREYBOX PROMPT."""
        generic_phrases = [
            "market is growing",
            "competition is high",
            "huge opportunity",
            "shows promise",
            "has potential",
            "could work",
            "industry is expanding",
            "competitive landscape",
            "significant growth"
        ]
        v_lower = v.lower()
        for phrase in generic_phrases:
            if phrase in v_lower:
                raise ValueError(
                    f"Generic phrase '{phrase}' detected in key_insight. "
                    f"MASTER GREYBOX PROMPT requires sharp, non-obvious insights."
                )
        # Must have "SO WHAT" character - check for action words
        action_words = ["must", "should", "indicates", "suggests", "reveals", "means", "requires"]
        if not any(word in v_lower for word in action_words):
            raise ValueError("key_insight must include SO WHAT implication (action/conclusion)")
        return v
    
    @validator('strategic_implication')
    def implication_actionable(cls, v):
        """Ensure strategic implication is actionable."""
        if len(v.split()) < 5:
            raise ValueError("strategic_implication too vague - needs clear action")
        # Should contain action verbs
        action_verbs = ["focus", "avoid", "prioritize", "build", "target", "invest", "delay", "pivot"]
        if not any(verb in v.lower() for verb in action_verbs):
            raise ValueError("strategic_implication must contain clear action verb")
        return v
    
    @validator('competitors_identified')
    def competitors_real(cls, v):
        """Ensure competitors are real companies, not placeholders."""
        blocked_terms = ["platform a", "platform b", "company x", "company y", 
                        "competitor 1", "competitor 2", "solution a", "solution b",
                        "ngo", "non-profit", "organization"]
        all_competitors = v.get("direct", []) + v.get("indirect", [])
        for comp in all_competitors:
            comp_lower = comp.lower()
            if any(blocked in comp_lower for blocked in blocked_terms):
                raise ValueError(
                    f"Placeholder/generic competitor '{comp}' detected. "
                    f"MASTER GREYBOX PROMPT requires real company names only."
                )
        return v


class ExecutorOutput(BaseModel):
    """Legacy executor output - will be deprecated in favor of GreyboxTaskOutput."""
    task_id: str
    summary: str = Field(..., description="2-3 sentence executive summary")
    key_findings: List[str] = Field(default_factory=list, description="Key findings with data")
    comparisons: List[Dict[str, Any]] = Field(default_factory=list, description="Explicit comparisons")
    insights: List[str] = Field(default_factory=list, description="Strategic insights with WHY and SO WHAT")
    data_points: List[str] = Field(default_factory=list, description="Specific facts and figures")
    limitations: List[str] = Field(default_factory=list, description="Data gaps or uncertainties")
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    feature_matrix: Optional[Dict[str, Any]] = Field(default=None, description="Feature parity matrix if applicable")
    raw_data: Optional[Dict[str, Any]] = None


# ============== Validator Schemas ==============

class ValidationResult(BaseModel):
    """Output from validator agent."""
    valid: bool
    score: float = Field(ge=0, le=10)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    critique: Optional[str] = None


# ============== Coordinator Schemas ==============

class CoordinatorDecision(BaseModel):
    """Decision made by coordinator."""
    action: CoordinatorAction
    reason: str
    retry_count: int = 0
    prompt_update: Optional[str] = None
    task_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============== API Request/Response Schemas ==============

class AnalysisRequest(BaseModel):
    """Request to start analysis."""
    goal: str = Field(..., min_length=5, max_length=500)
    
    @validator('goal')
    def goal_not_too_vague(cls, v):
        if len(v.split()) < 2:
            raise ValueError("Goal is too vague. Please provide more detail.")
        return v


class AnalysisResponse(BaseModel):
    """Response after starting analysis."""
    run_id: str
    status: str
    message: str


class TaskResponse(BaseModel):
    """Task information for API responses."""
    id: str
    task_description: str
    status: str
    retries: int
    output: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    validation_score: Optional[float] = None
    error: Optional[str] = None


class RunStatusResponse(BaseModel):
    """Full run status response."""
    run_id: str
    goal: str
    goal_type: Optional[str] = None
    status: str
    current_task_id: Optional[str] = None
    tasks: List[TaskResponse] = Field(default_factory=list)
    progress: float = 0.0
    cost: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class RunResultResponse(BaseModel):
    """Final result response."""
    run_id: str
    goal: str
    status: str
    final_report: Optional[Dict[str, Any]] = None
    tasks: List[TaskResponse] = Field(default_factory=list)
    total_cost: Optional[Dict[str, Any]] = None


class ApprovalRequest(BaseModel):
    """Request to approve/reject a run."""
    approved: bool
    feedback: Optional[str] = None
    edits: Optional[Dict[str, Any]] = None


class LogEntry(BaseModel):
    """Log entry for frontend display."""
    id: int
    agent: str
    level: str
    message: str
    task_id: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime


class LogsResponse(BaseModel):
    """Logs response."""
    run_id: str
    logs: List[LogEntry]


# ============== Agent Communication Schemas ==============

class AgentMessage(BaseModel):
    """Message passed between agents."""
    from_agent: str
    to_agent: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentContext(BaseModel):
    """Context passed to agents."""
    run_id: str
    goal: str
    goal_type: Optional[GoalType] = None
    current_task: Optional[PlannedTask] = None
    completed_tasks: List[str] = Field(default_factory=list)
    task_outputs: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    total_cost: float = 0.0
