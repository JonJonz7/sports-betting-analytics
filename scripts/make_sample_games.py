"""
Generate data/sample/games_sample.csv: a SYNTHETIC season file in the same
columns as nflverse's games.csv, used by tests, CI and `make demo`.

Why synthetic: the real file is downloaded at run time from nflverse (it is
not ours to redistribute), and tests need data with KNOWN properties:

- 16 fictional teams (T01..T16) with hidden true strengths that drift slowly
- results drawn from those strengths plus home-field advantage
- closing moneylines from a "market" that sees the true strength with a
  little noise and charges ~4.5% vig

So a correct pipeline must find: the market is well calibrated, a pure Elo
model is close to (but worse than) the market, and betting at closing odds
loses roughly the vig.

Run:  python scripts/make_sample_games.py
"""

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "sample" / "games_sample.csv"
SEASONS = range(2012, 2020)
TEAMS = [f"T{i:02d}" for i in range(1, 17)]
DIVISIONS = [TEAMS[i : i + 4] for i in range(0, 16, 4)]
HOME_EDGE = 0.35  # in "strength" units; about 58% home win rate for equal teams
VIG = 0.045

COLUMNS = [
    "game_id",
    "season",
    "game_type",
    "week",
    "gameday",
    "weekday",
    "away_team",
    "away_score",
    "home_team",
    "home_score",
    "result",
    "total",
    "overtime",
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


def win_prob(diff: float) -> float:
    return 1 / (1 + math.exp(-diff))


def to_american(p: float) -> int:
    """Decimal-free American odds for a probability that already includes vig."""
    p = min(max(p, 0.02), 0.98)
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))


def division(team: str) -> int:
    return next(i for i, d in enumerate(DIVISIONS) if team in d)


def main() -> None:
    rng = random.Random(7)
    strength = {t: rng.gauss(0, 0.6) for t in TEAMS}
    rows = []
    for season in SEASONS:
        # regress toward the mean between seasons, then drift
        strength = {t: 0.7 * s + rng.gauss(0, 0.3) for t, s in strength.items()}
        kickoff = date(season, 9, 8)
        last_played = {t: kickoff - timedelta(days=200) for t in TEAMS}
        for week in range(1, 18):
            teams = TEAMS[:]
            rng.shuffle(teams)
            day = kickoff + timedelta(days=7 * (week - 1))
            for i in range(0, 16, 2):
                home, away = teams[i], teams[i + 1]
                strength[home] += rng.gauss(0, 0.04)
                strength[away] += rng.gauss(0, 0.04)
                p_home = win_prob(strength[home] - strength[away] + HOME_EDGE)
                home_win = rng.random() < p_home
                margin = max(1, int(abs(rng.gauss(10, 7))))
                base = int(rng.gauss(20, 5))
                hs, as_ = (base + margin, base) if home_win else (base, base + margin)
                # the market sees strength with noise, then adds vig to both sides
                p_mkt = win_prob(math.log(p_home / (1 - p_home)) + rng.gauss(0, 0.15))
                home_ml = to_american(p_mkt * (1 + VIG / 2))
                away_ml = to_american((1 - p_mkt) * (1 + VIG / 2))
                spread = round(math.log(p_mkt / (1 - p_mkt)) * 6.5 * 2) / 2
                rest_h = min((day - last_played[home]).days, 14)
                rest_a = min((day - last_played[away]).days, 14)
                last_played[home] = last_played[away] = day
                rows.append(
                    {
                        "game_id": f"{season}_{week:02d}_{away}_{home}",
                        "season": season,
                        "game_type": "REG",
                        "week": week,
                        "gameday": day.isoformat(),
                        "weekday": "Sunday",
                        "away_team": away,
                        "away_score": as_,
                        "home_team": home,
                        "home_score": hs,
                        "result": hs - as_,
                        "total": hs + as_,
                        "overtime": 0,
                        "away_rest": rest_a,
                        "home_rest": rest_h,
                        "away_moneyline": away_ml,
                        "home_moneyline": home_ml,
                        "spread_line": spread,
                        "total_line": 44.5,
                        "div_game": int(division(home) == division(away)),
                        "roof": rng.choice(["outdoors", "dome"]),
                        "temp": rng.randint(30, 85),
                        "wind": rng.randint(0, 20),
                    }
                )
    # one upcoming (unplayed) week, like the real file: no scores yet
    for row in rows[-8:]:
        future = dict(row)
        future.update(
            game_id=row["game_id"].replace("_17_", "_18_"),
            week=18,
            gameday=(date.fromisoformat(row["gameday"]) + timedelta(days=7)).isoformat(),
            away_score="",
            home_score="",
            result="",
            total="",
        )
        rows.append(future)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} synthetic games to {OUT}")


if __name__ == "__main__":
    main()
