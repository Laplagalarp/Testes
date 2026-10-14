"""Exporta arquivos de edição a partir da timeline:

  ../edit/ULTRAKILL_timeline.edl   — EDL CMX3600 (30 fps) para importar no
                                     DaVinci Resolve / Premiere / Vegas.
                                     Cada plano é um clipe offline com o nome
                                     da gravação (G01.mov, G13.mov…) — basta
                                     relinkar para os seus arquivos.
  ../edit/narracao.srt             — narração com tempos (guia do locutor e legenda)
  ../edit/timeline_planos.csv      — planilha plano a plano
  ../edit/textos_na_tela.csv       — motion graphics
  ../edit/marcadores.csv           — impactos e SFX (marcadores na timeline)
  ../edit/lista_de_captura.csv     — o que gravar e onde cada gravação entra
"""
import csv
import os
from collections import defaultdict

import timeline as T

OUT = os.path.join(os.path.dirname(__file__), "..", "edit")
FPS = T.FPS


def tc(sec):
    f = int(round(sec * FPS))
    return f"{f // (3600 * FPS):02d}:{f // (60 * FPS) % 60:02d}:{f // FPS % 60:02d}:{f % FPS:02d}"


def srt_tc(sec):
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def reel_of(s):
    if s["kind"] in ("gp", "split", "logo"):
        return s["ref"]
    return "BL" if s["kind"] == "black" else "ANIM"  # cards/flash: vêm do próprio animatic


def main():
    os.makedirs(OUT, exist_ok=True)
    shots = sorted(T.SHOTS, key=lambda s: s["t0"])

    # EDL — avança o ponto de entrada de cada gravação para não repetir frames
    offs = defaultdict(float)
    lines = ["TITLE: ULTRAKILL_A_ARTE_DO_CAOS", "FCM: NON-DROP FRAME", ""]
    for i, s in enumerate(shots, 1):
        reel = reel_of(s)
        dur = s["t1"] - s["t0"]
        src_in = {"BL": 0.0, "ANIM": s["t0"]}.get(reel, offs[reel])
        offs[reel] += dur
        lines.append(f"{i:03d}  {reel:<8} V     C        {tc(src_in)} {tc(src_in + dur)} {tc(s['t0'])} {tc(s['t1'])}")
        if reel == "ANIM":
            lines.append("* FROM CLIP NAME: ULTRAKILL_animatic_v1.mp4")
        elif reel != "BL":
            lines.append(f"* FROM CLIP NAME: {reel}.mov")
        note = (s["note"] or "").replace("\n", " ")
        if note:
            lines.append(f"* COMMENT: {note}")
        lines.append("")
    with open(os.path.join(OUT, "ULTRAKILL_timeline.edl"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # SRT
    with open(os.path.join(OUT, "narracao.srt"), "w", encoding="utf-8") as f:
        for i, (a, z, txt, _) in enumerate(T.NARRATION, 1):
            f.write(f"{i}\n{srt_tc(a)} --> {srt_tc(z)}\n{txt}\n\n")

    # planilhas
    with open(os.path.join(OUT, "timeline_planos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["#", "cena", "entrada", "saida", "duracao_s", "frames", "tipo", "gravacao",
                    "transicao", "velocidade", "nota"])
        for i, s in enumerate(shots, 1):
            w.writerow([i, T.scene_at(s["t0"])[0], tc(s["t0"]), tc(s["t1"]), f"{s['t1'] - s['t0']:.3f}",
                        int(round((s["t1"] - s["t0"]) * FPS)), s["kind"], s["ref"], s["trans"],
                        s["speed"], s["note"]])
    with open(os.path.join(OUT, "textos_na_tela.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entrada", "saida", "texto", "estilo"])
        for a, z, txt, st in T.TEXTS:
            w.writerow([tc(a), tc(z), txt.replace("|", " / "), st])
    with open(os.path.join(OUT, "marcadores.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timecode", "tipo", "detalhe"])
        rows = [(t, "IMPACTO", f"intensidade {k}") for t, k in T.HITS]
        rows += [(t, "SFX", k) for t, k in T.SFX]
        rows += [(a, "CENA", f"{sid} — {title}") for sid, a, _, title, _ in T.SCENES]
        for t, k, d in sorted(rows):
            w.writerow([tc(t), k, d])

    uses = defaultdict(list)
    for s in shots:
        if s["ref"]:
            uses[s["ref"]].append(s)
    with open(os.path.join(OUT, "lista_de_captura.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "o_que", "como_gravar", "usos", "tempo_total_no_video_s", "primeira_entrada"])
        for ref, (title, how) in T.CAPTURES.items():
            u = uses.get(ref, [])
            w.writerow([ref, title, how, len(u), f"{sum(x['t1'] - x['t0'] for x in u):.1f}",
                        tc(u[0]["t0"]) if u else "—"])
    print("ok:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
