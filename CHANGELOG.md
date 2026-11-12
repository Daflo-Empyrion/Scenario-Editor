# CHANGELOG — Empyrion Scenario Editor

Tous les changements notables du projet sont documentes ici.
Format inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
versionnement [SemVer](https://semver.org/lang/fr/) (`vX.Y.Z`).

Depuis la **2.6.0**, l'entree du CHANGELOG est la source des notes
de release : elle est recopiee telle quelle sur GitHub.

## [2.6.0] — 2026-11-12

*Bilan avant lancement, guerre totale entre factions, ressources en tension, corpus de traduction qui apprend*

### Bilan avant lancement (nouveau — `tools/prelaunch_check.py`)

Un seul passage couvre toutes les règles de cohérence du scénario, et le jeu ne
se lance plus sur une config douteuse. Deux crashs du 12/11 ont coûté deux
lancements : le bilan a été écrit pour qu'ils ne se reproduisent pas.

- **Hygiène ECF** : blocs ouverts et fermés sur la même ligne (« config line N
  is malformed » puis NRE), `HitPoints` sans `type: int` (valeur silencieusement
  ignorée), entrées de conteneur hors plage, `Material` inexistant.
- **Conflit de factions** : un seul bloc POI par faction (fini le churn de
  régénération), classes de défense spatiale, `ReserveCount`.
- **Progression** : `UnlockLevel` au-delà du cap joueur (25) signalé — l'objet
  n'est jamais débloquable.
- Chaque alerte nomme la **colonne Correction** (module ou passe à relancer) et
  la famille de gravité : `error` si le jeu crashe, `warning` si la donnée est
  seulement ignorée.

### Guerre totale entre factions NPC

- `ForceAttack` : les factions NPC s'attaquent réellement entre elles, avec une
  classe de vaisseau de défense spatiale par faction.
- Les mines et les bases partagent désormais un descripteur de POI unique : les
  passes ne se marchent plus dessus, et une mine starter est garantie sur
  chaque planète/lune.

### Ressources en tension

- **Zéro gisement au sol** : tout le minerai vient des POI, donc il faut aller
  le chercher.
- **Mines visibles** sur la carte et le HUD même sous brouillard de guerre
  (`Discovery: False` + `MapMarker`), avec la couleur de la faction.
- `RegenAfter` en **minutes de temps de jeu** (compteur gelé hors session), et
  non en temps réel.
- **Politique de régénération** : vaisseaux et ancres de placement
  (`SpawnPOINear`) intacts, marchands intacts, mines à 72 h, tout le reste
  **définitif** — une structure se récupère une fois. Appliquée par
  `tools/regen_passes.py` (idempotente, sauvegarde) et contrôlée au bilan : un
  POI qui revient au lieu de se vider rend les ressources infinies.

### Missions, jalons et particularités

- Chaîne « Anomalie » écrite par `core/mission_arc.py` (**désactivée** par
  défaut : le starter garde ses missions, reprise après décollage).
- Jalons technologiques par POI (PDA + tokens de localisation).
- `docs/scenario_re2fr_particularites.md` : la source de rédaction de la fiche
  du scénario, une entrée par particularité de gameplay.

### Traduction : le corpus apprend

- Une traduction **validée** est archivée par clé (nouvelle clé = ligne
  ajoutée) : elle ne repartira jamais vers l'IA sur un autre scénario.
- **« Mettre à jour le corpus »** (CSV Localization/Dialogues/PDA) : bilan
  chiffré avant d'écrire, et seule une action explicite remplace une valeur de
  référence. Toute écriture laisse une **copie datée**.
- **En-têtes mojibake** (`FranГ§ais`) : appariement corrigé, jamais écrits
  abîmés, et un bouton **« Réparer les en-têtes »** dans l'éditeur CSV.
- **Validation des départs** : le cache est clé par empreinte du départ
  (`Sectors.yaml` + `FixedPlayerStart`) et non plus par chemin — un
  déploiement dev → prod ne relance plus l'avertissement, mais changer le point
  de départ le relance.

### Sauvegardes et outils

- **Sauvegardes automatiques** (Outils > Fichiers) : liste par type, date et
  taille, **restauration** vers un fichier choisi (l'actuel est sauvegardé
  avant remplacement), et **ménage** (les 10 plus récentes de chaque dossier
  conservées, suppression au-delà de 60 jours, confirmation chiffrée).
- `tools/logdigest.py` : digest d'un gros log (14 000 lignes / 1,4 Mo →
  3,3 Ko) par signatures groupées, avec `--grep` pour redescendre au texte
  exact.

### Sous le capot

- Balance : audit IA des PNJ, vaisseaux, tourelles et factions.
- `paramiko` 5.x (alerte Dependabot SHA-1, CVSS 3.4).

## [2.5.0] — Non publiee

Bump de version effectue mais jamais tague ni distribuee : son contenu est repris integralement dans la 2.6.0.

## [2.4.0] — 2026-11-08

*Glossaire des propriétés, contrôle des blueprints, recettes réalistes*

### Glossaire des propriétés du scénario (nouveau)

Une base de connaissance de **~1500 propriétés** expliquées, construite en remontant à la source : moteur du jeu , documentation officielle Eleon dans les fichiers, et les 604 YAML + 259 ECF + 13 112 prefabs de RE2-FR. Chaque entrée est étiquetée par niveau de confiance ([M] moteur, [E] outil/scénario, [S] déduit).

- **Infobulles partout** : survoler une clé de propriété affiche son explication — éditeur ECF (mode liste et en-têtes de colonnes), éditeur YAML et vues lecture seule, tables de propriétés (duplication, template, ajout de bloc), clés de POI, comparateur du Codex, colonnes dynamiques des playfields, métas du panneau EPB. Priorité aux sources les plus fiables : glossaire manuel du fichier → glossaire général → commentaire inline du fichier ouvert. Rien n'est jamais inventé : une clé inconnue n'affiche rien.
- **Français ET anglais** : les explications sont traduites à la main (pas de traduction automatique) et un test garantit la synchronisation des deux langues avec le glossaire source.
- **Compréhension des ambiguïtés** : une clé homonyme (`Name`, `DroneProb`…) est désambiguïsée par son contexte (section du playfield, fichier ECF) ; sans contexte tranchant, pas d'infobulle plutôt qu'un faux sens.
- **Panneau « Voir l'explication de ce fichier » enrichi** : pour les fichiers sans glossaire fait main (EClassConfig, Dialogues, terrain.ecf…), le panneau affiche désormais la description du fichier et ses propriétés expliquées, au lieu du texte brut non traduit. Les YAML connus (playfield, Sectors, gameoptions, PDA) affichent une ligne « Ce fichier : … ».
- **Export CSV du glossaire de propriétés pré-rempli** avec les explications (garde anti-remplissage des termes trop génériques conservée).
- Source de vérité versionnée : `docs/glossaire_proprietes.md`, régénérable en données par `tools/build_propriete_glossary.py` (test de synchronisation markdown ↔ FR ↔ EN).

### Contrôle des blueprints .epb (parser réparé et vérifié)

- **Parseur  réparé sur 4 défauts de format** (statistiques v26+, booléens v28+, block groups v5, navigation par répertoire central du zip) : **13 103 / 13 112** prefabs de RE2-FR s'ouvrent (9 restants : format v<=3 non cartographié, erreur affichée proprement).
- **Colonne Groupe** et bandeau d'informations d'en-tête (GroupName, Tags, DisplayName — les clés de regroupement réelles du moteur).
- **Panneau meta** : pivot affiché avec bouton « Réinitialiser le pivot (0) » (le remblai du terrain suit le pivot — un pivot corrompu ensevelit le POI) et case **AddDigoutBox**. Roundtrip vérifié.
- **Surlignage des blocs interdits** activable/désactivable, avec la sémantique correcte : « interdit (spawn joueur) » n'est pas une corruption sur un POI.
- **Import des blocs manquants** : extraction des définitions brutes depuis la vanille ou le workshop et ajout au BlocksConfig du scénario (collision d'Id → import sans Id, backup central, ré-analyse).

### Recettes réalistes : doctrine finale

- Le `Templates.ecf` d'origine de RE2-FR était **octet pour octet** celui de la base RE2 Beta : les 968 recettes du scénario sont revenues **verbatim** (767 fabricables), `sync_to_base` = retour arrière idempotent.
- Le module `core/recipe_realism.py` ne gouverne plus que les recettes **absentes** de la base ; l'analyse exclut les recettes gouvernées par la base.
- **410 stubs de déconstruction** pour les objets non craftables pouvant entrer dans un inventaire (extrapolation du template RE2 le plus proche, `Target: ""` = visible du Deconstructor uniquement) + feuilles ajoutées pour tout ingrédient cité sans template — sinon le Deconstructor casse la chaîne. Idempotence vérifiée.
- Trace de conception complète dans `docs/recettes_realistes.md` (historique des doctrines essayées et annulées inclus).

### Corrections

- **Catalogue blocs/items** : blocs et items ont des **espaces d'ids séparés** — l'Item Id 978 écrasait le Block Id 978 et produisait ~714 faux « blocs inconnus ». Corrigé (deux tables, union des noms, bloc prioritaire).
- **Géométrie des fenêtres** : la taille restaurée est **bornée à l'écran d'accueil** (le retour d'une fenêtre de 2235 px sur un écran 1920 tronquait l'interface).

### Sous le capot

- Suite de tests : **2721 passed, 2 skipped** ; audit i18n 0 ; ruff 0.
- CI : le tag déclenche tests + audit i18n bloquants, puis build PyInstaller + Inno Setup et une release GitHub en brouillon.

## [2.3.0] — 2026-11-06

*Codex complet, planètes de départ, vue 3D des .epb, réintégration des playfields durcie*

### Codex (nouveau — menu Outils > Balance)

Portage complet du Codex communautaire dans l'éditeur, en lecture seule : rien n'est écrit dans le scénario.

- **Objets, blocs et jetons** : recherche sur le nom traduit ou la description, filtres par type, par placement (Base/CV/SV/HV) et « masquer sans prix ». Grille triable avec **colonne de cases à cocher** pour le comparateur (4 objets maximum).
- **Fiche détaillée** : stats, description BBCode rendue (couleurs du jeu), **recette directe ou aplatie** aux matériaux de base (les 4 minerais ne sont jamais développés), coût matériaux, marchands qui vendent/achètent, propriétés filtrées.
- **Comparateur** : une colonne par objet coché, différences surlignées — y compris les propriétés **présentes d'un seul côté** (c'est ce qui manquait), avec comparaison numérique (`1.5` = `1.50`).
- **Marchands** : fiche par négociant, prix estimés (un facteur `mf=` s'applique au prix marché, une plage absolue non), crédit total estimé, lignes illisibles conservées brutes.
- **Opportunités de trade** : un marchand vend, un autre rachète ; quantité échangeable × gain unitaire, filtre de profit, et **création d'une route en un clic** (vendeur → acheteur).
- **Lieux d'un marchand** : aucun fichier du scénario ne relie un marchand à un playfield — le lien est reconstruit par les **en-têtes de prefabs** (`Traders <nom>`, propriété 7 = GroupName), puis les POI des playfields, puis Sectors.yaml pour le système et le secteur. Rapprochement tolérant : alias `commdefault*`, suffixes `(hidden)`/`grey`/`white`, fautes de frappe (`paxpuragtory` → PaxPurgatory). Les marchands non nommés dans les prefabs restent « inconnu » avec des POI de commerce proposés comme **candidats**, jamais comme certitude.
- **Carnet de lieux et de routes** : destinations (planète, orbite, système, POI), item/bloc optionnel, quantité, note libre, case « vu » datée, net marchand `[conservateur] — [optimiste]`, duplication/renommage, illimité, enregistré hors scénario (`~/.empyrion_editor/codex/`).
- **Matrice de dégâts** : armes × catégories de matériaux, cellule = maximum des multiplicateurs explicites, paliers empiriques par colonne (percentiles 25/75/90). Vue « par bloc » : quelles armes percent un matériau donné.
- **Export CSV** de chaque vue (point-virgule, UTF-8 BOM), plus l'export de la route courante.

### Planètes de départ (nouveau)

- Choisir une planète **déjà présente dans la galaxie**, cocher « Départ proposé au menu » (marqueur `Human:1` dans Sectors.yaml) et régler le kit de départ façon Akua : `Spawn`, `Pos`, `RotY`, `Status`, `Items` sur 4 niveaux (EASY / MEDIUM / HARD / FRESH START).
- Fiche du menu Nouvelle partie : aperçu rendu (BBCode), ajout au-dessus de la description existante, réversible.
- Désactivation propre d'un départ, undo et backup central comme partout.
- Garde-fou honnête : un départ n'est validable qu'en jeu — cache de validation par playtest, avertissement au bilan pour les départs jamais testés, et playfields connus comme refusés par le client écartés.

### Vue 3D des blueprints .epb

Fenêtre externe ouverte depuis le contrôle : cubes de surface colorés avec la **palette du jeu**, caméra orbitale (glisser/molette/clic droit), sélection d'un bloc au clic avec ses coordonnées, son identifiant et sa couleur. Rendu logiciel (aucune dépendance ajoutée), blocs intérieurs ignorés pour tenir les gros prefabs.

### Réintégration des playfields : plus de plantage

- Les playfields **refusés par le moteur** (YAML invalide, `PlayfieldType` absent) sont écartés avec la raison affichée, au lieu d'être réintégrés.
- Les secteurs de l'ancien format sont correctement reconnus (WarpTarget n'est plus confondu avec un secteur legacy) : plus de suppression de secteurs de base ni d'orphelins éternels.
- Les départs déjà marqués dans Sectors.yaml sont préservés.

### Cohérence de l'interface

- **Messages métier d'un module affichés dans un autre, corrigés** : « Ondes de spawn » demandait « Appliquer N corrections aux **marchands** ? » puis annonçait « N **prix** écrits » ; même contamination dans corrélations, difficulté, jetons, ajout de POI, progression, défenses de faction, classements, recettes, coûts de déblocage et audit marchands. Chaque dialogue a désormais ses propres textes, avec un socle neutre pour ce qui est réellement générique.
- **Titres de fenêtre corrigés** : le visualiseur de galaxie s'annonçait « Fusion GalaxyConfig », le formulaire de signalement « Comparaison de scenarios ».
- **Garde-fou** : un test d'architecture refuse toute clé i18n métier utilisée hors de son module et vérifie que chaque clé existe en français ET en anglais.

### Sous le capot

- Nouveaux modules : `core/codex.py`, `core/codex_places.py`, `core/starters.py`, `gui/codex_*`, `gui/starters_dialog.py`, `gui/epb_3d_window.py`, `gui/codex_export.py`.
- Ajout de la lecture des couleurs et densités dans les `.epb` (l'écriture reste octet-pour-octet identique).
- Suite de tests : **2 658 tests passés**, 2 ignorés ; `ruff` propre ; audit i18n à 0.

## [2.2.0] — 2026-10-30

*Contrôle de cohérence global, boutons « Comprendre le module », prix marché par famille, look cartoon, réglage du danger sécurisé*

### Nouveau module : Contrôle de cohérence global (menu Outils)

Un seul clic lance TOUS les moteurs d'analyse en lecture seule et consolide le résultat en une table : domaine, sévérité, nombre, exemples, et le module de correction conseillé pour chaque constatation.

- **15 sections auditées** : bilan F5 (erreurs moteur), boucles d'argent marchands, disparités entre marchands, prix marché vs coût de fabrication, cibles famille en attente, recettes vs puissance, UnlockCost vs niveau, corrélations stats (masse, HP, dégâts, bouclier, thrusters), zones de spawn incohérentes, playfields sans spawn, progression (danger vs médianes).
- Chaque moteur est isolé : un échec n'annule pas les autres ; sévérité « info » pour ce qui est une réassurance (ex : « 0 boucle d'argent »).
- Export CSV complet ; scan hors thread (2-5 min sur un gros scénario, annoncé sur le bouton). Lecture seule : chaque ligne pointe vers l'outil dédié qui corrige.

### « Comprendre le module » sur 26 dialogues

Un bouton info (icône ?) ouvre une fiche HTML fr/en qui explique CE que fait le module, LES CONSÉQUENCES DES VALEURS CHOISIES (calculées en direct depuis les réglages quand ils comptent), les garde-fous, les limites moteur honnêtes et comment valider en jeu. Mécanisme partagé (une clé i18n par module) — câblé sur : prix marché, réglage du danger, look cartoon, bilan F5, réintégration, copie production, ondes de spawn, fiche scénario, sauvegardes (scénario + partie), jetons de quête, progression, défenses de faction, classements PDA, arbre technologique, carte galaxie 3D, ajustage de templates, éditeur PDA, admin EWA, fusion YAML révision + ligne à ligne, comparateur de scénarios, vérification économie, éditeur d'économie, recettes cohérentes, coûts de déblocage, corrélations, inspecteur POI, audit marchands, contrôle .epb, vérification yaml, équilibrage en un clic, duplication à variantes, création de bloc.

### Prix marché : cohérence par famille, recettes générées, bouton info dynamique

- **Statut « famille »** : les items vendables sans recette reçoivent une cible = médiane des prix des items partageant un mot du nom (séparation camelCase, familles d'au moins 3 membres).
- **Génération de recettes** : pour les vendables sans recette, une recette est écrite dans Templates.ecf en reprenant le modèle de la famille le plus proche, dosée au prorata pour atteindre le prix cible (backup central + revalidation avant écriture).
- **Recettes 1-ingrédient suspectes** : détectées (ingrédient = ~100 % du prix de sortie) — signalées dans le bandeau et en fin d'export CSV, jamais modifiées automatiquement.
- **Bouton info dynamique** : la fiche reflète TA marge et TA fabrication — multiplicateur réel, profit par palier, dérive d'un re-scan sur 5 niveaux, ou « zéro boucle » en politique prix = coût.
- Le filtre de statut liste le nouveau « famille » ; export CSV enrichi.

### Look cartoon complet

- Preset éditable dans le dialogue (8 facteurs : saturation, brillance, normales, relief, teintes RGB, ciel, luminance, brouillard), aperçu des couleurs **origine vs preset** par playfield avant toute écriture.
- **Sauvegardes cumulées datées** par passe, bouton **Restaurer** vers une passe choisie (working + resynchronisation production + invalidation des caches).
- Transformations chirurgicales : terrain.ecf et ciels modifiés ligne à ligne, tout le reste du fichier reste octet-pour-octet identique ; chaque fichier retransformé est revalidé par les parseurs avant écriture.

### Réglage du danger : annulation durable sur disque

- Chaque application archive l'état d'avant **sur disque** (dossier horodaté + manifest) : les boutons Annuler / Restaurer survivent à la fermeture du dialogue — fini le retour impossible après une passe trop dure.
- Bouton **Restaurer** : remonte une application archivée, archive l'état actuel avant, revalide.
- Garde-fous inchangés : plafond ×3, min ≤ max, POIs de départ jamais touchés, refus de vider un domaine.

### Copier vers la production : restauration intégrée

Le dialogue de synchronisation gagne un combo « Sauvegardes de synchro » + bouton **Restaurer** : remonte les fichiers écrasés par une copie précédente vers la production, en archivant d'abord l'état actuel (cumul horodaté) et en invalidant les caches du jeu.

### Bilan avant lancement renforcé

Nouvelles règles tirées de logs clients réels : ROF d'arme sous le minimum moteur (0.05), UnlockLevel d'un tier supérieur inférieur ou égal au tier inférieur (progression non croissante), IdMapping étendu à la bibliothèque Workshop et aux .epb racine, annotations `type:` fatales sur les propriétés lues comme chaîne, cohérence enfant/parent de l'arbre technologique.

### Divers

- Éditeur PDA : bouton info + règles de documentation intégrées (guidage PoiDiscovered).
- Fiche du scénario, Vérification yaml, Contrôle .epb, Audit marchands, Corrélations, Inspecteur POI : informations de contexte intégrées au même bouton.
- Traductions fr/en complétées pour toutes les nouvelles interfaces (audit i18n 0).

## [2.1.0] — 2026-10-25

### Bilan avant lancement : les chargeurs du jeu, dans l'editeur

Le bilan liste maintenant les erreurs **fatales exactes** des chargeurs du jeu — celles qui arretent le chargement d'un scenario. Avant, le test de chargement reel ne revelait qu'UNE erreur par iteration (corriger, relancer, corriger...) ; desormais tout est liste d'un coup, avec le message exact du moteur.

- **Items** : doublon d'Id, `Ref` inexistant, classe inconnue, `Material` manquant ou inexistant, `HoldType`/`Durability` non entiers, section `AltN` sans `Class`.
- **Blocs** : `Ref` inexistant, classe/mesh/place/shape inconnus (registres du moteur embarques), `Material` manquant ou inexistant, `Texture` non entiere, Id >= 2048, `TemplateRoot`/`BlockChangeTop`/`ChildBlocks`/`ParentBlocks` vers un bloc inexistant — la resolution des noms est **sensible a la casse**, comme en jeu.
- **Arbre technologique** : chaine `TechTreeParent` plus profonde que la limite du moteur, indices d'onglet `Nom$N` contradictoires, bloc affiche dans l'arbre sans template de craft (warning : pas de barre constructeur en jeu).
- **Parseur** : element sans Id ni Name, silencieusement ignore par le jeu.

Fidelite prouvee : **zero erreur sur la vanilla complete**, 16 warnings reels sur RE2-ATL-PRO. Le test de chargement reel reste en fin de chaine comme preuve finale — mais la boucle de correction passe desormais par le bilan instantane.

### Arbre technologique : la disposition exacte du F3

La vue de l'editeur reproduit maintenant l'agencement du jeu, regle par regle :

- **Construction par chaines** : chaque bloc affiche remonte sa chaine `TechTreeParent` et l'insere racine -> feuille ; un ancetre sans la categorie (ou `Hidden`) apparait quand meme comme noeud interne.
- **Ordre** : items d'abord (Id croissant), puis blocs — un enfant se place la ou la premiere feuille de son sous-arbre a ete traitee.
- **Colonnes = niveaux distincts de la categorie** (plus de grille fixe 1..25 : un scenario avec les niveaux 2 et 9 a deux colonnes, comme le jeu).
- **Lignes** : les enfants restent sur la ligne de leur parent, une feuille la coupe ; plus de « continuateur » devine.
- **`TechTreeSortIndex`** (tri des voies) et onglets **`Nom$N`** (ordre explicite) desormais lus — deux proprietes que l'editeur ignorait.

### Traduction des fiches : tu decides

Nouvelle option **Options > Traduction > « Traduction automatique des fiches »**, **desactivee par defaut**. Avant, ouvrir une fiche dont la description n'etait pas traduite declenchait une requete au moteur de traduction configure sans que tu le voies. Maintenant :

- option off : **aucune requete** a l'ouverture ; la note « description non traduite » reste affichee — c'est ta vue de ce qui reste a traduire en jeu ;
- option on : le comportement precedent revient (traduction automatique a l'ouverture, mise en cache par cle Info + langue) ;
- les traductions que tu declenches toi-meme (boutons FR/EN, menu contextuel, traduction de fichiers) ne changent pas.

---

2357 tests verts / 2 skipped, audit i18n 0, ruff 0. Installeur construit par la CI (tests 3.14 bloquants avant publication).

## [2.0.0] — 2026-10-24

### Assistant IA integre

L'editeur embarque desormais un assistant qui lit ton document et propose des modifications — sans jamais ecrire a ta place.

- **Chat contextuel** sur le document ouvert (ECF, YAML, CSV, PDA), palette d'appels, historique, arret en cours de reponse, revue d'une reponse avant de la garder.
- **Fournisseurs OpenAI-compatibles declares librement** : l'URL de base suffit, la cle est facultative pour un moteur local. Aucune liste figee dans le code, les presets ne font que pre-remplir le registre.
- **Routeur multi-maillons** : bascule automatique sur le maillon suivant en cas de panne, de quota ou de plafond ; un modele absent est ecarte 30 min, une panne 10 min, un 4xx ne condamne pas la chaine.
- **Gratuit d'abord** : les maillons gratuits tournent en boucle ; le payant n'est utilise que si tu le coches ET que le cout estime tient dans le plafond. Cumul mensuel en dollars, plafond global et plafond optionnel par fournisseur, compteur ecrit par lots (aucune I/O dans un chemin appele par cellule).
- **L'assistant n'ecrit jamais** : il rend un ChangeSet revu ligne par ligne (cocher, editer la valeur finale) et applique par les validateurs de chaque format. Un ChangeSet invalide n'est jamais applique : les problemes sont affiches, la reponse reste du texte.
- **Garde-fous avant tout envoi distant** : `redact_secrets` retire les formes connues de secrets (cles, mots de passe, identifiants d'URL) et signale le nombre de retraits ; un document modifie mais non sauvegarde n'est jamais touche par une proposition, pour qu'un Ctrl+Z ne melange pas une modification humaine et une application IA.
- **Reprise du format natif DeepSeek (DSML)** : certains maillons ecrivent leurs appels d'outils en texte dans `content`. Ils sont rejoues comme de vrais appels, et un invariant d'affichage garantit qu'aucun balisage n'atteint l'ecran, l'historique ni le tour suivant.
- **« Expliquer avec IA »** sur une valeur ECF, YAML ou CSV : les faits verifiables sont rassembles d'abord (glossaire du fichier, valeur vanille, mediane ou valeur la plus frequente du document), la question ne porte que sur eux.

### Equilibrage assiste (nouveaux outils)

- **Recettes de craft** (Templates) : cout en face de la puissance reelle des blocs et items, composition vanille respectee pour les templates qui existent en vanille.
- **Couts de deblocage** (UnlockCost) : perimetre limite aux entrees reellement affichees dans l'arbre, bande de cout par niveau.
- **Reparation du glossaire** : tri terminologie / phrases, reference a la localisation officielle quand elle existe, propositions revues avant toute ecriture.
- **Reintegration de playfields orphelins** : un dossier absent du `Sectors.yaml` n'est jamais charge par le jeu — il est repose dans des systemes existants, soleil deja present, `GalaxyConfig` inchange.
- **Import cible d'un scenario source** avec resolution recursive des dependances (Ref, recette du meme nom, ingredients de Template, BlockGroup, LootGroup, icone).

### Arbre technologique aligne sur le jeu

- **L'application lit desormais les proprietes comme le moteur** : declaration du scenario, puis patch `+Block`/`+Item` de la config de base du jeu, puis chaine `Ref`. Consequence directe : `OreScanner` apparait dans l'onglet Outils (niveau 3, cout 3, parent `RadarSuitT1`) — il etait invisible dans l'application alors que le jeu l'affiche depuis toujours. Ce sont au total 742 noeuds contre 732 auparavant qui sont maintenant visibles, exactement comme en jeu.
- **Regle de continuite des voies corrigee** : une voie continue avec le premier enfant declare qui partage les memes categories que son parent, et non avec le moins cher (contredit par une capture du jeu : `ThrusterSVRoundLarge` garde `LargeT2` a 15 et renvoie `JetRound1x3x1` a 12 sur la ligne suivante).
- **Edition coherente** : un noeud dont le niveau, le cout ou la categorie vient d'un `Ref` ou d'un patch de base est maintenant editable — la propriete est creee explicitement au lieu de faire echouer l'ecriture.

### Corrections et menage

- `.gitignore` : les fichiers de travail jetables (lots de traduction, scripts d'analyse ponctuels, notes de release en cours) ne polluent plus `git status`.
- `CONTEXTE_REPRISE.md` et `AGENTS.md` restent locaux par construction.

## [1.17.0] — 2026-10-18

*Carte de la galaxie en 3D*

### Carte de la galaxie en 3D (Sectors.yaml)
- **Camera orbitale a la souris** : glisser = orbite (des deux cotes du plan galactique), clic droit = deplacement de la vue, molette = zoom. Ouverture inclinee a 35 degres : le relief du scenario se voit des l'ouverture.
- **Une couleur par classe spectrale** d'etoile (O B A F G K M) avec legende ; **halo** sur les systemes structurants (Gate, Anomalie, systeme de depart) ; **etiquettes intelligentes** priorisees sans empilement (17 posees sur 82 systemes sur RE2) ; **recherche** de systeme qui estompe le reste de la carte.
- **Deplacement des systemes a la souris** conserve et ameliore : vue de dessus exacte, le point suit la souris avec les coordonnees affichees en direct, ecriture atomique annulable.

### Bibliothèque de blocs
- **Recherche par nom** dans la bibliotheque de blocs reutilisables.

### Missions PDA
- **Export de l'histoire en Markdown** : chapitres, taches et actions avec leurs textes traduits (colonne FR), pour relire ou partager le recit hors de l'application.

### Equilibrage economique (menu Outils)
- **Prix marche par cout de fabrication** : chaque MarketPrice face au cout reel de sa recette, formule reglable (marge + facteur temps), statuts par objet, selection en masse, backup central et re-scan automatique.
- **Audit des marchands** : uniformisation des taux de vente/rachat face aux MarketPrice effectifs, rachats manquants, prix absents, monnaies (Credits:) jamais touchees.
- **Equilibrage par correlations** : masse, points de vie, degats, boucliers, poussee des propulseurs compares a la mediane de leur groupe (famille x tier) — design volontaire preserve, medians epinglees apres application (pas de ratchet).

### Corrections et allegement
- 2 bugs corriges : les couleurs du theme etaient ignorees dans la fenetre de validation ; plantage possible de l'edition des proprietes de fin de bloc.
- Allegement : plus de 130 elements de code mort supprimes (imports et variables inutilises sur 84 fichiers), aucune fonctionnalite changee.

### Notes techniques
- Suite complete : 2062 verts / 2 skipped, audit i18n 0, ruff 0.

## [1.16.0] — 2026-10-12

*Empyrion Scenario Editor — v1.16.0*

**En bref :** cette version répond à LA question que tout auteur de scénario se pose avant de cliquer sur « Jouer » : *« mon scénario va-t-il se charger ? »*. Le **Bilan avant lancement** analyse ton scénario avec le moteur du jeu lui-même, la structure, les valeurs, les références — et si tu veux la certitude absolue, un **test de chargement réel** démarre ton serveur dédié dans une sauvegarde jetable et te remonte les erreurs du vrai moteur. Autres grosses nouveautés : le **module d'administration de serveur dédié** (EWA), la **fusion YAML ligne à ligne**, et quatorze correctifs d'audit.

---

### 🚀 Bilan avant lancement (menu Outils)

Un clic, une réponse claire : chaque problème est listé avec fichier, ligne et message exact.

- **Moteur du jeu embarqué** : tous les `.yaml` du scénario sont parsés avec le **YamlDotNet réel d'Empyrion** (outils compilés depuis la DLL du jeu) et tous les `.ecf` validés structurellement — les erreurs reproduites à l'identique, y compris le tristement célèbre *« did not find expected key »* des descriptions multi-lignes. (PyYAML donne des faux positifs sur le dialecte Empyrion : ne jamais valider un yaml du jeu avec lui.)
- **Structure Sectors** : playfields en doublon entre systèmes (*« Duplicate playfield name »*), systèmes sans soleil (injoignables), fichiers étrangers dans `Sectors/` (vécu : galaxie vide), playfields référencés mais absents du dossier.
- **Valeurs ECF** : dictionnaire de formes construit depuis la vanille — une valeur dont le type contredit tout ce que la vanille observe est signalée (tolérances calibrées sur le contenu officiel : valeurs quotées, booléens, décimales `.8`, suffixes `0.5f`).
- **Groupes d'entités** : les `Entities:/Names:` des playfields doivent exister dans `EGroupsConfig.ecf` / `EClassConfig.ecf` (scénario ou vanille).
- **GalaxyConfig** : séquences `Child StarRegion_N / Territory_N` sans doublon ni trou (*IndexOutOfRangeException* documentée).
- **Caches `.yaml.bin`** : orphelins et copies à date conservée (le piège qui servait l'ancien playfield).
- **Export CSV** des résultats en un clic.

### 🖥 Test de chargement réel

Pour la certitude absolue, une case à cocher : l'application **démarre ton serveur dédié** sur le scénario installé, dans une **sauvegarde jetable** (yaml `-dedicated` temporaire, ports dédiés, purge automatique), suit le démarrage ligne par ligne, puis s'arrête proprement.

- chaque ligne d'erreur que le **vrai moteur** logue remonte dans le bilan ;
- validé en conditions réelles : sur RE2-RPG, le moteur confirme l'unique groupe de POI fantôme (`Blueprint group 'FarrSpaceDef' not found or empty!`) — exactement ce que les checks statiques soupçonnaient ;
- ports hors gamme et sauvegarde dédiés : ton serveur et tes sauvegardes réelles ne sont jamais touchés.

### 🛡 Administration de serveur dédié (EWA)

Nouveau menu **Serveur** pour un dédié équipé du mod EmpyrionWebAccess : dashboard, chat serveur avec réponse directe, liste des joueurs en direct (kick/ban, crédits, envoi d'items), structures (touche/supprime/faction/warp), restauration joueurs et playfields depuis les backups, tâches planifiées, SystemConfig éditable, utilisateurs, **console telnet brute**, et **déploiement SFTP miroir** de ton scénario avec invalidation des caches du jeu.

Sécurité : mots de passe jamais persistés sans ton consentement explicite, clés d'hôte SSH épinglées (détection de MITM), confirmation avant toute action destructive, double-clic impossible.

### 🧭 Fusion YAML par lignes (menu Outils > Comparer YAML)

La fusion générique propose désormais la diff **ligne à ligne** entre deux fichiers : chaque ligne ajoutée/modifiée/supprimée est cochable individuellement, avec compteurs — la précision du merge de Sectors, pour tous les YAML.

### 📍 Placement guidé de POI

Nouvel outil d'ajout de POI sur la carte d'un playfield, avec sélection dans le catalogue des prefabs.

### 🛠 Quatorze correctifs d'audit

Crashs natifs au premier clic sur les onglets serveur, sélection d'un mauvais joueur dans les listes rafraîchies, conditions de course sur les restaurations, doublons de chat, confirmations manquantes, épingleage SSH, mots de passe en clair — tout est corrigé et couvert par de nouveaux tests connectés.

---

**Validation** : 1970 tests verts · audit i18n 0 · ruff 0

## [1.15.0] — 2026-10-06

*Empyrion Scenario Editor — v1.15.0*

**En bref :** la fusion des `Sectors.yaml` devient une revue fine et sûre (arbre système → secteur → playfield), la fusion YAML générique propose désormais **tout** ce que la source apporte — sous-clés absentes comme tâches ajoutées à une mission existante —, le `PDA.csv` est enfin parsé avec le bon dialecte, les références croisées gagnent deux contrôles — et la **synchronisation vers la production devient un miroir** qui invalide les caches du jeu. Adieu les modifications « à jour sur disque mais pas lues en jeu ».

---

### 🪞 Synchronisation production : miroir + invalidation des caches

> [!WARNING]
> **Le bug sournois de la semaine** : des fichiers parfaitement à jour dans le dossier de production... que le jeu ignorait royalement.

- **Cause** : la copie conserve la date du fichier source (`copy2`). Or le jeu compile chaque yaml de playfield en un cache `*.yaml.bin` et compare les **dates** : cache plus récent que le yaml → le jeu sert **l'ancien playfield compilé** et n'ouvre jamais le nouveau yaml.
- **Symptôme vécu** : missions cassées, POIs manquants, et une seule issue trouvée — supprimer tout le dossier de production à la main.
- **Correctif** :
  - les `*.yaml.bin` ne sont **jamais synchronisés** (fichiers dérivés du jeu, exclus comme les `.bak`) ;
  - copier un yaml de Playfields **invalide son cache** → le jeu le recompile au chargement ;
  - les caches **orphelins** (yaml supprimé ou renommé) sont purgés.
- **Mode miroir** (case cochée par défaut) : les fichiers présents en production *seulement* apparaissent `[À supprimer]` dans la liste et sont supprimés **avec sauvegarde préalable**. La production reste le reflet fidèle de la copie de travail — plus d'états mélangés.

---

### 🌌 Fusion fine de Sectors.yaml

Tout merge d'un `Sectors.yaml` passe désormais par une **revue fine**. La fusion générique ne sait pas que les playfields doivent rester uniques à l'échelle de la galaxie — vécu : *« Duplicate playfield name 'Zeyhines' »*, 5 doublons, crash du jeu.

- **Arbre cochenable** système → secteur → ligne de playfield, avec « ce qui change » à chaque niveau et sélection par sous-ensembles (tout un système, un seul secteur, une seule ligne...).
- **Conflits grisés** : une ligne déjà présente dans la copie de travail reste visible mais n'est jamais applicable — zéro doublon possible.
- **Dépendances proposées** : les dossiers `Playfields/<Type>` requis par les systèmes importés sont listés cochables et réparés à la copie ; types inconnus signalés.
- **Filets de sécurité à l'application** : correction optionnelle des doublons préexistants, détection des systèmes sans soleil, scan post-application — un résidu s'affiche au lieu d'écrire un fichier cassé.
- Backup central + undo espace de travail, comme toujours.

---

### 🧭 Fusion YAML : plus rien ne se perd

La fusion YAML générique connaissance deux limites gênantes — les deux sont levées :

#### Les sous-clés absentes sont proposées (YAML-009)

Avant : une sous-liste absente de la copie de travail était sautée **en silence** — vécu : les POIs d'histoire REX de GS_Masperon invisibles car rangés sous `POIs: → Random:`, et le `Fixed:` de REX ignoré car absent du scénario hôte.

Maintenant : toute sous-clé absente apparaît dans la fenêtre de fusion comme **« Sous-clé ajoutée »**, cochable, avec la liste des blocs qu'elle contient en info. Décochée, la convention de l'hôte prime (ex. le pod de départ `Fixed:` de REX ne s'impose pas à ton scénario).

#### Les blocs existants sont complétés

Avant : la fusion ne connaissait que les identités *absentes* — une mission PDA déjà présente chez toi mais **enrichie chez la source** (une tâche en plus, une action en plus) passait inaperçue.

Maintenant : le moteur descend dans les blocs présents des deux côtés et propose **unité par unité** ce que la source a en plus, avec son chemin d'insertion exact affiché (`Etape3 · Chapters/MissionAkua/Tasks`). Profondeur illimitée en pratique (tâches → actions → ...), plafonnée à 12 niveaux par sécurité. La copie de travail n'est jamais réécrite : seuls des ajouts cochés y sont insérés, commentaires et mise en forme préservés, re-fusionner ne double rien.

---

### 📄 PDA.csv : dialecte standard forcé

Le sniffer CSV choisissait `quotechar='` sur les CSV Empyrion (à cause des `''` d'échappement du jeu) et **tout le pipeline dérivait** — vécu Random EXP : clés brutes partout au lieu des textes.

- Le `PDA.csv` est parsé avec le dialecte standard **forcé** (`"` + doublequote), en fusion comme en application de révision.
- `sanitize_pda_game_dialect` défait le wrapper `'...''...'` des cellules déjà ingérées au format jeu.

---

### 🔗 Références croisées : deux nouveaux contrôles

| Contrôle | Ce qu'il vérifie | Vécu |
|---|---|---|
| **material_refs** | un `Material:` référencé par un bloc doit exister dans `MaterialConfig` | bloc 872 → `hullcombatcharged` absent, table des blocs morte |
| **pda_poi_refs** | les POIs ciblés par les missions (`NearPoi`, `PoiDiscovered`) doivent exister dans les Playfields | 124 manquants sur Serveur-MP — tout le couplage PDA ↔ contenu quantifié |

Correctif au passage : la fenêtre de correction des références dialogue refonctionne (mauvais import de `capture_file`).

---

### 💾 Sauvegardes centrales

Nouveau `central_backup()` : toutes les sauvegardes internes vont dans `~/.empyrion_editor/backups/<type>/` — **jamais de `.bak` à côté des fichiers du jeu**. Rappel du vécu : le jeu charge *tous* les `.yaml` du dossier `Sectors/`, un `Sectors.yaml.bak` y est fatal (galaxie vide).

---

### 🛠 Corrections diverses

- **Fusion GalaxyConfig** : la fenêtre « Systèmes du scénario source » s'affichait **vide** — l'arbre n'était jamais ajouté au layout. Réparé.
- Les tests n'écrivent plus jamais dans le vrai dossier de sauvegardes.

---

**Validation** : 1883 tests verts · audit i18n 0 · ruff 0

## [1.14.0] — 2026-10-01

*Empyrion Scenario Editor v1.14.0*

### Fusion spécialisée GalaxyConfig

- Nouvelle action **clic droit sur un `GalaxyConfig.ecf` source → « Fusion GalaxyConfig (spécialisée)... »** : le fichier a des noms de blocs répétés légitimes (variantes de classes d'étoiles), la fusion générique le refuse — cette voie spécialisée apparie les classes par **(Name, StarClass)** et contourne le garde-fou (qui reste en place pour la fusion ECF standard).
- **Fini l'`IndexOutOfRangeException`** : les blocs indexés `Child StarRegion_N / Territory_N` importés déclenchent une **renumérotation contiguë de tout le fichier** (plus de trous ni de doublons d'index), avec respect des limites du jeu (199 régions, 20 territoires).
- **Dépendances détectées et copiées automatiquement** : `SolarSystemConfigSuffix` → presets `RandomPresets/SolarSystemConfig<Suffix>.yaml` → playfields référencés → groupes d'ennemis `EGroup` ajoutés à `EGroupsConfig.ecf`. Avertissements pour les systèmes placés à la main absents du `Sectors.yaml`.
- **Bloc General** : la copie de travail reste prioritaire ; les différences sont cochables propriété par propriété si tu veux prendre celles de la source.
- **Factions** : une faction custom requise par un territoire importé est extraite de la source vers `Factions.ecf`, ses réputations propagées dans `DefReputation.ecf` (jamais d'écrasement, jamais de fichier à moitié vide), `FactionWarfare` signalé si elle y est pilotée.
- **Idempotent** : re-fusionner la même source ne redoublonne rien (systèmes « déjà présents » reconnus), `.bak` + undo espace de travail comme toujours.

### Équilibrage : les items et les patchs

- L'équilibrage scanne désormais **`ItemsConfig.ecf` en plus de `BlocksConfig.ecf`**, et lit les **patchs `+Block` / `+Item`** (convention de surcharge Empyrion) : sur REXiang, la couverture passe de 125 à **1 745 propositions** avec le préréglage « Retour aux valeurs vanille ».
- L'aperçu est **éditable ligne par ligne** : double-clic (ou F2) sur la colonne « Nouveau » pour ajuster la valeur à appliquer ; une cellule vidée ignore la proposition.

### Comparateur de bundles Unity

- Nouvel outil **Outils → Comparer des bundles Unity...** (et CLI `tools/compare_bundles.py`) : liste les ajouts / retraits / types différents entre deux asset bundles de scénarios (`decals`, `eden_decalmodels`...), export CSV. Les bundles ne se fusionnent pas en binaire — cet outil sert à décider avant une fusion de dossier.
- **UnityPy est embarqué dans l'installeur** : rien à installer. (Depuis les sources : `pip install UnityPy`.)

### Localisation : généralisée à tous les fichiers

- Le clic droit **« Créer une localisation... »** fonctionne maintenant sur **toutes les propriétés de corps de tous les fichiers ECF** (v1.10 la limitait à `SellingText` de TraderNPCConfig).
- Si la valeur est déjà une clé de localisation (`igmEffect...`, `TmpEff_...`) : la ligne est créée dans le `Localization.csv` du scénario et la cellule reste intacte. Si c'est un texte libre : une clé `scn_<Bloc>_<Propriété>` est générée et la cellule la pointe. Jamais d'écrasement d'une traduction existante.

### Panneau de propriétés ECF : plus de faux doublon

- Dans StatusEffects notamment, un bloc a un **`Name` d'identité** (ligne d'ouverture) **et** un `Name` de corps (nom d'affichage vanille) — affichés côte à côte, ils ressemblaient à un doublon cassé. Les propriétés de la ligne d'ouverture sont désormais **en gras + italique** avec une infobulle explicative.

### Divers

- La copie de travail d'un scénario posée dans le dossier du programme (`ATL/`) est ignorée par git — impossible de la committer par accident.
- Correctif packaging : les données/binaires de qfluentwidgets étaient collectés mais non embarqués dans l'exe.

### Pour rappel (inclus depuis v1.13.0)

Fusion ECF sécurisée (dédoublonnage, garde-fou identités dupliquées), fusion YAML/CSV génériques avec fenêtres de révision, Blocs en attente à 3 modes, validation E006/E008/W007, synchro production durcie, dialecte BBCode Empyrion, traduction à chaîne de secours Groq → DeepL → Google → NLLB → Argos.

## [1.12.0] — 2026-09-26

### Ajoute
- **Separateur des blocs ajoutes par fusion** (demande 25/09/2026) : les
  blocs issus uniquement du scenario source atterrissent apres ceux de la
  copie de travail — un commentaire `# ===== Fusion depuis "<source>" :
  blocs ajoutes ci-dessous =====` ouvre chaque paquet consecutif pour les
  differencier du contenu d'origine
- **Conflits d'Id visibles dans l'apercu de fusion** (demande 25/09/2026) :
  meme Id mais identite differente = materiel different — l'apercu
  affichait seulement un compteur rouge ; desormais UNE LIGNE par conflit
  (non cochable, informationnelle) avec l'Id en cle, les DEUX noms en
  Avant (copie de travail) / Apres (source), ET LA PROPRIETE QUI A
  DECLENCHE le conflit affichee dans la cle (ex : patch +Block de meme
  Id et meme Name mais Model different — sans elle, le conflit semblait
  absurde), en plus du bloc ajoute desactive en fin de fichier
- **Nom du bloc affiche sur TOUTES les lignes de l'apercu de fusion**
  (demande 25/09/2026) : le libelle devient « Block [412] · HullTest » —
  valider « MaxCount 32 -> 6 » sans voir le nom du bloc etait impossible
  quand l'identite n'est qu'un Id numerique
- **Fusion STRUCTURELLE du Sectors.yaml** (tranche 2, demande 25/09/2026) :
  dans la fenetre de revision, quand un Sectors.yaml est concerne, section
  « Fusion structurelle » (recommandee, cochee) listant UNITE PAR UNITE ce
  que la source apportera — systeme entier, secteur (par coordonnees),
  ligne de playfield (par nom affiche) — insere dans VOTRE Sectors.yaml
  via yamllite (commentaires et mise en forme preserves, texte source
  recopie tel quel) au lieu d'ecraser le fichier ; l'ecrasement brut
  reste possible en decochant la structure et en cochant le remplacement.
  Idempotent : apres insertion, une nouvelle analyse ne propose plus rien
- **Fenetre de revision pour la fusion de DOSSIER + dependances**
  (demande 25/09/2026) : les non-ECF (Sectors.yaml, Playfields/,
  Prefabs/) etaient copies EN AVEUGLE par la fusion de dossier — desormais
  une fenetre de revision liste chaque fichier (nouveau / REMPLACEMENT
  decoche par defaut avec diff +x −y en info-bulle / fusion ECF / fusion
  CSV), detecte les DEPENDANCES quand un Sectors.yaml est concerne
  (dossiers de playfield references — Playfields/<template>/ — et POIs
  references par leurs playfield_static — Prefabs/<GroupName>.epb —
  absents de la copie de travail, proposes coches), et n'applique que la
  selection validee ; un fichier ecrase ne l'est plus jamais sans choix
  explicite
  explicite ; extraction des templates SANS PyYAML (scan
  ligne des listes flow — PyYAML absent des
  requirements/installeur, vecu CI v1.12.0 : dependances
  vides silencieuses)
- **Fusion ECF : listes ItemN appariees PAR IDENTITE** (TraderNPCConfig,
  vecu 25/09 : deux scenarios n'ordonnent pas leurs items pareil, l'apercu
  appariait Item1<->Item1 et la fusion ecrasait des items differents —
  HeliumBottle remplace par ScienceEquipment) : dans l'apercu de fusion,
  les items sont apparies par leur NOM (premier champ de la valeur, ex
  « AlienNPCBlocks ») — lignes « Item1 · AlienNPCBlocks / Item3 · Leather »,
  (absent) quand sans correspondance ; a l'application, les items communs
  prennent la valeur source, les ajouts sont appended et la liste est
  RENUMEROTEE Item1..N sans trou ; les items propres a la copie de
  travail ne sont jamais touches
- **Apercu de fusion : cles et libelles CONSCIENTS DU PARENT** (vecu
  25/09, Templates.ecf : les blocs enfants sans identite — « Child
  Inputs » de chaque template — partageaient la meme cle et leurs lignes
  ne disaient pas de quel template elles relevaient) : les lignes
  affichent desormais « +Template [GoldOre] · Child Inputs » et
  l'appariement ne croise plus les parents
- **Équilibrage du scénario en un clic** (Outils > Équilibrage du scénario...,
  MODULE_EQUILIBRAGE.md, demande 24/09/2026) : moteur de règles
  (core/balance_rules.py) sur les blocs définis par le scénario — 28
  propriétés (MaxCount, CPUIn, HitPoints, Damage, Range/RangeSpace,
  boucliers ShieldCapacity/Recharge/Cooldown/PerCrystal/CapacityBonus/
  DamagePenFac/HitCooldown, ThrusterForce, RangeAU/LY, CostPerAU/LY,
  EnergyOut/In/InIdle, SolarPanelEfficiency, MarketPrice, StackSize, Mass,
  Volume) avec politiques « conservé / valeur vanille / plafonner à /
  MULTIPLIER PAR % » (demande 24/09 : le % multiplie la valeur ACTUELLE
  de chaque bloc et preserve les ratios internes, contrairement au
  plafond) et préréglage « retour aux valeurs vanille » ; APERÇU
  MODIFIABLE (fichier/bloc/propriété/actuel→nouveau, cases à cocher),
  application atomique avec backups .bak, undo espace de travail et
  rechargement des onglets ouverts. Inventaire vanille+scenario avec la
  règle du jeu « dernière définition gagne » ; n'écrit JAMAIS dans la
  vanille ; ne propose que les lignes de propriétés déjà présentes au
  scenario ; liste blanche CPU (MissionContainer) ; pas de proposition
  sans effet (0→0)
- **Synchronisation vers le scenario EN PRODUCTION** (demande 24/09/2026) :
  a la fermeture de l'application (et via Outils > « Copier vers le
  scenario en production... »), propose de copier (remplacer) tous les
  fichiers modifies de la copie de travail vers le dossier que charge le
  jeu (ex : Content/Scenarios/RE2 ATL) — fini le copier-coller manuel.
  La liste est une DIFFERENCE AVEC LE DOSSIER DE PRODUCTION (corrige le
  jour meme : une difference vs la source A reproposait a l'infini les
  memes fichiers) ; apres une copie reussie, plus rien n'est propose.
  Deduction automatique du dossier par le nom de la copie de travail,
  mémorise ensuite PAR PROJET (un reglage global unique faisait proposer
  RE2 ATL pour n'importe quel projet ouvert, et figeait la suite de tests
  sur un exec modal a la fermeture d'une fenetre de test) ; recalcul quand
  on change le dossier ; sauvegarde systematique des fichiers ecrases
  (~/.empyrion_editor/production_sync/<horodatage>/) ; case « ne plus me
  proposer a la fermeture » ; confirmation puis fermeture automatique du
  dialogue apres une copie reussie ; copie hors thread GUI (gerbe plasma)
- **Gerbe plasma animee pendant les operations longues** (gui/plasma_overlay.py,
  gui/busy.py) : des qu'un chargement, une ouverture, une verification ou un
  telechargement dure plus d'une seconde, une gerbe d'etincelles bleue
  radiante sur fond noir (style warp, QPainter pur, ~30 i/s) s'affiche avec
  fondu ; avant le delai, un bouclier d'entree invisible bloque tout
  double-declenchement. `run_long()` execute le travail HORS du thread GUI
  (thread demon + pompe processEvents) : l'animation reste VIVANTE, contra-
  rairement a l'ancienne boite figee. L'exception du worker est relancee sur
  le thread appelant
- **Sites convertis en run_long** : extraction de proprietes, parse du
  Sectors.yaml (galaxie), validation scenario, references croisees, jetons
  orphelins, fichiers modifies, recherche/remplacement scenario, scan
  orthographe Grammalecte + telechargement, verification/test Groq et DeepL,
  telechargement NLLB, calcul de l'apercu de fusion ECF, collecte des stats
  dashboard, « Tout verifier » (sante projet)
- `busy_guard` (blocs touchant aux widgets, donc forcement synchrones :
  construction du viewer galaxie, arbre technologique, onglets PDA/traders,
  corrections orthographe) affiche desormais l'ecran plasma des l'entree
  (image figee apres quelques frames, mais ecran d'attente uniforme)

- **Liste de remplacement triee par nom alphabetique** (demande 24/09/2026)
  : en tapant « core », tous les blocs contenant core apparaissent groupes
  dans la completion

### Corrige
- **Remplacement d'un bloc dans un .epb a mapping embarque : la cellule
  remplacee disparaissait au spawn** (vecu 24/09 : CoreNoCPU remplace par
  Core (558) -> « inconnu », blueprint spawnant sans coeur) : la resolution
  du jeu est PAR NOM — le BlockIdMapping embarque est desormais tenu a jour
  (entree de l'ancien id retiree, nouvel id mappe vers son nom du
  catalogue) ET la section mapping est reellement re-serialisee a la
  sauvegarde (l'entete etait recopiee verbatim depuis v1.11.0, aucun
  changement du mapping ne pouvait survivre)
- **LE bug des lignes CPUExtenderCVT4/CoreNoCPU jamais colorees (vecu 4
  fois, du 23/09)** : le dialogue .epb recevait `str(workspace.working)` —
  la REPRESENTATION d'un objet WorkingCopy, pas un chemin — donc le
  repertoire du scenario n'a JAMAIS figure dans le catalogue depuis
  v1.11.0 : l'analyse tournait en VANILLE SEULE (1891 ids au lieu de 1892),
  et ces deux blocs, connus de la vanille, n'etaient jamais marques.
  Corrige via `_epb_catalog_paths()` (working_root reel) + test de
  regression. La barre de statut affiche desormais toujours le catalogue
  utilise et avertit « VANILLE SEULE » quand le scenario n'est pas inclus
- **Rendu des couleurs sous le theme** : le QSS du theme ignore les roles
  Background/Foreground des items des qu'une regle touche
  `QTreeWidget::item` -> un delegate peint fond + texte lui-meme ; fonds
  satures (le premier choix, quasi noir sur theme sombre, etait invisible)
  ; filtre « problemes uniquement » applique des l'analyse + selection de
  la premiere ligne probleme + decheck automatique si le blueprint est
  propre ; detection interdit PAR NOM (ids locaux des mappings embarques)
- **Statut du dialogue .epb** : `{f}` brut affiche au lieu du nombre de
  fichiers (la chaine attend n ET f, l'appel ne passait que n)

## [1.11.0] — Non publiee

### Ajoute
- **Controle des blueprints .epb** (menu Verification -> Blueprints (.epb)) :
  lecture du format binaire .epb (reconstruit depuis le code du jeu :
  header magic/version/taille, proprietes, statistiques, BlockIdMapping
  embarque, groupes, matrice sparse bitmask + uint32 par cellule occupee),
  liste complete des blocs d'un .epb ou de tous les .epb d'un dossier
  (prefabs du scenario, dossier de blueprints Steam), statuts par bloc :
  inconnu (rouge) = absent du catalogue, interdit (orange) =
  AllowedInBlueprint: false dans les ECF, avec quantites
- **Vue 3D voxel** de la structure (gui/epb_view_3d.py) : projection
  isometrique dans une zone de defilement (QAbstractScrollArea, seuls les
  blocs visibles sont dessines -- 48k blocs fluides), zoom molette centre,
  Pivoter 90 deg, Recentrer, clic sur un voxel -> id + nom du bloc
- **Reparations** : Remplacement d'un bloc par un bloc du catalogue
  (rotation et position conserves), Suppression de toutes les cellules
  d'un id (clic droit), Sauvegarde des .epb modifies avec backup .bak ;
  le rezip reconstruit crc/tailles locales et repertoire central
- **Export CSV** de tous les blocs (X;Y;Z;ID;Nom;Rotation;HP)
- **Saisie libre** dans le combo de remplacement : nom de bloc (completion
  contient insensible a la casse), texte d'item `Nom (id)`, ou id numerique
- **Index des couleurs** de la vue 3D : pastille exacte + nom + quantite
  par id de bloc
- **Catalogue de blocs fusionne** (load_block_catalog) : BlocksConfig*.ecf
  des sources dans l'ordre du jeu (vanille d'abord, scenario gagne),
  blocs `Ref:` sans Id heritent par nom, ids dont le nom a disparu de la
  fusion = perdus au spawn (reproduit le message IdMapping de la console)

### Corrige
- **Rend_csv : les vrais retours a la ligne dans une cellule produisaient
  des cellules multi-lignes que le parseur PDA du jeu ne resout plus**
  (cles affichees brutes en jeu, vecu sur le PDA.csv de RE2 ATL, 37
  cellules) : le rendu convertit tout retour en litteral 
 -- convention
  du jeu, utilisee par les colonnes EN du vanille ; normalisation appliquee
  aux fichiers du scenario (PDA.csv 37, Localization.csv 8)

### Notes
- Catalogue par DOSSIER Configuration (le jeu fusionne tous les
  BlocksConfig*.ecf) ; ordre [vanille, scenario] : la derniere definition
  d'un id gagne ; blocs `Ref:` sans Id = connus par nom (id attribue par
  le jeu), donc JAMAIS proposes au remplacement par erreur
- Champ chemin du dialogue vide a l'ouverture (placeholder a la place)

## [1.10.0] — Non publiee

### Ajoute
- **« Localiser cette valeur (Localization) » sur SellingText**
  (TraderNPCConfig.ecf, demande utilisateur) : le jeu accepte une CLE de
  Localization.csv comme valeur de SellingText (mecanisme documente
  dans le fichier vanille lui-meme : `# SellingText:
  "trwDefaultSellingText"`) et affiche alors le texte dans la langue du
  joueur. L'action genere la cle (`scn_Selling_<Nom>`), cree/met a jour
  la ligne dans le Localization.csv du scenario (priorite a un fichier
  EXISTANT : la localisation peut vivre a la racine du scenario ou sous
  Content/Extras selon le scenario — vecu RE2 ATL ; jamais ecraser une
  traduction existante) et remplace la valeur ECF par la cle — le texte
  EN reste traduisible vers toutes les langues via le flux CSV existant
  (memoire, glossaire, Groq/DeepL...). Info-bulle d'affordance sur les
  cellules SellingText ; dialogue de confirmation avec le chemin du CSV
  a traduire ; garde si la cellule pointe deja vers une cle. Nouveau
  core/selling_localization.py.
- **Vert vanille retabli et persistent** (retour 19/09/2026) :
  - les cellules cibles dont le contenu est EXACTEMENT la traduction
    officielle Eleon sont colorees en vert **des le chargement** du CSV
    (les couleurs n'etaient appliquees qu'au moment de la traduction et
    disparaissaient a chaque reouverture) ;
  - la memoire utilisateur reste prioritaire, mais si elle contient
    exactement la traduction officielle, la source est reportee
    'vanilla' (le vert restait cache derriere les entrees 'memory' des
    fichiers deja traduits) ; une traduction CORRIGEE par l'utilisateur
    (differente de la vanille) ne devient jamais verte ;
  - nouveau core/vanilla_memory.vanilla_matches() (conformite Eleon).
- **Taille/position des fenetres persistees + boutons Agrandir/Reduire**
  (demande utilisateur : ne plus avoir a agrandir a la main a chaque
  ouverture ; les QDialog n'ont par defaut qu'une croix) :
  gui/window_geometry.py -- boutons Reduire/Agrandir-Restaurer ajoutes a
  la barre de titre des fenetres de travail, taille/position ET ETAT
  MAXIMISE persistes (28 fenetres branchees : fenetre principale, revue
  de traduction, assistants Argos/NLLB/Groq/DeepL, dashboard, catalogue
  d'items, glossaire, Grammalecte, comparateur, economie, protocole de
  test, wiki, tutoriel, sauvegardes, recherche/remplacement...).
  Restauration avec garde multi-ecran (position ignoree si l'ecran
  d'origine n'existe plus) ; sauvegarde a la fermeture ET au masquage
  (accept/reject des dialogues modaux) ; geometrie dans settings.json
  LOCAL.
- **Bascule automatique entre moteurs de traduction** (Options >
  Traduction > « Bascule automatique », activee par defaut ; inspiree du
  failover de freellmapi) : quand le moteur principal (radio du
  sous-menu Moteur) atteint son quota ou tombe en panne, la chaine de
  secours enchaine les autres moteurs disponibles — depuis le principal :
  Groq -> DeepL -> Google -> NLLB -> Argos. Chaque maillon en echec est
  mis au repos (quota DeepL = 30 min, pannes = 1-2 min) pour ne pas
  marteler un service mort ; la barre de progression affiche le moteur de
  secours qui sert reellement (« Secours : traduction assuree par... »).
  Une cle REFUSEE (401/403) ne bascule jamais silencieusement : l'erreur
  remonte pour etre corrigee. Les maillons en ligne sont filtres par la
  case « Traduction en ligne » (confidentialite).
- **Moteur DeepL (API Free)** : plan gratuit officiel (500 000
  caracteres/mois, sans carte bancaire), assistant dedie (liens
  cliquables, cle masquee, verification reelle via /v2/usage avec quota
  du mois affiche, test de traduction, case moteur principal). Nouveau
  core/deepl_provider.py (erreurs typees 403/456/429/5xx).
- PRIVACY.md : section DeepL (FR/EN).

### Change
- Erreurs des moteurs TYPEES (core/engine_errors.py : QuotaExhausted /
  EngineUnavailable / Auth) — sous-classes de RuntimeError, l'interface
  et les tests existants restent valides.
- Le lot Groq en echec quota ne fait plus echouer toutes ses cellules :
  la chaine les termine cellule par cellule.
- **Glossaire multi-langues** : chaque entree porte desormais la langue
  cible a laquelle elle s'applique — une traduction imposee francaise ne
  fuit plus dans les traductions vers d'autres langues, et le meme terme
  peut avoir une traduction imposee par langue. Les entrees de l'ancien
  format sont migrees en "fr" au chargement. L'auto-alimentation porte
  la langue de la cellule validee. Dialogue de gestion : colonne Langue
  + choix de la langue a l'ajout.
- Corrige au passage (bug latent historique) : la suppression d'une
  entree du glossaire n'etait visible qu'apres redemarrage (le cache
  memoire n'etait pas reassigne).

### Corrige
- **Contenu inventé par le glossaire (« Mourir / Sac à dos / Nager /
  Faction » injecté dans les traductions, retour 20/09/2026)** : une
  cellule contenant un simple « - » avait été validée et
  auto-alimentée dans le glossaire comme terme source « - » — qui
  correspondait au tiret de « high-end » etc., injectant la liste dans
  TOUTES les traductions, quel que soit le moteur (le glossaire
  s'applique avant tous). Correctifs : les 5 entrées sans aucun
  caractère alphanumérique du glossaire local sont purgées ;
  l'auto-alimentation refuse les cellules purement ponctuation ;
  `add_entry` refuse de tels termes ; les entrées existantes sans
  caractère alphanumérique sont ignorées à l'application.
- **RACINE des pertes de `\n` trouvée (tous moteurs)** :
  `restore_segments` réinjectait les segments protégés via `re.sub` avec
  un **template chaîne** — le moteur d'expressions régulières y
  interprète le `\n` littéral du CSV comme un **vrai retour à la
  ligne**. Chaque traduction « texte entier » (Groq cellule entière,
  DeepL, Google) convertissait donc les `\n` du fichier en vrais
  retours à la ligne — d'où « plus de `\n` dans la traduction ». Le
  remplacement se fait par **fonction** (jamais échappé). Corrigé au
  passage : la restauration tolérante pouvait avaler un `x`/`X` réel
  collé à un jeton (correspondance exacte d'abord, tolérante en repli).
- **Cellules contenant la page d'erreur Google « Error 500… »** (retour
  19/09/2026) : **293 entrees polluees** de la memoire de traduction,
  heritees de l'ere de l'auto-stockage, ressortaient comme hits
  « memoire » en court-circuitant tous les controles — purgees du
  fichier local, et un hit memoire qui ressemble a une page d'erreur
  est desormais IGNORE (cellule re-traduite proprement). Filet final
  ajoute sur TOUT resultat moteur (LLM hallucinant, MT limite) :
  jamais de page d'erreur dans un fichier de jeu.
- **Google : squelette de jetons desormais verifie** — dernier chemin
  envoyant un texte protege entier sans controle, il pouvait perdre des
  `\n`/balises comme DeepL ; structure perdue = moteur ecarte, le
  suivant prend le relais.
- **Journal de diagnostic de traduction** : chaque cellule traduite par
  un moteur est tracee en JSONL local (`~/.empyrion_editor/translation_
  debug.jsonl`, anneau de 2 Mo) — moteur reellement utilise, texte
  envoye, texte recu, repli ou non — pour attribuer precisement toute
  cellule litigieuse (pertes de `\n`, garbage) a son moteur.
- **DeepL perdait parfois des jetons `\n`** (retour 19/09/2026 avec
  captures, surtout quand plusieurs jetons sont colles) : le chemin
  DeepL verifie desormais le squelette de jetons comme les moteurs LLM
  et repasse en FRAGMENTS DeepL (les jetons ne voyagent plus au
  moteur) en cas de perte — structure toujours garantie.
- **Traduction bloquee pendant 10 minutes a 2 % (vecu 19/09/2026)** :
  quand Groq tombait en quota pendant un lot, la bascule vers DeepL
  prenait le relais — mais 60 s plus tard, un nouvel essai Groq
  repartait dans le throttle qui DORMAIT jusqu'au reset annonce
  (24 s pour le plafond/minute... jusqu'a des HEURES pour le plafond
  journalier de tokens). Correctifs : le throttle echoue immediatement
  au-dela de 30 s d'attente (jamais plus de sommeil) ; le maillon Groq
  est saute sans appel tant que son cooldown court ; le repos est
  aligne sur le reset REELLEMENT annonce ; les requetes lot ne
  redemarrent plus pendant le repos. L'annulation est de nouveau
  honoree immédiatement (plus de "QThread destroyed").
- **« Creer un Template pour ce bloc » : plus de silence quand un
  Template existe deja** (retour 19/09/2026) : information affichee avec
  un bouton « Aller au Template » qui ouvre Templates.ecf et selectionne
  le bloc existant ; comparaison des noms desormais insensible a la
  casse (menu, flux post-fusion et garde interne de creation). Le flux
  post-fusion reste silencieux de son cote (la proposition n'est pas
  rejouee).
- **Lenteur generale de l'application (mesuree, vecue 19/09/2026)** :
  deux sources d'I/O disque dans les chemins chauds :
  - `vanilla_memory._ensure_built` relisait et re-parseait le JSON ENTIER
    de la memoire vanille (~4 Mo) a CHAQUE consultation — 17 ms par
    appel, x 9 267 lignes d'un PDA.csv = **158 s de blocage** au
    chargement d'un CSV (coloration vanille) et +17 ms par cellule dans
    chaque traduction. L'index est desormais construit/lu UNE fois par
    session (la fraicheur des sources du jeu est re-evaluee au
    prochain lancement) ; mesure apres correctif : 0,24 ms/appel (70x).
  - `settings.json` etait relu et re-parse a CHAQUE appel de reglage
    (moteur, permission en ligne, chemin vanille... y compris par
    cellule). Cache memoire avec invalidation par mtime : une edition
    manuelle ou externe du fichier reste prise en compte. 0,10 ms ->
    0,02 ms par lecture, sur l'ensemble de l'application.

## [1.9.0] — 2026-09-18

### Ajoute
- **Autocompletion des items dans les dialogues** (backlog) : dans
  Dialogues.ecf, pendant la saisie d'une valeur Execute/OptionExecute/
  OptionIf/NextIf, taper l'apostrophe d'un Id dans AddItem('...'),
  RemoveItem('...') ou HasItem('...') propose les items du catalogue
  (scenario + vanille), avec filtre contenant — formes relevees sur le
  vrai Dialogues.ecf vanille.

### Change
- **Refactoring main_window (premiere tranche)** : les vues lecture seule
  `EcfViewWidget` et `YamlViewWidget` quittent gui/main_window.py pour
  gui/view_widgets.py (noms re-exportes, zero changement de comportement).
  La suite du refactoring (mixins menus/toolbar, deplacement de la logique
  metier des dialogues de duplication/resolution de conflits vers core/)
  reste a faire en session dediee — l'etat partage avec MainWindow est
  trop entrelace pour un deplacement mecanique sur.

## [1.8.0] — 2026-09-18

### Ajoute
- **Traduction par LOTS pour le moteur Groq** (Options > Traduction >
  « Traduction par lots (moteurs IA) », activee par defaut) : plusieurs
  cellules traduites par requete, bornes 8 cellules / 4 000 caracteres par
  lot — le tier gratuit (30 req/min) couvre d'autant plus de cellules.
  Squelette de jetons verifie par cellule : une cellule deviante repasse
  automatiquement en mode cellule entiere, puis fragments — jamais de
  fichier corrompu ; une enveloppe manquante ne fait replier que la
  cellule fautive.
- **Style / ton des traductions** (assistant Groq, champ libre) : consigne
  injectee dans chaque requete (registre, tutoiement, terminologie),
  max 500 caracteres.
- **Progression de traduction dans le tableau de bord** : % de cellules
  traduites (source EN -> langue cible des options) par CSV de langue,
  total global + detail par fichier.
- Affichage du libelle du moteur Groq rafraichi au changement de langue
  (oublie dans le rafraichissement i18n des menus, v1.7.0).

### Corrige
- Les tests du worker forcent desormais le moteur (piege documente : ne
  jamais supposer les reglages reels de la machine de dev).

## [1.7.1] — 2026-09-18

### Ajoute
- Job de TESTS dans la CI : la suite pytest tourne desormais a chaque tag
  AVANT la construction de l'installeur (Python 3.14 bloquant, 3.12
  informatif) + audit i18n ; le build ne se lance plus si les tests sont
  rouges.
- `pyproject.toml` (configuration ruff + coverage) et
  `requirements-dev.txt` : les outils de developpement ne polluent plus
  les dependances runtime.
- `CHANGELOG.md` (ce fichier).

### Change
- Les donnees du protocole de test manuel quittent `core/` pour un paquet
  dedie `protocol/` (`protocol/cases.py` + `protocol/cases_en.py`,
  ex-`core/test_protocol*.py`) — ~5 200 lignes de donnees hors du moteur.
  Le shim `tools/protocole_cas.py` est conserve.

### Corrige
- 6 bugs latents remontes par ruff (F821) :
  - `gui/scenario_compare_dialog.py` : NameError au clic sur un fichier
    differant (variable `nl` jamais definie) — crash natif possible avec
    PyQt6 6.11 ;
  - `gui/block_library_dialog.py` : export de bloc inutilisable
    (combo jamais cree dans le dialogue de choix de fichier) ;
  - `gui/block_info_card_widget.py` : NameError sur les chemins d'erreur
    de traduction de la fiche info (`QMessageBox` non importe) ;
  - `gui/cross_reference_dialog.py` : correction de reference de dialogue
    impossible (`apply_dialogue_ref_fix` non importe) ;
  - `core/spellcheck.py` / `core/translation.py` : annotations `Tuple` /
    `Optional` non importees.

## [1.7.0] — 2026-09-18

### Ajoute
- Moteur de traduction **Groq** (LLM en ligne compatible OpenAI, tier
  gratuit permanent) : assistant compte/cle avec liens cliquables,
  modele recommande preconfigure (Qwen 3.8 27B), compteur de quota en
  direct dans la barre de progression, cooldown anti-429 respectant
  retry-after/reset, throttle sous les 30 requetes/minute.
- Mode **CELLULE ENTIERE** pour les moteurs LLM : une requete par cellule
  avec texte protege en jetons, squelette verifie, repli automatique par
  cellule sur le pipeline fragmente si divergence — 5 a 10 fois moins de
  requetes.
- User-Agent obligatoire sur les appels API (Cloudflare 1010 sinon).

### Change
- README et textes de presentation Discord/Steam a jour v1.7.0.

## [1.6.9] — 2026-09-17

### Ajoute
- **Revisions interruptibles et reprenables** (sessions par CSV, traduction
  ET Grammalecte) : application au fil de l'eau, sauvegarde/reprise par cle
  de ligne, proposition de reprise a l'ouverture.
- **Traductions vanille colorees en vert** : memoire officielle Eleon
  generee depuis Localization.csv, PDA.csv et Dialogues.csv.
- **Correcteur Grammalecte** : cellule/colonne/fichier, revue cochable,
  auto-fix avant validation, lexique d'ignorance persistant.
- **Glossaire terminologique** moteur-agnostique avec auto-alimentation des
  cellules courtes validees.
- Presse-papiers en barre CSV (copier/couper/coller).

### Change
- Menus reorganises (Options en sous-menus, Centre de verification en tete,
  Outils en groupes) ; moteur en radios exclusives Google/Argos/NLLB avec
  variantes 600M/1.3B et finesse de decodage beam 2/4/8.
- Pipeline durci : balises de dialogue `[X :]`, jetons glossaire et nombres
  isoles jamais envoyes aux moteurs (hallucinations reelles corrigees) ;
  Azure retire.
- Memoire alimentee a la VALIDATION uniquement + memoire vanille consultee
  en repli.

## [1.6.8] — 2026-09-16

- Installeur : choix du dossier d'installation toujours propose.
- 69 infobulles PDA FR/EN basees sur le guide officiel.

## [1.6.7] — 2026-09-15

- Selecteur d'items sur les cles ECF referencant des items (inventaire
  RE2/Atlantis/vanille) + catalogue quasi instantane (9,2 s -> 1,1 s).

## [1.6.6] — 2026-09-14

- Moteur Argos hors ligne fonctionnel DANS l'exe installe (pip embarque
  in-process).

## [1.6.4] — 2026-09-12

- Pilote Fluent Widgets (toolbar adaptative, recherche d'arbres, theme
  Nuit Fluent) + correctif parseur commentaires `/* */` inline.

## [1.6.3] — 2026-09-11

- Correctif bloquant : NameError a l'ouverture de l'editeur d'economie
  dans l'exe installe.

## [1.6.2] — 2026-09-10

- Module economie (marchands PNJ) + catalogue d'icones + retours RE2.

## [1.6.0] — 2026-09-09

- Garde-fou de coherence de version (installeur nomme correctement).

## [1.5.1] — 2026-09-08

- Protocole de test embarque dans l'application + statut persistant.

## Versions anterieures

Historique detaille dans les messages de commit
(https://github.com/Daflo-Empyrion/Scenario-Editor/tags) : fiche info
inline, recherche scenario, workspace + annulation, bibliotheque de blocs,
dashboard, backups versionnes, editeur playfield 8 onglets, carte 2D,
galaxie, arbre technologique, themes Relief...
