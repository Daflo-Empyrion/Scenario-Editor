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
    ecrit des entrees de demonstration) + bascule automatique OFF : ces
    tests verifient le chemin mono-moteur historique (sinon une machine
    de dev avec NLLB installe ferait servir la chaine de secours)."""
    from core import glossary as g
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)
    # Les traductions reussies ici sont stockees (store_in_memory par
    # defaut) : ne JAMAIS ecrire dans la vraie memoire de la machine
    # (vecu 19/09/2026 : entree "Hello" polluee pour les autres tests).
    import core.translation_memory as tm
    monkeypatch.setattr(tm, "MEMORY_FILE", tmp_path / "translation_memory.json")
    monkeypatch.setattr(tm, "_cache", None)
    monkeypatch.setattr("core.settings.get_engine_fallback_enabled",
                        lambda: False)



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


def test_dialog_tag_protected(fake_argos):
    """Balise de dialogue Empyrion '[IDA :]' (nom + ':' DANS la balise) :
    structure du jeu, jamais du texte a traduire. Vecu reel 17/09/2026
    (PDA.csv Atlantis) : '[IDA :]' parti au moteur comme fragment libre,
    ressorti 'Je vous en prie.' (hallucination)."""
    out = translation._translate_offline_fragments(
        "[b][c][ffff00] [IDA :]-[/c][/b][c][100ffff]These are the files[/c]",
        "en", "fr")
    # la balise de dialogue ET le tiret sont reinjectes a l'identique ; seul
    # le vrai texte part au moteur
    assert out == ("[b][c][ffff00] [IDA :]-[/c][/b]"
                   "[c][100ffff][FR]These are the files[/FR][/c]")
    for call in fake_argos:
        assert "IDA" not in call and "[" not in call


def test_dialog_tag_without_space_protected(fake_argos):
    out = translation._translate_offline_fragments("[NPC:] Well met", "en", "fr")
    assert out.startswith("[NPC:] [FR]Well met")
    for call in fake_argos:
        assert "NPC" not in call


def test_glossary_token_never_reaches_engine(fake_argos):
    """Glossaire 'IDA' -> 'IDA' (verrouiller un acronyme) : le jeton XXGLOS
    ne doit JAMAIS traverser un moteur (deforme -> restauration impossible,
    le terme etait traduit quand meme -- vecu reel 17/09/2026)."""
    from core import glossary
    glossary.add_entry("IDA", "IDA")
    jetoned, replacements = glossary.apply_glossary(
        "[c][ffff00] The IDA system[/c]")
    assert "XXGLOS0XX" in jetoned
    out = translation._translate_offline_fragments(jetoned, "en", "fr")
    out = glossary.restore_glossary(out, replacements)
    assert "IDA" in out and "XXGLOS" not in out
    for call in fake_argos:
        assert "XXGLOS" not in call and "IDA" not in call


def test_numbers_never_reach_engine(fake_argos):
    """Nombres isoles : jamais au moteur -- Argos hallucine dessus
    ('29827602.55' ressorti \"Le montant de l'impot sur le revenu\", vecu
    reel 17/09/2026). Les nombres colles aux lettres ('x50', '1A') restent
    du texte : ils font partie du mot."""
    out = translation._translate_offline_fragments(
        "[b]Runtime:[/b] 29827602.55\\nSteel Plate x50 since 1900",
        "en", "fr")
    assert "29827602.55" in out and "1900" in out and "\\n" in out
    for call in fake_argos:
        assert "29827602.55" not in call and "1900" not in call
    # 'x50' colle a une lettre : reste dans le fragment envoye (comportement
    # historique, le moteur le gere)
    assert any("x50" in call for call in fake_argos)


def test_decimal_date_protected(fake_argos):
    """Date pointee : protegee ENTIERE ('25.07.2473', jamais '25' traduit
    seul) -- jamais envoyee au moteur."""
    out = translation._translate_offline_fragments(
        "[b]Date:[/b] 25.07.2473 -- Log", "en", "fr")
    assert "25.07.2473" in out
    for call in fake_argos:
        assert "25.07.2473" not in call


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
    # l'entite COUPEE par Argos est resserree et decodee ; le nombre '1900'
    # est protege : jamais envoye au moteur (plus de [FR]1900[/FR])
    assert out == "[b]Heure\xa0:[/b] 1900"
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


def test_restore_segments_keeps_literal_backslash_n():
    """Bug vecu 19-20/09/2026 : restore_segments reinjectait les segments
    via re.sub avec un TEMPLATE chaine -- le \n litteral du CSV y etait
    interprete comme un VRAI retour a la ligne par le moteur d'expressions
    regulieres (pertes de \n sur tous les chemins "texte entier" :
    Groq, DeepL, Google). Le remplacement par FONCTION n'est jamais
    escape."""
    from core.translation import protect_segments, restore_segments
    text = "A\\nB [b]x[/b]"
    protected, segments = protect_segments(text)
    assert segments[0] == "\\n"  # le \n litteral est protege
    engine_out = protected  # moteur qui recopie les jetons tels quels
    out = restore_segments(engine_out, segments)
    assert "\\n" in out  # le \n litteral est REINJECTE tel quel
    assert chr(10) not in out  # aucun vrai retour a la ligne introduit
    assert out == "A\\nB [b]x[/b]"
