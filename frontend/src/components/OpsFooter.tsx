import { useState, useEffect } from 'react'
import type { HealthResponse, ScorecardMetrics } from '../types'
import { usd, pct } from '../lib/format'

interface OpsFooterProps {
  health: HealthResponse | null
  scorecard: ScorecardMetrics | null
  lastUpdated: Date | null
}

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function OpsFooter({ health, scorecard, lastUpdated }: OpsFooterProps) {
  const [countdown, setCountdown] = useState(300)

  useEffect(() => {
    setCountdown(300)
  }, [lastUpdated])

  useEffect(() => {
    const id = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const hasErrors = (scorecard?.ops_error_alert_count as number | null) != null &&
    (scorecard?.ops_error_alert_count as number) > 0
  const isHealthy = health?.status === 'healthy' && !hasErrors
  const statusDotClass = `status-dot ${isHealthy ? 'green' : 'red'}`

  const runCount = scorecard?.ops_run_count
  const successRate = scorecard?.ops_run_success_rate
  const errorCount = scorecard?.ops_error_alert_count as number | null
  const llmCost = scorecard?.ops_llm_cost_usd
  const staleness = scorecard?.['data_quote_staleness_rate'] as number | null | undefined

  return (
    <div className="ops-footer">
      <div className="ops-cell">
        <span className={statusDotClass} />
        {isHealthy ? 'Healthy' : 'Issues'}
      </div>
      <div className="ops-cell">
        <span className="detail-label">Runs</span>{' '}
        {runCount ?? '\u2014'} ({pct(successRate, 0)})
      </div>
      <div className="ops-cell">
        <span className="detail-label">Errors</span>{' '}
        {errorCount ?? 0}
      </div>
      <div className="ops-cell">
        <span className="detail-label">LLM Cost</span>{' '}
        {usd(llmCost)}
      </div>
      <div className="ops-cell">
        <span className="detail-label">Quote Staleness</span>{' '}
        {pct(staleness as number | null, 0)}
      </div>
      <div className="ops-cell">
        <span className="detail-label">Refresh</span>{' '}
        {formatCountdown(countdown)}
      </div>
    </div>
  )
}
