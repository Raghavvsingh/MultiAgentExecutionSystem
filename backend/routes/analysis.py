"""API Routes for OrchestAI."""

import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import logging
import threading

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update, and_

from models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    RunStatusResponse,
    RunResultResponse,
    ApprovalRequest,
    TaskResponse,
    LogsResponse,
    LogEntry,
    RunStatusEnum,
)
from models.db_models import Run, Task, Log, CostTracking, TaskStatus, RunStatus
from database import get_db_session
from agents.coordinator import CoordinatorAgent
from services.cost_tracker import get_cost_tracker, remove_cost_tracker

logger = logging.getLogger(__name__)

# Thread pool for non-blocking database operations
_db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="db_worker")

router = APIRouter(prefix="/api", tags=["analysis"])

# Store active coordinators
active_coordinators: Dict[str, CoordinatorAgent] = {}

# WebSocket connections for live updates
ws_connections: Dict[str, List[WebSocket]] = {}


async def broadcast_to_run(run_id: str, message: Dict[str, Any]):
    """Broadcast message to all WebSocket connections for a run."""
    if run_id in ws_connections:
        dead_connections = []
        for ws in ws_connections[run_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        
        for ws in dead_connections:
            ws_connections[run_id].remove(ws)


def save_run_state_sync(coordinator: CoordinatorAgent):
    """Save coordinator state to database (sync version)."""
    state = coordinator.get_state()
    run_id = state["run_id"]
    
    with get_db_session() as session:
        # Update run
        session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status=state["status"],
                current_task_id=state.get("current_task_id"),
                goal_type=state.get("goal_type"),
                updated_at=datetime.utcnow(),
            )
        )
        
        # Update tasks
        for task_data in state.get("tasks", []):
            task_id = task_data["id"]
            
            existing = session.execute(
                select(Task).where(and_(Task.run_id == run_id, Task.task_id == task_id))
            )
            existing_task = existing.scalar_one_or_none()
            
            task_status = state.get("task_statuses", {}).get(task_id, "pending")
            task_output = state.get("task_outputs", {}).get(task_id)
            retries = state.get("task_retries", {}).get(task_id, 0)
            
            if existing_task:
                session.execute(
                    update(Task)
                    .where(and_(Task.run_id == run_id, Task.task_id == task_id))
                    .values(
                        status=task_status,
                        retries=retries,
                        output=task_output,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                new_task = Task(
                    task_id=task_id,
                    run_id=run_id,
                    task_description=task_data.get("task", ""),
                    reason=task_data.get("reason"),
                    depends_on=task_data.get("depends_on", []),
                    status=task_status,
                    retries=retries,
                    output=task_output,
                )
                session.add(new_task)
        
        # Update cost tracking
        cost_stats = state.get("cost", {})
        existing_cost = session.execute(
            select(CostTracking).where(CostTracking.run_id == run_id)
        )
        cost_record = existing_cost.scalar_one_or_none()
        
        if cost_record:
            session.execute(
                update(CostTracking)
                .where(CostTracking.run_id == run_id)
                .values(
                    prompt_tokens=cost_stats.get("prompt_tokens", 0),
                    completion_tokens=cost_stats.get("completion_tokens", 0),
                    total_tokens=cost_stats.get("total_tokens", 0),
                    estimated_cost_usd=cost_stats.get("estimated_cost_usd", 0),
                    tavily_searches=cost_stats.get("tavily_searches", 0),
                )
            )
        else:
            new_cost = CostTracking(
                run_id=run_id,
                prompt_tokens=cost_stats.get("prompt_tokens", 0),
                completion_tokens=cost_stats.get("completion_tokens", 0),
                total_tokens=cost_stats.get("total_tokens", 0),
                estimated_cost_usd=cost_stats.get("estimated_cost_usd", 0),
                tavily_searches=cost_stats.get("tavily_searches", 0),
            )
            session.add(new_cost)


def save_log_entry_sync(run_id: str, log_data: Dict[str, Any]):
    """Save a log entry to database (sync version)."""
    with get_db_session() as session:
        log = Log(
            run_id=run_id,
            task_id=log_data.get("task_id"),
            agent=log_data.get("agent", "unknown"),
            level=log_data.get("level", "info"),
            message=log_data.get("message", ""),
            latency_ms=log_data.get("latency_ms"),
            tokens_used=log_data.get("tokens_used"),
        )
        session.add(log)


async def run_analysis(run_id: str, goal: str, resume: bool = False):
    """Background task to run the analysis."""
    coordinator = CoordinatorAgent(run_id)
    active_coordinators[run_id] = coordinator
    
    # Get the current running event loop
    loop = asyncio.get_running_loop()
    
    # Debounce state saves - only save every N seconds or on important events
    last_state_save = [0.0]  # Use list for mutable closure
    STATE_SAVE_INTERVAL = 5.0  # Save state at most every 5 seconds
    
    # Set callbacks - run DB operations in thread pool to avoid blocking
    async def on_state_change(state):
        import time
        current_time = time.time()
        status = state.get("status", "")
        
        # Always save on important status changes, otherwise debounce
        important_statuses = ["completed", "failed", "pending_user_review"]
        should_save = (
            status in important_statuses or 
            current_time - last_state_save[0] >= STATE_SAVE_INTERVAL
        )
        
        if should_save:
            last_state_save[0] = current_time
            # Run DB save in thread pool (non-blocking)
            loop.run_in_executor(_db_executor, save_run_state_sync, coordinator)
        
        # Always broadcast to websocket (fast)
        await broadcast_to_run(run_id, {"type": "state_update", "state": state})
    
    async def on_log(log_data):
        # Only save important logs to DB (errors, warnings, task completions, search info)
        level = log_data.get("level", "info")
        message = log_data.get("message", "")
        
        should_save_log = (
            level in ["error", "warning"] or
            "completed" in message.lower() or
            "failed" in message.lower() or
            "search" in message.lower() or
            "results" in message.lower()
        )
        
        if should_save_log:
            # Run DB save in thread pool (non-blocking)
            loop.run_in_executor(_db_executor, save_log_entry_sync, run_id, log_data)
        
        # Always broadcast to websocket (fast)
        await broadcast_to_run(run_id, {"type": "log", "log": log_data})
    
    coordinator.set_callbacks(
        on_state_change=on_state_change,
        on_log=on_log,
    )
    
    # Load state if resuming
    if resume:
        with get_db_session() as session:
            run = session.execute(
                select(Run).where(Run.id == run_id)
            )
            run_record = run.scalar_one_or_none()
            
            if run_record:
                tasks_result = session.execute(
                    select(Task).where(Task.run_id == run_id)
                )
                tasks = tasks_result.scalars().all()
                
                state = {
                    "goal": run_record.goal,
                    "goal_type": run_record.goal_type,
                    "status": run_record.status,
                    "current_task_id": run_record.current_task_id,
                    "tasks": [
                        {
                            "id": t.task_id,
                            "task": t.task_description,
                            "reason": t.reason,
                            "depends_on": t.depends_on or [],
                        }
                        for t in tasks
                    ],
                    "task_statuses": {
                        t.task_id: t.status
                        for t in tasks
                    },
                    "task_outputs": {
                        t.task_id: t.output
                        for t in tasks
                        if t.output
                    },
                    "task_retries": {
                        t.task_id: t.retries
                        for t in tasks
                    },
                }
                coordinator.load_state(state)
    
    try:
        result = await coordinator.execute({"goal": goal, "resume": resume})
        
        # Save final state
        save_run_state_sync(coordinator)
        
        # Update run with final report if successful
        if result.get("success"):
            with get_db_session() as session:
                session.execute(
                    update(Run)
                    .where(Run.id == run_id)
                    .values(
                        final_report=result.get("report"),
                        status=RunStatus.PENDING_USER_REVIEW.value,
                        completed_at=datetime.utcnow(),
                    )
                )
        else:
            with get_db_session() as session:
                session.execute(
                    update(Run)
                    .where(Run.id == run_id)
                    .values(
                        status=RunStatus.FAILED.value,
                    )
                )
        
        # Broadcast completion
        await broadcast_to_run(run_id, {
            "type": "completed",
            "success": result.get("success"),
            "report": result.get("report"),
        })
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        with get_db_session() as session:
            session.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(status=RunStatus.FAILED.value)
            )
        await broadcast_to_run(run_id, {"type": "error", "error": str(e)})
    
    finally:
        # Cleanup
        if run_id in active_coordinators:
            del active_coordinators[run_id]
        remove_cost_tracker(run_id)


@router.post("/start-analysis", response_model=AnalysisResponse)
async def start_analysis(request: AnalysisRequest):
    """Start a new analysis run."""
    try:
        run_id = str(uuid.uuid4())
        
        # Create run record
        with get_db_session() as session:
            run = Run(
                id=run_id,
                goal=request.goal,
                status=RunStatus.PENDING.value,
            )
            session.add(run)
        
        # Start background task with proper error handling
        async def safe_run_analysis():
            try:
                print(f"[DEBUG] Starting analysis {run_id}")
                await run_analysis(run_id, request.goal)
                print(f"[DEBUG] Analysis {run_id} completed")
            except Exception as e:
                print(f"[ERROR] Analysis {run_id} failed with error: {e}")
                print(f"[ERROR] Traceback:", exc_info=True)
                import traceback
                traceback.print_exc()
                logger.error(f"Analysis {run_id} failed: {e}")
                # Update run status to failed in database
                try:
                    with get_db_session() as session:
                        result = session.execute(select(Run).where(Run.id == run_id))
                        run = result.scalar_one_or_none()
                        if run:
                            run.status = RunStatus.FAILED.value
                            run.final_report = f"Analysis failed: {str(e)}"
                except Exception as db_error:
                    logger.error(f"Failed to update run status: {db_error}")
        
        asyncio.create_task(safe_run_analysis())
        
        return AnalysisResponse(
            run_id=run_id,
            status="pending",
            message="Analysis started",
        )
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{run_id}", response_model=RunStatusResponse)
async def get_status(run_id: str):
    """Get status of an analysis run."""
    try:
        with get_db_session() as session:
            result = session.execute(
                select(Run).where(Run.id == run_id)
            )
            run = result.scalar_one_or_none()
            
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            
            # Get tasks
            tasks_result = session.execute(
                select(Task).where(Task.run_id == run_id)
            )
            tasks = tasks_result.scalars().all()
            
            # Get cost
            cost_result = session.execute(
                select(CostTracking).where(CostTracking.run_id == run_id)
            )
            cost = cost_result.scalar_one_or_none()
            
            # Calculate progress
            total_tasks = len(tasks)
            completed_tasks = sum(
                1 for t in tasks
                if t.status in ["completed", "failed", "skipped", "blocked_by_failed_dependency"]
            )
            progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Build task responses safely
            task_responses = []
            for t in tasks:
                task_responses.append(TaskResponse(
                    id=t.task_id or f"T{t.id}",  # Fallback if task_id is None
                    task_description=t.task_description or "",
                    depends_on=t.depends_on or [],
                    status=t.status or "pending",
                    retries=t.retries or 0,
                    output=t.output,
                    confidence=t.confidence,
                    validation_score=t.validation_score,
                    error=t.error,
                ))
            
            return RunStatusResponse(
                run_id=run_id,
                goal=run.goal or "",
                goal_type=run.goal_type,
                status=run.status or "pending",
                current_task_id=run.current_task_id,
                tasks=task_responses,
                progress=progress,
                cost={
                    "prompt_tokens": cost.prompt_tokens if cost else 0,
                    "completion_tokens": cost.completion_tokens if cost else 0,
                    "total_tokens": cost.total_tokens if cost else 0,
                    "estimated_cost_usd": cost.estimated_cost_usd if cost else 0,
                },
                created_at=run.created_at or datetime.utcnow(),
                updated_at=run.updated_at or datetime.utcnow(),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/result/{run_id}", response_model=RunResultResponse)
async def get_result(run_id: str):
    """Get the final result of an analysis run."""
    try:
        with get_db_session() as session:
            result = session.execute(
                select(Run).where(Run.id == run_id)
            )
            run = result.scalar_one_or_none()
            
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            
            if run.status not in [
                RunStatus.PENDING_USER_REVIEW.value,
                RunStatus.COMPLETED.value,
            ]:
                # Check if still executing
                if run.status == RunStatus.EXECUTING.value:
                    raise HTTPException(
                        status_code=202,  # 202 Accepted - still processing
                        detail=f"Analysis still in progress. Please wait and try again.",
                    )
                elif run.status == RunStatus.FAILED.value:
                    raise HTTPException(
                        status_code=400,
                        detail="Analysis failed. Check logs for details.",
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Run not ready. Current status: {run.status}",
                    )
            
            # Get tasks
            tasks_result = session.execute(
                select(Task).where(Task.run_id == run_id)
            )
            tasks = tasks_result.scalars().all()
            
            # Get cost
            cost_result = session.execute(
                select(CostTracking).where(CostTracking.run_id == run_id)
            )
            cost = cost_result.scalar_one_or_none()
            
            # Build task responses safely
            task_responses = []
            for t in tasks:
                task_responses.append(TaskResponse(
                    id=t.task_id or f"T{t.id}",
                    task_description=t.task_description or "",
                    depends_on=t.depends_on or [],
                    status=t.status or "pending",
                    retries=t.retries or 0,
                    output=t.output,
                    confidence=t.confidence,
                    validation_score=t.validation_score,
                    error=t.error,
                ))
            
            return RunResultResponse(
                run_id=run_id,
                goal=run.goal or "",
                status=run.status or "pending",
                final_report=run.final_report,
                tasks=task_responses,
                total_cost={
                    "prompt_tokens": cost.prompt_tokens if cost else 0,
                    "completion_tokens": cost.completion_tokens if cost else 0,
                    "total_tokens": cost.total_tokens if cost else 0,
                    "estimated_cost_usd": cost.estimated_cost_usd if cost else 0,
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve/{run_id}")
async def approve_run(run_id: str, request: ApprovalRequest):
    """Approve or reject a run result."""
    with get_db_session() as session:
        result = session.execute(
            select(Run).where(Run.id == run_id)
        )
        run = result.scalar_one_or_none()
        
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        if run.status != RunStatus.PENDING_USER_REVIEW.value:
            raise HTTPException(
                status_code=400,
                detail=f"Run not in review state. Current status: {run.status}",
            )
        
        if request.approved:
            # Apply any edits
            if request.edits and run.final_report:
                updated_report = {**run.final_report, **request.edits}
                session.execute(
                    update(Run)
                    .where(Run.id == run_id)
                    .values(
                        final_report=updated_report,
                        status=RunStatus.COMPLETED.value,
                        completed_at=datetime.utcnow(),
                    )
                )
            else:
                session.execute(
                    update(Run)
                    .where(Run.id == run_id)
                    .values(
                        status=RunStatus.COMPLETED.value,
                        completed_at=datetime.utcnow(),
                    )
                )
            
            return {"status": "approved", "message": "Run approved and completed"}
        else:
            # Log feedback
            log = Log(
                run_id=run_id,
                agent="user",
                level="info",
                message=f"User rejected: {request.feedback or 'No feedback'}",
            )
            session.add(log)
            
            session.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(status=RunStatus.FAILED.value)
            )
            
            return {"status": "rejected", "message": "Run rejected"}


@router.get("/logs/{run_id}", response_model=LogsResponse)
async def get_logs(run_id: str, limit: int = 100, offset: int = 0):
    """Get logs for a run."""
    try:
        with get_db_session() as session:
            result = session.execute(
                select(Log)
                .where(Log.run_id == run_id)
                .order_by(Log.id.desc())  # Use id instead of created_at for ordering
                .limit(limit)
                .offset(offset)
            )
            logs = result.scalars().all()
            
            log_entries = []
            for log in logs:
                # Handle None created_at gracefully
                created_at = log.created_at if log.created_at is not None else datetime.now()
                
                log_entries.append(LogEntry(
                    id=log.id,
                    agent=log.agent or "unknown",
                    level=log.level or "info",
                    message=log.message or "",
                    task_id=log.task_id,
                    latency_ms=log.latency_ms,
                    created_at=created_at,
                ))
            
            return LogsResponse(
                run_id=run_id,
                logs=log_entries,
            )
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume/{run_id}")
async def resume_run(run_id: str):
    """Resume a failed or incomplete run."""
    with get_db_session() as session:
        result = session.execute(
            select(Run).where(Run.id == run_id)
        )
        run = result.scalar_one_or_none()
        
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        if run.status not in [RunStatus.FAILED.value, RunStatus.EXECUTING.value]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume run in status: {run.status}",
            )
        
        goal = run.goal
        
        # Update status
        session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(status=RunStatus.EXECUTING.value)
        )
    
    # Start background task with resume flag using asyncio.create_task
    asyncio.create_task(run_analysis(run_id, goal, resume=True))
    
    return {"status": "resumed", "message": "Run resumed"}


@router.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    
    if run_id not in ws_connections:
        ws_connections[run_id] = []
    ws_connections[run_id].append(websocket)
    
    try:
        # Send current state
        if run_id in active_coordinators:
            state = active_coordinators[run_id].get_state()
            await websocket.send_json({"type": "state_update", "state": state})
        
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_text("keepalive")
    
    except WebSocketDisconnect:
        pass
    finally:
        if run_id in ws_connections:
            ws_connections[run_id].remove(websocket)
            if not ws_connections[run_id]:
                del ws_connections[run_id]
