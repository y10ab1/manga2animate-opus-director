"""MangaEval video metrics for every method on the 4 Manga109-s cases, one identical protocol:

  1. video -> 6 segments with their auto_clip.py (as in the paper; also for methods whose shot
     boundaries are known, so nobody gets an advantage from exact cuts)
  2. I2VB (DreamSim vs. the source manga panel), SC, BC, MS     -> their evaluate_i2v.py   (env m2a-vbench)
  3. DD (continuous RAFT flow)                                  -> their modified_dynamic_degree.py
  4. I2VS (DINOv3 ViT-B/16 vs. character ref)                   -> scripts/i2vs_dinov3.py   (env m2a-score)
  5. Shadow-v2, Waifu-v3 (8 frames / whole video)               -> their aesthetic/score.py (env m2a-score)
  6. per-segment -> per-video -> per-method mean                -> results/

  python scripts/eval_all.py prep|clip|vbench|dd|i2vs|aes|report|all [--only METHOD ...]
"""
import argparse, csv, glob, json, os, shutil, subprocess, sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
M2A = f"{ROOT}/third_party/Manga2Animate/mangaeval"
OUT = f"{ROOT}/data/m2a_eval/outputs"
W = f"{ROOT}/work/eval"
RES = f"{ROOT}/results"
CASES = ["dualjustice1", "dualjustice2", "kick", "lovehina"]

# Characters visible in each target panel (I2VS refs; None = no character -> skipped, as in the paper).
# Read off the panels and their script.json shot descriptions.
PANEL_CHARS = {
    "dualjustice1": [["girl1", "robot1"], ["dragon1"], ["dragon1"], ["robot1", "dragon1"],
                     ["girl1", "robot1", "dragon1"], ["girl1", "robot1", "dragon1"]],
    "dualjustice2": [["girl1"], ["girl1"], ["girl1"], ["monster1"], ["girl1"], ["girl1", "monster1"]],
    "kick": [None, ["girl1"], ["girl1"], None, None, ["girl1", "man1"]],
    "lovehina": [["girl1"], ["girl1"], ["boy1"], ["boy1", "girl1"], ["girl1"], ["girl1"]],
}


def methods(case):
    o = f"{OUT}/{case}"
    b = sorted(glob.glob(f"{ROOT}/runs/m2a_plan_omni/results/{case}/video/omni/run_*/final_story.mp4"))
    return {
        "M2A(Gemini)+Seedance2": f"{o}/ours_gemini/video_seedance2.mp4",
        "M2A(Gemini)+MiniMax-H3": f"{o}/ours_gemini/video_minimax_h3.mp4",
        "M2A(FLUX.2)+Seedance2": f"{o}/ours_flux2/video_seedance2.mp4",
        "Direct+Seedance2": f"{o}/direct_manga2video/video_seedance2.mp4",
        "ViMax+Seedance2": f"{o}/vimax/video_seedance2.mp4",
        "ViMax+Veo3.1Fast": f"{o}/vimax/video_veo31fast.mp4",
        "StoryMem": f"{o}/storymem/video.mp4",
        "AniMaker": [f"{o}/animaker/video_clips/scene_{i}_clip_1.mp4" for i in range(1, 7)],
        "B:M2A-plan+Omni": b[-1] if b else None,
        "C:Opus-director+Omni": f"{ROOT}/runs/opus_director/{case}/final.mp4",
    }


EXACT = {"B:M2A-plan+Omni", "C:Opus-director+Omni"}  # shot boundaries known -> also score with exact cuts
# (AniMaker's auto_clip cuts already land within ~0.1 s of its true scene boundaries)
EX = " [exact cuts]"


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)


def exact_bounds(m, c):
    """[t0..t6] shot boundaries (seconds) in the evaluated video."""
    if m.startswith("C:"):
        s = json.load(open(f"{ROOT}/runs/opus_director/{c}/final.mp4.segments.json"))
        return [0.0] + [x["end"] for x in s]
    if m.startswith("B:"):
        d = os.path.dirname(methods(c)[m])
        parts = [f"{d}/panel_{i}/best_panel_{i}.mp4" for i in range(1, 7)]
    else:
        parts = methods(c)[m]
    t = [0.0]
    for p in parts:
        t.append(t[-1] + dur(p))
    return t


def key(m, c):
    return m.replace(EX, "_exact").replace(":", "").replace("+", "_").replace("(", "").replace(")", "").replace(".", "") + "__" + c


def sh(cmd, env=None, cwd=None, log=None):
    print("$", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    with open(log, "a") if log else open(os.devnull, "w") as lf:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, env={**os.environ, **(env or {})},
                           stdout=lf if log else None, stderr=subprocess.STDOUT if log else None)
    if r.returncode:
        sys.exit(f"failed ({r.returncode}): {cmd}  (log: {log})")


NORM = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24,setsar=1"


def concat(paths, out):
    tmp = out + ".parts"
    os.makedirs(tmp, exist_ok=True)
    parts = []
    for i, p in enumerate(paths):
        q = f"{tmp}/{i}.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", p, "-an", "-vf", NORM,
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", q], check=True)
        parts.append(q)
    open(f"{tmp}/l.txt", "w").write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/l.txt", "-c", "copy", out], check=True)
    shutil.rmtree(tmp)


def items(only=None, exact=True):
    for c in CASES:
        for m, p in methods(c).items():
            if only and m not in only:
                continue
            ok = all(os.path.exists(x) for x in p) if isinstance(p, list) else (p and os.path.exists(p))
            yield m, c, p, ok
            if exact and m in EXACT:
                yield m + EX, c, p, ok


def cut_exact(m, c):
    src = f"{W}/need_clip/{key(m, c)}.mp4"
    d = f"{W}/need_clip/{key(m + EX, c)}"
    if os.path.isdir(d) and len(glob.glob(f"{d}/panel_*.mp4")) == 6:
        return
    os.makedirs(d, exist_ok=True)
    if not m.startswith("C:"):  # AniMaker / B: the per-shot clips themselves are the exact segments
        parts = methods(c)[m] if m == "AniMaker" else [
            f"{os.path.dirname(methods(c)[m])}/panel_{i}/best_panel_{i}.mp4" for i in range(1, 7)]
        for i, p in enumerate(parts):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", p, "-an", "-vf", NORM, "-c:v", "libx264",
                            "-crf", "16", "-pix_fmt", "yuv420p", f"{d}/panel_{i + 1:02d}.mp4"], check=True)
        return
    t = exact_bounds(m, c)
    for i in range(6):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t[i]:.3f}", "-to", f"{t[i + 1]:.3f}", "-i", src,
                        "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", f"{d}/panel_{i + 1:02d}.mp4"], check=True)
    open(f"{d}/transitions.txt", "w").write(" ".join(f"{x:.3f}" for x in t))


def prep(a):
    os.makedirs(f"{W}/need_clip", exist_ok=True)
    for m, c, p, ok in items(a.only, exact=False):
        if not ok:
            print("MISSING", m, c); continue
        dst = f"{W}/need_clip/{key(m, c)}.mp4"
        if os.path.exists(dst) and not a.force:
            continue
        if isinstance(p, list):
            concat(p, dst)
        else:
            shutil.copy(p, dst)
        print("prep", m, c)


def clip(a):
    env = {"PYTHONPATH": f"{M2A}/vbench"}
    sh(["conda", "run", "--no-capture-output", "-n", "m2a-vbench", "python", f"{M2A}/vbench/auto_clip.py"],
       env=env, cwd=W, log=f"{W}/auto_clip.log")
    for m, c, p, ok in items(exact=False):
        if ok and m in EXACT:
            cut_exact(m, c)
    # flat folder for VBench: <key>__panel_0k.mp4 paired by name with the manga panel <key>__panel_0k.png
    flat_v, flat_i = f"{W}/flat_videos", f"{W}/flat_panels"
    shutil.rmtree(flat_v, ignore_errors=True); shutil.rmtree(flat_i, ignore_errors=True)
    os.makedirs(flat_v); os.makedirs(flat_i)
    for m, c, p, ok in items():
        k = key(m, c)
        if not ok or not os.path.isdir(f"{W}/need_clip/{k}"):
            continue
        for i in range(1, 7):
            os.symlink(f"{W}/need_clip/{k}/panel_{i:02d}.mp4", f"{flat_v}/{k}__panel_{i:02d}.mp4")
            os.symlink(f"{ROOT}/data/cases/{c}/panels/panel{i}.png", f"{flat_i}/{k}__panel_{i:02d}.png")


def vbench(a):
    out = f"{W}/vbench_out"
    shutil.rmtree(out, ignore_errors=True)
    env = {"PYTHONPATH": f"{M2A}/vbench"}
    base = ["conda", "run", "--no-capture-output", "-n", "m2a-vbench", "python", "evaluate_i2v.py", "--mode", "custom_input",
            "--ratio", "16-9", "--videos_path", f"{W}/flat_videos", "--output_path", out]
    sh(base + ["--dimension", "i2v_background", "--custom_image_folder", f"{W}/flat_panels"], env=env, cwd=f"{M2A}/vbench", log=f"{W}/vbench.log")
    sh(base + ["--dimension", "subject_consistency", "background_consistency", "motion_smoothness"], env=env, cwd=f"{M2A}/vbench", log=f"{W}/vbench.log")


def manifest(i2vs):
    rows = []
    for m, c, p, ok in items():
        k = key(m, c)
        if not ok or not os.path.isdir(f"{W}/need_clip/{k}"):
            continue
        for i in range(1, 7):
            v = f"{W}/need_clip/{k}/panel_{i:02d}.mp4"
            chars = PANEL_CHARS[c][i - 1]
            if not i2vs:
                rows.append(dict(case=c, segment=i, method=m, video_path=v, character_ref=""))
            elif chars is None:
                rows.append(dict(case=c, segment=i, method=m, video_path=v, character_ref="", character="", skip="NO_CHARACTER"))
            else:
                for ch in chars:
                    rows.append(dict(case=c, segment=i, method=m, video_path=v, character=ch,
                                     character_ref=f"{ROOT}/data/cases/{c}/characters/{ch}.png"))
    return rows


def dd(a):
    json.dump(manifest(False), open(f"{W}/manifest_dd.json", "w"), indent=1)
    sh(["conda", "run", "--no-capture-output", "-n", "m2a-vbench", "python", "tools/modified_dynamic_degree.py",
        "--manifest", f"{W}/manifest_dd.json", "--output", f"{W}/dd.csv",
        "--checkpoint", os.path.expanduser("~/.cache/vbench/raft_model/models/raft-things.pth")],
       env={"PYTHONPATH": f"{M2A}/vbench"}, cwd=f"{M2A}/vbench", log=f"{W}/dd.log")


def i2vs(a):
    json.dump(manifest(True), open(f"{W}/manifest_i2vs.json", "w"), indent=1)
    sh(["conda", "run", "--no-capture-output", "-n", "m2a-score", "python", f"{ROOT}/scripts/i2vs_dinov3.py",
        f"{W}/manifest_i2vs.json", f"{W}/i2vs.csv"], log=f"{W}/i2vs.log")


def aes(a):
    sh(["conda", "run", "--no-capture-output", "-n", "m2a-score", "python", f"{M2A}/aesthetic/score.py",
        "--no-recursive", "--frames-per-video", "8", "--out", f"{W}/aesthetic.csv"] +
       sorted(glob.glob(f"{W}/need_clip/*.mp4")), cwd=f"{M2A}/aesthetic", log=f"{W}/aes.log")


def mean(x):
    x = [v for v in x if v is not None]
    return sum(x) / len(x) if x else float("nan")


def report(a):
    k2mc = {key(m, c): (m, c) for m, c, _, _ in items()}
    seg = defaultdict(lambda: defaultdict(list))  # (m,c) -> metric -> per-segment values

    for f in glob.glob(f"{W}/vbench_out/*_eval_results.json"):
        for dim, (_, per) in json.load(open(f)).items():
            name = {"i2v_background": "I2VB", "subject_consistency": "SC", "background_consistency": "BC",
                    "motion_smoothness": "MS"}[dim]
            for r in per:
                k = os.path.basename(r["video_path"]).rsplit("__panel_", 1)[0]
                if k not in k2mc:
                    continue
                seg[k2mc[k]][name].append(r["video_results"])
    if os.path.exists(f"{W}/dd.csv"):
        for r in csv.DictReader(open(f"{W}/dd.csv")):
            if r.get("normalized_modified_dd_mean"):
                seg[(r["method"], r["case"])]["DD"].append(float(r["normalized_modified_dd_mean"]))
    if os.path.exists(f"{W}/i2vs.csv"):
        per_seg = defaultdict(list)
        for r in csv.DictReader(open(f"{W}/i2vs.csv")):
            if r["status"] == "SUCCESS":
                per_seg[(r["method"], r["case"], r["segment"])].append(float(r["score"]))
        for (m, c, s), v in per_seg.items():
            seg[(m, c)]["I2VS"].append(mean(v))  # several characters in a panel -> average
    if os.path.exists(f"{W}/aesthetic.csv"):
        per_vid = defaultdict(lambda: defaultdict(list))
        for r in csv.DictReader(open(f"{W}/aesthetic.csv")):
            k = os.path.basename(r["path"])[:-4]
            per_vid[k2mc[k]][{"aesthetic_shadow_v2": "Shadow-v2", "waifu_scorer_v3": "Waifu-v3"}[r["metric"]]].append(float(r["score"]))
        for mc, d in per_vid.items():
            for n, v in d.items():
                seg[mc][n].append(mean(v))
                if mc[0] in EXACT:
                    seg[(mc[0] + EX, mc[1])][n].append(mean(v))  # whole-video metric, cuts don't matter

    cols = ["I2VS", "I2VB", "SC", "BC", "MS", "DD", "Shadow-v2", "Waifu-v3"]
    valid = set(k2mc.values())
    per_video = {mc: {n: mean(seg[mc][n]) for n in cols} for mc in seg if mc in valid}
    os.makedirs(RES, exist_ok=True)
    with open(f"{RES}/per_video.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["method", "case"] + cols)
        for (m, c), d in sorted(per_video.items()):
            w.writerow([m, c] + [f"{d[n]:.4f}" for n in cols])
    order = list(dict.fromkeys(m for m, c, _, _ in items()))
    lines = ["| Method | n | " + " | ".join(cols) + " |", "|---" * (len(cols) + 2) + "|"]
    summary = {}
    for m in order:
        vids = [per_video[(m, c)] for c in CASES if (m, c) in per_video]
        if not vids:
            continue
        summary[m] = {n: mean([v[n] for v in vids if v[n] == v[n]]) for n in cols}
        lines.append(f"| {m} | {len(vids)} | " + " | ".join(
            f"{summary[m][n]:.3f}" if n not in ("DD", "Waifu-v3") else f"{summary[m][n]:.2f}" for n in cols) + " |")
    json.dump(summary, open(f"{RES}/summary.json", "w"), indent=1)
    open(f"{RES}/summary.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prep", "clip", "vbench", "dd", "i2vs", "aes", "report", "all"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for st in (["prep", "clip", "vbench", "dd", "i2vs", "aes", "report"] if a.stage == "all" else [a.stage]):
        globals()[st](a)
