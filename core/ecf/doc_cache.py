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
Cache de documents ECF parses pour les LECTURES -- reponse a un retour
utilisateur du 31/08/2026 ("latence de quelques secondes a l'ouverture des
fiches") : un clic dans l'arbre technologique re-parserent BlocksConfig.ecf/
ItemsConfig.ecf 2 a 3 fois (fiche, provider, pool de valeurs) -- 0.33 s par
parse sur un fichier de 1.2 Mo, plusieurs secondes sur les vrais fichiers
vanilla.

Contrat STRICT :
  - Le document retourne est PARTAGE et doit etre considere LECTURE SEULE.
    Toutes les lectures fiche (find_block_by_name, scan du pool de valeurs,
    extraction des noeuds d'arbre) sont candidates ;
  - TOUTE ecriture continue de passer par parse_ecf_file() directement
    (parse -> mutation -> reecriture atomique) -- jamais via ce cache ;
  - Invalidation automatique par (st_mtime_ns, st_size) : une reecriture
    (atomic_write_text ou edition externe) change l'un des deux, la lecture
    suivante re-parse donc un document frais.
"""
from pathlib import Path
from typing import Dict, Optional, Tuple

from .parser import EcfDocument, parse_ecf_file

# str(chemin) -> ((mtime_ns, taille), document)
_cache: Dict[str, Tuple[Tuple[int, int], EcfDocument]] = {}
_MAX_ENTRIES = 8


def get_parsed_doc(path) -> EcfDocument:
    """Document parse du fichier, repris du cache si le fichier n'a pas
    change depuis le dernier parse (voir le contrat en docstring de
    module). Retombe sur un parse direct si le fichier est insaisissable."""
    p = Path(path)
    try:
        st = p.stat()
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        return parse_ecf_file(p)
    key = str(p)
    entry = _cache.get(key)
    if entry is not None and entry[0] == stamp:
        return entry[1]
    doc = parse_ecf_file(p)
    if len(_cache) >= _MAX_ENTRIES:
        _cache.pop(next(iter(_cache)))  # FIFO : les fichiers de config sont peu nombreux
    _cache[key] = (stamp, doc)
    return doc


def invalidate(path: Optional[str] = None) -> None:
    """Force un re-parse a la prochaine lecture (tout le cache si sans
    argument) -- filet de securite pour les rares cas ou la cle
    (mtime, taille) ne suffirait pas."""
    if path is None:
        _cache.clear()
    else:
        _cache.pop(str(Path(path)), None)
