# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Bibliotheque de blocs reutilisables (demande du 10/09/2026) : exporter un
bloc ECF (POI, item, marchand...) en snippet reimportable dans n'importe
quel scENARIO. Stockage local simple : un fichier par snippet dans
~/.empyrion_editor/block_library/, texte brut du bloc (round-trip sur le
parseur ECF a l'import). Aucune donnee de scenario n'est envoyee nulle
part : tout reste sur le poste."""

import re
import time
from pathlib import Path
from typing import List

from core.fsutil import atomic_write_text

LIB_DIR = Path.home() / ".empyrion_editor" / "block_library"
EXTENSION = ".ecfsnip"


def _sanitize_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (name or "").strip())
    return cleaned[:80] or "sans_nom"


def _snippet_path(name: str) -> Path:
    return LIB_DIR / (_sanitize_name(name) + EXTENSION)


def save_snippet(name: str, raw_text: str) -> Path:
    """Enregistre le texte brut d'un bloc sous le nom donne. Un suffixe
    horloge evite d'ecraser silencieusement un snippet du meme nom : deux
    exports 'POI Cargo' coexistent (POI Cargo, POI Cargo-143022)."""
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    path = _snippet_path(name)
    if path.exists():
        path = LIB_DIR / f"{_sanitize_name(name)}-{time.strftime('%H%M%S')}{EXTENSION}"
    atomic_write_text(path, raw_text if raw_text.endswith("\n") else raw_text + "\n")
    return path


def list_snippets() -> List[dict]:
    """Snippets disponibles, plus recents d'abord."""
    if not LIB_DIR.exists():
        return []
    out = []
    for p in sorted(LIB_DIR.glob("*" + EXTENSION)):
        try:
            st = p.stat()
        except OSError:
            continue
        out.append({"name": p.stem, "path": p, "size": st.st_size,
                    "mtime": st.st_mtime})
    out.sort(key=lambda s: s["mtime"], reverse=True)
    return out


def load_snippet(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def delete_snippet(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
