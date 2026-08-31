"""
Layer-4-with-oracle: the go/no-go test.

This is deterministic and rule-based ON PURPOSE. "Oracle" here does NOT mean an
LLM judge; it means we feed the two probes perfect information -- the true
observed effect, the tool's real description, the canary result -- and ask
whether the two-axis logic can recover the fault source. If it cannot even with
perfect input, the idea has a problem at its core. If it can, then swapping the
oracle for an LLM (the next, GPU-bound step) is a meaningful thing to measure.

  axis A  match(description, observed)  -> tool-side  (aleatoric)
  axis B  consistent(claim, world)      -> belief-side (epistemic)

  A ok  B ok   -> clean
  A fail B ok  -> world_drift
  A ok  B fail -> halluc
  A fail B fail-> both (halt + ask human)

A case the probes get wrong even here is an *unattributable* case: the fault
source cannot be read off the effect no matter how perfect the observation.
That set is contribution C4, not a bug -- we surface it explicitly.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_input import build_all
from probe_config import (AXIS_A_RULES, AXIS_B_RULES, FAIL, NO_SIGNAL, PASS,
                          ProbeConfig, RuleResult, aggregate)


# --------------------------------------------------------------- axis A
# For each tool, what content-change kinds does its description permit?
# These come straight from the tool docstrings in fs_server.py.
ALLOWED_CHANGE = {
    "write_file":  {"replaced", "filled_from_empty"},      # doc: replaces
    "append_file": {"appended", "filled_from_empty"},      # doc: appends
}

# tools whose description promises permanent deletion
HARD_DELETE = {"delete_file"}


def _norm(x):
    """Normalise line endings: the world may store CRLF while the agent
    submitted LF (or vice versa); a raw startswith would then miss a
    legitimate agent-composed write."""
    return x.replace("\r\n", "\n").replace("\r", "\n") if x else x


# --------------------------------------------------- axis A rules, one each
# Each returns a reason string when its condition holds, else None. Trial-level
# rules take the payload; step-level rules take one step. Splitting them out is
# what makes the ablation possible -- the logic inside each is byte-for-byte
# the logic that was previously inlined in probe_A.

def _a4_dup_canary(payload: dict) -> str | None:
    """A4: a task writes its canary exactly once, so more than one occurrence
    in the world means the write was silently multiplied (D7 double-append) --
    a tool-side divergence even though the change_kind ('appended') looks
    legal."""
    ce = payload.get("canary_evidence")
    if ce is not None and not ce.get("in_seed", False):
        if ce.get("count", 0) > 1:
            return f"canary written {ce['count']}x, expected once (multiplied write)"
    return None


def _a5_lock(payload: dict) -> str | None:
    """A5: the agent exhausted its budget without ever finishing. If a tool
    kept returning an error while the world never changed, the tool blocked
    progress -- a tool-side divergence (e.g. D2's undocumented lock)."""
    if (payload.get("agent_claim") or "").startswith("__LIVELOCK__"):
        blocked = any(
            "error" in (st.get("tool_reported") or "").lower()
            and st.get("world_unchanged")
            for st in payload["steps"]
        )
        if blocked:
            return "livelock: tool repeatedly blocked progress"
    return None


def _a1_content_diff(s: dict) -> str | None:
    """A1: the KIND of content change must be permitted by the tool's own
    description. Fires on ANY change_kind outside ALLOWED_CHANGE[tool] --
    'appended' and 'truncated' both occur on the baseline.

    Local exception (write_file + 'appended' only, not a general condition of
    the rule): classify_change looks only at final content, not at which tool
    produced it. If an agent legitimately calls write_file with new content
    that happens to start with the old content (e.g. it read the file and
    re-wrote the full updated text), the diff looks identical to a D1
    append-drift. That is not a tool fault. We tell the two apart by checking
    whether the agent's OWN submitted content already contains the old
    content: if so, the agent intentionally composed it and the tool is
    blameless regardless of the classify_change label.

    NOTE: before_preview may be truncated by inspector's _clip() for long
    files; this check is exact only when the seed content is short (true for
    this testbed).
    """
    tool = s["tool"]
    if tool not in ALLOWED_CHANGE:
        return None
    submitted = (s.get("args") or {}).get("content")
    for m in s["world_modified"]:
        kind = m.get("change_kind")
        if not kind or kind in ALLOWED_CHANGE[tool]:
            continue
        if tool == "write_file" and kind == "appended" and submitted:
            before_preview = m.get("before_preview")
            if before_preview and _norm(submitted).startswith(_norm(before_preview)):
                continue          # agent composed old+new itself
        return f"{tool} produced '{kind}', desc forbids it"
    return None


def _a2_relocation(s: dict) -> str | None:
    """A2: a write that created a file under an unexpected path is a namespace
    divergence. Purely path-diff -- needs no canary, so it survives
    use_canary=False.

    Exact-path check: substring matching is wrong here, since
    "notes/summary.txt" is a substring of "drafts/notes/summary.txt" and would
    silently defeat this rule.
    """
    tool = s["tool"]
    if tool not in ALLOWED_CHANGE:
        return None
    req = (s.get("args") or {}).get("path")
    if not req:
        return None
    created = [c["path"] for c in s["world_created"]]
    if created and all(c != req for c in created):
        return f"{tool} wrote to {created}, not {req}"
    return None


def _a3_soft_delete(s: dict) -> str | None:
    """A3: description says deletion is permanent -> the file must be gone,
    not moved. A hard delete should DELETE and not CREATE anything."""
    if s["tool"] not in HARD_DELETE:
        return None
    if s["world_created"]:
        where = [c["path"] for c in s["world_created"]]
        return f"delete moved file to {where} instead of removing"
    return None


def _a6_silent_noop(s: dict) -> str | None:
    """A6: the tool reported success but the world did not change at all
    (e.g. a D2 lock error returned as a plain string, with no effect).

    Distinct from A5, which requires a livelock AND an error in the tool
    return; A6 requires neither and fires on a normally-terminating run whose
    tool return carries no error at all.

    Exception: writing content identical to what is already there is a
    legitimate no-op, not a fault -- a redundant re-write leaves the world
    unchanged yet the tool behaved correctly. We cannot see disk here, so only
    delete/lock-style no-ops are flagged: a write/append is suspicious only if
    the agent submitted NOTHING.
    """
    tool = s["tool"]
    rep = (s.get("tool_reported") or "").lower()
    if not (s["world_unchanged"] and "error" not in rep
            and tool in (ALLOWED_CHANGE.keys() | HARD_DELETE)):
        return None
    if tool in HARD_DELETE:
        return f"{tool} reported '{s['tool_reported']}' but world unchanged"
    submitted = (s.get("args") or {}).get("content")
    if not submitted:
        return f"{tool} reported '{s['tool_reported']}' but world unchanged"
    return None


_A_TRIAL_RULES = {"A4": _a4_dup_canary, "A5": _a5_lock}
_A_STEP_RULES = {"A1": _a1_content_diff, "A2": _a2_relocation,
                 "A3": _a3_soft_delete, "A6": _a6_silent_noop}


def probe_A_detail(payload: dict,
                   config: ProbeConfig | None = None
                   ) -> tuple[bool, str, dict[str, RuleResult]]:
    """Run every enabled axis-A rule and return (ok, reason, per_rule).

    Evaluation order reproduces the original short-circuiting probe exactly:
    A4 and A5 once up front, then A1/A2/A3/A6 step-major over the trajectory.
    Every enabled rule is evaluated (needed for activation counts), but the
    reported reason is the FIRST failure in that order -- which is what the
    short-circuiting version would have returned.
    """
    config = config or ProbeConfig.full()
    events: list[RuleResult] = []
    per_rule: dict[str, RuleResult] = {}

    for rid in ("A4", "A5"):
        if not config.enabled(rid):
            per_rule[rid] = RuleResult(rid, NO_SIGNAL)
            continue
        reason = _A_TRIAL_RULES[rid](payload)
        res = RuleResult(rid, FAIL if reason else PASS, reason or "")
        events.append(res)
        per_rule[rid] = res

    live_step_rules = [r for r in ("A1", "A2", "A3", "A6") if config.enabled(r)]
    for rid in ("A1", "A2", "A3", "A6"):
        if rid not in live_step_rules:
            per_rule[rid] = RuleResult(rid, NO_SIGNAL)

    first_fail: dict[str, str] = {}
    for s in payload["steps"]:
        for rid in live_step_rules:
            reason = _A_STEP_RULES[rid](s)
            res = RuleResult(rid, FAIL if reason else PASS, reason or "")
            events.append(res)
            if reason and rid not in first_fail:
                first_fail[rid] = reason
    for rid in live_step_rules:
        per_rule[rid] = (RuleResult(rid, FAIL, first_fail[rid]) if rid in first_fail
                         else RuleResult(rid, PASS))

    ok, reason = aggregate(events)
    return ok, (reason if not ok else "tool matches description"), per_rule


def probe_A(payload: dict, config: ProbeConfig | None = None) -> tuple[bool, str]:
    """Return (tool_matches_description, reason).
    False => tool-side divergence somewhere in the trajectory."""
    ok, reason, _ = probe_A_detail(payload, config)
    return ok, reason


# --------------------------------------------------------------- axis B
SUCCESS_WORDS = ("confirm", "success", "wrote", "written", "created",
                 "added", "appended", "done", "complete", "saved")

import re

def _extract_claimed_count(claim: str) -> int | None:
    """Pull a self-reported count out of the agent's claim, e.g.
    'the file contains 2 lines' or '4 files total'. Best-effort, narrow on
    purpose: false positives here would corrupt axis B."""
    if not claim:
        return None
    m = re.search(r"(\d+)\s*(lines?|files?)", claim.lower())
    return int(m.group(1)) if m else None


def _true_line_count(final_world: dict, world_modified_previews: list[str]) -> int | None:
    """Best-effort true line count from the final content we have visibility
    into (the after_preview of the last modified file, if any)."""
    for prev in world_modified_previews:
        if prev is not None:
            return prev.count("\n") + (0 if prev.endswith("\n") else 1)
    return None


# --------------------------------------------------- axis B rules, one each

def _b1_canary_absent(payload: dict) -> str | None:
    """B1: hard signal -- the agent asserts success but the canary never
    reached the world."""
    claim = (payload.get("agent_claim") or "").lower()
    canary = payload.get("canary_evidence")
    if canary is not None and not canary.get("in_seed", False):
        if any(w in claim for w in SUCCESS_WORDS) and not canary["present_in_world"]:
            return "claimed success but canary absent from world"
    return None


def _b2_multi_location(payload: dict) -> str | None:
    """B2: when the canary started in a seed file and the task is to MOVE it, a
    correct relocation leaves exactly one copy. If the canary is still in more
    than one place, the agent copied rather than moved and only believes it
    relocated -> belief-side error. (Catches C_halluc.)"""
    claim = (payload.get("agent_claim") or "").lower()
    canary = payload.get("canary_evidence")
    if canary is not None and canary.get("in_seed", False):
        if any(w in claim for w in SUCCESS_WORDS) and canary.get("count", 1) > 1:
            return f"claimed relocation but canary still in {canary['count']} places"
    return None


def _b3_no_change(payload: dict) -> str | None:
    """B3: the agent describes a final state that contradicts the true final
    world -- claims success, the world shows no change at all, and no canary
    was carried to catch it. Kept deliberately narrow for the oracle: only
    clear contradictions.

    NOTE: a self-reported-count-vs-true-count check was tried here and
    removed. On the real 30-trial run, every halluc-labelled case had the agent
    report a count that MATCHED the true world -- the agent did not actually
    hallucinate, even though the task was designed to invite it. That is a
    finding about the testbed (temperature=0, a capable model rarely falls for
    these single-step traps), not a bug in this probe. Re-introduce this check
    if a run surfaces a genuine count mismatch.
    """
    claim = (payload.get("agent_claim") or "").lower()
    canary = payload.get("canary_evidence")
    fw = payload.get("final_world") or {}
    nothing_changed = not (fw.get("created") or fw.get("deleted") or fw.get("modified"))
    if nothing_changed and any(w in claim for w in SUCCESS_WORDS):
        if canary is None:
            return "claimed success but world shows no change"
    return None


_B_RULES = {"B1": _b1_canary_absent, "B2": _b2_multi_location,
            "B3": _b3_no_change}


def probe_B_detail(payload: dict,
                   config: ProbeConfig | None = None
                   ) -> tuple[bool, str, dict[str, RuleResult]]:
    """Run every enabled axis-B rule and return (ok, reason, per_rule).
    Order B1 -> B2 -> B3 reproduces the original short-circuit reason."""
    config = config or ProbeConfig.full()
    events: list[RuleResult] = []
    per_rule: dict[str, RuleResult] = {}

    for rid in AXIS_B_RULES:
        if not config.enabled(rid):
            per_rule[rid] = RuleResult(rid, NO_SIGNAL)
            continue
        reason = _B_RULES[rid](payload)
        res = RuleResult(rid, FAIL if reason else PASS, reason or "")
        events.append(res)
        per_rule[rid] = res

    ok, reason = aggregate(events)
    return ok, (reason if not ok else "belief consistent with world"), per_rule


def probe_B(payload: dict, config: ProbeConfig | None = None) -> tuple[bool, str]:
    """Return (belief_consistent, reason).
    False => belief-side error (the agent's account fails against the world)."""
    ok, reason, _ = probe_B_detail(payload, config)
    return ok, reason


# --------------------------------------------------------------- combine
def attribute(payload: dict, config: ProbeConfig | None = None) -> dict:
    """Combine the two axes into one attribution.

    With `config` omitted (or all flags on) this is the probe of Sect. 5,
    unchanged. `rules` carries the per-rule verdicts the ablation needs; the
    other keys are exactly what the pre-ablation version returned, so callers
    like scripts/rescore_baseline.py keep working untouched.
    """
    config = config or ProbeConfig.full()
    a_ok, a_reason, a_rules = probe_A_detail(payload, config)
    b_ok, b_reason, b_rules = probe_B_detail(payload, config)

    if a_ok and b_ok:
        pred = "clean"
    elif not a_ok and b_ok:
        pred = "world_drift"
    elif a_ok and not b_ok:
        pred = "halluc"
    else:
        pred = "both"

    return {
        "id": payload["id"],
        "gold": payload["gold_label"],
        "pred": pred,
        "axis_A": (a_ok, a_reason),
        "axis_B": (b_ok, b_reason),
        "arm": config.name,
        "rules": {**a_rules, **b_rules},
    }


# --------------------------------------------------------------- scoring
def score(rows: list[dict]) -> None:
    labels = ["clean", "world_drift", "halluc"]
    # map 'both' onto whichever gold it matches for scoring; report separately
    def norm(p):
        return p  # keep raw; 'both' counts as its own predicted bucket

    # confusion
    print("\\n=== per-trial ===")
    for r in rows:
        mark = "OK " if r["pred"] == r["gold"] or (
            r["pred"] == "both" and r["gold"] in ("world_drift", "halluc")
        ) else "XX "
        print(f"{mark}{r['id']:14s} gold={r['gold']:12s} pred={r['pred']:12s} "
              f"A={'ok' if r['axis_A'][0] else 'FAIL'} "
              f"B={'ok' if r['axis_B'][0] else 'FAIL'}")

    # precision/recall/F1 per class (treat 'both' as correct if gold is drift or halluc)
    def hit(r):
        return r["pred"] == r["gold"] or (
            r["pred"] == "both" and r["gold"] in ("world_drift", "halluc"))

    print("\\n=== per-class ===")
    for lab in labels:
        gold_n = sum(1 for r in rows if r["gold"] == lab)
        pred_n = sum(1 for r in rows if r["pred"] == lab)
        tp = sum(1 for r in rows if r["gold"] == lab and hit(r))
        prec = tp / pred_n if pred_n else 0.0
        rec = tp / gold_n if gold_n else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        print(f"{lab:12s} n={gold_n:2d}  P={prec:.2f} R={rec:.2f} F1={f1:.2f}")

    overall = sum(1 for r in rows if hit(r)) / len(rows) if rows else 0.0
    print(f"\\noverall attribution accuracy: {overall:.2f}  ({sum(1 for r in rows if hit(r))}/{len(rows)})")


# --------------------------------------------------------------- visibility
# A drift is *visible* if it left a trace in the observed effect that could,
# in principle, be attributed from the effect alone. This is a property of the
# (base, operator, trajectory) triple, read off the real effect signatures:
#   - invisible: the fault targets a tool the task never exercised, or the
#     agent recovered so the final world matches a clean run, or the drift is
#     purely in return-format / which-target with no world-effect difference.
# Reporting F1 on the visible subset separates "the probe is wrong" from
# "the effect carries no signal to be right about" (contribution C4).
INVISIBLE = {
    "B_drift_D1",  # D1 on write, but task B only deletes -> no write to corrupt
    "B_drift_D4",  # D4 on write, but task B only deletes
    "A_drift_D2",  # agent acquired lock and recovered -> final world clean
    "C_drift_D2",  # agent recovered from lock -> final world clean
    "D_drift_D2",  # agent recovered from lock -> final world clean
    "E_drift_D3",  # return-format only -> no world-effect difference
    "F_drift_D6",  # stale read -> write itself is well-formed; only wrong target
    "G_drift_D6",  # stale read -> same
}


def score_split(rows: list[dict]) -> None:
    """Report overall, then again on the visible-only subset."""
    def _f1(subset, labels=("clean","world_drift","halluc")):
        def hit(r):
            return r["pred"] == r["gold"] or (
                r["pred"] == "both" and r["gold"] in ("world_drift","halluc"))
        out = {}
        for lab in labels:
            gold_n = sum(1 for r in subset if r["gold"]==lab)
            pred_n = sum(1 for r in subset if r["pred"]==lab)
            tp = sum(1 for r in subset if r["gold"]==lab and hit(r))
            P = tp/pred_n if pred_n else 0.0
            R = tp/gold_n if gold_n else 0.0
            F = 2*P*R/(P+R) if (P+R) else 0.0
            out[lab] = (gold_n,P,R,F)
        acc = sum(1 for r in subset if hit(r))/len(subset) if subset else 0.0
        return out, acc

    print("\n=== ALL 30 trials ===")
    o,acc = _f1(rows)
    for lab,(n,P,R,F) in o.items():
        print(f"{lab:12s} n={n:2d}  P={P:.2f} R={R:.2f} F1={F:.2f}")
    print(f"overall accuracy: {acc:.2f}")

    # visible subset: drop invisible drifts (keep all clean + halluc + visible drift)
    vis = [r for r in rows if r["id"] not in INVISIBLE]
    print(f"\n=== VISIBLE subset ({len(vis)} trials; {len(INVISIBLE)} invisible drifts removed) ===")
    o2,acc2 = _f1(vis)
    for lab,(n,P,R,F) in o2.items():
        print(f"{lab:12s} n={n:2d}  P={P:.2f} R={R:.2f} F1={F:.2f}")
    print(f"visible accuracy: {acc2:.2f}")

    # drift-only detection on visible: can axis A find visible drift at all?
    visdrift = [r for r in vis if r["gold"]=="world_drift"]
    caught = sum(1 for r in visdrift if r["pred"] in ("world_drift","both"))
    print(f"\nvisible-drift detection: {caught}/{len(visdrift)} caught by axis A")


if __name__ == "__main__":
    payloads = build_all(sys.argv[1])
    rows = [attribute(p) for p in payloads]
    score(rows)
    score_split(rows)