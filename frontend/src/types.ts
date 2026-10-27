export type Period = {
  start_time: string;
  decision_date: string;
  decision_cutoff: string;
  delivery_date: string;
  settlement_period: number;
  period_label: string;
  actual_mw: number | null;
  forecast_mw: number | null;
  error_mw: number | null;
  abs_error_mw: number | null;
  forecast_publish_time: string | null;
  lead_time_hours: number | null;
};

export type DailyRow = {
  decision_date: string;
  delivery_date: string;
  actual_mean_mw: number | null;
  forecast_mean_mw: number | null;
  matched_periods: number;
  actual_periods: number;
  forecast_periods: number;
  mae_mw: number | null;
  bias_mw: number | null;
};

export type AnalysisResponse = {
  meta: {
    decision_month: string;
    timezone: string;
    cutoff_time: string;
    decision_days: number;
    delivery_start: string;
    delivery_end: string;
    units: string;
    actual_dataset: string;
    forecast_dataset: string;
    method: string;
  };
  summary: {
    matched_periods: number;
    mae_mw: number | null;
    rmse_mw: number | null;
    bias_mw: number | null;
    wape_pct: number | null;
    expected_periods: number;
    actual_periods: number;
    forecast_periods: number;
    actual_forecast_pairs: number;
    coverage_pct: number;
    latest_selected_publish_time: string | null;
  };
  daily: DailyRow[];
  periods: Period[];
};
