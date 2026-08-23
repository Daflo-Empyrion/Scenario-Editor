# Empyrion Scenario Editor

[![License: GPLv3](assets/gplv3_badge.png)](https://www.gnu.org/licenses/gpl-3.0.html)

Editeur graphique (PyQt6) pour la creation et modification de scenarios
**Empyrion Galactic Survival** — edition des fichiers `.ecf`, `.yaml` et `.csv`,
fusion assistee entre scenarios, traduction automatique, verification de
references, et un module dedie a l'edition structuree des playfields. Voir
`docs/wiki_app_fr.md` (ou `_en.md`, accessible aussi depuis le menu Aide de
l'application) pour la documentation complete des fonctionnalites.

## Fonctionnalites principales

### Edition ECF
- Arbre de navigation par blocs, recherche, filtrage par propriete
- Mode tableau automatique pour les structures repetitives
- **Creation guidee de bloc/item** : choix Id+Name ou Name seul, tableau de
  proprietes issues du fichier lui-meme (valeurs suggerees par menu
  deroulant), proposition automatique de creer le Template (recette de
  craft) associe
- **Transformation en masse** : multiplier/ajouter/fixer/plafonner/arrondir
  une propriete sur plusieurs blocs a la fois, avec tableau de revue editable
- Fusion intelligente entre scenarios avec garde-fou anti-collision
- **Verification de references croisees et de regles metier** : items/blocs
  references, jetons, dialogues, heritage Ref, limite d'Id du jeu, doublons
  — fenetres non modales avec actualisation et export

### Edition de playfields (YAML) — module dedie
Tout fichier `playfield*.yaml` ou `space*.yaml` s'ouvre avec un editeur
structure a 8 onglets (Carte 2D, Ressources, POI, Creatures, Drones/Vaisseaux,
Zones de spawn, Effets speciaux, YAML complet) plutot que du texte brut —
tableaux avec ajout/suppression pour les ressources (liste deroulante peuplee
depuis les vrais blocs du scenario), modification en tableau pour les autres
sections, colonnes speciales (Biome pour les creatures, RegenAfter pour les
POI/ressources spatiales).

- **Carte 2D** — vue du dessus des entites positionnables d'un playfield
  (POI fixes deplacables par glisser-depose, points de depart joueur,
  patrouilles de drones...), filtres, zoom
- **Inspecteur de POI** — statistiques de drones estimes par POI et par
  faction, fenetre non modale avec export
- **Carte de la galaxie** (`Sectors.yaml`) — systemes solaires du scenario,
  positions reelles, curseur d'inclinaison pour separer les systemes proches
  en X/Z mais distants en hauteur

### Traduction et CSV
- Traduction automatique (Google Translate, sans cle API) avec protection du
  BBCode/placeholders et memoire de traduction locale — desactivable
  entierement dans les options (voir `PRIVACY.md`)
- Edition CSV (tables de localisation) avec recherche/remplacement cible

### Et aussi
- Comparaison de scenarios, extraction de proprietes en glossaire CSV
- Sauvegardes de scenario et de parties
- Tutoriels integres et wikis bilingues (FR/EN), consultables dans l'appli
- Bouton "Signaler" integre (rapport de bug pre-rempli vers GitHub Issues)
- Verification automatique de nouvelle version au demarrage
- Outils en ligne de commande (`EmpyrionEditorCLI.exe`) pour les memes
  operations en scripts/automatisation

## Installation

Deux facons d'utiliser l'application :

1. **Installeur Windows** (recommande pour un usage courant) : telecharge
   `Setup-EmpyrionScenarioEditor-vX.X.X.exe` depuis la page
   [Releases](https://github.com/Daflo-Empyrion/Scenario-Editor/releases)
2. **Depuis les sources** (pour developper) :
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   python run_gui.py
   ```

## Construire l'installeur

Voir [`BUILD.md`](BUILD.md) pour la procedure complete (PyInstaller + Inno
Setup), y compris la construction automatisee via GitHub Actions a chaque
tag pousse.

## A propos des avertissements antivirus

Windows SmartScreen ou ton antivirus peuvent signaler l'installeur au premier
lancement — c'est un faux positif connu, courant sur les executables Python
non signes numeriquement. Voir `BUILD.md` (section "Faux positifs
antivirus") pour le detail et les liens de signalement aux editeurs
concernes. Le code source est integralement disponible dans ce depot.

## Politique de signature de code / Code Signing Policy

Signature de code gratuite fournie par SignPath.io, certificat de la
Fondation SignPath (candidature en cours).
*Free code signing provided by SignPath.io, certificate by SignPath
Foundation (application pending).*

- **Committers, reviewers et approvers** : [Daflo](https://github.com/Daflo-Empyrion)
  (mainteneur unique de ce projet a ce jour)
- **Politique de confidentialite / Privacy policy** : voir [`PRIVACY.md`](PRIVACY.md)
  pour le detail exact de ce qui est envoye sur le reseau, quand, et comment
  le desactiver.

## Signaler un bug ou proposer une amelioration

Le bouton "Signaler" integre a l'application (barre d'outils superieure)
ouvre un formulaire pre-rempli vers les
[Issues GitHub](https://github.com/Daflo-Empyrion/Scenario-Editor/issues) —
ou depose-en une directement.

## Licence

Ce projet est distribue sous licence **GNU General Public License v3.0**
(GPLv3) — voir le fichier [`LICENSE`](LICENSE) pour le texte complet.

En resume : tu es libre d'utiliser, etudier, modifier et redistribuer ce
logiciel, a condition que toute version modifiee ou derivee reste elle
aussi sous licence GPLv3, avec le code source disponible. Plus d'informations
sur [gnu.org/licenses](https://www.gnu.org/licenses/gpl-3.0.html).

Copyright (C) 2026 Daflo
