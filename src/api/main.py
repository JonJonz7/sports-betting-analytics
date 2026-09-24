"""FastAPI application -- REST + WebSocket API for EdgeIQ."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import load_config

app = FastAPI(
    title="EdgeIQ Sports Betting Analytics",
    description="Quantitative sports betting analytics engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down in production
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/predictions/{game_id}")
async def get_prediction(game_id: str):
    """Get model prediction for a specific game."""
    # TODO: query model_predictions table
    return {"game_id": game_id, "status": "not_implemented"}


@app.get("/api/opportunities")
async def get_opportunities(min_ev: float = 0.02, sport: str = "NBA"):
    """Get current +EV opportunities."""
    # TODO: run ev_engine.scan_for_ev against latest odds
    return {"opportunities": [], "min_ev": min_ev, "sport": sport}


@app.get("/api/clv/summary")
async def get_clv_summary(days: int = 90):
    """Get CLV summary statistics."""
    # TODO: query clv_records with rolling window
    return {"days": days, "status": "not_implemented"}


@app.get("/api/parlays")
async def get_correlated_parlays(sport: str = "NBA", min_edge: float = 0.02):
    """Get correlated parlay opportunities."""
    # TODO: run parlay_builder.find_correlated_parlays
    return {"parlays": [], "sport": sport}


@app.get("/api/splits/{entity_type}/{entity_id}")
async def get_splits(entity_type: str, entity_id: str):
    """Get contextual performance splits."""
    # TODO: query contextual_splits table
    return {"entity_type": entity_type, "entity_id": entity_id, "splits": {}}


@app.post("/api/injury/parse")
async def parse_injury(body: dict):
    """Parse an injury report using Claude API."""
    # TODO: call narrative_parser.parse_injury_report
    return {"status": "not_implemented"}


@app.get("/api/bankroll")
async def get_bankroll():
    """Get current bankroll status and P&L."""
    # TODO: query bankroll_ledger
    return {"status": "not_implemented"}
