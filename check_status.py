"""
Quick Status Check - Paste your run_id below
"""

import requests
import json

# PASTE YOUR RUN_ID HERE (from the dashboard URL)
RUN_ID = ""  # Example: "abc-1234-def-5678"

if not RUN_ID:
    print("=" * 70)
    print("Please paste your run_id!")
    print("=" * 70)
    print("\n1. Look at your browser Dashboard URL")
    print("   Example: http://localhost:3000/dashboard/abc-1234-def")
    print("                                              ^^^^^^^^^^^^")
    print("\n2. Copy the run_id (the part after /dashboard/)")
    print("\n3. Edit this file and paste it in line 8:")
    print("   RUN_ID = 'your-run-id-here'")
    print("\n4. Run this script again: python check_status.py")
    print("=" * 70)
    exit(1)

def check_status():
    print("=" * 70)
    print(f"Checking status for run: {RUN_ID}")
    print("=" * 70)
    
    try:
        response = requests.get(f"http://localhost:3001/api/status/{RUN_ID}", timeout=5)
        
        if response.status_code == 404:
            print("\nERROR: Run not found!")
            print("Double-check the run_id is correct.")
            return
        
        response.raise_for_status()
        data = response.json()
        
        print(f"\nStatus: {data.get('status', 'unknown').upper()}")
        print(f"Current Task: {data.get('current_task_id', 'N/A')}")
        
        tasks = data.get('tasks', [])
        print(f"\nTasks: {len(tasks)} total")
        
        for task in tasks:
            task_id = task.get('task_id', '?')
            status = task.get('status', '?')
            desc = task.get('task_description', '')[:60]
            retries = task.get('retries', 0)
            
            icon = "✓" if status == "completed" else "→" if status == "in_progress" else "○" if status == "pending" else "✗"
            retry_info = f" (retry {retries})" if retries > 0 else ""
            
            print(f"  {icon} {task_id}: {status}{retry_info}")
            print(f"     {desc}...")
        
        if data.get('status') in ['pending_user_review', 'completed']:
            print("\n" + "=" * 70)
            print("ANALYSIS COMPLETE! Check the report:")
            print(f"http://localhost:3000/report/{RUN_ID}")
            print("=" * 70)
        
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    check_status()
