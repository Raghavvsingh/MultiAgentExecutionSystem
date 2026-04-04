"""
Helper functions for generating example-based retry feedback.
Part of MASTER GREYBOX PROMPT implementation.
"""

def generate_retry_feedback_with_examples(
    validation: dict,
    output: dict,
    retry_count: int
) -> str:
    """
    Generate retry feedback with good/bad examples.
    Required by MASTER GREYBOX PROMPT for better retry quality.
    """
    
    issues = validation.get("issues", [])
    missing = validation.get("missing_fields", [])
    
    feedback_parts = [
        "⚠️ OUTPUT REJECTED - FIX THESE SPECIFIC ISSUES:\n"
    ]
    
    # Add specific issues
    if issues:
        feedback_parts.append("ISSUES FOUND:")
        for issue in issues[:5]:
            feedback_parts.append(f"  • {issue}")
        feedback_parts.append("")
    
    # key_insight examples
    if "key_insight" in missing or any("generic" in str(i).lower() and "insight" in str(i).lower() for i in issues):
        feedback_parts.extend([
            "❌ BAD key_insight (generic):",
            '  "The market is growing"',
            '  "Competition is high"',
            '  "Shows promise"',
            "",
            "✅ GOOD key_insight (sharp, non-obvious):",
            '  "Notion dominates teams but Obsidian captures power users - reveals fundamental tradeoff between collaboration and data sovereignty"',
            '  "Slack\'s $8-15/user pricing creates opening for Discord\'s free tier in educational communities"',
            ""
        ])
    
    # strategic_implication examples
    if "strategic_implication" in missing or any("strategic" in str(i).lower() for i in issues):
        feedback_parts.extend([
            "❌ BAD strategic_implication (vague):",
            '  "Worth exploring"',
            '  "Consider this market"',
            "",
            "✅ GOOD strategic_implication (actionable):",
            '  "Target individual knowledge workers exclusively - do NOT serve teams where Notion dominates"',
            '  "Focus on budget-conscious segments where free tier matters more than enterprise features"',
            ""
        ])
    
    # comparison examples
    if "comparison" in missing:
        feedback_parts.extend([
            "❌ MISSING: Structured comparison",
            "✅ REQUIRED: Comparison with explicit winners:",
            '{',
            '  "comparison": {',
            '    "rows": [',
            '      {"attribute": "Pricing", "winner": "Obsidian", "explanation": "Free vs $8/user"},',
            '      {"attribute": "Collaboration", "winner": "Notion", "explanation": "Built for teams"}',
            '    ]',
            '  }',
            '}',
            ""
        ])
    
    # competitor examples
    if any("competitor" in str(i).lower() or "placeholder" in str(i).lower() for i in issues):
        feedback_parts.extend([
            "❌ BAD competitors:",
            '  "Platform A", "Company X", "EdTech Foundation"',
            "",
            "✅ GOOD competitors (real companies):",
            '  "Notion", "Slack", "Discord", "Obsidian"',
            ""
        ])
    
    feedback_parts.extend([
        "MANDATORY FIXES:",
        "1. ALL required fields (summary, key_findings, comparison, key_insight, strategic_implication, biggest_risk)",
        "2. REAL company names only",
        "3. SHARP key_insight (not generic)",
        "4. ACTIONABLE strategic_implication",
        "5. Structured comparison with winners"
    ])
    
    if retry_count >= 2:
        feedback_parts.append("\n⚠️ FINAL RETRY - MUST BE COMPLETE")
    
    return "\n".join(feedback_parts)
