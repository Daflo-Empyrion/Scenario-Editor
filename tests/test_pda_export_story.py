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

"""Export Markdown de l'histoire PDA (core/pda/export_story.py) : contenu
des chapitres/taches/actions avec textes CSV de la colonne demandee, jeton
brut en repli."""

MINI_YAML = """Chapters:
  - ChapterTitle: pda_Aa1Bb2C
    Description: pda_Dd4Ee5F
    Tasks:
      - TaskTitle: pda_Gg7Hh8I
        Actions:
          - ActionTitle: pda_Jj9Kk0L
            Description: pda_Jj9Kk0L
            Check: SubjectKilled
            Amount: 10
Creator: "Test"
"""

MINI_CSV = """KEY,English,Français
pda_Aa1Bb2C,First chapter,Premier chapitre
pda_Dd4Ee5F,Story text,Texte d'histoire
pda_Gg7Hh8I,Task one,Tache une
pda_Jj9Kk0L,Kill them,Tuez-les
"""


def _model():
    from core.yamllite.parser import parse_yaml_text
    from core.csv_handler import parse_csv_text
    from core.pda.model import PdaModel
    return PdaModel(parse_yaml_text(MINI_YAML), parse_csv_text(MINI_CSV))


def test_export_markdown_fr_column():
    from core.pda.export_story import export_markdown
    md = export_markdown(_model(), column="Français")
    assert "## 1. Premier chapitre" in md
    assert "Texte d'histoire" in md
    assert "### 1.1 Tache une" in md
    assert "**Tuez-les** — `SubjectKilled`" in md
    assert "pda_" not in md  # tous les jetons resolvables


def test_export_markdown_falls_back_to_raw_token():
    from core.pda.export_story import export_markdown
    m = _model()
    md = export_markdown(m, column="English")
    assert "First chapter" in md
    # une colonne absente du CSV -> jetons bruts, jamais de crash
    md2 = export_markdown(m, column="Español")
    assert "pda_Aa1Bb2C" in md2


def test_export_markdown_empty_pda():
    from core.yamllite.parser import parse_yaml_text
    from core.csv_handler import parse_csv_text
    from core.pda.model import PdaModel
    from core.pda.export_story import export_markdown
    m = PdaModel(parse_yaml_text("Creator: \"Test\"\n"), parse_csv_text("KEY,English\n"))
    assert export_markdown(m).startswith("# PDA")


def test_editor_dialog_export_button_writes_file(qapp, monkeypatch, tmp_path):
    """Chemin connecte : le bouton de l'editeur ecrit reellement le fichier
    (regle projet — un slot route via un tuple avale un TypeError en natif)."""
    from pathlib import Path
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    from core.pda.model import PdaModel
    from core.pda.suggestions import PdaSuggestions
    from core.yamllite.parser import parse_yaml_file
    from core.csv_handler import parse_csv_text
    apply_theme(qapp)
    fixture = Path(__file__).parent / "fixtures" / "pda_scenario"
    m = PdaModel(parse_yaml_file(fixture / "PDA.yaml"),
                 parse_csv_text((fixture / "PDA.csv").read_text(encoding="utf-8")))
    import core.settings
    monkeypatch.setattr(core.settings, "get_language", lambda: "fr")
    dlg = PdaEditorDialog(m, PdaSuggestions(m))
    dest = tmp_path / "histoire.md"
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(dest), "Markdown (*.md)"))
    monkeypatch.setattr("gui.pda.editor_dialog.QMessageBox.information",
                        lambda *a, **k: None)
    dlg.btn_export_md.click()
    assert dest.exists()
    assert "PDA" in dest.read_text(encoding="utf-8")
    dlg.deleteLater()
