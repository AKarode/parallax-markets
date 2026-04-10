import type { PredictionsResponse, PredictionHistoryResponse, ScorecardMetrics } from '../types'
import { pct } from '../lib/format'
import { colors } from '../lib/colors'
import { Sparkline } from './Sparkline'

interface ModelCardsProps {
  predictions: PredictionsResponse | null
  predictionHistory: PredictionHistoryResponse | null
  scorecard: ScorecardMetrics | null
}

const MODEL_IDS = ['oil_price', 'ceasefire', 'hormuz_reopening'] as const

const MODEL_LABELS: Record<string, string> = {
  oil_price: 'OIL PRICE',
  ceasefire: 'CEASEFIRE',
  hormuz_reopening: 'HORMUZ REOPENING',
}

function directionColor(direction: string | null | undefined): string {
  if (direction === 'increase') return colors.green
  if (direction === 'decrease') return colors.red
  return colors.subtle
}

export function ModelCards({ predictions, predictionHistory }: ModelCardsProps) {
  return (
    <div className="model-cards">
      {MODEL_IDS.map((modelId) => {
        const prediction = predictions?.predictions.find((p) => p.model_id === modelId)
        const history = predictionHistory?.models[modelId]
        const sparkData = history
          ? history.slice(-10).map((pt) => pt.probability)
          : []

        return (
          <div className="model-card" key={modelId}>
            <div className="model-name">{MODEL_LABELS[modelId]}</div>

            <div
              className="model-probability"
              style={{ color: directionColor(prediction?.direction) }}
            >
              {pct(prediction?.probability ?? null, 0)}
            </div>

            <div className="model-direction">
              {prediction?.direction ?? '\u2014'} &middot; {prediction?.timeframe ?? '\u2014'}
            </div>

            {sparkData.length >= 2 && (
              <Sparkline
                data={sparkData}
                color={directionColor(prediction?.direction)}
              />
            )}

            <div className="c-muted" style={{ fontSize: '0.75rem' }}>
              Confidence: {pct(prediction?.confidence ?? null)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
