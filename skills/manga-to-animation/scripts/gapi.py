"""Tiny Gemini REST helpers shared by the generator scripts (stdlib only)."""
import base64, json, mimetypes, os, sys, time, urllib.error, urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta"


def key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        sys.exit("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")
    return k


def b64file(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def mime(path):
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _post(url, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key()})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def post(url, body, timeout=900, retries=3):
    """POST with retries; returns parsed JSON or raises RuntimeError with the server message."""
    err = ""
    for i in range(retries):
        try:
            return _post(url, body, timeout)
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read().decode()[:500]}"
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # timeouts, resets
            err = str(e)
        time.sleep(5 * (i + 1))
    raise RuntimeError(err)


def interaction(body, timeout=900):
    """Interactions API (Omni video, Lyria music, 3.8 TTS)."""
    return post(f"{BASE}/interactions", body, timeout)


def generate(model, parts, config=None, timeout=300):
    body = {"contents": [{"parts": parts}]}
    if config:
        body["generationConfig"] = config
    return post(f"{BASE}/models/{model}:generateContent", body, timeout)


def outputs(d, kind):
    """All content blocks of type `kind` (video/audio/text) from model_output steps."""
    return [c for s in d.get("steps", []) if s.get("type") == "model_output"
            for c in s.get("content", []) if c.get("type") == kind]


def fetch_uri(uri, retries=120):
    uri += ("&" if "?" in uri else "?") + f"key={key()}"
    for _ in range(retries):
        try:
            return urllib.request.urlopen(uri, timeout=300).read()
        except Exception:
            time.sleep(5)
    raise RuntimeError("download failed: " + uri)


def load_spec(path):
    return json.load(open(path, encoding="utf-8"))
