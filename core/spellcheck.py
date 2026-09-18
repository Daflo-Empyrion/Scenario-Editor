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
Correcteur grammatical et orthographique francais EMBARQUE : Grammalecte
(paquet Python pur, GPL -- comme l'application).

Installation a la demande dans ~/.empyrion_editor/grammalecte (meme modele
que le moteur Argos : rien dans le depot, rien dans l'exe ; telechargement
unique depuis le site officiel via download_and_install, bouton dedie dans
le dialogue de correction).

Le texte analyse est d'abord protege (balises BBCode et placeholders
remplaces par des jetons, meme mecanique que la traduction -- voir
core/translation.py) : seuls les fragments de TEXTE LIBRE partent a
Grammalecte, aucune fausse alerte sur [00fbff] ou {PlayerName}. Les offsets
des erreurs sont convertis en positions ABSOLUES dans le texte d'origine.

Lexique d'ignorance persistant : ~/.empyrion_editor/spell_ignore.json
(noms propres et refs du jeu que l'utilisateur ne veut jamais voir signales).
"""
import io
import json
import re
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple

GRAMMALECTE_VERSION = "2.3.0"
DOWNLOAD_URL = f"https://grammalecte.net/zip/Grammalecte-fr-v{GRAMMALECTE_VERSION}.zip"
INSTALL_DIR = Path.home() / ".empyrion_editor" / "grammalecte"
IGNORE_FILE = Path.home() / ".empyrion_editor" / "spell_ignore.json"

_lock = threading.Lock()
_module = None
_import_error = ""
_ignore_cache: Optional[Set[str]] = None


def _package_dirs() -> List[Path]:
    dirs = [INSTALL_DIR]
    if getattr(sys, "frozen", False):
        dirs.append(Path(getattr(sys, "_MEIPASS", "")) / "grammalecte")
    dirs.append(Path(__file__).resolve().parent.parent / "grammalecte")
    return dirs


def is_available() -> bool:
    try:
        _ensure_loaded()
        return True
    except Exception:
        return False


def is_packaged() -> bool:
    """Grammalecte present sur disque (sans charger le graphe ~1-2 s) -- pour
    activer/griser des boutons d'interface a moindre cout."""
    return any((d / "grammalecte").is_dir() for d in _package_dirs())


def get_import_error() -> str:
    return _import_error


def _ensure_loaded():
    """Import paresseux + chargement du graphe Grammalecte (1-2 s au premier
    appel, garde charge pour la duree du processus). Thread-safe."""
    global _module, _import_error
    with _lock:
        if _module is not None:
            return _module
        try:
            package_dir = None
            for d in _package_dirs():
                if (d / "grammalecte").is_dir():
                    package_dir = d
                    break
            if package_dir is None:
                raise RuntimeError("Grammalecte non installe")
            sd = str(package_dir)
            if sd not in sys.path:
                sys.path.insert(0, sd)
            import grammalecte.fr as gce
            gce.load()
            _module = gce
        except Exception as e:
            _import_error = str(e) or type(e).__name__
            raise
        return _module


def download_and_install(progress_cb: Optional[Callable[[str], None]] = None) -> bool:
    """Telecharge le zip officiel depuis grammalecte.net et l'installe dans
    INSTALL_DIR (pattern moteur Argos). Retourne True si le paquet est
    utilisable au retour."""
    def say(msg: str):
        if progress_cb:
            progress_cb(msg)

    if is_available():
        return True
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    say(f"Telechargement de Grammalecte v{GRAMMALECTE_VERSION}...")
    with urllib.request.urlopen(DOWNLOAD_URL, timeout=60) as resp:
        data = resp.read()
    say("Extraction...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(INSTALL_DIR)
    # purger un eventuel echec d'import precedent avant relecture
    for mod in [m for m in list(sys.modules) if m.startswith("grammalecte")]:
        del sys.modules[mod]
    say("Termine.")
    return is_available()


def load_ignore_words() -> Set[str]:
    global _ignore_cache
    if _ignore_cache is None:
        try:
            _ignore_cache = set(json.loads(IGNORE_FILE.read_text(encoding="utf-8")))
        except Exception:
            _ignore_cache = set()
    return _ignore_cache


def add_ignored_word(word: str) -> None:
    words = load_ignore_words()
    words.add(word.lower().strip())
    try:
        IGNORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        IGNORE_FILE.write_text(
            json.dumps(sorted(words), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# Options Grammalecte pour les textes de JEU : on desactive les groupes de
# regles typographiques inadaptes au contenu Empyrion (apostrophe droite
# ASCII volontaire, pas d'insecables requises, \n litteraux) -- c'est aussi
# ce qui elimine la derive d'offsets (l'insertion simulee 'nbsp' decalait le
# compteur interne du moteur sur les phrases suivantes).
_GAME_DOPTIONS = {'apos': False, 'nbsp': False, 'esp': False, 'tab': False,
                  'mapos': False, 'eepi': False, 'ocr': False, 'liga': False}

_TOKEN_RE_SPLIT = re.compile(r"(XXTAG\d+XX)")


def _rebuild_lines(text: str):
    """Decoupe `text` par vraies lignes (\n) ; dans chaque ligne, les elements
    proteges (balises BBCode, placeholders) sont remplaces par UN espace et
    les fragments de texte libre conserves : Grammalecte recoit la PHRASE
    COMPLETE (analyse grammaticale utile) au lieu de bouts coupes par les
    balises (retour utilisateur 12/09/2026). Retourne une liste de
    (line_start_abs, pure_line, mapping) ou mapping = [(abs_start,
    pure_start, frag_len)] localise chaque fragment dans la ligne reconstituee.

    Utilise la protection SANS les nombres (_PROTECTED_RE_GRAMMAR) : un
    nombre doit rester visible pour la grammaire -- la ponctuation autour
    nous interesse (espace avant ':' de 'Time: 1900'), et il n'y a aucune
    faute possible DANS un nombre."""
    from core.translation import _PROTECTED_RE_GRAMMAR
    results = []
    line_start = 0
    for line in text.split("\n"):
        fragments = []
        pos = 0
        for m in _PROTECTED_RE_GRAMMAR.finditer(line):
            if m.start() > pos:
                fragments.append((line_start + pos, line[pos:m.start()]))
            pos = m.end()
        if pos < len(line):
            fragments.append((line_start + pos, line[pos:]))
        if fragments:
            pure_parts = []
            mapping = []
            pure_pos = 0
            for i, (abs_start, frag) in enumerate(fragments):
                if i > 0:  # separateur a la place de la ou les balises
                    pure_parts.append(" ")
                    pure_pos += 1
                mapping.append((abs_start, pure_pos, len(frag)))
                pure_parts.append(frag)
                pure_pos += len(frag)
            results.append((line_start, "".join(pure_parts), mapping))
        line_start += len(line) + 1
    return results


def _map_to_original(mapping, pure_start_err: int, pure_end_err: int):
    """Convertit des offsets dans la ligne reconstituee vers le texte original.
    Retourne None si l'erreur tombe sur un separateur de balise (rien a
    corriger) ou hors des fragments."""
    for abs_start, pure_start, frag_len in mapping:
        if pure_start <= pure_start_err < pure_start + frag_len:
            end_clamped = min(pure_end_err, pure_start + frag_len)
            return (abs_start + (pure_start_err - pure_start),
                    abs_start + (end_clamped - pure_start))
    return None


def auto_fix(text: str) -> Tuple[str, List[dict]]:
    """Correction automatique : applique la premiere suggestion de chaque
    erreur detectee (du plus grand offset au plus petit pour preserver les
    offsets). Retourne (texte_corrige, corrections_appliquees). Sans
    Grammalecte ou sans rien a corriger : (text, []) -- jamais d'exception
    remontee a l'interface."""
    if not is_available() or not text or not text.strip():
        return text, []
    try:
        issues = check_text(text)
    except Exception:
        return text, []
    applicable = [i for i in issues if i.get("suggestions")]
    if not applicable:
        return text, []
    corrected = text
    applied: List[dict] = []
    for iss in sorted(applicable, key=lambda i: i["start"], reverse=True):
        corrected = (corrected[:iss["start"]] + iss["suggestions"][0]
                     + corrected[iss["end"]:])
        applied.append(iss)
    return corrected, applied


def check_text(text: str) -> List[dict]:
    """Analyse un texte de cellule (BBCode/placeholders exclus de l'analyse,
    lexique d'ignorance applique) et retourne les erreurs avec offsets ABSOLUS
    dans `text` :
      start, end, orig, s_type (conj/conf/ppas/typo/...), message, suggestions.
    Grammalecte doit etre installe (is_available) -- sinon RuntimeError.

    Chaque LIGNE est reconstituee complete (balises -> espaces) pour que le
    moteur analyse des phrases entieres, avec les options de jeu (voir
    _GAME_DOPTIONS). Les erreurs tombant sur un separateur de balise sont
    ignorees ; les erreurs hors fragments reconnus aussi (securite offsets)."""
    gce = _ensure_loaded()
    from core.translation import _PROTECTED_RE_GRAMMAR
    _ = _PROTECTED_RE_GRAMMAR  # documente : _rebuild_lines l'utilise
    ignored = load_ignore_words()
    issues: List[dict] = []
    # ATTENTION : un dOptions PARTIEL transmis a parse() REMPLACE toute la
    # configuration (les groupes absents sont desactives -> zero erreur
    # retournee, vecu 12/09/2026). Toujours partir de getOptions() complet
    # puis surcharger les options de jeu.
    dopt = dict(gce.getOptions())
    dopt.update(_GAME_DOPTIONS)
    for line_start_abs, pure, mapping in _rebuild_lines(text):
        if not pure.strip():
            continue
        for err in gce.parse(pure, "FR", dOptions=dopt):
            mapped = _map_to_original(mapping, err["nStart"], err["nEnd"])
            if mapped is None:
                continue
            start, end = mapped
            orig = text[start:end]
            if orig.lower().strip() in ignored:
                continue
            issues.append({
                "start": start, "end": end, "orig": orig,
                "s_type": err.get("sType", ""),
                "message": err.get("sMessage", ""),
                "suggestions": [s for s in (err.get("aSuggestions") or [])
                                if isinstance(s, str)][:4],
            })
    return issues
