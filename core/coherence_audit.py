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

"""Contrôle de cohérence GLOBAL du scénario : lance tous les moteurs
d'analyse en LECTURE SEULE et consolide les constats en une liste de
constatations (domaine, sévérité, nombre, détails, module de correction
conseillé). Aucune écriture — les corrections restent dans les modules
dédiés (cf. fix_tool de chaque constatation).

Sections : bilan F5 (erreurs moteur), boucles d'argent marchands,
disparités marchands, prix marché vs coût (politique prix = coût),
propositions famille en attente, recettes incohérentes, UnlockCost
incohérents, corrélations stats, zones de spawn incohérentes, playfields
sans spawn. Chaque moteur est isolé : un échec ne compromet pas les autres.
Politique économique appliquée à l'analyse : prix = coût (marge 1.0, fab 0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

SEV_ERROR = "error"
SEV_WARNING = "warning"
SEV_INFO = "info"


@dataclass
class Finding:
    """Une constatation par domaine : clé i18n de section, sévérité,
    nombre d'occurrences, détails (lignes texte), module de correction."""
    section: str                 # 'coh.sec.xxx' — libellé via t()
    severity: str                # error | warning | info
    count: int
    detail: str = ""             # resume (noms/exemples, pour l'export)
    items: List[str] = field(default_factory=list)
    fix_tool: str = ""           # libellé du module de correction (i18n)


@dataclass
class CoherenceReport:
    root: str = ""
    findings: List[Finding] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def errors(self) -> int:
        return sum(f.count for f in self.findings if f.severity == SEV_ERROR)

    @property
    def warnings(self) -> int:
        return sum(f.count for f in self.findings if f.severity == SEV_WARNING)

    def by_severity(self, sev: str) -> List[Finding]:
        return [f for f in self.findings if f.severity == sev]


def _top(items: List[str], n: int = 5) -> str:
    return " ; ".join(x[:40] for x in items[:n])


def run_coherence_audit(root, vanilla_root: str = "") -> CoherenceReport:
    import time
    t0 = time.time()
    root = str(root)
    rep = CoherenceReport(root=root)

    def add(section, severity, count, detail="", items=None, fix=""):
        if count == 0:
            severity = SEV_INFO       # "aucune anomalie" : rassure, sans alerte
        rep.findings.append(Finding(section, severity, count, detail,
                                    items or [], fix))

    # ---- 1. bilan F5 : erreurs moteur ----------------------------------
    try:
        from core.launch_check import run_launch_checks
        issues = run_launch_checks(Path(root), vanilla_root)
        errs = [i for i in issues if i.severity == "error"]
        add("coh.sec.f5_errors", SEV_ERROR, len(errs),
            _top([i.message[:60] for i in errs], 3),
            [i.message for i in errs], "coh.fix.f5_errors")
        warn = [i for i in issues if i.severity == "warning"]
        hi = [i for i in warn if "higher tier" in i.message]
        zones = [i for i in warn if "W31" in i.message]
        add("coh.sec.f5_tech_progress", SEV_WARNING, len(hi),
            _top([i.message[i.message.find(":", 60) + 2:] for i in hi], 4),
            [i.message for i in hi], "coh.fix.f5_tech")
        add("coh.sec.f5_misc", SEV_INFO, len(warn) - len(hi) - len(zones),
            "detail dans le bilan F5 (export CSV)", [],
            "coh.fix.f5_misc")
    except Exception as e:                      # noqa: BLE001 - section isolee
        add("coh.sec.f5_errors", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    # ---- 2. marchands : boucles d'argent + disparites -------------------
    try:
        from core.trader_audit import analyze_traders
        _doc, _midx, tr = analyze_traders(root)
        d = tr.dashboard
        add("coh.sec.trader_loops", SEV_ERROR, len(d.arbitrages),
            _top(d.arbitrages, 4), list(d.arbitrages)[:10],
            "coh.fix.trader_loops")
        add("coh.sec.trader_disparities", SEV_INFO, len(d.disparities),
            f"max x{d.max_disparity:.2f} ; " + _top(d.disparities, 4),
            list(d.disparities)[:10], "coh.fix.trader_disparities")
    except Exception as e:                      # noqa: BLE001
        add("coh.sec.trader_loops", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    # ---- 3. prix marche vs cout (politique prix = cout) -----------------
    fam_n = 0
    try:
        from core.market_balance import build_report, load_index
        idx, _van = load_index(root, vanilla_root)
        mrep = build_report(idx)                # marge 1.0, fab 0
        div = [e for e in mrep.entries
               if e.target is not None and e.price is not None
               and e.price != e.target]
        div.sort(key=lambda e: abs((e.price or 0) - (e.cost or 0)),
                 reverse=True)
        cout_nul = [e for e in div if not e.cost]
        repris = [e for e in div if e.cost]
        add("coh.sec.market_cost0", SEV_INFO, len(cout_nul),
            _top([f"{e.name} (prix {e.price}, recette gratuite/cosmetique)"
                  for e in cout_nul], 4),
            [e.name for e in cout_nul], "coh.fix.market_cost0")
        add("coh.sec.market_divergent", SEV_WARNING, len(repris),
            _top([f"{e.name} : {e.price} vs {round(e.cost or 0, 1)}"
                  for e in repris], 4), [e.name for e in repris],
            "coh.fix.market_divergent")
        fam = [e for e in mrep.entries if e.status == "famille"]
        fam_n = len(fam)
        add("coh.sec.market_famille", SEV_INFO, fam_n,
            _top([f"{e.name} : {e.price} -> {e.target}" for e in fam], 4),
            [e.name for e in fam], "coh.fix.market_famille")
    except Exception as e:                      # noqa: BLE001
        add("coh.sec.market_divergent", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    # ---- 4. recettes vs puissance ---------------------------------------
    try:
        from core.recipe_balance import analyze as rb_analyze
        props = rb_analyze(root, vanilla_root)
        changed = [p for p in props if p.changed]
        changed.sort(key=lambda p: abs(getattr(p, "ratio", 1.0) or 1.0),
                     reverse=True)
        add("coh.sec.recipes", SEV_WARNING, len(changed),
            _top([f"{getattr(p, 'name', '?')} "
                  f"(x{round(getattr(p, 'ratio', 0) or 0, 2)})" for p in changed], 4),
            [getattr(p, "name", "?") for p in changed],
            "coh.fix.recipes")
    except Exception as e:                      # noqa: BLE001
        add("coh.sec.recipes", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    # ---- 5. UnlockCost ----------------------------------------------------
    try:
        from core.unlock_balance import analyze as ub_analyze
        ups = ub_analyze(root, vanilla_root)
        changed = [u for u in ups if u.changed]
        add("coh.sec.unlocks", SEV_WARNING, len(changed),
            _top([f"{getattr(u, 'name', '?')} : "
                  f"{getattr(u, 'detail', '')[:40]}" for u in changed], 4),
            [getattr(u, "name", "?") for u in changed],
            "coh.fix.unlocks")
    except Exception as e:                      # noqa: BLE001
        add("coh.sec.unlocks", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    # ---- 6. correlations stats --------------------------------------------
    try:
        from core.correlation_balance import SPECS, analyze_correlations
        for key in SPECS:
            _cidx, corr = analyze_correlations(root, key)
            outliers = sum(corr.counts.get(k, 0)
                           for k in ("outlier", "zero", "ok") if k != "ok")
            outliers = sum(corr.counts.get(k, 0) for k in ("outlier",))
            zero = corr.counts.get("zero", 0)
            if outliers or zero:
                add("coh.sec.corr_" + key, SEV_WARNING, outliers + zero,
                    f"outliers {outliers}, valeurs a zero {zero}",
                    [], "coh.fix.corr")
    except Exception as e:                      # noqa: BLE001
        add("coh.sec.corr", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    # ---- 7. zones de spawn incoherentes (W310/W311) ------------------------
    zero_pf: List[str] = []
    try:
        from core.spawn_waves import check_spawn_consistency, scan
        scanres = scan(Path(root))
        issues = check_spawn_consistency(Path(root))
        add("coh.sec.spawn_zones", SEV_WARNING, len(issues),
            _top([f"{i.playfield}: {i.message[:40]}"
                  for i in issues[:40] if hasattr(i, "playfield")], 4),
            [], "coh.fix.spawn_zones")
        zero_pf = [s.playfield for s in scanres.summaries
                   if s.poi_max == 0 and s.vessels_max == 0
                   and s.drones_max == 0]
        add("coh.sec.spawn_zero", SEV_INFO, len(zero_pf),
            _top(zero_pf, 8), zero_pf, "coh.fix.spawn_zero")
    except Exception as e:                      # noqa: BLE001
        add("coh.sec.spawn_zones", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    # ---- 8. progression : danger vs medianes -------------------------------
    try:
        from core.progression_balance import scan as prog_scan
        prog = prog_scan(Path(root))
        meds = {k: round(v, 1) for k, v in prog.playfield_medians.items()}
        add("coh.sec.progression", SEV_INFO, len(prog.playfields),
            f"medianes par type : {meds}", [],
            "coh.fix.progression")
    except Exception as e:                      # noqa: BLE001
        add("coh.sec.progression", SEV_WARNING, 1,
            f"{type(e).__name__}: {e}", [], "")

    rep.seconds = time.time() - t0
    return rep
