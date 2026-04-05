"""
Real-time Backend Monitor for OrchestAI
Monitors the database to track analysis progress
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:3001/api"
CHECK_INTERVAL = 3  # seconds

def get_latest_run():
    """Get the most recent run from status check."""
    try:
        # Try to get recent runs - we'll need to query for a specific run_id
        # Since we don't have the run_id, let's just monitor health
        response = requests.get("http://localhost:3001/health", timeout=2)
        return response.json()
    except:
        return None

def get_run_status(run_id):
    """Get status of a specific run."""
    try:
        response = requests.get(f"{BASE_URL}/status/{run_id}", timeout=3)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return {"error": str(e)}

def monitor_run(run_id, max_duration=600):
    """Monitor a specific run until completion."""
    print("=" * 70)
    print(f"MONITORING RUN: {run_id}")
    print("=" * 70)
    
    start_time = time.time()
    last_status = None
    last_task_count = 0
    
    while time.time() - start_time < max_duration:
        elapsed = int(time.time() - start_time)
        
        # Get current status
        data = get_run_status(run_id)
        
        if not data or "error" in data:
            print(f"\n[{elapsed}s] Error fetching status: {data.get('error', 'Unknown')}")
            time.sleep(CHECK_INTERVAL)
            continue
        
        status = data.get("status", "unknown")
        current_task = data.get("current_task_id", "N/A")
        tasks = data.get("tasks", [])
        
        # Count task statuses
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
        failed = sum(1 for t in tasks if t.get("status") == "failed")
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        
        # Print status update if changed
        current_summary = f"{status}|{current_task}|{completed}"
        if current_summary != last_status or len(tasks) != last_task_count:
            print(f"\n[{elapsed}s] Status: {status.upper()}")
            print(f"  Current Task: {current_task}")
            print(f"  Tasks: {len(tasks)} total | {completed} done | {in_progress} running | {failed} failed | {pending} pending")
            
            # Show task details
            if tasks:
                print(f"\n  Task Breakdown:")
                for task in tasks:
                    task_id = task.get("task_id", "?")
                    task_status = task.get("status", "?")
                    task_desc = task.get("task_description", "")[:50]
                    retries = task.get("retries", 0)
                    
                    icon = "✓" if task_status == "completed" else "→" if task_status == "in_progress" else "○"
                    retry_str = f" (retry {retries})" if retries > 0 else ""
                    print(f"    {icon} {task_id}: {task_status}{retry_str} - {task_desc}...")
            
            last_status = current_summary
            last_task_count = len(tasks)
        
        # Check if completed
        if status in ["pending_user_review", "completed"]:
            print(f"\n{'=' * 70}")
            print(f"✓ ANALYSIS COMPLETE! Status: {status}")
            print(f"{'=' * 70}")
            print(f"\nTotal time: {elapsed}s")
            print(f"View report at: http://localhost:3000/report/{run_id}")
            return True
        
        if status == "failed":
            print(f"\n{'=' * 70}")
            print(f"✗ ANALYSIS FAILED!")
            print(f"{'=' * 70}")
            return False
        
        time.sleep(CHECK_INTERVAL)
    
    print(f"\n⏱ Timeout reached after {max_duration}s")
    return False

def check_backend_health():
    """Check if backend is running."""
    try:
        response = requests.get("http://localhost:3001/health", timeout=3)
        data = response.json()
        print(f"Backend Status: {data.get('status', 'unknown')}")
        print(f"Database: {data.get('database', 'unknown')}")
        return True
    except requests.exceptions.ConnectionError:
        print("ERROR: Backend is not running on port 3001")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    print("=" * 70)
    print("OrchestAI Backend Monitor")
    print("=" * 70)
    
    # Check backend health
    print("\nChecking backend health...")
    if not check_backend_health():
        print("\nPlease start the backend first:")
        print("  cd backend && python main.py")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    
    # Get run_id from command line or ask user
    if len(sys.argv) > 1:
        run_id = sys.argv[1]
    else:
        print("\nEnter the run_id to monitor:")
        print("(You can find this in the URL: http://localhost:3000/dashboard/{run_id})")
        run_id = input("Run ID: ").strip()
    
    if not run_id:
        print("No run_id provided!")
        sys.exit(1)
    
    # Monitor the run
    success = monitor_run(run_id, max_duration=600)  # 10 minutes max
    sys.exit(0 if success else 1)
