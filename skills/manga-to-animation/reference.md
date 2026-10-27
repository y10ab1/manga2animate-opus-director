# Reference: evidence, examples, evaluation

## Where this workflow comes from
An experiment on the 4 Manga109-s stories of the Manga2Animate test set (dualjustice1, dualjustice2, kick,
lovehina), with every method scored by the same local MangaEval setup.
Report: https://github.com/y10ab1/manga2animate-opus-director/blob/main/docs/report.md
Project page: https://y10ab1.github.io/manga2animate-opus-director/

| method | I2VS | I2VB | SC | BC | MS | DD | Shadow-v2 | Waifu-v3 |
|---|---|---|---|---|---|---|---|---|
| Manga2Animate (Gemini + Seedance 2.0) | 0.753 | 0.749 | 0.908 | 0.945 | 0.959 | 6.34 | 0.495 | 5.00 |
| Manga2Animate plan + Omni | 0.774 | 0.788 | 0.944 | 0.941 | 0.978 | 4.27 | 0.266 | 4.36 |
| **this skill (Opus director + Omni)** | **0.801** | 0.782 | **0.951** | **0.961** | **0.983** | 2.92 | 0.488 | 4.58 |

How to read this:
- The director is best on character match and temporal consistency.
- Holding the planner's video model fixed (Omni), its aesthetics are much better than Manga2Animate's planner.
- Motion is lower, because of the anti-drift prompting.
- 4 stories with 1 run each; differences under ≈0.02 in I2VS/I2VB are within segmentation noise.

## What replaces the Manga2Animate stages
| Manga2Animate | this skill |
|---|---|
| MAGI panels + order, OCR | the director reads the pages; `crop` cuts the panels |
| Character Description Creator | colour design in notes; optional model sheet |
| 3 scripts × 2 rounds + clip-wise reviewer | one careful script pass |
| 3 storyboard grids × 2 rounds + pairwise reviewer | one keyframe per shot; retry only on failure |
| 2 videos always + video reviewer | one clip per shot; frame-sheet review; retry only on failure |
| (none) | reference chaining, reference cleaning, temporal trimming, anti-drift prompts |

Typical usage per story: 8–11 image calls and 9–10 clip calls (about 1 keyframe retry and 1.5 clip retries per
3 shots). Opus tokens ≈ $0.6–0.9.

## Worked fixes from the runs
- **kick, shot 1**: the cylinder was drawn huge; in the panel it is small in an empty sky. The retry asked for small
  and spinning and used the shot-2 keyframe as the object reference.
- **kick, shot 5**: the keyframe showed the whole man, while the panel is a worm's-eye close-up of the shoe sole.
  The retry said "only the leg and shoe are visible", and the cylinder was chained from shot 2.
- **kick, shot 6 clip**: the man landed and knelt by 2 s. The retry asked for slow motion and "does not land".
- **dualjustice1, shot 6**: the panel crop included the line between two panels, drawn as a black bar, and the arm
  pointed at the wrong target. Fixed in 2 retries; the last one was an edit of the previous image.
- **dualjustice1, dragon**: there was only a B/W reference. Colours were fixed once (green scales, tan mane), and the
  first accepted dragon keyframe was chained into every later shot.
- **dualjustice2**: "バチバチ" lettering was copied into monster keyframes. Lettering was whited out in the panel refs.
- **lovehina**: 1 colour model sheet for both characters, used as a reference in every keyframe.

## Scoring with MangaEval (optional)
The scoring driver is `scripts/eval_all.py` in the experiment repo. It cuts the video at the true shot boundaries
from `final.mp4.segments.json` or with their auto_clip, then computes:
- I2VB, SC, BC, MS with their VBench++ code
- DD with their RAFT-based modified DD
- I2VS with DINOv3 ViT-B/16
- Shadow-v2 and Waifu-v3
Environment notes (CUDA 12.8, peft and DreamSim patch) are at the end of the report.
Score against the same panel crops and character refs for every method you compare.

## Licensing
Manga109 / Manga109-s images are for research. When you show results, credit as "© <author>, from Manga109-s",
keep whole pages under 20% of the volume, and never redistribute the dataset.
