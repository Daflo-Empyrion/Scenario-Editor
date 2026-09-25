# Module d'équilibrage de scénario — recherche et conception

> Demande du 24/09/2026 : trouver un moyen d'équilibrer un scénario
> (MaxCount, dégâts, bouclier, CPU, énergie, etc.) en s'appuyant sur la
> documentation Eleon, les forums et les fichiers réels du jeu, pour un
> module « équilibrage en un clic » avec fenêtre des modifications à valider.
> Ce document = base de conception. L'implémentation est un chantier à
> part entière (session dédiée).

## 1. Où vivent les leviers d'équilibrage (vérifié localement)

Toutes les valeurs citées ont été **mesurées dans les fichiers réels**
(vanille 1.11+ installée + RE2 ATL `C:/Dev/RE2 ATL`), pas recopiées d'un
forum.

### BlocksConfig.ecf (blocs) — propriétés d'équilibrage actives

| Propriété | Rôle | Vanille | RE2 ATL | Notes moteur |
|---|---|---|---|---|
| `MaxCount` | Quantité max par structure | 90 blocs (ex TurretBaseCannonOld 6) | 335 blocs (turrets → 32) | Bloque le placement ; gameoption `EnableMaxCount` peut tout désactiver |
| `ForceMaxCount: true` | Rend la limite incontournable | 40 blocs | 307 blocs | Sans lui, la limite n'est qu'indicative (créatif) |
| `CPUIn` | Coût CPU de l'appareil | 286 blocs, total 5.2 M | 872 blocs, total 16.1 M | Valeurs sauvages RE2 : `MissionContainer` 10 000 000 |
| `CPUExtenderLevel` | Tier d'extendeur (T2..T5) | T2-T4 | T2-T5 (RE2 ajoute) | `#CPUOut` est COMMENTÉ = obsolète, c'est le moteur qui calcule |
| `IsUsingCPUSystem` | Structure soumise au CPU | cores : true + MaxCount 1 + ForceMaxCount | idem | Un seul cœur par vaisseau, forcé |
| `Damage` | Dégâts de l'arme/bloc | 2 blocs | 19 blocs (ex `WeaponCVRailgunT2Blocks` 1889, `AIDroneBay` 330) | Les munitions portent souvent les dégâts (ItemsConfig) |
| `EnergyOut` | Production d'énergie | 7 blocs (GeneratorMS 25000) | 14 blocs (RE2 buffe les générateurs) | |
| `EnergyIn` | Consommation électrique | 447 blocs | 774 blocs | |
| `HitPoints` | Points de vie | 1003 blocs | 1513 blocs (RE2 multiplie ~×8 : CockpitMS01 150→1250) | |
| `Mass` / `Volume` | Masse / contenance | 798 / 404 | 1284 / 766 | Volume = capacité de stockage |
| `Range`, `BlastDamage`, `BlastRadius`, `ROF` (macros GlobalDefs) | Portée, explosion, cadence | — | — | `Range` détecteurs modifiés par RE2 (6000→4000) |
| `AllowedInBlueprint: false` | Interdit aux blueprints | — | — | déjà géré par le contrôle .epb |

### Autres fichiers du dossier Configuration (leviers globaux)

- `DamageMultiplierConfig.ecf` : multiplicateurs de dégâts par
  entité/matériau — le levier le plus « à moindre coût » pour durcir ou
  adoucir un scenario sans toucher aux blocs.
- `BAIConfig.ecf` : comportement/précision des IA (drones, troupes).
- `ItemsConfig.ecf` : dégâts et stack des munitions, objets.
- `GlobalDefsConfig.ecf` : **macros** partagées (`GlobalRef:`) — les armes
  vanilla référencent `Minigun_Damage` etc. : changer la macro change tout
  d'un coup (RE2 ATL peut avoir ses propres macros).
- `GlobalDefs` n'est PAS là où sont les paliers CPU : ils sont câblés dans
  le moteur (voir §2).
- `EGroupsConfig.ecf` / `EClassConfig.ecf` : groupes d'entités et classes
  (utilisés par DamageMultiplier).
- **Playfield yamls** : `MaxDrones` par POI, `DroneBaseSetup` (vagues),
  counts de POIs. Contrainte moteur : ~40 drones max par playfield (dont
  vagues d'attaque) — prévoir de la marge (≈34) ; `MaxStructures`
  (gameoptions) 0-255 mais ~220 max en pratique (crash au-delà, EAH).

### CPU : paliers moteur (communauté, à revérifier en jeu au premier bilan)

Les capacités par classe ne sont PAS dans les ECF. Valeurs documentées par
la communauté (wiki fandom CPU Extender*, fil officiel « [Alpha 11] CPU
Points and Tiers », Reforged Eden) :

| Classe | Base (T1) | T2 (×1 ext.) | T3 (×2 ext.) | T4 (×4 ext.) |
|---|---|---|---|---|
| SV | 40 000 | 100 000 | 250 000 | 500 000 |
| HV | 50 000 | 120 000 | 300 000 | 600 000 |
| CV | 500 000 | 1 250 000 | 2 500 000 | 5 000 000 |
| BA | 500 000 | 1 300 000 | 2 600 000 | 5 200 000 |

Le coût CPU des blocs de structure (coques) est calculé par le moteur à
partir du Volume/Masse quand `IsUsingCPUSystem` est actif ; les appareils
consomment leur `CPUIn`. Aucun de ces paliers n'est éditable par ECF → le
module ne PEUT PAS « régler le CPU du moteur » : il équilibre en
**ajustant CPUIn / MaxCount / dégâts / énergie** des blocs du scénario.

## 2. Constat RE2 ATL (mesures)

- Les tourelles passent de MaxCount 6 (vanille) à 32 (RE2) avec
  ForceMaxCount — un vaisseau peut embarquer 5× plus d'armes qu'en vanille.
- `MissionContainer` : CPUIn 10 000 000 (probablement volontaire, conteneur
  de mission hors CPU) — à exclure des règles par liste blanche.
- HitPoints globalement ×~8 vs vanille, dégâts d'armes fortement augmentés
  (Railgun T2 1889) — scénario volontairement « héroïque ».
- Générateurs buffés (GeneratorSV 1500→2000, SVSmall 700→875).

Conclusion : RE2 ATL a un choix d'équilibrage cohérent « héroïque » ; le
module doit donc proposer des **presets** (conservé / vanille-ratio /
personnalisé) et non écraser aveuglément vers la vanille.

## 3. Conception du module « équilibrage en un clic »

### Principes
1. **Règles déclaratives** : chaque règle = (famille de blocs, propriété,
   politique de calcul). Moteur de règles dans `core/balance_rules.py`,
   alimenté par un inventaire ECF (réutilise `parse_ecf_file` +
   `load_block_catalog` déjà en place).
2. **APERÇU MODIFIABLE avant écriture** (même pattern que l'aperçu de
   fusion ECF-030 et le dialogue de synchronisation) : tableau
   fichier / bloc / propriété / ancien → nouveau / case à cocher, bouton
   « Appliquer les lignes cochées », backups `.bak` + journal d'annulation
   (undo workspace existant).
3. Jamais d'écriture sans validation ; presets strictement séparés des
   règles (un preset = jeu de paramètres, pas de valeurs codées en dur).

### Règles initiales proposées (R1..R7)

- **R1 — Limites de placement (MaxCount/ForceMaxCount)** : politique
  « vanille » (reprendre la valeur vanilla du bloc s'il existe),
  « ratio » (vanille ×k), « plafond » (valeur max choisie). Signale les
  blocs scenario SANS équivalent vanilla (aucune action auto).
- **R2 — CPU des appareils (CPUIn)** : détecte les valeurs aberrantes
  (> n× la vanille ou > n× la moyenne de leur catégorie Devices) ;
  politique : normaliser vers la vanille ou vers un plafond. Exclusions
  par liste blanche (MissionContainer...).
- **R3 — Budget CPU par classe** : estimateur : somme CPUIn des blocs
  d'un modèle de BP ou d'un POI vs palier choisi (table §1) — information
  et suggestion (réduire le CPUIn des plus gros consommateurs).
- **R4 — Dégâts des armes (Damage + munitions ItemsConfig)** : ratio
  scenario/vanille par arme, détection des outliers (hors marge k),
  normalisation.
- **R5 — Énergie (EnergyIn/EnergyOut)** : cohérence production /
  consommation ; normalisation des générateurs vers la vanille ou preset.
- **R6 — Résistance (HitPoints)** : alignement sur un multiplicateur
  global choisi (le scénario actuel ≈ ×8) par famille (hull, cockpits,
  générateurs...).
- **R7 — Difficulté de campagne** : DamageMultiplierConfig + BAIConfig +
  compteurs playfield (MaxDrones ≤ ~34, MaxStructures ≤ ~220) — bornes
  moteur documentées, vérification plutôt que modification automatique.

### UX proposée

- Menu **Outils > Équilibrage du scénario...**
- Étape 1 : choix des règles + presets (cases + k adjustable).
- Étape 2 : aperçu modifiable des changements (avec filtre « problèmes
  uniquement »), totaux par fichier/règle.
- Étape 3 : « Appliquer les lignes cochées » → écritures atomiques
  (atomic_write_text déjà en place), backups, undo, résumé.
- Analyse hors thread GUI (gerbe plasma si > 1 s) ; catalogue de blocs
  réutilisé pour les noms.

### Limites connues (à documenter dans le module)

- Les paliers CPU moteur ne sont pas modifiables par ECF (on équilibre
  par CPUIn, pas par « budget moteur »).
- Les stats des POIs sont dans leurs .epb (outillage .epb déjà présent :
  remplacement/suppression de blocs) — pas dans BlocksConfig.
- La fusion vanille→scenario « dernière définition gagne » : le module
  doit toujours travailler sur la config FUSIONNÉE (même règle que le
  contrôle .epb) et écrire dans les fichiers du scénario.
- Les valeurs de paliers CPU affichées sont communautaires ; les confirmer
  au premier bilan en comparant avec les messages CPU en jeu.

## 4. Sources

- Fil officiel : [Alpha 11] CPU Points and Tiers — empyriononline.com
- Wiki : CPU Extender T2-T4 (SV/HV/CV/BA) — empyrion.fandom.com
- Modding : sethioz.com (MaxCount/ForceMaxCount), guide Steam « Editing
  .ECF Files », thread « Block Config Help » (empyriononline)
- Limites playfields : wiki gameoptions (MaxStructures 0-255), EAH
  (~220 pratique), forum « Drones! » (~40 drones/playfield)
- Boucliers : Steam « How do shields work? », forum HWS « Shield
  capacitors not working? » (capacitors ↑capacité ↓recharge)
- **Mesures locales** : BlocksConfig.ecf / GlobalDefsConfig.ecf vanille 1.11
  et RE2 ATL (détails §1-2, scripts d'inventaire réutilisables)
