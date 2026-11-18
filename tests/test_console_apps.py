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

"""APPS de console : LCD inventaire + tri de coffres — regen fusion,
exclusion des armes, preservation croisee avec la section traders."""
import re
import subprocess
from pathlib import Path

import pytest

from core.console_apps import APPS_MARKER, regen_apps
from core.console_traders import MARKER, regen

ITEMS = """# ItemsConfig
{ +Item Id: 100, Name: IronOre, Ref: OreTemplate
  MarketPrice: 10, display: true
}
{ +Item Id: 101, Name: IronIngot, Ref: ComponentsTemplate
  Mass: 5.9, MarketPrice: 6.5, display: true
}
{ +Item Id: 102, Name: Electronics, Ref: ComponentsTemplate
  Mass: 1, MarketPrice: 90, display: true
}
{ +Item Id: 103, Name: PulseLaser, Ref: GunsTemplate
  MarketPrice: 9000, display: true
  Category: Weapons
}
{ +Item Id: 104, Name: Berries, Ref: FoodTemplate
  MarketPrice: 5, display: true
  Category: Food
}
"""

TRADERS = """{ Trader Name: Talon
  SellingText: "hello"
  Item1: "IronOre, 10, 500, 5, 500"
}
"""

BLOCKS = """# BlocksConfig
{ +Block Id: 258, Name: ConsoleTrading
  Class: NPCDialogue
  Category: Devices
}
{ +Block Id: 259, Name: SteelWall01
  Category: BuildingBlocks
}
{ +Block Id: 260, Name: PlantPot01
  Class: Deco
  Category: Deco
}
{ +Block Id: 261, Name: TurretPlasmaCV
  Class: TurretManual
  Category: Weapons
}
"""

TEMPLATES = """# Templates
{ +Template Name: GeneratorBA
  Target: "SurvC"
}
"""

DIALOGUES = """{ +Dialogue Name: Vanilla_Node
  Option_1: "Salut"
  OptionNext_1: End
}
"""

LOC = ('KEY,English,Deutsch,Français,Italiano,Spanish,'
       'Portuguese (Euro),Portuguese (Brazil),Polish,Russian,'
       'Japanese,Chinese (simplified),Chinese (traditional),Korean,'
       'Turkish,Greek,Dutch,Vietnamese\n'
       'SomeKey,en,de,fr,it,es,pt,ptb,pl,ru,jp,zh,zht,ko,tr,el,nl,vi\n')


@pytest.fixture
def scenario(tmp_path):
    sc = tmp_path / 'Content' / 'Configuration'
    sc.mkdir(parents=True)
    (sc / 'ItemsConfig.ecf').write_text(ITEMS, encoding='utf-8')
    (sc / 'BlocksConfig.ecf').write_text(BLOCKS, encoding='utf-8')
    (sc / 'Templates.ecf').write_text(TEMPLATES, encoding='utf-8')
    (sc / 'TraderNPCConfig.ecf').write_text(TRADERS, encoding='utf-8')
    (sc / 'Dialogues.ecf').write_text(DIALOGUES, encoding='utf-8')
    extras = tmp_path / 'Extras'
    extras.mkdir()
    (extras / 'Localization.csv').write_text(LOC, encoding='utf-8')
    return tmp_path


def _read(root, rel):
    return (root / rel).read_text(encoding='utf-8')


def test_apps_premiere_passe(scenario):
    report = regen_apps(scenario)
    assert report['apps_items'] >= 1        # IronOre route
    assert report['apps_block'] == 2        # console principale + compacte
    assert report['apps_template'] == 2
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert APPS_MARKER in dlg and 'Frontier_AppAtelier' in dlg
    # LCD : multi-ecrans par prefixe, lookup double +8192, ID+Nom+Qte,
    # scroll auto (CallLater chaine) relance par RAFRAÎCHIR
    assert "GetDevice<ILcd>(nmec)" in dlg
    assert "GetDevice<IContainer>(cible2)" in dlg
    # pas d'id sur les lignes nommees (illisible) : nom + quantite
    assert "'\\n' + Frontier_NomItem(val2)" in dlg
    # nom affiche = Loc(nom interne) : la cle de Localization.csv EST le nom
    # interne de l'item -> langue du jeu, repli sur la chaine si absente
    assert 'Loc(v.Substring' in dlg and 'Frontier_NomItem' in dlg
    assert 'CallLater(5.0f, Frontier_ScrollSuivant)' in dlg
    # etat du defilement en champs static : la boucle CallLater s'execute
    # HORS etat de dialogue, ou AddToGlobalPfVar echoue (NOT NULL sur
    # DialogueVars.state, vecu 16/11 : ecran bloque en page 1)
    assert 'static int Frontier_Idx' in dlg
    assert 'static string Frontier_Nom' in dlg
    assert 'GlobalPfVar' not in dlg
    # chaque ecran AFFICHAGE_<Nom> est lie a son propre coffre
    assert "nmec.StartsWith('AFFICHAGE_')" in dlg
    assert 'nmec.Substring(10)' in dlg
    # sonde par nom saisi (Input du state + InputResultAsString)
    assert 'Input: "Nom du container a sonder :"' in dlg
    assert 'Frontier_SonderNom' in dlg and 'InputResultAsString()' in dlg
    # tri multi-coffres par prefixe + prefixe configurable en jeu
    assert 'GetAllCustomDeviceNames' in dlg and 'Array.Sort(tous)' in dlg
    assert "nmdev.StartsWith(pref + '_' + cat)" in dlg
    assert 'Frontier_SetPrefix' in dlg and "SetGlobalVar('Frontier_Tri_Pref'" in dlg
    # depot par Frontier_Deposer : AddItems retourne le RESTANT (0 = tout
    # entre) et cree la pile si aucune n'existe — le SetContent direct ne
    # transferait que si une pile existait deja (bug mv=0 du 17/11)
    assert 'int mv = Frontier_Deposer(dst, lot.id, restant);' in dlg
    assert 'dst.SetContent(dl)' not in dlg
    # fallback : slot libre explicite (un slotIdx pris ecraserait la pile)
    assert 'st.slotIdx = (byte)ns;' in dlg
    # retrait MESURE : RemoveItems n'est pas symetrique de AddItems (id
    # runtime vs config) — vecu 17/11, le tri copiait au lieu de deplacer
    assert 'int Frontier_Retirer(IContainer c, int id, int qty)' in dlg
    # SetContent (et non RemoveItems, qui ne retire rien sur ces
    # containers) : on reecrit le contenu sans les quantites retirees
    assert 'c.SetContent(neuf)' in dlg and 'List<ItemStack>' in dlg
    # la destination ne garde que ce qui a REELLEMENT quitte la source
    assert 'Frontier_Retirer(dst, lot.id, mv - out2)' in dlg
    # APPRENTISSAGE : la memoire (coffres TRI_*) prime sur la classification
    assert 'Frontier_AppAtelier_Apprendre' in dlg
    assert 'void Frontier_Apprendre()' in dlg
    # la destination APPRISE est le NOM du coffre, pas une sous-categorie :
    # tout container <prefix>_* est reconnu (TRI_Armures_A, TRI_Carburant_A
    # etaient ignores par l'ancien apprentissage par categorie, vecu 17/11)
    assert "SetGlobalVar('Frontier_Dest', dest)" in dlg
    assert 'string Frontier_Destin(int id)' in dlg
    assert 'string dest = Frontier_Destin(lot.id);' in dlg
    assert "dest = dest + st.id + '=' + nd + ','" in dlg
    assert 'Variable_1: "Frontier_Dest", param1: dbplayer_string' in dlg
    # la memoire est LUE via une variable dbplayer_string : AddToGlobalVar
    # ne renvoie pas le contenu stocke (seulement la valeur ajoutee)
    assert 'param1: dbplayer_string' in dlg
    assert 'void Frontier_Oublier()' in dlg


def test_noms_a_point_et_commentaires(scenario):
    """Vecu 17/11 : un `Name: (\\w+)` casse les noms a point
    (5.8mmBullet -> "5", donc munition non classee) et laisse passer les
    commentaires de fin de ligne. Le meme defaut faisait disparaitre ces
    munitions du catalogue des traders."""
    from core.console_apps import CATS, _catalogue
    sc = scenario / 'Content' / 'Configuration'
    (sc / 'ItemsConfig.ecf').write_text(
        ITEMS.replace('{ +Item Id: 104, Name: Berries',
                      '{ +Item Id: 105, Name: 5.8mmBullet, Ref: 50Caliber\n'
                      '  MarketPrice: 1\n'
                      '}\n{ +Item Id: 106, Name: Shotgun   # T1\n'
                      '  Category: Weapons\n'
                      '}\n{ +Item Id: 104, Name: Berries'),
        encoding='utf-8')
    f = scenario / 'Content/Configuration'
    info = _catalogue((f / 'ItemsConfig.ecf').read_text(encoding='utf-8'),
                      (f / 'BlocksConfig.ecf').read_text(encoding='utf-8'),
                      (f / 'TraderNPCConfig.ecf').read_text(encoding='utf-8'))
    assert info[105] == f'{CATS.index("Munitions")}|5.8mmBullet'
    assert info[106] == f'{CATS.index("ArmesJoueur")}|Shotgun'


def test_aide_html_generee(scenario):
    """La console ouvre une fenetre d'aide (%SHARED_DATA%, relatif au
    scenario donc embarque au Workshop) dont le tableau liste EXACTEMENT
    les containers a creer, derives de CATS."""
    from core.console_apps import AIDE_FILE, CATS
    regen_apps(scenario)
    aide = scenario / 'SharedData' / AIDE_FILE
    assert aide.is_file()
    html = aide.read_text(encoding='utf-8')
    for c in CATS:                       # une ligne par sous-categorie
        assert f'TRI_{c}</code>' in html
    assert 'SharedData' not in html       # autonome : aucun asset externe
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert f"'%SHARED_DATA%/{AIDE_FILE}'" in dlg
    assert 'Functions: "void Frontier_AideOuvrir' in dlg
    assert 'Execute: "Frontier_AideOuvrir();"' in dlg
    assert 'Frontier_AppAtelier_AideOuverture' in dlg


def test_approvisionnement_appro(scenario):
    """Option APPROVISIONNER : les containers APPRO_<Item>[_qty] (defaut
    1000) sont maintenus a niveau depuis les coffres TRI_<categorie>."""
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert 'Frontier_AppAtelier_Appro' in dlg
    assert "nma.StartsWith('APPRO_')" in dlg
    assert 'Frontier_Approvisionner' in dlg and 'Frontier_Trouver' in dlg
    # quantite par suffixe numerique, defaut 1000
    assert 'int qty = 1000;' in dlg
    assert 'int.Parse(fin)' in dlg
    # pioche dans les TRI_<cat> de l'item, a hauteur du manque seulement
    assert "nsa.StartsWith(pref + '_' + cat)" in dlg
    assert 'qty - deja' in dlg
    # l'aide documente la convention
    html = (scenario / 'SharedData' / 'Console_Aide.html').read_text(
        encoding='utf-8')
    assert 'APPRO_&lt;Item&gt;' in html and 'APPRO_CopperIngot_500' in html


def test_appro_auto_et_aide_avec_patientez(scenario):
    """AUTO toutes les 5 min : boucle CallLater chainee (comme le scroll),
    drapeau static pour stopper ; le prefix passe par le miroir static car
    un callback CallLater n'a pas le droit de toucher aux vars de dialogue.
    L'aide passe par un state intermediaire 'patientez' (page blanche au
    premier lancement, vecu 17/11)."""
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert 'Frontier_ApproAuto' in dlg and 'Frontier_Oublier' in dlg and 'Frontier_AutoMarche' in dlg
    assert 'CallLater(300.0f, Frontier_ApproAuto)' in dlg
    assert 'static bool Frontier_AutoOn' in dlg
    assert 'static string Frontier_Pref' in dlg
    assert 'Frontier_AutoStop' in dlg
    # state d'ouverture : message d'attente + Functions OpenHtmlWindow
    assert 'Frontier_AppAtelier_AideOuverture' in dlg
    assert 'patientez quelques secondes' in dlg
    # Functions = declaration ; Execute (state) = declencheur d'entree
    assert 'Functions: "void Frontier_AideOuvrir' in dlg
    assert 'Execute: "Frontier_AideOuvrir();"' in dlg


def test_aide_commerce_generee(scenario):
    """Guide HTML de la console commercante, option AIDE sur les DEUX hubs
    (T1 et T2), ouvert via un state 'patientez'."""
    regen(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    # hub T1 (le T2 n'existe que si AncientRelics est declare : relic_ok) ;
    # numerotation contigue : l'aide est en 3 sur T1, en 4 sur T2
    assert 'OptionNext_3: Frontier_THub_aide\n' in dlg
    assert 'patientez quelques secondes' in dlg
    html = (scenario / 'SharedData' / 'Console_Commerce_Aide.html'
            ).read_text(encoding='utf-8')
    assert 'VENTE' in html and 'licence' in html.lower()
    assert 'patientez' in html.lower()



def test_sous_categories_reelles(scenario):
    """Vecu 16/11 : la classification fine vient du Ref (minerais, lingots)
    AVANT la Category — ces items n'ont pas de champ Category et sortaient
    a 0. Les blocs se classent par leur Category du BlocksConfig."""
    from core.console_apps import CATS, regen_apps
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    code = {c: i for i, c in enumerate(CATS)}
    # dictionnaire unique id -> "<code>|<NomInterne>"
    # format compact : {id,'code|Nom'} pour les items, {100000+id,code} pour les blocs
    routes = {int(i): int(c) for i, c in
              re.findall(r"\{(\d+),'(\d+)\|", dlg)}
    noms = {int(i): n for i, n in
            re.findall(r"\{(\d+),'\d+\|([^']+)'\}", dlg)}
    assert routes[100] == code['Minerais']      # Ref: OreTemplate
    assert routes[101] == code['Lingots']       # ...Ingot
    assert routes[102] == code['Composants']    # ComponentsTemplate autre
    assert routes[103] == code['ArmesJoueur']   # Category: Weapons (item)
    assert routes[104] == code['Nourriture']
    # BLOCS : cle 100000+id — sans elle un bloc heritait de la categorie
    # de l'item homonyme (sieges passagers classes Minerais, vecu 17/11)
    blocs = {int(i): int(c) for i, c in
             re.findall(r"\{\s*(1\d{5}),'(\d+)'\s*\}", dlg)}
    assert blocs[100258] == code['Devices']     # blocs par Category
    assert blocs[100259] == code['Blocs']
    assert blocs[100260] == code['Deco']
    assert blocs[100261] == code['ArmesCV']     # tourelle = arme vaisseau
    # le nom interne accompagne chaque id (cle de Loc() a l'affichage)
    assert noms[100] == 'IronOre' and noms[103] == 'PulseLaser'
    # le tableau des libelles est genere dans le C#
    assert "'Minerais'" in dlg and "'Lingots'" in dlg and "'Deco'" in dlg
    # bloc + recette de la console d'atelier
    blocks = _read(scenario, 'Content/Configuration/BlocksConfig.ecf')
    assert 'Name: Frontier_Console_Atelier' in blocks
    assert re.search(r'\{ \+Block Id: 207,', blocks)
    tpl = _read(scenario, 'Content/Configuration/Templates.ecf')
    assert '+Template Name: Frontier_Console_Atelier' in tpl
    # le contenu vanilla est preserve
    assert 'Vanilla_Node' in dlg and 'ConsoleTrading' in blocks


def test_classe_functions_compile_membres_uniques(scenario):
    """Vecu 17/11 (plus rien ne marchait en jeu, classe morte) :
    (1) fonc_sonder/fonc_triok construits mais jamais injectes -> infosB..E
    references par Frontier_Valeur SANS declaration -> classe morte ;
    (2) Frontier_AutoOn declare 2 fois (static + simple) -> CS0102 -> classe
    morte. Tout membre C# du bloc Functions doit etre declare UNE fois."""
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    hub = next(f for f in re.findall(r'Functions: "([^"]*)"', dlg)
               if 'Frontier_TrierTri' in f)
    for n in ('infosA', 'infosB', 'infosC', 'infosD', 'infosE'):
        assert hub.count(f'Dictionary<int, string> {n} = ') == 1
    # declarations de niveau 0 (les locals des corps sont indentees)
    membres = [m for l in hub.split('<nl>') for m in re.findall(
        r"^(?:static )?(?:void|bool|int|string|Dictionary<[^>]+>)"
        r"\s+(\w+)\s*[=(]", l)]
    doublons = {m for m in membres if membres.count(m) > 1}
    assert not doublons, f'membres C# declares 2 fois : {doublons}'
    # toute fonction APPELEE est declaree (CS0103 = arbre mort). Vecu 17/11
    # soir : Frontier_Trouver (recherche inverse nom -> id de l'APPRO)
    # avait disparu dans la reecriture, tout l'atelier etait mort.
    appelees = set(re.findall(r'\b(Frontier_\w+)\s*\(', hub))
    declarees = set(re.findall(
        r'(?:void|bool|int|string|Dictionary<[^>]+>)\s+(Frontier_\w+)\s*\(',
        hub))
    assert not appelees - declarees, f'appelees non declarees : {appelees - declarees}'
    assert 'bool Frontier_Trouver(string nom, out int id, out int code)' in dlg
    # UNE seule variable de memoire, declaree dans UN SEUL etat de l'arbre :
    # une 2e declaration = CS0102, classe morte, console VIDE
    assert dlg.count('Variable_1: "Frontier_Dest"') == 1


CSC = r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
# API runtime fournies par le moteur aux dialogues (base commune des
# classes generees) : stubs suffisants pour compiler le code produit.
STUBS_CS = '''
using System;
using System.Collections.Generic;
using UnityEngine;
using Eleon.Modding;

namespace UnityEngine { public static class Debug {
  public static void Log(object o) { }
  public static void LogWarningFormat(string s, params object[] a) { } } }

namespace Eleon.Modding {
  public class ItemStack {
    public byte slotIdx; public int id; public int count;
    public int ammo; public int decay;
    public ItemStack(int id, int count) { this.id = id; this.count = count; } }
  public interface IContainer {
    List<ItemStack> GetContent();
    void SetContent(List<ItemStack> l);
    int AddItems(int type, int count);
    int RemoveItems(int type, int count); }
  public interface ILcd { void SetText(string s); } }

public class PlayerStub { public int Credit; public int UpgradePoints; }
public class LocalStructureStub {
  public T GetDevice<T>(string n) where T : class { return null; }
  public string[] GetAllCustomDeviceNames() { return new string[0]; } }

public class DialogueBase {
  protected LocalStructureStub LocalStructure = new LocalStructureStub();
  protected PlayerStub Player = new PlayerStub();
  protected string Loc(string k) { return k; }
  protected string AddToGlobalVar(string k, string v) { return v; }
  protected int AddToGlobalVar(string k, int v) { return v; }
  protected void SetGlobalVar(string k, string v) { }
  protected void SetGlobalVar(string k, int v) { }
  protected void CallLater(float s, Action f) { }
  protected bool IsInputOk() { return false; }
  protected string InputResultAsString() { return ""; }
  protected int InputResultAsInt() { return 0; }
  protected bool HasItem(string n, int q) { return false; }
  protected void AddItem(string n, int q) { }
  protected void RemoveItem(string n, int q) { }
  protected List<object> GetItems() { return new List<object>(); }
  protected void OpenHtmlWindow(string t, string u, float a, float b,
                                float c, float d) { } }
'''


def cs_arbres(dlg: str, blocs: str) -> str:
    """C# des classes de dialogue, tel que le compilateur du jeu le voit.

    Le moteur fusionne les Variable_N ET les Functions de TOUS les etats
    d'un ARBRE dans une seule classe : une classe par arbre atteignable
    depuis nos blocs. Le pre-processeur du jeu est rejoue (<nl> -> saut de
    ligne, apostrophe -> guillemet : sans cette conversion les litteraux
    donnent CS1012) et le TYPE des variables suit param1 (le code assigne
    des int aux dbplayer_int : CS0029 sinon)."""
    etats = {}
    for m in re.finditer(r'\{ \+Dialogue Name: (\S+)\n(.*?)'
                         r'(?=\n\{ \+Dialogue|\Z)', dlg, re.S):
        corps = m.group(2)
        f = re.search(r'^  Functions: "([^"]*)"', corps, re.M)
        etats[m.group(1)] = (
            [c.strip().strip('"') for c in re.findall(
                r'^  (?:OptionNext|Next)_\d+: (\S+)', corps, re.M)
             if c.strip() != 'End'],
            re.findall(r'Variable_\d+: "([^"]+)"(?:,\s*param1: (\w+))?',
                       corps),
            f.group(1) if f else '')
    debuts = {d for b in re.findall(
        r'\{ \+?Block Id: \d+, Name: Frontier_\w+\n(.*?)(?=\n\{ |\Z)',
        blocs, re.S) for d in re.findall(r'^  DialogueState: (\S+)', b, re.M)}
    classes = []
    for debut in sorted(debuts):
        vus, pile = set(), [debut]
        while pile:
            n = pile.pop()
            if n in vus or n not in etats:
                continue
            vus.add(n)
            pile.extend(etats[n][0])
        champs = sorted({(v, 'int' if p == 'dbplayer_int' else 'string')
                         for n in vus for v, p in etats[n][1]})
        if not champs and not any(etats[n][2] for n in vus):
            continue
        code = '\n'.join(etats[n][2].replace('<nl>', '\n').replace("'", '"')
                         for n in sorted(vus))
        # shortcut: csc du Framework = C# 5, le jeu compile en Roslyn —
        # neutralise le null-conditional (`?.`), upgrader vers Roslyn si
        # un autre operateur recent apparait dans le code genere.
        code = code.replace('?.', '.')
        classes.append(f'public class Dlg_{debut} : DialogueBase {{\n'
                       + '\n'.join(f'  {t} {v};' for v, t in champs)
                       + f'\n{code}\n}}')
    return '\n'.join(classes)


@pytest.mark.skipif(not Path(CSC).is_file(), reason='csc.exe absent')
def test_arbres_dialogue_compilent(scenario, tmp_path):
    """COMPILE reellement le C# de chaque arbre de dialogue genere.

    Vecu 17/11 (console VIDE, plusieurs sessions perdues) : les scans
    regex de config_hygiene attrapent les pieges CONNUS (doublon,
    fonction manquante), pas une erreur C# inedite. Ce test compile avec
    le compilateur du .NET Framework : toute classe morte
    (CS0102/CS0103/CS1061...) fait echouer le test avant le jeu."""
    regen_apps(scenario)
    regen(scenario)
    classes = cs_arbres(_read(scenario, 'Content/Configuration/Dialogues.ecf'),
                        _read(scenario,
                              'Content/Configuration/BlocksConfig.ecf'))
    assert classes, 'aucun arbre avec Functions genere'
    src = tmp_path / 'D.cs'
    src.write_text(STUBS_CS + '\n' + classes, encoding='utf-8')
    r = subprocess.run([CSC, '/nologo', '/t:library',
                        f'/out:{tmp_path / "D.dll"}', str(src)],
                       capture_output=True, text=True, errors='replace')
    assert r.returncode == 0, r.stdout[-3000:]


def test_deux_consoles_memes_fonctions(scenario):
    """Demande 18/11 : une console principale + une variante compacte a
    poser pres des containers. DEUX blocs, UN SEUL arbre de dialogue
    (DialogueState identique) : memoire d'apprentissage et reglages
    partages, aucune logique dupliquee. La compacte coute moins cher."""
    from core.console_apps import CONSOLES
    regen_apps(scenario)
    blocks = _read(scenario, 'Content/Configuration/BlocksConfig.ecf')
    tpl = _read(scenario, 'Content/Configuration/Templates.ecf')
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert len(CONSOLES) == 2
    models, icones = [], []
    for nom, model, icone, pref, _rec in CONSOLES:
        assert f'Name: {nom}\n' in blocks or f'Name: {nom} ' in blocks
        assert f'+Template Name: {nom}' in tpl
        assert re.search(rf'\{{\s*\+\s*Block Id: {pref}, Name: {nom}', blocks)
        models.append(model)
        icones.append(icone)
        assert f'CustomIcon: {icone}' in blocks
    # modeles ET icones DIFFERENTS pour le meme comportement
    assert len(set(models)) == 2 and len(set(icones)) == 2
    assert 'Consoles/StandConsole_C06_Prefab' in models
    assert 'StandConsole_C06' in icones
    # un seul arbre : le DialogueState des deux blocs est identique
    assert blocks.count('DialogueState: Frontier_AppAtelier\n') == 2
    assert dlg.count('{ +Dialogue Name: Frontier_AppAtelier\n') == 1
    # la variante est moins chere que la principale
    import re as _re
    def cout(m):
        corps = _re.search(r'\+Template Name: ' + m + r'.*?(?=\n\{ |\Z)',
                           tpl, _re.S).group(0)
        return (int(_re.search(r'Electronics: (\d+)', corps).group(1)),
                int(_re.search(r'PlasticMaterial: (\d+)', corps).group(1)))
    assert cout('Frontier_Console_Atelier_Petite') < cout('Frontier_Console_Atelier')
    # idempotence : deux regen d'affilee ne dupliquent ni bloc ni recette
    regen_apps(scenario)
    b2 = _read(scenario, 'Content/Configuration/BlocksConfig.ecf')
    t2 = _read(scenario, 'Content/Configuration/Templates.ecf')
    assert b2.count('Name: Frontier_Console_Atelier_Petite') == 1
    assert t2.count('+Template Name: Frontier_Console_Atelier_Petite') == 1


def test_apprentissage_coffres_libres(scenario):
    """Vecu 17/11 : `TRI_Armures_A`, `TRI_Carburant_A`, `TRI_Boost_A` —
    coffres du joueur hors des 15 sous-categories. L'ancien apprentissage
    cherchait la categorie du nom (`idx < 0 -> continue`) et IGNORAIT ces
    coffres : l'item, range a la main dedans, repartait au classement
    automatique (Divers/Composants/Medical). Desormais la destination
    memorisee est le NOM du coffre, pour TOUT container <prefix>_*."""
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    ap = dlg[dlg.index('void Frontier_Apprendre()'):
             dlg.index('void Frontier_Oublier()')]
    # plus aucun filtre par categorie dans l'apprentissage
    assert 'CATS[i]' not in ap and 'int idx = -1' not in ap
    # tout container du prefixe est visite, y compris hors categorie
    assert "if (!nd.StartsWith(pref + '_')) { continue; }" in ap
    assert 'LocalStructure.GetDevice<IContainer>(nd)' in ap
    # seuls les ECARTS sont memorises (le classement auto fait deja juste)
    assert 'if (auto0 >= 0 && nd.StartsWith(pref + \'_\' + CATS[auto0]))' in ap
    # la cle memorizee porte l'id ET le nom du coffre
    assert "string k0 = ',' + st.id.ToString() + '='" in ap
    assert "dest = dest + st.id + '=' + nd + ','" in ap
    # le tri essaie d'abord la destination apprise, puis le classement auto
    tri = dlg[dlg.index('void Frontier_TrierTri()'):
              dlg.index('void Frontier_SetPrefix()')]
    assert tri.index('Frontier_Destin(lot.id)') < tri.index('CATS[code3]')
    assert 'if (restant <= 0) { continue; }' in tri
    # OUBLIER vide la memoire et la persiste
    assert "Frontier_Dest = ','" in dlg and "SetGlobalVar('Frontier_Dest', ','" in dlg


def test_apps_preservees_par_regen_traders_et_reciproquement(scenario):
    regen_apps(scenario)
    dlg1 = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    regen(scenario)
    dlg2 = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert APPS_MARKER in dlg2 and MARKER in dlg2
    assert dlg2.index(APPS_MARKER) < dlg2.index(MARKER)
    assert 'Frontier_AppAtelier' in dlg2       # apps non effacees
    assert 'Frontier_TraderHub' in dlg2        # traders presents
    assert 'Vanilla_Node' in dlg2
    regen_apps(scenario)                       # regen apps : traders intactes
    dlg3 = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert MARKER in dlg3 and 'Frontier_TraderHub' in dlg3
    assert dlg3.count(APPS_MARKER) == 1
    # stabilite : deux regen apps d'affilee -> dialogues identiques
    regen_apps(scenario)
    dlg4 = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    regen_apps(scenario)
    assert _read(scenario, 'Content/Configuration/Dialogues.ecf') == dlg4


def test_appro_coffre_unique_memorise(scenario):
    """Demande 18/11 : un coffre lie a un constructeur contient PLUSIEURS
    ingredients. Le mode historique APPRO_<Item> ne gere qu'un item ;
    le coffre nomme APPRO memorise son contenu (item -> quantite) puis
    le maintient. Memoire : Variable_2 Frontier_Appr, format
    "|Nom=id:qty,id:qty|"."""
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    hub = dlg[dlg.index('{ +Dialogue Name: Frontier_AppAtelier\n'):
              dlg.index('{ +Dialogue Name: Frontier_AppAtelier_Apprendre')]
    # une seule declaration de la memoire (CS0102 sinon)
    assert hub.count('Variable_2: "Frontier_Appr", param1: dbplayer_string') == 1
    assert 'string Frontier_ApprDe(string nom)' in dlg
    assert 'string Frontier_ApprMaj(string nom, string liste)' in dlg
    assert 'string Frontier_ApprSnap(IContainer c)' in dlg
    # nœud de memorisation + option
    assert 'Frontier_AppAtelier_ApproMem' in dlg
    # deux voies : TOUS les coffres d'un coup (un par constructeur)
    # et un seul par nom
    assert 'MEMORISER TOUS les coffres APPRO' in dlg
    assert 'Frontier_ApprMemoriserTout()' in dlg
    assert 'MEMORISER UN coffre APPRO' in dlg
    assert 'Frontier_ApprMemoriser()' in dlg
    # remplissage factorise : un seul chemin pour les deux modes
    assert 'int Frontier_ApproUn(IContainer dsta, int cid, int qty' in dlg
    assert "if (nma != 'APPRO' && !nma.StartsWith('APPRO_'))" in dlg
    # l'aide documente la procedure
    html = (scenario / 'SharedData' / 'Console_Aide.html').read_text(
        encoding='utf-8')
    assert 'MÉMORISER' in html and 'coffre APPRO' in html


def test_aide_atelier_complete(scenario):
    """L'aide doit couvrir TOUTES les possibilites du tri et de l'appro,
    y compris les pieges (vecu 18/11 : Empyrion autorise deux coffres de
    meme nom, la console n'en voit qu'un)."""
    from core.console_apps import AIDE_FILE, CATS
    regen_apps(scenario)
    html = (scenario / 'SharedData' / AIDE_FILE).read_text(encoding='utf-8')
    # sommaire et sections
    for titre in ('Installer la console', "Afficher le contenu d'un coffre",
                  'Trier un coffre', 'Apprendre vos rangements',
                  'Plusieurs coffres par catégorie', 'Changer de préfixe',
                  'Approvisionner les fabricateurs',
                  'Un coffre = un seul item',
                  'Un coffre = plusieurs ingrédients', 'Automatiser',
                  'Règles d\'or', 'Tableau des sous-catégories'):
        assert titre in html, titre
    # pieges explicitement documentes
    assert 'noms <b>UNIQUES</b>' in html or 'noms UNIQUES' in html
    assert 'un seul' in html.lower() and 'ignoré' in html.lower()
    assert 'Casse et orthographe exactes' in html
    assert 'Renommer un coffre' in html
    assert 'TRIER avant APPROVISIONNER' in html
    # toutes les categories listees avec leur compte
    for c in CATS:
        assert f'TRI_{c}</code>' in html
    # les deux voies d'appro
    assert 'MÉMORISER TOUS les coffres APPRO' in html
    assert 'MÉMORISER UN coffre APPRO' in html
    # HTML bien ferme
    assert html.rstrip().endswith('</body></html>')


def test_appro_auto_hors_etat(scenario):
    """Vecu 18/11 : l'appro AUTO (CallLater toutes les 5 min) ne faisait
    rien. Frontier_Approvisionner commencait par
    AddToGlobalVar('Frontier_Tri_Pref') — API qui ECHOUE hors etat de
    dialogue : la fonction mourait a sa premiere ligne. Elle doit lire le
    miroir static Frontier_Pref, charge par Frontier_ChargePref() a
    l'entree du hub (Execute)."""
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    deb = dlg.index('void Frontier_Approvisionner()')
    corps = dlg[deb:deb + 1200]
    assert 'string pref = Frontier_Pref;' in corps
    assert 'AddToGlobalVar' not in corps
    # la fonction de chargement existe et est appelee a l'entree du hub
    assert 'void Frontier_ChargePref()' in dlg
    assert 'Frontier_ChargePref(); Frontier_Trace(' in dlg
    assert 'static string Frontier_Pref' in dlg


def test_appro_auto_options_presentes(scenario):
    """Vecu 18/11 : Frontier_AutoMarche/AutoStop existaient dans le C#
    mais AUCUNE option ne les appelait — l'auto etait inactivable en jeu."""
    regen_apps(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    i = dlg.index('{ +Dialogue Name: Frontier_AppAtelier_Appro\n')
    noeud = dlg[i:dlg.index('{ +Dialogue Name:', i + 10)]
    assert 'DEMARRER l auto' in noeud and 'Frontier_AutoMarche()' in noeud
    assert 'ARRETER l auto' in noeud and 'Frontier_AutoStop()' in noeud
    # numerotation contigue des options
    nums = [int(x) for x in re.findall(r'^  Option_(\d+):', noeud, re.M)]
    assert nums == list(range(1, len(nums) + 1)), nums
    # le noeud doit etre REFERME : sans ce `}`, le parseur ECF imbrique les
    # etats suivants et le jeu les declare introuvables (vecu 18/11)
    assert noeud.rstrip().endswith('}')


def test_traces_actions_presentes(scenario):
    """Vecu 18/11 : un bruit moteur (SetLabel sur UIScrollablePopupList)
    apparait par paires sans qu'on sache quelle action le declenche. Des
    traces horodatees APP-TRACE permettent de correler le log du jeu avec
    ce que le joueur vient de faire."""
    regen_apps(scenario)
    regen(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert 'void Frontier_Trace(string q)' in dlg
    assert "UnityEngine.Debug.Log('APP-TRACE: ' + q)" in dlg
    for trace in ('atelier', 'trier', 'appro', 'oublier', 'aide atelier',
                  'memoriser tous', 'memoriser un', 'commerce'):
        assert f"Frontier_Trace('{trace}')" in dlg or \
            f"Frontier_Trace('{trace}" in dlg, trace


def test_localisation_blocs_atelier_survit_a_la_regen_commerce(scenario):
    """Vecu 18/11 : sans cles de localisation le jeu affiche le nom
    technique du bloc. La purge des traders etait un PREFIXE large
    (`Frontier_`) : elle effacait les cles de l'atelier, ecrites avant
    elle dans le meme clic Codex > Marchands."""
    from core.console_apps import LOCS_ATELIER
    for _ in range(2):                      # idempotent
        regen_apps(scenario)
        regen(scenario)
        regen_apps(scenario)
        loc = '\n' + _read(scenario, 'Extras/Localization.csv')
        for cle, en, fr in LOCS_ATELIER:
            assert loc.count(f'\n{cle},') == 1, cle
            assert en in loc and fr in loc
        assert 'Frontier_Console_Commercant' in loc      # commerce intact


def test_marqueurs_section_uniques(scenario):
    """Vecu 18/11 : chaque regen ajoutait SON commentaire de section sans
    purger l'ancien — 70 marqueurs 'Console commerçante' accumules dans le
    Localization de Frontier-FR."""
    for _ in range(3):
        regen(scenario)
        regen_apps(scenario)
    loc = _read(scenario, 'Extras/Localization.csv')
    assert loc.count('# ===== Console commer') == 1
    assert loc.count('# ===== Console atelier') == 1
