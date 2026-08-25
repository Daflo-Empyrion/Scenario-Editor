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
Creation guidee de missions PDA (Extras/PDA/PDA.yaml + PDA.csv) -- structure
confirmee sur un vrai fichier (530 chapitres, meme auteurs que Dialogues.ecf/
eWCCT) : Chapters > Tasks > Actions, imbrication fractale (chaque niveau
utilise le meme motif is_sequence_item que le reste de l'application), round-
trip parfait avec notre parseur maison, aucun piege de commentaires (les 530
chapitres sont bien des enfants DIRECTS de 'Chapters', contrairement aux
POI/Sectors.yaml).

Deux types d'objectifs geres (les seuls demandes) :
- SubjectKilled : tuer un nombre donne d'entites nommees (creatures, drones,
  troupes...)
- BlockDestroyed : detruire un nombre donne de blocs nommes -- couvre a la
  fois la destruction de structures/coeurs ennemis (Types: CoreNPC/
  CoreNPCAdmin) ET le MINAGE d'une ressource precise (Types: IronResource,
  CopperResource... -- miner une ressource EST une destruction de bloc cote
  moteur du jeu, meme mecanisme, confirme sur le vrai fichier).

IMPORTANT -- les noms de cibles precis (ex: 'XenuMainRG') sont des noms de
blocs personnalises A L'INTERIEUR d'un blueprint donne, introuvables dans
BlocksConfig.ecf ou tout autre fichier .ecf/.yaml du scenario -- decision
prise avec l'utilisateur de ne PAS aller les chercher dans les fichiers de
blueprint (.epb, meme famille de risques que les sauvegardes de partie deja
ecartees : format binaire proprietaire non documente, aucun outil
communautaire sous licence reutilisable). A la place, les noms deja
utilises ailleurs dans le MEME PDA.yaml sont proposes comme suggestions
reutilisables (collect_used_names ci-dessous) -- la saisie libre reste
toujours possible en complement.

EXCEPTION -- minage (BlockDestroyed sur une ressource) : contrairement aux
noms de blocs personnalises ci-dessus, les noms de ressources MINABLES sont
de VRAIS noms de blocs BlocksConfig.ecf ('IronResource', 'CopperResource'...
pour les gisements planetaires) ou un motif technique confirme des playfields
spatiaux ('AsteroidVoxel0N<Materiau>' pour les asteroides) -- voir
list_mining_target_name_suggestions ci-dessous, qui reutilise les fonctions
deja confirmees de core/playfield_editor.py plutot que de dupliquer cette
logique.
"""
import random
import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .yamllite.model import YamlEntry, YamlDocument, create_entry


_TOKEN_ALPHABET = string.ascii_letters + string.digits


def generate_token(existing_tokens: set) -> str:
    """Nouveau jeton pda_XXXXXXX unique -- format confirme sur le vrai
    fichier (7 caracteres alphanumeriques la plupart du temps)."""
    while True:
        suffix = "".join(random.choice(_TOKEN_ALPHABET) for _ in range(7))
        token = f"pda_{suffix}"
        if token not in existing_tokens:
            return token


def find_chapters_root(doc: YamlDocument) -> Optional[YamlEntry]:
    for node in doc.nodes:
        if isinstance(node, YamlEntry) and node.key == "Chapters":
            return node
    return None


def list_chapters(doc: YamlDocument) -> List[YamlEntry]:
    root = find_chapters_root(doc)
    if root is None:
        return []
    return [c for c in root.children if isinstance(c, YamlEntry)]


def _iter_all_actions(doc: YamlDocument):
    """Parcourt toutes les Actions de tous les Chapters/Tasks -- generateur,
    pas de materialisation intermediaire vu le volume (530 chapitres)."""
    for chapter in list_chapters(doc):
        tasks_node = next((c for c in chapter.children if isinstance(c, YamlEntry) and c.key == "Tasks"), None)
        if tasks_node is None:
            continue
        for task in tasks_node.children:
            if not isinstance(task, YamlEntry):
                continue
            actions_node = next((c for c in task.children if isinstance(c, YamlEntry) and c.key == "Actions"), None)
            if actions_node is None:
                continue
            for action in actions_node.children:
                if isinstance(action, YamlEntry):
                    yield action


def collect_used_names(doc: YamlDocument, check_type: str) -> List[str]:
    """Toutes les valeurs de 'Names' deja utilisees pour un type d'objectif
    donne (SubjectKilled ou BlockDestroyed) -- suggestions reutilisables,
    voir avertissement de tete de module sur les noms de cibles precis."""
    names: set = set()
    for action in _iter_all_actions(doc):
        check_prop = next((c for c in action.children if isinstance(c, YamlEntry) and c.key == "Check"), None)
        if check_prop is None or check_prop.value != check_type:
            continue
        names_node = next((c for c in action.children if isinstance(c, YamlEntry) and c.key == "Names"), None)
        if names_node is None:
            continue
        for item in names_node.children:
            if isinstance(item, YamlEntry) and item.value:
                names.add(item.value)
    return sorted(names)


def list_mining_target_name_suggestions(blocks_ecf_files: List[Path]) -> List[str]:
    """Suggestions de noms de cibles pour un objectif de minage (BlockDestroyed
    avec Types: XxxResource) : combine les vrais blocs de ressource planetaires
    ('IronResource', 'CopperResource'... voir
    core.playfield_editor.list_resource_block_names) et les variantes
    d'asteroides spatiaux generees selon le motif confirme
    'AsteroidVoxel0N<Materiau>' (voir
    core.playfield_editor.list_space_material_names/add_space_resource_item).
    Ce dernier n'est PAS un Name de bloc reel dans BlocksConfig.ecf (confirme
    sur un vrai fichier), mais c'est la valeur technique reellement utilisee
    dans les playfields spatiaux -- donc la seule suggestion plausible pour
    une cible de minage sur asteroide."""
    from core.playfield_editor import list_resource_block_names, list_space_material_names

    names: set = set(list_resource_block_names(blocks_ecf_files))
    for material in list_space_material_names(blocks_ecf_files):
        for i in (1, 2, 3):
            names.add(f"AsteroidVoxel0{i}{material}")
    return sorted(names)


def credits_reward_item_name() -> str:
    """Nom de l'item representant les credits en recompense PDA : 'MoneyCard'
    -- CONFIRME (et non plus suppose) via le vrai ItemsConfig.ecf du
    scenario de l'utilisateur, qui porte le commentaire explicite juste
    au-dessus de sa definition : '## Please do not rename - referenced in
    code'. C'est un item normal avec 'Credits: 1' (chaque carte vaut 1
    credit) et 'StackSize: 50000' deja definis nativement -- Count dans la
    recompense = montant de credits voulu (jusqu'a 50000 par pile).

    IMPORTANT -- correction d'un diagnostic precedent : 'Credits' (nom
    litteral) N'EST PAS un nom d'item valide pour cette recompense, malgre ce
    que suggerait le wiki communautaire ('Item: Can be an item, device,
    credits, gold or XP') -- infirme sur deux vrais logs client (v1.19.2) :
    meme avec une entree 'Credits' + StackSize ajoutee a la main dans
    ItemsConfig.ecf ET un rechargement complet de la partie, le moteur
    rejetait systematiquement la recompense ('-WRN- PDA: No max stack size
    found for 'Credits'' puis 'Malformed item reward specification : count
    too high'). 'MoneyCard' est le VRAI nom utilise par le moteur."""
    return "MoneyCard"


def collect_used_block_types(doc: YamlDocument) -> List[str]:
    """Toutes les valeurs de 'Types' deja utilisees sur des Actions
    BlockDestroyed -- melange ressources (IronResource...) et coeurs
    ennemis (CoreNPC...), voir docstring de tete de module."""
    types_seen: set = set()
    for action in _iter_all_actions(doc):
        check_prop = next((c for c in action.children if isinstance(c, YamlEntry) and c.key == "Check"), None)
        if check_prop is None or check_prop.value != "BlockDestroyed":
            continue
        types_node = next((c for c in action.children if isinstance(c, YamlEntry) and c.key == "Types"), None)
        if types_node is None:
            continue
        for item in types_node.children:
            if isinstance(item, YamlEntry) and item.value:
                types_seen.add(item.value)
    return sorted(types_seen)


def collect_all_tokens(doc: YamlDocument) -> set:
    """Tous les jetons pda_XXXX deja utilises dans le document -- pour
    garantir l'unicite d'un nouveau jeton genere (voir generate_token)."""
    tokens: set = set()
    pattern = re.compile(r"^pda_[A-Za-z0-9]+$")

    def walk(nodes):
        for node in nodes:
            if isinstance(node, YamlEntry):
                if node.value and pattern.match(node.value):
                    tokens.add(node.value)
                walk(node.children)
    walk(doc.nodes)
    return tokens


@dataclass
class ObjectiveSpec:
    check_type: str          # 'SubjectKilled' ou 'BlockDestroyed'
    names: List[str]
    amount: int
    types: Optional[List[str]] = None    # uniquement pour BlockDestroyed
    title_text: str = ""
    description_text: str = ""


@dataclass
class RewardSpec:
    kind: str                 # 'XP', 'UP', 'Reputation', 'Item'
    count: int
    faction: Optional[str] = None   # uniquement pour 'Reputation'
    item_name: Optional[str] = None  # uniquement pour 'Item'
    meta: Optional[str] = None       # uniquement pour 'Item' (ex: qualite)


@dataclass
class RepeatSpec:
    num_repeats: int = 0      # 0 = jamais (une seule fois)
    delay_seconds: int = 0


def _make_list_of_scalars(key: str, values: List[str], indent: str, eol: str) -> YamlEntry:
    """Cree une entree 'key:' dont les enfants sont une simple liste de
    valeurs (ex: Names, Types) -- motif confirme partout dans le fichier
    reel (chaque valeur est une entree sans cle, is_sequence_item=True,
    key=None)."""
    parent = create_entry(key, "", indent=indent, is_sequence_item=False, eol=eol)
    for v in values:
        parent.children.append(create_entry(None, v, indent=indent + "  ", is_sequence_item=True, eol=eol))
    return parent


def create_action(spec: ObjectiveSpec, title_token: str, desc_token: str,
                   indent: str, eol: str) -> YamlEntry:
    """Construit une Action (SubjectKilled ou BlockDestroyed), non encore
    attachee a un document -- indent/eol calques sur une Action existante
    du meme fichier pour un rendu coherent (voir create_chapter)."""
    child_indent = indent + "  "
    action = create_entry("ActionTitle", title_token, indent=indent, is_sequence_item=True, eol=eol)
    action.children.append(create_entry("Description", desc_token, indent=child_indent, eol=eol))
    action.children.append(create_entry("Check", spec.check_type, indent=child_indent, eol=eol))
    action.children.append(_make_list_of_scalars("Names", spec.names, child_indent, eol))
    if spec.check_type == "BlockDestroyed" and spec.types:
        action.children.append(_make_list_of_scalars("Types", spec.types, child_indent, eol))
    action.children.append(create_entry("Amount", str(spec.amount), indent=child_indent, eol=eol))
    action.children.append(create_entry("AllowManualCompletion", "true", indent=child_indent, eol=eol))
    return action


def create_task(objectives: List[ObjectiveSpec], title_token: str, action_tokens: List[Tuple[str, str]],
                 indent: str, eol: str) -> YamlEntry:
    """action_tokens : liste de (title_token, desc_token), un couple par
    objectif, dans le meme ordre que 'objectives'."""
    child_indent = indent + "  "
    task = create_entry("TaskTitle", title_token, indent=indent, is_sequence_item=True, eol=eol)
    actions_node = create_entry("Actions", "", indent=child_indent, eol=eol)
    for spec, (t_token, d_token) in zip(objectives, action_tokens):
        actions_node.children.append(create_action(spec, t_token, d_token, child_indent + "  ", eol))
    task.children.append(actions_node)
    return task


def create_reward_entry(spec: RewardSpec, indent: str, eol: str) -> YamlEntry:
    child_indent = indent + "  "
    if spec.kind == "Item":
        entry = create_entry("Item", spec.item_name, indent=indent, is_sequence_item=True, eol=eol)
        entry.children.append(create_entry("Count", str(spec.count), indent=child_indent, eol=eol))
        if spec.meta:
            entry.children.append(create_entry("Meta", spec.meta, indent=child_indent, eol=eol))
        return entry
    entry = create_entry("Type", spec.kind, indent=indent, is_sequence_item=True, eol=eol)
    if spec.kind == "Reputation" and spec.faction:
        entry.children.append(_make_list_of_scalars("Faction", [spec.faction], child_indent, eol))
    entry.children.append(create_entry("Count", str(spec.count), indent=child_indent, eol=eol))
    return entry


def create_chapter(doc: YamlDocument, title_token: str, description_token: str,
                    category: str, objectives: List[ObjectiveSpec],
                    rewards: List[RewardSpec], repeat: RepeatSpec,
                    task_title_token: str, action_tokens: List[Tuple[str, str]],
                    activatable: str = "Always",
                    rewarded_chapters: Optional[List[str]] = None) -> Optional[YamlEntry]:
    """Construit un nouveau Chapter complet (avec sa seule Task et ses
    Actions) et l'ajoute a la fin de 'Chapters' -- indent/eol calques sur un
    chapitre existant si possible, sinon valeurs par defaut coherentes avec
    le vrai fichier (2 espaces / CRLF).

    rewarded_chapters : jetons ChapterTitle des chapitres a activer une fois
    CELUI-CI recompense (mecanisme reel de paliers -- voir create_tier_chain
    ci-dessous, confirme sur une vraie chaine du jeu : chaque palier est un
    Chapter distinct, jamais une repetition du meme chapitre)."""
    root = find_chapters_root(doc)
    if root is None:
        return None

    existing = list_chapters(doc)
    if existing:
        indent = existing[0].indent
        eol = existing[0].eol
    else:
        indent = "  "
        eol = "\r\n"
    child_indent = indent + "  "

    chapter = create_entry("ChapterTitle", title_token, indent=indent, is_sequence_item=True, eol=eol)
    chapter.children.append(create_entry("Category", category, indent=child_indent, eol=eol))
    chapter.children.append(create_entry("Activatable", activatable, indent=child_indent, eol=eol))
    chapter.children.append(create_entry("Visibility", "Always", indent=child_indent, eol=eol))
    chapter.children.append(create_entry("Description", description_token, indent=child_indent, eol=eol))

    tasks_node = create_entry("Tasks", "", indent=child_indent, eol=eol)
    tasks_node.children.append(create_task(objectives, task_title_token, action_tokens, child_indent + "  ", eol))
    chapter.children.append(tasks_node)

    if rewarded_chapters:
        chapter.children.append(_make_list_of_scalars("RewardedChapters", rewarded_chapters, child_indent, eol))

    if rewards:
        rewards_node = create_entry("Rewards", "", indent=child_indent, eol=eol)
        for r in rewards:
            rewards_node.children.append(create_reward_entry(r, child_indent + "  ", eol))
        chapter.children.append(rewards_node)

    if repeat.num_repeats:
        repeat_node = create_entry("RepeatConditions", "", indent=child_indent, eol=eol)
        repeat_node.children.append(create_entry("NumRepeats", str(repeat.num_repeats), indent=child_indent + "  ", eol=eol))
        repeat_node.children.append(create_entry("DelaySeconds", str(repeat.delay_seconds), indent=child_indent + "  ", eol=eol))
        chapter.children.append(repeat_node)

    root.children.append(chapter)
    return chapter


def add_pda_text_entries(csv_doc, entries: List[Tuple[str, str, str]]) -> None:
    """Ajoute une ligne PDA.csv par (jeton, texte anglais, texte francais) --
    les autres langues restent vides (comme le fait le vrai fichier pour de
    nombreuses entrees deja presentes, confirme sur PDA.csv reel). Modifie
    csv_doc.rows en place. Colonnes localisees par leur en-tete reel
    ('English'/'Français', confirme sur le vrai PDA.csv) plutot que par
    position fixe, pour rester robuste si l'ordre des colonnes differe d'un
    fichier a l'autre."""
    if not csv_doc.header:
        return
    try:
        en_idx = csv_doc.header.index("English")
    except ValueError:
        en_idx = 1  # repli raisonnable (position confirmee sur le vrai fichier)
    try:
        fr_idx = csv_doc.header.index("Français")
    except ValueError:
        fr_idx = None

    width = len(csv_doc.header)
    for token, en_text, fr_text in entries:
        row = [""] * width
        row[0] = token
        if en_idx < width:
            row[en_idx] = en_text
        if fr_idx is not None and fr_idx < width:
            row[fr_idx] = fr_text
        csv_doc.rows.append(row)


@dataclass
class TierSpec:
    """Un palier au sein d'une mission a etapes -- objectif et recompense
    propres, textes propres. Voir create_tier_chain() : chaque palier
    devient un Chapter DISTINCT (jamais une repetition du meme chapitre),
    chaine au suivant via RewardedChapters + Activatable: WhenRewarded --
    mecanisme confirme sur une vraie chaine du jeu (ex: 50 -> 100 -> 35
    kills sur 3 chapitres successifs)."""
    title_text: str
    description_text: str
    objective: ObjectiveSpec
    rewards: List[RewardSpec]


def create_tier_chain(doc: YamlDocument, csv_doc, tiers: List[TierSpec], category: str) -> List[YamlEntry]:
    """Cree une SUITE de Chapters chaines representant des paliers
    progressifs -- le premier est immediatement activable (Activatable:
    Always), chaque suivant ne le devient qu'une fois le precedent
    recompense (Activatable: WhenRewarded, via RewardedChapters sur le
    chapitre precedent). Genere aussi les entrees PDA.csv correspondantes
    (voir add_pda_text_entries). Retourne la liste des chapitres crees, dans
    l'ordre des paliers -- liste vide si 'tiers' est vide ou si 'Chapters'
    est introuvable dans le document."""
    if not tiers:
        return []

    tokens_used = collect_all_tokens(doc)

    def new_tok():
        token = generate_token(tokens_used)
        tokens_used.add(token)
        return token

    # Genere d'abord TOUS les jetons de titre de chapitre, dans l'ordre --
    # necessaire pour que chaque palier connaisse a l'avance le jeton du
    # SUIVANT (pour son propre RewardedChapters), avant meme que ce chapitre
    # suivant ne soit construit.
    chapter_title_tokens = [new_tok() for _ in tiers]

    created_chapters: List[YamlEntry] = []
    csv_entries: List[Tuple[str, str, str]] = []

    for i, tier in enumerate(tiers):
        desc_token = new_tok()
        task_token = new_tok()
        action_title_token = new_tok()
        action_desc_token = new_tok()

        activatable = "Always" if i == 0 else "WhenRewarded"
        rewarded_chapters = [chapter_title_tokens[i + 1]] if i + 1 < len(tiers) else None

        chapter = create_chapter(
            doc, chapter_title_tokens[i], desc_token, category,
            [tier.objective], tier.rewards, RepeatSpec(),
            task_token, [(action_title_token, action_desc_token)],
            activatable=activatable, rewarded_chapters=rewarded_chapters,
        )
        if chapter is None:
            return created_chapters
        created_chapters.append(chapter)

        title_fr = tier.title_text  # meme texte que l'anglais si non fourni separement
        csv_entries.append((chapter_title_tokens[i], tier.title_text, title_fr))
        csv_entries.append((desc_token, tier.description_text, tier.description_text))
        csv_entries.append((task_token, tier.title_text, title_fr))
        csv_entries.append((action_title_token, tier.title_text, title_fr))
        csv_entries.append((action_desc_token, tier.description_text, tier.description_text))

    add_pda_text_entries(csv_doc, csv_entries)
    return created_chapters
