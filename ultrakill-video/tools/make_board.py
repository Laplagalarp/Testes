"""Gera a prancha de identidade visual (paleta + tipografia) em ../assets/style_board.png."""
import os
from PIL import Image, ImageDraw

from render_animatic import PAL, RANK_COL, font, W, H

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "style_board.png")
SW = [("BLACK", "black", "fundo"), ("BLOOD", "blood", "acento principal"), ("HOT", "hot", "flash/destaque"),
      ("DEEP", "deep", "sombras"), ("BONE", "bone", "texto"), ("ASH", "ash", "texto secundário"),
      ("GOLD", "gold", "moedas / P-rank"), ("PARRY", "parry", "parry / Feedbacker")]

img = Image.new("RGB", (W, H), PAL["black"])
d = ImageDraw.Draw(img)
d.text((80, 60), "ULTRAKILL — A ARTE DO CAOS", font=font("anton", 96), fill=PAL["bone"])
d.text((84, 190), "// IDENTIDADE VISUAL v1", font=font("mono", 36), fill=PAL["blood"])
x = 80
for name, key, use in SW:
    c = PAL[key]
    d.rectangle([x, 280, x + 200, 480], fill=c, outline=(60, 60, 60))
    d.text((x, 495), name, font=font("anton", 40), fill=PAL["bone"])
    d.text((x, 545), "#%02X%02X%02X" % c, font=font("mono", 28), fill=PAL["ash"])
    d.text((x, 580), use, font=font("mono", 22), fill=PAL["ash"])
    x += 222
d.text((80, 660), "TÍTULOS — ANTON", font=font("anton", 110), fill=PAL["bone"])
d.text((84, 800), "HUD / LABELS — SHARE TECH MONO  0123456789", font=font("mono", 40), fill=PAL["bone"])
d.text((84, 860), "Legendas — Inter SemiBold", font=font("sub", 40), fill=PAL["bone"])
x = 84
for k, c in RANK_COL.items():
    d.rectangle([x, 950, x + 150, 1010], outline=c, width=4)
    d.text((x + 75, 980), k, font=font("anton", 40), fill=c, anchor="mm")
    x += 170
d.text((x + 20, 965), "cores dos ranks", font=font("mono", 24), fill=PAL["ash"])
img.save(OUT)
print(OUT)
