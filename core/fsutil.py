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
