import { useState } from "react";
import type { AgentDecisionMsg, IndicatorUpdate, Prediction } from "./types";
import { useHexData } from "./hooks/useHexData";
import { HexMap } from "./components/HexMap";

export default function App() {
  const [decisions, _setDecisions] = useState<AgentDecisionMsg[]>([]);
  const [_indicators, _setIndicators] = useState<IndicatorUpdate | null>(null);
  const [_predictions, _setPredictions] = useState<Prediction[]>([]);
  const { getData, revision } = useHexData();

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "280px 1fr 320px",
        gridTemplateRows: "48px 1fr 180px",
        height: "100vh",
        background: "#0a0e1a",
        color: "#e2e8f0",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top bar */}
      <header
        style={{
          gridColumn: "1 / -1",
          background: "#0f1629",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #1e293b",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "#60a5fa", fontWeight: 700, fontSize: 15 }}>
            PARALLAX
          </span>
          <span style={{ fontSize: 12, color: "#f59e0b" }}>LIVE</span>
          <span style={{ fontSize: 12, color: "#94a3b8" }}>
            Iran/Hormuz Scenario
          </span>
        </div>
      </header>

      {/* Left: Agent feed */}
      <aside
        style={{
          background: "#0f1629",
          padding: 12,
          overflowY: "auto",
          borderRight: "1px solid #1e293b",
        }}
      >
        <div
          style={{
            color: "#94a3b8",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 1,
            marginBottom: 12,
          }}
        >
          Agent Activity
        </div>
        {decisions.length === 0 && (
          <p style={{ color: "#475569", fontSize: 13 }}>Waiting for events...</p>
        )}
      </aside>

      {/* Center: Map */}
      <main
        style={{
          background: "#0a0e1a",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <HexMap getData={getData} revision={revision} />
      </main>

      {/* Right: Indicators */}
      <aside
        style={{
          background: "#0f1629",
          padding: 12,
          overflowY: "auto",
          borderLeft: "1px solid #1e293b",
        }}
      >
        <div
          style={{
            color: "#94a3b8",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 1,
            marginBottom: 12,
          }}
        >
          Live Indicators
        </div>
        <p style={{ color: "#475569", fontSize: 13 }}>No data yet</p>
      </aside>

      {/* Bottom: Timeline + Predictions */}
      <footer
        style={{
          gridColumn: "1 / -1",
          background: "#0f1629",
          padding: 12,
          borderTop: "1px solid #1e293b",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <p style={{ color: "#475569", fontSize: 13 }}>Timeline + Predictions</p>
      </footer>
    </div>
  );
}
