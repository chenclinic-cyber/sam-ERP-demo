# -*- coding: utf-8 -*-
"""
「皺皺水果重生記」寫實 3D 版 — 靚優煥膚短影音
28 秒 / 9:16 (720x1280) / 24fps
逐像素光照渲染(法線皺紋、絨毛絲絨光、水光高光)，非卡通風。
需要 assets/logo.png 與 assets/doctor.jpg
用法: python3 render_realistic.py
輸出: dreamu_renewal_3d_720x1280.mp4
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 720, 1280
FPS = 24
DUR = 28.0
N_FRAMES = int(DUR * FPS)
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

SHOTS = [(0, 5), (5, 9), (9, 16), (16, 20), (20, 28)]
XFADE = 7


def font(size):
    return ImageFont.truetype(FONT_PATH, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def smoothstep_np(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- assets
def load_logo():
    im = Image.open(os.path.join(OUT_DIR, "assets/logo.png")).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    lum = arr[..., :3].mean(axis=2)
    arr[..., 3] = np.clip((250 - lum) / 14.0, 0, 1) * 255
    im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return im.crop(im.getbbox())


def load_doctor(circle_d=560):
    im = Image.open(os.path.join(OUT_DIR, "assets/doctor.jpg")).convert("RGB")
    w, h = im.size
    side = w  # 取全寬,臉在圓內佔比較小
    cx, cy = w // 2, int(h * 0.32)
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


# ---------------------------------------------------------------- 寫實水果渲染器
class Fruit:
    """
    球體/橢球逐像素光照。紋理以 (u,v) 球面映射、u 方向可旋轉。
    皺紋 = 週期性扭曲脊線高度場 → 螢幕空間梯度擾動法線。
    """

    def __init__(self, kind, seed=0):
        self.kind = kind
        rng = np.random.default_rng(seed)
        tw, th = 1024, 512
        u = np.linspace(0, 1, tw, endpoint=False)[None, :]
        v = np.linspace(0, 1, th)[:, None]
        # u 方向週期性的扭曲場(無接縫)
        warp = (1.2 * np.sin(2 * np.pi * (u * 3) + 4.0 * v + 1.7)
                + 0.8 * np.sin(2 * np.pi * (u * 7) + 2.5 * v + 0.3)
                + 0.5 * np.sin(2 * np.pi * (u * 13) + 5.0 * v + 2.1))
        # 乾皺脊線(縱向為主)
        ridges = np.abs(np.sin(np.pi * (u * 11 + 0.55 * warp))) ** 1.3
        ridges = ridges * (0.65 + 0.35 * np.sin(2 * np.pi * v * 4 + 1.3 * warp))
        cross = np.abs(np.sin(np.pi * (v * 6 + 0.45 * warp))) ** 1.8
        self.wr_h = (0.85 * ridges + 0.16 * cross).astype(np.float32)
        # 細粒表皮(毛孔/斑點)
        spk = rng.random((th, tw)).astype(np.float32)
        spk_img = Image.fromarray((spk * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(1.1))
        self.pore = (np.asarray(spk_img, np.float32) / 255.0 - 0.5)
        # 紅暈斑塊(albedo 變化)
        blush = (0.5 + 0.5 * np.sin(2 * np.pi * u * 2 + 3.1 * v + 0.9)
                 + 0.5 * np.sin(2 * np.pi * u * 5 + 1.2 * v + 2.2)) / 1.5
        blush_img = Image.fromarray((np.clip(blush, 0, 1) * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(10))
        self.blush = np.asarray(blush_img, np.float32) / 255.0
        if kind == "peach":
            self.c_lo = np.array([255, 214, 150], np.float32) / 255
            self.c_hi = np.array([233, 96, 92], np.float32) / 255
            self.pore_amp = 0.03
            self.stretch = (1.0, 1.0)
        elif kind == "lemon":
            self.c_lo = np.array([250, 235, 160], np.float32) / 255
            self.c_hi = np.array([238, 195, 60], np.float32) / 255
            self.pore_amp = 0.10
            self.stretch = (1.22, 0.88)
        else:  # orange
            self.c_lo = np.array([255, 200, 110], np.float32) / 255
            self.c_hi = np.array([240, 140, 40], np.float32) / 255
            self.pore_amp = 0.14
            self.stretch = (1.0, 0.97)

    def render(self, R, wrinkle=0.0, gloss=0.0, rot=0.0, sweep=None,
               light=(-0.45, -0.38, 0.81), warm=0.0):
        """回傳 RGBA PIL Image。sweep∈[-1.4,1.4]: 左皺右亮分界(螢幕x/R)。"""
        sx, sy = self.stretch
        w, h = int(2 * R * sx), int(2 * R * sy)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        x = (xx - w / 2) / (R * sx)
        y = (yy - h / 2) / (R * sy)
        r2 = x * x + y * y
        mask = r2 <= 1.0
        nz = np.sqrt(np.clip(1 - r2, 0, 1))
        # 球面 UV
        u = (np.arctan2(x, np.maximum(nz, 1e-4)) / math.pi) * 0.5 + 0.5 + rot
        v = np.clip(y * 0.5 + 0.5, 0, 1)
        th, tw = self.wr_h.shape
        ui = ((u % 1.0) * (tw - 1)).astype(np.int32)
        vi = (v * (th - 1)).astype(np.int32)
        hgt = self.wr_h[vi, ui]
        pore = self.pore[vi, ui]
        blush = self.blush[vi, ui]
        # 皺紋強度場(可依 sweep 左右分區)
        if sweep is None:
            wamp = np.full_like(hgt, wrinkle)
            gamp = np.full_like(hgt, gloss)
        else:
            m = smoothstep_np((x - sweep) / 0.16 + 0.5)  # 右=1
            wamp = wrinkle * (1 - m)
            gamp = gloss * m
        # 法線擾動(皺紋+毛孔)
        gy_, gx_ = np.gradient(hgt)
        py_, px_ = np.gradient(pore)
        k = 5.2
        nx = x - k * (wamp * gx_ + self.pore_amp * px_ * (1 - 0.6 * gamp))
        ny = y - k * (wamp * gy_ + self.pore_amp * py_ * (1 - 0.6 * gamp))
        nl = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
        nx, ny, nzn = nx / nl, ny / nl, nz / nl
        # albedo
        base = self.c_lo[None, None] * (1 - blush)[..., None] + \
            self.c_hi[None, None] * blush[..., None]
        vgrad = (0.92 + 0.14 * (1 - v))[..., None]
        alb = base * vgrad
        if self.kind == "peach":
            cleft = np.exp(-((u % 1.0 - 0.5 - 0.02 * np.sin(v * 3)) ** 2) / (2 * 0.012 ** 2))
            alb = alb * (1 - 0.22 * cleft * (1 - v * 0.5))[..., None]
        # 老化:褐化+去飽和+縫隙陰影
        dullness = np.clip(wamp / max(wrinkle, 1e-6), 0, 1) * clamp(wrinkle) if wrinkle > 0 else 0
        if wrinkle > 0:
            gray = alb.mean(axis=2, keepdims=True)
            brown = np.array([0.64, 0.48, 0.44], np.float32)[None, None]
            aged = (alb * 0.55 + gray * 0.45) * brown / 0.55
            dd = (dullness * 0.85)[..., None] if isinstance(dullness, np.ndarray) else dullness * 0.85
            alb = alb * (1 - dd) + aged * dd
            alb = alb * (1 - 0.38 * (wamp * hgt))[..., None]
        # 光照
        L = np.array(light, np.float32)
        L = L / np.linalg.norm(L)
        diff = np.clip(nx * L[0] + ny * L[1] + nzn * L[2], 0, 1)
        Hv = L + np.array([0, 0, 1], np.float32)
        Hv = Hv / np.linalg.norm(Hv)
        ndh = np.clip(nx * Hv[0] + ny * Hv[1] + nzn * Hv[2], 0, 1)
        spec_p = 22 + 130 * gamp
        spec_i = 0.10 + 1.15 * gamp
        spec = spec_i * ndh ** spec_p
        # 桃子絨毛=絲絨邊緣光(乾皺時較啞)
        velvet = (1 - nz) ** 2.6 * (0.42 if self.kind == "peach" else 0.18)
        velvet = velvet * (1 - 0.7 * gamp)
        rim = (1 - nz) ** 3.2 * 0.28
        amb = 0.34
        col = alb * (amb + 0.88 * diff)[..., None]
        col += np.array([1, 1, 1], np.float32)[None, None] * spec[..., None]
        col += np.array([1.0, 0.97, 0.92], np.float32)[None, None] * velvet[..., None]
        col += np.array([1.0, 0.85, 0.62], np.float32)[None, None] * (rim * (0.6 + warm))[..., None]
        # 水光濕潤感:第二顆高光
        if gloss > 0.01:
            Hv2 = np.array([0.55, -0.5, 0.67], np.float32)
            Hv2 = Hv2 / np.linalg.norm(Hv2)
            ndh2 = np.clip(nx * Hv2[0] + ny * Hv2[1] + nzn * Hv2[2], 0, 1)
            col += (0.5 * gamp * ndh2 ** 90)[..., None] * np.array([1, 1, 1], np.float32)[None, None]
        col = np.clip(col, 0, 1)
        alpha = np.clip((1.0 - np.sqrt(r2)) / 0.015, 0, 1)
        out = np.dstack([col * 255, alpha[..., None] * 255 * mask[..., None]]).astype(np.uint8)
        return Image.fromarray(out, "RGBA")


PEACH = Fruit("peach", seed=3)
LEMON = Fruit("lemon", seed=7)
ORANGE = Fruit("orange", seed=11)


def ground_shadow(img, cx, cy, rx, ry, alpha=110):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(60, 40, 35, alpha))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))


def put_fruit(img, fruit, cx, cy, R, shadow=True, **kw):
    spr = fruit.render(R, **kw)
    if shadow:
        sx, sy = fruit.stretch
        ground_shadow(img, cx, cy + R * sy * 1.06, R * sx * 0.85, R * 0.16)
    img.alpha_composite(spr, (int(cx - spr.size[0] / 2), int(cy - spr.size[1] / 2)))


def draw_droplets(img, cx, cy, R, t, n=7, seed=5):
    """水珠高光(揭曉鏡用):小而克制,滑落感。"""
    d = ImageDraw.Draw(img)
    rng = random.Random(seed)
    for i in range(n):
        th = rng.uniform(0, 2 * math.pi)
        rr = R * math.sqrt(rng.uniform(0.15, 0.8))
        px = cx + rr * math.cos(th)
        py = cy + rr * math.sin(th) + (t * 3 + i * 5) % 8
        s = rng.uniform(2.5, 5.5)
        d.ellipse([px - s, py - s * 1.2, px + s, py + s * 1.2], fill=(255, 250, 245, 26))
        d.ellipse([px - s * 0.4, py - s * 0.7, px, py - s * 0.15],
                  fill=(255, 255, 255, 150))


def sparkle(d, x, y, s, color=(255, 250, 235, 220)):
    d.polygon([(x - s, y), (x, y - s * 0.26), (x + s, y), (x, y + s * 0.26)], fill=color)
    d.polygon([(x, y - s), (x - s * 0.26, y), (x, y + s), (x + s * 0.26, y)], fill=color)


# ---------------------------------------------------------------- 場景
def bg_vertical(c_top, c_bot):
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = np.array(c_top, np.float32)[None, None] * (1 - g) + \
        np.array(c_bot, np.float32)[None, None] * g
    arr = np.repeat(arr, W, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def studio_bg(warm=0.0, bokeh_seed=4):
    """攝影棚感:漸層+失焦光斑+地平線+暗角。"""
    top = (int(244 + 8 * warm), int(238 + 4 * warm), int(232 - 8 * warm))
    bot = (int(224 + 18 * warm), int(210 + 10 * warm), int(198 - 6 * warm))
    img = bg_vertical(top, bot)
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bok)
    rng = random.Random(bokeh_seed)
    for _ in range(9):
        bx, by = rng.uniform(0, W), rng.uniform(0, H * 0.5)
        rr = rng.uniform(30, 90)
        cc = (255, int(235 - 20 * warm), 200, rng.randint(14, 30))
        d.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=cc)
    img.alpha_composite(bok.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(img)
    fy = H * 0.70
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(grad)
    for k in range(40):
        a = int(26 * (1 - k / 40))
        dg.line([(0, fy + k * (H - fy) / 40), (W, fy + k * (H - fy) / 40)],
                fill=(120, 95, 80, a), width=int((H - fy) / 40) + 1)
    img.alpha_composite(grad.filter(ImageFilter.GaussianBlur(10)))
    return img


def vignette(img, strength=70):
    v = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.35, -H * 0.22, W * 1.35, H * 1.22], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", (W, H), (35, 22, 18, strength))
    dark.putalpha(Image.eval(v, lambda p: int((255 - p) * strength / 255)))
    img.alpha_composite(dark)


def caption(img, text, sub=None, y=None, small_note=None, color=(115, 78, 52, 255)):
    d = ImageDraw.Draw(img)
    y = y if y is not None else H - 205
    f1 = font(50)
    b = d.textbbox((0, 0), text, font=f1)
    tw = b[2] - b[0]
    d.rounded_rectangle([W / 2 - tw / 2 - 30, y - 16, W / 2 + tw / 2 + 30, y + 74],
                        radius=20, fill=(255, 253, 248, 175))
    d.text((W / 2 - tw / 2, y), text, font=f1, fill=color)
    if sub:
        f2 = font(29)
        b2 = d.textbbox((0, 0), sub, font=f2)
        d.text((W / 2 - (b2[2] - b2[0]) / 2, y + 90), sub, font=f2, fill=(150, 112, 82, 255))
    if small_note:
        f3 = font(22)
        b3 = d.textbbox((0, 0), small_note, font=f3)
        d.text((W / 2 - (b3[2] - b3[0]) / 2, H - 44), small_note, font=f3,
               fill=(150, 128, 105, 215))


def logo_watermark(img, alpha=200):
    lw = 190
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    logo = logo.copy()
    logo.putalpha(logo.split()[3].point(lambda v: int(v * alpha / 255)))
    img.alpha_composite(logo, (W - lw - 28, 26))


# ---------------------------------------------------------------- shots
def shot1(t, p):
    """寫實皺水果:昏暗棚光,緩慢旋轉。"""
    img = studio_bg(warm=0.0, bokeh_seed=4)
    rot = 0.012 * t
    breathe = math.sin(t * 1.6) * 4
    put_fruit(img, PEACH, W * 0.50, H * 0.42 + breathe, 205,
              wrinkle=1.0, gloss=0.0, rot=rot, light=(-0.5, -0.30, 0.81))
    put_fruit(img, LEMON, W * 0.16, H * 0.585 + breathe * 0.6, 96,
              wrinkle=1.0, gloss=0.0, rot=rot * 1.3 + 0.2)
    put_fruit(img, ORANGE, W * 0.85, H * 0.60 - breathe * 0.5, 102,
              wrinkle=1.0, gloss=0.0, rot=-rot + 0.55)
    vignette(img, 85)
    caption(img, "歲月悄悄，肌膚皺皺…", sub="鬆弛、暗沉、細紋悄悄爬上來")
    logo_watermark(img)
    return img


def shot2(t, p):
    """品牌卡:靚優 Logo + 療程名。"""
    img = bg_vertical((252, 246, 234), (240, 224, 196))
    d = ImageDraw.Draw(img)
    fade = ease(p * 2.8)
    lw = int(W * 0.66)
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    logo = logo.copy()
    logo.putalpha(logo.split()[3].point(lambda v: int(v * fade)))
    img.alpha_composite(logo, (int(W / 2 - lw / 2), int(H * 0.20)))
    # 金線
    a2 = int(255 * ease((p - 0.15) * 3))
    if a2 > 0:
        d.line([(W * 0.24, H * 0.42), (W * 0.76, H * 0.42)], fill=(198, 162, 96, a2), width=2)
        for txt, fs, yy in (("肌膚煥新體驗", 60, H * 0.46),
                            ("雷射煥膚 × 注射澎潤", 36, H * 0.545),
                            ("讓每一寸肌膚重新發光", 28, H * 0.60)):
            f = font(fs)
            b = d.textbbox((0, 0), txt, font=f)
            d.text((W / 2 - (b[2] - b[0]) / 2, yy), txt, font=f,
                   fill=(112, 82, 52, a2))
    # 底部小皺桃(旋轉),暗示主角
    put_fruit(img, PEACH, W * 0.5, H * 0.80, 96, wrinkle=1.0, gloss=0.0,
              rot=0.02 * t, shadow=True)
    rng = random.Random(9)
    for i in range(10):
        ph = (t * 0.1 + i / 10.0) % 1.0
        sparkle(d, (rng.random() * W) % W, ph * H, 3 + 5 * rng.random(),
                (214, 178, 110, 90))
    vignette(img, 40)
    caption(img, "來靚優，讓肌膚重新發光",
            sub="Dream-U Health Aesthetic Medicine Clinic")
    return img


def shot3(t, p):
    """治療:雷射掃過(左皺右亮) → 金色注射澎潤。"""
    laser_phase = clamp(p / 0.5)
    inj_phase = clamp((p - 0.5) / 0.5)
    warm = 0.25 * inj_phase
    img = studio_bg(warm=warm, bokeh_seed=6)
    R = 235
    cx, cy = W / 2, H * 0.42
    rot = 0.008 * t
    if inj_phase <= 0:
        sweep = -1.35 + 2.7 * ease(laser_phase)
        put_fruit(img, PEACH, cx, cy, R, wrinkle=1.0, gloss=0.85, rot=rot,
                  sweep=sweep, light=(-0.42, -0.36, 0.83))
        # 雷射光帶
        sxp = cx + sweep * R
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow)
        dg.ellipse([sxp - 60, cy - R - 46, sxp + 60, cy + R + 46], fill=(150, 205, 255, 55))
        dg.ellipse([sxp - 24, cy - R - 20, sxp + 24, cy + R + 20], fill=(205, 235, 255, 85))
        dg.line([(sxp, cy - R - 40), (sxp, cy + R + 40)], fill=(240, 250, 255, 230), width=5)
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(7)))
        d = ImageDraw.Draw(img)
        # 極簡雷射探頭(銀白+藍光圈,由上而下)
        hy = cy - R - 150
        d.rounded_rectangle([sxp - 17, hy, sxp + 17, hy + 116], radius=14,
                            fill=(232, 236, 242, 255), outline=(200, 206, 216, 255), width=2)
        d.rounded_rectangle([sxp - 23, hy + 108, sxp + 23, hy + 132], radius=9,
                            fill=(120, 180, 235, 255))
        d.ellipse([sxp - 10, hy + 16, sxp + 10, hy + 36], fill=(170, 215, 250, 255))
        # 微粒飄散(左側殘留皺屑感→光點)
        rng = random.Random(31)
        for i in range(26):
            life = (t * 0.8 + rng.random()) % 1.0
            px0 = cx + R * rng.uniform(-1, 1)
            if px0 > sxp - 8:
                continue
            px = px0 + life * 46
            py = cy + R * rng.uniform(-0.85, 0.85) - life * 120
            aa = int(130 * (1 - life))
            d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(235, 220, 200, aa))
        lbl = "雷射煥膚"
    else:
        wr = 0.5 * (1 - ease(inj_phase))
        plump = 1.0 + 0.045 * ease(inj_phase)
        put_fruit(img, PEACH, cx, cy, R * plump, wrinkle=wr, gloss=0.9, rot=rot,
                  warm=0.3, light=(-0.40, -0.40, 0.82))
        d = ImageDraw.Draw(img)
        # 金色注入點(右上,圓潤導入頭,無尖針)
        pen_x, pen_y = cx + R * 0.58, cy - R * 0.66
        ang = math.radians(40)
        px2 = pen_x + math.cos(ang) * 165
        py2 = pen_y - math.sin(ang) * 165
        d.line([(pen_x, pen_y), (px2, py2)], fill=(206, 168, 100, 255), width=22)
        d.line([(pen_x, pen_y), (px2, py2)], fill=(236, 208, 148, 255), width=10)
        d.ellipse([pen_x - 11, pen_y - 11, pen_x + 11, pen_y + 11], fill=(240, 214, 156, 255))
        for k in range(3):
            rr = (t * 85 + k * 42) % 126
            aa = int(150 * (1 - rr / 126))
            d.ellipse([pen_x - rr, pen_y - rr * 0.72, pen_x + rr, pen_y + rr * 0.72],
                      outline=(228, 188, 116, aa), width=3)
        rng = random.Random(77)
        for i in range(7):
            ph = (t * 0.85 + i / 7.0) % 1.0
            dx = rng.uniform(-0.45, 0.45) * R
            gx = pen_x + (cx + dx - pen_x) * ph
            gy = pen_y + (cy - pen_y) * ph
            aa = int(210 * (1 - ph * 0.7))
            d.ellipse([gx - 6, gy - 8, gx + 6, gy + 8], fill=(242, 204, 126, aa))
            d.ellipse([gx - 3, gy - 5, gx, gy - 2], fill=(255, 242, 205, aa))
        lbl = "注射澎潤"
    d = ImageDraw.Draw(img)
    rng2 = random.Random(int(t * 6))
    for _ in range(4):
        sparkle(d, cx + rng2.uniform(-R, R), cy + rng2.uniform(-R, R),
                rng2.uniform(6, 14))
    f = font(30)
    d.rounded_rectangle([cx - 108, cy + R + 42, cx + 108, cy + R + 92], radius=14,
                        fill=(255, 253, 248, 180))
    b = d.textbbox((0, 0), lbl, font=f)
    d.text((cx - (b[2] - b[0]) / 2, cy + R + 50), lbl, font=f, fill=(168, 112, 70, 255))
    vignette(img, 55)
    caption(img, "雷射煥膚 × 注射澎潤", small_note="療程效果因人而異")
    logo_watermark(img)
    return img


def shot4(t, p):
    """揭曉:水潤蜜桃+夥伴,暖金光。"""
    img = studio_bg(warm=0.6, bokeh_seed=8)
    ray = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ray)
    for k in range(9):
        a0 = k * 40 + t * 9
        dr.polygon([(W / 2, H * 0.40),
                    (W / 2 + 950 * math.cos(math.radians(a0)), H * 0.40 + 950 * math.sin(math.radians(a0))),
                    (W / 2 + 950 * math.cos(math.radians(a0 + 8)), H * 0.40 + 950 * math.sin(math.radians(a0 + 8)))],
                   fill=(255, 228, 165, 22))
    img.alpha_composite(ray.filter(ImageFilter.GaussianBlur(4)))
    rot = 0.015 * t
    bob = math.sin(t * 2.4) * 6
    R = 215
    put_fruit(img, PEACH, W * 0.50, H * 0.40 + bob, R, wrinkle=0.0, gloss=1.0,
              rot=rot, warm=0.5, light=(-0.42, -0.40, 0.81))
    draw_droplets(img, W * 0.50, H * 0.40 + bob, R * 0.9, t)
    put_fruit(img, LEMON, W * 0.15, H * 0.60 + math.sin(t * 2.4 + 1) * 5, 92,
              wrinkle=0.0, gloss=1.0, rot=rot + 0.3, warm=0.4)
    put_fruit(img, ORANGE, W * 0.86, H * 0.615 + math.sin(t * 2.4 + 2) * 5, 96,
              wrinkle=0.0, gloss=1.0, rot=-rot + 0.6, warm=0.4)
    d = ImageDraw.Draw(img)
    rng = random.Random(int(t * 8))
    for _ in range(9):
        sparkle(d, rng.uniform(30, W - 30), rng.uniform(H * 0.08, H * 0.72),
                rng.uniform(7, 20))
    vignette(img, 40)
    caption(img, "皺皺 OUT・水光 ON", sub="澎潤透亮，重新發光", small_note="療程效果因人而異")
    logo_watermark(img)
    return img


def shot5(t, p):
    """片尾卡:Logo + 醫師照 + 文案 + 小寫實蜜桃。"""
    img = bg_vertical((252, 245, 232), (238, 219, 186))
    d = ImageDraw.Draw(img)
    fade = ease(p * 3.5)
    lw = int(W * 0.62)
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    if fade < 1:
        logo = logo.copy()
        logo.putalpha(logo.split()[3].point(lambda v: int(v * fade)))
    img.alpha_composite(logo, (int(W / 2 - lw / 2), int(H * 0.075)))
    ds = int(300 * (0.85 + 0.15 * ease(p * 2.5)))
    doc = DOCTOR.resize((ds, ds), Image.LANCZOS)
    dy = int(H * 0.315)
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
    # 兩顆小寫實水果陪襯
    if p > 0.22:
        aa = ease((p - 0.22) * 4)
        yb = H * 0.50 + (1 - aa) * 30
        put_fruit(img, PEACH, W * 0.26, yb, 48, wrinkle=0.0, gloss=1.0,
                  rot=0.02 * t, warm=0.4)
        put_fruit(img, ORANGE, W * 0.74, yb + 6, 44, wrinkle=0.0, gloss=1.0,
                  rot=-0.02 * t, warm=0.4)
    d = ImageDraw.Draw(img)
    a2 = int(255 * ease((p - 0.18) * 3))
    if a2 > 0:
        for txt, fs, yy, col in (("撫平歲月痕跡", 58, H * 0.625, (110, 82, 52)),
                                 ("澎回青春光采", 58, H * 0.625 + 78, (110, 82, 52)),
                                 ("靚優健康醫學美容診所", 34, H * 0.625 + 195, (150, 118, 78)),
                                 ("Dream-U Health Aesthetic Medicine Clinic", 20,
                                  H * 0.625 + 250, (168, 140, 104))):
            f = font(fs)
            b = d.textbbox((0, 0), txt, font=f)
            d.text((W / 2 - (b[2] - b[0]) / 2, yy), txt, font=f, fill=col + (a2,))
        f = font(22)
        note = "療程效果因人而異"
        b = d.textbbox((0, 0), note, font=f)
        d.text((W / 2 - (b[2] - b[0]) / 2, H - 52), note, font=f, fill=(160, 138, 110, a2))
    rng = random.Random(42)
    for i in range(16):
        ph = (t * 0.12 + i / 16.0) % 1.0
        px = (rng.random() * W + math.sin(t + i) * 20) % W
        sparkle(d, px, ph * H, 4 + 6 * rng.random(), (222, 186, 120, 120))
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


# ---------------------------------------------------------------- audio (同前版)
def make_audio(path):
    sr = 44100
    n = int(DUR * sr)
    t = np.arange(n) / sr
    out = np.zeros(n, np.float32)
    chords = [(261.63, 329.63, 392.0), (246.94, 329.63, 392.0),
              (220.0, 261.63, 349.23), (196.0, 293.66, 392.0),
              (220.0, 261.63, 329.63), (174.61, 261.63, 349.23),
              (261.63, 329.63, 523.25)]
    seg = 4.0
    for k in range(7):
        m = (t >= k * seg) & (t < (k + 1) * seg)
        tt = t[m] - k * seg
        env = np.clip(np.minimum(tt / 0.9, 1.0) * np.minimum((seg - tt) / 0.9, 1.0), 0, 1)
        for f in chords[k]:
            out[m] += 0.045 * env * np.sin(2 * np.pi * f * tt) * \
                (0.8 + 0.2 * np.sin(2 * np.pi * 0.35 * tt))
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
    wav = os.path.join(OUT_DIR, "_music3.wav")
    out = os.path.join(OUT_DIR, "dreamu_renewal_3d_720x1280.mp4")
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
