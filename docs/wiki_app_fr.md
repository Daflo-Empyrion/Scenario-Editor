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
- **+ Bloc** — creation guidee en plusieurs etapes : choix Id+Name ou Name
  seul, puis un tableau de proprietes a cocher, issues du fichier de travail
  lui-meme (triees par frequence d'usage reelle, avec la valeur la plus
  courante proposee comme point de depart) — un champ de recherche permet de
  filtrer les proprietes si elles sont nombreuses. A la validation, propose
  de creer directement le **Template associe** (recette de craft) si
  `Templates.ecf` existe dans le scenario : meme mecanisme de tableau, avec
  le Name pre-rempli pour correspondre exactement au bloc/item cree, et une
  section **Ingredients** ou chaque ligne se choisit par liste deroulante
  (items et blocs reellement definis dans le scenario, jamais de saisie
  libre), avec la meme case a cocher **"Uniquement les blocs autorises aux
  joueurs"** que pour LootGroups.ecf. L'Id est verifie en direct contre la
  limite du jeu et les doublons deja presents dans le fichier.
- **+ Propriete** — ajoute une propriete au bloc selectionne ; plusieurs paires
  peuvent etre tapees en une fois (`valeur, param1: X, param2: "Y,Z"`) pour rester
  groupees sur la meme ligne comme le fait le jeu
- **+ Ligne** (mode tableau uniquement) — formulaire dedie (Type/Valeur/params),
  numerotation et position calculees automatiquement. Le champ Valeur devient
  un menu deroulant des vrais items/blocs du scenario (ItemsConfig.ecf/
  BlocksConfig.ecf) plutot qu'une saisie libre — disponible sur **tous les
  fichiers en mode tableau**, pas seulement LootGroups.ecf ; le champ reste
  editable dans tous les cas si les suggestions ne conviennent pas. Case a
  cocher **"Uniquement les blocs autorises aux joueurs"** pour exclure les
  blocs reserves aux POI (ceux sans propriete `AllowPlacingAt`) — les items
  restent toujours proposes, ce concept ne s'applique qu'aux blocs.

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

### Transformation en masse
Bouton **"Transformation en masse..."** (barre d'outils) — modifie numeriquement
plusieurs valeurs d'un coup, pour une meme cle de propriete (ex: `param1`,
`Count`, `HitPoints`) :
- **Choisir la propriete** — tape directement son nom (autocompletion parmi les
  cles reellement presentes dans le fichier ouvert), ou coche-la dans la liste
  juste en-dessous du champ, qui indique aussi le nombre d'occurrences de
  chaque propriete
- **Operations** : Multiplier, Ajouter, Fixer a une valeur, Plafonner (min/max),
  Arrondir
- **Filtres optionnels** : par genre de bloc (ex: `+Container`), et/ou par liste
  d'identites precises (Id/Name separes par des virgules)
- **Recursif par defaut** — descend aussi dans les sous-blocs (*Child Items*
  notamment) ; decochable
- **Tableau de revue complet** — l'apercu affiche TOUTES les valeurs concernees
  (jamais tronque), une ligne par valeur, chaque bloc identifie par son **Id et
  son Name ensemble** quand les deux existent (facile a reconnaitre plutot
  qu'un numero seul), avec case a cocher pour l'inclure ou non et **colonne
  "Apres" librement modifiable** avant validation : pratique pour un cas
  particulier qui doit s'ecarter de la regle generale (ex : `MaxCount` doit
  rester a 1 sur certains blocs a cause d'une limite du moteur du jeu, meme si
  la regle globale multiplie tout le reste par 2)
- Boutons **"Tout cocher"** / **"Tout decocher"**
- S'integre au **Annuler (Ctrl+Z)** normal de l'onglet comme n'importe quelle
  autre modification

---

## 4bis. Cas particulier -- Dialogues.ecf

Ouvrir un fichier nomme exactement `Dialogues.ecf` bascule automatiquement sur
un conteneur a deux onglets plutot que l'edition ECF seule :

- **Navigateur de dialogues** — vue structuree et navigable, en lecture seule.
  Liste filtrable de tous les dialogues a gauche ; a droite, pour le dialogue
  selectionne : PNJ, texte affiche, variables (avec leur type), scripts
  executes, transitions automatiques (`Next_N`/`NextIf_N`) et choix proposes
  au joueur (`Option_N`/`OptionNext_N`/`OptionIf_N`/`OptionExecute_N`) --
  chaque cible de transition ou de choix est **cliquable**, navigue
  directement vers le dialogue vise sans avoir a le chercher soi-meme dans
  une liste de plusieurs milliers d'entrees. Les cibles cassees (dialogue
  inexistant) s'affichent en rouge ; les sentinelles reservees
  (`End`, `GotoAndReset`, `Return`) sont grisees, non cliquables. Une section
  **"Reference par (N)"** liste tous les dialogues qui menent vers celui
  affiche.
- **Edition ECF** — le meme editeur generique que pour tout autre fichier
  .ecf, pour la modification reelle (le navigateur reste lecture seule). Les
  deux onglets partagent le meme document en memoire ; une modification faite
  cote edition se reflete automatiquement dans le navigateur en revenant sur
  son onglet, ou apres enregistrement.

---

## 5. Editer un fichier YAML

Arbre de navigation a gauche (cle + apercu), panneau de valeur editable a droite.

- **+ Entree** / **Supprimer l'entree selectionnee**
- **Appliquer cette valeur** — valide le texte tape (aussi applique automatiquement
  au changement de selection ou a la sauvegarde, aucun risque de perte par oubli)
- **Chaines entre guillemets multi-lignes** : une ligne vide a l'interieur des
  guillemets devient un vrai retour a la ligne, pour un affichage correct en jeu
  (frequent pour les descriptions de playfield)

### Edition structuree des playfields (Ressources, POI, Creatures)
Tout fichier nomme `playfield*.yaml` (planetes : `playfield.yaml`,
`playfield_static.yaml`, `playfield_dynamic.yaml`) ou `space*.yaml` (secteurs
spatiaux : `space_dynamic.yaml`) s'ouvre automatiquement avec un editeur
specialise a **4 onglets**, plutot que l'editeur YAML generique ci-dessus.
Un bouton **"Enregistrer (Ctrl+S)"** reste visible en permanence en haut,
quel que soit l'onglet actif -- ainsi qu'un indicateur "Modifications non
enregistrees" -- pour ne jamais avoir a chercher la sauvegarde dans l'onglet
"YAML complet" apres une modification faite depuis un autre onglet :
- **Ressources** — trois tableaux distincts, chacun avec sa propre liste
  deroulante d'ajout (jamais de saisie libre) :
  - **Ressources aleatoires** (`RandomResources`) et **Ressources
    d'asteroides** (`AsteroidResources`) — playfields planete, liste peuplee
    depuis les vrais blocs `*Resource` de `BlocksConfig.ecf`
  - **Ressources spatiales** (`Resources`) — playfields espace uniquement,
    structure differente (variantes `AsteroidVoxel01/02/03<Materiau>`, nom
    lisible via `DisplayName`) — liste peuplee avec le meme materiau de base
    (Fer, Cuivre...) que les ressources planete, colonne **RegenAfter**
    (delai avant reapparition) directement editable
- **POI** et **Creatures** — tableau des entrees deja presentes (delais,
  difficulte, distances, quantites...), colonnes triees par frequence
  d'usage. **Modification uniquement** : pas d'ajout d'un nouveau POI/creature
  par selection de type, faute de source fiable pour peupler une telle liste
  (voir le wiki Empyrion, section 5, pour EPD si tu as besoin d'aller plus
  loin sur ce point precis).
  - POI : colonne **RegenAfter** directement editable (imbriquee dans
    `Properties` sur le fichier d'origine, exposee ici comme une colonne a
    part entiere)
  - Creatures : colonne **Biome** (lecture seule) — indispensable des qu'un
    meme nom de creature apparait dans plusieurs zones de biome differentes
    avec des parametres differents, sinon impossible a distinguer
  - Les autres valeurs structurees imbriquees (ex: `Position`) restent non
    editables ici, modifiables via l'onglet "YAML complet"
- **Drones/Vaisseaux** — modification des entrees deja presentes uniquement,
  meme raisonnement que POI/Creatures (aucune source fiable pour une liste
  deroulante de nouveaux types) :
  - **Garnison de base de drones** (planete, `DroneBaseSetup > Stock`) —
    Name + Amount
  - **Drones de patrouille libres** (espace, `FreeDrones`) et **Vaisseaux
    spatiaux** (espace, `SpaceVessels`) — structure la plus riche du module
    (Faction, CountMinMax, Probability...), les champs les plus imbriques
    (`MissionDescription`, `StockDescription`) restent non editables ici
  - Chaque tableau reste vide si non pertinent pour le type de playfield
    ouvert (meme principe que l'onglet Ressources)
- **Zones de spawn** — modification des entrees existantes uniquement :
  - **Patrouilles de drones** (planete, `DroneSpawning > Random`)
  - **Modulation du taux d'apparition autour des POI** (`SpawnRateZones`)
  - **Creatures liees a un POI** (`SpawnZones`) — different de l'onglet
    Creatures, qui organise par biome plutot que par POI ; la sous-liste
    `Entities` reste non editable ici, voir "YAML complet"
- **Effets speciaux** — purement cosmetique (pollen, papillons, meteo...),
  sans impact sur le gameplay, mais couvert pour une coherence complete :
  **effets locaux par biome** (`SpecialEffectsLocal`) et **effets globaux**
  (`SpecialEffectsGlobal`)
- **YAML complet** — le meme editeur generique que ci-dessus, pour tout le
  reste du playfield (atmosphere, ciel, brouillard...) — partage le
  meme document en memoire que les vues structurees : une modification faite
  d'un cote est immediatement visible en changeant d'onglet.

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

### References croisees entre fichiers
**Verification > Verifier les references croisees...** — contrairement a
"Verifier les references" ci-dessus (qui ne regarde que `Ref:` au sein des
fichiers ECF), celle-ci controle que ce qu'un fichier mentionne existe
**reellement ailleurs** dans le scenario. Trois verifications independantes,
chacune activable/desactivable individuellement :
- **Heritage Ref** — identique a la verification classique ci-dessus, incluse
  ici pour tout verifier en un seul endroit
- **Items/blocs references** — chaque entree `Name_N` (Templates.ecf,
  Containers.ecf, LootGroups.ecf...) correspond-elle a un item ou un bloc qui
  existe reellement dans ItemsConfig.ecf ou BlocksConfig.ecf ? (les deux
  fichiers sont verifies ensemble : un bloc ramasse devient un item du meme
  nom, ils partagent le meme espace de noms)
- **Jetons** — chaque reference `Token:XXXX` correspond-elle a un jeton
  reellement defini dans TokenConfig.ecf ?
- **Dialogues** — chaque cible `Next_N`/`OptionNext_N` (et son eventuel
  `param1` co-occurrent sur la meme ligne) correspond-elle a un dialogue
  (`+Dialogue Name:`) qui existe reellement ? Les mots-cles reserves du
  moteur de dialogue (`End`, `GotoAndReset`, `Return`) et les references
  dynamiques a une variable de script (`@NomVariable`, resolue au moment de
  l'execution) ne sont jamais signales -- seules les vraies references
  cassees le sont.

Chaque probleme trouve indique le **chemin complet** du fichier concerne —
**double-clique un resultat pour ouvrir directement le fichier concerne et
naviguer jusqu'au bloc/sous-bloc exact**, cellule comprise, sans avoir a
chercher soi-meme ou se trouve le probleme.

### Valider les regles metier
**Verification > Valider les regles metier...** — contrairement aux deux
verifications ci-dessus (qui portent sur des references), celle-ci controle
des **valeurs** : limite d'Id du jeu (8192, confirmee via les notes de mise a
jour officielles Eleon v1.17), classes de conteneurs necessitant
`VolumeCapacity` (avec resolution de l'heritage `Ref:`), materiaux et
`HoldType` reconnus, virgules non protegees dans les listes
(`AllowPlacingAt`, `ChildBlocks`), format `BlockColor`, doublons d'Id/Name,
et quelques valeurs numeriques suspectes (`HitPoints`/`Mass`/`MaxCount`
negatifs ou nuls). Chaque regle est fondee sur une verification directe
contre de vrais fichiers du jeu ou une source officielle -- aucune supposee.

Certaines regles (materiaux, `VolumeCapacity`, doublons de Name) ne
s'appliquent qu'a `BlocksConfig.ecf` et `HoldType` qu'a `ItemsConfig.ecf` --
le meme mot ("Material", "Class: Container"...) designe des concepts
differents selon le fichier (ex: un conteneur de butin d'entite dans
`EClassConfig.ecf` n'a pas la meme regle qu'un conteneur de bloc), verifie
directement sur les fichiers reels du jeu avant d'ecarter cette confusion.

Double-clique un resultat pour ouvrir le fichier et naviguer jusqu'au bloc
concerne, comme pour les references croisees. Filtre erreurs/avertissements
disponible en haut du dialogue.

### Jetons potentiellement non utilises
**Verification > Jetons potentiellement non utilises...** — suggestion
directe d'un membre de la communaute (Begebum, commentaire Steam) : liste
les jetons definis dans `TokenConfig.ecf` mais jamais references
(`Token:XXXX`) ailleurs dans le scenario. Purement informatif, jamais une
erreur — certains jetons peuvent etre utilises implicitement par le jeu sans
reference explicite. Volontairement restreint aux jetons (contrairement aux
blocs/items generiques, dont l'absence de reference ne signifie rien — un
bloc de construction basique n'a pas besoin d'etre "reference" pour etre
utile, il est simplement place en jeu).

### Bilan de sante du scenario
**Verification > Bilan de sante du scenario...** — lance en un clic les 4
verifications ci-dessus et affiche un resume consolide (vert/aucun probleme
ou rouge/nombre de problemes par categorie), avec un bouton "Voir le
detail" qui ouvre la vraie fenetre complete correspondante. Ne reimplemente
aucun affichage — un simple point d'entree unique quand on veut un etat des
lieux rapide sans ouvrir les 4 fenetres une par une.

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

## 13bis. Rechercher dans tout le scenario

**Fichier > Rechercher dans le scenario...** — contrairement aux recherches
existantes (filtrer par propriete en ECF, recherche CSV) qui portent sur le
fichier ouvert, celle-ci parcourt **tous les fichiers de la copie de
travail** en une seule fois : ECF (genre, Id/Name, toutes les proprietes y
compris imbriquees), YAML de playfield (toutes les entrees), CSV (chaque
ligne). Double-clique un resultat pour ouvrir directement le fichier
concerne et naviguer jusqu'au bloc/entree exact — memes mecanismes de
navigation que les fenetres de verification.

Limitation connue : les resultats CSV ouvrent le fichier concerne sans
naviguer jusqu'a la ligne exacte (aucun mecanisme de selection de ligne
construit pour l'instant dans l'editeur CSV).

---

## 13ter. Creer une mission PDA

**Fichier > Nouvelle mission PDA...** — creation guidee d'une mission
(Chapitre PDA avec sa Tache et son objectif), localise automatiquement
`Extras/PDA/PDA.yaml` et `PDA.csv` dans le scenario ouvert. Structure
confirmee sur un vrai fichier (530 chapitres, memes auteurs que
`Dialogues.ecf`) : Chapitre > Tache > Action.

Deux types d'objectifs geres :
- **Tuer des ennemis** — noms des creatures/entites cibles (suggestions
  issues des noms deja utilises ailleurs dans le meme `PDA.yaml`, saisie
  libre possible), quantite requise
- **Detruire une structure OU miner une ressource** — meme mecanisme cote
  jeu (`BlockDestroyed`) : detruire le coeur d'une base/vaisseau ennemi et
  miner une ressource sont techniquement la meme chose (une ressource minee
  est un bloc detruit). Le champ **Types** distingue les deux (`CoreNPC`
  pour une structure ennemie, `IronResource`/`CopperResource`... pour une
  ressource) — suggestions issues des Types deja utilises dans le meme
  fichier. Pour le minage specifiquement, le champ **Noms des cibles** propose
  aussi automatiquement les vrais blocs de ressource planetaires
  (`BlocksConfig.ecf`, ex: `IronResource`) et les variantes d'asteroides
  spatiaux (`AsteroidVoxel01/02/03<Materiau>`, motif technique confirme des
  playfields spatiaux) — bascule automatiquement selon le type d'objectif
  choisi.

**Recompenses** : XP, UP (points de competence), Reputation (avec choix de
faction), ou Item (liste deroulante peuplee des vrais items/blocs du
scenario, meme infrastructure que le choix d'ingredients de Template, avec
la meme case a cocher "Uniquement les blocs autorises aux joueurs") —
plusieurs recompenses possibles par mission. Pour recompenser en argent :
choisis **`MoneyCard`** s'il est propose (mis automatiquement en tete de
liste s'il existe dans `ItemsConfig.ecf`) — 1 carte = 1 credit, confirme sur
un vrai fichier de scenario (commentaire `## Please do not rename -
referenced in code` juste au-dessus de sa definition). <span
style="color:#7c859c"><i>Le nom litteral "Credits" ne fonctionne PAS malgre
ce que suggere le wiki communautaire du jeu — infirme sur deux logs client
reels (v1.19.2) : la recompense est systematiquement rejetee par le
moteur.</i></span>

**Repetition** (mission a un seul palier uniquement) : case a cocher
"Mission repetable", avec nombre de repetitions et delai avant reactivation
(en heures) — correspond au mecanisme reel `RepeatConditions` du jeu (repete
IDENTIQUEMENT le meme objectif/la meme recompense).

**Paliers** — **"+ Ajouter un palier"** : pour une mission a etapes avec un
objectif/une recompense DIFFERENTS a chaque palier (ex: palier 1 = miner
1000 unites -> recompense X, puis palier 2 = miner 2000 unites -> recompense
Y, etc.), chaque palier obtient son propre titre, description, objectif et
recompenses. Mecanisme reel confirme sur une vraie chaine du jeu (50 -> 100
-> 35 kills sur 3 chapitres successifs) : chaque palier devient un
**Chapitre PDA distinct**, jamais une repetition du meme chapitre — le
premier est immediatement disponible, chaque suivant ne s'active qu'une fois
le precedent recompense (`RewardedChapters` + `Activatable: WhenRewarded`).
La case "Mission repetable" est automatiquement desactivee des qu'un second
palier existe : les deux mecanismes ne se combinent jamais dans le jeu.

Les fichiers sont ouverts comme de **vrais onglets** de la copie de travail
(jamais une ecriture directe sur disque) — rien n'est enregistre tant que tu
ne cliques pas toi-meme sur Enregistrer sur ces deux onglets.

<span style="color:#7c859c"><i>Limite assumee (objectif "Tuer des ennemis"
uniquement -- le minage beneficie de vraies suggestions, voir ci-dessus) :
les noms de cibles precis propres a un blueprint donne (ex: le nom
personnalise d'un bloc "coeur" specifique a l'interieur d'un vaisseau
ennemi particulier) ne sont pas extraits automatiquement des fichiers de
blueprint (`.epb`) -- meme famille de risques que les sauvegardes de partie
(format binaire proprietaire non documente, aucun outil communautaire sous
licence reutilisable). Seuls les noms deja utilises ailleurs dans le meme
`PDA.yaml` sont proposes comme suggestions ; la saisie libre reste toujours
possible.</i></span>

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
- **Traduction en ligne (Google Translate)** (case a cocher, activee par
  defaut) — decoche pour desactiver completement l'envoi de texte a Google ;
  voir `PRIVACY.md`
- **Sauvegarde automatique (recuperation apres plantage)** (case a cocher,
  activee par defaut) — voir section 12bis ci-dessous
- **Langue de traduction par defaut...** — langue utilisee par le bouton "Traduire"
  rapide

---

## 12bis. Sauvegarde automatique et recuperation apres plantage

Toutes les 3 minutes, chaque onglet modifie mais pas encore enregistre est
sauvegarde dans un dossier de recuperation **separe** de la vraie copie de
travail — jamais ecrit dans les vrais fichiers du scenario tant que
l'utilisateur ne clique pas explicitement sur Enregistrer. Des qu'un fichier
est reellement enregistre, son instantane de recuperation est aussitot
supprime.

Si l'application se ferme de facon inattendue (plantage, coupure de
courant...) alors que des instantanes de recuperation existent encore pour
un scenario, une fenetre propose de les **restaurer** (ecrit directement
dans les vrais fichiers de la copie de travail, avant que le moindre onglet
ne soit rouvert) ou de les **ignorer** definitivement — a l'ouverture ou a
la reprise de ce scenario.

Desactivable dans **Options > Sauvegarde automatique**.

---

## 16bis. Theme visuel

**Options > Theme** — 8 themes selectionnables, bascule immediate sans
redemarrer :
- **Classique** — theme d'origine (tableau de bord bleu/marine), reste le
  theme par defaut tant qu'aucun autre n'est choisi explicitement
- **A — Console de bord** — sombre, cyan/ambre, esthetique tableau de
  commande spatial
- **B — Table a dessin** — clair, bleu plan technique
- **C — Terminal d'ingenierie** — sombre chaud, cuivre/sarcelle
- **D — Cristal nocturne** — sombre, violet/cyan
- **E — Cristal solaire** — clair, violet/cyan
- **F — Crepuscule** — ardoise moyen, pense pour un usage confortable sur
  plusieurs heures (contraste modere, blanc casse plutot que blanc pur)
- **G — Nacre** — clair, degrade irise multicolore en bandeau de menu

<span style="color:#7c859c"><i>Limite assumee : ces themes sont une
approximation fidele en couleurs/degrades des maquettes originales, mais
sans le vrai flou d'arriere-plan (verre depoli) -- PyQt6 Widgets ne le
supporte pas nativement (necessiterait l'API Acrylic/Mica propre a Windows
11, ou une reecriture en Qt Quick/QML).</i></span>

---

## 17. Aide

- **Aide > Tutoriels...** — module de tutoriels pas a pas integre, navigable
  (Precedent/Suivant), avec au minimum "Creer un bloc, pas a pas" et "Prise en main
  complete de l'application"
- **Aide > Wiki de l'application (fonctions)...** — ce document
- **Aide > Wiki Empyrion (proprietes, fichiers, structure)...** — documentation du
  jeu lui-meme (structure des fichiers, conventions, pieges connus)
- **Aide > Verifier les mises a jour...** — verification manuelle ; une
  verification automatique et silencieuse a egalement lieu au demarrage (ne
  s'affiche que si une mise a jour existe reellement)
- **Aide > Signaler un bug / une amelioration...** — ouvre un formulaire GitHub
  pre-rempli dans le navigateur (titre, description, actions recentes,
  informations techniques comme la version et le systeme) ; **rien n'est envoye
  automatiquement**, il faut relire et cliquer "Submit" soi-meme sur la page
  GitHub. Une capture d'ecran (prise au moment du clic sur le menu) est
  enregistree localement dans `~/.empyrion_editor/bug_reports/` — a
  glisser-deposer dans le formulaire GitHub pour l'inclure (aucun moyen
  technique de la joindre automatiquement via un simple lien). **Aussi
  accessible directement via le bouton "Signaler" de la barre superieure**,
  sans passer par ce menu.
- **Aide > A propos...** — version de l'application, mention de licence, et le
  meme badge GPLv3 cliquable que celui de la barre superieure

### Raccourcis directs dans la barre superieure
En plus du menu Aide, deux boutons restent accessibles en permanence en haut de
la fenetre principale, a cote du bouton de langue FR/EN :
- **Bouton "Signaler"** — raccourci direct vers le formulaire de rapport de bug
- **Badge GPLv3** — clic direct vers le texte officiel de la licence en ligne

---

## 18. Scripts de diagnostic (ligne de commande)

Complements a l'interface graphique, disponibles de deux facons selon comment tu
as obtenu l'application :

### Si tu as installe via l'installeur Windows
Un seul executable regroupe tous les outils : `EmpyrionEditorCLI.exe`, installe
dans un sous-dossier `CLI\` du dossier d'installation (separe de l'appli
graphique pour eviter tout conflit entre leurs fichiers internes respectifs).
Depuis un terminal (Invite de commandes ou PowerShell), dans ce sous-dossier :

```
CLI\EmpyrionEditorCLI.exe <commande> [arguments...]
```

Lance-le sans argument pour voir la liste complete des commandes disponibles.

### Si tu utilises les sources Python directement
Chaque outil reste aussi disponible comme script independant, a lancer depuis un
terminal dans le dossier du projet :

| Commande (`EmpyrionEditorCLI.exe`) | Script equivalent (sources) | Usage |
|---|---|---|
| `verifier-ecf <fichier_ou_dossier>` | `python verifier_parser_ecf.py ...` | Verifie le round-trip (fidelite parfaite) d'un ou plusieurs fichiers ECF |
| `verifier-yaml <fichier_ou_dossier>` | `python verifier_parser_yaml.py ...` | Meme chose pour le YAML |
| `verifier-csv <fichier_ou_dossier>` | `python verifier_parser_csv.py ...` | Meme chose pour le CSV |
| `diagnostic-bloc <fichier.ecf> <Id>` | `python diagnostic_bloc.py ...` | Cherche un bloc precis par Id, y compris dans les commentaires |
| `detecter-imbrication <fichier.ecf>` | `python detecter_imbrication_anormale.py ...` | Detecte les blocs qui ont "avale" le reste du fichier par erreur |
| `diff <fichierA.ecf> <fichierB.ecf>` | `python diff_ecf.py ...` | Compare deux fichiers ECF, affiche les blocs ajoutes/supprimes/modifies |
| `edit <fichier.ecf>` | `python edit_ecf.py ...` | Editeur ECF interactif en ligne de commande |
| `merge <sortie.ecf> <source1> <source2>...` | `python merge_ecf.py ...` | Fusionne plusieurs fichiers ECF par ordre de priorite |
| `transform` | `python transform_ecf.py` | Applique une transformation numerique en masse (multiplier/ajouter/fixer/plafonner) sur une propriete, pour un genre de bloc donne |

---

## 19. Carte 2D, inspecteur de POI et carte de galaxie

### Carte 2D d'un playfield
Premier onglet de l'editeur de playfield structure (voir section 8) — vue
top-down (axe X/Z) des entites positionnables : POI fixes (deplacables par
glisser-deposer, avec ecriture directe dans le YAML), POI aleatoires resolus
(quand ils referencent un POI fixe via `SpawnPOINear`), points de depart
joueur, patrouilles de drones. Filtre par genre d'entite, zoom a la molette.

Certaines entrees n'ont volontairement **pas de position affichee** plutot
que d'en inventer une approximative : les ressources spatiales (le champ
`RadialInfo` n'est pas une coordonnee cartesienne directe, verifie sur un
vrai fichier), et la plupart des POI aleatoires (ils referencent le plus
souvent un autre POI aleatoire plutot qu'un POI fixe, chaine non resolue
dans cette premiere version).

### Inspecteur de POI
Bouton **"Inspecteur de POI..."** au-dessus du tableau de l'onglet POI —
fenetre non modale avec deux vues : detail par POI (quantite, drones
estimes) et agregation par faction (combien de drones au total pour chaque
faction sur ce playfield). Porte uniquement sur les POI aleatoires (les POI
fixes n'ont pas ces champs de comptage/probabilite). Export et actualisation
disponibles, comme les fenetres de verification.

### Carte de la galaxie
**Fichier > Carte de la galaxie (Sectors.yaml)...** — carte des systemes
solaires du scenario, localise automatiquement `Sectors/Sectors.yaml`.
Couleur violette pour les roles de systeme speciaux (Gate, Anomaly,
HomeSystem...), orange pour les vraies classes spectrales d'etoile (A, K2V,
M2...) ; taille du point proportionnelle au nombre de secteurs locaux du
systeme. Aucune route de warp n'est affichee entre systemes : ces donnees ne
sont pas declarees dans `Sectors.yaml` (probablement calculees par le moteur
du jeu selon la proximite), impossible a restituer de facon fiable.

Curseur **"Inclinaison (axe Y)"** sous la carte : la vue de base n'affiche
que X/Z (vue du dessus, hauteur galactique ignoree) -- augmenter
l'inclinaison decale visuellement chaque systeme selon son Y reel,
utile quand plusieurs systemes proches en X/Z (ex: le long d'une chaine de
balises) se chevauchent a l'ecran malgre une hauteur tres differente.

---

## 20. Limitations connues

- Pas de copier/coller multi-lignes façon tableur pour le YAML (structure trop
  imbriquee)
- La fusion "intelligente" (priorite copie de travail, completion) n'existe que
  pour ECF et CSV — les autres formats sont remplaces entierement lors d'une fusion
  de fichier
- La traduction necessite une connexion internet (Google Translate, service
  gratuit non officiel — peut se bloquer temporairement sur de tres gros volumes,
  voir section 7)
