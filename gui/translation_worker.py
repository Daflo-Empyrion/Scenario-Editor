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
Worker de traduction en lot pour l'interface : traduit une liste de textes dans
un thread d'arriere-plan (QThread) au lieu d'une boucle synchrone sur le thread
de l'interface -- l'ancienne approche (processEvents a chaque cellule) gelait
l'interface pendant CHAQUE requete Google (jusqu'au timeout, cf.
core/translation.py) et autorisait une reentrance delicate (l'utilisateur pouvait
cliquer ailleurs pendant la boucle).

Contrat :
- Le thread appelant construit le worker avec la liste des textes, connecte les
  signaux, garde une reference (sinon le garbage collector tue le QThread en
  plein vol), puis start().
- item_done est emis par traduction : (index dans la liste, traduction, erreur) --
  erreur est une chaine vide si la traduction a reussi. Les signaux emis depuis
  un thread non-GUI sont automatiquement mis en file vers le thread du recepteur
  (connexion queued), donc les slots s'executent cote interface, sans verrou.
- stop() est pris en compte ENTRE deux textes (pas au milieu d'une requete --
  chaque requete reste bornee par le timeout de core/translation.py).
- finished_all est emis dans tous les cas (liste terminee ou arret demande) :
  c'est le signal de fin pour fermer la barre de progression et afficher la revue.
"""
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from core import translation


class BatchTranslationWorker(QThread):
    progress = pyqtSignal(int, int)        # (index_en_cours, total) -- avant chaque texte
    # (index, traduction, message_erreur_vide_si_ok, source : memory/vanilla/engine)
    item_done = pyqtSignal(int, str, str, str)
    finished_all = pyqtSignal()

    def __init__(self, texts: List[str], target_code: str, parent=None,
                 autofix: bool = False):
        super().__init__(parent)
        self._texts = texts
        self._target = target_code
        self._autofix = autofix   # correction Grammalecte de chaque traduction
        self._stop_requested = False

    def stop(self) -> None:
        """Demande l'arret apres le texte en cours (jamais au milieu d'une
        requete -- chaque appel reste borne par le timeout de translate_text)."""
        self._stop_requested = True

    def run(self) -> None:
        total = len(self._texts)
        spellcheck = None
        if self._autofix:
            from core import spellcheck as _sp
            if _sp.is_available():
                spellcheck = _sp
        for i, text in enumerate(self._texts):
            if self._stop_requested:
                break
            self.progress.emit(i, total)
            try:
                # Source suit la traduction ('vanilla' = localisation officielle
                # Eleon, coloree dans la revue) ; pas de store automatique :
                # la memoire est alimentee a la VALIDATION (12/09/2026).
                translated, src = translation.translate_text_with_source(
                    text, target=self._target)
                if spellcheck is not None and translated:
                    # correction grammaticale DANS le thread (jamais de gel
                    # interface) -- la revue affiche la version corrigee
                    translated, _applied = spellcheck.auto_fix(translated)
                self.item_done.emit(i, translated, "", src)
            except Exception as e:
                self.item_done.emit(i, "", str(e), "")
        self.finished_all.emit()
