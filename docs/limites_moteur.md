# Limites du moteur Empyrion — référentiel

Toutes les valeurs ci-dessous sont **vérifiées contre le chargement réel du jeu**
(v1.19.6, build 5188) et contre les fichiers de configuration vanilla officiels
(`Content/Configuration/`). Ce fichier est le référentiel à respecter pour toute
création ou modification de scénario.

## Identifiants de blocs (BlocksConfig.ecf)

| Limite | Valeur | Preuve |
|---|---|---|
| Id explicite max | **2047** | message de chargement : « Not allowed to assign a block id >= 2048 in BlocksConfig.ecf (…). Please leave the 'Id:' out! » — le bloc est rejeté (Id mis à -1) |
| Blocs TERRAIN | **0 à 255 réservés** | header officiel BlocksConfig : « Terrain blocks are stored for id=0 to id=255. Do NOT use other blocks there! » |
| Blocs par nom seul | **plage 2048 → 8192** (6144 emplacements) | code du chargeur 5188 : `CopySolution(2048, 8192, …)` dimensionne la table ; vérifié au chargement réel : 4177 blocs sans `Id:` (total > 4096) → READY, aucun « out of range ». Le commentaire du header officiel (« 2048 de plus → 4096 total ») est OBSOLÈTE |
| Encodage interne des Ids | jusqu'à **8191** (3 plages de 2048 marquées par drapeaux ≥2048 / ≥4096) | code de chargement (getter/setter d'Id compressé) |
| Doublon de nom | « Block X is overridden » : la 2ᵉ déclaration remplace la 1ʳᵉ (avertissement, pas un refus) | chargement réel |

À noter : un bloc vanilla commenté (`# Block Id: 2048`) montre que même le
contenu officiel respecte la barrière des 2048 pour les Id explicites.
Un bloc sans `Id:` dont le nom est absent du mapping de la sauvegarde déclenche
l'erreur FATALE « No block id mapping found for block X » (code du chargeur).

## Identifiants d'objets (ItemsConfig.ecf)

| Limite | Valeur | Preuve |
|---|---|---|
| Plage d'Id recommandée | **0 à 2047** | encodage interne des Ids sur 11 bits (masque 0x7FF) ; l'éditeur refuse un `Id >= 2048` dans ItemsConfig (vérifié en chargement réel) |
| Id vanilla max | 1444 (le contenu officiel laisse ~600 Id libres) | ItemsConfig vanilla |
| Items sans stack déclarée | pile par défaut **999** | code de chargement : absent de `StackSize` → 999 |

## Piles et objets

| Limite | Valeur | Preuve |
|---|---|---|
| `StackSize` vanilla | de 1 à 50 000 | ItemsConfig vanilla |
| Durée de vie d'un objet jeté | 200 s par défaut (`LifetimeOnDrop`) | header officiel ItemsConfig |
| Armures : boosters `SlotItems` | **15 entrées max** | header officiel ItemsConfig |
| Perceuses/forages : rayon | **≤ 5** | message du code : « Driller id={0}: Radius must be less or equal 5 » |

## Arbre technologique

| Limite | Valeur | Preuve |
|---|---|---|
| Chaîne `TechTreeParent` | **5 niveaux max** (exception « TechTree recursion error » au-delà) | code de chargement |
| Niveaux de déverrouillage | 9 paliers : 1 / 3 / 5 / 7 / 10 / 12 / 15 / 20 / 25 (`UnlockLevel` vanilla ≤ 25) | ItemsConfig + BlocksConfig vanilla |
| `UnlockCost` vanilla | jusqu'à 86 | configs vanilla |
| Continuité des voies | le jeu signale « Item unlock level of higher tier <= lower tier: X » quand un enfant a un niveau inférieur ou égal à son parent | message de chargement |

## Blueprints (fabriqués et POI)

| Limite | Valeur | Preuve |
|---|---|---|
| `MaxCount` par bloc | chaque bloc peut limiter son nombre par blueprint (ex : réacteur de warp, noyau) ; sans le champ, pas de limite | code de chargement + BlocksConfig vanilla |
| `ForceMaxCount` | force la limite même si le niveau de difficulté la désactive | header officiel BlocksConfig |
| Groupes de blocs (BlockGroups) | `MaxCount` obligatoire sur chaque groupe : « Property 'MaxCount' missing in BlockGroups » | message de chargement |
| Dépassement | « Prefab uses too many of these blocks: » liste blocs interdits ou excédentaires au chargement d'un POI | messages de chargement |

## Galaxie (GalaxyConfig.ecf)

| Limite | Valeur | Preuve |
|---|---|---|
| Régions stellaires | `Child StarRegion_1` à `StarRegion_99` (99 max) | header officiel GalaxyConfig |
| Territoires | `Child Territory_1` à `Territory_20` (20 max) ; 1-10 factions `Other_` par territoire | header officiel GalaxyConfig |
| Modèles de soleils | liste fermée : SunBlueGiant, SunWhiteDwarf, SunYellowWhite, SunYellow, SunRedGiant, SunRedDwarf, SunNeutron, BlackHole ; seule la liste des classes est personnalisable, pas les modèles | header officiel GalaxyConfig |
| Étoiles doubles | `CompanionStarClass:` ajoutée à une définition StarClass ; 2ᵉ étoile décorative | header officiel GalaxyConfig |

## Divers

| Limite | Valeur | Preuve |
|---|---|---|
| **Référence ECF inexistante** | tout nom cité (`Material`, `AmmoType`, `Sfx*`, `Pfx*`) doit exister dans les configs du **scénario** — pas seulement dans la vanille. Un `Material` inconnu lève `System.Exception: Material 'x' not found in item 'N'` pendant `ConfigFile.load`, le playfield est abandonné (`NullReferenceException` dans `DeployPciture`) et le **jeu crashe**. Vécu 12/11 avec `Material: metalweapon` (vanille) importé dans RE2-FR, qui ne déclare plus ce matériau : corriger en `Device` (celui des `TurretMS*Weapon` du scénario). | log client 22:34, `GroupTree.TestDevice` → `EcfFile.ParseLines` |
| **Importer un item de la vanille** | vérifier dans le scénario : `Material`, `AmmoType`, `Meshfile` (`@models/...`), `Sfx*` ; ids libres (RE2 vit jusqu'à 2010) ; le nom n'a pas été réassigné (`RocketLauncherMSWeapon` occupait l'id 110, repris par `CannonCVT1Weapon`) | ItemsConfig RE2-FR |

| Limite | Valeur | Preuve |
|---|---|---|
| PrixEquipage/défense BA | « BA Defense: Scenario price exceeds max price, the price will be reduced » : les prix de scénario sont plafonnés à l'import | message de chargement |
| Placer un bloc | `AllowPlacingAt: "Base,MS,SS,GV,Terrain"` | header officiel BlocksConfig |
| Explosions | types 1-9 (listés dans le header BlocksConfig) | header officiel BlocksConfig |
| Masse affichée | blocs de coque : ×0.125 en petite grille (HV/SV), ×8 en grande grille (BA/CV) | header officiel BlocksConfig |
| Chargement des configs | blocs → items → matériaux ; un fichier `BlocksConfig.ecf` de scénario REMPLACE entièrement celui de la base (les entrées manquantes font perdre les blocs aux POIs qui les référencent) | messages de chargement |

## Plafonds non déterminés (à documenter plus tard)

- Nombre max de playfields, de secteurs et de systèmes : aucune borne explicite
  ; les scénarios de la communauté en
  comptent des milliers (RE2-ATL-PRO : 1615 playfields chargés, vérifié).
- Coordonnées des secteurs : plage utile observée ±1000 dans les scénarios
  existants, sans borne explicite.
- Taille maximale d'une structure éditable : non rencontrée dans le code de
  chargement (limite éventuellement côté éditeur de blueprint, pas au
  chargement de scénario).

## WRN du log client sans action (verifies 29-30/10/2026)

- « Too many templates (in group?) — describing/updating only the first 15 » :
  garde-fou d'affichage du constructeur — quand un ingredient est utilise
  dans plus de 15 recettes, seules les 15 premieres sont decrites/mises a
  jour dans l'UI. Present aussi sur RE2 beta (SteelPlate y est dans 241
  recettes) ; amplifie sur ATL par le nombre de recettes autogenerees
  (4477 sorties de templates vs 953 chez RE2). Aucun groupe de sortie ne
  depasse 15 ; rien a corriger dans les fichiers.
- « PDA: Missing Name parameter in action 'CAA_PoiDiscovered_T:-_N:...' » :
  evaluation des chapitres tutoriels herites de RE2 (Visibility: Never,
  eden_pda_*) dont les activations PoiDiscovered ciblent des POI absents
  du playfield visite. Sans effet de jeu (la popup ne part simplement
  pas). Correctif applique le 30/10 : GuidingDistance: -1 (idiome
  vanilla) ajoute aux 3 activations sans guidage (Eden_AsteroidIceT3,
  Eden_AsteroidRichT1, Eden_HarvestVoidiumT1) + synchro production —
  a confirmer par le prochain log ; sinon rester sans action.
- « Item unlock level of higher tier <= lower tier: FieldRepairStation » :
  incoherence d'UnlockLevel heritee de la base, sans effet de jeu
  (l'item reste craftable) ; connue, non corrigee volontairement.
- « IdMapping: no name for id ARE_... » : blocs du mod ARE dans un prefab
  RE2 (POISeigeBrakerMK1RE) — non corrigeable hors retrait du prefab.


---
*Vérifié sur Empyrion v1.19.6 (build 5188), octobre 2026. Règles formulées
d'après le chargement réel du jeu et les fichiers de configuration officiels
livrés avec celui-ci.*

## Controle avant lancement (obligatoire apres toute edition ECF)

`python tools/ecf_lint.py <scenario>/Content/Configuration` → **0 erreur** avant
de lancer le jeu. Deux crashs vecus le 12/11 venaient de la :
`Material` inconnu du scenario (`metalweapon`, materiau vanille) et blocs
`+LootGroup` ecrits dans `Containers.ecf` (ce fichier n'admet que
`Container`). Dans les deux cas : `Exception`/`IndexOutOfRangeException` dans
`EcfFile.ParseLines`, playfield abandonne, `NullReferenceException` dans
`DeployPciture`, **crash** — et le parseur Python du projet ne voit rien.

## Bilan avant lancement : les avertissements, classés (12/11/2026)

`python tools/prelaunch_check.py <scenario> --all` → **0 erreur**, 71
avertissements en dev (72 en prod : +1 départ non validé). Parti de 166.

| # | Famille | Avant | Après | Reste | Pourquoi |
|---|---|---|---|---|---|
| A | `spawn` W311 (zones inertes) | 70 | 70 | 70 | **Neutralisation ANNULÉE** : commenter les items orphelins a avalé des en-têtes `SpawnZones:` dans 19 playfields -> « Property 'BiomesExcluded' not found on type 'SpawnRateZoneData' » + playfield refusé + **crash au chargement des planètes**. Fichiers restaurés depuis backup. Contrôle ajouté (`scan_spawnzone_schema`). À reprendre via l'éditeur de playfields, en supprimant le bloc (jamais en commentant une ligne d'en-tête). |
| B | `playfields` Compound | 37 | 0 | 0 | 5 sous-descripteurs `IsCompoundSubDesc` recopiés depuis un playfield sain (3 fichiers), `CompoundZiraxSentryT1` retiré des 2 `TestOrbit*` (aucune déclaration nulle part). |
| C | `prefabs` IdMapping | 30 | 30 | 30 | 139 noms manquants : 32 décoratifs **substitués** (1 580 prefabs, 5 707 mappings, cellules intactes) ; restent 107 blocs **fonctionnels** (boucliers, CPU, téléporteurs, minerais, leurres) : les substituer changerait le jeu, et 134 n'ont aucune définition source (94 mod externe, 44 DLC). |
| D | `poi_groups` | 15 | 12 | 12 | 3 groupes pointés vers un prefab existant (`R2TraderAuxT2`→`EPH_R2TraderAuxT1`, `CivilSettlementO2`→`BA_CivilSettlementO`, `R2KrielDroneBase`→`Eden_BA_KrielDroneBase`). Les 12 autres n'ont **aucun prefab nulle part** (ni scénario, ni quarantaine, ni vanille). |
| E | `values` | 5 | 0 | 0 | `IsScavenger: True` → `100` (forme numérique, la seule utilisée par la vanille). |
| F | `dialogues` | 7 | 0 | 0 | 3 cibles corrigées (`Eden_Telepad_Deny`, `Eden_PurgStartPod2_Log3`, `Eden_ExpeditionGeneral_Deny`) + 4 états écrits pour le marchand de colis (`Eden_MissionSmugglerNPCGive/Take_Greet|Deny`) avec 6 lignes de localisation EN/FR. |
| G | `engine` (arbre techno) | 2 | 1 | 1 | `ContainerAmmoSmall` remis au niveau 3 ; `FieldRepairStation` reste (incohérence vanilla assumée). |

Reste **71 avertissements**, dont **65 réellement corrigeables** (28 A + 30 C +
12 D moins recouvrements) mais tous bloqués par la même cause : des sources
absentes (DLC/mod) ou une chirurgie qui demande l'éditeur de playfields.

## Materiau d'entite inexistant : silencieux, et la resistance aux degats tombe au defaut

- **Symptome** : une creature encaisse (ou non) comme les autres, sans que son
  `Material:` ne corresponde a quoi que ce soit. Aucune ligne au log du client.
- **Cause** : `EClassConfig.ecf` accepte n'importe quelle chaine dans
  `Material:`. Si le nom n'est declare nulle part dans le `MaterialConfig.ecf`
  du scenario, le moteur ne trouve aucune definition et retombe sur un
  comportement par defaut. La vanille n'utilise que **2** materiaux dans son
  EClassConfig, tous declares.
- **Cas vecu (12/11)** : 131 entites de RE2-FR portaient 9 materiaux absents
  des 49 du scenario (`Mechanical`, `CreatureHard`, `CreatureSoft`,
  `DronePlanet`, `DroneSpace`, `HumanHard`, `HumanSoft`, `Ore`, `Player`).
  Consequence concrete : la correction v1.20 « les shotguns font a nouveau des
  degats contre les Turret Robots / Mechanoids / Androids » passe par le
  materiau de ces 3 entites — elle ne nous atteint pas, nos versions portant
  `Mechanical`.
- **Correctif** : declarer les materiaux dans `MaterialConfig.ecf` (copie d'une
  definition existante : `damage_category`, `surface_category`,
  `particle_category`, `stepsound`), ou pointer une entite sur un materiau
  declare (`metal`).
- **Applique le 12/11** : `metal` et `metalhard` copies tels quels de la base
  dans notre `MaterialConfig` (nos 49 materiaux ne les contenaient pas), puis
  report des 131 entites — `Mechanical`/`DronePlanet`/`DroneSpace`/
  `CreatureSoft` -> `metal`, `CreatureHard` -> `metalhard`,
  `HumanHard`/`HumanSoft`/`Player` -> `Human`, `Ore` -> `stone`. Bilan apres :
  111 avertissements (le notre a disparu), 0 erreur. Sauvegarde :
  `C:/Dev/_backup_prefabs_color/2026-11-12_materiaux/`.
- **Controle** : `scan_entity_materials` (`core/config_hygiene.py`) ->
  avertissement au bilan avant lancement, un par famille de materiaux.

## NRE a la creation de partie : deux playfields SPATIAUX dans un meme secteur

- **Symptome** : creation de partie impossible. Log client, sans aucun message
  prealable dans certains cas :
  `NullReferenceException at PackageSite.IncreaseStub <- FindDisk`.
- **Cause (prouvee par bissection, 13/11)** : un secteur ne peut porter
  QU'UN playfield spatial (corpus vanille : 0 secteur sur 360 en a deux). La
  reintegration des orphelins avait ajoute `Lava_Orbit` et
  `LavaCollided2_Orbit` dans un secteur qui avait deja son orbite -> le
  moteur cree un POI sans donnees de playfield et casse la creation de
  partie. **Systematique** ; le point d'apparition dans le log varie avec la
  graine, ce qui a fait perdre quatre essais (les `No BP group` et les
  `RadialInfo` observes n'etaient que des voisins d'ordre d'instanciation).
- **Preuve** : vanille + 4 secteurs ajoutes (aucun secteur double) = demarre ;
  vanille + le seul bloc fautif = crash ; vanille + ces 103 ajouts avec les
  doublons repares (9 playfields spatiaux deplaces dans leur propre secteur)
  = a valider en jeu.
- **Correctif** : `_host_sectors` (`core/playfield_reintegrate.py`) ecarte
  desormais un secteur hote qui porte deja un playfield spatial ; a defaut
  d'hote libre, l'orbite prend son propre secteur.
- **Controle** : `scan_sector_double_space` (`core/config_hygiene.py`) ->
  avertissement au bilan. Mesure : vanille 0, Frontier-FR 0 apres
  reparation, RE2-FR 23 (`SpaceWarpTargetFixed` + orbite, se lance) d'ou un
  avertissement et non une erreur.

## Cle `GroupName:` orpheline dans un `space_dynamic.yaml`

- **Symptome** : meme NRE, precede de `Blueprint group 'X' not found or
  empty!`.
- **Cause** : bloc de POI a moitie commente (`- Type:` en commentaire,
  `GroupName:` reste actif) -> POI sans type ni prefab. Vecu :
  `SpaceTradingStationStarter` / `JunkYardSpace`.
- **Correctif** : commenter la cle (fait, `.bak_20261114`).
- **Controle** : `scan_space_poi_groups` (erreur au bilan ; vanille 2 cas,
  RE2-FR 0).

## Reintegration de playfields orphelins : playfields poses dans les secteurs de warp

- **Symptome** : aucun crash isole a ce jour ; composition hors corpus.
- **Cause** : `_host_sectors` (`core/playfield_reintegrate.py`) acceptait un
  secteur `SpaceWarpTarget` comme hote pour une lune ou une orbite. Le corpus
  vanilla n'y met **qu'une** entree (0 secteur sur 360), la reintegration en
  a compose 26 (lune/orbite au meme offset que la porte).
- **Correctif** : un secteur contenant un `SpaceWarpTarget` n'est plus jamais
  hote ; un playfield d'instance (`Instance:`) n'est plus propose du tout.
  **Non prouve** comme cause de crash (RE2-FR porte 59 compositions analogues
  et se lance) : garde par prudence, pas par certitude.
- **Controle** : `scan_sector_composition` (`core/config_hygiene.py`) ->
  avertissement au bilan avant lancement.

## `Sectors.yaml` sans en-tete : le jeu refuse de lancer (crash a la selection)

- **Symptome** : le scenario ne se charge meme pas ; dans le log client,
  `YamlDotNet ... Property 'Name' not found on type
  ...StubTreeRegistryCollection` puis `No sectors specified`.
- **Cause** : le fichier a perdu ses premieres lignes (`GalaxyMode:`,
  `Sectors: []`, `SolarSystems:`). Le YAML reste valide — c'est une
  propriete attendue qui manque a la deserialisation. Vecu 13/11 : une
  reecriture automatique du fichier (reconstruction systeme par systeme)
  avait laisse le fichier commencer directement sur `  - Name: Ellyon`.
- **Correctif** : restaurer l'en-tete (7 lignes de la vanille).
- **Controle** : `scan_sectors_header` (`core/config_hygiene.py`) -> erreur.
  `yamlcheck` ne le voit PAS (YAML valide) : c'est bien un controle a part.


## Systeme avec soleil sans secteur SpaceWarpTarget : crash au warp (obligation de quitter)

- **Symptome** : le jeu se lance, la partie demarre ; au warp VERS le
  systeme, `Loading playfield '<Systeme> [Sun Right]'`,
  `-ERR- Sector for playfield '<Systeme> [Sun Right]' not found`,
  `DirectoryNotFoundException` sur le playfield_debug.yaml inexistant, puis
  `ArgumentNullException: Value cannot be null. Parameter name: key` en
  boucle a chaque frame (1520x) — le client est bloque, il faut quitter.
- **Cause** : les systemes au format EVO ont chacun 6 secteurs d'arrivee
  autour du soleil (`<Systeme> [Sun Right/Left/Top/Bottom/Front/Back]`,
  playfield type `SpaceWarpTarget`) : le routeur warp vise ces secteurs
  comme porte d'entree du systeme. Un systeme cree par conversion du
  format legacy (scenarios officiels anciens : liste plate `Sectors:`,
  warp direct entre orbites par listes `Allow`) n'en a pas — vecu 15/11
  avec l'integration de Shadows of Starlight dans Frontier-FR.
- **Correctif** : ajouter les 6 secteurs SpaceWarpTarget autour du soleil
  (coordonnees `[4,0,0]` / `[-4,0,0]` / `[0,4,0]` / `[0,-4,0]` /
  `[0,0,4]` / `[0,0,-4]`, `SectorMapType: None`, playfield type
  `SpaceWarpTarget` — dossier present en vanille). Exception legitime : les
  systemes d'instance (marque `# INSTANCE`, atteints par teleport PDA).
- **Controle** : `scan_sun_warp_targets` (`core/config_hygiene.py`) ->
  erreur au bilan avant lancement (exclut les systemes d'instance et le
  style flow ancien). Tests : `test_system_without_warp_targets_is_an_error`,
  `test_system_with_warp_targets_and_instance_are_clean`.

## Cle `Probability` dans les POIs d'un playfield_static : scenario impossible a selectionner

- **Symptome** : crash/erreur des l'ajout du scenario dans le menu (avant
  la creation de partie) ; log client : `YamlDotNet ... Property
  'Probability' not found on type 'PoiData+RandomPoiData'` puis `Issue
  with deserializing playfield data!` + `NullReferenceException`.
- **Cause** : `Probability` n'existe pas sur PoiData.RandomPoiData ni
  FixedPoiData (deobfusque 1.20.1 PoiData.cs : seul `SpaceDefenseProbability`
  existe). La vanille n'a AUCUN `Probability` dans ses playfield_static.yaml
  (verifie : 0) — les POIs statiques spawneront toujours sans cette cle.
  Les POIs SPATIAUX (`space_dynamic.yaml`, autre classe de donnees) l'admettent
  — d'ou la confusion possible. Vecu 15/11 : 96 statics avec des POIs ajoutes
  portant `Probability: 1` (les POIs legacy `playfield.yaml` sont couverts par
  `scan_poi_keys` qui flaggait deja cette cle).
- **Correctif** : supprimer les lignes `Probability:` des sections POIs des
  playfield_static.yaml (garantir la presence par `CountMinMax: [n,n]`).
- **Controle** : `scan_static_probability` (`core/config_hygiene.py`) ->
  erreur. Tests : `test_static_probability_is_an_error`,
  `test_static_without_probability_is_clean`.

## Variable C# non declaree dans une fonction dialogue generee : etat non compilable + spam « Cannot process 'DialogOption' »
- **Symptome** : le bouton de vente du container « VENTE » ne vend rien,
  aucun message d'erreur en jeu ; le log client se remplit de
  `error CS0103: The name 'vendus' does not exist in the current context`
  + `Error compiling dialogue logic in state 'Frontier_TraderHub2'`, puis
  324 `Cannot process 'DialogOption' event for action 'CAA_DialogOption_...'`
  (evenements PDA en attente rejetes tant que le script est casse).
- **Cause** : la fonction C# generee (`Functions:` d'un noeud Dialogue)
  incrementait `vendus` et `total` sans les declarer. Le compilateur
  dialogue du jeu rejette l'etat ENTIer : non seulement la fonction est
  morte, mais tout evenement DialogOption en attente du PDA est rejete en
  boucle. Aucun retour au joueur.
- **Correctif** : declarer les compteurs au debut de la fonction generee
  (`int vendus = 0;` / `int total = 0;`, un statement par ligne `<nl>`)
  dans `core/console_traders.py`, regenerer (mode fusion) et deployer prod.
- **Controle** : `scan_dialogue_vars` (`core/config_hygiene.py`) -> erreur
  (toute variable auto-referencee `X = X ...` doit etre declaree dans le
  bloc `Functions:` ou en `Variable_N:` du noeud). Test :
  `test_dialogue_var_undeclared_is_an_error`.

## Items d'un scenario : ids d'inventaire remappes +8192 au runtime
- **Symptome** : un matching par Id entre `GetContent()`/inventaire et les
  ids de l'ItemsConfig du scenario ne matche jamais (vente container :
  201 prix connus, 0 stack vendu). Traces : stack id=8416 pour
  IronIngot declare Id: 224 (ecart +8192 constant sur 4 stacks).
- **Cause** : le moteur remappe les ids d'inventaire des items declares
  dans l'ItemsConfig d'un scenario : id runtime = id config + 8192. Meme
  les ids vanille redeclares (IronIngot 224) sont remappes. Verifie en jeu
  16/11 (4/4 stacks, log 5232).
- **Correctif** : dans le C# genere, lookup double
  `TryGetValue(item.id, out p) || TryGetValue(item.id - 8192, out p)`
  avec `int p;` declare avant (`out int p` deux fois dans le meme if =
  CS0136). Les acces par NOM (AddItem/RemoveItem) ne sont pas concernes.
- **Controle** : pas de scan possible (comportement moteur, pas de donnee
  fautive) — le lookup double est dans le generateur
  (`core/console_traders.py`, Frontier_VendreContainer) ; fiche cerveau
  `items-scenario-ids-runtime-plus-8192`.

## Transfert d'items par (id, quantite) : le `meta` de pile est perdu
- **Symptome** : deplacer des stacks entre containers avec
  `IContainer.AddItems(int type, int count)` / `RemoveItems` — la
  signature n'a AUCUN parametre meta : la pile arrive avec meta = 0.
- **Cause** : `AddItems` fabrique une pile neuve a partir de (id, qte) ;
  seul `SetContent(List<ItemStack>)` transporte des piles completes
  (type `ItemStack` efface par la deobfuscation : champs non listables).
- **Ce que ce n'est PAS** : le tier/rarete d'une arme (T1, T2, Epic...)
  n'est pas un meta — ce sont des ITEMS DISTINCTS (ids distincts :
  RocketLauncherT2 = 33, RocketLauncherEpic = 34), donc le tier SUIT
  l'id et survit au transfert. Verifie sur Frontier-FR : aucun champ
  Quality/Meta dans l'ItemsConfig, et les dialogues vanille n'utilisent
  `meta` que pour `Token` (jetons, variantes). `Token` (Id 1305, ni
  Category ni Ref) n'est pas route par le tri.
- **Decision 16/11** : router les armes est donc sans risque de tier ;
  le seul item a meta du scenario (Token) reste hors routes. Si un item
  a variantes devait entrer dans le tri, passer par `SetContent`
  (piles completes) avec relecture de verification.
- **Controle** : pas de scan possible (comportement moteur) ; a
  revalider en jeu si un item a meta entre dans le tri.

## CallLater : les variables de dialogue (AddToGlobalPfVar) echouent hors etat
- **Symptome** : une fonction dialogue relancee par `CallLater(f, delai)`
  s'execute bien (les traces sortent, l'ecran se met a jour) mais toute
  ecriture de variable de dialogue echoue :
  `SQLiteException ... NOT NULL constraint failed: DialogueVars.state`,
  avec `1=Frontier_Lcd_Idx`, `3=` (state vide). L'effet visible : la
  valeur ne progresse pas (ecran bloque en page 1, log repete).
- **Cause** : `CallLater` execute le callback HORS de tout etat de
  dialogue ; le compilateur n'a pas de `state` courant a passer a
  l'INSERT dans `DialogueVars`, et la colonne est NOT NULL. Les acces a
  la structure (GetAllCustomDeviceNames, GetDevice, SetText) restent
  valides — seule la base de variables casse.
- **Correctif** : pour l'etat ephemeres d'une boucle d'animation, utiliser
  des champs `static` de la classe generee (`static int Frontier_Idx`)
  au lieu de `AddToGlobalVar`/`AddToGlobalPfVar`. Les vars de dialogue
  restent bonnes pour la persistance (prefixe de tri), lues et ecrites
  depuis un etat.
- **Controle** : `tests/test_console_apps.py` verifie l'absence de
  `GlobalPfVar` dans l'arbre genere et la presence des champs `static`.
  Vecu 16/11 (log 185524).
- **2e forme (vecu 18/11)** : `Frontier_Approvisionner` commencait par
  `AddToGlobalVar('Frontier_Tri_Pref', '')` — la meme API echoue hors
  etat : la fonction mourait a sa PREMIERE ligne, donc l'appro
  automatique (CallLater 5 min) ne faisait jamais rien, en silence
  (seule la premiere passe, lancee depuis l'option, marchait). Correctif :
  lire le miroir `static string Frontier_Pref`, charge a l'entree du hub
  par `Frontier_ChargePref()` (`Execute:` du state). Regle generale : TOUT
  code atteignable depuis un CallLater doit eviter les API d'etat.

## Parseur ECF : `Name: (\w+)` casse les noms a point et avale les commentaires
- **Symptome** : des items restent sans nom dans l'interface (id seul) et
  disparaissent silencieusement du catalogue des traders ; un item comme
  `5.8mmBullet` (ou `12.7mmBullet`, `8.3mmBullet`) n'est jamais reconnu.
- **Cause** : dans une declaration `{ +Item Id: 54, Name: 5.8mmBullet,
  Ref: 50Caliber`, un motif `(\w+)` s'arrete au point et capture `5` ;
  l'item est alors inconnu du mapping (donc non classe, non nomme, non
  vendu). Symetriquement, `Name: AssaultRifle    # T1` livre le nom suivi
  du commentaire si le motif l'accepte tel quel.
- **Correctif** : motif commun `ITEM_NAME = r'([^\s,#]+)'`
  (`core/console_traders.py`, importe par `core/console_apps.py`) : coupe
  a l'espace, a la virgule et au commentaire, garde les points.
- **Controle** : `test_noms_a_point_et_commentaires`
  (`tests/test_console_apps.py`). Vecu 17/11 : +532 noeuds de dialogue
  traders recuperes, `skipped` 100 -> 68.

## Chemins d'assets dans un dialogue : %SHARED_DATA% est le seul relatif au scenario
- **Symptome** : une page HTML (ou une image) livree avec le scenario ne
  s'affiche pas dans le panneau `OpenHtmlWindow` ; en Workshop elle est
  absente chez les joueurs.
- **Cause** : `%CONTENT_DIR%` pointe le dossier `Content` du **jeu**
  (verifie : `Content/Extras/Assets/Akua_7.jpg` existe la-bas, pas dans
  le scenario), donc tout ce qu'on y met n'est PAS livre avec le
  scenario. `%SHARED_DATA%` pointe `<scenario>/SharedData` (usage de
  RE2-FR pour ses images).
- **Correctif** : placer les assets du scenario dans
  `Content/Scenarios/<nom>/SharedData/` et les referencer par
  `%SHARED_DATA%/fichier.html`. `core.console_apps.regen_apps` y genere
  `Console_Aide.html`, ouvert par l'option AIDE de la console.
- **Controle** : `test_aide_html_generee` verifie le fichier, la presence
  de `%SHARED_DATA%` dans le dialogue et l'absence d'asset externe.

## Functions: ne contient que des DECLARATIONS ; declencheur = Execute:
- **Symptome** : un Functions portant un APPEL nu (`OpenHtmlWindow(...)`)
  casse la compilation de TOUTE la classe de l'arbre : `CS1520 Method must
  have a return type` + `CS0501 'Dialogue<Arbre>(?, ?, ?, ?, ?, ?)' must
  declare a body` — console vide a l'ouverture, figage au F (le moteur
  recompile en boucle : « trying to compile again »). Vecu 17/11 (log
  034353).
- **Cause** : les valeurs Functions sont emises telles quelles au niveau
  CLASSE : elles doivent declarer des membres (`void F() { ... }`). Un
  appel doit etre declare en fonction puis declenche par le champ
  `Execute:` du state (code lance a l'ENTREE du state — usage vanilla :
  DF_Campaign_Helper).
- **Correctif** : `Functions: "void F() {<nl>  Appel(...);<nl>}"` +
  `Execute: "F();"`.
- **Controle** : `scan_dialogue_functions` -> erreur prelaunch (bare_call).

## Dictionary C# : un bloc et un item peuvent partager le meme numero d'id
- **Symptome** : `ArgumentException: An item with the same key has already
  been added. Key: 600` a l'execution de Frontier_VendreContainer — la
  vente du container ne fait rien (l'exception tue la fonction).
- **Cause** : le dictionnaire des prix melange ids ItemsConfig et
  BlocksConfig : `600` existe des deux cotes -> l'initialiseur de
  Dictionary (semantique Add) refuse le doublon.
- **Correctif** : dedoublonner par id a la generation (meilleur prix
  conserve) ; pareil pour tout dictionnaire id->x issu des deux configs.
- **Controle** : `scan_dialogue_functions` (dup_key) -> erreur prelaunch.

## Litteraux char interdits dans le C# dialogue : apostrophes -> guillemets
- **Symptome** : `CS0019: Operator '<' cannot be applied to operands of
  type 'char' and 'string'` sur `ch < '0'`.
- **Cause** : le preprocesseur convertit TOUTES les apostrophes du champ
  en guillemets : `'0'` devient `"0"` (string). Les litteraux char
  n'existent donc pas dans le code dialogue.
- **Correctif** : comparer via une chaine (`"0123456789".IndexOf(ch) < 0`).

## Guillemet dans une valeur ECF : « ECF reading aborted », tout le reste est perdu
- **Symptome** : `ECF config line 23312 is malformed -- ECF reading
  aborted!` puis, en cascade, `Dialogue start state 'Frontier_AppAtelier'
  not found`, `'Frontier_TraderHub2' not found` : les consoles s'ouvrent
  VIDES, alors que les etats existent bien dans le fichier. Aucune erreur
  de compilation C# n'apparait (le parseur ECF n'est jamais alle si loin).
- **Cause** : la valeur `Functions: "..."` est delimitee par des
  guillemets ; y ecrire un guillemet (ex. `"0123456789"`) en ajoute deux
  et la ligne devient malformee. La lecture du fichier s'ARRETE la : tout
  ce qui suit (dont tous nos noeuds, places en fin de fichier) n'existe
  pas pour le jeu. Vecu 17/11 (log 045650) : un correctif C# (test de
  chiffres) ecrit avec des guillemets au lieu d'apostrophes.
- **Correctif** : dans une valeur ECF, toute chaine C# s'ecrit avec des
  APOSTROPHES (`'0123456789'`) — le preprocesseur les convertit en
  guillemets a la compilation. Regle a appliquer aux generateurs.
- **Controle** : `scan_dialogue_functions` (type `quotes`) -> erreur
  prelaunch si une ligne `Functions:` ne porte pas exactement 2
  guillemets. Test : `test_dialogue_functions_bare_call_et_dup_key`.

## Une option dont le noeud cible n'est pas charge est MASQUEE
- **Symptome** : une option ajoutee dans un menu n'apparait pas du tout
  en jeu, alors que la ligne `Option_N:` est bien dans le fichier.
- **Cause** : si le `OptionNext_N` pointe vers un etat inexistant (non
  charge, ou supprime), le moteur omet silencieusement l'option au lieu
  de l'afficher inerte. Vecu 17/11 : l'aide de la console commerce
  pointait vers un noeud place APRES la ligne qui cassait la lecture ECF.
- **Correctif** : verifier que les etats cibles existent apres toute
  regeneration (le prelaunch voit maintenant les lignes malformees, qui
  sont la cause habituelle).

## RemoveItems ne retire RIEN sur les containers de dialogue : utiliser SetContent
- **Symptome** : `AddItems` ajoute bien (l'objet apparait dans la
  destination) mais `RemoveItems(type, n)` ne retire rien, quel que soit
  l'id fourni (id, id-8192, id+8192) — duplication. Vecu 17/11 : tri des
  coffres `TRI` et vente du container `VENTE`, log `deplaces=0` alors que
  les destinations se remplissaient.
- **Cause** : `RemoveItems` boucle sur les slots et compare
  `slot.RemoveSymbol()` a l'entier fourni ; cette comparaison ne correspond
  pas a l'id expose par `GetContent()` sur ces containers, et l'echec est
  totalement silencieux (aucune exception, aucun retour d'erreur).
- **Correctif** : **ne pas utiliser RemoveItems**. `IContainer.SetContent`
  est deterministe : `GetContent()` renvoie des piles portant leur
  `slotIdx` ; on reconstruit la liste avec les quantites reduites (ou la
  pile omise si elle tombe a 0) et on la repasse a `SetContent`, qui
  reinstalle chaque pile dans son slot. Utilise par le tri,
  l'approvisionnement et la vente (`core/console_apps.py`,
  `core/console_traders.py`).
- **Controle** : les tests verifient la presence de
  `c.SetContent(neuf)` / `List<ItemStack>` et l'absence de retrait par
  `RemoveItems` dans les arbres generes.

## (historique) RemoveItems n'est PAS symetrique de AddItems
- **Symptome** : un tri/vente « fonctionne » — les items apparaissent bien
  dans la destination ou le credit monte — mais ils restent AUSSI dans la
  source : **duplication**. Vecu 17/11 (tri des coffres TRI).
- **Cause** : `AddItems(int type, int count)` fabrique un item par type-id
  (`new OptionsSerializer(type)`), tandis que `RemoveItems(int itemType,
  int count)` boucle sur les piles et compare `pile.RemoveSymbol()` a
  l'entier fourni. Les deux ne designent pas le meme identifiant : l'id
  d'inventaire (runtime) differe de l'id de config (+8192). Le retrait ne
  trouve aucune pile, ne retire rien, et ne signale rien.
- **Correctif** : ne jamais supposer qu'un retrait a eu lieu. Utiliser un
  retrait MESURE (`Frontier_Retirer`) : compter avant, appeler
  `RemoveItems`, recompter, retenter avec `id - 8192` puis `id + 8192` si
  la quantite n'a pas baisse, et retourner le delta reel. Cote appelant,
  ne crediter/afficher que le delta, et **annuler l'ajout** en destination
  s'il est superieur au delta (sinon duplication).
- **Controle** : pas de scan possible (comportement moteur) ; helper present
  dans les deux arbres (atelier : tri + appro ; commerçants : vente du
  container) et verifie par les tests de generation.

## Menu de dialogue : la numerotation des options doit etre CONTIGUE
- **Symptome** : une option ajoutee ne s'affiche jamais en jeu, alors que
  la ligne `Option_N:` et son `OptionNext_N` sont bien presentes et que
  l'etat cible existe. Vecu 17/11 : le hub commercant numerotait 1, 2, 8
  (AIDE), 9 (Quitter) ; l'aide n'apparaissait pas.
- **Cause** : le moteur parcourt les options dans l'ordre et s'arrete au
  premier numero manquant — memes les options d'avant le trou restent
  affichees, ce qui masque la cause.
- **Correctif** : numeroter 1, 2, 3, ... sans trou (`console_traders`
  utilise un compteur `hub_opt`).

## Output de dialogue : interpolation C#, donc pas d'apostrophe dans {…}
- **Symptome** : les deux consoles s'ouvrent VIDES (aucun texte), log
  `CS1012: Too many characters in character literal` en rafale, puis
  `Error compiling dialogue logic in state 'Frontier_AppAtelier'`.
- **Cause** : chaque `Output:` est emis en `return $"<texte>";` (voir
  DialogueSystem : `stringBuilder4.Append("  return $\"" + ...)`), **sans**
  passer par la conversion apostrophe -> guillemet appliquee aux
  `Functions:` (parseCode). Ecrire une expression a apostrophes dans une
  interpolation, ex. `{AddToGlobalVar('X', 0)}`, forme un LITTERAL
  CARACTERE multi-caracteres -> CS1012, et l'arbre entier est perdu.
  Vecu 17/11.
- **Correctif** : ne mettre dans `{...}` que des valeurs simples (variable,
  propriete comme `Player.Credit`, ou APPEL DE FONCTION sans argument :
  `{Frontier_Dispo()}`). Toute chaine C# doit rester dans `Functions:`.
- **Controle** : `scan_dialogue_functions` (type `output_char`) -> erreur
  prelaunch si une interpolation d'Output contient une apostrophe.

## Boucle foreach : la variable d'iteration n'est pas modifiable (CS1654)
- **Symptome** : `CS1654: Cannot modify members of 'st' because it is a
  'foreach iteration variable'`, arbre mort.
- **Cause** : `foreach (var st in c.GetContent()) { st.count = ...; }` —
  en C#, l'element d'iteration est en lecture seule (struct copie).
- **Correctif** : copier d'abord (`var st = st0;`) puis modifier la copie
  et l'ajouter a la nouvelle liste. Vecu 17/11 dans le retrait par
  SetContent.

## Variable declaree deux fois dans un MEME arbre : CS0102, console vide
- **Symptome** : la console s'ouvre VIDE (aucun texte, aucune option),
  sans autre message en jeu ; log : `CS0102: The type
  'Dialogue<Arbre>' already contains a definition for '<Variable>'` puis
  des `CS0229: Ambiguity between ...`.
- **Cause** : le compilateur fusionne les `Variable_N` de TOUS les etats
  d'un arbre dans une seule classe. Declarer la meme variable dans deux
  etats du meme arbre (ici `Frontier_DV2` dans le hub T2 et dans le noeud
  du container VENTE) rend la classe non compilable. Deux arbres
  DIFFERENTS (T1 et T2) peuvent legitimement reutiliser un nom. Vecu
  17/11, 2e forme : un CHAMP C# du bloc Functions declare deux fois
  (`static bool Frontier_AutoOn` puis `bool Frontier_AutoOn`), meme
  sanction CS0102.
- **Correctif** : declarer la variable dans UN seul etat ; la fusion la
  rend visible partout dans l'arbre. Pour les champs C# du Functions :
  un seul emplacement de declaration dans la chaine generee.
- **Controle** : `scan_dialogue_dup_vars` -> erreur prelaunch (parcours
  des arbres depuis les `DialogueState` des blocs Frontier_*) pour les
  `Variable_N` ; pour les champs C# :
  `test_classe_functions_compile_membres_uniques` (membres de niveau 0
  du bloc Functions declares exactement une fois). Test ECF :
  `test_dialogue_dup_var_intra_arbre`.
- **Piege du controle** : les regex ancrees sur `\n` echouent sur un
  fichier CRLF (read_bytes ne normalise pas) — normaliser avant de parser.

## Le RETOUR de AddItems est le RESTANT (0 = tout est entre), pas l'ajoute
- **Symptome** : le tri « envoie » bien les objets dans les coffres de
  destination, mais `mv=0` dans les traces et rien n'est retiré de la
  source — duplication. Vecu 17/11 (log 104018 :
  `APP-TRI: ajout id=266 vers TRI_Minerais_A mv=0/1000` alors que l'objet
  arrivait bien).
- **Cause DEMONTREE (deobfuscation 17/11)** : `int AddItems(type, count)`
  appelle `PrintProcess` : le compteur interne part de `count` et est
  DECREMENTE a chaque item empile ; la valeur retournee est ce RESTANT.
  Retour 0 = tout est entre ; retour N = N items non acceptes. Preuves
  croisees : moteur (PrintProcess/OrderVector), tests officiels
  EmpyrionScripting (`boxA.n(1,1).Returns(0)`, `boxB.n(1,10).Returns(1)`),
  et le tri officiel ConveyorHelpers (`count = target.AddItems(...)`,
  `count > 0` = re-empiler pour plus tard).
- **Correctif** : `Frontier_Deposer` (console_apps) : AddItems puis
  mesure REELLE par difference de stock (`Frontier_Stock` avant/apres),
  independante de la semantique du retour.
- **Controle** : test verifiant `int mv = Frontier_Deposer(dst, lot.id,
  restant);` dans l'arbre atelier (l'ancienne forme `int avd` + mesure
  inline a ete remplacee).

## Item et bloc peuvent partager le meme id : deux espaces de cles obligatoires
- **Symptome** : le tri classe des blocs dans la categorie d'ITEMS sans
  rapport — sieges passagers dans « Minerais », tourelles dans
  « Armes joueur ». Vecu 17/11.
- **Cause** : un item et un bloc portent souvent le MEME numero
  d'identification (669 collisions dans Frontier-FR : item 266 =
  minerai, bloc 266 = PassengerSeatMS). Un dictionnaire id -> categorie
  ne peut pas les distinguer : le bloc heritait de la categorie de
  l'item.
- **Distinction reelle** : au runtime un ITEM est remappe `+8192`, un
  BLOC garde son id. On utilise donc deux espaces de cles dans le meme
  dictionnaire : `id` pour les items, `100000 + id` pour les blocs, avec
  `Frontier_Cle(id) = id >= 8192 ? id - 8192 : id + 100000`. Toutes les
  comparaisons de piles (comptage, retrait) passent par cette cle, sinon
  un item et un bloc homonymes se comptent ensemble.
- **Controle** : `test_sous_categories_reelles` verifie les cles 100xxx.

## Apprentissage du tri : memoriser le NOM du coffre, pas la sous-categorie
- **Symptome** : un coffre cree par le joueur (`TRI_Armures_A`,
  `TRI_Carburant_A`, `TRI_Boost_A`) est IGNORE par l'option APPRENDRE :
  l'objet range a la main dedans, puis TRIER, repart au classement
  automatique (Divers / Composants / Medical). Vecu 17/11.
- **Cause** : l'apprentissage cherchait la sous-categorie dans le NOM du
  coffre (`for (i...) if (nd.StartsWith(pref + '_' + CATS[i])) idx = i;`
  puis `if (idx < 0) continue;`). Tout coffre hors des 15 categories
  figees etait saute en silence. Renommer ne suffit pas : deux objets
  voulus ensemble par le joueur tombent dans des categories differentes
  (ArmorLight -> Divers, EnergyCell -> Composants, BioFuel -> Divers).
- **Correctif** : la memoire stocke la DESTINATION PAR NOM de coffre
  (une seule variable `Frontier_Dest`, format `,id=NomCoffre,`) ; le tri
  essaie d'abord cette destination, puis retombe sur le classement
  automatique pour le reste. APPRENDRE parcourt tout container
  `<prefix>_*` et ne memorise que les ECARTS (ce que le classement auto
  enverrait deja dans CE coffre n'est pas grave).
  Effet de bord bienvenu : 15 variables `Frontier_M0..M14` -> 1, donc
  plus de risque de CS0102 sur ces declarations.
- **Controle** : `test_apprentissage_coffres_libres` (aucun filtre
  `CATS[i]` dans l'apprentissage, ordre `Frontier_Destin` avant
  `CATS[code3]`, format `,id=NomCoffre,`).
- **Limite connue** : le nom du coffre est stocke entre deux separateurs
  `,` et `=` ; un nom de coffre contenant une virgule ou un `=` casserait
  la lecture de cette entree.

## TechTreeNames inconnu : l'UI du CONSTRUCTEUR casse (SetLabel)
- **Symptome** : a chaque ouverture du constructeur, 2 lignes rouges
  `Could not find method 'SetLabel' on UIScrollablePopupList`. Aucun
  message en jeu, aucune consequence visible — mais le log se remplit.
- **Cause DEMONTREE (18/11)** : `TechTreeNames: "Commercants"` sur un
  bloc. Le constructeur parcourt les recettes et leurs onglets
  technologiques ; il ne connait que les valeurs du jeu (`Base`,
  `Capital Vessel`, `Small Vessel`, `Hover Vessel`, plus `Hidden` et
  `Schematics` utilises par RE2). Une valeur inventee le fait echouer sur
  la liste deroulante (`UIScrollablePopupList` n'a pas `SetLabel`).
- **Diagnostic** : le log n'indique pas l'action. Des traces horodatees
  `APP-TRACE:` dans les consoles ont permis de correler : les SetLabel
  suivaient les ouvertures du hub atelier... mais c'est en fait le
  CONSTRUCTEUR, ouvert juste apres, qui les produit.
- **Correctif** : utiliser un onglet existant (`TechTreeNames: "Base"`).
  Le bloc reste deblocable, il apparait simplement dans l'onglet Base.
- **A ne pas confondre** : `Hidden` et `Schematics` sont des valeurs
  SPECIALES du jeu (RE2 les utilise) — elles fonctionnent, contrairement
  a un nom libre.
- **Controle** : `scan_blocks_techtree_inconnu` -> avertissement prelaunch
  (liste des valeurs connues ; non bloquant, un onglet special du jeu
  peut legitimement apparaitre).

## Deux coffres de meme nom : un seul est vu par les dialogues
- **Symptome** : un coffre ne recoit jamais rien au tri, ou un
  approvisionnement ne remplit qu'un des deux coffres, sans erreur.
- **Cause** : Empyrion N'INTERDIT PAS deux containers portant le meme
  nom. Or nos consoles y accedent par NOM : `LocalStructure.
  GetDevice<IContainer>(nom)` rend UN device (le premier trouve, sans
  ordre garanti aux yeux du script). Le second bloc du meme nom est
  invisible pour le tri, l'appro et les ecrans lies.
- **Correctif** : noms uniques. Le generateur ne peut pas le detecter a
  l'avance (les noms vivent dans la sauvegarde, pas dans les configs) :
  c'est au joueur de veiller a l'unicite. Documente en tete des regles
  de l'aide atelier.
- **Controle** : `test_aide_atelier_complete` exige que l'aide cite ce
  piege, pour qu'il ne disparaisse pas d'une reecriture.

## Cout de compilation d'un arbre de dialogue : une methode PAR ITEM coute cher
- **Symptome** : plusieurs secondes de gel a la premiere ouverture d'une
  console d'un gros scenario, alors que les actions ensuite sont fluides.
- **Cause (mesuree)** : le moteur compile le C# de l'arbre au premier
  acces et le met en cache par NOM DE RACINE (`cachedCompiledScripts`,
  `DialogueSystem.cs:1080`). Le cout suit donc le VOLUME de code :
  6 020 blocs `Functions` = 643 Ko de C# pour 3 arbres, soit ~214 Ko par
  arbre. L'essentiel venait d'une methode `Frontier_Dispo<tag>_<s>_<i>()`
  generee par item (~2 000 par arbre) juste pour afficher un stock.
- **Correctif** : UNE fonction parametree `Frontier_Dispo(t, i, smax)`
  declaree dans le hub, appelee dans l'interpolation de l'Output
  (`{Frontier_Dispo(3, 739, 500)}`). Mesure apres : 215 blocs Functions,
  **96 Ko de C# (-85 %)**, compilation `csc` 0,47 s -> 0,22 s.
- **Autres limites du parseur** : `Execute_N` et `OptionExecute_N` sont
  TRONQUES a 150 caracteres (`DialogueSystem.cs:775`, avec log d'erreur) ;
  `Functions:` n'a aucune limite (parseur distinct).
- **SP/MP** : la compilation est par arbre et mise en cache pour la
  session, cote CLIENT. Le serveur ne compile rien ; chaque joueur paie
  une fois, au premier contact.
- **Regle** : ne jamais generer une methode par item/par marchand. Une
  fonction parametree + des arguments dans l'Output suffisent.

## Console VIDE : toujours une classe C# morte — la VERIFIER par compilation
- **Symptome** : la fenetre de dialogue s'ouvre sans texte ni option ;
  aucun message en jeu. Log client : `error CSxxxx` puis « Error
  compiling dialogue logic ». Vecu 17/11 (plusieurs sessions) : 15 ×
  CS0102 (`Frontier_M0..M14` declares dans le hub ET dans le noeud
  APPRENDRE — le compilateur fusionne les Variable_N de tous les etats
  d'un arbre) + 1 × CS0103 (`Frontier_Trouver` appelee par l'APPRO,
  disparue d'une reecriture).
- **Cause** : les scans regex de `config_hygiene` ne couvrent que les
  pieges CONNUS ; tout autre erreur C# (type, surcharge, ambiguite,
  membre absent) passe sans un mot et seule la fenetre vide le signale.
- **Correctif** : `Frontier_M*` declarees dans UN SEUL etat (le hub, qui
  lit la memoire ; APPRENDRE la reconstruit depuis les coffres) ;
  declarer toute fonction appelee.
- **CONTROLE (le vrai)** : `test_arbres_dialogue_compilent` compile le
  C# de chaque arbre avec `csc.exe` du .NET Framework et echoue sur
  toute erreur CS. Il rejoue le pre-processeur du jeu — `<nl>` -> saut
  de ligne, apostrophe -> guillemet (verifie : sans cette conversion les
  litteraux donnent CS1012) — fusionne les etats PAR ARBRE et type les
  variables selon `param1` (`dbplayer_int` -> int, sinon string ; sinon
  CS0029). Limite : csc du Framework est en C# 5, le `?.` du code
  traders est neutralise (le jeu compile en Roslyn).
- **Piege du controle regex (vecu le meme soir)** : `scan_dialogue_dup_vars`
  et `scan_dialogue_fonctions_manquantes` cherchaient la racine d'un
  arbre avec `Name: ...\n(?:.*?\n)?  DialogueState:` — UNE seule ligne
  intercalaire toleree. Le bloc de la console d'atelier en a TROIS
  (CustomIcon, Class, DialogueState) : ces deux scans etaient AVEUGLES a
  l'atelier et n'ont rien signale. Corrige par `_racines_dialogue()`
  (lecture de tout le corps du bloc). Lecon : un garde-fou muet doit
  etre teste sur un cas REEL, pas seulement sur son cas nominal.

## Fonction appelee mais non declaree dans l'arbre : CS0103, console vide
- **Symptome** : la console s'ouvre VIDE ; log `CS0103: The name
  'Frontier_Xxx' does not exist in the current context` puis
  `Error compiling dialogue logic in state '...'`. Vecu 17/11 (log
  110340) : `Frontier_Cle` utilisee par Frontier_Stock/Frontier_Retirer
  sans que sa declaration ait ete inseree.
- **Cause** : les Functions de tous les etats d'un arbre sont fusionnees
  en UNE classe ; une fonction appelee doit y etre declaree quelque part.
  Un patch du generateur qui n'insere que les appels produit ce cas, et
  rien ne le signale cote ECF. Vecu 17/11, 2e forme (le pire) : un CHAMP
  reference non declare — les dictionnaires `infosB..E` construits par le
  generateur Python mais jamais injectes dans la chaine C# : classe
  morte, PLUS RIEN de l'atelier ne marchait (tri, LCD, appro), sans
  erreur visible cote generateur car le code Python etait syntaxiquement
  sain.
- **Correctif** : declarer la fonction/le champ (n'importe quel etat de
  l'arbre) ; cote generateur, toute sous-chaine construite doit etre
  CONCATENEE dans la valeur finale — une variable Python non utilisee
  est un bug, pas du code mort inoffensif.
- **Controle** : `scan_dialogue_fonctions_manquantes` -> erreur prelaunch
  (parcours des arbres, declarations vs appels) ;
  `test_classe_functions_compile_membres_uniques` verifie que les 5
  dictionnaires cites par `Frontier_Valeur` sont declares exactement une
  fois dans le Functions.

## ItemStack porte son slotIdx : SetContent ecrit A L'INDEX, creation de pile = slot libre
- **Symptome** : depot par `GetContent()` + `SetContent(liste)` qui ne
  fait rien (mv=0, l'objet n'apparait pas alors que le coffre a des cases
  libres) ou qui ECRASE la premiere pile du container.
- **Cause** : chaque `ItemStack` a un champ public `slotIdx` (byte) ;
  `SetContent` fait `Clear()` puis ecrit chaque pile a `itemStack.slotIdx`.
  Un `new ItemStack(id, qty)` sans slotIdx vaut 0 -> il ecrase le slot 0 ;
  ajouter deux stacks neufs s'ecrase mutuellement. Preuve : moteur
  (SetContent : `keywordsID[itemStack.slotIdx] = ...`, warning « Cannot
  write to slot » au-dela de la capacite) et code officiel
  EmpyrionScripting `ItemsData.UniqueSlots()` qui REINDEXE
  `slotIdx = 0,1,2,...` avant chaque SetContent d'ajout.
- **Correctif** : `Frontier_Deposer` prend `max(slotIdx des piles
  existantes) + 1` pour la nouvelle pile (fallback du depot si AddItems
  refuse) ; au-dela de la capacite le moteur ignore proprement la pile
  (warning) — aucun ecrasement.
- **Controle** : test verifiant `st.slotIdx = (byte)ns;` dans l'arbre
  atelier.

## Category: Weapons contient armes ET munitions : deux criteres suffisent
- **Symptome** : des munitions (roquettes, charges de tourelle) atterrissent
  dans la categorie des armes, et inversement des tourelles dans les
  munitions. Vecu 17/11.
- **Cause** : le jeu range armes ET munitions sous `Category: Weapons`
  (217 items dans Frontier-FR) ; le nom seul ne suffit pas (`Turret
  MSRocketWeapon` est une arme, `rocketDrone` est une munition).
- **Criteres exhaustifs** (verifies sur les 217 items) :
  1. un nom contenant `Weapon` est une ARME (tourelles, armes de vaisseau,
     drones) — y compris quand `Weapon` n'est pas en fin de nom
     (`TurretEnemyLaserWeaponBlack`) ;
  2. sinon, un consommable EMPILABLE (`HoldType: 0` et `StackSize > 1`)
     est une MUNITION ; les exceptions nommees (Oxygen, Respirator,
     Extinguisher, Explosives, Constructor, Unit, Bay, Fuel, EnergyCell)
     partent en Divers/Composants ;
  3. les projectiles nommes (Charge, Bolt, Grenade, Bullet, Shells, Ammo,
     Rocket sans Launcher) sont des munitions meme sans StackSize.
- **Piege annexe** : `50Caliber` est la munition de reference et sert de
  `Ref` a des objets qui n'en sont pas (BioFuel, Category: Components) —
  la regle ne doit s'appliquer qu'en l'absence de Category explicite.
- **Resultat** : 99 munitions, 0 arme residuelle.

## Valeur ECF coupee par un saut de ligne : lecture du fichier AVORTEE
- **Symptome** : `ECF config line N is malformed -- ECF reading aborted!`
  puis `Dialogue start state '...' not found` — la console s'ouvre VIDE,
  sans AUCUNE erreur C# (le parseur n'arrive jamais jusqu'a la
  compilation). Vecu 17/11 (log 120714) : un `
` non echappe dans le
  generateur avait coupe une valeur `Functions:`.
- **Cause** : une valeur ECF `Cle: "..."` doit tenir sur UNE ligne. Un vrai
  saut de ligne la coupe, et la lecture du fichier entier s'arrete la :
  tout ce qui suit (dont tous nos etats, en fin de fichier) n'existe pas.
- **Correctif** : dans le generateur, ecrire un echappement C# (deux
  caracteres `\` + `n`) et non un saut de ligne Python ; verifier que la
  ligne generee se termine par son guillemet.
- **Controle** : `scan_ecf_valeurs_coupees` -> erreur prelaunch quand une
  ligne Functions/Output/Execute porte un nombre impair de guillemets.

## AddToGlobalVar ne LIT pas : il renvoie la valeur ajoutee
- **Symptome** : une valeur ecrite par `SetGlobalVar` puis relue par
  `AddToGlobalVar(nom, 0)` revient toujours a 0 ; toute logique
  « memoire » reste sans effet (vecu 17/11 : l'apprentissage des
  destinations de tri ne prenait jamais).
- **Cause** : dans le client 1.20.1,
  `int API_AddToGlobalVar_Int(string name, int addVal)` fait un
  `IncreaseToolbox(...)` puis **`return _addVal`** — la valeur ajoutee,
  pas la nouvelle valeur. `SetGlobalVar` renvoie de meme `_val`. Il
  n'existe donc AUCUNE API de lecture a nom dynamique.
- **Seul mecanisme de lecture** : declarer la valeur en
  `Variable_N: "Nom", param1: dbplayer_string` (ou `dbplayer_int`,
  `dbglobal_int`...) : le compilateur recharge la valeur depuis la base
  dans une propriete C# a l'ENTREE du state.
- **Correctif applique** : la memoire d'apprentissage du tri est stockee
  en 15 listes `Frontier_M0..M14` (`dbplayer_string`, format ",id,id,"),
  ecrites par `SetGlobalVar` et LUES via les variables du hub ;
  `Frontier_Memo(id)` renvoie la categorie memorisee ou -1.

## Les variables dbplayer_* sont chargees PAR ETAT : les declarer la ou on les lit
- **Symptome** : `CS0103: The name 'Frontier_M0' does not exist` sur les
  fonctions d'un etat alors que la variable est declaree dans un AUTRE
  etat du meme arbre (le hub). L'arbre ne compile pas, console VIDE.
- **Cause** : les `Variable_N: "X", param1: dbplayer_string` sont chargees
  a l'entree de CHAQUE etat (recuperation en base uniquement pour l'etat
  courant). Les declarer dans le hub ne les rend pas disponibles dans les
  autres etats de l'arbre.
- **Correctif** : declarer la variable DANS le noeud qui la lit. Ici, les
  15 listes de l'apprentissage sont generees dans le noeud Apprendre lui-
  meme (helper `_vars_memoire()` de core/console_apps.py).
- **Controle** : `test_apps_premiere_passe` verifie la presence des 15
  declarations dans le noeud Apprendre.

## Variable_N : la numerotation doit etre CONTIGUE (parseList casse au trou)
- **Symptome** : `CS0103: The name 'Variable...' does not exist` sur les
  variables d'un etat, alors qu'elles sont declarees dans son propre noeud.
  Vecu 17/11 (log 152351) : les 15 listes d'apprentissage etaient
  `Variable_8..Variable_22` -> aucune n'existait.
- **Cause** : `DialogueSystem.parseList(_el, "Variable_")` lit `Variable_1`,
  `Variable_2`... et **s'arrete au premier numero manquant** (`if
  (!_el.properties.HasKey(text)) break`). Des variables numerotees 8 a 22
  ne sont donc jamais parsees.
- **Correctif** : numeroter `Variable_1..Variable_N` sans trou dans chaque
  noeud (`core/console_apps.py`, `_vars_memoire` : `Variable_1..15`).
- **Controle** : verifier la contiguite apres toute generation (le scan
  des lignes malformees attrape le saut de ligne associe, mais pas le trou
  seul — le CS0103 au log reste l'indicateur).

## Cle de localisation effacee par une regen tierce (`Frontier_*`)
- **Symptome** : le bloc s'affiche en jeu sous son nom technique
  (`Frontier_Console_Atelier`) au lieu de son libelle, alors que la cle
  etait presente dans `Extras/Localization.csv` avant un clic Codex >
  Marchands.
- **Cause** : `_merge_loc` (`core/console_traders.py`) purgeait TOUTES les
  cles `Frontier_*` / `bkiFrontier_*` avant d'ecrire les siennes — une
  regen commerce effacait donc les cles de l'atelier. Et `regen_apps`
  n'ecrivait aucune cle : l'atelier n'etait jamais libelle.
- **Correctif** : chaque generateur ne purge QUE ses propres cles
  (`Frontier_Console_Commercant*` + `Frontier_Licence_*` cote commerce,
  `LOCS_ATELIER` cote atelier) et `regen_apps` ecrit ses 4 cles.
- **Controle** : `scan_blocs_frontier_loc` (prelaunch, warning) liste les
  blocs `Frontier_*` dont la cle `Info:` manque au Localization.csv ; les
  trois blocs vanilla qui pointent vers la cle d'un autre bloc
  (RadarTracker, TrapDoor, HeavyWindowA) sont hors cible.

## `ShowUser: Yes` sur une deco de biome = crash au chargement du playfield
- **Symptome** : `NullReferenceException` dans
  `InstancingManager.AddPrefab(BlockId)` appele par
  `DecorationManager.LoadBiomeDefinition`, immediatement apres
  `[Decoration] Start Loading Deco Presets` — le playfield ne charge pas
  (vecu 18/11 : crash d'Akua apres avoir passe `HollywoodJuniperDesktop` en
  `ShowUser: Yes`).
- **Cause** : un bloc `Shape: Deco` (arbre/plante/rocher de biome, ici
  `Ref: AlaskaCedarBare`) n'est un `ImageContext` que tant qu'il reste
  invisible ; rendu visible, `AddPrefab` caste quand meme le config en
  `ImageContext` et dereference `null`.
- **Correctif** : laisser `ShowUser: No` (ou ne pas ecrire la ligne, pour
  heriter du parent) sur tout bloc `Shape: Deco`. Les deployables visibles
  (tentes, lampes, `AutoMiningDevice`) portent `IsTerrainDecoration: true`
  et ne sont PAS concernes.
- **Controle** : `scan_deco_showuser` -> erreur prelaunch
  (`InstancingManager.AddPrefab` cite dans le message).

## Le scan radar n'existe que par l'arme de vaisseau (pas de radar de base)
- **Symptome** : un bloc de base equipe de `WeaponItem: DetectorCVWeapon` +
  `Class: TurretManual` ouvre bien le panneau tourelle (F), mais ni clic
  gauche ni clic droit ne declenche le scan.
- **Cause** : le scan est porte par le `RadarScan` du provider de device
  `DriveToken`, atteint uniquement par le tir d'une arme de VAISSEAU
  (l'item `DetectorCVWeapon` a `IsRadarItem`). Aucune classe de bloc
  `Class:` ne fournit ce provider : la liste vanilla n'a ni `Radar` ni
  `Detector` (74 classes).
- **Correctif** : laisser le radar sur un vaisseau (`AllowPlacingAt: MS`,
  il apparait dans la barre d'armes). Un radar de base fonctionnel exigerait
  un mod client.
