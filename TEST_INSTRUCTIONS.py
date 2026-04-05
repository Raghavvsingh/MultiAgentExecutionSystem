"""
OrchestAI Report Generation Test - Manual Instructions
========================================================

Since I cannot directly execute the backend, here's how YOU can test:

STEP 1: Start the Backend
--------------------------
In one terminal:
    cd backend
    python main.py

Expected output:
    INFO: Uvicorn running on http://127.0.0.1:3001
    INFO: Database connection successful

STEP 2: Start the Frontend (in another terminal)
-------------------------------------------------
    cd frontend
    npm run dev

Expected output:
    VITE ready in XXXms
    Local: http://localhost:3000/

STEP 3: Run a Test Analysis
----------------------------
Option A - Use the Frontend UI:
1. Go to http://localhost:3000
2. Enter test goal: "Compare Notion and Obsidian for note-taking"
3. Click "Start Analysis"
4. Monitor Dashboard for progress
5. When complete, view Report

Option B - Use Python Script:
Run from project root:
    python test_report_generation.py

Option C - Use curl:
    # Start analysis
    curl -X POST http://localhost:3001/api/start-analysis \
      -H "Content-Type: application/json" \
      -d '{"goal": "Compare Notion and Obsidian"}'
    
    # Get run_id from response, then check status:
    curl http://localhost:3001/api/status/{run_id}
    
    # When status is "pending_user_review", get report:
    curl http://localhost:3001/api/result/{run_id}

STEP 4: Verify Report Structure
--------------------------------
Check console output or API response for:

✅ Required fields in final_report:
   - final_report.sections (has T1, T2, T3...)
   - final_report.final_output
   - final_report.final_output.summary ← THIS IS THE KEY FIX!
   - final_report.final_output.key_insight
   - final_report.final_output.table
   - final_report.final_output.final_verdict

✅ In the frontend Report view:
   - Executive Summary shows text (not "not available")
   - Key Insight displays
   - Task sections show
   - Comparison Table displays
   - Strategic Recommendation displays

STEP 5: Check for Fixes Applied
--------------------------------
Backend fix verification:
    File: backend/agents/coordinator.py
    Line: ~870-885
    Should have: "summary": synthesis.get("final_insight")...

Frontend fix verification:
    File: frontend/src/components/ReportView.jsx
    Line: ~448-452
    Should check: finalOutput.summary || report.executive_summary || ...

TROUBLESHOOTING
---------------
If backend won't start:
    - Check: port 3001 not in use
    - Check: .env file has valid API keys
    - Check: pip install -r requirements.txt completed

If "500 Internal Server Error":
    - Check backend terminal for error traces
    - Check if imports are failing (SQLAlchemy, Tavily)
    - Restart backend after code changes

If report shows "not available":
    - Check backend logs for synthesis errors
    - Verify final_output.summary exists in API response
    - Check browser console for frontend errors

EXPECTED RESULTS
----------------
After 2-5 minutes of analysis:
1. Dashboard shows "Completed" status
2. Report View displays with all sections
3. Executive Summary shows actual text (using synthesis insight or first task summary)
4. Comparison table shows Notion vs Obsidian
5. Strategic Recommendation shows verdict

QUICK VERIFICATION (without running full analysis)
---------------------------------------------------
Check if fixes are applied:

Backend:
    grep -n "\"summary\":" backend/agents/coordinator.py
    # Should show line ~870 in final_output section

Frontend:
    grep -n "finalOutput.summary" frontend/src/components/ReportView.jsx
    # Should show line ~449 with multiple fallbacks

Import fixes:
    python -c "from backend.services.search_service import get_search_service; print('OK')"
    # Should print OK (no AsyncTavilyClient error)
"""

print(__doc__)
