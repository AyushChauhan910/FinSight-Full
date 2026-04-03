const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface IngestionResult {
  ticker: string;
  filings_processed: number;
  chunks_created: number;
  tokens_embedded: number;
  duration_seconds: number;
}

export interface IngestJobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'complete' | 'error';
  progress?: string | number;
  result?: IngestionResult;
  error?: string;
}

export interface CompanyStats {
  ticker: string;
  doc_count: number;
  token_count: number;
  filing_dates: string[];
  filing_types: string[];
}

interface CompanyStatsApi {
  ticker: string;
  document_count: number;
  total_tokens: number;
  filing_dates: string[];
  form_types: string[];
}

function mapCompanyStats(c: CompanyStatsApi): CompanyStats {
  return {
    ticker: c.ticker,
    doc_count: c.document_count,
    token_count: c.total_tokens,
    filing_dates: c.filing_dates || [],
    filing_types: c.form_types || [],
  };
}

export interface AgentResult {
  answer: string;
  report: ReportSections;
  citations: Citation[];
  iterations_used: number;
  tokens_used: number;
  sub_questions?: string[];
  retrieval_stats?: { query: string; chunks_found: number }[];
}

export interface ReportSections {
  executive_summary: string;
  key_metrics: KeyMetric[];
  risk_factors: RiskFactor[];
  yoy_analysis: YoYDataPoint[];
  investment_thesis: { bull_case: string[]; bear_case: string[] };
}

export interface KeyMetric {
  name: string;
  value: string;
  previous_value?: string;
  change_pct?: number;
  unit?: string;
}

export interface RiskFactor {
  title: string;
  description: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface YoYDataPoint {
  year: string;
  revenue?: number;
  net_income?: number;
  gross_margin?: number;
  eps?: number;
}

export interface Citation {
  chunk_id: string;
  text: string;
  metadata: {
    ticker: string;
    form_type: string;
    filing_date: string;
    section: string;
  };
}

class APIService {
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async ingestCompany(ticker: string, years = 3): Promise<{ job_id: string; status: string }> {
    return this.request('/api/research/ingest', {
      method: 'POST',
      body: JSON.stringify({ ticker: ticker.toUpperCase(), years }),
    });
  }

  async getJobStatus(jobId: string): Promise<IngestJobStatus> {
    const raw = await this.request<{
      job_id: string;
      status: string;
      progress?: string | number;
      result?: IngestionResult;
      error?: string;
    }>(`/api/research/status/${jobId}`);
    const statusMap: Record<string, IngestJobStatus['status']> = {
      queued: 'queued',
      running: 'running',
      completed: 'complete',
      failed: 'error',
    };
    return {
      job_id: raw.job_id,
      status: statusMap[raw.status] ?? (raw.status as IngestJobStatus['status']),
      progress: raw.progress,
      result: raw.result,
      error: raw.error,
    };
  }

  async queryCompany(ticker: string, query: string): Promise<AgentResult> {
    return this.request('/api/research/query', {
      method: 'POST',
      body: JSON.stringify({ ticker: ticker.toUpperCase(), query }),
    });
  }

  async generateReport(ticker: string): Promise<AgentResult> {
    return this.request('/api/research/report', {
      method: 'POST',
      body: JSON.stringify({ ticker: ticker.toUpperCase() }),
    });
  }

  async getCompanyStats(ticker: string): Promise<CompanyStats> {
    const raw = await this.request<CompanyStatsApi>(`/api/companies/${ticker.toUpperCase()}/stats`);
    return mapCompanyStats(raw);
  }

  async listCompanies(): Promise<CompanyStats[]> {
    const data = await this.request<{ companies: CompanyStatsApi[] }>('/api/companies/');
    return (data.companies || []).map(mapCompanyStats);
  }

  streamQuery(
    ticker: string,
    query: string,
    onToken: (token: string) => void,
    onDone: (result: AgentResult) => void,
    onError: (err: string) => void
  ): () => void {
    const url = `${BASE_URL}/api/research/stream?ticker=${encodeURIComponent(ticker)}&query=${encodeURIComponent(query)}`;
    const es = new EventSource(url);
    let finished = false;

    es.addEventListener('chunk', (e: MessageEvent) => {
      try {
        const d = JSON.parse(e.data as string) as { content?: string };
        if (d.content) onToken(d.content);
      } catch {
        onError('invalid chunk');
      }
    });

    es.addEventListener('done', (e: MessageEvent) => {
      finished = true;
      try {
        const d = JSON.parse(e.data as string) as AgentResult;
        onDone(d);
      } catch {
        onError('Parse error');
      }
      es.close();
    });

    es.addEventListener('stream_error', (e: MessageEvent) => {
      finished = true;
      try {
        const d = JSON.parse(e.data as string) as { error?: string };
        onError(d.error || 'Stream failed');
      } catch {
        onError('Stream failed');
      }
      es.close();
    });

    es.addEventListener('error', () => {
      if (finished) return;
      onError('Stream connection failed');
      es.close();
    });

    return () => es.close();
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request('/health');
  }
}

export const api = new APIService();
export default api;
