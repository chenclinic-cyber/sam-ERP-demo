#!/usr/bin/env python3
"""Selective pink->gold recolor for the fur jacket. Vectorized HSV in numpy."""
import numpy as np

def rgb_to_hsv(rgb):
    rgb = rgb.astype(np.float32) / 255.0
    mx = rgb.max(-1); mn = rgb.min(-1)
    diff = mx - mn + 1e-9
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    m = mx == r; h[m] = ((g - b)[m] / diff[m]) % 6
    m = mx == g; h[m] = (b - r)[m] / diff[m] + 2
    m = mx == b; h[m] = (r - g)[m] / diff[m] + 4
    h *= 60.0
    s = np.where(mx > 0, diff / (mx + 1e-9), 0)
    return h, s, mx

def hsv_to_rgb(h, s, v):
    h = (h % 360.0) / 60.0
    i = np.floor(h).astype(np.int32) % 6
    f = h - np.floor(h)
    p = v * (1 - s); q = v * (1 - f * s); t = v * (1 - (1 - f) * s)
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return (np.stack([r, g, b], -1) * 255.0).clip(0, 255).astype(np.uint8)

def pink_mask(h, s, v):
    """Soft mask of dusty-pink fur pixels."""
    # pink/magenta hues wrap around 300..360 plus a bit past 0
    hue_d = np.minimum(np.abs(((h - 335.0 + 180) % 360) - 180), 90)
    m_h = np.clip(1.0 - (hue_d - 25.0) / 15.0, 0, 1)   # full<=25deg, off>=40deg
    m_s = np.clip((s - 0.04) / 0.06, 0, 1) * np.clip((0.55 - s) / 0.12, 0, 1)
    m_v = np.clip((v - 0.25) / 0.15, 0, 1)
    return m_h * m_s * m_v

def recolor(rgb, blur=None):
    h, s, v = rgb_to_hsv(rgb)
    m = pink_mask(h, s, v)
    if blur is not None:
        m = blur(m)
    # target: warm gold ~42deg, boost saturation a touch, keep value texture
    h2 = np.full_like(h, 42.0)
    s2 = np.clip(s * 2.2 + 0.16, 0, 0.88)
    v2 = np.clip(v * 0.99, 0, 1)
    gold = hsv_to_rgb(h2, s2, v2).astype(np.float32)
    out = rgb.astype(np.float32) * (1 - m[..., None]) + gold * m[..., None]
    return out.clip(0, 255).astype(np.uint8), m

if __name__ == "__main__":
    import sys
    from PIL import Image, ImageFilter
    img = Image.open(sys.argv[1]).convert("RGB")
    a = np.array(img)
    def blur(m):
        mi = Image.fromarray((m * 255).astype(np.uint8))
        return np.array(mi.filter(ImageFilter.GaussianBlur(2))) / 255.0
    out, m = recolor(a, blur)
    Image.fromarray(out).save(sys.argv[2])
    Image.fromarray((m * 255).astype(np.uint8)).save(sys.argv[2] + ".mask.png")
