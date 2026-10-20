"""
EdgeIQ dashboard (Streamlit, read-only).

    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import WAREHOUSE_PATH

st.set_page_config(page_title="EdgeIQ", layout="wide")


@st.cache_data(ttl=300)
def q(sql: str) -> pd.DataFrame:
    if not WAREHOUSE_PATH.exists():
        return pd.DataFrame()
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        return con.execute(sql).fetchdf()
    except duckdb.Error:
        return pd.DataFrame()
    finally:
        con.close()


st.title("EdgeIQ: an NFL model vs the betting market")
scores = q("select * from marts.model_vs_market order by season")
if scores.empty:
    st.warning("No warehouse yet. Run `make demo` (sample) or `make run` (real NFL data).")
    st.stop()

overall = scores[scores["season"] == "ALL"].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Games scored", f"{int(overall['games']):,}")
c2.metric("Model accuracy", f"{overall['model_accuracy']:.1%}")
c3.metric("Market accuracy", f"{overall['market_accuracy']:.1%}")
c4.metric("Brier: model / market", f"{overall['model_brier']:.4f} / {overall['market_brier']:.4f}")

t1, t2, t3, t4 = st.tabs(["Model vs market", "Calibration", "Backtest", "Game lookup"])

with t1:
    per = scores[scores["season"] != "ALL"].melt(
        id_vars="season",
        value_vars=["model_log_loss", "elo_log_loss", "market_log_loss"],
        var_name="source",
        value_name="log_loss",
    )
    st.plotly_chart(
        px.line(
            per,
            x="season",
            y="log_loss",
            color="source",
            markers=True,
            title="Log loss by season (lower is better)",
        ),
        use_container_width=True,
    )
    st.dataframe(scores, hide_index=True, use_container_width=True)

with t2:
    cal = q("""
        select round(floor(home_novig * 20) / 20, 2) as bucket, avg(home_novig) as predicted,
               avg(home_win) as actual, count(*) as games
        from staging.stg_games where is_played and home_win is not null and home_novig is not null
        group by 1 having count(*) >= 20 order by 1""")
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="perfect", line={"dash": "dash"})
    fig.add_scatter(
        x=cal["predicted"], y=cal["actual"], mode="markers+lines", name="market", text=cal["games"]
    )
    fig.update_layout(
        title="Market calibration: predicted vs actual home win rate",
        xaxis_title="no-vig market probability",
        yaxis_title="actual win rate",
    )
    st.plotly_chart(fig, use_container_width=True)

with t3:
    st.dataframe(
        q("select * from marts.backtest_summary"), hide_index=True, use_container_width=True
    )
    bets = q("select game_date, bankroll, edge, won from marts.backtest_bets order by game_date")
    if not bets.empty:
        st.plotly_chart(
            px.line(
                bets,
                x="game_date",
                y="bankroll",
                title="Bankroll, quarter-Kelly on model edges (starts at $10,000)",
            ),
            use_container_width=True,
        )
        st.caption(
            "Bets are placed at closing odds, so closing line value is zero by construction."
        )

with t4:
    game_id = st.text_input("Game id (e.g. 2024_01_BAL_KC)")
    if game_id:
        g = q(f"""select f.*, p.model_prob_home from marts.fct_games f
                  left join marts.predictions p using (game_id)
                  where f.game_id = '{game_id.replace("'", "")}'""")
        st.dataframe(g.T if not g.empty else g, use_container_width=True)
