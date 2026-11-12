# RE2-FR — inventaire des particularités du scénario

> But : **source de rédaction** de la fiche du scénario (Steam, Discord,
> README du mod). Une entrée = une particularité de gameplay, avec ce que le
> joueur voit et où c'est réglé dans les fichiers.
>
> **Ce fichier se met à jour à chaque changement de gameplay** : on ajoute ou
> corrige l'entrée concernée, puis une ligne dans le journal en bas.
>
> Mesures faites sur les fichiers réels (`C:\Dev\RE2-FR`, version prod :
> `…\Content\Scenarios\RE2-FR`). Chiffres arrêtés au **11/11/2026**.
> Réglages de survie et d'équilibrage détaillés : `MODULE_EQUILIBRAGE.md`,
> `docs/audit_balance_re2fr.md`.

---

## 1. Il n'y a plus de gisement au sol

- **Toutes** les ressources `RandomResources` sont désactivées : 99 planètes
  (4 628 lignes) et 65 lunes (2 860 lignes). Aucun gisement ne pousse.
- Le minerai se trouve **dans les POI**, via `SpawnResource` : il faut aller
  le chercher dans les mines gardées.
- Réglé par : `tools/conflict_passes.py --only rare_resources` →
  `pass_rare_resources` (`RARE_RESOURCES = True`).

## 2. Mines gardées (la seule source de minerai)

**Une mine starter par planète/lune** — c'est le point d'entrée de partie.

| | Mine starter | Mine de faction |
|---|---|---|
| Groupe | `ConflictStarterMine` | `Conflict<Faction>Mines` |
| Prefab | **`RE2FR-BA_AbandonedMine-NoTurrets`** (copie sans ses 6 `SentryGun03` ; l'original `BA_AbandonedMine` reste pour les mines Pirates/Alien) | pool par faction |
| Distance au départ | **1,0 à 1,4 km de la capsule** (`SpawnPOINear: [<pod de départ>]`) ; 1,2-1,5 km du centre du biome quand le playfield n'a pas de pod déclaré | ≥ 2 km (hostile) / 1,2 km (alliée) |
| Minerai | fer + cuivre | fer + cuivre + cobalt, **+ néodyme si hostile** |
| Drones | **aucun** (`DroneProb: 0`) | 2-3 (alliée) / 3-5 (hostile) |
| Tourelles | **aucune** (copie de prefab sans `SentryGun`) + `InitPower: false` | alimentées |
| Musique | **`Tempest`** à l'entrée du POI (`Properties: Music`) | nappe `DarkSoundscape*` du playfield |
| Créatures | Alien hostiles (Cauchemars, Infectés) | celles du prefab |
| Repop | **72 h** de temps de jeu (4 320 min) | **72 h** |

- **La distance est comptée depuis la capsule, pas depuis le centre de la
  planète.** `SpawnPOINear` accepte un `GroupName` déjà posé : la mine
  s'ancre sur le pod de départ (`FixedPlayerStart > Structure`). Sur les
  playfields sans pod déclaré (25 écrivent `Wreckage`, qui n'est pas un
  groupe POI), elle garde l'ancrage `START` = centre du biome.
- Nombre de mines par playfield : **1 starter + 1 par faction du roster**,
  soit 8 factions sur une planète, 6 sur une lune (tirage déterministe sur le
  nom du playfield ; Zirax toujours présent) — mesuré : 9 mines sur Dread.
- Réglé par : `pass_faction_conflict` / `pass_mine_pois`
  (`core/conflict_warfare.py`, constantes `STARTER_MINE`, `_STARTER_MINE`,
  `MINE_POIS`, `_MINE_ORES*`, `_MINE_DEFENSE`, `_POI_AVOID`).

## 3. Les mines sont visibles sur la carte, même sous brouillard

- Propriétés des mines : `Discovery: False` (« always visible, even if not
  detected or under fog of war ») + `MapMarker: Neutral`, et
  **aucune** `MapDistance`/`HudDistance` (une valeur 0 signifie « jamais
  révélé » — c'est le piège qui a rendu les mines invisibles le 11/11).
- **Couleur du marqueur = couleur de la faction** (constaté en jeu 12/11 :
  la starter « Abandoned Mine » apparaît en violet Alien). `MapMarker:
  Neutral` ne force PAS le blanc quand le POI a une faction — les textes PDA
  ont été corrigés en conséquence.
- Le nom affiché est celui du prefab (« Abandoned Mine », « Mining Hub »…),
  pas le `GroupName`.
- Réglé par : `_mine_entry` dans `core/conflict_warfare.py`.

## 4. Régénération des POI : coupée, sauf vaisseaux, ancres et mines

- `RegeneratePOIs: True` dans **SP Survival et MP Survival** (la vanille le
  laisse à False en solo : sauvegardes plus lourdes, CPU).
- `RegenAfter` est en **minutes de temps de jeu** (compteur gelé hors
  session) ; `0` (= absent) signifie **jamais**. Régénération paresseuse :
  évaluée au (re)chargement du playfield — il faut sortir et revenir.
- **Ce qui ne revient plus** (`RegenAfter: 0`, **4 268 POI**) : bases de
  faction, ruines, décor, épaves au sol… Une structure se récupère **une
  fois**. Comme il n'y a plus de gisement au sol (§1), c'est ce qui force
  l'exploration.
- **Ce qui reste intact** :
  - les **vaisseaux et épaves volantes** (`SV/CV/HV/OPV`, ~587 instances) —
    la tension de patrouille repose sur eux ;
  - les **ancres de placement** (176 groupes cités par un `SpawnPOINear`,
    3 811 dépendances) : sans elles, les POI qui s'ancrent dessus ne se
    replacent plus ;
  - les **marchands** (`Trader`) — un service détruit ne reviendrait pas.
- **Mines : 72 h** (4 320 min de jeu) au lieu de 1-3 h — l'exploration reste
  obligatoire, mais une mine épuisée finit par revenir : pas de blocage
  minéral (le minerai ne vient que des POI, §2).
- Appliqué par : `tools/regen_passes.py --scenario C:\Dev\RE2-FR --apply`
  (idempotent, sauvegarde par fichier, `--sync-prod` pour publier). **À
  relancer après toute passe de conflit**, qui réécrit `RegenAfter: 720` en
  dur pour les POI qu'elle génère. Le bilan
  (`tools/prelaunch_check.py`) signale tout POI hors politique.

## 5. Guerre totale entre factions NPC

- **21 factions** participent : 12 hostiles au joueur (Zirax, Kriel, Warlord,
  Pirates, TheLegacy, Xenu, Rados, Epsilon, Ghyst, Serdu, Abyssal, Alien) et
  9 alliées (Polaris, Talon, Farr, UCH, Wastelanders, Colonists, ARC, Tesch,
  Trader). `ForceAttack` symétrique : elles se battent entre elles partout.
- Par playfield : une base par faction du roster, des patrouilleurs au sol et
  dans l'espace, et des défenses spatiales par faction (21 `FactionSettings`,
  41 blocs `Unit`).
- **Exception : la faction `Alien`** (celle des sites abandonnés, donc de la
  mine starter) **ne participe pas à cette guerre** : sa liste se réduit au
  joueur. Ses mines et ses ruines ne sont jamais rasées par les NPC — sans
  ça, la mine starter mourait avant la première visite du joueur.
- Réglé par : `pass_force_attack`, `pass_space_conflict`,
  `pass_space_defense` (`_WAR_EXEMPT = ("Alien",)`).

## 6. Zone de départ volontairement calme

- **Aucun drone dans les 3 500 m centraux** : 4 zones de patrouille
  `CenterX ±6000` / `±9000`, rayon 2 500, 5 à 10 drones.
- Les **patrouilleurs** (vaisseaux de faction au sol) sont bridés à un rayon
  de **1 000 m autour de leur base**. Sans ce réglage le moteur patrouille à
  l'échelle de la PLANÈTE (commentaire vanille : « Default patrol area is
  planet-size ») et un vaisseau Zirax venait survoler le point de départ
  (mesuré : Kiuvera-Class Cutter à 1 103 m du spawn, 370 m d'altitude).
- Tous nos POI évitent le point de départ : **2 000 m** pour les hostiles,
  **1 200 m** pour les alliés.
- Aucun POI `IsCommandCenter` sur `Starter_Dread` → **pas de vague
  d'attaque de base** sur la planète de départ (le système vanilla en a
  besoin ; 42 playfields en possèdent).
- Attention pour le joueur : **17 factions revendiquent un territoire
  visuel** (`ClaimTerritory: true`). Construire dans une zone colorée coûte
  de la réputation à la pose, puis toutes les 5 minutes → la faction devient
  hostile et attaque en continu.

## 7. Progression : trois jalons technologiques

Missions PDA, catégorie `SoloMission`, activables dès le niveau 1, textes
FR + EN dans `PDA.csv` (`pda_Jal1*` … `pda_Jal3*`).

| Jalon | Objectif | Récompense |
|---|---|---|
| Jalon I — Le premier lingot | ramasser 200 fer | 3 UP + 1 500 XP + **1 multi-outil + 250 charges** |
| Jalon II — Le cobalt du vaincu | ramasser 150 cobalt | 5 UP + 3 000 XP |
| Jalon III — L'ère du néodyme | ramasser 100 néodyme | 8 UP + 6 000 XP |

- **Chaînage** : le chapitre d'accueil déclare lui-même la suite —
  `ActivateChapterOnCompletion: pda_Jal1Title` (lance) + `RewardedChapters:
  [pda_Jal1Title]` (satisfait le `Activatable: WhenRewarded` du Jalon I).
  Les deux clés sont indispensables : sans elles le Jalon I reste affiché
  « à récompenser ». Quatre chapitres placés en tête dans l'ordre accueil →
  I → II → III. Jalons II et III restent activables à la main ; la fin du
  Jalon I le dit explicitement (« active le Jalon II dans le PDA (F1) >
  Missions solo »).
- Total possible : **16 points de déblocage et 10 500 XP**, plus un
  **multi-outil et 250 charges** au premier jalon (de quoi démonter les pièces
  des POI avant d'avoir un déconstructeur).
- Chaque jalon affiche un **message de validation** (`pda_Jal*Done`) qui
  récapitule le gain : sans lui, le jeu ne montre **rien** au moment où la
  mission se valide (constaté en jeu le 12/11).
- La même note est aussi **dans le premier message du chapitre de départ**
  (`eden_pda_84WqK` « Intro: Dread (Dead2) », message `eden_pda_qWOUGCK` —
  « Ow. My head. » — celui qui s'affiche vraiment au lancement ; la même
  note est posée sur le prologue UCH `pda_mKuKK` par sécurité). Texte
  **court** (3 lignes) et boîte de **30 s** : l'encart renvoie au PDA
  « Rappuie sur F1 pour la note complète », où le chapitre d'accueil développe
  tout. L'encart est recalculé à chaque passe (repéré par sa couleur) : le
  raccourcir dans `_MSG_EN`/`_MSG_FR` suffit à le mettre à jour partout :
  encart orange ajouté à la suite du texte narratif, en anglais **et** en
  français (la colonne `Français` de ce message était vide : elle est
  désormais remplie, traduction comprise). C'est le seul canal garanti — une
  tâche PDA ne s'affiche pas dans un chapitre `HideTasks: true` (vécu 12/11,
  la note était invisible).
- Avant eux, un **chapitre d'accueil** (`pda_Intro*`, catégorie `Tutorial`,
  visible et activable d'emblée) : il explique que le minerai n'est plus dans
  le sol, où sont les mines, celle de départ et le conseil de construire près
  du point de chute. Sa tâche se valide à l'**ouverture de la carte (M)** —
  `Check: WindowOpened`, `Names: [Map, SectorMap, SystemMap]` — et
  reste **complétable à la main** (`AllowManualCompletion`) pour ne jamais
  bloquer. C'est le
  garde-fou contre le « plus de ressources = bug » d'un joueur qui ne lit pas
  la fiche du scénario.
- Textes FR + EN dans `PDA.csv` — **le français va en colonne 4**
  (`Français`) ; la colonne 3 est l'allemand.
- Réglé par : `pass_tech_milestones` (`core/tech_milestones.py`,
  `TECH_MILESTONES`, `_INTRO`).

## 8. Réglages joueur modifiés (profils `gameoptions.yaml`)

| Réglage | SP Survival | MP Survival | Vanille |
|---|---|---|---|
| `MaxStructures` | **255** | 2 000 | 2 000 |
| `EnableVolumeWeight` | **False** | True | True |
| `EnableCPUPoints` | **False** | True | True |
| `MaxSpawnedEnemies` | **100** | 60 | 60 |
| `RegeneratePOIs` | **True** | **True** | False (SP) |

- En clair pour le joueur solo : pas de gestion volume/poids, pas de points
  CPU, jusqu'à 100 ennemis simultanés, POI qui se régénèrent, et
  **255 structures maximum par playfield**.
- **Plafond moteur de `MaxStructures` : 255 par playfield.** Doc livrée avec
  le jeu (`Content/Scenarios/Default Random/gameoptions_example.yaml:23`) :
  « Max number of structures per playfield (**limit = 255**, reduce if you
  have performance problems) ». La valeur est un `int` côté moteur
  (`GameOptionsYamlData.MaxStructures`) donc un `2000` **se charge sans
  erreur mais reste borné à 255** — le profil MP ci-dessus est au-delà du
  plafond, c'est la valeur vanille du mod, pas la nôtre.

## 9. Coulisses (utile pour la fiche technique, pas pour le joueur)

- **Bilan avant lancement** : familles `conflict`, `hygiene`, `validation`
  (correction en un clic) + CSV des corrections — `core/launch_check.py`.
- **Toutes les passes sont idempotentes** (2ᵉ passage à 0 modification) et
  sauvegardées fichier par fichier (`ai_passes.py --revert`).
- Console de test : `python tools/conflict_passes.py --scenario C:\Dev\RE2-FR`
  (dry-run), `--apply`, `--only <passe>`, `--limit N`, `--sync-prod <chemin>`.
- Replis par constante dans `core/conflict_warfare.py` : `TOTAL_WAR`,
  `TOTAL_WAR_FORCE_ATTACK`, `RARE_RESOURCES`, `MINE_POIS`, `STARTER_MINE`,
  `SPACE_DEFENSE_ENABLED`, `_DRONE_PATROLS`, `_MINE_DEFENSE`, `_WAR_EXEMPT`.

---

## Journal

| Date | Particularité touchée | Ce qui a changé |
|---|---|---|
| 12/12/2026 | Missions « Anomalie » (désactivation) | La planète de départ a **déjà ses missions** : la chaîne Anomalie I est **retirée du PDA** (chapitre + 16 lignes de textes) pour ne pas surcharger le starter. Le contenu est conservé dans `core/mission_arc.py` (`MISSIONS`) et se réactive en repassant `MISSION_ARC = True` ; le pass sait désormais **retirer** ce qu'il a posé. Les missions seront reprises **après le décollage**, hors planète de départ. |
| 12/12/2026 | Mission Anomalie I (tâche 2) | « Prends l'outil multifonction et vise la serrure » était **impossible** : Empyrion n'a pas de serrure sur les portes, et un POI avec noyau interdit la récupération au multi-outil. Remplacé par l'action réelle du jeu : **détruire le `CoreNPC` de la mine** (`BlockDestroyed` / `Names: [ConflictStarterMine]` / `Types: [CoreNPC]`), idiome utilisé par les chapitres RE2. Le noyau alimente la purge et verrouille la récupération : la fiction tient enfin sur une mécanique existante. |
| 12/11/2026 | Régénération des POI (ressources en tension) | La régénération ne concerne plus que ce qui la justifie : sur 9 393 `RegenAfter`, **4 268 POI passent à 0** (base, ruines, décor, épaves au sol → une seule récupération) et **1 773 mines passent à 72 h**. Restent **intacts** les vaisseaux/épaves volantes (~587 instances, tension de patrouille), les **176 ancres `SpawnPOINear`** (3 811 dépendances de placement) et les **marchands** (service). Mesuré sur 188 playfields : 9 555 entrées POI. Politique et réécriture `Value:` seule dans `core/regen_policy.py`, passe `tools/regen_passes.py` (idempotente, sauvegarde), contrôle `scan_regen_policy` au bilan. Effet voulu : chaque structure se récupère une fois, l'exploration devient la seule source durable. |
| 12/11/2026 | Missions (PDA) | Le chapitre Anomalie I était écrit avec `ChapterActivation:` en **mapping** au lieu de **séquence** : YamlDotNet rejette alors **tout** le PDA (« Expected 'SequenceStart', got 'MappingStart' ») → crash au lancement. Générateur corrigé (`core/mission_arc.py`), chapitre réécrit, contrôle `scan_pda_sequences` ajouté au bilan. |
| 12/11/2026 | Prefabs (blocs manquants) | 1 580 prefabs citaient des blocs **absents du `BlocksConfig`** du scénario (le jeu saute la cellule) : garde-corps (`RailingVertMetal` seul concernait 1 262 prefabs), fenêtres lourdes (`HeavyWindow*Bottom*`, `*Glass*`) et une affiche. **Substitution** par la variante existante la plus proche (5 707 entrées de mapping renommées, **aucune cellule touchée** : même nombre de blocs, mêmes positions). Les blocs fonctionnels (boucliers, CPU, téléporteurs, minerais) n'ont **pas** été substitués — décision de gameplay. |
| 12/11/2026 | Zones de spawn (nettoyage) | Tentative de neutralisation des zones `SpawnRateZones` visant un POI absent : **annulée**, elle commentait des en-têtes `SpawnZones:` et faisait crasher le chargement des planètes. Playfields restaurés ; les zones restent en place (inertes, sans effet). |
| 12/11/2026 | POI composés (espace) | 5 sous-descripteurs `IsCompoundSubDesc` manquants recopiés (3 playfields) : les composés `CompoundEdenAsteroidRichT1`, `CompoundPolarisHaulerTerritory`, `CompoundTSOPolarisTerritory` sont enfin créés ; `CompoundZiraxSentryT1`, déclaré nulle part, retiré des 2 `TestOrbit*`. |
| 12/11/2026 | Groupes de POI (espace) | 3 groupes cités sans prefab pointent maintenant vers le prefab existant le plus proche : `R2TraderAuxT2`→`EPH_R2TraderAuxT1`, `CivilSettlementO2`→`BA_CivilSettlementO`, `R2KrielDroneBase`→`Eden_BA_KrielDroneBase` — ces POI apparaissent enfin. |
| 12/11/2026 | Dialogues PNJ (colis) | 3 liens de dialogue cassaient sur des états inexistants (téléporteur, capsule de purge, général d'expédition) : recâblés vers les états voisins ; les 4 états du marchand de colis (`Give/Take_Greet|Deny`) sont écrits, avec 6 lignes de localisation EN/FR. |
| 12/11/2026 | Créatures (butin) | 5 entités avaient `IsScavenger: True` alors que le moteur n'utilise que la forme numérique (vanille : `100`) : valeur ignorée. Corrigé en `100`. |
| 12/11/2026 | Progression (conteneurs) | `ContainerAmmoSmall` était déblocable au **niveau 1**, comme son parent `ContainerLargeBlocks` : le jeu rejette un enfant au niveau ≤ celui du parent. Remis au niveau **3** (valeur vanilla). |
| 12/11/2026 | Zones de spawn (groupes) | 9 playfields (lunes de glace) citaient `ZiraxMechanoidPatrolEasyEasy`, groupe **inexistant** (absent aussi de la vanille) : le moteur ignorait la zone silencieusement. Référence alignée sur le groupe réel `ZiraxMechanoidPatrolEasy` → les patrouilles Zirax apparaissent enfin sur ces lunes. |
| 12/11/2026 | **Crash au lancement (armes MS)** | Les deux armes importées citaient `Material: metalweapon`, matériau **absent** du `MaterialConfig` du scénario → `System.Exception: Material 'metalweapon' not found in item '4010'`, puis `NullReferenceException` dans `DeployPciture` : **crash du jeu** au démarrage d'une partie. Corrigé en `Material: Device` (celui des `TurretMS*Weapon` du scénario). Leçon consignée : toute référence ECF importée (`Material`, `AmmoType`, `Sfx*`) doit être vérifiée contre le scénario, pas contre la vanille. |

| 12/11/2026 | Missions (nouvelle chaîne) | **Anomalie I : « le sas »** — approcher la mine starter (120 m) déclenche un briefing plein écran, puis : descendre dans la mine, tenir l'outil multifonction sur la serrure morte, extraire 50 fer pendant que **la purge s'égrène dans le HUD (10 min)**, sortir. Récompense : 80 XP + carte magnétique (`Token` 4001) et sonnerie de fin. Écrite par `core/mission_arc.py` (passe idempotente), textes EN + FR. |
| 12/11/2026 | Butin (coffres) | Le moteur ne lit que les index 0..19 de `Containers.ecf` : **34 entrées `Name_20+` ne sortaient jamais** (10 conteneurs, dont les Eden 268/269/270 : néodyme, sathium, tablette, superconducteur…). Surplus réémis en `LootGroups` `RE2FR_Surplus_<id>` (mêmes probabilités/quantités) et appelés par un `Group_` d'un index libre. Aucun retrait : ces objets deviennent enfin obtenables. |
| 12/11/2026 | Colis de ravitaillement (masse) | `Eden_Shipment160k` / `320k` pesaient **10× trop léger** (96 t pour 160 000 L au lieu de 960 t) : corrigé à 960 000 et 1 920 000 kg, aligné sur la série (6 kg/L). |

| 12/11/2026 | Arsenal (armes MS réimportées) | 2 WRN `SnA: stat 'achv_just_to_be_sure' - unknown item/block` : la liste des 8 armes du succès vanilla est **codée en dur dans le client** (*vérifié contre le chargement réel (v1.19.6)*), et le mod avait retiré les armes MS portées par le joueur (ids 110/112 réassignés à `CannonCVT1Weapon`/`LaserCVT1Weapon`). Réimport de **`RocketLauncherMSWeapon`** et **`PulseLaserMSWeapon`** à l'identique de la vanille, sous de nouveaux ids (`4010`, `4011`), munitions existantes (`FastRocketMS`, `PulseLaserChargeMS`), ligne de localisation `RocketLauncherMSWeapon` ajoutée. **Inertes** : `WeaponItem:` reste commenté côté `BlocksConfig`, `ShowUser: NoButCSV` les garde hors artisanat — aucun effet sur l'équilibrage. |
| 12/11/2026 | Log de lancement (mesh truss) | 3× `Cannot create mesh for block id=1407 texIdx=24` : bloc `TrussCylinder` (famille Truss, `Texture: 59` = une seule texture) posé avec la variante couleur **24** par 101 prefabs → index hors liste, mesh non créé (3 blocs invisibles près du spawn). Variante remise à 0 (`EpbBlueprint.set_colors`, matrice Colors : masque et cellules intacts). 1 078 blocs dans 101 `.epb`, dev + prod, sauvegardes `C:/Dev/_backup_prefabs_color/2026-11-11/{dev,prod}`. Défaut de donnée vanille : le `BlocksConfig` n'a pas été touché. |
| 12/11/2026 | Mine starter (distance) | Constaté en jeu : mine annoncée « ~1,2 km » mais mesurée à **2,44 km** de la capsule. Cause : `SpawnPOINear: [START]` s'ancre sur le **centre du biome** (`RandomPlacer: StartBiome center: 0, 0` au log), alors que le pod est lui-même posé `SpawnPOINear: [START]` à 250-2000 m de ce centre — ici pod à 1,29 km d'un côté, mine à 1,39 km du côté opposé. Correctif : `SpawnPOINear: [<groupe du pod>]` (`FixedPlayerStart > Structure`, 7 playfields) + `[1000, 1400]` → 1,0-1,4 km de la capsule. Repli `START` là où `Structure` n'est pas un groupe POI (`Wreckage`, 25 playfields). **Validé en jeu (nouvelle partie)** : mine à **1 071 m** de la capsule (avant : 2 442 m). |
| 12/11/2026 | Jalons (chaînage) — validation en jeu | Parcours complet vérifié sur une nouvelle partie : la mine starter apparaît sur la carte, le Jalon I se termine, la récompense (`MultiTool` + `MultiCharge` x250) est bien reçue avec son message de validation et l'annonce du Jalon II. |
| 11/11/2026 | Mines (marqueurs) | `Discovery: False` + `MapMarker: Neutral`, plus aucune distance : les mines sont visibles sous brouillard (avant : `MapDistance: 0` = jamais révélé). |
| 11/11/2026 | Mine starter (placement) | `SpawnPOINear: [START]` + `[1200, 1500]` : distance bornée (avant : simple minimum, la mine pouvait être à 10 km). |
| 11/11/2026 | Mine starter (faction) | Faction `Alien` au lieu de `None` : les créatures du prefab redeviennent hostiles. |
| 11/11/2026 | Mine starter (tourelles) | `InitPower: false` : les 6 blocs `SentryGun03` ne tirent plus (POI resté abordable en début de partie). |
| 11/11/2026 | Guerre NPC (Alien) | `Alien` exemptée de la guerre totale : la mine starter n'est plus détruite par les factions avant l'arrivée du joueur. |
| 11/11/2026 | Réglages joueur (documentation) | Plafond moteur vérifié : `MaxStructures` = **255 par playfield** (doc du jeu) → le SP est déjà au maximum, le `2000` du profil MP est au-delà du plafond. |
| 12/11/2026 | Zone de départ (patrouilleurs) | `Radius` posé par erreur sous `ImmobileTask` → YamlException, playfield refusé, crash au chargement. Corrigé : `Radius` uniquement sous `RangePatrolTask`, erreur retirée des 3 playfields touchés. |
| 11/11/2026 | Zone de départ (patrouilleurs) | `RangePatrolTask: Radius: 1000` sur les vaisseaux planétaires : ils restent autour de leur base au lieu de patrouiller toute la planète et de venir au-dessus du spawn. |
| 12/11/2026 | PDA (note minerai) | Texte raccourci à 3 lignes + renvoi « rappuie sur F1 » ; boîte portée à **30 s** (20 s ne suffisaient pas). Encart désormais recalculé à chaque passe (bug : les `
` littéraux s'empilaient). |
| 12/11/2026 | Mine starter (tourelles) | `InitPower: false` ne désarmait PAS les 6 `SentryGun03` (le courant ne gate pas les devices d'un POI). Copie du prefab `RE2FR-BA_AbandonedMine-NoTurrets` avec les 6 blocs retirés (`EpbBlueprint.remove_ids`, 10 796 → 10 790), utilisée par le seul POI starter ; l'original est conservé. |
| 12/11/2026 | Mines (marqueurs) + PDA | Constaté en jeu : le marqueur prend la couleur de la faction (starter = violet Alien), `MapMarker: Neutral` ne force pas le blanc. Textes PDA corrigés (« marqueur blanc » retiré) ; les lignes `pda_Intro*` se réécrivent maintenant à chaque passe. |
| 12/11/2026 | Log de lancement (blocs fantômes) | 1 509 lignes `IdMapping: no name for id` (923 prefabs, 196 blocs) : les prefabs posaient des blocs supprimés du `BlocksConfig`. Chirurgie sur nos 744 prefabs (751 remplacements par l'équivalent le plus proche, 437 retraits sans équivalent — invisibles, le moteur les sautait déjà). ~206 lignes viennent de prefabs VANILLE, non modifiables. `MechanoidRocket` aliasé (20 warnings). |
| 12/11/2026 | Ménage du scénario | 608 prefabs retirés du dossier `Prefabs/` (7,6 Mo) : 594 jamais cités, 12 marqués `OUTDATED`/`Test*` par le mod, 2 sauvegardes `_old`. Mis en quarantaine dans **dev et prod** (`C:/Dev/_quarantine_re2fr/2026-11-11`: `Prefabs/`, `prod_Prefabs/`, `manifeste.csv`, `RESTAURER.txt`), pas supprimés. Contrôles : tous les `BlueprintFileNames` et `Prefab:` résolvent, 0 inutilisé restant au scan, 9 passes à 0. |
| 12/11/2026 | Mine starter (musique) | Piste du POI : `Tempest` (hors famille `DarkSoundscape*` du playfield, donc audible au changement). Fichier `.ogg` perso ABANDONNÉ : l'entrée audio d'un `.decals` (section `[Plants]`, `-Audio`/`-Diffuse`, clone de l'entrée Atlantis) n'est jamais jouée sur un POI instancié, même en nouvelle partie, et sans aucun message d'erreur au log. Seules les pistes embarquées passent ; RE2 ajoute les siennes via un bundle Unity (`SharedData/Content/Prefabs/eden_music`). |
| 12/11/2026 | Mine starter (musique) | `Properties: - Key: Music / Value: DarkSoundscape2` sur le groupe `ConflictStarterMine` : piste jouée à l'entrée du POI (*vérifié contre le chargement réel (v1.19.6)*, POI → structure → playfield → `default`). Piste embarquée uniquement — les clips viennent des bundles, un fichier perso est impossible depuis un scénario. Piège vanilla noté : dans un POI à grandes sections d'options, la musique peut être remise à zéro. |
| 12/11/2026 | Jalons (chaînage) | `WhenRewarded` seul ne démarre rien : ajout de `ActivateChapterOnCompletion` + `RewardedChapters` sur le chapitre d'accueil (schéma du prologue RE2), sinon le Jalon I reste « à récompenser ». |
| 12/11/2026 | Jalons (chaînage) | Nos 4 chapitres remontés en tête dans l'ordre accueil → Jalon I → II → III (`WhenRewarded` ne regarde que le chapitre PRÉCÉDENT), Jalon I en `WhenRewarded` + message de validation qui indique d'activer le Jalon II dans PDA > Missions solo. |
| 12/11/2026 | PDA (accueil) | Tâche « ouvre la carte » : `Names` corrigé en `[Map, SectorMap, SystemMap]` — la touche M ouvre la fenêtre `Map` (`ConditionStreamStoreSite`, titre `mpwMapTitle`), pas `SystemMap` (carte système). `AllowManualCompletion: true` en filet. |
| 12/11/2026 | Jalons (récompenses) | Message de validation `norm;25` sur chaque jalon (aucun retour du jeu sinon) + `Item: MultiTool` (1) et `Item: MultiCharge` (250) au jalon I. Boîte du premier message du départ doublée (10 → 20 s). |
| 12/11/2026 | PDA (note minerai) | Chapitre visé corrigé : le vrai départ est `eden_pda_84WqK` (« Intro: Dread (Dead2) »), pas le prologue UCH. La note est posée sur son premier message (EN + FR), et sur `pda_mKuKK` en second. |
| 12/11/2026 | PDA (note minerai) | Tâche ajoutée dans un chapitre `HideTasks: true` = invisible : la note est déplacée dans le **premier message** du prologue (`pda_mKuKK`), EN + FR, et la tâche est retirée. |
| 11/11/2026 | PDA | Chapitre d'accueil `pda_Intro*` en tête : « le minerai n'est plus dans le sol, voilà où sont les mines ». Et correction de colonne : le français des jalons était écrit en colonne **Deutsch** (donc jamais affiché en FR), déplacé en colonne `Français`. |
