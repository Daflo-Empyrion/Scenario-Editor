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

"""Glossaire general des proprietes du scenario (tous formats : ECF, YAML
playfield/secteurs/gameoptions, EPB, PDA) -- source : docs/glossaire_proprietes.md,
donnees generees dans data/propriete_glossary.json par
tools/build_propriete_glossary.py.

Complement de core/ecf_header_glossary.py (qui ne couvre, a la main, que les
proprietes d'en-tete de quelques fichiers ECF) : ici ~1400 proprietes
expliquees, avec un scope par format pour eviter les faux sens (un 'Name'
YAML de biome n'est pas un 'Name' ECF d'item).

La version EN (data/propriete_glossary.en.json) est redigee a la main, MEME
ORDRE que le FR ; fusion par index a la lecture, repli FR transparent si
l'entree EN est absente/vide (jamais de fiche vide -- meme contrat que
ecf_header_glossary). Le test tests/test_propriete_glossary.py fait echouer
la suite si EN et FR sont desynchronises.
"""

import re

from core.resource_loading import load_json_data

_DATA = load_json_data("propriete_glossary.json")
_PROPS: list = _DATA["props"]
_INDEX_OF: dict = {id(e): i for i, e in enumerate(_PROPS)}

# --- index (construit une fois) -------------------------------------------
# chemin YAML complet ('pois.random[].droneprob') -> entree
_BY_PATH: dict = {}
# (nom en minuscules, scope) -> [entrees] ; (nom, fichier) -> [entrees]
_BY_NAME_SCOPE: dict = {}
_BY_NAME_FILE: dict = {}
for _entry in _PROPS:
    for _p in _entry.get("paths", []):
        _BY_PATH.setdefault(_p.lower(), _entry)
    _BY_NAME_SCOPE.setdefault((_entry["name"].lower(), _entry["scope"]), []).append(_entry)
    if _entry.get("file"):
        _BY_NAME_FILE.setdefault(
            (_entry["name"].lower(), _entry["file"].lower()), []).append(_entry)

# --- EN : cache paresseux, {} = fichier absent (repli FR) ------------------
_EN_DATA = None


def _english_exp_list() -> "list | None":
    """Liste parallele des explications EN (meme ordre que _PROPS), ou None
    si le fichier EN est absent. Une entree vide -> repli FR a l'usage."""
    global _EN_DATA
    if _EN_DATA is None:
        try:
            en = load_json_data("propriete_glossary.en.json")
        except Exception:
            en = {}
        if not isinstance(en, dict) or not en.get("props"):
            _EN_DATA = []
        elif len(en["props"]) != len(_PROPS):
            # desynchronise : on ignore tout le fichier EN (le test fait
            # echouer la suite, on ne degrade pas l'execution)
            _EN_DATA = []
        else:
            _EN_DATA = en["props"]
    return _EN_DATA or None


def _entry_text(entry: dict, index: int) -> str:
    """exp (+ detail) de l'entree, dans la langue de l'interface."""
    from core.i18n import get_language
    exp, detail = entry["exp"], entry.get("detail") or ""
    if get_language() == "en":
        en_list = _english_exp_list()
        if en_list:
            en_entry = en_list[index]
            en_exp = (en_entry.get("exp") or "").strip()
            if en_exp:
                exp = en_exp
                en_detail = (en_entry.get("detail") or "").strip()
                if en_detail:
                    detail = en_detail
    if detail and detail not in exp:
        return f"{exp} ({detail})"
    return exp


# --- recherche --------------------------------------------------------------
def _path_matches_context(entry: dict, context: str) -> bool:
    ctx = context.strip().lower()
    if not ctx:
        return False
    for p in entry.get("paths", []):
        first = re_segment(p)
        if first == ctx:
            return True
    return False


def re_segment(path: str) -> str:
    """Premier segment d'un chemin de glossaire ('POIs.Random[].X' -> 'pois')."""
    head = path.split(".", 1)[0]
    return head.split("[", 1)[0].strip().lower()


def find_explanation(key: str, file: "str | None" = None,
                     scope: "str | None" = None,
                     context: "str | None" = None) -> "str | None":
    """Explication d'une cle de propriete (ex. 'DroneProb', 'MaxCount'),
    pour les infobulles. Ordre de resolution :
    1. chemin complet si la cle en est un (contient un point) ;
    2. entrees indexees par (nom, fichier) quand un fichier ECF est fourni ;
    3. entrees par (nom, scope) ;
    4. entrees par nom seul si un seul scope correspond.
    Avec 'context' (section racine YAML, ex. 'Biomes'), les entrees dont un
    chemin commence par ce contexte sont preferrees -- sinon None.

    Comparaison insensible a la casse ; la cle peut porter les
    decorations de rendu ('`DroneProb`', 'DroneProb:') qui sont ignorees."""
    if not key:
        return None
    clean = key.strip().strip("`").strip()
    if clean.endswith(":"):
        clean = clean[:-1].strip()
    if not clean:
        return None
    lowered = clean.lower()

    # 1. chemin complet
    entry = _BY_PATH.get(lowered)
    if entry is not None:
        return _entry_text(entry, _INDEX_OF[id(entry)])

    candidates: list = []
    if file:
        candidates = _BY_NAME_FILE.get((lowered, file.lower()), [])
    if not candidates and scope:
        candidates = _BY_NAME_SCOPE.get((lowered, scope), [])
    if not candidates:
        # nom seul : acceptable seulement si un seul scope le porte
        seen = []
        for (name, _scope), entries in _BY_NAME_SCOPE.items():
            if name == lowered:
                seen.extend((e, _scope) for e in entries)
        scopes = {s for _e, s in seen}
        if len(scopes) == 1:
            candidates = [e for e, _s in seen]
    if not candidates:
        return None

    if context and len(candidates) > 1:
        with_ctx = [e for e in candidates if _path_matches_context(e, context)]
        if with_ctx:
            candidates = with_ctx
    if len(candidates) > 1 and not context:
        exps = {e["exp"] for e in candidates}
        if len(exps) > 1:
            # plusieurs sens possibles sans moyen de trancher : mieux vaut
            # pas d'infobulle qu'une explication potentiellement fausse
            return None
    entry = candidates[0]
    return _entry_text(entry, _INDEX_OF[id(entry)])


def entries_for_file(filename: str) -> list:
    """Toutes les entrees taggees pour ce fichier (panneau 'explication
    de ce fichier')."""
    lowered = (filename or "").lower()
    return [e for e in _PROPS if (e.get("file") or "").lower() == lowered]


def scope_for_file(filename: str) -> str:
    """Scope du glossaire le plus probable pour un nom de fichier
    (desambiguise les recherches par cle) : playfield*.yaml -> 'yaml',
    Sectors.yaml -> 'sector', gameoptions.yaml -> 'gameoptions',
    PDA.yaml -> 'pda', terrain.ecf et tout .ecf -> 'ecf',
    *.epb -> 'epb', sinon 'general'."""
    lowered = (filename or "").lower()
    if lowered.endswith(".ecf"):
        return "ecf"
    if lowered.endswith(".epb"):
        return "epb"
    if lowered.startswith("playfield"):
        return "yaml"
    if lowered == "sectors.yaml":
        return "sector"
    if lowered == "gameoptions.yaml":
        return "gameoptions"
    if lowered == "pda.yaml":
        return "pda"
    return "general"


# --- description de fichier -------------------------------------------------
def file_description(filename: str) -> "str | None":
    """Description generale d'un fichier connu du glossaire
    (playfield.yaml, Sectors.yaml, gameoptions.yaml, BlocksConfig.ecf...),
    dans la langue de l'interface. Les playfields ont des noms arbitraires :
    repli sur la cle generique 'playfield.yaml'."""
    if not filename:
        return None
    descriptions = _DATA.get("file_descriptions", {})
    desc = descriptions.get(filename)
    if not desc and filename.lower().startswith("playfield"):
        desc = descriptions.get("playfield.yaml")
    if not desc:
        return None
    if not (filename.endswith(".ecf") or filename.endswith(".yaml")):
        return desc
    if get_language_is_en():
        en = _english_file_descriptions()
        if en:
            text = (en.get(filename) or "").strip()
            if text:
                return text
    return desc


def get_language_is_en() -> bool:
    from core.i18n import get_language
    return get_language() == "en"


_EN_FILE_DESC = None


def _english_file_descriptions() -> "dict | None":
    global _EN_FILE_DESC
    if _EN_FILE_DESC is None:
        en = _english_exp_list()
        if en is None:
            _EN_FILE_DESC = {}
        else:
            try:
                data = load_json_data("propriete_glossary.en.json")
                _EN_FILE_DESC = data.get("file_descriptions") or {}
            except Exception:
                _EN_FILE_DESC = {}
    return _EN_FILE_DESC or None
