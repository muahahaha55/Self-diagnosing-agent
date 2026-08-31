#!/usr/bin/env python3
r"""Check every empirical number in the paper against the frozen run.

Parses paper/BeliefEffect_Mismatch.tex, pulls out every decimal of the form
``D.DD`` (probe metrics) and every ``N / M`` fraction ("15 of 30", "6 / 6",
"1 caught / 8 labelled"), and checks each against the numbers recomputed from
runs/*/summary.csv. Reports every token with a file:line pointer and PASS/FAIL.

Numbers that are *not* run-derived by construction are skipped, not checked:
the preamble, `\includegraphics`/`tabular` column specs, `\setlength` etc.,
percentages (cited third-party rates like 9.93\%), arXiv ids, and the
bibliography. Bare integers (confusion-matrix cells, trial counts) are out of
scope -- the prompt asks for ``0.XX`` and ``N / M`` only; regen_all.py prints the
integer-valued figures for a visual check.

Exit code 0 = all matched, 1 = at least one mismatch or a parse problem.

Usage:  python scripts/verify_all_numbers.py [paper.tex] [run_dir ...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PAPER_TEX, ROOT, compute_metrics, read_summary_csv

# ---- what to ignore ------------------------------------------------------
DROP_LINE = re.compile(r"^\s*\\(begin\{tabular|renewcommand|setlength|linespread"
                       r"|captionsetup|hypersetup|definecolor|sisetup|usepackage"
                       r"|documentclass|clubpenalty|widowpenalty|displaywidowpenalty)")
STRIP_SPANS = [
    re.compile(r"\\includegraphics\[[^\]]*\]\{[^}]*\}"),
    re.compile(r"\\(label|ref|cite|input|includegraphics)\{[^}]*\}"),
    re.compile(r"\\rowcolor\{[^}]*\}"), re.compile(r"\\cellcolor\{[^}]*\}"),
    re.compile(r"\\hspace\{[^}]*\}"),
    re.compile(r"arXiv:\S+"),
    re.compile(r"\d[\d,]*(?:\.\d+)?\s*\\?%"),          # percentages
    re.compile(r"\b20\d\d\b"),                          # years
    re.compile(r"table-format=[0-9.]+"),
]

# a metric decimal never sits directly after a letter or digit (that would make
# it part of an identifier such as "Qwen3.5-9B" or a version string)
DECIMAL = re.compile(r"(?<![\w.])\d\.\d{1,2}(?![\w])")
FRACTION = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b")
N_OF_M = re.compile(r"\b(\d{1,3})\s+of\s+(\d{1,3})\b")
N_CAUGHT_M = re.compile(r"\b(\d{1,3})\s+caught\s*/\s*(\d{1,3})\s+labelled\b")


def strip(line: str) -> str:
    line = line.split("%", 1)[0] if not line.strip().startswith("\\%") else line
    # cheap comment strip: LaTeX comments after an unescaped %
    line = re.sub(r"(?<!\\)%.*$", "", line)
    for pat in STRIP_SPANS:
        line = pat.sub(" ", line)
    return line


def body_lines(tex: str) -> list[tuple[int, str]]:
    out, active = [], False
    for i, raw in enumerate(tex.splitlines(), 1):
        if "\\begin{document}" in raw:
            active = True
            continue
        if "\\begin{thebibliography}" in raw:
            break
        if active:
            out.append((i, raw))
    return out


def norm_frac(a: int, b: int) -> str:
    return f"{a}/{b}"


def expected_values(run_dirs) -> tuple[set[str], set[str]]:
    """(decimals, fractions) that legitimately appear, recomputed from the run."""
    decs: set[str] = {"1.00"}
    fracs: set[str] = set()
    for rd in run_dirs:
        rows = read_summary_csv(Path(rd) / "summary.csv")
        m = compute_metrics(rows)

        def add_prf(block):
            for c in ("clean", "world_drift", "halluc"):
                for k in ("P", "R", "F1"):
                    decs.add(f"{block[c][k]:.2f}")
            decs.add(f"{block['accuracy']:.2f}")

        add_prf(m["table_overall"])
        tv = m["table_verified"]
        for key in ("design_all", "design_vis", "verified_all", "verified_vis"):
            decs.add(f"{tv[key]['acc']:.2f}")
            decs.add(f"{tv[key]['drift_f1']:.2f}")
            fracs.add(norm_frac(*tv[key]["belief"]))
        o = m["table_overall"]
        fracs.add(norm_frac(o["n_correct"], o["n"]))          # 15 / 30
        for v in m["table_baselines"].values():
            fracs.add(norm_frac(*v))                          # 0/6, 6/6
        # the visible / verified subset rows the paper also cites
        add_prf(m["table_overall_visible"])
        add_prf(m["table_verified_all"])
        add_prf(m["table_verified_visible"])
    return decs, fracs


def main() -> int:
    args = sys.argv[1:]
    tex_path = Path(args[0]) if args and args[0].endswith(".tex") else PAPER_TEX
    run_dirs = [a for a in args if not a.endswith(".tex")]
    if not run_dirs:
        run_dirs = sorted(str(p.parent) for p in
                          (ROOT / "runs").glob("*/*/summary.csv"))
    if not run_dirs:
        print("no runs/*/*/summary.csv found")
        return 1

    exp_dec, exp_frac = expected_values(run_dirs)
    tex = tex_path.read_text(encoding="utf-8")

    checks: list[tuple[int, str, str, bool]] = []   # line, kind, token, ok
    for lineno, raw in body_lines(tex):
        if DROP_LINE.match(raw):
            continue
        s = strip(raw)

        for m in N_CAUGHT_M.finditer(s):
            tok = f"{m.group(1)} caught / {m.group(2)} labelled"
            checks.append((lineno, "frac", tok,
                           norm_frac(int(m.group(1)), int(m.group(2))) in exp_frac))
        s2 = N_CAUGHT_M.sub(" ", s)
        for m in N_OF_M.finditer(s2):
            tok = f"{m.group(1)} of {m.group(2)}"
            checks.append((lineno, "frac", tok,
                           norm_frac(int(m.group(1)), int(m.group(2))) in exp_frac))
        for m in FRACTION.finditer(s2):
            tok = m.group(0)
            checks.append((lineno, "frac", tok,
                           norm_frac(int(m.group(1)), int(m.group(2))) in exp_frac))
        for m in DECIMAL.finditer(s):
            val = f"{float(m.group(0)):.2f}"
            checks.append((lineno, "dec", m.group(0), val in exp_dec))

    ok = [c for c in checks if c[3]]
    bad = [c for c in checks if not c[3]]

    print(f"paper : {tex_path.relative_to(ROOT)}")
    print(f"runs  : {', '.join(str(Path(r).relative_to(ROOT)) for r in run_dirs)}")
    print(f"tokens: {len(checks)} checked  ({len(ok)} matched, {len(bad)} mismatched)\n")

    for lineno, kind, tok, good in sorted(checks):
        flag = "  ok " if good else "FAIL "
        print(f"{flag}{tex_path.name}:{lineno:<4d} [{kind}] {tok!r}")

    if bad:
        print(f"\nRESULT: FAIL -- {len(bad)} token(s) not traceable to the run:")
        for lineno, kind, tok, _ in bad:
            print(f"  {tex_path.name}:{lineno}  {tok!r}")
        return 1
    print(f"\nRESULT: PASS -- all {len(ok)} empirical tokens trace to "
          f"{', '.join(Path(r).name for r in run_dirs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
