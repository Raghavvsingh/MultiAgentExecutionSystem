"""
MASTER GREYBOX PROMPTS V6 - Full System Fix: Multi-Call + Intelligence
Based on the MASTER GREYBOX PROMPT V6 specification.
"""

# ============== MASTER GREYBOX SYSTEM PROMPT V6 ==============

MASTER_GREYBOX_SYSTEM_PROMPT = """You are a **principal strategy consultant + AI systems architect**.

Your task is to generate a **decision-grade analysis** using a **multi-call reasoning pipeline** while ensuring **minimal API cost and maximum analytical depth**.

# 🎯 PRIMARY OBJECTIVE

Produce output that is:
✔ Structurally correct
✔ Explicitly comparative (with winners)
✔ Insight-driven (non-obvious)
✔ Decision-ready (clear verdict)
✔ Cost-efficient (minimal tokens, no redundancy)

# 🚨 CORE EXECUTION MODEL (MANDATORY)

You MUST simulate a **multi-call executor pipeline**:
```
FACTS → COMPARISON → INSIGHT → DECISION → MERGE
```

Each stage:
* Uses ONLY previous stage output
* Produces minimal, high-signal data
* Avoids repetition

# 💰 COST OPTIMIZATION RULES (CRITICAL)

* Use **short, dense outputs**
* Avoid repeating the same information
* No long explanations
* No unnecessary context restatement
* Each stage should output **only what is needed for next stage**
* Prefer bullet-style, compressed phrasing
* If data is missing → "No reliable data available" (no elaboration)

# 🧠 STAGE 1: FACT EXTRACTION (STRICT, LOW TOKEN)

Extract ONLY hard facts:
* Competitors (must include dominant players like Slack, LinkedIn, etc.)
* Core features
* Target users
* Missing capabilities

Rules:
* Each fact = 1 short line
* NO reasoning
* NO insights
* NO interpretation

# ⚖️ STAGE 2: STRUCTURED COMPARISON (CRITICAL FIX)

Using ONLY facts:
Create a **comparison_table** with:
* Minimum 3 attributes
* MUST include: Features, Target Users, Core Capability

Rules:
* EVERY row MUST have a **winner**
* Winner MUST be explicit (no ties)
* Explanation = 1 short line
* NO vague phrases
* NO "both are strong"

# 💡 STAGE 3: INSIGHT GENERATION (DEPTH LAYER)

Based ONLY on comparison:
Generate ONE non-obvious insight.

Must:
* Reveal hidden gap / structural weakness / tradeoff
* Explain WHY current solutions fail/succeed
* NOT repeat facts

Bad: "market is growing", "there is opportunity"
Good: "Existing tools optimize collaboration AFTER teams form, but none solve team formation → new layer opportunity"

# 🎯 STAGE 4: STRATEGIC DECISION (FORCED CLARITY)

Based ONLY on comparison + insight:
Return:
* verdict: YES / NO / CONDITIONAL

Must include:
* arguments_for (≥2, short bullets)
* arguments_against (≥2, short bullets)
* conditions_for_success (if CONDITIONAL → measurable)

Rules:
* NO vague language
* NO hedging
* NO "depends"

# 📊 STAGE 5: STRUCTURE-BASED CONFIDENCE

confidence = 0
if comparison_table exists: +0.25
if all rows have winners: +0.25
if insight is non-generic: +0.25
if verdict is clear and structured: +0.25

Clamp: Min 0.55, Max 0.9

# 🔄 STAGE 6: FINAL MERGE (NO REDUNDANCY)

Combine all stages into ONE JSON.
Rules:
* NO repetition across fields
* NO extra explanation
* Only high-signal content

# 📊 OUTPUT FORMAT

## FOR NON-FINAL TASKS (T1-T4):
```json
{
  "summary": "2-3 sharp sentences",
  "facts": ["Fact 1", "Fact 2"],
  "key_findings": ["Finding with specific data"],
  "data_points": ["Specific metric or stat"],
  "key_insight": "Non-obvious insight with WHY + IMPLICATION (use 'because' or 'therefore')",
  "strategic_implication": "1-2 line actionable recommendation",
  "biggest_risk": "Single most critical failure point",
  "competitors_identified": {"direct": ["Real Company 1"], "indirect": ["Real Company 2"]},
  "confidence": 0.X
}
```

## FOR ALL TASKS (V18: FORCED COMPARISON):
Every task MUST include a comparison block:
```json
{
  "comparison": {
    "features": {"Entity A": "...", "Entity B": "..."},
    "pricing": {"Entity A": "...", "Entity B": "..."},
    "target_users": {"Entity A": "...", "Entity B": "..."},
    "winner": "Entity A or Entity B",
    "why": "Clear 1-line reasoning"
  }
}
```

## FOR FINAL TASK ONLY (T5):
```json
{
  "summary": "2-3 sharp sentences (non-generic)",
  
  "facts": [
    "Short fact 1",
    "Short fact 2"
  ],
  
  "comparison_table": {
    "rows": [
      {
        "attribute": "Feature",
        "entity_a": "Slack",
        "entity_b": "Startup",
        "winner": "Slack",
        "explanation": "Slack has real-time chat, startup focuses on matching"
      },
      {
        "attribute": "Team Formation",
        "entity_a": "Slack",
        "entity_b": "Startup",
        "winner": "Startup",
        "explanation": "Slack lacks matching capability"
      }
    ]
  },
  
  "key_insight": "Non-obvious structural insight",
  
  "strategic_implication": "1-2 line actionable recommendation",
  
  "biggest_risk": "Single most critical failure point",
  
  "competitors_identified": {
    "direct": [],
    "indirect": []
  },
  
  "final_verdict": {
    "verdict": "YES | NO | CONDITIONAL",
    "arguments_for": ["Short reason"],
    "arguments_against": ["Short risk"],
    "conditions_for_success": ["Measurable condition"]
  },
  
  "confidence": 0.X,
  
  "confidence_breakdown": {
    "comparison_present": true,
    "winners_present": true,
    "insight_quality": "high | medium | low",
    "decision_clarity": "high | medium | low"
  }
}
```

# ⚠️ NON-NEGOTIABLE RULES (V18 UPGRADED)

* ALL TASKS: MUST include comparison block with features/pricing/target_users/winner
* ALL TASKS: MUST include non-obvious key_insight with WHY + IMPLICATION
* ALL TASKS: Use ONLY domain-correct competitors (fitness goals = fitness apps, NOT Slack)
* ALL TASKS: NO generic statements ("market is growing", "users prefer personalization")
* ALL TASKS: NO hallucinated data - if missing, write "No public data; inferred from competitor behavior: ..."
* ALL TASKS: NO output outside JSON
* ALL TASKS: Use REAL company names (e.g., MyFitnessPal, Fitbit for fitness)
* ALL TASKS: NO placeholders like "Platform A", "Company X", "some apps"
* FINAL TASK: MUST include comparison_table with 3+ rows, ALL with winners
* FINAL TASK: MUST include structured final_verdict (YES/NO/CONDITIONAL)

# 🧠 V18: CRITICAL THINKING REQUIREMENTS

Before finalizing, validate:
1. "Are ALL competitors from the SAME domain as the goal?"
2. "Does my insight explain WHY this matters (cause) and WHAT to do (implication)?"
3. "Would a McKinsey consultant approve this analysis?"
4. "Have I highlighted WEAKNESSES, not just strengths?"

If ANY check fails → FIX before returning.

Think like: A senior strategy consultant challenging assumptions, not validating them.
Be critical. Be specific. No fluff."""


# ============== FINAL VERDICT SYSTEM PROMPT V6 ==============

FINAL_VERDICT_SYSTEM_PROMPT = """Senior investment committee: Produce FINAL DECISION.

# EXECUTION PIPELINE (STRICT)

STAGE 1: Synthesize key facts from all prior analysis (max 5 bullets)
STAGE 2: Build final comparison_table (min 3 rows, ALL rows have explicit winners)
STAGE 3: Generate ONE decisive non-obvious insight
STAGE 4: Produce verdict with structured arguments (≥2 for, ≥2 against)

# REQUIRED JSON OUTPUT

```json
{
  "summary": "2-3 crisp sentences - final synthesis",
  "facts": ["Fact 1", "Fact 2", "Fact 3"],
  "comparison_table": {
    "rows": [
      {"attribute": "Features", "entity_a": "Incumbent", "entity_b": "Startup", "winner": "Incumbent", "explanation": "Short reason"},
      {"attribute": "Target Users", "entity_a": "Incumbent", "entity_b": "Startup", "winner": "Startup", "explanation": "Short reason"},
      {"attribute": "Core Capability", "entity_a": "Incumbent", "entity_b": "Startup", "winner": "Startup", "explanation": "Short reason"}
    ]
  },
  "key_insight": "Max 2 sentences - reveals hidden gap/tradeoff",
  "strategic_implication": "1-2 lines actionable",
  "biggest_risk": "Single critical failure point",
  "competitors_identified": {"direct": [], "indirect": []},
  "final_verdict": {
    "verdict": "YES | NO | CONDITIONAL",
    "arguments_for": ["Short point 1", "Short point 2"],
    "arguments_against": ["Risk 1", "Risk 2"],
    "conditions_for_success": ["Measurable condition"]
  },
  "confidence": 0.X,
  "confidence_breakdown": {
    "comparison_present": true,
    "winners_present": true,
    "insight_quality": "high | medium | low",
    "decision_clarity": "high | medium | low"
  }
}
```

# RULES
- NO vague conclusions
- YES/NO/CONDITIONAL with clear reasons
- ≥2 arguments_for, ≥2 arguments_against
- EVERY comparison row has explicit winner
- Sharp, decisive, executive-ready
- Maximum insight, minimum tokens"""


# ============== PATCH PROMPT V6 (for targeted fixes) ==============

PATCH_SYSTEM_PROMPT = """You are fixing an INCOMPLETE analysis output that failed validation.

# MANDATORY FIELDS (V6 Schema)

If ANY of these are MISSING or EMPTY, you MUST generate them:

1. comparison_table - MUST have ≥3 rows, EVERY row MUST have explicit winner
2. key_insight - MUST be 2 sentences revealing hidden gap/tradeoff (NOT generic)
3. final_verdict - MUST include verdict (YES/NO/CONDITIONAL), ≥2 arguments_for, ≥2 arguments_against
4. biggest_risk - MUST identify single critical failure point
5. strategic_implication - MUST be 1-2 lines actionable recommendation

# PATCH RULES

- Return ONLY the fields that need to be added or fixed
- DO NOT rewrite existing good content
- DO NOT return partial or weak fixes
- DO NOT use generic phrases ("market is growing", "has potential")
- ALL comparison rows MUST have explicit winner (no ties, no "both")

# EXAMPLE PATCH

If missing final_verdict and weak comparison_table:
```json
{
  "comparison_table": {
    "rows": [
      {"attribute": "Features", "entity_a": "Slack", "entity_b": "Startup", "winner": "Slack", "explanation": "Slack has mature chat features"},
      {"attribute": "Team Formation", "entity_a": "Slack", "entity_b": "Startup", "winner": "Startup", "explanation": "Startup focuses on matching"},
      {"attribute": "Target Users", "entity_a": "Slack", "entity_b": "Startup", "winner": "Startup", "explanation": "Startup targets unformed teams"}
    ]
  },
  "final_verdict": {
    "verdict": "CONDITIONAL",
    "arguments_for": ["Addresses gap in team formation", "Low direct competition"],
    "arguments_against": ["Slack could add matching feature", "Network effects hard to build"],
    "conditions_for_success": ["Achieve 10k active teams in 12 months", "Partner with 3 enterprise customers"]
  }
}
```

Return ONLY valid JSON with missing/fixed fields."""


# ============== ANTI-GENERIC VALIDATION PHRASES ==============

BANNED_GENERIC_PHRASES = [
    "market is growing",
    "competition is high",
    "huge opportunity",
    "shows promise",
    "has potential",
    "could work",
    "industry is expanding",
    "competitive landscape",
    "significant growth",
    "strong growth potential",
    "market opportunity",
    "interesting space",
    "worth exploring",
    "promising area",
    "compelling opportunity"
]


# ============== FORCED COMPARISON INTELLIGENCE PROMPT (V19) ==============

COMPARISON_INTELLIGENCE_PROMPT = """
# 🚀 FORCED COMPARATIVE INTELLIGENCE (MANDATORY)

Your task is to produce **deep, decision-grade comparative analysis**, not descriptive summaries.

## 🚨 CRITICAL RULE: "NO COMPARISON = INVALID OUTPUT"

If your output does NOT include **explicit comparison across entities**, it is **automatically invalid**.

## ⚙️ UNIVERSAL COMPARISON FRAMEWORK (MANDATORY)

For ANY domain, you MUST include:

```json
"comparison": {
  "dimension_1": {
    "entity_A": "...",
    "entity_B": "...",
    "insight": "What is the key difference and why it matters"
  },
  "dimension_2": {
    "entity_A": "...",
    "entity_B": "...",
    "insight": "..."
  },
  "dimension_3": {
    "entity_A": "...",
    "entity_B": "...",
    "insight": "..."
  },
  "overall_winner": "...",
  "why": "Clear reasoning explaining superiority"
}
```

## 🔥 WHAT COUNTS AS REAL COMPARISON

### ✅ VALID
* "X is stronger than Y because it does ___ while Y lacks ___"
* "A targets beginners, B targets advanced users → different positioning"
* "C is cheaper but lacks features → tradeoff"

### ❌ INVALID
* Listing features separately
* Describing each entity independently
* Generic statements without contrast

## 🧠 COMPARISON DIMENSION SELECTION (ADAPTIVE)

Choose **3–5 relevant dimensions** based on context:

### If PRODUCT / APP:
* Features, Pricing, Target users, UX / engagement, Differentiation

### If MARKET:
* Growth drivers, Barriers, Competitive intensity, Customer segments

### If STARTUP IDEA:
* Value proposition vs competitors, Execution complexity, Scalability, Risk vs reward

## 🔥 "INSIGHT RULE" (MANDATORY)

Each comparison dimension MUST include:
✔ Difference
✔ Why difference exists
✔ Why it matters

Format: X does ___ while Y does ___ → this matters because ___ → therefore ___

## 🔥 "WINNER RULE"

You MUST declare:
* Winner per dimension (optional but preferred)
* Final overall winner

NO neutral answers allowed unless justified with specific data.

## 🏆 FINAL STANDARD

Your output must feel like:
✔ A consultant comparing real options
✔ A decision memo, not a blog
✔ A clear answer to: "Which is better and why?"

If comparison is weak → REWRITE until strong.
"""


# ============== COMPARISON VALIDATION RULES (V19) ==============

def validate_comparison_output(output: dict) -> tuple:
    """
    Validate that output contains real comparative intelligence.
    Returns (is_valid, issues_list, suggestions_list)
    """
    issues = []
    suggestions = []
    
    # Check for comparison block
    comparison = output.get("comparison") or output.get("comparison_table")
    if not comparison:
        issues.append("missing_comparison_block")
        suggestions.append("Add comparison block with dimensions, entities, and overall_winner")
        return (False, issues, suggestions)
    
    # Check for dimensions (at least 3)
    if isinstance(comparison, dict):
        rows = comparison.get("rows", [])
        dimensions = [k for k in comparison.keys() if k not in ("rows", "overall_winner", "why", "winner")]
        
        if rows:
            # Table format
            if len(rows) < 3:
                issues.append(f"insufficient_comparison_dimensions: {len(rows)} (need 3+)")
                suggestions.append("Add more comparison dimensions (features, pricing, target_users, etc.)")
        elif dimensions:
            # Dimension format
            if len(dimensions) < 3:
                issues.append(f"insufficient_comparison_dimensions: {len(dimensions)} (need 3+)")
                suggestions.append("Add more comparison dimensions")
        else:
            issues.append("empty_comparison_block")
            suggestions.append("Comparison block must have dimensions or rows")
    
    # Check for overall winner
    overall_winner = comparison.get("overall_winner") or comparison.get("winner")
    if not overall_winner:
        issues.append("missing_overall_winner")
        suggestions.append("Declare overall_winner with clear reasoning (why)")
    
    # Check for winner reasoning
    winner_why = comparison.get("why")
    if overall_winner and not winner_why:
        issues.append("missing_winner_reasoning")
        suggestions.append("Add 'why' field explaining winner superiority")
    
    # Check for entity contrast (not just descriptions)
    if isinstance(comparison, dict):
        rows = comparison.get("rows", [])
        for row in rows:
            if isinstance(row, dict):
                entity_a = row.get("entity_a", "")
                entity_b = row.get("entity_b", "")
                if entity_a and entity_b and entity_a == entity_b:
                    issues.append("no_entity_contrast")
                    suggestions.append("Entities must be different for comparison")
                    break
    
    is_valid = len(issues) == 0
    return (is_valid, issues, suggestions)


# ============== V20: NON-GENERIC INSIGHT ENGINE ==============

NON_GENERIC_INSIGHT_PROMPT = """
# 🧠 NON-GENERIC INSIGHT ENGINE (MANDATORY)

## 🚨 CORE RULE: "GENERIC = INVALID"

Reject insights like:
* "market is growing"
* "users prefer personalization"
* "apps struggle with data"

These are **surface-level observations**, not insights.

## 🔥 WHAT A REAL INSIGHT MUST HAVE

### 1. CONTRADICTION / TENSION
What seems true vs what is actually happening

### 2. ROOT CAUSE
Why this situation exists

### 3. IMPLICATION
What decision this leads to

## 🧠 INSIGHT FORMULA (MANDATORY)

[Observed pattern] BUT [contradiction] BECAUSE [root cause] → THEREFORE [strategic implication]

## ✅ EXAMPLES

### ❌ BAD (GENERIC)
"Apps struggle with data integration"

### ✅ GOOD (SHARP)
"Apps collect large volumes of user data BUT fail to improve retention BECAUSE data is not translated into real-time adaptive coaching → THEREFORE competitive advantage lies in decision-layer intelligence, not data collection"

## 🔥 DEPTH ENFORCEMENT

Each insight must answer:
* Why does this happen?
* Why haven't competitors solved it?
* Why does it matter NOW?

## 🔥 UNIQUENESS BY TASK

* T1 → user behavior contradiction
* T2 → competitor weakness gap
* T3 → market dynamic tension
* T4 → risk paradox
* T5 → strategic opportunity

If your insight could be said by "anyone" -> REWRITE until sharp.
"""


# ============== V21: TASK DIFFERENTIATION ENGINE ==============

# Task-specific required focus areas (ANTI-REPETITION)
TASK_FOCUS_MAP = {
    "T1": {
        "name": "User Analysis",
        "focus": "Behavior gaps, unmet needs",
        "question": "What do users struggle with that others miss?",
        "comparison_dims": ["user_pain_points", "unmet_needs", "behavior_patterns"],
    },
    "T2": {
        "name": "Competitor Analysis", 
        "focus": "Direct strengths vs weaknesses",
        "question": "Where do competitors win/lose directly?",
        "comparison_dims": ["features", "pricing", "market_position"],
    },
    "T3": {
        "name": "Market Analysis",
        "focus": "Macro forces, trends, demand",
        "question": "What forces shape the market?",
        "comparison_dims": ["growth_drivers", "barriers", "customer_segments"],
    },
    "T4": {
        "name": "Risk Analysis",
        "focus": "Failure modes, tradeoffs",
        "question": "What can go wrong and why?",
        "comparison_dims": ["execution_risk", "market_risk", "competitive_risk"],
    },
    "T5": {
        "name": "Final Synthesis",
        "focus": "Strategic decision",
        "question": "What should be done?",
        "comparison_dims": ["overall_value", "feasibility", "timing"],
    },
}

# V21: Per-task comparison prompt (MANDATORY for ALL tasks)
PER_TASK_COMPARISON_PROMPT = """
# MANDATORY: PER-TASK COMPARISON

EVERY task MUST include a comparison block. Comparison is NOT only for the final output.

## REQUIRED STRUCTURE:

```json
"comparison": [
  {
    "dimension": "relevant dimension for this task",
    "entity_A": "value/description",
    "entity_B": "value/description",
    "key_difference": "what differs and why",
    "why_it_matters": "impact on decision",
    "winner": "entity_A or entity_B"
  }
]
```

## RULES:
- Include 2-3 comparison dimensions relevant to this task type
- EVERY dimension MUST have a declared winner
- MUST explain WHY the difference matters
- NO listing features separately - MUST contrast directly

## INVALID:
- Describing entities independently
- No winner declared
- Missing "why_it_matters"
"""

# V21: "Why It Matters" depth structure
DEPTH_STRUCTURE_PROMPT = """
# MANDATORY: "WHY IT MATTERS" DEPTH

Shallow insights are INVALID. Statements like "this leads to churn" are incomplete.

## REQUIRED DEPTH STRUCTURE:

Observation -> Root Cause -> Impact -> Why Competitors Failed -> Strategic Opportunity

## FORMULA:

[Observation] BUT [Root Cause] BECAUSE [Mechanism] -> this results in [Impact] -> competitors fail because [Gap] -> therefore [Opportunity]

## EXAMPLE:

BAD: "This leads to churn"

GOOD: "Users disengage after initial onboarding BUT competitors fail to adapt plans dynamically BECAUSE their systems rely on static templates -> this results in 40% drop-off after week 2 -> competitors fail because they optimize for acquisition not retention -> therefore opportunity lies in continuous adaptation loops"

## DEPTH VALIDATION:

Each insight MUST answer:
1. What is happening? (Observation)
2. Why does it happen? (Root Cause)
3. What is the impact? (Quantitative or directional)
4. Why haven't competitors solved it?
5. What opportunity does this create?
"""


# V20: Insight formula markers for validation
INSIGHT_FORMULA_MARKERS = {
    "contradiction": ["but", "however", "yet", "despite", "although", "while", "whereas"],
    "root_cause": ["because", "since", "due to", "as a result of", "owing to", "this happens because"],
    "implication": ["therefore", "thus", "hence", "->", "which means", "implication:", "this means", "so"],
}

# V21: Depth markers for "why it matters" validation
DEPTH_MARKERS = {
    "impact": ["results in", "leads to", "causes", "drives", "decreases", "increases", "%", "drop", "growth"],
    "competitor_gap": ["competitors fail", "others miss", "incumbents lack", "existing solutions", "no one addresses"],
    "opportunity": ["opportunity", "chance", "potential", "advantage", "differentiate", "win by"],
}

# V20: Task-specific insight angles (upgraded with focus)
TASK_INSIGHT_ANGLES = {
    "T1": "user_behavior_contradiction",
    "T2": "competitor_weakness_gap",
    "T3": "market_dynamic_tension",
    "T4": "risk_paradox",
    "T5": "strategic_opportunity",
}


def validate_insight_quality(insight: str, task_id: str = None) -> dict:
    """
    V20: Validate that insight follows the non-generic formula.
    Returns: {
        "valid": bool,
        "has_contradiction": bool,
        "has_root_cause": bool,
        "has_implication": bool,
        "insight_depth": float (0-1),
        "issues": list,
        "suggestions": list
    }
    """
    if not insight or not isinstance(insight, str):
        return {
            "valid": False,
            "has_contradiction": False,
            "has_root_cause": False,
            "has_implication": False,
            "insight_depth": 0,
            "issues": ["missing_insight"],
            "suggestions": ["Add key_insight with contradiction, root cause, and implication"]
        }
    
    insight_lower = insight.lower()
    issues = []
    suggestions = []
    
    # Check for CONTRADICTION markers
    has_contradiction = any(marker in insight_lower for marker in INSIGHT_FORMULA_MARKERS["contradiction"])
    
    # Check for ROOT CAUSE markers
    has_root_cause = any(marker in insight_lower for marker in INSIGHT_FORMULA_MARKERS["root_cause"])
    
    # Check for IMPLICATION markers
    has_implication = any(marker in insight_lower for marker in INSIGHT_FORMULA_MARKERS["implication"])
    
    # Check for generic phrases
    is_generic = any(phrase in insight_lower for phrase in BANNED_GENERIC_PHRASES)
    
    # Calculate insight depth score
    if has_contradiction and has_root_cause and has_implication:
        insight_depth = 1.0
    elif (has_contradiction and has_root_cause) or (has_root_cause and has_implication):
        insight_depth = 0.7
    elif has_contradiction or has_root_cause or has_implication:
        insight_depth = 0.5
    else:
        insight_depth = 0.3
    
    # Apply generic penalty
    if is_generic:
        insight_depth = min(insight_depth, 0.3)
        issues.append("generic_insight_detected")
        suggestions.append("Rewrite using formula: [Pattern] BUT [Contradiction] BECAUSE [Root Cause] → THEREFORE [Implication]")
    
    # Build issues and suggestions
    if not has_contradiction:
        issues.append("missing_contradiction")
        suggestions.append("Add contradiction: 'X seems true BUT Y is actually happening'")
    
    if not has_root_cause:
        issues.append("missing_root_cause")
        suggestions.append("Add root cause: 'BECAUSE [why this happens]'")
    
    if not has_implication:
        issues.append("missing_implication")
        suggestions.append("Add implication: 'THEREFORE [strategic decision]'")
    
    # Check minimum length (real insights need substance)
    if len(insight) < 80:
        issues.append("insight_too_short")
        suggestions.append("Expand insight with more depth (min 80 chars)")
        insight_depth = min(insight_depth, 0.4)
    
    is_valid = has_contradiction and has_root_cause and has_implication and not is_generic
    
    return {
        "valid": is_valid,
        "has_contradiction": has_contradiction,
        "has_root_cause": has_root_cause,
        "has_implication": has_implication,
        "insight_depth": round(insight_depth, 2),
        "issues": issues,
        "suggestions": suggestions,
    }


def check_insight_repetition(current_insight: str, previous_insights: list) -> dict:
    """
    V20: Check if current insight repeats ideas from previous tasks.
    Returns: {"is_repeated": bool, "similarity_score": float, "repeated_with": str}
    """
    if not current_insight or not previous_insights:
        return {"is_repeated": False, "similarity_score": 0, "repeated_with": None}
    
    current_lower = current_insight.lower()
    current_words = set(current_lower.split())
    
    for prev_insight in previous_insights:
        if not prev_insight:
            continue
        prev_lower = prev_insight.lower()
        prev_words = set(prev_lower.split())
        
        # Calculate word overlap (Jaccard similarity)
        intersection = current_words.intersection(prev_words)
        union = current_words.union(prev_words)
        
        if union:
            similarity = len(intersection) / len(union)
            if similarity > 0.6:  # 60% overlap = likely repeated
                return {
                    "is_repeated": True,
                    "similarity_score": round(similarity, 2),
                    "repeated_with": prev_insight[:100]
                }
    
    return {"is_repeated": False, "similarity_score": 0, "repeated_with": None}


# ============== V21: DEPTH VALIDATION ==============

def validate_insight_depth(insight: str) -> dict:
    """
    V21: Validate that insight has full "why it matters" depth.
    Returns: {
        "valid": bool,
        "has_impact": bool,
        "has_competitor_gap": bool,
        "has_opportunity": bool,
        "depth_score": float (0-1),
        "issues": list,
        "suggestions": list
    }
    """
    if not insight or not isinstance(insight, str):
        return {
            "valid": False,
            "has_impact": False,
            "has_competitor_gap": False,
            "has_opportunity": False,
            "depth_score": 0,
            "issues": ["missing_insight"],
            "suggestions": ["Add insight with full depth structure"]
        }
    
    insight_lower = insight.lower()
    issues = []
    suggestions = []
    
    # Check for IMPACT markers
    has_impact = any(marker in insight_lower for marker in DEPTH_MARKERS["impact"])
    
    # Check for COMPETITOR GAP markers
    has_competitor_gap = any(marker in insight_lower for marker in DEPTH_MARKERS["competitor_gap"])
    
    # Check for OPPORTUNITY markers
    has_opportunity = any(marker in insight_lower for marker in DEPTH_MARKERS["opportunity"])
    
    # Calculate depth score
    depth_components = [has_impact, has_competitor_gap, has_opportunity]
    depth_score = sum(depth_components) / 3
    
    # Bonus for full formula (contradiction + root cause from INSIGHT_FORMULA_MARKERS)
    has_contradiction = any(marker in insight_lower for marker in INSIGHT_FORMULA_MARKERS["contradiction"])
    has_root_cause = any(marker in insight_lower for marker in INSIGHT_FORMULA_MARKERS["root_cause"])
    
    if has_contradiction and has_root_cause:
        depth_score = min(1.0, depth_score + 0.2)
    
    # Build issues and suggestions
    if not has_impact:
        issues.append("missing_impact")
        suggestions.append("Add quantitative or directional impact: 'results in X% decline' or 'drives lower engagement'")
    
    if not has_competitor_gap:
        issues.append("missing_competitor_gap")
        suggestions.append("Explain why competitors failed: 'competitors miss this because...' or 'incumbents lack...'")
    
    if not has_opportunity:
        issues.append("missing_opportunity")
        suggestions.append("State the opportunity: 'therefore opportunity lies in...' or 'advantage comes from...'")
    
    is_valid = depth_score >= 0.6  # Need at least 2 of 3 depth components
    
    return {
        "valid": is_valid,
        "has_impact": has_impact,
        "has_competitor_gap": has_competitor_gap,
        "has_opportunity": has_opportunity,
        "depth_score": round(depth_score, 2),
        "issues": issues,
        "suggestions": suggestions,
    }


def validate_per_task_comparison(output: dict, task_id: str = None) -> dict:
    """
    V21: Validate that EVERY task has a comparison block (not just final).
    Returns: {
        "valid": bool,
        "has_comparison": bool,
        "dimension_count": int,
        "has_winners": bool,
        "has_why_matters": bool,
        "issues": list,
        "suggestions": list
    }
    """
    issues = []
    suggestions = []
    
    # FIX: Ensure output is a dict
    if not isinstance(output, dict):
        if isinstance(output, list):
            output = output[0] if output else {}
        else:
            output = {}
    
    # Check for comparison block
    comparison = output.get("comparison") or output.get("comparison_table")
    
    if not comparison:
        return {
            "valid": False,
            "has_comparison": False,
            "dimension_count": 0,
            "has_winners": False,
            "has_why_matters": False,
            "issues": ["missing_comparison_block"],
            "suggestions": ["Add comparison block with 2-3 dimensions, winners, and why_it_matters"]
        }
    
    # Handle both list and dict formats
    if isinstance(comparison, dict):
        rows = comparison.get("rows", [])
        if not rows:
            # Check for dimension-style format
            dimensions = [k for k in comparison.keys() if k not in ("rows", "overall_winner", "why", "winner")]
            dimension_count = len(dimensions)
        else:
            dimension_count = len(rows)
    elif isinstance(comparison, list):
        rows = comparison
        dimension_count = len(rows)
    else:
        return {
            "valid": False,
            "has_comparison": False,
            "dimension_count": 0,
            "has_winners": False,
            "has_why_matters": False,
            "issues": ["invalid_comparison_format"],
            "suggestions": ["Comparison must be a dict with rows or a list of dimensions"]
        }
    
    # Check dimension count (need 2-3 minimum)
    if dimension_count < 2:
        issues.append(f"insufficient_dimensions: {dimension_count} (need 2+)")
        suggestions.append("Add more comparison dimensions relevant to this task type")
    
    # Check for winners in rows
    has_winners = False
    has_why_matters = False
    
    if isinstance(comparison, dict):
        rows = comparison.get("rows", [])
        if rows:
            winners_count = sum(1 for r in rows if isinstance(r, dict) and r.get("winner"))
            has_winners = winners_count == len(rows) and len(rows) > 0
            
            why_count = sum(1 for r in rows if isinstance(r, dict) and (r.get("why_it_matters") or r.get("explanation")))
            has_why_matters = why_count >= len(rows) * 0.5
        else:
            # Dimension format - check for overall winner
            has_winners = bool(comparison.get("overall_winner") or comparison.get("winner"))
            has_why_matters = bool(comparison.get("why") or comparison.get("why_it_matters"))
    elif isinstance(comparison, list):
        winners_count = sum(1 for r in comparison if isinstance(r, dict) and r.get("winner"))
        has_winners = winners_count == len(comparison) and len(comparison) > 0
        
        why_count = sum(1 for r in comparison if isinstance(r, dict) and (r.get("why_it_matters") or r.get("explanation")))
        has_why_matters = why_count >= len(comparison) * 0.5
    
    if not has_winners:
        issues.append("missing_winners")
        suggestions.append("Every comparison dimension MUST have a declared winner")
    
    if not has_why_matters:
        issues.append("missing_why_it_matters")
        suggestions.append("Add 'why_it_matters' or 'explanation' for each dimension")
    
    is_valid = dimension_count >= 2 and has_winners and has_why_matters
    
    return {
        "valid": is_valid,
        "has_comparison": True,
        "dimension_count": dimension_count,
        "has_winners": has_winners,
        "has_why_matters": has_why_matters,
        "issues": issues,
        "suggestions": suggestions,
    }


def get_task_focus(task_id: str) -> dict:
    """
    V21: Get the required focus area for a task to enforce uniqueness.
    """
    return TASK_FOCUS_MAP.get(task_id, {
        "name": "General Analysis",
        "focus": "Comprehensive analysis",
        "question": "What should be understood?",
        "comparison_dims": ["features", "value", "fit"],
    })


def detect_case_type(goal: str, entities: list) -> str:
    """Detect analysis case type from goal and entities."""
    goal_lower = goal.lower()
    
    # Check for comparison keywords
    comparison_keywords = ["vs", "versus", "compare", "comparison", "or"]
    if any(kw in goal_lower for kw in comparison_keywords) and len(entities) >= 2:
        return "competitor_comparison"
    
    # Check for startup idea keywords
    startup_keywords = ["startup idea", "business idea", "new product", "launch", "build"]
    if any(kw in goal_lower for kw in startup_keywords):
        return "startup_idea"
    
    # Default to single company
    return "single_company"


# ============== COMPARISON TABLE EXAMPLES ==============

COMPARISON_TABLE_EXAMPLES = {
    "startup_idea": {
        "attributes": ["Features", "Target Users", "Differentiation", "Weaknesses", "Opportunity Gap"],
        "entities": ["Existing Solutions", "Proposed Startup"]
    },
    "single_company": {
        "attributes": ["Features", "Pricing", "Target Users", "Strengths", "Weaknesses"],
        "entities": ["Industry Standard", "Company"]
    },
    "competitor_comparison": {
        "attributes": ["Features", "Pricing", "Target Users", "Strengths", "Weaknesses", "Market Position"],
        "entities": ["Company A", "Company B"]
    }
}


# ============== V22: STRATEGIC DIFFERENTIATION PROMPT ==============

STRATEGIC_DIFFERENTIATION_PROMPT = """
# STRATEGIC DIFFERENTIATION ENGINE (MANDATORY FOR FINAL TASK)

Your task is to produce **non-obvious, execution-level differentiation strategies**, not generic ideas.

## CORE RULE: No Obvious Ideas

Statements like "Build community features" or "Add personalization" are:
- Obvious
- Already attempted by competitors
- NOT actionable strategy

## PART 1: "WHY INCUMBENTS FAILED" (MANDATORY)

For ANY recommendation, you MUST first analyze:

```json
"incumbent_failure": {
  "what_they_tried": "specific feature or approach",
  "why_it_failed": "root cause of failure",
  "constraint": "tech / UX / business model / incentives"
}
```

EXAMPLE:
BAD: "Competitors lack community features"
GOOD: "Competitors introduced community features BUT engagement remains low BECAUSE interactions are passive (forums, likes) rather than embedded into core workout loops -> community exists but does not influence behavior"

## PART 2: "REAL GAP IDENTIFICATION"

A real gap is NOT a missing feature. It's:
- Execution gap
- Experience gap
- Behavior gap

```json
"real_gap": {
  "surface_gap": "what appears to be missing",
  "deeper_problem": "the actual behavioral/structural issue",
  "why_unsolved": "constraints preventing solution"
}
```

## PART 3: "HOW YOU WIN" (EXECUTION STRATEGY)

No vague statements. Must be implementable:

```json
"execution_strategy": {
  "core_mechanism": "specific technical/product approach",
  "user_flow": "how users interact with this",
  "differentiation": "why this is different from competitors",
  "why_it_wins": "specific advantage created"
}
```

## PART 4: "COMPETITIVE DEFENSIBILITY"

Each strategy MUST answer:
- Why can't competitors easily copy this?
- What advantage compounds over time?

```json
"defensibility": {
  "barrier": "what makes this hard to replicate",
  "compounding_advantage": "what gets better with scale/time",
  "difficulty_to_copy": "high/medium/low with reason"
}
```

## FINAL OUTPUT STRUCTURE

```json
{
  "key_insight": "contrarian observation",
  "incumbent_failure": {...},
  "real_gap": {...},
  "execution_strategy": {...},
  "defensibility": {...},
  "final_recommendation": "YES / NO / CONDITIONAL"
}
```

If your strategy sounds obvious -> IT IS WRONG -> REWRITE.
"""


def validate_strategic_differentiation(output: dict) -> dict:
    """
    V22: Validate that final output has strategic differentiation depth.
    Returns validation result with issues and suggestions.
    """
    issues = []
    suggestions = []
    score = 0.3  # Base
    
    # Check for incumbent_failure analysis
    incumbent_failure = output.get("incumbent_failure") or output.get("final_verdict", {}).get("incumbent_failure")
    if incumbent_failure and isinstance(incumbent_failure, dict):
        if incumbent_failure.get("what_they_tried") and incumbent_failure.get("why_it_failed"):
            score += 0.2
        else:
            issues.append("incomplete_incumbent_failure")
            suggestions.append("Add what_they_tried and why_it_failed to incumbent_failure")
    else:
        issues.append("missing_incumbent_failure")
        suggestions.append("Add incumbent_failure block explaining why competitors failed")
    
    # Check for real_gap analysis
    real_gap = output.get("real_gap") or output.get("final_verdict", {}).get("real_gap")
    if real_gap and isinstance(real_gap, dict):
        if real_gap.get("deeper_problem") or real_gap.get("why_unsolved"):
            score += 0.15
        else:
            issues.append("shallow_gap_analysis")
            suggestions.append("Identify deeper_problem and why_unsolved in real_gap")
    else:
        # Check key_insight for gap indicators
        key_insight = output.get("key_insight", "").lower()
        if "gap" in key_insight or "miss" in key_insight or "fail" in key_insight:
            score += 0.1
    
    # Check for execution_strategy
    execution_strategy = output.get("execution_strategy") or output.get("strategic_implication")
    if execution_strategy:
        if isinstance(execution_strategy, dict) and execution_strategy.get("core_mechanism"):
            score += 0.2
        elif isinstance(execution_strategy, str) and len(execution_strategy) > 50:
            score += 0.1
        else:
            issues.append("vague_execution_strategy")
            suggestions.append("Add specific core_mechanism and user_flow to execution_strategy")
    else:
        issues.append("missing_execution_strategy")
        suggestions.append("Add execution_strategy with implementable approach")
    
    # Check for defensibility
    defensibility = output.get("defensibility") or output.get("final_verdict", {}).get("defensibility")
    if defensibility and isinstance(defensibility, dict):
        if defensibility.get("barrier") or defensibility.get("compounding_advantage"):
            score += 0.15
    else:
        # Check if key_insight mentions defensibility concepts
        key_insight = output.get("key_insight", "").lower()
        if any(term in key_insight for term in ["barrier", "moat", "defensi", "compound", "network effect"]):
            score += 0.1
    
    # Check for non-obvious indicators
    key_insight = output.get("key_insight", "").lower()
    obvious_phrases = ["build community", "add personalization", "improve ux", "better design", "more features"]
    if any(phrase in key_insight for phrase in obvious_phrases):
        issues.append("obvious_strategy")
        suggestions.append("Strategy is too obvious - explain WHY incumbents failed at this and HOW to do it differently")
        score -= 0.2
    
    score = max(0, min(1, score))
    is_valid = score >= 0.5 and "missing_incumbent_failure" not in issues
    
    return {
        "valid": is_valid,
        "score": round(score, 2),
        "issues": issues,
        "suggestions": suggestions,
    }
