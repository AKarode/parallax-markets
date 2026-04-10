import type { ScorecardMetrics } from '../types'
import { colors } from '../lib/colors'

interface ModelHealthProps {
  scorecard: ScorecardMetrics | null
}

function brierColor(value: number | null | undefined): string {
  if (value == null) return colors.muted
  if (value <= 0.22) return colors.green
  if (value >= 0.25) return colors.red
  return colors.amber
}

function hitRateColor(value: number | null | undefined): string {
  if (value == null) return colors.muted
  if (value >= 0.5) return colors.green
  if (value <= 0.4) return colors.red
  return colors.amber
}

function calibrationGapColor(value: number | null | undefined): string {
  if (value == null) return colors.muted
  if (value <= 0.10) return colors.green
  if (value >= 0.20) return colors.red
  return colors.amber
}

export function ModelHealth({ scorecard }: ModelHealthProps) {
  if (scorecard == null) {
    return <div className="loading-text">Loading scorecard...</div>
  }

  const brier = scorecard.signal_brier_score
  const hitRate = scorecard.signal_hit_rate
  const calibGap = scorecard.signal_calibration_max_gap

  return (
    <div>
      <div className="section-label">MODEL HEALTH</div>

      <div className="metric-row">
        <span className="metric-label">Brier Score</span>
        <span className="metric-value" style={{ color: brierColor(brier) }}>
          {brier != null ? brier.toFixed(3) : '\u2014'}
        </span>
        <span className="metric-benchmark">good &lt;0.22, random=0.25</span>
      </div>

      <div className="metric-row">
        <span className="metric-label">Overall Hit Rate</span>
        <span className="metric-value" style={{ color: hitRateColor(hitRate) }}>
          {hitRate != null ? `${(hitRate * 100).toFixed(0)}%` : '\u2014'}
        </span>
        <span className="metric-benchmark">&gt;50%</span>
      </div>

      <div className="metric-row">
        <span className="metric-label">Calibration Gap</span>
        <span className="metric-value" style={{ color: calibrationGapColor(calibGap) }}>
          {calibGap != null ? `${(calibGap * 100).toFixed(0)}%` : '\u2014'}
        </span>
        <span className="metric-benchmark">&lt;10%</span>
      </div>
    </div>
  )
}
