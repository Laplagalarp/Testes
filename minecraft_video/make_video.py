#!/usr/bin/env python3
"""Gera do zero um short vertical (1080x1920, ~56s) sobre Minecraft.

Tudo é procedural: texturas pixel-art, animações, transições e efeitos
sonoros sintetizados no estilo do jogo (cliques, blocos, XP, creeper,
explosão, portal, dragão) + uma trilha ambiente de piano original.

Uso:  python3 make_video.py      (precisa de numpy, Pillow e ffmpeg)
"""
import math
import os
import unicodedata
import subprocess
import wave
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 540, 960          # canvas interno (escalado 2x em pixel-art no final)
FPS = 30
SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(HERE, "PressStart2P.woff")
OUT = os.path.join(HERE, "minecraft_short.mp4")
WAV = os.path.join(HERE, "audio.wav")

WHITE = (255, 255, 255)
YELLOW = (255, 255, 85)
GREEN_XP = (128, 255, 32)
AQUA = (85, 255, 255)
GRAY = (170, 170, 170)
RED = (255, 85, 85)
PURPLE = (224, 121, 250)
ORANGE = (255, 170, 0)


# ----------------------------------------------------------------- utils
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_in(t):
    t = clamp(t)
    return t * t * t


def ease_out_back(t, s=1.70158):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out_bounce(t):
    t = clamp(t)
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


# -------------------------------------------------------------- texturas
def make_tex(base, amp, seed, spots=()):
    r = np.random.default_rng(seed)
    n = r.integers(-amp, amp + 1, (16, 16, 1))
    a = np.clip(np.array(base, float)[None, None, :] + n, 0, 255)
    for color, prob in spots:
        m = r.random((16, 16)) < prob
        a[m] = color
    return a.astype(np.uint8)


DIRT = make_tex((134, 96, 67), 12, 1, [((104, 74, 50), 0.14), ((160, 118, 84), 0.08)])
GRASS_TOP = make_tex((98, 160, 56), 14, 2, [((74, 128, 40), 0.18), ((124, 184, 72), 0.1)])
GRASS_SIDE = DIRT.copy()
_r = np.random.default_rng(9)
for _x in range(16):
    _d = 3 + int(_r.integers(0, 3))
    GRASS_SIDE[:_d, _x] = GRASS_TOP[:_d, _x]
STONE = make_tex((125, 125, 125), 9, 3, [((104, 104, 104), 0.16), ((146, 146, 146), 0.08)])
DIAMOND_ORE = STONE.copy()
for (_cx, _cy) in [(4, 4), (11, 5), (5, 11), (11, 12)]:
    for _dx, _dy, _c in [(0, 0, (92, 219, 213)), (1, 0, (161, 251, 232)), (0, 1, (30, 140, 140)),
                         (1, 1, (92, 219, 213)), (-1, 0, (30, 140, 140)), (0, -1, (209, 255, 247))]:
        DIAMOND_ORE[_cy + _dy, _cx + _dx] = _c
OBSIDIAN = make_tex((22, 17, 34), 5, 4, [((54, 38, 86), 0.12), ((8, 6, 14), 0.12)])
NETHERRACK = make_tex((111, 54, 52), 12, 5, [((80, 30, 30), 0.2), ((142, 72, 70), 0.08)])
END_STONE = make_tex((221, 223, 165), 7, 6, [((196, 196, 138), 0.2), ((236, 237, 192), 0.08)])
LOG = make_tex((104, 82, 50), 6, 7)
LOG[:, ::4] = (78, 60, 36)
LEAVES = make_tex((58, 132, 38), 16, 8, [((38, 98, 24), 0.25), ((84, 160, 60), 0.1)])


def block_img(tex, size):
    return Image.fromarray(tex).resize((size, size), Image.NEAREST)


@lru_cache(maxsize=None)
def tiled(name, block, darken=1.0, extra=0):
    tex = globals()[name]
    b = np.array(block_img(tex, block))
    ny, nx = (H + extra) // block + 2, (W + extra) // block + 2
    a = np.tile(b, (ny, nx, 1)).astype(float) * darken
    return np.clip(a, 0, 255).astype(np.uint8)


def tiled_bg(name, block, darken=1.0, ox=0, oy=0):
    a = tiled(name, block, darken, block)
    ox, oy = int(ox) % block, int(oy) % block
    return Image.fromarray(a[oy:oy + H, ox:ox + W].copy())


def vgrad(c1, c2):
    t = np.linspace(0, 1, H)[:, None, None]
    a = np.array(c1, float) * (1 - t) + np.array(c2, float) * t
    return np.repeat(a, W, axis=1).astype(np.uint8)


# ----------------------------------------------------------------- texto
@lru_cache(maxsize=None)
def font(sz):
    return ImageFont.truetype(FONT_PATH, sz)


# a fonte pixel só tem acentos minúsculos: desenhamos os acentos das maiúsculas à mão
ACCENTS = {
    "\u0301": [(4, -3), (5, -3), (3, -2), (4, -2)],          # agudo
    "\u0300": [(2, -3), (3, -3), (3, -2), (4, -2)],          # grave
    "\u0302": [(3, -3), (4, -3), (2, -2), (5, -2)],          # circunflexo
    "\u0303": [(1, -2), (2, -3), (3, -3), (4, -2), (5, -2), (6, -3)],  # til
    "\u0327": [(3, 7), (4, 7), (4, 8), (2, 9), (3, 9)],      # cedilha
}


def split_accents(txt):
    base, marks = "", []
    for i, ch in enumerate(txt):
        dec = unicodedata.normalize("NFD", ch)
        if ch.isupper() and len(dec) > 1 and dec[1] in ACCENTS:
            base += dec[0]
            marks.append((i, ACCENTS[dec[1]]))
        else:
            base += ch
    return base, marks


@lru_cache(maxsize=2048)
def text_img(txt, size, color=WHITE, outline=False):
    f = font(size)
    off = max(2, size // 8)
    u = size / 8
    pad = off * 3 + int(4 * u)
    base, marks = split_accents(txt)
    im = Image.new("RGBA", (len(txt) * size + pad * 2, size * 2 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def put(x, y, fill):
        d.text((x, y), base, font=f, fill=fill)
        for i, pts in marks:
            for px, py in pts:
                x0, y0 = x + i * size + px * u, y + py * u
                d.rectangle((x0, y0, x0 + u - 1, y0 + u - 1), fill=fill)

    if outline:
        for dx in (-off, 0, off):
            for dy in (-off, 0, off):
                put(pad + dx, pad + dy, (0, 0, 0, 255))
        put(pad + off, pad + off + off, (0, 0, 0, 255))
    else:
        sh = tuple(c // 4 for c in color)
        put(pad + off, pad + off, sh + (255,))
    put(pad, pad, tuple(color) + (255,))
    # caixa fixa (independe dos glifos) para o typewriter não "pular"
    top = pad - off - int(3 * u)
    full_w = len(txt) * size + off * 2
    return im.crop((pad - off, top, pad - off + full_w + off, pad + size + int(2 * u) + off * 2))


def paste_center(base, im, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.NEAREST)
    if angle:
        im = im.rotate(angle, Image.NEAREST, expand=True)
    if alpha < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    base.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def wrap(txt, size, maxw=W - 40):
    maxc = max(1, maxw // size)
    lines = []
    for para in txt.split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = (cur + " " + word).strip()
            if len(cand) <= maxc:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


class T:
    """Item de texto com animação (typewriter, pop, fade out)."""

    def __init__(self, t0, text, size, y, color=WHITE, cps=0, pop=False, outline=False, t1=None):
        self.t0, self.text, self.size, self.y = t0, text, size, y
        self.color, self.cps, self.pop, self.outline, self.t1 = color, cps, pop, outline, t1
        self.lines = wrap(text, size)

    @property
    def nchars(self):
        return sum(len(l) for l in self.lines)

    def draw(self, img, t):
        if t < self.t0:
            return
        alpha = 1.0
        if self.t1 is not None:
            if t > self.t1 + 0.25:
                return
            alpha = clamp(1 - (t - self.t1) / 0.25)
        lh = int(self.size * 1.55)
        shown = int((t - self.t0) * self.cps) if self.cps else 10 ** 9
        scale = ease_out_back((t - self.t0) / 0.35) if self.pop else 1.0
        for i, line in enumerate(self.lines):
            if shown <= 0:
                break
            part = line[:shown]
            shown -= len(line)
            full = text_img(line, self.size, self.color, self.outline)
            cy = self.y + i * lh
            if part == line:
                paste_center(img, full, W / 2, cy, scale, alpha)
            else:
                im = text_img(part, self.size, self.color, self.outline)
                left = W / 2 - full.width / 2
                img.paste(im, (int(left), int(cy - im.height / 2)), im)


# ------------------------------------------------------------ bloco 3D iso
FACES = {  # origem, U, V, normal
    "top": ((-1, 1, -1), (2, 0, 0), (0, 0, 2), (0, 1, 0)),
    "front": ((-1, 1, 1), (2, 0, 0), (0, -2, 0), (0, 0, 1)),
    "back": ((1, 1, -1), (-2, 0, 0), (0, -2, 0), (0, 0, -1)),
    "right": ((1, 1, 1), (0, 0, -2), (0, -2, 0), (1, 0, 0)),
    "left": ((-1, 1, -1), (0, 0, 2), (0, -2, 0), (-1, 0, 0)),
}


def draw_iso_block(img, cx, cy, s, theta, phi=0.55, top=GRASS_TOP, side=GRASS_SIDE):
    ct, st, cp, sp = math.cos(theta), math.sin(theta), math.cos(phi), math.sin(phi)
    ry = np.array([[ct, 0, st], [0, 1, 0], [-st, 0, ct]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    R = rx @ ry
    arr = np.array(img)
    light = np.array([-0.4, 0.75, 0.55])
    light /= np.linalg.norm(light)
    for name, (o, u, v, n) in FACES.items():
        rn = R @ np.array(n, float)
        if rn[2] <= 0.02:
            continue
        shade = 0.5 + 0.5 * max(0.0, float(rn @ light))
        tex = top if name == "top" else side
        o3, u3, v3 = R @ np.array(o, float), R @ np.array(u, float), R @ np.array(v, float)
        O = np.array([cx + s * o3[0], cy - s * o3[1]])
        U = np.array([s * u3[0], -s * u3[1]])
        V = np.array([s * v3[0], -s * v3[1]])
        det = U[0] * V[1] - U[1] * V[0]
        if abs(det) < 1e-3:
            continue
        pts = np.array([O, O + U, O + V, O + U + V])
        x0, y0 = np.floor(pts.min(0)).astype(int)
        x1, y1 = np.ceil(pts.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        py, px = np.mgrid[y0:y1, x0:x1]
        dx, dy = px + 0.5 - O[0], py + 0.5 - O[1]
        sc = (dx * V[1] - dy * V[0]) / det
        tc = (U[0] * dy - U[1] * dx) / det
        m = (sc >= 0) & (sc < 1) & (tc >= 0) & (tc < 1)
        ti = np.clip((tc * 16).astype(int), 0, 15)
        si = np.clip((sc * 16).astype(int), 0, 15)
        col = tex[ti, si].astype(float) * shade
        sub = arr[y0:y1, x0:x1]
        sub[m] = col[m].astype(np.uint8)
    img.paste(Image.fromarray(arr))


# ------------------------------------------------------------- sprites
def outline_sprite(a, color=(20, 20, 20, 255)):
    filled = a[..., 3] > 0
    o = np.zeros_like(filled)
    o[1:] |= filled[:-1]
    o[:-1] |= filled[1:]
    o[:, 1:] |= filled[:, :-1]
    o[:, :-1] |= filled[:, 1:]
    a[o & ~filled] = color
    return a


def make_pickaxe():
    a = np.zeros((16, 16, 4), np.uint8)
    for x in range(1, 11):  # cabo
        a[15 - x, x] = (137, 103, 39, 255) if x % 2 else (104, 78, 30, 255)
    head_outer = [(5, 1), (6, 1), (7, 1), (8, 1), (9, 2), (10, 2), (11, 3), (12, 4), (13, 5),
                  (13, 6), (14, 7), (14, 8), (14, 9)]
    head_inner = [(5, 2), (6, 2), (7, 2), (8, 2), (9, 3), (10, 3), (11, 4), (12, 5), (12, 6),
                  (13, 7), (13, 8), (13, 9)]
    for x, y in head_outer:
        a[y, x] = (161, 251, 232, 255)
    for x, y in head_inner:
        a[y, x] = (51, 235, 203, 255)
    for x, y in [(4, 2), (14, 10), (10, 4), (11, 5)]:
        a[y, x] = (20, 140, 120, 255)
    a = outline_sprite(a)
    return Image.fromarray(a[:, ::-1].copy())  # cabeça para a esquerda


def make_diamond():
    a = np.zeros((16, 16, 4), np.uint8)
    for y in range(16):
        for x in range(16):
            d = abs(x - 7.5) + abs(y - 7.5)
            if d <= 6.5:
                if x + y < 12:
                    c = (209, 255, 247)
                elif x + y < 17:
                    c = (74, 237, 217)
                else:
                    c = (24, 146, 128)
                a[y, x] = c + (255,)
    return Image.fromarray(outline_sprite(a, (14, 63, 54, 255)))


def make_cracks(seed=11):
    r = np.random.default_rng(seed)
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]
    branches = []
    for b in range(5):
        x, y = 8, 8
        main = dirs[r.integers(0, 8)]
        path = []
        for _ in range(9):
            d = main if r.random() < 0.6 else dirs[r.integers(0, 8)]
            x, y = int(clamp(x + d[0], 0, 15)), int(clamp(y + d[1], 0, 15))
            path.append((x, y))
        branches.append(path)
    order = [(8, 8)]
    for step in range(9):
        for p in branches:
            if p[step] not in order:
                order.append(p[step])
    stages = []
    for s in range(10):
        m = np.zeros((16, 16, 4), np.uint8)
        for x, y in order[: max(1, int(len(order) * (s + 1) / 10))]:
            m[y, x] = (0, 0, 0, 170)
        stages.append(Image.fromarray(m))
    return stages


PICKAXE = make_pickaxe()
DIAMOND = make_diamond()
CRACKS = make_cracks()

CREEPER_FACE = [(1, 2), (2, 2), (1, 3), (2, 3), (5, 2), (6, 2), (5, 3), (6, 3), (3, 4), (4, 4),
                (2, 5), (3, 5), (4, 5), (5, 5), (2, 6), (3, 6), (4, 6), (5, 6), (2, 7), (5, 7)]
PAL_PIG = np.array([(240, 163, 163), (226, 140, 140), (248, 180, 175), (214, 128, 128)], float)
PAL_CREEPER = np.array([(13, 168, 13), (84, 201, 73), (26, 120, 26), (150, 214, 140)], float)
MOB_NOISE = np.random.default_rng(21).choice(4, size=(30, 26), p=[0.45, 0.25, 0.2, 0.1])


def draw_mob(img, cx, feet_y, k, m, flash=0.0, walk=0.0, glitch=0.0, seed=0):
    cw, ch = 26, 30
    a = np.zeros((ch, cw, 4), np.uint8)
    pal = PAL_PIG * (1 - m) + PAL_CREEPER * m
    col = np.concatenate([pal[MOB_NOISE], np.full((ch, cw, 1), 255.0)], axis=2)
    bw, bh = int(round(lerp(14, 8, m))), int(round(lerp(7, 12, m)))
    lh, lw = int(round(lerp(4, 6, m))), 4
    mid, bottom = cw // 2, ch
    lift = int(round(abs(math.sin(walk)) * 1.0))

    def fill(x0, y0, x1, y1, darken=1.0):
        x0, x1 = max(0, x0), min(cw, x1)
        y0, y1 = max(0, y0), min(ch, y1)
        c = col[y0:y1, x0:x1].copy()
        c[..., :3] *= darken
        a[y0:y1, x0:x1] = c.astype(np.uint8)

    bx0 = mid - bw // 2
    fill(bx0, bottom - lh - (lift if math.sin(walk) > 0 else 0), bx0 + lw, bottom, 0.8)
    fill(bx0 + bw - lw, bottom - lh - (lift if math.sin(walk) <= 0 else 0), bx0 + bw, bottom, 0.8)
    fill(bx0, bottom - lh - bh, bx0 + bw, bottom - lh)
    hx = int(round(lerp(bx0 - 3, mid - 4, m)))
    hy = int(round(lerp(bottom - lh - bh - 4, bottom - lh - bh - 8, m)))
    fill(hx, hy, hx + 8, hy + 8, 1.05)
    if m >= 0.5:
        for x, y in CREEPER_FACE:
            a[hy + y, hx + x] = (12, 30, 12, 255)
    else:
        for x in range(2, 6):
            for y in range(4, 7):
                a[hy + y, hx + x] = (246, 190, 184, 255)
        a[hy + 5, hx + 2] = a[hy + 5, hx + 5] = (150, 86, 86, 255)
        a[hy + 3, hx + 1] = a[hy + 3, hx + 6] = (255, 255, 255, 255)
        a[hy + 3, hx + 2] = a[hy + 3, hx + 5] = (0, 0, 0, 255)
    if flash > 0:
        a[..., :3] = (a[..., :3] * (1 - flash) + 255 * flash).astype(np.uint8)
    if glitch > 0:
        r = np.random.default_rng(seed)
        for y in range(ch):
            if r.random() < glitch:
                a[y] = np.roll(a[y], int(r.integers(-4, 5)), axis=0)
    im = Image.fromarray(a).resize((cw * k, ch * k), Image.NEAREST)
    img.paste(im, (int(cx - im.width / 2), int(feet_y - im.height)), im)


def draw_dragon(img, cx, cy, phase, k=4):
    c = Image.new("RGBA", (82, 46), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    f = math.sin(phase)
    f2 = math.sin(phase - 0.6)
    d.polygon([(34, 21), (52, 21), (62, 22 - 15 * f2), (40, 22 - 19 * f2)], fill=(30, 26, 38, 255))
    d.polygon([(56, 22), (81, 26), (81, 27), (56, 29)], fill=(24, 24, 28, 255))
    d.rectangle((24, 20, 56, 30), fill=(24, 24, 28, 255))
    d.rectangle((26, 28, 54, 30), fill=(40, 40, 48, 255))
    d.rectangle((12, 20, 24, 25), fill=(24, 24, 28, 255))
    d.rectangle((2, 17, 14, 26), fill=(28, 28, 32, 255))
    d.rectangle((0, 21, 4, 26), fill=(28, 28, 32, 255))
    d.rectangle((10, 14, 11, 17), fill=(70, 70, 70, 255))
    d.rectangle((5, 19, 7, 20), fill=PURPLE + (255,))
    for x in range(26, 70, 6):
        d.rectangle((x, 18 if x < 56 else 22, x + 1, 20 if x < 56 else 24), fill=(80, 80, 80, 255))
    d.rectangle((30, 30, 33, 36), fill=(24, 24, 28, 255))
    d.rectangle((46, 30, 49, 36), fill=(24, 24, 28, 255))
    d.polygon([(28, 21), (48, 21), (54, 22 - 19 * f), (26, 22 - 22 * f)], fill=(46, 42, 58, 255))
    d.line([(48, 21), (54, 22 - 19 * f)], fill=(18, 18, 22, 255))
    im = c.resize((82 * k, 46 * k), Image.NEAREST)
    img.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)
    # brilho dos olhos
    ImageDraw.Draw(img).rectangle(
        (cx - im.width / 2 + 5 * k - 2, cy - im.height / 2 + 19 * k - 2,
         cx - im.width / 2 + 8 * k + 1, cy - im.height / 2 + 21 * k + 1), outline=(255, 180, 255))


CURSOR_ROWS = [
    "X...........", "XX..........", "XWX.........", "XWWX........", "XWWWX.......",
    "XWWWWX......", "XWWWWWX.....", "XWWWWWWX....", "XWWWWWWWX...", "XWWWWWWWWX..",
    "XWWWWWXXXXX.", "XWWXWWX.....", "XWX.XWWX....", "XX..XWWX....", "X....XWWX...",
    ".....XWWX...", "......XX....",
]


def make_cursor():
    a = np.zeros((len(CURSOR_ROWS), 12, 4), np.uint8)
    for y, row in enumerate(CURSOR_ROWS):
        for x, ch in enumerate(row):
            if ch == "X":
                a[y, x] = (0, 0, 0, 255)
            elif ch == "W":
                a[y, x] = (255, 255, 255, 255)
    return Image.fromarray(a).resize((36, len(CURSOR_ROWS) * 3), Image.NEAREST)


CURSOR = make_cursor()


def particles(seed, n, spread=1.0):
    r = np.random.default_rng(seed)
    ang = r.uniform(0, 2 * math.pi, n)
    spd = r.uniform(120, 420, n) * spread
    return list(zip(np.cos(ang) * spd, np.sin(ang) * spd - 150 * spread, r.uniform(6, 16, n),
                    r.uniform(0, 1, n)))


# --------------------------------------------------------- cena: intro
def build_terrain():
    bs, cols = 32, 160
    strip = Image.new("RGBA", (bs * cols, H), (0, 0, 0, 0))
    gs, dt, st = block_img(GRASS_SIDE, bs), block_img(DIRT, bs), block_img(STONE, bs)
    lg, lv = block_img(LOG, bs), block_img(LEAVES, bs)
    heights = []
    for i in range(cols):
        h = 2 + round(1.2 * math.sin(i * 0.33) + 0.9 * math.sin(i * 0.11 + 1.3))
        heights.append(h)
    for i, h in enumerate(heights):
        top = 700 - bs * h
        strip.paste(gs, (i * bs, top))
        for j in range(1, 4):
            strip.paste(dt, (i * bs, top + j * bs))
        y = top + 4 * bs
        while y < H:
            strip.paste(st, (i * bs, y))
            y += bs
    for i in range(6, cols - 3, 13):
        top = 700 - bs * heights[i]
        for j in range(1, 5):
            strip.paste(lg, (i * bs, top - j * bs))
        for dx in range(-2, 3):
            for dy in range(4, 7):
                if abs(dx) == 2 and dy == 6:
                    continue
                strip.paste(lv, ((i + dx) * bs, top - dy * bs))
    return strip


TERRAIN = build_terrain()
SKY = vgrad((112, 160, 255), (196, 222, 255))
CLOUDS = [(30, 120, 140, 28), (300, 200, 180, 32), (520, 90, 120, 24), (700, 260, 160, 28)]


def make_logo():
    size = 52
    txt = "MINECRAFT"
    f = font(size)
    w, h = len(txt) * size + 40, size + 40
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((20, 14), txt, font=f, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    for o in range(-4, 5, 2):
        for p in range(-4, 5, 2):
            out.paste(dark, (o, p), mask)
    for dpt in range(1, 9):
        out.paste(Image.new("RGBA", (w, h), (52, 52, 52, 255)), (0, dpt), mask)
    stone = Image.fromarray(tiled("STONE", 48, 1.15)[:h, :w])
    out.paste(stone, (0, 0), mask)
    return out


LOGO = make_logo()


def intro_bg(t, title=True):
    img = Image.fromarray(SKY)
    d = ImageDraw.Draw(img)
    d.rectangle((400, 110, 470, 180), fill=(255, 244, 150))
    d.rectangle((410, 120, 460, 170), fill=(255, 252, 210))
    for x0, y, w, h in CLOUDS:
        x = (x0 - t * 14) % (W + 300) - 150
        d.rectangle((x, y, x + w, y + h), fill=(246, 246, 252))
        d.rectangle((x + 20, y - 12, x + w - 30, y), fill=(246, 246, 252))
    off = int(t * 46) % (TERRAIN.width - W)
    crop = TERRAIN.crop((off, 0, off + W, H))
    img.paste(crop, (0, 0), crop)
    return img


INTRO_TEXTS = [T(1.9, "O JOGO DE BLOCOS MAIS FAMOSO DO MUNDO", 20, 440, WHITE, cps=30, outline=True)]


def scene_intro(t):
    img = intro_bg(t)
    y = lerp(-150, 250, ease_out_bounce(t / 1.0))
    paste_center(img, LOGO, W / 2, y)
    if t > 1.1:
        sc = ease_out_back((t - 1.1) / 0.3) * (1 + 0.07 * math.sin((t - 1.1) * 2 * math.pi * 1.6))
        paste_center(img, text_img("EM 1 MINUTO!", 20, (255, 255, 0)), 380, 330, sc, angle=16)
    for it in INTRO_TEXTS:
        it.draw(img, t)
    return img


# ------------------------------------------------------- cena: história
HIST_TEXTS = [
    T(0.1, "CAPÍTULO 1", 16, 100, YELLOW, pop=True),
    T(0.25, "COMO TUDO COMEÇOU", 24, 145, WHITE, cps=30),
    T(1.0, "2009", 32, 500, YELLOW, pop=True, outline=True),
    T(1.2, "NOTCH CRIA A PRIMEIRA VERSÃO EM SÓ 6 DIAS", 16, 548, WHITE, cps=40),
    T(2.9, "2011", 32, 635, YELLOW, pop=True, outline=True),
    T(3.1, "LANÇAMENTO OFICIAL: VERSÃO 1.0", 16, 683, WHITE, cps=40),
    T(4.6, "2014", 32, 770, YELLOW, pop=True, outline=True),
    T(4.8, "A MICROSOFT COMPRA POR US$ 2,5 BILHÕES", 16, 818, WHITE, cps=40),
]


def scene_history(t):
    img = tiled_bg("DIRT", 64, 0.3, 0, -t * 12)
    s = 92 * ease_out_back((t - 0.2) / 0.5)
    if s > 1:
        cy = 330 + 8 * math.sin(t * 2.2)
        sh = Image.new("RGBA", (220, 30), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((0, 0, 219, 29), fill=(0, 0, 0, 90))
        paste_center(img, sh, W / 2, 452, s / 92)
        draw_iso_block(img, W / 2, cy, s, t * 1.1 + 0.6)
    for it in HIST_TEXTS:
        it.draw(img, t)
    return img


# --------------------------------------------------------- cena: vendas
ORB_N = 24
_ro = np.random.default_rng(31)
ORBS = [(0.6 + i * 0.12, _ro.uniform(50, 490), _ro.uniform(470, 720), _ro.uniform(70, 470))
        for i in range(ORB_N)]
ORB_TRAVEL = 0.6
SALES_TEXTS = [
    T(0.15, "MAIS DE", 24, 215, WHITE, pop=True),
    T(0.6, "CÓPIAS VENDIDAS", 24, 375, WHITE, pop=True),
    T(4.4, "O JOGO MAIS VENDIDO DA HISTÓRIA!", 24, 520, YELLOW, pop=True, outline=True),
]
LEVELUP_T = 4.2


def scene_sales(t):
    img = tiled_bg("STONE", 64, 0.28, t * 8, 0)
    d = ImageDraw.Draw(img)
    v = 300_000_000 * ease_out_cubic((t - 0.4) / 3.2)
    num = f"{int(v):,}".replace(",", ".")
    paste_center(img, text_img(num, 40, GREEN_XP, True), W / 2, 295, ease_out_back(t / 0.3))
    for s0, x0, y0, tx in ORBS:
        if s0 <= t < s0 + ORB_TRAVEL:
            p = (t - s0) / ORB_TRAVEL
            e = ease_in(p)
            x = lerp(x0, tx, e)
            y = lerp(y0, 836, e) - 80 * math.sin(math.pi * p)
            c = mix((128, 255, 32), (255, 255, 80), 0.5 + 0.5 * math.sin(t * 20 + x0))
            r = 7 * ease_out_back(p / 0.2)
            d.rectangle((x - r - 3, y - r - 3, x + r + 3, y + r + 3), fill=(40, 90, 10))
            d.rectangle((x - r, y - r, x + r, y + r), fill=c)
            d.rectangle((x - r / 2, y - r / 2, x + r / 2, y + r / 2), fill=(255, 255, 220))
    arrived = sum(1 for s0, *_ in ORBS if t >= s0 + ORB_TRAVEL)
    frac = clamp((t - 1.0) / (LEVELUP_T - 1.0))
    bx0, bx1, by = 50, 490, 836
    d.rectangle((bx0 - 3, by - 3, bx1 + 3, by + 15), fill=(0, 0, 0))
    d.rectangle((bx0, by, bx1, by + 12), fill=(48, 48, 48))
    flash = clamp(1 - (t - LEVELUP_T) / 0.4) if t >= LEVELUP_T else 0
    d.rectangle((bx0, by, bx0 + (bx1 - bx0) * frac, by + 12), fill=mix(GREEN_XP, WHITE, flash))
    for i in range(1, 18):
        x = bx0 + i * (bx1 - bx0) / 18
        d.line((x, by, x, by + 12), fill=(0, 0, 0))
    lvl = int(30 * frac) if arrived else 0
    lsc = 1 + 0.6 * flash
    paste_center(img, text_img(str(lvl), 24, GREEN_XP, True), W / 2, by - 30, lsc)
    for it in SALES_TEXTS:
        it.draw(img, t)
    return img


# -------------------------------------------------------- cena: creeper
NIGHT = vgrad((8, 12, 36), (36, 46, 96))
_rs = np.random.default_rng(41)
STARS = [(_rs.uniform(0, W), _rs.uniform(0, 520), _rs.uniform(0, 6.28)) for _ in range(70)]
GROUND_Y = 780


def build_ground(tex_top, tex_fill, bs=48, hole=None):
    g = Image.new("RGBA", (W, H - GROUND_Y), (0, 0, 0, 0))
    top, fill = block_img(tex_top, bs), block_img(tex_fill, bs)
    for i in range(W // bs + 1):
        x = i * bs
        depth = 0
        if hole and abs(x + bs / 2 - hole[0]) < hole[1]:
            depth = 1 + int(abs(x + bs / 2 - hole[0]) < hole[1] * 0.5)
        y = depth * bs
        first = True
        while y < H - GROUND_Y:
            g.paste(top if first and depth == 0 else fill, (x, y))
            first = False
            y += bs
    return g


GROUND = build_ground(GRASS_SIDE, DIRT)
GROUND_HOLE = build_ground(GRASS_SIDE, DIRT, hole=(W / 2, 130))
EXPLO = particles(51, 90, 1.3)
CREEPER_TEXTS = [
    T(0.3, "SABIA QUE O CREEPER NASCEU DE UM ERRO?", 24, 130, WHITE, cps=30, t1=5.4),
    T(2.6, "NOTCH TROCOU ALTURA E COMPRIMENTO AO CRIAR O PORCO!", 16, 240, YELLOW, cps=40, t1=5.4),
    T(5.7, "TSSSSS...", 32, 220, (120, 255, 120), cps=8, outline=True, t1=6.95),
    T(7.15, "BOOM!", 48, 260, ORANGE, pop=True, outline=True),
    T(7.6, "...E VIROU O MOB MAIS FAMOSO!", 16, 340, WHITE, cps=40),
]
FUSE_T, BOOM_T = 5.6, 7.0
OINKS = (0.7, 1.5)
MORPH_T = 2.4


def scene_creeper(t):
    img = Image.fromarray(NIGHT)
    d = ImageDraw.Draw(img)
    for x, y, ph in STARS:
        b = int(150 + 105 * math.sin(t * 3 + ph))
        d.rectangle((x, y, x + 2, y + 2), fill=(b, b, b))
    d.rectangle((420, 400, 480, 460), fill=(232, 232, 214))
    d.rectangle((430, 414, 442, 426), fill=(196, 196, 180))
    d.rectangle((456, 436, 466, 446), fill=(196, 196, 180))
    boomed = t >= BOOM_T
    g = GROUND_HOLE if boomed else GROUND
    img.paste(g, (0, GROUND_Y), g)
    if not boomed:
        m = ease_in_out((t - MORPH_T) / 1.0)
        x = lerp(-140, W / 2, ease_out_cubic(t / 2.2))
        moving = t < 2.2 or 3.4 <= t < 5.6
        k = 8
        if t >= 3.4:
            k = int(round(lerp(8, 15, ease_in_out((t - 3.4) / 2.2))))
        flash, swell = 0.0, 1.0
        if t >= FUSE_T:
            p = (t - FUSE_T) / (BOOM_T - FUSE_T)
            flash = 0.85 if math.sin((t - FUSE_T) * (8 + 30 * p)) > 0 else 0.0
            swell = 1 + 0.15 * p
        glitch = 0.5 if MORPH_T <= t < MORPH_T + 1.0 else 0.0
        draw_mob(img, x, GROUND_Y + 2, max(1, int(k * swell)), m, flash,
                 t * 9 if moving else 0, glitch, int(t * 30))
    else:
        te = t - BOOM_T
        for vx, vy, sz, sh in EXPLO:
            life = 0.6 + sh * 0.9
            if te < life:
                x = W / 2 + vx * te
                y = 560 + vy * te + 260 * te * te
                c = int(lerp(255, 90, te / life))
                s = sz * (1 + te * 1.5)
                d.rectangle((x - s / 2, y - s / 2, x + s / 2, y + s / 2), fill=(c, c, c))
        fl = clamp(1 - te / 0.45)
        if fl > 0:
            img = Image.blend(img, Image.new("RGB", (W, H), WHITE), fl)
    for it in CREEPER_TEXTS:
        it.draw(img, t)
    if boomed:
        te = t - BOOM_T
        amp = 22 * math.exp(-te / 0.3)
        dx, dy = int(amp * math.sin(te * 70)), int(amp * math.cos(te * 53))
        arr = np.roll(np.array(img), (dy, dx), axis=(0, 1))
        img = Image.fromarray(arr)
    return img


# --------------------------------------------------------- cena: mineração
HITS = [0.7 + i * 0.3 for i in range(10)]
BREAK_T = 3.7
GRAB_T = 4.6
GRAB_DUR = 0.35
SLOT = 52
HOTBAR_X = (W - 9 * SLOT) // 2
HOTBAR_Y = 800
_rm = np.random.default_rng(61)
FRAGS = [(_rm.uniform(-1, 1), _rm.uniform(-1, 1), _rm.uniform(-260, 260), _rm.uniform(-380, -80),
          _rm.integers(0, 16), _rm.integers(0, 16)) for _ in range(36)]
VIGNETTE = None


def make_vignette():
    yy, xx = np.mgrid[0:H, 0:W]
    dd = np.sqrt(((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - 420) / (H * 0.55)) ** 2)
    return np.clip(1.15 - dd, 0.25, 1.0)[..., None]


VIGNETTE = make_vignette()
MINING_TEXTS = [
    T(0.1, "PROCURANDO DIAMANTES?", 24, 115, AQUA, cps=30, outline=True),
    T(4.9, "DICA:", 16, 585, YELLOW, pop=True),
    T(5.1, "A MELHOR ALTURA:\nY = -59", 24, 630, WHITE, cps=30, outline=True),
    T(6.6, "(DESDE A VERSÃO 1.18)", 16, 720, GRAY, cps=40),
]


def draw_hotbar(img, t):
    d = ImageDraw.Draw(img)
    for i in range(9):
        x = HOTBAR_X + i * SLOT
        d.rectangle((x, HOTBAR_Y, x + SLOT, HOTBAR_Y + SLOT), fill=(30, 30, 30))
        d.rectangle((x + 3, HOTBAR_Y + 3, x + SLOT - 3, HOTBAR_Y + SLOT - 3), fill=(110, 110, 110))
        d.rectangle((x + 6, HOTBAR_Y + 6, x + SLOT - 6, HOTBAR_Y + SLOT - 6), fill=(139, 139, 139))
    d.rectangle((HOTBAR_X - 3, HOTBAR_Y - 3, HOTBAR_X + SLOT + 3, HOTBAR_Y + SLOT + 3),
                outline=WHITE, width=4)
    if t >= GRAB_T + GRAB_DUR:
        paste_center(img, DIAMOND.resize((40, 40), Image.NEAREST), HOTBAR_X + SLOT / 2,
                     HOTBAR_Y + SLOT / 2, ease_out_back((t - GRAB_T - GRAB_DUR) / 0.25))
        n = min(64, 1 + int(max(0, t - 5.6) * 40))
        im = text_img(str(n), 16, WHITE)
        img.paste(im, (HOTBAR_X + SLOT - im.width + 2, HOTBAR_Y + SLOT - im.height + 2), im)


def scene_mining(t):
    arr = np.array(tiled_bg("STONE", 64, 1.0), float) * VIGNETTE * 0.75
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    bx, by, bs = W / 2, 400, 192
    if t < BREAK_T:
        blk = block_img(DIAMOND_ORE, bs)
        hits = sum(1 for h in HITS if t >= h)
        if hits:
            cr = CRACKS[min(9, hits - 1)].resize((bs, bs), Image.NEAREST)
            blk = blk.convert("RGBA")
            blk.alpha_composite(cr)
        recoil = 0
        for h in HITS:
            if 0 <= t - h < 0.08:
                recoil = 4
        paste_center(img, blk.convert("RGBA"), bx + recoil, by + recoil)
        d.rectangle((bx - bs / 2, by - bs / 2, bx + bs / 2, by + bs / 2), outline=(0, 0, 0), width=2)
        for i, h in enumerate(HITS):  # faíscas por golpe
            te = t - h
            if 0 <= te < 0.4:
                r = np.random.default_rng(i)
                for _ in range(5):
                    vx, vy = r.uniform(-160, 160), r.uniform(-260, -60)
                    x = bx + 70 + vx * te
                    y = by + 70 + vy * te + 700 * te * te
                    d.rectangle((x - 4, y - 4, x + 4, y + 4), fill=(100, 100, 100))
    else:
        te = t - BREAK_T
        for fx, fy, vx, vy, ti, si in FRAGS:
            if te < 1.0:
                x = bx + fx * bs / 2 + vx * te
                y = by + fy * bs / 2 + vy * te + 900 * te * te
                c = tuple(int(v) for v in DIAMOND_ORE[ti, si])
                d.rectangle((x - 7, y - 7, x + 7, y + 7), fill=c)
        if t < GRAB_T + GRAB_DUR:
            spin = abs(math.cos(te * 2.6)) * 0.85 + 0.15
            if t < GRAB_T:
                x, y, sc = bx, by + 10 * math.sin(te * 3), 72 * ease_out_back(te / 0.3)
            else:
                p = ease_in((t - GRAB_T) / GRAB_DUR)
                x = lerp(bx, HOTBAR_X + SLOT / 2, p)
                y = lerp(by, HOTBAR_Y + SLOT / 2, p)
                sc = lerp(72, 40, p)
            if sc > 1:
                im = DIAMOND.resize((max(1, int(sc * spin)), int(sc)), Image.NEAREST)
                paste_center(img, im, x, y)
    # picareta
    if t < BREAK_T + 0.4:
        p = ((t - 0.55) % 0.3) / 0.3 if 0.55 <= t < HITS[-1] + 0.15 else 0.0
        ang = -40 + 40 * math.cos(2 * math.pi * p) if t >= 0.55 else 0
        slide = 0
        if t < 0.5:
            slide = 300 * (1 - ease_out_cubic(t / 0.5))
        if t > BREAK_T:
            slide = 400 * ease_in((t - BREAK_T) / 0.4)
        pk = PICKAXE.resize((176, 176), Image.NEAREST)
        canvas = Image.new("RGBA", (420, 420), (0, 0, 0, 0))
        canvas.paste(pk, (210 - 165, 210 - 165), pk)  # ponta do cabo no centro
        rot = canvas.rotate(ang, Image.NEAREST)
        img.paste(rot, (int(468 - 210 + slide), int(615 - 210 + slide)), rot)
    draw_hotbar(img, t)
    for it in MINING_TEXTS:
        it.draw(img, t)
    return img


# ---------------------------------------------------------- cena: nether
PB = 56
PORTAL_X0, PORTAL_Y0 = W / 2 - 2 * PB, 170
IGNITE_T = 0.6
_rn = np.random.default_rng(71)
EMBERS = [(_rn.uniform(0, W), _rn.uniform(0, H), _rn.uniform(30, 90), _rn.uniform(0, 6.28))
          for _ in range(45)]
PPART = [(_rn.uniform(-150, 150), _rn.uniform(-40, 330), _rn.uniform(0, 6.28)) for _ in range(30)]
REDGLOW = (np.linspace(0, 1, H) ** 2)[:, None, None] * np.array([90, 22, 0], float)
NETHER_TEXTS = [
    T(0.1, "O NETHER", 40, 95, RED, pop=True, outline=True),
    T(1.3, "ANDAR 1 BLOCO NO NETHER...", 24, 525, WHITE, cps=30),
    T(3.8, "VALE 8 BLOCOS NO MUNDO NORMAL!", 24, 700, YELLOW, cps=30, outline=True),
    T(5.3, "O ATALHO PERFEITO PRA VIAGENS LONGAS", 16, 790, GRAY, cps=40),
]
EQ_POPS = [2.3] + [2.9 + i * 0.1 for i in range(8)]


def portal_swirl(t, w, h, radius):
    tw, th = w // 4, h // 4
    yy, xx = np.mgrid[0:th, 0:tw].astype(float)
    v = (np.sin(xx * 0.5 + t * 3) + np.sin(yy * 0.35 - t * 2.3) + np.sin((xx + yy) * 0.3 + t * 4)
         + np.sin(np.hypot(xx - tw / 2, yy - th / 2) * 0.8 - t * 5))
    v = (v + 4) / 8
    c = np.stack([lerp(70, 190, v), lerp(10, 90, v), lerp(150, 255, v)], -1)
    dist = np.hypot((xx - tw / 2) / (tw / 2), (yy - th / 2) / (th / 2))
    a = np.where(dist <= radius * 1.5, 235, 0)
    img = np.concatenate([c, a[..., None]], -1).astype(np.uint8)
    return Image.fromarray(img).resize((tw * 4, th * 4), Image.NEAREST)


def scene_nether(t):
    arr = np.array(tiled_bg("NETHERRACK", 64, 0.42, 0, t * 6), float) + REDGLOW
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for x, y, sp, ph in EMBERS:
        yy = (y - t * sp) % H
        c = (255, int(140 + 80 * math.sin(t * 8 + ph)), 40)
        d.rectangle((x, yy, x + 3, yy + 3), fill=c)
    obs = block_img(OBSIDIAN, PB)
    for i in range(4):
        for j in range(5):
            if 0 < i < 3 and 0 < j < 4:
                continue
            img.paste(obs, (int(PORTAL_X0 + i * PB), int(PORTAL_Y0 + j * PB)))
    cx, cy = W / 2, PORTAL_Y0 + 2.5 * PB
    if t >= IGNITE_T:
        rad = ease_out_cubic((t - IGNITE_T) / 0.5)
        sw = portal_swirl(t, 2 * PB, 3 * PB, rad)
        img.paste(sw, (int(PORTAL_X0 + PB), int(PORTAL_Y0 + PB)), sw)
        for px, py, ph in PPART:
            yy = PORTAL_Y0 + py - ((t * 30 + ph * 20) % 60)
            xx = cx + px + 6 * math.sin(t * 3 + ph)
            d.rectangle((xx, yy, xx + 4, yy + 4), fill=(190, 90, 255))
    elif t > IGNITE_T - 0.3:
        d.rectangle((cx - 6, cy + PB - 6, cx + 6, cy + PB + 6), fill=(255, 200, 80))
    # 1 = 8
    y0, bs = 600, 40
    x = 44
    if t >= EQ_POPS[0]:
        paste_center(img, block_img(NETHERRACK, bs).convert("RGBA"), x + bs / 2, y0,
                     ease_out_back((t - EQ_POPS[0]) / 0.25))
        paste_center(img, text_img("=", 24, WHITE), x + bs + 30, y0, ease_out_back((t - EQ_POPS[0]) / 0.25))
    for i, tp in enumerate(EQ_POPS[1:]):
        if t >= tp:
            bx = x + bs + 60 + i * (bs + 4)
            paste_center(img, block_img(GRASS_SIDE, bs).convert("RGBA"), bx + bs / 2, y0,
                         ease_out_back((t - tp) / 0.25))
    for it in NETHER_TEXTS:
        it.draw(img, t)
    return img


PORTAL_CENTER = (W / 2, PORTAL_Y0 + 2.5 * PB)


# -------------------------------------------------------------- cena: end
END_SKY = vgrad((10, 6, 20), (40, 20, 58))
_re = np.random.default_rng(81)
END_STARS = [(_re.uniform(0, W), _re.uniform(0, 700), _re.uniform(0, 6.28)) for _ in range(90)]
END_GROUND = build_ground(END_STONE, END_STONE)
ROAR_T = 2.0
END_TEXTS = [
    T(0.2, "E NO FIM DE TUDO...", 24, 110, WHITE, cps=30),
    T(2.2, "O ENDER DRAGON TE ESPERA!", 24, 540, PURPLE, pop=True, outline=True),
    T(3.8, "MAS O JOGO NUNCA ACABA DE VERDADE.", 16, 640, (200, 200, 200), cps=40),
]


def draw_crystal(d, x, y, t):
    for r, ang, col in [(16, t * 2, (230, 120, 200)), (9, -t * 3, (255, 210, 245))]:
        pts = [(x + r * math.cos(ang + k * math.pi / 2), y + r * math.sin(ang + k * math.pi / 2))
               for k in range(4)]
        d.polygon(pts, outline=col, fill=None if r > 10 else col)


def scene_end(t):
    img = Image.fromarray(END_SKY)
    d = ImageDraw.Draw(img)
    for x, y, ph in END_STARS:
        b = int(130 + 120 * math.sin(t * 2.5 + ph))
        d.rectangle((x, y, x + 2, y + 2), fill=(b, b, min(255, b + 30)))
    obs = block_img(OBSIDIAN, 48)
    for px, ph in [(30, 6), (462, 8)]:
        for j in range(ph):
            img.paste(obs, (px, GROUND_Y - (j + 1) * 48))
        draw_crystal(d, px + 24, GROUND_Y - ph * 48 - 26 + 6 * math.sin(t * 3 + px), t)
    img.paste(END_GROUND, (0, GROUND_Y), END_GROUND)
    if t >= 0.3:
        p = ease_out_cubic((t - 0.3) / 1.7)
        x = lerp(W + 220, W / 2, p)
        y = lerp(200, 330, p) + 14 * math.sin(t * 2.2)
        draw_dragon(img, x, y, t * 7, k=5)
    for it in END_TEXTS:
        it.draw(img, t)
    if t >= ROAR_T:
        te = t - ROAR_T
        amp = 10 * math.exp(-te / 0.6) if te < 1.6 else 0
        if amp > 0.5:
            dx, dy = int(amp * math.sin(te * 60)), int(amp * math.cos(te * 47))
            img = Image.fromarray(np.roll(np.array(img), (dy, dx), axis=(0, 1)))
    return img


# ------------------------------------------------------------ cena: outro
TOAST_T = 0.3
CLICK_T = 3.0
OUTRO_TEXTS = [
    T(1.0, "CURTIU?", 48, 330, WHITE, pop=True, outline=True),
    T(3.4, "ATÉ A PRÓXIMA, MINERADOR!", 16, 590, WHITE, cps=35, outline=True),
]
OUTRO_DUR = 6.0


def draw_button(img, cx, cy, w, h, label, color, hover, pressed):
    d = ImageDraw.Draw(img)
    x0, y0 = cx - w / 2, cy - h / 2 + (3 if pressed else 0)
    d.rectangle((x0 - 3, y0 - 3, x0 + w + 3, y0 + h + 3), fill=WHITE if hover else (0, 0, 0))
    base = (120, 128, 180) if hover else (111, 111, 111)
    d.rectangle((x0, y0, x0 + w, y0 + h), fill=base)
    d.rectangle((x0, y0, x0 + w, y0 + 4), fill=mix(base, WHITE, 0.35))
    d.rectangle((x0, y0 + h - 6, x0 + w, y0 + h), fill=mix(base, (0, 0, 0), 0.4))
    paste_center(img, text_img(label, 24, color), cx, y0 + h / 2)


def scene_outro(t):
    img = intro_bg(t + 8)
    img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), 0.25)
    # toast de conquista
    p_in = ease_out_cubic((t - TOAST_T) / 0.4)
    p_out = ease_in((t - 4.8) / 0.4)
    ty = lerp(-90, 40, p_in) - 140 * p_out
    if ty > -90:
        tw, th = 420, 76
        tx = (W - tw) / 2
        d = ImageDraw.Draw(img)
        d.rectangle((tx - 3, ty - 3, tx + tw + 3, ty + th + 3), fill=(0, 0, 0))
        d.rectangle((tx, ty, tx + tw, ty + th), fill=(85, 85, 85))
        d.rectangle((tx + 4, ty + 4, tx + tw - 4, ty + th - 4), fill=(33, 33, 33))
        draw_iso_block(img, tx + 40, ty + th / 2, 18, 0.78)
        for txt, col, yy in [("CONQUISTA OBTIDA!", YELLOW, ty + 26), ("ASSISTIU ATÉ O FIM", WHITE, ty + 52)]:
            im = text_img(txt, 16, col)
            img.paste(im, (int(tx + 76), int(yy - im.height / 2)), im)
    # botão + cursor
    bcx, bcy = W / 2, 470
    cur_p = ease_in_out((t - 1.8) / 0.9)
    cx, cy = lerp(500, bcx + 60, cur_p), lerp(880, bcy + 4, cur_p)
    hover = cur_p > 0.92
    clicked = t >= CLICK_T
    pressed = CLICK_T <= t < CLICK_T + 0.12
    if t >= 1.5:
        sc = ease_out_back((t - 1.5) / 0.3)
        if sc > 0.98:
            draw_button(img, bcx, bcy, 360, 64, "SEGUINDO!" if clicked else "SEGUIR",
                        (85, 255, 85) if clicked else WHITE, hover, pressed)
        else:
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw_button(tmp, bcx, bcy, 360, 64, "SEGUIR", WHITE, False, False)
            tmp = tmp.crop((int(bcx - 190), int(bcy - 40), int(bcx + 190), int(bcy + 40)))
            paste_center(img, tmp, bcx, bcy, sc)
    for it in OUTRO_TEXTS:
        it.draw(img, t)
    if t >= 1.7:
        csc = 0.85 if pressed else 1.0
        im = CURSOR if csc == 1 else CURSOR.resize((int(36 * csc), int(CURSOR.height * csc)), Image.NEAREST)
        img.paste(im, (int(cx), int(cy)), im)
    fade = clamp((t - (OUTRO_DUR - 0.6)) / 0.6)
    if fade > 0:
        img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), fade)
    return img


# --------------------------------------------------------- linha do tempo
SCENES = [  # (nome, duração, função, transição para a próxima, duração da transição)
    ("intro", 5.0, scene_intro, "blocks", 0.8),
    ("history", 7.5, scene_history, "pixel", 0.6),
    ("sales", 7.0, scene_sales, "slide", 0.6),
    ("creeper", 8.5, scene_creeper, "fall", 0.8),
    ("mining", 9.0, scene_mining, "nblocks", 0.8),
    ("nether", 7.0, scene_nether, "portal", 1.0),
    ("end", 6.5, scene_end, "fade", 0.8),
    ("outro", OUTRO_DUR, scene_outro, None, 0),
]
STARTS = []
_acc = 0.0
for _s in SCENES:
    STARTS.append(_acc)
    _acc += _s[1]
TOTAL = _acc
NFRAMES = int(round(TOTAL * FPS))
SCN = {s[0]: STARTS[i] for i, s in enumerate(SCENES)}

CELL = 60
_rc = np.random.default_rng(91)
CELL_RAND = _rc.random((H // CELL + 1, W // CELL + 1))


def trans_blocks(a, b, p, tex, mode):
    rows, cols = CELL_RAND.shape
    out = (a if p < 0.5 else b).copy()
    blk = block_img(tex, CELL)
    q = p * 2 if p < 0.5 else (p - 0.5) * 2
    for r in range(rows):
        for c in range(cols):
            if mode == "random":
                rank = CELL_RAND[r, c] * 0.85
            else:  # empilha de baixo pra cima, revela de cima pra baixo
                rr = (rows - 1 - r) / rows if p < 0.5 else r / rows
                rank = rr * 0.75 + CELL_RAND[r, c] * 0.1
            covered = q >= rank if p < 0.5 else q < rank
            if covered:
                drop = 0
                if mode == "fall" and p < 0.5:
                    drop = -CELL * (1 - clamp((q - rank) / 0.12))
                out.paste(blk, (c * CELL, int(r * CELL + drop)))
    return out


def transition(kind, a, b, p):
    if kind == "blocks":
        return trans_blocks(a, b, p, DIRT, "random")
    if kind == "nblocks":
        return trans_blocks(a, b, p, NETHERRACK, "random")
    if kind == "fall":
        return trans_blocks(a, b, p, STONE, "fall")
    if kind == "pixel":
        src = a if p < 0.5 else b
        q = 1 - abs(p - 0.5) * 2
        f = int(1 + q * 40)
        small = src.resize((max(1, W // f), max(1, H // f)), Image.BILINEAR)
        return small.resize((W, H), Image.NEAREST)
    if kind == "slide":
        e = ease_in_out(p)
        out = Image.new("RGB", (W, H))
        out.paste(a, (0, int(-e * H)))
        out.paste(b, (0, int(H - e * H)))
        return out
    if kind == "portal":
        purple = Image.new("RGB", (W, H), (150, 60, 230))
        if p < 0.6:
            q = p / 0.6
            z = 1 + 7 * ease_in(q)
            cx, cy = PORTAL_CENTER
            w, h = W / z, H / z
            x0 = clamp(cx - w / 2, 0, W - w)
            y0 = clamp(cy - h / 2, 0, H - h)
            zoomed = a.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.NEAREST)
            return Image.blend(zoomed, purple, ease_in(q) * 0.9)
        q = (p - 0.6) / 0.4
        return Image.blend(purple, b, ease_out_cubic(q))
    if kind == "fade":
        black = Image.new("RGB", (W, H))
        return Image.blend(a, black, p * 2) if p < 0.5 else Image.blend(black, b, (p - 0.5) * 2)
    return b


def render(fi):
    t = fi / FPS
    i = 0
    while i + 1 < len(SCENES) and t >= STARTS[i + 1]:
        i += 1
    # transição em volta da fronteira anterior ou seguinte
    for j in (i - 1, i):
        if 0 <= j < len(SCENES) - 1:
            kind, td = SCENES[j][3], SCENES[j][4]
            bnd = STARTS[j + 1]
            if bnd - td / 2 <= t < bnd + td / 2:
                p = (t - (bnd - td / 2)) / td
                a = SCENES[j][2](t - STARTS[j])
                b = SCENES[j + 1][2](max(0.0, t - STARTS[j + 1]))
                return transition(kind, a, b, p).convert("RGB").tobytes()
    return SCENES[i][2](t - STARTS[i]).convert("RGB").tobytes()


# ================================================================== ÁUDIO
def tt(dur):
    return np.arange(int(dur * SR)) / SR


def noise(n, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, n)


def fft_band(x, lo=0.0, hi=SR / 2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def norm(x, peak=1.0):
    m = np.max(np.abs(x))
    return x / m * peak if m > 0 else x


def onepole(x, cut):
    cut = np.broadcast_to(cut, x.shape)
    y = np.zeros_like(x)
    s = 0.0
    for i in range(len(x)):
        a = 1 - math.exp(-2 * math.pi * cut[i] / SR)
        s += a * (x[i] - s)
        y[i] = s
    return y


def sfx_click():
    t = tt(0.06)
    return norm(fft_band(noise(len(t), 1), 1500, 6000) * np.exp(-t / 0.006)
                + 0.6 * np.sin(2 * math.pi * 950 * t) * np.exp(-t / 0.012), 0.55)


def sfx_tick(seed=0):
    t = tt(0.025)
    return norm(fft_band(noise(len(t), seed), 2500, 7000) * np.exp(-t / 0.004), 0.12)


def sfx_place(seed=0, vol=0.6):
    t = tt(0.16)
    s = fft_band(noise(len(t), seed + 3), 60, 900) * np.exp(-t / 0.03)
    s += 0.8 * np.sin(2 * math.pi * 110 * t) * np.exp(-t / 0.04)
    return norm(s, vol)


def sfx_dig(seed=0):
    t = tt(0.18)
    r = np.random.default_rng(seed)
    s = fft_band(noise(len(t), seed + 10), 350, 2600 + r.uniform(-500, 500)) * np.exp(-t / 0.035)
    s += 0.3 * fft_band(noise(len(t), seed + 11), 3000, 8000) * np.exp(-t / 0.01)
    return norm(s, 0.5)


def sfx_break():
    out = np.zeros(int(0.5 * SR))
    for k, off in enumerate([0, 0.03, 0.07, 0.12]):
        d = sfx_dig(40 + k) * (1 - k * 0.15)
        i = int(off * SR)
        out[i:i + len(d)] += d
    t = tt(0.5)
    out += 0.4 * fft_band(noise(len(t), 99), 40, 400) * np.exp(-t / 0.12)
    return norm(out, 0.75)


def sfx_pop():
    t = tt(0.1)
    f = np.linspace(500, 1300, len(t))
    return norm(np.sin(2 * math.pi * np.cumsum(f) / SR) * np.sin(math.pi * t / 0.1), 0.4)


def bell(f, dur, tau, vol):
    t = tt(dur)
    s = np.sin(2 * math.pi * f * t) + 0.35 * np.sin(2 * math.pi * 2.76 * f * t) * np.exp(-t / (tau / 3))
    s *= np.exp(-t / tau) * np.minimum(1, t / 0.003)
    return norm(s, vol)


def sfx_xp(seed=0):
    f = np.random.default_rng(seed).uniform(1500, 2400)
    return bell(f, 0.35, 0.09, 0.22)


def sfx_levelup():
    out = np.zeros(int(1.2 * SR))
    for k, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
        b = bell(f, 0.9, 0.35, 0.3)
        i = int(k * 0.07 * SR)
        out[i:i + len(b)] += b
    return out


def sfx_hiss(dur):
    t = tt(dur)
    s = fft_band(noise(len(t), 7), 2500, 12000)
    env = (t / dur) ** 0.6 * (1 + 0.2 * np.sin(2 * math.pi * 17 * t))
    return norm(s * env, 0.28)


def sfx_explosion():
    t = tt(2.2)
    br = np.cumsum(noise(len(t), 13))
    br -= np.convolve(br, np.ones(800) / 800, mode="same")
    br = norm(fft_band(br, 20, 1400))
    crack = fft_band(noise(len(t), 14), 800, 6000) * np.exp(-t / 0.08)
    thump = np.sin(2 * math.pi * (48 - 12 * t) * t) * np.exp(-t / 0.35)
    s = (br * np.exp(-t / 0.5) + 0.5 * crack + 0.9 * thump) * np.minimum(1, t / 0.004)
    return np.tanh(norm(s, 1.0) * 2.2) * 0.95


def sfx_oink(seed=0):
    out = np.zeros(int(0.4 * SR))
    for k in range(2):
        t = tt(0.13)
        f = 210 - 60 * t / 0.13 + 15 * np.sin(2 * math.pi * 35 * t)
        ph = 2 * math.pi * np.cumsum(f) / SR
        saw = (ph / (2 * math.pi)) % 1 * 2 - 1
        g = fft_band(saw, 80, 1600) * np.sin(math.pi * t / 0.13)
        i = int(k * 0.17 * SR)
        out[i:i + len(g)] += g * (1 - 0.2 * k)
    return norm(out, 0.4)


def sfx_glitch():
    t = tt(0.9)
    r = np.random.default_rng(5)
    f = np.repeat(r.uniform(150, 1600, 40), len(t) // 40 + 1)[: len(t)]
    sq = np.sign(np.sin(2 * math.pi * np.cumsum(f) / SR))
    sq = np.round(sq * 4) / 4
    return norm(sq * np.exp(-t / 0.6), 0.22)


def sfx_whoosh(dur=0.6, lo=300, hi=3500, vol=0.35, seed=3):
    t = tt(dur)
    cut = lo + (hi - lo) * np.sin(math.pi * t / dur) ** 2
    s = onepole(noise(len(t), seed), cut)
    return norm(s * np.sin(math.pi * t / dur), vol)


def sfx_ignite():
    t = tt(0.35)
    s = fft_band(noise(len(t), 21), 2000, 9000) * np.exp(-t / 0.04)
    s += 0.6 * fft_band(noise(len(t), 22), 200, 1500) * np.sin(math.pi * t / 0.35)
    return norm(s, 0.5)


def sfx_portal_hum(dur):
    t = tt(dur)
    lfo = np.sin(2 * math.pi * 0.6 * t)
    f = 70 + 8 * lfo
    s = np.sin(2 * math.pi * np.cumsum(f) / SR) + 0.6 * np.sin(2 * math.pi * np.cumsum(f * 1.51) / SR)
    s += 0.8 * fft_band(noise(len(t), 23), 100, 700) * (0.6 + 0.4 * lfo)
    env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.4)
    return norm(s * env, 0.16)


def sfx_portal_travel(dur=1.6):
    t = tt(dur)
    f = 150 * (6 ** (t / dur)) * (1 + 0.06 * np.sin(2 * math.pi * 7 * t))
    s = np.sin(2 * math.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * math.pi * np.cumsum(f * 1.5) / SR)
    s += 0.5 * sfx_whoosh(dur, 200, 5000, 1.0, 9)[: len(t)]
    env = np.minimum(1, t / 0.2) * np.minimum(1, (dur - t) / 0.25)
    return norm(s * env, 0.4)


def sfx_roar():
    t = tt(1.8)
    f = (95 - 30 * t / 1.8) * (1 + 0.05 * np.sin(2 * math.pi * 6 * t))
    ph = 2 * math.pi * np.cumsum(f) / SR
    saw = (ph / (2 * math.pi)) % 1 * 2 - 1
    growl = fft_band(noise(len(t), 31), 80, 900) * (0.6 + 0.4 * np.sin(2 * math.pi * 28 * t))
    s = fft_band(saw, 40, 2500) + 0.9 * growl
    env = np.minimum(1, t / 0.15) * np.exp(-np.maximum(0, t - 0.9) / 0.4)
    return np.tanh(norm(s * env, 1.0) * 2.0) * 0.45


def sfx_flap(seed=0):
    return sfx_whoosh(0.3, 80, 600, 0.18, seed)


def sfx_chime():
    out = np.zeros(int(1.2 * SR))
    for k, f in enumerate([783.99, 1046.5]):
        b = bell(f, 1.0, 0.4, 0.3)
        i = int(k * 0.13 * SR)
        out[i:i + len(b)] += b
    return out


def sfx_blips():
    out = np.zeros(int(0.5 * SR))
    for k in range(6):
        t = tt(0.05)
        f = 1400 - k * 180
        b = np.sign(np.sin(2 * math.pi * f * t)) * np.exp(-t / 0.02) * 0.12
        i = int(k * 0.05 * SR)
        out[i:i + len(b)] += b
    return out


def piano(midi, dur, vel):
    f = 440 * 2 ** ((midi - 69) / 12)
    t = tt(dur)
    s = np.zeros_like(t)
    for k, amp in enumerate([1, 0.45, 0.22, 0.1, 0.05], start=1):
        s += amp * np.sin(2 * math.pi * f * k * t * (1 + 0.0007 * k)) * np.exp(-t * (0.9 + 0.7 * k))
    return s * np.minimum(1, t / 0.005) * vel


def music(total):
    out = np.zeros(int((total + 4) * SR))
    beat = 0.72
    prog = [(41, [57, 60, 64, 65, 69]), (40, [55, 59, 60, 64, 67]),
            (38, [57, 60, 62, 65, 69]), (34, [57, 58, 62, 65, 70])]
    r = np.random.default_rng(101)
    bar = 0
    tpos = 0.3
    while tpos < total:
        bass, ch = prog[bar % 4]
        events = [(0, bass, 0.5, 3.5), (0, bass + 12, 0.3, 3.0)]
        for bt in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
            if r.random() < 0.62:
                events.append((bt, int(r.choice(ch)), r.uniform(0.12, 0.2), 2.2))
        if r.random() < 0.7:
            events.append((float(r.choice([0, 2])), int(r.choice(ch)) + 12, 0.16, 2.5))
        for bt, note, vel, dur in events:
            p = piano(note, dur, vel)
            i = int((tpos + bt * beat) * SR)
            out[i:i + len(p)] += p[: max(0, len(out) - i)]
        tpos += 4 * beat
        bar += 1
    return out[: int(total * SR)]


def build_audio():
    n = int(TOTAL * SR) + SR
    mixbuf = np.zeros(n)

    def add(t, s, gain=1.0):
        i = int(t * SR)
        if i < 0 or i >= n:
            return
        s = s[: n - i]
        mixbuf[i:i + len(s)] += s * gain

    def add_texts(t0, items):
        for it in items:
            if it.cps:
                for k in range(0, it.nchars, 2):
                    add(t0 + it.t0 + k / it.cps, sfx_tick(k))
            elif it.pop:
                add(t0 + it.t0, sfx_pop(), 0.6)

    # intro
    s = SCN["intro"]
    add(s + 0.05, sfx_click())
    for k, (bt, v) in enumerate([(0.36, 0.7), (0.73, 0.45), (0.91, 0.3)]):
        add(s + bt, sfx_place(k, v))
    add(s + 1.1, sfx_pop())
    add_texts(s, INTRO_TEXTS)
    # história
    s = SCN["history"]
    add_texts(s, HIST_TEXTS)
    add(s + 0.2, sfx_place(5, 0.7))
    # vendas
    s = SCN["sales"]
    add_texts(s, SALES_TEXTS)
    for k, (s0, *_rest) in enumerate(ORBS):
        add(s + s0 + ORB_TRAVEL, sfx_xp(k))
    add(s + LEVELUP_T, sfx_levelup(), 0.7)
    # creeper
    s = SCN["creeper"]
    add_texts(s, CREEPER_TEXTS)
    for k, ot in enumerate(OINKS):
        add(s + ot, sfx_oink(k))
    add(s + MORPH_T, sfx_glitch())
    for k in range(5):
        add(s + 3.45 + k * 0.45, sfx_place(20 + k, 0.25))
    add(s + FUSE_T, sfx_hiss(BOOM_T - FUSE_T))
    add(s + BOOM_T, sfx_explosion(), 0.8)
    # mineração
    s = SCN["mining"]
    add_texts(s, MINING_TEXTS)
    for k, h in enumerate(HITS):
        add(s + h, sfx_dig(k))
    add(s + BREAK_T, sfx_break())
    add(s + GRAB_T + GRAB_DUR, sfx_pop())
    for k in range(10):
        add(s + 5.6 + k * 0.15, sfx_xp(200 + k), 0.4)
    # nether
    s = SCN["nether"]
    add_texts(s, NETHER_TEXTS)
    add(s + IGNITE_T - 0.15, sfx_click(), 0.6)
    add(s + IGNITE_T, sfx_ignite())
    add(s + IGNITE_T + 0.1, sfx_portal_hum(7.0 - IGNITE_T))
    for k, tp in enumerate(EQ_POPS):
        add(s + tp, sfx_place(30 + k, 0.5))
    # end
    s = SCN["end"]
    add_texts(s, END_TEXTS)
    for k in range(10):
        add(s + 0.4 + k * 0.9, sfx_flap(k))
    add(s + ROAR_T, sfx_roar())
    # outro
    s = SCN["outro"]
    add_texts(s, OUTRO_TEXTS)
    add(s + TOAST_T, sfx_whoosh(0.4, 400, 3000, 0.2))
    add(s + TOAST_T + 0.3, sfx_chime())
    add(s + CLICK_T, sfx_click())
    add(s + CLICK_T + 0.08, sfx_levelup(), 0.7)
    # transições
    for j, (name, dur, _f, kind, td) in enumerate(SCENES[:-1]):
        b = STARTS[j + 1]
        t0 = b - td / 2
        if kind in ("blocks", "nblocks", "fall"):
            for k in range(7):
                add(t0 + k * td / 14, sfx_place(60 + k, 0.35))
        elif kind == "pixel":
            add(t0, sfx_blips())
        elif kind == "slide":
            add(t0, sfx_whoosh(td, 300, 4000, 0.35))
        elif kind == "portal":
            add(t0 - 0.3, sfx_portal_travel(td + 0.5))

    # trilha: some na tensão do creeper e volta depois
    mus = music(TOTAL)
    tm = np.arange(len(mus)) / SR
    cs, ms = SCN["creeper"], SCN["mining"]
    env = np.ones_like(tm)
    env = np.minimum(env, np.clip((tm - 0.0) / 0.3, 0, 1))
    duck = np.clip(((cs + 2.0) - tm) / 0.8, 0, 1) + np.clip((tm - (ms + 0.3)) / 1.2, 0, 1)
    env = env * np.clip(duck, 0, 1)
    env *= np.clip((TOTAL - tm) / 2.0, 0, 1)
    mus = norm(mus, 0.22) * env
    mixbuf[: len(mus)] += mus

    mixbuf = mixbuf[: int(TOTAL * SR)]
    mixbuf = np.tanh(mixbuf * 1.1)
    mixbuf = norm(mixbuf, 0.85)
    pcm = (mixbuf * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(WAV, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo.tobytes())


# ================================================================== main
def main():
    print(f"Duração: {TOTAL:.1f}s, {NFRAMES} frames")
    build_audio()
    print("Áudio pronto")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", WAV,
           "-vf", "scale=1080:1920:flags=neighbor",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-af", "alimiter=limit=0.7:level=false", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render, range(NFRAMES), chunksize=6)):
            proc.stdin.write(buf)
            if k % 150 == 0:
                print(f"  frame {k}/{NFRAMES}")
    proc.stdin.close()
    proc.wait()
    os.remove(WAV)
    print("Pronto:", OUT)


if __name__ == "__main__":
    main()
