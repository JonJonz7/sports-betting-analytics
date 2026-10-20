"""Run the whole pipeline on the synthetic sample in a temp folder and check the outputs."""

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory) -> Path:
    data = tmp_path_factory.mktemp("e2e")
    env = {**os.environ, "EDGEIQ_DATA_DIR": str(data)}
    run = subprocess.run(
        [sys.executable, "-m", "src.cli", "all", "--source", "sample"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-3000:]
    return data / "warehouse.duckdb"


def one(db, sql):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchone()
    finally:
        con.close()


def test_every_game_flows_through(warehouse):
    assert one(warehouse, "select count(*) from marts.fct_games") == (1096,)


def test_predictions_cover_seasons_after_warmup(warehouse):
    assert one(warehouse, "select min(season), max(season) from marts.predictions") == (2015, 2019)


def test_market_is_the_benchmark(warehouse):
    model, market = one(
        warehouse,
        """select model_brier, market_brier
                                      from marts.model_vs_market where season = 'ALL'""",
    )
    assert market < model  # the synthetic market sees true strength; Elo has to learn it


def test_backtest_written(warehouse):
    assert one(warehouse, "select count(*) from marts.backtest_summary") == (2,)
