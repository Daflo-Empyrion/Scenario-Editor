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

"""Prefabs du scenario qui ne servent a rien (candidats au menage).

Regle volontairement CONSERVATRICE : un .epb n'est declare inutilise que si
AUCUN de ses identifiants (nom de fichier, Name interne, tags de la propriete
21) n'apparait nulle part dans le texte du scenario (Playfields, Sectors,
Content/Configuration, Extras, RandomPresets). Marquer un prefab « inutilise »
est une invitation a le supprimer : un faux positif casserait un POI, donc on
prefere rater des inutiles plutot que d'en inventer.

Pourquoi une recherche textuelle et pas une resolution par cle : un prefab est
cite par son GROUPE (GroupName des POI, resolu par les tags de l'entete), par
son nom de FICHIER (Prefab:/PrefabName:) ou par son Name interne, dans des
sections variees (POIs, SpaceVessels, DroneSpawning, POI Groups config...).
Chercher l'identifiant partout couvre tous ces cas d'un coup.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from core.epb_blueprint import read_header

_TEXT_SUFFIXES = (".yaml", ".yml", ".ecf", ".txt", ".csv", ".epk",
                  ".json", ".xml", ".manifest")
_TOKEN_RE = re.compile(r"[\w.\-]+")
_ALNUM_RE = re.compile(r"[^a-z0-9]")
# en dessous de ce seuil un identifiant matche n'importe quoi : il ne prouve
# rien, on ignore ces identifiants la (et le prefab est considere utilise)
_MIN_ID = 4


@dataclass
class UsageReport:
    used: int = 0
    unused: List[tuple] = field(default_factory=list)   # (Path, octets)
    scanned: int = 0

    @property
    def unused_bytes(self) -> int:
        return sum(taille for _p, taille in self.unused)


def _scenario_tokens(root: Path) -> Set[str]:
    """Jetons NORMALISES du scenario (alphanumerique minuscule), hors
    Prefabs/**.epb. La normalisation est indispensable : le PDA ecrit
    `OPVPolaris_T1` la ou l'entete du prefab dit `OPVPolaris` — une
    comparaison de jetons exacts declarait 37 prefabs inutilises a tort
    (mesure 05/11/2026, Extras/PDA).

    `Prefabs/` est scanne AUSSI, pour ses fichiers TEXTE seulement : c'est la
    que vit `_PoiGroupsConfig.yaml`, qui mappe chaque pool de POI vers ses
    `BlueprintFileNames`. L'ignorer faisait declarer « inutilise » tout
    prefab cite uniquement par un pool — vecu 12/11 : BAO_ARCMiningOutpost
    parti en quarantaine alors qu'il sert a `ConflictARCMines`."""
    jetons: Set[str] = set()
    for sous in ("Playfields", "Sectors", "Content", "Extras",
                 "RandomPresets", "SharedData", "Prefabs"):
        base = root / sous
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            try:
                texte = f.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            for m in _TOKEN_RE.finditer(texte):
                normalise = _ALNUM_RE.sub("", m.group(0).casefold())
                if normalise:
                    jetons.add(normalise)
    return jetons


def _cite(identifiants: Set[str], jetons: Set[str], blob: str) -> bool:
    """Au moins un identifiant assez long est present dans le blob.

    Recherche SOUS-CHAINE : `opvpolaris` apparait dans `opvpolarist1`. Le
    blob est petit (~2 Mo de jetons), le cout est negligeable.

    Les identifiants COURTS (< _MIN_ID, ex. le tag `RE2`) ne sont pas
    ignores : ils seraient absents partout et feraient declarer inutilise un
    prefab qui appartient bel et bien au groupe `RE2`. Ils sont testes en
    EGALITE de jeton — jamais en sous-chaine, sinon `re2` matcherait tout."""
    courts = {i for i in identifiants if len(i) < _MIN_ID}
    if any(i in jetons for i in courts):
        return True
    return any(i in blob for i in identifiants if len(i) >= _MIN_ID)


def scan_prefab_usage(root: Path) -> UsageReport:
    """(used, unused) sur `root/Prefabs`. `unused` = [(chemin, octets)]."""
    root = Path(root)
    prefabs = root / "Prefabs"
    rapport = UsageReport()
    if not prefabs.is_dir():
        return rapport
    jetons = _scenario_tokens(root)
    if not jetons:
        return rapport
    blob = " " + " ".join(sorted(jetons)) + " "
    for epb in sorted(prefabs.glob("*.epb")):
        rapport.scanned += 1
        identifiants = {_ALNUM_RE.sub("", epb.stem.casefold())}
        try:
            entete = read_header(epb)
        except Exception:            # noqa: BLE001 - format exotique
            entete = None
        if entete:
            nom, tags = entete
            if nom:
                identifiants.add(_ALNUM_RE.sub("", nom.strip().casefold()))
            identifiants.update(
                _ALNUM_RE.sub("", t.strip().casefold())
                for t in (tags or "").split(",") if t.strip())
        if _cite(identifiants, jetons, blob):
            rapport.used += 1
            continue
        try:
            taille = epb.stat().st_size
        except OSError:
            taille = 0
        rapport.unused.append((epb, taille))
    return rapport


def trash_prefabs(paths: List[Path], kind: str = "prefabs") -> tuple:
    """Compatibilite : delegue a `core.scenario_cleanup.trash_files`, qui
    gere aussi les compagnons .decals/.jpg des .epb."""
    from core.scenario_cleanup import trash_files

    return trash_files(paths, kind=kind)
