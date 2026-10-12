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
"""Configuration du module admin serveur, persistee dans settings.json
(cle "ewa" via core.settings.get_ewa/set_ewa). Mot de passe : memoire
OPTIONNELLE (case « Se souvenir ») -- sinon il n'est jamais ecrit sur
disque et doit etre ressaisi a chaque session."""

DEFAULTS = {
    "url": "",                  # ex : https://51.254.47.151:5001
    "username": "",
    "password": "",
    "remember_password": False,
    "verify_ssl": False,        # certificat auto-signé EWA : ignoré par défaut
    "timeout": 20,              # secondes
    "sftp": {
        "host": "",
        "port": 22,
        "username": "",
        "password": "",
        "remote_scenario": "",  # chemin distant du scenario (cote serveur)
    },
    "telnet": {
        "host": "",
        "port": 30004,
        "password": "",
    },
    "deploy_local_dir": "",     # dernier dossier local deploye ( DeployTab )
}


def load() -> dict:
    """Configuration complete, champs manquants remplis par DEFAULTS
    (fusion un niveau : sftp/telnet partiellement absents supportes)."""
    from core import settings
    data = dict(DEFAULTS)
    stored = settings.get_ewa()
    for key, value in (stored or {}).items():
        if key in ("sftp", "telnet") and isinstance(value, dict):
            merged = dict(DEFAULTS[key])
            merged.update({k: v for k, v in value.items() if k in DEFAULTS[key]})
            data[key] = merged
        elif key in DEFAULTS:
            data[key] = value
    if not data.get("remember_password"):
        # jamais de mot de passe persiste sans consentement explicite
        # (API EWA, SFTP et telnet : les trois ouvrent le dédié)
        data["password"] = ""
        data["sftp"]["password"] = ""
        data["telnet"]["password"] = ""
    return data


def save(data: dict) -> None:
    """Ecrit la configuration ; AUCUN mot de passe n'est stocke si la
    case « Se souvenir » n'est pas cochee (sinon vide sur disque)."""
    from core import settings
    stored = dict(data)
    if not stored.get("remember_password"):
        stored["password"] = ""
        stored.setdefault("sftp", {})["password"] = ""
        stored.setdefault("telnet", {})["password"] = ""
    settings.set_ewa(stored)


def ewa_ready(data: dict) -> bool:
    """L'URL EWA est-elle renseignable (connexion possible) ?"""
    return bool((data.get("url") or "").strip())
