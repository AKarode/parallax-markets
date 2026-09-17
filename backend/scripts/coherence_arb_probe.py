#!/usr/bin/env python3
"""Polymarket 2026-midterm Balance-of-Power coherence-arbitrage falsification probe.

This is the "Stage A" $0-capital falsification test from
docs/PROFITABILITY-STRATEGY-2026-06.md §9: the one structurally-sound,
forecasting-free thesis. It exploits *algebra*, not prediction.

Polymarket prices the "Balance of Power: 2026 Midterms" event as 4 mutually
exclusive joint outcomes (+ Other) that must sum to 1, and ALSO prices
standalone single-chamber control markets on the SAME venue / SAME resolution.
Two algebraic identities must therefore hold:

    P(D House)  == P(DemSweep) + P(R-Senate / D-House)
    P(D Senate) == P(DemSweep) + P(D-Senate / R-House)

When the standalone chamber market disagrees with the derived marginal beyond
the bid/ask spread, a riskless same-venue package exists. This probe polls the
order books every INTERVAL seconds, computes both identities in BOTH directions,
logs the net-of-spread gap and the top-of-book fillable size, and paper-trades a
pretend $1,000 bankroll whenever a genuinely fillable positive gap appears.

KILL CRITERION (the thesis is dead): over a full day, the violation NEVER
exceeds the spread at fillable size -> the book is already coherent (bots arb
it) and there is no edge for a slow cron operator. A clean null result is the
expected, and still valuable, outcome.

Self-contained: stdlib only (urllib + sqlite3). No project venv, no API keys,
no real orders. Polymarket reads are public.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

CLOB_BASE = "https://clob.polymarket.com"
UA = "Mozilla/5.0 (coherence-arb-probe; parallax research)"

# ---------------------------------------------------------------------------
# Leg definitions. token_id is the Polymarket CLOB asset id for that YES/NO leg.
# Captured 2026-06-04 from gamma-api events 32228 (BoP), 32224 (Senate), 32225 (House).
# YES = clobTokenIds[0], NO = clobTokenIds[1].
# ---------------------------------------------------------------------------
LEGS: dict[str, str] = {
    # Balance-of-Power joint outcomes (YES tokens)
    "dem_sweep_yes":   "34722410608062854697106861099776685947172185964394483545370684749662285977831",
    "dsen_rhouse_yes": "70997927349469817841862065582625658840347600365813612622959588796331622340305",
    "rsen_dhouse_yes": "6302359956133594764084277082169634158291609371270652093164054687145970756151",
    "rsweep_yes":      "103704141773947678931823410030956181918562062788486034785782641603149828893320",
    "other_yes":       "35477631289241705233759154026285946627439635224019448868888132647783862821489",
    # Standalone chamber-control markets
    "dhouse_yes":      "83247781037352156539108067944461291821683755894607244160607042790356561625563",
    "dhouse_no":       "33156410999665902694791064431724433042010245771106314074312009703157423879038",
    "dsen_yes":        "113287701564209339913693347405685749986285999146352375265161592243948562084773",
    "dsen_no":         "107118433685650702332040991454078902188473746599223732907923581436160160612542",
}

# Coherence checks. Each yields two riskless directions (cheap / rich).
# `synth_legs` are the YES joint outcomes whose union replicates the standalone
# chamber's YES payoff exactly (mutually exclusive + exhaustive within the event).
IDENTITIES = [
    {
        "name": "house",
        "standalone_yes": "dhouse_yes",
        "standalone_no": "dhouse_no",
        "synth_legs": ["dem_sweep_yes", "rsen_dhouse_yes"],
    },
    {
        "name": "senate",
        "standalone_yes": "dsen_yes",
        "standalone_no": "dsen_no",
        "synth_legs": ["dem_sweep_yes", "dsen_rhouse_yes"],
    },
]

# Paper-trading params
BANKROLL = 1000.0
# Minimum NET gap (in $/contract, after the politics taker fee) to act. 0.005 =
# half a cent of locked, riskless edge beyond all costs.
EDGE_THRESHOLD = 0.005

# Polymarket politics taker fee (verified 2026-06-04 against the live market
# feeSchedule {rate:0.04, takerOnly:True} and docs.polymarket.com/trading/fees):
#     fee_per_share = rate * price * (1 - price)
# Makers pay ZERO (and politics markets run a maker rebate/rewards program), so
# the maker path is modeled fee-free.
POLITICS_FEE_RATE = 0.04


def taker_fee(price: float) -> float:
    """Per-share Polymarket politics taker fee at a given execution price."""
    return POLITICS_FEE_RATE * price * (1.0 - price)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_book(token_id: str, timeout: float = 20.0) -> dict | None:
    """Return {'best_bid','bid_size','best_ask','ask_size'} or None on failure."""
    url = f"{CLOB_BASE}/book?token_id={token_id}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:  # noqa: BLE001
        print(f"  ! book fetch failed {token_id[:12]}…: {exc}", file=sys.stderr)
        return None

    bids = [(float(b["price"]), float(b["size"])) for b in data.get("bids", []) if b.get("price")]
    asks = [(float(a["price"]), float(a["size"])) for a in data.get("asks", []) if a.get("price")]
    best_bid = max(bids, key=lambda x: x[0]) if bids else (None, 0.0)
    best_ask = min(asks, key=lambda x: x[0]) if asks else (None, 0.0)
    return {
        "best_bid": best_bid[0],
        "bid_size": best_bid[1],
        "best_ask": best_ask[0],
        "ask_size": best_ask[1],
    }


def poll_all() -> dict[str, dict]:
    """Fetch books for every leg. Returns {leg_name: book_dict}."""
    snap: dict[str, dict] = {}
    for name, token in LEGS.items():
        book = fetch_book(token)
        if book is not None:
            snap[name] = book
        time.sleep(0.15)  # gentle on the public endpoint
    return snap


def compute_opportunities(snap: dict[str, dict]) -> list[dict]:
    """Compute net-of-spread riskless gaps for both identities, both directions."""
    opps: list[dict] = []
    for ident in IDENTITIES:
        sa_yes = snap.get(ident["standalone_yes"])
        sa_no = snap.get(ident["standalone_no"])
        synth_raw = [snap.get(leg) for leg in ident["synth_legs"]]
        if sa_yes is None or sa_no is None or any(s is None for s in synth_raw):
            continue
        synth: list[dict] = [s for s in synth_raw if s is not None]
        if any(s["best_bid"] is None or s["best_ask"] is None for s in synth):
            continue
        if sa_yes["best_ask"] is None or sa_yes["best_bid"] is None or sa_no["best_ask"] is None:
            continue

        # Maker mid-incoherence (fee-free best case for the doc's maker-only
        # thesis): how far the standalone chamber mid sits from the synthetic
        # mid. Signed so >0 => standalone rich, <0 => standalone cheap.
        def mid(b):
            return (b["best_bid"] + b["best_ask"]) / 2.0
        synth_mid_sum = sum(mid(s) for s in synth)
        incoherence_mid = mid(sa_yes) - synth_mid_sum

        # Direction CHEAP: standalone YES underpriced vs synthetic.
        # Taker: buy standalone YES @ ask, sell synthetic legs @ their bids.
        synth_bid_sum = sum(s["best_bid"] for s in synth)
        gross_cheap = synth_bid_sum - sa_yes["best_ask"]
        fee_cheap = taker_fee(sa_yes["best_ask"]) + sum(taker_fee(s["best_bid"]) for s in synth)
        fill_cheap = min([sa_yes["ask_size"]] + [s["bid_size"] for s in synth])

        # Direction RICH: standalone YES overpriced vs synthetic.
        # Taker: bundle {standalone NO + synthetic YES legs} pays exactly $1.
        synth_ask_sum = sum(s["best_ask"] for s in synth)
        gross_rich = 1.0 - (sa_no["best_ask"] + synth_ask_sum)
        fee_rich = taker_fee(sa_no["best_ask"]) + sum(taker_fee(s["best_ask"]) for s in synth)
        fill_rich = min([sa_no["ask_size"]] + [s["ask_size"] for s in synth])

        opps.append({
            "identity": ident["name"],
            "direction": "cheap",
            "gross_gap": round(gross_cheap, 4),
            "fee": round(fee_cheap, 4),
            "net_gap": round(gross_cheap - fee_cheap, 4),
            "maker_mid_gap": round(-incoherence_mid, 4),  # cheap profits when standalone cheap
            "fillable_size": fill_cheap,
            "legs": {
                "buy_standalone_yes@ask": sa_yes["best_ask"],
                **{f"sell_{leg}@bid": s["best_bid"] for leg, s in zip(ident["synth_legs"], synth)},
            },
        })
        opps.append({
            "identity": ident["name"],
            "direction": "rich",
            "gross_gap": round(gross_rich, 4),
            "fee": round(fee_rich, 4),
            "net_gap": round(gross_rich - fee_rich, 4),
            "maker_mid_gap": round(incoherence_mid, 4),  # rich profits when standalone rich
            "fillable_size": fill_rich,
            "legs": {
                "buy_standalone_no@ask": sa_no["best_ask"],
                **{f"buy_{leg}@ask": s["best_ask"] for leg, s in zip(ident["synth_legs"], synth)},
            },
        })
    return opps


class PaperBook:
    """Pretend $1,000 bankroll. Locks riskless packages when a fillable gap appears."""

    def __init__(self, db: sqlite3.Connection, bankroll: float = BANKROLL):
        self.db = db
        self.cash = bankroll
        self.deployed = 0.0          # capital tied up in open arb packages
        self.locked_profit = 0.0     # guaranteed profit from filled packages
        self.open_keys: set[str] = set()  # (identity,direction) currently held

    def maybe_trade(self, opp: dict, ts: str) -> None:
        key = f"{opp['identity']}:{opp['direction']}"
        # Trade only a genuinely riskless taker lock NET of the politics fee.
        if opp["net_gap"] < EDGE_THRESHOLD:
            self.open_keys.discard(key)  # dislocation closed; free to re-enter later
            return
        if opp["fillable_size"] <= 0:
            return
        if key in self.open_keys:
            return  # already holding this dislocation; don't double-count

        # Cost per package to acquire the $1-guaranteed bundle (net of fee).
        cost_per = max(1.0 - opp["net_gap"], 0.01)
        affordable = int(self.cash // cost_per)
        size = int(min(opp["fillable_size"], affordable))
        if size <= 0:
            return

        capital = size * cost_per
        profit = size * opp["net_gap"]
        self.cash -= capital
        self.deployed += capital
        self.locked_profit += profit
        self.open_keys.add(key)

        self.db.execute(
            "INSERT INTO arb_trades (ts, identity, direction, net_gap, gross_gap, fee, size, cost_per, "
            "capital_deployed, locked_profit, legs_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ts, opp["identity"], opp["direction"], opp["net_gap"], opp["gross_gap"], opp["fee"],
             size, round(cost_per, 4), round(capital, 2), round(profit, 2), json.dumps(opp["legs"])),
        )
        self.db.commit()
        print(f"  *** PAPER FILL {key}: {size} pkg @ net ${opp['net_gap']:.4f} "
              f"(gross ${opp['gross_gap']:.4f} fee ${opp['fee']:.4f}) "
              f"-> locked ${profit:.2f} (cash left ${self.cash:.2f})")


def init_db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS arb_log (
        ts TEXT, identity TEXT, direction TEXT, gross_gap REAL, fee REAL, net_gap REAL,
        maker_mid_gap REAL, fillable_size REAL, legs_json TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS arb_trades (
        ts TEXT, identity TEXT, direction TEXT, net_gap REAL, gross_gap REAL, fee REAL,
        size INTEGER, cost_per REAL, capital_deployed REAL, locked_profit REAL, legs_json TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS poll_meta (
        ts TEXT, legs_fetched INTEGER, best_net_gap REAL, best_maker_gap REAL, note TEXT)""")
    db.commit()
    return db


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interval", type=int, default=300, help="seconds between polls (default 300 = 5min)")
    ap.add_argument("--duration", type=int, default=86400, help="total run seconds (default 86400 = 24h)")
    ap.add_argument("--db", default=os.path.join(os.path.dirname(__file__), "..", "..", "data", "coherence_probe.sqlite"))
    ap.add_argument("--jsonl", default=os.path.join(os.path.dirname(__file__), "..", "..", "data", "coherence_probe.jsonl"))
    args = ap.parse_args()

    db_path = os.path.abspath(args.db)
    jsonl_path = os.path.abspath(args.jsonl)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = init_db(db_path)
    book = PaperBook(db)

    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))

    start = time.time()
    poll_n = 0
    best_net_ever = -1.0
    best_maker_ever = -1.0
    print(f"[{_utcnow()}] coherence-arb probe START | interval={args.interval}s "
          f"duration={args.duration}s bankroll=${BANKROLL:.0f} threshold=${EDGE_THRESHOLD}")
    print(f"  db={db_path}\n  jsonl={jsonl_path}")

    jf = open(jsonl_path, "a")
    while not stop["flag"] and (time.time() - start) < args.duration:
        poll_n += 1
        ts = _utcnow()
        snap = poll_all()
        opps = compute_opportunities(snap)
        best_net = max((o["net_gap"] for o in opps), default=-1.0)
        best_maker = max((o["maker_mid_gap"] for o in opps), default=-1.0)
        best_net_ever = max(best_net_ever, best_net)
        best_maker_ever = max(best_maker_ever, best_maker)

        for o in opps:
            db.execute(
                "INSERT INTO arb_log (ts, identity, direction, gross_gap, fee, net_gap, "
                "maker_mid_gap, fillable_size, legs_json) VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, o["identity"], o["direction"], o["gross_gap"], o["fee"], o["net_gap"],
                 o["maker_mid_gap"], o["fillable_size"], json.dumps(o["legs"])),
            )
            book.maybe_trade(o, ts)
        db.execute("INSERT INTO poll_meta (ts, legs_fetched, best_net_gap, best_maker_gap, note) VALUES (?,?,?,?,?)",
                   (ts, len(snap), best_net, best_maker, "ok" if opps else "incomplete"))
        db.commit()
        jf.write(json.dumps({"ts": ts, "poll": poll_n, "opps": opps,
                             "cash": round(book.cash, 2), "locked_profit": round(book.locked_profit, 2)}) + "\n")
        jf.flush()

        elapsed = int(time.time() - start)
        summary = " | ".join(
            f"{o['identity']}/{o['direction']} net={o['net_gap']:+.4f} maker={o['maker_mid_gap']:+.4f}(sz{int(o['fillable_size'])})"
            for o in opps)
        print(f"[{ts}] poll#{poll_n} t+{elapsed}s legs={len(snap)}/9 | {summary or 'NO DATA'} "
              f"| bestNet={best_net_ever:+.4f} bestMaker={best_maker_ever:+.4f} lockedP&L=${book.locked_profit:.2f}")

        # sleep in small chunks so SIGTERM is responsive
        slept = 0
        while slept < args.interval and not stop["flag"] and (time.time() - start) < args.duration:
            time.sleep(min(5, args.interval - slept))
            slept += 5

    jf.close()
    n_trades = db.execute("SELECT COUNT(*) FROM arb_trades").fetchone()[0]
    print(f"\n[{_utcnow()}] PROBE END after {poll_n} polls, {int(time.time()-start)}s")
    print(f"  best NET taker gap ever (after politics fee): {best_net_ever:+.4f}  (>{EDGE_THRESHOLD} => riskless arb)")
    print(f"  best MAKER mid gap ever (fee-free best case):  {best_maker_ever:+.4f}  (tick size=0.01)")
    print(f"  paper fills: {n_trades}  locked riskless profit: ${book.locked_profit:.2f}  cash: ${book.cash:.2f}")
    if best_net_ever < EDGE_THRESHOLD:
        print("  VERDICT: no riskless taker arb at any poll -> thesis NULL as a taker.")
        if best_maker_ever < 0.01:
            print("  Maker best-case stayed within one tick -> book is coherent to the price grid; "
                  "no harvestable edge for a slow maker either. Expected modal outcome.")
        else:
            print("  Maker best-case exceeded a tick at times -> a patient maker MIGHT harvest it; "
                  "gated by leg-fill / adverse-selection risk (not modeled). Worth a closer look.")
    else:
        print("  VERDICT: a riskless fillable coherence violation appeared -> investigate (rare).")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
