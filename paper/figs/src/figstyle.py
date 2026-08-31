"""Shared drawing style for the paper's generated figures (fig1, fig2).

Palette and box/arrow conventions match the existing fig4/fig5:
DejaVu Sans, rounded rectangles, ~2.4 pt strokes.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "svg.fonttype": "none",
})

# palette: (edge, face, text)
NAVY   = "#1F3A5F"
GREEN  = ("#2E7D32", "#E8F5E9", "#2E7D32")
ORANGE = ("#ED6C02", "#FFF3E0", "#B4530A")
BLUE   = ("#1565C0", "#E3F2FD", "#1565C0")
RED    = ("#C62828", "#FFEBEE", "#C62828")
GREY   = ("#78909C", "#ECEFF1", "#37474F")
# PURPLE is NOT one of the four semantic colours (green/orange/blue/red); it is
# used only in fig2 for the "second world_drift example" box (A_drift_D2), so it
# does not collide with fig1's "both -> defer" red.
PURPLE = ("#6A1B9A", "#F3E5F5", "#6A1B9A")
DARK   = (NAVY, NAVY, "#FFFFFF")          # solid navy block, white text
BODY   = "#333333"

LW = 2.4
ROUND = 0.028


def box(ax, x, y, w, h, colors, title, sub=None, *, dashed=False,
        title_size=13, sub_size=10.5, ha_title="center"):
    """Rounded box centred at (x, y) with a bold title and optional sub-text."""
    edge, face, tcol = colors
    p = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=f"round,pad=0.02,rounding_size={ROUND}",
        linewidth=LW, edgecolor=edge, facecolor=face,
        linestyle=(0, (4, 3)) if dashed else "solid",
        mutation_aspect=1.0, zorder=2,
    )
    ax.add_patch(p)
    if sub:
        ax.text(x, y + h * 0.27, title, ha=ha_title, va="center",
                fontsize=title_size, fontweight="bold", color=tcol, zorder=3)
        ax.text(x, y - h * 0.16, sub, ha="center", va="center",
                fontsize=sub_size, color=tcol if tcol == "#FFFFFF" else BODY,
                zorder=3, linespacing=1.3)
    else:
        ax.text(x, y, title, ha=ha_title, va="center",
                fontsize=title_size, fontweight="bold", color=tcol, zorder=3)
    return p


def arrow(ax, xy1, xy2, *, color="#55606A", lw=2.2, rad=0.0, ms=16):
    a = FancyArrowPatch(
        xy1, xy2, arrowstyle="-|>", mutation_scale=ms,
        linewidth=lw, color=color,
        connectionstyle=f"arc3,rad={rad}", zorder=1,
        shrinkA=0, shrinkB=0,
    )
    ax.add_patch(a)


def newfig(w_in, h_in, xlim, ylim, dpi=220):
    fig, ax = plt.subplots(figsize=(w_in, h_in), dpi=dpi)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    return fig, ax
