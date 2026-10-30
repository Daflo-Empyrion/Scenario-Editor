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

"""Look « cartoon » : presets visuels appliques en data au scenario.

Leviers prouves en data (fiche cerveau visuel-cartoon-leviers-data) :
- terrain.ecf de chaque playfield : saturation des teintes, relief et
  normales aplatis, brillance supprimee — le sol devient flat et sature ;
- playfield_static.yaml + playfield_dynamic.yaml : couleurs du ciel, de
  l'horizon, de l'atmosphere et du brouillard saturees, couverture de
  brouillard reduite — ciels crisper, plus « dessin animes ».
Hors perimetre (impossible ou non verifiable en data) : textures reelles
des blocs (bundle Unity), cel-shading (shader), paint des .epb.

Les transformations REEXPRIMENT uniquement les lignes ciblees : le reste
du fichier reste octet-pour-octet identique (commentaires, conventions de
l'hote, sections gameplay). Idempotence NON garantie : une 2e execution
reapplique les facteurs — le CLI refuse donc de rejouer sans --force.
"""
from __future__ import annotations

import colorsys
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from core.ecf.parser import parse_ecf_file
from core.fsutil import atomic_write_text
from core.production_sync import sync_to_production
from core.settings import get_backup_root, get_production_scenario_path
from core.yamllite.parser import parse_yaml_file


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip('0').rstrip('.')


# Facteurs du preset, editables depuis le dialogue : cle -> (defaut, min, max)
PRESET_SPECS: Dict[str, Tuple[float, float, float]] = {
    "saturation": (1.6, 1.0, 3.0),      # terrain : Saturation x
    "smoothness_cap": (-0.25, -1.0, 0.0),   # terrain : plafond de brillance
    "normal": (0.6, 0.1, 1.0),          # terrain : NormalStrength x
    "relief": (0.55, 0.0, 1.0),         # terrain : ReliefStrength x
    "rgb_spread": (1.5, 1.0, 3.0),      # terrain : ecart des teintes RGB
    "sky_saturation": (1.5, 1.0, 3.0),  # ciel : saturation des couleurs
    "sky_brightness": (1.05, 1.0, 1.3),  # ciel : luminance x
    "fog_intensity": (0.5, 0.0, 1.0),   # FogCloudIntensity x
}
DEFAULT_PRESET = {k: d for k, (d, _lo, _hi) in PRESET_SPECS.items()}


def normalize_preset(raw: object) -> Dict[str, float]:
    """Facteurs complets et bornes respectees : valeurs manquantes ou non
    numeriques -> defaut (une setting corrompue ne doit jamais casser la
    transformation)."""
    out: Dict[str, float] = {}
    for key, (dflt, lo, hi) in PRESET_SPECS.items():
        v = raw.get(key) if isinstance(raw, dict) else None
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = dflt
        out[key] = max(lo, min(hi, v))
    return out


def load_stored_preset() -> Dict[str, float]:
    from core.settings import get_cartoon_preset
    return normalize_preset(get_cartoon_preset())


def save_preset(preset: Dict[str, float]) -> None:
    from core.settings import set_cartoon_preset
    set_cartoon_preset(normalize_preset(preset))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def scale_float(text: str, factor: float, lo: float, hi: float) -> str:
    return _fmt(_clamp(float(text) * factor, lo, hi))


def floor_float(text: str, cap: float) -> str:
    return _fmt(min(float(text), cap))


def spread_rgb_tuple(text: str, factor: float, lo: float = 0.0,
                     hi: float = 3.5) -> str:
    """« (2.81, 1.11, 2.37) » : teinte multipliee du terrain — ecarte les
    canaux autour de leur moyenne (saturer sans changer la luminance)."""
    nums = [float(x) for x in text.strip('()').split(',')]
    mean = sum(nums) / len(nums)
    out = [_clamp((n - mean) * factor + mean, lo, hi) for n in nums]
    return "(" + ", ".join(_fmt(v) for v in out) + ")"


def saturate_triplet(text: str, factor: float,
                     brightness: float = 1.05) -> str:
    """« 1, 0.43, 0.1 » (ciel/atmosphere/brouillard) : saturation HSV
    x facteur, luminance legerement montee. Valeur > 1 : refusee (le
    corpus vanilla ne depasse jamais 1 ; ne pas inventer de clamp)."""
    nums = [float(x) for x in text.split(',')]
    if not nums or max(nums) > 1.0:
        return text
    h, l, s = colorsys.rgb_to_hls(*[min(n, 1.0) for n in nums])
    if s <= 0.0:
        return text            # gris/blanc : rien a saturer, pas de reformat
    r, g, b = colorsys.hls_to_rgb(h, min(l * brightness, 1.0),
                                  min(s * factor, 1.0))
    return f"{r:.3f}, {g:.3f}, {b:.3f}"


def _terrain_rules(preset: Dict[str, float]) -> List[Tuple[str, object]]:
    """Paires (cle de surface, regle). Les BORNES DE SORTIE restent fixes
    (securite moteur) : seuls les facteurs du preset sont editables."""
    return [
        ("Saturation", lambda t: scale_float(t, preset["saturation"], 0.8, 2.5)),
        ("Smoothness", lambda t: floor_float(t, preset["smoothness_cap"])),
        ("NormalStrength",
         lambda t: scale_float(t, preset["normal"], 0.2, 1.0)),
        ("ReliefStrength",
         lambda t: scale_float(t, preset["relief"], 0.0, 0.5)),
        ("RGB", lambda t: spread_rgb_tuple(t, preset["rgb_spread"])),
    ]

# playfield yaml : colonne 0 uniquement (les cles imbriquees ou commentees
# d'autres sections ne doivent pas bouger)
_YAML_COLOR_KEYS = ("AtmosphereColor", "SkyColor", "SkyHorizonColor",
                    "FogColor")


def _quoted_line_re(key: str) -> "re.Pattern[str]":
    return re.compile(
        rf'^([ \t]*{re.escape(key)}[ \t]*:[ \t]*)"([^"]*)"(.*)$', re.M)


def _col0_line_re(key: str) -> "re.Pattern[str]":
    return re.compile(
        rf'^({re.escape(key)}[ \t]*:[ \t]*)"([^"]*)"(.*)$', re.M)


def _col0_number_re(key: str) -> "re.Pattern[str]":
    return re.compile(
        rf'^({re.escape(key)}[ \t]*:[ \t]*)(-?\d+(?:\.\d+)?)([ \t]*(?:#.*)?)$',
        re.M)


def transform_terrain_ecf(text: str,
                          preset: Dict[str, float] | None = None
                          ) -> Tuple[str, Dict[str, int]]:
    """Applique le preset aux surfaces d'un terrain.ecf. Retourne
    (texte, nb de lignes changees par cle)."""
    preset = normalize_preset(preset or {})
    stats: Dict[str, int] = {}
    out = text
    for key, rule in _terrain_rules(preset):
        rx = _quoted_line_re(key)
        n = 0

        def _sub(m, rule=rule):
            nonlocal n
            new = rule(m.group(2))
            if new != m.group(2):
                n += 1
            return f"{m.group(1)}\"{new}\"{m.group(3)}"

        out = rx.sub(_sub, out)
        if n:
            stats[key] = n
    return out, stats


def transform_playfield_yaml(text: str,
                             preset: Dict[str, float] | None = None
                             ) -> Tuple[str, Dict[str, int]]:
    """Sature les couleurs de ciel/brouillard et reduit la couverture de
    brouillard (FogCloudIntensity x facteur). Retourne (texte, stats)."""
    preset = normalize_preset(preset or {})
    stats: Dict[str, int] = {}
    out = text
    for key in _YAML_COLOR_KEYS:
        rx = _col0_line_re(key)
        n = 0

        def _sub(m):
            nonlocal n
            new = saturate_triplet(m.group(2), preset["sky_saturation"],
                                   preset["sky_brightness"])
            if new != m.group(2):
                n += 1
            return f"{m.group(1)}\"{new}\"{m.group(3)}"

        out = rx.sub(_sub, out)
        if n:
            stats[key] = n
    rx = _col0_number_re("FogCloudIntensity")
    n = 0

    def _sub_fog(m):
        nonlocal n
        new = scale_float(m.group(2), preset["fog_intensity"], 0.0, 1.0)
        if new != m.group(2):
            n += 1
        return f"{m.group(1)}{new}{m.group(3)}"

    out = rx.sub(_sub_fog, out)
    if n:
        stats["FogCloudIntensity"] = n
    return out, stats


# ---------------------------------------------------------------------------
# Orchestration — partagee par le CLI (tools/cartoon_look.py) et le dialogue
# ---------------------------------------------------------------------------

MARKER = "+cartoon_look_applique.txt"
TARGET_NAMES = ("terrain.ecf", "playfield_static.yaml",
                "playfield_dynamic.yaml")


def iter_targets(scenario: Path):
    playfields = scenario / "Playfields"
    if not playfields.is_dir():
        return
    for pf in sorted(playfields.iterdir()):
        if not pf.is_dir() or pf.name.startswith('+'):
            continue
        for name in TARGET_NAMES:
            path = pf / name
            if path.is_file():
                yield path


def _validate(path: Path, new: str) -> str:
    """Reparse le texte transforme avec le parseur de l'editeur ; retourne
    une chaine vide si le fichier reste lisible, l'erreur sinon."""
    tmp = path.with_suffix(path.suffix + ".cartoon_tmp")
    try:
        atomic_write_text(tmp, new)
        if path.name == "terrain.ecf":
            parse_ecf_file(tmp)
        else:
            parse_yaml_file(tmp)
        return ""
    except Exception as e:                      # noqa: BLE001 - rapport
        return f"{type(e).__name__}: {e}"
    finally:
        tmp.unlink(missing_ok=True)


def run_preset(scenario: str | Path, dry_run: bool = False,
               force: bool = False, no_sync: bool = False,
               preset: Dict[str, float] | None = None) -> Dict[str, object]:
    """Applique le preset cartoon (prevue, application, puis synchro
    production). Retourne un rapport :
    ok, error, marker_blocked, touched [(rel, lignes)], total, invalid,
    backup_dir, dry_run, prod, copied, bins."""
    preset = normalize_preset(preset or {})
    scenario = Path(scenario)
    rep: Dict[str, object] = {
        "ok": False, "error": "", "marker_blocked": False, "touched": [],
        "total": 0, "invalid": [], "backup_dir": "", "dry_run": dry_run,
        "prod": "", "copied": 0, "bins": 0}
    if not scenario.is_dir():
        rep["error"] = "scenario_missing"
        return rep
    if (scenario / MARKER).exists() and not force:
        rep["marker_blocked"] = True
        return rep

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = (Path(get_backup_root("scenario"))
                  / f"cartoon_look_{scenario.name}_{stamp}")
    touched: List[Tuple[str, int]] = []
    texts: Dict[str, str] = {}

    for path in iter_targets(scenario):
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.name == "terrain.ecf":
            new, stats = transform_terrain_ecf(text, preset)
        else:
            new, stats = transform_playfield_yaml(text, preset)
        if not stats:
            continue
        err = _validate(path, new)
        rel = path.relative_to(scenario).as_posix()
        if err:
            rep["invalid"].append(f"{rel} : {err}")   # type: ignore[union-attr]
            continue
        touched.append((rel, sum(stats.values())))
        texts[rel] = new

    rep["touched"] = touched                          # type: ignore[assignment]
    rep["total"] = sum(n for _r, n in touched)
    if dry_run:
        rep["ok"] = True
        return rep

    for rel, _n in touched:
        path = scenario / rel
        bdir = backup_dir / Path(rel).parent
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / path.name).write_bytes(path.read_bytes())
        atomic_write_text(path, texts[rel])
    (scenario / MARKER).write_text(
        f"preset cartoon applique le {stamp}\n"
        f"sauvegardes : {backup_dir}\n", encoding="utf-8")
    rep["backup_dir"] = str(backup_dir)

    if no_sync or not touched:
        rep["ok"] = True
        return rep
    prod = get_production_scenario_path(str(scenario))
    if prod:
        files = [(scenario / rel, 'modified') for rel, _n in touched]
        copied, _deleted, bins, _saved = sync_to_production(
            files, scenario, prod, backup_dir=backup_dir / "_production")
        rep["prod"] = prod
        rep["copied"] = copied
        rep["bins"] = bins
    rep["ok"] = True
    return rep


def list_backups() -> List[Path]:
    """Dossiers de sauvegarde cartoon_look_* du repertoire de sauvegardes
    — un par passe, nomme avec le scenario et l'horodatage (cumul)."""
    root = Path(get_backup_root("scenario"))
    if not root.is_dir():
        return []
    return [p for p in sorted(root.glob("cartoon_look_*")) if p.is_dir()]


def restore_backup(scenario: str | Path, backup_dir: str | Path,
                   no_sync: bool = False) -> Dict[str, object]:
    """Remonte l'etat sauvegarde (arborescence hors _production) dans la
    copie de travail, retire le marqueur (l'etat restaure peut etre
    pre-cartoon) puis resynchronise ces fichiers vers la production
    (caches .bin invalides par la meme occasion)."""
    scenario = Path(scenario)
    backup_dir = Path(backup_dir)
    rep: Dict[str, object] = {"ok": False, "error": "", "copied": 0,
                              "prod": "", "bins": 0}
    if not backup_dir.is_dir():
        rep["error"] = "backup_missing"
        return rep
    files = [p for p in sorted(backup_dir.rglob("*"))
             if p.is_file()
             and "_production" not in p.relative_to(backup_dir).parts]
    if not files:
        rep["error"] = "backup_empty"
        return rep
    for p in files:
        rel = p.relative_to(backup_dir)
        dest = scenario / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        rep["copied"] = rep["copied"] + 1
    (scenario / MARKER).unlink(missing_ok=True)
    prod = get_production_scenario_path(str(scenario))
    if prod and not no_sync:
        sources = [(scenario / p.relative_to(backup_dir), 'modified')
                   for p in files]
        copied, _deleted, bins, _saved = sync_to_production(
            sources, scenario, prod)
        rep["prod"] = prod
        rep["bins"] = bins
        rep["copied"] = copied
    rep["ok"] = True
    return rep


_NAME_RE = re.compile(r'^[ \t]+Name:[ \t]*"([^"]*)"')
_RGB_RE = re.compile(r'^[ \t]+RGB:[ \t]*"([^"]*)"')


def _terrain_rgb_pairs(text: str) -> List[Tuple[str, str]]:
    """[(surface, valeur RGB)] dans l'ordre du fichier (Name quoté des
    Child ; le Name non quoté du bloc racine ne compte pas)."""
    pairs: List[Tuple[str, str]] = []
    name = ""
    for line in text.splitlines():
        mn = _NAME_RE.match(line)
        if mn:
            name = mn.group(1)
            continue
        mr = _RGB_RE.match(line)
        if mr:
            pairs.append((name, mr.group(1)))
    return pairs


def preview_colors(scenario: str | Path, pf_name: str,
                   preset: Dict[str, float] | None = None
                   ) -> Dict[str, List[Tuple[str, str, str]]]:
    """Couleurs d'ORIGINE vs PRESET pour un playfield, sans rien ecrire :
    {"ciel": [(cle, old, new)], "terrain": [(surface, old, new)]} — seules
    les paires qui changent sont liste."""
    pf = Path(scenario) / "Playfields" / pf_name
    sky: List[Tuple[str, str, str]] = []
    terrain: List[Tuple[str, str, str]] = []
    ypath = pf / "playfield_static.yaml"
    if ypath.is_file():
        text = ypath.read_text(encoding="utf-8", errors="replace")
        new, _s = transform_playfield_yaml(text, preset)
        for key in _YAML_COLOR_KEYS:
            mo = _col0_line_re(key).search(text)
            mn = _col0_line_re(key).search(new)
            if mo and mn and mo.group(2) != mn.group(2):
                sky.append((key, mo.group(2), mn.group(2)))
    tpath = pf / "terrain.ecf"
    if tpath.is_file():
        text = tpath.read_text(encoding="utf-8", errors="replace")
        new, _s = transform_terrain_ecf(text, preset)
        olds = _terrain_rgb_pairs(text)
        news = _terrain_rgb_pairs(new)
        for (name, old), (_n2, newv) in zip(olds, news):
            if old != newv:
                terrain.append((name, old, newv))
    return {"ciel": sky, "terrain": terrain}
