"""Generate fig2_matched.png -- matched-pairs construction + base/operator matrix
(wide, two-panel layout: matched pairs on the LEFT, matrix on the RIGHT).

Semantics (unchanged from the original stacked figure):
  left  : one matched-pairs group for base A -- A_clean / A_drift_D1 / A_drift_D2,
          linked by dashed lines; identical instruction and seed, only the injected
          fault differs.
  right : the 7 bases (A-G) x 7 operators (D1-D7) grid; base B is outlined (three
          operators touch it) and columns D2, D4 are shaded (each recurs across
          several bases) -- operators do not map one-to-one onto bases.

Colour note: A_drift_D2 is drawn in PURPLE, deliberately NOT the semantic red
(#C62828) that fig1 reserves for "both -> defer to a human".  A_drift_D2 is just a
second world_drift example (operator D2), not a "both" case.

The paper caption for this figure must say "(left)" / "(right)", not
"(top)" / "(bottom)".

DESIGN NOTE.  Authored at W_IN == \\linewidth in inches (4.803) and placed with
width=\\linewidth, so matplotlib pt == on-page pt.  All text >= 8.0 pt.

Run:  python fig2_gen.py [output.png]
"""
import sys
from matplotlib.patches import Rectangle
from figstyle import newfig, box, GREEN, ORANGE, PURPLE, BLUE, NAVY, BODY

OUT = sys.argv[1] if len(sys.argv) > 1 else "../fig2_matched.png"

W_IN = 4.80
XMAX, YMAX = 100.0, 45.0
fig, ax = newfig(W_IN, W_IN * YMAX / XMAX, (0, XMAX), (0, YMAX), dpi=600)

TITLE = 9.0
NAME, TAG = 9.0, 8.0
CELL = 8.4
LEG = 8.0

# ============================ LEFT: matched-pairs group =====================
lx, lw = 19.0, 33.0
ax.text(lx, 42.4, "Matched pairs (base A)", ha="center", va="center",
        fontsize=TITLE, fontweight="bold", color=BODY)

pair = [
    (34.0, GREEN,  "A_clean",    "no fault"),
    (23.5, ORANGE, "A_drift_D1", "D1 injected"),
    (13.0, PURPLE, "A_drift_D2", "D2 injected"),
]
ph = 8.6
for y, col, name, tag in pair:
    box(ax, lx, y, lw, ph, col, name, tag, title_size=NAME, sub_size=TAG)
for y0, y1 in [(34.0, 23.5), (23.5, 13.0)]:
    ax.plot([lx, lx], [y0 - ph / 2 - 0.2, y1 + ph / 2 + 0.2],
            color="#9AA5AD", lw=1.6, linestyle=(0, (3, 2)), zorder=1)

# ============================ RIGHT: base x operator matrix =================
ops = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
bases = ["A", "B", "C", "D", "E", "F", "G"]
shaded_ops = {"D2", "D4"}
outlined_base = "B"

mx0, mx1 = 41.0, 99.6
labw = 7.6
datw = (mx1 - mx0 - labw) / len(ops)
my_top, rowh = 39.0, 3.75
nbody = len(bases)
my_bot = my_top - (nbody + 1) * rowh

ax.text((mx0 + mx1) / 2, 42.4, "Base × operator grid", ha="center", va="center",
        fontsize=TITLE, fontweight="bold", color=BODY)

def col_x(j):
    return mx0 + labw + j * datw

def row_y(i):                       # bottom edge of body row i (0 = base A)
    return my_top - (i + 2) * rowh

# shaded operator columns
for j, op in enumerate(ops):
    if op in shaded_ops:
        ax.add_patch(Rectangle((col_x(j), my_bot), datw, nbody * rowh,
                               facecolor="#FFF3E0", edgecolor="none", zorder=0))
# alternating body rows + label column
for i in range(nbody):
    if i % 2:
        ax.add_patch(Rectangle((mx0 + labw, row_y(i)), mx1 - mx0 - labw, rowh,
                               facecolor="#00000008", edgecolor="none", zorder=0))
ax.add_patch(Rectangle((mx0, my_bot), labw, nbody * rowh,
                       facecolor="#ECEFF1", edgecolor="none", zorder=0))
# header
ax.add_patch(Rectangle((mx0, my_top - rowh), mx1 - mx0, rowh,
                       facecolor=NAVY, edgecolor="none", zorder=1))
ax.text(mx0 + labw / 2, my_top - rowh / 2, "Base", ha="center", va="center",
        fontsize=CELL, fontweight="bold", color="white", zorder=2)
for j, op in enumerate(ops):
    ax.text(col_x(j) + datw / 2, my_top - rowh / 2, op, ha="center", va="center",
            fontsize=CELL, fontweight="bold", color="white", zorder=2)
# body labels + grid
for i, b in enumerate(bases):
    ax.text(mx0 + labw / 2, row_y(i) + rowh / 2, b, ha="center", va="center",
            fontsize=CELL, fontweight="bold", color=NAVY, zorder=2)
for j in range(len(ops) + 1):
    x = mx0 + labw + j * datw
    ax.plot([x, x], [my_bot, my_top - rowh], color="#D6DBDF", lw=0.8, zorder=1)
for i in range(nbody + 1):
    y = my_bot + i * rowh
    ax.plot([mx0 + labw, mx1], [y, y], color="#D6DBDF", lw=0.8, zorder=1)
ax.add_patch(Rectangle((mx0, my_bot), mx1 - mx0, nbody * rowh,
                       facecolor="none", edgecolor="#B7BEC4", lw=1.0, zorder=1))
# outlined base row
bi = bases.index(outlined_base)
ax.add_patch(Rectangle((mx0, row_y(bi)), mx1 - mx0, rowh, facecolor="none",
                       edgecolor=BLUE[0], lw=2.2, zorder=3))

# legend (under the matrix)
lgy = my_bot - 3.8
ax.add_patch(Rectangle((mx0, lgy - 1.0), 3.0, 2.0, facecolor="none",
                       edgecolor=BLUE[0], lw=1.8))
ax.text(mx0 + 4.0, lgy, "base B — three operators touch it",
        ha="left", va="center", fontsize=LEG, color=BODY)
ax.add_patch(Rectangle((mx0, lgy - 3.6), 3.0, 2.0, facecolor="#FFF3E0",
                       edgecolor="#ED6C02", lw=1.3))
ax.text(mx0 + 4.0, lgy - 2.6, "D2, D4 — each recurs across bases",
        ha="left", va="center", fontsize=LEG, color=BODY)

fig.savefig(OUT, dpi=600)
print("wrote", OUT, "logical size", tuple(round(v, 3) for v in fig.get_size_inches()))
