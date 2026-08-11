"""
Gestion de l'espace de travail (Workspace) : un scenario source A (lecture seule), un
scenario source B optionnel (lecture seule, pour la fusion), et une COPIE DE TRAVAIL
physique -- un scenario complet, copie sur disque a un nouvel emplacement -- qui est le
seul scenario modifiable. Les sources A et B ne sont jamais touchees.
"""
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .scanner import scan_scenario
from .models import Scenario


@dataclass
class Workspace:
    source_a: Scenario
    source_a_root: Path
    working: Scenario
    working_root: Path
    source_b: Optional[Scenario] = None
    source_b_root: Optional[Path] = None

    @property
    def is_merge_mode(self) -> bool:
        return self.source_b is not None

    def rescan_working(self) -> None:
        """A appeler apres toute modification physique de la copie de travail (ex:
        copie d'un fichier depuis une source) pour rafraichir l'inventaire."""
        self.working = scan_scenario(self.working_root)


def create_working_copy(source_root: Path, dest_root: Path) -> Path:
    """Copie physiquement TOUT le contenu du scenario source vers un nouvel
    emplacement, qui devient la copie de travail modifiable. Le dossier de destination
    ne doit pas deja exister (securite : on ne veut jamais ecraser quoi que ce soit par
    erreur)."""
    if dest_root.exists():
        raise FileExistsError(f"Le dossier de destination existe deja : {dest_root}")
    shutil.copytree(source_root, dest_root, copy_function=shutil.copy2)
    return dest_root


def open_workspace(source_a_root: Path, working_dest: Path,
                    source_b_root: Optional[Path] = None) -> Workspace:
    """Cree la copie de travail a partir de la source A, scanne les scenarios
    concernes, et retourne le Workspace pret a l'emploi."""
    source_a = scan_scenario(source_a_root)
    create_working_copy(source_a_root, working_dest)
    working = scan_scenario(working_dest)
    source_b = scan_scenario(source_b_root) if source_b_root else None
    return Workspace(
        source_a=source_a, source_a_root=source_a_root,
        working=working, working_root=working_dest,
        source_b=source_b, source_b_root=source_b_root,
    )


def load_existing_workspace(source_a_root: Path, working_root: Path,
                             source_b_root: Optional[Path] = None) -> Workspace:
    """Recharge un workspace DEJA CREE precedemment (la copie de travail existe deja
    sur disque, avec eventuellement des modifications en cours) -- pour reprendre un
    projet, sans recreer la copie physique. Contrairement a open_workspace(), ne copie
    rien : se contente de scanner les trois emplacements tels qu'ils sont."""
    if not working_root.exists():
        raise FileNotFoundError(f"La copie de travail n'existe plus : {working_root}")
    source_a = scan_scenario(source_a_root)
    working = scan_scenario(working_root)
    source_b = scan_scenario(source_b_root) if source_b_root else None
    return Workspace(
        source_a=source_a, source_a_root=source_a_root,
        working=working, working_root=working_root,
        source_b=source_b, source_b_root=source_b_root,
    )


def copy_file_into_working(workspace: Workspace, source_file: Path, source_root: Path) -> Path:
    """Copie un fichier (mesh, icone, ECF, YAML...) depuis une source (A ou B) vers la
    copie de travail, en preservant son chemin relatif. Cree les dossiers intermediaires
    si besoin. Retourne le chemin de destination. Ecrase sans fusion (voir
    merge_file_into_working pour la fusion intelligente des .ecf existants)."""
    rel = source_file.relative_to(source_root)
    dest = workspace.working_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, dest)
    return dest


@dataclass
class MergeHighlight:
    """Ce qui a ete ajoute lors d'une fusion, pour coloriser la vue du fichier resultat."""
    new_blocks: set     # {(kind, identite)} -- blocs entierement nouveaux (n'existaient pas avant)
    changed_blocks: dict  # {(kind, identite): {cles ajoutees/completees}} -- blocs existants completes


def merge_file_into_working(workspace: Workspace, source_file: Path, source_root: Path,
                             source_label: str) -> Tuple[Path, Optional["MergeHighlight"], list, Optional[list]]:
    """
    Importe un fichier depuis une source (A ou B) vers la copie de travail :
      - .ecf qui existe deja -> FUSION intelligente (mode 'properties', copie de
        travail prioritaire, garde-fou anti-collision d'Id -- voir plus bas).
      - .csv qui existe deja -> FUSION par cle (1ere colonne) : la copie de travail
        est prioritaire, seules les cellules VIDES sont completees depuis la source,
        les lignes de cle absente sont ajoutees. Retourne un rapport texte (4eme
        valeur) au lieu d'un MergeHighlight.
      - tout le reste (fichier absent de la copie de travail, ou format sans moteur de
        fusion dedie) -> simple copie.

    IMPORTANT -- garde-fou anti-collision (ECF uniquement) : si un Id est partage
    entre deux blocs dont la propriete 'Name' differe (meme Id, materiel different),
    le bloc n'est JAMAIS fusionne a l'aveugle -- ajoute en fin de fichier, DESACTIVE
    (commente), pour revue manuelle.

    Retourne (chemin_destination, highlight_ecf_ou_None, conflits_id_ecf, rapport_csv_ou_None).
    """
    rel = source_file.relative_to(source_root)
    dest = workspace.working_root / rel

    if dest.suffix.lower() == '.csv' and dest.exists():
        from .csv_handler import CsvHandler, merge_csv_documents, render_csv

        handler = CsvHandler()
        working_doc = handler.parse(handler.load(dest))
        source_doc = handler.parse(handler.load(source_file))
        merged_doc, csv_report = merge_csv_documents(working_doc, source_doc)

        with open(dest, 'w', encoding='utf-8', newline='') as f:
            f.write(render_csv(merged_doc))

        return dest, None, [], csv_report

    if dest.suffix.lower() != '.ecf' or not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, dest)
        return dest, None, [], None

    from .ecf.parser import parse_ecf_file
    from .ecf.merge import merge_documents

    working_doc = parse_ecf_file(dest)
    source_doc = parse_ecf_file(source_file)
    result = merge_documents(
        [("Copie de travail", working_doc), (source_label, source_doc)],
        mode='properties',
    )

    with open(dest, 'w', encoding='utf-8', newline='') as f:
        f.write(result.document.render())

    new_blocks = {
        (e.kind, e.identity) for e in result.report
        if len(e.sources_present) == 1 and e.winning_source == source_label
    }
    changed_blocks = {}
    for e in result.report:
        if e.property_overrides:
            idents = {ov.split(' (depuis')[0] for ov in e.property_overrides}
            changed_blocks[(e.kind, e.identity)] = idents

    highlight = MergeHighlight(new_blocks=new_blocks, changed_blocks=changed_blocks)
    return dest, highlight, result.id_conflicts, None


def merge_folder_into_working(workspace: Workspace, source_folder: Path, source_root: Path,
                               source_label: str) -> Tuple[dict, list, dict]:
    """
    Fusionne recursivement TOUS les fichiers d'un dossier (et sous-dossiers) source vers
    la copie de travail, fichier par fichier -- meme logique que merge_file_into_working
    pour chacun (fusion intelligente pour les .ecf existants, fusion par cle pour les
    .csv existants, simple copie sinon). Utile pour importer plusieurs fichiers d'un
    coup sans fusionner tout le scenario.

    Retourne (dict {chemin: MergeHighlight} pour les .ecf, liste de tous les conflits
    d'Id, dict {chemin: rapport} pour les .csv).
    """
    highlights = {}
    all_conflicts = []
    csv_reports = {}
    files = [p for p in source_folder.rglob('*') if p.is_file()]
    for f in files:
        dest, highlight, conflicts, csv_report = merge_file_into_working(workspace, f, source_root, source_label)
        if highlight:
            highlights[dest] = highlight
        if csv_report:
            csv_reports[dest] = csv_report
        all_conflicts.extend(conflicts)
    return highlights, all_conflicts, csv_reports


def merge_csv_row_into_working(workspace: Workspace, working_relative_path: Path,
                                row: list) -> Tuple[Path, str]:
    """Fusionne UNE SEULE ligne CSV (venant d'une source) dans le fichier correspondant
    de la copie de travail, SANS toucher au reste du fichier. Meme logique que
    merge_csv_documents (jamais d'ecrasement, complete seulement les cellules vides).
    Retourne (chemin_du_fichier, statut) -- statut : 'added', 'merged', 'unchanged'."""
    dest = workspace.working_root / working_relative_path
    if not dest.exists():
        raise FileNotFoundError(
            f"Le fichier {dest} n'existe pas encore dans la copie de travail -- "
            f"importe d'abord le fichier entier avant de fusionner une ligne precise."
        )

    from .csv_handler import CsvHandler, merge_single_csv_row, render_csv

    handler = CsvHandler()
    doc = handler.parse(handler.load(dest))
    doc, status = merge_single_csv_row(doc, row)

    with open(dest, 'w', encoding='utf-8', newline='') as f:
        f.write(render_csv(doc))

    return dest, status


def translate_csv_cell_into_working(workspace: Workspace, working_relative_path: Path,
                                     key: str, target_code: str, target_label: str,
                                     translated_value: str) -> Tuple[Path, str]:
    """
    Applique une traduction (deja calculee) dans la cellule de la copie de travail
    correspondant a la cle `key` et a la colonne de la langue cible (trouvee par
    correspondance d'en-tete, code ou libelle). Meme philosophie que le reste de la
    fusion CSV : ne remplace JAMAIS une cellule deja non-vide.

    Retourne (chemin_du_fichier, statut) -- statut : 'added' (nouvelle ligne creee),
    'merged' (cellule vide completee), ou 'unchanged' (deja une valeur, rien fait).
    """
    dest = workspace.working_root / working_relative_path
    if not dest.exists():
        raise FileNotFoundError(
            f"Le fichier {dest} n'existe pas encore dans la copie de travail -- "
            f"importe d'abord le fichier entier."
        )

    from .csv_handler import CsvHandler, render_csv

    handler = CsvHandler()
    doc = handler.parse(handler.load(dest))

    target_col = None
    if doc.header:
        from .translation import find_language_aliases, _normalize
        aliases = find_language_aliases(target_code, target_label)
        for c, h in enumerate(doc.header):
            if _normalize(h.strip()) in aliases:
                target_col = c
                break
    if target_col is None:
        raise ValueError(
            f"Aucune colonne correspondant a la langue '{target_label}' ({target_code}) "
            f"trouvee dans l'en-tete de {dest.name}."
        )

    for i, row in enumerate(doc.rows):
        if row and row[0] == key:
            existing = row[target_col] if target_col < len(row) else ""
            if existing.strip():
                return dest, 'unchanged'
            new_row = list(row)
            while len(new_row) <= target_col:
                new_row.append("")
            new_row[target_col] = translated_value
            doc.rows[i] = new_row
            with open(dest, 'w', encoding='utf-8', newline='') as f:
                f.write(render_csv(doc))
            return dest, 'merged'

    n_cols = len(doc.header) if doc.header else (target_col + 1)
    new_row = [""] * max(n_cols, target_col + 1)
    new_row[0] = key
    new_row[target_col] = translated_value
    doc.rows.append(new_row)
    with open(dest, 'w', encoding='utf-8', newline='') as f:
        f.write(render_csv(doc))
    return dest, 'added'


def merge_block_into_working(workspace: Workspace, working_relative_path: Path,
                              block, source_label: str) -> Tuple[Path, str, Optional["MergeHighlight"]]:
    """
    Fusionne UN SEUL bloc (venant d'une source) dans le fichier correspondant de la
    copie de travail, SANS toucher au reste du fichier -- utile pour importer une
    seule modification/ajout lors d'une mise a jour, sans avoir a tout re-controler
    (et sans risquer d'ecraser des modifications deja faites ailleurs dans le fichier).

    Le fichier doit deja exister dans la copie de travail (sinon utiliser
    copy_file_into_working pour importer le fichier en entier d'abord).

    Retourne (chemin_du_fichier, status, highlight) ou status vaut 'added', 'merged',
    ou 'conflict' (voir merge_single_block dans core.ecf.merge pour le detail).
    """
    dest = workspace.working_root / working_relative_path
    if not dest.exists():
        raise FileNotFoundError(
            f"Le fichier {dest} n'existe pas encore dans la copie de travail -- "
            f"importe d'abord le fichier entier avant de fusionner un bloc precis."
        )

    from .ecf.parser import parse_ecf_file
    from .ecf.merge import merge_single_block

    working_doc = parse_ecf_file(dest)
    status, info = merge_single_block(working_doc, block, source_label)

    with open(dest, 'w', encoding='utf-8', newline='') as f:
        f.write(working_doc.render())

    highlight = None
    if status == 'added':
        highlight = MergeHighlight(new_blocks={info}, changed_blocks={})
    elif status == 'merged':
        key, idents = info
        highlight = MergeHighlight(new_blocks=set(), changed_blocks={key: idents})

    return dest, status, highlight
