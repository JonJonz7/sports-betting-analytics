"""
Quality gate on the bronze layer, run BEFORE the transform.

Each check counts failing rows. "error" checks stop the pipeline; "warn"
checks are reported. A check that can never fail is decoration, so each one
here is backed by a test that makes it fail on purpose (tests/test_checks.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from src.config import DATA_DIR


@dataclass
class Check:
    name: str
    level: str  # "error" or "warn"
    sql: str  # returns the number of failing rows (or 1/0 for table-level checks)


CHECKS = [
    Check("table is not empty", "error", "select (count(*) = 0)::int from bronze"),
    Check(
        "game_id is unique",
        "error",
        "select count(*) from (select game_id from bronze group by 1 having count(*) > 1)",
    ),
    Check(
        "key columns present",
        "error",
        "select count(*) from bronze where game_id is null or season is null "
        "or home_team is null or away_team is null or gameday is null",
    ),
    Check(
        "scores are both present or both missing",
        "error",
        "select count(*) from bronze where (home_score is null) <> (away_score is null)",
    ),
    Check(
        "scores are not negative",
        "error",
        "select count(*) from bronze where home_score < 0 or away_score < 0",
    ),
    Check(
        "moneylines look like American odds",
        "error",
        "select count(*) from bronze where home_moneyline is not null "
        "and (abs(home_moneyline) < 100 or abs(away_moneyline) < 100)",
    ),
    Check(
        "both sides priced as underdogs (only near pick'em)",
        "warn",
        "select count(*) from bronze where home_moneyline > 100 and away_moneyline > 100",
    ),
    Check(
        "week numbers are sane", "error", "select count(*) from bronze where week < 1 or week > 23"
    ),
]


def run_checks(data_dir: Path = DATA_DIR) -> list[tuple[Check, int]]:
    con = duckdb.connect()
    try:
        con.execute(f"""create view bronze as select * from read_parquet(
            '{(data_dir / 'lake').as_posix()}/bronze/games/**/*.parquet', hive_partitioning = true)""")
        return [(c, int(con.execute(c.sql).fetchone()[0])) for c in CHECKS]
    finally:
        con.close()
