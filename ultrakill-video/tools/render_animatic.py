"""Renderiza o ANIMATIC 1080p30 de "ULTRAKILL — A ARTE DO CAOS".

Cada plano de gameplay aparece como um PLACEHOLDER identificado (G01, G13…)
com a descrição da gravação que deve entrar ali. Toda a camada de motion
graphics (títulos, tags, ranks, lower thirds, legendas da narração, flashes,
shake e RGB split nos impactos) já está no ritmo final da música.

Uso:
  python3 render_animatic.py                    # vídeo completo
  python3 render_animatic.py --from 64 --to 80  # trecho
  python3 render_animatic.py --still 130.2      # frame único em PNG
"""
import argparse
import math
import os
import subprocess
import sys
import textwrap
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import timeline as T

W, H = 1920, 1080
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "assets", "fonts")
OUT = os.path.join(HERE, "..", "output")

# ------------------------------------------------------------ identidade visual
PAL = {
    "black": (11, 11, 13),
    "blood": (224, 16, 16),
    "hot": (255, 59, 31),
    "deep": (58, 5, 5),
    "bone": (237, 230, 218),
    "ash": (90, 90, 96),
    "gold": (245, 183, 0),
    "parry": (47, 168, 255),
}
RANK_COL = {"D": (170, 170, 176), "C": (47, 168, 255), "B": (60, 220, 120), "A": (245, 183, 0),
            "S": (255, 120, 20), "SS": (255, 40, 40), "SSS": (200, 0, 30), "U": (255, 255, 255)}

_F = {}


def font(name, size):
    key = (name, size)
    if key not in _F:
        path = {"anton": os.path.join(FONTS, "Anton.ttf"),
                "mono": os.path.join(FONTS, "ShareTechMono.ttf"),
                "sub": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"}[name]
        _F[key] = ImageFont.truetype(path, size)
    return _F[key]


# ------------------------------------------------------------ pré-cálculos
SHOTS = sorted(T.SHOTS, key=lambda s: s["t0"])
HIT_T = np.array([h[0] for h in T.HITS])
HIT_K = np.array([h[1] for h in T.HITS])

_rng = np.random.default_rng(1)
GRAIN = [(_rng.standard_normal((H // 2, W // 2)) * 9).astype(np.int16) for _ in range(6)]
SCAN = np.ones((H, 1, 1), np.float32)
SCAN[::3] = 0.86


def _grad():
    arr = np.zeros((H, W, 3), np.uint8)
    g = np.linspace(0, 1, H)[:, None]
    arr[..., 0] = (18 + 40 * g).astype(np.uint8)
    arr[..., 1] = (6 + 4 * g).astype(np.uint8)
    arr[..., 2] = (8 + 4 * g).astype(np.uint8)
    return Image.fromarray(arr)


GRAD = _grad()


def shot_at(t):
    for s in SHOTS:
        if s["t0"] <= t < s["t1"]:
            return s
    return SHOTS[-1]


def hit_env(t):
    """Intensidade do impacto mais recente (decai em ~6 frames)."""
    d = t - HIT_T
    m = (d >= 0) & (d < 0.25)
    if not m.any():
        return 0.0
    i = np.where(m)[0][-1]
    return float(HIT_K[i] * math.exp(-d[i] * 18))


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def text_img(txt, fnt, fill, stroke=0, stroke_fill=(0, 0, 0)):
    bb = fnt.getbbox(txt, stroke_width=stroke)
    im = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - bb[0], 10 - bb[1]), txt, font=fnt, fill=fill,
                            stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def skew(im, k=0.22):
    w, h = im.size
    nw = int(w + k * h)
    return im.transform((nw, h), Image.AFFINE, (1, k, -k * h, 0, 1, 0), Image.BICUBIC)


def paste_c(base, im, cx, cy, scale=1.0):
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# ------------------------------------------------------------ fundos por tipo de plano
def bg_gameplay(img, s, t):
    d = ImageDraw.Draw(img)
    local = t - s["t0"]
    dur = s["t1"] - s["t0"]
    ref = s["ref"]
    calm = ref.startswith("G20") or ref in ("A02", "A01")
    # gradiente vermelho escuro + linhas de velocidade (sugere movimento)
    img.paste(GRAD, (0, 0))
    seed = int(s["t0"] * 1000)
    r = np.random.default_rng(seed)
    n = 14 if calm else 46
    speed = 60 if calm else 1400
    for i in range(n):
        y = r.uniform(0, H)
        x0 = (r.uniform(0, W) + speed * local * r.uniform(0.6, 1.4)) % (W + 600) - 300
        ln = r.uniform(80, 420) * (0.4 if calm else 1)
        c = int(r.uniform(40, 110))
        d.line([(x0, y), (x0 + ln, y)], fill=(c, 12, 12), width=int(r.uniform(1, 4)))
    # moldura
    d.rectangle([60, 60, W - 60, H - 60], outline=PAL["blood"], width=3)
    for (x, y) in [(60, 60), (W - 60, 60), (60, H - 60), (W - 60, H - 60)]:
        d.rectangle([x - 14, y - 14, x + 14, y + 14], outline=PAL["bone"], width=3)
    kind = "ARTE OFICIAL" if ref.startswith("A") else "INSERIR GAMEPLAY"
    title, desc = T.CAPTURES.get(ref, ("", ""))
    d.text((100, 92), f"// {kind}", font=font("mono", 34), fill=PAL["blood"])
    idim = text_img(ref, font("anton", 220), (0, 0, 0, 0), stroke=3, stroke_fill=PAL["bone"] + (170,))
    img.alpha_composite(idim, (100, 150))
    d.text((110, 430), title.upper(), font=font("anton", 64), fill=PAL["bone"])
    note = s["note"]
    y = 530
    for line in textwrap.wrap(desc, 70)[:4]:
        d.text((112, y), line, font=font("mono", 30), fill=(190, 180, 170))
        y += 40
    if note:
        y += 16
        for line in textwrap.wrap("EDIÇÃO: " + note, 70)[:3]:
            d.text((112, y), line, font=font("mono", 30), fill=PAL["gold"])
            y += 40
    meta = f"{dur:4.2f}s  ·  VEL {s['speed']}  ·  ENTRADA: {s['trans']}"
    mw = d.textlength(meta, font=font("mono", 26))
    d.text((W - 112 - mw, 96), meta, font=font("mono", 26), fill=PAL["ash"])
    # barra de progresso do plano
    d.rectangle([W - 112 - mw, 136, W - 112, 142], fill=(40, 10, 10))
    d.rectangle([W - 112 - mw, 136, W - 112 - mw + mw * min(local / dur, 1), 142], fill=PAL["blood"])


def bg_split(img, s, t):
    d = ImageDraw.Draw(img)
    img.paste(PAL["black"], (0, 0, W, H))
    cw = W // 3
    for i in range(3):
        x0 = i * cw
        shade = 25 + 18 * i
        d.rectangle([x0 + 8, 8, x0 + cw - 8, H - 8], fill=(shade, 8, 8), outline=PAL["blood"], width=3)
        d.text((x0 + 40, 80), f"G25 · TENTATIVA {i + 1}", font=font("mono", 34), fill=PAL["bone"])
        d.text((x0 + 40, 130), ["RUIM", "MÉDIA", "A MELHOR"][i], font=font("anton", 90),
               fill=[PAL["ash"], PAL["bone"], PAL["gold"]][i])
        for j, line in enumerate(textwrap.wrap("Mesmo encontro, sincronizado no mesmo ponto de partida.", 26)):
            d.text((x0 + 40, 280 + j * 40), line, font=font("mono", 28), fill=(180, 170, 160))


def bg_logo(img, s, t):
    img.paste(PAL["black"], (0, 0, W, H))
    local = t - s["t0"]
    sc = 1.12 - 0.12 * ease_out(local / 0.25) + 0.015 * local
    lg = text_img("ULTRAKILL", font("anton", 300), PAL["blood"])
    glow = lg.filter(ImageFilter.GaussianBlur(18))
    paste_c(img, glow, W / 2, H / 2 - 30, sc)
    paste_c(img, lg, W / 2, H / 2 - 30, sc)
    d = ImageDraw.Draw(img)
    msg = "PLACEHOLDER — SUBSTITUIR PELO LOGOTIPO OFICIAL (A01, press kit)"
    w = d.textlength(msg, font=font("mono", 26))
    d.text(((W - w) / 2, H - 170), msg, font=font("mono", 26), fill=PAL["ash"])


def draw_background(img, s, t):
    k = s["kind"]
    if k in ("gp",):
        bg_gameplay(img, s, t)
    elif k == "split":
        bg_split(img, s, t)
    elif k == "logo":
        bg_logo(img, s, t)
    elif k == "flash":
        img.paste((255, 255, 255), (0, 0, W, H))
    else:  # card, type, black
        img.paste(PAL["black"], (0, 0, W, H))
        if k == "card":
            # textura sutil de sangue nos cards
            d = ImageDraw.Draw(img)
            d.rectangle([0, H - 14, W, H], fill=PAL["deep"])


# ------------------------------------------------------------ overlays (motion graphics)
def ov_typewriter(img, txt, t0, t):
    lines = txt.split("|")
    d = ImageDraw.Draw(img)
    f = font("anton", 110)
    for i, ln in enumerate(lines):
        st = t0 + i * 1.0
        if t < st:
            break
        n = int(min(len(ln), (t - st) / 0.035))
        s = ln[:n]
        w = d.textlength(ln, font=f)
        y = 300 + i * 160
        col = PAL["blood"] if i == 2 else PAL["bone"]
        d.text(((W - w) / 2, y), s, font=f, fill=col)
        if n < len(ln) and int(t * 8) % 2 == 0:
            cx = (W - w) / 2 + d.textlength(s, font=f)
            d.rectangle([cx + 6, y + 20, cx + 40, y + 150], fill=PAL["blood"])


def ov_title(img, txt, t0, t):
    a, b2 = (txt.split("|") + [""])[:2]
    p = ease_out((t - t0) / 0.2)
    sc = 1.25 - 0.25 * p
    big = text_img(a, font("anton", 260), PAL["bone"])
    shadow = text_img(a, font("anton", 260), PAL["blood"])
    paste_c(img, shadow, W / 2 + 12, H / 2 - 60 + 12, sc)
    paste_c(img, big, W / 2, H / 2 - 60, sc)
    if b2 and t - t0 > 0.3333:
        band = Image.new("RGBA", (900, 96), PAL["blood"] + (255,))
        ImageDraw.Draw(band).text((450, 48), b2, font=font("anton", 70), fill=PAL["black"], anchor="mm")
        paste_c(img, skew(band, 0.25), W / 2, H / 2 + 150, 1.0)


def ov_big(img, txt, t0, t):
    p = ease_out((t - t0) / 0.15)
    f = font("anton", 150 if len(txt) < 20 else 118)
    im = text_img(txt, f, PAL["bone"])
    paste_c(img, im, W / 2, H / 2 - 20, 1.15 - 0.15 * p)
    d = ImageDraw.Draw(img)
    bw = im.width * p
    d.rectangle([W / 2 - bw / 2, H / 2 + 90, W / 2 + bw / 2, H / 2 + 104], fill=PAL["blood"])


def ov_tag(img, txt, t0, t):
    p = ease_out((t - t0) / 0.12)
    im = text_img(txt, font("anton", 190), PAL["bone"], stroke=0)
    back = Image.new("RGBA", (im.width + 60, im.height + 10), PAL["blood"] + (235,))
    back.alpha_composite(im, (30, 5))
    back = skew(back, 0.2)
    x = 140 + back.width / 2 - 200 * (1 - p)
    paste_c(img, back, x, H - 300, 1.0 + 0.2 * (1 - p))


def ov_small(img, txt, t0, t):
    d = ImageDraw.Draw(img)
    f = font("mono", 40)
    w = d.textlength(txt, font=f)
    p = ease_out((t - t0) / 0.25)
    d.rectangle([W - 140 - w - 40, 180, W - 140 - w - 40 + (w + 60) * p, 240], fill=PAL["blood"])
    if p > 0.6:
        d.text((W - 140 - w - 10, 186), txt, font=f, fill=PAL["black"])


def ov_lower(img, txt, t0, t):
    d = ImageDraw.Draw(img)
    p = ease_out((t - t0) / 0.3)
    f = font("mono", 36)
    w = d.textlength(txt, font=f)
    d.rectangle([120, H - 260, 120 + (w + 60) * p, H - 200], fill=PAL["black"])
    d.rectangle([120, H - 260, 132, H - 200], fill=PAL["blood"])
    if p > 0.7:
        d.text((150, H - 252), txt, font=f, fill=PAL["bone"])


def ov_rank(img, txt, style, t0, t):
    key = style.split(":")[1]
    col = RANK_COL[key]
    p = ease_out((t - t0) / 0.1)
    box = Image.new("RGBA", (620, 300), (0, 0, 0, 200))
    bd = ImageDraw.Draw(box)
    bd.rectangle([0, 0, 619, 299], outline=col, width=6)
    letter = {"U": "U"}.get(key, key)
    bd.text((40, 150), letter, font=font("anton", 200), fill=col, anchor="lm")
    bd.text((600, 230), txt, font=font("anton", 70 if len(txt) < 10 else 56), fill=PAL["bone"], anchor="rm")
    bd.text((600, 50), "STYLE", font=font("mono", 34), fill=PAL["ash"], anchor="rm")
    paste_c(img, box, W - 420, 330, 1.25 - 0.25 * p)


def ov_coin(img, t0, t):
    d = ImageDraw.Draw(img)
    local = t - t0
    cx, cy = W * 0.7, H * 0.4 - 260 * math.sin(min(local / 1.6, 1) * math.pi)
    rw = 70 * abs(math.cos(local * 14)) + 8
    d.ellipse([cx - rw, cy - 70, cx + rw, cy + 70], fill=PAL["gold"], outline=(255, 230, 120), width=4)


def ov_prank(img, t0, t):
    p = ease_out((t - t0) / 0.3)
    im = text_img("P", font("anton", 520), PAL["gold"])
    glow = im.filter(ImageFilter.GaussianBlur(30))
    paste_c(img, glow, W - 420, H / 2, 1.3 - 0.3 * p)
    paste_c(img, im, W - 420, H / 2, 1.3 - 0.3 * p)


def ov_subtitle(img, t):
    for t0, t1, txt, _ in T.NARRATION:
        if t0 <= t < t1:
            d = ImageDraw.Draw(img)
            f = font("sub", 40)
            lines = textwrap.wrap(txt, 60)
            y = H - 90 - 54 * len(lines)
            for ln in lines:
                w = d.textlength(ln, font=f)
                d.rectangle([(W - w) / 2 - 16, y - 6, (W + w) / 2 + 16, y + 50], fill=(0, 0, 0, 200))
                d.text(((W - w) / 2, y), ln, font=f, fill=(255, 255, 255))
                y += 54
            break


def ov_hud(img, t, s):
    d = ImageDraw.Draw(img)
    sid, title = T.scene_at(t)
    f = font("mono", 24)
    d.text((70, 18), f"ANIMATIC v1  ·  {sid} — {title}", font=f, fill=(150, 150, 150))
    mm, ss = divmod(t, 60)
    tc = f"{int(mm):02d}:{ss:05.2f}  ·  F{int(round(t * T.FPS)):05d}"
    w = d.textlength(tc, font=f)
    d.text((W - 70 - w, 18), tc, font=f, fill=(150, 150, 150))
    # linha do tempo com marcadores de cena
    y = H - 22
    d.rectangle([70, y, W - 70, y + 4], fill=(45, 45, 50))
    for _, a, _, _, _ in T.SCENES:
        x = 70 + (W - 140) * a / T.DURATION
        d.rectangle([x - 1, y - 6, x + 1, y + 10], fill=(120, 120, 120))
    d.rectangle([70, y, 70 + (W - 140) * t / T.DURATION, y + 4], fill=PAL["blood"])


def overlays(img, t):
    for t0, t1, txt, style in T.TEXTS:
        if not (t0 <= t < t1):
            continue
        if style == "typewriter":
            ov_typewriter(img, txt, t0, t)
        elif style == "title":
            ov_title(img, txt, t0, t)
        elif style == "big":
            ov_big(img, txt, t0, t)
        elif style == "tag":
            ov_tag(img, txt, t0, t)
        elif style == "small":
            ov_small(img, txt, t0, t)
        elif style == "lower":
            ov_lower(img, txt, t0, t)
        elif style.startswith("rank"):
            ov_rank(img, txt, style, t0, t)
        elif style == "coin":
            ov_coin(img, t0, t)
        elif style == "prank":
            ov_prank(img, t0, t)


# ------------------------------------------------------------ pós (impactos, grão, scanlines)
def post(arr, t, s):
    e = hit_env(t)
    if e > 0.02:
        # shake
        r = np.random.default_rng(int(t * 1000))
        dx, dy = (r.uniform(-1, 1, 2) * 28 * e).astype(int)
        arr = np.roll(arr, (dy, dx), axis=(0, 1))
        # RGB split
        sh = int(16 * e)
        if sh:
            arr[..., 0] = np.roll(arr[..., 0], sh, axis=1)
            arr[..., 2] = np.roll(arr[..., 2], -sh, axis=1)
        # flash vermelho/branco
        fl = min(1.0, e * 1.1)
        tint = np.array([255, 235, 225] if e > 0.7 else [255, 40, 30], np.float32)
        arr = (arr * (1 - 0.55 * fl) + tint * 0.55 * fl)
    arr = arr.astype(np.float32)
    if s["kind"] in ("gp", "split"):
        arr *= SCAN
    g = GRAIN[int(t * T.FPS) % len(GRAIN)]
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    arr = arr + g
    # vinheta
    return np.clip(arr * VIG, 0, 255).astype(np.uint8)


yy, xx = np.mgrid[0:H, 0:W]
VIG = (1 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2).astype(np.float32)[..., None]
del yy, xx


def fade_factor(t):
    if t >= 308.0:
        return max(0.0, 1 - (t - 308.0) / 1.0)
    # dissolves da cena 4
    return 1.0


def render(t):
    s = shot_at(t)
    img = Image.new("RGBA", (W, H), PAL["black"] + (255,))
    draw_background(img, s, t)
    # dissolve de entrada (cena 4)
    if s["trans"].startswith("dissolve") and t - s["t0"] < 1.0:
        k = (t - s["t0"])
        img = Image.blend(Image.new("RGBA", (W, H), PAL["black"] + (255,)), img, k)
    if s["trans"] == "dip to black" and t - s["t0"] < 0.3333:
        img = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), img, (t - s["t0"]) / 0.3333)
    overlays(img, t)
    ov_subtitle(img, t)
    arr = np.asarray(img.convert("RGB"))
    arr = post(arr.copy(), t, s)
    arr = (arr * fade_factor(t)).astype(np.uint8)
    out = Image.fromarray(arr)
    ov_hud(out, t, s)
    return out


def frame_bytes(i):
    return render(i / T.FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", type=float, default=0.0)
    ap.add_argument("--to", dest="b", type=float, default=T.DURATION)
    ap.add_argument("--still", type=float)
    ap.add_argument("--out", default=os.path.join(OUT, "ULTRAKILL_animatic_v1.mp4"))
    ap.add_argument("--audio", default=os.path.join(OUT, "audio", "mix_animatic.wav"))
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    if a.still is not None:
        p = os.path.join(OUT, "stills", f"still_{a.still:07.2f}.png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        render(a.still).save(p)
        print(p)
        return
    f0, f1 = int(a.a * T.FPS), int(a.b * T.FPS)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(T.FPS), "-i", "-",
           "-ss", str(a.a), "-t", str(a.b - a.a), "-i", a.audio,
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(a.workers) as pool:
        for k, buf in enumerate(pool.imap(frame_bytes, range(f0, f1), chunksize=8)):
            proc.stdin.write(buf)
            if k % 300 == 0:
                print(f"frame {f0 + k}/{f1}", file=sys.stderr, flush=True)
    proc.stdin.close()
    proc.wait()
    print(a.out)


if __name__ == "__main__":
    main()
