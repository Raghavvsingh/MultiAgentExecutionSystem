"""Base Agent - Common functionality for all agents."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from backend.services.llm_service import get_llm_service, LLMService
from backend.services.cost_tracker import get_cost_tracker, CostTracker
logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents with common functionality."""
    
    def __init__(self, run_id: str, name: str):
        self.run_id = run_id
        self.name = name
        self.llm_service: LLMService = get_llm_service()
        self.cost_tracker: CostTracker = get_cost_tracker(run_id)
        self.logs: list = []
    
    def log(
        self,
        message: str,
        level: str = "info",
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log a message."""
        log_entry = {
            "agent": self.name,
            "level": level,
            "message": message,
            "task_id": task_id,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.logs.append(log_entry)
        
        log_func = getattr(logger, level, logger.info)
        log_func(f"[{self.name}] {message}")
    
    def track_llm_usage(
        self,
        response: Dict[str, Any],
        task_id: Optional[str] = None,
    ):
        """Track LLM usage from a response."""
        self.cost_tracker.add_llm_usage(
            prompt_tokens=response.get("prompt_tokens", 0),
            completion_tokens=response.get("completion_tokens", 0),
            cost=response.get("cost", 0),
            agent=self.name,
            task_id=task_id,
        )
    
    def get_logs(self) -> list:
        """Get all logs from this agent."""
        return self.logs
    
    def clear_logs(self):
        """Clear logs."""
        self.logs = []
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's main function."""
        pass
