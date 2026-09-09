# Empyrion Scenario Editor — présentez votre scénario, pas vos fichiers

> Fichier de présentation pour Discord (partie Markdown) et Steam (partie BBCode en bas).
> À jour de la version **v1.6.1**.

---

## ✂️ Partie Discord (Markdown — copier tout le bloc ci-dessous)

# Empyrion Scenario Editor — éditez vos scénarios Empyrion sans risque

**Gratuit & open source (GPLv3) · Windows 10/11 · interface FR/EN**

Empyrion Scenario Editor est un éditeur graphique complet pour les scénarios d'**Empyrion Galactic Survival** : blocs et objets, recettes, playfields, dialogues, arbres technologiques, localisation et missions PDA. Il travaille toujours sur une **copie de travail** : vos scénarios d'origine restent intacts, et un fichier non modifié est réécrit **à l'identique octet par octet** (parseurs fidèles, BOM et fins de ligne préservés).

## Ce que vous pouvez faire
- 🧱 **Blocs & objets (ECF)** — édition en listes déroulantes des valeurs déjà observées du fichier, ajout/suppression de blocs et de propriétés, duplication avec nouvel Id libre, transformation en masse (multiplier, ajouter, plafonner, arrondir…), désactivation/réactivation
- 🗺️ **Playfields** — éditeur structuré (ressources, POI, créatures, drones, zones de spawn, effets), **carte 2D** avec déplacement des POI à la souris, **carte de la galaxie** (Sectors.yaml) éditable et annulable
- ⚙️ **Recettes (Templates)** — création et ajustement guidés, ingrédients choisis par nom, propositions tirées des recettes existantes
- 💬 **Dialogues.ecf** — navigateur dédié, édition des textes, détection des liens cassés avec correction assistée
- 🌳 **Arbre technologique** — niveaux, coûts, parents et catégories éditables directement sur l'arbre, fiche d'info détaillée par item (descriptif, fabrication, déblocage, export Markdown)
- 🌍 **Localisation (CSV)** — tableur complet avec **traduction intégrée** : mémoire persistante, protection des balises BBCode et des placeholders (`{PlayerName}`…)
- 📋 **Missions PDA** — éditeur complet (chapitres, tâches, actions, récompenses, activations) + assistant de création en 3 étapes
- ✅ **Vérifications** — références orphelines, références croisées entre fichiers, Id > 8192, doublons, virgules non protégées… le Centre de vérification (F5) lance tout d'un coup
- 🛟 **Sécurité** — sauvegardes avant mise à jour, restauration avec backup de sécurité, enregistrement atomique, récupération après plantage, annulation globale
- 🧪 **Protocole de test intégré** — 248 cas réécrits **pas à pas** pour les non-techniciens, traduits FR/EN, commandes copiables en un clic

## Téléchargement
➡ **[Télécharger la dernière version](https://github.com/Daflo-Empyrion/Scenario-Editor/releases/latest)** — installeur Windows autonome (aucune dépendance, Python inutile). Fonctionne avec la vanille et les scénarios personnalisés (Reforged Eden 2, Atlantis…).

## Liens
- 🌐 Dépôt & wikis FR/EN : <https://github.com/Daflo-Empyrion/Scenario-Editor>
- 🐛 Un bug, une idée : <https://github.com/Daflo-Empyrion/Scenario-Editor/issues>
- 💬 Retours et captures bienvenus ici même !

*Créé par Daflo — libre et gratuit, licence GPL-3.*

---

## 🎮 Partie Steam (BBCode — copier tout le bloc ci-dessous)

```
[h1]Empyrion Scenario Editor — éditez vos scénarios Empyrion sans risque[/h1]
[b]Gratuit et open source (GPLv3) — Windows 10/11 — interface FR/EN[/b]

Empyrion Scenario Editor est un éditeur graphique complet pour les scénarios d'Empyrion Galactic Survival : blocs et objets, recettes, playfields, dialogues, arbres technologiques, localisation et missions PDA. Il travaille toujours sur une copie de travail : vos scénarios d'origine restent intacts, et un fichier non modifié est réécrit à l'identique octet par octet.

[h2]Ce que vous pouvez faire[/h2]
[list]
[*][b]Blocs & objets (ECF)[/b] : listes déroulantes des valeurs observées, ajout/suppression de blocs et propriétés, duplication avec nouvel Id, transformation en masse, désactivation/réactivation
[*][b]Playfields[/b] : éditeur structuré (ressources, POI, créatures, drones, zones de spawn, effets), carte 2D avec déplacement des POI à la souris, carte de la galaxie éditable
[*][b]Recettes (Templates)[/b] : création et ajustement guidés, ingrédients choisis par nom
[*][b]Dialogues.ecf[/b] : navigateur dédié, détection des liens cassés avec correction assistée
[*][b]Arbre technologique[/b] : niveaux, coûts, parents et catégories éditables sur l'arbre, fiche d'info détaillée par item (export Markdown)
[*][b]Localisation (CSV)[/b] : tableur complet, traduction intégrée avec mémoire et protection du BBCode/placeholder
[*][b]Missions PDA[/b] : éditeur complet (chapitres, tâches, actions, récompenses) + assistant de création
[*][b]Vérifications[/b] : références cassées, Id > 8192, doublons, virgules non protégées… tout en un clic (F5)
[*][b]Sécurité[/b] : sauvegardes, restauration avec backup de sécurité, enregistrement atomique, récupération après plantage, annulation globale
[*][b]Protocole de test intégré[/b] : 248 cas pas à pas FR/EN, commandes copiables en un clic
[/list]

[h2]Téléchargement[/h2]
[url=https://github.com/Daflo-Empyrion/Scenario-Editor/releases/latest][b]Télécharger la dernière version[/b][/url] — installeur Windows autonome (aucune dépendance, Python inutile). Fonctionne avec la vanille et les scénarios personnalisés (Reforged Eden 2, Atlantis…).

[h2]Liens[/h2]
[url=https://github.com/Daflo-Empyrion/Scenario-Editor]Dépôt et wikis FR/EN[/url] — [url=https://github.com/Daflo-Empyrion/Scenario-Editor/issues]Signaler un bug / proposer une idée[/url]

Créé par Daflo — libre et gratuit, licence GPL-3.
```

---

## 📌 Mode d'emploi du fichier

- **Discord** : copier le bloc Markdown ci-dessus (du titre `# Empyrion Scenario Editor` jusqu'à « licence GPL-3 »).
  - Limite Discord : 2000 caractères par message (~4000 avec Nitro). Le bloc fait ~2900 caractères : deux solutions —
    1. poster le titre + la 1re section dans un 1er message, le reste (à partir de « ## Téléchargement ») dans un 2e ;
    2. ou l'utiliser dans un post de forum/salon d'annonces (1er message à 4000).
- **Steam** : copier le bloc `[h1]…[/h1]` (la zone entre les triplets de backticks) et le coller tel quel dans une annonce, un commentaire de collecte ou le forum — Steam convertit le BBCode. Les URL cliquables passent par `[url=…]`.
- **Mettre à jour la version** : remplacer « v1.6.1 » (2 occurrences dans le texte Discord, 1 dans le BBCode) à la prochaine release.
- **Images** : sur les deux plateformes, une ou deux captures d'écran juste sous le titre augmentent beaucoup l'impact (suggestion : l'éditeur ECF avec la fiche d'info, et la carte 2D d'un playfield).
