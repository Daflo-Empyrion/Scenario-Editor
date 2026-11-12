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
