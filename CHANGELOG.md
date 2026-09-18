# CHANGELOG — Empyrion Scenario Editor

Tous les changements notables du projet sont documentes ici.
Format inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
versionnement [SemVer](https://semver.org/lang/fr/) (`vX.Y.Z`).

## [1.7.1] — Non publiee

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

## [1.9.0] — Non publiee

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

## [1.8.0] — Non publiee

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
