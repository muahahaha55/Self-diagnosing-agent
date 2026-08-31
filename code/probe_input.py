"""
Assembles the Layer 4 probe payload from a trial record. Version 2.

The two binary probes need different evidence; keeping them separate here stops
them collapsing into one vague judgement.

  axis A  match(description, observed)   -- tool-side / aleatoric
          Did the tool do what its own documentation claims?
          Evidence per step: description, args, what the tool SAID, what the
          world ACTUALLY did (full modified_detail, not a summary line).

  axis B  consistent(claim, observed)    -- belief-side / epistemic
          Does the agent's account survive contact with the true world?
          Evidence: the agent's final claim, the cumulative effect, and -- when
          the task carried one -- the canary result. The canary is the hard
          part: a success claim with canary.present == False is a clean
          belief-side signal that needs no interpretation.

Also carried through for context (not probed directly):
  ref_clean_steps / n_tool_calls  -- how far this run drifted from the clean
                                     step budget for the same base.

Oracle-test note: Layer 1 is not built yet, so there is no recorded belief.
We proxy it with the agent's stated outcome (final_answer). When Layer 1 lands,
swap agent_claim for the recorded belief; the probe structure is unchanged.
"""

import json
from pathlib import Path


def _descriptions(trial: dict) -> dict:
    return {s["name"]: s["description"] for s in trial.get("tool_specs", [])}


def build_probe_payload(trial: dict) -> dict:
    desc = _descriptions(trial)

    steps = []
    for rec in trial["trajectory"]:
        if not rec.get("tool"):
            continue
        eff = rec.get("observed_effect") or {}
        steps.append(
            {
                "step": rec["step"],
                "tool": rec["tool"],
                "description": desc.get(rec["tool"], ""),
                "args": rec["args"],
                "tool_reported": rec["raw_result"],
                "world_created": eff.get("created_detail", []),
                "world_deleted": eff.get("deleted", []),
                "world_modified": eff.get("modified_detail", []),
                "world_unchanged": not (
                    eff.get("created") or eff.get("deleted") or eff.get("modified")
                ),
            }
        )

    cum = trial.get("cumulative_effect") or {}

    # axis B hard evidence: did the intended write actually land?
    canary_evidence = None
    cr = trial.get("canary_result")
    if cr is not None:
        canary_evidence = {
            "token": cr["canary"],
            "present_in_world": cr["present"],
            "locations": cr["locations"],
            "count": cr.get("count", 1 if cr["present"] else 0),
            "in_seed": trial.get("canary_in_seed", False),
        }

    return {
        "id": trial["id"],
        "task": trial["task"],
        "gold_label": trial["label"],        # never shown to the probe
        "steps": steps,
        "agent_claim": trial.get("final_answer"),
        "final_world": {
            "created": cum.get("created_detail", []),
            "deleted": cum.get("deleted", []),
            "modified": cum.get("modified_detail", []),
        },
        "canary_evidence": canary_evidence,   # axis B hard signal, may be None
        "step_budget": {
            "n_tool_calls": trial.get("n_tool_calls"),
            "ref_clean_steps": trial.get("ref_clean_steps"),
        },
    }


def build_all(trials_path: str | Path) -> list[dict]:
    trials = json.loads(Path(trials_path).read_text(encoding="utf-8"))
    return [build_probe_payload(t) for t in trials]


def strip_gold(payload: dict) -> dict:
    """What the probe is actually allowed to see."""
    return {k: v for k, v in payload.items() if k != "gold_label"}


if __name__ == "__main__":
    import sys
    payloads = build_all(sys.argv[1])
    print(json.dumps([strip_gold(p) for p in payloads], indent=2, ensure_ascii=False))