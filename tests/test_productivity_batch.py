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

"""Tests du lot « productivite » du 10/09/2026 : TraderZone -> marchands,
reecriture des Ref internes a la duplication, remplacement multi-fichiers,
bibliotheque de blocs, sauvegardes versionnees."""

from pathlib import Path

from core.block_library import delete_snippet, list_snippets, load_snippet, save_snippet
from core.ecf.model import EcfBlock
from core.ecf.parser import parse_ecf_text
from core.ecf.ref_rewrite import rewrite_internal_refs
from core.scenario_search import replace_in_files
from core.versioned_backup import restore_latest, rotate, snapshot_file


# ---------------------------------------------------------------------------
# Regle metier TraderZone -> marchands (core/trader_zone_check.py)
# ---------------------------------------------------------------------------

TRADER_ECF = (
    "{ Trader Name: Bertrams\n"
    "  SellingGoods: \"trwSpecial\"\n"
    "}\n"
    "{ Trader Name: Medic\n"
    "  SellingGoods: \"trwMedicine\"\n"
    "}\n"
)


def _scenario(tmp_path: Path, zones: dict) -> Path:
    cfg = tmp_path / "Content" / "Configuration"
    cfg.mkdir(parents=True)
    (cfg / "TraderNPCConfig.ecf").write_text(TRADER_ECF, encoding="utf-8")
    for pf_name, zone in zones.items():
        pf = tmp_path / "Playfields" / pf_name
        pf.mkdir(parents=True)
        text = "Playfield: Test\n"
        if zone is not None:
            text += f"TraderZone: {zone}\n"
        (pf / "playfield_static.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_trader_zone_known_and_unknown(tmp_path):
    from core.trader_zone_check import check_trader_zone_references
    root = _scenario(tmp_path, {"Alpha": "Bertrams", "Beta": "Inconnu", "Gamma": None})
    issues = check_trader_zone_references(root)
    assert len(issues) == 1  # seule Beta signalee
    assert issues[0].code == 'W010'
    assert issues[0].level == 'warning'
    assert 'Inconnu' in issues[0].message
    assert issues[0].file_path.name == 'playfield_static.yaml'


def test_trader_zone_no_config_no_complaint(tmp_path):
    from core.trader_zone_check import check_trader_zone_references
    root = _scenario(tmp_path, {"Alpha": "Quelquun"})
    (root / "Content" / "Configuration" / "TraderNPCConfig.ecf").unlink()
    # pas de table de marchands lisible -> on ne juge pas
    assert check_trader_zone_references(root) == []


# ---------------------------------------------------------------------------
# Reecriture des Ref internes d'un clone (core/ecf/ref_rewrite.py)
# ---------------------------------------------------------------------------

DUPLICATED = (
    "{ Block Id: 100, Name: Original\n"
    "{\n"
    "   ChildBlock\n"
    "   {\n"
    "      Ref: 100\n"
    "      Other: 1\n"
    "   }\n"
    "   ExternalRef: 999\n"
    "}\n"
)


def test_rewrite_internal_refs_only_exact_matches():
    doc = parse_ecf_text(DUPLICATED)
    block = doc.nodes[0]
    # simule le clone : Id passe a 200
    block.set('Id', '200')
    count = rewrite_internal_refs(doc.nodes, '100', '200')
    assert count == 1
    # structure : bloc racine > bloc anonyme > [prop 'ChildBlock',
    #              bloc imbrique { Ref: 100 / Other: 1 }, prop 'ExternalRef']
    anon = block.children[0]
    nested = anon.children[1]
    ref_prop = nested.children[0]
    assert ref_prop.pairs[0] == ('Ref', '200')
    assert ref_prop.dirty is True
    other = anon.children[2]
    assert other.pairs == [('ExternalRef', '999')]  # rien d'autre touche


def test_rewrite_internal_refs_noop_cases():
    doc = parse_ecf_text(DUPLICATED)
    # old == new : interdit (0 reecriture)
    assert rewrite_internal_refs(doc.nodes, '100', '100') == 0
    assert rewrite_internal_refs(doc.nodes, '', '200') == 0


# ---------------------------------------------------------------------------
# Remplacement multi-fichiers (core/scenario_search.py)
# ---------------------------------------------------------------------------

def test_replace_in_files_literal_and_bom_crlf(tmp_path):
    f1 = tmp_path / "a.ecf"
    f1.write_bytes("# doc\r\nSizeBlocks: 4,7\r\nIronOre\r\n".encode("utf-8"))
    f2 = tmp_path / "b.ecf"
    f2.write_bytes("\ufeffName: IronOre\r\n".encode("utf-8"))  # BOM + CRLF
    replaced = replace_in_files([f1, f2], "IronOre", "CopperOre")
    assert replaced == {f1: 1, f2: 1}
    assert "CopperOre" in f1.read_text(encoding="utf-8")
    raw2 = f2.read_bytes()
    assert raw2.startswith(b"\xef\xbb\xbf")           # BOM preserve
    assert b"\r\n" in raw2                            # CRLF preserve
    assert "CopperOre".encode() in raw2


def test_replace_in_files_regex_and_case(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("Prix: 100\nPrix: 250\nprix: 3\n", encoding="utf-8")
    # regex sensible a la casse : 2 correspondances 'Prix: <chiffres>'
    replaced = replace_in_files([f], r"Prix: (\d+)", r"Cost: \1",
                                case_sensitive=True, use_regex=True)
    assert replaced == {f: 2}
    text = f.read_text(encoding="utf-8")
    assert "Cost: 100" in text and "Cost: 250" in text
    assert "prix: 3" in text  # casse minuscule non touchee (sensible)

    replaced = replace_in_files([f], r"prix: (\d+)", r"cost: \1",
                                case_sensitive=False, use_regex=True)
    assert replaced == {f: 1}
    assert "cost: 3" in f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Bibliotheque de blocs (core/block_library.py)
# ---------------------------------------------------------------------------

def test_block_library_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("core.block_library.LIB_DIR", tmp_path / "lib")
    path = save_snippet("POI Cargo", "{ Block Id: 5\n{\n}\n")
    assert path.exists() and path.suffix == ".ecfsnip"
    snippets = list_snippets()
    assert [s["name"] for s in snippets] == ["POI Cargo"]
    assert "{ Block Id: 5" in load_snippet(path)
    delete_snippet(path)
    assert list_snippets() == []


def test_block_library_name_sanitized_and_collision(tmp_path, monkeypatch):
    monkeypatch.setattr("core.block_library.LIB_DIR", tmp_path / "lib")
    save_snippet('POI <Cargo>/2', "x\n")
    snippets = list_snippets()
    assert len(snippets) == 1
    assert "/" not in snippets[0]["name"] and "<" not in snippets[0]["name"]
    # meme nom a quelques secondes d'intervalle : pas d'ecrasement
    p2 = save_snippet(snippets[0]["name"], "y\n")
    assert load_snippet(p2) == "y\n"


# ---------------------------------------------------------------------------
# Sauvegardes versionnees (core/versioned_backup.py)
# ---------------------------------------------------------------------------

def test_versioned_backup_snapshot_rotate_restore(tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    monkeypatch.setattr("core.versioned_backup.BACKUPS_ROOT", backups)
    # horodatages DETERMINISTES : trois snapshots a la seconde pres tomberaient
    # dans le meme dossier (comportement voulu : un snapshot par seconde, le
    # dernier etat gagne) -- on force des secondes distinctes pour tester la
    # rotation.
    stamps = iter(["20260910-000001", "20260910-000002", "20260910-000003"])
    monkeypatch.setattr("core.versioned_backup.time.strftime",
                        lambda fmt: next(stamps))
    work = tmp_path / "work"
    work.mkdir()
    target = work / "Content"
    target.mkdir()
    f = target / "ItemsConfig.ecf"
    f.write_text("v1", encoding="utf-8")

    p1 = snapshot_file(work, f, keep=2)
    assert p1 is not None and "ItemsConfig.ecf" in p1.name
    f.write_text("v2", encoding="utf-8")
    snapshot_file(work, f, keep=2)
    f.write_text("v3", encoding="utf-8")
    snapshot_file(work, f, keep=2)
    # rotation : 3 horodatages, 2 conserves (le plus ancien supprime)
    stamps_dirs = sorted((backups / work.name).iterdir())
    assert len(stamps_dirs) == 2

    # restaure le plus recent = v3
    assert f.read_text(encoding="utf-8") == "v3"
    src = restore_latest(work, f)
    assert src is not None and f.read_text(encoding="utf-8") == "v3"
    # suppression du plus recent -> le "latest" devient v2
    import shutil
    shutil.rmtree(stamps_dirs[-1])
    restore_latest(work, f)
    assert f.read_text(encoding="utf-8") == "v2"


def test_versioned_backup_missing_source_noop(tmp_path, monkeypatch):
    monkeypatch.setattr("core.versioned_backup.BACKUPS_ROOT", tmp_path / "backups")
    work = tmp_path / "work"
    work.mkdir()
    assert snapshot_file(work, work / "inexistant.ecf") is None
    assert restore_latest(work, work / "inexistant.ecf") is None


# ---------------------------------------------------------------------------
# Glossaire EN (OPT-006) : repli transparent sans fichier traduit
# ---------------------------------------------------------------------------

def test_glossary_falls_back_to_french_when_en_absent(monkeypatch, tmp_path):
    """Fichier EN absent/illisible : repli FR INTEGRAL, quel que soit l'etat
    de l'explication recherchee (jamais de fiche vide)."""
    from core import ecf_header_glossary as g
    from core.i18n import set_language, get_language
    import core.settings as settings
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(g, "_english_data", lambda: {})  # simule l'absence
    old = get_language()
    try:
        set_language("fr")
        assert g.glossary_by_file_for_current_language() == g.GLOSSARY_BY_FILE
        set_language("en")
        assert g.glossary_by_file_for_current_language() == g.GLOSSARY_BY_FILE
    finally:
        set_language(old)


def test_glossary_english_used_when_file_present(monkeypatch, tmp_path):
    """Fichier EN genere (OPT-006) : interface en anglais -> le glossaire
    sert les explications anglaises ; interface en francais -> FR."""
    from core import ecf_header_glossary as g
    from core.i18n import set_language, get_language
    import core.settings as settings
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    old = get_language()
    try:
        set_language("en")
        expl_en = g.find_term_explanation("BlocksConfig.ecf", "AllowPlacingAt")
        assert expl_en is not None
        assert "structure" in expl_en.lower()  # explication anglaise
        set_language("fr")
        expl_fr = g.find_term_explanation("BlocksConfig.ecf", "AllowPlacingAt")
        assert expl_fr is not None and expl_fr != expl_en  # explication francaise
    finally:
        set_language(old)
