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

"""Starters : marqueur de depart, kit 4 niveaux, fiche du menu Nouvelle partie.

Le corpus fait foi : marqueur dans le 4e champ (`..., Starter_X,'Human:1',
'', '', '']`, sans espace avant), kit dans `POIs > FixedPlayerStart` en
`Mode: Survival`, fiche inseree devant la `Description`.
"""
from pathlib import Path

from core.starters import (AKUA_ITEMS, MARKER, StartKit, clear_starts,
                           find_planets, prepend_start_card, preview_markers,
                           read_kit, set_starts, write_kit)

SECTORS = """SolarSystems:
  - Name: Alpha
    StarClass: GStartingSystem
    Sectors:
      - Coordinates: [0, 0, 0]
        SectorMapType: None
        Playfields:
          - ['0,0,0', Alpha, SunRandom, '']
      - Coordinates: [28, 0, -77]
        SectorMapType: GasGiant
        Playfields:
          - ['0, 0, 0', Alpha I, GasGiant,'', '', 'JupiterYellow', '12']
      - Coordinates: [30, 0, 30]
        Color: '0.5,0.5,0.5'
        Playfields:
          - ['0, 0, 0', Eden, EdenOcean2, '', '', '', '']
          - ['0,0,0', Eden Sector, Start_OrbitEasy, '']
      - Coordinates: [40, 0, 40]
        Color: '0.04,0.8,0.4'
        Playfields:
          - ['0, 0, 0', Akua, Starter_Akua_V2,'Human:1', '', '', '']
          - ['0,0,0', Akua Sector, Start_OrbitEasy, '']
"""

# planete normale : Description simple + un seul depart (Debug) dans les POIs
PLAIN = """---
# Playfield Configuration
Description: "Difficulty: Hard \\n\\nVast oceans cover the planet."

PlanetType: Ocean
PlayfieldType: Planet

POIs:
    Random:
      - GroupName: AnyPOI
        CountMinMax: [ 1, 1 ]

    FixedPlayerStart:
        - Mode: Debug
          Pos: [ 0, 147, 0 ]
          RotY: 160

# Section suivante du fichier
Autre: 1
"""

# depart du corpus : Survival avec listes ecrites sur plusieurs lignes
STARTER = """---
# Playfield Configuration
Description: "Difficulty: Easy."

PlanetType: TemperateStarter
PlayfieldType: Planet

POIs:
    FixedPlayerStart:
        - Mode: Survival

          # Spawn: EscapePod
          Spawn: EscapePodLandAtPos      # capsule
          Pos: [0, 70, 0]
          RotY: 160
          Status: [
          "Food: 500, Health: 500",
          "Food: 500, Health: 500",
          "Food: 500, Health: 500",
          "#FreshStart:Food: 250, Health: 250" ]
          Items: [
          "SurvivalTool, Pistol:1",
          "SurvivalTool, Pistol:1",
          "SurvivalTool, Pistol:1",
          "#FreshStart: SurvivalTool" ]

        ## commentaire de fin du bloc
Autre: 1
"""


def _build(root: Path) -> Path:
    (root / "Sectors").mkdir(parents=True)
    (root / "Sectors" / "Sectors.yaml").write_text(SECTORS, encoding="utf-8")
    for name, text in (("EdenOcean2", PLAIN), ("Starter_Akua_V2", STARTER)):
        path = root / "Playfields" / name / "playfield_static.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _rows(root):
    return {row.name: row for row in find_planets(root)}


def _sectors(root) -> str:
    return (root / "Sectors" / "Sectors.yaml").read_text(encoding="utf-8")


def _playfield(root, name="EdenOcean2") -> str:
    return (root / "Playfields" / name / "playfield_static.yaml").read_text(
        encoding="utf-8")


def test_find_planets_flags_marker_kit_and_card(tmp_path):
    rows = _rows(_build(tmp_path))
    assert set(rows) == {"Eden", "Akua"}          # soleil et geante exclus
    assert rows["Akua"].marker == MARKER and rows["Akua"].is_start
    assert rows["Eden"].marker == "" and not rows["Eden"].is_start
    assert rows["Akua"].has_kit is True           # Survival + Items
    assert rows["Eden"].has_kit is False          # seulement Debug
    assert rows["Eden"].sector == (30, 0, 30)


def test_validated_cache_seeds_marks_and_lists_untested(tmp_path):
    """Le cache « validé en jeu » est la SEULE source de vérité : aucun
    critère de forme ne prédit si le client acceptera la donnée d'un départ
    (vecu 05/11 : Lava ET StarterRandom_Arid_V2, données du mod intactes)."""
    from core.starters import (find_untested_starts, load_validated,
                               mark_validated)
    root = _build(tmp_path)
    # premier contact : cache absent, rien n'est juge
    validated, exists = load_validated(root)
    assert validated == set() and exists is False
    assert find_untested_starts(root) == []
    # l'utilisateur valide Akua (joué sans crash)
    mark_validated(root, ["Starter_Akua_V2"])
    validated, exists = load_validated(root)
    assert validated == {"Starter_Akua_V2"} and exists is True
    # Akua (marque) est valide ; Eden (marque par le module) reste a tester
    eden = _rows(root)["Eden"]
    set_starts(root, [eden])
    assert find_untested_starts(root) == [("Eden", "EdenOcean2")]


def test_set_and_clear_start_markers(tmp_path):
    root = _build(tmp_path)
    eden = _rows(root)["Eden"]
    assert preview_markers(root, [eden], MARKER) == [(
        "Eden", "['0, 0, 0', Eden, EdenOcean2, '', '', '', '']",
        "['0, 0, 0', Eden, EdenOcean2, 'Human:1', '', '', '']")]
    assert set_starts(root, [eden]) == (1, [])
    assert "['0, 0, 0', Eden, EdenOcean2, 'Human:1', '', '', '']" in _sectors(root)
    assert set_starts(root, [eden]) == (0, [])     # deja marquee
    akua = _rows(root)["Akua"]
    assert clear_starts(root, [akua]) == (1, [])
    assert "['0, 0, 0', Akua, Starter_Akua_V2,'', '', '', '']" in _sectors(root)


def test_unknown_row_is_reported_not_raised(tmp_path):
    root = _build(tmp_path)
    ghost = _rows(root)["Eden"]
    ghost = type(ghost)("Alpha", (99, 99, 99), "Fantome", "EdenOcean2", "",
                        False, False)
    written, details = set_starts(root, [ghost])
    assert written == 0 and "introuvable" in details[0]


def test_read_kit_returns_four_levels(tmp_path):
    root = _build(tmp_path)
    kit = read_kit(root, "Starter_Akua_V2")
    assert kit.spawn == "EscapePodLandAtPos"
    assert kit.items[0] == "SurvivalTool, Pistol:1"
    assert kit.items[3] == "#FreshStart: SurvivalTool"
    assert kit.status[3] == "#FreshStart:Food: 250, Health: 250"
    # planete sans kit : repli sur le kit d'Akua
    assert read_kit(root, "EdenOcean2").items == AKUA_ITEMS


def test_write_kit_updates_in_place_and_keeps_comments(tmp_path):
    root = _build(tmp_path)
    kit = StartKit(items=("CombatKnife", "CombatKnife", "CombatKnife",
                          "#FreshStart: CombatKnife"))
    assert write_kit(root, "Starter_Akua_V2", kit) == "updated"
    text = _playfield(root, "Starter_Akua_V2")
    # forme du corpus : `Items: [` puis un niveau cite par ligne
    assert 'Items: [ \n          "CombatKnife",\n          "CombatKnife",\n' \
           '          "CombatKnife",\n          "#FreshStart: CombatKnife" ]' \
           in text
    assert "Spawn: EscapePodLandAtPos" in text
    assert "# Spawn: EscapePod" in text          # commentaire du corpus garde
    assert "## commentaire de fin du bloc" in text
    assert read_kit(root, "Starter_Akua_V2").items[0] == "CombatKnife"


def test_write_kit_creates_before_trailing_comments(tmp_path):
    root = _build(tmp_path)
    assert write_kit(root, "EdenOcean2", StartKit()) == "created"
    text = _playfield(root)
    block = text.split("FixedPlayerStart:", 1)[1].split("# Section suivante", 1)[0]
    assert "- Mode: Debug" in block               # l'entree Debug reste
    assert "        - Mode: Survival" in block    # indentation du corpus
    assert "          Spawn: EscapePodLandAtPos" in block
    assert text.index("Mode: Survival") < text.index("# Section suivante")
    assert _rows(root)["Eden"].has_kit is True


def test_prepend_card_adds_once_and_keeps_description(tmp_path):
    root = _build(tmp_path)
    eden = _rows(root)["Eden"]
    assert prepend_start_card(root, eden) == "added"
    text = _playfield(root)
    assert "Start Location:" in text and "[b]Eden[/b]" in text
    assert "System: [c][[c][00ff00][b]Alpha[/b]" in text
    assert "Vast oceans cover the planet." in text   # description d'origine
    assert prepend_start_card(root, _rows(root)["Eden"]) == "already"


def test_kit_check_flags_unknown_items_only(tmp_path):
    """Le jeu IGNORE en silence un item inconnu : le controle doit le dire, sans
    bloquer, et accepter l'espace apres les deux-points (`WaterBottle: 1`
    existe 38 fois dans le corpus) comme la forme collee."""
    from core.starters import check_kit
    root = _build(tmp_path)
    conf = root / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "ItemsConfig.ecf").write_text(
        "{ +Item Id: 1, Name: SurvivalTool }\n"
        "{ +Item Id: 2, Name: 9mmBullet }\n", encoding="utf-8")
    ok = StartKit(items=("9mmBullet: 100", "9mmBullet:100, SurvivalTool",
                         "SurvivalTool#Drop", "Token:1:6999, #FreshStart: 9mmBullet:5"))
    assert check_kit(root, ok) == []
    bad = StartKit(items=("9mmBulllet: 100", "Pistol: cent", "", ""))
    problems = check_kit(root, bad)
    assert any("9mmBulllet" in p for p in problems)
    assert any("forme invalide" in p for p in problems)
    assert len(problems) == 2


def test_kit_check_is_silent_without_itemsconfig(tmp_path):
    from core.starters import check_kit
    root = _build(tmp_path)               # aucune config : aucun faux positif
    assert check_kit(root, StartKit(items=("NimporteQuoi:3", "", "", ""))) == []


def test_write_kit_ensures_a_final_newline(tmp_path):
    """Vecu 05/11 : `Lava/playfield_static.yaml` finissait sans saut de ligne ;
    le jeu lit static + dynamic dans un MEME flux, la derniere ligne collait au
    `---` du dynamic et plus aucun depart n'apparaissait au menu."""
    from core.starters import ensure_final_eol
    root = _build(tmp_path)
    path = root / "Playfields" / "EdenOcean2" / "playfield_static.yaml"
    path.write_bytes(PLAIN.rstrip("\n").encode("utf-8"))
    assert ensure_final_eol(root, "EdenOcean2") is True
    assert path.read_bytes().endswith(b"\n")
    assert ensure_final_eol(root, "EdenOcean2") is False       # idempotent
    path.write_bytes(PLAIN.rstrip("\n").encode("utf-8"))
    assert write_kit(root, "EdenOcean2", StartKit()) == "created"
    assert path.read_bytes().endswith(b"\n")


def test_card_write_also_ends_with_a_newline(tmp_path):
    root = _build(tmp_path)
    path = root / "Playfields" / "EdenOcean2" / "playfield_static.yaml"
    path.write_bytes(PLAIN.rstrip("\n").encode("utf-8"))
    assert prepend_start_card(root, _rows(root)["Eden"]) == "added"
    assert path.read_bytes().endswith(b"\n")
    assert not path.read_bytes().endswith(b"\n\n")


def test_check_playfield_flags_an_empty_duplicate_key(tmp_path):
    """Vecu 05/11 : `Lava/playfield_dynamic.yaml` declarait `GroundShapes:`
    VIDE puis `GroundShapes:` avec sa sequence — le menu lit static+dynamic
    dans un meme flux, le parseur du jeu rejette l'item de sequence et le
    client plante au lancement. Deux cles dupliquees TOUTES DEUX valorisees
    passent (`Starter_Pandora_V2` : PlayfieldLevelOverride [3,3] et [4,4])."""
    from core.starters import check_playfield
    root = _build(tmp_path)
    dynamic = root / "Playfields" / "EdenOcean2" / "playfield_dynamic.yaml"
    dynamic.write_text("Gravity: -50\nGroundShapes:\n\n\n"
                       "GroundShapes: \n - GroundShape_Mercury, 1\n",
                       encoding="utf-8")
    problems = check_playfield(root, "EdenOcean2")
    assert len(problems) == 1 and "GroundShapes" in problems[0]
    assert "sans valeur" in problems[0]
    dynamic.write_text("Gravity: -50\nLevel: [3,3]\nLevel: [4,4]\n",
                       encoding="utf-8")
    assert check_playfield(root, "EdenOcean2") == []


def test_description_and_canvas_text(tmp_path):
    """La carte du menu est la Description du playfield : lue sans les
    guillemets YAML, et prefixee par la fiche quand elle va etre ajoutee."""
    from core.starters import card_preview, description
    root = _build(tmp_path)
    eden = _rows(root)["Eden"]
    assert description(root, "EdenOcean2") == \
        "Difficulty: Hard \\n\\nVast oceans cover the planet."
    assert "Start Location:" not in card_preview(root, eden, False)
    preview = card_preview(root, eden, True)
    assert preview.startswith("[sup][c][A9A9A9]Start Location:")
    assert preview.endswith("Vast oceans cover the planet.")
    assert description(root, "Absent") == ""


def test_card_is_refused_on_a_multiline_description(tmp_path):
    """Le client re-serialise la donnee du playfield avant de la relire : deux
    crashs au menu Nouvelle partie ont suivi l'insertion d'une fiche dans une
    Description multi-lignes (vecu 05/11 sur `Lava`). Non prouve -> refuse."""
    root = _build(tmp_path)
    path = root / "Playfields" / "EdenOcean2" / "playfield_static.yaml"
    path.write_text(
        'Description: "Difficulty: Hard\n\nPlanets are born by the swirling '
        'ashes.\n\\nMore text here. "\n\nPlanetType: Ocean\n', encoding="utf-8")
    message = prepend_start_card(root, _rows(root)["Eden"])
    assert "plusieurs lignes" in message
    assert "Start Location" not in _playfield(root)


def test_card_is_not_written_over_a_block_description(tmp_path):
    """Vanilla ecrit parfois `Description: >-` : on ne reecrit pas la forme du
    fichier, on le dit."""
    root = _build(tmp_path)
    path = root / "Playfields" / "EdenOcean2" / "playfield_static.yaml"
    path.write_text(PLAIN.replace(
        'Description: "Difficulty: Hard \\n\\nVast oceans cover the planet."',
        "Description: >-\n   Difficulty: Hard"), encoding="utf-8")
    message = prepend_start_card(root, _rows(root)["Eden"])
    assert "non guillemetee" in message
    assert "Start Location:" not in _playfield(root)
