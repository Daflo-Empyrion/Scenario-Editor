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
