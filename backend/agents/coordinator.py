"""Coordinator Agent - Orchestration brain for workflow execution."""

import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import asyncio

from agents.base_agent import BaseAgent
from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent
from agents.validator import ValidatorAgent
from models.schemas import (
    CoordinatorAction,
    CoordinatorDecision,
    RunStatusEnum,
    TaskStatusEnum,
    GoalType,
    AnalysisCaseType,
)
from services.cost_tracker import get_cost_tracker
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CoordinatorAgent(BaseAgent):
    """Brain agent that orchestrates the entire workflow (v15 - Real Multi-Call)."""
    
    def __init__(self, run_id: str):
        super().__init__(run_id, "coordinator")
        self.planner = PlannerAgent(run_id)
        self.executor = ExecutorAgent(run_id)
        self.validator = ValidatorAgent(run_id)
        
        self.max_retries = 2  # Allow 2 retries before failing
        self.min_validation_score = 5.5  # Relaxed from 6.8 to improve completion rate
        
        # Run state
        self.tasks: List[Dict[str, Any]] = []
        self.task_outputs: Dict[str, Any] = {}
        self.task_statuses: Dict[str, str] = {}
        self.task_retries: Dict[str, int] = {}
        self.current_task_id: Optional[str] = None
        self.status = RunStatusEnum.PENDING
        self.goal: str = ""
        self.goal_type: Optional[str] = None
        self.classification: Dict[str, Any] = {}
        
        # ============== V15: GLOBAL MEMORY (ENTITY LOCKING) ==============
        self.global_context: Dict[str, Any] = {
            "entities": None,           # Locked after first extraction
            "entity_a": None,           # Primary competitor
            "entity_b": None,           # Startup/subject
            "insights": [],             # Track all insights to prevent repetition
            "facts": [],                # Accumulated facts
            "risks": [],                # Accumulated risks
            "task_outputs": [],         # All task outputs for synthesis
            "category": None,           # Business category (locked)
        }
        
        # Legacy shared memory (for backward compat)
        self.shared_memory: Dict[str, Any] = {
            "competitors": [],
            "dominant_incumbents": [],
            "market_data": {},
            "key_metrics": [],
        }
        
        # V11: Patch retry tracking
        self._patch_retries: Dict[str, int] = {}
        
        # Callbacks for state persistence
        self.on_state_change: Optional[callable] = None
        self.on_log: Optional[callable] = None
    
    def set_callbacks(
        self,
        on_state_change: Optional[callable] = None,
        on_log: Optional[callable] = None,
    ):
        """Set callbacks for state updates."""
        self.on_state_change = on_state_change
        self.on_log = on_log
    
    async def _emit_state_change(self):
        """Emit state change event."""
        if self.on_state_change:
            await self.on_state_change(self.get_state())
    
    async def _emit_log(self, message: str, level: str = "info", task_id: Optional[str] = None):
        """Emit log event."""
        self.log(message, level=level, task_id=task_id)
        if self.on_log:
            await self.on_log({
                "agent": self.name,
                "level": level,
                "message": message,
                "task_id": task_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state for persistence."""
        return {
            "run_id": self.run_id,
            "status": self.status.value if isinstance(self.status, RunStatusEnum) else self.status,
            "goal": self.goal,
            "goal_type": self.goal_type,
            "classification": self.classification,
            "current_task_id": self.current_task_id,
            "tasks": self.tasks,
            "task_outputs": self.task_outputs,
            "task_statuses": self.task_statuses,
            "task_retries": self.task_retries,
            "cost": self.cost_tracker.get_stats(),
        }
    
    def load_state(self, state: Dict[str, Any]):
        """Load state from persistence."""
        self.goal = state.get("goal", "")
        self.goal_type = state.get("goal_type")
        self.classification = state.get("classification", {})
        self.current_task_id = state.get("current_task_id")
        self.tasks = state.get("tasks", [])
        self.task_outputs = state.get("task_outputs", {})
        self.task_statuses = state.get("task_statuses", {})
        self.task_retries = state.get("task_retries", {})
        status = state.get("status", "pending")
        self.status = RunStatusEnum(status) if isinstance(status, str) else status
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution entry point."""
        self.goal = context.get("goal", "")
        resume = context.get("resume", False)
        
        if not self.goal:
            return {"success": False, "error": "No goal provided"}
        
        await self._emit_log(f"Starting analysis: {self.goal}")
        
        try:
            if not resume:
                # Phase 1: Planning
                self.status = RunStatusEnum.PLANNING
                await self._emit_state_change()
                await self._emit_log("Starting task planning...", level="info")
                
                try:
                    # Add timeout to prevent infinite planning
                    plan_result = await asyncio.wait_for(
                        self._plan(),
                        timeout=120  # 2 minutes max for planning
                    )
                    if not plan_result["success"]:
                        return plan_result
                except asyncio.TimeoutError:
                    error_msg = "Planning phase timed out after 2 minutes"
                    await self._emit_log(error_msg, level="error")
                    self.status = RunStatusEnum.FAILED
                    await self._emit_state_change()
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"Planning phase failed: {str(e)}"
                    await self._emit_log(error_msg, level="error") 
                    self.status = RunStatusEnum.FAILED
                    await self._emit_state_change()
                    return {"success": False, "error": error_msg}
            
            # Phase 2: Execution
            self.status = RunStatusEnum.EXECUTING
            await self._emit_state_change()
            
            execution_result = await self._execute_tasks()
            
            # Phase 3: FINAL SYNTHESIS BLOCK (V17 - MANDATORY)
            if execution_result["success"]:
                await self._emit_log("V17: Running FINAL SYNTHESIS BLOCK")
                synthesis_result = await self._run_final_synthesis()
                
                # Phase 4: Final Report
                self.status = RunStatusEnum.PENDING_USER_REVIEW
                await self._emit_state_change()
                
                final_report = self._generate_final_report(synthesis_result)
                
                return {
                    "success": True,
                    "status": self.status.value,
                    "report": final_report,
                    "tasks": self.tasks,
                    "outputs": self.task_outputs,
                    "synthesis": synthesis_result,
                    "cost": self.cost_tracker.get_stats(),
                }
            else:
                self.status = RunStatusEnum.FAILED
                await self._emit_state_change()
                return execution_result
                
        except Exception as e:
            self.status = RunStatusEnum.FAILED
            await self._emit_state_change()
            await self._emit_log(f"Execution failed: {e}", level="error")
            return {"success": False, "error": str(e)}
    
    async def _plan(self) -> Dict[str, Any]:
        """Execute planning phase."""
        await self._emit_log("Starting task planning...")
        
        plan_result = await self.planner.execute({"goal": self.goal})
        
        if not plan_result["success"]:
            await self._emit_log("Planning failed", level="error")
            return plan_result
        
        plan = plan_result["plan"]
        self.goal_type = plan_result.get("goal_type", plan.get("goal_type"))
        self.classification = plan_result.get("classification", plan.get("classification", {}))
        self.tasks = plan.get("tasks", [])
        
        # Initialize task statuses
        for task in self.tasks:
            task_id = task["id"]
            self.task_statuses[task_id] = TaskStatusEnum.PENDING.value
            self.task_retries[task_id] = 0
        
        await self._emit_log(f"Created {len(self.tasks)} tasks (method: {plan_result.get('method', 'unknown')})")
        await self._emit_log(f"Classification: type={self.goal_type}, domain={self.classification.get('domain', 'unknown')}")
        
        # 🔥 CRITICAL FIX: Save tasks to database so frontend can see them
        await self._emit_log("Saving tasks to database...")
        await self._save_tasks_to_database()
        await self._emit_log(f"✅ {len(self.tasks)} tasks saved to database")
        
        await self._emit_state_change()
        
        return {"success": True}
    
    async def _execute_tasks(self) -> Dict[str, Any]:
        """Execute all tasks in order (v15: with global context)."""
        
        # V15: Lock entities on first task
        await self._lock_entities_if_needed()
        
        while True:
            # Find next executable task
            next_task = self._get_next_task()
            
            if next_task is None:
                # Check if all tasks are done
                completed = all(
                    s in [TaskStatusEnum.COMPLETED.value, TaskStatusEnum.FAILED.value, TaskStatusEnum.SKIPPED.value, TaskStatusEnum.BLOCKED.value]
                    for s in self.task_statuses.values()
                )
                
                if completed:
                    await self._emit_log("All tasks completed")
                    return {"success": True}
                else:
                    await self._emit_log("No executable tasks found", level="warning")
                    return {"success": False, "error": "Deadlock: no executable tasks"}
            
            # Execute the task
            task_id = next_task["id"]
            self.current_task_id = task_id
            self.task_statuses[task_id] = TaskStatusEnum.IN_PROGRESS.value
            await self._emit_state_change()
            
            # Get retry feedback if this is a retry
            retry_feedback = self._get_retry_feedback(task_id)
            result = await self._execute_single_task(next_task, retry_feedback)
            
            # V15: Update global context with task output
            self._update_global_context(result.get("output", {}))
            
            # Process result
            decision = await self._make_decision(task_id, result)
            
            if decision.action == CoordinatorAction.PROCEED:
                self.task_statuses[task_id] = TaskStatusEnum.COMPLETED.value
                # V21: Include validation_metrics in task output for frontend display
                task_output = result.get("output", {})
                if isinstance(task_output, dict):
                    validation = result.get("validation", {})
                    task_output["validation_metrics"] = validation.get("validation_metrics", {})
                    task_output["confidence"] = validation.get("confidence", validation.get("validation_metrics", {}).get("confidence", 0.7))
                    task_output["rejection_reason"] = validation.get("feedback_for_retry", "") if not validation.get("valid", True) else None
                self.task_outputs[task_id] = task_output
                await self._emit_log(f"Task {task_id} completed (score: {result.get('validation', {}).get('score', 'N/A')})", task_id=task_id)
                
            elif decision.action == CoordinatorAction.RETRY:
                self.task_retries[task_id] = self.task_retries.get(task_id, 0) + 1
                self.task_statuses[task_id] = TaskStatusEnum.PENDING.value
                await self._emit_log(
                    f"Task {task_id} retry {self.task_retries[task_id]}/{self.max_retries}: {decision.reason}",
                    level="warning",
                    task_id=task_id,
                )
                
            elif decision.action == CoordinatorAction.SKIP:
                self.task_statuses[task_id] = TaskStatusEnum.SKIPPED.value
                await self._emit_log(f"Task {task_id} skipped: {decision.reason}", level="warning", task_id=task_id)
                
            elif decision.action == CoordinatorAction.FAIL:
                self.task_statuses[task_id] = TaskStatusEnum.FAILED.value
                self._block_dependent_tasks(task_id)
                await self._emit_log(f"Task {task_id} failed: {decision.reason}", level="error", task_id=task_id)
            
            await self._emit_state_change()
            
            # Check cost limit
            if self.cost_tracker.is_over_limit():
                await self._emit_log("Cost limit exceeded", level="warning")
                self._skip_remaining_tasks()
                return {"success": True, "warning": "Cost limit reached"}
    
    async def _lock_entities_if_needed(self):
        """V15: Lock comparison entities at start to prevent drift."""
        if self.global_context["entities"] is not None:
            return  # Already locked
        
        # Detect category from goal
        from agents.executor import detect_category, get_comparison_entities
        category = detect_category(self.goal)
        self.global_context["category"] = category
        
        # Get comparison entities
        entity_a, entity_b, _, competitors = get_comparison_entities(self.goal)
        
        self.global_context["entities"] = [entity_a, entity_b]
        self.global_context["entity_a"] = entity_a
        self.global_context["entity_b"] = entity_b
        
        # Also update shared_memory for backward compat
        self.shared_memory["competitors"] = competitors
        self.shared_memory["dominant_incumbents"] = [entity_a]
        
        self.log(f"V15: Entities locked - {entity_a} vs {entity_b} (category: {category})")
    
    def _update_global_context(self, output: Dict[str, Any]):
        """V15: Update global context with task output, preventing repetition."""
        if not isinstance(output, dict):
            return
        
        # Accumulate facts
        facts = output.get("facts", [])
        for fact in facts:
            if fact and fact not in self.global_context["facts"]:
                self.global_context["facts"].append(fact)
        
        # Accumulate insights (prevent repetition)
        insight = output.get("key_insight", "")
        if insight and insight not in self.global_context["insights"]:
            self.global_context["insights"].append(insight)
        
        # Accumulate risks
        risk = output.get("biggest_risk", "")
        if risk and risk not in self.global_context["risks"]:
            self.global_context["risks"].append(risk)
        
        # Store task output
        self.global_context["task_outputs"].append(output)
    
    async def _execute_single_task(self, task: Dict[str, Any], retry_feedback: str = "") -> Dict[str, Any]:
        """Execute a single task with validation (v23: single-call pipeline)."""
        task_id = task["id"]
        
        # V24: Task-level timeout - allow for real-world API delays
        # Search: ~2-3s per query (parallel), LLM: ~5-10s per call
        # But real-world API delays can be 30-60s, so need buffer
        # Synthesis tasks need more time as they process all previous outputs
        is_synthesis = task_id in ["T5", "synthesis", "final_synthesis"]
        TASK_TIMEOUT = 300 if is_synthesis else 180  # 5 min for synthesis, 3 min for regular tasks
        
        try:
            return await asyncio.wait_for(
                self._execute_single_task_impl(task, retry_feedback),
                timeout=TASK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Task {task_id} timed out after {TASK_TIMEOUT}s - likely search/LLM API slowness")
            return {
                "success": False,
                "error": f"Task timed out after {TASK_TIMEOUT} seconds",
                "task_id": task_id,
                "timeout": True
            }
        except Exception as e:
            logger.error(f"Task {task_id} failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Task execution failed: {str(e)}",
                "task_id": task_id,
                "exception": str(type(e).__name__)
            }
    
    async def _execute_single_task_impl(self, task: Dict[str, Any], retry_feedback: str = "") -> Dict[str, Any]:
        """Implementation of single task execution."""
        task_id = task["id"]
        
        # Check if should use summarization mode
        use_summarization = self.cost_tracker.should_use_summarization()
        
        # V11: Check if this is a patch retry
        is_patch_retry = bool(retry_feedback and self._patch_retries.get(task_id, 0) == 0)
        
        # V14: Determine task index and if this is the final task
        task_index = next((i for i, t in enumerate(self.tasks) if t["id"] == task_id), 0)
        is_final_task = (task_index == len(self.tasks) - 1)
        
        # Execute with classification context, retry feedback, and global context
        exec_result = await self.executor.execute({
            "task": task,
            "previous_outputs": self.task_outputs,
            "use_summarization": use_summarization,
            "classification": self.classification,
            "retry_feedback": retry_feedback,
            "shared_memory": self.shared_memory,
            "is_patch_retry": is_patch_retry,
            "is_final_task": is_final_task,
            "task_index": task_index,
            "total_tasks": len(self.tasks),
            # V15: Global context for entity locking and insight tracking
            "global_context": self.global_context,
        })
        
        if not exec_result.get("success"):
            return exec_result
        
        # V11: Update shared memory with new competitors/data
        self._update_shared_memory(exec_result.get("output", {}))
        
        # Validate with classification context
        self.task_statuses[task_id] = TaskStatusEnum.VALIDATING.value
        await self._emit_state_change()
        
        # Small delay to ensure frontend receives the VALIDATING state
        import asyncio
        await asyncio.sleep(0.2)  # 200ms delay for websocket delivery
        
        is_retry = self.task_retries.get(task_id, 0) > 0
        val_result = await self.validator.execute({
            "task_id": task_id,
            "task_description": task.get("task", ""),
            "output": exec_result.get("output", {}),
            "sources": exec_result.get("sources", []),
            "is_retry": is_retry,  # V11: signal for deep validation on retries
        })
        
        exec_result["validation"] = val_result.get("validation", {})
        return exec_result
    
    def _update_shared_memory(self, output: Dict[str, Any]):
        """V11: Extract and store reusable data from task output."""
        # Ensure output is a dict
        if not isinstance(output, dict):
            return
        
        # Extract competitors
        competitors = output.get("competitors_identified", {})
        if isinstance(competitors, dict):
            direct = competitors.get("direct", [])
            indirect = competitors.get("indirect", [])
            for comp in direct + indirect:
                if comp and comp not in self.shared_memory["competitors"]:
                    self.shared_memory["competitors"].append(comp)
            # Check for dominant incumbent
            if competitors.get("dominant_incumbent"):
                dom = competitors.get("dominant_incumbent")
                if dom not in self.shared_memory["dominant_incumbents"]:
                    self.shared_memory["dominant_incumbents"].append(dom)
        
        # Extract key metrics
        if output.get("key_metrics"):
            for metric in output.get("key_metrics", []):
                if metric not in self.shared_memory["key_metrics"]:
                    self.shared_memory["key_metrics"].append(metric)
    
    async def _make_decision(self, task_id: str, result: Dict[str, Any]) -> CoordinatorDecision:
        """Make decision based on task result (v14: stricter final task validation)."""
        
        # Check for execution failure
        if not result.get("success"):
            error = result.get("error", "Unknown error")
            retries = self.task_retries.get(task_id, 0)
            
            if retries < self.max_retries:
                return CoordinatorDecision(
                    action=CoordinatorAction.RETRY,
                    reason=f"Execution failed: {error}",
                    retry_count=retries + 1,
                )
            else:
                return CoordinatorDecision(
                    action=CoordinatorAction.FAIL,
                    reason=f"Max retries exceeded. Last error: {error}",
                )
        
        # Check validation result
        validation = result.get("validation", {})
        score = validation.get("score", 8)
        is_valid = validation.get("valid", True)
        issues = validation.get("issues", [])
        feedback = validation.get("feedback_for_retry", "")
        missing = validation.get("missing", [])
        weak = validation.get("weak", [])
        
        # Check output quality
        output = result.get("output", {})
        
        # Ensure output is a dict
        if not isinstance(output, dict):
            output = {"raw_output": output}
        
        has_content = output and (
            output.get("summary") or 
            output.get("key_findings") or 
            len(str(output)) > 100
        )
        
        # Check for comparison/competitor content
        has_competitors = bool(output.get("competitors_identified", []))
        has_comparisons = bool(output.get("comparisons", []) or output.get("comparison_table"))
        has_key_insight = bool(output.get("key_insight"))
        
        # V14: Check if this is the final task
        is_final_task = output.get("is_final_task", False)
        
        # V14: Strict checks for final task
        if is_final_task:
            comparison_table = output.get("comparison_table", {})
            has_valid_comparison = (
                isinstance(comparison_table, dict) and 
                len(comparison_table.get("rows", [])) >= 3
            )
            final_verdict = output.get("final_verdict", {})
            has_valid_verdict = (
                isinstance(final_verdict, dict) and 
                final_verdict.get("verdict") in ["YES", "NO", "CONDITIONAL"]
            )
        else:
            has_valid_comparison = True  # Not required for non-final tasks
            has_valid_verdict = True
        
        retries = self.task_retries.get(task_id, 0)
        patch_retries = self._patch_retries.get(task_id, 0)
        
        # COST OPTIMIZATION: Enhanced early exit for high-quality first attempts
        # If first attempt has confidence > 0.75 AND score >= 7.5 → PROCEED immediately
        confidence = output.get("confidence", 0) if isinstance(output, dict) else 0
        
        # V14: Higher bar for final tasks (require comparison + verdict)
        if is_final_task:
            if retries == 0 and confidence > 0.75 and score >= 7.5 and has_content and has_key_insight and has_valid_comparison and has_valid_verdict:
                self.log(
                    f"✅ EARLY EXIT: Excellent final task (confidence={confidence:.2f}, score={score:.1f})",
                    task_id=task_id,
                    level="info"
                )
                return CoordinatorDecision(
                    action=CoordinatorAction.PROCEED,
                    reason=f"Excellent final task (conf={confidence:.2f}, score={score:.1f})",
                )
        else:
            if retries == 0 and confidence > 0.75 and score >= 7.5 and has_content and has_key_insight:
                self.log(
                    f"✅ EARLY EXIT: Excellent first attempt (confidence={confidence:.2f}, score={score:.1f})",
                    task_id=task_id,
                    level="info"
                )
                return CoordinatorDecision(
                    action=CoordinatorAction.PROCEED,
                    reason=f"Excellent first attempt (conf={confidence:.2f}, score={score:.1f})",
                )
        
        # V14: Relaxed validation standards for better completion rate
        min_score = 6.0 if is_final_task else self.min_validation_score
        
        if is_final_task:
            # Final task - more lenient requirements
            if is_valid and score >= min_score and has_content and has_key_insight:
                return CoordinatorDecision(
                    action=CoordinatorAction.PROCEED,
                    reason=f"Final task validation passed (score: {score:.1f})",
                )
        else:
            # Non-final tasks: even more relaxed requirements
            if retries == 0 and has_content and has_key_insight and score >= 5.8:
                return CoordinatorDecision(
                    action=CoordinatorAction.PROCEED,
                    reason=f"First attempt passed (score: {score:.1f})",
                )
            
            if is_valid and score >= self.min_validation_score:
                return CoordinatorDecision(
                    action=CoordinatorAction.PROCEED,
                    reason=f"Validation passed (score: {score:.1f})",
                )
        
        # V11: Smart retry strategy - patch first, then full retry
        if score < self.min_validation_score:
            # Store the current output for patching
            self._store_current_output(task_id, output)
            
            # Try patch retry first (cheaper)
            if patch_retries == 0 and missing:
                self._patch_retries[task_id] = 1
                # Create targeted feedback for patch
                patch_feedback = f"PATCH ONLY - add these missing fields:\n{chr(10).join(f'- {m}' for m in missing)}\nKeep existing output, just add missing parts."
                self._store_retry_feedback(task_id, patch_feedback)
                
                return CoordinatorDecision(
                    action=CoordinatorAction.RETRY,
                    reason=f"Patch retry for missing: {', '.join(missing[:3])}",
                    retry_count=retries + 1,
                    prompt_update=patch_feedback,
                )
            
            # Full retry if patch didn't work
            if retries < self.max_retries:
                self._store_retry_feedback(task_id, feedback or f"Issues: {'; '.join(issues[:3])}")
                
                return CoordinatorDecision(
                    action=CoordinatorAction.RETRY,
                    reason=f"Full retry (score: {score:.1f})",
                    retry_count=retries + 1,
                    prompt_update=feedback[:300] if feedback else None,
                )
        
        # Accept with content after multiple tries (relaxed requirements)
        if has_content and has_key_insight and retries >= 1:
            return CoordinatorDecision(
                action=CoordinatorAction.PROCEED,
                reason=f"Accepting after {retries} retries (score: {score:.1f})",
            )
        
        # Accept ANY content after 2 retries to prevent task failures
        if retries >= 2 and has_content:
            return CoordinatorDecision(
                action=CoordinatorAction.PROCEED,
                reason=f"Final acceptance after {retries} retries - minimal quality (score: {score:.1f})",
            )
        
        # Final retry
        if retries < self.max_retries:
            return CoordinatorDecision(
                action=CoordinatorAction.RETRY,
                reason="Insufficient content quality",
                retry_count=retries + 1,
            )
        
        return CoordinatorDecision(
            action=CoordinatorAction.FAIL,
            reason=f"Failed after {self.max_retries} retries (score: {score:.1f})",
        )
    
        
    async def _save_tasks_to_database(self):
        """Save tasks from memory to database for frontend display."""
        if not self.tasks:
            return
        
        from database import get_db_session
        from models.db_models import Task
        
        try:
            with get_db_session() as session:
                for task in self.tasks:
                    task_id = task["id"]
                    
                    # FIXED: Use correct field names from planner output
                    # Tasks use "task" field for description, not "description"
                    description = task.get("task", "")  # ← Key fix!
                    reason = task.get("reason", "")
                    dependencies = task.get("depends_on", [])  # ← This is already a list
                    order_idx = task.get("order", 0)
                    
                    # Create database task - SQLAlchemy handles auto-increment id
                    db_task = Task(
                        task_id=task_id,
                        run_id=self.run_id,
                        task_description=description,
                        reason=reason,
                        depends_on=dependencies,  # ← Store as JSON list, not string
                        order_index=order_idx,
                        status=self.task_statuses.get(task_id, TaskStatusEnum.PENDING.value),
                        retries=0,
                        max_retries=2
                    )
                    
                    session.add(db_task)
                
                session.commit()
                await self._emit_log(f"✅ Saved {len(self.tasks)} tasks to database successfully")
                
        except Exception as e:
            await self._emit_log(f"❌ Failed to save tasks to database: {e}", level="error")
            # Don't fail the planning phase, continue with in-memory tasks
            pass

    def _store_current_output(self, task_id: str, output: Dict[str, Any]):
        """V11: Store current output for patch-based retry."""
        if not hasattr(self, '_outputs_for_patch'):
            self._outputs_for_patch = {}
        self._outputs_for_patch[task_id] = output
    
    def _get_output_for_patch(self, task_id: str) -> Dict[str, Any]:
        """V11: Get stored output for patching."""
        if not hasattr(self, '_outputs_for_patch'):
            return {}
        return self._outputs_for_patch.get(task_id, {})
    
    def _store_retry_feedback(self, task_id: str, feedback: str):
        """Store retry feedback for a task."""
        if not hasattr(self, '_retry_feedbacks'):
            self._retry_feedbacks = {}
        self._retry_feedbacks[task_id] = feedback
    
    def _get_retry_feedback(self, task_id: str) -> str:
        """Get stored retry feedback for a task."""
        if not hasattr(self, '_retry_feedbacks'):
            return ""
        return self._retry_feedbacks.get(task_id, "")
    
    def _get_next_task(self) -> Optional[Dict[str, Any]]:
        """Get the next task that can be executed."""
        for task in self.tasks:
            task_id = task["id"]
            status = self.task_statuses.get(task_id)
            
            if status != TaskStatusEnum.PENDING.value:
                continue
            
            # Check dependencies
            deps = task.get("depends_on", [])
            deps_satisfied = all(
                self.task_statuses.get(dep) == TaskStatusEnum.COMPLETED.value
                for dep in deps
            )
            
            # Check if any dependency failed
            deps_failed = any(
                self.task_statuses.get(dep) in [
                    TaskStatusEnum.FAILED.value,
                    TaskStatusEnum.BLOCKED.value,
                ]
                for dep in deps
            )
            
            if deps_failed:
                self.task_statuses[task_id] = TaskStatusEnum.BLOCKED.value
                continue
            
            if deps_satisfied:
                return task
        
        return None
    
    def _block_dependent_tasks(self, failed_task_id: str):
        """Mark tasks that depend on a failed task as blocked."""
        for task in self.tasks:
            if failed_task_id in task.get("depends_on", []):
                self.task_statuses[task["id"]] = TaskStatusEnum.BLOCKED.value
    
    def _skip_remaining_tasks(self):
        """Skip remaining pending tasks."""
        for task in self.tasks:
            if self.task_statuses.get(task["id"]) == TaskStatusEnum.PENDING.value:
                self.task_statuses[task["id"]] = TaskStatusEnum.SKIPPED.value
    
    # ============== V17: FINAL SYNTHESIS BLOCK ==============
    
    async def _run_final_synthesis(self) -> Dict[str, Any]:
        """
        V17: Run the FINAL SYNTHESIS BLOCK after all tasks complete.
        
        This combines all task outputs into a unified analysis with:
        - ONE final insight (merged from all tasks)
        - ONE comparison table (generated fresh, not per-task)
        - ONE final verdict
        """
        await self._emit_log("V17: Starting FINAL SYNTHESIS")
        
        entity_a = self.global_context.get("entity_a", "Competitor")
        entity_b = self.global_context.get("entity_b", "Proposed Startup")
        category = self.global_context.get("category", "general")
        case_type = self.classification.get("type", "startup_idea")
        
        # Step 1: Run synthesis to combine all outputs
        synthesis_result = await self.executor.synthesize_all_outputs(
            all_task_outputs=self.task_outputs,
            goal=self.goal,
            classification=self.classification,
            global_context=self.global_context,
        )
        
        if not synthesis_result.get("success"):
            await self._emit_log(f"V17: Synthesis failed: {synthesis_result.get('error')}", level="warning")
            # Continue with fallback
            synthesis = {}
        else:
            synthesis = synthesis_result.get("synthesis", {})
            await self._emit_log(f"V17: Synthesis complete - verdict: {synthesis.get('final_verdict', 'MISSING')}")
        
        # Step 2: Generate the FINAL comparison table (ONE table for entire analysis)
        table_result = await self.executor.generate_final_table(
            synthesis=synthesis,
            goal=self.goal,
            case_type=case_type,
            entity_a=entity_a,
            entity_b=entity_b,
            category=category,
        )
        
        if not table_result.get("success"):
            await self._emit_log(f"V17: Table generation failed: {table_result.get('error')}", level="warning")
            final_table = {"rows": []}
        else:
            final_table = table_result.get("table", {})
            await self._emit_log(f"V17: Final table generated - {len(final_table.get('rows', []))} rows")
        
        # Combine into synthesis result
        return {
            "synthesis": synthesis,
            "final_table": final_table,
            "entities": {
                "entity_a": entity_a,
                "entity_b": entity_b,
            },
            "category": category,
            "case_type": case_type,
        }
    
    def _generate_final_report(self, synthesis_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate the final analysis report with V17 SYNTHESIS output."""
        case_type = self.classification.get("case_type", "single_company")
        
        # V17: Get synthesis data if available
        synthesis = {}
        final_table_from_synthesis = {}
        if synthesis_result:
            synthesis = synthesis_result.get("synthesis", {})
            final_table_from_synthesis = synthesis_result.get("final_table", {})
        
        # V15: Get locked entities from global context
        entity_a = self.global_context.get("entity_a", "Competitor")
        entity_b = self.global_context.get("entity_b", "Proposed Startup")
        
        report = {
            "goal": self.goal,
            "goal_type": self.goal_type,
            "case_type": case_type,
            "classification": self.classification,
            "generated_at": datetime.utcnow().isoformat(),
            "sections": {},
            "executive_summary": "",
            "key_findings": [],
            "strategic_insights": [],
            "final_verdict": None,
            "feature_matrix": {},
            "swot": {},
            "recommendations": [],
            # V17: Global outputs from SYNTHESIS BLOCK
            "final_output": {
                "entities": {
                    "entity_a": entity_a,
                    "entity_b": entity_b,
                },
                # Add summary for frontend compatibility (from synthesis or first task)
                "summary": synthesis.get("final_insight") if synthesis and synthesis.get("final_insight") else (
                    self.task_outputs.get(self.tasks[0]["id"], {}).get("summary", "") if self.tasks else ""
                ),
                # V17: Use synthesis table instead of per-task table
                "table": final_table_from_synthesis if final_table_from_synthesis else None,
                "key_insight": synthesis.get("final_insight") if synthesis else None,
                "final_verdict": {
                    "verdict": synthesis.get("final_verdict"),
                    "arguments_for": synthesis.get("arguments_for", []),
                    "arguments_against": synthesis.get("arguments_against", []),
                } if synthesis else None,
                "true_competitors": synthesis.get("true_competitors", []) if synthesis else [],
                "critical_risk": synthesis.get("critical_risk") if synthesis else None,
                "all_insights": self.global_context.get("insights", []),
                "all_risks": self.global_context.get("risks", []),
            },
        }
        
        # Organize outputs by task (V17: NO comparison_table in ANY task sections)
        all_findings = []
        
        for task in self.tasks:
            task_id = task["id"]
            output = self.task_outputs.get(task_id, {})
            
            # Ensure output is a dict
            if not isinstance(output, dict):
                output = {"raw_output": output}
            
            if output:
                # V17: ALWAYS remove comparison_table and final_verdict from task sections
                # These are now in the SYNTHESIS output only
                section_output = dict(output)
                section_output.pop("comparison_table", None)
                section_output.pop("final_verdict", None)
                
                report["sections"][task_id] = {
                    "task": task.get("task", ""),
                    "output": section_output,
                    "status": self.task_statuses.get(task_id),
                }
                
                # Extract key components
                if isinstance(output, dict):
                    # Key findings
                    all_findings.extend(output.get("key_findings", []) or output.get("facts", []))
                    
                    # Feature matrix
                    if output.get("feature_matrix"):
                        report["feature_matrix"].update(output["feature_matrix"])
                    
                    # SWOT if present
                    if output.get("swot"):
                        report["swot"] = output["swot"]
        
        # V17: Use synthesis verdict if available, fallback to final task
        if synthesis.get("final_verdict"):
            report["final_verdict"] = {
                "verdict": synthesis.get("final_verdict"),
                "arguments_for": synthesis.get("arguments_for", []),
                "arguments_against": synthesis.get("arguments_against", []),
            }
        
        # V17: Use synthesis facts if available
        if synthesis.get("synthesized_facts"):
            all_findings = synthesis.get("synthesized_facts") + all_findings
        
        # Best insight from synthesis or global context
        if synthesis.get("final_insight"):
            report["final_output"]["key_insight"] = synthesis.get("final_insight")
        elif self.global_context.get("insights"):
            report["final_output"]["key_insight"] = self.global_context.get("insights")[-1]
        
        # Strategic insights from global context
        insights = self.global_context.get("insights", [])
        report["strategic_insights"] = [
            {"insight": i, "from_task": "accumulated"} 
            for i in insights[:8]
        ]
        
        # Top findings (best 10)
        report["key_findings"] = list(set(all_findings))[:10]
        
        # Executive summary from first task or generate
        if self.tasks:
            first_output = self.task_outputs.get(self.tasks[0]["id"], {})
            if isinstance(first_output, dict):
                report["executive_summary"] = first_output.get("summary", "")
        
        # Add cost breakdown
        cost_tracker = get_cost_tracker(self.run_id)
        report["cost_breakdown"] = cost_tracker.get_breakdown()
        
        return report
    
    def _build_competitive_table(
        self,
        case_type: str,
        comparison_rows: List[Dict],
        competitors: Dict,
        classification: Dict
    ) -> Dict[str, Any]:
        """Build the final competitive analysis table based on case type."""
        entities = classification.get("entities", [])
        
        if case_type == "competitor_comparison" and len(entities) >= 2:
            # Two-company comparison
            return {
                "type": "competitor_comparison",
                "company_a": entities[0],
                "company_b": entities[1],
                "dimensions": self._merge_comparison_dimensions(comparison_rows, entities[:2])
            }
        elif case_type == "startup_idea":
            # Startup vs existing solutions
            existing_solutions = competitors.get("direct", [])[:3]
            return {
                "type": "startup_idea",
                "proposed_startup": entities[0] if entities else "Proposed Solution",
                "existing_solutions": existing_solutions,
                "dimensions": self._merge_comparison_dimensions(comparison_rows, entities + existing_solutions)
            }
        else:
            # Single company vs industry standard
            company = entities[0] if entities else "Subject"
            competitors_list = competitors.get("direct", [])[:3]
            return {
                "type": "single_company",
                "company": company,
                "competitors": competitors_list,
                "dimensions": self._merge_comparison_dimensions(comparison_rows, [company] + competitors_list)
            }
    
    def _merge_comparison_dimensions(self, rows: List[Dict], entities: List[str]) -> List[Dict]:
        """Merge comparison rows from all tasks into unified dimensions."""
        # Group by attribute
        by_attribute = {}
        for row in rows:
            attr = row.get("attribute", "Unknown")
            if attr not in by_attribute:
                by_attribute[attr] = row
            # Keep the most complete row
            elif row.get("winner"):
                by_attribute[attr] = row
        
        return list(by_attribute.values())
    
    def get_all_logs(self) -> List[Dict[str, Any]]:
        """Get logs from all agents."""
        all_logs = []
        all_logs.extend(self.logs)
        all_logs.extend(self.planner.get_logs())
        all_logs.extend(self.executor.get_logs())
        all_logs.extend(self.validator.get_logs())
        
        # Sort by timestamp
        all_logs.sort(key=lambda x: x.get("timestamp", ""))
        
        return all_logs
