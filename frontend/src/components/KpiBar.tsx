import type { HealthResponse, PortfolioState, ScorecardMetrics, DivergencesResponse } from '../types'
import { usd, signedPct, relativeTime, pct } from '../lib/format'
import { colors } from '../lib/colors'

interface KpiBarProps {
  health: HealthResponse | null
  portfolio: PortfolioState | null
  scorecard: ScorecardMetrics | null
  divergences: DivergencesResponse | null
}

const BUDGET_CAP = 20

function portfolioColor(returnPct: number | null | undefined): string {
  if (returnPct == null) return colors.muted
  return returnPct >= 0 ? colors.green : colors.red
}

function lastRunColor(iso: string | null | undefined): string {
  if (iso == null) return colors.red
  const hoursAgo = (Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60)
  return hoursAgo > 24 ? colors.red : colors.subtle
}

function budgetColor(cost: number | null | undefined): string {
  if (cost == null) return colors.muted
  const pctUsed = cost / BUDGET_CAP
  if (pctUsed > 0.95) return colors.red
  if (pctUsed > 0.80) return colors.amber
  return colors.subtle
}

function countActiveSignals(divergences: DivergencesResponse | null): number {
  if (!divergences) return 0
  return divergences.divergences.filter(
    (d) => d.signal !== 'HOLD' && d.signal !== 'REFUSED'
  ).length
}

export function KpiBar({ health, portfolio, scorecard, divergences }: KpiBarProps) {
  const returnPct = portfolio?.portfolio_return_pct
  const activeSignals = countActiveSignals(divergences)
  const llmCost = scorecard?.ops_llm_cost_usd

  return (
    <div className="kpi-bar">
      <div className="kpi-cell">
        <div className="kpi-label">Portfolio</div>
        <div className="kpi-value" style={{ color: portfolioColor(returnPct) }}>
          {usd(portfolio?.portfolio_value)} {signedPct(returnPct != null ? returnPct * 100 : null)}
        </div>
      </div>

      <div className="kpi-cell">
        <div className="kpi-label">Hit Rate</div>
        <div className="kpi-value">
          {pct(scorecard?.signal_hit_rate)}
        </div>
      </div>

      <div className="kpi-cell">
        <div className="kpi-label">Active Signals</div>
        <div className="kpi-value" style={{ color: colors.amber }}>
          {activeSignals} signal{activeSignals !== 1 ? 's' : ''}
        </div>
      </div>

      <div className="kpi-cell">
        <div className="kpi-label">Last Run</div>
        <div className="kpi-value" style={{ color: lastRunColor(health?.last_brief_time) }}>
          {relativeTime(health?.last_brief_time)}
        </div>
      </div>

      <div className="kpi-cell">
        <div className="kpi-label">Budget</div>
        <div className="kpi-value" style={{ color: budgetColor(llmCost) }}>
          {usd(llmCost)}/${BUDGET_CAP}
        </div>
      </div>
    </div>
  )
}
