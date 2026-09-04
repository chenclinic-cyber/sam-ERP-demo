#!/usr/bin/env python3
"""Vertical (1080x1920) gold CTA end card."""
from PIL import Image, ImageDraw, ImageFont
import numpy as np

W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
GOLD = (222, 178, 60)
GOLD_HI = (250, 228, 150)
GOLD_DIM = (170, 130, 40)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
d = np.sqrt(((xx - W / 2) / (W * 0.95)) ** 2 + ((yy - H * 0.38) / (H * 0.75)) ** 2)
glow = np.clip(1.0 - d, 0, 1) ** 2.2
base = np.zeros((H, W, 3), np.float32)
base[..., 0] = 24 + glow * 46
base[..., 1] = 21 + glow * 34
base[..., 2] = 18 + glow * 14
img = Image.fromarray(base.astype(np.uint8))
draw = ImageDraw.Draw(img)

rng = np.random.default_rng(7)
for _ in range(40):
    x, y = rng.integers(40, W - 40), rng.integers(40, H - 40)
    r = int(rng.integers(1, 3))
    draw.ellipse([x - r, y - r, x + r, y + r], fill=GOLD_HI)

logo = Image.open("real_logo_gold.png").convert("RGBA")
lw = 760
logo_s = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
img.paste(logo_s, ((W - lw) // 2, 360), logo_s)  # ends ~660

def text_c(y, s, size, fill):
    f = ImageFont.truetype(FONT, size)
    draw.text((W / 2, y), s, font=f, fill=fill, anchor="ma")

text_c(780, "水 嫩 回 春", 88, GOLD_HI)
text_c(910, "蜜 桃 新 生", 88, GOLD_HI)
text_c(1060, "抗衰逆齡 × 私密緊緻", 44, (214, 200, 170))
text_c(1130, "專 屬 訂 製 療 程", 44, (214, 200, 170))

draw.line([(W / 2 - 300, 1260), (W / 2 + 300, 1260)], fill=GOLD_DIM, width=2)
draw.ellipse([W / 2 - 6, 1254, W / 2 + 6, 1266], fill=GOLD)

bw, bh = 620, 118
bx, by = (W - bw) // 2, 1330
for i in range(3):
    draw.rounded_rectangle([bx - i, by - i, bx + bw + i, by + bh + i],
                           radius=bh // 2 + i, outline=GOLD, width=1)
bnp = np.zeros((bh, bw, 3), np.float32)
for i in range(bh):
    t = i / (bh - 1)
    c0, c1 = (238, 198, 92), (180, 134, 36)
    bnp[i] = [c0[k] + (c1[k] - c0[k]) * t for k in range(3)]
btn = Image.fromarray(bnp.astype(np.uint8))
m = Image.new("L", (bw, bh), 0)
ImageDraw.Draw(m).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bh // 2, fill=255)
img.paste(btn, (bx, by), m)
f = ImageFont.truetype(FONT, 56)
draw.text((W / 2, by + bh / 2 - 2), "立即預約諮詢", font=f, fill=(40, 28, 8), anchor="mm")

text_c(1530, "私訊預約", 36, (170, 158, 132))
text_c(1595, "靚優健康醫學美容診所", 36, (170, 158, 132))

img.save("endcard_peach_v.png")
print("vertical endcard saved", img.size)
