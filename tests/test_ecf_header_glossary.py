"""
Tests du glossaire d'explication ECF (core/ecf_header_glossary.py) --
verifie l'absence de la limite d'Id perimee (2048, corrigee en 8192 lors
d'un audit complet du projet).
"""


def test_no_stale_2048_id_limit():
    """'2048' est volontairement mentionne comme reference historique explicite
    ('2048 puis 4096 sont des valeurs perimees') -- ce test verifie que ce n'est
    plus presente comme LA limite actuelle (regression cible : l'ancienne
    affirmation 'Id jusqu'a 2048')."""
    from core.ecf_header_glossary import GLOSSARY_BY_FILE
    glossary = GLOSSARY_BY_FILE.get("BlocksConfig.ecf")
    assert glossary is not None
    all_terms = []
    all_text = ""
    for category, entries in glossary:
        for term, explanation in entries:
            all_terms.append(term)
            all_text += term + explanation
    assert "Id jusqu'a 2048" not in all_terms
    assert "Id jusqu'a 8192" in all_terms
    assert "8192" in all_text


def test_find_term_explanation_exact_match():
    """Cle de propriete correspondant exactement a un terme du glossaire."""
    from core.ecf_header_glossary import find_term_explanation
    result = find_term_explanation("BlocksConfig.ecf", "AllowPlacingAt")
    assert result is not None
    assert "Base" in result


def test_find_term_explanation_grouped_term():
    """Un terme groupe comme 'EnergyIn / EnergyOut' doit repondre pour
    chacun des deux membres separement."""
    from core.ecf_header_glossary import find_term_explanation
    result_in = find_term_explanation("BlocksConfig.ecf", "EnergyIn")
    result_out = find_term_explanation("BlocksConfig.ecf", "EnergyOut")
    assert result_in is not None
    assert result_in == result_out


def test_find_term_explanation_case_insensitive():
    from core.ecf_header_glossary import find_term_explanation
    result = find_term_explanation("BlocksConfig.ecf", "allowplacingat")
    assert result is not None


def test_find_term_explanation_unknown_file_returns_none():
    from core.ecf_header_glossary import find_term_explanation
    assert find_term_explanation("FichierInconnu.ecf", "AllowPlacingAt") is None


def test_find_term_explanation_unknown_term_returns_none():
    from core.ecf_header_glossary import find_term_explanation
    assert find_term_explanation("BlocksConfig.ecf", "ProprieteQuiNexistePas") is None
