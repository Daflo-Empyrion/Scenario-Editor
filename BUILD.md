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
Depuis le dossier du projet, **sans avoir besoin d'activer le venv toi-meme** —
`build.bat` s'en charge automatiquement (et verifie que les dependances du
projet sont bien presentes avant de lancer quoi que ce soit, pour eviter un
probleme deja rencontre : construire avec le mauvais Python produit un `.exe`
qui semble fonctionner mais ou une fonctionnalite comme la traduction est
silencieusement cassee) :

```bat
build.bat
```

Ce script enchaine automatiquement :
0. **Verification** — active `venv\` et confirme que `deep_translator`, `bs4`,
   `PyQt6` et `PyInstaller` sont bien importables dans cet environnement ; arrete
   immediatement avec un message clair sinon (plutot que de laisser construire un
   `.exe` casse sans le signaler)
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

---

---

## 6. Une fonctionnalite marche depuis les sources mais pas dans l'exe construit

Signe classique : `build.bat` reussit sans erreur visible, mais une fois installe,
une fonctionnalite precise (typiquement la traduction) affiche une erreur comme
"module indisponible" alors qu'elle marche tres bien en lancant `python run_gui.py`
depuis les sources.

**Cause la plus frequente** : PyInstaller a construit l'exe avec le **Python
global** au lieu du `venv` du projet -- le code source est bien present (donc pas
d'erreur de construction), mais une dependance tierce (`deep-translator`, `bs4`...)
absente de cet environnement-la n'est jamais embarquee dans l'exe.

**Depuis cette version de `build.bat`**, ce cas precis est detecte automatiquement
avant meme de lancer PyInstaller (voir Etape 0 ci-dessus) -- si tu vois ce message
d'erreur au lancement de `build.bat`, suis simplement les instructions affichees
(reinstaller les dependances dans le venv). Si le probleme persiste malgre un
`build.bat` qui annonce "Dependances verifiees : OK", verifie manuellement :

```bat
venv\Scripts\activate
where python
```

Le chemin affiche doit pointer vers `...\venv\Scripts\python.exe`, jamais vers
`AppData\Local\Programs\Python\...`.

---

## 7. Faux positifs antivirus (VirusTotal et autres)

Il est **normal et courant** qu'un ou deux moteurs sur VirusTotal (sur une
soixantaine) signalent un `.exe` PyInstaller non signe comme suspect, meme
pour un logiciel parfaitement legitime. Ce n'est generalement pas un vrai
signal d'alerte, mais une consequence de la *technique d'empaquetage*
elle-meme :

- Les moteurs heuristiques/IA (DeepInstinct, et d'autres du meme type)
  reagissent a des **patterns d'empaquetage** (bootloader qui deballe et
  execute du code, compression...) plutot qu'a un vrai comportement malveillant
  observe -- ces memes patterns sont aussi utilises par de vrais malwares pour
  s'obfusquer, d'ou la confusion.
- La **compression UPX** est un facteur particulierement frequent de faux
  positifs -- **deja desactivee** dans `empyrion_editor.spec` (`upx=False`)
  pour cette raison. Le `.exe` est legerement plus gros sans elle, mais
  nettement moins suspect aux yeux des scanners heuristiques.

### Pour reduire encore plus le risque

1. **Signature de code (la solution la plus efficace)** — un certificat de
   signature de code (Authenticode) coute generalement 100-300€/an chez un
   fournisseur comme SSL.com ou Sectigo. Une fois le `.exe` signe
   numeriquement, la grande majorite des faux positifs heuristiques
   disparaissent, et Windows SmartScreen n'affiche plus l'avertissement
   "Editeur inconnu". Recommande si tu distribues largement.
2. **Soumettre le fichier au fournisseur concerne** — DeepInstinct (et la
   plupart des autres) proposent un formulaire de soumission de faux positif ;
   une fois examine et confirme legitime, leur detection est corrigee pour
   tout le monde.
3. **Depot GitHub public** — un code source visible et un historique de
   commits publics renforcent la confiance (certains outils de reputation,
   comme Windows SmartScreen, s'ameliorent aussi avec le nombre de
   telechargements dans le temps).
4. **Prevenir tes utilisateurs** — pour une distribution informelle
   (Discord, amis), un simple message du type *"Windows/l'antivirus peut
   afficher un avertissement au premier lancement -- c'est un faux positif
   connu des `.exe` Python non signes, le code source est disponible ici :
   [lien]"* suffit largement a rassurer.

**Ce que je ne recommande pas** : ignorer completement le probleme sans rien
dire aux utilisateurs -- meme un faux positif legitime peut faire fuir
quelqu'un qui ne sait pas a quoi s'attendre.
