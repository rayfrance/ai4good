from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "AGENTS.md",
    "CONTEXT.md",
    "README.md",
    "GEMINI.md",
    "workspace.code-workspace",
    "code/CONTEXT.md",
    "papers/CONTEXT.md",
    "article/CONTEXT.md",
    "article/PROJECT.md",
    "article/ROADMAP.md",
    "article/samplepaper.tex",
    "core/CONTEXT.md",
    "core/flows/research/literature.md",
    "core/flows/research/draft.md",
    "core/templates/paper-section.tex",
    "tools/CONTEXT.md",
    "tools/compile_article.py",
]


def main() -> int:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    nested_git = ROOT / "article" / ".git"

    if missing:
        print("Workspace incompleto. Arquivos faltando:")
        for path in missing:
            print(f"- {path}")
        return 1

    if nested_git.exists():
        print("Workspace invalido: article/ contem outro repositorio Git.")
        return 1

    print("Workspace OK.")
    print("Codigo: code/")
    print("Referencias: papers/")
    print("Artigo: article/samplepaper.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
