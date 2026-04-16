import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { colors } from '../lib/colors'
import type { PricePoint, PredictionPoint } from '../types'

interface PriceChartProps {
  prices: PricePoint[]
  predictions?: PredictionPoint[]
}

interface ChartDatum {
  date: string
  market: number | null
  model: number | null
}

function mergeData(prices: PricePoint[], predictions?: PredictionPoint[]): ChartDatum[] {
  const map = new Map<string, ChartDatum>()

  for (const p of prices) {
    const date = p.fetched_at.slice(0, 10)
    const existing = map.get(date)
    map.set(date, {
      date,
      market: p.yes_price ?? existing?.market ?? null,
      model: existing?.model ?? null,
    })
  }

  if (predictions) {
    for (const p of predictions) {
      const date = p.created_at.slice(0, 10)
      const existing = map.get(date)
      map.set(date, {
        date: existing?.date ?? date,
        market: existing?.market ?? null,
        model: p.probability,
      })
    }
  }

  return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date))
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(0)}%`
}

export function PriceChart({ prices, predictions }: PriceChartProps) {
  if (prices.length === 0) {
    return (
      <div className="equity-chart">
        <span className="loading-text">No price data</span>
      </div>
    )
  }

  const data = mergeData(prices, predictions)

  return (
    <div className="equity-chart">
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <XAxis
            dataKey="date"
            tick={{ fill: colors.muted, fontSize: 10 }}
            axisLine={{ stroke: colors.border }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1]}
            tickFormatter={formatPct}
            tick={{ fill: colors.muted, fontSize: 10 }}
            axisLine={{ stroke: colors.border }}
            tickLine={false}
            width={36}
          />
          <Tooltip
            contentStyle={{
              background: colors.surface,
              border: `1px solid ${colors.border}`,
              borderRadius: 4,
              fontSize: 11,
            }}
            labelStyle={{ color: colors.subtle }}
            formatter={(value: number) => formatPct(value)}
          />
          <Line
            type="monotone"
            dataKey="market"
            stroke={colors.indigo}
            strokeWidth={2}
            dot={false}
            connectNulls
            name="Market"
          />
          <Line
            type="monotone"
            dataKey="model"
            stroke={colors.green}
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={false}
            connectNulls
            name="Model"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
