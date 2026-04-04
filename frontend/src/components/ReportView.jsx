import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FileText, 
  CheckCircle, 
  XCircle, 
  Loader2, 
  Download,
  Edit3,
  ThumbsUp,
  ThumbsDown,
  ExternalLink,
  DollarSign,
  Clock
} from 'lucide-react';
import { analysisApi } from '../services/api';

function ReportView() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [approving, setApproving] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const data = await analysisApi.getResult(runId);
        setResult(data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to fetch result');
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

  const handleDownload = () => {
    const dataStr = JSON.stringify(result.final_report, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `analysis-${runId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 bg-red-900/30 border border-red-700 rounded-xl text-center">
        <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-white mb-2">Error</h2>
        <p className="text-red-200">{error}</p>
        <button
          onClick={() => navigate('/')}
          className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white"
        >
          Start New Analysis
        </button>
      </div>
    );
  }

  const report = result?.final_report || {};
  const isPendingReview = result?.status === 'pending_user_review';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <FileText className="w-8 h-8 text-blue-400" />
            <h1 className="text-2xl font-bold text-white">Analysis Report</h1>
            {result?.status === 'completed' && (
              <span className="px-3 py-1 bg-green-900 text-green-200 rounded-full text-sm">
                Approved
              </span>
            )}
            {isPendingReview && (
              <span className="px-3 py-1 bg-purple-900 text-purple-200 rounded-full text-sm">
                Pending Review
              </span>
            )}
          </div>
          <p className="text-slate-400">{result?.goal}</p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleDownload}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export JSON
          </button>
        </div>
      </div>

      {/* HITL Controls */}
      {isPendingReview && (
        <div className="p-6 bg-purple-900/30 border border-purple-700 rounded-xl">
          <h3 className="text-lg font-semibold text-white mb-4">Review Required</h3>
          <p className="text-slate-300 mb-4">
            Please review the analysis below and approve or reject it.
          </p>

          {showFeedback && (
            <div className="mb-4">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Please provide feedback for rejection..."
                className="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                rows={3}
              />
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleApprove}
              disabled={approving}
              className="px-6 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 rounded-lg text-white flex items-center gap-2"
            >
              {approving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ThumbsUp className="w-4 h-4" />
              )}
              Approve
            </button>
            <button
              onClick={handleReject}
              disabled={approving}
              className="px-6 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 rounded-lg text-white flex items-center gap-2"
            >
              <ThumbsDown className="w-4 h-4" />
              Reject
            </button>
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-slate-800 rounded-xl border border-slate-700">
          <div className="flex items-center gap-2 text-slate-400 mb-1">
            <Clock className="w-4 h-4" />
            <span className="text-sm">Generated</span>
          </div>
          <p className="text-white">
            {report.generated_at 
              ? new Date(report.generated_at).toLocaleString()
              : 'N/A'
            }
          </p>
        </div>
        <div className="p-4 bg-slate-800 rounded-xl border border-slate-700">
          <div className="flex items-center gap-2 text-slate-400 mb-1">
            <FileText className="w-4 h-4" />
            <span className="text-sm">Analysis Type</span>
          </div>
          <p className="text-white capitalize">
            {report.goal_type?.replace(/_/g, ' ') || report.summary_type || 'N/A'}
          </p>
        </div>
        <div className="p-4 bg-slate-800 rounded-xl border border-slate-700">
          <div className="flex items-center gap-2 text-slate-400 mb-1">
            <DollarSign className="w-4 h-4" />
            <span className="text-sm">Total Cost</span>
          </div>
          <p className="text-white">
            ${result?.total_cost?.estimated_cost_usd?.toFixed(4) || '0.0000'}
          </p>
        </div>
      </div>

      {/* Report Sections */}
      <div className="space-y-6">
        {Object.entries(report.sections || {}).map(([taskId, section]) => (
          <div 
            key={taskId}
            className="p-6 bg-slate-800 rounded-xl border border-slate-700"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <span className="px-2 py-1 bg-blue-900 rounded text-sm text-blue-200">
                  {taskId}
                </span>
                {section.task}
              </h3>
              {section.status === 'completed' && (
                <CheckCircle className="w-5 h-5 text-green-400" />
              )}
            </div>

            {/* Output content */}
            {section.output && (
              <div className="space-y-4">
                {/* Summary */}
                {section.output.summary && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">Summary</h4>
                    <p className="text-slate-200">{section.output.summary}</p>
                  </div>
                )}

                {/* Key Insight (V6) */}
                {section.output.key_insight && (
                  <div className="p-4 bg-blue-900/30 border border-blue-700 rounded-lg">
                    <h4 className="text-sm font-medium text-blue-300 mb-2">💡 Key Insight</h4>
                    <p className="text-white font-medium">{section.output.key_insight}</p>
                  </div>
                )}

                {/* V18: Per-Task Comparison Block (object format) - Only show if not empty */}
                {section.output.comparison && 
                 typeof section.output.comparison === 'object' && 
                 !Array.isArray(section.output.comparison) &&
                 (section.output.comparison.features || section.output.comparison.pricing || section.output.comparison.target_users) && (
                  <div className="p-4 bg-slate-700/50 rounded-lg border border-slate-600">
                    <h4 className="text-sm font-medium text-slate-300 mb-3">⚖️ Comparison</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      {/* Features */}
                      {section.output.comparison.features && (
                        <div>
                          <h5 className="text-xs text-slate-400 mb-1">Features</h5>
                          {Object.entries(section.output.comparison.features).map(([key, val]) => (
                            <div key={key} className="text-slate-200">
                              <span className="text-slate-400">{key}:</span> {val}
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Pricing */}
                      {section.output.comparison.pricing && (
                        <div>
                          <h5 className="text-xs text-slate-400 mb-1">Pricing</h5>
                          {Object.entries(section.output.comparison.pricing).map(([key, val]) => (
                            <div key={key} className="text-slate-200">
                              <span className="text-slate-400">{key}:</span> {val}
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Target Users */}
                      {section.output.comparison.target_users && (
                        <div>
                          <h5 className="text-xs text-slate-400 mb-1">Target Users</h5>
                          {Object.entries(section.output.comparison.target_users).map(([key, val]) => (
                            <div key={key} className="text-slate-200">
                              <span className="text-slate-400">{key}:</span> {val}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    {/* Winner */}
                    {section.output.comparison.winner && (
                      <div className="mt-3 pt-3 border-t border-slate-600">
                        <span className="px-2 py-1 bg-green-900 text-green-200 rounded text-xs font-medium">
                          Winner: {section.output.comparison.winner}
                        </span>
                        {section.output.comparison.why && (
                          <span className="ml-2 text-slate-300 text-sm">{section.output.comparison.why}</span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* V21: Per-Task Comparison List (NEW - array format) */}
                {section.output.comparison && Array.isArray(section.output.comparison) && section.output.comparison.length > 0 && (
                  <div className="p-5 bg-gradient-to-br from-indigo-900/40 to-purple-900/30 rounded-xl border border-indigo-600/50 shadow-lg">
                    <h4 className="text-base font-semibold text-indigo-200 mb-4 flex items-center gap-2">
                      <span className="text-xl">⚖️</span> Task Comparison
                    </h4>
                    <div className="space-y-4">
                      {section.output.comparison.map((dim, idx) => (
                        <div key={idx} className="p-4 bg-slate-800/70 rounded-lg border border-slate-600/50 hover:border-indigo-500/50 transition-colors">
                          <div className="flex justify-between items-start mb-3">
                            <span className="text-slate-100 font-semibold text-sm uppercase tracking-wide">{dim.dimension}</span>
                            {dim.winner && (
                              <span className="px-3 py-1.5 bg-gradient-to-r from-green-800 to-emerald-800 text-green-100 rounded-full text-xs font-bold shadow-md">
                                ✓ Winner: {dim.winner}
                              </span>
                            )}
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                            <div className="p-3 bg-blue-900/20 rounded-md border border-blue-800/30">
                              <span className="text-blue-300 text-xs font-medium uppercase block mb-1">Entity A:</span>
                              <p className="text-slate-100 text-sm leading-relaxed">{dim.entity_a || dim.entity_A}</p>
                            </div>
                            <div className="p-3 bg-purple-900/20 rounded-md border border-purple-800/30">
                              <span className="text-purple-300 text-xs font-medium uppercase block mb-1">Entity B:</span>
                              <p className="text-slate-100 text-sm leading-relaxed">{dim.entity_b || dim.entity_B}</p>
                            </div>
                          </div>
                          {dim.key_difference && (
                            <div className="p-2 bg-slate-700/50 rounded-md mb-2">
                              <p className="text-slate-300 text-xs">
                                <span className="text-slate-400 font-medium">Key Difference:</span> {dim.key_difference}
                              </p>
                            </div>
                          )}
                          {dim.why_it_matters && (
                            <div className="p-2 bg-indigo-900/30 rounded-md border-l-2 border-indigo-500">
                              <p className="text-indigo-200 text-xs">
                                <span className="text-indigo-300 font-medium">💡 Why it matters:</span> {dim.why_it_matters}
                              </p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* V21: Task Focus Info */}
                {section.output.task_focus && (
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="px-2 py-1 bg-slate-700 rounded">{section.output.task_focus}</span>
                    {section.output.task_question && (
                      <span className="italic">{section.output.task_question}</span>
                    )}
                  </div>
                )}

                {/* V14: Comparison Table - Show for ALL tasks now (V21) */}
                {section.output.comparison_table?.rows && section.output.comparison_table.rows.length > 0 && (
                  <div className="p-4 bg-slate-800/50 rounded-xl border border-slate-600/50">
                    <h4 className="text-base font-semibold text-slate-300 mb-3 flex items-center gap-2">
                      <span className="text-lg">⚖️</span> Comparison Analysis
                    </h4>
                    <div className="overflow-x-auto rounded-lg border border-slate-700">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-700/50">
                          <tr className="border-b border-slate-600">
                            <th className="text-left py-3 px-4 text-slate-300 font-semibold">Attribute</th>
                            <th className="text-left py-3 px-4 text-blue-300 font-semibold">
                              {section.output.comparison_table.rows[0]?.entity_a || 'Entity A'}
                            </th>
                            <th className="text-left py-3 px-4 text-purple-300 font-semibold">
                              {section.output.comparison_table.rows[0]?.entity_b || 'Entity B'}
                            </th>
                            <th className="text-left py-3 px-4 text-slate-300 font-semibold">Winner</th>
                          </tr>
                        </thead>
                        <tbody className="bg-slate-800/30">
                          {section.output.comparison_table.rows.map((row, idx) => (
                            <tr key={idx} className="border-b border-slate-700 hover:bg-slate-700/30 transition-colors">
                              <td className="py-3 px-4 text-slate-200 font-medium">{row.attribute}</td>
                              <td className="py-3 px-4 text-slate-100">{row.entity_a}</td>
                              <td className="py-3 px-4 text-slate-100">{row.entity_b}</td>
                              <td className="py-3 px-4">
                                <div className="flex flex-col gap-1">
                                  <span className={`inline-block px-3 py-1.5 rounded-md text-xs font-bold ${
                                    row.winner === row.entity_a ? 'bg-gradient-to-r from-green-800 to-emerald-800 text-green-100' :
                                    row.winner === row.entity_b ? 'bg-gradient-to-r from-purple-800 to-violet-800 text-purple-100' :
                                    'bg-slate-600 text-slate-200'
                                  }`}>
                                    {row.winner}
                                  </span>
                                  {row.explanation && (
                                    <span className="text-slate-400 text-xs italic">{row.explanation}</span>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* V14: Final Verdict - Only show for final task (is_final_task flag) */}
                {section.output.is_final_task && section.output.final_verdict?.verdict && (
                  <div className={`p-4 rounded-lg border ${
                    section.output.final_verdict.verdict === 'YES' ? 'bg-green-900/30 border-green-700' :
                    section.output.final_verdict.verdict === 'NO' ? 'bg-red-900/30 border-red-700' :
                    'bg-yellow-900/30 border-yellow-700'
                  }`}>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">🎯 Final Verdict</h4>
                    <div className="flex items-center gap-3 mb-3">
                      <span className={`px-4 py-2 rounded-lg text-lg font-bold ${
                        section.output.final_verdict.verdict === 'YES' ? 'bg-green-600 text-white' :
                        section.output.final_verdict.verdict === 'NO' ? 'bg-red-600 text-white' :
                        'bg-yellow-600 text-white'
                      }`}>
                        {section.output.final_verdict.verdict}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {section.output.final_verdict.arguments_for?.length > 0 && (
                        <div>
                          <h5 className="text-xs text-green-300 mb-1">Arguments For</h5>
                          <ul className="space-y-1">
                            {section.output.final_verdict.arguments_for.map((arg, idx) => (
                              <li key={idx} className="text-slate-200 text-sm flex gap-2">
                                <span className="text-green-400">+</span>
                                {arg}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {section.output.final_verdict.arguments_against?.length > 0 && (
                        <div>
                          <h5 className="text-xs text-red-300 mb-1">Arguments Against</h5>
                          <ul className="space-y-1">
                            {section.output.final_verdict.arguments_against.map((arg, idx) => (
                              <li key={idx} className="text-slate-200 text-sm flex gap-2">
                                <span className="text-red-400">-</span>
                                {arg}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {section.output.final_verdict.conditions_for_success?.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-600">
                        <h5 className="text-xs text-yellow-300 mb-1">Conditions for Success</h5>
                        <ul className="space-y-1">
                          {section.output.final_verdict.conditions_for_success.map((cond, idx) => (
                            <li key={idx} className="text-slate-200 text-sm flex gap-2">
                              <span className="text-yellow-400">→</span>
                              {cond}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Strategic Implication (V6) */}
                {section.output.strategic_implication && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">📈 Strategic Implication</h4>
                    <p className="text-slate-200">{section.output.strategic_implication}</p>
                  </div>
                )}

                {/* Biggest Risk (V6) */}
                {section.output.biggest_risk && (
                  <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg">
                    <h4 className="text-sm font-medium text-red-300 mb-1">⚠️ Biggest Risk</h4>
                    <p className="text-slate-200">{section.output.biggest_risk}</p>
                  </div>
                )}

                {/* Competitors Identified (V6) */}
                {section.output.competitors_identified && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">🏢 Competitors</h4>
                    <div className="flex flex-wrap gap-2">
                      {section.output.competitors_identified.direct?.map((comp, idx) => (
                        <span key={`d-${idx}`} className="px-2 py-1 bg-blue-900 text-blue-200 rounded text-sm">
                          {comp}
                        </span>
                      ))}
                      {section.output.competitors_identified.indirect?.map((comp, idx) => (
                        <span key={`i-${idx}`} className="px-2 py-1 bg-slate-600 text-slate-200 rounded text-sm">
                          {comp} (indirect)
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Facts (V6) */}
                {section.output.facts && section.output.facts.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">📋 Key Facts</h4>
                    <ul className="space-y-1">
                      {section.output.facts.map((fact, idx) => (
                        <li key={idx} className="text-slate-200 flex gap-2">
                          <span className="text-blue-400">•</span>
                          {fact}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Legacy: Findings (backward compatibility) */}
                {section.output.findings && !section.output.facts && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">Key Findings</h4>
                    <div className="space-y-2">
                      {Object.entries(section.output.findings).map(([key, value]) => (
                        <div key={key} className="flex gap-2">
                          <span className="text-blue-400">•</span>
                          <div>
                            <span className="text-slate-300 font-medium capitalize">
                              {key.replace(/_/g, ' ')}:
                            </span>{' '}
                            <span className="text-slate-200">{value}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Legacy: Data Points (backward compatibility) */}
                {section.output.data_points && section.output.data_points.length > 0 && !section.output.facts && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">Data Points</h4>
                    <ul className="space-y-1">
                      {section.output.data_points.map((point, idx) => (
                        <li key={idx} className="text-slate-200 flex gap-2">
                          <span className="text-green-400">✓</span>
                          {point}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Limitations */}
                {section.output.limitations && section.output.limitations.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">Limitations</h4>
                    <ul className="space-y-1">
                      {section.output.limitations.map((limitation, idx) => (
                        <li key={idx} className="text-yellow-300 text-sm flex gap-2">
                          <span>⚠</span>
                          {limitation}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Confidence with V6 breakdown */}
                {section.output.confidence !== undefined && (
                  <div className="mt-4 pt-4 border-t border-slate-700">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-slate-400">Confidence:</span>
                      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden max-w-xs">
                        <div 
                          className={`h-full ${
                            section.output.confidence >= 0.7 ? 'bg-green-500' :
                            section.output.confidence >= 0.55 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${section.output.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-sm text-slate-300">
                        {(section.output.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    
                    {/* V21: Validation Metrics Display (Updated with new metrics) */}
                    {section.output.validation_metrics && (
                      <div className="mt-3 p-3 bg-slate-700/50 rounded-lg">
                        <h5 className="text-xs text-slate-400 mb-2">V21 Quality Metrics</h5>
                        <div className="grid grid-cols-4 md:grid-cols-7 gap-2 text-xs">
                          {['data_quality', 'completeness', 'comparison_depth', 'specificity', 'domain_correctness', 'insight_depth', 'per_task_comparison'].map((metric) => (
                            section.output.validation_metrics[metric] !== undefined && (
                              <div key={metric} className="text-center">
                                <div className={`text-lg font-bold ${
                                  section.output.validation_metrics[metric] >= 0.7 ? 'text-green-400' :
                                  section.output.validation_metrics[metric] >= 0.5 ? 'text-yellow-400' : 'text-red-400'
                                }`}>
                                  {((section.output.validation_metrics[metric] || 0) * 100).toFixed(0)}%
                                </div>
                                <div className="text-slate-500 capitalize text-[10px]">{metric.replace(/_/g, ' ')}</div>
                              </div>
                            )
                          ))}
                        </div>
                        {/* V21: Originality indicator */}
                        {section.output.validation_metrics.originality !== undefined && (
                          <div className="mt-2 flex items-center gap-2">
                            <span className="text-xs text-slate-400">Originality:</span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              section.output.validation_metrics.originality >= 0.7 ? 'bg-green-900 text-green-200' :
                              section.output.validation_metrics.originality >= 0.5 ? 'bg-yellow-900 text-yellow-200' :
                              'bg-red-900 text-red-200'
                            }`}>
                              {((section.output.validation_metrics.originality || 0) * 100).toFixed(0)}%
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* V18: Rejection Reason (if task was rejected) */}
                    {section.output.rejection_reason && (
                      <div className="mt-3 p-3 bg-red-900/30 border border-red-700 rounded-lg">
                        <h5 className="text-xs text-red-300 mb-1">⚠️ Validation Issue</h5>
                        <p className="text-red-200 text-sm">{section.output.rejection_reason}</p>
                      </div>
                    )}
                    
                    {/* V6 Confidence Breakdown (legacy) */}
                    {section.output.confidence_breakdown && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span className={`px-2 py-1 rounded text-xs ${
                          section.output.confidence_breakdown.comparison_present ? 'bg-green-900 text-green-200' : 'bg-slate-600 text-slate-300'
                        }`}>
                          Comparison: {section.output.confidence_breakdown.comparison_present ? '✓' : '✗'}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs ${
                          section.output.confidence_breakdown.winners_present ? 'bg-green-900 text-green-200' : 'bg-slate-600 text-slate-300'
                        }`}>
                          Winners: {section.output.confidence_breakdown.winners_present ? '✓' : '✗'}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs ${
                          section.output.confidence_breakdown.insight_quality === 'high' ? 'bg-green-900 text-green-200' :
                          section.output.confidence_breakdown.insight_quality === 'medium' ? 'bg-yellow-900 text-yellow-200' :
                          'bg-slate-600 text-slate-300'
                        }`}>
                          Insight: {section.output.confidence_breakdown.insight_quality || 'N/A'}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs ${
                          section.output.confidence_breakdown.decision_clarity === 'high' ? 'bg-green-900 text-green-200' :
                          section.output.confidence_breakdown.decision_clarity === 'medium' ? 'bg-yellow-900 text-yellow-200' :
                          'bg-slate-600 text-slate-300'
                        }`}>
                          Decision: {section.output.confidence_breakdown.decision_clarity || 'N/A'}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* V15: FINAL ANALYSIS SECTION (Global Table + Verdict) */}
      {report.final_output && (report.final_output.table?.rows?.length > 0 || report.final_output.final_verdict?.verdict) && (
        <div className="p-6 bg-gradient-to-r from-slate-800 to-slate-900 rounded-xl border-2 border-blue-600">
          <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            🎯 Final Analysis
            <span className="text-sm font-normal text-slate-400">
              ({report.final_output.entities?.entity_a} vs {report.final_output.entities?.entity_b})
            </span>
          </h3>

          {/* Global Comparison Table */}
          {report.final_output.table?.rows && report.final_output.table.rows.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-slate-400 mb-3">⚖️ Competitive Comparison</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-600 bg-slate-700/50">
                      <th className="text-left py-3 px-4 text-slate-300">Attribute</th>
                      <th className="text-left py-3 px-4 text-slate-300">
                        {report.final_output.entities?.entity_a || 'Entity A'}
                      </th>
                      <th className="text-left py-3 px-4 text-slate-300">
                        {report.final_output.entities?.entity_b || 'Entity B'}
                      </th>
                      <th className="text-left py-3 px-4 text-slate-300">Winner</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.final_output.table.rows.map((row, idx) => (
                      <tr key={idx} className="border-b border-slate-700 hover:bg-slate-700/30">
                        <td className="py-3 px-4 text-slate-300 font-medium">{row.attribute}</td>
                        <td className="py-3 px-4 text-slate-200">{row.entity_a}</td>
                        <td className="py-3 px-4 text-slate-200">{row.entity_b}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            row.winner === report.final_output.entities?.entity_a ? 'bg-blue-900 text-blue-200' :
                            row.winner === report.final_output.entities?.entity_b ? 'bg-green-900 text-green-200' :
                            'bg-slate-600 text-slate-200'
                          }`}>
                            {row.winner}
                          </span>
                          {row.explanation && (
                            <span className="ml-2 text-slate-400 text-xs">{row.explanation}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Key Insight */}
          {report.final_output.key_insight && (
            <div className="mb-6 p-4 bg-blue-900/30 border border-blue-700 rounded-lg">
              <h4 className="text-sm font-medium text-blue-300 mb-2">💡 Key Insight</h4>
              <p className="text-white font-medium">{report.final_output.key_insight}</p>
            </div>
          )}

          {/* Final Verdict */}
          {report.final_output.final_verdict?.verdict && (
            <div className={`p-4 rounded-lg border-2 ${
              report.final_output.final_verdict.verdict === 'YES' ? 'bg-green-900/30 border-green-600' :
              report.final_output.final_verdict.verdict === 'NO' ? 'bg-red-900/30 border-red-600' :
              'bg-yellow-900/30 border-yellow-600'
            }`}>
              <div className="flex items-center gap-4 mb-4">
                <span className={`px-6 py-3 rounded-lg text-2xl font-bold ${
                  report.final_output.final_verdict.verdict === 'YES' ? 'bg-green-600 text-white' :
                  report.final_output.final_verdict.verdict === 'NO' ? 'bg-red-600 text-white' :
                  'bg-yellow-600 text-white'
                }`}>
                  {report.final_output.final_verdict.verdict}
                </span>
                <span className="text-slate-300 text-sm">Investment Recommendation</span>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {report.final_output.final_verdict.arguments_for?.length > 0 && (
                  <div>
                    <h5 className="text-xs text-green-300 mb-2 font-medium">✓ Arguments For</h5>
                    <ul className="space-y-1">
                      {report.final_output.final_verdict.arguments_for.map((arg, idx) => (
                        <li key={idx} className="text-slate-200 text-sm flex gap-2">
                          <span className="text-green-400">+</span>
                          {arg}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.final_output.final_verdict.arguments_against?.length > 0 && (
                  <div>
                    <h5 className="text-xs text-red-300 mb-2 font-medium">✗ Arguments Against</h5>
                    <ul className="space-y-1">
                      {report.final_output.final_verdict.arguments_against.map((arg, idx) => (
                        <li key={idx} className="text-slate-200 text-sm flex gap-2">
                          <span className="text-red-400">-</span>
                          {arg}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {report.final_output.final_verdict.conditions_for_success?.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-600">
                  <h5 className="text-xs text-yellow-300 mb-2 font-medium">→ Conditions for Success</h5>
                  <ul className="space-y-1">
                    {report.final_output.final_verdict.conditions_for_success.map((cond, idx) => (
                      <li key={idx} className="text-slate-200 text-sm flex gap-2">
                        <span className="text-yellow-400">→</span>
                        {cond}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* V17: True Competitors from Synthesis */}
          {report.final_output.true_competitors?.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-slate-400 mb-2">🏢 True Competitors (Validated)</h4>
              <div className="flex flex-wrap gap-2">
                {report.final_output.true_competitors.map((comp, idx) => (
                  <span key={idx} className="px-3 py-1 bg-blue-900 text-blue-200 rounded text-sm font-medium">
                    {comp}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* V17: Critical Risk from Synthesis */}
          {report.final_output.critical_risk && (
            <div className="mt-4 p-3 bg-red-900/30 border border-red-700 rounded-lg">
              <h4 className="text-sm font-medium text-red-300 mb-1">⚠️ Critical Risk</h4>
              <p className="text-slate-200">{report.final_output.critical_risk}</p>
            </div>
          )}
        </div>
      )}

      {/* Task Summary */}
      {result?.tasks && result.tasks.length > 0 && (
        <div className="p-6 bg-slate-800 rounded-xl border border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-4">Task Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-white">
                {result.tasks.length}
              </div>
              <div className="text-sm text-slate-400">Total Tasks</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-400">
                {result.tasks.filter(t => t.status === 'completed').length}
              </div>
              <div className="text-sm text-slate-400">Completed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-400">
                {result.tasks.filter(t => t.status === 'failed').length}
              </div>
              <div className="text-sm text-slate-400">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-400">
                {result.tasks.reduce((sum, t) => sum + (t.retries || 0), 0)}
              </div>
              <div className="text-sm text-slate-400">Total Retries</div>
            </div>
          </div>
        </div>
      )}

      {/* Back button */}
      <div className="flex justify-center pt-4">
        <button
          onClick={() => navigate('/')}
          className="px-6 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white"
        >
          Start New Analysis
        </button>
      </div>
    </div>
  );
}

export default ReportView;
