"""Fonte única da timeline do vídeo "ULTRAKILL — A ARTE DO CAOS".

Tudo aqui está em segundos. A trilha foi composta a 180 BPM:
1 batida = 1/3 s (10 frames a 30 fps), 1 compasso = 4/3 s (40 frames).
Os cortes, impactos e textos caem sempre em múltiplos de batida.

Este arquivo alimenta:
  - render_animatic.py  (vídeo animatic com placeholders)
  - make_music.py       (trilha original e efeitos sintetizados)
  - export_docs.py      (SRT da narração, EDL/CSV da timeline, lista de captura)
"""

BPM = 180
BEAT = 60 / BPM          # 0.333 s
BAR = 4 * BEAT           # 1.333 s
FPS = 30
DURATION = 312.0         # 5:12


def b(n):
    """Converte batidas em segundos."""
    return round(n * BEAT, 4)


# ---------------------------------------------------------------------------
# CENAS
# ---------------------------------------------------------------------------
SCENES = [
    # id, início, fim, título, energia da música
    ("C1", 0.0, 16.0, "ABERTURA — COLD OPEN", "explosão"),
    ("C2", 16.0, 64.0, "O QUE É ULTRAKILL?", "groove médio"),
    ("C3", 64.0, 144.0, "A ARTE DO CAOS", "breakcore total"),
    ("C4", 144.0, 208.0, "O INFERNO E SUA ATMOSFERA", "drone → drop"),
    ("C5", 208.0, 264.0, "POR QUE É TÃO VICIANTE?", "groove melódico"),
    ("C6", 264.0, 312.0, "ENCERRAMENTO", "clímax → silêncio"),
]


# ---------------------------------------------------------------------------
# GRAVAÇÕES NECESSÁRIAS (lista de captura)
# G = gameplay que precisa ser gravado / A = arte oficial (press kit)
# ---------------------------------------------------------------------------
CAPTURES = {
    "G01": ("Primeiro combate de 1-1 (Limbo)", "Entrada em arena, mortes no ar com revólver e shotgun, HUD ligado."),
    "G04": ("Cura por sangue", "Explodir um inimigo à queima-roupa e mostrar a barra de vida subindo com o sangue. Gravar também em câmera lenta (Sandbox + slowmo do editor)."),
    "G05": ("Dash triplo", "Três dashes seguidos com a barra de stamina visível no HUD."),
    "G06": ("Slide + slide jump", "Slide longo atravessando a arena e pulo no fim do slide (ganho de distância)."),
    "G07": ("Wall jumps", "Escalar uma parede/pilar com saltos na parede consecutivos."),
    "G08": ("Ground slam + pulo", "Slam do alto até o chão e pulo imediato ao aterrissar (salto mais alto)."),
    "G09": ("Movimento encadeado", "20–30 s contínuos de dash/slide/slam/wall jump em arena vertical, matando sem parar. Ideal: Cyber Grind ou camada 7."),
    "G10": ("Troca de armas", "Um combate usando revólver, shotgun, nailgun, railcannon e lança-foguetes em sequência rápida. Gravar 1 kill limpa por arma."),
    "G11": ("Variantes", "Railcannon Electric atravessando fila de inimigos; Freezeframe do lança-foguetes; Nailgun com variante de ímã; Core Eject da shotgun."),
    "G12": ("Moeda simples", "Revólver Marksman: jogar moeda e acertar o tiro nela, ricocheteando num inimigo. Ângulo limpo, de preferência no Sandbox."),
    "G13": ("Corrente de moedas", "3–4 moedas no ar encadeadas em um único tiro. Repetir até sair perfeito."),
    "G14": ("Railcoin", "Tiro do railcannon acertando uma moeda e ricocheteando."),
    "G15": ("Parry de projétil", "Socar de volta um projétil inimigo (Feedbacker), matando o atirador. Mostrar o flash e a barra de vida enchendo."),
    "G16": ("Projectile boost", "Disparar a shotgun e socar os estilhaços logo em seguida."),
    "G17": ("Parry corpo a corpo", "Parry num ataque corpo a corpo de inimigo/chefe que permita parry. Gravar 3 tentativas boas."),
    "G18": ("Medidor de estilo", "Combate longo com o medidor de estilo visível subindo do D até o ULTRAKILL. HUD ligado, Cyber Grind em onda alta."),
    "G19": ("Arma 'stale'", "Usar a mesma arma repetidamente até o medidor indicar que ela ficou repetitiva (freshness caindo)."),
    "G20a": ("Ambiente — Limbo (1-x)", "Planos lentos sem combate, HUD desligado. Mouse suave, panorâmicas de 6–8 s."),
    "G20b": ("Ambiente — Lust (2-x)", "Planos lentos sem combate, HUD desligado."),
    "G20c": ("Ambiente — Gluttony (3-x)", "Planos lentos sem combate, HUD desligado."),
    "G20d": ("Ambiente — Greed (4-x)", "Planos lentos sem combate, HUD desligado."),
    "G20e": ("Ambiente — Wrath (5-x)", "Planos lentos sem combate, HUD desligado."),
    "G20f": ("Ambiente — Heresy (6-x) e Violence (7-x)", "Planos lentos sem combate, HUD desligado."),
    "G21": ("Inimigos", "Close de Filth, Stray, Malicious Face e Mindflayer (Sandbox com braço spawner ou fases)."),
    "G22": ("Chefes", "V2 (1-4) e Gabriel (3-2). Momentos de entrada e o primeiro golpe de cada luta."),
    "G23": ("Chefe em fúria", "15–20 s do trecho mais intenso de uma luta de chefe, com parries e trocas de arma."),
    "G24": ("Tela de resultado", "Tela final de fase com nota em tempo, kills e estilo; uma versão comum e uma com P-RANK."),
    "G25": ("Mesma fase, 3 tentativas", "O MESMO encontro gravado 3 vezes: tentativa ruim, média e a melhor (para split screen)."),
    "G26": ("Cyber Grind", "Ondas altas do Cyber Grind, plano aberto da arena mudando."),
    "G27": ("Sandbox", "Experimentos: combos de moeda + railcannon, explosões, criatividade."),
    "G28": ("Clipes de alto nível", "Melhores momentos (seus ou de criadores que autorizarem por escrito)."),
    "A01": ("Logotipo oficial ULTRAKILL", "Do press kit oficial da New Blood ou página da Steam, conforme termos de uso."),
    "A02": ("Arte oficial de V1", "Key art do press kit / Steam."),
}


# ---------------------------------------------------------------------------
# PLANOS (vídeo, trilha V1)
# kind: "gp" gameplay placeholder | "card" tela tipográfica | "type" texto digitado
#       "black" preto | "logo" logotipo | "split" tela dividida
# ---------------------------------------------------------------------------
SHOTS = []


def shot(t0, t1, kind, ref="", note="", trans="corte", speed="100%"):
    SHOTS.append(dict(t0=round(t0, 4), t1=round(t1, 4), kind=kind, ref=ref, note=note,
                      trans=trans, speed=speed))


def montage(t0, t1, step_beats, refs, note="", trans="corte seco"):
    """Divide [t0, t1) em cortes de `step_beats` batidas, alternando as gravações."""
    t, i = t0, 0
    step = b(step_beats)
    while t < t1 - 1e-6:
        e = min(t + step, t1)
        shot(t, e, "gp", refs[i % len(refs)], note, trans)
        t, i = e, i + 1


# C1 — ABERTURA (0:00–0:16)
shot(0.0, 4.0, "type", note="Tela preta. Frase oficial do jogo digitada letra a letra.")
montage(4.0, 4.0 + b(16), 2, ["G09", "G13", "G15", "G23", "G18", "G08", "G14", "G28"],
        note="Montagem: 1 corte a cada 2 batidas")
montage(4.0 + b(16), 12.6667, 1, ["G28", "G16", "G06", "G23", "G12", "G07", "G26", "G04", "G11", "G17"],
        note="Montagem: 1 corte por batida")
shot(12.6667, 13.0, "flash", note="Flash branco 1 batida")
shot(13.0, 16.0, "card", note="TÍTULO: ULTRAKILL — A ARTE DO CAOS", trans="corte no impacto")

# C2 — O QUE É ULTRAKILL? (0:16–1:04)
shot(16.0, 20.0, "gp", "G01", "Primeiro combate. Legenda: Arsi 'Hakita' Patala / New Blood Interactive")
shot(20.0, 24.0, "gp", "A02", "Key art de V1 com zoom lento (Ken Burns 100→108%)")
shot(24.0, 28.0, "gp", "G09", "Filtro CRT/scanline leve para remeter aos FPS dos anos 90")
shot(28.0, 34.6667, "gp", "G18", "Zoom digital no medidor de estilo")
shot(34.6667, 35.0, "black", note="1 batida de preto — a música cai")
shot(35.0, 38.6667, "card", note="MANKIND IS DEAD.")
shot(38.6667, 42.0, "card", note="BLOOD IS FUEL.")
shot(42.0, 45.3333, "card", note="HELL IS FULL.")
shot(45.3333, 51.0, "gp", "A02", "V1 — corte para a descida (G20a ao fundo)", trans="whip pan")
shot(51.0, 58.0, "gp", "G04", "Cura por sangue: rampa de velocidade 100% → 30% → 100%", speed="rampa")
shot(58.0, 64.0, "gp", "G09", "Avanço agressivo, sem parar")

# C3 — A ARTE DO CAOS (1:04–2:24)
shot(64.0, 66.6667, "card", note="A ARTE DO CAOS (impacto)", trans="corte no drop")
shot(66.6667, 68.0, "gp", "G09", "V1 acelerando")
shot(68.0, 69.3333, "gp", "G05", "TAG: DASH")
shot(69.3333, 70.6667, "gp", "G06", "TAG: SLIDE")
shot(70.6667, 72.0, "gp", "G07", "TAG: WALL JUMP")
shot(72.0, 73.3333, "gp", "G08", "TAG: SLAM")
shot(73.3333, 76.0, "gp", "G06", "Slide → pulo longo (linha de trajetória desenhada)")
shot(76.0, 78.6667, "gp", "G08", "Slam → salto alto (linha de trajetória desenhada)")
shot(78.6667, 82.6667, "gp", "G09", "Plano longo vertical — a arena vira 3D")
shot(82.6667, 84.0, "gp", "G10", "TAG: REVOLVER")
shot(84.0, 85.3333, "gp", "G10", "TAG: SHOTGUN")
shot(85.3333, 86.6667, "gp", "G10", "TAG: NAILGUN")
shot(86.6667, 88.0, "gp", "G10", "TAG: RAILCANNON")
shot(88.0, 89.3333, "gp", "G10", "TAG: ROCKET LAUNCHER")
montage(89.3333, 96.0, 2, ["G11"], note="Variantes — 1 corte a cada 2 batidas")
shot(96.0, 100.0, "gp", "G10", "Trocas de arma no meio do combo (HUD de estilo visível)")
shot(100.0, 104.0, "gp", "G12", "Moeda simples — som de moeda em destaque")
shot(104.0, 109.3333, "gp", "G13", "Corrente de moedas — freeze-frame de 2 batidas com linhas ligando as moedas")
shot(109.3333, 113.3333, "gp", "G14", "Railcoin")
shot(113.3333, 116.0, "gp", "G13", "Replay da corrente em velocidade 50%", speed="50%")
shot(116.0, 120.0, "gp", "G15", "Parry de projétil — flash + zoom punch")
shot(120.0, 125.3333, "gp", "G16", "Projectile boost — repetir o soco 2x (rewind de 6 frames)")
shot(125.3333, 130.0, "gp", "G17", "Parry corpo a corpo")
shot(130.0, 135.3333, "gp", "G18", "Ranks de estilo pipocando na tela, 1 por 2 batidas")
shot(135.3333, 139.3333, "gp", "G19", "Freshness caindo (destacar com zoom e círculo)")
montage(139.3333, 144.0, 1, ["G28", "G23", "G13", "G09"], note="Fecho de cena — 1 corte por batida")

# C4 — O INFERNO (2:24–3:28)
shot(144.0, 150.0, "gp", "G20a", "Limbo — crossfade lento", trans="dissolve 1 s")
shot(150.0, 155.0, "gp", "G20b", "Lust", trans="dissolve 1 s")
shot(155.0, 160.0, "gp", "G20c", "Gluttony", trans="dissolve 1 s")
shot(160.0, 165.0, "gp", "G20d", "Greed", trans="dissolve 1 s")
shot(165.0, 170.0, "gp", "G20e", "Wrath", trans="dissolve 1 s")
shot(170.0, 175.0, "gp", "G20f", "Heresy / Violence", trans="dissolve 1 s")
shot(175.0, 176.75, "gp", "G21", "Filth", trans="corte")
shot(176.75, 178.5, "gp", "G21", "Stray")
shot(178.5, 180.25, "gp", "G21", "Malicious Face")
shot(180.25, 182.0, "gp", "G21", "Mindflayer")
shot(182.0, 186.3333, "gp", "G22", "V2 — entrada", trans="dip to black")
shot(186.3333, 190.6667, "gp", "G22", "Gabriel — entrada", trans="dip to black")
shot(190.6667, 192.0, "black", note="Silêncio total (4 batidas). Só respiração/eco.")
montage(192.0, 208.0, 1, ["G23", "G17", "G23", "G15", "G23", "G28"], note="DROP — chefe em fúria, 1 corte por batida", trans="corte seco + flash")

# C5 — VICIANTE (3:28–4:24)
shot(208.0, 212.0, "gp", "G24", "Tela de resultado — ranks contando")
shot(212.0, 220.0, "gp", "G24", "P-RANK — zoom + glow dourado")
shot(220.0, 232.0, "split", "G25", "Split screen 3 colunas: tentativa 1 / 2 / 3 sincronizadas no mesmo ponto")
shot(232.0, 240.0, "gp", "G27", "Experimentação no Sandbox")
shot(240.0, 248.0, "gp", "G26", "Cyber Grind")
shot(248.0, 258.0, "gp", "G28", "Execução limpa — sem cortes, deixar respirar")
shot(258.0, 264.0, "card", note="NÃO É SOBRE ATIRAR. / É SOBRE PERFORMANCE.")

# C6 — ENCERRAMENTO (4:24–5:12)
montage(264.0, 280.0, 2, ["G28", "G13", "G23", "G09", "G14", "G16"], note="Build — 1 corte a cada 2 batidas")
montage(280.0, 296.0, 1, ["G28", "G18", "G23", "G13", "G17", "G26", "G14", "G04"], note="Clímax — 1 corte por batida")
shot(296.0, 297.0, "black", note="CORTE SECO PARA SILÊNCIO")
shot(297.0, 299.6667, "card", note="YOU ARE NOT HERE TO SURVIVE.")
shot(299.6667, 302.6667, "card", note="YOU ARE HERE TO DOMINATE.")
shot(302.6667, 308.0, "logo", "A01", "Logotipo ULTRAKILL + impacto", trans="corte no impacto")
shot(308.0, 312.0, "black", note="Fade para preto", trans="fade 1 s")


# ---------------------------------------------------------------------------
# NARRAÇÃO (PT-BR) — início, fim, fala, direção de voz
# ---------------------------------------------------------------------------
NARRATION = [
    # C1
    (5.0, 8.6667, "Imagina um FPS que não quer saber se você vai sobreviver…", "baixo, quase sussurrado"),
    (9.0, 12.3333, "…e sim se você vai fazer isso com estilo.", "sorriso na voz, subindo"),
    # C2
    (16.3333, 22.6667, "ULTRAKILL é um FPS criado pelo desenvolvedor finlandês Arsi “Hakita” Patala, publicado pela New Blood Interactive.", "natural, ritmo de conversa"),
    (23.6667, 27.6667, "Ele bebe direto da fonte dos shooters dos anos 90, tipo DOOM e Quake…", "nostálgico"),
    (28.0, 34.0, "…mas mistura isso com um medidor de estilo que julga cada segundo do seu combate.", "ênfase em 'julga'"),
    (35.3333, 38.0, "A premissa é simples: a humanidade acabou.", "seco, pausa depois"),
    (38.6667, 41.6667, "As máquinas que sobraram funcionam à base de sangue.", "seco"),
    (42.0, 44.6667, "E o Inferno… está lotado.", "pausa antes de 'está lotado'"),
    (45.6667, 50.6667, "Você é V1: uma máquina de guerra que desce camada por camada do Inferno atrás de combustível.", "firme"),
    (51.3333, 57.6667, "E o detalhe que muda tudo: V1 se cura com o sangue dos inimigos. Mas só se estiver perto o bastante pra se banhar nele.", "explicativo, 'banhar' com prazer"),
    (58.3333, 63.3333, "Ou seja: ficar escondido não é uma opção. O jogo te empurra pra frente.", "acelerando"),
    # C3
    (64.0, 65.6667, "Então vamos falar de combate.", "energia lá em cima"),
    (65.6667, 68.0, "V1 é rápida. Absurdamente rápida.", "rápido"),
    (68.0, 73.3333, "Dash. Slide. Salto na parede. Slam.", "cada palavra no corte"),
    (73.3333, 78.3333, "E tudo se encadeia: o slide vira um pulo longo, o slam vira um salto ainda mais alto.", "fluido"),
    (78.6667, 82.3333, "A arena deixa de ser um chão… e vira um espaço em três dimensões.", ""),
    (82.6667, 89.3333, "Revólver. Shotgun. Nailgun. Railcannon. Lança-foguetes.", "cada nome no corte"),
    (89.6667, 95.6667, "E cada arma tem variantes que mudam completamente o jeito de jogar.", ""),
    (96.0, 99.6667, "Trocar de arma no meio do combo não é só permitido. É recompensado.", "ênfase em 'recompensado'"),
    (100.0, 102.0, "E aí… tem as moedas.", "pausa dramática, quase rindo"),
    (102.3333, 109.3333, "Uma variante do revólver joga moedas pro alto. Você atira nelas, e o tiro ricocheteia no inimigo. Ou em outra moeda. E em outra.", "acelerando no fim"),
    (109.6667, 113.3333, "Dá pra ricochetear até o disparo do railcannon.", "incrédulo"),
    (116.0, 119.6667, "Inimigo atirou em você? Soca de volta.", "provocador"),
    (120.0, 125.3333, "Dá pra socar até os próprios tiros: shotgun e soco na sequência, e os estilhaços saem turbinados.", "rápido"),
    (125.3333, 129.6667, "E acertar um parry ainda te devolve vida. Defender é atacar.", "firme"),
    (130.0, 134.6667, "Tudo isso alimenta o medidor de estilo. De Destructive até ULTRAKILL.", "subindo junto com os ranks"),
    (135.3333, 139.0, "Repetir a mesma arma? O estilo cai. O jogo quer variedade.", ""),
    (139.3333, 143.6667, "Habilidade, agressividade e criatividade. Tudo ao mesmo tempo.", "três batidas, uma por palavra"),
    # C4
    (145.3333, 149.6667, "Mas não dá pra falar de ULTRAKILL sem falar do lugar onde tudo acontece.", "baixo, contemplativo"),
    (150.3333, 157.6667, "O jogo é dividido em camadas inspiradas no Inferno de Dante: Limbo, Luxúria, Gula, Ganância, Ira, Heresia, Violência…", "devagar, cada camada no seu plano"),
    (158.6667, 168.6667, "E cada camada tem identidade própria. Arquitetura, cor e música mudam a cada descida, e a trilha do Heaven Pierce Her acompanha cada uma delas.", ""),
    (170.0, 174.6667, "O Inferno de ULTRAKILL é bonito. Estranho. E sempre hostil.", "pausas entre as palavras"),
    (175.0, 181.6667, "Lá embaixo vivem Filths, Strays, Malicious Faces… e Mindflayers.", "nome a nome, no corte"),
    (182.3333, 190.3333, "E os chefes são outro nível. V2, uma máquina como você. Gabriel, o Juiz do Inferno.", "tensão crescendo"),
    (191.0, 191.6667, "E aí…", "sussurro, no silêncio"),
    # C5
    (208.3333, 211.6667, "Então por que é tão difícil largar ULTRAKILL?", "curioso, mais leve"),
    (212.0, 219.6667, "Porque toda fase termina com uma nota. E a nota máxima, o P-Rank, exige S em tudo, sem morrer.", ""),
    (220.0, 231.6667, "Aí você volta. Descobre uma rota mais rápida. Um combo que nem sabia que existia. Um jeito de limpar a sala em dois segundos em vez de dez.", "ritmo crescendo"),
    (232.0, 239.6667, "O jogo não muda. Você muda. No começo você sobrevive. Depois você entende. E no fim… você se exibe.", "pausa antes de 'se exibe'"),
    (240.0, 247.6667, "E tem o Cyber Grind, com ondas infinitas, e o Sandbox, pra testar qualquer maluquice que você imaginar.", ""),
    (248.3333, 257.6667, "No fim das contas, ULTRAKILL não é só sobre atirar. É sobre transformar o combate numa performance.", "a frase-tese do vídeo, devagar"),
    # C6
    (297.3333, 302.3333, "Você não está aqui pra sobreviver. Está aqui pra dominar.", "baixo, grave, sem pressa"),
]


# ---------------------------------------------------------------------------
# TEXTOS NA TELA (motion graphics) — início, fim, texto, estilo
# estilos: tag (palavra-impacto), rank (rank de estilo), lower (lower third),
#          title, big (frase grande), small
# ---------------------------------------------------------------------------
TEXTS = [
    (0.6667, 4.0, "MANKIND IS DEAD.|BLOOD IS FUEL.|HELL IS FULL.", "typewriter"),
    (13.0, 16.0, "ULTRAKILL|A ARTE DO CAOS", "title"),
    (16.3333, 20.0, "ARSI \"HAKITA\" PATALA  //  NEW BLOOD INTERACTIVE", "lower"),
    (24.0, 28.0, "DOOM / QUAKE", "small"),
    (28.0, 34.6667, "MEDIDOR DE ESTILO", "small"),
    (35.0, 38.6667, "MANKIND IS DEAD.", "big"),
    (38.6667, 42.0, "BLOOD IS FUEL.", "big"),
    (42.0, 45.3333, "HELL IS FULL.", "big"),
    (45.6667, 51.0, "V1", "tag"),
    (51.3333, 58.0, "SANGUE = VIDA", "small"),
    (64.0, 66.6667, "A ARTE DO CAOS", "title"),
    (68.0, 69.3333, "DASH", "tag"),
    (69.3333, 70.6667, "SLIDE", "tag"),
    (70.6667, 72.0, "WALL JUMP", "tag"),
    (72.0, 73.3333, "SLAM", "tag"),
    (82.6667, 84.0, "REVOLVER", "tag"),
    (84.0, 85.3333, "SHOTGUN", "tag"),
    (85.3333, 86.6667, "NAILGUN", "tag"),
    (86.6667, 88.0, "RAILCANNON", "tag"),
    (88.0, 89.3333, "ROCKET LAUNCHER", "tag"),
    (100.0, 102.0, "$", "coin"),
    (116.0, 117.3333, "PARRY", "tag"),
    (130.0, 130.6667, "DESTRUCTIVE", "rank:D"),
    (130.6667, 131.3333, "CHAOTIC", "rank:C"),
    (131.3333, 132.0, "BRUTAL", "rank:B"),
    (132.0, 132.6667, "ANARCHIC", "rank:A"),
    (132.6667, 133.3333, "SUPREME", "rank:S"),
    (133.3333, 134.0, "SSADISTIC", "rank:SS"),
    (134.0, 134.6667, "SSSHITSTORM", "rank:SSS"),
    (134.6667, 135.3333, "ULTRAKILL", "rank:U"),
    (139.3333, 140.6667, "HABILIDADE", "tag"),
    (140.6667, 142.0, "AGRESSIVIDADE", "tag"),
    (142.0, 144.0, "CRIATIVIDADE", "tag"),
    (144.5, 150.0, "LIMBO", "small"),
    (150.0, 155.0, "LUST", "small"),
    (155.0, 160.0, "GLUTTONY", "small"),
    (160.0, 165.0, "GREED", "small"),
    (165.0, 170.0, "WRATH", "small"),
    (170.0, 175.0, "HERESY / VIOLENCE", "small"),
    (175.0, 176.75, "FILTH", "small"),
    (176.75, 178.5, "STRAY", "small"),
    (178.5, 180.25, "MALICIOUS FACE", "small"),
    (180.25, 182.0, "MINDFLAYER", "small"),
    (182.0, 186.3333, "V2", "tag"),
    (186.3333, 190.6667, "GABRIEL", "tag"),
    (212.0, 220.0, "P", "prank"),
    (220.0, 232.0, "TENTATIVA 1|TENTATIVA 2|TENTATIVA 3", "split"),
    (240.0, 244.0, "CYBER GRIND", "small"),
    (232.0, 236.0, "SANDBOX", "small"),
    (258.0, 261.0, "NÃO É SOBRE ATIRAR.", "big"),
    (261.0, 264.0, "É SOBRE PERFORMANCE.", "big"),
    (297.0, 299.6667, "YOU ARE NOT HERE TO SURVIVE.", "big"),
    (299.6667, 302.6667, "YOU ARE HERE TO DOMINATE.", "big"),
]


# ---------------------------------------------------------------------------
# IMPACTOS (flash + shake + som de impacto) — tempo, intensidade 0..1
# ---------------------------------------------------------------------------
HITS = [
    (4.0, 1.0), (13.0, 1.0), (16.0, 0.6), (35.0, 0.7), (38.6667, 0.7), (42.0, 0.9),
    (45.3333, 0.6), (64.0, 1.0), (68.0, 0.6), (69.3333, 0.6), (70.6667, 0.6), (72.0, 0.9),
    (82.6667, 0.6), (84.0, 0.6), (85.3333, 0.6), (86.6667, 0.6), (88.0, 0.8),
    (100.0, 0.5), (116.0, 0.9), (130.0, 0.6), (134.6667, 1.0), (139.3333, 0.7),
    (140.6667, 0.7), (142.0, 0.9), (192.0, 1.0), (208.0, 0.6), (212.0, 0.8),
    (258.0, 0.7), (261.0, 0.8), (264.0, 0.8), (280.0, 1.0), (297.0, 0.9),
    (299.6667, 1.0), (302.6667, 1.0),
]

# Efeitos sonoros pontuais (além dos impactos) — tempo, tipo
SFX = [
    (0.6667, "type"), (1.6667, "type"), (2.6667, "type"),
    (9.3333, "riser_end"), (63.0, "riser_end"),
    (68.0, "whoosh"), (69.3333, "whoosh"), (70.6667, "whoosh"), (72.0, "slam"),
    (100.6667, "coin"), (101.3333, "coin"), (104.6667, "coin"), (105.0, "coin"),
    (105.3333, "coin"), (105.6667, "coin"), (110.0, "rail"),
    (116.6667, "parry"), (120.6667, "parry"), (126.0, "parry"),
    (130.0, "ui"), (130.6667, "ui"), (131.3333, "ui"), (132.0, "ui"),
    (132.6667, "ui"), (133.3333, "ui"), (134.0, "ui"), (134.6667, "ui"),
    (190.6667, "breath"), (212.0, "ui"), (296.0, "cut"), (302.6667, "boom"),
]


def scene_at(t):
    for sid, t0, t1, title, _ in SCENES:
        if t0 <= t < t1:
            return sid, title
    return SCENES[-1][0], SCENES[-1][3]


def validate():
    """Checa buracos/sobreposições e velocidade de fala."""
    errs = []
    s = sorted(SHOTS, key=lambda x: x["t0"])
    for a, c in zip(s, s[1:]):
        if abs(a["t1"] - c["t0"]) > 0.01:
            errs.append(f"buraco/sobreposição entre {a['t1']} e {c['t0']}")
    if abs(s[0]["t0"]) > 0.01 or abs(s[-1]["t1"] - DURATION) > 0.01:
        errs.append("timeline não cobre 0..DURATION")
    for t0, t1, txt, _ in NARRATION:
        cps = len(txt) / (t1 - t0)
        if cps > 19:
            errs.append(f"fala rápida demais ({cps:.1f} c/s): {txt[:40]}")
    return errs


if __name__ == "__main__":
    e = validate()
    print("\n".join(e) if e else f"OK — {len(SHOTS)} planos, {len(NARRATION)} falas")
