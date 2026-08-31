# Claude Code Prompt — Belief–Effect Mismatch (SOICT 2026)

## Cách chạy (Windows, thư mục đã có sẵn: `D:\Self-diagnosing-agent\paper`)

Mở **PowerShell** (không cần quyền admin), rồi:

```powershell
cd "D:\Self-diagnosing-agent\paper"
claude
```

Lệnh `claude` mở phiên làm việc tương tác trong đúng thư mục chứa `paper.tex`, `llncs.cls`, `splncs04.bst`, `CLAUDE_CODE_PROMPT.md`. Sau khi Claude Code khởi động, dán lệnh sau để nó tự đọc và thực thi toàn bộ prompt bên dưới:

```
Đọc kỹ file CLAUDE_CODE_PROMPT.md trong thư mục hiện tại và thực hiện đúng theo đó, bắt đầu từ Block 0.
```

**Nếu chưa cài Claude Code CLI**, cài trước bằng npm (cần Node.js ≥ 18):

```powershell
npm install -g @anthropic-ai/claude-code
```

Sau đó xác thực (mở trình duyệt đăng nhập) trong lần chạy `claude` đầu tiên.

**Chạy không tương tác (một lệnh, tự làm hết Block 0 rồi dừng):**

```powershell
cd "D:\Self-diagnosing-agent\paper"
claude -p "Đọc kỹ file CLAUDE_CODE_PROMPT.md trong thư mục hiện tại và thực hiện đúng theo đó, bắt đầu từ Block 0. Dừng lại sau khi Block 0 xong và chờ tôi duyệt."
```

Sau khi Block 0 (thẩm mỹ) xong, Claude Code sẽ tạo `FORMATTING_CHANGELOG.md` và báo số trang mới. Anh mở lại `paper.pdf` kiểm tra, rồi gõ tiếp trong cùng phiên:

```
Duyệt Block 0, tiếp tục Block 1.
```

Cứ lặp lại "duyệt, tiếp tục Block N" cho tới Block 5.

---

Copy the entire block below into Claude Code inside the repo that contains `paper.tex` + the 30-trial experiment code.

---

## Prompt

You are an NLP engineer assisting the paper *"Belief–Effect Mismatch: Attributing Tool-Side and Belief-Side Failures in Tool-Using LLM Agents"* (target: SOICT 2026, EasyChair, single-blind, deadline 16/09/2026).

**Absolute rule: no fabricated numbers.** Every new statistic in the paper must trace back to a real run logged under `runs/`. If a metric cannot be produced, mark it as future work, not an estimate.

The repo already contains: `paper.tex` (LaTeX llncs, ~15 pages), `figs/`, and the code from the original 30-trial run on Qwen3.5-9B against an MCP filesystem server. Tables 2, 3, and Fig. 4 are frozen — they are the evidence for the "no cross-confusion" claim.

Work is split into five blocks. For each block: (1) plan out loud, wait for my confirmation; (2) write code; (3) run experiments, logging to `runs/<block>/<timestamp>/`; (4) update `paper.tex` + tables/figures from that log; (5) commit as two separate commits, one `exp: <block>` and one `paper: <block>`.

### Block 0 — Typography & visual polish (run first, no experiments needed)

The current `paper.tex` compiles correctly but was assembled quickly; treat this block as a full aesthetic pass. Do not change any wording, numbers, or claims in this block — only formatting, spacing, and visual consistency. Work through each item, then run `pdflatex` twice and visually diff a few pages against the previous PDF before committing.

- **Fonts.** The class currently falls back to Computer Modern with `microtype`'s font expansion disabled (the environment lacks scalable Type-1 fonts). Try to install/enable `lmodern` or `newtxtext`+`newtxmath` (Times-like, standard for LNCS camera-ready) so `expansion=true` can be re-enabled in the `microtype` package options; if neither is available, keep CM but confirm `protrusion=true` still works to tighten the right margin. Verify math and text fonts match (no mixed CM/Latin Modern glyphs).
- **Captions.** Standardize every figure/table caption to the same voice: bold "Fig. N." / "Table N." label (llncs default), sentence case, no trailing period inconsistency. Check `\captionsetup` sizing (`font=small,labelfont=bf`) actually renders — some table captions currently look the same size as body text after the recent edits; fix if so.
- **Tables.** Re-check every table for: consistent vertical rule usage (LNCS style avoids vertical rules — use `booktabs` `\toprule/\midrule/\bottomrule` only, no `|`), consistent decimal alignment in numeric columns (use `S` columns from `siunitx` or manually pad), consistent cell shading (`okgreen`/`missred`) applied to the same semantic meaning across all tables, and consistent row height / padding so tables don't look cramped next to prose.
- **Figures.** Confirm all remaining figures (`fig1_flow.png`, `fig2_matched.png`, `fig4_confusion.png`, `fig5_verif.png`) share one visual language: same font family inside the PNGs, same corner radius / stroke width on boxes, same arrow style, same color palette (navy `#1F3A5F` headers, green `#2E7D32`/`#E8F5E9` for "clean"/pass, orange `#ED6C02`/`#FFF3E0` for tool-side, blue `#1565C0`/`#E3F2FD` for belief-side, red `#C62828`/`#FFEBEE` for defer/error). Regenerate any figure that has drifted from this palette. Confirm all figure text is legible at final print width (rasterize the compiled PDF at 300dpi and visually inspect — flag any figure where caption/label text is under ~7pt at that resolution).
- **Whitespace & flow.** Check for orphan/widow lines, section headers stranded at the bottom of a column/page, figures floating far from their first reference, and any table that spans awkwardly close to a page break. Use `\FloatBarrier` (`placeins` package) at natural section boundaries if floats are drifting too far from their referencing text.
- **Cross-references.** Confirm every `\ref{}`/`\label{}` resolves (no `??` in the compiled PDF — grep the `.log` for "undefined"), and that Table/Figure numbers are referenced in the same style throughout ("Table 2" not "Tab. 2" in some places and "Table 2" in others).
- **Hyperref & metadata.** Set proper PDF metadata (`\hypersetup{pdftitle=..., pdfauthor=..., pdfsubject=..., pdfkeywords=...}` matching the abstract's keywords) so the PDF's document properties are populated instead of blank. Keep `hidelinks` (no colored boxes around citations/links, per LNCS convention) but confirm internal links (Table/Figure refs) are still clickable.
- **Consistency pass.** Grep for inconsistent hyphenation of repeated terms (`world_drift` vs `world-drift` vs `worlddrift`; `two-axis` vs `two axis`), inconsistent capitalization of section-reference style (`§6.1` vs `Section 6.1` vs `Sec. 6.1` — pick one and apply throughout), and inconsistent use of `\textsf{}` for the three class labels (`clean`, `world_drift`, `halluc`) — every occurrence in body text should use the same monospace/sans treatment as the tables.
- **Deliverable:** a short `FORMATTING_CHANGELOG.md` listing every visual change made, so I can spot-check without re-diffing the whole `.tex`.

### Block 1 — Reproducibility scaffold (no experiments yet)

- Add `README.md` at repo root: for every table/figure in the paper, list the exact command that regenerates it from `runs/`.
- Add `scripts/verify_all_numbers.py`: parses `paper.tex`, extracts every `0.XX` and `N / M` token, checks each against `runs/*/summary.csv`, and reports mismatches with file/line pointers.
- Add `scripts/regen_all.py` that rebuilds every figure and table PNG/tex fragment from the raw run logs.
- Add `requirements.txt` pinning all dependencies (vllm, transformers, mcp, pandas, matplotlib, cairosvg, etc.).
- Freeze the existing 30-trial run as `runs/exp_baseline/2025_original/` and check it in.
- Verify `verify_all_numbers.py` passes on the current paper before touching anything else.

### Block 2 — Experiment A: verified ground truth at scale

Problem the current paper concedes: belief-side attribution rests on n=1 genuine hallucination. Fix that by scaling up.

- **Setup:** 270 trials. Seed only creates real variance at T=0.7 (T=0 is greedy decode — re-seeding gives an essentially identical trajectory bar floating-point noise), so seeds are not replicated at T=0:
  - T=0.0: 3 backbones × 30 tasks × 1 seed = 90 trials.
  - T=0.7: 3 backbones × 30 tasks × 2 seeds = 180 trials.
  - Total = 270 trials.
  - Backbones: Qwen3.5-9B, Llama-3.1-8B-Instruct, Mistral-Nemo-12B-Instruct.
  - Task set: the existing 30 tasks (7 bases A–G; 8 clean / 14 world_drift / 8 halluc), unchanged from the original testbed — same `code/tasks.py` that produced the frozen baseline.
- **Post-hoc verification:** after every trial, snapshot the true final world with the oracle inspector, then run the verification protocol from Fig. 5 to relabel every halluc-designed trial as one of `{clean, halluc, ambiguous}`. Log both `designed_label` and `verified_label` with a `verify_reason` string.
- **Output:** `runs/exp_a/summary.csv` with columns `backbone, temp, seed, base, op, designed_label, verified_label, probe_pred, verify_reason, canary_present, canary_count, world_diff_class`.
- **Paper update:** rewrite Table 7 using verified labels at the new n. If any backbone hallucinates > 30% of halluc-designed trials, break it out as a separate row so the reader can see backbone variance. Rewrite the last paragraph of §6.5 (which currently says "the verified halluc class contains exactly one trial") with the new n.
- **Do not** touch Tables 2, 3, or Fig. 4 — these belong to the 30-trial evidence base and must stay reproducible from `runs/exp_baseline/`.

### Block 2.5 — Ablation study (build harness, then re-score Block 2's logs — no new agent runs)

The probe (§5) has never been decomposed, and no toggle mechanism exists to disable individual rules. A reviewer will ask which piece carries the work. This block answers that. It has **three phases**: build a configurable harness (real code), re-score the frozen Block 2 trajectories under each ablation arm (no agent calls), and analyse firing vs. load-bearing. Do not collapse them — re-scoring alone, without the harness and the marginal-contribution analysis, produces numbers that look like an ablation but do not isolate anything.

**Ground rules for the whole block.** Ground truth = the post-hoc **verified** labels from Block 2 (same gold as Table 7), fixed across every arm; only the probe prediction changes. The probe is deterministic, so each arm's numbers are exact given the 270 trajectories — report them as exact, no confidence intervals from the probe. All variance comes from the agent trajectories (backbone × temp × seed; seed replicated only at T=0.7), so every arm is reported both pooled and broken down by backbone and temperature.

**Rule inventory — reconstruct this table from the actual code first (`code/probe_input.py`, `code/layer_4_oracle.py`), and confirm each rule exists before ablating it. Do not ablate a rule the code does not actually have; if the code and this table disagree, stop and report.**

**Reconciled against the code 2026-08-31 — this table is now the confirmed 9-rule inventory** (the code has *nine* rules, not eight; the original table missed A6 and under-described A1).

| ID | Axis | Fires when | Targets | Canary-dependent? |
|----|------|-----------|---------|-------------------|
| A1 | A (tool) | a modified file's `change_kind` is **anything outside** `ALLOWED_CHANGE[tool]` — for `write_file` that is everything but `replaced`/`filled_from_empty`; for `append_file` everything but `appended`/`filled_from_empty`. Baseline fires on both `appended` and `truncated`. **Local exception, not a general condition:** for the single pair `write_file`+`appended`, the rule is suppressed if the agent's own submitted text already started with the prior content (agent composed old+new itself) | D1 | no (diff-based) |
| A2 | A (tool) | created path ≠ the path the agent requested (`args.path` vs `world_created[].path`, exact match) | D4 | **no** — purely path-diff, confirmed independent of canary; must stay ON under `use_canary=False` |
| A3 | A (tool) | a delete leaves a `leftover` copy in a trash path (`world_created` non-empty on a `delete_file` step) | D5 | no |
| A4 | A (tool) | canary appears in the world > 1 time (write multiplied) | D7 | **yes** |
| A5 | A (tool) | agent never terminated (`__LIVELOCK__` claim) **and** some step both errored and left the world unchanged (lock) | D2 | no |
| A6 | A (tool) | a step reports success (**no** error in the tool return) yet the world is unchanged, on `write_file`/`append_file`/`delete_file` — failing if the tool is `delete_file`, or if the agent submitted no content. Distinct from A5: A5 needs a livelock **and** an error present; A6 needs neither and fires on a normally-terminating run | D2 (silent no-op) | no |
| B1 | B (belief) | agent claims success but the canary never reached the world | missing write | **yes** |
| B2 | B (belief) | move task: canary survives in > 1 location (copied, not moved) | copy-not-move | **yes** |
| B3 | B (belief) | success claim over a world showing **no change at all**, *and* the task carried no canary (no-canary fallback, bases B/E) | miscount / no-op | no |

Note two operators — **D3** (return format) and **D6** (stale read) — have **no detector by design** (they leave no world-state trace; §6.3 "invisible drift"). The ablation table must say so explicitly, so a reader does not read the absence of a D3/D6 rule as an oversight.

**Activation on the frozen 30-trial baseline** (measured 2026-08-31): A1 = 3, A2 = 2, A3 = 1, B2 = 1; **A4, A5, A6, B1, B3 = 0**. The five zero-activation rules are why the byte-identical regression gate alone is not sufficient — see Phase A.

**Phase A — build the ablation harness (real code work).**
- Thread a `ProbeConfig` (dataclass or dict) through both probe files with a boolean per rule above — **nine flags**: `a1_content_diff`, `a2_relocation`, `a3_soft_delete`, `a4_dup_canary`, `a5_lock`, `a6_silent_noop`, `b1_canary_absent`, `b2_multi_location`, `b3_no_change` — plus three group switches derived from them: `axis_a_enabled`, `axis_b_enabled`, `use_canary` (when false, force every canary-dependent rule off — A4, B1, B2 only; A2 is *not* canary-dependent and stays on).
- **Disabled ≠ pass.** A disabled rule must return a `NO_SIGNAL` sentinel, and axis aggregation must treat `NO_SIGNAL` as "this check was never written" — the axis fails iff at least one *enabled* rule fires; it passes iff every enabled rule returns pass-or-`NO_SIGNAL`. Getting this wrong (treating disabled as pass, or as fail) silently corrupts every ablation number; add a unit test that a fully-disabled axis yields "pass for all trials" and a single-enabled-rule axis yields exactly that rule's firings.
- **Regression gate before any ablation run:** run the harness with all flags on over the frozen `runs/exp_baseline/` 30-trial set and assert **byte-identical** `probe_pred` to the frozen `summary.csv`. If it differs, the harness has changed probe behaviour — stop, report the diff, do not proceed. This proves the harness's "full" mode is the real probe.
- **Synthetic coverage for the zero-activation rules (mandatory).** A4, A5, A6, B1 and B3 never fire on the 30-trial baseline, so the regression gate passes *vacuously* for them — it proves nothing about whether the harness preserved their behaviour. For each of these five, hand-build a minimal synthetic payload that triggers exactly that rule, and assert: (i) with the rule enabled the axis fails with that rule's reason; (ii) with the rule disabled it returns `NO_SIGNAL` and the axis passes. Without this, five of nine ablation arms rest on untested code.
- This edits `code/probe_input.py` / `code/layer_4_oracle.py`; do it only after the untracked-`code/` question is resolved (see note below) so the harness is not built on files that get reverted.

**Phase B — the ablation arms** (re-score the frozen `runs/exp_a/` trajectories from Block 2; no agent calls, no GPU/API):
- *Tier 1 — is each axis necessary?* `full`, `axis_A_only` (`axis_b_enabled=False`), `axis_B_only` (`axis_a_enabled=False`). Report how many belief trials `axis_A_only` silently mis-files as clean, and vice-versa — this is the direct evidence that a single axis is insufficient.
- *Tier 2 — is the canary mechanism necessary?* `no_canary` (`use_canary=False`; only A1/A2/A3/A5/A6 and B3 survive). Expected to collapse belief detection to the no-change fallback — that collapse is the point, it shows the canary of §4.4 is load-bearing, not decorative.
- *Tier 3 — which individual rules carry the load?* **nine** single-rule knockouts (`full` minus exactly one rule), one per ID above.
- **`full` arm is a consistency check:** its pooled numbers must reproduce Block 2's headline (Table 7 verified rows) exactly. If not, Phase A is wrong — stop.

**Phase C — firing vs. load-bearing (this is what makes it an ablation and not just nine reruns).** For each rule, compute and log three distinct quantities, because they answer different questions:
1. **Activation count** — trials where the rule's condition is true (it *fired*), pooled and per backbone/temp.
2. **Marginal contribution** — trials where the single-rule-knockout flips the attribution from *correct* to *wrong* (i.e. this rule was the *only* signal producing the right answer). A rule can fire often yet have zero marginal contribution if another rule always co-fires on the same trials; only marginal contribution shows a rule is load-bearing.
3. **Coverage confound flag** — if activation count is 0, check whether the rule's target operator even appears in the task set (e.g. A4 depends on D7 tasks existing). Label each zero-activation rule as either `dead-no-coverage` (testbed never exercises it) or `dead-redundant` (fault occurs but another rule always caught it first). **Never call a rule "useless" from zero activations alone** — the two causes have opposite implications (add coverage vs. simplify the probe).
- Because single-rule knockouts miss pairwise redundancy (two rules each individually removable because the other covers, but jointly load-bearing), add a **pairwise knockout** for any pair of rules that target overlapping signatures or that both show high activation but low individual marginal contribution — to catch a redundancy the single knockouts would hide.
- **Mandatory pairwise arm: `A5+A6`.** Both target D2 and both key off "the world did not change", so they are exactly the overlapping-signature case above; a single knockout of either could look free while the pair is load-bearing. Run this arm regardless of what the single-knockout numbers show, and report it in the ablation table.

**Outputs:**
- `runs/exp_ablation/summary.csv` — columns `arm, backbone, temp, seed, base, op, verified_label, probe_pred, axis_a_result, axis_b_result`.
- `runs/exp_ablation/arm_metrics.csv` — per arm: `Tool_F1, Belief_F1, Macro_F1, Accuracy`, each with its **support n**, pooled and per backbone/temp, plus delta vs. `full`.
- `runs/exp_ablation/rule_analysis.csv` — per rule: `activation_count, marginal_contribution, coverage_flag (live | dead-no-coverage | dead-redundant)`.
- Extend `scripts/verify_all_numbers.py` to cover every ablation number that lands in the paper.

**Paper integration** (new §6 subsection "Ablation", after §6.5):
- One table: rows = arms (Tier 1 + Tier 2 + the notable Tier-3 knockouts), columns = `Tool F1, Belief F1, Macro-F1 (Δ vs. full)`, with support n in the caption. Report Belief-side numbers with explicit n — if verified belief positives are still few even at 270 trials, say so and treat Belief deltas as directional, not rates (same honesty stance as §6.5's n=1 caveat).
- One short paragraph naming the load-bearing rules (largest marginal contribution) and the dead rules, each dead rule labelled `no-coverage` or `redundant`. If a rule is `dead-redundant`, state plainly it could be removed to simplify the probe; if `dead-no-coverage`, state the testbed doesn't exercise it and leave it in.
- Do not overclaim: the ablation characterises *this* probe on *this* testbed; a rule dead here may be essential on a domain with different operators.


### Block 3 — Experiment B: LLM-judge baseline and multi-backbone comparison

Currently §6.2 reports the two attribution-free baselines as "forced by construction" — analytical, not run. Replace this with real runs, plus one model-based baseline.

- **New baselines to actually run** on all 270 trials from Block 2:
  1. `outcome-only`: given only the final task success/failure signal, predict `{clean, world_drift, halluc}`.
  2. `tool-report-only`: given only the concatenated tool return strings, predict.
  3. `llm-judge`: give a judge model (GPT-4o-mini or Claude Haiku 4.5) the full trajectory + final world diff and ask it to classify. Run three times with three prompt variants, majority vote.
  4. `two-axis probe (ours)`: unchanged.
- **New Table 4** (replaces the current analytical one): rows = methods, columns = `Tool F1, Belief F1, Macro-F1, Accuracy` on the visible + verified subset from Block 2. If the two-axis probe does not beat the LLM-judge on Tool F1, write it honestly — do not hide the result.
- **Update §6.2 prose** to describe real runs rather than analytical arguments. Keep the observation that outcome-only and tool-report-only cannot recover drift by construction as an intuition, but back it with the empirical numbers.

### Block 4 — Experiment C: recovery experiment (conditional)

Only run this if the paper is still ≤ 14 pages after Blocks 2–3; otherwise ship as supplementary.

- Add three recovery modes triggered after attribution:
  1. `no-diagnosis`: retry the failing step verbatim.
  2. `generic-reflection`: prompt the agent with "something went wrong, try again."
  3. `source-aware`: if `drift` → re-read the world state and replan; if `halluc` → re-verify the belief against a fresh world snapshot; if `both` → halt and log a defer-to-human event.
- **Run:** 100 tasks × 3 modes = 300 trials. Log `task_success, recovery_success, retry_count, tokens_total, latency_sec`.
- **New §9 Recovery Experiment** in `paper.tex` with a single results table.
- **Statistical rule:** run a paired t-test (α = 0.05) between `source-aware` and `generic-reflection` on `task_success`. If `source-aware` does **not** win, rewrite the Conclusion — remove any phrasing that implies attribution turns diagnosis into action, and add a paragraph reporting the null result.

### Block 5 — Submission package

- Build `soict2026_submission.zip` containing `paper.tex`, `figs/`, `llncs.cls`, `splncs04.bst`, `runs/`, `scripts/`, `requirements.txt`, `README.md`.
- Confirm the zip compiles cleanly on a fresh TeX Live install: `pdflatex paper.tex; pdflatex paper.tex`, exit code 0, page count ≤ 15.
- Run `verify_all_numbers.py` one final time.

### Hard constraints

- No KTO, RLHF, or any alignment method — this paper does not touch alignment; that scope belongs to the EduQA project.
- No changes to Tables 2, 3, or Fig. 4 (30-trial evidence base for the "no cross-confusion" claim).
- Every change to `paper.tex` must be followed by two `pdflatex` passes and a commit of the updated `paper.pdf`.
- After every block, `scripts/verify_all_numbers.py` must pass before the block is committed.
- Deadline discipline: Blocks 0, 1, and 5 are mandatory. Block 2 is high priority. Block 2.5 should follow immediately after Block 2 (same trajectory logs, no extra cost) — do not skip it even under time pressure, since it is cheap relative to Block 2. Blocks 3 and 4 are best-effort if time allows.

**Start with Block 0.** When Block 0 is complete, stop and show me `FORMATTING_CHANGELOG.md` plus the new page count, and wait for my approval before starting Block 1.