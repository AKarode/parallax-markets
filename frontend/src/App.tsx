import { usePolling } from './hooks/usePolling'
import { KpiBar } from './components/KpiBar'
import { ModelCards } from './components/ModelCards'
import { MarketsTable } from './components/MarketsTable'
import { ModelHealth } from './components/ModelHealth'
import { PortfolioPanel } from './components/PortfolioPanel'
import { OpsFooter } from './components/OpsFooter'
import type {
  HealthResponse,
  PredictionsResponse,
  MarketsResponse,
  DivergencesResponse,
  ScorecardMetrics,
  ContractsResponse,
  PredictionHistoryResponse,
  PortfolioState,
  LatestSignalsResponse,
} from './types'

export function App() {
  const health = usePolling<HealthResponse>('/api/health')
  const predictions = usePolling<PredictionsResponse>('/api/predictions')
  const markets = usePolling<MarketsResponse>('/api/markets')
  const divergences = usePolling<DivergencesResponse>('/api/divergences')
  const scorecard = usePolling<ScorecardMetrics>('/api/scorecard')
  const contracts = usePolling<ContractsResponse>('/api/contracts')
  const predictionHistory = usePolling<PredictionHistoryResponse>('/api/prediction-history')
  const portfolio = usePolling<PortfolioState>('/api/portfolio')
  const latestSignals = usePolling<LatestSignalsResponse>('/api/latest-signals')

  return (
    <div className="dashboard">
      <KpiBar
        health={health.data}
        portfolio={portfolio.data}
        scorecard={scorecard.data}
        divergences={divergences.data}
        latestSignals={latestSignals.data}
      />

      <ModelCards
        predictions={predictions.data}
        predictionHistory={predictionHistory.data}
        scorecard={scorecard.data}
      />

      <MarketsTable
        divergences={divergences.data}
        markets={markets.data}
        contracts={contracts.data}
        predictions={predictions.data}
        predictionHistory={predictionHistory.data}
        latestSignals={latestSignals.data}
      />

      <div className="two-col">
        <ModelHealth scorecard={scorecard.data} />
        <PortfolioPanel portfolio={portfolio.data} />
      </div>

      <OpsFooter
        health={health.data}
        scorecard={scorecard.data}
        lastUpdated={health.lastUpdated}
      />
    </div>
  )
}
