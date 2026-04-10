export interface HealthResponse {
  status: string
  last_brief_time: string | null
  predictions_count: number
  markets_count: number
  divergences_count: number
  kalshi_configured: boolean
  data_environment: string
  execution_environment: string
  timestamp: string
}

export interface Prediction {
  model_id: string
  prediction_type: string
  probability: number
  direction: string | null
  magnitude_range: string | null
  unit: string | null
  confidence: number
  timeframe: string
  reasoning: string
  evidence: string[]
  created_at: string
  kalshi_ticker?: string | null
  polymarket_id?: string | null
}

export interface PredictionsResponse {
  predictions: Prediction[]
}

export interface MarketData {
  ticker: string
  source: string
  best_yes_bid: number | null
  best_yes_ask: number | null
  best_no_bid: number | null
  best_no_ask: number | null
  yes_price: number | null
  no_price: number | null
  derived_price_kind: string | null
  volume: number | null
  fetched_at: string
  data_environment: string
}

export interface MarketsResponse {
  markets: MarketData[]
}

export interface Divergence {
  model_id: string
  prediction: Prediction | null
  model_probability: number
  market_price: MarketData | null
  market_probability: number | null
  buy_yes_edge: number | null
  buy_no_edge: number | null
  edge: number | null
  edge_pct: number | null
  signal: string
  strength: string | null
  entry_side: string | null
  entry_price: number | null
  entry_price_kind: string | null
  entry_price_is_executable: boolean | null
  tradeability_status: string | null
  created_at: string
}

export interface DivergencesResponse {
  divergences: Divergence[]
}

export interface ScorecardMetrics {
  signal_hit_rate: number | null
  signal_brier_score: number | null
  signal_calibration_max_gap: number | null
  ops_llm_cost_usd: number | null
  ops_run_count: number | null
  ops_run_success_rate: number | null
  ops_error_alert_count: number | null
  score_date: string
  [key: string]: unknown
}

export interface ContractInfo {
  ticker: string
  source: string
  event_ticker: string
  title: string
  resolution_criteria: string | null
  resolution_date: string | null
  contract_family: string | null
  expected_fee_rate: number | null
  expected_slippage_rate: number | null
  proxy_map: Record<string, string>
  best_proxy: string | null
}

export interface ContractsResponse {
  contracts: ContractInfo[]
}

export interface SignalRecord {
  signal_id: string
  created_at: string
  model_id: string
  effective_edge: number | null
  signal: string
  model_probability: number
  entry_price: number | null
  entry_side: string | null
  resolution_price: number | null
  model_was_correct: boolean | null
  run_id: string | null
}

export interface SignalsResponse {
  signals: SignalRecord[]
}

export interface LatestSignal {
  signal_id: string
  contract_ticker: string
  model_id: string
  proxy_class: string | null
  model_probability: number | null
  effective_edge: number
  signal: string
  entry_side: string | null
  entry_price: number | null
  model_reasoning: string | null
  market_yes_price: number | null
  market_no_price: number | null
  market_volume: number | null
  best_yes_bid: number | null
  best_yes_ask: number | null
  best_no_bid: number | null
  best_no_ask: number | null
  market_source: string | null
}

export interface LatestSignalsResponse {
  signals: LatestSignal[]
}

export interface EdgeDecayAnalysis {
  n_pairs: number
  avg_decay_rate: number | null
  avg_edge_change: number | null
  time_to_zero_edge: number | null
  round_trip_cost: number | null
  exit_profitable: boolean | null
  verdict: string | null
}

export interface PricePoint {
  fetched_at: string
  yes_price: number | null
  no_price: number | null
  volume: number | null
  best_yes_bid: number | null
  best_yes_ask: number | null
}

export interface PriceHistoryResponse {
  prices: PricePoint[]
}

export interface PredictionPoint {
  probability: number
  direction: string | null
  confidence: string
  created_at: string
  run_id: string | null
}

export interface PredictionHistoryResponse {
  models: Record<string, PredictionPoint[]>
}

export interface PortfolioPosition {
  ticker: string
  side: string
  quantity: number
  entry_price: number
  current_price: number | null
  notional: number | null
  unrealized_pnl: number | null
  weight_pct: number | null
}

export interface ClosedTrade {
  ticker: string
  side: string
  quantity: number
  entry_price: number
  exit_price: number
  pnl: number
  return_pct: number
  fees: number | null
}

export interface EquityPoint {
  date: string
  value: number
}

export interface PortfolioState {
  portfolio_value: number | null
  portfolio_return_pct: number | null
  cash: number | null
  cash_pct: number | null
  deployed: number | null
  positions: PortfolioPosition[]
  closed_trades: ClosedTrade[]
  equity_curve: EquityPoint[]
  max_drawdown: number | null
  max_drawdown_pct: number | null
  sharpe: number | null
  total_fees: number | null
  days_remaining: number | null
  win_rate: number | null
  max_concentration_pct: number | null
}
