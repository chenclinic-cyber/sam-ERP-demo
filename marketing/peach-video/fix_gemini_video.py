# -*- coding: utf-8 -*-
"""
Gemini 生成影片後製修正 (gemini_src.mp4, 1280x720, 10s, 24fps):
1. 右上角亂碼 Logo → 蓋上真正的靚優 Logo 白底章 (全程)
2. 2.2-4.45s 亂碼字幕 → 替換為「靚優雷射治療 撫平歲月痕跡」
3. 5.0-6.42s 注射水泡 → 漸進皮膚平滑 + 金色精華光暈/漣漪蓋掉水泡,呈現皺紋撫平
4. 7.7s 起片尾卡整段重做:真 Logo + 真醫師照 + 正確診所名(移除假電話)
音訊保留原始配樂。輸出: dreamu_gemini_fixed.mp4
"""
import math
import os
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
FPS = 24
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(OUT_DIR, "gemini_src.mp4")
OUT = os.path.join(OUT_DIR, "dreamu_gemini_fixed.mp4")
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def font(size):
    return ImageFont.truetype(FONT_PATH, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def sparkle(d, x, y, s, color=(255, 250, 235, 220)):
    d.polygon([(x - s, y), (x, y - s * 0.26), (x + s, y), (x, y + s * 0.26)], fill=color)
    d.polygon([(x, y - s), (x - s * 0.26, y), (x, y + s), (x + s * 0.26, y)], fill=color)


# ---------------------------------------------------------------- assets
def load_logo():
    im = Image.open(os.path.join(OUT_DIR, "assets/logo.png")).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    lum = arr[..., :3].mean(axis=2)
    arr[..., 3] = np.clip((250 - lum) / 14.0, 0, 1) * 255
    im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return im.crop(im.getbbox())


LOGO = load_logo()


def make_logo_overlay():
    """去背 Logo + 柔和白光暈(保持在任何背景上可讀),無白底章。"""
    lw = 260
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    pad = 30
    ov = Image.new("RGBA", (lw + pad * 2, logo.size[1] + pad * 2), (0, 0, 0, 0))
    halo = Image.new("RGBA", ov.size, (0, 0, 0, 0))
    white = Image.new("RGBA", logo.size, (255, 255, 255, 255))
    white.putalpha(logo.split()[3])
    halo.alpha_composite(white, (pad, pad))
    halo = halo.filter(ImageFilter.GaussianBlur(7))
    halo.putalpha(halo.split()[3].point(lambda v: int(v * 0.75)))
    ov.alpha_composite(halo)
    ov.alpha_composite(logo, (pad, pad))
    return ov


LOGO_OV = make_logo_overlay()
LOGO_BOX = (938, 6, 1258, 150)  # 原亂碼 Logo 區,先模糊融背


def apply_logo(img):
    region = img.crop(LOGO_BOX).filter(ImageFilter.GaussianBlur(28))
    region = region.filter(ImageFilter.GaussianBlur(28))
    img.paste(region, LOGO_BOX)
    img.alpha_composite(LOGO_OV, (952, 14))


def elliptical_mask(size, cx, cy, rx, ry, feather=40):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather))


# 水泡區與桃子區遮罩(固定鏡位,略放大涵蓋水泡長大)
BLISTER_MASK = elliptical_mask((W, H), 690, 450, 195, 165, feather=46)
PEACH_MASK = elliptical_mask((W, H), 660, 500, 430, 290, feather=70)


def make_endcard_base():
    """片尾卡:真醫師照 + 真 Logo + 正確文案(不放未經確認的電話)。"""
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = np.array([250, 243, 230], np.float32)[None, None] * (1 - g) + \
        np.array([236, 218, 188], np.float32)[None, None] * g
    img = Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")
    # 失焦金光斑
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    db = ImageDraw.Draw(bok)
    rng = random.Random(5)
    for _ in range(10):
        bx, by = rng.uniform(0, W), rng.uniform(0, H)
        rr = rng.uniform(40, 110)
        db.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=(255, 232, 180, rng.randint(10, 24)))
    img.alpha_composite(bok.filter(ImageFilter.GaussianBlur(20)))
    d = ImageDraw.Draw(img)
    # 醫師全身照(左,圓角金框)
    doc = Image.open(os.path.join(OUT_DIR, "assets/doctor.jpg")).convert("RGB")
    dh = 545
    dw = int(doc.size[0] * dh / doc.size[1])
    doc = doc.resize((dw, dh), Image.LANCZOS)
    dmask = Image.new("L", (dw, dh), 0)
    ImageDraw.Draw(dmask).rounded_rectangle([0, 0, dw, dh], radius=26, fill=255)
    dx, dy = 70, 55
    d.rounded_rectangle([dx - 8, dy - 8, dx + dw + 8, dy + dh + 8], radius=32,
                        outline=(198, 162, 96, 255), width=5)
    d.rounded_rectangle([dx - 2, dy - 2, dx + dw + 2, dy + dh + 2], radius=27,
                        outline=(255, 252, 244, 255), width=3)
    img.paste(doc, (dx, dy), dmask)
    # 蜜桃照(右,取自原片光滑鏡頭)
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = os.path.join(OUT_DIR, "_smooth_frame.png")
    subprocess.run([ff, "-y", "-ss", "7.05", "-i", SRC, "-frames:v", "1", tmp,
                    "-loglevel", "error"], check=True)
    pe = Image.open(tmp).convert("RGB").crop((410, 140, 850, 580)).resize((330, 330), Image.LANCZOS)
    os.remove(tmp)
    pmask = Image.new("L", (330, 330), 0)
    ImageDraw.Draw(pmask).rounded_rectangle([0, 0, 330, 330], radius=24, fill=255)
    px, py = 892, 160
    d.rounded_rectangle([px - 8, py - 8, px + 338, py + 338], radius=30,
                        outline=(198, 162, 96, 255), width=5)
    d.rounded_rectangle([px - 2, py - 2, px + 332, py + 332], radius=25,
                        outline=(255, 252, 244, 255), width=3)
    img.paste(pe, (px, py), pmask)
    # 中央:Logo + 文案
    lw = 380
    logo = LOGO.resize((lw, int(lw * LOGO.size[1] / LOGO.size[0])), Image.LANCZOS)
    ccx = 655
    img.alpha_composite(logo, (ccx - lw // 2, 80))
    d = ImageDraw.Draw(img)
    for txt, fs, yy, col in (("靚優健康醫學美容診所", 46, 320, (108, 80, 50)),
                             ("Dream-U Health Aesthetic Medicine Clinic", 20, 388, (162, 134, 98))):
        f = font(fs)
        b = d.textbbox((0, 0), txt, font=f)
        d.text((ccx - (b[2] - b[0]) / 2, yy), txt, font=f, fill=col + (255,))
    d.line([(ccx - 170, 440), (ccx + 170, 440)], fill=(198, 162, 96, 255), width=2)
    f = font(52)
    txt = "您的美麗專家"
    b = d.textbbox((0, 0), txt, font=f)
    d.text((ccx - (b[2] - b[0]) / 2, 468), txt, font=f, fill=(148, 110, 62, 255))
    # 底部金棕色帶
    d.rectangle([0, 645, W, H], fill=(176, 142, 94, 255))
    d.line([(0, 645), (W, 645)], fill=(210, 178, 128, 255), width=3)
    f = font(30)
    txt = "靚優健康醫學美容診所　讓美麗與健康同行"
    b = d.textbbox((0, 0), txt, font=f)
    d.text((W / 2 - (b[2] - b[0]) / 2, 656), txt, font=f, fill=(255, 252, 244, 255))
    f = font(17)
    txt = "療程效果因人而異"
    b = d.textbbox((0, 0), txt, font=f)
    d.text((W / 2 - (b[2] - b[0]) / 2, 694), txt, font=f, fill=(240, 226, 200, 230))
    return img


ENDCARD = make_endcard_base()


def endcard_frame(t):
    img = ENDCARD.copy()
    d = ImageDraw.Draw(img)
    rng = random.Random(42)
    for i in range(14):
        ph = (t * 0.10 + i / 14.0) % 1.0
        px = (rng.random() * W + math.sin(t * 0.8 + i) * 24) % W
        sparkle(d, px, ph * H * 0.88, 3 + 6 * rng.random(), (230, 196, 130, 110))
    return img


# ---------------------------------------------------------------- 逐幀處理
SUB_FIX = (2.2, 4.45)      # 亂碼字幕區間
BLISTER_FIX = (5.0, 6.42)  # 水泡區間
CARD_START = 7.70          # 片尾卡開始淡入
CARD_FULL = 8.05


def fix_subtitle(img):
    """模糊原字幕bbox,重寫正確文字。"""
    box = (255, 605, 1030, 700)
    region = img.crop(box).filter(ImageFilter.GaussianBlur(16))
    img.paste(region, box)
    d = ImageDraw.Draw(img)
    f = font(46)
    txt = "靚優雷射治療 撫平歲月痕跡"
    b = d.textbbox((0, 0), txt, font=f, stroke_width=3)
    d.text((W / 2 - (b[2] - b[0]) / 2, 622), txt, font=f, fill=(255, 255, 255, 255),
           stroke_width=3, stroke_fill=(70, 50, 40, 255))


def fix_blister(img, t):
    """水泡→漸進平滑+金色精華光暈:皺紋(與水泡)被撫平的視覺。"""
    s = ease((t - BLISTER_FIX[0]) / (BLISTER_FIX[1] - BLISTER_FIX[0]))
    # 1) 桃子整體皮膚漸進平滑(磨皮感)
    soft = img.filter(ImageFilter.GaussianBlur(3 + 7 * s))
    m1 = PEACH_MASK.point(lambda v: int(v * 0.72 * s))
    img.paste(soft, (0, 0), m1)
    # 2) 水泡區強力平滑融掉
    melt = img.filter(ImageFilter.GaussianBlur(10 + 14 * s))
    m2 = BLISTER_MASK.point(lambda v: int(v * (0.55 + 0.45 * s)))
    img.paste(melt, (0, 0), m2)
    # 3) 金色精華光暈 + 擴散漣漪(以針尖為中心)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    gx, gy = 640, 430
    dg.ellipse([gx - 200, gy - 160, gx + 240, gy + 200], fill=(255, 214, 140, int(48 + 30 * s)))
    dg.ellipse([gx - 90, gy - 70, gx + 120, gy + 100], fill=(255, 236, 190, int(56 + 30 * s)))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)
    for k in range(3):
        rr = (t * 130 + k * 60) % 190 + 20
        aa = int(140 * (1 - (rr - 20) / 190) * (0.5 + 0.5 * s))
        d.ellipse([gx - rr, gy - rr * 0.75, gx + rr, gy + rr * 0.75],
                  outline=(238, 198, 128, aa), width=4)
    rng = random.Random(int(t * 8))
    for _ in range(6):
        sparkle(d, gx + rng.uniform(-210, 230), gy + rng.uniform(-160, 190),
                rng.uniform(7, 16), (255, 244, 214, 200))
    # 小標籤:皺紋撫平中
    f = font(26)
    txt = "皺紋撫平中"
    b = d.textbbox((0, 0), txt, font=f)
    bx = gx + 150
    by = gy - 190
    d.rounded_rectangle([bx - 16, by - 8, bx + (b[2] - b[0]) + 16, by + 40], radius=12,
                        fill=(255, 253, 248, 190))
    d.text((bx, by), txt, font=f, fill=(168, 112, 70, 255))


def process_frame(img, i):
    t = i / FPS
    if t >= CARD_START:
        a = ease((t - CARD_START) / (CARD_FULL - CARD_START))
        card = endcard_frame(t)
        if a >= 1.0:
            return card
        base = img.copy()
        apply_logo(base)
        return Image.blend(base, card, a)
    if BLISTER_FIX[0] <= t <= BLISTER_FIX[1]:
        fix_blister(img, t)
    if SUB_FIX[0] <= t <= SUB_FIX[1]:
        fix_subtitle(img)
    apply_logo(img)
    return img


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
    nbytes = W * H * 3
    i = 0
    while True:
        buf = dec.stdout.read(nbytes)
        if len(buf) < nbytes:
            break
        img = Image.frombytes("RGB", (W, H), buf).convert("RGBA")
        out = process_frame(img, i).convert("RGB")
        enc.stdin.write(out.tobytes())
        if i % 48 == 0:
            print(f"  frame {i}")
        i += 1
    dec.stdout.close()
    enc.stdin.close()
    enc.wait()
    print(f"完成: {OUT} ({i} frames)")


if __name__ == "__main__":
    main()
