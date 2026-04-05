"""Search Service - Tavily API wrapper with fallback strategies."""

import logging
from typing import Dict, Any, Optional, List
import time
import asyncio

from tavily import TavilyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import get_settings
from models.schemas import SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()


def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Safely get attribute or key from object or dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class SearchService:
    """Service for web search using Tavily API."""
    
    def __init__(self):
        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.total_searches = 0
        self.search_timeout = 10  # 10 second timeout - shorter for faster fallback
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((ConnectionError, OSError)),  # Only retry network errors, NOT timeouts
    )
    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Perform a search using Tavily API with timeout."""
        start_time = time.time()
        
        try:
            kwargs = {
                "query": query[:400],  # Limit query length
                "search_depth": search_depth,
                "max_results": min(max_results, 5),  # Cap at 5
            }
            
            if include_domains:
                kwargs["include_domains"] = include_domains
            if exclude_domains:
                kwargs["exclude_domains"] = exclude_domains
            
            logger.info(f"Tavily search: {query[:60]}...")
            
            # Use sync client via executor (tavily 0.3.3 doesn't have async support)
            response = None
            try:
                loop = asyncio.get_running_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: self.client.search(**kwargs)),
                    timeout=self.search_timeout
                )
                logger.info(f"Search completed")
            except asyncio.CancelledError:
                # Critical: propagate cancellation from outer timeout
                logger.warning(f"Search cancelled by outer timeout")
                raise
            except asyncio.TimeoutError:
                logger.error(f"Tavily search timed out after {self.search_timeout}s")
                return {"results": [], "query": query, "error": "timeout"}
            except Exception as e:
                logger.error(f"Tavily search error: {str(e)}")
                return {"results": [], "query": query, "error": str(e)}
            
            if response is None:
                return {"results": [], "query": query, "error": "No response"}
            
            self.total_searches += 1
            latency = int((time.time() - start_time) * 1000)
            
            # Handle response - could be dict or object
            raw_results = safe_get(response, "results", []) or []
            
            results = []
            for item in raw_results[:max_results]:
                # Handle both dict and object responses
                title = safe_get(item, "title", "")
                url = safe_get(item, "url", "")
                content = safe_get(item, "content", "")
                score = safe_get(item, "score", 0.0)
                
                results.append(SearchResult(
                    title=str(title) if title else "",
                    url=str(url) if url else "",
                    content=str(content)[:1000] if content else "",  # Limit content size
                    score=float(score) if score else 0.0,
                ))
            
            logger.info(f"Search done: {len(results)} results in {latency}ms")
            
            return {
                "query": query,
                "results": results,
                "answer": safe_get(response, "answer"),
                "latency_ms": latency,
            }
            
        except asyncio.CancelledError:
            logger.warning(f"Search operation cancelled")
            raise
        except asyncio.TimeoutError:
            logger.error(f"Tavily search timeout after {self.search_timeout}s")
            raise
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            raise
    
    async def search_with_fallback(
        self,
        query: str,
        entity_name: Optional[str] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Search with fallback strategies."""
        
        # Strategy 1: Direct search
        logger.info(f"Search strategy 1: direct query '{query[:60]}...'")
        try:
            result = await self.search(query, max_results=max_results)
            if result.get("results"):
                logger.info(f"Strategy 1 success: {len(result['results'])} results")
                return result
            logger.info(f"Strategy 1: no results, error={result.get('error')}")
        except Exception as e:
            logger.warning(f"Primary search failed: {type(e).__name__}: {e}")
        
        # Small delay before retry to avoid rate limiting
        await asyncio.sleep(0.5)
        
        # Strategy 2: Simplified query (use first part only)
        simplified_query = " ".join(query.split()[:8])
        logger.info(f"Search strategy 2: simplified query '{simplified_query}'")
        try:
            result = await self.search(simplified_query, max_results=max_results)
            if result.get("results"):
                logger.info(f"Strategy 2 success: {len(result['results'])} results")
                return result
            logger.info(f"Strategy 2: no results, error={result.get('error')}")
        except Exception as e:
            logger.warning(f"Simplified search failed: {type(e).__name__}: {e}")
        
        # Small delay before retry
        await asyncio.sleep(0.5)
        
        # Strategy 3: Entity name only
        if entity_name:
            logger.info(f"Search strategy 3: entity name '{entity_name}'")
            try:
                result = await self.search(entity_name, max_results=max_results)
                if result.get("results"):
                    logger.info(f"Strategy 3 success: {len(result['results'])} results")
                    return result
                logger.info(f"Strategy 3: no results, error={result.get('error')}")
            except Exception as e:
                logger.warning(f"Entity search failed: {type(e).__name__}: {e}")
        
        # Return empty result
        logger.warning(f"All search strategies failed for: {query[:100]}")
        return {
            "query": query,
            "results": [],
            "answer": None,
            "error": "All search strategies failed",
            "latency_ms": 0,
        }
    
    async def search_comparison(
        self,
        entity1: str,
        entity2: str,
        aspect: str,
    ) -> Dict[str, Any]:
        """Search for comparison between two entities."""
        query = f"{entity1} vs {entity2} {aspect} comparison"
        return await self.search_with_fallback(query, max_results=5)
    
    async def search_entity(
        self,
        entity: str,
        aspects: List[str],
    ) -> Dict[str, Any]:
        """Search for multiple aspects of an entity."""
        all_results = []
        
        for aspect in aspects[:3]:  # Limit to 3 aspects
            query = f"{entity} {aspect}"
            result = await self.search(query, max_results=3)
            all_results.extend(result.get("results", []))
        
        return {
            "entity": entity,
            "results": all_results,
            "aspects": aspects,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            "total_searches": self.total_searches,
        }


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get or create search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
