import React, { useState } from 'react';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart,
} from 'recharts';
import { AgentResult, KeyMetric, RiskFactor } from '../services/api';

interface Props {
  result: AgentResult | null;
  ticker: string | null;
}

const TABS = ['Summary', 'Metrics', 'Risks', 'YoY Chart', 'Thesis'];

const MetricsTable: React.FC<{ metrics: KeyMetric[] }> = ({ metrics }) => (
  <div style={{ overflowX: 'auto' }}>
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--border)' }}>
          {['Metric', 'Current', 'Previous', 'Change'].map(h => (
            <th key={h} style={{
              padding: '10px 12px', textAlign: 'left',
              fontFamily: 'var(--font-mono)', fontSize: '10px',
              fontWeight: 700, letterSpacing: '0.1em',
              color: 'var(--text-muted)', textTransform: 'uppercase',
            }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {metrics.map((m, i) => {
          const isUp = m.change_pct !== undefined && m.change_pct > 0;
          const isDown = m.change_pct !== undefined && m.change_pct < 0;
          return (
            <tr
              key={i}
              style={{
                borderBottom: '1px solid var(--border)',
                animation: `fadeInUp 0.3s ease ${i * 0.05}s both`,
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <td style={{ padding: '10px 12px', fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500 }}>
                {m.name}
              </td>
              <td style={{ padding: '10px 12px', fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--text-primary)', fontWeight: 700 }}>
                {m.value}{m.unit && <span style={{ color: 'var(--text-muted)', fontSize: '10px', marginLeft: '2px' }}>{m.unit}</span>}
              </td>
              <td style={{ padding: '10px 12px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-muted)' }}>
                {m.previous_value || '—'}
              </td>
              <td style={{ padding: '10px 12px' }}>
                {m.change_pct !== undefined ? (
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '3px',
                    fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700,
                    color: isUp ? 'var(--green)' : isDown ? 'var(--red)' : 'var(--text-muted)',
                    background: isUp ? 'var(--green-dim)' : isDown ? 'var(--red-dim)' : 'var(--bg-elevated)',
                    padding: '2px 8px', borderRadius: '3px',
                  }}>
                    {isUp ? '↑' : isDown ? '↓' : '—'}
                    {Math.abs(m.change_pct).toFixed(1)}%
                  </span>
                ) : '—'}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

const RiskList: React.FC<{ risks: RiskFactor[] }> = ({ risks }) => {
  const severityConfig = {
    HIGH: { color: 'var(--red)', bg: 'var(--red-dim)', border: '#ff475744' },
    MEDIUM: { color: 'var(--amber)', bg: 'var(--amber-dim)', border: '#f5a62344' },
    LOW: { color: 'var(--green)', bg: 'var(--green-dim)', border: '#2ed57344' },
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {risks.map((r, i) => {
        const cfg = severityConfig[r.severity];
        return (
          <div
            key={i}
            style={{
              padding: '14px 16px',
              background: 'var(--bg-elevated)', border: `1px solid ${cfg.border}`,
              borderLeft: `3px solid ${cfg.color}`,
              borderRadius: `0 var(--radius-md) var(--radius-md) 0`,
              animation: `fadeInUp 0.35s ease ${i * 0.07}s both`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px', marginBottom: '6px' }}>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                {r.title}
              </div>
              <span style={{
                padding: '2px 8px', borderRadius: '3px',
                background: cfg.bg, color: cfg.color,
                border: `1px solid ${cfg.border}`,
                fontFamily: 'var(--font-mono)', fontSize: '9px', fontWeight: 700, letterSpacing: '0.1em',
                whiteSpace: 'nowrap', flexShrink: 0,
              }}>{r.severity}</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.7' }}>
              {r.description}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const YoYChartView: React.FC<{ data: any[] }> = ({ data }) => {
  const [activeMetric, setActiveMetric] = useState<'revenue' | 'net_income' | 'gross_margin'>('revenue');

  const metrics = [
    { key: 'revenue', label: 'Revenue', color: 'var(--cyan)' },
    { key: 'net_income', label: 'Net Income', color: 'var(--teal)' },
    { key: 'gross_margin', label: 'Gross Margin %', color: 'var(--amber)' },
  ];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{
        background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)',
        borderRadius: 'var(--radius-md)', padding: '10px 14px',
        boxShadow: '0 4px 20px #00000088',
      }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px' }}>{label}</div>
        {payload.map((p: any) => (
          <div key={p.name} style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: p.color, fontWeight: 700 }}>
            {p.value?.toLocaleString()}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: '6px', marginBottom: '16px' }}>
        {metrics.map(m => (
          <button
            key={m.key}
            onClick={() => setActiveMetric(m.key as any)}
            style={{
              padding: '6px 12px',
              background: activeMetric === m.key ? m.color + '22' : 'var(--bg-elevated)',
              border: `1px solid ${activeMetric === m.key ? m.color + '66' : 'var(--border)'}`,
              borderRadius: 'var(--radius-md)', cursor: 'pointer',
              fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
              color: activeMetric === m.key ? m.color : 'var(--text-muted)',
              transition: 'all 0.2s',
            }}
          >{m.label}</button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
          <defs>
            <linearGradient id="colorGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={metrics.find(m => m.key === activeMetric)?.color} stopOpacity={0.25}/>
              <stop offset="95%" stopColor={metrics.find(m => m.key === activeMetric)?.color} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false}/>
          <XAxis dataKey="year" tick={{ fontFamily: 'var(--font-mono)', fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false}/>
          <YAxis tick={{ fontFamily: 'var(--font-mono)', fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false}/>
          <Tooltip content={<CustomTooltip />}/>
          <Area
            type="monotone" dataKey={activeMetric}
            stroke={metrics.find(m => m.key === activeMetric)?.color}
            strokeWidth={2} fill="url(#colorGrad)"
            dot={{ fill: metrics.find(m => m.key === activeMetric)?.color, strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

const ThesisView: React.FC<{ thesis: { bull_case: string[]; bear_case: string[] } }> = ({ thesis }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
    {[
      { title: 'Bull Case', items: thesis.bull_case, color: 'var(--green)', icon: '↑', bg: 'var(--green-dim)', border: '#2ed57344' },
      { title: 'Bear Case', items: thesis.bear_case, color: 'var(--red)', icon: '↓', bg: 'var(--red-dim)', border: '#ff475744' },
    ].map(side => (
      <div key={side.title} style={{
        padding: '16px', background: 'var(--bg-elevated)',
        border: `1px solid ${side.border}`, borderRadius: 'var(--radius-lg)',
        borderTop: `3px solid ${side.color}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <span style={{
            width: 24, height: 24, borderRadius: '6px',
            background: side.bg, color: side.color,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 700, fontSize: '14px',
          }}>{side.icon}</span>
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '13px', color: side.color }}>{side.title}</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {side.items.map((item, i) => (
            <div key={i} style={{
              display: 'flex', gap: '8px', alignItems: 'flex-start',
              animation: `fadeInUp 0.3s ease ${i * 0.07}s both`,
            }}>
              <div style={{
                width: 4, height: 4, borderRadius: '50%',
                background: side.color, marginTop: '7px', flexShrink: 0,
              }}/>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>{item}</span>
            </div>
          ))}
        </div>
      </div>
    ))}
  </div>
);

export const ReportViewer: React.FC<Props> = ({ result, ticker }) => {
  const [activeTab, setActiveTab] = useState(0);

  if (!result) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100%', gap: '16px', padding: '40px',
        border: '1px dashed var(--border)', borderRadius: 'var(--radius-xl)',
        background: 'var(--bg-card)',
      }}>
        {/* 3D-ish floating document illustration */}
        <div style={{ position: 'relative', width: 80, height: 80, animation: 'float 4s ease-in-out infinite' }}>
          <div style={{
            position: 'absolute', inset: 0, borderRadius: '14px',
            background: 'linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-surface) 100%)',
            border: '1px solid var(--border-bright)',
            boxShadow: '0 8px 32px #00000066, 0 0 20px var(--cyan-glow), 4px 4px 0 var(--bg-deep)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '6px',
            padding: '14px',
          }}>
            {[80, 60, 70, 50].map((w, i) => (
              <div key={i} style={{
                height: 3, width: `${w}%`, borderRadius: '2px',
                background: i === 0 ? 'var(--cyan-dim)' : 'var(--border)',
              }}/>
            ))}
          </div>
          {/* Shadow/depth */}
          <div style={{
            position: 'absolute', inset: 4, top: 8, borderRadius: '14px',
            background: 'var(--cyan-glow)', filter: 'blur(12px)', zIndex: -1,
          }}/>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '16px', marginBottom: '6px' }}>
            No report generated yet
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Run a query above to generate an analyst report
          </div>
        </div>
      </div>
    );
  }

  const report = {
    executive_summary: result.report?.executive_summary ?? '',
    key_metrics: result.report?.key_metrics ?? [],
    risk_factors: result.report?.risk_factors ?? [],
    yoy_analysis: result.report?.yoy_analysis ?? [],
    investment_thesis: result.report?.investment_thesis ?? { bull_case: [] as string[], bear_case: [] as string[] },
  };
  const exportMarkdown = () => {
    const bull = report.investment_thesis.bull_case.map(b => `- ${b}`).join('\n');
    const bear = report.investment_thesis.bear_case.map(b => `- ${b}`).join('\n');
    const md = `# ${ticker} Analyst Report\n\n## Executive Summary\n${report.executive_summary}\n\n## Investment Thesis\n### Bull Case\n${bull}\n### Bear Case\n${bear}`;
    const blob = new Blob([md], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${ticker}_finsight_report.md`;
    a.click();
  };

  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-xl)', overflow: 'hidden',
      display: 'flex', flexDirection: 'column', height: '100%',
      animation: 'fadeIn 0.4s ease',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        background: 'linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-surface) 100%)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: 36, height: 36, borderRadius: '9px',
            background: 'linear-gradient(135deg, var(--cyan) 0%, var(--teal) 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 20px var(--cyan-dim)',
            fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, color: 'var(--bg-void)',
          }}>{ticker?.slice(0, 2)}</div>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '16px' }}>
              {ticker} Research Report
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)' }}>
              {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })} · FinSight AI
            </div>
          </div>
        </div>
        <button
          onClick={exportMarkdown}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '7px 14px', background: 'var(--bg-deep)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
            fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
            color: 'var(--text-secondary)', cursor: 'pointer', letterSpacing: '0.08em',
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--cyan-dim)'; e.currentTarget.style.color = 'var(--cyan)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
        >
          <svg width="12" height="12" fill="none" viewBox="0 0 24 24">
            <path d="M12 15V3M7 10l5 5 5-5M3 20h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          EXPORT
        </button>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-surface)', overflowX: 'auto',
      }}>
        {TABS.map((tab, i) => (
          <button
            key={tab}
            onClick={() => setActiveTab(i)}
            style={{
              padding: '12px 18px', border: 'none', background: 'transparent',
              fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700,
              letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
              color: activeTab === i ? 'var(--cyan)' : 'var(--text-muted)',
              borderBottom: `2px solid ${activeTab === i ? 'var(--cyan)' : 'transparent'}`,
              transition: 'all 0.2s', whiteSpace: 'nowrap',
              boxShadow: activeTab === i ? '0 2px 8px var(--cyan-glow)' : 'none',
            }}
          >{tab}</button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {activeTab === 0 && (
          <div style={{ animation: 'fadeInUp 0.3s ease' }}>
            <div style={{
              fontSize: '14px', lineHeight: '1.9', color: 'var(--text-secondary)',
              borderLeft: '3px solid var(--cyan)', paddingLeft: '16px',
            }}>
              {report.executive_summary}
            </div>
          </div>
        )}

        {activeTab === 1 && (
          <div style={{ animation: 'fadeInUp 0.3s ease' }}>
            {report.key_metrics?.length > 0
              ? <MetricsTable metrics={report.key_metrics} />
              : <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px', fontSize: '13px' }}>No metrics data available</div>
            }
          </div>
        )}

        {activeTab === 2 && (
          <div style={{ animation: 'fadeInUp 0.3s ease' }}>
            {report.risk_factors?.length > 0
              ? <RiskList risks={report.risk_factors} />
              : <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px', fontSize: '13px' }}>No risk factors extracted</div>
            }
          </div>
        )}

        {activeTab === 3 && (
          <div style={{ animation: 'fadeInUp 0.3s ease' }}>
            {report.yoy_analysis?.length > 0
              ? <YoYChartView data={report.yoy_analysis} />
              : <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px', fontSize: '13px' }}>No YoY data available</div>
            }
          </div>
        )}

        {activeTab === 4 && (
          <div style={{ animation: 'fadeInUp 0.3s ease' }}>
            {report.investment_thesis
              ? <ThesisView thesis={report.investment_thesis} />
              : <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px', fontSize: '13px' }}>No thesis generated</div>
            }
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportViewer;
