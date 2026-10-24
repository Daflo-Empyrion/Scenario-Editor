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
Fournisseurs IA (v1.17.0, 20/10/2026) : registre de comptes OpenAI-compatibles
(OpenRouter, Groq, DeepSeek direct, Mistral, Unsloth/Ollama locaux, URL
personnalisee), maillons ordonnes free/payant, plafond budget et test reel.

Presets : le bouton Ajouter pre-remplit le compte et la boucle free OpenRouter.
Tout ce qui est reseau passe par run_long (jamais dans le thread GUI).
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from core import settings
from core.ai import budget, providers, router
from core.i18n import t
from gui.theme import icon


class AiProvidersDialog(QDialog):
    """Comptes, maillons et budget des fournisseurs IA."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("ai.title"))
        self.setMinimumWidth(820)
        self.resize(900, 700)
        from gui.window_geometry import track
        track(self, "ai_providers")

        self.providers = settings.get_ai_providers()
        self.links = settings.get_ai_links()
        self._catalog = {}          # provider id -> [modeles normalises]
        self._prices = {}           # (provider id, modele) -> (in, out) $/M
        self._current = -1
        self._loading = False
        for link in self.links:
            try:
                self._prices[(link.get("provider"), link.get("model"))] = (
                    float(link.get("price_in") or 0.0),
                    float(link.get("price_out") or 0.0))
            except (TypeError, ValueError):
                pass

        layout = QVBoxLayout(self)
        intro = QLabel(t("ai.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # --- comptes ---------------------------------------------------------
        row = QHBoxLayout()
        row.addWidget(QLabel(t("ai.provider_label")))
        self.provider_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self._select_provider)
        row.addWidget(self.provider_combo, 1)
        self.btn_add = QPushButton(icon("fa5s.plus", "#ffffff"), t("ai.add"))
        self.btn_add.setObjectName("secondaryButton")
        self.btn_add.clicked.connect(self._menu_add)
        row.addWidget(self.btn_add)
        self.btn_remove = QPushButton(t("ai.remove"))
        self.btn_remove.setObjectName("secondaryButton")
        self.btn_remove.clicked.connect(self._remove_provider)
        row.addWidget(self.btn_remove)
        layout.addLayout(row)

        order_row = QHBoxLayout()
        self.btn_up = QPushButton(t("ai.up"))
        self.btn_up.setObjectName("secondaryButton")
        self.btn_up.clicked.connect(lambda: self._move_provider(-1))
        order_row.addWidget(self.btn_up)
        self.btn_down = QPushButton(t("ai.down"))
        self.btn_down.setObjectName("secondaryButton")
        self.btn_down.clicked.connect(lambda: self._move_provider(1))
        order_row.addWidget(self.btn_down)
        order_row.addStretch()
        layout.addLayout(order_row)

        form = QFormLayout()
        self.field_label = QLineEdit()
        self.field_label.editingFinished.connect(self._save_fields)
        form.addRow(t("ai.field_label"), self.field_label)
        self.field_url = QLineEdit()
        self.field_url.editingFinished.connect(self._save_fields)
        form.addRow(t("ai.field_url"), self.field_url)
        key_row = QHBoxLayout()
        self.field_key = QLineEdit()
        self.field_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.field_key.editingFinished.connect(self._save_fields)
        key_row.addWidget(self.field_key, 1)
        self.btn_verify = QPushButton(icon("fa5s.check", "#ffffff"),
                                      t("ai.verify"))
        self.btn_verify.setObjectName("secondaryButton")
        self.btn_verify.clicked.connect(self._verify)
        key_row.addWidget(self.btn_verify)
        form.addRow(t("ai.field_key"), key_row)
        self.kind_combo = QComboBox()
        self.kind_combo.addItem(t("ai.kind_free"), "free")
        self.kind_combo.addItem(t("ai.kind_paid"), "paid")
        self.kind_combo.addItem(t("ai.kind_mixed"), "mixed")
        self.kind_combo.currentIndexChanged.connect(self._save_fields)
        form.addRow(t("ai.field_kind"), self.kind_combo)
        self.field_cap = QDoubleSpinBox()
        self.field_cap.setRange(0.0, 100000.0)
        self.field_cap.setDecimals(2)
        self.field_cap.setSuffix(" $")
        self.field_cap.setToolTip(t("ai.field_cap_tip"))
        self.field_cap.valueChanged.connect(self._save_fields)
        form.addRow(t("ai.field_cap"), self.field_cap)
        layout.addLayout(form)
        self.verify_status = QLabel("")
        self.verify_status.setWordWrap(True)
        layout.addWidget(self.verify_status)

        # --- modeles ---------------------------------------------------------
        models_box = QGroupBox(t("ai.models_label"))
        models_layout = QVBoxLayout(models_box)
        self.model_list = QListWidget()
        self.model_list.itemChanged.connect(self._model_toggled)
        self.model_list.currentItemChanged.connect(self._model_selected)
        models_layout.addWidget(self.model_list)
        model_row = QHBoxLayout()
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText(t("ai.model_placeholder"))
        model_row.addWidget(self.model_edit, 1)
        self.btn_add_model = QPushButton(t("ai.add_model"))
        self.btn_add_model.setObjectName("secondaryButton")
        self.btn_add_model.clicked.connect(self._add_model)
        model_row.addWidget(self.btn_add_model)
        self.btn_refresh = QPushButton(icon("fa5s.sync", "#ffffff"),
                                       t("ai.refresh"))
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.clicked.connect(self._refresh)
        model_row.addWidget(self.btn_refresh)
        models_layout.addLayout(model_row)
        price_row = QHBoxLayout()
        price_row.addWidget(QLabel(t("ai.price_in")))
        self.price_in = QDoubleSpinBox()
        self.price_in.setRange(0.0, 10000.0)
        self.price_in.setDecimals(4)
        self.price_in.setSuffix(" $/M")
        price_row.addWidget(self.price_in)
        price_row.addWidget(QLabel(t("ai.price_out")))
        self.price_out = QDoubleSpinBox()
        self.price_out.setRange(0.0, 10000.0)
        self.price_out.setDecimals(4)
        self.price_out.setSuffix(" $/M")
        price_row.addWidget(self.price_out)
        price_row.addWidget(QLabel(t("ai.price_tip")))
        price_row.addStretch()
        models_layout.addLayout(price_row)
        self.price_in.valueChanged.connect(self._price_changed)
        self.price_out.valueChanged.connect(self._price_changed)
        layout.addWidget(models_box, 1)

        # --- budget / style / moteur ----------------------------------------
        budget_box = QGroupBox(t("ai.budget_label"))
        grid = QGridLayout(budget_box)
        self.paid_check = QCheckBox(t("ai.paid_enabled"))
        self.paid_check.toggled.connect(self._paid_toggled)
        grid.addWidget(self.paid_check, 0, 0, 1, 2)
        grid.addWidget(QLabel(t("ai.paid_cap")), 1, 0)
        self.cap_spin = QDoubleSpinBox()
        self.cap_spin.setRange(0.0, 100000.0)
        self.cap_spin.setDecimals(2)
        self.cap_spin.setSuffix(" $")
        self.cap_spin.valueChanged.connect(self._cap_changed)
        grid.addWidget(self.cap_spin, 1, 1)
        self.spend_label = QLabel("")
        grid.addWidget(self.spend_label, 2, 0, 1, 2)
        self.account_label = QLabel("")
        self.account_label.setWordWrap(True)
        grid.addWidget(self.account_label, 3, 0, 1, 2)
        self.btn_account = QPushButton(t("ai.account"))
        self.btn_account.setObjectName("secondaryButton")
        self.btn_account.clicked.connect(self._account)
        grid.addWidget(self.btn_account, 4, 0, 1, 2)
        layout.addWidget(budget_box)

        style_label = QLabel(t("ai.style_label"))
        layout.addWidget(style_label)
        self.style_edit = QPlainTextEdit()
        self.style_edit.setPlaceholderText(t("ai.style_placeholder"))
        self.style_edit.setFixedHeight(52)
        self.style_edit.textChanged.connect(self._style_changed)
        layout.addWidget(self.style_edit)
        self.batch_check = QCheckBox(t("ai.batch"))
        self.batch_check.toggled.connect(settings.set_ai_batch_enabled)
        layout.addWidget(self.batch_check)
        self.use_check = QCheckBox(t("ai.use_as_engine"))
        self.use_check.toggled.connect(self._toggle_engine)
        layout.addWidget(self.use_check)

        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)
        layout.addWidget(self.test_result)
        bottom = QHBoxLayout()
        self.btn_test = QPushButton(icon("fa5s.check", "#ffffff"), t("ai.test"))
        self.btn_test.clicked.connect(self._test)
        bottom.addWidget(self.btn_test)
        bottom.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

        self._reload_provider_combo()
        self._load_global()

    # -- comptes -------------------------------------------------------------
    def _reload_provider_combo(self) -> None:
        self._loading = True
        self.provider_combo.clear()
        for provider in self.providers:
            self.provider_combo.addItem(provider.get("label")
                                        or provider.get("id"))
        self._loading = False
        if self.providers:
            self.provider_combo.setCurrentIndex(0)
            self._select_provider(0)
        else:
            self._current = -1
            self._clear_fields()

    def _clear_fields(self) -> None:
        self._loading = True
        for widget in (self.field_label, self.field_url, self.field_key):
            widget.setText("")
        self.field_cap.setValue(0.0)
        self.model_list.clear()
        self._loading = False

    def _select_provider(self, index: int) -> None:
        if self._loading:
            return
        if 0 <= self._current < len(self.providers):
            self._save_fields()
        self._current = index
        if not (0 <= index < len(self.providers)):
            self._clear_fields()
            return
        provider = self.providers[index]
        self._loading = True
        self.field_label.setText(provider.get("label", ""))
        self.field_url.setText(provider.get("base_url", ""))
        self.field_key.setText(provider.get("key", ""))
        idx = self.kind_combo.findData(provider.get("kind", "paid"))
        self.kind_combo.setCurrentIndex(max(0, idx))
        # type verrouille pour les presets connus (budget non contournable)
        self.kind_combo.setEnabled(provider.get("preset") == "custom")
        self.field_cap.setValue(float(provider.get("cap_usd") or 0.0))
        self._loading = False
        self._fill_models()

    def _save_fields(self) -> None:
        if self._loading or not (0 <= self._current < len(self.providers)):
            return
        provider = self.providers[self._current]
        provider["label"] = self.field_label.text().strip() or provider["id"]
        provider["base_url"] = self.field_url.text().strip()
        provider["key"] = self.field_key.text().strip()
        provider["kind"] = self.kind_combo.currentData() or "paid"
        provider["cap_usd"] = float(self.field_cap.value())
        settings.set_ai_providers(self.providers)
        if self.provider_combo.itemText(self._current) != provider["label"]:
            self._loading = True
            self.provider_combo.setItemText(self._current, provider["label"])
            self._loading = False
            self._build_links()
        self._notify_main()

    def _menu_add(self) -> None:
        menu = QMenu(self)
        for preset_id in providers.PRESET_ORDER:
            action = menu.addAction(providers.preset(preset_id)["label"])
            action.triggered.connect(
                lambda _checked=False, pid=preset_id: self._add_preset(pid))
        menu.exec(self.btn_add.mapToGlobal(self.btn_add.rect().bottomLeft()))

    def _add_preset(self, preset_id: str) -> None:
        if 0 <= self._current < len(self.providers):
            self._save_fields()
        provider = providers.new_provider(preset_id)
        self.providers.append(provider)
        settings.set_ai_providers(self.providers)
        self._reload_provider_combo()
        self.provider_combo.setCurrentIndex(len(self.providers) - 1)
        self._build_links()

    def _remove_provider(self) -> None:
        if not (0 <= self._current < len(self.providers)):
            return
        provider = self.providers.pop(self._current)
        self.links = [link for link in self.links
                      if link.get("provider") != provider.get("id")]
        settings.set_ai_providers(self.providers)
        settings.set_ai_links(self.links)
        self._current = -1
        self._reload_provider_combo()

    def _move_provider(self, delta: int) -> None:
        if not (0 <= self._current < len(self.providers)):
            return
        target = self._current + delta
        if not (0 <= target < len(self.providers)):
            return
        self._save_fields()
        self.providers[self._current], self.providers[target] = (
            self.providers[target], self.providers[self._current])
        settings.set_ai_providers(self.providers)
        self._current = -1
        self._reload_provider_combo()
        self.provider_combo.setCurrentIndex(target)
        self._build_links()

    # -- modeles -------------------------------------------------------------
    def _provider(self) -> dict:
        if 0 <= self._current < len(self.providers):
            return self.providers[self._current]
        return {}

    def _fill_models(self) -> None:
        provider = self._provider()
        checked = set(provider.get("models") or [])
        self._loading = True
        self.model_list.clear()
        for model in provider.get("models_order") or []:
            item = QListWidgetItem(model)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if model in checked
                               else Qt.CheckState.Unchecked)
            self.model_list.addItem(item)
        self._loading = False
        if self.model_list.count():
            self.model_list.setCurrentRow(0)

    def _model_toggled(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        provider = self._provider()
        if not provider:
            return
        checked = set(provider.get("models") or [])
        model = item.text()
        if item.checkState() == Qt.CheckState.Checked:
            checked.add(model)
        else:
            checked.discard(model)
        provider["models"] = [m for m in (provider.get("models_order") or [])
                              if m in checked]
        settings.set_ai_providers(self.providers)
        self._build_links()

    def _add_model(self) -> None:
        provider = self._provider()
        model = self.model_edit.text().strip()
        if not provider or not model:
            return
        order = provider.setdefault("models_order", [])
        if model not in order:
            order.append(model)
        models = provider.setdefault("models", [])
        if model not in models:
            models.append(model)
        self.model_edit.clear()
        settings.set_ai_providers(self.providers)
        self._fill_models()
        self._build_links()

    def _refresh(self) -> None:
        provider = self._provider()
        if not provider:
            return
        self._save_fields()
        try:
            from gui.busy import run_long
            models = run_long(self, lambda: providers.list_models(provider),
                              "ai.verifying")
        except Exception as e:
            self.verify_status.setStyleSheet("color: #b02a2a;")
            self.verify_status.setText(t("ai.verify_fail", error=e))
            return
        self._catalog[provider["id"]] = models
        for info in models:
            if info.get("price_in") is not None:
                self._prices[(provider["id"], info["id"])] = (
                    info["price_in"], info.get("price_out") or 0.0)
        order = provider.setdefault("models_order", [])
        for info in models:
            if info["id"] not in order:
                order.append(info["id"])
        settings.set_ai_providers(self.providers)
        self._fill_models()
        self._build_links()
        self.verify_status.setStyleSheet("")
        self.verify_status.setText(t("ai.verify_ok", count=len(models)))
        self._notify_main()

    def _model_selected(self, item, _previous=None) -> None:
        if item is None:
            return
        provider = self._provider()
        model = item.text()
        tier = providers.kind_tier(provider, model)
        prices = self._prices.get((provider.get("id"), model),
                                  providers.model_prices(provider, model))
        self._loading = True
        self.price_in.setValue(float(prices[0] or 0.0))
        self.price_out.setValue(float(prices[1] or 0.0))
        self.price_in.setEnabled(tier == "paid")
        self.price_out.setEnabled(tier == "paid")
        self._loading = False

    def _price_changed(self) -> None:
        if self._loading:
            return
        provider = self._provider()
        item = self.model_list.currentItem()
        if not provider or item is None:
            return
        self._prices[(provider["id"], item.text())] = (
            float(self.price_in.value()), float(self.price_out.value()))
        self._build_links()

    def _build_links(self) -> None:
        """Reconstruit les maillons : ordre des comptes, puis de leurs
        modeles. L'ordre du registre EST la priorite de repli."""
        links = []
        for provider in self.providers:
            checked = provider.get("models") or []
            for model in provider.get("models_order") or []:
                if model not in checked:
                    continue
                tier = providers.kind_tier(provider, model)
                price_in, price_out = self._prices.get(
                    (provider["id"], model),
                    providers.model_prices(provider, model))
                links.append({
                    "provider": provider["id"],
                    "model": model,
                    "tier": tier,
                    "price_in": float(price_in or 0.0),
                    "price_out": float(price_out or 0.0),
                    "enabled": True,
                })
        self.links = links
        settings.set_ai_links(links)

    def _verify(self) -> None:
        self._save_fields()
        self._refresh()

    # -- budget / style / moteur --------------------------------------------
    def _load_global(self) -> None:
        self._loading = True
        self.paid_check.setChecked(settings.get_ai_paid_enabled())
        self.cap_spin.setValue(settings.get_ai_monthly_cap_usd())
        self.style_edit.setPlainText(settings.get_ai_style())
        self.batch_check.setChecked(settings.get_ai_batch_enabled())
        self.use_check.setChecked(settings.get_translation_engine() == "ai")
        self._loading = False
        self._refresh_spend()

    def _refresh_spend(self) -> None:
        summary = budget.summary()
        self.spend_label.setText(t(
            "ai.paid_spend", spent=f"{summary['total']:.2f}",
            cap=f"{summary['cap']:.2f}", month=summary["month"]))
        self.spend_label.setStyleSheet("")
        if summary["cap"] > 0 and summary["total"] >= summary["cap"]:
            self.spend_label.setStyleSheet("color: #b02a2a;")

    def _paid_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        settings.set_ai_paid_enabled(checked)

    def _cap_changed(self, value: float) -> None:
        if self._loading:
            return
        settings.set_ai_monthly_cap_usd(value)
        self._refresh_spend()

    def _style_changed(self) -> None:
        if not self._loading:
            settings.set_ai_style(self.style_edit.toPlainText())

    def _toggle_engine(self, checked: bool) -> None:
        if self._loading:
            return
        settings.set_translation_engine("ai" if checked else "google")
        self._notify_main()

    def _notify_main(self) -> None:
        mw = self.parent()
        if mw is not None and hasattr(mw, "_refresh_engine_menu"):
            mw._refresh_engine_menu()

    def _account(self) -> None:
        provider = self._provider()
        if not provider:
            return
        self._save_fields()
        try:
            from gui.busy import run_long
            info = run_long(self, lambda: providers.account_info(provider),
                            "ai.verifying")
        except Exception as e:
            self.account_label.setStyleSheet("color: #b02a2a;")
            self.account_label.setText(t("ai.account_fail", error=e))
            return
        self.account_label.setStyleSheet("")
        self.account_label.setText(info or t("ai.account_none"))

    def _test(self) -> None:
        self._save_fields()
        self._build_links()
        self.test_result.setStyleSheet("color: gray;")
        self.test_result.setText(t("ai.testing"))
        try:
            from gui.busy import run_long
            result = run_long(self, router.quick_check, "ai.testing")
        except Exception as e:
            self.test_result.setStyleSheet("color: #b02a2a;")
            self.test_result.setText(t("ai.test_fail", error=e))
            return
        budget.flush()
        self.test_result.setStyleSheet("")
        self.test_result.setText(t("ai.test_ok", result=result))
        self._refresh_spend()

    def closeEvent(self, event):
        """La saisie de cle ne doit pas etre perdue si la fenetre est fermee
        sans focus-out (editingFinished ne se declenche pas toujours)."""
        self._save_fields()
        self._build_links()
        budget.flush()
        super().closeEvent(event)
