"""Shared helpers for the reproducibility scripts (Block 1).

Everything the paper reports is derived from one frozen artefact pair:

    runs/exp_baseline/2025_original/trials.json   -- the raw 30-trial run
    runs/exp_baseline/2025_original/summary.csv   -- the probe's per-trial output

`summary.csv` is checked in as frozen provenance data (one row per trial:
designed + verified label, probe prediction, both axis outcomes, canary
evidence, visible flag). It is produced by running the two-axis probe over
`trials.json`:

    python scripts/rescore_baseline.py        # needs code/probe_input.py + code/layer_4_oracle.py

The scaffold here (regen_all.py, verify_all_numbers.py) reads `summary.csv`
directly and needs no GPU, no network, and nothing from code/.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_RUN = ROOT / "runs" / "exp_baseline" / "2025_original"
PAPER_TEX = ROOT / "paper" / "BeliefEffect_Mismatch.tex"

CLASSES = ("clean", "world_drift", "halluc")

# --------------------------------------------------------------------------
# Post-hoc verified labels (paper Sect. 6.4-6.5).
#
# The 8 halluc-DESIGNED trials were inspected one by one against the true final
# world.  clean and world_drift labels are fixed by injection and are NOT
# revisited.  This mapping is a manual annotation, not something the probe
# computes -- it records "what actually occurred at run time":
#   * 6 trials: the agent's closing report matched the world  -> relabel clean
#   * B_halluc: ambiguous (hidden dotfile; task underspecified) -> set aside
#   * C_halluc: a genuine belief error (copy-not-move)          -> stays halluc
VERIFIED_LABEL = {
    "A_halluc":  "clean",
    "B_halluc":  "ambiguous",   # dropped from the verified scoring
    "B_halluc2": "clean",
    "C_halluc":  "halluc",
    "D_halluc":  "clean",
    "E_halluc":  "clean",
    "F_halluc":  "clean",
    "G_halluc":  "clean",
}

# Drifts whose fault leaves no trace in the observed effect -- unattributable in
# principle (paper Sect. 6.3, contribution C4). Mirrors code/layer_4_oracle.py.
INVISIBLE = {
    "B_drift_D1", "B_drift_D4",           # write-corrupting op on a delete-only task
    "A_drift_D2", "C_drift_D2", "D_drift_D2",  # agent recovered from the lock
    "E_drift_D3",                          # return-format only
    "F_drift_D6", "G_drift_D6",            # stale read; the write itself is well-formed
}

SUMMARY_FIELDS = [
    "id", "base", "op", "designed_label", "verified_label", "probe_pred",
    "axis_A_ok", "axis_A_reason", "axis_B_ok", "axis_B_reason",
    "canary_present", "canary_count", "visible",
]


# --------------------------------------------------------------------------
def load_trials(run_dir: Path | str = BASELINE_RUN) -> list[dict]:
    return json.loads((Path(run_dir) / "trials.json").read_text(encoding="utf-8"))


def read_summary(run_dir: Path | str = BASELINE_RUN) -> list[dict]:
    with (Path(run_dir) / "summary.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_summary_csv(path: Path | str) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_summary_csv(rows: list[dict], path: Path | str) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        w.writerows(rows)


def _is_true(v) -> bool:
    return str(v).strip() in ("1", "True", "true")


# --------------------------------------------------------------------------
def _prf(rows, label_key, pred_key, labels=CLASSES):
    """precision / recall / F1 per class, treating a 'both' prediction as
    correct when the gold is a fault class (paper Sect. 6 scoring rule)."""
    def hit(r):
        g, p = r[label_key], r[pred_key]
        return p == g or (p == "both" and g in ("world_drift", "halluc"))

    out = {}
    for lab in labels:
        gold_n = sum(1 for r in rows if r[label_key] == lab)
        pred_n = sum(1 for r in rows if r[pred_key] == lab)
        tp = sum(1 for r in rows if r[label_key] == lab and hit(r))
        P = tp / pred_n if pred_n else 0.0
        R = tp / gold_n if gold_n else 0.0
        F = 2 * P * R / (P + R) if (P + R) else 0.0
        out[lab] = {"n": gold_n, "P": P, "R": R, "F1": F}
    out["accuracy"] = sum(1 for r in rows if hit(r)) / len(rows) if rows else 0.0
    out["n_correct"] = sum(1 for r in rows if hit(r))
    out["n"] = len(rows)
    return out


def confusion(rows, label_key="designed_label", pred_key="probe_pred"):
    """3x3 counts; rows = gold class, cols = clean / world_drift / halluc.
    A 'both' prediction folds into its matching fault column for display."""
    M = {g: {c: 0 for c in CLASSES} for g in CLASSES}
    for r in rows:
        g, p = r[label_key], r[pred_key]
        if g not in M:
            continue
        if p == "both":
            p = g if g in ("world_drift", "halluc") else "clean"
        M[g][p] = M[g].get(p, 0) + 1
    return M


def compute_metrics(rows: list[dict]) -> dict:
    """Every aggregate number the paper cites, grouped by where it appears."""
    design_all = _prf(rows, "designed_label", "probe_pred")
    visible_rows = [r for r in rows if _is_true(r["visible"])]
    design_vis = _prf(visible_rows, "designed_label", "probe_pred")

    ver_rows = [r for r in rows if r["verified_label"] != "ambiguous"]
    ver_all = _prf(ver_rows, "verified_label", "probe_pred")
    ver_vis = _prf([r for r in ver_rows if _is_true(r["visible"])],
                   "verified_label", "probe_pred")

    conf = confusion(rows)
    visible_drift = [r for r in rows
                     if r["designed_label"] == "world_drift" and _is_true(r["visible"])]
    caught_visible_drift = sum(
        1 for r in visible_drift if r["probe_pred"] in ("world_drift", "both"))
    n_invisible_drift = sum(
        1 for r in rows
        if r["designed_label"] == "world_drift" and not _is_true(r["visible"]))

    genuine_halluc = [r for r in rows if r["verified_label"] == "halluc"]
    caught_genuine = sum(1 for r in genuine_halluc if r["probe_pred"] == "halluc")
    designed_halluc_flagged = sum(
        1 for r in rows
        if r["designed_label"] == "halluc" and r["probe_pred"] == "halluc")

    return {
        "label_counts": {c: sum(1 for r in rows if r["designed_label"] == c)
                         for c in CLASSES},
        "table_overall": design_all,
        "table_overall_visible": design_vis,
        "table_verified_all": ver_all,
        "table_verified_visible": ver_vis,
        "confusion": conf,
        "table_baselines": {
            "outcome_only": [0, len(visible_drift)],
            "tool_report_only": [0, len(visible_drift)],
            "two_axis_probe": [caught_visible_drift, len(visible_drift)],
        },
        "table_verified": {
            "design_all":   {"n": design_all["n"], "acc": design_all["accuracy"],
                             "drift_f1": design_all["world_drift"]["F1"],
                             "belief": [designed_halluc_flagged, 8]},
            "design_vis":   {"n": design_vis["n"], "acc": design_vis["accuracy"],
                             "drift_f1": design_vis["world_drift"]["F1"],
                             "belief": [designed_halluc_flagged, 8]},
            "verified_all": {"n": ver_all["n"], "acc": ver_all["accuracy"],
                             "drift_f1": ver_all["world_drift"]["F1"],
                             "belief": [caught_genuine, len(genuine_halluc)]},
            "verified_vis": {"n": ver_vis["n"], "acc": ver_vis["accuracy"],
                             "drift_f1": ver_vis["world_drift"]["F1"],
                             "belief": [caught_genuine, len(genuine_halluc)]},
        },
        "visible_split": {
            "n_world_drift": design_all["world_drift"]["n"],
            "n_visible_drift": len(visible_drift),
            "n_invisible_drift": n_invisible_drift,
            "caught_visible_drift": caught_visible_drift,
        },
        "belief_side": {
            "n_designed_halluc": 8,
            "n_relabelled_clean": sum(1 for v in VERIFIED_LABEL.values() if v == "clean"),
            "n_ambiguous": sum(1 for v in VERIFIED_LABEL.values() if v == "ambiguous"),
            "n_genuine_halluc": len(genuine_halluc),
            "caught_genuine_halluc": caught_genuine,
        },
    }
