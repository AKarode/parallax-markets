import { Fragment, useState } from 'react'
import { pct, edge } from '../lib/format'
import { ContractDetail } from './ContractDetail'
import type {
  DivergencesResponse,
  MarketsResponse,
  ContractsResponse,
  PredictionsResponse,
  PredictionHistoryResponse,
  Divergence,
  ContractInfo,
  MarketData,
} from '../types'

interface MarketsTableProps {
  divergences: DivergencesResponse | null
  markets: MarketsResponse | null
  contracts: ContractsResponse | null
  predictions: PredictionsResponse | null
  predictionHistory: PredictionHistoryResponse | null
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
    case 'DIRECT': return 'badge badge-direct'
    case 'NEAR_PROXY': return 'badge badge-near'
    case 'LOOSE_PROXY': return 'badge badge-loose'
    default: return 'badge badge-loose'
  }
}

function proxyLabel(proxy: string | null): string {
  switch (proxy) {
    case 'DIRECT': return 'DIRECT'
    case 'NEAR_PROXY': return 'NEAR'
    case 'LOOSE_PROXY': return 'LOOSE'
    default: return proxy ?? ''
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

export function MarketsTable({
  divergences,
  markets,
  contracts,
}: MarketsTableProps) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)

  if (!divergences || divergences.divergences.length === 0) {
    return (
      <div>
        <div className="section-label">Markets</div>
        <span className="loading-text">No divergences available</span>
      </div>
    )
  }

  const marketMap = new Map<string, MarketData>()
  if (markets) {
    for (const m of markets.markets) {
      marketMap.set(m.ticker, m)
    }
  }

  const contractMap = new Map<string, ContractInfo>()
  if (contracts) {
    for (const c of contracts.contracts) {
      contractMap.set(c.ticker, c)
    }
  }

  const sorted = [...divergences.divergences].sort((a, b) => {
    const absA = Math.abs(a.edge ?? 0)
    const absB = Math.abs(b.edge ?? 0)
    return absB - absA
  })

  function getTicker(d: Divergence): string {
    return d.market_price?.ticker ?? d.model_id
  }

  function toggleExpand(ticker: string) {
    setExpandedTicker((prev) => (prev === ticker ? null : ticker))
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
          {sorted.map((d) => {
            const ticker = getTicker(d)
            const market = marketMap.get(ticker) ?? d.market_price ?? null
            const contract = contractMap.get(ticker)
            const isExpanded = expandedTicker === ticker

            return (
              <Fragment key={ticker}>
                <tr
                  className={rowClass(d.signal, isExpanded)}
                  onClick={() => toggleExpand(ticker)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <div style={{ fontWeight: 500 }}>{ticker}</div>
                    {contract && (
                      <div className="c-subtle" style={{ fontSize: 11 }}>
                        {contract.title}
                      </div>
                    )}
                  </td>
                  <td>{pct(d.market_probability)}</td>
                  <td>{pct(d.model_probability)}</td>
                  <td className={edgeColorClass(d.edge)}>{edge(d.edge)}</td>
                  <td>
                    {contract?.best_proxy ? (
                      <span className={proxyBadgeClass(contract.best_proxy)}>
                        {proxyLabel(contract.best_proxy)}
                      </span>
                    ) : null}
                  </td>
                  <td>
                    <span className={signalBadgeClass(d.signal)}>{d.signal}</span>
                  </td>
                  <td className="c-muted">{market?.volume ?? '\u2014'}</td>
                  <td>
                    <span className={isExpanded ? 'expand-arrow open' : 'expand-arrow'}>
                      &#x25B8;
                    </span>
                  </td>
                </tr>
                {isExpanded && contract && (
                  <ContractDetail
                    contract={contract}
                    divergence={d}
                    market={market}
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
