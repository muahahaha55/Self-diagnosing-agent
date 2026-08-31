#!/usr/bin/env python3
"""Regenerate runs/exp_baseline/2025_original/summary.csv from trials.json by
re-running the two-axis probe.

This is the ONE script that depends on the probe implementation in
    code/probe_input.py   +   code/layer_4_oracle.py
(both pure-stdlib, self-contained -- they import nothing else from code/).

The rest of the scaffold reads the checked-in summary.csv directly and needs
none of code/. Run this only when you have changed the probe and want to
re-derive the frozen per-trial output.

Usage:  python scripts/rescore_baseline.py [run_dir]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BASELINE_RUN, INVISIBLE, ROOT, VERIFIED_LABEL,
                    load_trials, write_summary_csv)

_PROBE_FILES = [ROOT / "code" / "probe_input.py",
                ROOT / "code" / "layer_4_oracle.py"]
_missing = [p for p in _PROBE_FILES if not p.exists()]
if _missing:
    sys.exit(
        "rescore_baseline.py needs code/probe_input.py + code/layer_4_oracle.py, "
        "which are not committed to the repo yet -- see PROVENANCE.md, section "
        "'probe_provenance', to check the sha256 once these two files are "
        "committed officially.\n"
        "  missing: " + ", ".join(str(p.relative_to(ROOT)) for p in _missing))

sys.path.insert(0, str(ROOT / "code"))
try:
    from probe_input import build_all
    from layer_4_oracle import attribute
except ModuleNotFoundError as e:                       # e.g. an incomplete probe
    sys.exit(
        f"rescore_baseline.py needs code/probe_input.py + code/layer_4_oracle.py "
        f"(the probe from paper Sect. 5), but importing it failed: {e}. "
        f"See PROVENANCE.md, section 'probe_provenance'.")


def rescore(run_dir: Path | str = BASELINE_RUN) -> list[dict]:
    run_dir = Path(run_dir)
    by_id = {t["id"]: t for t in load_trials(run_dir)}
    rows = []
    for payload in build_all(run_dir / "trials.json"):
        r = attribute(payload)
        t = by_id[r["id"]]
        cr = t.get("canary_result") or {}
        fm = t.get("fault_mode") or "none"
        rows.append({
            "id": r["id"],
            "base": t["base"],
            "op": "" if fm == "none" else fm,
            "designed_label": t["label"],
            "verified_label": VERIFIED_LABEL.get(r["id"], t["label"]),
            "probe_pred": r["pred"],
            "axis_A_ok": int(r["axis_A"][0]),
            "axis_A_reason": r["axis_A"][1],
            "axis_B_ok": int(r["axis_B"][0]),
            "axis_B_reason": r["axis_B"][1],
            "canary_present": int(bool(cr.get("present"))) if cr else "",
            "canary_count": cr.get("count", "") if cr else "",
            "visible": int(r["id"] not in INVISIBLE),
        })
    return rows


if __name__ == "__main__":
    rd = Path(sys.argv[1]) if len(sys.argv) > 1 else BASELINE_RUN
    rows = rescore(rd)
    write_summary_csv(rows, rd / "summary.csv")
    print(f"wrote {rd / 'summary.csv'}  ({len(rows)} trials)")
