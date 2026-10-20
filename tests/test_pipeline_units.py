"""Unit tests for ingestion, bronze checks, Elo, the walk-forward model and the runner."""

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.models.elo import HOME_FIELD, run_elo, win_probability
from src.models.win_model import walk_forward
from src.pipeline import checks, ingest
from src.pipeline.transform import BuildError, Model, _test_sql, render

SAMPLE = ingest.SAMPLE_FILE.read_bytes()


# ---------- ingestion ----------


def test_parse_types_and_keeps_only_required_columns():
    df = ingest.parse(SAMPLE)
    assert list(df.columns) == ingest.REQUIRED_COLUMNS
    assert str(df["home_moneyline"].dtype) == "Int64"
    assert df["home_score"].isna().sum() == 8  # the unplayed week


def test_parse_rejects_a_changed_source():
    broken = SAMPLE.replace(b"home_moneyline", b"home_ml", 1)
    with pytest.raises(ingest.SchemaError, match="home_moneyline"):
        ingest.parse(broken)


def test_bronze_write_is_idempotent(tmp_path):
    df = ingest.parse(SAMPLE)
    ingest.write_bronze(df, tmp_path)
    ingest.write_bronze(df, tmp_path)  # second run replaces partitions, doesn't append
    n = duckdb.sql(
        f"select count(*) from read_parquet('{tmp_path}/bronze/games/**/*.parquet')"
    ).fetchone()[0]
    assert n == len(df)


def test_landing_same_bytes_same_file(tmp_path):
    p1, sha1 = ingest.land(b"abc", "sample", tmp_path)
    p2, sha2 = ingest.land(b"abc", "sample", tmp_path)
    assert (p1, sha1) == (p2, sha2)


# ---------- bronze checks: every check must be able to fail ----------


def _lake_with(tmp_path, mutate):
    df = ingest.parse(SAMPLE)
    mutate(df)
    ingest.write_bronze(df, tmp_path / "lake")
    return {c.name: n for c, n in checks.run_checks(tmp_path)}


def test_checks_pass_on_clean_data(tmp_path):
    assert all(n == 0 for n in _lake_with(tmp_path, lambda df: None).values())


@pytest.mark.parametrize(
    "name,mutate",
    [
        ("game_id is unique", lambda df: df.loc.__setitem__((1, "game_id"), df.loc[0, "game_id"])),
        ("scores are not negative", lambda df: df.loc.__setitem__((0, "home_score"), -3)),
        (
            "scores are both present or both missing",
            lambda df: df.loc.__setitem__((0, "away_score"), pd.NA),
        ),
        (
            "moneylines look like American odds",
            lambda df: df.loc.__setitem__((0, "home_moneyline"), 50),
        ),
        ("week numbers are sane", lambda df: df.loc.__setitem__((0, "week"), 40)),
    ],
)
def test_each_check_can_fail(tmp_path, name, mutate):
    assert _lake_with(tmp_path, mutate)[name] >= 1


# ---------- Elo ----------


def _games(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "game_id",
            "season",
            "game_date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "is_played",
        ],
    )


def test_equal_teams_home_gets_home_field_edge():
    out = run_elo(_games([("g1", 2020, "2020-09-10", "A", "B", 20, 10, True)]))
    assert out.loc[0, "elo_prob_home"] == pytest.approx(win_probability(HOME_FIELD))
    assert 0.56 < out.loc[0, "elo_prob_home"] < 0.58


def test_ratings_are_pre_game_and_zero_sum():
    out = run_elo(
        _games(
            [
                ("g1", 2020, "2020-09-10", "A", "B", 30, 10, True),
                ("g2", 2020, "2020-09-17", "A", "B", 30, 10, True),
            ]
        )
    )
    # game 1's row must not know game 1's result
    assert out.loc[0, "elo_home_pre"] == out.loc[0, "elo_away_pre"] == 1500
    # the winner's gain equals the loser's loss
    assert out.loc[1, "elo_home_pre"] - 1500 == pytest.approx(1500 - out.loc[1, "elo_away_pre"])
    assert out.loc[1, "elo_home_pre"] > 1500


def test_unplayed_games_get_predictions_but_no_update():
    out = run_elo(
        _games(
            [
                ("g1", 2020, "2020-09-10", "A", "B", None, None, False),
                ("g2", 2020, "2020-09-17", "A", "B", None, None, False),
            ]
        )
    )
    assert out.loc[1, "elo_home_pre"] == 1500


# ---------- walk-forward model ----------


def _synthetic(seasons=6, per=200, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(2010, 2010 + seasons):
        diff = rng.normal(0, 150, per)
        p = 1 / (1 + 10 ** (-(diff + 48) / 400))
        win = (rng.random(per) < p).astype(int)
        for i in range(per):
            rows.append((f"{s}_{i}", s, True, win[i], diff[i], 0, False, False))
    return pd.DataFrame(
        rows,
        columns=[
            "game_id",
            "season",
            "is_played",
            "home_win",
            "elo_diff",
            "rest_diff",
            "is_division",
            "is_playoff",
        ],
    )


def test_walk_forward_never_sees_the_season_it_predicts():
    preds = walk_forward(_synthetic())
    assert (preds["max_train_season"] < preds["season"]).all()
    assert preds["season"].min() == 2013  # needs 3 earlier seasons
    assert preds["coef_elo"].iloc[-1] > 0  # learned that stronger teams win


# ---------- runner ----------


def test_ref_before_build_is_an_error(tmp_path):
    with pytest.raises(BuildError, match="reorder"):
        render("select * from {{ ref('marts.x') }}", tmp_path, built=set())
    assert render("select * from {{ ref('a.b') }}", tmp_path, {"a.b"}) == "select * from a.b"


def test_unknown_test_type_is_an_error():
    with pytest.raises(BuildError):
        _test_sql(Model(name="a.b", kind="sql"), {"type": "nope"})
