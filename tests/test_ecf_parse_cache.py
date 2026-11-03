"""Cache de parsing opt-in (core/ecf/parser.parse_ecf_file_cached) :
reserves aux analyses LECTURE SEULE — meme objet pour un fichier inchange,
nouvel objet apres modification (mtime/taille), eviction par le hook
d'ecriture de core.fsutil, et JAMAIS partage avec les editeurs (mutation)."""
import os

import pytest

from core.ecf.parser import (clear_parse_cache, parse_ecf_file,
                             parse_ecf_file_cached)

ECF = "{ +Container Id: 1\n  Name: Caisse\n}\n"


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_parse_cache()
    yield
    clear_parse_cache()


def test_same_object_on_unchanged_file(tmp_path):
    path = tmp_path / "Items.ecf"
    path.write_text(ECF, encoding="utf-8")
    d1 = parse_ecf_file_cached(path)
    d2 = parse_ecf_file_cached(path)
    assert d1 is d2                       # hit : meme objet, un seul parse


def test_external_modification_busts_the_key(tmp_path):
    path = tmp_path / "Items.ecf"
    path.write_text(ECF, encoding="utf-8")
    d1 = parse_ecf_file_cached(path)
    path.write_text(ECF.replace("Caisse", "Baril"), encoding="utf-8")
    os.utime(path, ns=(1_000_000_000, 2_000_000_000))   # mtime force
    d2 = parse_ecf_file_cached(path)
    assert d1 is not d2
    assert "Baril" in d2.render()


def test_atomic_write_evicts_through_fsutil_hook(tmp_path):
    from core.fsutil import atomic_write_text
    path = tmp_path / "Items.ecf"
    path.write_text(ECF, encoding="utf-8")
    d1 = parse_ecf_file_cached(path)
    # meme contenu mais ecriture ATOMIQUE reelle -> hook -> eviction ;
    # mtime_ns change de toute facon, on verifie surtout le chemin du hook
    atomic_write_text(path, ECF)
    d2 = parse_ecf_file_cached(path)
    assert d1 is not d2


def test_editors_never_share_the_cached_doc(tmp_path):
    """Un doc cache mute ne doit JAMAIS fuir vers un editeur : les editeurs
    passent par parse_ecf_file (sans cache) et obtiennent un objet distinct
    reconstruit depuis le disque."""
    path = tmp_path / "Items.ecf"
    path.write_text(ECF, encoding="utf-8")
    cached = parse_ecf_file_cached(path)
    block = next(iter(cached.iter_blocks()))
    prop = next(c for c in block.children if hasattr(c, "pairs"))
    prop.pairs[0] = ("Name", "MUTATION")   # un lecteur brutal mute le cache
    fresh = parse_ecf_file(path)           # chemin EDITEUR : pas de cache
    assert "Caisse" in fresh.render()      # le disque n'a pas bouge
    assert "MUTATION" not in fresh.render()


def test_uncached_parse_returns_distinct_objects(tmp_path):
    path = tmp_path / "Items.ecf"
    path.write_text(ECF, encoding="utf-8")
    a = parse_ecf_file(path)
    b = parse_ecf_file(path)
    assert a is not b                      # l'editeur reparse toujours


def test_missing_file_raises_like_uncached(tmp_path):
    with pytest.raises(OSError):
        parse_ecf_file_cached(tmp_path / "absent.ecf")
