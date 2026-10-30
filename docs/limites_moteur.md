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
