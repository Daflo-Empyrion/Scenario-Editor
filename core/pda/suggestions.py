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
Pools de suggestions contextuelles du NOUVEAU module PDA -- identifiants de
pool definis dans core/pda/schema.py (POOL_*).

Principe confirme en session : SCENARIO D'ABORD, VANILLE EN COMPLEMENT. Chaque
pool = fusion (valeurs statiques connues) + (valeurs deja utilisees dans le
PDA.yaml ouvert) + (valeurs extraites des playfields du scenario) +
(valeurs extraites de la vanille si le dossier Content du jeu est renseigne
dans les reglages -- meme logique que le repli localization_vanilla.pak).

Latence : les docs playfield utilises pour extraire POI/creatures passent par
un cache module (cle mtime_ns + taille, FIFO 8) -- meme discipline que
core/ecf/doc_cache.py, JAMAIS de re-parse en boucle dans un handler UI. Les
documents caches sont PARTAGES et LECTURE SEULE : ne jamais muter."""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.yamllite.parser import parse_yaml_file
from core.yamllite.model import YamlEntry

_yaml_cache: Dict[str, Tuple[Tuple[int, int], object]] = {}
_YAML_CACHE_MAX = 8

# Checks dont les 'Names' designent des POI (pour le pool POI depuis le PDA
# lui-meme) ou des unites/creatures (pool UNIT) -- distinguo necessaire parce
# que 'Names' seul ne suffit pas a savoir de QUOI c'est un nom.
_POI_NAME_CHECKS = ("NearPoi", "InventoryOpened", "InventoryClosed",
                    "InventoryOpenedPoi", "InventoryClosedPoi",
                    "DeviceUsed", "MainPowerSwitched")
_UNIT_NAME_CHECKS = ("NearUnit", "SubjectKilled", "StructureSpawned")
_PLAYFIELD_NAME_CHECKS = ("PlayfieldEntered", "PlayfieldLeft")
_DIALOG_NAME_CHECKS = ("DialogOption",)
_SIGNAL_NAME_CHECKS = ("Signal", "DeviceNamePowered")
_WINDOW_NAME_CHECKS = ("WindowOpened", "WindowClosed")
_BIOME_NAME_CHECKS = ("BiomeChanged",)
_PF_TYPE_NAME_CHECKS = ("PlayfieldTypeEntered", "PlayfieldTypeLeft")
_STAR_NAME_CHECKS = ("StarClassEntered",)


def _cached_playfield_doc(path: Path):
    """Doc playfield parse, cache partage lecture seule (mtime_ns + taille)."""
    try:
        stat = path.stat()
    except OSError:
        return None
    key = str(path)
    signature = (stat.st_mtime_ns, stat.st_size)
    cached = _yaml_cache.get(key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    try:
        doc = parse_yaml_file(str(path))
    except Exception:
        return None
    if len(_yaml_cache) >= _YAML_CACHE_MAX:
        _yaml_cache.pop(next(iter(_yaml_cache)))
    _yaml_cache[key] = (signature, doc)
    return doc


def collect_names_for_check(model, check: str, key: str = "Names") -> List[str]:
    """Toutes les valeurs de Names/Types des actions d'un check donne, dans
    tout le PDA.yaml ouvert (suggestions reutilisables -- le seul bassin
    GARANTI valide, meme principe que collect_used_names de l'ancien module)."""
    values: set = set()
    for chapter in model.chapters():
        for task in model.tasks(chapter):
            for action in model.actions(task):
                if model.action_check(action) != check:
                    continue
                values.update(model.get_list(action, key))
    return sorted(v for v in values if v)


def collect_used_pda_tokens(model) -> List[str]:
    """Tous les jetons pda_XXXXXXX du PDA.yaml (pour rejouer un texte existant)."""
    return sorted(model.collect_all_tokens())


def chapter_title_tokens(model) -> List[str]:
    return [model.chapter_title_token(c) for c in model.chapters()
            if model.chapter_title_token(c)]


def _playfield_yaml_paths(content_dir: Optional[Path]) -> List[Path]:
    if content_dir is None:
        return []
    pf_dir = content_dir / "Playfields"
    if not pf_dir.is_dir():
        return []
    return sorted(pf_dir.glob("*.yaml"))


def _collect_poi_and_creature_names(yaml_paths: List[Path],
                                    pois: set, creatures: set) -> None:
    """Extrait POI (Fixed+Random) et creatures des playfields -- reutilise les
    fonctions confirmees de core/playfield_editor.py, jamais de logique
    reimprovisee."""
    from core.playfield_editor import find_poi_items, find_creature_items
    for path in yaml_paths:
        doc = _cached_playfield_doc(path)
        if doc is None:
            continue
        for item in find_poi_items(doc):
            if item.value:
                pois.add(item.value)
        for item in find_creature_items(doc):
            if item.value:
                creatures.add(item.value)


class PdaSuggestions:
    """Bassins de suggestions fusionnes, construits UNE FOIS a l'ouverture du
    dialogue (collecte lazy par pool : un pool n'est calcule qu'a sa premiere
    demande)."""

    def __init__(self, model, scenario_content_dir: Optional[Path] = None,
                 vanilla_content_dir: Optional[Path] = None,
                 sibling_ecf_files: Optional[List[Path]] = None):
        self.model = model
        self.scenario_content_dir = scenario_content_dir
        self.vanilla_content_dir = vanilla_content_dir
        self._ecf_files = list(sibling_ecf_files or [])
        self._cache: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    def pool(self, pool_key: str) -> List[str]:
        if pool_key not in self._cache:
            self._cache[pool_key] = self._build_pool(pool_key)
        return self._cache[pool_key]

    # ------------------------------------------------------------------
    def _build_pool(self, pool_key: str) -> List[str]:
        from core.pda.schema import (POOL_POI, POOL_UNIT, POOL_PLAYFIELD,
                                     POOL_PLAYFIELD_TYPE, POOL_STAR_CLASS,
                                     POOL_DIALOG, POOL_SIGNAL, POOL_WINDOW,
                                     POOL_RESOURCE, POOL_ITEM, POOL_BLOCK,
                                     POOL_BIOME, POOL_FACTION, POOL_CHAPTER,
                                     POOL_PDA_TOKEN, STATIC_POOLS)
        if pool_key == POOL_PDA_TOKEN:
            return collect_used_pda_tokens(self.model)
        if pool_key == POOL_CHAPTER:
            return chapter_title_tokens(self.model)
        if pool_key == POOL_ITEM:
            return self._item_names()
        if pool_key == POOL_BLOCK:
            return self._resource_and_block_names(include_asteroid=False)
        if pool_key == POOL_RESOURCE:
            return self._resource_and_block_names(include_asteroid=True)
        if pool_key == POOL_POI:
            merged = self._used_names(_POI_NAME_CHECKS) | self._poi_names()
            return _sorted(merged)
        if pool_key == POOL_UNIT:
            merged = self._used_names(_UNIT_NAME_CHECKS) | self._creature_names()
            return _sorted(merged)
        if pool_key == POOL_PLAYFIELD:
            merged = self._used_names(_PLAYFIELD_NAME_CHECKS) | self._playfield_names()
            return _sorted(merged)
        # Pools a source statique + valeurs deja utilisees du meme genre
        static = set(STATIC_POOLS.get(pool_key, ()))
        check_map = {
            POOL_DIALOG: _DIALOG_NAME_CHECKS,
            POOL_SIGNAL: _SIGNAL_NAME_CHECKS,
            POOL_WINDOW: _WINDOW_NAME_CHECKS,
            POOL_BIOME: _BIOME_NAME_CHECKS,
            POOL_PLAYFIELD_TYPE: _PF_TYPE_NAME_CHECKS,
            POOL_STAR_CLASS: _STAR_NAME_CHECKS,
            POOL_FACTION: (),
        }
        used = self._used_names(check_map.get(pool_key, ()))
        if pool_key == POOL_FACTION:
            used |= self._faction_names()
        return _sorted(static | used)

    # ------------------------------------------------------------------
    def _used_names(self, checks: tuple) -> set:
        out: set = set()
        for chapter in self.model.chapters():
            for task in self.model.tasks(chapter):
                for action in self.model.actions(task):
                    if model_action_check(action) in checks:
                        out.update(self.model.get_list(action, "Names"))
        return {v for v in out if v}

    def _faction_names(self) -> set:
        out: set = set()
        for chapter in self.model.chapters():
            for task in self.model.tasks(chapter):
                for action in self.model.actions(task):
                    out.update(self.model.get_list(action, "Faction"))
                    for reward in self.model.rewards(action):
                        if reward.faction:
                            out.add(reward.faction)
                for reward in self.model.rewards(task):
                    if reward.faction:
                        out.add(reward.faction)
            faction = model_scalar(chapter, "Faction")
            if faction:
                out.add(faction)
        return out

    # ------------------------------------------------------------------
    def _all_playfield_yamls(self) -> List[Path]:
        return (_playfield_yaml_paths(self.scenario_content_dir) +
                _playfield_yaml_paths(self.vanilla_content_dir))

    def _poi_names(self) -> set:
        pois: set = set()
        _collect_poi_and_creature_names(self._all_playfield_yamls(), pois, set())
        return pois

    def _creature_names(self) -> set:
        creatures: set = set()
        _collect_poi_and_creature_names(self._all_playfield_yamls(), set(), creatures)
        return creatures

    def _playfield_names(self) -> set:
        names: set = set()
        for path in self._all_playfield_yamls():
            names.add(path.stem)
        return names

    # ------------------------------------------------------------------
    def _find_ecf(self, name: str) -> Optional[Path]:
        for path in self._ecf_files:
            if path.name == name:
                return path
        return None

    def _item_names(self) -> List[str]:
        from core.ecf.block_creation import find_file_by_name, list_craftable_names
        items_path = self._find_ecf("ItemsConfig.ecf")
        blocks_path = self._find_ecf("BlocksConfig.ecf")
        if items_path is None and blocks_path is None:
            return []
        return list_craftable_names(items_path, blocks_path)

    def _resource_and_block_names(self, include_asteroid: bool) -> List[str]:
        """Pool ressources minables (BlockDestroyed/ResourceDiscovered/
        NearResource) : vrais blocs de ressource BlocksConfig.ecf + variantes
        d'asteroide 'AsteroidVoxel0N<Materiau>' (motif confirme, voir
        core.pda_mission.list_mining_target_name_suggestions qui a etabli ce
        comportement)."""
        from core.pda_mission import list_mining_target_name_suggestions
        blocks_path = self._find_ecf("BlocksConfig.ecf")
        if blocks_path is None:
            return []
        names = set(list_mining_target_name_suggestions([blocks_path]))
        if not include_asteroid:
            names = {n for n in names if not n.startswith("AsteroidVoxel")}
        return sorted(names)


def model_action_check(action: YamlEntry) -> str:
    from core.pda.model import PdaModel
    return PdaModel.action_check(action)


def model_scalar(entry: YamlEntry, key: str) -> str:
    from core.pda.model import PdaModel
    return PdaModel.scalar(entry, key)


_SORT_KEY = re.compile(r"([0-9]+)")


def _sorted(values) -> List[str]:
    """Tri alphabetique naturel (Iron2 apres Iron10) -- les noms Empyrion sont
    truffes de suffixes numeriques."""
    return sorted({v for v in values if v},
                  key=lambda s: [int(p) if p.isdigit() else p.lower()
                                 for p in _SORT_KEY.split(s)])
