"""Regenerate figs/fig4_confusion.png and figs/fig5_verif.png from the author's
originals in figs/.orig/.

fig1 and fig2 are now drawn by fig1_gen.py / fig2_gen.py.  fig4 and fig5 are the
author-supplied raster figures (no vector source); the only processing they need
is a tighter crop so their in-figure text is larger at the column width:
  - crop to the content bounding box with a small uniform pad
  - fig4 only: collapse the oversized all-white band between its two panels

Run:  python crop_fig4_fig5.py           (paths are relative to figs/src/)
"""
import numpy as np
from PIL import Image

SRC = "../.orig"
DST = ".."
PAD = 40  # px of white kept around the content


def content_box(a, thresh=245):
    nonwhite = np.any(a < thresh, axis=2)
    rows = np.where(nonwhite.any(axis=1))[0]
    cols = np.where(nonwhite.any(axis=0))[0]
    return cols[0], rows[0], cols[-1], rows[-1]


def pad_crop(im, box, pad=PAD):
    W, H = im.size
    l, t, r, b = box
    return im.crop((max(0, l - pad), max(0, t - pad),
                    min(W, r + 1 + pad), min(H, b + 1 + pad)))


def process(name, collapse_band=None):
    im = Image.open(f"{SRC}/{name}.png").convert("RGB")
    before = im.size
    if collapse_band is not None:
        y0, y1, keep = collapse_band
        top = im.crop((0, 0, im.size[0], y0 + keep // 2))
        bottom = im.crop((0, y1 - keep // 2, im.size[0], im.size[1]))
        im = Image.new("RGB", (im.size[0], top.size[1] + bottom.size[1]), "white")
        im.paste(top, (0, 0))
        im.paste(bottom, (0, top.size[1]))
    out = pad_crop(im, content_box(np.asarray(im)))
    out.save(f"{DST}/{name}.png")
    print(f"{name}: {before[0]}x{before[1]} -> {out.size[0]}x{out.size[1]}")


process("fig4_confusion", collapse_band=(612, 896, 110))
process("fig5_verif")
