# Wiki de l'application — Empyrion Scenario Editor

Documentation de toutes les fonctions de l'outil, organisee par theme.

---

## 1. Les bases : projets et copie de travail

### Nouveau projet
**Fichier > Nouveau projet...** — Choisis un Scenario A (obligatoire), et si tu veux fusionner deux scenarios, coche "Mode fusion" et choisis un Scenario B. Indique ensuite un dossier de destination (qui ne doit pas exister deja) : c'est ta **copie de travail**.

A la creation, l'outil copie **integralement et a l'identique** le Scenario A dans le dossier de destination (tous les fichiers, pas seulement les .ecf/.csv/.yaml). Rien n'est invente ni transforme a la copie.

### Copie de travail vs sources
- **Scenario A / Scenario B** : affiches en bas, en **lecture seule**. Ce sont tes references, jamais modifiees par l'outil.
- **Copie de travail** : affichee au milieu, **modifiable**. C'est le seul endroit ou tu edites, fusionnes, dupliques.

### Projets recents
**Fichier > Projets recents...** (ou automatiquement propose au demarrage) — reprend un projet existant **sans recopier** la copie de travail (tes modifications precedentes restent intactes). Utile pour continuer un travail en cours sur plusieurs sessions.

### Arborescence
Les trois panneaux (A, copie de travail, B) affichent **l'arborescence exacte du disque** — comme un explorateur de fichiers classique, pas de categorisation artificielle.

---

## 2. Fusionner depuis Scenario A ou B

### Fusionner un fichier entier
Clic droit sur un fichier dans Scenario A ou B > **"Copier / fusionner vers la copie de travail"**.

- Si le fichier n'existe pas encore dans la copie de travail : simple copie.
- Si c'est un **.ecf** deja existant : fusion intelligente par bloc (voir plus bas).
- Si c'est un **.csv** deja existant : fusion par cle (1ere colonne) — la copie de travail est **toujours prioritaire** : une ligne dont la cle existe deja n'est jamais ecrasee, seules les cellules **vides** sont completees ; les lignes absentes sont ajoutees.
- Les autres formats (yaml, txt...) : simple copie qui **remplace** le fichier existant (pas de fusion intelligente pour ces formats).

### Fusionner un dossier entier
Clic droit sur **n'importe quel dossier** > "Fusionner ce dossier (et sous-dossiers)" — applique la meme logique a tous les fichiers qu'il contient, en une seule action. Une barre de progression s'affiche pour les gros dossiers.

### Fusion ECF — comment ca marche precisement
- La copie de travail est **prioritaire** : ses proprietes et blocs existants ne sont jamais ecrases.
- Les blocs et proprietes **absents** de la copie de travail sont ajoutes.
- **Garde-fou anti-collision** : si un Id est partage entre deux blocs dont le `Name` differe (meme Id, materiel different — ca arrive entre scenarios independants), le bloc **n'est jamais fusionne a l'aveugle**. Il est ajoute en fin de fichier, **desactive** (commente), pour revue manuelle (voir "Blocs en attente" plus bas).

### Copier un seul bloc / une seule ligne
Clic droit sur un bloc ECF (dans l'arbre) ou une ligne CSV, dans la vue Scenario A/B > "Copier ce bloc/cette ligne vers la copie de travail" — fusionne **seulement cet element**, sans toucher au reste du fichier.

### Dupliquer avec un nouvel identifiant
Clic droit sur un bloc ECF ou une ligne CSV en lecture seule > "Dupliquer avec un nouvel Id/une nouvelle cle..." — contrairement a "copier/fusionner", ceci cree un **element totalement independant** (pas de fusion), en te laissant choisir un nouvel Id et/ou un nouveau Name (avec suggestions d'Ids libres). Pratique pour partir d'un bloc existant comme modele pour en creer un nouveau distinct (ex : une variante d'un item).

- Fonctionne aussi sur des blocs **sans Id** (identifies seulement par `Name`) — cas reel dans certains fichiers Empyrion.
- Tu peux aussi **abandonner l'Id** du bloc duplique pour ne l'identifier que par Name.
- Si tu dupliques un **sous-bloc imbrique** (ex: un `Mode` dans un `Item`), il reste automatiquement **dans le meme bloc parent** dans la copie de travail (pas isole a la racine).
- Meme logique disponible pour le YAML (dupliquer une entree avec une nouvelle cle/valeur).

---

## 3. Editer la copie de travail

### Fichiers ECF
Double-clic sur un `.ecf` dans la copie de travail : ouvre une **vue comparative** (ta copie a gauche, editable ; Scenario A/B a droite, lecture seule, en onglets).

- **Double-clic sur une valeur** dans le tableau de proprietes pour l'editer.
- **+ Bloc** / **+ Propriete** pour ajouter.
- Clic droit sur une propriete : **Supprimer**, **Traduire vers...**, **Mise en forme BBCode...**
- Toute modification de valeur est **automatiquement annotee** : `# original: <ancienne_valeur> -- Mod par <toi>` (configurable dans **Options**).

### Fichiers CSV
Double-clic sur un `.csv` : tableau editable.
- **+ Ligne** / **Supprimer la ligne selectionnee**.
- Clic droit : Copier/Couper/Coller (compatible Excel, format tabule), **Supprimer le contenu** (vide la cellule) vs **Supprimer la ligne entiere** (deux actions distinctes), Traduire, BBCode.
- Le **delimiteur** (`,` ou `;`) et le **style de fin de ligne** sont detectes automatiquement et preserves.

### Fichiers YAML
Double-clic sur un `.yaml`/`.yml` : arbre de navigation a gauche (cle + apercu), panneau de valeur editable a droite avec bouton **"Appliquer cette valeur"** — plus adapte qu'une edition en cellule vu la structure imbriquee des playfields.
- **+ Entree** / **Supprimer l'entree selectionnee**.
- Traduction et BBCode disponibles sur la valeur en cours d'edition.

### Fichiers TXT
Double-clic sur un `.txt` : editeur de texte simple. Copier/couper/coller natifs (Qt), plus traduction et BBCode sur une selection via clic droit.

### Copier / Couper / Coller (tableaux CSV et ECF)
`Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Suppr` fonctionnent sur les tableaux, avec un format compatible Excel (tabulations). La colonne "Cle" d'un tableau de proprietes ECF reste protegee en ecriture (impossible de la modifier par un collage accidentel).

---

## 4. Traduction

Disponible partout ou tu edites du texte (CSV, ECF, YAML, TXT), via clic droit > **"Traduire vers..."**. Utilise Google Translate (bibliotheque `deep-translator`, gratuite, necessite une connexion internet).

- **Protection du BBCode et des placeholders** : les balises (`[b]`, `[color=#RRGGBB]`...) et jetons de substitution (`{PlayerName}`, `%d`, `%s`...) sont automatiquement extraits avant traduction et reinjectes a leur place — jamais traduits ni casses.
- **Traduction CSV cible la bonne colonne** : clic droit sur une cellule source (ex: colonne `English`) et choisis la langue cible (ex: `Francais`) — le resultat va dans la colonne correspondante (ex: `Français`), pas dans la cellule source. La correspondance de colonne est insensible aux accents et reconnait plusieurs conventions de nommage (code ISO, nom anglais, nom natif).
- **Depuis Scenario A/B (lecture seule)** : tu peux traduire directement une cellule source et le resultat s'applique dans la cellule correspondante de la **copie de travail**.
- La fenetre de resultat te laisse **relire et corriger** la traduction avant de l'appliquer.

## 5. Mise en forme BBCode

Clic droit > **"Mise en forme BBCode..."** ouvre une petite fenetre : selectionne une portion de texte a la souris, clique une couleur (palette de 10 teintes) ou un style (Gras/Italique/Souligne) pour l'entourer automatiquement des bonnes balises (`[color=#FF0000]...[/color]`, `[b]...[/b]`...).

---

## 6. Verifications

### Verifier les references (menu Verification)
Controle que chaque `Ref: X` correspond bien a un `Name: X` existant quelque part dans le scenario — `Ref` est le mecanisme d'heritage d'Empyrion, une reference cassee echoue silencieusement en jeu (pas de message d'erreur, juste des proprietes manquantes). A lancer apres une fusion.

### Blocs en attente (menu Verification)
Liste tous les blocs mis en attente (desactives) par le garde-fou anti-collision du merge. Pour chacun :
- **Comparaison detaillee** avec le bloc actuellement actif (diff propriete par propriete).
- **Suggestions d'Id libres** (calculees au-dessus du maximum utilise dans le scenario).
- Bouton pour **activer** le bloc avec le nouvel Id choisi — evite d'editer le fichier a la main (risque reel de casser la structure si la ligne de fermeture `}` reste commentee par erreur).

### Filtrer par propriete
Dans la vue d'un fichier ECF, bouton **"Filtrer par propriete..."** : liste toutes les proprietes existantes dans le fichier (avec leur nombre d'occurrences), coche-en une ou plusieurs pour filtrer l'arbre en direct (masque les blocs qui ne les ont pas toutes).

### Recherche
Chaque vue de fichier a une barre de recherche (Id / Name / cle / valeur selon le format) avec navigation "suivant" — indispensable des qu'un fichier depasse quelques centaines d'entrees.

---

## 7. Options

**Options > Nom pour les annotations...** — le nom qui apparait dans les commentaires de tracabilite (`Mod par <nom>`).

**Options > Annoter les modifications automatiquement** — active/desactive l'annotation automatique.

---

## 8. Scripts de diagnostic (ligne de commande)

Utiles en complement de l'interface, a lancer depuis un terminal dans le dossier du projet :

- `verifier_parser_ecf.py <fichier_ou_dossier>` — verifie le round-trip (fidelite parfaite) d'un ou plusieurs fichiers ECF.
- `verifier_parser_yaml.py <fichier_ou_dossier>` — meme chose pour le YAML.
- `verifier_parser_csv.py <fichier_ou_dossier>` — meme chose pour le CSV.
- `diagnostic_bloc.py <fichier.ecf> <Id>` — cherche un bloc precis par Id, y compris dans les commentaires (utile si un bloc semble avoir disparu).
- `detecter_imbrication_anormale.py <fichier.ecf>` — detecte les blocs qui ont "avale" le reste du fichier par erreur (typiquement apres une edition manuelle qui a laisse une accolade fermante commentee).

---

## 9. Limitations connues

- Pas encore de copier/coller multi-lignes façon tableur pour le YAML (structure trop imbriquee pour que ca ait du sens de la meme facon).
- La fusion "intelligente" (priorite copie de travail, completion) n'existe que pour ECF et CSV. Les autres formats (YAML, TXT...) sont remplaces entierement lors d'une fusion de fichier.
- La traduction necessite une connexion internet (Google Translate).
