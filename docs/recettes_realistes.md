# Recettes réalistes — doctrine et table de référence

> Chantier du 06/11/2026. Objet : aligner les recettes de `Templates.ecf`
> (blocks **et** items) sur le réel — « la recette d'un générateur se base
> sur celle réelle, approximativement ».
> **STATUT FINAL (06/11/2026) — DOCTRINE RE2 BETA VERBATIM.**
> Décision de l'auteur après revue : les recettes de RE2-FR sont celles de la
> base RE2 Beta (atelier Steam `3143225812`), **sans aucune modification** —
> c'était déjà le cas d'origine (RE2-FR = base octet pour octet) ; toutes les
> réécritures du jour (réalisme, composants, exotique, lots, réalignement
> recalé) ont été **annulées**. Les sections §4.1-§4.8 restent comme trace de
> conception mais ne gouvernent RIEN. Seul survivant : les **templates de
> déconstruction** (§4.7) pour les objets non craftables, extrapolés du
> template RE2 le plus proche (`use_realism=False`).

## 1. Doctrine verrouillée

| Point | Décision |
|---|---|
| Livrable | module réutilisable (`core/recipe_realism.py` + dialogue), pas un one-shot |
| Critère | composition **et** proportions |
| Référence | recherche web → ce document → table codée citant ce document |
| Coût | **libre, il dérive** (à la différence de `core/recipe_balance.py`) |
| Périmètre | tout : blocs, items, nourriture, lingots, munitions |
| Maille | par **classe**, quantités à la masse/puissance |
| Matières | composants du jeu en priorité (voir §3, la granularité impose un repli) |
| Sans analogue réel | extrapolation par analogie, **marquée** dans l'aperçu |
| Masse cible | **`Mass` du jeu** (les masses du jeu ne sont pas physiques, voir §2) |
| CraftTime | recalculé, bornes absolues 1-120 (pas de plafond relatif, voir §5) ; `OutputCount` conservé |
| Validation | aperçu cochable → application RE2-FR + backup central → bilan → serveur |

## 2. Ancrage mesuré (RE2-FR, 06/11/2026)

Le jeu porte une masse par objet et par composant, en kilogrammes. C'est le
seul ancrage dont on dispose sans inventer d'unité — mais il n'est **pas**
physique : `GeneratorSV` pèse 500 kg pour 2 000 W (250 kg/kW), alors qu'un
groupe électrogène réel est à 15-25 kg/kW. On garde donc ces masses comme
**conteneur**, et le réalisme porte sur la **répartition**.

Masses unitaires des ingrédients les plus utilisés (mesurées, `ItemsConfig`) :

| Ingrédient | Mass/unité | Utilisations | Ingrédient | Mass/unité | Utilisations |
|---|---:|---:|---|---:|---:|
| SteelPlate | 11,8 | 246 | PowerCoil | 184,9 | 121 |
| SteelPlateArmored | 28,88 | 132 | FluxCoil | 39,1 | 110 |
| TitanPlates | 6,76 | 161 | CapacitorComponent | 42,0 | 120 |
| Motor | 24,28 | 229 | EnergyMatrix | 17,2 | 110 |
| Computer | 12,0 | 284 | Electronics | 2,86 | 246 |
| Oscillator | 8,27 | 199 | MechanicalComponents | 0,65 | 242 |
| OpticalFiber | 0,12 | 138 | PlasticMaterial | 0,18 | 111 |
| CobaltAlloy | 6,29 | 105 | Nanotubes | 0,57 | 62 |
| ZascosiumAlloy | 7,33 | 146 | AluminiumCoil | 8,1 | 80 |
| GlassPlate | 5,8 | 44 | CopperIngot | 6,71 | 28 |
| IronIngot | 5,9 | 15 | SiliconIngot | 1,9 | lingots |

Ratios actuels masse-ingrédients / masse-objet (témoins) :

| Template | masse objet | masse ingrédients | ratio | verdict |
|---|---:|---:|---:|---|
| `GeneratorSV` | 500 kg | 305,5 kg | 0,61 | plausible |
| `GeneratorSVT2` | 750 kg | 812,7 kg | 1,08 | plausible |
| `SolarPanelBlocks` | 730 kg | 353,5 kg | 0,48 | sous-dosé en verre |
| `ConstructorT2` | 7 200 kg | 1 618,6 kg | 0,22 | très sous-dosé |
| `AssaultRifle` | **3,85 kg** | **34,8 kg** | **9,04** | absurde (9× sa masse) |

Le fusil d'assaut résume le problème : la composition n'est pas seulement
fausse, elle est physiquement impossible.

## 3. Règle des deux niveaux, et granularité

**Deux niveaux, un seul est écrit.** Une recette ne contient que des
ingrédients de premier niveau. Un `Motor` (24,28 kg) a lui-même une recette
qui porte son acier et son cuivre. On ne réécrit donc **jamais** la matière
brute à l'intérieur d'un composant : on choisit **quels composants** et
**combien**.

**Granularité.** Les composants du jeu ont des masses unitaires très
disparates (0,12 kg pour `OpticalFiber`, 184,9 kg pour `PowerCoil`). Une part
de 22 kg de cuivre ne peut pas s'écrire « 1 PowerCoil » (185 kg, ×8) : pour
chaque matière, la chaîne de candidats est ordonnée du plus fin au plus gros,
et on retient **le plus gros composant dont la masse unitaire tient dans la
part**, sinon on descend d'un cran, jusqu'au lingot.

Exemple acier : `IronIngot` (5,9 kg) → `SteelPlate` (11,8 kg). Un fusil de
3,85 kg tombe donc sur le lingot, un générateur de 500 kg sur la plaque.
Exemple bobinage : `FluxCoil` (39,1) → `PowerCoil` (184,9).

**Contrainte mesurée au lot 1** : un maillon grossier doit être la **même
matière en vrac**, pas un autre produit. `SteelPlateArmored` (28,88 kg)
captait toutes les parts d'acier (« plaque blindée » pour un générateur) ;
il est écarté de la chaîne. Idem `Computer`/`Oscillator` pour l'électronique
générique : ce sont des produits, pas de l'électronique en vrac.

C'est une **déviation assumée** au choix « composants, pas lingots » : elle
est imposée par la physique des masses, pas par confort.

**Rendement (yield).** La matière entrante dépasse la masse produite de la
perte d'usinage/coulée. Constante par classe, à ajuster en un seul endroit :

| Famille de fabrication | yield | raison |
|---|---:|---|
| Structures, coques, blocs | 1,10 | tôle soudée, peu de perte |
| Assemblages mécaniques | 1,30 | usinage, chutes |
| Électronique | 1,50 | PCB, rebut, test |
| Alimentaire | 1,20 | parage, cuisson |
| Métallurgie (lingots) | 1,05 | rendement de fonderie |

`yield = masse_ingrédients / masse_produite`. Un fusil de 3,85 kg consomme
donc ≈ 5,0 kg de matières, pas 34,8.

## 4. Composition réelle par classe

`parts` = répartition de la **masse cible** (objet × yield). La colonne
« matière réelle » documente l'origine ; la colonne « composants » est ce qui
est écrit dans `Child Inputs`.

### 4.1 Appareils

| Classe | Composition réelle (statut) | Composants écrits (parts) |
|---|---|---|
| `GENERATOR` | acier 58-60 %, cuivre 0,4-1,1 % du groupe complet, fonte pour le moteur (sourcé : EPD groupe 250 kVA, 1 089 kg) | SteelPlate 55, Motor 18, Electronics 12, MechanicalComponents 8, FluxCoil 7 |
| `SOLAR` | verre 74-76 %, alu 8-10 %, silicium 3,6-5 %, plastique ~10 %, cuivre ~1 % (sourcé : NREL tab. 4-18, IRENA 2016) | GlassPlate 50, PlasticMaterial 30, AluminiumCoil 10, SiliconIngot 6, Electronics 4 |
| `THRUSTER` | superalliage Ni > 50 % de la masse chaude, CuCrZr pour les chambres, titane structural (sourcé : UKCMIC OR23016, IOP 2025) | TitanPlates 45, SteelPlate 20, CopperIngot 10, Motor 15, Nanotubes 5, Electronics 5 |
| `MOTOR` / `RCS` | acier 50-60 %, alu 18-30 %, cuivre 10-12 %, aimants ~3 % (sourcé : RWTH/ANTS, ReFreeDrive) | SteelPlate 50, AluminiumCoil 15, CopperIngot 12, Motor 15, NeodymiumIngot 5, PlasticMaterial 3 |
| `SHIELD` | bobines cuivre massif + électronique de puissance + radiateurs (estimation : même famille que transformateur/onduleur) | CopperIngot 30, PowerCoil 25, Electronics 15, SteelPlate 15, CapacitorComponent 10, GlassPlate 5 |
| `WARP` / `TELEPORTER` | extrapolé (aucun analogue) : électronique quantique + supraconducteur + structure | Superconductor 30, QuantumProcessor 20, TitanPlates 20, PowerCoil 15, Computer 15 |
| `CONTAINER` | acier 70 %, joints/plastique 15 %, quincaillerie 15 % (estimation) | SteelPlate 70, PlasticMaterial 15, MechanicalComponents 15 |
| `FUELTANK` / `O2TANK` | acier ou alu 85 %, joints 10 %, robinetterie 5 % (estimation) | SteelPlate 75, AluminiumCoil 10, PlasticMaterial 10, MechanicalComponents 5 |
| `CORE` | électronique + structure + refroidissement (estimation) | Computer 30, Electronics 25, SteelPlate 20, CapacitorComponent 15, Nanotubes 10 |
| `CONSTRUCTOR` | acier 60 %, fonte/alu 15 %, moteurs et mécanique 15 %, électronique 10 % (estimation) | SteelPlate 55, Motor 15, MechanicalComponents 15, Electronics 10, Computer 5 |
| `LIGHT` / `LCD` | verre, plastique, électronique fine (estimation) | GlassPlate 40, PlasticMaterial 35, Electronics 15, OpticalFiber 10 |
| `DOOR` / `LANDINGGEAR` / `GRAVITY` | acier 60-80 %, mécanique, petit moteur (estimation) | SteelPlate 65, MechanicalComponents 20, Motor 10, Electronics 5 |
| `STRUCTURE` | **non traitée** : sa `Mass` est celle d'un volume de plusieurs mètres cubes (un bloc 2×2×2 de béton ≈ 19 t), pas d'une pièce usinée. Mesure du 06/11 : l'ancrage masse y multipliait la matière par 6 en médiane et par 1 400 sur le béton. Composition d'auteur conservée. | — |
| `GENERIC_DEVICE` | repli : acier 50, électronique 25, mécanique 25 (estimation) | SteelPlate 50, Electronics 25, MechanicalComponents 25 |

### 4.2 Items manufacturés

| Classe | Composition réelle (statut) | Composants écrits (parts) |
|---|---|---|
| `FIREARM` | acier 50-65 %, alu 20-30 %, polymère 10-15 % (estimation : aucune source pondérale publiée) | SteelPlate 45, AluminiumCoil 25, PlasticMaterial 20, MechanicalComponents 10 |
| `MELEE` / `TOOL` | acier 70 %, polymère 20 %, électronique 10 % si outil | SteelPlate 60, PlasticMaterial 25, Electronics 15 |
| `AMMO` | douille laiton, projectile plomb/acier, poudre (estimation) | CopperIngot 50, SteelPlate 30, Chemicals 20 |
| `MEDICAL` | principes actifs, support, conditionnement (estimation) | Chemicals 50, PlasticMaterial 30, GlassPlate 20 |
| `FOOD` | recette réelle de cuisine (sourcé par la recette elle-même : pain = farine + eau + sel) | ingrédients réels conservés, quantités recalculées à la masse |
| `UPGRADEKIT` | électronique + métaux précieux (estimation) | Computer 30, Electronics 30, CopperIngot 20, GoldIngot 10, SteelPlate 10 |
| `PLANT` (agriculture) | terreau, eau, contenant (estimation) | Fertilizer 40, PlasticMaterial 30, SteelPlate 20, WaterJug 10 |

### 4.3 Matières premières et métallurgie

Règle : **conservation de la matière**. Les chaînes existantes (`Ore` →
`Ingot` → `Powder`) ne sont réalignées que sur le rendement métallurgique
(minerai → métal : 1,6-2 kg de minerai par kg de fer, 0,5 kg pour l'aluminium
par électrolyse), et seulement si l'objet a une `Mass` mesurable.

| Classe | Correction | Statut |
|---|---|---|
| `INGOT` | masse produite conservée, `OutputCount` inchangé, rendement appliqué au minerai | estimation |
| `ALLOY` (CobaltAlloy, ZascosiumAlloy) | composition d'alliage réelle (base fer + éléments d'addition) | estimation |
| `ORE` / `POWDER` / `ROCKDUST` | intouchés (pas d'analogue fabriqué, `BaseItem: true`) | — |

### 4.4 Sans analogue réel

`Eden_*`, `Promethium`, `Erestrum`, `Pentaxid`, `Xeno*`, `Alien*`, entités
IA : composition de la classe la plus proche, **marquée `extrapole: true`**
dans l'aperçu. Aucun silence : une extrapolation est toujours visible.

### 4.5 Écartés explicitement (chacun avec sa raison)

Toute recette non traitée est listée avec un motif dans le rapport ; aucune
n'est modifiée en silence.

| Motif | Templates | Pourquoi |
|---|---:|---|
| `BaseItem` (matière première) | 179 | minerais, poudres, roches : la composition n'a pas de sens, le moteur s'en sert pour la déconstruction |
| composant (§4.6) | 6 | 4 matières fictives dont la recette d'auteur est incohérente en masse (×0,24 à ×9,9) et 2 qui se contiendraient elles-mêmes (`TitanPlates`←`TitanRods`←`TitanPlates`, `PlatinOunce`) |
| minerai / glace / recyclage / poudre / cristal / gel / granule / gemme / carburant | 45 | matières premières et résidus, pas des objets fabriqués |
| métallurgie (`INGOT`, `ALLOY`) | 2 | CobaltAlloy et ZascosiumAlloy sont traités en §4.6 |
| contenant à gaz (bouteilles) | 6 | la bouteille est un contenant ; au gaz près, elle relève du composant |
| objet endommagé (`CPUBroken*`) | 4 | réparation, pas fabrication |
| marqueur technique / arbre technologique / monnaie / décor / résidu | 8 | objets du moteur, hors économie de craft |
| masse inconnue | 35 | ni `Mass` sur l'objet, ni sur une variante du même template |

### 4.6 Passe des composants (25 écrits)

Un composant n'a pas de composant en dessous : sa recette **est** la matière.
Règle propre, sinon double comptage :

- **cible** = `OutputCount × Mass(composant) × rendement` — 15 des 31 sont en
  lot, donc la matière entrante porte sur tout le lot (10 plaques = 118 kg,
  pas 11,8 kg) ;
- **composition** en matières premières ou en sous-composants réels
  (plaque = lingots de fer + graphite ; moteur = acier 50 / alu 30 /
  cuivre 12 / aimants 4 ; électronique = cuivre 35 / silice 30 / résine 35,
  type PCB ; carte/condensateur = cuivre + alumine + chimie) ;
- **garde-fou anti-cycle** : si un ingrédient retenu demande, transitivement,
  le composant écrit, la proposition est refusée (`TitanPlates`↔`TitanRods`,
  `PlatinOunce`) — la recette se contiendrait ;
- **matières fictives** (Promethium, Erestrum, Eden) : composition de l'auteur
  conservée et remise à l'échelle de la masse, **refusée** si le facteur sort
  de [0,25 ; 4] (la recette d'auteur est alors incohérente : 4 templates).

Mesures après écriture : 25 composants réécrits, puis **80 recettes**
(AMMO/FOOD/MEDICAL) ont suivi, parce que le chaînage des produits chimiques a
été précisé (`NCPowder` pour les petites parts). Total : **686 recettes**,
7 334 lignes modifiées, compteurs structurels inchangés, re-analyse à zéro.
Changer une table re-propose donc des lignes : c'est le contrat, pas un défaut.

### 4.6 bis Objets de quelques grammes : composition d'auteur conservée

En dessous de **1 kg par unité**, l'ancrage masse ne peut rien exprimer et le
minimum « 1 unité » fausse tout. Cas mesuré le 06/11 (`Eden_Semiconductor`,
0,05 kg/unité, lot de 10) : cible de 0,6 kg de matière pour tout le lot, donc
la recette d'auteur — 10 silicium, 5 cuivre, 6 or, 25 plastique, 10 poudre
d'aluminium, 4 palladium, 10 platine, soit ~486 kg — s'était effondrée en
**1 `SiliconIngot`**. La composition réelle d'un circuit intégré
(silicium ultra-pur + dopants + cuivre + or + boîtier époxy) n'a rien à voir
avec ce qu'une masse de laboratoire permet d'exprimer.

Règle : `unit_mass < 1 kg` → **la recette de l'auteur est conservée**
(motif « objet de quelques grammes »). Concernés : `Eden_Semiconductor`,
`MechanicalComponents` (0,65), `Nanotubes` (0,57), `OpticalFiber` (0,12).
Les trois qui avaient été réécrites ont été restaurées depuis le backup.

Cas généralisé le 06/11 après audit des 1 452 recettes : le garde-fou vaut
pour **toute classe**. Si la composition calculée pèse plus de 4× la masse
cible (ou moins du quart), elle n'est **pas écrite** : « composition
inexprimable (unités trop grossières), recette d'auteur conservée ». Les
unités du jeu sont trop grossières pour une pilule de 10 g (`Chemicals` =
40 kg) ou une plantule de 2,4 kg (`Fertilizer` = 85 kg). 65 recettes
concernées, restaurées à la composition d'auteur. Audit final : **3** recettes
à nous hors cadre (115 avant la correction des lots).

### 4.7 Templates de déconstruction (tout ce qui peut être en inventaire)

Le coût ayant été multiplié (§9), il faut pouvoir **récupérer la matière** :
tout objet qui peut entrer dans un inventaire ou un conteneur reçoit un
template, **sans devenir fabricable**.

Outil : `core/template_autogen.py` + `tools/generate_missing_templates.py
--only-obtainable --apply` (idempotent, section ajoutée en fin de fichier).

- **Filtre « peut être en inventaire »** (`obtainable_names`, mesuré le
  06/11) : tous les items, les blocs `CanPickup: true` (15), les blocs cités
  comme `PickupTarget` d'un autre bloc (355 — c'est l'item *reçu* en
  ramassant : tourelle repliée → bloc tourelle), et la déco `IsDeco` sans
  `IsTerrainDecoration`. Le terrain et les textures ne sont jamais en
  inventaire : ils ne coûtent pas un template.
- **Forme écrite** : `Target: ""` (présent au déconstructeur, absent de tous
  les constructeurs — convention vanille `HullDestroyed`), `CraftTime` > 0,
  `DeconOverride: Continue` (sans lui, P3 = 0 et le démontage au premier
  niveau ne rend rien), au moins un ingrédient templaté.
- **Composition** : la table réaliste quand la classe de l'objet est
  connue (§4), sinon le modèle connu le plus proche mis à l'échelle de la
  masse. Réservé aux **items** : un bloc classé par repli aurait reçu de
  l'acier et de l'électronique (mesuré : `AkuaFruit` rendait des lingots).
  La classe de repli `GENERIC_DEVICE` n'est jamais composée.
- **Résultat RE2-FR** : 463 templates ajoutés (436 items, 27 blocs,
  9 feuilles vides), 331 objets écartés avec motif (`aucun modele proche`,
  `ressource brute`, `entree technique`). Fabricable inchangé :
  **767 recettes avec `Target` non vide, avant comme après**.

**Trou de chaîne (trouvé par l'utilisateur le 06/11).** `ErestrumOre` et
`ZascosiumOre` n'avaient **aucun** template, alors qu'ils sont les ingrédients
d'`ErestrumIngot` et `ZascosiumIngot` : le Déconstructeur ne pouvait pas
résoudre l'ingrédient, donc la chaîne de démontage s'arrêtait là — 40 recettes
fabricables étaient concernées. 22 ingrédients cités étaient dans ce cas
(`Fertilizer`, `MoneyCard`, `Bone`, `Egg`, `MetalPieces`, `PentacidOre`,
`PromethiumOre`…).

**Exception : la monnaie.** `MoneyCard` (et `GoldCoins`, `Credits`) n'a pas de
template et ne doit pas en avoir : la carte se dépose dans un **ATM** qui
crédite le compte du joueur, la démonter n'a pas de sens. Elle est citée comme
ingrédient (`PlatinumCard`, blocs PNJ) donc la couverture automatique lui avait
fabriqué une feuille : retirée le 06/11, et `NOT_DECONSTRUCTIBLE` l'exclut
désormais aux deux passes. Les 3 devises restent des matières « sans template »,
ce qui n'empêche pas les recettes qui les citent de s'appliquer — seul leur
démontage est impossible, ce qui est voulu.

Correction : l'outil ne créait des **feuilles** que pour les ingrédients de ses
propres entrées. Il couvre désormais **tout ingrédient cité par n'importe
quelle recette** : `{ Template Name: X, CraftTime: 1, Target: "", DeconOverride:
Stop }` avec `Child Inputs` vide — la forme vanille de `CrushedStone`. Effet :
22 feuilles ajoutées, **0 ingrédient orphelin restant**, 1 452 templates,
fabricable toujours à 767.

**Cohérence avec la table.** Ces stubs sont calculés avec la même table que
les recettes : quand la table change (pointe d'exotique, §4.8), ils deviennent
périmés et un objet démonté ne rend plus ce que sa fabrication consomme.
`refresh_deconstruction()` recalcule **uniquement** les noms de la section
marquée en fin de fichier — jamais les recettes cachées de l'auteur, qui
portent le même `Target: ""` mais une composition écrite à la main. Mesure du
06/11 : 52 stubs de tier ≥ 2, 49 rafraîchis (l'exotique des armes revient au
démontage : 127 recettes consomment de l'Erestrum contre 78 avant), seconde
passe à 0.

**Piège mesuré le 06/11** : `Target: ""` se lit **avec les guillemets**
(`'""'`, chaîne non vide). Un test de vérité naïf prend donc une recette
cachée pour fabricable : 27 recettes non fabricables (munitions Zirax,
`NightVision`, `DeadAnimalBlocks`…) avaient été réécrites par les passes
précédentes, puis restaurées. La lecture passe par `target_of()` qui retire
les guillemets ; `test_hidden_recipe_with_empty_target_is_never_rewritten`
verrouille le cas.


### 4.8 Pointe de matière exotique (le gisement redevient un palier)

Le réalisme avait un effet de bord : les appareils réécrits n'utilisaient plus
**aucune** matière exotique directement (acier, cuivre, alu, verre, silicium,
électronique), et le Zascosium ne subsistait que dans les composants lourds.
Décision du 06/11 : réinjecter une pointe, pour que le gisement reste un
palier de progression.

- **Palier = profondeur dans l'arbre technologique** (`TechTreeParent`,
  plancher au suffixe du nom `T2/T3/…`), **jamais `UnlockLevel`** : mesuré le
  06/11, des blocs de haut niveau se débloquent dès le niveau 1-5, et un `T3`
  est le petit-fils d'un `T1` dans la lignée, quel que soit son niveau
  (`tier_of()`). Distribution sur 576 recettes : 208 / 77 / 98 / 86 / 42 /
  39 / 18 / 8 pour les tiers 0 à 7.
- **Part de masse** : 3 % aux tiers 2-3, 6 % au tier 4 et au-delà, **prélevée
  sur la masse cible**, jamais ajoutée : composition et masse restent justes.
- **Matière** : `ZascosiumAlloy` pour les machines (générateur, propulseur,
  bouclier, constructeur, warp, moteur, cœur), `ErestrumIngot` pour les armes.
- **Limite assumée** : 3 % ne tient une unité (4,65-7,33 kg) qu'au-dessus de
  ~155 kg. Les petits objets (`LaserPistol`, `CannonShellCVT2` et 13 autres)
  n'ont donc **pas** d'exotique, et le disent (« exotique impossible
  (part < 1 unite) ») au lieu d'être forcés.

Résultat RE2-FR : **187 recettes** portent la pointe (118 consomment du
Zascosium contre 31 avant, 78 de l'Erestrum contre 6), 0 proposition
restante, fabricable inchangé (767).

### 4.9 Doctrine finale : RE2 Beta verbatim, stubs extrapolés

Révélé par la restauration : le `Templates.ecf` d'origine de RE2-FR était
**octet pour octet identique** à celui de la base RE2 Beta — l'auteur de
RE2-FR n'avait jamais modifié une recette. Toutes les « divergences » mesurées
dans la journée venaient des passes de ce document, pas du scénario.

État final de RE2-FR :
- **968 recettes = base RE2 Beta, verbatim** (0 différence au parseur) ;
- **410 templates de déconstruction générés** (`use_realism=False`) :
  extrapolation du **template RE2 le plus proche** (méthode d'origine de
  `template_autogen` : même groupe, même famille de nom, même matériau, puis
  proximité de masse ; quantités ramenées à une unité et bornées) ;
- 32 feuilles vides pour les ingrédients sans template (`ErestrumOre`,
  `ZascosiumOre`…), devises exclues (`NOT_DECONSTRUCTIBLE`) ;
- 384 objets sans modèle proche : écartés avec motif (terrain, textures) ;
- fabricables : **767, identiques à la base** ; seconde passe à 0 ;
- `analyze(..., base_root=...)` : toute recette de la base est hors périmètre
  de la composition par classes (les deux doctrines ne se battent plus) ;
- `sync_to_base(root, base)` : remet la base verbatim (utilitaire de retour
  arrière idempotent).

Ce qui a été annulé et pourquoi (trace) : composition par classe (§4.1-§4.4),
passe composants (§4.6), pointe exotique (§4.8), plafond d'unités fines,
recalage des lots — tout reposait sur des compositions inventées là où la
base en fournit de cohérentes (médiane de masse déjà ×1,00). L'ancrage masse
n'est resté utile que pour **détecter** les recettes douteuses
(`_audit_recettes.csv`) et pour borner l'extrapolation des stubs.

## 5. Calcul

Pour un template de masse cible `M` (kg objet) et de classe `C` :

```
M_ingr = M × yield(C) × OutputCount
pour chaque (matière, part) de C :
    m_part = M_ingr × part / 100
    si le composant résolu pèse < 1 kg et m_part > 2 % de M_ingr :
        m_part = 2 % de M_ingr ; le surplus repart sur la part non fine la
        plus lourde (voir garde-fou « unités fines »)
    composant = le plus grossier de la chaîne dont Mass ≤ m_part,
                sinon le plus fin
    qte = max(1, round(m_part / Mass(composant)))
CraftTime = clamp(round(2 + M_ingr^0,4 × s_kg(C)), 1, 120)
OutputCount : inchangé
```

**`OutputCount` = un lot.** 30 roquettes de 128 kg, c'est 3 840 kg de matière
entrante, pas 128. Mesure du 06/11 : l'oubli laissait **101 recettes**
(munitions, armes, plantes) 30 à 40 fois sous-dotées.

`s_kg` (secondes par kg^0,4) : structures 0,05 ; appareils 0,5 ;
électronique 5 ; alimentaire 10. Valeurs d'ordre de grandeur, réglables en
un seul endroit.

**Aucun plafond relatif au CraftTime existant.** C'était l'erreur du premier
jet (06/11) : « jamais plus de ×10 la valeur d'auteur » n'est pas idempotent,
le plafond monte avec la valeur écrite (mesuré : 3 s → 30 s plafonné, puis
60 s, puis 120 s — un ratchet). Bornes **absolues** 1-120 uniquement ; le test
`test_craft_time_is_not_ratcheted_by_its_own_value` le verrouille.

L'exposant 0,4 est mesuré : une formule linéaire envoyait 625 kg et 78 t au
même plafond de 120 s, et ne distinguait donc plus rien.

**Réalisme ±20 %** : la masse obtenue est comparée à `M_ingr` ; un écart
au-delà de 20 % (dû aux arrondis et au minimum 1) est signalé en aperçu, pas
corrigé en silence.

## 6. Garde-fous

- **Idempotence** : la cible dépend de `M` et de la table, jamais du coût
  courant → une 2ᵉ passe ne doit produire **aucun** changement. Critère
  d'acceptation dur (le piège du ratchet a déjà été vécu le 23/10).
- **Cycles** : une recette ne peut pas se contenir ; le graphe est vérifié
  avant écriture, repli vers le lingot amont sinon (déjà vécu : prix à 1e17
  le 04/11).
- **Comptage aberrant** : une quantité > 10× celle de la recette actuelle est
  signalée (cas `PlasticMaterial` 0,18 kg : 30 % d'un panneau de 730 kg =
  1 216 unités — mathématiquement juste, à l'œil suspect).
- **Unités fines** (`PlasticMaterial` 0,18 kg, `MechanicalComponents` 0,65,
  `OpticalFiber` 0,12, `Nanotubes` 0,57, `Electronics` 2,86) : une part de
  masse brute les rend absurdes — mesuré au lot 1, un constructeur de 7,2 t
  demandait **18 000** `MechanicalComponents`, un panneau **1 582**
  `PlasticMaterial`. Leur part est plafonnée à **2 %** de la masse cible, le
  surplus repart sur la part non fine la plus lourde (l'acier en pratique).
  Dérogation assumée : la répartition réelle en masse n'est plus exacte pour
  ces matières, la lisibilité en jeu l'est. Réglage : `FINE_MASS_CAP`.
- **Déconstruction** : `BaseItem`, `DeconOverride`, `Target` et
  `OutputCount` sont préservés ; l'impact sur le déconstructeur est listé.
- **Structures hors ancrage masse** (`NO_MASS_ANCHOR`) : `STRUCTURE` (coques,
  béton, bois, déco) garde la composition de l'auteur. Mesure du 06/11 : la
  masse de ces blocs est celle d'un **volume** (2×2×2 de béton ≈ 19 t), d'où
  des multiplicateurs de ×6 en médiane et ×1 400 au pire — le jeu est
  délibérément abstrait sur ces blocs. Elles sont listées avec ce motif.
- **Template partagé** : une recette pour N variantes (jusqu'à 93) → masse de
  **l'objet lui-même**, et masse maximale du groupe seulement si l'objet n'a
  pas de `Mass`. Le max de groupe est écarté en premier choix : mesuré au
  lot 1, `ContainerLargeBlocks` pèse 125 kg quand une variante du même
  template en pèse 20 000 (×160) — la recette devenait celle d'un vaisseau
  pour un bloc de 125 kg. (Contrairement à `recipe_balance`, où le max de
  puissance reste juste : une recette sert toutes les variantes.)
- **Masse introuvable** (ni `Mass` ni masse de groupe) : objet laissé intact
  et listé « non traité (masse inconnue) ».
- Aucune écriture sans validation ; backup central ; jamais de `.bak` à côté
  des fichiers du jeu.

## 7. Critères d'acceptation

1. 2ᵉ passe = 0 changement (idempotence).
2. Masse obtenue dans ±20 % de `M × yield` pour les classes `sourcé`.
3. `OutputCount`, `Target`, `BaseItem`, `DeconOverride` inchangés.
4. Chaque template soit traité, soit listé avec sa raison.
5. Aucun cycle nouveau ; fichier non modifié si l'objet est inconnu.
6. Bilan éditeur à 0 erreur, serveur dédié qui démarre, 3 témoins vérifiés
   en jeu (`GeneratorSV`, `SolarPanelBlocks`, `AssaultRifle`).

## 8. Sources

- **Modules solaires PV** (verre 74-76 %, alu 8-10 %, silicium 3,6 %, cuivre
  0,8 %, plastique 11-12 %) : tableau 4-18 « Materials and average mass
  fractions of a typical crystalline standard module » du guide DOE /
  PV Fire Safety (2018) —
  https://www.energy.gov/sites/prod/files/2018/10/f56/PV%20Fire%20Safety%20Fire%20Guideline_Translation_V04%2020180614_FINAL.pdf
  *Attribution corrigée le 06/11 : cette table est souvent citée comme
  « NREL tableau 4-18 », elle est publiée dans le guide DOE.*
- **Groupes électrogènes** : EPD Italy, groupe 250 kVA ≈ 1 089 kg —
  acier 58-60 %, cuivre 0,4-1,1 %. **URL non retrouvée le 06/11** : à
  rechercher sur epditaly.it (catégorie générateurs). Ordre de grandeur
  cohérent avec les EPD de transformateurs du même registre (Matelec
  FPT184xx : acier magnétique 36,8 %, tôle 16,4 %, cuivre 12,6 %).
- **Moteurs électriques** : ReFreeDrive H2020, *Deliverable 8.2 — LCA
  technologies analyses*, https://zenodo.org/records/4725240 (75 kW :
  acier ~50 %, alu 31,8 %, cuivre 12,1 %, aimants NdFeB 2,8 %) ; désassemblage
  pesé RWTH Aachen/ANTS (acier 60,2 %, alu 17,6 %, cuivre 11,7 %, aimants
  3,2 %) — URL à retrouver.
- **Moteurs-fusées** (superalliages Ni, CuCrZr, titane) :
  https://www.ukcmic.org/downloads/reports/ukcmic-specialist-alloys-aerospace-report-or23016.pdf ;
  https://ntrs.nasa.gov/api/citations/20080004531/downloads/20080004531.pdf ;
  https://beta.iopscience.iop.org/article/10.1088/2631-7990/ae5295/pdf ;
  https://scholar.afit.edu/cgi/viewcontent.cgi?article=2329&context=etd
- **Armes légères** : **aucune source pondérale publiée** — la répartition
  retenue est une estimation d'ingénierie, à traiter comme telle.

## 9. État du lot 1, décisions validées et dette

État au 06/11 (soir) : `core/recipe_realism.py`, `gui/recipe_realism_dialog.py`
(Outils ▸ Balance ▸ « Recettes réalistes… »), `tests/test_recipe_realism.py`
(17 cas) et `tests/test_recipe_realism_dialog.py` (2 cas). Sur RE2-FR :
**603 recettes proposées**, 365 écartées avec motif, **0 template sans
explication**, 0 proposition restante après écriture.

**Écrit et vérifié hors jeu** : 661 recettes de blocs/items, 25 composants
(§4.6), 80 recettes de munitions/nourriture/médical après précision du
chaînage chimique, puis **83 structures restaurées** à la composition
d'auteur. Backups à chaque passe dans `~/.empyrion_editor/backups/recipe_balance/`,
compteurs structurels des 967 templates inchangés, round-trip ECF identique,
aucun ingrédient inexistant.

### Impact mesuré sur la matière première par unité

Avant / après, en kg de matière première récursive (lecture seule, mêmes
masses) :

| Classe | Médiane | p90 |
|---|---:|---:|
| GENERATOR | ×20,1 | ×54 |
| WARP | ×16,6 | ×165 |
| CONSTRUCTOR | ×14,8 | ×61 |
| SHIELD | ×14,4 | ×53 |
| FOOD | ×12,3 | ×77 |
| MOTOR | ×7,8 | ×25 |
| COMPOSANT | ×1,2 | ×6,5 |
| FIREARM | ×1,7 | ×10 |
| AMMO | ×0,5 | ×3 |
| STRUCTURE | ×1,0 (restaurée) | — |

Lecture : le jeu était **10 à 20 fois plus léger que la physique** sur les
appareils (0,1 kg de matière par kg d'objet au lieu de 1-2). C'est le prix du
réalisme, et c'est assumé — mais cela veut dire que la progression de RE2-FR
devient nettement plus exigeante : c'est le contrôle en jeu qui tranche, pas
le rééquilibrage des prix.

### Boucle monétaire de l'or (contrôle du 06/11, non modifiée)

Chaîne mesurée : `GoldOre` ← 22 `GoldCoins` ; `GoldIngot` ← 5 `GoldOre` pour
10 lingots ; `GoldCoins` ← 5 `GoldIngot` pour 10 pièces (**2 pièces par
lingot**) ; ATM = `Credits: 50` par pièce.

- Donc **1 000 lingots → 2 000 pièces → 100 000 crédits**.
- Cible annoncée par l'auteur : **1 000 000** (facteur 10 manquant).
- La boucle est aujourd'hui **exactement à l'équilibre** : un lingot acheté
  200 chez un marchand rend 2 pièces = 100 crédits. Passer `Credits` à 500
  sans toucher aux prix transforme ce même achat en **bénéfice ×5** :
  imprimante à fric.
- Révision cohérente (à faire avec le rééquilibrage des prix marché) :
  `Credits` 500, `MarketPrice` lingot 1 000 et minerai 2 000 (le lingot vaut
  aujourd'hui MOINS qu'un minerai), prix marchands de `GoldIngot` ×10.
- La recette inverse reste saine à 500 : 22 pièces (11 000) → 5 minerais →
  10 lingots → 20 pièces (10 000), perte de 9 %.

Reste : contrôle en jeu, puis rééquilibrage des prix marché (`market_balance`)
pour que les marchands ne vendent plus sous le coût de fabrication.

Validé par l'utilisateur le 06/11 : **plafond des unités fines à 2 %**,
**repli vers le lingot autorisé**, **les 140 templates sans `Category`
classés** (fait : règles par token de nom dans `TOKEN_CLASS`/`SKIP_TOKENS`).

1. **Plafond des unités fines à 2 %** (§6) : c'est le réglage qui décide de
   la lisibilité. Sans lui, 1 582 plastiques pour un panneau et 18 000
   mécaniques pour un constructeur ; avec lui, 105 et 288. Le réalisme de
   répartition en souffre, le jeu y gagne.
2. **Le repli vers le lingot** quand la part est plus petite que le composant
   (§3) : entorse au choix « composants, pas lingots ».
3. **Les tableaux `yield` et `s_kg`** (§3, §5) : une seule constante chacun,
   mais ils décident de tout le coût.
4. **Les composants** (§4.5) : dette assumée, passe métallurgique à part.

**Reste** : contrôle en jeu des 3 témoins (démarrage, constructeur,
déconstructeur), puis écriture des **658** autres recettes, puis rééquilibrage
des prix marché (`market_balance`), puisque les coûts ont bougé.
