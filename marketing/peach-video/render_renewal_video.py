# -*- coding: utf-8 -*-
"""
「皺皺水果重生記」— 靚優煥膚短影音
28 秒 / 9:16 (720x1280) / 24fps
皺皺水果們 → 靚優治療(雷射+注射) → 光滑發亮 → 片尾(Logo+醫師照)
需要 assets/logo.png 與 assets/doctor.jpg
用法: python3 render_renewal_video.py
輸出: dreamu_renewal_720x1280.mp4
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 720, 1280
FPS = 24
DUR = 28.0
N_FRAMES = int(DUR * FPS)
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

SHOTS = [(0, 5), (5, 9), (9, 16), (16, 20), (20, 28)]
XFADE = 7

GOLD = (183, 146, 74, 255)
BROWN = (110, 82, 52, 255)


def font(size):
    return ImageFont.truetype(FONT_PATH, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- assets
def load_logo():
    im = Image.open(os.path.join(OUT_DIR, "assets/logo.png")).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    lum = arr[..., :3].mean(axis=2)
    alpha = np.clip((250 - lum) / 14.0, 0, 1) * 255  # 去白底
    arr[..., 3] = alpha
    im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return im.crop(im.getbbox())


def load_doctor(circle_d=560):
    im = Image.open(os.path.join(OUT_DIR, "assets/doctor.jpg")).convert("RGB")
    w, h = im.size  # 851x1391，臉在上半部中央
    side = int(w * 0.86)
    cx, cy = w // 2, int(h * 0.30)
    box = (cx - side // 2, max(0, cy - side // 2),
           cx + side // 2, max(0, cy - side // 2) + side)
    im = im.crop(box).resize((circle_d, circle_d), Image.LANCZOS)
    mask = Image.new("L", (circle_d, circle_d), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, circle_d, circle_d], fill=255)
    out = Image.new("RGBA", (circle_d, circle_d), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


LOGO = load_logo()
DOCTOR = load_doctor()


# ---------------------------------------------------------------- sprites
def make_sphere(top, bot, glossy=False, size=900):
    n = size
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    c = n / 2.0
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
    nz = np.sqrt(np.clip(1 - r * r, 0, 1))
    nx = (x - c) / c
    ny = (y - c) / c
    lam = np.clip(nx * -0.38 + ny * -0.5 + nz * 0.78, 0, 1)
    ty = y / n
    col = np.array(top, np.float32)[None, None] * (1 - ty)[..., None] + \
        np.array(bot, np.float32)[None, None] * ty[..., None]
    col = col * (0.80 + 0.20 * lam)[..., None]
    if glossy:
        h = np.clip(nx * -0.45 + ny * -0.6 + nz * 0.66, 0, 1) ** 18
        col = col + 190 * h[..., None]
        rim = np.clip(nx * 0.7 + nz * 0.1, 0, 1) ** 6
        col = col + 55 * rim[..., None]
    col = np.clip(col, 0, 255)
    alpha = np.clip((1.0 - r) / 0.02, 0, 1) * 255
    img = Image.fromarray(np.dstack([col, alpha]).astype(np.uint8), "RGBA")
    if glossy:
        img = ImageEnhance.Color(img).enhance(1.15)
    return img


PEACH_M = make_sphere((255, 220, 182), (252, 150, 142))
PEACH_G = make_sphere((255, 220, 182), (252, 150, 142), glossy=True)
LEMON_M = make_sphere((255, 246, 200), (244, 204, 90))
LEMON_G = make_sphere((255, 246, 200), (244, 204, 90), glossy=True)
ORANGE_M = make_sphere((255, 226, 176), (250, 160, 74))
ORANGE_G = make_sphere((255, 226, 176), (250, 160, 74), glossy=True)


def sparkle(d, x, y, s, color=(255, 255, 255, 230)):
    d.polygon([(x - s, y), (x, y - s * 0.28), (x + s, y), (x, y + s * 0.28)], fill=color)
    d.polygon([(x, y - s), (x - s * 0.28, y), (x, y + s), (x + s * 0.28, y)], fill=color)


def draw_wrinkles(d, cx, cy, R, amt, seed=0, x_max=None):
    """皺紋：橫向弧線+眼周/嘴角紋。amt 0~1。"""
    if amt <= 0.02:
        return
    rng = random.Random(seed)
    n = int(13 * amt)
    a = int(120 * amt)
    for i in range(n):
        yy = cy + R * rng.uniform(-0.78, 0.82)
        half = math.sqrt(max(0.05, 1 - ((yy - cy) / R) ** 2)) * R
        x0 = cx - half * rng.uniform(0.35, 0.8)
        x1 = cx + half * rng.uniform(0.35, 0.8)
        if x_max is not None:
            if x0 > x_max:
                continue
            x1 = min(x1, x_max)
            if x1 - x0 < R * 0.1:
                continue
        bow = R * rng.uniform(0.04, 0.10) * (1 if yy < cy else -1)
        mid = ((x0 + x1) / 2, yy + bow)
        pts = []
        for t in np.linspace(0, 1, 12):
            px = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mid[0] + t * t * x1
            py = (1 - t) ** 2 * yy + 2 * (1 - t) * t * mid[1] + t * t * yy
            pts.append((px, py))
        d.line(pts, fill=(150, 92, 76, a), width=max(2, int(R * 0.018)))
    # 眼下細紋
    for sx in (-0.30, 0.30):
        ex = cx + sx * R
        if x_max is not None and ex > x_max:
            continue
        for k in range(2):
            d.arc([ex - R * 0.14, cy + R * 0.02 + k * R * 0.05,
                   ex + R * 0.14, cy + R * 0.14 + k * R * 0.05], 200, 340,
                  fill=(150, 92, 76, a), width=max(1, int(R * 0.012)))


def paste_fruit(img, sprites, cx, cy, R, gloss=0.0, sag=0.0, split_x=None):
    """貼水果球體。sag: 下垂/暗沉 0~1。split_x: 左皺右亮。"""
    matte, glossb = sprites
    w = int(2 * R)
    h = int(2 * R * (1 - 0.10 * sag))
    m = matte.resize((w, h), Image.LANCZOS)
    if sag > 0.02:
        dull = ImageEnhance.Brightness(ImageEnhance.Color(m).enhance(1 - 0.45 * sag)).enhance(1 - 0.13 * sag)
        m = Image.blend(m, dull, clamp(sag))
    g = glossb.resize((w, h), Image.LANCZOS)
    if split_x is None:
        body = Image.blend(m, g, clamp(gloss)) if gloss > 0 else m
    else:
        body = g.copy()
        cut = int(clamp((split_x - (cx - R)) / (2 * R)) * w)
        if cut > 0:
            left = m.crop((0, 0, cut, h))
            body.paste(left, (0, 0), left)
    img.alpha_composite(body, (int(cx - R), int(cy - R * (1 - 0.20 * sag))))


def draw_leaf(layer, cx, cy, R, wiggle=0.0, droop=0.0):
    d = ImageDraw.Draw(layer)
    sx, sy = cx + R * 0.10, cy - R * 0.97
    d.line([(sx, sy), (sx + R * 0.03, sy - R * 0.16)], fill=(122, 82, 52, 255),
           width=max(2, int(R * 0.035)))
    leaf = Image.new("RGBA", (int(R * 0.9), int(R * 0.5)), (0, 0, 0, 0))
    dl = ImageDraw.Draw(leaf)
    green = (92, 168, 82, 255) if droop < 0.5 else (128, 148, 84, 255)
    green2 = (116, 196, 100, 255) if droop < 0.5 else (150, 168, 100, 255)
    dl.ellipse([0, int(R * 0.06), int(R * 0.62), int(R * 0.40)], fill=green)
    dl.ellipse([int(R * 0.06), int(R * 0.10), int(R * 0.52), int(R * 0.32)], fill=green2)
    ang = 28 + wiggle - droop * 55
    leaf = leaf.rotate(ang, expand=True, resample=Image.BICUBIC)
    layer.alpha_composite(leaf, (int(sx - R * 0.06), int(sy - R * 0.42)))


def draw_face(d, cx, cy, R, mood="happy", lashes=True):
    """mood: happy / sad / closed / wink"""
    ew, eh = R * 0.16, R * 0.145
    ey_ = cy - R * 0.10
    exl, exr = cx - R * 0.30, cx + R * 0.30
    sad = mood == "sad"
    for ex, side in ((exl, -1), (exr, 1)):
        closed = mood == "closed" or (mood == "wink" and side > 0)
        d.ellipse([ex - ew * 1.15, ey_ - eh * 1.5, ex + ew * 1.15, ey_ + eh * 0.2],
                  fill=(248, 170, 190, 70 if sad else 95))
        if closed:
            d.arc([ex - ew, ey_ - eh * 0.4, ex + ew, ey_ + eh * 0.8], 20, 160,
                  fill=(70, 40, 40, 255), width=max(2, int(R * 0.022)))
        elif sad:
            d.chord([ex - ew * 0.75, ey_ - eh * 0.5, ex + ew * 0.75, ey_ + eh * 0.75],
                    0, 180, fill=(66, 40, 40, 255))
            d.ellipse([ex - ew * 0.2, ey_ - eh * 0.15, ex + ew * 0.15, ey_ + eh * 0.25],
                      fill=(255, 255, 255, 190))
        else:
            d.ellipse([ex - ew * 0.75, ey_ - eh, ex + ew * 0.75, ey_ + eh * 0.55],
                      fill=(66, 40, 40, 255))
            d.ellipse([ex - ew * 0.28, ey_ - eh * 0.72, ex + ew * 0.2, ey_ - eh * 0.1],
                      fill=(255, 255, 255, 235))
        if lashes and not closed:
            for k, ang in enumerate((-55, -30, -8)):
                a = math.radians(ang if side > 0 else 180 - ang)
                bx = ex + side * ew * 0.62
                by = ey_ - eh * 0.55 + k * eh * 0.28
                d.line([(bx, by), (bx + math.cos(a) * ew * 0.85, by + math.sin(a) * ew * 0.85)],
                       fill=(60, 35, 35, 255), width=max(2, int(R * 0.018)))
        # 眉毛：sad 時往外下垂
        b0, b1 = (215, 325) if not sad else (200, 300)
        if side < 0:
            d.arc([ex - ew, ey_ - eh * (2.6 - 0.7 * sad), ex + ew, ey_ - eh * 0.9],
                  b0 - 15, b1 - 15, fill=(150, 90, 70, 210), width=max(2, int(R * 0.014)))
        else:
            d.arc([ex - ew, ey_ - eh * (2.6 - 0.7 * sad), ex + ew, ey_ - eh * 0.9],
                  b0, b1, fill=(150, 90, 70, 210), width=max(2, int(R * 0.014)))
    # 腮紅
    blush_a = 40 if sad else 75
    d.ellipse([cx - R * 0.62, cy + R * 0.05, cx - R * 0.36, cy + R * 0.20],
              fill=(255, 130, 140, blush_a))
    d.ellipse([cx + R * 0.36, cy + R * 0.05, cx + R * 0.62, cy + R * 0.20],
              fill=(255, 130, 140, blush_a))
    # 嘴
    ly = cy + R * 0.30
    lw = R * 0.15
    if sad:
        d.arc([cx - lw, ly, cx + lw, ly + lw * 1.6], 195, 345,
              fill=(190, 80, 95, 255), width=max(3, int(R * 0.03)))
    else:
        d.chord([cx - lw, ly - lw * 0.75, cx + lw, ly + lw * 0.75], 15, 165,
                fill=(232, 80, 110, 255))
        d.ellipse([cx - lw * 0.45, ly - lw * 0.05, cx - lw * 0.05, ly + lw * 0.28],
                  fill=(255, 175, 195, 200))


def draw_fruit(img, kind, cx, cy, R, mood="happy", wrinkle=0.0, gloss=0.0,
               t=0.0, leaf=False, lashes=False, split_x=None, seed=0):
    sprites = {"peach": (PEACH_M, PEACH_G), "lemon": (LEMON_M, LEMON_G),
               "orange": (ORANGE_M, ORANGE_G)}[kind]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    paste_fruit(layer, sprites, cx, cy, R, gloss=gloss, sag=wrinkle, split_x=split_x)
    d = ImageDraw.Draw(layer)
    draw_wrinkles(d, cx, cy + R * 0.10 * wrinkle, R, wrinkle, seed=seed, x_max=split_x)
    if leaf:
        draw_leaf(layer, cx, cy + R * 0.17 * wrinkle, R,
                  wiggle=math.sin(t * 3 + seed) * 4, droop=wrinkle)
    d = ImageDraw.Draw(layer)
    draw_face(d, cx, cy + R * 0.10 * wrinkle, R, mood=mood, lashes=lashes)
    img.alpha_composite(layer)


# ---------------------------------------------------------------- helpers
def bg_vertical(c_top, c_bot):
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = np.array(c_top, np.float32)[None, None] * (1 - g) + \
        np.array(c_bot, np.float32)[None, None] * g
    arr = np.repeat(arr, W, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def caption(img, text, sub=None, y=None, small_note=None, color=(120, 62, 66, 255)):
    d = ImageDraw.Draw(img)
    y = y if y is not None else H - 205
    f1 = font(50)
    bbox = d.textbbox((0, 0), text, font=f1)
    tw = bbox[2] - bbox[0]
    d.rounded_rectangle([W / 2 - tw / 2 - 28, y - 16, W / 2 + tw / 2 + 28, y + 74],
                        radius=18, fill=(255, 255, 255, 180))
    d.text((W / 2 - tw / 2, y), text, font=f1, fill=color)
    if sub:
        f2 = font(30)
        b2 = d.textbbox((0, 0), sub, font=f2)
        d.text((W / 2 - (b2[2] - b2[0]) / 2, y + 90), sub, font=f2, fill=(150, 105, 100, 255))
    if small_note:
        f3 = font(22)
        b3 = d.textbbox((0, 0), small_note, font=f3)
        d.text((W / 2 - (b3[2] - b3[0]) / 2, H - 44), small_note, font=f3,
               fill=(140, 120, 115, 220))


def floor(img, y0, col=(238, 229, 222, 255)):
    d = ImageDraw.Draw(img)
    d.rectangle([0, y0, W, H], fill=col)
    d.line([(0, y0), (W, y0)], fill=(222, 210, 202, 255), width=3)


# ---------------------------------------------------------------- shots
def shot1(t, p):
    """皺皺水果們：垂頭喪氣。"""
    img = bg_vertical((240, 234, 230), (223, 213, 208))
    floor(img, H * 0.68)
    d = ImageDraw.Draw(img)
    # 陰天氛圍小雲
    for k, (cxx, cyy) in enumerate(((W * 0.2, H * 0.12), (W * 0.75, H * 0.08))):
        for dx, rr in ((-40, 34), (0, 46), (44, 32)):
            d.ellipse([cxx + dx - rr, cyy - rr * 0.7, cxx + dx + rr, cyy + rr * 0.7],
                      fill=(214, 208, 205, 255))
    droop = math.sin(t * 1.8) * 5
    # 主角皺桃子
    draw_fruit(img, "peach", W * 0.5, H * 0.42 + droop, 175, mood="sad",
               wrinkle=1.0, t=t, leaf=True, lashes=True, seed=1)
    # 皺檸檬與皺橘子
    draw_fruit(img, "lemon", W * 0.17, H * 0.56 + droop * 0.6, 100, mood="sad",
               wrinkle=1.0, t=t, seed=2)
    draw_fruit(img, "orange", W * 0.85, H * 0.57 - droop * 0.5, 105, mood="sad",
               wrinkle=1.0, t=t, seed=3)
    # 嘆氣符號
    if (t % 2.0) < 1.2:
        a = int(200 * (1 - abs((t % 2.0) / 1.2 - 0.5) * 2))
        f = font(46)
        d.text((W * 0.66, H * 0.24 - (t % 2.0) * 22), "唉…", font=f,
               fill=(150, 130, 125, a))
    caption(img, "歲月悄悄，肌膚皺皺…", sub="鬆弛、暗沉、沒精神")
    return img


def shot2(t, p):
    """來到靚優：門面+金色 Logo 招牌。"""
    img = bg_vertical((248, 240, 228), (236, 222, 205))
    floor(img, H * 0.72, (235, 224, 212, 255))
    d = ImageDraw.Draw(img)
    # 診所立面
    d.rounded_rectangle([W * 0.10, H * 0.10, W * 0.90, H * 0.72], radius=18,
                        fill=(252, 248, 242, 255), outline=(224, 208, 182, 255), width=6)
    # 招牌(白底金字 Logo)
    lw = int(W * 0.56)
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    d.rounded_rectangle([W / 2 - lw / 2 - 24, H * 0.135, W / 2 + lw / 2 + 24,
                         H * 0.135 + logo.size[1] + 36], radius=14,
                        fill=(255, 255, 255, 255), outline=(226, 200, 150, 255), width=3)
    img.alpha_composite(logo, (int(W / 2 - lw / 2), int(H * 0.135 + 18)))
    d = ImageDraw.Draw(img)
    # 玻璃門
    d.rounded_rectangle([W * 0.30, H * 0.38, W * 0.70, H * 0.72], radius=10,
                        fill=(214, 228, 234, 255), outline=(190, 174, 148, 255), width=5)
    d.line([(W / 2, H * 0.38), (W / 2, H * 0.72)], fill=(190, 174, 148, 255), width=4)
    d.ellipse([W * 0.46 - 7, H * 0.55, W * 0.46 + 7, H * 0.55 + 14], fill=(200, 170, 110, 255))
    d.ellipse([W * 0.54 - 7, H * 0.55, W * 0.54 + 7, H * 0.55 + 14], fill=(200, 170, 110, 255))
    # 暖光
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    dg.ellipse([W * 0.30, H * 0.36, W * 0.70, H * 0.74], fill=(255, 236, 190, 70))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    # 水果們走向門(由前景走遠)
    prog = ease(p)
    scale = 1.0 - 0.42 * prog
    bounce = abs(math.sin(t * 6.5)) * 8 * scale
    base_y = H * 0.86 - (H * 0.86 - H * 0.66) * prog
    draw_fruit(img, "peach", W * 0.5, base_y - bounce, 130 * scale, mood="happy",
               wrinkle=0.9, t=t, leaf=True, lashes=True, seed=1)
    draw_fruit(img, "lemon", W * 0.5 - 190 * scale, base_y + 26 * scale - bounce * 0.7,
               76 * scale, mood="happy", wrinkle=0.9, t=t, seed=2)
    draw_fruit(img, "orange", W * 0.5 + 195 * scale, base_y + 30 * scale - bounce * 0.8,
               80 * scale, mood="happy", wrinkle=0.9, t=t, seed=3)
    caption(img, "來靚優，讓肌膚重新發光", sub="Dream-U Health Aesthetic Medicine Clinic")
    return img


def shot3(t, p):
    """治療：前段雷射掃過、後段金色注射澎潤。"""
    img = bg_vertical((250, 247, 244), (238, 230, 224))
    floor(img, H * 0.70)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([W * 0.06, H * 0.08, W * 0.32, H * 0.34], radius=14,
                        fill=(255, 250, 238, 255), outline=(226, 216, 205, 255), width=4)
    R = 240
    cx, cy = W / 2, H * 0.42
    laser_phase = clamp(p / 0.5)      # 0~0.5: 雷射
    inj_phase = clamp((p - 0.5) / 0.5)  # 0.5~1: 注射
    if inj_phase <= 0:
        # 雷射掃描：左皺右亮
        sweep = cx - R * 1.1 + (2.3 * R) * ease(laser_phase)
        wr = 1.0 - 0.35 * ease(laser_phase)
        draw_fruit(img, "peach", cx, cy, R, mood="happy", wrinkle=wr * 0.6,
                   gloss=1.0, t=t, leaf=True, lashes=True, split_x=sweep, seed=1)
        d = ImageDraw.Draw(img)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow)
        dg.ellipse([sweep - 55, cy - R - 40, sweep + 55, cy + R + 40], fill=(150, 210, 255, 60))
        dg.line([(sweep, cy - R - 30), (sweep, cy + R + 30)], fill=(235, 250, 255, 220), width=6)
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
        d = ImageDraw.Draw(img)
        # 雷射手持探頭(藍手套)
        hx, hy = sweep + 28, cy - R - 128
        d.rounded_rectangle([hx - 20, hy + 58, hx + 20, hy + 165], radius=16,
                            fill=(235, 240, 246, 255), outline=(205, 212, 222, 255), width=3)
        d.rounded_rectangle([hx - 28, hy + 156, hx + 28, hy + 186], radius=10,
                            fill=(90, 160, 220, 255))
        d.ellipse([hx - 42, hy - 8, hx + 42, hy + 82], fill=(70, 120, 200, 255))
        for k in range(4):
            d.rounded_rectangle([hx - 34 + k * 19, hy - 32, hx - 18 + k * 19, hy + 14],
                                radius=8, fill=(70, 120, 200, 255))
        lbl = "雷射煥膚"
    else:
        # 注射澎潤：皺紋撫平、體積回彈
        wr = 0.4 * (1 - ease(inj_phase))
        plump = 1.0 + 0.05 * math.sin(ease(inj_phase) * math.pi)
        draw_fruit(img, "peach", cx, cy, R * plump, mood="closed" if inj_phase < 0.7 else "happy",
                   wrinkle=wr, gloss=1.0, t=t, leaf=True, lashes=True, seed=1)
        d = ImageDraw.Draw(img)
        # 金色美膚筆(圓潤筆型,無尖針)
        pen_x = cx + R * 0.62
        pen_y = cy - R * 0.72
        ang = math.radians(38)
        px2 = pen_x + math.cos(ang) * 150
        py2 = pen_y - math.sin(ang) * 150
        d.line([(pen_x, pen_y), (px2, py2)], fill=(212, 175, 106, 255), width=26)
        d.line([(pen_x, pen_y), (px2, py2)], fill=(238, 210, 150, 255), width=14)
        d.ellipse([pen_x - 12, pen_y - 12, pen_x + 12, pen_y + 12], fill=(238, 210, 150, 255))
        # 金色精華漣漪
        for k in range(3):
            rr = (t * 90 + k * 40) % 130
            aa = int(160 * (1 - rr / 130))
            d.ellipse([pen_x - rr, pen_y - rr * 0.7, pen_x + rr, pen_y + rr * 0.7],
                      outline=(230, 190, 120, aa), width=4)
        # 金色小水滴吸收
        rng = random.Random(77)
        for i in range(8):
            ph = (t * 0.8 + i / 8.0) % 1.0
            dx = rng.uniform(-0.5, 0.5) * R
            gx = pen_x + (cx + dx - pen_x) * ph
            gy = pen_y + (cy - pen_y) * ph
            aa = int(220 * (1 - ph * 0.7))
            d.ellipse([gx - 7, gy - 9, gx + 7, gy + 9], fill=(240, 200, 120, aa))
            d.ellipse([gx - 3, gy - 5, gx + 1, gy - 1], fill=(255, 240, 200, aa))
        lbl = "注射澎潤"
    d = ImageDraw.Draw(img)
    rng2 = random.Random(int(t * 6))
    for _ in range(5):
        sparkle(d, rng2.uniform(cx - R, cx + R), rng2.uniform(cy - R, cy + R),
                rng2.uniform(8, 18), (255, 250, 235, 210))
    # 療程標籤
    f = font(30)
    d.rounded_rectangle([cx - 110, cy + R + 30, cx + 110, cy + R + 80], radius=14,
                        fill=(255, 255, 255, 185))
    b = d.textbbox((0, 0), lbl, font=f)
    d.text((cx - (b[2] - b[0]) / 2, cy + R + 38), lbl, font=f, fill=(184, 120, 90, 255))
    caption(img, "雷射煥膚 × 注射澎潤", small_note="療程效果因人而異")
    return img


def shot4(t, p):
    """蛻變：三顆水果光滑發亮、開心彈跳。"""
    img = bg_vertical((255, 244, 232), (250, 224, 200))
    floor(img, H * 0.70, (246, 228, 210, 255))
    d = ImageDraw.Draw(img)
    # 放射金光
    ray = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ray)
    for k in range(9):
        a0 = k * 40 + t * 12
        dr.polygon([(W / 2, H * 0.40),
                    (W / 2 + 900 * math.cos(math.radians(a0)), H * 0.40 + 900 * math.sin(math.radians(a0))),
                    (W / 2 + 900 * math.cos(math.radians(a0 + 9)), H * 0.40 + 900 * math.sin(math.radians(a0 + 9)))],
                   fill=(255, 226, 160, 26))
    img.alpha_composite(ray.filter(ImageFilter.GaussianBlur(3)))
    bounce = abs(math.sin(t * 5.2))
    draw_fruit(img, "peach", W * 0.5, H * 0.40 - bounce * 34, 180, mood="happy",
               wrinkle=0.0, gloss=1.0, t=t, leaf=True, lashes=True, seed=1)
    draw_fruit(img, "lemon", W * 0.16, H * 0.57 - abs(math.sin(t * 5.2 + 1.1)) * 26,
               102, mood="happy", wrinkle=0.0, gloss=1.0, t=t, seed=2)
    draw_fruit(img, "orange", W * 0.85, H * 0.58 - abs(math.sin(t * 5.2 + 2.2)) * 26,
               106, mood="wink" if (t % 2) > 1.2 else "happy", wrinkle=0.0, gloss=1.0,
               t=t, seed=3)
    d = ImageDraw.Draw(img)
    rng = random.Random(int(t * 8))
    for _ in range(10):
        sparkle(d, rng.uniform(30, W - 30), rng.uniform(H * 0.1, H * 0.72),
                rng.uniform(8, 24), (255, 246, 225, 220))
    caption(img, "皺皺 OUT・水光 ON", sub="澎潤透亮，重新發光", small_note="療程效果因人而異")
    return img


def shot5(t, p):
    """片尾卡：Logo + 醫師照 + 文案(沿用診所奶油金版式)。"""
    img = bg_vertical((252, 245, 232), (238, 219, 186))
    d = ImageDraw.Draw(img)
    fade = ease(p * 3.5)
    # Logo
    lw = int(W * 0.62)
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    if fade < 1:
        logo = logo.copy()
        logo.putalpha(logo.split()[3].point(lambda v: int(v * fade)))
    img.alpha_composite(logo, (int(W / 2 - lw / 2), int(H * 0.075)))
    # 醫師圓照 + 金環
    ds = int(430 * (0.85 + 0.15 * ease(p * 2.5)))
    doc = DOCTOR.resize((ds, ds), Image.LANCZOS)
    dy = int(H * 0.30)
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ring)
    dr.ellipse([W / 2 - ds / 2 - 10, dy - 10, W / 2 + ds / 2 + 10, dy + ds + 10],
               outline=(198, 162, 96, int(255 * fade)), width=6)
    dr.ellipse([W / 2 - ds / 2 - 3, dy - 3, W / 2 + ds / 2 + 3, dy + ds + 3],
               outline=(255, 252, 244, int(255 * fade)), width=3)
    if fade < 1:
        doc = doc.copy()
        doc.putalpha(doc.split()[3].point(lambda v: int(v * fade)))
    img.alpha_composite(doc, (int(W / 2 - ds / 2), dy))
    img.alpha_composite(ring)
    d = ImageDraw.Draw(img)
    # 文案
    a2 = int(255 * ease((p - 0.18) * 3))
    if a2 > 0:
        for i, (txt, fs, yy, col) in enumerate((
                ("撫平歲月痕跡", 58, H * 0.685, (110, 82, 52)),
                ("澎回青春光采", 58, H * 0.685 + 78, (110, 82, 52)),
                ("靚優健康醫學美容診所", 34, H * 0.685 + 190, (150, 118, 78)),
                ("Dream-U Health Aesthetic Medicine Clinic", 20, H * 0.685 + 244, (168, 140, 104)))):
            f = font(fs)
            b = d.textbbox((0, 0), txt, font=f)
            d.text((W / 2 - (b[2] - b[0]) / 2, yy), txt, font=f, fill=col + (a2,))
        f = font(22)
        note = "療程效果因人而異"
        b = d.textbbox((0, 0), note, font=f)
        d.text((W / 2 - (b[2] - b[0]) / 2, H - 52), note, font=f, fill=(160, 138, 110, a2))
    # 迷你水果觀眾
    if p > 0.25:
        aa = ease((p - 0.25) * 4)
        yb = H * 0.585 + (1 - aa) * 40
        draw_fruit(img, "peach", W * 0.24, yb, 46, mood="happy", gloss=1.0, t=t,
                   leaf=True, seed=1)
        draw_fruit(img, "orange", W * 0.76, yb + 4, 44, mood="wink", gloss=1.0, t=t, seed=3)
    # 飄落金粒
    rng = random.Random(42)
    for i in range(16):
        ph = (t * 0.12 + i / 16.0) % 1.0
        px = (rng.random() * W + math.sin(t + i) * 20) % W
        py = ph * H
        s = 4 + 6 * rng.random()
        sparkle(d, px, py, s, (222, 186, 120, 130))
    return img


SHOT_FN = [shot1, shot2, shot3, shot4, shot5]


def render_shot_frame(idx, gt):
    s0, s1 = SHOTS[idx]
    p = clamp((gt - s0) / (s1 - s0))
    return SHOT_FN[idx](gt, p).convert("RGB")


def frame_at(i):
    gt = i / FPS
    idx = len(SHOTS) - 1
    for k, (s0, s1) in enumerate(SHOTS):
        if s0 <= gt < s1:
            idx = k
            break
    img = render_shot_frame(idx, gt)
    if idx + 1 < len(SHOTS):
        nxt = SHOTS[idx][1]
        f_to_cut = int(nxt * FPS) - i
        if f_to_cut <= XFADE:
            a = 1 - f_to_cut / (XFADE + 1)
            img2 = render_shot_frame(idx + 1, nxt + 0.001)
            img = Image.blend(img, img2, a * 0.85)
    return img


# ---------------------------------------------------------------- audio
def make_audio(path):
    sr = 44100
    n = int(DUR * sr)
    t = np.arange(n) / sr
    out = np.zeros(n, np.float32)
    # 溫暖和弦 (C - Em/G - F - G - Am - F - C 每4秒)
    chords = [(261.63, 329.63, 392.0), (246.94, 329.63, 392.0),
              (220.0, 261.63, 349.23), (196.0, 293.66, 392.0),
              (220.0, 261.63, 329.63), (174.61, 261.63, 349.23),
              (261.63, 329.63, 523.25)]
    seg = 4.0
    for k in range(7):
        ch = chords[k]
        m = (t >= k * seg) & (t < (k + 1) * seg)
        tt = t[m] - k * seg
        env = np.clip(np.minimum(tt / 0.9, 1.0) * np.minimum((seg - tt) / 0.9, 1.0), 0, 1)
        for f in ch:
            out[m] += 0.045 * env * np.sin(2 * np.pi * f * tt) * \
                (0.8 + 0.2 * np.sin(2 * np.pi * 0.35 * tt))
    # 琶音 (第一段低落=慢,治療後轉輕快)
    penta = [523.25, 587.33, 659.25, 783.99, 880.0]
    rng = random.Random(21)
    tt0, k = 0.6, 0
    while tt0 < DUR - 1.2:
        speed = 0.66 if tt0 < 5 else (0.30 if tt0 > 16 else 0.45)
        f = penta[(k * 2 + (k // 3)) % 5] * (0.5 if tt0 < 5 else 1.0)
        i0 = int(tt0 * sr)
        td = np.arange(int(0.55 * sr)) / sr
        i1 = min(n, i0 + len(td))
        out[i0:i1] += 0.07 * np.exp(-td[:i1 - i0] * 4.5) * np.sin(2 * np.pi * f * td[:i1 - i0])
        tt0 += speed * (2 if rng.random() < 0.3 else 1)
        k += 1
    # 「叮」×2：雷射啟動(9.6s)、注射澎潤(12.9s);揭曉上行音階(16s)
    for t0, base in ((9.6, 1567.98), (12.9, 1760.0)):
        for f, amp in ((base, 0.26), (base * 2, 0.10)):
            i0 = int(t0 * sr)
            td = np.arange(int(1.8 * sr)) / sr
            i1 = min(n, i0 + len(td))
            out[i0:i1] += amp * np.exp(-td[:i1 - i0] * 2.8) * np.sin(2 * np.pi * f * td[:i1 - i0])
    for j, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
        i0 = int((16.0 + j * 0.12) * sr)
        td = np.arange(int(0.9 * sr)) / sr
        i1 = min(n, i0 + len(td))
        out[i0:i1] += 0.16 * np.exp(-td[:i1 - i0] * 3.5) * np.sin(2 * np.pi * f * td[:i1 - i0])
    # 片尾暖和弦
    i0 = int(20.0 * sr)
    td = np.arange(n - i0) / sr
    for f in (261.63, 329.63, 392.0, 523.25):
        out[i0:] += 0.05 * np.minimum(td / 1.5, 1.0) * np.sin(2 * np.pi * f * td)
    fade = int(1.6 * sr)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = np.clip(out / max(1.0, np.abs(out).max() / 0.85), -1, 1)
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())


# ---------------------------------------------------------------- main
def main():
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    wav = os.path.join(OUT_DIR, "_music2.wav")
    out = os.path.join(OUT_DIR, "dreamu_renewal_720x1280.mp4")
    print("生成配樂 ...")
    make_audio(wav)
    cmd = [ffmpeg, "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(N_FRAMES):
        proc.stdin.write(frame_at(i).tobytes())
        if i % 48 == 0:
            print(f"  frame {i}/{N_FRAMES}")
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("完成:", out)


if __name__ == "__main__":
    main()
