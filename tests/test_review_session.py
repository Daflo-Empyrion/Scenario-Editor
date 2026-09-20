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

"""Revision de traduction persistable (demande 17/09/2026) : controler les
~5000 lignes traduites d'un gros Localization.csv se fait en plusieurs fois.

- core/review_session.py : session par fichier CSV (row_key + colonnes,
  JAMAIS l'index de ligne) ;
- BatchTranslationReviewDialog en mode incrémental : application au fil de
  l'eau des lignes cochees, sauvegarde/reprise de l'etat restant ;
- CsvEditWidget : proposition de reprise a l'ouverture, bouton barre.
"""

import pytest

from core import review_session


@pytest.fixture(autouse=True)
def _isolate_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(review_session, "SESSIONS_DIR", tmp_path / "sessions")


def _make_csv(tmp_path, name="Localization.csv", rows=(("k1", "Hello", ""),
                                                        ("k2", "World", ""),
                                                        ("k3", "Bye", ""))):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["KEY,English,Français"] + [",".join(r) for r in rows]
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")
    return path


# ----------------------------------------------------------------------
# core/review_session.py
# ----------------------------------------------------------------------

def test_save_load_delete_roundtrip(tmp_path):
    path = _make_csv(tmp_path)
    items = [{"row_key": "k1", "src_col": 1, "dst_col": 2,
              "original": "Hello", "translated": "Salut", "checked": True}]
    review_session.save_session(path, {"items": items, "target_col": 2})
    data = review_session.load_session(path)
    assert data is not None
    assert data["version"] == 1
    assert data["target_col"] == 2
    assert data["items"] == items
    review_session.delete_session(path)
    assert review_session.load_session(path) is None


def test_delete_missing_session_is_noop(tmp_path):
    review_session.delete_session(tmp_path / "absent.csv")


def test_load_missing_or_corrupt_returns_none(tmp_path):
    path = _make_csv(tmp_path)
    assert review_session.load_session(path) is None
    review_session.save_session(path, {"items": [{"row_key": "k1"}]})
    review_session._session_file(path).write_text("{corrompu", encoding="utf-8")
    assert review_session.load_session(path) is None


def test_same_name_in_different_folders_do_not_collide(tmp_path):
    a = _make_csv(tmp_path / "a", rows=(("k1", "Hello", ""),))
    b = _make_csv(tmp_path / "b", rows=(("k1", "Hello", ""),))
    review_session.save_session(a, {"items": [{"row_key": "A"}]})
    assert review_session.load_session(b) is None
    assert review_session._session_file(a) != review_session._session_file(b)


# ----------------------------------------------------------------------
# BatchTranslationReviewDialog : mode revision persistable
# ----------------------------------------------------------------------

def _spy_dialog(items, **kwargs):
    from gui.csv_dialogs import BatchTranslationReviewDialog

    class Spy(BatchTranslationReviewDialog):
        accepted_count = 0

        def accept(self):
            self.accepted_count += 1
            super().accept()

    return Spy(items, **kwargs)


METAS = [{"row_key": f"k{i}", "src_col": 1, "dst_col": 2, "plan_idx": i}
         for i in range(4)]


def test_incremental_consume_checked_applies_and_shrinks(qapp):
    applied = []
    dialog = _spy_dialog(
        [{"label": f"k{i}", "original": f"O{i}", "translated": f"T{i}",
          "checked": False} for i in range(4)],
        metas=METAS, on_apply_batch=lambda res: applied.extend(res))
    assert dialog.remaining() == 4
    dialog._consume_checked()
    assert applied == []
    assert dialog.accepted_count == 0  # rien de coche -> rien ne se passe

    from PyQt6.QtCore import Qt
    for r in (0, 2):
        dialog.table.item(r, 0).setCheckState(Qt.CheckState.Checked)
    dialog._consume_checked()
    assert [(m["plan_idx"], txt) for m, txt in applied] == [(0, "T0"), (2, "T2")]
    assert dialog.remaining() == 2
    assert dialog.accepted_count == 0
    # alignement metas <-> lignes maintenu apres suppression
    assert [m["row_key"] for m in dialog._metas] == ["k1", "k3"]
    assert dialog.table.item(0, 1).text() == "k1"

    dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog._consume_checked()
    assert dialog.remaining() == 1
    dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog._consume_checked()
    assert dialog.accepted_count == 1  # tableau vide -> fermeture automatique


def test_checked_state_and_current_state_roundtrip(qapp):
    dialog = _spy_dialog(
        [{"label": "a", "original": "A", "translated": "T1", "checked": False},
         {"label": "b", "original": "B", "translated": "T2"},
         {"label": "c", "original": "C", "translated": "ERR", "failed": True}],
        metas=[{"row_key": "a", "src_col": 1, "dst_col": 2},
               {"row_key": "b", "src_col": 1, "dst_col": 2},
               {"row_key": "c", "src_col": 1, "dst_col": 2, "failed": True}])
    from PyQt6.QtCore import Qt
    assert dialog.table.item(0, 0).checkState() == Qt.CheckState.Unchecked
    assert dialog.table.item(1, 0).checkState() == Qt.CheckState.Checked
    assert dialog.table.item(2, 0).checkState() == Qt.CheckState.Unchecked

    state = dialog.current_state()
    assert [s["checked"] for s in state] == [False, True, False]
    assert [s["failed"] for s in state] == [False, False, True]
    assert [s["row_key"] for s in state] == ["a", "b", "c"]
    assert [s["translated"] for s in state] == ["T1", "T2", "ERR"]


def test_save_and_close_persists_state(qapp):
    saved = []
    dialog = _spy_dialog(
        [{"label": "k0", "original": "O0", "translated": "T0"}],
        metas=[{"row_key": "k0", "src_col": 1, "dst_col": 2, "plan_idx": 0}],
        on_apply_batch=lambda res: None,
        on_save_session=lambda state: saved.append(state))
    dialog._save_and_close()
    assert dialog.saved_session is True
    assert dialog.accepted_count == 1
    assert saved and saved[0][0]["row_key"] == "k0"
    assert saved[0][0]["translated"] == "T0"


def test_reject_offers_save(monkeypatch):
    """Fermeture d'une revision non vide : boite Sauvegarder / Quitter sans
    sauvegarder / Annuler (QMessageBox patche : le VRAI bloquerait la suite
    pytest, piege documente)."""
    import gui.csv_dialogs as cd

    class _Btn:
        def __init__(self, text):
            self.text = text

    state = {"choose": None}  # box -> bouton clique

    class _Roles:
        AcceptRole, DestructiveRole, RejectRole = "acc", "des", "rej"

    class _FakeBox:
        ButtonRole = _Roles

        def __init__(self, *a, **k):
            self.buttons = []
            self.texts = []

        def setWindowTitle(self, s):
            pass

        def setText(self, s):
            self.texts.append(s)

        def addButton(self, text, role):
            b = _Btn(text)
            self.buttons.append(b)
            return b

        def exec(self):
            pass

        def clickedButton(self):
            return state["choose"](self)

    monkeypatch.setattr(cd, "QMessageBox", _FakeBox)
    calls = []

    def _mk_dialog():
        return _spy_dialog(
            [{"label": "k0", "original": "O0", "translated": "T0"},
             {"label": "k1", "original": "O1", "translated": "T1"}],
            metas=[{"row_key": "k0", "plan_idx": 0},
                   {"row_key": "k1", "plan_idx": 1}],
            on_apply_batch=lambda res: calls.append(res),
            on_save_session=lambda st: calls.append(("saved", st)))

    # bouton 1 = Sauvegarder et quitter -> session ecrite + accept
    d = _mk_dialog()
    state["choose"] = lambda box: box.buttons[0]
    d.reject()
    assert d.saved_session is True and d.accepted_count == 1
    assert calls and calls[0][0] == "saved"

    # bouton 2 = Quitter sans sauvegarder -> fermeture simple, rien persiste
    d = _mk_dialog()
    state["choose"] = lambda box: box.buttons[1]
    d.reject()
    assert d.saved_session is False and d.accepted_count == 0

    # bouton 3 = Annuler -> dialogue reste ouvert, rien ne bouge
    d = _mk_dialog()
    state["choose"] = lambda box: box.buttons[2]
    d.reject()
    assert d.saved_session is False and d.accepted_count == 0
    assert d.remaining() == 2


def test_legacy_mode_unchanged(qapp):
    """Sans callbacks (Rechercher/Remplacer), comportement historique :
    tout-ou-rien via get_accepted_results()."""
    from gui.csv_dialogs import BatchTranslationReviewDialog

    dialog = BatchTranslationReviewDialog(
        [{"label": "a", "original": "A", "translated": "T1"},
         {"label": "b", "original": "B", "translated": "T2", "failed": True}])
    assert dialog.on_apply_batch is None
    assert dialog.on_save_session is None
    from PyQt6.QtCore import Qt
    # b ('failed') est decochee par defaut, a (normale) est cochee
    assert dialog.get_accepted_results() == [(0, "T1")]
    dialog.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    assert dialog.get_accepted_results() == []
    assert dialog.remaining() == 2


# ----------------------------------------------------------------------
# CsvEditWidget : ouverture de la revue + reprise
# ----------------------------------------------------------------------

@pytest.fixture()
def widget(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)
    # memoire/glossaire : espions (aucune ecriture du vrai ~/.empyrion_editor)
    stored = []
    monkeypatch.setattr("core.translation_memory.store", lambda *a: stored.append(a))
    added = []
    monkeypatch.setattr("core.glossary.add_entry",
                        lambda *a, **k: added.append(a))
    monkeypatch.setattr("core.glossary.auto_feed_ok", lambda txt: True)
    w = CsvEditWidget(_make_csv(tmp_path), editable=True)
    w._stored_memory = stored
    w._added_glossary = added
    return w


def _capture_open(widget, monkeypatch):
    captured = []
    monkeypatch.setattr(widget, "_open_review_dialog",
                        lambda plan, metas: captured.append((plan, metas)))
    return captured


def test_finish_batch_review_opens_incremental(widget, monkeypatch):
    captured = _capture_open(widget, monkeypatch)
    plan = []
    for r in range(2):
        plan.append({'label': f"k{r}", 'original': widget.table.item(r, 1).text(),
                     'dest_item': widget.table.item(r, 2),
                     'target_code': 'fr', 'source_code': 'en',
                     'row_key': f"k{r}", 'src_col': 1, 'dst_col': 2,
                     'header': 'English'})
    results = [{'translated': 'Salut', 'failed': False},
               {'translated': 'Monde', 'failed': False}]
    widget._finish_batch_review(plan, results, False, 0, 2)
    (p, metas), = captured
    assert metas[0]['plan_idx'] == 0 and metas[1]['plan_idx'] == 1
    assert metas[0]['translated'] == 'Salut'
    assert metas[0]['row_key'] == 'k0' and metas[0]['dst_col'] == 2

    # application d'un lot via le vrai applier : cellule + memoire
    applier = widget._make_review_applier(p)
    applier([(metas[0], 'Salut corrige')])
    assert widget.table.item(0, 2).text() == 'Salut corrige'
    assert widget._stored_memory == [('Hello', 'en', 'fr', 'Salut corrige')]
    assert widget.table.item(1, 2).text() == ''  # l'autre ligne n'est pas touchee


def test_finish_batch_review_nothing_processed(widget, monkeypatch):
    captured = _capture_open(widget, monkeypatch)
    widget._finish_batch_review([], [], False, 0, 0)
    widget._finish_batch_review([{'label': 'x'}], [None], False, 0, 0)
    assert captured == []


def test_resume_review_session(widget, monkeypatch):
    captured = _capture_open(widget, monkeypatch)
    data = {"version": 1, "items": [
        {"row_key": "k2", "src_col": 1, "dst_col": 2, "label": "k2 / English",
         "original": "World", "translated": "Monde", "failed": False,
         "checked": True, "source_code": "en", "target_code": "fr",
         "header": "English"},
        {"row_key": "k1", "src_col": 1, "dst_col": 2, "label": "k1 / English",
         "original": "Hello", "translated": "Salut", "failed": False,
         "checked": False, "source_code": "en", "target_code": "fr",
         "header": "English"},
    ]}
    widget._resume_review_session(data)
    (plan, metas), = captured
    assert [m['row_key'] for m in metas] == ["k2", "k1"]
    assert plan[0]['dest_item'] is widget.table.item(1, 2)
    assert metas[1]['checked'] is False
    assert metas[0]['translated'] == 'Monde'


def test_resume_skips_missing_rows(widget, monkeypatch):
    captured = _capture_open(widget, monkeypatch)
    data = {"version": 1, "items": [
        {"row_key": "k1", "src_col": 1, "dst_col": 2, "label": "k1",
         "original": "World", "translated": "Monde", "failed": False,
         "source_code": "en", "target_code": "fr"},
        {"row_key": "supprimee", "src_col": 1, "dst_col": 2, "label": "x",
         "original": "Ghost", "translated": "Fantome", "failed": False,
         "source_code": "en", "target_code": "fr"},
    ]}
    widget._resume_review_session(data)
    (plan, metas), = captured
    assert [m['row_key'] for m in metas] == ["k1"]
    assert "1" in widget.search_status.text()  # 1 ligne introuvable signalee


def test_resume_with_duplicate_keys_consumes_each_row_once(qapp, tmp_path,
                                                           monkeypatch):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)
    w = CsvEditWidget(_make_csv(tmp_path, rows=(("dup", "A", ""),
                                                ("dup", "B", ""))), editable=True)
    captured = []
    monkeypatch.setattr(w, "_open_review_dialog",
                        lambda plan, metas: captured.append((plan, metas)))
    w._resume_review_session({"version": 1, "items": [
        {"row_key": "dup", "src_col": 1, "dst_col": 2, "translated": "A2",
         "failed": False},
        {"row_key": "dup", "src_col": 1, "dst_col": 2, "translated": "B2",
         "failed": False},
    ]})
    (plan, metas), = captured
    assert plan[0]['dest_item'] is w.table.item(0, 2)
    assert plan[1]['dest_item'] is w.table.item(1, 2)


def test_resume_nothing_left_deletes_session(widget, monkeypatch):
    deleted = []
    monkeypatch.setattr("core.review_session.delete_session",
                        lambda p: deleted.append(p))
    widget._resume_review_session({"version": 1, "items": []})
    assert deleted == []  # session vide : refusee avant meme le matching

    data = {"version": 1, "items": [
        {"row_key": "ghost", "src_col": 1, "dst_col": 2, "translated": "x",
         "failed": False}]}
    widget._resume_review_session(data)
    assert len(deleted) == 1  # plus aucune ligne retrouvable -> purge


def test_resume_button_visibility(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    from core import review_session
    apply_theme(qapp)
    path = _make_csv(tmp_path)
    w = CsvEditWidget(path, editable=True)
    assert w.btn_resume_review.isHidden()
    review_session.save_session(path, {"items": [{"row_key": "k1"}]})
    assert w._refresh_review_resume_btn() is not None
    assert not w.btn_resume_review.isHidden()
    review_session.delete_session(path)
    assert w._refresh_review_resume_btn() is None
    assert w.btn_resume_review.isHidden()


# ----------------------------------------------------------------------
# Sessions par KIND : traduction et orthographe coexistent
# ----------------------------------------------------------------------

def test_kinds_are_independent(tmp_path):
    path = _make_csv(tmp_path)
    review_session.save_session(path, {"items": [{"row_key": "k1"}]},
                                kind="translation")
    review_session.save_session(path, {"items": [{"row_key": "k2"}]},
                                kind="spellcheck")
    assert review_session.load_session(path, kind="translation")["items"] == [
        {"row_key": "k1"}]
    assert review_session.load_session(path, kind="spellcheck")["items"] == [
        {"row_key": "k2"}]
    review_session.delete_session(path, kind="translation")
    assert review_session.load_session(path, kind="translation") is None
    assert review_session.load_session(path, kind="spellcheck") is not None
    assert review_session.load_session(path) is None  # defaut = translation


# ----------------------------------------------------------------------
# Revue Grammalecte : mode revision persistable
# ----------------------------------------------------------------------

def _spell_issue(row, col, text, start, end, s_type="typo",
                 suggestions=("Corrige",)):
    return {"row": row, "col": col, "key": f"k{row}",
            "cell_text": text, "start": start, "end": end,
            "orig": text[start:end], "s_type": s_type,
            "message": "msg", "suggestions": list(suggestions),
            "is_lang": False}


def _spell_dialog(issues, **kwargs):
    from gui.spellcheck_dialog import SpellcheckReviewDialog

    class Spy(SpellcheckReviewDialog):
        accepted_count = 0

        def accept(self):
            self.accepted_count += 1
            super().accept()

    return Spy(issues, **kwargs)


def test_spellcheck_incremental_consume_and_offset_adjust():
    """Application au fil de l'eau : les issues restantes de la MEME cellule
    voient leurs offsets ajustes du delta des corrections appliquees."""
    applied = []

    def applier(pairs):
        applied.extend(pairs)
        # simule l'application reelle : remplace l'erreur par le choix
        text = "Un moit corrige ici"
        new_text = text
        for issue, choice in sorted(pairs, key=lambda p: p[0]["start"],
                                    reverse=True):
            new_text = new_text[:issue["start"]] + choice + new_text[issue["end"]:]
        return {(pairs[0][0]["row"], pairs[0][0]["col"]): new_text}

    # cellule : "Un moit corrige ici" ; deux issues sur la MEME cellule :
    #   A = [3,7) 'moit' (appliquee -> 'Corrige' plus long : delta = +3)
    #   B = [16,19) 'ici' (reste, doit devenir [19,22))
    issues = [_spell_issue(0, 2, "Un moit corrige ici", 3, 7),
              _spell_issue(0, 2, "Un moit corrige ici", 16, 19, suggestions=())]
    dialog = _spell_dialog(issues, on_apply_batch=applier)
    dialog.table.cellWidget(0, 0).setChecked(True)
    dialog._consume_checked()

    assert len(applied) == 1
    remaining_issue = dialog._issues[0]
    assert remaining_issue["orig"] == "ici"
    assert remaining_issue["start"] == 19 and remaining_issue["end"] == 22
    assert remaining_issue["cell_text"] == "Un Corrige corrige ici"
    assert "[ici]" in dialog.table.item(0, 2).text()  # extrait rafraichi
    assert dialog.remaining() == 1
    assert dialog.accepted_count == 0


def test_spellcheck_consume_last_row_accepts():
    issues = [_spell_issue(0, 2, "Un moit ici", 4, 8)]
    dialog = _spell_dialog(issues, on_apply_batch=lambda pairs: {(0, 2): "ok"})
    dialog.table.cellWidget(0, 0).setChecked(True)
    dialog._consume_checked()
    assert dialog.accepted_count == 1
    assert dialog.remaining() == 0


def test_spellcheck_absorbed_issue_removed():
    """Une issue recouverte par une correction appliquee disparait aussi."""
    issues = [_spell_issue(0, 2, "aaaa bb", 0, 4),
              _spell_issue(0, 2, "aaaa bb", 2, 5)]  # recouvre la premiere
    dialog = _spell_dialog(issues, on_apply_batch=lambda pairs: {(0, 2): "X bb"})
    dialog.table.cellWidget(0, 0).setChecked(True)  # applique la [0,4)
    dialog._consume_checked()
    assert dialog.remaining() == 0  # la [2,5) recouverte est retiree
    assert dialog.accepted_count == 1


def test_spellcheck_current_state_and_save():
    saved = []
    issues = [_spell_issue(0, 2, "Un moit ici", 4, 8),
              _spell_issue(1, 2, " Encore anglais", 0, 0, s_type="lang",
                           suggestions=())]
    issues[1]["is_lang"] = True
    dialog = _spell_dialog(issues,
                           on_apply_batch=lambda pairs: {},
                           on_save_session=lambda state: saved.append(state))
    dialog.table.cellWidget(0, 0).setChecked(True)
    dialog.table.cellWidget(0, 4).setCurrentIndex(1)  # choix de suggestion
    state = dialog.current_state()
    assert state[0]["row_key"] == "k0" and "row" not in state[0]
    assert state[0]["checked"] is True
    assert state[0]["chosen"] == "Corrige"
    assert state[1]["is_lang"] is True
    assert state[1]["checked"] is False
    dialog._save_and_close()
    assert dialog.saved_session is True and dialog.accepted_count == 1
    assert saved and saved[0][0]["row_key"] == "k0"


def test_spellcheck_restore_checked_and_choice_on_rebuild():
    """A la reprise, l'etat sauvegarde des cases et du combo est restaure."""
    issues = [_spell_issue(0, 2, "Un moit ici", 4, 8,
                           suggestions=("Corrige", "Autre"))]
    issues[0]["checked"] = True
    issues[0]["chosen"] = "Autre"
    dialog = _spell_dialog(issues, on_apply_batch=lambda pairs: {})
    assert dialog.table.cellWidget(0, 0).isChecked()
    combo = dialog.table.cellWidget(0, 4)
    assert combo.currentData() == "Autre"


def test_spellcheck_legacy_mode_unchanged():
    from gui.spellcheck_dialog import SpellcheckReviewDialog
    issues = [_spell_issue(0, 2, "Un moit ici", 4, 8)]
    dialog = SpellcheckReviewDialog(issues)
    assert dialog.on_apply_batch is None
    assert dialog.on_save_session is None
    # pre-coche pour un type sur (conf) seulement
    assert dialog.table.cellWidget(0, 0).isChecked() is False
    issues[0]["s_type"] = "conf"
    dialog2 = SpellcheckReviewDialog([issues[0]])
    assert dialog2.table.cellWidget(0, 0).isChecked() is True
    chosen = dialog2.checked_issues()
    assert len(chosen) == 1 and chosen[0]["chosen"] == "Corrige"


# ----------------------------------------------------------------------
# Reprise d'une session orthographe (CsvEditWidget)
# ----------------------------------------------------------------------

def _capture_spell_open(widget, monkeypatch):
    captured = []
    monkeypatch.setattr(widget, "_open_spellcheck_review",
                        lambda issues, scope_label: captured.append(issues))
    return captured


def test_resume_spellcheck_intact_cells_restored(widget, monkeypatch):
    """Cellule inchangee depuis la sauvegarde : issue restauree a
    l'identique, aucun re-scan."""
    from core import spellcheck as sp
    called = []
    monkeypatch.setattr(sp, "check_text", lambda text: called.append(text))
    captured = _capture_spell_open(widget, monkeypatch)
    data = {"version": 1, "items": [
        dict(_spell_issue(0, 2, "", 0, 0), row_key="k1"),
    ]}
    widget._resume_spellcheck_session(data)
    issues, = captured
    assert issues[0]["row"] == 0 and issues[0]["col"] == 2
    assert issues[0]["row_key"] == "k1"
    assert called == []  # cellule intacte : pas de re-scan


def test_resume_spellcheck_changed_cell_rescanned(widget, monkeypatch):
    from core import spellcheck as sp
    captured = _capture_spell_open(widget, monkeypatch)
    monkeypatch.setattr(sp, "check_text",
                        lambda text: [{"start": 0, "end": 1, "orig": text[:1],
                                       "s_type": "typo", "message": "m",
                                       "suggestions": ["X"]}])
    data = {"version": 1, "items": [
        dict(_spell_issue(0, 2, "TEXTE OBSOLETE", 6, 11), row_key="k1"),
    ]}
    widget._resume_spellcheck_session(data)
    issues, = captured
    assert issues and issues[0]["cell_text"] == ""  # cellule FR du CSV de test
    assert issues[0]["row"] == 0 and issues[0]["col"] == 2


def test_resume_spellcheck_missing_rows(widget, monkeypatch):
    captured = _capture_spell_open(widget, monkeypatch)
    review_session.save_session(widget.path, {"items": [
        dict(_spell_issue(0, 2, "Hello", 1, 2), row_key="introuvable"),
    ]}, kind="spellcheck")
    widget._resume_spellcheck_session()
    assert captured == []  # plus rien de retrouvable : purge, pas d'ouverture
    assert review_session.load_session(widget.path,
                                       kind="spellcheck") is None


# ----------------------------------------------------------------------
# Traductions vanille : source + couleurs
# ----------------------------------------------------------------------

def test_translate_text_with_source_sources(tmp_path, monkeypatch):
    from core import translation, translation_memory, vanilla_memory
    monkeypatch.setattr(translation_memory, "get_cached",
                        lambda text, src, tgt: "MEM" if text == "a" else None)
    monkeypatch.setattr(vanilla_memory, "get_vanilla_cached",
                        lambda text, tgt: "VAN" if text == "b" else None)
    monkeypatch.setattr(translation, "translate_text",
                        lambda text, **k: f"ENG:{text}")
    assert translation.translate_text_with_source("a", target="fr") == ("MEM", "memory")
    assert translation.translate_text_with_source("b", target="fr") == ("VAN", "vanilla")
    assert translation.translate_text_with_source("c", target="fr") == ("ENG:c", "engine")
    assert translation.translate_text_with_source("  ", target="fr") == ("  ", "")


def test_vanilla_row_color_in_review(qapp):
    from gui.csv_dialogs import BatchTranslationReviewDialog, VANILLA_COLOR
    dialog = BatchTranslationReviewDialog([
        {"label": "a", "original": "A", "translated": "VAN", "source": "vanilla"},
        {"label": "b", "original": "B", "translated": "ENG", "source": "engine"},
    ])
    vanilla_bg = dialog.table.item(0, 3).background()
    engine_bg = dialog.table.item(1, 3).background()
    assert vanilla_bg.color() == VANILLA_COLOR
    assert engine_bg.color() != VANILLA_COLOR


def test_vanilla_cell_marked_on_apply(widget, monkeypatch):
    captured = []
    monkeypatch.setattr(widget, "_open_review_dialog",
                        lambda plan, metas: captured.append((plan, metas)))
    plan = [{'label': "k1", 'original': "Hello",
             'dest_item': widget.table.item(0, 2),
             'target_code': 'fr', 'source_code': 'en',
             'row_key': "k1", 'src_col': 1, 'dst_col': 2, 'header': "English"}]
    results = [{'translated': "Salut", 'failed': False, 'source': "vanilla"}]
    widget._finish_batch_review(plan, results, False, 0, 1)
    (p, metas), = captured
    assert metas[0]["source"] == "vanilla"
    applier = widget._make_review_applier(p)
    applier([(metas[0], "Salut")])
    cell = widget.table.item(0, 2)
    assert cell.background().color().name() == "#e4f3e8"
    assert widget.table.item(1, 2).background().color().name() != "#e4f3e8"


def test_vanilla_pending_kinds_menu_dispatcher(widget, monkeypatch):
    """Le bouton barre dispatche entre traduction et orthographe."""
    review_session.save_session(widget.path, {"items": [{"row_key": "k1"}]},
                                kind="spellcheck")
    review_session.save_session(widget.path, {"items": [{"row_key": "k1"}]},
                                kind="translation")
    kinds = widget._pending_review_kinds()
    assert [k for k, _ in kinds] == ["translation", "spellcheck"]
    review_session.delete_session(widget.path, kind="spellcheck")
    kinds = widget._pending_review_kinds()
    assert [k for k, _ in kinds] == ["translation"]
