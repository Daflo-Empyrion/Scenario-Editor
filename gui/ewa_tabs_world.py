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
"""Onglets MONDE : structures (GlobalStructureList : toucher / supprimer /
faction / teleport), restauration depuis les backups EWA (joueurs,
playfields) et planificateur Timetable (arbre + execution + edition JSON)."""
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.ewa.client import pick
from core.i18n import t
from gui.ewa_dialog import EwaTab
from gui.theme import icon

STRUCTURE_TYPES = {0: "ewa.struct.type.bp", 1: "ewa.struct.type.ba",
                   2: "ewa.struct.type.cv", 3: "ewa.struct.type.sv",
                   4: "ewa.struct.type.pois", 5: "ewa.struct.type.asteroid"}


def _s(value) -> str:
    return "" if value is None else str(value)


class StructuresTab(EwaTab):
    """Arbre playfield -> structures avec actions d'administration."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._factions: list = []
        self._busy = False

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.refresh_btn = QPushButton(icon("fa5s.refresh", "#ffffff"),
                                       t("ewa.struct.refresh"))
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(t("ewa.struct.filter"))
        self.filter_edit.textChanged.connect(self._apply_filter)
        top.addWidget(self.filter_edit, 1)
        layout.addLayout(top)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t(k) for k in [
            "ewa.struct.col.name", "ewa.struct.col.id",
            "ewa.struct.col.type", "ewa.struct.col.faction",
            "ewa.struct.col.blocks", "ewa.struct.col.pos"]])
        self.tree.itemSelectionChanged.connect(self._toggle_actions)
        layout.addWidget(self.tree, 1)

        actions = QHBoxLayout()
        for icon_name, label_key, handler in [
                ("fa5s.hand-paper", "ewa.struct.touch", self._touch),
                ("fa5s.trash", "ewa.struct.delete", self._delete),
                ("fa5s.users", "ewa.struct.faction", self._set_faction),
                ("fa5s.location-arrow", "ewa.struct.warp", self._warp)]:
            button = QPushButton(icon(icon_name, "#ffffff"), t(label_key))
            button.setObjectName("secondaryButton")
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self._toggle_actions()

    # --------------------------------------------------------------- donnees

    def on_connected(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            structures = self.client.get_global_structures()
            factions = self.client.get_factions()
            return structures, factions

        def _done(payload):
            self._busy = False
            structures, self._factions = payload
            self._fill(structures)

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-structures")

    def _fill(self, structures: dict) -> None:
        self.tree.clear()
        for playfield in sorted(structures):
            parent = QTreeWidgetItem([playfield, "", "", "", _s(len(
                structures[playfield])), ""])
            for info in structures[playfield]:
                type_key = STRUCTURE_TYPES.get(
                    int(pick(info, "type", default=-1) or -1), "")
                type_label = t(type_key) if type_key else _s(pick(info, "type"))
                QTreeWidgetItem(parent, [
                    _s(pick(info, "name")),
                    _s(pick(info, "id")),
                    type_label,
                    _s(pick(info, "factionId")),
                    _s(pick(info, "cntBlocks")),
                    f"{_s(pick(info, 'pos'))}"])
            self.tree.addTopLevelItem(parent)
        self.tree.expandAll()

    def _apply_filter(self) -> None:
        needle = self.filter_edit.text().strip().lower()
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            any_visible = False
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                match = (not needle
                         or needle in child.text(0).lower()
                         or needle in parent.text(0).lower())
                child.setHidden(not match)
                any_visible = any_visible or match
            parent.setHidden(bool(needle) and not any_visible)

    # -------------------------------------------------------------- selected

    def _selected(self):
        item = self.tree.currentItem()
        if item is None or item.parent() is None:
            return None
        return item

    def _toggle_actions(self) -> None:
        pass                        # actions gardées actives : gardes internes

    def _run(self, work) -> None:
        from gui.ewa_async import async_call
        async_call(self, work, lambda _r: self.refresh(),
                   lambda error: self.dialog.show_error(error),
                   "ewa-struct-action")

    def _touch(self) -> None:
        item = self._selected()
        if item is None or self.client is None:
            return
        payload = {"id": int(item.text(1) or 0), "playfield":
                   item.parent().text(0)}

        def _work():
            self.client.touch_structures([payload])

        self._run(_work)

    def _delete(self) -> None:
        item = self._selected()
        if item is None or self.client is None:
            return
        from gui.msgboxes import ask_yes_no
        if not ask_yes_no(self, t("ewa.struct.delete_title"),
                          t("ewa.struct.delete_confirm", name=item.text(0))):
            return
        payload = {"id": int(item.text(1) or 0), "playfield":
                   item.parent().text(0)}

        def _work():
            self.client.delete_structures([payload])

        self._run(_work)

    def _set_faction(self) -> None:
        item = self._selected()
        if item is None or self.client is None:
            return
        if not self._factions:
            self.dialog.show_error(t("ewa.struct.no_factions"))
            return
        combo = QComboBox()
        names = []
        for faction in self._factions:
            abbrev = _s(pick(faction, "FactionAbbrev")
                        or pick(faction, "Abbrev"))
            name = _s(pick(faction, "FactionName") or pick(faction, "Name"))
            names.append(f"{abbrev} ({name})" if name else abbrev)
        dialog = QInputDialog(self)
        dialog.setWindowTitle(t("ewa.struct.faction_title"))
        dialog.setComboBoxItems(names)
        dialog.setLabelText(t("ewa.struct.faction_ask", name=item.text(0)))
        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return
        abbrev = names[dialog.comboBox().currentIndex()].split(" (")[0]

        def _work():
            self.client.set_faction_of_structures(abbrev, [int(item.text(1))])

        self._run(_work)

    def _warp(self) -> None:
        item = self._selected()
        if item is None or self.client is None:
            return
        current_pf = item.parent().text(0)
        playfield, ok = QInputDialog.getText(
            self, t("ewa.struct.warp_title"), t("ewa.struct.warp_pf"),
            text=current_pf)
        if not ok or not playfield.strip():
            return
        coords, ok = QInputDialog.getText(
            self, t("ewa.struct.warp_title"), t("ewa.struct.warp_coords"),
            text="0, 0, 0")
        if not ok:
            return
        try:
            x_value, y_value, z_value = [float(part) for part in
                                         coords.replace(",", " ").split()[:3]]
        except (ValueError, IndexError):
            self.dialog.show_error(t("ewa.struct.warp_bad_coords"))
            return

        def _work():
            self.client.warp_structure(int(item.text(1) or 0),
                                       playfield.strip(),
                                       (x_value, y_value, z_value))

        self._run(_work)


class RestoreTab(EwaTab):
    """Restauration depuis les backups du serveur (joueurs, playfields)."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._busy = False

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(t("ewa.restore.backup")))
        self.backup_combo = QComboBox()
        top.addWidget(self.backup_combo, 1)
        self.reload_btn = QPushButton(icon("fa5s.refresh", "#ffffff"),
                                      t("ewa.restore.reload"))
        self.reload_btn.setObjectName("secondaryButton")
        self.reload_btn.clicked.connect(self.reload_backups)
        top.addWidget(self.reload_btn)
        layout.addLayout(top)

        mark_row = QHBoxLayout()
        self.mark_edit = QLineEdit()
        self.mark_edit.setPlaceholderText(t("ewa.restore.mark_placeholder"))
        mark_row.addWidget(self.mark_edit, 1)
        mark_btn = QPushButton(icon("fa5s.save", "#ffffff"),
                               t("ewa.restore.mark_btn"))
        mark_btn.setObjectName("secondaryButton")
        mark_btn.clicked.connect(self._mark_backup)
        mark_row.addWidget(mark_btn)
        layout.addLayout(mark_row)

        self.inner = QTabWidget()
        layout.addWidget(self.inner, 1)

        # --- joueurs
        players_page = QWidget()
        players_layout = QVBoxLayout(players_page)
        self.players_table = QTreeWidget()
        self.players_table.setHeaderLabels([t(k) for k in
                                            ["ewa.restore.col.name",
                                             "ewa.restore.col.steamid"]])
        players_layout.addWidget(self.players_table, 1)
        restore_player_btn = QPushButton(icon("fa5s.undo", "#ffffff"),
                                         t("ewa.restore.player_btn"))
        restore_player_btn.setObjectName("secondaryButton")
        restore_player_btn.clicked.connect(self._restore_player)
        players_layout.addWidget(restore_player_btn)
        self.inner.addTab(players_page, t("ewa.restore.tab_players"))

        # --- playfields
        playfields_page = QWidget()
        playfields_layout = QVBoxLayout(playfields_page)
        self.playfields_list = QTreeWidget()
        self.playfields_list.setHeaderLabels([t("ewa.restore.col.playfield")])
        playfields_layout.addWidget(self.playfields_list, 1)
        restore_pf_btn = QPushButton(icon("fa5s.undo", "#ffffff"),
                                     t("ewa.restore.playfield_btn"))
        restore_pf_btn.setObjectName("secondaryButton")
        restore_pf_btn.clicked.connect(self._restore_playfield)
        playfields_layout.addWidget(restore_pf_btn)
        self.inner.addTab(playfields_page, t("ewa.restore.tab_playfields"))

        self.warn_label = QLabel(t("ewa.restore.warn"))
        self.warn_label.setWordWrap(True)
        layout.addWidget(self.warn_label)

    def on_connected(self) -> None:
        self.reload_backups()

    def reload_backups(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            return self.client.get_backups()

        def _done(backups):
            self._busy = False
            self.backup_combo.clear()
            for backup in backups:
                self.backup_combo.addItem(_s(backup if not isinstance(
                    backup, dict) else pick(backup, "name", "backup",
                                            default="")))

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-backups")

    def _selected_backup(self) -> str:
        return self.backup_combo.currentText().strip()

    def _mark_backup(self) -> None:
        if self.client is None:
            return
        mark = self.mark_edit.text().strip()
        if not mark:
            return

        def _work():
            self.client.backup_mark(mark)

        def _done(_result):
            self.reload_backups()

        from gui.ewa_async import async_call
        async_call(self, _work, _done,
                   lambda error: self.dialog.show_error(error), "ewa-mark")

    def _restore_player(self) -> None:
        if self.client is None:
            return
        # capture dans le thread GUI : la combo peut etre rechargee pendant
        # l'appel, restaurer depuis un AUTRE backup est une perte de donnees
        backup = self._selected_backup()
        if not backup:
            return
        item = self.players_table.currentItem()
        if item is None:
            self._load_players_into_view()
            return
        from gui.msgboxes import ask_yes_no
        if not ask_yes_no(self, t("ewa.restore.player_title"),
                          t("ewa.restore.player_confirm", name=item.text(0))):
            return

        def _work():
            self.client.backup_restore_player(backup, item.text(1))

        from gui.ewa_async import async_call
        async_call(self, _work, None,
                   lambda error: self.dialog.show_error(error),
                   "ewa-restore-player")

    def _load_players_into_view(self) -> None:
        backup = self._selected_backup()
        if not backup:
            return

        def _work():
            return self.client.backup_read_players(backup)

        def _done(players):
            self.players_table.clear()
            for player in players or []:
                QTreeWidgetItem(self.players_table, [
                    _s(pick(player, "PlayerName")),
                    _s(pick(player, "SteamId"))])

        def _fail(error):
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-backup-players")

    def _restore_playfield(self) -> None:
        if self.client is None:
            return
        backup = self._selected_backup()
        if not backup:
            return
        item = self.playfields_list.currentItem()
        if item is None:
            self._load_playfields_into_view()
            return
        from gui.msgboxes import ask_yes_no
        if not ask_yes_no(self, t("ewa.restore.playfield_title"),
                          t("ewa.restore.playfield_confirm",
                            name=item.text(0))):
            return

        def _work():
            self.client.backup_restore_playfield(backup, item.text(0))

        from gui.ewa_async import async_call
        async_call(self, _work, None,
                   lambda error: self.dialog.show_error(error),
                   "ewa-restore-pf")

    def _load_playfields_into_view(self) -> None:
        backup = self._selected_backup()
        if not backup:
            return

        def _work():
            return self.client.backup_read_playfields(backup)

        def _done(playfields):
            self.playfields_list.clear()
            for playfield in playfields or []:
                QTreeWidgetItem(self.playfields_list, [_s(playfield)])

        def _fail(error):
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-backup-pfs")


class TimetableTab(EwaTab):
    """Planificateur : arbre des taches, execution imediate, edition JSON."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._busy = False

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.refresh_btn = QPushButton(icon("fa5s.refresh", "#ffffff"),
                                       t("ewa.timetable.refresh"))
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        run_btn = QPushButton(icon("fa5s.play", "#ffffff"),
                              t("ewa.timetable.run"))
        run_btn.setObjectName("secondaryButton")
        run_btn.clicked.connect(self._run_selected)
        top.addWidget(run_btn)
        top.addStretch()
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t(k) for k in [
            "ewa.timetable.col.repeat", "ewa.timetable.col.next",
            "ewa.timetable.col.active", "ewa.timetable.col.action",
            "ewa.timetable.col.data"]])
        splitter.addWidget(self.tree)
        self.json_edit = QPlainTextEdit()
        splitter.addWidget(self.json_edit)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        bottom = QHBoxLayout()
        save_btn = QPushButton(icon("fa5s.upload", "#ffffff"),
                               t("ewa.timetable.save"))
        save_btn.setObjectName("secondaryButton")
        save_btn.clicked.connect(self._save_json)
        bottom.addWidget(save_btn)
        bottom.addStretch()
        layout.addLayout(bottom)

    def on_connected(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            return self.client.get_timetable()

        def _done(actions):
            self._busy = False
            self.json_edit.setPlainText(
                json.dumps(actions, indent=2, ensure_ascii=False))
            self._fill_tree(actions)

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-timetable")

    def _fill_tree(self, actions: list) -> None:
        self.tree.clear()
        for action in actions or []:
            parent = QTreeWidgetItem([
                _s(pick(action, "repeat")),
                _s(pick(action, "nextExecute"))[:19],
                "", "", ""])
            for sub in pick(action, "subAction", default=[]) or []:
                QTreeWidgetItem(parent, [
                    "", "", t("ewa.timetable.yes") if pick(sub, "active")
                    else t("ewa.timetable.no"),
                    _s(pick(sub, "actionType")),
                    _s(pick(sub, "data"))[:120]])
            self.tree.addTopLevelItem(parent)
        self.tree.expandAll()

    def _run_selected(self) -> None:
        # (action, sub) resolus ICI, dans le thread GUI : toucher le tree ou
        # relire json_edit depuis le worker = course + mauvaise subAction
        # executee si le JSON a change entre le refresh et le clic
        if self.client is None or self._busy:
            return
        item = self.tree.currentItem()
        if item is None:
            return
        actions = self._current_actions()
        if item.parent() is None:
            index = self.tree.indexOfTopLevelItem(item)
            if index >= len(actions):
                return
            payload = ("all", pick(actions[index], "subAction",
                                   default=[]) or [])
        else:
            parent = self.tree.indexOfTopLevelItem(item.parent())
            if parent >= len(actions):
                return
            subs = pick(actions[parent], "subAction", default=[]) or []
            sub_index = item.parent().indexOfChild(item)
            if sub_index >= len(subs):
                return
            payload = ("sub", subs[sub_index])
        self._busy = True

        def _work():
            if payload[0] == "all":
                self.client.run_timetable(payload[1])
            else:
                self.client.run_timetable_sub(payload[1])

        def _done(_result):
            self._busy = False

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-timetable-run")

    def _current_actions(self) -> list:
        try:
            return json.loads(self.json_edit.toPlainText() or "[]")
        except json.JSONDecodeError:
            return []

    def _save_json(self) -> None:
        if self.client is None:
            return
        try:
            actions = json.loads(self.json_edit.toPlainText() or "[]")
        except json.JSONDecodeError as error:
            QMessageBox.warning(self, t("ewa.timetable.bad_json_title"),
                                t("ewa.timetable.bad_json", error=error))
            return

        def _work():
            self.client.set_timetable(actions)

        from gui.ewa_async import async_call
        async_call(self, _work, lambda _r: self.refresh(),
                   lambda error: self.dialog.show_error(error),
                   "ewa-timetable-save")
