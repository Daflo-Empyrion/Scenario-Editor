"""
Parser pour le format yamllite : scan ligne par ligne, avec une pile d'indentation
(au lieu d'une pile d'accolades comme pour l'ECF) pour determiner l'imbrication.

Regles de classification d'une ligne (apres calcul de son indentation) :
  - vide                                -> YamlBlank
  - commentaire (# apres indentation)   -> YamlComment (jamais reinterprete)
  - commence par '- '                   -> item de sequence (YamlEntry, is_sequence_item=True)
  - sinon, contient 'Cle:' en debut     -> entree de mapping (YamlEntry)
  - sinon                                -> traitee comme un YamlComment de secours
                                             (texte brut preserve, non interprete -- ex:
                                             suite d'un scalaire multi-lignes '|' ou '>')

L'imbrication est determinee par indentation : une ligne devient enfant de la derniere
entree ouverte dont l'indentation est strictement inferieure. Les items de sequence
('- ') sont traites comme ayant leur contenu indente a la position juste apres le tiret
(convention YAML standard), ce qui permet a une entree de mapping du type :
    - Name: Alpha
      Tags: [...]
  d'attacher correctement 'Tags' comme frere de 'Name' sous le meme item de sequence.
"""
import re
from typing import List, Optional, Tuple

from .model import YamlBlank, YamlComment, YamlEntry, YamlDocument, YamlNode


def parse_yaml_text(text: str, source_path: Optional[str] = None) -> YamlDocument:
    lines = text.splitlines(keepends=True)
    nodes = _parse_block(lines, 0, len(lines), base_indent=-1)
    return YamlDocument(nodes=nodes, source_path=source_path)


def parse_yaml_file(path) -> YamlDocument:
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8')
    return parse_yaml_text(text, source_path=str(path))


def _split_line(raw_line: str) -> Tuple[str, str, str]:
    if raw_line.endswith('\r\n'):
        content, eol = raw_line[:-2], '\r\n'
    elif raw_line.endswith('\n'):
        content, eol = raw_line[:-1], '\n'
    else:
        content, eol = raw_line, ''
    stripped = content.lstrip(' ')
    indent = content[:len(content) - len(stripped)]
    return stripped, eol, indent


def _find_unquoted_colon(s: str) -> int:
    in_single = in_double = False
    for i, c in enumerate(s):
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == ':' and not in_single and not in_double:
            if i + 1 == len(s) or s[i + 1] == ' ':
                return i
    return -1


def _split_trailing_comment(s: str) -> Tuple[str, Optional[str]]:
    in_single = in_double = False
    for i, c in enumerate(s):
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == '#' and not in_single and not in_double:
            if i == 0 or s[i - 1] == ' ':
                return s[:i].rstrip(), s[i:].rstrip()
    return s, None


_BLOCK_SCALAR_RE = re.compile(r'^[|>][+-]?\d*$')


def _classify(stripped: str) -> Tuple[bool, Optional[str], str, Optional[str]]:
    is_seq = False
    rest = stripped
    if rest.startswith('- '):
        is_seq = True
        rest = rest[2:]
    elif rest == '-':
        is_seq = True
        rest = ''

    code, comment = _split_trailing_comment(rest)
    code = code.rstrip()

    colon_idx = _find_unquoted_colon(code)
    if colon_idx == -1:
        return is_seq, None, code, comment

    key = code[:colon_idx].strip()
    value = code[colon_idx + 1:].strip()
    return is_seq, key, value, comment


def _parse_block(lines: List[str], start: int, end: int, base_indent: int) -> List[YamlNode]:
    nodes: List[YamlNode] = []
    i = start
    in_block_scalar = False
    block_scalar_indent = None

    while i < end:
        raw = lines[i]
        content, eol, indent = _split_line(raw)
        indent_len = len(indent)
        stripped = content.strip()

        if in_block_scalar:
            if stripped == '' or indent_len > block_scalar_indent:
                nodes.append(YamlComment(raw=raw))
                i += 1
                continue
            else:
                in_block_scalar = False

        if stripped == '':
            nodes.append(YamlBlank(raw=raw))
            i += 1
            continue

        if indent_len <= base_indent:
            break

        if stripped.startswith('#'):
            nodes.append(YamlComment(raw=raw))
            i += 1
            continue

        is_seq, key, value, comment = _classify(stripped)

        # Les enfants (imbrication) sont toutes les lignes suivantes plus indentees que
        # la ligne courante elle-meme (son indentation de depart, PAS la position apres
        # le tiret) -- important pour la notation compacte '- Cle: Valeur' ou les cles
        # soeurs suivantes ('Tags:', 'Meta:'...) s'alignent a la meme colonne que 'Cle',
        # pas plus profond. Ex:
        #   - Name: Alpha      <- indent_len=2
        #     Tags: [...]      <- indent=4, doit etre FRERE de Name (meme item), pas enfant
        child_base_indent = indent_len

        child_start = i + 1
        j = child_start
        while j < end:
            c2, _, ind2 = _split_line(lines[j])
            if c2.strip() == '':
                j += 1
                continue
            if len(ind2) > child_base_indent:
                j += 1
                continue
            break
        child_end = j

        children = _parse_block(lines, child_start, child_end, base_indent=child_base_indent) \
            if child_end > child_start else []

        entry = YamlEntry(
            raw=raw, indent=indent, is_sequence_item=is_seq, key=key, value=value,
            comment=comment, eol=eol, children=children,
        )
        nodes.append(entry)

        if _BLOCK_SCALAR_RE.match(value.strip()):
            in_block_scalar = True
            block_scalar_indent = indent_len

        i = child_end

    return nodes
