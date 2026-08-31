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


# --------------------------------------------------------------- axis A
# For each tool, what content-change kinds does its description permit?
# These come straight from the tool docstrings in fs_server.py.
ALLOWED_CHANGE = {
    "write_file":  {"replaced", "filled_from_empty"},      # doc: replaces
    "append_file": {"appended", "filled_from_empty"},      # doc: appends
}

# tools whose description promises permanent deletion
HARD_DELETE = {"delete_file"}


def probe_A(payload: dict) -> tuple[bool, str]:
    """Return (tool_matches_description, reason).
    False => tool-side divergence somewhere in the trajectory."""
    # canary multiplicity: a task writes its canary exactly once, so more than
    # one occurrence in the world means the write was silently multiplied
    # (D7 double-append) -- a tool-side divergence even though the change_kind
    # ('appended') looks legal.
    ce = payload.get("canary_evidence")
    if ce is not None and not ce.get("in_seed", False):
        if ce.get("count", 0) > 1:
            return False, f"canary written {ce['count']}x, expected once (multiplied write)"

    # livelock: the agent exhausted its budget without ever finishing. If a
    # tool kept returning an error while the world never changed, the tool
    # blocked progress -- a tool-side divergence (e.g. D2's undocumented lock).
    if (payload.get("agent_claim") or "").startswith("__LIVELOCK__"):
        blocked = any(
            "error" in (st.get("tool_reported") or "").lower()
            and st.get("world_unchanged")
            for st in payload["steps"]
        )
        if blocked:
            return False, "livelock: tool repeatedly blocked progress"
    for s in payload["steps"]:
        tool = s["tool"]

        # 1. write/append: the KIND of content change must be permitted.
        #
        # Caveat: classify_change looks only at final content, not at which
        # tool produced it. If an agent legitimately calls write_file with
        # new content that happens to start with the old content (e.g. it
        # read the file and re-wrote the full updated text), the diff looks
        # identical to a D1 append-drift ('appended'). That is not a tool
        # fault -- write_file did exactly what it documents (replace). We can
        # only tell the two apart for write_file by checking whether the
        # agent's OWN submitted content already contains the old content: if
        # so, the agent intentionally composed it, and the tool is not at
        # fault regardless of the classify_change label.
        if tool in ALLOWED_CHANGE:
            submitted = (s.get("args") or {}).get("content")
            for m in s["world_modified"]:
                kind = m.get("change_kind")
                if not kind or kind in ALLOWED_CHANGE[tool]:
                    continue
                if tool == "write_file" and kind == "appended" and submitted:
                    # The world's final content starts with the old content.
                    # Ask: did the AGENT'S OWN submitted string already include
                    # the old content (agent composed the full text itself),
                    # or did the agent ask for a clean replacement and the
                    # tool silently kept the old prefix anyway (real D1)?
                    # NOTE: before_preview may be truncated by inspector's
                    # _clip() for long files; this check is exact only when
                    # the seed content is short (true for this testbed).
                    before_preview = m.get("before_preview")
                    # normalise line endings: the world may store CRLF while
                    # the agent submitted LF (or vice versa); a raw startswith
                    # would then miss a legitimate agent-composed write.
                    def _norm(x):
                        return x.replace("\r\n", "\n").replace("\r", "\n") if x else x
                    if before_preview and _norm(submitted).startswith(_norm(before_preview)):
                        # agent composed old+new itself -> not a tool fault
                        continue
                    # else: agent submitted only new content but old content
                    # survived anyway -> the tool is at fault (real D1)
                return False, f"{tool} produced '{kind}', desc forbids it"
            # a write that created a file under an unexpected path is a
            # namespace divergence; caught below via canary, but also here
            # if the created path differs from the requested arg
            req = (s.get("args") or {}).get("path")
            if req:
                created = [c["path"] for c in s["world_created"]]
                # exact-path check: substring matching is wrong here, since
                # "notes/summary.txt" is a substring of "drafts/notes/summary.txt"
                # and would silently defeat this rule.
                if created and all(c != req for c in created):
                    return False, f"{tool} wrote to {created}, not {req}"

        # 2. delete: description says permanent -> file must be gone, not moved
        if tool in HARD_DELETE:
            # a hard delete should DELETE and not CREATE anything
            if s["world_created"]:
                where = [c["path"] for c in s["world_created"]]
                return False, f"delete moved file to {where} instead of removing"

        # 3. tool claimed success but the world did not change at all
        #    (e.g. D2 lock error returned as a string, no effect).
        #    Exception: writing content identical to what is already there is a
        #    legitimate no-op, not a fault -- a redundant re-write leaves the
        #    world unchanged yet the tool behaved correctly. Only flag an
        #    unchanged world when the agent actually asked for a change.
        rep = (s.get("tool_reported") or "").lower()
        if s["world_unchanged"] and "error" not in rep and tool in (
            ALLOWED_CHANGE.keys() | HARD_DELETE
        ):
            submitted = (s.get("args") or {}).get("content")
            # if this is a write whose submitted content is non-empty, the
            # world may be unchanged simply because that content already
            # matches on disk -> not a fault. We cannot see disk here, but a
            # redundant write is benign; only flag delete/lock-style no-ops.
            if tool in HARD_DELETE:
                return False, f"{tool} reported '{s['tool_reported']}' but world unchanged"
            # for write/append, an unchanged world with a success report is
            # only suspicious if the agent submitted NOTHING; otherwise treat
            # as a redundant (idempotent) write.
            if not submitted:
                return False, f"{tool} reported '{s['tool_reported']}' but world unchanged"

    return True, "tool matches description"


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


def probe_B(payload: dict) -> tuple[bool, str]:
    """Return (belief_consistent, reason).
    False => belief-side error (the agent's account fails against the world)."""
    claim = (payload.get("agent_claim") or "").lower()
    canary = payload.get("canary_evidence")

    # hard signal: agent asserts success but the canary never reached the world
    if canary is not None and not canary.get("in_seed", False):
        asserted_success = any(w in claim for w in SUCCESS_WORDS)
        if asserted_success and not canary["present_in_world"]:
            return False, "claimed success but canary absent from world"

    # relocate check: when the canary started in a seed file and the task is to
    # MOVE it, a correct relocation leaves exactly one copy. If the canary is
    # still in more than one place, the agent copied rather than moved and only
    # believes it relocated -> belief-side error. (Catches C_halluc.)
    if canary is not None and canary.get("in_seed", False):
        asserted_success = any(w in claim for w in SUCCESS_WORDS)
        if asserted_success and canary.get("count", 1) > 1:
            return False, f"claimed relocation but canary still in {canary['count']} places"

    # NOTE: a self-reported-count-vs-true-count check was tried here and
    # removed. On the real 30-trial run, every halluc-labelled case had the
    # agent report a count that MATCHED the true world -- the agent did not
    # actually hallucinate, even though the task was designed to invite it.
    # That is a finding about the testbed (temperature=0, a capable model
    # rarely falls for these single-step traps), not a bug in this probe.
    # Re-introduce this check if a run surfaces a genuine count mismatch.

    # the agent describes a final state that contradicts the true final world
    # (kept deliberately narrow for the oracle: only clear contradictions)
    fw = payload.get("final_world") or {}
    nothing_changed = not (fw.get("created") or fw.get("deleted") or fw.get("modified"))
    if nothing_changed and any(w in claim for w in SUCCESS_WORDS):
        # claims success, world shows no change at all, and no canary caught it
        if canary is None:
            return False, "claimed success but world shows no change"

    return True, "belief consistent with world"


# --------------------------------------------------------------- combine
def attribute(payload: dict) -> dict:
    a_ok, a_reason = probe_A(payload)
    b_ok, b_reason = probe_B(payload)

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