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
"""Reparations mecaniques des configs ECF, sans parse+render.

Regles issues du vecu (fiches cerveau) :
- `{ ... }` sur UNE ligne = « config line N is malformed » puis NRE au
  chargement (empyrion-ecf-bloc-mono-ligne-malformed) : l'entete va sur sa
  ligne, l'accolade fermante seule sur la suivante ;
- `HitPoints:`/`Armor:` sans `, type: int` = valeur stockee en chaine,
  « Error converting property ... to an int value » au log et valeur
  IGNOREE silencieusement (empyrion-ecf-hitpoints-type-int-obligatoire).

Ecritures TEXTE BRUT (jamais parse+render : perte de blocs, cf.
re2fr-bilan-corrections-import-blocs), idempotentes, sauvegarde par
fichier via BackupStore.
"""
from pathlib import Path
import re

from core.ai_realism import read_text_raw, write_text_raw

# `{ ... }` ferme sur la meme ligne (hors commentaire)
_MONOLINE_RE = re.compile(r"^([ \t]*)\{([^{}]+)\}[ \t]*$")
# HitPoints/Armor numerique SANS `type:` sur la ligne
_INT_RE = re.compile(r"^([ \t]*)(HitPoints|Armor):[ \t]*([-0-9.]+)[ \t]*(#.*)?$")
_INT_FILES = ("BlocksConfig.ecf", "ItemsConfig.ecf")


def _apply(path: Path, text: str, eol: str, store) -> None:
    if store:
        store.snapshot(path)
    write_text_raw(path, text, eol)


def fix_ecf_monoline(scenario: Path, apply: bool = False, store=None) -> dict:
    """Separe l'entete et l'accolade fermante des blocs ECF mono-ligne."""
    rep = {"id": "ecf_monoline", "edits": 0, "files": 0, "details": []}
    conf = Path(scenario) / "Content" / "Configuration"
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        text, eol = read_text_raw(path)
        out, n = [], 0
        for ln in text.split("\n"):
            m = _MONOLINE_RE.match(ln)
            if m is None or ln.lstrip().startswith("#"):
                out.append(ln)
                continue
            ind, corps = m.group(1), m.group(2).strip()
            out.append(ind + "{ " + corps)
            out.append(ind + "}")
            n += 1
        if not n:
            continue
        if apply:
            _apply(path, "\n".join(out), eol, store)
        rep["files"] += 1
        rep["edits"] += n
        rep["details"].append(path.name + " : " + str(n) + " bloc(s)")
    return rep


def fix_hitpoints_type(scenario: Path, apply: bool = False, store=None) -> dict:
    """Ajoute `, type: int` aux HitPoints/Armor qui n'en portent pas."""
    rep = {"id": "hitpoints_type", "edits": 0, "files": 0, "details": []}
    conf = Path(scenario) / "Content" / "Configuration"
    for name in _INT_FILES:
        path = conf / name
        if not path.is_file():
            continue
        text, eol = read_text_raw(path)
        out, n = [], 0
        for ln in text.split("\n"):
            m = _INT_RE.match(ln)
            if m is None or "type:" in ln:
                out.append(ln)
                continue
            ind, prop, val, comment = m.groups()
            out.append(ind + prop + ": " + val + ", type: int"
                       + (("  " + comment) if comment else ""))
            n += 1
        if not n:
            continue
        if apply:
            _apply(path, "\n".join(out), eol, store)
        rep["files"] += 1
        rep["edits"] += n
        rep["details"].append(name + " : " + str(n) + " propriete(s)")
    return rep


def scan_hitpoints_type(scenario: Path) -> list:
    """[(fichier, line, texte)] des HitPoints/Armor sans `type: int`."""
    conf = Path(scenario) / "Content" / "Configuration"
    out = []
    for name in _INT_FILES:
        path = conf / name
        if not path.is_file():
            continue
        for i, ln in enumerate(
                path.read_bytes().decode("utf-8", errors="replace")
                .replace("\r\n", "\n").split("\n"), 1):
            if _INT_RE.match(ln) and "type:" not in ln:
                out.append((name, i, ln.strip()))
    return out


def scan_ecf_monoline(scenario: Path) -> list:
    """[(fichier, line)] des blocs ECF ouverts et fermes sur la meme ligne."""
    conf = Path(scenario) / "Content" / "Configuration"
    out = []
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        for i, ln in enumerate(
                path.read_bytes().decode("utf-8", errors="replace")
                .replace("\r\n", "\n").split("\n"), 1):
            if not ln.lstrip().startswith("#") and _MONOLINE_RE.match(ln):
                out.append((path.name, i))
    return out


# ---------------------------------------------------------------------------
# References ECF : les deux crashs du 12/11 (playfield abandonne puis
# NullReferenceException dans DeployPciture, sans nom de fichier au log).
# ---------------------------------------------------------------------------
BASE_CONFIG = ("C:/Program Files (x86)/Steam/steamapps/common/Empyrion - "
               "Galactic Survival/Content/Configuration")


def _types_ecf(texte: str) -> set:
    """Types de blocs — l'element DOIT etre sur la ligne du `{`
    (`{ +Type ...`), c'est la seule forme que le chargeur accepte.

    Vecu 12/11 : des blocs ecrits `{` puis `+LootGroup Name: X` a la ligne
    suivante ont fait sortir le chargeur du tableau
    (`IndexOutOfRangeException` dans EcfFile.ParseLines) puis planter le jeu.
    Un scan tolerant (type sur la ligne suivante accepte) ne voyait rien :
    les blocs mal formes sont donc signales a part par `scan_ecf_openline`."""
    return set(re.findall(r"(?m)^\{ *\+?([A-Za-z]+)", texte))


def scan_ecf_openline(scenario: Path) -> list:
    """[(fichier, ligne)] des blocs dont la declaration n'est pas sur la ligne
    du `{` : forme rejetee par le chargeur (crash), vecu 12/11."""
    conf = Path(scenario) / "Content" / "Configuration"
    out = []
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        lignes = path.read_bytes().decode("utf-8", errors="replace").splitlines()
        for i, ln in enumerate(lignes, 1):
            if ln.strip() != "{":
                continue
            if i < len(lignes) and re.match(r"\s*\+?[A-Za-z]+\s+\w+\s*:", lignes[i]):
                out.append((path.name, i))
    return out


def scan_ecf_types(scenario: Path, base_config: Path | str = BASE_CONFIG) -> list:
    """[(fichier, [types en trop])] : un fichier de scenario contient un type de
    bloc absent du meme fichier en vanille.

    Vecu 12/11 : 10 blocs `+LootGroup` ecrits dans `Containers.ecf` (le fichier
    n'admet que `Container`) -> `IndexOutOfRangeException` dans
    `EcfFile.ParseLines` et crash du jeu."""
    conf = Path(scenario) / "Content" / "Configuration"
    base = Path(base_config)
    out = []
    for path in sorted(conf.glob("*.ecf")) if conf.is_dir() else []:
        ref = base / path.name
        if not ref.is_file():
            continue                    # fichier propre au scenario
        trop = (_types_ecf(path.read_bytes().decode("utf-8", errors="replace"))
                - _types_ecf(ref.read_bytes().decode("utf-8", errors="replace")))
        if trop:
            out.append((path.name, sorted(trop)))
    return out


def scan_container_slots(scenario: Path) -> list:
    """[(fichier, id, index)] : entrees de conteneur au-dela de l'index 19.

    Le moteur boucle `for (i < 20)` sur `Group_i`/`Name_i` : ces lignes sont
    ecrites mais jamais lues (vecu 12/11 : 34 entrees, dont tout le butin rare
    des coffres Eden). Ce n'est pas un crash, mais du contenu mort."""
    conf = Path(scenario) / "Content" / "Configuration"
    path = conf / "Containers.ecf"
    if not path.is_file():
        return []
    out = []
    cid = 0
    for ln in path.read_bytes().decode("utf-8", errors="replace").splitlines():
        m = re.match(r"\{\s*\+?Container Id: (\d+)", ln)
        if m:
            cid = int(m.group(1))
            continue
        m = re.match(r"\s*(?:Name|Group)_(\d+):", ln)
        if m and int(m.group(1)) >= 20:
            out.append((path.name, cid, int(m.group(1))))
    return out


# proprietes qui n'existent QUE dans SpawnZoneData (pas dans SpawnRateZoneData)
SPAWNZONE_ONLY = ("BiomesExcluded", "SpawnOnlyIfPoiIsAlien", "Entities")


def scan_spawnzone_schema(scenario: Path) -> list:
    """[(fichier, ligne)] : item de `SpawnRateZones:` portant une propriete de
    `SpawnZoneData`.

    Vecu 12/11 au soir : un en-tete `SpawnZones:` commente par erreur (ou avale
    par une edition de bloc) fait tomber ses items sous `SpawnRateZones:` ; le
    jeu tente de deserialiser des SpawnZoneData comme des SpawnRateZoneData :
    « Property 'BiomesExcluded' not found on type 'SpawnRateZoneData' »,
    playfield refuse (« unknown playfield type Undefined ») puis crash au
    chargement des planetes. Regle : les cles de SpawnZoneData n'ont rien a
    faire dans une section `SpawnRateZones:`."""
    pf = Path(scenario) / "Playfields"
    out = []
    for path in sorted(pf.glob("*/playfield*.yaml")) if pf.is_dir() else []:
        dans = False
        for i, ln in enumerate(path.read_bytes().decode("utf-8", errors="replace")
                               .splitlines(), 1):
            if re.match(r"^SpawnRateZones:\s*$", ln):
                dans = True
                continue
            if dans and re.match(r"^[A-Za-z_]", ln):
                dans = False
                continue
            if dans and re.match(r"^\s*(" + "|".join(SPAWNZONE_ONLY) + r"):", ln):
                out.append((path.parent.name, path.name, i))
                break
    return out


PDA_SEQ_KEYS = ("ChapterActivation", "Rewards", "Tasks", "RewardedChapters")


def scan_pda_sequences(scenario: Path) -> list:
    """[(fichier, ligne, cle)] : cle de chapitre PDA qui devrait etre une
    SEQUENCE mais porte un mapping.

    Vecu 12/11 : un `ChapterActivation:` ecrit en mapping (« Check: » au lieu
    de « - Check: ») fait jeter YamlDotNet « Expected 'SequenceStart', got
    'MappingStart' » : ce n'est pas le chapitre qui est perdu, c'est TOUT le
    PDA, donc plantage au chargement de la partie."""
    p = Path(scenario) / "Extras" / "PDA" / "PDA.yaml"
    if not p.is_file():
        return []
    lignes = p.read_bytes().decode("utf-8", errors="replace").splitlines()
    out = []
    for i, ln in enumerate(lignes):
        m = re.match(r"^(\s*)([A-Za-z]+):\s*$", ln)
        if not m or m.group(2) not in PDA_SEQ_KEYS:
            continue
        for j in range(i + 1, min(i + 4, len(lignes))):
            s = lignes[j].strip()
            if not s:
                continue
            if not s.startswith("- "):
                out.append((p.name, j + 1, m.group(2)))
            break
    return out


def scan_pda_activations(scenario: Path) -> list:
    """[(fichier, ligne, chapitre, check)] des activations de chapitre PDA
    (`ChapterActivation`) dont le Check exige une cible mais n'en porte pas
    (NearPoi / DialogOption sans `Names:` ni `Types:`).

    Vecu 14/11 : 13 activations mortes importees du pack RE2/ATL et de la
    vanille — le moteur genere alors des actions `CAA_*_T:-_N:-` qui ne
    peuvent jamais se declencher et crachent en boucle dans le log client
    ("Cannot create 'NearPoi' action ... no 'Names' specified" a chaque
    evaluation du PDA, "Cannot process 'DialogOption' event" a chaque
    dialogue). La donnee est ignoree : le chapitre ne s'activera jamais.
    """
    p = Path(scenario) / "Extras" / "PDA" / "PDA.yaml"
    if not p.is_file():
        return []
    lignes = p.read_bytes().decode("utf-8", errors="replace").splitlines()
    out = []
    chap = "?"
    i = 0
    n = len(lignes)
    while i < n:
        l = lignes[i]
        m = re.match(r"^  - ChapterTitle: *(\S+)", l)
        if m:
            chap = m.group(1)
            i += 1
            continue
        if re.match(r"^\s+ChapterActivation:\s*$", l):
            base = len(l) - len(l.lstrip())
            i += 1
            while i < n:
                l2 = lignes[i]
                m2 = re.match(r"^(\s*)- Check: *(\w+)", l2)
                if not m2:
                    mc = re.match(r"^  - ChapterTitle: *(\S+)", l2)
                    if mc:
                        chap = mc.group(1)
                    if l2.strip() and (len(l2) - len(l2.lstrip())) <= base                             and not l2.strip().startswith("-"):
                        break
                    i += 1
                    continue
                entree = [l2]
                j = i + 1
                while j < n:
                    l3 = lignes[j]
                    if re.match(r"^\s+- Check: ", l3):
                        break
                    if l3.startswith("  - ChapterTitle: "):
                        break
                    if l3.strip() and (len(l3) - len(l3.lstrip())) <= base                             and not l3.strip().startswith("-"):
                        break
                    entree.append(l3)
                    j += 1
                if m2.group(2) in ("NearPoi", "DialogOption") and not any(
                        re.search(r"^\s+(Names|Types):", x) for x in entree):
                    out.append((p.name, i + 1, chap, m2.group(2)))
                i = j
                continue
            continue
        i += 1
    return out


def scan_regen_policy(scenario: Path) -> list:
    """[(playfield, ligne, POI, valeur, voulue)] des POI hors politique.

    Politique (core/regen_policy.py) : vaisseaux, ancres `SpawnPOINear` et
    marchands intacts ; mines a 72 h ; tout le reste definitif. Un regen
    laisse a 720 rend les ressources infinies — le jeu ne s'en plaint pas,
    c'est le design qui fuit.
    """
    from core.regen_policy import scan as _scan
    return _scan(Path(scenario))


_ENTITY_RE = re.compile(r"^\{ *\+?Entity Name: *([A-Za-z0-9_]+)")
_ENTITY_MATERIAL_RE = re.compile(r"^\s*Material:\s*([A-Za-z0-9_]+)")
_MATERIAL_NAME_RE = re.compile(r"^\{ *\+?Material Name: *([A-Za-z0-9_]+)", re.M)


def scan_entity_materials(scenario: Path) -> list:
    """[(fichier, ligne, entite, materiau)] des entites dont le `Material:`
    n'est defini nulle part dans le `MaterialConfig.ecf` du scenario.

    Vecu 12/11 : 24 entites de RE2-FR portaient `Material: Mechanical`, absent
    des 49 materiaux du scenario (et de la vanille, 1.19 comme 1.20). Le
    moteur ne trouve alors aucune definition et retombe sur un comportement
    par defaut, **sans rien ecrire au log** : la resistance aux degats de ces
    creatures n'est plus celle prevue (cas d'ecole : la correction v1.20 des
    shotguns passe par le materiau de Mechanoid / TurretRobotV2 /
    AssaultCyborgCommando, qui ne nous atteint donc pas).

    Une entite qui herite son materiau par `Ref:` n'est pas signalee : seules
    les declarations explicites sont controlees.
    """
    conf = Path(scenario) / "Content" / "Configuration"
    matieres = conf / "MaterialConfig.ecf"
    entites = conf / "EClassConfig.ecf"
    if not matieres.is_file() or not entites.is_file():
        return []
    definis = set(_MATERIAL_NAME_RE.findall(
        matieres.read_bytes().decode("utf-8", errors="replace")))
    if not definis:
        return []
    out = []
    entite = ""
    texte = entites.read_bytes().decode("utf-8", errors="replace")
    for i, ligne in enumerate(texte.replace("\r\n", "\n").split("\n"), 1):
        trouve = _ENTITY_RE.match(ligne)
        if trouve:
            entite = trouve.group(1)
            continue
        materiau = _ENTITY_MATERIAL_RE.match(ligne)
        if materiau and materiau.group(1) not in definis:
            out.append((entites.name, i, entite, materiau.group(1)))
    return out


_DIALOGUE_RE = re.compile(r"\{\s*\+?Dialogue Name: ([^\n]+)")
_FUNCTIONS_RE = re.compile(r'\s*Functions:\s*"(.*)"\s*$')
_VARIABLE_RE = re.compile(r'\s*Variable_\d+:\s*"(\w+)"')
_DECL_RE = re.compile(
    r"\b(?:out\s+)?(?:int|var|long|float|double|bool|string)\s+(\w+)\b")
_SELF_RE = re.compile(r"\b(\w+)\s*=\s*\1\b")
# un champ Functions doit DECLARER des membres de classe : tout le reste
# (appel nu, statement) finit au niveau classe -> CS1520/CS0501
_FUNC_DECL_OK = ('void ', 'bool ', 'int ', 'float ', 'double ', 'string ',
                 'static ', 'Dictionary<', 'List<', 'string[] ', 'int[] ',
                 '//')
_DICT_KEY_RE = re.compile(r"\{\s*(\d+)\s*,")


def _cles_par_dictionnaire(code: str) -> list:
    """Compteurs de cles de CHAQUE litteral `Dictionary<...>() { ... }` du
    code. Le corps est delimite par comptage d'accolades, pour ne pas
    melanger les cles de dictionnaires voisins."""
    out: list = []
    for m in re.finditer(r"Dictionary<[^>]+>\s*\([^)]*\)\s*\{", code):
        i = m.end() - 1
        prof, j = 0, i
        while j < len(code):
            if code[j] == "{":
                prof += 1
            elif code[j] == "}":
                prof -= 1
                if prof == 0:
                    break
            j += 1
        cles: dict = {}
        for km in _DICT_KEY_RE.finditer(code[i + 1:j]):
            cles[km.group(1)] = cles.get(km.group(1), 0) + 1
        out.append(cles)
    return out


def scan_dialogue_functions(scenario: Path) -> list:
    """[(dialogue, type, detail)] : blocs Functions invalides.

    Vecus 17/11 (log 034353, classe Frontier_AppAtelier morte, console
    vide + figage au F) :
    - 'bare_call' : un Functions contenant un APPEL nu (OpenHtmlWindow(...))
      au lieu d'une declaration — le compilateur le prend pour un
      constructeur (CS0501). Le declencheur d'entree = champ Execute: ;
    - 'dup_key' : deux entrees de Dictionary de meme id dans un meme bloc
      (un bloc et un item peuvent partager un numero : Key 600 ->
      ArgumentException a l'execution, vente container morte) ;
    - 'quotes' : plus de 2 guillemets sur la ligne — un guillemet dans la
      valeur casse le delimiteur ECF : « line N is malformed -- ECF
      reading aborted », TOUT ce qui suit n est pas charge (vecu 17/11
      log 045650 : etats Frontier introuvables alors que presents) ;
    - 'output_char' : une apostrophe DANS une interpolation d'Output. Les
      Output sont emis en `$"..."` et ne passent PAS par la conversion
      apostrophe->guillemet : `{...('x', 0)}` forme un litteral caractere
      multi-caracteres (CS1012, tout l arbre meurt). Vecu 17/11 : ecran
      vide sur les deux consoles."""
    path = Path(scenario) / "Content" / "Configuration" / "Dialogues.ecf"
    if not path.is_file():
        return []
    out: list = []
    dlg = ""
    for i, ln in enumerate(path.read_bytes().decode(
            "utf-8", errors="replace").splitlines(), 1):
        m = _DIALOGUE_RE.match(ln)
        if m:
            dlg = m.group(1).strip()
            continue
        if ln.lstrip().startswith("Output:"):
            prof, dedans = 0, ""
            for ch in ln:
                if ch == "{":
                    prof, dedans = prof + 1, ""
                elif ch == "}" and prof:
                    prof -= 1
                    if "'" in dedans:
                        out.append((dlg, "output_char", f"ligne {i}"))
                elif prof:
                    dedans += ch
            continue
        m = _FUNCTIONS_RE.match(ln)
        if not m:
            continue
        v = m.group(1)
        if ln.count('"') != 2:
            out.append((dlg, "quotes", f"ligne {i} : "
                        f"{ln.count(chr(34))} guillemets"))
        code = v.lstrip()
        while True:
            if code.startswith("//"):
                nl = code.find("<nl>")
                code = code[nl + 4:].lstrip() if nl >= 0 else ""
            elif code.startswith("<nl>"):
                code = code[4:].lstrip()
            else:
                break
        if code and not code.startswith(_FUNC_DECL_OK):
            out.append((dlg, "bare_call", code[:40]))
        # ids dupliques PAR DICTIONNAIRE (un Dictionary.Add en double leve
        # ArgumentException a l'execution). Compter sur tout le bloc donnait
        # des faux positifs des qu'un bloc portait plusieurs dictionnaires
        # (prix + noms + cles de stock, vecu 18/11) : le vrai risque est une
        # cle repetee DANS LE MEME litteral.
        for cles in _cles_par_dictionnaire(v):
            for k, n in cles.items():
                if n > 1:
                    out.append((dlg, "dup_key", f"id {k} x{n}"))
    return out


def scan_ecf_valeurs_coupees(scenario: Path) -> list:
    """[(fichier, ligne)] : valeur ECF non refermee sur sa propre ligne.

    Vecu 17/11 (log 120714) : un generateur a introduit un SAUT DE LIGNE au
    milieu d'une valeur `Functions: "..."`. Le jeu repond
    « ECF config line N is malformed -- ECF reading aborted! » puis
    `Dialogue start state ... not found` : console VIDE, sans aucune erreur
    C#. On verifie donc que toute ligne Functions/Output/Execute se termine
    bien par son guillemet fermant (nombre de guillemets pair)."""
    conf = Path(scenario) / "Content" / "Configuration"
    dlg = conf / "Dialogues.ecf"
    if not dlg.is_file():
        return []
    cle = re.compile(r"^\s*(?:Functions|Output|Execute|Output_\d+):\s*\"")
    out: list = []
    for i, ln in enumerate(dlg.read_bytes().decode(
            "utf-8", errors="replace").replace("\r\n", "\n").split("\n"), 1):
        s = ln.rstrip()
        if not cle.match(s):
            continue
        if s.count('"') % 2:
            out.append((dlg.name, i))
    return out


def _racines_dialogue(blocs_tex: str) -> set:
    """Etats d'entree de NOS arbres : le `DialogueState` de chaque bloc
    Frontier_*.

    Vecu 17/11 soir : un regex `Name: ...\\n(?:.*?\\n)?  DialogueState:`
    ne tolere qu'UNE ligne entre les deux champs. Le bloc de la console
    d'atelier en a TROIS (CustomIcon, Class, DialogueState) : sa racine
    n'etait jamais trouvee, donc `scan_dialogue_dup_vars` et
    `scan_dialogue_fonctions_manquantes` ne parcouraient pas cet arbre et
    laissaient passer 15 CS0102 + 1 CS0103 (console VIDE en jeu). On lit
    desormais tout le corps du bloc."""
    out: set = set()
    for m in re.finditer(r"\{ \+?Block Id: \d+, Name: Frontier_\w+\n"
                         r"(.*?)(?=\n\{ |\Z)", blocs_tex, re.S):
        ds = re.search(r"^  DialogueState: (\S+)", m.group(1), re.M)
        if ds:
            out.add(ds.group(1))
    return out


def scan_dialogue_etats_manquants(scenario: Path) -> list:
    """[(etat, cible)] : un OptionNext/Next pointe vers un etat INEXISTANT.

    Vecu 18/11 : le jeu a charge un `Dialogues.ecf` PARTIEL (une regen
    ecrivait pendant la session) -> log « Dialogue state definition for
    Frontier_AppAtelier_TriOk not found! » x4, options mortes, sans autre
    message. Un fichier tronque casse TOUJOURS les derniers etats : ce
    scan le voit dans le fichier lui-meme, regen comprise."""
    conf = Path(scenario) / "Content" / "Configuration"
    path = conf / "Dialogues.ecf"
    if not path.is_file():
        return []
    tex = path.read_bytes().decode("utf-8", errors="replace"
                                  ).replace("\r\n", "\n")
    noms = set(re.findall(r"\{ \+Dialogue Name: (\S+)", tex))
    # mots-cles du moteur, pas des etats ; `undefined` est une sentinelle
    # du vanilla. On ne controle que NOS arbres (Frontier_*) : le vanilla
    # porte ses propres references cassees (RP_Tut_3_Guide_...).
    hors = {"End", "Return", "undefined"}
    out: list = []
    for m in re.finditer(r"\{ \+Dialogue Name: (\S+)\n(.*?)"
                         r"(?=\n\{ \+Dialogue|\Z)", tex, re.S):
        if not m.group(1).startswith("Frontier_"):
            continue
        for c in re.findall(r"^  (?:OptionNext|Next)_\d+: (\S+)",
                            m.group(2), re.M):
            c = c.strip().rstrip(",").strip('"')
            if c not in hors and c not in noms:
                out.append((m.group(1), c))
    return out


def scan_dialogue_blocs_non_fermes(scenario: Path) -> list:
    """[nom] des etats dont l'accolade fermante MANQUE.

    Vecu 18/11 : une edition du generateur avait supprime le `}` final du
    noeud Appro. Le parseur ECF voit alors le `{ +Dialogue` suivant comme
    IMBRIQUE dans le bloc precedent : les etats suivants n'existent pas
    pour le moteur -> « Dialogue state definition for X not found! » en
    cascade, alors que le fichier les contient et que tous les scans
    precedents etaient verts (ils decoupent sur `+Dialogue Name:` sans
    verifier l'equilibre des accolades)."""
    conf = Path(scenario) / "Content" / "Configuration"
    path = conf / "Dialogues.ecf"
    if not path.is_file():
        return []
    tex = path.read_bytes().decode("utf-8", errors="replace"
                                  ).replace("\r\n", "\n")
    out: list = []
    for m in re.finditer(r"\{ \+Dialogue Name: (\S+)\n", tex):
        i = m.start()
        prof, j = 0, i
        while j < len(tex):
            ch = tex[j]
            if ch == "{":
                if prof > 0 and tex.startswith("{ +Dialogue Name:", j):
                    out.append(m.group(1))   # bloc jamais referme
                    break
                prof += 1
            elif ch == "}":
                prof -= 1
                if prof == 0:
                    break
            j += 1
    return out


def scan_dialogue_fonctions_manquantes(scenario: Path) -> list:
    """[(arbre, fonction)] : fonction Frontier_* appelee dans un arbre mais
    declaree nulle part dans cet arbre.

    Vecu 17/11 (log 110340) : `Frontier_Cle` utilisee par Frontier_Stock et
    Frontier_Retirer sans que sa declaration ait ete inseree -> CS0103
    « The name 'Frontier_Cle' does not exist », arbre mort, console VIDE.
    Le compilateur fusionne les Functions des etats d'un arbre en une seule
    classe : une declaration suffit, ou qu'elle soit dans l'arbre."""
    conf = Path(scenario) / "Content" / "Configuration"
    dlg, blocs = conf / "Dialogues.ecf", conf / "BlocksConfig.ecf"
    if not dlg.is_file() or not blocs.is_file():
        return []
    tex = dlg.read_bytes().decode("utf-8", errors="replace"
                                  ).replace("\r\n", "\n")
    etats: dict = {}
    for m in re.finditer(
            r"\{ \+Dialogue Name: (\S+)\n(.*?)(?=\n\{ \+Dialogue|\Z)",
            tex, re.S):
        cibles = [c.strip().strip('"') for c in
                  re.findall(r"^  (?:OptionNext|Next)_\d+: (\S+)",
                             m.group(2), re.M) if c.strip() != "End"]
        etats[m.group(1)] = (cibles, m.group(2))
    racines = _racines_dialogue(blocs.read_bytes().decode(
        "utf-8", errors="replace").replace("\r\n", "\n"))
    decl = re.compile(r"\b(?:void|int|bool|float|double|string)\s+"
                      r"(Frontier_\w+)\s*\(")
    appel = re.compile(r"\b(Frontier_\w+)\s*\(")
    out: list = []
    for racine in sorted(racines):
        vus, pile, ordre = set(), [racine], []
        while pile and len(vus) < 20000:
            n = pile.pop()
            if n in vus or n not in etats:
                continue
            vus.add(n)
            ordre.append(n)
            pile.extend(etats[n][0])
        corps = "\n".join(etats[n][1] for n in ordre)
        declarees = set(decl.findall(corps))
        appelees = set(appel.findall(corps))
        for f in sorted(appelees - declarees):
            out.append((racine, f))
    return out


def scan_dialogue_dup_vars(scenario: Path) -> list:
    """[(etat, variable, etats)] : variable declaree DEUX fois dans le meme
    arbre de dialogue.

    Vecu 17/11 : `Frontier_DV2` declare dans le hub T2 et dans le noeud du
    container VENTE -> CS0102 « already contains a definition », la classe
    de l'arbre ne compile plus : la console commerce s'ouvre VIDE, sans
    aucun autre message en jeu. Deux arbres differents (T1/T2) peuvent
    legitimement declarer le meme nom. On parcourt donc depuis les racines
    declarees par NOS blocs (DialogueState des blocs Frontier_*)."""
    conf = Path(scenario) / "Content" / "Configuration"
    dlg, blocs = conf / "Dialogues.ecf", conf / "BlocksConfig.ecf"
    if not dlg.is_file() or not blocs.is_file():
        return []
    # CRLF : un fichier ecrit sous Windows casse les regex ancrees sur \n
    # (read_text normalise, read_bytes non) — vecu 17/11
    tex = dlg.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
    etats: dict = {}
    for m in re.finditer(r"\{ \+Dialogue Name: (\S+)\n(.*?)(?=\n\{ \+Dialogue|\Z)",
                         tex, re.S):
        cibles = [c.strip().strip('"') for c in
                  re.findall(r"^  (?:OptionNext|Next)_\d+: (\S+)",
                             m.group(2), re.M) if c.strip() != "End"]
        etats[m.group(1)] = (cibles,
                             re.findall(r'  Variable_\d+: "([^"]+)"', m.group(2)))
    racines = _racines_dialogue(blocs.read_bytes().decode(
        "utf-8", errors="replace").replace("\r\n", "\n"))
    out: list = []
    for racine in sorted(racines):
        vus, pile, ordre = set(), [racine], []
        while pile and len(vus) < 20000:
            n = pile.pop()
            if n in vus or n not in etats:
                continue
            vus.add(n)
            ordre.append(n)
            pile.extend(etats[n][0])
        props: dict = {}
        for n in ordre:
            for v in etats[n][1]:
                props.setdefault(v, []).append(n)
        for v, ou in props.items():
            if len(ou) > 1:
                out.append((racine, v, ou[:3]))
    return out


def scan_dialogue_vars(scenario: Path) -> list:
    """[(dialogue, variable)] : variable lue par la fonction C# generee mais
    jamais declaree (ni `int/var ... =` dans le bloc Functions, ni
    `Variable_N:` du noeud dialogue).

    Vecu 16/11 : Frontier_VendreContainer incrementait `vendus` et `total`
    sans les declarer -> CS0103, l'etat Frontier_TraderHub2 ne compile PLUS,
    la vente du container ne fait rien (aucun message en jeu) et chaque
    echec inonde le log client de 324 « Cannot process 'DialogOption' »
    (evenements PDA en attente rejetes tant que le script est casse)."""
    # le compilateur FUSIONNE les Variable_N et les Functions de tous les
    # etats d'un ARBRE dans une classe : une variable declaree dans le hub
    # est donc visible dans tous ses noeuds. On modelise pareil — un scan
    # par noeud signalait a tort Frontier_Spent2 (declaree par le hub T2
    # en Variable_4, lue par Frontier_VendreContainer) : vecu 18/11.
    conf = Path(scenario) / "Content" / "Configuration"
    path, blocs = conf / "Dialogues.ecf", conf / "BlocksConfig.ecf"
    if not path.is_file():
        return []
    tex = path.read_bytes().decode("utf-8", errors="replace"
                                  ).replace("\r\n", "\n")
    etats: dict = {}
    for m in re.finditer(r"\{ \+Dialogue Name: (\S+)\n(.*?)(?=\n\{ \+Dialogue|\Z)",
                         tex, re.S):
        corps = m.group(2)
        etats[m.group(1)] = (
            [c.strip().strip('"') for c in re.findall(
                r"^  (?:OptionNext|Next)_\d+: (\S+)", corps, re.M)
             if c.strip() != "End"],
            re.findall(r'  Variable_\d+: "([^"]+)"', corps),
            re.findall(r'^  Functions: "([^"]*)"', corps, re.M))
    racines = (_racines_dialogue(blocs.read_bytes().decode(
        "utf-8", errors="replace").replace("\r\n", "\n"))
        if blocs.is_file() else set(etats))
    out: list = []
    for racine in sorted(racines):
        vus, pile = set(), [racine]
        while pile:
            n = pile.pop()
            if n in vus or n not in etats:
                continue
            vus.add(n)
            pile.extend(etats[n][0])
        if not vus:
            continue
        # champs visibles depuis n'importe quel etat de l'arbre
        arbre_decl = {v for n in vus for v in etats[n][1]}
        arbre_decl |= {d for n in vus for f in etats[n][2]
                       for d in _DECL_RE.findall(f)}
        for n in sorted(vus):
            for f in etats[n][2]:
                for nom in sorted(set(_SELF_RE.findall(f))):
                    if nom not in arbre_decl:
                        out.append((n, nom))
    return out


_GROUP_NAME_RE = re.compile(r"^GroupName:[ \t]*([^#]+)")


def scan_space_poi_groups(scenario: Path) -> list:
    """[(fichier, ligne, groupe)] des `GroupName` de playfields SPATIAUX dont
    le groupe ne correspond a aucun prefab du scenario.

    Vecu 13/11 (Frontier-FR) : `SpaceTradingStationStarter/space_dynamic.yaml`
    portait un bloc a moitie commente — la ligne `- Type:` etait en
    commentaire, mais `GroupName: JunkYardSpace` restait ACTIVE. Le moteur
    cree alors un POI sans type ni prefab et casse la creation de partie
    (`NullReferenceException at PackageSite.IncreaseStub <- FindDisk`), juste
    apres un `Blueprint group 'JunkYardSpace' not found or empty!`.

    Les playfields de SURFACE sont exclus : un groupe vide y est courant
    (`NullPOI`, `DroneBaseSetup*`) et reste benin. Mesure : 0 cas dans la
    vanille 1.20 et dans RE2-FR, 1 seul ici.
    """
    from core.epb_blueprint import read_header
    root = Path(scenario)
    prefabs = root / "Prefabs"
    if not prefabs.is_dir():
        return []
    groupes = set()
    for path in prefabs.rglob("*.epb"):
        entete = read_header(path)
        if entete and entete[0]:
            groupes.add(entete[0].strip())
    if not groupes:
        return []
    out = []
    for path in sorted((root / "Playfields").glob("*/space_dynamic.yaml")):
        for i, ligne in enumerate(read_text_raw(path)[0].splitlines(), 1):
            strip = ligne.strip()
            if strip.startswith("#"):
                continue
            trouve = _GROUP_NAME_RE.match(strip)
            if trouve:
                groupe = trouve.group(1).strip().strip("'").strip()
                if groupe and groupe not in groupes:
                    out.append((str(path.relative_to(root)), i, groupe))
    return out


def scan_sector_double_space(scenario: Path) -> list:
    """[(fichier, coordonnees, [playfields])] des secteurs qui portent PLUS
    d'un playfield SPATIAL.

    Le corpus vanille n'en met jamais deux dans un secteur (mesure : 0 sur
    360). En ajouter un second fait creer au moteur un POI sans donnees de
    playfield : `NullReferenceException at PackageSite.IncreaseStub <-
    FindDisk` et la creation de partie est impossible (vecu 13/11 : la
    reintegration avait pose `Lava_Orbit` et `LavaCollided2_Orbit` dans un
    secteur qui avait deja son orbite). Le crash est systematique et son
    point d'apparition varie avec la graine — d'ou ce controle.
    """
    root = Path(scenario)
    sectors = root / "Sectors" / "Sectors.yaml"
    if not sectors.is_file():
        return []
    espaces = {p.parent.name for p in (root / "Playfields").glob(
        "*/space_dynamic.yaml")}
    if not espaces:
        return []
    out = []
    coord = ""
    block = []
    for i, ligne in enumerate(read_text_raw(sectors)[0].splitlines(), 1):
        strip = ligne.strip()
        if _SECTOR_COORD_RE.match(ligne):
            _flush_double(coord, block, espaces, sectors, out)
            coord = strip.split("Coordinates:", 1)[1].strip()
            block = []
            continue
        if _SECTOR_ITEM_RE.match(ligne) and not strip.startswith("#"):
            row = _SECTOR_ROW_RE.search(strip)
            if row:
                block.append(((row.group(3) or row.group(4) or "").strip(), i))
    _flush_double(coord, block, espaces, sectors, out)
    return out


def _flush_double(coord, block, espaces, sectors, out) -> None:
    spatiaux = [nom for nom, _l in block if nom in espaces]
    if coord and len(spatiaux) > 1:
        out.append((sectors.name, coord, spatiaux))


# entree playfield d'un secteur : `          - ['0,0,0', NomSecteur, Playfield, '']`
# l'offset contient des virgules : on ne peut PAS decouper sur la virgule
_SECTOR_ITEM_RE = re.compile(r"^[ \t]{8,}-[ \t]*\[")
_SECTOR_ROW_RE = re.compile(
    r"\[\s*'[^']*'\s*,\s*(?:'([^']*)'|([^,\]]+))\s*,"
    r"\s*(?:'([^']*)'|([^,\]]+))")
_SECTOR_COORD_RE = re.compile(r"^[ \t]{6}- Coordinates:")


# Cles admises dans un bloc POI de `playfield.yaml` (format ancien), relevees
# sur les 140 playfield.yaml des scenarios vanille 1.20. Les deux sous-sections
# sont des types DIFFERENTS pour le deserialiseur : dans `Random:` (RandomPoiData)
# ni `Name` ni `Prefab` n'existent — les y mettre fait echouer le playfield
# entier (« Property 'Name' not found on type 'PoiData+RandomPoiData' » puis
# « Playfield X has unknown playfield type Undefined », vecu 13/11).
_POI_RANDOM_KEYS = frozenset("""
AuxiliaryPOIs AvoidFactionTerritory Biome BiomesExcluded CountMinMax DroneBaseSetup
DroneProb DroneSetupID DronesMinMax Faction FactionTerritory GroupName InitPower
IsAuxPOI IsCommandCenter IsImportant IsScalingCount LevelMod NoShieldReload POIDistance
PlaceAt Properties ReserveCount ResourceDistance SpawnPOIAvoid SpawnPOIAvoidDistance
SpawnPOINear SpawnPOINearDistance SpawnPOINearRange SpawnResource SpawnResourceRange
Territory TroopTransport Type UseEachGroupPoiOnlyOnce""".split())
_POI_FIXED_KEYS = frozenset("""
Armor Faction FixedPlayerStart InitPower IsCommandCenter Items LevelMod Mode Name
NoShieldReload PlayerArmor Pos Prefab Properties ResourceDistance Rot RotY
SpaceDefenseOverrideDefaults SpaceDefensePrice SpaceDefensePriceMinMax
SpaceDefenseProbability Spawn SpawnResource SpawnResourceRange Status Structure SubMode
Type""".split())
_POI_ITEM_RE = re.compile(r"^[ 	]{8,}- (\w+):")


def scan_static_probability(scenario: Path) -> list:
    """[(fichier, ligne)] des cles `Probability:` dans les sections POIs des
    `playfield_static.yaml` (Random ET Fixed).

    `Probability` n'existe PAS sur PoiData.RandomPoiData/FixedPoiData
    (deobfusque 1.20.1 : seul SpaceDefenseProbability existe, et les POIs
    spatiaux des space_dynamic.yaml sont d'une autre classe ou Probability
    est admis). Sans statut explicite le POI spawnerait toujours : la cle
    est refusee par YamlDotNet -> « Property 'Probability' not found on
    type 'PoiData+RandomPoiData' » -> « Issue with deserializing playfield
    data! » + NRE, scenario impossible a selectionner. Vecu 15/11 : 96
    statics avec des POIs ajoutes portant Probability: 1. Le corpus
    vanille n'a AUCUN Probability dans ses statics (verifie).
    """
    root = Path(scenario)
    out = []
    for path in sorted((root / "Playfields").glob("*/playfield_static.yaml")):
        section = None
        for i, ligne in enumerate(read_text_raw(path)[0].splitlines(), 1):
            if re.match(r"^POIs:", ligne):
                section = "POIs"
                continue
            if section and re.match(r"^[A-Za-z]", ligne):
                section = None
                continue
            if not section:
                continue
            strip = ligne.strip()
            if not strip or strip.startswith("#"):
                continue
            if re.match(r"^Probability:", strip):
                out.append((str(path.relative_to(root)), i))
    return out


def scan_poi_keys(scenario: Path) -> list:
    """[(fichier, ligne, section, cle)] des cles inconnues dans un bloc POI de
    `playfield.yaml`. Le deserialiseur refuse alors TOUT le playfield : « the
    game will not start correctly » + « unknown playfield type Undefined ».

    Les cles d'un item POI vivent a deux retraits : celui du `- Cle:` d'ouverture
    et celui des cles suivantes (+2). Plus profond = sous-liste (`Properties:`),
    ignoree.
    """
    root = Path(scenario)
    out = []
    for path in sorted((root / "Playfields").glob("*/playfield.yaml")):
        section = None
        indent_item = None
        for i, ligne in enumerate(read_text_raw(path)[0].splitlines(), 1):
            if re.match(r"^POIs:", ligne):
                section, indent_item = "POIs", None
                continue
            if re.match(r"^[A-Za-z]", ligne):
                section, indent_item = None, None
                continue
            strip = ligne.strip()
            if section is None or not strip or strip.startswith("#"):
                continue
            if strip in ("Random:", "Fixed:"):
                section, indent_item = strip[:-1], None
                continue
            if section not in ("Random", "Fixed"):
                continue
            trouve = re.match(r"^([ 	]*)(?:- )?(\w+):", ligne)
            if not trouve:
                continue
            indent = len(trouve.group(1))
            if indent_item is None:
                if not strip.startswith("- "):
                    continue
                indent_item = indent
            if indent not in (indent_item, indent_item + 2):
                continue
            cle = trouve.group(2)
            if cle in ("Key", "Value"):    # sous-liste Properties:, jamais un POI
                continue
            admises = _POI_RANDOM_KEYS if section == "Random" else _POI_FIXED_KEYS
            if cle not in admises:
                out.append((str(path.relative_to(root)), i, section, cle))
    return out


_PDA_TASK_KEYS = ("OnCompletePdaDataOps", "OnCompletePlayfieldOps",
                  "OnCompletePlayerOps")


def scan_pda_task_keys(scenario: Path) -> list:
    """[(fichier, ligne, cle)] des cles de NIVEAU TACHE ecrites au niveau
    chapitre dans `Extras/PDA/PDA.yaml`.

    Vecu 13/11 : `OnCompletePdaDataOps` place sous le chapitre fait jeter tout
    le PDA par le deserialiseur (« Property 'OnCompletePdaDataOps' not found
    on type 'Eleon.Pda.ChapterData' » puis « No or incomplete PDA data ») : le
    jeu tourne mais AUCUNE mission n'existe. Ces cles n'existent qu'au niveau
    tache (indentation 8 espaces ; `schema.TASK_ADVANCED_KEYS`).
    """
    root = Path(scenario)
    pda = root / "Extras" / "PDA" / "PDA.yaml"
    if not pda.is_file():
        return []
    out = []
    for i, ligne in enumerate(read_text_raw(pda)[0].splitlines(), 1):
        strip = ligne.strip()
        if strip.startswith("#") or not strip.endswith(":"):
            continue
        cle = strip[:-1]
        if cle not in _PDA_TASK_KEYS:
            continue
        indent = len(ligne) - len(ligne.lstrip())
        if indent <= 4:              # 4 = chapitre ; 8 = tache
            out.append((str(pda.relative_to(root)), i, cle))
    return out


def scan_sectors_header(scenario: Path) -> list:
    """[(fichier, 0, "SolarSystems")] si le `Sectors.yaml` n'a plus son
    en-tete. Le jeu ne parse alors plus la galaxie et refuse de lancer :
    « Property 'Name' not found on type ...StubTreeRegistryCollection » puis
    « No sectors specified ». Vecu 13/11 : une reecriture du fichier avait
    perdu les 7 premieres lignes (`GalaxyMode`, `Sectors: []`,
    `SolarSystems:`). `yamlcheck` ne le voit pas : le YAML reste valide.
    """
    root = Path(scenario)
    sectors = root / "Sectors" / "Sectors.yaml"
    if not sectors.is_file():
        return []
    texte = read_text_raw(sectors)[0]
    if not re.search(r"^SolarSystems:", texte, re.M):
        return [(sectors.name, 0, "SolarSystems")]
    return []


def scan_sun_warp_targets(scenario: Path) -> list:
    """[(fichier, ligne, systeme)] des systemes `SolarSystems` qui portent
    un playfield soleil (`Sun*`) mais AUCUN secteur `SpaceWarpTarget`.

    Le routeur warp vise a l'arrivee les portes `<Systeme> [Sun Right]`...
    autour du soleil : sans secteur SpaceWarpTarget dans le systeme,
    « Sector for playfield 'X [Sun Right]' not found » puis
    DirectoryNotFoundException et NRE/ArgumentNullException en boucle a
    chaque frame — obligation de quitter (vecu 15/11 : systeme SoS converti
    du legacy, qui n'avait pas de portes). Sont exclus : les systemes
    d'instance (marque `# INSTANCE`, atteints par teleport PDA, jamais au
    warp) et les systemes au style flow ancien (secteurs lignes directes,
    sans secteur imbrique `- Coordinates:` — corpus de test historique).
    """
    root = Path(scenario)
    sectors = root / "Sectors" / "Sectors.yaml"
    if not sectors.is_file():
        return []
    out = []
    nom = ""
    ligne_nom = 0
    soleil = False
    porte = False
    imbrique = False

    def flush():
        nonlocal nom, ligne_nom, soleil, porte, imbrique
        if nom and imbrique and soleil and not porte:
            out.append((sectors.name, ligne_nom, nom))
        nom, ligne_nom, soleil, porte, imbrique = "", 0, False, False, False

    for i, ligne in enumerate(
            read_text_raw(sectors)[0].splitlines(), 1):
        m = re.match(r"^ {2,4}- Name: *(.+?)\s*$", ligne)
        if m:
            flush()
            nom = m.group(1).strip().strip("'\"")
            ligne_nom = i
            continue
        if not nom:
            continue
        if _SECTOR_COORD_RE.match(ligne):
            imbrique = True
        if "INSTANCE" in ligne.upper() and "#" in ligne:
            porte = True  # systeme d'instance : jamais atteint au warp
            continue
        if _SECTOR_ITEM_RE.match(ligne) and not ligne.strip().startswith("#"):
            row = _SECTOR_ROW_RE.search(ligne.strip())
            if row:
                type_pf = (row.group(3) or row.group(4) or "").strip()
                if type_pf.casefold().startswith("sun"):
                    soleil = True
                elif type_pf.startswith("SpaceWarpTarget"):
                    porte = True
    flush()
    return out


def scan_sector_composition(scenario: Path) -> list:
    """[(fichier, ligne, secteur, code)] des secteurs `SpaceWarpTarget`
    qui portent une SECONDE entree playfield.

    Le corpus vanilla n'y met que la porte de warp (0 cas sur 360 secteurs) ;
    y poser une lune ou une orbite charge le secteur en playfields
    concurrents au meme offset (vecu 13/11 : 26 secteurs ainsi composes apres
    reintegration de playfields orphelins — la consequence en jeu n'est pas
    prouvee, RE2-FR en porte 59 et se lance, d'ou un simple avertissement).
    """
    root = Path(scenario)
    sectors = root / "Sectors" / "Sectors.yaml"
    if not sectors.is_file():
        return []
    out = []
    coord = ""
    block = []

    def flush():
        if not coord or len(block) < 2:
            return
        if not any(n.casefold().startswith("spacewarptarget")
                   for _l, n in block):
            return
        for line, name in block:
            if not name.casefold().startswith("spacewarptarget"):
                out.append((sectors.name, line, coord, "warp"))
                return

    for i, ligne in enumerate(
            read_text_raw(sectors)[0].split("\n"), 1):
        strip = ligne.strip()
        if _SECTOR_COORD_RE.match(ligne):
            flush()
            coord = strip.split("Coordinates:", 1)[1].strip()
            block = []
            continue
        if _SECTOR_ITEM_RE.match(ligne) and not strip.startswith("#"):
            row = _SECTOR_ROW_RE.search(strip)
            if row:
                name = row.group(3) or row.group(4) or ""
                block.append((i, name.strip()))
    flush()
    return out


def scan_blocs_frontier_loc(scenario: Path) -> list:
    """[(bloc, cle)] : blocs `Frontier_*` dont la cle `Info:` manque dans
    Extras/Localization.csv -> le jeu affiche le nom technique (vecu 18/11 :
    regen_apps n'ecrivait pas la localisation, et la regen commerce purgeait
    ensuite ces cles).

    Limite volontairement a NOS blocs : trois blocs vanilla du corpus
    (RadarTracker, TrapDoor, HeavyWindowA) pointent vers la cle d'un AUTRE
    bloc, cas legitime qu'un scan global signalerait a tort."""
    root = Path(scenario)
    blocks = root / "Content" / "Configuration" / "BlocksConfig.ecf"
    loc = root / "Extras" / "Localization.csv"
    if not blocks.is_file() or not loc.is_file():
        return []
    cles = {ln.split(",", 1)[0].strip().strip('"')
            for ln in loc.read_bytes().decode("utf-8-sig",
                                              errors="replace").splitlines()}
    texte = blocks.read_bytes().decode("utf-8-sig", errors="replace")
    out = []
    for m in re.finditer(r"\{\s*\+?Block Id: \d+, Name: (Frontier_\w+)"
                         r"\r?\n(.*?)(?=\r?\n\{ |\Z)", texte, re.S):
        cle = re.search(r"^  Info: ([^\s,]+)", m.group(2), re.M)
        if cle and cle.group(1) not in cles:
            out.append((m.group(1), cle.group(1)))
    return out


def scan_deco_showuser(scenario: Path) -> list:
    """[(bloc, showuser)] : decorations de biome rendues visibles.

    Un bloc `Shape: Deco` (plante/arbre/rocher de biome) avec
    `ShowUser` != No est enregistre comme bloc joueur : le chargement du
    playfield passe alors dans `InstancingManager.AddPrefab(BlockId)` et
    crashe en NullReferenceException (vecu 18/11 : HollywoodJuniperDesktop
    passe en Yes -> crash au chargement d'Akua).

    `IsTerrainDecoration: true` n'est PAS un critere : les deployables
    visibles (tentes, lampes, AutoMiningDevice) le portent legitimement.
    """
    root = Path(scenario)
    blocks = root / "Content" / "Configuration" / "BlocksConfig.ecf"
    if not blocks.is_file():
        return []
    texte = blocks.read_bytes().decode("utf-8-sig", errors="replace")
    champs: dict = {}
    out = []
    for m in re.finditer(r"\{\s*\+?\s*(?:Block\s+)?(?:Id:\s*\d+,\s*)?"
                         r"Name:\s*(\S+)\s*[,\n](.*?)(?=\n\{\s|\Z)",
                         texte, re.S):
        nom, corps = m.group(1), m.group(2)
        d = {}
        for k in ("Shape", "ShowUser", "Ref", "IsTerrainDecoration"):
            mm = re.search(r"^\s*" + k + r":\s*([^\n#]*)", corps, re.M)
            if mm:
                d[k] = mm.group(1).strip().strip('"')
        if "Ref" in d and d["Ref"] in champs:
            base = dict(champs[d["Ref"]])
            base.update(d)
            d = base
        champs[nom] = d
        shape = (d.get("Shape") or "").lower()
        visible = (d.get("ShowUser") or "").lower() not in ("no", "nobutcsv")
        if visible and shape == "deco":
            out.append((nom, d.get("ShowUser") or "defaut"))
    return out