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

"""Fusion STRUCTURELLE de Sectors.yaml (tranche 2, demande 25/09) :
systemes/secteurs/lignes playfield proposes un a un et INSERTS dans le
fichier de la copie de travail (jamais d'ecrasement), commentaires et
mise en forme preserves via yamllite."""
import types

import pytest

from core.sectors_merge import (FineRequest, analyze_sectors_merge,
                                apply_fine_selection,
                                apply_structural_units)

WORKING_YAML = """SolarSystems:
  - Name: Alpha
    Coordinates: [190, 15, 50]
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Ancienne, OldTemplate, '']
# --- commentaire de section Beta conserve chez la source
"""

SOURCE_YAML = """SolarSystems:
  - Name: Alpha
    Coordinates: [190, 15, 50]
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Ancienne, OldTemplate, '']
          - ['120,0,0', MaPlanete, TempX, '']
# --- commentaire de section Beta conserve chez la source
  - Name: Beta
    Coordinates: [42, 21, 7]
    Sectors:
      - Coordinates: [1, 2, 3]
        Playfields:
          - ['0,0,0', PlaneteBeta, TempX, '']
"""


@pytest.fixture
def yaml_paths(tmp_path):
    working = tmp_path / "working" / "Sectors" / "Sectors.yaml"
    working.parent.mkdir(parents=True)
    working.write_text(WORKING_YAML, encoding="utf-8")
    source = tmp_path / "source" / "Sectors" / "Sectors.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE_YAML, encoding="utf-8")
    return working, source


def test_analyze_finds_missing_units(yaml_paths):
    working, source = yaml_paths
    units = analyze_sectors_merge(working, source)
    kinds = {(u.kind, u.name) for u in units}
    assert ("playfield", "MaPlanete") in kinds
    assert ("system", "Beta") in kinds
    # le playfield deja present (Ancienne) n'est jamais propose
    assert ("playfield", "Ancienne") not in kinds


def test_apply_inserts_and_preserves(yaml_paths):
    working, source = yaml_paths
    units = analyze_sectors_merge(working, source)
    n = apply_structural_units(working, units, source)
    assert n == 2
    text = working.read_text(encoding="utf-8")
    # insertion du systeme Beta avec son commentaire source preserve
    assert "- Name: Beta" in text
    assert "# --- commentaire de section Beta conserve chez la source" in text
    assert "PlaneteBeta" in text
    # la ligne playfield inseree dans le secteur existant, l'ancienne garde
    assert "MaPlanete" in text and "Ancienne" in text
    # idempotent : une nouvelle analyse ne propose plus rien
    assert analyze_sectors_merge(working, source) == []


def test_apply_empty_units_writes_nothing(yaml_paths):
    working, source = yaml_paths
    before = working.read_bytes()
    assert apply_structural_units(working, [], source) == 0
    assert working.read_bytes() == before


def test_dialog_structural_section(qapp, yaml_paths, monkeypatch):
    """Le dialogue de revision affiche la section structurelle quand un
    Sectors.yaml est dans le plan, avec les unites cochees."""
    from PyQt6.QtCore import Qt
    from gui.folder_merge_review_dialog import FolderMergeReviewDialog
    working, source = yaml_paths
    # racines : working = <tmp>/working/Sectors/Sectors.yaml
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working.parent.parent))
    source_root = source.parent.parent
    (source_root / "Prefabs").mkdir(exist_ok=True)
    dlg = FolderMergeReviewDialog(main, source.parent, source_root,
                                  "source", parent=None)
    assert dlg.sectors_plan is not None
    units = dlg.selected_structural_units()
    assert {(u.kind, u.name) for u in units} == {
        ("playfield", "MaPlanete"), ("system", "Beta")}
    # tout decocher -> plus aucune unite selectionnee
    dlg._set_all_checks(False)
    assert dlg.selected_structural_units() == []
    dlg._set_all_checks(True)
    assert len(dlg.selected_structural_units()) == 2


def test_merge_preserves_system_coordinates_block(tmp_path):
    """Vecu 01-02/10 : les Coordinates de SYSTEME en bloc vertical sont le
    format que le jeu LIT (carte + chargement) — une conversion en flow
    rendait le Sectors.yaml inparsable par YamlDotNet du jeu (« Expected
    'SequenceStart', got 'MappingStart' »). Garde-fou anti-regression : le
    round-trip yamllite preserve le bloc vertical ET son commentaire."""
    from core.yamllite.parser import parse_yaml_file
    src = tmp_path / "Sectors.yaml"
    src.write_text(
        "SolarSystems:\n"
        "  - Name: Hyperion System\n"
        "    StarClass: S\n"
        "    Coordinates:\n"
        "      - 110  # original: 190\n"
        "      - 1\n"
        "      - 140\n"
        "    Sectors:\n"
        "      - Coordinates:\n"
        "          - 0\n"
        "          - 0\n"
        "          - 0\n"
        "        Playfields:\n"
        "          - ['0,0,0', Hyperion System, SunRandom, '']\n",
        encoding="utf-8")
    doc = parse_yaml_file(src)
    rendered = doc.render()
    assert "- 110  # original: 190" in rendered, \
        "le bloc vertical Coordinates et son commentaire doivent rester"
    assert "Coordinates:\n" in rendered or "- 110" in rendered


def test_normalize_system_coordinates_removed():
    """La normalisation flow (nuisible, vecu 02/10 : le jeu ne parsait plus
    le Sectors.yaml) a ete retiree du moteur."""
    import core.sectors_merge as m
    assert not hasattr(m, "normalize_system_coordinates"), \
        "normalize_system_coordinates ne doit plus exister"


# ---------------------------------------------------------------------------
# Soleils et orphelines (vecu 04/10 : fusion generique Default Akua-Omicron
# -> Vanilla EVO, « Duplicate playfield name 'Zeyhines' » : 5 doublons, le
# soleil du systeme Symos importe etait un doublon, lunes sans planetes)
# ---------------------------------------------------------------------------

EVO_LIKE_WORKING = """SolarSystems:
  - Name: Ellyon
    Coordinates: [134, 25, 126]
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Symos, SunRandom, '']
          - ['4,0,0', Skillon, GS_Skillon, '']
# --- commentaire de section preserve
"""

B_LIKE_SOURCE = """SolarSystems:
  - Name: Symos
    Coordinates:
      - 221
      - 0
      - 801
    Sectors:
      - Coordinates:
          - 0
          - 0
          - 0
        Playfields:
          - ["0,0,0", Symos, Sun, ""]
      - Coordinates:
          - -3
          - 1
          - 51
        Playfields:
          - ["0,0,0", Skillon, Barren, ""]
          - ["5927,5000,5209", Skillon Moon, MoonDesert]
          - ["0,0,0", Skillon Orbit, SpaceOrbit, ""]
      - Coordinates:
          - -244
          - 21
          - -12
        Playfields:
          - ["0,0,0", Oryzs Tor Trading Hub, SpaceTradingStation, ""]
"""


@pytest.fixture
def sun_paths(tmp_path):
    working = tmp_path / "working" / "Sectors" / "Sectors.yaml"
    working.parent.mkdir(parents=True)
    working.write_text(EVO_LIKE_WORKING, encoding="utf-8")
    source = tmp_path / "source" / "Sectors" / "Sectors.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(B_LIKE_SOURCE, encoding="utf-8")
    return working, source


def test_apply_skips_system_losing_its_sun(sun_paths):
    """Le systeme importe 'Symos' a pour SEUL soleil le playfield 'Symos',
    deja pris par Ellyon : un systeme sans soleil est injoignable —
    l'insertion du systeme entier est refusee (pas juste le secteur)."""
    working, source = sun_paths
    units = analyze_sectors_merge(working, source)
    symos = next(u for u in units if u.kind == "system")
    assert symos.conflict, "Symos/Skillon doivent etre marques en conflit"
    n = apply_structural_units(working, units, source)
    assert n == 0
    txt = working.read_text(encoding="utf-8")
    assert "- Name: Symos" not in txt


def test_drop_removes_orphans_and_sunless_system(tmp_path):
    """drop_duplicate_playfields retire les orphelines ('Skillon Moon'/
    'Skillon Orbit') de la planete dupliquee et le systeme qui perd son
    DERNIER soleil (ici tout 'Symos' est retire, Oryzs Tor avec)."""
    from core.sectors_merge import (drop_duplicate_playfields,
                                    find_broken_systems,
                                    find_duplicate_playfields)
    p = tmp_path / "Sectors.yaml"
    # etat produit par la fusion generique fautive : les systemes de B
    # INSERES dans la liste SolarSystems du working (une seule cle racine)
    p.write_text(
        "SolarSystems:\n"
        "  - Name: Ellyon\n"
        "    Coordinates: [134, 25, 126]\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Symos, SunRandom, '']\n"
        "          - ['4,0,0', Skillon, GS_Skillon, '']\n"
        "# --- commentaire de section preserve\n"
        + B_LIKE_SOURCE.split("SolarSystems:\n", 1)[1],
        encoding="utf-8")
    retired, details = drop_duplicate_playfields(p)
    assert retired == 4          # Symos, Skillon, Skillon Moon, Skillon Orbit
    assert any("retire entierement" in d for d in details)
    assert any("orphelin" in d for d in details)
    txt = p.read_text(encoding="utf-8")
    assert "- Name: Symos" not in txt
    assert "Skillon Moon" not in txt
    assert "Oryzs Tor" not in txt          # parti avec son systeme casse
    assert "SunRandom" in txt and "- Name: Ellyon" in txt
    assert "# --- commentaire de section preserve" in txt
    assert find_duplicate_playfields(p) == {}
    assert find_broken_systems(p) == []


def test_drop_keeps_system_with_its_own_sun(tmp_path):
    """Un systeme qui garde AU MOINS un soleil n'est pas retire, meme s'il
    perd un soleil doublon et une planete doublonne avec orphelines."""
    from core.sectors_merge import drop_duplicate_playfields
    p = tmp_path / "Sectors.yaml"
    p.write_text(
        "SolarSystems:\n"
        "  - Name: Alpha\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Alpha Sun, SunRandom, '']\n"
        "          - ['1,0,0', Delta, Desert, '']\n"
        "          - ['2,0,0', Delta Moon, MoonDesert]\n"
        "  - Name: Beta\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Beta Sun, Sun, '']\n"
        "          - ['1,0,0', Alpha Sun, Sun, '']\n"
        "      - Coordinates: [5, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Delta, Desert, '']\n"
        "          - ['2,0,0', Delta Moon, MoonDesert]\n",
        encoding="utf-8")
    retired, details = drop_duplicate_playfields(p)
    assert retired == 3          # Alpha Sun, Delta, Delta Moon
    txt = p.read_text(encoding="utf-8")
    assert "- Name: Beta" in txt            # garde : Beta Sun reste
    assert "Beta Sun" in txt
    assert "Alpha Sun" in txt               # l'original d'Alpha
    # orpheline retiree du systeme Beta ; Alpha garde la SIENNE (premiere
    # occurrence, jamais touchee)
    assert txt.count("Delta Moon") == 1
    assert "secteur vide supprime" in " ".join(details)


def test_find_broken_systems(tmp_path):
    """Detecte les systemes a secteurs SANS aucun playfield soleil ; les
    formats Pos sans liste Sectors ne sont pas jugeables."""
    from core.sectors_merge import find_broken_systems
    p = tmp_path / "Sectors.yaml"
    p.write_text(
        "SolarSystems:\n"
        "  - Name: SansSoleil\n"
        "    Coordinates: [1, 1, 1]\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Un Poste, SpaceTradingStation, '']\n"
        "  - Name: PosFormat\n"
        "    Coordinates: [2, 2, 2]\n"
        "  - Name: Bon\n"
        "    Coordinates: [3, 3, 3]\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Son Soleil, Sun, '']\n",
        encoding="utf-8")
    assert find_broken_systems(p) == ["SansSoleil"]


# ---------------------------------------------------------------------------
# Fusion FINE (demande 04/10 : coches unitaires systeme/secteur/ligne)
# ---------------------------------------------------------------------------

FINE_SOURCE = """SolarSystems:
  - Name: Beta
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Beta Sun, Sun, '']
          - ['2,0,0', BetaA, Desert, '']
      - Coordinates: [5, 0, 0]
        Playfields:
          - ['0,0,0', BetaB, Ocean, '']
          - ['1,0,0', BetaB Moon, MoonWater, '']
"""

FINE_WORKING = """SolarSystems:
  - Name: Alpha
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Alpha Sun, SunRandom, '']
"""


@pytest.fixture
def fine_paths(tmp_path):
    working = tmp_path / "working" / "Sectors" / "Sectors.yaml"
    working.parent.mkdir(parents=True)
    working.write_text(FINE_WORKING, encoding="utf-8")
    source = tmp_path / "source" / "Sectors" / "Sectors.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(FINE_SOURCE, encoding="utf-8")
    return working, source


def test_analyze_detailed_children_units(fine_paths):
    """detailed=True : un systeme absent emet SES enfants (secteurs +
    lignes) ; les feuilles portent les conflits, le parent les recaps."""
    from core.sectors_merge import find_duplicate_playfields
    working, source = fine_paths
    units = analyze_sectors_merge(working, source, detailed=True)
    kinds = {}
    for u in units:
        kinds.setdefault(u.kind, []).append(u.name)
    assert kinds["system"] == ["Beta"]
    assert sorted(kinds["sector"]) == ["Beta", "Beta"]
    assert sorted(kinds["playfield"]) == ["Beta Sun", "BetaA", "BetaB",
                                          "BetaB Moon"]
    # aucune unit en conflit (Beta est inconnu du working)
    assert all(not u.conflict for u in units)
    assert find_duplicate_playfields(working) == {}


def test_analyze_detailed_marks_row_conflicts(sun_paths):
    """Les conflits sont marques LIGNE PAR LIGNE ; le systeme parent
    recappe les noms conflictuels."""
    working, source = sun_paths
    units = analyze_sectors_merge(working, source, detailed=True)
    by_kind = {}
    for u in units:
        by_kind.setdefault(u.kind, []).append(u)
    rows = {u.name: u for u in by_kind["playfield"]}
    assert rows["Symos"].conflict == "Symos"        # soleil deja dans Ellyon
    assert rows["Skillon"].conflict == "Skillon"
    assert rows["Oryzs Tor Trading Hub"].conflict == ""
    sys_unit = by_kind["system"][0]
    assert "Symos" in sys_unit.conflict and "Skillon" in sys_unit.conflict


def test_apply_fine_selection_whole_system(fine_paths):
    working, source = fine_paths
    reqs = [FineRequest("Beta", "[0, 0, 0]", None),
            FineRequest("Beta", "[5, 0, 0]", None)]
    n, details = apply_fine_selection(working, reqs, source)
    assert n == 4
    txt = working.read_text(encoding="utf-8")
    assert "- Name: Beta" in txt
    for nm in ("Beta Sun", "BetaA", "BetaB", "BetaB Moon"):
        assert nm in txt
    assert "Alpha Sun" in txt                # working intact
    # idempotent : re-appliquer ne reinsere rien
    n2, _ = apply_fine_selection(working, reqs, source)
    assert n2 == 0


def test_apply_fine_selection_partial_rows(fine_paths):
    """Un seul secteur demande : le systeme est insere avec SES secteurs
    choisis seulement ; un seul lignes demande : secteur filtre."""
    working, source = fine_paths
    reqs = [FineRequest("Beta", "[0, 0, 0]", None)]
    n, details = apply_fine_selection(working, reqs, source)
    assert n == 2                            # Beta Sun + BetaA
    txt = working.read_text(encoding="utf-8")
    assert "BetaB" not in txt                # secteur non demande
    # reprise : on ajoute UNE ligne du second secteur
    reqs2 = [FineRequest("Beta", "[5, 0, 0]", ("BetaB",))]
    n2, _ = apply_fine_selection(working, reqs2, source)
    assert n2 == 1
    txt = working.read_text(encoding="utf-8")
    assert "BetaB" in txt
    assert "BetaB Moon" not in txt           # ligne non demandee


def test_apply_fine_selection_refuses_sunless(fine_paths):
    """Demander des secteurs SANS le soleil : le systeme n'est pas insere
    (injoignable), avec un detail explicite."""
    working, source = fine_paths
    reqs = [FineRequest("Beta", "[5, 0, 0]", None)]
    n, details = apply_fine_selection(working, reqs, source)
    assert n == 0
    assert any("NON insere" in d for d in details)
    assert "- Name: Beta" not in working.read_text(encoding="utf-8")


def test_apply_fine_selection_common_system_row(fine_paths):
    """Ligne ajoutee a un secteur DEJA present dans le working (apres une
    premiere insertion, Beta est un systeme commun)."""
    working, source = fine_paths
    apply_fine_selection(working,
                         [FineRequest("Beta", "[0, 0, 0]", None)], source)
    reqs = [FineRequest("Beta", "[5, 0, 0]", ("BetaB Moon",))]
    n, _ = apply_fine_selection(working, reqs, source)
    assert n == 1
    txt = working.read_text(encoding="utf-8")
    assert "BetaB Moon" in txt
    assert txt.count("BetaB") == 1           # la ligne Moon ; BetaB absent


def test_apply_fine_selection_excludes_conflicts(tmp_path):
    """Une ligne demandee dont le nom est deja pris ailleurs dans le
    working est EXCLUE (jamais un doublon), les autres passent."""
    working = tmp_path / "working" / "Sectors" / "Sectors.yaml"
    working.parent.mkdir(parents=True)
    working.write_text(
        "SolarSystems:\n"
        "  - Name: Alpha\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Alpha Sun, SunRandom, '']\n"
        "          - ['1,0,0', BetaA, Desert, '']\n",
        encoding="utf-8")
    source = tmp_path / "source" / "Sectors" / "Sectors.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(FINE_SOURCE, encoding="utf-8")
    reqs = [FineRequest("Beta", "[0, 0, 0]", None)]
    n, details = apply_fine_selection(working, reqs, source)
    assert n == 1                            # Beta Sun seul ; BetaA exclu
    assert any("BetaA exclu" in d for d in details)
    txt = working.read_text(encoding="utf-8")
    assert txt.count("BetaA") == 1           # l'original d'Alpha uniquement


# ---------------------------------------------------------------------------
# Coordonnees VERTICALES (format EVO 1.19.6) — vecu 04/10 : sector.value
# vide pour TOUS les secteurs -> unites confondues aux memes coords,
# secteurs dupliques a l'affichage, mauvais contenus a l'insertion fine.
# ---------------------------------------------------------------------------

VERT_SOURCE = """SolarSystems:
  - Name: Thelya
    Coordinates:
      - 240
      - 0
      - 600
    Sectors:
      - Coordinates:
          - 0
          - 0
          - 0
        Playfields:
          - ["0,0,0", Thelya, Sun, ""]
      - Coordinates:
          - 36
          - 0
          - 100
        Playfields:
          - ["0,0,0", PlaneteX, Desert, ""]
          - ["0,0,0", PlaneteX Orbit, SpaceOrbit, ""]
"""


@pytest.fixture
def vert_paths(tmp_path):
    working = tmp_path / "working" / "Sectors" / "Sectors.yaml"
    working.parent.mkdir(parents=True)
    working.write_text(FINE_WORKING, encoding="utf-8")
    source = tmp_path / "source" / "Sectors" / "Sectors.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(VERT_SOURCE, encoding="utf-8")
    return working, source


def test_analyze_detailed_vertical_coords(vert_paths):
    """Les secteurs a coordonnees VERTICALES sont distingues : chacun
    garde ses coordonnees reconstruites et ses PROPRES lignes."""
    working, source = vert_paths
    units = analyze_sectors_merge(working, source, detailed=True)
    coords = sorted(u.coordinates for u in units if u.kind == "sector")
    assert coords == ["[0,0,0]", "[36,0,100]"]
    rows_by_sec = {}
    for u in units:
        if u.kind == "playfield":
            rows_by_sec.setdefault(u.coordinates, []).append(u.name)
    assert rows_by_sec["[0,0,0]"] == ["Thelya"]
    assert sorted(rows_by_sec["[36,0,100]"]) == ["PlaneteX",
                                                 "PlaneteX Orbit"]


def test_apply_fine_selection_vertical_coords_picks_right_sector(vert_paths):
    """Demander le second secteur (coords verticales) insere SON contenu,
    pas celui du premier secteur du document ; le bloc vertical du
    systeme est preserve."""
    working, source = vert_paths
    reqs = [FineRequest("Thelya", "[0,0,0]", None),
            FineRequest("Thelya", "[36,0,100]", ("PlaneteX",))]
    n, _ = apply_fine_selection(working, reqs, source)
    assert n == 2                            # Thelya Sun + PlaneteX
    txt = working.read_text(encoding="utf-8")
    assert "Thelya, Sun" in txt
    assert "PlaneteX" in txt
    assert "PlaneteX Orbit" not in txt       # ligne non demandee
    assert "- 240" in txt                    # bloc vertical preserve
