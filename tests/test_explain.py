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

"""Tests de core.explain -- contexte « Expliquer avec IA » (faits verifiables
uniquement : glossaire, valeur courante, tendance observee)."""
import pytest

from core.ecf.parser import parse_ecf_text
from core.explain import (ExplainContext, csv_context, ecf_block_context,
                          ecf_property_context, yaml_context)
from core.localization_lookup import LocalizationIndex
from core.yamllite.parser import parse_yaml_text

ECF = """{ +Block
    Id: 1, Name: GenSmall, Mass: 100
    EnergyOut: 50, type: int
}
{ +Block
    Id: 2, Name: GenMid, Mass: 200
    EnergyOut: 150, type: int
}
{ +Block
    Id: 3, Name: GenBig, Mass: 300
    EnergyOut: 250, type: int
}
"""


def _doc():
    return parse_ecf_text(ECF)


def _block(doc, name):
    for b in doc.iter_blocks():
        if (b.get_property('Name') or '').strip() == name:
            return b
    raise AssertionError(name)


def test_property_context_numeric_median_and_glossary():
    doc = _doc()
    block = _block(doc, 'GenMid')
    ctx = ecf_property_context(doc, block, 'EnergyOut', '150', 'BlocksConfig.ecf')
    assert ctx.current == '150'
    assert ctx.glossary  # entree reelle du glossaire BlocksConfig
    # 3 valeurs numeriques -> mediane 150, pas « valeur la plus frequente »
    assert '150' in ctx.observed and '3' in ctx.observed
    assert any('150' in s for s in ctx.suggestions)


def test_property_context_without_glossary_or_values_omits_facts():
    doc = _doc()
    block = _block(doc, 'GenSmall')
    ctx = ecf_property_context(doc, block, 'CleInconnue', None, 'BlocksConfig.ecf')
    assert ctx.glossary is None
    assert ctx.vanilla is None
    assert ctx.observed is None


def test_block_context_lists_kind_and_properties():
    doc = _doc()
    block = _block(doc, 'GenBig')
    ctx = ecf_block_context(doc, block, 'BlocksConfig.ecf')
    assert 'GenBig' in ctx.title
    joined = '\n'.join(ctx.facts)
    assert '+Block' in joined and 'Name=GenBig' in joined


def test_messages_follow_language_and_only_use_facts():
    ctx = ExplainContext(title='X', subject='k', current='1',
                         suggestions=['2 (vanille)'])
    fr = ctx.messages('fr')
    assert fr[0]['role'] == 'system'
    assert 'francais' in fr[0]['content']
    assert 'Champ a expliquer' in fr[1]['content']
    assert '2 (vanille)' in fr[1]['content']
    en = ctx.messages('en')
    assert 'English' in en[0]['content']


def test_csv_context_uses_column_family():
    header = ['Key', 'English', 'Français']
    rows = [['A', 'Iron', 'Fer'], ['B', 'Copper', 'Cuivre'],
            ['C', 'Iron', 'Fer']]
    ctx = csv_context(header, rows, 0, 1, 'Localization.csv')
    assert ctx.subject == 'English'
    assert ctx.current == 'Iron'
    assert 'Iron' in ctx.observed
    assert any('Iron' in s for s in ctx.suggestions)


def test_yaml_context_uses_same_key_values():
    doc = parse_yaml_text("Items:\n  - Block: A\n    Count: 10\n"
                          "  - Block: B\n    Count: 30\n"
                          "  - Block: C\n    Count: 20\n")
    ctx = yaml_context(doc, 'Count', '20', 'Items/Count', 'Templates.yaml')
    assert ctx.current == '20'
    assert '20' in ctx.observed  # mediane de 10/30/20


def test_localization_get_exact_does_not_fall_back_to_english():
    index = LocalizationIndex({'k': {'English': 'Hello', 'Français': ''}})
    assert index.get('k', 'fr') == 'Hello'
    assert index.get_exact('k', 'fr') is None
    assert index.get_exact('k', 'en') == 'Hello'
