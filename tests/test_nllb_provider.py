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

"""Moteur local NLLB (core/nllb_provider.py) -- protocole de tokenisation
NLLB (code langue source en tete, EOS, target_prefix, retrait du code cible
et de l'EOS), installation et chemin translate_text. CTranslate2 et
SentencePiece sont MOCKES : aucun modele reel requis."""

import io
import json
from pathlib import Path

import pytest

from core import nllb_provider, translation


@pytest.fixture(autouse=True)
def _isolate_stores(tmp_path, monkeypatch):
    """Isole glossaire ET memoire de traduction du fichier reel (les tests
    du protocole ecrivent des entrees de demonstration)."""
    import core.translation_memory as tm
    monkeypatch.setattr(tm, "MEMORY_FILE", tmp_path / "translation_memory.json")
    monkeypatch.setattr(tm, "_cache", None)


@pytest.fixture(autouse=True)
def _isolate_glossary(tmp_path, monkeypatch):
    """Isole le glossaire du fichier reel de la machine (les tests y ecrivent
    des entrees de demonstration)."""
    from core import glossary as g
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)


class FakeSP:
    """SentencePiece factice : split sur espaces / join."""

    def __init__(self, model_file=None):
        pass

    def encode(self, text, out_type=str):
        return text.split()

    def decode(self, tokens):
        return " ".join(tokens)


class FakeSPModule:
    SentencePieceProcessor = FakeSP


class FakeTranslator:
    """Reproduit le protocole NLLB : hypothese = [tgt] + tokens source
    (sans code langue ni EOS) + [</s>]."""

    last_instance = None

    def __init__(self, path, device=None, inter_threads=None):
        self.path = path
        FakeTranslator.last_instance = self

    def translate_batch(self, tokens_list, target_prefix=None, beam_size=None):
        src_tokens = tokens_list[0]
        tgt = target_prefix[0][0]
        hyp = [tgt] + [t for t in src_tokens if t not in (src_tokens[0], "</s>")]
        hyp = hyp + ["</s>"]
        result = type("R", (), {})()
        result.hypotheses = [hyp]
        return [result]


class FakeCt2Module:
    Translator = FakeTranslator


@pytest.fixture()
def fake_engine(tmp_path, monkeypatch):
    d = tmp_path / "nllb"
    d.mkdir()
    (d / "model.bin").write_bytes(b"x")
    (d / "sentencepiece.bpe.model").write_bytes(b"x")
    monkeypatch.setattr(nllb_provider, "_VARIANTS", {
        "600M": {"repo": "fake/repo", "dir": d},
        "1.3B": {"repo": "fake/repo", "dir": tmp_path / "nllb13"},
    })
    monkeypatch.setattr(nllb_provider, "spm", FakeSPModule)
    monkeypatch.setattr(nllb_provider, "ctranslate2", FakeCt2Module)
    # vider le cache global des translators : il survivrait au test precedent
    # et renverrait le Translator instancie sur SON dossier tmp
    nllb_provider._translators.clear()
    return d


def test_nllb_code_mapping():
    assert nllb_provider.nllb_code("fr") == "fra_Latn"
    assert nllb_provider.nllb_code("en") == "eng_Latn"
    assert nllb_provider.nllb_code("zh-CN") == "zho_Hans"
    assert nllb_provider.nllb_code("langue_inconnue") == "eng_Latn"


def test_is_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(nllb_provider, "_VARIANTS", {
        "600M": {"repo": "r", "dir": tmp_path}})
    assert not nllb_provider.is_installed("600M")
    (tmp_path / "model.bin").write_bytes(b"x")
    (tmp_path / "sentencepiece.bpe.model").write_bytes(b"x")
    assert nllb_provider.is_installed("600M")


def test_translate_protocol(fake_engine):
    """Protocole NLLB : [src_code] + tokens + [</s>] en entree, retrait du
    code cible et de l'EOS en sortie."""
    out = nllb_provider.translate("Hello world", "en", "fr", "600M")
    assert out == "Hello world"  # fake : tokens renvoyes a l'identique


def test_beam_size_setting_roundtrip(tmp_path, monkeypatch):
    """Reglage 'finesse du decodage' (17/09/2026) : persiste, borne 1..10,
    defaut 4."""
    from core import settings
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    assert settings.get_nllb_beam_size() == 4
    settings.set_nllb_beam_size(8)
    assert settings.get_nllb_beam_size() == 8
    settings.set_nllb_beam_size(99)  # hors bornes : ignore
    assert settings.get_nllb_beam_size() == 8


def test_variant_radios_show_and_change_active(qapp, tmp_path, monkeypatch):
    """Demande 17/09/2026 : le 600M et le 1.3B peuvent etre installes tous
    les deux -- la radio montre laquelle est UTILISEE et permet de changer."""
    from core import settings, nllb_provider as np
    from gui.nllb_setup_dialog import NllbSetupDialog
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(np, "is_installed", lambda v: True)
    settings.set_nllb_variant("1.3B")
    d = NllbSetupDialog()
    try:
        assert d.variant_radios["1.3B"].isChecked()
        assert not d.variant_radios["600M"].isChecked()
        # cliquer l'autre radio persiste le changement
        d.variant_radios["600M"].setChecked(True)
        assert settings.get_nllb_variant() == "600M"
        assert not d.variant_radios["1.3B"].isChecked()
    finally:
        d.close()


def test_beam_size_transmitted_to_translator(fake_engine, monkeypatch):
    """Le beam size du reglage atteint translate_batch (2 rapide / 4
    equilibre / 8 qualite)."""
    from core import settings as core_settings
    monkeypatch.setattr(core_settings, "get_nllb_beam_size", lambda: 8)
    seen = {}

    outer = nllb_provider.ctranslate2.Translator

    class SpyTranslator(outer):
        def translate_batch(self, tokens_list, target_prefix=None,
                            beam_size=None):
            seen["beam"] = beam_size
            return super().translate_batch(tokens_list,
                                           target_prefix=target_prefix,
                                           beam_size=beam_size)

    class SpyModule:
        Translator = SpyTranslator
    monkeypatch.setattr(nllb_provider, "ctranslate2", SpyModule)
    nllb_provider._translators.clear()
    try:
        nllb_provider.translate("Hello", "en", "fr", variant="600M")
    finally:
        nllb_provider._translators.clear()
    assert seen["beam"] == 8


def test_nllb_fragment_via_translate_text(fake_engine, monkeypatch):
    """Chemin translate_text moteur nllb : fragments (texte libre) traduits,
    balises restituees exactement."""
    from core import settings as core_settings
    from core import vanilla_memory
    import core.translation_memory as tm
    monkeypatch.setattr(core_settings, "get_translation_engine", lambda: "nllb")
    monkeypatch.setattr(core_settings, "get_nllb_variant", lambda: "600M")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled",
                        lambda: False)
    monkeypatch.setattr(tm, "get_cached", lambda *a: None)
    monkeypatch.setattr(tm, "store", lambda *a: None)
    monkeypatch.setattr(vanilla_memory, "get_vanilla_cached",
                        lambda text, target: None)
    out = translation.translate_text("[b]Hello world[/b]", target="fr",
                                     store_in_memory=False)
    # le fake est identite : le texte passe inchange, mais les balises sont
    # restituees exactement et le moteur a bien ete instancie sur la variante
    assert out == "[b]Hello world[/b]"
    assert str(FakeTranslator.last_instance.path) == str(fake_engine)


def test_translate_text_nllb_not_installed(tmp_path, monkeypatch):
    from core import settings as core_settings
    import core.translation_memory as tm
    monkeypatch.setattr(nllb_provider, "_VARIANTS", {
        "600M": {"repo": "r", "dir": tmp_path / "absent"}})
    monkeypatch.setattr(core_settings, "get_translation_engine", lambda: "nllb")
    # isoler du REGLAGE reel de la machine (la variante activee peut etre
    # 1.3B -- vecu 17/09/2026 : le test cassait des qu'on telechargeait 1.3B)
    monkeypatch.setattr(core_settings, "get_nllb_variant", lambda: "600M")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled",
                        lambda: False)
    monkeypatch.setattr(tm, "get_cached", lambda *a: None)
    with pytest.raises(RuntimeError):
        translation.translate_text("Hello", target="fr")
