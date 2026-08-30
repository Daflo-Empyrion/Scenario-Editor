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

"""Controles AVANT validation d'une creation/duplication de bloc/item
(core/ecf/creation_check.py) : les 4 obligations de creation (enregistrement,
recette, localisation, arbre technologique) et le piege mortel de la casse.
Les messages sont traduits via core/i18n (cles createcheck.*)."""
from pathlib import Path

from core.ecf.parser import parse_ecf_text
from core.ecf.creation_check import (
    CreationContext, check_creation, has_blocking, format_blocking,
    SEVERITE_ERREUR, SEVERITE_AVERTISSEMENT, SEVERITE_INFO,
)


def make_doc(text: str):
    return parse_ecf_text(text)


def make_context(tmp_path: Path, templates_text: str = "",
                 material_text: str = "", localization_entries=None,
                 with_working_root: bool = False):
    """Contexte de reference avec fichiers de test ecrits sur disque."""
    siblings = []
    if templates_text:
        p = tmp_path / "Templates.ecf"
        p.write_text(templates_text, encoding="utf-8")
        siblings.append(p)
    if material_text:
        p = tmp_path / "MaterialConfig.ecf"
        p.write_text(material_text, encoding="utf-8")
        siblings.append(p)
    root = tmp_path if with_working_root else None
    if with_working_root and localization_entries is not None:
        from core.localization_lookup import write_scenario_localization_entries
        write_scenario_localization_entries(tmp_path, localization_entries)
    return CreationContext(siblings, root)


BASE_DOC = make_doc("""
{ Block Id: 100, Name: BlocExistant
  Material: metal
}

{ Block Id: 101, Name: AutreBloc
  Material: wood
}
""")


def issue_keys(issues):
    return {i.message_key for i in issues}


# ------------------------------------------------------------- Enregistrement
def test_name_missing_is_blocking(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "200", "")
    assert "createcheck.err_name_missing" in issue_keys(issues)
    assert has_blocking(issues)


def test_id_too_high_is_blocking(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "9000", "Nouveau")
    assert "createcheck.err_id_too_high" in issue_keys(issues)
    assert has_blocking(issues)


def test_id_duplicate_is_blocking(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "100", "Nouveau")
    assert "createcheck.err_id_used" in issue_keys(issues)
    assert has_blocking(issues)


def test_id_not_numeric_is_blocking(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "abc", "Nouveau")
    assert "createcheck.err_id_not_numeric" in issue_keys(issues)


def test_name_duplicate_exact_is_blocking(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "200", "BlocExistant")
    assert "createcheck.err_name_used" in issue_keys(issues)
    assert has_blocking(issues)


def test_name_case_clash_is_blocking(tmp_path):
    """Piege mortel no 2 : le moteur est sensible a la casse -- 'blocexistant'
    face a 'BlocExistant' doit etre BLOQUE meme si techniquement different."""
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "200", "blocexistant")
    assert "createcheck.err_name_case" in issue_keys(issues)
    assert has_blocking(issues)


def test_material_unknown_is_warning_not_blocking(tmp_path):
    ctx = make_context(tmp_path, material_text="""
{ Material Name: metal
}

{ Material Name: wood
}
""")
    issues = check_creation(BASE_DOC, ctx, "Block", "200", "Nouveau",
                            properties=[("Material", "plastique_inconnu")])
    assert "createcheck.warn_material_unknown" in issue_keys(issues)
    assert not has_blocking(issues)


def test_material_known_produces_no_warning(tmp_path):
    ctx = make_context(tmp_path, material_text="{ Material Name: metal\n}")
    issues = check_creation(BASE_DOC, ctx, "Block", "200", "Nouveau",
                            properties=[("Material", "metal")])
    assert "createcheck.warn_material_unknown" not in issue_keys(issues)


# ------------------------------------------------------------------- Recette
def test_template_collision_is_blocking(tmp_path):
    ctx = make_context(tmp_path, templates_text="""
{ Template Name: Nouveau
  CraftTime: 5
}
""")
    issues = check_creation(BASE_DOC, ctx, "Block", "200", "Nouveau")
    assert "createcheck.err_template_used" in issue_keys(issues)
    assert has_blocking(issues)


def test_template_case_clash_is_blocking(tmp_path):
    """La recette doit reprendre EXACTEMENT le Name du bloc : un Template a la
    casse pres est un piege mortel (rencontre en production, IdMapping)."""
    ctx = make_context(tmp_path, templates_text="""
{ Template Name: nouveau
  CraftTime: 5
}
""")
    issues = check_creation(BASE_DOC, ctx, "Block", "200", "Nouveau")
    assert "createcheck.err_template_case" in issue_keys(issues)
    assert has_blocking(issues)


def test_templates_file_missing_is_warning(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "200", "Nouveau")
    assert "createcheck.warn_templates_missing" in issue_keys(issues)
    assert not has_blocking(issues)


def test_template_collision_skipped_when_target_is_templates(tmp_path):
    """Fichier cible = Templates.ecf : pas de double controle collision (le
    controle Name suffit)."""
    ctx = make_context(tmp_path, templates_text="{ Template Name: Existant\n}")
    templates_doc = make_doc("{ Template Name: Existant\n}")
    issues = check_creation(templates_doc, ctx, "Template", None, "NouveauTemplate",
                            check_template_collision=False)
    assert "createcheck.err_template_used" not in issue_keys(issues)


# -------------------------------------------------------------- Localisation
def test_localization_missing_is_warning(tmp_path):
    ctx = make_context(tmp_path, with_working_root=True, localization_entries={})
    issues = check_creation(BASE_DOC, ctx, "Block", "200", "Nouveau")
    assert "createcheck.warn_localization_missing" in issue_keys(issues)
    assert not has_blocking(issues)


def test_localization_present_is_silent(tmp_path):
    ctx = make_context(tmp_path, with_working_root=True,
                       localization_entries={"Nouveau": {"Français": "Nouveau", "English": "New"}})
    issues = check_creation(BASE_DOC, ctx, "Block", "200", "Nouveau")
    assert "createcheck.warn_localization_missing" not in issue_keys(issues)


# ------------------------------------------------------- Arbre technologique
def test_techtree_hint_when_no_unlock_properties(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "200", "Nouveau",
                            properties=[("Material", "metal")], check_techtree_hint=True)
    assert "createcheck.info_techtree_missing" in issue_keys(issues)
    assert not has_blocking(issues)


def test_techtree_silent_when_unlock_present(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "200", "Nouveau",
                            properties=[("UnlockLevel", "3"), ("UnlockCost", "5")],
                            check_techtree_hint=True)
    assert "createcheck.info_techtree_missing" not in issue_keys(issues)


def test_techtree_hint_disabled_by_default(tmp_path):
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "200", "Nouveau")
    assert "createcheck.info_techtree_missing" not in issue_keys(issues)


# ------------------------------------------------------------------ Divers
def test_messages_are_translated_not_raw_keys(tmp_path):
    """Les messages passent par core/i18n : jamais une cle brute a l'ecran."""
    issues = check_creation(BASE_DOC, make_context(tmp_path), "Block", "9000", "Nouveau")
    for issue in issues:
        assert not issue.message.startswith("createcheck."), issue.message_key


def test_format_blocking_lists_only_blocking(tmp_path):
    ctx = make_context(tmp_path, with_working_root=True, localization_entries={})
    issues = check_creation(BASE_DOC, ctx, "Block", "9000", "Nouveau")
    text = format_blocking(issues)
    assert "createcheck" not in text  # traduit
    assert str(9000) in text


def test_valid_creation_has_no_blocking(tmp_path):
    ctx = make_context(tmp_path, templates_text="{ Template Name: AutreRecette\n}",
                       with_working_root=True,
                       localization_entries={"Nouveau": {"Français": "N", "English": "N"}})
    issues = check_creation(BASE_DOC, ctx, "Block", "200", "Nouveau",
                            properties=[("Material", "metal")])
    assert not has_blocking(issues)


def test_names_needing_localization_filters_known(tmp_path):
    from core.ecf.creation_check import names_needing_localization
    result = names_needing_localization(tmp_path, ["Nouveau", None, ""])
    assert result == ["Nouveau"]
