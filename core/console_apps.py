"""APPS de console : arbres de dialogues utilitaires generes (LCD
inventaire, tri de coffres) + bloc « Console d'atelier ». Meme mecanique
de fusion que console_traders : APPS_MARKER delimite la section
regeneree, placee AVANT le MARKER des traders pour que leur regen
(coupe a son propre marqueur) la preserve.

Conventions de nommage, dans la structure du joueur :
- AFFICHAGE : ecran LCD recevant le contenu de SONDE (option RAFRAICHIR) ;
- SONDE     : container dont on affiche le contenu ;
- TRI       : container source du tri ; cibles TRI_<Categorie> (TRI_Food).

Pieges moteur geres ici :
- AddItems RETOURNE LE RESTANT (0 = tout est entre), jamais l'ajoute ->
  Frontier_Deposer mesure le reel par difference de stock (preuve :
  PrintProcess du moteur + ConveyorHelpers officiel, vecu 17/11) ;
- creation de pile par SetContent : chaque ItemStack porte son slotIdx,
  un nouveau stack sans slot libre ecraserait le slot 0 -> Frontier_Deposer
  prend max(slotIdx)+1 (pattern UniqueSlots du code officiel) ;
- ids runtime des items du scenario : +8192 (voir fiche cerveau) -> lookup
  double sur chaque dictionnaire ;
- le pre-processeur dialogue transforme les apostrophes en guillemets :
  AUCUNE apostrophe francaise dans les chaines C# des fonctions.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from core.console_traders import ITEM_NAME
    from core.console_traders import MARKER as TRADERS_MARKER
    from core.console_traders import _csv_row, _read, _write
except ImportError:      # package autonome (dist/console_atelier)
    from console_traders import ITEM_NAME
    from console_traders import MARKER as TRADERS_MARKER
    from console_traders import _csv_row, _read, _write

APPS_MARKER = '# ===== Console APPS Frontier-FR (16/11) ====='
LCD_PREFIX, SONDE_NAME, TRI_NAME = 'AFFICHAGE', 'SONDE', 'TRI'
APPS_CONSOLE_ID = 207
APPS_CONSOLE_NAME = 'Frontier_Console_Atelier'
# DEUX blocs pour le MEME arbre (DialogueState identique) : une console
# principale + une variante compacte a poser pres des containers (tri /
# rafraichissement d'ecran sans traverser la base). Un seul arbre =
# memoire et reglages partages, aucune duplication de logique.
# (nom, modele dans @models2/Entities/Decorations/, icone d'inventaire,
#  id prefere, recette). L'icone est le nom d'un asset du bundle
# itemicons : `StandConsole_C06` y existe sans etre utilisee par un bloc
# vanilla (verifie via UnityPy), d'ou une icone propre pour la compacte.
CONSOLES = (
    (APPS_CONSOLE_NAME,
     'Sci-Fi_InteriorPack/ScifiComputerTablePrefab', 'ScifiComputerTable',
     207, 'Electronics: 5\n    PlasticMaterial: 10'),
    ('Frontier_Console_Atelier_Petite',
     'Consoles/StandConsole_C06_Prefab', 'StandConsole_C06',
     208, 'Electronics: 3\n    PlasticMaterial: 6'),
)
LCD_PAGE_LINES = 12             # lignes par page de scroll
LCD_SCROLL_S = 5                # secondes entre deux pages (CallLater)
APPRO_AUTO_S = 300              # periode de l'appro auto (5 min)
AIDE_FILE = 'Console_Aide.html'  # dans <scenario>/SharedData (%SHARED_DATA%)
# libelles des blocs (sans ces cles le jeu affiche le nom technique) ;
# la console commerce purge SES cles a chaque regen, d'ou une purge ici
# limitee aux notres (sinon l'ordre de regen efface l'un ou l'autre)
LOCS_ATELIER = (
    ('Frontier_Console_Atelier', 'Frontier Workshop Console',
     "Console d'atelier Frontier"),
    ('bkiFrontier_Console_Atelier',
     'Workshop console: show containers on LCD screens (AFFICHAGE + SONDE), '
     'sort containers (TRI), feed constructors (APPRO).',
     "Console d'atelier : affichez vos coffres sur des écrans LCD "
     "(AFFICHAGE + SONDE), triez vos coffres (TRI), approvisionnez les "
     "fabricateurs (APPRO)."),
    ('Frontier_Console_Atelier_Petite', 'Compact Workshop Console',
     "Console d'atelier compacte"),
    ('bkiFrontier_Console_Atelier_Petite',
     'Compact workshop console. Same dialogue tree as the main console: '
     'shared memory and settings.',
     "Console d'atelier compacte. Même arbre de dialogue que la console "
     "principale : mémoire et réglages partagés."),
)
# description de chaque sous-categorie, pour la fenetre d'aide HTML
CATS_AIDE = {
    'Minerais': 'Minerais et ressources brutes (IronOre, CobaltOre, WoodLogs, '
                'IceBlocks, CrushedStone…)',
    'Lingots': 'Matières raffinées : lingots, barres, poudres (IronIngot, '
               'PlatinBar, MagnesiumPowder…)',
    'Composants': 'Composants fabriqués : plaques, moteurs, électronique, kits',
    'Plantes': 'Récoltes et plantes (Fruit, Grain, Spice, champignons…)',
    'Nourriture': 'Nourriture et rations',
    'Medical': 'Soins, medikits, boosts d\'armure',
    'ArmesJoueur': 'Armes portées par le joueur (fusils, pistolets, laser, '
                   'mêlée) — le tier T2/Épique suit l\'objet',
    'Munitions': 'Munitions et obus (5.8mmBullet, ShotgunShells, obus de '
                 'tourelles)',
    'Deco': 'Blocs décoratifs',
    'ArmesCV': 'Armes de vaisseau et tourelles (blocs)',
    'Devices': 'Appareils et blocs fonctionnels (générateurs, propulseurs, '
               'portes, containers posés…)',
    'Blocs': 'Blocs de construction',
    'Farming': 'Agriculture (plants, cultures)',
    'Marchandises': 'Marchandises commerciales et objets de valeur',
    'Divers': 'Reste du catalogue (véhicules, clés, rapports, objets de '
              'quête…)',
}
# sous-categories de tri (index = code stocke dans le dict C#, d'ou des
# codes entiers : la ligne ECF mono-ligne reste ~1/2 de la version chaines)
CATS = ('Minerais', 'Lingots', 'Composants', 'Plantes', 'Nourriture',
        'Medical', 'ArmesJoueur', 'Munitions', 'Deco', 'ArmesCV', 'Devices',
        'Blocs', 'Farming', 'Marchandises', 'Divers')
# templates de base (Ref: XxxTemplate) -> sous-categorie
TEMPLATE_CATS = {'FoodTemplate': 'Nourriture',
                 'MeleeTemplate': 'ArmesJoueur',
                 'ArmorBoostTemplate': 'Medical',
                 'TradingGoodsTemplate': 'Marchandises',
                 'KeysTemplate': 'Divers',
                 'ReportsTemplate': 'Divers'}
# noms de composants qui sont des MATIERES RAFFINEES (lingots et derives)
REFINED_SUFFIX = ('Ingot', 'Bar', 'Ounce', 'Rods', 'Powder', 'Dust',
                  'Crystal', 'Planks', 'Fibre', 'Cement')
# munitions : nom explicite (charge, obus, projectile, roquette non lanceur)
MUNITION_NOM = ('Charge', 'Bolt', 'Grenade', 'Bullet', 'Shells', 'Ammo',
                'Missile', 'Torpedo', 'antitank', 'Explosive')
# consommables a HoldType 0 qui ne sont PAS des munitions (oxygene, outils)
NON_MUNITION = ('Oxygen', 'Respirator', 'Extinguisher', 'Explosives',
                'Constructor', 'Unit', 'Bay', 'Launcher', 'WeaponTag')
# consommables empilables a HoldType 0 qui sont des COMPOSANTS, pas des
# projectiles (cellules d'energie, carburants)
CONSO_COMPOSANT = ('Fuel', 'EnergyCell', 'Battery', 'Cell')

BLOCK = """{{ +Block Id: {bid}, Name: {name}
  CustomIcon: {icone}
  Class: NPCDialogue
  DialogueState: Frontier_AppAtelier
  NPCModelRotation: false
  Group: cpgCrewStationHuman
  Material: metallight
  Shape: ModelEntity
  Model: @models2/Entities/Decorations/{model}
  DropMeshfile: Entities/Misc/DropContainerNewPrefab
  Place: Free
  Info: bki{name}, display: true
  Category: Devices
  AllowPlacingAt: "Base,MS", display: true
  SizeInBlocks: "1,1,1", display: true
  EnergyIn: 1, type: int, display: true, formatter: Watt
  BlockColor: "255,215,120"
  ShowBlockName: true
  StackSize: 10
}}"""

TEMPLATE = """{{ +Template Name: {name}
  CraftTime: 15
  Target: "SurvC,SmallC,HoverC,BaseC,LargeC,AdvC"
  {{ Child Inputs
    {inputs}
  }}
}}"""


def _aide_html(idf_par_cat: dict) -> str:
    """Fenetre d'aide (panneau HtmlContent du jeu) : TOUTES les possibilites
    du tri et de l'appro, les pieges de nommage, et la liste exacte des
    containers avec le nombre d'items de chaque sous-categorie. Autonome
    (CSS inline, aucun asset externe)."""
    lignes = '\n'.join(
        f'<tr><td class="n"><code>{TRI_NAME}_{c}</code></td>'
        f'<td>{CATS_AIDE.get(c, "")}</td>'
        f'<td class="c">{idf_par_cat.get(c, 0)}</td></tr>' for c in CATS)
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Console d'atelier</title>
<style>
 body {{ font-family: Segoe UI, Arial, sans-serif; background:#12181d;
        color:#dde6ee; margin:0; padding:18px 22px; font-size:14px; }}
 h1 {{ font-size:20px; color:#8fd0ff; margin:0 0 4px; }}
 h2 {{ font-size:15px; color:#ffd479; margin:18px 0 6px;
       border-bottom:1px solid #2b3a46; padding-bottom:3px; }}
 code {{ background:#1b242c; color:#9fe6a0; padding:1px 5px;
         border-radius:3px; font-family:Consolas,monospace; }}
 table {{ border-collapse:collapse; width:100%; margin-top:6px; }}
 th,td {{ text-align:left; padding:4px 8px; border-bottom:1px solid #23303a; }}
 th {{ color:#8fd0ff; }}
 td.c {{ text-align:right; color:#8fd0ff; }}
 td.n {{ width:210px; }}
 .note {{ background:#1b242c; border-left:3px solid #ffd479;
          padding:8px 12px; margin:8px 0; }}
 .warn {{ background:#2a1412; border-left:3px solid #ff8c66;
          padding:8px 12px; margin:8px 0; }}
 .warn b {{ color:#ffb3a0; }}
 ol,ul {{ margin:6px 0 6px 18px; padding:0; }} li {{ margin:4px 0; }}
 .ex {{ color:#9fe6a0; }}
</style></head><body>
<h1>Console d'atelier Frontier</h1>
<p>Trois outils en une console, dans <b>la base où elle se trouve</b> :
<a href="#lcd">affichage sur écrans</a>, <a href="#tri">tri de coffres</a>,
<a href="#appro">approvisionnement des fabricateurs</a>.
Tout se lie par le <b>NOM des blocs</b> (renommez un bloc depuis sa fenêtre
de contrôle, F).</p>

<h2>Installer la console</h2>
<table>
<tr><th>Modèle</th><th>Recette</th><th>Remarque</th></tr>
<tr><td>Console d'atelier</td><td>5 électroniques + 10 plastique</td>
    <td>table d'ordinateur</td></tr>
<tr><td>Console compacte</td><td>3 électroniques + 6 plastique</td>
    <td>sur pied, à poser près des coffres</td></tr>
</table>
<div class="note">Les deux modèles sont <b>strictement équivalents</b> :
même arbre, mêmes réglages, même apprentissage. Posez-en plusieurs si
vous voulez trier sans traverser la base — elles partagent tout.</div>

<h2 id="lcd">1. Afficher le contenu d'un coffre sur un écran</h2>
<ol>
 <li>Posez des <b>écrans LCD</b> et renommez-les :
  <ul>
   <li><code>{LCD_PREFIX}</code> — affiche le <b>dernier coffre sondé</b>
    (par défaut <code>{SONDE_NAME}</code>) ;</li>
   <li><code>{LCD_PREFIX}_&lt;NomCoffre&gt;</code> — écran <b>lié</b> à un
    coffre précis (ex. <code>{LCD_PREFIX}_CaisseFer</code> affiche le coffre
    <code>CaisseFer</code>).</li>
  </ul></li>
 <li>Autant d'écrans que vous voulez, <b>tous en même temps</b> : chacun
  suit son coffre.</li>
 <li><b>RAFRAÎCHIR / relancer l'écran</b> démarre le défilement : une page
  toutes les {LCD_SCROLL_S} s, {LCD_PAGE_LINES} lignes par page, boucle sans
  fin.</li>
 <li><b>SONDER un container (par nom)</b> : tapez un nom de coffre, les
  écrans génériques <code>{LCD_PREFIX}</code> l'affichent.</li>
</ol>
<div class="note">Les noms d'items sont ceux du jeu, dans <b>votre
langue</b>. Un item sans traduction garde son nom interne ; un item
totalement inconnu affiche son identifiant.</div>

<h2 id="tri">2. Trier un coffre</h2>
<ol>
 <li>Nommez le coffre source <b><code>{TRI_NAME}</code></b>.</li>
 <li>Nommez les coffres de destination <code>{TRI_NAME}_&lt;quelque
  chose&gt;</code>. Le tableau plus bas propose les sous-catégories
  automatiques, mais <b>n'importe quel nom</b> fonctionne :
  <code>{TRI_NAME}_Armures_A</code>, <code>STOCK_Carburant</code>…</li>
 <li>Console → <b>TRIER le coffre {TRI_NAME}</b>.</li>
</ol>
<p>Trois niveaux de classement, dans cet ordre :</p>
<ol>
 <li><b>Ce que vous avez appris</b> (option APPRENDRE) — prioritaire ;</li>
 <li><b>La sous-catégorie automatique</b> (15 catégories, tableau plus bas) ;</li>
 <li>Sinon l'item <b>reste dans <code>{TRI_NAME}</code></b>.</li>
</ol>

<h3>Apprendre vos rangements</h3>
<ol>
 <li>Rangez à la main un objet mal classé dans <b>le coffre de votre
  choix</b> (nom libre accepté).</li>
 <li>Console → <b>APPRENDRE mes rangements</b>.</li>
 <li>Désormais cet objet va <b>toujours</b> dans ce coffre, en priorité sur
  le classement automatique. <b>OUBLIER la mémoire</b> remet tout en
  automatique.</li>
</ol>
<div class="note">APPRENDRE ne mémorise que les <b>écarts</b> : ce que le
classement automatique fait déjà correctement n'est pas enregistré, ce qui
garde la mémoire courte et lisible. L'apprentissage est <b>partagé</b> par
toutes les consoles d'atelier.</div>

<h3>Plusieurs coffres par catégorie (débordement)</h3>
<p><code>{TRI_NAME}_Lingots</code>, <code>{TRI_NAME}_Lingots_A</code>,
<code>{TRI_NAME}_Lingots_2</code>… peuvent coexister : ils sont remplis
<b>dans l'ordre alphabétique</b>, le contenu déborde sur le suivant quand
un coffre est plein.</p>

<h3>Changer de préfixe</h3>
<p>Option <b>CHANGER le préfixe de tri</b> : tout le système bascule
(<code>STOCK_Coffre</code> au lieu de <code>TRI_Coffre</code>). Le préfixe
est conservé avec la partie.</p>

<div class="warn"><b>Jamais triés</b> : les <b>licences</b> de commerçant
(objets uniques, elles restent dans <code>{TRI_NAME}</code>), les blocs de
terrain (pierre, herbe, sable — ils n'entrent pas dans un coffre) et tout
item inconnu du catalogue.</div>

<h2 id="appro">3. Approvisionner les fabricateurs</h2>
<p>La console maintient des coffres à niveau, en puisant dans vos coffres
de tri (<code>{TRI_NAME}_&lt;Catégorie&gt;</code>). <b>Triez d'abord</b> :
l'approvisionnement lit là où le tri a rangé.</p>

<h3>a) Un coffre = un seul item</h3>
<ol>
 <li>Nommez un container <code>APPRO_&lt;Item&gt;</code> (ex.
  <code>APPRO_CopperIngot</code>) : il sera maintenu à <b>1000 unités</b>.</li>
 <li>Pour un autre niveau, suffixez la quantité :
  <code>APPRO_CopperIngot_500</code>, <code>APPRO_IronIngot_4000</code>.</li>
 <li>Le nom de l'item est son <b>nom interne exact</b> (celui affiché sur
  l'écran LCD, sans traduction) : <code>5.8mmBullet</code>,
  <code>CopperIngot</code>, <code>SteelPlate</code>…</li>
</ol>

<h3>b) Un coffre = plusieurs ingrédients (recette complète)</h3>
<ol>
 <li>Remplissez un container à la main avec <b>tout</b> ce qu'il faut à
  votre fabricateur, aux quantités voulues (ex. <code>IronIngot ×500</code>,
  <code>TitanIngot ×200</code>, <code>Electronics ×100</code>).</li>
 <li>Nommez-le <b><code>APPRO</code></b> — ou <code>APPRO_A</code>,
  <code>APPRO_Fonderie</code>… si vous en avez plusieurs.</li>
 <li>Console → <b>MÉMORISER UN coffre APPRO (par nom)</b> → tapez son nom.</li>
 <li>Ensuite <b>APPROVISIONNER</b> recharge chaque ingrédient à son niveau.</li>
</ol>
<div class="note"><b>Plusieurs fabricateurs (un craft chacun)</b> : un
coffre par fabricateur, puis <b>MÉMORISER TOUS les coffres APPRO</b> — en
un clic, chaque coffre enregistre sa propre cible. Ensuite
<b>APPROVISIONNER</b> les réalimente tous ensemble.
<br>Un coffre <b>vide</b> est ignoré par cette option : il est en cours de
craft, sa cible est conservée.</div>
<p>Pour changer une quantité : ajustez le coffre à la main, puis
re-mémorisez.</p>

<h3>Automatiser</h3>
<p>Dans le menu <b>APPROVISIONNER les coffres de craft</b>, deux options :
<b>DÉMARRER l'auto</b> (l'appro tourne toutes les 5 minutes de session, en
fond) et <b>ARRÊTER l'auto</b>. Pratique avec un fabricateur qui produit en
continu.</p>
<div class="note">L'auto s'arrête au chargement suivant : relance-la en
ouvrant la console une fois après chaque reprise de partie. Le journal du
jeu trace <code>APP-APPRO: auto demarre</code>, puis un
<code>tick auto</code> toutes les 5 minutes avec le nombre d'items
déplacés.</div>
<div class="note">Le <b>fabricateur</b> déclare lui-même le coffre qu'il
utilise (panneau de contrôle) : posez le coffre <code>APPRO…</code> contre
lui et déclarez-le. La console ne se mêle pas de ce câblage, elle maintient
le contenu.</div>

<h2>Règles d'or (à lire une fois)</h2>
<div class="warn">
<b>1. Des noms UNIQUES.</b> Empyrion autorise deux coffres portant le
<b>même</b> nom — mais la console n'en voit qu'<b>un seul</b> : le tri et
l'appro tomberont toujours sur le même, l'autre sera ignoré sans message.
C'est la première cause de « ça ne marche pas ». Vérifiez aussi qu'un nom
n'existe pas déjà dans un autre groupe de blocs de la base.
</div>
<ul>
 <li><b>Casse et orthographe exactes</b> : <code>{TRI_NAME}_Lingots</code>
  fonctionne, <code>{TRI_NAME}_lingots</code> non.</li>
 <li><b>Renommer un coffre</b> après apprentissage : la mémoire garde
  l'ancien nom, le coffre renommé n'est plus reconnu — re-mémorisez / ré
  apprenez.</li>
 <li><b>TRIER avant APPROVISIONNER</b> : l'appro puise dans les coffres de
  sous-catégorie, pas directement dans <code>{TRI_NAME}</code>.</li>
 <li>Rien n'est perdu : un item sans destination reste dans
  <code>{TRI_NAME}</code> ; le journal du jeu trace <code>APP-LCD</code>,
  <code>APP-TRI</code>, <code>APP-APPRO</code> et <code>APP-APPRIS</code>.</li>
 <li>Les réglages (préfixe, apprentissage, cibles d'appro) sont
  <b>conservés avec la partie</b>.</li>
</ul>

<h2>Tableau des sous-catégories automatiques</h2>
<table><tr><th>Coffre à créer</th><th>Contenu classé</th><th>Items</th></tr>
{lignes}
</table>
<p>Créez seulement ceux qui vous servent. Un coffre au nom libre
(<code>{TRI_NAME}_Armures_A</code>) est parfaitement valide : il ne
recevra rien automatiquement, mais APPRENDRE le remplira.</p>
</body></html>"""


def _merge_blocks(blocks_text: str) -> tuple:
    out, added = blocks_text, 0
    used = set(int(x) for x in
               re.findall(r'^\{ \+?Block Id: (\d+),', out, re.M))
    # unicite par NOM : un bloc deja present (et donc deja pose en jeu)
    # n'est jamais reecrit — couleurs et reglages du joueur preserves
    for nom, model, icone, pref, _recette in CONSOLES:
        if f'Name: {nom}' in out:
            continue
        bid = pref if pref not in used else \
            next(i for i in range(136, 2048) if i not in used)
        used.add(bid)
        out = out.rstrip('\n') + '\n\n' + \
            BLOCK.format(bid=bid, name=nom, model=model, icone=icone) + '\n'
        added += 1
    return out, added


def _merge_templates(templates_text: str) -> tuple:
    out, added = templates_text, 0
    for nom, _model, _icone, _pref, recette in CONSOLES:
        if f'+Template Name: {nom}' in out:
            continue
        out = out.rstrip('\n') + '\n\n' + \
            TEMPLATE.format(name=nom, inputs=recette) + '\n'
        added += 1
    return out, added


def _sous_cat_item(nom: str, ref: str, cat: str, body: str = ''):
    """Sous-categorie de tri d'un item (None : pas trie).

    Distinction reelle des configs : Ref: OreTemplate = minerais ;
    ComponentsTemplate = matieres raffinees (suffixe de nom) ou composants ;
    Category = armes joueur / nourriture / medical / plantes. Le Ref est
    teste AVANT la Category : les minerais et les lingots n'ont pas de
    champ Category (vecu 16/11 : ils sortaient a 0)."""
    if ref == 'OreTemplate':
        return 'Minerais'
    # munitions : pas de Category, refilees par Ref:50Caliber ou par nom
    # (les obus de tourelle sont des ...UpgradeAmmo ; "Shells" au pluriel
    # pour ne pas happer MeleeShell, Ref: MeleeTemplate). 50Caliber est la
    # munition de reference et beaucoup d'objets l'ont en Ref sans etre des
    # projectiles (BioFuel : Ref 50Caliber ET Category Components) -> la
    # regle ne s'applique qu'hors Category explicite.
    if cat not in ('Components', 'Food', 'Medical', 'Ingredients') and \
            (ref == '50Caliber' or nom.endswith('Ammo')
             or nom.endswith('Shells') or 'Bullet' in nom):
        return 'Munitions'
    # projectiles qui portent Category: Weapons sans etre des armes :
    # SlowRocket / FastRocketHoming / FlakRocketMS... mais NI les lanceurs
    # (RocketLauncher*) NI les armes de tourelle (TurretMSRocketWeapon)
    if ('Rocket' in nom and 'Launcher' not in nom and 'Weapon' not in nom) \
            or any(k in nom for k in ('Missile', 'Torpedo', 'Grenade',
                                      'PlasmaCharge')):
        return 'Munitions'
    if ref == 'ComponentsTemplate':
        return 'Lingots' if nom.endswith(REFINED_SUFFIX) else 'Composants'
    # la Category EXPLICITE prime sur le template : les medikits et bandages
    # portent Ref: FoodTemplate MAIS Category: Medical (vecu 17/11 : ils
    # partaient en Nourriture, puis l'apprentissage figeait l'erreur)
    if cat == 'Medical':
        return 'Medical'
    if cat == 'Food':
        return 'Nourriture'
    if cat == 'Ingredients':
        return 'Plantes'
    if cat == 'BuildingBlocks':
        return 'Blocs'
    if ref in TEMPLATE_CATS:
        return TEMPLATE_CATS[ref]
    if cat == 'Weapons':
        # dans Category: Weapons cohabitent armes ET munitions. Deux
        # criteres exhaustifs (scannes sur les 217 items du scenario) :
        #  - nom explicite de projectile (Charge, Bolt, Grenade, Rocket
        #    sans Launcher...) ;
        #  - consommable EMPILABLE : HoldType 0 et StackSize > 1.
        # Les armes de vaisseau finissent par Weapon (StackSize 250-500).
        if nom in ('Explosives',) or 'Armor' in nom:
            return 'Divers'          # armures : Category Weapons chez le
                                     # jeu, mais ce ne sont pas des armes
        if any(k in nom for k in CONSO_COMPOSANT):
            return 'Composants'      # cellules / carburants, pas projectiles
        # un nom contenant Weapon est une ARME (tourelles, armes de
        # vaisseau, drones) — y compris TurretMSRocketWeapon ou
        # TurretEnemyLaserWeaponBlack ou `Weapon` n'est pas en fin de nom
        if 'Weapon' in nom:
            return 'ArmesJoueur'
        if any(k in nom for k in MUNITION_NOM) or \
                ('Rocket' in nom and 'Launcher' not in nom):
            if not any(k in nom for k in NON_MUNITION):
                return 'Munitions'
        ht = re.search(r'^  HoldType: (\d+)', body, re.M)
        ss = re.search(r'^  StackSize: (\d+)', body, re.M)
        if ht and ht.group(1) == '0' and ss and int(ss.group(1)) > 1:
            if any(k in nom for k in NON_MUNITION):
                return 'Divers'
            return 'Munitions'
        # le tier (T1/T2/Epic) est un item distinct (id distinct) : il suit
        # l'id. Seul le `meta` de pile est perdu par AddItems — dans
        # Frontier-FR seul `Token` s'en sert, et il n'est pas route.
        return 'ArmesJoueur'
    if cat == 'Food':
        return 'Nourriture'
    if cat == 'Medical':
        return 'Medical'
    if cat == 'Ingredients':
        return 'Plantes'
    if cat == 'BuildingBlocks':
        return 'Blocs'
    if ref in TEMPLATE_CATS:
        return TEMPLATE_CATS[ref]
    if nom.startswith('Melee'):
        return 'ArmesJoueur'          # arme de melee de base (ni Ref ni Cat)
    if cat:
        return 'Divers'               # catalogué (vehicules, armures...) mais
    return None                       # sans regle dediee


def _catalogue(items_text: str, blocks_text: str, traders_text: str) -> dict:
    """id -> '<code>|<NomInterne>' : index de sous-categorie dans CATS et
    cle de localisation (le nom interne EST la cle de Localization.csv).
    Combine en un seul dictionnaire : 1 093 entrees en 28,6 Ko, contre
    43,4 Ko en deux dictionnaires separes.

    Items : Ref/Category des configs. Blocs : Category du BlocksConfig
    (Deco/ArmesCV/Devices/Blocs/Farming) ; nos blocs Frontier_ et ceux
    cites par les traders restent routes en Blocs."""
    # DEUX tables de routes : un item et un bloc peuvent porter le meme
    # numero d'id et avoir des categories differentes (669 collisions dans
    # Frontier-FR). Les cles du dictionnaire runtime sont distinctes :
    # item = id config (pile remappee +8192), bloc = 100000 + id config.
    routes_item: dict = {}
    routes_bloc: dict = {}
    trades = set(re.findall(r'Item\d+: "(\w+)', traders_text))
    decl = []            # (id, nom, ref, categorie, corps de l'item)
    for m in re.finditer(r'\{ \+?Item Id: (\d+), Name: ' + ITEM_NAME
                         + r'(?:, Ref: (\w+))?[^\n]*\n(.*?\n)(?=\{ |\Z)',
                         items_text, re.S):
        if m.group(2).startswith('Frontier_Licence_'):
            continue                  # licences : jamais triees (objet unique)
        cm = re.search(r'^  Category: (\w+)', m.group(4), re.M)
        decl.append((int(m.group(1)), m.group(2), m.group(3),
                     cm.group(1) if cm else '', m.group(4)))
    # passe 1 : regles directes ; passe 2 : heritage par Ref (PistolT2 et
    # PistolEpic n'ont AUCUNE Category, seul le Ref les relie a leur base)
    decide = {}
    for iid, nom, ref, cat, body in decl:
        sc = _sous_cat_item(nom, ref, cat, body)
        if sc:
            decide[iid] = sc
    par_nom = {nom: iid for iid, nom, _r, _c, _b in decl}
    for _ in range(3):               # chaines de variantes : T2 -> base -> ...
        avant = len(decide)
        for iid, nom, ref, _c, _b in decl:
            if iid in decide or not ref:
                continue
            base = par_nom.get(ref)
            if base is not None and base in decide:
                decide[iid] = decide[base]
        if len(decide) == avant:
            break
    for iid, sc in decide.items():
        routes_item[iid] = CATS.index(sc)
    map_bloc = {'Deco': 'Deco', 'Weapons': 'ArmesCV', 'Devices': 'Devices',
                'BuildingBlocks': 'Blocs', 'Farming': 'Farming'}
    ids_blocs_routes: set = set()
    blocs_decl = []              # (id, nom, ref, categorie, masse)
    for m in re.finditer(r'\{ \+?Block Id: (\d+), Name: ' + ITEM_NAME
                         + r'(?:, Ref: (\w+))?[^\n]*\n(.*?\n)(?=\{ |\Z)',
                         blocks_text, re.S):
        bid, nom, ref = int(m.group(1)), m.group(2), m.group(3)
        body = m.group(4)
        cm = re.search(r'^  Category: (\w+)', body, re.M)
        sc = map_bloc.get(cm.group(1)) if cm else None
        if not sc:
            # repli par Class : blocs FONCTIONNELS non catalogues (containers,
            # sieges, interrupteurs poses par les POI) et plantes cultivables
            cls = re.search(r'^  Class: (\w+)', body, re.M)
            if cls:
                sc = 'Farming' if cls.group(1) in ('PlantGrowing',
                                                   'CropsGrown') else 'Devices'
        if not sc and (nom.startswith('Frontier_') or nom in trades):
            sc = 'Blocs'
        # `Mass:` distingue un bloc INVENTORIABLE (siege, tourelle
        # retractable, reservoir, bloc plein) du terrain (Stone, Grass,
        # Rock n'en ont pas)
        masse = bool(re.search(r'^  Mass:', body, re.M))
        # bloc de construction PLEIN (HullFullSmall, WoodFull, ConcreteFull,
        # PlasticFull...) : ni Category ni Class ni Ref, mais une Mass —
        # c'est un bloc, pas du terrain
        if not sc and masse:
            sc = 'Blocs'
        # (suite) seul un bloc a masse herite par Ref
        blocs_decl.append((bid, nom, ref, sc, masse))
    # les blocs heritent aussi par Ref (PassengerSeatSS_Slope porte
    # `Ref: PassengerSeatSS_Cube` sans Category ni Class, vecu 17/11 :
    # les sieges passagers tombaient dans la categorie de l'item homonyme)
    par_nom_b = {nom: bid for bid, nom, _r, _c, _m in blocs_decl}
    decide_b = {bid: sc for bid, _n, _r, sc, _m in blocs_decl if sc}
    for _ in range(3):
        avant_b = len(decide_b)
        for bid, _n, ref, _c, masse in blocs_decl:
            if bid in decide_b or not ref or not masse:
                continue
            base = par_nom_b.get(ref)
            if base is not None and base in decide_b:
                decide_b[bid] = decide_b[base]
        if len(decide_b) == avant_b:
            break
    for bid, sc in decide_b.items():
        routes_bloc[bid] = CATS.index(sc)
        ids_blocs_routes.add(bid)
    # un seul dictionnaire au runtime : cle -> "<code>|<NomInterne>". Le nom
    # sert a Loc() (cle de localisation = nom interne de l'item) ; combine,
    # il coute 28,6 Ko au lieu de 43,4 Ko en deux dictionnaires.
    noms_blocs = {}
    for m in re.finditer(r'\{ \+?Block Id: (\d+), Name: ' + ITEM_NAME,
                         blocks_text):
        noms_blocs[int(m.group(1))] = m.group(2)
    noms_libres = dict(noms_blocs)
    noms_libres.update({iid: nom for iid, nom, _r, _c, _b in decl})
    # ESPACES DE CLES SEPARES : un item et un bloc portent souvent le meme
    # numero (669 collisions dans Frontier-FR : le bloc PassengerSeatMS
    # id 266 heritait de la categorie de l'ITEM id 266, un minerai). Au
    # runtime les items sont remappes +8192 et les blocs gardent leur id,
    # donc : cle item = id config, cle bloc = 100000 + id config.
    info: dict = {}
    for iid, code in routes_item.items():
        if iid in noms_libres:
            info[iid] = f'{code}|{noms_libres[iid]}'
    for bid, code in routes_bloc.items():
        # blocs : CODE SEUL. ~860 blocs, leur nom couterait 14 Ko de plus
        # dans une ligne Functions deja limitee : le tri reste exact, et
        # l'affichage retombe sur l'id (les items, eux, gardent leur nom)
        info[100000 + bid] = str(code)
    # les ITEMS non triables gardent un nom (code -1) : un container peut en
    # contenir, et l'ecran ne doit pas afficher un id nu. Les BLOCS non
    # routes (terrain) restent hors dictionnaire : ils ne sont jamais dans
    # un coffre et pousseraient 1 000 entrees de plus. Les licences, exclues
    # du tri, sont nommees en forme courte (Licence_Xxx) : leur cle de
    # localisation coute 1,1 Ko de plus pour un affichage identique en FR.
    for m in re.finditer(r'\{ \+?Item Id: (\d+), Name: ' + ITEM_NAME,
                         items_text):
        iid, nom = int(m.group(1)), m.group(2)
        if iid not in info:
            info[iid] = '-1|' + nom.replace('Frontier_Licence_', 'Licence_')
    return info


def _dict_info(d: dict) -> str:
    """Entrees compactes "{1234,'5|Nom'}" : sans les espaces de la forme
    litterale, 4 caracteres par entree, ~4,6 Ko sur 1 154 entrees."""
    return ','.join(f"{{{i},'{v}'}}" for i, v in sorted(d.items()))


def _vars_memoire() -> str:
    """Declaration de la memoire d'apprentissage, LUE depuis la base.

    `param1: dbplayer_string` est le SEUL mecanisme qui recharge une
    valeur existante dans une propriete C# (a l'entree du state) : les
    API Add/SetGlobalVar ne permettent pas de lire (elles renvoient la
    valeur ajoutee/ecrite, jamais le contenu — vecu 17/11).

    UNE SEULE variable (format ",id=NomCoffre,id=NomCoffre,") : la
    destination apprise est le NOM du coffre, pas une sous-categorie.
    Les 15 categories figees ne couvrent pas les coffres libres du
    joueur (TRI_Armures_A, TRI_Carburant_A...) : l'apprentissage les
    ignorait (vecu 17/11). UN SEUL etat la declare : le compilateur
    fusionne les Variable_N de tous les etats d'un arbre, une 2e
    declaration = CS0102 « already contains a definition » -> classe
    morte, console VIDE (vecu 17/11 soir)."""
    return ('  Variable_1: "Frontier_Dest", param1: dbplayer_string\n'
            # memoire du coffre APPRO multi-items : "|Nom=id:qty,id:qty|"
            '  Variable_2: "Frontier_Appr", param1: dbplayer_string\n')


def _fonc_memoire() -> str:
    """Lecteur de la memoire d'apprentissage.

    POURQUOI PAS AddToGlobalVar : `API_AddToGlobalVar_Int` retourne
    `_val` (la valeur AJOUTEE), pas la valeur stockee — on lit toujours
    0. Seules les variables declarees en `Variable_N: ...,
    param1: dbplayer_string` sont reellement LUES depuis la base.

    Format : ",id=NomCoffre,id=NomCoffre," -> un item mémorisé va dans
    CE coffre, en priorite sur le classement automatique."""
    return (
        # trace horodatee des actions de la console : permet de correler un
        # bruit moteur (SetLabel...) avec CE QUE le joueur vient de faire.
        # Prefixe unique pour un grep : APP-TRACE
        "void Frontier_Trace(string q) {<nl>"
        "  UnityEngine.Debug.Log('APP-TRACE: ' + q);<nl>"
        "}<nl>"
        "string Frontier_Destin(int id) {<nl>"
        "  if (Frontier_Dest == null) { return null; }<nl>"
        "  string cle = ',' + id.ToString() + '=';<nl>"
        "  int p = Frontier_Dest.IndexOf(cle);<nl>"
        "  if (p < 0) { return null; }<nl>"
        "  int d = p + cle.Length;<nl>"
        "  int f = Frontier_Dest.IndexOf(',', d);<nl>"
        "  if (f < 0) { return null; }<nl>"
        "  return Frontier_Dest.Substring(d, f - d);<nl>"
        "}<nl>"
        # ---- coffre APPRO multi-items : "|Nom=id:qty,id:qty|"
        # De() rend la liste memorisee d'un coffre (null si inconnu),
        # Maj() la remplace, Snap() photographie le contenu d'un coffre.
        "string Frontier_ApprDe(string nom) {<nl>"
        "  if (Frontier_Appr == null) { return null; }<nl>"
        "  string cle = '|' + nom + '=';<nl>"
        "  int p = Frontier_Appr.IndexOf(cle);<nl>"
        "  if (p < 0) { return null; }<nl>"
        "  int d = p + cle.Length;<nl>"
        "  int f = Frontier_Appr.IndexOf('|', d);<nl>"
        "  if (f < 0) { return null; }<nl>"
        "  return Frontier_Appr.Substring(d, f - d);<nl>"
        "}<nl>"
        "string Frontier_ApprMaj(string nom, string liste) {<nl>"
        "  string mem = Frontier_Appr;<nl>"
        "  if (mem == null) { mem = '|'; }<nl>"
        "  string cle = '|' + nom + '=';<nl>"
        "  int p = mem.IndexOf(cle);<nl>"
        "  if (p < 0) { return mem + nom + '=' + liste + '|'; }<nl>"
        "  int d = p + cle.Length;<nl>"
        "  int f = mem.IndexOf('|', d);<nl>"
        "  if (f < 0) { f = mem.Length; }<nl>"
        "  return mem.Substring(0, d) + liste + mem.Substring(f);<nl>"
        "}<nl>"
        "string Frontier_ApprSnap(IContainer c) {<nl>"
        "  string s = '';<nl>"
        "  foreach (var st in c.GetContent()) {<nl>"
        "    if (st.count <= 0) { continue; }<nl>"
        "    s = s + Frontier_Cle(st.id) + ':' + st.count + ',';<nl>"
        "  }<nl>"
        "  return s;<nl>"
        "}"
    )


def _fonc_apprendre() -> str:
    """Memorise la destination de CHAQUE pile rangee a la main, par NOM
    de coffre : tout container `<prefix>_...` est reconnu, y compris
    ceux hors des 15 sous-categories (TRI_Armures_A...). Ne memorise que
    les ECARTS : ce que le classement automatique enverrait deja dans CE
    coffre n'a pas besoin d'etre grave."""
    return (
        "void Frontier_Apprendre() {<nl>"
        "  string pref = AddToGlobalVar('Frontier_Tri_Pref', '');<nl>"
        "  if (pref == null || pref == '') { pref = 'TRI'; }<nl>"
        "  string dest = ',';<nl>"
        "  string[] noms = LocalStructure.GetAllCustomDeviceNames();<nl>"
        "  Array.Sort(noms);<nl>"
        "  int n = 0;<nl>"
        "  foreach (string nd in noms) {<nl>"
        "    if (!nd.StartsWith(pref + '_')) { continue; }<nl>"
        "    var c = LocalStructure.GetDevice<IContainer>(nd);<nl>"
        "    if (c == null) { continue; }<nl>"
        "    foreach (var st in c.GetContent()) {<nl>"
        "      string v0;<nl>"
        "      int auto0 = -1;<nl>"
        "      if (Frontier_Valeur(st.id, out v0)) { auto0 = "
        "Frontier_Code(v0); }<nl>"
        # le classement auto enverrait deja cet item dans CE coffre
        "      if (auto0 >= 0 && nd.StartsWith(pref + '_' + "
        "CATS[auto0])) { continue; }<nl>"
        "      string k0 = ',' + st.id.ToString() + '=';<nl>"
        "      if (dest.IndexOf(k0) >= 0) { continue; }<nl>"
        "      dest = dest + st.id + '=' + nd + ',';<nl>"
        "      n = n + 1;<nl>"
        "    }<nl>"
        "  }<nl>"
        "  Frontier_Dest = dest;<nl>"
        "  SetGlobalVar('Frontier_Dest', dest);<nl>"
        "  UnityEngine.Debug.Log('APP-APPRIS: ' + n + ' ECARTS memorises "
        "(le reste suit le classement automatique)');<nl>"
        "}<nl>"
        "void Frontier_Oublier() {<nl>"
        "  Frontier_Dest = ',';<nl>"
        "  SetGlobalVar('Frontier_Dest', ',');<nl>"
        "  Frontier_Trace('oublier');<nl>"
        "  UnityEngine.Debug.Log('APP-APPRIS: memoire effacee');<nl>"
        "}"
    )


def _arbre(info: dict) -> str:
    """Genere le texte complet de la section APPS (hub + noeuds) pour
    insertion entre APPS_MARKER et TRADERS_MARKER dans Dialogues.ecf.
    Les declarations Variables du hub et du noeud Apprendre restent dans
    leurs noeuds respectifs (chacun charge les siennes a l'entree)."""
    cats_cs = ', '.join(f"'{c}'" for c in CATS)
    ids = sorted(info)
    total = sum(len(f"{{ {i}, '{info[i]}' }}") for i in ids)
    bornes = [0.105, 0.337, 0.567, 0.75, 1.0]
    parts: list = [[], [], [], [], []]
    acc = 0
    for iid in ids:
        frac = acc / total
        b = 0
        while b < 4 and frac > bornes[b]:
            b += 1
        parts[b].append(iid)
        acc += len(f"{{ {iid}, '{info[iid]}' }}")
    tranches = [{i: info[i] for i in p} for p in parts]
    noms_tr = ['infosA', 'infosB', 'infosC', 'infosD', 'infosE']
    # les 5 dictionnaires sont des CHAMPS de la classe : Frontier_Valeur
    # les référence tous (vecu 17/11 : fonc_sonder/fonc_triok construits
    # mais jamais injectés -> infosB..E inconnus -> classe morte)
    decl_tr = ''.join(
        f"Dictionary<int, string> {n} = new Dictionary<int, string>() {{ "
        + _dict_info(tranches[k]) + ' };<nl>'
        for k, n in enumerate(noms_tr))
    cle_look = ''.join(
        f"  if ({n}.TryGetValue(k, out v)) {{ return true; }}<nl>"
        for n in noms_tr)
    brut_look = ''.join(
        f"  if ({n}.TryGetValue(id, out v)) {{ return true; }}<nl>"
        for n in noms_tr)
    trouve_look = ''.join(
        f"  foreach (var kv in {n}) {{ if (Frontier_NomItem(kv.Value) == "
        "nom) { id = kv.Key; code = Frontier_Code(kv.Value); "
        "return true; } }<nl>"
        for n in noms_tr)
    fonc = (
        f"string[] CATS = new string[] {{ {cats_cs} }};<nl>"
        + _fonc_memoire() +
        "static int Frontier_Idx = 0;<nl>"
        "static string Frontier_Nom = '';<nl>"
        "static string Frontier_Pref = '';<nl>"
        "static bool Frontier_AutoOn = false;<nl>"
        + decl_tr +
        "int Frontier_Cle(int id) {<nl>"
        "  return id >= 8192 ? id - 8192 : id + 100000;<nl>"
        "}<nl>"
        "bool Frontier_Valeur(int id, out string v) {<nl>"
        "  int k = Frontier_Cle(id);<nl>"
        + cle_look +
        "  if (infosE.TryGetValue(k, out v)) { return true; }<nl>"
        + brut_look +
        "  if (infosE.TryGetValue(id, out v)) { return true; }<nl>"
        "  v = null;<nl>"
        "  return false;<nl>"
        "}<nl>"
        "int Frontier_Code(string v) {<nl>"
        "  int p = v.IndexOf('|');<nl>"
        "  return p < 0 ? int.Parse(v) : int.Parse(v.Substring(0, p));<nl>"
        "}<nl>"
        "string Frontier_NomItem(string v) {<nl>"
        "  int p = v.IndexOf('|');<nl>"
        "  return p < 0 ? null : Loc(v.Substring(p + 1));<nl>"
        "}<nl>"
        # recherche INVERSE (nom interne -> id + code), pour APPRO_<Item> :
        # perdue dans la reecriture du 17/11 -> CS0103 sur tout l'arbre
        "bool Frontier_Trouver(string nom, out int id, out int code) {<nl>"
        "  id = -1;<nl>"
        "  code = -1;<nl>"
        + trouve_look +
        "  return false;<nl>"
        "}<nl>"
        "int Frontier_Stock(IContainer c, int id) {<nl>"
        "  int t = 0;<nl>"
        "  foreach (var st in c.GetContent()) {<nl>"
        "    if (Frontier_Cle(st.id) == Frontier_Cle(id)) { "
        "t = t + st.count; }<nl>"
        "  }<nl>"
        "  return t;<nl>"
        "}<nl>"
        # retrait VERIFIE par SetContent : RemoveItems ne retire RIEN sur
        # ces containers (vecu 17/11, log 'deplaces=0')
        "int Frontier_Retirer(IContainer c, int id, int qty) {<nl>"
        "  int av = Frontier_Stock(c, id);<nl>"
        "  if (av <= 0) { return 0; }<nl>"
        "  if (qty > av) { qty = av; }<nl>"
        "  var neuf = new List<ItemStack>();<nl>"
        "  int reste = qty;<nl>"
        "  foreach (var st0 in c.GetContent()) {<nl>"
        "    var st = st0;<nl>"
        "    if (reste > 0 && Frontier_Cle(st.id) == Frontier_Cle(id)) {<nl>"
        "      int pris = st.count < reste ? st.count : reste;<nl>"
        "      st.count = st.count - pris;<nl>"
        "      reste = reste - pris;<nl>"
        "    }<nl>"
        "    if (st.count > 0) { neuf.Add(st); }<nl>"
        "  }<nl>"
        "  c.SetContent(neuf);<nl>"
        "  return av - Frontier_Stock(c, id);<nl>"
        "}<nl>"
        # depot : AddItems retourne le RESTANT (0 = tout entre, preuve :
        # moteur PrintProcess + ConveyorHelpers officiel), JAMAIS l'ajoute.
        # On mesure donc le reel par difference de stock ; si AddItems
        # refuse une pile entiere alors qu'une place existe (cas connu du
        # moteur), depot explicite sur un slotIdx libre — un slotIdx deja
        # pris ecraserait la pile existante (SetContent ecrit a l'index).
        "int Frontier_Deposer(IContainer c, int id, int qty) {<nl>"
        "  int av = Frontier_Stock(c, id);<nl>"
        "  c.AddItems(id, qty);<nl>"
        "  int mv = Frontier_Stock(c, id) - av;<nl>"
        "  if (mv <= 0) {<nl>"
        "    var dl = c.GetContent();<nl>"
        "    int ns = 0;<nl>"
        "    foreach (var d in dl) { if (d.slotIdx >= ns) { ns = d.slotIdx "
        "+ 1; } }<nl>"
        "    var st = new ItemStack(id, qty);<nl>"
        "    st.slotIdx = (byte)ns;<nl>"
        "    dl.Add(st);<nl>"
        "    c.SetContent(dl);<nl>"
        "    mv = Frontier_Stock(c, id) - av;<nl>"
        "  }<nl>"
        "  if (mv > qty) { mv = qty; }<nl>"
        "  return mv;<nl>"
        "}<nl>"
        "void Frontier_AfficherEcran(int avance) {<nl>"
        "  int nb2 = 0;<nl>"
        "  Frontier_Idx = Frontier_Idx + avance;<nl>"
        "  if (Frontier_Idx < 0) { Frontier_Idx = 0; }<nl>"
        "  int idx = Frontier_Idx;<nl>"
        "  string nsrc = Frontier_Nom;<nl>"
        f"  if (nsrc == '' || nsrc == null) {{ nsrc = '{SONDE_NAME}'; }}<nl>"
        "  string[] ecrans = LocalStructure.GetAllCustomDeviceNames();<nl>"
        "  Array.Sort(ecrans);<nl>"
        "  foreach (string nmec in ecrans) {<nl>"
        f"    if (!nmec.StartsWith('{LCD_PREFIX}')) {{ continue; }}<nl>"
        "    string cible2 = nsrc;<nl>"
        f"    if (nmec.StartsWith('{LCD_PREFIX}_')) {{ cible2 = "
        f"nmec.Substring({len(LCD_PREFIX) + 1}); }}<nl>"
        "    var src2 = LocalStructure.GetDevice<IContainer>(cible2);<nl>"
        "    if (src2 == null) { continue; }<nl>"
        "    var piles = src2.GetContent();<nl>"
        "    int npiles = piles.Count;<nl>"
        "    int deb = 0;<nl>"
        f"    if (npiles > 0) {{ deb = (idx * {LCD_PAGE_LINES}) % npiles; "
        "}<nl>"
        "    string s = cible2 + ' (' + npiles + ' piles)';<nl>"
        "    int k = 0;<nl>"
        f"    while (k < {LCD_PAGE_LINES} && k < npiles) {{<nl>"
        "      var p2 = piles[(deb + k) % npiles];<nl>"
        "      string val2;<nl>"
        "      if (Frontier_Valeur(p2.id, out val2)) {<nl>"
        "        s = s + '\\n' + Frontier_NomItem(val2) + ' x' + "
        "p2.count;<nl>"
        "      } else {<nl>"
        "        s = s + '\\n' + p2.id + ' x' + p2.count;<nl>"
        "      }<nl>"
        "      k = k + 1;<nl>"
        "    }<nl>"
        "    var lcd2 = LocalStructure.GetDevice<ILcd>(nmec);<nl>"
        "    if (lcd2 != null) { lcd2.SetText(s); nb2 = nb2 + 1; }<nl>"
        "  }<nl>"
        "  UnityEngine.Debug.Log('APP-LCD: page ' + idx + ' sur ' + nb2 + "
        "' ecran(s)');<nl>"
        f"  if (nb2 > 0) {{ CallLater({LCD_SCROLL_S}.0f, "
        "Frontier_ScrollSuivant); }<nl>"
        "}<nl>"
        "void Frontier_ScrollSuivant() {<nl>"
        "  Frontier_AfficherEcran(1);<nl>"
        "}<nl>"
        "void Frontier_AfficherSonde() {<nl>"
        "  Frontier_Idx = 0;<nl>"
        "  Frontier_AfficherEcran(0);<nl>"
        "}<nl>"
        "void Frontier_SonderNom() {<nl>"
        "  if (!IsInputOk()) { return; }<nl>"
        "  string nom2 = InputResultAsString();<nl>"
        "  var coffre = LocalStructure.GetDevice<IContainer>(nom2);<nl>"
        "  if (coffre == null) { UnityEngine.Debug.Log('APP-LCD: ' + nom2 + "
        "' introuvable'); return; }<nl>"
        "  Frontier_Trace('sonde ' + nom2);<nl>"
        "  Frontier_Nom = nom2;<nl>"
        "  Frontier_Idx = 0;<nl>"
        "  Frontier_AfficherEcran(0);<nl>"
        "}<nl>"
        "void Frontier_TrierTri() {<nl>"
        f"  var src = LocalStructure.GetDevice<IContainer>('{TRI_NAME}');<nl>"
        f"  if (src == null) {{ UnityEngine.Debug.Log('APP-TRI: {TRI_NAME} "
        "introuvable'); return; }<nl>"
        "  Frontier_Trace('trier');<nl>"
        "  int total = 0;<nl>"
        "  int vus = 0;<nl>"
        "  int routes = 0;<nl>"
        "  string sans = '';<nl>"
        "  string pref = AddToGlobalVar('Frontier_Tri_Pref', '');<nl>"
        "  if (pref == null || pref == '') { pref = 'TRI'; }<nl>"
        "  Frontier_Pref = pref;<nl>"
        "  string[] tous = LocalStructure.GetAllCustomDeviceNames();<nl>"
        "  Array.Sort(tous);<nl>"
        "  foreach (var lot in src.GetContent()) {<nl>"
        "    vus = vus + 1;<nl>"
        "    int restant = lot.count;<nl>"
        # 1) APPRIS : le nom de coffre memorise prime sur le classement
        # automatique (coffres libres du joueur : TRI_Armures_A...)
        "    string dest = Frontier_Destin(lot.id);<nl>"
        "    if (dest != null) {<nl>"
        "      var dd = LocalStructure.GetDevice<IContainer>(dest);<nl>"
        "      if (dd != null) {<nl>"
        "        int mvd = Frontier_Deposer(dd, lot.id, restant);<nl>"
        "        UnityEngine.Debug.Log('APP-TRI: appris id=' + lot.id + "
        "' vers ' + dest + ' mv=' + mvd + '/' + restant);<nl>"
        "        if (mvd > 0) {<nl>"
        "          int outd = Frontier_Retirer(src, lot.id, mvd);<nl>"
        "          if (outd < mvd) { Frontier_Retirer(dd, lot.id, "
        "mvd - outd); }<nl>"
        "          total = total + outd;<nl>"
        "          restant = restant - outd;<nl>"
        "        }<nl>"
        "      }<nl>"
        "    }<nl>"
        "    if (restant <= 0) { continue; }<nl>"
        # 2) classement automatique pour ce qui reste
        "    string val3b;<nl>"
        "    if (!Frontier_Valeur(lot.id, out val3b)) { continue; }<nl>"
        "    int code3 = Frontier_Code(val3b);<nl>"
        "    if (code3 < 0) { continue; }<nl>"
        "    routes = routes + 1;<nl>"
        "    string cat = CATS[code3];<nl>"
        "    bool suivi = false;<nl>"
        "    foreach (string nmdev in tous) {<nl>"
        "      if (!nmdev.StartsWith(pref + '_' + cat)) { continue; }<nl>"
        "      var dst = LocalStructure.GetDevice<IContainer>(nmdev);<nl>"
        "      if (dst == null) { continue; }<nl>"
        "      suivi = true;<nl>"
        # depot par Frontier_Deposer : empile sur pile existante, CREE la
        # pile si aucune (le bug mv=0 du 17/11 : le SetContent direct ne
        # transferait que si une pile existait deja dans le coffre cible)
        "      int mv = Frontier_Deposer(dst, lot.id, restant);<nl>"
        "      UnityEngine.Debug.Log('APP-TRI: ajout id=' + lot.id + ' "
        "vers ' + nmdev + ' mv=' + mv + '/' + restant);<nl>"
        "      if (mv > 0) {<nl>"
        "        int out2 = Frontier_Retirer(src, lot.id, mv);<nl>"
        "        if (out2 < mv) { Frontier_Retirer(dst, lot.id, "
        "mv - out2); }<nl>"
        "        total = total + out2; restant = restant - out2;<nl>"
        "        if (out2 <= 0) { break; }<nl>"
        "      }<nl>"
        "      if (restant <= 0) { break; }<nl>"
        "    }<nl>"
        "  }<nl>"
        "  UnityEngine.Debug.Log('APP-TRI: vus=' + vus + ' classes=' + "
        "routes + ' deplaces=' + total + ' sansCoffre=' + sans);<nl>"
        "  string res = 'TRI : ' + total + ' deplaces';<nl>"
        "  if (sans != '') { res = res + '\\nSans coffre :' + sans; }<nl>"
        "  else if (total == 0 && vus > 0) { res = res + '\\nRien a "
        "deplacer'; }<nl>"
        "  string[] ecr = LocalStructure.GetAllCustomDeviceNames();<nl>"
        "  Array.Sort(ecr);<nl>"
        "  foreach (string ne in ecr) {<nl>"
        f"    if (!ne.StartsWith('{LCD_PREFIX}')) {{ continue; }}<nl>"
        "    var le = LocalStructure.GetDevice<ILcd>(ne);<nl>"
        "    if (le != null) { le.SetText(res); }<nl>"
        "  }<nl>"
        "}<nl>"
        "void Frontier_ChargePref() {<nl>"
        "  string p = AddToGlobalVar('Frontier_Tri_Pref', '');<nl>"
        "  if (p == null || p == '') { p = 'TRI'; }<nl>"
        "  Frontier_Pref = p;<nl>"
        "}<nl>"
        "void Frontier_SetPrefix() {<nl>"
        "  if (!IsInputOk()) { return; }<nl>"
        "  string val = InputResultAsString();<nl>"
        "  if (val == null || val == '') { val = 'TRI'; }<nl>"
        "  SetGlobalVar('Frontier_Tri_Pref', val);<nl>"
        "  Frontier_Pref = val;<nl>"
        "  UnityEngine.Debug.Log('APP-TRI: prefix = ' + val);<nl>"
        "}<nl>"
        # remplissage d'UN item : stock cible - present, pioche dans les
        # TRI_<categorie>. Factorise : sert au mode memorise ET au mode
        # historique APPRO_<Item>[_qty].
        "int Frontier_ApproUn(IContainer dsta, int cid, int qty, "
        "string pref, string[] tous) {<nl>"
        "  int deja = 0;<nl>"
        "  foreach (var sta in dsta.GetContent()) { if (Frontier_Cle("
        "sta.id) == cid) { deja = deja + sta.count; } }<nl>"
        "  int manque = qty - deja;<nl>"
        "  if (manque <= 0) { return 0; }<nl>"
        "  string vv; int cdc = -1;<nl>"
        "  if (Frontier_Valeur(cid, out vv)) { cdc = Frontier_Code(vv); }<nl>"
        "  if (cdc < 0) { return 0; }<nl>"
        "  string cat = CATS[cdc];<nl>"
        "  int ops = 0;<nl>"
        "  foreach (string nsa in tous) {<nl>"
        "    if (!nsa.StartsWith(pref + '_' + cat)) { continue; }<nl>"
        "    var srca = LocalStructure.GetDevice<IContainer>(nsa);<nl>"
        "    if (srca == null) { continue; }<nl>"
        "    foreach (var st2 in srca.GetContent()) {<nl>"
        "      if (Frontier_Cle(st2.id) != cid) { continue; }<nl>"
        "      int mv = Frontier_Deposer(dsta, st2.id, manque);<nl>"
        "      if (mv > 0) {<nl>"
        "        int out3 = Frontier_Retirer(srca, st2.id, mv);<nl>"
        "        if (out3 < mv) { Frontier_Retirer(dsta, st2.id, "
        "mv - out3); }<nl>"
        "        ops = ops + out3; manque = manque - out3;<nl>"
        "      }<nl>"
        "      if (manque <= 0) { break; }<nl>"
        "    }<nl>"
        "    if (manque <= 0) { break; }<nl>"
        "  }<nl>"
        "  return ops;<nl>"
        "}<nl>"
        # memorise le contenu ACTUEL d'un coffre : item -> quantite
        # TOUS les coffres APPRO en un clic : indispensable avec un
        # constructeur par craft (20 coffres = 20 saisies sinon). Un
        # coffre VIDE est ignore : il est en cours de craft, on garde sa
        # cible memorisee.
        "void Frontier_ApprMemoriserTout() {<nl>"
        "  Frontier_Trace('memoriser tous');<nl>"
        "  string[] tous = LocalStructure.GetAllCustomDeviceNames();<nl>"
        "  Array.Sort(tous);<nl>"
        "  int n = 0;<nl>"
        "  foreach (string nm in tous) {<nl>"
        "    if (nm != 'APPRO' && !nm.StartsWith('APPRO_')) { continue; }<nl>"
        "    var c = LocalStructure.GetDevice<IContainer>(nm);<nl>"
        "    if (c == null) { continue; }<nl>"
        "    string s = Frontier_ApprSnap(c);<nl>"
        "    if (s == '') { continue; }<nl>"
        "    Frontier_Appr = Frontier_ApprMaj(nm, s);<nl>"
        "    n = n + 1;<nl>"
        "  }<nl>"
        "  SetGlobalVar('Frontier_Appr', Frontier_Appr);<nl>"
        "  UnityEngine.Debug.Log('APP-APPRO: ' + n + ' coffres "
        "memorises');<nl>"
        "}<nl>"
        "void Frontier_ApprMemoriser() {<nl>"
        "  Frontier_Trace('memoriser un');<nl>"
        "  if (!IsInputOk()) { return; }<nl>"
        "  string nom = InputResultAsString();<nl>"
        "  var c = LocalStructure.GetDevice<IContainer>(nom);<nl>"
        "  if (c == null) { UnityEngine.Debug.Log('APP-APPRO: ' + nom + "
        "' introuvable'); return; }<nl>"
        "  Frontier_Appr = Frontier_ApprMaj(nom, Frontier_ApprSnap(c));<nl>"
        "  SetGlobalVar('Frontier_Appr', Frontier_Appr);<nl>"
        "  UnityEngine.Debug.Log('APP-APPRO: ' + nom + ' memorise');<nl>"
        "}<nl>"
        "void Frontier_Approvisionner() {<nl>"
        "  Frontier_Trace('appro');<nl>"
        # HORS ETAT (CallLater de l'auto) : AddToGlobalVar echoue -> la
        # fonction mourait a sa premiere ligne et l'auto ne faisait rien
        # (vecu 18/11). Frontier_Pref est le miroir static, charge a
        # l'entree du hub.
        "  string pref = Frontier_Pref;<nl>"
        "  if (pref == null || pref == '') { pref = 'TRI'; }<nl>"
        "  string[] tous = LocalStructure.GetAllCustomDeviceNames();<nl>"
        "  Array.Sort(tous);<nl>"
        "  int ops = 0;<nl>"
        "  foreach (string nma in tous) {<nl>"
        "    if (nma != 'APPRO' && !nma.StartsWith('APPRO_')) { continue; "
        "}<nl>"
        "    var dsta = LocalStructure.GetDevice<IContainer>(nma);<nl>"
        "    if (dsta == null) { continue; }<nl>"
        # 1) coffre MEMORISE : liste id:qty -> plusieurs items par coffre
        "    string lst = Frontier_ApprDe(nma);<nl>"
        "    if (lst != null) {<nl>"
        "      int p = 0;<nl>"
        "      while (p < lst.Length) {<nl>"
        "        int f = lst.IndexOf(',', p);<nl>"
        "        if (f < 0) { f = lst.Length; }<nl>"
        "        string paire = lst.Substring(p, f - p);<nl>"
        "        int c2 = paire.IndexOf(':');<nl>"
        "        if (c2 > 0) {<nl>"
        "          int cid2 = int.Parse(paire.Substring(0, c2));<nl>"
        "          int q2 = int.Parse(paire.Substring(c2 + 1));<nl>"
        "          ops = ops + Frontier_ApproUn(dsta, cid2, q2, pref, "
        "tous);<nl>"
        "        }<nl>"
        "        p = f + 1;<nl>"
        "      }<nl>"
        "      continue;<nl>"
        "    }<nl>"
        # 2) mode historique : APPRO_<Item>[_qty]
        "    string spec = nma.Substring(5);<nl>"
        "    if (spec.StartsWith('_')) { spec = spec.Substring(1); }<nl>"
        "    int qty = 1000;<nl>"
        "    int uss = spec.LastIndexOf('_');<nl>"
        "    if (uss > 0) {<nl>"
        "      string fin = spec.Substring(uss + 1);<nl>"
        "      bool tst = fin.Length > 0;<nl>"
        "      foreach (char ch in fin) { if "
        "('0123456789'.IndexOf(ch) < 0) { tst = false; } }<nl>"
        "      if (tst) { qty = int.Parse(fin); spec = "
        "spec.Substring(0, uss); }<nl>"
        "    }<nl>"
        "    int cid; int cdc;<nl>"
        "    if (!Frontier_Trouver(spec, out cid, out cdc)) { continue; }<nl>"
        "    if (cdc < 0) { continue; }<nl>"
        "    ops = ops + Frontier_ApproUn(dsta, cid, qty, pref, tous);<nl>"
        "  }<nl>"
        "  UnityEngine.Debug.Log('APP-APPRO: ' + ops + ' items "
        "deplaces');<nl>"
        "}<nl>"
        "void Frontier_ApproAuto() {<nl>"
        "  if (!Frontier_AutoOn) { return; }<nl>"
        "  UnityEngine.Debug.Log('APP-APPRO: tick auto');<nl>"
        "  Frontier_Approvisionner();<nl>"
        "  CallLater(300.0f, Frontier_ApproAuto);<nl>"
        "}<nl>"
        "void Frontier_AutoMarche() {<nl>"
        "  Frontier_AutoOn = true;<nl>"
        "  UnityEngine.Debug.Log('APP-APPRO: auto demarre');<nl>"
        "  Frontier_ApproAuto();<nl>"
        "}<nl>"
        "void Frontier_AutoStop() {<nl>"
        "  Frontier_AutoOn = false;<nl>"
        "  UnityEngine.Debug.Log('APP-APPRO: auto stoppe');<nl>"
        "}<nl>"
        "void Frontier_ListerCats() {<nl>"
        "  string pref2 = AddToGlobalVar('Frontier_Tri_Pref', '');<nl>"
        "  if (pref2 == null || pref2 == '') { pref2 = 'TRI'; }<nl>"
        "  string s = 'Coffres de tri :';<nl>"
        "  foreach (string c in CATS) { s = s + '\\n' + pref2 + '_' + c; "
        "}<nl>"
        "  string[] ec = LocalStructure.GetAllCustomDeviceNames();<nl>"
        "  Array.Sort(ec);<nl>"
        "  foreach (string n2 in ec) {<nl>"
        f"    if (!n2.StartsWith('{LCD_PREFIX}')) {{ continue; }}<nl>"
        "    var l3 = LocalStructure.GetDevice<ILcd>(n2);<nl>"
        "    if (l3 != null) { l3.SetText(s); }<nl>"
        "  }<nl>"
        "}<nl>"
        "void Frontier_ListeAide() {<nl>"
        "  Frontier_Trace('aide atelier');<nl>"
        "  OpenHtmlWindow('Console atelier - aide', "
        f"'%SHARED_DATA%/{AIDE_FILE}', 0.14f, 0.14f, 0.72f, "
        "0.80f);<nl>"
        "}")
    hub = ('{ +Dialogue Name: Frontier_AppAtelier\n'
           '  NPCName: "Console d\'atelier"\n'
           + _vars_memoire() +
           '  Output: "Atelier : liez vos blocs par leur NOM. Le tri '
           'ventile par sous-categorie (voir LISTER). RAFRAÎCHIR relance '
           f'le defilement ({LCD_SCROLL_S} s)."\n'
           f'  Functions: "{fonc}"\n'
           # charge le prefixe dans le miroir static DES L'ENTREE : l'auto
           # (CallLater) lit Frontier_Pref hors etat, ou AddToGlobalVar
           # echoue. Sans ca l'auto ne faisait rien (vecu 18/11).
           "  Execute: \"Frontier_ChargePref(); Frontier_Trace('atelier');\"\n"
           '  Option_1: "RAFRAÎCHIR / relancer l\'écran"\n'
           '  OptionExecute_1: "Frontier_AfficherSonde()"\n'
           '  OptionNext_1: Frontier_AppAtelier\n'
           '  Option_2: "TRIER le coffre TRI"\n'
           '  OptionExecute_2: "Frontier_TrierTri()"\n'
           '  OptionNext_2: Frontier_AppAtelier_TriOk\n'
           '  Option_3: "SONDER un container (par nom)"\n'
           '  OptionNext_3: Frontier_AppAtelier_Sonder\n'
           '  Option_4: "CHANGER le prefix de tri"\n'
           '  OptionNext_4: Frontier_AppAtelier_Pref\n'
           '  Option_5: "LISTER les coffres de tri"\n'
           '  OptionExecute_5: "Frontier_ListerCats()"\n'
           '  OptionNext_5: Frontier_AppAtelier\n'
           '  Option_6: "APPRENDRE mes rangements"\n'
           '  OptionNext_6: Frontier_AppAtelier_Apprendre\n'
           '  Option_7: "AIDE"\n'
           '  OptionNext_7: Frontier_AppAtelier_AideOuverture\n'
           '  Option_8: "APPROVISIONNER les coffres de craft"\n'
           '  OptionNext_8: Frontier_AppAtelier_Appro\n'
           '  Option_9: "Quitter"\n'
           '  OptionNext_9: End\n'
           '}\n'
           '{ +Dialogue Name: Frontier_AppAtelier_Apprendre\n'
           '  NPCName: "Console d\'atelier"\n'
           '  Output: "Apprentissage : rangez les objets dans les bons '
           'coffres TRI_*, puis APPRENDRE memorise vos choix."\n'
           f'  Functions: "{_fonc_apprendre()}"\n'
           '  Execute: "Frontier_Apprendre();"\n'
           '  Option_1: "OUBLIER la memoire"\n'
           '  OptionExecute_1: "Frontier_Oublier()"\n'
           '  OptionNext_1: Frontier_AppAtelier\n'
           '  Option_2: "Retour"\n'
           '  OptionNext_2: Frontier_AppAtelier\n'
           '}\n'
           '{ +Dialogue Name: Frontier_AppAtelier_AideOuverture\n'
           '  NPCName: "Console d\'atelier"\n'
           '  Output: "Ouverture de l\'aide — patientez quelques '
           'secondes."\n'
           '  Functions: "void Frontier_AideOuvrir() {<nl>  '
           "Frontier_Trace('aide html');<nl>  "
           'OpenHtmlWindow(\'Console atelier - aide\', '
           f"'%SHARED_DATA%/{AIDE_FILE}', 0.14f, 0.14f, 0.72f, "
           '0.80f);<nl>}"\n'
           '  Execute: "Frontier_AideOuvrir();"\n'
           '  Option_1: "Retour"\n'
           '  OptionNext_1: Frontier_AppAtelier\n'
           '}\n'
           '{ +Dialogue Name: Frontier_AppAtelier_Appro\n'
           '  NPCName: "Console d\'atelier"\n'
           '  Output: "Maintient a niveau les containers APPRO_<Item>, '
           'ou un coffre APPRO memorise (plusieurs items)."\n'
           '  Option_1: "APPROVISIONNER"\n'
           '  OptionExecute_1: "Frontier_Approvisionner()"\n'
           '  OptionNext_1: Frontier_AppAtelier_Appro\n'
           '  Option_2: "DEMARRER l auto (toutes les 5 min)"\n'
           '  OptionExecute_2: "Frontier_AutoMarche()"\n'
           '  OptionNext_2: Frontier_AppAtelier_Appro\n'
           '  Option_3: "ARRETER l auto"\n'
           '  OptionExecute_3: "Frontier_AutoStop()"\n'
           '  OptionNext_3: Frontier_AppAtelier_Appro\n'
           '  Option_4: "MEMORISER TOUS les coffres APPRO"\n'
           '  OptionExecute_4: "Frontier_ApprMemoriserTout()"\n'
           '  OptionNext_4: Frontier_AppAtelier_Appro\n'
           '  Option_5: "MEMORISER UN coffre APPRO (par nom)"\n'
           '  OptionNext_5: Frontier_AppAtelier_ApproMem\n'
           '  Option_6: "Retour"\n'
           '  OptionNext_6: Frontier_AppAtelier\n'
           '}\n'
           '{ +Dialogue Name: Frontier_AppAtelier_ApproMem\n'
           '  NPCName: "Console d\'atelier"\n'
           '  Output: "Remplissez un coffre a la main (plusieurs items et '
           'quantites), nommez-le APPRO, puis tapez son nom : ce contenu '
           'deviendra la cible, rechargee depuis les coffres TRI."\n'
           '  Input: "Nom du coffre APPRO :"\n'
           '  Option_1: "MEMORISER ce contenu"\n'
           '  OptionExecute_1: "Frontier_ApprMemoriser()"\n'
           '  OptionNext_1: Frontier_AppAtelier_Appro\n'
           '  Option_2: "Retour"\n'
           '  OptionNext_2: Frontier_AppAtelier_Appro\n'
           '}\n'
           '{ +Dialogue Name: Frontier_AppAtelier_Pref\n'
           '  NPCName: "Console d\'atelier"\n'
           '  Output: "Tapez le nouveau prefixe ; vide = TRI."\n'
           '  Input: "Nouveau prefix de tri :"\n'
           '  Option_1: "APPLIQUER"\n'
           '  OptionExecute_1: "Frontier_SetPrefix()"\n'
           '  OptionNext_1: Frontier_AppAtelier\n'
           '  Option_2: "Retour"\n'
           '  OptionNext_2: Frontier_AppAtelier\n'
           '}\n'
           '{ +Dialogue Name: Frontier_AppAtelier_Sonder\n'
           '  NPCName: "Console d\'atelier"\n'
           '  Output: "Tapez le nom du container à afficher."\n'
           '  Input: "Nom du container a sonder :"\n'
           '  Option_1: "AFFICHER"\n'
           '  OptionExecute_1: "Frontier_SonderNom()"\n'
           '  OptionNext_1: Frontier_AppAtelier_Sonder\n'
           '  Option_2: "Retour"\n'
           '  OptionNext_2: Frontier_AppAtelier\n'
           '}\n'
           '{ +Dialogue Name: Frontier_AppAtelier_TriOk\n'
           '  NPCName: "Console d\'atelier"\n'
           '  Output: "Tri effectué."\n'
           '  Option_1: "Retour"\n'
           '  OptionNext_1: Frontier_AppAtelier\n'
           '}')
    return hub


def _write_dialogues(sc: Path, info: dict) -> None:
    dlg = _read(sc / 'Dialogues.ecf').rstrip('\n')
    i_tr = dlg.find(TRADERS_MARKER)
    i_ap = dlg.find(APPS_MARKER)
    if 0 <= i_tr < i_ap:
        i_ap = -1
    if i_ap >= 0:
        tete = dlg[:i_ap].rstrip('\n')
    elif i_tr >= 0:
        tete = dlg[:i_tr].rstrip('\n')
    else:
        tete = dlg
    suite = dlg[i_tr:].rstrip('\n') if i_tr >= 0 else ''
    partie = APPS_MARKER + '\n' + _arbre(info)
    if suite:
        nouveau = tete + '\n\n' + partie + '\n\n' + suite + '\n'
    else:
        nouveau = tete + '\n\n' + partie + '\n'
    _write(sc / 'Dialogues.ecf', nouveau)


def _merge_loc_apps(loc_text: str) -> str:
    """Reecrit les libelles des blocs atelier, idempotent. Purge limitee
    aux cles de LOCS_ATELIER et a SON commentaire de section : ceux du
    commerce survivent."""
    propres = {k for k, _en, _fr in LOCS_ATELIER}
    kept = [ln for ln in loc_text.rstrip('\n').splitlines()
            if ln.split(',')[0].strip('"') not in propres
            and not ln.strip().startswith('# ===== Console atelier')]
    kept += ['', '# ===== Console atelier Frontier-FR =====']
    kept += [_csv_row(k, en, fr) for k, en, fr in LOCS_ATELIER]
    return '\n'.join(kept) + '\n'


def regen_apps(scenario_root: str | Path) -> dict:
    root = Path(scenario_root)
    sc = root / 'Content' / 'Configuration'
    info = _catalogue(_read(sc / 'ItemsConfig.ecf'),
                      _read(sc / 'BlocksConfig.ecf'),
                      _read(sc / 'TraderNPCConfig.ecf'))
    blocks_new, blk_added = _merge_blocks(_read(sc / 'BlocksConfig.ecf'))
    _write(sc / 'BlocksConfig.ecf', blocks_new)
    tpl_new, tpl_added = _merge_templates(_read(sc / 'Templates.ecf'))
    _write(sc / 'Templates.ecf', tpl_new)
    _write_dialogues(sc, info)
    par_cat: dict = {}
    for val in info.values():
        code = val.split('|', 1)[0]
        if int(code) >= 0:
            par_cat[CATS[int(code)]] = par_cat.get(CATS[int(code)], 0) + 1
    aide = root / 'SharedData' / AIDE_FILE
    aide.parent.mkdir(parents=True, exist_ok=True)
    aide.write_text(_aide_html(par_cat), encoding='utf-8')
    loc = root / 'Extras' / 'Localization.csv'
    loc.parent.mkdir(parents=True, exist_ok=True)
    _write(loc, _merge_loc_apps(
        loc.read_text(encoding='utf-8-sig') if loc.is_file() else ''))
    return {'apps_items': len(info), 'apps_routes': len(info),
            'apps_block': blk_added, 'apps_template': tpl_added}