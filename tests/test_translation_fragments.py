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

"""Traduction hors ligne par FRAGMENTS (12/09/2026) : Argos recopie sans
traduire les textes a forte densite de BBCode envoyes entiers (vecu reel :
'Prologue: ... Journey into the unknown' du PDA.csv Atlantis revenait en
anglais). Desormais seuls les fragments de texte libre partent au moteur,
et le texte est reconstruit avec les balises d'origine -- structure
garantie par construction. Le moteur est MOCKE ici : aucun modele Argos
requis pour les tests."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_glossary(tmp_path, monkeypatch):
    """Isole le glossaire du fichier reel de la machine (les tests y ont
    ecrit des entrees de demonstration)."""
    from core import glossary as g
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)



from core import translation


@pytest.fixture()
def fake_argos(monkeypatch):
    """Remplace le moteur Argos par un traducteur factice verifiable."""
    calls = []

    def fake(text, source, target):
        calls.append(text)
        return f"[FR]{text}[/FR]"

    from core import argos_provider, settings as core_settings
    monkeypatch.setattr(argos_provider, "translate_offline", fake)
    # translate_text fait un import local 'from . import settings as _settings'
    # : c'est le MODULE core.settings qu'il faut patcher.
    monkeypatch.setattr(core_settings, "get_translation_engine",
                        lambda: "argos")
    return calls


def test_fragments_translate_only_free_text(fake_argos):
    out = translation._translate_offline_fragments(
        "[b]Prologue:[/b] [b][c][00fbff]Journey[-]![/c][/b]", "en", "fr")
    # balises ET [-] reinjectes EXACTES, fragments traduits a leur place ; le
    # fragment '!' (ponctuation seule, aucun alphanumerique) ne part PAS au
    # moteur -- Argos hallucine sur ces fragments ('!' -> '- Oui.', vecu reel)
    assert out == ("[b][FR]Prologue:[/FR][/b] "
                   "[b][c][00fbff][FR]Journey[/FR][-]![/c][/b]")
    # le moteur ne recoit JAMAIS de balise BBCode (les jetons remplacent tout,
    # y compris la balise de fermeture Empyrion [-])
    for call in fake_argos:
        assert "[" not in call and "]" not in call


def test_fragments_preserve_border_spaces(fake_argos):
    out = translation._translate_offline_fragments(
        "[b] Bonjour [/b]monde", "en", "fr")
    # les espaces de bord du fragment original sont conserves autour de la
    # traduction (le modele n'a pas a les decider)
    assert out == "[b] [FR]Bonjour[/FR] [/b][FR]monde[/FR]"


def test_fragments_without_tags_single_call(fake_argos):
    out = translation._translate_offline_fragments("A whole new world", "en", "fr")
    assert out == "[FR]A whole new world[/FR]"
    assert len(fake_argos) == 1


def test_fragments_no_tag_leak(fake_argos):
    out = translation._translate_offline_fragments("===", "en", "fr")
    # pas de jeton XXTAG jamais expose dans le resultat final
    assert "XXTAG" not in out


def test_clean_argos_entities():
    # entite COUPEE par le tokenizer Argos (vecu reel : 'Heure & #160;:')
    assert translation._clean_argos_entities("Heure & #160;:") == "Heure\xa0:"
    assert translation._clean_argos_entities("Heure&#160;:") == "Heure\xa0:"
    # esperluette litterale du jeu intacte (pas une entite)
    assert translation._clean_argos_entities("a & b") == "a & b"


def test_pipeline_cleans_argos_entities(fake_argos, monkeypatch):
    from core import argos_provider

    def entity_output(text, source, target):
        return "Heure & #160;:" if text == "Time:" else f"[FR]{text}[/FR]"
    monkeypatch.setattr(argos_provider, "translate_offline", entity_output)

    out = translation._translate_offline_fragments(
        "[b]Time:[/b] 1900", "en", "fr")
    assert out == "[b]Heure\xa0:[/b] [FR]1900[/FR]"
    assert "&" not in out and "#160" not in out


def test_translate_text_offline_uses_fragments(fake_argos, monkeypatch):
    from core import settings as core_settings
    from core import vanilla_memory
    import core.translation_memory as tm
    monkeypatch.setattr(core_settings, "get_online_translation_enabled",
                        lambda: False)
    # isolation de la memoire : cache utilisateur vide ET vanille neutralisee
    # (le vrai Localization.csv du jeu contient 'Hello world' -> 'Bonjour le
    # monde' : la traduction officielle prime sinon sur le moteur mocke), et
    # aucun store vers le fichier reel
    monkeypatch.setattr(tm, "get_cached", lambda text, source, target: None)
    monkeypatch.setattr(tm, "store", lambda *a: None)
    monkeypatch.setattr(vanilla_memory, "get_vanilla_cached",
                        lambda text, target: None)
    out = translation.translate_text("[b]Hello world[/b]", target="fr",
                                     store_in_memory=False)
    assert out == "[b][FR]Hello world[/FR][/b]"


def test_translate_text_argos_failure_raises_combined(monkeypatch):
    from core import argos_provider, settings as core_settings
    monkeypatch.setattr(core_settings, "get_translation_engine",
                        lambda: "argos")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled",
                        lambda: False)

    def boom(text, source, target):
        raise RuntimeError("paire de langues absente")
    monkeypatch.setattr(argos_provider, "translate_offline", boom)

    with pytest.raises(RuntimeError, match="hors ligne impossible"):
        translation.translate_text("Hello", target="fr")


def test_azure_engine_missing_key_raises(monkeypatch):
    """Moteur 'azure' RETIRE de l'application (12/09/2026, configuration
    trop lourde) : ce test assure qu'un settings.json residuel avec
    translation_engine='azure' NE bascule PAS silencieusement vers Google si
    l'online est desactive -- erreur explicite."""
    from core import settings as core_settings
    monkeypatch.setattr(core_settings, "get_translation_engine", lambda: "azure")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled",
                        lambda: False)
    with pytest.raises(RuntimeError):
        translation.translate_text("Hello", target="fr")
