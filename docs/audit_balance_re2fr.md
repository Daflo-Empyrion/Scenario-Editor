# AUDIT BALANCE — dégâts, PV, XP (RE2-FR vs vanille 1.19.1)

> **STATUT (08/11/2026) — P1 + P2 appliqués (validation utilisateur).**
> P1 : 13 correctifs / 24 éditions. P2 : 8 correctifs / 22 éditions
> (progression armes, MinigunT2 vs CreatureHard, Titan 650, armures
> T2 +50 / Epic +100, Brafus+Salad 75 PV, Cultist 60 / Weston 30,
> XP cohérence ×6). Backups `C:\Dev\RE2-FR_ai_backups\` (run du jour),
> second passage = 0 édition (gardes). EOL préservés, 1455 entités
> intactes, audit IA vide. Reste à valider en jeu quand RE2-FR chargera.

Audit du 08/11/2026, lecture seule. Méthode : héritage `Ref:` résolu, DPS
soutenu = coup × plombs × chargeur / (chargeur × ROF + recharge) ; pour les
lanceurs, dégâts = arme + munition. Trois angles : armes du joueur, PNJ
(dégâts + PV), survie du joueur. Vérifications manuelles sur les 8 constats
les plus critiques : toutes confirmées dans les fichiers.

## Référence mesurée RE2 vs vanille (corrige la fiche « armes ÷2 / HP ×10 »)

| Élément | Facteur médian RE2/vanille |
|---|---|
| Armes du joueur (31 communes) | dégâts/coup ×1,00 · DPS ×1,15 |
| PNJ du sol (151 profils) | PV ×1,00 (Zirax ×0,80) · DPS ×0,71 |
| Drones planétaires / spatiaux | PV ×4,8 / ×4,6 · DPS vs joueur ×1,45 / ×0,20 |
| Tourelles de POI | PV ×7 · DPS ÷2,9 |
| Corps-à-corps des créatures | ÷2 |
| XP | ÷2,3 (Zirax ×0,30) |

→ La « difficulté » RE2 vient des drones/tourelles tanky et de l'XP lente,
pas d'un buff global des PNJ sol.

## Mon module IA (ai_realism) — aucun rapport

Diff backup→actuel sur toutes les valeurs MaxHealth/HitPoints/Damage/
BlastDamage/Armor/ROF : **0 ligne changée** (l'écart « 1126 lignes » vu au
premier diff était 100 % l'effet fin de ligne CRLF, corrigé depuis). Les
passes touchent uniquement : détection/alerte/peur, chefs de meute,
re-pops, pression de spawn, réputation. Interaction réelle : la pression
drone accrue fait RENCONTRER plus souvent les drones aux stats bancales
ci-dessous → corriger la balance AVANT la validation en jeu.

## P1 — corrections proposées (fichier : ligne, valeur actuelle → proposée)

| # | Objet | Problème | Correction proposée |
|---|---|---|---|
| 1 | DroneBaseAttackHeavyMinigun (EC:2058) | XpFactor 69 (voisins 3,5-6, vanille 9) → farm XP | 6 |
| 2 | MeleeMegalonopsGrey (IC:18675) | 550/coup : une PROIE one-shot le joueur 500 PV (vanille 100, variante Brown 60) | 55 |
| 3 | Eden_Dissolver_Weapon2 (IC:26604) | 125 @ ROF 0,1 = 1250 DPS (×28 famille) | ROF 1,0 (125 DPS) |
| 4 | Eden_DroneAbyssalLaser_Ammo (IC:24638) | 1200 @ 0,3 s = 2857 DPS | 400 @ 0,3 s (1333) ou ROF 1,0 |
| 5 | Eden_RoyalZiraxCommander (EC:16791) | porte MinigunEpic du joueur : 1053 DPS, meurt 500 PV en 0,5 s | remplacer par ZiraxMinigunWeapon + entrée Player ×0,3 dans MinigunT2 |
| 6 | Eden_ZiraxInfected*Easy (EC:16671+) | « Easy » 1000-2000 PV > normales 410-550 | 300/400/450/500 · Commander 550 |
| 7 | Eden_SpaceDronePirateGatling (EC:18007) | 1500 PV / 1500 DPS / 18 XP (BanditGatling : 49 DPS) | PV 8000, arme Bandit |
| 8 | Eden_AbyssalSentry2 (IC:24010) | ROF 8 → 80 DPS pour 25 000 PV | ROF 0,8 |
| 9 | Mod PlasmaT1AmmoDamage +300 (Dialogues:22555) | sur arme ROF 0,15 : ×3,9 DPS, blast −275 (négatif) | +45 (calibré ROF 0,15) |
| 10 | Eden_DroneBaySwarm_Drone (EC:17985) | 25 000 PV, 1314 DPS, XP 0 | XP 15 |
| 11 | Matériaux orphelins MechArmored/DroneArmored/HumanLight/DroneLight | entités Abyssal ignorent roquettes ×15 et laser ×8 → 5-15× plus résistantes que prévu | ajouter les 4 matériaux à DamageMultiplierConfig (≈ Mechanical/DronePlanet) |
| 12 | Eden_ImmunityShield (SE:1907) | 500 PV/0,1 s enchaînable = invulnérable | Stack: discard ou 50 PV/0,5 s |
| 13 | Malus PV max sans plancher (SE) | Resurrected −300 + InfectedWound −200 = PV max 0 | plancher via ModifyMaxValue ou réduire les malus |

## P2 — progression (à arbitrer, choix de design RE2)

- Pistol T1→T2 : +2 % DPS (inversion avec mods) ; SMG T3 < T2 vs CreatureSoft ;
  MinigunEpic < Minigun vs CreatureHard ; PulseRifleT3 < AR T2 vs CreatureHard.
- Talon : ZÉRO progression (tout à 400 PV, Chief compris).
- Titan (Armor 500) dominée : MediumEpic + boosters = 675 armor, mobile.
- Armures T2/Epic = T1 en protection (seuls slots/contenance changent).
- Eden_ShotgunDouble : ×2,3 la médiane, dans un pool « very rare » < epic.
- Roquettes ×15 vs Mechanical : saut ×8,5 par tir entre T2 et Epic.
- Soins spamables : BrafusFungi 481 PV/s (achetable 500 cr), Salad 150 PV/s
  (+200 nourriture), Medikit05 100 PV/s — soigne plus vite que tout DPS PNJ.
- Boss à DPS de troupe : Weston (67), CultistOverseer (~10), Weston2 (45) ;
  SpaceDroneTraderBoss avec l'arme d'un petit drone (385).
- XP incohérentes : AssaultMechT2 35 vs MechaBotTank 10 (stats identiques) ;
  AbyssalAssaultMech 100 ; LightBomberBase 15 vs Bomber 7,5 ; FastTransport 10
  vs MiningShuttle 2 ; QueenStatic 25 vs Queen 10 ; tourelles POI toutes XP 2.

## P3 — lore/affichage

- DroneLargePiratesCannon = Small (5000 PV) ; DroneSmallCrystalCube/Sphere :
  10 000 PV + arme spatiale ; RogueSwarmer 15-20k PV > chasseurs ; Crystal
  Micro = Small ; Leaders identiques à la troupe (Raptor, CaveWorm, LizardMule,
  Zirax) ; Tresari défini 2 fois (ver l.9555, humanoïde l.14194) ; entités sans
  Material (GolemOld, Bug03Spitter, Tresari, FARRPrime) ; SoldierHumanMale
  AssaultRifle porte un fusil laser ; FW:996+ référence une catégorie
  `DroneBaseAttackHeavyMinigun` inexistante ; EC:12841 `SubmachinegunT1`
  (casse) — 10 PNJ UCH sans arme ; textes trompeurs (en-tête Armor, 150 vs
  175, bandages « 85 PV » pour 100).

## Ce que le module IA (ai_realism) a changé qui interagit

- **Pression drone ×** (DroneProb 0→0,3/0,5 sur 119 playfields, réserves,
  ambiants) : plus de rencontres avec les drones listés en P1 → corriger la
  balance avant de valider en jeu.
- Archétypes sensoriels / chefs / SfxSense / réputation : aucun effet sur
  dégâts ou PV.
