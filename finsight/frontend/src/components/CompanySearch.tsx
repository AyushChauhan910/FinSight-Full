import React, { useState, useCallback, useRef } from 'react';
import api, { CompanyStats, IngestJobStatus } from '../services/api';

interface Props {
  onCompanySelected: (ticker: string, stats: CompanyStats) => void;
  indexedCompanies: CompanyStats[];
  setIndexedCompanies: (companies: CompanyStats[]) => void;
}

const TOP_TICKERS = [
  'AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA','BRK.B',
  'JPM','JNJ','V','UNH','XOM','LLY','AVGO','MA','HD','PG','MRK','ABBV',
];

const TICKER_NAMES: Record<string, string> = {
  AAPL: 'Apple Inc.', MSFT: 'Microsoft Corp.', GOOGL: 'Alphabet Inc.',
  AMZN: 'Amazon.com Inc.', NVDA: 'NVIDIA Corp.', META: 'Meta Platforms',
  TSLA: 'Tesla Inc.', JPM: 'JPMorgan Chase', JNJ: 'Johnson & Johnson',
  V: 'Visa Inc.', UNH: 'UnitedHealth Group', XOM: 'Exxon Mobil',
  LLY: 'Eli Lilly', AVGO: 'Broadcom Inc.', MA: 'Mastercard',
  HD: 'Home Depot', PG: 'Procter & Gamble', MRK: 'Merck & Co.',
  ABBV: 'AbbVie Inc.', 'BRK.B': 'Berkshire Hathaway',
};

export const CompanySearch: React.FC<Props> = ({ onCompanySelected, indexedCompanies, setIndexedCompanies }) => {
  const [ticker, setTicker] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [jobStatus, setJobStatus] = useState<IngestJobStatus | null>(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const [error, setError] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const handleInput = (val: string) => {
    setTicker(val.toUpperCase());
    if (val.length > 0) {
      setSuggestions(TOP_TICKERS.filter(t => t.startsWith(val.toUpperCase())).slice(0, 5));
      setShowSuggestions(true);
    } else {
      setShowSuggestions(false);
    }
  };

  const pollStatus = useCallback((jobId: string, tickerVal: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getJobStatus(jobId);
        setJobStatus(status);
        if (status.status === 'complete' && status.result) {
          clearInterval(pollRef.current!);
          setIsIngesting(false);
          const stats = await api.getCompanyStats(tickerVal);
          setIndexedCompanies([...indexedCompanies.filter(c => c.ticker !== tickerVal), stats]);
          onCompanySelected(tickerVal, stats);
        } else if (status.status === 'error') {
          clearInterval(pollRef.current!);
          setIsIngesting(false);
          setError(status.error || 'Ingestion failed');
        }
      } catch (e) {
        clearInterval(pollRef.current!);
        setIsIngesting(false);
      }
    }, 2000);
  }, [indexedCompanies, onCompanySelected, setIndexedCompanies]);

  const handleAnalyze = async () => {
    if (!ticker.trim()) return;
    setError('');
    setIsIngesting(true);
    setJobStatus({ job_id: '', status: 'queued' });
    try {
      const { job_id } = await api.ingestCompany(ticker, 3);
      setJobStatus({ job_id, status: 'running', progress: 0 });
      pollStatus(job_id, ticker);
    } catch (e: any) {
      setError(e.message);
      setIsIngesting(false);
    }
  };

  const handleSelectCompany = async (t: string) => {
    try {
      const stats = await api.getCompanyStats(t);
      onCompanySelected(t, stats);
    } catch {
      setTicker(t);
    }
  };

  const progressPct =
    typeof jobStatus?.progress === 'number'
      ? Math.round(jobStatus.progress * 100)
      : isIngesting
        ? 50
        : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{
          width: 32, height: 32, borderRadius: '8px',
          background: 'linear-gradient(135deg, var(--cyan) 0%, var(--teal) 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 16px var(--cyan-dim)',
          flexShrink: 0,
        }}>
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
            <path d="M4 7h16M4 12h16M4 17h10" stroke="#030508" strokeWidth="2.5" strokeLinecap="round"/>
          </svg>
        </div>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>Data Ingestion</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>SEC EDGAR → ChromaDB</div>
        </div>
      </div>

      {/* Search */}
      <div style={{ position: 'relative' }}>
        <div style={{
          display: 'flex', gap: '8px', alignItems: 'stretch',
          background: 'var(--bg-deep)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          padding: '4px',
          transition: 'border-color 0.2s, box-shadow 0.2s',
          ...(ticker ? { borderColor: 'var(--border-bright)', boxShadow: '0 0 0 3px var(--cyan-glow)' } : {}),
        }}>
          <div style={{ display: 'flex', alignItems: 'center', padding: '0 10px' }}>
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="7" stroke="var(--text-muted)" strokeWidth="2"/>
              <path d="m16 16 4 4" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <input
            className="input-field"
            style={{ background: 'transparent', border: 'none', boxShadow: 'none', flex: 1, fontSize: '14px', fontWeight: 700, letterSpacing: '0.06em', padding: '8px 4px' }}
            placeholder="Enter ticker... (AAPL, MSFT)"
            value={ticker}
            onChange={e => handleInput(e.target.value)}
            onFocus={() => ticker && setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            onKeyDown={e => e.key === 'Enter' && !isIngesting && handleAnalyze()}
          />
          <button
            className="btn-primary"
            onClick={handleAnalyze}
            disabled={isIngesting || !ticker.trim()}
            style={{ padding: '8px 16px', fontSize: '10px', borderRadius: '6px' }}
          >
            {isIngesting ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <svg width="12" height="12" viewBox="0 0 24 24" style={{ animation: 'spin-slow 1s linear infinite' }}>
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="40 20"/>
                </svg>
                INDEXING
              </span>
            ) : 'ANALYZE'}
          </button>
        </div>

        {/* Suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div style={{
            position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 50,
            background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)',
            borderRadius: 'var(--radius-md)', overflow: 'hidden',
            boxShadow: '0 8px 32px #00000088',
            animation: 'fadeInUp 0.15s ease',
          }}>
            {suggestions.map((s, i) => (
              <div
                key={s}
                onClick={() => { setTicker(s); setShowSuggestions(false); }}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px', cursor: 'pointer',
                  borderBottom: i < suggestions.length - 1 ? '1px solid var(--border)' : 'none',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 700, color: 'var(--cyan)' }}>{s}</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{TICKER_NAMES[s] || ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Progress */}
      {isIngesting && jobStatus && (
        <div style={{ animation: 'fadeInUp 0.3s ease' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--cyan)' }}>
              {jobStatus.status === 'queued' ? '● QUEUED' : '● INDEXING FILINGS'}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>{progressPct}%</span>
          </div>
          <div style={{ height: '3px', background: 'var(--bg-deep)', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${progressPct}%`,
              background: 'linear-gradient(90deg, var(--cyan), var(--teal))',
              borderRadius: '2px',
              boxShadow: '0 0 8px var(--cyan)',
              transition: 'width 0.5s ease',
            }}/>
          </div>
          <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
            Fetching SEC EDGAR filings → parsing → embedding → storing in ChromaDB
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          padding: '10px 14px', background: 'var(--red-dim)', border: '1px solid #ff475744',
          borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--red)',
          fontFamily: 'var(--font-mono)', animation: 'fadeIn 0.3s ease',
        }}>
          ✕ {error}
        </div>
      )}

      <div className="divider"/>

      {/* Indexed companies */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <span className="section-label">Indexed Companies</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '11px',
            background: 'var(--cyan-glow)', color: 'var(--cyan)',
            padding: '2px 8px', borderRadius: '20px',
            border: '1px solid var(--cyan-dim)',
          }}>{indexedCompanies.length}</span>
        </div>

        {indexedCompanies.length === 0 ? (
          <div style={{
            padding: '24px 16px', textAlign: 'center',
            border: '1px dashed var(--border)', borderRadius: 'var(--radius-md)',
          }}>
            <div style={{ fontSize: '28px', marginBottom: '8px', opacity: 0.3 }}>◈</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No companies indexed yet</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {indexedCompanies.map((c, i) => (
              <div
                key={c.ticker}
                className="glass-card"
                onClick={() => onCompanySelected(c.ticker, c)}
                style={{
                  padding: '10px 14px', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  animation: `fadeInUp 0.3s ease ${i * 0.05}s both`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '6px',
                    background: 'linear-gradient(135deg, var(--cyan-glow), var(--bg-elevated))',
                    border: '1px solid var(--border-bright)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: 'var(--font-mono)', fontSize: '9px', fontWeight: 700, color: 'var(--cyan)',
                  }}>
                    {c.ticker.slice(0, 2)}
                  </div>
                  <div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>{c.ticker}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{c.doc_count?.toLocaleString()} chunks</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span className="badge badge-green">READY</span>
                  <svg width="12" height="12" fill="none" viewBox="0 0 24 24">
                    <path d="M9 18l6-6-6-6" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick picks */}
      <div>
        <div className="section-label" style={{ marginBottom: '8px' }}>Quick Select</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN', 'JPM'].map(t => (
            <button
              key={t}
              onClick={() => handleSelectCompany(t)}
              style={{
                padding: '4px 10px', background: 'var(--bg-elevated)',
                border: '1px solid var(--border)', borderRadius: '4px',
                fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
                color: 'var(--text-secondary)', cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--cyan-dim)';
                e.currentTarget.style.color = 'var(--cyan)';
                e.currentTarget.style.background = 'var(--cyan-glow)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.color = 'var(--text-secondary)';
                e.currentTarget.style.background = 'var(--bg-elevated)';
              }}
            >{t}</button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CompanySearch;
