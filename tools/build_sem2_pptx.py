"""Gera os 5 slides do seminário · iteração 2, demonstração (sem2).

Regra do guia (passo 2):
- 4 a 6 slides (1 capa + 4 pontos).
- Cada slide carrega UMA ideia: uma troca para a tela ao vivo (slide 1),
  os números medidos vs. estimados no flx (slide 2), a saída errada ao lado
  do certo (slide 3) e a decisão que mudou/manteve desde o sem1 (slide 4).
- Nenhum slide tem parágrafo.

Uso:  python tools/build_sem2_pptx.py
Saída: outputs/sem2_demonstracao.pptx
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'sem2_demonstracao.pptx'

BG = RGBColor(0x10, 0x12, 0x1A)
FG = RGBColor(0xF4, 0xF4, 0xF5)
MUTED = RGBColor(0xA1, 0xA1, 0xAA)
ACCENT = RGBColor(0x4A, 0xDE, 0x80)
WARN = RGBColor(0xF8, 0x71, 0x71)
CARD = RGBColor(0x1F, 0x23, 0x30)
CARD_ERR = RGBColor(0x2D, 0x1A, 0x1E)
CARD_OK = RGBColor(0x14, 0x29, 0x20)


def new_slide(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG
    return slide


def text(slide, txt: str, left, top, w, h, size: int, color=FG, bold: bool = False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(left, top, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = txt
    p.alignment = align
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    return tb


def card(slide, title: str, lines: list[str], left, top, w, h, fill=CARD, border=ACCENT, title_color=ACCENT):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = border
    shp.line.width = Pt(2)
    tf = shp.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.size = Pt(20)
    p0.font.bold = True
    p0.font.color.rgb = title_color
    p0.space_after = Pt(10)
    for line in lines:
        p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(18)
        p.font.color.rgb = FG
        p.space_after = Pt(6)
    return shp


def build() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    # ----------------------------------------------------------- Slide 0: Capa
    s0 = new_slide(prs)
    text(s0, 'LuzIA', Inches(0.8), Inches(2.0), Inches(11.7), Inches(1.4), 72, ACCENT, bold=True)
    text(
        s0,
        'iteração 2 · demonstração ponta a ponta no agente',
        Inches(0.8), Inches(3.5), Inches(11.7), Inches(0.9), 30, FG,
    )
    text(
        s0,
        'Rayane France · AI4Good · UFRPE · 11/11/2026 · tag: sem2',
        Inches(0.8), Inches(6.3), Inches(11.7), Inches(0.5), 16, MUTED,
    )

    # ---------------------------------------------- Slide 1: Ponta a ponta
    s1 = new_slide(prs)
    text(s1, '1 · PONTA A PONTA (AO VIVO)', Inches(0.6), Inches(0.4), Inches(12), Inches(0.5), 16, ACCENT, bold=True)
    text(
        s1,
        'Ao vivo no Claude Desktop + painel @career-map',
        Inches(0.6), Inches(1.0), Inches(12), Inches(0.8), 32, FG, bold=True,
    )
    card(
        s1,
        'Entrada real (com filtro local LGPD)',
        [
            '• Declaração: Dev Fullstack Jr 3 → Pleno em 12 meses (DDD + IA)',
            '• Currículo + GitHub (rayfrance)',
            '• Histórico entre IAs: Obsidian (ddd-cap-01) + Claude Code + Codex',
            '• 39 commits meus no repo de trabalho (31 itens mascarados)',
        ],
        Inches(0.6), Inches(2.2), Inches(5.8), Inches(4.3),
    )
    card(
        s1,
        'Comandos rodando agora na máquina',
        [
            '• /LuzIA:triage',
            '• /LuzIA:feedback-skills-opportunities',
            '• /LuzIA:feedback-progress',
            '• /LuzIA:next-level',
            '• /LuzIA:career-map  →  streamlit run code/leadroid/app.py',
        ],
        Inches(6.9), Inches(2.2), Inches(5.8), Inches(4.3),
    )

    # ---------------------------------------------- Slide 2: Quanto custa
    s2 = new_slide(prs)
    text(s2, '2 · QUANTO CUSTA (MEDIDO VS. FLX)', Inches(0.6), Inches(0.4), Inches(12), Inches(0.5), 16, ACCENT, bold=True)
    text(
        s2,
        '9,85 s e 80,4 MiB (CLI) / 186 MiB (Streamlit)',
        Inches(0.6), Inches(1.0), Inches(12), Inches(0.8), 34, FG, bold=True,
    )
    card(
        s2,
        'Medido (3 execuções · exp.md)',
        [
            '• Tempo total: 10,88 s · 9,27 s · 9,39 s (média 9,85 s)',
            '  – Preparo + LGPD local: 1,28 s | Modelo: 7,59 s',
            '• Pico de RAM: 80,4 MiB (CLI) · 186,0 MiB (Streamlit)',
            '• Tokens: 10.171 entrada → 2.489 saída (~325 tok/s)',
        ],
        Inches(0.6), Inches(2.2), Inches(5.9), Inches(4.1),
        fill=CARD_OK, border=ACCENT,
    )
    card(
        s2,
        'Estimado antes de rodar (flx.md)',
        [
            '• Tempo total estimado: ~13,0 s (2,5 s local + 10,0 s LLM)',
            '• Pico de RAM estimado: ~300,0 MiB',
            '• Tokens estimados: ~5.000 entrada → ~1.500 saída',
            '• Diferença: prefill rápido na API + pesos fora da RAM local',
        ],
        Inches(6.8), Inches(2.2), Inches(5.9), Inches(4.1),
    )
    text(
        s2,
        'Máquina: Windows 11 · Intel 12 CPUs · 16 GiB RAM · Python 3.14.3 · gemini-3.5-flash-lite · versão tag sem2',
        Inches(0.6), Inches(6.65), Inches(12), Inches(0.4), 13, MUTED,
    )

    # ---------------------------------------------- Slide 3: A falha
    s3 = new_slide(prs)
    text(s3, '3 · ONDE ERRA (A FALHA MOSTRADA)', Inches(0.6), Inches(0.4), Inches(12), Inches(0.5), 16, WARN, bold=True)
    text(
        s3,
        'Arquivos estáticos (currículo ou Obsidian desatualizado) ≠ domínio real',
        Inches(0.6), Inches(1.0), Inches(12), Inches(0.8), 28, FG, bold=True,
    )
    card(
        s3,
        '❌ Como saiu (confiando cegamente nos arquivos)',
        [
            '• Pelo currículo de vaga: infla Back-end para 4/5 ("sem conflito")',
            '• Pela nota antiga do Obsidian (Cap. 1): rebaixa meu DDD para 1/5',
            '  (mesmo eu aplicando DDD na prática e só não atualizando a nota)',
            '• Pelos commits (+384 linhas Jev): assume autoria sem checar o agente',
        ],
        Inches(0.6), Inches(2.2), Inches(5.9), Inches(4.1),
        fill=CARD_ERR, border=WARN, title_color=WARN,
    )
    card(
        s3,
        '✅ O certo (Autoavaliação + Sessões no Harness)',
        [
            '• Nunca tratar currículo ou nota parada como verdade absoluta',
            '• Partir da autoavaliação declarada pela usuária (sliders 0 a 5)',
            '• Cruzar com a memória viva do harness (Claude Code / Codex)',
            '• Medir domínio real pela Propriedade Intelectual (P1–P4) na tarefa',
        ],
        Inches(6.8), Inches(2.2), Inches(5.9), Inches(4.1),
        fill=CARD_OK, border=ACCENT, title_color=ACCENT,
    )
    text(
        s3,
        'Quem sofre: a desenvolvedora (subestimada em DDD por nota antiga ou superestimada por currículo) · Medida do sem3',
        Inches(0.6), Inches(6.65), Inches(12), Inches(0.4), 14, MUTED,
    )

    # ---------------------------------------------- Slide 4: O que mudou
    s4 = new_slide(prs)
    text(s4, '4 · O QUE MUDOU DESDE O SEM1', Inches(0.6), Inches(0.4), Inches(12), Inches(0.5), 16, ACCENT, bold=True)
    text(
        s4,
        'A triagem entrou no 1º uso; o nível declarado ficou',
        Inches(0.6), Inches(1.0), Inches(12), Inches(0.8), 32, FG, bold=True,
    )
    card(
        s4,
        'No sem1 (04/11)',
        [
            '• Comandos @... eram só conceito',
            '• Currículo, GitHub e histórico ficavam FORA do 1º uso',
            '  ("para não comprometer fluidez e adesão")',
            '• Nível atual e objetivo declarados pela pessoa',
        ],
        Inches(0.6), Inches(2.2), Inches(5.9), Inches(4.1),
    )
    card(
        s4,
        'Agora no sem2 (11/11)',
        [
            '• Mudou: /LuzIA:triage puxa currículo, GitHub, commits',
            '  e histórico compartilhado entre IAs logo na largada',
            '• Mudou: premissa explícita de uso educado da IA + LGPD',
            '• Mantido de propósito: nível (Jr 3) e alvo (Pleno) declarados',
            '  (evita a falha de confiar só no currículo ou no git log)',
        ],
        Inches(6.8), Inches(2.2), Inches(5.9), Inches(4.1),
        fill=CARD_OK, border=ACCENT,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f'{len(prs.slides)} slides gerados em {OUT}')


if __name__ == '__main__':
    build()
