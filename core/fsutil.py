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
Utilitaire filesystem partage. Sert principalement a garantir qu'aucun fichier/dossier
ecrit par l'application n'herite d'un attribut lecture seule de sa source -- probleme
concret rencontre avec des scenarios installes sous Program Files (souvent marques
lecture seule par Windows) : `shutil.copy2`/`copytree` preservent les metadonnees par
defaut, ce qui rend la copie de travail elle-meme lecture seule (impossible a modifier
ou meme a supprimer -- Windows demande alors "l'autorisation" du proprietaire, meme si
c'est l'utilisateur courant).
"""
import os
import re
import shutil
import stat
import tempfile
import time
from pathlib import Path


def clear_readonly(path: Path) -> None:
    """Retire l'attribut lecture seule sur `path`. Si c'est un dossier, le fait
    recursivement sur tout son contenu (fichiers ET sous-dossiers). Ignore les erreurs
    individuelles (fichier verrouille par un autre processus, etc.) plutot que de faire
    echouer toute l'operation pour un seul fichier problematique."""
    path = Path(path)
    if not path.exists():
        return

    def _unlock_one(p: Path) -> None:
        try:
            current = os.stat(p).st_mode
            os.chmod(p, current | stat.S_IWRITE | stat.S_IWUSR)
        except OSError:
            pass

    if path.is_dir():
        _unlock_one(path)
        for root, dirs, files in os.walk(path):
            for d in dirs:
                _unlock_one(Path(root) / d)
            for f in files:
                _unlock_one(Path(root) / f)
    else:
        _unlock_one(path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Ecrit `data` dans `path` de maniere ATOMIQUE : le contenu est d'abord ecrit
    entierement dans un fichier temporaire DANS LE MEME DOSSIER (meme volume --
    os.replace ne sait pas traverser les volumes), synchronise sur le disque, puis
    renomme sur la destination via os.replace, qui est atomique sur Windows comme
    sur POSIX.

    Interet : avec un truncate-then-write classique, un crash ou une coupure
    d'alimentation PENDANT l'ecriture laisse le fichier coupe en deux (donnee de
    scenario ou de configuration irrecuperable). Avec ce helper, au pire l'ancienne
    version intacte est conservee, au mieux la nouvelle est complete -- jamais
    d'etat intermediaire. Le fichier temporaire est supprime en cas d'echec.

    Gere aussi l'attribut lecture seule de la destination (meme probleme que pour
    une ecriture directe -- cf. clear_readonly, que les appelants n'ont donc plus
    besoin d'appeler eux-memes avant d'ecrire).

    Leve OSError en cas d'echec (disque plein, destination verrouillee par un
    autre processus...) -- l'appelant affiche l'erreur comme avant."""
    path = Path(path)
    clear_readonly(path)

    tmp = tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False)
    tmp_path = Path(tmp.name)
    try:
        with tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())  # garantit que le contenu est bien sur le disque AVANT le renommage
        os.replace(tmp_path, path)
    except OSError:
        try:
            tmp_path.unlink()
        except OSError:
            pass  # le nettoyage du temporaire ne doit pas masquer l'erreur d'origine
        raise
    # Accroches post-ecriture (index de noms, caches...) : jamais d'exception
    # ni de latence perceptible -- une ecriture ne doit jamais echouer a cause
    # d'un observateur (demande 31/10 : mise a jour de l'index de noms en
    # arriere-plan a la sauvegarde).
    for _hook in _WRITE_HOOKS:
        try:
            _hook(path)
        except Exception:
            pass


# Observateurs de toutes les ecritures atomiques du projet (enregistrement
# via register_write_hook ; appelé APRES que le fichier final est en place).
_WRITE_HOOKS = []


def register_write_hook(callback) -> None:
    """Enregistre un observateur appele apres CHAQUE ecriture atomique reussie
    (path final). Utilise par core/ecf/name_index.py -- ne pas y faire de
    travail lourd : c'est sur le chemin de toutes les ecritures."""
    _WRITE_HOOKS.append(callback)


def atomic_write_text(path: Path, text: str, encoding: str = 'utf-8') -> None:
    """Variante texte de atomic_write_bytes -- meme semantique qu'un
    `open(path, 'w', encoding=..., newline='')` : le texte est encode SANS
    traduction des fins de ligne, donc le contenu au disque est exactement la
    chaine passee (comportement requis pour le round-trip fidele des fichiers
    de scenario, voir core/ecf/model.py)."""
    atomic_write_bytes(path, text.encode(encoding))


def central_backup(path: Path, kind: str = "sectors") -> Path:
    """Copie de secours vers ~/.empyrion_editor/backups/<kind>/ — JAMAIS
    un *.bak a cote du fichier : le jeu charge TOUS les .yaml du dossier
    Sectors/ et un Sectors.yaml.bak y est FATAL (vecu 02/10/2026, le jeu
    le parse comme une liste de secteurs -> galaxie vide)."""
    import time
    src = Path(path)
    dst_dir = Path.home() / ".empyrion_editor" / "backups" / kind
    dst_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = dst_dir / f"{src.stem}-{stamp}{src.suffix}.bak"
    n = 0                                    # deux sauvegardes la meme seconde
    while dst.exists():
        n += 1
        dst = dst_dir / f"{src.stem}-{stamp}-{n}{src.suffix}.bak"
    shutil.copy2(src, dst)
    return dst

# Menage des sauvegardes de `central_backup` : les fichiers datees s'accumulent
# dans ~/.empyrion_editor/backups/<type>/ (vecu : 1268 fichiers dans
# cjk_cleanup, 485 dans difficulty). Regle : garder les N plus recentes de
# chaque dossier, supprimer au-dela celles qui depassent X jours.
BACKUP_KEEP = 10
BACKUP_MAX_AGE_DAYS = 60


def _backups_root(root=None) -> Path:
    return Path(root) if root else Path.home() / ".empyrion_editor" / "backups"


def plan_backup_cleanup(root=None, keep: int = BACKUP_KEEP,
                        max_age_days: float = BACKUP_MAX_AGE_DAYS) -> dict:
    """{fichier: taille} des sauvegardes a supprimer, sans rien effacer.

    Ne regarde QUE les fichiers `*.bak` poses directement dans
    `backups/<type>/` par `central_backup`. Les SOUS-DOSSIERS (sauvegardes de
    scenario avec `_backup_info.json`, anciens enregistrements aplatis) ne sont
    jamais inspectes ni supprimes : leur menage appartient a
    `gui/backup_dialog.py`, qui sait ce qu'ils contiennent.
    """
    folder_root = _backups_root(root)
    if not folder_root.is_dir():
        return {}
    limit = time.time() - float(max_age_days) * 86400
    floor = max(int(keep), 1)
    out = {}
    for folder in sorted(p for p in folder_root.iterdir() if p.is_dir()):
        try:
            files = sorted((f for f in folder.iterdir()
                            if f.is_file() and f.name.endswith(".bak")),
                           key=lambda f: f.stat().st_mtime, reverse=True)
        except OSError:
            continue
        for stale in files[floor:]:
            try:
                stat = stale.stat()
            except OSError:
                continue
            if stat.st_mtime < limit:
                out[stale] = stat.st_size
    return out


_STAMP_RE = re.compile(r"-\d{8}-\d{6}(?:-\d+)?(?=\.[^.]*$)")


def original_name(backup) -> str:
    """Nom d'origine d'une sauvegarde : `Localization-20261112-121530.csv.bak`
    -> `Localization.csv` (propose au moment de restaurer)."""
    name = Path(backup).name
    if name.endswith(".bak"):
        name = name[:-4]
    return _STAMP_RE.sub("", name)


def list_backup_files(root=None, kind=None) -> list:
    """[(fichier, type, mtime, taille)] des `*.bak` de `central_backup`, du
    plus recent au plus ancien. Meme perimetre que le menage : les fichiers
    directement dans `backups/<type>/`, jamais les sous-dossiers."""
    folder_root = _backups_root(root)
    if not folder_root.is_dir():
        return []
    out = []
    for folder in sorted(p for p in folder_root.iterdir() if p.is_dir()):
        if kind and folder.name != kind:
            continue
        try:
            files = [f for f in folder.iterdir()
                     if f.is_file() and f.name.endswith(".bak")]
        except OSError:
            continue
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            out.append((path, folder.name, stat.st_mtime, stat.st_size))
    out.sort(key=lambda row: row[2], reverse=True)
    return out


def restore_backup_file(backup, destination) -> Path | None:
    """Restaure une sauvegarde vers `destination`.

    L'actuel fichier de destination est d'abord sauvegarde (`central_backup`,
    type « restauration ») : un ecrasement doit toujours etre rattrapable.
    Retourne le chemin de cette sauvegarde de securite, ou None.
    """
    src, dst = Path(backup), Path(destination)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    safety = central_backup(dst, "restauration") if dst.is_file() else None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return safety


def apply_backup_cleanup(plan: dict) -> tuple:
    """Supprime les fichiers d'un plan ; retourne (nombre, octets liberes)."""
    count = freed = 0
    for path, size in plan.items():
        try:
            Path(path).unlink()
        except OSError:
            continue
        count += 1
        freed += size
    return count, freed


# Caracteres parasites colles APRES le crochet fermant d'une liste flow
# en fin de valeur ('[Pirates, None]s' -> vecu 01/10/2026 : corruption de
# presets SolarSystemConfig qui faisait crasher le parseur YAML du jeu
# « did not find expected key »). YamlDotNet est strict sur ce point.
_JUNK_AFTER_FLOW = re.compile(r"(\])[A-Za-z0-9_]+(?=\s*(?:#.*)?$)")


def repair_stray_junk_after_flow(text: str) -> tuple:
    """Retire les caracteres parasites colles APRES le crochet fermant
    d'une liste flow en fin de valeur (les commentaires de fin de ligne
    sont preserves). Retourne (texte corrige, nombre de corrections).
    Une ligne commentee seule n'est jamais touchee."""
    fixed = 0
    out = []
    for line in text.splitlines(keepends=True):
        eol = ""
        while line and line[-1] in "\r\n":
            eol = line[-1] + eol
            line = line[:-1]
        if line.lstrip().startswith("#"):
            out.append(line + eol)
            continue
        idx = line.find("#")
        no_comment, comment = (line, "") if idx < 0 \
            else (line[:idx], line[idx:])
        if _JUNK_AFTER_FLOW.search(no_comment):
            no_comment = _JUNK_AFTER_FLOW.sub(r"\1", no_comment)
            fixed += 1
        out.append(no_comment + comment + eol)
    return "".join(out), fixed


def copy_dir_repairing_yaml(source_dir: Path, dest_dir: Path) -> tuple:
    """Copie recursive d'un dossier en REPARANT les *.yaml parasites
    (junk apres crochet de liste flow) ; les autres fichiers sont copies
    tels quels. Retourne (fichiers copies, corrections appliquees)."""
    copied, fixed = 0, 0
    Path(dest_dir).mkdir(parents=True, exist_ok=True)   # dossier vide = cree aussi
    for src in sorted(Path(source_dir).rglob("*")):
        rel = src.relative_to(source_dir)
        dst = Path(dest_dir) / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".yaml":
            try:
                text = src.read_text(encoding="utf-8", errors="replace")
            except Exception:
                shutil.copy2(src, dst)
                copied += 1
                continue
            fixed_text, n = repair_stray_junk_after_flow(text)
            atomic_write_text(dst, fixed_text)
            fixed += n
        else:
            shutil.copy2(src, dst)
        copied += 1
    return copied, fixed


def dir_signature(path: Path) -> str:
    """Empreinte stable du CONTENU d'un dossier (chemins relatifs sans
    casse + tailles + contenus) — sert a comparer un playfield de
    scenario avec son equivalent vanille : une DIFFERENCE signifie que
    le scenario a modifie le playfield (contenu a preserver), pas un
    simple fallback vanille."""
    import hashlib
    h = hashlib.md5()
    for f in sorted(Path(path).rglob("*")):
        if f.is_file():
            h.update(f.relative_to(path).as_posix().lower()
                     .encode("utf-8", "ignore"))
            h.update(str(f.stat().st_size).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def dirs_differ(a: Path, b: Path) -> bool:
    """Vrai si les deux dossiers ont un contenu different (ou si l'un
    manque)."""
    a, b = Path(a), Path(b)
    if not a.is_dir() or not b.is_dir():
        return True
    return dir_signature(a) != dir_signature(b)
