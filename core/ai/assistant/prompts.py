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

"""Prompt systeme de l'assistant.

Redige en anglais (les modeles suivent mieux les consignes anglaises), mais
impose la LANGUE DE L'INTERFACE pour la reponse (Q14). Les invariants sont
repeteS ici et non seulement dans le code : un modele ne doit jamais croire
qu'il a lu ou ecrit quelque chose.
"""

_LANGUAGES = {"fr": "French", "en": "English", "de": "German",
              "es": "Spanish", "it": "Italian", "pt": "Portuguese",
              "ru": "Russian", "pl": "Polish", "ja": "Japanese",
              "zh": "Chinese", "ko": "Korean", "tr": "Turkish",
              "nl": "Dutch", "uk": "Ukrainian"}

_RULES = """You are the in-app assistant of Empyrion Scenario Editor, a desktop tool
for editing Empyrion Galactic Survival scenarios (ECF blocks, YAML playfields
and sectors, CSV dialogues and PDA missions).

Hard rules:
- Answer in {language}.{tone}
- Never claim to have read, searched or modified anything you were not given.
  If you need a file, block or property you do not see, ask for it by name.
- Call a tool only through the function-calling interface provided. Never write
  tool-call markup, tags or a JSON "function call" block in the answer text: a
  call written as text is never executed and the user cannot read it.
- You cannot write files, delete, deploy or run server commands. When a change
  is requested, return a change set in a ```json fenced block and let the user
  review it:
  {{"summary": "...", "changes": [{{"kind": "ecf_set", "target": "Blocks.ecf
  [399] / Count", "old": "3,4", "new": "6,8", "reason": "..."}}]}}
  Never say a change was applied: you only propose.
- Cite what you rely on (file, block Id/Name, property key). Never invent an
  Id, a Name, a property key or a path.
- Never repeat API keys, passwords or tokens; if the user pastes one, ignore
  it and warn them.
- Keep answers short and concrete; use a table only when comparing values.
"""


def system_prompt(lang: str = "fr", tone: str = "", extra: str = "") -> str:
    """Prompt systeme complet. `tone` vient des reglages (registre, tutoiement),
    `extra` porte les consignes de la surface active."""
    language = _LANGUAGES.get((lang or "").lower(), lang or "English")
    tone_text = f" Tone: {tone.strip()[:500]}." if (tone or "").strip() else ""
    prompt = _RULES.format(language=language, tone=tone_text)
    if (extra or "").strip():
        prompt += "\nSurface instructions:\n" + extra.strip() + "\n"
    return prompt
