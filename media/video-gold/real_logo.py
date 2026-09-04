#!/usr/bin/env python3
"""Extract the real Dream-U logo from the screenshot, remove the white
background, and recolor everything to radiant gold with a specular sheen."""
import numpy as np
from PIL import Image, ImageFilter

SRC = "/root/.claude/uploads/b62246aa-84da-5240-b4e2-fc56dfb16a1e/3cbf78be-image.png"

img = Image.open(SRC).convert("RGB")
a = np.array(img)

# find the white logo band: rows whose mean brightness is high
rowmean = a.mean(axis=(1, 2))
band = np.where(rowmean > 200)[0]
top, bot = band[0], band[-1]
crop = a[top:bot + 1]

# alpha = distance from white (un-matte): 1 - min(r,g,b)
mn = crop.min(axis=2).astype(np.float32) / 255.0
alpha = np.clip((1.0 - mn) * 1.15, 0, 1)
alpha[alpha < 0.04] = 0

# trim to content bbox with margin
ys, xs = np.where(alpha > 0.1)
m = 14
y0, y1 = max(ys.min() - m, 0), min(ys.max() + m, alpha.shape[0])
x0, x1 = max(xs.min() - m, 0), min(xs.max() + m, alpha.shape[1])
alpha = alpha[y0:y1, x0:x1]
h, w = alpha.shape
print("logo content size:", w, h)

# radiant gold fill: vertical gradient + diagonal specular highlight
STOPS = [(0.00, (255, 244, 195)),
         (0.30, (244, 208, 112)),
         (0.55, (218, 165, 32)),
         (0.78, (184, 134, 20)),
         (1.00, (240, 202, 105))]
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
t = yy / max(h - 1, 1)
rgb = np.zeros((h, w, 3), np.float32)
for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
    seg = (t >= t0) & (t <= t1)
    f = np.zeros_like(t)
    f[seg] = (t[seg] - t0) / (t1 - t0)
    for k in range(3):
        rgb[..., k][seg] = c0[k] + (c1[k] - c0[k]) * f[seg]
# diagonal sheen band (金光)
sheen = np.exp(-(((xx / w + yy / h) - 0.85) / 0.18) ** 2)
rgb = np.clip(rgb + sheen[..., None] * np.array([70, 60, 30]), 0, 255)

out = np.dstack([rgb, alpha[..., None] * 255]).astype(np.uint8)
logo = Image.fromarray(out, "RGBA")

# faint dark under-edge so it stays readable on light footage
edge = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
edge = edge.filter(ImageFilter.GaussianBlur(2))
under = np.zeros((h, w, 4), np.uint8)
under[..., :3] = (58, 40, 6)
under[..., 3] = (np.array(edge, np.float32) * 0.55).astype(np.uint8)
final = Image.fromarray(under, "RGBA")
final.alpha_composite(logo)

final.save("real_logo_gold.png")
for name, bg in [("real_on_dark.png", (28, 28, 32)), ("real_on_light.png", (236, 233, 228))]:
    c = Image.new("RGB", final.size, bg)
    c.paste(final, (0, 0), final)
    c.resize((600, int(final.height * 600 / final.width))).save(name)
print("saved real_logo_gold.png", final.size)
