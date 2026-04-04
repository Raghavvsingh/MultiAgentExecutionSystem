"""
Simple LLM Response Cache for Cost Optimization
"""
import hashlib
import json
from typing import Dict, Any, Optional
import time

class LLMCache:
    """Simple in-memory cache for LLM responses."""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
    
    def _hash_key(self, prompt: str, system_prompt: str, model: str) -> str:
        """Generate cache key from prompt."""
        content = f"{system_prompt}||{prompt}||{model}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, prompt: str, system_prompt: str, model: str) -> Optional[Dict[str, Any]]:
        """Get cached response if exists and not expired."""
        key = self._hash_key(prompt, system_prompt, model)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["response"]
            else:
                # Expired - remove
                del self.cache[key]
        return None
    
    def set(self, prompt: str, system_prompt: str, model: str, response: Dict[str, Any]):
        """Cache response."""
        key = self._hash_key(prompt, system_prompt, model)
        self.cache[key] = {
            "response": response,
            "timestamp": time.time()
        }
    
    def clear(self):
        """Clear all cached responses."""
        self.cache.clear()
    
    def size(self) -> int:
        """Get cache size."""
        return len(self.cache)


# Global cache instance
_llm_cache = LLMCache(ttl_seconds=3600)  # 1 hour TTL

def get_llm_cache() -> LLMCache:
    """Get global LLM cache instance."""
    return _llm_cache
