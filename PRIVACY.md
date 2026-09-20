# Politique de confidentialite / Privacy Policy

*(English version below / Version anglaise plus bas)*

## Francais

Empyrion Scenario Editor est un logiciel de bureau qui fonctionne
integralement en local sur ta machine, sur tes propres fichiers de scenario.
Il ne collecte aucune donnee personnelle, aucune statistique d'usage, et ne
transmet rien "en arriere-plan" a l'insu de l'utilisateur.

Trois fonctionnalites precises effectuent des requetes reseau (cinq avec
les moteurs IA optionnels Groq et DeepL). Chacune est decrite ci-dessous
avec exactement ce qui est envoye, quand, et comment la desactiver si tu
le souhaites.

### 1. Traduction en ligne (Google Translate)
Quand tu utilises la fonction de traduction (bouton "Traduire" dans
l'editeur CSV), le texte que tu choisis de traduire est envoye aux serveurs
Google Translate (via la bibliotheque `deep-translator`) pour obtenir la
traduction, puis le resultat est stocke dans une memoire de traduction
**locale** (sur ta machine) afin d'eviter de renvoyer le meme texte deux
fois.

- **Quoi** : le texte source du champ que tu traduis (jamais l'integralite
  du fichier, uniquement l'entree selectionnee)
- **Quand** : uniquement quand tu cliques explicitement sur "Traduire"
- **Comment desactiver** : menu **Options > Traduction en ligne (Google
  Translate)** -- decoche pour desactiver completement cette fonctionnalite
  (la traduction refusera alors de fonctionner, avec un message clair
  l'expliquant). Meme desactivee, les traductions deja obtenues
  precedemment restent utilisables depuis la memoire locale, sans aucun
  appel reseau.

### 2. Traduction IA Groq (en ligne, optionnel)
Si tu configures et actives le moteur « Groq » (Options > Traduction >
Traduction IA Groq), les fragments de texte a traduire sont envoyes a l'API
de Groq Inc. (`api.groq.com`), qui les transmet au fournisseur du modele IA
choisi (par defaut Qwen) afin d'obtenir la traduction. Les moteurs locaux
Argos et NLLB, eux, n'envoient rien du tout : tout reste sur ta machine.

- **Quoi** : uniquement les fragments de texte libre a traduire (les balises
  du jeu, les nombres et les placeholders sont retires avant l'envoi ; la
  memoire locale evite de renvoyer deux fois le meme texte)
- **Quand** : uniquement quand tu lances une traduction avec le moteur Groq
  actif ; aucune requete tant que tu n'as pas colle ta propre cle API
- **Ou va ta cle API** : uniquement dans ta configuration locale
  (`~/.empyrion_editor/settings.json`), jamais dans le depot ni envoyee a
  qui que ce soit d'autre que Groq
- **Comment desactiver** : choisis un autre moteur dans le sous-menu
  Options > Traduction > Moteur de traduction, et/ou decoche Options >
  Traduction en ligne -- cette case autorise ou bloque TOUS les moteurs
  en ligne (Google comme Groq)

### 3. Traduction DeepL (en ligne, optionnel)
Si tu configures et actives le moteur « DeepL » (Options > Traduction >
Traduction DeepL), les textes a traduire sont envoyes a l'API de DeepL SE
(`api-free.deepl.com`, plan API Free : 500 000 caracteres/mois) afin
d'obtenir la traduction. C'est aussi un maillon de la bascule
automatique : si le moteur principal atteint son quota, DeepL peut servir
de secours (uniquement si tu y as colle ta propre cle, et uniquement si
la traduction en ligne est permise).

- **Quoi** : uniquement le texte a traduire (les balises du jeu et les
  placeholders sont proteges avant l'envoi ; la memoire locale evite de
  renvoyer deux fois le meme texte)
- **Quand** : uniquement quand tu lances une traduction avec le moteur
  DeepL actif, ou quand il sert de secours ; aucune requete tant que tu
  n'as pas colle ta propre cle API
- **Ou va ta cle API** : uniquement dans ta configuration locale
  (`~/.empyrion_editor/settings.json`), jamais dans le depot ni envoyee a
  qui que ce soit d'autre que DeepL
- **Comment desactiver** : choisis un autre moteur dans le sous-menu
  Options > Traduction > Moteur de traduction, et/ou decoche Options >
  Traduction en ligne -- cette case autorise ou bloque TOUS les moteurs
  en ligne (Google, Groq comme DeepL)

### 4. Verification de nouvelle version (GitHub)
Au demarrage, l'application interroge l'API publique de GitHub
(`api.github.com`) pour savoir si une version plus recente a ete publiee.
Cette requete ne contient aucune information personnelle -- uniquement une
demande standard "quelle est la derniere version publiee de ce logiciel ?",
identique a celle que ferait n'importe quel navigateur visitant cette page
publique. Comme pour toute requete internet, ton adresse IP est visible par
GitHub le temps de cette requete (caracteristique inherente a tout acces
reseau, pas specifique a ce logiciel).

Cette verification echoue silencieusement si elle ne peut pas aboutir (pas
de connexion, etc.) et n'empeche jamais l'application de demarrer.

### 5. Bouton "Signaler"
Le bouton "Signaler" (rapport de bug) n'envoie rien directement depuis
l'application -- il ouvre ton navigateur systeme habituel sur une page
GitHub Issues pre-remplie. L'envoi effectif ne se produit que si tu choisis
ensuite, dans ton propre navigateur, de valider ce rapport.

### Ce que le logiciel ne fait jamais
- Il ne collecte ni ne transmet le contenu de tes scenarios, sauf action
  explicite de ta part (ex: traduction d'un champ precis)
- Il ne suit aucune statistique d'usage
- Il ne modifie aucun reglage systeme sans passer par l'installeur standard
  (Inno Setup), qui affiche les etapes habituelles et cree un
  desinstalleur

---

## English

Empyrion Scenario Editor is a desktop application that runs entirely
locally on your machine, on your own scenario files. It does not collect
any personal data, does not track usage statistics, and never sends
anything "in the background" without your knowledge.

Four specific features make network requests (five with the optional Groq and DeepL online engines). Each is described below
with exactly what is sent, when, and how to disable it if you wish.

### 1. Online translation (Google Translate)
When you use the translation feature (the "Translate" button in the CSV
editor), the text you choose to translate is sent to Google Translate's
servers (via the `deep-translator` library) to obtain the translation,
after which the result is stored in a **local** translation memory (on
your own machine) so the same text is never sent twice.

- **What**: the source text of the field you are translating (never the
  whole file, only the selected entry)
- **When**: only when you explicitly click "Translate"
- **How to disable**: **Options menu > Online translation (Google
  Translate)** -- uncheck to fully disable this feature (translation will
  then refuse to run, with a clear message explaining why). Even when
  disabled, translations already obtained previously remain usable from
  the local memory, with no network call at all.

### 2. Groq AI translation (online, optional)
If you configure and enable the "Groq" engine (Options > Translation >
Groq AI translation), the text fragments to translate are sent to Groq
Inc.'s API (`api.groq.com`), which forwards them to the provider of the
selected AI model (Qwen by default) to obtain the translation. The local
Argos and NLLB engines send nothing at all: everything stays on your
machine.

- **What**: only the free-text fragments to translate (game tags, numbers
  and placeholders are stripped before sending; the local memory avoids
  sending the same text twice)
- **When**: only when you start a translation with the Groq engine active;
  no request at all until you paste your own API key
- **Where your API key goes**: only into your local configuration
  (`~/.empyrion_editor/settings.json`), never into the repository and
  never sent to anyone other than Groq
- **How to disable**: pick another engine in the Options > Translation >
  Translation engine submenu, and/or uncheck Options > Online
  translation -- this checkbox allows or blocks ALL online engines
  (Google as well as Groq)

### 3. DeepL translation (online, optional)
If you configure and enable the "DeepL" engine (Options > Translation >
DeepL translation), the texts to translate are sent to DeepL SE's API
(`api-free.deepl.com`, Free API plan: 500,000 characters/month) to obtain
the translation. It is also a link in the automatic fallback chain: if
the main engine runs out of quota, DeepL can serve as a fallback (only
if you pasted your own key, and only if online translation is allowed).

- **What**: only the text to translate (game tags and placeholders are
  protected before sending; the local memory avoids sending the same
  text twice)
- **When**: only when you start a translation with the DeepL engine
  active, or when it serves as a fallback; no request at all until you
  paste your own API key
- **Where your API key goes**: only into your local configuration
  (`~/.empyrion_editor/settings.json`), never into the repository and
  never sent to anyone other than DeepL
- **How to disable**: pick another engine in the Options > Translation >
  Translation engine submenu, and/or uncheck Options > Online
  translation -- this checkbox allows or blocks ALL online engines
  (Google, Groq as well as DeepL)

### 4. New version check (GitHub)
On startup, the application queries GitHub's public API
(`api.github.com`) to check whether a newer version has been published.
This request contains no personal information -- just a standard "what is
the latest published version of this software?" request, identical to
what any browser would send visiting that public page. As with any
internet request, your IP address is visible to GitHub for the duration
of that request (an inherent characteristic of any network access, not
specific to this software).

This check fails silently if it cannot complete (no connection, etc.) and
never prevents the application from starting.

### 5. "Report" button
The "Report" (bug report) button does not send anything directly from the
application -- it opens your regular system browser to a pre-filled
GitHub Issues page. The report is only actually submitted if you then
choose, in your own browser, to confirm it.

### What the software never does
- It does not collect or transmit the contents of your scenarios, except
  through your explicit action (e.g. translating a specific field)
- It does not track any usage statistics
- It does not modify any system setting outside of the standard installer
  (Inno Setup), which shows the usual steps and creates an uninstaller
