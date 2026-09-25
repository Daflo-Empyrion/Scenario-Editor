# CHANGELOG — Empyrion Scenario Editor

Tous les changements notables du projet sont documentes ici.
Format inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
versionnement [SemVer](https://semver.org/lang/fr/) (`vX.Y.Z`).

## [1.12.0] — Non publiee

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
