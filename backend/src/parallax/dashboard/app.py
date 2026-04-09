"""Parallax Intelligence Dashboard.

Dark trading terminal aesthetic matching karode.dev.
Dense, functional, screenshot-worthy.

Usage:
    streamlit run backend/src/parallax/dashboard/app.py
"""

from __future__ import annotations

import os

import duckdb
import plotly.graph_objects as go
import streamlit as st

from parallax.dashboard.data import get_latest_brief, get_signal_history

# ── Palette ──────────────────────────────────────────────
BG = "#09090b"
SURFACE = "#111113"
BORDER = "#1c1c1f"
MUTED = "#52525b"
SUBTLE = "#71717a"
TEXT = "#e4e4e7"
WHITE = "#fafafa"
GREEN = "#22c55e"
RED = "#ef4444"
AMBER = "#f59e0b"
INDIGO = "#818cf8"
PURPLE = "#a78bfa"
CYAN = "#22d3ee"

# ── Plotly shared config ────────────────────────────────
_PL = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=SUBTLE, size=10),
    margin=dict(l=40, r=12, t=24, b=32),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=9)),
    hoverlabel=dict(bgcolor=SURFACE, font_color=TEXT, bordercolor=BORDER, font_size=11),
)
_AX = dict(gridcolor="#1a1a1e", showline=False, tickfont=dict(size=9))
_AX_Z = dict(**_AX, zeroline=True, zerolinecolor="#27272a", zerolinewidth=1)


def _css() -> None:
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg: #09090b; --surface: #111113; --border: #1c1c1f;
        --muted: #52525b; --subtle: #71717a; --text: #e4e4e7; --white: #fafafa;
        --green: #22c55e; --red: #ef4444; --indigo: #818cf8; --purple: #a78bfa; --cyan: #22d3ee;
    }

    #MainMenu, footer, header, div[data-testid="stDecoration"],
    div[data-testid="stToolbar"] { display:none!important; }

    .stApp { background: var(--bg); color: var(--text); }
    .block-container { padding: 1.2rem 2rem 2rem; max-width: 1200px; }

    /* ── Header ── */
    .hdr { display:flex; align-items:baseline; gap:0.75rem; margin-bottom:0.15rem; }
    .hdr-title {
        font-family: 'Instrument Sans', sans-serif; font-size: 1.5rem;
        font-weight: 700; color: var(--white); letter-spacing: -0.02em;
    }
    .hdr-live {
        font-family: 'JetBrains Mono', monospace; font-size: 0.6rem;
        color: var(--green); letter-spacing: 0.05em; text-transform: uppercase;
        display:flex; align-items:center; gap:0.3rem;
    }
    .hdr-live::before {
        content:''; width:5px; height:5px; border-radius:50%;
        background:var(--green); display:inline-block;
        box-shadow: 0 0 6px var(--green);
    }
    .hdr-sub {
        font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
        color: var(--muted); margin-bottom: 1rem;
    }

    /* ── Section labels ── */
    .lbl {
        font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; font-weight: 500;
        letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted);
        margin-bottom: 0.5rem; padding-bottom:0.3rem; border-bottom: 1px solid var(--border);
    }

    /* ── Prediction strip ── */
    .pred-strip { display:flex; gap:0.5rem; margin-bottom:0.15rem; }
    .pred {
        flex:1; background:var(--surface); border:1px solid var(--border);
        border-radius:8px; padding:0.65rem 0.8rem; position:relative; overflow:hidden;
    }
    .pred::after {
        content:''; position:absolute; top:0; left:0; right:0; height:2px;
    }
    .pred-up::after { background: linear-gradient(90deg, var(--green), transparent); }
    .pred-dn::after { background: linear-gradient(90deg, var(--red), transparent); }
    .pred-st::after { background: linear-gradient(90deg, var(--indigo), transparent); }
    .pred-name {
        font-family: 'JetBrains Mono', monospace; font-size:0.55rem;
        letter-spacing:0.08em; text-transform:uppercase; color:var(--subtle);
    }
    .pred-row { display:flex; align-items:baseline; gap:0.4rem; margin-top:0.2rem; }
    .pred-pct { font-family:'Instrument Sans',sans-serif; font-size:1.6rem; font-weight:700; line-height:1; }
    .pred-dir { font-family:'Instrument Sans',sans-serif; font-size:0.7rem; color:var(--subtle); }
    .pred-why {
        font-family:'Instrument Sans',sans-serif; font-size:0.65rem;
        color:#3f3f46; line-height:1.35; margin-top:0.3rem;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }
    .cg { color:var(--green); } .cr { color:var(--red); } .ci { color:var(--indigo); }

    /* ── Stat pills ── */
    .stats { display:flex; gap:0.4rem; margin-bottom:0.15rem; }
    .st-pill {
        flex:1; background:var(--surface); border:1px solid var(--border);
        border-radius:8px; padding:0.5rem 0.6rem; text-align:center;
    }
    .st-v {
        font-family:'Instrument Sans',sans-serif; font-size:1.15rem;
        font-weight:700; color:var(--white);
    }
    .st-l {
        font-family:'JetBrains Mono',monospace; font-size:0.5rem;
        letter-spacing:0.1em; text-transform:uppercase; color:var(--muted); margin-top:0.1rem;
    }

    /* ── Signal table ── */
    .s-hdr {
        display:flex; padding:0.3rem 0; border-bottom:1px solid var(--border);
        font-family:'JetBrains Mono',monospace; font-size:0.55rem; font-weight:500;
        letter-spacing:0.08em; text-transform:uppercase; color:#3f3f46;
    }
    .s-row {
        display:flex; align-items:center; padding:0.4rem 0;
        border-bottom:1px solid #18181b; font-size:0.78rem;
    }
    .s-row:hover { background: rgba(255,255,255,0.015); }
    .s-tk { font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#d4d4d8; flex:2.2; display:flex; flex-direction:column; }
    .s-tk-desc { font-family:'Instrument Sans',sans-serif; font-size:0.6rem; color:#3f3f46; margin-top:0.1rem; font-style:normal; }
    .s-md { font-family:'Instrument Sans',sans-serif; color:var(--subtle); flex:1.1; }
    .s-eg {
        font-family:'JetBrains Mono',monospace; font-size:0.7rem;
        flex:0.6; text-align:right;
    }

    /* ── Badges ── */
    .bg {
        display:inline-block; padding:0.1rem 0.4rem; border-radius:9999px;
        font-family:'JetBrains Mono',monospace; font-size:0.58rem; font-weight:500;
    }
    .bg-y { background:rgba(34,197,94,0.1); color:var(--green); border:1px solid rgba(34,197,94,0.18); }
    .bg-n { background:rgba(239,68,68,0.1); color:var(--red); border:1px solid rgba(239,68,68,0.18); }
    .bg-r { background:rgba(113,113,122,0.1); color:var(--subtle); border:1px solid rgba(113,113,122,0.15); }
    .px {
        display:inline-block; padding:0.08rem 0.35rem; border-radius:4px;
        font-family:'JetBrains Mono',monospace; font-size:0.55rem;
    }
    .px-d { background:rgba(129,140,248,0.1); color:var(--indigo); }
    .px-n { background:rgba(167,139,250,0.1); color:var(--purple); }
    .px-l { background:rgba(113,113,122,0.08); color:var(--muted); }

    /* ── Divider ── */
    .div { border:none; border-top:1px solid var(--border); margin:0.8rem 0; }

    /* ── Footer ── */
    .foot {
        display:flex; gap:1.2rem; font-family:'JetBrains Mono',monospace;
        font-size:0.6rem; color:#3f3f46; padding-top:0.4rem;
    }
    .foot-dot { width:4px; height:4px; border-radius:50%; display:inline-block; margin-right:0.25rem; }
    .fd-g { background:var(--green); box-shadow:0 0 4px var(--green); }
    .fd-m { background:var(--muted); }

    div[data-testid="column"] { padding: 0 0.3rem; }
    </style>""", unsafe_allow_html=True)


def _badge(signal: str) -> str:
    s = (signal or "").upper()
    if s == "BUY_YES": return '<span class="bg bg-y">BUY YES</span>'
    if s == "BUY_NO": return '<span class="bg bg-n">BUY NO</span>'
    return '<span class="bg bg-r">PASS</span>'


def _proxy(pc: str) -> str:
    p = (pc or "").lower()
    if p == "direct": return '<span class="px px-d">DIRECT</span>'
    if p == "near_proxy": return '<span class="px px-n">NEAR</span>'
    return '<span class="px px-l">LOOSE</span>'


# ── Queries ──────────────────────────────────────────────

def _summary(conn: duckdb.DuckDBPyConnection) -> dict:
    r = conn.execute("""
        SELECT COUNT(*),
            SUM(CASE WHEN signal='BUY_YES' THEN 1 ELSE 0 END),
            SUM(CASE WHEN signal='BUY_NO' THEN 1 ELSE 0 END),
            AVG(ABS(effective_edge)), MAX(ABS(effective_edge)),
            COUNT(DISTINCT contract_ticker),
            COUNT(DISTINCT model_id)
        FROM signal_ledger
    """).fetchone()
    if not r or r[0] is None:
        return {"total": 0, "act": 0, "avg": 0, "max": 0, "tickers": 0, "models": 0}
    return {
        "total": r[0], "act": (r[1] or 0) + (r[2] or 0),
        "avg": float(r[3] or 0), "max": float(r[4] or 0),
        "tickers": r[5] or 0, "models": r[6] or 0,
    }


def _edges(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = conn.execute("""
        SELECT proxy_class, effective_edge, signal, model_id, contract_ticker
        FROM signal_ledger WHERE signal != 'REFUSED' ORDER BY ABS(effective_edge) DESC
    """).fetchall()
    return [{"pc": r[0], "edge": float(r[1]), "sig": r[2], "model": r[3], "ticker": r[4]} for r in rows]


def _ticker_info(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Map ticker -> short human description from contract registry."""
    rows = conn.execute("""
        SELECT ticker, resolution_criteria FROM contract_registry
    """).fetchall()
    return {r[0]: (r[1] or "")[:60] for r in rows}


def _history(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = conn.execute("""
        SELECT model_id, probability, direction, created_at
        FROM prediction_log ORDER BY created_at
    """).fetchall()
    return [{"m": r[0], "p": float(r[1]), "d": r[2], "t": r[3]} for r in rows]


# ── Main ─────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="Parallax", layout="wide", initial_sidebar_state="collapsed")
    _css()

    db_path = os.environ.get("DUCKDB_PATH", "data/parallax.duckdb")
    try:
        conn = duckdb.connect(db_path, read_only=True)
    except Exception as e:
        st.markdown(f'<div style="color:{RED};padding:2rem;">Cannot connect: {e}</div>', unsafe_allow_html=True)
        return

    brief = get_latest_brief(conn)
    stats = _summary(conn)
    signals = get_signal_history(conn)
    tinfo = _ticker_info(conn)

    # ── Header ──
    st.markdown(f"""
    <div class="hdr"><span class="hdr-title">Parallax</span><span class="hdr-live">Live</span></div>
    <div class="hdr-sub">prediction market edge-finder &mdash; iran-hormuz crisis</div>
    """, unsafe_allow_html=True)

    # ── Predictions (horizontal strip) ──
    if brief:
        cards = ""
        for pred in brief:
            p = pred["probability"]
            d = pred["direction"]
            cls = "cg pred-up" if d == "increase" else ("cr pred-dn" if d == "decrease" else "ci pred-st")
            arrow = "&#8593;" if d == "increase" else ("&#8595;" if d == "decrease" else "&#8596;")
            name = pred["model_id"].replace("_", " ")
            why = (pred.get("reasoning") or "")[:90]
            cards += f"""<div class="pred {cls.split()[-1]}">
                <div class="pred-name">{name}</div>
                <div class="pred-row">
                    <span class="pred-pct {cls.split()[0]}">{p:.0%}</span>
                    <span class="pred-dir">{arrow} {d}</span>
                </div>
                <div class="pred-why">{why}</div>
            </div>"""
        st.markdown(f'<div class="pred-strip">{cards}</div>', unsafe_allow_html=True)

    # ── Stats pills ──
    st.markdown(f"""<div class="stats">
        <div class="st-pill"><div class="st-v">{stats["total"]}</div><div class="st-l">Signals</div></div>
        <div class="st-pill"><div class="st-v">{stats["act"]}</div><div class="st-l">Actionable</div></div>
        <div class="st-pill"><div class="st-v">{stats["avg"]:.1%}</div><div class="st-l">Avg Edge</div></div>
        <div class="st-pill"><div class="st-v">{stats["max"]:.1%}</div><div class="st-l">Max Edge</div></div>
        <div class="st-pill"><div class="st-v">{stats["tickers"]}</div><div class="st-l">Contracts</div></div>
        <div class="st-pill"><div class="st-v">{stats["models"]}</div><div class="st-l">Models</div></div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="div">', unsafe_allow_html=True)

    # ── Signal Ledger + Edge Chart ──
    col_l, col_r = st.columns([1.4, 1])

    with col_l:
        st.markdown('<div class="lbl">Signal Ledger</div>', unsafe_allow_html=True)
        if signals:
            st.markdown("""<div class="s-hdr">
                <span style="flex:2.2">Contract</span><span style="flex:1.1">Model</span>
                <span style="flex:0.7">Proxy</span><span style="flex:0.7">Signal</span>
                <span style="flex:0.6;text-align:right">Edge</span>
            </div>""", unsafe_allow_html=True)
            for sig in signals[:11]:
                e = sig["effective_edge"]
                ec = "cg" if e > 0 else "cr"
                es = f"+{e:.1%}" if e > 0 else f"{e:.1%}"
                desc = tinfo.get(sig['contract_ticker'], "")
                st.markdown(f"""<div class="s-row">
                    <span class="s-tk"><span>{sig['contract_ticker']}</span><span class="s-tk-desc">{desc}</span></span>
                    <span class="s-md">{sig['model_id'].replace('_',' ')}</span>
                    <span style="flex:0.7">{_proxy(sig['proxy_class'])}</span>
                    <span style="flex:0.7">{_badge(sig['signal'])}</span>
                    <span class="s-eg {ec}">{es}</span>
                </div>""", unsafe_allow_html=True)

    with col_r:
        # ── Edge waterfall chart ──
        st.markdown('<div class="lbl">Edge Analysis</div>', unsafe_allow_html=True)
        edges = _edges(conn)
        if edges:
            pc_colors = {"direct": INDIGO, "near_proxy": PURPLE, "loose_proxy": MUTED}
            fig = go.Figure()
            for pc in ["direct", "near_proxy", "loose_proxy"]:
                sub = [e for e in edges if e["pc"] == pc]
                if sub:
                    fig.add_trace(go.Bar(
                        y=[f"{e['ticker'][:12]}" for e in sub],
                        x=[e["edge"] * 100 for e in sub],
                        orientation="h",
                        name=pc.replace("_", " ").title(),
                        marker_color=pc_colors.get(pc, MUTED),
                        marker_line_width=0,
                        hovertemplate="%{y}<br>Edge: %{x:.1f}%<extra></extra>",
                    ))
            fig.update_layout(**_PL, barmode="group", height=250,
                              xaxis=dict(**_AX_Z, title="Edge %", title_font_size=9),
                              yaxis=dict(**_AX, autorange="reversed"))
            fig.add_vline(x=5, line_dash="dot", line_color="rgba(34,197,94,0.15)")
            fig.add_vline(x=-5, line_dash="dot", line_color="rgba(239,68,68,0.15)")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ── Prediction timeline ──
        hist = _history(conn)
        if hist and len(hist) > 1:
            st.markdown('<div class="lbl" style="margin-top:0.3rem;">Prediction Timeline</div>', unsafe_allow_html=True)
            fig2 = go.Figure()
            mc = {"ceasefire": GREEN, "oil_price": AMBER, "hormuz_reopening": CYAN}
            for model in ["ceasefire", "oil_price", "hormuz_reopening"]:
                sub = [h for h in hist if h["m"] == model]
                if sub:
                    fig2.add_trace(go.Scatter(
                        x=[h["t"] for h in sub], y=[h["p"] * 100 for h in sub],
                        name=model.replace("_", " ").title(),
                        mode="lines+markers",
                        line=dict(color=mc.get(model, SUBTLE), width=2, shape="spline"),
                        marker=dict(size=5),
                    ))
            fig2.update_layout(**_PL, height=160,
                               xaxis=dict(**_AX, tickformat="%H:%M"),
                               yaxis=dict(**_AX, range=[0, 100], title="Prob %", title_font_size=9))
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ── Footer ──
    st.markdown('<hr class="div">', unsafe_allow_html=True)
    last_run = brief[0]["created_at"] if brief else "—"
    sig_n = len(signals) if signals else 0
    st.markdown(f"""<div class="foot">
        <span><span class="foot-dot fd-g"></span>{len(brief) if brief else 0} models active</span>
        <span><span class="foot-dot fd-g"></span>{sig_n} signals tracked</span>
        <span><span class="foot-dot {'fd-g' if stats['act']>0 else 'fd-m'}"></span>{stats['act']} actionable</span>
        <span>last run {last_run}</span>
    </div>""", unsafe_allow_html=True)

    conn.close()


if __name__ == "__main__":
    main()
