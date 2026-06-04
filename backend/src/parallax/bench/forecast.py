"""Generate P(YES) forecasts from Claude models for benchmark questions.

Async, bounded-concurrency, checkpointed to JSONL so reruns resume instead of
re-paying for completed questions. Tracks token usage and estimates cost.

LEAKAGE WARNING: KalshiBench questions resolved in 2025, within the knowledge
cutoff of current Claude models, so a model may *recall* outcomes rather than
forecast them. These probabilities therefore measure "how (mis)calibrated is the
model's stated confidence on these outputs", NOT forecasting skill on unknown
futures. The harness reports this prominently.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from anthropic import NOT_GIVEN
from anthropic.types import ToolChoiceToolParam, ToolParam

logger = logging.getLogger(__name__)

# Approximate Anthropic list prices, USD per 1M tokens (input, output). For cost
# *estimation* only -- not billing. Update if pricing changes.
_PRICES = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (15.0, 75.0),
}

_SYSTEM = (
    "You are a careful probabilistic forecaster. Call the report_probability tool with "
    "a single calibrated probability that the question resolves YES. Report honest "
    "uncertainty: use values near 0 or 1 only when you are genuinely that confident."
)

# Forced tool-use gives a structured numeric output that works across all current
# Claude models (assistant-prefill is rejected by some; tool-use is universal) and
# can't run out of tokens mid-reasoning.
_TOOL: ToolParam = {
    "name": "report_probability",
    "description": "Report your single calibrated probability that the question resolves YES.",
    "input_schema": {
        "type": "object",
        "properties": {
            "p_yes": {
                "type": "number",
                "description": "Probability in [0,1] that the question resolves YES.",
            }
        },
        "required": ["p_yes"],
    },
}
_TOOL_CHOICE: ToolChoiceToolParam = {"type": "tool", "name": "report_probability"}

# A bare probability token: 0.xx, .xx, 1.0, or exactly 0/1 (not part of a longer number).
_NUM = r"(0?\.\d+|1(?:\.0+)?|0|1)(?![\d.])"
_TAG_RE = re.compile(r"PROBABILITY:\s*" + _NUM, re.IGNORECASE)
_PROB_RE = re.compile(r"(?<![\d.])" + _NUM)


@dataclass
class ForecastStats:
    model: str
    n_ok: int = 0
    n_error: int = 0
    n_skipped_cached: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def est_cost_usd(self) -> float:
        pin, pout = _PRICES.get(self.model, (3.0, 15.0))
        return self.input_tokens / 1e6 * pin + self.output_tokens / 1e6 * pout


def _build_prompt(row: pd.Series) -> str:
    parts = [f"Question: {row['question']}"]
    desc = str(row.get("description") or "").strip()
    if desc:
        parts.append(f"Resolution criteria: {desc}")
    cat = str(row.get("category") or "").strip()
    if cat:
        parts.append(f"Category: {cat}")
    ct = str(row.get("close_time") or "").strip()
    if ct:
        parts.append(f"Closes: {ct}")
    parts.append("What is the probability this resolves YES?")
    return "\n".join(parts)


def _extract_tool_prob(resp) -> float | None:
    """Pull p_yes from the forced report_probability tool call; clamp to [0,1]."""
    for block in resp.content:
        if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == _TOOL["name"]:
            val = (getattr(block, "input", None) or {}).get("p_yes")
            if val is None:
                return None
            try:
                v = float(val)
            except (TypeError, ValueError):
                return None
            return min(1.0, max(0.0, v))
    return None


def _parse_prob(text: str) -> float | None:
    """Prefer the explicit 'PROBABILITY: X' tag; else the last in-range number."""
    text = text.strip()
    m = _TAG_RE.search(text)
    if m:
        v = float(m.group(1))
        return v if 0.0 <= v <= 1.0 else None
    # Fallback: last bare number in [0,1] (the conclusion usually comes last).
    for tok in reversed(_PROB_RE.findall(text)):
        try:
            v = float(tok)
        except ValueError:
            continue
        if 0.0 <= v <= 1.0:
            return v
    return None


def _load_checkpoint(path: Path) -> dict[str, dict]:
    """Return {qid: record} for already-completed (ok) forecasts."""
    done: dict[str, dict] = {}
    if not path.exists():
        return done
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ok") and rec.get("prob") is not None:
                done[rec["qid"]] = rec
    return done


async def generate_forecasts(
    df: pd.DataFrame,
    model: str,
    *,
    checkpoint_path: str | Path,
    concurrency: int = 12,
    limit: int | None = None,
    max_tokens: int = 64,
    temperature: float = 0.0,
) -> tuple[pd.DataFrame, ForecastStats]:
    """Forecast P(YES) for each row with ``model``; resume from checkpoint.

    Returns ``(forecasts_df, stats)`` where forecasts_df has columns
    ``qid, model, prob``. Rows that error after retries are dropped from the
    returned frame (recorded in ``stats.errors``).
    """
    from anthropic import AsyncAnthropic

    checkpoint_path = Path(checkpoint_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    done = _load_checkpoint(checkpoint_path)

    work = df if limit is None else df.head(limit)
    stats = ForecastStats(model=model)
    client = AsyncAnthropic(max_retries=5)
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    fh = checkpoint_path.open("a")

    rows = [r for _, r in work.iterrows()]
    pending = [r for r in rows if r["qid"] not in done]
    stats.n_skipped_cached = len(rows) - len(pending)

    # Some models reject the `temperature` param; flip this off on first such error
    # and retry without it (shared across coroutines; benign idempotent race).
    use_temperature = [True]

    async def _one(row: pd.Series) -> None:
        qid = row["qid"]
        async with sem:
            prob: float | None = None
            err: str | None = None
            in_tok = out_tok = 0
            for attempt in range(3):
                try:
                    resp = await client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        system=_SYSTEM,
                        messages=[{"role": "user", "content": _build_prompt(row)}],
                        tools=[_TOOL],
                        tool_choice=_TOOL_CHOICE,
                        temperature=temperature if use_temperature[0] else NOT_GIVEN,
                    )
                    in_tok += resp.usage.input_tokens
                    out_tok += resp.usage.output_tokens
                    prob = _extract_tool_prob(resp)
                    if prob is None:  # defensive: parse any text the model emitted instead
                        prob = _parse_prob("".join(getattr(b, "text", "") for b in resp.content))
                    if prob is not None:
                        break
                    err = "no report_probability tool_use in response"
                except Exception as exc:  # network / API / rate-limit after SDK retries
                    msg = str(exc)
                    # Some models reject `temperature`; drop it and retry. Don't gate
                    # on the flag's current value -- another coroutine may have already
                    # flipped it, and this call still needs its own retry.
                    if "temperature" in msg.lower() and attempt < 2:
                        use_temperature[0] = False
                        continue
                    err = f"{type(exc).__name__}: {msg[:200]}"
                    break
        rec = {"qid": qid, "model": model, "prob": prob, "ok": prob is not None, "error": err,
               "in_tok": in_tok, "out_tok": out_tok}
        async with lock:
            stats.input_tokens += in_tok
            stats.output_tokens += out_tok
            if prob is not None:
                stats.n_ok += 1
            else:
                stats.n_error += 1
                if err:
                    stats.errors.append(f"{qid}: {err}")
            fh.write(json.dumps(rec) + "\n")
            fh.flush()

    try:
        await asyncio.gather(*(_one(r) for r in pending))
    finally:
        fh.close()
        try:
            await client.close()
        except Exception:
            pass

    # Reload full checkpoint (cached + new) and return forecasts for the worked set.
    done = _load_checkpoint(checkpoint_path)
    worked_qids = set(work["qid"])
    records = [
        {"qid": qid, "model": model, "prob": rec["prob"]}
        for qid, rec in done.items()
        if qid in worked_qids
    ]
    out = pd.DataFrame(records, columns=["qid", "model", "prob"])
    return out, stats
