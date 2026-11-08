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

"""Genere data/propriete_glossary.json (FR) depuis docs/glossaire_proprietes.md.

La source de verite est le markdown du glossaire ; ce script le parse en
donnees indexables pour les infobulles de l'application (consommation via
core/propriete_glossary.py). La version EN (data/propriete_glossary.en.json)
est redigee a la main, meme ordre que le FR ; a relire apres TOUTE evolution
du glossaire (le test tests/test_propriete_glossary.py fait echouer la suite
si le EN n'est plus en synchro).

Rappels de parsing (contracte avec la redaction du glossaire) :
- lignes de table `| nom | ... | explication |` : 1re cellule = nom(s) de
  propriete ou chemin complet (split ' / ' pour les noms groupes), DERNIERE
  cellule = explication, cellules intermediaires = detail ;
- la section courante (# / ##) determine le scope et le fichier ECF
  (les titres 5.x contiennent 'NomFichier.ecf') ;
- la section 10 (noms employes comme DONNEES) n'est pas indexee.

    python tools/build_propriete_glossary.py            # ecrit
    python tools/build_propriete_glossary.py --check    # compare sans ecrire
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "glossaire_proprietes.md"
DEST = ROOT / "data" / "propriete_glossary.json"

# Contenu d'une cellule "nom" acceptable : mots ASCII lettre/underscore,
# points, crochets, etoiles (chemins YAML) -- rejette la prose (accents,
# parentheses de commentaire sans nom...).
NAME_RE = re.compile(r"^[A-Za-z_][\w\.\[\]]*( [A-Za-z_][\w\.\[\]]*)*$")

# Vocabulaire des EN-TETES de tables : une ligne dont TOUTES les cellules
# sont dans ce vocabulaire est un en-tete (jamais une donnee). Les colonnes
# 'Sens'/'Explication'/'Detail'/'Signification' designent la colonne
# d'explication ; 'Valeurs observées' etc. restent des details.
HEADER_WORDS = {
    "propriété", "propriete", "sens", "type/défaut moteur", "type/defaut moteur",
    "défaut moteur", "defaut moteur", "clé", "cle", "clé du bloc", "cle du bloc",
    "piège", "piece", "détail", "detail", "signification", "explication",
    "valeurs observées", "valeurs observees", "valeur", "valeur cible", "key",
    "enfant/clé", "enfant/cle", "section", "id", "champ", "type", "genre",
    "exemples", "fichier", "paramètre", "parametre", "enfant", "noms", "name",
    "description", "colonnes", "catégorie", "categorie", "utilisation",
    "défauts", "defauts", "types", "défaut", "defaut",
}
EXPCOL_WORDS = {"sens", "explication", "détail", "detail", "signification"}

# Section (titre sans les '#' initiaux) -> (scope, fichier force ou None).
SECTION_RULES = [
    ("1.", ("yaml", None)),
    ("2.", ("yaml", None)),
    ("3.", ("sector", None)),
    ("4.", ("gameoptions", None)),
    ("5.", ("ecf", None)),      # le fichier vient du titre ## 5.x
    ("6.", ("ecf", "terrain.ecf")),
    ("7.", ("epb", None)),
    ("8.", ("pda", None)),
    ("9.", ("general", None)),
]


def _clean(cell: str) -> str:
    """Nettoie une cellule : markdown leger, espaces."""
    cell = cell.strip()
    cell = re.sub(r"\*\*(.+?)\*\*", r"\1", cell)
    cell = cell.replace("`", "")
    return cell.strip()


def _section_key(heading: str) -> str:
    """Titre de section sans les '#' initiaux ni espaces ('## 5.1 X' -> '5.1 X')."""
    return heading.lstrip("#").strip()


def _scope_and_file(heading: str) -> "tuple[str, str | None] | None":
    if not heading:
        return None
    key = _section_key(heading)
    if key.startswith("10."):
        return None
    for prefix, rule in SECTION_RULES:
        if key.startswith(prefix):
            scope, forced_file = rule
            if scope == "ecf" and not forced_file:
                m = re.search(r"([A-Za-z]+\.ecf)", key)
                return ("ecf", m.group(1) if m else None)
            return (scope, forced_file)
    return None


def _is_data_row(name_cell: str) -> bool:
    """True si la 1re cellule n'est pas un nom de propriete exploitable
    (prose, phrase francaise, exemple de valeur...)."""
    if not name_cell or name_cell in ("---", "…"):
        return False
    if not NAME_RE.match(name_cell):
        return False
    # prose multi-mots tout en minuscules (ex. 'couches souterraines')
    words = name_cell.split()
    if len(words) >= 3 and name_cell == name_cell.lower():
        return True
    return False


def parse_glossary(md_text: str) -> dict:
    props = {}          # cle de fusion (name.lower(), scope, file) -> entree
    file_descriptions = {}
    heading = ""
    section_prose = []  # paragraphes de la section courante (hors tables/code)
    in_code = False
    exp_col = None      # colonne d'explication de la table courante (déf. dernière)

    for raw in md_text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        if line.startswith("#"):
            # nouvelle section : on fige la description de fichier de la
            # section precedente (1er paragraphe de prose non vide)
            _freeze_file_description(heading, section_prose, file_descriptions)
            heading = line.strip()
            section_prose = []
            continue

        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in
                     re.split(r"(?<!\\)\|", stripped.strip("|"))]
            if len(cells) < 2:
                continue
            # les '\|' litteraux du markdown redeviennent des '|'
            cells = [c.replace("\\|", "|") for c in cells]
            # table a colonne Id numerique (section EPB) : le nom est en 2e cellule
            if len(cells) >= 3 and re.fullmatch(r"\d+", cells[0]):
                cells = cells[1:]
            first = _clean(cells[0])
            if set(first) <= set("-: "):
                continue  # ligne de separation
            # en-tete de table : TOUTES les cellules dans le vocabulaire des
            # en-tetes -> memorise la colonne d'explication de CETTE table
            cleaned_cells = [_clean(c) for c in cells]
            if all(c.lower() in HEADER_WORDS for c in cleaned_cells if c):
                exp_col = next((i for i, c in enumerate(cleaned_cells)
                                if c.lower() in EXPCOL_WORDS),
                               len(cleaned_cells) - 1)
                continue
            if _is_data_row(first):
                continue
            # forme groupee 'PREFIX* (A, B, C)' -> une entree par nom
            grouped = re.match(r"^(\w+)\*\s*\((.+)\)$", first)
            if grouped:
                names_list = [n.strip() for n in grouped.group(2).split(",")]
            else:
                names_list = first.split(" / ")
            if exp_col is None or exp_col >= len(cells):
                exp_col = len(cells) - 1
            exp = _clean(cells[exp_col])
            detail = " · ".join(c for c in (_clean(c) for c in cells[1:] if c is not cells[exp_col]) if c)
            rule = _scope_and_file(heading)
            if not rule or not exp:
                continue
            scope, forced_file = rule
            file_tag = forced_file
            for one_name in names_list:
                one_name = one_name.strip()
                if not one_name or not NAME_RE.match(one_name):
                    continue
                # chemin YAML complet -> name = dernier segment
                if "." in one_name and "/" not in one_name:
                    path = one_name
                    name = one_name.split(".")[-1]
                    paths = [path]
                else:
                    name = one_name
                    paths = []
                # la fusion ne regroupe que les entrees de MEME racine de
                # chemin (sinon tous les 'Name' YAML fusionneraient et la
                # desambiguisation par contexte deviendrait impossible)
                root = paths[0].split(".", 1)[0].split("[", 1)[0].lower() if paths else ""
                key = (name.lower(), scope, file_tag, root)
                entry = props.get(key)
                if entry is None:
                    props[key] = {"name": name, "scope": scope, "file": file_tag,
                                  "paths": paths, "detail": detail, "exp": exp}
                else:
                    for p in paths:
                        if p not in entry["paths"]:
                            entry["paths"].append(p)
                    if not entry["detail"] and detail:
                        entry["detail"] = detail
            section_prose = []  # une table coupe un paragraphe
            continue

        # prose courante (description de fichier potentielle)
        if stripped and not stripped.startswith("#"):
            section_prose.append(stripped)
        elif not stripped:
            # paragraphe termine : garde seulement le premier bloc non vide
            if section_prose and heading:
                _freeze_file_description(heading, section_prose, file_descriptions)
                section_prose = []

    _freeze_file_description(heading, section_prose, file_descriptions)

    # ordre stable : scope puis name puis paths
    ordered = sorted(props.values(),
                     key=lambda e: (e["scope"], e["file"] or "", e["name"].lower(),
                                    e["paths"]))
    return {
        "_meta": {"source": "docs/glossaire_proprietes.md", "props": len(ordered)},
        "file_descriptions": dict(sorted(file_descriptions.items())),
        "props": ordered,
    }


def _freeze_file_description(heading: str, prose: list, out: dict) -> None:
    """Associe le premier paragraphe de prose d'une section a son fichier,
    pour les vues 'explication de ce fichier'."""
    if not prose or not heading:
        return
    rule = _scope_and_file(heading)
    if not rule:
        return
    key = _section_key(heading)
    m = re.search(r"([A-Za-z]+\.ecf|playfield\.yaml|Sectors\.yaml|gameoptions\.yaml"
                  r"|PDA\.yaml|LoadingScreenConfig\.yaml)", key)
    if m:
        filename = m.group(1)
    elif key.startswith("1.") or key.startswith("2."):
        filename = "playfield.yaml"
    elif key.startswith("3."):
        filename = "Sectors.yaml"
    elif key.startswith("4.1"):
        filename = "LoadingScreenConfig.yaml"
    elif key.startswith("4."):
        filename = "gameoptions.yaml"
    elif key.startswith("8."):
        filename = "PDA.yaml"
    elif key.startswith("7."):
        filename = "*.epb"
    else:
        return
    if filename in out:
        return
    text = " ".join(prose).strip()
    if text:
        out[filename] = text


def build() -> dict:
    return parse_glossary(SRC.read_text(encoding="utf-8"))


def main() -> int:
    data = build()
    out = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if "--check" in sys.argv:
        current = DEST.read_text(encoding="utf-8") if DEST.exists() else ""
        if current == out:
            print(f"OK : data/propriete_glossary.json a jour "
                  f"({data['_meta']['props']} proprietes)")
            return 0
        print("DESYNCHRO : docs/glossaire_proprietes.md a evolue -- "
              "relancer sans --check puis mettre a jour le EN")
        return 1
    DEST.write_text(out, encoding="utf-8")
    print(f"ecrit {DEST.relative_to(ROOT)} : "
          f"{data['_meta']['props']} proprietes, "
          f"{len(data['file_descriptions'])} descriptions de fichiers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
