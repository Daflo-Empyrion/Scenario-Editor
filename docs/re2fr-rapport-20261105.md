# RE2-FR — Rapport de corrections et état, session du 05/11/2026

## Verdict en une ligne

Le **serveur dédié charge** le scénario (947 playfields, 0 erreur) et le **bilan de
l'éditeur est à 0 avertissement / 0 erreur** — mais le **client ne démarre toujours
pas** : `NullReferenceException` dans `ConfigTree.FormatMenu` (arbre technologique).
7 causes réelles ont été corrigées ; celle du plantage client reste inconnue.

## Ce qui est prouvé

| Test | Résultat |
|---|---|
| Boot serveur dédié (copie de travail) | ✅ `Server started listening`, 947 playfields, 0 `-ERR-` |
| Bilan de lancement (éditeur) | ✅ 0 avertissement / 0 erreur |
| Lancement client | ❌ NRE `ConfigTree.FormatMenu` → fermeture |
| Client avec les **6 configs de la base RE2 Beta** | ✅ il charge (aucun NRE) |

Dernier point capital : le plantage vient donc **des fichiers de `Content/Configuration`
propres à RE2-FR**, pas des prefabs, ni des playfields, ni des dialogues.
`ItemsConfig` a été innocenté par test (remplacé par celui de la base → NRE quand même).

## Corrections appliquées (avec preuve)

1. **Bloc `PentaxidSeedCrystal3` manquant** — `Next:` dans un sous-bloc `{ Child … }`
   référençait un bloc absent → le client jetait au chargement. Réintégré depuis ATL-PRO.
   *Nouveau contrôle ajouté à l'éditeur (`_check_transitions`) : `Next`, `UpgradeOn`, `DowngradeTo`.*
2. **41 blocs visibles dans l'arbre sans template** → masqués (`TechTreeNames: Hidden`).
3. **18 recettes `*Arena*` mortes** (sortie inexistante dans vanille/base/ATL) → supprimées ;
   elles faisaient **avorter le chargeur de templates**, ce qui cascadait jusqu'au NRE.
4. **Doublon de clé `Eden_DroneHawkPlayerUnit`** — un import de ma part sur un objet déjà
   présent → `ArgumentException … same key has already been added`. Import annulé.
5. **73 blocs `+Block` sans `Id`** (patchs de la vanille copiés seuls) → 73 Ids libres attribués.
6. **5 matériaux manquants** (`Naqahdah`, `DevicePRO`, `ThrusterPRO`, `WeaponLargePRO`,
   `WeaponSmallPRO`, 143 blocs les référencent) → réintégrés depuis la base.
7. **POI / prefabs / playfields** (travaux antérieurs de la session) : 64 entrées POI mortes
   supprimées, 70 zones de spawn inertes, 244 prefabs importés pour 8 groupes POI, 100
   références de groupes réalignées, 7 références de dialogues réparées, bloc YAML cassé
   (`EdenOcean2`) restauré, arbre technologique recadré (niveaux, `Hidden`).

## Hypothèses écartées, avec la preuve

- Blocs sans Id / Ids en double / bloc `Id: 0` absent → **non** (0 doublon, `Air` présent).
- `TechTreeParent: ""` (106 cas) → **normal**, la base en a 56 et charge.
- Collision d'Ids entre `BlocksConfig` et `ItemsConfig` (773 cas) → **normal**, la base en a 796.
- `ItemsConfig` de RE2-FR → **innocenté** par test.
- Templates orphelins → **corrigés**, le NRE persiste sans aucun message préalable.

## État actuel des fichiers

| Fichier | État |
|---|---|
| `BlocksConfig.ecf` | modifié (corrections 1, 2, 5 + POI/blocs antérieurs) |
| `ItemsConfig.ecf` | modifié (correction 4, import annulé) |
| `Templates.ecf` | modifié (correction 3) |
| `MaterialConfig.ecf` | modifié (correction 6) |
| `EClassConfig.ecf`, `BlockGroupsConfig.ecf` | **originaux RE2-FR** (non touchés) |
| Playfields, Prefabs, Extras, Configurations annexes | corrigés lors de la session |

## Revenir en arrière

Toutes les sauvegardes sont dans `C:\Users\David\.empyrion_editor\backups\RE2-FR\`
(79 Mo, 31 dossiers). Les deux repères utiles :

- **`20261105-102736-avant-bisect\BlocksConfig.ecf`** — votre `BlocksConfig` d'avant le bisect.
- **`20261105-102838-avant-bisect-complet\`** — vos 5 autres configs d'avant le bisect.

⚠️ Le dossier `…-avant-bisect-complet` **ne contient pas** le bon `BlocksConfig` (il a été
pris après son remplacement : c'est mon erreur de procédure, elle a coûté un lancement).

Pour restaurer un fichier précis, chaque dossier ne contient que les fichiers modifiés à
cette étape, nommés comme dans le scénario :

```powershell
Copy-Item "~\.empyrion_editor\backups\RE2-FR\20261105-111729-patchs-numerotes\BlocksConfig.ecf" `
          "C:\Dev\RE2-FR\Content\Configuration\BlocksConfig.ecf"
```

## Ce que je recommande si le sujet est repris

1. **Repartir des 6 configs de la base** (elles chargent, c'est prouvé) et réinjecter
   uniquement ce que les prefabs, playfields, dialogues et PDA réclament — calculable
   automatiquement (`IdMapping` des prefabs + références des playfields). C'est la seule
   voie déterministe ; elle évite une huitième chasse au coupable.
2. **Deux contrôles à ajouter au bilan** (ils auraient évité la moitié de cette session) :
   - un bloc importé **doit** porter un `Id` (les `+Block` sans Id sont des patchs) ;
   - un `Template` dont la sortie n'existe pas est **fatal** (il arrête le chargeur).
3. Ne plus jamais lancer un bisect en mélangeant les configs : les 6 fichiers sont
   interdépendants, un mélange base/FR crée des erreurs croisées qui noient le signal.
