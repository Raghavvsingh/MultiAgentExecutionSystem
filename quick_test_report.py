"""
Quick Report Generation Test - NO API CALLS NEEDED
===================================================
This test directly calls the report generation logic with mock data.
No OpenAI, no Tavily, no time wasted!
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from agents.coordinator import CoordinatorAgent
from datetime import datetime
import json

def create_mock_coordinator():
    """Create a coordinator with mock data."""
    coordinator = CoordinatorAgent(run_id="test-run-123")
    
    # Mock goal
    coordinator.goal = "Compare Notion and Obsidian for note-taking"
    coordinator.goal_type = "comparison"
    
    # Mock classification
    coordinator.classification = {
        "type": "startup_idea",
        "case_type": "competitor_comparison",
        "domain": "productivity",
        "entities": ["Notion", "Obsidian"]
    }
    
    # Mock tasks
    coordinator.tasks = [
        {
            "id": "T1",
            "task": "Research Notion's features and pricing",
            "depends_on": []
        },
        {
            "id": "T2", 
            "task": "Research Obsidian's features and pricing",
            "depends_on": []
        },
        {
            "id": "T3",
            "task": "Compare both tools on key dimensions",
            "depends_on": ["T1", "T2"]
        }
    ]
    
    # Mock task statuses
    coordinator.task_statuses = {
        "T1": "completed",
        "T2": "completed", 
        "T3": "completed"
    }
    
    # Mock task outputs (this is what ExecutorAgent would return)
    coordinator.task_outputs = {
        "T1": {
            "summary": "Notion is a comprehensive workspace tool with databases, wikis, and project management. Pricing starts at $10/user/month.",
            "key_insight": "Notion excels at structured data and collaboration but has a steeper learning curve.",
            "facts": [
                "Used by 30M+ users globally",
                "All-in-one workspace combining notes, databases, and wikis",
                "$10/month per user for Plus plan"
            ],
            "comparison": {
                "strengths": ["Rich database features", "Team collaboration", "Templates"],
                "weaknesses": ["Steeper learning curve", "Requires internet", "Can be slow"]
            }
        },
        "T2": {
            "summary": "Obsidian is a powerful markdown-based knowledge management tool that works offline. Pricing is free for personal use, $50/user/year for commercial.",
            "key_insight": "Obsidian is ideal for personal knowledge management with its graph view and local-first approach.",
            "facts": [
                "Local-first, markdown-based approach",
                "Powerful linking and graph visualization",
                "Free for personal use, $50/year for commercial"
            ],
            "comparison": {
                "strengths": ["Offline-first", "Fast performance", "Privacy-focused"],
                "weaknesses": ["Less polished UI", "Fewer collaboration features", "Steeper learning curve for beginners"]
            }
        },
        "T3": {
            "summary": "Notion is better for teams needing collaboration and databases, while Obsidian excels for individual knowledge management and research.",
            "key_insight": "The choice depends on whether you prioritize team collaboration (Notion) or personal knowledge graphs (Obsidian).",
            "facts": [
                "Notion has native collaboration features",
                "Obsidian has superior linking and graph view",
                "Both have active plugin ecosystems"
            ]
        }
    }
    
    # Mock global context
    coordinator.global_context = {
        "entity_a": "Notion",
        "entity_b": "Obsidian", 
        "category": "note_taking",
        "insights": [
            "Notion excels at structured data and collaboration",
            "Obsidian is ideal for personal knowledge management",
            "The choice depends on team vs individual use case"
        ],
        "risks": [
            "Notion requires internet connection",
            "Obsidian has steeper learning curve"
        ]
    }
    
    return coordinator

def create_mock_synthesis_result():
    """Create mock synthesis result (what ExecutorAgent.synthesize_all_outputs would return)."""
    return {
        "synthesis": {
            "final_verdict": "CONDITIONAL",
            "final_insight": "Choose Notion for team collaboration and structured workflows, or Obsidian for personal knowledge management and offline work. Both are excellent tools serving different needs.",
            "arguments_for": [
                "Notion offers superior collaboration features",
                "Notion has better database capabilities",
                "Notion provides pre-built templates"
            ],
            "arguments_against": [
                "Notion requires internet connection",
                "Notion can be slower with large workspaces",
                "Higher cost for team usage"
            ],
            "true_competitors": ["Notion", "Obsidian", "Roam Research", "Evernote"],
            "critical_risk": "Vendor lock-in with Notion's proprietary format vs Obsidian's portable markdown files",
            "synthesized_facts": [
                "Notion: 30M+ users, $10/mo, cloud-based",
                "Obsidian: Local-first, $50/year commercial, markdown-based"
            ]
        },
        "final_table": {
            "rows": [
                {
                    "attribute": "Pricing",
                    "entity_a": "$10/user/month",
                    "entity_b": "Free (personal), $50/year (commercial)",
                    "winner": "Obsidian"
                },
                {
                    "attribute": "Collaboration",
                    "entity_a": "Native, real-time",
                    "entity_b": "Limited (via plugins)",
                    "winner": "Notion"
                },
                {
                    "attribute": "Offline Access",
                    "entity_a": "Limited",
                    "entity_b": "Full offline support",
                    "winner": "Obsidian"
                },
                {
                    "attribute": "Learning Curve",
                    "entity_a": "Moderate",
                    "entity_b": "Steep",
                    "winner": "Notion"
                },
                {
                    "attribute": "Data Portability",
                    "entity_a": "Proprietary format",
                    "entity_b": "Plain markdown files",
                    "winner": "Obsidian"
                }
            ]
        },
        "entities": {
            "entity_a": "Notion",
            "entity_b": "Obsidian"
        },
        "category": "note_taking",
        "case_type": "competitor_comparison"
    }

def test_report_generation():
    """Test the report generation with mock data."""
    print("=" * 70)
    print("QUICK REPORT GENERATION TEST - NO API CALLS")
    print("=" * 70)
    
    # Create mock coordinator
    print("\n[1/3] Creating mock coordinator with completed tasks...")
    coordinator = create_mock_coordinator()
    print(f"  ✓ Goal: {coordinator.goal}")
    print(f"  ✓ Tasks: {len(coordinator.tasks)} (all completed)")
    print(f"  ✓ Classification: {coordinator.classification['type']}")
    
    # Create mock synthesis result
    print("\n[2/3] Creating mock synthesis result...")
    synthesis_result = create_mock_synthesis_result()
    print(f"  ✓ Verdict: {synthesis_result['synthesis']['final_verdict']}")
    print(f"  ✓ Table rows: {len(synthesis_result['final_table']['rows'])}")
    
    # Generate report
    print("\n[3/3] Generating final report...")
    try:
        report = coordinator._generate_final_report(synthesis_result)
        print("  ✓ Report generated successfully!")
    except Exception as e:
        print(f"  ✗ ERROR generating report: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verify report structure
    print("\n" + "=" * 70)
    print("REPORT VERIFICATION")
    print("=" * 70)
    
    print("\n[Basic Structure]")
    print(f"  ✓ goal: {report.get('goal', 'MISSING')}")
    print(f"  ✓ goal_type: {report.get('goal_type', 'MISSING')}")
    print(f"  ✓ case_type: {report.get('case_type', 'MISSING')}")
    print(f"  ✓ generated_at: {report.get('generated_at', 'MISSING')}")
    
    print("\n[Sections]")
    sections = report.get('sections', {})
    print(f"  ✓ sections count: {len(sections)}")
    for task_id, section in sections.items():
        print(f"    - {task_id}: {section.get('task', 'N/A')[:50]}...")
    
    print("\n[Top-Level Fields]")
    print(f"  ✓ executive_summary: {len(report.get('executive_summary', ''))} chars")
    if report.get('executive_summary'):
        print(f"      Preview: {report['executive_summary'][:80]}...")
    
    print(f"  ✓ key_findings: {len(report.get('key_findings', []))} items")
    print(f"  ✓ strategic_insights: {len(report.get('strategic_insights', []))} items")
    
    print("\n[final_output - THE CRITICAL SECTION]")
    final_output = report.get('final_output', {})
    
    if not final_output:
        print("  ✗ ERROR: final_output is missing or empty!")
        return False
    
    print("  ✓ final_output exists")
    
    # Check each critical field
    checks = {
        "entities": final_output.get('entities'),
        "summary": final_output.get('summary'),  # ← THE KEY FIX
        "key_insight": final_output.get('key_insight'),
        "table": final_output.get('table'),
        "final_verdict": final_output.get('final_verdict'),
        "true_competitors": final_output.get('true_competitors'),
        "critical_risk": final_output.get('critical_risk')
    }
    
    all_pass = True
    for field, value in checks.items():
        if value is None or (isinstance(value, (list, dict, str)) and not value):
            print(f"  ✗ {field}: MISSING or EMPTY")
            all_pass = False
        else:
            if field == "summary":
                print(f"  ✓ {field}: EXISTS ({len(value)} chars) ← KEY FIX!")
                print(f"      Preview: {value[:100]}...")
            elif field == "table":
                rows = value.get('rows', []) if isinstance(value, dict) else []
                print(f"  ✓ {field}: {len(rows)} rows")
            elif field == "entities":
                print(f"  ✓ {field}: {value}")
            elif isinstance(value, list):
                print(f"  ✓ {field}: {len(value)} items")
            else:
                print(f"  ✓ {field}: exists")
    
    # Print the actual JSON structure
    print("\n[Final Output JSON Structure]")
    print(json.dumps({
        "entities": final_output.get('entities'),
        "summary": f"{final_output.get('summary', '')[:60]}..." if final_output.get('summary') else None,
        "key_insight": f"{final_output.get('key_insight', '')[:60]}..." if final_output.get('key_insight') else None,
        "table_rows": len(final_output.get('table', {}).get('rows', [])),
        "verdict": final_output.get('final_verdict', {}).get('verdict') if final_output.get('final_verdict') else None,
        "has_all_required_fields": all_pass
    }, indent=2))
    
    # Final verdict
    print("\n" + "=" * 70)
    if all_pass:
        print("✅ SUCCESS! Report structure is correct.")
        print("✅ final_output.summary is present (the key fix is working!)")
        print("✅ All required fields are populated.")
        print("\nThe frontend should now display:")
        print("  - Executive Summary: YES (from final_output.summary)")
        print("  - Key Insight: YES")
        print("  - Comparison Table: YES")
        print("  - Strategic Recommendation: YES")
    else:
        print("❌ FAILURE! Some required fields are missing.")
        print("The report generation has issues that need to be fixed.")
    print("=" * 70)
    
    return all_pass

if __name__ == "__main__":
    success = test_report_generation()
    sys.exit(0 if success else 1)
