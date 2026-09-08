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

"""Tests GUI (offscreen) du NOUVEAU module PDA : editeur complet + assistant.
Docs = fixture reduite tests/fixtures/pda_scenario (meme principe que les
tests de l'ancien module)."""
from pathlib import Path

import pytest

from core.csv_handler import parse_csv_text
from core.pda.model import PdaModel
from core.pda.suggestions import PdaSuggestions
from core.yamllite.parser import parse_yaml_file, parse_yaml_text

PDA_YAML = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.yaml"
PDA_CSV = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.csv"


@pytest.fixture(autouse=True)
def _force_fr_labels(monkeypatch):
    """Les attentes de ce fichier sont FR (colonne 'Français' du CSV...) :
    forcer la langue (la machine de test peut etre reglee EN)."""
    import core.settings
    monkeypatch.setattr(core.settings, "get_language", lambda: "fr")


@pytest.fixture
def model():
    ydoc = parse_yaml_file(PDA_YAML)
    csv_doc = parse_csv_text(PDA_CSV.read_text(encoding="utf-8"))
    return PdaModel(ydoc, csv_doc)


@pytest.fixture
def dialog(qapp, model):
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    apply_theme(qapp)
    suggestions = PdaSuggestions(model)
    dlg = PdaEditorDialog(model, suggestions)
    yield dlg
    dlg.deleteLater()


def test_tree_populated(dialog, model):
    assert dialog.tree.topLevelItemCount() == len(model.chapters())
    # premier chapitre : au moins une tache avec actions
    first = dialog.tree.topLevelItem(0)
    assert first.childCount() >= 1


def test_select_chapter_loads_panel(dialog, model):
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
    first = model.chapters()[0]
    assert dialog.stack.currentWidget() is dialog.chapter_panel
    assert dialog.chapter_panel.entry is first
    # valeurs chargees depuis le model
    category = model.scalar(first, "Category")
    combo = dialog.chapter_panel.form._widgets["Category"][1]
    assert combo.currentText() == category


def test_chapter_field_change_applies_to_model(dialog, model):
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
    chapter = model.chapters()[0]
    old_level = model.scalar(chapter, "PlayerLevel")
    dialog.chapter_panel.form.changed.emit("PlayerLevel", "25")
    assert model.scalar(chapter, "PlayerLevel") == "25"
    assert model.scalar(chapter, "PlayerLevel") != old_level or old_level == "25"


def test_activation_swap_through_panel(dialog, model):
    """Bascule Check/Names d'une activation via le panneau chapitre -- le flux
    GUI doit produire exactement ce que les tests core garantissent."""
    chapter = model.create_chapter()
    activation = model.create_activation(chapter)
    model.set_activation_names(activation, ["AlienOutpost1"])
    dialog._reload_tree()
    dialog._select_entry(chapter)
    panel = dialog.chapter_panel
    panel._refresh_act_combo()
    panel._load_activation(0)
    # passer en Check explicite
    panel.act_form.changed.emit("Check", "DialogOption")
    assert model.activation_field(activation, "Check") == "DialogOption"
    assert model.activation_names(activation) == ["AlienOutpost1"]
    # retour implicite (Check vide -> primary Names)
    panel.act_form.changed.emit("Check", "")
    assert activation.key == "Names"
    assert model.activation_names(activation) == ["AlienOutpost1"]


def test_add_and_delete_chapter(dialog, model, monkeypatch):
    n0 = len(model.chapters())
    dialog._add_chapter()
    assert len(model.chapters()) == n0 + 1
    chapter = model.chapters()[-1]
    assert dialog.chapter_panel.entry is chapter
    monkeypatch.setattr("gui.pda.editor_dialog.ask_yes_no", lambda *a, **k: True)
    dialog._delete()
    assert len(model.chapters()) == n0


def test_add_action_to_task(dialog, model):
    first = dialog.tree.topLevelItem(0)
    task_node = first.child(0)
    dialog.tree.setCurrentItem(task_node)
    n0 = len(model.actions(model.tasks(model.chapters()[0])[0]))
    dialog._add_action()
    assert len(model.actions(model.tasks(model.chapters()[0])[0])) == n0 + 1
    # l'editeur d'action est affiche avec le check pose a la creation
    assert dialog.stack.currentWidget() is dialog.action_panel


def test_action_check_switch(dialog, model):
    action = model.actions(model.tasks(model.chapters()[0])[0])[0]
    model.set_list(action, "Names", ["ZiraxTrooper"])
    model.set_scalar(action, "Check", "SubjectKilled")
    dialog._reload_tree()
    dialog._select_entry(action)
    assert dialog.stack.currentWidget() is dialog.action_panel
    # changer le type : la cle Check est mise a jour dans le model
    dialog.action_panel.check_combo.setCurrentText("NearPoi")
    assert model.action_check(action) == "NearPoi"


def test_render_stays_parseable_after_edits(dialog, model):
    dialog._add_chapter()
    chapter = model.chapters()[-1]
    dialog.chapter_panel.form.changed.emit("Description", "pda_EDITED1")
    doc2 = parse_yaml_text(model.yaml_doc.render())
    m2 = PdaModel(doc2, model.csv_doc)
    assert m2.scalar(m2.chapters()[-1], "Description") == "pda_EDITED1"


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------
def test_wizard_creates_chapter(qapp, model, monkeypatch):
    from gui.theme import apply_theme
    from gui.pda.create_wizard import CreateWizard
    apply_theme(qapp)
    suggestions = PdaSuggestions(model)
    wizard = CreateWizard(model, suggestions)
    wizard._go(1)
    wizard._add_action_editor()  # WaitAction par defaut
    editor = wizard._action_editors[0]
    editor.form.changed.emit("Amount", "42")
    wizard._go(2)
    # titre : on impose le jeton sans passer par la saisie clavier
    wizard.title_field.set_token("")
    wizard.title_field.token = "pda_WIZTITL"
    wizard._on_create()
    assert wizard.created_chapter is not None
    chapter = model.chapters()[-1]
    assert chapter is wizard.created_chapter
    assert model.scalar(chapter, "Description") == "pda_WIZTITL"
    task = model.tasks(chapter)[0]
    action = model.actions(task)[0]
    assert model.action_check(action) == "WaitAction"
    assert model.scalar(action, "Amount") == "42"
    # re-parse : tout est relisible
    doc2 = parse_yaml_text(model.yaml_doc.render())
    m2 = PdaModel(doc2, model.csv_doc)
    assert m2.action_check(m2.actions(m2.tasks(m2.chapters()[-1])[0])[0]) == "WaitAction"


def test_wizard_requires_title(qapp, model, monkeypatch):
    from gui.theme import apply_theme
    from gui.pda.create_wizard import CreateWizard
    apply_theme(qapp)
    wizard = CreateWizard(model, PdaSuggestions(model))
    wizard.title_field.set_token("")
    n0 = len(model.chapters())
    from PyQt6.QtWidgets import QMessageBox
    called = {"warning": False}

    def fake_warning(*a, **k):
        called["warning"] = True
        return QMessageBox.StandardButton.Ok
    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    wizard._go(2)
    wizard._on_create()
    assert called["warning"] is True
    assert len(model.chapters()) == n0  # rien de cree


# ---------------------------------------------------------------------------
# Prefixes de format ('mbox;20|pda_XXX') dans les champs de texte localise --
# confirmes sur les vrais fichiers (StartMessage: mbox;20|pda_mKuKK...)
# ---------------------------------------------------------------------------
def test_token_field_resolves_prefixed_value(qapp, model):
    from gui.theme import apply_theme
    from gui.pda.widgets import TokenTextField
    apply_theme(qapp)
    model.set_csv_text("pda_PrefMsg", "Message boite", "English")
    field = TokenTextField(model)
    field.set_token("mbox;20|pda_PrefMsg")
    assert field.edit.text() == "Message boite"
    assert field.state_label.text().startswith("✔")  # resolu, pas d'avertissement
    assert field.value() == "mbox;20|pda_PrefMsg"    # prefixe preserve au save


def test_token_field_edits_prefixed_value(qapp, model):
    from gui.theme import apply_theme
    from gui.pda.widgets import TokenTextField
    apply_theme(qapp)
    model.set_csv_text("pda_PrefMsg", "Message boite", "English")
    field = TokenTextField(model)
    field.set_token("mbox;20|pda_PrefMsg")
    field.edit.setText("")
    field._on_text_edited("")
    assert field.value() == ""  # champ vide -> cle retiree au save
    field.edit.setText("Nouveau message")
    field._on_text_edited("Nouveau message")
    written = field.value()
    assert written.startswith("mbox;20|")  # le prefixe est PRESERVE a l'edition
    token = written.split("|", 1)[1]
    # le texte saisi atterrit dans la colonne de reference (langue de l'appli)
    from gui.pda.widgets import _reference_column
    assert model.csv_text(token, _reference_column()) == "Nouveau message"


def test_token_field_keeps_raw_text_untouched(qapp, model):
    """Une valeur YAML non jeton (texte brut) reste intacte tant que le champ
    n'est pas edite -- le save() ne doit jamais l'effacer ni la re-tokeniser."""
    from gui.theme import apply_theme
    from gui.pda.widgets import TokenTextField
    apply_theme(qapp)
    field = TokenTextField(model)
    field.set_token("Message brut sans jeton")
    assert field.edit.text() == "Message brut sans jeton"
    assert field.value() == "Message brut sans jeton"


# ---------------------------------------------------------------------------
# Annuler (snapshots), non-ecriture parasite et journal de session --
# retour utilisateur du 31/08/2026
# ---------------------------------------------------------------------------
def test_undo_restores_previous_state(qapp, model):
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    apply_theme(qapp)
    dlg = PdaEditorDialog(model, PdaSuggestions(model))
    dlg._select_entry(model.chapters()[0])
    dlg.chapter_panel.form.changed.emit("PlayerLevel", "42")
    assert model.scalar(model.chapters()[0], "PlayerLevel") == "42"
    assert dlg.btn_undo.isEnabled()
    dlg._undo()
    assert model.scalar(model.chapters()[0], "PlayerLevel") == "1"
    # l'entree selectionnee apres undo est rechargée (meme jeton de titre)
    assert dlg.stack.currentWidget() is dlg.chapter_panel
    assert not dlg.btn_undo.isEnabled() or dlg._undo_stack


def test_save_does_not_write_unchanged_values(qapp, model):
    """Deux save() successifs sans modification : aucun champ ne doit etre
    reecrit (le journal reste vide et le document non pollue)."""
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    apply_theme(qapp)
    dlg = PdaEditorDialog(model, PdaSuggestions(model))
    dlg._select_entry(model.chapters()[0])
    dlg.chapter_panel.save()
    dlg.chapter_panel.save()
    assert dlg.chapter_panel.entry is model.chapters()[0]
    assert model.take_touched_csv_tokens() == set()
    assert dlg._touched_fields == {}


def test_structural_ops_are_logged_and_undoable(qapp, model):
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    apply_theme(qapp)
    dlg = PdaEditorDialog(model, PdaSuggestions(model))
    n0 = len(model.chapters())
    dlg._add_chapter()
    assert len(model.chapters()) == n0 + 1
    assert dlg._session_log
    dlg._undo()
    assert len(model.chapters()) == n0


def test_resume_banner_shows_history(qapp, model, tmp_path, monkeypatch):
    from core.pda import history as hist
    monkeypatch.setattr(hist, "HISTORY_FILE", tmp_path / "pda_history.json")
    hist.append_history("C:/mon/scenario", ["Modifié « Mission X » : Description"])
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    apply_theme(qapp)
    dlg = PdaEditorDialog(model, PdaSuggestions(model), scenario_key="C:/mon/scenario")
    from PyQt6.QtWidgets import QLabel
    banner = [dlg.layout().itemAt(i).widget() for i in range(dlg.layout().count())
              if dlg.layout().itemAt(i).widget() and isinstance(dlg.layout().itemAt(i).widget(), QLabel)]
    assert banner, "le bandeau de reprise doit exister"
    assert "Mission X" in banner[0].text()


def test_flush_history_on_close(qapp, model, tmp_path, monkeypatch):
    from core.pda import history as hist
    monkeypatch.setattr(hist, "HISTORY_FILE", tmp_path / "pda_history.json")
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    apply_theme(qapp)
    dlg = PdaEditorDialog(model, PdaSuggestions(model), scenario_key="C:/mon/scenario")
    dlg._select_entry(model.chapters()[0])
    dlg.chapter_panel.form.changed.emit("PlayerLevel", "33")
    dlg.done(0)
    entries = hist.read_history("C:/mon/scenario")
    assert entries and "PlayerLevel" in entries[0]["label"]


# ---------------------------------------------------------------------------
# CONTROLE COMPLET (retour utilisateur du 31/08/2026) : "tout s'affiche bien
# dans l'editeur apres avoir cree une mission" + titres editables
# ---------------------------------------------------------------------------
def test_wizard_mission_shows_everything_in_editor(qapp, model):
    """Bout-en-bout : mission creee via l'assistant -> CHAQUE element saisi
    doit se retrouver affiche dans le panneau correspondant de l'editeur,
    y compris le TITRE du chapitre (il n'etait jamais propose avant)."""
    from gui.theme import apply_theme
    from gui.pda.create_wizard import CreateWizard
    apply_theme(qapp)
    wizard = CreateWizard(model, PdaSuggestions(model))
    # etape 1 : categorie + niveau
    wizard.category_combo.setCurrentText("Tutorial")
    wizard.level_spin.setValue(25)
    # etape 2 : une action SubjectKilled
    wizard._go(1)
    wizard._add_action_editor()
    editor = wizard._action_editors[0]
    editor.check_combo.setCurrentText("SubjectKilled")
    editor.form.changed.emit("Names", ["ZiraxTrooper", "DroneTier1"])
    editor.form.changed.emit("Amount", "42")
    # etape 3 : titres, description, recompense
    wizard._go(2)
    wizard.title_field.set_token("")
    wizard.title_field.token = "pda_TITRE01"
    wizard.title_field.edit.setText("La mission de test")
    wizard.title_field._on_text_edited("La mission de test")
    wizard.desc_field.set_token("")
    wizard.desc_field.token = "pda_DESCR01"
    wizard.desc_field.edit.setText("Une belle description")
    wizard.desc_field._on_text_edited("Une belle description")
    wizard.rewards.add_row()
    wizard.rewards.rows_layout.itemAt(0).widget()._fields[0].setCurrentText("XP")
    wizard.rewards.rows_layout.itemAt(0).widget()._fields[2].setValue(5000)
    wizard._on_create()
    assert wizard.created_chapter is not None

    # ---- dans l'editeur : le chapitre
    from gui.pda.editor_dialog import PdaEditorDialog
    dlg = PdaEditorDialog(model, PdaSuggestions(model))
    dlg._select_entry(wizard.created_chapter)
    assert dlg.stack.currentWidget() is dlg.chapter_panel
    panel = dlg.chapter_panel
    # TITRE : propose ET modifiable
    assert panel.title_field.edit.text() == "La mission de test"
    cat_widget = panel.form._widgets["Category"][1]
    assert cat_widget.currentText() == "Tutorial"
    assert panel.form._widgets["PlayerLevel"][1].value() == 25
    assert panel.title_field.value() == "pda_TITRE01"
    # modifier le titre depuis le panneau : le jeton est CONSERVE (pas de cle
    # orpheline dans le CSV), seul le texte change
    panel.title_field.edit.setText("Nouveau titre")
    panel.title_field._on_text_edited("Nouveau titre")
    assert model.chapter_title_token(wizard.created_chapter) == "pda_TITRE01"
    assert model.csv_text("pda_TITRE01", "Français") == "Nouveau titre"

    # ---- la tache : titre affiche (jeton PARTAGE avec le chapitre : le
    # texte edite ci-dessus se retrouve ici, comme dans les vrais fichiers)
    task = model.tasks(wizard.created_chapter)[0]
    dlg._select_entry(task)
    assert dlg.stack.currentWidget() is dlg.task_panel
    assert dlg.task_panel.title_field.edit.text() == "Nouveau titre"

    # ---- l'action : type, cibles, quantite affiches ; son ActionTitle a son
    # PROPRE jeton (pose par create_action) : le repli affiche le jeton brut,
    # renommable via le champ titre (meme discipline que le chapitre)
    action = model.actions(task)[0]
    dlg._select_entry(action)
    assert dlg.stack.currentWidget() is dlg.action_panel
    assert dlg.action_panel.title_field.edit.text() == model.actions(task)[0].value
    assert dlg.action_panel.check_combo.currentText() == "SubjectKilled"
    assert dlg.action_panel.form._widgets["Amount"][1].value() == 42
    names_widget = dlg.action_panel.form._widgets["Names"][1]
    assert names_widget.values() == ["ZiraxTrooper", "DroneTier1"]


RICH_YAML = """Chapters:
  - ChapterTitle: pda_RICH001
    Category: FactionMission
    NoSkip: 'true'
    Activatable: Always
    Visibility: WhileCompleted
    PlayerLevel: 10
    Group: Groupe A
    Description: pda_RICHD
    CompletedMessage: mbox;20|pda_RICHM
    Faction: Talon
    ReputationLevel: 3
    PictureFile: photo.jpg
    PlayfieldTypes:
      - Orbit
    VisibleOnStartPlayfieldTypes:
      - StartPlanet
    Playfields:
      - Akua
    Tasks:
      - TaskTitle: pda_RICHT
        StartDelay: 5
        HasUniqueItems: 'true'
        Headline: pda_RICHHL
        OnCompletePdaDataOps:
          - Key: someData
        OnCompletePlayfieldOps:
          - Key: other
        OnCompletePlayerOps:
          - Key: third
        OnActivateSignal: SIG1
        OnCompleteSignal: SIG2
        RewardedTasks:
          - pda_OTHERT
        Actions:
          - ActionTitle: pda_RICHA
            Description: pda_RICHA
            Check: NearPoi
            Names:
              - AlienOutpost1
            TriggerDistance: 80
            OnCompleteSignal: ACTSIG
Creator: "Test"
"""


def test_every_key_of_rich_file_is_visible(qapp):
    """EXHAUSTIVITE : un chapitre/tache/action reellement riches ne laissent
    AUCUNE cle invisible -- les scalaires/listes sont dans le formulaire, les
    sections complexes apparaissent en 'Avance (lecture seule)'."""
    from gui.theme import apply_theme
    from gui.pda.editor_dialog import PdaEditorDialog
    apply_theme(qapp)
    ydoc = parse_yaml_text(RICH_YAML)
    from tests.test_pda_model import MINI_CSV
    m = PdaModel(ydoc, parse_csv_text(MINI_CSV))
    dlg = PdaEditorDialog(m, PdaSuggestions(m))

    # chapitre : tout est couvert, section avancee VIDE
    dlg._select_entry(m.chapters()[0])
    ch = m.chapters()[0]
    from core.yamllite.model import YamlEntry
    all_keys = {c.key for c in ch.children if isinstance(c, YamlEntry) and c.key}
    from core.pda.schema import CHAPTER_FIELDS, CHAPTER_STRUCTURE_KEYS
    covered = {s.key for s in CHAPTER_FIELDS} | set(CHAPTER_STRUCTURE_KEYS) | {"ChapterTitle"}
    assert all_keys <= covered, all_keys - covered
    assert not dlg.chapter_panel.advanced_label.text()

    # tache : les Ops sortent en section avancee, Rien d'autre
    task = m.tasks(ch)[0]
    dlg._select_entry(task)
    task_keys = {c.key for c in task.children if isinstance(c, YamlEntry) and c.key}
    from core.pda.schema import TASK_FIELDS, TASK_STRUCTURE_KEYS, TASK_ADVANCED_KEYS
    t_covered = {s.key for s in TASK_FIELDS} | set(TASK_STRUCTURE_KEYS) | {"TaskTitle"}
    assert task_keys <= t_covered | set(TASK_ADVANCED_KEYS), task_keys - (t_covered | set(TASK_ADVANCED_KEYS))
    advanced = dlg.task_panel.advanced_label.text()
    for op in ("OnCompletePdaDataOps", "OnCompletePlayfieldOps", "OnCompletePlayerOps"):
        assert op in advanced, op
    assert "Headline" not in advanced  # les champs de formulaire n'y sont JAMAIS
    # titres + signaux visibles
    assert dlg.task_panel.title_field.edit.text()  # jeton resolu (vide ici) -> pas de plantage
    assert dlg.task_panel.form._widgets["OnActivateSignal"][1].text() == "SIG1"

    # action : OnCompleteSignal hors schéma visible en avance
    action = m.actions(task)[0]
    dlg._select_entry(action)
    assert "OnCompleteSignal" in dlg.action_panel.advanced_label.text()
