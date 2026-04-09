"""Runtime environment helpers for DB and execution isolation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeConfig:
    """Resolved runtime/storage settings for one process."""

    data_environment: str
    execution_environment: str
    db_path: str


def resolve_runtime_config(*, dry_run: bool = False) -> RuntimeConfig:
    """Resolve DB path and environment labels without mixing dry-run/live data."""

    explicit_db_path = os.environ.get("DUCKDB_PATH")
    base_data_dir = Path(os.environ.get("PARALLAX_DATA_DIR", "data"))
    base_data_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        db_path = os.environ.get(
            "PARALLAX_DRY_RUN_DUCKDB_PATH",
            ":memory:",
        )
        return RuntimeConfig(
            data_environment="dry_run",
            execution_environment="none",
            db_path=db_path,
        )

    parallax_env = os.environ.get("PARALLAX_ENV", "demo").strip().lower() or "demo"
    if parallax_env not in {"demo", "live", "test"}:
        logger.warning("Unknown PARALLAX_ENV=%s, defaulting to demo", parallax_env)
        parallax_env = "demo"

    default_name = f"parallax-{parallax_env}.duckdb"
    db_path = explicit_db_path or str(base_data_dir / default_name)
    execution_environment = "demo" if parallax_env == "demo" else "live"
    return RuntimeConfig(
        data_environment=parallax_env,
        execution_environment=execution_environment,
        db_path=db_path,
    )
