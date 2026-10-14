"""Gera a trilha ORIGINAL do animatic (breakcore/industrial, 180 BPM) e os efeitos.

Tudo é sintetizado do zero com numpy/scipy — sem samples de terceiros — então
pode ser usado livremente como trilha-guia (ou até final, se você gostar).

Saídas (em ../output/audio/):
  music_stem.(wav|flac)   — só a música, sem ducking
  sfx_stem.(wav|flac)     — impactos, whooshes, moedas, parries, UI
  mix_animatic.(wav|flac) — música com ducking sob a narração + SFX (usada no animatic)
"""
import os
import subprocess

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
from scipy.io import wavfile

import timeline as T

SR = 44100
N = int(T.DURATION * SR)
RNG = np.random.default_rng(666)
OUT = os.path.join(os.path.dirname(__file__), "..", "output", "audio")
S16 = T.BEAT / 4  # duração de uma semicolcheia


# ---------------------------------------------------------------- utilidades
def tt(dur):
    return np.arange(int(dur * SR)) / SR


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def place(buf, sig, t, gain=1.0):
    i = int(round(t * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    s = sig if i >= 0 else sig[-i:]
    i = max(i, 0)
    e = min(len(buf), i + len(s))
    buf[i:e] += gain * s[: e - i]


def saw(f, t):
    ph = (f * t) % 1.0
    return 2 * ph - 1


def reverb(x, secs=2.2, wet=0.3, bright=4000):
    n = int(secs * SR)
    ir = RNG.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir = lp(ir, bright)
    ir /= np.sqrt(np.sum(ir ** 2))
    y = fftconvolve(x, ir)[: len(x)]
    return x * (1 - wet) + y * wet


def seg(a, b):
    return slice(int(a * SR), int(b * SR))


# ---------------------------------------------------------------- one-shots
def kick(drive=2.5):
    t = tt(0.35)
    f = 42 + 130 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 7) + 0.4 * np.exp(-t * 300) * RNG.standard_normal(len(t)) * 0.3
    return np.tanh(drive * x) / np.tanh(drive)


def snare(tone=190):
    t = tt(0.25)
    n = bp(RNG.standard_normal(len(t)), 900, 7000) * np.exp(-t * 16)
    b = np.sin(2 * np.pi * tone * t) * np.exp(-t * 28)
    return np.tanh(1.8 * (0.9 * n + 0.6 * b))


def hat(open_=False):
    t = tt(0.22 if open_ else 0.05)
    return hp(RNG.standard_normal(len(t)), 7000) * np.exp(-t * (14 if open_ else 70)) * 0.6


def crash():
    t = tt(1.8)
    return hp(RNG.standard_normal(len(t)), 4000) * np.exp(-t * 2.4) * 0.22


def impact(size=1.0):
    t = tt(2.5)
    f = 30 + 70 * np.exp(-t * 6)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    nz = lp(RNG.standard_normal(len(t)), 2500) * np.exp(-t * 9)
    x = np.tanh(2.2 * (sub + 0.6 * nz)) * size
    return reverb(x, 2.8, 0.35)


def riser(dur):
    t = tt(dur)
    k = t / dur
    nz = RNG.standard_normal(len(t))
    out = np.zeros_like(nz)
    # varredura de banda em blocos
    blocks = 24
    L = len(t) // blocks
    for i in range(blocks):
        c = 300 * (40 ** (i / blocks))
        sl = slice(i * L, (i + 1) * L if i < blocks - 1 else len(t))
        out[sl] = bp(nz[sl], c * 0.7, min(c * 1.4, 18000))
    tone = saw(110 * (2 ** (3 * k)), t) * 0.15
    return (out * 0.5 + tone) * k ** 2


def whoosh():
    t = tt(0.35)
    env = np.sin(np.pi * t / 0.35) ** 2
    return bp(RNG.standard_normal(len(t)), 600, 5000) * env * 0.6


def coin():
    t = tt(0.9)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
            for f, a, d in [(2637, 1, 4), (3951, .5, 6), (5274, .3, 9), (7040, .15, 12)])
    return reverb(x * 0.35, 1.2, 0.25, 9000)


def parry():
    t = tt(1.2)
    parts = [(523, 1, 5), (1187, .7, 7), (1893, .5, 9), (2742, .4, 11), (4110, .3, 14)]
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in parts)
    x += 0.8 * hp(RNG.standard_normal(len(t)), 3000) * np.exp(-t * 40)
    return reverb(np.tanh(1.5 * x) * 0.5, 1.6, 0.35, 8000)


def slam():
    return impact(0.7)[: int(1.2 * SR)]


def rail():
    t = tt(0.8)
    f = 2400 * np.exp(-t * 3) + 200
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 5) * 0.25
    return x + 0.4 * impact(0.5)[: len(t)]


def ui():
    t = tt(0.12)
    return np.sign(np.sin(2 * np.pi * 1320 * t)) * np.exp(-t * 30) * 0.18


def typewriter():
    t = tt(0.6)
    out = np.zeros(len(t))
    for i in range(12):
        place(out, hp(RNG.standard_normal(int(0.012 * SR)), 2000) * 0.4, i * 0.045)
    return out


def breath():
    t = tt(1.0)
    return bp(RNG.standard_normal(len(t)), 300, 1800) * np.sin(np.pi * t) ** 2 * 0.25


def cut():
    t = tt(0.08)
    return hp(RNG.standard_normal(len(t)), 1000) * np.exp(-t * 60) * 0.5


# ---------------------------------------------------------------- bateria
K, SN, H = kick(), snare(), hat()
GHOST = snare(230) * 0.35

PATTERNS = {
    # 16 passos por compasso: 'k' bumbo, 's' caixa, 'g' ghost, 'h' chimbal
    "half":  {"k": [0, 10], "s": [8], "g": [], "h": [0, 2, 4, 6, 8, 10, 12, 14]},
    "break": {"k": [0, 2, 10, 11], "s": [4, 12], "g": [7, 9, 15], "h": list(range(0, 16, 2))},
    "break2": {"k": [0, 3, 6, 10], "s": [4, 12, 14], "g": [2, 9, 11], "h": list(range(16))},
    "stomp": {"k": [0, 4, 8, 12], "s": [4, 12], "g": [], "h": [2, 6, 10, 14]},
}


def drums(buf, t0, t1, style, gain=1.0, rolls=True, density=0.0):
    bars = int(round((t1 - t0) / T.BAR))
    for bi in range(bars):
        bt = t0 + bi * T.BAR
        pat = PATTERNS[style]
        if style == "break" and bi % 2 == 1:
            pat = PATTERNS["break2"]
        for s in pat["k"]:
            place(buf, K, bt + s * S16, 0.95 * gain)
        for s in pat["s"]:
            place(buf, SN, bt + s * S16, 0.7 * gain)
        for s in pat["g"]:
            place(buf, GHOST, bt + s * S16, gain)
        for s in pat["h"]:
            place(buf, H, bt + s * S16, (0.35 if s % 4 else 0.5) * gain)
        # breakcore: rolos de caixa em fusas a cada 4 compassos
        if rolls and style.startswith("break") and bi % 4 == 3:
            for j in range(8):
                place(buf, SN[: int(0.06 * SR)], bt + 3 * T.BEAT + j * S16 / 2, 0.45 * gain * (0.6 + j / 16))
        # densidade extra (build): caixas aleatórias em semicolcheias
        for s in range(16):
            if RNG.random() < density:
                place(buf, SN[: int(0.08 * SR)], bt + s * S16, 0.4 * gain)


def fill(buf, t0, beats=4, gain=0.8):
    n = beats * 8
    for j in range(n):
        place(buf, SN[: int(0.07 * SR)], t0 + j * T.BEAT / 8, gain * (0.3 + 0.7 * j / n))


# ---------------------------------------------------------------- baixo / harmonia
E1, F1, G1, D1, C2, A1, B1 = 41.2, 43.65, 49.0, 36.71, 65.41, 55.0, 61.74
PROG = [E1, E1, F1, E1, E1, G1, F1, D1]  # um compasso por nota (frígio)


def reese(f, dur, bright):
    t = tt(dur)
    x = saw(f, t) + saw(f * 1.007, t) + 0.5 * saw(f * 2.003, t)
    x = lp(x, bright, 2)
    return np.tanh(2.0 * x) * 0.5


def bassline(buf, t0, t1, bright=700, gain=0.6, sweep=None):
    bars = int(round((t1 - t0) / T.BAR))
    for bi in range(bars):
        bt = t0 + bi * T.BAR
        f = PROG[bi % len(PROG)]
        br = bright
        if sweep:
            br = sweep[0] * (sweep[1] / sweep[0]) ** (bi / max(bars - 1, 1))
        note = reese(f, T.BAR, br)
        # sidechain: abaixa no tempo de cada batida
        tn = tt(T.BAR)
        sc = 1 - 0.7 * np.exp(-((tn % T.BEAT) / 0.06))
        note *= sc
        fade = np.minimum(1, np.minimum(tn / 0.005, (T.BAR - tn) / 0.01))
        place(buf, note * fade, bt, gain)


def pad(buf, t0, t1, chords, gain=0.18, cutoff=900):
    span = (t1 - t0) / len(chords)
    for ci, ch in enumerate(chords):
        t = tt(span + 1.0)
        x = sum(saw(f, t) + saw(f * 1.004, t) for f in ch)
        x = lp(x, cutoff, 2)
        env = np.minimum(1, t / 0.8) * np.minimum(1, np.maximum(0, (span + 1.0 - t) / 1.0))
        place(buf, x * env * gain / len(ch), t0 + ci * span)


def stabs(buf, t0, t1, gain=0.22):
    bars = int(round((t1 - t0) / T.BAR))
    for bi in range(bars):
        bt = t0 + bi * T.BAR
        root = PROG[bi % len(PROG)] * 4
        for s in (0, 3, 6, 10, 13):
            t = tt(0.12)
            x = sum(np.sign(np.sin(2 * np.pi * root * r * t)) for r in (1, 1.189, 1.498))
            place(buf, lp(x, 3000) * np.exp(-t * 25) * gain / 3, bt + s * S16)


def arp(buf, t0, t1, gain=0.12, notes=(329.6, 392.0, 493.9, 587.3, 659.3, 493.9, 392.0, 440.0)):
    steps = int(round((t1 - t0) / S16))
    for i in range(steps):
        t = tt(S16 * 0.9)
        f = notes[i % len(notes)]
        x = (saw(f, t) * 0.6 + np.sign(np.sin(2 * np.pi * f * 0.5 * t)) * 0.4) * np.exp(-t * 18)
        place(buf, lp(x, 2500), t0 + i * S16, gain)


def drone(buf, t0, t1, gain=0.35):
    t = tt(t1 - t0)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t)
    sub = np.sin(2 * np.pi * 41.2 * t) * 0.6 + np.sin(2 * np.pi * 61.74 * t) * 0.25
    wind = lp(RNG.standard_normal(len(t)), 500) * (0.2 + 0.4 * lfo)
    x = (sub + wind) * np.minimum(1, t / 2.0)
    buf[seg(t0, t1)] += gain * x[: len(buf[seg(t0, t1)])]


def clank(size=1.0):
    t = tt(2.5)
    parts = [(311, 1, 3), (743, .6, 4), (1291, .4, 5), (1873, .3, 7)]
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in parts) * 0.25 * size
    return reverb(x, 3.0, 0.6, 3000)


def heartbeat(buf, t0, t1, gain=0.5):
    t = t0
    while t < t1:
        place(buf, K, t, gain)
        place(buf, K, t + 0.22, gain * 0.6)
        t += 4 * T.BEAT


# ---------------------------------------------------------------- arranjo
def build_music():
    m = np.zeros(N)
    # C1
    drone(m, 0.0, 4.0, 0.25)
    place(m, riser(2.0), 2.0, 0.6)
    drums(m, 4.0, 12.6667 + 1e-3, "break")
    bassline(m, 4.0, 12.0)
    stabs(m, 4.0, 12.0)
    for x in np.arange(4.0, 12.6, T.BAR * 2):
        place(m, crash(), x, 0.8)
    place(m, riser(1.6667), 12.6667 - 1.6667, 0.5)
    # 12.6667–13: silêncio (corte); 13: impacto no SFX
    drone(m, 13.0, 16.0, 0.2)
    place(m, riser(1.3333), 14.6667, 0.4)

    # C2 — groove médio sob narração
    drums(m, 16.0, 34.6667, "half", 0.8)
    bassline(m, 16.0, 34.6667, bright=450, gain=0.45)
    pad(m, 16.0, 34.6667, [[164.8, 196.0, 246.9], [174.6, 220.0, 261.6]] * 2, 0.14)
    # premissa: só pad e batimento
    pad(m, 34.6667, 45.3333, [[82.4, 123.5, 164.8]], 0.18, 600)
    heartbeat(m, 35.0, 45.0, 0.45)
    drums(m, 45.3333, 58.6667, "half", 0.85)
    bassline(m, 45.3333, 64.0, bright=600, gain=0.5)
    drums(m, 58.6667, 62.6667, "break", 0.75, rolls=False)
    place(m, riser(4.0), 60.0, 0.6)
    fill(m, 62.6667, 4)

    # C3 — breakcore total
    for a, z in [(64.0, 81.3333), (82.6667, 98.6667), (102.0, 114.6667), (116.0, 128.6667)]:
        drums(m, a, z, "break", 1.0)
        bassline(m, a, z, bright=900, gain=0.55)
        stabs(m, a, z)
        for x in np.arange(a, z - 0.01, T.BAR * 4):
            place(m, crash(), x, 0.7)
    fill(m, 81.3333, 4)
    fill(m, 114.6667, 4)
    # moedas: respiro de 1 compasso e meio só com chimbal e baixo
    drums(m, 98.6667, 100.0, "break", 0.9, rolls=False)
    for s in range(24):
        place(m, H, 100.0 + s * S16, 0.35)
    bassline(m, 98.6667, 102.6667, bright=400, gain=0.45)
    # style: build com arpejo
    drums(m, 128.6667, 139.3333, "break2", 1.0, density=0.15)
    bassline(m, 128.6667, 139.3333, sweep=(500, 2500), gain=0.55)
    arp(m, 130.0, 139.3333, 0.12)
    drums(m, 139.3333, 143.6667, "stomp", 1.1)
    bassline(m, 139.3333, 143.6667, bright=1200, gain=0.6)

    # C4 — atmosfera
    drone(m, 144.0, 190.6667, 0.4)
    pad(m, 144.0, 190.6667, [[82.4, 123.5, 196.0], [65.4, 98.0, 164.8], [73.4, 110.0, 174.6],
                             [82.4, 123.5, 164.8], [87.3, 130.8, 174.6], [82.4, 123.5, 155.6]], 0.2, 700)
    for tc in (147.0, 156.0, 163.0, 171.0, 176.0, 180.0):
        place(m, clank(), tc, 0.8)
    heartbeat(m, 175.0, 190.0, 0.4)
    place(m, riser(4.6667), 186.0, 0.7)
    # 190.6667–192: silêncio
    drums(m, 192.0, 208.0, "break", 1.1, density=0.08)
    bassline(m, 192.0, 208.0, bright=1600, gain=0.65)
    stabs(m, 192.0, 208.0, 0.28)
    for x in np.arange(192.0, 207.9, T.BAR * 2):
        place(m, crash(), x, 0.8)

    # C5 — groove melódico
    drums(m, 208.0, 220.0, "half", 0.85)
    bassline(m, 208.0, 258.0, bright=650, gain=0.48)
    pad(m, 208.0, 258.0, [[164.8, 196.0, 246.9], [130.8, 164.8, 196.0],
                          [146.8, 174.6, 220.0], [164.8, 207.7, 246.9]] * 2, 0.12, 1200)
    arp(m, 220.0, 258.0, 0.09)
    drums(m, 220.0, 248.0, "break", 0.75, rolls=False)
    drums(m, 248.0, 257.3333, "half", 0.8)
    place(m, riser(4.0), 260.0, 0.6)

    # C6 — clímax
    drums(m, 264.0, 280.0, "break", 1.0, density=0.05)
    bassline(m, 264.0, 280.0, sweep=(350, 2200), gain=0.55)
    fill(m, 278.6667, 4, 0.9)
    drums(m, 280.0, 296.0, "break2", 1.15, density=0.12)
    bassline(m, 280.0, 296.0, bright=2200, gain=0.65)
    stabs(m, 280.0, 296.0, 0.3)
    arp(m, 280.0, 296.0, 0.1, notes=(659.3, 587.3, 493.9, 392.0, 659.3, 784.0, 659.3, 493.9))
    for x in np.arange(280.0, 295.9, T.BAR):
        place(m, crash(), x, 0.7)
    m[seg(296.0, T.DURATION)] = 0  # corte seco
    # logo: acorde final longo com reverb
    t = tt(6.0)
    ch = sum(saw(f, t) + saw(f * 1.005, t) for f in (82.4, 123.5, 164.8, 196.0))
    ch = lp(ch, 900) * np.exp(-t * 0.8) * 0.12
    place(m, reverb(ch, 3.0, 0.5), 302.6667)
    m[seg(308.0, T.DURATION)] *= np.linspace(1, 0, len(m[seg(308.0, T.DURATION)])) ** 2
    return m


SFX_FN = {"type": typewriter, "whoosh": whoosh, "slam": slam, "coin": coin, "parry": parry,
          "rail": rail, "ui": ui, "breath": breath, "cut": cut, "boom": lambda: impact(1.3),
          "riser_end": lambda: crash() * 0.8}


def build_sfx():
    s = np.zeros(N)
    for t, k in T.HITS:
        place(s, impact(0.5 + 0.5 * k), t, 0.7)
    for t, k in T.SFX:
        place(s, SFX_FN[k](), t, 0.8)
    return s


def duck_curve():
    """Abaixa a música ~6 dB enquanto há narração (rampas de 120 ms)."""
    g = np.ones(N)
    for t0, t1, *_ in T.NARRATION:
        g[seg(t0 - 0.12, t1 + 0.2)] = 0.5
    k = int(0.12 * SR)
    return np.convolve(g, np.ones(k) / k, mode="same")


def norm(x, peak=0.89):
    return x * (peak / (np.max(np.abs(x)) + 1e-9))


def stereo(x, width=0.0):
    d = int(0.012 * SR)
    r = np.concatenate([np.zeros(d), x[:-d]]) if width else x
    return np.stack([x, x * (1 - width) + r * width], axis=1)


def write(name, x):
    """Grava WAV (usado pelo render) e uma cópia FLAC sem perdas (versionada no git)."""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, path[:-4] + ".flac"], check=True)


if __name__ == "__main__":
    music = build_music()
    music = np.tanh(1.3 * norm(music)) / np.tanh(1.3)  # cola/saturação de master
    sfx = build_sfx()
    write("music_stem.wav", stereo(norm(music, 0.85), 0.3))
    write("sfx_stem.wav", stereo(norm(sfx, 0.85)))
    mix = music * duck_curve() * 0.8 + norm(sfx, 0.7)
    write("mix_animatic.wav", stereo(norm(mix, 0.89), 0.3))
    print("ok")
