import type { PortfolioState } from '../types'
import { usd, signedUsd, signedPct, pct, shortDate } from '../lib/format'
import { colors } from '../lib/colors'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface PortfolioPanelProps {
  portfolio: PortfolioState | null
}

function pnlColor(value: number | null | undefined): string {
  if (value == null) return colors.muted
  return value >= 0 ? colors.green : colors.red
}

export function PortfolioPanel({ portfolio }: PortfolioPanelProps) {
  if (portfolio == null) {
    return <div className="loading-text">Loading portfolio...</div>
  }

  const returnPct = portfolio.portfolio_return_pct
  const positions = portfolio.positions ?? []
  const closedTrades = portfolio.closed_trades ?? []
  const equityCurve = portfolio.equity_curve ?? []

  return (
    <div>
      <div className="section-label">PORTFOLIO</div>

      {/* Summary Row */}
      <div className="portfolio-summary">
        <div className="portfolio-cell">
          <div className="kpi-label">Value</div>
          <div className="kpi-value" style={{ color: pnlColor(returnPct) }}>
            {usd(portfolio.portfolio_value)}{' '}
            <span style={{ fontSize: '0.8em' }}>
              {signedPct(returnPct != null ? returnPct * 100 : null)}
            </span>
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Cash</div>
          <div className="kpi-value">
            {usd(portfolio.cash)}{' '}
            <span className="c-subtle" style={{ fontSize: '0.8em' }}>
              {pct(portfolio.cash_pct, 0)}
            </span>
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Deployed</div>
          <div className="kpi-value">
            {usd(portfolio.deployed)}{' '}
            <span className="c-subtle" style={{ fontSize: '0.8em' }}>
              {positions.length} pos
            </span>
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Max Drawdown</div>
          <div className="kpi-value" style={{ color: colors.red }}>
            {pct(portfolio.max_drawdown_pct, 1)}
          </div>
        </div>
        <div className="portfolio-cell">
          <div className="kpi-label">Sharpe</div>
          <div className="kpi-value">
            {portfolio.sharpe != null ? portfolio.sharpe.toFixed(2) : '\u2014'}
          </div>
        </div>
      </div>

      {/* Equity Curve */}
      {equityCurve.length >= 2 && (
        <div className="equity-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={equityCurve} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
              <XAxis
                dataKey="date"
                tickFormatter={(v: string) => shortDate(v)}
                tick={{ fill: colors.dim, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tickFormatter={(v: number) => `$${v}`}
                tick={{ fill: colors.dim, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={50}
              />
              <Tooltip
                contentStyle={{ backgroundColor: colors.surface, border: `1px solid ${colors.border}`, fontSize: 12 }}
                labelFormatter={(v: string) => shortDate(v)}
                formatter={(v: number) => [usd(v), 'Value']}
              />
              <ReferenceLine y={1000} stroke={colors.dim} strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="value"
                stroke={colors.green}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Open Positions Table */}
      {positions.length > 0 && (
        <>
          <div className="section-label" style={{ marginTop: '0.75rem' }}>OPEN POSITIONS</div>
          <table className="positions-table">
            <thead>
              <tr>
                <th>Contract</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Current</th>
                <th>Notional</th>
                <th>Unreal P&amp;L</th>
                <th>Weight</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <tr key={`${pos.ticker}-${pos.side}`}>
                  <td>{pos.ticker}</td>
                  <td>{pos.side}</td>
                  <td>{pos.quantity}</td>
                  <td>{(pos.entry_price * 100).toFixed(0)}\u00a2</td>
                  <td>{pos.current_price != null ? `${(pos.current_price * 100).toFixed(0)}\u00a2` : '\u2014'}</td>
                  <td>{usd(pos.notional)}</td>
                  <td style={{ color: pnlColor(pos.unrealized_pnl) }}>
                    {signedUsd(pos.unrealized_pnl)}
                  </td>
                  <td>{pct(pos.weight_pct, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Closed Trades Table */}
      {closedTrades.length > 0 && (
        <>
          <div className="section-label" style={{ marginTop: '0.75rem' }}>CLOSED TRADES</div>
          <table className="positions-table">
            <thead>
              <tr>
                <th>Contract</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P&amp;L</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              {closedTrades.map((trade, i) => (
                <tr key={`${trade.ticker}-${trade.side}-${i}`}>
                  <td>{trade.ticker}</td>
                  <td>{trade.side}</td>
                  <td>{trade.quantity}</td>
                  <td>{(trade.entry_price * 100).toFixed(0)}\u00a2</td>
                  <td>{(trade.exit_price * 100).toFixed(0)}\u00a2</td>
                  <td style={{ color: pnlColor(trade.pnl) }}>
                    {signedUsd(trade.pnl)}
                  </td>
                  <td style={{ color: pnlColor(trade.return_pct) }}>
                    {signedPct(trade.return_pct * 100)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Risk Footer */}
      <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.75rem' }}>
        <div className="ops-cell">
          <span className="detail-label">Max Concentration</span>{' '}
          {pct(portfolio.max_concentration_pct, 1)} / 25%
        </div>
        <div className="ops-cell">
          <span className="detail-label">Win Rate</span>{' '}
          {pct(portfolio.win_rate, 0)}
        </div>
        <div className="ops-cell">
          <span className="detail-label">Total Fees</span>{' '}
          {usd(portfolio.total_fees)}
        </div>
        <div className="ops-cell">
          <span className="detail-label">Days Remaining</span>{' '}
          {portfolio.days_remaining ?? '\u2014'}
        </div>
      </div>
    </div>
  )
}
