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
"""Client REST de l'API EmpyrionWebAccess (EWA) -- JWT Bearer 7 jours,
controleurs SANS prefixe (/Systeminfo/..., /Structure/...) + endpoints
OData (odata/Players, odata/Chats, odata/Factions).

PIEGE de casse : selon le controleur (System.Text.Json camelCase vs OData
vs Newtonsoft), les proprietes arrivent en PascalCase OU camelCase -- toute
lecture passe donc par pick() qui accepte les deux. Les corps POST partent
en PascalCase (noms exacts des DTO C#, liaison insensible a la casse).

1re connexion : si la base Users d'EWA est VIDE, authenticate() CREE le
compte (serveur = admin) -- c'est le bootstrap officiel d'EWA.
"""
import logging

import requests
import urllib3

logger = logging.getLogger(__name__)


class EwaError(Exception):
    """Erreur API EWA (statut + message serveur)."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class EwaAuthError(EwaError):
    """Identifiants refuses (ou serveur injoignable a l'auth)."""


def pick(data, *names, default=None):
    """Premiere cle presente dans data parmi names, casse indifferente
    (PlayerName == playerName == playername)."""
    if not isinstance(data, dict):
        return default
    lowered = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return default


def normalize_url(url: str) -> str:
    """https://IP:5001/ -> https://IP:5001 ; http force si l'utilisateur
    colle l'URL sans scheme."""
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "https://" + url
    return url


class EwaClient:
    """Client HTTP de l'API EWA. Toutes les methodes reseau sont BLOQUANTES :
    les appeler hors du thread GUI (gui.busy.run_long / threads EWA)."""

    def __init__(self, base_url: str, verify_ssl: bool = False,
                 timeout: int = 20):
        self.base_url = normalize_url(base_url)
        self.verify_ssl = verify_ssl
        self.timeout = int(timeout or 20)
        self.token = ""
        self.user: dict = {}
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "EmpyrionScenarioEditor"
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ------------------------------------------------------------ requetes

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        try:
            response = self._session.request(
                method, self._url(path), timeout=self.timeout,
                verify=self.verify_ssl, headers=headers, **kwargs)
        except requests.exceptions.SSLError as e:
            raise EwaError(
                f"CERTIFICAT : {e} (case « certificat auto-signé » ?)") from e
        except requests.exceptions.RequestException as e:
            raise EwaError(f"RESEAU : {e}") from e
        if response.status_code in (401, 403):
            message = self._error_message(response)
            raise EwaAuthError(f"ACCES REFUSE ({response.status_code}) : "
                               f"{message}", response.status_code)
        if response.status_code >= 400:
            raise EwaError(
                f"HTTP {response.status_code} sur {path} : "
                f"{self._error_message(response)}", response.status_code)
        return response

    @staticmethod
    def _error_message(response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return (response.text or "").strip()[:200] or "aucun detail"
        if isinstance(payload, dict):
            message = pick(payload, "message", "msg", "error", "title",
                           default="")
            if message:
                return str(message)[:200]
        return (response.text or "").strip()[:200] or "aucun detail"

    def _get_json(self, path: str):
        response = self._request("GET", path)
        if not response.content:
            return None
        return response.json()

    def _post_json(self, path: str, body=None):
        response = self._request("POST", path, json=body)
        if not response.content:
            return None
        return response.json()

    # ------------------------------------------------------- authentification

    def authenticate(self, username: str, password: str) -> dict:
        """POST Users/authenticate -> {Id, Username, Role, Token}. Si la
        base Users d'EWA est vide, le serveur CREE ce premier compte
        (bootstrap admin officiel d'EWA)."""
        if not self.base_url:
            raise EwaAuthError("URL du serveur EWA manquante.")
        if not username or not password:
            raise EwaAuthError("Identifiant et mot de passe requis.")
        self.token = ""
        try:
            payload = self._post_json("Users/authenticate",
                                      {"Username": username,
                                       "Password": password})
        except EwaError as e:
            # EWA repond 400 « Username or password is incorrect »
            raise EwaAuthError(str(e), e.status) from e
        token = pick(payload, "Token", default="") if payload else ""
        if not token:
            raise EwaAuthError("Authentification refusée par le serveur.")
        self.token = token
        self.user = payload or {}
        return self.user

    # ---------------------------------------------------------------- OData

    def _odata(self, entity: str, query: str = "") -> list:
        path = f"odata/{entity}"
        if query:
            path += f"?{query}"
        payload = self._get_json(path)
        if isinstance(payload, dict):
            value = pick(payload, "value", default=[])
            return value if isinstance(value, list) else []
        return payload if isinstance(payload, list) else []

    # ------------------------------------------------------------- systeminfo

    def get_systeminfo(self) -> dict:
        return self._get_json("Systeminfo/CurrentSysteminfo") or {}

    def get_system_config(self) -> dict:
        return self._get_json("Systeminfo/SystemConfig") or {}

    def set_system_config(self, config: dict) -> None:
        self._post_json("Systeminfo/SystemConfig", config)

    def egs_start(self) -> None:
        self._get_json("Systeminfo/EGSStart")

    def egs_stop(self, wait_minutes: int = 5) -> None:
        self._get_json(f"Systeminfo/EGSStop/{int(wait_minutes)}")

    def egs_restart(self, wait_minutes: int = 5) -> None:
        self._get_json(f"Systeminfo/EGSRestart/{int(wait_minutes)}")

    # ------------------------------------------------------------- joueurs

    def get_players(self, top: int = 1000) -> list:
        return self._odata("Players", f"$top={int(top)}")

    def get_online_players(self) -> list:
        """Joueurs en ligne : filtre OData cote serveur quand il accepte
        le filtre booléen, sinon filtrage local (repli robuste)."""
        try:
            online = self._odata("Players", "$filter=Online eq true&$top=1000")
            if online:
                return online
        except EwaError:
            pass
        return [p for p in self.get_players() if pick(p, "Online") is True]

    def kick_player(self, steam_id: str) -> None:
        self._get_json(f"Gameplay/KickPlayer/{steam_id}")

    def ban_player(self, steam_id: str, duration: str = "1d") -> None:
        """duration : '1h' ou '1d' (le serveur borne selon le role)."""
        self._get_json(f"Gameplay/BanPlayer/{steam_id}/{duration}")

    def unban_player(self, steam_id: str) -> None:
        self._get_json(f"Gameplay/UnBanPlayer/{steam_id}")

    def wipe_player(self, steam_id: str) -> None:
        self._get_json(f"Gameplay/WipePlayer/{steam_id}")

    def set_player_role(self, steam_id: str, role: str) -> None:
        self._get_json(f"Gameplay/SetRoleOfPlayer/{steam_id}/{role}")

    def set_player_credits(self, entity_id: int, credits: int) -> None:
        self._get_json(f"Gameplay/PlayerSetCredits/{int(entity_id)}/{int(credits)}")

    def save_player_note(self, steam_id: str, note: str) -> None:
        self._post_json("Player/SaveNote", {"SteamId": steam_id, "Note": note})

    def change_player_info(self, data: dict) -> None:
        self._post_json("Player/ChangePlayerInfo", data)

    def player_remote_ex(self, client_id: int, command: str) -> None:
        self._post_json("Player/PlayerRemoteEx",
                        {"ClientId": int(client_id), "Command": command})

    def get_elevated_users(self) -> list:
        payload = self._get_json("Player/GetElevatedUsers")
        return payload if isinstance(payload, list) else []

    def get_banned_users(self) -> list:
        payload = self._get_json("Player/GetBannedUsers")
        return payload if isinstance(payload, list) else []

    def add_item_to_player(self, player_entity_id: int, item_id: int,
                           count: int, slot_idx: int = 0) -> None:
        """Backpack/AddItem : depose un item dans le sac du joueur
        (equivalent EWA ; le serveur rafraichit l'inventaire)."""
        self._post_json("Backpack/AddItem", {
            "id": int(player_entity_id),
            "itemStack": {"id": int(item_id), "count": int(count),
                          "slotIdx": int(slot_idx), "ammo": 0, "decay": 0},
        })

    def get_backpacks(self, steam_id: str) -> list:
        payload = self._get_json(f"Backpack/Backpacks/{steam_id}")
        return payload if isinstance(payload, list) else []

    # ---------------------------------------------------------------- chat

    def get_chats(self, top: int = 200) -> list:
        """Historique (OData) : les plus recents d'abord."""
        return self._odata("Chats", f"$top={int(top)}&$orderby=Timestamp desc")

    # ---------------------------------------------------------- structures

    def get_global_structures(self, with_pois: bool = False) -> dict:
        payload = self._get_json(
            f"Structure/GlobalStructureList?WithPOIs={'true' if with_pois else 'false'}")
        if isinstance(payload, dict):
            structures = pick(payload, "globalStructures", "GlobalStructures",
                              default=None)
            if isinstance(structures, dict):
                return structures
        return payload if isinstance(payload, dict) else {}

    def delete_structures(self, entries: list) -> None:
        """entries : [{'id': int, 'playfield': str}, ...]"""
        self._post_json("Structure/DeleteStructures", entries)

    def touch_structures(self, entries: list) -> None:
        self._post_json("Structure/TouchStructures", entries)

    def set_faction_of_structures(self, faction_abbrev: str,
                                  entity_ids: list) -> None:
        self._post_json("Structure/SetFactionOfStuctures",
                        {"FactionAbbrev": faction_abbrev,
                         "EntityIds": [int(i) for i in entity_ids]})

    def warp_structure(self, entity_id: int, playfield: str,
                       pos, rot=(0.0, 0.0, 0.0)) -> None:
        self._post_json(f"Gameplay/WarpTo/{int(entity_id)}", {
            "Playfield": playfield,
            "PosX": float(pos[0]), "PosY": float(pos[1]),
            "PosZ": float(pos[2]),
            "RotX": float(rot[0]), "RotY": float(rot[1]),
            "RotZ": float(rot[2]),
        })

    def get_factions(self, top: int = 1000) -> list:
        return self._odata("Factions", f"$top={int(top)}")

    # ------------------------------------------------- sauvegardes / restore

    def get_backups(self) -> list:
        payload = self._get_json("Backup/GetBackups")
        return payload if isinstance(payload, list) else []

    def backup_read_players(self, backup: str) -> list:
        payload = self._post_json("Backup/ReadPlayers", {"backup": backup})
        return payload if isinstance(payload, list) else []

    def backup_restore_player(self, backup: str, steam_id: str) -> None:
        self._post_json("Backup/RestorePlayer",
                        {"backup": backup, "steamId": steam_id})

    def backup_read_playfields(self, backup: str) -> list:
        payload = self._post_json("Backup/ReadPlayfields", {"backup": backup})
        return payload if isinstance(payload, list) else []

    def backup_restore_playfield(self, backup: str, playfield: str) -> None:
        self._post_json("Backup/RestorePlayfield",
                        {"backup": backup, "playfield": playfield})

    def backup_mark(self, backup: str) -> None:
        self._post_json("Backup/MarkBackup", {"backup": backup})

    def backup_zip(self, backup: str) -> None:
        self._post_json("Backup/ZipBackup", {"backup": backup})

    # ------------------------------------------------------------ timetable

    def get_timetable(self) -> list:
        payload = self._get_json("Timetable/GetTimetable")
        return payload if isinstance(payload, list) else []

    def set_timetable(self, actions: list) -> None:
        self._post_json("Timetable/SetTimetable", actions)

    def run_timetable_sub(self, sub_action: dict) -> None:
        self._post_json("Timetable/RunThisSubAction", sub_action)

    def run_timetable(self, sub_actions: list) -> None:
        self._post_json("Timetable/RunThis", {"subAction": sub_actions})

    # ------------------------------------------------- playfields / secteurs

    def get_playfields(self) -> list:
        payload = self._get_json("Playfield/Playfields")
        return payload if isinstance(payload, list) else []

    def get_sectors(self) -> list:
        payload = self._get_json("Sectors/Sectors")
        return payload if isinstance(payload, list) else []

    def get_playfield_map(self, playfield_name: str) -> bytes:
        response = self._request("GET",
                                 f"Playfield/GetPlayfieldMap/{playfield_name}")
        return response.content

    # ------------------------------------------------------- utilisateurs EWA

    def get_users(self) -> list:
        payload = self._get_json("Users")
        return payload if isinstance(payload, list) else []

    def register_user(self, username: str, password: str, role: int = 6) -> None:
        """Role : 6 = ServerAdmin (1er compte deja admin via bootstrap)."""
        self._post_json("Users/register", {"Username": username,
                                           "Password": password, "Role": role})

    def update_user(self, user_id: int, username: str,
                    password: str = None) -> None:
        body = {"Id": int(user_id), "Username": username}
        if password:
            body["Password"] = password
        self._post_json("Users/update", body)

    def delete_user(self, user_id: int) -> None:
        self._request("DELETE", f"Users/{int(user_id)}")

    # ------------------------------------------------------- diagnostic EWA

    def mod_loader_installed(self) -> bool:
        payload = self._get_json("Mod/ModLoaderInstalled")
        text = str(payload or "").strip().lower()
        return text not in ("", "false", "0")

    def diagnose(self) -> dict:
        """Diagnostic de connexion pour le guide d'installation : joignable,
        JWT OK, mod loader visible, systeminfo lisible."""
        result = {"reachable": False, "auth": False, "mod_loader": None,
                  "server_name": "", "error": ""}
        try:
            info = self.get_systeminfo()
            result["reachable"] = True
            result["server_name"] = str(pick(info, "serverName", default="") or "")
            result["mod_loader"] = self.mod_loader_installed()
        except EwaAuthError:
            result["reachable"] = True
        except EwaError as e:
            result["error"] = str(e)
        result["auth"] = bool(self.token)
        return result
