"""Gera os 5 slides do seminário · iteração 2, demonstração (sem2).

Regras do guia (passo 2):
- 4 a 6 slides: 1 capa + 1 por ponto.
- Cada slide carrega UMA ideia: a tela rodando (1), dois números (2), um erro
  ao lado do certo (3) e uma decisão (4). Nenhum slide tem parágrafo.
- A fala é da autora: os slides não trazem fala, só o que aparece na tela.
  As notas do orador guardam apenas de onde vem cada número.

Todos os números vêm de va2/exp.md, va2/flx.md e outputs/sem2/*.json
(versão 9727f6e). Nada aqui é estimado de novo.

Uso:  python tools/build_sem2_pptx.py
Saída: outputs/sem2_demonstracao.pptx
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'sem2_demonstracao.pptx'

BG = RGBColor(0x10, 0x12, 0x1A)
FG = RGBColor(0xF4, 0xF4, 0xF5)
MUTED = RGBColor(0xA1, 0xA1, 0xAA)
ACCENT = RGBColor(0x4A, 0xDE, 0x80)
WARN = RGBColor(0xF8, 0x71, 0x71)
CARD = RGBColor(0x1B, 0x1F, 0x2B)
CARD_ERR = RGBColor(0x2D, 0x1A, 0x1E)
CARD_OK = RGBColor(0x14, 0x29, 0x20)
TRACK = RGBColor(0x2A, 0x2F, 0x3E)

W, H = Inches(13.333), Inches(7.5)
MX = Inches(0.7)  # margem lateral
CW = W - 2 * MX  # largura útil
FONT = 'Segoe UI'


def new_slide(prs: Presentation, notes: str = ''):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG
    if notes:
        slide.notes_slide.notes_text_frame.text = notes
    return slide


def text(slide, txt, left, top, w, h, size, color=FG, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(left, top, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = txt
    r.font.name = FONT
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    return tb


def box(slide, left, top, w, h, fill=CARD, border=None, radius=0.06):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    shp.adjustments[0] = radius
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if border is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = border
        shp.line.width = Pt(2)
    shp.shadow.inherit = False
    return shp


def kicker(slide, label, color=ACCENT):
    text(slide, label, MX, Inches(0.45), CW, Inches(0.4), 16, color, bold=True)


def title(slide, label, size=36):
    text(slide, label, MX, Inches(0.95), CW, Inches(1.0), size, FG, bold=True)


def footer(slide, label):
    text(slide, label, MX, Inches(6.85), CW, Inches(0.4), 13, MUTED)


def build() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # ------------------------------------------------------------- 0 · capa
    s = new_slide(prs, 'Capa. Versão que roda: commit 9727f6e, branch feature/va2-sem2.')
    text(s, 'Luzia', MX, Inches(2.1), CW, Inches(1.5), 88, ACCENT, bold=True)
    text(s, 'a líder técnica de carreira dentro do agente', MX, Inches(3.75),
         CW, Inches(0.8), 32, FG)
    text(s, 'Rayane France · AI4Good · UFRPE · seminário 2: demonstração · versão 9727f6e',
         MX, Inches(6.5), CW, Inches(0.4), 16, MUTED)

    # ------------------------------------------------- 1 · ponta a ponta
    s = new_slide(
        prs,
        'Troca para a demo ao vivo (não é print): sessão do Claude Code no repositório de trabalho, '
        'comandos /luzia:* e painel em localhost:8501.\n'
        'Entrada real (exp.md §1): triagem Júnior 3 → Plena em 12 meses, currículo, GitHub rayfrance, '
        '6 notas do vault, 30 sessões (Claude Code + Codex), 39 commits com 34 itens mascarados por LGPD.',
    )
    kicker(s, '1 · A DEMO, AO VIVO')
    title(s, 'Do meu dia de trabalho ao que praticar')

    colw, gap, top, ch = Inches(3.7), Inches(0.5), Inches(2.3), Inches(3.0)
    cols = [
        ('ENTRADA', 'Eu: dev Júnior 3 → Plena em 12 meses',
         ['39 commits', '30 sessões com IA', '6 notas · currículo · GitHub'], CARD, None, MUTED),
        ('LUZIA', 'Máscara LGPD, local',
         ['depois Gemini flash-lite', 'código nunca sai', '34 itens mascarados'], CARD, None, MUTED),
        ('SAÍDA', 'Centelhas e um mapa até a meta',
         ['centelhas: o que praticar', 'propriedade das entregas', 'mapa de níveis'], CARD_OK, ACCENT, ACCENT),
    ]
    for i, (head, big, lines, fill, border, hc) in enumerate(cols):
        x = MX + i * (colw + gap)
        box(s, x, top, colw, ch, fill, border)
        text(s, head, x + Inches(0.3), top + Inches(0.25), colw - Inches(0.6), Inches(0.4), 15, hc, bold=True)
        text(s, big, x + Inches(0.3), top + Inches(0.7), colw - Inches(0.6), Inches(0.9), 22, FG, bold=True)
        text(s, '\n'.join(lines), x + Inches(0.3), top + Inches(1.75), colw - Inches(0.6), Inches(1.1), 16, MUTED)
        if i < 2:
            text(s, '→', x + colw, top + Inches(1.1), gap, Inches(0.6), 30, MUTED,
                 align=PP_ALIGN.CENTER)

    bar = box(s, MX, Inches(5.75), CW, Inches(0.95), CARD, ACCENT)
    text(s, '▶  AO VIVO', MX + Inches(0.35), Inches(5.75), Inches(2.6), Inches(0.95), 20, ACCENT,
         bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, '/luzia:centelhas  ·  /luzia:career-map', MX + Inches(3.0), Inches(5.75),
         CW - Inches(3.3), Inches(0.95), 22, FG, anchor=MSO_ANCHOR.MIDDLE)

    # ------------------------------------------------------ 2 · quanto custa
    s = new_slide(
        prs,
        'Fonte: va2/exp.md §2 e outputs/sem2/runs.jsonl (sem2-completo-1..3, versão 9727f6e). '
        'Tempos 13,47 / 13,01 / 12,95 s; pico 76,6 / 76,8 / 76,8 MiB; tokens 10.277 → ~2.720.\n'
        'Estimativa: va2/flx.md §2, registrada em 11/11 às 17h20, antes de medir.\n'
        'Diferença do tempo: tokens de entrada foram o dobro (10.277 vs ~5.000), a geração foi mais rápida, '
        'e o carregamento do SDK (~3,3 s) não estava na estimativa. '
        'Diferença da memória: o modelo roda na API, nenhum peso fica na RAM local; '
        'o servidor do painel (Streamlit) é outro processo e não foi medido.\n'
        'Uma tentativa terminou em 504 (timeout da API) e foi repetida.',
    )
    kicker(s, '2 · QUANTO CUSTA: MEDIDO × ESTIMADO NO FLX')
    title(s, 'O tempo bateu. A memória ficou 4× menor.')

    def metric(top, name, est_txt, est_frac, med_txt, med_frac, why):
        text(s, name, MX, top, Inches(2.6), Inches(0.5), 22, FG, bold=True)
        track_x, track_w = MX + Inches(2.7), Inches(7.3)
        for k, (lab, val, frac, col) in enumerate([
            ('estimado (flx)', est_txt, est_frac, MUTED),
            ('medido', med_txt, med_frac, ACCENT),
        ]):
            y = top + Inches(0.05) + k * Inches(0.62)
            box(s, track_x, y, track_w, Inches(0.45), TRACK, radius=0.5)
            box(s, track_x, y, max(int(track_w * frac), Inches(0.3)), Inches(0.45), col, radius=0.5)
            text(s, val, track_x + track_w + Inches(0.25), y - Inches(0.04), Inches(2.0), Inches(0.5),
                 22, col, bold=True)
            text(s, lab, MX, y + Inches(0.02), Inches(2.6), Inches(0.4), 13, MUTED)
        text(s, why, track_x, top + Inches(1.3), track_w + Inches(2.2), Inches(0.4), 15, MUTED)

    # ordem: nome + rótulos à esquerda; o nome fica acima da 1ª barra
    metric(Inches(2.2), 'Tempo total', '~13,0 s', 1.0, '13,14 s', 13.14 / 13.0,
           'mesmo total, por outra conta: 2× mais tokens, +3,3 s de SDK, geração mais rápida')
    metric(Inches(4.4), 'Pico de memória', '~300 MiB', 1.0, '76,7 MiB', 76.7 / 300,
           'o modelo roda na API: nenhum peso na RAM local')
    footer(s, 'média de 3 triagens · versão 9727f6e · Windows 11 · 12 CPUs · 16 GiB · Python 3.14.3 · gemini-3.5-flash-lite')

    # ---------------------------------------------------------- 3 · a falha
    s = new_slide(
        prs,
        'Fonte: va2/exp.md §3 e outputs/sem2/falha_run.json / career_state.json (versão 9727f6e).\n'
        'Execução: sem2-completo-3, a mesma triagem completa, com o histórico entre IAs '
        '(6 notas do vault + 30 sessões).\n'
        'Reserva, mesma falha por outro caminho: sem2-falha-fontes-estaticas (só currículo, GitHub e commits) '
        'deu "Sem conflito relevante, currículo alinhado com commits recentes." e programação agêntica 4/5.\n'
        'Quem sofre: a própria desenvolvedora, com mapa de carreira e plano de estudo errados.\n'
        'Vira medida no sem3: com que frequência a sugestão contraria a autoavaliação por causa de fonte estática.',
    )
    kicker(s, '3 · ONDE ERRA', WARN)
    title(s, 'Uma nota parada rebaixou o meu DDD', 38)

    cw2, ch2, top2 = Inches(5.85), Inches(3.55), Inches(2.1)
    box(s, MX, top2, cw2, ch2, CARD_ERR, WARN)
    text(s, '✕  COMO SAIU', MX + Inches(0.35), top2 + Inches(0.25), cw2, Inches(0.4), 15, WARN, bold=True)
    text(s, 'DDD 1/5', MX + Inches(0.35), top2 + Inches(0.8), cw2, Inches(1.2), 64, FG, bold=True)
    text(s, '“Início do estudo formal no clube de leitura e notas do capítulo 1.”',
         MX + Inches(0.35), top2 + Inches(2.1), cw2 - Inches(0.7), Inches(1.2), 20, MUTED)

    x2 = MX + cw2 + Inches(0.5)
    box(s, x2, top2, cw2, ch2, CARD_OK, ACCENT)
    text(s, '✓  O CERTO', x2 + Inches(0.35), top2 + Inches(0.25), cw2, Inches(0.4), 15, ACCENT, bold=True)
    text(s, 'Nível = minha autoavaliação', x2 + Inches(0.35), top2 + Inches(0.8), cw2 - Inches(0.7),
         Inches(1.3), 32, FG, bold=True)
    text(s, 'A nota do capítulo 1 só diz que DDD é um tópico em estudo.',
         x2 + Inches(0.35), top2 + Inches(2.3), cw2 - Inches(0.7), Inches(1.0), 20, MUTED)

    text(s, 'Quem sofre: eu, com um mapa e um plano de estudo errados', MX, Inches(5.95), CW, Inches(0.5), 22, FG,
         bold=True)
    text(s, 'a regra “fonte parada não define nível” já estava no prompt, e não bastou',
         MX, Inches(6.45), CW, Inches(0.4), 16, MUTED)
    footer(s, 'entrada: a mesma triagem, com histórico entre IAs · execução sem2-completo-3 · versão 9727f6e')

    # ---------------------------------------------------- 4 · o que mudou
    s = new_slide(
        prs,
        'Fonte do sem1: va2/sem1.md (produto chamado Leadroid; comandos @... só como conceito; painel de progresso). '
        'Fonte do sem2: va2/sem2.md (frase 4) e o código de code/luzia/ na versão apresentada.\n'
        'Mantido de propósito: o nível continua declarado por mim (sem1: "o Leadroid não tenta adivinhar o meu nível"), '
        'e a falha do slide 3 mostra o porquê.\n'
        'O observador de sessão (hook) ainda não existe no Codex, no Cursor nem no Antigravity.',
    )
    kicker(s, '4 · O QUE MUDOU DESDE O SEM1')
    title(s, 'Leadroid virou Luzia, e o uso virou jogo', 38)

    cw3, ch3, top3 = Inches(3.7), Inches(2.7), Inches(2.2)
    items = [
        ('NO SEM1', 'Leadroid', 'painel de progresso e comandos como conceito', CARD, None, MUTED),
        ('AGORA', 'Luzia, com centelhas', 'o progresso vira centelhas para acender', CARD_OK, ACCENT, ACCENT),
        ('POR QUÊ', 'Luz + IA', 'e um uso contínuo mais estimulante', CARD, ACCENT, ACCENT),
    ]
    g3 = Inches(0.5)
    for i, (head, big, sub, fill, border, hc) in enumerate(items):
        x = MX + i * (cw3 + g3)
        box(s, x, top3, cw3, ch3, fill, border)
        text(s, head, x + Inches(0.3), top3 + Inches(0.25), cw3, Inches(0.4), 15, hc, bold=True)
        text(s, big, x + Inches(0.3), top3 + Inches(0.8), cw3 - Inches(0.6), Inches(0.95), 26, FG, bold=True)
        text(s, sub, x + Inches(0.3), top3 + Inches(1.75), cw3 - Inches(0.6), Inches(0.8), 17, MUTED)
        if i < 2:
            text(s, '→', x + cw3, top3 + Inches(1.0), g3, Inches(0.6), 30, MUTED, align=PP_ALIGN.CENTER)

    text(s, 'Mantido de propósito', MX, Inches(5.4), CW, Inches(0.4), 15, MUTED, bold=True)
    text(s, 'o nível continua declarado por mim, não deduzido (a falha do slide 3)',
         MX, Inches(5.85), CW, Inches(0.5), 20, FG)
    footer(s, 'só no Claude Code: o observador ainda não existe no Codex, no Cursor nem no Antigravity')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f'{len(prs.slides)} slides gerados em {OUT}')


if __name__ == '__main__':
    build()
