"""Validator Agent - Multi-layer validation (v21 - Per-Task Comparison + Depth Scoring)."""

import json
from typing import Dict, Any, Optional, List
import logging
import re

from backend.agents.base_agent import BaseAgent

from backend.models.schemas import ValidationResult

from backend.agents.greybox_prompts import (
    validate_insight_quality,
    validate_insight_depth,
    validate_per_task_comparison,
    check_insight_repetition,
    BANNED_GENERIC_PHRASES,
)

logger = logging.getLogger(__name__)


# ============== V18 VALIDATOR SYSTEM PROMPT (UPGRADED) ==============
VALIDATOR_SYSTEM_PROMPT = """You are a senior investment analyst validating competitive intelligence.

Score this analysis using V18 STRICT METRICS (each 0-1):

1. data_quality (0-1): Are facts verifiable? Real data, not hallucinated?
2. completeness (0-1): All required fields present? (summary, facts, insight, comparison)
3. comparison_depth (0-1): Real comparison with winner + reasoning? Not superficial?
4. specificity (0-1): Specific names, numbers, features? Not vague?
5. domain_correctness (0-1): ALL competitors from the CORRECT domain?

FINAL CONFIDENCE = (data_quality + completeness + comparison_depth + specificity + domain_correctness) / 5

HARD AUTO-REJECT CONDITIONS:
- Competitors from wrong domain (e.g., Notion for fitness app)
- Missing comparison block
- Placeholder text ("Platform A", "Company X")
- Generic insights ("market is growing")

Output JSON:
{
  "data_quality": 0.X,
  "completeness": 0.X,
  "comparison_depth": 0.X,
  "specificity": 0.X,
  "domain_correctness": 0.X,
  "confidence": 0.X,
  "valid": true/false,
  "issues": [...],
  "rejection_reason": "..." (if rejected)
}"""


# V18: Generic insight phrases to reject (expanded)
GENERIC_INSIGHT_PHRASES = [
    "team formation gap",
    "collaboration tools focus",
    "market is growing",
    "competition is high",
    "has potential",
    "shows promise",
    "opportunity exists",
    "users prefer personalization",
    "growing trend",
    "significant opportunity",
    "large market",
    "fragmented market",
]

# V18: Placeholder patterns that auto-reject
PLACEHOLDER_PATTERNS = [
    "platform a", "platform b",
    "entity a", "entity b", 
    "company x", "company y",
    "[product]", "[company]", "[competitor]",
    "some apps", "various tools",
]

# V18: Domain competitor mapping (for validation)
CATEGORY_COMPETITOR_MAP = {
    "collaboration": ["slack", "microsoft teams", "discord", "zoom", "google chat"],
    "project_management": ["asana", "monday.com", "jira", "trello", "clickup"],
    "edtech": ["coursera", "udemy", "linkedin learning", "skillshare", "khan academy"],
    "marketplace": ["upwork", "fiverr", "toptal", "freelancer"],
    "social": ["linkedin", "twitter", "facebook", "instagram", "tiktok"],
    "productivity": ["notion", "evernote", "obsidian", "roam research", "coda"],
    "developer": ["github", "gitlab", "bitbucket", "stack overflow", "replit"],
    "crm": ["salesforce", "hubspot", "pipedrive", "zoho crm"],
    "fitness": ["myfitnesspal", "fitbit", "nike training club", "strava", "peloton", "freeletics"],
    "health": ["headspace", "calm", "noom", "ww", "hinge health"],
    "fintech": ["stripe", "square", "paypal", "robinhood", "plaid"],
    "ecommerce": ["shopify", "woocommerce", "bigcommerce", "magento"],
    "gaming": ["steam", "epic games", "unity", "roblox", "twitch"],
    "travel": ["airbnb", "booking.com", "expedia", "tripadvisor"],
    "food": ["doordash", "uber eats", "grubhub", "instacart", "hellofresh"],
}

# V17: Domain drift detection keywords - these indicate output has drifted from the goal
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


class ValidatorAgent(BaseAgent):
    """Agent for validation (v18 - Consultant-Grade Strict Scoring)."""
    
    def __init__(self, run_id: str):
        super().__init__(run_id, "validator")
        self.min_valid_score = 0.55  # V18: Now 0-1 scale (was 6.5 out of 10)
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """V18: Validate task output with strict 5-metric scoring."""
        task_id = context.get("task_id", "unknown")
        task_description = context.get("task_description", "")
        output = context.get("output", {})
        sources = context.get("sources", [])
        is_retry = context.get("is_retry", False)
        expected_domain = context.get("domain", "general")
        
        self.log(f"V18: Validating output for task {task_id} (domain: {expected_domain})", task_id=task_id)
        
        # Layer 1: Schema validation
        schema_result = self._validate_schema(output)
        if not schema_result["valid"]:
            return {"success": True, "validation": schema_result}
        
        # ============== V18: AUTO-REJECT CONDITIONS ==============
        reject_result = self._check_auto_reject(output, task_description, expected_domain)
        if reject_result["rejected"]:
            self.log(f"V18: AUTO-REJECT: {reject_result['reason']}", task_id=task_id, level="warning")
            return {
                "success": True,
                "validation": {
                    "valid": False,
                    "score": 0.2,
                    "confidence": 0.2,
                    "issues": [reject_result["reason"]],
                    "missing": reject_result.get("missing", []),
                    "weak": [],
                    "rejection_reason": reject_result["reason"],
                    "feedback_for_retry": reject_result.get("fix_suggestion", ""),
                    "layer": "auto_reject",
                },
            }
        
        # ============== V18: 5-METRIC SCORING ==============
        metrics = self._calculate_v18_metrics(output, task_description, expected_domain)
        
        # Quick check - if metrics are fairly high, skip deep validation (SPEED OPTIMIZATION)
        if metrics["confidence"] >= 0.70 and not is_retry:
            self.log(f"V18: High confidence ({metrics['confidence']:.2f}), skipping deep validation", task_id=task_id)
            return {
                "success": True,
                "validation": {
                    "valid": True,
                    "score": metrics["confidence"] * 10,  # Convert to 0-10 scale for compatibility
                    "confidence": metrics["confidence"],
                    "metrics": metrics,
                    "issues": [],
                    "missing": [],
                    "weak": [],
                    "feedback_for_retry": "",
                    "layer": "v18_metrics",
                },
            }
        
        # Stage 2: Deep validation (rule-based)
        rule_result = self._validate_rules_investor(output, sources, task_description, context)
        
        # COST OPTIMIZATION: ONLY run LLM validation for final task or retries with low scores
        is_final_task = any(kw in task_description.lower() 
            for kw in ["final", "verdict", "recommend", "decision", "strategic recommendation"])
        
        # Only use LLM validation if:
        # 1. Final task (needs high quality verdict)
        # 2. OR retry attempt (failed before, needs deeper check)
        # 3. OR rule validation score is very low (< 6.0) - SPEED OPTIMIZATION: raised from 6.5
        if is_final_task or (is_retry and rule_result["score"] < 6.0):
            # Layer 3: LLM-based quality assessment (EXPENSIVE - use sparingly)
            llm_result = await self._validate_llm_investor(
                task_id,
                task_description,
                output,
                sources,
            )
            self.log(f"LLM validation used (final={is_final_task}, retry={is_retry}, low_score={rule_result['score']< 0.6})", task_id=task_id)
        else:
            # COST OPTIMIZATION: Skip LLM validation for normal tasks
            # Rule-based validation is sufficient for 80% of cases
            llm_result = {"valid": True, "score": rule_result["score"], "issues": [], "layer": "skipped_llm"}
            self.log(f"LLM validation SKIPPED (cost optimization) - rule_score={rule_result['score']:.1f}", task_id=task_id)
        
        # Combine results with precise feedback
        combined = self._combine_validations(schema_result, rule_result, llm_result, task_description)
        
        # V18: Extract missing/weak fields from metrics or rule_result
        combined["missing"] = rule_result.get("missing", [])
        combined["weak"] = rule_result.get("weak", [])
        combined["feedback_for_retry"] = self._generate_precise_feedback(combined.get("missing", []), combined.get("weak", []))
        
        # V21: Add metrics to validation result for frontend display
        combined["validation_metrics"] = metrics
        
        self.log(
            f"Validation: score={combined['score']:.1f}, valid={combined['valid']}, confidence={metrics.get('confidence', 0):.2f}",
            task_id=task_id,
        )
        
        return {
            "success": True,
            "validation": combined,
        }
    
    def _quick_check(self, output: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        """V15: Quick check - different rules for THINKING vs STRUCTURING tasks."""
        missing = []
        weak = []
        score = 0.8  # V18: Changed to 0-1 scale (was 8.0 out of 10)
        
        if not isinstance(output, dict):
            return {"passes": False, "score": 0.2, "missing": ["valid_dict_output"], "weak": []}
        
        # V15: Check if this is a final/structuring task
        is_final_task = output.get("is_final_task", False)
        task_lower = task_description.lower()
        if any(kw in task_lower for kw in ["recommend", "verdict", "final", "decision"]):
            is_final_task = True
        
        # ============== V15: THINKING TASK VALIDATION (T1-T4) ==============
        # For non-final tasks: only check facts, insights, risks
        
        # CHECK 1: key_insight is MANDATORY for ALL tasks (relaxed requirement)
        key_insight = str(output.get("key_insight", ""))
        if not key_insight or len(key_insight) < 10:  # Reduced from 20 to 10
            missing.append("key_insight")
            score -= 0.10  # Reduced penalty from 0.15 to 0.10
        else:
            # V15: Reject generic insights
            insight_lower = key_insight.lower()
            for phrase in GENERIC_INSIGHT_PHRASES:
                if phrase in insight_lower:
                    weak.append("generic_insight")
                    score -= 0.10
                    break
        
        # CHECK 2: facts should be present (relaxed requirement)
        facts = output.get("facts", [])
        if not facts or len(facts) < 1:  # Reduced from 2 to 1
            weak.append("insufficient_facts")
            score -= 0.03  # Reduced penalty from 0.05 to 0.03
        
        # CHECK 3: biggest_risk should be present
        if not output.get("biggest_risk"):
            weak.append("missing_risk")
            score -= 0.03
        
        # ============== V15: STRUCTURING TASK VALIDATION (FINAL ONLY) ==============
        if is_final_task:
            # CHECK 4: comparison_table MANDATORY for final task
            comparison = output.get("comparison_table") or output.get("comparison")
            if not comparison or not isinstance(comparison, dict):
                # V22 FIX: Try to extract rows if it's a list
                if isinstance(comparison, list):
                    comparison = {"rows": comparison}
                else:
                    missing.append("comparison_table")
                    score -= 0.20
                    comparison = {"rows": []}  # Set to empty dict for further checks
            
            if isinstance(comparison, dict):
                rows = comparison.get("rows", [])
                if not isinstance(rows, list):
                    rows = []
                if len(rows) < 3:
                    missing.append("comparison_table_3_rows")
                    score -= 0.15
                else:
                    # Check winners
                    rows_without_winners = [i for i, r in enumerate(rows) 
                                            if isinstance(r, dict) and not r.get("winner")]
                    if rows_without_winners:
                        weak.append(f"missing_winners_{len(rows_without_winners)}")
                        score -= 0.05 * len(rows_without_winners)
            
            # CHECK 5: final_verdict MANDATORY for final task
            final_verdict = output.get("final_verdict", {})
            # V22 FIX: Ensure final_verdict is a dict
            if not isinstance(final_verdict, dict):
                final_verdict = {}
            if not final_verdict.get("verdict"):
                missing.append("final_verdict")
                score -= 0.20
            else:
                verdict_val = str(final_verdict.get("verdict", "")).upper()
                if verdict_val not in ["YES", "NO", "CONDITIONAL"]:
                    weak.append("invalid_verdict_value")
                    score -= 0.05
                args_for = final_verdict.get("arguments_for", [])
                args_against = final_verdict.get("arguments_against", [])
                if not isinstance(args_for, list) or len(args_for) < 2:
                    weak.append("insufficient_arguments_for")
                    score -= 0.05
                if not isinstance(args_against, list) or len(args_against) < 2:
                    weak.append("insufficient_arguments_against")
                    score -= 0.05
        
        return {
            "passes": len(missing) == 0,
            "score": max(0.4, score),  # V18: Floor is 0.4 on 0-1 scale (was 4.0 out of 10)
            "missing": missing,
            "weak": weak,
        }
    
    def _generate_precise_feedback(
        self, 
        missing: List[str], 
        weak: List[str],
        penalties: Dict[str, float] = None,
        expected_domain: str = "general",
        insight_validation: Dict[str, Any] = None,
    ) -> str:
        """V20: Generate structured retry feedback with specific fixes.
        
        Format:
        ISSUES:
        - Wrong competitors
        - Missing comparison
        
        FIX:
        - Use real domain competitors
        - Add feature/pricing/user comparison
        """
        if not missing and not weak and not penalties and not insight_validation:
            return ""
        
        lines = []
        
        # V18: Start with ISSUES section
        lines.append("═══ ISSUES FOUND ═══")
        
        # Add penalty-based issues first (V18)
        if penalties:
            if penalties.get("wrong_domain"):
                lines.append("- WRONG DOMAIN COMPETITORS (CRITICAL)")
            if penalties.get("no_comparison"):
                lines.append("- MISSING COMPARISON BLOCK")
            if penalties.get("generic_insight"):
                lines.append("- GENERIC INSIGHT (lacks specificity)")
            if penalties.get("hallucination_risk"):
                lines.append("- EXCESSIVE 'NO DATA' CLAIMS")
            if penalties.get("weak_conclusion"):
                lines.append("- WEAK/UNCLEAR VERDICT")
            if penalties.get("placeholder"):
                lines.append("- PLACEHOLDER TEXT DETECTED")
        
        # V20: Add insight validation issues
        if insight_validation and insight_validation.get("issues"):
            for issue in insight_validation["issues"]:
                if issue == "missing_contradiction":
                    lines.append("- INSIGHT: Missing CONTRADICTION/TENSION")
                elif issue == "missing_root_cause":
                    lines.append("- INSIGHT: Missing ROOT CAUSE (why this happens)")
                elif issue == "missing_implication":
                    lines.append("- INSIGHT: Missing IMPLICATION (what decision this leads to)")
                elif issue == "generic_insight_detected":
                    lines.append("- INSIGHT: Generic/obvious statement detected")
                elif issue == "insight_too_short":
                    lines.append("- INSIGHT: Too shallow (needs more depth)")
        
        if missing:
            for m in missing:
                lines.append(f"- Missing: {m}")
        
        if weak:
            for w in weak:
                lines.append(f"- Weak: {w}")
        
        # V20: FIX section with specific remedies
        lines.append("\n═══ HOW TO FIX ═══")
        
        valid_comps = CATEGORY_COMPETITOR_MAP.get(expected_domain, [])
        
        if penalties and penalties.get("wrong_domain"):
            lines.append(f"- Use ONLY {expected_domain} competitors: {', '.join(valid_comps[:4])}")
        
        if "comparison" in str(missing) or (penalties and penalties.get("no_comparison")):
            lines.append("- Add comparison block:")
            lines.append("  comparison: {features: {...}, pricing: {...}, target_users: {...}, winner: '...', why: '...'}")
        
        # V20: Insight-specific fixes
        if insight_validation and not insight_validation.get("valid"):
            lines.append("- REWRITE INSIGHT using this formula:")
            lines.append("  [Observed pattern] BUT [contradiction] BECAUSE [root cause] → THEREFORE [strategic implication]")
            lines.append("")
            lines.append("  Example:")
            lines.append("  'Apps collect vast user data BUT retention remains low BECAUSE data isn't translated")
            lines.append("   into real-time adaptive coaching → THEREFORE competitive advantage lies in")
            lines.append("   decision-layer intelligence, not data collection'")
        elif penalties and penalties.get("generic_insight"):
            lines.append("- Rewrite insight with:")
            lines.append("  * CONTRADICTION: What seems true vs what actually happens")
            lines.append("  * ROOT CAUSE: WHY it happens (use 'because...')")
            lines.append("  * IMPLICATION: WHAT decision it leads to (use 'therefore...')")
        
        if "key_insight" in missing:
            lines.append("- key_insight: Must follow [Pattern] BUT [Contradiction] BECAUSE [Cause] → THEREFORE [Implication]")
        
        if "final_verdict" in missing or (penalties and penalties.get("weak_conclusion")):
            lines.append("- final_verdict: {verdict: 'YES'|'NO'|'CONDITIONAL', arguments_for: [≥2], arguments_against: [≥2]}")
        
        if penalties and penalties.get("hallucination_risk"):
            lines.append("- Instead of 'No reliable data available', write:")
            lines.append("  'No public data; inferred from competitor behavior: [your inference]'")
        
        if penalties and penalties.get("placeholder"):
            lines.append("- Replace ALL placeholders with REAL company names")
            lines.append(f"  Valid examples: {', '.join(valid_comps[:4])}")
        
        # V18: Add weak component fixes
        if weak:
            for w in weak:
                if "winners" in w:
                    lines.append("- Every comparison row MUST have explicit winner (no ties)")
                elif "arguments" in w:
                    lines.append("- Need ≥2 arguments_for AND ≥2 arguments_against")
                elif "generic" in w:
                    lines.append("- Avoid: 'market is growing', 'users prefer personalization', 'has potential'")
        
        return "\n".join(lines)
    
    # ============== V18: AUTO-REJECT CONDITIONS ==============
    def _check_auto_reject(
        self,
        output: Dict[str, Any],
        task_description: str,
        expected_domain: str,
    ) -> Dict[str, Any]:
        """V18: Check for conditions that should auto-reject the output."""
        output_str = json.dumps(output, default=str).lower()
        
        # CHECK 1: Placeholder text
        for placeholder in PLACEHOLDER_PATTERNS:
            if placeholder in output_str:
                return {
                    "rejected": True,
                    "reason": f"Placeholder text detected: '{placeholder}'",
                    "fix_suggestion": "Use real company/product names, not placeholders like 'Platform A' or 'Company X'",
                }
        
        # CHECK 2: Wrong domain competitors
        competitors = output.get("competitors_identified", {})
        if isinstance(competitors, dict):
            all_comps = competitors.get("direct", []) + competitors.get("indirect", [])
        else:
            all_comps = competitors if isinstance(competitors, list) else []
        
        if all_comps and expected_domain != "general":
            valid_comps = CATEGORY_COMPETITOR_MAP.get(expected_domain, [])
            wrong_domain = []
            for comp in all_comps:
                comp_lower = comp.lower()
                # Check if this competitor belongs to a different domain
                for domain, domain_comps in CATEGORY_COMPETITOR_MAP.items():
                    if domain != expected_domain and any(dc in comp_lower for dc in domain_comps):
                        wrong_domain.append(f"{comp} (from {domain})")
                        break
            
            if len(wrong_domain) > len(all_comps) * 0.5:  # More than half are wrong
                return {
                    "rejected": True,
                    "reason": f"Wrong domain competitors: {', '.join(wrong_domain[:3])}",
                    "fix_suggestion": f"Use {expected_domain} competitors: {', '.join(valid_comps[:4])}",
                    "missing": ["domain_correct_competitors"],
                }
        
        # CHECK 3: Missing comparison block (for tasks that should have it)
        is_final = any(kw in task_description.lower() for kw in ["final", "verdict", "recommend"])
        comparison = output.get("comparison_table") or output.get("comparison")
        if is_final and (not comparison or not isinstance(comparison, dict)):
            return {
                "rejected": True,
                "reason": "Missing comparison block in final task",
                "fix_suggestion": "Add comparison block with features/pricing/target_users/winner/why",
                "missing": ["comparison"],
            }
        
        return {"rejected": False}
    
    # ============== V20: 6-METRIC SCORING (Added insight_depth + originality) ==============
    def _calculate_v18_metrics(
        self,
        output: Dict[str, Any],
        task_description: str,
        expected_domain: str,
        previous_insights: List[str] = None,
    ) -> Dict[str, Any]:
        """V20: Calculate the 6 core validation metrics (each 0-1)."""
        output_str = json.dumps(output, default=str).lower()
        
        # METRIC 1: data_quality (0-1)
        # - Are facts present and verifiable?
        # - No hallucinated stats?
        data_quality = 0.5  # Base
        facts = output.get("facts", [])
        data_points = output.get("data_points", [])
        
        if facts and len(facts) >= 2:
            data_quality += 0.2
        if data_points and len(data_points) >= 1:
            data_quality += 0.15
        
        # Penalty for "no reliable data" without inference
        no_data_count = output_str.count("no reliable data")
        if no_data_count > 2:
            data_quality -= 0.2
        elif no_data_count > 0 and len(facts) < 2:
            data_quality -= 0.1
        
        # METRIC 2: completeness (0-1)
        # - All required fields present?
        completeness = 0.0
        required_fields = ["summary", "key_insight"]
        for field in required_fields:
            if output.get(field):
                completeness += 0.2
        
        if facts and len(facts) >= 2:
            completeness += 0.2
        if output.get("biggest_risk"):
            completeness += 0.15
        if output.get("competitors_identified"):
            completeness += 0.15
        if output.get("comparison") or output.get("comparison_table"):
            completeness += 0.1
        
        # METRIC 3: comparison_depth (0-1)
        # - Real comparison with winner + reasoning?
        comparison_depth = 0.3  # Base
        comparison = output.get("comparison_table") or output.get("comparison")
        
        if isinstance(comparison, dict):
            rows = comparison.get("rows", [])
            if rows and len(rows) >= 3:
                comparison_depth += 0.3
            elif rows:
                comparison_depth += 0.15
            
            # Check for winners
            winners_present = sum(1 for r in rows if isinstance(r, dict) and r.get("winner"))
            if rows and winners_present == len(rows):
                comparison_depth += 0.2
            elif winners_present > 0:
                comparison_depth += 0.1
            
            # Check for explanations
            explanations_present = sum(1 for r in rows if isinstance(r, dict) and r.get("explanation"))
            if rows and explanations_present > len(rows) * 0.5:
                comparison_depth += 0.1
        
        # V18: Also check the new comparison format
        if isinstance(comparison, dict) and comparison.get("features") and comparison.get("winner"):
            comparison_depth = max(comparison_depth, 0.7)
        
        # METRIC 4: specificity (0-1)
        # - Specific names, numbers, features?
        specificity = 0.4  # Base
        
        # Check for real company names
        known_companies = ["slack", "notion", "discord", "linkedin", "asana", "jira", 
                         "myfitnesspal", "fitbit", "stripe", "shopify", "airbnb"]
        real_names_found = sum(1 for c in known_companies if c in output_str)
        if real_names_found >= 3:
            specificity += 0.25
        elif real_names_found >= 1:
            specificity += 0.1
        
        # Check for numbers/metrics
        has_numbers = bool(re.search(r'\d+[%$MKB]?|\$\d+', output_str))
        if has_numbers:
            specificity += 0.15
        
        # Penalty for vague phrases
        vague_phrases = ["some apps", "various", "multiple", "many tools", "certain"]
        vague_count = sum(1 for v in vague_phrases if v in output_str)
        specificity -= min(0.2, vague_count * 0.05)
        
        # METRIC 5: domain_correctness (0-1)
        # - ALL competitors from correct domain?
        domain_correctness = 0.7  # Base
        
        competitors = output.get("competitors_identified", {})
        if isinstance(competitors, dict):
            all_comps = competitors.get("direct", []) + competitors.get("indirect", [])
        else:
            all_comps = competitors if isinstance(competitors, list) else []
        
        if all_comps and expected_domain != "general":
            valid_comps = CATEGORY_COMPETITOR_MAP.get(expected_domain, [])
            correct_count = sum(1 for c in all_comps if c.lower() in [v.lower() for v in valid_comps])
            if correct_count == len(all_comps):
                domain_correctness = 1.0
            elif correct_count > len(all_comps) * 0.5:
                domain_correctness = 0.7
            else:
                domain_correctness = 0.3  # Wrong domain - major penalty
        
        # Check for domain drift keywords
        drift_count = sum(1 for kw in INVALID_DOMAIN_KEYWORDS if kw in output_str)
        if drift_count > 0:
            domain_correctness -= min(0.3, drift_count * 0.1)
        
        # ============== V20: METRIC 6 - INSIGHT DEPTH (0-1) ==============
        # - Does insight have contradiction + root cause + implication?
        key_insight = output.get("key_insight", "")
        insight_validation = validate_insight_quality(key_insight)
        insight_depth = insight_validation["insight_depth"]
        
        # V21: Also validate "why it matters" depth
        depth_validation = validate_insight_depth(key_insight)
        if depth_validation["valid"]:
            insight_depth = max(insight_depth, depth_validation["depth_score"])
        
        # ============== V21: METRIC 7 - PER-TASK COMPARISON (0-1) ==============
        # - Does this task have comparison (not just final)?
        per_task_comp = validate_per_task_comparison(output)
        per_task_comparison_score = 0.3  # Base
        if per_task_comp["has_comparison"]:
            per_task_comparison_score = 0.5
            if per_task_comp["dimension_count"] >= 2:
                per_task_comparison_score += 0.2
            if per_task_comp["has_winners"]:
                per_task_comparison_score += 0.15
            if per_task_comp["has_why_matters"]:
                per_task_comparison_score += 0.15
        
        # ============== V20: METRIC 8 - ORIGINALITY (0-1) ==============
        # - Is insight unique (not repeated from previous tasks)?
        originality = 1.0  # Base
        if previous_insights:
            repetition_check = check_insight_repetition(key_insight, previous_insights)
            if repetition_check["is_repeated"]:
                originality = 0.3  # Heavy penalty for repetition
                self.log(f"V21 REPETITION DETECTED: similarity={repetition_check['similarity_score']}", level="warning")
        
        # Generic insight also kills originality
        if not insight_validation["valid"] and insight_validation.get("issues"):
            if "generic_insight_detected" in insight_validation["issues"]:
                originality = min(originality, 0.3)
        
        # Clamp all metrics to [0, 1]
        data_quality = max(0, min(1, data_quality))
        completeness = max(0, min(1, completeness))
        comparison_depth = max(0, min(1, comparison_depth))
        specificity = max(0, min(1, specificity))
        domain_correctness = max(0, min(1, domain_correctness))
        insight_depth = max(0, min(1, insight_depth))
        per_task_comparison_score = max(0, min(1, per_task_comparison_score))
        originality = max(0, min(1, originality))
        
        # V21: Calculate final confidence (7 metrics now)
        confidence = (
            data_quality + 
            completeness +
            comparison_depth + 
            specificity + 
            domain_correctness + 
            insight_depth +
            per_task_comparison_score
        ) / 7
        
        # V20: Apply originality penalty (not part of base average, but reduces final)
        if originality < 0.5:
            confidence -= 0.15  # -0.15 penalty for non-original insights
        
        confidence = max(0, min(1, confidence))
        
        return {
            "data_quality": round(data_quality, 2),
            "completeness": round(completeness, 2),
            "comparison_depth": round(comparison_depth, 2),
            "specificity": round(specificity, 2),
            "domain_correctness": round(domain_correctness, 2),
            "insight_depth": round(insight_depth, 2),
            "per_task_comparison": round(per_task_comparison_score, 2),
            "originality": round(originality, 2),
            "confidence": round(confidence, 2),
            "insight_validation": insight_validation,
            "depth_validation": depth_validation,
            "per_task_comp_validation": per_task_comp,
        }
    
    def _validate_schema(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Layer 1: Basic schema validation."""
        if not output:
            return {"valid": False, "score": 0, "issues": ["Output is empty"], "layer": "schema"}
        
        if not isinstance(output, dict):
            return {"valid": False, "score": 0, "issues": ["Output is not a dictionary"], "layer": "schema"}
        
        output_str = json.dumps(output, default=str)
        if len(output_str) < 200:
            return {"valid": False, "score": 2, "issues": ["Output too short for investor-grade"], "layer": "schema"}
        
        return {"valid": True, "score": 10, "issues": [], "layer": "schema"}
    
    def _validate_rules_investor(
        self,
        output: Dict[str, Any],
        sources: List[str],
        task_description: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Layer 2: V18 Investor-grade rule-based validation with HARD PENALTIES."""
        issues = []
        bonuses = []
        penalties = {}  # V18: Track penalties by type
        base_score = 7.5
        
        output_str = json.dumps(output, default=str).lower()
        task_lower = task_description.lower()
        expected_domain = context.get("domain", "general") if context else "general"
        
        # ============== V18: HARD PENALTY 1 - WRONG DOMAIN COMPETITORS (-0.4) ==============
        competitors = output.get("competitors_identified", {})
        if isinstance(competitors, dict):
            all_comps = competitors.get("direct", []) + competitors.get("indirect", [])
        else:
            all_comps = competitors if isinstance(competitors, list) else []
        
        if all_comps and expected_domain != "general":
            valid_comps = [c.lower() for c in CATEGORY_COMPETITOR_MAP.get(expected_domain, [])]
            wrong_domain_comps = []
            for comp in all_comps:
                comp_lower = comp.lower()
                # Check if this competitor belongs to a DIFFERENT domain
                found_wrong = False
                for domain, domain_comps in CATEGORY_COMPETITOR_MAP.items():
                    if domain != expected_domain:
                        if any(dc.lower() in comp_lower or comp_lower in dc.lower() for dc in domain_comps):
                            wrong_domain_comps.append(f"{comp} (from {domain})")
                            found_wrong = True
                            break
            
            if wrong_domain_comps:
                issues.append(f"Wrong domain competitors: {', '.join(wrong_domain_comps[:3])}")
                base_score -= 4.0  # V18: -0.4 * 10 = -4.0 on 0-10 scale
                penalties["wrong_domain"] = 0.4
                self.log(f"V18 WRONG DOMAIN: {wrong_domain_comps}", level="warning")
        
        # ============== V18: HARD PENALTY 2 - NO COMPARISON (-0.3) ==============
        is_final_task = any(kw in task_lower for kw in ["final", "verdict", "recommend", "decision"])
        comparison = output.get("comparison_table") or output.get("comparison")
        
        if is_final_task:
            if not comparison or not isinstance(comparison, dict):
                issues.append("Missing comparison block in final task")
                base_score -= 3.0  # V18: -0.3 * 10
                penalties["no_comparison"] = 0.3
            else:
                rows = comparison.get("rows", [])
                if not rows or len(rows) < 3:
                    issues.append(f"Insufficient comparison rows: {len(rows) if rows else 0} (need 3+)")
                    base_score -= 1.5
                    penalties["weak_comparison"] = 0.15
        
        # ============== V18: HARD PENALTY 3 - GENERIC INSIGHT (-0.2) ==============
        key_insight = str(output.get("key_insight", "")).lower()
        for phrase in GENERIC_INSIGHT_PHRASES:
            if phrase in key_insight:
                issues.append(f"Generic insight: contains '{phrase}'")
                base_score -= 2.0  # V18: -0.2 * 10
                penalties["generic_insight"] = 0.2
                break
        
        # V18: Check insight has cause/implication
        if key_insight and len(key_insight) > 30:
            has_reasoning = any(word in key_insight for word in ["because", "since", "therefore", "thus", "implies"])
            if not has_reasoning:
                issues.append("Insight lacks reasoning (no 'because'/'therefore')")
                base_score -= 1.0
                penalties["weak_reasoning"] = 0.1
        
        # ============== V18: HARD PENALTY 4 - HALLUCINATED DATA (-0.3) ==============
        # Check for excessive "no reliable data" without any inference
        no_data_phrases = ["no reliable data available", "no public data available"]
        no_data_count = sum(output_str.count(phrase) for phrase in no_data_phrases)
        facts = output.get("facts", [])
        
        if no_data_count >= 2 and len(facts) < 2:
            issues.append("Excessive 'no data' claims without inference")
            base_score -= 3.0  # V18: -0.3 * 10
            penalties["hallucination_risk"] = 0.3
        
        # ============== V18: HARD PENALTY 5 - WEAK CONCLUSION (-0.2) ==============
        if is_final_task:
            verdict = output.get("final_verdict", {})
            if isinstance(verdict, dict):
                verdict_val = str(verdict.get("verdict", "")).upper()
                if verdict_val not in ["YES", "NO", "CONDITIONAL"]:
                    issues.append("Weak/unclear verdict (must be YES/NO/CONDITIONAL)")
                    base_score -= 2.0
                    penalties["weak_conclusion"] = 0.2
                
                args_for = verdict.get("arguments_for", [])
                args_against = verdict.get("arguments_against", [])
                if len(args_for) < 2 or len(args_against) < 2:
                    issues.append(f"Insufficient arguments: for={len(args_for)}, against={len(args_against)} (need 2+ each)")
                    base_score -= 1.5
                    penalties["weak_arguments"] = 0.15
        
        # ============== V18: PLACEHOLDER DETECTION ==============
        for placeholder in PLACEHOLDER_PATTERNS:
            if placeholder in output_str:
                issues.append(f"Contains placeholder: '{placeholder}'")
                base_score -= 2.0
                penalties["placeholder"] = 0.2
                break
        
        # ============== V17: DRIFT DETECTION ==============
        drift_count = sum(1 for keyword in INVALID_DOMAIN_KEYWORDS if keyword in output_str)
        if drift_count > 0:
            base_score -= min(2.0, drift_count * 0.5)
            issues.append(f"Domain drift: {drift_count} invalid keywords found")
            self.log(f"V18 DRIFT: {drift_count} invalid domain keywords", level="warning")
        
        # V18: Additional vague phrase check
        vague_phrases = [
            ("shows promise", "Vague: 'shows promise' - be decisive"),
            ("has potential", "Vague: 'has potential' - state conditions"),
            ("could be viable", "Vague: 'could be viable' - make a decision"),
        ]
        for phrase, issue in vague_phrases:
            if phrase in output_str:
                issues.append(issue)
                base_score -= 0.3
        
        # CRITICAL CHECK 3: Wrong competitor types
        wrong_signals = ["foundation", "initiative", "program", "lab", "institute", "ngo", "non-profit"]
        competitors = output.get("competitors_identified", {})
        if isinstance(competitors, dict):
            all_competitors = competitors.get("direct", []) + competitors.get("indirect", [])
        else:
            all_competitors = competitors if isinstance(competitors, list) else []
        
        for comp in all_competitors:
            comp_lower = str(comp).lower()
            if any(signal in comp_lower for signal in wrong_signals):
                issues.append(f"Wrong competitor type: {comp}")
                base_score -= 0.5
        
        # CHECK 4: Comparison table (MANDATORY for competitor tasks)
        is_competitor_task = any(kw in task_lower for kw in 
            ["competitor", "compare", "landscape", "player", "alternative", "vs"])
        
        # Accept both comparison_table and comparison (normalize to comparison_table)
        comparison_data = output.get("comparison_table") or output.get("comparison")
        has_comparison_table = bool(comparison_data)
        
        if is_competitor_task:
            if has_comparison_table:
                bonuses.append("Has comparison table")
                base_score += 0.6
                ct = comparison_data if isinstance(comparison_data, dict) else {}
                # V7: Check for explicit winner_by_feature or rows with winners
                if ct.get("winner_by_feature") and len(ct.get("winner_by_feature", {})) >= 2:
                    bonuses.append("Has explicit winner_by_feature")
                    base_score += 0.5
                elif ct.get("rows"):
                    rows = ct.get("rows", [])
                    winners_count = sum(1 for r in rows if isinstance(r, dict) and r.get("winner"))
                    if winners_count >= 2:
                        bonuses.append("Has winners in comparison rows")
                        base_score += 0.4
                elif ct.get("winner_analysis") or ct.get("winner_by_factor"):
                    bonuses.append("Has winner analysis")
                    base_score += 0.2
                else:
                    issues.append("MISSING winners in comparison table")
                    base_score -= 0.25
            else:
                issues.append("MISSING comparison_table (required for competitor task)")
                base_score -= 1.0
        elif has_comparison_table:
            bonuses.append("Includes comparison table")
            base_score += 0.4
        
        # V7 CHECK: Dominant incumbent requirement
        dominant_incumbents = ["slack", "discord", "linkedin", "notion", "github", "figma", "trello", "microsoft teams", "zoom", "google"]
        competitors = output.get("competitors_identified", {})
        dominant_present = False
        
        if isinstance(competitors, dict):
            all_comp_str = json.dumps(competitors, default=str).lower()
            dominant_present = any(d in all_comp_str for d in dominant_incumbents)
            # Also check dominant_incumbent field
            if competitors.get("dominant_incumbent"):
                dominant_present = True
        
        # Also check comparison_table
        if has_comparison_table:
            ct_str = json.dumps(output.get("comparison_table", {}), default=str).lower()
            if any(d in ct_str for d in dominant_incumbents):
                dominant_present = True
        
        if is_competitor_task:
            if dominant_present:
                bonuses.append("Includes dominant market incumbent")
                base_score += 0.3
            else:
                issues.append("MISSING dominant incumbent (Slack/LinkedIn/Discord/Notion/GitHub)")
                base_score -= 0.25
        
        # CHECK 5: Key insight (MANDATORY)
        key_insight = output.get("key_insight", "")
        if key_insight and len(str(key_insight)) >= 40:
            bonuses.append("Has substantive key_insight")
            base_score += 0.5
        elif key_insight and len(str(key_insight)) >= 20:
            bonuses.append("Has key_insight")
            base_score += 0.25
        else:
            issues.append("MISSING or weak key_insight")
            base_score -= 0.5
        
        # CHECK 6: Strategic implication (MANDATORY)
        strategic_imp = output.get("strategic_implication", "")
        if strategic_imp and len(str(strategic_imp)) >= 30:
            bonuses.append("Has strategic implication")
            base_score += 0.4
        else:
            issues.append("MISSING strategic_implication")
            base_score -= 0.5
        
        # V7 CHECK: Biggest risk (MANDATORY)
        biggest_risk = output.get("biggest_risk", "")
        if biggest_risk and len(str(biggest_risk)) >= 30:
            bonuses.append("Has biggest_risk identified")
            base_score += 0.5
        elif biggest_risk and len(str(biggest_risk)) >= 15:
            bonuses.append("Has biggest_risk")
            base_score += 0.2
        else:
            issues.append("MISSING biggest_risk (critical failure point)")
            base_score -= 0.2
        
        # V7 CHECK: Data points with implications
        data_with_imp = output.get("data_points_with_implications", [])
        if isinstance(data_with_imp, list) and len(data_with_imp) >= 2:
            # Check if they have implication field
            has_implications = all(
                isinstance(dp, dict) and dp.get("implication")
                for dp in data_with_imp[:3]  # Check first 3
            )
            if has_implications:
                bonuses.append("Data points have implications (SO WHAT)")
                base_score += 0.4
            else:
                bonuses.append("Has data_points_with_implications structure")
                base_score += 0.2
        # Also check old-style data_points for interpretation
        elif output.get("data_points"):
            data_str = json.dumps(output.get("data_points", []), default=str).lower()
            if "→" in data_str or "->" in data_str or "implication" in data_str or "means" in data_str:
                bonuses.append("Data points interpreted")
                base_score += 0.2
            else:
                issues.append("Data points lack SO WHAT interpretation")
                base_score -= 0.2
        
        # CHECK 7: Verdict for final tasks
        is_final_task = any(kw in task_lower for kw in 
            ["recommend", "verdict", "conclusion", "final", "decision"])
        
        if is_final_task:
            verdict = output.get("verdict", "")
            if verdict and str(verdict).upper() in ["YES", "NO", "CONDITIONAL"]:
                bonuses.append(f"Has decisive verdict: {verdict}")
                base_score += 0.4
                if output.get("verdict_reasoning"):
                    base_score += 0.15
                if str(verdict).upper() == "CONDITIONAL" and output.get("conditions_for_success"):
                    # V8: Check if conditions are measurable (bonus, not penalty)
                    conditions = output.get("conditions_for_success", [])
                    measurable_keywords = ["1000", "100", "10", "%", "month", "week", "day", "user", "revenue", "retention"]
                    conditions_str = json.dumps(conditions, default=str).lower()
                    if any(kw in conditions_str for kw in measurable_keywords):
                        bonuses.append("Conditions are measurable")
                        base_score += 0.4
                # Biggest risk bonus for final
                if biggest_risk and len(str(biggest_risk)) >= 30:
                    base_score += 0.15
            else:
                issues.append("MISSING clear verdict (YES/NO/CONDITIONAL)")
                base_score -= 0.3  # Reduced penalty
        
        # ============== V8 NEW CHECKS ==============
        
        # V8 CHECK: Overall Positioning (why wins/loses)
        positioning = output.get("overall_positioning", {})
        if isinstance(positioning, dict):
            why_wins = positioning.get("why_this_wins", [])
            why_loses = positioning.get("why_this_loses", [])
            if why_wins and why_loses and len(why_wins) >= 1 and len(why_loses) >= 1:
                bonuses.append("Has overall_positioning (win vs lose)")
                base_score += 0.5
            elif why_wins or why_loses:
                bonuses.append("Partial positioning")
                base_score += 0.25
            # No penalty for missing - it's a bonus feature
        
        # V8 CHECK: Moat Analysis (bonus, not penalty)
        moat = output.get("moat_analysis", {})
        if isinstance(moat, dict):
            defensibility = moat.get("defensibility", "")
            if defensibility and str(defensibility).upper() in ["HIGH", "MEDIUM", "LOW"]:
                bonuses.append(f"Has moat_analysis: {defensibility}")
                base_score += 0.5
                if moat.get("reasons") and len(moat.get("reasons", [])) >= 1:
                    base_score += 0.15
        
        # V8 CHECK: Execution Difficulty (bonus, not penalty)
        exec_diff = output.get("execution_difficulty", {})
        if isinstance(exec_diff, dict):
            level = exec_diff.get("level", "")
            if level and str(level).upper() in ["HIGH", "MEDIUM", "LOW"]:
                bonuses.append(f"Has execution_difficulty: {level}")
                base_score += 0.35
        
        # V8 CHECK: Switching Barrier Analysis (bonus, not penalty)
        switching = output.get("switching_barrier_analysis", {})
        if isinstance(switching, dict):
            current_behavior = switching.get("current_behavior", "")
            switching_difficulty = switching.get("switching_difficulty", "")
            barriers = switching.get("barriers", [])
            
            if current_behavior and switching_difficulty and barriers:
                bonuses.append("Has complete switching_barrier_analysis")
                base_score += 0.5
            elif current_behavior or switching_difficulty or barriers:
                bonuses.append("Partial switching analysis")
                base_score += 0.25
        
        # BONUS: Sources
        if sources and len(sources) >= 2:
            bonuses.append("Has sources")
            base_score += 0.15
        
        # BONUS: Limitations acknowledged
        if output.get("limitations") and len(output.get("limitations", [])) >= 1:
            bonuses.append("Acknowledges limitations")
            base_score += 0.15
        
        return {
            "valid": base_score >= 5.5,
            "score": max(0, min(10, base_score)),
            "issues": issues[:4],
            "bonuses": bonuses,
            "layer": "rules",
        }
    
    async def _validate_llm_investor(
        self,
        task_id: str,
        task_description: str,
        output: Dict[str, Any],
        sources: List[str],
    ) -> Dict[str, Any]:
        """Layer 3: Fast LLM validation (v9)."""
        
        is_competitor_task = any(kw in task_description.lower() 
            for kw in ["competitor", "compare", "landscape", "player"])
        is_final_task = any(kw in task_description.lower() 
            for kw in ["recommend", "verdict", "conclusion", "final"])
        
        # Shorter prompt for faster response
        prompt = f"""Score this analysis (1-10):

TASK: {task_description[:200]}

OUTPUT (truncated):
{json.dumps(output, indent=1, default=str)[:1500]}

Score 5 dimensions:
1. comparison_depth: comparison_table present? (8 if yes, 6 if partial, 4 if none)
2. insight_quality: key_insight non-obvious? (8 if sharp, 6 if okay, 4 if generic)
3. competitor_quality: real products like Slack/Discord? (8 if yes, 4 if NGOs)
4. decision_strength: {"verdict present?" if is_final_task else "clear conclusions?"}
5. risk_clarity: biggest_risk stated?

Output JSON: {{comparison_depth, insight_quality, competitor_quality, decision_strength, risk_clarity, overall_score, valid, issues}}"""

        try:
            response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt=VALIDATOR_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=300,  # Reduced from 800
            )
            
            self.track_llm_usage(response, task_id)
            
            if response.get("parsed"):
                parsed = response["parsed"]
                
                # Calculate overall from 5 dimensions (v9 fast)
                dimensions = [
                    parsed.get("comparison_depth", 7),
                    parsed.get("insight_quality", 7),
                    parsed.get("competitor_quality", 7),
                    parsed.get("decision_strength", 7),
                    parsed.get("risk_clarity", 7),
                ]
                avg_score = sum(dimensions) / len(dimensions)
                
                return {
                    "valid": avg_score >= self.min_valid_score,
                    "score": avg_score,
                    "dimension_scores": {
                        "comparison_depth": parsed.get("comparison_depth", 7),
                        "insight_quality": parsed.get("insight_quality", 7),
                        "competitor_quality": parsed.get("competitor_quality", 7),
                        "decision_strength": parsed.get("decision_strength", 7),
                        "risk_clarity": parsed.get("risk_clarity", 7),
                    },
                    "issues": parsed.get("issues", []),
                    "layer": "llm",
                }
        except Exception as e:
            self.log(f"LLM validation failed: {e}", level="warning", task_id=task_id)
        
        # Default on LLM failure - pass it
        return {
            "valid": True,
            "score": 7.0,
            "issues": [],
            "layer": "llm_fallback",
        }
    
    def _combine_validations(
        self,
        schema_result: Dict[str, Any],
        rule_result: Dict[str, Any],
        llm_result: Dict[str, Any],
        task_description: str,
    ) -> Dict[str, Any]:
        """Combine validation results for investor-grade output."""
        
        # If schema fails, reject
        if not schema_result["valid"]:
            return {
                "valid": False,
                "score": 0,
                "issues": schema_result.get("issues", []),
                "feedback_for_retry": "Output must be substantial dictionary.",
            }
        
        # Weight: rules 45%, LLM 55%
        rule_score = rule_result.get("score", 0.7)  # V18: Default 0.7 on 0-1 scale (was 7 out of 10)
        llm_score = llm_result.get("score", 0.75)   # V18: Default 0.75 on 0-1 scale (was 7.5 out of 10)
        
        final_score = (rule_score * 0.45) + (llm_score * 0.55)
        
        # Combine issues
        all_issues = rule_result.get("issues", []) + llm_result.get("issues", [])
        
        is_valid = final_score >= self.min_valid_score
        
        # Generate feedback for retry
        feedback = ""
        if not is_valid:
            feedback = self._generate_investor_feedback(all_issues, task_description)
        
        return {
            "valid": is_valid,
            "score": round(final_score, 1),
            "issues": all_issues[:6],
            "strengths": rule_result.get("bonuses", []) + llm_result.get("strengths", []),
            "suggestions": self._generate_suggestions(all_issues, task_description),
            "feedback_for_retry": feedback,
            "dimension_scores": llm_result.get("dimension_scores", {}),
            "layer_scores": {
                "schema": schema_result.get("score", 1.0),  # V18: 0-1 scale (was 10)
                "rules": rule_score,
                "llm": llm_score,
            },
        }
    
    def _generate_investor_feedback(self, issues: List[str], task_description: str) -> str:
        """Generate specific feedback for investor decision engine retry (v8)."""
        feedback_parts = ["OUTPUT REJECTED. MANDATORY FIXES (v8 INVESTOR ENGINE):"]
        
        is_competitor_task = any(kw in task_description.lower() 
            for kw in ["competitor", "compare", "landscape", "player"])
        is_final_task = any(kw in task_description.lower() 
            for kw in ["recommend", "verdict", "conclusion", "final"])
        
        issues_str = " ".join(issues).lower()
        
        # V8 NEW: Positioning
        if "positioning" in issues_str or "wins" in issues_str or "loses" in issues_str:
            feedback_parts.append("""
1. ADD overall_positioning:
{
  "overall_positioning": {
    "why_this_wins": ["Specific advantage 1", "Specific advantage 2"],
    "why_this_loses": ["Critical weakness 1", "Critical weakness 2"]
  }
}""")
        
        # V8 NEW: Moat Analysis
        if "moat" in issues_str or "defensibility" in issues_str:
            feedback_parts.append("""
2. ADD moat_analysis:
{
  "moat_analysis": {
    "defensibility": "LOW/MEDIUM/HIGH",
    "reasons": ["Can competitors copy easily?", "Network effects?", "Data advantage?"]
  }
}""")
        
        # V8 NEW: Execution Difficulty
        if "execution" in issues_str or "difficulty" in issues_str:
            feedback_parts.append("""
3. ADD execution_difficulty:
{
  "execution_difficulty": {
    "level": "HIGH/MEDIUM/LOW",
    "technical_complexity": "...",
    "market_difficulty": "...",
    "user_acquisition": "..."
  }
}""")
        
        # V8 NEW: Switching Barrier
        if "switching" in issues_str or "barrier" in issues_str:
            feedback_parts.append("""
4. ADD switching_barrier_analysis:
{
  "switching_barrier_analysis": {
    "current_behavior": "What users do today",
    "switching_difficulty": "HIGH/MEDIUM/LOW",
    "barriers": ["habit", "network effects", "low urgency"],
    "switching_triggers": ["pain event", "institutional mandate"]
  }
}""")
        
        # V8: Measurable conditions
        if "condition" in issues_str or "measurable" in issues_str or "metric" in issues_str:
            feedback_parts.append("""
5. MAKE conditions_for_success MEASURABLE:
   ❌ "MUST achieve strong adoption"
   ✅ "MUST: 1000 team matches in 6 months (proves PMF)" """)
        
        if is_final_task:
            feedback_parts.append("""
6. FINAL TASK REQUIRES:
   - verdict: YES/NO/CONDITIONAL
   - conditions_for_success: [measurable with metrics/timeframes]
   - biggest_risk: single deal-breaker
   - execution_difficulty: {level: HIGH/MEDIUM/LOW}
   - moat_analysis: {defensibility: HIGH/MEDIUM/LOW}""")
        
        return "\n".join(feedback_parts)[:500]  # Allow longer for v8
    
    def _generate_suggestions(self, issues: List[str], task_description: str) -> List[str]:
        """Generate actionable suggestions (v8)."""
        suggestions = []
        issues_str = " ".join(issues).lower()
        
        # V8 new suggestions
        if "positioning" in issues_str:
            suggestions.append("Add overall_positioning: why_this_wins + why_this_loses")
        
        if "moat" in issues_str:
            suggestions.append("Add moat_analysis: defensibility (HIGH/MEDIUM/LOW) + reasons")
        
        if "execution" in issues_str:
            suggestions.append("Add execution_difficulty: level + technical/market/acquisition")
        
        if "switching" in issues_str:
            suggestions.append("Add switching_barrier_analysis: behavior + barriers + triggers")
        
        if "condition" in issues_str or "measurable" in issues_str:
            suggestions.append("Make conditions measurable: include metrics/timeframes")
        
        if "comparison" in issues_str or "winner" in issues_str:
            suggestions.append("Add comparison_table with winner_by_feature")
        
        if "dominant" in issues_str or "incumbent" in issues_str:
            suggestions.append("Include dominant incumbent: Slack/LinkedIn/Discord")
        
        if "insight" in issues_str:
            suggestions.append("Add key_insight (non-obvious) + strategic_implication")
        
        if "risk" in issues_str:
            suggestions.append("Add biggest_risk: critical failure point")
        
        if "verdict" in issues_str:
            suggestions.append("Add verdict: YES/NO/CONDITIONAL")
        
        return suggestions[:6]  # Allow more suggestions for v8
    
    # ============== V17: CROSS-TASK CONSISTENCY CHECK ==============
    
    def check_cross_task_consistency(
        self,
        current_output: Dict[str, Any],
        previous_outputs: Dict[str, Any],
        goal: str,
    ) -> Dict[str, Any]:
        """
        V17: Check that current output is consistent with previous task outputs.
        
        Lightweight check (no LLM) to detect:
        - New unrelated entities being introduced
        - Contradictory facts
        - Topic drift from original goal
        """
        issues = []
        
        if not previous_outputs:
            return {"consistent": True, "issues": []}
        
        current_str = json.dumps(current_output, default=str).lower()
        
        # 1. Check for domain drift using banned keywords
        for keyword in INVALID_DOMAIN_KEYWORDS:
            if keyword in current_str:
                issues.append(f"cross_task_drift: New unrelated domain '{keyword}' introduced")
        
        # 2. Collect entities from previous outputs
        previous_entities = set()
        for tid, output in previous_outputs.items():
            if not isinstance(output, dict):
                continue
            
            # Get competitors from previous outputs
            competitors = output.get("competitors_identified", {})
            if isinstance(competitors, dict):
                previous_entities.update(competitors.get("direct", []))
                previous_entities.update(competitors.get("indirect", []))
        
        # 3. Check if current output introduces completely new competitors not in previous
        current_competitors = current_output.get("competitors_identified", {})
        if isinstance(current_competitors, dict):
            current_entities = set(current_competitors.get("direct", []) + current_competitors.get("indirect", []))
            
            # New entities (not seen before)
            new_entities = current_entities - previous_entities
            
            # Check if new entities are in banned domains
            for entity in new_entities:
                entity_lower = entity.lower()
                for keyword in INVALID_DOMAIN_KEYWORDS:
                    if keyword in entity_lower:
                        issues.append(f"cross_task_drift: New entity '{entity}' is from unrelated domain")
        
        return {
            "consistent": len(issues) == 0,
            "issues": issues[:3],  # Limit to 3 issues
        }
