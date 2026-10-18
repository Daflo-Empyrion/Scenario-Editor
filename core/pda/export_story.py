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

"""Export de l'histoire d'un PDA en Markdown (demande Phase B) : chapitres,
taches et actions avec leurs textes CSV dans la colonne demandee — pour
relire/partager le recit d'un scenario hors de l'application. Lecture seule :
aucune mutation, aucun acces disque (l'appelant ecrit la chaine)."""


def _text(model, token: str, column: str) -> str:
    """Texte CSV du jeton, sinon le jeton brut (action sans localisation)."""
    if not token:
        return ""
    return model.csv_text(token, column) or token


def export_markdown(model, column: str = "Français") -> str:
    """Construit le Markdown de tout l'arbre PDA du modele donne."""
    lines = ["# PDA", ""]
    chapters = model.chapters()
    for ci, chapter in enumerate(chapters, 1):
        title = _text(model, model.chapter_title_token(chapter), column)
        lines.append(f"## {ci}. {title}")
        desc = _text(model, model.scalar(chapter, "Description"), column)
        if desc:
            lines.append("")
            lines.append(desc)
        for ti, task in enumerate(model.tasks(chapter), 1):
            # TaskTitle est la VALEUR de la ligne sequence ('- TaskTitle: pda_x'),
            # pas un enfant (meme convention que gui/pda/editor_dialog).
            t_title = _text(model, task.value or model.scalar(task, "TaskTitle"), column)
            lines.append("")
            lines.append(f"### {ci}.{ti} {t_title}")
            t_desc = _text(model, model.scalar(task, "Description"), column)
            if t_desc:
                lines.append("")
                lines.append(t_desc)
            for action in model.actions(task):
                check = model.action_check(action)
                a_title = _text(model, action.value or model.scalar(action, "ActionTitle"), column)
                lines.append("")
                label = f"- **{a_title}**" if a_title else "-"
                if check:
                    label += f" — `{check}`"
                lines.append(label)
                a_desc = _text(model, model.scalar(action, "Description"), column)
                if a_desc:
                    lines.append(f"  {a_desc}")
        if ci < len(chapters):
            lines.append("")
    lines.append("")
    return "\n".join(lines)
