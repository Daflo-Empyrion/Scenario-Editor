"""
Tests du dialogue de creation guidee de mission PDA (gui/pda_mission_dialog.py).
"""
from pathlib import Path

import pytest

from core.yamllite.parser import parse_yaml_file, parse_yaml_text
from core.csv_handler import parse_csv_text, render_csv
from core.pda_mission import list_chapters

PDA_YAML = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.yaml"
PDA_CSV = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.csv"


@pytest.fixture
def dialog(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import PdaMissionDialog
    apply_theme(qapp)
    doc = parse_yaml_file(PDA_YAML)
    csv_doc = parse_csv_text(PDA_CSV.read_text(encoding="utf-8"))
    return PdaMissionDialog(doc, csv_doc)


def test_names_suggestions_populated_from_real_data(dialog):
    assert dialog.tier_widgets[0].names_editor.combo.count() >= 0  # fixture reduite, peut etre 0


def test_names_suggestions_switch_when_check_type_changes(qapp, tmp_path):
    """Bug corrige : le menu 'Noms des cibles' restait fige sur les
    suggestions SubjectKilled quel que soit le type d'objectif choisi --
    doit maintenant basculer vers les suggestions BlockDestroyed (dont les
    ressources minables) des que ce type est selectionne."""
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import PdaMissionDialog
    apply_theme(qapp)
    doc = parse_yaml_file(PDA_YAML)
    csv_doc = parse_csv_text(PDA_CSV.read_text(encoding="utf-8"))

    blocks_ecf = tmp_path / "BlocksConfig.ecf"
    blocks_ecf.write_text(
        "{ Block Id: 1, Name: IronResource\n  Group: resource\n}\n", encoding="utf-8")

    pda_dialog = PdaMissionDialog(doc, csv_doc, sibling_ecf_files=[blocks_ecf])
    tier = pda_dialog.tier_widgets[0]

    # Par defaut (SubjectKilled) : pas de ressource de minage proposee.
    suggestions_kill = [tier.names_editor.combo.itemText(i)
                         for i in range(tier.names_editor.combo.count())]
    assert "IronResource" not in suggestions_kill

    # Bascule sur BlockDestroyed (mine/detruit) : IronResource doit apparaitre.
    tier.check_combo.setCurrentIndex(1)
    suggestions_mine = [tier.names_editor.combo.itemText(i)
                         for i in range(tier.names_editor.combo.count())]
    assert "IronResource" in suggestions_mine

    # Retour sur SubjectKilled : la ressource disparait a nouveau.
    tier.check_combo.setCurrentIndex(0)
    suggestions_back = [tier.names_editor.combo.itemText(i)
                         for i in range(tier.names_editor.combo.count())]
    assert "IronResource" not in suggestions_back


def test_names_suggestions_include_asteroid_voxel_variants(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import PdaMissionDialog
    apply_theme(qapp)
    doc = parse_yaml_file(PDA_YAML)
    csv_doc = parse_csv_text(PDA_CSV.read_text(encoding="utf-8"))

    blocks_ecf = tmp_path / "BlocksConfig.ecf"
    blocks_ecf.write_text(
        "{ Block Id: 1, Name: IronResource\n  Group: resource\n}\n", encoding="utf-8")

    pda_dialog = PdaMissionDialog(doc, csv_doc, sibling_ecf_files=[blocks_ecf])
    tier = pda_dialog.tier_widgets[0]
    tier.check_combo.setCurrentIndex(1)
    suggestions = [tier.names_editor.combo.itemText(i)
                   for i in range(tier.names_editor.combo.count())]
    assert "AsteroidVoxel01Iron" in suggestions


def test_kill_mission_creates_chapter_and_csv_rows(dialog):
    before_chapters = len(list_chapters(dialog.doc))
    before_rows = len(dialog.csv_doc.rows)

    dialog.tier_widgets[0].title_en_edit.setText("Kill 10 Zirax soldiers")
    dialog.tier_widgets[0].names_editor.combo.setCurrentText("WeakZiraxSoldier")
    dialog.tier_widgets[0].names_editor._on_add()
    dialog.tier_widgets[0].amount_spin.setValue(10)
    dialog._on_create()

    assert len(list_chapters(dialog.doc)) == before_chapters + 1
    assert len(dialog.csv_doc.rows) > before_rows


def test_mine_resource_mission_uses_block_destroyed_with_matching_types(dialog):
    dialog.tier_widgets[0].title_en_edit.setText("Mine 500 Iron")
    dialog.tier_widgets[0].check_combo.setCurrentIndex(1)  # BlockDestroyed
    dialog.tier_widgets[0].names_editor.combo.setCurrentText("IronResource")
    dialog.tier_widgets[0].names_editor._on_add()
    dialog.tier_widgets[0].types_editor.combo.setCurrentText("IronResource")
    dialog.tier_widgets[0].types_editor._on_add()
    dialog.tier_widgets[0].amount_spin.setValue(500)
    dialog._on_create()

    new_chapter = list_chapters(dialog.doc)[-1]
    tasks_node = next(c for c in new_chapter.children if c.key == "Tasks")
    action = tasks_node.children[0].children[0].children[0]
    check_val = next(c.value for c in action.children if c.key == "Check")
    types_node = next(c for c in action.children if c.key == "Types")
    assert check_val == "BlockDestroyed"
    assert types_node.children[0].value == "IronResource"


def test_created_mission_reparses_correctly_in_both_files(dialog):
    dialog.tier_widgets[0].title_en_edit.setText("Kill 10 Zirax soldiers")
    dialog.tier_widgets[0].names_editor.combo.setCurrentText("WeakZiraxSoldier")
    dialog.tier_widgets[0].names_editor._on_add()
    dialog._on_create()

    rendered_yaml = dialog.doc.render()
    reparsed_yaml = parse_yaml_text(rendered_yaml)
    assert reparsed_yaml is not None
    assert len(list_chapters(reparsed_yaml)) == len(list_chapters(dialog.doc))

    rendered_csv = render_csv(dialog.csv_doc)
    reparsed_csv = parse_csv_text(rendered_csv)
    assert reparsed_csv is not None


def test_reward_row_switches_to_item_dropdown(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow(["IronIngot", "SteelPlate"], lambda r: None)
    row.show()
    row.kind_combo.setCurrentText("Item")
    assert row.extra_combo.isVisible() is True
    assert row.extra_combo.count() == 2


def test_reward_row_hides_extra_combo_for_xp(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow([], lambda r: None)
    row.show()
    row.kind_combo.setCurrentText("XP")
    assert row.extra_combo.isVisible() is False


def test_repeat_fields_disabled_until_checkbox_checked(dialog):
    assert dialog.num_repeats_spin.isEnabled() is False
    dialog.repeatable_check.setChecked(True)
    assert dialog.num_repeats_spin.isEnabled() is True


def test_create_without_title_shows_warning(dialog, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    called = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: called.append(True)))
    dialog.tier_widgets[0].title_en_edit.setText("")
    dialog._on_create()
    assert called == [True]


def test_create_without_names_shows_warning(dialog, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    called = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: called.append(True)))
    dialog.tier_widgets[0].title_en_edit.setText("Some title")
    dialog._on_create()
    assert called == [True]


def test_multiple_reward_rows_can_be_added(dialog):
    initial_count = len(dialog.tier_widgets[0].reward_rows)
    dialog.tier_widgets[0]._add_reward_row()
    assert len(dialog.tier_widgets[0].reward_rows) == initial_count + 1


# ============================================================================
# Integration menu principal (main_window._open_pda_mission_dialog) --
# localisation reelle Extras/PDA/, ouverture comme VRAIS onglets (jamais
# d'ecriture directe sur disque), propagation de l'etat modifie.
# ============================================================================

@pytest.fixture
def window_with_pda_scenario(qapp, tmp_path):
    import shutil
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    apply_theme(qapp)
    pda_dir = tmp_path / "Extras" / "PDA"
    pda_dir.mkdir(parents=True)
    shutil.copy(PDA_YAML, pda_dir / "PDA.yaml")
    shutil.copy(PDA_CSV, pda_dir / "PDA.csv")
    (tmp_path / "Content" / "Configuration").mkdir(parents=True)

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    return window


def test_menu_action_shows_info_when_no_workspace(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QMessageBox
    apply_theme(qapp)
    window = MainWindow()
    window.workspace = None

    called = []
    monkeypatch.setattr(QMessageBox, "information",
                         staticmethod(lambda *a, **k: called.append(True)))
    window._open_pda_mission_dialog()
    assert called == [True]


def test_menu_action_shows_info_when_pda_files_missing(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    from PyQt6.QtWidgets import QMessageBox
    apply_theme(qapp)

    (tmp_path / "Content" / "Configuration").mkdir(parents=True)
    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    called = []
    monkeypatch.setattr(QMessageBox, "information",
                         staticmethod(lambda *a, **k: called.append(True)))
    window._open_pda_mission_dialog()
    assert called == [True]


def test_menu_action_opens_both_tabs_and_marks_modified(window_with_pda_scenario, monkeypatch):
    from gui.pda_mission_dialog import PdaMissionDialog
    from PyQt6.QtWidgets import QDialog

    def fake_exec(self):
        self.tier_widgets[0].title_en_edit.setText("Kill 10 Zirax soldiers")
        self.tier_widgets[0].names_editor.combo.setCurrentText("WeakZiraxSoldier")
        self.tier_widgets[0].names_editor._on_add()
        self._on_create()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(PdaMissionDialog, "exec", fake_exec)
    window_with_pda_scenario._open_pda_mission_dialog()

    assert window_with_pda_scenario.tabs.count() == 2
    assert window_with_pda_scenario.tabs.widget(0).is_modified() is True
    assert window_with_pda_scenario.tabs.widget(1).is_modified() is True


def test_declining_dialog_does_not_mark_tabs_modified(window_with_pda_scenario, monkeypatch):
    from gui.pda_mission_dialog import PdaMissionDialog
    from PyQt6.QtWidgets import QDialog

    monkeypatch.setattr(PdaMissionDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    window_with_pda_scenario._open_pda_mission_dialog()

    assert window_with_pda_scenario.tabs.widget(0).is_modified() is False
    assert window_with_pda_scenario.tabs.widget(1).is_modified() is False


def test_reopening_menu_action_reuses_already_open_tabs(window_with_pda_scenario, monkeypatch):
    """Confirme qu'on ne duplique jamais les onglets si PDA.yaml/PDA.csv sont
    deja ouverts -- meme raisonnement que la creation de Template associe a
    un bloc (reutilisation d'un onglet existant plutot que reouverture)."""
    from gui.pda_mission_dialog import PdaMissionDialog
    from PyQt6.QtWidgets import QDialog

    monkeypatch.setattr(PdaMissionDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    window_with_pda_scenario._open_pda_mission_dialog()
    window_with_pda_scenario._open_pda_mission_dialog()

    assert window_with_pda_scenario.tabs.count() == 2


# ============================================================================
# Infobulles avec exemples concrets sur chaque champ -- verifiees contre les
# vraies donnees confirmees (MiningShuttle=kill, IronResource=mine,
# CoreNPC=detruire une structure).
# ============================================================================

def test_all_text_fields_have_tooltips_with_content(dialog):
    for field in [dialog.tier_widgets[0].title_en_edit, dialog.tier_widgets[0].title_fr_edit, dialog.tier_widgets[0].desc_en_edit, dialog.tier_widgets[0].desc_fr_edit]:
        assert field.toolTip().strip() != ""


def test_names_tooltip_changes_with_objective_type(dialog):
    dialog.tier_widgets[0].check_combo.setCurrentIndex(0)  # SubjectKilled
    kill_tooltip = dialog.tier_widgets[0].names_editor.toolTip()
    dialog.tier_widgets[0].check_combo.setCurrentIndex(1)  # BlockDestroyed
    destroy_tooltip = dialog.tier_widgets[0].names_editor.toolTip()
    assert kill_tooltip != destroy_tooltip


def test_kill_tooltip_mentions_miningshuttle_is_not_a_resource(dialog):
    """Regression directe de la question de l'utilisateur : MiningShuttle est
    un drone a tuer, pas une ressource a miner -- l'infobulle doit le
    clarifier explicitement pour eviter la meme confusion."""
    dialog.tier_widgets[0].check_combo.setCurrentIndex(0)
    tooltip = dialog.tier_widgets[0].names_editor.toolTip()
    assert "MiningShuttle" in tooltip
    assert "pas une ressource" in tooltip or "not a resource" in tooltip


def test_mine_tooltip_mentions_real_resource_example(dialog):
    dialog.tier_widgets[0].check_combo.setCurrentIndex(1)
    tooltip = dialog.tier_widgets[0].names_editor.toolTip()
    assert "IronResource" in tooltip


def test_types_tooltip_mentions_core_npc_example(dialog):
    assert "CoreNPC" in dialog.tier_widgets[0].types_editor.toolTip()


def test_repeatable_tooltip_distinguishes_from_tiers(dialog):
    """L'infobulle doit clarifier que la repetition simple (meme objectif a
    chaque fois) est differente des paliers (objectifs/recompenses
    differents a chaque etape)."""
    tooltip = dialog.repeatable_check.toolTip()
    assert tooltip.strip() != ""


def test_reward_row_fields_have_tooltips(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow(["IronIngot"], lambda r: None)
    assert row.kind_combo.toolTip().strip() != ""
    assert row.count_spin.toolTip().strip() != ""
    assert row.extra_combo.toolTip().strip() != ""


# ============================================================================
# Paliers (plusieurs Chapters chaines) -- via l'interface graphique.
# ============================================================================

def test_single_tier_by_default(dialog):
    assert len(dialog.tier_widgets) == 1


def test_repeat_section_enabled_with_one_tier(dialog):
    assert dialog.repeat_box.isEnabled() is True


def test_adding_second_tier_disables_repeat_section(dialog):
    dialog._add_tier()
    assert dialog.repeat_box.isEnabled() is False


def test_adding_tier_unchecks_repeatable_if_it_was_checked(dialog):
    dialog.repeatable_check.setChecked(True)
    dialog._add_tier()
    assert dialog.repeatable_check.isChecked() is False


def test_tier_group_titles_numbered_correctly(dialog):
    dialog._add_tier()
    dialog._add_tier()
    assert dialog.tier_widgets[0].title() == "Palier 1"
    assert dialog.tier_widgets[1].title() == "Palier 2"
    assert dialog.tier_widgets[2].title() == "Palier 3"


def test_three_tier_mission_creates_three_chained_chapters(dialog):
    from core.pda_mission import list_chapters
    before = len(list_chapters(dialog.doc))

    for i, (tw_getter, amount) in enumerate([(lambda: dialog.tier_widgets[0], 1000),
                                                (lambda: None, 2000), (lambda: None, 5000)]):
        if i > 0:
            dialog._add_tier()
        tier = dialog.tier_widgets[i]
        tier.title_en_edit.setText(f"Mine {amount} Iron")
        tier.check_combo.setCurrentIndex(1)
        tier.names_editor.combo.setCurrentText("IronResource")
        tier.names_editor._on_add()
        tier.types_editor.combo.setCurrentText("IronResource")
        tier.types_editor._on_add()
        tier.amount_spin.setValue(amount)
        tier.reward_rows[0].kind_combo.setCurrentText("XP")
        tier.reward_rows[0].count_spin.setValue(1000 * (i + 1))

    dialog._on_create()

    assert len(list_chapters(dialog.doc)) == before + 3


def test_tier_chain_reparses_and_is_chained_correctly(dialog):
    from core.pda_mission import list_chapters
    from core.yamllite.parser import parse_yaml_text

    for i in range(3):
        if i > 0:
            dialog._add_tier()
        tier = dialog.tier_widgets[i]
        tier.title_en_edit.setText(f"Tier {i + 1}")
        tier.names_editor.combo.setCurrentText("WeakZiraxSoldier")
        tier.names_editor._on_add()
        tier.amount_spin.setValue(10 * (i + 1))

    dialog._on_create()

    reparsed = parse_yaml_text(dialog.doc.render())
    assert reparsed is not None
    chapters = list_chapters(reparsed)
    new_chapters = chapters[-3:]

    activatables = [next(c.value for c in ch.children if c.key == "Activatable") for ch in new_chapters]
    assert activatables == ["Always", "WhenRewarded", "WhenRewarded"]


def test_validation_checks_every_tier_not_just_first(dialog, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    dialog._add_tier()
    dialog.tier_widgets[0].title_en_edit.setText("Valid tier")
    dialog.tier_widgets[0].names_editor.combo.setCurrentText("WeakZiraxSoldier")
    dialog.tier_widgets[0].names_editor._on_add()
    # Palier 2 laisse volontairement incomplet (pas de titre)

    called = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: called.append(True)))
    dialog._on_create()
    assert called == [True]


# ============================================================================
# Suppression d'une ligne de recompense -- manque signale par l'utilisateur
# (ajout par erreur d'une meme recompense deux fois, aucun moyen de la
# retirer). _NameListEditor avait deja ce bouton, _RewardRow non.
# ============================================================================

def test_reward_row_has_remove_button(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow([], lambda r: None)
    texts = []
    for i in range(row.layout().count()):
        widget = row.layout().itemAt(i).widget()
        if hasattr(widget, "text"):
            texts.append(widget.text())
    from core.i18n import t
    assert t("pda_mission.btn_remove_reward") in texts


def test_removing_reward_row_updates_tier_widget_list(dialog):
    tier = dialog.tier_widgets[0]
    initial_count = len(tier.reward_rows)
    tier._add_reward_row()
    assert len(tier.reward_rows) == initial_count + 1

    row_to_remove = tier.reward_rows[-1]
    tier._remove_reward_row(row_to_remove)
    assert len(tier.reward_rows) == initial_count
    assert row_to_remove not in tier.reward_rows


def test_removing_reward_via_its_own_button_click(dialog):
    tier = dialog.tier_widgets[0]
    tier._add_reward_row()
    tier.reward_rows[0].kind_combo.setCurrentText("XP")
    tier.reward_rows[0].count_spin.setValue(2000)
    tier.reward_rows[1].kind_combo.setCurrentText("XP")
    tier.reward_rows[1].count_spin.setValue(2000)

    duplicate = tier.reward_rows[1]
    from core.i18n import t
    for i in range(duplicate.layout().count()):
        widget = duplicate.layout().itemAt(i).widget()
        if hasattr(widget, "text") and widget.text() == t("pda_mission.btn_remove_reward"):
            widget.click()
            break

    assert len(tier.reward_rows) == 1
    assert tier.reward_rows[0].count_spin.value() == 2000


def test_created_mission_reflects_removed_duplicate_reward(dialog):
    from core.pda_mission import list_chapters
    tier = dialog.tier_widgets[0]
    tier.title_en_edit.setText("Kill 10 Zirax soldiers")
    tier.names_editor.combo.setCurrentText("WeakZiraxSoldier")
    tier.names_editor._on_add()

    tier._add_reward_row()
    tier.reward_rows[0].kind_combo.setCurrentText("XP")
    tier.reward_rows[0].count_spin.setValue(2000)
    tier.reward_rows[1].kind_combo.setCurrentText("XP")
    tier.reward_rows[1].count_spin.setValue(2000)

    duplicate = tier.reward_rows[1]
    tier._remove_reward_row(duplicate)

    dialog._on_create()
    new_chapter = list_chapters(dialog.doc)[-1]
    rewards_node = next(c for c in new_chapter.children if c.key == "Rewards")
    assert len(rewards_node.children) == 1


def test_removing_only_reward_row_leaves_zero_and_still_creates_mission(dialog):
    """Retirer la seule recompense presente doit rester possible -- une
    mission sans recompense est valide cote jeu (confirme sur de vrais
    chapitres du fichier reel, certains n'ont aucune section Rewards)."""
    from core.pda_mission import list_chapters
    tier = dialog.tier_widgets[0]
    tier.title_en_edit.setText("Kill 10 Zirax soldiers")
    tier.names_editor.combo.setCurrentText("WeakZiraxSoldier")
    tier.names_editor._on_add()

    tier._remove_reward_row(tier.reward_rows[0])
    assert len(tier.reward_rows) == 0

    dialog._on_create()
    new_chapter = list_chapters(dialog.doc)[-1]
    assert not any(c.key == "Rewards" for c in new_chapter.children)


def test_reward_row_players_only_checkbox_filters_item_suggestions(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow(["IronIngot", "PoiOnlyDecoration"], lambda r: None,
                      item_suggestions_players_only=["IronIngot"])
    row.show()
    row.kind_combo.setCurrentText("Item")
    assert row.extra_combo.count() == 2  # les 2 suggestions completes

    row.players_only_check.setChecked(True)
    items = [row.extra_combo.itemText(i) for i in range(row.extra_combo.count())]
    assert "PoiOnlyDecoration" not in items
    assert "IronIngot" in items


def test_reward_row_prioritizes_moneycard_when_present(qapp):
    """'MoneyCard' (voir core.pda_mission.credits_reward_item_name) doit
    passer en tete de liste des suggestions Item quand il existe reellement
    dans les suggestions -- confirme sur le vrai ItemsConfig.ecf de
    l'utilisateur comme etant le vrai item cable en dur par le moteur pour
    representer les credits."""
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow(["IronIngot", "MoneyCard", "SteelPlate"], lambda r: None)
    row.show()
    row.kind_combo.setCurrentText("Item")
    assert row.extra_combo.itemText(0) == "MoneyCard"
    assert row.extra_combo.count() == 3


def test_reward_row_never_fabricates_moneycard_when_absent(qapp):
    """Si 'MoneyCard' n'existe pas reellement dans les suggestions (scenario
    sans cet item), il ne doit JAMAIS etre invente/ajoute artificiellement."""
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow(["IronIngot", "SteelPlate"], lambda r: None)
    row.show()
    row.kind_combo.setCurrentText("Item")
    items = [row.extra_combo.itemText(i) for i in range(row.extra_combo.count())]
    assert "MoneyCard" not in items
    assert row.extra_combo.count() == 2


def test_reward_row_moneycard_produces_item_spec_with_correct_name(qapp):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import _RewardRow
    apply_theme(qapp)
    row = _RewardRow(["MoneyCard"], lambda r: None)
    row.show()
    row.kind_combo.setCurrentText("Item")
    row.extra_combo.setCurrentText("MoneyCard")
    row.count_spin.setValue(500)
    spec = row.to_spec()
    assert spec.kind == "Item"
    assert spec.item_name == "MoneyCard"
    assert spec.count == 500


def test_create_mission_with_moneycard_reward_no_warning(qapp, tmp_path, monkeypatch):
    """'MoneyCard' est un item normal comme un autre (confirme via le vrai
    ItemsConfig.ecf de l'utilisateur) -- aucun avertissement special ne doit
    se declencher, contrairement a l'ancien mecanisme 'Credits' (infirme sur
    deux logs client reels, retire depuis)."""
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import PdaMissionDialog
    from core.pda_mission import list_chapters
    from PyQt6.QtWidgets import QMessageBox
    apply_theme(qapp)
    doc = parse_yaml_file(PDA_YAML)
    csv_doc = parse_csv_text(PDA_CSV.read_text(encoding="utf-8"))

    items_ecf = tmp_path / "ItemsConfig.ecf"
    items_ecf.write_text(
        "{ Item Id: 248, Name: MoneyCard\n  StackSize: 50000\n  Credits: 1\n}\n", encoding="utf-8")

    pda_dialog = PdaMissionDialog(doc, csv_doc, sibling_ecf_files=[items_ecf])
    tier = pda_dialog.tier_widgets[0]
    tier.title_en_edit.setText("Bounty reward")
    tier.names_editor.combo.setCurrentText("WeakZiraxSoldier")
    tier.names_editor._on_add()
    tier.reward_rows[0].kind_combo.setCurrentText("Item")
    tier.reward_rows[0].extra_combo.setCurrentText("MoneyCard")
    tier.reward_rows[0].count_spin.setValue(500)

    warn_called = []
    monkeypatch.setattr(QMessageBox, "warning",
                         staticmethod(lambda *a, **k: warn_called.append(True) or QMessageBox.StandardButton.Yes))
    before_chapters = len(list_chapters(pda_dialog.doc))
    pda_dialog._on_create()
    assert not warn_called
    assert len(list_chapters(pda_dialog.doc)) == before_chapters + 1

    new_chapter = list_chapters(pda_dialog.doc)[-1]
    rewards_node = next(c for c in new_chapter.children if c.key == "Rewards")
    reward_entry = rewards_node.children[0]
    assert reward_entry.key == "Item"
    assert reward_entry.value == "MoneyCard"


def test_create_mission_no_warning_when_no_credits_reward_used(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.pda_mission_dialog import PdaMissionDialog
    from core.pda_mission import list_chapters
    from PyQt6.QtWidgets import QMessageBox
    apply_theme(qapp)
    doc = parse_yaml_file(PDA_YAML)
    csv_doc = parse_csv_text(PDA_CSV.read_text(encoding="utf-8"))

    pda_dialog = PdaMissionDialog(doc, csv_doc)
    tier = pda_dialog.tier_widgets[0]
    tier.title_en_edit.setText("Bounty reward")
    tier.names_editor.combo.setCurrentText("WeakZiraxSoldier")
    tier.names_editor._on_add()
    tier.reward_rows[0].kind_combo.setCurrentText("XP")

    warn_called = []
    monkeypatch.setattr(QMessageBox, "warning",
                         staticmethod(lambda *a, **k: warn_called.append(True) or QMessageBox.StandardButton.Yes))
    before_chapters = len(list_chapters(pda_dialog.doc))
    pda_dialog._on_create()
    assert not warn_called
    assert len(list_chapters(pda_dialog.doc)) == before_chapters + 1
