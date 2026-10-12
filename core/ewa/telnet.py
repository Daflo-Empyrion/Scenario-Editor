# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it is useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Console TELNET du serveur dedie (port Tel_Port du serverconfig, ex
30005) -- socket BRUT : le dedié Empyrion n'implemente pas la negotiation
telnet (les octets IAC 0xFF.. sont ignores defensivement), le mot de passe
est demande a la connexion.

Toute la lecture vit dans un thread demon possede par l'objet ; le GUI ne
touche JAMAIS au socket directement (callbacks via signaux Qt cote appelant).
"""
import logging
import socket
import threading
import time

logger = logging.getLogger(__name__)


class TelnetError(Exception):
    pass


class TelnetConsole:
    """Console telnet Empyrion : connect(host, port, password) puis
    send_command() ; chaque ligne recue part dans on_line (thread telnet :
    l'appelant DOIT marshaler vers le GUI via un signal Qt)."""

    def __init__(self, on_line=None, on_closed=None):
        self._sock: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._reader: threading.Thread | None = None
        self._closing = False
        self.on_line = on_line          # callback(line: str)
        self.on_closed = on_closed      # callback() a la deconnexion

    # ------------------------------------------------------------- connexion

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self, host: str, port: int, password: str,
                auth_timeout: float = 8.0) -> None:
        if self._sock is not None:
            raise TelnetError("Déjà connecté.")
        if not host or not password:
            raise TelnetError("Hôte et mot de passe telnet requis.")
        try:
            self._sock = socket.create_connection((host, int(port)),
                                                  timeout=5.0)
        except OSError as e:
            self._sock = None
            raise TelnetError(f"Connexion impossible {host}:{port} : {e}") from e
        self._sock.settimeout(0.5)
        self._closing = False

        # Login : attendre l'invite "Password" puis l'acquitter. Certains
        # dedies envoient l'invite sans saut de ligne -> lecture par morceaux.
        buffer = b""
        deadline = time.monotonic() + auth_timeout
        while time.monotonic() < deadline:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                continue
            except OSError as e:
                self._teardown()
                raise TelnetError(f"Lecture interrompue : {e}") from e
            if not chunk:
                self._teardown()
                raise TelnetError("Connexion fermée avant le mot de passe.")
            buffer += self._strip_iac(chunk)
            if buffer.lower().rstrip(b"\r\n \x00").endswith(b"password:"):
                break
        else:
            self._teardown()
            raise TelnetError("Invite « Password » non reçue (port telnet ? "
                              "mot de passe déjà envoyé ?).")
        self._send_raw(password.encode("utf-8", "replace") + b"\r\n")
        time.sleep(0.3)
        # Vider l'eventuel refus ("Password incorrect" / fermeture) : le
        # thread lecteur signale la deconnexion le cas echeant.
        try:
            while True:
                chunk = self._sock.recv(4096)
                if not chunk:
                    self._teardown()
                    raise TelnetError("Refusé : mot de passe telnet faux.")
                text = self._strip_iac(chunk).decode("utf-8", "replace")
                lowered = text.lower()
                if "incorrect" in lowered or "failed" in lowered \
                        or "denied" in lowered:
                    self._teardown()
                    raise TelnetError(text.strip() or "Mot de passe refusé.")
                self._emit(text)
                break
        except socket.timeout:
            pass
        self._reader = threading.Thread(target=self._read_loop, daemon=True,
                                        name="ewa-telnet-reader")
        self._reader.start()
        self._emit(f"--- connecté {host}:{port}\n")

    def close(self) -> None:
        self._closing = True
        self._teardown()

    # ---------------------------------------------------------------- usage

    def send_command(self, command: str) -> None:
        """Envoie une commande console (SAY, bans, saves...). Thread GUI OK :
        l'envoi est protege par un verrou et n'attend aucune reponse."""
        if self._sock is None:
            raise TelnetError("Console déconnectée.")
        data = command.rstrip("\r\n").encode("utf-8", "replace") + b"\r\n"
        with self._send_lock:
            try:
                self._sock.sendall(data)
            except OSError as e:
                raise TelnetError(f"Envoi impossible : {e}") from e

    # --------------------------------------------------------------- interne

    def _send_raw(self, data: bytes) -> None:
        with self._send_lock:
            assert self._sock is not None
            self._sock.sendall(data)

    def _read_loop(self) -> None:
        sock = self._sock
        while sock is not None and not self._closing:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            text = self._strip_iac(chunk).decode("utf-8", "replace")
            self._emit(text)
        self._teardown()
        self._emit("--- déconnecté\n")
        if self.on_closed is not None and not self._closing:
            try:
                self.on_closed()
            except Exception:               # noqa: BLE001 - callback GUI
                logger.exception("callback on_closed telnet")

    def _emit(self, text: str) -> None:
        if self.on_line is None or not text:
            return
        try:
            self.on_line(text)
        except Exception:                   # noqa: BLE001 - callback GUI
            logger.exception("callback on_line telnet")

    def _teardown(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    @staticmethod
    def _strip_iac(data: bytes) -> bytes:
        """Retire les sequences de negotiation telnet (0xFF + 2 octets) --
        le dedié Empyrion ne negocie pas, filtre defensif seulement."""
        if 0xFF not in data:
            return data
        out = bytearray()
        index = 0
        while index < len(data):
            if data[index] == 0xFF:
                index += 3                  # IAC + commande + option
                continue
            out.append(data[index])
            index += 1
        return bytes(out)


def say_command(message: str) -> str:
    """Commande console equivalent au chat serveur d'EWA (ChatManager :
    SAY '[c][ffffff]...' avec echappement des apostrophes)."""
    escaped = message.replace("'", "\\'")
    return f"SAY '[c][ffffff]{escaped}[/c]'"
