"""
A small transformation runner: what dbt does, in ~150 lines you can read.

    python -m src.cli build

Reads sql/models.toml, then for each model in order:
  1. renders the SQL ({{ lake }} -> Parquet lake path, {{ ref('x.y') }} -> x.y)
     or calls a Python function that returns a DataFrame,
  2. materialises it in DuckDB (view or table) inside its schema,
  3. runs the model's tests and stops the build on the first failure.

Python models exist because some logic is naturally sequential (Elo ratings
update game by game) or needs a library (scikit-learn). They sit in the same
graph and are tested the same way.
"""

from __future__ import annotations

import importlib
import logging
import re
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from src.config import DATA_DIR, PROJECT_ROOT, WAREHOUSE_PATH

logger = logging.getLogger(__name__)

SQL_DIR = PROJECT_ROOT / "sql"
_REF = re.compile(r"\{\{\s*ref\('([\w.]+)'\)\s*\}\}")


class BuildError(RuntimeError):
    """A model failed to build or one of its tests failed."""


@dataclass
class Model:
    name: str
    kind: str
    path: str | None = None
    callable: str | None = None
    materialized: str = "table"
    tests: list[dict] = field(default_factory=list)

    @property
    def schema(self) -> str:
        return self.name.split(".")[0]


def load_models(path: Path = SQL_DIR / "models.toml") -> list[Model]:
    with open(path, "rb") as fh:
        return [Model(**m) for m in tomllib.load(fh)["model"]]


def render(sql: str, lake_dir: Path, built: set[str]) -> str:
    """Fill in the lake path and check that every ref() was built earlier."""

    def ref(match: re.Match) -> str:
        name = match.group(1)
        if name not in built:
            raise BuildError(f"ref('{name}') is used before it is built; reorder models.toml")
        return name

    return _REF.sub(ref, sql.replace("{{ lake }}", lake_dir.as_posix()))


def _test_sql(model: Model, test: dict) -> tuple[str, str]:
    """Return (label, SQL that counts failing rows)."""
    t, n = test["type"], model.name
    if t == "unique":
        cols = test.get("columns") or [test["column"]]
        key = ", ".join(cols)
        return (
            f"unique({key})",
            f"select count(*) from (select {key} from {n} group by {key} having count(*) > 1)",
        )
    if t == "not_null":
        return (
            f"not_null({test['column']})",
            f"select count(*) from {n} where {test['column']} is null",
        )
    if t == "expression":
        return (
            test.get("description") or test["sql"],
            f"select count(*) from {n} where not ({test['sql']})",
        )
    if t == "max_share":
        # table-level: fails (returns 1) when the share of rows matching `sql` exceeds `max`
        return (
            test.get("description") or f"share({test['sql']}) <= {test['max']}",
            f"select (avg(case when {test['sql']} then 1.0 else 0 end) > {test['max']})::int "
            f"from {n}",
        )
    if t == "row_count_equals":
        return (
            f"row count = {test['ref']}",
            f"select abs((select count(*) from {n}) - (select count(*) from {test['ref']}))",
        )
    raise BuildError(f"Unknown test type {t!r} on {n}")


def run_tests(con: duckdb.DuckDBPyConnection, model: Model) -> list[tuple[str, int]]:
    results = []
    for test in model.tests:
        label, sql = _test_sql(model, test)
        failing = con.execute(sql).fetchone()[0]
        results.append((label, failing))
        if failing:
            raise BuildError(f"{model.name}: test '{label}' failed ({failing} rows)")
    return results


def _drop(con: duckdb.DuckDBPyConnection, model: Model) -> None:
    """Drop whatever currently has this name. DuckDB refuses DROP VIEW on a table
    (and vice versa), so look up the existing object's type first."""
    schema, name = model.name.split(".")
    row = con.execute(
        "select table_type from information_schema.tables where table_schema = ? and table_name = ?",
        [schema, name],
    ).fetchone()
    if row:
        kind = "view" if row[0] == "VIEW" else "table"
        con.execute(f"drop {kind} {model.name}")


def build_model(
    con: duckdb.DuckDBPyConnection, model: Model, lake_dir: Path, built: set[str]
) -> None:
    con.execute(f"create schema if not exists {model.schema}")
    if model.kind == "sql":
        sql = render((SQL_DIR / model.path).read_text(), lake_dir, built)
        kind = "view" if model.materialized == "view" else "table"
        _drop(con, model)
        con.execute(f"create {kind} {model.name} as {sql}")
    elif model.kind == "python":
        module, func = model.callable.split(":")
        df = getattr(importlib.import_module(module), func)(con)
        con.register("_py_model", df)
        try:
            con.execute(f"create or replace table {model.name} as select * from _py_model")
        finally:
            con.unregister("_py_model")
    else:
        raise BuildError(f"Unknown model kind {model.kind!r}")


def build(
    warehouse: Path = WAREHOUSE_PATH, data_dir: Path = DATA_DIR, select: str | None = None
) -> list[dict]:
    """Build every model (or those whose name contains `select`) and test them."""
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    lake_dir = data_dir / "lake"
    con = duckdb.connect(str(warehouse))
    built: set[str] = set()
    report = []
    try:
        for model in load_models():
            started = time.perf_counter()
            if select and select not in model.name:
                built.add(model.name)  # assume already built; refs still resolve
                continue
            build_model(con, model, lake_dir, built)
            built.add(model.name)
            rows = con.execute(f"select count(*) from {model.name}").fetchone()[0]
            tests = run_tests(con, model)
            secs = time.perf_counter() - started
            logger.info("OK %-28s %7d rows  %d tests  %.2fs", model.name, rows, len(tests), secs)
            report.append(
                {"model": model.name, "rows": rows, "tests": len(tests), "seconds": round(secs, 2)}
            )
    finally:
        con.close()
    return report
