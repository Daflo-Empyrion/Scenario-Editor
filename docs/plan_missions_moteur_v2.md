# Plan — Missions « Anomalie » (exploitation large du moteur)

État : proposition, 12/11/2026. Base factuelle : `docs/pistes_moteur_inexploitees.md`
(niveaux de preuve V = vérifié, ⚠ = à tester en jeu avant dépendance).
Cible : solo, français d'abord, pas de DLL, pas de DLC, rien de multijoueur.

## 0. Principe

Une chaîne narrative **parallèle** aux jalons I-III existants : 5 missions
« Anomalie » qui se débloquent au fil des jalons, chacune choisie pour
**couvrir une famille de fonctions moteur aujourd'hui inutilisée**. Une
mission ne se justifie que si elle exerce au moins deux leviers nouveaux ;
sinon elle rejoint le chantier « systèmes transverses ».

Contraintes de tenue : tout passe par une **passe idempotente** (même modèle
que `core/tech_milestones.py`) ; textes EN + FR dans `PDA.csv` ; aucune
écriture manuelle dans `PDA.yaml` ; validation par `core/pda/validation.py`
puis en jeu.

## 1. Couverture — levier → mission

| Levier moteur (état actuel) | Mission qui l'exerce |
|---|---|
| `SetTimer`/`TimerRate`, `Preamble`, `CompletedSound` | A1 « Le sas » |
| `Instance:` (Time/Cooldown/DropInventory), `DenyLeaveSV/CV/HV` | A1 |
| `DeviceUnlock` (codes de porte), `HoldingItem` | A1 / A4 |
| `DayNightChange`, `AttackWave`/`WaveStart`, `HUD`, `StructPower` | A2 « La nuit des rôdeurs » |
| Récompenses `DropBox`/`AirDrop`/`DropRange` | A2 |
| `HoldingItem`, `StatusEffectApplied`/`Removed`, `PlayerStatChanged` | A3 « Le contaminé » |
| `IsInvisible`, `Effect:±`, `ItemsCrafted`, `ChapterData`, ⚠`Transform` | A3 |
| `RewardsOnSkip`/`ActivateChapterOnSkip`, réputation, `TraderZone` | A4 « La caravane » |
| `AdditionalPoiSpawning.ecf`, `PlayfieldLevel`, `PdaReferral` | A5 « Le signal » |
| `PoiDiscovered`, `NearUnit`, `MapMarker`/`Discovery`, `ItemsConsumed` | A5 |
| Jetons dans le butin (`LootGroups`), groupes `EGroupsConfig` orphelins | transversal T1 |
| `AffectedByBuffs`, `LootListAlive`, `movement_factor`/`slippery_factor` | transversal T2 (⚠) |
| `PlayerStart: True`, `AllowSavingBlueprints`, 9 options `gameoptions` | transversal T3 |
| `SqlQueries` (panneau unique), `EGroupsConfig` | transversal T4 |

Levers déjà saturés (ne pas réutiliser sans raison) : `WaitAction`,
`DialogOption`, `NearPoi`/`NearUnit`, `SubjectKilled`, `BlockDestroyed`,
`WindowOpened`, `SpawnOPV`, `InventoryOp`, `dlg`/`mbox`.

## 2. Chantier 0 — corrections sèches (avant toute mission)

Aucune dépendance, gain immédiat, réversible.

1. **`Containers.ecf`** : 34 entrées `Name_20…Name_30` jamais lues (plafond 20
   du moteur). Scinder les 10 conteneurs concernés en deux groupes
   (`Group_`+`Name_`), sauvegarde + journal CSV.
2. **`GlobalDefsConfig.ecf`** : `Eden_Shipment160k` → `Mass: 960000`,
   `Eden_Shipment320k` → `Mass: 1920000`.
3. **`gameoptions.yaml`** : trancher l'incohérence masse/volume/CPU du profil
   SP Survival (soit on active, soit on corrige `description.txt`).

Critères : `yamlcheck` 0 erreur, CSV/ECF rechargés par le parseur du projet,
contrôle en jeu des coffres 269/270 (butin rare enfin complet).

## 3. Chantier 1 — infrastructure (½ journée)

- `core/mission_arc.py` : `MISSIONS` (constante déclarative), helpers
  `_chapter/_task/_action`, `pass_mission_arc(scenario, apply=False)` ⇒ dict
  de rapport comme les autres passes ; idempotent (retire puis réinsère nos
  chapitres par clé `pda_Ano*`), réécrit les lignes `PDA.csv` (EN + FR,
  colonne FR = index 3).
- Branchement : appel depuis `tools/conflict_passes.py` (même bloc que
  `tech_milestones`) + option `--only missions`.
- Tests : `tests/test_mission_arc.py` (chapitre créé une fois, contenu
  attendu, 2ᵉ passage = 0 édition, CSV réparé si colonne FR décalée).
- Garde-fous projet : `python tools/audit_i18n.py` = 0, `core/pda/validation.py`
  sur le modèle relu, `yamlcheck` sur le scénario.

## 4. Chantier 2 — les cinq missions

**Avancement** : chaîne **DÉSACTIVÉE le 12/12** (`MISSION_ARC = False`) — la planète de départ a déjà ses missions, on ne surcharge pas le starter ; contenu conservé, reprise après décollage. A1 « Le sas » avait été écrite et appliquée (12/11) —
`core/mission_arc.py` (`MISSIONS[0]`), 16 lignes CSV EN/FR, chapitre
`pda_Ano1*` posé en fin de liste (avant `Creator:`), relance = 0 edit,
`yamlcheck` 0 erreur. Leviers A1 v1 : `NearPoi` en activation (120 m),
`Preamble` (briefing plein écran), `HoldingItem` (outil en main),
`SetTimer: 600` + `TimerRate: 1` (compte à rebours HUD), `ItemsPickedUp`,
`CompletedSound`. Reportés en A1b (à tester isolément) : `DeviceUnlock`
(code de porte) et `Instance:` (purge réelle avec éjection).

Chaque fiche donne : pitch, déclencheur, leviers exercés, contenu à écrire,
fichiers touchés, critères d'acceptation, risque principal.

### A1 « Le sas » — Anomalie I (débloquée par le Jalon I)
- **Pitch** : un bunker scellé à 1,5-2 km du départ ; la porte se referme
  derrière le joueur. Il faut retrouver le code dans les salles et ressortir
  avant la purge. Échec = éjection, inventaire laissé sur place.
- **Leviers** : `SetTimer`+`TimerRate` (compte à rebours HUD), `Preamble`
  (briefing plein écran), `CompletedSound`, `DeviceUnlock` (code de porte),
  `Instance:` (`Time: 12`, `Cooldown: 7200`, `DropInventory: True`,
  `PortalOpen: 120`), ⚠ `DenyLeaveSV/CV/HV` sur le playfield d'instance.
- **Contenu** : 1 chapitre (`pda_Ano1*`), 4 tâches (entrer, lire 3 journaux
  `InventoryOpenedPoi`/`InventoryContains` du code, ouvrir la porte
  `DeviceUnlock`, sortir `PlayfieldLeft`), 1 récompense `Item` (keycard
  `Token:4001`) + `XP`.
- **Fichiers** : `Playfields/EdenDeadRefuge_Instance/playfield.yaml`
  (bloc `Instance:` déjà présent : on en fixe les valeurs), `PDA.yaml`/`.csv`
  via la passe. Aucun nouveau prefab.
- **Acceptation** : le timer s'affiche ; l'éjection laisse bien l'inventaire ;
  la porte refuse sans le code et accepte avec.
- **Risque** : `DenyLeave*` non testé (⚠) — le laisser hors du chemin critique.

### A2 « La nuit des rôdeurs » — Anomalie II (Jalon II)
- **Pitch** : le joueur est prévenu au coucher du soleil ; trois vagues
  attaquent la mine starter (ou sa base). Un largage de munitions tombe entre
  la 1ʳᵉ et la 2ᵉ vague. À l'aube, c'est fini — sans récompense si la base tombe.
- **Leviers** : `DayNightChange` (`Names: [Sunset]`) en activation ;
  `AttackWave`+`WaveStart` (3 vagues), `SpawnEnemy`/`SpawnDrone` en ops,
  `StructPower:local;false` (les lumières meurent au 1er impact),
  `HUD:PdaTasks;false` (panique), récompense `DropBox`/`AirDrop`.
- **Contenu** : 1 chapitre, 5 tâches (survivre vague 1/2/3, récupérer le
  largage, tenir jusqu'à `Sunrise`), 2 récompenses (munitions, `MultiCharge`).
- **Acceptation** : la vague se déclenche au coucher, les ennemis viennent
  bien par vagues, le largage tombe, la fin à l'aube se valide sans action.
- **Risque** : `AttackWave` exige un `WaveStart` cohérent (coût/faction) ⚠ —
  prévoir un test isolé sur un playfield de dev avant intégration.

### A3 « Le contaminé » — Anomalie III (Jalon II)
- **Pitch** : une morsure applique un effet ; la quête de l'antidote court
  contre la progression de l'infection. Sous 25 % de vie, le chapitre bascule
  en hallucination (chapitre caché, playfield qui s'obscurcit ⚠).
- **Leviers** : `StatusEffectApplied`/`StatusEffectRemoved`, `PlayerStatChanged`
  en action, `IsInvisible` (objectif caché « ne pas mourir »), ops `Effect:+/-`,
  `InventoryOp` (retirer l'antidote), `ItemsCrafted`, `ChapterData`
  (`Visibility`/`Reset`), ⚠ `Transform`.
- **Contenu** : 1 chapitre principal + 1 chapitre « hallucination »
  (`PdaReferral` sur le playfield), 4 tâches, 1 récompense `Item`.
- **Acceptation** : l'effet déclenche la tâche, le remède la termine, la
  branche hallucination ne s'ouvre qu'une fois.
- **Risque** : `Transform` non documenté → à isoler derrière un flag de
  constante, retirable en une ligne.

### A4 « La caravane » — Anomalie IV (Jalon III)
- **Pitch** : une caravane marchande traverse la zone ; l'aider donne des
  crédits et des codes de coffre, l'abandonner ferme la branche et allume une
  réputation négative (fin alternative via `OnSkip`).
- **Leviers** : `DialogOption` (déjà connu, ici en choix de branche),
  `HoldingItem`, `RemoveItem`, `AddReputation`, `RewardsOnSkip` /
  `ActivateChapterOnSkip` / `RewardedChaptersOnSkip`, `TraderZone` +
  `StationInterface` sur le POI marchand, jetons en butin (T1).
- **Contenu** : 2 chapitres (aide / abandon), 6 tâches, 2 récompenses
  (`Token`, réputation).
- **Acceptation** : chaque choix ouvre la bonne suite ; l'abandon donne bien
  un chapitre différent et une réputation négative visible en faction.

### A5 « Le signal » — Anomalie V (Jalon III)
- **Pitch** : un signal radio n'apparaît qu'au-dessus d'un niveau de
  playfield ; en le suivant, des POI se matérialisent autour du joueur jusqu'à
  révéler un relais. Chapitre invisible hors de la planète concernée.
- **Leviers** : `AdditionalPoiSpawning.ecf` (POI dynamiques par
  `PlayFieldLevelMin/Max` + `DistanceFromPlanetMin/Max`), `PlayfieldLevel`,
  `PdaReferral`, `PoiDiscovered`, `NearUnit`, `MapMarker`/`Discovery`,
  `ItemsConsumed`.
- **Contenu** : 1 chapitre, 4 tâches, 1 récompense (blueprint ou `Token`).
- **Acceptation** : les POI n'apparaissent qu'au niveau requis, le chapitre
  ne s'affiche que sur le playfield prévu, la découverte du relais le termine.
- **Risque** : `AdditionalPoiSpawning.ecf` n'a **aucun** précédent dans notre
  scénario → première implémentation à faire sur une copie d'un playfield, en
  comparant le log (`RandomPlacer`/`aps`) avant généralisation.

## 5. Chantier 3 — systèmes transverses

- **T1 (données, sûr)** : jetons dans le butin (`Item_n: Token:xxxx` dans
  `LootGroups.ecf`/`Containers.ecf`) ; brancher 5-8 groupes `EGroupsConfig`
  orphelins sur les playfields concernés (contenu déjà écrit).
- **T2 (⚠ à tester)** : `AffectedByBuffs` (créatures sensibles au feu),
  `LootListAlive` (butin sur le vivant), `movement_factor`/`slippery_factor`.
- **T3 (design)** : variante de départ `PlayerStart: True` dans un POI
  (réveil dans une épave) ; `AllowSavingBlueprints: False` sur une planète
  « hardcore » ; pack `gameoptions` mort lourde.
- **T4 (confort)** : un seul panneau `SqlQueries` (jours survécus / morts par
  faction) dans un terminal POI.

## 6. Ordre d'exécution et estimation

| Étape | Contenu | Effort | Bloquant |
|---|---|---|---|
| 0 | Corrections sèches | ½ session | — |
| 1 | `core/mission_arc.py` + tests + branchement | ½ session | — |
| 2 | A1 « Le sas » | 1 session (dont test instance) | 1 |
| 3 | A2 « La nuit des rôdeurs » | 1 session | 1, test `AttackWave` |
| 4 | A3 « Le contaminé » | 1 session | 1 |
| 5 | A4 « La caravane » | 1 session | 1 |
| 6 | A5 « Le signal » | 1-2 sessions | 1, POI dynamiques |
| 7 | T1 → T4 | 1 session | 0 |

Chaque session se termine par : passes à 0 en relance, `pytest` ciblé vert,
`audit_i18n` 0, `yamlcheck` 0 erreur, `docs/scenario_re2fr_particularites.md`
à jour, une fiche cerveau si un piège moteur apparaît.

## 7. Protocole de validation en jeu (une mission à la fois)

1. Nouvelle partie, noter `IdMapping`, `Placing FAILED`, `-ERR-`.
2. Dérouler la mission et cocher la liste d'acceptation de sa fiche.
3. Log : aucune ligne nouvelle liée à nos `Check:`/ops ; `PDA: Missing Name
   parameter` interdit (il signifie un `Names:` vide).
4. Si un levier est invalidé (⚠), il sort du chemin critique et la mission est
   livrée sans lui (constante à `False`), pas de Rustine silencieuse.

## 8. Hors périmètre (assumé)

- Mod DLL (`IModApi`) : installation manuelle, hors scénario, pas de Workshop
  atomique.
- Contenu DLC (Dark Faction) et champs Alpha : dépendance externe.
- Multijoueur : les chapitres MP (`Team`/`Leader`) et `SetStarterPfIndex` ne
  sont pas traités.
- Refonte des 543 chapitres existants : on ajoute une chaîne, on ne réécrit pas.
