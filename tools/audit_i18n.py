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
Audit i18n du projet -- detecte TOUT ce qui peut afficher un texte non
traduit (ou traduit en dur) dans l'interface, quel que soit le langage
affiche par l'utilisateur :

  1. Cles t("...") utilisees dans le code mais ABSENTES de
     data/i18n_strings.json (l'interface afficherait la cle brute) ;
  2. Cles presentes sans 'fr' ou sans 'en' (affichage incomplet apres
     bascule de langue) ;
  3. LITTERAUX en dur passes a des appels d'interface connus pour afficher
     du texte (QPushButton, QLabel, setWindowTitle, QMessageBox, QAction,
     QComboBox.addItem, setPlaceholderText, setToolTip, showMessage,
     addTab, QGroupBox, QRadioButton, QCheckBox, QTableWidgetItem, setTitle,
     QTabWidget, itemsetText...) -- la source reelle des boutons restes en
     anglais (ou en francais) chez les utilisateurs, demande d'audit du
     30/08/2026 apres constat de boutons en anglais sous langue francaise.

Usage :
    python tools/audit_i18n.py            # audit complet, code retour 1 si problemes
    python tools/audit_i18n.py --max 40   # limite l'affichage par categorie

Le scan est base sur l'AST (pas de regex sur le source) : les chaines
calculees (f-strings, concatenations, appels t(...)) ne sont PAS signalees
ici -- seuls les litteraux purs, ceux qui s'affichent tels quels. Les
f-strings francaises en dur echappent donc a ce scan : elles sont couvertes
par la regle de dev "tout texte visible passe par t()" (voir docs/).
"""
import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.resource_loading import load_json_data  # noqa: E402

# Dossiers scannes (le code UI) -- cli/ et tools/ sont exclus par defaut :
# leurs messages vont majoritairement a la CONSOLE, pas a l'interface.
SCAN_DIRS = ("gui", "core")

# Appels dont l'argument N (0-based) est un texte affiche a l'utilisateur.
# Forme : nom_simple_d_appel -> tuple de positions d'arguments a verifier.
# Les appels qualifies (QMessageBox.warning, self.statusBar().showMessage)
# sont compares sur leur DERNIER composant (attribute id).
TEXT_ARGUMENTS: Dict[str, Tuple[int, ...]] = {
    # Constructeurs de widgets dont le 1er argument positionnel est un texte
    "QLabel": (0,),
    "QPushButton": (0,),
    "QCheckBox": (0,),
    "QRadioButton": (0,),
    "QGroupBox": (0,),
    "QAction": (0, 1),      # texte, puis parent -- seul le texte nous interesse
    "QTableWidgetItem": (0,),
    "QListWidgetItem": (0,),
    "QTreeWidgetItem": (0, 1, 2, 3),
    # Methodes de texte
    "setWindowTitle": (0,),
    "setPlaceholderText": (0,),
    "setToolTip": (0,),
    "setStatusTip": (0,),
    "setTitle": (0,),
    "addItem": (0,),        # QComboBox.addItem(texte[, donnee]) / QListWidget
    "addItems": (0,),
    "setText": (0,),
    "insertItem": (1,),
    "addTab": (1,),         # addTab(widget, texte)
    "setTabText": (1,),
    "setTabToolTip": (1,),
    "showMessage": (0,),    # statusBar().showMessage(texte[, duree])
    "setLabelText": (0,),
    # Boites de dialogue : (titre, message) = arguments 1 et 2 (apres parent)
    "information": (1, 2),
    "warning": (1, 2),
    "critical": (1, 2),
    "about": (1, 2),
    "question": (1, 2),
    # Menus
    "addSection": (0,),
}

# Valeurs d'argument legitiment non traduisibles meme positionnees sur un
# appel surveille (objectName, icones, roles, donnees...), plus les rares
# textes VOLONTAIREMENT en dur :
#  - l'ecran de premier lancement est bilingue FR+EN PAR CONCEPTION (aucune
#    langue n'est encore choisie a ce stade, voir
#    gui/main_window.py::_show_first_launch_language_picker) ;
#  - 'Francais'/'English' : chaque langue s'y affiche dans sa propre langue ;
#  - noms propres et URLs (GPLv3, copyright, lien vers le texte de licence).
IGNORED_LITERAL_VALUES = {
    "secondaryButton", "primaryButton", "", " ", "fr", "en", "UTF-8", "utf-8",
    "Choisissez votre langue / Choose your language",
    "Bienvenue dans Empyrion Scenario Editor !\n"
    "Welcome to Empyrion Scenario Editor!\n\n"
    "Choisissez la langue de l'application\n"
    "(modifiable a tout moment ensuite via le bouton FR/EN) :\n\n"
    "Choose the application's language\n"
    "(changeable anytime afterward via the FR/EN button):",
    "Francais", "English", "GPLv3", "Copyright © 2026 Daflo",
    "https://www.gnu.org/licenses/gpl-3.0.html",
}


def _is_ignored(text: str) -> bool:
    if text in IGNORED_LITERAL_VALUES:
        return True
    return text.startswith("http://") or text.startswith("https://")


@dataclass
class Finding:
    path: Path
    line: int
    category: str
    detail: str


@dataclass
class AuditResult:
    missing_keys: List[Finding] = field(default_factory=list)
    incomplete_keys: List[Finding] = field(default_factory=list)
    hardcoded: List[Finding] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.missing_keys) + len(self.incomplete_keys) + len(self.hardcoded)

    @property
    def ok(self) -> bool:
        return self.total == 0


def _call_name(call: ast.Call) -> Optional[str]:
    """Dernier composant du nom d'appel : 'QMessageBox.warning' -> 'warning',
    'btn.setText' -> 'setText', t(...) -> 't'."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_t_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and _call_name(node) == "t"
            and not isinstance(node.func, ast.Attribute))


def _literal_str(node: ast.AST) -> Optional[str]:
    """Contenu d'un litteral chaine pur (ast.Constant str), sinon None --
    les f-strings/JoinedStr et concatenations ne sont PAS des litteraux purs."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def scan_file(path: Path, strings: Dict[str, dict]) -> Tuple[List[Finding], List[Finding], List[Finding]]:
    missing: List[Finding] = []
    hardcoded: List[Finding] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name is None:
            continue
        if name == "t" and not isinstance(node.func, ast.Attribute):
            # Cle t("...") : verifie l'existence dans le JSON
            if node.args:
                key = _literal_str(node.args[0])
                if key is not None and key not in strings:
                    missing.append(Finding(path, node.lineno, "missing_key", key))
            continue
        positions = TEXT_ARGUMENTS.get(name)
        if not positions:
            continue
        for pos in positions:
            if pos >= len(node.args):
                continue
            text = _literal_str(node.args[pos])
            if text is None or _is_ignored(text):
                continue
            if not any(ch.isalpha() for ch in text):
                continue  # separateurs, ponctuation pure : rien a traduire
            hardcoded.append(Finding(path, node.lineno, "hardcoded", text[:80]))
    return missing, [], hardcoded


def check_json_completeness(strings: Dict[str, dict]) -> List[Finding]:
    incomplete: List[Finding] = []
    json_path = PROJECT_ROOT / "data" / "i18n_strings.json"
    for key, entry in strings.items():
        for lang in ("fr", "en"):
            if not entry.get(lang):
                incomplete.append(Finding(json_path, 0, "incomplete_key",
                                          f"{key} ({lang} manquant)"))
    return incomplete


def run_audit(max_display: int = 25) -> AuditResult:
    strings = load_json_data("i18n_strings.json")
    result = AuditResult()
    result.incomplete_keys = check_json_completeness(strings)

    for scan_dir in SCAN_DIRS:
        for path in sorted((PROJECT_ROOT / scan_dir).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            missing, _incomplete, hardcoded = scan_file(path, strings)
            result.missing_keys.extend(missing)
            result.hardcoded.extend(hardcoded)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--max", type=int, default=25,
                        help="nb max de resultats affiches par categorie")
    args = parser.parse_args()

    result = run_audit(max_display=args.max)

    print(f"=== Audit i18n (dossiers : {', '.join(SCAN_DIRS)}) ===")
    print(f"Cles t() manquantes dans i18n_strings.json : {len(result.missing_keys)}")
    for f in result.missing_keys[:args.max]:
        print(f"  {f.path.relative_to(PROJECT_ROOT)}:{f.line}  cle absente : {f.detail}")
    print(f"Cles incompletes (fr/en) : {len(result.incomplete_keys)}")
    for f in result.incomplete_keys[:args.max]:
        print(f"  {f.detail}")
    print(f"Litteraux affiches en dur : {len(result.hardcoded)}")
    for f in result.hardcoded[:args.max]:
        print(f"  {f.path.relative_to(PROJECT_ROOT)}:{f.line}  {f.detail!r}")
    print(f"TOTAL : {result.total}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
