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


TUTORIALS: List[Tutorial] = [
    TUTORIAL_CREATE_BLOCK,
    # Ajoute de futurs tutoriels ici -- voir TUTORIAL_CREATE_BLOCK comme modele.
]
