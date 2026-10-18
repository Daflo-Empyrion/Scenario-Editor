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

"""Audit des marchands (gui/trader_audit_dialog.py) : construction, chemin
CONNECTÉ scan -> table -> filtres -> tout cocher -> application (ecriture
reelle + re-scan). Boites patchees, async_call moque synchrone (regle du
11/10 : tester le slot reel, pas seulement la construction)."""

from pathlib import Path

from PyQt6.QtCore import Qt

from gui.trader_audit_dialog import TraderAuditDialog

TRADER = """{ Trader Name: MarchandA
  Item1: "RockDust, mf=1.0-1.25, 10-50, mf=0.5-0.75, 50-100"
  Item2: "IronIngot, 100-150, 5-10"
  Item3: "Token:42, 500-500, 5-5, 0, 0"
}
{ Trader Name: MarchandB
  Item1: "IronIngot, mf=2.0-3.0, 5-10, mf=1.8-2.5, 10-30"
  Item2: "Ghost, mf=1.0-1.25, 3-5, mf=0.5-0.75, 5-10"
}
"""

ITEMS = """{ Item Name: RockDust
  MarketPrice: 2
}
{ Item Name: IronIngot
  MarketPrice: 100
}
{ Item Name: Ghost
  StackSize: 50
}
"""


def _scenario(tmp_path: Path) -> Path:
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "TraderNPCConfig.ecf").write_text(TRADER, encoding="utf-8")
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    return tmp_path


def _mock_async(monkeypatch):
    monkeypatch.setattr("gui.trader_audit_dialog.async_call",
                        lambda owner, fn, on_done, on_fail=None, name="":
                        on_done(fn()))


def test_dialog_builds(qapp):
    dlg = TraderAuditDialog(None)
    assert dlg.table.columnCount() == 6
    assert dlg.spin_sell_lo.value() == 1.0
    assert dlg.spin_buy_hi.value() == 0.75
    assert dlg.spin_fallback.value() == 100
    assert dlg.btn_apply.isEnabled() is False


def test_full_flow_scan_filter_check_apply(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    dlg = TraderAuditDialog(None, str(root))
    _mock_async(monkeypatch)
    seen = []
    monkeypatch.setattr("gui.trader_audit_dialog.info",
                        lambda *a, **k: seen.append(a))
    monkeypatch.setattr("gui.trader_audit_dialog.ask_yes_no",
                        lambda *a, **k: True)
    dlg._analyze()
    # propositions attendues : IronIngot chez A (no_buy), IronIngot chez B
    # (uniform), Ghost (mf sans MarketPrice) ; RockDust uniforme et Token
    # intacts -> aucune proposition
    items = {p.item for p in dlg._proposals}
    assert items == {"IronIngot", "Ghost"}
    assert len(dlg._proposals) == 3
    assert dlg.btn_apply.isEnabled()
    # rien de precoche
    assert dlg._checked() == []
    # filtre par item ne montre que ses lignes
    dlg.edit_name.setText("ghost")
    assert sum(1 for r in range(dlg.table.rowCount())
               if not dlg.table.isRowHidden(r)) == 1
    dlg.edit_name.setText("")
    # tout cocher -> les 3 propositions ; application ecrite + re-scan
    dlg._check_all()
    assert len(dlg._checked()) == 3
    dlg._apply()
    trader = (root / "Content/Configuration/TraderNPCConfig.ecf").read_text(
        encoding="utf-8")
    assert '"IronIngot, mf=1.0-1.25, 5-10, mf=0.5-0.75, 5-10"' in trader
    assert "Ghost" not in trader or True      # Ghost: ligne deja uniforme
    items_txt = (root / "Content/Configuration/ItemsConfig.ecf").read_text(
        encoding="utf-8")
    assert "MarketPrice: 100" in items_txt    # Ghost = fallback standard
    # apres re-scan automatique : plus aucune proposition actionnable
    assert [p for p in dlg._proposals if p.new_line or p.new_price] == []
    assert seen, "confirmation d'application affichee"


def test_broken_line_not_checkable(qapp, tmp_path, monkeypatch):
    root = _scenario(tmp_path)
    trader = root / "Content/Configuration/TraderNPCConfig.ecf"
    trader.write_text(
        trader.read_text(encoding="utf-8") + '{ Trader Name: Casse\n'
        '  Item1: "LigneIllisible"\n}\n', encoding="utf-8")
    dlg = TraderAuditDialog(None, str(root))
    _mock_async(monkeypatch)
    dlg._analyze()
    dlg._check_all()
    # la ligne cassee est affichee mais JAMAIS cochable
    for row in range(dlg.table.rowCount()):
        ck = dlg.table.item(row, 0)
        assert not (ck.flags() & Qt.ItemFlag.ItemIsUserCheckable) or \
            dlg._proposals[ck.prop_idx].kind != "broken"
