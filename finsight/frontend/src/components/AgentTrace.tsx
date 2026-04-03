import React, { useState } from 'react';
import { AgentResult } from '../services/api';

interface Props {
  result: AgentResult | null;
  isRunning: boolean;
  currentStep: number; // 0-4 matching pipeline steps
  streamingText?: string;
}

const PIPELINE_STEPS = [
  {
    id: 0,
    icon: (
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
        <path d="M4 6h16M4 12h10M4 18h13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    label: 'Query Decomposition',
    desc: 'Breaking query into sub-questions',
    color: 'var(--cyan)',
  },
  {
    id: 1,
    icon: (
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2"/>
        <path d="m16 16 4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    label: 'Document Retrieval',
    desc: 'Searching SEC filings via vector similarity',
    color: 'var(--teal)',
  },
  {
    id: 2,
    icon: (
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" stroke="currentColor" strokeWidth="2"/>
        <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    label: 'Analysis',
    desc: 'Drafting analysis with inline citations',
    color: '#a78bfa',
  },
  {
    id: 3,
    icon: (
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
        <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
      </svg>
    ),
    label: 'Fact Validation',
    desc: 'Cross-referencing numerical claims',
    color: 'var(--amber)',
  },
  {
    id: 4,
    icon: (
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2"/>
        <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2"/>
        <line x1="8" y1="13" x2="16" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <line x1="8" y1="17" x2="12" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    label: 'Report Generation',
    desc: 'Structuring final output',
    color: 'var(--green)',
  },
];

const StepStatus: React.FC<{ stepIdx: number; currentStep: number; isDone: boolean }> = ({ stepIdx, currentStep, isDone }) => {
  if (isDone) {
    return (
      <div style={{
        width: 18, height: 18, borderRadius: '50%',
        background: 'var(--green-dim)', border: '1px solid var(--green)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <svg width="10" height="10" fill="none" viewBox="0 0 24 24">
          <path d="M5 13l4 4L19 7" stroke="var(--green)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
    );
  }
  if (stepIdx === currentStep) {
    return (
      <div style={{
        width: 18, height: 18, borderRadius: '50%',
        border: '2px solid var(--cyan)',
        boxShadow: '0 0 8px var(--cyan)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        animation: 'pulse-cyan 2s ease-in-out infinite',
      }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--cyan)' }}/>
      </div>
    );
  }
  return (
    <div style={{
      width: 18, height: 18, borderRadius: '50%',
      border: '1px solid var(--border)', background: 'var(--bg-deep)',
      flexShrink: 0,
    }}/>
  );
};

export const AgentTrace: React.FC<Props> = ({ result, isRunning, currentStep, streamingText }) => {
  const [expanded, setExpanded] = useState(true);
  const isDone = !!result;

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px', cursor: 'pointer',
          background: 'var(--bg-elevated)',
          borderBottom: expanded ? '1px solid var(--border)' : 'none',
          transition: 'background 0.2s',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: 28, height: 28, borderRadius: '7px',
            background: isRunning ? 'linear-gradient(135deg, var(--cyan), var(--teal))' : 'var(--bg-deep)',
            border: isRunning ? 'none' : '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.3s',
            boxShadow: isRunning ? '0 0 16px var(--cyan-dim)' : 'none',
          }}>
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24"
              style={{ animation: isRunning ? 'spin-slow 3s linear infinite' : 'none' }}>
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
                stroke={isRunning ? '#030508' : 'var(--text-muted)'} strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '13px' }}>Agent Trace</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)' }}>
              {isDone ? `${result.iterations_used} iteration${result.iterations_used !== 1 ? 's' : ''} · ${result.tokens_used?.toLocaleString()} tokens` : isRunning ? 'Processing...' : 'Run a query to see agent trace'}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isDone && <span className="badge badge-green">COMPLETE</span>}
          {isRunning && <span className="badge badge-cyan">RUNNING</span>}
          <svg
            width="14" height="14" fill="none" viewBox="0 0 24 24"
            style={{ color: 'var(--text-muted)', transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
          >
            <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>

      {/* Pipeline steps */}
      {expanded && (
        <div style={{ padding: '16px' }}>
          {/* Visual pipeline */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {PIPELINE_STEPS.map((step, i) => {
              const isActive = isRunning && i === currentStep;
              const isComplete = isDone || (isRunning && i < currentStep);

              return (
                <div key={step.id} style={{ display: 'flex', gap: '12px' }}>
                  {/* Left connector */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 18 }}>
                    <StepStatus stepIdx={i} currentStep={currentStep} isDone={isComplete} />
                    {i < PIPELINE_STEPS.length - 1 && (
                      <div style={{
                        width: 1, flex: 1, minHeight: 24,
                        background: isComplete
                          ? 'linear-gradient(180deg, var(--green), var(--border))'
                          : isActive
                          ? 'linear-gradient(180deg, var(--cyan), var(--border))'
                          : 'var(--border)',
                        margin: '3px 0',
                        transition: 'background 0.5s',
                      }}/>
                    )}
                  </div>

                  {/* Step content */}
                  <div style={{
                    flex: 1, paddingBottom: i < PIPELINE_STEPS.length - 1 ? '12px' : 0,
                    animation: isActive ? 'fadeIn 0.3s ease' : 'none',
                  }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '8px',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-md)',
                      border: `1px solid ${isActive ? step.color + '44' : isComplete ? 'var(--border-bright)' : 'var(--border)'}`,
                      background: isActive ? step.color + '0d' : isComplete ? 'var(--bg-elevated)' : 'var(--bg-deep)',
                      transition: 'all 0.3s',
                    }}>
                      <div style={{ color: isActive || isComplete ? step.color : 'var(--text-muted)', transition: 'color 0.3s' }}>
                        {step.icon}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '12px',
                          color: isActive ? step.color : isComplete ? 'var(--text-primary)' : 'var(--text-muted)',
                          transition: 'color 0.3s',
                        }}>{step.label}</div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '1px' }}>
                          {step.desc}
                        </div>
                      </div>
                      {isActive && (
                        <div style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
                          {[0, 1, 2].map(d => (
                            <div key={d} style={{
                              width: 3, height: 3, borderRadius: '50%',
                              background: step.color,
                              animation: `glow-pulse 1s ${d * 0.2}s ease-in-out infinite`,
                            }}/>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Sub-questions expansion */}
                    {isComplete && i === 0 && result?.sub_questions && (
                      <div style={{ marginTop: '6px', paddingLeft: '8px' }}>
                        {result.sub_questions.map((q, qi) => (
                          <div key={qi} style={{
                            fontSize: '10px', color: 'var(--text-muted)',
                            padding: '3px 0',
                            borderLeft: '2px solid var(--cyan-dim)',
                            paddingLeft: '8px',
                            marginBottom: '2px',
                            fontFamily: 'var(--font-mono)',
                            animation: `fadeInUp 0.3s ease ${qi * 0.1}s both`,
                          }}>
                            {qi + 1}. {q}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Retrieval stats */}
                    {isComplete && i === 1 && result?.retrieval_stats && (
                      <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {result.retrieval_stats.map((rs, ri) => (
                          <div key={ri} style={{
                            padding: '2px 8px', background: 'var(--cyan-glow)',
                            border: '1px solid var(--cyan-dim)', borderRadius: '3px',
                            fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--cyan)',
                            animation: `fadeIn 0.3s ease ${ri * 0.05}s both`,
                          }}>
                            {rs.chunks_found} chunks
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Stats bar */}
          {isDone && (
            <div style={{
              marginTop: '16px', padding: '12px',
              background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-bright)',
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '12px',
              animation: 'fadeInUp 0.4s ease',
            }}>
              {[
                { label: 'Iterations', value: result.iterations_used, color: 'var(--cyan)' },
                { label: 'Tokens', value: result.tokens_used?.toLocaleString(), color: 'var(--teal)' },
                { label: 'Citations', value: result.citations?.length, color: 'var(--amber)' },
              ].map(stat => (
                <div key={stat.label} style={{ textAlign: 'center' }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: 700,
                    color: stat.color, lineHeight: 1,
                  }}>{stat.value}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '3px', letterSpacing: '0.05em' }}>
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Streaming preview */}
          {isRunning && streamingText && (
            <div style={{
              marginTop: '12px', padding: '10px 12px',
              background: 'var(--bg-deep)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)',
              maxHeight: '80px', overflowY: 'auto',
              lineHeight: '1.5',
            }}>
              <span className="stream-cursor">{streamingText.slice(-200)}</span>
            </div>
          )}

          {!isDone && !isRunning && (
            <div style={{
              marginTop: '12px', padding: '14px', textAlign: 'center',
              border: '1px dashed var(--border)', borderRadius: 'var(--radius-md)',
            }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Run a query to see agent trace</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AgentTrace;
