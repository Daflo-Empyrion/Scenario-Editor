# IA des PNJ — pistes d'optimisation et de réalisme (RE2-FR)

> **STATUT (08/11/2026) — appliqué.** Les passes P0-P3 ont été exécutées sur
> RE2-FR (6795 modifications, backups dans `C:\Dev\RE2-FR_ai_backups\`,
> réversibles via `python tools/ai_passes.py --revert RUN_ID`), l'audit P4.1
> repart à zéro. Outils P4 livrés dans l'éditeur (menu Outils > « Audit IA
> des PNJ... » + `tools/ai_passes.py`). Détails dans
> `core/ai_realism.py` (presets = P4.2/P4.3) et `gui/ai_audit_dialog.py`.
> Validation en jeu toujours impossible tant que RE2-FR ne charge pas
> (NRE connu) — chaque valeur reste conservatrice et réversible.

Document de travail — exploration moteur + vanille 1.19.1 + RE2-FR
(08/11/2026). Sources : comportement constate en jeu (moteur 1.19.6 build
5188), install vanille
(`C:\Dev\2026-08-13_03h31__vanilla_1_19_1`), scénario RE2-FR. Chiffres
vérifiés par agrégation sur les 342 playfields RE2-FR et 190 vanille.

---

## 0. Ce que le moteur permet vraiment (les leviers réels)

L'IA des PNJ est bâtie sur **Behavior Designer (Opsive)** : les arbres de
comportement (`Behaviors/HiLevelTrees/MainAnimal`, `ZiraxTroopCommands`,
`TalonGuardianCommands`...) sont **compilés dans le jeu — non modifiables
par un scénario**. Ce qu'un scénario contrôle :

| Levier | Où | Effet |
|---|---|---|
| `BehaviorName` + slots (Slot0..19) | EClassConfig | quel arbre/activity l'entité utilise (liste fermée, cf. §A.1) |
| Capteurs : `VisionSensor` (ViewAngle, VisibleDistance), `AlertSensor` (AlertLevel1..6, ouïe, propagation), `FearSensor` (peur, contagion aux amis), `TargetSensor` (AttackableTypes), `GroupDirectionSensor` (TickIfLead), `BodySensor` (soif/faim), `StuckSensor`, `HideSensor` | EClassConfig `{ Child ... }` | perception, alerte, panique, cohésion de groupe |
| `Hints` + `VariableOverride` | EClassConfig | paramètres des arbres (IsHunting, AttackApproachTarget, SpeedCalm...) |
| `AITask-N` / `AITarget-N` | EClassConfig | 106 tâches EAI (Wander, ApproachAttack, FleeOnHurt, DronePathPatrol, Manager*) |
| `BAIConfig.ecf` | Configuration | préchargement des pools d'arbres (perf) |
| `Animations.ecf` | Configuration | délai ray-cast par hold type (synchronisation dégâts/animation) |
| Playfields | yaml | SpawnZones, SpawnRateZones, CreatureSpawning, DroneBaseSetup, DroneSpawning, DroneProb/ReserveCount/TroopTransport des POIs |
| gameoptions | yaml | MaxSpawnedEnemies, Diff* |

Limites moteur hard-codées (à connaître, non contournables) : mémoire de
cible **50 s**, grâce anti-ennemi **9000 s** après début de partie, tick
spawn 0,2 s, despawn si joueur > 500 m en attaque de base, 4
MovementController seulement (GroundMovement, BigSizeFly, SmallSizeFly,
SmallSizeSwim).

---

## 1. Constats (preuves chiffrées)

### 1.1 RE2-FR a rendu les PNJ nerveux mais fragiles
Vitesses ×1,5–2,5 (Raptor SpeedFlee 1,5→3,5), ouïe ×2–3
(NoiseMaxDistance 65→130, NoiseAlertMultiplier 0,5→1,5 sur Zirax),
vision poussée à 130 m sur les humanoïdes — mais HP et XP divisés par
~2–3 (Zirax 500→350, TalonGuardian 500→400). `AlertLevelDrop` 10→5 :
l'alerte retombe moins vite. **Résultat perçu : réactif mais uniforme** —
tout détecte tout de loin, plus de différenciation sentinelle/éclaireur/proie.

### 1.2 RE2-FR a PERDU des fichiers et des contenus (par rapport à la vanille)
1. **`BAIConfig.ecf` absent** : aucun préchargement des 17 pools d'arbres →
   hitchs possibles au premier spawn de chaque comportement, alors que le
   scénario a 2× plus d'entités que la vanille.
2. **`Animations.ecf` absent** : les délais ray-cast par hold type
   (synchronisation animation/dégâts des attaques NPC) retombent sur les
   défauts moteur.
3. **219 groupes de spawn supprimés** (EGroupsConfig 330→143) : patrouilles
   de 14 factions (Epsilon, Ghyst, Rados, Kriel, Pirates...), battle groups
   (ZiraxBattleGroupA/B, TalonGuardianBattleGroup), variantes de hardes
   (`RaptorHerdFew`, `OviraptorsGroupSmall`...), IA de groupe dédiée
   (`WormDesertGroup`/`Leader`, `AlienBugs02Group` protecteur,
   `TalonAdvancedBlackGuard`).
4. **Réputation territoriale neutralisée** : `StructSpawnedInTerritory` et
   `StructStayInTerritory` = 0 — s'installer dans un territoire ne réagit
   plus. Rivalités faction réduites à 17 blocs (dont 2 vidés). Tuer des
   prédateurs ne paie plus que pour Talon/Polaris.

### 1.3 RE2-FR a BRIDÉ la pression drone — en contradiction avec sa difficulté
| Paramètre | RE2-FR | Vanille | Effet |
|---|---|---|---|
| POIs `DroneProb` dominant | **0.0 (2967 POIs)** | 1.0 (1213) | plus d'attaques-drone sur la majorité des POIs |
| POIs `ReserveCount` | **0 (4156/6273)** | 5 | pas de réserves de renfort |
| POIs `TroopTransport` | **12 %** | **50 %** | 4× moins de débarquements |
| DroneSpawning ambiant | **[0,0] sur 66 playfields** | [5,7] | 1/3 des planètes sans drones ambiants |
| Bases Difficulty | **6 (101 PF)** | 5 | mais les bases sont plus dures ! |

### 1.4 DÉFAUT CRITIQUE découvert : 58/59 vaisseaux PNJ ne spawneront jamais
Les `PlanetVessels`/`SpaceVessels`/`Stock` référencent `R2PVZiraxT1`,
`R2OPVZiraxT0/T1`, `RE2_OPVBanditT1`, `OPVFarrRG`... alors que les .epb
s'orthographient avec un underscore : `R2PV_ZiraxCutter01.epb`,
`R2OPV_ZiraxCutter01.epb`, `RE2_OPV_BanditT1_1.epb`. **~50 playfields ont
des patrouilles/OPV/freighters qui échouent au spawn silencieusement.**
La vanille n'a qu'un seul nom manquant (OPVTresariT4).

### 1.5 Rythme de repop uniformisé
`DelayMinMax (20,24)` = 41 % des entrées de faune (vanille : gamme variée
(0,1) à (70,240)) ; les patrouilles Zirax des SpawnZones sont **jamais
re-popées** ([-1,-1] sur 702/1052 entrées, Amount 75-200) — les
avant-postes se vident définitivement après nettoyage. Extinctions locales
possibles pour prédateurs localisés (GolemsIce, MegalonopsesBrown).

### 1.6 Leviers moteur à 0 usage dans TOUT le monde
`SpawnRateZones.AffectedGroups` (booster/couper un groupe précis près d'un
POI), `AffectFriendlies`, `GroupLeaderPriority` (3 usages — **aucune meute
ni patrouille n'a de chef** alors que le sensor de groupe existe),
`SfxSense` (0 actif — pas de cri de détection), `MaxCountInGroup`,
`IsScavenger` (2), `AllowInWater` (~113/3000), PlanetVessels 100 %
RangePatrol (aucun cargo autonome ni vaisseau en dérive).

---

## 2. Pistes priorisées

### P0 — Réparer ce qui est cassé (impact immédiat, peu risqué)
| # | Action | Effort | Impact |
|---|---|---|---|
| 0.1 | **Mapping vaisseaux ↔ .epb** : corriger les ~59 noms (R2PVZiraxT1 → R2PV_ZiraxCutter01) dans les playfields, ou renommer les .epb — à trancher par inventaire complet | moyen | les patrouilles/OPV spatiales reviennent sur ~50 playfields |
| 0.2 | **Réintroduire `BAIConfig.ecf`** adapté aux BehaviorName réellement utilisés en RE2 (reprendre les 17 pools vanille + pools Eden_*/toutes créatures spécifiques) | faible | perf : plus de hitch au premier spawn ; base pour tout le reste |
| 0.3 | **Réintroduire `Animations.ecf`** (copie vanille + hold types des armes RE2) | faible | timing d'attaque cohérent (dégâts collés à l'animation) |

### P1 — Réalisme sensoriel et comportemental (différenciation par archétype)
| # | Action | Effort | Impact |
|---|---|---|---|
| 1.1 | **Profils sensoriels par archétype** au lieu du tout-à-130/1,5 : sentinelle de base (vision 130/ouïe 1,5), éclaireur (vision 80/ouïe 2), prédateur embusqué (vision 40/ouïe 1 + ViewAngle étroit + HideSensor), proie (vision 60/AlertFromFriendDeath + fuite rapide), golem/tank (vision 50, angle 270 vanille restauré) | moyen | chaque rencontre se joue différemment |
| 1.2 | **Chefs de meute/patrouille** : `GroupLeaderPriority` + `TickIfLead` + `MaxCountInGroup` sur RaptorHerd, Parasaurs, TalonGuardianHerd, patrouilles Zirax (le sensor existe, la vanille l'utilise à peine — RE2 peut aller plus loin) | faible | groupes qui tiennent ensemble, réagissent au chef |
| 1.3 | **Prédateurs/charognards** : élargir `IsHunting` (Spinosaurus, Megalonops, AlienBug02/03) et `IsScavenger` (Otyugh, Creepy, Slime, MegalonopsGrey) | faible | écosystème crédible (le moteur module l'agressivité) |
| 1.4 | **Cri de détection** `SfxSense` sur quelques prédateurs/humanoïdes (levier à 0 partout) | faible | le joueur entend qu'il a été repéré |
| 1.5 | **Vie nocturne** : `NightWanderSpeed`/`NightApproachSpeed` généralisés aux animaux diurnes (les créatures Nocturnes existent déjà — RaptorsNight etc.) | faible | les nuits se sentent différentes |
| 1.6 | Rééquilibrer HP/XP là où la nervosité RE2 a trop fragilisé (option : garder le gameplay mais restaurer les HP des « tanks » Golem/Queen) | moyen | le monde redevient menaçant sans être spammy |

### P2 — Pression et cycles (remplir les vides créés par les bridages)
| # | Action | Effort | Impact |
|---|---|---|---|
| 2.1 | **Progression drone par tier de planète** : DroneProb/ReserveCount/TroopTransport croissants (0 → 0,3 → 0,5 → 1,0 ; réserves 0→2→5 ; TroopTransport 10→50 %) au lieu du 0 uniforme | moyen | les débuts respirent, les zones avancées pressent — cohérent avec Difficulty 6 |
| 2.2 | **Re-pops différenciés** : proies (20,24) rapides, prédateurs (70,240), hardes locales repop lentes ; restaurer quelques (0,1) pour les petits animaux ; réparer les extinctions locales ([-1,-1] sur prédateurs localisés) | faible | le monde reste vivant sans re-spawn spammy |
| 2.3 | **Patrouilles Zirax re-popables** (ou quasi : [240, 360]) au lieu de [-1,-1] | faible | les avant-postes ne se vident pas définitivement |
| 2.4 | **SpawnRateZones ciblées** : première utilisation au monde de `AffectedGroups` (booster prédateurs autour des nids, couper la faune près des villes) et `AffectFriendlies` (zones refuges) | moyen | faune zonée fine, signature RE2 |
| 2.5 | **Vagues ambiantes** : remplacer les [0,0] des 66 playfields par de petites vagues (1,2) tier-appropriées | faible | plus de planètes « mortes » |

### P3 — Vie du monde (ambiance, lore)
| # | Action | Effort | Impact |
|---|---|---|---|
| 3.1 | **Recréer un sous-ensemble de patrouilles faction** (les plus lore-relevantes des 219 perdues : Talon, Polaris, Pirates, Kriel — pas tout) avec compositions mixtes comme ZiraxMinigunPatrol RE2 | moyen | rencontres variées, factions vivantes |
| 3.2 | **Variantes de hardes** (`*Few`/`*Mega`) pour moduler densité par biomes | faible | densité crédible selon la planète |
| 3.3 | **Espace** : PlanetVessels avec missions variées (Freighter cargo autonome, Immobile épave/dérive, pas que RangePatrol) ; FreeDrones en embuscade planétaire (Fixed) | moyen | le ciel raconte quelque chose |
| 3.4 | **Aquaculture** : élargir `AllowInWater` aux espèces aquatiques/plongeuses, poissons dans plus de biomes | faible | lacs et océans vivants |
| 3.5 | **Réputation territoriale restaurée** (StructSpawnedInTerritory/StayInTerritory aux valeurs vanille) + rivalités faction (remplir les blocs vides Wastelanders/ARC) + `AttackedPredator/Prey` rémunérés plus largement | faible | vos actes dans un territoire ont des conséquences |

### P4 — Outils dans l'éditeur (rendre tout ça praticable)
| # | Action | Effort | Impact |
|---|---|---|---|
| 4.1 | **Audit IA** (comme epb_check) : capteurs extrêmes (vision/ouïe hors gammes), entités de groupe sans chef, DelayMinMax [-1,-1] sur prédateurs localisés, POIs DroneProb/Reserve à 0 sur planètes tier 3+, noms de vaisseaux sans .epb (détection 0.1 automatique !) | moyen | gouverner la cohérence à l'échelle de 342 playfields |
| 4.2 | **Presets d'archétypes IA** (embuscade/harde/patrouille/sentinelle/tank) applicables en masse sur EClass avec override paramétrable | moyen | appliquer P1 en 2 clics au lieu de 400 éditions |
| 4.3 | **Outil de progression par tier** : appliquer les courbes P2 (DroneProb/Reserve/Delay) par tier de planète en un geste | faible | l'équilibrage global devient reproductible |

---

## 3. Ordre suggéré

1. **P0.1** (mapping vaisseaux — bug, pas du tuning) + **P0.2/P0.3** (2 fichiers à réintégrer).
2. **P2** (courbes de pression + re-pops) — changement de perception maximal pour un effort minimal.
3. **P1** (archétypes sensoriels + chefs de groupe) via l'outil **P4.2**.
4. **P3** en fond (lore), en s'appuyant sur l'audit **P4.1** pour garder la cohérence.

Vérification en jeu à chaque étape : commandes admin `ba` (base attack),
debug IA (`BAIDebugEMainSwitch`), logs `PlanetLifeManager` et
`Behavior does not exists` pour valider les arbres préchargés.
