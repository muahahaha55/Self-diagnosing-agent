"""Generate fig1_flow.png -- execution flow of a single trial (wide layout).

Semantics (unchanged from the original vertical figure):
  matched pair fixes the inputs
    -> agent (Qwen3.5-9B, T=0) issues MCP tool calls
    -> MCP tool executes (description unchanged, behaviour may drift)
    -> true world state
    -> oracle inspector (out-of-band, dashed border)
  the oracle then drives a two-axis attribution:
    Axis A -- did each tool honour its description?   (tool-side)
    Axis B -- does the belief survive the true world? (belief-side)
  combined into a 2x2 decision:
    clean / world_drift / halluc / both (defer to a human)

DESIGN NOTE.  Authored at W_IN == the paper's \\linewidth in inches
(347.12 pt / 72.27 = 4.803 in) and placed with  width=\\linewidth , so a
matplotlib point equals an on-page point (scale ~= 1.0).  Width is fixed at
\\linewidth; when more room is needed for text at >= 8 pt we grow YMAX (the
figure gets taller), never shrink the font.  Every box carries its own detail
line so the figure reads on its own without the caption.

Run:  python fig1_gen.py [output.png]
"""
import sys
from figstyle import (newfig, box, arrow, GREEN, ORANGE, BLUE, RED, GREY, DARK,
                      BODY)

OUT = sys.argv[1] if len(sys.argv) > 1 else "../fig1_flow.png"

W_IN = 4.80                       # == \linewidth in inches
XMAX, YMAX = 100.0, 57.5          # tall enough for 8 pt text in every box
T_PIPE, S_PIPE = 8.2, 8.0
T_AX, S_AX = 8.8, 8.0
T_CHIP, S_CHIP = 9.2, 8.0

fig, ax = newfig(W_IN, W_IN * YMAX / XMAX, (0, XMAX), (0, YMAX), dpi=600)


def centers(n, lo, hi, w):
    gap = (hi - lo - n * w) / (n - 1)
    return [lo + w / 2 + i * (w + gap) for i in range(n)]


# ---- top: 5-stage pipeline (title + detail line inside each box) -----------
yp, bh = 48.5, 15.0
pipe = [
    (GREY,   "Matched pair", "instruction\n+ seed fixed", 20.4),
    (BLUE,   "Agent",        "Qwen3.5-9B\nT = 0",         18.0),
    (ORANGE, "MCP tool",     "behaviour\nmay drift",      18.0),
    (DARK,   "True world",   "the true\nfilesystem",      18.0),
    (GREY,   "Oracle",       "out-of-band\ndiff + canary", 18.0),
]
_gap = (99.6 - sum(w for *_, w in pipe)) / (len(pipe) - 1)
_left, cx = 0.2, []
for col, t, d, w in pipe:
    xc = _left + w / 2
    cx.append(xc)
    box(ax, xc, yp, w, bh, col, t, d, title_size=T_PIPE, sub_size=S_PIPE,
        dashed=(t == "Oracle"))
    _left += w + _gap
for i in range(len(pipe) - 1):
    r = cx[i] + pipe[i][3] / 2
    l = cx[i + 1] - pipe[i + 1][3] / 2
    arrow(ax, (r + 0.3, yp), (l - 0.3, yp), ms=11, lw=1.6)

# ---- middle: the two axes -----------------------------------------------
ya, aw, ah = 30.5, 34.0, 12.6
axcx = [25.0, 62.0]
box(ax, axcx[0], ya, aw, ah, ORANGE, "Axis A · tool-side",
    "did each tool honour\nits own description?", title_size=T_AX, sub_size=S_AX)
box(ax, axcx[1], ya, aw, ah, BLUE, "Axis B · belief-side",
    "does the account survive\nthe true world?", title_size=T_AX, sub_size=S_AX)

rail = 39.5
ax.plot([cx[4], cx[4], axcx[0]], [yp - bh / 2, rail, rail],
        color="#55606A", lw=1.7, zorder=1,
        solid_capstyle="round", solid_joinstyle="round")
for x in axcx:
    arrow(ax, (x, rail), (x, ya + ah / 2), ms=12, lw=1.7)

# ---- bottom: 2x2 decision as four chips (tag + name + action) -------------
cy, cw, ch = 9.5, 23.8, 13.4
ccx = centers(4, 0.2, 99.8, cw)
chips = [
    ("clean",       GREEN,  "A ✓  B ✓", "proceed"),
    ("world_drift", ORANGE, "A ✗  B ✓", "re-read, replan"),
    ("halluc",      BLUE,   "A ✓  B ✗", "re-check belief"),
    ("both",        RED,    "A ✗  B ✗", "defer to a human"),
]
for x, (name, col, tag, act) in zip(ccx, chips):
    box(ax, x, cy, cw, ch, col, "", title_size=1)
    ax.text(x, cy + ch * 0.29, tag, ha="center", va="center",
            fontsize=S_CHIP, color=BODY)
    ax.text(x, cy + ch * 0.02, name, ha="center", va="center",
            fontsize=T_CHIP, fontweight="bold", color=col[2])
    ax.text(x, cy - ch * 0.28, act, ha="center", va="center",
            fontsize=S_CHIP, color=BODY)

mid = sum(axcx) / 2
for x in ccx:
    rad = 0.17 if x < mid else -0.17
    arrow(ax, (mid, ya - ah / 2 - 0.3), (x, cy + ch / 2 + 0.3),
          rad=rad, lw=1.5, ms=11)

fig.savefig(OUT, dpi=600)
print("wrote", OUT, "logical size", tuple(round(v, 3) for v in fig.get_size_inches()))
