"""Executor Agent - RAG pipeline for task execution (v8 - Investor Decision Engine)."""

import json
from typing import Dict, Any, Optional, List
import logging
import re

from agents.base_agent import BaseAgent
from services.search_service import get_search_service, SearchService
from models.schemas import ExecutorOutput

logger = logging.getLogger(__name__)


# ============== V8 SYSTEM PROMPT - INVESTOR DECISION ENGINE ==============
EXECUTOR_SYSTEM_PROMPT = """You are a VC partner making investment decisions. Your analysis determines capital allocation.

# ABSOLUTE RULES (v8 - INVESTOR DECISION ENGINE)

## RULE 1: OVERALL POSITIONING (MANDATORY)
Every output MUST include explicit win/lose analysis:

{
  "overall_positioning": {
    "why_this_wins": [
      "AI matching is 10x faster than manual team formation",
      "Solves acute pain point in hackathons/bootcamps"
    ],
    "why_this_loses": [
      "No network effects → chicken-and-egg problem",
      "Users already have free alternatives (Discord)"
    ]
  }
}

❌ OUTPUT INVALID without clear win vs lose positioning

## RULE 2: MOAT ANALYSIS (CRITICAL)
Every output MUST include defensibility assessment:

{
  "moat_analysis": {
    "defensibility": "LOW",
    "reasons": [
      "No proprietary data advantage",
      "Feature can be copied by Slack/Discord in weeks",
      "No network effects until critical mass"
    ],
    "potential_moats": [
      "Could build data moat if usage scales",
      "University partnerships could create lock-in"
    ]
  }
}

Defensibility levels: HIGH / MEDIUM / LOW
Be BRUTALLY honest about moat strength.

## RULE 3: EXECUTION DIFFICULTY (MANDATORY)
Assess how hard this is to build and scale:

{
  "execution_difficulty": {
    "level": "HIGH",
    "technical_complexity": "MEDIUM - ML matching is commodity tech",
    "market_difficulty": "HIGH - crowded space with entrenched players",
    "user_acquisition": "HIGH - no viral loop, requires paid acquisition"
  }
}

## RULE 4: USER SWITCHING BARRIER (VERY IMPORTANT)
Analyze why users would or wouldn't switch:

{
  "switching_barrier_analysis": {
    "current_behavior": "Users form teams manually via Discord servers, LinkedIn, or word-of-mouth",
    "switching_difficulty": "HIGH",
    "barriers": [
      "Habit: users already have established networks",
      "Network effects: team members use existing tools",
      "Low urgency: current method works 'good enough'"
    ],
    "switching_triggers": [
      "Major pain event (failed team, missed deadline)",
      "Institutional mandate (university requires tool)"
    ]
  }
}

## RULE 5: DOMINANT COMPETITOR REQUIREMENT
Every analysis MUST include at least ONE market leader:
- LinkedIn, Slack, Discord, Notion, GitHub, Figma, Trello, Microsoft Teams

❌ OUTPUT INVALID if no dominant incumbent analyzed

## RULE 6: EXPLICIT WINNER ANALYSIS (PER FEATURE)
comparison_table MUST include winner_by_feature:

{
  "comparison_table": {
    "factors": ["Core Use Case", "Key Feature", "Pricing", "Target", "Strength", "Weakness"],
    "competitors": {
      "Slack": ["Team chat", "Channels", "$7-15/mo", "Teams", "Network effects", "Cost"],
      "Discord": ["Community", "Voice", "Free", "Communities", "Free tier", "Less professional"]
    },
    "your_idea": ["Team matching", "AI pairing", "Freemium", "Students", "Speed", "No network"],
    "winner_by_feature": {
      "Team Formation": "Your Idea (AI matching advantage)",
      "Communication": "Slack (network + integrations)",
      "Cost": "Discord (free tier)"
    }
  }
}

## RULE 7: DATA + IMPLICATION (MANDATORY)
EVERY data point MUST have SO WHAT interpretation:

{
  "data_points_with_implications": [
    {
      "data": "Slack has 12M daily active users",
      "implication": "Massive network effects → 10x differentiation required to compete"
    }
  ]
}

## RULE 8: MEASURABLE CONDITIONS FOR SUCCESS
Conditions must be TESTABLE and OBSERVABLE:

❌ WRONG: "MUST achieve strong adoption"
✅ RIGHT: "MUST achieve 1000 successful team matches in first 6 months"

{
  "conditions_for_success": [
    "MUST: 1000+ team matches in 6 months (proves product-market fit)",
    "MUST: 40%+ user retention after 30 days (proves value)",
    "MUST: 3+ university partnerships signed (proves distribution)"
  ]
}

## RULE 9: BANNED GENERIC PHRASES
INSTANT REJECTION if output contains:
- "market is growing"
- "competition is high"
- "shows promise"
- "has potential"
- "could be viable"

## RULE 10: FINAL VERDICT FORMAT
For recommendation tasks, include complete decision framework:

{
  "verdict": "CONDITIONAL",
  "verdict_reasoning": ["Specific factor 1", "Specific factor 2"],
  "conditions_for_success": ["MUST: measurable condition 1", "MUST: measurable condition 2"],
  "biggest_risk": "Single most critical failure point",
  "execution_difficulty": {"level": "HIGH/MEDIUM/LOW"},
  "moat_analysis": {"defensibility": "HIGH/MEDIUM/LOW"}
}

# OUTPUT STRUCTURE (v8 STRICT)

{
  "summary": "2-3 sentences: key finding + investment implication",
  "key_findings": ["Finding with SO WHAT interpretation"],
  "competitors_identified": {
    "dominant_incumbent": "Market leader name",
    "direct": ["Real products"],
    "indirect": ["Alternatives"]
  },
  "comparison_table": { ... },
  "data_points_with_implications": [{"data": "...", "implication": "..."}],
  "overall_positioning": {
    "why_this_wins": ["..."],
    "why_this_loses": ["..."]
  },
  "moat_analysis": {
    "defensibility": "HIGH/MEDIUM/LOW",
    "reasons": ["..."]
  },
  "execution_difficulty": {
    "level": "HIGH/MEDIUM/LOW",
    "technical_complexity": "...",
    "market_difficulty": "...",
    "user_acquisition": "..."
  },
  "switching_barrier_analysis": {
    "current_behavior": "...",
    "switching_difficulty": "HIGH/MEDIUM/LOW",
    "barriers": ["..."],
    "switching_triggers": ["..."]
  },
  "limitations": ["What we don't know"],
  "key_insight": "NON-OBVIOUS conclusion",
  "strategic_implication": "Clear action",
  "biggest_risk": "Single critical failure point",
  "confidence": 0.0-1.0
}

For FINAL/RECOMMENDATION tasks, also include:
- verdict: YES/NO/CONDITIONAL
- verdict_reasoning: [factors]
- conditions_for_success: [MUST: measurable conditions]

# CONFIDENCE SCORING
- 0.8+: Strong data, clear conclusions
- 0.65-0.8: Good data with gaps
- 0.5-0.65: Limited data, inference
- Below 0.5: Mostly guesswork"""


class ExecutorAgent(BaseAgent):
    """Agent for executing tasks (v8 - Investor Decision Engine)."""
    
    def __init__(self, run_id: str):
        super().__init__(run_id, "executor")
        self.search_service: SearchService = get_search_service()
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single task with investor-grade analysis."""
        task = context.get("task", {})
        task_id = task.get("id", "unknown")
        task_description = task.get("task", "")
        previous_outputs = context.get("previous_outputs", {})
        use_summarization = context.get("use_summarization", False)
        goal_classification = context.get("classification", {})
        retry_feedback = context.get("retry_feedback", "")
        
        if not task_description:
            return {
                "success": False,
                "task_id": task_id,
                "error": "No task description provided",
            }
        
        self.log(f"Executing task {task_id}: {task_description[:50]}...", task_id=task_id)
        
        try:
            # Step 1: Generate smart search queries
            queries = self._generate_search_queries(task_description, goal_classification)
            self.log(f"Searching with {len(queries)} queries", task_id=task_id)
            
            # Step 2: Execute searches
            all_results = []
            for query in queries[:3]:
                results = await self._search(query, task_description)
                all_results.extend(results.get("results", []))
            
            # Deduplicate
            all_results = self._deduplicate_results(all_results)
            self.log(f"Found {len(all_results)} unique search results", task_id=task_id)
            
            if not all_results:
                # Try simpler search
                entities = goal_classification.get("entities", [])
                if entities:
                    results = await self._search(entities[0][:100], task_description)
                    all_results = results.get("results", [])
                
                if not all_results:
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": "No search results found",
                        "sources": [],
                    }
            
            # Step 3: Prepare context
            context_text = self._prepare_context({"results": all_results}, use_summarization)
            
            # Step 4: Generate consultant-grade output with anti-hallucination
            output = await self._generate_deep_intelligence_output(
                task_description,
                context_text,
                previous_outputs,
                goal_classification,
                task_id,
                retry_feedback,
            )
            
            # Extract sources safely
            sources = []
            for r in all_results[:5]:
                url = getattr(r, 'url', None) if hasattr(r, 'url') else r.get('url', '') if isinstance(r, dict) else ''
                if url:
                    sources.append(str(url))
            sources = list(set(sources))
            
            parsed_output = output.get("parsed", {})
            
            # Validate output quality before returning
            quality_check = self._check_output_quality(parsed_output, task_description)
            if not quality_check["passes"]:
                self.log(f"Quality check failed: {quality_check['issues']}", level="warning", task_id=task_id)
                # Adjust confidence based on quality
                try:
                    conf = float(parsed_output.get("confidence", 0))
                    if conf > 0.7:
                        parsed_output["confidence"] = 0.65
                except (TypeError, ValueError):
                    parsed_output["confidence"] = 0.5
            
            # Ensure confidence is always a float
            try:
                parsed_output["confidence"] = float(parsed_output.get("confidence", 0.5))
            except (TypeError, ValueError):
                parsed_output["confidence"] = 0.5
            
            return {
                "success": True,
                "task_id": task_id,
                "output": parsed_output,
                "summary": parsed_output.get("summary", ""),
                "key_findings": parsed_output.get("key_findings", []),
                "comparisons": parsed_output.get("comparisons", []),
                "competitors_identified": parsed_output.get("competitors_identified", []),
                "insights": parsed_output.get("insights", []),
                "data_points": parsed_output.get("data_points", []),
                "feature_matrix": parsed_output.get("feature_matrix"),
                "strategic_implication": parsed_output.get("strategic_implication", ""),
                "sources": sources,
                "confidence": parsed_output.get("confidence", 0.5),
                "limitations": parsed_output.get("limitations", []),
                "raw_response": output.get("content", ""),
            }
            
        except Exception as e:
            self.log(f"Task execution failed: {e}", level="error", task_id=task_id)
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
            }
    
    def _generate_search_queries(
        self,
        task_description: str,
        classification: Dict[str, Any],
    ) -> List[str]:
        """Generate effective search queries from task."""
        entities = classification.get("entities", [])
        domain = classification.get("domain", "")
        
        queries = []
        
        # Primary query from task
        queries.append(task_description[:200])
        
        # Entity-specific queries
        for entity in entities[:2]:
            queries.append(f"{entity} competitors comparison")
            queries.append(f"{entity} pricing features")
        
        # Domain-specific query
        if domain and domain != "general":
            queries.append(f"{domain} market leaders 2024")
        
        return queries[:4]  # Limit to 4 queries
    
    async def _search(
        self,
        query: str,
        task_description: str,
    ) -> Dict[str, Any]:
        """Search for information."""
        
        entity_name = None
        words = task_description.split()
        for i, word in enumerate(words):
            if word.lower() in ["for", "of", "about"] and i + 1 < len(words):
                entity_name = words[i + 1]
                break
        
        result = await self.search_service.search_with_fallback(
            query=query,
            entity_name=entity_name,
            max_results=5,
        )
        
        self.cost_tracker.add_search_usage(1, self.name)
        
        return result
    
    def _deduplicate_results(self, results: List[Any]) -> List[Any]:
        """Remove duplicate results based on URL."""
        seen_urls = set()
        unique = []
        for r in results:
            if hasattr(r, 'url'):
                url = r.url or ''
            elif isinstance(r, dict):
                url = r.get('url', '')
            else:
                url = ''
            
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(r)
        return unique
    
    def _prepare_context(
        self,
        search_results: Dict[str, Any],
        use_summarization: bool,
    ) -> str:
        """Prepare context from search results."""
        results = search_results.get("results", [])
        
        context_parts = []
        for i, result in enumerate(results[:6], 1):
            if hasattr(result, 'title'):
                title = result.title or ""
                url = result.url or ""
                content = result.content or ""
            elif isinstance(result, dict):
                title = result.get('title', '')
                url = result.get('url', '')
                content = result.get('content', '')
            else:
                continue
            
            if use_summarization:
                content = str(content)[:400]
            else:
                content = str(content)[:1000]
            
            context_parts.append(f"SOURCE {i}: {title}\nURL: {url}\n{content}\n")
        
        return "\n".join(context_parts)
    
    def _check_output_quality(self, output: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """Check output quality for anti-hallucination compliance."""
        issues = []
        
        output_str = json.dumps(output, default=str).lower()
        
        # Check for generic placeholders
        generic_terms = ["platform a", "platform b", "company x", "entity 1", "entity 2", "[product]"]
        for term in generic_terms:
            if term in output_str:
                issues.append(f"Contains generic placeholder: {term}")
        
        # Check for overly generic statements without context
        generic_statements = ["market is growing", "competition is high", "industry is expanding"]
        for stmt in generic_statements:
            if stmt in output_str and "because" not in output_str and "due to" not in output_str:
                issues.append(f"Generic statement without context: {stmt}")
        
        # Check if competitors are named (for competitor-related tasks)
        if "competitor" in task_description.lower() or "compare" in task_description.lower():
            competitors = output.get("competitors_identified", [])
            if not competitors or len(competitors) < 2:
                issues.append("Missing real competitor names")
        
        # Check for comparisons in comparison tasks
        if "compare" in task_description.lower() or "vs" in task_description.lower():
            comparisons = output.get("comparisons", [])
            if not comparisons:
                issues.append("Missing explicit comparisons")
        
        return {
            "passes": len(issues) == 0,
            "issues": issues,
        }
    
    async def _generate_deep_intelligence_output(
        self,
        task_description: str,
        context_text: str,
        previous_outputs: Dict[str, Any],
        classification: Dict[str, Any],
        task_id: str,
        retry_feedback: str = "",
    ) -> Dict[str, Any]:
        """Generate investor-grade output (v6)."""
        
        # Previous context - extract competitor info
        prev_context = ""
        known_competitors = []
        if previous_outputs:
            relevant = []
            for tid, output in list(previous_outputs.items())[:3]:
                if isinstance(output, dict):
                    summary = output.get("summary", "")
                    # Handle both old and new competitor formats
                    competitors = output.get("competitors_identified", [])
                    if isinstance(competitors, dict):
                        known_competitors.extend(competitors.get("direct", []))
                        known_competitors.extend(competitors.get("indirect", []))
                    elif isinstance(competitors, list):
                        known_competitors.extend(competitors)
                    if summary:
                        relevant.append(f"{tid}: {summary[:150]}")
            if relevant:
                prev_context = f"\nPRIOR ANALYSIS:\n" + "\n".join(relevant)
            if known_competitors:
                prev_context += f"\nCOMPETITORS IDENTIFIED: {', '.join(set(known_competitors[:8]))}"
        
        # Build task-specific instructions
        entities = classification.get("entities", [])
        entities_str = ", ".join(entities) if entities else "the subject"
        goal_type = classification.get("goal_type", "analysis")
        domain = classification.get("domain", "general")
        
        task_specific = self._get_task_specific_instructions(task_description)
        
        # Retry feedback if this is a retry
        feedback_section = ""
        if retry_feedback:
            feedback_section = f"""
⚠️ PREVIOUS OUTPUT REJECTED. MANDATORY FIXES:
{retry_feedback}

YOU MUST:
1. Include comparison_table with real products (Slack, Notion, Discord, etc.)
2. Include key_insight (non-obvious conclusion)
3. Include strategic_implication (clear action)
4. NO generic phrases - every statement needs "SO WHAT" interpretation
5. Be CRITICAL - identify weaknesses and failure risks
"""
        
        # Determine if comparison is needed
        needs_comparison = any(kw in task_description.lower() for kw in 
            ["competitor", "compare", "vs", "versus", "alternative", "landscape", "player", "analysis"])
        
        comparison_instruction = ""
        if needs_comparison:
            comparison_instruction = """
MANDATORY COMPARISON TABLE FORMAT:
{
  "comparison_table": {
    "factors": ["Core Use Case", "Key Feature", "Pricing", "Target Users", "Strength", "Weakness"],
    "competitors": {
      "Slack": ["Team chat", "Channels", "$7-15/mo", "Teams", "Integrations", "Cost"],
      "Discord": ["Community", "Voice", "Free/$10", "Communities", "Free tier", "Professional image"]
    },
    "your_idea": ["Your use case", "Your feature", "Your pricing", "Your target", "Your strength", "Your weakness"],
    "winner_analysis": "Who wins overall and why. What gap exists."
  }
}
OUTPUT IS INVALID WITHOUT comparison_table.
"""
        
        # Build the main prompt
        prompt = f"""TASK: {task_description}
IDEA/ENTITIES: {entities_str}
DOMAIN: {domain}
{task_specific}
{feedback_section}
{comparison_instruction}

SEARCH DATA (USE ONLY THIS - NO FABRICATION):
{context_text[:5500]}
{prev_context}

INVESTOR-GRADE RULES:
1. COMPETITORS: Real products only (Slack, Notion, Discord, LinkedIn, GitHub)
   - NEVER: NGOs, programs, foundations, initiatives
2. COMPARISON TABLE: Include for any competitor task (MANDATORY)
3. DATA INTERPRETATION: Every fact must include "SO WHAT does this mean?"
4. CRITICAL THINKING: Challenge the idea, identify WHY it might FAIL
5. key_insight: Non-obvious conclusion that challenges assumptions (MANDATORY)
6. strategic_implication: Clear action recommendation (MANDATORY)

Output JSON: summary, key_findings, competitors_identified, comparison_table, data_points, insights, limitations, key_insight, strategic_implication, confidence"""

        response = await self.llm_service.generate_json(
            prompt=prompt,
            system_prompt=EXECUTOR_SYSTEM_PROMPT,
            temperature=0.2,  # Low for factual, decisive output
            max_tokens=2000,
        )
        
        self.track_llm_usage(response, task_id)
        
        return response
    
    def _get_task_specific_instructions(self, task_description: str) -> str:
        """Get task-specific instructions (v6 - Investor Grade)."""
        task_lower = task_description.lower()
        
        if "feature" in task_lower or "matrix" in task_lower:
            return """TASK TYPE: Feature Comparison
- comparison_table REQUIRED with features as factors
- Real products only: Slack, Notion, Discord, Trello, Figma
- State winner for EACH dimension with WHY
- Identify the GAP your idea can fill"""
        
        elif "pricing" in task_lower:
            return """TASK TYPE: Pricing Analysis
- Use ranges: "$5-15/month" not "$12.47/month"
- Include free tiers if they exist
- Interpret pricing: "Premium pricing → limited to enterprises"
- State "pricing not public" if unknown"""
        
        elif "swot" in task_lower:
            return """TASK TYPE: SWOT Analysis
- Each point MUST be relative to named competitors
- Each point MUST include SO WHAT implication
- Weaknesses: be brutally honest about failure risks
- Threats: identify what could kill this idea"""
        
        elif "competitor" in task_lower or "landscape" in task_lower:
            return """TASK TYPE: Competitor Analysis
- comparison_table REQUIRED (output invalid without it)
- ONLY real products: Notion, Slack, Discord, LinkedIn, GitHub, etc.
- NEVER: NGOs, programs, foundations, initiatives
- State who WINS each dimension and WHY
- Identify the exploitable GAP"""
        
        elif "recommend" in task_lower or "strategic" in task_lower or "verdict" in task_lower or "conclusion" in task_lower or "final" in task_lower:
            return """TASK TYPE: Final Recommendation
REQUIRED OUTPUT:
{
  "verdict": "YES" | "NO" | "CONDITIONAL",
  "verdict_reasoning": ["Factor 1", "Factor 2", "Factor 3"],
  "conditions_for_success": ["MUST achieve X", "MUST solve Y", "MUST differentiate on Z"]
}
- NO vague language: "could work", "shows promise", "has potential"
- Be DECISIVE: make a clear call
- If CONDITIONAL: list 2-3 HARD make-or-break conditions"""
        
        elif "market" in task_lower:
            return """TASK TYPE: Market Analysis
- Use ranges for market size, not precise fake numbers
- Interpret data: "Large market → attractive but competitive"
- Name key players (real companies only)
- State limitations clearly"""
        
        elif "risk" in task_lower or "challenge" in task_lower or "weakness" in task_lower:
            return """TASK TYPE: Risk/Challenge Analysis
- Be PESSIMISTIC - assume things go wrong
- Identify specific failure modes
- Rank by likelihood × impact
- State what would KILL this idea"""
        
        return """GENERAL ANALYSIS:
- comparison_table if comparing anything
- key_insight (non-obvious, challenges assumptions)
- strategic_implication (clear action)
- Interpret all data: every fact needs SO WHAT
- Be critical: identify weaknesses and failure risks"""
