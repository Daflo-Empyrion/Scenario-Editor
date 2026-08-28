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


def _count_unescaped_quotes(s: str) -> int:
    count = 0
    i = 0
    while i < len(s):
        if s[i] == '\\':
            i += 2
            continue
        if s[i] == '"':
            count += 1
        i += 1
    return count


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

        if stripped.startswith('#'):
            # Un commentaire n'etablit et ne rompt JAMAIS un niveau d'imbrication --
            # verifie sur de vrais fichiers reels (playfield_static.yaml,
            # Sectors.yaml) : des commentaires a indentation ZERO apparaissent
            # couramment au milieu d'une liste profondement imbriquee (ex: sous
            # 'POIs > Random', indente a 8+ espaces), sans que cela signifie une
            # sortie de section. Seule une VRAIE ligne de contenu (mapping/sequence)
            # dont l'indentation est <= base_indent marque la fin du bloc courant --
            # voir le test indent_len <= base_indent juste apres, qui ne s'applique
            # donc plus qu'aux lignes de contenu reel.
            nodes.append(YamlComment(raw=raw))
            i += 1
            continue

        if indent_len <= base_indent:
            break

        is_seq, key, value, comment = _classify(stripped)

        # Chaine entre guillemets non refermee sur cette ligne : YAML autorise une
        # valeur entre guillemets doubles de s'etaler sur plusieurs lignes (y compris
        # des lignes vides -- ex: 'Description: "texte...\n\n...suite."'). Traite AVANT
        # le calcul normal des enfants (qui se tromperait sinon en absorbant les lignes
        # vides intermediaires comme si c'etaient des enfants structurels de l'entree).
        # On consomme les lignes suivantes TELLES QUELLES (pour un round-trip exact)
        # jusqu'a celle qui referme le guillemet, et on construit une version "repliee"
        # (lignes jointes par un espace) dans `value` pour un affichage/edition lisibles.
        if value.startswith('"') and _count_unescaped_quotes(value) % 2 == 1:
            continuation_raw_parts = []
            folded_parts = [value]
            k = i + 1
            closed = False
            while k < end:
                raw_k = lines[k]
                content_k, eol_k, _ = _split_line(raw_k)
                continuation_raw_parts.append(raw_k)
                stripped_k = content_k.strip()
                if stripped_k == '':
                    # Ligne vide entre guillemets : en YAML, un saut de ligne simple se
                    # replie en espace, mais une ligne VIDE cree un veritable retour a
                    # la ligne dans la chaine resultante (souvent utilise pour separer
                    # des paragraphes dans un texte affiche en jeu). On le represente
                    # par la sequence d'echappement '\n' -- valide dans une chaine YAML
                    # entre guillemets doubles, et interpretee comme un vrai retour a
                    # la ligne par le moteur du jeu a l'affichage.
                    folded_parts.append('\\n')
                else:
                    folded_parts.append(stripped_k)
                if _count_unescaped_quotes(content_k) % 2 == 1:
                    closed = True
                    k += 1
                    break
                k += 1
            if closed:
                # Assemble en evitant un espace superflu autour d'un '\n' insere.
                folded = folded_parts[0]
                for part in folded_parts[1:]:
                    if part == '\\n' or folded.endswith('\\n'):
                        folded += part
                    else:
                        folded += ' ' + part
                entry = YamlEntry(
                    raw=raw, indent=indent, is_sequence_item=is_seq, key=key,
                    value=folded,
                    comment=comment, eol=eol, children=[],
                    quoted_continuation_raw="".join(continuation_raw_parts),
                )
                nodes.append(entry)
                if _BLOCK_SCALAR_RE.match(value.strip()):
                    in_block_scalar = True
                    block_scalar_indent = indent_len
                i = k
                continue
            # Pas de guillemet fermant trouve avant la fin du bloc : cas degenere/
            # fichier tronque -- on abandonne le repliage et retombe sur le comportement
            # normal ci-dessous (identique a avant ce correctif, pas pire qu'auparavant).

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
            stripped2 = c2.strip()
            if stripped2 == '' or stripped2.startswith('#'):
                # Meme principe que dans la boucle principale ci-dessus : un
                # commentaire (quelle que soit son indentation, y compris zero)
                # ne marque jamais la fin du bloc d'enfants -- seule une vraie
                # ligne de contenu moins indentee le fait.
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
