#!/usr/bin/env python3
"""Peach lady character sprite + scene backgrounds (flat-luxe 2D style)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
SS = 2  # supersample factor for sprites

def lerp(c0, c1, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))

# ---------------- character sprite ----------------
# canvas 520x680 (at 1x); body center (260,350) r=195

def body_layer(dewy):
    """numpy body: vertical gradient + radial highlight + soft shading."""
    W, H = 520, 680
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy, r = 260.0, 350.0, 195.0
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    mask = np.clip((r - d) / 2.0, 0, 1)  # AA edge
    t = np.clip((yy - (cy - r)) / (2 * r), 0, 1)
    dull_top, dull_bot = (233, 196, 158), (206, 158, 124)
    dewy_top, dewy_bot = (255, 216, 168), (248, 134, 118)
    top = lerp(dull_top, dewy_top, dewy)
    bot = lerp(dull_bot, dewy_bot, dewy)
    rgb = np.zeros((H, W, 3), np.float32)
    for k in range(3):
        rgb[..., k] = top[k] + (bot[k] - top[k]) * t
    # left-cheek rosy zone (peach two-tone)
    dz = np.sqrt(((xx - (cx + 90)) / (r * 1.1)) ** 2 + ((yy - (cy + 70)) / (r * 0.9)) ** 2)
    rose = np.clip(1 - dz, 0, 1) ** 1.5 * (0.25 + 0.45 * dewy)
    rose_c = lerp((215, 150, 125), (244, 105, 105), dewy)
    for k in range(3):
        rgb[..., k] = rgb[..., k] * (1 - rose) + rose_c[k] * rose
    # radial highlight upper-left (stronger when dewy)
    dh = np.sqrt(((xx - (cx - 70)) / (r * 0.75)) ** 2 + ((yy - (cy - 85)) / (r * 0.6)) ** 2)
    hi = np.clip(1 - dh, 0, 1) ** 2 * (0.18 + 0.5 * dewy)
    for k, c in enumerate((255, 240, 222)):
        rgb[..., k] = rgb[..., k] * (1 - hi) + c * hi
    # bottom-right shade
    ds = np.sqrt(((xx - (cx + 110)) / (r * 1.05)) ** 2 + ((yy - (cy + 120)) / (r * 0.95)) ** 2)
    sh = np.clip(1 - ds, 0, 1) ** 2 * 0.22
    for k in range(3):
        rgb[..., k] *= (1 - sh)
    out = np.dstack([rgb, mask[..., None] * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def fluff_cluster(draw, pts, r0, colors, rng):
    for (x, y) in pts:
        r = r0 + rng.integers(-6, 7)
        c = colors[rng.integers(0, len(colors))]
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)

GOLDS_BACK = [(214, 160, 40, 255), (198, 146, 34, 255), (226, 176, 62, 255)]
GOLDS_FRONT = [(246, 208, 100, 255), (232, 186, 74, 255), (252, 222, 132, 255)]

def coat_back():
    img = Image.new("RGBA", (520, 680), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(3)
    pts = []
    # wide fluffy wrap behind the lower half of the body
    for ang in np.linspace(15, 165, 20):
        a = np.radians(ang)
        pts.append((260 + 225 * np.cos(a), 360 + 205 * np.sin(a)))
    for ang in np.linspace(25, 155, 14):
        a = np.radians(ang)
        pts.append((260 + 250 * np.cos(a), 340 + 235 * np.sin(a)))
    fluff_cluster(d, pts, 40, GOLDS_BACK, rng)
    return img

def coat_front():
    img = Image.new("RGBA", (520, 680), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(5)
    pts = []
    # shawl collar: sweeps from the sides across the lower front
    for ang in np.linspace(30, 150, 12):
        a = np.radians(ang)
        pts.append((260 + 208 * np.cos(a), 380 + 188 * np.sin(a)))
    fluff_cluster(d, pts, 34, GOLDS_FRONT, rng)
    # shoulder puffs at the sides
    fluff_cluster(d, [(48, 400), (475, 400), (35, 470), (488, 470)], 38, GOLDS_FRONT, rng)
    return img

def face_layer(dewy, goggles=False):
    img = Image.new("RGBA", (520 * SS, 680 * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = SS
    # leaf + stem
    d.ellipse([(238 - 6) * s, 120 * s, (282 + 6) * s, 175 * s], fill=(146, 110, 70, 255))
    for dx, rot in ((-52, -25), (48, 20)):
        leaf = Image.new("RGBA", (150 * s, 80 * s), (0, 0, 0, 0))
        dl = ImageDraw.Draw(leaf)
        dl.ellipse([5 * s, 12 * s, 145 * s, 68 * s], fill=(120, 168, 84, 255))
        dl.line([(20 * s, 40 * s), (135 * s, 40 * s)], fill=(88, 132, 60, 255), width=3 * s)
        leaf = leaf.rotate(rot, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(leaf, ((260 + dx - leaf.width // (2 * s)) * s, (105 - leaf.height // (2 * s)) * s))
    # peach cleft
    d.arc([180 * s, 140 * s, 340 * s, 320 * s], start=250, end=290,
          fill=(200, 140, 110, 200), width=6 * s)
    if goggles:
        # black goggles band + lenses
        d.rounded_rectangle([110 * s, 262 * s, 410 * s, 352 * s], radius=44 * s,
                            fill=(28, 26, 30, 255))
        for ex in (187, 333):
            d.ellipse([(ex - 55) * s, 272 * s, (ex + 55) * s, 344 * s], fill=(52, 50, 44, 255))
            d.ellipse([(ex - 40) * s, 282 * s, (ex + 10) * s, 316 * s], fill=(96, 92, 70, 160))
    else:
        for ex in (185, 335):
            # eyeshadow
            shadow = lerp((205, 165, 150), (232, 158, 120), dewy)
            d.ellipse([(ex - 52) * s, 245 * s, (ex + 52) * s, 320 * s], fill=shadow + (150,))
            # eye white + iris
            d.ellipse([(ex - 42) * s, 255 * s, (ex + 42) * s, 352 * s], fill=(252, 250, 248, 255))
            d.ellipse([(ex - 26) * s, 272 * s, (ex + 26) * s, 336 * s], fill=(112, 132, 96, 255))
            d.ellipse([(ex - 15) * s, 285 * s, (ex + 15) * s, 322 * s], fill=(30, 26, 24, 255))
            d.ellipse([(ex - 2) * s, 284 * s, (ex + 16) * s, 302 * s], fill=(255, 255, 255, 230))
            # lash line + lashes
            d.arc([(ex - 44) * s, 252 * s, (ex + 44) * s, 340 * s], start=200, end=340,
                  fill=(40, 30, 28, 255), width=7 * s)
            for i, (lx, ly, ex2, ey2) in enumerate([(-38, 258, -58, 240), (-8, 246, -14, 224), (24, 250, 38, 232)]):
                d.line([((ex + lx) * s, ly * s), ((ex + ex2) * s, ey2 * s)],
                       fill=(40, 30, 28, 255), width=5 * s)
            # brow: gentle high arch
            d.arc([(ex - 36) * s, 208 * s, (ex + 36) * s, 252 * s], start=225, end=315,
                  fill=(168, 116, 86, 255), width=5 * s)
    # lips (full pout)
    lip = lerp((196, 110, 105), (226, 84, 96), dewy)
    d.ellipse([225 * s, 392 * s, 295 * s, 428 * s], fill=lip + (255,))
    d.ellipse([228 * s, 380 * s, 258 * s, 404 * s], fill=lip + (255,))
    d.ellipse([262 * s, 380 * s, 292 * s, 404 * s], fill=lip + (255,))
    if dewy > 0.5:
        d.ellipse([238 * s, 388 * s, 256 * s, 398 * s], fill=(255, 235, 235, 190))
    # subtle dryness lines when dull
    if dewy < 0.5:
        wa = int((1 - dewy * 2) * 110)
        for (x0, y0, x1, y1) in [(122, 350, 168, 382), (348, 346, 396, 380)]:
            d.arc([x0 * s, y0 * s, x1 * s, y1 * s], start=210, end=320,
                  fill=(178, 128, 100, wa), width=3 * s)
    img = img.resize((520, 680), Image.LANCZOS)
    return img

def droplets_layer():
    img = Image.new("RGBA", (520, 680), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for (x, y, r) in [(150, 330, 9), (200, 470, 7), (330, 300, 8), (370, 430, 10), (250, 520, 7)]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=(210, 236, 255, 210))
        d.ellipse([x - r // 2, y - r // 2, x, y], fill=(255, 255, 255, 230))
    return img

def arm_wave(angle):
    """right arm capsule rotated; anchor at shoulder (415,340) of sprite."""
    arm = Image.new("RGBA", (220, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(arm)
    d.rounded_rectangle([10, 42, 190, 82], radius=20, fill=(250, 190, 150, 255))
    d.ellipse([170, 32, 214, 90], fill=(252, 198, 158, 255))
    arm = arm.rotate(angle, expand=True, center=(20, 62), resample=Image.BICUBIC)
    return arm

def bag_layer():
    img = Image.new("RGBA", (520, 680), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.arc([60, 430, 150, 560], start=180, end=330, fill=(190, 160, 60, 255), width=5)
    d.rounded_rectangle([52, 520, 162, 600], radius=18, fill=(34, 30, 32, 255))
    d.rounded_rectangle([52, 520, 162, 545], radius=12, fill=(52, 46, 48, 255))
    d.ellipse([98, 548, 118, 568], fill=(212, 172, 66, 255))
    return img

def peach_sprite(dewy, goggles=False, coat=True, bag=False, wave=None, droplets=False):
    spr = Image.new("RGBA", (520, 680), (0, 0, 0, 0))
    if coat:
        spr.alpha_composite(coat_back())
    spr.alpha_composite(body_layer(dewy))
    spr.alpha_composite(face_layer(dewy, goggles))
    if droplets:
        spr.alpha_composite(droplets_layer())
    if coat:
        spr.alpha_composite(coat_front())
    if bag:
        spr.alpha_composite(bag_layer())
    if wave is not None:
        arm = arm_wave(wave)
        spr.alpha_composite(arm, (398, 250))
    return spr

# ---------------- backgrounds ----------------

def _marble_floor(d, W, y0, H, rng):
    d.rectangle([0, y0, W, H], fill=(226, 220, 212))
    for _ in range(26):
        x = rng.integers(0, W); ln = rng.integers(60, 220)
        y = rng.integers(y0 + 8, H - 6)
        d.line([(x, y), (x + ln, y + rng.integers(-8, 8))], fill=(206, 199, 190), width=2)
    d.line([(0, y0), (W, y0)], fill=(200, 193, 184), width=3)

def _gold_sign(img, d, cx, cy, scale=1.0):
    f = ImageFont.truetype(FONT, int(34 * scale))
    d.text((cx, cy), "靚優診所", font=f, fill=(196, 156, 56), anchor="mm")

def bg_lobby():
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (240, 232, 222))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(11)
    # wall gradient bands + gold slats
    for i, x in enumerate(range(0, W, 64)):
        d.rectangle([x, 0, x + 64, 520], fill=(242 - i % 3 * 3, 234 - i % 3 * 3, 224 - i % 3 * 2))
    for x in (240, 300, 940, 1000):
        d.rectangle([x, 0, x + 10, 520], fill=(212, 176, 96))
    _marble_floor(d, W, 520, H, rng)
    # glass door (left)
    d.rectangle([40, 60, 210, 520], outline=(196, 160, 70), width=8)
    d.rectangle([56, 76, 194, 504], fill=(214, 226, 230))
    d.line([(125, 76), (125, 504)], fill=(196, 160, 70), width=5)
    # reception desk (right)
    d.rounded_rectangle([880, 360, 1240, 560], radius=26, fill=(214, 196, 172))
    d.rectangle([868, 348, 1252, 372], fill=(196, 160, 70))
    _gold_sign(img, d, 1060, 250, 1.1)
    d.rectangle([950, 285, 1170, 291], fill=(212, 176, 96))
    # plant
    d.rounded_rectangle([760, 430, 830, 530], radius=10, fill=(180, 150, 110))
    for (px, py, pr) in [(795, 380, 55), (760, 410, 40), (830, 405, 42)]:
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(118, 150, 96))
    # receptionist behind the desk
    d.ellipse([1030, 268, 1090, 328], fill=(246, 210, 182))        # face
    d.pieslice([1018, 250, 1102, 334], start=180, end=360, fill=(74, 56, 48))  # hair
    d.rounded_rectangle([1006, 330, 1114, 386], radius=20, fill=(250, 250, 250))  # white coat
    d.line([(1046, 296), (1056, 300), (1066, 296)], fill=(180, 110, 100), width=3)  # smile
    return img

def bg_room():
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (244, 242, 240))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(12)
    d.rectangle([0, 0, W, 500], fill=(238, 238, 240))
    d.rectangle([880, 60, 1200, 340], fill=(224, 234, 240))   # window light
    d.rectangle([880, 60, 1200, 340], outline=(210, 214, 218), width=6)
    _marble_floor(d, W, 500, H, rng)
    # treatment chair
    d.rounded_rectangle([340, 430, 980, 560], radius=40, fill=(228, 214, 196))
    d.rounded_rectangle([300, 240, 480, 520], radius=40, fill=(234, 220, 202))
    d.rounded_rectangle([300, 540, 1000, 580], radius=14, fill=(206, 190, 172))
    # equipment cart
    d.rounded_rectangle([80, 330, 230, 560], radius=14, fill=(228, 228, 232))
    d.rectangle([100, 360, 210, 420], fill=(190, 205, 220))
    d.ellipse([110, 570, 140, 600], fill=(180, 180, 186))
    d.ellipse([180, 570, 210, 600], fill=(180, 180, 186))
    return img

def bg_exterior():
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (236, 230, 220))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(13)
    # facade header
    d.rectangle([0, 0, W, 150], fill=(52, 48, 46))
    f = ImageFont.truetype(FONT, 56)
    d.text((640, 75), "靚優健康醫學美容診所", font=f, fill=(224, 184, 88), anchor="mm")
    # marble columns
    for x in (0, 1160):
        d.rectangle([x, 150, x + 120, 620], fill=(232, 228, 222))
        for _ in range(10):
            y = rng.integers(170, 600)
            d.line([(x + 8, y), (x + 112, y + rng.integers(-10, 10))], fill=(214, 209, 202), width=2)
    # glass doors
    d.rectangle([120, 150, 1160, 620], fill=(206, 220, 226))
    for x in (420, 640, 860):
        d.line([(x, 150), (x, 620)], fill=(196, 160, 70), width=8)
    d.rectangle([120, 150, 1160, 620], outline=(196, 160, 70), width=10)
    _marble_floor(d, W, 620, H, rng)
    # plants
    for bx in (60, 1200):
        d.rounded_rectangle([bx - 40, 520, bx + 40, 620], radius=10, fill=(170, 140, 100))
        for (px, py, pr) in [(bx, 470, 52), (bx - 32, 500, 38), (bx + 32, 498, 40)]:
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(118, 150, 96))
    return img

if __name__ == "__main__":
    # previews
    peach_sprite(0.15, coat=True, bag=True).save("prev_peach_dull.png")
    peach_sprite(1.0, coat=True, wave=30).save("prev_peach_dewy.png")
    peach_sprite(0.1, goggles=True, coat=False).save("prev_peach_gog.png")
    bg_lobby().save("prev_bg_lobby.png")
    bg_room().save("prev_bg_room.png")
    bg_exterior().save("prev_bg_ext.png")
    print("previews saved")
