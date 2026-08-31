import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "article"
OUTPUT_DIR = ROOT / "outputs" / "article"
PAPER = "samplepaper.tex"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ARTICLE_DIR, check=True)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if shutil.which("latexmk"):
        run([
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-outdir={OUTPUT_DIR}",
            PAPER,
        ])
    elif shutil.which("pdflatex"):
        command = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={OUTPUT_DIR}",
            PAPER,
        ]
        run(command)
        run(command)
    else:
        print("LaTeX nao encontrado no PATH.")
        print("Instale MiKTeX ou TeX Live e execute novamente.")
        return 1

    print(f"PDF gerado em: {OUTPUT_DIR / 'samplepaper.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
