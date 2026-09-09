# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
CAS DU PROTOCOLE DE TEST MANUEL -- donnees pures, aucun import Qt.

COMMENT ENRICHIR CE PROTOCOLE (a chaque evolution de l'application) :

1. NOUVELLE FONCTIONNALITE -> ajouter un cas (dict) dans CASES, avec un Id
   unique dans la bonne categorie, EN FIN DE SERIE (numerotation continue
   par ordre du fichier). Dans une session reprise d'une anterieure, il
   apparait automatiquement comme NOUVEAU, non testé.

2. MODIFICATION D'UN CAS EXISTANT (comportement change, etapes differentes)
   -> modifier le dict ET incrementer "rev" (absent = rev 1). Dans toute
   session reprise, le cas est remis a non testé et marque "A RETESTER" :
   c'est ce qui garantit qu'un test vert sur l'ancien code ne masque pas
   une regression. PENSER AU MIROIR ANGLAIS (core/test_protocol_en.py) :
   meme Id, meme nombre d'etapes, meme forme (str ou dict) -- un test
   d'integrite le verifie (tests/test_protocole_cas.py).

3. CAS OBSOLETE -> le supprimer ; sa ligne disparait des sessions suivantes
   (les anciennes sessions le conservent pour l'historique).

Champs d'un cas :
- "id"      : PREFIXE-numero, unique, PREFIXE = categorie
- "cat"     : code categorie (voir CATEGORIES)
- "titre"   : intitule court du test
- "pre"     : (facultatif) preconditions / preparation
- "etapes"  : liste ordonnee d'etapes a suivre. Chaque etape est :
    * une chaine (instruction seule), OU
    * un dict {"txt": instruction, "cmd": commande_ou_liste} ou "cmd"
      est ce que l'utilisateur peut COPIER-COLLER (commande console,
      chemin de fichier...) -- l'interface affiche un bouton copier.
- "attendu" : resultat attendu, observable et verifiable
- "rev"     : (facultatif) revision du cas -- incrementer a chaque modification

REECRITURE GLOBALE (08/09/2026) : les 248 cas reecrits en pas-a-pas
detaille pour utilisateurs non techniques (chaque clic, chaque commande,
formes copiables version installee EmpyrionEditorCLI.exe ET depot
"python cli/...") + traduction anglaise integrale. Discipline rev :
+1 sur chaque cas existant (TECH-003 excepte, cas N/A sans rien a
retester) ; les nouveaux cas PDA2 n'ont PAS de champ rev (rev 1 implicite).
Le FR est ACCENTUE (convention des nouvelles chaines, comme
data/i18n_strings.json).
"""


from core.test_protocol_en import CATEGORY_LABELS_EN, EN as _EN_TRANSLATIONS


CATEGORIES = [
    ("PROJ", "1. Projets & panneaux"),
    ("OPEN", "2. Ouverture & navigation"),
    ("ECF", "3. Edition ECF"),
    ("DLG", "4. Dialogues.ecf"),
    ("YAML", "5. Edition YAML / Playfields"),
    ("MAP", "6. Carte 2D / POI / Galaxie"),
    ("CSV", "7. Edition CSV"),
    ("TRAD", "8. Traduction"),
    ("FUS", "9. Copier / fusionner / dupliquer"),
    ("VERIF", "10. Verifications"),
    ("SAUV", "11. Sauvegardes & recuperation"),
    ("COMP", "12. Comparaison / recherche / PDA"),
    ("TECH", "13. Arbre technologique & fiche info"),
    ("OPT", "14. Options & i18n"),
    ("CLI", "15. CLI"),
    ("ROBU", "16. Robustesse"),
    ("BUILD", "17. Installateur / build"),
    ("GUI", "18. Interface, barre d'outils & theme"),
    ("PDA2", "19. Editeur PDA (nouveau module)"),
    ("ECO", "20. Economie (marchands PNJ)"),
]

CASES = [
    # ---------------------------------------------------------------- PROJ
    {
        "id": "PROJ-001", "cat": "PROJ", "rev": 2,
        "titre": "Nouveau projet : création standard depuis le Scénario A",
        "pre": "Un dossier de scénario Empyrion valide est disponible (Scénario A) -- par exemple une copie de Content/Scenarios/EmpyrionFrontier du jeu.",
        "etapes": [
            "Lance l'application : double-clique sur son icône (bureau ou menu Démarrer > Empyrion Scenario Editor).",
            "Dans la barre de menus tout en haut de la fenêtre, clique sur Fichier, puis sur Nouveau projet...",
            "À droite du champ Scénario A, clique le bouton Parcourir (bouton « ... »), navigue jusqu'au dossier de ton scénario, sélectionne-le puis clique le bouton Sélectionner un dossier.",
            "À droite du champ Copie de travail, clique Parcourir, place-toi là où tu veux créer le projet, saisis un nom de dossier QUI N'EXISTE PAS ENCORE (ex : MonScenario-Travail) puis clique Sélectionner un dossier.",
            "Ne remplis PAS le champ Scénario B : il est optionnel et le test porte sur un projet sans B.",
            "Lance la création en cliquant le bouton Créer de la fenêtre.",
        ],
        "attendu": "La copie de travail est créée puis sélectionnée automatiquement ; le panneau central « Copie de travail » se remplit avec l'arborescence du scénario ; le Scénario A d'origine est intact (aucun fichier modifié dedans).",
    },
    {
        "id": "PROJ-002", "cat": "PROJ", "rev": 2,
        "titre": "Nouveau projet : avec Scénario B optionnel",
        "pre": "Deux dossiers de scénarios DIFFÉRENTS (A et B) -- par exemple EmpyrionFrontier et Atlantis du jeu.",
        "etapes": [
            "Fichier > Nouveau projet... (même ouverture que PROJ-001).",
            "Remplis le Scénario A avec ton premier scénario (bouton Parcourir « ... » comme dans PROJ-001).",
            "Remplis le champ Scénario B avec le SECOND scénario, différent du premier.",
            "Remplis la Copie de travail avec un nom de dossier nouveau, puis clique Créer.",
        ],
        "attendu": "Les trois panneaux sont remplis (A à gauche, copie au centre, B à droite) ; le panneau B porte la mention « lecture seule » dans son titre.",
    },
    {
        "id": "PROJ-003", "cat": "PROJ", "rev": 2,
        "titre": "Nouveau projet : refus si la destination existe déjà",
        "etapes": [
            "Fichier > Nouveau projet...",
            "Remplis le Scénario A normalement.",
            "Pour la Copie de travail, clique Parcourir et choisis VOLONTAIREMENT un dossier qui EXISTE DÉJÀ (par exemple le dossier du scénario A lui-même).",
            "Clique Créer et observe.",
        ],
        "attendu": "Un message d'erreur clair est affiché (destination existante) ; rien n'a été écrit nulle part ; le dossier choisi est intact.",
    },
    {
        "id": "PROJ-004", "cat": "PROJ", "rev": 2,
        "titre": "Copie conforme : tous les fichiers du scénario sont recopiés",
        "etapes": [
            "Dans l'explorateur Windows, clic DROIT sur le dossier du Scénario A > Propriétés : note le nombre de fichiers et de dossiers indiqué.",
            "Crée un projet depuis ce scénario (PROJ-001).",
            "Clic droit sur le dossier de la copie de travail > Propriétés : compare les nombres.",
        ],
        "attendu": "Même nombre de fichiers, mêmes sous-dossiers : la copie est un miroir complet du scénario (pas seulement les .ecf/.yaml/.csv).",
    },
    {
        "id": "PROJ-005", "cat": "PROJ", "rev": 2,
        "titre": "Projets récents : proposition au démarrage",
        "pre": "Au moins un projet a déjà été créé (PROJ-001).",
        "etapes": [
            "Ferme l'application si elle est ouverte (croix en haut à droite de la fenêtre), puis relance-la.",
            "Observe la fenêtre (ou l'écran) de démarrage qui apparaît avant la fenêtre principale.",
        ],
        "attendu": "La liste des projets récents est proposée ; le bouton Ouvrir la sélection recharge le projet choisi (les trois panneaux se remplissent).",
    },
    {
        "id": "PROJ-006", "cat": "PROJ", "rev": 2,
        "titre": "Projets récents : réouverture SANS recopie (travail intact)",
        "pre": "Un projet existant dont tu as déjà enregistré une modification (le fichier est visible modifié sur le disque).",
        "etapes": [
            "Ouvre un projet, modifie une valeur dans un onglet (par exemple le titre d'un bloc), enregistre avec Ctrl+S (touches Ctrl et S en même temps), puis ferme l'application.",
            "Relance l'application et rouvre le MÊME projet via Projets récents (PROJ-005).",
            "Rouvre le fichier modifié : double-clic sur le fichier dans le panneau Copie de travail.",
        ],
        "attendu": "La modification d'hier est toujours là : la copie de travail n'a PAS été recopiée depuis le Scénario A à la réouverture.",
    },
    {
        "id": "PROJ-007", "cat": "PROJ", "rev": 2,
        "titre": "Trois panneaux : A/B lecture seule, centre éditable",
        "etapes": [
            "Dans le panneau Scénario A (gauche), déplie l'arborescence (petites flèches) puis double-clique sur BlocksConfig.ecf.",
            "Observe l'onglet qui s'ouvre : essaye le bouton + Bloc s'il est visible, et cherche le bouton Enregistrer.",
            "Ferme cet onglet (croix sur l'onglet), puis double-clique sur le MÊME fichier BlocksConfig.ecf dans le panneau Copie de travail (centre).",
            "Compare les boutons disponibles de cet onglet avec ceux de l'onglet du panneau A.",
        ],
        "attendu": "Scénario A : onglet en lecture seule (préfixe cadenas, pas de + Bloc / pas d'enregistrement possible). Copie de travail : onglet éditable (préfixe crayon ✎, outils d'édition actifs).",
    },
    {
        "id": "PROJ-008", "cat": "PROJ", "rev": 2,
        "titre": "Arborescence disque exacte dans les 3 panneaux",
        "etapes": [
            "Place l'explorateur Windows et l'application côte à côte (touche Windows + flèche Gauche pour coller l'explorateur à gauche, puis Windows + flèche Droite sur l'application).",
            "Compare, dossier par dossier, l'arbre du panneau Scénario A avec le contenu réel du dossier sur le disque (sous-dossiers et fichiers).",
        ],
        "attendu": "L'arborescence affichée est identique au disque : aucune catégorie inventée, aucun fichier caché ou ajouté.",
    },
    {
        "id": "PROJ-009", "cat": "PROJ", "rev": 2,
        "titre": "Changer le Scénario B en cours de route",
        "pre": "Un projet ouvert avec un Scénario B actif (PROJ-002).",
        "etapes": [
            "Fichier > Changer le Scénario B...",
            "Dans la fenêtre de choix de dossier, sélectionne un AUTRE dossier de scénario que l'actuel, puis clique Sélectionner un dossier.",
            "Une demande de confirmation apparaît : lis-la puis confirme le remplacement.",
        ],
        "attendu": "La confirmation est bien demandée ; après validation, le panneau B affiche l'arborescence du NOUVEAU scénario ; la copie de travail n'a pas bougé.",
    },
    {
        "id": "PROJ-010", "cat": "PROJ", "rev": 2,
        "titre": "Retirer le Scénario B",
        "pre": "Un projet ouvert avec un Scénario B actif.",
        "etapes": [
            "Fichier > Retirer le Scénario B.",
            "Observe les trois panneaux après l'opération.",
        ],
        "attendu": "Le panneau B se grise ou disparaît ; la copie de travail et le panneau A sont inchangés.",
    },
    {
        "id": "PROJ-011", "cat": "PROJ", "rev": 2,
        "titre": "Ouvrir un Scénario B quand aucun n'est actif",
        "pre": "Un projet ouvert SANS Scénario B (après PROJ-010, par exemple).",
        "etapes": [
            "Fichier > Ouvrir un Scénario B...",
            "Sélectionne un dossier de scénario puis clique Sélectionner un dossier.",
        ],
        "attendu": "Le panneau B s'active et affiche le contenu du dossier choisi, en lecture seule.",
    },
    {
        "id": "PROJ-012", "cat": "PROJ", "rev": 2,
        "titre": "Premier lancement : écran de langue (une seule fois)",
        "pre": "Simuler un tout premier lancement : ferme l'application, puis renomme le dossier de configuration (voir la commande à copier) en ajoutant « -old » à la fin.",
        "etapes": [
            {
                "txt": "Ouvre le dossier de configuration dans l'explorateur : colle le chemin ci-dessous dans la barre d'adresse de l'explorateur (la barre où il y a écrit Ce PC) puis appuie sur Entrée. Renomme le dossier .empyrion_editor en .empyrion_editor-old (clic droit > Renommer).",
                "cmd": ["%USERPROFILE%/.empyrion_editor"],
            },
            "Lance l'application : l'écran de choix de langue apparaît (Français / English). Choisis une langue.",
            "Ferme puis relance l'application une seconde fois.",
        ],
        "attendu": "L'écran de langue n'apparaît qu'AU PREMIER lancement ; le choix est appliqué immédiatement (toute l'interface dans la langue choisie) et conservé au second lancement.",
    },
    {
        "id": "PROJ-013", "cat": "PROJ", "rev": 2,
        "titre": "Tutoriel automatique au démarrage + ne plus afficher",
        "etapes": [
            "Au lancement de l'application, laisse le tutoriel s'ouvrir tout seul (ne le ferme pas tout de suite).",
            "Dans la fenêtre de tutoriel, coche la case « Ne plus afficher automatiquement au démarrage », puis ferme la fenêtre.",
            "Ferme l'application et relance-la.",
        ],
        "attendu": "Au relancement, le tutoriel ne s'ouvre plus tout seul ; il reste accessible à la demande via Aide > Tutoriels...",
    },
    {
        "id": "PROJ-014", "cat": "PROJ", "rev": 2,
        "titre": "Bouton FR/EN : bascule sans perdre le travail",
        "pre": "Un projet ouvert avec un onglet contenant une modification non enregistrée (le titre d'onglet est rouge avec un crayon).",
        "etapes": [
            "Clique sur le bouton FR/EN situé en haut à droite de la fenêtre.",
            "Observe les menus, les panneaux et l'onglet modifié.",
        ],
        "attendu": "Toute l'interface bascule dans l'autre langue ; l'onglet modifié reste ouvert et toujours marqué comme modifié (rien n'est perdu).",
    },
    {
        "id": "PROJ-015", "cat": "PROJ", "rev": 2,
        "titre": "Nouveau projet : destination non inscriptible refusée AVANT la copie",
        "pre": "Un dossier de destination dont l'écriture échouera (ex : un chemin dont un dossier parent est en réalité un FICHIER, ou un dossier réseau sans droit d'écriture).",
        "etapes": [
            "Fichier > Nouveau projet...",
            "Remplis le Scénario A normalement.",
            "Pour la Copie de travail, saisis (ou colle via Parcourir) la destination impossible préparée.",
            "Clique Créer et observe.",
        ],
        "attendu": "Message d'erreur immédiat « Dossier de destination inaccessible en écriture » ; la copie n'a PAS démarré ; aucun dossier partiel n'a été créé.",
    },
    # ---------------------------------------------------------------- OPEN
    {
        "id": "OPEN-001", "cat": "OPEN", "rev": 2,
        "titre": "Double-clic fichier copie de travail : onglet éditable",
        "etapes": [
            "Dans le panneau central Copie de travail, déplie l'arborescence jusqu'à trouver BlocksConfig.ecf (racine du scénario, section Configuration ou selon l'arborescence réelle).",
            "Double-clique sur BlocksConfig.ecf (deux clics rapides).",
            "Observe le titre du nouvel onglet et essaye de cliquer dans le tableau de propriétés d'un bloc.",
        ],
        "attendu": "Un onglet s'ouvre, préfixé du crayon ✎ (éditable) : les valeurs sont modifiables, les boutons d'édition (+ Bloc, + Propriété, Enregistrer) sont actifs.",
    },
    {
        "id": "OPEN-002", "cat": "OPEN", "rev": 2,
        "titre": "Double-clic fichier Scénario A/B : lecture seule",
        "etapes": [
            "Dans le panneau Scénario A (gauche), repère le MÊME fichier BlocksConfig.ecf.",
            "Double-clique dessus.",
            "Compare avec l'onglet de la copie de travail (OPEN-001) : préfixe du titre, boutons disponibles, tentative de modification d'une valeur.",
        ],
        "attendu": "L'onglet est préfixé du cadenas 🔒 (lecture seule) : aucune modification possible, pas d'enregistrement.",
    },
    {
        "id": "OPEN-003", "cat": "OPEN", "rev": 2,
        "titre": "Onglet déjà ouvert : resélection au lieu du doublon",
        "etapes": [
            "Double-clique une première fois sur BlocksConfig.ecf de la copie de travail : l'onglet s'ouvre.",
            "Sans fermer cet onglet, double-clique une DEUXIÈME fois sur le même fichier dans l'arbre.",
        ],
        "attendu": "Le second double-clic sélectionne (met au premier plan) l'onglet déjà ouvert au lieu d'en ouvrir une seconde copie : il n'y a jamais deux onglets pour le même fichier.",
    },
    {
        "id": "OPEN-004", "cat": "OPEN", "rev": 2,
        "titre": "Fermeture d'un onglet (croix)",
        "etapes": [
            "Ouvre un onglet (OPEN-001), puis clique la petite croix située sur l'onglet lui-même (à droite de son titre).",
            "Rouvre le fichier par double-clic : le contenu affiché est relu depuis le disque.",
        ],
        "attendu": "L'onglet se ferme proprement ; le fichier sur disque n'est pas touché par la fermeture (aucune écriture).",
    },
    {
        "id": "OPEN-005", "cat": "OPEN", "rev": 2,
        "titre": "Recherche dans l'arbre ECF (Id / Name / CustomIcon)",
        "etapes": [
            "Dans un onglet ECF ouvert, repère la barre Rechercher (champ de saisie au-dessus de l'arbre de blocs, à gauche).",
            "Tape l'Id d'un bloc connu (un nombre, ex : 1625) puis appuie sur Entrée.",
            "Rappuie sur Entrée : la sélection passe au résultat suivant. Recommence encore une fois.",
            "Recommence l'essai en cherchant cette fois un Name (texte, ex : Hull) puis un CustomIcon.",
        ],
        "attendu": "Le premier appui saute au premier bloc correspondant (sélectionné et visible), chaque Entrée suivante passe au résultat suivant, puis reboucle au début.",
    },
    {
        "id": "OPEN-006", "cat": "OPEN", "rev": 2,
        "titre": "Groupes de section affichés en en-têtes",
        "pre": "Un fichier avec séparateurs ### (ex : Containers.ecf de la vanille).",
        "etapes": [
            "Double-clique le fichier dans la copie de travail pour l'ouvrir.",
            "Observe le haut de l'arbre de blocs : les titres de section (lignes commençant par ### dans le fichier) apparaissent en tête des groupes.",
        ],
        "attendu": "Les titres de section sont affichés en tête de groupe dans l'arbre et ne sont pas cliquables (ce sont des séparateurs, pas des blocs).",
    },
    {
        "id": "OPEN-007", "cat": "OPEN", "rev": 2,
        "titre": "Étiquettes ## affichées à côté du bloc",
        "pre": "Un fichier avec étiquettes ## placées avant un bloc.",
        "etapes": [
            "Ouvre le fichier (double-clic dans la copie de travail).",
            "Repère dans l'arbre le bloc qui est précédé d'une étiquette ## dans le fichier.",
        ],
        "attendu": "Le nom de l'étiquette apparaît entre parenthèses à côté de l'identifiant du bloc dans l'arbre.",
    },
    {
        "id": "OPEN-008", "cat": "OPEN", "rev": 2,
        "titre": "En-tête de fichier extrait et affiché",
        "etapes": [
            "Ouvre BlocksConfig.ecf (double-clic, copie de travail).",
            "Ouvre le panneau d'explication du fichier : cherche le bouton/bandeau d'aide ou d'explication en haut de l'onglet (l'entête du fichier est le bloc de commentaires # tout au début du fichier).",
        ],
        "attendu": "La documentation technique d'en-tête est affichée de façon lisible (texte sans les #) dans le panneau d'explication.",
    },
    {
        "id": "OPEN-009", "cat": "OPEN", "rev": 4,
        "titre": "Fichier non supporté : aperçu intégré ou message clair",
        "etapes": [
            "Dans la copie de travail, place (ou repère) une image (png/jpg) -- par exemple une texture d'icône -- puis double-clique dessus.",
            "Recommence avec un PDF (l'aperçu PDF est désormais EMBARQUÉ dans l'installeur : plus besoin du module optionnel QtPdf).",
            "Recommence avec un fichier sans parseur ni visionneuse (texture jeu .dds, modèle 3D...) : un message clair s'affiche, c'est voulu.",
        ],
        "attendu": "Image ou PDF : un onglet APERÇU en lecture seule affiche le contenu (PDF embarqué depuis v1.6.2 -- avant, module optionnel QtPdf requis). Formats sans parseur NI visionneuse : message explicite (pas de plantage, pas d'onglet vide).",
    },
    {
        "id": "OPEN-010", "cat": "OPEN", "rev": 2,
        "titre": "Fichier .txt : lecture simple",
        "etapes": [
            "Double-clique un fichier .txt du scénario dans la copie de travail.",
            "Compare le contenu affiché avec le fichier ouvert dans le Bloc-notes Windows (clic droit sur le fichier > Ouvrir avec > Bloc-notes).",
        ],
        "attendu": "Un onglet texte s'ouvre, contenu fidèle au fichier (lecture seule ou édition basique fonctionnelle).",
    },
    {
        "id": "OPEN-011", "cat": "OPEN", "rev": 3,
        "titre": "Titre d'onglet : marqueur de modification",
        "etapes": [
            "Dans un onglet éditable, modifie une valeur SANS enregistrer (double-clic sur une valeur du tableau, tape autre chose, valide avec Entrée).",
            "Observe le titre de l'onglet en haut.",
            "Enregistre (Ctrl+S) puis ré-observe le titre.",
        ],
        "attendu": "Onglet modifié : icône crayon + point plein + TEXTE D'ONGLET EN ROUGE, visible sur tous les thèmes. Après enregistrement, le marqueur disparaît.",
    },
    # ---------------------------------------------------------------- ECF
    {
        "id": "ECF-001", "cat": "ECF", "rev": 3,
        "titre": "Affichage des propriétés en mode liste (valeurs en liste déroulante)",
        "etapes": [
            "Ouvre BlocksConfig.ecf de la copie de travail (double-clic).",
            "Dans l'arbre de gauche, clique UNE seule fois sur un bloc classique (ex : un bloc de structure) pour le sélectionner : ses propriétés s'affichent à droite, une ligne par propriété (clé à gauche, valeur à droite).",
            "Édite une valeur (double-clic dessus) : une liste déroulante EDITABLE s'ouvre avec les valeurs déjà observées dans le fichier.",
            "Recommence sur un bloc dont le genre (Group) est UNIQUE dans le fichier : la liste doit quand même proposer des valeurs (pool global de repli).",
        ],
        "attendu": "Une ligne par propriété, clé à gauche / valeur éditable AVEC LISTE DÉROULANTE des valeurs observées du fichier ; même sur un bloc au genre unique, la liste propose des valeurs (pool global -- correctif v1.6.1 : liste vide avant).",
    },
    {
        "id": "ECF-002", "cat": "ECF", "rev": 2,
        "titre": "Détection automatique du mode tableau (Child Items)",
        "pre": "Un bloc avec propriétés numérotées Name_0/Name_1... (ex : containers vanilla).",
        "etapes": [
            "Dans l'arbre, sélectionne un bloc à structure répétitive (ses clés finissent par _0, _1, _2...).",
            "Observe le panneau de droite : affichage en TABLEAU (une colonne par paramètre) au lieu de la liste.",
            "Cherche le bouton + Ligne sous le tableau : il doit être présent et actif.",
        ],
        "attendu": "Le bloc s'affiche en tableau (une colonne par paramètre), avec le bouton + Ligne actif.",
    },
    {
        "id": "ECF-003", "cat": "ECF", "rev": 3,
        "titre": "Modification d'une valeur + surlignage de session",
        "etapes": [
            "Double-clique une valeur dans le tableau de propriétés, remplace-la par une autre, valide avec Entrée.",
            "Observe la cellule modifiée puis le titre de l'onglet.",
        ],
        "attendu": "La cellule modifiée est surlignée (trace de session) ; le titre de l'onglet passe en état modifié (crayon + point + texte rouge).",
    },
    {
        "id": "ECF-004", "cat": "ECF", "rev": 2,
        "titre": "Enregistrement Ctrl+S + round-trip fidèle",
        "etapes": [
            "Modifie une valeur puis appuie sur Ctrl+S (touches Ctrl et S en même temps).",
            {
                "txt": "Vérifie la fidélité du fichier en ligne de commande : copie l'une des commandes ci-dessous et colle-la dans une invite de commandes (voir CLI-001 pour ouvrir une invite), en remplaçant <fichier> par le chemin du fichier modifié (astuce : Maj+clic droit sur le fichier > Copier en tant que chemin d'accès).",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-ecf \"<fichier>\"",
                    "python cli/verifier_parser_ecf.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Enregistrement OK ; le vérificateur affiche que le round-trip (relecture/réécriture) est fidèle, sans erreur.",
    },
    {
        "id": "ECF-005", "cat": "ECF", "rev": 3,
        "titre": "Ctrl+Z de l'onglet : annulation d'une modification",
        "etapes": [
            "Modifie une valeur (ne l'enregistre pas).",
            "Clique quelque part dans l'ARBRE de blocs (pour ne pas être en cours de frappe dans un champ), puis appuie sur Ctrl+Z.",
            "Recommence le test en laissant le curseur DANS un champ de saisie : Ctrl+Z y annule la frappe (comportement normal), pas la modification du bloc.",
        ],
        "attendu": "La valeur d'origine revient et le marqueur de modification disparaît. Dans un champ texte, Ctrl+Z reste l'annulation de la saisie (correctif v1.6.1 : le raccourci était ambigu et n'annulait rien).",
    },
    {
        "id": "ECF-006", "cat": "ECF", "rev": 3,
        "titre": "Annotation automatique des modifications",
        "pre": "Options > Annoter les modifications automatiquement activé, nom configuré (voir OPT-001).",
        "etapes": [
            "Modifie une valeur, puis enregistre avec Ctrl+S.",
            {
                "txt": "Ouvre le fichier brut dans le Bloc-notes pour voir l'annotation : copie la commande ci-dessous dans une invite de commandes (remplace <fichier> par le chemin réel), ou ouvre le fichier avec le Bloc-notes à la main.",
                "cmd": ["notepad \"<fichier>\""],
            },
            "Re-modifie LA MÊME propriété avec une autre valeur, enregistre, ré-ouvre le fichier.",
        ],
        "attendu": "La ligne modifiée porte un commentaire « # original: <ancien> -- Mod par <nom> ». COMPORTEMENT NORMAL : l'annotation est écrite À L'ENREGISTREMENT seulement (rien dans le fichier tant que tu n'as pas enregistré). Les éditions répétées de la MÊME propriété REMPLACENT la note précédente (pas d'accumulation).",
    },
    {
        "id": "ECF-007", "cat": "ECF", "rev": 2,
        "titre": "Désactivation des annotations automatiques",
        "etapes": [
            "Dans la barre de menus : Options > Annoter les modifications automatiquement (décoche la case si cochée).",
            "Modifie une valeur, enregistre (Ctrl+S), ouvre le fichier brut (commande de ECF-006).",
        ],
        "attendu": "Aucun commentaire « # original » n'a été ajouté sur la ligne modifiée.",
    },
    {
        "id": "ECF-008", "cat": "ECF", "rev": 3,
        "titre": "+ Propriété : ajout simple (listes déroulantes)",
        "etapes": [
            "Sélectionne un bloc dans l'arbre, puis clique le bouton + Propriété (au-dessus du tableau de propriétés).",
            "Dans le dialogue, observe : la CLÉ et la VALEUR sont des listes déroulantes EDITABLES, pré-remplies avec les clés/valeurs déjà observées dans le fichier.",
            "Choisis une paire clé/valeur qui existe ailleurs dans le fichier, puis valide.",
        ],
        "attendu": "La propriété apparaît sur le bloc, grisée/surlignée dans le tableau, et le bloc est marqué dans l'arbre de gauche (correctif v1.6.1 : champs de saisie à vide sans liste, pas de surlignage).",
    },
    {
        "id": "ECF-009", "cat": "ECF", "rev": 2,
        "titre": "+ Propriété : plusieurs paires sur une même ligne",
        "etapes": [
            "Clique + Propriété sur un bloc.",
            "Dans le champ de valeur, saisis plusieurs paires en respectant la syntaxe du jeu : param1: 0.6, param2: \"1,3\" (séparées par des virgules, guillemets si la valeur contient une virgule).",
            "Valide, puis ouvre le fichier brut (ECF-006) : les paires sont sur UNE ligne.",
        ],
        "attendu": "Les paires sont regroupées sur une seule ligne du bloc, exactement comme le jeu les écrit.",
    },
    {
        "id": "ECF-010", "cat": "ECF", "rev": 2,
        "titre": "+ Bloc : choix Id + Name",
        "etapes": [
            "Clique le bouton + Bloc (au-dessus de l'arbre ou dans la barre d'outils de l'onglet ECF).",
            "Dans l'assistant, choisis le mode AVEC Id, saisis un Id libre (nombre < 8192 non déjà utilisé) et un Name libre.",
            "Termine l'assistant (bouton Créer). Accepte ou refuse la proposition de fiche d'info qui peut suivre.",
        ],
        "attendu": "Le bloc est créé avec l'Id et le Name demandés ; l'assistant vérifie la saisie en direct (limite 8192, doublons interdits).",
    },
    {
        "id": "ECF-011", "cat": "ECF", "rev": 2,
        "titre": "+ Bloc : choix Name seul (au-delà de la limite d'Id)",
        "etapes": [
            "Clique + Bloc.",
            "Choisis le mode Name SEUL (sans Id), saisis un Name libre et termine.",
        ],
        "attendu": "Le bloc est créé sans Id : il est identifié par son Name uniquement (cas des blocs au-delà de la limite d'Id du jeu).",
    },
    {
        "id": "ECF-012", "cat": "ECF", "rev": 2,
        "titre": "+ Bloc : tableau de propriétés du fichier + menus déroulants",
        "etapes": [
            "Clique + Bloc et observe la liste des propriétés proposées dans l'assistant.",
            "Ouvre le menu déroulant d'une VALEUR proposée.",
        ],
        "attendu": "Les propriétés proposées viennent du fichier de travail, triées par usage ; les valeurs suggérées sont des valeurs réelles déjà vues dans le fichier.",
    },
    {
        "id": "ECF-013", "cat": "ECF", "rev": 2,
        "titre": "+ Bloc : vérification d'Id en direct (8192 / doublon)",
        "etapes": [
            "Dans l'assistant + Bloc (mode avec Id), saisis un Id SUPÉRIEUR à 8192 : observe le message d'erreur.",
            "Saisis ensuite un Id déjà utilisé par un bloc du fichier : observe le message d'erreur.",
            "Essaye de terminer l'assistant dans cet état.",
        ],
        "attendu": "Erreur visible dans les deux cas ; la création est impossible tant que l'Id est invalide.",
    },
    {
        "id": "ECF-014", "cat": "ECF", "rev": 2,
        "titre": "+ Bloc : proposition du Template associé",
        "pre": "Templates.ecf est présent dans la copie de travail.",
        "etapes": [
            "Crée un bloc via + Bloc (ECF-010).",
            "À la fin de l'assistant, accepte la proposition de créer le Template (recette de fabrication) associé.",
            "Dans la fenêtre d'ajustement qui suit, valide, puis ouvre Templates.ecf (double-clic dans la copie de travail) et cherche le Template créé.",
        ],
        "attendu": "Un Template de même Name est créé dans Templates.ecf, avec ses ingrédients ajoutables par liste déroulante de noms d'items.",
    },
    {
        "id": "ECF-015", "cat": "ECF", "rev": 3,
        "titre": "+ Ligne : numérotation automatique (Name_6 après Name_5)",
        "pre": "Un bloc en mode tableau avec Name_0..Name_5 (ECF-002).",
        "etapes": [
            "Sélectionne le bloc en mode tableau, clique + Ligne.",
            "Choisis le type Name dans la liste proposée, saisis une valeur simple (un nombre, ex : 5), valide.",
            "Recommence en saisissant cette fois une valeur CONTENANT une virgule ou un espace (ex : pierre, bois).",
            "Ouvre le fichier brut (ECF-006) pour vérifier l'écriture.",
        ],
        "attendu": "La ligne est insérée avec le numéro suivant (Name_6) à la bonne place. Une valeur contenant virgule ou espace est automatiquement MISE ENTRE GUILLEMETS (sinon elle serait coupée en deux) ; un chiffre simple reste sans guillemets.",
    },
    {
        "id": "ECF-016", "cat": "ECF", "rev": 2,
        "titre": "+ Ligne : choix du Type parmi les préfixes du fichier",
        "etapes": [
            "Sur un bloc possédant Name_N ET Group_N, ouvre + Ligne et observe la liste Type.",
            "Compare la liste avec les préfixes réellement présents sur le bloc.",
        ],
        "attendu": "Le Type propose les préfixes réels du bloc (Name, Group...), pas une liste figée.",
    },
    {
        "id": "ECF-017", "cat": "ECF", "rev": 3,
        "titre": "Suppression d'une propriété (et Annuler reste sur le bloc)",
        "etapes": [
            "Dans l'arbre, descends vers un bloc LOIN du début de la liste (fais défiler l'arbre).",
            "Clic droit sur une propriété du bloc (dans l'arbre) > Supprimer, confirme.",
            "Appuie sur Ctrl+Z (annulation de l'onglet) et observe où se trouve la sélection dans l'arbre.",
        ],
        "attendu": "La ligne disparaît du bloc, et l'annulation la restaure EN RESTANT positionné sur le même bloc (correctif v1.6.1 : après Annuler, l'arbre remontait au tout début).",
    },
    {
        "id": "ECF-018", "cat": "ECF", "rev": 2,
        "titre": "Suppression d'un bloc (confirmation demandée)",
        "etapes": [
            "Clic droit sur un bloc de l'arbre > Supprimer.",
            "Une confirmation est demandée : lis-la, puis confirme.",
        ],
        "attendu": "La confirmation est affichée ; après confirmation, le bloc disparaît de l'arbre et du fichier (Ctrl+S puis vérification possible par ECF-004).",
    },
    {
        "id": "ECF-019", "cat": "ECF", "rev": 2,
        "titre": "Désactiver ce bloc (test) : commentaire à position exacte",
        "etapes": [
            "Clic droit sur un bloc > Désactiver ce bloc (test).",
            "Enregistre (Ctrl+S) puis ouvre le fichier brut (ECF-006).",
            "Cherche le bloc dans le fichier (Ctrl+F dans le Bloc-notes).",
        ],
        "attendu": "Le bloc est commenté (désactivé) À SA POSITION D'ORIGINE dans le fichier : il n'a pas été déplacé en fin de fichier.",
    },
    {
        "id": "ECF-020", "cat": "ECF", "rev": 2,
        "titre": "Liste des blocs désactivés + réactivation",
        "pre": "Au moins un bloc désactivé via ECF-019.",
        "etapes": [
            "Ouvre la liste des blocs désactivés (bouton ou menu de l'onglet ECF).",
            "Sélectionne le bloc désactivé et clique Réactiver.",
            "Vérifie le fichier brut (ECF-006).",
        ],
        "attendu": "Le bloc revient exactement à son état et à sa position d'origine dans le fichier.",
    },
    {
        "id": "ECF-021", "cat": "ECF", "rev": 2,
        "titre": "Filtrer par propriété",
        "etapes": [
            "Dans l'onglet ECF, lance Filtrer par propriété... (bouton ou menu de l'onglet).",
            "Coche une propriété courante (ex : Mass) et applique.",
            "Observe l'arbre, puis décoche pour revenir à la vue complète.",
        ],
        "attendu": "L'arbre n'affiche plus que les blocs possédant (ou n'ayant pas, selon l'option choisie) la propriété cochée ; le retour à la vue complète restaure tout.",
    },
    {
        "id": "ECF-022", "cat": "ECF", "rev": 2,
        "titre": "Panneau d'explication : glossaire fait main",
        "etapes": [
            "Ouvre BlocksConfig.ecf, déploie le panneau d'explication (OPEN-008).",
            "Lis quelques définitions du glossaire (ex : Id, Mass, HitPoints).",
        ],
        "attendu": "Le glossaire est rédigé et clarifié en français : ce fichier est couvert par le glossaire manuel (pas de traduction automatique grossière).",
    },
    {
        "id": "ECF-023", "cat": "ECF", "rev": 2,
        "titre": "Panneau d'explication : traduction automatique hors glossaire",
        "pre": "Un fichier ECF NON couvert par le glossaire manuel.",
        "etapes": [
            "Ouvre ce fichier et son panneau d'explication.",
            "Clique le bouton Traduire automatiquement du panneau.",
        ],
        "attendu": "Le texte original est traduit à la demande (ou erreur claire si la traduction en ligne est désactivée -- voir TRAD-013).",
    },
    {
        "id": "ECF-024", "cat": "ECF", "rev": 3,
        "titre": "Transformation en masse : choix de la propriété (autocomplétion qui coche)",
        "etapes": [
            "Lance Transformation en masse... (bouton/menu de l'onglet ECF).",
            "Dans le champ de propriété, tape les premières lettres d'une propriété courante (ex : cra pour CraftTime) : une suggestion d'autocomplétion apparaît.",
            "VALIDE la suggestion avec les flèches + Entrée, ou en cliquant dessus.",
            "Observe la liste de cases à cocher en dessous. Tape ensuite une clé qui n'existe pas (ex : xxx) : tout reste décoché.",
        ],
        "attendu": "L'autocomplétion propose les clés réellement présentes ; valider la suggestion COCHE automatiquement la case correspondante dans la liste du dessous (correctif v1.6.1 : il fallait défiler et cocher à la main). Une clé inexistante laisse tout décoché.",
    },
    {
        "id": "ECF-025", "cat": "ECF", "rev": 2,
        "titre": "Transformation en masse : les 5 opérations",
        "etapes": [
            "Dans Transformation en masse, choisis une propriété numérique courante (ex : Mass) sur une petite sélection de blocs.",
            "Applique successivement les 5 opérations : Multiplier (facteur 2), Ajouter (+10), Fixer (=100), Plafonner (max 500), Arrondir.",
            "Après chaque opération, vérifie le résultat mathématique sur quelques blocs (ECF-006 pour ouvrir le fichier, ou le tableau de l'onglet).",
        ],
        "attendu": "Chaque opération produit le résultat mathématique attendu dans le fichier, uniquement sur les blocs ciblés.",
    },
    {
        "id": "ECF-026", "cat": "ECF", "rev": 2,
        "titre": "Transformation en masse : aperçu complet + colonne Après éditable",
        "etapes": [
            "Prépare une transformation sur un lot de blocs, puis clique Aperçu.",
            "Dans le tableau d'aperçu : décoche UNE ligne, puis double-clique la valeur de la colonne Après d'une AUTRE ligne et corrige-la.",
            "Applique, puis vérifie le fichier : seules les lignes cochées ont changé, avec ta valeur « Après » corrigée.",
        ],
        "attendu": "L'aperçu n'est PAS tronqué (toutes les lignes visibles) ; seules les lignes cochées sont écrites, avec la valeur « Après » éventuellement corrigée à la main.",
    },
    {
        "id": "ECF-027", "cat": "ECF", "rev": 2,
        "titre": "Transformation en masse : filtres genre + identités",
        "etapes": [
            "Applique une transformation avec filtre par GENRE de bloc (ex : seulement les blocs Group: SVCargoContainer).",
            "Applique ensuite une transformation avec une liste d'IDENTITÉS de blocs (noms précis saisis/choisis).",
            "Vérifie à chaque fois quels blocs ont été modifiés.",
        ],
        "attendu": "Seuls les blocs correspondant au filtre (genre ou liste d'identités) sont modifiés.",
    },
    {
        "id": "ECF-028", "cat": "ECF", "rev": 2,
        "titre": "Transformation en masse : annulation Ctrl+Z",
        "etapes": [
            "Applique une transformation en masse (ECF-025) sans enregistrer.",
            "Clique dans l'arbre puis appuie sur Ctrl+Z.",
        ],
        "attendu": "Toutes les valeurs transformées reviennent à leur état d'avant l'opération.",
    },
    {
        "id": "ECF-029", "cat": "ECF", "rev": 2,
        "titre": "Fiche d'en-tête ECF : traduction de l'en-tête",
        "etapes": [
            "Dans un onglet ECF, repère le bouton dédié à la traduction de l'en-tête (près du panneau d'explication, cf. OPEN-008).",
            "Clique-le et observe le résultat.",
        ],
        "attendu": "L'en-tête (bloc de commentaires # du début de fichier) est traduit ; ou erreur claire si la traduction en ligne est désactivée.",
    },
    {
        "id": "ECF-030", "cat": "ECF", "rev": 3,
        "titre": "Fusion ECF (A vers copie) : APERÇU modifiable avant écriture",
        "pre": "Options > Autoriser la fusion activé. Le fichier existe DÉJÀ dans la copie de travail (pour avoir des différences, modifie d'abord un bloc côté A dans un fichier, sans le recopier).",
        "etapes": [
            "Dans le panneau Scénario A, clic droit sur un fichier ECF > fusionner vers la copie de travail.",
            "Lis l'APERÇU qui s'ouvre : une ligne par différence (bloc ajouté / propriété ajoutée / valeur différente), avec colonnes AVANT et APRÈS.",
            "Décoche une ligne, puis double-clique la colonne « Après » d'une autre ligne et corrige la valeur.",
            "Valide : observe l'onglet qui s'ouvre tout seul.",
        ],
        "attendu": "RIEN n'est écrit avant validation. À la validation, seules les lignes COCHÉES sont appliquées (avec tes corrections « Après ») ; les valeurs différentes restent celles de la copie de travail sauf si tu les as cochées. L'onglet du fichier s'ouvre DIRECTEMENT positionné sur le premier bloc fusionné.",
    },
    {
        "id": "ECF-031", "cat": "ECF", "rev": 3,
        "titre": "Tableau de propriétés : liste déroulante sur chaque valeur",
        "pre": "Un fichier ECF ouvert avec plusieurs blocs du même genre portant la même propriété (ex : CraftTime).",
        "etapes": [
            "Sélectionne un bloc à gauche, puis dans le tableau de droite clique la VALEUR d'une propriété (ex : CraftTime).",
            "Ouvre la liste déroulante : elle propose les valeurs réellement observées dans le fichier (triées par fréquence). Choisis-en une.",
            "Recommence en TAPANT cette fois une valeur totalement nouvelle (saisie libre) et valide avec Entrée.",
        ],
        "attendu": "La cellule propose les valeurs observées du fichier (tri fréquence) ; la saisie libre reste possible ; la modification est appliquée au bloc (ligne surlignée + compteur de modifications à jour).",
    },
    # ---------------------------------------------------------------- DLG
    {
        "id": "DLG-001", "cat": "DLG", "rev": 2,
        "titre": "Ouverture de Dialogues.ecf : navigateur dédié",
        "etapes": [
            "Dans la copie de travail, double-clique sur Dialogues.ecf.",
            "Observe les zones de l'onglet : arbre des dialogues à gauche, contenu du dialogue sélectionné à droite, et l'édition ECF classique reste disponible.",
        ],
        "attendu": "Le navigateur de dialogues s'ajoute À l'édition ECF classique (il ne la remplace pas) : arbre des dialogues + panneau de lecture/édition.",
    },
    {
        "id": "DLG-002", "cat": "DLG", "rev": 3,
        "titre": "Navigation entre dialogues (Next / OptionNext)",
        "pre": "Dialogues.ecf ouvert en onglet : la colonne de GAUCHE liste les dialogues (arbre). Les liens Next/NextIf sont les champs « Next: » / « OptionNext: » des nœuds, visibles dans le panneau de droite.",
        "etapes": [
            "Double-clique un dialogue dans l'arbre de gauche pour l'afficher à droite.",
            "Dans le panneau de droite, repère le champ « Next: » d'un nœud : sa valeur est le nom d'un AUTRE dialogue.",
            "Retrouve ce dialogue destination dans l'arbre de gauche (barre de filtre au besoin), double-clique-le, et répète la chaîne 2 ou 3 fois.",
        ],
        "attendu": "Chaque dialogue s'affiche avec ses propres nœuds et textes ; l'arbre de gauche reste synchronisé (pas de perte de contexte). La navigation est MANUELLE via l'arbre : les liens ne sont pas cliquables dans le panneau de droite (évolution possible, voir bilan).",
    },
    {
        "id": "DLG-003", "cat": "DLG", "rev": 2,
        "titre": "Édition d'un texte de dialogue",
        "etapes": [
            "Dans le panneau de droite, modifie un texte de dialogue (ajoute par exemple un mot, ou des balises [b]...[/b]).",
            "Enregistre (Ctrl+S), puis vérifie le fichier : ECF-006 (Bloc-notes) ou commande verifier-ecf de ECF-004.",
        ],
        "attendu": "Le texte modifié est écrit fidèlement dans le fichier (round-trip), balises BBCode comprises.",
    },
    {
        "id": "DLG-004", "cat": "DLG", "rev": 2,
        "titre": "Cohérence dialogues : vérification des références croisées",
        "etapes": [
            "Dans la barre de menus : Vérification > Vérifier les références croisées (entre fichiers)...",
            "Active le contrôle Dialogues (case de la fenêtre), puis lance l'analyse.",
            "Lis les résultats (renvoi au cas VERIF-006 pour la correction).",
        ],
        "attendu": "Les liens Next/OptionNext orphelins (dialogue inexistant) sont détectés et listés.",
    },
    {
        "id": "DLG-005", "cat": "DLG", "rev": 2,
        "titre": "Round-trip Dialogues.ecf sans modification",
        "etapes": [
            "Ouvre Dialogues.ecf, puis enregistre immédiatement sans rien changer (Ctrl+S).",
            "Lance la vérification de fidélité sur le fichier : commande verifier-ecf (voir ECF-004).",
        ],
        "attendu": "Le fichier est reproduit à l'identique : aucune différence binaire signalée par le vérificateur.",
    },

    # ---------------------------------------------------------------- YAML
    {
        "id": "YAML-001", "cat": "YAML", "rev": 2,
        "titre": "YAML générique : arbre + édition de valeur",
        "etapes": [
            "Dans la copie de travail, double-clique un YAML simple non-playfield (par exemple un petit YAML de configuration du scénario).",
            "Sélectionne une entrée dans l'arbre, modifie sa valeur dans le champ de droite, puis clique le bouton Appliquer.",
            "Ouvre le dernier onglet « YAML complet » de la même fenêtre pour voir le texte brut.",
        ],
        "attendu": "La valeur modifiée apparaît dans l'arbre ET dans le YAML brut (dernier onglet), sans enregistrer.",
    },
    {
        "id": "YAML-002", "cat": "YAML", "rev": 2,
        "titre": "+ Entrée / Supprimer l'entrée sélectionnée",
        "etapes": [
            "Clique le bouton + Entrée de l'éditeur YAML : une nouvelle entrée apparaît dans l'arbre ; remplis son nom/valeur.",
            "Sélectionne-la puis clique Supprimer l'entrée sélectionnée.",
            "Observe l'arbre et l'onglet YAML complet après chaque opération.",
        ],
        "attendu": "L'ajout puis la suppression se reflètent dans l'arbre ET dans le YAML complet.",
    },
    {
        "id": "YAML-003", "cat": "YAML", "rev": 2,
        "titre": "Application automatique du texte en attente",
        "etapes": [
            "Tape une nouvelle valeur dans le champ SANS cliquer Appliquer, puis clique directement le bouton Enregistrer de l'onglet.",
            "Recommence : tape une valeur sans Appliquer, puis clique simplement sur une AUTRE entrée de l'arbre.",
        ],
        "attendu": "Le texte en attente est appliqué dans les deux cas (à l'enregistrement et au changement de sélection) : jamais perdu par oubli.",
    },
    {
        "id": "YAML-004", "cat": "YAML", "rev": 2,
        "titre": "Chaînes multilignes avec lignes vides",
        "pre": "Un playfield avec une Description multiligne.",
        "etapes": [
            "Ouvre le playfield, onglet YAML complet ou champ Description, et rédige un texte sur plusieurs lignes avec UNE LIGNE VIDE au milieu.",
            "Enregistre (Ctrl+S).",
            "Rouvre le fichier dans le Bloc-notes (ECF-006) : la Description doit contenir les retours à la ligne.",
        ],
        "attendu": "La ligne vide devient un vrai retour à la ligne dans le fichier ; l'affichage reste correct dans l'éditeur (et en jeu pour une description).",
    },
    {
        "id": "YAML-005", "cat": "YAML", "rev": 2,
        "titre": "Round-trip YAML fidèle",
        "etapes": [
            "Ouvre un YAML quelconque et enregistre immédiatement sans rien changer (Ctrl+S).",
            {
                "txt": "Vérifie la fidélité : commande ci-dessous (remplace <fichier>), ou compare les octets avant/après avec une copie faite avant l'enregistrement.",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-yaml \"<fichier>\"",
                    "python cli/verifier_parser_yaml.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Fichier identique octet pour octet (le vérificateur confirme le round-trip).",
    },
    {
        "id": "YAML-006", "cat": "YAML", "rev": 2,
        "titre": "Playfield : bascule auto vers l'éditeur structuré (8 onglets)",
        "etapes": [
            "Double-clique un playfield.yaml de la copie de travail (dossier Playfields).",
            "Observe les onglets de la fenêtre qui s'ouvre.",
        ],
        "attendu": "L'éditeur structuré s'ouvre avec ses 8 onglets : Carte 2D, Ressources, POI, Creatures, Drones/Vaisseaux, Zones de spawn, Effets spéciaux, YAML complet.",
    },
    {
        "id": "YAML-007", "cat": "YAML", "rev": 2,
        "titre": "Ressources : ajout avec liste déroulante de vrais blocs",
        "etapes": [
            "Dans le playfield ouvert, onglet Ressources, clique + ressource.",
            "Dans la nouvelle ligne, ouvre la liste déroulante du champ ressource.",
        ],
        "attendu": "La liste est peuplée des VRAIS blocs du scénario (pas de saisie à l'aveugle) ; la saisie libre reste possible.",
    },
    {
        "id": "YAML-008", "cat": "YAML", "rev": 2,
        "titre": "Ressources : colonne RegenAfter modifiable",
        "etapes": [
            "Onglet Ressources : double-clique la cellule RegenAfter d'une ressource, change la valeur, valide.",
            "Enregistre (Ctrl+S) puis vérifie dans l'onglet YAML complet (ou Bloc-notes) que la valeur est au bon endroit.",
        ],
        "attendu": "La nouvelle valeur RegenAfter est écrite au bon endroit de la section Resources.",
    },
    {
        "id": "YAML-009", "cat": "YAML", "rev": 3,
        "titre": "POI : tableau + entrées DÉSACTIVÉES nativement (grisées, réactivables)",
        "etapes": [
            "Onglet POI : modifie un champ d'un POI, enregistre, vérifie le YAML.",
            "Repère les lignes GRISEES « (désactivé) ... » en fin de tableau : ce sont des entrées commentées NATIVEMENT dans le fichier (ex : « # - GroupName: X » du RE2), pas par l'application.",
            "Clic droit sur une entrée grisée > Activer cette entrée.",
            "Enregistre puis vérifie le YAML brut : les lignes ne sont plus commentées.",
            "Appuie sur Ctrl+Z : l'opération doit s'annuler.",
        ],
        "attendu": "1) La modification est écrite correctement. 2) Les entrées commentées du fichier apparaissent GRISEES avec un compteur (« N entrée(s) désactivée(s) »). 3) « Activer » dé-commente les lignes : l'entrée devient une vraie ligne éditable sur disque, annulable (Ctrl+Z) -- nouveau v1.6.1. Même mécanisme dans Ressources/Creatures/Drones/Zones/Effets ET dans l'arbre ECF (blocs commentés natifs, ex : « #{ +Block »).",
    },
    {
        "id": "YAML-010", "cat": "YAML", "rev": 3,
        "titre": "Creatures : colonne Biome (éditable + filtre)",
        "etapes": [
            "Onglet Creatures : ouvre la liste déroulante de FILTRE par biome (au-dessus du tableau) et choisis un biome : le tableau ne montre que les créatures de ce biome.",
            "Édite le biome d'une créature (liste déroulante des biomes observés), enregistre, vérifie le YAML.",
        ],
        "attendu": "Le filtre n'affiche que les créatures du biome choisi. L'édition réécrit la ZONE « - Biomes: [...] » de la créature (le biome appartient à la zone, pas à la créature) ; une zone multi-biomes est remplacée par le biome choisi.",
    },
    {
        "id": "YAML-011", "cat": "YAML", "rev": 2,
        "titre": "Drones / Vaisseaux : tableau fonctionnel",
        "etapes": [
            "Onglet Drones/Vaisseaux : modifie une entrée (ex : un nom ou un nombre), enregistre, vérifie le YAML complet.",
        ],
        "attendu": "La modification est écrite correctement dans la bonne section.",
    },
    {
        "id": "YAML-012", "cat": "YAML", "rev": 2,
        "titre": "Zones de spawn : tableau fonctionnel",
        "etapes": [
            "Onglet Zones de spawn : modifie une entrée, enregistre, vérifie le YAML complet.",
        ],
        "attendu": "La modification est écrite correctement.",
    },
    {
        "id": "YAML-013", "cat": "YAML", "rev": 2,
        "titre": "Effets spéciaux : tableau fonctionnel",
        "etapes": [
            "Onglet Effets spéciaux : modifie une entrée, enregistre, vérifie le YAML complet.",
        ],
        "attendu": "La modification est écrite correctement.",
    },
    {
        "id": "YAML-014", "cat": "YAML", "rev": 3,
        "titre": "YAML complet : dernier onglet partage le document",
        "etapes": [
            "Modifie une valeur dans un onglet structuré (Ressources, POI...), SANS enregistrer.",
            "Ouvre l'onglet YAML complet de la même fenêtre.",
        ],
        "attendu": "Le YAML brut reflète la modification IMMÉDIATEMENT (aperçu rafraîchi à chaque édition structurée) : même document en mémoire, pas d'écart entre les vues.",
    },
    {
        "id": "YAML-015", "cat": "YAML", "rev": 3,
        "titre": "Playfield : Ctrl+Z de l'onglet + annotation unique",
        "pre": "Options > Annoter les modifications automatiquement activé.",
        "etapes": [
            "Modifie une valeur d'un onglet structuré, puis appuie sur Ctrl+Z (après un clic hors champ).",
            "Recommence : modifie puis enregistre (Ctrl+S) LA MÊME valeur 3 fois de suite.",
            "Ouvre le fichier brut (ECF-006) et cherche la ligne annotée.",
        ],
        "attendu": "Ctrl+Z restaure la valeur d'origine dans la vue structurée ET le YAML complet. Le commentaire d'annotation ne contient qu'UNE SEULE note « # original: ... » (correctif v1.6.1 : les notes s'accumulaient jusqu'à casser le YAML avec une fausse clé).",
    },
    {
        "id": "YAML-016", "cat": "YAML", "rev": 2,
        "titre": "Ressources : suppression d'une ressource",
        "etapes": [
            "Onglet Ressources : sélectionne une ligne de ressource et supprime-la (bouton Supprimer ou touche Suppr selon l'interface).",
            "Enregistre puis vérifie le YAML complet : la section Resources.",
        ],
        "attendu": "La ligne est retirée proprement de la section Resources (pas de virgule orpheline ni de ligne vide résiduelle).",
    },
    {
        "id": "YAML-017", "cat": "YAML", "rev": 2,
        "titre": "space*.yaml reconnu comme playfield",
        "etapes": [
            "Double-clique un fichier space*.yaml de la copie de travail (Playfields spatiaux).",
        ],
        "attendu": "Bascule vers l'éditeur structuré (8 onglets) comme pour un playfield*.yaml planétaire.",
    },
    {
        "id": "YAML-018", "cat": "YAML", "rev": 2,
        "titre": "YAML : round-trip après édition structurée",
        "etapes": [
            "Modifie une valeur via un onglet structuré, enregistre (Ctrl+S).",
            {
                "txt": "Lance la vérification de fidélité sur le fichier (remplace <fichier>) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-yaml \"<fichier>\"",
                    "python cli/verifier_parser_yaml.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Le vérificateur confirme la fidélité du YAML après l'édition structurée.",
    },
    # ---------------------------------------------------------------- MAP
    {
        "id": "MAP-001", "cat": "MAP", "rev": 3,
        "titre": "Carte 2D : affichage des entités positionnables",
        "etapes": [
            "Ouvre un playfield RE2 (ex : Akua), onglet Carte 2D.",
            "Repère : les POI fixes (points pleins), les points de départ joueur, et les POI aléatoires en CHAINE SpawnPOINear (cercle pointillé = rayon).",
        ],
        "attendu": "POI fixes, départs joueur ET POI aléatoires chaînés SpawnPOINear visibles (position approximative héritée de leur référence, cercle pointillé = rayon ; correctif v1.6.1 : seuls le 1er POI apparaissait, les chaînes NullPOI->R2AntennaStory->... n'étaient pas résolues). Un POI sans aucune référence connue reste « sans position » (jamais inventée).",
    },
    {
        "id": "MAP-002", "cat": "MAP", "rev": 3,
        "titre": "Glisser-déposer un POI fixe + écriture YAML",
        "etapes": [
            "Sur la Carte 2D, place le curseur SUR un point de POI fixe (le curseur change), maintiens le clic gauche et déplace le point ailleurs.",
            "Relâche : le point est à sa nouvelle place.",
            "Enregistre (Ctrl+S), puis vérifie dans l'onglet YAML complet la Position X/Z du POI déplacé.",
            "Note aussi : un SIMPLE clic sans déplacement ne marque PAS l'onglet comme modifié.",
        ],
        "attendu": "Les nouvelles coordonnées sont écrites dans la section du POI. (Correctif v1.6.1 : le glisser gauche PANAIT la carte au lieu de déplacer le point ; un simple clic ne marque plus l'onglet modifié.)",
    },
    {
        "id": "MAP-003", "cat": "MAP", "rev": 2,
        "titre": "Filtres par genre d'entité + zoom",
        "etapes": [
            "Sur la Carte 2D, coche/décoche successivement les filtres de genres (POI, créatures, ressources... selon la légende).",
            "Zoome avec la molette de la souris (pointeur sur la carte), dézoome, et déplace la vue.",
        ],
        "attendu": "Les filtres masquent/affichent les genres d'entités ; le zoom reste précis (pas de décalage entre le curseur et les points).",
    },
    {
        "id": "MAP-004", "cat": "MAP", "rev": 2,
        "titre": "Entités sans position : pas d'invention",
        "pre": "Un playfield avec ressources spatiales, ou des POI aléatoires sans aucune référence connue.",
        "etapes": [
            "Repère ces entrées sur la carte ou dans la légende (compteur « sans position »).",
            "Vérifie dans le YAML qu'aucune coordonnée n'a été ajoutée pour elles.",
        ],
        "attendu": "Elles n'ont volontairement PAS de position affichée (aucune coordonnée inventée). Un playfield SANS section POIs (certains space*.yaml) liste 0 POI dans l'inspecteur : normal, le fichier n'en contient pas.",
    },
    {
        "id": "MAP-005", "cat": "MAP", "rev": 2,
        "titre": "Inspecteur de POI : statistiques par POI",
        "pre": "Un playfield PLANÉTAIRE avec une section POIs (les spatiaux n'en ont pas forcément -- voir MAP-004).",
        "etapes": [
            "Ouvre l'onglet POI du playfield.",
            "Clique le bouton Inspecteur de POI... au-dessus du tableau.",
        ],
        "attendu": "Une fenêtre NON modale liste les POI aléatoires avec quantité et drones estimés.",
    },
    {
        "id": "MAP-006", "cat": "MAP", "rev": 2,
        "titre": "Inspecteur de POI : agrégation par faction + export",
        "etapes": [
            "Dans l'inspecteur (MAP-005), bascule la vue par faction (bouton/case de la fenêtre).",
            "Clique Exporter et choisis un emplacement pour le fichier texte.",
            "Ouvre le fichier exporté.",
        ],
        "attendu": "Le total de drones par faction est cohérent avec la vue ; l'export écrit un fichier texte complet et lisible.",
    },
    {
        "id": "MAP-007", "cat": "MAP", "rev": 3,
        "titre": "Carte de la galaxie : localisation auto + affichage",
        "etapes": [
            "Dans la barre de menus : Outils > Carte de la galaxie (Sectors.yaml)...",
            "Observe les systèmes affichés et leurs couleurs.",
        ],
        "attendu": "Les systèmes sont trouvés automatiquement et affichés ; violet pour les rôles spéciaux, orange pour les classes spectrales.",
    },
    {
        "id": "MAP-008", "cat": "MAP", "rev": 2,
        "titre": "Carte de la galaxie : curseur d'inclinaison Y",
        "etapes": [
            "Dans la carte de la galaxie, repère le curseur Inclinaison (axe Y).",
            "Augmente-le progressivement (glisse le curseur vers la droite) et observe la carte.",
        ],
        "attendu": "Les systèmes se décalent selon leur Y réel : ceux qui se chevauchaient se séparent visuellement.",
    },
    {
        "id": "MAP-009", "cat": "MAP", "rev": 3,
        "titre": "Carte de la galaxie : lecture seule / mode édition",
        "etapes": [
            "Ouvre la carte de la galaxie SANS cocher la case d'autorisation, puis essaie de déplacer un système (glisser).",
            "Coche « Autoriser le déplacement des systèmes », déplace un système, puis vérifie Sectors.yaml (YAML complet ou Bloc-notes).",
            "Annule via le bouton global d'annulation de la fenêtre principale et revérifie.",
        ],
        "attendu": "1er cas : lecture seule, aucune édition involontaire. 2e cas : la nouvelle position X/Z est écrite dans Sectors.yaml (Y conservé, inclinaison figée à 0), annulable via le bouton Annuler global (nouveau v1.6.1).",
    },

    # ---------------------------------------------------------------- CSV
    {
        "id": "CSV-001", "cat": "CSV", "rev": 2,
        "titre": "Ouverture CSV copie de travail : tableau éditable",
        "etapes": [
            "Dans la copie de travail, double-clique Extras/Localization.csv.",
            "Observe le tableau : colonnes fidèles au fichier, cellules modifiables (double-clic).",
        ],
        "attendu": "Le CSV s'ouvre en tableau éditable, avec les mêmes colonnes que le fichier (Key, English, French...).",
    },
    {
        "id": "CSV-002", "cat": "CSV", "rev": 3,
        "titre": "CSV Scénario A : lecture seule + copie de ligne",
        "etapes": [
            "Ouvre le MÊME Localization.csv depuis le panneau Scénario A : il est en lecture seule.",
            "Clic droit sur une ligne > copier vers la copie de travail : la ligne est copiée (ou fusionnée par clé).",
            "Recommence avec une ligne dont la clé existe DÉJÀ dans la copie de travail, toutes cellules remplies : une boîte EXPLIQUE que rien n'a changé.",
        ],
        "attendu": "1er cas : la ligne est copiée dans le CSV de la copie de travail (ou fusionnée par clé). 2e cas : boîte explicative (mode fusion = copie de travail prioritaire, cellules déjà remplies) au lieu de sembler ne rien faire.",
    },
    {
        "id": "CSV-003", "cat": "CSV", "rev": 2,
        "titre": "+ Ligne / suppression de ligne",
        "etapes": [
            "Clique + Ligne, remplis les cellules de la nouvelle ligne (au moins la clé).",
            "Sélectionne cette ligne puis supprime-la (bouton ou clic droit > Supprimer).",
            "Enregistre et vérifie le fichier (ECF-006 ou verifier-csv).",
        ],
        "attendu": "L'ajout et la suppression fonctionnent et s'enregistrent correctement.",
    },
    {
        "id": "CSV-004", "cat": "CSV", "rev": 2,
        "titre": "Presse-papiers multi-cellules",
        "etapes": [
            "Sélectionne plusieurs cellules (clic puis Maj+clic, ou glisser), Copier (Ctrl+C).",
            "Clique une cellule de destination et colle (Ctrl+V).",
            "Teste aussi Couper (Ctrl+X) et Effacer (touche Suppr).",
        ],
        "attendu": "Comportement tableur : la sélection multiple est respectée, le collage recopie le bloc de cellules.",
    },
    {
        "id": "CSV-005", "cat": "CSV", "rev": 2,
        "titre": "Recherche avec portée (colonne / toutes)",
        "etapes": [
            "Lance la recherche de l'onglet CSV, cherche un texte présent avec la portée « toutes les colonnes ».",
            "Relance la même recherche limitée à UNE colonne.",
            "Appuie plusieurs fois sur Entrée pour enchaîner les résultats.",
        ],
        "attendu": "Les résultats respectent la portée choisie ; Entrée passe au résultat suivant.",
    },
    {
        "id": "CSV-006", "cat": "CSV", "rev": 2,
        "titre": "Clic droit en-tête : recherche limitée à la colonne",
        "etapes": [
            "Clic droit sur un EN-TÊTE de colonne du tableau, lance une recherche depuis le menu.",
        ],
        "attendu": "La recherche est pré-limitée à cette colonne (portée déjà sélectionnée).",
    },
    {
        "id": "CSV-007", "cat": "CSV", "rev": 2,
        "titre": "Rechercher et remplacer avec revue",
        "etapes": [
            "Lance Rechercher et remplacer... et remplace un texte présent plusieurs fois.",
            "Dans la fenêtre de revue, examine les correspondances : décoche-en une, applique.",
        ],
        "attendu": "Chaque correspondance est listée et décochable : jamais de remplacement à l'aveugle.",
    },
    {
        "id": "CSV-008", "cat": "CSV", "rev": 2,
        "titre": "Remplacer : respect de la casse et mot entier",
        "etapes": [
            "Active « Respecter la casse » puis teste un remplacement sur un mot et son dérivé (ex : Dos / Dossier).",
            "Active « Mot entier » et refais le test : les dérivés ne doivent plus être touchés.",
        ],
        "attendu": "Les options filtrent correctement les correspondances (casse exacte, mot entier).",
    },
    {
        "id": "CSV-009", "cat": "CSV", "rev": 2,
        "titre": "Round-trip CSV fidèle (fins de ligne préservées)",
        "etapes": [
            "Fais une copie du CSV avant modification (Ctrl+C/Ctrl+V dans l'explorateur).",
            "Ouvre le CSV dans l'application et enregistre sans rien changer (Ctrl+S).",
            "Compare les deux fichiers : clic droit sur chacun > Propriétés (taille identique), ou commande verifier-csv ci-dessous.",
            {
                "txt": "Vérification par commande (remplace <fichier>) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-csv \"<fichier>\"",
                    "python cli/verifier_parser_csv.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Fichier identique après enregistrement (fins de ligne et structure préservés).",
    },
    {
        "id": "CSV-010", "cat": "CSV", "rev": 3,
        "titre": "Ctrl+Z onglet CSV",
        "etapes": [
            "Modifie une cellule (double-clic, change la valeur, Entrée).",
            "Clique dans le tableau (hors cellule en édition) puis appuie sur Ctrl+Z.",
        ],
        "attendu": "La valeur d'origine revient. (Correctif v1.6.1 : même cause qu'ECF-005, raccourci ambigu.)",
    },
    {
        "id": "CSV-011", "cat": "CSV", "rev": 2,
        "titre": "Cellules multilignes affichées correctement",
        "pre": "Un CSV avec des cellules contenant des retours à la ligne.",
        "etapes": [
            "Ouvre le fichier et repère les cellules multilignes.",
            "Édite une telle cellule (double-clic), valide sans casser les retours à la ligne, enregistre, vérifie le fichier.",
        ],
        "attendu": "Le contenu est fidèle ; l'édition ne casse pas la structure du fichier (pas de ligne CSV dédoublée).",
    },
    {
        "id": "CSV-012", "cat": "CSV", "rev": 2,
        "titre": "Enregistrement : BOM préservé si présent",
        "pre": "Un CSV commençant par un BOM (3 octets invisibles EF BB BF -- fréquent dans les CSV du jeu).",
        "etapes": [
            "Ouvre + enregistre le fichier sans modification (Ctrl+S).",
            {
                "txt": "Vérifie les 3 premiers octets : copie la commande ci-dessous dans une invite de commandes (remplace <fichier>) -- elle affiche les 3 premiers octets en hexadécimal.",
                "cmd": [
                    "powershell -Command \"$b=[System.IO.File]::ReadAllBytes('<fichier>')[0..2]; ($b | ForEach-Object { $_.ToString('X2') }) -join ' '\"",
                ],
            },
        ],
        "attendu": "Les 3 premiers octets sont toujours EF BB BF : le BOM d'origine est conservé.",
    },
    # ---------------------------------------------------------------- TRAD
    {
        "id": "TRAD-001", "cat": "TRAD", "rev": 2,
        "titre": "Mémoire de traduction : réutilisation instantanée",
        "etapes": [
            "Dans un onglet CSV, traduis une cellule (clic droit > Traduire vers > une langue, voir TRAD-002).",
            "Trouve une AUTRE cellule contenant EXACTEMENT le même texte (barre de recherche) et traduis-la.",
        ],
        "attendu": "La deuxième traduction est instantanée (aucun appel réseau) et identique à la première (elle vient de la mémoire).",
    },
    {
        "id": "TRAD-002", "cat": "TRAD", "rev": 2,
        "titre": "Clic droit > Traduire vers > langue : aperçu avant/après",
        "etapes": [
            "Clic droit sur une cellule > Traduire vers > choisis une langue dans le sous-menu.",
            "Observe la fenêtre d'aperçu (texte avant / texte proposé) et valide ou annule.",
        ],
        "attendu": "Un aperçu avant/après est proposé AVANT tout remplacement ; annuler ne change rien.",
    },
    {
        "id": "TRAD-003", "cat": "TRAD", "rev": 2,
        "titre": "Remplacement dans la colonne de la langue cible",
        "pre": "Le CSV a une colonne de la langue cible (ex : French).",
        "etapes": [
            "Choisis une ligne dont la cellule de la colonne CIBLE est vide.",
            "Traduis la cellule source (clic droit > Traduire vers > cette langue).",
            "Observe la ligne après validation.",
        ],
        "attendu": "La traduction va dans la colonne cible (la case vide est remplie) ; la cellule source reste intacte.",
    },
    {
        "id": "TRAD-004", "cat": "TRAD", "rev": 2,
        "titre": "Bouton Traduire rapide : langue par défaut",
        "pre": "Une langue par défaut configurée dans Options > Langue de traduction par défaut...",
        "etapes": [
            "Configure (ou vérifie) la langue par défaut dans Options.",
            "Clique le bouton Traduire de la barre d'outils de l'onglet CSV sur une cellule sélectionnée.",
        ],
        "attendu": "La traduction part directement vers la langue configurée, sans sous-menu de choix.",
    },
    {
        "id": "TRAD-005", "cat": "TRAD", "rev": 2,
        "titre": "Traduction en lot : progression + tableau de revue",
        "etapes": [
            "Sélectionne plusieurs cellules (glisser ou Maj+clic), clic droit > Traduire la sélection vers...",
            "Pendant le lot : observe la barre de progression, et déplace la fenêtre pour vérifier qu'elle reste réactive.",
            "À la fin, passe la revue (tableau des traductions proposées) et clique Appliquer.",
        ],
        "attendu": "Barre de progression SANS gel de l'interface ; revue avant application ; les échecs sont marqués en rouge et décochés.",
    },
    {
        "id": "TRAD-006", "cat": "TRAD", "rev": 2,
        "titre": "Revue : décocher une ligne / éditer le texte proposé",
        "etapes": [
            "Dans la revue d'un lot (TRAD-005), décoche UNE ligne.",
            "Double-clique le texte proposé d'une AUTRE ligne et corrige-le.",
            "Applique, puis vérifie les cellules dans le tableau.",
        ],
        "attendu": "Seules les lignes cochées sont appliquées, avec le texte corrigé pour celle que tu as éditée.",
    },
    {
        "id": "TRAD-007", "cat": "TRAD", "rev": 2,
        "titre": "Arrêt automatique après 5 échecs consécutifs",
        "pre": "Réseau coupé ou traduction en ligne indisponible (débranche le réseau ou coupe le Wi-Fi).",
        "etapes": [
            "Lance un GROS lot de traduction avec le réseau coupé.",
            "Observe la barre de progression et les messages.",
        ],
        "attendu": "Arrêt automatique après 5 échecs consécutifs, message clair ; les traductions déjà réussies restent en revue pour application.",
    },
    {
        "id": "TRAD-008", "cat": "TRAD", "rev": 2,
        "titre": "Combler les langues manquantes : vides seulement",
        "etapes": [
            "Clique le bouton Combler les langues manquantes... de l'onglet CSV.",
            "Choisis la langue source et la langue cible, lance.",
            "Passe la revue et applique.",
        ],
        "attendu": "Seules les cellules CIBLES VIDES sont traduites ; les cellules déjà remplies restent intactes.",
    },
    {
        "id": "TRAD-009", "cat": "TRAD", "rev": 2,
        "titre": "Protection BBCode et placeholders",
        "pre": "Une cellule avec balises [b]...[/b] et un placeholder {PlayerName} ou %s.",
        "etapes": [
            "Traduis cette cellule (TRAD-002) et observe le texte proposé dans l'aperçu.",
        ],
        "attendu": "Balises et placeholders restent EXACTEMENT identiques dans le résultat (même position, même orthographe).",
    },
    {
        "id": "TRAD-010", "cat": "TRAD", "rev": 2,
        "titre": "Lot en arrière-plan : interface restée fluide",
        "etapes": [
            "Lance un gros lot de traduction (TRAD-005).",
            "Pendant le lot : déplace la fenêtre, ouvre un menu, redimensionne la fenêtre, bascule vers une autre application et reviens.",
        ],
        "attendu": "L'interface réagit immédiatement à chaque action (pas de gel pendant les requêtes réseau).",
    },
    {
        "id": "TRAD-011", "cat": "TRAD", "rev": 2,
        "titre": "Annulation d'un lot en cours",
        "etapes": [
            "Lance un gros lot, puis clique Annuler dans la barre de progression.",
        ],
        "attendu": "Le lot s'arrête entre deux cellules ; les traductions déjà faites restent en revue.",
    },
    {
        "id": "TRAD-012", "cat": "TRAD", "rev": 2,
        "titre": "Réseau indisponible : erreur claire et bornée",
        "pre": "Réseau coupé (ou pare-feu bloquant l'application).",
        "etapes": [
            "Tente une traduction d'une cellule unique : chronomètre grossièrement l'attente.",
            "Tente ensuite un lot.",
        ],
        "attendu": "Erreur explicite en ~15 secondes maximum (pas de gel indéfini) ; le lot s'arrête proprement.",
    },
    {
        "id": "TRAD-013", "cat": "TRAD", "rev": 2,
        "titre": "Traduction en ligne désactivée : refus clair, mémoire OK",
        "etapes": [
            "Décoche Options > Traduction en ligne.",
            "Tente la traduction d'un texte NOUVEAU (jamais traduit) : message du PRIVACY.md.",
            "Tente ensuite un texte DÉJÀ traduit (présent en mémoire, TRAD-001).",
        ],
        "attendu": "Nouvelle traduction refusée avec le message de confidentialité ; le texte en mémoire reste utilisable (instantané).",
    },
    {
        "id": "TRAD-014", "cat": "TRAD", "rev": 2,
        "titre": "Mémoire persistée : survit au redémarrage",
        "etapes": [
            "Traduis un texte, puis ferme l'application.",
            "Relance, rouvre le CSV, retraduis le MÊME texte (nouvelle cellule avec le même contenu).",
        ],
        "attendu": "Traduction réutilisée depuis la mémoire (instantanée, sans réseau).",
    },
    {
        "id": "TRAD-015", "cat": "TRAD", "rev": 2,
        "titre": "ECF : traduction d'une propriété via menu contextuel",
        "etapes": [
            "Dans un onglet ECF, clic droit sur une valeur textuelle (ex : un Info: ou un Name affiché) > traduire.",
        ],
        "attendu": "Aperçu avant/après puis remplacement correct dans la propriété.",
    },
    {
        "id": "TRAD-016", "cat": "TRAD", "rev": 2,
        "titre": "Mémoire corrompue : récupération sans plantage",
        "pre": "Corrompt volontairement la mémoire : ferme l'application, ouvre le fichier ci-dessous (barre d'adresse de l'explorateur) et remplace tout son contenu par xxx.",
        "etapes": [
            {
                "txt": "Ouvre le dossier puis le fichier (avec le Bloc-notes) :",
                "cmd": ["%USERPROFILE%/.empyrion_editor"],
            },
            "Remplace tout le contenu du fichier translation_memory.json par xxx, enregistre.",
            "Relance l'application et traduis un texte.",
        ],
        "attendu": "Aucun plantage : la mémoire repart de zéro et se reconstruit (fichier réécrit atomiquement).",
    },

    # ---------------------------------------------------------------- FUS
    {
        "id": "FUS-001", "cat": "FUS", "rev": 2,
        "titre": "Dupliquer un bloc depuis le Scénario A",
        "etapes": [
            "Dans le panneau Scénario A, ouvre BlocksConfig.ecf (il s'ouvre en lecture seule).",
            "Clic droit sur un bloc > Dupliquer avec un nouvel Id...",
            "Dans la fenêtre, observe les Id proposés et choisis-en un.",
            "Valide, puis cherche le bloc dupliqué dans la copie de travail (même fichier).",
        ],
        "attendu": "Le bloc apparaît dans la copie de travail, identique au bloc source sauf l'Id.",
    },
    {
        "id": "FUS-002", "cat": "FUS", "rev": 2,
        "titre": "Duplication : suggestions d'Ids libres",
        "etapes": [
            "Ouvre la fenêtre de duplication (FUS-001) et observe la liste déroulante des Id proposés.",
            "Compare chaque Id proposé avec les Id existants (recherche dans le fichier).",
        ],
        "attendu": "Les Id proposés sont libres (aucun conflit existant) et sous la limite du jeu (8192).",
    },
    {
        "id": "FUS-003", "cat": "FUS", "rev": 2,
        "titre": "Duplication multi-variantes (ChildBlocks)",
        "pre": "Un bloc avec plusieurs variantes ChildBlocks (sous-blocs dans l'arbre).",
        "etapes": [
            "Clic droit sur le bloc parent dans A > Dupliquer : la fenêtre de duplication des variantes s'ouvre.",
            "Suis la fenêtre dédiée (choix des variantes à dupliquer, nouveaux Ids).",
            "Compare dans la copie de travail le bloc dupliqué et ses variantes avec l'original.",
        ],
        "attendu": "Les variantes sont dupliquées avec une numérotation cohérente (Name_0, Name_1... réalignés).",
    },
    {
        "id": "FUS-004", "cat": "FUS", "rev": 2,
        "titre": "Variantes : Templates associés proposés",
        "pre": "Le bloc source a un Template dans Templates.ecf.",
        "etapes": [
            "Duplique les variantes (FUS-003) et accepte la création des Templates associés.",
            "Ouvre Templates.ecf de la copie de travail et cherche les Templates créés.",
        ],
        "attendu": "Un Template par variante est créé, avec le Name de chaque variante.",
    },
    {
        "id": "FUS-005", "cat": "FUS", "rev": 2,
        "titre": "Ajustement des Templates créés (éditeur dédié)",
        "etapes": [
            "Dans la fenêtre d'ajustement des Templates (après duplication), modifie le temps de fabrication et les quantités d'ingrédients.",
            "Valide, puis regarde l'onglet Templates.ecf (marqué modifié, pas encore écrit).",
            "Enregistre l'onglet (Ctrl+S) et vérifie le disque (ECF-006).",
            "Teste aussi Annuler : Ctrl+Z une fois = une étape (pas tout le lot d'un coup).",
        ],
        "attendu": "Les valeurs ajustées sont dans l'onglet Templates.ecf ; le DISQUE ne change qu'à l'enregistrement (modèle de l'appli : édition en mémoire dans les onglets). Ctrl+Z annule UNE modification à la fois -- comportement voulu, documenté.",
    },
    {
        "id": "FUS-006", "cat": "FUS", "rev": 2,
        "titre": "Nom affiché (Localization.csv) : proposition après duplication",
        "etapes": [
            "Duplique un bloc/item (FUS-001).",
            "Accepte la proposition d'ajuster le nom affiché, renseigne le FR et l'EN, valide.",
            "Ouvre Extras/Localization.csv de la copie de travail et cherche les clés ajoutées.",
        ],
        "attendu": "Les noms FR/EN sont ajoutés dans Extras/Localization.csv (ou le CSV du scénario), avec les clés correctes.",
    },
    {
        "id": "FUS-007", "cat": "FUS", "rev": 2,
        "titre": "Nom affiché : pré-remplissage source / repli vanilla",
        "etapes": [
            "Duplique un bloc depuis le Scénario A dont le Name a une entrée dans le Localization.csv du scénario : observe le pré-remplissage FR/EN proposé.",
            "Duplique un bloc SANS entrée dans le scénario (bloc vanilla) : observe le repli depuis le pack de localisation intégré.",
        ],
        "attendu": "Les champs FR/EN sont pré-remplis avec le nom source (scénario d'abord, vanille sinon) dans la fenêtre de localisation proposée après la duplication.",
    },
    {
        "id": "FUS-008", "cat": "FUS", "rev": 3,
        "titre": "Dupliquer une ligne CSV depuis le Scénario A (clé suggérée)",
        "etapes": [
            "Dans le CSV ouvert depuis le panneau A, clic droit sur une ligne > dupliquer vers la copie de travail.",
            "Observe le champ de nouvelle clé : il est PRÉ-REMPLI avec une suggestion libre (base_2, base_3...).",
            "Modifie-la si tu veux, valide, vérifie le CSV de la copie de travail.",
        ],
        "attendu": "Le champ de nouvelle clé est PRÉ-REMPLI avec une suggestion libre et modifiable (correctif v1.6.1 : champ vide avant).",
    },
    {
        "id": "FUS-009", "cat": "FUS", "rev": 3,
        "titre": "Dupliquer une entrée YAML (valeur suggérée)",
        "etapes": [
            "Dans un YAML ouvert depuis le panneau A, clic droit sur une entrée > dupliquer.",
            "Observe le champ de nouvelle valeur : PRÉ-REMPLI avec une suggestion libre.",
            "Valide et vérifie le YAML de la copie de travail.",
        ],
        "attendu": "Le champ de nouvelle valeur est PRÉ-REMPLI avec une suggestion libre, modifiable (correctif v1.6.1 : champ vide avant).",
    },
    {
        "id": "FUS-010", "cat": "FUS", "rev": 3,
        "titre": "Fusion ECF (option activée) : priorité copie de travail + aperçu",
        "pre": "Options > Autoriser la fusion activée.",
        "etapes": [
            "Fusionne un fichier ECF de A déjà présent (modifié) dans la copie de travail (clic droit dans A > fusionner).",
            "Dans l'aperçu, observe les lignes « différente » : par défaut elles sont DÉCOCHÉES.",
            "Coche la ligne d'une propriété DIFFÉRENTE (pour prendre la valeur source), puis valide.",
        ],
        "attendu": "Par défaut les valeurs de la copie de travail sont CONSERVÉES (lignes « différentes » décochées) ; seuls les ajouts arrivent de A. Cocher une ligne « différente » prend la valeur source (choix explicite, éditable). La validation ouvre l'onglet positionné sur le bloc fusionné.",
    },
    {
        "id": "FUS-011", "cat": "FUS", "rev": 2,
        "titre": "Fusion : garde-fou anti-collision d'Id",
        "pre": "Dans le Scénario A, repère (ou crée) un bloc dont l'Id existe déjà dans la copie de travail mais avec un Name DIFFÉRENT.",
        "etapes": [
            "Clic droit sur ce bloc dans A > fusionner/copier vers la copie de travail.",
            "Ouvre le fichier de la copie de travail : le bloc entrant est ajouté DÉSACTIVÉ (commenté) en fin de fichier.",
            "Menu Vérification > Blocs en attente (conflits d'Id)... : le bloc apparaît dans la liste.",
        ],
        "attendu": "Le bloc entrant n'a PAS écrasé l'existant : ajouté DÉSACTIVÉ (commenté) en fin de fichier, listé dans Blocs en attente.",
    },
    {
        "id": "FUS-012", "cat": "FUS", "rev": 2,
        "titre": "Fusion CSV : complétion des cellules vides uniquement",
        "etapes": [
            "Fusionne un CSV de A dans la copie de travail (clic droit dans A > copier/fusionner vers la copie).",
            "Compare cellule par cellule une ligne modifiable.",
        ],
        "attendu": "Les cellules vides de la copie sont complétées depuis A ; les cellules remplies restent inchangées.",
    },
    {
        "id": "FUS-013", "cat": "FUS", "rev": 2,
        "titre": "Bouton global Annuler la dernière action",
        "pre": "Une fusion/duplication/copie depuis A/B vient d'être faite (FUS-001 par exemple).",
        "etapes": [
            "Repère le bouton global d'annulation (barre d'outils de la fenêtre principale).",
            "Clique-le et observe les fichiers concernés.",
        ],
        "attendu": "L'opération est annulée (fichiers restaurés sur le disque) ; les onglets concernés sont fermés ou rafraîchis.",
    },
    {
        "id": "FUS-014", "cat": "FUS", "rev": 3,
        "titre": "Template sans source : TOUTES les propriétés des autres Templates",
        "pre": "Templates.ecf contient au moins un Template avec une propriété peu commune (ex : OutputCount).",
        "etapes": [
            "Duplique un bloc SANS Template, accepte la proposition de créer la recette.",
            "Observe la liste des propriétés proposées dans la fenêtre d'ajustement.",
            "Compare avec les propriétés réellement présentes dans Templates.ecf.",
        ],
        "attendu": "La liste contient TOUTES les propriétés observées sur les autres Templates du fichier (pas seulement CraftTime/Target), chacune avec sa valeur la plus courante.",
    },
    {
        "id": "FUS-015", "cat": "FUS", "rev": 3,
        "titre": "Template sans source : ajout de propriété par liste déroulante",
        "pre": "Fenêtre d'ajustement du Template ouverte (bloc sans Template source).",
        "etapes": [
            "Ouvre la liste déroulante des noms de propriétés, choisis-en une.",
            "Ouvre la liste déroulante de valeurs associée, choisis-en une, valide.",
        ],
        "attendu": "L'ajout de propriété passe par le même formulaire à LISTES DÉROULANTES que le reste de l'application (corrigé v1.6.1 : c'était un dialogue sans liste).",
    },
    {
        "id": "FUS-016", "cat": "FUS", "rev": 2,
        "titre": "Template sans source : suppression de propriétés pré-remplies",
        "pre": "Fenêtre d'ajustement ouverte avec plusieurs propriétés pré-remplies.",
        "etapes": [
            "Sélectionne une propriété dans la liste, clique « Retirer la propriété », valide la création.",
            "Vérifie Templates.ecf après création (onglet + disque après Ctrl+S).",
        ],
        "attendu": "La propriété retirée N'APPARAÎT PAS sur le Template créé ; les autres sont conservées.",
    },
    {
        "id": "FUS-017", "cat": "FUS", "rev": 2,
        "titre": "Template : listes déroulantes des valeurs et quantités courantes",
        "pre": "Templates.ecf contient plusieurs Templates avec des valeurs/quantités variées.",
        "etapes": [
            "Dans la fenêtre d'ajustement, ouvre la liste de valeur d'une propriété existante.",
            "Ouvre la liste de quantité à côté de l'ajout d'ingrédient.",
        ],
        "attendu": "Les deux listes proposent les valeurs/quantités réellement observées dans le fichier, triées par fréquence, avec saisie libre toujours possible.",
    },
    # ---------------------------------------------------------------- VERIF
    {
        "id": "VERIF-001", "cat": "VERIF", "rev": 3,
        "titre": "Vérifier les références (Ref:) : détection",
        "pre": "Un bloc avec Ref: pointant vers un nom absent (ex : Ref: NomQuiNexistePas), ENREGISTRÉ (Ctrl+S).",
        "etapes": [
            "Enregistre le fichier modifié : l'analyse lit le disque -- une invite propose désormais d'enregistrer les onglets modifiés avant l'analyse (correctif v1.6.1 : une édition non enregistrée était invisible).",
            "Dans la barre de menus : Vérification > Vérifier les références (Ref) de la copie de travail...",
            "Lis les résultats (fichier + bloc indiqués).",
        ],
        "attendu": "La référence orpheline est signalée avec le fichier et le bloc. Supprimer la VALEUR de Ref n'est PAS une référence cassée : aucune détection dans ce cas, c'est normal.",
    },
    {
        "id": "VERIF-002", "cat": "VERIF", "rev": 2,
        "titre": "Références : double-clic ouvre le fichier au bloc",
        "etapes": [
            "Dans la fenêtre de résultats de Vérifier les références (VERIF-001), double-clique un résultat.",
        ],
        "attendu": "Le fichier s'ouvre dans un onglet, positionné sur le bloc en cause.",
    },
    {
        "id": "VERIF-003", "cat": "VERIF", "rev": 2,
        "titre": "Références : Actualiser + Exporter",
        "etapes": [
            "Corrige un problème signalé (sans fermer la fenêtre de résultats), clique Actualiser.",
            "Clique ensuite Exporter, choisis un emplacement, ouvre le rapport exporté.",
        ],
        "attendu": "Les résultats se rafraîchissent (le problème corrigé disparaît) ; l'export écrit le rapport complet en texte.",
    },
    {
        "id": "VERIF-004", "cat": "VERIF", "rev": 3,
        "titre": "Références croisées : items/blocs référencés",
        "pre": "La convention vérifiée : des clés Name_N (ex : Name_1:) dont la VALEUR est un nom d'item/bloc. Test simple : dans un bloc, ajoute « Name_1: ItemQuiNexistePas », enregistre (Ctrl+S).",
        "etapes": [
            "Vérification > Vérifier les références croisées (entre fichiers)...",
            "Active le contrôle items/blocs (case), lance.",
            "Observe le résultat pour ItemQuiNexistePas.",
        ],
        "attendu": "ItemQuiNexistePas est signalé ; une valeur existante (ex : Name_1: SomeItem avec SomeItem dans ItemsConfig/BlocksConfig) ne l'est pas.",
    },
    {
        "id": "VERIF-005", "cat": "VERIF", "rev": 2,
        "titre": "Références croisées : jetons Token:XXXX",
        "etapes": [
            "Vérification > Vérifier les références croisées..., active le contrôle jetons, lance.",
            "Lis les jetons signalés et vérifie-en un dans TokenConfig.ecf.",
        ],
        "attendu": "Les jetons RÉFÉRENCÉS mais INEXISTANTS dans TokenConfig.ecf sont signalés (erreur réelle). Les jetons « non utilisés » sont INDICATIFS : un jeton consommé directement par le jeu (hors fichiers du scénario) apparaîtra -- outil de tri, pas liste d'erreurs.",
    },
    {
        "id": "VERIF-006", "cat": "VERIF", "rev": 3,
        "titre": "Références croisées : dialogues Next/OptionNext + CORRECTION proposée",
        "pre": "Une référence Next_N/OptionNext_N pointant un dialogue inexistant (faute de frappe ou dialogue supprimé).",
        "etapes": [
            "Vérification > Vérifier les références croisées..., active le contrôle dialogues, lance.",
            "Double-clique un résultat cassé : une fenêtre EXPLIQUE le problème et propose : remplacer par le nom le plus proche (suggéré, éditable via la liste des dialogues existants), ou supprimer la référence.",
            "Applique une correction, relance la vérification.",
            "Teste aussi le bouton « Voir dans le fichier » : il navigue vers l'emplacement sans corriger.",
        ],
        "attendu": "La correction est écrite sur disque (annulable via le bouton Annuler global), l'onglet ouvert est rechargé, et la relance ne montre plus l'erreur.",
    },
    {
        "id": "VERIF-007", "cat": "VERIF", "rev": 2,
        "titre": "Règles métier : limite d'Id 8192",
        "etapes": [
            "Crée (ou modifie) un bloc avec un Id SUPÉRIEUR à 8192 dans la copie de travail, enregistre (Ctrl+S).",
            "Dans la barre de menus : Vérification > Bilan de santé du scénario... (règles métier).",
            "Observe le résultat pour ce bloc.",
        ],
        "attendu": "Le dépassement de la limite d'Id est signalé.",
    },
    {
        "id": "VERIF-008", "cat": "VERIF", "rev": 2,
        "titre": "Règles métier : conteneurs sans VolumeCapacity",
        "etapes": [
            "Sur un conteneur qui exige VolumeCapacity, supprime cette propriété (clic droit > Supprimer), enregistre.",
            "Lance le Bilan de santé (Vérification > Bilan de santé du scénario...).",
        ],
        "attendu": "L'incohérence (conteneur sans VolumeCapacity) est signalée.",
    },
    {
        "id": "VERIF-009", "cat": "VERIF", "rev": 3,
        "titre": "Règles métier : matériaux et HoldType inconnus",
        "pre": "Material: pneu dans BlocksConfig.ecf ET HoldType: 99 dans ItemsConfig.ecf (portée VOLONTAIRE : chaque règle n'est fiable que dans son fichier confirmé -- Material ailleurs désigne d'autres concepts). Enregistre les deux fichiers.",
        "etapes": [
            "Lance la validation (Vérification > Bilan de santé du scénario...). Une invite d'enregistrement des onglets modifiés est proposée (v1.6.1).",
        ],
        "attendu": "Les deux valeurs non reconnues sont signalées en avertissement (elles peuvent être légitimes dans un scénario personnalisé).",
    },
    {
        "id": "VERIF-010", "cat": "VERIF", "rev": 3,
        "titre": "Règles métier : virgules non protégées",
        "etapes": [
            "Écris une valeur de liste SANS guillemets dans n'importe quelle propriété (ex : SizeBlocks: 4,7 ou TechTreeNames: Base,Capital Vessel), enregistre, lance la validation.",
            "Vérifie que la détection fonctionne sur PLUSIEURS clés différentes (pas seulement deux).",
        ],
        "attendu": "Chaque virgule non protégée est signalée. (Correctif v1.6.1 : la règle détecte désormais TOUTE valeur coupée en deux par une virgule, quelle que soit la clé.)",
    },
    {
        "id": "VERIF-011", "cat": "VERIF", "rev": 2,
        "titre": "Règles métier : format BlockColor",
        "etapes": [
            "Mets BlockColor: 170,170,170 SANS guillemets sur un bloc, enregistre, lance la validation.",
        ],
        "attendu": "Le format incorrect (valeurs non protégées par guillemets) est signalé.",
    },
    {
        "id": "VERIF-012", "cat": "VERIF", "rev": 2,
        "titre": "Règles métier : doublons Id/Name",
        "etapes": [
            "Crée volontairement deux blocs avec le MÊME Id dans DEUX fichiers différents du scénario, enregistre, lance la validation.",
        ],
        "attendu": "Le doublon est signalé avec les fichiers concernés.",
    },
    {
        "id": "VERIF-013", "cat": "VERIF", "rev": 2,
        "titre": "Blocs en attente : liste + comparaison détaillée",
        "pre": "Un bloc en attente existe (fais d'abord FUS-011 : fusion d'un bloc dont l'Id existe déjà avec un Name différent).",
        "etapes": [
            "Menu Vérification > Blocs en attente (conflits d'Id)...",
            "Sélectionne le bloc en attente dans la liste.",
        ],
        "attendu": "Les deux versions (bloc actif actuel vs bloc désactivé en attente) sont comparées côte à côte clairement.",
    },
    {
        "id": "VERIF-014", "cat": "VERIF", "rev": 2,
        "titre": "Blocs en attente : activation avec nouvel Id",
        "pre": "Un bloc en attente existe (voir VERIF-013).",
        "etapes": [
            "Menu Vérification > Blocs en attente..., sélectionne-le.",
            "Choisis l'activation avec un Id libre PARMI LES SUGGESTIONS affichées.",
            "Confirme, puis regarde le fichier dans l'onglet qui s'ouvre.",
        ],
        "attendu": "Le bloc est décommenté avec le nouvel Id ; l'onglet ouvert est rechargé automatiquement.",
    },
    {
        "id": "VERIF-015", "cat": "VERIF", "rev": 3,
        "titre": "Centre de vérification : tout vérifier d'un coup",
        "etapes": [
            "Vérification > Centre de vérification (ou touche F5).",
            "Clique le bouton Tout vérifier.",
            "Observe les compteurs, puis clique un bouton de détail.",
        ],
        "attendu": "Les 5 familles sont relancées avec compteurs ; chaque bouton de détail ouvre la fenêtre de vérification correspondante ; le résumé compte les vrais problèmes (orphelins informatifs exclus).",
    },

    # ---------------------------------------------------------------- SAUV
    {
        "id": "SAUV-001", "cat": "SAUV", "rev": 2,
        "titre": "Sauvegarder un scénario (avant mise à jour)",
        "etapes": [
            "Fichier > Sauvegarder un scénario (avant mise à jour)...",
            "Choisis le scénario A comme source, un dossier de destination, lance.",
            "Ouvre ensuite le gestionnaire de sauvegardes (même menu, fenêtre qui liste) et observe.",
        ],
        "attendu": "Une sauvegarde datée apparaît dans le gestionnaire.",
    },
    {
        "id": "SAUV-002", "cat": "SAUV", "rev": 3,
        "titre": "Gérer mes sauvegardes de partie : liste (dossier pré-rempli)",
        "etapes": [
            "Fichier > Gérer mes sauvegardes de partie...",
            "Observe le champ source : pré-rempli avec le dossier des parties du jeu s'il existe (Documents/Empyrion - Game Saves, modifiable).",
            "Refais l'opération après avoir changé le dossier : il est mémorisé par type.",
        ],
        "attendu": "La fenêtre liste les sauvegardes faites PAR L'APPLICATION ; le champ source est PRÉ-REMPLI avec le dossier des parties du jeu s'il existe ; les dossiers de stockage sont mémorisés par type (correctif v1.6.1).",
    },
    {
        "id": "SAUV-003", "cat": "SAUV", "rev": 2,
        "titre": "Restaurer une sauvegarde + safety backup auto",
        "etapes": [
            "Dans le gestionnaire (SAUV-002), sélectionne une sauvegarde et clique Restaurer.",
            "Après restauration, cherche dans le dossier de stockage un backup de sécurité créé AVANT la restauration (il porte une mention safety/avant-restauration).",
        ],
        "attendu": "La restauration s'applique ; l'état d'avant est conservable (safety backup automatique).",
    },
    {
        "id": "SAUV-004", "cat": "SAUV", "rev": 2,
        "titre": "Supprimer une sauvegarde (confirmation)",
        "etapes": [
            "Dans le gestionnaire, sélectionne une sauvegarde de test et clique Supprimer.",
            "Confirme dans la boîte de confirmation.",
        ],
        "attendu": "Confirmation demandée ; suppression effective après confirmation.",
    },
    {
        "id": "SAUV-005", "cat": "SAUV", "rev": 2,
        "titre": "Ouvrir le dossier des sauvegardes",
        "etapes": [
            "Dans le gestionnaire, clique Ouvrir le dossier.",
        ],
        "attendu": "L'explorateur Windows s'ouvre au bon dossier (celui des sauvegardes).",
    },
    {
        "id": "SAUV-006", "cat": "SAUV", "rev": 2,
        "titre": "Comparer avec... une sauvegarde",
        "etapes": [
            "Sur une sauvegarde de SCÉNARIO dans le gestionnaire, clique Comparer avec...",
        ],
        "attendu": "L'outil de comparaison s'ouvre pré-rempli avec cette sauvegarde (côté référence ou modifié, selon le sens).",
    },
    {
        "id": "SAUV-007", "cat": "SAUV", "rev": 3,
        "titre": "Autosave : instantané pendant une édition non enregistrée",
        "etapes": [
            "Modifie un fichier SANS enregistrer, attends l'intervalle d'autosave (quelques dizaines de secondes).",
            {
                "txt": "Ouvre le dossier de récupération du projet : colle le chemin ci-dessous dans la barre d'adresse de l'explorateur (remplace <nom-du-projet>) -- dossier caché : active Affichage > Éléments cachés si besoin.",
                "cmd": ["%USERPROFILE%/.empyrion_editor/recovery/<nom-du-projet>/"],
            },
        ],
        "attendu": "Un fichier instantané y existe, contenant la version NON enregistrée (correctif protocole v1.6.1 : chemin exact indiqué -- l'ancien pas-à-pas disait juste ~/.empyrion_editor et l'utilisateur ne trouvait rien).",
    },
    {
        "id": "SAUV-008", "cat": "SAUV", "rev": 3,
        "titre": "Récupération au démarrage après plantage",
        "pre": "Un instantané de récupération existe (SAUV-007). Ferme l'application via le gestionnaire des tâches (Ctrl+Maj+Échap > clic droit sur l'application > Fin de tâche : kill brutal, PAS une fermeture propre).",
        "etapes": [
            "Relance l'application.",
            "Rouvre le MÊME projet (Projets récents).",
        ],
        "attendu": "Le dialogue de récupération propose de restaurer le contenu jamais enregistré (l'instantané de SAUV-007).",
    },
    {
        "id": "SAUV-009", "cat": "SAUV", "rev": 3,
        "titre": "Nettoyage de l'instantané après enregistrement",
        "etapes": [
            "Enregistre le fichier qui avait un instantané (Ctrl+S).",
            "Ré-ouvre le dossier de récupération (chemin de SAUV-007).",
        ],
        "attendu": "L'instantané de CE fichier a disparu (le dossier peut rester, vide ou avec d'autres fichiers).",
    },
    {
        "id": "SAUV-010", "cat": "SAUV", "rev": 2,
        "titre": "Undo global : restauration fichier",
        "etapes": [
            "Fais une duplication (FUS-001), puis annule-la via le bouton global Annuler.",
            "Vérifie le fichier de la copie de travail (onglet ou Bloc-notes).",
        ],
        "attendu": "Le fichier retrouve son état d'avant l'opération (le bloc dupliqué n'y est plus).",
    },
    {
        "id": "SAUV-011", "cat": "SAUV", "rev": 3,
        "titre": "Écriture atomique : crash pendant enregistrement",
        "pre": "Test volontairement destructif : sur une COPIE de test uniquement (jamais sur ton vrai projet).",
        "etapes": [
            "Lance une sauvegarde de scénario (gros dossier) et tue le processus pendant la copie : Ctrl+Maj+Échap > gestionnaire des tâches > clic droit sur l'application > Fin de tâche.",
            "Relance l'application, ouvre la liste des sauvegardes (Fichier > Sauvegarder / gestionnaire).",
        ],
        "attendu": "La sauvegarde n'apparaît PAS dans la liste tant qu'elle est incomplète (dossier tampon *.inprogress, invisible et nettoyé à la tentative suivante -- correctif v1.6.1 : le dossier tronqué restait en place). Une restauration copie aussi dans un tampon AVANT de toucher à la destination : un crash pendant la restauration laisse l'ancien contenu intact.",
    },
    {
        "id": "SAUV-012", "cat": "SAUV", "rev": 2,
        "titre": "Réparer les permissions de la copie de travail",
        "etapes": [
            "Dans l'explorateur : clic droit sur le dossier de la copie de travail > Propriétés > onglet Sécurité... ou plus simple : coche Lecture seule (attribut Windows) sur le dossier et applique.",
            "Dans l'application : Fichier > Réparer les permissions de la copie de travail.",
            "Vérifie dans l'explorateur que l'attribut est parti.",
        ],
        "attendu": "Les fichiers redeviennent modifiables/supprimables (attribut lecture seule retiré).",
    },
    # ---------------------------------------------------------------- COMP
    {
        "id": "COMP-001", "cat": "COMP", "rev": 2,
        "titre": "Comparer deux scénarios : arbre coloré",
        "etapes": [
            "Fichier > Comparer deux scénarios...",
            "Dans la fenêtre, choisis le Scénario A (référence) d'un côté et un second scénario (modifié) de l'autre (boutons Parcourir « ... »).",
            "Clique Compare et observe l'arbre de résultats.",
        ],
        "attendu": "Arbre coloré : ajouté (vert) / retiré (rouge) / modifié (orange) / identique (gris).",
    },
    {
        "id": "COMP-002", "cat": "COMP", "rev": 3,
        "titre": "Comparaison : détail par type de fichier (+ contenu ajouté/supprimé)",
        "etapes": [
            "Dans l'arbre de comparaison (COMP-001), clique un ECF modifié : le détail est bloc par bloc.",
            "Clique un CSV modifié : détail ligne à ligne ; un YAML modifié : clé par clé.",
            "Clique un fichier AJOUTÉ (vert) puis un SUPPRIMÉ (rouge).",
        ],
        "attendu": "Détail précis pour ECF/CSV/YAML modifiés ; un fichier AJOUTÉ ou SUPPRIMÉ affiche un APERÇU de son contenu (tronqué) au lieu d'un message vide (correctif v1.6.1).",
    },
    {
        "id": "COMP-003", "cat": "COMP", "rev": 2,
        "titre": "Afficher aussi les fichiers identiques",
        "etapes": [
            "Dans la fenêtre de comparaison, coche « Afficher aussi les fichiers identiques ».",
        ],
        "attendu": "La liste complète apparaît, pas seulement les différences.",
    },
    {
        "id": "COMP-004", "cat": "COMP", "rev": 2,
        "titre": "Comparer : exporter le rapport",
        "etapes": [
            "Dans la fenêtre de comparaison, clique Exporter le rapport, choisis un emplacement.",
            "Ouvre le fichier texte produit.",
        ],
        "attendu": "Fichier texte complet écrit (atomiquement), lisible, reprenant l'arbre des différences.",
    },
    {
        "id": "COMP-005", "cat": "COMP", "rev": 3,
        "titre": "Recherche dans tout le scénario",
        "etapes": [
            "Outils > Rechercher dans le scénario... (ou Ctrl+Maj+F, ou la barre d'outils).",
            "Tape un texte connu (ex : le Name d'un bloc), lance la recherche.",
            "Observe les résultats : parcours A / copie / B, avec fichiers et localisation.",
        ],
        "attendu": "Les résultats couvrent les trois panneaux (A, copie de travail, B) avec fichier et position du texte trouvé.",
    },
    {
        "id": "COMP-006", "cat": "COMP", "rev": 2,
        "titre": "Recherche scénario : ouverture du résultat",
        "etapes": [
            "Double-clique un résultat de la recherche (COMP-005).",
        ],
        "attendu": "Le fichier s'ouvre dans un onglet, à l'endroit trouvé.",
    },
    {
        "id": "COMP-007", "cat": "COMP", "rev": 3,
        "titre": "Mission PDA (ancien module) : création guidée",
        "etapes": [
            "Outils > Nouvelle mission PDA... (ou Ctrl+M), suis l'assistant jusqu'à la création (étapes et bouton Suivant).",
        ],
        "attendu": "Les fichiers PDA sont créés dans le scénario, structure valide (vérifiable en ouvrant PDA.yaml/PDA.csv).",
    },
    {
        "id": "COMP-008", "cat": "COMP", "rev": 2,
        "titre": "Mission PDA (ancien module) : édition d'une mission existante",
        "etapes": [
            "Ouvre une mission PDA existante (via l'ancien module PDA), modifie un texte ou l'humeur, enregistre.",
        ],
        "attendu": "Modification écrite fidèlement ; la mission reste chargeable en jeu.",
    },
    {
        "id": "COMP-009", "cat": "COMP", "rev": 3,
        "titre": "Extraction des propriétés du scénario",
        "etapes": [
            "Fichier > Extraire les propriétés du scénario...",
            "Lance l'extraction et ouvre le CSV produit.",
        ],
        "attendu": "CSV généré : propriétés, occurrences, exemples ; clés numérotées regroupées (Name_N).",
    },
    {
        "id": "COMP-010", "cat": "COMP", "rev": 2,
        "titre": "Recherche : mode expression régulière",
        "etapes": [
            "Outils > Rechercher dans le scénario...",
            "Coche Expression régulière, cherche un motif (ex : Robo.*Dog).",
            "Saisis ensuite un motif INVALIDE (ex : Robo([unclosed) et relance.",
        ],
        "attendu": "Les motifs regex fonctionnent sur ECF/YAML/CSV ; un motif invalide affiche un message d'erreur et CONSERVE les résultats de la recherche précédente (liste jamais vidée).",
    },

    # ---------------------------------------------------------------- TECH
    {
        "id": "TECH-001", "cat": "TECH", "rev": 4,
        "titre": "Arbre technologique : catégories, tuiles vertes, mise en page adaptative",
        "etapes": [
            "Outils > Arbre technologique... (ou Ctrl+T, ou la barre d'outils).",
            "Compare avec l'écran F3 du jeu (mêmes catégories, même ordre).",
            "Observe les tuiles sous les icônes (vertes, effet brillant).",
        ],
        "attendu": "Catégories dans l'ordre du jeu (Base, CV, SV, HV, Misc, Tools, Weapons), Hidden jamais affiché. Chaque icône posée sur une tuile verte style « bouton » (cadre en dégradé, reflet brillant).",
    },
    {
        "id": "TECH-002", "cat": "TECH", "rev": 2,
        "titre": "Icônes : scénario > pack intégré > générique",
        "etapes": [
            "SANS dossier itemicons local : ouvre l'arbre technologique et vérifie que les icônes viennent du pack intégré.",
            "Avec SharedData/ItemIcons dans le scénario : vérifie qu'une icône personnalisée l'emporte (place une icône PNG de test portant le nom d'un item).",
        ],
        "attendu": "Priorité respectée (scénario puis pack intégré) ; à défaut, icône générique (jamais de case vide ni plantage).",
    },
    {
        "id": "TECH-003", "cat": "TECH", "rev": 2,
        "titre": "Curseur de niveau joueur simulé (FONCTION SUPPRIMÉE)",
        "etapes": ["Fonction retirée à la demande de l'utilisateur (retour protocole v1.6.0). À passer en N/A."],
        "attendu": "N/A -- la fonction n'existe plus ; le cas est conservé pour la continuité de numérotation.",
    },
    {
        "id": "TECH-004", "cat": "TECH", "rev": 2,
        "titre": "Infobulle d'un nœud",
        "etapes": [
            "Dans l'arbre technologique, laisse la souris immobile sur un nœud (sans cliquer) ~2 secondes.",
        ],
        "attendu": "Une infobulle affiche nom localisé, niveau requis et coût.",
    },
    {
        "id": "TECH-005", "cat": "TECH", "rev": 3,
        "titre": "Modification du niveau requis (UnlockLevel)",
        "etapes": [
            "Attrape une icône (clic gauche maintenu) et déplace-la HORIZONTALEMENT vers une autre colonne de niveau, relâche.",
            "Vérifie le fichier : l'arbre indique le fichier modifié (TechTree dans l'onglet, ou disque après Ctrl+S).",
        ],
        "attendu": "UnlockLevel écrit dans le bon fichier (colonne réelle la plus proche) ; l'arbre le montre en direct.",
    },
    {
        "id": "TECH-006", "cat": "TECH", "rev": 3,
        "titre": "Modification du coût (UnlockCost)",
        "etapes": [
            "Clique une icône : la fiche s'ouvre ; clique la valeur du coût, change-la, valide.",
            "Ou : clic droit sur l'icône > modifier le coût.",
            "Vérifie le fichier (onglet ou disque après Ctrl+S) : UnlockCost.",
        ],
        "attendu": "UnlockCost mis à jour correctement ; le badge de l'icône et la fiche montrent la nouvelle valeur.",
    },
    {
        "id": "TECH-007", "cat": "TECH", "rev": 3,
        "titre": "Garde-fou : écriture refusée si onglet modifié",
        "pre": "BlocksConfig.ecf ouvert dans un onglet AVEC modification non enregistrée.",
        "etapes": [
            "Depuis l'arbre technologique, tente une modification (glisser d'une icône, TECH-005) et valide la boite d'erreur qui s'affiche.",
            "Refais ensuite un glisser : l'application doit rester fonctionnelle.",
        ],
        "attendu": "L'écriture est refusée avec un message clair, et l'application CONTINUE de fonctionner normalement ensuite (correctif v1.6.1 : la boite d'erreur détruisait l'item en cours de glisser et le relâchement suivant plantait).",
    },
    {
        "id": "TECH-008", "cat": "TECH", "rev": 3,
        "titre": "Rechargement auto de l'onglet si non modifié",
        "pre": "BlocksConfig.ecf ouvert dans un onglet SANS modification.",
        "etapes": [
            "Modifie un niveau via l'arbre technologique (TECH-005).",
            "Observe l'onglet ouvert : il doit montrer la nouvelle valeur.",
            "Puis fais une RECHERCHE dans cet onglet (même mot, deux fois : Entrée, Entrée).",
        ],
        "attendu": "L'onglet se recharge automatiquement et montre la nouvelle valeur, et la recherche fonctionne toujours après le rechargement (correctif v1.6.1 : RuntimeError à chaque recherche suivante).",
    },
    {
        "id": "TECH-009", "cat": "TECH", "rev": 2,
        "titre": "Déplacer vers une catégorie (TechTreeNames)",
        "etapes": [
            "Clic droit sur un item > Déplacer vers..., choisis une catégorie dans le sous-menu.",
            "Vérifie le fichier : TechTreeNames remplacé intégralement, valeurs multiples entre guillemets.",
        ],
        "attendu": "TechTreeNames est remplacé par la nouvelle catégorie ; valeurs multiples entre guillemets.",
    },
    {
        "id": "TECH-010", "cat": "TECH", "rev": 2,
        "titre": "Changer le parent (mode pick) et racine",
        "etapes": [
            "Clic droit sur un item > Changer le parent : le mode « pick » s'active (bandeau si prévu), clique le nouveau parent dans l'arbre.",
            "Refais l'opération en cliquant un nœud RACINE pour en faire une racine.",
        ],
        "attendu": "TechTreeParent écrit vers le nouveau parent ; pour une racine, la propriété est SUPPRIMÉE (jamais laissée vide).",
    },
    {
        "id": "TECH-011", "cat": "TECH", "rev": 2,
        "titre": "Annulation globale d'une modification d'arbre",
        "etapes": [
            "Après une modification d'arbre (TECH-005 à 010), clique le bouton global Annuler de la fenêtre principale.",
        ],
        "attendu": "Le fichier retrouve son état antérieur ; l'arbre (rechargé) le reflète.",
    },
    {
        "id": "TECH-012", "cat": "TECH", "rev": 3,
        "titre": "Prévisualisation d'un nouveau bloc dans l'arbre (déplacements multiples)",
        "etapes": [
            "Dans l'assistant + Bloc, clique Prévisualiser dans l'arbre technologique...",
            "Dans l'arbre, déplace l'icône entourée : choisis niveau/categorie/parent.",
            "Déplace-la ENCORE plusieurs fois (le mode choix du parent est signalé par un bandeau orange -- Échap pour annuler).",
            "Valide la création.",
        ],
        "attendu": "Le bloc en prévisu est déplaçable AUTANT DE FOIS que voulu ; le parent choisi est pris en compte au résultat (correctif v1.6.1 : le mode pick s'activait en silence et avalait les clics).",
    },
    {
        "id": "TECH-013", "cat": "TECH", "rev": 2,
        "titre": "Fiche info : export Markdown",
        "etapes": [
            "Ouvre la fiche d'info d'un bloc (double-clic dans l'éditeur ECF).",
            "Clique le bouton export (à côté de la croix), choisis un fichier .md.",
            "Ouvre le .md produit (Bloc-notes ou éditeur Markdown).",
        ],
        "attendu": "Fichier Markdown écrit, miroir de la fiche (description, stats, déblocage, fabrication, prix) sans balises HTML ; confirmation d'export.",
    },
    {
        "id": "TECH-014", "cat": "TECH", "rev": 3,
        "titre": "Arbre technologique : coût de déblocage visible sur chaque icône",
        "etapes": [
            "Outils > Arbre technologique...",
            "Observe le badge doré EN HAUT À GAUCHE de CHAQUE icône.",
            "Agrandis la fenêtre : icône et badge grossissent ensemble.",
            "Survole une icône : l'infobulle doit confirmer le même coût.",
        ],
        "attendu": "Chaque icône porte son UnlockCost (badge doré sur pastille sombre, EN HAUT À GAUCHE, police proportionnelle à l'icône) ; le chiffre correspond à l'infobulle.",
    },
    {
        "id": "TECH-015", "cat": "TECH", "rev": 2,
        "titre": "Arbre adaptatif : niveaux 1 à 25 visibles à toute résolution",
        "etapes": [
            "Outils > Arbre technologique...",
            "Réduis la fenêtre au minimum, puis agrandis-la en plein écran (ou sur un second écran d'une autre résolution).",
        ],
        "attendu": "Les 9 jalons (Niveau 1 à Niveau 25) restent TOUJOURS tous visibles sans défilement horizontal ; icônes, tuiles et badges s'agrandissent/réduisent avec la fenêtre (bornes mini/maxi pour rester lisibles).",
    },
    {
        "id": "FICHE-001", "cat": "TECH", "rev": 4,
        "titre": "Fiche info : ouverture au DOUBLE-clic sur un bloc (éditeur ECF)",
        "etapes": [
            "Dans un onglet ECF de la copie de travail, clique UNE fois un bloc de l'arbre : la fiche ne doit pas s'ouvrir.",
            "Puis double-clique le MÊME bloc.",
        ],
        "attendu": "Un clic simple N'OUVRE PAS la fiche ; seul le double-clic affiche la fiche flottante (vue COMPLETE par défaut : toutes les propriétés, même « display: false »).",
    },
    {
        "id": "FICHE-002", "cat": "TECH", "rev": 6,
        "titre": "Fiche info : vue COMPLETE par défaut + libellés et descriptions traduits",
        "etapes": [
            "Ouvre la fiche d'un bloc connu (ex : FuelTankMSLarge) : TOUTES les propriétés sont visibles, y compris celles en « display: false ».",
            "Crée ou duplique un bloc/Template, ouvre sa fiche AVANT enregistrement.",
            "Ouvre la fiche d'un bloc du SCÉNARIO dont la description existe en français dans Extras/Localization.csv (même si son en-tête de colonne s'appelle « French »).",
        ],
        "attendu": "Vue COMPLETE (défaut, demande du 31/08/2026) : toutes les propriétés affichées, « display: false » compris. Blocs CRÉÉS : toutes leurs propriétés s'affichent, libellés traduits (Temps de fabrication, Quantité produite, Constructeur portable pour les codes Target...) même si le jeu ne connaît pas la clé. DESCRIPTION (Info) lue dans la colonne FR du Localization.csv DU SCÉNARIO en priorité (alias « French » reconnus), repli pack vanilla ; ingrédients confinés à FABRICATION ; aucun double deux-points.",
    },
    {
        "id": "FICHE-003", "cat": "TECH", "rev": 2,
        "titre": "Fiche info : rendu BBCode dans les valeurs",
        "pre": "Un bloc avec AllowPlacingAt (codes couleur du jeu) ou un Info: BBCode.",
        "etapes": [
            "Ouvre sa fiche (double-clic) et observe les valeurs colorées.",
        ],
        "attendu": "Les codes [c][RRGGBB]...[-][/c] se rendent visuellement comme en jeu (couleurs appliquées).",
    },
    {
        "id": "FICHE-004", "cat": "TECH", "rev": 3,
        "titre": "Fiche info : déplacement et fermeture (bascule)",
        "etapes": [
            "Ouvre la fiche d'un bloc par double-clic, déplace-la à la souris (glisser sa barre de titre).",
            "Double-clique à nouveau le MÊME bloc : la fiche se referme.",
            "Double-clique un AUTRE bloc : elle se rouvre sur celui-ci.",
        ],
        "attendu": "Double-clic sur le bloc déjà affiché = la fiche se referme (bascule) ; double-clic sur un autre bloc = elle se rouvre sur celui-ci, sans perdre son déplacement.",
    },
    {
        "id": "FICHE-005", "cat": "TECH", "rev": 3,
        "titre": "Fiche info : édition INLINE d'une valeur (éditeur ECF)",
        "pre": "Onglet ECF de la copie de travail ouvert.",
        "etapes": [
            "Double-clique un bloc pour ouvrir sa fiche.",
            "Clique une valeur (ex : HitPoints) : une liste déroulante EDITABLE apparaît (valeurs observées du fichier, tri fréquence, flèche visible) avec la valeur BRUTE courante.",
            "Choisis une valeur proposée OU tape-la librement, valide avec Entrée.",
            "Teste aussi Échap pendant la saisie (annule), puis l'annulation de l'onglet (Ctrl+Z).",
        ],
        "attendu": "Le fichier est modifié (marqueur ✎ *, compteur de modifications à jour, annotation d'origine), le tableau de propriétés ET la fiche montrent la nouvelle valeur ; annuler de l'onglet revient à l'ancienne valeur. Échap pendant la saisie annule sans écrire. Sans historique pour la clé : saisie libre simple.",
    },
    {
        "id": "FICHE-006", "cat": "TECH", "rev": 3,
        "titre": "Fiche info : ajouter / supprimer une propriété (listes déroulantes)",
        "etapes": [
            "Ouvre la fiche d'un bloc, clique « + Ajouter une propriété » : les combos de clé et de valeur proposent les clés/valeurs observées du fichier (saisie libre possible).",
            "Renseigne et valide.",
            "Puis clic droit sur cette nouvelle ligne > Supprimer cette propriété.",
        ],
        "attendu": "La propriété est ajoutée au bloc (visible fiche + tableau + fichier, annulable) puis supprimée. Les propriétés de la ligne d'ouverture (Id, Name) ne sont jamais proposables à la suppression.",
    },
    {
        "id": "FICHE-007", "cat": "TECH", "rev": 3,
        "titre": "Fiche info : ingrédients du Template éditables (quantités, ajout, suppression)",
        "pre": "Un bloc dont le Template existe dans Templates.ecf.",
        "etapes": [
            "Ouvre la fiche du bloc, section FABRICATION.",
            "Clique une quantité d'ingrédient, change-la, valide.",
            "Ajoute un ingrédient (« + Ajouter un ingrédient ») : la combo propose les NOMS d'items/blocs (ItemsConfig + BlocksConfig) ; tape ou choisis-en un, saisis une quantité, valide.",
            "Puis supprime-le (clic droit > Supprimer cet ingrédient).",
        ],
        "attendu": "Templates.ecf est mis à jour (onglet ouvert : marqué modifié ; sinon écriture disque directe avec annulation globale) ; la fiche rafraîchit les quantités en direct.",
    },
    {
        "id": "FICHE-008", "cat": "TECH", "rev": 2,
        "titre": "Fiche info éditable depuis l'ARBRE technologique",
        "etapes": [
            "Outils > Arbre technologique...",
            "Clic simple (sans glisser) sur une icône : la fiche s'ouvre ; double-clic aussi.",
            "Modifie une valeur (ex : le coût) et valide.",
            "Clique le bouton global Annuler.",
        ],
        "attendu": "La fiche s'ouvre sur le nœud, complète et éditable. Chaque modification écrit le fichier (annulation globale enregistrée, onglet ouvert rechargé, arbre et badge mis à jour en direct) ; Annuler restaure l'état antérieur. Glisser une icône n'ouvre PAS la fiche.",
    },
    {
        "id": "FICHE-009", "cat": "TECH", "rev": 2,
        "titre": "Fiche info : bascule « Vue jeu (fidèle F3) » / vue complète",
        "etapes": [
            "Ouvre la fiche d'un bloc vrai du jeu (avec attributs display).",
            "Coche « Vue jeu (fidèle F3) » en haut de la fiche, puis décoche-la.",
            "Exporte la fiche en Markdown dans chaque mode (TECH-013) et compare les contenus.",
        ],
        "attendu": "Cochée : la fiche retombe sur la fidèle F3 du jeu (les « display: false » sont masqués). Décochée (défaut) : tout est visible. L'export Markdown reflète TOUJOURS la vue affichée.",
    },
    {
        "id": "FICHE-010", "cat": "TECH", "rev": 3,
        "titre": "Fiche info : modifier le DESCRIPTIF (FR + EN, BBCode, traduction)",
        "pre": "Un bloc AVEC descriptif (propriété Info: + ligne Localization.csv) et un bloc SANS Info:.",
        "etapes": [
            "Ouvre la fiche d'un bloc, clique le CRAYON à côté de « Descriptif ».",
            "Teste la barre : gras/italique/souligné (autour de la sélection), couleur (palette -> [c][hex]...[-][/c]).",
            "Teste la traduction : boutons FR -> EN / EN -> FR, et clic droit dans un champ > Traduire vers...",
            "Modifie, valide. Recommence sur le bloc SANS Info: (la fenêtre propose de CRÉER la clé).",
        ],
        "attendu": "La fenêtre pré-remplit FR/EN depuis Localization.csv. La barre insère le BBCode dans l'éditeur ACTIF (celui où tu as cliqué/déplacé le curseur), autour de la sélection. La traduction utilise le mécanisme existant (moteur en ligne, confirmation avant remplacement) ; sans traduction configurée, les boutons sont grisés et le clic droit explique pourquoi. À la validation : CSV mis à jour (autres colonnes préservées), fiche rafraîchie, annulable via le bouton Annuler global. Bloc sans Info: : propriété ajoutée + ligne CSV créée.",
    },
    # ---------------------------------------------------------------- OPT
    {
        "id": "OPT-001", "cat": "OPT", "rev": 2,
        "titre": "Options : nom pour les annotations",
        "etapes": [
            "Options > Nom pour les annotations..., saisis un nom reconnaissable (ex : David), valide.",
            "Modifie une valeur dans un onglet ECF, enregistre (Ctrl+S), ouvre le fichier brut (ECF-006).",
        ],
        "attendu": "Les nouvelles annotations portent le nouveau nom (« -- Mod par David »).",
    },
    {
        "id": "OPT-002", "cat": "OPT", "rev": 2,
        "titre": "Options : autoriser la fusion (activation)",
        "etapes": [
            "Coche Options > Autoriser la fusion (experimental, désactivé par défaut).",
            "Clic droit sur un fichier des panneaux A/B : les actions de fusion apparaissent.",
            "Décoche l'option : les actions disparaissent.",
        ],
        "attendu": "Les actions de fusion apparaissent dans le menu contextuel (et disparaissent en décochant).",
    },
    {
        "id": "OPT-003", "cat": "OPT", "rev": 2,
        "titre": "Options : langue de traduction par défaut",
        "etapes": [
            "Options > Langue de traduction par défaut..., change la langue, valide.",
            "Dans un onglet CSV, clique le bouton Traduire rapide sur une cellule.",
        ],
        "attendu": "La traduction rapide cible la langue configurée (TRAD-004).",
    },
    {
        "id": "OPT-004", "cat": "OPT", "rev": 3,
        "titre": "Options : thème visuel (changement à chaud)",
        "etapes": [
            "Ouvre une session chargée (projet + plusieurs onglets), change de thème dans Options > Theme.",
            "Observe : l'interface se repeint EN UN SEUL passage (plus de balayage progressif).",
            "Passe au theme Verriere SANS redémarrer, puis repasse sur un autre thème.",
        ],
        "attendu": "Le thème s'applique immédiatement et persiste au redémarrage. Correctif v1.6.1 : les repaints intermédiaires sont gelés pendant l'échange (plus de traînée perceptible), et Verrière (re)tente le flou acrylique AU CHANGEMENT de thème, pas seulement au démarrage.",
    },
    {
        "id": "OPT-005", "cat": "OPT", "rev": 2,
        "titre": "i18n : aucune clé brute à l'écran (FR)",
        "etapes": [
            "Parcours TOUS les menus (Fichier, Options, Outils, Vérification, Aide) et les principales fenêtres en français.",
            "Cherche des textes suspects de la forme « menu.xxx » ou « runner.xxx ».",
        ],
        "attendu": "Aucune chaîne du type « menu.xxx » ni texte manquant : tout est traduit.",
    },
    {
        "id": "OPT-006", "cat": "OPT", "rev": 2,
        "titre": "i18n : aucune clé brute à l'écran (EN)",
        "etapes": [
            "Bascule en anglais (bouton FR/EN), parcours les mêmes écrans qu'en OPT-005.",
        ],
        "attendu": "Tout est traduit en anglais, aucune clé FR visible. (Reste connu : les explications de propriétés de la fiche restent FR -- reporté, gros travail de contenu.)",
    },
    {
        "id": "OPT-007", "cat": "OPT", "rev": 2,
        "titre": "Aide : wikis FR/EN consultables",
        "etapes": [
            "Aide > Wiki de l'application (fonctions)..., en FR puis en EN (bascule le bouton FR/EN entre les deux).",
            "Aide > Wiki Empyrion (propriétés, fichiers, structure)..., en FR puis EN.",
        ],
        "attendu": "Les 4 wikis s'ouvrent dans la langue attendue, contenu à jour.",
    },
    {
        "id": "OPT-008", "cat": "OPT", "rev": 3,
        "titre": "Aide : tutoriels + politique de confidentialité + à propos",
        "etapes": [
            "Aide > Tutoriels... : ouvre les 3 tutoriels.",
            "Aide > Politique de confidentialité... puis Aide > A propos...",
        ],
        "attendu": "Le texte officiel GPLv3 s'ouvre en anglais (seule version juridiquement faisant foi) avec une NOTE explicative affichée dans A propos (clarifié v1.6.1).",
    },
    {
        "id": "OPT-009", "cat": "OPT", "rev": 3,
        "titre": "i18n : boutons standards de Qt dans la langue choisie",
        "etapes": [
            "En français, ouvre une boîte de confirmation Oui/Non (ex : duplication avec création de recettes).",
            "Bascule en anglais (bouton FR/EN) et rouvre la même boîte.",
        ],
        "attendu": "Les boutons affichent Oui/Non en français, Yes/No en anglais (jamais l'inverse ni l'anglais forcé).",
    },
    {
        "id": "OPT-010", "cat": "OPT", "rev": 2,
        "titre": "Audit i18n automatique sans régression",
        "etapes": [
            {
                "txt": "Depuis la racine du dépôt (développeurs), lance :",
                "cmd": ["python tools/audit_i18n.py"],
            },
        ],
        "attendu": "Code retour 0 : aucune clé t() manquante, aucune clé sans fr/en, aucun littéral affiché en dur dans gui/ et core/.",
    },

    # ---------------------------------------------------------------- CLI
    {
        "id": "CLI-001", "cat": "CLI", "rev": 3,
        "titre": "CLI : verifier_parser_ecf + ouvrir une invite de commandes",
        "etapes": [
            "Ouvre une invite de commandes : touche Windows + R, tape cmd, appuie sur Entrée (une fenêtre noire s'ouvre).",
            {
                "txt": "Version APPLICAtion INSTALLÉE : colle la 1re commande (remplace <fichier> par le chemin du fichier, Maj+clic droit sur le fichier > Copier en tant que chemin d'accès).",
                "cmd": ["\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-ecf \"<fichier>\""],
            },
            {
                "txt": "Version DÉPÔT (développeurs) : colle la 2e commande depuis la racine du dépôt -- les scripts CLI sont TOUS dans cli/ (correctif protocole v1.6.1).",
                "cmd": ["python cli/verifier_parser_ecf.py \"<fichier>\""],
            },
        ],
        "attendu": "Round-trip ECF vérifié (message OK), ou erreurs claires listées.",
    },
    {
        "id": "CLI-002", "cat": "CLI", "rev": 3,
        "titre": "CLI : verifier_parser_yaml",
        "etapes": [
            "Invite de commandes ouverte (CLI-001), puis :",
            {
                "txt": "Colle l'une des commandes (remplace <fichier>) -- forme installée puis forme dépôt (scripts dans cli/, voir CLI-001) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-yaml \"<fichier>\"",
                    "python cli/verifier_parser_yaml.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Round-trip YAML confirmé, ou erreurs claires.",
    },
    {
        "id": "CLI-003", "cat": "CLI", "rev": 2,
        "titre": "CLI : verifier_parser_csv",
        "etapes": [
            {
                "txt": "Colle l'une des commandes (remplace <fichier>) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-csv \"<fichier>\"",
                    "python cli/verifier_parser_csv.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Round-trip CSV confirmé.",
    },
    {
        "id": "CLI-004", "cat": "CLI", "rev": 2,
        "titre": "CLI : diagnostic_bloc",
        "etapes": [
            {
                "txt": "Cherche un bloc par Id, y compris dans les commentaires (remplace <fichier> et <Id> -- ex : 1625) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" diagnostic-bloc \"<fichier>\" <Id>",
                    "python cli/diagnostic_bloc.py \"<fichier>\" <Id>",
                ],
            },
        ],
        "attendu": "Le bloc est retrouvé et affiché, y compris s'il est commenté (désactivé).",
    },
    {
        "id": "CLI-005", "cat": "CLI", "rev": 2,
        "titre": "CLI : detecter_imbrication_anormale",
        "etapes": [
            {
                "txt": "Sur un fichier sain, puis sur un cas fabriqué (un bloc dont l'accolade fermante a été supprimée) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" detecter-imbrication \"<fichier>\"",
                    "python cli/detecter_imbrication_anormale.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Aucune fausse détection sur le fichier sain ; détection sur le cas fabriqué.",
    },
    {
        "id": "CLI-006", "cat": "CLI", "rev": 2,
        "titre": "CLI : diff_ecf",
        "etapes": [
            "Fais deux copies d'un fichier et modifie un bloc dans l'une (ajoute un bloc dans l'une des deux).",
            {
                "txt": "Compare les deux versions (remplace <versionA> et <versionB>) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" diff \"<versionA>\" \"<versionB>\"",
                    "python cli/diff_ecf.py \"<versionA>\" \"<versionB>\"",
                ],
            },
        ],
        "attendu": "Blocs ajoutés/supprimés/modifiés correctement listés.",
    },
    {
        "id": "CLI-007", "cat": "CLI", "rev": 2,
        "titre": "CLI : edit_ecf interactif",
        "etapes": [
            {
                "txt": "Lance l'éditeur interactif (remplace <fichier>), parcours les commandes (aide intégrée), quitte SANS modifier (commande de sortie indiquée par l'aide, ex : q) :",
                "cmd": [
                    "python cli/edit_ecf.py \"<fichier>\"",
                ],
            },
        ],
        "attendu": "Navigation fonctionnelle, aucune modification involontaire à la sortie.",
    },
    {
        "id": "CLI-008", "cat": "CLI", "rev": 2,
        "titre": "CLI : merge_ecf",
        "etapes": [
            {
                "txt": "Fusionne deux sources vers une sortie (remplace <sortie>, <source1>, <source2> -- sur des COPIES de test), puis vérifie la sortie (verifier-ecf) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" merge \"<sortie>\" \"<source1>\" \"<source2>\"",
                    "python cli/merge_ecf.py \"<sortie>\" \"<source1>\" \"<source2>\"",
                ],
            },
        ],
        "attendu": "Fusion conforme aux priorités ; sortie fidèle (verifier-ecf OK).",
    },
    {
        "id": "CLI-009", "cat": "CLI", "rev": 2,
        "titre": "CLI : transform_ecf",
        "etapes": [
            "Sur une COPIE de test, prépare une transformation (multiplier une propriété x2) : la commande sans argument affiche son usage détaillé.",
            {
                "txt": "Lance la transformation (voir usage affiché), puis vérifie le résultat (verifier-ecf) :",
                "cmd": [
                    "\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" transform",
                    "python cli/transform_ecf.py",
                ],
            },
        ],
        "attendu": "Transformation appliquée uniquement aux blocs cibles, fichier valide après vérification.",
    },
    # ---------------------------------------------------------------- ROBU
    {
        "id": "ROBU-001", "cat": "ROBU", "rev": 2,
        "titre": "Fermeture sans modification : directe",
        "etapes": [
            "Sans aucun onglet modifié (tous les titres d'onglets normaux, pas de rouge), ferme l'application (croix en haut à droite).",
        ],
        "attendu": "Fermeture immédiate, aucun dialogue.",
    },
    {
        "id": "ROBU-002", "cat": "ROBU", "rev": 3,
        "titre": "Fermeture avec onglets modifiés : dialogue",
        "etapes": [
            "Modifie DEUX fichiers sans enregistrer (deux onglets rouges), puis ferme l'application.",
            "Lis le dialogue : liste des fichiers, boutons Enregistrer tout / Abandonner / Annuler.",
            "Teste les trois boutons (relance le scénario à chaque fois).",
        ],
        "attendu": "Dialogue à boutons APPLICATION listant les fichiers : Enregistrer tout (défaut) / Abandonner / Annuler -- Annuler ramène dans l'application sans rien perdre.",
    },
    {
        "id": "ROBU-003", "cat": "ROBU", "rev": 2,
        "titre": "Fermeture : enregistrement en échec annule la sortie",
        "pre": "Rends un fichier ouvert et modifié lecture seule au niveau système : clic droit sur le fichier > Propriétés > coche Lecture seule (l'application doit être fermée au moment de le faire, puis relancée avec le fichier ouvert et modifié).",
        "etapes": [
            "Ferme l'application et choisis Enregistrer dans le dialogue de fermeture.",
        ],
        "attendu": "Erreur affichée pour le fichier en échec, la fermeture est ANNULÉE, le travail reste ouvert.",
    },
    {
        "id": "ROBU-004", "cat": "ROBU", "rev": 2,
        "titre": "Excepthook : dialogue au lieu du crash brutal",
        "etapes": [
            "Provoque une erreur interne (ou attends une erreur réelle) : par exemple déconnecte un périphérique pendant une opération, ou signale tout comportement anormal.",
        ],
        "attendu": "Dialogue avec détails dépliables et bouton Signaler ; l'application NE FERME PAS.",
    },
    {
        "id": "ROBU-005", "cat": "ROBU", "rev": 2,
        "titre": "Vérification de mise à jour : silencieuse + manuelle",
        "etapes": [
            "Lance l'application (vérification auto silencieuse au démarrage).",
            "Aide > Vérifier les mises à jour... (manuelle).",
        ],
        "attendu": "Auto : rien si pas de mise à jour ; manuelle : message même en cas d'égalité/échec.",
    },
    {
        "id": "ROBU-006", "cat": "ROBU", "rev": 2,
        "titre": "Bouton Signaler : formulaire pré-rempli",
        "etapes": [
            "Ouvre le dialogue d'erreur (ROBU-004) ou Aide > Signaler un bug / une amélioration..., clique Signaler.",
            "Remplis le formulaire et clique Envoyer : le navigateur s'ouvre sur GitHub.",
        ],
        "attendu": "La page GitHub s'ouvre pré-remplie (titre, description, infos techniques, capture à joindre) ; rien n'est envoyé automatiquement sans toi.",
    },
    {
        "id": "ROBU-007", "cat": "ROBU", "rev": 2,
        "titre": "Settings corrompus : démarrage quand même",
        "pre": "Ferme l'appli, ouvre le dossier ci-dessous (dossier caché du profil utilisateur -- PAS à la racine du dépôt ; correctif protocole v1.6.1) et remplace le contenu de settings.json par xxx.",
        "etapes": [
            {
                "txt": "Ouvre le dossier (barre d'adresse de l'explorateur), ouvre settings.json avec le Bloc-notes, remplace tout par xxx, enregistre :",
                "cmd": ["%USERPROFILE%/.empyrion_editor"],
            },
            "Lance l'application, vérifie les options, change une option.",
        ],
        "attendu": "Démarrage normal (valeurs par défaut), settings reconstruit à la prochaine écriture.",
    },
    {
        "id": "ROBU-008", "cat": "ROBU", "rev": 2,
        "titre": "Projets récents corrompus : liste vide, pas de crash",
        "pre": "Ferme l'appli, corromps projects.json (même dossier que ROBU-007) en y écrivant xxx.",
        "etapes": [
            {
                "txt": "Ouvre le dossier (barre d'adresse de l'explorateur), ouvre projects.json avec le Bloc-notes, remplace tout par xxx, enregistre :",
                "cmd": ["%USERPROFILE%/.empyrion_editor"],
            },
            "Lance l'application, ouvre Fichier > Projets récents...",
        ],
        "attendu": "Liste vide ou partielle sans plantage.",
    },
    {
        "id": "ROBU-009", "cat": "ROBU", "rev": 3,
        "titre": "Protocole de test accessible dans l'application",
        "etapes": [
            "Aide > Protocole de test (tutoriel / débogage)...",
            "Clique « ▶ Commencer une session de tests... » : choisis vierge ou reprise, teste cas par cas (pas-à-pas, verdicts F1 à F4).",
            "Parcours les catégories, filtre par mot-clé, exporte le bilan en Markdown/CSV.",
        ],
        "attendu": "Le pas-à-pas complet est disponible DANS l'application (moteur embarqué) ; les verdicts sont sauvegardés entre deux lancements ; l'export écrit un bilan complet. Barres « Préparation » et « Résultat attendu » LISIBLES sur thèmes clairs ET sombres (texte sombre sur fond clair).",
    },

    # ---------------------------------------------------------------- BUILD
    {
        "id": "BUILD-001", "cat": "BUILD", "rev": 3,
        "titre": "Installeur : installation propre",
        "pre": "L'installeur de la release à tester (Setup-EmpyrionScenarioEditor-vX.Y.Z.exe).",
        "etapes": [
            "Double-clique le Setup sur une machine (ou VM) propre -- sans Python installé.",
            "Suis l'assistant d'installation (Suivant, Installer, Terminer).",
            "Lance l'application depuis le raccourci créé (bureau ou menu Démarrer).",
        ],
        "attendu": "Installation sans erreur ; l'application démarre, tout fonctionne (wikis, icônes, pack de localisation, protocole de test embarqué, aperçu PDF embarqué).",
    },
    {
        "id": "BUILD-002", "cat": "BUILD", "rev": 2,
        "titre": "Désinstallation propre",
        "etapes": [
            "Paramètres Windows > Applications > Empyrion Scenario Editor > Désinstaller (ou panneau de configuration).",
            "Après désinstallation, vérifie les deux emplacements : dossier Programme Files, et le dossier caché de l'utilisateur (commande ci-dessous).",
            {
                "txt": "Dossier de données utilisateur (doit RESTER) :",
                "cmd": ["%USERPROFILE%/.empyrion_editor"],
            },
        ],
        "attendu": "Désinstallation complète des fichiers programme ; les données utilisateur (~/.empyrion_editor) restent, documenté.",
    },
    {
        "id": "BUILD-003", "cat": "BUILD", "rev": 2,
        "titre": "CLI embarquée : EmpyrionEditorCLI autonome",
        "etapes": [
            "Invite de commandes (CLI-001) SANS Python installé (machine de l'installeur).",
            {
                "txt": "Lance une commande (remplace <fichier>) :",
                "cmd": ["\"C:/Program Files/Empyrion Scenario Editor/CLI/EmpyrionEditorCLI.exe\" verifier-ecf \"<fichier>\""],
            },
            "Lance-la SANS argument pour voir la liste des commandes.",
        ],
        "attendu": "Fonctionne sans Python installé, résultats identiques aux scripts du dépôt.",
    },
    {
        "id": "BUILD-004", "cat": "BUILD", "rev": 2,
        "titre": "Vérificateur de mise à jour : détection de la release",
        "pre": "La release <version> est publiée sur GitHub.",
        "etapes": [
            "Avec une version ANTÉRIEURE installée, lance l'application et attends quelques secondes au démarrage.",
            "Puis, avec la version à jour, relance : plus de proposition.",
        ],
        "attendu": "La mise à jour <version> est proposée au démarrage (et non proposée si déjà à jour).",
    },

    # ---------------------------------------------------------------- GUI
    {
        "id": "GUI-001", "cat": "GUI", "rev": 2,
        "titre": "Theme H - Verrière néon : bascule et rendu",
        "etapes": [
            "Options > Theme > H - Verrière néon.",
            "Observe les couleurs (noir océan + cyan), les panneaux verre, le gloss des boutons actifs.",
            "Rebascule vers le thème précédent puis revient.",
        ],
        "attendu": "Bascule immédiate sans redémarrage ; sélections en NÉON (halo + liseré + texte clair) dans l'arbre et le tableau ; les autres thèmes sont inchangés.",
    },
    {
        "id": "GUI-002", "cat": "GUI", "rev": 3,
        "titre": "Theme Verrière : flou acrylique Windows 11",
        "pre": "Windows 11 22H2 minimum (build 22621) ET effets de transparence Windows activés (Paramètres > Personnalisation > Couleurs). Redémarre l'application avec le thème H actif.",
        "etapes": [
            "Place une fenêtre COLORÉE (navigateur, image...) derrière l'éditeur.",
            "Observe la BARRE DE TITRE : elle laisse voir le fond flouté.",
            "Déplace l'éditeur et observe ce fond changer.",
            "Change aussi de thème à chaud : Verrière (re)tente le flou sans redémarrage (voir OPT-004).",
        ],
        "attendu": "Le contenu DERRIÈRE la fenêtre apparaît flouté (acrylique) -- visible en priorité sur la barre de titre ; les panneaux restent peints pour la lisibilité. CORRECTIF v1.6.1 : il manquait DwmExtendFrameIntoClientArea(-1) -- l'attribut backdrop SEUL ne produit aucun effet visible (vérifié par capture côte à côte). Sans support (Win10, bureau distant, transparence désactivée) : fond peint du thème, rien d'illisible.",
    },
    {
        "id": "GUI-003", "cat": "GUI", "rev": 2,
        "titre": "Barre d'outils : lisibles dans TOUS les thèmes",
        "etapes": [
            "Passe successivement en thèmes Classic (clair), B, H (Options > Theme).",
            "Observe les 6 boutons de la barre du haut (Enregistrer, Recherche, Arbre, Galaxie, PDA, Centre de vérification).",
        ],
        "attendu": "Boutons auto-peints (fond bleu accent, icônes blanches + libellés) lisibles sur tout fond ; au changement de thème, les libellés suivent la langue et le thème.",
    },
    {
        "id": "GUI-004", "cat": "GUI", "rev": 2,
        "titre": "Barre d'outils : les 6 boutons déclenchent les bonnes fenêtres",
        "etapes": [
            "Avec un projet ouvert, clique successivement Enregistrer, Recherche, Arbre technologique, Carte de la galaxie, Missions PDA, Centre de vérification.",
            "Pour chacun, compare avec l'entrée de menu équivalente.",
        ],
        "attendu": "Chaque bouton ouvre exactement la même fenêtre que son entrée de menu.",
    },
    {
        "id": "GUI-005", "cat": "GUI", "rev": 3,
        "titre": "Raccourcis clavier affichés et fonctionnels",
        "etapes": [
            "Ouvre les menus Outils et Vérification et lis les raccourcis affichés à droite des libellés.",
            "Teste Ctrl+Maj+F (recherche), Ctrl+T (arbre), Ctrl+G (galaxie), Ctrl+M (PDA), F5 (centre de vérification) -- touches en même temps.",
        ],
        "attendu": "Tous les raccourcis sont visibles dans leur menu ; le libellé du Centre de vérification a été raccourci pour que le F5 ne soit plus tronqué (correctif v1.6.1).",
    },
    {
        "id": "GUI-006", "cat": "GUI", "rev": 2,
        "titre": "Compteur de modifications dans le bandeau",
        "etapes": [
            "Modifie 2 fichiers ouverts sans enregistrer.",
            "Observe le libellé du panneau Copie de travail.",
            "Enregistre chaque onglet modifié (Ctrl+S dans chaque onglet, ou le bouton Enregistrer de la barre d'outils) puis ré-observe.",
        ],
        "attendu": "Libellé : « Copie de travail -- N fichier(s) modifié(s) » avec le bon compte ; retour à « Copie de travail (modifiable) » après enregistrement.",
    },
    {
        "id": "GUI-007", "cat": "GUI", "rev": 2,
        "titre": "Barre d'état : résumé persistant du projet",
        "etapes": [
            "Ouvre un projet, modifie un fichier.",
            "Déclenche un message éphémère (ex : une action qui affiche un message en bas de la fenêtre).",
        ],
        "attendu": "Le résumé « projet - N modifié(s) » reste affiché à DROITE de la barre d'état, jamais écrasé par les messages temporaires ; il affiche « Aucun projet ouvert » sans projet.",
    },
    {
        "id": "GUI-008", "cat": "GUI", "rev": 2,
        "titre": "Boîte de chargement sur les opérations longues",
        "etapes": [
            "Reprends un projet récent (Projets récents).",
            "Lance F5 (Centre de vérification) puis une recherche globale (Ctrl+Maj+F).",
            "Observe le bas de la fenêtre pendant chaque opération, et tente de cliquer ailleurs.",
        ],
        "attendu": "Boîte « Traitement en cours... » immédiate + curseur sablier ; impossible de cliquer ailleurs pendant l'opération ; disparition propre à la fin (même en cas d'erreur).",
    },

    # ---------------------------------------------------------------- PDA2
    {
        "id": "PDA2-001", "cat": "PDA2",
        "titre": "Éditeur PDA : ouverture sur un scénario réel",
        "etapes": [
            "Ouvre un projet dont le scénario contient Extras/PDA/PDA.yaml + PDA.csv (ex : vanille).",
            "Outils > Éditeur PDA (nouveau).",
            "Observe l'arbre : chapitres, puis déploie (petites flèches) en tâches puis actions.",
        ],
        "attendu": "L'arbre affiche TOUS les chapitres (titres résolus depuis PDA.csv, langue de l'appli), dépliables en tâches puis actions (libellé du type de Check). Ouverture couverte par le sablier, pas de gel.",
    },
    {
        "id": "PDA2-002", "cat": "PDA2",
        "titre": "Éditeur PDA : édition d'un chapitre",
        "etapes": [
            "Sélectionne un chapitre dans l'arbre.",
            "Change le Niveau requis, décoche Non passable, modifie la Description (texte FR).",
            "Ferme l'éditeur (croix), regarde l'onglet PDA.yaml (Ctrl+S pour sauvegarder) puis l'onglet PDA.csv.",
        ],
        "attendu": "Les onglets PDA.yaml/PDA.csv sont marqués modifiés ; le YAML contient les changements (clé supprimée si décochée, sauf clés structurelles) ; le CSV contient le nouveau texte sous un jeton pda_XXXXXXX, SANS doublon si le texte existait déjà.",
    },
    {
        "id": "PDA2-003", "cat": "PDA2",
        "titre": "Éditeur PDA : actions de tout type de Check",
        "etapes": [
            "Sélectionne une action, change son type (ex : WaitAction -> NearPoi).",
            "Remplis les champs du formulaire (POI via la liste avec recherche, distances).",
            "Ajoute une action « Sans objectif (texte seul) » et une action d'un type absent du formulaire.",
        ],
        "attendu": "Le formulaire suit le type choisi (champs spécifiques confirmés sur les vrais fichiers). Les actions sans Check restent du texte pur. Un type inconnu reste éditable (propriétés préservées).",
    },
    {
        "id": "PDA2-004", "cat": "PDA2",
        "titre": "Éditeur PDA : récompenses, répétition, activations",
        "etapes": [
            "Sur un chapitre : ajoute une récompense Item (MoneyCard en tête des suggestions) et une réputation Faction.",
            "Règle le Nombre de répétitions.",
            "Ajoute une activation (ChapterActivation) : saisie des POI, bascule vers un Check explicite (ex : DialogOption) puis retour implicite.",
            "Sauvegarde et vérifie le YAML (onglet PDA.yaml).",
        ],
        "attendu": "Rewards aux formes réelles (Item+Count[+Meta] / Type+Count[+Faction]), RepeatConditions ajoutées/retirées proprement, ChapterActivation avec première clé « Names » ou « Check » selon le champ Check (vide = forme implicite majoritaire du jeu).",
    },
    {
        "id": "PDA2-005", "cat": "PDA2",
        "titre": "Éditeur PDA : création, duplication, suppression, déplacement",
        "etapes": [
            "Crée un nouveau chapitre (+ boutons de l'arbre).",
            "Duplique un chapitre existant et compare les deux dans l'arbre.",
            "Déplace (boutons ▲/▼) puis supprime après confirmation.",
        ],
        "attendu": "Le dupliqué re-tokénise TOUS ses textes (titres/descriptions indépendants, lignes CSV ajoutées) et s'insère juste après l'original. Déplacement et suppression (avec confirmation) reflétés dans l'arbre et dans le YAML.",
    },
    {
        "id": "PDA2-006", "cat": "PDA2",
        "titre": "Assistant de mission PDA (3 étapes)",
        "etapes": [
            "Éditeur PDA > Assistant de création... : remplis l'étape 1, passe à l'étape 2 (Suivant).",
            "Ajoute 2 actions de types différents avec leurs quantités, passe à l'étape 3.",
            "Saisis titres/description + une récompense, clique Créer le chapitre.",
        ],
        "attendu": "Le chapitre apparaît sélectionné dans l'arbre avec tâche et actions configurées ; textes présents dans le CSV ; structure du YAML conforme (ChapterTitle/Category/NoSkip/Activatable/Visibility/PlayerLevel/Description + Tasks + Rewards). Le titre saisi EST appliqué à ChapterTitle.",
    },
    {
        "id": "PDA2-007", "cat": "PDA2",
        "titre": "Éditeur PDA : suggestions scénario + vanille",
        "etapes": [
            "Options : renseigne (ou non) le dossier Content du jeu (installation Steam) via Options > Dossier du jeu (vanille)...",
            "Ouvre l'éditeur PDA, ouvre une liste POI/Playfields d'un NearPoi puis d'un PlayfieldEntered.",
        ],
        "attendu": "Les listes proposent les valeurs du scénario ouvert COMPLÉTÉES par la vanille (POI, playfields, créatures) quand le dossier est renseigné ; sans lui, valeurs du scénario + déjà utilisées dans le PDA ; saisie libre toujours possible.",
    },
    {
        "id": "PDA2-008", "cat": "PDA2",
        "titre": "Éditeur PDA : modifications visibles dans les onglets YAML/CSV",
        "etapes": [
            "Édite plusieurs éléments dans l'éditeur PDA (texte, liste, récompense), ferme l'éditeur.",
            "Regarde l'onglet PDA.yaml puis l'onglet PDA.csv.",
        ],
        "attendu": "Dans PDA.yaml, l'arbre surligne (fond jaune pâle) les entrées modifiées ; dans PDA.csv, les lignes des jetons créés/modifiés sont surlignées de la même couleur. Les valeurs préfixées (« mbox;20|pda_XXX ») montrent un check vert et gardent leur préfixe après édition.",
    },
    {
        "id": "PDA2-009", "cat": "PDA2",
        "titre": "Éditeur PDA : bouton Annuler",
        "etapes": [
            "Édite un champ, ajoute puis supprime une activation, crée un chapitre.",
            "Clique le bouton « ↩ Annuler » plusieurs fois d'affilée.",
        ],
        "attendu": "Chaque clic restaure l'état antérieur des deux fichiers en mémoire (chapitre supprimé réapparaît, champ retrouve sa valeur, l'élément sélectionné reste pertinent) ; le bouton est grisé quand la pile est vide. Après fermeture, les onglets reflètent l'état final.",
    },
    {
        "id": "PDA2-010", "cat": "PDA2",
        "titre": "Éditeur PDA : rappel des dernières modifications à la reprise",
        "etapes": [
            "Fais quelques modifications, ferme l'éditeur (les onglets restent modifiés, ne sauvegarde pas encore).",
            "Sauvegarde (Ctrl+S), ferme l'application, relance, rouvre le même scénario et l'éditeur PDA.",
        ],
        "attendu": "Un bandeau gris en haut de l'éditeur rappelle les dernières modifications de la session précédente (horodatées, libellés de chaque élément touché) ; un journal complet est conservé dans ~/.empyrion_editor/pda_history.json (local, jamais versionné).",
    },
    {
        "id": "PDA2-011", "cat": "PDA2",
        "titre": "Éditeur PDA : bouton de traduction lisible",
        "etapes": [
            "Sélectionne une action, observe le bouton à droite de chaque champ de texte localisé (Description, Message de complétion...).",
            "Clique-le, puis fais un clic droit sur le champ.",
        ],
        "attendu": "Le bouton affiche le GLOBE qtawesome de l'application (pas un carré bleu emoji) et son clic ouvre l'éditeur de toutes les langues du jeton ; le clic droit sur le champ propose toujours « Traduire vers... ».",
    },
    {
        "id": "PDA2-012", "cat": "PDA2",
        "titre": "Éditeur PDA : titres éditables partout + rien d'invisible",
        "etapes": [
            "Sélectionne un chapitre, une tâche puis une action : le TITRE est proposé en tête de chaque panneau (modifiable).",
            "Édite le titre du chapitre : l'arbre se met à jour sans perdre la frappe.",
            "Ouvre un chapitre/tâche riche d'un vrai fichier (ex : avec OnComplete*Ops, PlayfieldTypes, VisibleOnStart...).",
        ],
        "attendu": "Tout est visible : scalaires et listes (Playfields, PlayfieldTypes, VisibleOnStart..., RewardedTasks/Chapters, signaux) dans le formulaire ; sections complexes (On*Ops) affichées en « Avancé (lecture seule) ». Le titre du chapitre saisi dans l'assistant EST appliqué à ChapterTitle. Édition du titre : jeton conservé, texte CSV mis à jour (pas de clé orpheline).",
    },
    # ---------------------------------------------------------------- ECO
    {
        "id": "ECO-001", "cat": "ECO",
        "titre": "Éditeur d'économie : ouverture et lecture du fichier",
        "etapes": [
            "Ouvre un scénario (copie de travail contenant un TraderNPCConfig.ecf).",
            "Menu Outils > Éditeur d'économie (marchands PNJ)...",
            "Clique sur quelques marchands dans la liste de gauche.",
        ],
        "attendu": "La liste affiche les marchands du fichier ; pour chacun : tableau des items (nom, prix/stocks vente et achat) et fiche (texte d'accueil, catégorie, remise). Un prix en facteur s'affiche tel quel (ex : mf=1.1-1.2).",
    },
    {
        "id": "ECO-002", "cat": "ECO",
        "titre": "Économie : création du fichier de départ quand absent",
        "etapes": [
            "Prends une copie de travail SANS TraderNPCConfig.ecf (ou renomme temporairement le fichier existant).",
            "Menu Outils > Éditeur d'économie (marchands PNJ)...",
            "Réponds Oui à la proposition de création.",
        ],
        "attendu": "Un TraderNPCConfig.ecf minimal est créé dans Content/Configuration de la copie de travail (marchand TraderDefault), l'éditeur s'ouvre dessus et l'annulation d'espace de travail (bouton flèche arrière) peut supprimer le fichier créé.",
    },
    {
        "id": "ECO-003", "cat": "ECO", "rev": 2,
        "titre": "Économie : ajout d'items depuis le catalogue",
        "etapes": [
            "Sélectionne un marchand, clique « Catalogue... » : une fenêtre s'ouvre avec 3 onglets (Par catégorie, A→Z, Tous) et une recherche qui filtre partout.",
            "Onglet Par catégorie : Items > Medical, coche MedPack ; double-clique dessus pour l'ajout immédiat (la fenêtre reste ouverte).",
            "Coche 2-3 items d'autres catégories, clique « Ajouter la sélection ».",
            "Ajuste prix/stocks dans le tableau (prix et stocks absolus = ENTIERS ; formats : 100-150, 10, ou facteur mf=1.1-1.2).",
            "Compare avec l'onglet brut TraderNPCConfig.ecf (ouvert derrière).",
        ],
        "attendu": "Le catalogue liste TOUT le scénario (items ET blocs, icônes réelles, noms lisibles, MarketPrice, filtre « Masquer ceux sans MarketPrice »). Chaque item ajouté arrive avec prix = MarketPrice en absolu (repli mf=1.1-1.2 si prix inconnu) et stock 10-50 ; la sélection multiple = UNE seule annulation. Valeur invalide : message + cellule réaffichée.",
    },
    {
        "id": "ECO-004", "cat": "ECO", "rev": 2,
        "titre": "Économie : bascule prix plage ⇄ facteur",
        "etapes": [
            "Sélectionne une ligne d'item dont le prix est une plage (ex : 100-150).",
            "Clique « Convertir en facteur ».",
            "Clique à nouveau « Convertir en prix ».",
        ],
        "attendu": "Le prix devient un facteur mf= calculé depuis le MarketPrice de l'item (ex : 100-150 avec MarketPrice 126 → mf=0.79-1.19) puis revient en prix absolu ENTIER (arrondi au chiffre supérieur ; ici exactement 100-150). RÈGLE : prix et stocks absolus sont toujours des entiers — seuls les facteurs mf= ont des décimales. Si l'item n'a pas de MarketPrice connu : message clair, rien n'est modifié.",
    },
    {
        "id": "ECO-005", "cat": "ECO",
        "titre": "Économie : achat / vente (partie achat optionnelle)",
        "etapes": [
            "Sur un item « Vend » seul, mets la liste déroulante Échange sur « Vend + rachète ».",
            "Vérifie la ligne dans l'onglet brut, puis repasse sur « Vend ».",
        ],
        "attendu": "« Vend + rachète » ajoute prix d'achat (mf=0.4-0.5) et stock max d'achat (55-150) dans la chaîne ; « Vend » les retire. Les colonnes achat suivent la liste déroulante.",
    },
    {
        "id": "ECO-006", "cat": "ECO",
        "titre": "Économie : fiche du marchand (texte, catégorie, remise)",
        "etapes": [
            "Sélectionne un marchand, modifie son texte d'accueil (utilise Entrée pour un retour à la ligne), sa catégorie et sa remise (ex : 0.1).",
            "Clique « Appliquer la fiche », puis vérifie l'onglet brut.",
        ],
        "attendu": "SellingText est réécrit avec \\n échappé, SellingGoods et Discount mis à jour. Le texte ne casse pas la ligne du fichier (guillemets conservés).",
    },
    {
        "id": "ECO-007", "cat": "ECO",
        "titre": "Économie : duplication, création, suppression de marchand",
        "etapes": [
            "Duplique un marchand (bouton Dupliquer) et donne un nouveau nom.",
            "Crée un marchand vide, puis supprime-le (Supprimer, confirme).",
            "Rouvre le fichier brut pour comparer.",
        ],
        "attendu": "La duplication recopie TOUS les items et la fiche à l'identique (seul le nom change, y compris les prix en facteur). Le nom est unique (refus sinon). La suppression retire le bloc entier ; le reste du fichier est inchangé octet pour octet.",
    },
    {
        "id": "ECO-008", "cat": "ECO", "rev": 2,
        "titre": "Économie : inflation et pénurie (presets rapides)",
        "etapes": [
            "Cocher ou non « Sur le marchand sélectionné seulement », clique « Inflation... » et saisis 10.",
            "Clique « Pénurie... » et saisis 2.",
        ],
        "attendu": "Tous les prix (vente ET achat) sont multipliés par 1,1 (les stocks ne bougent pas) ; la pénurie DIVISE tous les stocks par 2 (les prix ne bougent pas). RÈGLE : les résultats absolus sont arrondis au chiffre ENTIER supérieur (stock 3 → 1,5 → 2 ; facteurs mf= inchangés, ils restent décimaux). Décoché : l'opération touche TOUS les marchands en une seule annulation.",
    },
    {
        "id": "ECO-009", "cat": "ECO",
        "titre": "Économie : variante régionale ×50 %",
        "etapes": [
            "Sélectionne un marchand, clique « Variante ×... », saisis 1.5.",
            "Regarde la nouvelle entrée dans la liste et ses prix.",
        ],
        "attendu": "Une variante « Nom @+50% » est créée (prix multipliés, stocks identiques) ; l'original est intact. C'est la façon de faire payer plus cher une station précise (le jeu n'a pas de multiplicateur par station : on duplique).",
    },
    {
        "id": "ECO-010", "cat": "ECO",
        "titre": "Économie : profils types (militaire, agricole, personnels)",
        "etapes": [
            "Sélectionne un marchand, choisis « Militaire (embarqué) » puis « Appliquer au marchand ».",
            "Enregistre un autre marchand comme profil type (« Enregistrer comme profil type... »), applique-le à un troisième.",
            "Ferme et rouvre l'éditeur d'économie : le profil personnel est toujours dans la liste.",
        ],
        "attendu": "Le catalogue du marchand est remplacé par celui du profil (numérotation Item1..N regénérée, catégorie et remise mises à jour). Les profils personnels sont conservés au niveau de l'APPLICATION (réutilisables dans un autre scénario).",
    },
    {
        "id": "ECO-011", "cat": "ECO",
        "titre": "Économie : TraderZone dans l'éditeur playfield",
        "etapes": [
            "Ouvre un playfield de la copie de travail (onglet structuré).",
            "En haut, choisis un marchand dans la liste « TraderZone ».",
            "Onglet POI : sur la ligne d'un POI, mets la colonne « TraderZone (marchands) » à un marchand, puis sauvegarde (Ctrl+S).",
            "Ouvre le yaml brut (bloc-notes ou onglet YAML complet).",
        ],
        "attendu": "La clé « TraderZone: <marchand> » est écrite en tête du playfield, et le POI gagne une section Properties avec Key: TraderZone / Value: <marchand>. Vider la cellule retire la section. En jeu, ces tables s'appliquent aux PNJ marchands réglés sur #ZONE#.",
    },
    {
        "id": "ECO-012", "cat": "ECO",
        "titre": "Économie : vérification (menu Vérification)",
        "etapes": [
            "Modifie une ligne Item pour référencer un item inexistant (ou crée une TraderZone vers un marchand supprimé), enregistre.",
            "Menu Vérification > Vérification économie (marchands PNJ)...",
        ],
        "attendu": "La fenêtre liste chaque problème (ERR = item absent du catalogue, plage inversée, TraderZone vers un profil inexistant ; ATT = profil jamais assigné à une zone). Corrige dans l'éditeur d'économie puis relance : plus aucun problème.",
    },
]


def cases_by_category():
    """Retourne {code_categorie: [cas...]} dans l'ordre de CATEGORIES."""
    grouped = {code: [] for code, _label in CATEGORIES}
    for case in CASES:
        grouped[case["cat"]].append(case)
    return grouped


def _step_parts(step):
    """(txt, cmds) d'une etape BRUTE (chaine ou dict {"txt","cmd"})."""
    if isinstance(step, dict):
        cmds = step.get("cmd") or []
        if isinstance(cmds, str):
            cmds = [cmds]
        return step.get("txt", ""), list(cmds)
    return step, []


def localized_case(case, lang=None):
    """Cas adapte a la langue affichee.

    Retourne une COPIE du cas dont :
    - "etapes" est NORMALISEE en liste de {"txt": ..., "cmds": [...]} --
      forme consommee par l'interface et les exports (plus jamais de
      chaine/dict brut en aval) ;
    - "titre"/"pre"/"etapes"/"attendu" sont remplaces par le miroir anglais
      (core/test_protocol_en.py) quand la langue est "en" -- les "cmds"
      restent celles du FR (une commande console ne se traduit pas), seul
      le texte change.
    """
    if lang is None:
        from core.i18n import get_language
        lang = get_language()
    out = dict(case)
    rows = [{"txt": txt, "cmds": cmds}
            for txt, cmds in (_step_parts(s) for s in case.get("etapes", []))]
    if lang == "en":
        en = _EN_TRANSLATIONS.get(case["id"]) or {}
        out["titre"] = en.get("titre") or case["titre"]
        if en.get("pre"):
            out["pre"] = en["pre"]
        en_steps = en.get("etapes") or []
        for i, row in enumerate(rows):
            if i < len(en_steps):
                s = en_steps[i]
                txt = s if isinstance(s, str) else (s or {}).get("txt", "")
                if txt:
                    row["txt"] = txt
        if en.get("attendu"):
            out["attendu"] = en["attendu"]
    out["etapes"] = rows
    return out


def localized_cases(lang=None):
    """CASES entierement localisee (voir localized_case)."""
    return [localized_case(c, lang) for c in CASES]


def category_label(code, lang=None):
    """Libelle affichable d'une categorie, dans la langue demandee."""
    if lang is None:
        from core.i18n import get_language
        lang = get_language()
    if lang == "en":
        from core.test_protocol_en import CATEGORY_LABELS_EN
        if code in CATEGORY_LABELS_EN:
            return CATEGORY_LABELS_EN[code]
    return dict(CATEGORIES).get(code, code)


def case_has_commands(case):
    """Au moins une etape copiable dans le cas ?"""
    return any(row["cmds"] for row in localized_case(case)["etapes"])


def protocol_to_markdown(lang=None) -> str:
    """Rend le protocole complet en Markdown (utilise par le dialogue
    Aide > Protocole de test de l'application et pour l'export). Structure :
    une section par categorie, un sous-titre par cas (id, titre, revision),
    prerequis / etapes numerotees (commandes copiables en sous-puce code) /
    resultat attendu."""
    from core.i18n import t
    grouped = cases_by_category()
    lines = [f"# {t('protocol.md_title', to_lang=lang)}", ""]
    total = sum(len(cases) for cases in grouped.values())
    lines.append(f"**{total} {t('protocol.md_cases', to_lang=lang)}** "
                 f"-- {t('protocol.md_generated', to_lang=lang)}")
    lines.append("")
    for code, _label in CATEGORIES:
        cases = grouped[code]
        if not cases:
            continue
        lines.append(f"## {category_label(code, lang)}")
        lines.append("")
        for raw in cases:
            case = localized_case(raw, lang)
            rev = f" (rev {raw['rev']})" if raw.get("rev") else ""
            lines.append(f"### {case['id']} - {case['titre']}{rev}")
            lines.append("")
            if case.get("pre"):
                lines.append(f"- {t('protocol.md_prereq', to_lang=lang)} : {case['pre']}")
            for i, row in enumerate(case["etapes"], 1):
                lines.append(f"- {t('protocol.md_step', to_lang=lang)} {i} : {row['txt']}")
                for cmd in row["cmds"]:
                    lines.append(f"  - `{cmd}`")
            lines.append(f"- **{t('protocol.md_expected', to_lang=lang)}** : {case['attendu']}")
            lines.append("")
    return chr(10).join(lines) + chr(10)
