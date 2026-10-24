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

"""Appels d'outils ecrits en TEXTE par le modele (format natif DeepSeek).

Certains maillons rendent leur format d'appel natif dans `content` au lieu de
`tool_calls` (vecu 22/10 : `<｜｜DSML｜｜ invoke name="file_read">`). Sans
repli les outils ne tournent jamais et l'utilisateur voit le balisage dans le
chat. `tool_calls()` les rejoue comme de vrais appels ; `strip()` est
l'invariant d'affichage : aucun balisage ne doit atteindre l'ecran,
l'historique ni le tour suivant (un modele qui se relit en train d'en ecrire
continue d'en ecrire).
"""
import json
import re

_TAG = re.compile(r"<[^>]*DSML[^>]*>", re.I)
_INVOKE = re.compile(
    r"<(?!/)[^>]*DSML[^>]*\binvoke\b([^>]*)>(.*?)"
    r"</[^>]*DSML[^>]*\binvoke\s*>", re.S | re.I)
_PARAM = re.compile(
    r"<(?!/)[^>]*DSML[^>]*\bparameter\b([^>]*)>(.*?)"
    r"</[^>]*DSML[^>]*\bparameter\s*>", re.S | re.I)
_ATTR = re.compile(
    r"""([A-Za-z_]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")


def looks_like(text: str) -> bool:
    return "dsml" in (text or "").lower()


def _attrs(raw: str) -> dict:
    """Attributs d'une balise, guillemets doubles, simples ou absents."""
    return {m.group(1): next(g for g in m.groups()[1:] if g is not None)
            for m in _ATTR.finditer(raw or "")}


def tool_calls(text: str):
    """(texte affichable, appels au format OpenAI)."""
    text = text or ""
    if not looks_like(text):
        return text, []
    calls = []
    for number, match in enumerate(_INVOKE.finditer(text), 1):
        name = (_attrs(match.group(1)).get("name") or "").strip()
        if not name:
            continue
        arguments = {}
        for param in _PARAM.finditer(match.group(2)):
            pattrs = _attrs(param.group(1))
            key = (pattrs.get("name") or "").strip()
            if not key:
                continue
            value = param.group(2)
            if (pattrs.get("string") or "").lower() != "true":
                try:
                    value = json.loads(value)
                except (TypeError, ValueError):
                    pass
            arguments[key] = value
        calls.append({"id": f"dsml_{number}", "type": "function",
                      "function": {"name": name,
                                   "arguments": json.dumps(arguments)}})
    return strip(text), calls


def strip(text: str) -> str:
    """Texte sans balisage d'appel. Le bloc d'appels suit la prose : on coupe
    au premier marqueur, puis on retire les balises orphelines."""
    text = text or ""
    if not looks_like(text):
        return text
    first = _TAG.search(text)
    if first:
        text = text[:first.start()]
    return _TAG.sub("", text).strip()
