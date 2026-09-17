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
Detection heuristique de langue (anglais vs francais) sans AUCUNE dependance
-- lexiques embarques des mots tres frequents de chaque langue.

But operationnel : apres une traduction automatique, reperer les cellules de
la colonne francaise qui contiennent ENCORE majoritairement de l'anglais
(Argos/Google recopient parfois la source, vecu sur PDA.csv Atlantis).
Les noms propres du jeu (UCH-011, Heidelberg, Zirax...) ne sont dans aucun
lexique : ils comptent neutres et diluent le score, sans fausse alerte.
"""
import re
from typing import Dict

# Mots tres frequents (short-list volontaire : suffit largement pour un
# ratio significatif sur des phrases entieres, et reste maintenable).
EN_WORDS = frozenset("""
the be to of and a in that have it for not on with he as you do at this but
his by from they we say her she or an will my one all would there their what
so up out if about who get which go me when make can like time no just him
know take people into year your good some could them see other than then now
look only come its over think also back after use two how our work first well
way even new want because any these give day most is are was were has had did
been world ship station crew planet star system fleet mission crewman spaceship
captain soldiers weapons alien aliens power energy water food oxygen fuel
damage repair build found lost dead alive kill attack defense
""".split())

FR_WORDS = frozenset("""
le la les un une des et est sont etre avoir dans pour pas sur avec que qui ce
cette ces il elle nous vous ils elles mais plus par au aux comme tout tous
leur se ne son sa ses on en y quoi dont donc alors tres aussi deja temps jour
monde peut faire dire aller voir savoir vouloir pouvoir venir trouver rester
passer donner falloir partir prendre mener bon toujours encore souvent
maintenant meme chose gens annee fois nuit rien peu autre bien premier dernier
grand petit jeune vieux nouveau vaisseau station equipe planete etoile
systeme flotte mission capitaine soldats armes alien aliens energie eau
nourriture oxygene carburant degat reparer construire trouve perdu mort vivant
attaquer defense nous vous il elle elles on qu il d l s n c m t
""".split())

_TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÖØ-öø-ÿ]{3,}", re.UNICODE)


def language_scores(text: str) -> Dict[str, float]:
    """Ratios de tokens reconnus {en, fr} sur les fragments de TEXTE LIBRE
    (balises BBCode et placeholders exclus, meme protection que la traduction).
    Les mots absents des deux lexiques (noms propres, refs du jeu) sont neutres
    et diluent les ratios."""
    from core.translation import protect_segments
    protected, _segments = protect_segments(text)
    parts = re.split(r"(XXTAG\d+XX)", protected)
    en_hits = fr_hits = total = 0
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            continue
        for token in _TOKEN_RE.findall(part):
            token = token.lower()
            total += 1
            if token in EN_WORDS:
                en_hits += 1
            elif token in FR_WORDS:
                fr_hits += 1
    if not total:
        return {"en": 0.0, "fr": 0.0}
    return {"en": en_hits / total, "fr": fr_hits / total}


def is_likely_english(text: str, min_ratio: float = 0.3, min_tokens: int = 4) -> bool:
    """Vrai si le texte ressemble a de l'anglais non traduit : assez de tokens
    recognisables (min_tokens, sinon pas d'avis sur un texte trop court) et un
    ratio anglais nettement superieur au ratio francais."""
    from core.translation import protect_segments
    tokens = _TOKEN_RE.findall(" ".join(
        p for i, p in enumerate(
            re.split(r"(XXTAG\d+XX)", protect_segments(text)[0])) if i % 2 == 0))
    if len(tokens) < min_tokens:
        return False
    scores = language_scores(text)
    return scores["en"] >= min_ratio and scores["en"] > scores["fr"]
