"""Held-out character references for I2VS (leak check).

The refs in data/cases/<case>/characters/ were given to condition C as generation input and are
also what I2VS scores against. Here every character gets K new refs cropped from *other* Manga109-s
spreads of the same chapter, which no method ever saw. Boxes come from the Manga109 `body`
annotations (largest first, one per spread, input spreads excluded).

Output: data/cases/<case>/heldout/<tag>_<k>.png, heldout.json, and results/heldout_refs.jpg (visual check).
"""
import json, os, sys, xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from build_cases import CASES, M109

K = 3
WINDOW = 6          # stay within +-WINDOW spreads of the input -> same chapter / same monster design
MIN_SIDE = 150      # skip tiny bodies
# manual exclusions (character not clearly visible: mostly another character, motion blur,
# transformation scene), decided from the sheet before any scoring; see data/heldout_exclude.json
# manual exclusions after looking at results/heldout_refs.jpg: (case, tag, spread)
EXCLUDE = {tuple(x) for x in json.load(open("data/heldout_exclude.json"))} if os.path.exists("data/heldout_exclude.json") else set()


def candidates(book, name, center, inputs, window=WINDOW):
    root = ET.parse(f"{M109}/annotations_main/{book}.xml").getroot()
    cid = {c.get("name"): c.get("id") for c in root.iter("character")}[name]
    out = []
    for p in root.iter("page"):
        idx = int(p.get("index"))
        if idx in inputs or abs(idx - center) > window:
            continue
        for e in p.iter("body"):
            if e.get("character") != cid:
                continue
            b = [int(e.get(k)) for k in ("xmin", "ymin", "xmax", "ymax")]
            if min(b[2] - b[0], b[3] - b[1]) < MIN_SIDE:
                continue
            out.append(((b[2] - b[0]) * (b[3] - b[1]), idx, b))
    return sorted(out, reverse=True)


def main():
    tiles = []
    for case, cfg in CASES.items():
        inputs = {p for _, p in cfg["pages"]}
        center = sum(inputs) / len(inputs)
        d = f"data/cases/{case}/heldout"
        os.makedirs(d, exist_ok=True)
        meta = {}
        for name, tag in cfg["chars"].items():
            picked, used = [], set()
            cands = candidates(cfg["book"], name, center, inputs)
            if len({i for _, i, _ in cands}) < K + 2 and name != "悪魔獣":  # monsters change design per chapter
                cands += candidates(cfg["book"], name, center, inputs, 2 * WINDOW)
            for area, idx, b in cands:
                if idx in used or (case, tag, idx) in EXCLUDE:
                    continue
                used.add(idx)
                picked.append((idx, b))
                if len(picked) == K:
                    break
            meta[tag] = []
            for k, (idx, b) in enumerate(picked, 1):
                im = Image.open(f"{M109}/images/{cfg['book']}/{idx:03d}.jpg").convert("RGB").crop(b)
                im.save(f"{d}/{tag}_{k}.png")
                meta[tag].append(dict(file=f"{tag}_{k}.png", name=name, spread=idx, box=b))
                tiles.append((f"{case}/{tag}_{k} s{idx}", im))
            tiles.append((f"{case}/{tag} (input ref)", Image.open(f"data/cases/{case}/characters/{tag}.png").convert("RGB")))
            print(case, tag, name, [m["spread"] for m in meta[tag]])
        json.dump(meta, open(f"{d}/heldout.json", "w"), indent=1, ensure_ascii=False)

    W, H = 220, 260
    cols = K + 1
    sheet = Image.new("RGB", (cols * W, -(-len(tiles) // cols) * H), "white")
    dr = ImageDraw.Draw(sheet)
    for i, (lab, im) in enumerate(tiles):
        im = im.copy(); im.thumbnail((W - 10, H - 30))
        x, y = (i % cols) * W, (i // cols) * H
        sheet.paste(im, (x + 5, y + 25))
        dr.text((x + 5, y + 5), lab, fill="red")
    os.makedirs("results", exist_ok=True)
    sheet.save("results/heldout_refs.jpg", quality=85)


if __name__ == "__main__":
    main()
