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
    text(s0, '✨ Luzia', Inches(0.8), Inches(2.0), Inches(11.7), Inches(1.4), 72, ACCENT, bold=True)
    text(
        s0,
        'sua líder técnica dentro do agente · demonstração ao vivo',
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
        'Um dia de trabalho no Claude Code, com a Luzia junto',
        Inches(0.6), Inches(1.0), Inches(12), Inches(0.8), 32, FG, bold=True,
    )
    card(
        s1,
        '👀 Passiva: observa a sessão (hook)',
        [
            '• A cada edição ou commit, compara com as lacunas do plano',
            '• Ativa: avisa em 1 linha no chat · Passiva: só registra',
            '• Local, sem código salvo, sem nome de arquivo (LGPD)',
            '• Triagem já feita: currículo, GitHub, histórico entre IAs, commits',
        ],
        Inches(0.6), Inches(2.2), Inches(5.8), Inches(4.3),
    )
    card(
        s1,
        '💬 Ativa: quando eu chamo',
        [
            '• /luzia:feedback-skills-opportunities',
            '• /luzia:feedback-progress',
            '• /luzia:next-level',
            '• /luzia:career-map  →  painel visual',
        ],
        Inches(6.9), Inches(2.2), Inches(5.8), Inches(4.3),
    )

    # ---------------------------------------------- Slide 2: Quanto custa
    s2 = new_slide(prs)
    text(s2, '2 · QUANTO CUSTA (MEDIDO VS. FLX)', Inches(0.6), Inches(0.4), Inches(12), Inches(0.5), 16, ACCENT, bold=True)
    text(
        s2,
        'Triagem: 13,1 s e 76,7 MiB · dia a dia: 7–8 s',
        Inches(0.6), Inches(1.0), Inches(12), Inches(0.8), 34, FG, bold=True,
    )
    card(
        s2,
        'Medido (3 triagens · versão 9727f6e · exp.md)',
        [
            '• Tempo total: 13,47 s · 13,01 s · 12,95 s (média 13,14 s)',
            '  – local + LGPD 2,36 s · modelo 7,44 s · SDK/rede ~3,3 s',
            '• Pico de RAM: 76,6 – 76,8 MiB',
            '• Tokens: 10.277 entrada → ~2.720 saída',
            '• 1 tentativa falhou: timeout da API (504)',
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
            '• Tempo bateu; RAM ficou 4× menor: os pesos ficam na API',
        ],
        Inches(6.8), Inches(2.2), Inches(5.9), Inches(4.1),
    )
    text(
        s2,
        'Máquina: Windows 11 · Intel 12 CPUs · 16 GiB RAM · Python 3.14.3 · gemini-3.5-flash-lite · versão 9727f6e',
        Inches(0.6), Inches(6.65), Inches(12), Inches(0.4), 13, MUTED,
    )

    # ---------------------------------------------- Slide 3: A falha
    s3 = new_slide(prs)
    text(s3, '3 · ONDE ERRA (A FALHA MOSTRADA)', Inches(0.6), Inches(0.4), Inches(12), Inches(0.5), 16, WARN, bold=True)
    text(
        s3,
        'Mesmo com a regra no prompt, a Luzia confiou na nota parada',
        Inches(0.6), Inches(1.0), Inches(12), Inches(0.8), 28, FG, bold=True,
    )
    card(
        s3,
        '❌ Como saiu (execuções medidas, versão 9727f6e)',
        [
            '• Com histórico: DDD sugerido 1/5 por "notas do capítulo 1"',
            '• Sem histórico: "sem conflito" entre currículo e commits',
            '  e programação agêntica inflada para 4/5',
        ],
        Inches(0.6), Inches(2.2), Inches(5.9), Inches(4.1),
        fill=CARD_ERR, border=WARN, title_color=WARN,
    )
    card(
        s3,
        '✅ O certo',
        [
            '• Nota parada só mapeia o tópico; não define nível',
            '• O nível parte da minha autoavaliação (painel)',
            '• A memória viva (sessões, commits) ajusta, com evidência',
        ],
        Inches(6.8), Inches(2.2), Inches(5.9), Inches(4.1),
        fill=CARD_OK, border=ACCENT, title_color=ACCENT,
    )
    text(
        s3,
        'Quem sofre: a desenvolvedora, com um mapa de carreira errado · regra só no prompt não basta → medida do sem3',
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
            '• Mudou: a triagem (currículo, GitHub, commits, histórico',
            '  entre IAs) virou a largada, feita uma vez',
            '• Mudou: a Luzia observa a sessão de verdade (hook)',
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
