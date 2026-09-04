#!/usr/bin/env python3
"""Render the 10s peach-lady ad (24fps, 1280x720) to master_peach.mp4 (no logo)."""
import subprocess as sp
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import peach_assets as PA

W, H, FPS = 1280, 720, 24
N1, N2, N3 = 84, 120, 36           # scene frame counts (total 240 = 10s)
XF = 8                              # crossfade frames between scenes

def ease(t):
    return t * t * (3 - 2 * t)

# ---- cached assets ----
bg1 = PA.bg_lobby().convert("RGBA")
bg2 = PA.bg_room().convert("RGBA")
bg3 = PA.bg_exterior().convert("RGBA")
spr_walk = PA.peach_sprite(0.15, coat=True, bag=True)
spr_dull = PA.peach_sprite(0.12, goggles=True, coat=False)
spr_dewy = PA.peach_sprite(1.0, goggles=True, coat=False, droplets=True)
spr_out_base = dict(dewy=1.0, coat=True)
rng = np.random.default_rng(21)
SPARKS = [(rng.integers(80, 1200), rng.integers(60, 600),
           rng.uniform(0, 6.28), rng.uniform(2, 5)) for _ in range(26)]

def draw_spark(d, x, y, r, a):
    c = (255, 240, 180, int(a * 255))
    d.polygon([(x, y - r), (x + r * 0.3, y - r * 0.3), (x + r, y),
               (x + r * 0.3, y + r * 0.3), (x, y + r), (x - r * 0.3, y + r * 0.3),
               (x - r, y), (x - r * 0.3, y - r * 0.3)], fill=c)

def scene1(i):
    f = bg1.copy()
    t = i / (N1 - 1)
    # walk in from the left door towards center
    x = int(-380 + (470 + 380) * ease(min(t * 1.25, 1.0)))
    bob = int(10 * abs(np.sin(i * 0.45)))
    rot = 3.0 * np.sin(i * 0.45)
    spr = spr_walk.resize((390, 510), Image.LANCZOS).rotate(rot, resample=Image.BICUBIC, expand=False)
    f.alpha_composite(spr, (x, 170 - bob))
    return f

def scene2(i):
    f = bg2.copy()
    t = i / (N2 - 1)
    sw, sh = 470, 614
    sx, sy = 400, 80
    p = ease(np.clip((i - 20) / 80.0, 0, 1))     # treatment progress
    wipe = int(p * (sw + 60)) - 30
    dull = spr_dull.resize((sw, sh), Image.LANCZOS)
    dewy = spr_dewy.resize((sw, sh), Image.LANCZOS)
    # soft vertical wipe mask (dewy on the left of the front line)
    mx = np.clip((wipe - np.arange(sw)) / 26.0 + 0.5, 0, 1)
    mask = Image.fromarray(np.tile((mx * 255).astype(np.uint8), (sh, 1)))
    body = Image.composite(dewy, dull, mask)
    f.alpha_composite(body, (sx, sy))
    d = ImageDraw.Draw(f)
    # doctor arm + handpiece treats the left cheek while the glow sweeps
    if 0.01 < p < 0.99:
        tipx, tipy = sx + 165, 452 + int(14 * np.sin(i * 0.5))
        d.rounded_rectangle([tipx - 330, tipy - 26, tipx - 130, tipy + 26],
                            radius=22, fill=(250, 250, 252, 255))       # sleeve
        d.ellipse([tipx - 150, tipy - 30, tipx - 74, tipy + 34], fill=(96, 128, 196, 255))  # glove
        d.rounded_rectangle([tipx - 96, tipy - 14, tipx - 6, tipy + 14],
                            radius=12, fill=(150, 152, 158, 255))       # device
        # glow at tip
        glow = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow)
        pr = 34 + 10 * np.sin(i * 0.9)
        for rr, aa in ((pr * 1.9, 60), (pr * 1.3, 110), (pr * 0.7, 220)):
            dg.ellipse([80 - rr, 80 - rr, 80 + rr, 80 + rr], fill=(255, 232, 150, aa))
        glow = glow.filter(ImageFilter.GaussianBlur(6))
        f.alpha_composite(glow, (tipx - 80, tipy - 80))
    # sparkles on the treated side
    if p > 0.15:
        for (px, py, ph, pf) in SPARKS[:14]:
            if sx < px < sx + wipe and 60 < py < 640:
                a = max(0.0, np.sin(i * 0.35 + ph)) * min(1, (p - 0.1) * 2)
                if a > 0.05:
                    draw_spark(d, px, py, 4 + 5 * a, a)
    return f

def scene3(i):
    f = bg3.copy()
    t = i / (N3 - 1)
    wave = 28 + 16 * np.sin(i * 0.55)
    spr = PA.peach_sprite(1.0, coat=True, wave=wave)
    sc = 0.78 + 0.10 * ease(t)
    sw, sh = int(520 * sc), int(680 * sc)
    spr = spr.resize((sw, sh), Image.LANCZOS)
    f.alpha_composite(spr, (640 - sw // 2, 640 - sh))
    d = ImageDraw.Draw(f)
    for (px, py, ph, pf) in SPARKS[10:]:
        a = max(0.0, np.sin(i * 0.4 + ph)) * 0.9
        if a > 0.05:
            draw_spark(d, px, py, 4 + 6 * a, a)
    return f

def frame(n):
    if n < N1:
        img = scene1(n)
        if n >= N1 - XF:  # crossfade into scene 2
            a = (n - (N1 - XF)) / XF
            img = Image.blend(img, scene2(0), a)
    elif n < N1 + N2:
        i = n - N1
        img = scene2(i)
        if i >= N2 - XF:
            a = (i - (N2 - XF)) / XF
            img = Image.blend(img, scene3(0), a)
    else:
        img = scene3(n - N1 - N2)
    return img.convert("RGB")

enc = sp.Popen([
    "ffmpeg", "-y", "-v", "error",
    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
    "master_peach.mp4"], stdin=sp.PIPE)
for n in range(N1 + N2 + N3):
    enc.stdin.write(np.asarray(frame(n), np.uint8).tobytes())
enc.stdin.close()
enc.wait()
print("master_peach.mp4 done:", N1 + N2 + N3, "frames")
