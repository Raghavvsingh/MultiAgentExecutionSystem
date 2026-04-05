"""Planner Agent - High-Density Task DAG Generator (v3 - Industry Grade)."""

import json
from typing import Dict, Any, Optional, List
import logging
import re

from backend.agents.base_agent import BaseAgent

from backend.models.schemas import (
    TaskPlan,
    PlannedTask,
    GoalType,
    AnalysisCaseType,
)

from backend.agents.greybox_prompts import detect_case_type
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ============== V3 HIGH-DENSITY SYSTEM PROMPT ==============
PLANNER_SYSTEM_PROMPT = """You are a STRATEGY CONSULTANT designing execution plans for competitive intelligence.

# CORE PHILOSOPHY
You are NOT a task splitter. You are a STRATEGIC COMPRESSION ENGINE.
- Generate MAXIMUM 5 tasks (can be 3-5, but never more than 5)
- MAXIMIZE depth per task
- Each task must produce DECISION-READY output

# TASK DESIGN RULES

## HIGH-DENSITY TASKS (MANDATORY)
Each task MUST combine multiple dimensions:

❌ BAD (Low Density):
- "Analyze competitors"
- "Analyze pricing"
- "Study the market"

✅ GOOD (High Density):
- "Identify key competitors and compare their features, pricing, and target segments to understand competitive positioning"
- "Analyze market size, growth trends, and demand drivers to assess opportunity attractiveness"
- "Evaluate differentiation, strengths, weaknesses relative to competitors to identify strategic advantage"

## MANDATORY COVERAGE (Compressed into EXACTLY 5 tasks)
Across ALL tasks, MUST cover:
1. Problem/user understanding
2. Competitor identification + comparison
3. Feature + pricing + positioning (COMBINED)
4. Market context (size, trends, dynamics)
5. Risks + opportunities + strategic recommendation

## ANTI-FRAGMENTATION RULE
If two tasks CAN be merged → MUST be merged.

## TASK COUNT CONSTRAINT
- MINIMUM: 3 tasks
- MAXIMUM: 5 tasks
- HARD LIMIT - NO EXCEPTIONS (never exceed 5 tasks)

## DEPENDENCY FLOW
T1: Problem/context understanding
T2-T5: Analysis tasks (competitors, features, market)
Final: Strategic recommendation with clear verdict

## ABSOLUTE RULES
- NO placeholders like "Entity 1", "[Product]"
- Use ACTUAL names from the goal
- Every task must be MULTI-DIMENSIONAL
- NO shallow/vague tasks
- NO redundant tasks

## OUTPUT FORMAT
{
  "classification": {
    "type": "comparison|single_entity|idea_analysis|market_analysis",
    "domain": "...",
    "entities": ["actual names"],
    "focus": "main analysis focus"
  },
  "tasks": [
    {
      "id": "T1",
      "task": "High-density task description covering MULTIPLE dimensions",
      "depends_on": [],
      "reason": "Why this task matters for decision-making"
    }
  ]
}"""


def get_planner_prompt(goal: str, goal_type: str, domain: str, entities: List[str]) -> str:
    """Generate the user prompt for planning."""
    entities_str = ", ".join(entities) if entities else "to be identified"
    
    prompt = f"""Generate a HIGH-DENSITY task DAG for this goal:

GOAL: {goal}
TYPE: {goal_type}
DOMAIN: {domain}
ENTITIES: {entities_str}

## STRICT REQUIREMENTS:
1. Generate 3-5 tasks (HARD LIMIT: MAXIMUM 5 tasks, never exceed this)
2. Each task MUST be multi-dimensional (combine related aspects)
3. NO shallow tasks like "analyze X" without context
4. NO redundant or overlapping tasks
5. Use actual entity names, NOT placeholders

## CONTEXT-SPECIFIC GUIDANCE:
"""
    
    if goal_type == "idea_analysis":
        prompt += """- Focus on: feasibility, competitor landscape, market gaps
- Include: competitor discovery, differentiation assessment
- Final task: Strategic recommendation (GO/NO-GO/CONDITIONAL)
"""
    elif goal_type == "comparison":
        prompt += """- Focus heavily on: DIRECT comparison between entities
- Combine: features + pricing + positioning into fewer tasks
- Minimize generic market tasks
- Final task: Clear winner assessment with trade-offs
"""
    elif goal_type == "single_entity":
        prompt += """- Focus on: deep analysis of the entity
- Include: benchmarking vs key competitors
- Final task: Strategic assessment with recommendations
"""
    else:
        prompt += """- Focus on: comprehensive market understanding
- Include: key players, trends, opportunities
- Final task: Strategic insights and recommendations
"""
    
    prompt += """
## SELF-CHECK BEFORE RESPONDING:
Reject your plan if:
- Task count exceeds 5 ❌
- Task count is less than 3 ❌
- Any task is vague/shallow ❌
- Tasks are repetitive ❌
- Comparison is missing where relevant ❌
- No clear final recommendation task ❌

Generate 3-5 high-density tasks (never exceed 5).

Return ONLY valid JSON."""
    
    return prompt


class PlannerAgent(BaseAgent):
    """Agent for high-density task planning (v3 - Industry Grade)."""
    
    def __init__(self, run_id: str):
        super().__init__(run_id, "planner")
        self.max_retries = 3  # Increased retries for better LLM success rate
        self.min_tasks = 3  # Allow flexibility (3-5 tasks)
        self.max_tasks = 5  # HARD LIMIT: Maximum 5 tasks
        
        # Known established companies for quick entity type detection
        self.known_companies = {
            # Tech giants
            'google', 'amazon', 'apple', 'microsoft', 'meta', 'facebook', 'netflix',
            # Indian companies
            'swiggy', 'zomato', 'flipkart', 'paytm', 'ola', 'uber', 'rapido',
            'byju', 'unacademy', 'phonepe', 'myntra', 'meesho', 'cred', 'razorpay',
            # Global brands
            'spotify', 'airbnb', 'tesla', 'nike', 'mcdonalds', 'starbucks', 'walmart',
            'linkedin', 'twitter', 'instagram', 'whatsapp', 'slack', 'zoom', 'notion',
            # Automotive
            'hyundai', 'toyota', 'ford', 'bmw', 'mercedes', 'volkswagen', 'honda', 'kia',
            'tesla', 'gm', 'general motors', 'nissan', 'mazda', 'audi', 'porsche',
            # Add more as needed
        }
    
    async def _classify_with_llm(self, goal: str) -> Dict[str, Any]:
        """Use LLM to classify intent and detect entity type."""
        classification_prompt = f"""Analyze this query and classify it:

Query: "{goal}"

Return JSON with:
{{
    "goal_type": "idea_analysis" | "comparison" | "single_entity" | "market_analysis",
    "entity_type": "existing_company" | "startup_idea" | "concept" | "market",
    "entities": ["entity1", "entity2"],
    "domain": "automotive" | "fintech" | "foodtech" | "ecommerce" | "saas" | "ai" | "healthtech" | "edtech" | "logistics" | "mobility" | "general",
    "primary_focus": "brief description of what user wants to know",
    "confidence": 0.0-1.0
}}

IMPORTANT - Entity Type Detection Rules:
1. "existing_company": If the entity is a known/established company or business (e.g., Hyundai, Swiggy, Microsoft, Tesla, Airbnb, DoorDash, Stripe, etc.)
   - Companies that are operating and have customers/revenue
   - Well-known brands or established businesses
   - Even if you haven't heard of it, if it sounds like a company name (capitalized, no "idea" context)

2. "startup_idea": ONLY if query explicitly mentions:
   - "startup idea", "business idea", "app idea", "new business"
   - "build a", "create a", "launch a" (describing something new to create)
   - "validate", "feasibility study" (for a proposed concept)

3. "concept": Generic concepts or descriptions without specific company names

4. "market": When asking about an entire market/industry

Examples:
- "Analyze Hyundai" → existing_company (it's a real car manufacturer)
- "Analyze TechCorp" → existing_company (sounds like a company name)  
- "Startup idea: AI fitness coach" → startup_idea (explicitly says "startup idea")
- "Build a food delivery app" → startup_idea (describes creating something new)
- "Analyze the fintech market" → market

Default to "existing_company" for capitalized proper nouns unless clear startup indicators are present."""

        try:
            response = await self.llm_service.generate(
                prompt=classification_prompt,
                system_prompt="You are an intent classifier. Return only valid JSON. Be accurate in distinguishing existing companies from startup ideas.",
                temperature=0.0,
                max_tokens=300,
                json_mode=True,
            )
            
            classification = json.loads(response.get("content", "{}"))
            self.track_llm_usage(response)
            return classification
        except Exception as e:
            self.log(f"LLM classification failed: {e}", level="warning")
            # Don't return empty dict - this causes cascade failures
            # Return None to trigger fallback behavior
            return None
    
    def _detect_entity_type(self, goal: str, entities: List[str]) -> str:
        """
        Detect if entities are existing companies or startup ideas.
        Uses heuristics as fallback when LLM classification is unavailable.
        """
        goal_lower = goal.lower()
        
        # PRIORITY 1: Check for EXPLICIT startup indicators (high confidence)
        startup_patterns = [
            r'\bstartup\s*idea\b', r'\bbusiness\s*idea\b', r'\bapp\s*idea\b',
            r'\bproduct\s*idea\b', r'\bnew\s*(business|product|app|platform)\b',
            r'\bbuild\s+a\b', r'\bcreate\s+a\b', r'\blaunch\s+a\b',
            r'\bproposed\b', r'\bvalidate\b', r'\bfeasibility\b',
            r'\bwant\s+to\s+build\b', r'\bwant\s+to\s+create\b'
        ]
        
        for pattern in startup_patterns:
            if re.search(pattern, goal_lower):
                return "startup_idea"
        
        # PRIORITY 2: Check known companies list (fast path)
        for entity in entities:
            entity_lower = entity.lower()
            for company in self.known_companies:
                if company in entity_lower:
                    return "existing_company"
        
        # PRIORITY 3: Heuristics for company detection
        # Check if entity looks like a company name
        for entity in entities:
            entity_lower = entity.lower()
            
            # Check for company suffixes
            company_indicators = ['ltd', 'inc', 'corp', 'corporation', 'company', 'co.', 'llc', 'limited']
            if any(indicator in entity_lower for indicator in company_indicators):
                return "existing_company"
            
            # If entity is capitalized and not in a "build/create" context, assume it's a company
            # (e.g., "Analyze MyCompany" suggests MyCompany is real)
            if entity[0].isupper() and not any(word in goal_lower for word in ['build', 'create', 'idea', 'new', 'proposed']):
                # Additional check: if the goal starts with analysis verbs, it's likely an existing entity
                analysis_verbs = ['analyze', 'analyse', 'review', 'study', 'evaluate', 'assess', 'research', 'examine']
                if any(goal_lower.startswith(verb) for verb in analysis_verbs):
                    return "existing_company"
        
        # PRIORITY 4: Check for descriptive concepts (suggests startup idea)
        # If entities contain generic descriptions rather than proper nouns
        descriptive_words = ['platform', 'app', 'service', 'solution', 'system', 'tool', 'marketplace']
        for entity in entities:
            entity_lower = entity.lower()
            # If entity has descriptive words AND no capitalized name, it's a concept
            if any(desc in entity_lower for desc in descriptive_words) and not entity[0].isupper():
                return "concept"
        
        # DEFAULT: If user is asking to "analyze X" where X is a proper noun, assume existing company
        # This handles unknown companies that aren't in our list
        if entities and entities[0][0].isupper():
            return "existing_company"
        
        return "concept"
    
    def _detect_goal_type(self, goal: str) -> GoalType:
        """Detect the type of goal from the text."""
        goal_lower = goal.lower().strip()
        
        # Priority-ordered pattern detection
        patterns = [
            # Check idea/startup patterns FIRST
            (GoalType.IDEA_ANALYSIS, [
                r'\bstartup\s*idea\b', r'\bbusiness\s*idea\b', r'\bapp\s*idea\b',
                r'\bproduct\s*idea\b', r'\banalyze\s*(startup\s*)?idea\b',
                r'\bnew\s*(business|product|app|platform|startup)\b',
                r'\bbuild\s+a\b', r'\bcreate\s+a\b', r'\blaunch\s+a\b',
                r'\bidea\s*:', r'\bproposed\b', r'\bvalidate\b'
            ]),
            # Then comparison
            (GoalType.COMPARISON, [
                r'\s+vs\.?\s+', r'\s+versus\s+', r'\bcompare\b',
                r'\bcomparison\b', r'\bcompared\s+to\b'
            ]),
            # Market analysis
            (GoalType.MARKET_ANALYSIS, [
                r'\bmarket\s+analysis\b', r'\bmarket\s+research\b',
                r'\bindustry\s+analysis\b', r'\bmarket\s+size\b'
            ]),
        ]
        
        for goal_type, pattern_list in patterns:
            for pattern in pattern_list:
                if re.search(pattern, goal_lower):
                    return goal_type
        
        return GoalType.SINGLE_ENTITY
    
    async def _extract_classification(self, goal: str, goal_type: GoalType) -> Dict[str, Any]:
        """Extract classification metadata from goal using LLM."""
        goal_lower = goal.lower()
        
        # Try LLM classification first for better accuracy
        llm_classification = await self._classify_with_llm(goal)
        
        # Extract domain with word boundary matching to avoid false positives (e.g., "ai" in "Hyundai")
        domain_keywords = {
            'automotive': ['car', 'vehicle', 'automotive', 'hyundai', 'toyota', 'tesla', 'ford', 'bmw', 'mercedes', 'volkswagen', 'kia'],
            'fitness': ['fitness', 'gym', 'workout', 'exercise'],
            'fintech': ['fintech', 'banking', 'payment', 'finance', 'wallet'],
            'edtech': ['education', 'learning', 'student', 'college', 'course'],
            'ecommerce': ['ecommerce', 'shop', 'retail', 'marketplace', 'shopping'],
            'saas': ['saas', 'software', 'platform', 'tool', 'app'],
            'foodtech': ['food', 'delivery', 'restaurant', 'dining', 'meal', 'swiggy', 'zomato'],
            'healthtech': ['health', 'medical', 'healthcare', 'doctor', 'hospital'],
            'ai': [r'\bai\b', r'\bartificial intelligence\b', r'\bml\b', r'\bmachine learning\b', r'\bllm\b', r'\bopenai\b'],
            'logistics': ['logistics', 'shipping', 'transport', 'courier'],
            'mobility': ['ride', 'cab', 'taxi', 'ola', 'uber', 'lyft'],
        }
        
        domain = 'general'
        for d, keywords in domain_keywords.items():
            for kw in keywords:
                # Use regex for word boundary matching (especially for short words like 'ai', 'ml')
                if kw.startswith(r'\b'):
                    if re.search(kw, goal_lower):
                        domain = d
                        break
                else:
                    # Simple substring match for multi-word keywords and company names
                    if kw in goal_lower:
                        domain = d
                        break
            if domain != 'general':
                break
        
        # Extract entities
        entities = llm_classification.get("entities", []) if llm_classification else []
        
        if not entities:
            # Fallback to pattern matching
            if goal_type == GoalType.COMPARISON:
                for sep in [" vs ", " vs. ", " versus ", " compared to ", " compare "]:
                    if sep in goal_lower:
                        parts = goal.split(sep if sep in goal else sep.strip())
                        if len(parts) >= 2:
                            # Clean up entities
                            entities = [p.strip().strip(":.?!").title() for p in parts[:2]]
                            break
            else:
                # Extract main entity from goal - improved extraction
                # Remove common prefixes
                cleaned_goal = goal
                prefixes = ["analyze", "review", "study", "evaluate", "assess"]
                for prefix in prefixes:
                    if goal_lower.startswith(prefix):
                        cleaned_goal = goal[len(prefix):].strip()
                        break
                
                # Extract entity (up to 4 words)
                words = cleaned_goal.split()
                if len(words) > 0:
                    entity_text = " ".join(words[:min(4, len(words))]).strip(":.?!")
                    entities = [entity_text.title()]
        
        # Detect entity type - PRIORITIZE LLM classification
        entity_type = llm_classification.get("entity_type") if llm_classification else None
        
        # Only use heuristic fallback if LLM didn't provide entity_type or has low confidence
        if not entity_type or (llm_classification and llm_classification.get("confidence", 0) < 0.5):
            entity_type = self._detect_entity_type(goal, entities)
            self.log(f"Using heuristic entity type detection: {entity_type}", level="debug")
        else:
            self.log(f"Using LLM entity type: {entity_type} (confidence: {llm_classification.get('confidence', 0):.2f})", level="debug")
        
        # Override goal_type if LLM has higher confidence
        if llm_classification and llm_classification.get("confidence", 0) > 0.7:
            llm_goal_type = llm_classification.get("goal_type")
            if llm_goal_type:
                try:
                    goal_type = GoalType(llm_goal_type)
                except ValueError:
                    pass  # Keep original goal_type
        
        # Add safety check for empty entities
        if not entities:
            # Use pattern extraction or generic fallback
            self.log("No entities found, using fallback entity extraction", level="warning")
            entities = ["the target"]  # Generic fallback to prevent empty task lists
        
        return {
            "type": goal_type.value,
            "domain": domain,
            "entities": entities,
            "entity_type": entity_type,
            "focus": llm_classification.get("primary_focus", "competitive analysis") if llm_classification else "competitive analysis",
            "llm_confidence": llm_classification.get("confidence", 0) if llm_classification else 0,
        }
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a high-density task plan."""
        goal = context.get("goal", "")
        
        if not goal:
            return {"success": False, "error": "No goal provided"}
        
        self.log(f"Planning for goal: {goal[:80]}...")
        
        # Detect goal type and extract classification (NOW ASYNC)
        goal_type = self._detect_goal_type(goal)
        classification = await self._extract_classification(goal, goal_type)
        
        # Add MASTER GREYBOX case type detection
        case_type = detect_case_type(goal, classification.get("entities", []))
        classification["case_type"] = case_type
        classification["analysis_case_type"] = case_type  # For compatibility
        
        self.log(f"Detected: type={goal_type.value}, entity_type={classification.get('entity_type')}, case_type={case_type}, domain={classification['domain']}")
        self.log(f"Entities: {classification.get('entities', [])}")
        
        # If LLM classification succeeded, log confidence
        if classification.get('llm_confidence', 0) > 0:
            self.log(f"LLM classification confidence: {classification['llm_confidence']:.2f}")
        
        # Try LLM-based planning (PRIMARY METHOD)
        llm_errors = []
        for attempt in range(self.max_retries + 1):
            try:
                self.log(f"LLM planning attempt {attempt + 1}/{self.max_retries + 1}")
                plan = await self._generate_plan_llm(goal, classification)
                
                if plan and self._validate_plan(plan):
                    self.log(f"✅ LLM planning succeeded on attempt {attempt + 1}")
                    return {
                        "success": True,
                        "plan": plan,
                        "goal_type": goal_type.value,
                        "classification": classification,
                        "method": "llm",
                    }
                else:
                    error_msg = f"Plan validation failed on attempt {attempt + 1}"
                    llm_errors.append(error_msg)
                    self.log(error_msg, level="warning")
                    
            except Exception as e:
                error_msg = f"LLM planning error on attempt {attempt + 1}: {e}"
                llm_errors.append(error_msg)
                self.log(error_msg, level="error")
        
        # Fallback to template (BACKUP ONLY - LLM failed after all retries)
        self.log(f"⚠️ All {self.max_retries + 1} LLM attempts failed, using template fallback. Errors: {llm_errors}", level="warning")
        plan = self._generate_template_plan(goal, goal_type, classification)
        
        return {
            "success": True,
            "plan": plan,
            "goal_type": goal_type.value,
            "classification": classification,
            "method": "template",
            "llm_errors": llm_errors,  # Include errors for debugging
        }
    
    async def _generate_plan_llm(self, goal: str, classification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate plan using LLM."""
        prompt = get_planner_prompt(
            goal=goal,
            goal_type=classification["type"],
            domain=classification["domain"],
            entities=classification["entities"],
        )
        
        response = await self.llm_service.generate_json(
            prompt=prompt,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            temperature=0.4,
            max_tokens=1200,  # Increased for 5-7 tasks
        )
        
        self.track_llm_usage(response)
        
        if response.get("parsed"):
            parsed = response["parsed"]
            
            # Extract tasks
            tasks = parsed.get("tasks", [])
            if not tasks and isinstance(parsed, list):
                tasks = parsed
            
            # Merge classification
            llm_classification = parsed.get("classification", {})
            merged_classification = {**classification, **llm_classification}
            
            return {
                "classification": merged_classification,
                "tasks": tasks,
            }
        
        return None
    
    def _validate_plan(self, plan: Dict[str, Any]) -> bool:
        """Validate plan meets high-density requirements."""
        tasks = plan.get("tasks", [])
        
        # Check task count (HARD LIMIT: 3-5 tasks, max 5)
        if len(tasks) < self.min_tasks:
            self.log(f"Too few tasks: {len(tasks)} < {self.min_tasks}", level="warning")
            return False
        
        if len(tasks) > self.max_tasks:
            self.log(f"Too many tasks: {len(tasks)} > {self.max_tasks} - truncating to {self.max_tasks}", level="warning")
            # Truncate to max_tasks instead of failing completely
            plan["tasks"] = tasks[:self.max_tasks]
            tasks = plan["tasks"]
        
        # Check for placeholders
        plan_str = json.dumps(plan).lower()
        placeholders = ["entity 1", "entity 2", "[product]", "[company]", "first entity"]
        for placeholder in placeholders:
            if placeholder in plan_str:
                self.log(f"Plan contains placeholder: {placeholder}", level="warning")
                return False
        
        # Check task quality (relaxed for better LLM acceptance)
        for task in tasks:
            task_text = task.get("task", "").lower()
            
            # Check minimum length (relaxed from 40 to 25 for flexibility)
            if len(task_text) < 25:
                self.log(f"Task too short: {task_text[:50]}", level="warning")
                return False
            
            # Check for vague standalone verbs
            vague_patterns = [
                r'^analyze\s+\w+$',  # Just "analyze X"
                r'^study\s+\w+$',    # Just "study X"
                r'^research\s+\w+$', # Just "research X"
            ]
            for pattern in vague_patterns:
                if re.match(pattern, task_text):
                    self.log(f"Task too vague: {task_text}", level="warning")
                    return False
        
        # Check for valid DAG (no cycles)
        if not self._validate_dag(tasks):
            self.log("Invalid DAG: contains cycles", level="warning")
            return False
        
        self.log(f"LLM plan validated successfully with {len(tasks)} tasks")
        return True
    
    def _validate_dag(self, tasks: List[Dict[str, Any]]) -> bool:
        """Validate that tasks form a valid DAG (no cycles)."""
        task_ids = {t.get("id") for t in tasks}
        
        for task in tasks:
            deps = task.get("depends_on", [])
            for dep in deps:
                if dep not in task_ids:
                    return False
                if dep == task.get("id"):
                    return False
        
        # Simple cycle detection using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)
            
            task = next((t for t in tasks if t.get("id") == task_id), None)
            if task:
                for dep in task.get("depends_on", []):
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            
            rec_stack.remove(task_id)
            return False
        
        for task in tasks:
            task_id = task.get("id")
            if task_id not in visited:
                if has_cycle(task_id):
                    return False  # Cycle found - invalid DAG
        
        return True  # No cycles found
    
    def _generate_template_plan(
        self,
        goal: str,
        goal_type: GoalType,
        classification: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a high-density template plan as fallback."""
        entities = classification.get("entities", [])
        domain = classification.get("domain", "the market")
        
        # Extract entity names or use generic
        entity_name = entities[0] if entities else "the solution"
        
        if goal_type == GoalType.COMPARISON and len(entities) >= 2:
            # Comparison: 5 high-density tasks
            tasks = [
                {
                    "id": "T1",
                    "task": f"Identify the core problem that {entities[0]} and {entities[1]} solve, their target users, and key value propositions",
                    "depends_on": [],
                    "reason": "Establishes context for meaningful comparison"
                },
                {
                    "id": "T2",
                    "task": f"Compare core features, capabilities, and unique differentiators of {entities[0]} vs {entities[1]} including pricing models and target segments",
                    "depends_on": ["T1"],
                    "reason": "Core competitive comparison across multiple dimensions"
                },
                {
                    "id": "T3",
                    "task": f"Analyze market positioning, competitive advantages, and weaknesses of both {entities[0]} and {entities[1]} relative to market needs",
                    "depends_on": ["T2"],
                    "reason": "Strategic positioning assessment"
                },
                {
                    "id": "T4",
                    "task": f"Evaluate market trends, growth dynamics, and external factors affecting both {entities[0]} and {entities[1]}",
                    "depends_on": ["T1"],
                    "reason": "Market context for strategic decision"
                },
                {
                    "id": "T5",
                    "task": f"Provide strategic recommendation on {entities[0]} vs {entities[1]} with clear trade-offs, use cases, and verdict",
                    "depends_on": ["T3", "T4"],
                    "reason": "Actionable decision guidance"
                },
            ]
        elif goal_type == GoalType.IDEA_ANALYSIS:
            # Idea analysis: 5 high-density tasks (combined risks into final recommendation)
            tasks = [
                {
                    "id": "T1",
                    "task": f"Analyze the core problem that {entity_name} addresses, target user segments, and pain points being solved",
                    "depends_on": [],
                    "reason": "Validates problem-solution fit"
                },
                {
                    "id": "T2",
                    "task": f"Identify direct and indirect competitors in {domain}, their features, pricing, and market positioning",
                    "depends_on": ["T1"],
                    "reason": "Competitive landscape understanding"
                },
                {
                    "id": "T3",
                    "task": f"Compare {entity_name}'s proposed features and value proposition against top competitors to identify differentiation and gaps",
                    "depends_on": ["T2"],
                    "reason": "Competitive positioning assessment"
                },
                {
                    "id": "T4",
                    "task": f"Analyze {domain} market size, growth trends, and demand drivers to assess opportunity attractiveness",
                    "depends_on": ["T1"],
                    "reason": "Market opportunity validation"
                },
                {
                    "id": "T5",
                    "task": f"Provide strategic recommendation for {entity_name} with GO/NO-GO/CONDITIONAL verdict, key risks, and success factors",
                    "depends_on": ["T3", "T4"],
                    "reason": "Actionable strategic guidance with risk assessment"
                },
            ]
        else:
            # Single entity analysis - check if it's an existing company or startup
            entity_type = classification.get("entity_type", "concept")
            
            if entity_type == "existing_company":
                # Company analysis: Focus on performance, strategy, competitive position
                tasks = [
                    {
                        "id": "T1",
                        "task": f"Analyze {entity_name}'s business model, revenue streams, key products/services, and target market segments in {domain}",
                        "depends_on": [],
                        "reason": "Establishes company's core business foundation"
                    },
                    {
                        "id": "T2",
                        "task": f"Identify and analyze {entity_name}'s main competitors, their market share, competitive advantages, and strategic positioning in {domain}",
                        "depends_on": ["T1"],
                        "reason": "Competitive landscape and market positioning"
                    },
                    {
                        "id": "T3",
                        "task": f"Evaluate {entity_name}'s financial performance, growth metrics, profitability, and operational efficiency compared to industry benchmarks",
                        "depends_on": ["T1", "T2"],
                        "reason": "Performance assessment and competitive standing"
                    },
                    {
                        "id": "T4",
                        "task": f"Analyze {entity_name}'s strategic initiatives, market opportunities, challenges, and industry trends affecting {domain}",
                        "depends_on": ["T2"],
                        "reason": "Strategic context and future outlook"
                    },
                    {
                        "id": "T5",
                        "task": f"Provide comprehensive assessment of {entity_name}'s strengths, weaknesses, competitive threats, growth potential, and strategic recommendations",
                        "depends_on": ["T3", "T4"],
                        "reason": "Strategic insights and actionable recommendations"
                    },
                ]
            else:
                # Startup/concept analysis: Original approach
                tasks = [
                    {
                        "id": "T1",
                        "task": f"Analyze {entity_name}'s core offering, target market, and value proposition in {domain}",
                        "depends_on": [],
                        "reason": "Establishes analysis foundation"
                    },
                    {
                        "id": "T2",
                        "task": f"Identify key competitors to {entity_name} and compare features, pricing, and market positioning",
                        "depends_on": ["T1"],
                        "reason": "Competitive context"
                    },
                    {
                        "id": "T3",
                        "task": f"Evaluate {entity_name}'s strengths, weaknesses, and competitive advantages relative to alternatives",
                        "depends_on": ["T2"],
                        "reason": "Strategic position assessment"
                    },
                    {
                        "id": "T4",
                        "task": f"Analyze market dynamics, trends, and growth opportunities relevant to {entity_name}",
                        "depends_on": ["T1"],
                        "reason": "Market context and opportunities"
                    },
                    {
                        "id": "T5",
                        "task": f"Provide strategic assessment of {entity_name} with recommendations and key considerations",
                        "depends_on": ["T3", "T4"],
                        "reason": "Actionable insights and recommendations"
                    },
                ]
        
        return {
            "classification": classification,
            "tasks": tasks,
        }

