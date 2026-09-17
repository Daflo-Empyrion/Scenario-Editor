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

"""
Session de revision de traduction interrompue (demande 17/09/2026) :
controler les ~5000 lignes traduites d'un gros Localization.csv se fait
en plusieurs fois, or fermer la revue perdait tout le travail de relecture.

Principe : la revue CSV applique les lignes cochees AU FIL DE L'EAU ; quand
l'utilisateur quitte, les lignes restantes (non validees) sont persistees
ici, identifiees par la cle de la ligne (colonne 0) et les colonnes
source/destination -- jamais par index de ligne, l'ordre pouvant changer
entre deux ouvertures du fichier. A la prochaine ouverture du meme CSV,
la reprise reconstruit les destinations et rouvre la revue a l'identique.

Un fichier de session par CSV source ET par type de revue :
review_sessions/<nom>__<hash8>.json (traduction) et
review_sessions/<nom>__<hash8>_spellcheck.json (orthographe/grammaire) --
le hash du chemin absolu evite que deux fichiers de meme nom dans des
scenarios differents se marchent dessus. Ecrase a chaque sauvegarde,
supprime quand la revision est terminee ou abandonnee.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

SESSIONS_DIR = Path.home() / ".empyrion_editor" / "review_sessions"


def _session_file(file_path: Path, kind: str = "translation") -> Path:
    p = str(Path(file_path).resolve())
    digest = hashlib.sha256(p.encode("utf-8", "replace")).hexdigest()[:8]
    slug = "".join(ch if ch.isalnum() else "_" for ch in Path(p).stem)[:40]
    suffix = "" if kind == "translation" else f"_{kind}"
    return SESSIONS_DIR / f"{slug}__{digest}{suffix}.json"


def load_session(file_path: Path, kind: str = "translation") -> Optional[dict]:
    """Session du fichier, ou None (absente, corrompue ou sans ligne)."""
    path = _session_file(file_path, kind)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != 1:
        return None
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return None
    return data


def save_session(file_path: Path, data: dict, kind: str = "translation") -> None:
    """Ecrit (ecrase) la session du fichier. `data` contient au minimum
    'items' ; version et horodatage ajoutes ici."""
    from core.fsutil import atomic_write_text
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "kind": kind, "file": str(file_path),
               "saved_at": datetime.now().isoformat(timespec="seconds"),
               **data}
    atomic_write_text(_session_file(file_path, kind),
                      json.dumps(payload, ensure_ascii=False, indent=1))


def delete_session(file_path: Path, kind: str = "translation") -> None:
    try:
        _session_file(file_path, kind).unlink()
    except OSError:
        pass
