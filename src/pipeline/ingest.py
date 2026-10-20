"""
Ingest NFL games with closing betting lines into the bronze layer.

    source "nflverse"  real data: every NFL game since 1999 with closing moneylines
                       (2006+), spreads, totals, rest days, weather. Downloaded from
                       https://github.com/nflverse/nfldata (not redistributed here).
    source "sample"    synthetic file in the same columns (data/sample/), no network.

Steps:  fetch -> land raw bytes (gzip + SHA-256) -> validate columns ->
        write bronze Parquet partitioned by season -> append a manifest line.

Re-running is idempotent: each season partition is replaced, never appended to.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import requests

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

NFLVERSE_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
SAMPLE_FILE = Path(__file__).resolve().parents[2] / "data" / "sample" / "games_sample.csv"

REQUIRED_COLUMNS = [
    "game_id",
    "season",
    "game_type",
    "week",
    "gameday",
    "away_team",
    "away_score",
    "home_team",
    "home_score",
    "away_rest",
    "home_rest",
    "away_moneyline",
    "home_moneyline",
    "spread_line",
    "total_line",
    "div_game",
    "roof",
    "temp",
    "wind",
]
# Explicit types: never let pandas guess (a column of blanks would become float, IDs could lose zeros)
DTYPES = {
    "game_id": "string",
    "season": "int64",
    "game_type": "string",
    "week": "int64",
    "gameday": "string",
    "away_team": "string",
    "home_team": "string",
    "away_score": "Int64",
    "home_score": "Int64",
    "away_rest": "Int64",
    "home_rest": "Int64",
    "away_moneyline": "Int64",
    "home_moneyline": "Int64",
    "spread_line": "float64",
    "total_line": "float64",
    "div_game": "Int64",
    "roof": "string",
    "temp": "float64",
    "wind": "float64",
}


class SchemaError(ValueError):
    """The source file no longer has the columns this pipeline depends on."""


def fetch(source: str) -> bytes:
    if source == "sample":
        return SAMPLE_FILE.read_bytes()
    if source == "nflverse":
        resp = requests.get(NFLVERSE_URL, timeout=60)
        resp.raise_for_status()
        return resp.content
    raise ValueError(f"Unknown source: {source}")


def land(raw: bytes, source: str, landing_dir: Path) -> tuple[Path, str]:
    """Save the exact bytes received; return (path, sha256)."""
    sha = hashlib.sha256(raw).hexdigest()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = landing_dir / source / f"games_{day}_{sha[:12]}.csv.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():  # same content, same name: landing twice is a no-op
        with gzip.open(path, "wb") as fh:
            fh.write(raw)
    return path, sha


def parse(raw: bytes) -> pd.DataFrame:
    """CSV bytes -> typed DataFrame with only the columns we rely on."""
    df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, na_values=[""])
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"Source is missing columns: {missing}")
    df = df[REQUIRED_COLUMNS].copy()
    for col, dtype in DTYPES.items():
        if dtype in ("Int64", "int64", "float64"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].astype(dtype)
    return df


def write_bronze(df: pd.DataFrame, lake_dir: Path) -> list[int]:
    """Write one Parquet partition per season, replacing those seasons only."""
    target = lake_dir / "bronze" / "games"
    table = pa.Table.from_pandas(df, preserve_index=False)
    ds.write_dataset(
        table,
        target,
        format="parquet",
        partitioning=ds.partitioning(pa.schema([("season", pa.int64())]), flavor="hive"),
        existing_data_behavior="delete_matching",
        basename_template="part-{i}.parquet",
    )
    return sorted(int(s) for s in df["season"].unique())


def run_ingest(source: str = "nflverse", data_dir: Path = DATA_DIR) -> dict:
    run_id = uuid.uuid4().hex[:12]
    raw = fetch(source)
    landed, sha = land(raw, source, data_dir / "landing")
    df = parse(raw)
    seasons = write_bronze(df, data_dir / "lake")
    record = {
        "run_id": run_id,
        "source": source,
        "sha256": sha,
        "landed_path": str(landed),
        "rows": len(df),
        "seasons": [seasons[0], seasons[-1]],
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    manifest = data_dir / "lake" / "_manifest.jsonl"
    with open(manifest, "a") as fh:
        fh.write(json.dumps(record) + "\n")
    logger.info("Ingested %d games (%s-%s) from %s", len(df), seasons[0], seasons[-1], source)
    return record
