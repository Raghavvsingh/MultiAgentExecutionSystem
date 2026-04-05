"""Test script to verify report generation in OrchestAI."""

import requests
import time
import json
import sys

BASE_URL = "http://localhost:3001/api"

def check_backend():
    """Check if backend is running."""
    try:
        response = requests.get("http://localhost:3001/health", timeout=5)
        print(f"✅ Backend is running: {response.json()}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Backend is NOT running on port 3001")
        print("Please start it with: cd backend && python main.py")
        return False
    except Exception as e:
        print(f"❌ Error checking backend: {e}")
        return False

def start_analysis(goal):
    """Start a new analysis."""
    print(f"\n📝 Starting analysis: '{goal}'")
    try:
        response = requests.post(
            f"{BASE_URL}/start-analysis",
            json={"goal": goal},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        run_id = data.get("run_id")
        print(f"✅ Analysis started: run_id={run_id}")
        return run_id
    except Exception as e:
        print(f"❌ Failed to start analysis: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return None

def check_status(run_id):
    """Check analysis status."""
    try:
        response = requests.get(f"{BASE_URL}/status/{run_id}", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return None

def get_result(run_id):
    """Get final result."""
    try:
        response = requests.get(f"{BASE_URL}/result/{run_id}", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPException as e:
        if e.response.status_code == 202:
            print("⏳ Analysis still in progress...")
            return None
        elif e.response.status_code == 400:
            print(f"⚠️ Analysis not ready: {e.response.json().get('detail')}")
            return None
        raise
    except Exception as e:
        print(f"❌ Error getting result: {e}")
        return None

def monitor_analysis(run_id, timeout=300):
    """Monitor analysis until completion."""
    print(f"\n🔍 Monitoring analysis: {run_id}")
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        status_data = check_status(run_id)
        
        if status_data:
            status = status_data.get("status")
            current_task = status_data.get("current_task_id", "N/A")
            
            if status != last_status:
                print(f"📊 Status: {status} | Current Task: {current_task}")
                last_status = status
            
            # Check if completed or failed
            if status in ["pending_user_review", "completed"]:
                print(f"✅ Analysis completed with status: {status}")
                return True
            elif status == "failed":
                print(f"❌ Analysis failed")
                return False
        
        time.sleep(5)  # Check every 5 seconds
    
    print(f"⏱️ Timeout reached after {timeout}s")
    return False

def verify_report(run_id):
    """Verify the generated report."""
    print(f"\n📄 Fetching report for run_id: {run_id}")
    
    result = get_result(run_id)
    
    if not result:
        print("❌ Failed to fetch report")
        return False
    
    print("\n=== REPORT VERIFICATION ===")
    
    # Check basic fields
    print(f"Goal: {result.get('goal', 'MISSING')}")
    print(f"Status: {result.get('status', 'MISSING')}")
    
    # Check final_report structure
    final_report = result.get('final_report')
    if not final_report:
        print("❌ final_report is NULL or missing!")
        return False
    
    print("✅ final_report exists")
    
    # Check sections
    sections = final_report.get('sections', {})
    print(f"✅ Sections: {len(sections)} tasks")
    
    # Check final_output
    final_output = final_report.get('final_output', {})
    if not final_output:
        print("⚠️ final_output is missing!")
    else:
        print("✅ final_output exists")
        
        # Check critical fields
        has_summary = 'summary' in final_output
        has_key_insight = 'key_insight' in final_output
        has_table = 'table' in final_output
        has_verdict = 'final_verdict' in final_output
        
        print(f"  - summary: {'✅' if has_summary else '❌'} {final_output.get('summary', '')[:50] if has_summary else 'MISSING'}...")
        print(f"  - key_insight: {'✅' if has_key_insight else '❌'}")
        print(f"  - table: {'✅' if has_table else '❌'} ({len(final_output.get('table', {}).get('rows', []))} rows)")
        print(f"  - final_verdict: {'✅' if has_verdict else '❌'}")
        
        if not has_summary:
            print("\n⚠️ WARNING: final_output.summary is missing!")
            print("This will cause 'Analysis summary not available' in frontend")
            
            # Check fallback sources
            exec_summary = final_report.get('executive_summary')
            first_task_summary = None
            if sections:
                first_section = next(iter(sections.values()))
                first_task_summary = first_section.get('output', {}).get('summary')
            
            print(f"\nFallback sources:")
            print(f"  - executive_summary: {'✅' if exec_summary else '❌'}")
            print(f"  - first task summary: {'✅' if first_task_summary else '❌'}")
    
    # Check tasks
    tasks = result.get('tasks', [])
    print(f"\n✅ Tasks: {len(tasks)} total")
    completed = sum(1 for t in tasks if t.get('status') == 'completed')
    failed = sum(1 for t in tasks if t.get('status') == 'failed')
    print(f"  - Completed: {completed}")
    print(f"  - Failed: {failed}")
    
    # Check cost
    total_cost = result.get('total_cost', {})
    print(f"\n💰 Cost: ${total_cost.get('estimated_cost_usd', 0):.4f}")
    
    print("\n=== REPORT STRUCTURE ===")
    print(json.dumps({
        "has_final_report": bool(final_report),
        "has_final_output": bool(final_output),
        "has_summary": has_summary if final_output else False,
        "sections_count": len(sections),
        "tasks_count": len(tasks),
        "status": result.get('status')
    }, indent=2))
    
    return True

def main():
    """Main test function."""
    print("=" * 60)
    print("OrchestAI Report Generation Test")
    print("=" * 60)
    
    # Step 1: Check backend
    if not check_backend():
        sys.exit(1)
    
    # Step 2: Start analysis
    test_goal = "Compare Notion and Obsidian for note-taking"
    run_id = start_analysis(test_goal)
    
    if not run_id:
        sys.exit(1)
    
    # Step 3: Monitor until completion
    success = monitor_analysis(run_id, timeout=600)  # 10 minutes max
    
    if not success:
        print("\n❌ Analysis did not complete successfully")
        sys.exit(1)
    
    # Step 4: Verify report
    time.sleep(2)  # Brief delay to ensure DB is updated
    verify_report(run_id)
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print(f"View report at: http://localhost:3000/report/{run_id}")
    print("=" * 60)

if __name__ == "__main__":
    main()
