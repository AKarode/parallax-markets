"""Streamlit single-page dashboard for Parallax intelligence system.

Displays 4 expandable sections:
1. Today's Brief -- latest prediction model outputs
2. Track Record / Calibration -- calibration curves and hit rates
3. Signal History -- recent signal ledger entries
4. Market Prices -- latest fetched market prices

Connects to DuckDB in read-only mode (T-03-04) to prevent accidental writes.

Usage:
    streamlit run backend/src/parallax/dashboard/app.py
"""

from __future__ import annotations

import os

import duckdb
import streamlit as st

from parallax.dashboard.data import (
    get_calibration_data,
    get_latest_brief,
    get_market_prices,
    get_signal_history,
)


def main() -> None:
    """Render the Parallax Intelligence Dashboard."""
    st.set_page_config(page_title="Parallax Dashboard", layout="wide")
    st.title("Parallax Intelligence Dashboard")

    db_path = os.environ.get("DUCKDB_PATH", "data/parallax.duckdb")
    try:
        conn = duckdb.connect(db_path, read_only=True)
    except Exception as e:
        st.error(f"Cannot connect to DuckDB: {e}")
        return

    with st.expander("Today's Brief", expanded=True):
        brief = get_latest_brief(conn)
        if brief:
            for pred in brief:
                st.markdown(
                    f"**{pred['model_id']}**: {pred['probability']:.0%} "
                    f"{pred['direction']} (confidence: {pred['confidence']:.0%})"
                )
                st.caption((pred.get("reasoning") or "")[:200])
        else:
            st.info("No predictions yet. Run the pipeline first.")

    with st.expander("Track Record / Calibration"):
        cal = get_calibration_data(conn)
        if cal["calibration_curve"]:
            try:
                import plotly.graph_objects as go

                fig = go.Figure()
                buckets = cal["calibration_curve"]
                fig.add_trace(
                    go.Bar(
                        x=[b["bucket"] for b in buckets],
                        y=[b["avg_predicted"] for b in buckets],
                        name="Predicted",
                    )
                )
                fig.add_trace(
                    go.Bar(
                        x=[b["bucket"] for b in buckets],
                        y=[b["actual_rate"] for b in buckets],
                        name="Actual",
                    )
                )
                fig.update_layout(title="Calibration Curve", barmode="group")
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.warning("Install plotly for calibration charts: pip install plotly")
        if cal["hit_rate"]:
            st.dataframe(cal["hit_rate"])

    with st.expander("Signal History"):
        signals = get_signal_history(conn)
        if signals:
            st.dataframe(signals)
        else:
            st.info("No signals recorded yet.")

    with st.expander("Market Prices"):
        prices = get_market_prices(conn)
        if prices:
            st.dataframe(prices)
        else:
            st.info("No market prices fetched yet.")


if __name__ == "__main__":
    main()
