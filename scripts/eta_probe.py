#!/usr/bin/env python3
"""Time a handful of trials in one matrix cell to extrapolate the 270-trial ETA.

The point is a schedule estimate, not a separate experiment, so this runs the
REAL harness in the REAL cell and files what it produces into
`runs/exp_a/raw/<cell>.json` like any other attempt: the probe trials count
toward the 270 and the driver will not re-run them.

Timing is collected by wrapping `run_trial.run_one` rather than by
reimplementing the loop, so the mandatory enable_thinking abort in
`run_trial.main` still fires -- on a leak the SystemExit propagates out of
here and nothing further runs.

    usage: eta_probe.py [--backbone REPO] [--temperature T] [--seed S]
                        [--ids ID [ID ...]]
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
sys.path.insert(0, str(ROOT / "scripts"))

import run_trial                                     # noqa: E402
from run_exp_a import RAW, slug, load_cell, save_cell, fill_ref_steps, newest_log  # noqa: E402

# A clean task first (it sets the per-base reference), then the two fault
# shapes that share its base, so the sample spans the regimes a cell contains.
DEFAULT_IDS = ["A_clean", "A_drift_D1", "A_halluc"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", default=run_trial.BACKBONES[0])
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--ids", nargs="+", default=DEFAULT_IDS)
    args = ap.parse_args()

    cell = {"backbone": args.backbone, "temperature": args.temperature,
            "seed": args.seed}
    timings: list[tuple[str, float]] = []

    real_run_one = run_trial.run_one

    async def timed_run_one(t, ref_steps, c=None):
        t0 = time.time()
        try:
            return await real_run_one(t, ref_steps, c)
        finally:
            dt = time.time() - t0
            timings.append((t["id"], dt))
            print(f"  [timing] {t['id']:14s} {dt:6.1f}s")

    run_trial.run_one = timed_run_one

    started = time.time()
    asyncio.run(run_trial.main(args.ids, cell=cell))   # SystemExit propagates
    wall = time.time() - started

    # file the probe trials into the real cell so they are not re-run
    path = RAW / f"{slug(cell)}.json"
    rows = load_cell(path)
    done = {r["id"] for r in rows}
    log = newest_log(started)
    added = 0
    if log is not None:
        for r in load_cell(log):
            if r["id"] not in done:
                rows.append(r); done.add(r["id"]); added += 1
        save_cell(fill_ref_steps(rows), path)

    per = [d for _, d in timings]
    print("\n=== ETA probe ===")
    print(f"cell            {slug(cell)}")
    print(f"trials timed    {len(per)}")
    print(f"wall            {wall:.1f}s")
    if per:
        print(f"per-trial       min {min(per):.1f}s  mean {sum(per)/len(per):.1f}s  "
              f"max {max(per):.1f}s")
    print(f"filed into      {path.relative_to(ROOT)}  (+{added}, {len(rows)}/30)")

    (ROOT / "runs" / "exp_a" / "eta_probe.json").write_text(json.dumps(
        {"cell": slug(cell), "wall_seconds": round(wall, 1),
         "per_trial_seconds": {i: round(d, 1) for i, d in timings}},
        indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
