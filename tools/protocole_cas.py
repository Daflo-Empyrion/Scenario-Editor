# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# Licence GPL-3 ou superieure (voir LICENSE a la racine du depot).

"""
Point d'entree COMPATIBILITE pour les outils de developpement (tests,
lancement direct) -- les DONNEES du protocole vivent desormais dans
protocol/cases.py, embarquees dans l'application installee (le dialogue
Aide > Protocole de test les lit directement).

Ne rien ajouter ici : modifier protocol/cases.py (incrementer "rev" des
cas modifies, voir l'en-tete de celui-ci).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol.cases import (  # noqa: F401
    CASES, CATEGORIES, cases_by_category, protocol_to_markdown,
)

if __name__ == "__main__":
    grouped = cases_by_category()
    total = 0
    for code, label in CATEGORIES:
        n = len(grouped[code])
        total += n
        print(f"{label}: {n}")
    print(f"TOTAL: {total} cas")
