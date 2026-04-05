"""Cost Tracker - Monitor and control token usage and costs."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CostTracker:
    """Track costs across a run."""
    
    def __init__(self, run_id: str, cost_limit: Optional[float] = None):
        self.run_id = run_id
        self.cost_limit = cost_limit or settings.cost_limit_usd
        
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.estimated_cost = 0.0
        self.tavily_searches = 0
        
        self.history = []
    
    def add_llm_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        agent: str,
        task_id: Optional[str] = None,
    ):
        """Record LLM usage."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.estimated_cost += cost
        
        self.history.append({
            "type": "llm",
            "agent": agent,
            "task_id": task_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        logger.debug(f"LLM usage: {agent} - tokens={prompt_tokens+completion_tokens}, cost=${cost:.4f}")
    
    def add_search_usage(
        self,
        num_searches: int,
        agent: str,
        task_id: Optional[str] = None,
    ):
        """Record search API usage."""
        self.tavily_searches += num_searches
        
        self.history.append({
            "type": "search",
            "agent": agent,
            "task_id": task_id,
            "searches": num_searches,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        logger.debug(f"Search usage: {agent} - searches={num_searches}")
    
    def is_over_limit(self) -> bool:
        """Check if cost limit is exceeded."""
        return self.estimated_cost >= self.cost_limit
    
    def get_remaining_budget(self) -> float:
        """Get remaining budget."""
        return max(0, self.cost_limit - self.estimated_cost)
    
    def should_use_summarization(self) -> bool:
        """Check if we should switch to summarization mode to save costs."""
        return self.estimated_cost >= (self.cost_limit * 0.7)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current cost statistics."""
        return {
            "run_id": self.run_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost, 4),
            "tavily_searches": self.tavily_searches,
            "cost_limit_usd": self.cost_limit,
            "remaining_budget_usd": round(self.get_remaining_budget(), 4),
            "over_limit": self.is_over_limit(),
        }
    
    def get_breakdown(self) -> Dict[str, Any]:
        """Get detailed cost breakdown by agent and task."""
        by_agent = {}
        by_task = {}
        
        for entry in self.history:
            agent = entry.get("agent", "unknown")
            task_id = entry.get("task_id", "unknown")
            
            if agent not in by_agent:
                by_agent[agent] = {"tokens": 0, "cost": 0.0, "searches": 0}
            if task_id not in by_task:
                by_task[task_id] = {"tokens": 0, "cost": 0.0, "searches": 0}
            
            if entry["type"] == "llm":
                tokens = entry["prompt_tokens"] + entry["completion_tokens"]
                by_agent[agent]["tokens"] += tokens
                by_agent[agent]["cost"] += entry["cost"]
                by_task[task_id]["tokens"] += tokens
                by_task[task_id]["cost"] += entry["cost"]
            elif entry["type"] == "search":
                by_agent[agent]["searches"] += entry["searches"]
                by_task[task_id]["searches"] += entry["searches"]
        
        return {
            "by_agent": by_agent,
            "by_task": by_task,
            "history": self.history,
        }


# Run-specific cost trackers
_cost_trackers: Dict[str, CostTracker] = {}


def get_cost_tracker(run_id: str) -> CostTracker:
    """Get or create cost tracker for a run."""
    if run_id not in _cost_trackers:
        _cost_trackers[run_id] = CostTracker(run_id)
    return _cost_trackers[run_id]


def remove_cost_tracker(run_id: str):
    """Remove cost tracker for a completed run."""
    if run_id in _cost_trackers:
        del _cost_trackers[run_id]
