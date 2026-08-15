from pathlib import Path

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "node_modules",
}

EXTENSIONS = {".py", ".txt", ".md", ".toml", ".cfg", ".ini", ".yml", ".yaml"}

output_file = Path("bundle.md")

with output_file.open("w", encoding="utf-8") as out:
    out.write("# Bundle du projet\n\n")

    out.write("## Arborescence\n\n")
    out.write("```text\n")

    for path in sorted(Path(".").rglob("*")):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        if path.is_file():
            out.write(f"{path}\n")

    out.write("```\n\n")

    out.write("## Fichiers\n\n")

    for path in sorted(Path(".").rglob("*")):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        if not path.is_file():
            continue

        if path.suffix not in EXTENSIONS:
            continue

        out.write(f"### {path}\n\n")

        ext = path.suffix.replace(".", "")

        out.write(f"```{ext}\n")

        try:
            content = path.read_text(encoding="utf-8")
            out.write(content)
        except UnicodeDecodeError:
            out.write("# Impossible de lire ce fichier automatiquement.")

        out.write("\n```\n\n")

print(f"Fichier généré : {output_file.resolve()}")