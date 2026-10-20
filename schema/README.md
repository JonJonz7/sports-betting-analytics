# schema/ (design for a live system; not used by the batch pipeline)

Postgres + TimescaleDB DDL for capturing live odds snapshots, bets and CLV over time
(`docker-compose.yml` starts it). The batch pipeline (`make run`) uses Parquet + DuckDB
instead. See ARCHITECTURE.md, "Live system (designed)", and docs/ROADMAP.md item 1.
