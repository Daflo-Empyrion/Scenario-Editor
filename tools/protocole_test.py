# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# Licence GPL-3 ou superieure (voir LICENSE a la racine du depot).

"""
Point d'entree COMPATIBILITE developpement -- le RUNNER pas-a-pas vit
desormais dans gui/test_protocol_runner.py (embarque dans l'application
installee, lance depuis Aide > Protocole de test).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.test_protocol_runner import main

if __name__ == "__main__":
    main()
