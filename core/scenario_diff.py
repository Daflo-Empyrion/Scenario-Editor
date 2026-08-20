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


def _compare_files_by_chunks(path_a: Path, path_b: Path, chunk_size: int = 65536) -> bool:
    if path_a.stat().st_size != path_b.stat().st_size:
        return False
    with open(path_a, 'rb') as fa, open(path_b, 'rb') as fb:
        while True:
            chunk_a = fa.read(chunk_size)
            chunk_b = fb.read(chunk_size)
            if chunk_a != chunk_b:
                return False
            if not chunk_a:
                return True


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
            identical = _compare_files_by_chunks(path_a, path_b)
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
