# Manga2Animate comparison — results (2026-10-27)

## Question
Given manga pages, can a general agent (Claude Opus 5.5) that plans everything itself match the
hand-designed Manga2Animate pipeline (arXiv 2610.26851) on their own benchmark, MangaEval?

## Setup
- **Cases**: the 4 stories of their 8-story evaluation set that come from Manga109-s
  (`dualjustice1`, `dualjustice2`, `kick`, `lovehina`). The source spreads were located in the local
  Manga109-s copy (`webtoon-sfx-research/data/coo`). Built by `scripts/build_cases.py` → `data/cases/`.
  - Panels: 6 target panels per case, cropped in the order of their final script. `dualjustice1` uses
    the panels shipped in their repo.
  - Character references: their refs are only released for `dualjustice1`. For the other cases each
    main character's ref is the largest Manga109 `body` box on the source pages.
  - **Every method is scored against the same panels and refs**, so numbers are comparable between rows
    but not exactly with the paper's table.
- **Methods**
  | row | planning | storyboard / keyframes | video |
  |---|---|---|---|
  | M2A(Gemini)+Seedance2, … | their pipeline (released outputs, Drive) | Gemini 3.1 image / FLUX.2 | Seedance 2.0 / MiniMax-H3 |
  | ViMax, StoryMem, AniMaker, Direct | their released baseline outputs | – | – |
  | **B: M2A-plan+Omni** | their pipeline, run by us (`src/video_models.py` + Omni backend, `patches/`) | Gemini 3.1 image | Gemini Omni 1.1 flash, first-frame, per panel |
  | **C: Opus-director+Omni** | Opus 5.5 subagent, free-form, brief in `docs/director_brief.md` | Gemini 3.1 image (≤12 calls) | Gemini Omni 1.1 flash, first-frame (≤12 calls) |
- **Metrics**: MangaEval video metrics (`scripts/eval_all.py`): auto_clip → 6 segments, I2VB/SC/BC/MS
  (their VBench++ code), DD (their modified RAFT DD), I2VS (DINOv3 ViT-B/16, same formula;
  `scripts/i2vs_dinov3.py` loads the HF port of the same checkpoint because the official .pth is gated),
  Shadow-v2 / Waifu-v3 (their `aesthetic/score.py`, 8 frames per video).
  For B and C the true shot boundaries are known, so they are also scored with **exact cuts**.

## Main table (mean of 4 cases, 1 run each) — `results/summary.md`
| Method | I2VS | I2VB | SC | BC | MS | DD | Shadow-v2 | Waifu-v3 |
|---|---|---|---|---|---|---|---|---|
| M2A(Gemini)+Seedance2 (paper's main) | 0.753 | 0.749 | 0.908 | 0.945 | 0.959 | 6.34 | 0.495 | **5.00** |
| M2A(Gemini)+MiniMax-H3 | 0.790 | **0.792** | 0.937 | 0.951 | 0.971 | 2.38 | 0.363 | 3.98 |
| M2A(FLUX.2)+Seedance2 | 0.748 | 0.727 | 0.874 | 0.939 | 0.945 | 10.91 | **0.626** | 4.52 |
| Direct+Seedance2 | 0.733 | 0.724 | 0.863 | 0.934 | 0.953 | **12.32** | 0.398 | 4.94 |
| ViMax+Seedance2 | 0.738 | 0.778 | 0.929 | 0.950 | 0.975 | 1.31 | 0.218 | 4.49 |
| ViMax+Veo3.1Fast | 0.751 | 0.784 | 0.871 | 0.934 | 0.971 | 1.48 | 0.183 | 4.58 |
| StoryMem | 0.743 | 0.766 | 0.942 | 0.958 | 0.971 | 3.36 | 0.308 | 3.37 |
| AniMaker | 0.742 | 0.728 | 0.901 | 0.940 | 0.978 | 1.41 | 0.345 | 4.12 |
| B: M2A-plan+Omni | 0.774 | 0.788 | 0.944 | 0.941 | 0.978 | 4.27 | 0.266 | 4.36 |
| B … [exact cuts] | 0.780 | 0.793 | 0.950 | 0.958 | 0.978 | 4.41 | 0.266 | 4.36 |
| **C: Opus-director+Omni** | **0.801** | 0.782 | 0.951 | 0.961 | 0.983 | 2.92 | 0.488 | 4.58 |
| C … [exact cuts] | 0.782 | 0.780 | **0.955** | **0.969** | **0.984** | 2.59 | 0.488 | 4.58 |

Per-case values: `results/per_video.csv`. Visual comparison (manga panel / M2A+Seedance / B / C, mid-frame
of each auto-cut segment): `results/sheets/<case>.jpg`.

## Findings
1. **Opus directing ≈ their best rows on manga alignment, better than their main setting.**
   C has the highest I2VS (0.801; 0.782 with exact cuts) and an I2VB of 0.78, tied with the top group
   (M2A+MiniMax 0.792, B 0.788–0.793) and clearly above the paper's main row M2A(Gemini)+Seedance2
   (0.753 / 0.749). C is also the most temporally stable (best SC/BC/MS).
2. **Planning matters for aesthetics: C vs. B use the same video model (Omni).** C's Shadow-v2 is 0.488 vs.
   0.266 for B, and Waifu-v3 is 4.58 vs. 4.36. C ties M2A+Seedance on Shadow-v2 (0.495), which is the
   paper's best Seedance row. B shows that putting Omni behind their planner alone raises alignment but costs aesthetics.
   C closes that gap. Our reading is that the self-review (Opus rejecting keyframes and clips that
   drifted, then retrying) is what C adds over B.
3. **C trades motion for faithfulness.** DD is 2.9 vs. 6.3 for M2A+Seedance and 12.3 for Direct. The director
   told Omni repeatedly to hold the camera and stay on the panel's composition; its notes say that this
   was its main fix for drift. DD rewards any motion, so it penalises this choice. Their table shows the same
   trade-off between alignment and DD (MiniMax rows).
4. **Cost.** C costs about US$6.0 per story (range 5.7–6.6) at list prices: Omni 720p at $0.10/s × 5 s clips ≈ $4.6,
   Gemini 3.1 Flash Image at 1K at $0.067 ≈ $0.6, and Opus 5.5 tokens ≈ $0.75 (from the opencode session records:
   $0.63–0.87). Wall-clock time was 7–13 min per story. The paper reports US$5.65 per story (Seedance $4.55) and 24m49s.
   Only about 3 of each 5 s Omni clip is used, so requesting shorter clips would cut about 30–40% of the video cost.

## Validity checks
- **Our MangaEval setup reproduces their ranking** (`results/paper_check.txt`). Over the 8 released methods,
  Spearman ρ between the paper's Table 1 (8 stories, their refs) and our re-scoring (4 stories, our refs)
  is: I2VS 0.76, I2VB 0.67, SC 0.62, MS 0.79, DD 0.79, Shadow-v2 0.93, Waifu-v3 0.81 (BC 0.19, all values
  within 0.93–0.96). Absolute I2VS is mostly lower than in the paper (by up to 0.04), consistent with our
  different character refs.
- **Segmentation noise.** auto_clip misses cuts sometimes. On C/kick it merged shots 1–2 and split shot
  2, and on dualjustice1 it misaligned M2A and B the same way (see sheets). Exact vs. auto cuts change C's
  I2VS by 0.02, which is the same size as the gaps between the top rows. **Differences below about 0.02 in
  I2VS/I2VB should not be trusted.**
- **Input asymmetries (disclosed).** (a) C was given `data/cases/<case>/characters/*.png` as generation
  input, and the main I2VS scores against those same files; on dualjustice2/kick/lovehina these are our
  crops, which M2A and B never saw (B reuses their released script and storyboard unchanged and only
  swaps the video model). On kick, girl1's ref is the same crop as panel 3. (b) C was given the 6 panels
  already selected and ordered (we cut them following their final script), so C is a
  "given panels -> video" result, not end to end.
- **Held-out-ref check for (a)** (`results/i2vs_heldout.md`, `scripts/build_heldout_refs.py`,
  `scripts/eval_heldout.py`). Every character got 3 new refs from other Manga109-s spreads of the same
  chapter (largest `body` annotations, input spreads excluded; 6 crops where the character was not clearly
  visible were swapped out on the sheet `results/heldout_refs.jpg` before any scoring). No method saw them.
  Same segments, formula and aggregation; score = mean over the 3 refs.

  | Method | I2VS input refs | I2VS held-out | drop | RefSim held-out |
  |---|---|---|---|---|
  | M2A(Gemini)+Seedance2 | 0.753 | 0.725 | −0.028 | 0.429 |
  | M2A(Gemini)+MiniMax-H3 | 0.790 | 0.754 | −0.036 | 0.452 |
  | B: M2A plan + Omni | 0.774 | 0.740 | −0.034 | 0.426 |
  | C: Opus director + Omni | **0.801** | **0.771** | −0.030 | 0.460 |
  | C [exact cuts] | 0.782 | 0.754 | −0.028 | 0.444 |

  RefSim = the ref term alone (max over frames of DINOv3 similarity; it is 40% of I2VS, the rest ignores
  the ref). Every method drops by about the same amount (held-out refs are different poses, and for
  dualjustice1 B/W instead of the colour art), and C does not drop more than the others, so the leak did not
  measurably inflate C. C stays #1 on held-out I2VS (auto cuts) and ties MiniMax-H3 with exact cuts; on
  RefSim alone it is #2 behind ViMax+Veo3.1Fast (0.471). Caveat: C's kick score benefits from auto_clip's
  mis-cut (RefSim 0.512 auto vs. 0.436 exact). Asymmetry (b) is not addressed by this check.

## Limitations
- n = 4 stories, 1 run per method, and no variance estimate. Generation is stochastic.
- Different refs and panels from the paper (theirs are not released), and the HF port of DINOv3 rather than the official .pth.
- C videos are 17.5–19.5 s (6 shots of 2.5–4 s) vs. 15 s for Seedance. Segment metrics are per-shot, so
  length mostly affects DD and the aesthetic frame sampling.
- Each director subagent started from a fresh context with only the brief: no paper, no other methods'
  outputs, and only `<RUN>/input/` as source material.
- Storyboard-level metrics (CSD/CIDS/PA/OCCM) and a user study are not done.

## Next steps
1. 2 more runs of C (and B) per case → mean ± std.
2. Add "C with Seedance 2.0" (Opus plans, Seedance renders one 15 s shot from a storyboard) to separate the
   planner effect from the video model on the paper's own video model.
3. A small user study (faithfulness, consistency, overall preference) on the 4 cases, because DD and the
   aesthetic scorers disagree with what C optimises.
4. Get the other 4 stories' panels and refs from the authors to evaluate on the full set.

## Reproduce
```
python3 scripts/build_cases.py
# B: runs/m2a_plan_omni (their pipeline with the Omni backend), C: subagent per case with docs/director_brief.md
python3 scripts/eval_all.py all   # envs: m2a-vbench (VBench++/DreamSim/RAFT), m2a-score (DINOv3/aesthetic)
```
Env notes: their vbench `setup.py` refuses CUDA 12.8 (RTX 5090), so we use `PYTHONPATH` instead of
installing it. peft 0.6.2 is needed for transformers 4.33.2; the cached DreamSim `adapter_config.json`
has six new, all-default fields that are removed for that peft version (original kept as
`adapter_config.orig.json`). `setuptools<81` is needed for `pkg_resources`.
