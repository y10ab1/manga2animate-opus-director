"""Locate the Manga109-s pages behind the project-page manga crops (SIFT + ratio test + RANSAC)."""
import glob, sys, cv2, numpy as np
M109 = "/home/yuehpo/coding/webtoon-sfx-research/data/coo/images"
PP = "third_party/Manga2Animate/project_page/static/images"
QUERIES = {"DualJustice": ["dualjustice1_manga_1", "dualjustice1_manga_2", "dualjustice2_manga_1",
                           "dualjustice2_manga_2", "dualjustice-kick_manga_1", "dualjustice-kick_manga_2"],
           "LoveHina_vol01": ["lovehina_manga", "lovehina_vol01_manga_1", "lovehina_vol01_manga_2"],
           "LoveHina_vol14": ["lovehina_manga"],
           "BurariTessenTorimonocho": ["burari_manga_1", "burari_manga_2"],
           "HarukaRefrain": ["hakura-refrain_manga_1", "hakura-refrain_manga_2"]}
sift = cv2.SIFT_create(4000)
bf = cv2.BFMatcher()


def feats(path, w=1000):
    im = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    s = w / max(im.shape)
    im = cv2.resize(im, None, fx=s, fy=s) if s < 1 else im
    return sift.detectAndCompute(im, None)


for book, qs in QUERIES.items():
    pages = sorted(glob.glob(f"{M109}/{book}/*.jpg"))
    pf = [feats(p) for p in pages]
    for q in qs:
        kq, dq = feats(f"{PP}/{q}.jpg")
        best = []
        for p, (kp, dp) in zip(pages, pf):
            if dp is None:
                continue
            m = [a for a, b in bf.knnMatch(dq, dp, k=2) if a.distance < 0.75 * b.distance]
            inl = 0
            if len(m) >= 8:
                src = np.float32([kq[a.queryIdx].pt for a in m]); dst = np.float32([kp[a.trainIdx].pt for a in m])
                H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
                inl = int(mask.sum()) if mask is not None else 0
            best.append((inl, p.split("/")[-1]))
        best.sort(reverse=True)
        print(book, q, best[:3], flush=True)
