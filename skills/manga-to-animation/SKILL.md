---
name: manga-to-animation
description: Turns manga or comic pages into a short multi-shot anime video that stays faithful to the source (characters, art style, plot, panel composition). Claude acts as the sole director, reading the pages, writing the script, generating keyframes with Gemini image and shots with Gemini Omni, then reviewing and retrying its own outputs. Use when the user wants to animate manga pages, comic panels or a webtoon strip, adapt a manga scene into anime, or reproduce or compare against Manga2Animate.
---

# Manga to Animation (single-agent director)

You are the director. There is no separate planner or reviewer model: you read the manga, plan, prompt
the generators, look at every output, and retry only what fails. On the 4 Manga109-s stories of the
Manga2Animate test set, this beat that paper's main setting on manga alignment and temporal consistency
in MangaEval, at about the same cost (≈US$6 and ≈10 min per 6-shot story).

## Requirements
- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) with access to `gemini-3.1-flash-image` and `gemini-omni-1.1-flash`
- `ffmpeg`, `ffprobe`, Python 3 with Pillow
- Optional: `FAL_API_KEY` for the Seedance 2.0 `video` command (one 15 s multi-shot video from a storyboard)

The tools live in `scripts/manga_tools.py` (next to this file). Call it with its absolute path. Use `T` below
as shorthand for `python3 <skill_dir>/scripts/manga_tools.py`.

| command | cost | purpose |
|---|---|---|
| `T crop --src page.png --out x.png --box x0,y0,x1,y1 [--whiteout x0,y0,x1,y1 ...]` | free | cut panels and character refs; paint out lettering |
| `T image --run R --out R/kf/k1.png --prompt-file p.txt --ref a.png --ref b.png [--aspect 16:9]` | ≈$0.07 | keyframe, model sheet, or edit of a previous image |
| `T clip --run R --out R/clips/c1a.mp4 --prompt-file p.txt --first kf.png [--last kf2.png]` | ≈$0.50 (5 s, 720p) | Omni image-to-video, the keyframe is frame 0 |
| `T frames --video c.mp4 --out R/frames/c1a --fps 4` | free | frame contact sheet `sheet.jpg` to review a clip |
| `T assemble --out R/final.mp4 --shot clip:start:dur ...` | free | hard-cut concat, 1280x720 24 fps, writes `final.mp4.segments.json` |
| `T budget --run R` | free | calls used out of the budget |

Every call is logged to `R/calls.jsonl`. The default budget is 12 image and 12 clip calls per story (override with
`MANGA_BUDGET_IMAGE`, `MANGA_BUDGET_CLIP`). Failed calls are not counted. Write prompts to files under `R/prompts/`.

## Workflow

```
- [ ] 1. Set up R/ and read the pages
- [ ] 2. Choose and crop the target panels; collect character refs
- [ ] 3. Fix designs and write the shot script (R/notes.md)
- [ ] 4. Keyframes: generate, review, retry
- [ ] 5. Clips: generate, review, retry, pick windows
- [ ] 6. Assemble, check the final, finish notes
```

### 1. Set up and read
Create `R/` with `input/pages/`, `input/panels/`, `input/characters/`, `kf/`, `clips/`, `prompts/`, `frames/`.
Copy the pages in. Look at every page yourself. Japanese manga reads right-to-left and top-to-bottom, both
between panels and within speech balloons. Read the dialogue and SFX directly and translate them in your notes;
no OCR step is needed. Work out who is who, what happens and what each SFX means.

### 2. Panels and references
- If the user gave panels, keep their order. Otherwise pick about 6 panels that tell the beat (default 6 shots),
  measure the boxes on the page image and run `T crop`. Shot *i* will depict panel *i*.
- Crop each main character's clearest appearance into `input/characters/<name>.png` if no refs were given.
- **Clean references**: if a panel crop carries SFX lettering, speech-balloon text or a neighbouring panel's border,
  crop tighter or use `--whiteout` on a copy. The image model copies lettering and draws borders as black bars.

### 3. Designs and script
Write these into `R/notes.md` before generating anything:
- **Colour design** for every character and recurring object. Refs are usually black and white, so decide hair,
  eyes, outfit and object colours once and reuse the exact wording in every prompt.
- When there are 2 or more characters or the refs are poor, spend 1 image call on a **colour model sheet** (all
  characters, full body and face, no text) and use it as a reference for every keyframe.
- **Shot script** as a table: shot / panel / what happens / dialogue and SFX (audio only) / camera.
  Keep each shot inside its panel's moment; do not invent events between panels.

### 4. Keyframes (one per shot, 16:9)
References, in order: panel *i*, then the character refs or model sheet, then any **accepted earlier keyframe**
that shows a recurring object or creature (reference chaining; this is what keeps designs stable). Template:

```
[Image 1] is a manga panel to recreate as a colored anime keyframe, keeping its composition
(ignore speech bubbles: no text at all). [Image 2] is <name>'s design (<colour design>). [Image 3] shows the
exact <object> design; keep that shape. Clean modern TV-anime style, crisp black lineart matching the manga's
linework, cel shading, <palette>. Absolutely NO text, NO letters, NO sound-effect lettering, NO speech bubbles,
NO panel borders, NO captions. Full-bleed 16:9 single frame.
Shot: <camera and framing from the panel>, <who is where, pose, expression>, <background>.
```

Review each keyframe next to its panel before using it:
- composition and camera match the panel (scale of objects, who is in frame, angle)
- identities and colours match the design; no extra characters or duplicated props
- no text, lettering, borders or bars
On failure, retry with the specific fix written into the prompt ("the object is a cylinder, not a sphere",
"only the leg and shoe are visible"), or pass the failed image as a reference and ask for an edit.

### 5. Clips (Omni, first-frame)
Ask for about 4–5 s and plan to keep only 2.5–4 s. Template:

```
2D cel-shaded TV anime, keep the exact art style, character designs and colors of the first frame.
No text, no subtitles, no captions, no speech bubbles appear at any time. <N>-second shot, composition held
like the first frame, <camera: locked / slow push-in>. <one continuous action from the panel>.
<sound / spoken line in quotes>. <explicit stop condition, e.g. "he does not land during the shot">.
```

Run `T frames --fps 4` and look at `sheet.jpg` for every clip. Known Omni failure modes:
- **drift**: the framing jumps, or the camera zooms until the subject leaves the frame
- **redesign**: a creature or object changes shape, colour or species mid-shot
- **over-acting**: the action continues past the panel (lands, kneels, object hits the girl)
- **lighting and expression changes** on faces
- action too small (the object barely moves)

When a clip fails, retry with a constraint that names the failure ("camera locked off", "keeps its exact
design", "stays in frame", "does not land"). Otherwise choose the window that starts on the panel's moment and
ends before the drift. Do not spend a retry on a clip that already has a good 2.5 s window.

### 6. Assemble and finish
`T assemble --out R/final.mp4 --shot R/clips/c1b.mp4:0:3 --shot ...` in panel order, hard cuts only.
Run `T frames --video R/final.mp4 --fps 2` and check: 6 shots in order, no text anywhere, the same
designs across shots. Finish `notes.md` with the picks (clip, start, dur), what was rejected and why, and the
budget used. Report the final path, the shot table and the cost (`calls.jsonl`) to the user.

## Defaults and adjustments
- 6 shots, 2.5–4 s each, 1280x720. Hard cuts matter if the video will be scored per panel (MangaEval).
- For a stylised version (bubbles, SFX lettering, colour grading), make the clean version first and add the
  effects in post. Do not ask the generators for text.
- With `FAL_API_KEY` you can instead compose a 3×2 storyboard from the accepted keyframes and run `T video --ref
  storyboard.png` (Seedance 2.0, one 15 s multi-shot video, ≈$4.5), which is Manga2Animate's main setting.

For evidence, worked examples and evaluation, see [reference.md](reference.md).
