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

"""Moteur DEEPL API Free (v1.10.0, maillon de secours de la chaine) :
payload officiel /v2/translate, erreurs TYPEES (403 = AuthError -- jamais
de bascule silencieuse ; 456/429 = QuotaExhaustedError ; 5xx/reseau =
EngineUnavailableError), langue cible mappee (en -> EN-US, pt -> PT-BR).
Tout le reseau est MOCKE ici : aucun appel reel."""

import io
import json
import urllib.error

import pytest

from core import deepl_provider, settings
from core.engine_errors import (AuthError, EngineUnavailableError,
                                QuotaExhaustedError)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    settings.set_deepl_api_key("")


def _http_error(code, body=b'{"message":"detail"}'):
    return urllib.error.HTTPError(
        "https://api-free.deepl.com/v2/translate", code, "err",
        None, io.BytesIO(body))


def _mock_urlopen(monkeypatch, respond):
    """respond(req) -> dict (succes) ou leve. Capture la requete."""
    captured = {}

    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(respond(captured)).encode()

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        captured["timeout"] = timeout
        return _R()

    monkeypatch.setattr(deepl_provider.urllib.request, "urlopen", fake_urlopen)
    return captured


def test_is_configured(monkeypatch):
    assert deepl_provider.is_configured() is False
    settings.set_deepl_api_key("abc:fx")
    assert deepl_provider.is_configured() is True


def test_target_supported_mapping():
    assert deepl_provider.target_supported("fr")
    assert deepl_provider.target_supported("en")
    assert deepl_provider.target_supported("pt-BR")
    assert not deepl_provider.target_supported("xx")
    assert deepl_provider._TARGET_MAP["en"] == "EN-US"
    assert deepl_provider._TARGET_MAP["pt"] == "PT-BR"


def test_translate_payload_and_parsing(monkeypatch):
    captured = _mock_urlopen(monkeypatch, lambda req: {
        "translations": [{"detected_source_language": "EN",
                          "text": "Les generateurs sont surcharges."}]})
    settings.set_deepl_api_key("cle:fx")
    out = deepl_provider.translate("The generators are overloaded.", "fr")
    assert out == "Les generateurs sont surcharges."
    req = captured["req"]
    assert req.full_url.startswith(deepl_provider.BASE_FREE + "/translate")
    assert req.headers["Authorization"] == "DeepL-Auth-Key cle:fx"
    assert req.headers["User-agent"] == "EmpyrionScenarioEditor"
    body = json.loads(req.data.decode())
    assert body == {"text": ["The generators are overloaded."],
                    "target_lang": "FR", "preserve_formatting": True}


def test_translate_bad_key_403_is_auth(monkeypatch):
    settings.set_deepl_api_key("mauvaise")
    _mock_urlopen(monkeypatch, lambda req: (_ for _ in ()).throw(
        _http_error(403)))
    with pytest.raises(AuthError, match="refusee"):
        deepl_provider.translate("Hello", "fr")


def test_translate_quota_456(monkeypatch):
    settings.set_deepl_api_key("cle:fx")
    _mock_urlopen(monkeypatch, lambda req: (_ for _ in ()).throw(
        _http_error(456)))
    with pytest.raises(QuotaExhaustedError, match="500 000"):
        deepl_provider.translate("Hello", "fr")


def test_translate_rate_limit_429(monkeypatch):
    settings.set_deepl_api_key("cle:fx")
    _mock_urlopen(monkeypatch, lambda req: (_ for _ in ()).throw(
        _http_error(429)))
    with pytest.raises(QuotaExhaustedError):
        deepl_provider.translate("Hello", "fr")


def test_translate_server_error_5xx(monkeypatch):
    settings.set_deepl_api_key("cle:fx")
    _mock_urlopen(monkeypatch, lambda req: (_ for _ in ()).throw(
        _http_error(503)))
    with pytest.raises(EngineUnavailableError):
        deepl_provider.translate("Hello", "fr")


def test_translate_network_error(monkeypatch):
    settings.set_deepl_api_key("cle:fx")

    def boom(req, timeout=None):
        raise urllib.error.URLError("dns ko")
    monkeypatch.setattr(deepl_provider.urllib.request, "urlopen", boom)
    with pytest.raises(EngineUnavailableError, match="Reseau"):
        deepl_provider.translate("Hello", "fr")


def test_translate_unsupported_target_short_circuits(monkeypatch):
    captured = _mock_urlopen(
        monkeypatch, lambda req: (_ for _ in ()).throw(AssertionError(
            "aucun reseau attendu")))
    with pytest.raises(EngineUnavailableError, match="couvre pas"):
        deepl_provider.translate("Hello", "xx")
    assert "req" not in captured
