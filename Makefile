###############################################################################
# EdgeIQ: NFL model vs the betting market
#
#   make setup    one-time: virtualenv + pinned dependencies
#   make demo     whole pipeline on the synthetic sample (no network)
#   make run      whole pipeline on real NFL data from nflverse (~2 MB download)
###############################################################################
.DEFAULT_GOAL := help
.PHONY: help setup demo run ingest check build backtest report test lint format api dashboard clean sample-data

VENV   := $(CURDIR)/.venv
PY     := $(VENV)/bin/python
SOURCE ?= nflverse

help: ## Show commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv and install pinned dependencies
	python3.11 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

demo: ## Full pipeline on the synthetic sample, in data/demo/ (no network)
	EDGEIQ_DATA_DIR=$(CURDIR)/data/demo $(PY) -m src.cli all --source sample

run: ## Full pipeline on real NFL games + closing lines (nflverse)
	$(PY) -m src.cli all --source nflverse

ingest: ## Land raw file + write bronze Parquet (SOURCE=nflverse|sample)
	$(PY) -m src.cli ingest --source $(SOURCE)

check: ## Quality gate on bronze
	$(PY) -m src.cli check

build: ## Build + test every model in sql/models.toml
	$(PY) -m src.cli build

backtest: ## Simulate betting the model's edges
	$(PY) -m src.cli backtest

report: ## Write reports/report.md
	$(PY) -m src.cli report --source $(SOURCE)

sample-data: ## Regenerate the synthetic sample
	$(PY) scripts/make_sample_games.py

test: ## All tests (unit + end-to-end on the sample)
	$(PY) -m pytest -q

lint: ## Lint + format check
	$(VENV)/bin/ruff check src tests scripts
	$(VENV)/bin/ruff format --check src tests scripts

format: ## Auto-fix lint and formatting
	$(VENV)/bin/ruff check --fix src tests scripts
	$(VENV)/bin/ruff format src tests scripts

api: ## FastAPI on http://localhost:8000/docs
	$(VENV)/bin/uvicorn src.api.main:app --reload

dashboard: ## Streamlit on http://localhost:8501
	PYTHONPATH=$(CURDIR) $(VENV)/bin/streamlit run src/dashboard/app.py

clean: ## Remove generated data (keeps data/sample)
	rm -rf data/landing data/lake data/demo data/warehouse.duckdb .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
