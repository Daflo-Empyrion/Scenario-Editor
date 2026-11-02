"""Pont de la vue web BBCode (gui/bbcode_web.py) : meme parti pris que
test_csv_web_view — le pont seul est teste, jamais le QWebEngineView (il
bloque sous offscreen). Les regles d'applicabilite vivent cote Python :
c'est elles qu'on verifie ici.
"""
import json


def _bridge_for(tmp_path, monkeypatch, csv_text):
    from PyQt6.QtWidgets import QApplication
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    from gui.bbcode_web import BbcodeWebBridge
    apply_theme(QApplication.instance())
    # sauvegarde centralisee redirigee vers tmp : jamais le vrai dossier home
    def _backup(path, kind="localization"):
        dst = path.parent / (path.stem + "-backup.bak")
        dst.write_bytes(path.read_bytes())
        return dst
    monkeypatch.setattr("gui.bbcode_web.central_backup", _backup)
    path = tmp_path / "Localization.csv"
    path.write_text(csv_text, encoding="utf-8", newline="")
    widget = CsvEditWidget(path, editable=True)
    return path, widget, BbcodeWebBridge(widget)


CSV = ("KEY,English,Français,Deutsch\r\n"
       "b1,[0AC9F9]Alien Block[-],[0AC9F9]Bloc Alien,Alien Block\r\n")


def test_get_reports_payload(qapp, tmp_path, monkeypatch):
    _path, widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    data = json.loads(bridge.get_reports(-1))
    assert data["col"] == -1
    assert [s["name"] for s in data["scope"]] == ["Français", "Deutsch"]
    # un seul rapport : le Deutsch sans balise n'a rien a signaler
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["line"] == 2                       # +1 entete, +1 base 1
    assert row["col_name"] == "Français"
    assert row["source"] == "[0AC9F9]Alien Block[-]"
    assert row["before"] == "[0AC9F9]Bloc Alien"
    assert row["after"] == "[0AC9F9]Bloc Alien[-]"
    assert row["repairable"] and row["applicable"] and row["checked"]
    assert data["apply_enabled"] is True
    # tout texte visible passe par t() : libelles presents
    assert data["labels"]["apply"] and data["labels"]["found"]


def test_get_reports_preset_follows_editor_column(qapp, tmp_path, monkeypatch):
    _path, widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    widget.table.setCurrentCell(0, 2)             # Français
    assert json.loads(bridge.get_reports(-2))["col"] == 2
    widget.table.setCurrentCell(0, 1)             # anglais = source
    assert json.loads(bridge.get_reports(-2))["col"] == -1
    widget.table.setCurrentCell(0, 0)             # cle technique
    assert json.loads(bridge.get_reports(-2))["col"] == -1


def test_apply_writes_fixes_and_central_backup(qapp, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr("gui.bbcode_web.info", lambda *a, **k: shown.append(a))
    path, widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    bridge.get_reports(-1)
    bridge.run_action("apply")
    assert "[0AC9F9]Bloc Alien[-]" in path.read_text(encoding="utf-8")
    assert not (tmp_path / "Localization.csv.bak").exists()  # rien a cote
    assert (tmp_path / "Localization-backup.bak").exists()
    assert widget.is_modified() is False          # save() a remis le drapeau
    assert len(shown) == 1                        # boite « N corrections »


def test_manual_edition_is_applied_not_proposal(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gui.bbcode_web.info", lambda *a, **k: None)
    path, _widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    bridge.get_reports(-1)
    bridge.set_after(0, "[0AC9F9]Bloc Alien (manuel)[-]")
    bridge.run_action("apply")
    assert "[0AC9F9]Bloc Alien (manuel)[-]" in path.read_text(encoding="utf-8")


def test_edition_equal_to_before_is_not_applied(qapp, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr("gui.bbcode_web.info", lambda *a, **k: shown.append(a))
    path, _widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    bridge.get_reports(-1)
    bridge.set_after(0, "[0AC9F9]Bloc Alien")     # = avant : rien a ecrire
    bridge.run_action("apply")
    assert len(shown) == 1                        # boite « rien de selectionne »
    assert "[0AC9F9]Bloc Alien[-]" not in path.read_text(encoding="utf-8")


def test_state_push_and_uncheck(qapp, tmp_path, monkeypatch):
    _path, _widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    bridge.get_reports(-1)
    seen = []
    bridge.data_changed.connect(seen.append)
    bridge.set_checked(0, False)
    state = json.loads(seen[-1])
    assert "rows" not in state                    # etat LEGER, pas le payload
    assert state["checked"]["0"] is False
    assert state["apply_enabled"] is False
    assert bridge._checked_fixes() == []


def test_select_all_rechecks(qapp, tmp_path, monkeypatch):
    _path, _widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    bridge.get_reports(-1)
    bridge.set_checked(0, False)
    bridge.run_action("select_all")
    assert len(bridge._checked_fixes()) == 1


def test_scope_restriction_writes_only_one_language(qapp, tmp_path, monkeypatch):
    """Confirmation demandee (31/10) : une langue seule -> seule cette
    colonne est ecrite, les autres restent intactes."""
    monkeypatch.setattr("gui.bbcode_web.info", lambda *a, **k: None)
    path, _widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    bridge.get_reports(3)                         # Deutsch seul : aucun rapport
    assert json.loads(bridge._payload)["rows"] == []
    bridge.get_reports(2)                         # Français seul
    bridge.run_action("apply")
    content = path.read_text(encoding="utf-8")
    assert "[0AC9F9]Bloc Alien[-]" in content
    assert content.splitlines()[-1].endswith("Alien Block")   # Deutsch intact


def test_actions_without_dialog_are_safe(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gui.bbcode_web.info", lambda *a, **k: None)
    _path, _widget, bridge = _bridge_for(tmp_path, monkeypatch, CSV)
    bridge.get_reports(-1)
    bridge.run_action("close")                    # dialog=None : pas de crash
    bridge.run_action("action_inconnue")          # liste blanche : ignore
    bridge.set_after(99999, "x")                  # hors bornes : ignore
