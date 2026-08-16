# Wiki de l'application — Empyrion Scenario Editor

Documentation de reference de toutes les fonctions de l'outil, organisee par theme.
Pour un parcours guide pas a pas, voir plutot **Aide > Tutoriels...** dans
l'application — ce wiki est concu pour etre consulte en cherchant un point precis,
pas necessairement lu dans l'ordre.

---

## 1. Premier lancement et langue

Au tout premier demarrage de l'application (jamais ensuite), un ecran bilingue
demande de choisir la langue de l'interface (Francais / English) — ce choix est
immediatement applique, modifiable a tout moment par la suite via le bouton **FR/EN**
en haut a droite de la fenetre principale. Le choix n'est demande qu'une seule fois ;
les lancements suivants demarrent directement dans la langue choisie.

A la suite de ce choix (et a chaque lancement suivant, sauf desactivation), le
**module de tutoriels** s'ouvre automatiquement avec un bandeau rappelant qu'il est
accessible a tout moment via **Aide > Tutoriels...**, et une case a cocher
**"Ne plus afficher automatiquement au demarrage"** — une fois cochee, l'ouverture
automatique cesse definitivement (reactivable uniquement en supprimant le fichier de
parametres de l'application).

---

## 2. Projets : creer, ouvrir, structure des trois panneaux

### Nouveau projet
**Fichier > Nouveau projet...** demande trois champs :
- **Scenario A** (obligatoire) — le dossier du scenario source, jamais modifie
- **Scenario B** (optionnel) — un deuxieme scenario de reference
- **Destination de la copie de travail** — ou sera creee la copie modifiable (ne
  doit pas deja exister)

A la creation, l'outil copie **integralement et a l'identique** le Scenario A dans
le dossier de destination (tous les fichiers, pas seulement les .ecf/.csv/.yaml).
Rien n'est invente ni transforme a la copie.

### Projets recents
**Fichier > Projets recents...** (egalement propose automatiquement au demarrage)
reprend un projet existant **sans recopier** la copie de travail — tes
modifications precedentes restent intactes. Utile pour continuer un travail sur
plusieurs sessions.

### Les trois panneaux
- **Scenario A** (a gauche) — source d'origine, **lecture seule**, jamais modifiee
- **Copie de travail** (au centre) — la seule zone modifiable, tout ton travail se
  fait ici
- **Scenario B** (a droite, optionnel) — deuxieme source de reference, egalement
  lecture seule

Les trois panneaux affichent **l'arborescence exacte du disque** — comme un
explorateur de fichiers classique, aucune categorisation artificielle.

### Gerer le Scenario B en cours de route
- **Fichier > Ouvrir un Scenario B...** — apparait quand aucun B n'est actif
- **Fichier > Changer le Scenario B...** — meme menu, renomme automatiquement une
  fois un B actif ; demande confirmation avant remplacement
- **Fichier > Retirer le Scenario B** — desactive le panneau B ; la copie de
  travail n'est jamais affectee

---

## 3. Ouvrir et naviguer dans un fichier

**Double-clique** n'importe quel fichier dans l'un des trois panneaux pour l'ouvrir
dans un nouvel onglet. Les fichiers ouverts depuis Scenario A/B sont en **lecture
seule** ; ceux ouverts depuis la copie de travail sont **editables**. Un onglet deja
ouvert pour un fichier se selectionne au lieu de s'ouvrir en double.

Types geres : **.ecf** (blocs, items, config), **.yaml/.yml** (playfields,
planetes...), **.csv** (traductions, tables), **.txt** (texte brut).

### L'arbre des blocs (ECF)
- **Groupes de section** : si le fichier source utilise des commentaires de
  separation (`# ===...===` / titre / `# ===...===`), l'arbre affiche des en-tetes
  de categorie en gras (reperes visuels uniquement, pas cliquables)
- **Etiquettes lisibles** : un commentaire `## NomLisible` juste avant un bloc
  apparait entre parentheses a cote de son identifiant technique
- **Recherche** : par Id, Name, ou CustomIcon, avec navigation au resultat suivant
  (Entree)

---

## 4. Editer un fichier ECF

### Le tableau de proprietes — deux modes
- **Mode liste classique** (majorite des blocs) — une ligne par propriete, double-
  clic sur la valeur pour editer
- **Mode tableau** (structures repetitives type *Child Items*, *LootGroups*,
  *DamageMultiplier*...) — detecte automatiquement toute suite d'entrees numerotees
  (`Name_0`, `Name_1`... ou `Item_0`, peu importe le prefixe utilise par le
  fichier), affiche une colonne par parametre. Le bouton **"+ Ligne"** remplace
  alors **"+ Propriete"**.

### Ajouter
- **+ Bloc** — cree un bloc entierement vide (genre a choisir : Block, Item...)
- **+ Propriete** — ajoute une propriete au bloc selectionne ; plusieurs paires
  peuvent etre tapees en une fois (`valeur, param1: X, param2: "Y,Z"`) pour rester
  groupees sur la meme ligne comme le fait le jeu
- **+ Ligne** (mode tableau uniquement) — formulaire dedie (Type/Valeur/params),
  numerotation et position calculees automatiquement

### Supprimer et desactiver
- **Supprimer** (clic droit) — retire definitivement l'element, confirmation
  demandee pour un bloc entier
- **Desactiver ce bloc (test)** (clic droit sur un bloc) — commente le bloc **a sa
  position exacte** (jamais deplace), sans le supprimer ; utile pour isoler une
  cause de plantage par elimination
- **Blocs desactives (test)** (bouton) — liste tous les blocs desactives du
  fichier, avec **Reactiver** par entree

### Filtrer et comprendre
- **Filtrer par propriete...** — n'affiche que les blocs possedant (ou non)
  certaines proprietes precises
- **Panneau "Voir l'explication des proprietes de ce fichier"** (repliable, sous le
  nom du fichier) — glossaire clarifie en francais fait main pour 17 fichiers
  (BlocksConfig.ecf, ItemsConfig.ecf, Templates.ecf, GalaxyConfig.ecf,
  GlobalDefsConfig.ecf, LootGroups.ecf, MaterialConfig.ecf, StatusEffects.ecf,
  TokenConfig.ecf, TraderNPCConfig.ecf, BlockGroupsConfig.ecf, Containers.ecf,
  DamageMultiplierConfig.ecf, DefReputation.ecf, EGroupsConfig.ecf, Factions.ecf,
  FactionWarfare.ecf) ; pour les autres, un bouton traduit automatiquement le
  texte original

### Annotations automatiques
Toute modification de valeur est annotee (si active dans Options) :
`# original: <ancienne_valeur> -- Mod par <toi>`.

---

## 5. Editer un fichier YAML

Arbre de navigation a gauche (cle + apercu), panneau de valeur editable a droite.

- **+ Entree** / **Supprimer l'entree selectionnee**
- **Appliquer cette valeur** — valide le texte tape (aussi applique automatiquement
  au changement de selection ou a la sauvegarde, aucun risque de perte par oubli)
- **Chaines entre guillemets multi-lignes** : une ligne vide a l'interieur des
  guillemets devient un vrai retour a la ligne, pour un affichage correct en jeu
  (frequent pour les descriptions de playfield)

---

## 6. Editer un fichier CSV

- **Recherche** avec selecteur de portee ("dans :" une colonne precise ou toutes) ;
  clic droit sur un en-tete de colonne pour y limiter directement une recherche
- **+ Ligne** / **Ligne selectionnee** (suppression)
- **Presse-papier** (clic droit) — Copier, Couper, Coller, Effacer le contenu,
  fonctionne sur une selection multiple façon tableur
- Le **delimiteur** (`,` ou `;`) et le **style de fin de ligne** sont detectes
  automatiquement et preserves

---

## 7. Traduction

Toutes les fonctions ci-dessous utilisent Google Translate (bibliotheque
`deep-translator`, gratuite, necessite une connexion internet) et protegent
automatiquement le BBCode et les placeholders (`{PlayerName}`, `%d`...) — jamais
traduits ni casses.

### Memoire de traduction
Entierement automatique et invisible : des qu'un texte est traduit une fois vers
une langue donnee, la meme traduction est reutilisee instantanement (sans nouvel
appel reseau) si ce texte exact revient ailleurs — plus rapide, et garantit une
coherence totale du meme mot dans tout le fichier.

### Cellule par cellule
Clic droit sur une cellule > **"Traduire vers"** > choisir une langue — montre un
apercu avant/apres, propose de remplacer la cellule elle-meme ou la colonne
correspondant a la langue cible sur la meme ligne si elle existe deja.

### Traduction rapide
Bouton **"Traduire"** (barre d'outils) — traduit directement la cellule/selection
courante vers la **langue par defaut** (Options > "Langue de traduction par
defaut..."), sans sous-menu. Bascule automatiquement en lot si plusieurs cellules
sont selectionnees.

### En lot (selection multiple)
Selection multiple + clic droit > **"Traduire la selection vers..."** — barre de
progression, puis tableau de revue avant application.

### Combler les langues manquantes
Bouton dedie — choisis une colonne source (remplie) et une colonne cible (a
completer) ; scanne tout le fichier, ne traduit que les cellules vraiment vides.

### Tableau de revue et gestion des echecs
Toute traduction en lot passe par un tableau (cases a cocher, texte modifiable
avant validation) — rien n'est ecrit sans confirmation. Sur un tres gros lot, si le
service se bloque temporairement, l'arret est **automatique apres 5 echecs
consecutifs** avec message clair ; les traductions deja reussies restent
disponibles ; les echecs sont surlignes en rouge et decoches par defaut.

---

## 8. Rechercher et remplacer (CSV)

Bouton **"Rechercher et remplacer..."** — corrige un texte repete a plusieurs
endroits (typiquement une traduction automatique approximative) :
- **Rechercher** / **Remplacer par**
- **Dans la colonne** — une colonne precise ou toutes
- **Respecter la casse**
- **Mot entier seulement** — evite de toucher un mot qui contient seulement le
  texte cherche comme fragment

Comme pour la traduction, chaque correspondance passe par le tableau de revue.

---

## 9. Mise en forme BBCode

Clic droit > **"Mise en forme BBCode..."** — selectionne une portion de texte,
clique une couleur (palette de 10 teintes) ou un style (Gras/Italique/Souligne)
pour l'entourer automatiquement des bonnes balises (`[color=#FF0000]...[/color]`,
`[b]...[/b]`...).

---

## 10. Copier, fusionner et dupliquer depuis Scenario A ou B

### Copier/fusionner
Clic droit (fichier, dossier, bloc, ligne, entree) > **"Copier / fusionner vers la
copie de travail"** — combine le contenu source avec la copie de travail.
**Desactive par defaut** (trop de cas particuliers pour etre fiable a 100%),
reactivable dans **Options > "Autoriser la fusion"**.

Comportement par type de fichier :
- **.ecf** deja existant : fusion intelligente par bloc — la copie de travail est
  toujours prioritaire (rien n'est ecrase), les blocs/proprietes absents sont
  ajoutes
- **.csv** deja existant : fusion par cle (1ere colonne) — une ligne existante
  n'est jamais ecrasee, seules les cellules vides sont completees, les lignes
  absentes sont ajoutees
- **Autres formats** (yaml, txt...) : simple copie qui remplace le fichier existant

**Garde-fou anti-collision** : si un Id est partage entre deux blocs dont le `Name`
differe, le bloc n'est jamais fusionne a l'aveugle — il est ajoute en fin de
fichier, **desactive**, pour revue manuelle (voir "Blocs en attente" ci-dessous).

### Dupliquer
Clic droit (fichier, bloc, ligne, entree) > **"Dupliquer avec un nouvel Id/une
nouvelle cle..."** — **toujours disponible**, cree systematiquement une copie
**independante** (nouvel Id/nouveau nom, suggestions d'Ids libres fournies), sans
jamais ecraser quoi que ce soit. Fonctionne aussi sur des blocs sans Id (identifies
seulement par `Name`), permet d'abandonner l'Id du duplicata pour ne l'identifier
que par Name, et garde un sous-bloc imbrique dans le meme bloc parent.

### Annuler une fusion/duplication
Bouton global **"Annuler la derniere action"** (en haut de la fenetre, distinct du
"Annuler (Ctrl+Z)" propre a chaque onglet).

---

## 11. Verifications

### Verifier les references
**Verification > Verifier les references** — controle que chaque `Ref:`,
`TemplateRoot` et reference similaire pointe vers un nom existant.

### Blocs en attente
**Verification > Blocs en attente** — liste tous les blocs mis en attente par le
garde-fou anti-collision, avec comparaison detaillee (bloc actuel vs en attente) et
suggestions d'Ids libres pour l'activer proprement.

---

## 12. Sauvegardes

### Sauvegardes de scenario
**Fichier > Sauvegarder un scenario (avant mise a jour)...** — copie complete
avant qu'une mise a jour Steam Workshop n'ecrase le scenario en place.

### Sauvegardes de partie
**Fichier > Gerer mes sauvegardes de partie...** — meme principe pour la
progression de partie, avec **Restauration** (une sauvegarde de securite est
automatiquement creee avant toute restauration).

Le gestionnaire propose dans les deux cas : Sauvegarder maintenant, Restaurer,
Ouvrir le dossier, Supprimer (confirmation demandee), et pour les scenarios
uniquement, **Comparer avec...** (ouvre directement l'outil de comparaison).

---

## 13. Comparer deux scenarios

**Fichier > Comparer deux scenarios...** — independant du projet ouvert, compare
n'importe quels deux dossiers :
- Arbre colore par statut (ajoute / retire / modifie / identique)
- Detail precis des changements (bloc par bloc pour l'ECF, ligne par ligne pour le
  CSV, cle par cle pour le YAML)
- **Afficher aussi les fichiers identiques** (case a cocher)
- **Exporter le rapport...** (fichier texte complet)

---

## 14. Extraire les proprietes du scenario

**Fichier > Extraire les proprietes du scenario...** — parcourt tous les fichiers
.ecf d'une source (copie de travail, Scenario A ou B) et construit un glossaire de
travail CSV :
- Chaque propriete, avec occurrences, fichiers concernes, exemples de valeurs, et
  description automatique quand reconnue sans ambiguite
- Les cles numerotees (`Name_0`, `Name_1`...) sont regroupees sous une entree
  generique (`Name_N`)
- Une colonne **"Valeur cible"** vide, a completer au fil de la reflexion de
  conception

Le fichier resultat s'ouvre automatiquement, directement editable.

---

## 15. Maintenance

### Reparer les permissions
**Fichier > Reparer les permissions de la copie de travail** — deverrouille
instantanement une copie de travail devenue impossible a modifier/supprimer
(attribut lecture-seule herite de la source, frequent sous Program Files). Chaque
sauvegarde de fichier tente deja cette reparation automatiquement en
arriere-plan ; ce bouton n'est utile que dans de rares cas residuels.

---

## 16. Options

Menu **Options**, reglages globaux valables pour tous les projets :
- **Nom pour les annotations...** — nom utilise dans les commentaires automatiques
- **Annoter les modifications automatiquement** (case a cocher)
- **Autoriser la fusion** (case a cocher, desactivee par defaut)
- **Langue de traduction par defaut...** — langue utilisee par le bouton "Traduire"
  rapide

---

## 17. Aide

- **Aide > Tutoriels...** — module de tutoriels pas a pas integre, navigable
  (Precedent/Suivant), avec au minimum "Creer un bloc, pas a pas" et "Prise en main
  complete de l'application"
- **Aide > Wiki de l'application (fonctions)...** — ce document
- **Aide > Wiki Empyrion (proprietes, fichiers, structure)...** — documentation du
  jeu lui-meme (structure des fichiers, conventions, pieges connus)

---

## 18. Scripts de diagnostic (ligne de commande)

Complements a l'interface, a lancer depuis un terminal dans le dossier du projet :

| Script | Usage |
|---|---|
| `verifier_parser_ecf.py <fichier_ou_dossier>` | Verifie le round-trip (fidelite parfaite) d'un ou plusieurs fichiers ECF |
| `verifier_parser_yaml.py <fichier_ou_dossier>` | Meme chose pour le YAML |
| `verifier_parser_csv.py <fichier_ou_dossier>` | Meme chose pour le CSV |
| `diagnostic_bloc.py <fichier.ecf> <Id>` | Cherche un bloc precis par Id, y compris dans les commentaires |
| `detecter_imbrication_anormale.py <fichier.ecf>` | Detecte les blocs qui ont "avale" le reste du fichier par erreur |
| `diff_ecf.py <fichierA.ecf> <fichierB.ecf>` | Compare deux fichiers ECF, affiche les blocs ajoutes/supprimes/modifies |
| `edit_ecf.py <fichier.ecf>` | Editeur ECF interactif en ligne de commande |
| `merge_ecf.py <sortie.ecf> <source1> <source2>...` | Fusionne plusieurs fichiers ECF par ordre de priorite |
| `transform_ecf.py` | Applique une transformation numerique en masse (multiplier/ajouter/fixer/plafonner) sur une propriete, pour un genre de bloc donne |

---

## 19. Limitations connues

- Pas de copier/coller multi-lignes façon tableur pour le YAML (structure trop
  imbriquee)
- La fusion "intelligente" (priorite copie de travail, completion) n'existe que
  pour ECF et CSV — les autres formats sont remplaces entierement lors d'une fusion
  de fichier
- La traduction necessite une connexion internet (Google Translate, service
  gratuit non officiel — peut se bloquer temporairement sur de tres gros volumes,
  voir section 7)
