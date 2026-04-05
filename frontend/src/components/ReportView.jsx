import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Clock,
  CheckCircle2, 
  XCircle, 
  Loader2, 
  Download,
  Lightbulb,
  AlertTriangle
} from 'lucide-react';
import { analysisApi } from '../services/api';

// ============================================
// MODULAR COMPONENTS
// ============================================

// Status Badge Component
const StatusBadge = ({ status }) => {
  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-green-50 text-green-700 rounded-full text-sm font-medium">
        <CheckCircle2 className="w-4 h-4" />
        Completed
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-red-50 text-red-600 rounded-full text-sm font-medium">
        <XCircle className="w-4 h-4" />
        Failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm font-medium">
      {status}
    </span>
  );
};

// Pending Review Badge
const PendingReviewBadge = () => (
  <span className="inline-flex items-center px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm font-medium border border-gray-200">
    Pending Review
  </span>
);

// Executive Summary Card
const ExecutiveSummaryCard = ({ summary }) => (
  <div className="bg-white rounded-2xl border border-gray-200 p-6">
    <h2 className="text-lg font-semibold text-gray-900 mb-3">Executive Summary</h2>
    <p className="text-gray-600 leading-relaxed">{summary}</p>
  </div>
);

// Key Insight Card (Yellow/Amber tinted)
const KeyInsightCard = ({ insight }) => (
  <div className="bg-amber-50 rounded-2xl border border-amber-100 p-5">
    <div className="flex items-start gap-3">
      <div className="text-amber-500 mt-0.5">
        <Lightbulb className="w-5 h-5" />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-2">Key Insight</h3>
        <p className="text-gray-700 leading-relaxed">{insight}</p>
      </div>
    </div>
  </div>
);

// Task Card Component
const TaskCard = ({ taskId, title, description, status, summary, keyInsight, strategicImplication }) => (
  <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
    {/* Task Header */}
    <div className="px-6 py-4 border-b border-gray-100">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="flex items-center justify-center w-8 h-8 bg-gray-100 rounded-lg text-sm font-semibold text-gray-600">
            {taskId}
          </span>
          <div>
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-gray-500">{description}</p>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>
    </div>
    
    {/* Task Content */}
    <div className="px-6 py-5 space-y-5">
      {/* Summary */}
      {summary && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Summary</h4>
          <p className="text-gray-700 leading-relaxed">{summary}</p>
        </div>
      )}
      
      {/* Key Insight Box */}
      {keyInsight && (
        <div className="bg-amber-50 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="text-amber-500 mt-0.5">
              <Lightbulb className="w-4 h-4" />
            </div>
            <p className="text-gray-700 text-sm leading-relaxed">{keyInsight}</p>
          </div>
        </div>
      )}
      
      {/* Strategic Implication */}
      {strategicImplication && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Strategic Implication</h4>
          <p className="text-gray-700 leading-relaxed">{strategicImplication}</p>
        </div>
      )}
    </div>
  </div>
);

// Competitive Comparison Table
const CompetitiveComparisonTable = ({ rows, entityA, entityB }) => (
  <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
    <div className="px-6 py-4 border-b border-gray-100">
      <h2 className="text-lg font-semibold text-gray-900">Competitive Comparison</h2>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wide">Attribute</th>
            <th className="text-left py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wide">{entityA || 'Notion'}</th>
            <th className="text-left py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wide">{entityB || 'Proposed Startup'}</th>
            <th className="text-left py-3 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wide">Winner</th>
          </tr>
        </thead>
        <tbody>
          {rows?.map((row, idx) => (
            <tr key={idx} className="border-b border-gray-100 last:border-b-0">
              <td className="py-4 px-6 text-gray-900 font-medium">{row.attribute}</td>
              <td className="py-4 px-6 text-gray-600">{row.entity_a}</td>
              <td className="py-4 px-6 text-gray-600">{row.entity_b}</td>
              <td className="py-4 px-6">
                <span className="inline-flex items-center px-3 py-1 bg-gray-800 text-white rounded-full text-xs font-medium">
                  {row.winner}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

// Strategic Recommendation Card
const StrategicRecommendationCard = ({ verdict, argumentsFor, argumentsAgainst, trueCompetitors, criticalRisk }) => (
  <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
    <div className="px-6 py-4 border-b border-gray-100">
      <h2 className="text-lg font-semibold text-gray-900">Strategic Recommendation</h2>
    </div>
    
    <div className="px-6 py-5 space-y-6">
      {/* Verdict Badge */}
      <div className="flex items-center gap-3">
        <span className={`inline-flex items-center px-4 py-1.5 rounded-full text-sm font-semibold ${
          verdict === 'YES' ? 'bg-green-100 text-green-700 border border-green-200' :
          verdict === 'NO' ? 'bg-red-100 text-red-700 border border-red-200' :
          'bg-amber-100 text-amber-700 border border-amber-200'
        }`}>
          {verdict === 'CONDITIONAL' ? 'CONDITIONAL' : verdict}
        </span>
        <span className="text-gray-600">Investment Recommendation</span>
      </div>
      
      {/* Arguments Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Arguments For */}
        {argumentsFor && argumentsFor.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-3">Arguments For</h4>
            <ul className="space-y-2">
              {argumentsFor.map((arg, idx) => (
                <li key={idx} className="flex gap-2 text-gray-700">
                  <span className="text-green-500 font-medium">+</span>
                  <span>{arg}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Arguments Against */}
        {argumentsAgainst && argumentsAgainst.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-3">Arguments Against</h4>
            <ul className="space-y-2">
              {argumentsAgainst.map((arg, idx) => (
                <li key={idx} className="flex gap-2 text-gray-700">
                  <span className="text-red-500 font-medium">–</span>
                  <span>{arg}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      
      {/* True Competitors */}
      {trueCompetitors && trueCompetitors.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">True Competitors</h4>
          <div className="flex flex-wrap gap-2">
            {trueCompetitors.map((comp, idx) => (
              <span key={idx} className="inline-flex items-center px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm border border-gray-200">
                {comp}
              </span>
            ))}
          </div>
        </div>
      )}
      
      {/* Critical Risk */}
      {criticalRisk && (
        <div className="bg-red-50 rounded-xl p-4 border border-red-100">
          <div className="flex items-start gap-3">
            <div className="text-red-500 mt-0.5">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-red-600 mb-1">Critical Risk</h4>
              <p className="text-red-700 text-sm leading-relaxed">{criticalRisk}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  </div>
);

// Task Summary Stats
const TaskSummaryCard = ({ totalTasks, completed, failed, retries }) => (
  <div className="bg-white rounded-2xl border border-gray-200 p-6">
    <h3 className="text-lg font-semibold text-gray-900 mb-6">Task Summary</h3>
    <div className="grid grid-cols-4 gap-4 text-center">
      <div>
        <div className="text-3xl font-bold text-gray-900">{totalTasks}</div>
        <div className="text-sm text-gray-500 mt-1">Total Tasks</div>
      </div>
      <div>
        <div className="text-3xl font-bold text-green-600">{completed}</div>
        <div className="text-sm text-gray-500 mt-1">Completed</div>
      </div>
      <div>
        <div className="text-3xl font-bold text-red-500">{failed}</div>
        <div className="text-sm text-gray-500 mt-1">Failed</div>
      </div>
      <div>
        <div className="text-3xl font-bold text-amber-500">{retries}</div>
        <div className="text-sm text-gray-500 mt-1">Retries</div>
      </div>
    </div>
  </div>
);

// ============================================
// MAIN REPORT VIEW COMPONENT
// ============================================

function ReportView() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const reportRef = useRef(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [approving, setApproving] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const data = await analysisApi.getResult(runId);
        setResult(data);
      } catch (err) {
        // Check if analysis is still in progress (202 status)
        if (err.response?.status === 202) {
          setError('Analysis is still in progress. Please wait for it to complete, then refresh this page.');
        } else {
          setError(err.response?.data?.detail || 'Failed to fetch result');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchResult();
  }, [runId]);

  const handleApprove = async () => {
    setApproving(true);
    try {
      await analysisApi.approveRun(runId, true);
      setResult((prev) => ({ ...prev, status: 'completed' }));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!feedback.trim()) {
      setShowFeedback(true);
      return;
    }
    
    setApproving(true);
    try {
      await analysisApi.approveRun(runId, false, feedback);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject');
    } finally {
      setApproving(false);
    }
  };

  // PDF Export Function
  const handleExportPDF = async () => {
    if (!reportRef.current) return;
    
    setExporting(true);
    try {
      // Dynamic import of html2pdf
      const html2pdf = (await import('html2pdf.js')).default;
      
      const element = reportRef.current;
      const opt = {
        margin: [10, 10, 10, 10],
        filename: `analysis-report-${runId}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { 
          scale: 2, 
          useCORS: true,
          letterRendering: true 
        },
        jsPDF: { 
          unit: 'mm', 
          format: 'a4', 
          orientation: 'portrait' 
        },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
      };
      
      await html2pdf().set(opt).from(element).save();
    } catch (err) {
      console.error('PDF export failed:', err);
      // Fallback to print
      window.print();
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 bg-red-50 border border-red-200 rounded-2xl text-center">
        <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Error</h2>
        <p className="text-red-600">{error}</p>
        <button
          onClick={() => navigate('/')}
          className="mt-4 px-6 py-2 bg-gray-900 hover:bg-gray-800 rounded-lg text-white transition-colors"
        >
          Start New Analysis
        </button>
      </div>
    );
  }

  const report = result?.final_report || {};
  const isPendingReview = result?.status === 'pending_user_review';
  const sections = report.sections || {};
  const finalOutput = report.final_output || {};
  
  // Debug logging
  console.log('[ReportView] Result data:', {
    hasResult: !!result,
    hasFinalReport: !!result?.final_report,
    sectionCount: Object.keys(sections).length,
    taskCount: result?.tasks?.length || 0,
    sections: sections,
    tasks: result?.tasks,
  });
  
  // Extract task data for display
  // If sections is empty, build it from result.tasks
  let taskEntries = Object.entries(sections);
  
  if (taskEntries.length === 0 && result?.tasks) {
    console.log('[ReportView] No sections found, building from tasks array');
    // Build sections from tasks array as fallback
    const builtSections = {};
    result.tasks.forEach(task => {
      builtSections[task.id] = {
        task: task.task_description,
        status: task.status,
        output: task.output || {},
      };
    });
    taskEntries = Object.entries(builtSections);
  }
  
  const totalTasks = result?.tasks?.length || taskEntries.length;
  const completedTasks = result?.tasks?.filter(t => t.status === 'completed').length || 
    taskEntries.filter(([, s]) => s.status === 'completed').length;
  const failedTasks = result?.tasks?.filter(t => t.status === 'failed').length ||
    taskEntries.filter(([, s]) => s.status === 'failed').length;
  const totalRetries = result?.tasks?.reduce((sum, t) => sum + (t.retries || 0), 0) || 0;

  // Format timestamp
  const timestamp = report.generated_at 
    ? new Date(report.generated_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      })
    : 'N/A';

  // Get executive summary from multiple fallback sources
  const executiveSummary = 
    finalOutput.summary ||  // Primary: from final_output
    report.executive_summary ||  // Secondary: from top-level report
    (taskEntries[0] && taskEntries[0][1]?.output?.summary) ||  // Tertiary: from first task
    'Analysis summary not available.';

  // Get main key insight
  const mainKeyInsight = finalOutput.key_insight ||
    (taskEntries[0] && taskEntries[0][1]?.output?.key_insight) ||
    '';

  return (
    <>
      {/* Print styles */}
      <style>{`
        @media print {
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .no-print { display: none !important; }
        }
      `}</style>
      
      <div ref={reportRef} className="max-w-4xl mx-auto py-8 px-4 space-y-6">
        
        {/* HEADER SECTION */}
        <div className="pb-6 border-b border-gray-200">
          <div className="flex items-start justify-between">
            {/* Left: Title, Subtitle, Timestamp */}
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl font-bold text-gray-900">Analysis Report</h1>
                {isPendingReview && <PendingReviewBadge />}
                {result?.status === 'completed' && (
                  <span className="inline-flex items-center px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium border border-green-200">
                    Approved
                  </span>
                )}
              </div>
              <p className="text-gray-600 text-lg mb-2">{result?.goal || 'Analyze Swiggy'}</p>
              <div className="flex items-center gap-2 text-gray-500 text-sm">
                <Clock className="w-4 h-4" />
                <span>{timestamp}</span>
              </div>
            </div>
            
            {/* Right: Action Buttons */}
            <div className="flex gap-2 no-print">
              {isPendingReview && (
                <>
                  <button
                    onClick={handleApprove}
                    disabled={approving}
                    className="px-5 py-2 bg-gray-900 hover:bg-gray-800 disabled:bg-gray-400 rounded-lg text-white text-sm font-medium transition-colors"
                  >
                    {approving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Approve'}
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={approving}
                    className="px-5 py-2 bg-white hover:bg-gray-50 border border-gray-300 rounded-lg text-gray-700 text-sm font-medium transition-colors"
                  >
                    Reject
                  </button>
                </>
              )}
              <button
                onClick={handleExportPDF}
                disabled={exporting}
                className="px-5 py-2 bg-white hover:bg-gray-50 border border-gray-300 rounded-lg text-gray-700 text-sm font-medium transition-colors flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                {exporting ? 'Exporting...' : 'Export'}
              </button>
            </div>
          </div>
          
          {/* Feedback textarea for rejection */}
          {showFeedback && isPendingReview && (
            <div className="mt-4 no-print">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Please provide feedback for rejection..."
                className="w-full p-3 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-400"
                rows={3}
              />
            </div>
          )}
        </div>

        {/* EXECUTIVE SUMMARY */}
        <ExecutiveSummaryCard summary={executiveSummary} />

        {/* MAIN KEY INSIGHT */}
        {mainKeyInsight && <KeyInsightCard insight={mainKeyInsight} />}

        {/* TASK ANALYSIS SECTION */}
        <div className="space-y-4">
          <h2 className="text-xl font-bold text-gray-900">Task Analysis</h2>
          
          {taskEntries.length === 0 && (
            <p className="text-gray-500 text-sm">No task data available</p>
          )}
          
          {taskEntries.map(([taskId, section]) => (
            <TaskCard
              key={taskId}
              taskId={taskId}
              title={section.task || 'Task'}
              description={''} 
              status={section.status}
              summary={section.output?.summary}
              keyInsight={section.output?.key_insight}
              strategicImplication={section.output?.strategic_implication}
            />
          ))}
        </div>

        {/* COMPETITIVE COMPARISON TABLE */}
        {finalOutput.table?.rows && finalOutput.table.rows.length > 0 && (
          <CompetitiveComparisonTable
            rows={finalOutput.table.rows}
            entityA={finalOutput.entities?.entity_a}
            entityB={finalOutput.entities?.entity_b}
          />
        )}

        {/* STRATEGIC RECOMMENDATION */}
        {finalOutput.final_verdict && (
          <StrategicRecommendationCard
            verdict={finalOutput.final_verdict.verdict}
            argumentsFor={finalOutput.final_verdict.arguments_for}
            argumentsAgainst={finalOutput.final_verdict.arguments_against}
            trueCompetitors={finalOutput.true_competitors}
            criticalRisk={finalOutput.critical_risk}
          />
        )}

        {/* TASK SUMMARY */}
        <TaskSummaryCard
          totalTasks={totalTasks}
          completed={completedTasks}
          failed={failedTasks}
          retries={totalRetries}
        />

        {/* START NEW ANALYSIS BUTTON */}
        <div className="flex justify-center pt-4 no-print">
          <button
            onClick={() => navigate('/')}
            className="px-8 py-3 bg-gray-900 hover:bg-gray-800 rounded-lg text-white font-medium transition-colors"
          >
            Start New Analysis
          </button>
        </div>
      </div>
    </>
  );
}

export default ReportView;
