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
Journal PERSISTANT des modifications PDA, par scenario -- donne au retour en
session un RAPPEL de ce qui a ete touche dans PDA.yaml/PDA.csv la fois
derniere (demande utilisateur du 31/08/2026).

Fichier local ~/.empyrion_editor/pda_history.json (meme dossier que
settings.json, JAMAIS versionne) : {chemin_scenario: [{"ts", "label"}]}.
Ecriture atomique via core.fsutil.atomic_write_text, comme settings.json.
Les libelles sont deja localises par l'appelant (l'editeur) au moment de la
journalisation -- ce fichier est un journal technique, pas une ressource i18n."""
import json
from pathlib import Path

from core.fsutil import atomic_write_text

CONFIG_DIR = Path.home() / ".empyrion_editor"
HISTORY_FILE = CONFIG_DIR / "pda_history.json"
MAX_PER_PROJECT = 200      # borne anti-glouton (petits libelles, aucun risque)
DEFAULT_READ = 8


def append_history(scenario_key: str, labels) -> None:
    """Ajoute des libelles horodate au journal du scenario (le plus ancien
    d'abord). Sans libelle : no-op. Toute erreur disque est silencieuse -- le
    journal ne doit JAMAIS faire echouer une fermeture d'editeur."""
    labels = [l for l in (labels or []) if l]
    if not labels or not scenario_key:
        return
    data = _read_all()
    project = data.setdefault(str(scenario_key), [])
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    for label in labels:
        project.append({"ts": now, "label": label})
    del project[:-MAX_PER_PROJECT]
    _write_all(data)


def read_history(scenario_key: str, limit: int = DEFAULT_READ):
    """Les `limit` dernieres entrees du scenario (les PLUS RECENTES d'abord),
    [] si aucun journal ou erreur disque."""
    project = _read_all().get(str(scenario_key), [])
    return list(reversed(project[-limit:])) if project else []


def _read_all() -> dict:
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_all(data: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_text(HISTORY_FILE, json.dumps(data, ensure_ascii=False, indent=1))
    except OSError:
        pass
