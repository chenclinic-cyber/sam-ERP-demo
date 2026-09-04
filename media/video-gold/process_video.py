#!/usr/bin/env python3
"""Two-pass jacket recolor: pass1 computes per-frame gate, pass2 recolors."""
import subprocess as sp
import numpy as np
from PIL import Image, ImageFilter
import recolor as R

SRC = "/root/.claude/uploads/b62246aa-84da-5240-b4e2-fc56dfb16a1e/f7bf348c-gemini_generated_video_473F29C8.mp4"
W, H = 1280, 720

# ---- pass 1: gate per frame (downscaled for speed) ----
w1, h1 = 320, 180
p = sp.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", f"scale={w1}:{h1}",
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=sp.PIPE)
fracs = []
while True:
    buf = p.stdout.read(w1 * h1 * 3)
    if len(buf) < w1 * h1 * 3:
        break
    a = np.frombuffer(buf, np.uint8).reshape(h1, w1, 3)
    h, s, v = R.rgb_to_hsv(a)
    m = R.pink_mask(h, s, v)
    fracs.append(float((m > 0.6).mean()))
p.wait()
fracs = np.array(fracs)
# median smooth (width 5)
sm = np.copy(fracs)
for i in range(len(fracs)):
    sm[i] = np.median(fracs[max(0, i - 2):i + 3])
gates = np.clip((sm - 0.04) / 0.03, 0, 1)
print(f"frames={len(fracs)} gated_on={int((gates>0.5).sum())}")

# ---- pass 2: recolor + encode ----
dec = sp.Popen(["ffmpeg", "-v", "error", "-i", SRC,
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=sp.PIPE)
enc = sp.Popen([
    "ffmpeg", "-y", "-v", "error",
    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "24", "-i", "-",
    "-i", "logo_overlay.png",
    "-filter_complex",
    "[0:v]delogo=x=925:y=8:w=350:h=84,delogo=x=1112:y=552:w=116:h=106[d];"
    "[d][1:v]overlay=954:10",
    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
    "main.mp4"], stdin=sp.PIPE)

def blur(m):
    mi = Image.fromarray((m * 255).astype(np.uint8))
    return np.array(mi.filter(ImageFilter.GaussianBlur(2)), np.float32) / 255.0

i = 0
while True:
    buf = dec.stdout.read(W * H * 3)
    if len(buf) < W * H * 3:
        break
    a = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    g = gates[i] if i < len(gates) else 0.0
    if g > 0.01:
        h, s, v = R.rgb_to_hsv(a)
        m = R.pink_mask(h, s, v) * g
        m = blur(m)
        h2 = np.full_like(h, 42.0)
        s2 = np.clip(s * 2.2 + 0.16, 0, 0.88)
        v2 = np.clip(v * 0.99, 0, 1)
        gold = R.hsv_to_rgb(h2, s2, v2).astype(np.float32)
        out = (a.astype(np.float32) * (1 - m[..., None]) + gold * m[..., None])
        a = out.clip(0, 255).astype(np.uint8)
    enc.stdin.write(a.tobytes())
    i += 1
dec.wait()
enc.stdin.close()
enc.wait()
print("pass2 done, frames:", i)
