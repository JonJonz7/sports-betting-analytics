"""Streamlit dashboard for EdgeIQ Sports Betting Analytics.

Replaces PowerBI with a free, Python-native, deployable dashboard.
Connects to the FastAPI backend for data.
"""

from __future__ import annotations


def main():
    """Entry point for the Streamlit dashboard."""
    import streamlit as st

    st.set_page_config(
        page_title="EdgeIQ Analytics",
        page_icon="📊",
        layout="wide",
    )

    st.title("EdgeIQ -- Sports Betting Analytics")

    tab_ev, tab_clv, tab_parlays, tab_bankroll, tab_model = st.tabs([
        "+EV Opportunities",
        "CLV Tracker",
        "Correlated Parlays",
        "Bankroll & P/L",
        "Model Performance",
    ])

    with tab_ev:
        st.header("+EV Discrepancy Engine")
        st.info("Displays real-time +EV opportunities from the ev_engine.")
        # TODO: fetch from /api/opportunities and display as sortable table
        st.dataframe({"status": ["Connect to API"]})

    with tab_clv:
        st.header("Closing Line Value Tracker")
        st.info("Rolling CLV with significance testing.")
        # TODO: fetch from /api/clv/summary and display charts
        st.metric("Avg CLV (90d)", "--", help="Average CLV over last 90 days")

    with tab_parlays:
        st.header("Correlated Parlay Builder")
        st.info("Parlays with identified positive correlation between legs.")
        # TODO: fetch from /api/parlays
        st.dataframe({"status": ["Connect to API"]})

    with tab_bankroll:
        st.header("Bankroll & P/L")
        st.info("Cumulative P&L, drawdown chart, per-sport breakdown.")
        # TODO: fetch from /api/bankroll
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Bankroll", "--")
        col2.metric("Net P/L", "--")
        col3.metric("ROI", "--")

    with tab_model:
        st.header("Model Performance")
        st.info("Accuracy, Brier score, and calibration by sport and market.")
        # TODO: fetch from model leaderboard view
        st.dataframe({"status": ["Connect to API"]})


if __name__ == "__main__":
    main()
