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

"""Consoles commerçantes Frontier-FR : regenere, depuis les configs
COURANTES du scenario, le pool de licences vendues par les traders et les
arbres de dialogues des consoles T1 et T2 (hub, activation par licence,
boutiques achat/vente avec fenetres quantite et budget de reapro).

Mode FUSION : les morceaux deja presents (licences, blocs, templates,
lignes de stock) sont conserves tels quels — seul l'arbre de dialogues
(section delimitee par MARKER) est regenere de zero. Les editions manuelles
dans le reste des configs sont preservees, et la relecture de
TraderNPCConfig/ItemsConfig repercute toute modification de catalogue ou de
prix (l'ajout/retrait d'un item chez un trader se repercute au prochain
passage).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

try:
    from core.fsutil import atomic_write_text
except ImportError:      # package autonome (dist/console_commerce)
    from fsutil import atomic_write_text

MARKER = '# ===== Console commerçante Frontier-FR (14/11) ====='
LICENCE_PRICE = 1_000_000   # prix d'une licence chez le commerçant
BUDGET_CYCLE = 500_000      # crédits achetables par cycle de reapro (T1)
BUDGET_CYCLE2 = 5_000_000   # idem T2 (x10)
# T3 : plafond de credits ILLIMITE en pratique (1 milliard par cycle : les
# objets coutent des milliers). Seule contrainte : le stock du marchand.
# Reste loin de int.MaxValue (2,1 milliards) pour eviter tout debordement.
BUDGET_CYCLE3 = 1_000_000_000
REAPRO_S = 3600             # cooldown de reapro : secondes RÉELLES de session
PER_PAGE = 9                # items par page (l'UI affiche 12 options max)
HUB_PER_PAGE = 15           # commerçants par page de hub
UNLOCK_LEVEL, UNLOCK_COST = 10, 20
CONSOLE_ID = 136
CONSOLE_NAME = 'Frontier_Console_Commercant'
CONSOLE2_BASE = 'Frontier_Console_Commercant_T2'
CONSOLE3_BASE = 'Frontier_Console_Commercant_T3'
# BlockColor = multiplicateur de teinte (255 = couleur native du modele).
# Bleu : celui d'origine du bloc de commerce vanilla (valeur commentee
# dans sa config, remplacee par le rouge). Or : teinte chaude, R au max.
COULEUR_T1 = '0,64,255'
COULEUR_T2 = '255,200,80'
# T3 : violet (distinct du bleu T1 et de l'or T2 ; a ajuster a l'envie)
COULEUR_T3 = '190,150,255'
# Paliers economiques : les consoles hautes reduisent la marge du marchand.
# 'buy' = le joueur achete (facteur > 1 = plus cher) ; 'sell' = le joueur
# vend (facteur < 1 = il encaisse moins). Demande 18/11.
FACT_ACHAT = {'': 1.60, '2': 1.40, '3': 1.20}
# en-tete et separateurs de la FACTURE (tableau texte : colonnes a largeur
# fixe, cadre par tirets — l'alignement parfait demanderait du HTML)
FACT_ENTETE = ('MARCHAND'.ljust(26) + 'ITEM'.ljust(22) + 'QTE'.rjust(8) +
               'PU'.rjust(8) + 'TOTAL'.rjust(11))
FACT_SEP = '-' * 75
FACT_VENTE = {'': 0.40, '2': 0.50, '3': 0.60}
T2_T1_COUNT = 5             # recette T2 : consoles T1
T2_LIC_COUNT = 5            # + licences du commerçant correspondant
T2_RELICS = 20              # + reliques anciennes
# recette T3 : elle se fabrique à partir de consoles T2
T3_T2_COUNT = 5
T3_RELICS = 20
RELIC_ITEM = 'AncientRelics'
AIDE_COMMERCE_FILE = 'Console_Commerce_Aide.html'   # <scenario>/SharedData


def slug(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')


def _bit_of(i: int) -> tuple:
    """3 mots de 24 bits pour les flags d'activation (69 traders)."""
    return (i // 24) + 1, 1 << (i % 24)


def _mid(s: str):
    s = s.strip()
    m = re.match(r'^([\d.]+)-([\d.]+)$', s)
    if m:
        return round((float(m.group(1)) + float(m.group(2))) / 2)
    try:
        return round(float(s))
    except ValueError:
        return None


def _fmid(s: str) -> float:
    m = re.match(r'^([\d.]+)-([\d.]+)$', s)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2
    return float(s)


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8-sig', errors='strict')


def _write(path: Path, text: str) -> None:
    atomic_write_text(path, text, encoding='utf-8')


# nom d'item/bloc dans une declaration ECF : tout sauf espace, virgule et
# commentaire. Un `\w+` casse les noms a point (5.8mmBullet -> "5") et
# laisse passer les commentaires de fin de ligne ("AssaultRifle   # T1").
ITEM_NAME = r'([^\s,#]+)'


def _parse_market(items_text: str, blocks_text: str = ''):
    """Base de prix `MarketPrice` et noms existants, items ET blocs (les
    traders vanilla echangent des blocs, declares en BlocksConfig)."""
    market, names = {}, set()
    for m in re.finditer(r'\{ \+?(?:Item|Block) [^\n]*Name: ' + ITEM_NAME
                         + r'[^\n]*\n(.*?\n)(?=\{ |\Z)',
                         items_text + blocks_text, re.S):
        names.add(m.group(1))
        mp = re.search(r'^\s*MarketPrice: (\d+)', m.group(2), re.M)
        if mp:
            market[m.group(1)] = int(mp.group(1))
    return market, names


def _parse_catalog(traders_text: str, traders, market, item_names):
    """slug -> {'name', 'buy': [(iname, meta, px)], 'sell': [...]}.

    Les licences (Frontier_Licence_*) sont exclues : jamais vendues par la
    console, uniquement chez le commerçant lui-meme."""
    catalog, skipped = {}, 0
    for t in traders:
        s = slug(t)
        catalog[s] = {'name': t, 'buy': [], 'sell': []}
        m = re.search(r'^\{ Trader Name: ' + re.escape(t)
                      + r'\s*$(.*?)^\}', traders_text, re.M | re.S)
        body = m.group(1) if m else ''
        for lm in re.finditer(r'^\s*Item\d+: "(.+)"\s*$', body, re.M):
            parts = [p.strip() for p in lm.group(1).split(',')]
            iname, meta = parts[0], None
            mm = re.match(r'^(Token):(\d+)$', iname)
            if mm:
                iname, meta = mm.group(1), mm.group(2)
            if iname not in item_names or \
                    iname.startswith('Frontier_Licence_'):
                skipped += 1
                continue

            def px(field):
                if field.startswith('mf='):
                    base = market.get(iname)
                    if base is None:
                        return None
                    return round(base * _fmid(field[3:]))
                return _mid(field)

            sell = px(parts[1]) if len(parts) >= 2 else None
            sst = _mid(parts[2]) if len(parts) >= 3 else None
            buy = px(parts[3]) if len(parts) >= 4 else None
            # 5e champ = stock MAX que le marchand accepte d'ACHETER
            # (ce que le joueur lui vend). Jamais lu jusqu'ici : la vente
            # n'avait aucune limite de quantite (vecu 18/11).
            bst = _mid(parts[4]) if len(parts) >= 5 else None
            if sell and sell > 0 and (sst is None or sst > 0):
                # 4e champ = STOCK du marchand (colonne « stock » du
                # TraderNPCConfig) : plafond d'achat par cycle
                catalog[s]['buy'].append((iname, meta, sell,
                                          max(1, sst or 1)))
            if buy and buy > 0:
                catalog[s]['sell'].append((iname, meta, buy,
                                           max(1, bst or 1)))
        catalog[s]['buy'].sort(key=lambda x: x[2])
        catalog[s]['sell'].sort(key=lambda x: -x[2])
    return catalog, skipped


# ---------------------------------------------------------------- items

def _merge_items(items_text: str, traders) -> tuple:
    used = set(int(x) for x in
               re.findall(r'^\{ \+?Item Id: (\d+),', items_text, re.M))
    add, next_id = [], max(used, default=1000) + 1
    for t in traders:
        s = slug(t)
        if f'Name: Frontier_Licence_{s},' in items_text:
            continue
        next_id += 1
        add += [f'{{ Item Id: {next_id}, Name: Frontier_Licence_{s},'
                ' Ref: TradingGoodsTemplate',
                '  Mass: 0.01, type: float, display: true, formatter: Kilogram',
                '  Volume: 0, type: float, display: true, formatter: Liter',
                '  ShowUser: Yes',
                # icone : PNG depose dans SharedData/Content/Bundles/
                # ItemIcons/Frontier_Licence.png (le moteur scanne ce
                # dossier — MenuSiteConnectionToken.cs:1836 ; RE2 en livre
                # 1426). Pas besoin de bundle Unity.
                '  CustomIcon: Frontier_Licence',
                f'  Info: Frontier_Licence_{s}info, display: true',
                '  StackSize: 1',
                '}']
    if not add:
        return items_text, 0
    lines = items_text.rstrip('\n').splitlines()
    lines += ['', '# ===== Bornes commerçantes Frontier-FR : licences ====='] \
        + add
    return '\n'.join(lines) + '\n', len(add) // 8


# ---------------------------------------------------------------- bloc

BLOCK_TPL = """{{ +Block Id: {bid}, Name: {name}
  CustomIcon: ConsoleTrading
  Class: NPCDialogue
  DialogueState: {state}
  NPCModelRotation: false
  Group: cpgCrewStationHuman
  Material: metallight
  Shape: ModelEntity
  Model: @models/Blocks/Mothership/TradingConsolePrefab
  DropMeshfile: Entities/Misc/DropContainerNewPrefab
  Place: Free
  Info: bki{name}, display: true
  Category: Devices
  AllowPlacingAt: "Base,MS", display: true
  SizeInBlocks: "1,1,1", display: true
  SizeInBlocksLocked: "Base,MS"
  IsAccessible: true, type: bool
  IsOxygenTight: false, display: true
  Mass: 65, type: float, display: true, formatter: Kilogram
  Volume: 12, type: float, display: true, formatter: Liter
  EnergyIn: 1, type: int, display: true, formatter: Watt
  BlockColor: "{couleur}"
  ShowBlockName: true
  StackSize: 100
  UnlockLevel: {ul}, display: true
  UnlockCost: {uc}, display: true
  TechTreeNames: "{categ}"
}}"""


def blocks_cfg_text(blocks_text: str) -> str:
    """Coupe une eventuelle section console generee residuelle."""
    i = blocks_text.find(MARKER)
    if i >= 0:
        return blocks_text[:i].rstrip('\n')
    return blocks_text.rstrip('\n')


def _merge_blocks(blocks_text: str, traders, relic_ok: bool) -> tuple:
    """UNE seule console T2 : le choix du commerçant se fait dans le
    dialogue (Activer = consommation de la licence, filtrage auto).

    Modeles et couleurs : meme modele que la console de commerce vanilla
    (`TradingConsolePrefab`, dont la teinte est prouvee : ConsoleTrading
    rouge vs ConsoleGIN cyan). `BlockColor` est un MULTIPLICATEUR de
    teinte (255 = couleur native) : bleu d'origine du bloc pour T1, or
    pour T2, afin de les distinguer d'un coup d'oeil."""
    out = blocks_text
    used = set(int(x) for x in
               re.findall(r'^\{ \+?Block Id: (\d+),', out, re.M))
    added = 0
    if f'Name: {CONSOLE_NAME}' not in out:
        bid = CONSOLE_ID if CONSOLE_ID not in used else \
            next(i for i in range(136, 2048) if i not in used)
        used.add(bid)
        out = out.rstrip('\n') + '\n\n' + MARKER + '\n' + \
            BLOCK_TPL.format(bid=bid, name=CONSOLE_NAME,
                             state='Frontier_TraderHub', ul=UNLOCK_LEVEL,
                             uc=UNLOCK_COST, categ='Frontier',
                             couleur=COULEUR_T1) + '\n'
        added += 1
    if relic_ok:
        # supprime les anciennes variantes suffixees (69 -> 1)
        out = re.sub(r'\n\{ \+Block Id: \d+, Name: '
                     rf'{CONSOLE2_BASE}_\w+(?:\n(?!\{{ \+Block)[^\n]*)*',
                     '', out)
        if f'Name: {CONSOLE2_BASE}' not in out:
            bid = next(i for i in range(136, 2048) if i not in used)
            used.add(bid)
            out = out.rstrip('\n') + '\n' + \
                BLOCK_TPL.format(bid=bid, name=CONSOLE2_BASE,
                                 state='Frontier_TraderHub2',
                                 ul=UNLOCK_LEVEL, uc=UNLOCK_COST,
                                 categ='Frontier', couleur=COULEUR_T2)
            added += 1
        if f'Name: {CONSOLE3_BASE}' not in out:
            bid = next(i for i in range(136, 2048) if i not in used)
            used.add(bid)
            out = out.rstrip('\n') + '\n' + \
                BLOCK_TPL.format(bid=bid, name=CONSOLE3_BASE,
                                 state='Frontier_TraderHub3',
                                 ul=UNLOCK_LEVEL, uc=UNLOCK_COST,
                                 categ='Frontier', couleur=COULEUR_T3)
            added += 1
    return out, added


# ---------------------------------------------------------------- template

def _merge_templates(templates_text: str, traders, relic_ok: bool) -> tuple:
    out, added = templates_text, 0
    if f'+Template Name: {CONSOLE_NAME}' not in out:
        tpl = (f'{{ +Template Name: {CONSOLE_NAME}\n'
               '  CraftTime: 20\n'
               '  Target: "SurvC,SmallC,HoverC,BaseC,LargeC,AdvC"\n'
               '  { Child Inputs\n'
               '    Electronics: 5\n'
               '    PlasticMaterial: 10\n'
               '  }\n}')
        out = out.rstrip('\n') + '\n\n' + tpl + '\n'
        added += 1
    if relic_ok:
        # supprime les anciennes recettes suffixees (69 -> 1)
        out = re.sub(r'\n\{ \+Template Name: '
                     rf'{CONSOLE2_BASE}_\w+\n(?:.|\n(?!\{{ \+Template))*?\n\}}\n',
                     '\n', out)
        if f'+Template Name: {CONSOLE2_BASE}\n' not in out:
            tpl = (f'{{ +Template Name: {CONSOLE2_BASE}\n'
                   '  CraftTime: 30\n'
                   '  Target: "SurvC,SmallC,HoverC,BaseC,LargeC,AdvC"\n'
                   '  { Child Inputs\n'
                   f'    {CONSOLE_NAME}: {T2_T1_COUNT}\n'
                   f'    {RELIC_ITEM}: {T2_RELICS}\n'
                   '  }\n}')
            out = out.rstrip('\n') + '\n\n' + tpl + '\n'
            added += 1
        if f'+Template Name: {CONSOLE3_BASE}\n' not in out:
            tpl = (f'{{ +Template Name: {CONSOLE3_BASE}\n'
                   '  CraftTime: 40\n'
                   '  Target: "SurvC,SmallC,HoverC,BaseC,LargeC,AdvC"\n'
                   '  { Child Inputs\n'
                   f'    {CONSOLE2_BASE}: {T3_T2_COUNT}\n'
                   f'    {RELIC_ITEM}: {T3_RELICS}\n'
                   '  }\n}')
            out = out.rstrip('\n') + '\n\n' + tpl + '\n'
            added += 1
    return out, added


# ---------------------------------------------------------------- stock

def _merge_stock(traders_text: str, traders) -> tuple:
    lines = traders_text.splitlines()
    starts = [i for i, l in enumerate(lines)
              if l.startswith('{ Trader Name:')]
    inserted, new_lines = 0, list(lines)
    for k in range(len(starts) - 1, -1, -1):
        b = starts[k]
        e = starts[k + 1] if k + 1 < len(starts) else len(lines)
        blk = lines[b:e]
        if any('Frontier_Licence_' in l for l in blk):
            continue
        name = lines[b].replace('{ Trader Name: ', '').strip()
        j = e - 1
        while j > b and not lines[j].strip():
            j -= 1
        cur_max = 0
        for l in blk:
            mi = re.match(r'^\s*Item(\d+):', l)
            if mi:
                cur_max = max(cur_max, int(mi.group(1)))
        new_lines.insert(j, f'  Item{cur_max + 1}: '
                         f'"Frontier_Licence_{slug(name)}, '
                         f'{LICENCE_PRICE}, 1-1"')
        inserted += 1
    return '\n'.join(new_lines) + '\n', inserted


def _aide_commerce_html() -> str:
    """Guide de la console commerçante (option AIDE des hubs T1/T2),
    ouvert via %SHARED_DATA% — voir console_apps._aide_html pour l'atelier."""
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Console commerçante</title>
<style>
 body {{ font-family: Segoe UI, Arial, sans-serif; background:#12181d;
        color:#dde6ee; margin:0; padding:18px 22px; font-size:14px; }}
 h1 {{ font-size:20px; color:#ffd479; margin:0 0 4px; }}
 h2 {{ font-size:15px; color:#8fd0ff; margin:18px 0 6px;
       border-bottom:1px solid #2b3a46; padding-bottom:3px; }}
 code {{ background:#1b242c; color:#9fe6a0; padding:1px 5px;
         border-radius:3px; font-family:Consolas,monospace; }}
 .note {{ background:#1b242c; border-left:3px solid #ffd479;
          padding:8px 12px; margin:8px 0; }}
 ol,ul {{ margin:6px 0 6px 18px; padding:0; }} li {{ margin:3px 0; }}
 table {{ border-collapse:collapse; }}
 th,td {{ text-align:left; padding:4px 10px; border-bottom:1px solid #23303a; }}
 th {{ color:#8fd0ff; }}
</style></head><body>
<h1>Console commerçante Frontier</h1>
<div class="note"><b>Première ouverture de la session</b> : le jeu compile
le dialogue au premier contact — patientez quelques secondes, ce n'est pas
un plantage. Idem au premier affichage de cette page.</div>

<h2>1. Obtenir une console</h2>
<table>
<tr><th></th><th>Console T1</th><th>Console T2</th><th>Console T3</th></tr>
<tr><td>Recette (atelier / fabricateur)</td>
    <td>5 électroniques + 10 plastique</td>
    <td>5 consoles T1 + 20 {RELIC_ITEM}</td>
    <td>5 consoles T2 + 20 {RELIC_ITEM}</td></tr>
<tr><td>Budget du cycle (achat <b>et</b> vente)</td>
    <td>{BUDGET_CYCLE:,} cr</td><td>{BUDGET_CYCLE2:,} cr</td>
    <td><b>illimité</b></td></tr>
<tr><td>Taux appliqués <span style="color:#9fe6a0">achat / vente</span></td>
    <td>×{FACT_ACHAT['']:.2f} / ×{FACT_VENTE['']:.2f}</td>
    <td>×{FACT_ACHAT['2']:.2f} / ×{FACT_VENTE['2']:.2f}</td>
    <td>×{FACT_ACHAT['3']:.2f} / ×{FACT_VENTE['3']:.2f}</td></tr>
<tr><td>Vendre le container « VENTE » en un clic</td>
    <td>non</td><td><b>oui</b></td><td><b>oui</b></td></tr>
<tr><td>Prix d'une licence de commerçant</td>
    <td colspan="3">{LICENCE_PRICE:,} cr, chez le commerçant lui-même
    (consommée à l'activation)</td></tr>
<tr><td>Stock du marchand</td>
    <td colspan="3"><b>limité dans les deux sens</b> : quantité vendue par
    le marchand (colonne stock) et quantité qu'il accepte encore d'acheter
    (stock max). Vaut aussi pour la <b>vente du container en un clic</b> :
    quand l'acheteur le plus offrant est épuisé, la vente <b>passe à
    l'acheteur suivant</b> (prix inférieur) ; ce que personne n'achète
    demeure dans le container. Remis à plein au réapprovisionnement.</td></tr>
<tr><td>Réapprovisionnement</td>
    <td colspan="3">budget <b>et</b> stock remis à plein toutes les
    {REAPRO_S // 60} minutes de session de jeu</td></tr>
</table>
<div class="note">
<b>Chaque console a ses propres commerçants activés</b> : activer un
commerçant sur la T1 ne l'ouvre ni sur la T2 ni sur la T3. Les compteurs
de stock sont eux aussi <b>propres à chaque console</b>.<br>
<b>Le budget du cycle est partagé entre achats et ventes</b> : vendre
consomme le même quota que d'acheter. Sur la T3 il est sans limite
pratique — <b>seul le stock du marchand vous arrête</b>.<br>
<b>La T1 n'a pas la vente automatique du container</b> : c'est le
premier palier, on y commerce commerçant par commerçant. La T2 débloque
la vente du container « VENTE » en un clic, la T3 ajoute le budget
illimité.
</div>

<h2>2. Activer un commerçant</h2>
<ol>
 <li>Allez chez le commerçant voulu et <b>achetez sa licence</b>
  ({LICENCE_PRICE:,} cr — vendue uniquement par lui-même).</li>
 <li>Sur la console : <b>Activer un commerçant (1 licence)</b> — la licence
  est consommée, le commerçant apparaît dans <b>Mes boutiques actives</b>.</li>
 <li>Chaque console T2 peut activer plusieurs commerçants ; les licences
  sont propres à chaque commerçant.</li>
</ol>

<h2>3. Acheter et vendre</h2>
<ul>
 <li><b>ACHETER</b> : catalogue du commerçant, prix fixes. Choisissez un
  objet puis <b>saisissez la quantité</b> (clampée à votre crédit et au
  budget restant du cycle) ou prenez <b>×MAX</b>.</li>
 <li><b>VENDRE</b> : uniquement ce que le commerçant recherche. Choisissez
  un objet puis <b>saisissez la quantité</b> (automatiquement limitée à ce
  que vous possédez) ou prenez <b>×MAX</b> (tout votre stock).</li>
 <li>Le catalogue suit exactement les commerçants du jeu : si un marchand
  vend ou achète un objet (blocs compris), il est dans la console.</li>
</ul>

<h2>4. Vente du container « VENTE » (consoles T2 et T3)</h2>
<ol>
 <li>Nommez un container de votre base <code>VENTE</code>.</li>
 <li>Déposez-y ce que vous voulez vendre.</li>
 <li>Sur la console : <b>VENDRE le container « VENTE »</b> — tout ce
  qu'au moins un commerçant activé achète est vendu <b>au meilleur prix
  parmi eux</b> ; le reste reste dans le container.</li>
 <li>La vente affiche une <b>FACTURE</b> détaillée (marchand | item |
  quantité | prix unitaire | total) avec la ligne <b>TOTAL VENTES</b>.
  Elle est paginée <b>5 lignes par page</b> (12 pages) : utilisez
  « Page suivante » / « Page précédente ».</li>
</ol>

<h2>5. Points à connaître</h2>
<ul>
 <li>Le budget se réinitialise tout seul au fil de la session — pas
  d'action à faire.</li>
 <li>Les prix des options ×MAX dépendent de votre crédit et du stock du
  marchand au moment de l'achat.</li>
 <li>Besoin de trier vos ressources ou d'afficher un coffre sur un écran ?
  Voir la <b>console d'atelier</b> et son option AIDE.</li>
</ul>
</body></html>"""


# ---------------------------------------------------------------- dialogues

def _opt(n, text, nxt, cond=None, execute=None):
    L = [f'  Option_{n}: "{text}"']
    if cond:
        L.append(f'  OptionIf_{n}: "{cond}"')
    if execute:
        L.append(f'  OptionExecute_{n}: "{execute}"')
    L.append(f'  OptionNext_{n}: {nxt}')
    return L


def _node(D, name, lines):
    D.append('{ +Dialogue Name: ' + name)
    D.extend(lines)
    D.append('}')


def _fonc_stock(tag: str = "") -> str:
    """Lecture/ecriture du compteur de stock d'un couple (marchand, item).

    Stockage : `,trader:item:qty,` dans la Variable_N dbplayer_string
    `Frontier_Stk{tag}` (une par arbre). Pourquoi pas une globale : l'API
    AddToGlobalVar ne LIT pas (DialogueSystem.cs:2231 `return _addVal`) et
    il n'existe aucun GetGlobalVar. La cle melange marchand ET item, avec
    un offset de 5000 pour les ventes (pas de collision achat/vente).
    """
    return (
        # trace horodatee : correle un bruit moteur (SetLabel...) avec
        # l'action du joueur. Prefixe unique pour un grep : APP-TRACE
        "void Frontier_Trace(string q) {<nl>"
        "  UnityEngine.Debug.Log('APP-TRACE: ' + q);<nl>"
        "}<nl>"
        "int Frontier_StkDe(string lst, int t, int i) {<nl>"
        "  if (lst == null) { return 0; }<nl>"
        "  string cle = ',' + t.ToString() + ':' + i.ToString() + ':'"
        ";<nl>"
        "  int p = lst.IndexOf(cle);<nl>"
        "  if (p < 0) { return 0; }<nl>"
        "  int d = p + cle.Length;<nl>"
        "  int f = lst.IndexOf(',', d);<nl>"
        "  if (f < 0) { return 0; }<nl>"
        "  return int.Parse(lst.Substring(d, f - d));<nl>"
        "}<nl>"
        "string Frontier_StkMaj(string lst, int t, int i, int q) {<nl>"
        "  if (lst == null) { lst = ','; }<nl>"
        "  string cle = ',' + t.ToString() + ':' + i.ToString() + ':'"
        ";<nl>"
        "  int p = lst.IndexOf(cle);<nl>"
        "  if (p < 0) { return lst + t.ToString() + ':' + i.ToString() + "
        "':' + q.ToString() + ','; }<nl>"
        "  int d = p + cle.Length;<nl>"
        "  int f = lst.IndexOf(',', d);<nl>"
        "  if (f < 0) { f = lst.Length; }<nl>"
        "  return lst.Substring(0, d) + q.ToString() + lst.Substring(f)"
        ";<nl>"
        "}<nl>"
        # stock disponible avant plafond : UNE fonction pour tous les
        # items. L'Output est une interpolation C# : {Frontier_Dispo(a,b,c)}
        # y est evalue a l'affichage.
        "int Frontier_Dispo(int t, int i, int smax) {<nl>"
        f"  return smax - Frontier_StkDe(Frontier_Stk{tag}, t, i);<nl>"
        "}"
    )


def _prix(px: int, kind: str, tag: str) -> int:
    """Prix effectif d'une transaction sur cette console.

    T1 : achat x1.60 / vente x0.40 ; T2 : x1.40 / x0.50 ; T3 : x1.20 /
    x0.60. Les paliers hauts servent donc deux fois : budget plus large ET
    meilleur taux. Jamais inferieur a 1 credit."""
    f = FACT_ACHAT.get(tag, 1.0) if kind == 'buy' else FACT_VENTE.get(tag, 1.0)
    return max(1, int(round(px * f)))


def _build_dialogues(traders, catalog, lic_price, budget, reapro, tag='',
                     names=None):
    """Arbre de la console. tag='' = T1 ; tag='2' = T2 (memes noeuds,
    suffixe 2 sur les noms, sur Frontier_Spent/Restock et sur les flags
    Frontier_Active{tag}{w} : CHAQUE console a ses propres commercants
    actives (vecu 18/11 : une licence activee en T1 ouvrait la boutique
    en T2). tag='' garde les noms Frontier_Active1..3 — les deblocages
    deja faits sur T1 restent valides)."""
    D = []
    slugs = [slug(t) for t in traders]
    names = names or {}

    def dn(key):
        """Nom affiche : traduit (FR puis EN) sinon nom interne."""
        return names.get(key, key)

    hub = ['  NPCName: "Borne commerçante"',
           '  Output: "Console commerçante personnelle. Activez un '
           'commerçant avec sa licence (achetée chez lui), puis accédez à '
           'sa boutique. Première ouverture de la session : patientez '
           'quelques secondes (compilation)."',
           f'  Variable_1: "Frontier_Active{tag}1", param1: dbplayer_int',
           f'  Variable_2: "Frontier_Active{tag}2", param1: dbplayer_int',
           f'  Variable_3: "Frontier_Active{tag}3", param1: dbplayer_int',
           f'  Variable_4: "Frontier_Spent{tag}", param1: dbplayer_int',
           f'  Variable_5: "Frontier_Restock{tag}", param1: dbplayer_int',
           # montants de la DERNIERE operation, affiches dans les outputs
           # (les Output sont des methodes C# interpolees : {Var} marche)
           f'  Variable_6: "Frontier_DA{tag}", param1: dbplayer_int',
           f'  Variable_7: "Frontier_DV{tag}", param1: dbplayer_int',
           # STOCK du marchand : UNE chaine par arbre, format
           # ",trader:item:qty,". L'API AddToGlobalVar ne permet PAS de
           # lire (elle retourne la valeur ajoutee, preuve DialogueSystem
           # .cs:2231) : les compteurs par item doivent donc vivre dans une
           # Variable_N dbplayer_string, lue a l'entree du state.
           f'  Variable_8: "Frontier_Stk{tag}", param1: dbplayer_string',
           # FACTURE : 6 pages de 10 lignes + compteur. Les balises
           # `@p9` de la doc NE FONCTIONNENT PAS en 1.20.1 (aucun dialogue
           # du jeu ni de RE2 ne les utilise, et le texte s'affiche d'un
           # bloc en reduisant la police) : pagination par NŒUDS.
           f'  Variable_9: "Frontier_F1{tag}", param1: dbplayer_string',
           f'  Variable_10: "Frontier_F2{tag}", param1: dbplayer_string',
           f'  Variable_11: "Frontier_F3{tag}", param1: dbplayer_string',
           f'  Variable_12: "Frontier_F4{tag}", param1: dbplayer_string',
           f'  Variable_13: "Frontier_F5{tag}", param1: dbplayer_string',
           f'  Variable_14: "Frontier_F6{tag}", param1: dbplayer_string',
           f'  Variable_15: "Frontier_F7{tag}", param1: dbplayer_string',
           f'  Variable_16: "Frontier_F8{tag}", param1: dbplayer_string',
           f'  Variable_17: "Frontier_F9{tag}", param1: dbplayer_string',
           f'  Variable_18: "Frontier_F10{tag}", param1: dbplayer_string',
           f'  Variable_19: "Frontier_F11{tag}", param1: dbplayer_string',
           f'  Variable_20: "Frontier_F12{tag}", param1: dbplayer_string',
           f'  Variable_21: "Frontier_Fnb{tag}", param1: dbplayer_int',
           f'  Functions: "{_fonc_stock(tag)}"',
           f'  Execute: "Frontier_Trace(\'commerce{tag}\');"']
    # numerotation CONTIGUE : le moteur s'arrete au premier numero manquant
    # (vecu 17/11 : options 1,2,8,9 -> l'aide en 8 n'apparaissait pas)
    nopt = 0

    def hub_opt(text, nxt, execute=None):
        nonlocal nopt
        nopt += 1
        return _opt(nopt, text, nxt, execute=execute)

    hub += hub_opt('Mes boutiques actives', f'Frontier_THub_shops{tag}_p1')
    hub += hub_opt('Activer un commerçant (1 licence)',
                   f'Frontier_THub_act{tag}_p1')
    # vente automatique du container « VENTE » : T2 et T3, jamais T1
    # (choix de jeu : il faut au moins une T2 pour vendre en un clic)
    if tag in ('2', '3'):
        hub += hub_opt('VENDRE le container « VENTE »',
                       f'Frontier_THub{tag}_container')
    hub += hub_opt('AIDE (guide de la console)', f'Frontier_THub_aide{tag}')
    hub += hub_opt('Quitter', 'End')
    _node(D, f'Frontier_TraderHub{tag}', hub)
    D.append('{ +Dialogue Name: Frontier_THub_aide' + tag + '\n'
             '  NPCName: "Borne commerçante"\n'
             '  Output: "Ouverture de l\'aide — patientez quelques secondes '
             'si la page reste blanche (premier lancement de la session)."\n'
             # Functions = DECLARATIONS (un appel nu finit au niveau classe :
             # CS0501, vecu 17/11) ; Execute = lance a l'entree du state
             '  Functions: "void Frontier_AideOuvrir' + tag + '() {<nl>  '
             "Frontier_Trace('aide html" + tag + "');<nl>  "
             'OpenHtmlWindow(\'Console commercante - aide\', '
             f"'%SHARED_DATA%/{AIDE_COMMERCE_FILE}', "
             # y decale de ~2 lignes sous la fenetre de dialogue, comme
             # l'aide de l'atelier : le texte d'attente reste visible
             '0.14f, 0.14f, 0.72f, 0.80f);<nl>}"\n'
             '  Execute: "Frontier_AideOuvrir' + tag + '();"\n'
             '  Option_1: "Retour"\n'
             f'  OptionNext_1: Frontier_TraderHub{tag}\n'
             '}\n')

    def pages(prefix, entries, back_to):
        npages = max(1, (len(entries) + HUB_PER_PAGE - 1) // HUB_PER_PAGE)
        for p in range(npages):
            chunk = entries[p * HUB_PER_PAGE:(p + 1) * HUB_PER_PAGE]
            lines = ['  NPCName: "Borne commerçante"',
                     f'  Output: "Page {p + 1}/{npages}"']
            n = 0
            for ent in chunk:
                n += 1
                lines += _opt(n, ent[0], ent[2], cond=ent[1])
            n += 1
            if p + 1 < npages:
                lines += _opt(n, 'Page suivante', f'{prefix}_p{p + 2}')
            else:
                lines += _opt(n, 'Retour', back_to)
            _node(D, f'{prefix}_p{p + 1}', lines)

    shops = [(f'{t} — boutique', f'(Frontier_Active{tag}{w} & {b}) != 0',
              f'Frontier_Tshop{tag}_{s}_menu')
             for i, (t, s) in enumerate(zip(traders, slugs))
             for w, b in [_bit_of(i)]]
    pages(f'Frontier_THub_shops{tag}', shops, f'Frontier_TraderHub{tag}')
    acts = [(f'{t} — ACTIVER', f"HasItem('Frontier_Licence_{s}', 1)",
             f'Frontier_Tact{tag}_{s}')
            for t, s in zip(traders, slugs)]
    pages(f'Frontier_THub_act{tag}', acts, f'Frontier_TraderHub{tag}')

    for ti, (t, s) in enumerate(zip(traders, slugs)):
        w, b = _bit_of(ti)
        c = catalog[s]
        # porte de reapro : budget reinitialise apres cooldown
        _node(D, f'Frontier_Tgate{tag}_{s}', [
            f'  Next_1: Frontier_Tbuy{tag}_{s}_p1',
            f'  NextIf_1: "Frontier_Spent{tag} < {budget}"',
            f'  Next_2: Frontier_Treset{tag}_{s}',
            '  NextIf_2: "GetGameTimeInSec() >= '
            f'Frontier_Restock{tag}"',
            f'  Next_3: Frontier_Twait{tag}_{s}',
        ])
        # remise a niveau du stock d'achat au meme moment que le budget :
        # les compteurs d'ACHATS du cycle reviennent a 0 (stock plein).
        # Une methode par trader, appelee par Execute_1 (limite 150 car).
        # remise a plein : le budget repart a zero ET le stock du marchand
        # est vide de ses compteurs (une seule chaine pour tout l'arbre)
        sets = (f"Frontier_Stk{tag} = ',';<nl>  "
                f"SetGlobalVar('Frontier_Stk{tag}', ',');<nl>  ")
        _node(D, f'Frontier_Treset{tag}_{s}', [
            f'  Functions: "void Frontier_Rst{tag}_{s}() {{<nl>  {sets}}}"',
            f'  Execute_1: "Frontier_Rst{tag}_{s}(); '
            f'Frontier_Spent{tag} = 0; '
            f'Frontier_Restock{tag} = GetGameTimeInSec() + {reapro}"',
            f'  Next_1: Frontier_Tbuy{tag}_{s}_p1',
        ])
        _node(D, f'Frontier_Twait{tag}_{s}', [
            f'  NPCName: "{t}"',
            '  Output: "Réapprovisionnement en cours — le commerçant '
            'complète son stock. Revenez plus tard."',
            *_opt(1, 'Retour', f'Frontier_Tshop{tag}_{s}_menu'),
        ])
        _node(D, f'Frontier_Tact{tag}_{s}', [
            '  NPCName: "Borne commerçante"',
            f'  Output: "Activer le commerçant {t} ? Votre licence de '
            f'{lic_price} cr sera consommée (définitif)."',
            *_opt(1, "Confirmer l'activation",
                  f'Frontier_Tshop{tag}_{s}_menu',
                  execute=f"RemoveItem('Frontier_Licence_{s}', 1); "
                          f"Frontier_Active{tag}{w} = Frontier_Active{tag}{w} | {b}"),
            *_opt(2, 'Annuler', f'Frontier_THub_act{tag}_p1'),
        ])
        _node(D, f'Frontier_Tshop{tag}_{s}_menu', [
            f'  NPCName: "{t}"',
            f'  Output: "Commerçant {t}. Achetez son catalogue ou vendez-lui '
            f'vos marchandises."',
            *_opt(1, 'ACHETER (son catalogue)', f'Frontier_Tgate{tag}_{s}'),
            *_opt(2, "VENDRE (ce qu'il recherche)",
                  f'Frontier_Tsell{tag}_{s}_p1'),
            *_opt(3, 'Retour au hub', f'Frontier_TraderHub{tag}'),
        ])

        for kind in ('buy', 'sell'):
            kl = kind[0]
            # prix du PALIER applique ici : tout le reste du noeud
            # (Outputs, calculs, xMAX) utilise ce prix effectif
            entries = [(i_, m_, _prix(px_, kind, tag), s_)
                       for i_, m_, px_, s_ in c[kind]]
            lbl = 'ACHAT' if kind == 'buy' else 'VENTE'
            need = ('Crédits ou approvisionnement insuffisants. Le '
                    'commerçant réapprovisionne périodiquement.'
                    if kind == 'buy' else 'Stock insuffisant.')
            other = 'sell' if kind == 'buy' else 'buy'
            other_lbl = "VENDRE (ce qu'il recherche)" if kind == 'buy' \
                else 'ACHETER (son catalogue)'
            _node(D, f'Frontier_Tnm{tag}_{s}_{kl}', [
                f'  NPCName: "{t}"',
                f'  Output: "{need}"',
                *_opt(1, 'Retour', f'Frontier_T{kind}{tag}_{s}_p1'),
            ])
            npages = max(1, (len(entries) + PER_PAGE - 1) // PER_PAGE)
            for p in range(npages):
                chunk = entries[p * PER_PAGE:(p + 1) * PER_PAGE]
                lines = [f'  NPCName: "{t}"',
                         f'  Output: "{t} — {lbl} (page {p + 1}/{npages})"']
                n = 0
                for i0, (iname, meta, px, _stk) in enumerate(chunk):
                    i = p * PER_PAGE + i0
                    n += 1
                    lines += _opt(n, f'{dn(iname)} — {px} cr',
                                  f'Frontier_Tq{tag}_{s}_{kl}{i}')
                n += 1
                lines += _opt(n, other_lbl, f'Frontier_T{other}{tag}_{s}_p1')
                n += 1
                if p + 1 < npages:
                    lines += _opt(n, 'Page suivante',
                                  f'Frontier_T{kind}{tag}_{s}_p{p + 2}')
                else:
                    lines += _opt(n, 'Retour au menu du commerçant',
                                  f'Frontier_Tshop{tag}_{s}_menu')
                _node(D, f'Frontier_T{kind}{tag}_{s}_p{p + 1}', lines)
            for i, (iname, meta, px, stk) in enumerate(entries):
                ref = f"'{iname}'" + (f", {meta}" if meta else '')
                page = i // PER_PAGE + 1
                qn = f'Frontier_Tq{tag}_{s}_{kl}{i}'
                qi = f'Frontier_Tqi{tag}_{s}_{kl}{i}'
                if kind == 'buy':
                    # cle de stock : marchand + item (offset 5000 pour les
                    # ventes), lue/ecrite dans Frontier_Stk{tag}
                    kstk = ti * 10000 + i
                    # UNE fonction parametree pour tous les items (declaree
                    # dans le hub) : une methode par item faisait 2000
                    # methodes et 214 Ko de C# par arbre, donc plusieurs
                    # secondes de compilation Roslyn a la premiere ouverture.
                    dispo_txt = f'{{Frontier_Dispo({ti}, {kstk}, {stk})}}'
                    qlines_fn = []
                else:
                    kstk = ti * 10000 + 5000 + i
                    # ce que le marchand peut encore acheter (stock max)
                    dispo_txt = (f'{{Frontier_Dispo({ti}, {kstk}, {stk})}} '
                                 'restant(s)')
                    qlines_fn = []
                qlines = [f'  NPCName: "{t}"',
                          f"  Output: \"{dn(iname)} — {px} cr l'unité ({lbl}). "
                          f"Disponible : {dispo_txt}. "
                          f"Crédit : {{Player.Credit}} cr. "
                          f"Dernier {'achat' if kind == 'buy' else 'gain'} : "
                          f"{{Frontier_D{'A' if kind == 'buy' else 'V'}{tag}}} "
                          f'cr"'] + qlines_fn
                if kind == 'buy':
                    # variables UNIQUES par etat : le compilateur dialogue
                    # genere une classe par arbre, des champs homonymes dans
                    # plusieurs etats = CS0102 (doublons). Elles sont donc
                    # declarees dans le seul noeud de SAISIE (qi) : la fusion
                    # en une classe les rend visibles depuis Tq.
                    vq = f'q_{s}_{kl}{i}'
                    vr = f'rem_{s}_{kl}{i}'
                else:
                    vq = f'qs_{s}_s{i}'
                meta_part = f", {meta}" if meta else ''
                if kind == 'buy':
                    # clamp : stock du marchand, budget du cycle, puis credit
                    corps = (f"int dispo = {stk} - "
                             f"Frontier_StkDe(Frontier_Stk{tag}, {ti}, "
                             f"{kstk}); "
                             f"if (dispo < {vq}) {{ {vq} = dispo; }} "
                             f"{vr} = ({budget} - Frontier_Spent{tag}) "
                             f"/ {px}; if ({vr} < {vq}) {{ {vq} = {vr}; }} "
                             f"int maxc = (int)(Player.Credit / {px}); "
                             f"if (maxc < {vq}) {{ {vq} = maxc; }} "
                             f"if ({vq} > 0) {{ Player.Credit -= {vq} * {px}; "
                             f"Frontier_Spent{tag} += {vq} * {px}; "
                             f"AddItem({ref}, {vq}); "
                             f"int deja = Frontier_StkDe(Frontier_Stk{tag}, "
                             f"{ti}, {kstk}); "
                             f"Frontier_Stk{tag} = Frontier_StkMaj("
                             f"Frontier_Stk{tag}, {ti}, {kstk}, "
                             f"deja + {vq}); "
                             f"SetGlobalVar('Frontier_Stk{tag}', "
                             f"Frontier_Stk{tag}); "
                             f"Frontier_DA{tag} = {vq} * {px}; "
                             f"Frontier_DV{tag} = 0; }}")
                    # la SAISIE est sur un noeud enfant : un champ Input sur
                    # ce noeud s'appliquerait AUSSI a l'option xMAX (vecu
                    # 17/11 : xMAX demandait un nombre)
                    qlines += _opt(1, 'SAISIR la quantité', qi)
                    qlines += _opt(2, '×MAX — stock, budget et crédit', qn,
                                   execute=(f"{vq} = (int)(Player.Credit / "
                                            f"{px}); " + corps))
                else:
                    # VENTE : clamp au stock reel du joueur (GetItems), au
                    # stock MAX que le marchand accepte encore d'acheter
                    # (5e champ du TraderNPCConfig), puis au budget restant.
                    corps = (f"foreach (DialogueSystem.ItemInfo it in "
                             f"GetItems()) {{ if (it.Name == '{iname}') {{ "
                             f"if (it.Count < {vq}) {{ {vq} = it.Count; }} "
                             f"}} }} int dejs = Frontier_StkDe("
                             f"Frontier_Stk{tag}, {ti}, {kstk}); "
                             f"int maxs = {stk} - dejs; "
                             f"if (maxs < {vq}) {{ {vq} = maxs; }} "
                             f"int maxb = ({budget} - "
                             f"Frontier_Spent{tag}) / {px}; "
                             f"if (maxb < {vq}) {{ {vq} = maxb; }} "
                             f"if ({vq} > 0) {{ RemoveItem('{iname}'"
                             f"{meta_part}, {vq}); Player.Credit += {vq} * "
                             f"{px}; Frontier_Spent{tag} += {vq} * {px}; "
                             f"Frontier_Stk{tag} = Frontier_StkMaj("
                             f"Frontier_Stk{tag}, {ti}, {kstk}, "
                             f"dejs + {vq}); "
                             f"SetGlobalVar('Frontier_Stk{tag}', "
                             f"Frontier_Stk{tag}); "
                             f"Frontier_DV{tag} = {vq} * {px}; "
                             f"Frontier_DA{tag} = 0; }}")
                    qlines += _opt(1, 'SAISIR la quantité', qi)
                    qlines += _opt(2, '×MAX — stock et budget', qn,
                                   execute=(f"{vq} = 0; " + corps))
                qlines += _opt(3, f'Retour à la page {page}',
                               f'Frontier_T{kind}{tag}_{s}_p{page}')
                qlines += _opt(4, 'Retour au hub', f'Frontier_TraderHub{tag}')
                _node(D, qn, qlines)
                # noeud de saisie : Input + application
                _node(D, qi, [
                    f'  NPCName: "{t}"',
                    f"  Output: \"{dn(iname)} — {px} cr l'unité. "
                    f"Tapez la quantité ({lbl}).\"",
                    '  Input: "Quantité :"',
                    f'  Variable_1: "{vq}", param1: int']
                    + ([f'  Variable_2: "{vr}", param1: int']
                       if kind == 'buy' else [])
                    + _opt(1, 'VALIDER la quantité',
                           f'Frontier_Tq{tag}_{s}_{kl}{i}',
                           execute=(f"if (!IsInputOk()) {{ return; }} "
                                    f"{vq} = InputResultAsInt(); " + corps))
                    + _opt(2, 'Retour', qn)
                    + _opt(3, 'Retour au hub', f'Frontier_TraderHub{tag}'))
    return D


# ---------------------------------------------------------------- loc

def _csv_row(key: str, en: str, fr: str, ncols: int = 18) -> str:
    vals = [key, en, '', fr] + [''] * (ncols - 4)
    return ','.join('"' + v.replace('"', '""') + '"' if (',' in v or '"' in v
                                                          or v == '')
                    else v for v in vals)


def _merge_loc(loc_text: str, traders, relic_ok: bool) -> tuple:
    kept = []
    for ln in loc_text.rstrip('\n').splitlines():
        key = ln.split(',')[0].strip('"')
        # purge limitee aux cles QUE CE MODULE ECRIT : le prefixe large
        # (`Frontier_`) effacait aussi les cles de la console atelier
        if key.startswith(('Frontier_Console_Commercant',
                           'bkiFrontier_Console_Commercant',
                           'Frontier_Licence_')):
            continue
        # le commentaire de section s'accumulait aussi (70 copies dans
        # Frontier-FR au 18/11, une par regen)
        if ln.strip().startswith('# ===== Console commer'):
            continue
        kept.append(ln)
    kept += ['', '# ===== Console commerçante Frontier-FR =====']
    kept.append(_csv_row('Frontier_Console_Commercant', 'Merchant Console',
                         'Console commerçante'))
    kept.append(_csv_row(
        'bkiFrontier_Console_Commercant',
        'Personal merchant console. Activate a trader with his licence '
        '(bought from him), then trade from your base.',
        'Console commerçante personnelle. Activez un commerçant avec sa '
        'licence (achetée chez lui), puis commerciez depuis votre base ou '
        'votre vaisseau capital.'))
    if relic_ok:
        for t in traders:
            s = slug(t)
            kept.append(_csv_row(
                f'Frontier_Licence_{s}info',
                f'Trading licence of trader {t}. Consumed when activating '
                f'{t} on an advanced merchant console. Sold ONLY by {t} '
                f'himself.',
                f'Licence commerciale du commerçant {t}. Consommée lors de '
                f'l\'activation de {t} sur une console commerçante avancée. '
                f'Vendue UNIQUEMENT par {t} lui-même.'))
        kept.append(_csv_row(
            CONSOLE2_BASE,
            'Advanced merchant console (x10 restock)',
            'Console commerçante avancée (réapprovisionnement x10)'))
        kept.append(_csv_row(
            f'bki{CONSOLE2_BASE}',
            'Advanced merchant console. Same catalogue as the basic '
            'console, x10 restock budget. Built from 5 T1 consoles and 20 '
            'ancient relics. Activate traders with their licences.',
            'Console commerçante avancée. Même catalogue que la console '
            'de base, budget de réapprovisionnement x10. Se fabrique avec '
            '5 consoles T1 et 20 reliques anciennes. Activez les '
            'commerçants avec leurs licences.'))
        kept.append(_csv_row(
            CONSOLE3_BASE,
            'Merchant console T3 (unlimited cycle budget)',
            'Console commerçante T3 (budget de cycle illimité)'))
        kept.append(_csv_row(
            f'bki{CONSOLE3_BASE}',
            'Merchant console T3. Same catalogue, cycle budget practically '
            'unlimited: the only limit is the trader stock. Built from 5 T2 '
            'consoles and 20 ancient relics. Activate traders with their '
            'licences.',
            'Console commerçante T3. Même catalogue, budget de cycle '
            'pratiquement illimité : la seule limite est le stock du '
            'marchand. Se fabrique avec 5 consoles T2 et 20 reliques '
            'anciennes. Activez les commerçants avec leurs licences.'))
    return '\n'.join(kept) + '\n'


# ---------------------------------------------------------------- noms affiches

GAME_LOC = Path(r'C:/Program Files (x86)/Steam/steamapps/common/'
                r'Empyrion - Galactic Survival/Content/Extras/Localization.csv')


def _load_names(root: Path) -> dict:
    """Cle d'item -> nom affiche (Francais, sinon Anglais, sinon cle).
    Sources : Localization VANILLE du jeu puis celle du scenario
    (prioritaire). Noms manquants = nom interne affiche tel quel."""
    import csv

    def lire(p: Path, acc: dict) -> None:
        if not Path(p).is_file():
            return
        with Path(p).open(encoding='utf-8-sig', errors='replace',
                          newline='') as fh:
            for r in csv.reader(fh):
                if len(r) < 4 or not r[0] or r[0] == 'KEY':
                    continue
                key = r[0].strip()
                fr = r[3].strip()
                en = r[1].strip()
                if fr:
                    acc[key] = fr.replace('"', "'")
                elif en:
                    acc.setdefault(key, en.replace('"', "'"))

    acc: dict = {}
    lire(GAME_LOC, acc)
    lire(Path(root) / 'Extras' / 'Localization.csv', acc)
    return acc


# ---------------------------------------------------------------- regen

def _facture_pages(tag: str) -> list:
    """Les 6 noeuds de la facture (10 lignes par page).

    Pagination par NŒUDS : les balises `@p9`/`@d0` documentees dans
    Dialogue-Docu-and-Examples.md section 4.7 n'ont AUCUN effet en 1.20.1
    (aucun dialogue du jeu ni de RE2 ne les utilise ; le texte s'affiche
    d'un bloc et la police se reduit jusqu'a l'illisible — vecu 18/11).
    Options contigues : le moteur s'arrete au premier numero manquant."""
    out = []
    for pg in range(1, 13):
        suffixe = '' if pg == 1 else str(pg)
        lignes = [f'{{ +Dialogue Name: Frontier_THub{tag}_container_vendu{suffixe}',
                  '  NPCName: "Borne commerçante"']
        titre = ('<b>FACTURE FRONTIER</b> — '
                 f'{{Frontier_DV{tag}}} cr' if pg == 1
                 else f'FACTURE FRONTIER — page {pg}/12')
        lignes.append(
            f'  Output: "{titre}\\n{FACT_ENTETE}\\n{FACT_SEP}\\n'
            f'{{Frontier_F{pg}{tag}}}{FACT_SEP}\\n'
            f'<b>TOTAL VENTES : {{Frontier_DV{tag}}} cr</b>'
            ' — solde : {Player.Credit} cr"')
        n = 0
        if pg < 12:
            n += 1
            lignes.append(f'  Option_{n}: "Page suivante ({pg + 1}/12)"')
            lignes.append(
                f'  OptionIf_{n}: "Frontier_Fnb{tag} > {pg * 5}"')
            lignes.append(
                f'  OptionNext_{n}: Frontier_THub{tag}_container_vendu{pg + 1}')
        if pg > 1:
            n += 1
            prec = '' if pg == 2 else str(pg - 1)
            lignes.append(f'  Option_{n}: "Page précédente"')
            lignes.append(
                f'  OptionNext_{n}: Frontier_THub{tag}_container_vendu{prec}')
        n += 1
        lignes.append(f'  Option_{n}: "Retour au hub"')
        lignes.append(f'  OptionNext_{n}: Frontier_TraderHub{tag}')
        lignes.append('}')
        # '\n' final : sans lui les noeuds se collent en « }{ +Dialogue »
        # et le parseur du jeu (comme nos scans) ne voit pas le suivant
        out.append('\n'.join(lignes) + '\n')
    return out


def regen(scenario_root: str | Path) -> dict:
    """Regenere licences + consoles + dialogues depuis les configs
    courantes. Mode fusion : conserve les editions manuelles hors sections
    generees. Retourne un rapport (dict) pour l'interface."""
    root = Path(scenario_root)
    sc = root / 'Content' / 'Configuration'
    items_text = _read(sc / 'ItemsConfig.ecf')
    traders_text = _read(sc / 'TraderNPCConfig.ecf')
    blocks_text = _read(sc / 'BlocksConfig.ecf')
    traders = re.findall(r'^\{ Trader Name: (.+?)\s*$', traders_text, re.M)
    market, item_names = _parse_market(items_text, blocks_text)
    catalog, skipped = _parse_catalog(traders_text, traders, market,
                                      item_names)
    relic_ok = RELIC_ITEM in item_names
    items_new, lic_added = _merge_items(items_text, traders)
    _write(sc / 'ItemsConfig.ecf', items_new)
    blocks_new, blk_added = _merge_blocks(blocks_text,
                                          traders, relic_ok)
    _write(sc / 'BlocksConfig.ecf', blocks_new)
    tpl_new, tpl_added = _merge_templates(_read(sc / 'Templates.ecf'),
                                          traders, relic_ok)
    _write(sc / 'Templates.ecf', tpl_new)
    stock_new, stock_added = _merge_stock(traders_text, traders)
    _write(sc / 'TraderNPCConfig.ecf', stock_new)
    D = _build_dialogues(traders, catalog, LICENCE_PRICE, BUDGET_CYCLE,
                         REAPRO_S, names=_load_names(root))
    if relic_ok:
        D += _build_dialogues(traders, catalog, LICENCE_PRICE,
                              BUDGET_CYCLE2, REAPRO_S, tag='2',
                              names=_load_names(root))
        # T3 : meme arbre, budget de cycle sans limite pratique
        D += _build_dialogues(traders, catalog, LICENCE_PRICE,
                              BUDGET_CYCLE3, REAPRO_S, tag='3',
                              names=_load_names(root))
        # etat container de vente : fonction C# avec les prix d'achat
        # (meilleur prix parmi les commerçants qui achètent l'item)
        item_ids = {m.group(2).split('#')[0].strip(): int(m.group(1))
                    for m in re.finditer(r'\{ \+Item Id: (\d+), '
                                         r'Name: ([^\n,]+)', items_text)}
        for m in re.finditer(r'\{ \+?Block Id: (\d+), Name: ([^\n,]+)',
                             blocks_text):
            # blocs : id BlocksConfig (pas de remap prouve) ; un item
            # homonyme garde la priorite
            item_ids.setdefault(m.group(2).split('#')[0].strip(),
                                int(m.group(1)))
        # container VENTE : T2 et T3 (T1 sans vente automatique)
        for tag, budget in (('2', BUDGET_CYCLE2),
                            ('3', BUDGET_CYCLE3)):
            # TOUS les acheteurs par item, du meilleur prix au moins bon : le
            # container rebondit sur le suivant quand le stock du premier est
            # epuise (demande 18/11). La cle de stock encode le marchand et
            # l'item comme dans les noeuds de vente : ti*10000+5000+i.
            acheteurs: dict = {}
            for ti_, t2_ in enumerate(traders):
                s2_ = slug(t2_)
                for i_, (iname, meta, px, stk) in enumerate(catalog[s2_]['sell']):
                    if meta:
                        continue          # items a meta : prix par qualite, v1 ignore
                    # prix du PALIER de la console qui vend (facteur de vente)
                    acheteurs.setdefault(iname, []).append(
                        (_prix(px, 'sell', tag), ti_ * 10000 + 5000 + i_, stk))
            # dedoublonne par ID : un bloc et un item peuvent partager le meme
            # numero (vecu 17/11 : Key 600 -> ArgumentException Dictionary.Add
            # dans Frontier_VendreContainer, vente entiere morte). MAX_ACH = 4
            # acheteurs par item : au-dela, le gain de confort ne vaut pas la
            # taille du dictionnaire.
            MAX_ACH = 4
            par_id: dict = {}
            for n, lst in acheteurs.items():
                if n not in item_ids:
                    continue
                good = [x for x in lst if x[0] > 0]
                if not good:
                    continue
                good.sort(key=lambda x: -x[0])
                iid = item_ids[n]
                if iid in par_id:
                    continue          # homonyme : le premier item garde la main
                par_id[iid] = good[:MAX_ACH]

            # UN SEUL dictionnaire cle -> long, valeurs PACKED : prix (24 bits)
            # | cle de stock (24) << 24 | stock max (16) << 48. La cle de
            # dictionnaire est id*10+r (r = rang de l'acheteur) : des
            # dictionnaires paralleles ou un int[] litteral declenchaient le
            # garde-fou dup_key, qui compte les accolades numeriques du bloc.
            entrees = [(iid * 10 + r, p | (cle << 24) | (stk << 48))
                       for iid, lst in sorted(par_id.items())
                       for r, (p, cle, stk) in enumerate(lst)]
            info_csharp = ', '.join(f'{{ {k}, {v}L }}' for k, v in entrees)
            # noms d'items pour la FACTURE : id -> nom interne (clé de Loc,
            # affichage identique au reste du dialogue)
            inv_noms = {}
            for n_, i_ in item_ids.items():
                if i_ in par_id:
                    inv_noms.setdefault(i_, n_)
            # APOSTROPHES, pas de guillemets : dans une valeur ECF
            # (`Functions: "..."`) un guillemet interne termine la valeur
            # et tout le reste est perdu (piege documente). Le preprocesseur
            # convertit les apostrophes en guillemets cote jeu.
            noms_csharp = ', '.join(f"{{ {i_}, '{n_}' }}"
                                    for i_, n_ in sorted(inv_noms.items()))
            tnoms_csharp = ', '.join(
                f"{{ {k_}, '{n_.replace(chr(39), '')}' }}"
                for k_, n_ in enumerate(traders))
            # format ECF : fonction mono-ligne, separateurs <nl>, chaines C#
            # entre apostrophes (pattern RE2-FR) ; traces Debug.Log pour le
            # diagnostic (visibles dans la console du jeu)
            fonc = (
                # retrait VERIFIE : RemoveItems compare RemoveSymbol des piles
                # a l'id fourni, et l'id d'inventaire differe de l'id de config
                # (+8192). Sans mesure, le retrait peut echouer en silence ->
                # items vendus mais toujours dans le container (vecu 17/11).
                # meme espace de cle que l'atelier : item (remappe +8192) et
                # bloc (id direct) ne doivent pas se compter ensemble
                'int Frontier_Cle(int id) {<nl>'
                '    return id >= 8192 ? id - 8192 : id + 100000;<nl>'
                '}<nl>'
                'int Frontier_Stock(IContainer c, int id) {<nl>'
                '    int t = 0;<nl>'
                '    foreach (var st in c.GetContent()) {<nl>'
                '        if (Frontier_Cle(st.id) == Frontier_Cle(id)) { '
                't = t + st.count; }<nl>'
                '    }<nl>'
                '    return t;<nl>'
                '}<nl>'
                'int Frontier_Retirer(IContainer c, int id, int qty) {<nl>'
                '    int av = Frontier_Stock(c, id);<nl>'
                '    if (av <= 0) { return 0; }<nl>'
                '    if (qty > av) { qty = av; }<nl>'
                # RemoveItems ne retire rien sur ces containers (vecu 17/11) :
                # SetContent replace les piles par slotIdx, on reecrit le
                # contenu sans les quantites retirees.
                '    var neuf = new List<ItemStack>();<nl>'
                '    int reste = qty;<nl>'
                '    foreach (var st0 in c.GetContent()) {<nl>'
                # copie locale : une variable d'iteration n'est pas modifiable
                # (CS1654, vecu 17/11)
                '        var st = st0;<nl>'
                '        if (reste > 0 && Frontier_Cle(st.id) == '
                'Frontier_Cle(id)) {<nl>'
                '            int pris = st.count < reste ? st.count : reste;<nl>'
                '            st.count = st.count - pris;<nl>'
                '            reste = reste - pris;<nl>'
                '        }<nl>'
                '        if (st.count > 0) { neuf.Add(st); }<nl>'
                '    }<nl>'
                '    c.SetContent(neuf);<nl>'
                '    return av - Frontier_Stock(c, id);<nl>'
                '}<nl>'
                f'void Frontier_VendreContainer{tag}() {{<nl>'
                '    int vendus = 0;<nl>'
                '    int total = 0;<nl>'
                # plafond de VENTE : meme budget de cycle que les achats
                # (vecu 18/11 : la vente n etait limitee par rien)
                f'    int dispo = {budget} - Frontier_Spent{tag};<nl>'
                "    string pg1 = '';"                 "    string pg2 = '';"                 "    string pg3 = '';"                 "    string pg4 = '';"                 "    string pg5 = '';"                 "    string pg6 = '';"                 "    string pg7 = '';"                 "    string pg8 = '';"                 "    string pg9 = '';"                 "    string pg10 = '';"                 "    string pg11 = '';"                 "    string pg12 = '';"
                '<nl>'
                '    int nl4 = 0;<nl>'
                "    UnityEngine.Debug.Log('VENTE: fonction appelée');<nl>"
                "    var container = LocalStructure?.GetDevice<IContainer>"
                "('VENTE');<nl>"
                "    UnityEngine.Debug.Log('VENTE: container=' + (container == "
                "null ? 'INTROUVABLE' : 'trouvé'));<nl>"
                '    if (container == null) return;<nl>'
                f'    var info = new Dictionary<int, long>() '
                f'{{ {info_csharp} }};<nl>'
                # noms pour la FACTURE (items + marchands)
                f'    var noms = new Dictionary<int, string>() '
                f'{{ {noms_csharp} }};<nl>'
                f'    var tnoms = new Dictionary<int, string>() '
                f'{{ {tnoms_csharp} }};<nl>'
                "    UnityEngine.Debug.Log('VENTE: prix connus=' + info.Count);"
                '<nl>'
                "    UnityEngine.Debug.Log('VENTE: stacks dans le container=' "
                "+ container.GetContent().Count);<nl>"
                '    foreach (var item in container.GetContent()) {<nl>'
                "        UnityEngine.Debug.Log('VENTE: stack id=' + item.id + "
                "' count=' + item.count);<nl>"
                '        if (item.count <= 0) continue;<nl>'
                '        if (dispo <= 0) { break; }<nl>'
                '        int baseId = info.ContainsKey(item.id * 10) ? '
                'item.id : item.id - 8192;<nl>'
                '        int q4 = item.count;<nl>'
                # boucle sur les ACHETEURS : du meilleur prix au moins bon,
                # on rebondit tant qu'il reste des items et du budget
                '        for (int r4 = 0; r4 < 4; r4++) {<nl>'
                '            if (q4 <= 0) { break; }<nl>'
                '            if (dispo <= 0) { break; }<nl>'
                '            long inf;<nl>'
                '            if (!info.TryGetValue(baseId * 10 + r4, '
                'out inf)) { break; }<nl>'
                '            int p = (int)(inf & 0xFFFFFFL);<nl>'
                '            int cle4 = (int)((inf >> 24) & 0xFFFFFFL);<nl>'
                '            int smax4 = (int)((inf >> 48) & 0xFFFFL);<nl>'
                # NE VENDRE QU'AUX COMMERCANTS ACTIVES SUR CETTE CONSOLE :
                # sans ce filtre, le container se vendait sur T2/T3 meme
                # avec zero commercant debloque (vecu 18/11). Le marchand
                # est encode dans la cle : bit w/b comme le hub.
                '            int ti4 = cle4 / 10000;<nl>'
                '            int w4 = ti4 / 24 + 1;<nl>'
                '            int b4 = 1 << (ti4 % 24);<nl>'
                '            bool act4 = false;<nl>'
                f'            if (w4 == 1) {{ act4 = (Frontier_Active{tag}1 & '
                'b4) != 0; }<nl>'
                f'            else if (w4 == 2) {{ act4 = '
                f'(Frontier_Active{tag}2 & b4) != 0; }}<nl>'
                f'            else {{ act4 = (Frontier_Active{tag}3 & b4) '
                '!= 0; }<nl>'
                '            if (!act4) { continue; }<nl>'
                f'            int dej4 = Frontier_StkDe('
                f'Frontier_Stk{tag}, cle4 / 10000, cle4 % 10000);<nl>'
                '            int reste4 = smax4 - dej4;<nl>'
                '            if (reste4 <= 0) { continue; }<nl>'
                '            int parte = q4 < reste4 ? q4 : reste4;<nl>'
                '            int maxb = dispo / p;<nl>'
                '            if (maxb < parte) { parte = maxb; }<nl>'
                '            if (parte <= 0) { continue; }<nl>'
                '            int out4 = Frontier_Retirer(container, baseId, '
                'parte);<nl>'
                '            if (out4 == 0) { out4 = Frontier_Retirer('
                'container, item.id, parte); }<nl>'
                '            if (out4 > 0) {<nl>'
                '                Player.Credit += out4 * p;<nl>'
                '                dispo = dispo - out4 * p;<nl>'
                f'                Frontier_Spent{tag} = Frontier_Spent{tag} '
                '+ out4 * p;<nl>'
                f'                Frontier_Stk{tag} = Frontier_StkMaj('
                f'Frontier_Stk{tag}, cle4 / 10000, cle4 % 10000, '
                'dej4 + out4);<nl>'
                f"                SetGlobalVar('Frontier_Stk{tag}', "
                f'Frontier_Stk{tag});<nl>'
                '                q4 = q4 - out4;<nl>'
                '                vendus = vendus + 1;<nl>'
                '                total = total + out4 * p;<nl>'
                # FACTURE : ligne en TABLEAU, 10 lignes par page, 6 pages
                # (la police du dialogue se reduit au-dela : 10 lignes
                # restent lisibles, 20 non — vecu 18/11)
                '                nl4 = nl4 + 1;<nl>'
                '                string nm4 = baseId.ToString();<nl>'
                '                noms.TryGetValue(baseId, out nm4);<nl>'
                "                string tn4 = '?';<nl>"
                '                tnoms.TryGetValue(cle4 / 10000, out tn4);<nl>'
                "                string lg4 = tn4.PadRight(26) + nm4.PadRight(22) "
                "+ ('x' + out4).PadLeft(8) + p.ToString().PadLeft(8) + "
                "(out4 * p).ToString().PadLeft(11) + '\\n';<nl>"
                "                if (nl4 <= 5) { pg1 = pg1 + lg4; }<nl>"
                "                else if (nl4 <= 10) { pg2 = pg2 + lg4; }<nl>"
                "                else if (nl4 <= 15) { pg3 = pg3 + lg4; }<nl>"
                "                else if (nl4 <= 20) { pg4 = pg4 + lg4; }<nl>"
                "                else if (nl4 <= 25) { pg5 = pg5 + lg4; }<nl>"
                "                else if (nl4 <= 30) { pg6 = pg6 + lg4; }<nl>"
                "                else if (nl4 <= 35) { pg7 = pg7 + lg4; }<nl>"
                "                else if (nl4 <= 40) { pg8 = pg8 + lg4; }<nl>"
                "                else if (nl4 <= 45) { pg9 = pg9 + lg4; }<nl>"
                "                else if (nl4 <= 50) { pg10 = pg10 + lg4; }<nl>"
                "                else if (nl4 <= 55) { pg11 = pg11 + lg4; }<nl>"
                "                else if (nl4 <= 60) { pg12 = pg12 + lg4; }<nl>"
                '            }<nl>'
                '        }<nl>'
                '    }<nl>'
                "    if (nl4 == 0) { pg1 = 'Aucun item achete par vos "
                "marches.\\n'; }<nl>"
                f'    Frontier_F1{tag} = pg1;<nl>'
                f'    Frontier_F2{tag} = pg2;<nl>'
                f'    Frontier_F3{tag} = pg3;<nl>'
                f'    Frontier_F4{tag} = pg4;<nl>'
                f'    Frontier_F5{tag} = pg5;<nl>'
                f'    Frontier_F6{tag} = pg6;<nl>'
                f'    Frontier_F7{tag} = pg7;<nl>'
                f'    Frontier_F8{tag} = pg8;<nl>'
                f'    Frontier_F9{tag} = pg9;<nl>'
                f'    Frontier_F10{tag} = pg10;<nl>'
                f'    Frontier_F11{tag} = pg11;<nl>'
                f'    Frontier_F12{tag} = pg12;<nl>'
                f'    Frontier_Fnb{tag} = nl4;<nl>'
                f'    Frontier_DV{tag} = total;<nl>'
                '}')
            D.append(f'{{ +Dialogue Name: Frontier_THub{tag}_container\n'
                     '  NPCName: "Borne commerçante"\n'
                     '  Output: "Vend tout le contenu de votre container nommé '
                     '« VENTE » (dans cette base) — uniquement ce que vos '
                     'commerçants activés achètent ; le reste y reste."\n'
                     # Frontier_DV{tag} est declare par le hub (Variable_7) :
                     # le redeclarer ici = CS0102, arbre commerce mort (17/11)
                     f'  Functions: "{fonc}"\n'
                     '  Option_1: "VENDRE maintenant"\n'
                     f'  OptionExecute_1: "Frontier_VendreContainer{tag}()"\n'
                     f'  OptionNext_1: Frontier_THub{tag}_container_vendu\n'
                     '}\n'
                     # FACTURE : 6 pages de 10 lignes (pagination par
                     # NŒUDS : les balises @p9 de la doc ne font rien en
                     # 1.20.1, le texte s'affiche d'un bloc en reduisant la
                     # police). Une page = 10 lignes, lisibles.
                     + ''.join(_facture_pages(tag))
                     )
    # la section generee precedente (marqueur -> fin de fichier) est retiree
    dlg_prev = _read(sc / 'Dialogues.ecf').rstrip('\n')
    i = dlg_prev.find(MARKER)
    if i >= 0:
        dlg_prev = dlg_prev[:i].rstrip('\n')
    _write(sc / 'Dialogues.ecf',
           dlg_prev + '\n\n' + MARKER + '\n' + '\n'.join(D) + '\n')
    n_nodes = sum(1 for l in D if l.startswith('{ +Dialogue Name:'))
    # guide de la console commerçante (option AIDE des hubs), meme principe
    # que l'aide atelier : SharedData = embarque au Workshop
    aide = root / 'SharedData' / AIDE_COMMERCE_FILE
    aide.parent.mkdir(parents=True, exist_ok=True)
    aide.write_text(_aide_commerce_html(), encoding='utf-8')
    # icone des licences : le moteur scanne SharedData/Content/Bundles/
    # ItemIcons et enregistre chaque PNG (MenuSiteConnectionToken.cs:1836,
    # comme les 1426 PNG de RE2) — aucun bundle Unity a fabriquer.
    # l'icone vit a cote du module dans le package autonome
    # (dist/console_commerce/) et dans assets/icons/ du projet complet
    base = Path(__file__).resolve().parent
    src_ic = next((q for q in (
        base / 'Frontier_Licence.png',
        base.parent.parent / 'assets' / 'icons' / 'Frontier_Licence.png',
        base.parent / 'assets' / 'icons' / 'Frontier_Licence.png')
        if q.is_file()), None)
    if src_ic is not None:
        dst_ic = (root / 'SharedData' / 'Content' / 'Bundles' / 'ItemIcons'
                  / 'Frontier_Licence.png')
        dst_ic.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_ic, dst_ic)
    loc = _read(root / 'Extras' / 'Localization.csv')
    loc_new = _merge_loc(loc, traders, relic_ok)
    _write(root / 'Extras' / 'Localization.csv', loc_new)
    return {'licences': lic_added, 'block': blk_added, 'template': tpl_added,
            'stock': stock_added, 'nodes': n_nodes, 'skipped': skipped,
            'traders': len(traders), 't2': relic_ok}
