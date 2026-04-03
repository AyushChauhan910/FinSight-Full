import React, { useState, useRef } from 'react';
import api, { AgentResult, Citation } from '../services/api';

interface Props {
  selectedTicker: string | null;
  onResult: (result: AgentResult, step: number) => void;
  onStreamUpdate: (text: string, step: number) => void;
  onRunning: (running: boolean) => void;
}

const PRESET_QUERIES = [
  { label: 'Key Risk Factors', icon: '⚠', query: 'What are the key risk factors and potential threats to the business?', color: 'var(--red)' },
  { label: 'Revenue Growth', icon: '↗', query: 'Analyze revenue growth trends, segment breakdown, and year-over-year performance.', color: 'var(--green)' },
  { label: 'Full Report', icon: '▤', query: 'Generate a comprehensive analyst report covering business overview, financial performance, key risks, and YoY trends.', color: 'var(--cyan)' },
  { label: 'YoY Comparison', icon: '⇄', query: 'Compare key financial metrics year-over-year including revenue, net income, gross margin, and EPS.', color: 'var(--amber)' },
];

const CitationDrawer: React.FC<{ citation: Citation | null; onClose: () => void }> = ({ citation, onClose }) => {
  if (!citation) return null;
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100,
      display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end',
    }}
      onClick={onClose}
    >
      <div style={{
        position: 'absolute', inset: 0, background: '#00000066',
        backdropFilter: 'blur(2px)',
      }}/>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          position: 'relative', zIndex: 1,
          width: '420px', maxHeight: '80vh',
          background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)',
          borderRadius: 'var(--radius-xl) 0 0 var(--radius-xl)',
          overflow: 'auto', padding: '24px',
          animation: 'slideInRight 0.3s ease',
          boxShadow: '-8px 0 40px #00000088, 0 0 40px var(--cyan-glow)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '15px' }}>Source Document</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
              [{citation.chunk_id}]
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: '6px', padding: '6px', cursor: 'pointer', color: 'var(--text-muted)' }}
          >
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
          <span className="badge badge-cyan">{citation.metadata.ticker}</span>
          <span className="badge badge-amber">{citation.metadata.form_type}</span>
          <span className="badge" style={{ background: 'var(--bg-deep)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
            {citation.metadata.section}
          </span>
          <span className="badge" style={{ background: 'var(--bg-deep)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
            {citation.metadata.filing_date}
          </span>
        </div>

        <div style={{
          padding: '14px', background: 'var(--bg-card)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
          fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.8',
          fontFamily: 'var(--font-body)',
        }}>
          {citation.text}
        </div>
      </div>
    </div>
  );
};

const renderAnswerWithCitations = (text: string, citations: Citation[], onCitationClick: (c: Citation) => void) => {
  if (!text) return null;
  const parts = text.split(/(\[Doc [^\]]+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/\[Doc ([^\]]+)\]/);
    if (match) {
      const cit = citations.find(c => c.chunk_id === match[1]);
      return (
        <span
          key={i}
          onClick={() => cit && onCitationClick(cit)}
          style={{
            display: 'inline-flex', alignItems: 'center',
            background: 'var(--cyan-glow)', border: '1px solid var(--cyan-dim)',
            borderRadius: '3px', padding: '1px 5px', margin: '0 2px',
            fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--cyan)',
            cursor: cit ? 'pointer' : 'default',
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => cit && (e.currentTarget.style.background = 'var(--cyan-dim)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'var(--cyan-glow)')}
        >
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
};

export const QueryPanel: React.FC<Props> = ({ selectedTicker, onResult, onStreamUpdate, onRunning }) => {
  const [query, setQuery] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const [finalResult, setFinalResult] = useState<AgentResult | null>(null);
  const [error, setError] = useState('');
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [useStream, setUseStream] = useState(true);
  const stopStreamRef = useRef<(() => void) | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleRun = async () => {
    if (!selectedTicker || !query.trim()) return;
    setError('');
    setFinalResult(null);
    setStreamedText('');
    setIsStreaming(true);
    onRunning(true);
    onStreamUpdate('', 0);

    if (useStream) {
      let accumulated = '';
      let step = 0;
      stopStreamRef.current = api.streamQuery(
        selectedTicker,
        query,
        (token) => {
          accumulated += token;
          setStreamedText(accumulated);
          if (accumulated.length > 50 && step === 0) { step = 2; onStreamUpdate(accumulated, step); }
          else { onStreamUpdate(accumulated, step); }
        },
        (result) => {
          setFinalResult(result);
          setStreamedText('');
          setIsStreaming(false);
          onRunning(false);
          onResult(result, 4);
        },
        (err) => {
          // Fallback to REST
          runREST();
        }
      );
    } else {
      runREST();
    }
  };

  const runREST = async () => {
    if (!selectedTicker || !query.trim()) return;
    try {
      onStreamUpdate('', 1);
      await new Promise(r => setTimeout(r, 400));
      onStreamUpdate('', 2);
      const result = await api.queryCompany(selectedTicker, query);
      onStreamUpdate('', 3);
      await new Promise(r => setTimeout(r, 200));
      setFinalResult(result);
      setIsStreaming(false);
      onRunning(false);
      onResult(result, 4);
    } catch (e: any) {
      setError(e.message);
      setIsStreaming(false);
      onRunning(false);
    }
  };

  const handleStop = () => {
    stopStreamRef.current?.();
    setIsStreaming(false);
    onRunning(false);
  };

  const handlePreset = (q: string) => {
    setQuery(q);
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
        {/* Preset query buttons */}
        <div>
          <div className="section-label" style={{ marginBottom: '10px' }}>Quick Queries</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}>
            {PRESET_QUERIES.map(p => (
              <button
                key={p.label}
                onClick={() => handlePreset(p.query)}
                disabled={!selectedTicker}
                style={{
                  padding: '8px 12px',
                  background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  display: 'flex', alignItems: 'center', gap: '6px',
                  cursor: selectedTicker ? 'pointer' : 'not-allowed',
                  transition: 'all 0.15s', textAlign: 'left',
                  opacity: selectedTicker ? 1 : 0.4,
                }}
                onMouseEnter={e => {
                  if (!selectedTicker) return;
                  e.currentTarget.style.borderColor = p.color + '66';
                  e.currentTarget.style.background = p.color + '0d';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border)';
                  e.currentTarget.style.background = 'var(--bg-elevated)';
                }}
              >
                <span style={{ fontSize: '13px', color: p.color }}>{p.icon}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700, color: 'var(--text-secondary)' }}>{p.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Query input */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div className="section-label">Research Query</div>
          <div style={{ position: 'relative', flex: 1 }}>
            <textarea
              ref={textareaRef}
              className="input-field"
              style={{ height: '120px', resize: 'none', lineHeight: '1.6', fontSize: '13px', fontFamily: 'var(--font-body)' }}
              placeholder={selectedTicker ? `Ask anything about ${selectedTicker}...` : 'Select a company first'}
              value={query}
              onChange={e => setQuery(e.target.value)}
              disabled={!selectedTicker || isStreaming}
              onKeyDown={e => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleRun();
              }}
            />
            {selectedTicker && query.length === 0 && (
              <div style={{
                position: 'absolute', bottom: '10px', right: '10px',
                fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
                pointerEvents: 'none',
              }}>⌘↵ to run</div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <div
                onClick={() => setUseStream(!useStream)}
                style={{
                  width: 28, height: 16, borderRadius: '8px',
                  background: useStream ? 'var(--cyan)' : 'var(--border)',
                  position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
                  boxShadow: useStream ? '0 0 8px var(--cyan-dim)' : 'none',
                }}
              >
                <div style={{
                  position: 'absolute', top: 2, left: useStream ? 14 : 2,
                  width: 12, height: 12, borderRadius: '50%',
                  background: useStream ? 'var(--bg-void)' : 'var(--text-muted)',
                  transition: 'left 0.2s',
                }}/>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)' }}>Stream</span>
            </label>

            <div style={{ display: 'flex', gap: '8px' }}>
              {isStreaming && (
                <button
                  onClick={handleStop}
                  style={{
                    padding: '8px 14px', background: 'var(--red-dim)',
                    border: '1px solid #ff475744', borderRadius: 'var(--radius-md)',
                    fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
                    color: 'var(--red)', cursor: 'pointer', letterSpacing: '0.08em',
                  }}
                >■ STOP</button>
              )}
              <button
                className="btn-primary"
                onClick={handleRun}
                disabled={!selectedTicker || !query.trim() || isStreaming}
                style={{ padding: '8px 20px' }}
              >
                {isStreaming ? (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" style={{ animation: 'spin-slow 1s linear infinite' }}>
                      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="40 20"/>
                    </svg> RUNNING
                  </span>
                ) : (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <svg width="10" height="10" fill="none" viewBox="0 0 24 24">
                      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg> RUN
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div style={{
            padding: '10px 14px', background: 'var(--red-dim)', border: '1px solid #ff475744',
            borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--red)',
            fontFamily: 'var(--font-mono)',
          }}>✕ {error}</div>
        )}

        {/* Streaming output */}
        {(streamedText || finalResult?.answer) && (
          <div style={{ animation: 'fadeInUp 0.4s ease' }}>
            <div className="section-label" style={{ marginBottom: '8px' }}>Response</div>
            <div style={{
              padding: '14px', background: 'var(--bg-deep)',
              border: '1px solid var(--border-bright)', borderRadius: 'var(--radius-md)',
              maxHeight: '300px', overflowY: 'auto',
              fontSize: '13px', lineHeight: '1.8', color: 'var(--text-secondary)',
            }}>
              {finalResult?.answer
                ? renderAnswerWithCitations(finalResult.answer, finalResult.citations || [], setActiveCitation)
                : <span className="stream-cursor">{streamedText}</span>
              }
            </div>
            {finalResult?.citations && finalResult.citations.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '8px' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginRight: '4px', alignSelf: 'center' }}>Sources:</span>
                {finalResult.citations.map(c => (
                  <button
                    key={c.chunk_id}
                    onClick={() => setActiveCitation(c)}
                    style={{
                      padding: '2px 7px', background: 'var(--cyan-glow)',
                      border: '1px solid var(--cyan-dim)', borderRadius: '3px',
                      fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--cyan)',
                      cursor: 'pointer',
                    }}
                  >[{c.chunk_id}]</button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <CitationDrawer citation={activeCitation} onClose={() => setActiveCitation(null)} />
    </>
  );
};

export default QueryPanel;
