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

"""Nettoyage d'un scenario : fichiers qui ne servent a rien.

DEUX CLASSES, volontairement separees :
- SURS (`safe=True`) : supprimables sans risque de casser le scenario —
  `.bak` (le projet a vecu un `Sectors.yaml.bak` qui VIDait la galaxie), cache
  `*.yaml.bin` orphelin (le jeu le regenere), `.jpg`/`.decals` d'un prefab
  disparu (compagnons orphelins).
- A VERIFIER (`safe=False`) : images/icones dont le nom n'est cite nulle part.
  On ne peut PAS garantir qu'elles sont inutiles : les icones sont souvent
  appelees avec un prefixe (`bki12.7x99mmBullet` pour `12.7x99mmBullet.png`),
  et certains dossiers sont charges par CONVENTION (les ecrans de chargement).
  Le module les liste, l'utilisateur tranche.

Regle de correspondance (classe « a verifier ») : le nom est normalise en
alphanumerique minuscule des deux cotes, puis cherche en SOUS-CHAINE dans les
jetons du scenario — un prefixe colle (`bki…`) compte donc comme une
reference. En cas de doute on declare « reference » : rater un inutile est
moins grave que supprimer un fichier utilise.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

_TEXT_SUFFIXES = (".yaml", ".yml", ".ecf", ".txt", ".csv", ".json", ".xml",
                  ".manifest", ".ini", ".cfg")
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".dds", ".webm")
_VISIT = ("Playfields", "Sectors", "Content", "Extras", "RandomPresets",
          "SharedData")
_TOKEN_RE = re.compile(r"[\w.\-]+")
_ALNUM_RE = re.compile(r"[^a-z0-9]")


@dataclass(frozen=True)
class JunkItem:
    path: Path
    category: str          # backup | cache | thumbnail | asset
    safe: bool
    octets: int = 0


def _scenario_text(root: Path) -> str:
    """Texte complet du scenario (hors Prefabs), pour les recherches de noms."""
    morceaux = []
    for sous in _VISIT:
        base = root / sous
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            try:
                morceaux.append(f.read_text(encoding="utf-8-sig",
                                            errors="replace"))
            except OSError:
                continue
    return "\n".join(morceaux)


def _token_blob(texte: str) -> str:
    """Jetons normalises (alphanumerique minuscule), separes par une espace.

    Les jetons gardent d'abord points et tirets (`12.7x99mmBullet` reste
    entier), PUIS sont reduits a l'alphanumerique : sans ca, `12.7x…` se
    coupait en `12` + `7x…` et son icone passait pour non citee (vecu 05/11,
    1085 faux positifs).
    """
    return " ".join(
        normalise for normalise in
        (_ALNUM_RE.sub("", t) for t in _TOKEN_RE.findall(texte.casefold()))
        if normalise)


def _unused_stems(stems, blob: str) -> Set[str]:
    """Noms ABSENTS du blob.

    Test SOUS-CHAINE nom par nom : une regex d'alternatives sur 1500 noms
    prenait 143 s (backtracking), le test direct reste sous les 10 s.
    Le blob est un texte de quelques Mo : c'est la boucle la plus lente du
    module, a lancer dans un thread (l'appelant le fait).
    """
    return {s for s in stems if s not in blob}


def scan_junk(root: Path) -> List[JunkItem]:
    """Fichiers inutiles du scenario, classes par categorie. Ne supprime rien."""
    root = Path(root)
    items: List[JunkItem] = []
    if not root.is_dir():
        return items

    # 1. .bak : jamais charges par le jeu, deja fatal dans Sectors/
    for f in root.rglob("*.bak"):
        items.append(JunkItem(f, "backup", True, f.stat().st_size))

    # 2. cache *.yaml.bin orphelin (le .yaml source n'existe plus)
    for f in root.rglob("*.yaml.bin"):
        if not f.with_suffix("").exists():
            items.append(JunkItem(f, "cache", True, f.stat().st_size))

    # 3. compagnons orphelins des prefabs (le .epb n'existe plus)
    prefabs = root / "Prefabs"
    if prefabs.is_dir():
        for f in prefabs.iterdir():
            if f.suffix.lower() in (".jpg", ".decals") \
                    and not f.with_suffix(".epb").exists():
                items.append(JunkItem(f, "thumbnail", True, f.stat().st_size))

    # 4. images dont le nom n'est cite nulle part (a verifier)
    blob = _token_blob(_scenario_text(root))
    images = []
    for sous in _VISIT:
        base = root / sous
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if f.is_file() and f.suffix.lower() in _IMAGE_SUFFIXES:
                images.append(f)
    stems = {_ALNUM_RE.sub("", f.stem.casefold()) for f in images}
    stems.discard("")
    inconnus = _unused_stems(stems, blob)
    for f in images:
        if _ALNUM_RE.sub("", f.stem.casefold()) in inconnus:
            items.append(JunkItem(f, "asset", False, f.stat().st_size))
    return items


def trash_files(paths: List[Path], kind: str = "cleanup") -> tuple:
    """Met des fichiers a la corbeille : copie de secours centralisee PUIS
    suppression. Pour un `.epb`, ses compagnons `.decals`/`.jpg` partent avec
    lui (un `.decals` orphelin resterait dans Prefabs/).

    Si la copie echoue, le fichier N'EST PAS supprime : l'ordre est la garde.
    Retourne (nombre de fichiers traites, [messages d'echec]).
    """
    from core.fsutil import central_backup

    faits, echecs = 0, []
    for chemin in paths:
        f = Path(chemin)
        try:
            central_backup(f, kind=kind)
        except OSError as exc:
            echecs.append(f"{f.name} : sauvegarde impossible ({exc})")
            continue
        try:
            f.unlink()
        except OSError as exc:
            echecs.append(f"{f.name} : suppression impossible ({exc})")
            continue
        if f.suffix.lower() == ".epb":
            for suffixe in (".decals", ".jpg"):
                compagnon = f.with_suffix(suffixe)
                if compagnon.exists():
                    try:
                        central_backup(compagnon, kind=kind)
                        compagnon.unlink()
                    except OSError as exc:
                        echecs.append(f"{compagnon.name} : {exc}")
        faits += 1
    return faits, echecs
