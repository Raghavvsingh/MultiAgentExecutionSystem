"""Executor Agent - RAG pipeline for task execution (v12 - MASTER GREYBOX)."""

import json
from typing import Dict, Any, Optional, List
import logging
import re

from agents.base_agent import BaseAgent
from services.search_service import get_search_service, SearchService
from models.schemas import ExecutorOutput, GreyboxTaskOutput, AnalysisCaseType
from agents.greybox_prompts import (
    MASTER_GREYBOX_SYSTEM_PROMPT,
    FINAL_VERDICT_SYSTEM_PROMPT,
    PATCH_SYSTEM_PROMPT,
    BANNED_GENERIC_PHRASES,
    COMPARISON_INTELLIGENCE_PROMPT,
    NON_GENERIC_INSIGHT_PROMPT,
    PER_TASK_COMPARISON_PROMPT,
    DEPTH_STRUCTURE_PROMPT,
    TASK_INSIGHT_ANGLES,
    TASK_FOCUS_MAP,
    detect_case_type,
    validate_comparison_output,
    validate_insight_quality,
    validate_insight_depth,
    validate_per_task_comparison,
    check_insight_repetition,
    get_task_focus
)

logger = logging.getLogger(__name__)


# ============== COMPARISON CONTROLLER (V14) ==============

# ============== V18: DOMAIN COMPETITOR MAP (EXPANDED) ==============
# ONLY these competitors are valid for each domain - enforces domain correctness
CATEGORY_COMPETITOR_MAP = {
    "collaboration": ["Slack", "Microsoft Teams", "Discord", "Zoom", "Google Chat"],
    "project_management": ["Asana", "Monday.com", "Jira", "Trello", "ClickUp", "Basecamp"],
    "edtech": ["Coursera", "Udemy", "LinkedIn Learning", "Skillshare", "Khan Academy", "edX"],
    "marketplace": ["Upwork", "Fiverr", "Toptal", "Freelancer", "99designs"],
    "social": ["LinkedIn", "Twitter/X", "Facebook", "Instagram", "TikTok"],
    "productivity": ["Notion", "Evernote", "Obsidian", "Roam Research", "Coda"],
    "developer": ["GitHub", "GitLab", "Bitbucket", "Stack Overflow", "Replit"],
    "crm": ["Salesforce", "HubSpot", "Pipedrive", "Zoho CRM", "Freshsales"],
    # V18: NEW DOMAINS
    "fitness": ["MyFitnessPal", "Fitbit", "Nike Training Club", "Strava", "Peloton", "Freeletics"],
    "health": ["Headspace", "Calm", "Noom", "WW (WeightWatchers)", "Hinge Health"],
    "fintech": ["Stripe", "Square", "PayPal", "Robinhood", "Plaid", "Wise"],
    "ecommerce": ["Shopify", "WooCommerce", "BigCommerce", "Magento", "Squarespace"],
    "gaming": ["Steam", "Epic Games", "Unity", "Roblox", "Twitch"],
    "travel": ["Airbnb", "Booking.com", "Expedia", "Tripadvisor", "Kayak"],
    "food": ["DoorDash", "Uber Eats", "Grubhub", "Instacart", "HelloFresh"],
    "general": ["Notion", "Slack", "GitHub"]
}

# Reverse map: competitor -> domain (for validation)
COMPETITOR_TO_DOMAIN = {}
for domain, competitors in CATEGORY_COMPETITOR_MAP.items():
    for comp in competitors:
        COMPETITOR_TO_DOMAIN[comp.lower()] = domain

# Invalid cross-category pairs - these should NEVER be compared
INVALID_COMPARISON_PAIRS = {
    ("Slack", "Coursera"), ("Coursera", "Slack"),
    ("Discord", "Udemy"), ("Udemy", "Discord"),
    ("Microsoft Teams", "LinkedIn Learning"), ("LinkedIn Learning", "Microsoft Teams"),
    ("Upwork", "Slack"), ("Slack", "Upwork"),
    ("Fiverr", "Discord"), ("Discord", "Fiverr"),
    # V18: More invalid pairs
    ("Notion", "MyFitnessPal"), ("MyFitnessPal", "Notion"),
    ("Slack", "Fitbit"), ("Fitbit", "Slack"),
    ("GitHub", "Peloton"), ("Peloton", "GitHub"),
}

# Generic insight phrases to reject - V18 EXPANDED
GENERIC_INSIGHT_PHRASES = [
    "team formation gap",
    "collaboration tools focus",
    "market is growing",
    "competition is high",
    "has potential",
    "shows promise",
    "opportunity exists",
    "room for innovation",
    "underserved market",
    "first mover advantage",
    # V18: More generic phrases to reject
    "users prefer personalization",
    "there is demand",
    "growing trend",
    "users want",
    "significant opportunity",
    "large market",
    "fragmented market",
    "early stage market",
]

# V18: Placeholder patterns that indicate hallucinated/fake output
PLACEHOLDER_PATTERNS = [
    "platform a", "platform b",
    "entity a", "entity b",
    "company x", "company y",
    "startup x", "startup y",
    "[product]", "[company]", "[competitor]",
    "some apps", "various tools", "multiple platforms",
]

# ============== V17: DRIFT DETECTION KEYWORDS ==============
# Keywords that indicate domain drift - if these appear in output for unrelated goals, reject
INVALID_DOMAIN_KEYWORDS = [
    "healthcare", "hospital", "medical", "patient", "clinical",
    "disco", "nightclub", "party", "entertainment venue",
    "restaurant", "food delivery", "recipe",
    "real estate", "property", "housing",
    "automotive", "car", "vehicle",
    "banking", "loan", "mortgage",
    "insurance", "policy", "coverage",
    "pharmaceutical", "drug", "medication",
    "manufacturing", "factory", "industrial",
    "agriculture", "farming", "crop",
    "mining", "extraction", "mineral",
]

# Domain-specific valid keywords mapping - V18 EXPANDED
VALID_DOMAIN_KEYWORDS = {
    "collaboration": ["team", "chat", "messaging", "communication", "workspace", "channel", "meeting"],
    "project_management": ["task", "project", "workflow", "kanban", "sprint", "agile", "board"],
    "edtech": ["learning", "course", "education", "student", "training", "skill", "tutorial"],
    "marketplace": ["freelance", "gig", "hire", "talent", "contractor", "job", "client"],
    "social": ["network", "connect", "community", "profile", "follower", "feed"],
    "productivity": ["notes", "knowledge", "writing", "document", "organize", "wiki"],
    "developer": ["code", "git", "repository", "developer", "engineering", "deploy"],
    "crm": ["sales", "customer", "pipeline", "lead", "deal", "contact"],
    # V18: New domain keywords
    "fitness": ["workout", "exercise", "gym", "fitness", "training", "calories", "steps", "activity"],
    "health": ["meditation", "wellness", "mindfulness", "sleep", "mental", "therapy", "diet"],
    "fintech": ["payment", "transfer", "invest", "trading", "crypto", "banking", "finance"],
    "ecommerce": ["shop", "store", "product", "cart", "checkout", "inventory", "seller"],
    "gaming": ["game", "player", "stream", "esports", "multiplayer", "leaderboard"],
    "travel": ["booking", "hotel", "flight", "trip", "vacation", "destination", "itinerary"],
    "food": ["delivery", "restaurant", "meal", "order", "menu", "recipe", "grocery"],
}


def detect_category(goal: str) -> str:
    """V18: Detect the business category from the goal to select appropriate competitors."""
    goal_lower = goal.lower()
    
    # V18: Check in order of specificity (most specific first)
    if any(kw in goal_lower for kw in ["fitness", "workout", "exercise", "gym", "training app", "health tracker"]):
        return "fitness"
    elif any(kw in goal_lower for kw in ["mental health", "meditation", "wellness", "mindfulness", "weight loss"]):
        return "health"
    elif any(kw in goal_lower for kw in ["payment", "fintech", "banking app", "investing", "trading", "crypto"]):
        return "fintech"
    elif any(kw in goal_lower for kw in ["ecommerce", "online store", "shopping", "retail", "marketplace selling"]):
        return "ecommerce"
    elif any(kw in goal_lower for kw in ["gaming", "game", "esports", "streaming games"]):
        return "gaming"
    elif any(kw in goal_lower for kw in ["travel", "hotel", "booking", "flight", "vacation"]):
        return "travel"
    elif any(kw in goal_lower for kw in ["food delivery", "restaurant", "meal", "grocery", "recipe app"]):
        return "food"
    elif any(kw in goal_lower for kw in ["team", "collaboration", "chat", "communication", "meeting"]):
        return "collaboration"
    elif any(kw in goal_lower for kw in ["project", "task", "workflow", "kanban", "agile"]):
        return "project_management"
    elif any(kw in goal_lower for kw in ["learning", "education", "course", "training", "skill"]):
        return "edtech"
    elif any(kw in goal_lower for kw in ["marketplace", "freelance", "gig", "hire", "talent"]):
        return "marketplace"
    elif any(kw in goal_lower for kw in ["social", "network", "connect", "community"]):
        return "social"
    elif any(kw in goal_lower for kw in ["productivity", "notes", "knowledge", "writing"]):
        return "productivity"
    elif any(kw in goal_lower for kw in ["developer", "code", "git", "engineering", "devops"]):
        return "developer"
    elif any(kw in goal_lower for kw in ["crm", "sales", "customer", "pipeline"]):
        return "crm"
    else:
        return "general"


def validate_competitors_domain(competitors: list, expected_domain: str) -> tuple:
    """V18: Validate that ALL competitors belong to the expected domain.
    Returns (is_valid, wrong_competitors, correct_competitors)
    """
    wrong = []
    correct = []
    expected_competitors = [c.lower() for c in CATEGORY_COMPETITOR_MAP.get(expected_domain, [])]
    
    for comp in competitors:
        comp_lower = comp.lower()
        actual_domain = COMPETITOR_TO_DOMAIN.get(comp_lower)
        
        if actual_domain is None:
            # Unknown competitor - check if it matches valid domain keywords
            domain_keywords = VALID_DOMAIN_KEYWORDS.get(expected_domain, [])
            if any(kw in comp_lower for kw in domain_keywords):
                correct.append(comp)
            else:
                wrong.append(comp)
        elif actual_domain != expected_domain:
            wrong.append(f"{comp} (belongs to {actual_domain}, not {expected_domain})")
        else:
            correct.append(comp)
    
    return (len(wrong) == 0, wrong, correct)


def get_comparison_entities(goal: str, startup_name: str = "Proposed Startup") -> tuple:
    """Get the two entities to use for comparison based on goal category.
    Returns (dominant_incumbent, startup_name)
    """
    category = detect_category(goal)
    competitors = CATEGORY_COMPETITOR_MAP.get(category, CATEGORY_COMPETITOR_MAP["general"])
    dominant = competitors[0]  # First one is the dominant incumbent
    return (dominant, startup_name, category, competitors)


def validate_comparison_entities(rows: list, expected_entities: tuple) -> tuple:
    """Validate that comparison rows use consistent entities.
    Returns (is_valid, error_message)
    """
    if not rows:
        return (False, "No comparison rows")
    
    if len(rows) < 3:
        return (False, f"Only {len(rows)} rows, need minimum 3")
    
    expected_a, expected_b = expected_entities[0], expected_entities[1]
    entities_found = set()
    
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            return (False, f"Row {i} is not a dict")
        
        entity_a = row.get("entity_a", "")
        entity_b = row.get("entity_b", "")
        entities_found.add(entity_a)
        entities_found.add(entity_b)
        
        if not row.get("winner"):
            return (False, f"Row {i} missing winner")
        
        # Check for cross-category invalid pairs
        if (entity_a, entity_b) in INVALID_COMPARISON_PAIRS:
            return (False, f"Invalid cross-category comparison: {entity_a} vs {entity_b}")
    
    # Should only have exactly 2 unique entities
    if len(entities_found) != 2:
        return (False, f"Inconsistent entities: found {len(entities_found)} ({entities_found}), expected 2")
    
    return (True, "Valid")


class ExecutorAgent(BaseAgent):
    """Agent for executing tasks (v15 - Real Multi-Call Pipeline)."""
    
    def __init__(self, run_id: str):
        super().__init__(run_id, "executor")
        self.search_service: SearchService = get_search_service()
    
    def _build_strict_context(
        self,
        goal: str,
        task_description: str,
        previous_outputs: Dict[str, Any],
        category: str = "",
    ) -> str:
        """V17: Build strict context block to prevent domain drift with explicit banned domains."""
        
        # Summarize previous outputs
        prev_summary = ""
        if previous_outputs:
            summaries = []
            for tid, output in list(previous_outputs.items())[:3]:
                if isinstance(output, dict):
                    s = output.get("summary", "")[:100]
                    if s:
                        summaries.append(f"- {tid}: {s}")
            if summaries:
                prev_summary = "\n".join(summaries)
        
        # V17: Get valid keywords for this domain
        valid_keywords = VALID_DOMAIN_KEYWORDS.get(category, [])
        valid_keywords_str = ", ".join(valid_keywords) if valid_keywords else "general business"
        
        strict_context = f"""
═══════════════════════════════════════════════════════════════
🎯 STRICT CONTEXT GROUNDING (DO NOT IGNORE)
═══════════════════════════════════════════════════════════════

ORIGINAL GOAL:
{goal}

ALLOWED DOMAIN: {category or 'general'}
ALLOWED KEYWORDS: {valid_keywords_str}

🚫 BANNED DOMAINS (DO NOT MENTION):
- healthcare, hospital, medical, clinical
- disco, nightclub, entertainment venue
- restaurant, food delivery
- real estate, property, housing
- automotive, car, vehicle
- banking, loan, mortgage
- insurance, pharmaceutical
- manufacturing, agriculture, mining

STRICT RULES (MANDATORY):
1. Stay ONLY within the "{category or 'general'}" domain
2. DO NOT introduce ANY unrelated industries listed above
3. DO NOT change the use-case or target users from the original goal
4. DO NOT hallucinate facts, tools, companies, or data
5. If data is unavailable → say "No reliable data available"
6. ALL outputs MUST directly relate to: {goal[:100]}
7. If your output drifts from the goal → STOP and refocus

PREVIOUS TASK OUTPUTS:
{prev_summary if prev_summary else "None yet"}

CURRENT TASK:
{task_description}

═══════════════════════════════════════════════════════════════
"""
        return strict_context
    
    def _check_domain_drift(self, output: Dict[str, Any], category: str) -> List[str]:
        """V17: Check output for domain drift issues."""
        drift_issues = []
        output_str = json.dumps(output, default=str).lower()
        
        # Check for invalid domain keywords
        for keyword in INVALID_DOMAIN_KEYWORDS:
            if keyword in output_str:
                drift_issues.append(f"domain_drift: Found invalid keyword '{keyword}'")
        
        # Check if valid domain keywords are present (at least some)
        valid_keywords = VALID_DOMAIN_KEYWORDS.get(category, [])
        if valid_keywords:
            found_valid = sum(1 for kw in valid_keywords if kw in output_str)
            if found_valid == 0:
                drift_issues.append(f"domain_drift: No valid {category} keywords found")
        
        return drift_issues
    
    def _validate_output_v18(
        self,
        output: Dict[str, Any],
        category: str,
        is_final_task: bool,
        valid_competitors: list,
    ) -> Dict[str, Any]:
        """V18: Comprehensive output validation for consultant-grade quality.
        
        Returns dict with:
        - is_valid: bool
        - issues: list of issues found
        - score_penalties: dict of penalty amounts
        - suggestions: list of fixes
        """
        issues = []
        penalties = {}
        suggestions = []
        
        output_str = json.dumps(output, default=str).lower()
        
        # ============== V18: DOMAIN VALIDATION ==============
        competitors = output.get("competitors_identified", {})
        if isinstance(competitors, dict):
            all_comps = competitors.get("direct", []) + competitors.get("indirect", [])
        else:
            all_comps = competitors if isinstance(competitors, list) else []
        
        if all_comps:
            is_valid_domain, wrong_comps, _ = validate_competitors_domain(all_comps, category)
            if not is_valid_domain:
                issues.append(f"wrong_domain_competitors: {wrong_comps}")
                penalties["wrong_domain"] = 0.4
                correct_comps = CATEGORY_COMPETITOR_MAP.get(category, [])[:5]
                suggestions.append(f"Use {category} competitors: {', '.join(correct_comps)}")
        
        # ============== V18: PLACEHOLDER DETECTION ==============
        for placeholder in PLACEHOLDER_PATTERNS:
            if placeholder in output_str:
                issues.append(f"placeholder_detected: {placeholder}")
                penalties["placeholder"] = 0.3
                suggestions.append("Use real company/product names, not placeholders")
                break
        
        # ============== V18: COMPARISON VALIDATION (FINAL TASK) ==============
        if is_final_task:
            comparison = output.get("comparison_table") or output.get("comparison")
            if not comparison or not isinstance(comparison, dict):
                issues.append("missing_comparison_block")
                penalties["no_comparison"] = 0.3
                suggestions.append("Add comparison block with features/pricing/target_users/winner")
            else:
                rows = comparison.get("rows", [])
                if len(rows) < 3:
                    issues.append(f"insufficient_comparison_rows: {len(rows)}")
                    penalties["weak_comparison"] = 0.15
                
                # Check for missing winners
                no_winner_count = sum(1 for r in rows if isinstance(r, dict) and not r.get("winner"))
                if no_winner_count > 0:
                    issues.append(f"missing_winners: {no_winner_count} rows")
                    penalties["no_winners"] = 0.2
        
        # ============== V18: ANTI-GENERIC INSIGHT ==============
        insight = str(output.get("key_insight", ""))
        insight_lower = insight.lower()
        
        for phrase in GENERIC_INSIGHT_PHRASES:
            if phrase in insight_lower:
                issues.append(f"generic_insight: contains '{phrase}'")
                penalties["generic_insight"] = 0.2
                suggestions.append("Insight must include WHY it matters and WHAT decision it leads to")
                break
        
        # V18: Check insight has cause + implication
        if insight and len(insight) > 20:
            has_cause = any(word in insight_lower for word in ["because", "since", "due to", "as a result of"])
            has_implication = any(word in insight_lower for word in ["therefore", "thus", "implies", "means", "suggests", "indicates"])
            if not has_cause and not has_implication:
                issues.append("insight_lacks_reasoning: no cause/implication")
                penalties["weak_insight"] = 0.1
                suggestions.append("Add 'because...' (cause) or 'therefore...' (implication) to insight")
        
        # ============== V18: ANTI-HALLUCINATION ==============
        # Check for standalone "no reliable data" without inference
        if "no reliable data available" in output_str:
            # If it's standalone without any inference, flag it
            data_points = output.get("data_points", [])
            facts = output.get("facts", [])
            if len(data_points) < 2 and len(facts) < 2:
                issues.append("excessive_no_data_claims")
                penalties["hallucination_risk"] = 0.2
                suggestions.append("If data is missing, infer from competitor behavior")
        
        # ============== V18: CONCLUSION STRENGTH ==============
        if is_final_task:
            verdict = output.get("final_verdict", {})
            if isinstance(verdict, dict):
                verdict_val = str(verdict.get("verdict", "")).upper()
                if verdict_val not in ["YES", "NO", "CONDITIONAL"]:
                    issues.append("weak_conclusion: unclear verdict")
                    penalties["weak_conclusion"] = 0.2
                
                args_for = verdict.get("arguments_for", [])
                args_against = verdict.get("arguments_against", [])
                if len(args_for) < 2 or len(args_against) < 2:
                    issues.append("insufficient_arguments: need 2+ for and 2+ against")
                    penalties["weak_arguments"] = 0.15
        
        total_penalty = sum(penalties.values())
        is_valid = total_penalty < 0.5 and "wrong_domain" not in penalties
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "penalties": penalties,
            "total_penalty": total_penalty,
            "suggestions": suggestions,
        }
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single task with real multi-call pipeline (v15).
        
        V15 Architecture:
        - Tasks T1-T4: THINKING only (facts, insights, risks)
        - Task T5 (final): STRUCTURING (comparison table + verdict)
        - Entity locking via global_context
        - No simulated multi-call in prompts
        """
        task = context.get("task", {})
        task_id = task.get("id", "unknown")
        task_description = task.get("task", "")
        previous_outputs = context.get("previous_outputs", {})
        use_summarization = context.get("use_summarization", False)
        goal_classification = context.get("classification", {})
        retry_feedback = context.get("retry_feedback", "")
        shared_memory = context.get("shared_memory", {})
        is_patch_retry = context.get("is_patch_retry", False)
        
        # V15: Global context with locked entities
        global_context = context.get("global_context", {})
        
        # V15: Detect if this is the final task
        is_final_task = context.get("is_final_task", False)
        total_tasks = context.get("total_tasks", 5)
        task_index = context.get("task_index", 0)
        
        # Also detect from task description
        if any(kw in task_description.lower() for kw in ["final", "verdict", "recommend", "conclusion", "strategic"]):
            is_final_task = True
        
        # V15: Use locked entities from global context (or detect new)
        entity_a = global_context.get("entity_a")
        entity_b = global_context.get("entity_b")
        category = global_context.get("category")
        
        if not entity_a or not entity_b:
            # Fallback to detection
            goal = goal_classification.get("goal", task_description)
            entity_a, entity_b, category, valid_competitors = get_comparison_entities(goal)
        else:
            valid_competitors = CATEGORY_COMPETITOR_MAP.get(category, ["Slack", "Microsoft Teams"])
        
        self.log(f"V15: entity_a={entity_a}, entity_b={entity_b}, final={is_final_task}", task_id=task_id)
        
        if not task_description:
            return {
                "success": False,
                "task_id": task_id,
                "error": "No task description provided",
            }
        
        self.log(f"Executing task {task_id}: {task_description[:50]}...", task_id=task_id)
        
        try:
            # V15: Use category-specific competitors
            known_competitors = valid_competitors[:3]
            if shared_memory.get("competitors"):
                known_competitors = list(set(known_competitors + shared_memory.get("competitors", [])[:2]))
            
            self.log(f"Using competitors: {known_competitors}", task_id=task_id)
            
            # Step 1: Generate smart search queries (COST OPTIMIZED: 2 max instead of 3-4)
            queries = self._generate_search_queries(task_description, goal_classification)
            self.log(f"Searching with {len(queries)} queries", task_id=task_id)
            
            # Step 2: Execute searches (COST OPTIMIZED: Limit to 2 queries, 4 results each)
            all_results = []
            for query in queries[:2]:  # COST OPTIMIZATION: Max 2 queries (was 3)
                results = await self._search(query, task_description, max_results=4)  # Max 4 results (was 5)
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
            
            # V15: Include locked entity info
            context_text += f"\n\nLOCKED ENTITIES: {entity_a} vs {entity_b}"
            context_text += f"\nCATEGORY: {category}"
            context_text += f"\nVALID COMPETITORS: {', '.join(valid_competitors)}"
            
            # V15: Include accumulated insights to prevent repetition
            existing_insights = global_context.get("insights", [])
            if existing_insights:
                context_text += f"\n\nPREVIOUS INSIGHTS (DO NOT REPEAT): {'; '.join(existing_insights[:3])}"
            
            # Step 4: Generate output using REAL multi-call pipeline
            output = await self._generate_deep_intelligence_output(
                task_description,
                context_text,
                previous_outputs,
                goal_classification,
                task_id,
                retry_feedback,
                is_final_task=is_final_task,
                comparison_entities=(entity_a, entity_b),
                valid_competitors=valid_competitors,
                global_context=global_context,  # V15: Pass global context
            )
            
            # Check if output generation failed
            if output is None:
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": "LLM output generation failed",
                    "sources": [],
                }
            
            # Extract sources safely
            sources = []
            for r in all_results[:5]:
                url = getattr(r, 'url', None) if hasattr(r, 'url') else r.get('url', '') if isinstance(r, dict) else ''
                if url:
                    sources.append(str(url))
            sources = list(set(sources))
            
            parsed_output = output.get("parsed", {}) or {}
            
            # V6 DEBUGGING: Log raw LLM output structure
            self.log(f"RAW LLM OUTPUT TYPE: {type(parsed_output).__name__}", task_id=task_id)
            if isinstance(parsed_output, dict):
                self.log(f"RAW LLM KEYS: {list(parsed_output.keys())[:10]}", task_id=task_id)
            
            # CRITICAL FIX: Handle list vs dict - LLM may return list
            if isinstance(parsed_output, list):
                self.log(f"LLM returned list, extracting first element", level="warning", task_id=task_id)
                parsed_output = parsed_output[0] if len(parsed_output) > 0 and isinstance(parsed_output[0], dict) else {}
            
            # STRICT: Reject non-dict output
            if not isinstance(parsed_output, dict):
                self.log(f"LLM returned non-dict output type: {type(parsed_output).__name__}, wrapping", level="warning", task_id=task_id)
                parsed_output = {"raw_output": parsed_output, "summary": str(parsed_output)[:500] if parsed_output else ""}
            
            # SCHEMA NORMALIZATION: Unify comparison -> comparison_table
            if "comparison" in parsed_output and "comparison_table" not in parsed_output:
                parsed_output["comparison_table"] = parsed_output.pop("comparison")
            
            # V6: Ensure required fields exist with strict defaults
            parsed_output = self._ensure_required_fields(parsed_output, task_description)
            
            # V6 DEBUGGING: Log structure after normalization
            ct = parsed_output.get("comparison_table", {})
            fv = parsed_output.get("final_verdict", {})
            self.log(
                f"V6 STRUCTURE CHECK: comparison_rows={len(ct.get('rows', []))}, "
                f"verdict={fv.get('verdict', 'MISSING')}, "
                f"key_insight_len={len(str(parsed_output.get('key_insight', '')))}",
                task_id=task_id
            )
            
            # V11: Self-check - verify critical components before returning
            self_check = self._self_check_output(parsed_output, task_description)
            if not self_check["passes"]:
                self.log(f"Self-check issues: {self_check['issues']}", level="warning", task_id=task_id)
                # Try to auto-fix simple issues
                parsed_output = self._auto_fix_output(parsed_output, self_check["issues"], known_competitors)
            
            # Calculate dynamic confidence based on actual factors (NO HARDCODING)
            confidence_calc = self._calculate_confidence(
                search_results=all_results,
                output=parsed_output,
                quality_check=self_check
            )
            parsed_output["confidence"] = confidence_calc["confidence"]
            parsed_output["confidence_factors"] = confidence_calc["factors"]
            parsed_output["confidence_breakdown"] = confidence_calc.get("confidence_breakdown", {})
            
            self.log(
                f"Confidence: {confidence_calc['confidence']:.2f} "
                f"(search={confidence_calc['factors']['search_quality']:.2f}, "
                f"data={confidence_calc['factors']['data_availability']:.2f}, "
                f"credibility={confidence_calc['factors']['source_credibility']:.2f}, "
                f"comparison={confidence_calc['factors']['comparison_depth']:.2f})",
                task_id=task_id
            )
            
            return {
                "success": True,
                "task_id": task_id,
                "output": parsed_output,
                "summary": parsed_output.get("summary", ""),
                "facts": parsed_output.get("facts", []),  # V5
                "key_findings": parsed_output.get("key_findings", []),
                "comparison_table": parsed_output.get("comparison_table", {}),  # V5
                "competitors_identified": parsed_output.get("competitors_identified", {}),
                "key_insight": parsed_output.get("key_insight", ""),  # V5
                "strategic_implication": parsed_output.get("strategic_implication", ""),
                "biggest_risk": parsed_output.get("biggest_risk", ""),  # V5
                "final_verdict": parsed_output.get("final_verdict", {}),  # V5
                "data_points": parsed_output.get("data_points", []),
                "sources": sources,
                "confidence": parsed_output.get("confidence", 0.55),
                "confidence_breakdown": parsed_output.get("confidence_breakdown", {}),  # V5
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
        max_results: int = 5,
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
            max_results=max_results,
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
        """Prepare context from search results (COST OPTIMIZED)."""
        results = search_results.get("results", [])
        
        context_parts = []
        # COST OPTIMIZATION: Limit to top 4 results (was 6)
        for i, result in enumerate(results[:4], 1):
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
            
            # COST OPTIMIZATION: Reduce content length (400 → 300, 1000 → 500)
            if use_summarization:
                content = str(content)[:300]  # Reduced from 400
            else:
                content = str(content)[:500]  # Reduced from 1000
            
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
    
    def _self_check_output(self, output: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """V12: Enhanced self-check using MASTER GREYBOX rules."""
        issues = []
        task_lower = task_description.lower()
        
        # Check 1: Real competitors (NOT placeholders or NGOs)
        competitors = output.get("competitors_identified", {})
        if isinstance(competitors, dict):
            all_comps = competitors.get("direct", []) + competitors.get("indirect", [])
            
            # Check for placeholders
            blocked_terms = ["platform a", "platform b", "company x", "company y", 
                           "competitor 1", "competitor 2", "solution a", "solution b"]
            for comp in all_comps:
                if any(blocked in comp.lower() for blocked in blocked_terms):
                    issues.append(f"placeholder_competitor: '{comp}' is not a real company name")
            
            # Check for NGOs/non-profits (common error)
            ngo_indicators = ["foundation", "initiative", "program", "ngo", "non-profit", 
                             "organization", "association", "institute"]
            for comp in all_comps:
                if any(indicator in comp.lower() for indicator in ngo_indicators):
                    issues.append(f"ngo_as_competitor: '{comp}' appears to be an NGO, not a competitor")
            
            # Minimum competitor count
            if len(all_comps) < 2:
                issues.append("insufficient_competitors: Need at least 2 real competitors")
        else:
            issues.append("missing_competitors: competitors_identified must be a dict")
        
        # Check 2: Anti-generic key_insight
        key_insight = str(output.get("key_insight", ""))
        if not key_insight or len(key_insight) < 20:
            issues.append("missing_key_insight: Must be at least 20 characters")
        else:
            # Check against BANNED_GENERIC_PHRASES
            for banned in BANNED_GENERIC_PHRASES:
                if banned in key_insight.lower():
                    issues.append(
                        f"generic_key_insight: Contains banned phrase '{banned}'. "
                        f"MASTER GREYBOX requires sharp, non-obvious insights."
                    )
                    break
            
            # Check for SO WHAT character
            action_words = ["must", "should", "indicates", "suggests", "reveals", "means", "requires"]
            if not any(word in key_insight.lower() for word in action_words):
                issues.append("weak_key_insight: Missing SO WHAT implication - needs action/conclusion")
        
        # Check 3: Actionable strategic_implication
        strategic_impl = str(output.get("strategic_implication", ""))
        if not strategic_impl or len(strategic_impl) < 15:
            issues.append("missing_strategic_implication: Must provide clear action")
        else:
            action_verbs = ["focus", "avoid", "prioritize", "build", "target", "invest", 
                          "delay", "pivot", "pursue", "abandon"]
            if not any(verb in strategic_impl.lower() for verb in action_verbs):
                issues.append("weak_strategic_implication: Must contain clear action verb")
        
        # Check 4: Biggest risk specified
        biggest_risk = str(output.get("biggest_risk", ""))
        if not biggest_risk or len(biggest_risk) < 15:
            issues.append("missing_biggest_risk: Must identify single critical failure point")
        
        # Check 5: MANDATORY comparison structure
        # UNIFIED: Check both comparison_table and comparison
        comparison = output.get("comparison_table") or output.get("comparison") or {}
        # FIX: Ensure comparison is a dict
        if isinstance(comparison, list):
            comparison = {"rows": comparison} if comparison else {}
        elif not isinstance(comparison, dict):
            comparison = {}
        
        if not comparison or not isinstance(comparison, dict):
            issues.append("missing_comparison_table: MANDATORY per MASTER GREYBOX - even for single entity")
        else:
            rows = comparison.get("rows", [])
            if not isinstance(rows, list):
                rows = []
            if len(rows) < 3:
                issues.append("insufficient_comparison: Need at least 3 comparison dimensions")
            
            # Check for explicit winners
            winners_count = sum(1 for row in rows if isinstance(row, dict) and row.get("winner"))
            if len(rows) > 0 and winners_count < len(rows) * 0.5:
                issues.append("missing_winners: Must declare explicit winner for each dimension")
            
            # Check for generic attributes
            generic_attrs = ["general", "overall", "other", "miscellaneous"]
            for row in rows:
                if isinstance(row, dict) and row.get("attribute", "").lower() in generic_attrs:
                    issues.append(f"generic_attribute: '{row.get('attribute')}' too vague - be specific")
        
        # Check 6: Data grounding (no hallucinated numbers)
        data_points = output.get("data_points", [])
        summary = str(output.get("summary", ""))
        key_findings = output.get("key_findings", [])
        
        # Look for suspicious exact percentages or numbers in text without sources
        suspicious_patterns = [r'\d+\.\d+%', r'\$\d+\.\d+[MB]', r'\d+,\d+,\d+']
        all_text = summary + " ".join(key_findings) + " ".join(data_points)
        
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, all_text)
            if matches:
                # Check if these numbers are from data_points (sourced)
                # If not, likely hallucinated
                sourced = any("No reliable data" not in dp for dp in data_points)
                if not sourced and len(matches) > 2:
                    issues.append("potential_hallucination: Specific numbers without 'No reliable data' disclaimer")
        
        # Check 7: Final verdict (if final task)
        is_final = any(kw in task_lower for kw in ["recommend", "verdict", "final", "decision", "strategic"])
        if is_final:
            final_verdict = output.get("final_verdict", {})
            # FIX: Ensure final_verdict is a dict
            if isinstance(final_verdict, list):
                final_verdict = final_verdict[0] if final_verdict else {}
            elif not isinstance(final_verdict, dict):
                final_verdict = {}
            
            if not final_verdict:
                issues.append("missing_final_verdict: Final task MUST include verdict")
            else:
                verdict = final_verdict.get("verdict", "").upper()
                if verdict not in ["YES", "NO", "CONDITIONAL"]:
                    issues.append("invalid_verdict: Must be YES, NO, or CONDITIONAL")
                
                strong_args = final_verdict.get("strong_arguments", [])
                if len(strong_args) < 2:
                    issues.append("insufficient_arguments: Need 2-3 strong arguments for verdict")
                
                if verdict == "CONDITIONAL" and not final_verdict.get("conditions_for_success"):
                    issues.append("missing_conditions: CONDITIONAL verdict requires conditions_for_success")
        
        return {
            "passes": len(issues) == 0,
            "issues": issues,
        }
    
    def _auto_fix_output(self, output: Dict[str, Any], issues: List[str], known_competitors: List[str]) -> Dict[str, Any]:
        """V11: Auto-fix simple issues to reduce retries."""
        fixed = output.copy()
        
        # Auto-fix missing competitors using shared memory
        if "missing_competitors" in issues or "insufficient_competitors" in issues:
            if known_competitors:
                existing = fixed.get("competitors_identified", {})
                if not isinstance(existing, dict):
                    existing = {"direct": [], "indirect": []}
                existing["direct"] = list(set(existing.get("direct", []) + known_competitors[:3]))
                fixed["competitors_identified"] = existing
        
        # Auto-fix missing biggest_risk with placeholder
        if "missing_biggest_risk" in issues:
            # Generate a generic but useful risk
            fixed["biggest_risk"] = "Market adoption uncertainty - users may not switch from existing solutions"
        
        return fixed
    
    def _ensure_required_fields(self, output: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """Ensure all required fields exist with sensible defaults (V6 schema).
        V6 FIX: Strict structure enforcement.
        """
        # V6 REQUIRED FIELDS with defaults
        required_fields = {
            "summary": "",
            "facts": [],
            "key_findings": [],  # Backward compatibility
            "comparison_table": {"rows": []},
            "key_insight": "",
            "strategic_implication": "",
            "biggest_risk": "",
            "competitors_identified": {"direct": [], "indirect": []},
            "final_verdict": {
                "verdict": "",
                "arguments_for": [],
                "arguments_against": [],
                "conditions_for_success": []
            },
            "confidence": 0.55,
            "confidence_breakdown": {
                "comparison_present": False,
                "winners_present": False,
                "insight_quality": "medium",
                "decision_clarity": "medium"
            },
            "data_points": [],
            "limitations": ["Data based on available search results"],
        }
        
        for field, default in required_fields.items():
            if field not in output or output[field] is None:
                output[field] = default
        
        # V6: Populate facts from key_findings if empty
        if not output.get("facts") and output.get("key_findings"):
            output["facts"] = output["key_findings"][:5]
        
        # V6: Ensure comparison_table has proper structure
        ct = output.get("comparison_table", {})
        if not isinstance(ct, dict):
            output["comparison_table"] = {"rows": []}
        elif "rows" not in ct:
            output["comparison_table"]["rows"] = []
        
        # V6: Ensure final_verdict has proper structure
        fv = output.get("final_verdict", {})
        if not isinstance(fv, dict):
            output["final_verdict"] = {
                "verdict": "",
                "arguments_for": [],
                "arguments_against": [],
                "conditions_for_success": []
            }
        else:
            # Ensure all sub-fields exist
            if "verdict" not in fv:
                fv["verdict"] = ""
            if "arguments_for" not in fv or not isinstance(fv["arguments_for"], list):
                fv["arguments_for"] = []
            if "arguments_against" not in fv or not isinstance(fv["arguments_against"], list):
                fv["arguments_against"] = []
            if "conditions_for_success" not in fv or not isinstance(fv["conditions_for_success"], list):
                fv["conditions_for_success"] = []
        
        # Ensure competitors_identified is a dict
        if not isinstance(output.get("competitors_identified"), dict):
            comp = output.get("competitors_identified", [])
            if isinstance(comp, list):
                output["competitors_identified"] = {"direct": comp, "indirect": []}
            else:
                output["competitors_identified"] = {"direct": [], "indirect": []}
        
        # V6: Build confidence_breakdown from comparison_table
        ct = output.get("comparison_table") or {}
        rows = ct.get("rows", []) if isinstance(ct, dict) else []
        output["confidence_breakdown"]["comparison_present"] = len(rows) >= 1
        output["confidence_breakdown"]["winners_present"] = any(
            isinstance(r, dict) and r.get("winner") for r in rows
        )
        
        # V6: Determine insight quality
        key_insight = str(output.get("key_insight", ""))
        if len(key_insight) >= 50:
            output["confidence_breakdown"]["insight_quality"] = "high"
        elif len(key_insight) >= 20:
            output["confidence_breakdown"]["insight_quality"] = "medium"
        else:
            output["confidence_breakdown"]["insight_quality"] = "low"
        
        # V6: Determine decision clarity
        verdict = str(output.get("final_verdict", {}).get("verdict", "")).upper()
        if verdict in ["YES", "NO", "CONDITIONAL"]:
            output["confidence_breakdown"]["decision_clarity"] = "high"
        elif verdict:
            output["confidence_breakdown"]["decision_clarity"] = "medium"
        else:
            output["confidence_breakdown"]["decision_clarity"] = "low"
        
        return output
    
    def _calculate_confidence(
        self,
        search_results: List[Dict[str, Any]],
        output: Dict[str, Any],
        quality_check: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate dynamic confidence based on ACTUAL factors (NO HARDCODING).
        Per MASTER GREYBOX PROMPT: confidence based on search quality, data availability,
        source credibility, and comparison depth.
        """
        # Factor 1: Search Quality (0.0-1.0)
        # Based on: number of results, relevance scores, content depth
        num_results = len(search_results)
        if num_results == 0:
            search_quality = 0.0
        elif num_results >= 8:
            search_quality = 0.9
        elif num_results >= 5:
            search_quality = 0.75
        elif num_results >= 3:
            search_quality = 0.6
        else:
            search_quality = 0.4
        
        # Boost if results have high scores
        def get_score(r):
            if hasattr(r, 'score'):
                return r.score or 0.5
            elif isinstance(r, dict):
                return r.get("score", 0.5)
            return 0.5
        avg_score = sum(get_score(r) for r in search_results) / max(num_results, 1)
        search_quality = (search_quality + avg_score) / 2
        
        # Factor 2: Data Availability (0.0-1.0)
        # Based on: how much real data vs "No reliable data available"
        data_points = output.get("data_points", [])
        num_data_points = len(data_points) if isinstance(data_points, list) else 0
        
        # Count how many are "No reliable data available"
        no_data_count = sum(1 for dp in data_points if isinstance(dp, str) and "no reliable data" in dp.lower())
        
        if num_data_points == 0:
            data_availability = 0.5  # Increased from 0.3 - some analysis
        else:
            # More data points = higher confidence
            # FIX: Don't over-penalize honest "no data" entries
            real_data_ratio = (num_data_points - no_data_count) / num_data_points if num_data_points > 0 else 0
            data_availability = min(0.9, 0.5 + (num_data_points * 0.08) * max(0.5, real_data_ratio))
            # Honesty bonus: if they said "no reliable data", don't penalize below 0.6
            if no_data_count > 0:
                data_availability = max(data_availability, 0.6)
        
        # Factor 3: Source Credibility (0.0-1.0)
        # Based on: source domains and diversity
        sources = output.get("sources", [])
        if not sources:
            source_credibility = 0.5  # Increased from 0.3
        else:
            # Check for credible domains
            credible_domains = [
                "techcrunch.com", "crunchbase.com", "bloomberg.com", "wsj.com",
                "forbes.com", "reuters.com", "nytimes.com", "ft.com",
                "company.com", "blog.com"  # Official company sites
            ]
            
            credible_count = sum(
                1 for src in sources 
                if isinstance(src, str) and any(domain in src.lower() for domain in credible_domains)
            )
            
            # Base score on mix of credible sources
            if credible_count >= 3:
                source_credibility = 0.9
            elif credible_count >= 2:
                source_credibility = 0.75
            elif credible_count >= 1:
                source_credibility = 0.65
            else:
                source_credibility = 0.55  # Unverified sources - still decent
        
        # Factor 4: Comparison Depth (0.0-1.0)
        # Based on: comparison_table completeness and explicit winners
        # UNIFIED: Check both comparison_table and comparison
        comparison = output.get("comparison_table") or output.get("comparison") or {}
        if not comparison or not isinstance(comparison, dict):
            comparison_depth = 0.4  # Some analysis still valid
        else:
            rows = comparison.get("rows", [])
            num_rows = len(rows) if isinstance(rows, list) else 0
            
            # Check for explicit winners
            winners_declared = sum(1 for row in rows if isinstance(row, dict) and row.get("winner"))
            
            if num_rows >= 5 and winners_declared >= num_rows * 0.8:
                comparison_depth = 0.9
            elif num_rows >= 3 and winners_declared >= num_rows * 0.6:
                comparison_depth = 0.8
            elif num_rows >= 3:
                comparison_depth = 0.7
            elif num_rows >= 2:
                comparison_depth = 0.6
            else:
                comparison_depth = 0.5
        
        # V5: STRUCTURE-BASED CONFIDENCE CALCULATION
        # confidence = 0
        # if comparison_table exists: +0.25
        # if winners present: +0.25
        # if insight is non-generic: +0.25
        # if verdict structured: +0.25
        
        structure_confidence = 0.0
        
        # +0.25 if comparison_table exists with rows
        if comparison and isinstance(comparison, dict) and len(comparison.get("rows", [])) >= 1:
            structure_confidence += 0.25
        
        # +0.25 if winners present
        if comparison and isinstance(comparison, dict):
            rows = comparison.get("rows", [])
            if any(isinstance(r, dict) and r.get("winner") for r in rows):
                structure_confidence += 0.25
        
        # +0.25 if insight is non-generic (check key_insight length and quality)
        key_insight = str(output.get("key_insight", ""))
        generic_phrases = ["market is growing", "competition is high", "shows promise", "has potential"]
        if len(key_insight) >= 30 and not any(gp in key_insight.lower() for gp in generic_phrases):
            structure_confidence += 0.25
        
        # +0.25 if verdict structured (final_verdict exists)
        final_verdict = output.get("final_verdict", {})
        if isinstance(final_verdict, dict) and final_verdict.get("verdict") in ["YES", "NO", "CONDITIONAL"]:
            structure_confidence += 0.25
        
        # Combine factor-based and structure-based confidence
        factor_confidence = (
            0.30 * search_quality +
            0.20 * data_availability +
            0.25 * source_credibility +
            0.25 * comparison_depth
        )
        
        # Final confidence is weighted average of both approaches
        overall_confidence = (0.5 * factor_confidence + 0.5 * structure_confidence)
        
        # V5: CLAMP to realistic range (0.55 - 0.9)
        overall_confidence = max(0.55, min(0.9, overall_confidence))
        
        # Determine quality levels for V5 breakdown
        insight_quality = "high" if len(key_insight) >= 50 else "medium" if len(key_insight) >= 20 else "low"
        decision_clarity = "high" if final_verdict.get("verdict") else "medium"
        
        return {
            "confidence": round(overall_confidence, 2),
            "factors": {
                "search_quality": round(search_quality, 2),
                "data_availability": round(data_availability, 2),
                "source_credibility": round(source_credibility, 2),
                "comparison_depth": round(comparison_depth, 2)
            },
            "confidence_breakdown": {
                "comparison_present": bool(comparison and comparison.get("rows")),
                "winners_present": bool(comparison and any(isinstance(r, dict) and r.get("winner") for r in comparison.get("rows", []))),
                "insight_quality": insight_quality,
                "decision_clarity": decision_clarity
            }
        }
    
    async def _generate_deep_intelligence_output(
        self,
        task_description: str,
        context_text: str,
        previous_outputs: Dict[str, Any],
        classification: Dict[str, Any],
        task_id: str,
        retry_feedback: str = "",
        is_final_task: bool = False,
        comparison_entities: tuple = None,
        valid_competitors: list = None,
        global_context: dict = None,
    ) -> Dict[str, Any]:
        """Generate output using REAL MULTI-CALL PIPELINE (v15).
        
        V15 Architecture:
        - THINKING tasks (T1-T4): facts, insights, risks only
        - STRUCTURING task (T5/final): comparison table + verdict
        - Entity locking via global_context
        - Insight repetition prevention
        
        Pipeline:
        - Non-final: FACTS → INSIGHT (no table, no verdict)
        - Final: FACTS → TABLE → INSIGHT → VERDICT → MERGE
        """
        
        if global_context is None:
            global_context = {}
        
        # Detect case type for proper comparison structure
        entities = classification.get("entities", [])
        goal = classification.get("goal", "")
        case_type = detect_case_type(goal, entities)
        entities_str = ", ".join(entities) if entities else "the subject"
        domain = classification.get("domain", "general")
        
        # V15: Use locked entities from global_context (or derive)
        entity_a = global_context.get("entity_a")
        entity_b = global_context.get("entity_b")
        
        if comparison_entities:
            entity_a = comparison_entities[0]
            entity_b = comparison_entities[1]
        elif not entity_a or not entity_b:
            entity_a, entity_b, _, valid_competitors = get_comparison_entities(goal)
        
        if not valid_competitors:
            valid_competitors = CATEGORY_COMPETITOR_MAP.get("general", [])
        
        self.log(f"V15: Comparison entities: {entity_a} vs {entity_b}", task_id=task_id)
        
        # V15: Get existing insights to prevent repetition
        existing_insights = global_context.get("insights", [])
        
        # Previous context - extract competitor info
        prev_context = ""
        known_competitors = []
        if previous_outputs:
            relevant = []
            for tid, output in list(previous_outputs.items())[:3]:
                if isinstance(output, dict):
                    summary = output.get("summary", "")
                    competitors = output.get("competitors_identified", {})
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
                prev_context += f"\nKNOWN COMPETITORS: {', '.join(set(known_competitors[:8]))}"
        
        # Retry feedback if this is a retry
        feedback_section = ""
        if retry_feedback:
            feedback_section = f"\n⚠️ FIX THESE: {retry_feedback}\n"
        
        self.log(f"V16: Starting REAL multi-call pipeline with STRICT CONTEXT (is_final={is_final_task})", task_id=task_id)
        
        # ============== V16: BUILD STRICT CONTEXT ==============
        strict_context = self._build_strict_context(
            goal=goal,
            task_description=task_description,
            previous_outputs=previous_outputs,
            category=global_context.get("category", "") if global_context else "",
        )
        
        # ============== STEP 1: FACT EXTRACTION ==============
        facts_prompt = f"""{strict_context}

Extract ONLY verifiable facts from the search data below.

RULES:
- Each fact = 1 short line
- NO reasoning, NO explanation, NO interpretation
- Facts MUST relate to: {goal}
- Include: competitors, features, target users, pricing (if available)
- If unknown → "No reliable data available"
- Use REAL company names only
- DO NOT mention unrelated industries

SEARCH DATA:
{context_text[:2000]}
{prev_context}

Return ONLY valid JSON:
{{"facts": ["fact 1", "fact 2", ...]}}"""

        self.log(f"STEP 1: Extracting facts", task_id=task_id)
        facts_response = await self.llm_service.generate_json(
            prompt=facts_prompt,
            system_prompt=f"You extract facts ONLY about: {goal}. Stay in domain. Return ONLY JSON.",
            temperature=0.1,
            max_tokens=400,
        )
        self.track_llm_usage(facts_response, task_id)
        
        facts_data = facts_response.get("parsed", {})
        if isinstance(facts_data, list):
            facts_data = {"facts": facts_data}
        if not isinstance(facts_data, dict):
            facts_data = {"facts": []}
        
        facts = facts_data.get("facts", [])
        if not isinstance(facts, list):
            facts = []
        
        self.log(f"STEP 1 RESULT: {len(facts)} facts extracted", task_id=task_id)
        
        # ============== V21: STEP 2 - PER-TASK COMPARISON (ALL TASKS) ==============
        # V21 FIX: Comparison is now MANDATORY for ALL tasks, not just final
        comparison_table = {"rows": []}
        competitors_identified = {"direct": valid_competitors[:3], "indirect": []}
        
        # V21: Get task-specific focus and comparison dimensions
        task_focus = get_task_focus(task_id)
        # V21 FIX: Ensure task_focus is a dict
        if not isinstance(task_focus, dict):
            task_focus = {"name": "General Analysis", "focus": "Comprehensive analysis", "question": "What should be understood?", "comparison_dims": ["features", "value", "fit"]}
        task_comparison_dims = task_focus.get("comparison_dims", ["features", "value", "fit"])
        
        # Build comparison prompt (for ALL tasks now)
        comparison_prompt = f"""{strict_context}

{PER_TASK_COMPARISON_PROMPT}

TASK TYPE: {task_focus.get('name', 'Analysis')}
TASK FOCUS: {task_focus.get('focus', 'General analysis')}
KEY QUESTION: {task_focus.get('question', 'What should be analyzed?')}

Create a comparison for the ORIGINAL GOAL above.

MANDATORY ENTITIES:
- Entity A: {entity_a}
- Entity B: {entity_b}

FACTS FROM ANALYSIS:
{json.dumps(facts[:10], indent=1)}

REQUIRED COMPARISON DIMENSIONS FOR THIS TASK:
{json.dumps(task_comparison_dims, indent=1)}

STRICT RULES:
- Include 2-3 comparison dimensions from the list above
- EVERY dimension MUST have explicit winner
- EVERY dimension MUST have "why_it_matters" explanation
- Use EXACTLY these entities: "{entity_a}" and "{entity_b}"
- DO NOT just list features - CONTRAST directly

{feedback_section}

Return ONLY valid JSON:
{{
  "comparison": [
    {{"dimension": "{task_comparison_dims[0] if task_comparison_dims else 'features'}", "entity_a": "Description for {entity_a}", "entity_b": "Description for {entity_b}", "key_difference": "What differs", "why_it_matters": "Why this matters for decision", "winner": "{entity_a} or {entity_b}"}},
    {{"dimension": "{task_comparison_dims[1] if len(task_comparison_dims) > 1 else 'value'}", "entity_a": "...", "entity_b": "...", "key_difference": "...", "why_it_matters": "...", "winner": "..."}}
  ],
  "comparison_table": {{
    "rows": [
      {{"attribute": "{task_comparison_dims[0] if task_comparison_dims else 'features'}", "entity_a": "...", "entity_b": "...", "winner": "...", "explanation": "..."}}
    ],
    "overall_winner": "{entity_a} or {entity_b}",
    "why": "Reason for overall winner"
  }},
  "competitors_identified": {{"direct": {json.dumps(valid_competitors[:3])}, "indirect": []}}
}}

CRITICAL: The "comparison" array is MANDATORY. Each dimension MUST have winner and why_it_matters."""

        self.log(f"STEP 2: Building comparison (task_type: {task_focus.get('name')})", task_id=task_id)
        comparison_response = await self.llm_service.generate_json(
            prompt=comparison_prompt,
            system_prompt=f"You build COMPARATIVE analysis (not descriptions) for: {goal}. Use '{entity_a}' vs '{entity_b}'. EVERY dimension MUST contrast entities with explicit winners. NO neutral statements. Return ONLY JSON.",
            temperature=0.2,
            max_tokens=800,
        )
        self.track_llm_usage(comparison_response, task_id)
        
        comparison_data = comparison_response.get("parsed", {})
        if isinstance(comparison_data, list):
            comparison_data = comparison_data[0] if comparison_data else {}
        if not isinstance(comparison_data, dict):
            comparison_data = {}
        
        # V21 FIX: Ensure extracted values are correct types (LLM might return wrong types)
        comparison_table = comparison_data.get("comparison_table", {"rows": []})
        if not isinstance(comparison_table, dict):
            comparison_table = {"rows": comparison_table if isinstance(comparison_table, list) else []}
        
        comparison_list = comparison_data.get("comparison", [])
        if not isinstance(comparison_list, list):
            comparison_list = [comparison_list] if comparison_list else []
        
        # V21 FALLBACK: If comparison array is empty but comparison_table has rows, convert them
        if not comparison_list and isinstance(comparison_table, dict):
            rows = comparison_table.get("rows", [])
            if rows:
                comparison_list = []
                for row in rows:
                    if isinstance(row, dict):
                        comparison_list.append({
                            "dimension": row.get("attribute", "comparison"),
                            "entity_a": row.get("entity_a", entity_a),
                            "entity_b": row.get("entity_b", entity_b),
                            "key_difference": row.get("explanation", ""),
                            "why_it_matters": row.get("explanation", ""),
                            "winner": row.get("winner", ""),
                        })
                self.log(f"V21 FALLBACK: Converted {len(comparison_list)} rows to comparison list", task_id=task_id)
        
        competitors_identified = comparison_data.get("competitors_identified", {"direct": valid_competitors[:3], "indirect": []})
        if not isinstance(competitors_identified, dict):
            if isinstance(competitors_identified, list):
                competitors_identified = {"direct": competitors_identified, "indirect": []}
            else:
                competitors_identified = {"direct": valid_competitors[:3], "indirect": []}
        
        # V21: Validate per-task comparison
        per_task_comp_validation = validate_per_task_comparison(comparison_data, task_id)
        if not per_task_comp_validation["valid"]:
            self.log(f"V21 PER-TASK COMPARISON: issues={per_task_comp_validation['issues']}", level="warning", task_id=task_id)
        
        # V15: VALIDATE comparison entities (for final task)
        if is_final_task:
            rows = comparison_table.get("rows", []) if isinstance(comparison_table, dict) else []
            is_valid, error_msg = validate_comparison_entities(
                rows,
                (entity_a, entity_b)
            )
            if not is_valid:
                self.log(f"V16 VALIDATION FAILED: {error_msg}", level="warning", task_id=task_id)
        
        rows_count = len(comparison_table.get("rows", [])) if isinstance(comparison_table, dict) else 0
        self.log(f"STEP 2 RESULT: {rows_count} rows, {len(comparison_list)} dims", task_id=task_id)
        
        # ============== V21: STEP 3 - INSIGHT WITH DEPTH STRUCTURE ==============
        insight_context = json.dumps(comparison_list[:5] if comparison_list else facts[:8], indent=1)
        
        # V15: Add existing insights to prevent repetition
        existing_insights_str = ""
        if existing_insights:
            existing_insights_str = f"\n\nDO NOT REPEAT THESE PREVIOUS INSIGHTS:\n- " + "\n- ".join(existing_insights[:3])
        
        # V21: Get task-specific focus and angle
        task_angle = TASK_INSIGHT_ANGLES.get(task_id, "strategic_opportunity")
        
        insight_prompt = f"""{strict_context}

{NON_GENERIC_INSIGHT_PROMPT}

{DEPTH_STRUCTURE_PROMPT}

TASK TYPE: {task_focus.get('name', 'Analysis')}
KEY QUESTION TO ANSWER: {task_focus.get('question', 'What insight emerges?')}
REQUIRED INSIGHT ANGLE: {task_angle}

Generate ONE deep, non-obvious insight about the ORIGINAL GOAL above.

COMPARISON DATA:
{insight_context}
{existing_insights_str}

BANNED GENERIC PHRASES:
- "team formation gap", "collaboration tools focus", "market is growing"
- "competition is high", "has potential", "opportunity exists"
- "users prefer personalization", "apps struggle with data", "this leads to churn"

MANDATORY DEPTH FORMULA:
[Observation] BUT [Root Cause] BECAUSE [Mechanism] -> this results in [Impact] -> competitors fail because [Gap] -> therefore [Opportunity]

DEPTH REQUIREMENTS:
- MUST include IMPACT (quantitative or directional)
- MUST explain WHY COMPETITORS FAILED to solve this
- MUST state STRATEGIC OPPORTUNITY

RULES:
- Insight MUST answer: {task_focus.get('question', 'What insight emerges?')}
- MUST include contradiction (BUT/however/yet)
- MUST include root cause (BECAUSE/since)
- MUST include impact (results in/leads to/causes)
- MUST include opportunity (therefore/opportunity lies in)
- 2-3 sentences with full depth
- DO NOT drift to unrelated industries

{feedback_section}

Return ONLY valid JSON:
{{
  "key_insight": "[Observation] BUT [Root Cause] BECAUSE [Mechanism] -> results in [Impact] -> competitors fail because [Gap] -> therefore [Opportunity]",
  "strategic_implication": "Concrete action recommendation",
  "biggest_risk": "Single most critical failure point"
}}"""

        self.log(f"STEP 3: Generating insight (angle: {task_angle}, focus: {task_focus.get('name')})", task_id=task_id)
        insight_response = await self.llm_service.generate_json(
            prompt=insight_prompt,
            system_prompt=f"You generate DEEP, CONTRADICTION-DRIVEN insights about: {goal}. EVERY insight MUST have: BUT (root cause) + BECAUSE (mechanism) + IMPACT + WHY COMPETITORS FAIL + OPPORTUNITY. NO shallow statements like 'this leads to churn'. Return ONLY JSON.",
            temperature=0.3,
            max_tokens=500,
        )
        self.track_llm_usage(insight_response, task_id)
        
        insight_data = insight_response.get("parsed", {})
        if isinstance(insight_data, list):
            insight_data = insight_data[0] if insight_data else {}
        if not isinstance(insight_data, dict):
            insight_data = {}
        
        key_insight = insight_data.get("key_insight", "")
        strategic_implication = insight_data.get("strategic_implication", "")
        biggest_risk = insight_data.get("biggest_risk", "")
        
        # V20: Validate insight quality with formula checker
        insight_validation = validate_insight_quality(key_insight, task_id)
        if not insight_validation["valid"]:
            self.log(f"V20 INSIGHT VALIDATION: depth={insight_validation['insight_depth']}, issues={insight_validation['issues']}", level="warning", task_id=task_id)
        
        # V21: Validate insight depth ("why it matters")
        depth_validation = validate_insight_depth(key_insight)
        if not depth_validation["valid"]:
            self.log(f"V21 DEPTH VALIDATION: score={depth_validation['depth_score']}, issues={depth_validation['issues']}", level="warning", task_id=task_id)
        
        # V21: Check for repetition with previous insights
        if existing_insights:
            repetition_check = check_insight_repetition(key_insight, existing_insights)
            if repetition_check["is_repeated"]:
                self.log(f"V21 REPETITION DETECTED: similarity={repetition_check['similarity_score']}", level="warning", task_id=task_id)
        
        self.log(f"STEP 3 RESULT: insight_len={len(key_insight)}, depth={depth_validation['depth_score']}", task_id=task_id)
        
        # ============== STEP 4: STRATEGIC DECISION (V14: PREFER YES/NO) ==============
        # V14: Only generate verdict for final task, otherwise skip
        final_verdict = {}
        
        if is_final_task:
            decision_prompt = f"""{strict_context}

Give final verdict for the ORIGINAL GOAL above.

COMPARISON:
{json.dumps(comparison_table, indent=1)}

KEY INSIGHT:
{key_insight}

BIGGEST RISK:
{biggest_risk}

DECISION RULES:
- Verdict MUST be about: {goal}
- PREFER YES or NO when evidence is clear
- Use CONDITIONAL only when truly uncertain
- Be DECISIVE - investors want clear recommendations
- Arguments MUST relate to the original goal

{feedback_section}

Return ONLY valid JSON:
{{
  "final_verdict": {{
    "verdict": "YES",
    "arguments_for": ["Clear differentiator in X", "Weak incumbent in Y"],
    "arguments_against": ["High CAC risk", "Network effects barrier"],
    "conditions_for_success": []
  }}
}}"""

            self.log(f"STEP 4: Making strategic decision (FINAL TASK)", task_id=task_id)
            decision_response = await self.llm_service.generate_json(
                prompt=decision_prompt,
                system_prompt=f"You make investment decisions about: {goal}. Stay in domain. Prefer YES or NO. Return ONLY JSON.",
                temperature=0.2,
                max_tokens=350,
            )
            self.track_llm_usage(decision_response, task_id)
            
            decision_data = decision_response.get("parsed", {})
            if isinstance(decision_data, list):
                decision_data = decision_data[0] if decision_data else {}
            if not isinstance(decision_data, dict):
                decision_data = {}
            
            final_verdict = decision_data.get("final_verdict", {})
            if not isinstance(final_verdict, dict):
                final_verdict = {}
            
            self.log(f"STEP 4 RESULT: verdict={final_verdict.get('verdict', 'MISSING')}", task_id=task_id)
        else:
            self.log(f"STEP 4: SKIPPED (not final task)", task_id=task_id)
        
        # ============== V21: STEP 5 - FINAL MERGE ==============
        # Build summary from facts + insight
        summary_parts = []
        if facts[:3]:
            summary_parts.append(". ".join(str(f) for f in facts[:2]))
        if key_insight:
            summary_parts.append(key_insight[:150])
        summary = " ".join(summary_parts)[:300] if summary_parts else ""
        
        merged_output = {
            "summary": summary,
            "facts": facts[:5],
            "key_findings": facts[:5],  # Backward compatibility
            "key_insight": key_insight,
            "strategic_implication": strategic_implication,
            "biggest_risk": biggest_risk,
            "competitors_identified": competitors_identified,
            "data_points": facts[:3],
            "limitations": ["Analysis based on available search data"],
            "is_final_task": is_final_task,
            # V21: Include task focus metadata
            "task_focus": task_focus.get("name", "Analysis"),
            "task_question": task_focus.get("question", ""),
        }
        
        # V21: Include comparison for ALL tasks (not just final)
        merged_output["comparison"] = comparison_list if comparison_list else []
        merged_output["comparison_table"] = comparison_table
        
        if is_final_task:
            merged_output["final_verdict"] = final_verdict
        else:
            merged_output["final_verdict"] = {}
        
        # ============== V21: COMPREHENSIVE VALIDATION ==============
        validation_errors = []
        
        # V21: Validate comparison exists for ALL tasks (safe check for dict type)
        comp_table_rows = comparison_table.get("rows", []) if isinstance(comparison_table, dict) else []
        if not comparison_list and not comp_table_rows:
            validation_errors.append("Missing comparison (required for ALL tasks)")
        
        if is_final_task:
            ct = merged_output.get("comparison_table", {})
            if isinstance(ct, dict) and not ct.get("rows"):
                validation_errors.append("Missing comparison_table rows")
            elif not isinstance(ct, dict):
                validation_errors.append("comparison_table is not a dict")
            
            fv = merged_output.get("final_verdict", {})
            if isinstance(fv, dict) and not fv.get("verdict"):
                validation_errors.append("Missing final_verdict.verdict")
            elif not isinstance(fv, dict):
                validation_errors.append("final_verdict is not a dict")
            
            # V19: Run comparison intelligence validation
            comp_valid, comp_issues, comp_suggestions = validate_comparison_output(merged_output)
            if not comp_valid:
                validation_errors.extend(comp_issues)
                self.log(f"V19 COMPARISON VALIDATION: {comp_issues} → {comp_suggestions}", level="warning", task_id=task_id)
        
        if not merged_output.get("key_insight"):
            validation_errors.append("Missing key_insight")
        
        if validation_errors:
            self.log(f"V14 VALIDATION ISSUES: {validation_errors}", level="warning", task_id=task_id)
        else:
            self.log(f"STEP 5: Merge complete - all fields present", task_id=task_id)
        
        return {
            "parsed": merged_output,
            "content": json.dumps(merged_output),
        }
    
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
    
    # ============== V17: FINAL SYNTHESIS BLOCK (MANDATORY) ==============
    
    async def synthesize_all_outputs(
        self,
        all_task_outputs: Dict[str, Any],
        goal: str,
        classification: Dict[str, Any],
        global_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        V17 FINAL SYNTHESIS BLOCK - Combines ALL task outputs into ONE unified analysis.
        
        This is called AFTER all tasks complete, BEFORE generating the final table.
        Removes inconsistencies, merges insights, identifies true competitors.
        """
        category = global_context.get("category", "general")
        entity_a = global_context.get("entity_a", "Competitor")
        entity_b = global_context.get("entity_b", "Proposed Startup")
        
        # Collect all facts, insights, risks from task outputs
        all_facts = []
        all_insights = []
        all_risks = []
        all_competitors = set()
        
        for task_id, output in all_task_outputs.items():
            if not isinstance(output, dict):
                continue
            all_facts.extend(output.get("facts", []))
            if output.get("key_insight"):
                all_insights.append(output.get("key_insight"))
            if output.get("biggest_risk"):
                all_risks.append(output.get("biggest_risk"))
            
            competitors = output.get("competitors_identified", {})
            if isinstance(competitors, dict):
                all_competitors.update(competitors.get("direct", []))
                all_competitors.update(competitors.get("indirect", []))
        
        # Build synthesis prompt
        strict_context = self._build_strict_context(
            goal=goal,
            task_description="Final synthesis of all analysis",
            previous_outputs={},
            category=category,
        )
        
        synthesis_prompt = f"""{strict_context}

You are a senior strategy consultant synthesizing ALL analysis into ONE unified output.

TASK OUTPUTS TO SYNTHESIZE:
{json.dumps({k: {"facts": v.get("facts", [])[:3], "insight": v.get("key_insight", "")[:100], "risk": v.get("biggest_risk", "")} for k, v in all_task_outputs.items() if isinstance(v, dict)}, indent=1)}

GOAL: {goal}
ENTITIES: {entity_a} vs {entity_b}
DOMAIN: {category}

YOUR TASK:
1. Remove any inconsistencies or contradictions
2. Remove any entities/facts from unrelated domains
3. Merge insights into ONE strong, non-generic insight
4. Identify the TRUE competitors (real companies only)
5. Produce a clear final decision

BANNED FROM OUTPUT:
- Generic phrases like "market is growing", "has potential"
- Unrelated domains: healthcare, restaurant, real estate, etc.
- Hallucinated or made-up companies
- Contradictory statements

Return ONLY valid JSON:
{{
  "final_insight": "One sharp, non-obvious insight that synthesizes all analysis (2 sentences max)",
  "final_verdict": "YES" | "NO" | "CONDITIONAL",
  "arguments_for": ["Specific strength 1", "Specific strength 2"],
  "arguments_against": ["Specific risk 1", "Specific risk 2"],
  "true_competitors": ["Real company 1", "Real company 2"],
  "synthesized_facts": ["Key fact 1", "Key fact 2", "Key fact 3"],
  "critical_risk": "The single most critical failure point"
}}"""

        self.log("V17: Running FINAL SYNTHESIS BLOCK")
        
        try:
            response = await self.llm_service.generate_json(
                prompt=synthesis_prompt,
                system_prompt=f"You synthesize analysis about: {goal}. Stay in domain: {category}. Be decisive. Return ONLY JSON.",
                temperature=0.3,
                max_tokens=600,
            )
            self.track_llm_usage(response, "synthesis")
            
            synthesis = response.get("parsed", {})
            if isinstance(synthesis, list):
                synthesis = synthesis[0] if synthesis else {}
            if not isinstance(synthesis, dict):
                synthesis = {}
            
            # V17: Check for domain drift in synthesis
            drift_issues = self._check_domain_drift(synthesis, category)
            if drift_issues:
                self.log(f"V17 SYNTHESIS DRIFT: {drift_issues}", level="warning")
            
            self.log(f"V17 SYNTHESIS: verdict={synthesis.get('final_verdict', 'MISSING')}, competitors={synthesis.get('true_competitors', [])}")
            
            return {
                "success": True,
                "synthesis": synthesis,
                "drift_issues": drift_issues,
            }
            
        except Exception as e:
            self.log(f"V17 SYNTHESIS FAILED: {e}", level="error")
            return {
                "success": False,
                "error": str(e),
                "synthesis": {},
            }
    
    async def generate_final_table(
        self,
        synthesis: Dict[str, Any],
        goal: str,
        case_type: str,
        entity_a: str,
        entity_b: str,
        category: str,
    ) -> Dict[str, Any]:
        """
        V17 FINAL TABLE GENERATOR - Creates ONE final evaluation table.
        
        Called AFTER synthesis to produce the definitive comparison table.
        """
        strict_context = self._build_strict_context(
            goal=goal,
            task_description="Generate final comparison table",
            previous_outputs={},
            category=category,
        )
        
        # Determine table structure based on case type
        if case_type == "competitor_comparison":
            table_structure = f"""
TABLE FORMAT (Two-Company Comparison):
| Attribute | {entity_a} | {entity_b} | Winner |"""
        elif case_type == "startup_idea":
            table_structure = f"""
TABLE FORMAT (Startup Evaluation):
| Attribute | {entity_b} (Proposed) | Evaluation | Winner vs Incumbents |"""
        else:
            table_structure = f"""
TABLE FORMAT (Single Entity Analysis):
| Attribute | {entity_a} | Evaluation |"""
        
        table_prompt = f"""{strict_context}

Create ONE final evaluation table based on this synthesis:

SYNTHESIS:
{json.dumps(synthesis, indent=1)}

GOAL: {goal}
CASE TYPE: {case_type}
ENTITIES: {entity_a} vs {entity_b}

{table_structure}

RULES:
- Maximum 5-6 attributes (decision-focused, not exhaustive)
- NO vague attributes like "General", "Overall", "Other"
- Each row MUST have explicit winner or evaluation
- NO repetition of attributes
- Focus on attributes that MATTER for the decision
- Use REAL data from synthesis, NO hallucination

SUGGESTED ATTRIBUTES (pick 5-6 most relevant):
- Target Users, Core Capability, Differentiation
- Pricing Model, Market Position, Technical Depth
- User Experience, Integration Ecosystem, Scalability

Return ONLY valid JSON:
{{
  "table": {{
    "case_type": "{case_type}",
    "entity_a": "{entity_a}",
    "entity_b": "{entity_b}",
    "rows": [
      {{"attribute": "...", "entity_a": "...", "entity_b": "...", "winner": "...", "explanation": "..."}},
      ...
    ]
  }}
}}"""

        self.log("V17: Running FINAL TABLE GENERATOR")
        
        try:
            response = await self.llm_service.generate_json(
                prompt=table_prompt,
                system_prompt=f"You create comparison tables about: {goal}. Use entities '{entity_a}' and '{entity_b}'. Return ONLY JSON.",
                temperature=0.2,
                max_tokens=500,
            )
            self.track_llm_usage(response, "final_table")
            
            table_data = response.get("parsed", {})
            if isinstance(table_data, list):
                table_data = table_data[0] if table_data else {}
            if not isinstance(table_data, dict):
                table_data = {}
            
            final_table = table_data.get("table", {})
            
            # FIX: Ensure final_table is a dict (not a list)
            if isinstance(final_table, list):
                final_table = {"rows": final_table} if final_table else {}
            elif not isinstance(final_table, dict):
                final_table = {}
            
            # Validate table structure
            rows = final_table.get("rows", [])
            if not rows or len(rows) < 3:
                self.log("V17 TABLE: Insufficient rows, adding defaults", level="warning")
            
            # Validate entity consistency
            is_valid, error_msg = validate_comparison_entities(rows, (entity_a, entity_b))
            if not is_valid:
                self.log(f"V17 TABLE VALIDATION: {error_msg}", level="warning")
            
            self.log(f"V17 FINAL TABLE: {len(rows)} rows generated")
            
            return {
                "success": True,
                "table": final_table,
            }
            
        except Exception as e:
            self.log(f"V17 FINAL TABLE FAILED: {e}", level="error")
            return {
                "success": False,
                "error": str(e),
                "table": {"rows": []},
            }
