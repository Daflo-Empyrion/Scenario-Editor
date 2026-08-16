# Construire et distribuer Empyrion Scenario Editor

Ce guide couvre la construction d'un installeur Windows autonome (aucun Python
requis chez la personne qui l'installe) et le processus a suivre pour chaque
nouvelle version.

---

## 1. Configuration initiale (une seule fois)

### Outils necessaires
1. **Python 3.11+** (deja installe si tu developpes l'appli)
2. **Inno Setup** (gratuit) : https://jrsoftware.org/isinfo.php — installation
   standard, garder les options par defaut
3. Un environnement virtuel avec les dependances du projet **et** de build :

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-build.txt
```

### Icone de l'application
Une icone simple par defaut a ete generee dans `assets/icon.ico` (visible en
apercu dans `assets/icon_preview.png`). Pour la remplacer par la tienne : cree
un fichier `.ico` multi-resolutions (16/32/48/64/128/256 px — n'importe quel
convertisseur PNG-vers-ICO en ligne fait l'affaire) et remplace
`assets/icon.ico`. Rien d'autre a changer, le spec PyInstaller et le script
Inno Setup le reference deja par ce chemin.

---

## 2. Construire une version (a chaque nouvelle release)

### Etape 1 — Mettre a jour le numero de version
**Deux fichiers a modifier, avec exactement le meme numero** :
- `core/version.py` → `APP_VERSION = "1.1.0"`
- `installer.iss` → `#define MyAppVersion "1.1.0"`

### Etape 2 — Construire
Avec l'environnement virtuel active, dans le dossier du projet :

```bat
build.bat
```

Ce script enchaine automatiquement :
1. **PyInstaller** — construit `dist/EmpyrionScenarioEditor/` (l'appli complete,
   Python et toutes les dependances inclus, aucune installation Python requise
   chez l'utilisateur final)
2. **Inno Setup** — empaquete ce dossier en un seul installeur classique
   `installer_output/Setup-EmpyrionScenarioEditor-v1.1.0.exe`

### Etape 3 — Tester avant de distribuer
Lance l'installeur genere sur une machine de test (ou la tienne), verifie que :
- L'installation se deroule normalement, icone sur le Bureau si coche
- L'application demarre et fonctionne normalement
- Si une version precedente etait deja installee : verifie qu'elle est
  proprement remplacee, et que **tes projets/scenarios ouverts avant restent
  intacts** (voir section 4 ci-dessous — c'est garanti par construction, mais
  ca vaut le coup de le confirmer une fois)

---

## 3. Publier une nouvelle version sur GitHub

Une fois `Setup-EmpyrionScenarioEditor-vX.Y.Z.exe` teste et pret :

1. Commit les changements de code, avec un tag correspondant a la version :
   ```bat
   git add .
   git commit -m "Version 1.1.0"
   git tag v1.1.0
   git push origin main --tags
   ```
2. Sur GitHub, va dans **Releases > Draft a new release**, choisis le tag
   `v1.1.0`, ajoute une description des changements, et **attache le fichier
   `Setup-EmpyrionScenarioEditor-v1.1.0.exe`** genere a l'etape precedente.
3. Publie la release.

**Important** : le tag doit obligatoirement commencer par `v` suivi du meme
numero que `APP_VERSION` (ex: tag `v1.1.0` pour `APP_VERSION = "1.1.0"`) —
c'est ce que le verificateur de mise a jour integre a l'application compare.

### Activer la verification automatique de mise a jour
Tant que `GITHUB_REPO` est vide dans `core/version.py`, la verification de
mise a jour reste desactivee (aucune erreur, juste ignoree). Des que ton depot
existe, renseigne-le une fois pour toutes :

```python
# core/version.py
GITHUB_REPO = "TonPseudo/empyrion-scenario-editor"
```

A partir de la, chaque lancement de l'application verifie silencieusement en
arriere-plan si une version plus recente existe sur GitHub (sans jamais rien
telecharger automatiquement), et l'utilisateur peut aussi verifier manuellement
via **Aide > Verifier les mises a jour...**.

---

## 4. Pourquoi les mises a jour ne cassent jamais les scenarios en cours

Par construction, l'application separe strictement :
- **Le code de l'appli**, installe dans `Program Files` (ou equivalent) —
  entierement remplace a chaque mise a jour
- **Les donnees utilisateur** : les copies de travail (creees ou vivent tes
  scenarios, jamais dans le dossier d'installation) et les reglages/projets
  recents (`%USERPROFILE%\.empyrion_editor\`, hors du dossier d'installation)

L'installeur Inno Setup ne touche qu'au dossier d'installation (`{app}`),
jamais a ces deux emplacements. Une mise a jour peut donc toujours se faire en
toute securite, meme avec un projet en cours d'edition.

---

## 5. Distribution "one-off" (sans passer par GitHub Releases)

Pour partager une version ponctuelle sans creer de release GitHub (ex: test
rapide avec un ami), le fichier `installer_output/Setup-*.exe` genere a
l'etape 2 peut etre partage directement (Discord, cle USB, etc.) — il est
totalement autonome, aucune dependance externe au moment de l'installation.
