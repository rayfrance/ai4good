"""
Gera os slides do seminário preliminares (sem1) a partir de va2/sem1.md.

Cada seção "## slide N · título · tempo" vira um slide:
- "aparece" -> texto grande do slide (links markdown viram rodapé com a fonte);
- imagem escolhida por palavra-chave no "aparece" (telas em outputs/sem1/);
- "eu falo" -> notas do apresentador.

Uso: python tools/build_sem1_pptx.py
Saída: outputs/sem1_preliminares.pptx (importar no Google Slides).
"""

import re
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "va2" / "sem1.md"
IMG_DIR = ROOT / "outputs" / "sem1"
OUT = ROOT / "outputs" / "sem1_preliminares.pptx"

# palavra-chave no "aparece" -> captura de tela
IMAGES = {
    "vibe check": "vibecheck.png",
    "pear": ["pear_landing.png", "pear_init.png"],
    "junior": "junior_senior.png",
    "code with me": "code_with_me.png",
    "conceito": "conceito.png",
}

BG = RGBColor(0x10, 0x12, 0x1A)
FG = RGBColor(0xF4, 0xF4, 0xF5)
MUTED = RGBColor(0xA1, 0xA1, 0xAA)
ACCENT = RGBColor(0x4A, 0xDE, 0x80)
ACCENT_DARK = RGBColor(0x16, 0x65, 0x34)
CARD = RGBColor(0x1F, 0x23, 0x30)

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_slides(text: str):
    slides = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        if not head.startswith("slide"):
            continue
        parts = [p.strip() for p in head.split("·")]
        title = parts[1] if len(parts) > 1 else head
        title = re.sub(r"\(opcional\)", "", title).strip()
        aparece = re.search(r"\*\*aparece:\*\*\s*(.+)", body)
        falo = re.search(r"\*\*eu falo:\*\*\s*(.+)", body)
        aparece = aparece.group(1).strip() if aparece else ""
        if not aparece or aparece.startswith("[preencha"):
            continue
        slides.append({"title": title, "aparece": aparece,
                       "falo": falo.group(1).strip() if falo else ""})
    return slides


def add_text(slide, text, left, top, width, height, size, color, bold=False):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    return box


def box(slide, text, left, top, w, h, fill, size=14, color=FG, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    shp = slide.shapes.add_shape(shape, left, top, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = ACCENT
    tf = shp.text_frame
    tf.word_wrap = True
    tf.text = text
    for para in tf.paragraphs:
        para.alignment = PP_ALIGN.CENTER
        para.font.size = Pt(size)
        para.font.color.rgb = color
        para.font.bold = True
    return shp


def arrow(slide, x1, y1, x2, y2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = ACCENT
    c.line.width = Pt(2.5)
    c.line._get_or_add_ln().append(c.line._get_or_add_ln().makeelement(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"}))


def draw_flow(slide):
    """fluxo do Leadroid (conceito): tarefa -> observa -> referencial -> painel -> próxima tarefa"""
    steps = ["você diz onde está\ne aonde quer chegar", "você + agente\nfazem a tarefa",
             "Leadroid acompanha\n(repositórios autorizados)", "painel: progresso, skills\ne próximo passo"]
    w, h, gap, top, left = Inches(2.6), Inches(1.05), Inches(0.45), Inches(5.35), Inches(0.6)
    for i, s in enumerate(steps):
        x = left + i * (w + gap)
        box(slide, s, x, top, w, h, CARD, 14)
        if i:
            arrow(slide, x - gap, top + h // 2, x, top + h // 2)
    add_text(slide, "↻ a cada nova tarefa o painel se atualiza  ·  conceito, ainda não implementado",
             left, top + h + Inches(0.05), Inches(12), Inches(0.4), 12, MUTED)


def draw_ladder(slide):
    """escada de carreira dinâmica (conceito, dados fictícios)"""
    levels = [("júnior", Inches(5.6)), ("pleno", Inches(4.5)), ("sênior", Inches(3.4))]
    left, w, h = Inches(9.0), Inches(1.35), Inches(0.9)
    for i, (name, top) in enumerate(levels):
        x = left + i * Inches(1.4)
        box(slide, name, x, top, w, h, ACCENT_DARK if i == 1 else CARD, 16)
    box(slide, "você está aqui · objetivo: sênior\n3 de 5 skills do plano", left + Inches(0.6), Inches(2.0),
        Inches(2.8), Inches(1.0), BG, 12, ACCENT, MSO_SHAPE.ROUNDED_RECTANGLE)
    arrow(slide, left + Inches(2.1), Inches(3.0), left + Inches(2.1), Inches(4.5))
    add_text(slide, "conceito, dados fictícios", left, Inches(6.55), Inches(4), Inches(0.3), 11, MUTED)


def build():
    slides = parse_slides(SRC.read_text(encoding="utf-8"))
    if not slides:
        raise SystemExit("nenhum slide preenchido em va2/sem1.md")
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    for s in slides:
        slide = prs.slides.add_slide(blank)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = BG
        links = LINK_RE.findall(s["aparece"])
        parts = [x.strip() for x in LINK_RE.sub("", s["aparece"]).split("|")]
        parts = [x.rstrip(" ·") for x in parts if x.strip(" ·")]
        headline, bullets = parts[0], parts[1:]
        add_text(slide, s["title"].upper(), Inches(0.6), Inches(0.35),
                 Inches(12), Inches(0.5), 16, ACCENT, bold=True)
        img = next((f for k, f in IMAGES.items() if k in s["aparece"].lower()), None)
        imgs = [x for x in ([img] if isinstance(img, str) else (img or []))
                if (IMG_DIR / x).exists()]
        title_l = s["title"].lower()
        ladder = "só a minha" in title_l
        text_w = Inches(6.2) if imgs else (Inches(8.0) if ladder else Inches(12.1))
        add_text(slide, headline, Inches(0.6), Inches(1.0), text_w,
                 Inches(1.4), 30 if not imgs else 26, FG, bold=True)
        if bullets:
            box = slide.shapes.add_textbox(Inches(0.6), Inches(2.6), text_w, Inches(4))
            tf = box.text_frame
            tf.word_wrap = True
            for i, b in enumerate(bullets):
                para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                para.text = "• " + b
                para.font.size = Pt(20 if (imgs or ladder) else 22)
                para.font.color.rgb = FG
                para.space_after = Pt(12)
        if len(imgs) == 1:
            slide.shapes.add_picture(str(IMG_DIR / imgs[0]), Inches(7.1), Inches(1.6),
                                     width=Inches(5.8))
        elif imgs:
            top = Inches(1.0)
            for x in imgs:
                pic = slide.shapes.add_picture(str(IMG_DIR / x), Inches(7.3), top,
                                               height=Inches(2.85))
                top += pic.height + Inches(0.15)
        if links:
            add_text(slide, "fonte: " + " · ".join(u for _, u in links),
                     Inches(0.6), Inches(6.9), Inches(12.1), Inches(0.4), 11, MUTED)
        if title_l == "a ideia":
            draw_flow(slide)
        if ladder:
            draw_ladder(slide)
        slide.notes_slide.notes_text_frame.text = s["falo"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"{len(slides)} slides -> {OUT}")


if __name__ == "__main__":
    build()
