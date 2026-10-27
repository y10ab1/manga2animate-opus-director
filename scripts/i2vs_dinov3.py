"""I2VS with DINOv3 ViT-B/16 (LVD-1689M), VBench++ formula — same as MangaEval's
tools/evaluate_i2v_subject_dinov3_official.py, but loading the HF port of the same checkpoint
(facebook/dinov3-vitb16-pretrain-lvd1689m) because the official .pth is gated.
Feature = CLS token after the final norm (= official `model(x)`), L2-normalised.
  score = 0.4*max(sim(frame, ref)) + 0.3*mean(sim(f_t, f_t+1)) + 0.3*min(sim(f_t, f_t+1))
Runs in env m2a-score.   python scripts/i2vs_dinov3.py manifest.json out.csv
"""
import csv, json, sys
import numpy as np
import torch, torch.nn.functional as F
from decord import VideoReader, cpu
from PIL import Image
from torchvision.transforms import Compose, InterpolationMode, Normalize, Resize, ToTensor
from transformers import AutoModel

dev = "cuda"
model = AutoModel.from_pretrained("facebook/dinov3-vitb16-pretrain-lvd1689m").eval().to(dev)
tf = Compose([Resize((256, 256), interpolation=InterpolationMode.BICUBIC), ToTensor(),
              Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])


@torch.inference_mode()
def embed(ims, bs=32):
    out = []
    for i in range(0, len(ims), bs):
        x = torch.stack([tf(im) for im in ims[i:i + bs]]).to(dev)
        out.append(F.normalize(model(pixel_values=x).pooler_output.float(), dim=-1).cpu())
    return torch.cat(out)


rows = json.load(open(sys.argv[1]))
cache, res = {}, []
for r in rows:
    if r.get("skip"):
        res.append({**r, "score": "", "status": "SKIP_" + r["skip"]}); continue
    v = r["video_path"]
    if v not in cache:
        vr = VideoReader(v, ctx=cpu(0), num_threads=1)
        fr = [Image.fromarray(f).convert("RGB") for f in vr.get_batch(range(len(vr))).asnumpy()]
        ff = embed(fr)
        cache[v] = (ff, (ff[:-1] * ff[1:]).sum(1).clamp(min=0).numpy())
    ff, cons = cache[v]
    ref = embed([Image.open(r["character_ref"]).convert("RGB")])
    conf = (ff @ ref.T).clamp(min=0).squeeze(1).numpy()
    s = 0.4 * conf.max() + 0.3 * cons.mean() + 0.3 * cons.min()
    res.append({**r, "score": float(s), "ref_max": float(conf.max()), "status": "SUCCESS"})
    print(r["method"], r["case"], r["segment"], r.get("character"), round(float(s), 4), flush=True)
with open(sys.argv[2], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=sorted({k for x in res for k in x}))
    w.writeheader(); w.writerows(res)
