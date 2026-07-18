#!/usr/bin/env python3
"""Coverage gap report for both OIUEEI stacks.

Runs the backend suite with coverage (JSON report) and, unless skipped, the
frontend suite with its V8 coverage, then prints the WORST-covered modules —
the places to point the Prime Directive at. A gap is an invitation to ask
"which behaviour here is unprotected?", never to write line-filler tests.

Usage (from the repo root):
    python .claude/skills/solid-testing/scripts/coverage_report.py
    python .claude/skills/solid-testing/scripts/coverage_report.py --backend-only
    python .claude/skills/solid-testing/scripts/coverage_report.py --worst 15
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BACKEND_JSON = REPO / ".coverage-report.json"
FRONTEND_SUMMARY = REPO / "frontend" / "coverage" / "coverage-summary.json"


def run(cmd, cwd):
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd).returncode


def backend(worst_n):
    rc = run(
        ["pytest", "-q", "--cov=core", f"--cov-report=json:{BACKEND_JSON}",
         "--cov-report=term:skip-covered"],
        cwd=REPO,
    )
    if not BACKEND_JSON.exists():
        print("backend: no coverage JSON produced", file=sys.stderr)
        return rc or 1
    data = json.loads(BACKEND_JSON.read_text())
    files = [
        (meta["summary"]["percent_covered"], path,
         meta["summary"]["num_statements"] - meta["summary"]["covered_lines"])
        for path, meta in data["files"].items()
        if meta["summary"]["num_statements"] > 0 and "/migrations/" not in path
    ]
    files.sort()
    total = data["totals"]["percent_covered"]
    print(f"\n== Backend total: {total:.2f}% — worst {worst_n} modules ==")
    for pct, path, missing in files[:worst_n]:
        print(f"  {pct:6.1f}%  {path}  ({missing} uncovered statements)")
    BACKEND_JSON.unlink(missing_ok=True)
    return rc


def frontend(worst_n):
    # vitest is configured with the json-summary reporter via --coverage;
    # fall back gracefully if the repo config only emits text.
    rc = run(["npm", "run", "test:coverage", "--silent", "--",
              "--coverage.reporter=text-summary", "--coverage.reporter=json-summary"],
             cwd=REPO / "frontend")
    if not FRONTEND_SUMMARY.exists():
        print("frontend: no coverage-summary.json (text summary above is authoritative)")
        return rc
    data = json.loads(FRONTEND_SUMMARY.read_text())
    total = data.pop("total")
    print("\n== Frontend totals (vs the vite.config ratchet) ==")
    for k in ("statements", "branches", "functions", "lines"):
        print(f"  {k:>10}: {total[k]['pct']}%")
    files = sorted(
        ((v["lines"]["pct"], k) for k, v in data.items() if v["lines"]["total"] > 0)
    )
    print(f"\n== Frontend worst {worst_n} files (line %) ==")
    for pct, path in files[:worst_n]:
        print(f"  {pct:6.1f}%  {path.replace(str(REPO / 'frontend') + '/', '')}")
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-only", action="store_true")
    ap.add_argument("--frontend-only", action="store_true")
    ap.add_argument("--worst", type=int, default=10, help="modules to list per stack")
    args = ap.parse_args()

    rc = 0
    if not args.frontend_only:
        rc |= backend(args.worst)
    if not args.backend_only:
        rc |= frontend(args.worst)
    print("\nReminder: a gap is a question ('which behaviour is unprotected?'),"
          " not a quota. See SKILL.md — the Prime Directive.")
    sys.exit(rc)


if __name__ == "__main__":
    main()
