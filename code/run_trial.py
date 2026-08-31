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


async def run_one(t: dict, ref_steps: dict, cell: dict | None = None) -> dict:
    """Run one task. `cell` selects the Block 2 matrix cell
    {backbone, temperature, seed}; None keeps the .env defaults (the regime
    that produced the frozen 30-trial baseline)."""
    cell = cell or {}
    inspector.reset(t.get("seed"))
    start = inspector.snapshot()
    prev = {"state": start}

    def on_step(record):
        now = inspector.snapshot()
        record["observed_effect"] = inspector.diff(prev["state"], now)
        prev["state"] = now

    out = await run_task(
        t["task"], t["fault_mode"], on_step=on_step, verbose=False,
        model=cell.get("backbone"), temperature=cell.get("temperature", 0.0),
        seed=cell.get("seed"),
    )

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
        # NOTE two different "seeds" meet here, keep them apart:
        #   seed          -- the WORLD seed: the dict of files the sandbox is
        #                    reset to before the agent runs (from tasks.py).
        #   sampling_seed -- the DECODER seed passed to the backbone. Only set
        #                    at temperature 0.7; at 0.0 decoding is greedy.
        # The Block 2 summary.csv column called `seed` is the sampling one.
        "seed": t.get("seed"),
        "backbone": out["run_config"]["model"],
        "temperature": out["run_config"]["temperature"],
        "sampling_seed": out["run_config"]["seed"],
        "enable_thinking": out["run_config"]["enable_thinking"],
        "thinking_seen": out["thinking_seen"],
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


# --------------------------------------------------------- Block 2 matrix
# 270 trials. Seed only creates real variance at T=0.7 -- at T=0 decoding is
# greedy and re-seeding reproduces the same trajectory bar float noise -- so
# seeds are not replicated at T=0.
#   T=0.0  3 backbones x 30 tasks x 1 seed  =  90
#   T=0.7  3 backbones x 30 tasks x 2 seeds = 180
BACKBONES = ["Qwen/Qwen3.5-9B",
             "meta-llama/Llama-3.1-8B-Instruct",
             "mistralai/Mistral-Nemo-Instruct-2407"]
SAMPLING_SEEDS = {0.0: [None], 0.7: [1234, 5678]}

# Only Qwen has an implicit reasoning block to suppress; Llama-3.1 and
# Mistral-Nemo have no equivalent toggle and vLLM ignores the unknown key.
THINKING_CAPABLE = ("qwen",)


def matrix(backbones=None) -> list[dict]:
    cells = []
    for bb in (backbones or BACKBONES):
        for temp, seeds in SAMPLING_SEEDS.items():
            for sd in seeds:
                cells.append({"backbone": bb, "temperature": temp, "seed": sd})
    return cells


def _thinking_capable(backbone: str) -> bool:
    return any(k in (backbone or "").lower() for k in THINKING_CAPABLE)


async def main(only=None, cell=None, strict_thinking=True):
    """Run the task set once, in one matrix cell.

    strict_thinking aborts the run if the FIRST trial on a thinking-capable
    backbone comes back with a reasoning trace despite enable_thinking=False.
    That flag has been silently ignored on some vLLM builds, and 270 trials in
    the wrong regime is not something to discover afterwards.
    """
    subset = [t for t in TASKS if (only is None or t["id"] in only)]

    # pass 1: clean tasks first, to learn the reference step count per base
    ref_steps = {}
    clean = [t for t in subset if t["label"] == "clean"]
    other = [t for t in subset if t["label"] != "clean"]
    results = []
    checked_thinking = False

    # One timestamped file for this run, written after EVERY trial so a dropped
    # tunnel or a killed instance never loses the whole batch. Resuming is easy:
    # pass the ids that are missing from the partial file.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = LOGDIR / f"trials_{stamp}.json"
    if cell:
        print(f"[cell] backbone={cell['backbone']} temp={cell['temperature']} "
              f"seed={cell['seed']}")

    for t in clean + other:
        print(f"running {t['id']:14s} label={t['label']:12s} fault={t['fault_mode']}")
        try:
            r = await run_one(t, ref_steps, cell)
        except Exception as e:
            print(f"  ERROR {type(e).__name__}: {e}")
            continue

        # MANDATORY first-trial check (PROVENANCE.md, Block-2 checklist)
        if not checked_thinking:
            checked_thinking = True
            bb = r["backbone"] or ""
            if r["thinking_seen"]:
                msg = (f"  !! reasoning trace present on {bb} despite "
                       f"enable_thinking={r['enable_thinking']}")
                if _thinking_capable(bb) and strict_thinking:
                    print(msg)
                    raise SystemExit(
                        "ABORT: enable_thinking=False did not take effect on "
                        f"{bb}. Known vLLM/ms-swift issue (parameter-name drift "
                        "between chat template and reasoning parser). Fix the "
                        "server or the key before running the matrix -- do not "
                        "trust these trials. Re-run with strict_thinking=False "
                        "only if you deliberately want the thinking regime.")
                print(msg + "  (not thinking-capable: unexpected, continuing)")
            else:
                print(f"  ok: no reasoning trace on {bb}")
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
    # Default: one cell using the .env defaults -- the regime that produced the
    # frozen 30-trial baseline. `--matrix` walks all 9 Block 2 cells (270
    # trials); `--plan` prints the matrix and exits without calling a backbone.
    args = sys.argv[1:]
    if "--plan" in args:
        cells = matrix()
        for c in cells:
            print(f"{c['backbone']:38s} T={c['temperature']}  seed={c['seed']}")
        print(f"\n{len(cells)} cells x {len(TASKS)} tasks = "
              f"{len(cells) * len(TASKS)} trials")
    elif "--matrix" in args:
        for c in matrix():
            asyncio.run(main(None, cell=c))
    else:
        ids = args or None
        asyncio.run(main(ids))