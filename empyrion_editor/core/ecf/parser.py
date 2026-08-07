"""
Parser ECF : transforme le texte brut d'un fichier .ecf en EcfDocument (AST).

Approche : scan ligne par ligne, en gardant le texte brut de chaque ligne pour
permettre une reproduction fidèle. Une ligne est classée en 4 catégories :
  - vide                    -> EcfBlank
  - commentaire (#...)      -> EcfComment (jamais interprétée comme structure)
  - ouverture de bloc ({)   -> EcfBlock (empile un nouveau contexte)
  - fermeture de bloc (})   -> dépile le contexte courant
  - sinon                   -> EcfProperty (Cle: valeur, Cle2: valeur2  # commentaire)

Le parsing des paires "Cle: valeur" est "quote-aware" : les virgules et les '#'
à l'intérieur de guillemets doubles ne sont pas traités comme des séparateurs,
ce qui est indispensable ici car des valeurs comme "5,19" ou "8,1" contiennent
des virgules.
"""
import re
from typing import List, Optional, Tuple

from .model import EcfBlank, EcfComment, EcfProperty, EcfBlock, EcfDocument, EcfNode


def parse_ecf_text(text: str, source_path: Optional[str] = None) -> EcfDocument:
    lines = text.splitlines(keepends=True)
    nodes, _ = _parse_nodes(lines, 0, depth=0)
    return EcfDocument(nodes=nodes, source_path=source_path)


def parse_ecf_file(path) -> EcfDocument:
    # Note : on utilise 'utf-8' (pas 'utf-8-sig') volontairement -- si le fichier
    # commence par un BOM (ex: BlocksConfig.ecf), on le garde tel quel comme premier
    # caractère du texte (\ufeff), qui finit dans le "raw" de la première ligne et sera
    # donc automatiquement reproduit à l'identique au moment du render(). Utiliser
    # 'utf-8-sig' supprimerait le BOM à la lecture sans le remettre à l'écriture,
    # cassant le round-trip byte-pour-byte sur ce type de fichier.
    with open(path, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    return parse_ecf_text(text, source_path=str(path))


# ------------------------------------------------------------------
# Découpage bas niveau d'une ligne : indent / contenu / commentaire / eol
# ------------------------------------------------------------------

def _split_line(raw_line: str) -> Tuple[str, str, str]:
    """Sépare une ligne brute en (contenu_sans_eol, eol, indent).
    eol est '\\r\\n', '\\n' ou '' (dernière ligne sans retour)."""
    if raw_line.endswith('\r\n'):
        content, eol = raw_line[:-2], '\r\n'
    elif raw_line.endswith('\n'):
        content, eol = raw_line[:-1], '\n'
    else:
        content, eol = raw_line, ''
    stripped = content.lstrip(' \t')
    indent = content[:len(content) - len(stripped)]
    return stripped, eol, indent


def _find_unquoted(s: str, chars: str, start: int = 0) -> int:
    """Trouve la première occurrence d'un caractère de `chars` en dehors de guillemets doubles."""
    in_quotes = False
    for i in range(start, len(s)):
        c = s[i]
        if c == '"':
            in_quotes = not in_quotes
        elif not in_quotes and c in chars:
            return i
    return -1


def _split_top_level_comment(s: str) -> Tuple[str, Optional[str]]:
    """Sépare le code du commentaire de fin de ligne (premier '#' hors guillemets)."""
    idx = _find_unquoted(s, '#')
    if idx == -1:
        return s, None
    code = s[:idx].rstrip()
    comment = s[idx:].rstrip()
    return code, comment


def _split_top_level_commas(s: str) -> List[str]:
    """Découpe sur les virgules de premier niveau (hors guillemets)."""
    parts = []
    depth_start = 0
    in_quotes = False
    for i, c in enumerate(s):
        if c == '"':
            in_quotes = not in_quotes
        elif c == ',' and not in_quotes:
            parts.append(s[depth_start:i])
            depth_start = i + 1
    parts.append(s[depth_start:])
    return parts


def _parse_pairs(s: str) -> List[Tuple[Optional[str], str]]:
    """Parse 'Cle: valeur, Cle2: valeur2' -> [('Cle','valeur'), ('Cle2','valeur2')].
    Si un segment n'a pas de ':' de premier niveau, il est gardé tel quel avec clé=None
    (cas de tokens isolés, rares mais possibles)."""
    pairs = []
    for part in _split_top_level_commas(s):
        part = part.strip()
        if not part:
            continue
        colon_idx = _find_unquoted(part, ':')
        if colon_idx == -1:
            pairs.append((None, part))
        else:
            key = part[:colon_idx].strip()
            value = part[colon_idx + 1:].strip()
            pairs.append((key, value))
    return pairs


def _split_block_header(content: str) -> Tuple[str, List[Tuple[Optional[str], str]]]:
    """
    Sépare le 'genre' du bloc de ses propriétés inline, à partir du contenu après '{'.
    Ex: '+Container Id: 5'  -> kind='+Container', pairs=[('Id','5')]
        'Child Items'       -> kind='Child Items', pairs=[]
        'Container Id: 251' -> kind='Container', pairs=[('Id','251')]
    """
    colon_idx = _find_unquoted(content, ':')
    if colon_idx == -1:
        return content.strip(), []

    before = content[:colon_idx]
    tokens = before.split()
    if not tokens:
        # Ligne malformée (':' en tout début) -- on garde tout comme "kind" par sécurité
        return content.strip(), []

    key_start_token = tokens[-1]
    kind = " ".join(tokens[:-1]).strip()
    # Position du début du dernier token avant les ':' pour reconstruire "Cle: valeur..."
    key_pos = before.rfind(key_start_token)
    header_props_str = content[key_pos:]
    pairs = _parse_pairs(header_props_str)
    return kind, pairs


# ------------------------------------------------------------------
# Construction de l'arbre (parsing récursif via pile explicite)
# ------------------------------------------------------------------

_OPEN_RE = re.compile(r'^\{')
_CLOSE_RE = re.compile(r'^\}')


def _parse_nodes(lines: List[str], start_idx: int, depth: int) -> Tuple[List[EcfNode], int]:
    """Parse une séquence de lignes jusqu'à la fin de fichier ou une accolade fermante
    correspondant au niveau appelant. Retourne (liste_de_noeuds, index_suivant)."""
    nodes: List[EcfNode] = []
    i = start_idx
    n = len(lines)

    while i < n:
        raw = lines[i]
        content, eol, indent = _split_line(raw)
        stripped = content.strip()

        if stripped == '':
            nodes.append(EcfBlank(raw=raw))
            i += 1
            continue

        if stripped.startswith('#'):
            # Commentaire : jamais réinterprété comme structure, même s'il contient { ou }
            nodes.append(EcfComment(raw=raw))
            i += 1
            continue

        if _CLOSE_RE.match(stripped):
            # Fin du bloc courant -- on remonte au parent
            return nodes, i + 1

        if _OPEN_RE.match(stripped):
            after_brace = stripped[1:]
            code, comment = _split_top_level_comment(after_brace)
            kind, pairs = _split_block_header(code)

            children, next_i = _parse_nodes(lines, i + 1, depth + 1)

            close_raw = lines[next_i - 1] if next_i - 1 < n and next_i > i + 1 else ''
            # Si le fichier se termine sans accolade fermante explicite, close_raw reste vide
            # (cas limite, ne devrait pas arriver sur un ECF valide).

            block = EcfBlock(
                indent=indent,
                kind=kind,
                pairs=pairs,
                comment=comment,
                eol=eol,
                raw_open=raw,
                close_raw=close_raw if _CLOSE_RE.match(_split_line(close_raw)[0].strip()) else '',
                children=children,
            )
            nodes.append(block)
            i = next_i
            continue

        # Ligne de propriété classique
        code, comment = _split_top_level_comment(stripped)
        pairs = _parse_pairs(code)
        nodes.append(EcfProperty(
            raw=raw,
            indent=indent,
            pairs=pairs,
            comment=comment,
            eol=eol,
        ))
        i += 1

    return nodes, i
