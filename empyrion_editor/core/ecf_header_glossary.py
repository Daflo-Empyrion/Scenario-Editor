"""
Glossaire clarifie (en francais) des commentaires d'en-tete techniques trouves au debut
des fichiers ECF (BlocksConfig.ecf en particulier -- le plus dense). Ce n'est PAS une
traduction mot a mot : le texte original est souvent tres technique/condense, donc
chaque entree est reformulee pour rester claire, tout en gardant le sens exact.

Organise en sections (categorie -> liste de (terme, explication)) dans le meme ordre
que l'en-tete original, pour rester facile a comparer avec le fichier source.
"""

BLOCKS_CONFIG_GLOSSARY = [
    ("Identifiants (Id)", [
        ("Id 0 a 255", "Reserves au terrain (sol, roches...). Ne jamais reutiliser ces "
                        "numeros pour autre chose."),
        ("Id jusqu'a 2048", "Les blocs identifies par un numero (Id) doivent rester "
                             "sous cette limite."),
        ("Au-dela de 2048", "Pour ajouter un bloc au-dela de cette limite, ne mets pas "
                             "de Id du tout -- utilise seulement 'Block Name: MonBloc' "
                             "(identifie par son nom, pas par un numero)."),
    ]),
    ("Masse des blocs", [
        ("Regle generale", "La masse indiquee correspond a un bloc de 1 metre. Le jeu "
                            "l'ajuste ensuite automatiquement selon la taille reelle du "
                            "bloc :"),
        ("Petite grille (HV, SV)", "Masse reelle = valeur indiquee x 0.125 (bloc de 0.5m)"),
        ("Grande grille (BA, CV)", "Masse reelle = valeur indiquee x 8 (bloc de 2m)"),
    ]),
    ("Proprietes courantes", [
        ("AllowPlacingAt", "Sur quels types de structure ce bloc peut etre pose "
                            "(Base, MS, SS, GV, Terrain)."),
        ("Collide", "Quels types d'objets entrent en collision avec ce bloc "
                     "(mouvement, balles, roquettes, corps a corps, visee). Retirer "
                     "'movement' par exemple rend le bloc traversable a pied tout en "
                     "restant touchable par les armes."),
        ("EnergyIn / EnergyOut", "Consommation/production d'energie, exprimee en kW."),
        ("Texture", "Liste de 6 numeros de texture, dans l'ordre : dessus, dessous, "
                     "nord, sud, ouest, est."),
    ]),
    ("Codes d'explosion", [
        ("1", "Grande explosion aerienne"),
        ("2 a 4", "Petite explosion au sol"),
        ("5 a 6", "Petite explosion aerienne"),
        ("7", "Explosion electrique"),
        ("8 a 9", "Grande explosion aerienne"),
        ("10", "Explosion electrique"),
    ]),
    ("La regle du Ref (heritage)", [
        ("Regle d'ordre", "Un bloc ne peut heriter (Ref) que d'un bloc DEJA DEFINI PLUS "
                           "HAUT dans le fichier (Id ou position plus petite) -- jamais "
                           "d'un bloc plus bas."),
    ]),
    ("Proprietes avancees", [
        ("CustomIcon", "Reutilise une icone deja existante pour l'affichage en jeu "
                        "(ex: 'CustomIcon: DetectorSVT1')."),
        ("PickupTarget", "Objet qui sera automatiquement place dans l'inventaire du "
                          "joueur quand il ramasse ce bloc/appareil. Ne fonctionne que "
                          "sur le bloc PARENT, jamais sur un sous-bloc ('child')."),
        ("TemplateRoot", "Indique quelle recette de craft (Templates.ecf) utiliser pour "
                          "ce sous-groupe -- utile pour la fonction MISE A NIVEAU "
                          "(Upgrade). Le bloc parent n'en a pas besoin (il utilise "
                          "toujours la recette portant son propre nom). ATTENTION : ne "
                          "jamais faire un Ref vers un bloc qui EST lui-meme la cible de "
                          "TemplateRoot dans la meme entree -- ca fait planter la "
                          "bibliotheque de blueprints."),
        ("UpgradeTo", "Definit vers quel bloc/appareil ce bloc se transforme en cas de "
                       "mise a niveau. Si tu mets ca sur un sous-groupe, ce sous-groupe "
                       "a besoin de son propre TemplateRoot, sinon la mise a niveau sera "
                       "gratuite (bug). Peut valoir 'null' pour eviter une boucle."),
        ("DowngradeTo", "Meme principe que UpgradeTo, mais dans l'autre sens (retour "
                         "en arriere)."),
        ("Place: NoRotation", "Le bloc ne peut pas etre tourne a la pose."),
        ("Place: Face", "Le bloc s'oriente automatiquement selon la surface visee "
                         "(collé/oriente correctement), mais seule la rotation autour "
                         "d'un axe est possible."),
        ("Place: Free", "Pose libre, toutes rotations possibles, mais sans "
                         "l'alignement automatique (moins pratique, demande souvent "
                         "des rotations manuelles)."),
        ("RemoveOnSI", "Si actif (true), ce bloc disparait immediatement quand la "
                        "structure s'effondre (perte d'integrite)."),
        ("IsPhysicsColliders", "Active/desactive les collisions physiques fines "
                                "(desactive parfois sur les rampes trop fines)."),
        ("OccupySizeInBlocks", "Le bloc occupe tout son volume declare meme s'il n'est "
                                "pas 'voxelise' (utile pour des blocs avec animation ou "
                                "shader special)."),
        ("BlockSizeScale", "2 pour SV/HV, 8 pour CV/BA -- sert a mettre a l'echelle la "
                            "masse et les points de vie selon le nombre de voxels."),
        ("Voxelize", "Determine si le bloc est decoupe en petits cubes plutot que "
                      "d'occuper tout un voxel d'un coup (true par defaut)."),
        ("IsActivateable", "Le bloc peut etre allume/eteint par le joueur."),
        ("IsActivateableInCP", "Accessible via le Panneau de Controle (tourelle, "
                                "reservoir, coffre...)."),
        ("IsActivatedOnPlace", "Le bloc est deja allume des qu'il est pose."),
        ("IsDuplicateable", "Le bloc peut etre utilise avec les outils de dessin en "
                             "plan/ligne."),
        ("ForceMaxCount", "Force la limite MaxCount meme si le niveau de difficulte "
                           "l'avait desactivee (utile pour le Core, le Warp Drive... "
                           "mais pas pour les armes)."),
        ("IsAntiInfantryWeapon", "Les degats/PV de cet appareil ne comptent que face a "
                                  "l'infanterie et aux entites, pas face a l'artillerie."),
        ("IsKeepContainers", "Reserve aux Cores (PNJ uniquement) : le contenu preplace "
                              "est sauvegarde avec le blueprint et devient du butin."),
        ("VolumeCapacity", "Capacite du conteneur, en litres (SU)."),
        ("ShieldMultiplier", "Uniquement pour Class:ShieldGenerator -- un texte libre "
                              "utilisable dans le DamageMultiplier d'une arme "
                              "(ItemsConfig.ecf)."),
        ("RepairToTemplate", "Mettre a false pour exclure un bloc special/rare de la "
                              "reparation automatique via la recette (evite des abus)."),
        ("DropOnDeath", "Mettre a 'False' pour qu'un objet important d'histoire ne soit "
                         "jamais perdu a la mort du joueur (vrai par defaut)."),
        ("RepFac", "Multiplicateur de reputation gagnee/perdue en detruisant ce bloc "
                    "(ex: 0.1 pour reduire l'impact)."),
        ("DropMeshfile", "Modele 3D du sac/conteneur affiche au sol quand ce bloc est "
                          "lache (variantes: petit, grand, evenement...)."),
        ("DropInventoryEntity", "Quelle variante de conteneur apparait quand un "
                                 "conteneur de butin est detruit."),
        ("ShieldHitCooldown", "Delai en secondes avant que le bouclier ne recommence a "
                               "se recharger apres un coup (5s par defaut)."),
    ]),
    ("Dialogues (special)", [
        ("ExecuteOnActivate", "Declenche un etat de dialogue (Dialogues.ecf) quand le "
                               "joueur regarde le bloc et appuie sur F."),
        ("ExecuteOnCollide", "Meme chose, mais en touchant/poussant contre le bloc "
                              "plutot qu'en appuyant sur F."),
        ("DialogueSingleUserAccess", "Un seul joueur a la fois peut interagir avec ce "
                                      "dialogue."),
        ("DialogueState", "Force un dialogue precis ; permet aussi de placer ce bloc "
                           "sur une base appartenant a un joueur (declenchable via F)."),
        ("OmitCone", "Cache le cone jaune de dialogue au-dessus du PNJ (utile si le "
                      "PNJ ne fait qu'aboyer sans vraie interaction)."),
    ]),
    ("Competences (special)", [
        ("Player.Skills[...]", "Utilise dans Dialogues.ecf pour definir une entree de "
                                "competence. Les valeurs peuvent modifier : degats, "
                                "degats de zone, dispersion, delai de rechargement, "
                                "recul, portee..."),
        ("Mod.ReloadDelay exemple", "Exemple de syntaxe : "
                                     "Mod.ReloadDelay: \"ReloadDelay + Player.Skill['nom']\""),
    ]),
    ("Classes de conteneur", [
        ("Class: Container", "Cargo, coffre, frigo... necessite VolumeCapacity."),
        ("Class: ContainerPersonal", "Necessite VolumeCapacity."),
        ("Class: ContainerController", "Necessite VolumeCapacity."),
        ("Class: ContainerExtension", "Necessite VolumeCapacity."),
        ("Class: ArmorLocker", "Necessite VolumeCapacity."),
        ("Class: Constructor", "Tous les constructeurs, y compris le transformateur "
                                "alimentaire."),
        ("Class: WarpDriveTank", "Necessite VolumeCapacity."),
        ("Class: RepairStation", "Necessite VolumeCapacity."),
    ]),
    ("Types de symetrie (SymType)", [
        ("SymType 1", "Forme symetrique type quart de rond (par defaut)."),
        ("SymType 2", "Forme symetrique type coin."),
        ("SymType 3", "Forme symetrique type mur incline."),
        ("SymType 4", "Forme type coin biseau, mais avec une rotation par defaut "
                       "incorrecte (orthogonale a l'axe Z)."),
        ("MirrorTo", "Bloc utilise quand celui-ci est mis en miroir."),
    ]),
    ("Modes de shader", [
        ("Device", "Coloration classique (constructeurs, etc.)."),
        ("NoSI", "Objets de decor sans integrite structurelle (meme rendu que Device "
                  "mais sans SI)."),
        ("NPC", "Coloration par materiau, pour les PNJ."),
        ("Cutout", "Comme Device, avec transparence par decoupe."),
        ("DeviceEmissiveOn", "Comme Device, mais avec un effet lumineux constant "
                              "(ex: panneaux solaires)."),
        ("DeviceNewColoring", "Nouvelle methode de coloration pour les blocs Device."),
        ("NoSINewColoring", "Nouvelle methode de coloration pour les objets de decor."),
    ]),
    ("Proprietes exportees", [
        ("IsAccessible", "Apparait dans le Panneau de Controle."),
        ("O2Accept", "Liste des objets utilisables pour remplir une bouteille "
                      "d'oxygene (le premier de la liste est utilise en priorite)."),
        ("FuelAccept", "Liste des objets utilisables comme carburant (le premier de la "
                        "liste est utilise en priorite)."),
    ]),
]

# ============================================================================
# GalaxyConfig.ecf -- generation de la galaxie (etoiles, regions, territoires)
# ============================================================================
GALAXY_CONFIG_GLOSSARY = [
    ("Limites de nombre", [
        ("Regions", "De StarRegion_1 a StarRegion_99 maximum."),
        ("Territoires", "De Territory_1 a Territory_20 maximum, chacun pouvant avoir "
                         "1 a 10 factions 'Other_' additionnelles (Other_1 a Other_10)."),
        ("Types d'etoiles (suntypes)", "Illimites."),
    ]),
    ("Systemes a deux etoiles", [
        ("CompanionStarClass", "Ajoute une 2e etoile decorative (pas de gameplay) a une "
                                "StarClass -- la valeur doit etre une StarClass deja "
                                "definie dans ce fichier."),
    ]),
    ("Configuration avancee", [
        ("SolarSystemConfigSuffix", "Force l'utilisation d'un fichier "
                                     "SolarSystemConfig<suffixe>.yaml particulier au "
                                     "lieu de celui du type d'etoile par defaut."),
        ("Modeles d'etoile disponibles", "SunBlueGiant, SunWhiteDwarf, SunYellowWhite, "
                                          "SunYellow, SunRedGiant, SunRedDwarf, "
                                          "SunNeutron, BlackHole, SunGeneric. Seul le "
                                          "modele visuel est limite a cette liste -- "
                                          "tous les autres parametres (StarClass, "
                                          "couleur...) restent personnalisables."),
        ("Systeme de depart", "Si le scenario n'utilise pas de sectors.yaml fixe avec "
                               "planetes de depart, un systeme de depart peut etre "
                               "defini dans les reglages generaux. Un sectors.yaml "
                               "avec planetes de depart est prioritaire sur cette "
                               "entree si les deux existent."),
    ]),
    ("Unites de mesure internes", [
        ("1 annee-lumiere (LJ)", "= 10 000 UA = 100 000 secteurs (valeur simplifiee "
                                  "pour la lisibilite, pas la vraie mesure "
                                  "astronomique)."),
        ("1 UA", "= 10 secteurs."),
        ("Coordonnees en annees-lumiere", "Territoires, position d'une etoile "
                                           "(sectors.yaml), rayon de spawn galactique, "
                                           "rayon de la galaxie."),
        ("Coordonnees en secteurs", "Zones autour d'une etoile (ex: HabitableCold), "
                                     "position d'une planete/lune/station dans "
                                     "sectors.yaml ou SolarSystemConfig -- PAS en UA."),
    ]),
    ("Territoires", [
        ("Factions disponibles", "Zirax, Talon, Polaris, Kriel, Pirates, Trader, UCH, "
                                  "Civilian, Alien."),
        ("Chevauchement", "Plusieurs territoires peuvent exister pour la meme faction, "
                           "meme avec des coordonnees/spheres qui se chevauchent."),
        ("Faction du territoire", "Seuls ses propres POI sont places dans le "
                                   "territoire par defaut ; pour en autoriser d'autres, "
                                   "utiliser 'Other_' avec un numero, en definissant la "
                                   "probabilite du centre vers le bord."),
    ]),
    ("Etiquettes sur la carte (StarRegion)", [
        ("LabelName", "Texte de l'etiquette a cette position."),
        ("LabelColor", "Couleur, ex: \"0,1,0.67\" ou avec transparence "
                        "\"1.0,0.0,0.0,0.2\"."),
        ("LabelSize", "Taille de l'etiquette."),
        ("LabelLYDistance", "Distance (en annees-lumiere) au-dela de laquelle "
                             "l'etiquette se cache."),
    ]),
    ("Nebuleuses", [
        ("NebulaSpawnCount", "Si defini dans une StarRegion, desactive les nebuleuses "
                              "aleatoires -- seules celles de regions utilisant cette "
                              "propriete apparaissent."),
        ("NebulaColorIndex", "Choisit la couleur de la nebuleuse dans le degrade "
                              "NebulaColor correspondant (jusqu'a 30 degrades "
                              "possibles)."),
    ]),
    ("Voir les changements sans relancer", [
        ("Astuce", "Charge une partie sauvegardee, edite son Galaxyconfig.ecf dans le "
                    "dossier de la sauvegarde, puis recharge avec la commande console "
                    "'galaxy'."),
    ]),
    ("Cacher un systeme solaire", [
        ("HideFromMap", "Masque le systeme de la carte galactique."),
        ("HideFromSearch", "Le systeme reste visible sur la carte mais n'apparait plus "
                            "dans la recherche."),
    ]),
    ("Reglages d'une etoile (exemple complet)", [
        ("Name", "Nom de l'etoile -- personnalisable, ou generique "
                  "'<StarClass> Type Star'."),
        ("StarClass", "Classe de l'etoile, 3-4 lettres/chiffres."),
        ("Model", "Modele visuel (par defaut SunGeneric)."),
        ("Probability", "0 a 1 -- probabilite globale que cette classe existe dans la "
                         "galaxie (ne jamais mettre 0)."),
        ("SizeClass", "1 a 12 -- taille de l'etoile et de son icone, influence la "
                       "distance des secteurs de warp pour les grosses etoiles."),
        ("Color / LightColor / ModelColor / ModelColor2", "Couleurs de l'etoile "
                          "(carte, apparence en jeu, couleur interne, couronne)."),
        ("ModelBrightness", "0.1 a 1.5 -- luminosite globale de la couronne "
                             "(SunGeneric uniquement)."),
        ("SurfaceTemperature / Mass / Radius / Luminosity / Age", "Purement "
                          "informatif, aucun effet sur le jeu."),
        ("InnerSystem / HabitableHot / HabitableTemperate / HabitableCold / OuterSystem",
         "Plages de distance (en UA) definissant chaque zone du systeme -- utilisees "
         "ensuite dans sectors.yaml pour placer les planetes."),
        ("GalaxySpawnRadius", "Distance min/max (en annees-lumiere) du centre pour que "
                               "cette etoile apparaisse."),
        ("GalaxySpawnAmount", "Nombre d'etoiles de ce type placees dans la galaxie -- "
                               "mettre 0 seulement si gere via les REGIONS."),
        ("ClusterProb / ClusterRange", "Probabilite (0-1) et position (0=bord, "
                                        "1=centre) de regroupement en amas."),
        ("Description", "Courte description scientifique/narrative pour la carte."),
    ]),
]

# ============================================================================
# ItemsConfig.ecf -- items, armes, armures (tres proche de BlocksConfig.ecf)
# ============================================================================
ITEMS_CONFIG_GLOSSARY = [
    ("Proprietes generales", [
        ("CustomIcon", "Reutilise une icone deja existante pour l'affichage en jeu."),
        ("AllowAt", "Restreint l'usage, ex: 'AllowAt: NoPvP' et 'AllowAt: NoPvE' pour "
                     "interdire un objet selon le mode de jeu."),
        ("MarketPrice", "Prix par unite pour les POI 'StationInterface'. Si plusieurs "
                         "objets remplissent le meme role (ex: 3 types de piles pour "
                         "le carburant), celui au cout le plus bas est utilise "
                         "automatiquement."),
        ("LifetimeOnDrop", "Duree en secondes avant qu'un objet lache au sol "
                            "disparaisse (200s par defaut). N'augmenter qu'en cas de "
                            "necessite absolue -- trop d'objets au sol degrade les "
                            "performances."),
        ("DropOnDeath", "Mettre a 'False' pour qu'un objet important d'histoire ne "
                         "soit jamais perdu a la mort du joueur (vrai par defaut)."),
    ]),
    ("Effets (Buffs/Debuffs)", [
        ("BuffMod", "Syntaxe: \"StatusID, FacteurDuree, FacteurIntensite, "
                     "AnnulerAExpiration(optionnel)\". Le facteur duree/intensite "
                     "modifie le temps/la force de l'effet (0 = pas de changement)."),
        ("Annuler a expiration", "Booleen qui empeche les effets de fin de statut si "
                                  "vrai -- ex: un medicament qui empeche une blessure "
                                  "infectee d'evoluer en septicemie."),
    ]),
    ("Armures et boosters", [
        ("SlotItems", "15 entrees maximum par armure. Attention : modifier cette "
                       "liste change les boosters deja actifs dans les parties "
                       "existantes (stockes par simple INDEX dans cette liste)."),
        ("Armor", "Points de vie supplementaires."),
        ("Oxygen", "Volume d'oxygene supplementaire."),
        ("Radiation / Heat / Cold", "Protection jusqu'a cette valeur."),
        ("PowerFac / SpeedFac / StaminaFac / JetpackFac / JumpFac / FoodFac",
         "Multiplicateurs pour l'energie, la vitesse, l'endurance, le jetpack, le "
         "saut, la consommation alimentaire."),
    ]),
    ("Types d'armes et degats", [
        ("Class: Ranged", "Les degats sont definis sur l'arme elle-meme ; le type de "
                           "munition ne porte que des stats (masse, volume, cout...)."),
        ("Class: LauncherSS", "Degats ET degats de zone (optionnel) definis sur le "
                               "type de munition (sous-entree 'Class: Projectile')."),
        ("Degats de zone (Blast)", "S'AJOUTENT aux degats de base pour le bloc central "
                                    "touche. Formule approximative : "
                                    "(Degats + DegatsZone) - (DegatsZone / RayonZone)."),
        ("Materiaux disponibles pour multiplicateurs", "head, body, dirt, stone, rock, "
                          "metallight, metal, metalhard, woodsoft, wood, woodhard, "
                          "concrete, hull, hullarmored, hullcombat, shield."),
        ("ShieldDamagePenFac / BlastShieldDamagePenFac", "Pourcentage (0.0-1.0) de "
                          "degats normaux/de zone qui traverse le bouclier."),
        ("BlastRadius / BlastDamage / BlastParticleIndex", "Rayon et intensite des "
                          "degats de zone, et quel effet visuel utiliser (1-16)."),
        ("Boucliers : cas particulier", "Les degats de zone ne s'appliquent JAMAIS a "
                          "un bouclier -- seuls les degats de base comptent."),
        ("ShieldMultiplier", "Sur un Class:ShieldGenerator (BlocksConfig.ecf), valeur "
                              "libre reutilisable dans un DamageMultiplier pour cibler "
                              "specifiquement ce type de bouclier."),
    ]),
    ("Categories", [
        ("Ingredients", "Matiere brute sans recette (ramassee dans le monde)."),
        ("Components", "Materiau transforme, avec une recette (Templates.ecf)."),
    ]),
    ("Types de prise en main (HoldType)", [
        ("0", "Non specifie."),
        ("14", "Pistolet."),
        ("15", "Fusil."),
        ("16", "Fusil avec animation de tir plus faible (outil de survie, "
                "multi-outil, foreuse)."),
        ("17", "Arc."),
        ("20", "Corps a corps."),
    ]),
    ("Divers", [
        ("AllowRemote", "Autorise/interdit l'usage en drone joueur (vrai par defaut)."),
        ("AmmoCapacity", "Maximum 500 pour toutes les tourelles/armes montees."),
        ("Durability", "Maximum 5000 pour les armes/outils portes a la main."),
        ("AutoReload", "Rechargement automatique (vrai par defaut)."),
    ]),
]

# ============================================================================
# GlobalDefsConfig.ecf -- macros/valeurs reutilisables entre fichiers ECF
# ============================================================================
GLOBALDEFS_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Definir des valeurs communes (ex: degats d'une arme, points de "
                      "vie d'un drone) UNE SEULE FOIS ici, puis les reutiliser dans "
                      "n'importe quel autre fichier ECF -- modifier la valeur ici "
                      "suffit a la changer partout."),
        ("Utilisation", "Dans un autre fichier (ex: ItemsConfig.ecf), utiliser "
                         "'GlobalRef: NomDeLaDef' pour reference cette valeur."),
        ("Plusieurs References", "Un meme bloc peut utiliser plusieurs GlobalDef via "
                                  "GlobalRef_1 jusqu'a GlobalRef_5."),
    ]),
]

# ============================================================================
# LootGroups.ecf -- tables de butin (format de ligne)
# ============================================================================
LOOT_GROUPS_GLOSSARY = [
    ("Format d'une ligne", [
        ("Syntaxe", "Item_x: nom, data: quantite[-plage], xdata: probabilite "
                     "(x s'incremente pour chaque ligne ; utiliser des guillemets si "
                     "la quantite est une plage)."),
    ]),
]

# ============================================================================
# MaterialConfig.ecf -- proprietes physiques des materiaux
# ============================================================================
MATERIAL_CONFIG_GLOSSARY = [
    ("Notes generales", [
        ("hullarmored / hullcombat", "Ne peuvent pas etre detruits par la plupart des "
                                      "armes portees a la main."),
        ("Integrite structurelle (SI)", "Longueur maximale actuelle d'une poutre "
                                         "horizontale = 12 blocs."),
        ("stability_glue / mass", "Determine le nombre maximum de blocs alignes qui "
                                   "ne se detacheront pas a cause de la perte "
                                   "d'integrite structurelle."),
    ]),
]

# ============================================================================
# StatusEffects.ecf -- effets de statut (blessures, maladies...)
# ============================================================================
STATUS_EFFECTS_GLOSSARY = [
    ("Notes generales", [
        ("Blessures basiques", "Regroupent tout ce qu'un ennemi inflige couramment."),
        ("Exemple : saignement standard", "Guerit seul sans traitement, en 240 points "
                                           "de vie de duree."),
    ]),
]

# ============================================================================
# Templates.ecf -- recettes de craft
# ============================================================================
TEMPLATES_GLOSSARY = [
    ("Abreviations de constructeur et facteur de temps", [
        ("SuitC", "Constructeur de Survie -- facteur 1.8 (le plus lent)."),
        ("SurvC", "Constructeur Portable -- facteur 1.6."),
        ("SmallC", "Constructeur SV -- facteur 1.4."),
        ("HoverC", "Constructeur HV -- facteur 1.4."),
        ("BaseC", "Constructeur T0 -- facteur 1.2."),
        ("LargeC", "Constructeur T1V2 -- facteur 1 (reference)."),
        ("AdvC", "Constructeur T2 -- facteur 0.5 (le plus rapide)."),
        ("FoodP", "Transformateur Alimentaire V2 -- facteur 1."),
        ("Furn", "Fournaise -- facteur 0.2."),
        ("(sans balise)", "Deconstructeur -- facteur 0.5."),
    ]),
    ("Astuces de recette", [
        ("Objet gratuit", "Mettre TOUTES les lignes de Child Inputs a 0 -- ne JAMAIS "
                           "supprimer la section entierement."),
        ("BaseItem: true", "Definit le niveau de base pour l'usine a blueprints, et "
                            "sert de reference pour la reparation R2T."),
        ("Deconstructeur", "Decompose un objet jusqu'a n'obtenir que des ingredients "
                            "marques BaseItem. Ex: le minerai de fer (BaseItem) ne "
                            "sera jamais recree a partir du lingot de fer."),
        ("DeconOverride: Continue", "Autorise le deconstructeur a decomposer l'objet "
                                     "une etape supplementaire."),
        ("DeconOverride: Stop", "Empeche toute deconstruction de cet objet."),
        ("Limitation T1 vers T2", "Utiliser un appareil T1 comme ingredient d'un "
                                   "appareil T2 ne fonctionne que pour les appareils "
                                   "uniques (ex: Constructeur), pas pour les groupes "
                                   "de blocs (ex: Cockpits) -- ne pas utiliser le T1 "
                                   "en ingredient dans ce cas."),
    ]),
]

# ============================================================================
# TokenConfig.ecf -- jetons (cles, quetes, PDA...)
# ============================================================================
TOKEN_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Definition", "Un jeton (Token) est une instance de l'item 'GenericToken' qui "
                        "prend son sens en jeu -- ex: le code d'une porte verrouillee, "
                        "ou une quete/mission PDA necessitant ce jeton pour se "
                        "terminer."),
        ("RemoveOnUse", "A true, retire le jeton de l'inventaire du joueur des qu'il "
                         "est utilise."),
        ("Facultatif", "Pas besoin de definir chaque jeton ici, mais si defini, son "
                        "nom et sa description s'afficheront correctement."),
    ]),
    ("Cas d'usage", [
        ("1. Placer un jeton dans un conteneur", "Console: 'give item Token 0001', "
                          "puis le placer dans un conteneur et sauvegarder le POI "
                          "(fonctionne seulement avec un core admin actuellement)."),
        ("2. Donner via PDA", "Utiliser 'Token:0001' comme recompense ou operation "
                               "d'inventaire dans une mission PDA."),
        ("3. Donner via dialogue", "Fonction AddItem, ex: "
                                    "AddItem('KeyCardBlack', 3, 1234) donne 3 cartes "
                                    "avec le Meta 1234."),
        ("4. Vente par un marchand", "Ajouter l'item au TraderNPCConfig.ecf en "
                                      "utilisant 'Token:0001' comme nom d'item."),
        ("5. Dans une table de butin", "Meme principe, utiliser 'Token:0001' dans le "
                                        "LootGroups.ecf."),
    ]),
    ("Important", [
        ("Item 'Token' (Id 1305)", "Seul cet item precis peut recevoir un Meta a 4 "
                                    "chiffres. Aucun autre objet 'carte-cle' ou "
                                    "similaire ne peut avoir de Meta attache."),
        ("Rechargement a chaud", "La commande console 'token reload' applique les "
                                  "changements de ce fichier sans relancer le jeu."),
    ]),
]

# ============================================================================
# TraderNPCConfig.ecf -- configuration des marchands
# ============================================================================
TRADER_NPC_CONFIG_GLOSSARY = [
    ("Format d'un item", [
        ("Syntaxe generale", "Nom de l'item, plage de prix de vente, plage de stock "
                              "disponible[, plage de prix d'achat, plage de stock "
                              "maximum]."),
        ("Section achat optionnelle", "Si omise, le marchand n'achete pas cet item."),
        ("Calcul du prix", "Si le marchand achete l'item (stock max defini), le prix "
                            "de reference correspond a un stock actuel egal a la "
                            "moitie du stock max. Plus de stock = prix qui baisse, "
                            "moins de stock = prix qui monte."),
        ("Vente seule", "Si le marchand ne fait que vendre l'item, le prix ne depend "
                         "pas du stock."),
        ("Chevauchement autorise", "Le prix d'achat peut chevaucher le prix de vente "
                                    "-- le jeu garantit quand meme une marge d'au "
                                    "moins 5% pour le marchand."),
        ("Facteur de marche (mf=)", "Permet d'appliquer un facteur au prix de marche "
                                     "de base."),
        ("Exemple", "Item1: \"AutoMinerCore, mf=2.5-3.2, 10-50, mf=1.2-2.3, 55-150\""),
    ]),
    ("Attention", [
        ("Marchand par defaut", "Ne pas changer le nom du marchand fourni par "
                                 "defaut."),
    ]),
]

# ============================================================================
# BlockGroupsConfig.ecf -- groupes de blocs avec limite commune (ex: tourelles)
# ============================================================================
BLOCK_GROUPS_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Definir un groupe de blocs personnalise partageant une limite "
                      "commune -- utile pour equilibrer, par exemple, le nombre total "
                      "de tourelles."),
        ("Limite individuelle conservee", "Les blocs du groupe respectent a la fois "
                                           "la limite du groupe ET leur propre limite "
                                           "individuelle (definie dans "
                                           "BlocksConfig.ecf)."),
        ("Fonctionne uniquement", "Sur les blocs ayant un index (un Id numerique)."),
        ("Informer le joueur", "Ajouter une ligne correspondante dans "
                                "Localization.csv (ex: 'SVWeapons,Total SV Weapons "
                                "{0},...') pour afficher la limite dans l'interface -- "
                                "rien d'autre a ajouter dans BlocksConfig.ecf."),
    ]),
    ("Exemple", [
        ("BlockGroup Name / MaxCount / Blocks", "Nom du groupe, limite totale, et "
                                                  "liste des blocs concernes separes "
                                                  "par des virgules."),
    ]),
]

# ============================================================================
# Containers.ecf -- tables de butin des conteneurs
# ============================================================================
CONTAINERS_GLOSSARY = [
    ("Format d'une ligne", [
        ("Syntaxe", "\"Groupe|Nom_x\" (x s'incremente), data: \"probabilite\" "
                     "[, xdata=\"plage de quantite\"] (par defaut 1,1)."),
        ("Colonnes", "Toujours utiliser 8 colonnes actuellement (premier nombre de la "
                      "ligne 'Size')."),
        ("Total disponible", "1023 Id au maximum."),
    ]),
    ("Jetons dans une table de butin", [
        ("Syntaxe", "Name_0: Token, param1: 1, param2: \"meta=9992\" -- le meta "
                     "provient de TokenConfig.ecf."),
    ]),
    ("Tables pour spawners de PNJ", [
        ("Usage", "Entrer le numero d'Id du conteneur (ex: 255) dans le menu "
                   "deroulant a cote du spawn-entity."),
    ]),
    ("Cultures cultivables (jardiniere joueur)", [
        ("Fruit", "AlienPalmTreeStage1, PearthingStage1"),
        ("Legumes", "AlienPlantTube2Stage1, BulbShroomYoungStage1, DurianRoot, "
                     "PumpkinStage1, TomatoStage1"),
        ("Edulcorant naturel", "AlienplantWormStage1"),
        ("Bourgeons", "BigFlowerStage1"),
        ("Epice", "CobraLeavesPlantStage1"),
        ("Stimulant naturel", "CoffeePlantStage1"),
        ("Cereales", "CornStage1, WheatStage1"),
        ("Minerai de Pentaxid", "CrystalsPyramidBlueStage1, "
                                 "CrystalsPyramidOrangeStage1, CrystalStraightStage1"),
        ("Feuilles medicinales", "DesertPlant20Stage1"),
        ("Baies", "ElderberryStage1"),
        ("Champignon brun", "MushroomBellBrown01Stage1"),
        ("Fibre", "SnakeweedStage1"),
    ]),
]

# ============================================================================
# DamageMultiplierConfig.ecf -- multiplicateurs de degats par materiau
# ============================================================================
DAMAGE_MULTIPLIER_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Definir des groupes de multiplicateurs de degats reutilisables "
                      "depuis ItemsConfig.ecf via 'DamageMultiplier_Group: NomDuGroupe'."),
        ("Une seule methode a la fois", "Dans ItemsConfig.ecf, utiliser soit "
                                         "DamageMultiplier_x SOIT "
                                         "DamageMultiplier_Group, pas les deux."),
        ("Groupe de groupes", "Un 'Collection' permet de combiner plusieurs groupes -- "
                               "mais un groupe de groupes ne peut pas en referencer un "
                               "autre."),
    ]),
    ("Exemple : Pistol", [
        ("DamageMultiplier_1: 5, param1: head", "x5 de degats sur la tete."),
        ("DamageMultiplier_2: 0, param1: dirt|stone|...", "Aucun degat sur ces "
                                                            "materiaux de terrain/mur."),
        ("DamageMultiplier_3: 0, param1: shield", "Aucun degat sur les boucliers."),
    ]),
]

# ============================================================================
# DefReputation.ecf -- reputation par defaut envers les factions
# ============================================================================
DEF_REPUTATION_GLOSSARY = [
    ("Principe", [
        ("Objectif", "Permet de remplacer la reputation par defaut de toutes les "
                      "factions d'origine (Origin) envers les factions PNJ."),
    ]),
]

# ============================================================================
# EGroupsConfig.ecf -- groupes d'entites (spawns de creatures/PNJ)
# ============================================================================
EGROUPS_CONFIG_GLOSSARY = [
    ("Principe", [
        ("Factions", "Les factions des creatures sont definies dans EClassConfig.ecf, "
                      "pas ici."),
        ("Groupes de bataille (Battle Groups)", "Apparaissent ensemble et "
                          "interagissent comme une equipe (IA comportementale)."),
    ]),
]

# ============================================================================
# Factions.ecf -- definition des factions
# ============================================================================
FACTIONS_GLOSSARY = [
    ("Valeurs obligatoires", [
        ("Id", "Doit etre unique, utilise dans les sauvegardes -- le changer casse "
                "les parties existantes. Doit etre < 100, sinon une faction JOUEUR "
                "est creee a la place. Des trous dans la numerotation sont "
                "autorises."),
        ("FactionName", "Sans espaces ni caracteres speciaux -- utilisable dans la "
                         "localisation. Sert de reference pour les playfields, POI, "
                         "etc."),
        ("Abbrev", "3 lettres maximum, eviter les caracteres speciaux."),
        ("Color", "\"R,G,B\" -- diviser la valeur RGB par 255 pour obtenir le "
                   "flottant attendu."),
        ("Description", "Affichee en haut de la liste pour les factions PNJ."),
    ]),
    ("Factions statiques", [
        ("Definition", "Factions comme Legacy ou Alien -- impossible d'ameliorer sa "
                        "reputation avec elles."),
        ("Friendly: true", "Toujours amicale -- DefReputation.ecf ignore, ne pas "
                            "combiner avec 'Reputation: true'."),
        ("Unfriendly: true", "Toujours hostile -- meme regle."),
        ("Ni l'un ni l'autre", "La faction est neutre par defaut."),
    ]),
    ("Factions dynamiques", [
        ("Definition", "Factions comme les Zirax -- reputation, territoire propre, "
                        "amelioration/degradation possible."),
        ("Reputation: true", "Active la matrice de reputation de DefReputation.ecf. "
                              "Sans ca, la faction est hostile statique (sauf si "
                              "FriendlyToPlayers est actif)."),
        ("ClaimTerritory: true", "La faction peut avoir un territoire visuel sur les "
                                  "planetes (sans lien avec les territoires "
                                  "galactiques, geres dans galaxy.ecf)."),
    ]),
    ("Autres reglages", [
        ("OmitMapLegend", "Cache la faction de la legende des cartes."),
        ("HideAbbrev", "Cache l'abreviation de la faction dans l'interface (HUD)."),
        ("Discovery", "La faction devient decouvrable des qu'un de ses POI est "
                       "decouvert. Debug via la commande console "
                       "'faction discover <faction>'."),
        ("AttackNPC", "Cette faction attaque les autres factions PNJ ayant aussi "
                       "cette option active."),
        ("ForceAttack", "Liste de factions specifiquement attaquees (peut etre "
                         "asymetrique) -- ecrase le comportement d'AttackNPC."),
    ]),
    ("A savoir", [
        ("Ne pas melanger", "Une faction est soit statique, soit dynamique -- jamais "
                             "les deux."),
        ("Factions protegees", "Zirax, Talon, Alien, Polaris, Prey, Predator et Admin "
                                "sont geres en interne (references/valeurs par "
                                "defaut) et ne sont pas personnalisables."),
    ]),
    ("Guerre des factions (resume)", [
        ("Civilisation galactique (alliee)", "Zirax, Polaris, Trader, Colonists, "
                                              "Eden_Defender."),
        ("Ennemis de tous", "Warlord, Alien, TheLegacy, Kriel, Eden_Drone, "
                             "Eden_DroneHome, Pirates."),
        ("Ressources minables", "Eden_Resource, Prey."),
        ("Factions codees en dur", "Ne jamais les modifier (sauf la couleur) -- "
                                    "doivent etre definies avant toute autre "
                                    "faction dans le fichier."),
    ]),
]

# ============================================================================
# FactionWarfare.ecf -- attaques de base, defense spatiale
# ============================================================================
FACTION_WARFARE_GLOSSARY = [
    ("Defense de base spatiale (SBD)", [
        ("Portee", "Globale pour toute une faction sur un POI donne -- impossible de "
                    "configurer un vaisseau specifique pour un POI precis via SBD."),
        ("Exclure un POI de la SBD", "Dans le playfield yaml, utiliser "
                          "SpaceDefenseOverrideDefaults: True avec "
                          "SpaceDefenseProbability: 1.0 et "
                          "SpaceDefensePriceMinMax: [30, 60] -- ou fixer une "
                          "probabilite precise (0-1) autrement geree par l'IA."),
    ]),
    ("Attaque de base Zirax (Survie)", [
        ("FactionSettings", "Convertit un numero de niveau en prix de vague "
                             "d'attaque."),
        ("Unit", "Definit une unite individuelle utilisable dans un scenario "
                  "d'attaque, rangee dans une categorie (ex: plusieurs forces de "
                  "drone minigun selon la difficulte)."),
        ("Scenario", "Definit la composition complete d'une attaque -- utilisable "
                      "automatiquement par le systeme d'attaque de base, ou "
                      "manuellement via une mission PDA."),
    ]),
]

GLOSSARY_BY_FILE = {
    "BlocksConfig.ecf": BLOCKS_CONFIG_GLOSSARY,
    "GalaxyConfig.ecf": GALAXY_CONFIG_GLOSSARY,
    "ItemsConfig.ecf": ITEMS_CONFIG_GLOSSARY,
    "GlobalDefsConfig.ecf": GLOBALDEFS_CONFIG_GLOSSARY,
    "LootGroups.ecf": LOOT_GROUPS_GLOSSARY,
    "MaterialConfig.ecf": MATERIAL_CONFIG_GLOSSARY,
    "StatusEffects.ecf": STATUS_EFFECTS_GLOSSARY,
    "Templates.ecf": TEMPLATES_GLOSSARY,
    "TokenConfig.ecf": TOKEN_CONFIG_GLOSSARY,
    "TraderNPCConfig.ecf": TRADER_NPC_CONFIG_GLOSSARY,
    "BlockGroupsConfig.ecf": BLOCK_GROUPS_CONFIG_GLOSSARY,
    "Containers.ecf": CONTAINERS_GLOSSARY,
    "DamageMultiplierConfig.ecf": DAMAGE_MULTIPLIER_CONFIG_GLOSSARY,
    "DefReputation.ecf": DEF_REPUTATION_GLOSSARY,
    "EGroupsConfig.ecf": EGROUPS_CONFIG_GLOSSARY,
    "Factions.ecf": FACTIONS_GLOSSARY,
    "FactionWarfare.ecf": FACTION_WARFARE_GLOSSARY,
}
