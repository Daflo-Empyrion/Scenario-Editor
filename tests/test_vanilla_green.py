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

"""Vert VANILLE (traduction officielle Eleon) -- retour du 19/09/2026 :
le vert avait disparu pour l'utilisateur (memoire utilisateur prioritaire
=> re-traduire un fichier donne source 'memory', et le vert n'etait pas
re-applique au rechargement du CSV). Trois briques testees ici :
vanilla_matches (conformite Eleon), source 'vanilla' quand la memoire
contient exactement la traduction officielle, et coloration des cellules
DES LE CHARGEMENT de la grille CSV. Memoire vanille isolee (JSON fabrique)
-- jamais les vrais fichiers de la machine."""

import json

import pytest

from core import settings, translation, vanilla_memory
from gui.csv_edit_widget import COLOR_VANILLA_CELL


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    import core.translation_memory as tm
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(tm, "MEMORY_FILE", tmp_path / "memory.json")
    monkeypatch.setattr(tm, "_cache", None)
    monkeypatch.setattr(vanilla_memory, "VANILLA_MEMORY_FILE",
                        tmp_path / "vanilla_memory.json")
    monkeypatch.setattr(vanilla_memory, "_cache", None)
    # NE PAS regenerer depuis le vrai jeu : _ensure_built comparerait les
    # mtimes des vrais CSV aux _sources du fichier fabrique et ECRASERAIT
    # ce dernier (vecu 19/09/2026).
    monkeypatch.setattr(vanilla_memory, "_ensure_built", lambda: True)
    # paires de test (normalisation : espaces multiples ramenees a un)
    (tmp_path / "vanilla_memory.json").write_text(json.dumps({
        "_sources": {},
        "en:fr": {
            "Coordinates:": "Coordonnées :",
            "Marker Name:": "Nom du marqueur :",
            "Hello.": "Bonjour.",
        }}), encoding="utf-8")
    settings.set_default_translation_language("fr", "Francais")


def test_vanilla_matches_exact_and_normalized():
    assert vanilla_memory.vanilla_matches("Coordinates:", "Coordonnées :")
    assert vanilla_memory.vanilla_matches("  Coordinates:  ",
                                          "Coordonnées   :")  # espaces
    assert not vanilla_memory.vanilla_matches("Coordinates:", "Autre chose")
    assert not vanilla_memory.vanilla_matches("Inconnu:", "Coordonnées :")
    assert not vanilla_memory.vanilla_matches("Coordinates:", "")
    assert not vanilla_memory.vanilla_matches("Coordinates:", "Coordonnées :",
                                              target="de")


def test_memory_hit_equal_to_vanilla_reports_vanilla(monkeypatch):
    import core.translation_memory as tm
    monkeypatch.setattr(tm, "get_cached",
                        lambda text, src, tgt: "Coordonnées :")
    trad, src = translation.translate_text_with_source("Coordinates:",
                                                       target="fr")
    assert (trad, src) == ("Coordonnées :", "vanilla")


def test_memory_hit_different_stays_memory(monkeypatch):
    """L'utilisateur a CORRIGE la traduction : sa version est prioritaire
    et n'est PAS marquee vanille (pas conforme Eleon)."""
    import core.translation_memory as tm
    monkeypatch.setattr(tm, "get_cached",
                        lambda text, src, tgt: "Coordonnées:")
    trad, src = translation.translate_text_with_source("Coordinates:",
                                                       target="fr")
    assert (trad, src) == ("Coordonnées:", "memory")


def test_no_memory_reports_vanilla(monkeypatch):
    import core.translation_memory as tm
    monkeypatch.setattr(tm, "get_cached", lambda *a, **k: None)
    trad, src = translation.translate_text_with_source("Hello.", target="fr")
    assert (trad, src) == ("Bonjour.", "vanilla")


def test_csv_grid_colors_vanilla_cells_on_load(qapp, tmp_path, monkeypatch):
    """Le vert doit etre LA au chargement du fichier (couleurs non
    persistees dans le CSV -- sinon perdu a chaque reouverture)."""
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget, COLOR_VANILLA_CELL
    apply_theme(qapp)

    path = tmp_path / "PDA.csv"
    path.write_text(
        "KEY,English,Français\r\n"
        "k1,Coordinates:,Coordonnées :\r\n"
        "k2,Hello.,Mauvaise traduction\r\n"
        "k3,Marker Name:,Nom du marqueur :\r\n"
        "k4,Only English.,\r\n",
        encoding="utf-8", newline="")

    widget = CsvEditWidget(path, editable=True)
    vanilla = widget.table.item(0, 2).background()
    assert vanilla == COLOR_VANILLA_CELL  # conforme Eleon -> vert
    assert widget.table.item(1, 2).background() != COLOR_VANILLA_CELL
    assert widget.table.item(2, 2).background() == COLOR_VANILLA_CELL
    assert widget.table.item(3, 2).background() != COLOR_VANILLA_CELL
    widget.deleteLater()


def test_csv_grid_no_vanilla_color_without_language_columns(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)

    path = tmp_path / "autre.csv"
    path.write_text("A,B\r\n1,2\r\n", encoding="utf-8", newline="")
    widget = CsvEditWidget(path, editable=True)
    # pas de colonnes English/Francais : aucune coloration vanille
    for r in range(widget.table.rowCount()):
        for c in range(widget.table.columnCount()):
            item = widget.table.item(r, c)
            if item is not None:
                assert item.background() != COLOR_VANILLA_CELL
    widget.deleteLater()
