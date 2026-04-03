import React, { useState, useEffect, useRef } from 'react';
import { CompanySearch } from './components/CompanySearch';
import { AgentTrace } from './components/AgentTrace';
import { QueryPanel } from './components/QueryPanel';
import { ReportViewer } from './components/ReportViewer';
import api, { CompanyStats, AgentResult } from './services/api';
import './index.css';

const TICKER_TAPE = ['AAPL +2.4%', 'MSFT -0.8%', 'NVDA +5.1%', 'GOOGL +1.2%', 'AMZN +0.3%', 'TSLA -1.9%', 'META +3.7%', 'JPM +0.6%', 'BRK.B -0.2%', 'LLY +2.1%'];

const ParticleCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener('resize', resize);

    const particles: { x: number; y: number; vx: number; vy: number; size: number; opacity: number; color: string }[] = [];
    const colors = ['#00d4ff', '#00ffcc', '#f5a623'];
    for (let i = 0; i < 50; i++) {
      particles.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 1.5 + 0.3,
        opacity: Math.random() * 0.4 + 0.1,
        color: colors[Math.floor(Math.random() * colors.length)],
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color + Math.round(p.opacity * 255).toString(16).padStart(2, '0');
        ctx.fill();
      });

      // Draw connections
      particles.forEach((p, i) => {
        particles.slice(i + 1).forEach(q => {
          const dist = Math.hypot(p.x - q.x, p.y - q.y);
          if (dist < 100) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = `#00d4ff${Math.round((1 - dist / 100) * 0.15 * 255).toString(16).padStart(2, '0')}`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        });
      });
      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={canvasRef} style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }} />;
};

const OrbLogo: React.FC = () => (
  <div style={{ position: 'relative', width: 32, height: 32, flexShrink: 0 }}>
    <div style={{
      width: 32, height: 32, borderRadius: '50%',
      background: 'radial-gradient(circle at 35% 35%, var(--teal), var(--cyan) 40%, #0044ff 100%)',
      boxShadow: '0 0 16px var(--cyan-dim), 0 0 32px var(--cyan-glow), inset 0 1px 0 #ffffff33',
      animation: 'glow-pulse 3s ease-in-out infinite',
    }}>
      <div style={{
        position: 'absolute', top: '20%', left: '25%',
        width: '50%', height: '30%',
        background: 'linear-gradient(135deg, #ffffff44, transparent)',
        borderRadius: '50%', filter: 'blur(2px)',
      }}/>
    </div>
  </div>
);

const App: React.FC = () => {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [indexedCompanies, setIndexedCompanies] = useState<CompanyStats[]>([]);
  const [agentResult, setAgentResult] = useState<AgentResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [streamText, setStreamText] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'query' | 'report'>('query');

  const handleCompanySelected = (ticker: string, stats: CompanyStats) => {
    setSelectedTicker(ticker);
    setAgentResult(null);
    setStreamText('');
    setCurrentStep(0);
  };

  const handleResult = (result: AgentResult, step: number) => {
    setAgentResult(result);
    setCurrentStep(step);
  };

  const handleStreamUpdate = (text: string, step: number) => {
    setStreamText(text);
    setCurrentStep(step);
  };

  const handleRunning = (running: boolean) => {
    setIsRunning(running);
    if (running) {
      setAgentResult(null);
      setCurrentStep(0);
    }
    if (!running && agentResult) {
      setActiveTab('report');
    }
  };

  useEffect(() => {
    if (agentResult) {
      setTimeout(() => setActiveTab('report'), 300);
    }
  }, [agentResult]);

  useEffect(() => {
    api.listCompanies().then(setIndexedCompanies).catch(() => {});
  }, []);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <ParticleCanvas />

      {/* Top nav */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
        height: 52,
        background: 'rgba(3, 5, 8, 0.92)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center',
      }}>
        {/* Logo */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '0 20px', borderRight: '1px solid var(--border)',
          height: '100%', minWidth: 220,
        }}>
          <OrbLogo />
          <div>
            <div style={{
              fontFamily: 'var(--font-display)', fontWeight: 800,
              fontSize: '16px', letterSpacing: '0.08em',
              background: 'linear-gradient(90deg, var(--cyan), var(--teal))',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>FINSIGHT</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--text-muted)', letterSpacing: '0.15em', marginTop: '-1px' }}>
              AGENTIC FINANCIAL RESEARCH
            </div>
          </div>
        </div>

        {/* Ticker tape */}
        <div style={{ flex: 1, overflow: 'hidden', height: '100%', display: 'flex', alignItems: 'center', mask: 'linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent)' }}>
          <div style={{
            display: 'flex', gap: '40px', whiteSpace: 'nowrap',
            animation: 'ticker-slide 30s linear infinite',
          }}>
            {[...TICKER_TAPE, ...TICKER_TAPE].map((item, i) => {
              const isUp = item.includes('+');
              return (
                <span key={i} style={{
                  fontFamily: 'var(--font-mono)', fontSize: '11px',
                  color: isUp ? 'var(--green)' : 'var(--red)',
                }}>
                  {item}
                </span>
              );
            })}
          </div>
        </div>

        {/* Right status */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '16px',
          padding: '0 20px', height: '100%',
          borderLeft: '1px solid var(--border)',
        }}>
          {selectedTicker && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{
                width: 24, height: 24, borderRadius: '6px',
                background: 'linear-gradient(135deg, var(--cyan-glow), var(--bg-elevated))',
                border: '1px solid var(--border-bright)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontSize: '8px', fontWeight: 700, color: 'var(--cyan)',
              }}>{selectedTicker.slice(0, 2)}</div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, color: 'var(--cyan)' }}>{selectedTicker}</span>
              <span className="badge badge-green">ACTIVE</span>
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)' }}>
              SEC EDGAR · ChromaDB · Groq
            </span>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'var(--green)',
              boxShadow: '0 0 6px var(--green)',
              animation: 'glow-pulse 2s infinite',
            }}/>
          </div>
        </div>
      </header>

      {/* Main layout */}
      <div style={{
        display: 'flex', flex: 1, paddingTop: 52,
        minHeight: '100vh',
      }}>
        {/* Left sidebar */}
        <aside style={{
          width: sidebarOpen ? 280 : 0,
          flexShrink: 0, overflow: 'hidden',
          borderRight: '1px solid var(--border)',
          background: 'rgba(7, 13, 20, 0.8)',
          backdropFilter: 'blur(10px)',
          transition: 'width 0.3s ease',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ padding: '20px', flex: 1, overflowY: 'auto', minWidth: 280 }}>
            <CompanySearch
              onCompanySelected={handleCompanySelected}
              indexedCompanies={indexedCompanies}
              setIndexedCompanies={setIndexedCompanies}
            />

            <div style={{ marginTop: '24px' }}>
              <AgentTrace
                result={agentResult}
                isRunning={isRunning}
                currentStep={currentStep}
                streamingText={streamText}
              />
            </div>
          </div>
        </aside>

        {/* Sidebar toggle */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          style={{
            position: 'fixed', left: sidebarOpen ? 268 : 0, top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 40, width: 12, height: 48,
            background: 'var(--bg-elevated)', border: '1px solid var(--border)',
            borderLeft: sidebarOpen ? '1px solid var(--border)' : 'none',
            borderRadius: sidebarOpen ? '0 6px 6px 0' : '0 6px 6px 0',
            cursor: 'pointer', color: 'var(--text-muted)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'left 0.3s ease',
            padding: 0,
          }}
        >
          <div style={{
            width: 0, height: 0,
            borderStyle: 'solid',
            borderWidth: sidebarOpen ? '4px 4px 4px 0' : '4px 0 4px 4px',
            borderColor: sidebarOpen
              ? 'transparent var(--text-muted) transparent transparent'
              : 'transparent transparent transparent var(--text-muted)',
          }}/>
        </button>

        {/* Main panel */}
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
          {/* Mobile/panel tab switcher */}
          <div style={{
            display: 'flex', borderBottom: '1px solid var(--border)',
            background: 'rgba(7, 13, 20, 0.9)', backdropFilter: 'blur(10px)',
            padding: '0 24px',
          }}>
            {[{ id: 'query', label: 'Research Query', icon: '⌕' }, { id: 'report', label: 'Analyst Report', icon: '▤' }].map(t => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id as any)}
                style={{
                  padding: '14px 18px', border: 'none', background: 'transparent',
                  fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700,
                  letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
                  color: activeTab === t.id ? 'var(--cyan)' : 'var(--text-muted)',
                  borderBottom: `2px solid ${activeTab === t.id ? 'var(--cyan)' : 'transparent'}`,
                  transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: '6px',
                }}
              >
                <span style={{ fontSize: '14px' }}>{t.icon}</span>
                {t.label}
                {t.id === 'report' && agentResult && (
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%', background: 'var(--cyan)',
                    boxShadow: '0 0 6px var(--cyan)',
                  }}/>
                )}
              </button>
            ))}
          </div>

          <div style={{
            flex: 1, padding: '24px', overflowY: 'auto',
            display: 'grid',
            gridTemplateColumns: activeTab === 'report' ? '1fr' : '1fr',
          }}>
            {activeTab === 'query' ? (
              <div style={{
                display: 'grid',
                gridTemplateColumns: agentResult ? '1fr 1fr' : '1fr',
                gap: '24px',
                height: 'fit-content',
                transition: 'grid-template-columns 0.3s ease',
              }}>
                <div className="glass-card" style={{ padding: '24px' }}>
                  <QueryPanel
                    selectedTicker={selectedTicker}
                    onResult={handleResult}
                    onStreamUpdate={handleStreamUpdate}
                    onRunning={handleRunning}
                  />
                </div>
                {agentResult && (
                  <div style={{ animation: 'slideInRight 0.4s ease' }}>
                    <ReportViewer result={agentResult} ticker={selectedTicker} />
                  </div>
                )}
              </div>
            ) : (
              <ReportViewer result={agentResult} ticker={selectedTicker} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
};

export default App;
