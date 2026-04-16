import { Fragment, useState } from 'react'
import { pct, edge } from '../lib/format'
import { ContractDetail } from './ContractDetail'
import type {
  DivergencesResponse,
  MarketsResponse,
  ContractsResponse,
  PredictionsResponse,
  PredictionHistoryResponse,
  LatestSignalsResponse,
  ContractInfo,
} from '../types'

interface MarketsTableProps {
  divergences: DivergencesResponse | null
  markets: MarketsResponse | null
  contracts: ContractsResponse | null
  predictions: PredictionsResponse | null
  predictionHistory: PredictionHistoryResponse | null
  latestSignals?: LatestSignalsResponse | null
}

function signalBadgeClass(signal: string): string {
  switch (signal) {
    case 'BUY_YES': return 'badge badge-buy-yes'
    case 'BUY_NO': return 'badge badge-buy-no'
    default: return 'badge badge-hold'
  }
}

function proxyBadgeClass(proxy: string | null): string {
  switch (proxy) {
    case 'DIRECT': case 'direct': return 'badge badge-direct'
    case 'NEAR_PROXY': case 'near_proxy': return 'badge badge-near'
    case 'LOOSE_PROXY': case 'loose_proxy': return 'badge badge-loose'
    default: return 'badge badge-loose'
  }
}

function proxyLabel(proxy: string | null): string {
  if (!proxy) return ''
  const upper = proxy.toUpperCase()
  switch (upper) {
    case 'DIRECT': return 'DIRECT'
    case 'NEAR_PROXY': return 'NEAR'
    case 'LOOSE_PROXY': return 'LOOSE'
    default: return upper
  }
}

function rowClass(signal: string, isExpanded: boolean): string {
  const parts: string[] = []
  if (signal === 'BUY_YES' || signal === 'BUY_NO') parts.push('active-signal')
  else parts.push('hold-signal')
  if (isExpanded) parts.push('expanded')
  return parts.join(' ')
}

function edgeColorClass(edgeVal: number | null): string {
  if (edgeVal == null) return 'c-muted'
  return edgeVal >= 0 ? 'c-green' : 'c-red'
}

// Unified row shape for both divergences and latest-signals
interface TableRow {
  ticker: string
  title: string
  marketPrice: number | null
  modelPrice: number | null
  edgeValue: number
  proxy: string | null
  signal: string
  volume: number | null
  reasoning: string | null
}

export function MarketsTable({
  divergences,
  markets,
  contracts,
  latestSignals,
}: MarketsTableProps) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)

  const contractMap = new Map<string, ContractInfo>()
  if (contracts) {
    for (const c of contracts.contracts) {
      contractMap.set(c.ticker, c)
    }
  }

  // Build rows: prefer divergences, fall back to latestSignals
  let rows: TableRow[] = []

  const hasDivergences = divergences && divergences.divergences.length > 0

  if (hasDivergences) {
    rows = divergences.divergences.map(d => {
      const ticker = d.market_price?.ticker ?? d.model_id
      const contract = contractMap.get(ticker)
      return {
        ticker,
        title: contract?.title ?? ticker,
        marketPrice: d.market_probability,
        modelPrice: d.model_probability,
        edgeValue: d.edge ?? 0,
        proxy: contract?.best_proxy ?? null,
        signal: d.signal,
        volume: d.market_price?.volume ?? null,
        reasoning: d.prediction?.reasoning ?? null,
      }
    })
  } else if (latestSignals && latestSignals.signals.length > 0) {
    rows = latestSignals.signals.map(s => {
      const contract = contractMap.get(s.contract_ticker)
      return {
        ticker: s.contract_ticker,
        title: contract?.title ?? s.contract_ticker,
        marketPrice: s.market_yes_price,
        modelPrice: s.model_probability,
        edgeValue: s.effective_edge,
        proxy: s.proxy_class ?? contract?.best_proxy ?? null,
        signal: s.signal,
        volume: s.market_volume,
        reasoning: s.model_reasoning,
      }
    })
  }

  // Sort by absolute edge descending
  rows.sort((a, b) => Math.abs(b.edgeValue) - Math.abs(a.edgeValue))

  if (rows.length === 0) {
    return (
      <div>
        <div className="section-label">Markets</div>
        <span className="loading-text">No signal data available</span>
      </div>
    )
  }

  return (
    <div>
      <div className="section-label">Markets</div>
      <table className="markets-table">
        <thead>
          <tr>
            <th>Contract</th>
            <th>Market%</th>
            <th>Model%</th>
            <th>Edge</th>
            <th>Proxy</th>
            <th>Signal</th>
            <th>Volume</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const isExpanded = expandedTicker === row.ticker
            const contract = contractMap.get(row.ticker)

            return (
              <Fragment key={row.ticker}>
                <tr
                  className={rowClass(row.signal, isExpanded)}
                  onClick={() => setExpandedTicker(isExpanded ? null : row.ticker)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <div style={{ fontWeight: 500 }}>{row.ticker}</div>
                    <div className="c-subtle" style={{ fontSize: 11 }}>{row.title}</div>
                  </td>
                  <td>{pct(row.marketPrice)}</td>
                  <td>{pct(row.modelPrice)}</td>
                  <td className={edgeColorClass(row.edgeValue)}>{edge(row.edgeValue)}</td>
                  <td>
                    {row.proxy && (
                      <span className={proxyBadgeClass(row.proxy)}>
                        {proxyLabel(row.proxy)}
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={signalBadgeClass(row.signal)}>{row.signal.replace('_', ' ')}</span>
                  </td>
                  <td className="c-muted">{row.volume?.toFixed(0) ?? '\u2014'}</td>
                  <td>
                    <span className={isExpanded ? 'expand-arrow open' : 'expand-arrow'}>&#x25B8;</span>
                  </td>
                </tr>
                {isExpanded && contract && (
                  <ContractDetail
                    contract={contract}
                    divergence={null}
                    market={null}
                  />
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
