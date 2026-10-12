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
"""Deploiement du scenario vers le serveur dedie par SFTP -- meme
semantique que la synchro production miroir (core/production_sync.py,
v1.15.0) mais en RESEAU :

- comparaison locale (working) vs distante (dedié) par taille+mtime ;
- NE JAMAIS uploader *.yaml.bin (caches compiles du jeu, il les regenere)
  ni *.bak (sauvegardes internes de l'editeur) ;
- le .bin d'un yaml UPLOADE est INVALIDE (supprime : le mtime du yaml
  change, l'ancien cache deviendrait « plus frais » -- vecu 05/10, le jeu
  servait le playfield perime) ; un .bin SANS yaml distant est un orphelin
  (purge) ;
- les fichiers presents en DISTANT SEUL sont proposes a la suppression
  (miroir), sauvegardes d'abord par TELECHARGEMENT vers
  ~/.empyrion_editor/backups/sftp_remote/<horodatage>/.

paramiko est une dependance OPTIONNELLE (comme UnityPy) : is_available()
dit quoi faire sinon (message + commande pip), le reste de l'editeur n'y
touche pas.
"""
import logging
import posixpath
import stat as stat_module
from pathlib import Path

logger = logging.getLogger(__name__)

SKIP_SUFFIX = (".yaml.bin", ".bak")


def is_available() -> bool:
    try:
        import paramiko  # noqa: F401
        return True
    except ImportError:
        return False


def availability_message() -> str:
    from core.i18n import t
    return t("ewa.sftp.missing_paramiko")


def known_hosts_file() -> Path:
    """Cles d'hotes EPINGLEES du/de la dedie (jamais le known_hosts
    systeme) : premiere connexion = acceptation + sauvegarde, ensuite
    toute cle DIFFERENTE est rejetee (MITM ou reinstall du serveur)."""
    return Path.home() / ".empyrion_editor" / "sftp_known_hosts"


class SftpError(Exception):
    pass


class SftpSession:
    """Connexion SFTP (paramiko) + primitives dossier/fichier distants."""

    def __init__(self, host: str, port: int, username: str, password: str):
        if not is_available():
            raise SftpError(availability_message())
        if not host or not username:
            raise SftpError("Hôte / identifiant SFTP manquants.")
        import paramiko
        self._client = paramiko.SSHClient()
        keys_path = known_hosts_file()
        keys_path.parent.mkdir(parents=True, exist_ok=True)
        # load_host_keys (et non load_system_host_keys) : le fichier est
        # ENRICHI par AutoAdd a la 1re connexion, verifie ensuite
        self._client.load_host_keys(str(keys_path))
        if self._client.get_host_keys().lookup(host) is None:
            self._client.set_missing_host_key_policy(
                paramiko.AutoAddPolicy())       # 1re connexion : epingler
        else:
            self._client.set_missing_host_key_policy(
                paramiko.RejectPolicy())
        try:
            self._client.connect(host, port=int(port), username=username,
                                 password=password, timeout=15,
                                 allow_agent=False, look_for_keys=False)
        except paramiko.BadHostKeyException as e:
            raise SftpError(
                f"Clé d'hôte SFTP de {e.hostname} DIFFÉRENTE de celle "
                f"épinglée dans {keys_path} : MITM possible OU serveur "
                f"réinstallé — supprimez ce fichier si le changement est "
                f"légitime, puis reconnectez-vous.") from e
        except Exception as e:              # noqa: BLE001 - paramiko hétérogène
            raise SftpError(f"Connexion SFTP {host}:{port} : {e}") from e
        self._sftp = self._client.open_sftp()

    def close(self) -> None:
        try:
            self._sftp.close()
        finally:
            self._client.close()

    # ------------------------------------------------------------- distants

    def list_remote(self, remote_root: str) -> dict:
        """Arbre distant -> {chemin relatif posix: (taille, mtime)} fichiers
        seuls. Les *.bak ne sont PAS listes (inertes) ; les *.yaml.bin le
        SONT -- jamais synchronises, mais il faut les voir pour les
        INVALIDER (yaml recopie = cache perime) ou purger les orphelins."""
        root = remote_root.rstrip("/") or "/"
        listing: dict = {}
        stack = [("", root)]
        while stack:
            rel, absolute = stack.pop()
            try:
                entries = self._sftp.listdir_attr(absolute)
            except IOError as e:
                if not rel:
                    raise SftpError(
                        f"Dossier distant introuvable : {remote_root} ({e})") from e
                continue
            for entry in entries:
                name = entry.filename
                rel_path = f"{rel}/{name}" if rel else name
                mode = entry.st_mode or 0
                if stat_module.S_ISDIR(mode):
                    stack.append((rel_path, f"{absolute}/{name}"))
                elif stat_module.S_ISREG(mode):
                    if name.lower().endswith(".bak"):
                        continue
                    listing[rel_path] = (entry.st_size or 0, entry.st_mtime or 0)
        return listing

    def read_file(self, remote_path: str) -> bytes:
        import io
        buffer = io.BytesIO()
        self._sftp.getfo(remote_path, buffer)
        return buffer.getvalue()

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Copie + replique le mtime LOCAL sur le fichier distant : la
        comparaison (taille, mtime) devient idempotente malgre le decalage
        d'horloge entre les machines."""
        self._mkdirs(posixpath.dirname(remote_path))
        self._sftp.put(str(local_path), remote_path)
        st = local_path.stat()
        try:
            self._sftp.utime(remote_path, (st.st_atime, st.st_mtime))
        except IOError:
            pass                        # serveur SFTP sans extension utime

    def delete_file(self, remote_path: str) -> None:
        self._sftp.remove(remote_path)

    def _mkdirs(self, remote_dir: str) -> None:
        parts = [p for p in (remote_dir or "").split("/") if p]
        current = "/" if remote_dir.startswith("/") else ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            try:
                self._sftp.stat(current)
            except IOError:
                try:
                    self._sftp.mkdir(current)
                except IOError:
                    pass            # course benigne : stat le verifiera


# ------------------------------------------------------------------- plan

def plan_sync(local_root: Path, remote_files: dict) -> dict:
    """Compare l'arbre local (working) au listing distant -> plan miroir.
    Local : .bak et .yaml.bin jamais candidats. Distant : un yaml recopie
    invalide son .bin (cache perime), un .bin sans yaml est un orphelin
    (purge), un fichier distant seul part en suppression (miroir, sauvegarde
    prealable a l'application)."""
    local_root = Path(local_root)
    local_files: dict = {}
    for path in local_root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.endswith(SKIP_SUFFIX):
            continue
        rel = path.relative_to(local_root).as_posix()
        st = path.stat()
        # mtime ENTIER : les attributs SFTP arrivent en secondes ; un float
        # local ne matcherait jamais un int distant a contenu identique
        local_files[rel] = (st.st_size, int(st.st_mtime))
    upload = sorted(rel for rel, (size, mtime) in local_files.items()
                    if remote_files.get(rel) != (size, mtime))
    upload_set = set(upload)
    remote_set = set(remote_files)
    remote_bin_names = {r for r in remote_set if r.lower().endswith(".bin")}
    remote_yaml_names = remote_set - remote_bin_names
    invalidate = sorted({f"{rel}.bin" for rel in upload_set
                         if f"{rel}.bin" in remote_bin_names})
    orphans = sorted(r for r in remote_bin_names
                     if r[:-4] not in remote_yaml_names
                     and r[:-4] not in upload_set)
    delete = sorted(remote_yaml_names - set(local_files))
    return {"upload": upload, "delete": delete, "invalidate": invalidate,
            "orphans": orphans,
            "unchanged": len((set(local_files) & remote_yaml_names)
                             - upload_set)}


def apply_sync(session: SftpSession, local_root: Path, remote_root: str,
               plan: dict, backup_dir: Path, progress=None) -> dict:
    """Execute le plan (bloquant : thread). Les fichiers supprimes sont
    telecharges dans backup_dir AVANT suppression. progress(text) informe
    l'UI (marshal signal cote appelant)."""
    local_root = Path(local_root)
    remote_root = remote_root.rstrip("/")
    done = {"uploaded": 0, "deleted": 0, "invalidated": 0,
            "backups": 0, "errors": []}

    def report(text):
        if progress is not None:
            try:
                progress(text)
            except Exception:           # noqa: BLE001 - callback UI
                logger.exception("progress sftp")

    total = len(plan["upload"]) + len(plan["delete"]) + len(plan["invalidate"])
    step = 0
    for rel in plan["upload"]:
        step += 1
        report(f"[{step}/{total}] + {rel}")
        try:
            session.upload_file(local_root / rel,
                                f"{remote_root}/{rel}")
            done["uploaded"] += 1
        except Exception as e:          # noqa: BLE001
            done["errors"].append(f"upload {rel} : {e}")
    for rel in plan["delete"]:
        step += 1
        report(f"[{step}/{total}] - {rel}")
        remote_path = f"{remote_root}/{rel}"
        try:
            target = backup_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(session.read_file(remote_path))
            done["backups"] += 1
        except Exception as e:          # noqa: BLE001
            done["errors"].append(f"backup {rel} : {e} (suppression annulée)")
            continue
        try:
            session.delete_file(remote_path)
            done["deleted"] += 1
        except Exception as e:          # noqa: BLE001
            done["errors"].append(f"delete {rel} : {e}")
    for rel in plan["invalidate"] + plan["orphans"]:
        step += 1
        report(f"[{step}/{total}] x {rel}")
        try:
            session.delete_file(f"{remote_root}/{rel}")
            done["invalidated"] += 1
        except Exception as e:          # noqa: BLE001
            done["errors"].append(f"bin {rel} : {e}")
    return done


def sync_summary(done: dict) -> str:
    from core.i18n import t
    return t("ewa.sync.summary", up=done["uploaded"], deleted=done["deleted"],
             bins=done["invalidated"], errors=len(done["errors"]))
