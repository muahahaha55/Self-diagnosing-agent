# exp_baseline / 2025_original  — FROZEN, DO NOT MODIFY

The single 30-trial run behind the paper's frozen evidence base:
**Table 2, Table 3, Table 4, Table 5, Fig. 4, Fig. 5** and every empirical number
in Sections 6.1–6.5.

| | |
|---|---|
| Backbone | Qwen3.5-9B, temperature 0, reasoning disabled |
| Serving | OpenAI-compatible endpoint (out of process); `API_BASE` / `MODEL` in `.env` (not checked in) |
| Agent | ReAct-over-MCP loop, `code/run_agent.py` (`MAX_STEPS = 10`) |
| Tool server | `code/fs_server.py` (6 tools + 7 drift operators) |
| Tasks | 30, from `code/tasks.py` (8 clean · 14 world_drift · 8 halluc) |
| Oracle inspector | `code/inspector.py` (two-tier world diff + canary check) |
| Run date | 2026-08-18 (`trials/trials_20260818_234558.json`) |
| `trials.json` sha256 | `df95a757a43354b6c7e077d9eb815594ad1ef0ab35db87d56d55c3f968d39cff` |

`trials.json` is a verbatim copy of `trials/trials_20260818_234558.json`. The
directory name follows the naming in `paper/CLAUDE_CODE_PROMPT.md`; the actual
run is from August 2026.

## Files

- `trials.json` — the raw run: 30 trial records, each with the full trajectory,
  recorded per-step and cumulative world effects, canary result, and tool specs.
  **The source of truth. Never edit.**
- `summary.csv` — one row per trial: designed + post-hoc-verified label, probe
  prediction, both axis outcomes and their reasons, canary evidence,
  visible/invisible flag. **Frozen provenance data** — it is the two-axis probe's
  output on `trials.json` and is checked in alongside it. Regenerate it only by
  re-running the probe: `python scripts/rescore_baseline.py` (see
  *probe provenance* below).
- `metrics.json` — every aggregate number the paper cites, regenerated from
  `summary.csv` by `scripts/regen_all.py`, grouped by the table / section it
  appears in.
- `derived/table{2,3,4,5}.tex` — reference fragments for eyeballing the paper's
  hand-written tables against the recomputed numbers. Not `\input` by the paper.

## Reproduce (no GPU, no network)

```
python scripts/regen_all.py            # rebuild metrics.json, table fragments, figures
python scripts/verify_all_numbers.py   # check the paper against summary.csv
```

Both read the checked-in `summary.csv` and need nothing from `code/`.

## Probe provenance (known limitation)

`summary.csv` was produced by the two-axis probe of paper Sect. 5:

| File | sha256 (on disk, 2026-08-30) |
|---|---|
| `code/probe_input.py` | `7bb05e02582755fa1a91d0425bfcb83d1f2501e3a012e2918ac515ea09d0938c` |
| `code/layer_4_oracle.py` | `b4e2cd54c107f3a68797bec6fdd131412efd63e6e64dd22d93ffe42e0495cd55` |

**Git status of these two files at the time the baseline was frozen:**
untracked, never committed — verified 2026-08-30 with `git status --porcelain code/`
(both shown as `??`) and `git log --all --oneline -- code/probe_input.py`
/ `-- code/layer_4_oracle.py` (both empty; not present in the first commit
`944c22b` nor any other ref).

They are deliberately **not** committed on branch `paper/block-0`, which is kept
separate from the still-in-progress `code/`. The probe will be committed
officially when Block 2 needs it. **When `code/` is committed, compare the sha256
above** to confirm that is the same probe version that generated this baseline's
`summary.csv`. If the sha256 differs, re-run `python scripts/rescore_baseline.py`
and check that `summary.csv` is unchanged before trusting the new probe.

`scripts/rescore_baseline.py` is the only script that imports these two files;
`regen_all.py` and `verify_all_numbers.py` read the frozen `summary.csv` and do
not.

## Re-running the agent (needs the backbone endpoint)

```
cp .env.example .env    # set API_BASE, API_KEY, MODEL
python code/run_trial.py
```

Trajectories are model- and sampling-dependent; a fresh run will not be
byte-identical. This frozen copy is what the paper reports, and per the paper
(Sect. 6.5 / Limitations) **Table 2, Table 3 and Fig. 4 must stay reproducible
from this directory.**
