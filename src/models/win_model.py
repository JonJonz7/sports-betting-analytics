"""
Home-win probability model, trained walk-forward (no look-ahead).

For each season S: fit a logistic regression on every played game BEFORE S,
then predict every game IN S. The model never sees the season it predicts,
which is how it would have been used in real life. A random train/test split
would let it learn from the future and look better than it is.

Features (all known before kickoff):
    elo_diff     pre-game Elo gap incl. home field (src/models/elo.py), per 100 points
    rest_diff    home rest days minus away rest days
    is_division  division rivals (closer games)
    is_playoff   playoff game

The betting market's price is deliberately NOT a feature: the point is to
compare an independent model with the market, not to copy it.
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

FEATURES = ["elo_diff_100", "rest_diff", "is_division", "is_playoff"]
MIN_TRAIN_SEASONS = 3


def _features(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["elo_diff_100"] = (df["elo_diff"] + 48.0) / 100.0  # include home field as Elo does
    x["rest_diff"] = df["rest_diff"].clip(-7, 7).fillna(0)
    x["is_division"] = df["is_division"].astype(float)
    x["is_playoff"] = df["is_playoff"].astype(float)
    return x[FEATURES]


def walk_forward(games: pd.DataFrame, min_train_seasons: int = MIN_TRAIN_SEASONS) -> pd.DataFrame:
    """Predict each season using only earlier seasons."""
    seasons = sorted(games["season"].unique())
    out = []
    for i, season in enumerate(seasons):
        if i < min_train_seasons:
            continue
        train = games[(games["season"] < season) & games["is_played"] & games["home_win"].notna()]
        test = games[games["season"] == season]
        if train.empty or test.empty:
            continue
        model = LogisticRegression(C=1.0, max_iter=1000)
        model.fit(_features(train), train["home_win"].astype(int))
        probs = np.clip(model.predict_proba(_features(test))[:, 1], 0.01, 0.99)
        out.append(
            pd.DataFrame(
                {
                    "game_id": test["game_id"].values,
                    "season": season,
                    "model_prob_home": probs,
                    "train_rows": len(train),
                    "max_train_season": int(train["season"].max()),
                    "coef_elo": float(model.coef_[0][0]),
                }
            )
        )
    if not out:
        return pd.DataFrame(
            columns=[
                "game_id",
                "season",
                "model_prob_home",
                "train_rows",
                "max_train_season",
                "coef_elo",
            ]
        )
    return pd.concat(out, ignore_index=True)


def build_predictions(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Python model for the transform runner."""
    games = con.execute("""
        select game_id, season, is_played, home_win, elo_diff, rest_diff, is_division, is_playoff
        from marts.fct_games
    """).fetchdf()
    return walk_forward(games)
