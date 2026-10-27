"""Download the Manga2Animate evaluation data (Drive folder) file by file.
Uses the drive.usercontent endpoint, which works when gdown hits the quota page."""
import json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = "data/m2a_eval"
files = json.load(open(f"{ROOT}/files.json"))
only = sys.argv[1:]


def get(item):
    fid, path = item
    if only and not any(path.startswith(o) for o in only):
        return
    out = os.path.join(ROOT, path)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
    data = urllib.request.urlopen(url, timeout=600).read()
    if data[:15].lower().startswith(b"<!doctype html"):
        print("FAILED (html)", path)
        return
    open(out, "wb").write(data)
    print("ok", path, len(data))


with ThreadPoolExecutor(6) as ex:
    list(ex.map(get, files))
