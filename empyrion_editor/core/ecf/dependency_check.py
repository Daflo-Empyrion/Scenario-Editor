"""
Verification des references entre blocs ECF (principalement 'Ref', le mecanisme
d'heritage d'Empyrion : un bloc 'Ref: X' herite des proprietes du bloc dont le 'Name'
vaut X). Une reference cassee (qui ne correspond a aucun 'Name' existant dans le
scenario) echoue silencieusement en jeu -- l'heritage attendu n'a simplement pas lieu,
sans message d'erreur visible. Utile a lancer apres une fusion pour reperer ce genre de
probleme avant de tester en jeu.

Portee actuelle : verifie uniquement 'Ref' (le seul mecanisme de reference dont la
semantique est certaine -- doit correspondre a un 'Name'). D'autres cles comme
'CustomIcon' ne sont pas verifiees ici : elles renvoient vers des ressources visuelles
(icones) dont on n'a pas d'index fiable dans les fichiers ECF eux-memes.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

from .parser import parse_ecf_file
from .model import block_identity


@dataclass
class BrokenReference:
    file: Path
    kind: str
    identity: str     # Id (ou Name a defaut) du bloc qui contient la reference cassee
    ref_key: str       # ex: 'Ref'
    ref_value: str     # la valeur qui ne correspond a aucun Name existant

    def label(self) -> str:
        return f"{self.file.name} : {self.kind} [{self.identity}] -- {self.ref_key}: {self.ref_value}"


def build_name_index(ecf_files: List[Path]) -> Dict[str, List[Path]]:
    """Construit un index {Name -> [fichiers ou ce Name est declare]} a partir d'une
    liste de fichiers ECF. Le but est juste de savoir si UNE valeur existe QUELQUE PART."""
    index: Dict[str, List[Path]] = {}
    for path in ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            name = block.get_property('Name')
            if name:
                index.setdefault(name, []).append(path)
    return index


def check_references(ecf_files: List[Path], ref_keys: tuple = ('Ref',)) -> List[BrokenReference]:
    """Verifie que chaque valeur des cles de reference fournies (par defaut 'Ref')
    correspond a un 'Name' existant QUELQUE PART dans la liste de fichiers fournie."""
    name_index = build_name_index(ecf_files)
    broken: List[BrokenReference] = []

    for path in ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        for block in doc.iter_blocks():
            for key in ref_keys:
                val = block.get_property(key)
                if val and val not in name_index:
                    broken.append(BrokenReference(
                        file=path, kind=block.kind,
                        identity=block_identity(block) or "?",
                        ref_key=key, ref_value=val,
                    ))
    return broken
