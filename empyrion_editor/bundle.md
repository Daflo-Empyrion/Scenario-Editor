# Bundle du projet

## Arborescence

```text
__init__.py
bundle.md
core\__init__.py
core\backup_manager.py
core\csv_handler.py
core\ecf\__init__.py
core\ecf\dependency_check.py
core\ecf\diff.py
core\ecf\disable_block.py
core\ecf\merge.py
core\ecf\model.py
core\ecf\parser.py
core\ecf\pending_conflicts.py
core\ecf\transform.py
core\ecf_header_glossary.py
core\file_handlers.py
core\fsutil.py
core\i18n.py
core\models.py
core\project_store.py
core\scanner.py
core\scenario_diff.py
core\settings.py
core\translation.py
core\workspace.py
core\workspace_undo.py
core\yaml_handler.py
core\yamllite\__init__.py
core\yamllite\model.py
core\yamllite\parser.py
detecter_imbrication_anormale.py
diagnostic_bloc.py
diff_ecf.py
docs\wiki_app.md
docs\wiki_app_en.md
docs\wiki_app_fr.md
docs\wiki_empyrion.md
docs\wiki_empyrion_en.md
docs\wiki_empyrion_fr.md
edit_ecf.py
gui\__init__.py
gui\backup_dialog.py
gui\csv_edit_widget.py
gui\ecf_edit_widget.py
gui\main_window.py
gui\new_project_dialog.py
gui\scenario_compare_dialog.py
gui\startup_dialog.py
gui\text_tools.py
gui\theme.py
gui\txt_edit_widget.py
gui\wiki_viewer.py
gui\yaml_edit_widget.py
merge_ecf.py
Qwen.py
requirements.txt
run_gui.py
test_ecf_roundtrip.py
test_scan.py
transform_ecf.py
verifier_parser_csv.py
verifier_parser_ecf.py
verifier_parser_yaml.py
```

## Fichiers

### __init__.py

```py

```

### bundle.md

```md

```

### core\__init__.py

```py

```

### core\backup_manager.py

```py
"""
Sauvegarde/restauration generique de dossiers complets -- utilise pour deux besoins :

  - 'scenario' : garder une copie de la version vanille d'un scenario juste avant une
    mise a jour (le Workshop Steam ecrase le dossier original en place a la mise a
    jour), pour pouvoir ensuite comparer l'ancienne et la nouvelle version avec la
    fonction de comparaison de scenarios.
  - 'savegame' : garder des copies de la progression de partie, avec restauration
    possible si une mise a jour de scenario casse la sauvegarde en cours.

Chaque sauvegarde est un dossier horodate contenant une copie integrale de la source,
plus un petit fichier _backup_info.json avec les metadonnees (source d'origine, date,
nom donne par l'utilisateur, type).
"""
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .fsutil import clear_readonly

INFO_FILENAME = "_backup_info.json"


@dataclass
class BackupRecord:
    backup_path: Path
    label: str
    source_path: str
    created_at: str  # ISO 8601
    kind: str  # 'scenario' | 'savegame'

    def content_path(self) -> Path:
        """Le contenu copie vit dans un sous-dossier 'content' -- evite toute ambiguite
        avec le fichier _backup_info.json lui-meme lors d'une restauration."""
        return self.backup_path / "content"

    def display_name(self) -> str:
        dt = self.created_at.replace("T", " ")[:19]
        return f"{self.label}  --  {dt}"


def _sanitize_label(label: str) -> str:
    safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in label)
    return safe.strip().replace(' ', '_')[:60] or "sauvegarde"


def create_backup(source: Path, backup_root: Path, label: Optional[str], kind: str) -> BackupRecord:
    """Copie integralement `source` dans un nouveau sous-dossier horodate de
    `backup_root`. Leve une exception si `source` n'existe pas."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"La source n'existe pas : {source}")

    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    ts_str = timestamp.strftime("%Y-%m-%d_%Hh%M")
    label = label.strip() if label and label.strip() else source.name
    folder_name = f"{ts_str}__{_sanitize_label(label)}"

    backup_path = backup_root / folder_name
    n = 1
    while backup_path.exists():
        n += 1
        backup_path = backup_root / f"{folder_name}_{n}"

    content_path = backup_path / "content"
    shutil.copytree(source, content_path)
    clear_readonly(content_path)

    record = BackupRecord(
        backup_path=backup_path,
        label=label,
        source_path=str(source),
        created_at=timestamp.isoformat(),
        kind=kind,
    )
    info = {
        'label': record.label,
        'source_path': record.source_path,
        'created_at': record.created_at,
        'kind': record.kind,
    }
    (backup_path / INFO_FILENAME).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')

    return record


def list_backups(backup_root: Path, kind: Optional[str] = None) -> List[BackupRecord]:
    """Liste les sauvegardes presentes dans `backup_root`, triees de la plus recente a
    la plus ancienne. Ignore silencieusement les sous-dossiers qui ne sont pas des
    sauvegardes valides (pas de _backup_info.json lisible)."""
    backup_root = Path(backup_root)
    if not backup_root.exists():
        return []

    records = []
    for entry in backup_root.iterdir():
        if not entry.is_dir():
            continue
        info_file = entry / INFO_FILENAME
        if not info_file.exists():
            continue
        try:
            info = json.loads(info_file.read_text(encoding='utf-8'))
            record = BackupRecord(
                backup_path=entry,
                label=info.get('label', entry.name),
                source_path=info.get('source_path', ''),
                created_at=info.get('created_at', ''),
                kind=info.get('kind', 'scenario'),
            )
            if kind is None or record.kind == kind:
                records.append(record)
        except Exception:
            continue

    records.sort(key=lambda r: r.created_at, reverse=True)
    return records


def restore_backup(record: BackupRecord, destination: Path,
                    safety_backup_root: Optional[Path] = None) -> Optional[BackupRecord]:
    """Restaure une sauvegarde vers `destination`, en REMPLACANT completement son
    contenu actuel (pas une fusion -- un vrai retour en arriere).

    Si `safety_backup_root` est fourni et que `destination` existe deja avec du
    contenu, une sauvegarde automatique de securite de l'etat ACTUEL est d'abord
    creee (label "avant restauration") avant tout ecrasement -- pour qu'une
    restauration accidentelle ne fasse jamais perdre de donnees de facon
    irreversible. Retourne cette sauvegarde de securite si elle a ete creee, sinon
    None.

    Cette fonction ne demande AUCUNE confirmation elle-meme -- c'est la responsabilite
    de l'appelant (interface graphique) de confirmer avec l'utilisateur avant d'appeler
    cette fonction, vu son caractere destructif.
    """
    destination = Path(destination)
    safety_record = None

    if destination.exists() and any(destination.iterdir()) and safety_backup_root:
        safety_record = create_backup(
            destination, Path(safety_backup_root),
            label=f"avant_restauration_{record.label}", kind=record.kind
        )

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(record.content_path(), destination)
    clear_readonly(destination)

    return safety_record


def delete_backup(record: BackupRecord) -> None:
    if record.backup_path.exists():
        clear_readonly(record.backup_path)  # au cas ou une sauvegarde anterieure a ce correctif soit verrouillee
        shutil.rmtree(record.backup_path)


def backup_size_bytes(record: BackupRecord) -> int:
    total = 0
    for p in record.content_path().rglob('*'):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"

```

### core\csv_handler.py

```py
"""
Handler CSV, pour l'edition des fichiers de traduction Empyrion (Localization.csv,
PDA.csv, Dialogues.csv...).

IMPORTANT -- contrairement au parser ECF (valide sur 240+ fichiers reels) et au parser
YAML (valide sur 561 fichiers reels), ce handler n'a pas encore ete teste sur un vrai
fichier CSV Empyrion. Il utilise le module 'csv' standard de Python, avec detection
automatique du delimiteur (virgule, point-virgule...) et du style de fin de ligne
(CRLF/LF). A VALIDER avec verifier_parser_csv.py sur tes vrais fichiers avant de lui
faire confiance pour de l'edition reelle -- meme demarche que pour l'ECF et le YAML.
"""
import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from .file_handlers import FileHandler


@dataclass
class CsvDocument:
    header: Optional[List[str]]
    rows: List[List[str]]
    delimiter: str = ","
    quotechar: str = '"'
    lineterminator: str = "\r\n"
    quoting: int = csv.QUOTE_MINIMAL


def _detect_lineterminator(raw_text: str) -> str:
    return "\r\n" if "\r\n" in raw_text else "\n"


def _detect_dialect(raw_text: str) -> csv.Dialect:
    sample = raw_text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        class _Default(csv.Dialect):
            delimiter = ','
            quotechar = '"'
            doublequote = True
            skipinitialspace = False
            lineterminator = '\r\n'
            quoting = csv.QUOTE_MINIMAL
        return _Default


def _detect_has_header(raw_text: str, dialect: csv.Dialect) -> bool:
    """Les fichiers CSV Empyrion (Localization.csv, PDA.csv, Dialogues.csv...) ont
    quasiment toujours une ligne d'en-tete (Key/EN/FR/DE...). L'heuristique de
    csv.Sniffer().has_header() s'est averee peu fiable sur de petits fichiers reels
    (rate des cas evidents) -- on suppose donc un en-tete present par defaut, ce qui
    correspond a la convention de ces fichiers."""
    return True


def parse_csv_text(raw_text: str) -> CsvDocument:
    lineterminator = _detect_lineterminator(raw_text)
    dialect = _detect_dialect(raw_text)
    has_header = _detect_has_header(raw_text, dialect)

    reader = csv.reader(io.StringIO(raw_text), dialect)
    all_rows = list(reader)
    if all_rows and all_rows[-1] == []:
        all_rows.pop()

    header = all_rows[0] if (has_header and all_rows) else None
    rows = all_rows[1:] if header is not None else all_rows

    return CsvDocument(
        header=header, rows=rows,
        delimiter=dialect.delimiter, quotechar=dialect.quotechar,
        lineterminator=lineterminator, quoting=dialect.quoting,
    )


def render_csv(doc: CsvDocument) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=doc.delimiter, quotechar=doc.quotechar,
                         lineterminator=doc.lineterminator, quoting=doc.quoting)
    if doc.header is not None:
        writer.writerow(doc.header)
    writer.writerows(doc.rows)
    return buf.getvalue()


class CsvHandler(FileHandler):
    extensions = ('.csv',)

    def load(self, path: Path) -> str:
        with open(path, 'rb') as f:
            raw = f.read()
        return raw.decode('utf-8-sig')

    def parse(self, raw: str) -> CsvDocument:
        return parse_csv_text(raw)

    def serialize(self, ast: CsvDocument) -> str:
        return render_csv(ast)


def merge_csv_documents(working_doc: CsvDocument, incoming_doc: CsvDocument) -> "Tuple[CsvDocument, List[str]]":
    """
    Fusionne deux documents CSV par cle (1ere colonne) : la copie de travail est
    TOUJOURS prioritaire -- une ligne dont la cle existe deja n'est jamais ecrasee,
    seules les CELLULES VIDES sont completees depuis la source (meme philosophie que
    la fusion ECF en mode 'properties'). Les lignes dont la cle est absente de la copie
    de travail sont ajoutees telles quelles.

    Retourne (document_fusionne, rapport_des_changements -- une ligne de texte par
    ligne ajoutee ou completee).
    """
    report: List[str] = []
    merged_rows = [list(row) for row in working_doc.rows]
    key_to_index = {row[0]: i for i, row in enumerate(merged_rows) if row}

    for inc_row in incoming_doc.rows:
        if not inc_row:
            continue
        key = inc_row[0]
        if key not in key_to_index:
            merged_rows.append(list(inc_row))
            key_to_index[key] = len(merged_rows) - 1
            report.append(f"+ {key} (nouvelle ligne)")
        else:
            idx = key_to_index[key]
            existing_row = merged_rows[idx]
            new_row = list(existing_row)
            changed_cols = []
            for c in range(max(len(existing_row), len(inc_row))):
                existing_val = existing_row[c] if c < len(existing_row) else ""
                inc_val = inc_row[c] if c < len(inc_row) else ""
                if not existing_val.strip() and inc_val.strip():
                    while len(new_row) <= c:
                        new_row.append("")
                    new_row[c] = inc_val
                    changed_cols.append(c)
            if changed_cols:
                merged_rows[idx] = new_row
                col_names = [working_doc.header[c] if working_doc.header and c < len(working_doc.header) else str(c)
                             for c in changed_cols]
                report.append(f"~ {key} (complete : {', '.join(col_names)})")

    merged_doc = CsvDocument(
        header=working_doc.header, rows=merged_rows,
        delimiter=working_doc.delimiter, quotechar=working_doc.quotechar,
        lineterminator=working_doc.lineterminator, quoting=working_doc.quoting,
    )
    return merged_doc, report


def merge_single_csv_row(working_doc: CsvDocument, row: List[str]) -> "Tuple[CsvDocument, str]":
    """Fusionne UNE SEULE ligne (par cle) dans un document CSV deja charge -- meme
    logique que merge_csv_documents (complete les cellules vides, jamais d'ecrasement).
    Retourne (document_modifie, statut) ou statut vaut 'added', 'merged', ou 'unchanged'."""
    if not row:
        return working_doc, 'unchanged'
    key = row[0]
    for i, existing_row in enumerate(working_doc.rows):
        if existing_row and existing_row[0] == key:
            new_row = list(existing_row)
            changed = False
            for c in range(max(len(existing_row), len(row))):
                existing_val = existing_row[c] if c < len(existing_row) else ""
                inc_val = row[c] if c < len(row) else ""
                if not existing_val.strip() and inc_val.strip():
                    while len(new_row) <= c:
                        new_row.append("")
                    new_row[c] = inc_val
                    changed = True
            if changed:
                working_doc.rows[i] = new_row
                return working_doc, 'merged'
            return working_doc, 'unchanged'
    working_doc.rows.append(list(row))
    return working_doc, 'added'

```

### core\ecf\__init__.py

```py

```

### core\ecf\dependency_check.py

```py
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

```

### core\ecf\diff.py

```py
"""
Diff structurel entre deux documents ECF (EcfDocument).

Principe : on ne compare pas ligne à ligne (ça n'aurait aucun sens vu que l'ordre des
blocs peut changer, ou qu'une ligne ajoutée décale tout le reste). On compare bloc par
bloc, en les appariant par identité :
  - Si un bloc a une propriété identifiante (Id, Name, ou Ref -- dans cet ordre de
    priorité), on apparie les blocs de même 'genre' (kind) par cette valeur.
  - Sinon (ex: 'Child Items', qui n'a pas d'identifiant propre), on apparie par position
    s'il y a le même nombre de blocs de ce genre à ce niveau, sinon on les traite comme
    ajoutés/supprimés au mieux.

Pour un couple de blocs appariés, on compare :
  - leurs propriétés directes (Cle: valeur), en aplatissant celles déclarées sur la
    ligne d'ouverture ET celles des lignes enfants
  - récursivement leurs sous-blocs, avec la même logique d'appariement

Le résultat est un arbre de BlockDiff, élagué pour ne garder que ce qui a changé
(un bloc identique dans ses moindres détails n'apparaît pas dans le résultat).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import EcfBlock, EcfDocument, EcfProperty, IDENTITY_KEYS, block_identity as _block_identity, property_lines, normalized_kind


@dataclass
class PropertyDiff:
    key: str
    value_a: Optional[str]   # None si absent du document A (= ajoutée dans B)
    value_b: Optional[str]   # None si absent du document B (= supprimée dans B)
    status: str              # 'added' | 'removed' | 'changed'


@dataclass
class BlockDiff:
    kind: str
    identity: Optional[str]           # valeur Id/Name/Ref, ou None
    status: str                       # 'added' | 'removed' | 'modified'
    property_diffs: List[PropertyDiff] = field(default_factory=list)
    child_diffs: List["BlockDiff"] = field(default_factory=list)
    block_a: Optional[EcfBlock] = None
    block_b: Optional[EcfBlock] = None

    def label(self) -> str:
        if self.identity:
            return f"{self.kind} [{self.identity}]"
        return self.kind

    def has_changes(self) -> bool:
        return bool(self.property_diffs) or bool(self.child_diffs) or self.status in ('added', 'removed')


def diff_documents(doc_a: EcfDocument, doc_b: EcfDocument) -> List[BlockDiff]:
    """Diff au niveau racine du document. Retourne uniquement les blocs qui ont changé
    (ajoutés, supprimés, ou modifiés quelque part dans leur sous-arbre)."""
    blocks_a = [n for n in doc_a.nodes if isinstance(n, EcfBlock)]
    blocks_b = [n for n in doc_b.nodes if isinstance(n, EcfBlock)]
    return diff_blocks(blocks_a, blocks_b)


def diff_blocks(blocks_a: List[EcfBlock], blocks_b: List[EcfBlock]) -> List[BlockDiff]:
    """Diff une liste de blocs (à un niveau donné, ex: tous les enfants directs d'un bloc
    parent, ou les blocs racine du document). Regroupe par 'kind' puis apparie."""
    results: List[BlockDiff] = []

    by_kind_a = _group_by_kind(blocks_a)
    by_kind_b = _group_by_kind(blocks_b)

    all_kinds = list(dict.fromkeys(list(by_kind_a.keys()) + list(by_kind_b.keys())))

    for kind in all_kinds:
        group_a = by_kind_a.get(kind, [])
        group_b = by_kind_b.get(kind, [])
        results.extend(_diff_block_group(kind, group_a, group_b))

    return results


def _group_by_kind(blocks: List[EcfBlock]) -> Dict[str, List[EcfBlock]]:
    groups: Dict[str, List[EcfBlock]] = {}
    for b in blocks:
        groups.setdefault(normalized_kind(b.kind), []).append(b)
    return groups


def _diff_block_group(kind: str, group_a: List[EcfBlock], group_b: List[EcfBlock]) -> List[BlockDiff]:
    results: List[BlockDiff] = []

    identities_a = {_block_identity(b): b for b in group_a}
    identities_b = {_block_identity(b): b for b in group_b}

    has_real_identities = any(k is not None for k in identities_a) or any(k is not None for k in identities_b)

    if has_real_identities:
        # Appariement par identité (Id/Name/Ref)
        all_ids = list(dict.fromkeys(
            [k for k in identities_a if k is not None] + [k for k in identities_b if k is not None]
        ))
        for ident in all_ids:
            a = identities_a.get(ident)
            b = identities_b.get(ident)
            results.extend(_diff_matched_pair(kind, ident, a, b))

        # Blocs sans identité du tout dans ce groupe (rare) -> appariement positionnel de secours
        none_a = [b for b in group_a if _block_identity(b) is None]
        none_b = [b for b in group_b if _block_identity(b) is None]
        results.extend(_diff_positional(kind, none_a, none_b))
    else:
        # Aucun bloc de ce genre n'a d'identifiant (ex: 'Child Items') -> appariement positionnel
        results.extend(_diff_positional(kind, group_a, group_b))

    return results


def _diff_positional(kind: str, group_a: List[EcfBlock], group_b: List[EcfBlock]) -> List[BlockDiff]:
    results = []
    n = max(len(group_a), len(group_b))
    for i in range(n):
        a = group_a[i] if i < len(group_a) else None
        b = group_b[i] if i < len(group_b) else None
        results.extend(_diff_matched_pair(kind, None, a, b))
    return results


def _diff_matched_pair(kind: str, identity: Optional[str],
                        a: Optional[EcfBlock], b: Optional[EcfBlock]) -> List[BlockDiff]:
    if a is None and b is not None:
        return [BlockDiff(kind=kind, identity=identity or _block_identity(b), status='added',
                           block_a=None, block_b=b)]
    if b is None and a is not None:
        return [BlockDiff(kind=kind, identity=identity or _block_identity(a), status='removed',
                           block_a=a, block_b=None)]
    if a is None and b is None:
        return []

    # Les deux existent -> diff des propriétés + recursion sur les sous-blocs
    prop_diffs = _diff_properties(a, b)
    child_diffs = diff_blocks(
        [c for c in a.children if isinstance(c, EcfBlock)],
        [c for c in b.children if isinstance(c, EcfBlock)],
    )

    if not prop_diffs and not child_diffs:
        return []  # bloc strictement identique -> pas de bruit dans le resultat

    return [BlockDiff(kind=kind, identity=identity or _block_identity(a), status='modified',
                       property_diffs=prop_diffs, child_diffs=child_diffs, block_a=a, block_b=b)]


def _format_pairs(pairs: List[Tuple[Optional[str], str]]) -> str:
    """Formate une ligne de propriété pour l'affichage, sans repeter la 1ere cle
    (deja utilisee comme identifiant de la ligne dans le diff)."""
    if not pairs:
        return ''
    _, first_v = pairs[0]
    rest = pairs[1:]
    s = first_v
    if rest:
        s += ", " + ", ".join(f"{k}: {v}" for k, v in rest)
    return s


def _diff_properties(a: EcfBlock, b: EcfBlock) -> List[PropertyDiff]:
    lines_a = property_lines(a)
    lines_b = property_lines(b)

    diffs = []
    all_idents = list(dict.fromkeys(list(lines_a.keys()) + list(lines_b.keys())))
    for ident in all_idents:
        pa = lines_a.get(ident)
        pb = lines_b.get(ident)
        if pa == pb:
            continue
        if pa is None:
            diffs.append(PropertyDiff(key=ident, value_a=None, value_b=_format_pairs(pb), status='added'))
        elif pb is None:
            diffs.append(PropertyDiff(key=ident, value_a=_format_pairs(pa), value_b=None, status='removed'))
        else:
            diffs.append(PropertyDiff(key=ident, value_a=_format_pairs(pa), value_b=_format_pairs(pb), status='changed'))
    return diffs


# ------------------------------------------------------------------
# Rendu texte lisible du resultat de diff
# ------------------------------------------------------------------

def format_diff(diffs: List[BlockDiff], indent: int = 0) -> str:
    from core.i18n import t
    lines = []
    pad = "  " * indent
    for d in diffs:
        if d.status == 'added':
            lines.append(f"{pad}+ {d.label()}  {t('diff.new')}")
        elif d.status == 'removed':
            lines.append(f"{pad}- {d.label()}  {t('diff.removed')}")
        else:
            lines.append(f"{pad}~ {d.label()}  {t('diff.modified')}")
            for pd in d.property_diffs:
                if pd.status == 'changed':
                    lines.append(f"{pad}    {pd.key}: {pd.value_a} -> {pd.value_b}")
                elif pd.status == 'added':
                    lines.append(f"{pad}    + {pd.key}: {pd.value_b}  {t('diff.new_property')}")
                elif pd.status == 'removed':
                    lines.append(f"{pad}    - {pd.key}: {pd.value_a}  {t('diff.removed_property')}")
            if d.child_diffs:
                lines.append(format_diff(d.child_diffs, indent + 2))
    return "\n".join(lines)


def summarize_diff(diffs: List[BlockDiff]) -> Dict[str, int]:
    """Compte recursivement le nombre de blocs ajoutes/supprimes/modifies dans tout l'arbre."""
    counts = {'added': 0, 'removed': 0, 'modified': 0}

    def _walk(items: List[BlockDiff]):
        for d in items:
            counts[d.status] += 1
            if d.child_diffs:
                _walk(d.child_diffs)

    _walk(diffs)
    return counts

```

### core\ecf\disable_block.py

```py
"""
Desactivation/reactivation manuelle d'un bloc, pour tester l'elimination de causes
probables lors d'un bug de lancement (ex: le jeu plante, on veut essayer sans tel
bloc precis sans le supprimer ni casser la structure du fichier).

Reutilise la meme convention de commentaire que le garde-fou anti-collision du merge
(core/ecf/merge.py) -- chaque ligne du bloc prefixee par '# ' -- mais avec son propre
marqueur d'en-tete pour ne pas se confondre avec un conflit d'Id.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from .model import EcfDocument, EcfBlock, EcfComment, EcfBlank
from .parser import parse_ecf_text

_HEADER_MARKER = "BLOC DESACTIVE (TEST)"


@dataclass
class DisabledBlock:
    header_index: int
    start_index: int
    end_index: int
    header_text: str
    block_text: str  # texte du bloc, '# ' deja retire, pret a re-parser
    label: str        # ex: "Block [1234]" -- pour affichage


def disable_block(doc: EcfDocument, block: EcfBlock, author: str) -> bool:
    """Commente le bloc donne, EXACTEMENT a sa position actuelle dans le fichier (ne
    le deplace jamais en fin de fichier -- important pour l'ordre de chargement).
    Retourne False si le bloc n'est pas trouve au niveau racine du document."""
    index = None
    for i, n in enumerate(doc.nodes):
        if n is block:
            index = i
            break
    if index is None:
        return False

    from .model import block_identity
    ident = block_identity(block)
    label = f"{block.kind} [{ident}]" if ident else block.kind

    header_text = (
        f"# {_HEADER_MARKER} -- {label} -- desactive par {author} pour tester "
        f"l'elimination des causes probables d'un bug. Decommenter (ou utiliser "
        f"'Reactiver' dans l'appli) pour le remettre.\r\n"
    )
    comment_nodes = [EcfComment(raw=header_text)]
    rendered = block.render()
    for line in rendered.splitlines(keepends=True):
        stripped = line.rstrip('\r\n')
        if stripped == '':
            comment_nodes.append(EcfComment(raw="#" + line[len(stripped):]))
        else:
            comment_nodes.append(EcfComment(raw="# " + line))

    doc.nodes[index:index + 1] = comment_nodes
    return True


def find_disabled_blocks(doc: EcfDocument) -> List[DisabledBlock]:
    """Trouve toutes les sequences de commentaires generees par disable_block()."""
    results = []
    nodes = doc.nodes
    i = 0
    n = len(nodes)
    while i < n:
        node = nodes[i]
        if isinstance(node, EcfComment) and _HEADER_MARKER in node.raw:
            header_idx = i
            # Extrait le label affiche depuis l'en-tete (entre les deux '--')
            m = re.search(r'--\s*(.+?)\s*--', node.raw)
            label = m.group(1) if m else "?"
            j = i + 1
            lines = []
            depth = 0
            started = False
            while j < n and isinstance(nodes[j], EcfComment):
                raw = nodes[j].raw
                if raw.startswith('# '):
                    uncommented = raw[2:]
                elif raw.startswith('#'):
                    uncommented = raw[1:]
                else:
                    break
                lines.append(uncommented)
                stripped = uncommented.strip()
                if stripped.startswith('{'):
                    depth += 1
                    started = True
                if stripped.endswith('}'):
                    depth -= 1
                j += 1
                if started and depth <= 0:
                    break
            if lines:
                results.append(DisabledBlock(
                    header_index=header_idx,
                    start_index=i + 1,
                    end_index=j - 1,
                    header_text=node.raw.strip(),
                    block_text="".join(lines),
                    label=label,
                ))
            i = j
        else:
            i += 1
    return results


def enable_disabled_block(doc: EcfDocument, disabled: DisabledBlock) -> bool:
    """Remplace la sequence de commentaires par le bloc reel reactive, EXACTEMENT a
    la meme position dans le fichier (important : preserve l'ordre de chargement)."""
    parsed = parse_ecf_text(disabled.block_text)
    new_blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    if len(new_blocks) != 1:
        return False

    doc.nodes[disabled.header_index:disabled.end_index + 1] = [new_blocks[0]]
    return True

```

### core\ecf\merge.py

```py
"""
Moteur de fusion (merge) entre plusieurs documents ECF, avec ordre de priorité.

Généralise le système de fusion à priorité (RE2/ATLnext/ATLcrew) développé
précédemment, en le rendant réutilisable sur n'importe quel fichier ECF.

Deux modes :

  - mode 'block' (par défaut, le plus sûr) : pour chaque identité de bloc (Id/Name/Ref),
    le bloc ENTIER provient de la source la plus prioritaire qui le possède. Pas de
    mélange de propriétés à l'intérieur d'un même bloc -- le résultat est toujours un
    bloc intact, tel qu'il existait dans une des sources.

  - mode 'properties' : fusion propriété par propriété (ligne par ligne). Pour chaque
    ligne (Count, Size, Name_0, Group_1...), la valeur provient de la source la plus
    prioritaire qui la définit, même si ce n'est pas la même source que pour les autres
    lignes du même bloc. Le bloc de base (structure, commentaires, ordre) est celui de
    la source la plus prioritaire qui possède ce bloc ; les propriétés manquantes chez
    elle mais présentes ailleurs sont ajoutées, copiées depuis leur source d'origine.
    Limite : les sous-blocs (ex: 'Child Items') finissent regroupés après toutes les
    propriétés simples dans le résultat fusionné, même si leur position d'origine était
    différente -- une légère réorganisation, sans impact sur le contenu.

Dans les deux cas, un rapport de fusion liste les identités présentes dans plusieurs
sources (donc "arbitrées" par la priorité), pour revue humaine avant application.
"""
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import EcfDocument, EcfBlock, EcfProperty, EcfComment, EcfBlank, block_identity, property_lines, normalized_kind


@dataclass
class MergeReportEntry:
    kind: str
    identity: Optional[str]
    sources_present: List[str]                       # labels des sources qui possedaient ce bloc
    winning_source: str                               # source dont vient le bloc (mode block) ou le bloc de base (mode properties)
    property_overrides: List[str] = field(default_factory=list)  # mode 'properties' seulement

    def label(self) -> str:
        return f"{self.kind} [{self.identity}]" if self.identity else self.kind


@dataclass
class IdConflict:
    """
    Cas dangereux : deux blocs partagent le meme (genre, identite) -- typiquement le
    meme Id -- mais leur propriete 'Name' differe, ce qui indique qu'il s'agit en
    realite de DEUX ELEMENTS DIFFERENTS qui se trouvent juste avoir le meme numero
    d'Id d'un scenario a l'autre (ex: Id 628 = 'InteriorBath' dans un scenario,
    'CPUExtenderLargeT5' dans un autre -- les Id de BlocksConfig.ecf ne sont PAS
    garantis coherents entre deux scenarios independants).

    Dans ce cas, on ne fusionne JAMAIS automatiquement (ce serait fusionner deux
    materiels differents entre eux, silencieusement). Le bloc de la source non
    prioritaire est ajoute au document en fin de fichier, mais DESACTIVE (commente),
    avec une note explicative -- a l'utilisateur de lui assigner un Id libre puis de
    le decommenter manuellement.
    """
    kind: str
    identity: str
    base_name: Optional[str]
    base_source: str
    conflicting_source: str
    conflicting_name: Optional[str]
    block: EcfBlock


@dataclass
class MergeResult:
    document: EcfDocument
    report: List[MergeReportEntry]
    id_conflicts: List[IdConflict] = field(default_factory=list)

    def conflicts(self) -> List[MergeReportEntry]:
        """Entrees ou plusieurs sources definissaient le meme bloc -- la priorite a du
        arbitrer, donc a revoir en premier lors d'un controle humain."""
        return [e for e in self.report if len(e.sources_present) > 1]


def _blocks_correspond(base_block: EcfBlock, other_block: EcfBlock) -> bool:
    """Verifie qu'un Id (ou autre identite) partage designe bien le MEME element
    materiel des deux cotes. On compare 'Name' ET plusieurs proprietes revelatrices
    de l'identite REELLE du bloc (CustomIcon, TemplateRoot, Model).

    Pourquoi pas 'Name' seul : les scenarios recyclent parfois un ancien Id/Name
    vanilla pour un objet completement different (ex: 'InteriorBath' garde son nom
    d'origine mais devient en realite un Quantum CPU via son CustomIcon/TemplateRoot).
    Deux blocs peuvent donc avoir exactement le meme 'Name' tout en etant des elements
    totalement differents -- il faut regarder plus loin que le nom affiche.

    Un mismatch sur N'IMPORTE LAQUELLE de ces cles (quand les deux blocs la definissent)
    suffit a declencher un conflit."""
    identity_keys = ('Name', 'CustomIcon', 'TemplateRoot', 'Model', 'IndexName')
    for key in identity_keys:
        val_a = base_block.get_property(key)
        val_b = other_block.get_property(key)
        if val_a is not None and val_b is not None and val_a != val_b:
            return False
    return True


def _make_pending_comment_nodes(conflict: IdConflict) -> List:
    """Transforme un bloc en conflit en une sequence de commentaires inertes (meme
    convention que les blocs deja desactives manuellement dans les fichiers Empyrion :
    '# { +Container Id: ...'), precedee d'une note expliquant le conflit."""
    header_text = (
        f"# CONFLIT D'ID {conflict.identity} ({conflict.kind}) : la copie de travail "
        f"utilise deja cet Id pour \"{conflict.base_name}\" (source: {conflict.base_source}), "
        f"mais {conflict.conflicting_source} l'utilise pour \"{conflict.conflicting_name}\". "
        f"Bloc DESACTIVE ci-dessous -- assigner un Id libre puis decommenter pour l'activer.\r\n"
    )
    nodes = [EcfBlank(raw="\r\n"), EcfComment(raw=header_text)]
    rendered = conflict.block.render()
    for line in rendered.splitlines(keepends=True):
        stripped = line.rstrip('\r\n')
        if stripped == '':
            nodes.append(EcfComment(raw="#" + line[len(stripped):]))
        else:
            nodes.append(EcfComment(raw="# " + line))
    return nodes


def merge_documents(sources: List[Tuple[str, EcfDocument]], mode: str = 'block') -> MergeResult:
    """
    sources : liste de (label, EcfDocument), dans l'ordre de PRIORITE DECROISSANTE
              (la premiere source de la liste gagne en cas de conflit).
    mode    : 'block' (par defaut) ou 'properties'.
    """
    if mode not in ('block', 'properties'):
        raise ValueError("mode doit etre 'block' ou 'properties'")
    if not sources:
        raise ValueError("au moins une source est requise")

    grouped: Dict[Tuple[str, Optional[str]], List[Tuple[str, EcfBlock]]] = {}
    order: List[Tuple[str, Optional[str]]] = []
    id_conflicts: List[IdConflict] = []

    for label, doc in sources:
        for node in doc.nodes:
            if not isinstance(node, EcfBlock):
                continue
            key = (normalized_kind(node.kind), block_identity(node))
            if key in grouped:
                base_label, base_block = grouped[key][0]
                if key[1] is not None and not _blocks_correspond(base_block, node):
                    id_conflicts.append(IdConflict(
                        kind=node.kind, identity=key[1],
                        base_name=base_block.get_property('Name'), base_source=base_label,
                        conflicting_source=label, conflicting_name=node.get_property('Name'),
                        block=node,
                    ))
                    continue
            else:
                grouped[key] = []
                order.append(key)
            grouped[key].append((label, node))

    merged_nodes = []
    report: List[MergeReportEntry] = []

    for key in order:
        kind, identity = key
        candidates = grouped[key]  # deja dans l'ordre de priorite (car sources iterees dans cet ordre)
        winning_label, winning_block = candidates[0]
        sources_present = [label for label, _ in candidates]

        if mode == 'block' or len(candidates) == 1:
            merged_block = copy.deepcopy(winning_block)
            entry = MergeReportEntry(kind=kind, identity=identity, sources_present=sources_present,
                                      winning_source=winning_label)
        else:
            merged_block, overrides = _merge_properties(candidates)
            entry = MergeReportEntry(kind=kind, identity=identity, sources_present=sources_present,
                                      winning_source=winning_label, property_overrides=overrides)

        merged_nodes.append(merged_block)
        report.append(entry)

    for conflict in id_conflicts:
        merged_nodes.extend(_make_pending_comment_nodes(conflict))

    merged_doc = EcfDocument(nodes=merged_nodes, source_path=None)
    return MergeResult(document=merged_doc, report=report, id_conflicts=id_conflicts)


def _merge_properties(candidates: List[Tuple[str, EcfBlock]]) -> Tuple[EcfBlock, List[str]]:
    """Fusionne les proprietes de plusieurs versions d'un meme bloc (mode 'properties').
    `candidates` est deja trie par priorite decroissante."""
    base_label, base_block = candidates[0]
    merged = copy.deepcopy(base_block)

    base_lines = property_lines(merged)
    overrides = []

    for label, block in candidates[1:]:
        other_lines = property_lines(block)
        for ident, pairs in other_lines.items():
            if ident in base_lines:
                continue  # une source plus prioritaire definit deja cette ligne
            _add_property_line(merged, pairs)
            base_lines[ident] = pairs
            overrides.append(f"{ident} (depuis {label})")

    # Fusionne aussi les sous-blocs (ex: Child Items), et les substitue dans merged.children
    # sans toucher aux lignes de propriete simples deja en place ci-dessus.
    merged_sub_blocks = _merge_child_blocks(candidates)
    merged.children = [c for c in merged.children if not isinstance(c, EcfBlock)] + merged_sub_blocks

    return merged, overrides


def _add_property_line(block: EcfBlock, pairs: List[Tuple[Optional[str], str]]) -> None:
    """Insere une nouvelle ligne de propriete (copiee depuis une autre source) dans un
    bloc. Placee avant le premier sous-bloc s'il y en a un, pour rester groupee avec les
    autres proprietes simples plutot qu'apres un bloc imbrique comme 'Child Items'."""
    indent = "  "
    for child in block.children:
        if isinstance(child, EcfProperty):
            indent = child.indent
            break
    new_prop = EcfProperty(raw="", indent=indent, pairs=list(pairs), comment=None, eol=block.eol, dirty=True)

    insert_at = len(block.children)
    for i, child in enumerate(block.children):
        if isinstance(child, EcfBlock):
            insert_at = i
            break
    block.children.insert(insert_at, new_prop)


def _merge_child_blocks(candidates: List[Tuple[str, EcfBlock]]) -> List[EcfBlock]:
    """Fusionne les sous-blocs (EcfBlock enfants directs) de plusieurs versions d'un
    bloc, par (kind, identite), avec la meme logique de priorite qu'au niveau racine."""
    grouped: Dict[Tuple[str, Optional[str]], List[Tuple[str, EcfBlock]]] = {}
    order: List[Tuple[str, Optional[str]]] = []

    for label, block in candidates:
        for child in block.children:
            if isinstance(child, EcfBlock):
                key = (child.kind, block_identity(child))
                if key not in grouped:
                    grouped[key] = []
                    order.append(key)
                grouped[key].append((label, child))

    merged_sub_blocks = []
    for key in order:
        subcandidates = grouped[key]
        if len(subcandidates) == 1:
            merged_sub_blocks.append(copy.deepcopy(subcandidates[0][1]))
        else:
            sub_merged, _ = _merge_properties(subcandidates)
            merged_sub_blocks.append(sub_merged)

    return merged_sub_blocks


# ------------------------------------------------------------------
# Rendu texte lisible du rapport de fusion
# ------------------------------------------------------------------

def format_report(result: MergeResult, show_all: bool = False) -> str:
    lines = []
    conflicts = result.conflicts()
    lines.append(f"Total : {len(result.report)} bloc(s) dans le resultat fusionne")
    lines.append(f"Dont {len(conflicts)} present(s) dans plusieurs sources (arbitres par la priorite)")
    if result.id_conflicts:
        lines.append(f"⚠ {len(result.id_conflicts)} CONFLIT(S) D'ID : Id partage entre deux elements "
                      f"DIFFERENTS -- ajoutes en fin de fichier, DESACTIVES (commentes), non fusionnes")
    lines.append("")

    entries = result.report if show_all else conflicts
    if not entries:
        lines.append("(aucun conflit de fusion -- toutes les identites de bloc n'apparaissaient que dans une seule source)")
    for e in entries:
        sources_str = " > ".join(e.sources_present)
        lines.append(f"  {e.label()} : {sources_str}  (gagnant: {e.winning_source})")
        for ov in e.property_overrides:
            lines.append(f"      + {ov}")

    if result.id_conflicts:
        lines.append("")
        lines.append("CONFLITS D'ID (a revoir manuellement) :")
        for c in result.id_conflicts:
            lines.append(f"  {c.kind} [{c.identity}] : \"{c.base_name}\" ({c.base_source}) "
                          f"vs \"{c.conflicting_name}\" ({c.conflicting_source}) -- bloc desactive en fin de fichier")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Fusion d'un seul bloc (sans toucher au reste du fichier)
# ------------------------------------------------------------------

def merge_single_block(working_doc: EcfDocument, incoming: EcfBlock,
                        source_label: str) -> Tuple[str, object]:
    """
    Fusionne UN SEUL bloc (venant d'une source) dans un document deja charge (la copie
    de travail), sans toucher au reste du fichier -- utile pour importer une seule
    modification/ajout lors d'une mise a jour, sans avoir a tout re-controler.

    Retourne (status, info) ou status vaut :
      'added'    : bloc absent de la copie de travail -> ajoute tel quel.
                   info = (kind, identite)
      'merged'   : bloc deja present et coherent (meme 'Name') -> complete avec les
                   proprietes manquantes. info = ((kind, identite), {cles ajoutees})
      'conflict' : meme identite mais 'Name' different (materiel different) -> PAS
                   fusionne, ajoute en fin de document sous forme de bloc desactive
                   (commente). info = l'IdConflict correspondant.
    """
    key = (normalized_kind(incoming.kind), block_identity(incoming))
    existing = None
    for node in working_doc.nodes:
        if isinstance(node, EcfBlock) and (normalized_kind(node.kind), block_identity(node)) == key:
            existing = node
            break

    if existing is None:
        working_doc.nodes.append(copy.deepcopy(incoming))
        return 'added', key

    if key[1] is not None and not _blocks_correspond(existing, incoming):
        conflict = IdConflict(
            kind=incoming.kind, identity=key[1],
            base_name=existing.get_property('Name'), base_source="copie de travail",
            conflicting_source=source_label, conflicting_name=incoming.get_property('Name'),
            block=incoming,
        )
        working_doc.nodes.extend(_make_pending_comment_nodes(conflict))
        return 'conflict', conflict

    merged_block, overrides = _merge_properties([("copie de travail", existing), (source_label, incoming)])
    idx = working_doc.nodes.index(existing)
    working_doc.nodes[idx] = merged_block
    idents = {ov.split(' (depuis')[0] for ov in overrides}
    return 'merged', (key, idents)

```

### core\ecf\model.py

```py
"""
Modèle AST (arbre syntaxique) pour les fichiers ECF d'Empyrion.

Principe de conception : chaque nœud garde son texte brut d'origine (raw), donc tant
qu'on ne modifie rien, la sérialisation reproduit le fichier à l'identique, byte pour
byte (commentaires, indentation, fins de ligne CRLF/LF, espacement -- tout est préservé).
Quand une valeur est modifiée, seule la ligne concernée est régénérée ; le reste du
fichier reste intact.

Un fichier ECF est une séquence de "nœuds" au niveau racine, où un nœud est :
  - EcfBlank    : une ligne vide
  - EcfComment  : une ligne de commentaire (# ou ##...), jamais interprétée comme structure,
                  même si elle contient des accolades (utile pour les blocs désactivés)
  - EcfProperty : une ligne "Cle: valeur[, Cle2: valeur2, ...]" avec commentaire de fin optionnel
  - EcfBlock    : un bloc "{ ... }" avec un "genre" (ex: "+Container", "Child Items"),
                  des propriétés déclarées sur la ligne d'ouverture, et des enfants
                  (récursivement les mêmes types de nœuds) jusqu'à la accolade fermante.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

# Cles utilisees pour identifier un bloc de maniere unique (dans cet ordre de priorite).
# Partagees entre le diff et l'editeur pour qu'un bloc soit toujours repere de la meme facon.
IDENTITY_KEYS = ('Id', 'Name', 'Ref')


@dataclass
class EcfBlank:
    raw: str  # ligne brute complète, avec sa fin de ligne d'origine

    def render(self) -> str:
        return self.raw


@dataclass
class EcfComment:
    raw: str  # ligne brute complète -- jamais réinterprétée, même si elle contient '{' ou '}'

    def render(self) -> str:
        return self.raw


@dataclass
class EcfProperty:
    """Une ligne du type 'Cle: valeur, Cle2: valeur2  # commentaire'."""
    raw: str                                  # texte d'origine complet (utilisé si non modifié)
    indent: str                               # espaces/tabs en début de ligne
    pairs: List[Tuple[Optional[str], str]]    # liste ordonnée de (cle, valeur_brute)
    comment: Optional[str]                    # commentaire de fin de ligne (avec son '#'), ou None
    eol: str                                  # fin de ligne d'origine ('\r\n' ou '\n')
    dirty: bool = False                       # True si modifié depuis le parsing -> à régénérer

    def get(self, key: str) -> Optional[str]:
        for k, v in self.pairs:
            if k == key:
                return v
        return None

    def set(self, key: str, new_value: str) -> bool:
        """Modifie la valeur d'une clé existante sur cette ligne. Retourne False si la clé n'existe pas."""
        for i, (k, v) in enumerate(self.pairs):
            if k == key:
                self.pairs[i] = (k, new_value)
                self.dirty = True
                return True
        return False

    def render(self) -> str:
        if not self.dirty:
            return self.raw
        body = ", ".join(f"{k}: {v}" if k is not None else v for k, v in self.pairs)
        line = self.indent + body
        if self.comment:
            line += "  " + self.comment
        return line + self.eol


@dataclass
class EcfBlock:
    """Un bloc '{ genre Cle: valeur, ... }' avec des enfants imbriqués."""
    indent: str
    kind: str                                 # ex: '+Container', 'Child Items', 'Container'
    pairs: List[Tuple[Optional[str], str]]    # propriétés déclarées sur la ligne d'ouverture
    comment: Optional[str]                    # commentaire de fin sur la ligne d'ouverture
    eol: str
    raw_open: str                             # ligne d'ouverture brute d'origine
    close_raw: str                            # ligne de fermeture '}' brute d'origine
    children: List["EcfNode"] = field(default_factory=list)
    dirty: bool = False

    def get(self, key: str) -> Optional[str]:
        """Cherche une propriété déclarée sur la ligne d'ouverture du bloc (ex: Id)."""
        for k, v in self.pairs:
            if k == key:
                return v
        return None

    def set(self, key: str, new_value: str) -> bool:
        for i, (k, v) in enumerate(self.pairs):
            if k == key:
                self.pairs[i] = (k, new_value)
                self.dirty = True
                return True
        return False

    def remove(self, key: str) -> bool:
        """Retire une propriete de la ligne d'ouverture du bloc (ex: pour dupliquer un
        bloc en abandonnant son Id, pour ne le laisser identifie que par Name)."""
        for i, (k, v) in enumerate(self.pairs):
            if k == key:
                del self.pairs[i]
                self.dirty = True
                return True
        return False

    def get_property(self, key: str) -> Optional[str]:
        """Cherche une propriété parmi les enfants directs (lignes EcfProperty) du bloc,
        et si absente, dans les propriétés déclarées sur la ligne d'ouverture."""
        for child in self.children:
            if isinstance(child, EcfProperty):
                val = child.get(key)
                if val is not None:
                    return val
        return self.get(key)

    def set_property(self, key: str, new_value: str) -> bool:
        """Modifie une propriété existante, qu'elle soit sur la ligne d'ouverture ou une ligne enfant."""
        for child in self.children:
            if isinstance(child, EcfProperty) and child.set(key, new_value):
                return True
        return self.set(key, new_value)

    def child_blocks(self, kind: Optional[str] = None) -> List["EcfBlock"]:
        """Sous-blocs directs, filtrés par genre si précisé (ex: 'Child Items')."""
        return [c for c in self.children if isinstance(c, EcfBlock) and (kind is None or c.kind == kind)]

    def summary_line(self, max_items: int = 3) -> str:
        """Résumé court et lisible du bloc (utilisé par l'éditeur en ligne de commande),
        ex: 'Count: "3,4", Size: "8,1", SfxOpen: UseActions/body_open'."""
        items = []
        for k, v in self.pairs:
            if k is not None and k not in IDENTITY_KEYS:
                items.append(f"{k}: {v}")
        for child in self.children:
            if len(items) >= max_items:
                break
            if isinstance(child, EcfProperty) and child.pairs:
                k, v = child.pairs[0]
                if k is not None:
                    items.append(f"{k}: {v}")
        return ", ".join(items[:max_items])

    def render_open(self) -> str:
        if not self.dirty:
            return self.raw_open
        body = ", ".join(f"{k}: {v}" if k is not None else v for k, v in self.pairs)
        line = f"{self.indent}{{ {self.kind}"
        if body:
            line += f" {body}"
        if self.comment:
            line += "  " + self.comment
        return line + self.eol

    def render(self) -> str:
        parts = [self.render_open()]
        for child in self.children:
            parts.append(child.render())
        parts.append(self.close_raw)
        return "".join(parts)


EcfNode = Union[EcfBlank, EcfComment, EcfProperty, EcfBlock]


def block_identity(block: EcfBlock) -> Optional[str]:
    """Identite d'un bloc, dans l'ordre de priorite IDENTITY_KEYS (Id, puis Name, puis Ref).
    Utilisee par le diff et l'editeur pour reperer un bloc de maniere stable."""
    for key in IDENTITY_KEYS:
        val = block.get(key)
        if val is not None:
            return val
    return None


def normalized_kind(kind: str) -> str:
    """Retire le prefixe '+'/'-' d'un genre de bloc pour les comparaisons d'identite.

    Empyrion utilise ce prefixe comme convention de PATCH/SURCHARGE : un meme Id peut
    apparaitre une fois comme '{ Block Id: 53...}' (definition de base) et une autre
    fois comme '{ +Block Id: 53...}' (patch qui le complete) -- c'est le MEME bloc
    conceptuellement, pas deux blocs differents. Sans cette normalisation, le merge et
    le diff les traitent a tort comme deux entites distinctes et en creent des doublons.
    """
    return kind.lstrip('+-').strip()


def add_property_line(block: EcfBlock, pairs: List[Tuple[Optional[str], str]]) -> EcfProperty:
    """Insere une nouvelle ligne de propriete dans un bloc (avant le premier sous-bloc
    s'il y en a un, pour rester groupee avec les autres proprietes simples, sinon a la
    fin). Retourne le noeud cree."""
    indent = "  "
    for child in block.children:
        if isinstance(child, EcfProperty):
            indent = child.indent
            break
    new_prop = EcfProperty(raw="", indent=indent, pairs=list(pairs), comment=None,
                            eol=block.eol or "\r\n", dirty=True)
    insert_at = len(block.children)
    for i, child in enumerate(block.children):
        if isinstance(child, EcfBlock):
            insert_at = i
            break
    block.children.insert(insert_at, new_prop)
    return new_prop


_ITEM_KEY_RE = re.compile(r'^(Name|Group)_(\d+)$')


def add_repeating_item_row(block: EcfBlock, item_type: str, first_value: str,
                            extra_pairs: List[Tuple[str, str]]) -> EcfProperty:
    """Ajoute une NOUVELLE ligne a une structure repetitive de type 'Child Items'
    (Name_0/Name_1/..., Group_0/Group_1/...) -- utilise par le mode tableau de
    l'interface. Calcule automatiquement le PROCHAIN NUMERO libre pour le type demande
    (Name ou Group) et insere la ligne juste APRES la derniere entree du MEME type
    (ou, a defaut, apres la derniere entree du type oppose, ou en dernier recours a la
    position habituelle de add_property_line) -- jamais a l'aveugle en toute fin de
    bloc, ce qui casserait la numerotation sequentielle et l'ordre attendu par le
    moteur du jeu (constate sensible a l'ordre pour ce genre de structure).

    `item_type` doit etre 'Name' ou 'Group'. Retourne le noeud cree."""
    same_type_max = -1
    same_type_last_index = -1
    other_type_last_index = -1
    last_prop_index = -1
    indent = "  "

    for i, child in enumerate(block.children):
        if not isinstance(child, EcfProperty):
            continue
        last_prop_index = i
        indent = child.indent
        if not child.pairs:
            continue
        m = _ITEM_KEY_RE.match(child.pairs[0][0] or "")
        if not m:
            continue
        if m.group(1) == item_type:
            same_type_max = max(same_type_max, int(m.group(2)))
            same_type_last_index = i
        else:
            other_type_last_index = i

    next_number = same_type_max + 1
    new_key = f"{item_type}_{next_number}"
    pairs = [(new_key, first_value)] + list(extra_pairs)
    new_prop = EcfProperty(raw="", indent=indent, pairs=pairs, comment=None,
                            eol=block.eol or "\r\n", dirty=True)

    if same_type_last_index >= 0:
        insert_at = same_type_last_index + 1
    elif other_type_last_index >= 0:
        insert_at = other_type_last_index + 1
    elif last_prop_index >= 0:
        insert_at = last_prop_index + 1
    else:
        insert_at = len(block.children)
        for i, child in enumerate(block.children):
            if isinstance(child, EcfBlock):
                insert_at = i
                break

    block.children.insert(insert_at, new_prop)
    return new_prop


def remove_property_line(block: EcfBlock, prop_node: EcfProperty) -> bool:
    """Supprime une ligne de propriete d'un bloc. Retourne False si elle n'y etait pas."""
    if prop_node in block.children:
        block.children.remove(prop_node)
        return True
    return False


def remove_block(nodes: List["EcfNode"], target: EcfBlock) -> bool:
    """Supprime un bloc (a n'importe quelle profondeur) d'une liste de noeuds.
    Retourne False si le bloc n'a pas ete trouve."""
    if target in nodes:
        nodes.remove(target)
        return True
    for node in nodes:
        if isinstance(node, EcfBlock):
            if remove_block(node.children, target):
                return True
    return False


def create_block(kind: str, pairs: List[Tuple[Optional[str], str]], eol: str = "\r\n") -> EcfBlock:
    """Cree un nouveau bloc de toutes pieces (pas encore attache a un document)."""
    return EcfBlock(indent="", kind=kind, pairs=list(pairs), comment=None, eol=eol,
                     raw_open="", close_raw=f"}}{eol}", children=[], dirty=True)


def annotate_property(prop: EcfProperty, note_text: str) -> None:
    """Ajoute une note de tracabilite en fin de ligne (ex: '# original: 100 -- Mod par
    Daflo'), sans ecraser un commentaire deja present sur cette ligne."""
    if prop.comment:
        prop.comment = prop.comment + "  " + note_text
    else:
        prop.comment = note_text
    prop.dirty = True


def duplicate_block(block: EcfBlock, overrides: Optional[dict] = None,
                     remove_keys: Optional[List[str]] = None) -> EcfBlock:
    """Copie profonde d'un bloc, avec certaines proprietes d'en-tete optionnellement
    remplacees (overrides, ex: {'Id': '700000'}) et/ou retirees (remove_keys, ex:
    ['Id'] pour dupliquer un bloc en l'identifiant desormais seulement par Name) --
    pour l'utiliser comme modele de depart pour un NOUVEL element distinct (pas une
    fusion : le bloc obtenu est independant de l'original, aucun lien conserve).

    Le genre est TOUJOURS normalise (+Block/-Block -> Block, +Item -> Item, etc.),
    meme si l'original etait un patch (+). Un bloc duplique porte par definition un
    nouvel Id/Name qui n'existe nulle part ailleurs -- le prefixe '+' n'a de sens que
    pour completer une entree deja existante (souvent une entree du jeu de base,
    invisible dans les fichiers texte). Le conserver ferait du duplicata un patch
    orphelin, ignore silencieusement par le jeu ou source de plantage (deja rencontre
    concretement : IdMapping/NullReferenceException sur un item duplique)."""
    import copy as _copy
    new_block = _copy.deepcopy(block)
    new_block.dirty = True
    new_block.kind = normalized_kind(new_block.kind)
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                new_block.set(key, value)
    if remove_keys:
        for key in remove_keys:
            new_block.remove(key)
    return new_block


@dataclass
class EcfDocument:
    nodes: List[EcfNode]
    source_path: Optional[str] = None

    def render(self) -> str:
        parts = []
        for n in self.nodes:
            text = n.render()
            # Garde-fou : si un noeud precedent (typiquement un commentaire de fin de
            # fichier sans retour a la ligne final, cas reel rencontre sur un fichier
            # vanille Empyrion) ne se termine pas par un saut de ligne, on en ajoute un
            # avant le noeud suivant -- sinon les deux se collent sur la meme ligne et
            # le fichier redevient illisible au re-parsing (ex: '# }{ Item Id: ...').
            if parts and parts[-1] and not parts[-1].endswith(('\n', '\r')):
                parts.append('\n')
            parts.append(text)
        return "".join(parts)

    def extract_header_comment(self) -> str:
        """Texte brut de TOUTES les lignes (commentaires, vides, ou meme mal
        classees a cause d'un BOM en tout debut de fichier) qui precedent le tout
        premier bloc/item reel -- typiquement la documentation technique en tete des
        fichiers ECF officiels (BlocksConfig.ecf en particulier). Retire le '#' de
        debut de chaque ligne commentaire pour un affichage plus lisible."""
        lines = []
        for node in self.nodes:
            if isinstance(node, EcfBlock):
                break
            raw = getattr(node, 'raw', None)
            if raw is None:
                continue
            # Retire un BOM eventuel en tout debut de fichier (premiere ligne)
            raw = raw.lstrip('\ufeff')
            stripped = raw.strip('\r\n')
            if stripped.startswith('#'):
                cleaned = stripped.lstrip('#').strip()
                lines.append(cleaned)
            elif stripped == '':
                lines.append('')
        # Retire les lignes vides en trop (plus de 2 consecutives) pour un affichage
        # plus compact
        result = []
        blank_run = 0
        for l in lines:
            if l == '':
                blank_run += 1
                if blank_run > 1:
                    continue
            else:
                blank_run = 0
            result.append(l)
        return "\n".join(result).strip('\n')

    def scan_section_groups_and_labels(self):
        """Detecte deux motifs de documentation courants dans les vrais fichiers ECF :

        1. Groupe de section : trois commentaires consecutifs a un seul '#' formant
           'separateur / titre / separateur' (ex: lignes de '='), qui introduisent une
           categorie visuelle regroupant tous les blocs suivants jusqu'au prochain
           groupe (ou la fin du fichier). Exemple reel (Containers.ecf) :
               # ==================================================================
               # Gigas
               # ==================================================================

        2. Etiquette de bloc : un commentaire a DOUBLE '#' ('##') place juste avant un
           bloc (lignes vides tolerees entre les deux), qui lui donne un nom lisible
           complementaire a son Id/Name technique. Exemple reel :
               ## GolemSwamp
               { +Container Id: 5

        Retourne (group_before_index: {index dans self.nodes: titre du groupe},
                  label_by_block_id: {id(bloc): etiquette}) -- utilise l'id Python du
        bloc comme cle plutot que le bloc lui-meme pour rester utilisable meme si le
        bloc n'est pas hashable de facon fiable."""
        def _clean(raw: str) -> str:
            return raw.strip('\r\n').lstrip('#').strip()

        def _is_separator(text: str) -> bool:
            s = text.strip()
            return len(s) >= 5 and len(set(s)) == 1 and s[0] in '=-*'

        nodes = self.nodes
        group_before = {}
        label_by_block_id = {}
        i, n = 0, len(nodes)
        while i < n:
            node = nodes[i]
            is_plain_comment = isinstance(node, EcfComment) and not node.raw.lstrip().startswith('##')
            if (is_plain_comment and _is_separator(_clean(node.raw)) and i + 2 < n
                    and isinstance(nodes[i + 1], EcfComment)
                    and not nodes[i + 1].raw.lstrip().startswith('##')
                    and not _is_separator(_clean(nodes[i + 1].raw))
                    and isinstance(nodes[i + 2], EcfComment)
                    and not nodes[i + 2].raw.lstrip().startswith('##')
                    and _is_separator(_clean(nodes[i + 2].raw))):
                group_before[i] = _clean(nodes[i + 1].raw)
                i += 3
                continue
            if (isinstance(node, EcfComment) and node.raw.lstrip().startswith('##')
                    and not _is_separator(_clean(node.raw))):
                j = i + 1
                while j < n and isinstance(nodes[j], EcfBlank):
                    j += 1
                if j < n and isinstance(nodes[j], EcfBlock):
                    label_by_block_id[id(nodes[j])] = _clean(node.raw)
            i += 1
        return group_before, label_by_block_id

    def iter_blocks(self, kind: Optional[str] = None):
        """Parcourt récursivement tous les blocs du document, filtrés par genre si précisé."""
        def _walk(nodes):
            for n in nodes:
                if isinstance(n, EcfBlock):
                    if kind is None or n.kind == kind:
                        yield n
                    yield from _walk(n.children)
        yield from _walk(self.nodes)

    def find_block(self, kind: str, key: str, value: str) -> Optional[EcfBlock]:
        """Trouve le premier bloc d'un genre donné dont la propriété `key` vaut `value`.
        Ex: find_block('+Container', 'Id', '5')."""
        for block in self.iter_blocks(kind):
            if block.get(key) == value:
                return block
        return None

    def find_block_by_identity(self, kind: str, identity: str) -> Optional[EcfBlock]:
        """Trouve le premier bloc d'un genre donné par son identite (Id, ou a defaut Name/Ref).
        Ex: find_block_by_identity('+Container', '5')."""
        for block in self.iter_blocks(kind):
            if block_identity(block) == identity:
                return block
        return None

    def top_level_kinds(self) -> List[Tuple[str, int]]:
        """Liste les genres de blocs presents au niveau racine, avec leur nombre
        d'occurrences -- utile pour explorer un fichier ECF inconnu."""
        counts: dict = {}
        for n in self.nodes:
            if isinstance(n, EcfBlock):
                counts[n.kind] = counts.get(n.kind, 0) + 1
        return list(counts.items())


def property_lines(block: EcfBlock) -> "dict[str, List[Tuple[Optional[str], str]]]":
    """
    Regroupe les propriétés directes d'un bloc par IDENTITE DE LIGNE (sa première clé,
    ex: 'Count', 'Name_0', 'Group_1'), et non par clé simple -- voir la docstring de
    EcfProperty pour la raison (une clé comme 'param1' se répète sur plusieurs lignes
    sœurs Name_0/Name_1/..., il faut comparer/fusionner ligne entière par ligne entière).

    Inclut aussi les paires déclarées sur la ligne d'ouverture du bloc (Id, etc.).
    Partagée entre le diff et le merge.
    """
    lines: "dict[str, List[Tuple[Optional[str], str]]]" = {}
    for k, v in block.pairs:
        if k is not None:
            lines[k] = [(k, v)]
    for child in block.children:
        if isinstance(child, EcfProperty) and child.pairs:
            first_key = child.pairs[0][0]
            ident = first_key if first_key is not None else f"_ligne_{id(child)}"
            lines[ident] = child.pairs
    return lines

```

### core\ecf\parser.py

```py
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

```

### core\ecf\pending_conflicts.py

```py
"""
Detection et activation des "blocs en attente" -- ceux ajoutes en fin de fichier,
desactives (commentes), par le garde-fou anti-collision d'Id du merge (voir
core/ecf/merge.py, IdConflict). Permet de les reactiver DEPUIS L'APPLI avec un nouvel
Id, sans jamais avoir a editer le fichier a la main dans un editeur externe -- ce qui
evite une source d'erreur reelle (ex: decommenter le bloc mais oublier la '}' de
fermeture, ce qui casse la structure du reste du fichier).
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from .model import EcfDocument, EcfBlock, EcfComment, EcfBlank
from .parser import parse_ecf_text

_HEADER_MARKER = "CONFLIT D'ID"


@dataclass
class PendingConflict:
    header_index: int    # index dans doc.nodes du commentaire d'en-tete explicatif
    start_index: int      # premier index du bloc commente lui-meme
    end_index: int         # dernier index (inclusif) du bloc commente
    header_text: str
    block_text: str        # texte du bloc, '# ' deja retire, pret a re-parser


def find_pending_conflicts(doc: EcfDocument) -> List[PendingConflict]:
    """Trouve toutes les sequences de commentaires generees par le garde-fou
    anti-collision du merge (reperables par leur en-tete '# CONFLIT D'ID ...')."""
    results = []
    nodes = doc.nodes
    i = 0
    n = len(nodes)
    while i < n:
        node = nodes[i]
        if isinstance(node, EcfComment) and _HEADER_MARKER in node.raw:
            header_idx = i
            j = i + 1
            lines = []
            depth = 0
            started = False
            while j < n and isinstance(nodes[j], EcfComment):
                raw = nodes[j].raw
                if raw.startswith('# '):
                    uncommented = raw[2:]
                elif raw.startswith('#'):
                    uncommented = raw[1:]
                else:
                    break
                lines.append(uncommented)
                stripped = uncommented.strip()
                if stripped.startswith('{'):
                    depth += 1
                    started = True
                if stripped.endswith('}'):
                    depth -= 1
                j += 1
                if started and depth <= 0:
                    break
            if lines:
                results.append(PendingConflict(
                    header_index=header_idx,
                    start_index=i + 1,
                    end_index=j - 1,
                    header_text=node.raw.strip(),
                    block_text="".join(lines),
                ))
            i = j
        else:
            i += 1
    return results


def parse_pending_block(conflict: "PendingConflict") -> Optional[EcfBlock]:
    """Reparse le texte d'un bloc en attente (deja decommenter en memoire) pour
    l'inspecter -- SANS toucher au document d'origine ni changer son Id. Utile pour
    afficher son contenu avant de decider de l'activer."""
    parsed = parse_ecf_text(conflict.block_text)
    blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    return blocks[0] if len(blocks) == 1 else None


def find_used_ids(ecf_files: List) -> set:
    """Recense tous les Id numeriques utilises dans une liste de fichiers ECF (tous
    genres de blocs confondus) -- pour pouvoir suggerer des Id libres."""
    used = set()
    for path in ecf_files:
        try:
            doc = parse_ecf_text(open(path, 'r', encoding='utf-8', newline='').read())
        except Exception:
            continue
        for block in doc.iter_blocks():
            val = block.get('Id')
            if val and val.strip().lstrip('-').isdigit():
                used.add(int(val))
    return used


def suggest_free_ids(used_ids: set, count: int = 10) -> List[int]:
    """Propose `count` Id libres, au-dessus du maximum actuellement utilise -- la
    zone la plus sure pour ne rentrer en collision avec rien d'existant (scenario
    comme vanilla). Le mod lui-meme peut avoir ses propres conventions de plage
    d'Id -- ceci est une suggestion de depart, pas une regle absolue."""
    if not used_ids:
        return list(range(1, count + 1))
    start = max(used_ids) + 1
    return list(range(start, start + count))


def activate_pending_conflict(doc: EcfDocument, conflict: PendingConflict, new_id: str) -> bool:
    """Remplace la sequence de commentaires par un VRAI bloc actif, avec le nouvel Id
    fourni. Retourne False si le remplacement de l'Id n'a pas pu se faire."""
    new_text = re.sub(r'(Id:\s*)[^\s,]+', r'\g<1>' + new_id, conflict.block_text, count=1)
    if new_text == conflict.block_text:
        return False

    parsed = parse_ecf_text(new_text)
    new_blocks = [n for n in parsed.nodes if isinstance(n, EcfBlock)]
    if len(new_blocks) != 1:
        return False

    new_block = new_blocks[0]

    del doc.nodes[conflict.header_index:conflict.end_index + 1]
    doc.nodes.insert(conflict.header_index, new_block)
    return True

```

### core\ecf\transform.py

```py
"""
Moteur de transformations en masse sur un document ECF.

Principe : on cible une CLE de propriete (ex: 'Count', 'param1', 'Health'), on filtre
les blocs concernes (par genre, et eventuellement par liste d'identites precises), et
on applique une operation numerique a toutes les valeurs trouvees pour cette cle --
que ce soit une propriete simple de bloc ('Count: "3,4"') ou une sous-cle repetee dans
des lignes de type liste ('Name_0: X, param1: 0.3, param2: "1,2"').

Les valeurs peuvent etre :
  - un nombre simple, quote ou non : "0.5" ou 0.5
  - une plage min,max, quotee ou non : "3,6"
Dans le cas d'une plage, l'operation s'applique aux DEUX bornes.

Par defaut, la recherche est recursive (elle descend aussi dans les sous-blocs comme
'Child Items'). Les proprietes declarees sur la ligne d'ouverture d'un bloc (Id, etc.)
ne sont jamais ciblees, pour ne jamais toucher accidentellement a un identifiant.
"""
import copy
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .model import EcfDocument, EcfBlock, EcfProperty, block_identity


@dataclass
class TransformRule:
    property_key: str                       # ex: 'param1', 'Count', 'Health'
    operation: str                          # 'multiply' | 'add' | 'set' | 'clamp' | 'round'
    amount: Optional[float] = None          # pour multiply / add / set
    min_value: Optional[float] = None       # pour clamp
    max_value: Optional[float] = None       # pour clamp
    ndigits: int = 2                        # pour round
    block_kind: Optional[str] = None        # None = tous les genres de blocs
    block_ids: Optional[List[str]] = None   # None = tous les blocs de ce genre
    recursive: bool = True                  # chercher aussi dans les sous-blocs (ex: Child Items)


@dataclass
class TransformChange:
    block_kind: str
    block_identity: Optional[str]
    old_value: str
    new_value: str


@dataclass
class TransformReport:
    changes: List[TransformChange] = field(default_factory=list)
    skipped_non_numeric: int = 0  # valeurs trouvees mais non numeriques -> ignorees, jamais modifiees


def apply_transform(doc: EcfDocument, rule: TransformRule) -> TransformReport:
    report = TransformReport()

    for block in doc.iter_blocks(rule.block_kind):
        if rule.block_ids is not None:
            ident = block_identity(block)
            if ident not in rule.block_ids:
                continue

        matches = _find_matching_pairs(block, rule.property_key, rule.recursive)
        for prop_node, pair_index in matches:
            key, old_value = prop_node.pairs[pair_index]
            new_value, ok = _apply_operation(old_value, rule)
            if not ok:
                report.skipped_non_numeric += 1
                continue
            if new_value == old_value:
                continue
            prop_node.pairs[pair_index] = (key, new_value)
            prop_node.dirty = True
            report.changes.append(TransformChange(
                block_kind=block.kind,
                block_identity=block_identity(block),
                old_value=old_value,
                new_value=new_value,
            ))

    return report


def _find_matching_pairs(block: EcfBlock, key: str, recursive: bool) -> List[Tuple[EcfProperty, int]]:
    """Trouve toutes les paires (nœud propriété, index de la paire) dont la clé
    correspond, parmi les lignes de propriété directes du bloc (jamais l'en-tête)."""
    matches = []
    for child in block.children:
        if isinstance(child, EcfProperty):
            for i, (k, v) in enumerate(child.pairs):
                if k == key:
                    matches.append((child, i))
        elif isinstance(child, EcfBlock) and recursive:
            matches.extend(_find_matching_pairs(child, key, recursive))
    return matches


# ------------------------------------------------------------------
# Parsing / formatage numerique (gere les plages "min,max" et le quotage)
# ------------------------------------------------------------------

_NUMBER_RE = re.compile(r'^-?\d+(\.\d+)?$')


def _parse_numbers(value_str: str) -> Optional[Tuple[List[float], bool]]:
    quoted = value_str.startswith('"') and value_str.endswith('"') and len(value_str) >= 2
    inner = value_str[1:-1] if quoted else value_str
    parts = [p.strip() for p in inner.split(',')]
    if not parts or not all(_NUMBER_RE.match(p) for p in parts):
        return None
    return [float(p) for p in parts], quoted


def _format_number(x: float) -> str:
    if x == int(x):
        return str(int(x))
    s = f"{x:.4f}".rstrip('0').rstrip('.')
    return s


def _format_numbers(nums: List[float], quoted: bool) -> str:
    s = ",".join(_format_number(n) for n in nums)
    return f'"{s}"' if quoted else s


def _apply_operation(value_str: str, rule: TransformRule) -> Tuple[str, bool]:
    parsed = _parse_numbers(value_str)
    if parsed is None:
        return value_str, False
    nums, quoted = parsed

    new_nums = []
    for n in nums:
        if rule.operation == 'multiply':
            n = n * rule.amount
        elif rule.operation == 'add':
            n = n + rule.amount
        elif rule.operation == 'set':
            n = rule.amount
        elif rule.operation == 'clamp':
            lo = rule.min_value if rule.min_value is not None else n
            hi = rule.max_value if rule.max_value is not None else n
            n = max(lo, min(hi, n))
        elif rule.operation == 'round':
            n = round(n, rule.ndigits)
        else:
            raise ValueError(f"Operation inconnue : {rule.operation}")
        new_nums.append(n)

    return _format_numbers(new_nums, quoted), True


def format_report(report: TransformReport, max_lines: int = 50) -> str:
    lines = [f"{len(report.changes)} valeur(s) modifiee(s)"]
    if report.skipped_non_numeric:
        lines.append(f"{report.skipped_non_numeric} valeur(s) trouvee(s) mais non numerique(s) -> ignoree(s)")
    lines.append("")
    for c in report.changes[:max_lines]:
        label = f"{c.block_kind} [{c.block_identity}]" if c.block_identity else c.block_kind
        lines.append(f"  {label} : {c.old_value} -> {c.new_value}")
    if len(report.changes) > max_lines:
        lines.append(f"  ... et {len(report.changes) - max_lines} autre(s)")
    return "\n".join(lines)

```

### core\ecf_header_glossary.py

```py
"""
Glossaire clarifie (en francais) des commentaires d'en-tete techniques trouves au debut
des fichiers ECF (BlocksConfig.ecf en particulier -- le plus dense). Ce n'est PAS une
traduction mot a mot : le texte original est souvent tres technique/condense, donc
chaque entree est reformulee pour rester claire, tout en gardant le sens exact.

Organise en sections (categorie -> liste de (terme, explication)) dans le meme ordre
que l'en-tete original, pour rester facile a comparer avec le fichier source.
"""

BLOCKS_CONFIG_GLOSSARY = [
    ("Identifiants (Id)", [
        ("Id 0 a 255", "Reserves au terrain (sol, roches...). Ne jamais reutiliser ces "
                        "numeros pour autre chose."),
        ("Id jusqu'a 2048", "Les blocs identifies par un numero (Id) doivent rester "
                             "sous cette limite."),
        ("Au-dela de 2048", "Pour ajouter un bloc au-dela de cette limite, ne mets pas "
                             "de Id du tout -- utilise seulement 'Block Name: MonBloc' "
                             "(identifie par son nom, pas par un numero)."),
    ]),
    ("Masse des blocs", [
        ("Regle generale", "La masse indiquee correspond a un bloc de 1 metre. Le jeu "
                            "l'ajuste ensuite automatiquement selon la taille reelle du "
                            "bloc :"),
        ("Petite grille (HV, SV)", "Masse reelle = valeur indiquee x 0.125 (bloc de 0.5m)"),
        ("Grande grille (BA, CV)", "Masse reelle = valeur indiquee x 8 (bloc de 2m)"),
    ]),
    ("Proprietes courantes", [
        ("AllowPlacingAt", "Sur quels types de structure ce bloc peut etre pose "
                            "(Base, MS, SS, GV, Terrain)."),
        ("Collide", "Quels types d'objets entrent en collision avec ce bloc "
                     "(mouvement, balles, roquettes, corps a corps, visee). Retirer "
                     "'movement' par exemple rend le bloc traversable a pied tout en "
                     "restant touchable par les armes."),
        ("EnergyIn / EnergyOut", "Consommation/production d'energie, exprimee en kW."),
        ("Texture", "Liste de 6 numeros de texture, dans l'ordre : dessus, dessous, "
                     "nord, sud, ouest, est."),
    ]),
    ("Codes d'explosion", [
        ("1", "Grande explosion aerienne"),
        ("2 a 4", "Petite explosion au sol"),
        ("5 a 6", "Petite explosion aerienne"),
        ("7", "Explosion electrique"),
        ("8 a 9", "Grande explosion aerienne"),
        ("10", "Explosion electrique"),
    ]),
    ("La regle du Ref (heritage)", [
        ("Regle d'ordre", "Un bloc ne peut heriter (Ref) que d'un bloc DEJA DEFINI PLUS "
                           "HAUT dans le fichier (Id ou position plus petite) -- jamais "
                           "d'un bloc plus bas."),
    ]),
    ("Proprietes avancees", [
        ("CustomIcon", "Reutilise une icone deja existante pour l'affichage en jeu "
                        "(ex: 'CustomIcon: DetectorSVT1')."),
        ("PickupTarget", "Objet qui sera automatiquement place dans l'inventaire du "
                          "joueur quand il ramasse ce bloc/appareil. Ne fonctionne que "
                          "sur le bloc PARENT, jamais sur un sous-bloc ('child')."),
        ("TemplateRoot", "Indique quelle recette de craft (Templates.ecf) utiliser pour "
                          "ce sous-groupe -- utile pour la fonction MISE A NIVEAU "
                          "(Upgrade). Le bloc parent n'en a pas besoin (il utilise "
                          "toujours la recette portant son propre nom). ATTENTION : ne "
                          "jamais faire un Ref vers un bloc qui EST lui-meme la cible de "
                          "TemplateRoot dans la meme entree -- ca fait planter la "
                          "bibliotheque de blueprints."),
        ("UpgradeTo", "Definit vers quel bloc/appareil ce bloc se transforme en cas de "
                       "mise a niveau. Si tu mets ca sur un sous-groupe, ce sous-groupe "
                       "a besoin de son propre TemplateRoot, sinon la mise a niveau sera "
                       "gratuite (bug). Peut valoir 'null' pour eviter une boucle."),
        ("DowngradeTo", "Meme principe que UpgradeTo, mais dans l'autre sens (retour "
                         "en arriere)."),
        ("Place: NoRotation", "Le bloc ne peut pas etre tourne a la pose."),
        ("Place: Face", "Le bloc s'oriente automatiquement selon la surface visee "
                         "(collé/oriente correctement), mais seule la rotation autour "
                         "d'un axe est possible."),
        ("Place: Free", "Pose libre, toutes rotations possibles, mais sans "
                         "l'alignement automatique (moins pratique, demande souvent "
                         "des rotations manuelles)."),
        ("RemoveOnSI", "Si actif (true), ce bloc disparait immediatement quand la "
                        "structure s'effondre (perte d'integrite)."),
        ("IsPhysicsColliders", "Active/desactive les collisions physiques fines "
                                "(desactive parfois sur les rampes trop fines)."),
        ("OccupySizeInBlocks", "Le bloc occupe tout son volume declare meme s'il n'est "
                                "pas 'voxelise' (utile pour des blocs avec animation ou "
                                "shader special)."),
        ("BlockSizeScale", "2 pour SV/HV, 8 pour CV/BA -- sert a mettre a l'echelle la "
                            "masse et les points de vie selon le nombre de voxels."),
        ("Voxelize", "Determine si le bloc est decoupe en petits cubes plutot que "
                      "d'occuper tout un voxel d'un coup (true par defaut)."),
        ("IsActivateable", "Le bloc peut etre allume/eteint par le joueur."),
        ("IsActivateableInCP", "Accessible via le Panneau de Controle (tourelle, "
                                "reservoir, coffre...)."),
        ("IsActivatedOnPlace", "Le bloc est deja allume des qu'il est pose."),
        ("IsDuplicateable", "Le bloc peut etre utilise avec les outils de dessin en "
                             "plan/ligne."),
        ("ForceMaxCount", "Force la limite MaxCount meme si le niveau de difficulte "
                           "l'avait desactivee (utile pour le Core, le Warp Drive... "
                           "mais pas pour les armes)."),
        ("IsAntiInfantryWeapon", "Les degats/PV de cet appareil ne comptent que face a "
                                  "l'infanterie et aux entites, pas face a l'artillerie."),
        ("IsKeepContainers", "Reserve aux Cores (PNJ uniquement) : le contenu preplace "
                              "est sauvegarde avec le blueprint et devient du butin."),
        ("VolumeCapacity", "Capacite du conteneur, en litres (SU)."),
        ("ShieldMultiplier", "Uniquement pour Class:ShieldGenerator -- un texte libre "
                              "utilisable dans le DamageMultiplier d'une arme "
                              "(ItemsConfig.ecf)."),
        ("RepairToTemplate", "Mettre a false pour exclure un bloc special/rare de la "
                              "reparation automatique via la recette (evite des abus)."),
        ("DropOnDeath", "Mettre a 'False' pour qu'un objet important d'histoire ne soit "
                         "jamais perdu a la mort du joueur (vrai par defaut)."),
        ("RepFac", "Multiplicateur de reputation gagnee/perdue en detruisant ce bloc "
                    "(ex: 0.1 pour reduire l'impact)."),
        ("DropMeshfile", "Modele 3D du sac/conteneur affiche au sol quand ce bloc est "
                          "lache (variantes: petit, grand, evenement...)."),
        ("DropInventoryEntity", "Quelle variante de conteneur apparait quand un "
                                 "conteneur de butin est detruit."),
        ("ShieldHitCooldown", "Delai en secondes avant que le bouclier ne recommence a "
                               "se recharger apres un coup (5s par defaut)."),
    ]),
    ("Dialogues (special)", [
        ("ExecuteOnActivate", "Declenche un etat de dialogue (Dialogues.ecf) quand le "
                               "joueur regarde le bloc et appuie sur F."),
        ("ExecuteOnCollide", "Meme chose, mais en touchant/poussant contre le bloc "
                              "plutot qu'en appuyant sur F."),
        ("DialogueSingleUserAccess", "Un seul joueur a la fois peut interagir avec ce "
                                      "dialogue."),
        ("DialogueState", "Force un dialogue precis ; permet aussi de placer ce bloc "
                           "sur une base appartenant a un joueur (declenchable via F)."),
        ("OmitCone", "Cache le cone jaune de dialogue au-dessus du PNJ (utile si le "
                      "PNJ ne fait qu'aboyer sans vraie interaction)."),
    ]),
    ("Competences (special)", [
        ("Player.Skills[...]", "Utilise dans Dialogues.ecf pour definir une entree de "
                                "competence. Les valeurs peuvent modifier : degats, "
                                "degats de zone, dispersion, delai de rechargement, "
                                "recul, portee..."),
        ("Mod.ReloadDelay exemple", "Exemple de syntaxe : "
                                     "Mod.ReloadDelay: \"ReloadDelay + Player.Skill['nom']\""),
    ]),
    ("Classes de conteneur", [
        ("Class: Container", "Cargo, coffre, frigo... necessite VolumeCapacity."),
        ("Class: ContainerPersonal", "Necessite VolumeCapacity."),
        ("Class: ContainerController", "Necessite VolumeCapacity."),
        ("Class: ContainerExtension", "Necessite VolumeCapacity."),
        ("Class: ArmorLocker", "Necessite VolumeCapacity."),
        ("Class: Constructor", "Tous les constructeurs, y compris le transformateur "
                                "alimentaire."),
        ("Class: WarpDriveTank", "Necessite VolumeCapacity."),
        ("Class: RepairStation", "Necessite VolumeCapacity."),
    ]),
    ("Types de symetrie (SymType)", [
        ("SymType 1", "Forme symetrique type quart de rond (par defaut)."),
        ("SymType 2", "Forme symetrique type coin."),
        ("SymType 3", "Forme symetrique type mur incline."),
        ("SymType 4", "Forme type coin biseau, mais avec une rotation par defaut "
                       "incorrecte (orthogonale a l'axe Z)."),
        ("MirrorTo", "Bloc utilise quand celui-ci est mis en miroir."),
    ]),
    ("Modes de shader", [
        ("Device", "Coloration classique (constructeurs, etc.)."),
        ("NoSI", "Objets de decor sans integrite structurelle (meme rendu que Device "
                  "mais sans SI)."),
        ("NPC", "Coloration par materiau, pour les PNJ."),
        ("Cutout", "Comme Device, avec transparence par decoupe."),
        ("DeviceEmissiveOn", "Comme Device, mais avec un effet lumineux constant "
                              "(ex: panneaux solaires)."),
        ("DeviceNewColoring", "Nouvelle methode de coloration pour les blocs Device."),
        ("NoSINewColoring", "Nouvelle methode de coloration pour les objets de decor."),
    ]),
    ("Proprietes exportees", [
        ("IsAccessible", "Apparait dans le Panneau de Controle."),
        ("O2Accept", "Liste des objets utilisables pour remplir une bouteille "
                      "d'oxygene (le premier de la liste est utilise en priorite)."),
        ("FuelAccept", "Liste des objets utilisables comme carburant (le premier de la "
                        "liste est utilise en priorite)."),
    ]),
]

# ============================================================================
# GalaxyConfig.ecf -- generation de la galaxie (etoiles, regions, territoires)
# ============================================================================
GALAXY_CONFIG_GLOSSARY = [
    ("Limites de nombre", [
        ("Regions", "De StarRegion_1 a StarRegion_99 maximum."),
        ("Territoires", "De Territory_1 a Territory_20 maximum, chacun pouvant avoir "
                         "1 a 10 factions 'Other_' additionnelles (Other_1 a Other_10)."),
        ("Types d'etoiles (suntypes)", "Illimites."),
    ]),
    ("Systemes a deux etoiles", [
        ("CompanionStarClass", "Ajoute une 2e etoile decorative (pas de gameplay) a une "
                                "StarClass -- la valeur doit etre une StarClass deja "
                                "definie dans ce fichier."),
    ]),
    ("Configuration avancee", [
        ("SolarSystemConfigSuffix", "Force l'utilisation d'un fichier "
                                     "SolarSystemConfig<suffixe>.yaml particulier au "
                                     "lieu de celui du type d'etoile par defaut."),
        ("Modeles d'etoile disponibles", "SunBlueGiant, SunWhiteDwarf, SunYellowWhite, "
                                          "SunYellow, SunRedGiant, SunRedDwarf, "
                                          "SunNeutron, BlackHole, SunGeneric. Seul le "
                                          "modele visuel est limite a cette liste -- "
                                          "tous les autres parametres (StarClass, "
                                          "couleur...) restent personnalisables."),
        ("Systeme de depart", "Si le scenario n'utilise pas de sectors.yaml fixe avec "
                               "planetes de depart, un systeme de depart peut etre "
                               "defini dans les reglages generaux. Un sectors.yaml "
                               "avec planetes de depart est prioritaire sur cette "
                               "entree si les deux existent."),
    ]),
    ("Unites de mesure internes", [
        ("1 annee-lumiere (LJ)", "= 10 000 UA = 100 000 secteurs (valeur simplifiee "
                                  "pour la lisibilite, pas la vraie mesure "
                                  "astronomique)."),
        ("1 UA", "= 10 secteurs."),
        ("Coordonnees en annees-lumiere", "Territoires, position d'une etoile "
                                           "(sectors.yaml), rayon de spawn galactique, "
                                           "rayon de la galaxie."),
        ("Coordonnees en secteurs", "Zones autour d'une etoile (ex: HabitableCold), "
                                     "position d'une planete/lune/station dans "
                                     "sectors.yaml ou SolarSystemConfig -- PAS en UA."),
    ]),
    ("Territoires", [
        ("Factions disponibles", "Zirax, Talon, Polaris, Kriel, Pirates, Trader, UCH, "
                                  "Civilian, Alien."),
        ("Chevauchement", "Plusieurs territoires peuvent exister pour la meme faction, "
                           "meme avec des coordonnees/spheres qui se chevauchent."),
        ("Faction du territoire", "Seuls ses propres POI sont places dans le "
                                   "territoire par defaut ; pour en autoriser d'autres, "
                                   "utiliser 'Other_' avec un numero, en definissant la "
                                   "probabilite du centre vers le bord."),
    ]),
    ("Etiquettes sur la carte (StarRegion)", [
        ("LabelName", "Texte de l'etiquette a cette position."),
        ("LabelColor", "Couleur, ex: \"0,1,0.67\" ou avec transparence "
                        "\"1.0,0.0,0.0,0.2\"."),
        ("LabelSize", "Taille de l'etiquette."),
        ("LabelLYDistance", "Distance (en annees-lumiere) au-dela de laquelle "
                             "l'etiquette se cache."),
    ]),
    ("Nebuleuses", [
        ("NebulaSpawnCount", "Si defini dans une StarRegion, desactive les nebuleuses "
                              "aleatoires -- seules celles de regions utilisant cette "
                              "propriete apparaissent."),
        ("NebulaColorIndex", "Choisit la couleur de la nebuleuse dans le degrade "
                              "NebulaColor correspondant (jusqu'a 30 degrades "
                              "possibles)."),
    ]),
    ("Voir les changements sans relancer", [
        ("Astuce", "Charge une partie sauvegardee, edite son Galaxyconfig.ecf dans le "
                    "dossier de la sauvegarde, puis recharge avec la commande console "
                    "'galaxy'."),
    ]),
    ("Cacher un systeme solaire", [
        ("HideFromMap", "Masque le systeme de la carte galactique."),
        ("HideFromSearch", "Le systeme reste visible sur la carte mais n'apparait plus "
                            "dans la recherche."),
    ]),
    ("Reglages d'une etoile (exemple complet)", [
        ("Name", "Nom de l'etoile -- personnalisable, ou generique "
                  "'<StarClass> Type Star'."),
        ("StarClass", "Classe de l'etoile, 3-4 lettres/chiffres."),
        ("Model", "Modele visuel (par defaut SunGeneric)."),
        ("Probability", "0 a 1 -- probabilite globale que cette classe existe dans la "
                         "galaxie (ne jamais mettre 0)."),
        ("SizeClass", "1 a 12 -- taille de l'etoile et de son icone, influence la "
                       "distance des secteurs de warp pour les grosses etoiles."),
        ("Color / LightColor / ModelColor / ModelColor2", "Couleurs de l'etoile "
                          "(carte, apparence en jeu, couleur interne, couronne)."),
        ("ModelBrightness", "0.1 a 1.5 -- luminosite globale de la couronne "
                             "(SunGeneric uniquement)."),
        ("SurfaceTemperature / Mass / Radius / Luminosity / Age", "Purement "
                          "informatif, aucun effet sur le jeu."),
        ("InnerSystem / HabitableHot / HabitableTemperate / HabitableCold / OuterSystem",
         "Plages de distance (en UA) definissant chaque zone du systeme -- utilisees "
         "ensuite dans sectors.yaml pour placer les planetes."),
        ("GalaxySpawnRadius", "Distance min/max (en annees-lumiere) du centre pour que "
                               "cette etoile apparaisse."),
        ("GalaxySpawnAmount", "Nombre d'etoiles de ce type placees dans la galaxie -- "
                               "mettre 0 seulement si gere via les REGIONS."),
        ("ClusterProb / ClusterRange", "Probabilite (0-1) et position (0=bord, "
                                        "1=centre) de regroupement en amas."),
        ("Description", "Courte description scientifique/narrative pour la carte."),
    ]),
]

# ============================================================================
# ItemsConfig.ecf -- items, armes, armures (tres proche de BlocksConfig.ecf)
# ============================================================================
ITEMS_CONFIG_GLOSSARY = [
    ("Proprietes generales", [
        ("CustomIcon", "Reutilise une icone deja existante pour l'affichage en jeu."),
        ("AllowAt", "Restreint l'usage, ex: 'AllowAt: NoPvP' et 'AllowAt: NoPvE' pour "
                     "interdire un objet selon le mode de jeu."),
        ("MarketPrice", "Prix par unite pour les POI 'StationInterface'. Si plusieurs "
                         "objets remplissent le meme role (ex: 3 types de piles pour "
                         "le carburant), celui au cout le plus bas est utilise "
                         "automatiquement."),
        ("LifetimeOnDrop", "Duree en secondes avant qu'un objet lache au sol "
                            "disparaisse (200s par defaut). N'augmenter qu'en cas de "
                            "necessite absolue -- trop d'objets au sol degrade les "
                            "performances."),
        ("DropOnDeath", "Mettre a 'False' pour qu'un objet important d'histoire ne "
                         "soit jamais perdu a la mort du joueur (vrai par defaut)."),
    ]),
    ("Effets (Buffs/Debuffs)", [
        ("BuffMod", "Syntaxe: \"StatusID, FacteurDuree, FacteurIntensite, "
                     "AnnulerAExpiration(optionnel)\". Le facteur duree/intensite "
                     "modifie le temps/la force de l'effet (0 = pas de changement)."),
        ("Annuler a expiration", "Booleen qui empeche les effets de fin de statut si "
                                  "vrai -- ex: un medicament qui empeche une blessure "
                                  "infectee d'evoluer en septicemie."),
    ]),
    ("Armures et boosters", [
        ("SlotItems", "15 entrees maximum par armure. Attention : modifier cette "
                       "liste change les boosters deja actifs dans les parties "
                       "existantes (stockes par simple INDEX dans cette liste)."),
        ("Armor", "Points de vie supplementaires."),
        ("Oxygen", "Volume d'oxygene supplementaire."),
        ("Radiation / Heat / Cold", "Protection jusqu'a cette valeur."),
        ("PowerFac / SpeedFac / StaminaFac / JetpackFac / JumpFac / FoodFac",
         "Multiplicateurs pour l'energie, la vitesse, l'endurance, le jetpack, le "
         "saut, la consommation alimentaire."),
    ]),
    ("Types d'armes et degats", [
        ("Class: Ranged", "Les degats sont definis sur l'arme elle-meme ; le type de "
                           "munition ne porte que des stats (masse, volume, cout...)."),
        ("Class: LauncherSS", "Degats ET degats de zone (optionnel) definis sur le "
                               "type de munition (sous-entree 'Class: Projectile')."),
        ("Degats de zone (Blast)", "S'AJOUTENT aux degats de base pour le bloc central "
                                    "touche. Formule approximative : "
                                    "(Degats + DegatsZone) - (DegatsZone / RayonZone)."),
        ("Materiaux disponibles pour multiplicateurs", "head, body, dirt, stone, rock, "
                          "metallight, metal, metalhard, woodsoft, wood, woodhard, "
                          "concrete, hull, hullarmored, hullcombat, shield."),
        ("ShieldDamagePenFac / BlastShieldDamagePenFac", "Pourcentage (0.0-1.0) de "
                          "degats normaux/de zone qui traverse le bouclier."),
        ("BlastRadius / BlastDamage / BlastParticleIndex", "Rayon et intensite des "
                          "degats de zone, et quel effet visuel utiliser (1-16)."),
        ("Boucliers : cas particulier", "Les degats de zone ne s'appliquent JAMAIS a "
                          "un bouclier -- seuls les degats de base comptent."),
        ("ShieldMultiplier", "Sur un Class:ShieldGenerator (BlocksConfig.ecf), valeur "
                              "libre reutilisable dans un DamageMultiplier pour cibler "
                              "specifiquement ce type de bouclier."),
    ]),
    ("Categories", [
        ("Ingredients", "Matiere brute sans recette (ramassee dans le monde)."),
        ("Components", "Materiau transforme, avec une recette (Templates.ecf)."),
    ]),
    ("Types de prise en main (HoldType)", [
        ("0", "Non specifie."),
        ("14", "Pistolet."),
        ("15", "Fusil."),
        ("16", "Fusil avec animation de tir plus faible (outil de survie, "
                "multi-outil, foreuse)."),
        ("17", "Arc."),
        ("20", "Corps a corps."),
    ]),
    ("Divers", [
        ("AllowRemote", "Autorise/interdit l'usage en drone joueur (vrai par defaut)."),
        ("AmmoCapacity", "Maximum 500 pour toutes les tourelles/armes montees."),
        ("Durability", "Maximum 5000 pour les armes/outils portes a la main."),
        ("AutoReload", "Rechargement automatique (vrai par defaut)."),
    ]),
]

# ============================================================================
# GlobalDefsConfig.ecf -- macros/valeurs reutilisables entre fichiers ECF
# ============================================================================
GLOBALDEFS_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Definir des valeurs communes (ex: degats d'une arme, points de "
                      "vie d'un drone) UNE SEULE FOIS ici, puis les reutiliser dans "
                      "n'importe quel autre fichier ECF -- modifier la valeur ici "
                      "suffit a la changer partout."),
        ("Utilisation", "Dans un autre fichier (ex: ItemsConfig.ecf), utiliser "
                         "'GlobalRef: NomDeLaDef' pour reference cette valeur."),
        ("Plusieurs References", "Un meme bloc peut utiliser plusieurs GlobalDef via "
                                  "GlobalRef_1 jusqu'a GlobalRef_5."),
    ]),
]

# ============================================================================
# LootGroups.ecf -- tables de butin (format de ligne)
# ============================================================================
LOOT_GROUPS_GLOSSARY = [
    ("Format d'une ligne", [
        ("Syntaxe", "Item_x: nom, data: quantite[-plage], xdata: probabilite "
                     "(x s'incremente pour chaque ligne ; utiliser des guillemets si "
                     "la quantite est une plage)."),
    ]),
]

# ============================================================================
# MaterialConfig.ecf -- proprietes physiques des materiaux
# ============================================================================
MATERIAL_CONFIG_GLOSSARY = [
    ("Notes generales", [
        ("hullarmored / hullcombat", "Ne peuvent pas etre detruits par la plupart des "
                                      "armes portees a la main."),
        ("Integrite structurelle (SI)", "Longueur maximale actuelle d'une poutre "
                                         "horizontale = 12 blocs."),
        ("stability_glue / mass", "Determine le nombre maximum de blocs alignes qui "
                                   "ne se detacheront pas a cause de la perte "
                                   "d'integrite structurelle."),
    ]),
]

# ============================================================================
# StatusEffects.ecf -- effets de statut (blessures, maladies...)
# ============================================================================
STATUS_EFFECTS_GLOSSARY = [
    ("Notes generales", [
        ("Blessures basiques", "Regroupent tout ce qu'un ennemi inflige couramment."),
        ("Exemple : saignement standard", "Guerit seul sans traitement, en 240 points "
                                           "de vie de duree."),
    ]),
]

# ============================================================================
# Templates.ecf -- recettes de craft
# ============================================================================
TEMPLATES_GLOSSARY = [
    ("Abreviations de constructeur et facteur de temps", [
        ("SuitC", "Constructeur de Survie -- facteur 1.8 (le plus lent)."),
        ("SurvC", "Constructeur Portable -- facteur 1.6."),
        ("SmallC", "Constructeur SV -- facteur 1.4."),
        ("HoverC", "Constructeur HV -- facteur 1.4."),
        ("BaseC", "Constructeur T0 -- facteur 1.2."),
        ("LargeC", "Constructeur T1V2 -- facteur 1 (reference)."),
        ("AdvC", "Constructeur T2 -- facteur 0.5 (le plus rapide)."),
        ("FoodP", "Transformateur Alimentaire V2 -- facteur 1."),
        ("Furn", "Fournaise -- facteur 0.2."),
        ("(sans balise)", "Deconstructeur -- facteur 0.5."),
    ]),
    ("Astuces de recette", [
        ("Objet gratuit", "Mettre TOUTES les lignes de Child Inputs a 0 -- ne JAMAIS "
                           "supprimer la section entierement."),
        ("BaseItem: true", "Definit le niveau de base pour l'usine a blueprints, et "
                            "sert de reference pour la reparation R2T."),
        ("Deconstructeur", "Decompose un objet jusqu'a n'obtenir que des ingredients "
                            "marques BaseItem. Ex: le minerai de fer (BaseItem) ne "
                            "sera jamais recree a partir du lingot de fer."),
        ("DeconOverride: Continue", "Autorise le deconstructeur a decomposer l'objet "
                                     "une etape supplementaire."),
        ("DeconOverride: Stop", "Empeche toute deconstruction de cet objet."),
        ("Limitation T1 vers T2", "Utiliser un appareil T1 comme ingredient d'un "
                                   "appareil T2 ne fonctionne que pour les appareils "
                                   "uniques (ex: Constructeur), pas pour les groupes "
                                   "de blocs (ex: Cockpits) -- ne pas utiliser le T1 "
                                   "en ingredient dans ce cas."),
    ]),
]

# ============================================================================
# TokenConfig.ecf -- jetons (cles, quetes, PDA...)
# ============================================================================
TOKEN_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Definition", "Un jeton (Token) est une instance de l'item 'GenericToken' qui "
                        "prend son sens en jeu -- ex: le code d'une porte verrouillee, "
                        "ou une quete/mission PDA necessitant ce jeton pour se "
                        "terminer."),
        ("RemoveOnUse", "A true, retire le jeton de l'inventaire du joueur des qu'il "
                         "est utilise."),
        ("Facultatif", "Pas besoin de definir chaque jeton ici, mais si defini, son "
                        "nom et sa description s'afficheront correctement."),
    ]),
    ("Cas d'usage", [
        ("1. Placer un jeton dans un conteneur", "Console: 'give item Token 0001', "
                          "puis le placer dans un conteneur et sauvegarder le POI "
                          "(fonctionne seulement avec un core admin actuellement)."),
        ("2. Donner via PDA", "Utiliser 'Token:0001' comme recompense ou operation "
                               "d'inventaire dans une mission PDA."),
        ("3. Donner via dialogue", "Fonction AddItem, ex: "
                                    "AddItem('KeyCardBlack', 3, 1234) donne 3 cartes "
                                    "avec le Meta 1234."),
        ("4. Vente par un marchand", "Ajouter l'item au TraderNPCConfig.ecf en "
                                      "utilisant 'Token:0001' comme nom d'item."),
        ("5. Dans une table de butin", "Meme principe, utiliser 'Token:0001' dans le "
                                        "LootGroups.ecf."),
    ]),
    ("Important", [
        ("Item 'Token' (Id 1305)", "Seul cet item precis peut recevoir un Meta a 4 "
                                    "chiffres. Aucun autre objet 'carte-cle' ou "
                                    "similaire ne peut avoir de Meta attache."),
        ("Rechargement a chaud", "La commande console 'token reload' applique les "
                                  "changements de ce fichier sans relancer le jeu."),
    ]),
]

# ============================================================================
# TraderNPCConfig.ecf -- configuration des marchands
# ============================================================================
TRADER_NPC_CONFIG_GLOSSARY = [
    ("Format d'un item", [
        ("Syntaxe generale", "Nom de l'item, plage de prix de vente, plage de stock "
                              "disponible[, plage de prix d'achat, plage de stock "
                              "maximum]."),
        ("Section achat optionnelle", "Si omise, le marchand n'achete pas cet item."),
        ("Calcul du prix", "Si le marchand achete l'item (stock max defini), le prix "
                            "de reference correspond a un stock actuel egal a la "
                            "moitie du stock max. Plus de stock = prix qui baisse, "
                            "moins de stock = prix qui monte."),
        ("Vente seule", "Si le marchand ne fait que vendre l'item, le prix ne depend "
                         "pas du stock."),
        ("Chevauchement autorise", "Le prix d'achat peut chevaucher le prix de vente "
                                    "-- le jeu garantit quand meme une marge d'au "
                                    "moins 5% pour le marchand."),
        ("Facteur de marche (mf=)", "Permet d'appliquer un facteur au prix de marche "
                                     "de base."),
        ("Exemple", "Item1: \"AutoMinerCore, mf=2.5-3.2, 10-50, mf=1.2-2.3, 55-150\""),
    ]),
    ("Attention", [
        ("Marchand par defaut", "Ne pas changer le nom du marchand fourni par "
                                 "defaut."),
    ]),
]

# ============================================================================
# BlockGroupsConfig.ecf -- groupes de blocs avec limite commune (ex: tourelles)
# ============================================================================
BLOCK_GROUPS_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Definir un groupe de blocs personnalise partageant une limite "
                      "commune -- utile pour equilibrer, par exemple, le nombre total "
                      "de tourelles."),
        ("Limite individuelle conservee", "Les blocs du groupe respectent a la fois "
                                           "la limite du groupe ET leur propre limite "
                                           "individuelle (definie dans "
                                           "BlocksConfig.ecf)."),
        ("Fonctionne uniquement", "Sur les blocs ayant un index (un Id numerique)."),
        ("Informer le joueur", "Ajouter une ligne correspondante dans "
                                "Localization.csv (ex: 'SVWeapons,Total SV Weapons "
                                "{0},...') pour afficher la limite dans l'interface -- "
                                "rien d'autre a ajouter dans BlocksConfig.ecf."),
    ]),
    ("Exemple", [
        ("BlockGroup Name / MaxCount / Blocks", "Nom du groupe, limite totale, et "
                                                  "liste des blocs concernes separes "
                                                  "par des virgules."),
    ]),
]

# ============================================================================
# Containers.ecf -- tables de butin des conteneurs
# ============================================================================
CONTAINERS_GLOSSARY = [
    ("Format d'une ligne", [
        ("Syntaxe", "\"Groupe|Nom_x\" (x s'incremente), data: \"probabilite\" "
                     "[, xdata=\"plage de quantite\"] (par defaut 1,1)."),
        ("Colonnes", "Toujours utiliser 8 colonnes actuellement (premier nombre de la "
                      "ligne 'Size')."),
        ("Total disponible", "1023 Id au maximum."),
    ]),
    ("Jetons dans une table de butin", [
        ("Syntaxe", "Name_0: Token, param1: 1, param2: \"meta=9992\" -- le meta "
                     "provient de TokenConfig.ecf."),
    ]),
    ("Tables pour spawners de PNJ", [
        ("Usage", "Entrer le numero d'Id du conteneur (ex: 255) dans le menu "
                   "deroulant a cote du spawn-entity."),
    ]),
    ("Cultures cultivables (jardiniere joueur)", [
        ("Fruit", "AlienPalmTreeStage1, PearthingStage1"),
        ("Legumes", "AlienPlantTube2Stage1, BulbShroomYoungStage1, DurianRoot, "
                     "PumpkinStage1, TomatoStage1"),
        ("Edulcorant naturel", "AlienplantWormStage1"),
        ("Bourgeons", "BigFlowerStage1"),
        ("Epice", "CobraLeavesPlantStage1"),
        ("Stimulant naturel", "CoffeePlantStage1"),
        ("Cereales", "CornStage1, WheatStage1"),
        ("Minerai de Pentaxid", "CrystalsPyramidBlueStage1, "
                                 "CrystalsPyramidOrangeStage1, CrystalStraightStage1"),
        ("Feuilles medicinales", "DesertPlant20Stage1"),
        ("Baies", "ElderberryStage1"),
        ("Champignon brun", "MushroomBellBrown01Stage1"),
        ("Fibre", "SnakeweedStage1"),
    ]),
]

# ============================================================================
# DamageMultiplierConfig.ecf -- multiplicateurs de degats par materiau
# ============================================================================
DAMAGE_MULTIPLIER_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Definir des groupes de multiplicateurs de degats reutilisables "
                      "depuis ItemsConfig.ecf via 'DamageMultiplier_Group: NomDuGroupe'."),
        ("Une seule methode a la fois", "Dans ItemsConfig.ecf, utiliser soit "
                                         "DamageMultiplier_x SOIT "
                                         "DamageMultiplier_Group, pas les deux."),
        ("Groupe de groupes", "Un 'Collection' permet de combiner plusieurs groupes -- "
                               "mais un groupe de groupes ne peut pas en referencer un "
                               "autre."),
    ]),
    ("Exemple : Pistol", [
        ("DamageMultiplier_1: 5, param1: head", "x5 de degats sur la tete."),
        ("DamageMultiplier_2: 0, param1: dirt|stone|...", "Aucun degat sur ces "
                                                            "materiaux de terrain/mur."),
        ("DamageMultiplier_3: 0, param1: shield", "Aucun degat sur les boucliers."),
    ]),
]

# ============================================================================
# DefReputation.ecf -- reputation par defaut envers les factions
# ============================================================================
DEF_REPUTATION_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Permet de remplacer la reputation par defaut de toutes les "
                      "factions d'origine (Origin) envers les factions PNJ."),
    ]),
]

# ============================================================================
# EGroupsConfig.ecf -- groupes d'entites (spawns de creatures/PNJ)
# ============================================================================
EGROUPS_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Factions", "Les factions des creatures sont definies dans EClassConfig.ecf, "
                      "pas ici."),
        ("Groupes de bataille (Battle Groups)", "Apparaissent ensemble et "
                          "interagissent comme une equipe (IA comportementale)."),
    ]),
]

# ============================================================================
# Factions.ecf -- definition des factions
# ============================================================================
FACTIONS_GLOSSARY = [
    ("Valeurs obligatoires", [
        ("Id", "Doit etre unique, utilise dans les sauvegardes -- le changer casse "
                "les parties existantes. Doit etre < 100, sinon une faction JOUEUR "
                "est creee a la place. Des trous dans la numerotation sont "
                "autorises."),
        ("FactionName", "Sans espaces ni caracteres speciaux -- utilisable dans la "
                         "localisation. Sert de reference pour les playfields, POI, "
                         "etc."),
        ("Abbrev", "3 lettres maximum, eviter les caracteres speciaux."),
        ("Color", "\"R,G,B\" -- diviser la valeur RGB par 255 pour obtenir le "
                   "flottant attendu."),
        ("Description", "Affichee en haut de la liste pour les factions PNJ."),
    ]),
    ("Factions statiques", [
        ("Definition", "Factions comme Legacy ou Alien -- impossible d'ameliorer sa "
                        "reputation avec elles."),
        ("Friendly: true", "Toujours amicale -- DefReputation.ecf ignore, ne pas "
                            "combiner avec 'Reputation: true'."),
        ("Unfriendly: true", "Toujours hostile -- meme regle."),
        ("Ni l'un ni l'autre", "La faction est neutre par defaut."),
    ]),
    ("Factions dynamiques", [
        ("Definition", "Factions comme les Zirax -- reputation, territoire propre, "
                        "amelioration/degradation possible."),
        ("Reputation: true", "Active la matrice de reputation de DefReputation.ecf. "
                              "Sans ca, la faction est hostile statique (sauf si "
                              "FriendlyToPlayers est actif)."),
        ("ClaimTerritory: true", "La faction peut avoir un territoire visuel sur les "
                                  "planetes (sans lien avec les territoires "
                                  "galactiques, geres dans galaxy.ecf)."),
    ]),
    ("Autres reglages", [
        ("OmitMapLegend", "Cache la faction de la legende des cartes."),
        ("HideAbbrev", "Cache l'abreviation de la faction dans l'interface (HUD)."),
        ("Discovery", "La faction devient decouvrable des qu'un de ses POI est "
                       "decouvert. Debug via la commande console "
                       "'faction discover <faction>'."),
        ("AttackNPC", "Cette faction attaque les autres factions PNJ ayant aussi "
                       "cette option active."),
        ("ForceAttack", "Liste de factions specifiquement attaquees (peut etre "
                         "asymetrique) -- ecrase le comportement d'AttackNPC."),
    ]),
    ("A savoir", [
        ("Ne pas melanger", "Une faction est soit statique, soit dynamique -- jamais "
                             "les deux."),
        ("Factions protegees", "Zirax, Talon, Alien, Polaris, Prey, Predator et Admin "
                                "sont geres en interne (references/valeurs par "
                                "defaut) et ne sont pas personnalisables."),
    ]),
    ("Guerre des factions (resume)", [
        ("Civilisation galactique (alliee)", "Zirax, Polaris, Trader, Colonists, "
                                              "Eden_Defender."),
        ("Ennemis de tous", "Warlord, Alien, TheLegacy, Kriel, Eden_Drone, "
                             "Eden_DroneHome, Pirates."),
        ("Ressources minables", "Eden_Resource, Prey."),
        ("Factions codees en dur", "Ne jamais les modifier (sauf la couleur) -- "
                                    "doivent etre definies avant toute autre "
                                    "faction dans le fichier."),
    ]),
]

# ============================================================================
# FactionWarfare.ecf -- attaques de base, defense spatiale
# ============================================================================
FACTION_WARFARE_GLOSSARY = [
    ("Defense de base spatiale (SBD)", [
        ("Portee", "Globale pour toute une faction sur un POI donne -- impossible de "
                    "configurer un vaisseau specifique pour un POI precis via SBD."),
        ("Exclure un POI de la SBD", "Dans le playfield yaml, utiliser "
                          "SpaceDefenseOverrideDefaults: True avec "
                          "SpaceDefenseProbability: 1.0 et "
                          "SpaceDefensePriceMinMax: [30, 60] -- ou fixer une "
                          "probabilite precise (0-1) autrement geree par l'IA."),
    ]),
    ("Attaque de base Zirax (Survie)", [
        ("FactionSettings", "Convertit un numero de niveau en prix de vague "
                             "d'attaque."),
        ("Unit", "Definit une unite individuelle utilisable dans un scenario "
                  "d'attaque, rangee dans une categorie (ex: plusieurs forces de "
                  "drone minigun selon la difficulte)."),
        ("Scenario", "Definit la composition complete d'une attaque -- utilisable "
                      "automatiquement par le systeme d'attaque de base, ou "
                      "manuellement via une mission PDA."),
    ]),
]

GLOSSARY_BY_FILE = {
    "BlocksConfig.ecf": BLOCKS_CONFIG_GLOSSARY,
    "GalaxyConfig.ecf": GALAXY_CONFIG_GLOSSARY,
    "ItemsConfig.ecf": ITEMS_CONFIG_GLOSSARY,
    "GlobalDefsConfig.ecf": GLOBALDEFS_CONFIG_GLOSSARY,
    "LootGroups.ecf": LOOT_GROUPS_GLOSSARY,
    "MaterialConfig.ecf": MATERIAL_CONFIG_GLOSSARY,
    "StatusEffects.ecf": STATUS_EFFECTS_GLOSSARY,
    "Templates.ecf": TEMPLATES_GLOSSARY,
    "TokenConfig.ecf": TOKEN_CONFIG_GLOSSARY,
    "TraderNPCConfig.ecf": TRADER_NPC_CONFIG_GLOSSARY,
    "BlockGroupsConfig.ecf": BLOCK_GROUPS_CONFIG_GLOSSARY,
    "Containers.ecf": CONTAINERS_GLOSSARY,
    "DamageMultiplierConfig.ecf": DAMAGE_MULTIPLIER_CONFIG_GLOSSARY,
    "DefReputation.ecf": DEF_REPUTATION_GLOSSARY,
    "EGroupsConfig.ecf": EGROUPS_CONFIG_GLOSSARY,
    "Factions.ecf": FACTIONS_GLOSSARY,
    "FactionWarfare.ecf": FACTION_WARFARE_GLOSSARY,
}

```

### core\file_handlers.py

```py
"""
Interface commune que chaque type de fichier (ECF, YAML, CSV...) devra implémenter.

Étape 0 : on pose le contrat et un registre d'extensions -> handler.
Étape 1 : le handler ECF réel est branché ici (voir EcfHandler plus bas).
Les autres extensions (.yaml, .csv) restent en placeholder pour les étapes suivantes.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional

from .ecf.parser import parse_ecf_file, parse_ecf_text
from .ecf.model import EcfDocument


class FileHandler(ABC):
    """Contrat commun à tous les parsers de fichiers de scénario."""

    extensions: tuple = ()

    @abstractmethod
    def load(self, path: Path) -> Any:
        """Lit le fichier depuis le disque et retourne son contenu brut (texte, bytes...)."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: Any) -> Any:
        """Transforme le contenu brut en structure interne éditable (AST)."""
        raise NotImplementedError

    @abstractmethod
    def serialize(self, ast: Any) -> str:
        """Reconstruit le texte du fichier à partir de l'AST (doit préserver commentaires/ordre)."""
        raise NotImplementedError

    def diff(self, ast_a: Any, ast_b: Any) -> Any:
        """Compare deux AST du même type. Implémenté à l'Étape 3."""
        raise NotImplementedError(f"{type(self).__name__}: diff pas encore implémenté")

    def merge(self, sources: List[Any], rules: Optional[Any] = None) -> Any:
        """Fusionne plusieurs AST du même type selon des règles. Implémenté à l'Étape 4."""
        raise NotImplementedError(f"{type(self).__name__}: merge pas encore implémenté")


class EcfHandler(FileHandler):
    """Handler réel pour les fichiers .ecf, basé sur le parser de l'Étape 1.
    Garantit un round-trip fidèle (byte pour byte) tant qu'aucune valeur n'est modifiée."""

    extensions = ('.ecf',)

    def load(self, path: Path) -> str:
        # Voir la note dans core/ecf/parser.py : 'utf-8' (pas 'utf-8-sig') pour préserver
        # un éventuel BOM comme partie du texte, et garantir le round-trip byte-pour-byte.
        with open(path, 'r', encoding='utf-8', newline='') as f:
            return f.read()

    def parse(self, raw: str) -> EcfDocument:
        return parse_ecf_text(raw)

    def serialize(self, ast: EcfDocument) -> str:
        return ast.render()


class UnimplementedHandler(FileHandler):
    """
    Placeholder utilisé tant qu'un vrai parser n'existe pas pour une extension donnée.
    Permet de savoir dès l'Étape 0 quelles extensions seront un jour éditables, sans
    encore fournir de vraie logique de parsing.
    """

    def __init__(self, extensions: tuple):
        self.extensions = extensions

    def load(self, path: Path) -> Any:
        return path.read_text(encoding='utf-8', errors='replace')

    def parse(self, raw: Any) -> Any:
        raise NotImplementedError("Parser non encore implémenté (arrive à l'Étape 1)")

    def serialize(self, ast: Any) -> str:
        raise NotImplementedError("Serializer non encore implémenté (arrive à l'Étape 1)")


class HandlerRegistry:
    """Associe une extension de fichier à son FileHandler."""

    def __init__(self):
        self._handlers = {}

    def register(self, handler: FileHandler) -> None:
        for ext in handler.extensions:
            self._handlers[ext.lower()] = handler

    def get_handler(self, path: Path) -> Optional[FileHandler]:
        return self._handlers.get(path.suffix.lower())

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self._handlers

    def supported_extensions(self) -> List[str]:
        return sorted(self._handlers.keys())


def default_registry() -> HandlerRegistry:
    """Registre par défaut. Les handlers ECF et YAML sont réels (Étapes 1 et 6, tous
    deux avec parser maison, sans dépendance externe) ; CSV reste un placeholder."""
    reg = HandlerRegistry()
    reg.register(EcfHandler())
    from .yaml_handler import YamlHandler
    reg.register(YamlHandler())
    from .csv_handler import CsvHandler
    reg.register(CsvHandler())
    return reg

```

### core\fsutil.py

```py
"""
Utilitaire filesystem partage. Sert principalement a garantir qu'aucun fichier/dossier
ecrit par l'application n'herite d'un attribut lecture seule de sa source -- probleme
concret rencontre avec des scenarios installes sous Program Files (souvent marques
lecture seule par Windows) : `shutil.copy2`/`copytree` preservent les metadonnees par
defaut, ce qui rend la copie de travail elle-meme lecture seule (impossible a modifier
ou meme a supprimer -- Windows demande alors "l'autorisation" du proprietaire, meme si
c'est l'utilisateur courant).
"""
import os
import stat
from pathlib import Path


def clear_readonly(path: Path) -> None:
    """Retire l'attribut lecture seule sur `path`. Si c'est un dossier, le fait
    recursivement sur tout son contenu (fichiers ET sous-dossiers). Ignore les erreurs
    individuelles (fichier verrouille par un autre processus, etc.) plutot que de faire
    echouer toute l'operation pour un seul fichier problematique."""
    path = Path(path)
    if not path.exists():
        return

    def _unlock_one(p: Path) -> None:
        try:
            current = os.stat(p).st_mode
            os.chmod(p, current | stat.S_IWRITE | stat.S_IWUSR)
        except OSError:
            pass

    if path.is_dir():
        _unlock_one(path)
        for root, dirs, files in os.walk(path):
            for d in dirs:
                _unlock_one(Path(root) / d)
            for f in files:
                _unlock_one(Path(root) / f)
    else:
        _unlock_one(path)

```

### core\i18n.py

```py
"""
Systeme de traduction de l'interface (FR/EN). Usage :

    from core.i18n import t
    label = QLabel(t("menu.file"))

La langue active est lue/ecrite via core.settings (persistee entre sessions). Bascule
en direct via set_language() -- les widgets deja crees doivent etre reconstruits ou
avoir leur texte reassigne manuellement pour refleter le changement (voir
gui/main_window.py, _apply_language()).
"""
from core import settings

# Format : "cle" -> {"fr": "...", "en": "..."}
STRINGS = {
    # --- Menu Fichier ---
    "menu.file": {"fr": "&Fichier", "en": "&File"},
    "menu.file.new_project": {"fr": "&Nouveau projet...", "en": "&New project..."},
    "menu.file.recent_projects": {"fr": "&Projets recents...", "en": "&Recent projects..."},
    "menu.file.save": {"fr": "&Enregistrer", "en": "&Save"},
    "menu.file.quit": {"fr": "&Quitter", "en": "&Quit"},

    # --- Menu Verification ---
    "menu.verification": {"fr": "&Verification", "en": "&Verification"},
    "menu.verification.check_refs": {"fr": "Verifier les references (Ref) de la copie de travail...",
                                      "en": "Check references (Ref) in the working copy..."},
    "menu.verification.pending": {"fr": "Blocs en attente (conflits d'Id)...",
                                   "en": "Pending blocks (Id conflicts)..."},

    # --- Menu Options ---
    "menu.options": {"fr": "&Options", "en": "&Options"},
    "menu.options.author": {"fr": "Nom pour les annotations...", "en": "Name for annotations..."},
    "menu.options.annotations": {"fr": "Annoter les modifications automatiquement",
                                  "en": "Automatically annotate changes"},
    "menu.options.language": {"fr": "Langue : Francais (clic pour English)",
                               "en": "Language: English (click for Francais)"},

    # --- Menu Aide ---
    "menu.help": {"fr": "&Aide", "en": "&Help"},
    "menu.help.wiki_app": {"fr": "Wiki de l'application (fonctions)...",
                            "en": "Application wiki (features)..."},
    "menu.help.wiki_empyrion": {"fr": "Wiki Empyrion (proprietes, fichiers, structure)...",
                                 "en": "Empyrion wiki (properties, files, structure)..."},

    # --- Boutons communs (editeurs) ---
    "btn.save": {"fr": "Enregistrer (Ctrl+S)", "en": "Save (Ctrl+S)"},
    "btn.undo": {"fr": "Annuler (Ctrl+Z)", "en": "Undo (Ctrl+Z)"},
    "btn.add_block": {"fr": "Bloc", "en": "Block"},
    "btn.add_property": {"fr": "Propriete", "en": "Property"},
    "btn.add_row": {"fr": "Ligne", "en": "Row"},
    "btn.delete_selected_row": {"fr": "Ligne selectionnee", "en": "Selected row"},
    "btn.add_entry": {"fr": "Entree", "en": "Entry"},
    "btn.delete_selected_entry": {"fr": "Supprimer l'entree selectionnee", "en": "Delete selected entry"},
    "btn.filter_by_property": {"fr": "Filtrer par propriete...", "en": "Filter by property..."},
    "btn.apply_value": {"fr": "Appliquer cette valeur", "en": "Apply this value"},
    "btn.cancel": {"fr": "Annuler", "en": "Cancel"},
    "btn.close": {"fr": "Fermer", "en": "Close"},

    # --- Menu contextuel copier/coller ---
    "ctx.copy": {"fr": "Copier", "en": "Copy"},
    "ctx.cut": {"fr": "Couper", "en": "Cut"},
    "ctx.paste": {"fr": "Coller", "en": "Paste"},
    "ctx.clear_content": {"fr": "Supprimer le contenu (vide la/les cellule(s))",
                           "en": "Clear content (empties the cell(s))"},
    "ctx.delete_rows": {"fr": "Supprimer la/les ligne(s) entiere(s)", "en": "Delete entire row(s)"},
    "ctx.translate_to": {"fr": "Traduire vers...", "en": "Translate to..."},
    "ctx.translate_selection_to": {"fr": "Traduire la selection vers...", "en": "Translate selection to..."},
    "ctx.bbcode": {"fr": "Mise en forme BBCode (couleur/gras/italique)...",
                   "en": "BBCode formatting (color/bold/italic)..."},

    # --- Dialogue Nouveau projet ---
    "newproj.title": {"fr": "Nouveau projet", "en": "New project"},
    "newproj.scenario_a": {"fr": "Scenario A (base) :", "en": "Scenario A (base):"},
    "newproj.scenario_a_placeholder": {"fr": "Dossier racine du scenario de base...",
                                        "en": "Root folder of the base scenario..."},
    "newproj.browse": {"fr": "Parcourir...", "en": "Browse..."},
    "newproj.merge_mode": {"fr": "Mode fusion (ajouter un second scenario source B)",
                            "en": "Merge mode (add a second source Scenario B)"},
    "newproj.scenario_b": {"fr": "Scenario B (source, optionnel) :", "en": "Scenario B (source, optional):"},
    "newproj.scenario_b_placeholder": {"fr": "Dossier racine du scenario B...",
                                        "en": "Root folder of Scenario B..."},
    "newproj.working_copy": {"fr": "Copie de travail (modifiable) :", "en": "Working copy (editable):"},
    "newproj.working_copy_placeholder": {"fr": "Nouvel emplacement pour la copie de travail...",
                                          "en": "New location for the working copy..."},
    "newproj.info": {"fr": "La copie de travail sera une copie physique complete du scenario A, creee\n"
                            "au nouvel emplacement choisi. Les scenarios A et B restent en lecture seule\n"
                            "et ne seront jamais modifies.",
                      "en": "The working copy will be a complete physical copy of Scenario A, created\n"
                            "at the new location you choose. Scenarios A and B stay read-only\n"
                            "and are never modified."},
    "newproj.choose_scenario_folder": {"fr": "Choisir un dossier de scenario", "en": "Choose a scenario folder"},
    "newproj.choose_parent_folder": {"fr": "Choisir le dossier PARENT de la copie de travail",
                                      "en": "Choose the PARENT folder of the working copy"},
    "err.missing_field": {"fr": "Champ manquant", "en": "Missing field"},
    "err.invalid_path": {"fr": "Chemin invalide", "en": "Invalid path"},
    "err.dest_exists": {"fr": "Destination existante", "en": "Destination already exists"},

    # --- Dialogue Projets recents ---
    "startup.title": {"fr": "Projets recents", "en": "Recent projects"},
    "startup.subtitle": {"fr": "Reprendre un projet existant, ou en creer un nouveau :",
                          "en": "Resume an existing project, or create a new one:"},
    "startup.open_selected": {"fr": "Ouvrir le projet selectionne", "en": "Open selected project"},
    "startup.remove": {"fr": "Retirer de la liste", "en": "Remove from list"},
    "startup.new_project": {"fr": "Nouveau projet...", "en": "New project..."},

    # --- Dialogue Dupliquer un bloc ---
    "dup.title": {"fr": "Dupliquer ce bloc", "en": "Duplicate this block"},
    "dup.current_block": {"fr": "Bloc actuel : Id={id}, Name={name}", "en": "Current block: Id={id}, Name={name}"},
    "dup.none_placeholder": {"fr": "(aucun)", "en": "(none)"},
    "dup.instructions": {"fr": "Renseigne un nouvel Id, un nouveau Name, ou les deux -- au moins une "
                                "valeur doit differer de l'original.",
                          "en": "Enter a new Id, a new Name, or both -- at least one "
                                "value must differ from the original."},

    # --- Barre de statut ---
    "status.no_project": {"fr": "Aucun projet ouvert -- Fichier > Nouveau projet...",
                           "en": "No project open -- File > New project..."},
    "status.nothing_to_save": {"fr": "Rien a enregistrer sur cet onglet.", "en": "Nothing to save on this tab."},
    "status.block_activated": {"fr": "Bloc active avec Id={id} dans {file}", "en": "Block activated with Id={id} in {file}"},
    "status.project_opened": {"fr": "Projet ouvert ({mode}) -- copie de travail : {path}",
                               "en": "Project opened ({mode}) -- working copy: {path}"},
    "status.project_resumed": {"fr": "Projet repris ({mode}) -- copie de travail : {path}",
                                "en": "Project resumed ({mode}) -- working copy: {path}"},
    "status.folder_merged": {"fr": "Dossier fusionne : {n} fichier(s) traites, {ecf} fichier(s) .ecf "
                                    "avec des changements, {csv} fichier(s) .csv completes "
                                    "({rows} ligne(s)), {conflicts} conflit(s) d'Id au total",
                              "en": "Folder merged: {n} file(s) processed, {ecf} .ecf file(s) "
                                    "with changes, {csv} .csv file(s) completed "
                                    "({rows} row(s)), {conflicts} Id conflict(s) in total"},
    "status.csv_merged_rows": {"fr": "Fusionne (CSV) dans la copie de travail : {file} -- "
                                      "{n} ligne(s) ajoutee(s)/completee(s) "
                                      "(les lignes deja presentes n'ont pas ete ecrasees)",
                                "en": "Merged (CSV) into working copy: {file} -- "
                                      "{n} row(s) added/completed "
                                      "(existing rows were not overwritten)"},
    "status.csv_merged_none": {"fr": "Fusionne (CSV) : {file} -- aucun changement (deja a jour)",
                                "en": "Merged (CSV): {file} -- no change (already up to date)"},
    "status.merged_working": {"fr": "Fusionne dans la copie de travail : {file} -- "
                                     "{new} bloc(s) nouveau(x), {changed} bloc(s) complete(s)",
                               "en": "Merged into working copy: {file} -- "
                                     "{new} new block(s), {changed} completed block(s)"},
    "status.id_conflicts_suffix": {"fr": ", {n} conflit(s) d'Id a revoir", "en": ", {n} Id conflict(s) to review"},
    "status.copied_to_working": {"fr": "Copie vers la copie de travail : {dest}", "en": "Copied to working copy: {dest}"},
    "status.block_duplicated": {"fr": "Bloc duplique ({details}) dans {file}", "en": "Block duplicated ({details}) in {file}"},
    "status.id_conflict_detected": {"fr": "Conflit d'Id detecte sur {file} -- bloc ajoute desactive",
                                     "en": "Id conflict detected on {file} -- block added disabled"},
    "status.block_added": {"fr": "Bloc ajoute dans {file}", "en": "Block added in {file}"},
    "status.block_merged": {"fr": "Bloc fusionne (complete) dans {file}", "en": "Block merged (completed) in {file}"},
    "status.row_added": {"fr": "Ligne '{key}' ajoutee dans {file}", "en": "Row '{key}' added in {file}"},
    "status.row_merged": {"fr": "Ligne '{key}' completee (cellules vides) dans {file}",
                           "en": "Row '{key}' completed (empty cells) in {file}"},
    "status.row_unchanged": {"fr": "Ligne '{key}' deja a jour dans {file} -- rien a changer",
                              "en": "Row '{key}' already up to date in {file} -- nothing to change"},
    "status.row_duplicated": {"fr": "Ligne dupliquee avec la cle '{key}' dans {file}",
                               "en": "Row duplicated with key '{key}' in {file}"},
    "status.entry_copied_root": {"fr": "Entree copiee dans {file} -- emplacement d'origine introuvable, "
                                        "ajoutee a la racine du fichier (a repositionner si besoin)",
                                  "en": "Entry copied in {file} -- original location not found, "
                                        "added at the file's root (reposition if needed)"},
    "status.entry_copied": {"fr": "Entree copiee dans {file} (meme emplacement)",
                             "en": "Entry copied in {file} (same location)"},
    "status.entry_duplicated": {"fr": "Entree dupliquee avec '{value}' dans {file}{note}",
                                 "en": "Entry duplicated with '{value}' in {file}{note}"},
    "status.row_translated": {"fr": "Ligne '{key}' ajoutee avec la traduction ({lang}) dans {file}",
                               "en": "Row '{key}' added with translation ({lang}) in {file}"},
    "status.cell_translated": {"fr": "Traduction ({lang}) ajoutee pour '{key}' dans {file}",
                                "en": "Translation ({lang}) added for '{key}' in {file}"},
    "status.cell_already_has_value": {"fr": "'{key}' avait deja une valeur dans la colonne {lang} -- "
                                             "rien change (copie de travail prioritaire)",
                                       "en": "'{key}' already had a value in the {lang} column -- "
                                             "nothing changed (working copy takes priority)"},
    "status.saved": {"fr": "Enregistre : {path}", "en": "Saved: {path}"},
    "status.mode_merge": {"fr": "FUSION", "en": "MERGE"},
    "status.mode_simple": {"fr": "edition simple", "en": "simple editing"},

    # --- Panneau de comparaison (blocs en attente) ---
    "pending.no_base_block": {"fr": "(bloc de base introuvable -- affichage du bloc en attente seul)",
                               "en": "(base block not found -- showing pending block only)"},
    "pending.read_error": {"fr": "(erreur de lecture du bloc)", "en": "(error reading the block)"},
    "pending.differences_header": {"fr": "Differences (- = valeur actuelle, + = valeur du bloc en attente) :",
                                    "en": "Differences (- = current value, + = pending block value):"},
    "pending.no_diff": {"fr": "Aucune difference de propriete detectee entre les deux (le conflit "
                               "vient uniquement du Name/CustomIcon/TemplateRoot different).",
                         "en": "No property difference detected between the two (the conflict "
                               "only comes from a different Name/CustomIcon/TemplateRoot)."},
    "pending.active_block_header": {"fr": "--- Bloc actuellement actif (Id existant) ---",
                                     "en": "--- Currently active block (existing Id) ---"},
    "pending.pending_block_header": {"fr": "--- Bloc en attente (ce que tu vas activer) ---",
                                      "en": "--- Pending block (what you're about to activate) ---"},
    "pending.suggestions_label": {"fr": "Id libres suggeres (au-dessus du maximum utilise dans le scenario) : {ids}",
                                   "en": "Free Id suggestions (above the highest used in the scenario): {ids}"},
    "status.entry_duplicated_note": {"fr": " (emplacement d'origine introuvable, ajoutee a la racine)",
                                      "en": " (original location not found, added at the root)"},
    "check.refs_broken_title": {"fr": "References cassees detectees", "en": "Broken references detected"},
    "check.refs_broken_msg": {"fr": "{n} reference(s) 'Ref' ne correspondent a aucun 'Name' existant "
                                     "dans la copie de travail (l'heritage attendu ne fonctionnera pas en jeu) :\n\n"
                                     "{details}{more}",
                               "en": "{n} 'Ref' reference(s) don't match any existing 'Name' "
                                     "in the working copy (the expected inheritance won't work in-game):\n\n"
                                     "{details}{more}"},
    "check.refs_more": {"fr": "\n... et {n} autre(s)", "en": "\n... and {n} more"},
    "dup.name_required_msg": {"fr": "Si tu abandonnes l'Id, il faut un nouveau Name pour identifier "
                                     "ce bloc (sinon impossible de le distinguer de l'original).",
                               "en": "If you drop the Id, a new Name is required to identify "
                                     "this block (otherwise it can't be distinguished from the original)."},
    "dup.no_change_msg": {"fr": "Indique un nouvel Id et/ou un nouveau Name, different de l'original.",
                           "en": "Enter a new Id and/or a new Name, different from the original."},
    "ecf.single_block_conflict_title": {"fr": "Conflit d'Id", "en": "Id conflict"},
    "ecf.single_block_conflict_msg": {"fr": "Ce bloc partage un Id deja utilise par un element DIFFERENT dans la "
                                             "copie de travail. Il n'a PAS ete fusionne -- ajoute en fin de fichier, "
                                             "desactive (commente), a traiter manuellement.",
                                       "en": "This block shares an Id already used by a DIFFERENT element in the "
                                             "working copy. It was NOT merged -- added at the end of the file, "
                                             "disabled (commented out), to be handled manually."},
    "ecf.header_property_tooltip": {"fr": "Propriete d'en-tete du bloc (ex: Id, Name)",
                                     "en": "Block header property (e.g. Id, Name)"},
    "bbcode.select_text_hint": {"fr": "Selectionne d'abord une portion de texte dans la zone ci-dessus.",
                                 "en": "Select a portion of text in the area above first."},
    "dup.new_id": {"fr": "Nouvel Id :", "en": "New Id:"},
    "dup.new_name": {"fr": "Nouveau Name :", "en": "New Name:"},
    "dup.remove_id": {"fr": "Abandonner l'Id sur le nouveau bloc (l'identifier seulement par Name -- "
                             "necessite un nouveau Name ci-dessus)",
                       "en": "Drop the Id on the new block (identify it by Name only -- "
                             "requires a new Name above)"},
    "dup.duplicate": {"fr": "Dupliquer", "en": "Duplicate"},
    "dup.name_required": {"fr": "Name requis", "en": "Name required"},
    "dup.no_change": {"fr": "Aucun changement", "en": "No change"},

    # --- Dialogue Blocs en attente ---
    "pending.title": {"fr": "Blocs en attente (conflits d'Id)", "en": "Pending blocks (Id conflicts)"},
    "pending.compare_label": {"fr": "Comparaison (bloc actuel dans la copie de travail vs bloc en attente) :",
                               "en": "Comparison (current block in working copy vs pending block):"},
    "pending.new_id_label": {"fr": "Nouvel Id a assigner :", "en": "New Id to assign:"},
    "pending.activate": {"fr": "Activer avec cet Id", "en": "Activate with this Id"},
    "pending.id_missing": {"fr": "Id manquant", "en": "Missing Id"},
    "pending.id_missing_msg": {"fr": "Indique un Id.", "en": "Enter an Id."},
    "pending.id_already_used": {"fr": "Id deja utilise", "en": "Id already in use"},
    "pending.id_already_used_confirm": {"fr": "L'Id {id} semble deja utilise ailleurs dans le scenario. Continuer quand meme ?",
                                         "en": "Id {id} seems to already be used elsewhere in the scenario. Continue anyway?"},

    # --- Dialogue Filtrer par propriete ---
    "propfilter.title": {"fr": "Filtrer par propriete", "en": "Filter by property"},
    "propfilter.instructions": {"fr": "Coche une ou plusieurs proprietes : seuls les blocs\n"
                                       "possedant TOUTES les proprietes cochees restent visibles\n"
                                       "dans l'arbre du fichier ouvert.",
                                 "en": "Check one or more properties: only blocks that\n"
                                       "have ALL checked properties stay visible\n"
                                       "in the open file's tree."},
    "propfilter.clear_all": {"fr": "Tout decocher (afficher tous les blocs)",
                              "en": "Uncheck all (show all blocks)"},

    # --- Titres generiques de messages ---
    "err.title": {"fr": "Erreur", "en": "Error"},
    "err.read_title": {"fr": "Erreur de lecture", "en": "Read error"},
    "err.no_project_title": {"fr": "Aucun projet", "en": "No project"},
    "err.no_project_msg": {"fr": "Ouvre d'abord un projet.", "en": "Open a project first."},
    "err.no_file_title": {"fr": "Aucun fichier", "en": "No file"},

    # --- Blocs en attente ---
    "pending.none_title": {"fr": "Blocs en attente", "en": "Pending blocks"},
    "pending.none_msg": {"fr": "Aucun bloc en attente (conflit d'Id) trouve dans la copie de travail.",
                          "en": "No pending block (Id conflict) found in the working copy."},
    "pending.not_found_msg": {"fr": "Le bloc en attente n'a plus ete retrouve (fichier modifie entre-temps ?).",
                               "en": "The pending block could no longer be found (was the file modified meanwhile?)."},
    "pending.cannot_activate_msg": {"fr": "Impossible d'activer ce bloc (motif 'Id:' introuvable dans son texte).",
                                     "en": "Could not activate this block ('Id:' pattern not found in its text)."},
    "pending.activation_error": {"fr": "Erreur pendant l'activation", "en": "Error during activation"},
    "pending.activated_title": {"fr": "Bloc active", "en": "Block activated"},
    "pending.activated_msg": {"fr": "Le bloc est maintenant actif avec Id={id} dans {file}.\n"
                                     "Pense a relancer la verification des references si ce bloc en concernait.",
                               "en": "The block is now active with Id={id} in {file}.\n"
                                     "Remember to re-run the reference check if this block was involved."},

    # --- Verification des references ---
    "check.no_ecf_found": {"fr": "Aucun fichier .ecf trouve dans Configuration.",
                            "en": "No .ecf file found in Configuration."},
    "check.verification_error": {"fr": "Erreur pendant la verification", "en": "Error during check"},
    "check.refs_title": {"fr": "Verification des references", "en": "Reference check"},
    "check.refs_ok": {"fr": "Aucune reference cassee trouvee sur {n} fichier(s) verifie(s).",
                       "en": "No broken reference found across {n} checked file(s)."},

    # --- Projets ---
    "err.create_project": {"fr": "Impossible de creer le projet", "en": "Could not create the project"},
    "recent.none_title": {"fr": "Aucun projet recent", "en": "No recent project"},
    "recent.none_msg": {"fr": "Aucun projet recent enregistre -- utilise 'Nouveau projet...'",
                         "en": "No recent project saved -- use 'New project...'"},
    "recent.resume_error": {"fr": "Impossible de reprendre ce projet", "en": "Could not resume this project"},
    "recent.resume_error_hint": {"fr": "Il a peut-etre ete deplace ou supprime.",
                                  "en": "It may have been moved or deleted."},

    # --- Fusion ---
    "merge.empty_folder_title": {"fr": "Dossier vide", "en": "Empty folder"},
    "merge.empty_folder_msg": {"fr": "Aucun fichier a fusionner dans ce dossier.",
                                "en": "No file to merge in this folder."},
    "merge.folder_error": {"fr": "Impossible de fusionner le dossier", "en": "Could not merge the folder"},
    "merge.file_error": {"fr": "Impossible de copier/fusionner {file}", "en": "Could not copy/merge {file}"},
    "merge.confirm_title": {"fr": "Confirmer", "en": "Confirm"},
    "merge.confirm_folder_msg": {"fr": "Fusionner {n} fichier(s) de '{folder}' (et sous-dossiers) vers la copie de travail ?",
                                  "en": "Merge {n} file(s) from '{folder}' (and subfolders) into the working copy?"},
    "merge.id_conflicts_title": {"fr": "Conflits d'Id detectes", "en": "Id conflicts detected"},
    "merge.id_conflicts_folder_msg": {"fr": "{n} bloc(s) au total n'ont pas ete fusionnes (Id partage "
                                             "avec un materiel different) -- ajoutes desactives dans leurs "
                                             "fichiers respectifs pour revue manuelle :\n\n{details}{more}",
                                       "en": "{n} block(s) in total were not merged (Id shared "
                                             "with different content) -- added disabled in their "
                                             "respective files for manual review:\n\n{details}{more}"},
    "merge.id_conflicts_file_msg": {"fr": "{n} bloc(s) partagent un Id deja utilise par un element "
                                           "DIFFERENT dans la copie de travail. Ils n'ont PAS ete fusionnes -- "
                                           "ajoutes en fin de fichier, desactives (commentes), a traiter "
                                           "manuellement (reassigner un Id libre) :\n\n{details}",
                                     "en": "{n} block(s) share an Id already used by a DIFFERENT "
                                           "element in the working copy. They were NOT merged -- "
                                           "added at the end of the file, disabled (commented out), to be "
                                           "handled manually (reassign a free Id):\n\n{details}"},
    "merge.id_conflicts_more": {"fr": "\n... et {n} autre(s)", "en": "\n... and {n} more"},

    # --- YAML : suppression d'entree ---
    "yaml.no_selection_title": {"fr": "Aucune selection", "en": "No selection"},
    "yaml.no_selection_msg": {"fr": "Selectionne d'abord une entree dans l'arbre.",
                               "en": "Select an entry in the tree first."},
    "yaml.confirm_delete": {"fr": "Supprimer '{name}' ?", "en": "Delete '{name}'?"},

    # --- ECF : selection/suppression de bloc ---
    "ecf.no_block_title": {"fr": "Aucun bloc", "en": "No block"},
    "ecf.no_block_msg": {"fr": "Selectionne d'abord un bloc dans l'arbre.",
                          "en": "Select a block in the tree first."},
    "ecf.confirm_delete_block": {"fr": "Supprimer le bloc {name} ?", "en": "Delete block {name}?"},
    "ecf.delete_block_action": {"fr": "Supprimer ce bloc", "en": "Delete this block"},

    # --- ECF : ajout bloc/propriete (QInputDialog) ---
    "ecf.add_property_title": {"fr": "Ajouter une propriete", "en": "Add a property"},
    "ecf.property_name_label": {"fr": "Nom de la propriete :", "en": "Property name:"},
    "ecf.property_value_label": {"fr": "Valeur de '{key}' :\n(pour ajouter d'autres proprietes sur la meme ligne, "
                                        "ex: Name_X -> param1/param2, tape 'valeur, param1: X, param2: \"Y,Z\"' "
                                        "-- guillemets obligatoires si une valeur contient une virgule)",
                                  "en": "Value of '{key}':\n(to add more properties on the same line, "
                                        "e.g. Name_X -> param1/param2, type 'value, param1: X, param2: \"Y,Z\"' "
                                        "-- quotes required if a value contains a comma)"},
    "ecf.add_block_title": {"fr": "Ajouter un bloc", "en": "Add a block"},
    "ecf.block_kind_label": {"fr": "Genre du bloc (ex: Block) :", "en": "Block kind (e.g. Block):"},
    "ecf.id_label": {"fr": "Id :", "en": "Id:"},
    "ecf.name_optional_label": {"fr": "Name (optionnel) :", "en": "Name (optional):"},
    "ecf.delete_property_action": {"fr": "Supprimer cette propriete", "en": "Delete this property"},
    "ctx.translate_cell_to": {"fr": "Traduire cette cellule vers... (-> copie de travail)",
                               "en": "Translate this cell to... (-> working copy)"},

    # --- Options : nom d'auteur ---
    "author.title": {"fr": "Nom pour les annotations", "en": "Name for annotations"},
    "author.label": {"fr": "Ce nom apparaitra dans les commentaires '# original: ... -- Mod par ...' :",
                      "en": "This name will appear in the traceability comments '# original: ... -- Mod by ...':"},

    # --- YAML : ajout d'entree ---
    "yaml.add_entry_title": {"fr": "Ajouter une entree", "en": "Add an entry"},
    "yaml.key_label": {"fr": "Cle (laisser vide pour un item de sequence) :",
                        "en": "Key (leave empty for a sequence item):"},
    "yaml.value_label": {"fr": "Valeur :", "en": "Value:"},
    "yaml.duplicate_action": {"fr": "Dupliquer avec une nouvelle cle/valeur vers la copie de travail...",
                               "en": "Duplicate with a new key/value to working copy..."},

    # --- Menu contextuel bloc ECF (vue comparative / source) ---
    "ecf.merge_block_action": {"fr": "Copier / fusionner ce bloc ({label}) vers la copie de travail",
                                "en": "Copy / merge this block ({label}) to working copy"},
    "ecf.duplicate_subblock_action": {"fr": "Dupliquer ce sous-bloc (dans le meme parent) vers la copie de travail...",
                                       "en": "Duplicate this sub-block (in the same parent) to working copy..."},
    "ecf.duplicate_block_action": {"fr": "Dupliquer avec un nouvel Id vers la copie de travail...",
                                    "en": "Duplicate with a new Id to working copy..."},

    # --- Menus contextuels fichier/ligne/entree (f-strings ratees a la premiere passe) ---
    "csv.copy_row_action": {"fr": "Copier cette ligne (cle '{key}') vers la copie de travail",
                             "en": "Copy this row (key '{key}') to working copy"},
    "csv.duplicate_row_action": {"fr": "Dupliquer avec une nouvelle cle vers la copie de travail...",
                                  "en": "Duplicate with a new key to working copy..."},
    "file.merge_action": {"fr": "Copier / fusionner '{name}' vers la copie de travail",
                           "en": "Copy / merge '{name}' to working copy"},
    "folder.merge_action": {"fr": "Fusionner le dossier '{name}' (et sous-dossiers) vers la copie de travail",
                             "en": "Merge folder '{name}' (and subfolders) to working copy"},
    "file.duplicate_action": {"fr": "Dupliquer '{name}' avec un nouveau nom vers la copie de travail...",
                               "en": "Duplicate '{name}' with a new name to working copy..."},
    "dupfile.title": {"fr": "Dupliquer le fichier", "en": "Duplicate file"},
    "dupfile.new_name_label": {"fr": "Nouveau nom de fichier (dans le meme dossier que l'original) :",
                                "en": "New filename (in the same folder as the original):"},
    "dupfile.exists_title": {"fr": "Fichier deja existant", "en": "File already exists"},
    "dupfile.exists_msg": {"fr": "'{name}' existe deja dans la copie de travail -- choisis un autre nom.",
                            "en": "'{name}' already exists in the working copy -- choose another name."},
    "status.file_duplicated": {"fr": "Fichier duplique sous le nom '{name}' dans la copie de travail",
                                "en": "File duplicated as '{name}' in the working copy"},
    "file.delete_action": {"fr": "Supprimer '{name}'", "en": "Delete '{name}'"},
    "folder.delete_action": {"fr": "Supprimer le dossier '{name}' (et son contenu)",
                              "en": "Delete folder '{name}' (and its content)"},
    "delete.confirm_file_msg": {"fr": "Supprimer definitivement '{name}' de la copie de travail ? "
                                       "Cette action est irreversible (le fichier original de Scenario "
                                       "A/B n'est pas touche, tu peux le refusionner si besoin).",
                                 "en": "Permanently delete '{name}' from the working copy? "
                                       "This action cannot be undone (the original file in Scenario "
                                       "A/B is untouched, you can merge it again if needed)."},
    "delete.confirm_folder_msg": {"fr": "Supprimer definitivement le dossier '{name}' et TOUT son contenu "
                                         "de la copie de travail ? Cette action est irreversible.",
                                   "en": "Permanently delete the folder '{name}' and ALL its content "
                                         "from the working copy? This action cannot be undone."},
    "status.file_deleted": {"fr": "'{name}' supprime de la copie de travail", "en": "'{name}' deleted from the working copy"},
    "status.folder_deleted": {"fr": "Dossier '{name}' supprime de la copie de travail",
                               "en": "Folder '{name}' deleted from the working copy"},
    "delete.error": {"fr": "Impossible de supprimer", "en": "Could not delete"},

    # --- Annulation globale (niveau espace de travail) ---
    "wsundo.button": {"fr": "Annuler la derniere action", "en": "Undo last action"},
    "wsundo.tooltip_empty": {"fr": "Rien a annuler pour l'instant", "en": "Nothing to undo yet"},
    "wsundo.tooltip_action": {"fr": "Annuler : {label}", "en": "Undo: {label}"},
    "wsundo.status_done": {"fr": "Annule : {label}", "en": "Undone: {label}"},
    "wsundo.merge_file": {"fr": "Copie/fusion de '{name}'", "en": "Copy/merge of '{name}'"},
    "wsundo.merge_folder": {"fr": "Fusion du dossier '{name}'", "en": "Merge of folder '{name}'"},
    "wsundo.duplicate_file": {"fr": "Duplication de fichier '{name}'", "en": "File duplication '{name}'"},
    "wsundo.delete_file": {"fr": "Suppression de '{name}'", "en": "Deletion of '{name}'"},
    "wsundo.delete_folder": {"fr": "Suppression du dossier '{name}'", "en": "Deletion of folder '{name}'"},
    "wsundo.duplicate_block": {"fr": "Duplication de bloc dans '{name}'", "en": "Block duplication in '{name}'"},
    "wsundo.copy_block": {"fr": "Copie de bloc dans '{name}'", "en": "Block copy in '{name}'"},
    "wsundo.copy_row": {"fr": "Copie de ligne dans '{name}'", "en": "Row copy in '{name}'"},
    "wsundo.duplicate_row": {"fr": "Duplication de ligne dans '{name}'", "en": "Row duplication in '{name}'"},
    "wsundo.copy_entry": {"fr": "Copie d'entree dans '{name}'", "en": "Entry copy in '{name}'"},
    "wsundo.duplicate_entry": {"fr": "Duplication d'entree dans '{name}'", "en": "Entry duplication in '{name}'"},
    "wsundo.translate_cell": {"fr": "Traduction dans '{name}'", "en": "Translation in '{name}'"},
    "wsundo.activate_pending": {"fr": "Activation de bloc en attente dans '{name}'", "en": "Pending block activation in '{name}'"},

    # --- Recherche CSV ---
    "search.no_results": {"fr": "Aucun resultat", "en": "No results"},
    "search.column_all": {"fr": "Toutes les colonnes", "en": "All columns"},
    "search.in_column_action": {"fr": "Rechercher dans '{name}'...", "en": "Search in '{name}'..."},
    "csv.search_placeholder": {"fr": "Rechercher... puis Entree", "en": "Search... then Enter"},
    "csv.search_scope_label": {"fr": "dans :", "en": "in:"},

    # --- Comparaison de scenarios ---
    "menu.file.compare": {"fr": "Comparer deux scenarios...", "en": "Compare two scenarios..."},
    "compare.title": {"fr": "Comparer deux scenarios", "en": "Compare two scenarios"},
    "compare.scenario_a": {"fr": "Scenario A (ancien / reference) :", "en": "Scenario A (old / reference):"},
    "compare.scenario_b": {"fr": "Scenario B (nouveau / mis a jour) :", "en": "Scenario B (new / updated):"},
    "compare.run": {"fr": "Comparer", "en": "Compare"},
    "compare.choose_folder": {"fr": "Choisir un dossier de scenario", "en": "Choose a scenario folder"},
    "compare.both_required": {"fr": "Choisis les deux dossiers de scenario a comparer.",
                               "en": "Choose both scenario folders to compare."},
    "compare.progress": {"fr": "Comparaison en cours...", "en": "Comparing..."},
    "compare.summary": {"fr": "{added} ajoute(s)   {removed} supprime(s)   {modified} modifie(s)   {unchanged} identique(s)",
                         "en": "{added} added   {removed} removed   {modified} modified   {unchanged} unchanged"},
    "compare.show_unchanged": {"fr": "Afficher aussi les fichiers identiques", "en": "Also show unchanged files"},
    "compare.export": {"fr": "Exporter le rapport...", "en": "Export report..."},
    "compare.export_title": {"fr": "Enregistrer le rapport de comparaison", "en": "Save comparison report"},
    "compare.export_done_title": {"fr": "Rapport exporte", "en": "Report exported"},
    "compare.export_done_msg": {"fr": "Rapport enregistre dans {path}", "en": "Report saved to {path}"},
    "compare.select_file_hint": {"fr": "Selectionne un fichier modifie dans l'arbre pour voir le detail.",
                                  "en": "Select a modified file in the tree to see the detail."},
    "compare.no_detail": {"fr": "(pas de detail disponible pour ce type de fichier -- "
                                 "contenu binaire ou format non structure)",
                           "en": "(no detail available for this file type -- "
                                 "binary content or unstructured format)"},
    "compare.error_title": {"fr": "Erreur de comparaison", "en": "Comparison error"},

    # --- Fusion desactivable ---
    "menu.options.merge_enabled": {"fr": "Autoriser la fusion (experimental, desactive par defaut)",
                                    "en": "Allow merging (experimental, disabled by default)"},
    "merge.disabled_title": {"fr": "Fusion desactivee", "en": "Merging disabled"},
    "merge.disabled_msg": {"fr": "La fusion est desactivee par defaut (trop de cas particuliers pour "
                                  "etre fiable a 100%, risque de casser le scenario). Utilise plutot "
                                  "'Dupliquer', qui cree toujours une entree nouvelle et independante, "
                                  "sans risque d'ecraser quoi que ce soit.\n\n"
                                  "Tu peux reactiver la fusion dans Options si tu en as vraiment besoin.",
                            "en": "Merging is disabled by default (too many edge cases to be 100% "
                                  "reliable, risk of breaking the scenario). Use 'Duplicate' instead, "
                                  "which always creates a new, independent entry with no risk of "
                                  "overwriting anything.\n\n"
                                  "You can re-enable merging in Options if you really need it."},

    # --- Ouverture/changement du Scenario B a tout moment ---
    "menu.file.open_scenario_b": {"fr": "Ouvrir un Scenario B...", "en": "Open a Scenario B..."},
    "menu.file.change_scenario_b": {"fr": "Changer le Scenario B...", "en": "Change Scenario B..."},
    "menu.file.remove_scenario_b": {"fr": "Retirer le Scenario B", "en": "Remove Scenario B"},
    "scenariob.choose_folder": {"fr": "Choisir le dossier du Scenario B", "en": "Choose the Scenario B folder"},
    "scenariob.confirm_change_title": {"fr": "Changer le Scenario B", "en": "Change Scenario B"},
    "scenariob.confirm_change_msg": {"fr": "Remplacer le Scenario B actuel ('{old}') par '{new}' ?",
                                      "en": "Replace the current Scenario B ('{old}') with '{new}'?"},
    "scenariob.confirm_remove_title": {"fr": "Retirer le Scenario B", "en": "Remove Scenario B"},
    "scenariob.confirm_remove_msg": {"fr": "Retirer le Scenario B ('{name}') de ce projet ? "
                                            "La copie de travail n'est pas affectee.",
                                      "en": "Remove Scenario B ('{name}') from this project? "
                                            "The working copy is not affected."},
    "status.scenario_b_set": {"fr": "Scenario B defini : {name}", "en": "Scenario B set: {name}"},
    "status.scenario_b_removed": {"fr": "Scenario B retire", "en": "Scenario B removed"},

    # --- Desactivation manuelle de bloc (test d'elimination de causes) ---
    "ecf.disable_block_action": {"fr": "Desactiver ce bloc (test)", "en": "Disable this block (test)"},
    "ecf.confirm_disable_block": {"fr": "Desactiver '{name}' ? Le bloc sera commente (garde dans le fichier, "
                                         "inactif en jeu) -- reactivable a tout moment via 'Blocs desactives (test)'.",
                                   "en": "Disable '{name}'? The block will be commented out (kept in the "
                                         "file, inactive in-game) -- can be re-enabled anytime via "
                                         "'Disabled blocks (test)'."},
    "status.block_disabled": {"fr": "'{name}' desactive (commente)", "en": "'{name}' disabled (commented out)"},
    "ecf.disabled_blocks_menu": {"fr": "Blocs desactives (test)...", "en": "Disabled blocks (test)..."},
    "ecf.disabled_blocks_title": {"fr": "Blocs desactives (test)", "en": "Disabled blocks (test)"},
    "ecf.disabled_blocks_intro": {"fr": "Blocs actuellement desactives (commentes) dans ce fichier -- "
                                         "utile pour tester l'elimination de causes probables d'un bug. "
                                         "Selectionne-en un puis clique 'Reactiver' pour le remettre.",
                                   "en": "Blocks currently disabled (commented out) in this file -- "
                                         "useful for testing to eliminate probable causes of a bug. "
                                         "Select one then click 'Re-enable' to restore it."},
    "ecf.disabled_blocks_none": {"fr": "Aucun bloc desactive dans ce fichier.", "en": "No disabled blocks in this file."},
    "ecf.reactivate_block": {"fr": "Reactiver", "en": "Re-enable"},
    "status.block_reenabled": {"fr": "'{name}' reactive", "en": "'{name}' re-enabled"},

    # --- Menu Fichier : nouvelles entrees sauvegarde ---
    "menu.file.backup_scenario": {"fr": "Sauvegarder un scenario (avant mise a jour)...",
                                   "en": "Back up a scenario (before update)..."},
    "menu.file.repair_permissions": {"fr": "Reparer les permissions de la copie de travail",
                                      "en": "Repair working copy permissions"},
    "repair.no_project_msg": {"fr": "Ouvre d'abord un projet.", "en": "Open a project first."},
    "repair.done_title": {"fr": "Permissions reparees", "en": "Permissions repaired"},
    "repair.done_msg": {"fr": "La copie de travail est de nouveau entierement modifiable "
                              "(et supprimable).",
                         "en": "The working copy is fully writable (and deletable) again."},
    "save.error_title": {"fr": "Erreur d'enregistrement", "en": "Save error"},
    "save.error_msg": {"fr": "Impossible d'enregistrer '{name}' :\n{error}\n\n"
                              "Si c'est une erreur de permission, essaie Fichier > "
                              "'Reparer les permissions de la copie de travail'.",
                        "en": "Could not save '{name}':\n{error}\n\n"
                              "If this is a permission error, try File > "
                              "'Repair working copy permissions'."},

    # --- Explication de l'en-tete ECF (glossaire) ---
    "ecf.header_toggle_show": {"fr": "Voir l'explication des proprietes de ce fichier",
                                "en": "Show property explanations for this file"},
    "ecf.header_toggle_hide": {"fr": "Masquer l'explication des proprietes",
                                "en": "Hide property explanations"},
    "ecf.header_none": {"fr": "Ce fichier ne contient pas de commentaires d'en-tete.",
                         "en": "This file has no header comments."},
    "ecf.header_glossary_intro": {"fr": "Explication clarifiee (pas une traduction mot a "
                                         "mot) des commentaires techniques presents en "
                                         "tete de ce fichier :",
                                   "en": "Clarified explanation (not a word-for-word "
                                         "translation) of the technical comments found "
                                         "at the top of this file:"},
    "ecf.header_raw_toggle": {"fr": "Voir le texte original (anglais)",
                               "en": "Show original text (English)"},
    "ecf.header_translate_btn": {"fr": "Traduire automatiquement en francais",
                                  "en": "Auto-translate to French"},
    "ecf.header_translating": {"fr": "Traduction en cours...", "en": "Translating..."},
    "ecf.header_translate_error": {"fr": "Echec de la traduction automatique : {error}",
                                    "en": "Automatic translation failed: {error}"},
    "ecf.col_property": {"fr": "Propriete", "en": "Property"},
    "ecf.col_value": {"fr": "Valeur", "en": "Value"},
    "ecf.col_type": {"fr": "Type", "en": "Type"},
    "ecf.col_item_value": {"fr": "Nom / Groupe", "en": "Name / Group"},
    "btn.add_row_table": {"fr": "+ Ligne", "en": "+ Row"},
    "ecf.add_row_title": {"fr": "Ajouter une ligne", "en": "Add a row"},
    "ecf.add_row_type_label": {"fr": "Type :", "en": "Type:"},
    "ecf.add_row_value_label": {"fr": "Nom / Groupe :", "en": "Name / Group:"},
    "ecf.add_row_value_required": {"fr": "Indique un nom ou un groupe.", "en": "Enter a name or group."},
    "status.row_added_numbered": {"fr": "'{key}' ajoute (numerote automatiquement)",
                                   "en": "'{key}' added (automatically numbered)"},
    "menu.file.manage_saves": {"fr": "Gerer mes sauvegardes de partie...",
                                "en": "Manage my savegame backups..."},

    # --- Dialogue de sauvegarde generique (scenario ou partie) ---
    "backup.title_scenario": {"fr": "Sauvegarder un scenario", "en": "Back up a scenario"},
    "backup.title_savegame": {"fr": "Sauvegardes de partie", "en": "Savegame backups"},
    "backup.source_scenario": {"fr": "Dossier du scenario a sauvegarder :", "en": "Scenario folder to back up:"},
    "backup.source_savegame": {"fr": "Dossier de la partie a sauvegarder :", "en": "Savegame folder to back up:"},
    "backup.storage_folder": {"fr": "Dossier ou stocker les sauvegardes :", "en": "Folder to store backups in:"},
    "backup.label": {"fr": "Nom (optionnel, ex: 'avant maj 2.0') :", "en": "Name (optional, e.g. 'before update 2.0'):"},
    "backup.create": {"fr": "Sauvegarder maintenant", "en": "Back up now"},
    "backup.existing_list": {"fr": "Sauvegardes existantes :", "en": "Existing backups:"},
    "backup.restore": {"fr": "Restaurer cette sauvegarde...", "en": "Restore this backup..."},
    "backup.delete": {"fr": "Supprimer cette sauvegarde", "en": "Delete this backup"},
    "backup.open_folder": {"fr": "Ouvrir le dossier", "en": "Open folder"},
    "backup.compare_with": {"fr": "Comparer avec...", "en": "Compare with..."},
    "backup.none_yet": {"fr": "Aucune sauvegarde pour l'instant.", "en": "No backups yet."},
    "backup.source_required": {"fr": "Choisis le dossier a sauvegarder.", "en": "Choose the folder to back up."},
    "backup.storage_required": {"fr": "Choisis un dossier ou stocker les sauvegardes.",
                                 "en": "Choose a folder to store backups in."},
    "backup.created_title": {"fr": "Sauvegarde creee", "en": "Backup created"},
    "backup.created_msg": {"fr": "Sauvegarde creee avec succes dans :\n{path}",
                            "en": "Backup successfully created in:\n{path}"},
    "backup.error": {"fr": "Erreur pendant la sauvegarde", "en": "Error during backup"},
    "backup.select_one": {"fr": "Selectionne d'abord une sauvegarde dans la liste.",
                           "en": "Select a backup in the list first."},
    "backup.confirm_delete_title": {"fr": "Confirmer la suppression", "en": "Confirm deletion"},
    "backup.confirm_delete_msg": {"fr": "Supprimer definitivement la sauvegarde '{label}' ? "
                                         "Cette action est irreversible.",
                                   "en": "Permanently delete the backup '{label}'? "
                                         "This action cannot be undone."},
    "backup.restore_title": {"fr": "Restaurer la sauvegarde", "en": "Restore backup"},
    "backup.restore_destination": {"fr": "Dossier de destination (sera entierement remplace) :",
                                    "en": "Destination folder (will be entirely replaced):"},
    "backup.restore_warning": {"fr": "Le contenu actuel du dossier de destination sera ENTIEREMENT "
                                      "remplace par cette sauvegarde. Si le dossier de destination "
                                      "contient deja quelque chose, une sauvegarde de securite automatique "
                                      "sera creee avant, par precaution.",
                                "en": "The current content of the destination folder will be ENTIRELY "
                                      "replaced by this backup. If the destination folder already "
                                      "contains something, an automatic safety backup will be created "
                                      "first, just in case."},
    "backup.confirm_restore": {"fr": "Confirmer la restauration", "en": "Confirm restore"},
    "backup.restore_done_title": {"fr": "Restauration terminee", "en": "Restore complete"},
    "backup.restore_done_msg": {"fr": "Sauvegarde restauree avec succes dans :\n{path}",
                                 "en": "Backup successfully restored to:\n{path}"},
    "backup.restore_done_with_safety": {"fr": "\n\nUne sauvegarde de securite de l'ancien contenu "
                                                "a ete creee : '{label}'",
                                         "en": "\n\nA safety backup of the previous content "
                                               "was created: '{label}'"},
    "backup.restore_error": {"fr": "Erreur pendant la restauration", "en": "Error during restore"},

    # --- Format de diff ECF (reutilise par comparaison de scenarios + blocs en attente) ---
    "diff.new": {"fr": "(nouveau)", "en": "(new)"},
    "diff.removed": {"fr": "(supprime)", "en": "(removed)"},
    "diff.modified": {"fr": "(modifie)", "en": "(modified)"},
    "diff.new_property": {"fr": "(nouvelle propriete)", "en": "(new property)"},
    "diff.removed_property": {"fr": "(propriete supprimee)", "en": "(removed property)"},
    "diff.row_removed": {"fr": "- Ligne '{key}'  (supprimee)", "en": "- Row '{key}'  (removed)"},
    "diff.row_added": {"fr": "+ Ligne '{key}'  (nouvelle)", "en": "+ Row '{key}'  (new)"},
    "diff.row_modified": {"fr": "~ Ligne '{key}'  (modifiee)", "en": "~ Row '{key}'  (modified)"},
    "diff.yaml_removed": {"fr": "- {path}  (supprime)", "en": "- {path}  (removed)"},
    "diff.yaml_added": {"fr": "+ {path}: {value}  (nouveau)", "en": "+ {path}: {value}  (new)"},
    "report.title": {"fr": "Comparaison de scenarios", "en": "Scenario comparison"},
    "report.summary": {"fr": "Resume : {added} fichier(s) ajoute(s), {removed} supprime(s), "
                              "{modified} modifie(s), {unchanged} identique(s)",
                        "en": "Summary: {added} file(s) added, {removed} removed, "
                              "{modified} modified, {unchanged} unchanged"},
    "report.scenario_a_line": {"fr": "Scenario A (reference) : {name}  --  {path}",
                                "en": "Scenario A (reference): {name}  --  {path}"},
    "report.scenario_b_line": {"fr": "Scenario B (compare a A) : {name}  --  {path}",
                                "en": "Scenario B (compared to A): {name}  --  {path}"},
    "report.direction_note": {"fr": "Les differences ci-dessous sont exprimees du point de vue de B : "
                                     "'+' = ajoute dans B, '-' = present dans A mais absent de B (supprime), "
                                     "'~' = different entre A et B.",
                               "en": "The differences below are expressed from B's perspective: "
                                     "'+' = added in B, '-' = present in A but missing from B (removed), "
                                     "'~' = different between A and B."},
    "compare.direction_label": {"fr": "Comparaison de {name_b} par rapport a {name_a}",
                                 "en": "Comparing {name_b} against {name_a}"},
    "yaml.copy_entry_action": {"fr": "Copier cette entree ({label}) vers la copie de travail",
                                "en": "Copy this entry ({label}) to working copy"},
    "csv.duplicate_title": {"fr": "Dupliquer avec une nouvelle cle", "en": "Duplicate with a new key"},
    "csv.duplicate_current_key": {"fr": "Cle actuelle : '{key}'\n\nNouvelle cle :",
                                   "en": "Current key: '{key}'\n\nNew key:"},
    "yaml.duplicate_title": {"fr": "Dupliquer avec une nouvelle cle/valeur", "en": "Duplicate with a new key/value"},
    "yaml.duplicate_current_value": {"fr": "Valeur actuelle : '{value}'\n\nNouvelle valeur :",
                                      "en": "Current value: '{value}'\n\nNew value:"},

    # --- Panneaux du bas (arborescence des 3 scenarios) ---
    "panel.scenario_a": {"fr": "Scenario A (lecture seule)", "en": "Scenario A (read-only)"},
    "panel.working_copy": {"fr": "Copie de travail (modifiable)", "en": "Working copy (editable)"},
    "panel.scenario_b": {"fr": "Scenario B (lecture seule)", "en": "Scenario B (read-only)"},
    "panel.scenario_a_named": {"fr": "Scenario A (lecture seule) -- {name}", "en": "Scenario A (read-only) -- {name}"},
    "panel.working_copy_named": {"fr": "Copie de travail (modifiable) -- {name}", "en": "Working copy (editable) -- {name}"},
    "panel.scenario_b_named": {"fr": "Scenario B (lecture seule) -- {name}", "en": "Scenario B (read-only) -- {name}"},

    # --- Fenetres de progression ---
    "progress.please_wait": {"fr": "Veuillez patienter", "en": "Please wait"},

    # --- Suggestions Id (fenetre duplication) ---
    "dup.suggestions_label": {"fr": "Suggestions libres : {ids}", "en": "Free suggestions: {ids}"},

    # --- Fenetre resultat de traduction ---
    "trans.dialog_title": {"fr": "Traduction", "en": "Translation"},
    "trans.original_label": {"fr": "Original :", "en": "Original:"},
    "trans.translation_label": {"fr": "Traduction :", "en": "Translation:"},
    "trans.close_no_apply": {"fr": "Fermer (ne pas appliquer)", "en": "Close (don't apply)"},

    # --- Fenetre BBCode ---
    "bbcode.title": {"fr": "Mise en forme BBCode", "en": "BBCode formatting"},
    "bbcode.instructions": {"fr": "Selectionne une portion de texte ci-dessous, puis clique une "
                                   "couleur ou un style pour l'appliquer :",
                             "en": "Select a portion of text below, then click a "
                                   "color or a style to apply it:"},
    "bbcode.colors_label": {"fr": "Couleurs :", "en": "Colors:"},
    "bbcode.apply_to_cell": {"fr": "Appliquer a la cellule", "en": "Apply to cell"},
    "bbcode.bold": {"fr": "Gras", "en": "Bold"},
    "bbcode.italic": {"fr": "Italique", "en": "Italic"},
    "bbcode.underline": {"fr": "Souligne", "en": "Underline"},
    "trans.place_in": {"fr": "Placer dans {destination}", "en": "Place in {destination}"},
    "trans.replace_cell": {"fr": "Remplacer la cellule par ce texte", "en": "Replace the cell with this text"},

    # --- Duplication ---
    "dup.file_missing_title": {"fr": "Fichier absent", "en": "File missing"},
    "dup.file_missing_msg": {"fr": "{file} n'existe pas encore dans la copie de travail -- "
                                    "importe d'abord le fichier entier.",
                              "en": "{file} doesn't exist yet in the working copy -- "
                                    "import the whole file first."},
    "dup.block_error": {"fr": "Impossible de dupliquer ce bloc", "en": "Could not duplicate this block"},
    "dup.parent_not_found_title": {"fr": "Bloc parent introuvable", "en": "Parent block not found"},
    "dup.parent_not_found_msg": {"fr": "Ce bloc est imbrique dans un autre (ex: un 'Mode' dans un 'Item'), "
                                        "mais son parent n'existe pas encore dans {file} -- copie/fusionne "
                                        "d'abord le bloc parent avant de dupliquer ce sous-bloc.",
                                  "en": "This block is nested inside another (e.g. a 'Mode' inside an 'Item'), "
                                        "but its parent doesn't exist yet in {file} -- copy/merge "
                                        "the parent block first before duplicating this sub-block."},
    "dup.already_used_title": {"fr": "Deja utilise", "en": "Already in use"},
    "dup.already_used_msg": {"fr": "Cette identite (Id ou Name) est deja utilisee dans {file} -- "
                                    "choisis une autre valeur.",
                              "en": "This identity (Id or Name) is already used in {file} -- "
                                    "choose another value."},
    "copy.block_error": {"fr": "Impossible de copier ce bloc", "en": "Could not copy this block"},
    "copy.row_error": {"fr": "Impossible de copier cette ligne", "en": "Could not copy this row"},
    "dup.key_required_title": {"fr": "Cle requise", "en": "Key required"},
    "dup.key_required_msg": {"fr": "Une cle est necessaire pour identifier cette nouvelle ligne "
                                    "(1ere colonne du fichier).",
                              "en": "A key is required to identify this new row "
                                    "(the file's first column)."},
    "dup.row_error": {"fr": "Impossible de dupliquer cette ligne", "en": "Could not duplicate this row"},
    "dup.key_exists_title": {"fr": "Cle deja utilisee", "en": "Key already in use"},
    "dup.key_exists_msg": {"fr": "La cle '{key}' existe deja dans {file} -- choisis-en une autre.",
                            "en": "The key '{key}' already exists in {file} -- choose another one."},
    "copy.entry_error": {"fr": "Impossible de copier cette entree", "en": "Could not copy this entry"},
    "dup.value_required_title": {"fr": "Valeur requise", "en": "Value required"},
    "dup.value_required_msg": {"fr": "Une nouvelle cle/valeur est necessaire pour distinguer "
                                      "cette entree de l'originale.",
                                "en": "A new key/value is required to distinguish "
                                      "this entry from the original."},
    "dup.entry_error": {"fr": "Impossible de dupliquer cette entree", "en": "Could not duplicate this entry"},
    "dup.value_exists_title": {"fr": "Deja utilisee", "en": "Already in use"},
    "dup.value_exists_msg": {"fr": "'{value}' existe deja dans {file} -- choisis autre chose.",
                              "en": "'{value}' already exists in {file} -- choose something else."},

    # --- Traduction ---
    "trans.unavailable_title": {"fr": "Traduction indisponible", "en": "Translation unavailable"},
    "trans.unavailable_msg": {"fr": "deep-translator n'est pas installe.\nLance : pip install deep-translator",
                               "en": "deep-translator is not installed.\nRun: pip install deep-translator"},
    "trans.error_title": {"fr": "Erreur de traduction", "en": "Translation error"},
    "trans.error_msg": {"fr": "La traduction a echoue :\n{error}\n\nVerifie ta connexion internet.",
                         "en": "Translation failed:\n{error}\n\nCheck your internet connection."},
    "trans.apply_error": {"fr": "Impossible d'appliquer la traduction", "en": "Could not apply the translation"},

    # --- Ouverture de fichiers ---
    "open.error": {"fr": "Impossible d'ouvrir {file}", "en": "Could not open {file}"},
    "open.not_supported_title": {"fr": "Non supporte", "en": "Not supported"},
    "open.not_supported_msg": {"fr": "Pas encore de vue pour les fichiers {ext}",
                                "en": "No viewer yet for {ext} files"},

    # --- Libelles communs ---
    "label.search": {"fr": "Rechercher :", "en": "Search:"},
    "label.value": {"fr": "Valeur :", "en": "Value:"},
    "label.key": {"fr": "Cle :", "en": "Key:"},

    # --- Etats de la copie de travail ---
    "status.editable": {"fr": "copie de travail -- modifiable", "en": "working copy -- editable"},
    "status.readonly": {"fr": "lecture seule", "en": "read-only"},
}


def get_language() -> str:
    return settings.get_language()


def set_language(lang: str) -> None:
    settings.set_language(lang)


def t(translation_key: str, **kwargs) -> str:
    """Traduit `translation_key` dans la langue active. Si la cle est absente, retourne
    la cle elle-meme (visible et sans plantage -- signale qu'une chaine reste a
    traduire). Le parametre s'appelle volontairement `translation_key` et non `key` :
    plusieurs chaines traduites ont elles-memes un placeholder nomme {key} (ex: la cle
    d'une ligne CSV), et un appel comme t("...", key=ma_valeur) entrerait sinon en
    collision avec le nom du premier parametre positionnel -- erreur reelle deja
    rencontree en production (TypeError: t() got multiple values for argument 'key')."""
    entry = STRINGS.get(translation_key)
    if entry is None:
        return translation_key
    lang = get_language()
    text = entry.get(lang, entry.get("fr", translation_key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text

```

### core\models.py

```py
"""
Modèle de données central pour représenter un scénario Empyrion scanné.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict  # noqa: F401 (Dict utilisé plus bas)

# Extensions considérées comme "éditables" par l'outil (texte structuré qu'on pourra parser/éditer)
EDITABLE_EXTENSIONS = {'.ecf', '.yaml', '.yml', '.csv'}


@dataclass
class FileEntry:
    """Un fichier détecté dans le scénario, avec sa catégorie et si l'outil sait (potentiellement) l'éditer."""
    path: Path
    category: str
    editable: bool = False

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @property
    def name(self) -> str:
        return self.path.name

    def __repr__(self):
        return f"FileEntry({self.name}, category={self.category}, editable={self.editable})"


@dataclass
class Playfield:
    """
    Un dossier de playfield (planète, orbite, secteur spatial...).

    Empyrion utilise plusieurs conventions de nommage selon le type de playfield :
      - Surface (planète)         : playfield_dynamic.yaml + playfield_static.yaml + terrain.ecf
      - Spatial (orbite/secteur)  : space_dynamic.yaml (+ souvent pas de terrain.ecf, pas de sol)
      - Système/soleil            : sun_static.yaml
      - Ancien format combiné     : playfield.yaml
      - Sauvegardes de l'éditeur  : fichiers préfixés "+" (ex: +backup_terrain.ecf) -> ignorés du
                                     rôle principal, gardés à part pour ne pas les confondre avec l'actif.
    On stocke donc les fichiers "rôle" détectés dans un dict plutôt que des champs fixes.
    """
    name: str
    role_files: Dict[str, Path] = field(default_factory=dict)   # rôle ('dynamic','static','terrain','combined') -> chemin
    backups: List[FileEntry] = field(default_factory=list)      # fichiers +backup*
    other_files: List[FileEntry] = field(default_factory=list)  # tout le reste (non reconnu)

    @property
    def dynamic_yaml(self) -> Optional[Path]:
        return self.role_files.get('dynamic')

    @property
    def static_yaml(self) -> Optional[Path]:
        return self.role_files.get('static')

    @property
    def terrain_ecf(self) -> Optional[Path]:
        return self.role_files.get('terrain')

    @property
    def combined_yaml(self) -> Optional[Path]:
        return self.role_files.get('combined')

    def is_complete(self) -> bool:
        """Un playfield est considéré 'reconnu' s'il a au moins un fichier de rôle principal détecté."""
        return bool(self.role_files)

    def file_count(self) -> int:
        return len(self.role_files) + len(self.backups) + len(self.other_files)


@dataclass
class Scenario:
    """Représentation complète d'un scénario Empyrion, une fois scanné."""
    root_path: Path
    name: str = ""

    configuration: List[FileEntry] = field(default_factory=list)   # Content/Configuration/*
    playfields: Dict[str, Playfield] = field(default_factory=dict)  # Playfields/<nom>/
    sectors: List[FileEntry] = field(default_factory=list)          # Sectors/*
    random_presets: List[FileEntry] = field(default_factory=list)   # RandomPresets/*
    extras: List[FileEntry] = field(default_factory=list)           # Extras/* (Localization.csv, PDA...)
    shared_data: Optional["Scenario"] = None                        # SharedData/ (structure annexe, même forme)
    other_files: List[FileEntry] = field(default_factory=list)      # Prefabs, Logos, racine, non catégorisé

    def total_file_count(self, include_shared: bool = False) -> int:
        count = (
            len(self.configuration)
            + len(self.sectors)
            + len(self.random_presets)
            + len(self.extras)
            + len(self.other_files)
        )
        for pf in self.playfields.values():
            count += pf.file_count()
        if include_shared and self.shared_data:
            count += self.shared_data.total_file_count()
        return count

    def configuration_extensions_summary(self) -> str:
        ext_counts = {}
        for f in self.configuration:
            ext_counts[f.extension] = ext_counts.get(f.extension, 0) + 1
        return ", ".join(f"{ext}: {n}" for ext, n in sorted(ext_counts.items()))

    def ecf_files(self) -> List[FileEntry]:
        """Raccourci pratique : uniquement les .ecf de Configuration."""
        return [f for f in self.configuration if f.extension == '.ecf']

    def summary(self) -> str:
        lines = []
        lines.append(f"Scénario : {self.name or self.root_path.name}")
        lines.append(f"  Configuration : {len(self.configuration)} fichiers détectés")
        ext_str = self.configuration_extensions_summary()
        if ext_str:
            lines.append(f"      ({ext_str})")

        lines.append(f"  Playfields    : {len(self.playfields)} dossiers détectés")
        incomplete = [p for p in self.playfields.values() if not p.is_complete()]
        if incomplete:
            lines.append(f"      ({len(incomplete)} sans fichier standard reconnu)")

        lines.append(f"  Sectors       : {len(self.sectors)} fichier(s)")
        lines.append(f"  RandomPresets : {len(self.random_presets)} fichier(s)")

        extras_names = ", ".join(sorted(f.name for f in self.extras)) or "-"
        lines.append(f"  Extras        : {len(self.extras)} fichier(s) [{extras_names}]")

        if self.shared_data:
            total_shared = self.shared_data.total_file_count()
            lines.append(f"  SharedData    : (structure annexe, {total_shared} fichiers)")

        lines.append(f"  Autres/non éditables : {len(self.other_files)} fichiers")
        return "\n".join(lines)

```

### core\project_store.py

```py
"""
Gestion des "projets recents" : sauvegarde sur disque (petit fichier JSON dans le
dossier utilisateur) la liste des workspaces deja crees, pour pouvoir les reprendre
au demarrage sans avoir a tout re-saisir a chaque fois.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

CONFIG_DIR = Path.home() / ".empyrion_editor"
CONFIG_FILE = CONFIG_DIR / "projets_recents.json"


@dataclass
class ProjectRecord:
    source_a: str
    working: str
    source_b: Optional[str] = None
    label: str = ""  # nom d'affichage ; genere automatiquement si vide

    def display_name(self) -> str:
        if self.label:
            return self.label
        name = Path(self.working).name
        mode = "  (fusion)" if self.source_b else ""
        return f"{name}{mode}"


def load_recent_projects() -> List[ProjectRecord]:
    if not CONFIG_FILE.exists():
        return []
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        return [ProjectRecord(**p) for p in data.get('projects', [])]
    except Exception:
        return []


def save_recent_projects(projects: List[ProjectRecord]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {'projects': [asdict(p) for p in projects]}
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def add_recent_project(record: ProjectRecord, max_entries: int = 10) -> List[ProjectRecord]:
    """Ajoute (ou remonte en tete si deja present) un projet a la liste des recents."""
    projects = load_recent_projects()
    projects = [p for p in projects if p.working != record.working]
    projects.insert(0, record)
    projects = projects[:max_entries]
    save_recent_projects(projects)
    return projects


def remove_project(working_path: str) -> List[ProjectRecord]:
    projects = load_recent_projects()
    projects = [p for p in projects if p.working != working_path]
    save_recent_projects(projects)
    return projects

```

### core\scanner.py

```py
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
    return _build_scenario(root, all_paths, entries_are_confirmed_files=True)


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
    return _build_scenario(root, path_objs, entries_are_confirmed_files=False)


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


def _build_scenario(root: Path, all_paths: List[Path], entries_are_confirmed_files: bool) -> Scenario:
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

        _classify(scenario, rel_parts, p, entries_are_confirmed_files)

    if shared_data_paths:
        shared_root = root / 'SharedData'
        scenario.shared_data = _build_scenario(shared_root, shared_data_paths, entries_are_confirmed_files)

    return scenario


def _classify(scenario: Scenario, rel_parts: tuple, p: Path, entries_are_confirmed_files: bool) -> None:
    top = rel_parts[0]

    # Un listing tree/Get-ChildItem inclut aussi les dossiers eux-mêmes comme entrées
    # (ex: "Content", "Extras\PDA"). Sur un VRAI scan disque (scan_scenario), tous les
    # chemins reçus ici sont déjà confirmés comme des fichiers via is_file() -- donc une
    # extension vide (ex: bundles Unity "reforgedcontent", "eden_music") est un vrai
    # fichier, pas un dossier, et ne doit PAS être ignorée. Ce heuristique ne s'applique
    # donc que pour scan_from_paths() (listing texte, sans info is_file() fiable).
    if not entries_are_confirmed_files and p.suffix == '':
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

```

### core\scenario_diff.py

```py
"""
Comparaison de deux scenarios Empyrion complets (utile pour verifier ce qui a change
entre deux versions d'un meme scenario, ex: avant/apres une mise a jour de l'auteur).

Compare l'arborescence entiere (tous les fichiers, pas seulement Content/Configuration),
avec un detail approfondi pour les formats structures :
  - .ecf  : diff bloc par bloc (reutilise le moteur existant core/ecf/diff.py)
  - .csv  : diff ligne par ligne, apparie par la 1ere colonne (cle)
  - .yaml/.yml : diff entree par entree, apparie par chemin de cles
  - autres fichiers (.txt, images, .epb...) : comparaison brute (identique / different),
    sans detail interne -- pas de format structure a analyser
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class FileDiffEntry:
    rel_path: str
    status: str  # 'added' | 'removed' | 'modified' | 'unchanged'
    detail: str = ""  # texte de detail (diff), vide si non applicable ou inchange

    def summary_line(self) -> str:
        symbol = {'added': '+', 'removed': '-', 'modified': '~', 'unchanged': ' '}[self.status]
        return f"{symbol} {self.rel_path}"


@dataclass
class ScenarioDiffResult:
    root_a: Path
    root_b: Path
    entries: List[FileDiffEntry] = field(default_factory=list)

    def counts(self) -> dict:
        c = {'added': 0, 'removed': 0, 'modified': 0, 'unchanged': 0}
        for e in self.entries:
            c[e.status] += 1
        return c

    def changed_entries(self) -> List[FileDiffEntry]:
        return [e for e in self.entries if e.status != 'unchanged']

    def render_report(self, include_unchanged: bool = False) -> str:
        """Rapport texte complet, exportable tel quel dans un .txt/.md."""
        from .i18n import t
        c = self.counts()
        lines = [
            t("report.title"),
            "",
            t("report.scenario_a_line", name=self.root_a.name, path=self.root_a),
            t("report.scenario_b_line", name=self.root_b.name, path=self.root_b),
            "",
            t("report.direction_note"),
            "",
            t("report.summary", added=c['added'], removed=c['removed'],
              modified=c['modified'], unchanged=c['unchanged']),
            "=" * 70,
            "",
        ]
        entries = self.entries if include_unchanged else self.changed_entries()
        for e in entries:
            lines.append(e.summary_line())
            if e.detail:
                for detail_line in e.detail.split("\n"):
                    lines.append(f"    {detail_line}")
                lines.append("")
        return "\n".join(lines)


def _diff_ecf_file(path_a: Path, path_b: Path) -> str:
    from .ecf.parser import parse_ecf_file
    from .ecf.diff import diff_documents, format_diff
    try:
        doc_a = parse_ecf_file(path_a)
        doc_b = parse_ecf_file(path_b)
    except Exception as e:
        return f"(erreur de lecture -- comparaison detaillee impossible : {e})"
    diffs = diff_documents(doc_a, doc_b)
    if not diffs:
        return ""
    return format_diff(diffs)


def _diff_csv_file(path_a: Path, path_b: Path) -> str:
    from .csv_handler import parse_csv_text
    from .i18n import t
    try:
        doc_a = parse_csv_text(path_a.read_text(encoding='utf-8'))
        doc_b = parse_csv_text(path_b.read_text(encoding='utf-8'))
    except Exception as e:
        return f"(erreur de lecture -- comparaison detaillee impossible : {e})"

    rows_a = {row[0]: row for row in doc_a.rows if row}
    rows_b = {row[0]: row for row in doc_b.rows if row}
    header = doc_b.header or doc_a.header or []

    lines = []
    for key in rows_a:
        if key not in rows_b:
            lines.append(t("diff.row_removed", key=key))
    for key, row_b in rows_b.items():
        row_a = rows_a.get(key)
        if row_a is None:
            lines.append(t("diff.row_added", key=key))
        elif row_a != row_b:
            lines.append(t("diff.row_modified", key=key))
            for i, col_name in enumerate(header):
                val_a = row_a[i] if i < len(row_a) else ""
                val_b = row_b[i] if i < len(row_b) else ""
                if val_a != val_b:
                    lines.append(f"    {col_name}: {val_a!r} -> {val_b!r}")
    return "\n".join(lines)


def _yaml_leaf_paths(nodes, prefix=()) -> dict:
    """Aplati un arbre YAML en {chemin_de_cles: valeur_rendue} pour permettre un diff
    par correspondance de chemin plutot que ligne a ligne (l'ordre peut differer sans
    que ca soit un vrai changement)."""
    from .yamllite.model import YamlEntry
    result = {}
    seq_index = 0
    for node in nodes:
        if not isinstance(node, YamlEntry):
            continue
        if node.key is not None:
            key_part = node.key
        else:
            key_part = f"[{seq_index}]"
            seq_index += 1
        path = prefix + (key_part,)
        if node.children:
            result.update(_yaml_leaf_paths(node.children, path))
        else:
            result[path] = node.value or ""
    return result


def _diff_yaml_file(path_a: Path, path_b: Path) -> str:
    from .yamllite.parser import parse_yaml_file
    from .i18n import t
    try:
        doc_a = parse_yaml_file(path_a)
        doc_b = parse_yaml_file(path_b)
    except Exception as e:
        return f"(erreur de lecture -- comparaison detaillee impossible : {e})"

    leaves_a = _yaml_leaf_paths(doc_a.nodes)
    leaves_b = _yaml_leaf_paths(doc_b.nodes)

    lines = []
    for path in leaves_a:
        if path not in leaves_b:
            lines.append(t("diff.yaml_removed", path='.'.join(path)))
    for path, val_b in leaves_b.items():
        if path not in leaves_a:
            lines.append(t("diff.yaml_added", path='.'.join(path), value=val_b))
        elif leaves_a[path] != val_b:
            lines.append(f"~ {'.'.join(path)}: {leaves_a[path]} -> {val_b}")
    return "\n".join(lines)


DETAIL_DIFFERS = {
    '.ecf': _diff_ecf_file,
    '.csv': _diff_csv_file,
    '.yaml': _diff_yaml_file,
    '.yml': _diff_yaml_file,
}


def compare_scenarios(root_a: Path, root_b: Path,
                       progress_callback=None) -> ScenarioDiffResult:
    """Compare deux dossiers de scenario entiers, fichier par fichier.

    progress_callback(current: int, total: int, rel_path: str), si fourni, est appele
    pour chaque fichier traite -- utile pour une barre de progression sur de gros
    scenarios (plusieurs milliers de fichiers).
    """
    root_a = Path(root_a)
    root_b = Path(root_b)

    files_a = {p.relative_to(root_a).as_posix(): p for p in root_a.rglob('*') if p.is_file()}
    files_b = {p.relative_to(root_b).as_posix(): p for p in root_b.rglob('*') if p.is_file()}

    all_rel_paths = sorted(set(files_a.keys()) | set(files_b.keys()))
    result = ScenarioDiffResult(root_a=root_a, root_b=root_b)

    total = len(all_rel_paths)
    for i, rel in enumerate(all_rel_paths):
        if progress_callback:
            progress_callback(i, total, rel)

        in_a = rel in files_a
        in_b = rel in files_b

        if in_a and not in_b:
            result.entries.append(FileDiffEntry(rel, 'removed'))
            continue
        if in_b and not in_a:
            result.entries.append(FileDiffEntry(rel, 'added'))
            continue

        path_a, path_b = files_a[rel], files_b[rel]
        try:
            identical = path_a.stat().st_size == path_b.stat().st_size and \
                path_a.read_bytes() == path_b.read_bytes()
        except Exception:
            identical = False

        if identical:
            result.entries.append(FileDiffEntry(rel, 'unchanged'))
            continue

        ext = path_a.suffix.lower()
        differ = DETAIL_DIFFERS.get(ext)
        detail = differ(path_a, path_b) if differ else ""
        result.entries.append(FileDiffEntry(rel, 'modified', detail))

    if progress_callback:
        progress_callback(total, total, "")

    return result

```

### core\settings.py

```py
"""
Reglages persistants simples de l'application (pour l'instant : le nom utilise dans
les annotations de tracabilite lors des modifications, ex: '# original: X -- Mod par
<nom>'). Stocke dans le meme dossier que les projets recents.
"""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".empyrion_editor"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_AUTHOR = "utilisateur"


def get_author() -> str:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('author', DEFAULT_AUTHOR)
        except Exception:
            pass
    return DEFAULT_AUTHOR


def set_author(name: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['author'] = name
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_annotations_enabled() -> bool:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('annotations_enabled', True)
        except Exception:
            pass
    return True


def set_annotations_enabled(enabled: bool) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['annotations_enabled'] = enabled
    data['author'] = data.get('author', DEFAULT_AUTHOR)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_language() -> str:
    """Code langue de l'interface : 'fr' ou 'en'."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('language', 'fr')
        except Exception:
            pass
    return 'fr'


def set_language(lang: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['language'] = lang
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def get_merge_enabled() -> bool:
    """La fusion (copier/fusionner fichier, dossier, bloc, ligne) est DESACTIVEE par
    defaut : trop de cas particuliers pour etre fiable a 100%, source de scenarios
    casses. La duplication (creation d'une entree nouvelle et independante) reste
    toujours disponible, elle. Peut etre reactivee via Options si besoin."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get('merge_enabled', False)
        except Exception:
            pass
    return False


def set_merge_enabled(enabled: bool) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data['merge_enabled'] = enabled
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    """Dernier dossier de sauvegardes utilise pour ce type ('scenario' ou 'savegame'),
    ou chaine vide si jamais defini."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            return data.get(f'backup_root_{kind}', '')
        except Exception:
            pass
    return ''


def set_backup_root(kind: str, path: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    data[f'backup_root_{kind}'] = path
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

```

### core\translation.py

```py
"""
Traduction de texte via Google Translate (bibliotheque deep-translator, gratuite, sans
cle API). Utilise pour la traduction ponctuelle d'une valeur (clic droit -> Traduire),
en complement du systeme de traduction CSV de masse (outil separe, hors ligne via Ollama).

IMPORTANT -- protection du BBCode et des placeholders : le texte Empyrion contient
souvent des balises de mise en forme ([b]...[/b], [color=#FF0000]...[/color]) et des
jetons de substitution ({PlayerName}, %s, {0}...) qui ne doivent JAMAIS etre traduits
ni alteres. Avant d'envoyer le texte au traducteur, on les extrait et on les remplace
par des jetons neutres insensibles a la traduction, puis on les reinjecte a leur place
dans le resultat -- meme principe que le "segment-splitting" deja utilise dans l'outil
de traduction CSV.
"""
import re
from typing import List, Tuple

try:
    from deep_translator import GoogleTranslator
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


COMMON_LANGUAGES = [
    ("Francais", "fr"),
    ("Anglais", "en"),
    ("Allemand", "de"),
    ("Espagnol", "es"),
    ("Italien", "it"),
    ("Russe", "ru"),
    ("Portugais (Europe)", "pt"),
    ("Portugais (Bresil)", "pt-BR"),
    ("Neerlandais", "nl"),
    ("Polonais", "pl"),
    ("Japonais", "ja"),
    ("Coreen", "ko"),
    ("Turc", "tr"),
    ("Grec", "el"),
    ("Vietnamien", "vi"),
    ("Chinois (simplifie)", "zh-CN"),
    ("Chinois (traditionnel)", "zh-TW"),
]

# Alias possibles pour reperer la colonne d'une langue dans l'en-tete d'un CSV --
# les fichiers Empyrion reels utilisent des conventions variees (nom anglais, nom
# natif, code ISO...), donc on accepte plusieurs formes par langue. La comparaison
# se fait sans tenir compte des accents (voir _normalize).
LANGUAGE_ALIASES = {
    "fr": ["fr", "french", "francais", "français"],
    "en": ["en", "english", "anglais"],
    "de": ["de", "german", "deutsch", "allemand"],
    "es": ["es", "spanish", "espanol", "español", "espagnol"],
    "it": ["it", "italian", "italiano", "italien"],
    "ru": ["ru", "russian", "russe"],
    "pt": ["pt", "portuguese (euro)", "portuguese", "portugues", "português", "portugais"],
    "pt-BR": ["pt-br", "portuguese (brazil)", "portugues (brasil)", "português (brasil)"],
    "nl": ["nl", "dutch", "nederlands", "neerlandais"],
    "pl": ["pl", "polish", "polski", "polonais"],
    "ja": ["ja", "japanese", "japonais"],
    "ko": ["ko", "korean", "coreen"],
    "tr": ["tr", "turkish", "turc"],
    "el": ["el", "greek", "grec"],
    "vi": ["vi", "vietnamese", "vietnamien"],
    "zh-CN": ["zh-cn", "chinese (simplified)", "chinois (simplifie)"],
    "zh-TW": ["zh-tw", "chinese (traditional)", "chinois (traditionnel)"],
}


def _normalize(s: str) -> str:
    """Normalise une chaine pour comparaison : sans accents, sans espaces superflus,
    en majuscules -- pour que 'Français' == 'Francais' == 'FRANCAIS'."""
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.strip().upper()


def find_language_aliases(target_code: str, target_label: str) -> list:
    """Retourne toutes les formes acceptees (normalisees) pour reperer la colonne
    d'une langue donnee dans un en-tete CSV."""
    aliases = set(LANGUAGE_ALIASES.get(target_code, [target_code]))
    aliases.add(target_code)
    aliases.add(target_label)
    return [_normalize(a) for a in aliases]

# Balises BBCode : [b], [/b], [color=#FF0000], [url=...], etc.
_BBCODE_RE = r'\[/?[a-zA-Z0-9_]+(?:=[^\]]*)?\]'
# Jetons de substitution courants : {PlayerName}, {0}, %s, %d, %1
_PLACEHOLDER_RE = r'\{[^{}]*\}|%[a-zA-Z0-9]+'

_PROTECTED_RE = re.compile(f'(?:{_BBCODE_RE})|(?:{_PLACEHOLDER_RE})')


def protect_segments(text: str) -> Tuple[str, List[str]]:
    """Remplace les balises BBCode et les placeholders par des jetons neutres
    (XXTAGnXX) que Google Translate laisse intacts. Retourne (texte_protege, liste_des_
    segments_originaux_dans_l_ordre)."""
    segments: List[str] = []

    def _replace(m):
        token = f"XXTAG{len(segments)}XX"
        segments.append(m.group(0))
        return token

    protected = _PROTECTED_RE.sub(_replace, text)
    return protected, segments


def restore_segments(translated_text: str, segments: List[str]) -> str:
    """Reinjecte les balises/placeholders d'origine a la place des jetons neutres."""
    result = translated_text
    for i, original in enumerate(segments):
        # Insensible a la casse et aux espaces que le traducteur peut inserer autour
        # du jeton (ex: 'xxtag0xx', 'XX TAG0 XX') -- on reste tolerant.
        pattern = re.compile(r'X{1,3}\s*TAG\s*' + str(i) + r'\s*X{1,3}', re.IGNORECASE)
        result = pattern.sub(original, result, count=1)
    return result


def is_available() -> bool:
    return _AVAILABLE


def translate_text(text: str, target: str = "fr", source: str = "auto") -> str:
    """Traduit `text` vers la langue `target` (code ISO, ex: 'fr', 'en'), en preservant
    le BBCode et les placeholders. Leve une exception explicite si la bibliotheque
    n'est pas installee ou si la requete echoue (ex: pas de connexion internet) -- a
    capturer et afficher clairement cote GUI."""
    if not _AVAILABLE:
        raise RuntimeError("deep-translator n'est pas installe. Lance : pip install deep-translator")
    if not text or not text.strip():
        return text

    protected, segments = protect_segments(text)
    translated = GoogleTranslator(source=source, target=target).translate(protected)
    if segments:
        translated = restore_segments(translated, segments)
    return translated

```

### core\workspace.py

```py
"""
Gestion de l'espace de travail (Workspace) : un scenario source A (lecture seule), un
scenario source B optionnel (lecture seule, pour la fusion), et une COPIE DE TRAVAIL
physique -- un scenario complet, copie sur disque a un nouvel emplacement -- qui est le
seul scenario modifiable. Les sources A et B ne sont jamais touchees.
"""
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from .scanner import scan_scenario
from .models import Scenario
from .fsutil import clear_readonly


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

    def set_scenario_b(self, source_b_root: Optional[Path]) -> None:
        """Definit ou change le Scenario B a tout moment, meme si le projet a ete
        ouvert sans (ou avec un autre). Passer None retire le Scenario B (retour au
        mode simple, sans comparaison)."""
        self.source_b_root = source_b_root
        self.source_b = scan_scenario(source_b_root) if source_b_root else None


def create_working_copy(source_root: Path, dest_root: Path) -> Path:
    """Copie physiquement TOUT le contenu du scenario source vers un nouvel
    emplacement, qui devient la copie de travail modifiable. Le dossier de destination
    ne doit pas deja exister (securite : on ne veut jamais ecraser quoi que ce soit par
    erreur)."""
    if dest_root.exists():
        raise FileExistsError(f"Le dossier de destination existe deja : {dest_root}")
    shutil.copytree(source_root, dest_root, copy_function=shutil.copy2)
    # La copie de travail doit TOUJOURS rester modifiable, meme si la source (souvent
    # installee sous Program Files) a des fichiers marques lecture seule par Windows --
    # sinon la copie entiere herite du verrou et devient elle-meme non modifiable/non
    # supprimable ("permission de <utilisateur>" demandee par Windows, meme pour son
    # propre compte).
    clear_readonly(dest_root)
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
    clear_readonly(dest)
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
        clear_readonly(dest)
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


def duplicate_csv_row_into_working(workspace: Workspace, working_relative_path: Path,
                                    row: List[str], new_key: str) -> Tuple[Path, str]:
    """Duplique une ligne CSV (venant d'une source) avec une NOUVELLE cle, et l'ajoute
    a la copie de travail comme un enregistrement INDEPENDANT (pas une fusion -- sert a
    creer un nouvel element en partant d'un modele existant). Refuse si la cle existe
    deja (evite un doublon accidentel).

    Retourne (chemin_du_fichier, statut) -- statut : 'added' ou 'key_exists'.
    """
    dest = workspace.working_root / working_relative_path
    if not dest.exists():
        raise FileNotFoundError(f"Le fichier {dest} n'existe pas encore dans la copie de travail.")

    from .csv_handler import CsvHandler, render_csv

    handler = CsvHandler()
    doc = handler.parse(handler.load(dest))

    for existing_row in doc.rows:
        if existing_row and existing_row[0] == new_key:
            return dest, 'key_exists'

    new_row = list(row)
    if new_row:
        new_row[0] = new_key
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


def _find_ecf_parent_children(nodes: list, parent_chain: list) -> Optional[list]:
    """Retrouve, dans une liste de noeuds ECF, la liste d'enfants correspondant a une
    chaine de parents (kind normalise, identite) -- pour savoir dans quel bloc reinserer
    un sous-bloc duplique, au meme niveau d'imbrication que l'original."""
    from .ecf.model import normalized_kind, block_identity
    current_nodes = nodes
    for kind, ident in parent_chain:
        found = None
        for n in current_nodes:
            if hasattr(n, 'kind') and normalized_kind(n.kind) == kind and block_identity(n) == ident:
                found = n
                break
        if found is None:
            return None
        current_nodes = found.children
    return current_nodes


def duplicate_ecf_block_into_working(workspace: Workspace, working_relative_path: Path,
                                      block, new_id: Optional[str], new_name: Optional[str],
                                      remove_id: bool, source_label: str,
                                      parent_chain: Optional[list] = None,
                                      annotation: Optional[str] = None) -> Tuple[Path, str]:
    """
    Duplique un bloc ECF (venant d'une source) vers la copie de travail comme un bloc
    INDEPENDANT (pas une fusion) -- l'utilisateur choisit librement : nouvel Id, nouveau
    Name, les deux, ou abandonner l'Id pour n'identifier le nouveau bloc que par Name
    (certains blocs reels n'ont pas d'Id du tout). Ne passe pas par le garde-fou de
    fusion puisque le but est justement de creer un element distinct.

    Si `parent_chain` est fourni (liste de (kind, identite) menant au bloc dans le
    document source -- ex: [('Item', '100')] pour un sous-bloc 'Mode' imbrique dans un
    Item), le nouveau bloc est insere DANS LE MEME PARENT (retrouve dans la copie de
    travail par cette chaine), et pas au niveau racine -- sinon un sous-bloc duplique se
    retrouverait isole/orphelin en fin de fichier.

    `annotation`, si fourni (ex: "# Duplique par Daflo"), est ajoute en fin de la ligne
    Id/Name du nouveau bloc -- fusionne avec un commentaire deja present sur le bloc
    d'origine (copie via deepcopy) plutot que de l'ecraser.

    Verifie les collisions contre l'identite REELLE du bloc obtenu (Id si present,
    sinon Name), au sein du meme conteneur (racine ou parent). Retourne
    (chemin_du_fichier, statut) -- statut : 'added', 'exists', ou 'parent_not_found'.
    """
    dest = workspace.working_root / working_relative_path
    if not dest.exists():
        raise FileNotFoundError(f"Le fichier {dest} n'existe pas encore dans la copie de travail.")

    from .ecf.parser import parse_ecf_file
    from .ecf.model import duplicate_block, normalized_kind

    working_doc = parse_ecf_file(dest)

    target_nodes = working_doc.nodes
    if parent_chain:
        found_nodes = _find_ecf_parent_children(working_doc.nodes, parent_chain)
        if found_nodes is None:
            return dest, 'parent_not_found'
        target_nodes = found_nodes

    overrides = {}
    if new_id:
        overrides['Id'] = new_id
    if new_name:
        overrides['Name'] = new_name
    remove_keys = ['Id'] if remove_id else []

    new_block = duplicate_block(block, overrides=overrides, remove_keys=remove_keys)
    # Reajuste l'indentation au niveau d'imbrication reel de destination (l'original
    # copie garde sinon l'indentation de sa position d'origine, qui peut ne pas
    # correspondre si le contexte differe).
    new_block.indent = "  " * len(parent_chain) if parent_chain else ""

    if annotation:
        new_block.comment = (new_block.comment + "  " + annotation) if new_block.comment else annotation

    final_id = new_block.get('Id')
    final_name = new_block.get_property('Name')

    for node in target_nodes:
        if not (hasattr(node, 'kind') and normalized_kind(node.kind) == normalized_kind(block.kind)):
            continue
        if final_id is not None:
            if node.get('Id') == final_id:
                return dest, 'exists'
        elif final_name is not None:
            if node.get('Id') is None and node.get_property('Name') == final_name:
                return dest, 'exists'

    target_nodes.append(new_block)

    with open(dest, 'w', encoding='utf-8', newline='') as f:
        f.write(working_doc.render())

    return dest, 'added'


def _find_yaml_parent_path(doc, key_path: List[str]):
    """Retrouve, dans un YamlDocument, la liste d'enfants correspondant a un chemin de
    cles ancetres (ex: ['Playfield', 'POIs']) -- pour savoir ou inserer une entree
    copiee au bon endroit. Retourne None si le chemin n'existe pas."""
    from .yamllite.model import YamlEntry
    current_nodes = doc.nodes
    entry = None
    for key in key_path:
        entry = None
        for n in current_nodes:
            if isinstance(n, YamlEntry) and n.key == key:
                entry = n
                break
        if entry is None:
            return None
        current_nodes = entry.children
    return current_nodes


def copy_yaml_entry_into_working(workspace: Workspace, working_relative_path: Path,
                                  entry, key_path: List[str]) -> Tuple[Path, str]:
    """Copie une entree YAML (venant d'une source) vers la copie de travail, au meme
    emplacement (meme chemin de cles ancetres) si on le retrouve, sinon au niveau
    racine. Retourne (chemin_du_fichier, statut) -- statut : 'added' ou 'added_at_root'."""
    dest = workspace.working_root / working_relative_path
    if not dest.exists():
        raise FileNotFoundError(f"Le fichier {dest} n'existe pas encore dans la copie de travail.")

    from .yamllite.parser import parse_yaml_file
    from .yamllite.model import YamlDocument
    import copy as _copy

    doc: YamlDocument = parse_yaml_file(dest)
    new_entry = _copy.deepcopy(entry)
    new_entry.dirty = True

    target_list = _find_yaml_parent_path(doc, key_path)
    status = 'added'
    if target_list is None:
        target_list = doc.nodes
        status = 'added_at_root'
    target_list.append(new_entry)

    with open(dest, 'w', encoding='utf-8', newline='') as f:
        f.write(doc.render())

    return dest, status


def duplicate_yaml_entry_into_working(workspace: Workspace, working_relative_path: Path,
                                       entry, key_path: List[str], new_key: Optional[str],
                                       annotation: Optional[str] = None) -> Tuple[Path, str]:
    """Duplique une entree YAML (venant d'une source) avec une NOUVELLE cle (si
    applicable), et l'ajoute a la copie de travail comme une entree INDEPENDANTE, au
    meme emplacement (meme chemin de cles ancetres) si on le retrouve. Refuse si la
    nouvelle cle existe deja parmi les enfants directs du meme parent.

    `annotation`, si fourni, est fusionne avec le commentaire existant de l'entree
    (comme pour la duplication de bloc ECF).

    Retourne (chemin_du_fichier, statut) -- statut : 'added', 'added_at_root', ou
    'key_exists'.
    """
    dest = workspace.working_root / working_relative_path
    if not dest.exists():
        raise FileNotFoundError(f"Le fichier {dest} n'existe pas encore dans la copie de travail.")

    from .yamllite.parser import parse_yaml_file
    from .yamllite.model import YamlDocument, YamlEntry
    import copy as _copy

    doc: YamlDocument = parse_yaml_file(dest)
    target_list = _find_yaml_parent_path(doc, key_path)
    status = 'added'
    if target_list is None:
        target_list = doc.nodes
        status = 'added_at_root'

    if new_key:
        for n in target_list:
            if not isinstance(n, YamlEntry):
                continue
            if n.key and n.key.strip().lower() in ('name', 'id'):
                if n.value == new_key:
                    return dest, 'key_exists'
            elif n.key == new_key:
                return dest, 'key_exists'

    new_entry = _copy.deepcopy(entry)
    new_entry.dirty = True
    if annotation:
        new_entry.comment = (new_entry.comment + "  " + annotation) if new_entry.comment else annotation
    if new_key:
        # Heuristique : si la cle de cette entree est 'Name' ou 'Id' (motif frequent
        # pour un item de sequence identifie par un champ, ex: '- Name: BaseOne'), la
        # VALEUR est le veritable identifiant -- on la renomme, pas la cle (qui est
        # juste le nom du champ 'Name'). Sinon (mapping classique 'Cle: valeur'), la
        # cle EST l'identifiant -- on la renomme directement.
        if new_entry.key and new_entry.key.strip().lower() in ('name', 'id'):
            new_entry.set_own_value(new_key)
        elif new_entry.key is not None:
            new_entry.key = new_key
            new_entry.dirty = True
        else:
            new_entry.set_own_value(new_key)
    target_list.append(new_entry)

    with open(dest, 'w', encoding='utf-8', newline='') as f:
        f.write(doc.render())

    return dest, status

```

### core\workspace_undo.py

```py
"""
Pile d'annulation GLOBALE au niveau de l'espace de travail -- couvre toute action qui
touche au systeme de fichiers de la copie de travail : fusion (fichier/dossier/bloc/
ligne/entree), duplication, suppression, traduction, activation d'un bloc en attente.

Complementaire (pas un remplacement) de l'annulation "en session" deja presente dans
chaque editeur ouvert (EcfEditWidget.undo() etc, qui n'agit que sur un fichier en cours
d'edition dans un onglet) : celle-ci agit sur TOUTE action qui ecrit sur le disque,
meme sans avoir ouvert le fichier concerne.

Principe : avant chaque operation qui va modifier un ou plusieurs fichiers de la copie
de travail, on capture leur etat EXACT (contenu binaire, ou absence) ; annuler restaure
cet etat tel quel. Fiable par construction (pas de reconstruction logique fragile),
au prix d'un peu de memoire -- largement acceptable pour des fichiers de configuration
de scenario (texte, quelques Ko a quelques Mo), pile plafonnee pour eviter toute derive.
"""
import shutil
from pathlib import Path
from typing import Optional, Dict, List


class UndoAction:
    def undo(self) -> None:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


class FileStateUndo(UndoAction):
    """Restaure UN fichier a son etat (contenu, ou absence) d'avant l'operation."""

    def __init__(self, path: Path, prior_bytes: Optional[bytes], label: str):
        self.path = Path(path)
        self.prior_bytes = prior_bytes
        self.label = label

    def undo(self) -> None:
        if self.prior_bytes is None:
            if self.path.exists():
                self.path.unlink()
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(self.prior_bytes)

    def describe(self) -> str:
        return self.label


class MultiFileStateUndo(UndoAction):
    """Restaure PLUSIEURS fichiers d'un coup (une fusion de dossier ou de bloc peut
    toucher de nombreux fichiers en une seule action utilisateur -- on veut qu'une
    seule 'Annuler' revienne sur tout, pas fichier par fichier)."""

    def __init__(self, entries: List[FileStateUndo], label: str):
        self.entries = entries
        self.label = label

    def undo(self) -> None:
        for entry in self.entries:
            entry.undo()

    def describe(self) -> str:
        return self.label


class FolderStateUndo(UndoAction):
    """Restaure un dossier ENTIER (utilise pour la suppression de dossier -- capture
    tout son contenu avant suppression)."""

    def __init__(self, folder: Path, existed_before: bool, prior_files: Dict[str, bytes], label: str):
        self.folder = Path(folder)
        self.existed_before = existed_before
        self.prior_files = prior_files
        self.label = label

    def undo(self) -> None:
        if self.folder.exists():
            shutil.rmtree(self.folder)
        if self.existed_before:
            for rel, data in self.prior_files.items():
                dest = self.folder / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)

    def describe(self) -> str:
        return self.label


class WorkspaceUndoStack:
    def __init__(self, max_depth: int = 15):
        self._stack: List[UndoAction] = []
        self.max_depth = max_depth

    def push(self, action: UndoAction) -> None:
        self._stack.append(action)
        if len(self._stack) > self.max_depth:
            self._stack.pop(0)

    def can_undo(self) -> bool:
        return bool(self._stack)

    def peek_label(self) -> str:
        return self._stack[-1].describe() if self._stack else ""

    def undo(self) -> Optional[str]:
        if not self._stack:
            return None
        action = self._stack.pop()
        action.undo()
        return action.describe()

    def clear(self) -> None:
        self._stack.clear()


def capture_file(path: Path) -> Optional[bytes]:
    """Capture le contenu d'un fichier avant modification -- None si le fichier
    n'existe pas encore (l'annulation saura alors qu'il faut le supprimer)."""
    path = Path(path)
    return path.read_bytes() if path.exists() else None


def capture_folder(folder: Path) -> tuple:
    """Capture tout le contenu d'un dossier avant suppression/fusion.
    Retourne (existait_avant: bool, {chemin_relatif: contenu})."""
    folder = Path(folder)
    if not folder.exists():
        return False, {}
    files = {}
    for p in folder.rglob('*'):
        if p.is_file():
            files[str(p.relative_to(folder))] = p.read_bytes()
    return True, files

```

### core\yaml_handler.py

```py
"""
Handler YAML pour les fichiers de playfield (playfield_static.yaml, playfield_dynamic.yaml).

Utilise le parser maison "yamllite" (core/yamllite/), qui garantit un round-trip fidele
par construction -- meme principe que le parser ECF : chaque ligne garde son texte brut,
donc rien n'est modifie tant qu'on ne touche pas explicitement une valeur.

Historique : une premiere version utilisait ruamel.yaml (bibliotheque tierce, mode
round-trip), mais des tests sur de vrais fichiers Empyrion ont revele plusieurs pertes
de fidelite non corrigibles simplement (lignes vides "orphelines" perdues selon le
contexte). D'ou le passage a un parser maison, comme pour l'ECF a l'Etape 1.
"""
from pathlib import Path
from typing import Any

from .file_handlers import FileHandler
from .yamllite.parser import parse_yaml_text
from .yamllite.model import YamlDocument


class YamlHandler(FileHandler):
    """Handler round-trip pour les fichiers .yaml/.yml (playfields Empyrion notamment)."""

    extensions = ('.yaml', '.yml')

    def load(self, path: Path) -> str:
        with open(path, 'rb') as f:
            return f.read().decode('utf-8')

    def parse(self, raw: str) -> YamlDocument:
        return parse_yaml_text(raw)

    def serialize(self, ast: YamlDocument) -> str:
        return ast.render()



```

### core\yamllite\__init__.py

```py

```

### core\yamllite\model.py

```py
"""
Modèle AST pour un parser YAML "léger" (yamllite), conçu sur le même principe que le
parser ECF : chaque ligne garde son texte brut d'origine, donc tant qu'on ne modifie
rien, la sérialisation reproduit le fichier à l'identique, byte pour byte -- quelle que
soit la complexité de la structure YAML sous-jacente.

Contrairement à un parser YAML générique (type ruamel.yaml), on ne cherche PAS à
comprendre finement chaque construction YAML (ancres, tags, styles de pliage...). On se
limite au sous-ensemble réellement utilisé par les fichiers Empyrion (playfields) :
mappings imbriqués par indentation, séquences ('- item'), scalaires simples, listes/
mappings "flow" sur une seule ligne ([a, b], {k: v}) traités comme du texte opaque, et
commentaires. C'est le même choix de conception que pour l'ECF : mieux vaut un
sous-ensemble fidèle à 100% qu'un parser généraliste qui trahit la moindre subtilité.

Types de nœuds :
  - YamlBlank    : ligne vide
  - YamlComment  : ligne de commentaire (#...), jamais réinterprétée
  - YamlEntry    : une ligne "clé: valeur" (mapping) ou "- valeur" (séquence), avec
                   ses enfants imbriqués (indentation supérieure)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class YamlBlank:
    raw: str

    def render(self) -> str:
        return self.raw


@dataclass
class YamlComment:
    raw: str

    def render(self) -> str:
        return self.raw


@dataclass
class YamlEntry:
    """
    Une ligne de contenu structurel : soit une entrée de mapping ('Cle: valeur'), soit
    un item de sequence ('- valeur' ou '- Cle: valeur' pour une sequence de mappings).
    """
    raw: str                          # texte d'origine complet (utilise si non modifie)
    indent: str                       # espaces en debut de ligne
    is_sequence_item: bool            # True si la ligne commence par '- '
    key: Optional[str]                # cle du mapping, ou None si scalaire de sequence pur
    value: str                        # valeur brute apres ':' ou apres '- ' (peut etre vide
                                       # si le contenu continue sur les lignes suivantes,
                                       # plus indentees)
    comment: Optional[str]            # commentaire de fin de ligne, ou None
    eol: str
    children: List["YamlNode"] = field(default_factory=list)
    dirty: bool = False
    quoted_continuation_raw: Optional[str] = None  # si la valeur est une chaine entre
        # guillemets s'etalant sur plusieurs lignes (YAML valide : les sauts de ligne
        # sont autorises entre guillemets, ex: Description: "...\n\n...suite...")  --
        # texte brut des lignes suivantes (a partir de celle qui suit la premiere),
        # jusqu'a et y compris la ligne qui referme le guillemet. `value` contient alors
        # une version repliee (lignes jointes par un espace, guillemets retires) pour un
        # affichage/edition lisibles ; `raw` + `quoted_continuation_raw` reproduit le
        # texte source EXACT tant que l'entree n'est pas modifiee.

    def get(self, key: str) -> Optional[str]:
        """Cherche une valeur parmi les enfants directs (mapping imbrique)."""
        for child in self.children:
            if isinstance(child, YamlEntry) and child.key == key:
                return child.value
        return None

    def set(self, key: str, new_value: str) -> bool:
        """Modifie la valeur d'une cle enfant existante. Retourne False si absente."""
        for child in self.children:
            if isinstance(child, YamlEntry) and child.key == key:
                child.value = new_value
                child.dirty = True
                return True
        return False

    def set_own_value(self, new_value: str) -> None:
        """Modifie la valeur de CETTE entree elle-meme (pas d'un enfant)."""
        self.value = new_value
        self.dirty = True

    def render(self) -> str:
        parts = [self._render_self_line()]
        if self.quoted_continuation_raw and not self.dirty:
            parts.append(self.quoted_continuation_raw)
        for child in self.children:
            parts.append(child.render())
        return "".join(parts)

    def _render_self_line(self) -> str:
        if not self.dirty:
            return self.raw
        prefix = "- " if self.is_sequence_item else ""
        if self.key is not None:
            body = f"{self.key}: {self.value}" if self.value else f"{self.key}:"
        else:
            body = self.value
        line = f"{self.indent}{prefix}{body}"
        if self.comment:
            line += "  " + self.comment
        return line + self.eol


YamlNode = Union[YamlBlank, YamlComment, YamlEntry]


def create_entry(key: Optional[str], value: str, indent: str = "", is_sequence_item: bool = False,
                  eol: str = "\r\n") -> YamlEntry:
    """Cree une nouvelle entree YAML de toutes pieces (pas encore attachee a un document)."""
    return YamlEntry(raw="", indent=indent, is_sequence_item=is_sequence_item, key=key,
                      value=value, comment=None, eol=eol, children=[], dirty=True)


def remove_entry(nodes: List[YamlNode], target: YamlEntry) -> bool:
    """Supprime une entree (a n'importe quelle profondeur) d'une liste de noeuds.
    Retourne False si l'entree n'a pas ete trouvee."""
    if target in nodes:
        nodes.remove(target)
        return True
    for node in nodes:
        if isinstance(node, YamlEntry):
            if remove_entry(node.children, target):
                return True
    return False


@dataclass
class YamlDocument:
    nodes: List[YamlNode]
    source_path: Optional[str] = None

    def render(self) -> str:
        return "".join(n.render() for n in self.nodes)

    def iter_entries(self):
        """Parcourt recursivement toutes les entrees (mapping/sequence) du document."""
        def _walk(nodes):
            for n in nodes:
                if isinstance(n, YamlEntry):
                    yield n
                    yield from _walk(n.children)
        yield from _walk(self.nodes)

    def find(self, key: str) -> Optional[YamlEntry]:
        """Trouve la premiere entree de mapping portant cette cle, a n'importe quel niveau."""
        for entry in self.iter_entries():
            if entry.key == key:
                return entry
        return None

    def get_path(self, *keys: str) -> Optional[str]:
        """Navigue par une suite de cles imbriquees, ex: get_path('Playfield','Name')."""
        current_nodes = self.nodes
        entry = None
        for key in keys:
            entry = None
            for n in current_nodes:
                if isinstance(n, YamlEntry) and n.key == key:
                    entry = n
                    break
            if entry is None:
                return None
            current_nodes = entry.children
        return entry.value if entry else None

```

### core\yamllite\parser.py

```py
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

        if indent_len <= base_indent:
            break

        if stripped.startswith('#'):
            nodes.append(YamlComment(raw=raw))
            i += 1
            continue

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

```

### detecter_imbrication_anormale.py

```py
"""
Detecte les blocs ECF qui contiennent anormalement d'autres blocs "Block"/"+Block"
imbriques a l'interieur -- signe caracteristique du bug ou une ligne de fermeture '}'
est restee commentee ('#}') apres une edition manuelle, ce qui fait que tout le reste
du fichier se retrouve avale comme "enfant" du bloc mal ferme.

Normalement, dans BlocksConfig.ecf, un bloc 'Block'/'+Block' ne contient PAS d'autres
blocs 'Block'/'+Block' imbriques -- si on en trouve, c'est le signe du probleme.

UTILISATION :
    python detecter_imbrication_anormale.py "chemin\vers\BlocksConfig.ecf"
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "parser.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/parser.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file
from core.ecf.model import EcfBlock, normalized_kind, block_identity


def main():
    if len(sys.argv) != 2:
        print("Usage: python detecter_imbrication_anormale.py <fichier.ecf>")
        sys.exit(1)

    path = Path(sys.argv[1])
    doc = parse_ecf_file(path)

    print(f"Analyse de {path.name}...")
    print()

    suspects = []
    for node in doc.nodes:
        if not isinstance(node, EcfBlock):
            continue
        nested_blocks = [c for c in node.children if isinstance(c, EcfBlock)
                          and normalized_kind(c.kind) == normalized_kind(node.kind)]
        if nested_blocks:
            suspects.append((node, nested_blocks))

    if not suspects:
        print("Aucune imbrication anormale detectee -- la structure du fichier semble saine.")
        return

    print(f"{len(suspects)} bloc(s) contiennent anormalement d'autres blocs du meme genre imbriques :")
    print()
    for node, nested in suspects:
        ident = block_identity(node)
        print(f"  {node.kind} [{ident}]  contient {len(nested)} bloc(s) imbrique(s) a tort :")
        for n in nested[:10]:
            print(f"      -> {n.kind} [{block_identity(n)}]")
        if len(nested) > 10:
            print(f"      ... et {len(nested) - 10} autre(s)")
        print()

    print("Cause probable : une ligne de fermeture '}' est restee commentee ('#}') lors d'une")
    print("edition manuelle. Le bloc liste ci-dessus n'a jamais ete correctement referme, donc")
    print("tout ce qui suit dans le fichier (jusqu'a la prochaine '}' non commentee) a ete")
    print("englouti comme si ca faisait partie de son contenu.")


if __name__ == "__main__":
    main()

```

### diagnostic_bloc.py

```py
"""
Diagnostic : verifie si mon parser retrouve un bloc precis (par Id) dans un fichier
.ecf, apres une edition manuelle (ex: decommenter un bloc en conflit d'Id).

UTILISATION :
    python diagnostic_bloc.py "chemin\vers\BlocksConfig.ecf" 999999
    (999999 = l'Id que tu as donne au bloc)
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "parser.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/parser.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file
from core.ecf.model import EcfBlock, EcfComment, block_identity


def main():
    if len(sys.argv) != 3:
        print("Usage: python diagnostic_bloc.py <fichier.ecf> <Id>")
        sys.exit(1)

    path = Path(sys.argv[1])
    target_id = sys.argv[2]

    doc = parse_ecf_file(path)

    print(f"Recherche du bloc avec Id={target_id} dans {path.name}...")
    print()

    found_blocks = []
    for block in doc.iter_blocks():
        if block_identity(block) == target_id:
            found_blocks.append(block)

    print(f"Blocs actifs (structures) trouves avec cet Id : {len(found_blocks)}")
    for b in found_blocks:
        print(f"  - genre={b.kind}, Name={b.get_property('Name')}")

    print()
    print("Recherche de l'Id dans les commentaires bruts (texte non-structure) :")
    count_in_comments = 0
    for node in doc.nodes:
        if isinstance(node, EcfComment) and target_id in node.raw:
            count_in_comments += 1
            print(f"  - {node.raw.rstrip()!r}")
    if count_in_comments == 0:
        print("  (aucun -- l'Id n'apparait dans aucun commentaire, donc pas de residu de commentaire)")

    print()
    print(f"Total de blocs actifs dans tout le fichier : {sum(1 for _ in doc.iter_blocks())}")


if __name__ == "__main__":
    main()

```

### diff_ecf.py

```py
"""
Compare deux fichiers .ecf et affiche les differences (blocs ajoutes/supprimes/modifies).

UTILISATION :
    python diff_ecf.py fichierA.ecf fichierB.ecf

Exemple concret : comparer la meme config entre deux versions d'un scenario, ou entre
deux scenarios differents (ex: Config_RE.ecf de Atlantis Next vs RE2).
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "diff.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/diff.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file
from core.ecf.diff import diff_documents, format_diff, summarize_diff


def main():
    if len(sys.argv) != 3:
        print("Usage: python diff_ecf.py fichierA.ecf fichierB.ecf")
        sys.exit(1)

    path_a = Path(sys.argv[1])
    path_b = Path(sys.argv[2])

    for p in (path_a, path_b):
        if not p.exists():
            print(f"ERREUR : fichier introuvable : {p}")
            sys.exit(1)

    print(f"Comparaison :")
    print(f"  A = {path_a}")
    print(f"  B = {path_b}")
    print()

    doc_a = parse_ecf_file(path_a)
    doc_b = parse_ecf_file(path_b)

    diffs = diff_documents(doc_a, doc_b)
    resume = summarize_diff(diffs)

    print("=" * 60)
    print("RESUME")
    print("=" * 60)
    print(f"  Blocs ajoutes   (dans B, absents de A) : {resume['added']}")
    print(f"  Blocs supprimes (dans A, absents de B) : {resume['removed']}")
    print(f"  Blocs modifies                         : {resume['modified']}")
    total = resume['added'] + resume['removed'] + resume['modified']
    print()

    if total == 0:
        print("Aucune difference detectee -- les deux fichiers sont equivalents.")
        return

    print("=" * 60)
    print("DETAIL")
    print("=" * 60)
    print(format_diff(diffs))


if __name__ == "__main__":
    main()

```

### docs\wiki_app.md

```md
# Wiki de l'application — Empyrion Scenario Editor

Documentation de toutes les fonctions de l'outil, organisee par theme.

---

## 1. Les bases : projets et copie de travail

### Nouveau projet
**Fichier > Nouveau projet...** — Choisis un Scenario A (obligatoire), et si tu veux fusionner deux scenarios, coche "Mode fusion" et choisis un Scenario B. Indique ensuite un dossier de destination (qui ne doit pas exister deja) : c'est ta **copie de travail**.

A la creation, l'outil copie **integralement et a l'identique** le Scenario A dans le dossier de destination (tous les fichiers, pas seulement les .ecf/.csv/.yaml). Rien n'est invente ni transforme a la copie.

### Copie de travail vs sources
- **Scenario A / Scenario B** : affiches en bas, en **lecture seule**. Ce sont tes references, jamais modifiees par l'outil.
- **Copie de travail** : affichee au milieu, **modifiable**. C'est le seul endroit ou tu edites, fusionnes, dupliques.

### Projets recents
**Fichier > Projets recents...** (ou automatiquement propose au demarrage) — reprend un projet existant **sans recopier** la copie de travail (tes modifications precedentes restent intactes). Utile pour continuer un travail en cours sur plusieurs sessions.

### Arborescence
Les trois panneaux (A, copie de travail, B) affichent **l'arborescence exacte du disque** — comme un explorateur de fichiers classique, pas de categorisation artificielle.

---

## 2. Fusionner depuis Scenario A ou B

### Fusionner un fichier entier
Clic droit sur un fichier dans Scenario A ou B > **"Copier / fusionner vers la copie de travail"**.

- Si le fichier n'existe pas encore dans la copie de travail : simple copie.
- Si c'est un **.ecf** deja existant : fusion intelligente par bloc (voir plus bas).
- Si c'est un **.csv** deja existant : fusion par cle (1ere colonne) — la copie de travail est **toujours prioritaire** : une ligne dont la cle existe deja n'est jamais ecrasee, seules les cellules **vides** sont completees ; les lignes absentes sont ajoutees.
- Les autres formats (yaml, txt...) : simple copie qui **remplace** le fichier existant (pas de fusion intelligente pour ces formats).

### Fusionner un dossier entier
Clic droit sur **n'importe quel dossier** > "Fusionner ce dossier (et sous-dossiers)" — applique la meme logique a tous les fichiers qu'il contient, en une seule action. Une barre de progression s'affiche pour les gros dossiers.

### Fusion ECF — comment ca marche precisement
- La copie de travail est **prioritaire** : ses proprietes et blocs existants ne sont jamais ecrases.
- Les blocs et proprietes **absents** de la copie de travail sont ajoutes.
- **Garde-fou anti-collision** : si un Id est partage entre deux blocs dont le `Name` differe (meme Id, materiel different — ca arrive entre scenarios independants), le bloc **n'est jamais fusionne a l'aveugle**. Il est ajoute en fin de fichier, **desactive** (commente), pour revue manuelle (voir "Blocs en attente" plus bas).

### Copier un seul bloc / une seule ligne
Clic droit sur un bloc ECF (dans l'arbre) ou une ligne CSV, dans la vue Scenario A/B > "Copier ce bloc/cette ligne vers la copie de travail" — fusionne **seulement cet element**, sans toucher au reste du fichier.

### Dupliquer avec un nouvel identifiant
Clic droit sur un bloc ECF ou une ligne CSV en lecture seule > "Dupliquer avec un nouvel Id/une nouvelle cle..." — contrairement a "copier/fusionner", ceci cree un **element totalement independant** (pas de fusion), en te laissant choisir un nouvel Id et/ou un nouveau Name (avec suggestions d'Ids libres). Pratique pour partir d'un bloc existant comme modele pour en creer un nouveau distinct (ex : une variante d'un item).

- Fonctionne aussi sur des blocs **sans Id** (identifies seulement par `Name`) — cas reel dans certains fichiers Empyrion.
- Tu peux aussi **abandonner l'Id** du bloc duplique pour ne l'identifier que par Name.
- Si tu dupliques un **sous-bloc imbrique** (ex: un `Mode` dans un `Item`), il reste automatiquement **dans le meme bloc parent** dans la copie de travail (pas isole a la racine).
- Meme logique disponible pour le YAML (dupliquer une entree avec une nouvelle cle/valeur).

---

## 3. Editer la copie de travail

### Fichiers ECF
Double-clic sur un `.ecf` dans la copie de travail : ouvre une **vue comparative** (ta copie a gauche, editable ; Scenario A/B a droite, lecture seule, en onglets).

- **Double-clic sur une valeur** dans le tableau de proprietes pour l'editer.
- **+ Bloc** / **+ Propriete** pour ajouter.
- Clic droit sur une propriete : **Supprimer**, **Traduire vers...**, **Mise en forme BBCode...**
- Toute modification de valeur est **automatiquement annotee** : `# original: <ancienne_valeur> -- Mod par <toi>` (configurable dans **Options**).

### Fichiers CSV
Double-clic sur un `.csv` : tableau editable.
- **+ Ligne** / **Supprimer la ligne selectionnee**.
- Clic droit : Copier/Couper/Coller (compatible Excel, format tabule), **Supprimer le contenu** (vide la cellule) vs **Supprimer la ligne entiere** (deux actions distinctes), Traduire, BBCode.
- Le **delimiteur** (`,` ou `;`) et le **style de fin de ligne** sont detectes automatiquement et preserves.

### Fichiers YAML
Double-clic sur un `.yaml`/`.yml` : arbre de navigation a gauche (cle + apercu), panneau de valeur editable a droite avec bouton **"Appliquer cette valeur"** — plus adapte qu'une edition en cellule vu la structure imbriquee des playfields.
- **+ Entree** / **Supprimer l'entree selectionnee**.
- Traduction et BBCode disponibles sur la valeur en cours d'edition.

### Fichiers TXT
Double-clic sur un `.txt` : editeur de texte simple. Copier/couper/coller natifs (Qt), plus traduction et BBCode sur une selection via clic droit.

### Copier / Couper / Coller (tableaux CSV et ECF)
`Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Suppr` fonctionnent sur les tableaux, avec un format compatible Excel (tabulations). La colonne "Cle" d'un tableau de proprietes ECF reste protegee en ecriture (impossible de la modifier par un collage accidentel).

---

## 4. Traduction

Disponible partout ou tu edites du texte (CSV, ECF, YAML, TXT), via clic droit > **"Traduire vers..."**. Utilise Google Translate (bibliotheque `deep-translator`, gratuite, necessite une connexion internet).

- **Protection du BBCode et des placeholders** : les balises (`[b]`, `[color=#RRGGBB]`...) et jetons de substitution (`{PlayerName}`, `%d`, `%s`...) sont automatiquement extraits avant traduction et reinjectes a leur place — jamais traduits ni casses.
- **Traduction CSV cible la bonne colonne** : clic droit sur une cellule source (ex: colonne `English`) et choisis la langue cible (ex: `Francais`) — le resultat va dans la colonne correspondante (ex: `Français`), pas dans la cellule source. La correspondance de colonne est insensible aux accents et reconnait plusieurs conventions de nommage (code ISO, nom anglais, nom natif).
- **Depuis Scenario A/B (lecture seule)** : tu peux traduire directement une cellule source et le resultat s'applique dans la cellule correspondante de la **copie de travail**.
- La fenetre de resultat te laisse **relire et corriger** la traduction avant de l'appliquer.

## 5. Mise en forme BBCode

Clic droit > **"Mise en forme BBCode..."** ouvre une petite fenetre : selectionne une portion de texte a la souris, clique une couleur (palette de 10 teintes) ou un style (Gras/Italique/Souligne) pour l'entourer automatiquement des bonnes balises (`[color=#FF0000]...[/color]`, `[b]...[/b]`...).

---

## 6. Verifications

### Verifier les references (menu Verification)
Controle que chaque `Ref: X` correspond bien a un `Name: X` existant quelque part dans le scenario — `Ref` est le mecanisme d'heritage d'Empyrion, une reference cassee echoue silencieusement en jeu (pas de message d'erreur, juste des proprietes manquantes). A lancer apres une fusion.

### Blocs en attente (menu Verification)
Liste tous les blocs mis en attente (desactives) par le garde-fou anti-collision du merge. Pour chacun :
- **Comparaison detaillee** avec le bloc actuellement actif (diff propriete par propriete).
- **Suggestions d'Id libres** (calculees au-dessus du maximum utilise dans le scenario).
- Bouton pour **activer** le bloc avec le nouvel Id choisi — evite d'editer le fichier a la main (risque reel de casser la structure si la ligne de fermeture `}` reste commentee par erreur).

### Filtrer par propriete
Dans la vue d'un fichier ECF, bouton **"Filtrer par propriete..."** : liste toutes les proprietes existantes dans le fichier (avec leur nombre d'occurrences), coche-en une ou plusieurs pour filtrer l'arbre en direct (masque les blocs qui ne les ont pas toutes).

### Recherche
Chaque vue de fichier a une barre de recherche (Id / Name / cle / valeur selon le format) avec navigation "suivant" — indispensable des qu'un fichier depasse quelques centaines d'entrees.

---

## 7. Options

**Options > Nom pour les annotations...** — le nom qui apparait dans les commentaires de tracabilite (`Mod par <nom>`).

**Options > Annoter les modifications automatiquement** — active/desactive l'annotation automatique.

---

## 8. Scripts de diagnostic (ligne de commande)

Utiles en complement de l'interface, a lancer depuis un terminal dans le dossier du projet :

- `verifier_parser_ecf.py <fichier_ou_dossier>` — verifie le round-trip (fidelite parfaite) d'un ou plusieurs fichiers ECF.
- `verifier_parser_yaml.py <fichier_ou_dossier>` — meme chose pour le YAML.
- `verifier_parser_csv.py <fichier_ou_dossier>` — meme chose pour le CSV.
- `diagnostic_bloc.py <fichier.ecf> <Id>` — cherche un bloc precis par Id, y compris dans les commentaires (utile si un bloc semble avoir disparu).
- `detecter_imbrication_anormale.py <fichier.ecf>` — detecte les blocs qui ont "avale" le reste du fichier par erreur (typiquement apres une edition manuelle qui a laisse une accolade fermante commentee).

---

## 9. Limitations connues

- Pas encore de copier/coller multi-lignes façon tableur pour le YAML (structure trop imbriquee pour que ca ait du sens de la meme facon).
- La fusion "intelligente" (priorite copie de travail, completion) n'existe que pour ECF et CSV. Les autres formats (YAML, TXT...) sont remplaces entierement lors d'une fusion de fichier.
- La traduction necessite une connexion internet (Google Translate).

```

### docs\wiki_app_en.md

```md
# Application Wiki — Empyrion Scenario Editor

Documentation of every function of the tool, organized by topic.

---

## 1. The basics: projects and working copy

### New project
**File > New project...** — Choose a Scenario A (required), and if you want to merge two scenarios, check "Merge mode" and choose a Scenario B. Then pick a destination folder (must not already exist): this is your **working copy**.

On creation, the tool copies the **entire, exact** content of Scenario A into the destination folder (all files, not just .ecf/.csv/.yaml). Nothing is invented or transformed during the copy.

### Working copy vs sources
- **Scenario A / Scenario B**: shown at the bottom, **read-only**. These are your references, never modified by the tool.
- **Working copy**: shown in the middle, **editable**. This is the only place you edit, merge, or duplicate.

### Recent projects
**File > Recent projects...** (or automatically offered at startup) — resumes an existing project **without recopying** the working copy (your previous changes stay intact). Useful for continuing work across multiple sessions.

### Folder tree
All three panels (A, working copy, B) show **the exact folder structure from disk** — like a regular file explorer, no artificial categorization.

---

## 2. Merging from Scenario A or B

### Merging a whole file
Right-click a file in Scenario A or B > **"Copy / merge to working copy"**.

- If the file doesn't exist yet in the working copy: plain copy.
- If it's an existing **.ecf** file: smart per-block merge (see below).
- If it's an existing **.csv** file: merge by key (1st column) — the working copy is **always prioritized**: a row whose key already exists is never overwritten, only **empty** cells get filled in; missing rows are added.
- Other formats (yaml, txt...): plain copy that **replaces** the existing file (no smart merge for these formats).

### Merging a whole folder
Right-click **any folder** > "Merge this folder (and subfolders)" — applies the same logic to every file it contains, in a single action. A progress bar shows for large folders.

### ECF merge — how it works precisely
- The working copy is **prioritized**: its existing properties and blocks are never overwritten.
- Blocks and properties **missing** from the working copy are added.
- **Anti-collision safeguard**: if an Id is shared between two blocks whose `Name` differs (same Id, different content — happens between independent scenarios), the block is **never blindly merged**. It's added at the end of the file, **disabled** (commented out), for manual review (see "Pending blocks" below).

### Copying a single block / a single row
Right-click a block in the ECF tree, or a CSV row, in the Scenario A/B view > "Copy this block/row to working copy" — merges **only that element**, leaving the rest of the file untouched.

### Duplicating with a new identifier
Right-click a read-only ECF block or CSV row > "Duplicate with a new Id/key..." — unlike "copy/merge", this creates a **fully independent element** (no merge), letting you choose a new Id and/or a new Name (with free-Id suggestions). Handy to start from an existing block as a template for a new, distinct one (e.g. a variant of an item).

- Also works on blocks **without an Id** (identified only by `Name`) — a real case in some Empyrion files.
- You can also **drop the Id** on the duplicate, leaving it identified by Name only.
- If you duplicate a **nested sub-block** (e.g. a `Mode` inside an `Item`), it automatically stays **inside the same parent block** in the working copy (not orphaned at the root).
- Same logic available for YAML (duplicating an entry with a new key/value).

---

## 3. Editing the working copy

### ECF files
Double-click a `.ecf` in the working copy: opens a **comparison view** (your copy on the left, editable; Scenario A/B on the right, read-only, in tabs).

- **Double-click a value** in the property table to edit it.
- **+ Block** / **+ Property** to add.
- Right-click a property: **Delete**, **Translate to...**, **BBCode formatting...**
- Every value change is **automatically annotated**: `# original: <old_value> -- Mod by <you>` (configurable in **Options**).

### CSV files
Double-click a `.csv`: editable table.
- **+ Row** / **Delete selected row**.
- Right-click: Copy/Cut/Paste (Excel-compatible, tab-delimited), **Clear content** (empties the cell) vs **Delete entire row** (two distinct actions), Translate, BBCode.
- The **delimiter** (`,` or `;`) and **line-ending style** are auto-detected and preserved.

### YAML files
Double-click a `.yaml`/`.yml`: navigation tree on the left (key + preview), editable value panel on the right with an **"Apply this value"** button — better suited than in-cell editing given the nested structure of playfields.
- **+ Entry** / **Delete selected entry**.
- Translation and BBCode available on the value being edited.

### TXT files
Double-click a `.txt`: simple text editor. Native copy/cut/paste (Qt), plus translation and BBCode on a selection via right-click.

### Copy / Cut / Paste (CSV and ECF tables)
`Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Delete` work on tables, using an Excel-compatible format (tabs). The "Key" column of an ECF property table stays write-protected (can't be changed by an accidental paste).

---

## 4. Translation

Available everywhere you edit text (CSV, ECF, YAML, TXT), via right-click > **"Translate to..."**. Uses Google Translate (`deep-translator` library, free, requires an internet connection).

- **BBCode and placeholder protection**: tags (`[b]`, `[color=#RRGGBB]`...) and substitution tokens (`{PlayerName}`, `%d`, `%s`...) are automatically extracted before translation and reinserted in place — never translated or broken.
- **CSV translation targets the right column**: right-click a source cell (e.g. the `English` column) and pick the target language (e.g. `Francais`) — the result goes into the matching column (e.g. `Français`), not the source cell. Column matching is accent-insensitive and recognizes several naming conventions (ISO code, English name, native name).
- **From Scenario A/B (read-only)**: you can translate a source cell directly and the result gets applied to the matching cell in the **working copy**.
- The result window lets you **review and correct** the translation before applying it.

## 5. BBCode formatting

Right-click > **"BBCode formatting..."** opens a small window: select a portion of text with the mouse, click a color (10-swatch palette) or a style (Bold/Italic/Underline) to automatically wrap it in the right tags (`[color=#FF0000]...[/color]`, `[b]...[/b]`...).

---

## 6. Checks

### Check references (Verification menu)
Checks that every `Ref: X` matches an existing `Name: X` somewhere in the scenario — `Ref` is Empyrion's inheritance mechanism, a broken reference fails silently in-game (no error message, just missing properties). Run this after a merge.

### Pending blocks (Verification menu)
Lists every block put on hold (disabled) by the merge's anti-collision safeguard. For each one:
- **Detailed comparison** with the currently active block (property-by-property diff).
- **Free-Id suggestions** (computed above the highest Id currently used in the scenario).
- A button to **activate** the block with the chosen new Id — avoids editing the file by hand (real risk of breaking the structure if the closing `}` line stays commented out by mistake).

### Filter by property
In an ECF file view, the **"Filter by property..."** button lists every property that exists in the file (with its occurrence count); check one or more to filter the tree live (hides blocks that don't have all of them).

### Search
Every file view has a search bar (Id / Name / key / value depending on the format) with "next" navigation — essential once a file goes beyond a few hundred entries.

---

## 7. Options

**Options > Name for annotations...** — the name that appears in traceability comments (`Mod by <name>`).

**Options > Automatically annotate changes** — enables/disables automatic annotation.

**Language button (toolbar)** — switches the interface between French and English instantly, no restart needed. The choice is saved between sessions.

---

## 8. Diagnostic scripts (command line)

Useful alongside the interface, run from a terminal in the project folder:

- `verifier_parser_ecf.py <file_or_folder>` — checks round-trip fidelity (perfect reproduction) of one or more ECF files.
- `verifier_parser_yaml.py <file_or_folder>` — same for YAML.
- `verifier_parser_csv.py <file_or_folder>` — same for CSV.
- `diagnostic_bloc.py <file.ecf> <Id>` — looks for a specific block by Id, including inside comments (useful if a block seems to have disappeared).
- `detecter_imbrication_anormale.py <file.ecf>` — detects blocks that have mistakenly "swallowed" the rest of the file (typically after a manual edit that left a closing brace commented out).

---

## 9. Known limitations

- No spreadsheet-style multi-row copy/paste for YAML yet (the structure is too nested for that to make sense the same way).
- "Smart" merge (working-copy priority, gap-filling) only exists for ECF and CSV. Other formats (YAML, TXT...) are replaced entirely during a file merge.
- Translation requires an internet connection (Google Translate).

```

### docs\wiki_app_fr.md

```md
# Wiki de l'application — Empyrion Scenario Editor

Documentation de toutes les fonctions de l'outil, organisee par theme.

---

## 1. Les bases : projets et copie de travail

### Nouveau projet
**Fichier > Nouveau projet...** — Choisis un Scenario A (obligatoire), et si tu veux fusionner deux scenarios, coche "Mode fusion" et choisis un Scenario B. Indique ensuite un dossier de destination (qui ne doit pas exister deja) : c'est ta **copie de travail**.

A la creation, l'outil copie **integralement et a l'identique** le Scenario A dans le dossier de destination (tous les fichiers, pas seulement les .ecf/.csv/.yaml). Rien n'est invente ni transforme a la copie.

### Copie de travail vs sources
- **Scenario A / Scenario B** : affiches en bas, en **lecture seule**. Ce sont tes references, jamais modifiees par l'outil.
- **Copie de travail** : affichee au milieu, **modifiable**. C'est le seul endroit ou tu edites, fusionnes, dupliques.

### Projets recents
**Fichier > Projets recents...** (ou automatiquement propose au demarrage) — reprend un projet existant **sans recopier** la copie de travail (tes modifications precedentes restent intactes). Utile pour continuer un travail en cours sur plusieurs sessions.

### Arborescence
Les trois panneaux (A, copie de travail, B) affichent **l'arborescence exacte du disque** — comme un explorateur de fichiers classique, pas de categorisation artificielle.

---

## 2. Fusionner depuis Scenario A ou B

### Fusionner un fichier entier
Clic droit sur un fichier dans Scenario A ou B > **"Copier / fusionner vers la copie de travail"**.

- Si le fichier n'existe pas encore dans la copie de travail : simple copie.
- Si c'est un **.ecf** deja existant : fusion intelligente par bloc (voir plus bas).
- Si c'est un **.csv** deja existant : fusion par cle (1ere colonne) — la copie de travail est **toujours prioritaire** : une ligne dont la cle existe deja n'est jamais ecrasee, seules les cellules **vides** sont completees ; les lignes absentes sont ajoutees.
- Les autres formats (yaml, txt...) : simple copie qui **remplace** le fichier existant (pas de fusion intelligente pour ces formats).

### Fusionner un dossier entier
Clic droit sur **n'importe quel dossier** > "Fusionner ce dossier (et sous-dossiers)" — applique la meme logique a tous les fichiers qu'il contient, en une seule action. Une barre de progression s'affiche pour les gros dossiers.

### Fusion ECF — comment ca marche precisement
- La copie de travail est **prioritaire** : ses proprietes et blocs existants ne sont jamais ecrases.
- Les blocs et proprietes **absents** de la copie de travail sont ajoutes.
- **Garde-fou anti-collision** : si un Id est partage entre deux blocs dont le `Name` differe (meme Id, materiel different — ca arrive entre scenarios independants), le bloc **n'est jamais fusionne a l'aveugle**. Il est ajoute en fin de fichier, **desactive** (commente), pour revue manuelle (voir "Blocs en attente" plus bas).

### Copier un seul bloc / une seule ligne
Clic droit sur un bloc ECF (dans l'arbre) ou une ligne CSV, dans la vue Scenario A/B > "Copier ce bloc/cette ligne vers la copie de travail" — fusionne **seulement cet element**, sans toucher au reste du fichier.

### Dupliquer avec un nouvel identifiant
Clic droit sur un bloc ECF ou une ligne CSV en lecture seule > "Dupliquer avec un nouvel Id/une nouvelle cle..." — contrairement a "copier/fusionner", ceci cree un **element totalement independant** (pas de fusion), en te laissant choisir un nouvel Id et/ou un nouveau Name (avec suggestions d'Ids libres). Pratique pour partir d'un bloc existant comme modele pour en creer un nouveau distinct (ex : une variante d'un item).

- Fonctionne aussi sur des blocs **sans Id** (identifies seulement par `Name`) — cas reel dans certains fichiers Empyrion.
- Tu peux aussi **abandonner l'Id** du bloc duplique pour ne l'identifier que par Name.
- Si tu dupliques un **sous-bloc imbrique** (ex: un `Mode` dans un `Item`), il reste automatiquement **dans le meme bloc parent** dans la copie de travail (pas isole a la racine).
- Meme logique disponible pour le YAML (dupliquer une entree avec une nouvelle cle/valeur).

---

## 3. Editer la copie de travail

### Fichiers ECF
Double-clic sur un `.ecf` dans la copie de travail : ouvre une **vue comparative** (ta copie a gauche, editable ; Scenario A/B a droite, lecture seule, en onglets).

- **Double-clic sur une valeur** dans le tableau de proprietes pour l'editer.
- **+ Bloc** / **+ Propriete** pour ajouter.
- Clic droit sur une propriete : **Supprimer**, **Traduire vers...**, **Mise en forme BBCode...**
- Toute modification de valeur est **automatiquement annotee** : `# original: <ancienne_valeur> -- Mod par <toi>` (configurable dans **Options**).

### Fichiers CSV
Double-clic sur un `.csv` : tableau editable.
- **+ Ligne** / **Supprimer la ligne selectionnee**.
- Clic droit : Copier/Couper/Coller (compatible Excel, format tabule), **Supprimer le contenu** (vide la cellule) vs **Supprimer la ligne entiere** (deux actions distinctes), Traduire, BBCode.
- Le **delimiteur** (`,` ou `;`) et le **style de fin de ligne** sont detectes automatiquement et preserves.

### Fichiers YAML
Double-clic sur un `.yaml`/`.yml` : arbre de navigation a gauche (cle + apercu), panneau de valeur editable a droite avec bouton **"Appliquer cette valeur"** — plus adapte qu'une edition en cellule vu la structure imbriquee des playfields.
- **+ Entree** / **Supprimer l'entree selectionnee**.
- Traduction et BBCode disponibles sur la valeur en cours d'edition.

### Fichiers TXT
Double-clic sur un `.txt` : editeur de texte simple. Copier/couper/coller natifs (Qt), plus traduction et BBCode sur une selection via clic droit.

### Copier / Couper / Coller (tableaux CSV et ECF)
`Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Suppr` fonctionnent sur les tableaux, avec un format compatible Excel (tabulations). La colonne "Cle" d'un tableau de proprietes ECF reste protegee en ecriture (impossible de la modifier par un collage accidentel).

---

## 4. Traduction

Disponible partout ou tu edites du texte (CSV, ECF, YAML, TXT), via clic droit > **"Traduire vers..."**. Utilise Google Translate (bibliotheque `deep-translator`, gratuite, necessite une connexion internet).

- **Protection du BBCode et des placeholders** : les balises (`[b]`, `[color=#RRGGBB]`...) et jetons de substitution (`{PlayerName}`, `%d`, `%s`...) sont automatiquement extraits avant traduction et reinjectes a leur place — jamais traduits ni casses.
- **Traduction CSV cible la bonne colonne** : clic droit sur une cellule source (ex: colonne `English`) et choisis la langue cible (ex: `Francais`) — le resultat va dans la colonne correspondante (ex: `Français`), pas dans la cellule source. La correspondance de colonne est insensible aux accents et reconnait plusieurs conventions de nommage (code ISO, nom anglais, nom natif).
- **Depuis Scenario A/B (lecture seule)** : tu peux traduire directement une cellule source et le resultat s'applique dans la cellule correspondante de la **copie de travail**.
- La fenetre de resultat te laisse **relire et corriger** la traduction avant de l'appliquer.

## 5. Mise en forme BBCode

Clic droit > **"Mise en forme BBCode..."** ouvre une petite fenetre : selectionne une portion de texte a la souris, clique une couleur (palette de 10 teintes) ou un style (Gras/Italique/Souligne) pour l'entourer automatiquement des bonnes balises (`[color=#FF0000]...[/color]`, `[b]...[/b]`...).

---

## 6. Verifications

### Verifier les references (menu Verification)
Controle que chaque `Ref: X` correspond bien a un `Name: X` existant quelque part dans le scenario — `Ref` est le mecanisme d'heritage d'Empyrion, une reference cassee echoue silencieusement en jeu (pas de message d'erreur, juste des proprietes manquantes). A lancer apres une fusion.

### Blocs en attente (menu Verification)
Liste tous les blocs mis en attente (desactives) par le garde-fou anti-collision du merge. Pour chacun :
- **Comparaison detaillee** avec le bloc actuellement actif (diff propriete par propriete).
- **Suggestions d'Id libres** (calculees au-dessus du maximum utilise dans le scenario).
- Bouton pour **activer** le bloc avec le nouvel Id choisi — evite d'editer le fichier a la main (risque reel de casser la structure si la ligne de fermeture `}` reste commentee par erreur).

### Filtrer par propriete
Dans la vue d'un fichier ECF, bouton **"Filtrer par propriete..."** : liste toutes les proprietes existantes dans le fichier (avec leur nombre d'occurrences), coche-en une ou plusieurs pour filtrer l'arbre en direct (masque les blocs qui ne les ont pas toutes).

### Recherche
Chaque vue de fichier a une barre de recherche (Id / Name / cle / valeur selon le format) avec navigation "suivant" — indispensable des qu'un fichier depasse quelques centaines d'entrees.

---

## 7. Options

**Options > Nom pour les annotations...** — le nom qui apparait dans les commentaires de tracabilite (`Mod par <nom>`).

**Options > Annoter les modifications automatiquement** — active/desactive l'annotation automatique.

---

## 8. Scripts de diagnostic (ligne de commande)

Utiles en complement de l'interface, a lancer depuis un terminal dans le dossier du projet :

- `verifier_parser_ecf.py <fichier_ou_dossier>` — verifie le round-trip (fidelite parfaite) d'un ou plusieurs fichiers ECF.
- `verifier_parser_yaml.py <fichier_ou_dossier>` — meme chose pour le YAML.
- `verifier_parser_csv.py <fichier_ou_dossier>` — meme chose pour le CSV.
- `diagnostic_bloc.py <fichier.ecf> <Id>` — cherche un bloc precis par Id, y compris dans les commentaires (utile si un bloc semble avoir disparu).
- `detecter_imbrication_anormale.py <fichier.ecf>` — detecte les blocs qui ont "avale" le reste du fichier par erreur (typiquement apres une edition manuelle qui a laisse une accolade fermante commentee).

---

## 9. Limitations connues

- Pas encore de copier/coller multi-lignes façon tableur pour le YAML (structure trop imbriquee pour que ca ait du sens de la meme facon).
- La fusion "intelligente" (priorite copie de travail, completion) n'existe que pour ECF et CSV. Les autres formats (YAML, TXT...) sont remplaces entierement lors d'une fusion de fichier.
- La traduction necessite une connexion internet (Google Translate).

```

### docs\wiki_empyrion.md

```md
# Wiki Empyrion — structure des scenarios et proprietes ECF/YAML

Base sur la documentation communautaire (wiki officiel Empyrion sur Fandom, guides Steam,
forums officiels, outil eWCCT). Les informations les plus specifiques (valeurs exactes de
proprietes rares) meritent toujours une verification en jeu -- la documentation communautaire
evolue avec les mises a jour du jeu et n'est pas toujours a jour a 100%.

---

## 1. Structure d'un dossier de scenario

```
MonScenario/
├── Content/
│   └── Configuration/       <- Tous les fichiers .ecf de gameplay (voir section 2)
├── Playfields/               <- Un sous-dossier par playfield, avec son .yaml
├── Prefabs/                  <- Blueprints (.epb) des POI/vaisseaux customs
├── RandomPresets/             <- Fichiers SolarSystemConfig.yaml (generation procedurale)
├── Sectors/                  <- Sectors.yaml (structure de la galaxie)
├── Extras/                   <- Dialogues.csv, Localization.csv, autres CSV
├── SharedData/                <- Contenu partage entre plusieurs sous-scenarios/DLC
├── gameoptions.yaml            <- Options de partie par defaut
└── description.txt / Logos/   <- Metadonnees d'affichage du scenario
```

**Regle generale (confirmee par plusieurs guides communautaires)** : seuls les fichiers que tu
modifies reellement ont besoin d'etre presents dans le dossier de ton scenario -- tout fichier
absent est simplement herite du jeu de base (vanilla). C'est pour ca qu'un scenario "leger" ne
contient parfois que quelques fichiers dans `Content/Configuration`.

---

## 2. Les fichiers .ecf de `Content/Configuration`

| Fichier | Contenu |
|---|---|
| `BlocksConfig.ecf` | Tous les blocs constructibles (structure, hitpoints, materiau, categorie de placement...) |
| `ItemsConfig.ecf` | Tous les objets : armes, munitions, objets a main, consommables -- **y compris les items lies aux vehicules et bases** (ex: foreuses de vehicule), pas seulement les objets portes par le joueur |
| `Templates.ecf` | Recettes de craft (quels items produisent quel objet, avec quels ingredients) |
| `Containers.ecf` | Contenus par defaut des conteneurs (coffres, sacs...) |
| `LootGroups.ecf` | Groupes de loot utilises par les POI et conteneurs generes aleatoirement |
| `EClassConfig.ecf` | Classes d'entites (NPC, creatures) |
| `EGroupsConfig.ecf` | Groupes d'entites |
| `DefReputation.ecf` | Reputation par defaut envers les differentes factions |
| `FactionWarfare.ecf` | Regles de guerre entre factions |
| `MaterialConfig.ecf` | Proprietes des materiaux (resistance, etc.) |
| `StatusEffects.ecf` | Effets de statut (buffs/debuffs) |
| `TraderNPCConfig.ecf` | Configuration des marchands PNJ |
| `TokenConfig.ecf` | Jetons/codes de verrouillage utilises par les portes, coffres... (lies au systeme de dialogue) |
| `Dialogues.ecf` | Arbres de dialogue des PNJ |
| `Dialogues.csv` / `Localization.csv` | Textes localises utilises par les dialogues et l'interface |
| `GalaxyConfig.ecf` | Parametres globaux de generation de galaxie |
| `Config.ecf` (ou `Config_Example.ecf`) | Fichier de **surcharge** legere -- voir section 4, usage limite |

---

## 3. Syntaxe des fichiers .ecf

Format proprietaire d'Eleon, **pas du JSON ni du YAML** meme s'il y ressemble. Un bloc
("objet") s'ecrit entre accolades :

```
{ Block Id: 399, Name: ConcreteBlocks
  Material: concrete
  BlockColor: "170,170,170"
  Info: bkiBlockGroup, display: true
  IsOxygenTight: true, display: true
  HitPoints: 600, type: int, display: false
  Mass: 1100, type: float, display: true, formatter: Kilogram
  Volume: 10, type: float, display: true, formatter: Liter
  Category: BuildingBlocks
  ChildBlocks: "ConcreteFull, ConcreteThin, ConcreteExtended"
  UnlockCost: 0
  UnlockLevel: 1
}
```

Points cles (source : guide Steam "Gentle guide to .ECF modding", confirme par le forum
officiel) :

- **`Id`** identifie le bloc/item de facon unique dans le fichier. Certains blocs reels n'ont
  **pas d'Id du tout** et sont identifies seulement par `Name` -- convention plus rare mais
  bien reelle (ex: `{ Block Name: LegacyForcefield ...}`).
- **`Name`** est le nom interne (pas le nom affiche en jeu -- celui-la vient de la
  localisation). **Ne jamais changer l'Id ou le Name d'un bloc/item existant** : ca casse les
  references dans les autres fichiers et les sauvegardes existantes.
- **`Ref: AutreNom`** fait heriter un bloc/item des proprietes d'un autre (mecanisme
  d'heritage) -- tres utilise pour creer des variantes (ex: une arme "Epic" qui herite de
  l'arme de base et ne redefinit que les stats qui changent).
- Une propriete peut avoir des **sous-attributs** apres une virgule : `type` (int/float/string),
  `display` (true/false -- affiche ou non l'info-bulle en jeu), `formatter` (unite d'affichage :
  `Kilogram`, `Liter`, `Watt`, `ROF`...).
- Les valeurs contenant une **virgule** doivent etre entre guillemets :
  `AllowPlacingAt: "Base,MS", display: true`. Une virgule non protegee casse le parsing.
- **Commentaires** : tout ce qui suit un `#` sur une ligne est ignore par le jeu.
- Le prefixe **`+`** avant un genre de bloc (`+Block`, `+Container`...) signale un **patch**
  qui complete une definition existante du meme Id, plutot qu'une nouvelle definition
  independante -- convention frequente dans les gros fichiers modifies au fil du temps.
- Une erreur de syntaxe (accolade manquante, virgule non protegee, propriete dupliquee) peut
  empecher le fichier entier de charger, avec un message dans la console du jeu (touche
  antiquote pour l'ouvrir) du type "Ignored unknown parameter(s) in element...".

### Sous-blocs imbriques
Un item peut contenir des sous-blocs (ex: `{ Mode Id: 0 ... }` pour un mode d'arme,
`{ Child Inputs ... }` pour les ingredients d'une recette). Un item peut avoir **plusieurs
`Mode`** pour representer plusieurs modes de tir (semi-auto/rafale, etc.).

---

## 4. `Config.ecf` vs les fichiers dedies -- un piege frequent

Confirme par de nombreux fils de discussion officiels (le sujet revient tres souvent) :
**`Config.ecf` ne peut surcharger QUE les proprietes deja presentes dans
`Config_Example.ecf`** -- ce n'est pas un fichier de surcharge universel. Si tu veux modifier
une propriete qui n'existe pas dans `Config_Example.ecf` (ex: `AllowPlacingAt` pour un bloc
donne), il faut editer directement `BlocksConfig.ecf` (ou le fichier dedie correspondant),
**pas `Config.ecf`**. Tenter de le faire dans `Config.ecf` produit une erreur silencieuse en
jeu ("Ignored unknown parameter(s)"), sans planter, mais sans effet non plus.

Consequence pratique : pour la plupart des mods de scenario serieux, on modifie directement les
fichiers dedies (`BlocksConfig.ecf`, `ItemsConfig.ecf`...) plutot que `Config.ecf`.

---

## 5. Les fichiers `.yaml` (playfields)

Contrairement aux `.ecf`, les playfields utilisent un **vrai YAML** (indentation, listes `-`).
Fichier principal : `playfield.yaml` (ou `playfield_static.yaml` / `playfield_dynamic.yaml`
selon le type) dans `Playfields/<NomDuPlayfield>/`.

### Ajouter un POI custom (base sur le guide officiel "Customized POIs")
1. Placer le fichier `.epb` du blueprint dans `Prefabs/`.
2. Dans le `playfield.yaml`, chercher la section `POIs: ... Random:` et ajouter une entree :
```yaml
- GroupName: JunkT1
  CountMinMax: [4, 5]
  DroneProb: 0
  DronesMinMax: [0]
  ReserveCount: 0
  TroopTransport: False
  SpawnPOINear: [START]
  SpawnPOINearRange: [500, 1000]
  Properties:
    - Key: MapDistance
      Value: 600
    - Key: MapMarker
      Value: Neutral
    - Key: RegenAfter
      Value: 720
```
3. `GroupName` doit correspondre au nom de groupe de ton blueprint (un POI ne peut appartenir
   qu'a **un seul** groupe).

**Piege important, confirme par le forum officiel** : modifier un `playfield.yaml` n'affecte
**que les nouvelles parties** (ou les playfields jamais visites dans une sauvegarde existante).
Un playfield deja genere dans une sauvegarde en cours garde son etat en cache -- les
changements sur les POI de planetes/lunes ne s'appliquent pas retroactivement (contrairement
aux playfields spatiaux, plus flexibles a ce niveau).

Les lignes marquees "Please don't change" ou "No functionality yet" dans le fichier lui-meme
sont a eviter (info du wiki officiel, "Customizing Solar Systems").

---

## 6. RandomPresets / Sectors -- generation de la galaxie

- `RandomPresets/*.yaml` (fichiers `SolarSystemConfig.yaml`) controlent la generation
  procedurale des systemes solaires.
- `Sectors/Sectors.yaml` definit la structure de la galaxie (quels secteurs, quelles planetes
  de depart).
- `gameoptions.yaml` / `gameoptions_example.yaml` : options de partie par defaut proposees a
  la creation d'une nouvelle partie avec ce scenario.

Convention communautaire frequente pour un scenario "leger" (juste des configs modifiees, pas
un monde entierement custom) : copier ces fichiers depuis le scenario "Default Random" du jeu
de base tel quel, et ne modifier que `Content/Configuration`.

---

## 7. Dialogues, Tokens et Localisation

- **`Dialogues.ecf`** definit les arbres de dialogue des PNJ et des blocs interactifs (portes
  a code, panneaux...). Un bloc peut declencher un dialogue via la propriete
  `ExecuteOnActivate` dans `BlocksConfig.ecf`.
- **`TokenConfig.ecf`** definit les codes de verrouillage (1 a 9999) utilisables sur les portes
  et conteneurs, lies au systeme de dialogue.
- **`Localization.csv`** contient les textes traduits utilises par les dialogues et
  l'interface -- structure typique : une colonne `Key`, puis une colonne par langue
  (`English`, `Deutsch`, `Français`...).
- Les dialogues supportent des variables dynamiques (`{PlayerName}`) et des fonctions
  avancees (`Execute`/`ExecuteEditor`, en C# simplifie) pour des mecaniques de quete
  personnalisees.

---

## 8. Points de vigilance generaux pour la fusion/modification de scenario

1. **Toujours travailler sur une copie**, jamais sur les fichiers vanilla ou un scenario en
   ligne (confirme par tous les guides communautaires consultes).
2. **Ne jamais changer l'Id ou le Name** d'un bloc/item deja reference ailleurs (recettes,
   loot tables, playfields) -- ca casse les references.
3. Une **virgule non protegee** dans une valeur de liste (`AllowPlacingAt: Base,MS` au lieu de
   `"Base,MS"`) est l'erreur de syntaxe la plus frequemment signalee dans les forums.
4. Verifier la console en jeu (touche antiquote) apres chargement pour reperer les erreurs de
   parsing -- le jeu indique souvent precisement quel element pose probleme.
5. Un playfield deja visite dans une sauvegarde ne recharge pas ses changements de POI --
   tester sur une **nouvelle partie**.
6. Un Id partage entre deux definitions differentes (par exemple lors d'une fusion entre deux
   scenarios independants) est une source reelle et documentee de conflits -- c'est
   precisement ce que le garde-fou anti-collision de cet outil est concu pour detecter (voir
   le wiki de l'application).

---

## Sources consultees

- Wiki officiel Empyrion (Fandom) -- pages "Guide/Customized POIs", "Guide/Customizing Solar
  Systems", "Scenarios"
- Steam Community, guide "Gentle guide to .ECF modding" (zaphodikus et al.)
- Steam Community, guide "Custom Scenarios for Dummies"
- Steam Workshop, "Scenario for Custom Config Mods"
- Forums officiels Empyrion (empyriononline.com) -- fils sur Config.ecf, ItemsConfig.ecf,
  terrain.ecf
- Discussions Steam Community sur les erreurs de parsing ECF
- Documentation de l'outil communautaire eWCCT (Empyrion Web Config Creator Tool) pour le
  systeme de dialogue/tokens

```

### docs\wiki_empyrion_en.md

```md
# Empyrion Wiki — scenario structure and ECF/YAML properties

Based on community documentation (official Empyrion wiki on Fandom, Steam guides,
official forums, the eWCCT tool). The most specific pieces of information (exact values
of rare properties) always deserve in-game verification — community documentation
evolves with game updates and isn't always 100% current.

---

## 1. Structure of a scenario folder

```
MyScenario/
├── Content/
│   └── Configuration/       <- All gameplay .ecf files (see section 2)
├── Playfields/               <- One subfolder per playfield, with its .yaml
├── Prefabs/                  <- Blueprints (.epb) of custom POIs/ships
├── RandomPresets/             <- SolarSystemConfig.yaml files (procedural generation)
├── Sectors/                  <- Sectors.yaml (galaxy structure)
├── Extras/                   <- Dialogues.csv, Localization.csv, other CSVs
├── SharedData/                <- Content shared across sub-scenarios/DLC
├── gameoptions.yaml            <- Default game options
└── description.txt / Logos/   <- Scenario display metadata
```

**General rule (confirmed by several community guides)**: only the files you actually
modify need to be present in your scenario folder — any missing file simply falls back
to the base game (vanilla). That's why a "light" scenario sometimes contains only a
handful of files in `Content/Configuration`.

---

## 2. The .ecf files in `Content/Configuration`

| File | Content |
|---|---|
| `BlocksConfig.ecf` | All buildable blocks (structure, hitpoints, material, placement category...) |
| `ItemsConfig.ecf` | All objects: weapons, ammo, hand items, consumables -- **including vehicle/base-related items** (e.g. vehicle drills), not just player-carried items |
| `Templates.ecf` | Crafting recipes (which items produce which object, with which ingredients) |
| `Containers.ecf` | Default contents of containers (chests, bags...) |
| `LootGroups.ecf` | Loot groups used by POIs and randomly generated containers |
| `EClassConfig.ecf` | Entity classes (NPCs, creatures) |
| `EGroupsConfig.ecf` | Entity groups |
| `DefReputation.ecf` | Default reputation towards the different factions |
| `FactionWarfare.ecf` | Rules of war between factions |
| `MaterialConfig.ecf` | Material properties (resistance, etc.) |
| `StatusEffects.ecf` | Status effects (buffs/debuffs) |
| `TraderNPCConfig.ecf` | NPC trader configuration |
| `TokenConfig.ecf` | Lock tokens/codes used by doors, chests... (tied to the dialogue system) |
| `Dialogues.ecf` | NPC dialogue trees |
| `Dialogues.csv` / `Localization.csv` | Localized texts used by dialogues and the UI |
| `GalaxyConfig.ecf` | Global galaxy-generation parameters |
| `Config.ecf` (or `Config_Example.ecf`) | Light **override** file -- see section 4, limited use |

---

## 3. ECF file syntax

Eleon's proprietary format, **not JSON nor YAML** despite resembling both. An "object"
(block) is written between curly braces:

```
{ Block Id: 399, Name: ConcreteBlocks
  Material: concrete
  BlockColor: "170,170,170"
  Info: bkiBlockGroup, display: true
  IsOxygenTight: true, display: true
  HitPoints: 600, type: int, display: false
  Mass: 1100, type: float, display: true, formatter: Kilogram
  Volume: 10, type: float, display: true, formatter: Liter
  Category: BuildingBlocks
  ChildBlocks: "ConcreteFull, ConcreteThin, ConcreteExtended"
  UnlockCost: 0
  UnlockLevel: 1
}
```

Key points (source: Steam guide "Gentle guide to .ECF modding", confirmed by the
official forum):

- **`Id`** uniquely identifies the block/item within the file. Some real blocks have
  **no Id at all** and are identified only by `Name` -- a rarer but genuinely real
  convention (e.g. `{ Block Name: LegacyForcefield ...}`).
- **`Name`** is the internal name (not the in-game display name -- that comes from
  localization). **Never change the Id or Name of an existing block/item**: it breaks
  references in other files and in existing saves.
- **`Ref: OtherName`** makes a block/item inherit properties from another (inheritance
  mechanism) -- widely used to create variants (e.g. an "Epic" weapon that inherits from
  the base weapon and only redefines the stats that change).
- A property can have **sub-attributes** after a comma: `type` (int/float/string),
  `display` (true/false -- whether the tooltip is shown in-game), `formatter` (display
  unit: `Kilogram`, `Liter`, `Watt`, `ROF`...).
- Values containing a **comma** must be wrapped in quotes:
  `AllowPlacingAt: "Base,MS", display: true`. An unprotected comma breaks parsing.
- **Comments**: anything after a `#` on a line is ignored by the game.
- The **`+`** prefix before a block kind (`+Block`, `+Container`...) marks a **patch**
  that completes an existing definition of the same Id, rather than an independent new
  definition -- a common convention in large files edited over time.
- A syntax error (missing brace, unprotected comma, duplicate property) can prevent the
  entire file from loading, with a message in the game console (backtick key to open it)
  like "Ignored unknown parameter(s) in element...".

### Nested sub-blocks
An item can contain sub-blocks (e.g. `{ Mode Id: 0 ... }` for a weapon mode,
`{ Child Inputs ... }` for a recipe's ingredients). An item can have **several `Mode`**
entries to represent multiple firing modes (semi-auto/burst, etc.).

---

## 4. `Config.ecf` vs the dedicated files -- a common trap

Confirmed by numerous official discussion threads (this topic comes up very often):
**`Config.ecf` can ONLY override properties already present in
`Config_Example.ecf`** -- it isn't a universal override file. If you want to change a
property that doesn't exist in `Config_Example.ecf` (e.g. `AllowPlacingAt` for a given
block), you have to edit `BlocksConfig.ecf` (or the corresponding dedicated file)
directly, **not `Config.ecf`**. Trying to do so in `Config.ecf` produces a silent error
in-game ("Ignored unknown parameter(s)"), no crash, but no effect either.

Practical consequence: for most serious scenario mods, people edit the dedicated files
directly (`BlocksConfig.ecf`, `ItemsConfig.ecf`...) rather than `Config.ecf`.

---

## 5. The `.yaml` files (playfields)

Unlike `.ecf`, playfields use **real YAML** (indentation, `-` lists). Main file:
`playfield.yaml` (or `playfield_static.yaml` / `playfield_dynamic.yaml` depending on
type) in `Playfields/<PlayfieldName>/`.

### Adding a custom POI (based on the official "Customized POIs" guide)
1. Place the blueprint's `.epb` file in `Prefabs/`.
2. In the `playfield.yaml`, find the `POIs: ... Random:` section and add an entry:
```yaml
- GroupName: JunkT1
  CountMinMax: [4, 5]
  DroneProb: 0
  DronesMinMax: [0]
  ReserveCount: 0
  TroopTransport: False
  SpawnPOINear: [START]
  SpawnPOINearRange: [500, 1000]
  Properties:
    - Key: MapDistance
      Value: 600
    - Key: MapMarker
      Value: Neutral
    - Key: RegenAfter
      Value: 720
```
3. `GroupName` must match your blueprint's group name (a POI can only belong to **one**
   group).

**Important trap, confirmed by the official forum**: modifying a `playfield.yaml` only
affects **new games** (or playfields never visited in an existing save). A playfield
already generated in an ongoing save keeps its cached state -- changes to POIs on
planets/moons don't apply retroactively (unlike space playfields, which are more
flexible in this respect).

Lines marked "Please don't change" or "No functionality yet" in the file itself should
be avoided (info from the official wiki, "Customizing Solar Systems").

---

## 6. RandomPresets / Sectors -- galaxy generation

- `RandomPresets/*.yaml` (`SolarSystemConfig.yaml` files) control the procedural
  generation of solar systems.
- `Sectors/Sectors.yaml` defines the galaxy structure (which sectors, which starting
  planets).
- `gameoptions.yaml` / `gameoptions_example.yaml`: default game options offered when
  starting a new game with this scenario.

Common community convention for a "light" scenario (just modified configs, not an
entirely custom world): copy these files as-is from the base game's "Default Random"
scenario, and only modify `Content/Configuration`.

---

## 7. Dialogues, Tokens and Localization

- **`Dialogues.ecf`** defines NPC and interactive block dialogue trees (code doors,
  panels...). A block can trigger a dialogue via the `ExecuteOnActivate` property in
  `BlocksConfig.ecf`.
- **`TokenConfig.ecf`** defines lock codes (1 to 9999) usable on doors and containers,
  tied to the dialogue system.
- **`Localization.csv`** contains the translated texts used by dialogues and the UI --
  typical structure: a `Key` column, then one column per language (`English`, `Deutsch`,
  `Français`...).
- Dialogues support dynamic variables (`{PlayerName}`) and advanced functions
  (`Execute`/`ExecuteEditor`, in simplified C#) for custom quest mechanics.

---

## 8. General points of caution when merging/modifying a scenario

1. **Always work on a copy**, never on vanilla files or an online scenario (confirmed
   by every community guide consulted).
2. **Never change the Id or Name** of a block/item already referenced elsewhere
   (recipes, loot tables, playfields) -- it breaks references.
3. An **unprotected comma** in a list-style value (`AllowPlacingAt: Base,MS` instead of
   `"Base,MS"`) is the syntax error most frequently reported on forums.
4. Check the in-game console (backtick key) after loading to spot parsing errors -- the
   game often points precisely to which element is problematic.
5. A playfield already visited in a save won't reload its POI changes -- test on a
   **new game**.
6. An Id shared between two different definitions (for example when merging two
   independent scenarios) is a real, well-documented source of conflicts -- this is
   exactly what this tool's anti-collision safeguard is designed to detect (see the
   application wiki).

---

## Sources consulted

- Official Empyrion wiki (Fandom) -- pages "Guide/Customized POIs",
  "Guide/Customizing Solar Systems", "Scenarios"
- Steam Community, guide "Gentle guide to .ECF modding" (zaphodikus et al.)
- Steam Community, guide "Custom Scenarios for Dummies"
- Steam Workshop, "Scenario for Custom Config Mods"
- Official Empyrion forums (empyriononline.com) -- threads on Config.ecf,
  ItemsConfig.ecf, terrain.ecf
- Steam Community discussions on ECF parsing errors
- Documentation of the community tool eWCCT (Empyrion Web Config Creator Tool) for the
  dialogue/token system

```

### docs\wiki_empyrion_fr.md

```md
# Wiki Empyrion — structure des scenarios et proprietes ECF/YAML

Base sur la documentation communautaire (wiki officiel Empyrion sur Fandom, guides Steam,
forums officiels, outil eWCCT). Les informations les plus specifiques (valeurs exactes de
proprietes rares) meritent toujours une verification en jeu -- la documentation communautaire
evolue avec les mises a jour du jeu et n'est pas toujours a jour a 100%.

---

## 1. Structure d'un dossier de scenario

```
MonScenario/
├── Content/
│   └── Configuration/       <- Tous les fichiers .ecf de gameplay (voir section 2)
├── Playfields/               <- Un sous-dossier par playfield, avec son .yaml
├── Prefabs/                  <- Blueprints (.epb) des POI/vaisseaux customs
├── RandomPresets/             <- Fichiers SolarSystemConfig.yaml (generation procedurale)
├── Sectors/                  <- Sectors.yaml (structure de la galaxie)
├── Extras/                   <- Dialogues.csv, Localization.csv, autres CSV
├── SharedData/                <- Contenu partage entre plusieurs sous-scenarios/DLC
├── gameoptions.yaml            <- Options de partie par defaut
└── description.txt / Logos/   <- Metadonnees d'affichage du scenario
```

**Regle generale (confirmee par plusieurs guides communautaires)** : seuls les fichiers que tu
modifies reellement ont besoin d'etre presents dans le dossier de ton scenario -- tout fichier
absent est simplement herite du jeu de base (vanilla). C'est pour ca qu'un scenario "leger" ne
contient parfois que quelques fichiers dans `Content/Configuration`.

---

## 2. Les fichiers .ecf de `Content/Configuration`

| Fichier | Contenu |
|---|---|
| `BlocksConfig.ecf` | Tous les blocs constructibles (structure, hitpoints, materiau, categorie de placement...) |
| `ItemsConfig.ecf` | Tous les objets : armes, munitions, objets a main, consommables -- **y compris les items lies aux vehicules et bases** (ex: foreuses de vehicule), pas seulement les objets portes par le joueur |
| `Templates.ecf` | Recettes de craft (quels items produisent quel objet, avec quels ingredients) |
| `Containers.ecf` | Contenus par defaut des conteneurs (coffres, sacs...) |
| `LootGroups.ecf` | Groupes de loot utilises par les POI et conteneurs generes aleatoirement |
| `EClassConfig.ecf` | Classes d'entites (NPC, creatures) |
| `EGroupsConfig.ecf` | Groupes d'entites |
| `DefReputation.ecf` | Reputation par defaut envers les differentes factions |
| `FactionWarfare.ecf` | Regles de guerre entre factions |
| `MaterialConfig.ecf` | Proprietes des materiaux (resistance, etc.) |
| `StatusEffects.ecf` | Effets de statut (buffs/debuffs) |
| `TraderNPCConfig.ecf` | Configuration des marchands PNJ |
| `TokenConfig.ecf` | Jetons/codes de verrouillage utilises par les portes, coffres... (lies au systeme de dialogue) |
| `Dialogues.ecf` | Arbres de dialogue des PNJ |
| `Dialogues.csv` / `Localization.csv` | Textes localises utilises par les dialogues et l'interface |
| `GalaxyConfig.ecf` | Parametres globaux de generation de galaxie |
| `Config.ecf` (ou `Config_Example.ecf`) | Fichier de **surcharge** legere -- voir section 4, usage limite |

---

## 3. Syntaxe des fichiers .ecf

Format proprietaire d'Eleon, **pas du JSON ni du YAML** meme s'il y ressemble. Un bloc
("objet") s'ecrit entre accolades :

```
{ Block Id: 399, Name: ConcreteBlocks
  Material: concrete
  BlockColor: "170,170,170"
  Info: bkiBlockGroup, display: true
  IsOxygenTight: true, display: true
  HitPoints: 600, type: int, display: false
  Mass: 1100, type: float, display: true, formatter: Kilogram
  Volume: 10, type: float, display: true, formatter: Liter
  Category: BuildingBlocks
  ChildBlocks: "ConcreteFull, ConcreteThin, ConcreteExtended"
  UnlockCost: 0
  UnlockLevel: 1
}
```

Points cles (source : guide Steam "Gentle guide to .ECF modding", confirme par le forum
officiel) :

- **`Id`** identifie le bloc/item de facon unique dans le fichier. Certains blocs reels n'ont
  **pas d'Id du tout** et sont identifies seulement par `Name` -- convention plus rare mais
  bien reelle (ex: `{ Block Name: LegacyForcefield ...}`).
- **`Name`** est le nom interne (pas le nom affiche en jeu -- celui-la vient de la
  localisation). **Ne jamais changer l'Id ou le Name d'un bloc/item existant** : ca casse les
  references dans les autres fichiers et les sauvegardes existantes.
- **`Ref: AutreNom`** fait heriter un bloc/item des proprietes d'un autre (mecanisme
  d'heritage) -- tres utilise pour creer des variantes (ex: une arme "Epic" qui herite de
  l'arme de base et ne redefinit que les stats qui changent).
- Une propriete peut avoir des **sous-attributs** apres une virgule : `type` (int/float/string),
  `display` (true/false -- affiche ou non l'info-bulle en jeu), `formatter` (unite d'affichage :
  `Kilogram`, `Liter`, `Watt`, `ROF`...).
- Les valeurs contenant une **virgule** doivent etre entre guillemets :
  `AllowPlacingAt: "Base,MS", display: true`. Une virgule non protegee casse le parsing.
- **Commentaires** : tout ce qui suit un `#` sur une ligne est ignore par le jeu.
- Le prefixe **`+`** avant un genre de bloc (`+Block`, `+Container`...) signale un **patch**
  qui complete une definition existante du meme Id, plutot qu'une nouvelle definition
  independante -- convention frequente dans les gros fichiers modifies au fil du temps.
- Une erreur de syntaxe (accolade manquante, virgule non protegee, propriete dupliquee) peut
  empecher le fichier entier de charger, avec un message dans la console du jeu (touche
  antiquote pour l'ouvrir) du type "Ignored unknown parameter(s) in element...".

### Sous-blocs imbriques
Un item peut contenir des sous-blocs (ex: `{ Mode Id: 0 ... }` pour un mode d'arme,
`{ Child Inputs ... }` pour les ingredients d'une recette). Un item peut avoir **plusieurs
`Mode`** pour representer plusieurs modes de tir (semi-auto/rafale, etc.).

---

## 4. `Config.ecf` vs les fichiers dedies -- un piege frequent

Confirme par de nombreux fils de discussion officiels (le sujet revient tres souvent) :
**`Config.ecf` ne peut surcharger QUE les proprietes deja presentes dans
`Config_Example.ecf`** -- ce n'est pas un fichier de surcharge universel. Si tu veux modifier
une propriete qui n'existe pas dans `Config_Example.ecf` (ex: `AllowPlacingAt` pour un bloc
donne), il faut editer directement `BlocksConfig.ecf` (ou le fichier dedie correspondant),
**pas `Config.ecf`**. Tenter de le faire dans `Config.ecf` produit une erreur silencieuse en
jeu ("Ignored unknown parameter(s)"), sans planter, mais sans effet non plus.

Consequence pratique : pour la plupart des mods de scenario serieux, on modifie directement les
fichiers dedies (`BlocksConfig.ecf`, `ItemsConfig.ecf`...) plutot que `Config.ecf`.

---

## 5. Les fichiers `.yaml` (playfields)

Contrairement aux `.ecf`, les playfields utilisent un **vrai YAML** (indentation, listes `-`).
Fichier principal : `playfield.yaml` (ou `playfield_static.yaml` / `playfield_dynamic.yaml`
selon le type) dans `Playfields/<NomDuPlayfield>/`.

### Ajouter un POI custom (base sur le guide officiel "Customized POIs")
1. Placer le fichier `.epb` du blueprint dans `Prefabs/`.
2. Dans le `playfield.yaml`, chercher la section `POIs: ... Random:` et ajouter une entree :
```yaml
- GroupName: JunkT1
  CountMinMax: [4, 5]
  DroneProb: 0
  DronesMinMax: [0]
  ReserveCount: 0
  TroopTransport: False
  SpawnPOINear: [START]
  SpawnPOINearRange: [500, 1000]
  Properties:
    - Key: MapDistance
      Value: 600
    - Key: MapMarker
      Value: Neutral
    - Key: RegenAfter
      Value: 720
```
3. `GroupName` doit correspondre au nom de groupe de ton blueprint (un POI ne peut appartenir
   qu'a **un seul** groupe).

**Piege important, confirme par le forum officiel** : modifier un `playfield.yaml` n'affecte
**que les nouvelles parties** (ou les playfields jamais visites dans une sauvegarde existante).
Un playfield deja genere dans une sauvegarde en cours garde son etat en cache -- les
changements sur les POI de planetes/lunes ne s'appliquent pas retroactivement (contrairement
aux playfields spatiaux, plus flexibles a ce niveau).

Les lignes marquees "Please don't change" ou "No functionality yet" dans le fichier lui-meme
sont a eviter (info du wiki officiel, "Customizing Solar Systems").

---

## 6. RandomPresets / Sectors -- generation de la galaxie

- `RandomPresets/*.yaml` (fichiers `SolarSystemConfig.yaml`) controlent la generation
  procedurale des systemes solaires.
- `Sectors/Sectors.yaml` definit la structure de la galaxie (quels secteurs, quelles planetes
  de depart).
- `gameoptions.yaml` / `gameoptions_example.yaml` : options de partie par defaut proposees a
  la creation d'une nouvelle partie avec ce scenario.

Convention communautaire frequente pour un scenario "leger" (juste des configs modifiees, pas
un monde entierement custom) : copier ces fichiers depuis le scenario "Default Random" du jeu
de base tel quel, et ne modifier que `Content/Configuration`.

---

## 7. Dialogues, Tokens et Localisation

- **`Dialogues.ecf`** definit les arbres de dialogue des PNJ et des blocs interactifs (portes
  a code, panneaux...). Un bloc peut declencher un dialogue via la propriete
  `ExecuteOnActivate` dans `BlocksConfig.ecf`.
- **`TokenConfig.ecf`** definit les codes de verrouillage (1 a 9999) utilisables sur les portes
  et conteneurs, lies au systeme de dialogue.
- **`Localization.csv`** contient les textes traduits utilises par les dialogues et
  l'interface -- structure typique : une colonne `Key`, puis une colonne par langue
  (`English`, `Deutsch`, `Français`...).
- Les dialogues supportent des variables dynamiques (`{PlayerName}`) et des fonctions
  avancees (`Execute`/`ExecuteEditor`, en C# simplifie) pour des mecaniques de quete
  personnalisees.

---

## 8. Points de vigilance generaux pour la fusion/modification de scenario

1. **Toujours travailler sur une copie**, jamais sur les fichiers vanilla ou un scenario en
   ligne (confirme par tous les guides communautaires consultes).
2. **Ne jamais changer l'Id ou le Name** d'un bloc/item deja reference ailleurs (recettes,
   loot tables, playfields) -- ca casse les references.
3. Une **virgule non protegee** dans une valeur de liste (`AllowPlacingAt: Base,MS` au lieu de
   `"Base,MS"`) est l'erreur de syntaxe la plus frequemment signalee dans les forums.
4. Verifier la console en jeu (touche antiquote) apres chargement pour reperer les erreurs de
   parsing -- le jeu indique souvent precisement quel element pose probleme.
5. Un playfield deja visite dans une sauvegarde ne recharge pas ses changements de POI --
   tester sur une **nouvelle partie**.
6. Un Id partage entre deux definitions differentes (par exemple lors d'une fusion entre deux
   scenarios independants) est une source reelle et documentee de conflits -- c'est
   precisement ce que le garde-fou anti-collision de cet outil est concu pour detecter (voir
   le wiki de l'application).

---

## Sources consultees

- Wiki officiel Empyrion (Fandom) -- pages "Guide/Customized POIs", "Guide/Customizing Solar
  Systems", "Scenarios"
- Steam Community, guide "Gentle guide to .ECF modding" (zaphodikus et al.)
- Steam Community, guide "Custom Scenarios for Dummies"
- Steam Workshop, "Scenario for Custom Config Mods"
- Forums officiels Empyrion (empyriononline.com) -- fils sur Config.ecf, ItemsConfig.ecf,
  terrain.ecf
- Discussions Steam Community sur les erreurs de parsing ECF
- Documentation de l'outil communautaire eWCCT (Empyrion Web Config Creator Tool) pour le
  systeme de dialogue/tokens

```

### edit_ecf.py

```py
"""
Editeur ECF simple, en ligne de commande interactive.

UTILISATION :
    python edit_ecf.py fichier.ecf

Une fois lance, tape 'help' pour voir les commandes disponibles.

PRINCIPE DE SECURITE :
- Aucune modification n'est ecrite sur disque tant que tu ne tapes pas 'save'.
- Avant 'save', un apercu des changements (diff) est toujours affiche, et une
  confirmation est demandee.
- Le tout premier 'save' d'une session cree automatiquement une sauvegarde de
  l'original (fichier.ecf.bak) avant d'ecrire quoi que ce soit.
"""
import shutil
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "parser.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/parser.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file, parse_ecf_text
from core.ecf.model import EcfProperty
from core.ecf.diff import diff_documents, format_diff, summarize_diff


HELP_TEXT = """
Commandes disponibles :
  kinds                          Liste les genres de blocs presents (ex: +Container)
  list <genre>                   Liste les blocs de ce genre (ex: list +Container)
  show <genre> <id>               Affiche le detail d'un bloc (ex: show +Container 5)
  set <genre> <id> <cle> <valeur> Modifie une propriete du bloc (ex: set +Container 5 Count "9,9")
  diff                             Affiche les changements en attente (pas encore sauvegardes)
  save                              Sauvegarde sur disque (avec apercu + confirmation)
  help                              Affiche cette aide
  quit / exit                       Quitte (previent si des changements ne sont pas sauvegardes)

Note : cette version simple modifie uniquement les proprietes directes d'un bloc
(celles visibles dans 'show'). Pour modifier une ligne a l'interieur d'un sous-bloc
(ex: 'Name_0' dans 'Child Items' d'un Container), utilise l'API Python directement --
demande a Claude si besoin, c'est prevu pour une prochaine etape.
""".strip()


def print_block_detail(block):
    print(f"Genre : {block.kind}")
    if block.pairs:
        print("Propriete(s) d'en-tete :")
        for k, v in block.pairs:
            if k:
                print(f"  {k}: {v}")
    props = [c for c in block.children if isinstance(c, EcfProperty)]
    if props:
        print("Propriete(s) :")
        for p in props:
            for k, v in p.pairs:
                if k:
                    print(f"  {k}: {v}")
    sub_blocks = block.child_blocks()
    if sub_blocks:
        print("Sous-bloc(s) (lecture seule dans cette version) :")
        counts = {}
        for sb in sub_blocks:
            counts[sb.kind] = counts.get(sb.kind, 0) + 1
        for kind, n in counts.items():
            print(f"  {kind} ({n})")


def main():
    if len(sys.argv) != 2:
        print("Usage: python edit_ecf.py fichier.ecf")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERREUR : fichier introuvable : {path}")
        sys.exit(1)

    with open(path, 'r', encoding='utf-8', newline='') as f:
        original_raw = f.read()

    doc = parse_ecf_text(original_raw, source_path=str(path))
    backup_done = False
    has_unsaved_changes = False

    print(f"Fichier charge : {path}")
    print(f"({sum(1 for _ in doc.iter_blocks())} blocs au total, tous genres confondus)")
    print("Tape 'help' pour voir les commandes.")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split(maxsplit=4)
        cmd = parts[0].lower()

        if cmd in ('quit', 'exit'):
            if has_unsaved_changes:
                confirm = input("Des changements ne sont pas sauvegardes. Quitter quand meme ? (o/N) ")
                if confirm.lower() != 'o':
                    continue
            break

        elif cmd == 'help':
            print(HELP_TEXT)

        elif cmd == 'kinds':
            for kind, count in doc.top_level_kinds():
                print(f"  {kind} ({count})")

        elif cmd == 'list':
            if len(parts) < 2:
                print("Usage: list <genre>  (ex: list +Container)")
                continue
            kind = parts[1]
            blocks = list(doc.iter_blocks(kind))
            if not blocks:
                print(f"Aucun bloc de genre '{kind}' trouve. Tape 'kinds' pour voir les genres disponibles.")
                continue
            for b in blocks:
                from core.ecf.model import block_identity
                ident = block_identity(b) or "?"
                summary = b.summary_line()
                print(f"  [{ident}] {summary}")

        elif cmd == 'show':
            if len(parts) < 3:
                print("Usage: show <genre> <id>  (ex: show +Container 5)")
                continue
            kind, ident = parts[1], parts[2]
            block = doc.find_block_by_identity(kind, ident)
            if not block:
                print(f"Bloc '{kind}' avec identite '{ident}' introuvable.")
                continue
            print_block_detail(block)

        elif cmd == 'set':
            if len(parts) < 5:
                print('Usage: set <genre> <id> <cle> <valeur>  (ex: set +Container 5 Count "9,9")')
                continue
            kind, ident, key, value = parts[1], parts[2], parts[3], parts[4]
            block = doc.find_block_by_identity(kind, ident)
            if not block:
                print(f"Bloc '{kind}' avec identite '{ident}' introuvable.")
                continue
            old_value = block.get_property(key)
            if old_value is None:
                print(f"La propriete '{key}' n'existe pas sur ce bloc. "
                      f"Cette version ne cree pas de nouvelle propriete, seulement modifier une existante.")
                continue
            block.set_property(key, value)
            has_unsaved_changes = True
            print(f"OK : {key}: {old_value} -> {value}  (pas encore sauvegarde -- tape 'save' pour ecrire sur disque)")

        elif cmd == 'diff':
            original_doc = parse_ecf_text(original_raw)
            diffs = diff_documents(original_doc, doc)
            if not diffs:
                print("Aucun changement en attente.")
                continue
            resume = summarize_diff(diffs)
            print(f"Changements en attente : {resume['modified']} bloc(s) modifie(s)")
            print(format_diff(diffs))

        elif cmd == 'save':
            original_doc = parse_ecf_text(original_raw)
            diffs = diff_documents(original_doc, doc)
            if not diffs:
                print("Aucun changement a sauvegarder.")
                continue

            print("Apercu des changements qui vont etre ecrits sur disque :")
            print(format_diff(diffs))
            confirm = input(f"\nConfirmer l'ecriture dans {path} ? (o/N) ")
            if confirm.lower() != 'o':
                print("Annule.")
                continue

            if not backup_done:
                backup_path = path.with_suffix(path.suffix + '.bak')
                if not backup_path.exists():
                    shutil.copy2(path, backup_path)
                    print(f"Sauvegarde de l'original creee : {backup_path}")
                backup_done = True

            rendered = doc.render()
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(rendered)

            original_raw = rendered  # nouvelle base de reference pour les prochains diff
            has_unsaved_changes = False
            print(f"Sauvegarde effectuee : {path}")

        else:
            print(f"Commande inconnue : '{cmd}'. Tape 'help' pour la liste des commandes.")


if __name__ == "__main__":
    main()

```

### gui\__init__.py

```py

```

### gui\backup_dialog.py

```py
"""
Fenetre generique de sauvegarde/restauration, reutilisee pour deux besoins :
  - kind='scenario' : sauvegarder la version vanille d'un scenario avant une mise a
    jour Steam Workshop (qui ecrase le dossier en place), pour pouvoir la comparer
    plus tard a la nouvelle version.
  - kind='savegame' : sauvegarder/restaurer la progression de partie.

Accessible independamment de tout projet ouvert (Fichier > ...).
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QProgressDialog,
    QApplication,
)
from PyQt6.QtCore import Qt
import os
import subprocess
import sys

from core.i18n import t
from core import settings, backup_manager
from gui.theme import icon, icon_size


class BackupManagerDialog(QDialog):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind  # 'scenario' ou 'savegame'
        title_key = "backup.title_scenario" if kind == 'scenario' else "backup.title_savegame"
        self.setWindowTitle(t(title_key))
        self.resize(750, 600)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.edit_source = QLineEdit()
        btn_source = QPushButton(t("newproj.browse"))
        btn_source.clicked.connect(lambda: self._browse(self.edit_source))
        row_source = QHBoxLayout()
        row_source.addWidget(self.edit_source)
        row_source.addWidget(btn_source)
        source_label_key = "backup.source_scenario" if kind == 'scenario' else "backup.source_savegame"
        form.addRow(t(source_label_key), row_source)

        self.edit_storage = QLineEdit(settings.get_backup_root(kind))
        btn_storage = QPushButton(t("newproj.browse"))
        btn_storage.clicked.connect(lambda: self._browse(self.edit_storage, remember=True))
        row_storage = QHBoxLayout()
        row_storage.addWidget(self.edit_storage)
        row_storage.addWidget(btn_storage)
        form.addRow(t("backup.storage_folder"), row_storage)

        self.edit_label = QLineEdit()
        form.addRow(t("backup.label"), self.edit_label)
        layout.addLayout(form)

        btn_create = QPushButton(icon("fa5s.save", "#ffffff"), t("backup.create"))
        btn_create.setIconSize(icon_size())
        btn_create.clicked.connect(self._create_backup)
        layout.addWidget(btn_create)

        layout.addWidget(QLabel(t("backup.existing_list")))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        actions_row = QHBoxLayout()
        btn_restore = QPushButton(icon("fa5s.undo", "#4a7dfc"), t("backup.restore"))
        btn_restore.setIconSize(icon_size())
        btn_restore.setObjectName("secondaryButton")
        btn_restore.clicked.connect(self._restore_selected)
        actions_row.addWidget(btn_restore)

        if kind == 'scenario':
            btn_compare = QPushButton(icon("fa5s.balance-scale", "#4a7dfc"), t("backup.compare_with"))
            btn_compare.setIconSize(icon_size())
            btn_compare.setObjectName("secondaryButton")
            btn_compare.clicked.connect(self._compare_selected)
            actions_row.addWidget(btn_compare)

        btn_open = QPushButton(icon("fa5s.folder-open", "#4a7dfc"), t("backup.open_folder"))
        btn_open.setIconSize(icon_size())
        btn_open.setObjectName("secondaryButton")
        btn_open.clicked.connect(self._open_selected_folder)
        actions_row.addWidget(btn_open)

        btn_delete = QPushButton(icon("fa5s.trash-alt", "#ef4444"), t("backup.delete"))
        btn_delete.setIconSize(icon_size())
        btn_delete.setObjectName("secondaryButton")
        btn_delete.clicked.connect(self._delete_selected)
        actions_row.addWidget(btn_delete)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

        self._refresh_list()

    def _browse(self, target_edit: QLineEdit, remember: bool = False):
        folder = QFileDialog.getExistingDirectory(self, t("compare.choose_folder"))
        if folder:
            target_edit.setText(folder)
            if remember:
                settings.set_backup_root(self.kind, folder)

    def _current_backup_root(self) -> Optional[Path]:
        text = self.edit_storage.text().strip()
        return Path(text) if text else None

    def _refresh_list(self):
        self.list_widget.clear()
        root = self._current_backup_root()
        if not root or not root.exists():
            return
        records = backup_manager.list_backups(root, kind=self.kind)
        if not records:
            item = QListWidgetItem(t("backup.none_yet"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return
        for record in records:
            size = backup_manager.format_size(backup_manager.backup_size_bytes(record))
            item = QListWidgetItem(f"{record.display_name()}   ({size})")
            item.setData(Qt.ItemDataRole.UserRole, record)
            item.setToolTip(record.source_path)
            self.list_widget.addItem(item)

    def _selected_record(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _create_backup(self):
        source_text = self.edit_source.text().strip()
        storage_text = self.edit_storage.text().strip()
        if not source_text:
            QMessageBox.warning(self, t("err.missing_field"), t("backup.source_required"))
            return
        if not storage_text:
            QMessageBox.warning(self, t("err.missing_field"), t("backup.storage_required"))
            return

        source = Path(source_text)
        storage = Path(storage_text)
        settings.set_backup_root(self.kind, storage_text)

        progress = QProgressDialog(t("progress.please_wait"), None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            record = backup_manager.create_backup(source, storage, self.edit_label.text().strip() or None, self.kind)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("backup.error"), str(e))
            return
        progress.close()

        QMessageBox.information(self, t("backup.created_title"),
                                 t("backup.created_msg", path=record.backup_path))
        self.edit_label.clear()
        self._refresh_list()

    def _restore_selected(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return

        default_dest = record.source_path or ""
        dest_text, ok = self._ask_destination(default_dest)
        if not ok or not dest_text.strip():
            return
        destination = Path(dest_text.strip())

        confirm = QMessageBox.question(
            self, t("backup.confirm_restore"),
            f"{t('backup.restore_warning')}\n\n{destination}"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog(t("progress.please_wait"), None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            safety = backup_manager.restore_backup(
                record, destination, safety_backup_root=self._current_backup_root()
            )
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("backup.restore_error"), str(e))
            return
        progress.close()

        msg = t("backup.restore_done_msg", path=destination)
        if safety:
            msg += t("backup.restore_done_with_safety", label=safety.label)
        QMessageBox.information(self, t("backup.restore_done_title"), msg)
        self._refresh_list()

    def _ask_destination(self, default_text: str):
        from PyQt6.QtWidgets import QInputDialog
        return QInputDialog.getText(self, t("backup.restore_title"),
                                     t("backup.restore_destination"), text=default_text)

    def _delete_selected(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return
        confirm = QMessageBox.question(
            self, t("backup.confirm_delete_title"),
            t("backup.confirm_delete_msg", label=record.label)
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        backup_manager.delete_backup(record)
        self._refresh_list()

    def _open_selected_folder(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return
        path = record.backup_path
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def _compare_selected(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, t("err.missing_field"), t("backup.select_one"))
            return
        from gui.scenario_compare_dialog import ScenarioCompareDialog
        dialog = ScenarioCompareDialog(self)
        dialog.edit_a.setText(str(record.content_path()))
        dialog.exec()

```

### gui\csv_edit_widget.py

```py
"""
Widget d'edition CSV (tableau) pour la copie de travail, avec traduction par clic
droit (Google Translate via deep-translator) directement sur une cellule.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QMenu, QMessageBox, QDialog, QTextEdit, QLineEdit, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from core.csv_handler import CsvHandler, CsvDocument, render_csv
from core import translation
from core.i18n import t
from gui.theme import icon, icon_size
from gui.text_tools import (
    copy_selection, cut_selection, paste_into_selection, delete_selection, delete_selected_rows,
    install_clipboard_shortcuts, add_clipboard_menu_actions, open_bbcode_tool,
)

COLOR_MODIFIED_CELL = QBrush(QColor(255, 250, 200))


class TranslationResultDialog(QDialog):
    """Petite fenetre affichant le resultat d'une traduction, avec le choix de
    remplacer la cellule d'origine (ou une cellule destination precise) ou juste
    copier le resultat."""

    def __init__(self, original: str, translated: str, parent=None, destination_label: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle(t("trans.dialog_title"))
        self.setMinimumWidth(500)
        self.accepted_replace = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("trans.original_label")))
        orig_view = QTextEdit()
        orig_view.setPlainText(original)
        orig_view.setReadOnly(True)
        orig_view.setMaximumHeight(80)
        layout.addWidget(orig_view)

        layout.addWidget(QLabel(t("trans.translation_label")))
        self.translated_view = QTextEdit()
        self.translated_view.setPlainText(translated)
        layout.addWidget(self.translated_view)

        buttons = QHBoxLayout()
        replace_label = t("trans.place_in", destination=destination_label) if destination_label else t("trans.replace_cell")
        btn_replace = QPushButton(replace_label)
        btn_replace.clicked.connect(self._on_replace)
        buttons.addWidget(btn_replace)
        btn_close = QPushButton(t("trans.close_no_apply"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

    def _on_replace(self):
        self.accepted_replace = True
        self.accept()

    def result_text(self) -> str:
        return self.translated_view.toPlainText()


def show_translate_context_menu(parent_widget, global_pos, text: str, on_apply):
    """Affiche un menu contextuel 'Traduire vers...' (sous-menu de langues) a la
    position donnee. Si l'utilisateur choisit une langue et confirme le remplacement
    dans la fenetre de resultat, appelle on_apply(texte_traduit)."""
    if not text or not text.strip():
        return

    menu = QMenu(parent_widget)
    translate_menu = menu.addMenu(t("ctx.translate_to"))
    lang_actions = {}
    for label, code in translation.COMMON_LANGUAGES:
        action = translate_menu.addAction(label)
        lang_actions[action] = code

    chosen = menu.exec(global_pos)
    if chosen not in lang_actions:
        return

    if not translation.is_available():
        QMessageBox.warning(parent_widget, t("trans.unavailable_title"), t("trans.unavailable_msg"))
        return

    target_lang = lang_actions[chosen]
    try:
        translated = translation.translate_text(text, target=target_lang)
    except Exception as e:
        QMessageBox.critical(parent_widget, t("trans.error_title"), t("trans.error_msg", error=e))
        return

    dialog = TranslationResultDialog(text, translated, parent_widget)
    if dialog.exec() == QDialog.DialogCode.Accepted and dialog.accepted_replace:
        on_apply(dialog.result_text())


class CsvEditWidget(QWidget):
    """Editeur/visualiseur de fichier .csv : tableau editable si `editable=True` (copie
    de travail), ou lecture seule sinon (Scenario A/B). La traduction par clic droit
    reste disponible dans les deux cas. En lecture seule, si `on_copy_row` est fourni,
    un clic droit propose de copier la ligne (par cle) vers la copie de travail."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, editable: bool = True, on_copy_row=None, copy_label: Optional[str] = None,
                 on_translate_cell=None, on_duplicate_row=None):
        super().__init__()
        self.path = path
        self.editable = editable
        self.on_copy_row = on_copy_row
        self.copy_label = copy_label
        self.on_translate_cell = on_translate_cell
        self.on_duplicate_row = on_duplicate_row
        self._modified = False
        self._undo_stack: list = []
        self._undo_max = 20
        self._pre_edit_snapshot = None  # capture avant edition en double-clic
        self._search_matches = []
        self._search_index = -1
        self._search_last_scope_key = None

        handler = CsvHandler()
        raw = handler.load(path)
        self.doc: CsvDocument = handler.parse(raw)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        mode_text = t("status.editable") if editable else t("status.readonly")
        info_label = QLabel(f"{path.name}  ({mode_text}) -- "
                             f"{len(self.doc.rows)} ligne(s), delimiteur '{self.doc.delimiter}'")
        info_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(info_label, 0)

        n_cols = len(self.doc.header) if self.doc.header else (len(self.doc.rows[0]) if self.doc.rows else 1)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(t("csv.search_placeholder"))
        self.search_box.addAction(icon("fa5s.search", color="#7c859c"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(QLabel(t("csv.search_scope_label")))
        self.search_scope = QComboBox()
        self.search_scope.addItem(t("search.column_all"), None)
        header_labels = self.doc.header or [str(i) for i in range(n_cols)]
        for col_index, col_name in enumerate(header_labels):
            self.search_scope.addItem(col_name, col_index)
        search_row.addWidget(self.search_scope)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        layout.addLayout(search_row, 0)

        if editable:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_add_row = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_row"))
            btn_add_row.setIconSize(icon_size())
            btn_add_row.clicked.connect(self._add_row)
            toolbar.addWidget(btn_add_row)
            btn_del_row = QPushButton(icon("fa5s.trash-alt", "#4a7dfc"), t("btn.delete_selected_row"))
            btn_del_row.setIconSize(icon_size())
            btn_del_row.setObjectName("secondaryButton")
            btn_del_row.clicked.connect(self._delete_selected_row)
            toolbar.addWidget(btn_del_row)
            self.btn_undo = QPushButton(icon("fa5s.undo", "#7c859c"), t("btn.undo"))
            self.btn_undo.setIconSize(icon_size())
            self.btn_undo.setObjectName("secondaryButton")
            self.btn_undo.clicked.connect(self.undo)
            self.btn_undo.setEnabled(False)
            toolbar.addWidget(self.btn_undo)
            btn_save = QPushButton(icon("fa5s.save", "#ffffff"), t("btn.save"))
            btn_save.setIconSize(icon_size())
            btn_save.clicked.connect(self.save)
            toolbar.addWidget(btn_save)
            toolbar.addStretch()
            layout.addLayout(toolbar, 0)

        self.table = QTableWidget(len(self.doc.rows), n_cols)
        if self.doc.header:
            self.table.setHorizontalHeaderLabels(self.doc.header)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._show_header_context_menu)
        self._populate_table()
        if not editable:
            from PyQt6.QtWidgets import QAbstractItemView
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        if editable:
            self.table.setSelectionMode(self.table.SelectionMode.ContiguousSelection)
            self.table.itemDoubleClicked.connect(lambda item: self._snapshot_undo())
            from PyQt6.QtGui import QKeySequence, QShortcut
            QShortcut(QKeySequence.StandardKey.Copy, self.table,
                      activated=lambda: copy_selection(self.table))
            QShortcut(QKeySequence.StandardKey.Cut, self.table,
                      activated=self._do_cut)
            QShortcut(QKeySequence.StandardKey.Paste, self.table,
                      activated=self._do_paste)
            QShortcut(QKeySequence(Qt.Key.Key_Delete), self.table,
                      activated=self._do_delete_content)
            QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)
        layout.addWidget(self.table, 1)

    def _populate_table(self):
        self.table.blockSignals(True)
        for r, row in enumerate(self.doc.rows):
            for c in range(self.table.columnCount()):
                val = row[c] if c < len(row) else ""
                self.table.setItem(r, c, QTableWidgetItem(val))
        self.table.blockSignals(False)

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def _show_header_context_menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        if col < 0:
            return
        col_name = self.doc.header[col] if self.doc.header and col < len(self.doc.header) else str(col)
        menu = QMenu(self)
        action_search = menu.addAction(t("search.in_column_action", name=col_name))
        chosen = menu.exec(self.table.horizontalHeader().viewport().mapToGlobal(pos))
        if chosen == action_search:
            idx = self.search_scope.findData(col)
            if idx >= 0:
                self.search_scope.setCurrentIndex(idx)
            self._search_matches = []  # force un recalcul avec la nouvelle portee
            self.search_box.setFocus()
            self.search_box.selectAll()

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            self.search_status.setText("")
            return

        scope_col = self.search_scope.currentData()  # None = toutes les colonnes
        scope_key = (query, scope_col)

        if not self._search_matches or self._search_last_scope_key != scope_key:
            self._search_matches = []
            n_rows = self.table.rowCount()
            cols = [scope_col] if scope_col is not None else list(range(self.table.columnCount()))
            for r in range(n_rows):
                for c in cols:
                    item = self.table.item(r, c)
                    if item and query in item.text().lower():
                        self._search_matches.append((r, c))
            self._search_index = -1
            self._search_last_scope_key = scope_key

        if not self._search_matches:
            self.search_status.setText(t("search.no_results"))
            return

        self._search_index = (self._search_index + 1) % len(self._search_matches)
        r, c = self._search_matches[self._search_index]
        self.table.setCurrentCell(r, c)
        self.table.scrollToItem(self.table.item(r, c))
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def save(self):
        if not self.editable:
            return
        self._sync_doc_from_table()
        rendered = render_csv(self.doc)
        try:
            from core.fsutil import clear_readonly
            clear_readonly(self.path)
            with open(self.path, 'w', encoding='utf-8', newline='') as f:
                f.write(rendered)
        except OSError as e:
            QMessageBox.critical(self, t("save.error_title"),
                                  t("save.error_msg", name=self.path.name, error=str(e)))
            return
        self._set_modified(False)
        self.saved.emit()

    def _snapshot_table(self) -> list:
        return [[self.table.item(r, c).text() if self.table.item(r, c) else ""
                 for c in range(self.table.columnCount())]
                for r in range(self.table.rowCount())]

    def _snapshot_undo(self):
        """A appeler AVANT toute modification (edition, coller, ajout/suppression de
        ligne...) -- capture le tableau tel qu'il est maintenant, pour pouvoir y revenir."""
        self._undo_stack.append(self._snapshot_table())
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self.btn_undo.setEnabled(True)

    def undo(self):
        if not self._undo_stack:
            return
        snapshot = self._undo_stack.pop()
        self.table.blockSignals(True)
        self.table.setRowCount(len(snapshot))
        for r, row_vals in enumerate(snapshot):
            for c, val in enumerate(row_vals):
                item = self.table.item(r, c)
                if item is None:
                    item = QTableWidgetItem("")
                    self.table.setItem(r, c, item)
                item.setText(val)
        self.table.blockSignals(False)
        self._set_modified(True)
        if not self._undo_stack:
            self.btn_undo.setEnabled(False)

    def _do_cut(self):
        self._snapshot_undo()
        cut_selection(self.table)

    def _do_paste(self):
        self._snapshot_undo()
        paste_into_selection(self.table, allow_new_rows=True)

    def _do_delete_content(self):
        self._snapshot_undo()
        delete_selection(self.table)

    def _do_delete_rows(self):
        self._snapshot_undo()
        delete_selected_rows(self.table)
        self._set_modified(True)

    def _sync_doc_from_table(self):
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row.append(item.text() if item else "")
            rows.append(row)
        self.doc.rows = rows

    def _on_cell_changed(self, item: QTableWidgetItem):
        item.setBackground(COLOR_MODIFIED_CELL)
        self._set_modified(True)

    def _add_row(self):
        self._snapshot_undo()
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem(""))
        self._set_modified(True)

    def _delete_selected_row(self):
        r = self.table.currentRow()
        if r < 0:
            return
        self._snapshot_undo()
        self.table.removeRow(r)
        self._set_modified(True)

    def _find_language_column(self, target_code: str, target_label: str) -> Optional[int]:
        """Trouve la colonne dont l'en-tete correspond a la langue cible -- via une
        liste d'alias (code ISO, nom anglais, nom natif, libelle du menu), comparaison
        insensible aux accents et a la casse (voir core.translation.find_language_aliases)."""
        aliases = translation.find_language_aliases(target_code, target_label)
        for c in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(c)
            if not header_item:
                continue
            if translation._normalize(header_item.text().strip()) in aliases:
                return c
        return None

    def _show_context_menu(self, pos):
        if not self.editable:
            # Vue lecture seule (Scenario A/B) : copier la ligne entiere, ET/OU
            # traduire directement cette cellule vers la colonne de la langue
            # choisie dans la copie de travail (meme ligne, cle identique).
            item = self.table.itemAt(pos)
            if not item:
                return
            row_idx = item.row()
            row_values = [self.table.item(row_idx, c).text() if self.table.item(row_idx, c) else ""
                          for c in range(self.table.columnCount())]
            key = row_values[0] if row_values else "?"
            text = item.text()

            menu = QMenu(self)
            action_copy = None
            if self.on_copy_row:
                action_copy = menu.addAction(t("csv.copy_row_action", key=key))
            action_dup = None
            if self.on_duplicate_row:
                action_dup = menu.addAction(t("csv.duplicate_row_action"))

            lang_actions = {}
            if self.on_translate_cell and text.strip():
                translate_menu = menu.addMenu(t("ctx.translate_cell_to"))
                for label, code in translation.COMMON_LANGUAGES:
                    a = translate_menu.addAction(label)
                    lang_actions[a] = (code, label)

            if not action_copy and not action_dup and not lang_actions:
                return

            chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
            if action_copy and chosen == action_copy:
                self.on_copy_row(row_values)
            elif action_dup and chosen == action_dup:
                self.on_duplicate_row(row_values)
            elif chosen in lang_actions:
                target_code, target_label = lang_actions[chosen]
                self.on_translate_cell(key, text, target_code, target_label)
            return

        item = self.table.itemAt(pos)
        if item is None:
            item = self.table.currentItem()

        menu = QMenu(self)
        menu.addAction(t("ctx.copy"), lambda: copy_selection(self.table))
        menu.addAction(t("ctx.cut"), self._do_cut)
        menu.addAction(t("ctx.paste"), self._do_paste)
        menu.addAction(t("ctx.clear_content"), self._do_delete_content)
        action_del_row = menu.addAction(t("ctx.delete_rows"))
        menu.addSeparator()

        text = item.text() if item else ""
        translate_menu = None
        lang_actions = {}
        action_bbcode = None
        if item and text.strip():
            translate_menu = menu.addMenu(t("ctx.translate_to"))
            for label, code in translation.COMMON_LANGUAGES:
                a = translate_menu.addAction(label)
                lang_actions[a] = (code, label)
            action_bbcode = menu.addAction(t("ctx.bbcode"))

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))

        if chosen == action_del_row:
            self._do_delete_rows()
            return

        if item is None:
            return
        row = item.row()

        if action_bbcode is not None and chosen == action_bbcode:
            new_text = open_bbcode_tool(self, text)
            if new_text is not None:
                self._snapshot_undo()
                item.setText(new_text)
            return

        if chosen not in lang_actions:
            return
        target_code, target_label = lang_actions[chosen]

        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(text, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        target_col = self._find_language_column(target_code, target_label)
        dest_label = None
        if target_col is not None and target_col != item.column():
            header = self.table.horizontalHeaderItem(target_col)
            dest_label = f"la colonne '{header.text() if header else target_label}' (meme ligne)"

        dialog = TranslationResultDialog(text, translated, self, destination_label=dest_label)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.accepted_replace:
            return
        result_text = dialog.result_text()

        self._snapshot_undo()
        if target_col is not None and target_col != item.column():
            dest_item = self.table.item(row, target_col)
            if dest_item is None:
                dest_item = QTableWidgetItem("")
                self.table.setItem(row, target_col, dest_item)
            dest_item.setText(result_text)
        else:
            # Pas de colonne correspondant a cette langue trouvee dans l'en-tete ->
            # on remplace la cellule d'origine par defaut, comme avant.
            item.setText(result_text)

```

### gui\ecf_edit_widget.py

```py
"""
Widget d'edition pour un fichier .ecf de la COPIE DE TRAVAIL : contrairement a
EcfViewWidget (lecture seule, dans main_window.py), celui-ci permet de modifier une
valeur, ajouter/supprimer une propriete, ajouter/supprimer un bloc -- avec annotation
automatique de tracabilite sur chaque modification.

Contient aussi CompareWidget : une vue cote a cote (copie de travail modifiable a
gauche, source(s) A/B en lecture seule a droite, dans des onglets si les deux sont
disponibles) pour editer en gardant la reference sous les yeux, sans perdre d'espace
d'affichage a switcher entre onglets separes.
"""
from pathlib import Path
from typing import Dict, List, Optional
import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QSplitter, QLabel, QLineEdit, QPushButton, QMenu, QMessageBox,
    QInputDialog, QTabWidget, QDialog, QListWidget, QListWidgetItem, QTextEdit, QSizePolicy,
    QApplication, QComboBox, QFormLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QColor, QBrush

from core.ecf.parser import parse_ecf_file, parse_ecf_text
from core.ecf.model import (
    EcfDocument, EcfBlock, EcfProperty, block_identity, normalized_kind,
    add_property_line, remove_property_line, remove_block, create_block, annotate_property,
    add_repeating_item_row,
)
from core.ecf.pending_conflicts import suggest_free_ids
from core import settings
from core.i18n import t
from gui.theme import icon, icon_size, PRIMARY_DARK
from gui.csv_edit_widget import TranslationResultDialog
from gui.text_tools import add_clipboard_menu_actions, install_clipboard_shortcuts, open_bbcode_tool

COLOR_MODIFIED_ROW = QBrush(QColor(255, 250, 200))  # jaune clair : ligne modifiee dans cette session


class DisabledBlocksDialog(QDialog):
    """Liste les blocs desactives (commentes) manuellement dans le fichier ouvert,
    avec un bouton pour les reactiver un par un -- utile pour tester l'elimination
    de causes probables d'un bug de lancement sans avoir a editer le fichier a la
    main."""

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.reactivated = False
        self.setWindowTitle(t("ecf.disabled_blocks_title"))
        self.resize(500, 400)

        layout = QVBoxLayout(self)
        intro = QLabel(t("ecf.disabled_blocks_intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_reactivate = QPushButton(icon("fa5s.undo", "#ffffff"), t("ecf.reactivate_block"))
        self.btn_reactivate.setIconSize(icon_size())
        self.btn_reactivate.clicked.connect(self._reactivate_selected)
        btn_row.addWidget(self.btn_reactivate)
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._refresh_list()

    def _refresh_list(self):
        from core.ecf.disable_block import find_disabled_blocks
        self.list_widget.clear()
        self.entries = find_disabled_blocks(self.doc)
        if not self.entries:
            item = QListWidgetItem(t("ecf.disabled_blocks_none"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.btn_reactivate.setEnabled(False)
            return
        self.btn_reactivate.setEnabled(True)
        for entry in self.entries:
            self.list_widget.addItem(entry.label)

    def _reactivate_selected(self):
        from core.ecf.disable_block import enable_disabled_block
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        if enable_disabled_block(self.doc, entry):
            self.reactivated = True
            self._refresh_list()


class PendingConflictsDialog(QDialog):
    """Fenetre de revue des blocs en attente : liste a gauche, comparaison detaillee
    (bloc actuel vs bloc en attente, via le moteur de diff) a droite, avec suggestion
    d'Id libres pour l'activation."""

    def __init__(self, entries: List[dict], used_ids: set, parent=None):
        """entries : liste de dict {path, conflict, pending_block, base_block}."""
        super().__init__(parent)
        self.setWindowTitle(t("pending.title"))
        self.setMinimumSize(900, 600)
        self.entries = entries
        self.used_ids = used_ids
        self.chosen_new_id: Optional[str] = None
        self.chosen_entry: Optional[dict] = None

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list_widget = QListWidget()
        for e in entries:
            ident = block_identity(e['pending_block']) if e['pending_block'] else "?"
            name = e['pending_block'].get_property('Name') if e['pending_block'] else "?"
            self.list_widget.addItem(f"{e['path'].name} -- Id {ident} ({name})")
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.list_widget)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        right_layout.addWidget(QLabel(t("pending.compare_label")))
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFontFamily("Consolas, monospace")
        right_layout.addWidget(self.diff_view)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel(t("pending.new_id_label")))
        self.id_edit = QLineEdit()
        id_row.addWidget(self.id_edit)
        right_layout.addLayout(id_row)

        self.suggestions_label = QLabel("")
        self.suggestions_label.setWordWrap(True)
        right_layout.addWidget(self.suggestions_label)

        splitter.addWidget(right)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter)

        buttons = QHBoxLayout()
        btn_activate = QPushButton(t("pending.activate"))
        btn_activate.clicked.connect(self._on_activate)
        buttons.addWidget(btn_activate)
        btn_cancel = QPushButton(t("btn.close"))
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        if entries:
            self.list_widget.setCurrentRow(0)

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        pending = entry['pending_block']
        base = entry['base_block']

        lines = []
        if base is None:
            lines.append(t("pending.no_base_block"))
            lines.append("")
            lines.append(pending.render() if pending else t("pending.read_error"))
        else:
            from core.ecf.diff import diff_documents, format_diff
            from core.ecf.model import EcfDocument
            doc_a = EcfDocument(nodes=[base])
            doc_b = EcfDocument(nodes=[pending])
            diffs = diff_documents(doc_a, doc_b)
            if diffs:
                lines.append(t("pending.differences_header"))
                lines.append("")
                lines.append(format_diff(diffs))
            else:
                lines.append(t("pending.no_diff"))
            lines.append("")
            lines.append(t("pending.active_block_header"))
            lines.append(base.render())
            lines.append("")
            lines.append(t("pending.pending_block_header"))
            lines.append(pending.render())

        self.diff_view.setPlainText("\n".join(lines))

        suggestions = suggest_free_ids(self.used_ids, 8)
        self.suggestions_label.setText(
            t("pending.suggestions_label", ids=", ".join(str(s) for s in suggestions))
        )
        self.id_edit.setText(str(suggestions[0]))

    def _on_activate(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        new_id = self.id_edit.text().strip()
        if not new_id:
            QMessageBox.warning(self, t("pending.id_missing"), t("pending.id_missing_msg"))
            return
        if new_id.isdigit() and int(new_id) in self.used_ids:
            confirm = QMessageBox.question(
                self, t("pending.id_already_used"),
                t("pending.id_already_used_confirm", id=new_id)
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self.chosen_entry = self.entries[row]
        self.chosen_new_id = new_id
        self.accept()


def _block_own_keys(block: EcfBlock) -> set:
    """Cles de proprietes DIRECTES d'un bloc (en-tete + lignes enfants directes, sans
    descendre dans les sous-blocs comme 'Child Items')."""
    keys = set()
    for k, v in block.pairs:
        if k:
            keys.add(k)
    for child in block.children:
        if isinstance(child, EcfProperty):
            for k, v in child.pairs:
                if k:
                    keys.add(k)
    return keys


class PropertyFilterDialog(QDialog):
    """Liste toutes les proprietes existantes dans un fichier (blocs de premier niveau)
    a cocher ; le filtre s'applique EN DIRECT sur l'arbre principal du fichier ouvert
    (masque les blocs qui n'ont pas toutes les proprietes cochees), via le callback
    `on_filter_changed`. Reste actif meme apres fermeture de cette fenetre."""

    def __init__(self, doc: EcfDocument, on_filter_changed, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("propfilter.title"))
        self.setMinimumSize(400, 500)
        self.on_filter_changed = on_filter_changed

        top_blocks = [n for n in doc.nodes if isinstance(n, EcfBlock)]
        key_counts: Dict[str, int] = {}
        for b in top_blocks:
            for k in _block_own_keys(b):
                key_counts[k] = key_counts.get(k, 0) + 1

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("propfilter.instructions")))

        self.prop_list = QListWidget()
        for key in sorted(key_counts.keys()):
            item = QListWidgetItem(f"{key}  ({key_counts[key]})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.prop_list.addItem(item)
        self.prop_list.itemChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.prop_list)

        buttons = QHBoxLayout()
        btn_clear = QPushButton(t("propfilter.clear_all"))
        btn_clear.clicked.connect(self._clear_all)
        buttons.addWidget(btn_clear)
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

    def _checked_keys(self) -> List[str]:
        keys = []
        for i in range(self.prop_list.count()):
            item = self.prop_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                keys.append(item.data(Qt.ItemDataRole.UserRole))
        return keys

    def _on_checkbox_changed(self, _item):
        self.on_filter_changed(self._checked_keys())

    def _clear_all(self):
        self.prop_list.blockSignals(True)
        for i in range(self.prop_list.count()):
            self.prop_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.prop_list.blockSignals(False)
        self.on_filter_changed([])


class EcfHeaderExplanationPanel(QWidget):
    """Panneau retractable (replie par defaut) affichant une explication claire des
    commentaires techniques d'en-tete d'un fichier ECF -- place entre le nom du fichier
    et la barre de recherche. Pour les fichiers ayant un glossaire dedie (voir
    core/ecf_header_glossary.py -- GLOSSARY_BY_FILE), affiche une explication francaise
    clarifiee faite main ; pour les autres, montre le texte original brut avec un
    bouton de traduction automatique a la demande (reutilise le meme moteur de
    traduction que l'onglet CSV)."""

    def __init__(self, doc: EcfDocument, filename: str, parent=None):
        super().__init__(parent)
        from core.ecf_header_glossary import GLOSSARY_BY_FILE
        self._header_text = doc.extract_header_comment()
        self._glossary = GLOSSARY_BY_FILE.get(filename)
        self._has_glossary = self._glossary is not None
        self._showing_raw = False
        self._translated_cache: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        if not self._header_text:
            self.setVisible(False)
            return

        self.toggle_btn = QPushButton(icon("fa5s.info-circle", "#4a7dfc"), t("ecf.header_toggle_show"))
        self.toggle_btn.setObjectName("secondaryButton")
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setVisible(False)
        self.content.setMaximumHeight(220)
        layout.addWidget(self.content)

        btn_row = QHBoxLayout()
        self.btn_raw_toggle = QPushButton(t("ecf.header_raw_toggle"))
        self.btn_raw_toggle.setObjectName("secondaryButton")
        self.btn_raw_toggle.setVisible(False)
        self.btn_raw_toggle.clicked.connect(self._toggle_raw)
        btn_row.addWidget(self.btn_raw_toggle)

        self.btn_translate = QPushButton(icon("fa5s.language", "#4a7dfc"), t("ecf.header_translate_btn"))
        self.btn_translate.setObjectName("secondaryButton")
        self.btn_translate.setVisible(False)
        self.btn_translate.clicked.connect(self._translate)
        btn_row.addWidget(self.btn_translate)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _toggle(self):
        expanded = not self.content.isVisible()
        self.content.setVisible(expanded)
        self.toggle_btn.setText(t("ecf.header_toggle_hide") if expanded else t("ecf.header_toggle_show"))
        self.btn_raw_toggle.setVisible(expanded and self._has_glossary)
        self.btn_translate.setVisible(expanded and not self._has_glossary)
        if expanded:
            self._render_content()

    def _render_content(self):
        if self._has_glossary and not self._showing_raw:
            self._render_glossary()
        elif self._translated_cache:
            self.content.setPlainText(self._translated_cache)
        else:
            self.content.setPlainText(self._header_text)

    def _render_glossary(self):
        parts = [f"<p><i>{t('ecf.header_glossary_intro')}</i></p>"]
        for section_title, entries in self._glossary:
            parts.append(f"<p style='margin-top:8px'><b>{section_title}</b></p><ul style='margin-top:0'>")
            for term, explanation in entries:
                parts.append(f"<li><b>{term}</b> : {explanation}</li>")
            parts.append("</ul>")
        self.content.setHtml("".join(parts))

    def _toggle_raw(self):
        self._showing_raw = not self._showing_raw
        self.btn_raw_toggle.setText(
            t("ecf.header_toggle_show") if self._showing_raw else t("ecf.header_raw_toggle"))
        self._render_content()

    def _translate(self):
        from core import translation
        if not translation.is_available():
            QMessageBox.warning(self, t("err.title"), "deep-translator n'est pas installe.")
            return
        self.content.setPlainText(t("ecf.header_translating"))
        QApplication.processEvents()
        try:
            self._translated_cache = translation.translate_text(self._header_text, target="fr")
        except Exception as e:
            QMessageBox.warning(self, t("err.title"), t("ecf.header_translate_error", error=str(e)))
            self.content.setPlainText(self._header_text)
            return
        self.content.setPlainText(self._translated_cache)


class AddTableRowDialog(QDialog):
    """Formulaire d'ajout d'une ligne au mode tableau (Child Items, Child Inputs...) :
    un champ par colonne detectee, plus le choix Name/Group -- la numerotation (Name_6,
    Group_2...) est calculee automatiquement par l'appli, jamais saisie a la main."""

    def __init__(self, param_columns: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("ecf.add_row_title"))
        self.param_columns = param_columns

        layout = QFormLayout(self)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Name", "Group"])
        layout.addRow(t("ecf.add_row_type_label"), self.type_combo)

        self.value_edit = QLineEdit()
        layout.addRow(t("ecf.add_row_value_label"), self.value_edit)

        self.param_edits: Dict[str, QLineEdit] = {}
        for col in param_columns:
            edit = QLineEdit()
            self.param_edits[col] = edit
            layout.addRow(f"{col} :", edit)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(t("ecf.add_row_title"))
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

        self.result_type = None
        self.result_value = None
        self.result_extra_pairs: List[tuple] = []

    def _on_accept(self):
        if not self.value_edit.text().strip():
            QMessageBox.warning(self, t("err.missing_field"), t("ecf.add_row_value_required"))
            return
        self.result_type = self.type_combo.currentText()
        self.result_value = self.value_edit.text().strip()
        self.result_extra_pairs = [
            (col, edit.text().strip()) for col, edit in self.param_edits.items() if edit.text().strip()
        ]
        self.accept()


class EcfEditWidget(QWidget):
    """Editeur d'un fichier .ecf de la copie de travail. Emet `modified_changed(bool)`
    quand l'etat 'modifications non enregistrees' change, pour que le conteneur (onglet)
    puisse afficher un indicateur."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.doc: EcfDocument = parse_ecf_file(path)
        self._modified = False
        self._current_block: Optional[EcfBlock] = None
        self._table_mode = False
        self._edited_prop_nodes = set()  # ids Python des EcfProperty touches cette session
        self._undo_stack: list = []  # textes serialises (fidelite deja prouvee par le parser)
        self._undo_max = 20

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        filename_label = QLabel(f"{path.name}  ({t('status.editable')})")
        filename_label.setStyleSheet("font-size: 11px; color: gray; padding: 0px;")
        filename_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(filename_label, 0)

        self.header_panel = EcfHeaderExplanationPanel(self.doc, path.name)
        layout.addWidget(self.header_panel, 0)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Id / Name / CustomIcon...")
        self.search_box.addAction(icon("fa5s.search", color="#7c859c"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        layout.addLayout(search_row, 0)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        btn_add_block = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_block"))
        btn_add_block.setIconSize(icon_size())
        btn_add_block.clicked.connect(self._add_block_dialog)
        toolbar.addWidget(btn_add_block)
        self.btn_add_prop = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_property"))
        self.btn_add_prop.setIconSize(icon_size())
        self.btn_add_prop.clicked.connect(self._add_property_dialog)
        toolbar.addWidget(self.btn_add_prop)
        self.btn_add_row = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_row_table"))
        self.btn_add_row.setIconSize(icon_size())
        self.btn_add_row.clicked.connect(self._add_table_row_dialog)
        self.btn_add_row.setVisible(False)
        toolbar.addWidget(self.btn_add_row)
        btn_filter = QPushButton(icon("fa5s.filter", "#4a7dfc"), t("btn.filter_by_property"))
        btn_filter.setIconSize(icon_size())
        btn_filter.setObjectName("secondaryButton")
        btn_filter.clicked.connect(self._open_property_filter)
        toolbar.addWidget(btn_filter)
        btn_disabled_blocks = QPushButton(icon("fa5s.ban", "#4a7dfc"), t("ecf.disabled_blocks_menu"))
        btn_disabled_blocks.setIconSize(icon_size())
        btn_disabled_blocks.setObjectName("secondaryButton")
        btn_disabled_blocks.clicked.connect(self._open_disabled_blocks_dialog)
        toolbar.addWidget(btn_disabled_blocks)
        self.btn_undo = QPushButton(icon("fa5s.undo", "#7c859c"), t("btn.undo"))
        self.btn_undo.setIconSize(icon_size())
        self.btn_undo.setObjectName("secondaryButton")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_undo.setEnabled(False)
        toolbar.addWidget(self.btn_undo)
        btn_save = QPushButton(icon("fa5s.save", "#ffffff"), t("btn.save"))
        btn_save.setIconSize(icon_size())
        btn_save.clicked.connect(self.save)
        toolbar.addWidget(btn_save)
        toolbar.addStretch()
        layout.addLayout(toolbar, 0)

        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Bloc"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_block_selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        splitter.addWidget(self.tree)

        self.props_table = QTableWidget(0, 2)
        self.props_table.setHorizontalHeaderLabels(["Propriete", "Valeur"])
        self.props_table.horizontalHeader().setStretchLastSection(True)
        self.props_table.itemChanged.connect(self._on_cell_changed)
        self.props_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.props_table.customContextMenuRequested.connect(self._show_table_context_menu)
        install_clipboard_shortcuts(self.props_table, allow_new_rows=False)
        splitter.addWidget(self.props_table)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter, 1)

        self._search_matches: list = []
        self._search_index = -1
        self._search_last_query = ""

    # ------------------------------------------------------------------
    # Etat modifie / enregistrement
    # ------------------------------------------------------------------

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        try:
            from core.fsutil import clear_readonly
            clear_readonly(self.path)
            with open(self.path, 'w', encoding='utf-8', newline='') as f:
                f.write(self.doc.render())
        except OSError as e:
            QMessageBox.critical(self, t("save.error_title"),
                                  t("save.error_msg", name=self.path.name, error=str(e)))
            return
        self._set_modified(False)
        self.saved.emit()

    def _snapshot_undo(self):
        """A appeler AVANT toute modification -- sauvegarde l'etat actuel du document
        (texte serialise ; fidelite deja prouvee par le parser) pour pouvoir l'annuler."""
        self._undo_stack.append(self.doc.render())
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self.btn_undo.setEnabled(True)

    def undo(self):
        if not self._undo_stack:
            return
        previous_text = self._undo_stack.pop()
        self.doc = parse_ecf_text(previous_text)
        self._current_block = None
        self.props_table.setRowCount(0)
        self._populate_tree()
        self._set_modified(True)
        if not self._undo_stack:
            self.btn_undo.setEnabled(False)

    # ------------------------------------------------------------------
    # Arbre des blocs
    # ------------------------------------------------------------------

    def _populate_tree(self):
        self.tree.clear()
        group_before, label_by_block_id = self.doc.scan_section_groups_and_labels()
        self._label_by_block_id = label_by_block_id
        for index, node in enumerate(self.doc.nodes):
            if index in group_before:
                self.tree.addTopLevelItem(self._make_group_header_item(group_before[index]))
            if isinstance(node, EcfBlock):
                self.tree.addTopLevelItem(self._make_block_item(node))

    def _make_group_header_item(self, title: str) -> QTreeWidgetItem:
        """Ligne de section non selectionnable (juste un repere visuel), pour les
        groupes de blocs annonces par un commentaire '# === Titre ===' dans le fichier
        source -- aide a s'y retrouver dans les tres longs fichiers (ex: Containers.ecf
        classe ses centaines de blocs en categories comme 'Gigas', 'Dinosaurs',
        'Zirax'...)."""
        item = QTreeWidgetItem([f"\u25a0 {title}"])
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(0, QBrush(QColor(PRIMARY_DARK)))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        return item

    def _make_block_item(self, block: EcfBlock) -> QTreeWidgetItem:
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind
        name = block.get_property('Name')
        if name and name != ident:
            label += f"  - {name}"
        friendly = self._label_by_block_id.get(id(block)) if hasattr(self, '_label_by_block_id') else None
        if friendly:
            label += f"   ({friendly})"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, block)
        for child in block.children:
            if isinstance(child, EcfBlock):
                item.addChild(self._make_block_item(child))
        return item

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            return
        if not self._search_matches or self._search_last_query != query:
            self._search_matches = []
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                block = item.data(0, Qt.ItemDataRole.UserRole)
                searchable = item.text(0).lower()
                if isinstance(block, EcfBlock):
                    for key in ('Name', 'CustomIcon', 'TemplateRoot', 'IndexName'):
                        val = block.get_property(key)
                        if val:
                            searchable += " " + val.lower()
                if query in searchable:
                    self._search_matches.append(item)
                it += 1
            self._search_index = -1
            self._search_last_query = query

        if not self._search_matches:
            self.search_status.setText("Aucun resultat")
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._on_block_selected(item, 0)
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    # ------------------------------------------------------------------
    # Table des proprietes (editable)
    # ------------------------------------------------------------------

    def _on_block_selected(self, item: QTreeWidgetItem, column: int):
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        self._current_block = block
        self._refresh_props_table()

    _ITEM_KEY_RE = re.compile(r'^(Name|Group)_(\d+)$')

    def _detect_repeating_items(self, block: EcfBlock):
        """Detecte les sous-blocs type 'Child Items'/'Child Inputs' : une suite de
        lignes de propriete dont la PREMIERE paire est 'Name_N: X' ou 'Group_N: X'
        (N croissant), suivie d'un jeu de parametres (param1, param2...) globalement
        coherent d'une ligne a l'autre. Tres courant dans les tables de butin
        (Containers.ecf, LootGroups.ecf) et les recettes (Templates.ecf).

        Retourne la liste ordonnee des noms de colonnes 'paramX' si detecte (peut etre
        vide si aucun param, mais Name_N/Group_N est present), sinon None (retombe sur
        l'affichage classique cle/valeur)."""
        prop_children = [c for c in block.children if isinstance(c, EcfProperty)]
        if len(prop_children) < 2:
            return None
        matches = 0
        param_keys_seen = []
        for prop in prop_children:
            if not prop.pairs:
                continue
            first_key = prop.pairs[0][0]
            if first_key and self._ITEM_KEY_RE.match(first_key):
                matches += 1
                for k, v in prop.pairs[1:]:
                    if k and k not in param_keys_seen:
                        param_keys_seen.append(k)
        if matches < 2 or matches < len(prop_children) * 0.5:
            return None
        # Trie les colonnes param naturellement (param1, param2, ..., param10) plutot
        # qu'alphabetiquement (qui mettrait param10 avant param2)
        def _natural_key(k):
            m = re.search(r'(\d+)$', k)
            return (k[:m.start()] if m else k, int(m.group(1)) if m else 0)
        param_keys_seen.sort(key=_natural_key)
        return param_keys_seen

    def _refresh_props_table(self):
        if not self._current_block:
            return
        block = self._current_block
        self.props_table.blockSignals(True)
        self.props_table.setSortingEnabled(False)

        param_columns = self._detect_repeating_items(block)
        self._table_mode = param_columns is not None
        self.btn_add_row.setVisible(self._table_mode)
        self.btn_add_prop.setVisible(not self._table_mode)

        if self._table_mode:
            self._refresh_props_table_grid(block, param_columns)
        else:
            self._refresh_props_table_flat(block)

        self.props_table.blockSignals(False)

    def _refresh_props_table_flat(self, block: EcfBlock):
        """Affichage classique : une ligne par paire cle/valeur (utilise pour la
        grande majorite des blocs, qui n'ont pas de structure repetitive)."""
        self.props_table.setColumnCount(2)
        self.props_table.setHorizontalHeaderLabels([t("ecf.col_property"), t("ecf.col_value")])
        rows = []
        for k, v in block.pairs:
            if k:
                rows.append((k, v, block))
        for child in block.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k:
                        rows.append((k, v, child))
        self.props_table.setRowCount(len(rows))
        for i, (k, v, prop_node) in enumerate(rows):
            item_k = QTableWidgetItem(k)
            item_k.setFlags(item_k.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_k.setData(Qt.ItemDataRole.UserRole, (prop_node, k))
            item_v = QTableWidgetItem(v)
            item_v.setData(Qt.ItemDataRole.UserRole, (prop_node, k))
            if prop_node is block:
                item_k.setToolTip(t("ecf.header_property_tooltip"))
            if id(prop_node) in self._edited_prop_nodes:
                item_k.setBackground(COLOR_MODIFIED_ROW)
                item_v.setBackground(COLOR_MODIFIED_ROW)
            self.props_table.setItem(i, 0, item_k)
            self.props_table.setItem(i, 1, item_v)

    def _refresh_props_table_grid(self, block: EcfBlock, param_columns: List[str]):
        """Affichage en tableau pour les structures repetitives (Child Items, Child
        Inputs...) : une LIGNE par entree (Name_X/Group_X), une COLONNE par parametre
        -- bien plus lisible qu'une longue liste plate ou les param1/param2 de
        chaque entree se retrouvaient meles a la suite les uns des autres."""
        columns = [t("ecf.col_type"), t("ecf.col_item_value")] + param_columns
        self.props_table.setColumnCount(len(columns))
        self.props_table.setHorizontalHeaderLabels(columns)

        prop_children = [c for c in block.children if isinstance(c, EcfProperty)]
        self.props_table.setRowCount(len(prop_children))
        for row, prop in enumerate(prop_children):
            if not prop.pairs:
                continue
            first_key, first_value = prop.pairs[0]
            m = self._ITEM_KEY_RE.match(first_key) if first_key else None
            item_type = QTableWidgetItem(m.group(1) if m else (first_key or ""))
            item_type.setData(Qt.ItemDataRole.UserRole, (prop, "__TYPE__"))
            item_value = QTableWidgetItem(first_value)
            item_value.setData(Qt.ItemDataRole.UserRole, (prop, first_key))
            modified = id(prop) in self._edited_prop_nodes
            if modified:
                item_type.setBackground(COLOR_MODIFIED_ROW)
                item_value.setBackground(COLOR_MODIFIED_ROW)
            self.props_table.setItem(row, 0, item_type)
            self.props_table.setItem(row, 1, item_value)

            pairs_by_key = {k: v for k, v in prop.pairs[1:] if k}
            for col_idx, param_key in enumerate(param_columns):
                cell = QTableWidgetItem(pairs_by_key.get(param_key, ""))
                cell.setData(Qt.ItemDataRole.UserRole, (prop, param_key))
                if modified:
                    cell.setBackground(COLOR_MODIFIED_ROW)
                self.props_table.setItem(row, 2 + col_idx, cell)

    def _on_cell_changed(self, item: QTableWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        prop_node, pair_key = data
        new_value = item.text()

        if isinstance(prop_node, EcfBlock):
            old_value = prop_node.get(pair_key)
            if old_value == new_value:
                return
            self._snapshot_undo()
            prop_node.set(pair_key, new_value)
            annotate_target = None
            key_for_annotation = pair_key
        elif pair_key == "__TYPE__":
            # Colonne 'Type' en mode tableau : bascule Name_N <-> Group_N en gardant le
            # meme N et la meme valeur -- reconstruit juste la cle de la 1ere paire.
            if not isinstance(prop_node, EcfProperty) or not prop_node.pairs:
                return
            old_first_key, first_value = prop_node.pairs[0]
            m = self._ITEM_KEY_RE.match(old_first_key) if old_first_key else None
            suffix = m.group(2) if m else "0"
            new_type = new_value.strip()
            if new_type not in ("Name", "Group"):
                # Valeur non reconnue : remet l'affichage precedent plutot que de
                # laisser une cle invalide silencieusement
                self._refresh_props_table()
                return
            new_first_key = f"{new_type}_{suffix}"
            if new_first_key == old_first_key:
                return
            self._snapshot_undo()
            prop_node.pairs[0] = (new_first_key, first_value)
            prop_node.dirty = True
            annotate_target = prop_node
            old_value = old_first_key
            key_for_annotation = "Type"
        else:
            if not isinstance(prop_node, EcfProperty):
                return
            old_value = None
            idx = None
            for i, (k, v) in enumerate(prop_node.pairs):
                if k == pair_key:
                    old_value = v
                    idx = i
                    break
            if idx is None:
                if new_value.strip() == "":
                    return
                # Nouvelle colonne param pour cette ligne precise (ex: on tape une
                # valeur dans param2 pour une ligne qui n'avait que param1 jusque la)
                self._snapshot_undo()
                prop_node.pairs.append((pair_key, new_value))
                prop_node.dirty = True
                annotate_target = prop_node
                old_value = "(absent)"
            else:
                if old_value == new_value:
                    return
                self._snapshot_undo()
                prop_node.pairs[idx] = (pair_key, new_value)
                prop_node.dirty = True
                annotate_target = prop_node
            key_for_annotation = pair_key

        if settings.get_annotations_enabled() and annotate_target is not None:
            author = settings.get_author()
            annotate_property(annotate_target, f"# original {key_for_annotation}: {old_value} -- Mod par {author}")

        self._edited_prop_nodes.add(id(prop_node))
        self._set_modified(True)
        self.props_table.blockSignals(True)
        item.setBackground(COLOR_MODIFIED_ROW)
        self.props_table.blockSignals(False)

    def _show_table_context_menu(self, pos):
        item = self.props_table.itemAt(pos)
        if not item or not self._current_block:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        prop_node, pair_key = data
        value_item = item  # la cellule cliquee elle-meme porte le texte pertinent
        # traduire/bbcode agissent sur n'importe quelle cellule cliquee ; supprimer agit
        # sur toute la LIGNE (le prop_node entier), peu importe la colonne cliquee

        is_header_prop = isinstance(prop_node, EcfBlock)
        global_pos = self.props_table.viewport().mapToGlobal(pos)

        menu = QMenu(self)
        add_clipboard_menu_actions(menu, self.props_table, allow_new_rows=False)
        menu.addSeparator()

        from core import translation
        translate_menu = menu.addMenu(t("ctx.translate_to"))
        lang_actions = {}
        for label, code in translation.COMMON_LANGUAGES:
            a = translate_menu.addAction(label)
            lang_actions[a] = code

        action_bbcode = menu.addAction(t("ctx.bbcode"))

        action_del = None
        if not is_header_prop:
            action_del = menu.addAction(t("ecf.delete_property_action"))

        chosen = menu.exec(global_pos)

        if chosen == action_bbcode:
            new_text = open_bbcode_tool(self, value_item.text())
            if new_text is not None:
                value_item.setText(new_text)
        elif chosen in lang_actions:
            self._translate_cell(value_item, None, prop_node, lang_actions[chosen])
        elif chosen == action_del and isinstance(prop_node, EcfProperty):
            self._snapshot_undo()
            remove_property_line(self._current_block, prop_node)
            self._set_modified(True)
            self._refresh_props_table()

    def _translate_cell(self, value_item, key_item, prop_node, target_lang: str):
        from core import translation
        text = value_item.text()
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(text, target=target_lang)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        dialog = TranslationResultDialog(text, translated, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.accepted_replace:
            return
        new_value = dialog.result_text()

        # Applique via le meme chemin qu'une edition manuelle -- annotation de
        # tracabilite comprise (comportement coherent avec toute autre modification).
        value_item.setText(new_value)  # declenche _on_cell_changed, qui gere tout le reste

    def _add_property_dialog(self):
        if not self._current_block:
            QMessageBox.information(self, t("ecf.no_block_title"), t("ecf.no_block_msg"))
            return
        key, ok = QInputDialog.getText(self, t("ecf.add_property_title"), t("ecf.property_name_label"))
        if not ok or not key.strip():
            return
        value, ok = QInputDialog.getText(self, t("ecf.add_property_title"),
                                          t("ecf.property_value_label", key=key))
        if not ok:
            return
        self._snapshot_undo()

        # Permet de taper directement plusieurs paires a la suite, EXACTEMENT comme
        # dans le fichier (ex: valeur = 'AlienParts04, param1: 0.6, param2: "1,3"') --
        # sinon chaque propriete ajoutee une par une finissait sur SA PROPRE ligne au
        # lieu d'etre regroupee comme ses voisines (Name_X, param1, param2...), ce qui
        # cassait le format attendu par le jeu pour ce genre de structure repetitive.
        # Les valeurs contenant une virgule doivent etre entre guillemets, comme
        # partout ailleurs dans le fichier (ex: "1,3") -- une virgule NON protegee y
        # serait sinon interpretee a tort comme separant une propriete supplementaire.
        from core.ecf.parser import _parse_pairs
        extra = _parse_pairs(value.strip())
        if len(extra) > 1 and extra[0][0] is None:
            pairs = [(key.strip(), extra[0][1])] + extra[1:]
        else:
            pairs = [(key.strip(), value.strip())]

        new_prop = add_property_line(self._current_block, pairs)
        if settings.get_annotations_enabled():
            author = settings.get_author()
            annotate_property(new_prop, f"# Ajoute par {author}")
        self._set_modified(True)
        self._refresh_props_table()

    def _add_table_row_dialog(self):
        """Ajoute une ligne au mode tableau (Child Items...) -- la numerotation
        (Name_N/Group_N) et la position (a la suite des entrees du meme type) sont
        entierement automatiques, jamais laissees a la saisie manuelle : c'est
        precisement ce qui posait probleme avec le dialogue generique '+ Propriete'
        (cle non numerotee, ligne ajoutee en toute fin de bloc plutot qu'au bon
        endroit)."""
        if not self._current_block or not self._table_mode:
            QMessageBox.information(self, t("ecf.no_block_title"), t("ecf.no_block_msg"))
            return
        param_columns = self._detect_repeating_items(self._current_block) or []
        dialog = AddTableRowDialog(param_columns, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._snapshot_undo()
        new_prop = add_repeating_item_row(
            self._current_block, dialog.result_type, dialog.result_value, dialog.result_extra_pairs)
        if settings.get_annotations_enabled():
            author = settings.get_author()
            annotate_property(new_prop, f"# Ajoute par {author}")
        self._set_modified(True)
        self._refresh_props_table()

    # ------------------------------------------------------------------
    # Blocs : ajout / suppression
    # ------------------------------------------------------------------

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        menu = QMenu(self)
        action_disable = menu.addAction(t("ecf.disable_block_action"))
        action_del = menu.addAction(t("ecf.delete_block_action"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == action_disable:
            confirm = QMessageBox.question(self, t("merge.confirm_title"),
                                            t("ecf.confirm_disable_block", name=item.text(0)))
            if confirm == QMessageBox.StandardButton.Yes:
                self._snapshot_undo()
                from core.ecf.disable_block import disable_block
                disable_block(self.doc, block, settings.get_author())
                self._set_modified(True)
                if self._current_block is block:
                    self._current_block = None
                    self.props_table.setRowCount(0)
                self._populate_tree()
        elif chosen == action_del:
            confirm = QMessageBox.question(self, t("merge.confirm_title"),
                                            t("ecf.confirm_delete_block", name=item.text(0)))
            if confirm == QMessageBox.StandardButton.Yes:
                self._snapshot_undo()
                remove_block(self.doc.nodes, block)
                self._set_modified(True)
                if self._current_block is block:
                    self._current_block = None
                    self.props_table.setRowCount(0)
                self._populate_tree()

    def _open_disabled_blocks_dialog(self):
        from core.ecf.disable_block import find_disabled_blocks, enable_disabled_block
        dialog = DisabledBlocksDialog(self.doc, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.reactivated:
            self._set_modified(True)
            self._populate_tree()

    def _open_property_filter(self):
        dialog = PropertyFilterDialog(self.doc, on_filter_changed=self._apply_property_filter, parent=self)
        dialog.exec()

    def _apply_property_filter(self, keys: List[str]):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            block = item.data(0, Qt.ItemDataRole.UserRole)
            if not keys or not isinstance(block, EcfBlock):
                item.setHidden(False)
                continue
            item.setHidden(not all(k in _block_own_keys(block) for k in keys))

    def _add_block_dialog(self):
        kind, ok = QInputDialog.getText(self, t("ecf.add_block_title"), t("ecf.block_kind_label"))
        if not ok or not kind.strip():
            return
        block_id, ok = QInputDialog.getText(self, t("ecf.add_block_title"), t("ecf.id_label"))
        if not ok or not block_id.strip():
            return
        name, ok = QInputDialog.getText(self, t("ecf.add_block_title"), t("ecf.name_optional_label"))
        if not ok:
            name = ""
        pairs = [('Id', block_id.strip())]
        if name.strip():
            pairs.append(('Name', name.strip()))
        self._snapshot_undo()
        new_block = create_block(kind.strip(), pairs)
        if settings.get_annotations_enabled():
            author = settings.get_author()
            new_block.comment = f"# Ajoute par {author}"
        self.doc.nodes.append(new_block)
        self._set_modified(True)
        self._populate_tree()


class CompareWidget(QWidget):
    """Vue cote a cote : copie de travail (editable) a gauche, source(s) A/B en
    lecture seule a droite (dans des onglets si plusieurs sont disponibles).
    Le clic droit "copier ce bloc" fonctionne aussi depuis les panneaux source ici."""

    def __init__(self, working_path: Path, compare_sources: Dict[str, tuple], view_widget_factory,
                 copy_block_callback=None, duplicate_block_callback=None):
        """
        compare_sources : {label: (chemin_source, racine_source)}
        view_widget_factory(path, on_copy_block=None, on_duplicate_block=None) doit
        retourner un widget de lecture seule (typiquement EcfViewWidget de
        main_window.py) -- injecte pour eviter un import circulaire entre ce module et
        main_window.py.
        copy_block_callback(block, source_path, source_root, source_label) : appele
        quand l'utilisateur choisit "copier ce bloc" depuis un panneau source.
        duplicate_block_callback(block, parent_chain, source_path, source_root,
        source_label) : appele quand l'utilisateur choisit "dupliquer avec un nouvel
        Id" depuis un panneau source.
        """
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.edit_widget = EcfEditWidget(working_path)
        splitter.addWidget(self.edit_widget)

        if compare_sources:
            right_side = QTabWidget()
            for label, (src_path, src_root) in compare_sources.items():
                on_copy = None
                if copy_block_callback:
                    on_copy = (lambda block, p=src_path, r=src_root, l=label:
                               copy_block_callback(block, p, r, l))
                on_dup = None
                if duplicate_block_callback:
                    on_dup = (lambda block, parent_chain, p=src_path, r=src_root, l=label:
                              duplicate_block_callback(block, parent_chain, p, r, l))
                right_side.addTab(
                    view_widget_factory(src_path, on_copy_block=on_copy, copy_label=label,
                                         on_duplicate_block=on_dup),
                    label)
            splitter.addWidget(right_side)
            splitter.setSizes([600, 500])
        else:
            splitter.setSizes([1])

        layout.addWidget(splitter)

        self.modified_changed = self.edit_widget.modified_changed
        self.saved = self.edit_widget.saved

    def is_modified(self) -> bool:
        return self.edit_widget.is_modified()

    def save(self):
        self.edit_widget.save()

```

### gui\main_window.py

```py
"""
Fenetre principale de l'editeur de scenario Empyrion.

Layout a 3 volets :
  - Gauche  : Scenario A (base), LECTURE SEULE
  - Centre  : Copie de travail (modifiable) + onglets des fichiers ouverts
  - Droite  : Scenario B (source pour la fusion, optionnel), LECTURE SEULE

Seule la copie de travail (une copie physique complete du scenario A, creee a un
nouvel emplacement) peut etre modifiee. Les scenarios A et B ne sont jamais touches.
Clic droit sur un fichier de A ou B -> "Copier vers la copie de travail" pour y
importer un fichier (mesh, icone, ECF, YAML...).
"""
import sys
import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QSplitter, QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QLabel, QStatusBar, QHeaderView, QMessageBox, QMenu,
    QProgressDialog, QInputDialog, QPushButton, QSizePolicy, QDialog, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QColor, QBrush

from core.scanner import scan_scenario
from core.models import Scenario, FileEntry
from core.workspace import (
    Workspace, open_workspace, load_existing_workspace, copy_file_into_working,
    merge_file_into_working, merge_folder_into_working, merge_block_into_working,
    merge_csv_row_into_working, translate_csv_cell_into_working,
    duplicate_ecf_block_into_working, duplicate_csv_row_into_working,
    copy_yaml_entry_into_working, duplicate_yaml_entry_into_working, MergeHighlight,
)
from core.ecf.parser import parse_ecf_file
from core.ecf.dependency_check import check_references
from core.ecf.pending_conflicts import (
    find_pending_conflicts, activate_pending_conflict, parse_pending_block, find_used_ids,
)
from core.ecf.model import EcfDocument, EcfBlock, EcfProperty, block_identity, normalized_kind
from core.yamllite.parser import parse_yaml_file
from core.yamllite.model import YamlDocument, YamlEntry
from core import project_store, settings
from core import i18n
from core.i18n import t
from core.project_store import ProjectRecord

from gui.new_project_dialog import NewProjectDialog
from gui.startup_dialog import StartupDialog
from gui.ecf_edit_widget import EcfEditWidget, CompareWidget, PendingConflictsDialog, PropertyFilterDialog, _block_own_keys, EcfHeaderExplanationPanel
from gui.csv_edit_widget import CsvEditWidget
from gui.yaml_edit_widget import YamlEditWidget
from gui.txt_edit_widget import TxtEditWidget
from gui.wiki_viewer import open_wiki
from gui.theme import NAVY, PRIMARY_DARK, PRIMARY, icon, icon_size
from core.workspace_undo import WorkspaceUndoStack, FileStateUndo, MultiFileStateUndo, FolderStateUndo, capture_file, capture_folder

COLOR_NEW_BLOCK = QBrush(QColor(200, 255, 200))       # vert clair : bloc entierement nouveau
COLOR_CHANGED_BLOCK = QBrush(QColor(255, 240, 200))   # orange clair : bloc complete partiellement
COLOR_NEW_PROPERTY = QBrush(QColor(200, 255, 200))    # vert clair : ligne de propriete ajoutee


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Empyrion Scenario Editor")
        self.resize(1500, 800)
        self.workspace_undo = WorkspaceUndoStack()

        self.workspace: Optional[Workspace] = None
        self._highlights: dict = {}  # Path -> MergeHighlight, pour colorer les ajouts de fusion

        self._build_menu()
        self._build_toolbar()
        self._refresh_scenario_b_menu_text()
        self._build_layout()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(t("status.no_project"))

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_menu(self):
        self.menu_file = self.menuBar().addMenu(t("menu.file"))
        self.action_new = self.menu_file.addAction(t("menu.file.new_project"))
        self.action_new.triggered.connect(self.new_project_dialog)
        self.action_recent = self.menu_file.addAction(t("menu.file.recent_projects"))
        self.action_recent.triggered.connect(self.show_startup_dialog)
        self.menu_file.addSeparator()
        self.action_save = self.menu_file.addAction(t("menu.file.save"))
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.triggered.connect(self._save_current_tab)
        self.menu_file.addSeparator()
        self.action_compare = self.menu_file.addAction(t("menu.file.compare"))
        self.action_compare.triggered.connect(self._open_compare_dialog)
        self.action_manage_scenario_b = self.menu_file.addAction(t("menu.file.open_scenario_b"))
        self.action_manage_scenario_b.triggered.connect(self._open_or_change_scenario_b)
        self.action_remove_scenario_b = self.menu_file.addAction(t("menu.file.remove_scenario_b"))
        self.action_remove_scenario_b.triggered.connect(self._remove_scenario_b)
        self.action_remove_scenario_b.setEnabled(False)
        self.action_backup_scenario = self.menu_file.addAction(t("menu.file.backup_scenario"))
        self.action_backup_scenario.triggered.connect(lambda: self._open_backup_dialog('scenario'))
        self.action_manage_saves = self.menu_file.addAction(t("menu.file.manage_saves"))
        self.action_manage_saves.triggered.connect(lambda: self._open_backup_dialog('savegame'))
        self.action_repair_permissions = self.menu_file.addAction(t("menu.file.repair_permissions"))
        self.action_repair_permissions.triggered.connect(self._repair_working_copy_permissions)
        self.menu_file.addSeparator()
        self.action_quit = self.menu_file.addAction(t("menu.file.quit"))
        self.action_quit.triggered.connect(self.close)

        self.menu_check = self.menuBar().addMenu(t("menu.verification"))
        self.action_refs = self.menu_check.addAction(t("menu.verification.check_refs"))
        self.action_refs.triggered.connect(self.check_references_dialog)
        self.action_pending = self.menu_check.addAction(t("menu.verification.pending"))
        self.action_pending.triggered.connect(self.check_pending_conflicts_dialog)

        self.menu_options = self.menuBar().addMenu(t("menu.options"))
        self.action_author = self.menu_options.addAction(t("menu.options.author"))
        self.action_author.triggered.connect(self._set_author_dialog)
        self.action_toggle_annotations = self.menu_options.addAction(t("menu.options.annotations"))
        self.action_toggle_annotations.setCheckable(True)
        self.action_toggle_annotations.setChecked(settings.get_annotations_enabled())
        self.action_toggle_annotations.toggled.connect(settings.set_annotations_enabled)
        self.action_toggle_merge = self.menu_options.addAction(t("menu.options.merge_enabled"))
        self.action_toggle_merge.setCheckable(True)
        self.action_toggle_merge.setChecked(settings.get_merge_enabled())
        self.action_toggle_merge.toggled.connect(settings.set_merge_enabled)

        self.menu_help = self.menuBar().addMenu(t("menu.help"))
        self.action_wiki_app = self.menu_help.addAction(t("menu.help.wiki_app"))
        self.action_wiki_app.triggered.connect(
            lambda: open_wiki(self, t("menu.help.wiki_app").rstrip("."), "wiki_app"))
        self.action_wiki_empyrion = self.menu_help.addAction(t("menu.help.wiki_empyrion"))
        self.action_wiki_empyrion.triggered.connect(
            lambda: open_wiki(self, t("menu.help.wiki_empyrion").rstrip("."), "wiki_empyrion"))

    def _toggle_language(self):
        current = i18n.get_language()
        new_lang = "en" if current == "fr" else "fr"
        i18n.set_language(new_lang)
        self._apply_language()

    def _apply_language(self):
        """Reassigne le texte de tous les elements de menu traduits, sans reconstruire
        la structure (garde les connexions de signaux intactes)."""
        self.menu_file.setTitle(t("menu.file"))
        self.action_new.setText(t("menu.file.new_project"))
        self.action_recent.setText(t("menu.file.recent_projects"))
        self.action_save.setText(t("menu.file.save"))
        self.action_compare.setText(t("menu.file.compare"))
        self._refresh_scenario_b_menu_text()
        self.action_backup_scenario.setText(t("menu.file.backup_scenario"))
        self.action_manage_saves.setText(t("menu.file.manage_saves"))
        self.action_repair_permissions.setText(t("menu.file.repair_permissions"))
        self.action_quit.setText(t("menu.file.quit"))

        self.menu_check.setTitle(t("menu.verification"))
        self.action_refs.setText(t("menu.verification.check_refs"))
        self.action_pending.setText(t("menu.verification.pending"))

        self.menu_options.setTitle(t("menu.options"))
        self.action_author.setText(t("menu.options.author"))
        self.action_toggle_annotations.setText(t("menu.options.annotations"))
        self.action_toggle_merge.setText(t("menu.options.merge_enabled"))

        self.menu_help.setTitle(t("menu.help"))
        self.action_wiki_app.setText(t("menu.help.wiki_app"))
        self.action_wiki_empyrion.setText(t("menu.help.wiki_empyrion"))

        self.btn_language.setText(i18n.get_language().upper())
        self.btn_language.setToolTip(t("menu.options.language"))
        self.btn_workspace_undo.setText(t("wsundo.button"))
        self._refresh_workspace_undo_button()

    def _build_toolbar(self):
        toolbar = self.addToolBar("Langue / Language")
        toolbar.setMovable(False)
        self.btn_workspace_undo = QPushButton(icon("fa5s.undo", "#ffffff"), t("wsundo.button"))
        self.btn_workspace_undo.setIconSize(icon_size())
        self.btn_workspace_undo.setToolTip(t("wsundo.tooltip_empty"))
        self.btn_workspace_undo.setEnabled(False)
        self.btn_workspace_undo.clicked.connect(self._undo_workspace_action)
        toolbar.addWidget(self.btn_workspace_undo)
        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self._undo_workspace_action)

        self.btn_language = QPushButton(icon("fa5s.globe", "#ffffff"), i18n.get_language().upper())
        self.btn_language.setIconSize(icon_size())
        self.btn_language.setFixedWidth(75)
        self.btn_language.setToolTip(t("menu.options.language"))
        self.btn_language.clicked.connect(self._toggle_language)
        toolbar.addWidget(self.btn_language)

    def _push_workspace_undo(self, action):
        self.workspace_undo.push(action)
        self._refresh_workspace_undo_button()

    def _refresh_workspace_undo_button(self):
        if self.workspace_undo.can_undo():
            self.btn_workspace_undo.setEnabled(True)
            self.btn_workspace_undo.setToolTip(
                t("wsundo.tooltip_action", label=self.workspace_undo.peek_label()))
        else:
            self.btn_workspace_undo.setEnabled(False)
            self.btn_workspace_undo.setToolTip(t("wsundo.tooltip_empty"))

    def _undo_workspace_action(self):
        if not self.workspace_undo.can_undo():
            return
        label = self.workspace_undo.undo()
        if not self.workspace:
            return
        self.workspace.rescan_working()
        self._populate_tree(self.tree_working, self.workspace.working)
        # Ferme tout onglet ouvert sur un fichier potentiellement touche par
        # l'annulation -- plus sur de le rouvrir a froid que de tenter de
        # rafraichir un editeur peut-etre desynchronise de son fichier.
        for i in reversed(range(self.tabs.count())):
            self.tabs.removeTab(i)
        self._refresh_workspace_undo_button()
        self.statusBar().showMessage(t("wsundo.status_done", label=label))

    def _save_current_tab(self):
        widget = self.tabs.currentWidget()
        if widget and hasattr(widget, 'save'):
            widget.save()
        else:
            self.statusBar().showMessage(t("status.nothing_to_save"))

    def _open_compare_dialog(self):
        from gui.scenario_compare_dialog import ScenarioCompareDialog
        dialog = ScenarioCompareDialog(self)
        dialog.exec()

    def _refresh_scenario_b_menu_text(self):
        """Met a jour le libelle du menu Scenario B selon l'etat actuel (aucun projet
        ouvert / pas de Scenario B / Scenario B deja defini) et active/desactive le
        retrait en consequence."""
        if self.workspace and self.workspace.is_merge_mode:
            self.action_manage_scenario_b.setText(t("menu.file.change_scenario_b"))
            self.action_remove_scenario_b.setEnabled(True)
        else:
            self.action_manage_scenario_b.setText(t("menu.file.open_scenario_b"))
            self.action_remove_scenario_b.setEnabled(False)
        self.action_remove_scenario_b.setText(t("menu.file.remove_scenario_b"))

    def _open_or_change_scenario_b(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.missing_field"), t("status.no_project"))
            return
        folder = QFileDialog.getExistingDirectory(self, t("scenariob.choose_folder"))
        if not folder:
            return
        new_root = Path(folder)

        if self.workspace.is_merge_mode:
            confirm = QMessageBox.question(
                self, t("scenariob.confirm_change_title"),
                t("scenariob.confirm_change_msg", old=self.workspace.source_b_root.name, new=new_root.name)
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self.workspace.set_scenario_b(new_root)
        self._refresh_all_trees()
        self._refresh_scenario_b_menu_text()
        self.statusBar().showMessage(t("status.scenario_b_set", name=new_root.name))

    def _remove_scenario_b(self):
        if not self.workspace or not self.workspace.is_merge_mode:
            return
        name = self.workspace.source_b_root.name
        confirm = QMessageBox.question(
            self, t("scenariob.confirm_remove_title"), t("scenariob.confirm_remove_msg", name=name))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.workspace.set_scenario_b(None)
        self._refresh_all_trees()
        self._refresh_scenario_b_menu_text()
        self.statusBar().showMessage(t("status.scenario_b_removed"))

    def _open_backup_dialog(self, kind: str):
        from gui.backup_dialog import BackupManagerDialog
        dialog = BackupManagerDialog(kind, self)
        dialog.exec()

    def _repair_working_copy_permissions(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.missing_field"), t("repair.no_project_msg"))
            return
        from core.fsutil import clear_readonly
        clear_readonly(self.workspace.working_root)
        QMessageBox.information(self, t("repair.done_title"), t("repair.done_msg"))

    def _set_author_dialog(self):
        current = settings.get_author()
        name, ok = QInputDialog.getText(self, t("author.title"), t("author.label"), text=current)
        if ok and name.strip():
            settings.set_author(name.strip())

    def check_pending_conflicts_dialog(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.no_project_title"), t("err.no_project_msg"))
            return

        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']

        entries = []
        for path in ecf_files:
            try:
                doc = parse_ecf_file(path)
            except Exception:
                continue
            for c in find_pending_conflicts(doc):
                pending_block = parse_pending_block(c)
                base_block = None
                if pending_block:
                    ident = block_identity(pending_block)
                    if ident:
                        base_block = doc.find_block(normalized_kind(pending_block.kind), 'Id', ident) \
                                     or doc.find_block(normalized_kind(pending_block.kind), 'Name', ident)
                entries.append({'path': path, 'doc': doc, 'conflict': c,
                                 'pending_block': pending_block, 'base_block': base_block})

        if not entries:
            QMessageBox.information(self, t("pending.none_title"), t("pending.none_msg"))
            return

        used_ids = find_used_ids(ecf_files)

        dialog = PendingConflictsDialog(entries, used_ids, self)
        if dialog.exec() != PendingConflictsDialog.DialogCode.Accepted:
            return
        if not dialog.chosen_entry or not dialog.chosen_new_id:
            return

        target_path = dialog.chosen_entry['path']
        target_conflict = dialog.chosen_entry['conflict']
        new_id = dialog.chosen_new_id

        try:
            doc = parse_ecf_file(target_path)
            fresh_conflicts = find_pending_conflicts(doc)
            match = next((c for c in fresh_conflicts if c.header_text == target_conflict.header_text), None)
            if match is None:
                QMessageBox.critical(self, t("err.title"), t("pending.not_found_msg"))
                return

            success = activate_pending_conflict(doc, match, new_id)
            if not success:
                QMessageBox.critical(self, t("err.title"), t("pending.cannot_activate_msg"))
                return

            prior = capture_file(target_path)
            with open(target_path, 'w', encoding='utf-8', newline='') as f:
                f.write(doc.render())
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('pending.activation_error')} :\n{e}")
            return

        self._push_workspace_undo(
            FileStateUndo(target_path, prior, t("wsundo.activate_pending", name=target_path.name)))

        self.workspace.rescan_working()
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(target_path):
                self.tabs.removeTab(i)

        self.statusBar().showMessage(t("status.block_activated", id=new_id, file=target_path.name))
        QMessageBox.information(self, t("pending.activated_title"),
                                 t("pending.activated_msg", id=new_id, file=target_path.name))

    def check_references_dialog(self):
        if not self.workspace:
            QMessageBox.information(self, t("err.no_project_title"), t("err.no_project_msg"))
            return

        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']
        if not ecf_files:
            QMessageBox.information(self, t("err.no_file_title"), t("check.no_ecf_found"))
            return

        progress = QProgressDialog(f"Verification de {len(ecf_files)} fichier(s)...", None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            broken = check_references(ecf_files)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("err.title"), f"{t('check.verification_error')} :\n{e}")
            return
        progress.close()

        if not broken:
            QMessageBox.information(self, t("check.refs_title"), t("check.refs_ok", n=len(ecf_files)))
            return

        details = "\n".join(b.label() for b in broken[:100])
        more = t("check.refs_more", n=len(broken) - 100) if len(broken) > 100 else ""
        QMessageBox.warning(
            self, t("check.refs_broken_title"),
            t("check.refs_broken_msg", n=len(broken), details=details, more=more)
        )

    def _build_layout(self):
        # Layout vertical : en HAUT les fichiers ouverts (l'espace de travail principal,
        # comparaison + edition -- ce qui merite le plus de place), en BAS une bande
        # compacte de navigation avec les 3 scenarios cote a cote (A | copie de travail | B).
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)

        # -- Haut : onglets des fichiers ouverts --
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(lambda i: self.tabs.removeTab(i))
        self.main_splitter.addWidget(self.tabs)

        # -- Bas : bande de navigation A | copie de travail | B --
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.panel_a = QWidget()
        layout_a = QVBoxLayout(self.panel_a)
        layout_a.setContentsMargins(4, 2, 4, 2)
        self.label_a = QLabel(t("panel.scenario_a"))
        self.label_a.setStyleSheet(f"font-weight: 700; color: {NAVY};")
        self.tree_a = QTreeWidget()
        self.tree_a.setHeaderLabels(["Scenario A"])
        self.tree_a.itemDoubleClicked.connect(lambda item, col: self._on_source_double_clicked(item, self._root_a))
        self.tree_a.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_a.customContextMenuRequested.connect(
            lambda pos: self._show_source_context_menu(self.tree_a, pos, self._root_a))
        layout_a.addWidget(self.label_a)
        layout_a.addWidget(self.tree_a)
        bottom_splitter.addWidget(self.panel_a)

        self.panel_working = QWidget()
        layout_w = QVBoxLayout(self.panel_working)
        layout_w.setContentsMargins(4, 2, 4, 2)
        self.label_working = QLabel(t("panel.working_copy"))
        self.label_working.setStyleSheet(f"font-weight: 700; color: {PRIMARY_DARK};")
        self.tree_working = QTreeWidget()
        self.tree_working.setHeaderLabels(["Copie de travail"])
        self.tree_working.itemDoubleClicked.connect(self._on_working_double_clicked)
        self.tree_working.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_working.customContextMenuRequested.connect(self._show_working_context_menu)
        layout_w.addWidget(self.label_working)
        layout_w.addWidget(self.tree_working)
        bottom_splitter.addWidget(self.panel_working)

        self.panel_b = QWidget()
        layout_b = QVBoxLayout(self.panel_b)
        layout_b.setContentsMargins(4, 2, 4, 2)
        self.label_b = QLabel(t("panel.scenario_b"))
        self.label_b.setStyleSheet(f"font-weight: 700; color: {NAVY};")
        self.tree_b = QTreeWidget()
        self.tree_b.setHeaderLabels(["Scenario B"])
        self.tree_b.itemDoubleClicked.connect(lambda item, col: self._on_source_double_clicked(item, self._root_b))
        self.tree_b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_b.customContextMenuRequested.connect(
            lambda pos: self._show_source_context_menu(self.tree_b, pos, self._root_b))
        layout_b.addWidget(self.label_b)
        layout_b.addWidget(self.tree_b)
        bottom_splitter.addWidget(self.panel_b)
        self.panel_b.setVisible(False)

        bottom_splitter.setSizes([320, 320, 320])
        self.main_splitter.addWidget(bottom_splitter)

        # Le haut (onglets) prend la grande majorite de la hauteur ; le bas reste une
        # bande de navigation compacte, redimensionnable a la souris si besoin.
        self.main_splitter.setSizes([650, 220])
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.setCentralWidget(self.main_splitter)

    @property
    def _root_a(self) -> Optional[Path]:
        return self.workspace.source_a_root if self.workspace else None

    @property
    def _root_b(self) -> Optional[Path]:
        return self.workspace.source_b_root if self.workspace else None

    # ------------------------------------------------------------------
    # Nouveau projet (creation du workspace)
    # ------------------------------------------------------------------

    def new_project_dialog(self):
        dialog = NewProjectDialog(self)
        if dialog.exec() != NewProjectDialog.DialogCode.Accepted:
            return

        progress = QProgressDialog("Copie du scenario de base en cours...", None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            self.workspace = open_workspace(dialog.source_a_path, dialog.dest_path, dialog.source_b_path)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("err.title"), f"{t('err.create_project')} :\n{e}")
            return
        progress.close()

        self._highlights = {}
        self._refresh_all_trees()
        self.tabs.clear()

        self._remember_current_project()

        mode = t("status.mode_merge") if self.workspace.is_merge_mode else t("status.mode_simple")
        self.statusBar().showMessage(
            t("status.project_opened", mode=mode, path=self.workspace.working_root)
        )

    def _remember_current_project(self):
        if not self.workspace:
            return
        record = ProjectRecord(
            source_a=str(self.workspace.source_a_root),
            working=str(self.workspace.working_root),
            source_b=str(self.workspace.source_b_root) if self.workspace.source_b_root else None,
        )
        project_store.add_recent_project(record)

    def show_startup_dialog(self, auto_at_launch: bool = False):
        projects = project_store.load_recent_projects()
        if not projects:
            if not auto_at_launch:
                QMessageBox.information(self, t("recent.none_title"), t("recent.none_msg"))
            return

        dialog = StartupDialog(projects, self)
        if dialog.exec() != StartupDialog.DialogCode.Accepted:
            if dialog.project_to_remove:
                project_store.remove_project(dialog.project_to_remove.working)
            return

        if dialog.project_to_remove:
            project_store.remove_project(dialog.project_to_remove.working)

        if dialog.want_new_project:
            self.new_project_dialog()
            return

        if dialog.chosen_project:
            self.open_existing_project(dialog.chosen_project)

    def open_existing_project(self, record: ProjectRecord):
        source_a = Path(record.source_a)
        working = Path(record.working)
        source_b = Path(record.source_b) if record.source_b else None

        try:
            self.workspace = load_existing_workspace(source_a, working, source_b)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"),
                                  f"{t('recent.resume_error')} :\n{e}\n\n{t('recent.resume_error_hint')}")
            return

        self._highlights = {}
        self._refresh_all_trees()
        self.tabs.clear()
        self._remember_current_project()  # remonte ce projet en tete de la liste recente

        mode = t("status.mode_merge") if self.workspace.is_merge_mode else t("status.mode_simple")
        self.statusBar().showMessage(
            t("status.project_resumed", mode=mode, path=self.workspace.working_root)
        )

    def _refresh_all_trees(self):
        if not self.workspace:
            return
        self.label_a.setText(t("panel.scenario_a_named", name=self.workspace.source_a_root.name))
        self._populate_tree(self.tree_a, self.workspace.source_a)

        self.label_working.setText(t("panel.working_copy_named", name=self.workspace.working_root.name))
        self._populate_tree(self.tree_working, self.workspace.working)

        if self.workspace.is_merge_mode:
            self.panel_b.setVisible(True)
            self.label_b.setText(t("panel.scenario_b_named", name=self.workspace.source_b_root.name))
            self._populate_tree(self.tree_b, self.workspace.source_b)
        else:
            self.panel_b.setVisible(False)

        self._refresh_scenario_b_menu_text()

    def _populate_tree(self, tree: QTreeWidget, scenario: Scenario):
        """Reconstruit l'arborescence EXACTE du disque (comme un explorateur de
        fichiers classique), plutot qu'une vue categorisee -- plus previsible et plus
        facile a comparer visuellement entre Scenario A, B et la copie de travail,
        puisque les trois montrent la meme structure que sur le disque."""
        tree.clear()
        root_item = QTreeWidgetItem([scenario.root_path.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, ("folder", scenario.root_path))
        tree.addTopLevelItem(root_item)
        self._build_real_tree(root_item, scenario.root_path)
        root_item.setExpanded(True)

    def _build_real_tree(self, parent_item: QTreeWidgetItem, folder: Path):
        try:
            entries = list(folder.iterdir())
        except OSError:
            return
        dirs = sorted((e for e in entries if e.is_dir()), key=lambda p: p.name.lower())
        files = sorted((e for e in entries if e.is_file()), key=lambda p: p.name.lower())

        for d in dirs:
            item = QTreeWidgetItem([d.name])
            item.setData(0, Qt.ItemDataRole.UserRole, ("folder", d))
            parent_item.addChild(item)
            self._build_real_tree(item, d)

        for f in files:
            item = QTreeWidgetItem([f.name])
            item.setData(0, Qt.ItemDataRole.UserRole, ("file", f))
            parent_item.addChild(item)

    # ------------------------------------------------------------------
    # Copier depuis une source (A ou B) vers la copie de travail
    # ------------------------------------------------------------------

    def _show_source_context_menu(self, tree: QTreeWidget, pos, source_root: Optional[Path]):
        if not self.workspace or not source_root:
            return
        item = tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        source_label = "Scenario A" if source_root == self.workspace.source_a_root else "Scenario B"
        menu = QMenu(self)
        merge_enabled = settings.get_merge_enabled()

        if data[0] == "file":
            path: Path = data[1]
            action_merge = menu.addAction(t("file.merge_action", name=path.name))
            if not merge_enabled:
                action_merge.setEnabled(False)
                action_merge.setToolTip(t("merge.disabled_msg"))
            action_dup = menu.addAction(t("file.duplicate_action", name=path.name))
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen == action_merge and merge_enabled:
                self._copy_into_working(path, source_root, source_label)
            elif chosen == action_dup:
                self._duplicate_file_into_working(path, source_root, source_label)

        elif data[0] == "folder":
            folder: Path = data[1]
            if not folder.exists():
                return
            action = menu.addAction(t("folder.merge_action", name=folder.name))
            if not merge_enabled:
                action.setEnabled(False)
                action.setToolTip(t("merge.disabled_msg"))
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen == action and merge_enabled:
                self._merge_folder_into_working_ui(folder, source_root, source_label)

    def _show_working_context_menu(self, pos):
        if not self.workspace:
            return
        item = self.tree_working.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)

        if data[0] == "file":
            path: Path = data[1]
            action_delete = menu.addAction(t("file.delete_action", name=path.name))
            chosen = menu.exec(self.tree_working.viewport().mapToGlobal(pos))
            if chosen == action_delete:
                self._delete_working_file(path)

        elif data[0] == "folder":
            folder: Path = data[1]
            action_delete = menu.addAction(t("folder.delete_action", name=folder.name))
            chosen = menu.exec(self.tree_working.viewport().mapToGlobal(pos))
            if chosen == action_delete:
                self._delete_working_folder(folder)

    def _delete_working_file(self, path: Path):
        confirm = QMessageBox.question(
            self, t("backup.confirm_delete_title"), t("delete.confirm_file_msg", name=path.name))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            prior = capture_file(path)
            from core.fsutil import clear_readonly
            clear_readonly(path)
            path.unlink()
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("delete.error"), str(e))
            return

        self._push_workspace_undo(FileStateUndo(path, prior, t("wsundo.delete_file", name=path.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.removeTab(i)
                break

        self._populate_tree(self.tree_working, self.workspace.working)
        self.statusBar().showMessage(t("status.file_deleted", name=path.name))

    def _delete_working_folder(self, folder: Path):
        confirm = QMessageBox.question(
            self, t("backup.confirm_delete_title"), t("delete.confirm_folder_msg", name=folder.name))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            existed, prior_files = capture_folder(folder)
            from core.fsutil import clear_readonly
            clear_readonly(folder)
            shutil.rmtree(folder)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("delete.error"), str(e))
            return

        self._push_workspace_undo(
            FolderStateUndo(folder, existed, prior_files, t("wsundo.delete_folder", name=folder.name)))

        folder_str = str(folder)
        for i in reversed(range(self.tabs.count())):
            tooltip = self.tabs.tabToolTip(i)
            if tooltip and tooltip.startswith(folder_str):
                self.tabs.removeTab(i)

        self._populate_tree(self.tree_working, self.workspace.working)
        self.statusBar().showMessage(t("status.folder_deleted", name=folder.name))

    def _merge_folder_into_working_ui(self, folder: Path, source_root: Path, source_label: str):
        nb_files = sum(1 for _ in folder.rglob('*') if _.is_file())
        if nb_files == 0:
            QMessageBox.information(self, t("merge.empty_folder_title"), t("merge.empty_folder_msg"))
            return
        confirm = QMessageBox.question(
            self, t("merge.confirm_title"),
            t("merge.confirm_folder_msg", n=nb_files, folder=folder.name)
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        rel = folder.relative_to(source_root)
        working_folder = self.workspace.working_root / rel
        existed_before, prior_files = capture_folder(working_folder)

        progress = QProgressDialog(f"Fusion de {nb_files} fichier(s)...", None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            highlights, id_conflicts, csv_reports = merge_folder_into_working(
                self.workspace, folder, source_root, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("err.title"), f"{t('merge.folder_error')} :\n{e}")
            return
        progress.close()

        self._push_workspace_undo(
            FolderStateUndo(working_folder, existed_before, prior_files,
                             t("wsundo.merge_folder", name=folder.name)))

        self._highlights.update(highlights)
        self._populate_tree(self.tree_working, self.workspace.working)

        for path_touched in list(highlights.keys()) + list(csv_reports.keys()):
            for i in range(self.tabs.count()):
                if self.tabs.tabToolTip(i) == str(path_touched):
                    self.tabs.removeTab(i)

        if id_conflicts:
            details = "\n".join(
                f"- {c.kind} [{c.identity}] : \"{c.base_name}\" (copie de travail) "
                f"vs \"{c.conflicting_name}\" ({c.conflicting_source})"
                for c in id_conflicts[:20]
            )
            more = t("merge.id_conflicts_more", n=len(id_conflicts) - 20) if len(id_conflicts) > 20 else ""
            QMessageBox.warning(
                self, t("merge.id_conflicts_title"),
                t("merge.id_conflicts_folder_msg", n=len(id_conflicts), details=details, more=more)
            )

        n_csv_rows = sum(len(r) for r in csv_reports.values())
        self.statusBar().showMessage(
            t("status.folder_merged", n=nb_files, ecf=len(highlights), csv=len(csv_reports),
              rows=n_csv_rows, conflicts=len(id_conflicts))
        )

    def _copy_into_working(self, path: Path, source_root: Path, source_label: str):
        rel = path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, highlight, id_conflicts, csv_report = merge_file_into_working(
                self.workspace, path, source_root, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('merge.file_error', file=path.name)} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.merge_file", name=dest.name)))

        if highlight:
            self._highlights[dest] = highlight
        else:
            self._highlights.pop(dest, None)

        self._populate_tree(self.tree_working, self.workspace.working)

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if id_conflicts:
            details = "\n".join(
                f"- {c.kind} [{c.identity}] : \"{c.base_name}\" (copie de travail) "
                f"vs \"{c.conflicting_name}\" ({c.conflicting_source})"
                for c in id_conflicts
            )
            QMessageBox.warning(
                self, t("merge.id_conflicts_title"),
                t("merge.id_conflicts_file_msg", n=len(id_conflicts), details=details)
            )

        if csv_report is not None:
            if csv_report:
                self.statusBar().showMessage(
                    t("status.csv_merged_rows", file=dest.name, n=len(csv_report))
                )
            else:
                self.statusBar().showMessage(t("status.csv_merged_none", file=dest.name))
        elif highlight and (highlight.new_blocks or highlight.changed_blocks):
            n_new = len(highlight.new_blocks)
            n_changed = len(highlight.changed_blocks)
            msg = t("status.merged_working", file=dest.name, new=n_new, changed=n_changed)
            if id_conflicts:
                msg += t("status.id_conflicts_suffix", n=len(id_conflicts))
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().showMessage(t("status.copied_to_working", dest=dest))

    def _duplicate_file_into_working(self, path: Path, source_root: Path, source_label: str):
        """Copie un fichier depuis Scenario A/B vers la copie de travail sous un
        NOUVEAU nom, comme fichier independant -- ne fusionne PAS avec un fichier de
        meme nom deja present. Utile pour garder deux versions distinctes d'un meme
        fichier (ex: comparer manuellement Templates.ecf de A et de B cote a cote)."""
        rel = path.relative_to(source_root)
        suffix_letter = "A" if source_label == "Scenario A" else "B"
        suggestion = f"{rel.stem}_{suffix_letter}{rel.suffix}"

        new_name, ok = QInputDialog.getText(
            self, t("dupfile.title"), t("dupfile.new_name_label"), text=suggestion)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()

        dest = self.workspace.working_root / rel.parent / new_name
        if dest.exists():
            QMessageBox.warning(self, t("dupfile.exists_title"), t("dupfile.exists_msg", name=new_name))
            return

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            from core.fsutil import clear_readonly
            clear_readonly(dest)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('merge.file_error', file=path.name)} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, None, t("wsundo.duplicate_file", name=new_name)))
        self._populate_tree(self.tree_working, self.workspace.working)
        self.statusBar().showMessage(t("status.file_duplicated", name=new_name))

    def _duplicate_ecf_block_dialog(self, block: EcfBlock, parent_chain: list, source_file_path: Path,
                                     source_root: Path, source_label: str):
        """Duplique un bloc en lui donnant un nouvel Id et/ou un nouveau Name, comme un
        element independant (pas une fusion) -- utile pour partir d'un bloc existant
        comme modele pour en creer un nouveau distinct (ex: variante d'un item).
        L'utilisateur choisit librement : nouvel Id, nouveau Name, les deux, ou
        abandonner l'Id pour n'identifier le nouveau bloc que par Name (certains blocs
        reels n'ont pas d'Id du tout, ex: '{ Block Name: LegacyForcefield ...}')."""
        from core.ecf.pending_conflicts import find_used_ids, suggest_free_ids

        rel = source_file_path.relative_to(source_root)
        dest_path = self.workspace.working_root / rel
        if not dest_path.exists():
            QMessageBox.warning(self, t("dup.file_missing_title"), t("dup.file_missing_msg", file=dest_path.name))
            return

        used_ids = find_used_ids([dest_path])
        suggestions = suggest_free_ids(used_ids, 5)

        dialog = DuplicateBlockDialog(block, suggestions, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        prior = capture_file(dest_path)
        annotation = None
        if settings.get_annotations_enabled():
            annotation = f"# Duplique par {settings.get_author()}"
        try:
            dest, status = duplicate_ecf_block_into_working(
                self.workspace, rel, block,
                dialog.result_new_id, dialog.result_new_name, dialog.result_remove_id,
                source_label, parent_chain=parent_chain, annotation=annotation)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('dup.block_error')} :\n{e}")
            return

        if status == 'parent_not_found':
            QMessageBox.warning(self, t("dup.parent_not_found_title"),
                                 t("dup.parent_not_found_msg", file=dest.name))
            return

        if status == 'exists':
            QMessageBox.warning(self, t("dup.already_used_title"), t("dup.already_used_msg", file=dest.name))
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.duplicate_block", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        details = []
        if dialog.result_new_id:
            details.append(f"Id={dialog.result_new_id}")
        if dialog.result_remove_id:
            details.append("Id abandonne")
        if dialog.result_new_name:
            details.append(f"Name={dialog.result_new_name}")
        self.statusBar().showMessage(t("status.block_duplicated", details=', '.join(details), file=dest.name))

    def _copy_block_into_working(self, block: EcfBlock, source_file_path: Path,
                                  source_root: Path, source_label: str):
        """Fusionne UN SEUL bloc (point 3 : mise a jour ciblee sans tout refusionner)."""
        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status, highlight = merge_block_into_working(self.workspace, rel, block, source_label)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('copy.block_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.copy_block", name=dest.name)))

        if highlight:
            self._highlights[dest] = highlight

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if status == 'conflict':
            QMessageBox.warning(
                self, t("ecf.single_block_conflict_title"),
                t("ecf.single_block_conflict_msg")
            )
            self.statusBar().showMessage(t("status.id_conflict_detected", file=dest.name))
        elif status == 'added':
            self.statusBar().showMessage(t("status.block_added", file=dest.name))
        else:
            self.statusBar().showMessage(t("status.block_merged", file=dest.name))

    def _copy_csv_row_into_working(self, row: list, source_file_path: Path,
                                    source_root: Path, source_label: str):
        """Copie UNE SEULE ligne CSV (par cle) vers le fichier correspondant de la
        copie de travail, sans toucher au reste du fichier."""
        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = merge_csv_row_into_working(self.workspace, rel, row)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('copy.row_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.copy_row", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        key = row[0] if row else "?"
        if status == 'added':
            self.statusBar().showMessage(t("status.row_added", key=key, file=dest.name))
        elif status == 'merged':
            self.statusBar().showMessage(t("status.row_merged", key=key, file=dest.name))
        else:
            self.statusBar().showMessage(t("status.row_unchanged", key=key, file=dest.name))

    def _duplicate_csv_row_dialog(self, row: list, source_file_path: Path,
                                   source_root: Path, source_label: str):
        """Duplique une ligne CSV avec une NOUVELLE cle, comme un enregistrement
        independant (pas une fusion) -- utile pour partir d'une ligne existante comme
        modele pour en creer une nouvelle."""
        rel = source_file_path.relative_to(source_root)
        old_key = row[0] if row else "?"

        new_key, ok = QInputDialog.getText(
            self, t("csv.duplicate_title"),
            t("csv.duplicate_current_key", key=old_key)
        )
        if not ok:
            return
        if not new_key.strip():
            QMessageBox.warning(self, t("dup.key_required_title"), t("dup.key_required_msg"))
            return

        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = duplicate_csv_row_into_working(self.workspace, rel, row, new_key.strip())
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('dup.row_error')} :\n{e}")
            return

        if status == 'key_exists':
            QMessageBox.warning(self, t("dup.key_exists_title"),
                                 t("dup.key_exists_msg", key=new_key.strip(), file=dest.name))
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.duplicate_row", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        self.statusBar().showMessage(t("status.row_duplicated", key=new_key.strip(), file=dest.name))

    def _copy_yaml_entry_into_working(self, entry, key_path: list, source_file_path: Path,
                                       source_root: Path, source_label: str):
        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = copy_yaml_entry_into_working(self.workspace, rel, entry, key_path)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('copy.entry_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.copy_entry", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if status == 'added_at_root':
            self.statusBar().showMessage(
                t("status.entry_copied_root", file=dest.name)
            )
        else:
            self.statusBar().showMessage(t("status.entry_copied", file=dest.name))

    def _duplicate_yaml_entry_dialog(self, entry, key_path: list, source_file_path: Path,
                                      source_root: Path, source_label: str):
        """Duplique une entree YAML avec une NOUVELLE cle/valeur, comme une entree
        independante -- utile pour partir d'une entree existante comme modele."""
        rel = source_file_path.relative_to(source_root)

        current = entry.value if (entry.key and entry.key.strip().lower() in ('name', 'id')) \
            else (entry.key or entry.value)

        new_value, ok = QInputDialog.getText(
            self, t("yaml.duplicate_title"),
            t("yaml.duplicate_current_value", value=current)
        )
        if not ok:
            return
        if not new_value.strip():
            QMessageBox.warning(self, t("dup.value_required_title"), t("dup.value_required_msg"))
            return

        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        annotation = None
        if settings.get_annotations_enabled():
            annotation = f"# Duplique par {settings.get_author()}"
        try:
            dest, status = duplicate_yaml_entry_into_working(
                self.workspace, rel, entry, key_path, new_value.strip(), annotation=annotation)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('dup.entry_error')} :\n{e}")
            return

        if status == 'key_exists':
            QMessageBox.warning(self, t("dup.value_exists_title"),
                                 t("dup.value_exists_msg", value=new_value.strip(), file=dest.name))
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.duplicate_entry", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        note = t("status.entry_duplicated_note") if status == 'added_at_root' else ""
        self.statusBar().showMessage(t("status.entry_duplicated", value=new_value.strip(), file=dest.name, note=note))

    def _translate_csv_cell_into_working(self, key: str, text: str, target_code: str, target_label: str,
                                          source_file_path: Path, source_root: Path, source_label: str):
        """Traduit une cellule d'une vue lecture seule (Scenario A/B) et applique le
        resultat directement dans la cellule correspondante (meme cle, colonne de la
        langue cible) de la copie de travail -- sans jamais ecraser une valeur deja
        presente."""
        from core import translation
        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(text, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        rel = source_file_path.relative_to(source_root)
        dest_before = self.workspace.working_root / rel
        prior = capture_file(dest_before)
        try:
            dest, status = translate_csv_cell_into_working(
                self.workspace, rel, key, target_code, target_label, translated)
            self.workspace.rescan_working()
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('trans.apply_error')} :\n{e}")
            return

        self._push_workspace_undo(FileStateUndo(dest, prior, t("wsundo.translate_cell", name=dest.name)))

        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(dest):
                self.tabs.removeTab(i)
                self.open_working_file_tab(dest)
                break

        if status == 'added':
            self.statusBar().showMessage(t("status.row_translated", key=key, lang=target_label, file=dest.name))
        elif status == 'merged':
            self.statusBar().showMessage(t("status.cell_translated", lang=target_label, key=key, file=dest.name))
        else:
            self.statusBar().showMessage(
                t("status.cell_already_has_value", key=key, lang=target_label)
            )

    # ------------------------------------------------------------------
    # Ouverture de fichiers (lecture seule pour A/B, meme vue pour l'instant sur
    # la copie de travail -- l'edition inline viendra dans une passe suivante)
    # ------------------------------------------------------------------

    def _on_source_double_clicked(self, item: QTreeWidgetItem, source_root):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "file":
            return
        source_label = "Scenario A" if source_root == self.workspace.source_a_root else "Scenario B"
        self.open_file_tab(data[1], read_only=True, source_root=source_root, source_label=source_label)

    def _on_working_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "file":
            return
        self.open_working_file_tab(data[1])

    def open_working_file_tab(self, path: Path):
        """Ouvre un fichier de la copie de travail en edition, avec la (ou les) source(s)
        A/B correspondante(s) affichee(s) cote a cote si elles existent (uniquement
        pour les .ecf pour l'instant -- les autres formats s'ouvrent seuls)."""
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.setCurrentIndex(i)
                return

        ext = path.suffix.lower()

        simple_editors = {
            '.csv': CsvEditWidget,
            '.yaml': YamlEditWidget,
            '.yml': YamlEditWidget,
            '.txt': TxtEditWidget,
        }
        if ext in simple_editors:
            try:
                widget = simple_editors[ext](path)
            except Exception as e:
                QMessageBox.critical(self, t("err.read_title"), f"{t('open.error', file=path.name)} :\n{e}")
                return
            index = self.tabs.addTab(widget, "✎ " + path.name)
            self.tabs.setTabToolTip(index, str(path))
            self.tabs.setCurrentIndex(index)
            widget.modified_changed.connect(lambda modified, w=widget: self._update_tab_title(w, modified))
            widget.saved.connect(lambda w=widget: self.statusBar().showMessage(t("status.saved", path=w.path)))
            return

        if ext != '.ecf':
            # Pas encore d'edition pour les autres formats -- vue lecture seule standard
            self.open_file_tab(path, read_only=False)
            return

        try:
            rel = path.relative_to(self.workspace.working_root)
        except ValueError:
            rel = None

        compare_sources = {}
        if rel is not None:
            candidate_a = self.workspace.source_a_root / rel
            if candidate_a.exists() and candidate_a != path:
                compare_sources["Scenario A"] = (candidate_a, self.workspace.source_a_root)
            if self.workspace.is_merge_mode:
                candidate_b = self.workspace.source_b_root / rel
                if candidate_b.exists():
                    compare_sources["Scenario B"] = (candidate_b, self.workspace.source_b_root)

        def _copy_block_cb(block, source_path, source_root, source_label):
            self._copy_block_into_working(block, source_path, source_root, source_label)

        def _duplicate_block_cb(block, parent_chain, source_path, source_root, source_label):
            self._duplicate_ecf_block_dialog(block, parent_chain, source_path, source_root, source_label)

        try:
            widget = CompareWidget(path, compare_sources, EcfViewWidget,
                                    copy_block_callback=_copy_block_cb if settings.get_merge_enabled() else None,
                                    duplicate_block_callback=_duplicate_block_cb)
        except Exception as e:
            QMessageBox.critical(self, t("err.read_title"), f"{t('open.error', file=path.name)} :\n{e}")
            return

        index = self.tabs.addTab(widget, "✎ " + path.name)
        self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)

        widget.modified_changed.connect(lambda modified, w=widget: self._update_tab_title(w, modified))
        widget.saved.connect(lambda w=widget: self.statusBar().showMessage(t("status.saved", path=w.edit_widget.path)))

    def _update_tab_title(self, widget, modified: bool):
        idx = self.tabs.indexOf(widget)
        if idx == -1:
            return
        inner = getattr(widget, 'edit_widget', widget)  # CompareWidget a un sous-widget, CsvEditWidget non
        base = inner.path.name
        self.tabs.setTabText(idx, ("✎ * " if modified else "✎ ") + base)

    def open_file_tab(self, path: Path, read_only: bool,
                       source_root: Optional[Path] = None, source_label: Optional[str] = None):
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == str(path):
                self.tabs.setCurrentIndex(i)
                return

        ext = path.suffix.lower()
        try:
            if ext == '.ecf':
                highlight = self._highlights.get(path)
                on_copy_block = None
                on_duplicate_block = None
                if read_only and source_root and source_label:
                    if settings.get_merge_enabled():
                        on_copy_block = lambda block: self._copy_block_into_working(
                            block, path, source_root, source_label)
                    on_duplicate_block = lambda block, parent_chain: self._duplicate_ecf_block_dialog(
                        block, parent_chain, path, source_root, source_label)
                widget = EcfViewWidget(path, highlight=highlight, on_copy_block=on_copy_block,
                                        copy_label=source_label, on_duplicate_block=on_duplicate_block)
            elif ext in ('.yaml', '.yml'):
                on_copy_entry = None
                on_duplicate_entry = None
                if read_only and source_root and source_label:
                    if settings.get_merge_enabled():
                        on_copy_entry = lambda entry, key_path: self._copy_yaml_entry_into_working(
                            entry, key_path, path, source_root, source_label)
                    on_duplicate_entry = lambda entry, key_path: self._duplicate_yaml_entry_dialog(
                        entry, key_path, path, source_root, source_label)
                widget = YamlEditWidget(path, editable=False, on_copy_entry=on_copy_entry,
                                        on_duplicate_entry=on_duplicate_entry)
            elif ext == '.txt':
                widget = TxtEditWidget(path, editable=False)
            elif ext == '.csv':
                on_copy_row = None
                on_translate_cell = None
                on_duplicate_row = None
                if read_only and source_root and source_label:
                    if settings.get_merge_enabled():
                        on_copy_row = lambda row: self._copy_csv_row_into_working(
                            row, path, source_root, source_label)
                    on_translate_cell = lambda key, text, code, label: self._translate_csv_cell_into_working(
                        key, text, code, label, path, source_root, source_label)
                    on_duplicate_row = lambda row: self._duplicate_csv_row_dialog(
                        row, path, source_root, source_label)
                widget = CsvEditWidget(path, editable=False, on_copy_row=on_copy_row,
                                        copy_label=source_label, on_translate_cell=on_translate_cell,
                                        on_duplicate_row=on_duplicate_row)
            else:
                QMessageBox.information(self, t("open.not_supported_title"), t("open.not_supported_msg", ext=ext))
                return
        except Exception as e:
            QMessageBox.critical(self, t("err.read_title"), f"{t('open.error', file=path.name)} :\n{e}")
            return

        prefix = "🔒 " if read_only else "✎ "
        index = self.tabs.addTab(widget, prefix + path.name)
        self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)


class DuplicateBlockDialog(QDialog):
    """Fenetre de duplication d'un bloc ECF : les deux champs (Id, Name) sont visibles
    en meme temps, avec une case a cocher pour abandonner completement l'Id (certains
    blocs reels n'ont pas d'Id du tout, identifies seulement par Name)."""

    def __init__(self, block: EcfBlock, suggestions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dup.title"))
        self.setMinimumWidth(450)

        current_id = block.get('Id')
        current_name = block.get_property('Name')

        layout = QVBoxLayout(self)
        none_placeholder = t("dup.none_placeholder")
        layout.addWidget(QLabel(
            t("dup.current_block", id=current_id or none_placeholder, name=current_name or none_placeholder) +
            "\n\n" + t("dup.instructions")
        ))

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel(t("dup.new_id")))
        self.id_edit = QLineEdit(str(suggestions[0]) if current_id and suggestions else "")
        id_row.addWidget(self.id_edit)
        layout.addLayout(id_row)
        if suggestions:
            sugg_label = QLabel(t("dup.suggestions_label", ids=', '.join(str(s) for s in suggestions)))
            sugg_label.setStyleSheet("color: gray; font-size: 11px;")
            layout.addWidget(sugg_label)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(t("dup.new_name")))
        self.name_edit = QLineEdit(current_name or "")
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        self.remove_id_checkbox = None
        if current_id:
            self.remove_id_checkbox = QCheckBox(t("dup.remove_id"))
            layout.addWidget(self.remove_id_checkbox)

        buttons = QHBoxLayout()
        btn_ok = QPushButton(t("dup.duplicate"))
        btn_ok.clicked.connect(self._on_accept)
        buttons.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        self._current_id = current_id
        self._current_name = current_name

    def _on_accept(self):
        new_id = self.id_edit.text().strip() or None
        new_name = self.name_edit.text().strip() or None
        remove_id = self.remove_id_checkbox.isChecked() if self.remove_id_checkbox else False

        if remove_id and not new_name:
            QMessageBox.warning(self, t("dup.name_required"), t("dup.name_required_msg"))
            return

        id_changed = new_id is not None and new_id != self._current_id
        name_changed = new_name is not None and new_name != self._current_name
        if not remove_id and not id_changed and not name_changed:
            QMessageBox.warning(self, t("dup.no_change"), t("dup.no_change_msg"))
            return

        self.result_new_id = new_id
        self.result_new_name = new_name
        self.result_remove_id = remove_id
        self.accept()


class EcfViewWidget(QWidget):
    """Vue en lecture d'un fichier .ecf : arbre des blocs a gauche, proprietes a droite.
    Si `highlight` est fourni (suite a une fusion), colore les blocs/proprietes ajoutes.
    Si `on_copy_block` est fourni (vue d'une source A/B), un clic droit sur un bloc
    propose de le fusionner vers la copie de travail SANS toucher au reste du fichier."""

    def __init__(self, path: Path, highlight: Optional[MergeHighlight] = None,
                 on_copy_block=None, copy_label: Optional[str] = None, on_duplicate_block=None):
        super().__init__()
        self.path = path
        self.highlight = highlight
        self.on_copy_block = on_copy_block
        self.copy_label = copy_label
        self.on_duplicate_block = on_duplicate_block
        self.doc: EcfDocument = parse_ecf_file(path)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        title = f"{path.name}  --  {sum(1 for _ in self.doc.iter_blocks())} blocs"
        if highlight and (highlight.new_blocks or highlight.changed_blocks):
            title += "   [vert = nouveau depuis la fusion, orange = complete depuis la fusion]"
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; color: gray; padding: 0px;")
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(title_label, 0)

        self.header_panel = EcfHeaderExplanationPanel(self.doc, path.name)
        layout.addWidget(self.header_panel, 0)

        # -- Barre de recherche : indispensable des que le fichier a beaucoup de blocs
        # (certains ECF reels en ont plus de 5000 au niveau racine, impossible a
        # reperer en faisant defiler manuellement une liste non triee) --
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Id / Name...")
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        btn_filter = QPushButton(t("btn.filter_by_property"))
        btn_filter.clicked.connect(self._open_property_filter)
        search_row.addWidget(btn_filter)
        layout.addLayout(search_row, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Bloc"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_block_selected)
        if self.on_copy_block or self.on_duplicate_block:
            self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._show_block_context_menu)
        splitter.addWidget(self.tree)

        self.props_table = QTableWidget(0, 2)
        self.props_table.setHorizontalHeaderLabels(["Propriete", "Valeur"])
        self.props_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.props_table)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter, 1)

        self._search_matches: list = []
        self._search_index = -1
        self._search_last_query = ""

    def _open_property_filter(self):
        dialog = PropertyFilterDialog(self.doc, on_filter_changed=self._apply_property_filter, parent=self)
        dialog.exec()

    def _apply_property_filter(self, keys):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            block = item.data(0, Qt.ItemDataRole.UserRole)
            if not keys or not isinstance(block, EcfBlock):
                item.setHidden(False)
                continue
            item.setHidden(not all(k in _block_own_keys(block) for k in keys))

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            return

        # Reconstruit la liste des correspondances seulement si la recherche a change
        if not self._search_matches or self._search_last_query != query:
            self._search_matches = []
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                block = item.data(0, Qt.ItemDataRole.UserRole)
                searchable = item.text(0).lower()
                if isinstance(block, EcfBlock):
                    for key in ('Name', 'CustomIcon', 'TemplateRoot', 'IndexName'):
                        val = block.get_property(key)
                        if val:
                            searchable += " " + val.lower()
                if query in searchable:
                    self._search_matches.append(item)
                it += 1
            self._search_index = -1
            self._search_last_query = query

        if not self._search_matches:
            self.search_status.setText("Aucun resultat")
            return

        self._search_index = (self._search_index + 1) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._on_block_selected(item, 0)
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def _show_block_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind

        # Chaine des ancetres (kind, identite) menant a ce bloc -- vide si le bloc est
        # deja au niveau racine. Indispensable pour un sous-bloc imbrique (ex: 'Mode'
        # dans un 'Item') : sans ca, une duplication le placerait a tort au niveau
        # racine, isole de son parent.
        parent_chain = []
        parent_item = item.parent()
        while parent_item is not None:
            parent_block = parent_item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(parent_block, EcfBlock):
                parent_chain.insert(0, (normalized_kind(parent_block.kind), block_identity(parent_block)))
            parent_item = parent_item.parent()

        menu = QMenu(self)
        action_merge = None
        if self.on_copy_block:
            action_merge = menu.addAction(t("ecf.merge_block_action", label=label))
        action_dup = None
        if self.on_duplicate_block:
            if parent_chain:
                action_dup = menu.addAction(t("ecf.duplicate_subblock_action"))
            else:
                action_dup = menu.addAction(t("ecf.duplicate_block_action"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action_merge and chosen == action_merge:
            self.on_copy_block(block)
        elif action_dup and chosen == action_dup:
            self.on_duplicate_block(block, parent_chain)

    def _populate_tree(self):
        group_before, label_by_block_id = self.doc.scan_section_groups_and_labels()
        self._label_by_block_id = label_by_block_id
        for index, node in enumerate(self.doc.nodes):
            if index in group_before:
                self.tree.addTopLevelItem(self._make_group_header_item(group_before[index]))
            if isinstance(node, EcfBlock):
                self.tree.addTopLevelItem(self._make_block_item(node))

    def _make_group_header_item(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([f"\u25a0 {title}"])
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(0, QBrush(QColor(PRIMARY_DARK)))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        return item

    def _make_block_item(self, block: EcfBlock) -> QTreeWidgetItem:
        ident = block_identity(block)
        label = f"{block.kind} [{ident}]" if ident else block.kind
        name = block.get_property('Name')
        if name and name != ident:
            label += f"  - {name}"
        friendly = self._label_by_block_id.get(id(block)) if hasattr(self, '_label_by_block_id') else None
        if friendly:
            label += f"   ({friendly})"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, block)

        if self.highlight:
            key = (normalized_kind(block.kind), ident)
            if key in self.highlight.new_blocks:
                item.setBackground(0, COLOR_NEW_BLOCK)
                item.setText(0, label + "  (nouveau)")
            elif key in self.highlight.changed_blocks:
                item.setBackground(0, COLOR_CHANGED_BLOCK)
                item.setText(0, label + "  (complete)")

        for child in block.children:
            if isinstance(child, EcfBlock):
                item.addChild(self._make_block_item(child))
        return item

    def _on_block_selected(self, item: QTreeWidgetItem, column: int):
        block = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(block, EcfBlock):
            return
        rows = []
        for k, v in block.pairs:
            if k:
                rows.append((k, v))
        for child in block.children:
            if isinstance(child, EcfProperty):
                for k, v in child.pairs:
                    if k:
                        rows.append((k, v))

        added_keys = set()
        if self.highlight:
            key = (normalized_kind(block.kind), block_identity(block))
            added_keys = self.highlight.changed_blocks.get(key, set())

        self.props_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(v)
            if k in added_keys:
                item_k.setBackground(COLOR_NEW_PROPERTY)
                item_v.setBackground(COLOR_NEW_PROPERTY)
            self.props_table.setItem(i, 0, item_k)
            self.props_table.setItem(i, 1, item_v)


class YamlViewWidget(QWidget):
    """Vue en lecture d'un fichier .yaml : arbre des cles/entrees."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.doc: YamlDocument = parse_yaml_file(path)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{path.name}"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Cle", "Valeur"])
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._populate_tree()
        layout.addWidget(self.tree)

    def _populate_tree(self):
        for node in self.doc.nodes:
            if isinstance(node, YamlEntry):
                self.tree.addTopLevelItem(self._make_entry_item(node))

    def _make_entry_item(self, entry: YamlEntry) -> QTreeWidgetItem:
        label = entry.key if entry.key is not None else "-"
        item = QTreeWidgetItem([label, entry.value])
        for child in entry.children:
            if isinstance(child, YamlEntry):
                item.addChild(self._make_entry_item(child))
        return item


def main():
    app = QApplication(sys.argv)
    from gui.theme import apply_theme
    apply_theme(app)
    window = MainWindow()
    window.show()

    # Propose de reprendre un projet recent des le lancement, s'il y en a
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(0, lambda: window.show_startup_dialog(auto_at_launch=True))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

```

### gui\new_project_dialog.py

```py
"""
Dialogue "Nouveau projet" : choix du scenario A (base), optionnellement du scenario B
(pour la fusion), et de l'emplacement ou creer la copie de travail modifiable.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QCheckBox, QDialogButtonBox, QFileDialog, QLabel, QMessageBox,
)

from core.i18n import t


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("newproj.title"))
        self.setMinimumWidth(520)

        self.source_a_path: Optional[Path] = None
        self.source_b_path: Optional[Path] = None
        self.dest_path: Optional[Path] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.edit_a = QLineEdit()
        self.edit_a.setPlaceholderText(t("newproj.scenario_a_placeholder"))
        btn_a = QPushButton(t("newproj.browse"))
        btn_a.clicked.connect(lambda: self._browse(self.edit_a))
        row_a = QHBoxLayout()
        row_a.addWidget(self.edit_a)
        row_a.addWidget(btn_a)
        form.addRow(t("newproj.scenario_a"), row_a)

        self.checkbox_merge = QCheckBox(t("newproj.merge_mode"))
        self.checkbox_merge.toggled.connect(self._on_merge_toggled)
        form.addRow("", self.checkbox_merge)

        self.edit_b = QLineEdit()
        self.edit_b.setPlaceholderText(t("newproj.scenario_b_placeholder"))
        self.edit_b.setEnabled(False)
        self.btn_b = QPushButton(t("newproj.browse"))
        self.btn_b.setEnabled(False)
        self.btn_b.clicked.connect(lambda: self._browse(self.edit_b))
        row_b = QHBoxLayout()
        row_b.addWidget(self.edit_b)
        row_b.addWidget(self.btn_b)
        form.addRow(t("newproj.scenario_b"), row_b)

        self.edit_dest = QLineEdit()
        self.edit_dest.setPlaceholderText(t("newproj.working_copy_placeholder"))
        btn_dest = QPushButton(t("newproj.browse"))
        btn_dest.clicked.connect(self._browse_dest)
        row_dest = QHBoxLayout()
        row_dest.addWidget(self.edit_dest)
        row_dest.addWidget(btn_dest)
        form.addRow(t("newproj.working_copy"), row_dest)

        layout.addLayout(form)

        info = QLabel(t("newproj.info"))
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setObjectName("secondaryButton")
        layout.addWidget(buttons)

    def _browse(self, target_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, t("newproj.choose_scenario_folder"))
        if folder:
            target_edit.setText(folder)

    def _browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, t("newproj.choose_parent_folder"))
        if folder:
            # On propose un sous-dossier par defaut plutot que d'ecrire directement
            # dans le dossier choisi (qui pourrait deja contenir des choses).
            suggested = str(Path(folder) / "copie_de_travail")
            self.edit_dest.setText(suggested)

    def _on_merge_toggled(self, checked: bool):
        self.edit_b.setEnabled(checked)
        self.btn_b.setEnabled(checked)

    def _on_accept(self):
        if not self.edit_a.text().strip():
            QMessageBox.warning(self, t("err.missing_field"), t("newproj.scenario_a_placeholder"))
            return
        if not self.edit_dest.text().strip():
            QMessageBox.warning(self, t("err.missing_field"), t("newproj.working_copy_placeholder"))
            return

        source_a = Path(self.edit_a.text().strip())
        dest = Path(self.edit_dest.text().strip())

        if not source_a.exists():
            QMessageBox.warning(self, t("err.invalid_path"), f"{source_a}")
            return
        if dest.exists():
            QMessageBox.warning(self, t("err.dest_exists"), f"{dest}")
            return

        source_b = None
        if self.checkbox_merge.isChecked():
            if not self.edit_b.text().strip():
                QMessageBox.warning(self, t("err.missing_field"), t("newproj.scenario_b_placeholder"))
                return
            source_b = Path(self.edit_b.text().strip())
            if not source_b.exists():
                QMessageBox.warning(self, t("err.invalid_path"), f"{source_b}")
                return

        self.source_a_path = source_a
        self.source_b_path = source_b
        self.dest_path = dest
        self.accept()

```

### gui\scenario_compare_dialog.py

```py
"""
Fenetre de comparaison de deux scenarios complets. Independante d'un projet ouvert --
accessible depuis Fichier > Comparer deux scenarios...

Affiche a la fois :
  - un arbre interactif (fichiers organises par dossier, colores par statut, clic pour
    voir le detail)
  - un bouton d'export vers un rapport texte complet (tout en un fichier)
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QSplitter, QProgressDialog, QApplication, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

from core.i18n import t
from core.scenario_diff import compare_scenarios, ScenarioDiffResult, FileDiffEntry
from gui.theme import icon, icon_size, GREEN, RED, ORANGE, TEXT_GRAY, PRIMARY_DARK


STATUS_COLORS = {
    'added': GREEN,
    'removed': RED,
    'modified': ORANGE,
    'unchanged': TEXT_GRAY,
}


class ScenarioCompareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("compare.title"))
        self.resize(1100, 700)
        self.result: Optional[ScenarioDiffResult] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.edit_a = QLineEdit()
        btn_a = QPushButton(t("newproj.browse"))
        btn_a.clicked.connect(lambda: self._browse(self.edit_a))
        row_a = QHBoxLayout()
        row_a.addWidget(self.edit_a)
        row_a.addWidget(btn_a)
        form.addRow(t("compare.scenario_a"), row_a)

        self.edit_b = QLineEdit()
        btn_b = QPushButton(t("newproj.browse"))
        btn_b.clicked.connect(lambda: self._browse(self.edit_b))
        row_b = QHBoxLayout()
        row_b.addWidget(self.edit_b)
        row_b.addWidget(btn_b)
        form.addRow(t("compare.scenario_b"), row_b)
        layout.addLayout(form)

        top_row = QHBoxLayout()
        btn_run = QPushButton(icon("fa5s.balance-scale", "#ffffff"), t("compare.run"))
        btn_run.setIconSize(icon_size())
        btn_run.clicked.connect(self._run_compare)
        top_row.addWidget(btn_run)
        self.checkbox_show_unchanged = QCheckBox(t("compare.show_unchanged"))
        self.checkbox_show_unchanged.toggled.connect(self._populate_tree)
        top_row.addWidget(self.checkbox_show_unchanged)
        top_row.addStretch()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        top_row.addWidget(self.summary_label)
        layout.addLayout(top_row)

        self.direction_label = QLabel("")
        self.direction_label.setStyleSheet(f"font-weight: 700; color: {PRIMARY_DARK}; padding: 4px 0;")
        layout.addWidget(self.direction_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Fichier"])
        self.tree.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self.tree)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setPlainText(t("compare.select_file_hint"))
        splitter.addWidget(self.detail_view)
        splitter.setSizes([450, 650])
        layout.addWidget(splitter, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("compare.export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export_report)
        bottom_row.addWidget(btn_export)
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.reject)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _browse(self, target_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, t("compare.choose_folder"))
        if folder:
            target_edit.setText(folder)

    def _run_compare(self):
        path_a_text = self.edit_a.text().strip()
        path_b_text = self.edit_b.text().strip()
        if not path_a_text or not path_b_text:
            QMessageBox.warning(self, t("err.missing_field"), t("compare.both_required"))
            return
        path_a, path_b = Path(path_a_text), Path(path_b_text)
        if not path_a.exists() or not path_b.exists():
            QMessageBox.warning(self, t("err.invalid_path"), t("compare.both_required"))
            return

        progress = QProgressDialog(t("compare.progress"), None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        def on_progress(current, total, rel_path):
            if total:
                progress.setRange(0, total)
                progress.setValue(current)
            QApplication.processEvents()

        try:
            self.result = compare_scenarios(path_a, path_b, progress_callback=on_progress)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("compare.error_title"), str(e))
            return
        progress.close()

        c = self.result.counts()
        self.summary_label.setText(t("compare.summary", added=c['added'], removed=c['removed'],
                                      modified=c['modified'], unchanged=c['unchanged']))
        self.direction_label.setText(
            t("compare.direction_label", name_a=self.result.root_a.name, name_b=self.result.root_b.name)
        )
        self._populate_tree()

    def _populate_tree(self):
        self.tree.clear()
        if not self.result:
            return
        include_unchanged = self.checkbox_show_unchanged.isChecked()
        entries = self.result.entries if include_unchanged else self.result.changed_entries()

        # Regroupe par dossier pour un arbre lisible plutot qu'une liste plate.
        folder_items = {}

        def get_folder_item(parts):
            if not parts:
                return self.tree.invisibleRootItem()
            key = tuple(parts)
            if key in folder_items:
                return folder_items[key]
            parent = get_folder_item(parts[:-1])
            item = QTreeWidgetItem(parent, [parts[-1]])
            item.setExpanded(True)
            folder_items[key] = item
            return item

        for entry in entries:
            path_parts = entry.rel_path.split('/')
            folder_parts, filename = path_parts[:-1], path_parts[-1]
            parent_item = get_folder_item(folder_parts)
            symbol = {'added': '+', 'removed': '-', 'modified': '~', 'unchanged': ' '}[entry.status]
            file_item = QTreeWidgetItem(parent_item, [f"{symbol} {filename}"])
            file_item.setData(0, Qt.ItemDataRole.UserRole, entry)
            color = QColor(STATUS_COLORS[entry.status])
            file_item.setForeground(0, QBrush(color))

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        entry: Optional[FileDiffEntry] = item.data(0, Qt.ItemDataRole.UserRole)
        if entry is None:
            return  # clic sur un dossier, pas un fichier
        if entry.status == 'unchanged':
            self.detail_view.setPlainText(entry.rel_path)
        elif entry.detail:
            self.detail_view.setPlainText(f"{entry.rel_path}\n{'=' * len(entry.rel_path)}\n\n{entry.detail}")
        else:
            self.detail_view.setPlainText(f"{entry.rel_path}\n\n{t('compare.no_detail')}")

    def _export_report(self):
        if not self.result:
            QMessageBox.warning(self, t("err.missing_field"), t("compare.both_required"))
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self, t("compare.export_title"), "rapport_comparaison.txt", "Texte (*.txt)")
        if not path_str:
            return
        report = self.result.render_report(include_unchanged=self.checkbox_show_unchanged.isChecked())
        Path(path_str).write_text(report, encoding='utf-8')
        QMessageBox.information(self, t("compare.export_done_title"),
                                 t("compare.export_done_msg", path=path_str))

```

### gui\startup_dialog.py

```py
"""
Dialogue affiche au demarrage (s'il existe des projets recents) : reprendre le dernier
projet en un clic, en choisir un autre dans la liste, ou en creer un nouveau.
"""
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QLabel,
)

from core.project_store import ProjectRecord
from core.i18n import t


class StartupDialog(QDialog):
    def __init__(self, projects: List[ProjectRecord], parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("startup.title"))
        self.setMinimumSize(560, 360)

        self.projects = projects
        self.chosen_project: Optional[ProjectRecord] = None
        self.want_new_project = False
        self.project_to_remove: Optional[ProjectRecord] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("startup.subtitle")))

        self.list_widget = QListWidget()
        for p in projects:
            item = QListWidgetItem(p.display_name())
            item.setToolTip(f"A: {p.source_a}\nTravail: {p.working}" +
                             (f"\nB: {p.source_b}" if p.source_b else ""))
            item.setData(1000, p)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self._on_open)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_open = QPushButton(t("startup.open_selected"))
        btn_open.clicked.connect(self._on_open)
        btn_row.addWidget(btn_open)

        btn_remove = QPushButton(t("startup.remove"))
        btn_remove.setObjectName("secondaryButton")
        btn_remove.clicked.connect(self._on_remove)
        btn_row.addWidget(btn_remove)

        btn_new = QPushButton(t("startup.new_project"))
        btn_new.clicked.connect(self._on_new)
        btn_row.addWidget(btn_new)

        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _on_open(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        self.chosen_project = item.data(1000)
        self.accept()

    def _on_new(self):
        self.want_new_project = True
        self.accept()

    def _on_remove(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        self.project_to_remove = item.data(1000)
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)

```

### gui\text_tools.py

```py
"""
Outils d'edition partages entre les editeurs de la copie de travail (CSV, ECF...) :
  - copier / couper / coller / supprimer sur une selection de cellules (comme un
    tableur : Ctrl+C/X/V/Suppr, compatible avec un simple copier-coller depuis/vers
    Excel puisque le format utilise des tabulations entre colonnes)
  - une petite fenetre de mise en forme BBCode (couleur + gras/italique/souligne) avec
    une palette de couleurs reduite, pour habiller une portion de texte selectionnee
    sans avoir a taper les balises a la main.
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QTableWidget, QTableWidgetItem, QDialog, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QMenu,
)
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt

from core.i18n import t


# ------------------------------------------------------------------
# Copier / couper / coller / supprimer sur un QTableWidget
# ------------------------------------------------------------------

def copy_selection(table: QTableWidget) -> None:
    """Copie la selection dans le presse-papier, format tabule (compatible Excel)."""
    ranges = table.selectedRanges()
    if not ranges:
        return
    r = ranges[0]
    lines = []
    for row in range(r.topRow(), r.bottomRow() + 1):
        cols = []
        for col in range(r.leftColumn(), r.rightColumn() + 1):
            item = table.item(row, col)
            cols.append(item.text() if item else "")
        lines.append("\t".join(cols))
    QApplication.clipboard().setText("\n".join(lines))


def cut_selection(table: QTableWidget) -> None:
    """Copie puis vide les cellules editables de la selection (ne supprime jamais une
    cellule non-editable, ex: la colonne 'Cle' d'un tableau de proprietes ECF)."""
    copy_selection(table)
    _clear_selection(table)


def delete_selection(table: QTableWidget) -> None:
    """Vide le contenu des cellules editables de la selection, sans toucher au
    presse-papier."""
    _clear_selection(table)


def _clear_selection(table: QTableWidget) -> None:
    for r in table.selectedRanges():
        for row in range(r.topRow(), r.bottomRow() + 1):
            for col in range(r.leftColumn(), r.rightColumn() + 1):
                item = table.item(row, col)
                if item and (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    item.setText("")


def paste_into_selection(table: QTableWidget, allow_new_rows: bool = True) -> None:
    """Colle le contenu du presse-papier (tabule) a partir de la cellule active,
    en ecrasant uniquement les cellules editables ; ajoute des lignes si necessaire
    et autorise (allow_new_rows)."""
    text = QApplication.clipboard().text()
    if not text:
        return
    rows_data = [line.split('\t') for line in text.split('\n')]
    if rows_data and rows_data[-1] == ['']:
        rows_data.pop()

    ranges = table.selectedRanges()
    if ranges:
        start_row, start_col = ranges[0].topRow(), ranges[0].leftColumn()
    else:
        start_row, start_col = max(table.currentRow(), 0), max(table.currentColumn(), 0)

    for i, row_vals in enumerate(rows_data):
        r = start_row + i
        if r >= table.rowCount():
            if not allow_new_rows:
                break
            table.insertRow(r)
        for j, val in enumerate(row_vals):
            c = start_col + j
            if c >= table.columnCount():
                continue
            item = table.item(r, c)
            if item is None:
                item = QTableWidgetItem("")
                table.setItem(r, c, item)
            if item.flags() & Qt.ItemFlag.ItemIsEditable:
                item.setText(val)


def install_clipboard_shortcuts(table: QTableWidget, allow_new_rows: bool = True) -> None:
    """Attache Ctrl+C / Ctrl+X / Ctrl+V / Suppr au tableau donne."""
    QShortcut(QKeySequence.StandardKey.Copy, table, activated=lambda: copy_selection(table))
    QShortcut(QKeySequence.StandardKey.Cut, table, activated=lambda: cut_selection(table))
    QShortcut(QKeySequence.StandardKey.Paste, table, activated=lambda: paste_into_selection(table, allow_new_rows))
    QShortcut(QKeySequence(Qt.Key.Key_Delete), table, activated=lambda: delete_selection(table))


def add_clipboard_menu_actions(menu: QMenu, table: QTableWidget, allow_new_rows: bool = True) -> None:
    """Ajoute Copier/Couper/Coller/Supprimer a un menu contextuel existant."""
    from core.i18n import t
    menu.addAction(t("ctx.copy"), lambda: copy_selection(table))
    menu.addAction(t("ctx.cut"), lambda: cut_selection(table))
    menu.addAction(t("ctx.paste"), lambda: paste_into_selection(table, allow_new_rows))
    menu.addAction(t("ctx.clear_content"), lambda: delete_selection(table))


def delete_selected_rows(table: QTableWidget) -> int:
    """Supprime ENTIEREMENT la ou les lignes couvertes par la selection (pas juste
    leur contenu) -- utile pour un tableau ou chaque ligne represente un enregistrement
    complet (ex: une ligne CSV). Retourne le nombre de lignes supprimees."""
    rows = set()
    for r in table.selectedRanges():
        rows.update(range(r.topRow(), r.bottomRow() + 1))
    if not rows and table.currentRow() >= 0:
        rows = {table.currentRow()}
    for row in sorted(rows, reverse=True):
        table.removeRow(row)
    return len(rows)


# ------------------------------------------------------------------
# Mise en forme BBCode (couleur + gras/italique/souligne) avec palette reduite
# ------------------------------------------------------------------

BBCODE_COLORS = [
    ("Rouge", "#FF0000"),
    ("Vert", "#00CC00"),
    ("Bleu", "#0066FF"),
    ("Jaune", "#FFCC00"),
    ("Orange", "#FF8800"),
    ("Violet", "#9900CC"),
    ("Cyan", "#00CCCC"),
    ("Rose", "#FF66CC"),
    ("Blanc", "#FFFFFF"),
    ("Gris", "#999999"),
]


class BBCodeToolDialog(QDialog):
    """Petite fenetre d'edition avec palette de couleurs et boutons de style (gras,
    italique, souligne) : selectionne du texte a la souris dans la zone d'edition,
    clique une couleur ou un style pour l'entourer des balises BBCode correspondantes."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("bbcode.title"))
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("bbcode.instructions")))

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setMinimumHeight(100)
        layout.addWidget(self.text_edit)

        style_row = QHBoxLayout()
        for label_key, tag in [("bbcode.bold", "b"), ("bbcode.italic", "i"), ("bbcode.underline", "u")]:
            btn = QPushButton(t(label_key))
            btn.clicked.connect(lambda checked, tg=tag: self._wrap_selection(f"[{tg}]", f"[/{tg}]"))
            style_row.addWidget(btn)
        style_row.addStretch()
        layout.addLayout(style_row)

        layout.addWidget(QLabel(t("bbcode.colors_label")))
        palette_row = QHBoxLayout()
        for name, hexcode in BBCODE_COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 22)
            btn.setToolTip(name)
            text_color = "#000000" if hexcode == "#FFFFFF" else "#FFFFFF"
            btn.setStyleSheet(f"background-color: {hexcode}; border: 1px solid #555; color: {text_color};")
            btn.clicked.connect(lambda checked, c=hexcode: self._wrap_selection(f"[color={c}]", "[/color]"))
            palette_row.addWidget(btn)
        palette_row.addStretch()
        layout.addLayout(palette_row)

        buttons = QHBoxLayout()
        btn_apply = QPushButton(t("bbcode.apply_to_cell"))
        btn_apply.clicked.connect(self.accept)
        buttons.addWidget(btn_apply)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def _wrap_selection(self, open_tag: str, close_tag: str):
        cursor = self.text_edit.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n')
        if not selected:
            self._flash_hint(t("bbcode.select_text_hint"))
            return
        cursor.insertText(f"{open_tag}{selected}{close_tag}")

    def _flash_hint(self, text: str):
        from PyQt6.QtWidgets import QToolTip
        from PyQt6.QtGui import QCursor
        QToolTip.showText(QCursor.pos(), text)

    def result_text(self) -> str:
        return self.text_edit.toPlainText()


def open_bbcode_tool(parent_widget, current_text: str) -> Optional[str]:
    """Ouvre la fenetre de mise en forme BBCode. Retourne le nouveau texte si
    l'utilisateur valide, sinon None."""
    dialog = BBCodeToolDialog(current_text, parent_widget)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.result_text()
    return None

```

### gui\theme.py

```py
"""
Theme visuel de l'application, inspire d'un tableau de bord admin moderne (bleu/marine,
cartes arrondies, icones vectorielles). Un seul point d'entree : apply_theme(app).

Palette extraite d'une reference visuelle fournie par l'utilisateur (capture d'ecran
d'un dashboard admin) : bleu primaire vif, fond gris-bleu tres clair, cartes blanches
a coins arrondis, accents vert/orange/rouge pour les statuts, marine fonce pour les
zones de navigation.
"""
from PyQt6.QtGui import QIcon, QFont, QFontDatabase
from PyQt6.QtCore import QSize

try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False


# ------------------------------------------------------------------
# Palette
# ------------------------------------------------------------------
PRIMARY = "#4a7dfc"
PRIMARY_DARK = "#3a63d8"
PRIMARY_DARKER = "#2f52b8"
PRIMARY_LIGHT = "#7ba3f5"
PRIMARY_BG_TINT = "#eaf0fe"

NAVY = "#131a2e"
NAVY_LIGHT = "#1c2440"

BG = "#eef1f6"
CARD_BG = "#ffffff"
BORDER = "#e2e6f0"
BORDER_STRONG = "#c9d0e0"

TEXT_DARK = "#1a1f36"
TEXT_GRAY = "#7c859c"
TEXT_ON_PRIMARY = "#ffffff"

GREEN = "#22c55e"
ORANGE = "#f5a623"
RED = "#ef4444"
RED_DARK = "#dc2626"

FONT_FAMILY = "Segoe UI"


# ------------------------------------------------------------------
# Icones (qtawesome si disponible -- degrade proprement sinon : QIcon() vide,
# les boutons gardent alors juste leur texte, rien ne casse).
# ------------------------------------------------------------------
def icon(name: str, color: str = TEXT_DARK, size: int = 16) -> QIcon:
    if not _HAS_QTA:
        return QIcon()
    try:
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()


def icon_size() -> QSize:
    return QSize(15, 15)


# ------------------------------------------------------------------
# Feuille de style Qt (QSS) globale
# ------------------------------------------------------------------
STYLESHEET = f"""
* {{
    font-family: "{FONT_FAMILY}", "Segoe UI", sans-serif;
}}

QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT_DARK};
}}

QDialog {{
    background-color: {CARD_BG};
}}

/* --- Barre de menus --- */
QMenuBar {{
    background-color: {NAVY};
    color: #ffffff;
    padding: 4px;
    font-weight: 600;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 6px;
    margin: 2px;
}}
QMenuBar::item:selected {{
    background-color: {PRIMARY};
}}
QMenu {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    color: {TEXT_DARK};
}}
QMenu::item:selected {{
    background-color: {PRIMARY_BG_TINT};
    color: {PRIMARY_DARK};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 6px 8px;
}}

/* --- Barre d'outils --- */
QToolBar {{
    background-color: {NAVY};
    border: none;
    padding: 6px;
    spacing: 6px;
}}

/* --- Barre de statut --- */
QStatusBar {{
    background-color: {CARD_BG};
    color: {TEXT_GRAY};
    border-top: 1px solid {BORDER};
    padding: 2px 8px;
}}

/* --- Boutons --- */
QPushButton {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {PRIMARY_DARK};
}}
QPushButton:pressed {{
    background-color: {PRIMARY_DARKER};
}}
QPushButton:disabled {{
    background-color: {BORDER_STRONG};
    color: {TEXT_GRAY};
}}
QPushButton:checked {{
    background-color: {PRIMARY_DARKER};
}}

/* Boutons secondaires (fond clair) -- utiliser objectName "secondaryButton" */
QPushButton#secondaryButton {{
    background-color: {CARD_BG};
    color: {TEXT_DARK};
    border: 1px solid {BORDER_STRONG};
}}
QPushButton#secondaryButton:hover {{
    background-color: {PRIMARY_BG_TINT};
    border-color: {PRIMARY};
    color: {PRIMARY_DARK};
}}
QPushButton#secondaryButton:disabled {{
    background-color: {BG};
    color: {BORDER_STRONG};
    border: 1px solid {BORDER};
}}

/* --- Champs de saisie --- */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {PRIMARY_LIGHT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {PRIMARY};
}}

/* --- Tableaux et arbres --- */
QTableWidget, QTreeWidget, QListWidget {{
    background-color: {CARD_BG};
    alternate-background-color: {PRIMARY_BG_TINT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: {BORDER};
    selection-background-color: {PRIMARY};
    selection-color: {TEXT_ON_PRIMARY};
}}
QHeaderView::section {{
    background-color: {BG};
    color: {TEXT_GRAY};
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid {BORDER};
    font-weight: 700;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 3px;
    border-radius: 4px;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
}}
QTableWidget::item:selected {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
}}

/* --- Onglets --- */
QTabWidget::pane {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    top: -1px;
}}
QTabBar::tab {{
    background-color: {BG};
    color: {TEXT_GRAY};
    padding: 8px 16px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background-color: {PRIMARY};
    color: {TEXT_ON_PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background-color: {PRIMARY_BG_TINT};
    color: {PRIMARY_DARK};
}}
QTabBar::close-button {{
    subcontrol-position: right;
}}

/* --- Cases a cocher --- */
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid {BORDER_STRONG};
    background-color: {CARD_BG};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
}}

/* --- Barres de defilement --- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PRIMARY_LIGHT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {PRIMARY_LIGHT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* --- Splitters --- */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:hover {{
    background-color: {PRIMARY_LIGHT};
}}

/* --- Progression --- */
QProgressDialog {{
    background-color: {CARD_BG};
}}
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {BG};
    text-align: center;
    height: 16px;
}}
QProgressBar::chunk {{
    background-color: {PRIMARY};
    border-radius: 7px;
}}

/* --- Info-bulles --- */
QToolTip {{
    background-color: {NAVY};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
}}

/* --- ComboBox --- */
QComboBox {{
    background-color: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 5px 10px;
}}
QComboBox:hover {{
    border-color: {PRIMARY};
}}
QComboBox QAbstractItemView {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY_BG_TINT};
    selection-color: {PRIMARY_DARK};
}}

/* --- Labels d'info secondaires (objectName "mutedLabel") --- */
QLabel#mutedLabel {{
    color: {TEXT_GRAY};
    font-size: 11px;
}}
"""


def apply_theme(app):
    """A appeler une seule fois, juste apres la creation de QApplication."""
    app.setStyleSheet(STYLESHEET)

```

### gui\txt_edit_widget.py

```py
"""
Editeur de fichier .txt (texte brut, ex: description.txt, SqlQueries.txt...). Utilise
QTextEdit nativement (copier/couper/coller/annuler deja geres par Qt), avec en plus la
traduction de la selection et l'outil de mise en forme BBCode, coherents avec les
autres editeurs de l'appli.
"""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QMenu, QMessageBox, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core import translation
from core.i18n import t
from gui.theme import icon, icon_size
from gui.csv_edit_widget import TranslationResultDialog
from gui.text_tools import open_bbcode_tool


class TxtEditWidget(QWidget):
    """Editeur/visualiseur de fichier .txt. Preserve l'encodage (BOM eventuel) et le
    style de fin de ligne (CRLF/LF) d'origine, comme les autres formats de l'appli."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, editable: bool = True):
        super().__init__()
        self.path = path
        self.editable = editable
        self._modified = False

        with open(path, 'rb') as f:
            raw = f.read()
        self._had_bom = raw.startswith(b'\xef\xbb\xbf')
        text = raw.decode('utf-8-sig')
        self._newline = '\r\n' if '\r\n' in text else '\n'

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        mode_text = t("status.editable") if editable else t("status.readonly")
        info_label = QLabel(f"{path.name}  ({mode_text})")
        info_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(info_label, 0)

        if editable:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_undo = QPushButton(icon("fa5s.undo", "#7c859c"), t("btn.undo"))
            btn_undo.setIconSize(icon_size())
            btn_undo.setObjectName("secondaryButton")
            btn_undo.clicked.connect(lambda: self.text_edit.undo())
            toolbar.addWidget(btn_undo)
            btn_save = QPushButton(icon("fa5s.save", "#ffffff"), t("btn.save"))
            btn_save.setIconSize(icon_size())
            btn_save.clicked.connect(self.save)
            toolbar.addWidget(btn_save)
            toolbar.addStretch()
            layout.addLayout(toolbar, 0)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(not editable)
        self.text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.text_edit, 1)

        self._loaded = False
        self.text_edit.textChanged.connect(self._on_text_changed)
        self._loaded = True

    def _on_text_changed(self):
        if self.editable and self._loaded:
            self._set_modified(True)

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        if not self.editable:
            return
        content = self.text_edit.toPlainText()
        if self._newline == '\r\n':
            content = content.replace('\r\n', '\n').replace('\n', '\r\n')
        with open(self.path, 'w', encoding='utf-8', newline='') as f:
            if self._had_bom:
                f.write('\ufeff')
            f.write(content)
        self._set_modified(False)
        self.saved.emit()

    def _show_context_menu(self, pos):
        menu = self.text_edit.createStandardContextMenu()

        cursor = self.text_edit.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n')

        lang_actions = {}
        action_bbcode = None
        if self.editable and selected.strip():
            menu.addSeparator()
            translate_menu = menu.addMenu(t("ctx.translate_selection_to"))
            for label, code in translation.COMMON_LANGUAGES:
                a = translate_menu.addAction(label)
                lang_actions[a] = code
            action_bbcode = menu.addAction(t("ctx.bbcode"))

        chosen = menu.exec(self.text_edit.viewport().mapToGlobal(pos))

        if action_bbcode is not None and chosen == action_bbcode:
            new_text = open_bbcode_tool(self, selected)
            if new_text is not None:
                cursor.insertText(new_text)
            return

        if chosen not in lang_actions:
            return
        target_code = lang_actions[chosen]

        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(selected, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        dialog = TranslationResultDialog(selected, translated, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.accepted_replace:
            cursor.insertText(dialog.result_text())

```

### gui\wiki_viewer.py

```py
"""
Visualiseur de wiki integre a l'application : affiche les fichiers Markdown de docs/
dans une fenetre avec rendu (titres, listes, tableaux, code) via QTextBrowser.
"""
from pathlib import Path

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

from core import i18n


class WikiDialog(QDialog):
    def __init__(self, title: str, markdown_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        try:
            content = markdown_path.read_text(encoding='utf-8')
            self.browser.setMarkdown(content)
        except Exception as e:
            self.browser.setPlainText(f"Impossible de charger {markdown_path} :\n{e}")
        layout.addWidget(self.browser)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_close = QPushButton(i18n.t("btn.close"))
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)


def open_wiki(parent, title: str, base_filename: str):
    """Ouvre docs/<base_filename>_<langue>.md, choisissant la langue active
    (docs/wiki_app_fr.md ou docs/wiki_app_en.md par ex.), avec repli sur le francais si
    la traduction demandee est introuvable."""
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    lang = i18n.get_language()
    path = docs_dir / f"{base_filename}_{lang}.md"
    if not path.exists():
        path = docs_dir / f"{base_filename}_fr.md"
    dialog = WikiDialog(title, path, parent)
    dialog.exec()

```

### gui\yaml_edit_widget.py

```py
"""
Editeur de fichier .yaml (playfields Empyrion). Structure imbriquee (contrairement au
CSV/ECF plus "plats"), donc UX differente : arbre de navigation a gauche (cle + apercu
de la valeur), panneau de valeur editable a droite avec bouton "Appliquer" -- plus
adapte a une hierarchie profonde et a des valeurs parfois longues que l'edition directe
en cellule.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QLabel, QLineEdit, QPushButton, QMenu, QMessageBox, QDialog, QInputDialog, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidgetItemIterator

from core.yamllite.parser import parse_yaml_file, parse_yaml_text
from core.yamllite.model import YamlDocument, YamlEntry, create_entry, remove_entry
from core import translation, settings
from core.i18n import t
from gui.theme import icon, icon_size
from gui.csv_edit_widget import TranslationResultDialog
from gui.text_tools import open_bbcode_tool


class YamlEditWidget(QWidget):
    """Editeur/visualiseur de fichier .yaml : arbre de navigation, panneau de valeur
    editable a droite (avec bouton Appliquer), traduction et BBCode disponibles sur la
    valeur en cours d'edition."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, editable: bool = True, on_copy_entry=None, on_duplicate_entry=None):
        super().__init__()
        self.path = path
        self.editable = editable
        self.on_copy_entry = on_copy_entry
        self.on_duplicate_entry = on_duplicate_entry
        self.doc: YamlDocument = parse_yaml_file(path)
        self._modified = False
        self._current_entry: Optional[YamlEntry] = None
        self._undo_stack: list = []
        self._undo_max = 20

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        mode_text = t("status.editable") if editable else t("status.readonly")
        info_label = QLabel(f"{path.name}  ({mode_text})")
        info_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(info_label, 0)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel(t("label.search")))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cle ou valeur...")
        self.search_box.returnPressed.connect(self._search_next)
        search_row.addWidget(self.search_box)
        self.search_status = QLabel("")
        search_row.addWidget(self.search_status)
        layout.addLayout(search_row, 0)

        if editable:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_add = QPushButton(icon("fa5s.plus", "#ffffff"), t("btn.add_entry"))
            btn_add.setIconSize(icon_size())
            btn_add.clicked.connect(self._add_entry_dialog)
            toolbar.addWidget(btn_add)
            btn_del = QPushButton(icon("fa5s.trash-alt", "#4a7dfc"), t("btn.delete_selected_entry"))
            btn_del.setIconSize(icon_size())
            btn_del.setObjectName("secondaryButton")
            btn_del.clicked.connect(self._delete_selected_entry)
            toolbar.addWidget(btn_del)
            self.btn_undo = QPushButton(icon("fa5s.undo", "#7c859c"), t("btn.undo"))
            self.btn_undo.setIconSize(icon_size())
            self.btn_undo.setObjectName("secondaryButton")
            self.btn_undo.clicked.connect(self.undo)
            self.btn_undo.setEnabled(False)
            toolbar.addWidget(self.btn_undo)
            btn_save = QPushButton(icon("fa5s.save", "#ffffff"), t("btn.save"))
            btn_save.setIconSize(icon_size())
            btn_save.clicked.connect(self.save)
            toolbar.addWidget(btn_save)
            toolbar.addStretch()
            layout.addLayout(toolbar, 0)
            from PyQt6.QtGui import QKeySequence, QShortcut
            QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Cle", "Apercu"])
        self._populate_tree()
        self.tree.itemClicked.connect(self._on_entry_selected)
        if self.on_copy_entry or self.on_duplicate_entry:
            self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        splitter.addWidget(self.tree)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel(t("label.value")))
        self.value_edit = QTextEdit()
        self.value_edit.setEnabled(False)
        self.value_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.value_edit.customContextMenuRequested.connect(self._show_value_context_menu)
        right_layout.addWidget(self.value_edit)
        if editable:
            btn_apply = QPushButton(t("btn.apply_value"))
            btn_apply.clicked.connect(self._apply_value)
            right_layout.addWidget(btn_apply)
        splitter.addWidget(right)

        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

        self._search_matches = []
        self._search_index = -1
        self._search_last_query = ""

    def _set_modified(self, value: bool):
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def save(self):
        if not self.editable:
            return
        # Applique d'abord toute edition en cours dans la boite de valeur qui n'aurait
        # pas ete explicitement validee via "Appliquer cette valeur" -- sinon un clic
        # direct sur Enregistrer semble ne rien faire (le texte tape reste dans la
        # boite mais n'a jamais atteint le document), et le texte revient a l'original
        # des qu'on change de ligne. Enregistrer doit toujours capturer ce qui est
        # visible a l'ecran, pas seulement ce qui a deja ete explicitement applique.
        self._apply_value()
        try:
            from core.fsutil import clear_readonly
            clear_readonly(self.path)
            with open(self.path, 'w', encoding='utf-8', newline='') as f:
                f.write(self.doc.render())
        except OSError as e:
            QMessageBox.critical(self, t("save.error_title"),
                                  t("save.error_msg", name=self.path.name, error=str(e)))
            return
        self._set_modified(False)
        self.saved.emit()

    def _snapshot_undo(self):
        """A appeler AVANT toute modification -- sauvegarde l'etat actuel du document
        (texte serialise) pour pouvoir l'annuler."""
        self._undo_stack.append(self.doc.render())
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self.btn_undo.setEnabled(True)

    def undo(self):
        if not self._undo_stack:
            return
        previous_text = self._undo_stack.pop()
        self.doc = parse_yaml_text(previous_text)
        self._current_entry = None
        self.value_edit.clear()
        self.value_edit.setEnabled(False)
        self._populate_tree()
        self._set_modified(True)
        if not self._undo_stack:
            self.btn_undo.setEnabled(False)

    def _populate_tree(self):
        self.tree.clear()
        for node in self.doc.nodes:
            if isinstance(node, YamlEntry):
                self.tree.addTopLevelItem(self._make_item(node))

    def _make_item(self, entry: YamlEntry) -> QTreeWidgetItem:
        label = entry.key if entry.key is not None else ("- " + (entry.value[:30] if entry.value else ""))
        preview = entry.value[:60] if entry.value else ""
        item = QTreeWidgetItem([label or "", preview])
        item.setData(0, Qt.ItemDataRole.UserRole, entry)
        for child in entry.children:
            if isinstance(child, YamlEntry):
                item.addChild(self._make_item(child))
        return item

    def _on_entry_selected(self, item: QTreeWidgetItem, column: int):
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(entry, YamlEntry):
            return
        # Applique d'abord toute edition en attente sur l'entree PRECEDENTE avant de
        # changer de selection -- sinon un texte tape mais jamais explicitement
        # "Applique" est silencieusement perdu des qu'on clique une autre ligne.
        if self.editable and self._current_entry is not None and self._current_entry is not entry:
            self._apply_value()
        self._current_entry = entry
        self.value_edit.blockSignals(True)
        self.value_edit.setPlainText(entry.value)
        self.value_edit.blockSignals(False)
        self.value_edit.setEnabled(self.editable)

    def _get_key_path_for_item(self, item: QTreeWidgetItem) -> list:
        """Chemin des cles ancetres (PAS l'entree elle-meme) menant a cet item -- pour
        savoir ou la reinserer au meme endroit dans un autre document (copie de
        travail)."""
        path = []
        parent = item.parent()
        while parent is not None:
            entry = parent.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(entry, YamlEntry) and entry.key:
                path.insert(0, entry.key)
            parent = parent.parent()
        return path

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(entry, YamlEntry):
            return
        key_path = self._get_key_path_for_item(item)
        label = entry.key or (entry.value[:30] if entry.value else "?")

        menu = QMenu(self)
        action_copy = None
        if self.on_copy_entry:
            action_copy = menu.addAction(t("yaml.copy_entry_action", label=label))
        action_dup = None
        if self.on_duplicate_entry:
            action_dup = menu.addAction(t("yaml.duplicate_action"))

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action_copy and chosen == action_copy:
            self.on_copy_entry(entry, key_path)
        elif action_dup and chosen == action_dup:
            self.on_duplicate_entry(entry, key_path)

    def _refresh_current_item_preview(self):
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, Qt.ItemDataRole.UserRole) is self._current_entry:
                item.setText(1, self._current_entry.value[:60] if self._current_entry.value else "")
                return
            it += 1

    def _apply_value(self):
        if not self._current_entry:
            return
        new_value = self.value_edit.toPlainText()
        if new_value != self._current_entry.value:
            self._snapshot_undo()
            old_value = self._current_entry.value
            self._current_entry.set_own_value(new_value)
            if settings.get_annotations_enabled():
                author = settings.get_author()
                note = f"# original: {old_value} -- Mod par {author}"
                if self._current_entry.comment:
                    self._current_entry.comment = self._current_entry.comment + "  " + note
                else:
                    self._current_entry.comment = note
                self._current_entry.dirty = True
            self._set_modified(True)
            self._refresh_current_item_preview()

    def _search_next(self):
        query = self.search_box.text().strip().lower()
        if not query:
            return
        if not self._search_matches or self._search_last_query != query:
            self._search_matches = []
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                entry = item.data(0, Qt.ItemDataRole.UserRole)
                searchable = (item.text(0) + " " + item.text(1)).lower()
                if isinstance(entry, YamlEntry) and entry.value:
                    searchable += " " + entry.value.lower()
                if query in searchable:
                    self._search_matches.append(item)
                it += 1
            self._search_index = -1
            self._search_last_query = query

        if not self._search_matches:
            self.search_status.setText("Aucun resultat")
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._on_entry_selected(item, 0)
        self.search_status.setText(f"{self._search_index + 1} / {len(self._search_matches)}")

    def _add_entry_dialog(self):
        key, ok = QInputDialog.getText(self, t("yaml.add_entry_title"), t("yaml.key_label"))
        if not ok:
            return
        value, ok = QInputDialog.getText(self, t("yaml.add_entry_title"), t("yaml.value_label"))
        if not ok:
            return

        parent_entry = self._current_entry
        target_list = parent_entry.children if parent_entry else self.doc.nodes
        indent = (parent_entry.indent + "  ") if parent_entry else ""
        self._snapshot_undo()
        new_entry = create_entry(key.strip() or None, value.strip(), indent=indent)
        if settings.get_annotations_enabled():
            author = settings.get_author()
            new_entry.comment = f"# Ajoute par {author}"
        target_list.append(new_entry)
        self._set_modified(True)
        self._populate_tree()

    def _delete_selected_entry(self):
        if not self._current_entry:
            QMessageBox.information(self, t("yaml.no_selection_title"), t("yaml.no_selection_msg"))
            return
        confirm = QMessageBox.question(self, t("merge.confirm_title"),
                                        t("yaml.confirm_delete", name=self._current_entry.key or self._current_entry.value))
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._snapshot_undo()
        remove_entry(self.doc.nodes, self._current_entry)
        self._current_entry = None
        self.value_edit.clear()
        self.value_edit.setEnabled(False)
        self._set_modified(True)
        self._populate_tree()

    def _show_value_context_menu(self, pos):
        menu = self.value_edit.createStandardContextMenu()
        if not self.editable or not self._current_entry:
            menu.exec(self.value_edit.viewport().mapToGlobal(pos))
            return

        cursor = self.value_edit.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n')

        lang_actions = {}
        action_bbcode = None
        if selected.strip():
            menu.addSeparator()
            translate_menu = menu.addMenu(t("ctx.translate_selection_to"))
            for label, code in translation.COMMON_LANGUAGES:
                a = translate_menu.addAction(label)
                lang_actions[a] = code
            action_bbcode = menu.addAction(t("ctx.bbcode"))

        chosen = menu.exec(self.value_edit.viewport().mapToGlobal(pos))

        if action_bbcode is not None and chosen == action_bbcode:
            new_text = open_bbcode_tool(self, selected)
            if new_text is not None:
                cursor.insertText(new_text)
            return

        if chosen not in lang_actions:
            return
        target_code = lang_actions[chosen]

        if not translation.is_available():
            QMessageBox.warning(self, t("trans.unavailable_title"), t("trans.unavailable_msg"))
            return
        try:
            translated = translation.translate_text(selected, target=target_code)
        except Exception as e:
            QMessageBox.critical(self, t("trans.error_title"), t("trans.error_msg", error=e))
            return

        dialog = TranslationResultDialog(selected, translated, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.accepted_replace:
            cursor.insertText(dialog.result_text())

```

### merge_ecf.py

```py
"""
Fusionne plusieurs fichiers .ecf selon un ordre de priorite (la premiere source citee
gagne en cas de conflit), et ecrit le resultat dans un nouveau fichier.

UTILISATION :
    python merge_ecf.py sortie.ecf source1.ecf source2.ecf source3.ecf ...
    python merge_ecf.py sortie.ecf source1.ecf source2.ecf --mode properties

    source1.ecf = la plus prioritaire (gagne les conflits)
    source2.ecf, source3.ecf, ... = par ordre de priorite decroissante

MODES :
    block      (par defaut) : en cas de conflit, le bloc ENTIER vient de la source
               la plus prioritaire qui le possede. Le plus sur.
    properties : fusion propriete par propriete -- une propriete manquante dans la
               source prioritaire est completee depuis une source moins prioritaire.
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "merge.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/merge.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file
from core.ecf.merge import merge_documents, format_report


def main():
    args = sys.argv[1:]
    mode = 'block'
    if '--mode' in args:
        idx = args.index('--mode')
        mode = args[idx + 1]
        del args[idx:idx + 2]

    if len(args) < 3:
        print(__doc__)
        sys.exit(1)

    output_path = Path(args[0])
    source_paths = [Path(p) for p in args[1:]]

    for p in source_paths:
        if not p.exists():
            print(f"ERREUR : fichier introuvable : {p}")
            sys.exit(1)

    print(f"Fusion de {len(source_paths)} source(s), mode='{mode}' :")
    for i, p in enumerate(source_paths):
        rank = "priorite la plus haute" if i == 0 else f"priorite #{i + 1}"
        print(f"  {i + 1}. {p.name}  ({rank})")
    print()

    sources = [(p.name, parse_ecf_file(p)) for p in source_paths]
    result = merge_documents(sources, mode=mode)

    print("=" * 60)
    print("RAPPORT DE FUSION")
    print("=" * 60)
    print(format_report(result))
    print()

    if output_path.exists():
        confirm = input(f"{output_path} existe deja. Ecraser ? (o/N) ")
        if confirm.lower() != 'o':
            print("Annule.")
            return
    else:
        confirm = input(f"Ecrire le resultat dans {output_path} ? (o/N) ")
        if confirm.lower() != 'o':
            print("Annule.")
            return

    rendered = result.document.render()
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        f.write(rendered)

    print(f"Fusion ecrite : {output_path}")


if __name__ == "__main__":
    main()

```

### Qwen.py

```py
from pathlib import Path

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "node_modules",
}

EXTENSIONS = {".py", ".txt", ".md", ".toml", ".cfg", ".ini", ".yml", ".yaml"}

output_file = Path("bundle.md")

with output_file.open("w", encoding="utf-8") as out:
    out.write("# Bundle du projet\n\n")

    out.write("## Arborescence\n\n")
    out.write("```text\n")

    for path in sorted(Path(".").rglob("*")):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        if path.is_file():
            out.write(f"{path}\n")

    out.write("```\n\n")

    out.write("## Fichiers\n\n")

    for path in sorted(Path(".").rglob("*")):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue

        if not path.is_file():
            continue

        if path.suffix not in EXTENSIONS:
            continue

        out.write(f"### {path}\n\n")

        ext = path.suffix.replace(".", "")

        out.write(f"```{ext}\n")

        try:
            content = path.read_text(encoding="utf-8")
            out.write(content)
        except UnicodeDecodeError:
            out.write("# Impossible de lire ce fichier automatiquement.")

        out.write("\n```\n\n")

print(f"Fichier généré : {output_file.resolve()}")
```

### requirements.txt

```txt
PyQt6
deep-translator
qtawesome

```

### run_gui.py

```py
"""
Lance l'interface graphique de l'editeur de scenario Empyrion.

UTILISATION :
    python run_gui.py
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "scanner.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver le dossier 'core'.")
    sys.exit(1)

from gui.main_window import main

if __name__ == "__main__":
    main()

```

### test_ecf_roundtrip.py

```py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.ecf.parser import parse_ecf_file

SRC = "/mnt/user-data/uploads/Containers.ecf"


def main():
    with open(SRC, 'rb') as f:
        original_bytes = f.read()

    doc = parse_ecf_file(SRC)
    rendered = doc.render()
    rendered_bytes = rendered.encode('utf-8')

    print(f"Taille originale : {len(original_bytes)} octets")
    print(f"Taille rendue    : {len(rendered_bytes)} octets")

    if original_bytes == rendered_bytes:
        print("\n✓✓✓ ROUND-TRIP PARFAIT : le fichier reproduit est BYTE POUR BYTE identique. ✓✓✓")
    else:
        print("\n✗ DIFFERENCE DETECTEE. Analyse...")
        orig_lines = original_bytes.decode('utf-8').splitlines(keepends=True)
        rend_lines = rendered.splitlines(keepends=True)
        print(f"Nombre de lignes original: {len(orig_lines)}, rendu: {len(rend_lines)}")
        diffs_shown = 0
        for idx, (a, b) in enumerate(zip(orig_lines, rend_lines)):
            if a != b:
                print(f"  Ligne {idx+1} DIFFERENTE:")
                print(f"    original: {a!r}")
                print(f"    rendu   : {b!r}")
                diffs_shown += 1
                if diffs_shown >= 15:
                    print("  ... (arret apres 15 differences)")
                    break
        if len(orig_lines) != len(rend_lines):
            print(f"  Decalage de longueur : {len(orig_lines)} vs {len(rend_lines)} lignes")

    # Quelques verifications structurelles supplementaires
    print("\n-- Verifications structurelles --")
    containers = list(doc.iter_blocks('+Container')) + list(doc.iter_blocks('Container'))
    print(f"Blocs Container trouves (actifs, hors commentaires): {len(containers)}")

    c5 = doc.find_block('+Container', 'Id', '5')
    if c5:
        print(f"Container Id=5 trouve. Count={c5.get_property('Count')}, Size={c5.get_property('Size')}")
        children_items = c5.child_blocks('Child Items')
        print(f"  Sous-blocs 'Child Items': {len(children_items)}")

    # Test d'edition : modifier le Count du container 5, verifier que SEULE cette ligne change
    print("\n-- Test d'edition ciblee --")
    c5.set_property('Count', '"9,9"')
    rendered2 = doc.render()
    orig_lines2 = original_bytes.decode('utf-8').splitlines(keepends=True)
    rend_lines2 = rendered2.splitlines(keepends=True)
    changed = [(i, a, b) for i, (a, b) in enumerate(zip(orig_lines2, rend_lines2)) if a != b]
    print(f"Nombre de lignes changees apres modif du Count: {len(changed)}")
    for i, a, b in changed:
        print(f"  Ligne {i+1}: {a!r} -> {b!r}")


if __name__ == "__main__":
    main()

```

### test_scan.py

```py
"""
Test de l'Étape 0 : charge les listings fournis par David (sortie Get-ChildItem)
et vérifie que le scanner produit un inventaire cohérent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.scanner import scan_from_paths
from core.file_handlers import default_registry


def load_paths_from_listing(txt_path: str) -> list:
    """Extrait les chemins de fichiers d'un fichier de listing (sortie Get-ChildItem -Recurse
    avec Select-Object FullName). Ignore l'en-tête et les lignes de séparation."""
    paths = []
    with open(txt_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line == 'FullName' or set(line) == {'-'}:
                continue
            paths.append(line)
    return paths


def main():
    listings = [
        ("Atlantis Next", "/mnt/user-data/uploads/Atlantis_next__.txt"),
        ("Reforged Eden 2 (RE2)", "/mnt/user-data/uploads/RE2.txt"),
    ]

    registry = default_registry()
    print(f"Extensions gérées par le registre de handlers (placeholders) : {registry.supported_extensions()}")
    print()

    for label, txt_path in listings:
        print("=" * 70)
        print(f"Scan du listing : {label}")
        print("=" * 70)

        raw_paths = load_paths_from_listing(txt_path)
        print(f"({len(raw_paths)} lignes de chemins lues dans le fichier)")

        scenario = scan_from_paths(raw_paths)
        print(scenario.summary())

        # Petits contrôles de cohérence
        print()
        print("  -- Vérifications --")
        ecf_files = scenario.ecf_files()
        print(f"  Fichiers .ecf détectés dans Configuration : {len(ecf_files)}")
        for f in sorted(ecf_files, key=lambda e: e.name)[:5]:
            print(f"    - {f.name}")
        if len(ecf_files) > 5:
            print(f"    ... et {len(ecf_files) - 5} autres")

        # Exemple de playfield reconnu vs non reconnu
        complets = [p for p in scenario.playfields.values() if p.is_complete()]
        print(f"  Playfields avec au moins 1 fichier de rôle reconnu : {len(complets)}/{len(scenario.playfields)}")
        non_reconnus = [p for p in scenario.playfields.values() if not p.is_complete()]
        if non_reconnus:
            print(f"    Non reconnus (ex): {[p.name for p in non_reconnus[:5]]}")
        if complets:
            example = complets[0]
            print(f"    Exemple ({example.name}): rôles détectés = {sorted(example.role_files.keys())}, "
                  f"backups={len(example.backups)}")
        # Combien de playfields utilisent chaque convention de nommage
        from collections import Counter
        role_usage = Counter()
        for pf in scenario.playfields.values():
            for role in pf.role_files:
                role_usage[role] += 1
        print(f"  Répartition des rôles détectés : {dict(role_usage)}")

        print()


if __name__ == "__main__":
    main()

```

### transform_ecf.py

```py
"""
Applique une transformation numerique en masse a un fichier .ecf : multiplier, ajouter,
fixer, ou plafonner toutes les valeurs d'une cle de propriete donnee, sur un genre de
bloc (et eventuellement une liste d'identites precises).

UTILISATION :
    python transform_ecf.py fichier.ecf --key param1 --op multiply --amount 1.2
    python transform_ecf.py fichier.ecf --kind +Container --key Count --op set --amount 5
    python transform_ecf.py fichier.ecf --kind +Container --ids 5,6,7 --key param1 --op add --amount 0.1
    python transform_ecf.py fichier.ecf --key Health --op clamp --min 10 --max 500 --no-recursive

OPTIONS :
    --kind          Genre de bloc a cibler (ex: +Container). Par defaut : tous les genres.
    --ids           Liste d'identites (Id/Name) separees par des virgules. Par defaut : tous.
    --key           Cle de propriete a transformer (ex: param1, Count, Health). OBLIGATOIRE.
    --op            multiply | add | set | clamp | round. OBLIGATOIRE.
    --amount        Valeur pour multiply / add / set.
    --min / --max   Bornes pour clamp.
    --ndigits       Nombre de decimales pour round (defaut 2).
    --no-recursive  Ne pas chercher dans les sous-blocs (ex: Child Items).
"""
import argparse
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "transform.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/transform.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_text
from core.ecf.transform import apply_transform, TransformRule, format_report
from core.ecf.diff import diff_documents, format_diff


def main():
    p = argparse.ArgumentParser(description="Transformation en masse sur un fichier ECF")
    p.add_argument('file', type=Path)
    p.add_argument('--kind', default=None, help="Genre de bloc a cibler (ex: +Container)")
    p.add_argument('--ids', default=None, help="Identites separees par des virgules (ex: 5,6,7)")
    p.add_argument('--key', required=True, help="Cle de propriete a transformer")
    p.add_argument('--op', required=True, choices=['multiply', 'add', 'set', 'clamp', 'round'])
    p.add_argument('--amount', type=float, default=None)
    p.add_argument('--min', type=float, default=None, dest='min_value')
    p.add_argument('--max', type=float, default=None, dest='max_value')
    p.add_argument('--ndigits', type=int, default=2)
    p.add_argument('--no-recursive', action='store_true')
    args = p.parse_args()

    if not args.file.exists():
        print(f"ERREUR : fichier introuvable : {args.file}")
        sys.exit(1)

    if args.op in ('multiply', 'add', 'set') and args.amount is None:
        print(f"ERREUR : --amount est requis pour l'operation '{args.op}'")
        sys.exit(1)
    if args.op == 'clamp' and args.min_value is None and args.max_value is None:
        print("ERREUR : --min et/ou --max sont requis pour l'operation 'clamp'")
        sys.exit(1)

    with open(args.file, 'r', encoding='utf-8', newline='') as f:
        original_raw = f.read()

    doc = parse_ecf_text(original_raw, source_path=str(args.file))

    rule = TransformRule(
        property_key=args.key,
        operation=args.op,
        amount=args.amount,
        min_value=args.min_value,
        max_value=args.max_value,
        ndigits=args.ndigits,
        block_kind=args.kind,
        block_ids=args.ids.split(',') if args.ids else None,
        recursive=not args.no_recursive,
    )

    report = apply_transform(doc, rule)

    print("=" * 60)
    print("RAPPORT DE TRANSFORMATION")
    print("=" * 60)
    print(format_report(report))
    print()

    if not report.changes:
        print("Aucune valeur modifiee -- rien a sauvegarder.")
        return

    original_doc = parse_ecf_text(original_raw)
    diffs = diff_documents(original_doc, doc)
    print("=" * 60)
    print("APERCU (via le diff)")
    print("=" * 60)
    print(format_diff(diffs))
    print()

    confirm = input(f"Confirmer l'ecriture dans {args.file} ? (o/N) ")
    if confirm.lower() != 'o':
        print("Annule.")
        return

    backup_path = args.file.with_suffix(args.file.suffix + '.bak')
    if not backup_path.exists():
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            f.write(original_raw)
        print(f"Sauvegarde de l'original creee : {backup_path}")

    rendered = doc.render()
    with open(args.file, 'w', encoding='utf-8', newline='') as f:
        f.write(rendered)

    print(f"Transformation ecrite : {args.file}")


if __name__ == "__main__":
    main()

```

### verifier_parser_csv.py

```py
"""
Verifie que le handler CSV reproduit fidelement (byte pour byte) un ou plusieurs
fichiers .csv reels (Localization.csv, PDA.csv, Dialogues.csv...).

Meme demarche que verifier_parser_ecf.py et verifier_parser_yaml.py -- on ne fait
confiance a un format qu'apres l'avoir valide sur de vrais fichiers.

UTILISATION :
    python verifier_parser_csv.py "C:\\chemin\\vers\\Extras"
    python verifier_parser_csv.py fichier.csv
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "csv_handler.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/csv_handler.py")
    sys.exit(1)

from core.csv_handler import CsvHandler


def check_file(path: Path, handler: CsvHandler) -> bool:
    with open(path, 'rb') as f:
        original = f.read()

    try:
        raw = handler.load(path)
        doc = handler.parse(raw)
        rendered = handler.serialize(doc)
        original_text = original.decode('utf-8-sig')
        rendered_bytes = rendered.encode('utf-8')
        original_compare_bytes = original_text.encode('utf-8')
    except Exception as e:
        print(f"  [ERREUR PARSING] {path.name} : {e}")
        return False

    if original_compare_bytes == rendered_bytes:
        print(f"  [OK] {path.name} ({len(original)} octets, identique)")
        return True

    print(f"  [ECHEC] {path.name} : difference detectee")
    try:
        orig_lines = original_text.splitlines(keepends=True)
        rend_lines = rendered.splitlines(keepends=True)
        print(f"    Lignes original: {len(orig_lines)}, rendu: {len(rend_lines)}")
        shown = 0
        for i, (a, b) in enumerate(zip(orig_lines, rend_lines)):
            if a != b:
                print(f"    Ligne {i+1}: original={a!r}  rendu={b!r}")
                shown += 1
                if shown >= 8:
                    print("    ... (arret apres 8 differences)")
                    break
        if len(orig_lines) != len(rend_lines):
            print(f"    Decalage de longueur : {len(orig_lines)} vs {len(rend_lines)} lignes")
    except Exception as e:
        print(f"    (impossible d'afficher le detail: {e})")
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python verifier_parser_csv.py <dossier_ou_fichier.csv>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.csv"))

    if not files:
        print(f"Aucun fichier .csv trouve dans {target}")
        return

    handler = CsvHandler()
    print(f"Verification de {len(files)} fichier(s) .csv...\n")
    ok_count = 0
    for f in files:
        if check_file(f, handler):
            ok_count += 1

    print(f"\n{'=' * 50}")
    print(f"Resultat : {ok_count}/{len(files)} fichiers reproduits a l'identique")
    if ok_count == len(files):
        print("Tout est bon, le handler CSV est fiable sur ces fichiers.")
    else:
        print("Certains fichiers posent probleme -- envoie-les moi (ou le detail ci-dessus) "
              "pour que j'ajuste le handler.")


if __name__ == "__main__":
    main()

```

### verifier_parser_ecf.py

```py
"""
Verifie que le parser ECF reproduit fidelement (byte pour byte) un ou plusieurs
fichiers .ecf reels. A lancer sur TES fichiers pour valider le parser au-dela
de l'exemple deja teste (Containers.ecf).

UTILISATION :
    python verifier_parser_ecf.py "C:\chemin\vers\Content\Configuration"

    (ou un chemin vers un seul fichier .ecf)

Passe en revue chaque .ecf trouve et affiche OK / ECHEC pour chacun, avec le detail
des differences en cas d'echec.
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "ecf" / "parser.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/ecf/parser.py")
    sys.exit(1)

from core.ecf.parser import parse_ecf_file


def check_file(path: Path) -> bool:
    with open(path, 'rb') as f:
        original = f.read()

    try:
        doc = parse_ecf_file(path)
        rendered = doc.render().encode('utf-8')
    except Exception as e:
        print(f"  [ERREUR PARSING] {path.name} : {e}")
        return False

    if original == rendered:
        print(f"  [OK] {path.name} ({len(original)} octets, identique)")
        return True

    print(f"  [ECHEC] {path.name} : difference detectee")
    try:
        orig_lines = original.decode('utf-8', errors='replace').splitlines(keepends=True)
        rend_lines = rendered.decode('utf-8', errors='replace').splitlines(keepends=True)
        print(f"    Lignes original: {len(orig_lines)}, rendu: {len(rend_lines)}")
        shown = 0
        for i, (a, b) in enumerate(zip(orig_lines, rend_lines)):
            if a != b:
                print(f"    Ligne {i+1}: original={a!r}  rendu={b!r}")
                shown += 1
                if shown >= 5:
                    print("    ... (arret apres 5 differences)")
                    break
    except Exception as e:
        print(f"    (impossible d'afficher le detail: {e})")
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python verifier_parser_ecf.py <dossier_ou_fichier.ecf>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.ecf"))

    if not files:
        print(f"Aucun fichier .ecf trouve dans {target}")
        return

    print(f"Verification de {len(files)} fichier(s) .ecf...\n")
    ok_count = 0
    for f in files:
        if check_file(f):
            ok_count += 1

    print(f"\n{'=' * 50}")
    print(f"Resultat : {ok_count}/{len(files)} fichiers reproduits a l'identique")
    if ok_count == len(files):
        print("Tout est bon, le parser est fiable sur ces fichiers.")
    else:
        print("Certains fichiers posent probleme -- envoie-les moi pour que je corrige le parser.")


if __name__ == "__main__":
    main()

```

### verifier_parser_yaml.py

```py
"""
Verifie que le handler YAML reproduit fidelement (byte pour byte) un ou plusieurs
fichiers .yaml/.yml reels (playfield_static.yaml, playfield_dynamic.yaml...).

C'est l'equivalent, pour YAML, de verifier_parser_ecf.py -- meme principe : on ne fait
confiance a un format qu'apres l'avoir valide sur de vrais fichiers.

UTILISATION :
    python verifier_parser_yaml.py "C:\\chemin\\vers\\Playfields"
    python verifier_parser_yaml.py fichier.yaml
"""
import sys
from pathlib import Path

_ici = Path(__file__).resolve().parent
_candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
for _c in _candidats:
    if (_c / "core" / "yaml_handler.py").exists():
        sys.path.insert(0, str(_c))
        break
else:
    print("ERREUR : impossible de trouver core/yaml_handler.py")
    sys.exit(1)

try:
    from core.yaml_handler import YamlHandler
except ImportError as e:
    print(f"ERREUR d'import : {e}")
    sys.exit(1)


def check_file(path: Path, handler: YamlHandler) -> bool:
    with open(path, 'rb') as f:
        original = f.read()

    try:
        raw = handler.load(path)
        parsed = handler.parse(raw)
        rendered = handler.serialize(parsed).encode('utf-8')
    except Exception as e:
        print(f"  [ERREUR PARSING] {path.name} : {e}")
        return False

    if original == rendered:
        print(f"  [OK] {path.name} ({len(original)} octets, identique)")
        return True

    print(f"  [ECHEC] {path.name} : difference detectee")
    try:
        orig_lines = original.decode('utf-8', errors='replace').splitlines(keepends=True)
        rend_lines = rendered.decode('utf-8', errors='replace').splitlines(keepends=True)
        print(f"    Lignes original: {len(orig_lines)}, rendu: {len(rend_lines)}")
        shown = 0
        for i, (a, b) in enumerate(zip(orig_lines, rend_lines)):
            if a != b:
                print(f"    Ligne {i+1}: original={a!r}  rendu={b!r}")
                shown += 1
                if shown >= 8:
                    print("    ... (arret apres 8 differences)")
                    break
        if len(orig_lines) != len(rend_lines):
            print(f"    Decalage de longueur de fichier : {len(orig_lines)} vs {len(rend_lines)} lignes")
    except Exception as e:
        print(f"    (impossible d'afficher le detail: {e})")
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python verifier_parser_yaml.py <dossier_ou_fichier.yaml>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.yaml")) + sorted(target.rglob("*.yml"))

    if not files:
        print(f"Aucun fichier .yaml/.yml trouve dans {target}")
        return

    handler = YamlHandler()

    print(f"Verification de {len(files)} fichier(s) .yaml/.yml...\n")
    ok_count = 0
    for f in files:
        if check_file(f, handler):
            ok_count += 1

    print(f"\n{'=' * 50}")
    print(f"Resultat : {ok_count}/{len(files)} fichiers reproduits a l'identique")
    if ok_count == len(files):
        print("Tout est bon, le handler YAML est fiable sur ces fichiers.")
    else:
        print("Certains fichiers posent probleme -- envoie-les moi (ou juste le detail affiche "
              "ci-dessus) pour que j'ajuste le handler.")


if __name__ == "__main__":
    main()

```

