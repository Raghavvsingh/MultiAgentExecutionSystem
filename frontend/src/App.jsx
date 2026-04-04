import React, { useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import LandingPage from './components/LandingPage';
import Dashboard from './components/Dashboard';
import ReportView from './components/ReportView';

function AppContent() {
  const [currentRunId, setCurrentRunId] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  const handleAnalysisStarted = useCallback((runId) => {
    setCurrentRunId(runId);
    navigate(`/dashboard/${runId}`);
  }, [navigate]);

  const isLandingPage = location.pathname === '/';

  return (
    <div className={`min-h-screen ${isLandingPage ? '' : 'bg-slate-900'}`}>
      {/* Only show header on non-landing pages */}
      {!isLandingPage && (
        <header className="bg-slate-800 border-b border-slate-700">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <h1 
                className="text-2xl font-bold text-white cursor-pointer"
                onClick={() => navigate('/')}
              >
                🤖 OrchestAI
              </h1>
              <span className="text-slate-400 text-sm">
                Multi-Agent Competitive Analysis
              </span>
            </div>
          </div>
        </header>
      )}

      {isLandingPage ? (
        <Routes>
          <Route 
            path="/" 
            element={<LandingPage onAnalysisStarted={handleAnalysisStarted} />} 
          />
        </Routes>
      ) : (
        <main className="max-w-7xl mx-auto px-4 py-8">
          <Routes>
            <Route 
              path="/dashboard/:runId" 
              element={<Dashboard />} 
            />
            <Route 
              path="/report/:runId" 
              element={<ReportView />} 
            />
          </Routes>
        </main>
      )}
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
