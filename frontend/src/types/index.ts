export interface HexCell {
  cellId: string;
  influence: string | null;
  threatLevel: number;
  flow: number;
  status: "open" | "restricted" | "blocked" | "mined" | "patrolled";
}

export interface AgentDecisionMsg {
  decisionId: string;
  agentId: string;
  tick: number;
  actionType: string;
  description: string;
  confidence: number;
  createdAt: string;
}

export interface IndicatorUpdate {
  oilPrice: number;
  oilPriceChange: number;
  hormuzTraffic: number;
  hormuzTrafficChange: number;
  bypassUtilization: number;
  bypassCapacity: number;
  escalationLevel: number; // 0-4
}

export interface Prediction {
  predictionId: string;
  agentId: string;
  predictionType: string;
  direction: string;
  magnitudeRange: [number, number];
  confidence: number;
  timeframe: string;
}

export type WsMessage =
  | { type: "cell_update"; cells: HexCell[] }
  | { type: "agent_decision"; decision: AgentDecisionMsg }
  | { type: "indicator_update"; indicators: IndicatorUpdate }
  | { type: "event"; event: { summary: string; timestamp: string } };
