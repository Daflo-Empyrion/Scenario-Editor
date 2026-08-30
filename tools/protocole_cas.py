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
   unique dans la bonne categorie. Dans une session reprise d'une anterieure,
   il apparait automatiquement comme NOUVEAU, non testé.

2. MODIFICATION D'UN CAS EXISTANT (comportement change, etapes differentes)
   -> modifier le dict ET incrementer "rev" (absent = rev 1). Dans toute
   session reprise, le cas est remis a non testé et marque "A RETESTER" :
   c'est ce qui garantit qu'un test vert sur l'ancien code ne masque pas
   une regression.

3. CAS OBSOLETE -> le supprimer ; sa ligne disparait des sessions suivantes
   (les anciennes sessions le conservent pour l'historique).

Champs d'un cas :
- "id"      : PREFIXE-numero, unique, PREFIXE = categorie
- "cat"     : code categorie (voir CATEGORIES)
- "titre"   : intitule court du test
- "pre"     : (facultatif) preconditions / preparation
- "etapes"  : liste ordonnee d'etapes a suivre (pas-a-pas)
- "attendu" : resultat attendu, observable et verifiable
- "rev"     : (facultatif) revision du cas -- incrementer a chaque modification
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
]

CASES = [
    # ---------------------------------------------------------------- PROJ
    {
        "id": "PROJ-001", "cat": "PROJ",
        "titre": "Nouveau projet : creation standard depuis le Scenario A",
        "pre": "Un dossier de scenario Empyrion valide est disponible (Scenario A).",
        "etapes": [
            "Fichier > Nouveau projet...",
            "Renseigne uniquement le Scenario A et la destination de la copie de travail (inexistante).",
            "Valide.",
        ],
        "attendu": "La copie de travail est creee et selectionnee ; le panneau central est rempli ; A reste intact.",
    },
    {
        "id": "PROJ-002", "cat": "PROJ",
        "titre": "Nouveau projet : avec Scenario B optionnel",
        "etapes": [
            "Fichier > Nouveau projet...",
            "Renseigne Scenario A, un Scenario B different, et une destination neuve.",
            "Valide.",
        ],
        "attendu": "Les trois panneaux sont remplis ; B est en lecture seule.",
    },
    {
        "id": "PROJ-003", "cat": "PROJ",
        "titre": "Nouveau projet : refus si la destination existe deja",
        "etapes": ["Fichier > Nouveau projet...", "Choisis comme destination un dossier DEJA existant.", "Valide."],
        "attendu": "Message d'erreur clair, aucune ecriture nulle part, aucun dossier ecrase.",
    },
    {
        "id": "PROJ-004", "cat": "PROJ",
        "titre": "Copie conforme : tous les fichiers du scenario sont recopies",
        "etapes": [
            "Note le nombre de fichiers du Scenario A (explorateur Windows).",
            "Cree un nouveau projet depuis ce scenario.",
            "Compare le nombre de fichiers de la copie de travail.",
        ],
        "attendu": "Meme arborescence, memes fichiers (pas seulement .ecf/.yaml/.csv).",
    },
    {
        "id": "PROJ-005", "cat": "PROJ",
        "titre": "Projets recents : proposition au demarrage",
        "pre": "Au moins un projet a deja ete cree.",
        "etapes": ["Lance l'application.", "Observe la fenetre de demarrage."],
        "attendu": "La liste des projets recents est proposee ; Ouvrir la selection recharge le projet.",
    },
    {
        "id": "PROJ-006", "cat": "PROJ",
        "titre": "Projets recents : reouverture SANS recopie (travail intact)",
        "pre": "Un projet existant avec une modification non enregistree... enregistree, donc visible sur disque.",
        "etapes": [
            "Ouvre un projet, modifie un fichier, enregistre, ferme l'application.",
            "Relance, reouvre le meme projet via Projets recents.",
        ],
        "attendu": "La modification precedente est toujours la : la copie de travail n'a PAS ete recopiee depuis A.",
    },
    {
        "id": "PROJ-007", "cat": "PROJ",
        "titre": "Trois panneaux : A/B lecture seule, centre editable",
        "etapes": [
            "Double-clique un meme fichier .ecf dans A, puis dans la copie de travail.",
            "Compare les boutons disponibles dans chaque onglet.",
        ],
        "attendu": "A : lecture seule (pas de + Bloc/Enregistrer) ; copie de travail : outils d'edition actifs.",
    },
    {
        "id": "PROJ-008", "cat": "PROJ",
        "titre": "Arborescence disque exacte dans les 3 panneaux",
        "etapes": ["Compare l'arbre du panneau A avec l'explorateur Windows (dossiers et sous-dossiers)."],
        "attendu": "Arborescence identique, aucune categorisation artificielle inventee.",
    },
    {
        "id": "PROJ-009", "cat": "PROJ",
        "titre": "Changer le Scenario B en cours de route",
        "pre": "Un projet avec un Scenario B actif.",
        "etapes": ["Fichier > Changer le Scenario B...", "Choisis un autre dossier.", "Confirme le remplacement."],
        "attendu": "Confirmation demandee ; apres validation, le panneau B affiche le nouveau scenario.",
    },
    {
        "id": "PROJ-010", "cat": "PROJ",
        "titre": "Retirer le Scenario B",
        "etapes": ["Fichier > Retirer le Scenario B."],
        "attendu": "Le panneau B se grise/disparait ; la copie de travail n'est jamais affectee.",
    },
    {
        "id": "PROJ-011", "cat": "PROJ",
        "titre": "Ouvrir un Scenario B quand aucun n'est actif",
        "etapes": ["Sur un projet sans B : Fichier > Ouvrir un Scenario B...", "Choisis un dossier."],
        "attendu": "Le panneau B s'active avec le contenu du dossier.",
    },
    {
        "id": "PROJ-012", "cat": "PROJ",
        "titre": "Premier lancement : ecran de langue (une seule fois)",
        "pre": "Supprimer (ou renommer) le dossier ~/.empyrion_editor pour simuler un premier lancement.",
        "etapes": ["Lance l'application.", "Choisis une langue.", "Relance l'application."],
        "attendu": "L'ecran de langue apparait une seule fois ; le choix est applique immediatement et persiste.",
    },
    {
        "id": "PROJ-013", "cat": "PROJ",
        "titre": "Tutoriel automatique au demarrage + ne plus afficher",
        "etapes": [
            "Au lancement, laisse le tutoriel s'ouvrir.",
            "Coche \"Ne plus afficher automatiquement au demarrage\", ferme.",
            "Relance l'application.",
        ],
        "attendu": "Le tutoriel ne s'ouvre plus ; il reste accessible via Aide > Tutoriels...",
    },
    {
        "id": "PROJ-014", "cat": "PROJ",
        "titre": "Bouton FR/EN : bascule sans perdre le travail",
        "pre": "Un projet ouvert avec un onglet modifie non enregistre.",
        "etapes": ["Clique sur le bouton FR/EN en haut a droite."],
        "attendu": "Toute l'interface bascule de langue ; l'onglet modifie reste ouvert et modifie.",
    },

    # ---------------------------------------------------------------- OPEN
    {
        "id": "OPEN-001", "cat": "OPEN",
        "titre": "Double-clic fichier copie de travail : onglet editable",
        "etapes": ["Double-clique BlocksConfig.ecf dans la copie de travail."],
        "attendu": "Onglet prefixe ✎, edition possible.",
    },
    {
        "id": "OPEN-002", "cat": "OPEN",
        "titre": "Double-clic fichier Scenario A/B : lecture seule",
        "etapes": ["Double-clique le meme fichier dans le panneau A."],
        "attendu": "Onglet prefixe 🔒, aucune modification possible.",
    },
    {
        "id": "OPEN-003", "cat": "OPEN",
        "titre": "Onglet deja ouvert : reselection au lieu du doublon",
        "etapes": ["Double-clique deux fois le meme fichier."],
        "attendu": "Le deuxieme double-clic selectionne l'onglet existant au lieu d'en ouvrir un second.",
    },
    {
        "id": "OPEN-004", "cat": "OPEN",
        "titre": "Fermeture d'un onglet (croix)",
        "etapes": ["Ferme un onglet avec sa croix."],
        "attendu": "L'onglet se ferme ; le fichier sur disque n'est pas touche.",
    },
    {
        "id": "OPEN-005", "cat": "OPEN",
        "titre": "Recherche dans l'arbre ECF (Id / Name / CustomIcon)",
        "etapes": [
            "Tape un Id connu dans la barre Rechercher, Entree.",
            "Rappuie sur Entree.",
        ],
        "attendu": "Saut au premier resultat, puis au suivant a chaque Entree.",
    },
    {
        "id": "OPEN-006", "cat": "OPEN",
        "titre": "Groupes de section affiches en en-tetes",
        "pre": "Fichier avec separateurs ### (ex: Containers.ecf vanilla).",
        "etapes": ["Ouvre le fichier, observe l'arbre."],
        "attendu": "Les titres de section apparaissent en tete de groupe, non cliquables.",
    },
    {
        "id": "OPEN-007", "cat": "OPEN",
        "titre": "Etiquettes ## affichees a cote du bloc",
        "pre": "Fichier avec etiquettes ## avant un bloc.",
        "etapes": ["Ouvre le fichier, repere un bloc annote."],
        "attendu": "Le nom de l'etiquette apparait entre parentheses a cote de l'identifiant du bloc.",
    },
    {
        "id": "OPEN-008", "cat": "OPEN",
        "titre": "En-tete de fichier extrait et affiche",
        "etapes": ["Ouvre BlocksConfig.ecf, ouvre le panneau d'explication du fichier."],
        "attendu": "La documentation technique d'en-tete est affichee lisible (sans #).",
    },
    {
        "id": "OPEN-009", "cat": "OPEN",
        "titre": "Fichier non supporte : message clair",
        "etapes": ["Double-clique un fichier d'extension exotique dans la copie de travail."],
        "attendu": "Message indiquant que le type n'est pas supporte, pas de plantage.",
    },
    {
        "id": "OPEN-010", "cat": "OPEN",
        "titre": "Fichier .txt : lecture simple",
        "etapes": ["Double-clique un .txt du scenario."],
        "attendu": "Onglet texte, contenu fidele, lecture seule ou edition basique fonctionnelle.",
    },
    {
        "id": "OPEN-011", "cat": "OPEN",
        "titre": "Titre d'onglet : marqueur de modification (✎ *)",
        "etapes": ["Modifie une valeur dans un onglet sans enregistrer.", "Observe le titre de l'onglet."],
        "attendu": "Le titre passe de ✎ a ✎ * ; il revient a ✎ apres enregistrement.",
    },

    # ---------------------------------------------------------------- ECF
    {
        "id": "ECF-001", "cat": "ECF",
        "titre": "Affichage des proprietes en mode liste",
        "etapes": ["Selectionne un bloc classique dans l'arbre ECF."],
        "attendu": "Une ligne par propriete, cle a gauche / valeur editable a droite.",
    },
    {
        "id": "ECF-002", "cat": "ECF",
        "titre": "Detection automatique du mode tableau (Child Items)",
        "pre": "Un bloc avec Name_0/Name_1... (ex: containers vanilla).",
        "etapes": ["Selectionne un bloc a structure repetitive."],
        "attendu": "Affichage en tableau (une colonne par parametre), bouton + Ligne actif.",
    },
    {
        "id": "ECF-003", "cat": "ECF",
        "titre": "Modification d'une valeur + surlignage de session",
        "etapes": ["Double-clique une valeur, modifie-la, valide."],
        "attendu": "La cellule modifiee est surlignee ; le titre d'onglet passe en modifie.",
    },
    {
        "id": "ECF-004", "cat": "ECF",
        "titre": "Enregistrement Ctrl+S + round-trip fidele",
        "etapes": [
            "Modifie une valeur puis Ctrl+S.",
            "Relance python cli/verifier_parser_ecf.py <fichier> sur le fichier modifie.",
        ],
        "attendu": "Enregistrement OK ; le verificateur confirme la fidelite (round-trip) du fichier.",
    },
    {
        "id": "ECF-005", "cat": "ECF",
        "titre": "Ctrl+Z de l'onglet : annulation d'une modification",
        "etapes": ["Modifie une valeur, Ctrl+Z."],
        "attendu": "La valeur d'origine revient, le marqueur de modification disparait.",
    },
    {
        "id": "ECF-006", "cat": "ECF",
        "titre": "Annotation automatique des modifications",
        "pre": "Options > Annoter les modifications automatiquement active, nom configure.",
        "etapes": ["Modifie une valeur, enregistre, ouvre le fichier brut dans un editeur externe."],
        "attendu": "La ligne modifiee porte un commentaire '# original: <ancien> -- Mod par <nom>'.",
    },
    {
        "id": "ECF-007", "cat": "ECF",
        "titre": "Desactivation des annotations automatiques",
        "etapes": ["Decoche Options > Annoter les modifications...", "Modifie + enregistre + inspecte le fichier."],
        "attendu": "Aucun commentaire ajoute.",
    },
    {
        "id": "ECF-008", "cat": "ECF",
        "titre": "+ Propriete : ajout simple",
        "etapes": ["Selectionne un bloc, + Propriete, ajoute une paire cle: valeur existant ailleurs dans le fichier."],
        "attendu": "La propriete apparait sur le bloc, groupee avec les proprietes simples.",
    },
    {
        "id": "ECF-009", "cat": "ECF",
        "titre": "+ Propriete : plusieurs paires sur une meme ligne",
        "etapes": ["+ Propriete, saisis plusieurs paires en respectant la syntaxe (ex: 'param1: 0.6, param2: \"1,3\"')."],
        "attendu": "Les paires sont regroupees sur une seule ligne, comme le fait le jeu.",
    },
    {
        "id": "ECF-010", "cat": "ECF",
        "titre": "+ Bloc : choix Id + Name",
        "etapes": ["+ Bloc, choisis Id + Name, renseigne des valeurs libres valides.", "Termine l'assistant."],
        "attendu": "Le bloc est cree avec l'Id et le Name demandes, verifie en direct (limite 8192, doublons).",
    },
    {
        "id": "ECF-011", "cat": "ECF",
        "titre": "+ Bloc : choix Name seul (au-dela de la limite d'Id)",
        "etapes": ["+ Bloc, choisis Name seul, renseigne un Name libre.", "Termine."],
        "attendu": "Bloc cree sans Id, identifie par Name uniquement.",
    },
    {
        "id": "ECF-012", "cat": "ECF",
        "titre": "+ Bloc : tableau de proprietes du fichier + menus deroulants",
        "etapes": ["+ Bloc : observe la liste de proprietes proposees, ouvre un menu deroulant de valeur."],
        "attendu": "Proprietes issues du fichier de travail, triees par usage ; valeurs suggerees = valeurs reelles deja vues.",
    },
    {
        "id": "ECF-013", "cat": "ECF",
        "titre": "+ Bloc : verification d'Id en direct (8192 / doublon)",
        "etapes": ["Dans l'assistant + Bloc, saisis un Id > 8192 puis un Id deja utilise."],
        "attendu": "Erreur visible pour les deux cas, creation impossible tant que l'Id est invalide.",
    },
    {
        "id": "ECF-014", "cat": "ECF",
        "titre": "+ Bloc : proposition du Template associe",
        "pre": "Templates.ecf present dans la copie de travail.",
        "etapes": ["Cree un bloc via + Bloc.", "Accepte la proposition de creer le Template."],
        "attendu": "Un Template de meme Name est cree dans Templates.ecf, ingredients par liste deroulante.",
    },
    {
        "id": "ECF-015", "cat": "ECF",
        "titre": "+ Ligne : numerotation automatique (Name_6 apres Name_5)",
        "pre": "Un bloc en mode tableau avec Name_0..Name_5.",
        "etapes": ["+ Ligne, choisis le type Name, valide."],
        "attendu": "La ligne Name_6 est inseree JUSTE APRES Name_5 (pas en fin de bloc), parametres vides prets.",
    },
    {
        "id": "ECF-016", "cat": "ECF",
        "titre": "+ Ligne : choix du Type parmi les prefixes du fichier",
        "etapes": ["Sur un bloc avec Name_N et Group_N, ouvre + Ligne et observe le choix Type."],
        "attendu": "Le Type propose les prefixes reellement presents du bloc (Name/Group...).",
    },
    {
        "id": "ECF-017", "cat": "ECF",
        "titre": "Suppression d'une propriete",
        "etapes": ["Clic droit sur une propriete > Supprimer."],
        "attendu": "La ligne disparait du bloc (Ctrl+Z la restaure).",
    },
    {
        "id": "ECF-018", "cat": "ECF",
        "titre": "Suppression d'un bloc (confirmation demandee)",
        "etapes": ["Clic droit sur un bloc > Supprimer, confirme."],
        "attendu": "Confirmation affichee ; apres confirmation le bloc disparait de l'arbre et du fichier.",
    },
    {
        "id": "ECF-019", "cat": "ECF",
        "titre": "Desactiver ce bloc (test) : commentaire a position exacte",
        "etapes": ["Clic droit sur un bloc > Desactiver ce bloc (test).", "Inspecte le fichier brut."],
        "attendu": "Le bloc est commente A SA POSITION d'origine (pas deplace en fin de fichier).",
    },
    {
        "id": "ECF-020", "cat": "ECF",
        "titre": "Liste des blocs desactives + reactivation",
        "pre": "Au moins un bloc desactive via ECF-019.",
        "etapes": ["Ouvre la liste des blocs desactives (bouton ou menu).", "Reactifie une entree."],
        "attendu": "Le bloc revient exactement a son etat et sa position d'origine.",
    },
    {
        "id": "ECF-021", "cat": "ECF",
        "titre": "Filtrer par propriete",
        "etapes": ["Filtrer par propriete..., coche une propriete courante (ex: Mass)."],
        "attendu": "L'arbre n'affiche plus que les blocs possedant (ou n'ayant pas) la propriete choisie.",
    },
    {
        "id": "ECF-022", "cat": "ECF",
        "titre": "Panneau d'explication : glossaire fait main",
        "etapes": ["Ouvre BlocksConfig.ecf, deploie le panneau d'explication."],
        "attendu": "Glossaire clarifie en francais (fichier couvert par le glossaire manuel).",
    },
    {
        "id": "ECF-023", "cat": "ECF",
        "titre": "Panneau d'explication : traduction automatique hors glossaire",
        "pre": "Un fichier ECF NON couvert par le glossaire manuel.",
        "etapes": ["Ouvre le panneau d'explication de ce fichier, clique Traduire automatiquement."],
        "attendu": "Le texte original est traduit a la demande (ou erreur claire si traduction desactivee).",
    },
    {
        "id": "ECF-024", "cat": "ECF",
        "titre": "Transformation en masse : choix de la propriete",
        "etapes": ["Transformation en masse..., tape les premieres lettres d'une propriete courante."],
        "attendu": "Autocompletion parmi les cles reellement presentes ; la liste montre le nombre d'occurrences.",
    },
    {
        "id": "ECF-025", "cat": "ECF",
        "titre": "Transformation en masse : les 5 operations",
        "etapes": [
            "Pour chaque operation (Multiplier, Ajouter, Fixer, Plafonner, Arrondir),",
            "applique-la a une propriete sur une petite selection, verifie les valeurs.",
        ],
        "attendu": "Chaque operation produit le resultat mathematique attendu dans le fichier.",
    },
    {
        "id": "ECF-026", "cat": "ECF",
        "titre": "Transformation en masse : apercu complet + colonne Apres editable",
        "etapes": ["Clique Apercu sur un lot.", "Decoche une ligne, modifie la valeur 'Apres' d'une autre, applique."],
        "attendu": "Tableau non tronque ; seules les lignes cochees sont ecrites, avec la valeur 'Apres' eventuellement corrigee.",
    },
    {
        "id": "ECF-027", "cat": "ECF",
        "titre": "Transformation en masse : filtres genre + identites",
        "etapes": ["Applique une transformation avec filtre par genre de bloc, puis avec une liste d'identites."],
        "attendu": "Seuls les blocs correspondant au filtre sont touches.",
    },
    {
        "id": "ECF-028", "cat": "ECF",
        "titre": "Transformation en masse : annulation Ctrl+Z",
        "etapes": ["Applique une transformation, puis Ctrl+Z dans l'onglet."],
        "attendu": "Toutes les valeurs transformees reviennent a leur etat d'avant l'operation.",
    },
    {
        "id": "ECF-029", "cat": "ECF",
        "titre": "Fiche d'entete ECF : traduction de l'en-tete",
        "etapes": ["Dans un onglet ECF, lance la traduction de l'en-tete du fichier (bouton dedie)."],
        "attendu": "En-tete traduit (ou erreur claire si traduction en ligne desactivee).",
    },
    {
        "id": "ECF-030", "cat": "ECF",
        "titre": "Dialogue de fusion ECF (A vers copie) : apercu et rapport",
        "pre": "Options > Autoriser la fusion active.",
        "etapes": ["Clic droit dans A sur un fichier ECF > fusionner vers la copie de travail.", "Lis le rapport de fusion."],
        "attendu": "Rapport clair (ajouts/modifications/conflits) ; la copie de travail reste prioritaire.",
    },
    {
        "id": "ECF-031", "cat": "ECF", "rev": 2,
        "titre": "Tableau de proprietes : liste deroulante sur chaque valeur",
        "pre": "Un fichier ECF ouvert avec plusieurs blocs du meme genre portant la meme propriete (ex: CraftTime).",
        "etapes": ["Selectionne un bloc a gauche, clique la VALEUR d'une propriete a droite.",
                   "Ouvre la liste deroulante, choisis une valeur observee ailleurs dans le fichier.",
                   "Recommence en TAPANT une valeur totalement nouvelle."],
        "attendu": "La cellule de valeur propose les valeurs reellement observees dans le fichier (tri frequence) ; la saisie libre reste possible ; la modification est appliquee au bloc (ligne jaune + compte a l'enregistrement).",
    },

    # ---------------------------------------------------------------- DLG
    {
        "id": "DLG-001", "cat": "DLG",
        "titre": "Ouverture de Dialogues.ecf : navigateur dedie",
        "etapes": ["Double-clique Dialogues.ecf dans la copie de travail."],
        "attendu": "Le navigateur de dialogues s'ajoute a l'edition ECF classique (sans la remplacer).",
    },
    {
        "id": "DLG-002", "cat": "DLG",
        "titre": "Navigation entre dialogues (Next / OptionNext)",
        "etapes": ["Suit les liens Next/OptionNext du navigateur sur plusieurs dialogues."],
        "attendu": "La navigation passe de dialogue en dialogue sans perte de contexte.",
    },
    {
        "id": "DLG-003", "cat": "DLG",
        "titre": "Edition d'un texte de dialogue",
        "etapes": ["Modifie un texte de dialogue, enregistre, inspecte le fichier."],
        "attendu": "Le texte modifie est ecrit fidelement (round-trip), y compris BBCode.",
    },
    {
        "id": "DLG-004", "cat": "DLG",
        "titre": "Coherence dialogues : verif references croisees",
        "etapes": ["Lance la verification des references croisees avec le controle Dialogues actif."],
        "attendu": "Les Next/OptionNext orphelins sont detects (renvoi VERIF-006).",
    },
    {
        "id": "DLG-005", "cat": "DLG",
        "titre": "Round-trip Dialogues.ecf sans modification",
        "etapes": ["Ouvre Dialogues.ecf, enregistre sans rien changer, lance le verificateur ECF sur le fichier."],
        "attendu": "Fichier reproduit a l'identique (aucune difference binaire).",
    },

    # ---------------------------------------------------------------- YAML
    {
        "id": "YAML-001", "cat": "YAML",
        "titre": "YAML generique : arbre + edition de valeur",
        "etapes": ["Ouvre un YAML non-playfield (ex: PlanetShares.xml non -- prendre un YAML simple du scenario).", "Selectionne une entree, modifie la valeur, Appliquer."],
        "attendu": "La valeur modifiee apparait dans l'arbre et dans le YAML brut (dernier onglet).",
    },
    {
        "id": "YAML-002", "cat": "YAML",
        "titre": "+ Entree / Supprimer l'entree selectionnee",
        "etapes": ["Ajoute une entree YAML, puis supprime-la."],
        "attendu": "Les deux operations se refletent dans l'arbre et dans le YAML complet.",
    },
    {
        "id": "YAML-003", "cat": "YAML",
        "titre": "Application automatique du texte en attente",
        "etapes": ["Tape une valeur SANS cliquer Appliquer, puis clique directement Enregistrer.", "Recommence en changeant simplement de ligne."],
        "attendu": "Le texte en attente est applique dans les deux cas : jamais perdu par oubli.",
    },
    {
        "id": "YAML-004", "cat": "YAML",
        "titre": "Chaines multilignes avec lignes vides",
        "pre": "Un playfield avec une Description multiligne.",
        "etapes": ["Modifie une description sur plusieurs lignes avec une ligne vide au milieu, enregistre, verifie en jeu ou dans le YAML brut."],
        "attendu": "La ligne vide devient un vrai retour a la ligne ; l'affichage en jeu reste correct.",
    },
    {
        "id": "YAML-005", "cat": "YAML",
        "titre": "Round-trip YAML fidele",
        "etapes": ["Ouvre un YAML, enregistre sans rien changer, compare avec la version d'avant (ou cli verifier_parser_yaml)."],
        "attendu": "Fichier identique byte-pour-byte.",
    },
    {
        "id": "YAML-006", "cat": "YAML",
        "titre": "Playfield : bascule auto vers l'editeur structure (8 onglets)",
        "etapes": ["Double-clique un playfield.yaml de la copie de travail."],
        "attendu": "Editeur structure : Carte 2D, Ressources, POI, Creatures, Drones/Vaisseaux, Zones de spawn, Effets speciaux, YAML complet.",
    },
    {
        "id": "YAML-007", "cat": "YAML",
        "titre": "Ressources : ajout avec liste deroulante de vrais blocs",
        "etapes": ["Onglet Ressources, + ressource, ouvre la liste deroulante du champ ressource."],
        "attendu": "La liste est peuplee des vrais blocs du scenario (pas de saisie a l'aveugle).",
    },
    {
        "id": "YAML-008", "cat": "YAML",
        "titre": "Ressources : colonne RegenAfter modifiable",
        "etapes": ["Modifie RegenAfter d'une ressource, enregistre, verifie le YAML."],
        "attendu": "La valeur est ecrite au bon endroit.",
    },
    {
        "id": "YAML-009", "cat": "YAML",
        "titre": "POI : modification en tableau",
        "etapes": ["Onglet POI : modifie un champ (ex: nom ou probabilité), enregistre, verifie."],
        "attendu": "Modification ecrite correctement dans la section POI du YAML.",
    },
    {
        "id": "YAML-010", "cat": "YAML",
        "titre": "Creatures : colonne Biome",
        "etapes": ["Onglet Creatures : modifie/filtre le biome d'une creature."],
        "attendu": "Le biome est affiche et modifiable, ecriture correcte.",
    },
    {
        "id": "YAML-011", "cat": "YAML",
        "titre": "Drones / Vaisseaux : tableau fonctionnel",
        "etapes": ["Onglet Drones/Vaisseaux : modifie une entree, enregistre, verifie."],
        "attendu": "Modification ecrite correctement.",
    },
    {
        "id": "YAML-012", "cat": "YAML",
        "titre": "Zones de spawn : tableau fonctionnel",
        "etapes": ["Onglet Zones de spawn : modifie une entree, enregistre, verifie."],
        "attendu": "Modification ecrite correctement.",
    },
    {
        "id": "YAML-013", "cat": "YAML",
        "titre": "Effets speciaux : tableau fonctionnel",
        "etapes": ["Onglet Effets speciaux : modifie une entree, enregistre, verifie."],
        "attendu": "Modification ecrite correctement.",
    },
    {
        "id": "YAML-014", "cat": "YAML",
        "titre": "YAML complet : dernier onglet partage le document",
        "etapes": ["Modifie une valeur dans un onglet structure, puis ouvre l'onglet YAML complet."],
        "attendu": "Le YAML brut reflete la modification (meme document en memoire).",
    },
    {
        "id": "YAML-015", "cat": "YAML",
        "titre": "Playfield : Ctrl+Z de l'onglet",
        "etapes": ["Modifie une valeur d'un onglet structure, Ctrl+Z."],
        "attendu": "La valeur d'origine revient dans la vue structure ET le YAML complet.",
    },
    {
        "id": "YAML-016", "cat": "YAML",
        "titre": "Ressources : suppression d'une ressource",
        "etapes": ["Supprime une ressource du tableau, enregistre, verifie le YAML."],
        "attendu": "La ligne est retiree proprement de la section Resources.",
    },
    {
        "id": "YAML-017", "cat": "YAML",
        "titre": "space*.yaml reconnu comme playfield",
        "etapes": ["Double-clique un fichier space*.yaml."],
        "attendu": "Bascule vers l'editeur structure comme pour playfield*.yaml.",
    },
    {
        "id": "YAML-018", "cat": "YAML",
        "titre": "YAML : round-trip apres edition structuree",
        "etapes": ["Modifie via un onglet structure, enregistre, lance cli/verifier_parser_yaml.py sur le fichier."],
        "attendu": "Le verificateur confirme la fidelite du YAML.",
    },

    # ---------------------------------------------------------------- MAP
    {
        "id": "MAP-001", "cat": "MAP",
        "titre": "Carte 2D : affichage des entites positionnables",
        "etapes": ["Ouvre un playfield, onglet Carte 2D."],
        "attendu": "POI fixes, points de depart joueur, patrouilles de drones visibles a leurs positions.",
    },
    {
        "id": "MAP-002", "cat": "MAP",
        "titre": "Glisser-deposer un POI fixe + ecriture YAML",
        "etapes": ["Deplace un POI fixe sur la carte, enregistre, verifie le YAML (Position X/Z)."],
        "attendu": "Les nouvelles coordonnees sont ecrites dans la section du POI.",
    },
    {
        "id": "MAP-003", "cat": "MAP",
        "titre": "Filtres par genre d'entite + zoom",
        "etapes": ["Active/desactive les filtres de la carte, zoome a la molette."],
        "attendu": "Les filtres masquent/affichent les genres ; le zoom fonctionne sans decalage.",
    },
    {
        "id": "MAP-004", "cat": "MAP",
        "titre": "Entites sans position : pas d'invention",
        "pre": "Un playfield avec ressources spatiales ou POI aleatoires en chaine.",
        "etapes": ["Observe ces entrees sur la carte / dans la legende."],
        "attendu": "Elles n'ont volontairement PAS de position affichee (aucune coordonnee inventee).",
    },
    {
        "id": "MAP-005", "cat": "MAP",
        "titre": "Inspecteur de POI : statistiques par POI",
        "etapes": ["Bouton Inspecteur de POI... au-dessus du tableau POI."],
        "attendu": "Fenetre non modale listant les POI aleatoires avec quantite et drones estimes.",
    },
    {
        "id": "MAP-006", "cat": "MAP",
        "titre": "Inspecteur de POI : agregation par faction + export",
        "etapes": ["Bascule la vue par faction, clique Exporter."],
        "attendu": "Total de drones par faction coherent ; l'export ecrit un fichier texte complet.",
    },
    {
        "id": "MAP-007", "cat": "MAP",
        "titre": "Carte de la galaxie : localisation auto + affichage",
        "etapes": ["Fichier > Carte de la galaxie (Sectors.yaml)..."],
        "attendu": "Systemes affiches ; violet pour roles speciaux, orange pour classes spectrales.",
    },
    {
        "id": "MAP-008", "cat": "MAP",
        "titre": "Carte de la galaxie : curseur d'inclinaison Y",
        "etapes": ["Augmente progressivement le curseur Inclinaison (axe Y)."],
        "attendu": "Les systemes se decalent selon leur Y reel, separant ceux qui se chevauchaient.",
    },
    {
        "id": "MAP-009", "cat": "MAP",
        "titre": "Carte de la galaxie : lecture seule",
        "etapes": ["Tente de deplacer un systeme a la souris."],
        "attendu": "Aucune edition involontaire (lecture seule assumee, documentee).",
    },

    # ---------------------------------------------------------------- CSV
    {
        "id": "CSV-001", "cat": "CSV",
        "titre": "Ouverture CSV copie de travail : tableau editable",
        "etapes": ["Double-clique Localization.csv de la copie de travail."],
        "attendu": "Tableau editable, colonnes fideles au fichier.",
    },
    {
        "id": "CSV-002", "cat": "CSV",
        "titre": "CSV Scenario A : lecture seule + copie de ligne",
        "etapes": ["Ouvre le CSV depuis A, clic droit sur une ligne > copier vers la copie de travail."],
        "attendu": "La ligne est copiee dans le CSV de la copie de travail (ou fusionnee par cle).",
    },
    {
        "id": "CSV-003", "cat": "CSV",
        "titre": "+ Ligne / suppression de ligne",
        "etapes": ["Ajoute une ligne, la remplit, la supprime."],
        "attendu": "Les deux operations fonctionnent et s'enregistrent correctement.",
    },
    {
        "id": "CSV-004", "cat": "CSV",
        "titre": "Presse-papier multi-cellules",
        "etapes": ["Selectionne plusieurs cellules, Copier, colle ailleurs ; testez aussi Couper et Effacer."],
        "attendu": "Comportement tableur : la selection multiple est respectee.",
    },
    {
        "id": "CSV-005", "cat": "CSV",
        "titre": "Recherche avec portee (colonne / toutes)",
        "etapes": ["Recherche un texte avec portee 'toutes', puis limite a une colonne.", "Entree pour encherainer."],
        "attendu": "Les resultats respectent la portee ; Entree passe au suivant.",
    },
    {
        "id": "CSV-006", "cat": "CSV",
        "titre": "Clic droit en-tete : recherche limitee a la colonne",
        "etapes": ["Clic droit sur un en-tete de colonne, lance une recherche."],
        "attendu": "La recherche est pre-limitee a cette colonne.",
    },
    {
        "id": "CSV-007", "cat": "CSV",
        "titre": "Rechercher et remplacer avec revue",
        "etapes": ["Rechercher et remplacer... : remplace un texte present plusieurs fois.", "Passe en revue les correspondances."],
        "attendu": "Chaque correspondance est listee, decochable, jamais de remplacement a l'aveugle.",
    },
    {
        "id": "CSV-008", "cat": "CSV",
        "titre": "Remplacer : respect de la casse et mot entier",
        "etapes": ["Active Respecter la casse puis Mot entier, teste sur un mot cible et son derive (ex: Dos/Dossier)."],
        "attendu": "Les options filtrent correctement les correspondances.",
    },
    {
        "id": "CSV-009", "cat": "CSV",
        "titre": "Round-trip CSV fidele (fins de ligne preservees)",
        "etapes": ["Ouvre un CSV, enregistre sans rien changer, compare les octets avant/apres."],
        "attendu": "Fichier identique (lineterminator et structure preserves).",
    },
    {
        "id": "CSV-010", "cat": "CSV",
        "titre": "Ctrl+Z onglet CSV",
        "etapes": ["Modifie une cellule, Ctrl+Z."],
        "attendu": "La valeur d'origine revient.",
    },
    {
        "id": "CSV-011", "cat": "CSV",
        "titre": "Cellules multilignes affichees correctement",
        "pre": "Un CSV avec des cellules contenant des retours a la ligne.",
        "etapes": ["Ouvre le fichier, observe les cellules multilignes."],
        "attendu": "Le contenu est fidele, l'edition ne casse pas la structure du fichier.",
    },
    {
        "id": "CSV-012", "cat": "CSV",
        "titre": "Enregistrement : BOM preserve si present",
        "pre": "Un CSV commencant par un BOM.",
        "etapes": ["Ouvre + enregistre le fichier, verifie les 3 premiers octets."],
        "attendu": "Le BOM d'origine est conserve.",
    },

    # ---------------------------------------------------------------- TRAD
    {
        "id": "TRAD-001", "cat": "TRAD",
        "titre": "Memoire de traduction : reutilisation instantanee",
        "etapes": ["Traduis une cellule.", "Traduis une AUTRE cellule contenant exactement le meme texte."],
        "attendu": "La deuxieme traduction est instantanee (aucun appel reseau) et identique.",
    },
    {
        "id": "TRAD-002", "cat": "TRAD",
        "titre": "Clic droit > Traduire vers > langue : apercu avant/apres",
        "etapes": ["Clic droit sur une cellule > Traduire vers > une langue."],
        "attendu": "Apercu avant/apres propose avant tout remplacement.",
    },
    {
        "id": "TRAD-003", "cat": "TRAD",
        "titre": "Remplacement dans la colonne de la langue cible",
        "pre": "Le CSV a une colonne de la langue cible.",
        "etapes": ["Traduis une cellule dont la ligne a une cellule vide dans la colonne cible."],
        "attendu": "La traduction va dans la colonne cible, la cellule source reste intacte.",
    },
    {
        "id": "TRAD-004", "cat": "TRAD",
        "titre": "Bouton Traduire rapide : langue par defaut",
        "etapes": ["Configure la langue par defaut dans Options, clique le bouton Traduire."],
        "attendu": "Traduction directe vers la langue configuree, sans sous-menu.",
    },
    {
        "id": "TRAD-005", "cat": "TRAD",
        "titre": "Traduction en lot : progression + tableau de revue",
        "etapes": ["Selectionne plusieurs cellules, clic droit > Traduire la selection vers...", "Laisse finir, passe la revue, applique."],
        "attendu": "Barre de progression SANS gel de l'interface ; revue avant application ; echecs en rouge decoches.",
    },
    {
        "id": "TRAD-006", "cat": "TRAD",
        "titre": "Revue : decocher une ligne / editer le texte propose",
        "etapes": ["Dans un lot, decoche une ligne et modifie le texte propose d'une autre avant d'appliquer."],
        "attendu": "Seules les lignes cochees sont appliquees, avec le texte corrige.",
    },
    {
        "id": "TRAD-007", "cat": "TRAD",
        "titre": "Arret automatique apres 5 echecs consecutifs",
        "pre": "Reseau coupe ou traduction en ligne indisponible.",
        "etapes": ["Lance un gros lot avec le reseau coupe."],
        "attendu": "Arret automatique apres 5 echecs, message clair, traductions deja reussies conservees pour revue.",
    },
    {
        "id": "TRAD-008", "cat": "TRAD",
        "titre": "Combler les langues manquantes : vides seulement",
        "etapes": ["Bouton Combler les langues manquantes..., choisis source/cible, lance."],
        "attendu": "Seules les cellules cible vides sont traduites ; les remplies restent intactes.",
    },
    {
        "id": "TRAD-009", "cat": "TRAD",
        "titre": "Protection BBCode et placeholders",
        "pre": "Une cellule avec [b]...[/b] et {PlayerName} ou %s.",
        "etapes": ["Traduis cette cellule."],
        "attendu": "Balises et placeholders restent EXACTEMENT identiques dans le resultat.",
    },
    {
        "id": "TRAD-010", "cat": "TRAD",
        "titre": "Lot en arriere-plan : interface restee fluide",
        "etapes": ["Pendant un lot de traduction, deplace la fenetre, ouvre un menu, redimensionne."],
        "attendu": "L'interface reagit immediatement (pas de gel pendant les requetes).",
    },
    {
        "id": "TRAD-011", "cat": "TRAD",
        "titre": "Annulation d'un lot en cours",
        "etapes": ["Lance un lot, clique Annuler dans la barre de progression."],
        "attendu": "Le lot s'arrete entre deux cellules ; les traductions faites restent en revue.",
    },
    {
        "id": "TRAD-012", "cat": "TRAD",
        "titre": "Reseau indisponible : erreur claire et bornee",
        "pre": "Reseau coupe (ou pare-feu bloquant).",
        "etapes": ["Tente une traduction cellule unique, puis un lot."],
        "attendu": "Erreur explicite en ~15 s max (pas de gel indefini) ; le lot s'arrete proprement.",
    },
    {
        "id": "TRAD-013", "cat": "TRAD",
        "titre": "Traduction en ligne desactivee : refus clair, memoire OK",
        "etapes": ["Decoche Options > Traduction en ligne.", "Tente une traduction NOUVELLE, puis un texte DEJA traduit."],
        "attendu": "Nouvelle traduction refusee avec message PRIVACY.md ; le texte en memoire reste utilisable.",
    },
    {
        "id": "TRAD-014", "cat": "TRAD",
        "titre": "Memoire persistee : survit au redemarrage",
        "etapes": ["Traduis un texte, ferme l'application, relance, retraduis le meme texte."],
        "attendu": "Traduction reutilisee depuis la memoire (instantanee).",
    },
    {
        "id": "TRAD-015", "cat": "TRAD",
        "titre": "ECF : traduction d'une propriete via menu contextuel",
        "etapes": ["Dans un onglet ECF, clic droit sur une valeur textuelle > traduire."],
        "attendu": "Apercu avant/apres puis remplacement correct.",
    },
    {
        "id": "TRAD-016", "cat": "TRAD",
        "titre": "Memoire corrompue : recuperation sans plantage",
        "pre": "Corrompre volontairement ~/.empyrion_editor/translation_memory.json (texte invalide).",
        "etapes": ["Lance l'application et traduis un texte."],
        "attendu": "Aucun plantage : la memoire repart de zero et se reconstruit (fichier reecrit atomiquement).",
    },

    # ---------------------------------------------------------------- FUS
    {
        "id": "FUS-001", "cat": "FUS",
        "titre": "Dupliquer un bloc depuis Scenario A",
        "etapes": ["Clic droit sur un bloc dans A > Dupliquer avec un nouvel Id...", "Choisis un Id propose."],
        "attendu": "Le bloc apparait dans la copie de travail, identique au bloc source sauf l'Id.",
    },
    {
        "id": "FUS-002", "cat": "FUS",
        "titre": "Duplication : suggestions d'Ids libres",
        "etapes": ["Dans la fenetre de duplication, observe les Id proposes."],
        "attendu": "Les Id proposes sont libres (aucun conflit existant) et sous la limite du jeu.",
    },
    {
        "id": "FUS-003", "cat": "FUS",
        "titre": "Duplication multi-variantes (ChildBlocks)",
        "pre": "Un bloc avec plusieurs variantes ChildBlocks.",
        "etapes": ["Duplique le bloc avec ses variantes via la fenetre dediee."],
        "attendu": "Les variantes sont dupliquees avec numerotation coherente.",
    },
    {
        "id": "FUS-004", "cat": "FUS",
        "titre": "Variants : Templates associes proposes",
        "pre": "Le bloc source a un Template dans Templates.ecf.",
        "etapes": ["Duplique les variantes, accepte la creation des Templates associes."],
        "attendu": "Un Template par variante est cree, avec le Name de chaque variante.",
    },
    {
        "id": "FUS-005", "cat": "FUS",
        "titre": "Ajustement des Templates crees (editeur dedie)",
        "etapes": ["Dans la fenetre d'ajustement, modifie le temps de fabrication et les quantites d'ingredients.", "Valide, verifie Templates.ecf."],
        "attendu": "Les valeurs ajustees sont ecrites dans les Templates crees.",
    },
    {
        "id": "FUS-006", "cat": "FUS",
        "titre": "Nom affiche (Localization.csv) : proposition apres duplication",
        "etapes": ["Duplique un bloc/item.", "Accepte la proposition d'ajuster le nom affiche, renseigne FR/EN, valide."],
        "attendu": "Les noms sont ajoutes dans Extras/Localization.csv (ou le CSV du scenario), cles correctes.",
    },
    {
        "id": "FUS-007", "cat": "FUS",
        "titre": "Nom affiche : pre-remplissage source / repli vanilla",
        "etapes": [
            "Duplique un bloc AYANT un nom affiche dans le scenario : verifie le pre-remplissage.",
            "Duplique un bloc vanilla : verifie le repli depuis le pack de localisation integre.",
        ],
        "attendu": "Les champs FR/EN pre-remplis avec le nom source (scenario d'abord, vanilla sinon).",
    },
    {
        "id": "FUS-008", "cat": "FUS",
        "titre": "Dupliquer une ligne CSV depuis Scenario A",
        "etapes": ["Clic droit sur une ligne du CSV de A > dupliquer vers la copie de travail."],
        "attendu": "La ligne arrive dans le CSV cible avec une cle nouvelle/non conflictuelle.",
    },
    {
        "id": "FUS-009", "cat": "FUS",
        "titre": "Dupliquer une entree YAML",
        "etapes": ["Clic droit sur une entree YAML de A > dupliquer."],
        "attendu": "L'entree est copiee dans le YAML de la copie de travail.",
    },
    {
        "id": "FUS-010", "cat": "FUS",
        "titre": "Fusion ECF (option activee) : priorite copie de travail",
        "pre": "Options > Autoriser la fusion activee.",
        "etapes": ["Fusionne un fichier ECF de A deja present (modifie) dans la copie de travail."],
        "attendu": "Les valeurs de la copie de travail sont CONSERVEES ; seuls les ajouts arrivent de A.",
    },
    {
        "id": "FUS-011", "cat": "FUS",
        "titre": "Fusion : garde-fou anti-collision d'Id",
        "etapes": ["Fusionne un bloc dont l'Id existe deja dans la copie avec un Name different."],
        "attendu": "Le bloc entrant est ajoute DESACTIVE en fin de fichier, liste dans Blocs en attente.",
    },
    {
        "id": "FUS-012", "cat": "FUS",
        "titre": "Fusion CSV : completion des cellules vides uniquement",
        "etapes": ["Fusionne un CSV de A dans la copie de travail."],
        "attendu": "Les cellules vides de la copie sont completees depuis A ; les remplies restent inchanges.",
    },
    {
        "id": "FUS-013", "cat": "FUS",
        "titre": "Bouton global Annuler la derniere action",
        "pre": "Une fusion/duplication/copie depuis A/B vient d'etre faite.",
        "etapes": ["Clique le bouton global d'annulation."],
        "attendu": "L'operation est annulee (fichiers restaures) ; les onglets concernes sont fermes/rafraichis.",
    },
    {
        "id": "FUS-014", "cat": "FUS", "rev": 2,
        "titre": "Template sans source : TOUTES les proprietes des autres Templates",
        "pre": "Templates.ecf contient au moins un Template avec une propriete peu commune (ex: OutputCount).",
        "etapes": ["Duplique un bloc SANS Template, accepte la proposition de creer la recette.",
                   "Observe la liste des proprietes proposees dans la fenetre d'ajustement."],
        "attendu": "La liste contient TOUTES les proprietes observees sur les autres Templates du fichier (pas seulement CraftTime/Target), chacune avec sa valeur la plus courante.",
    },
    {
        "id": "FUS-015", "cat": "FUS",
        "titre": "Template sans source : ajout de propriete par liste deroulante",
        "pre": "Fenetre d'ajustement du Template ouverte (bloc sans Template source).",
        "etapes": ["Ouvre la liste deroulante de noms de proprietes, choisis-en une.",
                   "Observe la liste deroulante de valeurs associee, choisis-en une, valide."],
        "attendu": "La propriete est ajoutee au Template cree avec la valeur choisie ; les valeurs proposees sont celles reellement observees dans le fichier, triees par frequence.",
    },
    {
        "id": "FUS-016", "cat": "FUS",
        "titre": "Template sans source : suppression de proprietes pre-remplies",
        "pre": "Fenetre d'ajustement du Template ouverte avec plusieurs proprietes pre-remplies.",
        "etapes": ["Selectionne une propriete, clique 'Retirer la propriete', valide.",
                   "Verifie Templates.ecf apres creation."],
        "attendu": "La propriete retiree N'APPARAIT PAS sur le Template cree ; les autres sont conservees.",
    },
    {
        "id": "FUS-017", "cat": "FUS",
        "titre": "Template : listes deroulantes des valeurs et quantites courantes",
        "pre": "Templates.ecf contient plusieurs Templates avec des valeurs/quantites variees.",
        "etapes": ["Dans la fenetre d'ajustement, ouvre la liste de valeur d'une propriete existante.",
                   "Ouvre la liste de quantite a cote de l'ajout d'ingredient."],
        "attendu": "Les deux listes proposent les valeurs/quantites reellement observees dans le fichier, triees par frequence, avec saisie libre toujours possible.",
    },

    # ---------------------------------------------------------------- VERIF
    {
        "id": "VERIF-001", "cat": "VERIF",
        "titre": "Verifier les references (Ref:) : detection",
        "pre": "Un bloc avec Ref: pointant vers un nom absent (a creer volontairement).",
        "etapes": ["Verification > Verifier les references.", "Lis les resultats."],
        "attendu": "La reference orpheline est signalee avec fichier et bloc.",
    },
    {
        "id": "VERIF-002", "cat": "VERIF",
        "titre": "References : double-clic ouvre le fichier au bloc",
        "etapes": ["Double-clique un resultat de la verification."],
        "attendu": "Le fichier s'ouvre, positionne sur le bloc en cause.",
    },
    {
        "id": "VERIF-003", "cat": "VERIF",
        "titre": "References : Actualiser + Exporter",
        "etapes": ["Corrige un probleme, clique Actualiser sans fermer.", "Puis Exporter."],
        "attendu": "Les resultats se rafraichissent ; l'export ecrit le rapport complet en texte.",
    },
    {
        "id": "VERIF-004", "cat": "VERIF",
        "titre": "References croisees : items/blocs references",
        "etapes": ["Verification > References croisees, active le controle items/blocs, lance."],
        "attendu": "Les references cassées vers Templates/Containers/LootGroups sont detectees.",
    },
    {
        "id": "VERIF-005", "cat": "VERIF",
        "titre": "References croisees : jetons Token:XXXX",
        "etapes": ["Active le controle jetons, lance."],
        "attendu": "Les jetons non definis (ou non utilises) sont signales.",
    },
    {
        "id": "VERIF-006", "cat": "VERIF",
        "titre": "References croisees : dialogues Next/OptionNext",
        "etapes": ["Active le controle dialogues, lance."],
        "attendu": "Les enchainements de dialogues casses sont detectes.",
    },
    {
        "id": "VERIF-007", "cat": "VERIF",
        "titre": "Regles metier : limite d'Id 8192",
        "etapes": ["Valider les regles metier sur un fichier contenant un Id > 8192 (a creer pour le test)."],
        "attendu": "Le depassement est signale.",
    },
    {
        "id": "VERIF-008", "cat": "VERIF",
        "titre": "Regles metier : conteneurs sans VolumeCapacity",
        "etapes": ["Retire VolumeCapacity d'un conteneur qui l'exige, lance la validation."],
        "attendu": "L'incoherence est signalee.",
    },
    {
        "id": "VERIF-009", "cat": "VERIF",
        "titre": "Regles metier : materiaux et HoldType inconnus",
        "etapes": ["Met un Material et un HoldType inventes, lance la validation."],
        "attendu": "Les valeurs non reconnues sont signalees.",
    },
    {
        "id": "VERIF-010", "cat": "VERIF",
        "titre": "Regles metier : virgules non protegees",
        "etapes": ["Ecris une valeur liste non protegee par guillemets (ex: TechTreeNames: Base,Capital Vessel).", "Lance la validation."],
        "attendu": "La virgule non protegee est signalee (risque de decoupage en deux proprietes).",
    },
    {
        "id": "VERIF-011", "cat": "VERIF",
        "titre": "Regles metier : format BlockColor",
        "etapes": ["Met BlockColor: 170,170,170 SANS guillemets, lance la validation."],
        "attendu": "Le format incorrect est signale.",
    },
    {
        "id": "VERIF-012", "cat": "VERIF",
        "titre": "Regles metier : doublons Id/Name",
        "etapes": ["Cree volontairement deux blocs avec le meme Id (fichiers differents du scenario), lance la validation."],
        "attendu": "Le doublon est signale avec les fichiers concernes.",
    },
    {
        "id": "VERIF-013", "cat": "VERIF",
        "titre": "Blocs en attente : liste + comparaison detaillee",
        "pre": "Une fusion a cree un bloc en attente (FUS-011).",
        "etapes": ["Verification > Blocs en attente.", "Compare le bloc actuel et le bloc en attente."],
        "attendu": "Les deux versions sont comparees cote a cote clairement.",
    },
    {
        "id": "VERIF-014", "cat": "VERIF",
        "titre": "Blocs en attente : activation avec nouvel Id",
        "etapes": ["Active un bloc en attente en choisissant un Id libre suggere."],
        "attendu": "Le bloc est active (decommente) avec le nouvel Id ; l'onglet ouvert est recharge.",
    },
    {
        "id": "VERIF-015", "cat": "VERIF",
        "titre": "Bilan de sante du scenario",
        "etapes": ["Lance le bilan de sante (menu Verification)."],
        "attendu": "Vue d'ensemble coherente du scenario, sans faux positif bloquant.",
    },

    # ---------------------------------------------------------------- SAUV
    {
        "id": "SAUV-001", "cat": "SAUV",
        "titre": "Sauvegarder un scenario (avant mise a jour)",
        "etapes": ["Fichier > Sauvegarder un scenario (avant mise a jour)...", "Sauvegarde le scenario A."],
        "attendu": "Une sauvegarde datee apparait dans le gestionnaire.",
    },
    {
        "id": "SAUV-002", "cat": "SAUV",
        "titre": "Gerer mes sauvegardes de partie : liste",
        "etapes": ["Fichier > Gerer mes sauvegardes de partie..."],
        "attendu": "Les sauvegardes de jeu detectees sont listees avec date.",
    },
    {
        "id": "SAUV-003", "cat": "SAUV",
        "titre": "Restaurer une sauvegarde + safety backup auto",
        "etapes": ["Restaure une sauvegarde.", "Verifie qu'un backup de securite a ete cree avant la restauration."],
        "attendu": "La restauration s'applique ; l'etat d'avant est conservable (safety backup).",
    },
    {
        "id": "SAUV-004", "cat": "SAUV",
        "titre": "Supprimer une sauvegarde (confirmation)",
        "etapes": ["Supprime une sauvegarde de test."],
        "attendu": "Confirmation demandee ; suppression effective.",
    },
    {
        "id": "SAUV-005", "cat": "SAUV",
        "titre": "Ouvrir le dossier des sauvegardes",
        "etapes": ["Clique Ouvrir le dossier dans le gestionnaire."],
        "attendu": "L'explorateur s'ouvre au bon dossier.",
    },
    {
        "id": "SAUV-006", "cat": "SAUV",
        "titre": "Comparer avec... une sauvegarde",
        "etapes": ["Sur une sauvegarde de scenario, clique Comparer avec..."],
        "attendu": "L'outil de comparaison s'ouvre pre-rempli avec cette sauvegarde.",
    },
    {
        "id": "SAUV-007", "cat": "SAUV",
        "titre": "Autosave : instantane pendant une edition non enregistree",
        "etapes": ["Modifie un fichier sans enregistrer, attend l'intervalle d'autosave.", "Inspecte le dossier de recuperation (~/.empyrion_editor)."],
        "attendu": "Un instantane du contenu non enregistre existe.",
    },
    {
        "id": "SAUV-008", "cat": "SAUV",
        "titre": "Recuperation au demarrage apres plantage",
        "pre": "Un instantane de recuperation existe (SAUV-007) : ferme l'application brutalement.",
        "etapes": ["Relance l'application."],
        "attendu": "Le dialogue de recuperation propose de restaurer le contenu jamais enregistre.",
    },
    {
        "id": "SAUV-009", "cat": "SAUV",
        "titre": "Nettoyage de l'instantane apres enregistrement",
        "etapes": ["Enregistre le fichier qui avait un instantane (SAUV-007).", "Reinspecte le dossier de recuperation."],
        "attendu": "L'instantane de ce fichier est supprime.",
    },
    {
        "id": "SAUV-010", "cat": "SAUV",
        "titre": "Undo global : restauration fichier",
        "etapes": ["Fais une duplication, annule-la via le bouton global.", "Verifie le fichier."],
        "attendu": "Le fichier retrouve son etat d'avant l'operation.",
    },
    {
        "id": "SAUV-011", "cat": "SAUV",
        "titre": "Ecriture atomique : crash pendant enregistrement",
        "pre": "Test volontairement destructif : sur une COPIE de test uniquement.",
        "etapes": [
            "Lance une sauvegarde d'un gros fichier et tue le processus pendant l'ecriture (gestionnaire des taches).",
            "Relance, ouvre le fichier.",
        ],
        "attendu": "Le fichier est soit l'ancienne version intacte, soit la nouvelle complete -- JAMAIS coupe en deux.",
    },
    {
        "id": "SAUV-012", "cat": "SAUV",
        "titre": "Reparer les permissions de la copie de travail",
        "etapes": ["Passe la copie de travail en lecture seule (attribut Windows).", "Fichier > Reparer les permissions."],
        "attendu": "Les fichiers redeviennent modifiables/supprimables.",
    },

    # ---------------------------------------------------------------- COMP
    {
        "id": "COMP-001", "cat": "COMP",
        "titre": "Comparer deux scenarios : arbre colore",
        "etapes": ["Fichier > Comparer deux scenarios..., choisis A (reference) et B (modifie), Compare."],
        "attendu": "Arbre colore : ajoute / retire / modifie / identique.",
    },
    {
        "id": "COMP-002", "cat": "COMP",
        "titre": "Comparaison : detail par type de fichier",
        "etapes": ["Clique un ECF modifie (detail bloc par bloc), un CSV (ligne/ligne), un YAML (cle/cle)."],
        "attendu": "Le detail des changements est precise pour chaque type.",
    },
    {
        "id": "COMP-003", "cat": "COMP",
        "titre": "Afficher aussi les fichiers identiques",
        "etapes": ["Coche Afficher aussi les fichiers identiques."],
        "attendu": "La liste complete apparait, pas seulement les differences.",
    },
    {
        "id": "COMP-004", "cat": "COMP",
        "titre": "Comparer : exporter le rapport",
        "etapes": ["Exporte le rapport de comparaison."],
        "attendu": "Fichier texte complet ecrit (atomique), lisible.",
    },
    {
        "id": "COMP-005", "cat": "COMP",
        "titre": "Recherche dans tout le scenario",
        "etapes": ["Fichier > Rechercher dans le scenario..., cherche un texte connu."],
        "attendu": "Resultats parcours A/copie/B avec fichiers et localisation.",
    },
    {
        "id": "COMP-006", "cat": "COMP",
        "titre": "Recherche scenario : ouverture du resultat",
        "etapes": ["Double-clique un resultat de recherche."],
        "attendu": "Le fichier s'ouvre a l'endroit trouve.",
    },
    {
        "id": "COMP-007", "cat": "COMP",
        "titre": "Mission PDA : creation guidee",
        "etapes": ["Fichier > Nouvelle mission PDA..., suis l'assistant jusqu'a la creation."],
        "attendu": "Les fichiers PDA sont crees dans le scenario, structure valide.",
    },
    {
        "id": "COMP-008", "cat": "COMP",
        "titre": "Mission PDA : edition d'une mission existante",
        "etapes": ["Ouvre une mission PDA existante, modifie un texte/humeur, enregistre."],
        "attendu": "Modification ecrite fidelement, mission chargeable en jeu.",
    },
    {
        "id": "COMP-009", "cat": "COMP",
        "titre": "Extraction des proprietes du scenario",
        "etapes": ["Fichier > Extraire les proprietes du scenario..."],
        "attendu": "CSV genere : proprietes, occurrences, exemples ; cles numerotees regroupees (Name_N).",
    },

    # ---------------------------------------------------------------- TECH
    {
        "id": "TECH-001", "cat": "TECH",
        "titre": "Arbre technologique : affichage fidele au F3",
        "etapes": ["Fichier > Arbre technologique...", "Compare avec l'ecran F3 du jeu."],
        "attendu": "Colonnes par niveau, categories dans l'ordre du jeu (Base, CV, SV, HV, Misc, Tools, Weapons), Hidden jamais affiche.",
    },
    {
        "id": "TECH-002", "cat": "TECH",
        "titre": "Icones : scenario > pack integre > generique",
        "etapes": [
            "Sans dossier itemicons local : verifie que les icones viennent du pack integre.",
            "Avec SharedData/ItemIcons dans le scenario : verifie qu'une icone personnalisee l'emporte.",
        ],
        "attendu": "Priorite respectee ; a defaut, icone generique (jamais de case vide ni plantage).",
    },
    {
        "id": "TECH-003", "cat": "TECH",
        "titre": "Curseur de niveau joueur simule",
        "etapes": ["Deplace le curseur Niveau du joueur."],
        "attendu": "L'arbre visualise la disponibilite au niveau choisi (comme F3).",
    },
    {
        "id": "TECH-004", "cat": "TECH",
        "titre": "Infobulle d'un noeud",
        "etapes": ["Laisse la souris sur un noeud."],
        "attendu": "Nom localise, niveau requis, cout affiches.",
    },
    {
        "id": "TECH-005", "cat": "TECH",
        "titre": "Double-clic : modification du niveau requis (UnlockLevel)",
        "etapes": ["Double-clique FuelTankMSLarge, passe le niveau de 1 a 3, valide.", "Verifie BlocksConfig.ecf."],
        "attendu": "UnlockLevel: 3 ecrit dans le bon fichier ; l'arbre le montre en direct.",
    },
    {
        "id": "TECH-006", "cat": "TECH",
        "titre": "Double-clic : modification du cout (UnlockCost)",
        "etapes": ["Double-clique le meme noeud, change le cout, valide, verifie le fichier."],
        "attendu": "UnlockCost mis a jour correctement.",
    },
    {
        "id": "TECH-007", "cat": "TECH",
        "titre": "Garde-fou : ecriture refusee si onglet modifie",
        "pre": "BlocksConfig.ecf ouvert dans un onglet AVEC modification non enregistree.",
        "etapes": ["Tente une modification depuis l'arbre technologique."],
        "attendu": "L'ecriture est refusee avec un message clair (aucune desynchronisation).",
    },
    {
        "id": "TECH-008", "cat": "TECH",
        "titre": "Rechargement auto de l'onglet si non modifie",
        "pre": "BlocksConfig.ecf ouvert dans un onglet SANS modification.",
        "etapes": ["Modifie un niveau via l'arbre technologique.", "Observe l'onglet ouvert."],
        "attendu": "L'onglet se recharge automatiquement et montre la nouvelle valeur.",
    },
    {
        "id": "TECH-009", "cat": "TECH",
        "titre": "Deplacer vers une categorie (TechTreeNames)",
        "etapes": ["Clic droit sur un item > Deplacer vers..., choisis une categorie.", "Verifie le fichier (guillemets si plusieurs categories)."],
        "attendu": "TechTreeNames remplace integralement ; valeurs multiples entre guillemets.",
    },
    {
        "id": "TECH-010", "cat": "TECH",
        "titre": "Changer le parent (mode pick) et racine",
        "etapes": ["Clic droit > Changer le parent, clique le nouveau parent dans l'arbre.", "Puis remets le noeud racine."],
        "attendu": "TechTreeParent ecrit vers le nouveau parent ; pour une racine, la propriete est SUPPRIMEE (jamais vide).",
    },
    {
        "id": "TECH-011", "cat": "TECH",
        "titre": "Annulation globale d'une modification d'arbre",
        "etapes": ["Apres une modif (TECH-005..010), clique le bouton global Annuler."],
        "attendu": "Le fichier retrouve son etat anterieur ; l'arbre (recharge) le reflete.",
    },
    {
        "id": "TECH-012", "cat": "TECH",
        "titre": "Previsualisation d'un nouveau bloc dans l'arbre",
        "etapes": ["+ Bloc, clique Previsualiser dans l'arbre technologique...", "Deplace l'icone entouree, choisis niveau/categorie/parent, valide."],
        "attendu": "Le formulaire de creation recupere les choix ; RIEN n'est ecrit par la fenetre de previsualisation elle-meme.",
    },
    {
        "id": "FICHE-001", "cat": "TECH", "rev": 2,
        "titre": "Fiche info : ouverture au DOUBLE-clic sur un bloc",
        "etapes": ["Dans un onglet ECF de la copie de travail, clique UNE fois un bloc de l'arbre.",
                   "Puis double-clique le meme bloc."],
        "attendu": "Un clic simple N'OUVRE PAS la fiche ; seul le double-clic affiche la fiche flottante reproduisant l'affichage F3 du jeu.",
    },
    {
        "id": "FICHE-002", "cat": "TECH", "rev": 4,
        "titre": "Fiche info : display, blocs crees + libelles et descriptions traduits",
        "etapes": ["Compare la fiche d'un bloc connu (ex: FuelTankMSLarge) avec la capture F3 du jeu.",
                   "Cree ou duplique un bloc/Template, ouvre sa fiche AVANT enregistrement.",
                   "Ouvre la fiche d'un bloc du SCENARIO dont la description existe en francais dans Extras/Localization.csv (meme si son en-tete de colonne s'appelle 'French')."],
        "attendu": "Vrais fichiers : memes proprietes que le jeu (regle display stricte). Blocs CREES : toutes leurs proprietes s'affichent, libelles traduits (Temps de fabrication, Quantite produite, Constructeur portable pour les codes Target...) meme si le jeu ne connait pas la cle. DESCRIPTION (Info) lue dans la colonne FR du Localization.csv DU SCENARIO en priorite (alias 'French' reconnus), repli pack vanilla ; ingredients confines a FABRICATION ; aucun double deux-points.",
    },
    {
        "id": "FICHE-003", "cat": "TECH",
        "titre": "Fiche info : rendu BBCode dans les valeurs",
        "pre": "Un bloc avec AllowPlacingAt (codes couleur du jeu) ou un Info: BBCode.",
        "etapes": ["Ouvre sa fiche, observe les valeurs colorees."],
        "attendu": "Les codes [c][RRGGBB]... se rendent visuellement comme en jeu.",
    },
    {
        "id": "FICHE-004", "cat": "TECH", "rev": 2,
        "titre": "Fiche info : deplacement et fermeture (bascule)",
        "etapes": ["Ouvre la fiche d'un bloc par double-clic, deplace-la a la souris.",
                   "Double-clique a nouveau le MEME bloc, puis double-clique un autre bloc."],
        "attendu": "Double-clic sur le bloc deja affiche = la fiche se referme (bascule) ; double-clic sur un autre bloc = elle se rouvre sur celui-ci, sans perdre son deplacement.",
    },

    # ---------------------------------------------------------------- OPT
    {
        "id": "OPT-001", "cat": "OPT",
        "titre": "Options : nom pour les annotations",
        "etapes": ["Options > Nom pour les annotations..., change le nom, modifie une valeur."],
        "attendu": "Les nouvelles annotations portent le nouveau nom.",
    },
    {
        "id": "OPT-002", "cat": "OPT",
        "titre": "Options : autoriser la fusion (activation)",
        "etapes": ["Coche Options > Autoriser la fusion.", "Verifie le menu contextuel des panneaux A/B."],
        "attendu": "Les actions de fusion apparaissent (et disparaissent en decochant).",
    },
    {
        "id": "OPT-003", "cat": "OPT",
        "titre": "Options : langue de traduction par defaut",
        "etapes": ["Change la langue par defaut, utilise le bouton Traduire."],
        "attendu": "La traduction rapide cible la langue configuree.",
    },
    {
        "id": "OPT-004", "cat": "OPT",
        "titre": "Options : theme visuel",
        "etapes": ["Change de theme dans Options, observe l'interface."],
        "attendu": "Le theme s'applique immediatement et persiste au redemarrage.",
    },
    {
        "id": "OPT-005", "cat": "OPT",
        "titre": "i18n : aucune cle brute a l'ecran (FR)",
        "etapes": ["Parcours TOUS les menus et principales fenetres en francais."],
        "attendu": "Aucune chaine du type 'menu.xxx' ou texte manquant ; tout est traduit.",
    },
    {
        "id": "OPT-006", "cat": "OPT",
        "titre": "i18n : aucune cle brute a l'ecran (EN)",
        "etapes": ["Bascule en anglais, parcours les memes ecrans."],
        "attendu": "Tout est traduit en anglais, aucune cle FR visible.",
    },
    {
        "id": "OPT-007", "cat": "OPT",
        "titre": "Aide : wikis FR/EN consultables",
        "etapes": ["Aide > Wiki de l'application, puis Wiki Empyrion, en FR puis EN."],
        "attendu": "Les 4 wikis s'ouvrent dans la langue attendue, contenu a jour.",
    },
    {
        "id": "OPT-008", "cat": "OPT",
        "titre": "Aide : tutoriels + politique de confidentialite + a propos",
        "etapes": ["Ouvre les Tutoriels (les 3), la Politique de confidentialite, et A propos."],
        "attendu": "Tout s'ouvre correctement ; A propos affiche la bonne version et la licence.",
    },
    {
        "id": "OPT-009", "cat": "OPT", "rev": 2,
        "titre": "i18n : boutons standards de Qt dans la langue choisie",
        "etapes": ["En francais, ouvre une boite de confirmation Oui/Non (ex: duplication avec creation de recettes).",
                   "Bascule en anglais (bouton FR/EN) et rouvre la meme boite."],
        "attendu": "Les boutons affichent Oui/Non en francais, Yes/No en anglais (jamais l'inverse ni l'anglais force).",
    },
    {
        "id": "OPT-010", "cat": "OPT",
        "titre": "Audit i18n automatique sans regression",
        "etapes": ["python tools/audit_i18n.py"],
        "attendu": "Code retour 0 : aucune cle t() manquante, aucune cle sans fr/en, aucun litteral affiche en dur dans gui/ et core/.",
    },

    # ---------------------------------------------------------------- CLI
    {
        "id": "CLI-001", "cat": "CLI",
        "titre": "CLI : verifier_parser_ecf (racine et cli/)",
        "etapes": ["python verifier_parser_ecf.py <fichier.ecf>", "python cli/verifier_parser_ecf.py <fichier.ecf>"],
        "attendu": "Les deux points d'entree donnent le meme resultat (round-trip verifie).",
    },
    {
        "id": "CLI-002", "cat": "CLI",
        "titre": "CLI : verifier_parser_yaml",
        "etapes": ["python verifier_parser_yaml.py <fichier.yaml>"],
        "attendu": "Round-trip YAML confirme, ou erreurs claires.",
    },
    {
        "id": "CLI-003", "cat": "CLI",
        "titre": "CLI : verifier_parser_csv",
        "etapes": ["python verifier_parser_csv.py <fichier.csv>"],
        "attendu": "Round-trip CSV confirme.",
    },
    {
        "id": "CLI-004", "cat": "CLI",
        "titre": "CLI : diagnostic_bloc",
        "etapes": ["python diagnostic_bloc.py <BlocksConfig.ecf> <Id connu>"],
        "attendu": "Le bloc est retrouve et affiche, y compris dans les commentaires.",
    },
    {
        "id": "CLI-005", "cat": "CLI",
        "titre": "CLI : detecter_imbrication_anormale",
        "etapes": ["python detecter_imbrication_anormale.py <fichier.ecf>"],
        "attendu": "Aucune fausse detection sur un fichier sain ; detection sur un cas fabrique.",
    },
    {
        "id": "CLI-006", "cat": "CLI",
        "titre": "CLI : diff_ecf",
        "etapes": ["python diff_ecf.py <versionA.ecf> <versionB.ecf> sur deux versions d'un fichier."],
        "attendu": "Blocs ajoutes/supprimes/modifies correctement listes.",
    },
    {
        "id": "CLI-007", "cat": "CLI",
        "titre": "CLI : edit_ecf interactif",
        "etapes": ["python edit_ecf.py <fichier.ecf>, parcours les commandes interactives, quitte sans modifier."],
        "attendu": "Navigation fonctionnelle, aucune modification involontaire.",
    },
    {
        "id": "CLI-008", "cat": "CLI",
        "titre": "CLI : merge_ecf",
        "etapes": ["python merge_ecf.py <sortie.ecf> <source1.ecf> <source2.ecf>", "Verifie la sortie (verifier_parser_ecf)."],
        "attendu": "Fusion conforme aux priorites ; sortie fidele.",
    },
    {
        "id": "CLI-009", "cat": "CLI",
        "titre": "CLI : transform_ecf",
        "etapes": ["python transform_ecf.py sur une copie de test (multiplier une propriete x2)."],
        "attendu": "Transformation appliquee uniquement aux blocs cibles, fichier valide.",
    },

    # ---------------------------------------------------------------- ROBU
    {
        "id": "ROBU-001", "cat": "ROBU",
        "titre": "Fermeture sans modification : directe",
        "etapes": ["Sans aucun onglet modifie, ferme l'application."],
        "attendu": "Fermeture immediate, aucun dialogue.",
    },
    {
        "id": "ROBU-002", "cat": "ROBU",
        "titre": "Fermeture avec onglets modifies : dialogue",
        "etapes": ["Modifie deux fichiers sans enregistrer, ferme l'application."],
        "attendu": "Dialogue listant les fichiers : Enregistrer / Abandonner / Annuler (defaut Enregistrer).",
    },
    {
        "id": "ROBU-003", "cat": "ROBU",
        "titre": "Fermeture : enregistrement en echec annule la sortie",
        "pre": "Rends un fichier ouvert et modifie lecture seule au niveau systeme (verrou externe).",
        "etapes": ["Ferme l'application, choisis Enregistrer."],
        "attendu": "Erreur affichee pour le fichier en echec, la fermeture est ANNULEE, le travail reste ouvert.",
    },
    {
        "id": "ROBU-004", "cat": "ROBU",
        "titre": "Excepthook : dialogue au lieu du crash brutal",
        "etapes": ["Provoque une erreur interne (ou attend une erreur reelle) : l'application doit afficher le dialogue d'erreur."],
        "attendu": "Dialogue avec details depilables et bouton Signaler ; l'application NE FERME PAS.",
    },
    {
        "id": "ROBU-005", "cat": "ROBU",
        "titre": "Verification de mise a jour : silencieuse + manuelle",
        "etapes": ["Lance l'appli (verif auto silencieuse).", "Aide > Verifier les mises a jour (manuelle)."],
        "attendu": "Auto : rien si pas de mise a jour ; manuelle : message meme en cas d'egalite/echec.",
    },
    {
        "id": "ROBU-006", "cat": "ROBU",
        "titre": "Bouton Signaler : formulaire pre-rempli",
        "etapes": ["Clique Signaler, remplis et clique Envoyer."],
        "attendu": "La page GitHub s'ouvre pre-remplie (titre, description, infos techniques, capture a joindre) ; rien n'est envoye automatiquement.",
    },
    {
        "id": "ROBU-007", "cat": "ROBU",
        "titre": "Settings corrompus : demarrage quand meme",
        "pre": "Corrompre ~/.empyrion_editor/settings.json (texte invalide).",
        "etapes": ["Lance l'application, verifie les options, change une option."],
        "attendu": "Demarrage normal (valeurs par defaut), settings reconstruit a la prochaine ecriture.",
    },
    {
        "id": "ROBU-008", "cat": "ROBU",
        "titre": "Projets recents corrompus : liste vide, pas de crash",
        "pre": "Corrompre ~/.empyrion_editor/projects.json.",
        "etapes": ["Lance l'application, ouvre Projets recents."],
        "attendu": "Liste vide ou partielle sans plantage.",
    },

    # ---------------------------------------------------------------- BUILD
    {
        "id": "BUILD-001", "cat": "BUILD",
        "titre": "Installeur : installation propre",
        "pre": "L'installeur de la release a tester.",
        "etapes": ["Execute Setup-EmpyrionScenarioEditor-<version>.exe sur une machine (ou VM) propre.", "Lance l'application depuis le raccourci."],
        "attendu": "Installation sans erreur ; l'application demarre, tout fonctionne (wikis, icones, pak localisation).",
    },
    {
        "id": "BUILD-002", "cat": "BUILD",
        "titre": "Desinstallation propre",
        "etapes": ["Desinstalle via Parametres Windows / panneau de configuration."],
        "attendu": "Desinstallation complete (fichiers programme) ; les donnees utilisateur (~/.empyrion_editor) restent, documente.",
    },
    {
        "id": "BUILD-003", "cat": "BUILD",
        "titre": "CLI embarquee : EmpyrionEditorCLI autonome",
        "etapes": ["Dans une invite, lance EmpyrionEditorCLI.exe avec une commande (ex: verifier-ecf)."],
        "attendu": "Fonctionne sans Python installe, resultats identiques aux scripts.",
    },
    {
        "id": "BUILD-004", "cat": "BUILD",
        "titre": "Verificateur de mise a jour : detection de la release",
        "pre": "La release <version> est publiee sur GitHub.",
        "etapes": ["Avec une version ANTERIEURE installée, lance l'application."],
        "attendu": "La mise a jour <version> est proposee au demarrage (et non proposee si deja a jour).",
    },
]


def cases_by_category():
    """Retourne {code_categorie: [cas...]} dans l'ordre de CATEGORIES."""
    grouped = {code: [] for code, _label in CATEGORIES}
    for case in CASES:
        grouped[case["cat"]].append(case)
    return grouped


if __name__ == "__main__":
    # Petit autotest en ligne de commande : compte les cas par categorie.
    grouped = cases_by_category()
    total = 0
    for code, label in CATEGORIES:
        n = len(grouped[code])
        total += n
        print(f"{label}: {n}")
    print(f"TOTAL: {total} cas")
