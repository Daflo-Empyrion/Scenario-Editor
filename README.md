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
- **Transformation en masse** : multiplier/ajouter/fixer/plafonner/arrondir
  une propriete sur plusieurs blocs a la fois, avec tableau de revue editable
- Fusion intelligente entre scenarios avec garde-fou anti-collision
- **Verification de references croisees** : items/blocs references, jetons,
  heritage Ref — avec navigation directe au clic vers l'endroit exact

### Edition de playfields (YAML) — module dedie
Tout fichier `playfield*.yaml` ou `space*.yaml` s'ouvre avec un editeur
structure a 7 onglets (Ressources, POI, Creatures, Drones/Vaisseaux, Zones de
spawn, Effets speciaux, YAML complet) plutot que du texte brut — tableaux
avec ajout/suppression pour les ressources (liste deroulante peuplee depuis
les vrais blocs du scenario), modification en tableau pour les autres
sections, colonnes speciales (Biome pour les creatures, RegenAfter pour les
POI/ressources spatiales).

### Traduction et CSV
- Traduction automatique (LLM local via Ollama, ou service en ligne) avec
  protection du BBCode/placeholders et memoire de traduction
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
