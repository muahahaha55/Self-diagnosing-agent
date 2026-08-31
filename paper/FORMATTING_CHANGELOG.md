# Formatting Changelog — Block 0 (Typography & Visual Polish)

Scope: `BeliefEffect_Mismatch.tex`, its figures, and the build tooling.
**No wording, numbers, or claims in the paper body were changed.** Every item below
is formatting, spacing, or visual consistency; figure *captions* were updated only
where the figure they describe was redrawn (see Figures).

Build: `bash paper/build.sh` (three `pdflatex` passes; manual `thebibliography`, no BibTeX).

## Result

| | Before | After |
|---|---|---|
| Pages | 15 | **14** |
| Overfull `\hbox` | 4 (draft figure boxes) / 0 (with figs) | **0** |
| Underfull `\hbox` | 0 | **0** |
| Undefined refs/citations | 0 | **0** |
| `??` in compiled PDF | none | none |
| PDF metadata | empty | populated (title/author/subject/keywords) |
| Text + math fonts | Computer Modern, `microtype` expansion disabled | Times-like (newtx), expansion + protrusion enabled |
| Embedded fonts | — | all Type-1, subsetted (camera-ready compliant) |

## Repository state note

`paper/figs/` **did not exist** in the repo when Block 0 started. The author then
supplied four original PNGs (`fig1_flow`, `fig2_matched`, `fig4_confusion`,
`fig5_verif` — there is deliberately no `fig3`; figure *numbers* are unrelated to
file names), kept under `figs/.orig/`. No vector/script source existed for any
figure; see **Figures** for what was done about it.

## Preamble / fonts

- **Fonts.** Removed `type1cm`; added `newtxtext` + `newtxmath[varvw]` (Times text,
  matching Times math) after `amsmath`. This is the LNCS camera-ready convention.
  `microtype` changed from `[expansion=false]` to `[protrusion=true,expansion=true]`
  (the environment does have scalable Type-1 fonts, contrary to the old comment).
  Verified: no mixed CM/LM glyphs; all math and text in Times; `pdffonts` shows only
  TeXGyreTermes(/X), TeXGyreHeros (sans), and newtx symbol fonts, all embedded.
- **`\linespread{0.97}` removed.** Line spacing back to the class default (LNCS
  camera-ready should not compress leading). Net page count still dropped to 14
  because Times sets more compactly than Computer Modern.
- **Widow/orphan control.** Added `\clubpenalty=\widowpenalty=\displaywidowpenalty=9000`.
- **PDF metadata.** `\hypersetup` now sets `pdftitle`, `pdfauthor`, `pdfsubject`,
  `pdfkeywords` (keywords match the abstract). `hidelinks` kept; internal
  Table/Figure/Section links remain clickable.

## Captions

- `\captionsetup`: `skip` 2pt → 6pt (captions were crowding the float);
  added `labelsep=period` so labels read **"Table 2."** / **"Fig. 1."** (LNCS style)
  instead of the `caption`-package default colon.
- `font=small,labelfont=bf` verified to actually render: captions are now visibly
  smaller than body text and the bold label is consistent on every float.
- All captions already used sentence case, a leading noun-phrase label, and a
  terminal period — left as-is.
- The `caption` package still prints one harmless warning ("Unknown document class")
  with `llncs`; its settings nonetheless apply (confirmed in the PDF).

## Cross-references

- **Section references unified.** Hard-coded `\S6.1`, `\S6.3--6.4`, `Section~5`,
  `Section~6.4`, `Section~7` etc. → `\label`/`\ref`. Added `\label{sec:...}` to every
  section and to the five Results subsections. All now render as
  "Section 5" / "Sections 6.3–6.5" consistently (the `§` glyph is gone).
- **Figure references unified.** `Figure~\ref{fig:flow}` → `Fig.~\ref{...}` to match
  `\figurename` ("Fig.") and every other reference in the paper.
- "Table N" references were already consistent — untouched.

## Tables

- **Decimal alignment.** `siunitx` `S` columns for the numeric columns of Table 2
  (Precision/Recall/F1, n) and Table 5 (Scored n, Accuracy, Drift F1). `\sisetup`
  fixes two decimals, text-mode figures (Times), bold detection for the highlighted
  row.
- **Row height.** `\arraystretch` 1.0 → 1.04 (uniform, less cramped, no page cost).
- **Column spacing.** Table 1 header ("Operator" / "Divergence…") was touching —
  added a 2.2 em gutter. Tables 2/5 given explicit inter-column gutters. Table 3
  prediction columns switched to three equal-width centred columns so the headers
  ("clean / world_drift / halluc") and the shaded cells line up as uniform blocks.
- **Cell shading semantics made consistent across all tables** and documented in the
  preamble: `okgreen` = a correct outcome *or* the "our method" row; `missred` = a
  miss (fault read as clean). `missred` recoloured `#FDECEA` → `#FFEBEE` to match the
  figure palette's red-background tint.
- **Class labels** (`clean`, `world_drift`, `halluc`) now wrapped in `\textsf{}`
  inside Tables 2 and 3, matching their treatment everywhere in the body text.
  Method names in Table 4 italicised (`\emph`) to match the body.
- No vertical rules anywhere (already `booktabs`-only) — confirmed.

## Figures

**Why this went further than a formatting tweak.** `figs/` had no vector or script
source for any figure. The author supplied four raster PNGs, but fig1 (a 7-level
vertical flowchart) and fig2 (two stacked panels) could not be made legible at the
LNCS column width: in-figure sub-labels rendered below ~7 pt however they were
cropped or scaled. fig1 and fig2 were therefore **redrawn from scratch as a source
that now lives in the repo**; fig4 and fig5 kept the author's artwork with only a
crop.

- **`fig1_flow.png` — redrawn (`figs/src/fig1_gen.py`).** Same content and meaning
  as the original (matched pair -> agent, Qwen3.5-9B, T=0 -> MCP tool, may drift ->
  true world -> out-of-band oracle -> Axis A / Axis B -> 2x2 decision clean /
  world_drift / halluc / both). New layout is **horizontal**: a left-to-right
  5-stage pipeline, then the two axes, then the four outcome chips, so the figure
  uses page width instead of height. Each box carries its own detail line, so the
  figure reads without the caption. Palette unchanged (navy `#1F3A5F`, green
  `#2E7D32`/`#E8F5E9`, orange `#ED6C02`/`#FFF3E0`, blue `#1565C0`/`#E3F2FD`, red
  `#C62828`/`#FFEBEE`).
- **`fig2_matched.png` — redrawn (`figs/src/fig2_gen.py`).** Same content: a
  matched-pairs group (`A_clean` / `A_drift_D1` / `A_drift_D2`, dashed links) and
  the 7 base x 7 operator grid with base B outlined and columns D2, D4 shaded.
  New layout is **two panels side by side** (matched pairs left, grid right), each
  with its own title on a clear band so no box border crosses the title text.
  `A_drift_D2` is now **purple** (`#6A1B9A` border, `#F3E5F5` fill) — deliberately
  *not* the semantic red that fig1 reserves for "both -> defer"; `A_drift_D2` is
  just a second `world_drift` example. Caption changed `(top)/(bottom)` ->
  `(left)/(right)` and notes the purple box.
- **`fig4_confusion.png`, `fig5_verif.png` — cropped only
  (`figs/src/crop_fig4_fig5.py`).** Author's raster kept; cropped to the content
  box + 40 px pad, and fig4's ~285 px interior white band between its two panels
  collapsed. Nothing inside the artwork is redrawn.
- **Shared style** (`figs/src/figstyle.py`): DejaVu Sans, rounded boxes, ~2.4 pt
  strokes — matched to fig4/fig5 so all four figures read as one set.
- `\includegraphics` widths: **fig1 and fig2 at `width=\linewidth`** (fig4 0.60,
  fig5 0.70). fig1/fig2 are authored at `W_IN = \linewidth` in inches
  (347.12 pt / 72.27 = 4.803 in), so placed at `\linewidth` the scale is 1.0007 and
  a matplotlib point equals an on-page point.

**Final in-figure text size at print scale** (method: authored width == `\linewidth`,
placed at `width=\linewidth`, scale 1.0007):

| figure | smallest on-page text | other elements |
|---|---|---|
| fig1 | **8.0 pt** (box detail lines, axis questions, chip actions, condition tags) | pipeline titles 8.2 pt, axis titles 8.8 pt, class names 9.2 pt |
| fig2 | **8.0 pt** (box tags, legend) | matrix cells 8.4 pt, panel titles / box names 9.0 pt |

Nothing in either figure is below 8.0 pt on the page. (Old raster fig1 sub-labels
were ~5-6 pt at the width the page budget allowed.) Empirical check: page rendered
at 600 dpi, the ~8 pt detail text measures ~6.2 pt of ink height (x-height plus
ascender), consistent with an 8 pt font.

## Whitespace & flow

- **Limitations section** was a single run-on paragraph with four inline italic
  lead-ins. Split into four paragraphs, each `\smallskip\noindent\emph{lead-in.}`,
  matching the run-in style used in Section 6.1.
- Float placement checked page by page against the rebuilt PDF: every float lands on
  `[t]` of a page at or adjacent to its first reference; none drifted. No
  `\FloatBarrier` needed.
- Orphan/widow scan of all 14 pages: none found.
- Bibliography `\itemsep` 2 pt → 0 pt (`plus 0.3 pt`) to keep the reference list
  on one page after the figure resizing.

## Consistency pass

- `world_drift` / `two-axis` hyphenation: grepped — already consistent, no fixes.
- Section-reference style: fixed (see Cross-references).
- `\textsf{}` for the three class labels: fixed in tables (see Tables).

## Visual diff (rebuilt PDF vs. previous `BeliefEffect_Mismatch.pdf`)

Rasterised both at ~100 dpi and compared page by page. Differences are all
intended: Times in place of Computer Modern throughout; "Table N."/"Fig. N."
labels; decimal-aligned and less cramped tables; Table 3 headers no longer
colliding; fig1 and fig2 redrawn (horizontal / two-panel, `A_drift_D2` purple);
fig4/fig5 cropped; Limitations now four paragraphs; section cross-references show
resolved numbers; page count unchanged at 14. The only body-text change is the
"§6.x" → "Section 6.x" reference substitutions; figure captions changed to match
the redrawn figures (fig1 shortened, fig2 `(top)/(bottom)` → `(left)/(right)`).

## New / changed files

- `paper/BeliefEffect_Mismatch.tex` — edited (formatting; figure captions updated to match redrawn figures)
- `paper/BeliefEffect_Mismatch.pdf` — rebuilt (14 pp)
- `paper/figs/fig1_flow.png`, `paper/figs/fig2_matched.png` — redrawn from `figs/src/`
- `paper/figs/fig4_confusion.png`, `paper/figs/fig5_verif.png` — cropped from `figs/.orig/`
- `paper/figs/src/figstyle.py`, `fig1_gen.py`, `fig2_gen.py`, `crop_fig4_fig5.py` — figure source
- `paper/figs/.orig/` — the four author-supplied original PNGs, checked in for provenance
- `paper/build.sh` — new build helper
- `.gitignore` — ignore `paper/build/`, LaTeX aux files, and `figs/src/__pycache__/`
