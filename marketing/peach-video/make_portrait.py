# -*- coding: utf-8 -*-
"""
直式 9:16 IG 版 (720x1280):
- 背景 = 原畫面放大模糊;主畫面 = 修正後影像縮至 720x405 圓角置中偏上
- 原字幕全部模糊隱藏,改在下方以大字卡重寫(手機易讀)
- 靚優去背 Logo 置頂;片尾卡為原生直式設計(真醫師照+可愛蜜桃照)
輸出: dreamu_gemini_fixed_9x16.mp4
"""
import math
import os
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import fix_gemini_video as fx
from fix_gemini_video import (LOGO, LOGO_BOX, BLISTER_FIX, SUB_FIX, CARD_START,
                              CARD_FULL, fix_blister, ease, sparkle, font, SRC)

W, H = 720, 1280
SW, SH = 1280, 720
FPS = 24
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(OUT_DIR, "dreamu_gemini_fixed_9x16.mp4")

STRIP_H = 405
STRIP_Y = 330

# 各段字卡 (t0, t1, 主標, 副標)
CAPTIONS = [
    (0.0, 2.2, "肌膚細紋好顯老…", "水蜜桃女孩的困擾"),
    (2.2, 4.45, "靚優雷射治療", "撫平歲月痕跡"),
    (4.45, 6.42, "精準微整注射", "找回澎潤彈性"),
    (6.42, CARD_START, "重返光滑亮麗", "靚優為您打造"),
]
SUB_BOX_RIGHT = (790, 270, 1262, 450)   # 第一段右側直排字
SUB_BOX_BOTTOM = (255, 595, 1035, 706)  # 其餘底部字幕


def make_logo_top():
    lw = 300
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    pad = 26
    ov = Image.new("RGBA", (lw + pad * 2, logo.size[1] + pad * 2), (0, 0, 0, 0))
    halo = Image.new("RGBA", ov.size, (0, 0, 0, 0))
    white = Image.new("RGBA", logo.size, (255, 255, 255, 255))
    white.putalpha(logo.split()[3])
    halo.alpha_composite(white, (pad, pad))
    halo = halo.filter(ImageFilter.GaussianBlur(6))
    halo.putalpha(halo.split()[3].point(lambda v: int(v * 0.8)))
    ov.alpha_composite(halo)
    ov.alpha_composite(logo, (pad, pad))
    return ov


LOGO_TOP = make_logo_top()

STRIP_MASK = Image.new("L", (W, STRIP_H), 0)
ImageDraw.Draw(STRIP_MASK).rounded_rectangle([0, 0, W, STRIP_H], radius=20, fill=255)


def get_cute_peach(size=220):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = os.path.join(OUT_DIR, "_cute.png")
    subprocess.run([ff, "-y", "-ss", "7.05", "-i", SRC, "-frames:v", "1", tmp,
                    "-loglevel", "error"], check=True)
    pe = Image.open(tmp).convert("RGB").crop((410, 140, 850, 580)).resize((size, size),
                                                                          Image.LANCZOS)
    os.remove(tmp)
    return pe


def make_endcard():
    """原生直式片尾卡。"""
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = np.array([252, 245, 232], np.float32)[None, None] * (1 - g) + \
        np.array([238, 219, 186], np.float32)[None, None] * g
    img = Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    db = ImageDraw.Draw(bok)
    rng = random.Random(5)
    for _ in range(10):
        bx, by = rng.uniform(0, W), rng.uniform(0, H)
        rr = rng.uniform(40, 100)
        db.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=(255, 232, 180, rng.randint(10, 22)))
    img.alpha_composite(bok.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)
    # Logo 置頂
    lw = 440
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    img.alpha_composite(logo, (W // 2 - lw // 2, 62))
    d = ImageDraw.Draw(img)
    # 醫師照(置中偏左) + 可愛蜜桃照(右下疊放,拼貼感)
    doc = Image.open(os.path.join(OUT_DIR, "assets/doctor.jpg")).convert("RGB")
    dh = 430
    dw = int(doc.size[0] * dh / doc.size[1])
    doc = doc.resize((dw, dh), Image.LANCZOS)
    dmask = Image.new("L", (dw, dh), 0)
    ImageDraw.Draw(dmask).rounded_rectangle([0, 0, dw, dh], radius=24, fill=255)
    dx, dy = W // 2 - dw // 2 - 70, 330
    d.rounded_rectangle([dx - 8, dy - 8, dx + dw + 8, dy + dh + 8], radius=30,
                        outline=(198, 162, 96, 255), width=5)
    d.rounded_rectangle([dx - 2, dy - 2, dx + dw + 2, dy + dh + 2], radius=25,
                        outline=(255, 252, 244, 255), width=3)
    img.paste(doc, (dx, dy), dmask)
    pe = get_cute_peach(230)
    pmask = Image.new("L", pe.size, 0)
    ImageDraw.Draw(pmask).rounded_rectangle([0, 0, pe.size[0], pe.size[1]], radius=22, fill=255)
    px, py = dx + dw - 60, dy + dh - 250
    d.rounded_rectangle([px - 8, py - 8, px + pe.size[0] + 8, py + pe.size[1] + 8],
                        radius=28, outline=(198, 162, 96, 255), width=5)
    d.rounded_rectangle([px - 2, py - 2, px + pe.size[0] + 2, py + pe.size[1] + 2],
                        radius=23, outline=(255, 252, 244, 255), width=3)
    img.paste(pe, (px, py), pmask)
    d = ImageDraw.Draw(img)
    # 文案
    for txt, fs, yy, col in (("靚優健康醫學美容診所", 46, 856, (108, 80, 50)),
                             ("Dream-U Health Aesthetic Medicine Clinic", 20, 922, (162, 134, 98))):
        f = font(fs)
        b = d.textbbox((0, 0), txt, font=f)
        d.text((W / 2 - (b[2] - b[0]) / 2, yy), txt, font=f, fill=col + (255,))
    d.line([(W / 2 - 160, 976), (W / 2 + 160, 976)], fill=(198, 162, 96, 255), width=2)
    f = font(54)
    txt = "您的美麗專家"
    b = d.textbbox((0, 0), txt, font=f)
    d.text((W / 2 - (b[2] - b[0]) / 2, 1002), txt, font=f, fill=(148, 110, 62, 255))
    # 底部金棕帶
    d.rectangle([0, 1180, W, H], fill=(176, 142, 94, 255))
    d.line([(0, 1180), (W, 1180)], fill=(210, 178, 128, 255), width=3)
    f = font(28)
    txt = "讓美麗與健康同行"
    b = d.textbbox((0, 0), txt, font=f)
    d.text((W / 2 - (b[2] - b[0]) / 2, 1194), txt, font=f, fill=(255, 252, 244, 255))
    f = font(17)
    txt = "療程效果因人而異"
    b = d.textbbox((0, 0), txt, font=f)
    d.text((W / 2 - (b[2] - b[0]) / 2, 1236), txt, font=f, fill=(240, 226, 200, 230))
    return img


ENDCARD_P = make_endcard()


def endcard_frame(t):
    img = ENDCARD_P.copy()
    d = ImageDraw.Draw(img)
    rng = random.Random(42)
    for i in range(16):
        ph = (t * 0.10 + i / 16.0) % 1.0
        px = (rng.random() * W + math.sin(t * 0.8 + i) * 22) % W
        sparkle(d, px, ph * H * 0.9, 3 + 6 * rng.random(), (230, 196, 130, 110))
    return img


def caption_card(img, main, sub):
    d = ImageDraw.Draw(img)
    y = STRIP_Y + STRIP_H + 92
    f1 = font(56)
    b = d.textbbox((0, 0), main, font=f1)
    tw = b[2] - b[0]
    d.rounded_rectangle([W / 2 - tw / 2 - 32, y - 18, W / 2 + tw / 2 + 32, y + 82],
                        radius=22, fill=(255, 253, 248, 200))
    d.text((W / 2 - tw / 2, y), main, font=f1, fill=(115, 78, 52, 255))
    f2 = font(34)
    b2 = d.textbbox((0, 0), sub, font=f2)
    d.text((W / 2 - (b2[2] - b2[0]) / 2, y + 104), sub, font=f2, fill=(150, 112, 82, 255))
    f3 = font(22)
    note = "療程效果因人而異"
    b3 = d.textbbox((0, 0), note, font=f3)
    d.text((W / 2 - (b3[2] - b3[0]) / 2, H - 56), note, font=f3, fill=(150, 128, 105, 215))


def process_frame(src_img, i):
    t = i / FPS
    if t >= CARD_FULL:
        return endcard_frame(t)
    # 修正原畫面(水泡/亂碼區塊模糊)
    work = src_img.convert("RGBA")
    if BLISTER_FIX[0] <= t <= BLISTER_FIX[1]:
        fix_blister(work, t)
    box = SUB_BOX_RIGHT if t < 2.2 else SUB_BOX_BOTTOM
    region = work.crop(box).filter(ImageFilter.GaussianBlur(22))
    work.paste(region, box)
    region = work.crop(LOGO_BOX).filter(ImageFilter.GaussianBlur(28)).filter(
        ImageFilter.GaussianBlur(28))
    work.paste(region, LOGO_BOX)
    # 背景:放大模糊
    bg_w = int(SW * H / SH)
    bg = src_img.resize((bg_w, H), Image.BILINEAR).crop(
        ((bg_w - W) // 2, 0, (bg_w - W) // 2 + W, H)).filter(ImageFilter.GaussianBlur(26))
    canvas = bg.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (250, 245, 238, 60)))
    # 主畫面圓角條
    strip = work.convert("RGB").resize((W, STRIP_H), Image.LANCZOS)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([14, STRIP_Y + 14, W - 14, STRIP_Y + STRIP_H + 14],
                                         radius=22, fill=(70, 45, 30, 90))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    canvas.paste(strip, (0, STRIP_Y), STRIP_MASK)
    # Logo 置頂
    canvas.alpha_composite(LOGO_TOP, (W // 2 - LOGO_TOP.size[0] // 2, 70))
    # 字卡
    for t0, t1, main, sub in CAPTIONS:
        if t0 <= t < t1:
            caption_card(canvas, main, sub)
            break
    if t >= CARD_START:
        a = ease((t - CARD_START) / (CARD_FULL - CARD_START))
        canvas = Image.blend(canvas, endcard_frame(t), a)
    return canvas


def main():
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    dec = subprocess.Popen(
        [ff, "-i", SRC, "-f", "rawvideo", "-pix_fmt", "rgb24", "-loglevel", "error", "-"],
        stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        [ff, "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", SRC, "-map", "0:v", "-map", "1:a", "-c:a", "copy",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
         "-movflags", "+faststart", "-loglevel", "error", OUT],
        stdin=subprocess.PIPE)
    nbytes = SW * SH * 3
    i = 0
    while True:
        buf = dec.stdout.read(nbytes)
        if len(buf) < nbytes:
            break
        img = Image.frombytes("RGB", (SW, SH), buf)
        enc.stdin.write(process_frame(img, i).convert("RGB").tobytes())
        if i % 48 == 0:
            print(f"  frame {i}")
        i += 1
    dec.stdout.close()
    enc.stdin.close()
    enc.wait()
    print(f"完成: {OUT} ({i} frames)")


if __name__ == "__main__":
    main()
