"""LLM Service - OpenAI API wrapper with retry logic and cost tracking."""

import logging
from typing import Dict, Any, Optional, List
import json
import time
import asyncio

from openai import AsyncOpenAI, APITimeoutError, RateLimitError, APIError, APIConnectionError
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log,
)

from backend.config import get_settings
from backend.services.llm_cache import get_llm_cache  # COST OPTIMIZATION: Add caching
logger = logging.getLogger(__name__)
settings = get_settings()


# Token pricing per 1K tokens (GPT-4o-mini)
TOKEN_PRICING = {
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
}


class LLMService:
    """Service for interacting with OpenAI API."""
    
    def __init__(self):
        # Aggressive timeout for faster failure detection
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=45.0,  # 45 second timeout (reduced from 60)
            max_retries=0,  # We handle retries ourselves
        )
        self.model = settings.llm_model
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0
        
        # Cache initialization
        self.cache = get_llm_cache()
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on token usage."""
        pricing = TOKEN_PRICING.get(self.model, TOKEN_PRICING["gpt-4o-mini"])
        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]
        return prompt_cost + completion_cost
    
    @retry(
        stop=stop_after_attempt(2),  # V23: Reduced from 3 to 2 for faster failure
        wait=wait_exponential(multiplier=1, min=1, max=8),  # V23: Faster retry (was 2, 2, 15)
        retry=retry_if_exception_type((APITimeoutError, RateLimitError, APIError, APIConnectionError)),  # Removed asyncio.TimeoutError - must not catch outer timeout
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,  # Reduced from 1500 for faster responses
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate a response from the LLM with caching (COST OPTIMIZATION)."""
        start_time = time.time()
        
        messages = []
        if system_prompt:
            # Truncate system prompt if too long
            system_prompt = system_prompt[:4000]
            messages.append({"role": "system", "content": system_prompt})
        
        # Truncate user prompt if too long
        prompt = prompt[:12000]
        messages.append({"role": "user", "content": prompt})
        
        # COST OPTIMIZATION: Check cache first
        cached_response = self.cache.get(prompt, system_prompt or "", self.model)
        if cached_response:
            self.cache_hits += 1
            logger.info(f"💰 CACHE HIT! Saved LLM call (total hits: {self.cache_hits})")
            return cached_response
        
        self.cache_misses += 1
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        try:
            logger.info(f"Calling LLM API (model={self.model}, max_tokens={max_tokens})...")
            
            response = await self.client.chat.completions.create(**kwargs)
            
            # Track tokens and cost
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            cost = self._calculate_cost(prompt_tokens, completion_tokens)
            
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_cost += cost
            
            latency = int((time.time() - start_time) * 1000)
            content = response.choices[0].message.content
            
            logger.info(f"LLM response: tokens={prompt_tokens+completion_tokens}, cost=${cost:.4f}, latency={latency}ms")
            
            result = {
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cost": cost,
                "latency_ms": latency,
            }
            
            # COST OPTIMIZATION: Cache the response
            self.cache.set(prompt, system_prompt or "", self.model, result)
            
            return result
            
        except APITimeoutError as e:
            logger.error(f"LLM API timeout after {time.time() - start_time:.1f}s")
            raise
        except APIConnectionError as e:
            logger.error(f"LLM API connection error: {e} - Check API key and network")
            raise
        except RateLimitError as e:
            logger.error(f"LLM API rate limit hit: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM API error: {type(e).__name__}: {e}")
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,  # Reduced from 1500 for speed
    ) -> Dict[str, Any]:
        """Generate JSON response from LLM."""
        try:
            response = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
            
            try:
                parsed = json.loads(response["content"])
                response["parsed"] = parsed
                return response
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                response["parsed"] = None
                response["parse_error"] = str(e)
                return response
                
        except Exception as e:
            # Return a minimal response on failure so execution can continue
            logger.error(f"LLM generate_json failed: {e}")
            return {
                "content": "",
                "parsed": None,
                "error": str(e),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0,
                "latency_ms": 0,
            }
    
    async def summarize(
        self,
        content: str,
        max_length: int = 500,
    ) -> str:
        """Summarize content to reduce token usage."""
        system_prompt = """You are a concise summarizer. Summarize the key points while preserving important facts, data, and insights. Be specific and data-driven."""
        
        prompt = f"""Summarize the following content in {max_length} words or less. Focus on:
- Key facts and data points
- Important insights
- Specific details that matter

Content:
{content[:6000]}
"""
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=max_length * 2,
        )
        
        return response["content"]
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost": round(self.total_cost, 4),
        }
    
    def reset_stats(self):
        """Reset usage statistics."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
