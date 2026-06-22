"""Load the KalshiBench resolved-question benchmark.

KalshiBench (HuggingFace ``2084Collective/kalshibench-v{1,2}``) is a set of
already-resolved binary Kalshi questions with ground-truth outcomes. v2 has
1,531 questions. It ships NO model forecasts and NO market prices
(``market_probability`` is null) -- forecasts must be generated (see
``bench/forecast.py``).

Important grouping note: the ``id`` / ``series_ticker`` field is the *event*, not
the question -- an event can contribute more than one row (in v2, ``id ==
series_ticker`` with up to 2 rows per event; other versions/events may have more).
Cross-validation must group by event (``group`` column) so rows of the same event
never split across train/test, or calibration leaks.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_REPO = {
    "v1": "2084Collective/kalshibench-v1",
    "v2": "2084Collective/kalshibench-v2",
}

# backend/data/bench (parents: kalshibench.py -> bench -> parallax -> src -> backend)
_DEFAULT_CACHE = Path(__file__).resolve().parents[3] / "data" / "bench"


def load_kalshibench(
    version: str = "v2",
    cache_dir: str | Path | None = None,
    download: bool = True,
) -> pd.DataFrame:
    """Load KalshiBench into a DataFrame, caching the parquet locally.

    Adds three derived columns:
      - ``label``: 1 if ground_truth == 'yes' else 0
      - ``qid``: unique per-row id (``series_ticker#rowindex``)
      - ``group``: event key for grouped CV (== series_ticker)
    """
    if version not in _REPO:
        raise ValueError(f"unknown KalshiBench version {version!r}; expected one of {list(_REPO)}")
    cache_dir = Path(cache_dir or _DEFAULT_CACHE)
    cache_dir.mkdir(parents=True, exist_ok=True)
    local = cache_dir / f"kalshibench-{version}.parquet"

    if local.exists():
        df = pd.read_parquet(local)
    elif download:
        from huggingface_hub import hf_hub_download, list_repo_files

        repo = _REPO[version]
        parquets = [
            f for f in list_repo_files(repo, repo_type="dataset") if f.endswith(".parquet")
        ]
        if not parquets:
            raise RuntimeError(f"no parquet files found in {repo}")
        path = hf_hub_download(repo, parquets[0], repo_type="dataset")
        df = pd.read_parquet(path)
        df.to_parquet(local)
    else:
        raise FileNotFoundError(
            f"KalshiBench cache missing at {local} and download=False"
        )

    df = df.reset_index(drop=True)
    gt = df["ground_truth"].astype(str).str.strip().str.lower()
    if not gt.isin({"yes", "no"}).all():
        bad = sorted(set(gt) - {"yes", "no"})
        raise ValueError(f"unexpected ground_truth values: {bad}")
    df["label"] = (gt == "yes").astype(int)
    df["qid"] = df["series_ticker"].astype(str) + "#" + df.index.astype(str)
    df["group"] = df["series_ticker"].astype(str)
    return df
