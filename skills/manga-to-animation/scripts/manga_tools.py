"""Tools for the manga-to-animation skill.  Every generation call is appended to
<run>/calls.jsonl (tool, model, inputs, output, seconds) for cost reporting.

  python manga_tools.py crop   --src page.png --out R/input/panels/panel1.png --box x0,y0,x1,y1 [--whiteout x0,y0,x1,y1 ...]
                                   (free; boxes in source pixels; whiteout paints white over lettering)
  python manga_tools.py image  --run R --out R/x.png --prompt-file p.txt [--ref a.png ...] [--aspect 16:9]
  python manga_tools.py video  --run R --out R/v.mp4 --prompt-file p.txt --ref sb.png [--ref c.png ...]
                                   [--duration 15] [--seed 1]
  python manga_tools.py clip   --run R --out R/c.mp4 --prompt-file p.txt --first kf.png [--last kf2.png]
                                   (Gemini Omni image->video, first-frame mode; ~4-8 s, has audio)
  python manga_tools.py assemble --out R/final.mp4 --shot c1.mp4:0:2.5 --shot c2.mp4:0.5:3 ...
                                   (hard-cut concat, 1280x720 24 fps; writes final.mp4.segments.json)
  python manga_tools.py frames --video v.mp4 --out R/frames_v [--fps 2]     (+ contact sheet, free)
  python manga_tools.py budget --run R                                      (calls used so far)

Models: image gemini-3.1-flash-image (= Manga2Animate's storyboard model); clip gemini-omni-1.1-flash;
  video Seedance 2.0 reference-to-video via fal.ai (= their main video model; needs fal balance).
"""
import argparse, base64, json, mimetypes, os, subprocess, sys, time, urllib.error, urllib.request

IMAGE_MODEL = "gemini-3.1-flash-image"
VIDEO_ENDPOINT = "bytedance/seedance-2.0/reference-to-video"
CLIP_MODEL = "gemini-omni-1.1-flash"
# per story; override with MANGA_BUDGET_IMAGE / MANGA_BUDGET_CLIP / MANGA_BUDGET_VIDEO
BUDGET = {"image": int(os.environ.get("MANGA_BUDGET_IMAGE", 12)), "video": int(os.environ.get("MANGA_BUDGET_VIDEO", 2)),
          "clip": int(os.environ.get("MANGA_BUDGET_CLIP", 12))}


def log(run, rec):
    rec = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%S"), **rec)
    with open(os.path.join(run, "calls.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def used(run):
    p = os.path.join(run, "calls.jsonl")
    n = {k: 0 for k in BUDGET}
    if os.path.exists(p):
        for line in open(p):
            r = json.loads(line)
            if r.get("ok"):
                n[r["tool"]] = n.get(r["tool"], 0) + 1
    return n


def check_budget(run, tool):
    n = used(run)
    if n[tool] >= BUDGET[tool]:
        sys.exit(f"budget exhausted: {tool} {n[tool]}/{BUDGET[tool]}")


def post(url, body, headers, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def data_uri(path):
    return f"data:{mimetypes.guess_type(path)[0] or 'image/png'};base64," + base64.b64encode(open(path, "rb").read()).decode()


def cmd_image(a):
    check_budget(a.run, "image")
    prompt = open(a.prompt_file).read()
    parts = []
    for i, r in enumerate(a.ref or [], 1):
        parts += [{"text": f"[Image {i}] ({os.path.basename(r)}):"},
                  {"inlineData": {"mimeType": mimetypes.guess_type(r)[0] or "image/png",
                                  "data": base64.b64encode(open(r, "rb").read()).decode()}}]
    parts.append({"text": prompt})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"], "imageConfig": {"aspectRatio": a.aspect}}}
    key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
    t0, ok, err = time.time(), False, ""
    for attempt in range(3):
        try:
            d = post(f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGE_MODEL}:generateContent",
                     body, {"x-goog-api-key": key}, 300)
            imgs = [p["inlineData"]["data"] for c in d.get("candidates", []) for p in c.get("content", {}).get("parts", [])
                    if "inlineData" in p]
            if imgs:
                os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
                open(a.out, "wb").write(base64.b64decode(imgs[-1]))
                ok = True
                break
            err = json.dumps(d)[:400]
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read().decode()[:400]}"
        except Exception as e:
            err = str(e)
        time.sleep(5)
    log(a.run, dict(tool="image", model=IMAGE_MODEL, ok=ok, out=a.out, refs=a.ref, prompt_file=a.prompt_file,
                    seconds=round(time.time() - t0, 1), error=err if not ok else ""))
    print("saved " + a.out if ok else "FAILED: " + err)


def cmd_video(a):
    check_budget(a.run, "video")
    prompt = open(a.prompt_file).read()
    body = {"prompt": prompt, "image_urls": [data_uri(r) for r in a.ref], "resolution": "720p",
            "aspect_ratio": "16:9", "duration": str(a.duration), "generate_audio": True}
    if a.seed is not None:
        body["seed"] = a.seed
    hdr = {"Authorization": f"Key {os.environ['FAL_API_KEY']}"}
    t0, ok, err, req_id = time.time(), False, "", None
    try:
        sub = post(f"https://queue.fal.run/{VIDEO_ENDPOINT}", body, hdr, 300)
        req_id = sub["request_id"]
        status_url = sub.get("status_url") or f"https://queue.fal.run/{VIDEO_ENDPOINT}/requests/{req_id}/status"
        result_url = sub.get("response_url") or f"https://queue.fal.run/{VIDEO_ENDPOINT}/requests/{req_id}"
        while time.time() - t0 < 1800:
            s = json.load(urllib.request.urlopen(urllib.request.Request(status_url, headers=hdr), timeout=60))
            if s.get("status") == "COMPLETED":
                break
            time.sleep(10)
        res = json.load(urllib.request.urlopen(urllib.request.Request(result_url, headers=hdr), timeout=120))
        url = res["video"]["url"]
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        open(a.out, "wb").write(urllib.request.urlopen(url, timeout=600).read())
        ok = True
    except urllib.error.HTTPError as e:
        err = f"HTTP {e.code}: {e.read().decode()[:600]}"
    except Exception as e:
        err = repr(e)
    log(a.run, dict(tool="video", model=VIDEO_ENDPOINT, ok=ok, out=a.out, refs=a.ref, prompt_file=a.prompt_file,
                    duration=a.duration, request_id=req_id, seconds=round(time.time() - t0, 1), error=err if not ok else ""))
    print("saved " + a.out if ok else "FAILED: " + err)


def cmd_clip(a):
    """Gemini Omni image->video (first-frame mode; optional last frame)."""
    check_budget(a.run, "clip")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gapi
    prompt = open(a.prompt_file).read()
    inp = [{"type": "image", "data": gapi.b64file(p), "mime_type": gapi.mime(p)} for p in [a.first] + ([a.last] if a.last else [])]
    inp.append({"type": "text", "text": prompt})
    body = {"model": CLIP_MODEL, "input": inp,
            "response_format": {"type": "video", "aspect_ratio": "16:9", "resolution": "720p", "delivery": "uri"}}
    t0, ok, err = time.time(), False, ""
    for attempt in range(2):
        try:
            d = gapi.interaction(body)
            vids = gapi.outputs(d, "video")
            if vids:
                v = vids[-1]
                os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
                open(a.out, "wb").write(base64.b64decode(v["data"]) if v.get("data") else gapi.fetch_uri(v["uri"]))
                ok = True
                break
            err = json.dumps(d)[:400]
        except Exception as e:
            err = str(e)[:400]
    log(a.run, dict(tool="clip", model=CLIP_MODEL, ok=ok, out=a.out, first=a.first, last=a.last,
                    prompt_file=a.prompt_file, seconds=round(time.time() - t0, 1), error=err if not ok else ""))
    print("saved " + a.out if ok else "FAILED: " + err)


def cmd_assemble(a):
    """Concatenate shots with hard cuts: --shot clip.mp4:start:dur (repeatable, in order).
    Writes <out> (1280x720, 24 fps, H.264, audio kept) and <out>.segments.json (exact shot boundaries)."""
    tmp = a.out + ".parts"
    os.makedirs(tmp, exist_ok=True)
    parts, segs, t = [], [], 0.0
    for i, s in enumerate(a.shot, 1):
        path, start, dur = s.rsplit(":", 2)
        p = os.path.join(tmp, f"s{i:02d}.mp4")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", start, "-t", dur, "-i", path,
                        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=24,setsar=1",
                        "-af", "aresample=44100", "-ac", "2", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", p], check=True)
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                 capture_output=True, text=True).stdout)
        parts.append(p); segs.append(dict(shot=i, start=round(t, 3), end=round(t + d, 3), source=path)); t += d
    lst = os.path.join(tmp, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", a.out], check=True)
    json.dump(segs, open(a.out + ".segments.json", "w"), indent=1)
    print(f"{a.out}: {t:.2f}s, {len(segs)} shots")


def cmd_crop(a):
    from PIL import Image, ImageDraw
    box = lambda s: tuple(int(float(v)) for v in s.split(","))
    im = Image.open(a.src).convert("RGB")
    d = ImageDraw.Draw(im)
    for w in a.whiteout or []:
        d.rectangle(box(w), fill="white")
    out = im.crop(box(a.box)) if a.box else im
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    out.save(a.out)
    print(f"saved {a.out} {out.size[0]}x{out.size[1]} (source {im.size[0]}x{im.size[1]})")


def cmd_frames(a):
    os.makedirs(a.out, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.video, "-vf", f"fps={a.fps},scale=480:-2",
                    os.path.join(a.out, "f_%03d.jpg")], check=True)
    from PIL import Image, ImageDraw
    fs = sorted(f for f in os.listdir(a.out) if f.startswith("f_"))
    ims = [Image.open(os.path.join(a.out, f)) for f in fs]
    w, h, cols = ims[0].width // 2, ims[0].height // 2, 6
    sheet = Image.new("RGB", (cols * w, ((len(ims) + cols - 1) // cols) * (h + 14)), "white")
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * (h + 14)
        sheet.paste(im.resize((w, h)), (x, y + 14)); d.text((x + 2, y + 1), f"{i / a.fps:.1f}s", fill="black")
    sheet.save(os.path.join(a.out, "sheet.jpg"), quality=85)
    print(f"{len(ims)} frames, sheet: {os.path.join(a.out, 'sheet.jpg')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("image"); p.add_argument("--run", required=True); p.add_argument("--out", required=True)
    p.add_argument("--prompt-file", required=True); p.add_argument("--ref", action="append"); p.add_argument("--aspect", default="16:9")
    p = sp.add_parser("video"); p.add_argument("--run", required=True); p.add_argument("--out", required=True)
    p.add_argument("--prompt-file", required=True); p.add_argument("--ref", action="append", required=True)
    p.add_argument("--duration", type=int, default=15); p.add_argument("--seed", type=int)
    p = sp.add_parser("clip"); p.add_argument("--run", required=True); p.add_argument("--out", required=True)
    p.add_argument("--prompt-file", required=True); p.add_argument("--first", required=True); p.add_argument("--last")
    p = sp.add_parser("assemble"); p.add_argument("--out", required=True); p.add_argument("--shot", action="append", required=True)
    p = sp.add_parser("frames"); p.add_argument("--video", required=True); p.add_argument("--out", required=True)
    p.add_argument("--fps", type=float, default=2)
    p = sp.add_parser("budget"); p.add_argument("--run", required=True)
    p = sp.add_parser("crop"); p.add_argument("--src", required=True); p.add_argument("--out", required=True)
    p.add_argument("--box"); p.add_argument("--whiteout", action="append")
    a = ap.parse_args()
    if a.cmd == "budget":
        print(used(a.run), "of", BUDGET)
    else:
        {"image": cmd_image, "video": cmd_video, "clip": cmd_clip, "assemble": cmd_assemble, "frames": cmd_frames,
         "crop": cmd_crop}[a.cmd](a)
