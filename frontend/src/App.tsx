import { useCallback,useEffect,useMemo,useState } from 'react';
import {
  Activity,AlertCircle,ArrowDownRight,ArrowUpRight,CheckCircle2,
  ChevronDown,Clock3,Download,ExternalLink,RefreshCw,ShieldCheck,Wind,Zap
} from 'lucide-react';
import {
  CartesianGrid,Legend,Line,LineChart,ResponsiveContainer,
  Tooltip,XAxis,YAxis,BarChart,Bar
} from 'recharts';
import type { AnalysisResponse, Period } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const MIN_DELIVERY_DATE = '2026-01-02';
const MAX_DELIVERY_DATE = '2026-02-01';
const CUTOFFS = ['09:00', '09:30', '10:00', '10:30', '11:00', '12:00', '15:00'];

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-GB', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

function formatDate(date: string, options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!date) return '—';
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', ...options }).format(new Date(`${date}T12:00:00Z`));
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return 'No forecast vintage selected';
  return new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/London' }).format(new Date(value)) + ' UK';
}

function downloadCsv(rows: Period[]) {
  const columns: (keyof Period)[] = [
    'decision_date', 'decision_cutoff', 'delivery_date', 'settlement_period', 'period_label',
    'actual_mw', 'forecast_mw', 'error_mw', 'abs_error_mw', 'forecast_publish_time', 'lead_time_hours',
  ];
  const escape = (value: unknown) => {
    const text = value === null || value === undefined ? '' : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = [columns.join(','), ...rows.map((row) => columns.map((column) => escape(row[column])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'wind-forecast-accuracy-january-2026.csv';
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [cutoffTime, setCutoffTime] = useState('10:00');
  const [selectedDate, setSelectedDate] = useState(MIN_DELIVERY_DATE);
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);

  const loadData = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    setData(null); 
    setRefreshing(forceRefresh);
    setError('');
    try {
      const params = new URLSearchParams({ month: '2026-01', cutoff_time: cutoffTime });
      if (forceRefresh) params.set('refresh', 'true');
      const response = await fetch(`${API_BASE}/api/analysis?${params.toString()}`);
      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          const body = await response.json();
          if (typeof body.detail === 'string') detail = body.detail;
        } catch {  }
        throw new Error(detail);
      }
      const result = (await response.json()) as AnalysisResponse;
      setData(result);
      setLastLoadedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error while loading the analysis.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [cutoffTime]);

  useEffect(() => {
    void loadData(false);
  }, [loadData]);

  const selectedPeriods = useMemo(() => (data?.periods || []).filter((row) => row.delivery_date === selectedDate), [data, selectedDate]);
  const selectedDaily = useMemo(
  () => (data?.daily ?? []).find(
    (row) => row.delivery_date === selectedDate
  ),
  [data, selectedDate]
);
  const selectedDecisionDate = selectedDaily?.decision_date || '';
  const chartByDay = useMemo(() => (data?.daily || []).map((row) => ({
    ...row,
    dayLabel: formatDate(row.delivery_date, { day: '2-digit', month: 'short' }),
  })), [data]);
  const intradayChart = useMemo(() => selectedPeriods.map((row) => ({
    ...row,
    intervalLabel: row.period_label,
    forecastLine: row.forecast_mw,
    actualLine: row.actual_mw,
  })), [selectedPeriods]);
  const errorChart = useMemo(() => chartByDay.map((row) => ({ ...row, dailyMae: row.mae_mw })), [chartByDay]);

  const hasMatchedData = Boolean(data && data.summary.matched_periods > 0);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Wind size={22} strokeWidth={2.3} /></div>
          <div><div className="brand-name">gridbricks</div><div className="brand-caption">ENERGY INTELLIGENCE</div></div>
        </div>
        <div className="nav-section-label">WORKSPACE</div>
        <div className="nav-item active"><Activity size={17} /> Forecast accuracy <span className="nav-dot" /></div>
        <div className="sidebar-bottom">
          <div className="sidebar-status"><span className="status-dot" /><span>Historical analysis</span></div>
          <div className="sidebar-footer">Pilot analytics workspace<br />Great Britain · Wind generation</div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Analytics <span>/</span> Wind forecast accuracy</div>
          <div className="topbar-right"><span className="period-chip"><span className="chip-dot" /> JAN 2026 SCOPE</span><span className="avatar">GB</span></div>
        </header>

        <section className="page-heading">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> DAY-AHEAD PROCUREMENT</div>
            <h1>Wind forecast accuracy</h1>
            <p className="page-subtitle">Understand the forecast available at decision time — and measure it against actual wind generation.</p>
          </div>
          <button className="button button-secondary refresh-button" onClick={() => void loadData(true)} disabled={loading}>
            <RefreshCw size={15} className={refreshing ? 'spin' : ''} /> Recalculate analysis
          </button>
        </section>

        <section className="control-panel">
          <div className="control-copy"><div className="control-icon"><Clock3 size={17} /></div><div><div className="control-title">Decision-time assumptions</div><div className="control-subtitle">Forecasts published after the cutoff are excluded from evaluation.</div></div></div>
          <div className="control-divider" />
          <label className="control-field"><span>Decision cutoff · UK time</span><span className="select-wrap"><select value={cutoffTime} onChange={(event) => setCutoffTime(event.target.value)}>{CUTOFFS.map((value) => <option key={value} value={value}>{value}</option>)}</select><ChevronDown size={14} /></span></label>
          <div className="scope-note"><ShieldCheck size={15} /><span>31 decision days · 744 hourly intervals</span></div>
        </section>

        {error && <div className="error-banner"><AlertCircle size={19} /><div><strong>Could not load analysis</strong><p>{error}</p><span>Check that the local FastAPI service is running at 127.0.0.1:8000, then retry.</span></div><button className="button button-secondary" onClick={() => void loadData(true)}>Try again</button></div>}

        <section className="section-topline"><div><h2>Performance overview</h2><p>January 2026 purchase decisions · delivery on the following day</p></div><div className="loaded-at">{loading ? <><span className="mini-spinner" /> Loading data…</> : lastLoadedAt ? `Updated ${lastLoadedAt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}` : 'Awaiting data'}</div></section>

        <section className="kpi-grid">
          <KpiCard label="Mean absolute error" value={formatNumber(data?.summary.mae_mw)} unit="MW" description="Average absolute forecast miss" icon={<Activity size={17} />} tone="blue" loading={loading && !data} />
          <KpiCard label="Root mean square error" value={formatNumber(data?.summary.rmse_mw)} unit="MW" description="Penalises larger forecast misses" icon={<Zap size={17} />} tone="purple" loading={loading && !data} />
          <KpiCard label="Forecast bias" value={formatNumber(data?.summary.bias_mw, 1)} unit="MW" description={data?.summary.bias_mw === null || data?.summary.bias_mw === undefined ? 'Forecast minus actual' : data.summary.bias_mw > 0 ? 'Systematic over-forecasting' : data.summary.bias_mw < 0 ? 'Systematic under-forecasting' : 'No average directional bias'} icon={data?.summary.bias_mw && data.summary.bias_mw > 0 ? <ArrowUpRight size={17} /> : <ArrowDownRight size={17} />} tone="amber" loading={loading && !data} />
          <KpiCard label="Matched coverage" value={formatNumber(data?.summary.coverage_pct, 1)} unit="%" description={`${formatNumber(data?.summary.matched_periods)} of ${formatNumber(data?.summary.expected_periods)} intervals`} icon={<CheckCircle2 size={17} />} tone="green" loading={loading && !data} />
        </section>

        <section className="chart-grid">
          <div className="panel chart-panel wide-panel">
            <div className="panel-header"><div><div className="panel-kicker">MONTHLY TREND</div><h3>Forecast vs actual generation</h3><p>Daily average power · MW</p></div><div className="legend-pills"><span><i className="legend-dot actual-dot" /> Actual</span><span><i className="legend-dot forecast-dot" /> Forecast</span></div></div>
            <div className="chart-wrap trend-chart">
              {chartByDay.length > 0 ? <ResponsiveContainer width="100%" height="100%"><LineChart data={chartByDay} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}><CartesianGrid stroke="#edf0f5" vertical={false} /><XAxis dataKey="dayLabel" tick={{ fill: '#8993a5', fontSize: 10 }} tickLine={false} axisLine={false} interval={4} /><YAxis tick={{ fill: '#8993a5', fontSize: 10 }} tickLine={false} axisLine={false} width={52} tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip content={<TrendTooltip />} /><Line type="monotone" dataKey="actual_mean_mw" name="Actual" stroke="#1f6a56" strokeWidth={2.2} dot={false} connectNulls={false} activeDot={{ r: 4 }} /><Line type="monotone" dataKey="forecast_mean_mw" name="Forecast" stroke="#6d73e8" strokeWidth={2.2} strokeDasharray="5 4" dot={false} connectNulls={false} activeDot={{ r: 4 }} /></LineChart></ResponsiveContainer> : <ChartEmpty loading={loading} />}
            </div>
            <div className="chart-footnote">Each forecast value is selected using the cutoff above, not the latest forecast available today.</div>
          </div>

          <div className="panel chart-panel error-panel">
            <div className="panel-header"><div><div className="panel-kicker">ERROR PROFILE</div><h3>Daily absolute error</h3><p>Mean absolute error · MW</p></div><div className="small-chart-icon"><Activity size={16} /></div></div>
            <div className="chart-wrap error-chart">
              {errorChart.length > 0 ? <ResponsiveContainer width="100%" height="100%"><BarChart data={errorChart} margin={{ top: 8, right: 0, bottom: 4, left: -15 }}><CartesianGrid stroke="#edf0f5" vertical={false} /><XAxis dataKey="dayLabel" tick={{ fill: '#8993a5', fontSize: 9 }} tickLine={false} axisLine={false} interval={7} /><YAxis tick={{ fill: '#8993a5', fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip content={<MaeTooltip />} /><Bar dataKey="dailyMae" name="Daily MAE" fill="#d79b51" radius={[3, 3, 0, 0]} maxBarSize={16} /></BarChart></ResponsiveContainer> : <ChartEmpty loading={loading} />}
            </div>
            <div className="chart-footnote">Days with no matched actual/forecast data are not assigned a zero error.</div>
          </div>
        </section>

        <section className="panel intraday-panel">
          <div className="panel-header intraday-header"><div><div className="panel-kicker">DELIVERY-DAY INSPECTOR</div><h3>Hourly generation</h3><p>Inspect forecast vintages and actual outturn for a single delivery day.</p></div><div className="date-picker-group"><label htmlFor="delivery-date">Delivery date</label><select id="delivery-date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)}>{(data?.daily || []).map((row) => <option key={row.delivery_date} value={row.delivery_date}>{formatDate(row.delivery_date)}</option>)}{!data && <option value={MIN_DELIVERY_DATE}>{formatDate(MIN_DELIVERY_DATE)}</option>}</select></div></div>
          <div className="selected-date-summary"><div className="date-summary-icon"><Wind size={20} /></div><div className="date-summary-title"><strong>{formatDate(selectedDate)}</strong><span>Decision made {selectedDecisionDate ? formatDate(selectedDecisionDate) : '—'} at {cutoffTime} UK time</span></div><div className="date-summary-metric"><span>Matched periods</span><strong>{formatNumber(selectedDaily?.matched_periods)} / 24</strong></div><div className="date-summary-metric"><span>Daily MAE</span><strong>{formatNumber(selectedDaily?.mae_mw)} <small>MW</small></strong></div></div>
          <div className="chart-wrap intraday-chart">
            {selectedPeriods.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={intradayChart} margin={{ top: 12, right: 12, bottom: 3, left: 0 }}><CartesianGrid stroke="#edf0f5" vertical={false} /><XAxis dataKey="intervalLabel" tick={{ fill: '#8993a5', fontSize: 10 }} tickLine={false} axisLine={false} interval={5} /><YAxis tick={{ fill: '#8993a5', fontSize: 10 }} tickLine={false} axisLine={false} width={55} tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip content={<TrendTooltip />} /><Legend wrapperStyle={{ fontSize: 11, color: '#707b8d', paddingTop: 8 }} /><Line type="monotone" dataKey="actualLine" name="Actual (MW)" stroke="#1f6a56" strokeWidth={2.3} dot={false} connectNulls={false} /><Line type="monotone" dataKey="forecastLine" name="Forecast at cutoff (MW)" stroke="#6d73e8" strokeWidth={2.3} strokeDasharray="5 4" dot={false} connectNulls={false} /></LineChart></ResponsiveContainer> : <ChartEmpty loading={loading} />}
          </div>
          <div className="table-heading-row"><div><h4>Hourly interval detail</h4><span>Sorted by delivery time · 	Hourly resolution</span></div><button className="button button-secondary export-button" onClick={() => data && downloadCsv(data.periods)} disabled={!data?.periods.length}><Download size={14} /> Export all periods</button></div>
          <div className="table-scroll"><table><thead><tr><th>Period</th><th>Delivery time</th><th>Actual (MW)</th><th>Forecast (MW)</th><th>Forecast error</th><th>Forecast published</th><th>Lead time</th></tr></thead><tbody>{selectedPeriods.slice(0, 24).map((row) => <tr key={row.start_time}><td><span className="period-number">{String(row.settlement_period).padStart(2, '0')}</span></td><td className="time-cell">{row.period_label}</td><td>{formatNumber(row.actual_mw)}</td><td>{formatNumber(row.forecast_mw)}</td><td><span className={`error-value ${row.error_mw === null ? 'muted' : row.error_mw > 0 ? 'positive' : row.error_mw < 0 ? 'negative' : ''}`}>{row.error_mw === null ? '—' : `${row.error_mw > 0 ? '+' : ''}${formatNumber(row.error_mw)} MW`}</span></td><td className="publish-cell">{row.forecast_publish_time ? formatTimestamp(row.forecast_publish_time) : 'No eligible forecast'}</td><td>{row.lead_time_hours === null ? '—' : `${formatNumber(row.lead_time_hours, 1)} h`}</td></tr>)}</tbody></table></div>
          <div className="table-bottom-note"><span className="status-dot" /> Actual/forecast pairs only are used for forecast-error metrics. Missing records remain missing; they are not treated as zero.</div>
        </section>

        <section className="bottom-grid">
          <div className="panel note-panel"><div className="note-icon"><ShieldCheck size={18} /></div><div><h3>Methodology & caveats</h3><p>Forecast error is defined as <strong>forecast − actual</strong>. Positive bias means wind generation was over-forecast on average. MAE and RMSE are reported in MW; WAPE is the sum of absolute errors divided by total absolute actual generation.</p><p>Actuals are deduplicated by keeping the latest published record per delivery interval. Forecasts are selected as of the configured decision cutoff. These are wind-only metrics; demand, market prices, and procurement volumes are outside this data scope.</p></div></div>
          <div className="panel source-panel"><div className="panel-kicker">DATA PROVENANCE</div><h3>Source datasets</h3><a href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream" target="_blank" rel="noreferrer">FUELHH · Actual generation <ExternalLink size={13} /></a><a href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream" target="_blank" rel="noreferrer">WINDFOR · Forecast vintages <ExternalLink size={13} /></a><div className="source-meta">Last analysis refresh: {lastLoadedAt ? lastLoadedAt.toLocaleString('en-GB') : '—'}<br />Data source: downloaded Elexon snapshot</div></div>
        </section>
        <footer className="page-footer"><span>GRIDBRICKS · ENERGY DECISIONS</span><span>Challenge scope: January 2026 · Europe/London time</span></footer>
      </main>
    </div>
  );
}

function KpiCard({ label, value, unit, description, icon, tone, loading }: { label: string; value: string; unit: string; description: string; icon: React.ReactNode; tone: string; loading: boolean }) {
  return <div className="kpi-card"><div className={`kpi-icon ${tone}`}>{icon}</div><div className="kpi-label">{label}</div><div className="kpi-value">{loading ? <span className="skeleton-value" /> : value}<span>{unit}</span></div><div className="kpi-description">{description}</div></div>;
}

function ChartEmpty({ loading }: { loading: boolean }) {
  return <div className="chart-empty">{loading ? <><span className="mini-spinner" /> Loading Elexon records…</> : <>No matching observations for this view.</>}</div>;
}

function TrendTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong>{payload.filter((item: any) => item.value !== null && item.value !== undefined).map((item: any) => <div key={item.dataKey}><span style={{ color: item.color }}>{item.name}</span><b>{formatNumber(item.value)} MW</b></div>)}</div>;
}

function MaeTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length || payload[0]?.value === null || payload[0]?.value === undefined) return null;
  return <div className="chart-tooltip"><strong>{label}</strong><div><span>Daily MAE</span><b>{formatNumber(payload[0].value)} MW</b></div></div>;
}