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
**Trois fichiers a modifier, avec exactement le meme numero** (`installer.iss`
gere `VersionInfoVersion` automatiquement a partir de `MyAppVersion`, donc pas
de quatrieme fichier separe pour l'installeur) :
- `core/version.py` → `APP_VERSION = "1.1.0"`
- `installer.iss` → `#define MyAppVersion "1.1.0"`
- `version_info.txt` → `filevers=(1, 1, 0, 0)`, `prodvers=(1, 1, 0, 0)`, et les
  deux champs `FileVersion`/`ProductVersion` (`u'1.1.0.0'`) -- ce fichier ajoute
  les metadonnees Windows (editeur, description, version) visibles dans les
  proprietes des EXECUTABLES DE L'APPLI (pas l'installeur, voir juste en
  dessous), ce qui reduit les faux positifs antivirus (voir section 7)

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

Depuis la mise en place du pipeline automatise (`.github/workflows/build.yml`,
voir aussi section 8), **l'etape 2 "Construire" (section 2 ci-dessus) devient
optionnelle** pour une publication -- le tag pousse a l'etape 1 ci-dessous
declenche automatiquement une construction complete sur un environnement
Windows propre, et prepare une Release en **brouillon** avec l'installeur deja
attache. `build.bat` en local reste utile pour tester rapidement sans attendre
le pipeline (quelques minutes) ou sans connexion internet.

1. Commit les changements de code, avec un tag correspondant a la version :
   ```bat
   git add .
   git commit -m "Version 1.1.0"
   git tag v1.1.0
   git push origin main --tags
   ```
2. Va sur l'onglet **Actions** du depot GitHub pour suivre la construction en
   cours (quelques minutes) -- ou construis en local avec `build.bat` si tu
   preferes ne pas attendre.
3. Une fois le workflow termine, va dans **Releases** : un brouillon avec le
   tag `v1.1.0` et l'installeur deja attache t'attend. Ajoute le titre et la
   description des changements, verifie que le bon fichier est present, puis
   **Publish release**.

**Important** : le tag doit obligatoirement commencer par `v` suivi du meme
numero que `APP_VERSION` (ex: tag `v1.1.0` pour `APP_VERSION = "1.1.0"`) —
c'est ce que le verificateur de mise a jour integre a l'application compare, et
c'est aussi ce qui declenche le pipeline automatise ci-dessus.

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
- Le **mode "onefile"** (tout dans un seul .exe qui s'auto-extrait a chaque
  lancement) est aussi plus suspect que le mode "onedir" (dossier avec l'exe +
  ses dependances a cote) -- les deux executables du projet utilisent
  desormais "onedir" pour cette raison.
- Un `.exe` **sans metadonnees Windows** (editeur, description, version --
  visibles dans Proprietes > Details sous Windows) ressemble davantage a un
  malware qu'un executable qui en a. **Deux configurations distinctes** pour
  ceci : `version_info.txt` (deja cable dans `empyrion_editor.spec`) pour les
  executables de l'appli une fois installee (`EmpyrionScenarioEditor.exe`,
  `EmpyrionEditorCLI.exe`), et les directives `VersionInfo*` du `[Setup]` dans
  `installer.iss` pour l'**installeur lui-meme** (`Setup-*.exe`) -- ce sont
  deux fichiers generes separement (PyInstaller vs Inno Setup), il faut donc
  verifier les proprietes du bon fichier si un doute survient sur la presence
  du copyright.
- Note sur Avast/AVG : ce sont **le meme moteur de detection** (AVG a ete
  rachete par Avast) -- les voir tous les deux signaler la meme chose n'est
  pas une double confirmation independante, juste le meme moteur affiche sous
  deux marques.
- Message generique de type `Win64:Malware-gen` ou `Trojan.TR/W64.Malware`
  (sans nom de famille de malware precis) est le signe classique d'une
  detection **heuristique generique**, pas d'une signature de malware connu --
  extremement courant et documente pour les executables PyInstaller, y compris
  pour des scripts absolument triviaux.

### Pour reduire encore plus le risque

1. **Signature de code (la solution la plus efficace)** — un certificat de
   signature de code (Authenticode) coute generalement 100-300€/an chez un
   fournisseur comme SSL.com ou Sectigo. Une fois le `.exe` signe
   numeriquement, la grande majorite des faux positifs heuristiques
   disparaissent, et Windows SmartScreen n'affiche plus l'avertissement
   "Editeur inconnu". Recommande si tu distribues largement.
   - Alternative **gratuite** pour les projets open source : SignPath
     Foundation (signpath.org) offre une signature de code gratuite aux
     projets sous licence OSI-approuvee (GPLv3 qualifie) avec un historique de
     releases publiques -- necessite cependant de mettre en place un pipeline
     CI/CD (ex: GitHub Actions) qui construit automatiquement l'exe depuis le
     depot, leur systeme signant ensuite ce build automatise. Plus adapte
     quand le projet grandit et que la mise en place de CI/CD se justifie.
2. **Soumettre le fichier au fournisseur concerne** — DeepInstinct, Avast/AVG,
   et la plupart des autres proposent un formulaire de soumission de faux
   positif ; une fois examine et confirme legitime, leur detection est
   corrigee pour tout le monde. Pour Avast/AVG :
   https://www.avast.com/false-positive-file-form.php
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

---

## 8. Pipeline automatise (GitHub Actions)

Le fichier `.github/workflows/build.yml` construit automatiquement l'appli des
qu'un tag `vX.Y.Z` est pousse -- meme geste qu'aujourd'hui, rien a changer dans
tes habitudes de commit/tag/push (voir section 3).

### Ce qu'il fait, dans l'ordre
1. Recupere le code sur une machine Windows fournie par GitHub (propre a
   chaque fois -- jamais l'environnement Python personnel de ton PC)
2. Installe les dependances depuis `requirements.txt` +
   `requirements-build.txt`
3. Construit les deux executables avec PyInstaller
4. *(Emplacement reserve pour la signature SignPath -- voir plus bas)*
5. Construit l'installeur avec Inno Setup
6. Cree une Release GitHub en **brouillon**, avec l'installeur deja attache

### Avantage independant de la signature de code
Meme sans signature, ce pipeline elimine une classe entiere de bugs deja
rencontres avec `build.bat` en local (ex: construction avec le mauvais
environnement Python, dependance manquante silencieusement -- voir section 6)
puisque l'environnement de construction est toujours identique et propre.

### Suivre une construction en cours
Onglet **Actions** du depot GitHub -- chaque tag pousse y apparait comme une
execution, avec le detail de chaque etape en cas d'echec.

### Problemes deja rencontres et corriges
- **"Resource not accessible by integration"** sur l'etape de creation de la
  Release -- le jeton `GITHUB_TOKEN` genere automatiquement par GitHub pour
  chaque execution est en lecture seule par defaut. Corrige en ajoutant un
  bloc `permissions: contents: write` au niveau du job dans
  `.github/workflows/build.yml` -- deja en place, rien a faire si tu utilises
  le fichier tel quel.
- **Avertissement "Node.js 20 est deprecie"** -- les actions tierces
  utilisees (`actions/checkout`, `actions/setup-python`,
  `actions/upload-artifact`, `softprops/action-gh-release`) ont ete mises a
  jour vers leurs versions majeures les plus recentes (compatibles Node.js
  24) pour eviter que le workflow casse quand GitHub retirera completement
  Node.js 20 de ses machines. Si l'avertissement reapparait plus tard (une de
  ces actions, ou une nouvelle ajoutee, prend du retard), verifie sur la page
  GitHub de l'action concernee si une version plus recente existe.

### Activer la signature SignPath Foundation (une fois la candidature approuvee)
1. Suis leur documentation pour connecter ton depot GitHub a leur plateforme
   (genere les secrets `SIGNPATH_API_TOKEN` et `SIGNPATH_ORGANIZATION_ID`)
2. Ajoute ces deux valeurs dans **Settings > Secrets and variables > Actions**
   du depot GitHub
3. Decommente et adapte le bloc d'etape "Signer les executables (SignPath)"
   deja present (mais commente) dans `.github/workflows/build.yml`, juste
   avant l'etape de construction de l'installeur -- pour qu'Inno Setup
   empaquete les executables deja signes plutot que les originaux

## 9. Conformite SignPath Foundation

Verifie point par point contre les conditions officielles SignPath
Foundation pour les projets OSS (aout 2026). Deux elements manquaient et ont
ete ajoutes :

- **Politique de signature de code** -- section dediee dans `README.md`
  (avec la formule exacte exigee), pointant vers `PRIVACY.md`
- **Fonctionnalite transferant des donnees utilisateur non declaree** -- la
  traduction en ligne (Google Translate, via `deep-translator`) envoie le
  texte a traduire aux serveurs Google sans qu'aucune politique de
  confidentialite ni option de desactivation n'existent auparavant. Corrige :
  - `PRIVACY.md` decrit precisement les 3 fonctionnalites qui font des
    requetes reseau (traduction, verification de version, bouton Signaler)
  - `core/settings.py:get_online_translation_enabled()` -- reglage
    persistant, True par defaut (comportement inchange), accessible via
    **Options > Traduction en ligne (Google Translate)**
  - `core/translation.py:translate_text()` refuse de fonctionner si
    desactive (le cache local de traductions deja obtenues reste utilisable
    sans appel reseau)
  - `installer_privacy_notice.txt` + `InfoBeforeFile` dans `installer.iss` --
    affiche un resume de cette politique **pendant l'installation**, comme
    l'exige SignPath pour les logiciels transferant des donnees

Si de nouvelles fonctionnalites font a l'avenir des requetes reseau non
deja couvertes ci-dessus, mettre a jour `PRIVACY.md` et
`installer_privacy_notice.txt` en consequence avant toute nouvelle demande
de verification aupres de SignPath.
