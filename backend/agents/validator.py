"""Validator Agent - Multi-layer validation (v9 - Fast & Sharp)."""

import json
from typing import Dict, Any, Optional, List
import logging
import re

from agents.base_agent import BaseAgent
from models.schemas import ValidationResult

logger = logging.getLogger(__name__)


# ============== V9 VALIDATOR SYSTEM PROMPT (FAST) ==============
VALIDATOR_SYSTEM_PROMPT = """Score this startup analysis 1-10 on these dimensions:

1. comparison_depth: Has comparison_table with real products?
2. insight_quality: key_insight is non-obvious? strategic_implication is actionable?
3. competitor_quality: Real products (Slack/Discord/LinkedIn), not NGOs?
4. decision_strength: Clear verdict (YES/NO/CONDITIONAL)?
5. risk_clarity: biggest_risk explicitly stated?

Auto-reject if: empty output, placeholder text, NGOs as competitors.

Output JSON: {comparison_depth, insight_quality, competitor_quality, decision_strength, risk_clarity, overall_score, valid, issues}"""


class ValidatorAgent(BaseAgent):
    """Agent for fast validation (v9)."""
    
    def __init__(self, run_id: str):
        super().__init__(run_id, "validator")
        self.min_valid_score = 6.0  # 60% threshold - faster pass rate
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate task output with fast checks."""
        task_id = context.get("task_id", "unknown")
        task_description = context.get("task_description", "")
        output = context.get("output", {})
        sources = context.get("sources", [])
        previous_outputs = context.get("previous_outputs", {})
        classification = context.get("classification", {})
        
        self.log(f"Validating output for task {task_id}", task_id=task_id)
        
        # Layer 1: Schema validation
        schema_result = self._validate_schema(output)
        if not schema_result["valid"]:
            return {"success": True, "validation": schema_result}
        
        # Layer 2: Rule-based validation (investor grade)
        rule_result = self._validate_rules_investor(output, sources, task_description)
        
        # Layer 3: LLM-based quality assessment
        llm_result = await self._validate_llm_investor(
            task_id,
            task_description,
            output,
            sources,
        )
        
        # Combine results
        combined = self._combine_validations(schema_result, rule_result, llm_result, task_description)
        
        self.log(
            f"Validation: score={combined['score']:.1f}, valid={combined['valid']}",
            task_id=task_id,
        )
        
        return {
            "success": True,
            "validation": combined,
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
    ) -> Dict[str, Any]:
        """Layer 2: Investor-grade rule-based validation (v8 balanced)."""
        issues = []
        bonuses = []
        base_score = 7.5  # Start higher for v8 balanced approach
        
        output_str = json.dumps(output, default=str).lower()
        task_lower = task_description.lower()
        
        # CRITICAL CHECK 1: Placeholder detection
        placeholders = ["entity 1", "entity 2", "[product]", "[company]", "platform a", "platform b", "company x"]
        for placeholder in placeholders:
            if placeholder in output_str:
                issues.append(f"Contains placeholder: '{placeholder}'")
                base_score -= 1.5  # Reduced from 2.0
        
        # CRITICAL CHECK 2: Generic banned phrases (reduced penalty)
        banned_phrases = [
            ("market is growing", "Generic: 'market is growing' - needs SO WHAT"),
            ("competition is high", "Generic: 'competition is high' - name winners"),
            ("shows promise", "Vague: 'shows promise' - be decisive"),
            ("has potential", "Vague: 'has potential' - state conditions"),
            ("could be viable", "Vague: 'could be viable' - make a decision"),
        ]
        for phrase, issue in banned_phrases:
            if phrase in output_str:
                issues.append(issue)
                base_score -= 0.4
        
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
        
        has_comparison_table = bool(output.get("comparison_table"))
        
        if is_competitor_task:
            if has_comparison_table:
                bonuses.append("Has comparison table")
                base_score += 0.6
                ct = output.get("comparison_table", {})
                # V7: Check for explicit winner_by_feature
                if ct.get("winner_by_feature") and len(ct.get("winner_by_feature", {})) >= 2:
                    bonuses.append("Has explicit winner_by_feature")
                    base_score += 0.5
                elif ct.get("winner_analysis") or ct.get("winner_by_factor"):
                    bonuses.append("Has winner analysis")
                    base_score += 0.2
                else:
                    issues.append("MISSING winner_by_feature in comparison table")
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
        rule_score = rule_result.get("score", 7)
        llm_score = llm_result.get("score", 7.5)
        
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
                "schema": schema_result.get("score", 10),
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
