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

"""Mode LOTS du moteur Groq (v1.8.0) : plusieurs cellules par requete
(tier gratuit plafonne en debit), bornes de lot (core/translation.
batch_chunks), decodage des enveloppes <CELLn> (core/groq_provider.
translate_batch), cascade lots -> cellule entiere -> fragments, entree
translate_batch_with_source et worker. Aucun reseau : _chat et les
fonctions moteur sont remplacees par des doubles."""

import pytest
from PyQt6.QtCore import QEventLoop

from core import groq_provider, settings, translation


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Settings isoles + throttle coupe + memoires vides + glossaire isole
    (le glossaire REEL piege les textes de test type 'Hello world') : jamais
    le vrai settings.json ni la vraie memoire de l'utilisateur."""
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(groq_provider, "MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(groq_provider, "_cooldown_until", 0.0)
    monkeypatch.setattr(groq_provider, "_last_call", 0.0)
    settings.set_groq_api_key("gsk_test_key")
    settings.set_groq_batch_enabled(True)
    import core.glossary as g
    import core.translation_memory as tm
    import core.vanilla_memory as vm
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)
    monkeypatch.setattr(tm, "get_cached", lambda *a, **k: None)
    monkeypatch.setattr(vm, "get_vanilla_cached", lambda *a, **k: None)


# ---------------------------------------------------------------- batch_chunks

def test_batch_chunks_groups_by_count():
    texts = [f"texte {i}" for i in range(20)]
    chunks = translation.batch_chunks(texts, max_cells=8, max_chars=100000)
    assert [len(c) for c in chunks] == [8, 8, 4]
    assert chunks[0] == list(range(8))


def test_batch_chunks_groups_by_chars():
    # 3000+16 chars : le 1er part seul (le 2e depasserait max_chars=4000),
    # le 3e est petit et rejoint le 2e.
    texts = ["a" * 3000, "b" * 3000, "c" * 10]
    chunks = translation.batch_chunks(texts, max_cells=8, max_chars=4000)
    assert chunks == [[0], [1, 2]]


def test_batch_chunks_empty():
    assert translation.batch_chunks([]) == []


# ------------------------------------------------- groq_provider.translate_batch

def _capture_chat(monkeypatch, response):
    seen = {}

    def fake_chat(payload):
        seen["payload"] = payload
        return response

    monkeypatch.setattr(groq_provider, "_chat", fake_chat)
    return seen


def test_translate_batch_parses_cells(monkeypatch):
    response = ("<CELL0>bonjour</CELL0>\n<CELL1>le reacteur "
                "surchauffe XXTAG0XX</CELL1>")
    seen = _capture_chat(monkeypatch, response)
    out = groq_provider.translate_batch(["hello XXTAG0XX", "the reactor"], "fr")
    assert out == ["bonjour", "le reacteur surchauffe XXTAG0XX"]
    user_content = seen["payload"]["messages"][1]["content"]
    assert "<CELL0>hello XXTAG0XX</CELL0>" in user_content
    assert "<CELL1>the reactor</CELL1>" in user_content


def test_translate_batch_missing_envelope_gives_none(monkeypatch):
    _capture_chat(monkeypatch, "<CELL0>bonjour</CELL0>")  # CELL1 perdue
    out = groq_provider.translate_batch(["hello", "world"], "fr")
    assert out == ["bonjour", None]


def test_translate_batch_duplicate_envelope_gives_none(monkeypatch):
    _capture_chat(monkeypatch, "<CELL0>a</CELL0><CELL0>b</CELL0>")
    out = groq_provider.translate_batch(["hello", "world"], "fr")
    assert out == [None, None]


def test_translate_batch_strips_chatter_after_close(monkeypatch):
    response = "<CELL0>bonjour</CELL0>\n\nVoici la traduction demandee !"
    _capture_chat(monkeypatch, response)
    out = groq_provider.translate_batch(["hello"], "fr")
    assert out == ["bonjour"]


def test_translate_batch_empty_input_no_request(monkeypatch):
    seen = _capture_chat(monkeypatch, "")
    assert groq_provider.translate_batch([], "fr") == []
    assert "payload" not in seen


def test_translate_batch_api_error_propagates(monkeypatch):
    def boom(payload):
        raise RuntimeError("Cle API Groq refusee (401).")

    monkeypatch.setattr(groq_provider, "_chat", boom)
    with pytest.raises(RuntimeError, match="401"):
        groq_provider.translate_batch(["hello"], "fr")


# --------------------------------------------------------- style / ton (consigne)

def test_style_directive_injected_in_all_requests(monkeypatch):
    seen = _capture_chat(monkeypatch, "<CELL0>bonjour</CELL0>")
    settings.set_groq_style("Registre militaire, tutoiement.")
    groq_provider.translate_batch(["hello"], "fr")
    assert "Registre militaire" in seen["payload"]["messages"][0]["content"]
    groq_provider.translate_whole("hello", "fr")
    assert "Registre militaire" in seen["payload"]["messages"][0]["content"]
    groq_provider.translate("hello", "en", "fr")
    assert "Registre militaire" in seen["payload"]["messages"][0]["content"]


def test_style_directive_absent_when_empty(monkeypatch):
    seen = _capture_chat(monkeypatch, "<CELL0>bonjour</CELL0>")
    settings.set_groq_style("   ")
    groq_provider.translate_batch(["hello"], "fr")
    assert "Style directive" not in seen["payload"]["messages"][0]["content"]


# ---------------------------------------------- translate_batch_with_source

@pytest.fixture
def groq_batch_env(monkeypatch):
    """Moteur groq + mode lots actif + LLM factice qui conserve les jetons
    et wrappe le texte ; capture les appels par forme."""
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_groq_batch_enabled", lambda: True)
    import re as _re
    calls = {"batch": [], "whole": [], "frag": []}

    def fake_batch(protected_list, target):
        calls["batch"].append(list(protected_list))
        return [f"[FR]{t}[/FR]" for t in protected_list]

    def fake_whole(protected, target):
        calls["whole"].append(protected)
        return f"[FR]{protected}[/FR]"

    def fake_frag(text, src, tgt):
        calls["frag"].append(text)
        return f"[F]{text}[/F]"

    monkeypatch.setattr(groq_provider, "translate_batch", fake_batch)
    monkeypatch.setattr(groq_provider, "translate_whole", fake_whole)
    monkeypatch.setattr(groq_provider, "translate", fake_frag)
    return calls


def test_batch_path_one_request_for_all_cells(groq_batch_env):
    calls = groq_batch_env
    out = translation.translate_batch_with_source(
        ["hello", "the reactor", "goodbye"], target="fr")
    assert out == [("[FR]hello[/FR]", "engine"),
                   ("[FR]the reactor[/FR]", "engine"),
                   ("[FR]goodbye[/FR]", "engine")]
    assert len(calls["batch"]) == 1
    assert calls["whole"] == [] and calls["frag"] == []


def test_batch_single_cell_uses_classic_path(groq_batch_env):
    # une seule cellule : pas de requete lot (le LLM verrait une enveloppe
    # unique pour rien) -- chemin cellule entiere classique
    calls = groq_batch_env
    out = translation.translate_batch_with_source(["hello"], target="fr")
    assert out == [("[FR]hello[/FR]", "engine")]
    assert calls["batch"] == [] and len(calls["whole"]) == 1


def test_batch_divergent_cell_falls_back_to_whole_cell(groq_batch_env,
                                                       monkeypatch):
    """Une cellule deviante dans la reponse du lot (squelette de jetons
    perdu) repasse SEULE en mode cellule entiere ; les autres gardent le
    resultat du lot."""
    calls = groq_batch_env

    def deviant_batch(protected_list, target):
        calls["batch"].append(list(protected_list))
        out = []
        for t in protected_list:
            if "XXTAG0XX" in t:
                out.append("reponse sans les jetons")  # squelette perdu
            else:
                out.append(f"[FR]{t}[/FR]")
        return out

    monkeypatch.setattr(groq_provider, "translate_batch", deviant_batch)
    out = translation.translate_batch_with_source(
        ["fine", "broken [b]bold[/b]"], target="fr")
    assert out[0] == ("[FR]fine[/FR]", "engine")
    # la cellule deviante a repasse par translate_whole (fake du fixture :
    # jetons conserves -> balises restorees proprement)
    assert out[1] == ("[FR]broken [b]bold[/b][/FR]", "engine")
    assert calls["whole"] == ["broken XXTAG0XXboldXXTAG1XX"]


def test_batch_memory_and_vanilla_resolved_without_engine(groq_batch_env,
                                                          monkeypatch):
    import core.translation_memory as tm
    import core.vanilla_memory as vm
    monkeypatch.setattr(tm, "get_cached",
                        lambda text, src, tgt: "MEM:" + text
                        if text == "cached" else None)
    monkeypatch.setattr(vm, "get_vanilla_cached",
                        lambda text, target: "VAN:" + text
                        if text == "vanilla" else None)
    calls = groq_batch_env
    out = translation.translate_batch_with_source(
        ["cached", "vanilla", "fresh1", "fresh2"], target="fr")
    assert out[0] == ("MEM:cached", "memory")
    assert out[1] == ("VAN:vanilla", "vanilla")
    assert out[2] == ("[FR]fresh1[/FR]", "engine")
    assert out[3] == ("[FR]fresh2[/FR]", "engine")
    # seules les cellules sans memoire partent au moteur
    assert calls["batch"][0] == ["fresh1", "fresh2"]


def test_batch_disabled_uses_per_cell_path(monkeypatch):
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_groq_batch_enabled", lambda: False)
    seen = []

    def fake_translate(text, target="fr", source="auto",
                       store_in_memory=False, **kw):
        seen.append(text)
        return "TRAD:" + text

    monkeypatch.setattr(translation, "translate_text", fake_translate)
    out = translation.translate_batch_with_source(["a", "b"], target="fr")
    assert out == [("TRAD:a", "engine"), ("TRAD:b", "engine")]
    assert seen == ["a", "b"]


def test_batch_other_engine_uses_per_cell_path(monkeypatch):
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "google")
    seen = []
    monkeypatch.setattr(
        translation, "translate_text",
        lambda text, target="fr", source="auto", store_in_memory=False, **kw:
        seen.append(text) or "TRAD:" + text)
    out = translation.translate_batch_with_source(["a", "b"], target="fr")
    assert out == [("TRAD:a", "engine"), ("TRAD:b", "engine")]
    assert seen == ["a", "b"]


def test_batch_empty_and_blank_texts_skipped(groq_batch_env):
    out = translation.translate_batch_with_source(["", "  ", "hello"],
                                                  target="fr")
    assert out == [("", ""), ("  ", ""), ("[FR]hello[/FR]", "engine")]
    # une seule cellule restante : chemin cellule entiere classique,
    # jamais une requete lot pour une enveloppe unique
    assert groq_batch_env["batch"] == []
    assert groq_batch_env["whole"] == ["hello"]


# ------------------------------------------------------------------- worker

def test_worker_batch_path_emits_all_cells(qapp, monkeypatch):
    """Moteur groq + lots actifs : le worker groupe les cellules en lots,
    emet item_done pour chacune avec la source du moteur."""
    from gui.translation_worker import BatchTranslationWorker
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_groq_batch_enabled", lambda: True)
    batch_calls = []

    def fake_batch(texts, target="fr"):
        batch_calls.append(list(texts))
        return [("TRAD:" + t, "engine") for t in texts]

    monkeypatch.setattr(translation, "translate_batch_with_source", fake_batch)

    worker = BatchTranslationWorker(["a", "b", "c"], "fr")
    results = {}
    loop = QEventLoop()
    worker.item_done.connect(
        lambda i, tr, err, src: results.__setitem__(i, (tr, src)))
    worker.finished_all.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait()

    assert results == {0: ("TRAD:a", "engine"), 1: ("TRAD:b", "engine"),
                       2: ("TRAD:c", "engine")}
    assert len(batch_calls) == 1 and batch_calls[0] == ["a", "b", "c"]


def test_worker_batch_api_error_fails_whole_chunk(qapp, monkeypatch):
    """Erreur API sur un lot : chaque cellule du lot recoit l'erreur (le
    dialogue compte les echecs consecutifs et stoppe au-dela de 5)."""
    from gui.translation_worker import BatchTranslationWorker
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_groq_batch_enabled", lambda: True)

    def boom(texts, target="fr"):
        raise RuntimeError("Quota Groq epuise.")

    monkeypatch.setattr(translation, "translate_batch_with_source", boom)

    worker = BatchTranslationWorker(["a", "b"], "fr")
    errors = {}
    loop = QEventLoop()
    worker.item_done.connect(
        lambda i, tr, err, src: errors.__setitem__(i, err))
    worker.finished_all.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait()
    assert errors == {0: "Quota Groq epuise.", 1: "Quota Groq epuise."}


def test_worker_single_text_keeps_classic_path(qapp, monkeypatch):
    """Un texte seul : chemin v1.7.0 preserve (translate_text_with_source
    mocke -- contrat des tests worker existants)."""
    from gui.translation_worker import BatchTranslationWorker
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_groq_batch_enabled", lambda: True)
    monkeypatch.setattr(translation, "translate_text_with_source",
                        lambda text, target="fr": ("TRAD:" + text, "engine"))
    worker = BatchTranslationWorker(["a"], "fr")
    results = {}
    loop = QEventLoop()
    worker.item_done.connect(
        lambda i, tr, err, src: results.__setitem__(i, (tr, src)))
    worker.finished_all.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait()
    assert results == {0: ("TRAD:a", "engine")}


# --------------------------------------------------------- progression CSV

def test_csv_translation_progress(tmp_path):
    from core.translation_progress import csv_translation_progress
    p = tmp_path / "PDA.csv"
    p.write_text(
        "Key,EN,FR,DE\n"
        'k1,"Hello","Bonjour","Hallo"\n'
        'k2,"World","","Welt"\n'
        'k3,"Done","Fait","Fertig"\n',
        encoding="utf-8")
    assert csv_translation_progress(p) == (2, 3)


def test_csv_translation_progress_no_language_columns(tmp_path):
    from core.translation_progress import csv_translation_progress
    p = tmp_path / "autre.csv"
    p.write_text("Name,Value\nfoo,1\n", encoding="utf-8")
    assert csv_translation_progress(p) is None


def test_csv_translation_progress_corrupt_file(tmp_path):
    from core.translation_progress import csv_translation_progress
    p = tmp_path / "cassee.csv"
    p.write_bytes(b"\xff\xfe\x00broken")
    assert csv_translation_progress(p) is None


def test_csv_translation_progress_same_language(tmp_path):
    from core.translation_progress import csv_translation_progress
    p = tmp_path / "PDA.csv"
    p.write_text("Key,EN,FR\nk1,Hello,Bonjour\n", encoding="utf-8")
    assert csv_translation_progress(p, target="en") is None


def test_scenario_translation_progress_aggregates(tmp_path):
    from core.translation_progress import scenario_translation_progress
    p1 = tmp_path / "PDA.csv"
    p1.write_text("Key,EN,FR\nk1,Hello,Bonjour\nk2,World,\n",
                  encoding="utf-8")
    p2 = tmp_path / "sans_langue.csv"
    p2.write_text("A,B\n1,2\n", encoding="utf-8")
    out = scenario_translation_progress([p1, p2])
    assert out == [(str(p1), 1, 2)]
