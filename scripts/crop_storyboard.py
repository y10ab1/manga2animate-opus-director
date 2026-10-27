"""Cut a Manga2Animate 3x2 storyboard (panels with black borders + 'Panel N' labels) into 6 panels.
Replaces their MAGI-based crop_storyboard_panels.py (avoids its torch stack).
  python scripts/crop_storyboard.py storyboard.png out_dir
"""
import os, sys
import numpy as np
from PIL import Image


def runs(mask):
    """[start, end) of consecutive True runs."""
    out, start = [], None
    for i, v in enumerate(list(mask) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i)); start = None
    return out


def crop(path, out_dir, n_cols=3, n_rows=2):
    im = Image.open(path).convert("RGB")
    g = np.asarray(im.convert("L")) < 80
    W, H = im.size
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for r in range(n_rows):
        for c in range(n_cols):
            x0, x1 = c * W // n_cols, (c + 1) * W // n_cols
            y0, y1 = r * H // n_rows, (r + 1) * H // n_rows
            cell = g[y0:y1, x0:x1]
            # border lines: rows / cols that are mostly dark
            rows = runs(cell.mean(1) > 0.5)
            cols = runs(cell.mean(0) > 0.4)
            if len(rows) >= 2 and len(cols) >= 2:
                top, bot = rows[0][1], rows[-1][0]
                left, right = cols[0][1], cols[-1][0]
            else:  # no border: trim the label strip and white margins
                ink = np.where(cell[: int(cell.shape[0] * 0.88)].any(1))[0]
                inkc = np.where(cell.any(0))[0]
                top, bot, left, right = ink[0], ink[-1], inkc[0], inkc[-1]
            n += 1
            im.crop((x0 + left, y0 + top, x0 + right, y0 + bot)).save(f"{out_dir}/panel{n}.png")
    print(out_dir, n)


if __name__ == "__main__":
    crop(sys.argv[1], sys.argv[2])
