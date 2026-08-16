"""
Tutoriels integres a l'application -- pas a pas, avec navigation par etapes.

Concu pour etre facilement etendu : chaque tutoriel est un objet Tutorial (titre,
resume court affiche dans la liste, liste ordonnee d'etapes). Pour ajouter un nouveau
tutoriel, il suffit de construire un nouvel objet Tutorial (voir TUTORIAL_CREATE_BLOCK
ci-dessous comme modele) et de l'ajouter a la liste TUTORIALS en bas de ce fichier --
aucune modification necessaire cote interface graphique, qui lit cette liste
dynamiquement.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class TutorialStep:
    title: str
    content_html: str  # HTML simple (gras, listes, code) -- affiche dans un QTextBrowser


@dataclass
class Tutorial:
    id: str
    title: str
    summary: str
    steps: List[TutorialStep] = field(default_factory=list)


# ============================================================================
# Tutoriel : Creer un bloc, pas a pas
# ============================================================================
TUTORIAL_CREATE_BLOCK = Tutorial(
    id="create_block",
    title="Creer un bloc, pas a pas",
    summary="Du choix du point de depart jusqu'au test en jeu -- tout ce qu'il faut "
            "savoir pour ajouter un nouveau bloc a un scenario sans rien oublier.",
    steps=[
        TutorialStep(
            title="Avant de commencer",
            content_html="""
<p>Un bloc est une entree dans <b>BlocksConfig.ecf</b> -- le fichier qui definit
absolument tous les blocs du jeu (blocs de construction, portes, tourelles,
constructeurs, panneaux solaires...). Un <b>item</b> (objet d'inventaire, arme,
ressource) fonctionne sur le meme principe mais vit dans <b>ItemsConfig.ecf</b> --
tout ce tutoriel s'applique aux deux, seul le fichier change.</p>

<p><b>Travaille toujours sur la copie de travail</b>, jamais directement sur les
fichiers sources -- c'est le seul endroit modifiable de l'application, et elle reste
comparable au scenario d'origine a tout moment (menu Fichier > Comparer deux
scenarios...).</p>

<p><b>Recommandation avant de commencer une session de creation de bloc</b> :
fais une sauvegarde du scenario (Fichier > Sauvegarder un scenario) si tu n'en as
pas de recente. Un bloc mal forme peut empecher le jeu de charger -- avoir un point
de retour rapide t'evite de tout reconstruire a la main.</p>
""",
        ),
        TutorialStep(
            title="Etape 1 -- Choisir son point de depart",
            content_html="""
<p>Deux approches possibles :</p>

<p><b>A. Dupliquer un bloc existant proche</b> (recommande dans la grande majorite des
cas) -- trouve dans Scenario A (ou B) un bloc qui ressemble deja a ce que tu veux
(meme materiau, meme famille de forme), clic droit dessus dans l'arbre, puis
"Dupliquer avec un nouvel Id...". Tu herites automatiquement de toutes ses
proprietes correctement formees -- texture, categorie, forme, collision -- et tu
n'as plus qu'a ajuster ce qui doit changer.</p>

<p><b>B. Partir de zero</b> avec le bouton "+ Bloc" de la copie de travail -- utile
seulement si aucun bloc existant ne s'en approche. Dans ce cas, prevois de renseigner
TOUTES les proprietes des etapes suivantes toi-meme : rien n'est herite.</p>

<p style="color:#b02a2a"><b>Piege frequent (verifie et corrige plusieurs fois pendant
la construction de cette application) :</b> dans le fichier vanille du jeu, beaucoup
de blocs existants sont eux-memes des <b>patchs</b> (genre <code>+Block</code>, avec
un <code>+</code>) qui completent une entree de base invisible, geree par le moteur
du jeu. Si tu dupliques un tel bloc, le nouveau doit <b>toujours</b> perdre ce
<code>+</code> -- un patch sans rien a patcher est ignore par le jeu ou provoque un
plantage au chargement. L'application s'en occupe desormais automatiquement a chaque
duplication, mais garde ce principe en tete si tu crees une entree a la main dans un
editeur externe.</p>
""",
        ),
        TutorialStep(
            title="Etape 2 -- L'identification : Id ou Name ?",
            content_html="""
<p>Chaque bloc a besoin d'un identifiant unique, sous une des deux formes :</p>

<p><b><code>Id: 1234</code></b> -- un numero. Les blocs numerotes doivent rester
<b>sous 2048</b> (le jeu refuse categoriquement tout nouvel Id au-dessus, avec un
message d'erreur explicite au chargement).</p>

<p><b><code>Name: MonBloc</code></b> (sans Id du tout) -- pour tout bloc cree
au-dela de la limite des 2048, c'est la SEULE facon valide de l'identifier. C'est
d'ailleurs la methode la plus simple et la plus sure pour un bloc entierement
nouveau.</p>

<p style="color:#b02a2a"><b>Regles a ne jamais enfreindre :</b></p>
<ul>
<li>Ne <b>jamais</b> changer l'Id ou le Name d'un bloc <b>deja existant</b> -- ca
casse toutes les parties/blueprints deja sauvegardees qui l'utilisent.</li>
<li>Un nouvel Id doit etre <b>libre</b> (non utilise ailleurs dans le fichier).
L'application vérifie ça automatiquement lors de la duplication et te propose des
Id libres.</li>
<li>Le <code>Ref:</code> d'un bloc (heritage de proprietes depuis un autre bloc) ne
peut pointer que vers un bloc <b>deja defini plus haut</b> dans le fichier, jamais
plus bas.</li>
</ul>
""",
        ),
        TutorialStep(
            title="Etape 3 -- Les proprietes essentielles",
            content_html="""
<p>Un bloc de construction minimal a besoin de :</p>

<p><b>Material</b> -- determine l'apparence de base ET les points de vie/degats
(concrete, metal, hullarmored, wood...). Verifie MaterialConfig.ecf pour la liste
complete disponible dans ton scenario.</p>

<p><b>Category</b> -- range le bloc dans le bon groupe du menu de construction
(BuildingBlocks, Devices, Cockpits...).</p>

<p><b>Texture</b> -- une liste de 6 numeros de texture, dans l'ordre : dessus,
dessous, nord, sud, ouest, est.</p>

<p><b>Mass</b> -- attention, la valeur indiquee correspond a un bloc de 1 metre, le
jeu l'ajuste ensuite automatiquement selon la taille reelle :</p>
<ul>
<li>Petite grille (HV, SV) : masse reelle = valeur x 0.125 (bloc de 0.5m)</li>
<li>Grande grille (BA, CV) : masse reelle = valeur x 8 (bloc de 2m)</li>
</ul>

<p><b>HitPoints</b> -- points de vie du bloc.</p>

<p><b>BlockColor</b> -- couleur RVB, ex: <code>"170,170,170"</code>.</p>

<p style="color:#7c859c"><i>Astuce : le panneau "Voir l'explication des proprietes
de ce fichier" (juste au-dessus de la barre de recherche quand tu ouvres
BlocksConfig.ecf) donne un glossaire complet de toutes ces proprietes et bien
d'autres, directement dans l'application.</i></p>
""",
        ),
        TutorialStep(
            title="Etape 4 -- Ou et comment il apparait en jeu",
            content_html="""
<p><b>Group</b> -- regroupe des blocs qui partagent une meme mecanique (ex:
<code>cpgCore</code> pour les Core, <code>cpgSolar</code> pour les panneaux
solaires) -- optionnel pour un bloc de construction simple.</p>

<p><b>ChildBlocks</b> -- liste les <b>variantes de forme</b> de ce bloc (plein,
fin, pente, coin...). Bonne nouvelle : tu n'as <b>pas besoin de creer de nouveaux
modeles 3D</b> pour ca -- le moteur du jeu fournit deja une bibliotheque standard
de formes (accessible par clic droit lors de la pose en jeu) qui s'applique
automatiquement a toute famille de blocs du meme materiau. ChildBlocks se contente
de lister les noms que ces variantes auto-generees porteront.</p>

<p><b>SymType</b> -- type de symetrie de la forme (utile surtout pour les formes en
coin/pente) :</p>
<ul>
<li><code>1</code> : quart de rond (par defaut)</li>
<li><code>2</code> : coin</li>
<li><code>3</code> : mur incline</li>
<li><code>4</code> : coin biseau (rotation par defaut particuliere)</li>
</ul>

<p><b>Shape</b> -- forme de base du bloc.</p>
""",
        ),
        TutorialStep(
            title="Etape 5 -- Le rendre placable et solide",
            content_html="""
<p><b>AllowPlacingAt</b> -- sur quels types de structure ce bloc peut etre pose,
ex: <code>"Base,MS,SS,GV"</code> (Base, petite grille, station spatiale, grande
grille).</p>

<p><b>Place</b> -- comment il se positionne a la pose :</p>
<ul>
<li><code>NoRotation</code> : ne peut pas etre tourne</li>
<li><code>Face</code> : s'oriente automatiquement selon la surface visee</li>
<li><code>Free</code> : pose libre, toutes rotations possibles</li>
</ul>

<p><b>Collide</b> -- quels types d'objets entrent en collision avec ce bloc
(mouvement du joueur, balles, roquettes...). Retirer 'movement' rend le bloc
traversable a pied tout en restant touchable par les armes -- utile pour des
elements decoratifs fins comme des grilles ou du feuillage.</p>

<p><b>IsPhysicsColliders</b> -- collisions physiques fines, parfois desactivees sur
les formes tres minces (rampes fines) pour eviter des comportements etranges.</p>
""",
        ),
        TutorialStep(
            title="Etape 6 -- Le rendre fabricable",
            content_html="""
<p>Un bloc sans recette de craft ne pourra <b>jamais</b> etre construit en jeu (sauf
s'il est purement decoratif/place uniquement dans des POI). La recette vit dans
<b>Templates.ecf</b>, un fichier <b>separe</b> de BlocksConfig.ecf.</p>

<p>Structure d'une recette minimale :</p>
<pre style="background:#f0f0f0; padding:8px; border-radius:4px;">
{ Template Name: MonBloc
  CraftTime: 10
  Target: "BaseC,LargeC,AdvC"
  { Child Inputs
    SteelPlate: 5
    Electronics: 1
  }
}</pre>

<p><b>Target</b> liste les constructeurs capables de le fabriquer (SuitC, SurvC,
SmallC, HoverC, BaseC, LargeC, AdvC...). <b>Le Name de la recette doit correspondre
exactement au Name du bloc.</b></p>

<p style="color:#b02a2a"><b>Piege identique a l'etape 1</b> : si tu t'inspires
d'une recette existante en la dupliquant/copiant a la main, verifie qu'elle n'est
pas en <code>+Template</code> -- un patch orphelin ici provoque exactement le meme
type de plantage (rencontre concretement pendant le developpement de cette
application : le constructeur plante a l'ouverture si sa recette est mal formee de
cette facon).</p>

<p><b>TemplateRoot</b> -- si ton bloc fait partie d'une famille avec mise a niveau
(Upgrade), indique quelle recette utiliser pour le sous-groupe. Le bloc parent n'en
a pas besoin, il utilise toujours la recette portant son propre nom.</p>
""",
        ),
        TutorialStep(
            title="Etape 7 -- Verifier avant de tester en jeu",
            content_html="""
<p>Ne teste jamais directement en jeu sans ces verifications rapides dans
l'application -- elles prennent quelques secondes et evitent le plus gros des
plantages :</p>

<ul>
<li><b>Round-trip automatique</b> : l'application le fait deja a chaque
sauvegarde -- si une erreur de syntaxe existe, elle te sera signalee.</li>
<li><b>Verification > Blocs en attente / References</b> : verifie qu'aucune
reference (Ref:, TemplateRoot...) ne pointe vers un nom introuvable.</li>
<li><b>Relis les proprietes une derniere fois</b> dans le tableau -- une valeur
mal placee (ex: un texte la ou un nombre est attendu) est la cause la plus
frequente de plantage au chargement.</li>
</ul>

<p style="color:#7c859c"><i>Si tu dois tester plusieurs hypotheses sans savoir
laquelle pose probleme, la fonction "Blocs desactives (test)" (clic droit sur un
bloc dans l'arbre) permet de le desactiver temporairement sans le supprimer -- tres
utile pour isoler une cause de plantage par elimination, sans jamais perdre ton
travail.</i></p>
""",
        ),
        TutorialStep(
            title="Etape 8 -- Tester en jeu",
            content_html="""
<p><b>Lance toujours une nouvelle partie de test</b> (jamais ta sauvegarde
principale en premier essai) -- une erreur de configuration peut empecher le
chargement completement.</p>

<p>Si le jeu se lance mais que le bloc ne se comporte pas comme prevu :</p>
<ul>
<li>Ouvre la console en jeu avec la touche <b>` (accent grave)</b> pour voir les
erreurs de chargement en detail.</li>
<li>Verifie que le bloc apparait bien dans le menu de construction, dans la bonne
categorie.</li>
<li>Ouvre <b>tous</b> les constructeurs listes dans <code>Target</code> de sa
recette pour confirmer qu'il y est proposé.</li>
</ul>

<p>Si le jeu plante ou affiche un message d'erreur au chargement, le nom du bloc ou
de la propriete en cause apparait generalement dans le message -- reviens dans
l'application, relis attentivement cette entree precise.</p>
""",
        ),
        TutorialStep(
            title="Recapitulatif -- check-list finale",
            content_html="""
<p>Avant de considerer ton nouveau bloc termine :</p>
<ul>
<li>&#9744; Id (sous 2048) OU Name seul -- jamais les deux regles mélangées</li>
<li>&#9744; Aucun <code>+</code> devant le genre du bloc (sauf s'il patche
reellement une entree existante)</li>
<li>&#9744; Material, Category, Texture, Mass, HitPoints, BlockColor renseignes</li>
<li>&#9744; AllowPlacingAt et Place coherents avec l'usage prevu</li>
<li>&#9744; Recette de craft creee dans Templates.ecf (Name identique, sans
<code>+</code>), avec un Target coherent</li>
<li>&#9744; Verification des references faite dans l'application</li>
<li>&#9744; Testé sur une nouvelle partie de test, console verifiee</li>
</ul>
<p>Une fois tout ça coché, ton bloc est prêt à rejoindre ton scénario.</p>
""",
        ),
    ],
)

TUTORIAL_APP_OVERVIEW = Tutorial(
    id='app_overview',
    title="Prise en main complete de l'application",
    summary="Chaque menu, chaque bouton, chaque fonction -- un tour complet et detaille de tout ce que l'application permet de faire.",
    steps=[
        TutorialStep(
            title="Vue d'ensemble",
            content_html="\n<p>Cette application accompagne la modification de scenarios Empyrion Galactic\nSurvival : lecture et edition des fichiers <b>.ecf</b>, <b>.yaml</b> et <b>.csv</b>,\navec verification de coherence, comparaison de scenarios, sauvegardes, traduction et\nbien plus. Ce tutoriel couvre <b>chaque menu, chaque bouton, chaque fonction</b> de\nl'application, dans l'ordre ou tu les rencontres naturellement.</p>\n\n<p>Trois zones structurent toujours l'interface :</p>\n<ul>\n<li><b>Scenario A</b> (a gauche) -- la source d'origine, en <b>lecture seule</b>,\njamais modifiee</li>\n<li><b>Copie de travail</b> (au centre) -- la seule zone modifiable, c'est ici que\ntout ton travail se fait</li>\n<li><b>Scenario B</b> (a droite, optionnel) -- une deuxieme source de reference,\negalement en lecture seule, utile pour comparer ou fusionner depuis deux scenarios\ndifferents</li>\n</ul>\n",
        ),
        TutorialStep(
            title='Demarrer : nouveau projet ou projet recent',
            content_html='\n<p>Au lancement, une fenetre propose la liste de tes <b>projets recents</b> --\nselectionne-en un puis clique <b>"Ouvrir la selection"</b>, ou clique\n<b>"Nouveau projet..."</b> pour en creer un.</p>\n\n<p><b>Fichier > Nouveau projet...</b> ouvre un formulaire avec trois champs :</p>\n<ul>\n<li><b>Scenario A</b> (obligatoire) -- le dossier du scenario source</li>\n<li><b>Scenario B</b> (optionnel) -- un deuxieme scenario de reference</li>\n<li><b>Destination de la copie de travail</b> -- ou sera creee la copie modifiable\n(ne doit pas deja exister)</li>\n</ul>\n\n<p><b>Fichier > Projets recents...</b> rouvre la meme liste a tout moment pour\nretourner sur un projet deja configure.</p>\n\n<p style="color:#7c859c"><i>Astuce : la copie de travail est une VRAIE copie\nphysique sur le disque, independante du scenario source -- tu peux la deplacer,\nla sauvegarder, ou meme la supprimer sans jamais affecter la source.</i></p>\n',
        ),
        TutorialStep(
            title='Le Scenario B : ouvrir, changer, retirer',
            content_html="\n<p>Le Scenario B est <b>entierement optionnel</b> et peut etre gere a tout moment,\nmeme en cours de travail sur un projet deja ouvert :</p>\n\n<ul>\n<li><b>Fichier > Ouvrir un Scenario B...</b> -- apparait quand aucun Scenario B\nn'est actif ; choisis un dossier pour l'activer</li>\n<li><b>Fichier > Changer le Scenario B...</b> -- le meme menu, renomme\nautomatiquement une fois un Scenario B actif ; demande confirmation avant de\nremplacer l'actuel</li>\n<li><b>Fichier > Retirer le Scenario B</b> -- desactive le panneau B (grise tant\nqu'aucun B n'est actif) ; ta copie de travail n'est jamais affectee par ce retrait</li>\n</ul>\n\n<p>Utilite typique : comparer une ancienne et une nouvelle version d'un meme\nscenario, ou piocher des elements dans deux scenarios differents pour ta propre\ncreation.</p>\n",
        ),
        TutorialStep(
            title='Ouvrir un fichier',
            content_html="\n<p><b>Double-clique sur n'importe quel fichier</b> dans l'un des trois panneaux\n(Scenario A, Copie de travail, ou Scenario B) pour l'ouvrir dans un nouvel onglet\nen haut de la fenetre.</p>\n\n<ul>\n<li>Les fichiers ouverts depuis <b>Scenario A ou B</b> s'ouvrent en <b>lecture\nseule</b> (tu peux les consulter, chercher dedans, copier/dupliquer vers la copie\nde travail, mais jamais les modifier directement)</li>\n<li>Les fichiers ouverts depuis la <b>copie de travail</b> s'ouvrent en mode\n<b>editable</b>, avec tous les outils de modification disponibles</li>\n</ul>\n\n<p>Types de fichiers geres : <b>.ecf</b> (blocs, items, config), <b>.yaml/.yml</b>\n(playfields, planetes...), <b>.csv</b> (traductions, tables de donnees),\n<b>.txt</b> (texte brut, lecture simple).</p>\n\n<p>Un onglet deja ouvert pour un fichier se selectionne au lieu de s'ouvrir en\ndouble si tu re-double-cliques dessus.</p>\n",
        ),
        TutorialStep(
            title='La barre superieure : langue et annuler global',
            content_html='\n<p><b>Bouton de langue</b> (FR/EN, en haut a droite) -- bascule toute l\'interface\nde l\'application entre francais et anglais instantanement, sans perdre ton travail\nen cours.</p>\n\n<p><b>Annuler la derniere action</b> (bouton global, pas celui d\'un onglet) --\nannule la derniere operation de type <i>fusion/duplication/copie depuis Scenario A\nou B</i> vers la copie de travail. C\'est different du bouton "Annuler (Ctrl+Z)"\npresent dans chaque onglet editable, qui n\'annule que les modifications DANS ce\nfichier precis. Le bouton global reste grise tant qu\'aucune fusion/duplication n\'a\neu lieu depuis Scenario A/B.</p>\n',
        ),
        TutorialStep(
            title="Editer un fichier ECF -- l'arbre des blocs",
            content_html='\n<p>L\'arbre a gauche de chaque onglet ECF liste tous les blocs/items du fichier.\nClique sur un bloc pour afficher ses proprietes a droite.</p>\n\n<p><b>Groupes de section</b> -- si le fichier source utilise des commentaires de\nseparation (frequent dans Containers.ecf, BlocksConfig.ecf...), l\'arbre affiche des\n<b>en-tetes de categorie</b> en gras (ex: "Gigas", "Dinosaurs") pour naviguer plus\nfacilement dans les tres longs fichiers -- ce sont de simples reperes visuels, pas\ndes blocs cliquables.</p>\n\n<p><b>Etiquettes lisibles</b> -- quand le fichier source annote un bloc juste avant\nlui (ex: <code>## GolemSwamp</code>), ce nom apparait entre parentheses a cote de\nl\'identifiant technique du bloc dans l\'arbre.</p>\n\n<p><b>Recherche</b> -- tape dans la barre "Rechercher :" (par Id, Name, ou\nCustomIcon) puis appuie sur Entree pour sauter au premier resultat ; re-appuie pour\npasser au suivant.</p>\n',
        ),
        TutorialStep(
            title='Editer un fichier ECF -- le tableau de proprietes',
            content_html='\n<p>Une fois un bloc selectionne, ses proprietes s\'affichent a droite sous deux\nformes possibles :</p>\n\n<p><b>Mode liste classique</b> (la grande majorite des blocs) -- une ligne par\npropriete (cle a gauche non editable, valeur a droite editable). Double-clique dans\nla colonne Valeur pour modifier.</p>\n\n<p><b>Mode tableau</b> (structures repetitives type <i>Child Items</i>,\n<i>LootGroups</i>...) -- detecte automatiquement quand un bloc contient une suite\nd\'entrees numerotees (Name_0, Name_1... ou Item_0, DamageMultiplier_1...) : affiche\nalors un vrai tableau avec une colonne par parametre, bien plus lisible qu\'une\nlongue liste plate. Le bouton "+ Ligne" (au lieu de "+ Propriete") s\'active\nautomatiquement dans ce mode -- voir l\'etape dediee plus loin.</p>\n\n<p>Chaque cellule modifiee est surlignee pour te rappeler ce qui a change dans la\nsession en cours.</p>\n',
        ),
        TutorialStep(
            title='Editer un fichier ECF -- ajouter un bloc ou une propriete',
            content_html='\n<p><b>+ Bloc</b> -- cree un nouveau bloc entierement vide dans le fichier ouvert ;\ndemande le genre (Block, Item...), puis tu renseignes toi-meme toutes les\nproprietes voulues.</p>\n\n<p><b>+ Propriete</b> -- ajoute une propriete au bloc actuellement selectionne.\nTu peux taper plusieurs paires en une seule fois en respectant la syntaxe du\nfichier (ex: <code>AlienParts04, param1: 0.6, param2: "1,3"</code>) pour les\nregrouper sur la meme ligne comme le fait le jeu -- important pour les structures\nou l\'ordre/le regroupement compte.</p>\n\n<p><b>+ Ligne</b> (visible seulement en mode tableau) -- ajoute une nouvelle\nentree a une structure repetitive (Child Items...) via un petit formulaire dedie\n: <b>Type</b> (Name/Group/Item selon ce que le fichier utilise deja), <b>Valeur</b>,\net un champ par colonne de parametre detectee. La numerotation (Name_6, Item_3...)\net la position (juste apres la derniere entree du meme type) sont calculees\nautomatiquement -- tu n\'as jamais a y reflechir toi-meme.</p>\n',
        ),
        TutorialStep(
            title='Editer un fichier ECF -- supprimer et desactiver un bloc',
            content_html='\n<p><b>Supprimer</b> (clic droit sur un bloc dans l\'arbre, ou sur une propriete\ndans le tableau) -- retire definitivement l\'element du fichier. Une confirmation\nest toujours demandee pour un bloc entier.</p>\n\n<p><b>Desactiver ce bloc (test)</b> (clic droit sur un bloc) -- alternative plus\nsure a la suppression : commente le bloc <b>a sa position exacte</b> dans le\nfichier (jamais deplace en fin de fichier, important pour l\'ordre de chargement),\nsans le supprimer. Tres utile pour tester "et si ce bloc precis causait mon\nprobleme ?" sans perdre son contenu.</p>\n\n<p><b>Bouton "Blocs desactives (test)"</b> -- ouvre la liste de tous les blocs\nactuellement desactives dans ce fichier, avec un bouton <b>"Reactiver"</b> par\nentree pour les remettre exactement comme avant.</p>\n',
        ),
        TutorialStep(
            title="Editer un fichier ECF -- filtrer et le panneau d'explication",
            content_html='\n<p><b>Filtrer par propriete...</b> -- affiche uniquement les blocs possedant (ou\nnon) certaines proprietes precises que tu choisis -- utile pour retrouver\nrapidement "tous les blocs qui ont une texture X" dans un tres gros fichier.</p>\n\n<p><b>Panneau "Voir l\'explication des proprietes de ce fichier"</b> (juste sous le\nnom du fichier, au-dessus de la recherche) -- replie par defaut, il s\'ouvre sur un\nglossaire clarifie en francais des commentaires techniques d\'en-tete du fichier.\nDix-sept fichiers (BlocksConfig.ecf, ItemsConfig.ecf, Templates.ecf, Factions.ecf,\nTokenConfig.ecf...) ont un glossaire fait main ; pour les autres, un bouton\n<b>"Traduire automatiquement en francais"</b> traduit le texte original a la\ndemande.</p>\n',
        ),
        TutorialStep(
            title='Editer un fichier YAML',
            content_html="\n<p>Le fonctionnement general ressemble a l'ECF, adapte a la structure YAML (cles\nimbriquees, listes) :</p>\n\n<ul>\n<li><b>+ Entree</b> / <b>Supprimer l'entree selectionnee</b></li>\n<li>Selectionne une entree dans l'arbre : sa valeur s'affiche dans une zone de\ntexte a droite, modifiable</li>\n<li><b>Appliquer cette valeur</b> -- valide le texte tape. Note : cliquer\ndirectement sur <b>Enregistrer</b> ou changer de ligne applique aussi\nautomatiquement le texte en attente, tu ne peux plus perdre une modification par\noubli</li>\n</ul>\n\n<p><b>Chaines entre guillemets sur plusieurs lignes</b> -- le parseur gere\ncorrectement les valeurs qui s'etendent sur plusieurs lignes avec des lignes\nvides au milieu (frequent pour les descriptions de playfield) : une ligne vide a\nl'interieur des guillemets devient un vrai retour a la ligne, pour un affichage\ncorrect en jeu.</p>\n",
        ),
        TutorialStep(
            title='Editer un fichier CSV -- les bases',
            content_html='\n<p><b>Recherche</b> -- tape un texte puis choisis la portee dans le menu\nderoulant "dans :" (une colonne precise, ou toutes) ; Entree pour sauter au\nresultat suivant. Clic droit sur un <b>en-tete de colonne</b> pour lancer\ndirectement une recherche limitee a cette colonne.</p>\n\n<p><b>+ Ligne</b> / <b>Ligne selectionnee</b> (suppression) -- gestion classique\ndes lignes.</p>\n\n<p><b>Presse-papier</b> (clic droit sur une ou plusieurs cellules) : Copier,\nCouper, Coller, Effacer le contenu -- fonctionne sur une selection multiple,\ncomme dans un tableur.</p>\n\n<p><b>Annuler / Enregistrer</b> comme partout ailleurs.</p>\n',
        ),
        TutorialStep(
            title="La traduction -- vue d'ensemble et memoire",
            content_html="\n<p>Toutes les fonctions de traduction (decrites dans les etapes suivantes)\npartagent une <b>memoire de traduction</b> commune, entierement automatique et\ninvisible : des qu'un texte est traduit une fois vers une langue donnee, la meme\ntraduction est reutilisee instantanement (sans nouvel appel reseau) si ce texte\nexact revient ailleurs -- plus rapide, et garantit que le meme mot ne se traduit\njamais differemment a deux endroits du meme fichier.</p>\n\n<p>Toutes les traductions en lot passent par un <b>tableau de revue</b> avant\nd'etre appliquees : rien n'est jamais ecrit dans le fichier sans validation. Tu\npeux decocher une ligne, ou modifier directement le texte propose avant de\nvalider.</p>\n",
        ),
        TutorialStep(
            title='La traduction -- cellule par cellule et rapide',
            content_html='\n<p><b>Clic droit sur une cellule > Traduire vers > (choisir une langue)</b> --\ntraduit cette seule cellule, montre un apercu avant/apres, et propose de\nremplacer soit la cellule elle-meme, soit la colonne correspondant a la langue\ncible sur la meme ligne si elle existe deja dans le fichier.</p>\n\n<p><b>Bouton "Traduire"</b> (barre d\'outils) -- traduit directement la cellule ou\nla selection courante vers ta <b>langue par defaut</b> (configurable dans Options\n> "Langue de traduction par defaut..."), sans passer par le sous-menu de choix de\nlangue a chaque fois. Si plusieurs cellules sont selectionnees, bascule\nautomatiquement sur la traduction en lot (etape suivante).</p>\n',
        ),
        TutorialStep(
            title='La traduction -- en lot et combler les langues manquantes',
            content_html='\n<p><b>Selection multiple + clic droit > "Traduire la selection vers..."</b> --\nselectionne plusieurs cellules (comme dans un tableur), choisis une langue : une\nbarre de progression traduit chaque cellule, puis le tableau de revue s\'ouvre\npour tout valider d\'un coup (ou cellule par cellule).</p>\n\n<p><b>Bouton "Combler les langues manquantes..."</b> -- pour un fichier entier :\nchoisis une colonne source (deja remplie) et une colonne cible (a completer), et\nl\'application scanne TOUT le fichier pour ne traduire que les cellules vraiment\nvides -- celles deja remplies restent intactes.</p>\n\n<p style="color:#b02a2a"><b>Sur un tres gros lot</b> (des milliers de cellules),\nsi le service de traduction se bloque temporairement (limite d\'usage), l\'arret\nest <b>automatique apres 5 echecs consecutifs</b>, avec un message clair -- les\ntraductions deja reussies restent disponibles pour revue, jamais perdues. Les\nechecs sont surlignes en rouge et decoches par defaut dans le tableau, impossible\nde les appliquer par erreur.</p>\n',
        ),
        TutorialStep(
            title='Rechercher et remplacer (CSV)',
            content_html='\n<p><b>Bouton "Rechercher et remplacer..."</b> -- pour corriger un texte repete a\nplusieurs endroits (typiquement une traduction automatique approximative) :</p>\n\n<ul>\n<li><b>Rechercher</b> / <b>Remplacer par</b> -- les deux textes</li>\n<li><b>Dans la colonne</b> -- une colonne precise, ou toutes</li>\n<li><b>Respecter la casse</b> -- coche pour distinguer majuscules/minuscules</li>\n<li><b>Mot entier seulement</b> -- coche pour eviter de toucher un mot qui\ncontient seulement le texte cherche comme fragment (ex: "Dos" ne touchera pas\n"Dossier" avec cette option)</li>\n</ul>\n\n<p>Comme pour la traduction, chaque correspondance trouvee passe par le meme\ntableau de revue avant d\'etre appliquee -- jamais de remplacement a l\'aveugle.</p>\n',
        ),
        TutorialStep(
            title='Copier ou dupliquer depuis Scenario A ou B',
            content_html='\n<p>Sur les panneaux Scenario A et B (lecture seule), le clic droit propose deux\nfamilles d\'actions differentes :</p>\n\n<p><b>Copier/fusionner</b> (fichier, dossier, bloc, ligne, entree) -- combine le\ncontenu source dans la copie de travail, en fusionnant avec ce qui existe deja si\nbesoin. <b>Desactive par defaut</b> (trop de cas particuliers pour etre fiable a\n100%) -- reactivable dans Options > "Autoriser la fusion" si tu en as vraiment\nbesoin.</p>\n\n<p><b>Dupliquer</b> (fichier, bloc, ligne, entree) -- <b>toujours disponible</b>,\ncree systematiquement une copie <b>independante</b> (nouvel Id/nouveau nom), sans\njamais ecraser quoi que ce soit. C\'est l\'action recommandee dans l\'immense\nmajorite des cas -- voir aussi le tutoriel "Creer un bloc, pas a pas" pour le\ndetail complet de la duplication de bloc.</p>\n\n<p>Chaque duplication/fusion (si activee) est annulable via le bouton global\n"Annuler la derniere action" en haut de la fenetre.</p>\n',
        ),
        TutorialStep(
            title='Verifier les references et les blocs en attente',
            content_html="\n<p><b>Verification > Verifier les references</b> -- controle que chaque\n<code>Ref:</code>, <code>TemplateRoot</code> et reference similaire pointe bien\nvers un nom qui existe reellement dans le fichier -- signale toute reference\ncassee avant que le jeu ne le fasse a ta place au chargement.</p>\n\n<p><b>Verification > Blocs en attente</b> -- lors d'une fusion, si un conflit\nd'Id est detecte (meme Id deja utilise par un autre bloc), le bloc en conflit est\nautomatiquement commente plutot que d'ecraser l'existant. Cette fenetre liste tous\nces blocs en attente, avec une comparaison detaillee (bloc actuel vs bloc en\nattente) et des suggestions d'Id libres pour l'activer proprement.</p>\n",
        ),
        TutorialStep(
            title='Sauvegardes de scenario et de partie',
            content_html="\n<p><b>Fichier > Sauvegarder un scenario (avant mise a jour)...</b> -- garde une\ncopie complete d'un scenario avant qu'une mise a jour Steam Workshop ne l'ecrase\nen place, pour pouvoir comparer l'ancienne et la nouvelle version ensuite.</p>\n\n<p><b>Fichier > Gerer mes sauvegardes de partie...</b> -- meme principe pour tes\nsauvegardes de progression de partie, avec possibilite de <b>restaurer</b> (une\nsauvegarde de securite est automatiquement creee avant toute restauration).</p>\n\n<p>Dans les deux cas, le gestionnaire de sauvegardes propose : <b>Sauvegarder\nmaintenant</b>, <b>Restaurer</b>, <b>Ouvrir le dossier</b>, <b>Supprimer</b> (avec\nconfirmation), et pour les scenarios uniquement, <b>Comparer avec...</b> qui\nouvre directement l'outil de comparaison avec cette sauvegarde pre-remplie.</p>\n",
        ),
        TutorialStep(
            title='Comparer deux scenarios',
            content_html="\n<p><b>Fichier > Comparer deux scenarios...</b> -- independant du projet\nactuellement ouvert, permet de comparer <b>n'importe quels deux dossiers de\nscenario</b> :</p>\n\n<ul>\n<li>Choisis les dossiers A (reference) et B (mise a jour), clique\n<b>Comparer</b></li>\n<li>Resultat : arbre colore par statut (ajoute / retire / modifie / identique),\navec le detail precis des changements pour le fichier selectionne (comparaison\nbloc par bloc pour l'ECF, ligne par ligne pour le CSV, cle par cle pour le\nYAML)</li>\n<li><b>Afficher aussi les fichiers identiques</b> -- coche pour voir la liste\ncomplete, pas seulement ce qui a change</li>\n<li><b>Exporter le rapport...</b> -- sauvegarde un fichier texte complet de la\ncomparaison</li>\n</ul>\n",
        ),
        TutorialStep(
            title='Extraire les proprietes du scenario',
            content_html='\n<p><b>Fichier > Extraire les proprietes du scenario...</b> -- parcourt tous les\nfichiers .ecf d\'une source (copie de travail, Scenario A ou B) et construit un\nglossaire de travail complet :</p>\n\n<ul>\n<li>Chaque propriete rencontree, avec son nombre d\'occurrences, les fichiers\nconcernes, quelques exemples de valeurs vues, et une description automatique\nquand la propriete est reconnue sans ambiguite</li>\n<li>Les cles numerotees (Name_0, Name_1...) sont regroupees sous une seule entree\ngenerique (Name_N) plutot que de noyer le resultat de milliers de quasi-doublons</li>\n<li>Une colonne <b>"Valeur cible"</b> vide, a completer toi-meme au fil de ta\nreflexion de conception</li>\n</ul>\n\n<p>Le resultat est un fichier CSV que l\'application propose d\'ouvrir\nimmediatement, directement modifiable comme n\'importe quel autre CSV.</p>\n',
        ),
        TutorialStep(
            title='Reparer les permissions et resoudre les blocages',
            content_html='\n<p><b>Fichier > Reparer les permissions de la copie de travail</b> -- si la copie\nde travail devient soudainement impossible a modifier ou a supprimer (Windows\ndemande une "autorisation" meme pour ton propre compte), c\'est generalement du a\nun attribut lecture-seule herite de la source (frequent avec les scenarios\ninstalles sous Program Files). Ce bouton deverrouille tout instantanement.</p>\n\n<p style="color:#7c859c"><i>Note : chaque sauvegarde de fichier tente desormais\nautomatiquement ce deverrouillage en arriere-plan avant d\'ecrire -- ce bouton\nn\'est donc utile que dans de rares cas residuels ou meme cette auto-reparation ne\nsuffit pas.</i></p>\n',
        ),
        TutorialStep(
            title="Les options de l'application",
            content_html='\n<p>Le menu <b>Options</b> regroupe les reglages globaux, valables pour tous les\nprojets :</p>\n\n<ul>\n<li><b>Nom pour les annotations...</b> -- ton nom, utilise dans les commentaires\nautomatiques ajoutes lors d\'une modification (ex: <code># Modifie par Toi</code>)</li>\n<li><b>Annoter les modifications automatiquement</b> (case a cocher) -- active\nou desactive ces commentaires automatiques</li>\n<li><b>Autoriser la fusion</b> (case a cocher, <b>desactivee par defaut</b>) --\nvoir l\'etape "Copier ou dupliquer depuis Scenario A ou B"</li>\n<li><b>Langue de traduction par defaut...</b> -- la langue utilisee par le\nbouton "Traduire" rapide</li>\n</ul>\n',
        ),
        TutorialStep(
            title='Le menu Aide : tutoriels et wiki de reference',
            content_html="\n<p><b>Aide > Tutoriels...</b> -- ouvre cette meme fenetre de tutoriels pas a pas,\naccessible a tout moment.</p>\n\n<p><b>Aide > Wiki de l'application (fonctions)...</b> -- un document de reference\ncomplet, organise par theme, a consulter en cherchant plutot qu'en suivant un\nparcours guide -- complementaire aux tutoriels : viens ici pour un parcours\nd'apprentissage complet une premiere fois, reviens au wiki ensuite pour\nretrouver rapidement un detail precis.</p>\n\n<p><b>Aide > Wiki Empyrion (proprietes, fichiers, structure)...</b> -- meme\nprincipe, mais pour la documentation du <b>jeu lui-meme</b> (structure des\nfichiers ECF/YAML, conventions, pieges connus) plutot que de l'application.</p>\n",
        ),
        TutorialStep(
            title='Recapitulatif -- ou trouver quoi',
            content_html='\n<p>Un dernier reperage rapide, par intention :</p>\n<ul>\n<li><b>"Je veux commencer un nouveau projet"</b> -> Fichier > Nouveau projet...</li>\n<li><b>"Je veux comparer deux versions"</b> -> Fichier > Comparer deux\nscenarios...</li>\n<li><b>"Je veux ajouter/modifier un bloc"</b> -> ouvre le fichier ECF dans la\ncopie de travail, utilise + Bloc / + Propriete / la duplication depuis Scenario\nA</li>\n<li><b>"Je veux traduire mes textes"</b> -> ouvre le CSV, utilise le bouton\nTraduire, la traduction en lot, ou "Combler les langues manquantes..."</li>\n<li><b>"Mon jeu plante au chargement"</b> -> Verification > Verifier les\nreferences, et la fonction "Desactiver ce bloc (test)" pour isoler la cause par\nelimination</li>\n<li><b>"Ma copie de travail est bloquee"</b> -> Fichier > Reparer les\npermissions</li>\n<li><b>"Je veux documenter mon scenario"</b> -> Fichier > Extraire les\nproprietes du scenario...</li>\n</ul>\n<p>Tu connais maintenant l\'integralite de l\'application -- bon travail sur ton\nscenario !</p>\n',
        ),
    ],
)

TUTORIALS: List[Tutorial] = [
    TUTORIAL_CREATE_BLOCK,
    TUTORIAL_APP_OVERVIEW,
    # Ajoute de futurs tutoriels ici -- voir TUTORIAL_CREATE_BLOCK comme modele.
]
