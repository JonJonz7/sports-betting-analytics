"""
EdgeIQ command line.

    python -m src.cli all --source sample      # whole pipeline, offline
    python -m src.cli all --source nflverse    # real NFL data (downloads ~2 MB)
    python -m src.cli ingest|check|build|backtest|report [--source ...]

Exit code is non-zero when any step fails, so schedulers and CI notice.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import duckdb

from src.config import DATA_DIR, PROJECT_ROOT, WAREHOUSE_PATH


def cmd_ingest(args) -> int:
    from src.pipeline.ingest import run_ingest

    print(json.dumps(run_ingest(args.source), indent=1))
    return 0


def cmd_check(args) -> int:
    from src.pipeline.checks import run_checks

    errors = 0
    for check, failing in run_checks(DATA_DIR):
        status = "PASS" if failing == 0 else ("FAIL" if check.level == "error" else "WARN")
        print(f"  {status}  {check.name} ({failing})")
        errors += failing > 0 and check.level == "error"
    print("Bronze checks:", "FAILED" if errors else "passed")
    return 1 if errors else 0


def cmd_build(args) -> int:
    from src.pipeline.transform import build

    build(WAREHOUSE_PATH, DATA_DIR, select=getattr(args, "select", None))
    return 0


def cmd_backtest(args) -> int:
    from src.backtest.backtest import run_backtest

    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        _, summaries = run_backtest(con)
    finally:
        con.close()
    for s in summaries:
        print(
            f"  {s.strategy:20} bets={s.bets:5}  flat ROI={s.flat_roi:+.2%}  "
            f"95% CI [{s.flat_roi_ci_low:+.2%}, {s.flat_roi_ci_high:+.2%}]"
        )
    return 0


def cmd_report(args) -> int:
    from src.reporting import write_report

    name = "report_sample.md" if args.source == "sample" else "report.md"
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        path = write_report(con, PROJECT_ROOT / "reports" / name, args.source)
    finally:
        con.close()
    print(f"Report: {path}")
    return 0


def cmd_all(args) -> int:
    for step in (cmd_ingest, cmd_check, cmd_build, cmd_backtest, cmd_report):
        code = step(args)
        if code:
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edgeiq", description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [
        ("ingest", cmd_ingest),
        ("check", cmd_check),
        ("build", cmd_build),
        ("backtest", cmd_backtest),
        ("report", cmd_report),
        ("all", cmd_all),
    ]:
        p = sub.add_parser(name)
        p.add_argument("--source", choices=["nflverse", "sample"], default="nflverse")
        if name == "build":
            p.add_argument("--select", help="only rebuild models whose name contains this")
        p.set_defaults(func=fn)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
