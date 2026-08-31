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

## Probe provenance

`summary.csv` was produced by the two-axis probe of paper Sect. 5:

| File | sha256 (on disk, 2026-08-30) |
|---|---|
| `code/probe_input.py` | `7bb05e02582755fa1a91d0425bfcb83d1f2501e3a012e2918ac515ea09d0938c` |
| `code/layer_4_oracle.py` | `b4e2cd54c107f3a68797bec6fdd131412efd63e6e64dd22d93ffe42e0495cd55` |

**Committed 2026-08-31** on branch `paper/block-0`:

| Item | Commit |
|---|---|
| v3 testbed (`fs_server.py`, `inspector.py`, `run_agent.py`, `run_trial.py`, `tasks.py`) | `9a8cf8b6ef92eb2e11674c2b40ecedefece5fd72` — `exp: freeze v3 testbed (D6/D7 operators + canary infrastructure)` |
| Probe (`probe_input.py`, `layer_4_oracle.py`) | `1e0b6f704296253bfc7a25bf09fcd496a060331a` — `exp: add two-axis probe (paper §5)` |

Until then these two probe files were untracked, never committed (verified
2026-08-30: `git status --porcelain code/` showed both as `??`; `git log --all`
for each was empty). They were deliberately kept off `paper/block-0` while
`code/` was still in progress, then committed as Block 2 came up.

**Verification done at commit time (2026-08-31, same session):**
- `tasks.py`: all 30 task definitions
  (`id/base/label/fault_mode/task/seed/canary/canary_in_seed`) byte-identical
  to those recorded in the frozen `trials.json` — canonical sha256 match, 0
  field diffs across 210 comparisons. The `tasks.py` source diff vs. the
  initial commit is reformatting only.
- On-disk probe sha256 == the values in the table above (unchanged since the
  baseline was frozen), so the committed probe is the exact version that
  produced this `summary.csv`.
- `python scripts/rescore_baseline.py` re-ran the committed probe over
  `trials.json` and reproduced `summary.csv` **byte-identical**
  (sha256 `0fbf695bb8e40218cb8172306401ab2d947d186482dd8520c2d8d036caecfa99`,
  `git status` clean).

**If the on-disk probe sha256 ever differs from the table above**, re-run
`python scripts/rescore_baseline.py` and confirm `summary.csv` is unchanged
before trusting the new probe.

`scripts/rescore_baseline.py` is the only script that imports these two files;
`regen_all.py` and `verify_all_numbers.py` read the frozen `summary.csv` and do
not.

## `ENABLE_THINKING` scope (Block 2 note)

`code/run_agent.py` sets `ENABLE_THINKING = False` and passes it as
`extra_body={"chat_template_kwargs": {"enable_thinking": ...}}`.

**This toggle only affects Qwen3.5-9B.** Llama-3.1-8B-Instruct and
Mistral-Nemo-12B-Instruct-2407 have no equivalent implicit-reasoning
mechanism: neither model's chat template references `enable_thinking` /
`thinking` / `reasoning` (checked directly against `tokenizer_config.json` /
model card, 2026-08-31), and vLLM silently ignores unknown
`chat_template_kwargs` keys. So the flag is a no-op on those two backbones —
harmless, but the paper must not imply "reasoning disabled" was applied
uniformly across all three.

Suggested §6 methodology line:
> Reasoning was disabled for Qwen3.5-9B (`enable_thinking=false`); the
> Llama-3.1 and Mistral-Nemo instruct variants have no equivalent reasoning
> toggle, so all three backbones were run in a single-pass, no-scratchpad
> regime.

### Mandatory Block-2 checklist — verify the toggle actually took effect

`enable_thinking=False` has been reported ignored on some vLLM / ms-swift
versions due to a parameter-name mismatch between the chat template and the
reasoning parser (`thinking` vs `enable_thinking`) — vLLM issue #43728,
ms-swift issue #5836.

**Before trusting all 300 Block 2 trials:** inspect the raw model output of
the *first* Qwen3.5-9B trial and confirm there is **no `<think>` block**. If a
`<think>` block is present, the toggle did not take — stop, fix the key /
vLLM version, and re-run the Qwen trials. (Llama/Mistral need no such check —
they never emit one.)

## Re-running the agent (needs the backbone endpoint)

```
cp .env.example .env    # set API_BASE, API_KEY, MODEL
python code/run_trial.py
```

Trajectories are model- and sampling-dependent; a fresh run will not be
byte-identical. This frozen copy is what the paper reports, and per the paper
(Sect. 6.5 / Limitations) **Table 2, Table 3 and Fig. 4 must stay reproducible
from this directory.**
