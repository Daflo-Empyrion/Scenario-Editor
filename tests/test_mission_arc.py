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

"""Missions « Anomalie » : passe idempotente sur PDA.yaml + PDA.csv."""
from pathlib import Path

import pytest

PDA_MIN = (
    "Chapters:\n"
    "  - ChapterTitle: pda_old01\n"
    "    Category: FAQ\n"
    "    Description: pda_old02\n"
    "Creator: \"Test\"\n"
)
PDA_CSV_MIN = (
    "KEY,English,Deutsch,Fran\u00e7ais\n"
    "pda_old01,Old title,,\n"
    "pda_old02,Old text,,\n"
)

MISSION = {
    "id": "Ano9",
    "title": ("The Vault", "Le coffre"),
    "desc": ("Find the code.", "Trouve le code."),
    "activation": {"check": "DayNightChange", "names": ["Sunset"],
                   "notify": "pda_Ano9Title"},
    "tasks": ({"title": ("Enter", "Entrer"),
               "actions": ({"title": ("Open it", "L'ouvrir"),
                            "desc": ("Code found.", "Code trouve."),
                            "check": "DeviceUnlock", "names": ["Door01"],
                            "trigger_distance": 30, "invisible": True},)},),
    "rewards": ({"type": "XP", "count": 50},),
    "done": ("Done.", "Termine."),
}


def _scenario(tmp_path) -> Path:
    sc = tmp_path / "RE2-TEST"
    pda = sc / "Extras" / "PDA"
    pda.mkdir(parents=True)
    (pda / "PDA.yaml").write_text(PDA_MIN, encoding="utf-8")
    (pda / "PDA.csv").write_text(PDA_CSV_MIN, encoding="utf-8")
    return sc


def test_mission_added_once(tmp_path, monkeypatch):
    """Chapitre pose avec ses leviers (activation, action sans Check,
    distances, invisible), textes EN+FR en colonne Francais, et un 2e
    passage ne fait rien."""
    from core import mission_arc as ma
    monkeypatch.setattr(ma, "MISSIONS", (MISSION,))
    monkeypatch.setattr(ma, "MISSION_ARC", True)
    sc = _scenario(tmp_path)
    rep = ma.pass_mission_arc(sc, apply=True)
    assert rep["edits"] == 1 + 7 and rep["files"] == 2, rep

    yaml_txt = (sc / "Extras" / "PDA" / "PDA.yaml").read_text("utf-8")
    assert yaml_txt.count("  - ChapterTitle: ") == 2      # existant + la notre
    assert "ChapterActivation:" in yaml_txt and "Check: DayNightChange" in yaml_txt
    assert "IsInvisible: true" in yaml_txt
    assert "TriggerDistance: 30" in yaml_txt
    assert "Check: DeviceUnlock" in yaml_txt
    assert yaml_txt.index("pda_Ano9Title") > yaml_txt.index("pda_old01")

    csv_txt = (sc / "Extras" / "PDA" / "PDA.csv").read_text("utf-8")
    ligne = next(l for l in csv_txt.splitlines() if l.startswith("pda_Ano9Title,"))
    assert ligne.split(",")[3] == "Le coffre"             # colonne Francais
    assert ma.pass_mission_arc(sc, apply=True)["edits"] == 0


def test_mission_updated_when_definition_changes(tmp_path, monkeypatch):
    """Un texte modifie dans MISSIONS met le chapitre a jour (remplacement,
    pas de doublon) — sinon on ne pourrait jamais corriger une mission."""
    from core import mission_arc as ma
    monkeypatch.setattr(ma, "MISSIONS", (MISSION,))
    monkeypatch.setattr(ma, "MISSION_ARC", True)
    sc = _scenario(tmp_path)
    ma.pass_mission_arc(sc, apply=True)
    change = dict(MISSION, rewards=({"type": "XP", "count": 99},))
    monkeypatch.setattr(ma, "MISSIONS", (change,))
    assert ma.pass_mission_arc(sc, apply=True)["edits"] == 1
    yaml_txt = (sc / "Extras" / "PDA" / "PDA.yaml").read_text("utf-8")
    assert yaml_txt.count("  - ChapterTitle: ") == 2
    assert "Count: 99" in yaml_txt


def test_no_missions_is_a_noop(tmp_path, monkeypatch):
    """Aucune mission declaree : rien a ajouter, rien a retirer."""
    from core import mission_arc as ma
    monkeypatch.setattr(ma, "MISSIONS", ())
    monkeypatch.setattr(ma, "MISSION_ARC", True)
    sc = _scenario(tmp_path)
    rep = ma.pass_mission_arc(sc, apply=True)
    assert rep["edits"] == 0 and "rien a retirer" in " ".join(rep["details"])


def test_real_mission_content_is_complete():
    """Garde-fou de contenu : A1 doit porter les leviers annonces dans le plan
    (compte a rebours HUD, briefing plein ecran, outil en main) et un jeton
    CSV pour chaque texte."""
    from core import mission_arc as ma
    bloc = ma._chapter(ma.MISSIONS[0])
    # tache 2 = destruction du noyau : il n'y a pas de serrure dans Empyrion
    # et le noyau interdit la recuperation au multi-outil (vecu 12/11).
    for attendu in ("SetTimer: 600", "TimerRate: 1", "Preamble: pda_Ano1Pre",
                    "Check: BlockDestroyed", "Types:", "- CoreNPC",
                    "Names:", "- ConflictStarterMine",
                    "NotifyMessage: pda_Ano1Notify",
                    "CompletedSound: Sounds/Misc/DroneSignalBad"):
        assert attendu in bloc, attendu
    cles = [c for c, _en, _fr in ma._rows(ma.MISSIONS[0])]
    assert len(cles) == len(set(cles))                   # pas de doublon
    for cle in cles:
        assert cle in bloc or cle.endswith(("Notify", "Pre")), cle
    assert all(fr and fr != "None" for _c, _e, fr in ma._rows(ma.MISSIONS[0]))


def test_disabling_the_chain_removes_the_chapter(tmp_path, monkeypatch):
    """Chaine desactivee (MISSION_ARC False) : le chapitre DEJA pose doit etre
    retire, sinon la planete de depart reste surchargee (demande 12/12)."""
    from core import mission_arc as ma
    monkeypatch.setattr(ma, "MISSIONS", (MISSION,))
    monkeypatch.setattr(ma, "MISSION_ARC", True)
    sc = _scenario(tmp_path)
    ma.pass_mission_arc(sc, apply=True)
    yaml_path = sc / "Extras" / "PDA" / "PDA.yaml"
    assert "pda_Ano9Title" in yaml_path.read_text("utf-8")

    monkeypatch.setattr(ma, "MISSION_ARC", False)
    rep = ma.pass_mission_arc(sc, apply=True)
    assert rep["edits"] > 0 and rep["files"] == 2, rep
    texte = yaml_path.read_text("utf-8")
    assert "pda_Ano9Title" not in texte
    assert texte.count("  - ChapterTitle: ") == 1          # le chapitre d'origine
    csv_txt = (sc / "Extras" / "PDA" / "PDA.csv").read_text("utf-8")
    assert "pda_Ano9" not in csv_txt
    assert ma.pass_mission_arc(sc, apply=True)["edits"] == 0   # idempotent
