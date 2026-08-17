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

import json
import urllib.error
import pytest

from core import update_checker


def test_parse_version_with_v_prefix():
    assert update_checker._parse_version("v1.2.3") == (1, 2, 3)


def test_parse_version_without_prefix():
    assert update_checker._parse_version("1.0.0") == (1, 0, 0)


def test_parse_version_garbage_falls_back():
    assert update_checker._parse_version("garbage") == (0,)


def test_check_for_update_returns_none_when_not_configured(monkeypatch):
    monkeypatch.setattr(update_checker, "GITHUB_REPO", "")
    assert update_checker.check_for_update() is None


def test_check_for_update_returns_none_on_network_error(monkeypatch):
    monkeypatch.setattr(update_checker, "GITHUB_REPO", "someone/somerepo")

    def fake_urlopen(*args, **kwargs):
        raise urllib.error.URLError("simulated network failure")

    monkeypatch.setattr(update_checker.urllib.request, "urlopen", fake_urlopen)
    assert update_checker.check_for_update() is None


def test_check_for_update_detects_newer_version(monkeypatch):
    monkeypatch.setattr(update_checker, "GITHUB_REPO", "someone/somerepo")
    monkeypatch.setattr(update_checker, "APP_VERSION", "1.0.0")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({
                "tag_name": "v1.5.0",
                "html_url": "https://github.com/someone/somerepo/releases/tag/v1.5.0",
            }).encode("utf-8")

    monkeypatch.setattr(update_checker.urllib.request, "urlopen", lambda *a, **k: FakeResponse())

    result = update_checker.check_for_update()
    assert result == {"version": "v1.5.0",
                       "url": "https://github.com/someone/somerepo/releases/tag/v1.5.0"}


def test_check_for_update_returns_none_when_already_current(monkeypatch):
    monkeypatch.setattr(update_checker, "GITHUB_REPO", "someone/somerepo")
    monkeypatch.setattr(update_checker, "APP_VERSION", "2.0.0")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"tag_name": "v2.0.0", "html_url": "https://x"}).encode("utf-8")

    monkeypatch.setattr(update_checker.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    assert update_checker.check_for_update() is None


def test_check_for_update_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setattr(update_checker, "GITHUB_REPO", "someone/somerepo")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"not valid json"

    monkeypatch.setattr(update_checker.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    assert update_checker.check_for_update() is None
