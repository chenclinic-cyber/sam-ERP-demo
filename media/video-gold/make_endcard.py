#!/usr/bin/env python3
"""Gold-themed CTA end card, 1280x720."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

W, H = 1280, 720
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
GOLD = (222, 178, 60)
GOLD_HI = (250, 228, 150)
GOLD_DIM = (170, 130, 40)

# background: deep charcoal with a soft radial gold glow
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.42) / (H * 0.9)) ** 2)
glow = np.clip(1.0 - d, 0, 1) ** 2.2
base = np.zeros((H, W, 3), np.float32)
base[..., 0] = 24 + glow * 46
base[..., 1] = 21 + glow * 34
base[..., 2] = 18 + glow * 14
img = Image.fromarray(base.astype(np.uint8))
draw = ImageDraw.Draw(img)

# subtle sparkles
rng = np.random.default_rng(7)
for _ in range(26):
    x, y = rng.integers(40, W - 40), rng.integers(30, H - 30)
    r = int(rng.integers(1, 3))
    a = int(rng.integers(60, 140))
    draw.ellipse([x - r, y - r, x + r, y + r], fill=(GOLD_HI[0], GOLD_HI[1], GOLD_HI[2]))

# logo
logo = Image.open("real_logo_gold.png").convert("RGBA")
lw = 520
logo_s = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
img.paste(logo_s, ((W - lw) // 2, 88), logo_s)

def text_c(y, s, size, fill, tracking=0, font_path=FONT):
    f = ImageFont.truetype(font_path, size)
    if tracking:
        widths = [draw.textlength(ch, font=f) + tracking for ch in s]
        total = sum(widths) - tracking
        x = (W - total) / 2
        for ch, wd in zip(s, widths):
            draw.text((x, y), ch, font=f, fill=fill)
            x += wd
    else:
        draw.text((W / 2, y), s, font=f, fill=fill, anchor="ma")

# tagline
text_c(338, "剝 去 歲 月 ・ 煥 然 新 生", 52, GOLD_HI)
text_c(408, "抗衰逆齡 × 私密緊緻 專屬訂製療程", 30, (214, 200, 170))

# divider
draw.line([(W / 2 - 260, 462), (W / 2 + 260, 462)], fill=GOLD_DIM, width=2)
draw.ellipse([W / 2 - 5, 457, W / 2 + 5, 467], fill=GOLD)

# CTA button
bw, bh = 480, 84
bx, by = (W - bw) // 2, 496
for i in range(3):
    draw.rounded_rectangle([bx - i, by - i, bx + bw + i, by + bh + i],
                           radius=bh // 2 + i, outline=GOLD, width=1)
grad = gold = None
btn = Image.new("RGB", (bw, bh))
bnp = np.zeros((bh, bw, 3), np.float32)
for i in range(bh):
    t = i / (bh - 1)
    c0, c1 = (238, 198, 92), (180, 134, 36)
    bnp[i] = [c0[k] + (c1[k] - c0[k]) * t for k in range(3)]
btn = Image.fromarray(bnp.astype(np.uint8))
m = Image.new("L", (bw, bh), 0)
ImageDraw.Draw(m).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bh // 2, fill=255)
img.paste(btn, (bx, by), m)
f = ImageFont.truetype(FONT, 40)
draw.text((W / 2, by + bh / 2 - 2), "立即預約諮詢", font=f, fill=(40, 28, 8), anchor="mm")

# bottom line
text_c(614, "私訊預約 ｜ 名額有限 ｜ 靚優健康醫學美容診所", 26, (170, 158, 132))

img.save("endcard.png")
print("endcard saved", img.size)
