"""Contact sheet of a folder of images (numbered) -> one jpg."""
import sys, glob, re
from PIL import Image, ImageDraw
files = sorted(glob.glob(sys.argv[1]), key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)])
H = 300
ims = [Image.open(f).convert("RGB") for f in files]
ims = [i.resize((max(1, int(i.width * H / i.height)), H)) for i in ims]
W = sum(i.width for i in ims) + 10 * len(ims)
cols, rows, cur, x = [], [], [], 0
for i in ims:
    if x + i.width > 1800 and cur:
        rows.append(cur); cur, x = [], 0
    cur.append(i); x += i.width + 10
rows.append(cur)
sheet = Image.new("RGB", (1800, len(rows) * (H + 30)), "white")
d = ImageDraw.Draw(sheet); n = 0
for r, row in enumerate(rows):
    x = 0
    for i in row:
        n += 1
        sheet.paste(i, (x, r * (H + 30) + 25)); d.text((x + 4, r * (H + 30) + 5), str(n), fill="red")
        x += i.width + 10
sheet.save(sys.argv[2], quality=85)
