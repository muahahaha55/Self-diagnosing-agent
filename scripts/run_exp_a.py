#!/usr/bin/env python3
"""Block 2 (Experiment A) driver: walk the 270-trial matrix, one cell at a time.

Why this lives outside `code/`: the frozen harness `code/run_trial.py` knows how
to run the task set in ONE matrix cell, but nothing about serving. This host has
a single RTX 5090 (32 GiB), which does not hold two of the three backbones at
bf16 at once, so vLLM serves exactly one backbone at a time and the driver runs
that backbone's three cells before the weights are swapped. `--matrix` in
run_trial.py assumes all three backbones answer on the same endpoint, which is
not true here.

    T=0.0  3 backbones x 30 tasks x 1 seed  =  90
    T=0.7  3 backbones x 30 tasks x 2 seeds = 180
                                              ---
                                              270

Resume is by missing id. Each cell accumulates into
`runs/exp_a/raw/<backbone>_T<temp>_s<seed>.json`; on every attempt the driver
computes which of the 30 task ids that file is still missing and asks the
harness for only those. A trial that has completed is never re-run, so an OOM,
a dropped endpoint or a killed server costs only the trial in flight.

    usage: run_exp_a.py --backbone <hf-repo> [--dry-run]

The backbone named here must already be the one vLLM is serving.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))

import run_trial                      # noqa: E402  (needs the path insert above)
from tasks import TASKS               # noqa: E402

RAW = ROOT / "runs" / "exp_a" / "raw"
TRIALS_DIR = ROOT / "trials"
ALL_IDS = [t["id"] for t in TASKS]

# Escalation ladder for an attempt that completes zero new trials. Transient
# faults (OOM, a restarting server, a dropped connection) are retried without
# limit, but a run that makes no progress at all is more likely a served model
# that never came back, so the wait grows and the operator gets told.
BACKOFF = [10, 30, 60, 120, 300]
STALL_LIMIT = 12        # consecutive zero-progress attempts before giving up


def slug(cell: dict) -> str:
    bb = cell["backbone"].replace("/", "_")
    return f"{bb}_T{cell['temperature']}_s{cell['seed']}"


def cells_for(backbone: str) -> list[dict]:
    return [c for c in run_trial.matrix([backbone])]


def load_cell(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:            # a write killed mid-flight
        print(f"  [warn] {path.name} is unreadable, starting the cell over")
        return []


def save_cell(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def fill_ref_steps(rows: list[dict]) -> list[dict]:
    """Refill `ref_clean_steps` after a resume.

    `run_trial.main` learns the per-base clean reference in a first pass over
    the clean tasks. A resume that only asks for the missing ids skips that
    pass, so those trials come back with a null reference. The number is
    recoverable from the base's own completed clean trial, which is strictly
    better than re-running a trial that already succeeded.
    """
    ref = {r["base"]: r["n_tool_calls"] for r in rows if r["label"] == "clean"}
    for r in rows:
        if r.get("ref_clean_steps") is None:
            r["ref_clean_steps"] = ref.get(r["base"])
    return rows


def newest_log(since: float) -> Path | None:
    """The harness writes one timestamped file per invocation and returns
    nothing, so the driver picks up the file that invocation just created."""
    fresh = [p for p in TRIALS_DIR.glob("trials_*.json") if p.stat().st_mtime >= since]
    return max(fresh, key=lambda p: p.stat().st_mtime) if fresh else None


def run_cell(cell: dict) -> dict:
    """Run one matrix cell to completion. Returns a per-cell run report."""
    path = RAW / f"{slug(cell)}.json"
    rows = fill_ref_steps(load_cell(path))
    done = {r["id"] for r in rows}
    missing = [i for i in ALL_IDS if i not in done]

    print(f"\n=== cell {slug(cell)} ===")
    print(f"  {len(done)}/{len(ALL_IDS)} already complete, {len(missing)} to run")
    if not missing:
        return {"cell": slug(cell), "trials": len(rows), "attempts": 0, "retries": 0}

    attempts = 0
    stalls = 0
    t0 = time.time()
    while missing:
        attempts += 1
        started = time.time()
        try:
            # SystemExit from the mandatory enable_thinking check is deliberately
            # NOT caught here: `except Exception` does not cover BaseException,
            # so an abort propagates instead of being retried into a 270-trial
            # run in the wrong regime.
            asyncio.run(run_trial.main(missing, cell=cell))
        except Exception as e:
            print(f"  [retry] attempt {attempts} raised {type(e).__name__}: {e}")

        log = newest_log(started)
        if log is not None:
            fresh = {r["id"]: r for r in load_cell(log)}
            for i, r in fresh.items():
                if i not in done:
                    rows.append(r)
                    done.add(i)
            save_cell(fill_ref_steps(rows), path)

        before = len(missing)
        missing = [i for i in ALL_IDS if i not in done]
        gained = before - len(missing)
        print(f"  attempt {attempts}: +{gained} trials, {len(missing)} still missing")

        if missing:
            if gained == 0:
                stalls += 1
                if stalls >= STALL_LIMIT:
                    raise RuntimeError(
                        f"{slug(cell)}: {stalls} consecutive attempts completed no "
                        f"trial at all. This is no longer a transient fault -- the "
                        f"served backbone is most likely down. Still missing: "
                        f"{', '.join(missing)}")
                wait = BACKOFF[min(stalls - 1, len(BACKOFF) - 1)]
                print(f"  no progress ({stalls}/{STALL_LIMIT}); waiting {wait}s")
                time.sleep(wait)
            else:
                stalls = 0

    return {"cell": slug(cell), "trials": len(rows), "attempts": attempts,
            "retries": max(0, attempts - 1), "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", required=True,
                    help="HF repo of the backbone vLLM is currently serving")
    ap.add_argument("--dry-run", action="store_true",
                    help="print this backbone's cells and their resume state, "
                         "then exit without calling the endpoint")
    args = ap.parse_args()

    cells = cells_for(args.backbone)
    if not cells:
        sys.exit(f"no matrix cell for backbone {args.backbone!r}. Known: "
                 + ", ".join(run_trial.BACKBONES))

    if args.dry_run:
        for c in cells:
            rows = load_cell(RAW / f"{slug(c)}.json")
            print(f"{slug(c):58s} {len(rows)}/{len(ALL_IDS)} complete")
        return

    reports = []
    for c in cells:
        reports.append(run_cell(c))

    print(f"\n=== {args.backbone} done ===")
    total = sum(r["trials"] for r in reports)
    for r in reports:
        print(f"  {r['cell']:58s} {r['trials']:3d} trials, "
              f"{r.get('retries', 0)} retries")
    print(f"  {total} trials for this backbone")


if __name__ == "__main__":
    main()
