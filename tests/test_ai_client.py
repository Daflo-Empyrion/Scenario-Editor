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

"""Client OpenAI-compatible (core/ai/client.py) : tout le reseau est mocke."""
import json
import urllib.error

import pytest

from core.ai import client
from core.engine_errors import (AuthError, EngineUnavailableError,
                                QuotaExhaustedError)


def _fake_body(payload):
    class R:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode()

        def close(self):
            pass

    return R()


def _http_error(code, body, headers=None):
    return urllib.error.HTTPError(
        "url", code, "err", headers or {},
        _fake_body({"error": {"message": body}}))


def test_chat_payload_headers_and_usage(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=60):
        seen["data"] = json.loads(req.data)
        seen["headers"] = dict(req.header_items())
        return _fake_body({"choices": [{"message": {"content": "Bonjour"}}],
                           "usage": {"prompt_tokens": 10,
                                     "completion_tokens": 5, "cost": 0.004}})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    out = client.chat("https://api.example.test", "sk-test", "m1",
                      [{"role": "user", "content": "Hello"}],
                      tools=[{"type": "function"}], max_tokens=42)
    assert out["content"] == "Bonjour"
    assert out["usage"]["cost"] == 0.004
    assert seen["data"]["model"] == "m1"
    assert seen["data"]["max_tokens"] == 42
    assert seen["data"]["tools"]
    assert seen["headers"]["Authorization"] == "Bearer sk-test"
    assert any(k.lower() == "user-agent" for k in seen["headers"])
    assert client.usage_cost(out["usage"], 1.0, 1.0) == 0.004


def test_common_errors_are_typed(monkeypatch):
    cases = [
        (401, "bad key", AuthError, "refusee"),
        (402, "no credits", QuotaExhaustedError, "Credits"),
        (404, "model not found", EngineUnavailableError, "Modele"),
        (500, "boom", EngineUnavailableError, "Erreur API"),
    ]
    for code, body, exc_type, match in cases:
        monkeypatch.setattr(
            client.urllib.request, "urlopen",
            lambda req, timeout=60, c=code, b=body: (_ for _ in ()).throw(
                _http_error(c, b)))
        with pytest.raises(exc_type, match=match):
            client.chat("https://x.test", "k", "m", [])


def test_403_unavailable_model_is_fallback_not_auth(monkeypatch):
    """OpenRouter renvoie 403 pour un modele reserve a un autre type
    d'acces (agentic harness) : ce n'est PAS une cle refusee, le maillon
    suivant doit pouvoir servir (vecu 21/10, inkling:free)."""
    monkeypatch.setattr(
        client.urllib.request, "urlopen",
        lambda req, timeout=60: (_ for _ in ()).throw(_http_error(
            403, "thinkingmachines/inkling:free is only available on "
                 "agentic harnesses")))
    with pytest.raises(client.ModelUnavailableError, match="Modele"):
        client.chat("https://x.test", "k", "m", [])
    monkeypatch.setattr(
        client.urllib.request, "urlopen",
        lambda req, timeout=60: (_ for _ in ()).throw(
            _http_error(403, "invalid api key")))
    with pytest.raises(AuthError, match="refusee"):
        client.chat("https://x.test", "k", "m", [])


def test_429_carries_retry_after(monkeypatch):
    monkeypatch.setattr(
        client.urllib.request, "urlopen",
        lambda req, timeout=60: (_ for _ in ()).throw(
            _http_error(429, "rate limited", {"retry-after": "17"})))
    with pytest.raises(QuotaExhaustedError) as ei:
        client.chat("https://x.test", "k", "m", [])
    assert ei.value.retry_after == 17.0


def test_network_error(monkeypatch):
    monkeypatch.setattr(
        client.urllib.request, "urlopen",
        lambda req, timeout=60: (_ for _ in ()).throw(
            urllib.error.URLError("offline")))
    with pytest.raises(EngineUnavailableError, match="Reseau"):
        client.chat("https://x.test", "k", "m", [])


def test_list_models_and_key_info(monkeypatch):
    def fake_urlopen(req, timeout=30):
        if req.full_url.endswith("/models"):
            return _fake_body({"data": [{"id": "a"}, {"id": "b"}]})
        return _fake_body({"data": {"usage": 1.5, "limit_remaining": 8.5}})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    assert [m["id"] for m in client.list_models("https://x.test", "k")] == [
        "a", "b"]
    assert client.key_info("https://x.test", "k")["limit_remaining"] == 8.5


def test_usage_cost_estimates_without_cost_field():
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}
    assert client.usage_cost(usage, 0.25, 0.95) == pytest.approx(0.25 + 0.475)


def test_stream_chat_parses_sse(monkeypatch):
    lines = [
        b'data: {"choices":[{"delta":{"content":"Bon"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"jour"}}]}\n',
        b"data: [DONE]\n",
    ]

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            return iter(lines)

    monkeypatch.setattr(client.urllib.request, "urlopen",
                        lambda req, timeout=60: R())
    assert "".join(client.stream_chat("https://x.test", "k", "m", [])) == \
        "Bonjour"
