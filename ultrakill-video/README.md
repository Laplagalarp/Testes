# ULTRAKILL — A ARTE DO CAOS
Vídeo-ensaio de 5:12 sobre ULTRAKILL: roteiro, identidade visual, trilha original, animatic renderizado e pacote de edição.

## O que tem aqui
```
docs/01_ROTEIRO.md              roteiro completo: fala, tempo, imagem e som de cada momento
docs/02_PLANO_DE_PRODUCAO.md    identidade visual, captura, montagem, mix, direitos, checklist
output/ULTRAKILL_animatic_v1.mp4  animatic 1080p30: grafismos, legendas e trilha no tempo final
output/audio/                   trilha original em FLAC: stem de música e stem de SFX (o mix fica no MP4)
edit/ULTRAKILL_timeline.edl     EDL CMX3600 com os 229 planos cortados na batida (Resolve/Premiere)
edit/narracao.srt               narração com tempos (guia do locutor e legenda)
edit/*.csv                      planos, textos na tela, marcadores de impacto e lista de captura
assets/style_board.png          paleta e tipografia
assets/storyboard.jpg           frames-chave do animatic
assets/fonts/                   Anton e Share Tech Mono (licença OFL)
tools/                          scripts que geram tudo a partir de tools/timeline.py
```

## Leia antes de usar
- O **animatic não contém gameplay real**. Cada plano de jogo é um placeholder identificado (G01…G28) com a descrição exata do que gravar. O vídeo final depende dessas gravações.
- **Não há locução gravada.** O texto aparece como legenda no animatic. Este ambiente não tinha síntese de voz natural disponível, e uma voz robótica contrariaria o briefing.
- O **logo** do animatic é um placeholder tipográfico. Substitua pelo logotipo oficial.
- A **trilha é original**, sintetizada do zero, e pode ser usada no vídeo final.
- O briefing recebido começava na Cena 2. A **Cena 1 (cold open) é uma proposta**.

## Regenerar
Requer Python 3 com numpy, scipy e Pillow, mais o ffmpeg.
```bash
cd tools
python3 timeline.py          # valida a timeline (buracos, velocidade de fala)
python3 make_music.py        # trilha + SFX  -> output/audio
python3 export_docs.py       # EDL, SRT, CSVs -> edit/
python3 render_animatic.py   # animatic       -> output/ (cerca de 1 h em 4 núcleos)
python3 render_animatic.py --still 130.2   # um frame para conferência
```
Para mudar qualquer tempo, fala ou texto, edite **só `tools/timeline.py`** e rode os scripts de novo. Música, animatic, EDL e legendas continuam sincronizados.
