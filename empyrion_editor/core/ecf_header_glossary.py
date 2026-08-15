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
