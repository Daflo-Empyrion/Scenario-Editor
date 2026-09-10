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
    nodes, _, _ = _parse_nodes(lines, 0, depth=0)
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


def _find_inline_block_comment_start(s: str) -> int:
    """Trouve le debut d'un commentaire /* ... */ hors guillemets, ou -1."""
    in_quotes = False
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            in_quotes = not in_quotes
        elif not in_quotes and c == '/' and i + 1 < n and s[i + 1] == '*':
            return i
        i += 1
    return -1


def _split_top_level_comment(s: str) -> Tuple[str, Optional[str]]:
    """Sépare le code du commentaire de fin de ligne.

    Deux syntaxes de commentaire existent dans les vrais fichiers du jeu :
      - '# commentaire' ;
      - '/* commentaire */' -- sur sa propre ligne OU EN FIN d'une ligne de
        propriete/bloc : 'SpawnInSameDirection: false /* if true,animals
        will spawn ... */'. Ce second cas n'etait pas reconnu : le
        commentaire restait dans la valeur, et la moindre virgule qu'il
        contenait (ex 'true,animals') etait comprise comme un eclatement de
        valeur -> fausses alertes E004 et paires polluees (signale le
        10/09/2026 sur RE2 EVO / FactionWarfare.ecf).
    Le marqueur hors guillemets le plus a gauche gagne ; un /* non ferme en
    fin de ligne ouvre un commentaire multi-lignes (gere par l'appelant via
    in_block_comment)."""
    idx_hash = _find_unquoted(s, '#')
    idx_block = _find_inline_block_comment_start(s)
    if idx_block != -1 and (idx_hash == -1 or idx_block < idx_hash):
        return s[:idx_block].rstrip(), s[idx_block:].rstrip()
    if idx_hash != -1:
        return s[:idx_hash].rstrip(), s[idx_hash:].rstrip()
    return s, None


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


def _parse_nodes(lines: List[str], start_idx: int, depth: int) -> Tuple[List[EcfNode], int, bool]:
    """Parse une séquence de lignes jusqu'à la fin de fichier ou une accolade fermante
    correspondant au niveau appelant. Retourne (liste_de_noeuds, index_suivant, ferme_par_accolade).
    Le 3eme element est False si on a atteint la fin du fichier sans rencontrer de '}' --
    cas normalement impossible sur un ECF valide, mais gere proprement au cas ou (evite de
    dupliquer une ligne deja consommee comme enfant lors d'un repli en fin de fichier)."""
    nodes: List[EcfNode] = []
    i = start_idx
    n = len(lines)
    in_block_comment = False  # a l'interieur d'un commentaire /* ... */ non encore ferme

    while i < n:
        raw = lines[i]
        content, eol, indent = _split_line(raw)
        stripped = content.strip()
        # Un BOM en tout debut de fichier (de vrais fichiers du jeu en ont un)
        # ne doit jamais empecher la reconnaissance de la premiere ligne comme
        # bloc, commentaire ou propriete. Il reste conserve dans `raw`, donc
        # le round-trip reste byte-pour-byte (voir la note de parse_ecf_file).
        stripped = stripped.lstrip('\ufeff')

        if in_block_comment:
            # Toute ligne a l'interieur d'un /* ... */ est un commentaire, quel que soit
            # son contenu (meme si elle ressemble a une propriete ou contient { ou }).
            nodes.append(EcfComment(raw=raw))
            if '*/' in content:
                in_block_comment = False
            i += 1
            continue

        if stripped == '':
            nodes.append(EcfBlank(raw=raw))
            i += 1
            continue

        if stripped.startswith('#'):
            # Commentaire : jamais réinterprété comme structure, même s'il contient { ou }
            nodes.append(EcfComment(raw=raw))
            i += 1
            continue

        if stripped.startswith('/*'):
            # Commentaire de style C, utilise par certains scenarios (ex: Atlantis Next)
            # pour desactiver une ligne. Peut se refermer sur la meme ligne ou plus loin.
            nodes.append(EcfComment(raw=raw))
            if '*/' not in stripped:
                in_block_comment = True
            i += 1
            continue

        if _CLOSE_RE.match(stripped):
            # Fin du bloc courant -- on remonte au parent
            return nodes, i + 1, True

        if _OPEN_RE.match(stripped):
            after_brace = stripped[1:]
            code, comment = _split_top_level_comment(after_brace)
            # /* non ferme en fin de ligne d'entete : la suite du fichier est
            # commentaire jusqu'au */ (meme semantique que les proprietes).
            if comment is not None and comment.startswith('/*') and '*/' not in comment:
                in_block_comment = True
            kind, pairs = _split_block_header(code)

            children, next_i, closed = _parse_nodes(lines, i + 1, depth + 1)

            close_raw = lines[next_i - 1] if closed else ''

            block = EcfBlock(
                indent=indent,
                kind=kind,
                pairs=pairs,
                comment=comment,
                eol=eol,
                raw_open=raw,
                close_raw=close_raw,
                children=children,
            )
            nodes.append(block)
            i = next_i
            continue

        # Ligne de propriété classique
        code, comment = _split_top_level_comment(stripped)
        # /* non ferme en fin de ligne : le commentaire continue sur les
        # lignes suivantes jusqu'au */ (les vrais fichiers du jeu en ont).
        if comment is not None and comment.startswith('/*') and '*/' not in comment:
            in_block_comment = True
        pairs = _parse_pairs(code)
        nodes.append(EcfProperty(
            raw=raw,
            indent=indent,
            pairs=pairs,
            comment=comment,
            eol=eol,
        ))
        i += 1

    return nodes, i, False
