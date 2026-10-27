"""Leak check for I2VS: re-score every method's segments against held-out character refs.

Condition C was given data/cases/<case>/characters/*.png as generation input, and the main I2VS
scores against those same files. Here the refs are replaced by 3 crops per character from other
spreads of the same chapter (scripts/build_heldout_refs.py) that no method saw; the per-character
score is the mean over the 3 refs. Same segments, same formula, same aggregation as eval_all.py.

I2VS = 0.4 * max_t sim(frame_t, ref) + 0.6 * (temporal terms that ignore the ref), so the table
also reports the ref term alone (RefSim = max_t sim) where any leak would show undiluted.

  python scripts/eval_heldout.py run|report
"""
import csv, json, os, subprocess, sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
W = f"{ROOT}/work/eval"
RES = f"{ROOT}/results"
CASES = ["dualjustice1", "dualjustice2", "kick", "lovehina"]


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def run():
    rows = []
    for r in json.load(open(f"{W}/manifest_i2vs.json")):
        if r.get("skip"):
            continue
        rows.append({**r, "ref_set": "input"})
        meta = json.load(open(f"{ROOT}/data/cases/{r['case']}/heldout/heldout.json"))
        for h in meta[r["character"]]:
            rows.append({**r, "ref_set": "heldout", "character_ref": f"{ROOT}/data/cases/{r['case']}/heldout/{h['file']}"})
    json.dump(rows, open(f"{W}/manifest_i2vs_heldout.json", "w"), indent=1)
    with open(f"{W}/i2vs_heldout.log", "w") as log:
        subprocess.run(["conda", "run", "--no-capture-output", "-n", "m2a-score", "python",
                        f"{ROOT}/scripts/i2vs_dinov3.py", f"{W}/manifest_i2vs_heldout.json", f"{W}/i2vs_heldout.csv"],
                       stdout=log, stderr=subprocess.STDOUT, check=True)


def report():
    # (ref_set, metric) -> (method, case, segment, character) -> values over refs
    per = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(f"{W}/i2vs_heldout.csv")):
        if r["status"] != "SUCCESS":
            continue
        k = (r["method"], r["case"], r["segment"], r["character"])
        per[(r["ref_set"], "I2VS")][k].append(float(r["score"]))
        per[(r["ref_set"], "RefSim")][k].append(float(r["ref_max"]))
    out = {}
    for col, d in per.items():
        seg = defaultdict(list)       # refs -> character -> segment
        for (m, c, s, ch), v in d.items():
            seg[(m, c, s)].append(mean(v))
        vid = defaultdict(list)
        for (m, c, s), v in seg.items():
            vid[(m, c)].append(mean(v))
        for (m, c), v in vid.items():
            out.setdefault(m, {}).setdefault(c, {})[col] = mean(v)

    cols = [("input", "I2VS"), ("heldout", "I2VS"), ("input", "RefSim"), ("heldout", "RefSim")]
    order = ["M2A(Gemini)+Seedance2", "M2A(Gemini)+MiniMax-H3", "M2A(FLUX.2)+Seedance2", "Direct+Seedance2",
             "ViMax+Seedance2", "ViMax+Veo3.1Fast", "StoryMem", "AniMaker",
             "B:M2A-plan+Omni", "B:M2A-plan+Omni [exact cuts]", "C:Opus-director+Omni", "C:Opus-director+Omni [exact cuts]"]
    summary = {m: {f"{a}/{b}": mean([out[m][c][(a, b)] for c in CASES if c in out[m]]) for a, b in cols}
               for m in order if m in out}
    rank = {k: sorted(summary, key=lambda m: -summary[m][k]) for k in summary[order[0]]}
    lines = ["| Method | I2VS (input refs) | I2VS (held-out) | RefSim (input) | RefSim (held-out) |",
             "|---|---|---|---|---|"]
    for m in summary:
        lines.append(f"| {m} | " + " | ".join(f"{summary[m][k]:.3f} (#{rank[k].index(m) + 1})" for k in summary[m]) + " |")
    lines += ["", "Per case, I2VS held-out / RefSim held-out:", "",
              "| Method | " + " | ".join(CASES) + " |", "|---" * (len(CASES) + 1) + "|"]
    for m in summary:
        lines.append(f"| {m} | " + " | ".join(
            f"{out[m][c][('heldout', 'I2VS')]:.3f} / {out[m][c][('heldout', 'RefSim')]:.3f}" if c in out[m] else "-"
            for c in CASES) + " |")
    open(f"{RES}/i2vs_heldout.md", "w").write("\n".join(lines) + "\n")
    with open(f"{RES}/i2vs_heldout_per_video.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["method", "case"] + [f"{a}/{b}" for a, b in cols])
        for m in summary:
            for c in CASES:
                if c in out[m]:
                    w.writerow([m, c] + [f"{out[m][c][k]:.4f}" for k in cols])
    print("\n".join(lines))


if __name__ == "__main__":
    {"run": run, "report": report}[sys.argv[1]]()
