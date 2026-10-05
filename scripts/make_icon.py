"""Draws icon.ico: a dark tile with a ragged, noisy waveform entering from
the left, a filter bar in the middle, and a clean sine leaving on the right.
Drawn at 1024 px and downsampled for crisp small sizes."""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

S = 1024
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico")

BG, EDGE = (16, 20, 24, 255), (79, 176, 224, 255)
NOISY, CLEAN, BAR = (150, 160, 170, 255), (95, 200, 245, 255), (240, 170, 60, 255)
MID, AMP = S // 2, 210


def wave(x: float) -> float:
    return MID - AMP * math.sin((x - 130) / (S - 260) * 2 * math.pi * 2)


def noisy_points():
    rnd = random.Random(7)  # fixed seed: the icon is identical every build
    pts = []
    for i, x in enumerate(range(130, 471, 20)):
        jitter = rnd.uniform(60, 190) * (1 if i % 2 else -1)
        pts.append((x, wave(x) * 0.45 + MID * 0.55 + jitter))
    return pts


def clean_points():
    return [(x, wave(x)) for x in range(560, S - 128, 4)]


def draw(d: ImageDraw.ImageDraw, bar: bool = True):
    d.line(noisy_points(), fill=NOISY, width=30, joint="curve")
    d.line(clean_points(), fill=CLEAN, width=46, joint="curve")
    if bar:
        d.rounded_rectangle([488, 190, 536, S - 190], radius=24, fill=BAR)


img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([40, 40, S - 40, S - 40], radius=190, fill=BG, outline=EDGE, width=34)

glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(glow).line(clean_points(), fill=CLEAN, width=70, joint="curve")
img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(30)))
draw(ImageDraw.Draw(img))

img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.resize((256, 256), Image.LANCZOS).save(os.path.join(os.path.dirname(OUT), "scripts", "icon_preview.png"))
print("wrote", OUT)
