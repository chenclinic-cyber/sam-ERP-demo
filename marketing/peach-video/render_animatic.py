# -*- coding: utf-8 -*-
"""
水蜜桃醫美影片 — 分鏡動態草稿 (storyboard animatic) 渲染器
20 秒 / 9:16 (720x1280) / 24fps，五個分鏡對應企劃腳本。
用法: python3 render_animatic.py
輸出: peach_animatic_720x1280.mp4
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 720, 1280
FPS = 24
DUR = 20.0
N_FRAMES = int(DUR * FPS)
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

# 分鏡時間軸 (秒)
SHOTS = [(0, 4), (4, 8), (8, 13), (13, 16), (16, 20)]
XFADE = 6  # 轉場交疊幀數


def font(size):
    return ImageFont.truetype(FONT_PATH, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- body sprite
def make_body(size=900, glossy=False):
    """水蜜桃球體漸層 sprite(RGBA)。glossy=True 時飽和水光版。"""
    n = size
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cx = cy = n / 2.0
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / (n / 2.0)
    inside = r <= 1.0
    nz = np.sqrt(np.clip(1 - r * r, 0, 1))
    nx = (x - cx) / (n / 2.0)
    ny = (y - cy) / (n / 2.0)
    lx, ly, lz = -0.38, -0.5, 0.78
    lam = np.clip(nx * lx + ny * ly + nz * lz, 0, 1)
    ty = (y / n)
    top = np.array([255, 220, 182], np.float32)
    bot = np.array([252, 150, 142], np.float32)
    col = top[None, None, :] * (1 - ty)[..., None] + bot[None, None, :] * ty[..., None]
    shade = (0.80 + 0.20 * lam)[..., None]
    col = col * shade
    # 桃子縱向凹縫(subtle cleft)
    cleft = np.exp(-((x - cx - 0.06 * n * np.sin(ty * 2.2)) ** 2) / (2 * (0.018 * n) ** 2))
    cleft = cleft * np.clip(1.1 - ty * 1.2, 0, 1)
    col = col * (1 - 0.09 * cleft)[..., None]
    if glossy:
        h = np.clip(nx * -0.45 + ny * -0.6 + nz * 0.66, 0, 1) ** 18
        col = col + 190 * h[..., None]
        rim = np.clip(nx * 0.7 + nz * 0.1, 0, 1) ** 6
        col = col + 60 * rim[..., None] * np.array([255, 230, 220]) / 255.0
    col = np.clip(col, 0, 255)
    alpha = np.clip((1.0 - r) / 0.02, 0, 1) * 255
    out = np.dstack([col, alpha]).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    if glossy:
        img = ImageEnhance.Color(img).enhance(1.18)
    return img


BODY_MATTE = make_body(glossy=False)
BODY_GLOSS = make_body(glossy=True)


def sparkle(d, x, y, s, color=(255, 255, 255, 230)):
    d.polygon([(x - s, y), (x, y - s * 0.28), (x + s, y), (x, y + s * 0.28)], fill=color)
    d.polygon([(x, y - s), (x - s * 0.28, y), (x, y + s), (x + s * 0.28, y)], fill=color)


def draw_fuzz(d, cx, cy, R, amount, seed, x_max=None):
    """絨毛：輪廓短毛 + 體表細毛。x_max 之右不畫(供左右對比鏡)。"""
    rng = random.Random(seed)
    n_edge = int(150 * amount)
    for _ in range(n_edge):
        th = rng.uniform(0, 2 * math.pi)
        ex = cx + R * math.cos(th)
        ey = cy + R * math.sin(th)
        if x_max is not None and ex > x_max:
            continue
        ln = R * rng.uniform(0.045, 0.085)
        jt = rng.uniform(-0.25, 0.25)
        tx = ex + ln * math.cos(th + jt)
        ty = ey + ln * math.sin(th + jt)
        d.line([(ex, ey), (tx, ty)], fill=(255, 224, 198, 170), width=max(1, int(R * 0.008)))
    n_in = int(90 * amount)
    for _ in range(n_in):
        th = rng.uniform(0, 2 * math.pi)
        rr = R * math.sqrt(rng.uniform(0.05, 0.92))
        px = cx + rr * math.cos(th)
        py = cy + rr * math.sin(th)
        if x_max is not None and px > x_max:
            continue
        a = rng.uniform(-0.7, -0.2)
        ln = R * rng.uniform(0.03, 0.05)
        d.line([(px, py), (px + ln * math.cos(a), py + ln * math.sin(a))],
               fill=(255, 235, 215, 60), width=1)


def draw_leaf(layer, cx, cy, R, wiggle=0.0):
    d = ImageDraw.Draw(layer)
    sx, sy = cx + R * 0.10, cy - R * 0.97
    d.line([(sx, sy), (sx + R * 0.03, sy - R * 0.16)], fill=(122, 82, 52, 255),
           width=max(2, int(R * 0.035)))
    leaf = Image.new("RGBA", (int(R * 0.9), int(R * 0.5)), (0, 0, 0, 0))
    dl = ImageDraw.Draw(leaf)
    dl.ellipse([0, int(R * 0.06), int(R * 0.62), int(R * 0.40)], fill=(92, 168, 82, 255))
    dl.ellipse([int(R * 0.06), int(R * 0.10), int(R * 0.52), int(R * 0.32)], fill=(116, 196, 100, 255))
    leaf = leaf.rotate(28 + wiggle, expand=True, resample=Image.BICUBIC)
    layer.alpha_composite(leaf, (int(sx - R * 0.06), int(sy - R * 0.42)))


def draw_face(d, cx, cy, R, eyes="open", smile=1.0, goggles=False, shy=False):
    ew = R * 0.16
    eh = R * 0.145
    ey_ = cy - R * 0.10
    exl, exr = cx - R * 0.30, cx + R * 0.30
    if goggles:
        d.rounded_rectangle([cx - R * 0.52, ey_ - R * 0.16, cx + R * 0.52, ey_ + R * 0.14],
                            radius=R * 0.12, fill=(38, 38, 46, 255), outline=(90, 90, 105, 255),
                            width=max(2, int(R * 0.02)))
        d.line([(cx - R * 0.52, ey_ - R * 0.01), (cx - R * 0.95, ey_ - R * 0.06)],
               fill=(38, 38, 46, 255), width=max(3, int(R * 0.05)))
        d.line([(cx + R * 0.52, ey_ - R * 0.01), (cx + R * 0.95, ey_ - R * 0.06)],
               fill=(38, 38, 46, 255), width=max(3, int(R * 0.05)))
        d.ellipse([exl - ew * 0.5, ey_ - eh * 0.4, exl + ew * 0.5, ey_ + eh * 0.3],
                  fill=(120, 170, 210, 120))
        d.ellipse([exr - ew * 0.5, ey_ - eh * 0.4, exr + ew * 0.5, ey_ + eh * 0.3],
                  fill=(120, 170, 210, 120))
    else:
        for ex, side, closed in ((exl, -1, eyes in ("closed",)),
                                 (exr, 1, eyes in ("closed", "wink"))):
            # 眼影
            d.ellipse([ex - ew * 1.15, ey_ - eh * 1.5, ex + ew * 1.15, ey_ + eh * 0.2],
                      fill=(248, 170, 190, 90))
            if closed:
                d.arc([ex - ew, ey_ - eh * 0.4, ex + ew, ey_ + eh * 0.8], 20, 160,
                      fill=(70, 40, 40, 255), width=max(2, int(R * 0.022)))
            else:
                d.ellipse([ex - ew * 0.75, ey_ - eh, ex + ew * 0.75, ey_ + eh * 0.55],
                          fill=(66, 40, 40, 255))
                d.ellipse([ex - ew * 0.28, ey_ - eh * 0.72, ex + ew * 0.2, ey_ - eh * 0.1],
                          fill=(255, 255, 255, 235))
            # 睫毛
            for k, ang in enumerate((-55, -30, -8)):
                a = math.radians(ang if side > 0 else 180 - ang)
                bx = ex + side * ew * 0.62
                by = ey_ - eh * 0.55 + k * eh * 0.28
                d.line([(bx, by), (bx + math.cos(a) * ew * 0.85, by + math.sin(a) * ew * 0.85)],
                       fill=(60, 35, 35, 255), width=max(2, int(R * 0.018)))
        # 眉
        d.arc([exl - ew, ey_ - eh * 2.6, exl + ew, ey_ - eh * 0.9], 200, 330,
              fill=(150, 90, 70, 200), width=max(2, int(R * 0.014)))
        d.arc([exr - ew, ey_ - eh * 2.6, exr + ew, ey_ - eh * 0.9], 210, 340,
              fill=(150, 90, 70, 200), width=max(2, int(R * 0.014)))
    # 腮紅
    d.ellipse([cx - R * 0.62, cy + R * 0.05, cx - R * 0.36, cy + R * 0.20],
              fill=(255, 130, 140, 70))
    d.ellipse([cx + R * 0.36, cy + R * 0.05, cx + R * 0.62, cy + R * 0.20],
              fill=(255, 130, 140, 70))
    # 唇
    ly = cy + R * 0.30
    lw = R * 0.17
    if smile > 0.5:
        d.chord([cx - lw, ly - lw * 0.75, cx + lw, ly + lw * 0.75], 15, 165,
                fill=(232, 80, 110, 255))
        d.ellipse([cx - lw * 0.45, ly - lw * 0.05, cx - lw * 0.05, ly + lw * 0.28],
                  fill=(255, 175, 195, 200))
    else:
        d.ellipse([cx - lw * 0.7, ly - lw * 0.4, cx + lw * 0.7, ly + lw * 0.4],
                  fill=(232, 80, 110, 255))


def draw_legs(d, cx, cy, R, phase=0.0, walking=True):
    lw = max(4, int(R * 0.12))
    top = cy + R * 0.86
    for side in (-1, 1):
        lift = math.sin(phase + (0 if side < 0 else math.pi)) * (R * 0.10 if walking else 0)
        hx = cx + side * R * 0.32
        ky = top + R * 0.42 - lift * 0.5
        fy = top + R * 0.88 - max(0, lift)
        kx = hx + side * R * 0.03 + (lift * 0.3 if walking else 0)
        d.line([(hx, top), (kx, ky)], fill=(250, 205, 175, 255), width=lw)
        d.line([(kx, ky), (kx, fy)], fill=(250, 205, 175, 255), width=lw)
        # 粉色高跟鞋
        d.polygon([(kx - lw * 0.7, fy - lw * 0.3), (kx + lw * 1.7, fy + lw * 0.15),
                   (kx + lw * 1.5, fy + lw * 0.7), (kx - lw * 0.6, fy + lw * 0.7)],
                  fill=(240, 96, 140, 255))
        d.line([(kx - lw * 0.35, fy + lw * 0.7), (kx - lw * 0.35, fy + lw * 1.35)],
               fill=(240, 96, 140, 255), width=max(2, int(lw * 0.3)))


def draw_coat(d, cx, cy, R):
    """粉色皮草外套：身體兩側+肩的蓬鬆泡泡。"""
    rng = random.Random(7)
    for side in (-1, 1):
        for k in range(9):
            t = k / 8.0
            th = math.pi * (0.62 + 0.75 * t) * side * -1 + (math.pi if side < 0 else 0)
            bx = cx + side * (R * 1.02) * math.cos(0.35 + t * 1.9) * 0.9
            by = cy - R * 0.75 + t * R * 1.55
            rr = R * rng.uniform(0.16, 0.24)
            d.ellipse([bx + side * R * 0.12 - rr, by - rr, bx + side * R * 0.12 + rr, by + rr],
                      fill=(250, 178, 200, 255))
            d.ellipse([bx + side * R * 0.12 - rr * 0.55, by - rr * 0.55,
                       bx + side * R * 0.12 + rr * 0.1, by + rr * 0.1],
                      fill=(255, 205, 220, 255))
    # 領口
    for k in range(6):
        bx = cx - R * 0.62 + k * R * 0.25
        by = cy - R * 0.86 + math.sin(k * 1.2) * R * 0.03
        rr = R * 0.15
        d.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=(255, 195, 214, 255))


def draw_handbag(d, cx, cy, R):
    hx, hy = cx + R * 1.12, cy + R * 0.72
    d.arc([hx - R * 0.16, hy - R * 0.26, hx + R * 0.16, hy + R * 0.05], 180, 360,
          fill=(190, 150, 90, 255), width=max(2, int(R * 0.03)))
    d.rounded_rectangle([hx - R * 0.22, hy - R * 0.05, hx + R * 0.22, hy + R * 0.28],
                        radius=R * 0.06, fill=(236, 205, 170, 255),
                        outline=(200, 165, 120, 255), width=2)
    d.ellipse([hx - R * 0.03, hy + R * 0.02, hx + R * 0.03, hy + R * 0.08],
              fill=(212, 175, 96, 255))


def paste_body(img, cx, cy, R, gloss=0.0, split_x=None):
    """貼上身體。split_x: 左霧面右水光的左右對比。"""
    size = int(R * 2)
    matte = BODY_MATTE.resize((size, size), Image.LANCZOS)
    if gloss <= 0 and split_x is None:
        img.alpha_composite(matte, (int(cx - R), int(cy - R)))
        return
    glossb = BODY_GLOSS.resize((size, size), Image.LANCZOS)
    if split_x is None:
        body = Image.blend(matte, glossb, clamp(gloss))
        img.alpha_composite(body, (int(cx - R), int(cy - R)))
        return
    # 對比：mask 左=matte
    body = glossb.copy()
    cut = int(clamp((split_x - (cx - R)) / (2 * R)) * size)
    if cut > 0:
        left = matte.crop((0, 0, cut, size))
        body.paste(left, (0, 0), left)
    img.alpha_composite(body, (int(cx - R), int(cy - R)))


def draw_peach(img, cx, cy, R, t, fuzz=1.0, gloss=0.0, eyes="open", smile=1.0,
               goggles=False, coat=False, bag=False, legs=True, walk=True,
               leaf_wiggle=0.0, split_x=None, seed=0):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if legs:
        draw_legs(d, cx, cy, R, phase=t * 7.0, walking=walk)
    if coat:
        draw_coat(d, cx, cy, R)
    paste_body(layer, cx, cy, R, gloss=gloss, split_x=split_x)
    if fuzz > 0.02:
        draw_fuzz(d, cx, cy, R, fuzz, seed=seed + int(t * 12) // 1, x_max=split_x)
    draw_leaf(layer, cx, cy, R, wiggle=leaf_wiggle)
    d2 = ImageDraw.Draw(layer)
    draw_face(d2, cx, cy, R, eyes=eyes, smile=smile, goggles=goggles)
    if bag:
        draw_handbag(d2, cx, cy, R)
    img.alpha_composite(layer)


# ---------------------------------------------------------------- backgrounds
def bg_vertical(c_top, c_bot):
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = np.array(c_top, np.float32)[None, None, :] * (1 - g) + \
        np.array(c_bot, np.float32)[None, None, :] * g
    arr = np.repeat(arr, W, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


BG_HALL = None


def bg_hallway():
    global BG_HALL
    if BG_HALL is not None:
        return BG_HALL.copy()
    img = bg_vertical((246, 238, 228), (232, 218, 205))
    d = ImageDraw.Draw(img)
    horizon = H * 0.55
    # 大理石地板
    d.rectangle([0, horizon, W, H], fill=(238, 232, 226, 255))
    for k in range(-6, 8):
        x0 = W / 2 + k * 60
        x1 = W / 2 + k * 340
        d.line([(x0, horizon), (x1, H)], fill=(215, 206, 200, 255), width=2)
    for k in range(5):
        yy = horizon + (H - horizon) * (k / 5.0) ** 1.7
        d.line([(0, yy), (W, yy)], fill=(219, 210, 204, 255), width=2)
    # 木質雙開門
    dw, dh = W * 0.30, H * 0.30
    d.rounded_rectangle([W / 2 - dw, horizon - dh, W / 2 + dw, horizon + 6], radius=8,
                        fill=(158, 116, 82, 255), outline=(120, 86, 58, 255), width=4)
    d.line([(W / 2, horizon - dh), (W / 2, horizon)], fill=(120, 86, 58, 255), width=4)
    d.ellipse([W / 2 - 18, horizon - dh * 0.45, W / 2 - 8, horizon - dh * 0.45 + 10],
              fill=(230, 200, 120, 255))
    d.ellipse([W / 2 + 8, horizon - dh * 0.45, W / 2 + 18, horizon - dh * 0.45 + 10],
              fill=(230, 200, 120, 255))
    # 壁燈暖光
    for sx in (W * 0.12, W * 0.88):
        d.ellipse([sx - 26, horizon - dh * 0.9 - 26, sx + 26, horizon - dh * 0.9 + 26],
                  fill=(255, 232, 180, 120))
        d.ellipse([sx - 12, horizon - dh * 0.9 - 12, sx + 12, horizon - dh * 0.9 + 12],
                  fill=(255, 246, 220, 255))
    # 模糊接待櫃台(右側)
    desk = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(desk)
    dd.rounded_rectangle([W * 0.68, horizon - 70, W * 1.05, horizon + 60], radius=18,
                         fill=(205, 178, 152, 255))
    dd.ellipse([W * 0.78, horizon - 150, W * 0.90, horizon - 80], fill=(150, 190, 140, 255))
    desk = desk.filter(ImageFilter.GaussianBlur(7))
    img.alpha_composite(desk)
    BG_HALL = img
    return img.copy()


def bg_room(warm=False):
    img = bg_vertical((250, 247, 244), (238, 230, 224)) if not warm else \
        bg_vertical((252, 242, 230), (244, 224, 208))
    d = ImageDraw.Draw(img)
    d.rectangle([0, H * 0.62, W, H], fill=(235, 229, 224, 255))
    d.line([(0, H * 0.62), (W, H * 0.62)], fill=(220, 212, 206, 255), width=3)
    # 窗光
    d.rounded_rectangle([W * 0.06, H * 0.08, W * 0.34, H * 0.36], radius=14,
                        fill=(255, 250, 238, 255), outline=(226, 216, 205, 255), width=4)
    return img


def draw_laser_device(d, x, y, s=1.0):
    d.rounded_rectangle([x, y, x + 150 * s, y + 260 * s], radius=16 * s,
                        fill=(240, 242, 246, 255), outline=(205, 210, 218, 255), width=3)
    d.rounded_rectangle([x + 18 * s, y + 22 * s, x + 132 * s, y + 96 * s], radius=8 * s,
                        fill=(40, 60, 90, 255))
    for k in range(4):
        px = x + 28 * s + k * 24 * s
        d.line([(px, y + 80 * s), (px, y + 80 * s - (18 + 14 * math.sin(k * 2.1)) * s)],
               fill=(120, 200, 255, 255), width=max(2, int(4 * s)))
    d.ellipse([x + 30 * s, y + 130 * s, x + 52 * s, y + 152 * s], fill=(120, 210, 170, 255))
    d.ellipse([x + 66 * s, y + 130 * s, x + 88 * s, y + 152 * s], fill=(250, 200, 120, 255))


def caption(img, text, sub=None, y=None, small_note=None):
    d = ImageDraw.Draw(img)
    y = y if y is not None else H - 210
    f1 = font(52)
    bbox = d.textbbox((0, 0), text, font=f1)
    tw = bbox[2] - bbox[0]
    # 底板
    d.rounded_rectangle([W / 2 - tw / 2 - 28, y - 16, W / 2 + tw / 2 + 28, y + 76],
                        radius=18, fill=(255, 255, 255, 175))
    d.text((W / 2 - tw / 2, y), text, font=f1, fill=(120, 62, 66, 255))
    if sub:
        f2 = font(30)
        b2 = d.textbbox((0, 0), sub, font=f2)
        d.text((W / 2 - (b2[2] - b2[0]) / 2, y + 92), sub, font=f2, fill=(150, 105, 100, 255))
    if small_note:
        f3 = font(22)
        b3 = d.textbbox((0, 0), small_note, font=f3)
        d.text((W / 2 - (b3[2] - b3[0]) / 2, H - 46), small_note, font=f3,
               fill=(140, 120, 115, 220))
    # 角落標籤
    f4 = font(20)
    d.text((W - 205, 24), "Storyboard Animatic", font=f4, fill=(160, 140, 135, 170))


# ---------------------------------------------------------------- shots
def shot1(t, p):
    """自信進場：走廊正面跟拍，鏡頭後退(人物放大)。"""
    img = bg_hallway()
    R = 150 + 60 * ease(p)
    sway = math.sin(t * 7.0) * R * 0.06
    cx = W / 2 + sway
    cy = H * 0.52 - R * 0.1 + abs(math.sin(t * 7.0)) * R * 0.03
    draw_peach(img, cx, cy, R, t, fuzz=1.0, gloss=0.0, eyes="open", smile=1.0,
               coat=True, bag=True, walk=True, leaf_wiggle=math.sin(t * 5) * 6, seed=1)
    caption(img, "毛毛的困擾，交給我們", sub="Dream-U 靚優健康醫學美容診所")
    return img


def shot2(t, p):
    """諮詢躺床：戴護目鏡放鬆躺床，鏡頭緩慢推近。"""
    img = bg_room()
    d = ImageDraw.Draw(img)
    zoom = 1.0 + 0.35 * ease(p)
    # 治療床
    bx0, bx1 = W * 0.08, W * 0.92
    by = H * 0.62
    d.rounded_rectangle([bx0, by - 26 * zoom, bx1, by + 60 * zoom], radius=26,
                        fill=(252, 252, 253, 255), outline=(222, 222, 228, 255), width=3)
    d.rectangle([bx0 + 30, by + 60 * zoom, bx0 + 54, by + 150], fill=(200, 200, 206, 255))
    d.rectangle([bx1 - 54, by + 60 * zoom, bx1 - 30, by + 150], fill=(200, 200, 206, 255))
    d.rounded_rectangle([bx0 + 14, by - 44 * zoom, bx0 + 150, by - 2], radius=16,
                        fill=(245, 246, 250, 255))  # 枕頭
    draw_laser_device(d, W * 0.70, H * 0.24, s=1.0)
    # 躺著的桃子(旋轉90度)
    R = int(120 * zoom)
    ply = Image.new("RGBA", (R * 5, R * 5), (0, 0, 0, 0))
    draw_peach(ply, R * 2.5, R * 2.2, R, t, fuzz=1.0, eyes="open", smile=1.0,
               goggles=True, legs=True, walk=False, seed=2)
    ply = ply.rotate(-78, resample=Image.BICUBIC, expand=False)
    img.alpha_composite(ply, (int(W * 0.36 - R * 2.5), int(by - R * 2.9)))
    # 特寫圓框：絨毛肌
    if p > 0.35:
        a = ease((p - 0.35) / 0.3)
        ins_r = 130
        ix, iy = W * 0.72, H * 0.685
        ins = Image.new("RGBA", (ins_r * 2 + 8, ins_r * 2 + 8), (0, 0, 0, 0))
        di = ImageDraw.Draw(ins)
        di.ellipse([4, 4, ins_r * 2 + 4, ins_r * 2 + 4], fill=(252, 190, 168, 255),
                   outline=(255, 255, 255, 255), width=6)
        rng = random.Random(9 + int(t * 10))
        for _ in range(90):
            px = rng.uniform(0.15, 1.85) * ins_r
            py = rng.uniform(0.15, 1.85) * ins_r
            if (px - ins_r) ** 2 + (py - ins_r) ** 2 < (ins_r * 0.92) ** 2:
                aa = rng.uniform(-1.2, -0.4)
                ll = rng.uniform(8, 16)
                di.line([(px, py), (px + ll * math.cos(aa), py + ll * math.sin(aa))],
                        fill=(255, 232, 210, 210), width=2)
        ins.putalpha(ins.split()[3].point(lambda v: int(v * a)))
        img.alpha_composite(ins, (int(ix - ins_r), int(iy - ins_r)))
        dm = ImageDraw.Draw(img)
        fm = font(26)
        dm.text((ix - 92, iy + ins_r + 8), "細毛看得一清二楚",
                font=fm, fill=(150, 105, 100, int(255 * a)))
    caption(img, "專業評估・安心舒適", small_note="療程效果因人而異")
    return img


def shot3(t, p):
    """核心蛻變：雷射掃過，左絨毛右水光的對比。"""
    img = bg_room()
    d = ImageDraw.Draw(img)
    R = 250
    cx, cy = W / 2, H * 0.46
    sweep = cx - R * 1.1 + (2.35 * R) * ease(p * 1.05)
    draw_peach(img, cx, cy, R, t, fuzz=1.0, gloss=1.0, eyes="open", smile=1.0,
               legs=True, walk=False, split_x=sweep, seed=3)
    d = ImageDraw.Draw(img)
    # 飄散的絨毛微粒(掃過側)
    rng = random.Random(33)
    for i in range(46):
        life = (t * 0.9 + rng.random()) % 1.0
        px0 = cx - R + rng.random() * 2 * R
        if px0 > sweep - R * 0.05:
            continue
        px = px0 + life * 60 * (0.5 + rng.random())
        py = cy - R * rng.uniform(-0.9, 0.9) - life * 140
        al = int(150 * (1 - life))
        d.line([(px, py), (px + 7, py - 5)], fill=(255, 236, 214, al), width=2)
    # 雷射光暈與探頭
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    dg.ellipse([sweep - 55, cy - R - 40, sweep + 55, cy + R + 40], fill=(150, 210, 255, 60))
    dg.ellipse([sweep - 26, cy - R - 15, sweep + 26, cy + R + 15], fill=(200, 235, 255, 90))
    dg.line([(sweep, cy - R - 30), (sweep, cy + R + 30)], fill=(235, 250, 255, 220), width=6)
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)
    # 藍手套手 + 探頭
    hx = sweep + 30
    hy = cy - R - 130
    d.rounded_rectangle([hx - 22, hy + 60, hx + 22, hy + 170], radius=18,
                        fill=(235, 240, 246, 255), outline=(205, 212, 222, 255), width=3)
    d.rounded_rectangle([hx - 30, hy + 160, hx + 30, hy + 190], radius=10,
                        fill=(90, 160, 220, 255))
    d.ellipse([hx - 44, hy - 10, hx + 44, hy + 84], fill=(70, 120, 200, 255))
    for k in range(4):
        d.rounded_rectangle([hx - 36 + k * 20, hy - 34, hx - 20 + k * 20, hy + 16],
                            radius=8, fill=(70, 120, 200, 255))
    # 掃過側閃亮
    rng2 = random.Random(int(t * 6))
    for _ in range(6):
        sx = rng2.uniform(sweep + 20, min(cx + R * 0.95, W - 10))
        sy = rng2.uniform(cy - R * 0.8, cy + R * 0.8)
        if sx > sweep + 10:
            sparkle(d, sx, sy, rng2.uniform(8, 20))
    # 對比標籤
    fm = font(30)
    if p > 0.25:
        d.rounded_rectangle([cx - R + 4, cy + R + 26, cx - 20, cy + R + 74], radius=12,
                            fill=(255, 255, 255, 170))
        d.text((cx - R + 28, cy + R + 32), "絨毛肌", font=fm, fill=(150, 110, 100, 255))
        d.rounded_rectangle([cx + 20, cy + R + 26, cx + R - 4, cy + R + 74], radius=12,
                            fill=(255, 255, 255, 170))
        d.text((cx + 58, cy + R + 32), "水光肌", font=fm, fill=(214, 92, 120, 255))
    caption(img, "雷射除毛・蛻變開始", small_note="療程效果因人而異")
    return img


def shot4(t, p):
    """保養按摩：雙手塗抹精華，水光感，閉眼享受。"""
    img = bg_room(warm=True)
    R = 265
    cx, cy = W / 2, H * 0.44
    drift = math.sin(t * 1.5) * 8
    draw_peach(img, cx + drift * 0.3, cy, R, t, fuzz=0.0, gloss=1.0, eyes="closed",
               smile=1.0, legs=True, walk=False, seed=4)
    d = ImageDraw.Draw(img)
    # 按摩的藍手套雙手(圓周運動)
    for side in (-1, 1):
        ph = t * 2.2 + (0 if side < 0 else math.pi * 0.9)
        hx = cx + side * R * 0.78 + math.cos(ph) * R * 0.10
        hy = cy + R * 0.12 + math.sin(ph) * R * 0.14
        d.ellipse([hx - 52, hy - 40, hx + 52, hy + 48], fill=(70, 120, 200, 255))
        for k in range(4):
            fx = hx - 40 + k * 26
            d.rounded_rectangle([fx, hy - 66, fx + 20, hy - 10], radius=9,
                                fill=(70, 120, 200, 255))
    # 精華液滴與光澤
    rng = random.Random(5)
    for i in range(10):
        ph = (t * 0.5 + i / 10.0) % 1.0
        px = cx + math.cos(i * 2.4) * R * 0.7
        py = cy + math.sin(i * 1.7) * R * 0.55 + ph * 26
        rr = 6 + 5 * math.sin(i * 3.0)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(255, 255, 255, 90))
        d.ellipse([px - rr * 0.4, py - rr * 0.5, px, py], fill=(255, 255, 255, 160))
    for _ in range(5):
        sparkle(d, rng.uniform(cx - R, cx + R), rng.uniform(cy - R, cy + R * 0.8),
                rng.uniform(10, 22), (255, 250, 240, 200))
    caption(img, "術後保養・水嫩加倍", small_note="療程效果因人而異")
    return img


def shot5(t, p):
    """結尾亮相：金色光線，回眸眨眼，撥葉子。"""
    img = bg_vertical((255, 236, 200), (250, 205, 170))
    d = ImageDraw.Draw(img)
    # 門框金光
    d.rectangle([W * 0.16, H * 0.10, W * 0.84, H * 0.72], fill=(255, 248, 224, 255))
    d.rectangle([W * 0.16, H * 0.10, W * 0.84, H * 0.72], outline=(226, 186, 130, 255), width=10)
    ray = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ray)
    for k in range(7):
        a0 = -90 + k * 12 - 36
        dr.polygon([(W / 2, H * 0.40),
                    (W / 2 + 900 * math.cos(math.radians(a0)), H * 0.40 + 900 * math.sin(math.radians(a0))),
                    (W / 2 + 900 * math.cos(math.radians(a0 + 6)), H * 0.40 + 900 * math.sin(math.radians(a0 + 6)))],
                   fill=(255, 226, 160, 40))
    img.alpha_composite(ray.filter(ImageFilter.GaussianBlur(4)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, H * 0.72, W, H], fill=(238, 214, 190, 255))
    # 眨眼與撥葉子時機
    wink = "wink" if 0.45 < p < 0.72 else "open"
    wig = math.sin(t * 9) * 14 if 0.3 < p < 0.5 else math.sin(t * 3) * 4
    R = 210 - 30 * ease(max(0, (p - 0.75) / 0.25))
    cx = W / 2 + ease(max(0, (p - 0.75) / 0.25)) * W * 0.35
    cy = H * 0.44
    draw_peach(img, cx, cy, R, t, fuzz=0.0, gloss=1.0, eyes=wink, smile=1.0,
               bag=True, legs=True, walk=p > 0.7, leaf_wiggle=wig, seed=5)
    d = ImageDraw.Draw(img)
    rng = random.Random(int(t * 8))
    for _ in range(7):
        sparkle(d, rng.uniform(cx - R * 1.3, cx + R * 1.3),
                rng.uniform(cy - R * 1.3, cy + R * 1.1), rng.uniform(8, 24),
                (255, 245, 225, 220))
    caption(img, "換一層肌，換一種自信",
            sub="Dream-U 靚優健康醫學美容診所",
            small_note="療程效果因人而異")
    return img


SHOT_FN = [shot1, shot2, shot3, shot4, shot5]


def render_shot_frame(idx, gt):
    s0, s1 = SHOTS[idx]
    t = gt - s0
    p = clamp(t / (s1 - s0))
    return SHOT_FN[idx](gt, p).convert("RGB")


def frame_at(i):
    gt = i / FPS
    idx = 0
    for k, (s0, s1) in enumerate(SHOTS):
        if s0 <= gt < s1:
            idx = k
            break
    else:
        idx = len(SHOTS) - 1
    img = render_shot_frame(idx, gt)
    # 交疊轉場
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
    # 溫暖 pad 和弦進行 (C - Am7 - F - G 循環)
    chords = [(261.63, 329.63, 392.0), (220.0, 261.63, 329.63),
              (174.61, 220.0, 261.63), (196.0, 246.94, 293.66)]
    seg = DUR / 5.0
    for k in range(5):
        ch = chords[k % 4]
        m = (t >= k * seg) & (t < (k + 1) * seg)
        tt = t[m] - k * seg
        env = np.minimum(tt / 0.8, 1.0) * np.minimum((seg - tt) / 0.8, 1.0)
        env = np.clip(env, 0, 1)
        for f in ch:
            out[m] += 0.05 * env * np.sin(2 * np.pi * f * tt) * \
                (0.8 + 0.2 * np.sin(2 * np.pi * 0.4 * tt))
    # 輕快 spa 琶音 (五聲音階撥奏)
    penta = [523.25, 587.33, 659.25, 783.99, 880.0]
    beat = 60.0 / 100.0 / 2.0
    rng = random.Random(11)
    k = 0
    tt0 = 0.4
    while tt0 < DUR - 1.0:
        f = penta[(k * 2 + (k // 3)) % 5]
        i0 = int(tt0 * sr)
        dur_n = int(0.5 * sr)
        i1 = min(n, i0 + dur_n)
        td = np.arange(i1 - i0) / sr
        out[i0:i1] += 0.075 * np.exp(-td * 5.0) * np.sin(2 * np.pi * f * td)
        tt0 += beat * (2 if rng.random() < 0.4 else 1)
        k += 1
    # 「叮」— 蛻變瞬間 (10 秒，Shot 3 中段)
    for f, amp in ((1567.98, 0.30), (3135.96, 0.12)):
        i0 = int(10.0 * sr)
        td = np.arange(int(2.0 * sr)) / sr
        i1 = min(n, i0 + len(td))
        out[i0:i1] += amp * np.exp(-td[:i1 - i0] * 2.6) * np.sin(2 * np.pi * f * td[:i1 - i0])
    # 淡入淡出
    fade = int(1.2 * sr)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = np.clip(out / max(1.0, np.abs(out).max() / 0.85), -1, 1)
    pcm = (out * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(stereo.tobytes())


# ---------------------------------------------------------------- main
def main():
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    wav = os.path.join(OUT_DIR, "_music.wav")
    out = os.path.join(OUT_DIR, "peach_animatic_720x1280.mp4")
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
        img = frame_at(i)
        proc.stdin.write(img.tobytes())
        if i % 48 == 0:
            print(f"  frame {i}/{N_FRAMES}")
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("完成:", out)


if __name__ == "__main__":
    main()
