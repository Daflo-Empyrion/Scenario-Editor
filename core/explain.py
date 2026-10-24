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

"""
Contexte de l'entree « Expliquer avec IA » (ECF, YAML, CSV) : rassemble les
FAITS verifiables autour d'une valeur -- glossaire du fichier, valeur vanille,
valeurs observees dans le document (mediane numerique / valeur la plus
frequente) -- puis construit les messages envoyes au moteur IA deja configure
(core.ai.router, jamais un LLM local : voir gui/explain_dialog.py).

Rien n'est invente ici : quand un fait manque (pas de glossaire, pas de
fichier vanille, colonne non numerique), il est simplement omis. Les
suggestions suivent la regle demandee le 24/10/2026 : valeur vanille, puis
mediane de la famille observee.
"""
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from core.i18n import t

# Plafonds : une explication ne doit jamais relire un fichier entier pour
# rien (PDA.yaml fait plusieurs Mo) -- le resume reste representatif.
_MAX_OBSERVED = 2000


@dataclass
class ExplainContext:
    title: str                      # "BlocksConfig.ecf — GeneratorLarge / EnergyOut"
    subject: str                    # cle, colonne ou chemin
    current: Optional[str] = None   # valeur affichee par l'editeur
    glossary: Optional[str] = None  # explication verifiee du glossaire
    vanilla: Optional[str] = None   # meme cle dans le fichier vanille
    observed: Optional[str] = None  # resume statistique des valeurs du document
    facts: List[str] = field(default_factory=list)  # autres faits (contexte)
    suggestions: List[str] = field(default_factory=list)

    def context_lines(self) -> List[str]:
        lines = []
        if self.glossary:
            lines.append(f"{t('explain.f_glossary')} : {self.glossary}")
        if self.current is not None:
            lines.append(f"{t('explain.f_current')} : {self.current}")
        if self.vanilla is not None:
            lines.append(f"{t('explain.f_vanilla')} : {self.vanilla}")
        if self.observed:
            lines.append(f"{t('explain.f_observed')} : {self.observed}")
        lines.extend(self.facts)
        lines.extend(f"{t('explain.f_suggestion')} : {s}" for s in self.suggestions)
        return lines

    def messages(self, language: str) -> list:
        """Messages prets pour core.ai.router.chat_with_link."""
        if language == "en":
            system = (
                "You explain Empyrion - Galactic Survival scenario files (ECF, "
                "YAML, CSV) to a scenario designer. Use only the facts provided; "
                "never invent a field meaning. Answer in English, concisely, with "
                "three short sections: what the field does, possible values, and "
                "the recommended value (justify it from the facts).")
            head = "Field to explain"
        else:
            system = (
                "Tu expliques les fichiers de scenario d'Empyrion - Galactic "
                "Survival (ECF, YAML, CSV) a un concepteur de scenario. Utilise "
                "UNIQUEMENT les faits fournis ; n'invente jamais le sens d'un "
                "champ. Reponds en francais, de facon concise, en trois courtes "
                "sections : role du champ, valeurs possibles, valeur recommandee "
                "(justifiee par les faits).")
            head = "Champ a expliquer"
        body = [f"{head} : {self.title}"]
        body.extend(self.context_lines())
        return [{"role": "system", "content": system},
                {"role": "user", "content": "\n".join(body)}]


def _fmt(n: float) -> str:
    """Nombre lisible : jamais de notation scientifique (2e+07 illisible)."""
    return f"{n:g}" if abs(n) < 100_000 else f"{n:,.0f}"


def _summary(values) -> Optional[str]:
    """Resume des valeurs observees : mediane si le champ est numerique,
    sinon valeur la plus frequente. None sans valeur exploitable."""
    vals = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not vals:
        return None
    nums = []
    for v in vals:
        try:
            nums.append(float(v.strip('"').split(",")[0]))
        except ValueError:
            continue
    if len(nums) >= 3 and len(nums) >= len(vals) * 0.8:
        med = statistics.median(nums)
        return t("explain.observed_numeric", count=len(nums), median=_fmt(med),
                 mini=_fmt(min(nums)), maxi=_fmt(max(nums)))
    top, count = Counter(vals).most_common(1)[0]
    return t("explain.observed_common", count=len(vals), value=top, hits=count)


def _suggestions(vanilla: Optional[str], values) -> List[str]:
    """Valeurs recommandees : vanille d'abord, puis tendance de la famille."""
    out = []
    if vanilla not in (None, ""):
        out.append(t("explain.suggest_vanilla", value=vanilla))
    vals = [str(v).strip() for v in values if v is not None and str(v).strip()]
    nums = []
    for v in vals:
        try:
            nums.append(float(v.strip('"').split(",")[0]))
        except ValueError:
            continue
    if len(nums) >= 3:
        out.append(t("explain.suggest_median", value=_fmt(statistics.median(nums))))
    elif vals:
        top = Counter(vals).most_common(1)[0][0]
        out.append(t("explain.suggest_common", value=top))
    return out


def _block_name(block) -> str:
    """Name d'un bloc, qu'il soit sur la ligne d'ouverture ou dans le corps
    (format reel : '{ +Block' puis 'Id: 5, Name: X' a la ligne suivante)."""
    if block is None:
        return ""
    return (block.get('Name') or block.get_property('Name') or "").strip()


def _vanilla_value(file_name: str, block_name: str, key: str) -> Optional[str]:
    """Valeur de la meme propriete dans le fichier vanille du jeu, si
    l'installation est renseignee (Options). Cache par appel : une seule
    lecture de fichier par explication."""
    from core.market_balance import config_dir
    from core.settings import get_vanilla_content_path
    root = get_vanilla_content_path()
    if not root:
        return None
    conf = config_dir(root)
    if conf is None:
        return None
    path = conf / file_name
    if not path.is_file():
        return None
    from core.ecf.parser import parse_ecf_file
    try:
        doc = parse_ecf_file(path)
    except Exception:
        return None
    target = block_name.strip().lower()
    for block in doc.iter_blocks():
        name = _block_name(block)
        if name.lower() == target:
            return block.get_property(key)
    return None


def _ecf_values(doc, key: str, limit: int = _MAX_OBSERVED) -> List[str]:
    """Valeurs de la propriete `key` dans TOUT le document (famille observee)."""
    out = []
    for block in doc.iter_blocks():
        raw = block.get_property(key)
        if raw is not None:
            out.append(raw)
            if len(out) >= limit:
                break
    return out


def ecf_property_context(doc, block, key: str, value: Optional[str],
                         file_name: str) -> ExplainContext:
    """Contexte d'une propriete ECF (cellule du tableau ou cle de l'arbre)."""
    from core.ecf_header_glossary import find_term_explanation
    block_name = _block_name(block)
    observed_values = _ecf_values(doc, key)
    vanilla = _vanilla_value(file_name, block_name, key) if block_name else None
    current = value if value is not None else (
        block.get_property(key) if block is not None else None)
    facts = []
    if block_name:
        facts.append(f"{t('explain.f_block')} : {block_name}")
    return ExplainContext(
        title=f"{file_name} — {block_name} / {key}" if block_name
        else f"{file_name} — {key}",
        subject=key,
        current=current,
        glossary=find_term_explanation(file_name, key),
        vanilla=vanilla,
        observed=_summary(observed_values),
        facts=facts,
        suggestions=_suggestions(vanilla, observed_values),
    )


def ecf_block_context(doc, block, file_name: str) -> ExplainContext:
    """Contexte d'un BLOC entier (clic droit dans l'arbre ECF) : ses
    proprietes d'en-tete servent de faits."""
    block_name = _block_name(block)
    from core.ecf.model import EcfProperty
    facts = []
    if block.kind:
        facts.append(f"{t('explain.f_kind')} : {block.kind}")
    if block.pairs:
        facts.append(f"{t('explain.f_properties')} : "
                     + ", ".join(f"{k}={v}" for k, v in block.pairs[:15]))
    props = [c for c in block.children if isinstance(c, EcfProperty)][:15]
    if props:
        facts.append(f"{t('explain.f_body')} : "
                     + ", ".join(f"{k}={v}" for p in props
                                 for k, v in p.pairs if k))
    return ExplainContext(
        title=f"{file_name} — {block_name or block.kind or ''}".strip(" —"),
        subject=block_name or block.kind or "",
        current=None,
        glossary=None,
        vanilla=None,
        observed=None,
        facts=facts,
        suggestions=[],
    )


def yaml_context(doc, key: str, value: Optional[str], path: str,
                 file_name: str) -> ExplainContext:
    """Contexte d'une entree YAML : tendance des valeurs de la meme cle dans
    le document (pas de vanille : les chemins different d'un scenario a
    l'autre)."""
    values = []
    for entry in doc.iter_entries():
        if entry.key == key and entry.value:
            values.append(entry.value)
            if len(values) >= _MAX_OBSERVED:
                break
    return ExplainContext(
        title=f"{file_name} — {path}" if path else f"{file_name} — {key}",
        subject=key,
        current=value,
        observed=_summary(values),
        suggestions=_suggestions(None, values),
    )


def csv_context(header: List[str], rows: List[List[str]], row_index: int,
                col_index: int, file_name: str) -> ExplainContext:
    """Contexte d'une cellule CSV : la colonne entiere comme famille."""
    if not header or not (0 <= col_index < len(header)):
        return ExplainContext(title=file_name, subject="")
    column = header[col_index]
    values = [r[col_index] for r in rows
              if col_index < len(r) and r[col_index].strip()][:_MAX_OBSERVED]
    current = None
    if 0 <= row_index < len(rows) and col_index < len(rows[row_index]):
        current = rows[row_index][col_index]
    facts = []
    if 0 <= row_index < len(rows) and rows[row_index]:
        facts.append(f"{t('explain.f_row')} : {header[0]} = {rows[row_index][0]}")
    from core.csv_column_glossary import get_csv_column_tooltip
    glossary = get_csv_column_tooltip(column)
    if glossary:
        # Le glossaire CSV est en HTML (infobulle) : texte brut suffisant ici.
        import re
        glossary = re.sub(r"<[^>]+>", " ", glossary).strip()
    return ExplainContext(
        title=f"{file_name} — {column}",
        subject=column,
        current=current,
        glossary=glossary or None,
        observed=_summary(values),
        facts=facts,
        suggestions=_suggestions(None, values),
    )
