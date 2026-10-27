"""SIFT + homography helpers for locating one image inside another."""
import cv2, numpy as np
sift = cv2.SIFT_create(6000)
bf = cv2.BFMatcher()


def _gray(x):
    if isinstance(x, str):
        return cv2.imread(x, cv2.IMREAD_GRAYSCALE)
    return cv2.cvtColor(np.asarray(x.convert("RGB")), cv2.COLOR_RGB2GRAY)


def locate(query, target):
    """Bounding box of `query` inside `target` (paths or PIL images) and the RANSAC inlier count."""
    q, p = _gray(query), _gray(target)
    kq, dq = sift.detectAndCompute(q, None); kp, dp = sift.detectAndCompute(p, None)
    if dq is None or dp is None or len(dp) < 2:
        return None, 0
    m = [a for a, b in bf.knnMatch(dq, dp, k=2) if a.distance < 0.75 * b.distance]
    if len(m) < 8:
        return None, 0
    src = np.float32([kq[a.queryIdx].pt for a in m]); dst = np.float32([kp[a.trainIdx].pt for a in m])
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        return None, 0
    h, w = q.shape
    c = cv2.perspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]])[None], H)[0]
    return [int(c[:, 0].min()), int(c[:, 1].min()), int(c[:, 0].max()), int(c[:, 1].max())], int(mask.sum())
