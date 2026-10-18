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
"""Onglets JOUEURS (liste, fiche, note, ban/kick/wipe, credits, item) et
CHAT (polling OData + envoi via telnet SAY serveur -- l'impersonnalisation
« chat-as » reste propre au hub SignalR du web EWA)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.ewa.client import pick
from core.i18n import t
from gui.ewa_dialog import EwaTab
from gui.theme import icon


def _s(value) -> str:
    return "" if value is None else str(value)


def _chat_key(chat) -> tuple:
    """Identite d'un message (OData ne donne pas d'Id stable)."""
    return (_s(pick(chat, "Timestamp")), _s(pick(chat, "PlayerName")),
            _s(pick(chat, "Message")))


class PlayersTab(EwaTab):
    """Liste des joueurs du serveur + fiche + actions d'administration."""

    POLL_SECONDS = 12
    COLUMNS = ["ewa.players.col.name", "ewa.players.col.online",
               "ewa.players.col.playfield", "ewa.players.col.ping",
               "ewa.players.col.faction", "ewa.players.col.credits",
               "ewa.players.col.steamid"]

    def __init__(self, dialog):
        super().__init__(dialog)
        self._players: list = []
        self._view: list = []
        self._busy = False

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.refresh_btn = QPushButton(icon("fa5s.refresh", "#ffffff"),
                                       t("ewa.players.refresh"))
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(t("ewa.players.filter"))
        self.filter_edit.textChanged.connect(self._render_table)
        top.addWidget(self.filter_edit, 1)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([t(k) for k in self.COLUMNS])
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._fill_details)
        splitter.addWidget(self.table)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        self.detail_values: dict = {}
        for key, label_key in [("health", "ewa.players.d_health"),
                               ("food", "ewa.players.d_food"),
                               ("oxygen", "ewa.players.d_oxygen"),
                               ("stamina", "ewa.players.d_stamina"),
                               ("kills", "ewa.players.d_kills"),
                               ("deaths", "ewa.players.d_deaths"),
                               ("exp", "ewa.players.d_exp"),
                               ("last", "ewa.players.d_last")]:
            value_label = QLabel("")
            self.detail_values[key] = value_label
            row = QHBoxLayout()
            row.addWidget(QLabel(t(label_key)))
            row.addWidget(value_label, 1)
            side_layout.addLayout(row)
        note_label = QLabel(t("ewa.players.note"))
        side_layout.addWidget(note_label)
        self.note_edit = QPlainTextEdit()
        self.note_edit.setMaximumHeight(80)
        side_layout.addWidget(self.note_edit)
        save_note_btn = QPushButton(t("ewa.players.note_save"))
        save_note_btn.setObjectName("secondaryButton")
        save_note_btn.clicked.connect(self._save_note)
        side_layout.addWidget(save_note_btn)

        actions = QHBoxLayout()
        for icon_name, label_key, handler in [
                ("fa5s.sign-out-alt", "ewa.players.kick", self._kick),
                ("fa5s.gavel", "ewa.players.ban1h", self._ban_1h),
                ("fa5s.gavel", "ewa.players.ban1d", self._ban_1d),
                ("fa5s.undo", "ewa.players.unban", self._unban),
                ("fa5s.skull", "ewa.players.wipe", self._wipe),
                ("fa5s.coins", "ewa.players.credits", self._set_credits),
                ("fa5s.gift", "ewa.players.item", self._add_item)]:
            button = QPushButton(icon(icon_name, "#ffffff"), t(label_key))
            button.setObjectName("secondaryButton")
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        side_layout.addLayout(actions)
        side_layout.addStretch()
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    # --------------------------------------------------------------- donnees

    def on_connected(self) -> None:
        self.refresh()

    def on_visible_tick(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            return self.client.get_players()

        def _done(players):
            self._busy = False
            self._players = players or []
            self._render_table()

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-players")

    def _selected_player(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._view):
            return None
        return self._view[row]

    # ---------------------------------------------------------------- table

    def _render_table(self) -> None:
        # le polling reconstruit la table : la selection (par ligne) peut
        # desormais designer un AUTRE joueur -- on re-synchronise par SteamId
        selected_id = _s(pick(self._selected_player() or {}, "SteamId"))
        needle = self.filter_edit.text().strip().lower()
        self._view = [
            player for player in self._players
            if not needle
            or needle in _s(pick(player, "PlayerName")).lower()
            or needle in _s(pick(player, "SteamId")).lower()]
        self.table.setRowCount(len(self._view))
        for row_index, player in enumerate(self._view):
            online = pick(player, "Online") is True
            values = [
                _s(pick(player, "PlayerName")),
                t("ewa.players.online_yes") if online
                else t("ewa.players.online_no"),
                _s(pick(player, "Playfield")),
                _s(pick(player, "Ping")),
                _s(pick(player, "FactionId")),
                _s(pick(player, "Credits")),
                _s(pick(player, "SteamId")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 1 and online:
                    item.setForeground(Qt.GlobalColor.darkGreen)
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()
        if selected_id:
            for row_index, player in enumerate(self._view):
                if _s(pick(player, "SteamId")) == selected_id:
                    self.table.selectRow(row_index)   # rearme _fill_details
                    return
        # joueur disparu ou pas de selection : re-synchronise le detail
        # avec la ligne encore surlignee (sinon detail et surlignage divergent)
        self._fill_details()

    # --------------------------------------------------------------- details

    def _fill_details(self) -> None:
        player = self._selected_player()
        if player is None:
            return
        pairs = [
            ("health", f"{_s(pick(player, 'Health'))} / "
                       f"{_s(pick(player, 'HealthMax'))}"),
            ("food", f"{_s(pick(player, 'Food'))} / "
                     f"{_s(pick(player, 'FoodMax'))}"),
            ("oxygen", f"{_s(pick(player, 'Oxygen'))} / "
                       f"{_s(pick(player, 'OxygenMax'))}"),
            ("stamina", f"{_s(pick(player, 'Stamina'))} / "
                        f"{_s(pick(player, 'StaminaMax'))}"),
            ("kills", _s(pick(player, "Kills"))),
            ("deaths", _s(pick(player, "Died"))),
            ("exp", _s(pick(player, "Exp"))),
            ("last", _s(pick(player, "LastOnline"))),
        ]
        for key, value in pairs:
            self.detail_values[key].setText(value)
        self.note_edit.setPlainText(_s(pick(player, "Note")))

    def _save_note(self) -> None:
        player = self._selected_player()
        if player is None or self.client is None:
            return
        steam_id = _s(pick(player, "SteamId"))
        note = self.note_edit.toPlainText()

        def _work():
            self.client.save_player_note(steam_id, note)

        from gui.ewa_async import async_call
        async_call(self, _work, None,
                   lambda error: self.dialog.show_error(error), "ewa-note")

    # -------------------------------------------------------------- actions

    def _guard(self) -> dict | None:
        if self.client is None:
            self.dialog.show_error(t("ewa.main.not_connected"))
            return None
        player = self._selected_player()
        if player is None:
            return None
        return player

    def _confirmed(self, player, title_key: str, msg_key: str) -> bool:
        from gui.msgboxes import ask_yes_no
        return ask_yes_no(self, t(title_key),
                          t(msg_key, name=_s(pick(player, "PlayerName"))))

    def _kick(self) -> None:
        player = self._guard()
        if player is None or not self._confirmed(
                player, "ewa.players.kick_title", "ewa.players.kick_confirm"):
            return

        def _work():
            self.client.kick_player(_s(pick(player, "SteamId")))

        self._run_action(_work)

    def _ban_1h(self) -> None:
        player = self._guard()
        if player is None or not self._confirmed(
                player, "ewa.players.ban_title", "ewa.players.ban_confirm"):
            return

        def _work():
            self.client.ban_player(_s(pick(player, "SteamId")), "1h")

        self._run_action(_work)

    def _ban_1d(self) -> None:
        player = self._guard()
        if player is None or not self._confirmed(
                player, "ewa.players.ban_title", "ewa.players.ban_confirm"):
            return

        def _work():
            self.client.ban_player(_s(pick(player, "SteamId")), "1d")

        self._run_action(_work)

    def _unban(self) -> None:
        player = self._guard()
        if player is None or not self._confirmed(
                player, "ewa.players.unban_title", "ewa.players.unban_confirm"):
            return

        def _work():
            self.client.unban_player(_s(pick(player, "SteamId")))

        self._run_action(_work)

    def _wipe(self) -> None:
        player = self._guard()
        if player is None:
            return
        from gui.msgboxes import ask_yes_no
        name = _s(pick(player, "PlayerName"))
        if not ask_yes_no(self, t("ewa.players.wipe_title"),
                          t("ewa.players.wipe_confirm", name=name)):
            return

        def _work():
            self.client.wipe_player(_s(pick(player, "SteamId")))

        self._run_action(_work)

    def _set_credits(self) -> None:
        player = self._guard()
        if player is None:
            return
        entity_id = pick(player, "EntityId", default=0) or 0
        current = int(pick(player, "Credits", default=0) or 0)
        amount, ok = QInputDialog.getInt(
            self, t("ewa.players.credits_title"), t("ewa.players.credits_ask"),
            current, -2_000_000_000, 2_000_000_000)
        if not ok:
            return

        def _work():
            self.client.set_player_credits(int(entity_id), int(amount))

        self._run_action(_work)

    def _add_item(self) -> None:
        player = self._guard()
        if player is None:
            return
        entity_id = pick(player, "EntityId", default=0) or 0
        item_id, ok = QInputDialog.getInt(
            self, t("ewa.players.item_title"), t("ewa.players.item_id"),
            1, 1, 100000)
        if not ok:
            return
        count, ok = QInputDialog.getInt(
            self, t("ewa.players.item_title"), t("ewa.players.item_count"),
            1, 1, 100000)
        if not ok:
            return

        def _work():
            self.client.add_item_to_player(int(entity_id), int(item_id),
                                           int(count))

        self._run_action(_work)

    def _run_action(self, work) -> None:
        if self._busy:
            return            # anti double-clic : kick/item x2 non idempotents
        self._busy = True

        def _done(_result):
            self._busy = False

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, work, _done, _fail, "ewa-action")


class ChatTab(EwaTab):
    """Chat du serveur : lecture (OData, polling) + envoi (telnet SAY)."""

    POLL_SECONDS = 4
    MAX_MESSAGES = 500

    def __init__(self, dialog):
        super().__init__(dialog)
        self._messages: list = []
        self._busy = False

        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        self.hide_serv_check = QCheckBox(t("ewa.chat.hide_serv"))
        self.hide_serv_check.setChecked(True)
        self.hide_serv_check.toggled.connect(self._render)
        filters.addWidget(self.hide_serv_check)
        self.hide_cmd_check = QCheckBox(t("ewa.chat.hide_cmd"))
        self.hide_cmd_check.setChecked(True)
        self.hide_cmd_check.toggled.connect(self._render)
        filters.addWidget(self.hide_cmd_check)
        filters.addStretch()
        layout.addLayout(filters)

        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        layout.addWidget(self.list_widget, 1)

        self.hint_label = QLabel(t("ewa.chat.hint"))
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(t("ewa.chat.placeholder"))
        self.input_edit.returnPressed.connect(self._send)
        row.addWidget(self.input_edit, 1)
        self.send_btn = QPushButton(icon("fa5s.paper-plane", "#ffffff"),
                                    t("ewa.chat.send"))
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)
        layout.addLayout(row)

    # -------------------------------------------------------------- lecture

    def on_connected(self) -> None:
        self._poll()

    def on_visible_tick(self) -> None:
        self._poll()

    def _poll(self) -> None:
        if self._busy or self.client is None:
            return
        self._busy = True

        def _work():
            return self.client.get_chats(top=200)

        def _done(chats):
            self._busy = False
            if not chats:
                return
            # OData renvoie TOUJOURS les 200 derniers : sans dedup, chaque
            # poll re-extend les memes messages et sature l'historique
            seen = {_chat_key(chat) for chat in self._messages}
            fresh = []
            for chat in chats:
                key = _chat_key(chat)
                if key not in seen:
                    seen.add(key)
                    fresh.append(chat)
            if fresh:
                self._messages.extend(fresh)
                self._messages = self._messages[-self.MAX_MESSAGES:]
                self._render()

        def _fail(error):
            self._busy = False
            self.dialog.show_error(error)

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-chat")

    def _render(self) -> None:
        self.list_widget.clear()
        hide_serv = self.hide_serv_check.isChecked()
        hide_cmd = self.hide_cmd_check.isChecked()
        for chat in reversed(self._messages):
            faction = _s(pick(chat, "FactionName"))
            message = _s(pick(chat, "Message"))
            if hide_serv and faction == "SERV":
                continue
            if hide_cmd and (message.startswith("\\") or message.startswith("/")):
                continue
            when = _s(pick(chat, "Timestamp")).split("T")[-1][:5]
            author = _s(pick(chat, "PlayerName"))
            item = QListWidgetItem(f"{when} [{faction}] {author} : {message}")
            self.list_widget.addItem(item)
        self.list_widget.scrollToBottom()

    # --------------------------------------------------------------- envoi

    def _send(self) -> None:
        """Envoi global (SAY serveur, meme chemin que ChatManager d'EWA) --
        hors thread GUI : la connexion telnet peut attendre l'invite."""
        if not self.send_btn.isEnabled():
            return            # double Entree = double worker = double SAY
        message = self.input_edit.text().strip()
        if not message:
            return
        self.send_btn.setEnabled(False)
        dialog = self.dialog

        def _work():
            from core.ewa import config as ewa_config
            from core.ewa.telnet import say_command
            telnet = dialog.telnet_console()
            if not telnet.connected:
                cfg = ewa_config.load().get("telnet", {})
                telnet.connect(cfg.get("host", ""),
                               int(cfg.get("port", 0) or 0),
                               cfg.get("password", ""))
            telnet.send_command(say_command(message))

        def _done(_result):
            self.send_btn.setEnabled(True)
            self.input_edit.clear()

        def _fail(error):
            self.send_btn.setEnabled(True)
            dialog.drop_telnet()
            self.hint_label.setText(t("ewa.chat.send_fail", error=error))

        from gui.ewa_async import async_call
        async_call(self, _work, _done, _fail, "ewa-chat-send")
