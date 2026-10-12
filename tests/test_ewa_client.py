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
"""Client EWA sans reseau : normalisation d'URL, lecture insensible a la
casse (piege System.Text.Json vs OData vs Newtonsoft), reponses HTTP
simulees (auth/erreurs/OData), config persistee, telnet (filtrage IAC,
echappement SAY) et plan de synchronisation miroir SFTP."""

import pytest

from core import settings


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    settings.set_ewa({})


# ------------------------------------------------------------------ config

def test_config_defaults_and_merge(tmp_path):
    from core.ewa import config as ewa_config
    cfg = ewa_config.load()
    assert cfg["verify_ssl"] is False
    assert cfg["sftp"]["port"] == 22
    assert cfg["telnet"]["port"] == 30004
    stored = dict(cfg)
    stored["sftp"] = {"port": 2257, "intrus": 1}
    ewa_config.save(stored)
    loaded = ewa_config.load()
    assert loaded["sftp"]["port"] == 2257
    assert "intrus" not in loaded["sftp"]
    assert loaded["sftp"]["host"] == ""


def test_config_password_never_persisted_without_consent():
    from core.ewa import config as ewa_config
    ewa_config.save({"url": "https://1.2.3.4:5001", "password": "secret",
                     "remember_password": False})
    assert settings.get_ewa()["password"] == ""
    ewa_config.save({"url": "https://1.2.3.4:5001", "password": "secret",
                     "remember_password": True})
    assert settings.get_ewa()["password"] == "secret"
    # relecture : sans consentement, le mot de passe ne revient pas
    assert ewa_config.load()["password"] == "secret"
    ewa_config.save({"remember_password": False, "password": "x"})
    assert ewa_config.load()["password"] == ""


# ------------------------------------------------------------------ client

def test_normalize_url():
    from core.ewa.client import normalize_url
    assert normalize_url("https://1.2.3.4:5001/") == "https://1.2.3.4:5001"
    assert normalize_url("1.2.3.4:5001") == "https://1.2.3.4:5001"
    assert normalize_url("http://localhost:5000") == "http://localhost:5000"
    assert normalize_url("  ") == ""


def test_pick_is_case_insensitive():
    from core.ewa.client import pick
    assert pick({"PlayerName": "Bob"}, "playername") == "Bob"
    assert pick({"playerName": "Bob"}, "PlayerName") == "Bob"
    assert pick({"x": 1}, "PlayerName", default="?") == "?"


class _Response:
    def __init__(self, payload=None, status_code=200, text="",
                 content=b"{}"):
        self._payload = payload
        self.status_code = status_code
        self.text = text
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("pas de json")
        return self._payload


def _client_with(monkeypatch, responder):
    """Mocke AU NIVEAU DE LA SESSION HTTP : _request (statuts, erreurs,
    en-tetes) reste le code reel sous test."""
    from core.ewa.client import EwaClient
    client = EwaClient("https://srv:5001", timeout=5)
    calls: list = []

    def _request(method, url, **kwargs):
        calls.append((method, url.replace(client.base_url + "/", "")))
        return responder(method, calls[-1][1], kwargs)

    monkeypatch.setattr(client._session, "request", _request)
    return client, calls


def test_authenticate_stores_token(monkeypatch):
    from core.ewa.client import EwaClient

    def responder(method, path, kwargs):
        assert path == "Users/authenticate"
        assert kwargs["json"] == {"Username": "bob", "Password": "pwd"}
        return _Response({"Id": 1, "Username": "bob", "Role": "ServerAdmin",
                          "Token": "jwt123"})

    client, _ = _client_with(monkeypatch, responder)
    user = client.authenticate("bob", "pwd")
    assert client.token == "jwt123"
    assert user["Username"] == "bob"


def test_authenticate_requires_fields(monkeypatch):
    from core.ewa.client import EwaAuthError, EwaClient
    client = EwaClient("https://srv:5001")
    with pytest.raises(EwaAuthError):
        client.authenticate("", "pwd")
    with pytest.raises(EwaAuthError):
        client.authenticate("bob", "")


def test_authenticate_rejected(monkeypatch):
    from core.ewa.client import EwaAuthError

    def responder(method, path, kwargs):
        return _Response(status_code=400,
                         payload={"message":
                                  "Username or password is incorrect"})

    client, _ = _client_with(monkeypatch, responder)
    with pytest.raises(EwaAuthError):
        client.authenticate("bob", "bad")


def test_http_error_maps_server_message(monkeypatch):
    from core.ewa.client import EwaError

    def responder(method, path, kwargs):
        return _Response(status_code=500, payload={"msg": "boom"})

    client, _ = _client_with(monkeypatch, responder)
    with pytest.raises(EwaError, match="boom"):
        client.get_systeminfo()


def test_odata_players_value_extraction(monkeypatch):
    players = [{"PlayerName": "Bob", "Online": True, "SteamId": "7654"}]

    def responder(method, path, kwargs):
        assert path.startswith("odata/Players")
        return _Response({"value": players})

    client, _ = _client_with(monkeypatch, responder)
    assert client.get_players() == players
    assert client.get_online_players() == players


def test_online_players_fallback_filters_locally(monkeypatch):
    all_players = [{"PlayerName": "A", "Online": True},
                   {"PlayerName": "B", "Online": False}]
    calls = {"n": 0}

    def responder(method, path, kwargs):
        calls["n"] += 1
        if "$filter" in path:
            return _Response(status_code=500, payload={"msg": "no filter"})
        return _Response({"value": all_players})

    client, _ = _client_with(monkeypatch, responder)
    online = client.get_online_players()
    assert len(online) == 1 and online[0]["PlayerName"] == "A"


def test_endpoint_paths(monkeypatch):
    paths: list = []

    def responder(method, path, kwargs):
        paths.append(path)
        return _Response(None, content=b"")

    client, _ = _client_with(monkeypatch, responder)
    client.kick_player("7654")
    client.ban_player("7654", "1d")
    client.unban_player("7654")
    client.set_player_credits(12, 3400)
    client.add_item_to_player(12, 1755, 10)
    client.egs_restart(5)
    client.backup_restore_player("b1", "7654")
    assert "Gameplay/KickPlayer/7654" in paths
    assert "Gameplay/BanPlayer/7654/1d" in paths
    assert "Gameplay/UnBanPlayer/7654" in paths
    assert "Gameplay/PlayerSetCredits/12/3400" in paths
    assert "Backpack/AddItem" in paths
    assert "Systeminfo/EGSRestart/5" in paths
    assert "Backup/RestorePlayer" in paths


def test_warp_and_delete_payloads(monkeypatch):
    bodies: dict = {}

    def responder(method, path, kwargs):
        bodies[path] = kwargs.get("json")
        return _Response(None, content=b"")

    client, _ = _client_with(monkeypatch, responder)
    client.warp_structure(42, "Akua", (1.5, 2.0, 3.0))
    client.delete_structures([{"id": 42, "playfield": "Akua"}])
    client.set_faction_of_structures("INV", [42, 43])
    assert bodies["Gameplay/WarpTo/42"]["Playfield"] == "Akua"
    assert bodies["Gameplay/WarpTo/42"]["PosY"] == 2.0
    assert bodies["Structure/DeleteStructures"] == [{"id": 42,
                                                     "playfield": "Akua"}]
    assert bodies["Structure/SetFactionOfStuctures"]["EntityIds"] == [42, 43]


def test_diagnose(monkeypatch):
    def responder(method, path, kwargs):
        if path == "Systeminfo/CurrentSysteminfo":
            return _Response({"serverName": "Serveur-MP"})
        if path == "Mod/ModLoaderInstalled":
            return _Response("True")
        return _Response(None, content=b"")

    client, _ = _client_with(monkeypatch, responder)
    result = client.diagnose()
    assert result["reachable"] is True
    assert result["server_name"] == "Serveur-MP"
    assert result["mod_loader"] is True


# ------------------------------------------------------------------ telnet

def test_telnet_strip_iac():
    from core.ewa.telnet import TelnetConsole
    assert TelnetConsole._strip_iac(b"abc") == b"abc"
    # sequences IAC completes : WILL/WONT/DO/DONT (0xFF + commande + option)
    assert TelnetConsole._strip_iac(b"a\xff\xfb\x01b") == b"ab"
    assert TelnetConsole._strip_iac(b"\xff\xfb\x01ok") == b"ok"


def test_say_command_escapes_apostrophes():
    from core.ewa.telnet import say_command
    assert "\\'" in say_command("l'item")
    assert say_command("salut").startswith("SAY '[c][ffffff]salut")


# ------------------------------------------------------------------- sftp

def _make_local(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def test_plan_sync_mirroring(tmp_path):
    from core.ewa.sftp_deploy import plan_sync
    local = tmp_path / "working"
    _make_local(local, {
        "a.yaml": b"NEW",
        "b.yaml": b"SAME",
        "c.yaml": b"ONLYLOCAL",
        "e.yaml": b"FRESH",
        "junk.bak": b"x",
        "e.yaml.bin": b"localbin",
    })
    b_stat = (local / "b.yaml").stat()
    remote = {
        "a.yaml": (3, 100),                  # different -> upload
        "b.yaml": (b_stat.st_size, int(b_stat.st_mtime)),  # -> unchanged
        "d.yaml": (9, 300),                  # distant seul -> delete
        "d.yaml.bin": (1, 1),                # bin d'un yaml present -> garde
        "e.yaml.bin": (1, 1),                # bin du yaml recopie -> invalide
        "f.yaml.bin": (1, 1),                # orphelin -> purge
    }
    plan = plan_sync(local, remote)
    assert plan["upload"] == ["a.yaml", "c.yaml", "e.yaml"]
    assert plan["delete"] == ["d.yaml"]
    assert plan["invalidate"] == ["e.yaml.bin"]
    assert plan["orphans"] == ["f.yaml.bin"]
    assert plan["unchanged"] == 1


def test_apply_sync_backups_before_delete(tmp_path, monkeypatch):
    from core.ewa.sftp_deploy import SftpSession, apply_sync

    remote_files = {"/srv/scen/d.yaml": b"OLD",
                    "/srv/scen/sub/x.yaml": b"KEEP"}
    monkeypatch.setattr(SftpSession, "__init__", lambda self: None)

    class _FakeSftp:
        def stat(self, path):
            raise IOError("pas de dossier distant dans le test")

        def mkdir(self, path):
            pass

        def put(self, local, remote):
            remote_files[remote] = b"NEW"

        def utime(self, remote, times):
            pass

        def getfo(self, remote, buffer):
            buffer.write(remote_files[remote])

        def remove(self, remote):
            remote_files.pop(remote, None)

    session = SftpSession()
    session._sftp = _FakeSftp()
    local = tmp_path / "working"
    _make_local(local, {"d.yaml": b"NEW"})
    backup_dir = tmp_path / "backups"

    done = apply_sync(session, local, "/srv/scen",
                      {"upload": ["d.yaml"], "delete": ["sub/x.yaml"],
                       "invalidate": [], "orphans": [], "unchanged": 0},
                      backup_dir, progress=None)
    assert done["uploaded"] == 1
    assert done["deleted"] == 1
    assert done["errors"] == []
    assert remote_files["/srv/scen/d.yaml"] == b"NEW"
    assert (backup_dir / "sub" / "x.yaml").read_bytes() == b"KEEP"
