import React, { useState, useEffect, useRef } from 'react';
import { ArrowUp, FileText, Loader2 } from 'lucide-react';
import { analysisApi } from '../services/api';

const placeholders = [
  "Analyze AI fitness apps for students",
  "Compare Swiggy vs Zomato",
  "Should I enter the EV charging market?",
  "Analyze fintech startups in India",
  "Compare Slack vs Microsoft Teams",
];

const exampleQueries = [
  "Analyze AI fitness apps for students",
  "Compare Swiggy vs Zomato",
  "Should I enter the EV charging market?",
];

function LandingPage({ onAnalysisStarted }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [isPlaceholderVisible, setIsPlaceholderVisible] = useState(true);
  const textareaRef = useRef(null);

  // Rotating placeholder effect - every 2 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setIsPlaceholderVisible(false);
      setTimeout(() => {
        setPlaceholderIndex((prev) => (prev + 1) % placeholders.length);
        setIsPlaceholderVisible(true);
      }, 200);
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [query]);

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setError(null);

    try {
      const response = await analysisApi.startAnalysis(query.trim());
      onAnalysisStarted(response.run_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start analysis');
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleExampleClick = (example) => {
    setQuery(example);
    textareaRef.current?.focus();
  };

  return (
    <div className="min-h-screen bg-[#F7F5F2] relative overflow-hidden">
      {/* Subtle Grid Background */}
      <div 
        className="absolute inset-0 opacity-[0.4]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />

      {/* Floating Card - Left */}
      <div className="hidden lg:block absolute left-8 xl:left-16 top-1/2 -translate-y-1/2 w-64 opacity-60 pointer-events-none">
        <div className="bg-white rounded-2xl shadow-lg p-5 border border-[#EAE7E3] transform -rotate-3">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-[#6B6B6B]" />
              <span className="text-sm font-medium text-[#1F1F1F]">Market research report</span>
            </div>
            <svg className="w-4 h-4 text-[#6B6B6B]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M7 17L17 7M17 7H7M17 7V17" />
            </svg>
          </div>
          <div className="space-y-2 mb-4">
            <p className="text-xs text-[#6B6B6B] leading-relaxed">
              3 underserved neighborhoods for specialty coffee in Austin
            </p>
          </div>
          <div className="space-y-2 mb-4">
            <div className="h-2 bg-[#E6C7A9] rounded-full w-3/4"></div>
            <div className="h-2 bg-[#EAE7E3] rounded-full w-1/2 relative">
              <span className="absolute -right-8 -top-1 bg-[#E6C7A9] text-white text-[10px] px-2 py-0.5 rounded-full font-medium">
                AI
              </span>
            </div>
          </div>
          <div className="text-xs text-[#6B6B6B]">236 sources</div>
        </div>
      </div>

      {/* Floating Card - Right Top */}
      <div className="hidden lg:block absolute right-8 xl:right-16 top-1/3 -translate-y-1/2 w-56 opacity-60 pointer-events-none">
        <div className="bg-white rounded-2xl shadow-lg p-5 border border-[#EAE7E3] transform rotate-2">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#EAE7E3] flex items-center justify-center">
                <span className="text-[8px]">🌐</span>
              </div>
              <span className="text-sm font-medium text-[#1F1F1F]">Austin Bean Co.</span>
            </div>
            <svg className="w-4 h-4 text-[#6B6B6B]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M7 17L17 7M17 7H7M17 7V17" />
            </svg>
          </div>
          <div className="flex gap-3">
            <div className="flex-1 space-y-2">
              <div className="h-2 bg-[#EAE7E3] rounded w-full"></div>
              <div className="h-2 bg-[#EAE7E3] rounded w-4/5"></div>
              <div className="h-2 bg-[#E6C7A9] rounded w-3/5"></div>
            </div>
            <div className="w-16 h-16 bg-[#E6C7A9]/30 rounded-lg"></div>
          </div>
          <div className="flex items-center gap-1.5 mt-4">
            <div className="w-2 h-2 bg-green-400 rounded-full"></div>
            <span className="text-xs text-[#6B6B6B]">Published</span>
          </div>
        </div>
      </div>

      {/* Floating Card - Right Bottom (Key Insight) */}
      <div className="hidden lg:block absolute right-12 xl:right-24 bottom-1/4 w-48 opacity-70 pointer-events-none">
        <div className="bg-[#FEF9C3] rounded-xl shadow-md p-4 transform rotate-1">
          <p className="text-xs">
            <span className="font-semibold text-[#1F1F1F]">Key insight:</span>
            <span className="text-[#6B6B6B]"> No direct competitor in the local market</span>
          </p>
          <div className="absolute -bottom-3 right-4">
            <svg className="w-4 h-4 text-[#FEF9C3]" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 21l-8-8h16l-8 8z" />
            </svg>
          </div>
        </div>
        <div className="flex justify-end mt-2 mr-2">
          <div className="bg-[#1F1F1F] text-white text-[10px] px-3 py-1 rounded-full">You</div>
        </div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex flex-col items-center justify-center px-4 py-16">
        <div className="w-full max-w-2xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-[#1F1F1F] text-white text-sm font-medium px-4 py-2 rounded-full mb-8">
            <span>Multi-Agent Intelligence</span>
          </div>

          {/* Heading */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[#1F1F1F] mb-5 tracking-tight leading-tight">
            Stop guessing.<br />Start analyzing.
          </h1>

          {/* Subtext */}
          <p className="text-lg sm:text-xl text-[#6B6B6B] mb-10 max-w-xl mx-auto leading-relaxed">
            Run structured, multi-agent analysis on markets, competitors, and strategies — not generic outputs.
          </p>

          {/* Input Box */}
          <form onSubmit={handleSubmit} className="w-full mb-4">
            <div className="relative bg-white rounded-2xl shadow-lg border border-[#EAE7E3] transition-all duration-300 focus-within:shadow-xl focus-within:border-[#D9B89B]">
              <textarea
                ref={textareaRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
                rows={3}
                className="w-full px-5 py-4 pr-16 text-[#1F1F1F] text-base bg-transparent resize-none focus:outline-none placeholder-transparent disabled:opacity-50"
                style={{ minHeight: '120px', maxHeight: '200px' }}
              />
              
              {/* Custom Placeholder */}
              {!query && (
                <div 
                  className={`absolute left-5 top-4 text-base text-[#9CA3AF] pointer-events-none transition-opacity duration-200 ${
                    isPlaceholderVisible ? 'opacity-100' : 'opacity-0'
                  }`}
                >
                  {placeholders[placeholderIndex]}...
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="absolute right-4 bottom-4 w-11 h-11 bg-[#E6C7A9] hover:bg-[#D9B89B] disabled:bg-[#EAE7E3] disabled:cursor-not-allowed rounded-xl flex items-center justify-center transition-all duration-200 hover:scale-105 active:scale-95"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 text-white animate-spin" />
                ) : (
                  <ArrowUp className="w-5 h-5 text-white" />
                )}
              </button>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
                {error}
              </div>
            )}
          </form>

          {/* Microcopy */}
          <p className="text-[#6B6B6B] text-sm mb-6">
            Consultant-grade insights. Real comparisons. Zero fluff.
          </p>

          {/* Secondary Action */}
          <button
            onClick={() => handleExampleClick(exampleQueries[Math.floor(Math.random() * exampleQueries.length)])}
            className="inline-flex items-center gap-2 text-[#6B6B6B] hover:text-[#1F1F1F] text-sm font-medium transition-colors duration-200 group"
          >
            <span className="group-hover:underline">Try example analysis</span>
          </button>

          {/* Trust Signal */}
          <p className="text-[#9CA3AF] text-xs mt-12 max-w-md mx-auto">
            Used for structured analysis across markets, startups, and strategy decisions
          </p>
        </div>
      </div>
    </div>
  );
}

export default LandingPage;
