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
Verification de mise a jour via l'API des Releases GitHub. Consultation
seulement -- ne telecharge et n'installe jamais rien automatiquement, se
contente de signaler qu'une version plus recente existe si c'est le cas.

Concu pour echouer silencieusement dans tous les cas non-critiques (pas de
connexion internet, depot pas encore configure, reponse GitHub inattendue...) :
une verification de mise a jour ratee ne doit jamais empecher l'application de
demarrer normalement.
"""
import json
import urllib.request
import urllib.error

from core.version import APP_VERSION, GITHUB_REPO

_TIMEOUT_SECONDS = 4


def _parse_version(version_str: str) -> tuple:
    """Convertit 'v1.2.3' ou '1.2.3' en (1, 2, 3) pour comparaison numerique.
    Retombe sur (0,) si le format est inattendu, plutot que de planter."""
    cleaned = version_str.strip().lstrip("vV")
    parts = []
    for piece in cleaned.split("."):
        digits = "".join(c for c in piece if c.isdigit())
        if digits == "":
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def check_for_update() -> dict | None:
    """Retourne {'version': str, 'url': str} si une version plus recente est
    disponible sur GitHub, sinon None -- que ce soit parce qu'on est deja a
    jour, que le depot n'est pas configure, ou que la verification a echoue
    pour n'importe quelle raison (reseau, format de reponse...)."""
    if not GITHUB_REPO.strip():
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        request = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "empyrion-scenario-editor-update-check"})
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None

    tag_name = data.get("tag_name")
    html_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")
    if not tag_name:
        return None

    try:
        latest = _parse_version(tag_name)
        current = _parse_version(APP_VERSION)
    except Exception:
        return None

    if latest > current:
        return {"version": tag_name, "url": html_url}
    return None
