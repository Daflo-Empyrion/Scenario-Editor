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
"""Traduction FR directe du PDA du scenario RE2-RPG (chantier 08/10).

Usage (depuis la racine du depot) :
    python tools/trad_re2rpg.py extract <chain_id>
        -> ecrit _lot.json (textes uniques du chapitre, ordre de
           l'arbre) + stats ; les deja traduits sont lists.
    python tools/trad_re2rpg.py merge <fichier.tsv>
        -> TSV `index<TAB>FR` (meme ordre que _lot.json) ; fusion
           SURGICALE ligne a ligne dans le PDA.csv du projet fige
           C:\\Dev\\RE2-RPG, backup central AVANT, puis verification
           (balises BBCode, placeholders {...}, sequences \\n).

Regles glossaire (decision 08/10) : noms propres (systemes, POI,
vaisseaux, classes de drones, items de recompense) restent EN ; noms
communs traduits ; « warp » inchange. Lecture du CSV en BYTES
(Path.read_text traduirait CRLF->LF, piege vecu)."""
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RE2RPG = Path(r"C:\Dev\RE2-RPG")
PDA_CSV = RE2RPG / "Extras" / "PDA" / "PDA.csv"
PDA_YAML = RE2RPG / "Extras" / "PDA" / "PDA.yaml"
FR_COL = 3   # colonne « Français »


def _extract(chain: str) -> None:
    from core.yamllite.parser import parse_yaml_file
    from core.yamllite.model import YamlEntry
    pda = parse_yaml_file(PDA_YAML)

    nodes = []

    def walk(node_list, inside):
        for n in node_list:
            if not isinstance(n, YamlEntry):
                continue
            hit = inside or (n.value or "").strip() == chain \
                or (n.key or "") == chain
            if hit:
                nodes.append(n)
            walk(n.children, hit)

    walk(pda.nodes, False)
    if not nodes:
        sys.exit(f"chapitre introuvable : {chain}")

    with io.open(PDA_CSV, encoding="utf-8", errors="replace") as f:
        rows = {r["KEY"].strip(): (r.get("English") or "",
                                   r.get("Français") or "")
                for r in csv.DictReader(f)}

    lot, seen_en, seen_key = [], {}, set()
    for n in nodes:
        for v in (n.key, n.value):
            t = (v or "").strip()
            if not t or t in seen_key or t not in rows:
                continue
            seen_key.add(t)
            en, fr = rows[t]
            if not en.strip():
                continue
            if en not in seen_en:
                seen_en[en] = len(lot)
                lot.append({"en": en, "keys": []})
            lot[seen_en[en]]["keys"].append(t)
    already = sum(1 for item in lot
                  if all(rows[k][1].strip() for k in item["keys"]))
    Path("_lot.json").write_text(json.dumps(lot, ensure_ascii=False,
                                            indent=1), encoding="utf-8")
    print(f"cles CSV: {len(lot)} -> {sum(len(i['keys']) for i in lot)} "
          f"| textes uniques: {len(lot)} | deja traduits: {already}")
    print("ecrit: _lot.json")


def _verify(text: str, lot: list, key_map: dict, fr_by_index: dict) -> None:
    rows = list(csv.reader(io.StringIO(text)))
    lot_keys = {k.strip() for item in lot for k in item["keys"]}
    filled = bad_tags = bad_ph = bad_nl = 0
    for r in rows[1:]:
        if not (r and r[0].strip() in lot_keys and (r[FR_COL] or "").strip()):
            continue
        filled += 1
        en, fr = r[1] or "", r[FR_COL] or ""
        if len(re.findall(r"\[/?c\]|\[-\]|\[/?b\]|\[/?i\]", fr)) != \
                len(re.findall(r"\[/?c\]|\[-\]|\[/?b\]|\[/?i\]", en)):
            bad_tags += 1
        if re.findall(r"\{[A-Za-z_.()]+\}", en) != \
                re.findall(r"\{[A-Za-z_.()]+\}", fr):
            bad_ph += 1
        if en.count("\\n") != fr.count("\\n"):
            bad_nl += 1
    print(f"verification : {filled}/{len(lot_keys)} remplies | "
          f"balises alterees: {bad_tags} | placeholders: {bad_ph} | "
          f"\\n: {bad_nl}")
    if bad_tags or bad_ph or bad_nl:
        sys.exit("INTEGRITE KO : corriger le TSV avant de re-fusionner.")


def _extract_all() -> None:
    """TOUT le restant non traduit (toutes chaines, y compris les
    chapitres-groupes « norm;N|token » que _extract ne voit pas),
    deduplique par texte, tri par KEY pour stabilite inter-sessions."""
    with io.open(PDA_CSV, encoding="utf-8", errors="replace") as f:
        rows = {r["KEY"].strip(): (r.get("English") or "",
                                   r.get("Français") or "")
                for r in csv.DictReader(f) if r.get("KEY")}
    lot, seen = [], {}
    for key in sorted(rows):
        en, fr = rows[key]
        if not en.strip() or fr.strip():
            continue
        if en in seen:
            lot[seen[en]]["keys"].append(key)
            continue
        seen[en] = len(lot)
        lot.append({"en": en, "keys": [key]})
    Path("_lot.json").write_text(json.dumps(lot, ensure_ascii=False,
                                            indent=1), encoding="utf-8")
    print(f"lignes restantes: {sum(len(i['keys']) for i in lot)} | "
          f"textes uniques: {len(lot)} -> _lot.json")


def _merge(tsv_path: str) -> None:
    lot = json.loads(Path("_lot.json").read_text(encoding="utf-8"))
    fr_by_index = {}
    for line in Path(tsv_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            idx, fr = line.split("\t", 1)
            fr_by_index[int(idx)] = fr
    manquants = len(lot) - len(fr_by_index)
    if manquants > 0:
        print(f"lot partiel : {len(fr_by_index)}/{len(lot)} traduits "
              f"({manquants} restants apres fusion)")
    key_map = {}
    for i, item in enumerate(lot):
        for key in item["keys"]:
            key_map[key.strip()] = (i, item["en"])

    from core.fsutil import central_backup
    print("backup:", central_backup(PDA_CSV, kind="pda").name)

    text = PDA_CSV.read_bytes().decode("utf-8")     # bytes : EOL preserves
    assert "\r\n" in text, "EOL inattendu"
    lines = text.split("\r\n")
    trailing = lines and lines[-1] == ""
    if trailing:
        lines = lines[:-1]
    assert len(lines) == len(list(csv.reader(io.StringIO(text)))), \
        "champs multilignes : fusion ligne a ligne impossible"

    changed, skipped = 0, []
    for i, line in enumerate(lines):
        if i == 0 or not line.strip():
            continue
        fields = next(csv.reader([line]))
        key = (fields[0] or "").strip()
        if key not in key_map:
            continue
        idx, expected_en = key_map[key]
        if idx not in fr_by_index:
            continue            # lot partiel : index traduit plus tard
        if (fields[1] or "").strip() != expected_en.strip():
            skipped.append((key, "EN a change")); continue
        if (fields[FR_COL] or "").strip():
            skipped.append((key, "FR deja presente")); continue
        fields[FR_COL] = fr_by_index[idx]
        out = io.StringIO()
        csv.writer(out, quoting=csv.QUOTE_MINIMAL,
                   lineterminator="").writerow(fields)
        lines[i] = out.getvalue()
        changed += 1
    print(f"traductions ecrites: {changed} | ignorees: {len(skipped)}")
    for key, why in skipped[:5]:
        print("  skip:", key, "-", why)
    PDA_CSV.write_bytes("\r\n".join(
        lines + ([""] if trailing else [])).encode("utf-8"))
    _verify(PDA_CSV.read_bytes().decode("utf-8"), lot, key_map, fr_by_index)
    print("PDA.csv mis a jour.")


def _list(top: int = 25) -> None:
    """Top des chapitres comptant le plus de lignes non traduites, avec
    l'etat global — designe automatiquement la suite du chantier."""
    from core.yamllite.parser import parse_yaml_file
    from core.yamllite.model import YamlEntry
    with io.open(PDA_CSV, encoding="utf-8", errors="replace") as f:
        rows = {r["KEY"].strip(): (r.get("English") or "",
                                   r.get("Français") or "")
                for r in csv.DictReader(f) if r.get("KEY")}
    pda = parse_yaml_file(PDA_YAML)
    ch_root = next((n for n in pda.nodes
                    if isinstance(n, YamlEntry) and n.key == "Chapters"), None)
    stats = []
    for ch in (c for c in ch_root.children
               if isinstance(c, YamlEntry) and c.is_sequence_item):
        tokens = set()

        def collect(entry):
            for v in (entry.key, entry.value):
                t = (v or "").strip()
                if t and t not in tokens:
                    tokens.add(t)
            for c in entry.children:
                if isinstance(c, YamlEntry):
                    collect(c)

        collect(ch)
        title = next(iter(tokens), "?")
        todo = sum(1 for t in tokens if t in rows
                   and rows[t][0].strip() and not rows[t][1].strip())
        if todo:
            stats.append((todo, title))
    stats.sort(reverse=True)
    total_todo = sum(s for s, _ in stats)
    print(f"chapitres avec du restant: {len(stats)} | lignes restantes: {total_todo}")
    for todo, title in stats[:top]:
        print(f"  {todo:4d} lignes restantes | {title}")


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    command = sys.argv[1]
    if command == "extract":
        _extract(sys.argv[2])
    elif command == "extract-all":
        _extract_all()
    elif command == "merge":
        _merge(sys.argv[2])
    elif command == "list":
        _list(int(sys.argv[2]) if len(sys.argv) > 2 else 25)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
