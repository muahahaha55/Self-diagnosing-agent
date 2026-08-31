"""
Trial harness, version 3.

Adds over v2:
  - canary_check per trial (when the task carries a canary): did the write
    actually land, and where. This is the hard evidence Layer 4 axis B needs.
  - a clean-reference step count per base, computed in a first pass over the
    clean tasks, so a faulted run can be measured against how many steps the
    same base needs when nothing is wrong.

Still out of band: the agent sees none of this.
"""

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inspector
from tasks import TASKS
from run_agent import run_task

ROOT = Path(__file__).resolve().parent.parent
LOGDIR = ROOT / "trials"
LOGDIR.mkdir(exist_ok=True)


async def run_one(t: dict, ref_steps: dict) -> dict:
    inspector.reset(t.get("seed"))
    start = inspector.snapshot()
    prev = {"state": start}

    def on_step(record):
        now = inspector.snapshot()
        record["observed_effect"] = inspector.diff(prev["state"], now)
        prev["state"] = now

    out = await run_task(t["task"], t["fault_mode"], on_step=on_step, verbose=False)

    end = inspector.snapshot()
    cumulative = inspector.diff(start, end)

    steps = [r for r in out["trajectory"] if r.get("tool")]
    first_effect_step = next(
        (r["step"] for r in steps
         if r["observed_effect"] and not inspector.is_empty_effect(r["observed_effect"])),
        None,
    )

    # canary evidence (only for tasks that declare one)
    canary_result = None
    if "canary" in t:
        canary_result = inspector.canary_check(t["canary"])

    return {
        "id": t["id"],
        "base": t["base"],
        "label": t["label"],
        "fault_mode": t["fault_mode"],
        "task": t["task"],
        "seed": t.get("seed"),
        "canary": t.get("canary"),
        "canary_in_seed": t.get("canary_in_seed", False),
        "canary_result": canary_result,
        "tool_specs": out["tool_specs"],
        "cumulative_effect": cumulative,
        "effect_empty": inspector.is_empty_effect(cumulative),
        "n_tool_calls": len(steps),
        "ref_clean_steps": ref_steps.get(t["base"]),
        "first_effect_step": first_effect_step,
        "final_answer": out["final_answer"],
        "trajectory": out["trajectory"],
    }


async def main(only=None):
    subset = [t for t in TASKS if (only is None or t["id"] in only)]

    # pass 1: clean tasks first, to learn the reference step count per base
    ref_steps = {}
    clean = [t for t in subset if t["label"] == "clean"]
    other = [t for t in subset if t["label"] != "clean"]
    results = []

    # One timestamped file for this run, written after EVERY trial so a dropped
    # tunnel or a killed instance never loses the whole batch. Resuming is easy:
    # pass the ids that are missing from the partial file.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = LOGDIR / f"trials_{stamp}.json"

    for t in clean + other:
        print(f"running {t['id']:14s} label={t['label']:12s} fault={t['fault_mode']}")
        try:
            r = await run_one(t, ref_steps)
        except Exception as e:
            print(f"  ERROR {type(e).__name__}: {e}")
            continue
        # record reference from the FIRST clean seen for each base
        if t["label"] == "clean" and t["base"] not in ref_steps:
            ref_steps[t["base"]] = r["n_tool_calls"]
            r["ref_clean_steps"] = r["n_tool_calls"]
        results.append(r)

        # flush to disk immediately (atomic-ish: temp then replace)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(out)

        cr = r["canary_result"]
        ctag = ""
        if cr is not None:
            ctag = f"  canary={'ok' if cr['present'] else 'MISSING'}"
            if cr["present"] and r["canary_in_seed"] is False and cr["locations"]:
                ctag += f"@{cr['locations'][0]}"
        print(f"  steps={r['n_tool_calls']} ref={r['ref_clean_steps']}  "
              f"{inspector.summarize(r['cumulative_effect'])}{ctag}  "
              f"[saved {len(results)}/{len(subset)}]")

    n_empty = sum(1 for r in results if r["effect_empty"])
    print(f"\n[log] {out}  ({len(results)} trials, {n_empty} with no effect)")


if __name__ == "__main__":
    ids = sys.argv[1:] or None
    asyncio.run(main(ids))