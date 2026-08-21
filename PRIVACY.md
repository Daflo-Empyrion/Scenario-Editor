# Politique de confidentialite / Privacy Policy

*(English version below / Version anglaise plus bas)*

## Francais

Empyrion Scenario Editor est un logiciel de bureau qui fonctionne
integralement en local sur ta machine, sur tes propres fichiers de scenario.
Il ne collecte aucune donnee personnelle, aucune statistique d'usage, et ne
transmet rien "en arriere-plan" a l'insu de l'utilisateur.

Trois fonctionnalites precises effectuent des requetes reseau. Chacune est
decrite ci-dessous avec exactement ce qui est envoye, quand, et comment la
desactiver si tu le souhaites.

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

### 2. Verification de nouvelle version (GitHub)
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

### 3. Bouton "Signaler"
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

Three specific features make network requests. Each is described below
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

### 2. New version check (GitHub)
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

### 3. "Report" button
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
