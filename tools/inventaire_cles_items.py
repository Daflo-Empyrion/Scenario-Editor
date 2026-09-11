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

"""Inventaire des cles de proprietes ECF qui REFERENCENT des items.

But (decision UX 10/09/2026) : preparer le "retrofit catalogue" en listant,
par scenario (RE2 EVO, Atlantis x3, vanille), toutes les cles dont les
valeurs contiennent un nom d'item connu (ItemsConfig + BlocksConfig du
scenario + vanille). Pour chaque (fichier, cle) : nombre de valeurs,
valeurs contenant un item (ratio), types de blocs, exemples.

Les fichiers de DEFINITION (ItemsConfig.ecf, BlocksConfig.ecf) sont exclus
du scan : leur 'Name: X' EST la definition de l'item, pas une reference.

Usage :
    python tools/inventaire_cles_items.py            # rapport markdown complet
    python tools/inventaire_cles_items.py --max 15   # exemples tronques
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.ecf.model import EcfBlock, EcfProperty  # noqa: E402
from core.ecf.parser import parse_ecf_file  # noqa: E402

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Empyrion - Galactic Survival")
# Racines de scan : selon les scenarios, SharedData/ et Playfields/ sont a la
# racine ou sous Content/ -- on scanne la racine, le filtre *.ecf fait le trie.
CORPORA = {
    "RE2 EVO": GAME / "Content" / "Scenarios" / "RE2 EVO",
    "Atlantis": Path(r"C:\Dev\atlantis"),
    "Atlantis next": Path(r"C:\Dev\atlantis next"),
    "Atlantis pro": Path(r"C:\Dev\atlantis pro"),
    "Vanille": GAME / "Content",
}
# Fichiers de definition : leur 'Name:' definit un item, ce n'est pas une
# reference a analyser.
DEFINITION_FILES = {"itemsconfig.ecf", "blocksconfig.ecf"}
# Dossiers jamais scannes (binaires, doublons de scenarios, ressources).
EXCLUDED_DIRS = {"scenarios", "bundles", "noise", "terrains", "stamps",
                 "mods", "prefabs", "prefabsstock"}
# Fichiers de definition des items, par corpus (scenario + vanille en repli).
ITEM_SOURCES = ("ItemsConfig.ecf", "BlocksConfig.ecf")


def _ecf_files(content_dir: Path):
    for p in content_dir.rglob("*.ecf"):
        if any(part.lower() in EXCLUDED_DIRS for part in p.relative_to(content_dir).parts[:-1]):
            continue
        if p.name.lower() in DEFINITION_FILES:
            continue
        yield p


def _names_from_config(path: Path) -> set:
    """Noms d'items d'un fichier de definition (blocs avec Id + Name)."""
    names = set()
    try:
        doc = parse_ecf_file(path)
    except Exception:
        return names
    stack = list(doc.nodes)
    while stack:
        node = stack.pop()
        if not isinstance(node, EcfBlock):
            continue
        stack.extend(node.children)
        name = node.get("Name")
        if name:
            names.add(name.strip().strip('"'))
    return names


def item_names_for(content_dir: Path, vanilla_config: Path) -> set:
    """Union des noms d'items : config du scenario + config vanille."""
    names = set()
    config = content_dir / "Content" / "Configuration"
    if not config.exists():
        config = content_dir / "Configuration"
    for source in ITEM_SOURCES:
        for base in (config, vanilla_config):
            p = base / source
            if p.exists():
                names |= _names_from_config(p)
    return {n for n in names if n}


def build_pattern(names: set):
    """Un seul regex alternation (noms les plus longs d'abord) : un passage
    par valeur suffit, des milliers de noms."""
    ordered = sorted((re.escape(n) for n in names), key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9_-])(" + "|".join(ordered) + r")(?![A-Za-z0-9_-])")


def scan_corpus(label: str, content_dir: Path, vanilla_config: Path,
                max_examples: int):
    names = item_names_for(content_dir, vanilla_config)
    if not names:
        print(f"[{label}] AUCUN nom d'item -- corpus ignore", file=sys.stderr)
        return None
    pattern = build_pattern(names)
    # (fichier, cle) -> stats
    stats = defaultdict(lambda: {"total": 0, "hits": 0, "blocks": set(),
                                 "examples": []})
    n_files = 0
    for path in _ecf_files(content_dir):
        rel = path.relative_to(content_dir)
        try:
            doc = parse_ecf_file(path)
        except Exception as e:
            print(f"[{label}] parse KO {rel}: {e}", file=sys.stderr)
            continue
        n_files += 1

        def walk(nodes, context):
            for node in nodes:
                if isinstance(node, EcfBlock):
                    kind = node.kind.lstrip("+").strip()
                    walk(node.children, f"{context}>{kind}" if context else kind)
                elif isinstance(node, EcfProperty):
                    for key, value in node.pairs:
                        if key is None:
                            continue
                        value = value.strip().strip('"')
                        if not value or len(value) > 300:
                            continue
                        entry = stats[(str(rel), key)]
                        entry["total"] += 1
                        if pattern.search(value):
                            entry["hits"] += 1
                            entry["blocks"].add(context or "-")
                            if len(entry["examples"]) < max_examples:
                                entry["examples"].append(value[:80])

        walk(doc.nodes, "")
    print(f"[{label}] {n_files} fichiers ECF, {len(names)} noms d'items",
          file=sys.stderr)
    return {"label": label, "names": len(names), "files": n_files,
            "stats": {k: {**v, "blocks": sorted(v["blocks"])}
                      for k, v in stats.items() if v["hits"] > 0}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=8, help="exemples par cle")
    ap.add_argument("-o", "--out", default=str(PROJECT_ROOT / "inventaire_cles_items.md"))
    args = ap.parse_args()

    vanilla_config = GAME / "Content" / "Configuration"
    results = []
    for label, content_dir in CORPORA.items():
        if not content_dir.exists():
            print(f"[{label}] introuvable : {content_dir}", file=sys.stderr)
            continue
        r = scan_corpus(label, content_dir, vanilla_config, args.max)
        if r:
            results.append(r)

    # ---- rapport markdown
    lines = ["# Inventaire des cles ECF referencant des items",
             "",
             "Rapport genere par `tools/inventaire_cles_items.py` (retrofit"
             " catalogue, decision UX). Une valeur \"item\" contient au moins"
             " un nom d'item connu (ItemsConfig + BlocksConfig du scenario"
             " et de la vanille).",
             ""]
    for r in results:
        lines += [f"## {r['label']}", "",
                  f"{r['files']} fichiers ECF scannes, {r['names']} noms"
                  " d'items connus. Cles triees par nombre de valeurs item.",
                  "",
                  "| fichier | cle | valeurs | item | % | blocs | exemples |",
                  "|---|---|---:|---:|---:|---|---|"]
        ranked = sorted(r["stats"].items(),
                        key=lambda kv: (-kv[1]["hits"], kv[0]))
        for (rel, key), s in ranked:
            if s["hits"] < 2:
                continue  # bruit : valeurs isolees
            pct = int(100 * s["hits"] / s["total"]) if s["total"] else 0
            blocks = ", ".join(sorted(b.split(">")[-1] for b in s["blocks"])[:4])
            ex = "<br>".join(e.replace("|", "\\|") for e in s["examples"][:3])
            lines.append(f"| {rel} | {key} | {s['total']} | {s['hits']} "
                         f"| {pct}% | {blocks} | {ex} |")
        lines.append("")
    # ---- synthese multi-scenarios : cles presentees partout
    by_key = defaultdict(dict)
    for r in results:
        for (rel, key), s in r["stats"].items():
            by_key[key][r["label"]] = (rel, s["hits"])
    lines += ["## Synthese : cles candidates par scenario", "",
              "| cle | " + " | ".join(r["label"] for r in results) + " |",
              "|---" * (len(results) + 1) + "|"]
    for key in sorted(by_key, key=lambda k: -sum(
            v[1] for v in by_key[k].values())):
        row = [key]
        for r in results:
            v = by_key[key].get(r["label"])
            row.append(f"{v[0]} ({v[1]})" if v else "-")
        lines.append("| " + " | ".join(row) + " |")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"rapport : {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
