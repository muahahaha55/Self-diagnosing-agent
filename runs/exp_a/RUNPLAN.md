# exp_a — Block 2 run plan and code-gap log

Status: **complete — 270/270 trials, not yet pushed**. This file is the running log for Block 2. It records the
allocation actually executed and every gap between what Block 2 asks for and what
the frozen v3 testbed can do.

## Allocation (settled 2026-08-31, supersedes the arithmetic in CLAUDE_CODE_PROMPT.md)

| Arm | Backbones | Tasks | Seeds | Trials |
|---|---|---|---|---|
| T = 0.0 (greedy) | 3 | 30 | 1 | 90 |
| T = 0.7 (sampling) | 3 | 30 | 2 | 180 |
| | | | **Total** | **270** |

Rationale for the asymmetry: at T=0 decoding is greedy, so a second seed
reproduces the first up to floating-point noise and buys no variance. All seed
budget is therefore spent at T=0.7, where sampling variance is real.

`CLAUDE_CODE_PROMPT.md` Block 2 states "300 trials = 3 backbones x 2 temperatures
x 3 seeds x the existing task set". With the actual task set of 30 that product is
540, not 300, and no T=0/T=0.7 split is given anywhere in the file. The 270-trial
table above is the allocation that was actually run.

## Backbones

| Role | Repo | Note |
|---|---|---|
| Qwen3.5-9B | `Qwen/Qwen3.5-9B` | `enable_thinking=false`; see the mandatory check below |
| Llama-3.1-8B-Instruct | `meta-llama/Llama-3.1-8B-Instruct` | gated repo; no HF token on this host — see "Llama access" |
| Mistral-Nemo-12B-Instruct | `mistralai/Mistral-Nemo-Instruct-2407` | |

Served sequentially, one at a time: this host has a single RTX 5090 (32 GiB), which
does not hold two of these backbones at bf16 concurrently.

## Code gaps found in the frozen v3 testbed — resolved upstream

Block 2 could not be executed against `code/` as frozen at `3718d19`. Two gaps,
both in `code/run_agent.py`:

1. **`temperature=0.0` was a hard-coded literal** in the
   `client.chat.completions.create(...)` call. There was no env var and no
   parameter, so the T=0.7 arm (180 of the 270 trials) was unreachable.
2. **`seed` was never passed to the API at all.** With no seed argument, the two
   T=0.7 seeds would have differed only by the server's own nondeterminism and
   would not be reproducible.

Both were fixed upstream in `19fc081` (pulled 2026-08-31), not in this session:
`run_task()` gained `model` / `temperature` / `seed` / `enable_thinking`
parameters that default to the previous behaviour, so the frozen 30-trial
baseline regime is still what an unparameterised call produces. The same commit
added the `matrix()` / `SAMPLING_SEEDS` definition of the nine cells and a
`thinking_seen` guard that aborts the run if a reasoning trace appears on a
thinking-capable backbone.

`probe_input.py`, `layer_4_oracle.py` and `probe_config.py` are untouched by
this block.

## Harness limitations worked around from outside `code/`

- `run_trial.py` has no backbone / temperature / seed dimension. Each arm is driven
  by env (`MODEL`, `API_BASE`, `TEMPERATURE`, `SAMPLING_SEED`) and its output file
  is filed under `runs/exp_a/raw/<backbone>_T<temp>_s<seed>.json`.
- `run_trial.py`'s resume is "pass the ids to run on argv"; it does not read a
  partial file. Missing ids are computed outside the harness and passed in, so no
  completed trial is ever re-run.
- On a resume that excludes the clean tasks, `ref_clean_steps` comes back null
  because the reference pass never runs. It is refilled during merge from the
  completed clean trial of the same base, rather than by re-running trials.

## Mandatory check — `enable_thinking` on Qwen

Per PROVENANCE.md: `enable_thinking=false` has been reported ignored on some vLLM
builds (vLLM #43728, ms-swift #5836). The raw output of the **first** Qwen trial is
inspected for a `<think>` block before any further Qwen trial runs. Result recorded
below.

- [x] first Qwen trial inspected (2026-08-31, `A_clean`, T=0, vLLM 0.28.0) — result:
      **no reasoning trace**. `thinking_seen=false`, and an independent sweep of the
      whole raw trial JSON finds no `<think>`, no `</think>` and no `reasoning_content`.
      `enable_thinking=false` is genuinely in effect on this build.

      The guard itself had to be fixed first, and the fix is load-bearing. Qwen3.5's
      chat template emits the OPENING `<think>` into the *prompt*, never the
      completion: with `enable_thinking=false` it prefills an already-closed
      `<think>\n\n</think>`, and when the flag is ignored it prefills a bare
      `<think>\n` and lets the model reason until it emits `</think>`. A leak
      therefore arrives as `...reasoning...</think>real answer`, with no `<think>`
      anywhere in `content` — and `_thinking_trace` tested only for the opening tag,
      so it would have passed the exact run it exists to catch. It now tests the
      closing tag as well. Trials run before that fix: none.

## Environment faults found on the restarted instance (2026-08-31)

Three environment breakages sat between vLLM 0.28.0 and the first trial. All are
serving/tooling faults, not experiment-design changes; none alters the regime.

1. **`torchaudio` 2.11+cu128 against `torch` 2.13+cu130.** transformers 5.16
   imports `torchaudio` from `audio_utils`, and its CUDA-version check aborts the
   import, so `vllm serve` died before touching the model. `torchaudio` was
   uninstalled — nothing in this repo or in vLLM's serving path uses it.
2. **FlashInfer sampler unusable on this GPU.** `RuntimeError: FlashInfer requires
   GPUs with sm75 or higher` on an RTX 5090, which is sm120: the system `nvcc` is
   12.8 and FlashInfer's JIT needs CUDA >= 12.9 to recognise SM 12.x, so it
   detected no eligible arch at all. Served with `VLLM_USE_FLASHINFER_SAMPLER=0`
   (torch-native top-k/top-p). Attention is unaffected — vLLM selects
   FlashAttention 2. Sampling semantics are unchanged, and T=0 is greedy anyway.
3. **`mcp` 2.x in the serving venv.** vLLM depends on `mcp` unpinned and pulled
   `/venv/main` to 2.1.1, where `FastMCP` is renamed `MCPServer`; `code/fs_server.py`
   is v1 code, so every trial failed at server start with `ModuleNotFoundError`
   (three trials aborted this way, none recorded). The harness now runs from its own
   venv at `/workspace/venv-harness`, built from the frozen `requirements.txt`
   (`mcp==1.29.0`, `openai==2.50.0`), and reaches the backbone over HTTP only. The
   serving venv keeps vLLM's own dependency versions. **Run the harness with
   `/workspace/venv-harness/bin/activate`, not `/venv/main`** — activation also puts
   the right `python` on PATH for the MCP subprocess `fs_server.py` is spawned as.

Serving command actually used for Qwen:

    VLLM_USE_FLASHINFER_SAMPLER=0 vllm serve Qwen/Qwen3.5-9B \
      --served-model-name Qwen/Qwen3.5-9B --max-model-len 16384 \
      --gpu-memory-utilization 0.90 --tool-call-parser qwen3_xml \
      --enable-auto-tool-choice --port 8000

`--max-model-len 16384` caps a config default of 262144, which leaves no KV cache
on a 32 GiB card. `qwen3_xml` matches this template's `<tool_call><function=...>`
form; without `--enable-auto-tool-choice` the server returns no `tool_calls` at all
and every trial would silently score zero steps.

## Timing probe (2026-08-31)

Measured on the three trials above, filed into the T=0 cell so they count toward
the 270 and are not re-run.

| Quantity | Measured |
|---|---|
| Model load, Qwen 9B (weights + torch.compile + CUDA graphs) | 331 s |
| Per trial | 1.7 s / 2.1 s (1 step), 3.8 s (3 steps) |
| Fit | ~0.95 s + ~0.95 s per tool call |
| Weight download | ~66 MB/s observed |

Against the baseline step distribution (30 trials, 90 tool calls, mean 3.0,
max 10) that is ~1.9 min per cell, ~17 min for all nine cells, plus ~5.5 min per
model load and the Llama/Mistral downloads.

## Outcome — 270/270 complete (2026-08-31)

**Read this paragraph and nothing else if you are catching up.** All nine cells
are at 30/30, one record per task id, no duplicates and no gaps. Nothing hit a
stop rule: no reasoning trace on any Qwen trial (nor anywhere in the other 180),
and no backbone was skipped. The three backbone runs each needed a serving fix
before their first trial, all documented below; none of them changed the
experiment. **The results are committed locally but NOT pushed — this host has
no GitHub credentials** (`git push` fails with "could not read Username"), so
three commits on `paper/block-0` are waiting for a push from somewhere that has
a token.

| Cell | Trials | Tool calls | Zero-step | No effect |
|---|---|---|---|---|
| Qwen3.5-9B T=0 | 30 | 85 | 0 | 0 |
| Qwen3.5-9B T=0.7 s1234 | 30 | 93 | 0 | 0 |
| Qwen3.5-9B T=0.7 s5678 | 30 | 82 | 0 | 0 |
| Llama-3.1-8B T=0 | 30 | 166 | 0 | 3 |
| Llama-3.1-8B T=0.7 s1234 | 30 | 153 | 0 | 2 |
| Llama-3.1-8B T=0.7 s5678 | 30 | 130 | 0 | 3 |
| Mistral-Nemo-12B T=0 | 30 | 70 | 0 | 4 |
| Mistral-Nemo-12B T=0.7 s1234 | 30 | 61 | 1 | 4 |
| Mistral-Nemo-12B T=0.7 s5678 | 30 | 78 | 0 | 3 |
| **Total** | **270** | **918** | **1** | **19** |

Integrity check over the merged raw files: every cell holds exactly the 30 task
ids, `backbone` / `temperature` / `sampling_seed` are single-valued per cell, and
no trial carries a null `ref_clean_steps`. 153 trials declare a canary; 11 of
those canaries are absent, which is a result about the fault modes, not a fault
in the run.

### The one zero-step trial is a parse failure, not a refusal

`E_halluc` in Mistral T=0.7 s1234 recorded `n_tool_calls=0`, and it is worth
knowing why before anyone treats it as "the model chose not to act". The model
emitted a malformed `[TOOL_CALLS]` block — several calls, mismatched brackets —
and the mistral parser declined it, so the whole thing survives as
`final_answer` text instead of as tool calls. The record is faithful and the raw
string is in the trial, but a step-count analysis will read this trial as a
zero-step success unless it is excluded or hand-scored. Re-running would not
help: the cell is seeded, so the same sampling path reproduces. 269 of 270
trials parsed cleanly, so this is one bad sample, not a parser mismatch.

### Serving fixes, per backbone

| Backbone | Parser | What it needed |
|---|---|---|
| Qwen3.5-9B | `qwen3_xml` | nothing beyond the three environment fixes below |
| Llama-3.1-8B-Instruct | `llama3_json` | nothing; worked first try |
| Mistral-Nemo-12B | `mistral` | an HF-only view of the snapshot + `--chat-template` (below) |

Mistral-Nemo took four attempts and none of the failures was the parser, which
is exactly the trap the stop rule was written for — each one *looked* like one:

1. Serving by repo id made vLLM go for `consolidated.safetensors`, a second
   22.8 GiB copy of weights already on disk as HF shards. With 12 GiB free the
   xet writer died mid-download ("File reconstruction error"). Fixed by serving
   the local snapshot directory (`SERVE_PATH` in `scripts/serve.sh`) while still
   advertising the canonical repo id as the model name.
2. Every request then failed with "As of transformers v4.44, default chat
   template is no longer allowed". transformers 5.x no longer reads
   `chat_template` out of `tokenizer_config.json`, and this repo predates the
   separate `chat_template.jinja` that Qwen and Llama ship. The template was
   copied verbatim into `configs/mistral_nemo_chat_template.jinja`.
3. Passing that file with `--chat-template` returned 501, "`MistralCommonBackend`
   does not implement `get_chat_template`": the presence of `tekken.json` and
   `params.json` in the directory makes vLLM choose Mistral's own tokenizer.
4. `--tokenizer-mode mistral` (the canonical Mistral path) rejects
   `chat_template_kwargs`, which `run_agent.py` sends on every call — so that
   route would have failed on all 90 trials, not just the smoke test.

What works: a directory of symlinks to the same snapshot with `tekken.json` and
`params.json` left out, which makes it an ordinary HF model, plus the repo's own
template via `--chat-template` and `--tool-call-parser mistral`. Rebuilt by
`scripts/pick_parser.sh`'s fallback path; the winning configuration is recorded
in `logs/parser_mistralai_Mistral-Nemo-Instruct-2407.txt`.

### Timing, measured

Model loads 331 s (Qwen, cold) / 266 s (Llama) / ~80 s (Mistral, warm compile
cache). Trials cost about 0.95 s + 0.95 s per tool call, so a 30-task cell runs
in roughly two to five minutes depending on how many steps the backbone takes.
Llama spends about twice Qwen's steps on the same tasks and Mistral about
four-fifths of Qwen's; that is a finding for the analysis, not a run problem.

## Llama access — resolved

`meta-llama/Llama-3.1-8B-Instruct` is `gated=manual` on the Hub. A Hugging Face
token with access granted was supplied by the operator and is read from `.env`
(gitignored, mode 600, never committed). All three backbones are therefore the
canonical repos; **no ungated mirror was substituted**, so provenance needs no
weight-substitution caveat.

| Backbone | Repo | Gated |
|---|---|---|
| Qwen3.5-9B | `Qwen/Qwen3.5-9B` | no |
| Llama-3.1-8B-Instruct | `meta-llama/Llama-3.1-8B-Instruct` | manual — access granted |
| Mistral-Nemo-12B-Instruct | `mistralai/Mistral-Nemo-Instruct-2407` | no |

## Disk budget

The three backbones at bf16 total roughly 60 GiB against a 65 GiB container
filesystem that also holds the venv (~15 GiB with vLLM). They therefore cannot
all be resident. Weights are fetched and evicted around the run order: a
backbone's snapshot is deleted once its three cells are complete and merged into
`runs/exp_a/raw/`, before the next backbone is pulled. Trial records are tiny and
are never evicted.
