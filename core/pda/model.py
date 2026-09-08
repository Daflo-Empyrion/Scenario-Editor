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
Modele du NOUVEAU module PDA : wrapper de lecture/mutation sur le couple
(PDA.yaml via yamllite, PDA.csv via csv_handler) -- meme contrat que
l'ancien core/pda_mission.py mais BREADTH-complet : chapitres, taches,
actions de TOUT type de Check, activites (ChapterActivation), recompenses,
repetitions, chainage (RewardedChapters) et textes CSV multilingues.

Discipline round-trip (non negociable) :
- toute mutation passe par set()/set_own_value() (dirty) ou par des entrees
  NEUVES creees avec create_entry() -- jamais de reecriture de branches
  existantes ;
- champ scalaire mis a '' => la cle est SUPPRIMEE du fichier (convention des
  vrais fichiers : tout est optionnel, une cle vide n'existe pas), sauf les
  cles structurelles obligatoires qui recoivent leur valeur par defaut ;
- indent/eol des entrees neuvess calques sur le parent (memo convention que
  l'ancien module, confirmee sur les 3 fichiers de reference).

Le modele ne connait PAS la GUI et n'ecrit JAMAIS sur disque : il mute les
documents des onglets ouverts, la fenetre principale marque ensuite les
onglets modifies (meme flux que l'ancien module)."""
import copy
import random
import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.yamllite.model import YamlDocument, YamlEntry, create_entry, remove_entry

_TOKEN_ALPHABET = string.ascii_letters + string.digits
# Jeton de localisation PDA : 'pda_XXXXXXX' pur ou PRE-FIXE par un namespace
# ('eden_pda_XXXXXXX' confirme sur le RE2, 'hws_pda_...' possible).
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]*pda_[A-Za-z0-9]+$")


def split_token_value(value: str) -> Tuple[str, str]:
    """Separe une valeur YAML de texte localise en (prefixe, jeton).

    Les vrais fichiers portent souvent un PREFIXE de format avant le jeton,
    separe par '|' : 'mbox;20|pda_KaOsQr' (boite de message, 20 s),
    'norm;20|pda_44CuO', 'high;30|eden_pda_a0SeOOO' -- le jeton CSV est la
    partie APRES le '|' uniquement. Si la partie droite ne ressemble pas a un
    jeton (famille *pda_), la valeur entiere est un TEXTE BRUT non localise :
    retourne ('', valeur) et l'appelant la traite comme telle."""
    if value and "|" in value:
        prefix, rest = value.split("|", 1)
        rest = rest.strip()
        if _TOKEN_RE.match(rest):
            return prefix, rest
    return "", value or ""

# Cles de chapitre JAMAIS supprimees (structure minimale confirmee sur les 3
# fichiers : presente sur 100% des chapitres) -- un effacement dans l'editeur
# remet la valeur par defaut au lieu de retirer la cle.
CHAPTER_REQUIRED_DEFAULTS = {
    "Category": "SoloMission",
    "NoSkip": "true",
    "Activatable": "Always",
    "Visibility": "Always",
    "PlayerLevel": "1",
}


def generate_token(existing_tokens: set) -> str:
    """Nouveau jeton pda_XXXXXXX unique (format confirme sur les vrais fichiers)."""
    while True:
        suffix = "".join(random.choice(_TOKEN_ALPHABET) for _ in range(7))
        token = f"pda_{suffix}"
        if token not in existing_tokens:
            return token


@dataclass
class RewardEntry:
    """Vue normalisee d'une ligne Rewards (forme Item OU Type -- voir
    schema.RewardSpec pour les formes confirmees)."""
    kind: str            # 'Item' | 'Type'
    name: str            # nom d'item (Item) ou valeur du Type (XP, UP...)
    count: int = 1
    faction: str = ""    # 'Type: Reputation' uniquement (liste a 1 valeur observee)
    meta: str = ""


class PdaModel:
    """Acces normalise au couple PDA.yaml/PDA.csv ouvert dans des onglets."""

    def __init__(self, yaml_doc: YamlDocument, csv_doc):
        self.yaml_doc = yaml_doc
        self.csv_doc = csv_doc
        self._columns: Optional[Dict[str, int]] = None
        # Jetons CSV crees/modifies depuis l'ouverture (pour surligner les
        # lignes correspondantes dans l'onglet PDA.csv -- demande utilisateur :
        # "voir ce qui a ete modifie") ; reset via take_touched_csv_tokens().
        self.touched_csv_tokens: set = set()

    # ------------------------------------------------------------------
    # Racine / chapitres
    # ------------------------------------------------------------------
    def chapters_root(self) -> Optional[YamlEntry]:
        for node in self.yaml_doc.nodes:
            if isinstance(node, YamlEntry) and node.key == "Chapters":
                return node
        return None

    def ensure_chapters_root(self) -> YamlEntry:
        root = self.chapters_root()
        if root is not None:
            return root
        root = create_entry("Chapters", "", indent="", eol="\r\n")
        self.yaml_doc.nodes.append(root)
        return root

    def chapters(self) -> List[YamlEntry]:
        root = self.chapters_root()
        if root is None:
            return []
        return [c for c in root.children if isinstance(c, YamlEntry)]

    # ------------------------------------------------------------------
    # Titres : jetons + resolution CSV
    # ------------------------------------------------------------------
    def chapter_title_token(self, chapter: YamlEntry) -> str:
        return chapter.value or ""

    def csv_column_index(self, column: str) -> Optional[int]:
        """Index d'une colonne par son en-tete exact ('English', 'Français'...)
        -- mis en cache, les colonnes sont localisees par NOM jamais par
        position (l'ordre differe d'un fichier a l'autre)."""
        if self._columns is None:
            self._columns = {}
            if self.csv_doc is not None and self.csv_doc.header:
                for i, name in enumerate(self.csv_doc.header):
                    self._columns.setdefault(name.strip(), i)
        return self._columns.get(column)

    def csv_text(self, token: str, column: str = "English") -> str:
        idx = self.csv_column_index(column)
        if idx is None or self.csv_doc is None:
            return ""
        for row in self.csv_doc.rows:
            if row and row[0].strip() == token:
                return row[idx] if idx < len(row) else ""
        return ""

    def set_csv_text(self, token: str, text: str, column: str = "English") -> bool:
        """Ecrit le texte du jeton dans la colonne donnee ; cree la ligne si
        absente (padded a la largeur du header). Retourne True si une NOUVELLE
        ligne a ete creee. Le jeton est enregistre dans touched_csv_tokens
        (surlignage de l'onglet PDA.csv)."""
        if self.csv_doc is None:
            return False
        idx = self.csv_column_index(column)
        if idx is None:
            return False
        self.touched_csv_tokens.add(token)
        for row in self.csv_doc.rows:
            if row and row[0].strip() == token:
                while len(row) <= idx:
                    row.append("")
                row[idx] = text
                return False
        width = len(self.csv_doc.header) if self.csv_doc.header else idx + 1
        row = [""] * max(width, idx + 1)
        row[0] = token
        row[idx] = text
        self.csv_doc.rows.append(row)
        return True

    def take_touched_csv_tokens(self) -> set:
        """Les jetons CSV touches depuis le dernier appel, puis remise a zero."""
        touched = self.touched_csv_tokens
        self.touched_csv_tokens = set()
        return touched

    # ------------------------------------------------------------------
    # Snapshots (bouton Annuler de l'editeur) -- texte serialise + copies de
    # lignes CSV : compact, restore par re-parse DANS LES MEMES objets
    # YamlDocument/CsvDocument que les onglets partagent (les onglets se
    # rafraichissent donc tous seuls apres un undo, via refresh_from_doc()).
    # ------------------------------------------------------------------
    def snapshot(self):
        rows = [row[:] for row in self.csv_doc.rows] if self.csv_doc is not None else None
        return (self.yaml_doc.render(), rows)

    def restore_snapshot(self, snap) -> None:
        yaml_text, rows = snap
        from core.yamllite.parser import parse_yaml_text
        self.yaml_doc.nodes = parse_yaml_text(yaml_text).nodes
        if self.csv_doc is not None and rows is not None:
            self.csv_doc.rows = [row[:] for row in rows]
        self.touched_csv_tokens = set()

    def csv_languages(self) -> List[str]:
        """Colonnes de langues du header (tout sauf la 1re colonne KEY)."""
        if self.csv_doc is None or not self.csv_doc.header:
            return []
        return [h.strip() for h in self.csv_doc.header[1:]]

    # ------------------------------------------------------------------
    # Jetons
    # ------------------------------------------------------------------
    def collect_all_tokens(self) -> set:
        tokens: set = set()
        if self.csv_doc is not None:
            for row in self.csv_doc.rows:
                if row and row[0].strip():
                    tokens.add(row[0].strip())

        def walk(nodes):
            for node in nodes:
                if isinstance(node, YamlEntry):
                    if node.value:
                        _prefix, token = split_token_value(node.value)
                        if _TOKEN_RE.match(token):
                            tokens.add(token)
                    walk(node.children)
        walk(self.yaml_doc.nodes)
        return tokens

    def new_token(self, tokens_used: set) -> str:
        token = generate_token(tokens_used)
        tokens_used.add(token)
        return token

    # ------------------------------------------------------------------
    # Lecture/mutation generique de champs scalaires et de listes
    # ------------------------------------------------------------------
    @staticmethod
    def _child(entry: YamlEntry, key: str) -> Optional[YamlEntry]:
        for c in entry.children:
            if isinstance(c, YamlEntry) and c.key == key:
                return c
        return None

    @staticmethod
    def scalar(entry: YamlEntry, key: str) -> str:
        node = PdaModel._child(entry, key)
        return node.value if node is not None else ""

    @staticmethod
    def set_scalar(entry: YamlEntry, key: str, value: str,
                   required_defaults: Optional[Dict[str, str]] = None) -> None:
        """Met a jour une cle scalaire ; '' supprime la cle SAUF si une valeur
        par defaut obligatoire est definie (cle structurelle des vrais fichiers)."""
        if value == "" and required_defaults:
            value = required_defaults.get(key, "")
        existing = PdaModel._child(entry, key)
        if value == "":
            if existing is not None:
                entry.children.remove(existing)
            return
        if existing is not None:
            existing.set_own_value(value)
            return
        child = create_entry(key, value, indent=entry.indent + "  ", eol=entry.eol)
        entry.children.append(child)

    @staticmethod
    def get_list(entry: YamlEntry, key: str) -> List[str]:
        node = PdaModel._child(entry, key)
        if node is None:
            return []
        return [c.value for c in node.children
                if isinstance(c, YamlEntry) and c.value is not None]

    @staticmethod
    def set_list(entry: YamlEntry, key: str, values: List[str]) -> None:
        node = PdaModel._child(entry, key)
        if not values:
            if node is not None:
                entry.children.remove(node)
            return
        if node is None:
            node = create_entry(key, "", indent=entry.indent + "  ", eol=entry.eol)
            entry.children.append(node)
        node.children = [
            create_entry(None, v, indent=node.indent + "  ", is_sequence_item=True, eol=node.eol)
            for v in values
        ]

    # ------------------------------------------------------------------
    # Taches / Actions : acces
    # ------------------------------------------------------------------
    def tasks(self, chapter: YamlEntry) -> List[YamlEntry]:
        node = self._child(chapter, "Tasks")
        if node is None:
            return []
        return [c for c in node.children if isinstance(c, YamlEntry)]

    def actions(self, task: YamlEntry) -> List[YamlEntry]:
        node = self._child(task, "Actions")
        if node is None:
            return []
        return [c for c in node.children if isinstance(c, YamlEntry)]

    @staticmethod
    def action_check(action: YamlEntry) -> str:
        node = PdaModel._child(action, "Check")
        return node.value if node is not None else ""

    # ------------------------------------------------------------------
    # CRUD chapitres
    # ------------------------------------------------------------------
    def _chapter_layout(self) -> Tuple[str, str]:
        existing = self.chapters()
        if existing:
            return existing[0].indent, existing[0].eol
        return "  ", "\r\n"

    def create_chapter(self) -> YamlEntry:
        indent, eol = self._chapter_layout()
        root = self.ensure_chapters_root()
        token = self.new_token(self.collect_all_tokens())
        chapter = create_entry("ChapterTitle", token, indent=indent,
                               is_sequence_item=True, eol=eol)
        child = indent + "  "
        for key, value in CHAPTER_REQUIRED_DEFAULTS.items():
            chapter.children.append(create_entry(key, value, indent=child, eol=eol))
        tasks = create_entry("Tasks", "", indent=child, eol=eol)
        chapter.children.append(tasks)
        root.children.append(chapter)
        return chapter

    def duplicate_chapter(self, chapter: YamlEntry) -> Optional[YamlEntry]:
        siblings = self._siblings_of(chapter)
        if siblings is None:
            return None
        clone = copy.deepcopy(chapter)
        tokens = self.collect_all_tokens()
        token_map: Dict[str, str] = {}

        # Re-tokénise CHAQUE jeton du clone : les textes du dupliqué doivent
        # rester indépendants de l'original (les prefixes de format
        # 'mbox;20|' sont preserves, seul le jeton change).
        def retokenize(entry: YamlEntry):
            if entry.value:
                prefix, token = split_token_value(entry.value)
                if _TOKEN_RE.match(token):
                    new_token = self.new_token(tokens)
                    token_map[token] = new_token
                    entry.set_own_value(f"{prefix}|{new_token}" if prefix else new_token)
            for c in entry.children:
                if isinstance(c, YamlEntry):
                    retokenize(c)
        retokenize(clone)
        # Copie les textes CSV de l'original vers les nouveaux jetons (toutes
        # les colonnes de langues) : sans cela le duplique afficherait des
        # jetons nus.
        if self.csv_doc is not None and self.csv_doc.header:
            for old, new in token_map.items():
                for column in self.csv_doc.header[1:]:
                    text = self.csv_text(old, column.strip())
                    if text:
                        self.set_csv_text(new, text, column.strip())
        siblings.insert(siblings.index(chapter) + 1, clone)
        return clone

    def delete_entry(self, entry: YamlEntry) -> bool:
        """Supprime chapitre/tache/action/activation -- remonte au parent par
        parcours, remove_entry gere toutes les profondeurs."""
        return remove_entry(self.yaml_doc.nodes, entry)

    def move_entry(self, entry: YamlEntry, delta: int) -> bool:
        """Deplace entry de delta positions (-1/+) dans sa liste parente."""
        siblings = self._siblings_of(entry)
        if siblings is None or entry not in siblings:
            return False
        idx = siblings.index(entry)
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(siblings):
            return False
        siblings.remove(entry)
        siblings.insert(new_idx, entry)
        return True

    def _siblings_of(self, entry: YamlEntry) -> Optional[list]:
        def walk(nodes):
            if entry in nodes:
                return nodes
            for node in nodes:
                if isinstance(node, YamlEntry):
                    found = walk(node.children)
                    if found is not None:
                        return found
            return None
        return walk(self.yaml_doc.nodes)

    # ------------------------------------------------------------------
    # CRUD taches / actions / activations
    # ------------------------------------------------------------------
    def create_task(self, chapter: YamlEntry) -> YamlEntry:
        tasks = self._child(chapter, "Tasks")
        if tasks is None:
            tasks = create_entry("Tasks", "", indent=chapter.indent + "  ", eol=chapter.eol)
            chapter.children.append(tasks)
        token = self.new_token(self.collect_all_tokens())
        task = create_entry("TaskTitle", token, indent=tasks.indent + "  ",
                            is_sequence_item=True, eol=tasks.eol)
        actions = create_entry("Actions", "", indent=tasks.indent + "    ", eol=tasks.eol)
        task.children.append(actions)
        tasks.children.append(task)
        return task

    def create_action(self, task: YamlEntry, check: str = "") -> YamlEntry:
        actions = self._child(task, "Actions")
        if actions is None:
            actions = create_entry("Actions", "", indent=task.indent + "  ", eol=task.eol)
            task.children.append(actions)
        token = self.new_token(self.collect_all_tokens())
        action = create_entry("ActionTitle", token, indent=actions.indent + "  ",
                              is_sequence_item=True, eol=actions.eol)
        child = actions.indent + "    "
        action.children.append(create_entry("Description", token, indent=child, eol=actions.eol))
        if check:
            action.children.append(create_entry("Check", check, indent=child, eol=actions.eol))
        actions.children.append(action)
        return action

    def create_activation(self, chapter: YamlEntry) -> YamlEntry:
        """Nouvelle entree de ChapterActivation -- forme majoritaire des vrais
        fichiers quand il n'y a pas de Check explicite : la PREMIERE cle est
        posee sur la ligne ('- Names:'), les champs suivants deviennent des
        enfants indentes. La 1re cle peut ensuite basculer vers 'Check' via
        set_activation_primary_key()."""
        node = self._child(chapter, "ChapterActivation")
        if node is None:
            node = create_entry("ChapterActivation", "", indent=chapter.indent + "  ", eol=chapter.eol)
            chapter.children.append(node)
        entry = create_entry("Names", "", indent=node.indent + "  ",
                             is_sequence_item=True, eol=node.eol)
        node.children.append(entry)
        return entry

    def activations(self, chapter: YamlEntry) -> List[YamlEntry]:
        node = self._child(chapter, "ChapterActivation")
        if node is None:
            return []
        return [c for c in node.children if isinstance(c, YamlEntry)]

    @staticmethod
    def activation_field(entry: YamlEntry, key: str) -> str:
        """Valeur d'un champ d'activation, y compris quand key EST la premiere
        cle de l'entree (ligne '- Key: value')."""
        if key == entry.key:
            return entry.value or ""
        return PdaModel.scalar(entry, key)

    def set_activation_field(self, entry: YamlEntry, key: str, value: str) -> None:
        if key == entry.key:
            entry.set_own_value(value)
            return
        self.set_scalar(entry, key, value)

    def activation_names(self, entry: YamlEntry) -> List[str]:
        names_node = self._child(entry, "Names")
        if entry.key == "Names" and names_node is None:
            # Forme native '- Names:' avec items directement enfants
            return [c.value for c in entry.children
                    if isinstance(c, YamlEntry) and c.key is None]
        return self.get_list(entry, "Names")

    def set_activation_names(self, entry: YamlEntry, values: List[str]) -> None:
        names_node = self._child(entry, "Names")
        if entry.key == "Names" and names_node is None:
            # Remplace UNIQUEMENT les items de liste (key=None), preserve les
            # autres champs (NoSkip, PopupActivatesChapter...) deja presents
            # en enfants.
            kept = [c for c in entry.children
                    if not (isinstance(c, YamlEntry) and c.key is None)]
            items = [create_entry(None, v, indent=entry.indent + "  ",
                                  is_sequence_item=True, eol=entry.eol)
                     for v in values]
            entry.children = items + kept
            return
        self.set_list(entry, "Names", values)

    def set_activation_primary_key(self, entry: YamlEntry, new_key: str) -> None:
        """Bascule la premiere cle de l'entree d'activation (ex: 'Names' ->
        'Check') en migrant l'ancien contenu premier vers les enfants."""
        if entry.key == new_key:
            return
        if entry.key and entry.value:
            child = create_entry(entry.key, entry.value,
                                 indent=entry.indent + "  ", eol=entry.eol)
            entry.children.insert(0, child)
        elif entry.key == "Names":
            items = [c for c in entry.children
                     if isinstance(c, YamlEntry) and c.key is None]
            if items:
                names_node = create_entry("Names", "", indent=entry.indent + "  ", eol=entry.eol)
                for item in items:
                    entry.children.remove(item)
                    item.indent = names_node.indent + "  "
                    item.dirty = True
                    names_node.children.append(item)
                entry.children.insert(0, names_node)
        entry.key = new_key
        entry.value = ""
        entry.dirty = True
        # Absorbe un enfant homonyme SCALAIRE existant comme valeur inline de
        # la nouvelle premiere cle (ex: enfant 'Check: DialogOption' devient
        # '- Check: DialogOption').
        same = self._child(entry, new_key)
        if same is not None and not same.children:
            entry.value = same.value or ""
            entry.children.remove(same)
        # Forme canonique quand la nouvelle premiere cle est la liste Names :
        # les items remontent en enfants directs de l'entree ('- Names:' +
        # items), le node enfant homonyme disparait.
        if new_key == "Names":
            node = self._child(entry, "Names")
            if node is not None and node is not entry:
                items = [c for c in node.children if isinstance(c, YamlEntry)]
                for item in items:
                    item.indent = entry.indent + "  "
                    item.dirty = True
                kept = [c for c in entry.children if c is not node]
                entry.children = items + kept

    # ------------------------------------------------------------------
    # Recompenses (Chapter OU Task -- meme forme confirmee)
    # ------------------------------------------------------------------
    def rewards(self, entry: YamlEntry) -> List[RewardEntry]:
        node = self._child(entry, "Rewards")
        if node is None:
            return []
        out: List[RewardEntry] = []
        for child in node.children:
            if not isinstance(child, YamlEntry):
                continue
            if child.key == "Item":
                out.append(RewardEntry(kind="Item", name=child.value,
                                       count=_to_int(self.scalar(child, "Count")),
                                       meta=self.scalar(child, "Meta")))
            elif child.key == "Type":
                factions = self.get_list(child, "Faction")
                out.append(RewardEntry(kind="Type", name=child.value,
                                       count=_to_int(self.scalar(child, "Count")),
                                       faction=factions[0] if factions else "",
                                       meta=self.scalar(child, "Meta")))
        return out

    def set_rewards(self, entry: YamlEntry, rewards: List[RewardEntry]) -> None:
        old = self._child(entry, "Rewards")
        if not rewards:
            if old is not None:
                entry.children.remove(old)
            return
        node = old if old is not None else create_entry(
            "Rewards", "", indent=entry.indent + "  ", eol=entry.eol)
        node.children = []
        child = node.indent + "  "
        for r in rewards:
            if r.kind == "Item":
                item = create_entry("Item", r.name, indent=child, is_sequence_item=True, eol=node.eol)
                item.children.append(create_entry("Count", str(r.count), indent=child + "  ", eol=node.eol))
                if r.meta:
                    item.children.append(create_entry("Meta", r.meta, indent=child + "  ", eol=node.eol))
                node.children.append(item)
            else:
                t = create_entry("Type", r.name, indent=child, is_sequence_item=True, eol=node.eol)
                t.children.append(create_entry("Count", str(r.count), indent=child + "  ", eol=node.eol))
                if r.faction:
                    faction = create_entry("Faction", "", indent=child + "  ", eol=node.eol)
                    faction.children.append(create_entry(None, r.faction, indent=child + "    ",
                                                         is_sequence_item=True, eol=node.eol))
                    t.children.append(faction)
                if r.meta:
                    t.children.append(create_entry("Meta", r.meta, indent=child + "  ", eol=node.eol))
                node.children.append(t)
        if old is None:
            entry.children.append(node)

    # ------------------------------------------------------------------
    # RepeatConditions (chapitre uniquement)
    # ------------------------------------------------------------------
    def repeat_fields(self, chapter: YamlEntry) -> Dict[str, str]:
        node = self._child(chapter, "RepeatConditions")
        if node is None:
            return {}
        return {c.key: c.value for c in node.children
                if isinstance(c, YamlEntry) and c.key}

    def set_repeat_field(self, chapter: YamlEntry, key: str, value: str) -> None:
        node = self._child(chapter, "RepeatConditions")
        if value == "":
            if node is not None:
                sub = self._child(node, key)
                if sub is not None:
                    node.children.remove(sub)
                if not node.children:
                    chapter.children.remove(node)
            return
        if node is None:
            node = create_entry("RepeatConditions", "", indent=chapter.indent + "  ", eol=chapter.eol)
            chapter.children.append(node)
        sub = self._child(node, key)
        if sub is not None:
            sub.set_own_value(value)
        else:
            node.children.append(create_entry(key, value, indent=node.indent + "  ", eol=node.eol))


def _to_int(value: Optional[str], default: int = 1) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def list_pda_yaml_files(content_dir: Path) -> List[Path]:
    """Tous les PDA*.yaml d'un dossier Content de scenario (Extras/PDA/) --
    utilitaire de decouverte pour l'ouverture multi-PDA."""
    out: List[Path] = []
    pda_dir = content_dir / "Extras" / "PDA"
    if pda_dir.is_dir():
        out.extend(sorted(pda_dir.glob("*.yaml")))
    return out
