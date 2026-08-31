# Belief–Effect Mismatch — testbed and reproducibility

Controlled testbed for attributing tool-using-agent failures to a **tool-side**
cause (`world_drift`) or a **belief-side** cause (`halluc`), plus the
training-free two-axis probe that reads the fault source off the observed effect.

Paper: `paper/BeliefEffect_Mismatch.tex` (LNCS, → `paper/BeliefEffect_Mismatch.pdf`).

```
code/        testbed + agent + probe
  tasks.py            30 tasks (7 bases × operators, + halluc counterparts)
  fs_server.py        MCP filesystem server, 6 tools + 7 drift operators
  run_agent.py        ReAct-over-MCP agent loop (OpenAI-compatible endpoint)
  run_trial.py        harness: run tasks, snapshot the world per step
  inspector.py        out-of-band oracle: two-tier world diff + canary check
  probe_input.py      assemble the probe payload from a trial record
  layer_4_oracle.py   the two-axis probe (axis A / axis B) + scoring

runs/        frozen experiment outputs
  exp_baseline/2025_original/   the 30-trial Qwen3.5-9B run behind the paper
                               (see its PROVENANCE.md — DO NOT MODIFY)

scripts/     reproducibility (no GPU, no network)
  common.py               load a run's summary.csv, compute every paper number
  regen_all.py            rebuild metrics.json / table fragments / figures from summary.csv
  verify_all_numbers.py   check every 0.XX and N/M in the paper against runs/
  rescore_baseline.py     re-derive summary.csv by re-running the probe
                          (needs code/ committed — see known limitation in
                          runs/exp_baseline/2025_original/PROVENANCE.md)

paper/figs/src/   figure generators (fig1_gen.py, fig2_gen.py — matplotlib;
                  crop_fig4_fig5.py — crop the author's raster fig4/fig5)
```

## Quick start

```bash
python -m venv .venv && . .venv/Scripts/activate      # or .venv/bin/activate
pip install -r requirements.txt

python scripts/regen_all.py            # rebuild all derived artefacts
python scripts/verify_all_numbers.py   # → RESULT: PASS
```

## Regenerating each table / figure

The paper's tables are hand-written inline (not `\input`). "Regenerate" below
means: recompute the numbers from the frozen run and emit a reference fragment /
figure you can diff against the paper. All commands read only
`runs/exp_baseline/2025_original/` — no GPU.

| Paper element | What it shows | Command | Output to compare |
|---|---|---|---|
| **Table 2** `tab:overall` | per-class P/R/F1, acc 0.50 (15/30) | `python scripts/regen_all.py` | `runs/exp_baseline/2025_original/derived/table2.tex` |
| **Table 3** `tab:conf` | 3×3 confusion matrix | `python scripts/regen_all.py` | `.../derived/table3.tex` |
| **Table 4** `tab:baselines` | 0/6, 0/6, 6/6 visible-drift recovery | `python scripts/regen_all.py` | `.../derived/table4.tex` |
| **Table 5** `tab:verified` | design-time vs verified labels | `python scripts/regen_all.py` | `.../derived/table5.tex` |
| **Fig. 1** `fig:flow` | execution-flow schematic (no run data) | `python paper/figs/src/fig1_gen.py ../fig1_flow.png` | `paper/figs/fig1_flow.png` |
| **Fig. 2** `fig:matched` | matched-pairs + base×operator grid (no run data) | `python paper/figs/src/fig2_gen.py ../fig2_matched.png` | `paper/figs/fig2_matched.png` |
| **Fig. 3** `fig:conf` (`fig4_confusion.png`) | confusion matrix + visible/invisible split | author raster, no generator; numbers printed by `python scripts/regen_all.py` and checked by `verify_all_numbers.py` | `paper/figs/fig4_confusion.png` |
| **Fig. 4** `fig:verif` (`fig5_verif.png`) | design→verified protocol + halluc outcome (6 / 1 / 1) | author raster, no generator; numbers printed by `regen_all.py` | `paper/figs/fig5_verif.png` |
| every `0.XX` / `N/M` in §6 prose | — | `python scripts/verify_all_numbers.py` | stdout PASS/FAIL with line pointers |

`metrics.json` in the run directory holds every aggregate number keyed by where
it appears (`table_overall`, `confusion`, `table_baselines`, `table_verified`,
`visible_split`, `belief_side`).

## Post-hoc verified labels

Table 5 / §6.5 re-score against what actually occurred at run time. The 8
halluc-*designed* trials were inspected by hand (§6.4): 6 showed no belief error
(→ `clean`), `B_halluc` is ambiguous (set aside → 29 scored), `C_halluc` is a
genuine belief error the probe catches. This mapping lives in
`scripts/common.py::VERIFIED_LABEL`. `clean` and `world_drift` labels are fixed
by injection and never revisited.

## Re-running the 30-trial experiment (needs the backbone)

```bash
cp .env.example .env      # set API_BASE, API_KEY, MODEL for an OpenAI-compatible server
python code/run_trial.py  # writes trials/trials_<timestamp>.json
python code/layer_4_oracle.py trials/trials_<timestamp>.json
```

A fresh run is sampling-dependent and will not be byte-identical.
`runs/exp_baseline/2025_original/` is the frozen copy the paper reports; per the
paper, Table 2 / Table 3 / Fig. 3 must stay reproducible from it.
