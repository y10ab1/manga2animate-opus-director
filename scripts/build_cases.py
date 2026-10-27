"""Build the 4 Manga109-s cases of the Manga2Animate evaluation set.

Pages  : the page images shown on their project page (= the cropped pages they fed the pipeline).
         The Manga109-s spread each one comes from was found with SIFT (scripts/find_m109_pages.py).
Panels : 6 target panels per case, boxes in page coordinates, in the order of their final script
         (checked against data/m2a_eval/outputs/<case>/ours_gemini/{script.json,storyboard.png}).
         dualjustice1 uses the panels shipped in their repo (mangaeval example case 01).
Refs   : one reference crop per main character, taken from the input pages (the paper's fallback
         when no official color art exists; their refs are only released for dualjustice1).
Every method (theirs, re-scored, and ours) is evaluated against these same panels and refs.

Output: data/cases/<case>/{pages/page<k>.png, panels/panel<i>.png, characters/<name>.png, case.json}
"""
import json, os, shutil, xml.etree.ElementTree as ET
from PIL import Image

M109 = "/home/yuehpo/coding/webtoon-sfx-research/data/coo"
PP = "third_party/Manga2Animate/project_page/static/images"
EX01 = "third_party/Manga2Animate/mangaeval/vistorybench/data/dataset/ViStory/01"

CASES = {
    "dualjustice1": dict(book="DualJustice", pages=[("dualjustice1_manga_1", 18), ("dualjustice1_manga_2", 18)],
                         panels="repo", chars={"アヴァロン": "robot1", "パレストリーナ": "girl1", "悪魔獣": "dragon1"}),
    "dualjustice2": dict(book="DualJustice", pages=[("dualjustice2_manga_1", 49), ("dualjustice2_manga_2", 50)],
                         panels=[(1, (5, 5, 944, 785)), (1, (5, 815, 944, 1110)), (1, (5, 1135, 944, 1882)),
                                 (2, (5, 10, 944, 965)), (2, (480, 975, 944, 1375)), (2, (5, 975, 470, 1375))],
                         chars={"悪魔獣": "monster1", "湖奈川美月": "girl1"},
                         refs={"girl1": (1, (230, 1240, 700, 1882)), "monster1": (2, (130, 230, 720, 930))}),
    "kick": dict(book="DualJustice", pages=[("dualjustice-kick_manga_1", 33), ("dualjustice-kick_manga_2", 34)],
                 panels=[(1, (625, 30, 775, 625)), (1, (255, 40, 630, 641)), (1, (0, 70, 300, 395)),
                         (1, (0, 0, 640, 100)), (1, (0, 395, 335, 641)), (2, (0, 0, 779, 640))],
                 chars={"天眼アリタ": "girl1", "瀬守源路": "man1"},
                 refs={"girl1": (1, (0, 70, 300, 395)), "man1": (2, (440, 90, 779, 620))}),
    "lovehina": dict(book="LoveHina_vol01", pages=[("lovehina_manga", 84)],
                     panels=[(1, (75, 20, 760, 145)), (1, (590, 160, 760, 422)), (1, (590, 425, 760, 812)),
                             (1, (458, 160, 590, 812)), (1, (75, 160, 452, 292)), (1, (0, 295, 456, 839))],
                     chars={"青山素子": "girl1", "浦島景太郎": "boy1"},
                     refs={"girl1": (1, (90, 300, 456, 760)), "boy1": (1, (600, 560, 760, 800))}),
}


def largest_bodies(book, page_idx, wanted):
    root = ET.parse(f"{M109}/annotations_main/{book}.xml").getroot()
    ids = {c.get("name"): c.get("id") for c in root.iter("character")}
    best = {}
    for p in root.iter("page"):
        if int(p.get("index")) not in page_idx:
            continue
        for kind in ("body", "face"):
            for e in p.iter(kind):
                for name in wanted:
                    if e.get("character") == ids.get(name):
                        b = [int(e.get(k)) for k in ("xmin", "ymin", "xmax", "ymax")]
                        score = (kind == "body", (b[2] - b[0]) * (b[3] - b[1]))
                        if score > best.get(name, ((False, 0), None, None))[0]:
                            best[name] = (score, int(p.get("index")), b)
    return best


def build(case, cfg, out="data/cases"):
    d = f"{out}/{case}"
    shutil.rmtree(d, ignore_errors=True)
    for s in ("pages", "panels", "characters"):
        os.makedirs(f"{d}/{s}")
    pages = []
    for k, (img, _) in enumerate(cfg["pages"], 1):
        im = Image.open(f"{PP}/{img}.jpg").convert("RGB")
        im.save(f"{d}/pages/page{k}.png")
        pages.append(im)
    if cfg["panels"] == "repo":
        for i in range(1, 7):
            shutil.copy(f"{EX01}/manga_panels/panel{i}.png", f"{d}/panels/panel{i}.png")
        panels = "repo:mangaeval/.../ViStory/01/manga_panels"
        for name, tag in cfg["chars"].items():
            Image.open(f"{EX01}/image/{tag}/00.jpg").convert("RGB").save(f"{d}/characters/{tag}.png")
        refs = {tag: dict(name=name, source="their repo") for name, tag in cfg["chars"].items()}
    else:
        for i, (k, box) in enumerate(cfg["panels"], 1):
            pages[k - 1].crop(box).save(f"{d}/panels/panel{i}.png")
        panels = [dict(panel=i, page=k, box=box) for i, (k, box) in enumerate(cfg["panels"], 1)]
        refs = {}
        for tag, (k, box) in cfg["refs"].items():
            pages[k - 1].crop(box).save(f"{d}/characters/{tag}.png")
            name = next(n for n, t in cfg["chars"].items() if t == tag)
            refs[tag] = dict(name=name, source=f"crop of input page {k}", box=box)
    json.dump(dict(case=case, book=cfg["book"], pages=[dict(image=i, manga109_page=p) for i, p in cfg["pages"]],
                   panels=panels, characters=refs), open(f"{d}/case.json", "w"), indent=1, ensure_ascii=False)
    print(case, "ok", list(refs))


if __name__ == "__main__":
    for c, cfg in CASES.items():
        build(c, cfg)
