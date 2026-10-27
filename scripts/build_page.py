"""Build project_page/: copy compressed media and write static/data.js from results/.

    python3 scripts/build_page.py && python3 -m http.server -d project_page 8765
"""
import csv
import json
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = f"{ROOT}/project_page/static"
NC = f"{ROOT}/work/eval/need_clip"
RUNS = f"{ROOT}/runs/opus_director"
CASES = ["dualjustice1", "dualjustice2", "kick", "lovehina"]
VIDEOS = {"m2a": "M2AGemini_Seedance2", "minimax": "M2AGemini_MiniMax-H3", "b": "BM2A-plan_Omni", "c": "COpus-director_Omni"}

PAPER = {  # Table 1 of arXiv 2610.26851 (8 stories)
    "AniMaker": [0.775, 0.749, 0.922, 0.950, 0.979, 7.680, 0.410, 2.694],
    "ViMax+Veo3.1Fast": [0.774, 0.752, 0.881, 0.932, 0.978, 1.639, 0.368, 4.394],
    "ViMax+Seedance2": [0.753, 0.747, 0.927, 0.948, 0.977, 2.541, 0.385, 4.764],
    "StoryMem": [0.728, 0.731, 0.885, 0.922, 0.956, 5.203, 0.275, 3.602],
    "Direct+Seedance2": [0.750, 0.711, 0.852, 0.931, 0.951, 13.941, 0.492, 5.250],
    "M2A(FLUX.2)+Seedance2": [0.781, 0.741, 0.892, 0.942, 0.958, 9.377, 0.595, 4.429],
    "M2A(Gemini)+MiniMax-H3": [0.792, 0.791, 0.940, 0.953, 0.969, 3.715, 0.413, 4.352],
    "M2A(Gemini)+Seedance2": [0.791, 0.768, 0.931, 0.958, 0.960, 9.457, 0.518, 5.090],
}

# cost of condition C per story: (image calls, clip calls, Opus USD, wall minutes); from calls.jsonl + opencode session records
COST = {"dualjustice1": (9, 9, 0.85, 10.4), "dualjustice2": (11, 10, 0.87, 12.7),
        "kick": (9, 9, 0.66, 7.2), "lovehina": (8, 9, 0.63, 7.2)}

# Opus self-review examples: (case, rejected, accepted, caption)
REVIEW = [
    ("kick", "kf/kf5.png", "kf/kf5b.png", "kick · shot 5: the first keyframe showed the whole man, while panel 5 is a worm's-eye close-up of the shoe sole. "
     "Opus regenerated it as that close-up and passed its accepted shot-2 keyframe as the object reference so the cylinder kept its design."),
    ("kick", "kf/kf1.png", "kf/kf1b.png", "kick · shot 1: the cylinder was far too big. In panel 1 it is a small object "
     "spinning in an empty sky."),
    ("dualjustice1", "kf/kf6.png", "kf/kf6c.png", "dualjustice1 · shot 6: the panel crop carried the line between two panels, "
     "which the image model drew as a black bar, and the robot pointed at the wrong target. Fixed in two retries."),
    ("kick", "frames/s6a/sheet.jpg", "frames/s6b/sheet.jpg", "kick · shot 6 clip: in take 1 the man lands and kneels by 2 s, "
     "leaving the panel's composition. Take 2 (slow motion, \u201cdoes not land\u201d) holds the kick pose."),
]


def ff(args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y"] + args, check=True)


def main():
    for c in CASES:
        d = f"{P}/media/{c}"
        os.makedirs(d, exist_ok=True)
        for k, v in VIDEOS.items():
            out = f"{d}/{k}.mp4"
            if not os.path.exists(out):
                ff(["-i", f"{NC}/{v}__{c}.mp4", "-an", "-vf", "scale=640:-2", "-c:v", "libx264", "-crf", "27",
                    "-preset", "slow", "-movflags", "+faststart", "-pix_fmt", "yuv420p", out])
        for i in range(1, 7):
            ff(["-i", f"{ROOT}/data/cases/{c}/panels/panel{i}.png", "-vf", "scale='min(480,iw)':-2", f"{d}/panel{i}.jpg"])
        for f in sorted(os.listdir(f"{ROOT}/data/cases/{c}/pages")):
            ff(["-i", f"{ROOT}/data/cases/{c}/pages/{f}", "-vf", "scale='min(900,iw)':-2", f"{d}/{f[:-4]}.jpg"])
    os.makedirs(f"{P}/review", exist_ok=True)
    review = []
    for n, (c, a, b, cap) in enumerate(REVIEW):
        pair = []
        for tag, src in (("rej", a), ("acc", b)):
            out = f"review/{n}_{tag}.jpg"
            ff(["-i", f"{RUNS}/{c}/{src}", "-vf", "scale='min(720,iw)':-2", f"{P}/{out}"])
            pair.append(f"static/{out}")
        review.append(dict(case=c, rej=pair[0], acc=pair[1], caption=cap))

    summary = json.load(open(f"{ROOT}/results/summary.json"))
    per = list(csv.DictReader(open(f"{ROOT}/results/per_video.csv")))
    pages = {c: sorted(f[:-4] + ".jpg" for f in os.listdir(f"{ROOT}/data/cases/{c}/pages")) for c in CASES}
    calls = {}
    for c in CASES:
        r = [json.loads(l) for l in open(f"{RUNS}/{c}/calls.jsonl")]
        calls[c] = dict(image=sum(x["tool"] == "image" for x in r), clip=sum(x["tool"] == "clip" for x in r))
    data = dict(summary=summary, per_video=per, paper=PAPER, cost=COST, calls=calls, cases=CASES, pages=pages,
                review=review, check=open(f"{ROOT}/results/paper_check.txt").read())
    open(f"{P}/data.js", "w").write("window.DATA = " + json.dumps(data, indent=1) + ";\n")
    print("ok", sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(P) for f in fs) // 1_000_000, "MB")


if __name__ == "__main__":
    main()
