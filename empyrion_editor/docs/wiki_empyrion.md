# Wiki Empyrion — structure des scenarios et proprietes ECF/YAML

Base sur la documentation communautaire (wiki officiel Empyrion sur Fandom, guides Steam,
forums officiels, outil eWCCT). Les informations les plus specifiques (valeurs exactes de
proprietes rares) meritent toujours une verification en jeu -- la documentation communautaire
evolue avec les mises a jour du jeu et n'est pas toujours a jour a 100%.

---

## 1. Structure d'un dossier de scenario

```
MonScenario/
├── Content/
│   └── Configuration/       <- Tous les fichiers .ecf de gameplay (voir section 2)
├── Playfields/               <- Un sous-dossier par playfield, avec son .yaml
├── Prefabs/                  <- Blueprints (.epb) des POI/vaisseaux customs
├── RandomPresets/             <- Fichiers SolarSystemConfig.yaml (generation procedurale)
├── Sectors/                  <- Sectors.yaml (structure de la galaxie)
├── Extras/                   <- Dialogues.csv, Localization.csv, autres CSV
├── SharedData/                <- Contenu partage entre plusieurs sous-scenarios/DLC
├── gameoptions.yaml            <- Options de partie par defaut
└── description.txt / Logos/   <- Metadonnees d'affichage du scenario
```

**Regle generale (confirmee par plusieurs guides communautaires)** : seuls les fichiers que tu
modifies reellement ont besoin d'etre presents dans le dossier de ton scenario -- tout fichier
absent est simplement herite du jeu de base (vanilla). C'est pour ca qu'un scenario "leger" ne
contient parfois que quelques fichiers dans `Content/Configuration`.

---

## 2. Les fichiers .ecf de `Content/Configuration`

| Fichier | Contenu |
|---|---|
| `BlocksConfig.ecf` | Tous les blocs constructibles (structure, hitpoints, materiau, categorie de placement...) |
| `ItemsConfig.ecf` | Tous les objets : armes, munitions, objets a main, consommables -- **y compris les items lies aux vehicules et bases** (ex: foreuses de vehicule), pas seulement les objets portes par le joueur |
| `Templates.ecf` | Recettes de craft (quels items produisent quel objet, avec quels ingredients) |
| `Containers.ecf` | Contenus par defaut des conteneurs (coffres, sacs...) |
| `LootGroups.ecf` | Groupes de loot utilises par les POI et conteneurs generes aleatoirement |
| `EClassConfig.ecf` | Classes d'entites (NPC, creatures) |
| `EGroupsConfig.ecf` | Groupes d'entites |
| `DefReputation.ecf` | Reputation par defaut envers les differentes factions |
| `FactionWarfare.ecf` | Regles de guerre entre factions |
| `MaterialConfig.ecf` | Proprietes des materiaux (resistance, etc.) |
| `StatusEffects.ecf` | Effets de statut (buffs/debuffs) |
| `TraderNPCConfig.ecf` | Configuration des marchands PNJ |
| `TokenConfig.ecf` | Jetons/codes de verrouillage utilises par les portes, coffres... (lies au systeme de dialogue) |
| `Dialogues.ecf` | Arbres de dialogue des PNJ |
| `Dialogues.csv` / `Localization.csv` | Textes localises utilises par les dialogues et l'interface |
| `GalaxyConfig.ecf` | Parametres globaux de generation de galaxie |
| `Config.ecf` (ou `Config_Example.ecf`) | Fichier de **surcharge** legere -- voir section 4, usage limite |

---

## 3. Syntaxe des fichiers .ecf

Format proprietaire d'Eleon, **pas du JSON ni du YAML** meme s'il y ressemble. Un bloc
("objet") s'ecrit entre accolades :

```
{ Block Id: 399, Name: ConcreteBlocks
  Material: concrete
  BlockColor: "170,170,170"
  Info: bkiBlockGroup, display: true
  IsOxygenTight: true, display: true
  HitPoints: 600, type: int, display: false
  Mass: 1100, type: float, display: true, formatter: Kilogram
  Volume: 10, type: float, display: true, formatter: Liter
  Category: BuildingBlocks
  ChildBlocks: "ConcreteFull, ConcreteThin, ConcreteExtended"
  UnlockCost: 0
  UnlockLevel: 1
}
```

Points cles (source : guide Steam "Gentle guide to .ECF modding", confirme par le forum
officiel) :

- **`Id`** identifie le bloc/item de facon unique dans le fichier. Certains blocs reels n'ont
  **pas d'Id du tout** et sont identifies seulement par `Name` -- convention plus rare mais
  bien reelle (ex: `{ Block Name: LegacyForcefield ...}`).
- **`Name`** est le nom interne (pas le nom affiche en jeu -- celui-la vient de la
  localisation). **Ne jamais changer l'Id ou le Name d'un bloc/item existant** : ca casse les
  references dans les autres fichiers et les sauvegardes existantes.
- **`Ref: AutreNom`** fait heriter un bloc/item des proprietes d'un autre (mecanisme
  d'heritage) -- tres utilise pour creer des variantes (ex: une arme "Epic" qui herite de
  l'arme de base et ne redefinit que les stats qui changent).
- Une propriete peut avoir des **sous-attributs** apres une virgule : `type` (int/float/string),
  `display` (true/false -- affiche ou non l'info-bulle en jeu), `formatter` (unite d'affichage :
  `Kilogram`, `Liter`, `Watt`, `ROF`...).
- Les valeurs contenant une **virgule** doivent etre entre guillemets :
  `AllowPlacingAt: "Base,MS", display: true`. Une virgule non protegee casse le parsing.
- **Commentaires** : tout ce qui suit un `#` sur une ligne est ignore par le jeu.
- Le prefixe **`+`** avant un genre de bloc (`+Block`, `+Container`...) signale un **patch**
  qui complete une definition existante du meme Id, plutot qu'une nouvelle definition
  independante -- convention frequente dans les gros fichiers modifies au fil du temps.
- Une erreur de syntaxe (accolade manquante, virgule non protegee, propriete dupliquee) peut
  empecher le fichier entier de charger, avec un message dans la console du jeu (touche
  antiquote pour l'ouvrir) du type "Ignored unknown parameter(s) in element...".

### Sous-blocs imbriques
Un item peut contenir des sous-blocs (ex: `{ Mode Id: 0 ... }` pour un mode d'arme,
`{ Child Inputs ... }` pour les ingredients d'une recette). Un item peut avoir **plusieurs
`Mode`** pour representer plusieurs modes de tir (semi-auto/rafale, etc.).

---

## 4. `Config.ecf` vs les fichiers dedies -- un piege frequent

Confirme par de nombreux fils de discussion officiels (le sujet revient tres souvent) :
**`Config.ecf` ne peut surcharger QUE les proprietes deja presentes dans
`Config_Example.ecf`** -- ce n'est pas un fichier de surcharge universel. Si tu veux modifier
une propriete qui n'existe pas dans `Config_Example.ecf` (ex: `AllowPlacingAt` pour un bloc
donne), il faut editer directement `BlocksConfig.ecf` (ou le fichier dedie correspondant),
**pas `Config.ecf`**. Tenter de le faire dans `Config.ecf` produit une erreur silencieuse en
jeu ("Ignored unknown parameter(s)"), sans planter, mais sans effet non plus.

Consequence pratique : pour la plupart des mods de scenario serieux, on modifie directement les
fichiers dedies (`BlocksConfig.ecf`, `ItemsConfig.ecf`...) plutot que `Config.ecf`.

---

## 5. Les fichiers `.yaml` (playfields)

Contrairement aux `.ecf`, les playfields utilisent un **vrai YAML** (indentation, listes `-`).
Fichier principal : `playfield.yaml` (ou `playfield_static.yaml` / `playfield_dynamic.yaml`
selon le type) dans `Playfields/<NomDuPlayfield>/`.

### Ajouter un POI custom (base sur le guide officiel "Customized POIs")
1. Placer le fichier `.epb` du blueprint dans `Prefabs/`.
2. Dans le `playfield.yaml`, chercher la section `POIs: ... Random:` et ajouter une entree :
```yaml
- GroupName: JunkT1
  CountMinMax: [4, 5]
  DroneProb: 0
  DronesMinMax: [0]
  ReserveCount: 0
  TroopTransport: False
  SpawnPOINear: [START]
  SpawnPOINearRange: [500, 1000]
  Properties:
    - Key: MapDistance
      Value: 600
    - Key: MapMarker
      Value: Neutral
    - Key: RegenAfter
      Value: 720
```
3. `GroupName` doit correspondre au nom de groupe de ton blueprint (un POI ne peut appartenir
   qu'a **un seul** groupe).

**Piege important, confirme par le forum officiel** : modifier un `playfield.yaml` n'affecte
**que les nouvelles parties** (ou les playfields jamais visites dans une sauvegarde existante).
Un playfield deja genere dans une sauvegarde en cours garde son etat en cache -- les
changements sur les POI de planetes/lunes ne s'appliquent pas retroactivement (contrairement
aux playfields spatiaux, plus flexibles a ce niveau).

Les lignes marquees "Please don't change" ou "No functionality yet" dans le fichier lui-meme
sont a eviter (info du wiki officiel, "Customizing Solar Systems").

---

## 6. RandomPresets / Sectors -- generation de la galaxie

- `RandomPresets/*.yaml` (fichiers `SolarSystemConfig.yaml`) controlent la generation
  procedurale des systemes solaires.
- `Sectors/Sectors.yaml` definit la structure de la galaxie (quels secteurs, quelles planetes
  de depart).
- `gameoptions.yaml` / `gameoptions_example.yaml` : options de partie par defaut proposees a
  la creation d'une nouvelle partie avec ce scenario.

Convention communautaire frequente pour un scenario "leger" (juste des configs modifiees, pas
un monde entierement custom) : copier ces fichiers depuis le scenario "Default Random" du jeu
de base tel quel, et ne modifier que `Content/Configuration`.

---

## 7. Dialogues, Tokens et Localisation

- **`Dialogues.ecf`** definit les arbres de dialogue des PNJ et des blocs interactifs (portes
  a code, panneaux...). Un bloc peut declencher un dialogue via la propriete
  `ExecuteOnActivate` dans `BlocksConfig.ecf`.
- **`TokenConfig.ecf`** definit les codes de verrouillage (1 a 9999) utilisables sur les portes
  et conteneurs, lies au systeme de dialogue.
- **`Localization.csv`** contient les textes traduits utilises par les dialogues et
  l'interface -- structure typique : une colonne `Key`, puis une colonne par langue
  (`English`, `Deutsch`, `Français`...).
- Les dialogues supportent des variables dynamiques (`{PlayerName}`) et des fonctions
  avancees (`Execute`/`ExecuteEditor`, en C# simplifie) pour des mecaniques de quete
  personnalisees.

---

## 8. Points de vigilance generaux pour la fusion/modification de scenario

1. **Toujours travailler sur une copie**, jamais sur les fichiers vanilla ou un scenario en
   ligne (confirme par tous les guides communautaires consultes).
2. **Ne jamais changer l'Id ou le Name** d'un bloc/item deja reference ailleurs (recettes,
   loot tables, playfields) -- ca casse les references.
3. Une **virgule non protegee** dans une valeur de liste (`AllowPlacingAt: Base,MS` au lieu de
   `"Base,MS"`) est l'erreur de syntaxe la plus frequemment signalee dans les forums.
4. Verifier la console en jeu (touche antiquote) apres chargement pour reperer les erreurs de
   parsing -- le jeu indique souvent precisement quel element pose probleme.
5. Un playfield deja visite dans une sauvegarde ne recharge pas ses changements de POI --
   tester sur une **nouvelle partie**.
6. Un Id partage entre deux definitions differentes (par exemple lors d'une fusion entre deux
   scenarios independants) est une source reelle et documentee de conflits -- c'est
   precisement ce que le garde-fou anti-collision de cet outil est concu pour detecter (voir
   le wiki de l'application).

---

## Sources consultees

- Wiki officiel Empyrion (Fandom) -- pages "Guide/Customized POIs", "Guide/Customizing Solar
  Systems", "Scenarios"
- Steam Community, guide "Gentle guide to .ECF modding" (zaphodikus et al.)
- Steam Community, guide "Custom Scenarios for Dummies"
- Steam Workshop, "Scenario for Custom Config Mods"
- Forums officiels Empyrion (empyriononline.com) -- fils sur Config.ecf, ItemsConfig.ecf,
  terrain.ecf
- Discussions Steam Community sur les erreurs de parsing ECF
- Documentation de l'outil communautaire eWCCT (Empyrion Web Config Creator Tool) pour le
  systeme de dialogue/tokens
