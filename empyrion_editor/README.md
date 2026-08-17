# Empyrion Scenario Editor

[![License: GPLv3](assets/gplv3_badge.png)](https://www.gnu.org/licenses/gpl-3.0.html)

Editeur graphique (PyQt6) pour la creation et modification de scenarios
**Empyrion Galactic Survival** — edition des fichiers `.ecf`, `.yaml` et `.csv`,
fusion assistee entre scenarios, traduction automatique, verification de
references, et bien plus. Voir `docs/wiki_app_fr.md` (ou `_en.md`) pour la
documentation complete des fonctionnalites.

## Fonctionnalites principales

- Edition des fichiers ECF (blocs, items, config) avec fusion intelligente
  et garde-fou anti-collision
- Edition YAML (playfields) et CSV (traductions, tables)
- Traduction automatique avec protection du BBCode/placeholders et memoire
  de traduction
- Comparaison de scenarios, extraction de proprietes, sauvegardes
- Tutoriels integres et wikis bilingues (FR/EN)
- Verification automatique de mise a jour (voir `core/version.py`)

## Installation

Deux facons d'utiliser l'application :

1. **Installeur Windows** (recommande pour un usage courant) : voir la page
   des Releases, ou construire soi-meme via `BUILD.md`
2. **Depuis les sources** (pour developper) :
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   python run_gui.py
   ```

## Construire l'installeur

Voir `BUILD.md` pour la procedure complete (PyInstaller + Inno Setup).

## Licence

Ce projet est distribue sous licence **GNU General Public License v3.0**
(GPLv3) — voir le fichier [`LICENSE`](LICENSE) pour le texte complet.

En resume : tu es libre d'utiliser, etudier, modifier et redistribuer ce
logiciel, a condition que toute version modifiee ou derivee reste elle
aussi sous licence GPLv3, avec le code source disponible. Plus d'informations
sur [gnu.org/licenses](https://www.gnu.org/licenses/gpl-3.0.html).

Copyright (C) 2026 Daflo
