# Frontier-FR — inventaire des particularités du scénario

> But : **source de rédaction** de la fiche du scénario (Steam, Discord).
> Une entrée = une particularité de gameplay, avec ce que le joueur voit et
> où c'est réglé dans les fichiers. Ce fichier se met à jour à chaque
> changement de gameplay. Mesures sur `C:\Dev\Frontier-FR` (prod :
> `…\Content\Scenarios\Frontier-FR`, sync à faire). Chiffres au **14/11/2026**.

---

## 1. Console commerçante constructible (les 69 commerçants de la galaxie)

- **Ce que le joueur voit** : une console posable en base/vaisseau capital
  (`Frontier_Console_Commercant`, onglet « Commercants » de l'arbre,
  débloquable niveau 10 pour 20 pts, fabriquée avec 5 Electronics +
  10 Plastic). Dans son menu :
  - **« Activer un commerçant »** — chaque commerçant de la galaxie vend
    **sa licence** chez lui uniquement (1 000 000 cr, stock 1) ; il faut
    donc l'avoir trouvé. Activer **consomme la licence** (définitif) ;
  - **« Mes boutiques actives »** — pour chaque commerçant activé :
    **ACHAT** de son catalogue complet et **VENTE** des marchandises qu'il
    recherche. Cliquer un item ouvre une **fenêtre quantité** (×1 / ×5 / ×25 / ×100 /
    ×1000, plus **×MAX** à l'achat — calculé sur le crédit et le budget
    restant ; totaux affichés, crédit visible), puis **confirmation**
    avant l'opération ; 9 items par page (12 options max affichées par l'UI).
- **Prix** : fixes (milieu des plages de `TraderNPCConfig.ecf` ×
  `MarketPrice` des items) — pas de prix flottant ni de stock limité.
- **Réglé par** : bloc Id 136 (`BlocksConfig.ecf`, clone du
  PlayerConsoleGIN en Class NPCDialogue + `DialogueState:
  Frontier_TraderHub`), 1 template (`Templates.ecf`), 69 licences
  `Frontier_Licence_*` (Id 1411-1479, vendues via 69 lignes de stock dans
  `TraderNPCConfig.ecf`), **38 794 nœuds de dialogue générés** (×MAX exécuté en `OptionExecute`
  direct — `Execute_N` est tronqué à 150 caractères par le compilateur) dans
  `Dialogues.ecf` (marqueur `===== Console commerçante Frontier-FR =====`).
  **Régénération** : bouton **« Régénérer les consoles commerçantes »**
  dans Codex > Marchands (module `core/console_traders.py`, mode fusion —
  préserve les éditions manuelles hors sections générées, relit
  TraderNPCConfig/ItemsConfig à chaque passage) puis déploiement prod.
  Backups d'origine : `C:\Dev\_backup_frontier\pool_traders_20261114\`.

## 1b. Pourquoi pas de bornes TraderNPC posables (limite moteur)

- Un bloc `Class: TraderNPC` posé par un joueur s'installe (la place est
  occupée) mais reste **invisible et sans NPC** : le spawn du PNJ est
  verrouillé par 3 conditions moteur (dont une condition créatif/admin),
  échec silencieux. Le F vanilla du bloc dit « Press F to configure
  trader » — outil d'éditeur. Même RE2 n'a jamais fait de trader
  craftable. Détails : fiche cerveau `bloc-tradernpc-editeur-uniquement`.

## 2. (reporté) Récompenses UP/XP sur la chaine PDA

Décision reportée : rewards `Type: UP` / `Type: XP` sur les chapitres PDA
(motif RE2, voir fiche cerveau `pda-reward-up-points-hors-niveau`).

## 3. Système « Shadows of Starlight » (scénario officiel intégré)

- **Ce que le joueur voit** : un système supplémentaire **« Shadows of
  Starlight »** sur la carte galactique, à [-160, 40, -160] (StarClass G3),
  joignable au warp depuis les systèmes voisins. 8 secteurs : Brexxis,
  Melago, Veldis (+ Veldis Moon), Gourtex, Kayam, un champ d'astéroïdes et
  « Somewhere » (espace isolé) — les planètes du scénario officiel SoS,
  avec leurs POIs d'origine (bases Zirax, colonies, épaves, consoles
  secrètes…) et leurs routes warp d'origine (`Allow:` hérités du legacy).
  **6 secteurs d'arrivée au warp** (`Shadows of Starlight [Sun
  Right/Left/Top/Bottom/Front/Back]`, type `SpaceWarpTarget`) autour du
  soleil : sans eux le warp vers le système crash le client (voir
  `limites_moteur.md`, contrôle `scan_sun_warp_targets`).
  **Nouvelle partie requise** : la galaxie est copiée dans la sauvegarde à
  la création — les parties existantes ne voient pas le système.
- **Ce qui n'est PAS venu de SoS** : la campagne PDA (Extras/PDA, reportée)
  et le TraderNPCConfig.ecf de SoS (quasi-vanille, fallback vanille OK).
- **Particularité design SoS** : Melago n'a **volontairement aucune
  ressource** (`RandomResources:`/`AsteroidResources:` vides dans le
  playfield d'origine) — c'est voulu par Eleon, ne pas « corriger ». Le
  prelaunch le liste dans le groupe « playfields sans ressource » (17e
  entrée, même classe que les 16 baseline vanilla).
- **Réglé par** : 13 dossiers `Playfields/Bro1_*` + 46 `.epb` dans
  `Prefabs/` (aucune collision de nom) + un système converti du format
  legacy SoS vers le format EVO à la fin de `Sectors.yaml` (marqueur
  `SHADOWS OF STARLIGHT (scenario integre)`). Conversion : secteurs legacy
  réindentés sous `- Name: Shadows of Starlight` ; items de listes
  (`Allow:`, `Playfields:`) indentés 2 crans sous leur clé (sinon
  yamllite ne les attache pas). Backups centraux
  `~/.empyrion_editor/backups/sectors/`.

---

## 4. Donjons aliens (2 minimum par playfield jouable)

- **Ce que le joueur voit** : sur chaque planète, lune, orbite et champ
  d'astéroïdes de la galaxie (175 playfields), au moins **2 donjons
  aliens** à explorer (bases BA de la faction Alien, drones hostiles,
  butin à la clé). Le choix du donjon varie d'un monde à l'autre parmi :
  tours alien (BA_AlienTowerV2a/V3a/V4a), temple ancien
  (BA_AncientTemple), sanctuaire Xenu (BAF_XenuShrine), tours de garde
  (BA_AlienWatchtower1/2). Sur les planètes/lunes ils apparaissent à des
  positions tirées par la graine ; sur les orbites/champs, deux donjons
  flottent dans l'espace (Pos fixes ±[3500, 1800, -2800]). Les donjons
  réapparaissent après ~12 min (RegenAfter: 720).
- **Exclus** : GasGiant (pas de surface d'atterrissage), soleils, portes
  de warp (SpaceWarpTarget*), scènes scriptées Story_*.
- **Marqueurs** : faction **Alien** en couleur **magenta FF00FF** (comme
  RE2-FR) — couleur définie dans l'override
  `Content/Configuration/Factions.ecf` du scénario (`{ Faction Id: 8,
  Name: "Alien" → Color: "1, 0, 1"}` ; vanilla = 0.9,0.9,0.9 quasi-blanc).
  Pas de `MapMarker:` sur les donjons (la valeur Neutral écrase la couleur
  de faction en blanc). NB : cet override remplace le Factions.ecf vanilla
  — le resynchroniser si une mise à jour du jeu le modifie.
- **Espace** : les POIs d'orbite exigent un bloc `Position: RadialInfo:`
  (placement aléatoire dans le secteur) — sans lui ils sont silencieusement
  ignorés (le log montre N structures spawnées < entrées ; vecu 15/11 :
  Omicron Sector 22/24). Format copié du corpus : `RadialInfo: [0, 0, 0,
  0, 1.5, 2, -1, -1, 0, 0, 0]` (rayon 1.5-2 autour du centre).
- **Réglé par** : 2 entrées ajoutées dans `POIs:` de chaque playfield
  (`playfield_static.yaml` Random pour les planètes/lunes modernes,
  `space_dynamic.yaml` pour les orbites modernes, `playfield.yaml` Fixed
  pour les legacy) — marqueur `# Donjons aliens Frontier-FR (15/11)`,
  faction Alien. **Nouvelle partie requise** (les POIs sont générés à la
  création du playfield). Sans `Probability` (clé invalide sur les POIs
  statiques — voir `limites_moteur.md`, contrôle `scan_static_probability`),
  présence garantie par `CountMinMax: [1,1]`.

---

## 5. Coque « hull » : peignable + 10 textures inédites au pinceau

- **Ce que le joueur voit** : les blocs de coque bas de gamme — forme
  « cube » de la famille **« Blocs de construction petits et bon marché »**
  (SS/GV) et **« … grands et bon marché »** (BA/CV) — sont désormais
  **peignables au pinceau texture/couleur** :
  - **petites grilles** : couleurs + textures vanilla (palette 0) ;
  - **grandes grilles** : le pinceau propose **10 textures inédites**
    (ids 296-305, palette 5) — 296/297 vertes, 298/299 grises, 300-305
    **sans couleur** (l'entrée de palette n'en porte pas : le pinceau
    applique la texture seule).
  - l'aspect par défaut reste la coque vanilla (texture 50, teinte 110) ;
  - la palette 5 ne contient **aucune entrée « couleur seule »** : choisir
    une entrée change la texture en même temps que sa couleur.
- **Réglé par** : `BlocksConfig.ecf` — `HullFullSmall` (Id 381) :
  `IsTextureable: true` ; `HullFullLarge` (Id 403) : `IsTextureable: true`
  + `TextureTable: 5`. Sans `IsTextureable`, le pinceau ne fait rien sur ces
  blocs. Les ids 296-305 ne sont proposés par aucune autre palette et ne
  sont utilisés par aucun bloc vanilla (voir `limites_moteur.md`).

## 6. Blocs de POI : recettes pour la DÉCONSTRUCTION (148)

- **Ce que le joueur voit** : en attaquant un POI, il peut **ramasser** les
  blocs/déco (statues, posters, mobilier et conteneurs tribaux/Talon,
  tourelles, sièges SS, cockpits SV, radar, mines…) et les passer au
  **Deconstructor**, qui les découpe en matériaux (facteur 0.5, jusqu'aux
  BaseItems).
- **Ce qui n'est PAS activé** : les recettes de ces blocs ont
  **`Target: ""`** (113 sur 148) — c'est le mécanisme vanilla des recettes
  « déconstruction seule » (`HullDestroyed`, `MarkerBlock`, kits) : elles ne
  sortent dans aucun constructeur. Seules les **statues et posters** (35)
  gardent un `Target` normal et restent craftables.
- **Récupération** : `PickupTarget: <lui-même>` ajouté sur les **148**
  blocs → le bloc revient en inventaire au ramassage/multitool, donc
  déconstructible.
- **Réglé par** : section `# ===== Frontier-FR : blocs rendus craftables
  (18/11) =====` de `Templates.ecf` (148 recettes, mapping
  `docs/recettes_blocs_proposees.csv`) + `PickupTarget` sur chaque bloc de
  `BlocksConfig.ecf`.

## 7. Radar `RadarTracker` : pas de radar de base possible en data

- **Constat** (testé 18/11) : le scan « structures + gisements » du
  détecteur est porté par l'**arme de vaisseau** `DetectorCVWeapon`
  (`IsRadarItem`) : il ne se déclenche que par la barre d'armes d'un
  vaisseau. Sur une base, `Class: TurretManual` fait bien ouvrir le panneau
  tourelle avec F, mais le tir ne déclenche pas le scan (aucune classe de
  device « radar » n'existe).
- **Décision** : `RadarTracker` reste **vanilla** (caché, sans fonction) ;
  pour un radar fonctionnel, le poser sur un **CV** (le bloc y apparaît dans
  la barre d'armes). Le radar décoratif `TurretRadar` reste craftable.

## Journal
- **17/11/2026 (18)** — **Apprentissage réparé (vraie lecture)** : le
  mécanisme précédent ne pouvait pas fonctionner — `AddToGlobalVar` ne
  renvoie **pas** la valeur stockée mais la valeur ajoutée, donc la
  mémoire était relue à 0. Elle est désormais stockée en 15 listes
  d'identifiants lisibles par le jeu (`dbplayer_string`, une par
  catégorie) : ranger un objet à la main puis **APPRENDRE** le mémorise
  réellement, et le tri l'applique **en priorité** sur le classement
  automatique. « OUBLIER la mémoire » efface ces listes.
- **17/11/2026 (17)** — **Apprentissage : corrige les anciennes mémoires** :
  l'option APPRENDRE efface désormais la destination mémorisée d'un objet
  qui se trouve dans le coffre correspondant à son classement automatique.
  Sans cela, une mémoire erronée d'un essai précédent **persistait** et
  renvoyait l'objet vers l'ancien coffre malgré un rangement correct — d'où
  l'impression que l'apprentissage « ne prenait pas ». Rappel de la règle :
  APPRENDRE lit l'état RÉEL des coffres, il faut donc que les objets y
  soient déjà à la bonne place (ou qu'ils y soient mis à la main).
- **17/11/2026 (16)** — **L'apprentissage ne retient que les exceptions** :
  APPRENDRE ne mémorise plus que les **écarts** entre le coffre où vous
  avez rangé un objet et la catégorie que le classement automatique lui
  donne. Conséquence pratique : la mémoire ne contient que vos décisions
  volontaires, et une correction de classement n'a plus besoin d'une purge
  — il suffit de relancer APPRENDRE. « OUBLIER la mémoire » reste là pour
  repartir de zéro.
- **17/11/2026 (15)** — **Médikits et soins enfin en `TRI_Medical`** :
  une régression de l'ordre des règles envoyait tout ce qui porte
  `Ref: FoodTemplate` en **Nourriture** — c'était le cas des médikits,
  bandages et remèdes (`Category: Medical`). La **catégorie explicite
  prime désormais sur le template**. Et comme le log montrait 86 objets
  figés vers `TRI_Nourriture_A` par l'apprentissage, l'option APPRENDRE
  reçoit un second bouton **« OUBLIER la mémoire »** : indispensable
  après une correction de classement, sinon les anciennes destinations
  restent gravées dans la partie.
- **17/11/2026 (14)** — **La console apprend vos rangements** : nouvelle
  option « APPRENDRE mes rangements (coffres TRI_*) ». Elle lit le contenu
  de chaque coffre `TRI_<Categorie>` et **mémorise la catégorie de chaque
  objet** (y compris les blocs et les objets à la classification
  incertaine). Le tri consulte cette mémoire **en priorité** sur le
  classement automatique : rangez un objet douteux à la main dans le bon
  coffre, lancez APPRENDRE, et les fois suivantes il ira tout seul au même
  endroit. Procédure : vider `TRI` dans les bons coffres → APPRENDRE →
  regrouper à nouveau dans `TRI` → TRIER.
- **17/11/2026 (13)** — **Couverture de tri complète + retour visible** :
  les derniers blocs inventoriables non triés sont couverts — les blocs
  de construction *pleins* (`HullFullSmall`, `WoodFull`, `ConcreteFull`,
  `PlasticFull`…) qui n'ont ni `Category` ni `Class`, sont reconnus à leur
  `Mass:` et rejoignent `TRI_Blocs`. Audit final : **0 item et 0 bloc
  inventorable non triés** (les 990 blocs restants sont du terrain pur).
  Enfin, après un tri, les écrans `AFFICHAGE` affichent un **résumé** :
  nombre déplacé et surtout la **liste des coffres manquants**
  (`Sans coffre : TRI_Lingots TRI_Minersis`) — plus besoin du log pour
  savoir quoi créer quand un objet reste dans `TRI`.
- **17/11/2026 (12)** — **Tri des munitions exhaustif** : 99 objets sont
  désormais classés en `TRI_Munitions` — balles, obus de tourelle, charges
  (plasma, laser, ION, railgun), roquettes, grenades, explosifs — sans
  qu'aucune arme n'y reste (et sans arme de tourelle égarée dans les
  munitions). Critère : un nom contenant `Weapon` est une arme ;
  sinon un consommable empilable (`HoldType: 0` + `StackSize > 1`) est une
  munition. Les armures, cellules d'énergie et carburants sont écartés de
  la catégorie « Armes joueur ».
- **17/11/2026 (11)** — **Tri affiné** : les blocs étaient classés dans la
  catégorie de l'**item** portant le même numéro (669 collisions d'ids :
  les sièges passagers tombaient dans « Minerais »). Items et blocs ont
  désormais **deux espaces de clés** (l'item est remappé +8192 au
  runtime, le bloc garde son id). Ajouts : les blocs héritent aussi par
  `Ref:` (sièges rétractables, tourelles — seuls les blocs inventoriables,
  repérés par leur `Mass:`, pour ne pas aspirer le terrain) et les
  projectiles (`SlowRocket`, charges, grenades) rejoignent **Munitions**
  au lieu d'« Armes joueur ». Coût assumé : seuls les items portent un nom
  dans le dictionnaire (les ~860 blocs n'y stockent que leur catégorie,
  sinon la ligne ECF dépassait la limite) — un bloc s'affiche donc par son
  id sur l'écran.
- **17/11/2026 (10)** — **Tri : duplication définitivement corrigée** : le
  log montrait `mv=0` pour chaque objet alors qu'ils arrivaient bien dans
  les coffres — **le retour de `AddItems` vaut toujours 0**. Le tri mesure
  désormais le contenu de la destination **avant/après** l'appel : la
  quantité réellement entrée est retirée de `TRI` par `SetContent`. Même
  traitement pour l'approvisionnement des coffres de craft.
- **17/11/2026 (9)** — **Tri/vente : duplication enfin corrigée** : le log
  (`vus=48 classes=43 deplaces=0 sansCoffre=`) prouvait que le classement
  et les coffres étaient bons, et que seul le **retrait** échouait.
  `IContainer.RemoveItems` ne retire rien sur ces containers (comparaison
  interne silencieusement sans effet). Le tri, l'approvisionnement et la
  vente réécrivent maintenant le contenu avec **`SetContent`** (les piles
  portent leur `slotIdx`, on les réinjecte moins les quantités
  déplacées) : déplacement réel, plus de duplication.
- **17/11/2026 (8)** — **Tri : diagnostic explicite** : le log indiquait
  seulement « 0 items tries », sans dire pourquoi. Il donne maintenant
  `APP-TRI: vus=N classes=M deplaces=K sansCoffre=<coffres manquants>` :
  `vus` = piles lues dans `TRI`, `classes` = piles reconnues par le
  classement, `sansCoffre` = **noms de containers à créer** pour que le
  tri puisse agir. C'est le cas quand les coffres existants portent les
  anciens noms (`TRI_Food`, `TRI_Ingredients`…) au lieu des
  sous-catégories actuelles (Nourriture, Minerais, Lingots…).
- **17/11/2026 (7)** — **Boutiques : montants affichés, ×MAX corrigé,
  bouton retour au hub** : (1) chaque page d'objet affiche désormais
  **le disponible chez le marchand**, votre crédit et **le montant de la
  dernière opération** (« Dernier achat / Dernier gain ») ; la vente du
  container `VENTE` affiche **le montant reçu** en plus du nouveau solde.
  (2) Bug corrigé : le champ de saisie était porté par la page de l'objet,
  donc **×MAX réclamait aussi un nombre et n'achetait rien** — la saisie
  est désormais sur une page dédiée. (3) Un bouton **« Retour au hub »**
  est présent sur chaque page d'objet et sur la page de saisie.
  Précision sur le stock : c'est un **compteur d'achats du cycle**
  comparé au stock du `TraderNPCConfig`, remis à zéro au réapprovisionnement
  — un stock « restant » stocké tel quel aurait valu 0 au premier passage
  et bloqué tout achat.
- **17/11/2026 (6)** — **Stock réel à l'achat + aide commerce visible** :
  (1) l'achat, désormais par saisie libre, est **plafonné au stock du
  marchand** (colonne « stock » du TraderNPCConfig), remis à niveau à
  chaque réapprovisionnement du cycle — sinon on pouvait acheter sans
  limite avec le seul crédit (cheat) ; le ×MAX est plafonné de la même
  façon. (2) L'option **AIDE de la console commerce** n'apparaissait pas :
  les options du menu étaient numérotées 1, 2, 8, 9 — un trou dans la
  numérotation suffit au moteur pour s'arrêter avant l'aide. Elles sont
  maintenant **contiguës** (1, 2, 3 AIDE, 4 Quitter).
- **17/11/2026 (5)** — **Correctif : le tri dupliquait les items** : les
  objets arrivaient bien dans les coffres `TRI_<Catégorie>` mais
  **restaient aussi dans `TRI`** (copie au lieu de déplacement). Cause :
  `IContainer.RemoveItems` n'est pas symétrique de `AddItems` — il compare
  l'identifiant interne des piles, qui diffère de celui qu'on lui passe
  (même décalage +8192) ; le retrait échouait donc en silence. Le tri,
  l'approvisionnement et la vente du container `VENTE` utilisent désormais
  un **retrait mesuré** : comptage avant/après, nouvelle tentative avec
  l'autre forme d'id, et la destination ne garde que ce qui a réellement
  quitté la source. Plus de duplication possible.
- **17/11/2026 (4)** — **Achat/vente par saisie de quantité (fini les
  paliers)** : sur chaque objet du catalogue, les options ×1 / ×5 / ×25 /
  ×100 / ×1000 sont remplacées par **« saisir la quantité »** (champ de
  saisie du dialogue, quantité automatiquement limitée au crédit/budget
  restant à l'achat, au stock possédé à la vente) — l'option **×MAX** est
  conservée. Effet de bord majeur : **-18 460 nœuds de dialogue (-77 %,
  23 897 → 5 437)**, puisque chaque palier coûtait deux états et une
  méthode C# compilée par objet — c'est ce qui figeait le jeu plusieurs
  secondes à la première ouverture des consoles. Le dialogue passe de
  15 Mo à 6,5 Mo.
- **17/11/2026 (3)** — **Appro auto + aide commerce + messages
  d'attente** : (1) option **AUTO toutes les 5 minutes** sur
  l'approvisionnement (boucle `CallLater` chaînée, option STOPPER, le
  préfixe de tri via un miroir mémoire car un callback n'a pas accès aux
  variables de dialogue) ; (2) **guide HTML de la console
  commerçante** (option AIDE sur les consoles T1 et T2 : recettes,
  budgets, licences, achat/vente, container VENTE —
  `SharedData/Console_Commerce_Aide.html`) ; (3) les ouvertures d'aide
  passent par un **état intermédiaire « patientez »** (la fenêtre HTML
  s'ouvre pendant que le joueur lit le message — plus d'impression de
  plantage) et les hubs des trois consoles affichent la mention
  « première ouverture : patientez (compilation) ».
- **17/11/2026 (2)** — **Approvisionnement automatique des coffres de
  craft (option APPROVISIONNER)** : containers nommés `APPRO_<Item>`
  (maintenus à 1000 unités) ou `APPRO_<Item>_Qté`
  (`APPRO_CopperIngot_500`) constamment réapprovisionnés depuis les
  coffres `TRI_<SousCategorie>` correspondants, à hauteur du manque
  uniquement. Pensé pour alimenter un constructeur dédié (munitions…).
  Le lancement du craft, lui, n'est pas automatisable (aucune API dans
  le compilateur dialogue — vérifié en source) : lancer la production
  avec une quantité élevée ×N reste manuel, l'option APPRO recharge
  l'entrée entre deux passages. Le dictionnaire est réparti sur 5 nœuds
  (lignes 10,0-10,5 Ko).
- **17/11/2026** — **Fenêtre d'aide dans le jeu (option AIDE)** : la console
  d'atelier ouvre une page HTML (`SharedData/Console_Aide.html`, chargée via
  `%SHARED_DATA%` — chemin relatif au scénario, donc embarqué au Workshop)
  qui détaille toute la procédure : nommage des écrans LCD (`AFFICHAGE`,
  `AFFICHAGE_<coffre>`), défilement, sondage, tri, et le **tableau complet
  des 15 containers à créer** avec le contenu de chacun et le nombre
  d'items concernés (généré depuis les configs, donc toujours à jour). Le
  fichier est régénéré par le bouton Codex > Marchands.
- **16/11/2026 (11)** — **Console d'atelier (APPS)** : nouveau bloc
  craftable `Frontier_Console_Atelier` (Id 207, recette 5 électroniques +
  10 plastique) portant l'arbre `Frontier_AppAtelier` avec deux apps
  générées : (1) **RAFRAÎCHIR l'écran** — affiche le contenu du container
  « SONDE » sur l'écran LCD nommé « AFFICHAGE » (noms + quantités, 18
  lignes max) ; option **SONDER par nom** — l'écran affiche n'importe
  quel container **nommé** de la structure (saisie clavier dans le
  dialogue, champ `Input` du state). Affichage au format
  `Nom xQté` (**nom localisé dans la langue du jeu** : la clé de
  Localization.csv est le nom interne de l'item, résolu par `Loc()` ;
  repli sur le nom interne si aucune traduction n'existe ; l'id n'est
  affiché que s'il n'y a aucun nom connu — tous les items en ont un,
  licences comprises, en forme courte `Licence_Talon`), **tous les
  écrans LCD nommés `AFFICHAGE*`** affichent la
  même page, et le contenu **défile automatiquement** (page toutes les
  5 s, boucle infinie relancée par
  RAFRAÎCHIR — la boucle s'arrête seule si les écrans/container
  disparaissent) ; **chaque écran peut suivre SON coffre** :
  `AFFICHAGE_<NomDuCoffre>` affiche le container de ce nom
  (`AFFICHAGE_CaisseFer` → `CaisseFer`), l'écran nommé `AFFICHAGE` seul
  affichant le dernier coffre sondé (`SONDE` par défaut) — plusieurs
  coffres donc visibles **en même temps**, tous pilotés par une seule
  console ; **tri ventilé par sous-catégorie** (option LISTER pour voir
  les noms de coffres à créer) : Minerais (`Ref: OreTemplate`), Lingots
  (matières raffinées : …Ingot/Bar/Rods/Powder…), Composants, Plantes,
  Nourriture, Medical, **Armes joueur**, **Munitions** (…Ammo/
  …Shells/Bullet, les obus de tourelle compris), Déco, **Armes
  vaisseau**, Devices, Blocs, Farming, Marchandises, Divers
  (**1 093 ids routés** : 92 % des items ; les 69 licences sont exclues
  par choix et restent dans TRI, et les blocs non routés sont le terrain
  — Air/Rock/Grass/Sand/Dirt — qui n'entre jamais dans un coffre). Le
  **tier** des armes (T1/T2/Épique) est un item distinct : il suit l'id
  et survit au tri ; seule la variante `meta` (jetons, non routés)
  serait perdue. Pas de transfert de piles complètes (`SetContent`) :
  il n'apporterait rien ici ; (2)
  **TRIER le coffre « TRI »** — ventile son contenu vers des containers
  nommés `PREFIXE_<SousCategorie>` ; ce qui n'a pas de coffre de
  destination reste dans TRI. **Coffres multiples par catégorie** : le
  tri parcourt TOUS les containers nommés commençant par ce préfixe
  (TRI_Lingots, TRI_Lingots_A, TRI_Lingots_2… ordre alphabétique) et
  remplit dans l'ordre avec débordement automatique (`AddItems` renvoie
  ce qui rentre). Le **préfixe est modifiable en jeu** (option CHANGER
  le prefix, var globale `Frontier_Tri_Pref`, défaut TRI) et l'option
  LISTER affiche sur l'écran les noms de coffres à créer. Lier les blocs
  **par leur NOM** dans sa structure. Le bouton Codex > Marchands
  régénère aussi les APPS (734 ids routés). **À valider en jeu** :
  compilation de la ligne générée (~15 Ko — si elle échoue, l'arbre
  atelier seul est perdu, les commerçants sont un autre arbre),
  affichage LCD réel, tri réel avec débordement, saisies.
- **16/11/2026 (10)** — **Les commerçants échangent TOUT leur catalogue
  vanilla, blocs compris** : le générateur ne filtrait le catalogue que
  sur l'ItemsConfig — les blocs que les traders vanilla achètent/vendent
  (HumanNPCBlocks, AlienNPCBlocks, GrowingPotConcrete,
  ForcefieldEmitterBlocks…) étaient rejetés (122 entrées perdues). Le
  mapping noms/prix/ids couvre désormais aussi le BlocksConfig
  (`MarketPrice:` des blocs sert de base aux prix `mf=` ; id BlocksConfig
  dans le Dictionary du container VENTE, l'item homonyme restant
  prioritaire). Les licences restent hors catalogue (vente dédiée 1 M cr
  chez le commerçant lui-même). **Rescan** : le bouton « Régénérer les
  consoles commerçantes » (Codex > Marchands) relit
  TraderNPCConfig/ItemsConfig/BlocksConfig et reconstruit la console en
  mode fusion — après toute modif du catalogue, cliquer, déployer en
  prod, relancer le jeu (la console ne peut pas se régénérer en jeu :
  ses options sont compilées au chargement du scénario). Stats : 122
  entrées récupérées, ~2 450 nœuds de plus (23 363 au total).
- **16/11/2026 (9)** — **Vente container réparée (cause du « ne vend
  rien »)** : le log 162011 révèle que la fonction C# de la (8)
  n'a **jamais compilé** — `vendus`/`total` utilisés sans déclaration
  (CS0103), l'état `Frontier_TraderHub2` entier rejeté, et chaque échec
  inondait le log de « Cannot process 'DialogOption' » (324 lignes PDA).
  Correctif : compteurs déclarés dans le générateur, régénéré + déployé
  prod (md5 identiques). Nouveau contrôle prelaunch
  (`scan_dialogue_vars`, erreur) + test pytest. **Deuxième couche
  trouvée en jeu** (compilation réparée, la fonction tourne : traces
  visibles) : le moteur remappe les ids d'inventaire des items du
  scénario **+8192** (stack 8416 = IronIngot 224) — le Dictionary de
  prix ne matchait jamais. Correctif : lookup double
  `item.id` / `item.id - 8192` dans le générateur, redéployé prod.
  **Reste à valider en jeu** : stacks vendus > 0 au prochain test.
- **16/11/2026 (8)** — **« Container de vente » sur la console T2** :
  nouvelle entrée du menu T2 — « VENDRE le container « VENTE » ». Le
  joueur nomme un container de sa base « VENTE », y met ce qu'il veut ;
  l'option vend **tout ce qu'au moins un commerçant activé achète** (au
  meilleur prix d'achat parmi eux), le reste reste dans le container.
  Implémentation : fonction C# générée dans l'état dialogue (pattern
  RE2-FR prouvé en jeu : `LocalStructure.GetDevice<IContainer>('VENTE')`
  + `GetContent()` + `RemoveItems(id, qté)`, chaîne mono-ligne avec
  séparateurs `<nl>` et apostrophes C#), prix par Id d'item (Dictionary
  int→int généré depuis les catalogues des commerçants, items à meta
  exclus v1). Prelaunch = 6 erreurs baseline, prod synchrone. Fonctionne
  sur les bases existantes (dialogues relus du scénario à chaque session).
- **16/11/2026 (7)** — **Vente partielle/×MAX + noms traduits dans les
  consoles** : (1) la VENTE passe aux options exécutées directement avec
  quantité **clampée au stock réel** via `GetItems()` — cliquer ×5 avec
  3 en stock vend les 3, silencieusement ; **×MAX = tout le stock** ;
  (2) les noms affichés sont **traduits** : le générateur lit la
  Localization (vanille `Content/Extras/Localization.csv` puis celle du
  scénario, prioritaire) — FR sinon EN sinon nom interne ; les 27 items
  craftables de FF apparaissent avec leurs noms (entrées ajoutées à la
  Localization du scénario au fil des ajouts). Les états intermédiaires
  ck/okn de la vente sont supprimés (les options ×N exécutent et
  re-affichent le menu de quantité). Dialogue interne dans la vente :
  variable `qs_<commerçant>_s<idx>` déclarée par état (unique, règle
  CS0102). Le nombre de nœuds dialogue passe de 38 794 à ~21 000 (les
  états ck/okn par quantité supprimés). Achats inchangés (×MAX crédit
  déjà en place). Prod synchrone, prelaunch = 6 erreurs baseline.
- **16/11/2026 (6)** — **Deuxième couche du bug de compilation dialogues
  corrigée** : après dédoublonnage des variables, le ×MAX échouait en
  CS0266 `double → int` — `Player.Credit` est un **double** (docu :
  `Player.Credit += 1.1`), la division produit un double affecté à des
  variables int. Correctif : cast explicite `(int)(Player.Credit / px)`
  dans les 1600 scripts ×MAX (générateur). Le ×MAX est conservé (pas
  supprimé). Prelaunch = 6 erreurs baseline, prod synchrone. Le duo
  pièges-compileur dialogue : doublons de déclarations (CS0102) +
  conversions implicites (CS0266) — le compilateur est un vrai csc, tout
  le C# s'applique (casts, types).
- **16/11/2026 (5)** — **Compilation des dialogues console réparée** :
  à l'appui sur F, `Error compiling dialogue logic in state
  'Frontier_TraderHub2'/'Frontier_TraderHub'` — CS0102/CS0229 sur des
  champs `q`/`rem` : le compilateur dialogue génère **une classe par
  arbre** et déclare un champ par Variable de chaque état SANS
  dédoublonner — les ~800 états de quantité (Tq) déclaraient tous
  `q`/`rem` → centaines de doublons → compilation morte (consoles
  inutilisables). Correctif : variables **uniques par état** dans
  `console_traders.py` (`q_<commercant>_<cat><item>`,
  `rem_<...>`) ; vérifié 0 doublon interne par arbre (1605
  déclarations/arbre, 0 collision). `EnableTrading: All` inchangé.
  Le bug datait de l'ajout du ×MAX (14/11) : il ne se révèle qu'à
  l'appui sur F sur une console (compilation à la première utilisation).
  Prelaunch = 6 erreurs baseline, prod synchrone. Nouvelle partie
  requise.
- **16/11/2026 (4)** — **Crash « ECF config Template contains too many
  child levels in line 6097 » corrigé** : la suppression des 35 accolades
  `}` orphelines avait révélé le vrai déséquilibre — des templates dont le
  `}` fermant avait été avalé dans les retraits précédents (profondeur
  cumulée, le jeu avorte TOUT Templates.ecf). Réparation par rewriting
  profondeur (fermer avant chaque nouveau template, jeter les `}`
  orphelines) : 556 templates parsés, T2 + 27 recettes indexés. Nouveau
  contrôle `brace_depth` dans engine_loaders (profondeur finale ≠ 0 ou
  > 3 = erreur) + test pytest (68 verts, ruff 0). Le parseur du projet
  tolérait ce que le jeu jette — d'où les prelaunch « verts » précédents.
  Prod synchrone. Nouvelle partie requise.
- **16/11/2026 (3)** — **Une seule console T2 (fini les 69 variantes)** :
  les 69 T2 partageaient déjà le même dialogue (Frontier_TraderHub2) qui
  contient « Activer un commerçant » avec **filtrage auto sur les licences
  tenues** (`HasItem` par commerçant, pagination 5 pages) et consommation
  à l'activation (`RemoveItem` + bitfield). Les 68 variantes redondantes
  supprimées (BlocksConfig + Templates + Localization, Ids 138-205) ;
  reste T1 (Id 136) + T2 (Id 206). Recette T2 simplifiée : 5 T1 + 20
  reliques (les licences se consomment à l'activation, 1 par commerçant).
  `console_traders.py` mis à jour (regen ne recrée plus les variantes ;
  nettoyage des anciennes recettes suffixées). **Régression trouvée et
  réparée au passage** : 35 accolades `}` orphelines (résidus des retraits
  par blocs) faisaient s'arrêter le parseur ECF après le template T1 —
  tous les templates suivants (27 recettes + T2) étaient morts dans le
  jeu ; parse vérifié 556 templates, T2 et recettes indexés. Dev = prod,
  prelaunch = 6 erreurs baseline. Nouvelle partie requise.
- **16/11/2026 (2)** — **POIs mission Talon d'Akua qui ne spawnaient plus**
  (`10 of 72 POIs could not be placed` : AkuaTalonMission/Archery/
  GuardTower + farms + TalonWood, contre 1 of 70 baseline) : les 2 donjons
  d'Akua, sans contrainte, se posaient dans la zone du cluster Talon
  (Faction Alien bloque 1200 m autour, cf. commentaire du POI mission).
  Correctif = pattern corpus (CNTRL_IsInfected) : `Territory: False` +
  `SpawnPOIAvoid: [ START ]` + `SpawnPOIAvoidDistance: 3000` sur les 198
  blocs des 99 statics. **`SpawnPOIAvoid` est ABSOLU** (SpawnPOINear n'est
  qu'une suggestion, cf. commentaire corpus). Rappel : les 40 erreurs
  `Did not find a position in space for POI using RadialInfo` à la création
  = fallback random NON fatal (donjons spatiaux spawn en position random,
  fonctionnel). Nouvelle partie requise. Prelaunch = 6 erreurs baseline.
- **16/11/2026** — **27 items rendus craftables + déconstructibles**
  (recettes 100 % FF-native, marqueur `Frontier-FR : items rendus
  craftables + deconstructibles` en fin de Templates.ecf, dev = prod
  653 templates) :
  - **Marchandises vendables** (inputs chers, pas d'imprimante à
    crédits) : Leather (5 RaptorMeat), Liquors (10 Grain + 5 WaterJug),
    Filters, Fertilizer, TexturedPlantProtein (20 PlantProtein),
    Narcotics, MutatedSubstance (10 ToxicWaste), Optronics, Robotics,
    ScienceEquipment, TechnicalArtifact (2 AncientRelics + Neodymium +
    Electronics, AdvC), LuxuryGoods (10 GoldIngot + OpticalFiber +
    Plastic, AdvC) ;
  - **Props de combinaison** : ArmorBoost, JetpackBoost, OxygenBoost,
    RadiationBoost, MobilityBoost, MultiBoost (AdvC), InsulationBoost
    (Silicium + fibre optique + nanotubes + or), TransportationBoost,
    TransportationBoostEpic (10 Erestrum + 10 Zascosium + nanotubes) ;
  - **Kits d'upgrade épiques** : Detector CV/HV (Néodyme 10 + Erestrum/
    Zascosium 5), WarpDrive CV (180 s, Erestrum+Zascosium+Nanotubes+15
    Electronics), Teleporter BA (15 Néodyme + 10 Sathium) ;
  - **Food processor** : Beer (10 Grain + 5 WaterJug → 2),
    NaturalStimulant (NutrientSolution + 8 HerbalLeaves).
  Déconstructibles par défaut (pas de DeconOverride: Stop). Une tentative
  d'import de templates RE2-FR a été abandonnée sur décision utilisateur
  (recettes 100 % FF-native) et retirée immédiatement. Prelaunch = 6
  erreurs baseline dev et prod.
- **15/11/2026 (23)** — **Pool planète = groupes « Abandoned » uniquement**
  (demande utilisateur, liste des groupes issue du mapping
  `…rontierFR`) : Donjon 1 = `AbandonedPOI` (10 variantes intégrées :
  bunker, mine, usine, réacteur, dépôt…), Donjon 2 = tiré parmi 13 autres
  groupes abandoned (AbandonedMissileBase, AbandonedDojo,
  AbandonedFactory, AbandonedMine, FarrAbandoned, TOTAbandonedDronebase,
  TOTMineralLab, TOTVesselYard, TOTWorkshop, AbandonedSnow, DeepMineStory,
  Akua/MasperonMissionAbandonedBase). 91 statics, prod synchrone,
  prelaunch = 6 erreurs baseline. Espace inchangé.
- **15/11/2026 (22)** — **Deux régressions de la réinsertion stat corrigées
  + RadialInfo recentré** : (1) Melago/Cothga étaient retombés dans
  `FixedPlayerStart:` (l'ancre « premier item après POIs: » retombe dans
  FixedPlayerStart quand `Random:` est vide — audit scopé : 0 autre cas) ;
  (2) les centres RadialInfo décalés sur les planètes ne fonctionnent pas
  (`Did not find a position in space for POI using RadialInfo` ×40, le jeu
  replace aléatoirement) — retour au centre `[0, 0, 0]` rayon 3.5–4.5
  standard. Placement final : aléatoire dans la sphère d'orbite, repérable
  par `Discovery: False` + `MapDistance/HudDistance 4000`. Prod synchrone,
  prelaunch = 6 erreurs baseline, validations scopées = 0 anomalie.
- **15/11/2026 (21)** — **Pool donjons remplacé : vrais prefabs volumineux**.
  Les epb du premier pool étaient des STUBS vanilla (BA_AlienWatchtower1 =
  2,2 Ko, contenu dans les bundles du jeu) → `Blueprint 'X' problem: no
  data (yet)` et structures jamais matérialisées en espace. Nouveau pool :
  6 donjons avec de vraies données locales (70-130 Ko) — Palais de
  l'Impératrice Zirax, Forteresse Xenu T4, avant-poste Xenu orbital, cité
  capitale Zirax, conseil des Anciens, corrupteur Legacy — GroupName =
  nom de fichier (mécanisme prouvé par Santa/XyFortress). Faction Alien +
  couleur magenta conservés. Constaté aussi : le corps des POIs spatiaux
  = classe POIDesc (Poidata.cs n'a que planète) — toutes les clés y sont
  valides. Prod synchrone (178 fichiers), prelaunch = 6 erreurs baseline,
  0 erreur PyYAML, 175 playfields complets.
- **15/11/2026 (20)** — **Donjons spatiaux qui disparaissaient à
  l'approche** : le rayon `RadialInfo` du corpus (1.5–2) place les POIs
  DANS le volume de la planète rendue au centre du secteur d'orbite
  (rayon planète ~2500-4000) — le jeu les supprime à l'approche. Rayon
  passé à 3.5–4.5 (altitude d'orbite) sur les 158 blocs. Prod synchrone,
  prelaunch = 6 erreurs baseline. Pool donjons = 7 prefabs variés tirés
  par playfield (pas « les 2 mêmes »).
- **15/11/2026 (19)** — **Placement des donjons spatiaux près des
  planètes** : les 8 secteurs multi-planètes (Crown Sector, Symos,
  Arkenia, Nyxia, Krichanda, Vanara II, Tavos, Arkenia Racing) avaient
  leurs donjons au CENTRE du secteur alors que les planètes sont à des
  offsets ±5600-12600 — le joueur décollant d'Akua n'était pas à côté.
  Centres RadialInfo calés sur 2 planètes par secteur (ex. Crown Sector :
  près d'Akua et de Ningues). Prod synchrone, prelaunch = 6 erreurs
  baseline. Fonctionnement EVO rappelé : les planètes starter n'ont pas
  d'orbite séparée — voler au-dessus d'Akua = rester dans GS_Akua ; le
  secteur spatial du système est Crown Sector.
- **15/11/2026 (18)** — **Trouvabilité des donjons spatiaux** : ajout
  `MapDistance: 4000` + `HudDistance: 4000` aux 158 blocs espace (le
  marqueur map/HUD devient visible de loin — sans lui le donjon spawne
  quelque part dans le secteur sans repère). Résidus d'indentation du
  patch précédent corrigés (0 erreur PyYAML sur les 79 fichiers espace).
  Prod synchrone, prelaunch = 6 erreurs baseline.
- **15/11/2026 (17)** — **Visibilité des donjons spatiaux + nettoyage
  Story_*** : ajout `Discovery: False` (POI visible immédiatement sur la
  map du secteur — sans lui le marqueur n'apparaît qu'après découverte)
  et `DisplayName: Donjon alien N` aux 158 blocs espace. Les 13 orbites
  Story_*Orbit nettoyées des fragments de la passe boguée (exclues des
  donjons). Réécriture littérale des 79 fichiers espace (0 erreur PyYAML,
  175 playfields complets, prod synchrone, prelaunch = 6 erreurs baseline).
  Rappel : BLTAA 36439 I = système généré procéduralement (RandomPresets),
  hors périmètre des donjons.
- **15/11/2026 (16)** — **Réparation de l'insertion Position** : le script
  d'ajout de `Position: RadialInfo:` sautait les lignes de l'entrée
  (Type/Name/Faction/CountMinMax) et dupliquait des fragments →
  `Expected 'SequenceStart', got 'MappingStart'` à la création de partie
  (Templates/Omicron Sector). Fragments retirés, entrées complètes
  réinsérées dans les **79 orbites** (13 de plus couvertes au passage) =
  158 donjons spatiaux. 0 erreur PyYAML, 175 playfields complets, prod
  synchrone, prelaunch = 6 erreurs baseline.
- **15/11/2026 (15)** — **Donjons spatiaux qui ne spawnaient pas** : les
  POIs d'orbite exigent `Position: RadialInfo:` (le corpus l'a sur toutes
  ses entrées qui spawnent) — ajouté aux 158 blocs espace des 79 orbites
  (prod synchrone, prelaunch = 6 erreurs baseline). Les orbites déjà
  visitées dans une sauvegarde ne les auront pas (structures sauvegardées).
- **15/11/2026 (14)** — **Derniers placements corrigés + validation
  exhaustive** : Melago et Cothga (Random: vide → blocs tombés dans
  FixedPlayerStart → `GroupName not found on PlayerStartData` à la
  création de partie) déplacés dans Random:. **Validation exhaustive des
  6 classes de pannes sur les 175 fichiers : 175/175 valides** (PyYAML
  strict, placement, Faction: Alien, noms internes, clés interdites par
  famille, indentation — règle moteur : corpus moins indenté que le
  premier item = fatal, plus indenté = toléré, prouvé en jeu 08:54).
  Prod synchrone, prelaunch = 6 erreurs baseline.
- **15/11/2026 (13)** — **Nettoyage complet des fusions résiduelles** :
  3 passes successives (76 paires MapMarker/Neutral au milieu des listes
  Properties, 46 fichiers avec indentations à corriger, 1 bloc avec
  `Properties: # commentaire` non reconnu). Critère final : **0 erreur
  PyYAML** sur les 175 fichiers modifiés (hors tabs/quirks préexistants
  du corpus), prelaunch = 6 erreurs baseline dev et prod.
- **15/11/2026 (12)** — **Corpus réparé** : le retrait du `MapMarker` par
  replace global avait avalé les `Key: MapMarker / Value: Neutral` du
  CORPUS (1267 lignes fusionnées dans 124 fichiers — la base FF utilise
  MapMarker: Neutral sur ses propres POIs) → `did not find expected key`
  au chargement. Fusions inversées mécaniquement (indent T = 3×ip−2 /
  2×ip+2 → lignes MapMarker/Neutral restaurées), 0 fusion restante, 0
  anomalie Properties. Prod synchrone, prelaunch = 6 erreurs baseline.
- **15/11/2026 (11)** — **Réparation du retrait MapMarker** : la
  suppression par replace à indent fixe avait laissé des lignes fusionnées
  (indent 28) dans les 350 blocs → `did not find expected key` à la
  sélection. Blocs réécrits proprement (Properties: + `- Key: RegenAfter`
  à l'indent correct). Prod synchrone, prelaunch = 6 erreurs baseline.
- **15/11/2026 (10)** — **Couleur magenta des donjons** (mécanisme RE2-FR
  identifié : override `Content/Configuration/Factions.ecf` du scénario,
  `Color: "1, 0, 1"` sur la faction Alien — vanilla = blanc). `MapMarker:
  Neutral` retiré des 350 blocs (il écrasait la couleur de faction en
  blanc). Prod synchrone, prelaunch = 6 erreurs baseline.
- **15/11/2026 (9)** — **Consolidation complète du lot donjons** : blocs
  supprimés puis réinsérés au propre (ancre `POIs:`, indent du corpus,
  `GroupName` = nom interne, faction **Alien**, `MapMarker: Neutral` —
  marqueur jaune neutre comme RE2-FR). Blocs des 2 legacy en sous-section
  Random (Inst_Moon, LavaEndPlanetOcean) convertis au style GroupName.
  Corpus réparé : 7 entrées dont la faction avait été basculée par erreur
  pendant les passes de couleur (ZiraxDroneBaseT2, 6 × DroneBaseT1/
  CrashedShip). 350 donjons / 175 playfields, dev = prod (octet-pour-
  octet), prelaunch = 6 erreurs baseline.
- **15/11/2026 (8)** — **Marqueurs des donjons colorés** : faction Alien →
  **Zirax** dans les 175 playfields (comme RE2-FR ; Alien = marqueurs
  blancs, Zirax = rouges). Prod resynchronisée, prelaunch = 6 erreurs
  baseline. Nouvelle partie requise pour les playfields déjà générés.
- **15/11/2026 (7)** — **POIs qui n'apparaissaient pas corrigé** : le
  `GroupName` doit être le **nom interne du blueprint** (header du .epb),
  pas le nom du fichier — `BA_AlienWatchtower1.epb` s'appelle en interne
  `AlienWatchtower`, etc. 328 références renommées dans les 164 fichiers
  (les donjons legacy `Prefab:` = nom de fichier, inchangés). Log :
  `No BP group 'BA_AlienWatchtower1'` + POI silencieusement non placé.
  Plusieurs epb à nom interne identique = variété vanilla. Nouvelle
  partie requise (playfields déjà générés sans les donjons).
- **15/11/2026 (6)** — **Crash à la création de partie (Gourtex) corrigé** :
  les 2 donjons de Bro1_Gourtex_Planet avaient été insérés dans
  `DroneBaseSetup: Random:` au lieu de `POIs: Random:` (le static du SoS
  indente son POIs Random à 2 crans — le script cherchait 4) →
  `CountMinMax not found on RandomDroneBaseDataDeprecated` dans
  Templates/Gourtex de la sauvegarde. Déplacés au bon endroit (audit
  top-level des 175 fichiers : 1 seul fautif), prod resynchronisée,
  prelaunch = 6 erreurs baseline.
- **15/11/2026 (5)** — **Indentation des blocs POIs corrigée** (Inst_Moon,
  LavaEndPlanetOcean) : blocs insérés à 10/12 crans dans un corpus à 8/11
  → `did not find expected key` au chargement (YamlDotNet verrouille
  l'indent de la séquence sur sa première entrée). Réalignés sur le
  corpus, prod resynchronisée (175 fichiers), prelaunch = 6 erreurs
  baseline. Pas de contrôle automatique possible : le corpus mélange
  lui-même les indents (189 pseudo-violations tolérées par le jeu).
- **15/11/2026 (4)** — **3 playfields legacy réparés** (GS_Ashon2Orbit,
  LavaStarterOrbit, SpaceEmpty) : un nettoyage de la session avait écrasé
  leur playfield.yaml par le contenu de fichiers voisins (backups centraux
  sans nom de fichier — restauration par « dernier .bak » fautive) ; crash
  à la sélection (`did not find expected key`, ligne 5821). Restaurés
  depuis les backups pré-insertion identifiés par signature de contenu,
  donjons réinsérés. LavaEndOrbit vérifié intact. dev = prod (175
  fichiers octet-pour-octet), prelaunch = 6 erreurs baseline.
- **15/11/2026 (3)** — **Crash à la sélection du scénario corrigé** :
  `Probability: 1` ajouté dans les POIs des playfield_static (clé absente
  de `PoiData.RandomPoiData` — la vanille n'en a aucune) → retiré des 96
  statics (dev + prod resynchronisées), nouveau contrôle
  `scan_static_probability` (erreur prelaunch) + 2 tests pytest.
  Prelaunch = 6 erreurs baseline inchangées.
- **15/11/2026 (2)** — **350 donjons aliens ajoutés** (entrée 4) : 2 POIs
  aliens minimum par playfield jouable (175 playfields : planètes, lunes,
  orbites, champs d'astéroïdes) — pool de 7 prefabs locaux (tours alien
  BA_AlienTowerV2a/V3a/V4a, BA_AncientTemple, BAF_XenuShrine,
  BA_AlienWatchtower1/2), tiré par playfield (varie), faction Alien,
  Random garanti (Probability: 1, CountMinMax: [1,1]) sur les modernes,
  Pos fixes sur les legacy. Exclus : GasGiant (pas de surface), Sun*,
  SpaceWarpTarget* (portes), Story_* (scènes scriptées). Prelaunch =
  6 erreurs baseline inchangées dev et prod. Nouvelle partie requise.
- **15/11/2026** — **Système Shadows of Starlight intégré** (entrée 3) :
  13 playfields Bro1_* + 46 prefabs .epb copiés depuis le scénario
  officiel SoS, secteurs legacy convertis en système EVO ajouté au
  Sectors.yaml (dev + prod synchrones). Aucune collision de nom ;
  prelaunch = 6 erreurs baseline inchangées (Melago sans ressource =
  design SoS). PDA SoS et TraderNPCConfig SoS non importés.
  **Correctif en jeu le même jour** : crash au warp vers le système
  (secteurs d'arrivée `SpaceWarpTarget` manquants) — 6 secteurs ajoutés
  autour du soleil, nouveau contrôle `scan_sun_warp_targets` (erreur
  prelaunch) + 2 tests pytest.
- **14/11/2026** — **Empyrion 1.20.1 (build 5232)** : patch mineur — aucun
  changement config/playfield/traders (Frontier-FR reste aligné) ; nos Ids
  blocs 136-205 et items 1411-1479 restent libres. Changelog officiel :
  fix BlockValue sur les Ids 4096-6143 (Eleon corrige progressivement la
  gestion des Ids > 2048 — notre choix d'Ids < 2048 reste le bon), retrait
  du template FireExtinguisher du DM-EXP (CoQ du Testing Grounds le
  demandait ; notre PDA n'y référence pas — template conservé chez nous, il
  est en plus « decon only »), fix kicks/bans sur changement de slot, fixes
  EAH. StructureLight absent de notre gameoptions.yaml (optionnel).
  Règles moteur confirmées sur 5232 déobfusqué (voir fiche
  `maj-1-20-delta`).

- **14/11/2026** — **Nettoyage du log client** : 13 activations de chapitre
  PDA mortes (`ChapterActivation` avec `Check: NearPoi/DialogOption` sans
  `Names:` ni `Types:` — jamais déclenchables, spam 1 821 + 104 erreurs
  `CAA_*_T:-_N:-` par session) supprimées ; `pda_iq048SO` remplacé par la
  vanille (le `Names: All_Debug_Help_Init` avait été perdu à l'import).
  591 activations valides, yamlcheck/prelaunch au vert, prod sync.
  **Nouveau contrôle prelaunch** : `scan_pda_activations` (warning) signale
  toute activation sans cible.
- **14/11/2026** — **StructureLight activé** dans `gameoptions.yaml`
  (dev+prod) : éclairage de structure « baked » de la 1.20 — chaque
  structure reçoit un volume de lumière précalculé (ciel, torches, lampes).
  `false`/absent = lumières temps réel comme avant. **Nouvelle partie
  requise** (les gameoptions sont copiées dans la sauvegarde à la création).
- **14/11/2026** — **Console commerçante v2 (option B)** : les bornes
  TraderNPC posables abandonnées (limite moteur, entrée 1b) ; remplacées
  par la console à dialogues `Frontier_Console_Commercant` (Id 136,
  modèle PlayerConsole, dialogue hub `Frontier_TraderHub`) — activation
  par licence consommée, boutiques achat/vente générées pour les 69
  commerçants (800 refs achat / 404 vente ; fenêtres quantité
  ×1/×5/×25/×100/×1000 (+×MAX achat) avec confirmation ; budget
  d'approvisionnement 500 000 cr/cycle par joueur, reapro 1 h ; 154 lignes de stock ignorées = items
  non-ItemsConfig ; UI dialogue : 12 options affichables max, pas
  d'icônes ni de colonnes possibles). prelaunch dev = prod = 6 erreurs baseline ;
  sync prod vérifiée md5 (6 fichiers). **À valider en jeu** : pose de la
  console, menu, activation, achat/vente.
- **14/11/2026** — **Réintégration vanille intégrale des playfields** :
  les 21 playfields static + dynamic GS_Akua remis au niveau de la base
  vanilla `Content\Playfields\` (le DM vanilla est un canevas sans POIs
  de faction — GS_Akua 9 POIs vs 35 ; mission Talon AkuaTalonMission).
  md5 : dev = prod = base vanilla. Backups :
  `C:\Dev\_backup_frontier\fix_starters_20261114\` +
  `fix_vanilla_full_20261114\`.
- **14/11/2026** — v1 abandonnée : 69 bornes `Frontier_Trader_*`
  (TraderNPC) + leurs templates supprimés après le test en jeu (bloc
  posé invisible). Les licences (Id 1411-1479) et leur vente par les
  commerçants sont conservées.
- **18/11/2026** — **Consoles commerçantes : trois paliers économiques.**
  T1 (5 électroniques + 10 plastique), T2 (5 consoles T1 + 20 reliques),
  T3 (5 consoles T2 + 20 reliques). Taux appliqués aux prix du marché :
  T1 ×1.60 à l'achat / ×0.40 à la vente, T2 ×1.40 / ×0.50, T3 ×1.20 /
  ×0.60 ; budgets de cycle 500 k / 5 M / illimité. Chaque console a ses
  propres commerçants activés et ses propres compteurs de stock (un
  marchand épuisé sur T1 peut être sollicité sur T2 puis T3). La vente
  automatique du container « VENTE » n'existe que sur T2 et T3, et
  affiche une **facture** détaillée (marchand, item, quantité, prix
  unitaire, total). Stock marchand limité dans les deux sens, remis à
  plein toutes les 60 min de session.
- **18/11/2026** — **Coque hull peignable + 10 textures inédites.**
  `HullFullSmall` (Id 381) reçoit `IsTextureable: true` (couleurs +
  textures vanilla), `HullFullLarge` (Id 403) reçoit `IsTextureable: true`
  + `TextureTable: 5` (textures 296-305 : 296/297 vertes, 298/299 grises,
  300-305 sans couleur). Aspect par défaut inchangé (texture 50, teinte
  110). Testé en jeu (pinceau) : textures visibles et appliquées, couleur
  impossible sur les entrées sans couleur de la palette 5.
- **18/11/2026** — **148 blocs POI rendus craftables + déconstructibles.**
  Tourelles (Retract/Faction/Upgrade), statues/posters, mobilier et
  conteneurs tribaux/Talon, sièges SS, cockpits SV, radar/capteurs, mines.
  Recettes copiées du bloc vanilla le plus proche (mapping :
  docs/recettes_blocs_proposees.csv), section « Frontier-FR : blocs rendus
  craftables » de Templates.ecf. Déconstruction par le Deconstructor (0.5).
  Exclus : stades de pousse, fenêtres Inv, blocs d'événement/POI, liquides.
  dev = prod, prelaunch 6/73.
- **18/11/2026** — **Radar de base fonctionnel + 57 blocs rendus visibles.**
  `RadarTracker` (Id 341) passe de déco inerte caché à scanner de base
  (`WeaponItem: DetectorCVWeapon`, 6000/24000, un par base, ShowUser Yes,
  recette LargeC/AdvC, clé `bkiRadarTracker`). Les 57 blocs craftables qui
  étaient `ShowUser: No` passent à `Yes` (recettes sinon invisibles).
  dev = prod, prelaunch 6/73.
- **18/11/2026** — **Blocs POI : recettes gardées pour la déconstruction.**
  Les 148 recettes restent dans Templates.ecf (Deconstructor), mais les
  changements de visibilité sont annulés (sauf statues/posters, déjà
  visibles) et `RadarTracker` revient vanilla (le scan n'existe que sur
  vaisseau). `PickupTarget: <lui-même>` ajouté sur les 148 blocs pour
  qu'ils soient ramassables en inventaire. dev = prod, prelaunch 6/73.
