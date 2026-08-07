"""
Scanner de scénario : construit un objet Scenario à partir soit d'un dossier réel sur disque,
soit d'une simple liste de chemins (utile pour tester à partir d'un listing tree/Get-ChildItem
sans avoir les fichiers réels disponibles).
"""
from pathlib import Path, PureWindowsPath, PurePath
from typing import Iterable, List

from .models import Scenario, Playfield, FileEntry, EDITABLE_EXTENSIONS


def scan_scenario(root: Path) -> Scenario:
    """Scan réel : parcourt un dossier sur disque (chemins natifs de l'OS courant)."""
    root = Path(root)
    all_paths = [p for p in root.rglob('*') if p.is_file()]
    return _build_scenario(root, all_paths)


def verify_integrity(scenario: Scenario, root: Path = None) -> dict:
    """
    Vérification de sécurité : recompte tous les fichiers réellement présents sur le disque
    (comptage brut, sans catégorisation) et compare au total classé par le scanner.
    Si les deux nombres ne correspondent pas, des fichiers ont été ignorés silencieusement.

    Retourne un dict avec 'disk_count', 'scanned_count', 'missing_count', 'ok' (bool).
    Ne fonctionne que sur un vrai dossier disque (pas depuis un listing texte).
    """
    root = Path(root) if root else scenario.root_path
    if not root.exists():
        return {
            'ok': None,
            'error': f"Le dossier {root} n'existe pas sur ce disque -- vérification impossible "
                     f"(utile seulement pour un vrai scan disque, pas pour un listing texte)."
        }

    disk_files = set(p for p in root.rglob('*') if p.is_file())
    disk_count = len(disk_files)

    scanned_count = scenario.total_file_count(include_shared=True)

    # Reconstruit l'ensemble des fichiers effectivement classés par le scanner, pour
    # pouvoir lister lesquels manquent précisément (pas juste un nombre).
    scanned_files = set()
    scanned_files.update(f.path for f in scenario.configuration)
    scanned_files.update(f.path for f in scenario.sectors)
    scanned_files.update(f.path for f in scenario.random_presets)
    scanned_files.update(f.path for f in scenario.extras)
    scanned_files.update(f.path for f in scenario.other_files)
    for pf in scenario.playfields.values():
        scanned_files.update(pf.role_files.values())
        scanned_files.update(f.path for f in pf.backups)
        scanned_files.update(f.path for f in pf.other_files)
    if scenario.shared_data:
        sub = verify_integrity(scenario.shared_data)
        scanned_files.update(sub.get('_scanned_files', set()))

    missing = disk_files - scanned_files

    return {
        'ok': len(missing) == 0,
        'disk_count': disk_count,
        'scanned_count': len(scanned_files),
        'missing_count': len(missing),
        'missing_files': sorted(missing)[:50],  # limite d'affichage
        '_scanned_files': scanned_files,  # usage interne (récursion SharedData)
    }


def scan_from_paths(paths: Iterable[str], root_hint: str = None) -> Scenario:
    """
    Construit un Scenario à partir d'une simple liste de chemins texte
    (ex: sortie de `tree /F` ou `Get-ChildItem -Recurse`).
    Ne nécessite pas que les fichiers existent réellement sur ce disque.

    Détecte automatiquement les chemins de style Windows (C:\\...) même si ce code
    tourne sur un environnement Unix (pratique pour tester sans être sur la machine cible).
    """
    cleaned = [p.strip() for p in paths if p.strip()]
    path_cls = _detect_path_class(cleaned)
    path_objs = [path_cls(p) for p in cleaned]
    root = path_cls(root_hint) if root_hint else _guess_root(path_objs)
    return _build_scenario(root, path_objs)


def _detect_path_class(paths: List[str]):
    """Devine s'il faut interpréter les chemins comme Windows (antislash) ou natifs."""
    if paths and ('\\' in paths[0] or (len(paths[0]) > 1 and paths[0][1] == ':')):
        return PureWindowsPath
    return Path


def _guess_root(paths: List[PurePath]) -> PurePath:
    """Déduit le dossier racine commun à partir d'une liste de chemins complets."""
    if not paths:
        return Path('.')
    path_cls = type(paths[0])
    parts_lists = [p.parts for p in paths]
    min_len = min(len(parts) for parts in parts_lists)
    common = []
    for i in range(min_len):
        values_at_i = {parts[i] for parts in parts_lists}
        if len(values_at_i) == 1:
            common.append(parts_lists[0][i])
        else:
            break
    return path_cls(*common) if common else path_cls('.')


def _build_scenario(root: Path, all_paths: List[Path]) -> Scenario:
    scenario = Scenario(root_path=root, name=root.name)
    shared_data_paths = []

    for p in all_paths:
        try:
            rel = p.relative_to(root)
        except ValueError:
            # Chemin hors de la racine détectée -> ignoré
            continue
        rel_parts = rel.parts
        if not rel_parts:
            continue

        if rel_parts[0] == 'SharedData':
            shared_data_paths.append(p)
            continue

        _classify(scenario, rel_parts, p)

    if shared_data_paths:
        shared_root = root / 'SharedData'
        scenario.shared_data = _build_scenario(shared_root, shared_data_paths)

    return scenario


def _classify(scenario: Scenario, rel_parts: tuple, p: Path) -> None:
    top = rel_parts[0]

    # Un listing tree/Get-ChildItem inclut aussi les dossiers eux-mêmes comme entrées
    # (ex: "Content", "Extras\PDA"). Dans ce jeu de données, une entrée sans extension
    # est quasi toujours un dossier -> on l'ignore. (Ce heuristique ne s'applique qu'au
    # scan depuis un listing texte ; scan_scenario() sur un vrai disque utilise is_file()
    # et n'a pas ce problème.)
    if p.suffix == '':
        return

    # Content/Configuration/*.ecf|.csv|.txt
    if top == 'Content' and len(rel_parts) > 1 and rel_parts[1] == 'Configuration':
        if len(rel_parts) == 2:
            return  # c'est le dossier lui-même, pas un fichier
        scenario.configuration.append(_make_entry(p, 'Configuration'))
        return

    # Playfields/<nom>/... : plusieurs conventions de nommage possibles selon le type
    # de playfield (surface, spatial, soleil...), voir _playfield_role().
    if top == 'Playfields' and len(rel_parts) >= 2:
        if len(rel_parts) == 2:
            return  # dossier du playfield lui-même
        pf_name = rel_parts[1]
        pf = scenario.playfields.setdefault(pf_name, Playfield(name=pf_name))
        fname = p.name.lower()

        if fname.startswith('+') or 'backup' in fname:
            pf.backups.append(_make_entry(p, 'Playfield-backup'))
            return

        role = _playfield_role(fname)
        if role:
            pf.role_files[role] = p
        else:
            pf.other_files.append(_make_entry(p, 'Playfield'))
        return

    if top == 'Sectors':
        if len(rel_parts) > 1:
            scenario.sectors.append(_make_entry(p, 'Sectors'))
        return

    if top == 'RandomPresets':
        if len(rel_parts) > 1:
            scenario.random_presets.append(_make_entry(p, 'RandomPresets'))
        return

    if top == 'Extras':
        if len(rel_parts) > 1:
            scenario.extras.append(_make_entry(p, 'Extras'))
        return

    # Tout le reste : Prefabs/*.epb, Logos/*, fichiers de racine (gameoptions.yaml, description.txt...),
    # ou tout dossier top-level non reconnu. On catégorise juste par nom de dossier top-level pour info.
    # On ignore les entrées qui sont clairement des dossiers intermédiaires (pas de suffixe et
    # une entrée plus profonde partage ce même chemin) -- en pratique on garde tout ce qui a une
    # extension, et pour les entrées sans extension on les garde aussi (ex: fichiers sans extension).
    category = top if top else 'Root'
    scenario.other_files.append(_make_entry(p, category))


def _playfield_role(fname_lower: str) -> str:
    """
    Détermine le rôle d'un fichier trouvé dans un dossier Playfields/<nom>/, à partir
    de son nom. Couvre les conventions observées : surface (playfield_*), spatial
    (space_*), soleil (sun_*), et l'ancien format combiné (playfield.yaml).
    Retourne '' si le fichier n'est pas reconnu (garde comme other_files).
    """
    if fname_lower == 'playfield.yaml':
        return 'combined'
    if fname_lower.endswith('dynamic.yaml'):
        return 'dynamic'
    if fname_lower.endswith('static.yaml'):
        return 'static'
    if fname_lower == 'terrain.ecf':
        return 'terrain'
    return ''


def _make_entry(path: Path, category: str) -> FileEntry:
    ext = path.suffix.lower()
    return FileEntry(path=path, category=category, editable=ext in EDITABLE_EXTENSIONS)
