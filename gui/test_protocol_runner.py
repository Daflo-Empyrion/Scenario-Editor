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
Protocole de test MANUEL de l'application -- compagnon GUI de recette.

PRINCIPE : les 900+ tests pytest verifient le code automatiquement ; ceci est
le complement humain : une liste exhaustive de cas a tester A LA MAIN dans
l'application reelle, pas a pas, avec verdict BON / PAS BON / BLOQUE / N/A,
annotations libres, sessions persistees et rapport exportable.

CYCLE DE VIE D'UNE SESSION :
- Une session = un fichier JSON dans ~/.empyrion_editor/test_sessions/ :
  version testee, date, et pour chaque cas : statut, annotation, horodatage
  et revision du cas au moment du test.
- "Nouvelle session..." propose de repartir a blanc OU de reprendre les
  statuts d'une session anterieure. En reprise, un cas MODIFIE depuis
  (rev superieure) ou manuellement marque "a retester" est AUTOMATIQUEMENT
  remis a non testé : un test vert sur l'ancien code ne masque jamais une
  regression (demande du 30/08/2026).
- Chaque verdict est sauvegarde ATOMIQUEMENT (core.fsutil) : un crash ne
  perd jamais la session.

ENRICHISSEMENT : voir l'en-tete de tools/protocole_cas.py (ajouter un cas ->
NOUVEAU ; modifier un cas -> incrementer "rev" -> A RETESTER).

RUNDEPUIS L'APPLICATION : Aide > Protocole de test > "Commencer une session
de tests..." (gui/test_protocol_dialog.py instancie MainWindow directement,
meme processus/theme). Le point d'entree developpement reste
tools/protocole_test.py (shim).

UTILISATION :
    python tools/protocole_test.py            # interface graphique
    python tools/protocole_test.py --smoke    # autotest sans interaction
"""
import argparse
import csv as csv_module
import io
import json
import os
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QRadioButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QAbstractItemView,
    QFrame,
)

from core.fsutil import atomic_write_text
from core.i18n import t
from core.version import APP_VERSION, GITHUB_REPO
from core.test_protocol import CASES, CATEGORIES, cases_by_category

SESSION_DIR = Path.home() / ".empyrion_editor" / "test_sessions"
SMOKE = False  # True pendant --smoke : pas de dialogue modal au demarrage

# Statuts possibles d'un cas dans une session.
VIERGE = ""          # non testé (valeur absente du JSON)
BON = "BON"
PAS_BON = "PAS BON"
BLOQUE = "BLOQUE"
NA = "N/A"

_CASES_BY_ID = {c["id"]: c for c in CASES}
_GROUPED = cases_by_category()


# ===========================================================================
# Session : persistance JSON (ecriture atomique)
# ===========================================================================

class Session:
    """Etat d'une session de test : resultats par cas + metadonnees."""

    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = data

    # ---------------------------------------------------------- creation
    @classmethod
    def neuve(cls, base: "Session | None" = None, tout_reinitialiser: bool = False) -> "Session":
        """Cree une session. Si `base` est fournie (reprise d'une session
        anterieure), les statuts sont repris SAUF : cas modifies depuis
        (rev differente), cas marques a retester, et -- si
        `tout_reinitialiser` -- absolument tous les cas."""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SESSION_DIR / f"session_{stamp}.json"
        data = {
            "version": APP_VERSION,
            "creee": datetime.now().isoformat(timespec="seconds"),
            "modifiee": datetime.now().isoformat(timespec="seconds"),
            "base": base.path.name if base else None,
            "resultats": {},
        }
        if base is not None and not tout_reinitialiser:
            for case in CASES:
                old = base.data.get("resultats", {}).get(case["id"])
                if not old:
                    continue  # jamais teste dans la base : reste vierge
                same_rev = old.get("rev", 1) == case.get("rev", 1)
                if same_rev and not old.get("a_retester"):
                    data["resultats"][case["id"]] = {
                        "statut": old.get("statut", VIERGE),
                        "annotation": old.get("annotation", ""),
                        "horodatage": old.get("horodatage", ""),
                        "rev": old.get("rev", 1),
                    }
        session = cls(path, data)
        session.save()
        return session

    @staticmethod
    def lister() -> list:
        """Sessions existantes, de la plus recente a la plus ancienne."""
        if not SESSION_DIR.is_dir():
            return []
        return sorted(SESSION_DIR.glob("session_*.json"), reverse=True)

    @classmethod
    def charger(cls, path: Path) -> "Session":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {"version": APP_VERSION, "creee": "", "modifiee": "",
                    "base": None, "resultats": {}}
        return cls(path, data if isinstance(data, dict) else {})

    # ------------------------------------------------------------ acces
    def result(self, case_id: str) -> dict | None:
        return self.data.get("resultats", {}).get(case_id)

    def set_result(self, case_id: str, statut: str, annotation: str) -> None:
        case = _CASES_BY_ID[case_id]
        existing = self.result(case_id) or {}
        self.data.setdefault("resultats", {})[case_id] = {
            "statut": statut,
            "annotation": annotation,
            "horodatage": datetime.now().isoformat(timespec="seconds"),
            "rev": case.get("rev", 1),
            "a_retester": existing.get("a_retester", False) if statut == VIERGE else False,
        }
        self.data["modifiee"] = datetime.now().isoformat(timespec="seconds")
        self.save()

    def reset_case(self, case_id: str, marquer_a_retester: bool = False) -> None:
        existing = self.result(case_id) or {}
        self.data.setdefault("resultats", {})[case_id] = {
            "statut": VIERGE,
            "annotation": existing.get("annotation", "") if marquer_a_retester else "",
            "horodatage": datetime.now().isoformat(timespec="seconds"),
            "rev": _CASES_BY_ID[case_id].get("rev", 1),
            "a_retester": marquer_a_retester,
        }
        self.save()

    def save(self) -> None:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))

    # -------------------------------------------------------- statistiques
    def stats(self) -> dict:
        counts = {"total": len(CASES), BON: 0, PAS_BON: 0, BLOQUE: 0, NA: 0, VIERGE: 0}
        for case in CASES:
            r = self.result(case["id"])
            counts[r.get("statut", VIERGE) if r else VIERGE] += 1
        tested = counts["total"] - counts[VIERGE]
        counts["couverture"] = round(100 * tested / counts["total"]) if counts["total"] else 0
        return counts


# ===========================================================================
# Widgets utilitaires
# ============================================================================

# Barre 'Resultat attendu' : fonds clairs (vert = OK, rouge = conseil
# d'annotation) -- la couleur de TEXTE doit y etre SOMBRE explicite, sinon
# le texte blanc des themes sombres devient illisible (bug du 31/08/2026).
_STYLE_ATTENDU_OK = ("background:#e8f5e9; border:1px solid #1a7f37; "
                     "color:#133a17; border-radius:6px; padding:8px;")
_STYLE_ATTENDU_HINT = ("background:#fdecea; border:1px solid #c62828; "
                       "color:#5c1310; border-radius:6px; padding:8px;")


def _badge(statut: str) -> QLabel:
    lab = QLabel()
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    styles = {
        BON: ("BON", "#1a7f37"),
        PAS_BON: ("PAS BON", "#c62828"),
        BLOQUE: ("BLOQUE", "#ef6c00"),
        NA: ("N/A", "#607d8b"),
    }
    if statut in styles:
        text, color = styles[statut]
        lab.setText(text)
        lab.setStyleSheet(f"background:{color}; color:white; border-radius:8px; "
                          "padding:2px 10px; font-weight:700; font-size:11px;")
    else:
        lab.setText("---")
        lab.setStyleSheet("color:#8a93a6; font-weight:600;")
    return lab


def _case_flag(case: dict, session: Session, base_resultats: dict) -> str:
    """Colonne Info : NOUVEAU (cas absent de la session de base), A RETESTER
    (rev du cas differente de celle testee dans la base), ou vide."""
    if base_resultats is None:
        return ""
    case_id = case["id"]
    if case_id not in base_resultats:
        return "NOUVEAU"
    old_rev = base_resultats[case_id].get("rev", 1)
    if old_rev != case.get("rev", 1):
        return f"A RETESTER (rev {old_rev} -> {case.get('rev', 1)})"
    r = session.result(case_id)
    if r and r.get("a_retester"):
        return "a retester (demande)"
    return ""


# ===========================================================================
# Fenetre pas-a-pas
# ===========================================================================

class StepWindow(QMainWindow):
    """Un test a la fois : etapes, resultat attendu, annotation, verdicts."""

    def __init__(self, session: Session, index: int, base_resultats: dict,
                 on_updated, parent=None):
        super().__init__(parent)
        self.session = session
        self.index = index
        self.base_resultats = base_resultats
        self.on_updated = on_updated  # callback(rafraichi apres chaque verdict)
        self.setWindowTitle(t("runner.step_title"))
        self.resize(1180, 820)
        self._build()
        self._show_case(index)

    def _build(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.lbl_pos = QLabel()
        top.addWidget(self.lbl_pos)
        self.bar = QProgressBar()
        self.bar.setFixedWidth(300)
        top.addWidget(self.bar)
        top.addStretch()
        self.lbl_cat = QLabel()
        top.addWidget(self.lbl_cat)
        root.addLayout(top)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        self.lbl_titre = QLabel()
        self.lbl_titre.setWordWrap(True)
        root.addWidget(self.lbl_titre)

        self.lbl_pre = QLabel()
        self.lbl_pre.setWordWrap(True)
        self.lbl_pre.setVisible(False)
        root.addWidget(self.lbl_pre)

        self.lbl_etapes = QLabel()
        self.lbl_etapes.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_etapes.setWordWrap(True)
        self.lbl_etapes.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.lbl_etapes, 1)

        self.lbl_attendu = QLabel()
        self.lbl_attendu.setWordWrap(True)
        # TEXTE SOMBRE explicite : sur les themes sombres, la couleur de
        # texte du theme (blanc) heritait sur ce fond clair -- invisible
        # (retour utilisateur du 31/08/2026, capture). Voir _STYLE_ATTENDU_OK.
        self.lbl_attendu.setStyleSheet(_STYLE_ATTENDU_OK)
        root.addWidget(self.lbl_attendu)

        root.addWidget(QLabel(t("runner.annotation_label")))
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(84)
        self.notes.setPlaceholderText(t("runner.notes_placeholder"))
        root.addWidget(self.notes)

        verdicts = QHBoxLayout()
        verdicts.setSpacing(12)

        def verdict_btn(text, color, shortcut, slot):
            b = QPushButton(f"{text}\n({shortcut})")
            b.setFixedHeight(72)
            b.setStyleSheet(f"background:{color}; color:white; font-weight:800; "
                            f"font-size:15px; border-radius:8px;")
            b.clicked.connect(slot)
            QShortcut(QKeySequence(shortcut), self, activated=slot)
            verdicts.addWidget(b)

        verdict_btn("✔  BON", "#1a7f37", "F1", lambda: self._verdict(BON))
        verdict_btn("✘  PAS BON", "#c62828", "F2", lambda: self._verdict(PAS_BON))
        verdict_btn("⏸  BLOQUE", "#ef6c00", "F3", lambda: self._verdict(BLOQUE))
        verdict_btn("↷  NON APPLICABLE", "#607d8b", "F4", lambda: self._verdict(NA))
        root.addLayout(verdicts)

        nav = QHBoxLayout()
        b_prev = QPushButton(t("runner.prev"))
        b_prev.clicked.connect(lambda: self._go(self.index - 1))
        b_skip = QPushButton(t("runner.skip"))
        b_skip.clicked.connect(lambda: self._go(self.index + 1))
        b_next = QPushButton(t("runner.next"))
        b_next.setObjectName("primaryButton")
        b_next.clicked.connect(lambda: self._go(self.index + 1))
        nav.addWidget(b_prev)
        nav.addWidget(b_skip)
        nav.addStretch()
        nav.addWidget(b_next)
        root.addLayout(nav)

        QShortcut(QKeySequence("Escape"), self, activated=self.close)
        self.setCentralWidget(central)

    def _show_case(self, index: int):
        index = max(0, min(index, len(CASES) - 1))
        self.index = index
        case = CASES[index]
        self.lbl_pos.setText(f"<b>Test {index + 1} / {len(CASES)}</b>")
        self.bar.setValue(round(100 * index / max(len(CASES) - 1, 1)))
        cat_label = dict(CATEGORIES).get(case["cat"], case["cat"])
        self.lbl_cat.setText(f"<b>Catégorie :</b> {cat_label}")
        self.setWindowTitle(f"{case['id']} — Protocole de test")
        self.lbl_titre.setText(f'<span style="font-size:20px; font-weight:800;">'
                               f'{case["id"]} — {case["titre"]}</span>')
        if case.get("pre"):
            self.lbl_pre.setVisible(True)
            # Texte sombre explicite sur le bandeau jaune clair -- meme bug
            # que la barre 'Resultat attendu' sur themes sombres.
            self.lbl_pre.setText(f'<div style="background:#fff7e0; border:1px solid #d9a800; '
                                 f'color:#4a3a00; border-radius:6px; padding:6px;"><b>Preparation :</b> '
                                 f'{case["pre"]}</div>')
        else:
            self.lbl_pre.setVisible(False)
        steps_html = "<b>Etapes a suivre :</b><ol>" + "".join(
            f"<li>{s}</li>" for s in case["etapes"]) + "</ol>"
        self.lbl_etapes.setText(steps_html)
        self.lbl_attendu.setText(f"<b>Resultat attendu :</b> {case['attendu']}")
        r = self.session.result(case["id"])
        self.notes.setPlainText(r.get("annotation", "") if r else "")

    def _verdict(self, statut: str):
        case = CASES[self.index]
        annotation = self.notes.toPlainText().strip()
        if statut in (PAS_BON, BLOQUE) and not annotation:
            # Rester sur place pour ecrire l'observation : c'est elle qui fera
            # le ticket GitHub ensuite.
            self.notes.setFocus()
            self.lbl_attendu.setStyleSheet(_STYLE_ATTENDU_HINT)
            self.lbl_attendu.setText(t("runner.fail_annotation_hint"))
            return
        self.lbl_attendu.setStyleSheet(_STYLE_ATTENDU_OK)
        self.session.set_result(case["id"], statut, annotation)
        if self.on_updated:
            self.on_updated()
        self._go(self.index + 1)

    def _go(self, index: int):
        if index < 0:
            index = 0
        if index >= len(CASES):
            self.close()
            return
        self._show_case(index)


# ===========================================================================
# Bilan
# ===========================================================================

class BilanDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle(t("runner.bilan_title"))
        self.resize(1100, 720)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)

        root.addWidget(QLabel("<span style='font-size:18px; font-weight:800;'>"
                              f"Bilan — session v{session.data.get('version', '?')} du "
                              f"{session.data.get('creee', '?')[:10]}</span>"))

        stats = session.stats()
        chips = QHBoxLayout()
        chips.addWidget(self._chip(str(stats["total"]), "tests au total", "#546e7a"))
        chips.addWidget(self._chip(str(stats[BON]), "BON", "#1a7f37"))
        chips.addWidget(self._chip(str(stats[PAS_BON]), "PAS BON", "#c62828"))
        chips.addWidget(self._chip(str(stats[BLOQUE]), "BLOQUES", "#ef6c00"))
        chips.addWidget(self._chip(str(stats[NA]), "N/A", "#607d8b"))
        chips.addWidget(self._chip(str(stats[VIERGE]), "non testés", "#9aa3b2"))
        chips.addWidget(self._chip(f"{stats['couverture']}%", "couverture", "#3f51b5"))
        chips.addStretch()
        root.addLayout(chips)

        root.addWidget(QLabel(t("runner.bilan_failures_header")))
        failures = [(c, session.result(c["id"])) for c in CASES
                    if (session.result(c["id"]) or {}).get("statut") in (PAS_BON, BLOQUE)]
        table = QTableWidget(len(failures), 3)
        table.setHorizontalHeaderLabels(["ID", "Test", "Annotation"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, (case, res) in enumerate(failures):
            table.setItem(r, 0, QTableWidgetItem(case["id"]))
            table.setItem(r, 1, QTableWidgetItem(case["titre"]))
            table.setItem(r, 2, QTableWidgetItem(res.get("annotation", "")))
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 90)
        table.setColumnWidth(1, 340)
        root.addWidget(table, 1)

        btns = QHBoxLayout()
        b_md = QPushButton(t("runner.export_md_bilan"))
        b_md.clicked.connect(lambda: self._export_markdown())
        b_csv = QPushButton(t("runner.export_csv"))
        b_csv.clicked.connect(lambda: self._export_csv())
        b_gh = QPushButton(t("runner.open_ticket"))
        b_gh.setObjectName("primaryButton")
        b_gh.clicked.connect(self._ticket_github)
        b_gh.setEnabled(bool(failures) and bool(GITHUB_REPO.strip()))
        btns.addWidget(b_md)
        btns.addWidget(b_csv)
        btns.addWidget(b_gh)
        btns.addStretch()
        b_close = QPushButton(t("btn.close"))
        b_close.setObjectName("primaryButton")
        b_close.clicked.connect(self.accept)
        btns.addWidget(b_close)
        root.addLayout(btns)

    def _chip(self, number, label, color):
        return QLabel(f"<div style='background:{color}; color:white; border-radius:8px; "
                      f"padding:10px 18px;'><span style='font-size:22px; font-weight:800;'>"
                      f"{number}</span><br><span style='font-size:11px;'>{label}</span></div>")

    # ------------------------------------------------------------- exports
    def _export_path(self, default_name):
        path, _ = QFileDialog.getSaveFileName(self, "Exporter le bilan", default_name)
        return Path(path) if path else None

    def _export_markdown(self):
        path = self._export_path("bilan_protocole.md")
        if not path:
            return
        atomic_write_text(path, render_markdown(self.session))
        QMessageBox.information(self, t("runner.export_title"), t("runner.export_md_written", path=path))

    def _export_csv(self):
        path = self._export_path("bilan_protocole.csv")
        if not path:
            return
        atomic_write_text(path, render_csv(self.session))
        QMessageBox.information(self, t("runner.export_title"), t("runner.export_csv_written", path=path))

    def _ticket_github(self):
        failures = [(c, self.session.result(c["id"])) for c in CASES
                    if (self.session.result(c["id"]) or {}).get("statut") in (PAS_BON, BLOQUE)]
        lines = [f"- **{c['id']}** — {c['titre']} : {res.get('annotation', '(sans detail)')}"
                 for c, res in failures]
        body = ("Echecs du protocole de test manuel v" + APP_VERSION + " :\n\n"
                + "\n".join(lines)
                + "\n\n---\nGenere par tools/protocole_test.py")
        params = urllib.parse.urlencode({
            "title": f"[Protocole] {len(failures)} echec(s) — v{APP_VERSION}",
            "body": body,
        })
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}/issues/new?{params}"))


# ===========================================================================
# Rendus d'export (separes des widgets : utilises aussi par --smoke)
# ===========================================================================

STATUT_LABELS = {VIERGE: "non testé", BON: "BON", PAS_BON: "PAS BON",
                 BLOQUE: "BLOQUE", NA: "N/A"}


def render_markdown(session: Session) -> str:
    stats = session.stats()
    out = io.StringIO()
    w = out.write
    w(f"# Protocole de test — v{session.data.get('version', '?')}\n\n")
    w(f"Session du {session.data.get('creee', '?')} (derniere mise a jour "
      f"{session.data.get('modifiee', '?')})\n\n")
    w(f"| Total | BON | PAS BON | BLOQUES | N/A | Non testés | Couverture |\n")
    w(f"|---|---|---|---|---|---|---|\n")
    w(f"| {stats['total']} | {stats[BON]} | {stats[PAS_BON]} | {stats[BLOQUE]} | "
      f"{stats[NA]} | {stats[VIERGE]} | {stats['couverture']}% |\n\n")

    failures = [(c, session.result(c["id"])) for c in CASES
                if (session.result(c["id"]) or {}).get("statut") in (PAS_BON, BLOQUE)]
    if failures:
        w("## Echecs\n\n")
        for case, res in failures:
            note = res.get("annotation", "") or "(sans detail)"
            w(f"- **{case['id']}** — {case['titre']} : {note}\n")
        w("\n")

    grouped = cases_by_category()
    for code, label in CATEGORIES:
        cases = grouped[code]
        done = sum(1 for c in cases
                   if (session.result(c["id"]) or {}).get("statut", VIERGE) != VIERGE)
        w(f"## {label} ({done}/{len(cases)})\n\n")
        w("| ID | Test | Statut | Annotation |\n|---|---|---|---|\n")
        for case in cases:
            r = session.result(case["id"]) or {}
            note = (r.get("annotation", "") or "").replace("|", "\\|").replace("\n", " ")
            w(f"| {case['id']} | {case['titre']} | {STATUT_LABELS[r.get('statut', VIERGE)]} "
              f"| {note} |\n")
        w("\n")
    return out.getvalue()


def render_csv(session: Session) -> str:
    out = io.StringIO()
    writer = csv_module.writer(out, lineterminator="\r\n")
    writer.writerow(["id", "categorie", "titre", "statut", "annotation", "horodatage", "rev"])
    cat_labels = dict(CATEGORIES)
    for case in CASES:
        r = session.result(case["id"]) or {}
        writer.writerow([
            case["id"], cat_labels[case["cat"]], case["titre"],
            STATUT_LABELS[r.get("statut", VIERGE)],
            r.get("annotation", ""), r.get("horodatage", ""), case.get("rev", 1),
        ])
    return out.getvalue()


# ===========================================================================
# Fenetre principale
# ===========================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session: Session | None = None
        self.base_resultats: dict | None = None  # resultats de la session de base (flags NOUVEAU/A RETESTER)
        self.setWindowTitle(f"Protocole de test — Empyrion Scenario Editor v{APP_VERSION}")
        self.resize(1280, 800)
        self._build()
        if not SMOKE:
            # Proposition de session au lancement (dialogue modal) -- saute en
            # mode --smoke sinon l'autotest bloquerait sur exec().
            self._nouvelle_session()

    # ------------------------------------------------------------ interface
    def _build(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)

        head = QHBoxLayout()
        self.lbl_session = QLabel(t("runner.no_session"))
        head.addWidget(self.lbl_session)
        head.addStretch()
        self.lbl_progress = QLabel("")
        head.addWidget(self.lbl_progress)
        self.bar = QProgressBar()
        self.bar.setFixedWidth(260)
        self.bar.setFormat("%p%")
        head.addWidget(self.bar)
        root.addLayout(head)

        btns = QHBoxLayout()
        b_new = QPushButton(t("runner.new_session"))
        b_new.setObjectName("primaryButton")
        b_new.clicked.connect(self._nouvelle_session)
        btns.addWidget(b_new)
        b_md = QPushButton(t("runner.export_markdown"))
        b_md.clicked.connect(lambda: self._export(render_markdown, "bilan_protocole.md"))
        btns.addWidget(b_md)
        b_csv = QPushButton(t("runner.export_csv"))
        b_csv.clicked.connect(lambda: self._export(render_csv, "bilan_protocole.csv"))
        btns.addWidget(b_csv)
        b_bilan = QPushButton(t("runner.bilan"))
        b_bilan.clicked.connect(self._bilan)
        btns.addWidget(b_bilan)
        btns.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("runner.filter_placeholder"))
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(self._fill_table)
        btns.addWidget(self.search)
        b_step = QPushButton(t("runner.step_mode"))
        b_step.setObjectName("primaryButton")
        b_step.clicked.connect(self._open_step_first_untested)
        btns.addWidget(b_step)
        root.addLayout(btns)

        split = QHBoxLayout()
        self.cats = QTreeWidget()
        self.cats.setHeaderLabels(["Categories", "Fait"])
        self.cats.setColumnWidth(0, 250)
        self.cats.itemSelectionChanged.connect(self._fill_table)
        split.addWidget(self.cats, 1)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Test", "Statut", "Info", "Dernier test"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        self.table.doubleClicked.connect(
            lambda idx: self._open_step(self._case_id_at(idx.row())))
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(2, 95)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 110)
        split.addWidget(self.table, 3)
        root.addLayout(split, 1)
        self.setCentralWidget(central)

    # ------------------------------------------------------ session : flux
    def _nouvelle_session(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(t("runner.session_dialog_title"))
        dialog.setMinimumWidth(560)
        lay = QVBoxLayout(dialog)
        lay.addWidget(QLabel(t("runner.base_question")))
        radios = {}
        r_vierge = QRadioButton(t("runner.session_vierge"))
        radios["vierge"] = r_vierge
        r_reprise = QRadioButton(t("runner.session_reprise"))
        radios["reprise"] = r_reprise
        r_total = QRadioButton(t("runner.session_total"))
        radios["total"] = r_total
        sessions = Session.lister()
        for r in (r_vierge, r_reprise, r_total):
            lay.addWidget(r)
        r_vierge.setChecked(not sessions)
        r_reprise.setChecked(bool(sessions))
        combo = None
        if sessions:
            lay.addWidget(QLabel(t("runner.base_session")))
            from PyQt6.QtWidgets import QComboBox
            combo = QComboBox()
            for p in sessions:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    summary = (f"{p.stem} — v{data.get('version', '?')} — "
                               f"{len(data.get('resultats', {}))} resultats")
                except Exception:
                    summary = p.stem
                combo.addItem(summary, p)
            combo.setCurrentIndex(0)
            lay.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        lay.addWidget(buttons)
        if not dialog.exec():
            return
        if not any(r.isChecked() for r in radios.values()):
            return
        base = None
        if radios["reprise"].isChecked() or radios["total"].isChecked():
            if combo is None:
                QMessageBox.information(self, t("runner.new_session_btn"),
                                        t("runner.no_previous_session"))
                return
            base = Session.charger(combo.currentData())
        self.session = Session.neuve(base, tout_reinitialiser=radios["total"].isChecked())
        self.base_resultats = (base.data.get("resultats", {}) if base is not None
                               and not radios["total"].isChecked() else
                               (base.data.get("resultats", {}) if base else None))
        self._refresh_all()
        self.statusBar().showMessage(
            f"Session creee : {self.session.path.name}", 8000)

    def _refresh_all(self):
        s = self.session
        if s is None:
            return
        stats = s.stats()
        self.lbl_session.setText(
            f"<b>Session de test</b> — v{s.data.get('version', '?')} — "
            f"{s.path.stem} — base : {s.data.get('base') or 'vierge'}")
        self.lbl_progress.setText(f"Progression : <b>{stats['total'] - stats[VIERGE]} / "
                                  f"{stats['total']}</b>")
        self.bar.setValue(stats["couverture"])
        self.cats.blockSignals(True)
        self.cats.clear()
        grouped = cases_by_category()
        for code, label in CATEGORIES:
            cases = grouped[code]
            done = sum(1 for c in cases
                       if (s.result(c["id"]) or {}).get("statut", VIERGE) != VIERGE)
            it = QTreeWidgetItem([label, f"{done}/{len(cases)}"])
            it.setData(0, Qt.ItemDataRole.UserRole, code)
            it.setTextAlignment(1, Qt.AlignmentFlag.AlignRight)
            self.cats.addTopLevelItem(it)
        self.cats.blockSignals(False)
        self._fill_table()

    # ---------------------------------------------------------- table
    def _selected_category(self) -> str | None:
        items = self.cats.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _fill_table(self):
        s = self.session
        if s is None:
            return
        cat = self._selected_category()
        text = self.search.text().strip().lower()
        rows = [c for c in CASES
                if (cat is None or c["cat"] == cat)
                and (not text or text in c["id"].lower()
                     or text in c["titre"].lower()
                     or text in STATUT_LABELS[(s.result(c["id"]) or {}).get("statut", VIERGE)].lower()
                     or text in _case_flag(c, s, self.base_resultats).lower())]
        self.table.setRowCount(len(rows))
        for r, case in enumerate(rows):
            res = s.result(case["id"]) or {}
            statut = res.get("statut", VIERGE)
            self.table.setItem(r, 0, QTableWidgetItem(case["id"]))
            self.table.setItem(r, 1, QTableWidgetItem(case["titre"]))
            self.table.setCellWidget(r, 2, _badge(statut))
            flag = _case_flag(case, s, self.base_resultats)
            item_flag = QTableWidgetItem(flag)
            if flag.startswith("A RETESTER") or flag == "a retester (demande)":
                item_flag.setForeground(Qt.GlobalColor.red)
            elif flag == "NOUVEAU":
                item_flag.setForeground(Qt.GlobalColor.darkGreen)
            self.table.setItem(r, 3, item_flag)
            self.table.setItem(r, 4, QTableWidgetItem(res.get("horodatage", "")[:16]
                                                       .replace("T", " ")))
            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, case["id"])

    def _case_id_at(self, row: int) -> str:
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _table_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        case_id = self._case_id_at(row)
        menu = QMenu(self)
        act_open = menu.addAction("Ouvrir en pas-a-pas")
        act_reset = menu.addAction("Reinitialiser ce test")
        act_retest = menu.addAction("Marquer a retester")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_open:
            self._open_step(case_id)
        elif chosen == act_reset:
            self.session.reset_case(case_id, marquer_a_retester=False)
            self._refresh_all()
        elif chosen == act_retest:
            self.session.reset_case(case_id, marquer_a_retester=True)
            self._refresh_all()

    # ------------------------------------------------------ pas-a-pas
    def _open_step(self, case_id: str):
        index = next(i for i, c in enumerate(CASES) if c["id"] == case_id)
        self._step_window = StepWindow(self.session, index, self.base_resultats,
                                       on_updated=self._refresh_all)
        self._step_window.show()

    def _open_step_first_untested(self):
        index = next((i for i, c in enumerate(CASES)
                      if (self.session.result(c["id"]) or {}).get("statut", VIERGE) == VIERGE), 0)
        self._open_step(CASES[index]["id"])

    # ------------------------------------------------------ exports/bilan
    def _export(self, renderer, default_name):
        if self.session is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter", default_name)
        if not path:
            return
        atomic_write_text(Path(path), renderer(self.session))
        self.statusBar().showMessage(f"Export ecrit : {path}", 8000)

    def _bilan(self):
        if self.session is None:
            return
        BilanDialog(self.session, parent=self).exec()


# ===========================================================================
# Autotest sans interaction (--smoke)
# ===========================================================================

def run_smoke() -> int:
    """Verifie la logique (sessions, reprise, rev, exports) sans interaction."""
    import tempfile
    global SMOKE, SESSION_DIR
    SMOKE = True
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    global SESSION_DIR
    with tempfile.TemporaryDirectory() as tmp:
        SESSION_DIR = Path(tmp)
        # 1. session vierge + verdicts
        s1 = Session.neuve()
        assert s1.stats()[VIERGE] == len(CASES)
        s1.set_result(CASES[0]["id"], BON, "ok")
        s1.set_result(CASES[1]["id"], PAS_BON, "probleme X")
        assert s1.stats()[BON] == 1 and s1.stats()[PAS_BON] == 1
        # 2. reprise : statuts conserves, cas modifie remis a zero
        s2 = Session.neuve(base=s1)
        assert s2.result(CASES[0]["id"])["statut"] == BON
        assert s2.result(CASES[1]["id"])["statut"] == PAS_BON
        case = dict(_CASES_BY_ID[CASES[1]["id"]], rev=2)
        CASES[1]["rev"] = 2
        s3 = Session.neuve(base=s1)
        assert s3.result(CASES[1]["id"]) is None, "cas modifie doit etre reinitialise"
        assert s3.result(CASES[0]["id"])["statut"] == BON
        del CASES[1]["rev"]
        # 3. reinitialisation totale
        s4 = Session.neuve(base=s1, tout_reinitialiser=True)
        assert s4.result(CASES[0]["id"]) is None
        # 4. exports
        md = render_markdown(s1)
        assert "PAS BON" in md and CASES[1]["titre"] in md
        cs = render_csv(s1)
        assert CASES[0]["id"] in cs
        # 5. fenetres (creation/rendu sans interaction)
        from gui.theme import apply_theme
        apply_theme(app)
        w = MainWindow()
        w.session = s1
        w._refresh_all()
        step = StepWindow(s1, 0, None, on_updated=None)
        step.close()
        bilan = BilanDialog(s1)
        bilan.close()
    print(f"SMOKE OK — {len(CASES)} cas, sessions/reprise/rev/exports/fenetres verifies")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Protocole de test manuel de l'application.")
    parser.add_argument("--smoke", action="store_true",
                        help="autotest sans interaction (sessions, reprise, exports)")
    args = parser.parse_args()
    if args.smoke:
        sys.exit(run_smoke())

    app = QApplication(sys.argv)
    from gui.theme import apply_theme
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
