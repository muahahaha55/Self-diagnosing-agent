"""
Trial harness. This is the out-of-band oracle that surrounds each agent run.

For every task:
    reset(seed)              -> known clean world
    snapshot()  == before
    run_task(task, fault)    -> agent acts (never sees before/after)
    snapshot()  == after
    diff(before, after)      -> observed_effect (true world change)

The trial record pairs the ground-truth label (clean / world_drift / halluc)
with the true observed_effect. Layer 4 will later be fed this observed_effect
as oracle input; its job is to recover the label. That is the go/no-go test.

This file does NOT implement Layer 4. It only produces the labelled substrate.
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


async def run_one(t: dict) -> dict:
    inspector.reset(t.get("seed"))
    before = inspector.snapshot()

    trajectory = await run_task(t["task"], t["fault_mode"], verbose=False)

    after = inspector.snapshot()
    observed = inspector.diff(before, after)

    # attach the true observed_effect to the final tool step for reference
    for rec in reversed(trajectory):
        if rec.get("tool") is not None:
            rec["observed_effect"] = observed
            break

    final = next((r.get("final_answer") for r in trajectory
                  if r.get("final_answer")), None)

    return {
        "id": t["id"],
        "base": t["base"],
        "label": t["label"],            # ground truth
        "fault_mode": t["fault_mode"],
        "task": t["task"],
        "observed_effect": observed,    # true world change, oracle view
        "effect_empty": inspector.is_empty_effect(observed),
        "final_answer": final,
        "trajectory": trajectory,
    }


async def main(only=None):
    subset = [t for t in TASKS if (only is None or t["id"] in only)]
    results = []
    for t in subset:
        print(f"running {t['id']:12s} label={t['label']:12s} fault={t['fault_mode']}")
        try:
            r = await run_one(t)
        except Exception as e:
            print(f"  ERROR {type(e).__name__}: {e}")
            continue
        results.append(r)
        eff = r["observed_effect"]
        print(f"  effect: +{eff['created']} -{eff['deleted']} ~{eff['modified']}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = LOGDIR / f"trials_{stamp}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\n[log] {out}  ({len(results)} trials)")


if __name__ == "__main__":
    ids = sys.argv[1:] or None    # optionally pass specific task ids
    asyncio.run(main(ids))