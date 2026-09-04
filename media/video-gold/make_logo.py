#!/usr/bin/env python3
"""Draw a gold, transparent-background 靚優診所 logo (mark + text)."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

# gold gradient stops (top -> bottom)
STOPS = [(0.00, (255, 241, 186)),
         (0.35, (240, 205, 110)),
         (0.55, (212, 160, 23)),
         (0.75, (176, 124, 16)),
         (1.00, (232, 190, 90))]

def gold_gradient(h):
    grad = np.zeros((h, 3), dtype=np.float32)
    for i in range(h):
        t = i / max(h - 1, 1)
        for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                grad[i] = [c0[k] + (c1[k] - c0[k]) * f for k in range(3)]
                break
    return grad

def apply_gold(alpha_img):
    """alpha_img: L-mode mask -> RGBA gold-filled image with dark edge."""
    w, h = alpha_img.size
    a = np.array(alpha_img, dtype=np.float32) / 255.0
    # find vertical extent of the glyphs for the gradient span
    rows = np.where(a.max(axis=1) > 0.05)[0]
    top, bot = (rows[0], rows[-1]) if len(rows) else (0, h - 1)
    grad = gold_gradient(bot - top + 1)
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    rgb[top:bot + 1] = grad[:, None, :]
    out = np.dstack([rgb, a[..., None] * 255.0]).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    # dark outline underneath for legibility on light backgrounds
    edge = alpha_img.filter(ImageFilter.MaxFilter(5))
    edge_np = np.array(edge, dtype=np.float32) / 255.0
    dark = np.zeros((h, w, 4), dtype=np.uint8)
    dark[..., 0:3] = (60, 42, 8)
    dark[..., 3] = (edge_np * 255).astype(np.uint8)
    base = Image.fromarray(dark, "RGBA").filter(ImageFilter.GaussianBlur(1.2))
    base.alpha_composite(img)
    return base

def make_logo(scale=4):
    # canvas at high res then downsample
    W, H = 1376 * scale // 4, 344 * scale // 4
    s = scale / 4.0
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)

    # --- circular swirl mark ---
    cx, cy, r = int(150 * s), int(172 * s), int(118 * s)
    lw = int(14 * s)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=255, width=lw)
    # two diagonal swooshes clipped to the circle interior (like the original mark)
    sw = Image.new("L", (W, H), 0)
    dsw = ImageDraw.Draw(sw)
    for off in (-int(30 * s), int(12 * s)):
        dsw.arc([cx - int(220 * s) + off, cy - int(60 * s),
                 cx + int(150 * s) + off, cy + int(320 * s)],
                start=270, end=350, fill=255, width=int(12 * s))
    clip = Image.new("L", (W, H), 0)
    ImageDraw.Draw(clip).ellipse(
        [cx - r + lw, cy - r + lw, cx + r - lw, cy + r - lw], fill=255)
    sw = Image.composite(sw, Image.new("L", (W, H), 0), clip)
    mask.paste(Image.new("L", (W, H), 255), (0, 0),
               Image.eval(sw, lambda v: v))
    # --- text ---
    fsize = int(200 * s)
    font = ImageFont.truetype(FONT, fsize)
    tx = cx + r + int(58 * s)
    d.text((tx, cy), "靚優診所", font=font, fill=255, anchor="lm")
    mask = mask.resize((W * 4 // scale, H * 4 // scale), Image.LANCZOS)
    return apply_gold(mask)

def user_end():
    return 470  # arc sweep end

logo = make_logo()
logo.save("logo_gold.png")
print("logo size:", logo.size)

# small preview on dark + light bg
for name, bg in [("logo_on_dark.png", (30, 30, 34)), ("logo_on_light.png", (235, 232, 228))]:
    canvas = Image.new("RGB", logo.size, bg)
    canvas.paste(logo, (0, 0), logo)
    canvas.save(name)
