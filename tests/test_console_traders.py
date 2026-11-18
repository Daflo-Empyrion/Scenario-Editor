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

"""Console commerçante : regen en mode fusion — idempotence, prix,
references et preservation des editions manuelles."""
import re

import pytest

from core.console_traders import regen

LOC_HEADER = ('KEY,English,Deutsch,Français,Italiano,Spanish,'
              'Portuguese (Euro),Portuguese (Brazil),Polish,Russian,'
              'Japanese,Chinese (simplified),Chinese (traditional),Korean,'
              'Turkish,Greek,Dutch,Vietnamese')

ITEMS = """# ItemsConfig
{ Item Id: 100, Name: Bandages, Ref: TradingGoodsTemplate
  MarketPrice: 100, display: true
}
{ +Item Id: 101, Name: AutoMinerCore, Ref: TradingGoodsTemplate
  MarketPrice: 7000, display: true
}
{ Item Id: 102, Name: AncientRelics, Ref: TradingGoodsTemplate
  MarketPrice: 5000, display: true
}
"""

TRADERS = """{ Trader Name: Talon
  SellingText: "hello"
  Item1: "Bandages, mf=1.1-1.2, 50-100, mf=0.4-0.5, 100-500"
  Item2: "AutoMinerCore, mf=1.0, 5, mf=0.5, 10"
} 
"""

BLOCKS = """# BlocksConfig
{ +Block Id: 258, Name: ConsoleTrading
  Class: NPCDialogue
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

LOC = LOC_HEADER + "\nSomeKey,en,de,fr,it,es,pt,ptb,pl,ru,jp,zh,zht,ko,tr,el,nl,vi\n"


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


BLOCKS_TRADER = """# BlocksConfig
{ +Block Id: 258, Name: ConsoleTrading
  Class: NPCDialogue
}
{ +Block Id: 1466, Name: HumanNPCBlocks
  MarketPrice: 5850, display: true
}
"""

TRADERS_BLOCS = """{ Trader Name: Talon
  SellingText: "hello"
  Item1: "HumanNPCBlocks, mf=1.1-1.2, 50-100, mf=0.4-0.5, 100-500"
  Item2: "NomInconnu, 100, 5, 50, 10"
}
"""


def test_blocs_traders_inclus_et_noms_inconnus_rejetes(scenario):
    """Vecu 16/11 : les blocs que les traders vanilla echangent (declares en
    BlocksConfig) etaient rejetes par le filtre ItemsConfig — l'utilisateur
    veut TOUT le catalogue trader dans la console, licences exceptees."""
    sc = scenario / 'Content' / 'Configuration'
    (sc / 'BlocksConfig.ecf').write_text(BLOCKS_TRADER, encoding='utf-8')
    (sc / 'TraderNPCConfig.ecf').write_text(TRADERS_BLOCS, encoding='utf-8')
    report = regen(scenario)
    assert report['skipped'] == 1          # NomInconnu : protege des fautes
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    assert 'HumanNPCBlocks' in dlg         # options ACHETER/VENDRE
    # le container VENTE connait l'id BlocksConfig du bloc
    # dictionnaire id -> long : prix | cle << 24 | stock max << 48
    # cle = id*10 + rang de l'acheteur, valeur packee (prix|cle|stock)
    assert re.search(r'\{ 14660, \d+L \}', dlg)


def test_regen_premiere_passe(scenario):
    report = regen(scenario)
    assert report['licences'] == 1        # Talon
    assert report['block'] == 3         # T1 + T2 (Talon) + T3
    assert report['template'] == 3
    assert report['t2'] is True
    assert report['stock'] == 1           # ligne de licence chez Talon
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    # prix : mf=1.15 * 100 = 115 cr ; le T1 cap au hub declare 5 variables
    # prix T1 = base x1.60 (palier economique, demande 18/11)
    assert 'Bandages — 184 cr' in dlg
    assert 'Frontier_TraderHub' in dlg
    assert 'Variable_5: "Frontier_Restock", param1: dbplayer_int' in dlg
    # bloc : Id 136 libre
    blocks = _read(scenario, 'Content/Configuration/BlocksConfig.ecf')
    assert 'Name: Frontier_Console_Commercant' in blocks
    assert re.search(r'\{ \+Block Id: 136,', blocks)
    # le contenu vanilla est preserve
    assert 'Vanilla_Node' in dlg
    assert 'ConsoleTrading' in blocks


def test_regen_idempotent(scenario):
    regen(scenario)
    before = {rel: _read(scenario, rel) for rel in (
        'Content/Configuration/ItemsConfig.ecf',
        'Content/Configuration/BlocksConfig.ecf',
        'Content/Configuration/Templates.ecf',
        'Content/Configuration/TraderNPCConfig.ecf',
        'Content/Configuration/Dialogues.ecf')}
    report = regen(scenario)
    assert report['licences'] == 0        # deja presents
    assert report['block'] == 0
    assert report['template'] == 0
    assert report['stock'] == 0
    for rel, txt in before.items():
        assert _read(scenario, rel) == txt, rel


def test_regenerated_dialogue_graph(scenario):
    regen(scenario)
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    names = set(re.findall(r'^\{ \+Dialogue Name: (\S+)', dlg, re.M))
    targets = set(re.findall(r'^  (?:OptionNext|Next)_\d+: (\S+)', dlg, re.M))
    invalid = sorted(x for x in targets if x not in names and x != 'End')
    assert not invalid, invalid
    # fenetres quantite : SAISIE libre + MAX (17/11 : les paliers x1/x5/x25/
    # x100/x1000 sont supprimes — ils coutaient 10 noeuds et 5 methodes C#
    # par item, d'ou le gel de plusieurs secondes a la premiere ouverture)
    # la SAISIE est portee par le noeud enfant Tqi, jamais par Tq : un
    # Input sur Tq s'appliquait aussi a xMAX (vecu 17/11)
    assert 'Frontier_Tqi' in dlg and 'Input: "Quantité :"' in dlg
    assert 'VALIDER la quantité' in dlg and 'InputResultAsInt()' in dlg
    # montant de la derniere operation affiche (Output = methode C#
    # interpolee) et bouton retour au hub sur chaque page objet
    assert '{Frontier_DA}' in dlg and '{Frontier_DV}' in dlg
    assert 'Retour au hub' in dlg
    # FACTURE : montant RECU + tableau pagine sur 3 pages
    assert 'FACTURE FRONTIER</b> — {Frontier_DV2} cr' in dlg
    assert 'MARCHAND' in dlg and 'QTE' in dlg and 'TOTAL VENTES' in dlg
    assert 'TOTAL VENTES : {Frontier_DV2} cr' in dlg
    # facture : 6 pages de 10 lignes, pagination par NŒUDS (les balises
    # @p9 de la doc ne font rien en 1.20.1 : police reduite au lieu de
    # paginer, vecu 18/11)
    for p_ in range(2, 7):
        assert f'Frontier_THub2_container_vendu{p_}' in dlg
    assert 'OptionIf_1: "Frontier_Fnb2 > 10"' in dlg
    assert "@p9" not in dlg
    # stock d'achat = compteur d'achats du cycle (stock du TraderNPCConfig)
    # STOCK du marchand : une variable chaine par arbre (l'API
    # AddToGlobalVar ne LIT pas, preuve DialogueSystem.cs:2231) + les deux
    # fonctions de lecture/ecriture, declarees une seule fois (le hub)
    assert "Variable_8: \"Frontier_Stk\", param1: dbplayer_string" in dlg
    assert "Variable_8: \"Frontier_Stk2\", param1: dbplayer_string" in dlg
    assert "Variable_8: \"Frontier_Stk3\", param1: dbplayer_string" in dlg
    assert dlg.count('int Frontier_StkDe(string lst, int t, int i)') == 3
    assert dlg.count('string Frontier_StkMaj(string lst, int t, int i, int q)') == 3
    # l'ancien compteur global (jamais lu) a disparu
    assert 'Frontier_Ach_' not in dlg
    assert '×25' not in dlg and '×1000' not in dlg
    assert dlg.count('×MAX — stock, budget et crédit') == 6   # achat (3 arbres)
    # la vente est desormais bornee par le budget du cycle (18/11)
    assert dlg.count('×MAX — stock et budget') == 6          # vente
    assert dlg.count('int maxb = (500000 - Frontier_Spent)') >= 4
    # stock = colonne « stock » du TraderNPCConfig pour l'achat, 5e champ
    # (stock max d'achat) pour la vente ; compteurs remis a plein au reappro
    assert 'Frontier_StkDe(Frontier_Stk' in dlg
    assert 'Frontier_StkMaj(Frontier_Stk' in dlg
    assert 'void Frontier_Rst' in dlg and "Frontier_Stk', ','" in dlg
    # numerotation CONTIGUE des options du hub (le moteur s'arrete au
    # premier numero manquant : l'aide etait en 8 apres un trou)
    hub = re.search(r'\{ \+Dialogue Name: Frontier_TraderHub2\n(.*?)\n\}',
                    dlg, re.S).group(1)
    nums = sorted(int(x) for x in re.findall(r'  Option_(\d+):', hub))
    assert nums == list(range(1, len(nums) + 1))
    assert 'AIDE (guide de la console)' in hub
    # aucune option au-dela de 12 (limite d'affichage UI)
    cur, worst = None, 0
    for ln in dlg.splitlines():
        m = re.match(r'^\{ \+Dialogue Name: (\S+)', ln)
        if m:
            cur = m.group(1)
        om = re.match(r'^  Option(\d+):', ln)
        if om and cur:
            worst = max(worst, int(om.group(1)))
    assert worst <= 12


def test_edition_manuelle_trader_preservee_et_repercutee(scenario):
    regen(scenario)
    # l'utilisateur ajoute un item au stock du trader Talon
    p = scenario / 'Content/Configuration/TraderNPCConfig.ecf'
    t = p.read_text(encoding='utf-8')
    p.write_text(t.replace('} \n', '  Item3: "Bandages, 200, 10-20"\n} \n'),
                 encoding='utf-8')
    report = regen(scenario)
    assert report['stock'] == 0           # licence deja inseree
    dlg = _read(scenario, 'Content/Configuration/Dialogues.ecf')
    # prix absolu 200 respecte a la regen
    assert 'Bandages — 320 cr' in dlg


def test_consoles_commercantes_modele_et_couleurs(scenario):
    """Demande 18/11 : meme modele que la console de commerce vanilla
    (`TradingConsolePrefab`, dont la teinte est prouvee par ConsoleTrading
    rouge vs ConsoleGIN cyan) et deux couleurs distinctes : bleu T1, or
    T2. BlockColor est un multiplicateur (255 = couleur native)."""
    regen(scenario)
    from core.console_traders import (CONSOLE2_BASE, CONSOLE_NAME,
                                      COULEUR_T1, COULEUR_T2)
    blocks = (scenario / 'Content/Configuration/BlocksConfig.ecf').read_text(
        encoding='utf-8')
    for nom, couleur in ((CONSOLE_NAME, COULEUR_T1),
                         (CONSOLE2_BASE, COULEUR_T2)):
        bloc = re.search(r'\{ \+Block Id: \d+, Name: ' + nom +
                         r'\n(.*?)(?=\n\{ |\Z)', blocks, re.S).group(1)
        assert 'Model: @models/Blocks/Mothership/TradingConsolePrefab' in bloc
        assert f'BlockColor: "{couleur}"' in bloc
        # icone assortie au modele (celle du bloc ConsoleTrading)
        assert 'CustomIcon: ConsoleTrading' in bloc
    assert COULEUR_T1 != COULEUR_T2


def test_activation_commercants_separee_par_console(scenario):
    """Vecu 18/11 : une licence activee en T1 ouvrait la boutique en T2.
    Les flags de deblocage portaient le meme nom dans les deux arbres
    (`Frontier_Active{w}`), contrairement a Spent/Restock qui ont un tag.
    Desormais `Frontier_Active{tag}{w}` : tag vide = T1 (noms historiques,
    deblocages existants preserves), tag 2 = T2."""
    regen(scenario)
    dlg = (scenario / 'Content/Configuration/Dialogues.ecf').read_text(
        encoding='utf-8')
    t1 = dlg[dlg.index('{ +Dialogue Name: Frontier_TraderHub\n'):
             dlg.index('{ +Dialogue Name: Frontier_TraderHub2\n')]
    t2 = dlg[dlg.index('{ +Dialogue Name: Frontier_TraderHub2\n'):]
    for w in '123':
        assert f'Variable_{w}: "Frontier_Active{w}"' in t1
    for w in '123':
        assert f'Frontier_Active2{w}"' in t2
    # aucun recouvrement : T1 n'utilise jamais les noms T2 en ecriture
    assert 'Frontier_Active21' not in t1


def test_localisation_sans_doublons(scenario):
    """Vecu 18/11 : `_merge_loc` ne supprimait que les cles `Frontier_`,
    pas les `bkiFrontier_` (nom d'Info des blocs) — elles s'accumulaient
    a chaque regen (300 lignes pour 71 cles). Deux regen d'affilee ne
    doivent laisser qu'une entree par cle."""
    regen(scenario)
    regen(scenario)
    loc = (scenario / 'Extras/Localization.csv').read_text(encoding='utf-8')
    assert loc.count('\nbkiFrontier_Console_Commercant,') == 1
    assert loc.count('\nFrontier_Console_Commercant,') == 1


def test_vente_container_filtre_commercants_actives(scenario):
    """Vecu 18/11 : le container « VENTE » se vendait sur T2/T3 meme avec
    ZERO commercant debloque sur cette console (seuls 3 l'etaient sur T1).
    La boucle d'acheteurs doit verifier le bit d'activation du marchand
    (Frontier_Active{tag}{w} & b) avant de lui vendre."""
    regen(scenario)
    dlg = (scenario / 'Content/Configuration/Dialogues.ecf').read_text(
        encoding='utf-8')
    deb = dlg.index('void Frontier_VendreContainer2()')
    fonc = dlg[deb:deb + 7000]
    assert 'int ti4 = cle4 / 10000;' in fonc
    assert 'int w4 = ti4 / 24 + 1;' in fonc
    assert 'if (!act4) { continue; }' in fonc


def test_licences_ont_une_icone(scenario):
    """Vecu 18/11 : les licences s'affichaient sans icone. Le moteur scanne
    SharedData/Content/Bundles/ItemIcons et enregistre chaque PNG
    (MenuSiteConnectionToken.cs:1836, comme les 1426 PNG de RE2) : il
    suffit d'y deposer Frontier_Licence.png et de pointer dessus."""
    regen(scenario)
    items = (scenario / 'Content/Configuration/ItemsConfig.ecf').read_text(
        encoding='utf-8')
    assert items.count('CustomIcon: Frontier_Licence\n') >= 1
    icone = (scenario / 'SharedData/Content/Bundles/ItemIcons'
             / 'Frontier_Licence.png')
    assert icone.is_file(), 'icone non copiee dans ItemIcons/'
    assert icone.stat().st_size > 1000


def test_stock_dispo_une_seule_fonction(scenario):
    """Vecu 18/11 : une methode `Frontier_Dispo<tag>_<trader>_<item>()` par
    item faisait ~2000 methodes et 214 Ko de C# par arbre -> plusieurs
    secondes de compilation Roslyn a la premiere ouverture. Remplac par
    UNE fonction parametree `Frontier_Dispo(t, i, smax)`, appelee dans
    l'interpolation de l'Output."""
    regen(scenario)
    dlg = (scenario / 'Content/Configuration/Dialogues.ecf').read_text(
        encoding='utf-8')
    assert dlg.count('int Frontier_Dispo(int t, int i, int smax)') == 3
    assert not re.search(r'Frontier_Dispo\w*_\w+_\d+\(\)', dlg)
    assert re.search(r'Disponible : \{Frontier_Dispo\(\d+, \d+, \d+\)\}', dlg)


def test_consoles_techtree_valide(scenario):
    """Vecu 18/11 : TechTreeNames "Commercants" (invente) faisait casser
    l'UI du CONSTRUCTEUR (SetLabel sur UIScrollablePopupList, 2 lignes
    rouges a chaque ouverture). Un onglet existant est obligatoire."""
    regen(scenario)
    blocks = (scenario / 'Content/Configuration/BlocksConfig.ecf').read_text(
        encoding='utf-8')
    for nom in ('Frontier_Console_Commercant', 'Frontier_Console_Commercant_T2',
                'Frontier_Console_Commercant_T3'):
        bloc = re.search(r'\{ \+Block Id: \d+, Name: ' + nom +
                         r'\n(.*?)(?=\n\{ |\Z)', blocks, re.S).group(1)
        assert 'TechTreeNames: "Frontier"' in bloc, nom
