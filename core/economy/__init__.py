"""Module economie : edition semantique de TraderNPCConfig.ecf (vendeurs PNJ).

Mecanisme reel du jeu (verifie sur fichiers vanilla 1.x -- voir l'en-tete du
TraderNPCConfig.ecf lui-meme) :
- Chaque marchand est un bloc '{ Trader Name: X }' identifie par son Name (pas d'Id).
- Les items sont des lignes 'Item<N>: "<Nom>, <prix VENTE>, <stock VENTE>, [prix ACHAT], [stock ACHAT max]"'
  ou un prix peut etre une PLAGE absolue ('100-150') ou un FACTEUR sur le MarketPrice
  de l'item dans ItemsConfig/BlocksConfig ('mf=1.1-1.2').
- Pas de restock par item (reglage serveur global), pas de reputation par item
  (uniquement 'Discount' global par marchand).
- Assignation spatiale : cle 'TraderZone' top-level d'un playfield*.yaml, ou
  'Properties: [- Key: TraderZone, Value: X]' sur un groupe de POI -- ne s'applique
  qu'aux PNJ dont le TraderType (dans le blueprint) vaut #ZONE#.
"""
