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

"""Controle et reparation des balises BBCode des CSV traduits.

Les textes Empyrion melangent plusieurs familles de balises :
  - paires classiques  [b]..[/b], [i], [u], [c]..[/c], [sup], ...
  - couleurs           [0AC9F9]..[-]   (6 ou 8 chiffres hexadecimaux)
  - jetons techniques  '\\n' litteral, {0}, %s, <DISCOUNTTEXT>

Une traduction peut perdre une fermeture, en ajouter une, casser
l'imbrication ou introduire un code couleur invalide : le jeu affiche alors
le texte brut ou perd la mise en forme.

Controle AUTONOME (02/11/2026) : plus aucune comparaison avec la colonne
anglaise — chaque colonne selectionnee est controlee seule (la tolerance
aux defauts herites de la source causait plus de problemes que de gains,
retour utilisateur du 01/11).

Choix de reparation :
  - une balise en TROP mais bien formee n'est JAMAIS supprimee : une
    traduction qui ajoute une couleur coherente a le droit de le faire ;
  - une fermeture orpheline ou une balise invalide est RETIREE ;
  - une fermeture manquante est TOUJOURS ajoutee, meme si la source laisse
    la balise ouverte ; un '[c]' rouvert avant la fermeture du precedent
    ferme d'abord le bloc precedent (deux blocs propres plutot qu'un
    empilement) ;
  - une couleur est un ETAT : un nouveau code remplace le precedent et un
    '[-]' remet a zero, ce n'est pas une imbrication ;
  - orphelines, balises invalides et imbrications ne sont corrigees que si
    la source ne presente pas deja le meme defaut.
Adaptation du correcteur externe du 04/11 (C:/Users/David/Desktop, moins de
faux negatifs que la version precedente) :
  - un code couleur hexa SANS bloc [c] n'est pas applique par le jeu :
    le bloc [c] est ajoute ;
  - une fermeture manquante est inseree AVANT le premier '\\n' litteral
    (fermee en toute fin, le jeu teintait la ligne suivante) ;
  - tout [/c] fermant un bloc qui contient une couleur est precede de [-]
    (convention du jeu : [c][hex]...[-][/c]) ;
  - espaces recolles : '[-] [/c]' -> '[-][/c]', '[/c] \\n' -> '[/c]\\n'.
Le RichText Unity (<b>, <i>, <color=#hex>...) est repare par
repair_richtext : imbrication stricte LIFO, fermeture avant les jetons
systeme ('\\n', @wN, @pN), fermeture orpheline retiree, tags ouverts
fermes en fin de texte. Les macros <UPPERCASE> (<DISCOUNTTEXT>...) et les
balises auto-fermantes sont laissees intactes (le correcteur externe les
corrompait en </discounttext>).
Les jetons techniques absents ({0}, \n...) restent signales sans
proposition : une machine ne devine pas ou le texte a ete coupe.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from core.translation import LANGUAGE_ALIASES, repair_mojibake

# Balises nommees reconnues (Empyrion + BBCode standard). Une balise hors de
# cette liste est jugee invalide : c'est ce qui attrape [ZZZZZZ] ou [couleur].
KNOWN_TAGS = frozenset(
    "b c i u s sup sub center left right justify color size font url img "
    "quote list table tr td hr br p".split()
)

_TAG_RE = re.compile(r"\[(/?)(-|[A-Za-z0-9#][A-Za-z0-9_#-]*)(=[^\]]*)?\]")
_HEX_RE = re.compile(r"^(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
# tag avec espaces interieurs ('[/c ]', '[- ]', '[ c]') : vecu dans RE2-FR
# (28 [/c ] et 2 [- ] au 04/11). '[ P ]' (touche clavier) reste intact :
# 'P' n'est pas un nom de balise connue.
_SPACED_TAG_RE = re.compile(
    r"\[\s*(/?)(-|[A-Za-z0-9#][A-Za-z0-9_#-]*)\s*(=[^\]]*)?\]")


def _normalize_spaced_tags(text: str) -> str:
    """Recolle les espaces interieurs des balises reconnues ([/c ] -> [/c])."""
    def _fix(m: re.Match) -> str:
        slash, name, arg = m.groups()
        if name == "-" or _HEX_RE.match(name) or name.lower() in KNOWN_TAGS:
            return f"[{slash}{name}{arg or ''}]"
        return m.group(0)                  # [ P ] : pas une balise, intact
    return _SPACED_TAG_RE.sub(_fix, text)

_NEWLINE = "\\n"                      # deux caracteres, pas un vrai saut
_PLACEHOLDER_RE = re.compile(r"\{[A-Za-z0-9_]+\}")
_PERCENT_RE = re.compile(r"%[sd]")
_MACRO_RE = re.compile(r"<[A-Z][A-Z0-9_]*>")


@dataclass(frozen=True)
class Token:
    text: str      # texte exact de la balise
    kind: str      # open | close | color | reset | invalid
    name: str      # nom en minuscules ('c', 'ff4500' pour une couleur)
    norm: str      # forme comparable : '[c]', '[/c]', '[color]', '[-]'


def _token_from_match(m: re.Match) -> Token:
    slash, name, _arg = m.group(1), m.group(2), m.group(3)
    low = name.lower()
    if name == "-" and not slash:
        return Token(m.group(0), "reset", "-", "[-]")
    if slash:
        return Token(m.group(0), "close", low, f"[/{low}]")
    if _HEX_RE.match(name):
        return Token(m.group(0), "color", low, "[color]")
    if low in KNOWN_TAGS:
        return Token(m.group(0), "open", low, f"[{low}]")
    return Token(m.group(0), "invalid", low, f"[{low}]")


def tokenize(text: str) -> list[Token]:
    """Decoupe une chaine en balises, dans l'ordre. Le texte hors balise est ignore.
    '[ R ]' (touche clavier, espaces internes) n'est PAS une balise : le motif
    exige un premier caractere alphanumerique juste apres le crochet."""
    return [_token_from_match(m) for m in _TAG_RE.finditer(text or "")]


def _closer(tok: Token) -> str:
    return "[-]" if tok.kind == "color" else f"[/{tok.name}]"


def structure(text: str) -> tuple[Counter, Counter]:
    """(multiplicite des balises, anomalie -> nombre).

    Une anomalie est decrite par 'genre:nom' ('unclosed:c', 'orphan:-',
    'nesting:b', 'invalid:zzzzzz'). Les fermetures correctes ferment la
    derniere ouverture de meme nom ; une fermeture qui traverse des
    ouvertures encore actives est une erreur d'imbrication et resynchronise
    la pile pour ne pas cascader en fausses orphelines."""
    tags: Counter = Counter()
    problems: Counter = Counter()
    stack: list[Token] = []
    for tok in tokenize(text):
        tags[tok.norm] += 1
        if tok.kind == "invalid":
            problems[f"invalid:{tok.name}"] += 1
        elif tok.kind == "color":
            # une couleur est un ETAT global : le nouveau code remplace le
            # precedent, meme s'il a ete pose dans un autre bloc [c]
            stack[:] = [t for t in stack if t.kind != "color"]
            stack.append(tok)
        elif tok.kind == "open":
            stack.append(tok)
        elif tok.kind == "reset":
            if any(t.kind == "color" for t in stack):
                stack[:] = [t for t in stack if t.kind != "color"]
            else:
                problems["orphan:-"] += 1
        else:  # close
            if stack and stack[-1].name == tok.name:
                stack.pop()
            elif any(t.name == tok.name for t in stack):
                problems[f"nesting:{tok.name}"] += 1
                while stack and stack[-1].name != tok.name:
                    stack.pop()
                stack.pop()
            else:
                problems[f"orphan:{tok.name}"] += 1
    for tok in stack:
        problems[f"unclosed:{tok.name}"] += 1
    return tags, problems


def repair_text(target: str) -> str:
    """Reecrit `target` en corrigeant ses balises BBCode, SANS toucher au
    choix de traduction. Controle AUTONOME (02/11/2026) : plus aucune
    comparaison a la source anglaise — ses regles de tolerance causaient
    plus de problemes (defauts herites non repares) que de gains.

      - un code couleur hexa sans bloc [c] recoit son [c] (le jeu n'applique
        pas la couleur sinon) ;
      - une fermeture manquante est TOUJOURS ajoutee, AVANT le premier
        '\\n' litteral s'il y en a un apres le bloc ouvert : un '[c]' orphelin
        peut teinter toute la suite du texte en jeu (31/10/2026) ;
      - une fermeture ORPHELINE ([-] ou [/b] sans ouverture) est retiree ;
      - une balise INVALIDE est retiree ;
      - un '[c]' (ou une couleur) rouvert alors que le precedent n'est pas
        ferme ferme d'abord le bloc precedent : on ressort
        '[c][green]A[-][/c][c][white]B[-][/c]' au lieu d'empiler deux
        ouvertures pour une seule fermeture ;
      - tout [/c] fermant un bloc colore est precede de [-] ;
      - une balise bien formee n'est JAMAIS retiree.
    Retourne `target` inchange si rien a faire."""
    # Tags espaces ('[/c ]', '[- ]') : recolles d'abord, sinon invisibles.
    target = _normalize_spaced_tags(target)
    # Code couleur hexa ou [/c] orphelin sans bloc [c] : le jeu ignore la
    # couleur (et la fermeture est orpheline), on ouvre le bloc.
    if re.search(r"\[c\]", target, re.IGNORECASE) is None \
            and (any(tok.kind == "color" for tok in tokenize(target))
                 or re.search(r"\[/c\]", target, re.IGNORECASE) is not None):
        target = "[c]" + target
    # Un '[c]' final isole est une coquille pour '[/c]' (vecu RE2-FR L600 :
    # '...Schutzanzug[-][c]') : retourne le bloc au lieu d'empiler une
    # ouverture vide.
    m_end = re.search(r"\[c\]\s*$", target, re.IGNORECASE)
    if m_end is not None \
            and len(re.findall(r"\[c\]", target, re.IGNORECASE)) \
            > len(re.findall(r"\[/c\]", target, re.IGNORECASE)):
        target = target[:m_end.start()] + "[/c]" + target[m_end.end():]

    tgt_tags, _ = structure(target)
    # un bloc '[c]' laisse ouvert quelque part : on separera les blocs
    split_c = tgt_tags["[c]"] > tgt_tags["[/c]"]

    out: list[str] = []
    stack: list[Token] = []
    pending: Counter = Counter()          # fermetures emises d'office (imbrication)
    color_open = False                    # couleur posee, pas encore remise
    pos = 0

    def _emit_close(tok: Token) -> None:
        """Emet la fermeture d'un token sorti de la pile, avec le [-]
        obligatoire devant [/c] si le bloc contient une couleur."""
        nonlocal color_open
        if tok.name == "c" and color_open:
            out.append("[-]")
            color_open = False
        out.append(_closer(tok))
        if tok.kind == "color":
            color_open = False

    for m in _TAG_RE.finditer(target):
        out.append(target[pos:m.start()])   # le texte entre les balises est conserve
        pos = m.end()
        tok = _token_from_match(m)
        if tok.kind == "invalid":
            continue                        # balise invalide : retiree
        if tok.kind in ("open", "color"):
            if tok.kind == "open" and tok.name == "c" and split_c:
                idx = next((i for i in range(len(stack) - 1, -1, -1)
                            if stack[i].name == "c"), None)
                if idx is not None:               # bloc couleur precedent non ferme
                    while len(stack) > idx:
                        _emit_close(stack.pop())
            elif tok.kind == "color":
                stack[:] = [t for t in stack if t.kind != "color"]
            if tok.kind == "color":
                color_open = True
            out.append(tok.text)
            stack.append(tok)
            continue
        if tok.kind == "reset":
            if any(t.kind == "color" for t in stack):
                stack[:] = [t for t in stack if t.kind != "color"]
                out.append(tok.text)
                color_open = False
            continue                          # '[-]' orphelin : retire
        # close
        if pending.get(tok.norm, 0) > 0:
            pending[tok.norm] -= 1
            continue                       # fermeture deja emise par la reparation
        idx = next((i for i in range(len(stack) - 1, -1, -1)
                    if stack[i].name == tok.name), None)
        if idx is None:
            continue                       # fermeture orpheline : retiree
        if idx != len(stack) - 1:
            while len(stack) - 1 > idx:    # imbrication : fermer d'abord
                _emit_close(stack.pop())
                pending[out[-1]] += 1
        stack.pop()
        if tok.name == "c" and color_open:
            out.append("[-]")
            color_open = False
        out.append(tok.text)

    tail = target[pos:]
    if stack:
        missing = list(reversed(stack))    # fermetures manquantes : toujours
        idx = tail.find(_NEWLINE)
        if idx > 0 and tail[idx - 1] == "[":
            idx -= 1                       # inserer avant le token [\n] entier
        if idx >= 0:
            # fermer le bloc AVANT le saut de ligne : au-dela, le jeu
            # prolonge la couleur sur les lignes suivantes (04/11)
            out.append(tail[:idx])
            for t in missing:
                _emit_close(t)
            out.append(tail[idx:])
        else:
            out.append(tail)
            for t in missing:
                _emit_close(t)
    else:
        out.append(tail)

    fixed = "".join(out)
    # cosmetique (04/11) : espaces accidentels recolles
    fixed = re.sub(r"\[-\]\s+\[/c\]", "[-][/c]", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\[/c\]\s+(" + re.escape(_NEWLINE) + r")",
                   r"[/c]\1", fixed, flags=re.IGNORECASE)
    return fixed


_RICH_SPLIT_RE = re.compile(
    r"(</?[A-Za-z][^>]*>|<#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?>)")
_RICH_NAME_RE = re.compile(r"^</?([A-Za-z][A-Za-z0-9]*)")
# Empyrion admet <#ffff00> comme raccourci de <color=#ffff00> (vecu RE2-FR :
# 172 occurrences) ; la fermeture reste </color>.
_RICH_SHORT_HEX_RE = re.compile(r"^<#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?>$")
_SYSTEM_TOKEN_RE = re.compile(r"(\[\\n\]|\\n|@w\d+|@p\d+)")  # jetons du jeu
# liste blanche RichText Unity : tout ce qui n'y est pas (macros
# <DISCOUNTTEXT>, comparaisons texte « a < b »...) est laisse intact
_RICH_TAGS = frozenset(
    "b i u s color size font link mark sub sup nobr align pos br".split())


def repair_richtext(target: str) -> str:
    """Repare le RichText Unity (<b>, <i>, <color=#hex>...) : imbrication
    stricte LIFO, fermeture avant les jetons systeme ('\\n', @wN, @pN),
    fermeture orpheline retiree, tags ouverts fermes en fin de texte.
    Hors liste blanche : intact. Retourne `target` inchange si rien a faire."""
    if not target:
        return target
    out: list[str] = []
    stack: list[tuple[str, str]] = []     # (nom, token d'ouverture normalise)
    for token in _RICH_SPLIT_RE.split(target):
        if not token:
            continue
        if _RICH_SHORT_HEX_RE.match(token):
            out.append(token)              # <#hex> : ouvert, ferme par </color>
            stack.append(("color", token))
            continue
        m = _RICH_NAME_RE.match(token)
        if m is None or m.group(1).lower() not in _RICH_TAGS:
            # texte brut, macro ou balise inconnue : fermer quand meme les
            # tags ouverts avant un jeton systeme ('\n' coupe la mise en forme)
            for part in _SYSTEM_TOKEN_RE.split(token):
                if part and _SYSTEM_TOKEN_RE.fullmatch(part):
                    while stack:
                        out.append(f"</{stack.pop()[0]}>")
                    out.append(part)
                elif part:
                    out.append(part)
            continue
        low = m.group(1).lower()
        norm = token.replace(m.group(1), low, 1)     # nom en minuscules
        if token.startswith("</"):
            if stack and stack[-1][0] == low:
                stack.pop()
                out.append(norm)
            elif any(n == low for n, _o in stack):
                # imbrication croisee : fermer en LIFO, puis rouvrir
                closed: list[tuple[str, str]] = []
                while stack and stack[-1][0] != low:
                    n, open_tok = stack.pop()
                    out.append(f"</{n}>")
                    closed.append((n, open_tok))
                if stack:
                    stack.pop()
                    out.append(norm)
                for n, open_tok in reversed(closed):
                    stack.append((n, open_tok))
                    out.append(open_tok)
            # fermeture orpheline : retiree
        elif token.endswith("/>"):
            out.append(token)              # auto-fermante : pas de pile
        else:
            out.append(norm)
            stack.append((low, norm))
    while stack:
        out.append(f"</{stack.pop()[0]}>")
    # les reouvertures apres imbrication croisee peuvent laisser une paire
    # vide (<i></i>) si le texte s'arretait la : elle ne rend rien, on l'ote
    return re.sub(r"<([A-Za-z][A-Za-z0-9]*)(?:=[^>]*)?></\1>", "",
                  "".join(out))


@dataclass
class CellReport:
    """Anomalies d'UNE cellule et correction proposee (vide si aucune)."""
    kinds: list[str]        # 'unclosed', 'orphan', 'nesting', 'invalid'
    details: str            # balises / jetons concernes, pour l'affichage
    before: str
    after: str = ""         # texte repare, '' si pas de proposition

    @property
    def repairable(self) -> bool:
        return bool(self.after) and self.after != self.before


def _tag_label(name: str) -> str:
    if name == "-":
        return "[-]"
    if _HEX_RE.match(name):
        return "[color]"
    return f"[{name}]"


def _tag_names(counter: Counter) -> str:
    """Balises d'un compteur de multiplicités (cles normalisees '[c]')."""
    return ", ".join(dict.fromkeys(counter))


def _problem_names(counter: Counter) -> str:
    """Balises d'un compteur d'anomalies (cles 'genre:nom')."""
    return ", ".join(dict.fromkeys(
        _tag_label(key.split(":", 1)[1]) for key in sorted(counter)))


def check_cell(target: str) -> CellReport | None:
    """Controle AUTONOME des balises d'une cellule (02/11/2026, plus aucune
    comparaison a la source anglaise). Retourne None si rien a signaler :
    cellule vide, ou balises deja equilibrees (BBCode ET RichText Unity)."""
    if not (target or "").strip():
        return None
    _tags, problems = structure(target)
    kinds: list[str] = []
    if any(k.startswith("unclosed:") for k in problems):
        kinds.append("unclosed")
    if any(k.startswith("orphan:") for k in problems):
        kinds.append("orphan")
    if any(k.startswith("nesting:") for k in problems):
        kinds.append("nesting")
    if any(k.startswith("invalid:") for k in problems):
        kinds.append("invalid")

    fixed = repair_text(target)
    rich = repair_richtext(fixed)
    if rich != fixed:
        kinds.append("richtext")
    if not kinds:
        return None

    details = _problem_names(Counter({k: 1 for k in problems}))
    after = rich if rich != target else ""
    return CellReport(kinds, details, target, after)


def _norm(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return value.strip().upper()


_LANG_ALIASES = frozenset(_norm(a) for forms in LANGUAGE_ALIASES.values() for a in forms)
_EN_ALIASES = frozenset(_norm(a) for a in LANGUAGE_ALIASES["en"])


def language_columns(header: list[str]) -> list[int]:
    """Colonnes de langue de l'en-tete. Si aucune n'est reconnue (en-tete
    exotique), repli sur « tout sauf la premiere colonne », qui reste la cle
    technique dans tous les CSV de ce projet (core/csv_column_glossary.py)."""
    cols = [i for i, name in enumerate(header)
            if _norm(repair_mojibake((name or "").strip())) in _LANG_ALIASES]
    return cols or list(range(1, len(header)))


def source_column(header: list[str], columns: list[int]) -> int:
    """Colonne de reference : l'anglais si present, sinon la premiere colonne
    de langue. Dans les deux cas la comparaison reste ligne a ligne."""
    for i in columns:
        if _norm(repair_mojibake((header[i] or "").strip())) in _EN_ALIASES:
            return i
    return columns[0]


def check_table(rows: list[list[str]], header: list[str], only=None):
    """Controle les colonnes de langue du tableau. Retourne
    (rapports [(ligne, colonne, CellReport)], colonne_source, colonnes).

    `only` restreint le controle a ces index de colonnes (choix « une seule
    langue » du dialogue) ; la colonne de reference reste l'anglais, meme
    quand elle n'est pas controlee."""
    columns = language_columns(header)
    source = source_column(header, columns)
    if only is not None:
        wanted = set(only)
        columns = [c for c in columns if c in wanted]
    reports = []
    for r, row in enumerate(rows):
        for c in columns:
            if c == source:
                continue            # la colonne de reference reste affichée
            report = check_cell(row[c] if c < len(row) else "")
            if report is not None:
                reports.append((r, c, report))
    return reports, source, columns


