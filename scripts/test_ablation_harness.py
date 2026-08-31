#!/usr/bin/env python3
"""Phase A gate for the Block 2.5 ablation harness.

Four things must hold before any ablation arm is trusted:

  1. REGRESSION -- with every flag on, the harness reproduces the frozen
     30-trial baseline byte-identically (probe_pred and both axis reasons).
     This proves the harness's "full" mode is the real probe of Sect. 5.

  2. DISABLED IS NOT PASS -- a fully-disabled axis passes every trial, and a
     single-enabled-rule axis yields exactly that rule's firings and nothing
     else.

  3. SYNTHETIC COVERAGE -- A4, A5, A6, B1 and B3 never fire on the baseline,
     so (1) passes vacuously for them and proves nothing. Each gets a minimal
     hand-built payload: it must FAIL when the rule is enabled and return
     NO_SIGNAL when the rule is off.

  4. CANARY SCOPE -- use_canary=False disables A4/B1/B2 and nothing else; A2
     is path-diff based and must stay live.

Usage:  python scripts/test_ablation_harness.py
Exit 0 = all gates pass. Any failure exits non-zero and names the gate.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BASELINE_RUN, ROOT

sys.path.insert(0, str(ROOT / "code"))
from probe_config import (ALL_RULES, AXIS_A_RULES, AXIS_B_RULES, CANARY_RULES,
                          FAIL, NO_SIGNAL, PASS, ProbeConfig)
from probe_input import build_all
from layer_4_oracle import attribute

FAILURES: list[str] = []


def check(gate: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {gate}")
    else:
        print(f"  FAIL {gate}  {detail}")
        FAILURES.append(f"{gate}: {detail}")


# --------------------------------------------------------------- synthetic
def _payload(**kw) -> dict:
    """Minimal probe payload. Defaults are inert: no steps, no canary, a world
    that changed, and a claim with no success word -- so nothing fires unless
    the test deliberately switches one signal on."""
    base = {
        "id": "SYNTH",
        "task": "synthetic",
        "gold_label": "clean",
        "steps": [],
        "agent_claim": "no comment",
        "final_world": {"created": ["x.txt"], "deleted": [], "modified": []},
        "canary_evidence": None,
        "step_budget": {"n_tool_calls": 0, "ref_clean_steps": 0},
    }
    base.update(kw)
    return base


def _step(**kw) -> dict:
    base = {
        "step": 0, "tool": "write_file", "description": "",
        "args": {}, "tool_reported": "ok",
        "world_created": [], "world_deleted": [], "world_modified": [],
        "world_unchanged": False,
    }
    base.update(kw)
    return base


# One payload per zero-activation rule, built to trigger exactly that rule.
SYNTHETIC = {
    # A4: canary written twice (D7 double-append). Present in world, so B1
    # cannot fire; not in seed, so B2 cannot fire.
    "A4": _payload(
        agent_claim="appended the line",
        canary_evidence={"token": "abc123", "present_in_world": True,
                         "locations": ["log.txt"], "count": 2, "in_seed": False},
    ),
    # A5: agent never terminated, and a step both errored and left the world
    # unchanged. The error in the tool return is what keeps A6 off.
    "A5": _payload(
        agent_claim="__LIVELOCK__ budget exhausted",
        steps=[_step(tool="write_file", tool_reported="ERROR: file is locked",
                     world_unchanged=True)],
    ),
    # A6: delete reported success, world unchanged, no error in the return and
    # no livelock -- the two conditions that separate A6 from A5.
    "A6": _payload(
        agent_claim="the file is gone",
        steps=[_step(tool="delete_file", tool_reported="deleted old.txt",
                     args={"path": "old.txt"}, world_unchanged=True)],
    ),
    # B1: success claim, canary never reached the world.
    "B1": _payload(
        agent_claim="I wrote the file successfully",
        canary_evidence={"token": "abc123", "present_in_world": False,
                         "locations": [], "count": 0, "in_seed": False},
    ),
    # B3: success claim over a world showing no change, with no canary to
    # catch it (the no-canary fallback).
    "B3": _payload(
        agent_claim="done, file saved",
        final_world={"created": [], "deleted": [], "modified": []},
    ),
}


# --------------------------------------------------------------- gate 1
def gate_regression() -> None:
    print("\n[1] regression gate -- full arm vs frozen baseline")
    frozen = {r["id"]: r for r in
              csv.DictReader(open(BASELINE_RUN / "summary.csv", encoding="utf-8"))}
    rows = [attribute(p) for p in build_all(BASELINE_RUN / "trials.json")]

    check("trial count", len(rows) == len(frozen), f"{len(rows)} vs {len(frozen)}")
    mismatch = []
    for r in rows:
        f = frozen[r["id"]]
        if r["pred"] != f["probe_pred"]:
            mismatch.append(f"{r['id']} pred {r['pred']} != {f['probe_pred']}")
        if int(r["axis_A"][0]) != int(f["axis_A_ok"]):
            mismatch.append(f"{r['id']} axis_A_ok differs")
        if int(r["axis_B"][0]) != int(f["axis_B_ok"]):
            mismatch.append(f"{r['id']} axis_B_ok differs")
        if r["axis_A"][1] != f["axis_A_reason"]:
            mismatch.append(f"{r['id']} axis_A_reason {r['axis_A'][1]!r} != {f['axis_A_reason']!r}")
        if r["axis_B"][1] != f["axis_B_reason"]:
            mismatch.append(f"{r['id']} axis_B_reason {r['axis_B'][1]!r} != {f['axis_B_reason']!r}")
    check("byte-identical pred + both axis reasons", not mismatch,
          "; ".join(mismatch[:5]))


# --------------------------------------------------------------- gate 2
def gate_disabled_is_not_pass() -> None:
    print("\n[2] disabled != pass")
    payloads = build_all(BASELINE_RUN / "trials.json")

    # every rule off -> both axes pass everywhere -> everything predicted clean
    none_rows = [attribute(p, ProbeConfig.none()) for p in payloads]
    check("all-off: every axis passes",
          all(r["axis_A"][0] and r["axis_B"][0] for r in none_rows))
    check("all-off: every trial predicted clean",
          all(r["pred"] == "clean" for r in none_rows))
    check("all-off: every rule reports NO_SIGNAL",
          all(res.status == NO_SIGNAL
              for r in none_rows for res in r["rules"].values()))

    # full arm: which rules fire on which trials
    full_rows = {r["id"]: r for r in (attribute(p) for p in payloads)}
    fired_under_full = {
        rid: {tid for tid, r in full_rows.items() if r["rules"][rid].status == FAIL}
        for rid in ALL_RULES
    }

    # single-enabled-rule arm must reproduce exactly that rule's firings
    for rid in ALL_RULES:
        rows = {r["id"]: r for r in
                (attribute(p, ProbeConfig.single(rid)) for p in payloads)}
        axis_failed = {tid for tid, r in rows.items()
                       if not (r["axis_A"][0] and r["axis_B"][0])}
        check(f"only_{rid}: axis failures == {rid} firings under full",
              axis_failed == fired_under_full[rid],
              f"got {sorted(axis_failed)} want {sorted(fired_under_full[rid])}")
        others = {res.status for tid, r in rows.items()
                  for k, res in r["rules"].items() if k != rid}
        check(f"only_{rid}: all other rules NO_SIGNAL",
              others <= {NO_SIGNAL}, f"saw {others}")

    # axis knockouts
    a_only = [attribute(p, ProbeConfig.axis_a_only()) for p in payloads]
    check("axis_A_only: axis B passes everywhere",
          all(r["axis_B"][0] for r in a_only))
    check("axis_A_only: no trial predicted halluc or both",
          all(r["pred"] in ("clean", "world_drift") for r in a_only))
    b_only = [attribute(p, ProbeConfig.axis_b_only()) for p in payloads]
    check("axis_B_only: axis A passes everywhere",
          all(r["axis_A"][0] for r in b_only))
    check("axis_B_only: no trial predicted world_drift or both",
          all(r["pred"] in ("clean", "halluc") for r in b_only))


# --------------------------------------------------------------- gate 3
def gate_synthetic() -> None:
    print("\n[3] synthetic coverage for the zero-activation rules")
    payloads = build_all(BASELINE_RUN / "trials.json")
    for rid in ("A4", "A5", "A6", "B1", "B3"):
        # confirm the premise: this rule really never fires on the baseline
        never = all(attribute(p)["rules"][rid].status != FAIL for p in payloads)
        check(f"{rid}: zero activation on baseline (so gate 1 is vacuous)", never)

        p = SYNTHETIC[rid]
        on = attribute(p, ProbeConfig.single(rid))
        check(f"{rid}: fires on its synthetic payload",
              on["rules"][rid].status == FAIL,
              f"status={on['rules'][rid].status}")
        axis = on["axis_A"] if rid in AXIS_A_RULES else on["axis_B"]
        check(f"{rid}: its axis fails with that rule's reason",
              not axis[0] and axis[1] == on["rules"][rid].reason,
              f"axis={axis}")

        off = attribute(p, ProbeConfig.knockout(rid))
        check(f"{rid}: NO_SIGNAL when knocked out",
              off["rules"][rid].status == NO_SIGNAL,
              f"status={off['rules'][rid].status}")
        axis_off = off["axis_A"] if rid in AXIS_A_RULES else off["axis_B"]
        check(f"{rid}: its axis passes when knocked out", axis_off[0],
              f"axis={axis_off}")


# --------------------------------------------------------------- gate 4
def gate_canary_scope() -> None:
    print("\n[4] use_canary scope")
    cfg = ProbeConfig.no_canary()
    for rid in CANARY_RULES:
        check(f"no_canary: {rid} disabled", not cfg.enabled(rid))
    for rid in ("A1", "A2", "A3", "A5", "A6", "B3"):
        check(f"no_canary: {rid} still live", cfg.enabled(rid))
    check("no_canary: A2 is not treated as canary-dependent",
          "A2" not in CANARY_RULES)

    # under no_canary the payload carries no canary evidence at all
    payloads = build_all(BASELINE_RUN / "trials.json", cfg)
    check("no_canary: payloads carry no canary evidence",
          all(p["canary_evidence"] is None for p in payloads))
    rows = [attribute(p, cfg) for p in payloads]
    check("no_canary: A4/B1/B2 all NO_SIGNAL",
          all(r["rules"][rid].status == NO_SIGNAL
              for r in rows for rid in CANARY_RULES))

    # A2 must still be able to fire -- it caught 2 trials under full
    a2_full = sum(1 for p in build_all(BASELINE_RUN / "trials.json")
                  if attribute(p)["rules"]["A2"].status == FAIL)
    a2_nc = sum(1 for r in rows if r["rules"]["A2"].status == FAIL)
    check("no_canary: A2 firings unchanged", a2_full == a2_nc,
          f"full={a2_full} no_canary={a2_nc}")


if __name__ == "__main__":
    print("Block 2.5 Phase A -- ablation harness gates")
    gate_regression()
    gate_disabled_is_not_pass()
    gate_synthetic()
    gate_canary_scope()

    print()
    if FAILURES:
        print(f"RESULT: FAIL -- {len(FAILURES)} gate(s) failed")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("RESULT: PASS -- harness is safe to run ablation arms on")
