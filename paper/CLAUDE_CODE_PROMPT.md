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

- **Setup:** 300 trials = 3 backbones × 2 temperatures × 3 seeds × the existing task set.
  - Backbones: Qwen3.5-9B, Llama-3.1-8B-Instruct, Mistral-Nemo-12B-Instruct.
  - Temperatures: 0.0 and 0.7.
  - Same 7 bases × 7 operators + halluc conditions as the original testbed.
- **Post-hoc verification:** after every trial, snapshot the true final world with the oracle inspector, then run the verification protocol from Fig. 5 to relabel every halluc-designed trial as one of `{clean, halluc, ambiguous}`. Log both `designed_label` and `verified_label` with a `verify_reason` string.
- **Output:** `runs/exp_a/summary.csv` with columns `backbone, temp, seed, base, op, designed_label, verified_label, probe_pred, verify_reason, canary_present, canary_count, world_diff_class`.
- **Paper update:** rewrite Table 7 using verified labels at the new n. If any backbone hallucinates > 30% of halluc-designed trials, break it out as a separate row so the reader can see backbone variance. Rewrite the last paragraph of §6.5 (which currently says "the verified halluc class contains exactly one trial") with the new n.
- **Do not** touch Tables 2, 3, or Fig. 4 — these belong to the 30-trial evidence base and must stay reproducible from `runs/exp_baseline/`.

### Block 3 — Experiment B: LLM-judge baseline and multi-backbone comparison

Currently §6.2 reports the two attribution-free baselines as "forced by construction" — analytical, not run. Replace this with real runs, plus one model-based baseline.

- **New baselines to actually run** on all 300 trials from Block 2:
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
- Deadline discipline: Blocks 1 and 5 are mandatory. Block 2 is high priority. Blocks 3 and 4 are best-effort if time allows.

**Start with Block 0.** When Block 0 is complete, stop and show me `FORMATTING_CHANGELOG.md` plus the new page count, and wait for my approval before starting Block 1.