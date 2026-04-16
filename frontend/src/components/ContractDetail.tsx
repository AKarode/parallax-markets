import { usePolling } from '../hooks/usePolling'
import { pct, edge, relativeTime } from '../lib/format'
import { PriceChart } from './PriceChart'
import type {
  ContractInfo,
  Divergence,
  MarketData,
  SignalsResponse,
  EdgeDecayAnalysis,
  PriceHistoryResponse,
  PredictionHistoryResponse,
} from '../types'

interface ContractDetailProps {
  contract: ContractInfo
  divergence: Divergence | null
  market: MarketData | null
}

function signalBadgeClass(signal: string): string {
  switch (signal) {
    case 'BUY_YES': return 'badge badge-buy-yes'
    case 'BUY_NO': return 'badge badge-buy-no'
    default: return 'badge badge-hold'
  }
}

export function ContractDetail({ contract, divergence, market }: ContractDetailProps) {
  const { data: signals } = usePolling<SignalsResponse>(
    `/api/signals?contract=${contract.ticker}`
  )
  const { data: edgeDecay } = usePolling<EdgeDecayAnalysis>(
    `/api/edge-decay?contract=${contract.ticker}`
  )
  const { data: priceHistory } = usePolling<PriceHistoryResponse>(
    `/api/price-history?ticker=${contract.ticker}`
  )
  const { data: predictionHistory } = usePolling<PredictionHistoryResponse>(
    `/api/prediction-history`
  )

  const feeRate = contract.expected_fee_rate ?? 0
  const slippageRate = contract.expected_slippage_rate ?? 0
  const rawEdge = divergence?.edge ?? 0
  const effectiveEdge = rawEdge - feeRate - slippageRate

  const modelId = divergence?.model_id ?? ''
  const modelPredictions = predictionHistory?.models[modelId]

  const recentSignals = (signals?.signals ?? []).slice(0, 5)

  return (
    <tr>
      <td colSpan={8}>
        <div className="contract-detail">
          {/* Row 1: 2-column grid */}
          <div className="detail-grid">
            <div className="detail-section">
              <div className="detail-label">Resolution Criteria</div>
              <div className="detail-value">
                {contract.resolution_criteria ?? 'Not specified'}
              </div>

              <div className="detail-label" style={{ marginTop: 12 }}>Order Book</div>
              <div className="detail-value">
                <div className="metric-row">
                  <span className="metric-label">Yes Bid / Ask</span>
                  <span className="metric-value">
                    {pct(market?.best_yes_bid)} / {pct(market?.best_yes_ask)}
                  </span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">No Bid / Ask</span>
                  <span className="metric-value">
                    {pct(market?.best_no_bid)} / {pct(market?.best_no_ask)}
                  </span>
                </div>
              </div>

              <div className="detail-label" style={{ marginTop: 12 }}>Edge Math</div>
              <div className="detail-value">
                <div className="metric-row">
                  <span className="metric-label">Raw Edge</span>
                  <span className="metric-value">{edge(rawEdge)}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Fee</span>
                  <span className="metric-value c-red">-{pct(feeRate)}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Slippage</span>
                  <span className="metric-value c-red">-{pct(slippageRate)}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Effective Edge</span>
                  <span className="metric-value" style={{ fontWeight: 600 }}>
                    {edge(effectiveEdge)}
                  </span>
                </div>
              </div>
            </div>

            <div className="detail-section">
              <PriceChart
                prices={priceHistory?.prices ?? []}
                predictions={modelPredictions}
              />
            </div>
          </div>

          {/* Row 2: 3-column grid */}
          <div className="detail-grid-3">
            <div className="detail-section">
              <div className="detail-label">Model Reasoning</div>
              <div className="reasoning-text">
                {divergence?.prediction?.reasoning ?? 'No reasoning available'}
              </div>
            </div>

            <div className="detail-section">
              <div className="detail-label">Signal History</div>
              {recentSignals.length === 0 ? (
                <span className="loading-text">No signals yet</span>
              ) : (
                recentSignals.map((s, i) => (
                  <div key={i} className="metric-row">
                    <span className={signalBadgeClass(s.signal)}>{s.signal}</span>
                    <span className="metric-value">
                      {edge(s.effective_edge)}
                    </span>
                    <span className="c-muted" style={{ fontSize: 11, marginLeft: 4 }}>
                      {relativeTime(s.created_at)}
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="detail-section">
              <div className="detail-label">Exit Analysis</div>
              {edgeDecay ? (
                <>
                  <div className="metric-row">
                    <span className="metric-label">Avg Decay Rate</span>
                    <span className="metric-value">
                      {edgeDecay.avg_decay_rate != null
                        ? `${(edgeDecay.avg_decay_rate * 100).toFixed(2)}%/hr`
                        : '\u2014'}
                    </span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Time to Zero Edge</span>
                    <span className="metric-value">
                      {edgeDecay.time_to_zero_edge != null
                        ? `${edgeDecay.time_to_zero_edge.toFixed(1)}h`
                        : '\u2014'}
                    </span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Round-Trip Cost</span>
                    <span className="metric-value">
                      {edgeDecay.round_trip_cost != null
                        ? pct(edgeDecay.round_trip_cost)
                        : '\u2014'}
                    </span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Verdict</span>
                    <span className="metric-value" style={{ fontWeight: 600 }}>
                      {edgeDecay.verdict ?? '\u2014'}
                    </span>
                  </div>
                </>
              ) : (
                <span className="loading-text">Loading...</span>
              )}
            </div>
          </div>
        </div>
      </td>
    </tr>
  )
}
