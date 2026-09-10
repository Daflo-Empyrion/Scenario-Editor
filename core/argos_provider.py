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

"""Traduction HORS LIGNE avec Argos Translate (demande du 10/09/2026).

Principe : argostranslate est une dependance OPTIONNELLE (meme philosophie
que qfluentwidgets -- degrade gracieux). Quand elle est installable, l'app
peut :
  1. installer le moteur automatiquement (pip --dry-run --report pour la
     TAILLE exacte de telechargement, affichee AVANT l'installation) ;
  2. proposer les paires de langues de l'index officiel (argospm-index),
     chacune avec sa taille reelle (requete HEAD), telechargees avec barre
     de progression puis installees via install_from_path ;
  3. traduire 100% localement (aucun contenu ne sort du poste).

Repli console (pip absent/inoperatif) : pip_console_command() construit la
commande exacte ciblant le dossier de l'application ; le bouton "Verifier"
de l'assistant relance la detection sans redemarrage.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional

from core.settings import CONFIG_DIR

ARGOS_SITE_DIR = Path(CONFIG_DIR) / "argos_site"
PACKAGE_INDEX_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
_PYPI_JSON = "https://pypi.org/pypi/argostranslate/json"


# ----------------------------------------------------------------- moteur

def is_engine_available() -> bool:
    """argostranslate est-il importable ? Le dossier d'installation cible
    (frozen : --target) est ajoute au path avant le test."""
    _ensure_site_dir_on_path()
    try:
        import argostranslate  # noqa: F401
        return True
    except Exception:
        return False


def _ensure_site_dir_on_path() -> None:
    site = str(ARGOS_SITE_DIR)
    if site not in sys.path and ARGOS_SITE_DIR.exists():
        sys.path.append(site)


def engine_target_dir() -> Path:
    """Dossier d'installation cible du moteur (mode --target)."""
    return ARGOS_SITE_DIR


def pip_console_command() -> str:
    """Commande a copier dans une console si l'installation automatique
    echoue (repli utilisateur, valide puis detecte par le bouton Verifier)."""
    exe = Path(sys.executable).name if not getattr(sys, "frozen", False) else "py"
    target = f'"{ARGOS_SITE_DIR}"' if " " in str(ARGOS_SITE_DIR) else str(ARGOS_SITE_DIR)
    return f'{exe} -m pip install argostranslate --target {target}'


def estimate_engine_download_bytes() -> Optional[int]:
    """Taille TOTALE de telechargement du moteur et de ses dependances :
    pip --dry-run --report resolve l'arbre complet, on interroge ensuite
    chaque URL en HEAD. None si l'estimation echoue (l'installation reste
    tentable, juste sans chiffre)."""
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--dry-run", "--quiet",
               "--report", "-", "argostranslate"]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=180, creationflags=_no_window())
        report = json.loads(result.stdout)
        total = 0
        for item in report.get("install", []):
            url = item.get("download_info", {}).get("url")
            if not url:
                continue
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "empyrion-editor"})
            with urllib.request.urlopen(req, timeout=30) as r:
                total += int(r.headers.get("Content-Length", 0))
        return total or None
    except Exception:
        return None


def install_engine(progress_cb: Optional[Callable[[str], None]] = None) -> bool:
    """Installe argostranslate via pip, en STREAMANT les lignes de pip (la
    callback recoit chaque ligne : journal + progression cote GUI). Sources :
    l'interpreteur courant. Frozen : le pip du SYSTEME cible le dossier de
    l'app (--target) -- les roues doivent correspondre a la version Python de
    l'exe (caveat documente ; en cas d'echec, l'assistant affiche le repli
    console)."""
    def say(msg: str):
        if progress_cb:
            progress_cb(msg)

    frozen = getattr(sys, "frozen", False)
    if frozen:
        cmd = [sys.executable, "-m", "pip", "install", "argostranslate",
               "--target", str(ARGOS_SITE_DIR)]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "argostranslate",
               "--progress-bar", "on"]
    say("$ " + " ".join(cmd))
    ARGOS_SITE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True,
                                   creationflags=_no_window())
    except Exception:
        return False
    for line in process.stdout or []:
        say(line.rstrip())
    code = process.wait()
    _ensure_site_dir_on_path()
    return code == 0 and is_engine_available()


def _no_window() -> int:
    if sys.platform == "win32":
        return 0x08000000  # CREATE_NO_WINDOW : pas de console qui clignote
    return 0


# ----------------------------------------------------------------- modeles

def available_pairs() -> List[dict]:
    """Paires de langues de l'index officiel :
    [{from_code, to_code, from_name, to_name, link}]."""
    req = urllib.request.Request(PACKAGE_INDEX_URL,
                                 headers={"User-Agent": "empyrion-editor"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    pairs = []
    for p in data:
        link = p.get("links")
        link = link[0] if isinstance(link, list) and link else link
        if not link:
            continue
        pairs.append({
            "from_code": p.get("from_code"), "to_code": p.get("to_code"),
            "from_name": p.get("from_name"), "to_name": p.get("to_name"),
            "link": link,
        })
    return pairs


def url_size_bytes(url: str) -> int:
    """Taille reelle d'un telechargement (requete HEAD)."""
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": "empyrion-editor"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length", 0))


def download_model(url: str, dest: Path,
                   progress_cb: Optional[Callable[[int, int], None]] = None) -> Path:
    """Telecharge un .argosmodel par blocs avec progression (done, total)."""
    req = urllib.request.Request(url, headers={"User-Agent": "empyrion-editor"})
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress_cb:
                progress_cb(done, total or done)
    return dest


def install_model_file(path: Path) -> bool:
    """Installe un .argosmodel local (telecharge ici OU importe manuellement,
    ex bundle torrent)."""
    _ensure_site_dir_on_path()
    try:
        from argostranslate import package
        package.install_from_path(str(path))
        return True
    except Exception:
        return False


def packages_on_disk() -> int:
    """Nombre de modeles installes, SANS importer argostranslate (l'import
    tire torch/spacy : plusieurs secondes -- inacceptable pour griser une
    entree de menu au demarrage). Replique le chemin par defaut du module
    settings d'argostranslate (env ARGOS_PACKAGE_DIR > ARGOS_TRANSLATE_PACKAGE_DIR
    > XDG_DATA_HOME/home /.local/share/argos-translate/packages)."""
    env = os.environ
    if env.get("ARGOS_PACKAGE_DIR"):
        d = Path(env["ARGOS_PACKAGE_DIR"])
    elif env.get("ARGOS_TRANSLATE_PACKAGE_DIR"):
        d = Path(env["ARGOS_TRANSLATE_PACKAGE_DIR"])
    else:
        data_home = Path(env.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        d = data_home / "argos-translate" / "packages"
    try:
        return sum(1 for p in d.iterdir() if p.is_dir())
    except OSError:
        return 0


def installed_pair_codes() -> "set[tuple[str, str]]":
    _ensure_site_dir_on_path()
    try:
        from argostranslate import package
        return {(p.from_code, p.to_code)
                for p in package.get_installed_packages()}
    except Exception:
        return set()


def translate_offline(text: str, source: str, target: str) -> str:
    """Traduit localement. Leve une exception explicite uniquement si le
    moteur ou la PAIRE n'est pas installee ; un texte vide ou a espaces seuls
    est rendu TEL QUEL sans erreur (Argos retourne '' -- confondu a tort avec
    une paire absente, retour utilisateur du 10/09/2026 sur en->fr). Les
    placeholders/BBCode sont proteges comme pour le moteur en ligne
    (core/translation.protect_segments) : Argos les alterait sinon."""
    _ensure_site_dir_on_path()
    try:
        from argostranslate import translate
    except Exception as e:
        raise RuntimeError(f"moteur Argos non installe ({e})")
    if (source, target) not in installed_pair_codes() and source not in (None, "", "auto"):
        raise RuntimeError(f"paire {source}->{target} non installee dans Argos "
                           f"(Options > Traduction hors ligne (Argos) pour l'ajouter)")
    if not text or not text.strip():
        return text
    installed = installed_pair_codes()
    from core.translation import protect_segments, restore_segments
    protected, segments = protect_segments(text)

    # source "auto" (defaut de tous les appels GUI) : Argos n'a pas de paire
    # auto -> on essaie les paires INSTALLEES qui aboutissent a la langue
    # cible (retour utilisateur du 10/09/2026 : 'Magnetic Plate' auto->fr
    # echouait systematiquement et retombait sur Google).
    if source in (None, "", "auto"):
        candidates = sorted({s for (s, t) in installed if t == target})
    elif (source, target) in installed:
        candidates = [source]
    else:
        candidates = []
    if not candidates:
        raise RuntimeError(f"paire ->{target} non installee dans Argos "
                           f"(Options > Traduction hors ligne (Argos) pour l'ajouter)")
    last_error: Optional[Exception] = None
    for src in candidates:
        try:
            result = translate.translate(protected, src, target)
        except Exception as e:
            last_error = e
            continue
        if result:
            return restore_segments(result, segments)
    if last_error is not None:
        raise last_error
    return text  # traduction vide -> texte original inchangé
