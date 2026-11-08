# GLOSSAIRE DES PROPRIÉTÉS — Scénario RE2-FR (Empyrion Galactic Survival)

Base de connaissance pour les infobulles, aides contextuelles et
explications des modules de l'éditeur. Chaque propriété présente dans les
fichiers du scénario RE2-FR y est répertoriée avec son sens.

## Sources et fiabilité

| Étiquette | Signification |
|---|---|
| **[M]** | Vérifié dans le MOTEUR décompilé/déobfusqué (`C:\Dev\empyrion_game_re`, Assembly-CSharp client+serveur) — classe typée, défaut `[DefaultValue]` ou doc `[PackageHelper]` d'Eleon |
| **[E]** | Vérifié dans EPD décompilé (`C:\Dev\rea-epd`, outil Empyrion Playfield Designer) ou observé dans les données du scénario |
| **[S]** | Déduit du scénario RE2-FR lui-même (valeurs observées, contexte d'usage) |

- Données extraites des **604 YAML** (playfields, sectors, PDA, gameoptions)
  et des **259 ECF** (19 configs + terrain.ecf) de RE2-FR : 1067 chemins
  YAML distincts, 1668 noms de propriétés ECF distinctes, 230 232 lignes
  de propriétés. Extraction : `_glossaire_work/extract_yaml.py`,
  `extract_ecf.py` (TSV de référence à côté des scripts).
- Format EPB : enum moteur `BlueprintHeader.EnumProperties` (26 clés, lire
  aussi `core/epb_blueprint.py`).
- Conventions : `[min, max]` = borne incluses ; `True/False` ;
  couleurs = chaîne `"r, g, b"` 0..1 (alpha optionnel) ; les listes YAML
  s'écrivent `[ a, b ]` ou bloc indenté. L'orthographe moteur
  **« Multiplyer »** (pour Multiplier) est d'origine : NE PAS corriger.
- Les clés non reconnues par le moteur sont ignorées silencieusement :
  une faute de frappe ne casse jamais un playfield, mais ne fait rien.

---

# 1. playfield_static.yaml / playfield.yaml (planètes, lunes, orbites)

Structure typée par le moteur dans `PlayfieldYamlData` (+ classes imbriquées
`InstanceData`, `LocalEffectData`, `GlobalEffectData`, `RandomResourceData`,
`FixedResourceData`, `AsteroidResourceData`, `ResourceDistType*`, `PresetData`,
`PoiData.*`, `DroneBaseSetupData.*`, `DroneSpawnData`, `CreatureSpawnData`,
`SpawnZoneData`, `SpawnRateZoneData`, `TerrainBiomeData`, `DCClusterData`,
`SpecialBiome`, `PoiData.PlayerStartData`). Les noms de clés YAML = noms des
propriétés C# (liaison par réflexion).

## 1.1 Général / identité

| Propriété | Type/défaut moteur | Sens |
|---|---|---|
| Description | string | Texte affiché sur la carte de la galaxie (balises de couleur `[c][ffffff]...[-][/c]` acceptées). |
| PlanetType | string | Type visuel/thématique du playfield (ex. Arid, Barren, Lava) ; détermine l'apparence de la planète en vue orbite. |
| PlayfieldType | enum (Planet, Moon, Sun, Space) | Nature du playfield : planète, lune, étoile ou espace orbital. |
| PlanetClass | string (déf. = PlanetType) | Classe utilisée par la génération dynamique pour choisir le gabarit. |
| Difficulty | int (déf. 1) | Niveau de difficulté affiché et utilisé par certains calculs (recommandé joueur). |
| LandClaimZone | enum Default/Off/Device (déf. Default) | Gestion des zones de revendication : Default (distance AntiGrief), Off (pas de protection), Device (protection uniquement autour d'un Land Claim Device). |
| Gravity | float (déf. selon type) | Gravité en m/s² (planètes ~8, lune ~2, orbite 0). |
| PlanetAxis | float[] | Axe de rotation de la planète (incline le jour/nuit). |
| PlanetRotAxis | float[] | Vecteur d'axe de rotation (précession du globe en vue orbite). |
| RealRadius | float | Rayon « réel » du corps pour l'échelle de la carte. |
| ScaledRadius | float | Rayon affiché (mis à l'échelle) sur la carte. |
| PlanetSize | int 2..5 (déf. 2) | Classe de taille : 2=Small, 3=Medium, 4=Large, 5=VeryLarge (enum PlanetSizeClass). |
| Moons | int | Nombre de lunes (purement informatif ici : les lunes réelles viennent de Sectors.yaml). |
| Emissive | bool | Le corps émet sa propre lumière (étoiles, nébuleuses). |
| PvP | bool | Playfield PvP (ou `ForcePvP` global dans gameoptions). |
| PvEStat | (non typé moteur) | Variante RE2 d'annotation PvP/PvE. |
| Seed | int (déf. -1 = aléatoire) | Graine du terrain : valeur fixe = terrain identique à chaque génération. |
| DayLength | int | Durée du cycle jour/nuit en minutes de jeu. |
| ChunkProviderId | int | Id du fournisseur de chunks (terrain précalculé d'un playfield vanilla). |
| WorldName | string | Nom interne du monde (espaces dynamiques). |
| Build | int | Numéro de build du générateur de playfield qui a écrit le fichier. |
| Music | string / string[] | Musique d'ambiance (ex. EmpyrionAmbient01) — liste acceptée en dynamique. |
| Skybox | string[] (espace) | Chemin de la skybox d'orbite. |
| Stars | string | Asset de champ d'étoiles (espace). |
| Nebula | string | Asset de nébuleuse (espace). |
| IsOrbitPlayfield | bool | Marque le playfield comme orbite (comportements espace). |
| LandClaimZone (voir plus haut) | | |
| RestrictToOrigin | byte (déf. 255) | Restriction par Origin (255 = toutes). |
| TraderZone | string | Marque la zone comme station de commerce. |
| PfServerWeight | int | Poids serveur (choix du playfield par le dédié). |
| PlayfieldLevel | int / PlayfieldLevelOverride int[] | Niveau du playfield (modifie la puissance des POI/armes ; Override = [min,max] en dynamique). |
| IndestructibleTerrain | bool | Terrain indestructible. |
| BaseAttackCount | int (déf. 1) | Nombre de vagues lors d'une attaque de base de drones. |
| AllowSavingBlueprints | bool (déf. True) | Autorise la sauvegarde de blueprints dans ce playfield. |
| PdaReferral | string[] | Renommage/redirection de références PDA (chapitres) pour ce playfield. |
| UseFixed | bool | Playfield entièrement fixe (pas de génération aléatoire). |
| UseRandom | bool (déf. = !UseFixed) | Complément de UseFixed : génération aléatoire. |
| LegacyBiome | OBSOLÈTE | Ancienne clé de biome (ignorée par le moteur). |
| RandomPOIs | OBSOLÈTE | Ancien format de POIs (remplacé par POIs.Random). |
| RandomDroneBase | OBSOLÈTE | Ancien format de bases de drones (remplacé par DroneBaseSetup). |

## 1.2 Restrictions d'usage et CPU (par type de structure)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| AllowSV / AllowCV / AllowHV / AllowBA | True | Structure autorisée dans le playfield (Small/Capital/Hover/Base). |
| AllowBlueprintSV/CV/HV/BA | True | Spawn de blueprint du type autorisé. |
| AllowBPFactory | True | Factory de blueprint autorisée. |
| DenyLeaveSV/CV/HV | False | Interdit de QUITTER le playfield avec ce type de structure. |
| DenyMicroWarp | False | Interdit le micro-warp (saut court). |
| AllowMaxCPUTierSV/CV/HV/BA | 0..10 | Palier CPU maximum autorisé pour le type (0 = pas de limite spécifique). |
| Instance | bloc InstanceData | Règles d'instance (playfields instanciés). |

InstanceData (blocs `Instance:`) :
| Clé | Sens |
|---|---|
| Instance.Time | Durée de l'instance (min). |
| Instance.MaxPlayers | Nombre de joueurs maximum simultanés. |
| Instance.PortalOpen | Temps (s) pendant lequel le portail d'entrée reste ouvert. |
| Instance.Cooldown | Délai avant une nouvelle entrée. |
| Instance.DropInventory | Vide l'inventaire à l'entrée. |
| Instance.AllowBlueprints | Spawn de blueprint autorisé dans l'instance. |
| Instance.RestrictToOrigin | Restriction d'Origin dans l'instance. |
| Instance.LockOnFaction | Instance réservée à la faction du premier entrant. |
| Instance.EnterWithEmptyInventory | Entrée avec inventaire obligatoirement vide. |
| Instance.NoVolumeWeightForPlayer | Désactive volume/poids joueur dans l'instance. |

## 1.3 Atmosphère, températures, respiration

| Propriété | Défaut moteur | Sens |
|---|---|---|
| AtmosphereEnabled | True | Atmosphère rendue (fog/ciel). |
| AtmosphereColor | "0.55, 0.61, 0.65" | Couleur de l'atmosphère. |
| AtmosphereDensity | float | Densité optique (épaisseur du voile). |
| AtmosphereO2 | 0.1 | Fraction d'O2 dans l'air : au-dessus du seuil, respirable sans masque. |
| AtmosphereBreathable | bool | Force l'air respirable (indépendamment d'AtmosphereO2). |
| AtmosphereParams | float[] | Paramètres fins du shader d'atmosphère (4 floats). |
| OrbitUsesLightColor | bool | L'orbite réutilise les couleurs de lumière de la planète liée. |
| Temperature | int | Température de référence (°C) au sol. |
| TemperatureDay | int (déf. int.MinValue) | Température de jour (si non définie = Temperature). |
| TemperatureNight | int | Température de nuit. |
| TemperatureMinMax | int[] [min,max] | Plage de températures (dynamique : tirage aléatoire). |
| Radiation | float | Radiation ambiante (R/s). |
| HumidityMinMax | float[] | Plage d'humidité (drive la pluie/neige). |

## 1.4 Mer, terrain

| Propriété | Sens |
|---|---|
| SeaLevel | Altitude de la mer (0..100 ; -999 = pas d'eau). |
| TerrainLevel | Niveau moyen du terrain (0..100). |
| BaseLevel | Niveau de base (plancher de génération, 0..511). |
| LandWaterRatio | Part d'eau 0..1 (génération). |
| TerrainHeightMapMax | Hauteur max de la heightmap (déf. -1 = 511). |
| GroundShapes | Liste de stamps de relief utilisés. |
| BiomeStampTries | Nombre d'essais de placement des stamps de biome (déf. 20). |

## 1.5 Ciel, lumière, fog, nuages, vent

| Propriété | Défaut moteur | Sens |
|---|---|---|
| DayLightIntensity | 0.6 | Intensité de la lumière du jour. |
| NightLightIntensity | 0.7 | Intensité de la lumière nocturne. |
| DayShadowStrength | 0.65 | Force des ombres de jour. |
| NightShadowStrength | 0.4 | Force des ombres de nuit. |
| LightZenithColor | "1, 0.95, 0.915" | Couleur de lumière au zénith (jour). |
| LightHorizonColor | "1, 0.6, 0" | Couleur de lumière à l'horizon (jour). |
| NightLightColor | "0.671, 0.647, 0.992" | Couleur de lumière de nuit. |
| SkyColor | "1, 1, 1" | Couleur du ciel. |
| SkyHorizonColor | — | Couleur du ciel à l'horizon. |
| SunFlare | string | Asset de flare solaire (ex. EnvironmentalEffects/SunFlareWhite2). |
| FogCloudIntensity | 1 | Densité des nuages de fog volumétrique. |
| FogColor | "0.8, 0.8, 0.8" | Couleur du fog linéaire. |
| FogIntensity | float | Intensité du fog linéaire. |
| FogStartDistance | float | Distance de départ du fog. |
| AtmosphereFog | float | Fog d'atmosphère (vue orbite). |
| GroundFogIntensity | float | Intensité du fog au sol (nappe basse). |
| GroundFogHeight | float | Hauteur de la nappe de fog au sol. |
| CloudsDensity | float | Densité des nuages. |
| CloudsSharpness | 1 | Netteté des contours de nuages. |
| CloudsBrightness | 0.6 | Luminosité des nuages. |
| CloudsOpacity | 0.9 | Opacité des nuages. |
| CloudsZenithColor / CloudsHorizonColor | voir défauts | Couleurs des nuages (zénith/horizon). |
| CloudsNightZenithColor / CloudsNightHorizonColor | "0.054, 0.094, 0.152" | Couleurs des nuages de nuit. |
| WindSpeed | int (déf. 1) | Force du vent (bruit des décors, éoliennes). |

## 1.6 Effets spéciaux — SpecialEffectsLocal

Effets attachés à des biomes, permanents (particules locales).

| Propriété | Défaut moteur | Sens |
|---|---|---|
| SpecialEffectsLocal[].Name | — | Id de l'effet (ex. Pollen, DustDevil, FireFliesGreenFew, WindLines). |
| SpecialEffectsLocal[].Biome | — | Biomes où l'effet s'applique (`[ Desert, Dunes ]` ou `[ Any ]`). |
| SpecialEffectsLocal[].Time | Always | Day, Night ou Always. |
| SpecialEffectsLocal[].MaxHeight | 200 | Altitude max d'apparition. |
| SpecialEffectsLocal[].FollowPlayerY | True | L'effet suit l'altitude du joueur. |
| SpecialEffectsLocal[].Struct | bool | Évite/active près des structures. |

## 1.7 Effets spéciaux — SpecialEffectsGlobal (météo et événements mondiaux)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| SpecialEffectsGlobal[].Name | — | Id de l'effet (météo : Clear, Clouds, Fog, HeatWave, FogRadiationGreen... ; événements : MeteorShower, BirdFlocksVultures...). |
| SpecialEffectsGlobal[].Type | Effect | Effect ou Weather (les météos sont affichées dans l'icône météo). |
| SpecialEffectsGlobal[].Time | Always | Night, Day, Always. |
| SpecialEffectsGlobal[].InitialDelay | 0.5 (déf moteur) | Délai (min de jeu) avant la 1re apparition. |
| SpecialEffectsGlobal[].Delay | 1 | Intervalle (min de jeu) entre deux apparitions. |
| SpecialEffectsGlobal[].Lifetime | 5 | Durée (min de jeu) de l'effet. |
| SpecialEffectsGlobal[].Biome | — | Biomes autorisés (`[ Any ]` = partout). |
| SpecialEffectsGlobal[].PlyDist | 50 | Distance au joueur pour spawn (m). |
| SpecialEffectsGlobal[].SpawnY | 50 | Altitude de spawn. |
| SpecialEffectsGlobal[].Struct | True / False / Avoid | True = près des structures ok ; Avoid = pas près des structures ; False = indépendant. |

## 1.8 Presets de végétation (Presets)

Utilisés par les `Grass`/`Decorations` des biomes via la clé `Preset`.

| Propriété | Défaut | Sens |
|---|---|---|
| Presets[].Name | — | Nom du preset (référencé par les tuiles d'herbe). |
| Presets[].Density | 1 | Multiplicateur de densité de touffes. |
| Presets[].Snow | 0 | Taux de couverture de neige sur la végétation. |
| Presets[].Hue | "0, 0, 0" | Teinte : `delta, plage, probabilité` (coloration des sprites). |
| Presets[].Contrast | 1 | Contraste de la texture. |
| Presets[].Saturation | 1 | Saturation de la texture. |
| Presets[].BendPower | 1 | Amplitude de courbure au vent. |
| Presets[].GrassPower | 1 | Force du sway de l'herbe. |
| Presets[].spawn.Min / spawn.Max | 0 / 0.5 | Plage (0..1) sur la carte d'humidité/température où l'herbe spawn. |
| Presets[].spawn.BushPower | 1 | Puissance de spawn des buissons. |
| Presets[].spawn.Noise | "1, 0.1, 2, 0.5" | Bruit de spawn (4 floats). |
| Presets[].scale.Power | 1 | Puissance de variation d'échelle. |
| Presets[].scale.Noise | "1, 0.1, 2, 0.5" | Bruit d'échelle. |

## 1.9 Biomes — bloc racine `Biomes:` (stamps)

Structure moteur : `TerrainBiomeData` (racine) + `DCClusterData` (chaque
biome nommé). RE2-FR écrit les biomes sous `Biomes:` ; le moteur lit aussi
`Terrain.Biomes`.

| Propriété (sous `Biomes`) | Défaut | Sens |
|---|---|---|
| Biomes.Name | — | Racine de chaque biome : clé = nom du biome (ex. `Desert:`). Toutes les sous-clés suivantes s'écrivent SOUS cette clé. |
| Biomes.Name.PoleLevel | 1 | Niveau des pôles (répartition planétaire). |
| Biomes.Name.PerlinCol | 1 | Échelle du bruit Perlin de coloration. |
| Biomes.Name.NoiseStrength | 0.4 | Force du bruit des contours de biome. |
| Biomes.Name.ColorChange | — | Changement de couleur par altitude : YFadeCenter, YFadeRange (40), YFadeMin, YFadeMax. |

Clés d'un biome (DCClusterData) :

| Propriété | Défaut | Sens |
|---|---|---|
| Name | — | Nom interne du biome (référencé par POIs/creatures/effects). |
| Id | int | Id numérique du biome (couleur de debug/ancien format). |
| Radiation | 0 | Radiation du biome (R/s, s'ajoute à l'ambiance). |
| Temperature | int | Correction de température locale. |
| AddTemperature | (variante RE2) | Idem, additive. |
| AmbientSound | string | Son d'ambiance du biome. |
| Weather | string | Effet météo actif par défaut dans le biome. |
| LevelMod | string | Modificateur de niveau des POI/entités du biome (ex. `+2`). |
| Stamps | string[] | Stamps de terrain/biome appliqués (nom des fichiers de stamp). |
| StampTries | int | Nombre d'essais de pose du stamp. |
| StampProb | 1 | Probabilité de pose de chaque stamp. |
| StampForcesBiome | bool | Le stamp impose son biome au sol posé. |
| StampForcesBiomeType | OverlapAll | OverlapAll / OverlapOwn / OverlapOther / OverlapOff : comment le stamp interagit avec les biomes voisins. |
| IgnoreForcedBiome | bool | Ne pas subir les biomes forcés par les stamps voisins. |
| SelectionCriteria | string[] | Critères de sélection (altitude/pente/zone) quand plusieurs stamps concourent. |
| SpecialBiome | — | Bloc biome spécial : IsStarterBiome, FixedPosition ("x, z"), CountMinMax, Avoid ("NomBiome"), AvoidDistance (m). |
| IsStarterBiome | bool | Le joueur peut démarrer ici (spawn joueur). |
| Texture | float[] | Contrôle de texture : `[idTex, idTex2, blend]` ou triples détaillés. |
| Color | "r,g,b" | Couleur dominante du biome (modulation). |
| Grass | bloc | Liste `Name:` : tuiles d'herbe avec Density, Preset, YScale. |
| Decorations | bloc | Liste `Name:` : décors posés (items) avec Density, Preset, YScale (même modèle que Grass). |
| DecorationItem | string[][] | Ancienne forme : liste `[item, densité, ...]`. |
| UndergroundLayers | int[][] | Couches souterraines : `[idBloc, profondeurMin, profondeurMax, probabilité]` par couche. |
| UndergroundLayersDefault | bool | Utilise les couches par défaut du moteur. |
| PoleBiome | bool | Biome réservé aux pôles. |
| FixedPosition | string | Position fixe "x, z" du stamp de biome. |
| Splat1 / Splat2 | float[] | Paramètres de splatmap (transitions de textures). |
| ClusterSize / NbOfClusters | int | Ancien système de clusters (V8) : taille et nombre de taches. |
| ClusterScale / ClusterProb / ClusterRange | (RE2) | Variations d'échelle/probabilité/portée des clusters. |
| GrassItem / DCGrass | listes | Ancien format d'herbe (Name, Density, Preset, YScale). |

## 1.10 Biomes — blocs `MainBiome:`, `SubBiomes:`, `Biome:` (ancien système altitude/pente)

| Propriété | Sens |
|---|---|
| MainBiome.Textures | Liste de textures par altitude `[idTex, idTex2, blend, altMin, altMax, ...]`. |
| MainBiome.Decorations | Liste de décors `[item, densité, hauteur, ...]`. |
| SubBiomes.Altitude | Altitude (0..100) de bascule vers ce sous-biome ; + Textures/Decorations comme MainBiome. |
| Biome.Altitude | Ancien format : liste `[altMin, altMax]`. |
| Biome.Slope | Liste `[slopeMin, slopeMax]` (pente). |
| Biome.BiomeClusterData | Clusters par altitude/pente : mêmes clés que les biomes stamped (Name, Color, Texture, Grass, Decorations, Stamps, StampProb, StampTries, StampForcesBiome..., Temperature, Radiation, AmbientSound, Weather, UndergroundLayers, IgnoreForcedBiome, SelectionCriteria, LevelMod, SpecialBiome...). |
| BiomeTextureReplacements | Liste Biome/From/To : remplace une texture par une autre dans un biome (ex. textures moddées). |

## 1.11 Ressources — RandomResources (gisements aléatoires)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| RandomResources[].Name | — | Nom du gisement (ex. IronDeposit, PentaxidCrystal, OilShale...). |
| RandomResources[].CountMinMax | [1,1] | Nombre de gisements [min, max]. |
| RandomResources[].SizeMinMax | [1,1] | Taille du dépôt (multiplicateur). |
| RandomResources[].DepthMinMax | [1,1] | Profondeur d'enfouissement (surface = 0). |
| RandomResources[].IsImportant | false | Gisement « important » : signalé, jamais déserté au wipe. |
| RandomResources[].IsScalingCount | false | Nombre de gisements mis à l'échelle avec la taille planète. |
| RandomResources[].DroneProb | 0 | Probabilité qu'une base de drones défende le gisement (0..1) ; 0 = aucun drone. |
| RandomResources[].MaxDroneCount | 1 | Nombre max de drones de défense. |
| RandomResources[].LevelMod | string | Modificateur de niveau du POI de défense. |
| RandomResources[].Faction | string | Faction des défenseurs. |
| RandomResources[].PlaceAt | Default/Terrain/OnWater/UnderWater/ResourceAll | Contraintes de placement (enum PlacingTargets). |
| RandomResources[].Biome | string[] | Biomes autorisés. |
| RandomResources[].BiomesExcluded | string[] | Biomes exclus. |
| RandomResources[].DistTypeCylinder | — | Distribution cylindrique : MaxRadius, YVariance. |
| RandomResources[].DistTypeHelix | — | Hélice : MaxRadius, GrowthPerRound, DropPerRound. |
| RandomResources[].DistTypeWorm | — | Ver de terre : FreqDirChange, DirChangeMagnitude, MaxLength, DeepnessType. |

## 1.12 Ressources — FixedResources (gisements à position fixe)

| Propriété | Sens |
|---|---|
| FixedResources[].Name | Nom du gisement. |
| FixedResources[].Pos | [x, y, z] position absolue dans le chunk. |
| FixedResources[].Radius | Rayon du gisement. |
| FixedResources[].Faction | Faction propriétaire (drônes de défense). |
| FixedResources[].DistTypeCylinder/Helix/Worm | Forme du gisement (mêmes sous-clés que RandomResources). |

## 1.13 Ressources — AsteroidResources (astéroïdes surfaciques volants)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| AsteroidResources[].Name | — | Nom de l'astéroïde (bloc mineable). |
| AsteroidResources[].Threshold | — | Seuil de proximité d'apparition. |
| AsteroidResources[].Amount | — | Quantité de minerai. |
| AsteroidResources[].InitialDelay | -1 | Délai initial (min). |
| AsteroidResources[].Delay | -1 | Intervalle de réapparition (min). |
| AsteroidResources[].DespawnDelay | — | Délai de disparition après épuisement. |

NB : ces clés génèrent des astéroïdes flottants au-dessus du terrain ;
`RegenerateAfter` de la fiche cerveau s'applique aux POI et aux champs
d'astéroïdes espace (voir Resources espace).

## 1.14 POIs — POIs.Random[] (groupes aléatoires)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| POIs.Random[].GroupName | — | Nom du groupe de blueprints (doit exister côté jeu = nom de groupe du prefab). |
| POIs.Random[].CountMinMax | [0,0] | Nombre d'instances [min, max] dans le playfield. |
| POIs.Random[].Faction | — | Faction propriétaire du POI. |
| POIs.Random[].FactionTerritory | string[] | Factions dans le territoire desquelles le POI peut spawn. |
| POIs.Random[].Territory | true | Le POI marque son territoire (blocage des autres factions). |
| POIs.Random[].AvoidFactionTerritory | false | Évite le territoire des autres factions. |
| POIs.Random[].DroneProb | 0 | Probabilité de renfort de drones attitrés (0..1) ; 0 = jamais. |
| POIs.Random[].DronesMinMax | [0,0] | Nombre de drones en garnison [min, max]. |
| POIs.Random[].ReserveCount | 0 | Nombre de POI de réserve (re-spawn tant que non découverts). |
| POIs.Random[].TroopTransport | false | Un Troop Transport peut débarquer des troupes ici. |
| POIs.Random[].IsImportant | false | POI important (signalé, non nettoyé). |
| POIs.Random[].IsScalingCount | false | Le count est mis à l'échelle avec la taille planète. |
| POIs.Random[].IsCommandCenter | false | Centre de commandement (cible stratégique de la campagne drone). |
| POIs.Random[].IsAuxPOI | false | POI auxiliaire (lié à un POI principal via AuxiliaryPOIs). |
| POIs.Random[].AuxiliaryPOIs | string[] | Noms des POI auxiliaires rattachés. |
| POIs.Random[].UseEachGroupPoiOnlyOnce | false | Chaque blueprint du groupe n'est utilisé qu'une fois. |
| POIs.Random[].InitPower | false | Initialise l'alimentation (réacteurs actifs) au spawn. |
| POIs.Random[].LevelMod | string | Modificateur de niveau (puissance des défenses). |
| POIs.Random[].PlayerStart | false | Peut servir de point de départ joueur. |
| POIs.Random[].SpawnPOINear | string[] | Noms de POI à proximité desquels placer (déclarés AVANT). |
| POIs.Random[].SpawnPOINearRange | [min,max] | Plage de distance (m) autour des POI cités. |
| POIs.Random[].SpawnPOIAvoid | string[] | Noms de POI à éviter (déclarés AVANT). |
| POIs.Random[].SpawnPOIAvoidDistance | int | Distance minimale (m) des POI évités. |
| POIs.Random[].SpawnResource | string[] | Gisements miniers à placer près du POI (format "NomDepot"). |
| POIs.Random[].SpawnResourceRange | [min,max] | Plage de distance des gisements. |
| POIs.Random[].PlaceAt | Default/Terrain/OnWater/UnderWater/ResourceAll | Contrainte de surface de placement. |
| POIs.Random[].Biome | string[] | Biomes où le POI peut apparaître. |
| POIs.Random[].BiomesExcluded | string[] | Biomes exclus. |
| POIs.Random[].DroneBaseSetup | string | Référence un DroneSetupID de DroneBaseSetup. |
| POIs.Random[].DroneSetupID | string | Id de setup de drones (liaison). |
| POIs.Random[].PlanetVesselBaseSetup | string | Référence une base de vaisseau planétaire. |
| POIs.Random[].NoShieldReload | false | Le bouclier ne se recharge pas (espaces). |
| POIs.Random[].SpaceDefenseOverrideDefaults | false | Remplace les défenses spatiales par défaut. |
| POIs.Random[].SpaceDefenseProbability | 0 | Probabilité de défenses spatiales. |
| POIs.Random[].SpaceDefensePriceMinMax | — | Prix min/max pour désactiver les défenses (corruption). |
| POIs.Random[].Properties | Key/Value | Paires librement lues par le jeu (voir 1.16). |
| POIs.Random[].POIDistance | OBSOLÈTE | Ancienne clé : convertie en SpawnPoiRange + SpawnPOIAvoidDistance. |
| POIs.Random[].SpawnPOINearDistance | OBSOLÈTE | Converti en SpawnPoiRange [80, valeur]. |
| POIs.Random[].ResourceDistance | OBSOLÈTE | Converti en SpawnResRange [80, valeur]. |

## 1.15 POIs — POIs.Fixed[] (POI à position fixe)

| Propriété | Sens |
|---|---|
| POIs.Fixed[].Type | Nom du prefab (fichier .epb). |
| POIs.Fixed[].Prefab | Alias/duplicate de Type (moteur accepte Prefab). |
| POIs.Fixed[].Name | Nom d'affichage/instance (utilisé par SpawnPOINear/Avoid d'autres POI). |
| POIs.Fixed[].DisplayName | Nom affiché sur la carte/HUD. |
| POIs.Fixed[].Mode | Survival ou Creative (contexte d'apparition). |
| POIs.Fixed[].SubMode | Variante du mode (ex. StartPlanet du start setup). |
| POIs.Fixed[].Pos | [x, y, z] position d'ancrage (y = altitude absolue). |
| POIs.Fixed[].Rot | [x, y, z] rotation en degrés. |
| POIs.Fixed[].InitPower | Alimentation initiale. |
| POIs.Fixed[].LevelMod | Modificateur de niveau. |
| POIs.Fixed[].Faction | Faction du POI. |
| POIs.Fixed[].FactionTerritory | Territoires permis. |
| POIs.Fixed[].Properties | Paires Key/Value (voir 1.16). |
| POIs.Fixed[].NoShieldReload / IsCommandCenter / SpaceDefense* | Comme Random. |
| POIs.Fixed[].FieldNameFogColor | "r, g, b" : brouillard local coloré autour du POI. |
| POIs.Fixed[].SpawnResource / SpawnResourceRange | Gisements liés. |
| POIs.Fixed[].BaseField | true = zone de départ de base (BaseField). |
| POIs.Fixed[].RandomRotation | true = rotation aléatoire autour de Y. |
| POIs.Fixed[].Compound | POI composé : CountMinMax, Probability, Name (liste de prefabs), DistanceMinMax (m), Rotate (rotation aléatoire). |
| POIs.Fixed[].IsCompoundSubDesc | true = ce POI est un sous-élément d'un Compound. |
| POIs.Fixed[].Position | Bloc de placement procédural : PosXZMinMax [min,max], PosYMax (2000), PosMultiplier [2..5], RadialInfo. |
| POIs.Fixed[].Probability | Probabilité d'apparition (0..1) en usage procédural. |
| POIs.Fixed[].CountMinMax | Nombre d'instances. |
| POIs.Fixed[].RadiusMinMax | Plage de rayon (astéroïdes/POI volumiques). |

## 1.16 POIs — FixedPlayerStart (départs joueur) et PoiGroups

| Propriété | Sens |
|---|---|
| POIs.FixedPlayerStart[].Mode | Survival ou Creative. |
| POIs.FixedPlayerStart[].SubMode | Variante (ex. StartPlanet). |
| POIs.FixedPlayerStart[].Spawn | PlayerSpawnOption : condition d'usage du départ. |
| POIs.FixedPlayerStart[].Pos | [x, y, z] point d'arrivée. |
| POIs.FixedPlayerStart[].RotY | Rotation Y du joueur. |
| POIs.FixedPlayerStart[].Structure | Nom du prefab où faire apparaître le joueur. |
| POIs.FixedPlayerStart[].Items | Items de départ (liste "Item:Nb"). |
| POIs.FixedPlayerStart[].Armor | Armure initiale. |
| POIs.FixedPlayerStart[].PlayerArmor | Liste d'armures autorisées/posées. |
| POIs.FixedPlayerStart[].Status | Status effects initiaux (ex. FoodPills). |
| PoiGroups | Gestion RE2 de groupes de POI réutilisables : GroupName, Configuration, Defaults (CountMinMax, Faction, InitPower, LevelMod, NoShieldReload, Properties, UseEachBlueprintOnlyOnce), Filters (BlueprintGroupNames). |

## 1.17 POIs — Properties (Key/Value) : catalogue des clés observées

Lues par le moteur selon le contexte (POI, espace, jumpgate...). Clés
présentes dans RE2-FR :

| Key | Sens | Valeurs observées |
|---|---|---|
| Discovery | Visible dès l'entrée dans le playfield | true/false |
| MapMarker | Marqueur sur la carte | true/false |
| MapDistance | Distance d'affichage du marqueur carte | entier (m) |
| HudDistance | Distance d'affichage HUD | entier (m) |
| Music | Musique propre au POI | nom d'asset |
| JumpGate | Le POI est un jumpgate | true |
| AIManExcludeFromPatrol | Exclut l'IA de patrouille | true |
| TradingStation | Station de commerce (prix/réduction) | voir Prices |
| Prices | Catalogue de prix : `Item:Prix,IfReputation:X:Prix` | ex. `All,IfNeutral:0.05,...` |
| IfNeutral/IfFriendly/IfHonored | Modificateurs de prix par réputation | fraction ± |
| Ref | Structure liée (marchand/mission) | nom de POI |
| InstanceOptions | Options d'instance | voir PDA |
| SpaceDefense* | cf. 1.14 | |

(La liste exacte des clés est data-driven : toute clé inconnue est ignorée.)

## 1.18 DroneBaseSetup — Random[] (bases de drones procédurales)

| Propriété | Sens |
|---|---|
| DroneBaseSetup.Random[].GroupName | Nom de la base (affiché/en interne). |
| DroneBaseSetup.Random[].DronesMinMax | Taille de la garnison [min, max]. |
| DroneBaseSetup.Random[].ReserveCount | Réserve de drones. |
| DroneBaseSetup.Random[].DroneProb | Probabilité d'activation de la base. |
| DroneBaseSetup.Random[].Difficulty | Difficulté de la base (1..5). |
| DroneBaseSetup.Random[].PresetStyle | Style prédéfini de la base. |
| DroneBaseSetup.Random[].BaseAttack | Configuration des attaques de base. |
| DroneBaseSetup.Random[].Stock[].Name | Nom de l'entité en stock (ex. Zirax, AssaultCyborg, Crawler). |
| DroneBaseSetup.Random[].Stock[].Amount | Quantité (entier ou "infinite"). |
| DroneBaseSetup.Random[].Stock[].Extra | Réserve supplémentaire (déf. -1 = aucune). |
| DroneBaseSetup.Random[].Stock[].Type | Type d'unité (déf. FighterDrone). |
| DroneBaseSetup.Random[].DroneSetupID | Id de setup référencé par les POI. |
| DroneBaseSetup.Random[].DroneBaseSetup | Référence croisée (POI → base). |
| DroneBaseSetup.Random[].PlanetVesselBase | Base de vaisseau planétaire (Name, Faction, Position3D, LevelMod, BaseType, KeyId, PlanetVessel[]). |
| DroneBaseSetup.Random[].PlanetVesselBase.PlanetVessel[].Name | Nom du vaisseau. |
| .../FixedMaxSpeed | Vitesse max fixe. |
| .../Mission | Nom de mission IA (RangePatrol, Attack...). |
| .../RangePatrolCenter / Radius / Altitude | Zone de patrouille (centre, rayon, altitude). |
| .../RangePatrolAvoidArea[].POIName/Duration | Zones évitées pendant la patrouille. |
| .../RespawnDelay | Délai de réapparition (min). |
| .../InitialDelay | Délai avant première apparition. |
| .../UseMainDroneBaseAsBase | Utilise la base principale comme base. |
| .../AttackDistToGround (VesselAttack.DistanceToGround) | Altitude d'attaque au sol. |
| .../AttackCVCircleAround.DistToTarget | Distance d'orbite autour d'une cible CV. |
| .../Stock | Drones embarqués (cf. Stock). |
| .../Properties | Key/Value (cf. 1.16). |

## 1.19 DroneBaseSetup — Fixed[] (bases à position fixe) et variantes

| Propriété | Sens |
|---|---|
| DroneBaseSetup.Fixed[].Name | Nom de la base. |
| DroneBaseSetup.Fixed[].Faction | Faction. |
| DroneBaseSetup.Fixed[].Pos | [x, y, z] position. |
| DroneBaseSetup.Fixed[].LevelMod | Modificateur de niveau. |
| DroneBaseSetup.Fixed[].DroneOnDuty[].Name | Nom du drone de garde (entité). |
| DroneBaseSetup.Fixed[].DroneOnDuty[].Faction | Faction du drone. |
| DroneBaseSetup.Fixed[].DroneOnDuty[].CanNotBeControlledByMasterAI | Le Master AI ne le pilote pas. |
| DroneBaseSetup.Fixed[].DroneOnDuty[].POINameAsPositionRef | Se positionne via un POI nommé. |
| DroneBaseSetup.Fixed[].DroneOnDuty[].Count | Nombre. |
| DroneBaseSetup.Fixed[].DroneOnDuty[].Radius | Rayon de ronde. |
| DroneBaseSetup.Fixed[].DroneOnDuty[].Properties | Key/Value. |
| DroneBaseSetup.Fixed[].SpaceVessel[].Name / Faction | Vaisseau fixe (cargo, patrouilleur). |
| DroneBaseSetup.Fixed[].SpaceVessel[].FixedMaxSpeed | Vitesse max. |
| DroneBaseSetup.Fixed[].SpaceVessel[].Mission | Mission IA (RangePatrol, Immobile, Freighter...). |
| DroneBaseSetup.Fixed[].SpaceVessel[].DelayBetweenRespawn | Délai entre deux réapparitions (min). |
| DroneBaseSetup.Fixed[].SpaceVessel[].DelayBeforeSelfDestruction | Délai avant auto-destruction. |
| DroneBaseSetup.Fixed[].SpaceVessel[].IsRespawnAfterDestruction | Respawn après destruction. |
| DroneBaseSetup.Fixed[].SpaceVessel[].RangePatrol | Bloc patrouille : Position3D, POINameAsPositionRef, Radius, DistToGround, RangePatrolAvoidArea (POIName, Radius, Duration), IsAllowToReturnToBaseWhenOver. |
| DroneBaseSetup.Fixed[].SpaceVessel[].Immobile | Bloc immobile : Position3D ou POINameAsPositionRef. |
| DroneBaseSetup.Fixed[].SpaceVessel[].Freighter | Bloc cargo : DelayBetweenRespawn, DelayBeforeSelfDestruction, IsRespawnAfterDestruction, PathWayPoint (liste de waypoints [x,y,z]). |
| DroneBaseSetup.Fixed[].SpaceVessel[].Stock | Drones embarqués. |
| DroneBaseSetup.Fixed[].SpaceVessel[].Properties | Key/Value. |
| DroneBaseSetup.Fixed[].DroneSpaceFreighter (obs.) | Ancienne forme de cargo. |
| DroneBaseSetup.Fixed[].DronePlanetVessel (obs.) | Ancienne forme de vaisseau planétaire. |
| DroneBaseSetup.Fixed[].DronePlanetBase (obs.) | Ancienne forme de base planétaire (Name, Faction, Position3D, BaseType, KeyId, PlanetVessel[]). |
| DroneBaseSetup.DroneBases[].DroneSetupID + Stock | Bases « v2 » par DroneSetupID (stock global). |
| DroneBaseSetup.PlanetVesselBases[] | { DroneBase, PlanetVessel } : base + vaisseau liés (NewPlanetVessel : Name, CountMinMax, Position3D, Faction, LevelMod, FixedMaxSpeed, PauseTimeOnStart, DelayBetweenRespawn, DelayBeforeSelfDestruction, IsRespawnAfterDestruction, RangePatrolTask, ImmobileTask, Stock, Properties). |
| DroneBaseSetup.PlanetVessels[] | Vaisseaux planétaires autonomes (mêmes clés que PlanetVessel). |
| DroneBaseSetup.FreeDrones[].Name | Drones libres : entité (ex. DroneSmallAttackBase). |
| DroneBaseSetup.FreeDrones[].Faction | Faction. |
| DroneBaseSetup.FreeDrones[].CanNotBeControlledByMasterAI | Hors contrôle du Master AI. |
| DroneBaseSetup.FreeDrones[].POINameAsPositionRef | Ancrage POI. |
| DroneBaseSetup.FreeDrones[].Count | Nombre. |
| DroneBaseSetup.FreeDrones[].Radius | Rayon d'activité. |
| DroneBaseSetup.FreeDrones[].Properties | Key/Value. |

## 1.20 DroneSpawning (drones d'escarmouche hors base)

| Propriété | Sens |
|---|---|
| DroneSpawning.Random[].Name | Zone : nom libre. |
| DroneSpawning.Random[].DronesMinMax | Nombre de drones [min, max]. |
| DroneSpawning.Random[].Faction | Faction. |
| DroneSpawning.Random[].CenterX | Centrage X de la zone. |
| DroneSpawning.Random[].POINameAsPositionRef | Ancrage sur un POI. |
| DroneSpawning.Random[].Radius | Rayon de la zone. |
| DroneSpawning.Fixed[].Name / Pos / Radius | Drone à position fixe. |

## 1.21 CreatureSpawning (créatures)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| CreatureSpawning[].Biomes | — | Biomes concernés (liste). |
| CreatureSpawning[].Entities[].Name | — | Nom de l'entité (EClass, ex. Crawler, Oviraptor). |
| CreatureSpawning[].Entities[].Amount | — | Nombre moyen simultané (float). |
| CreatureSpawning[].Entities[].Color | "1.0, 1.0, 1.0, 0.0" | Teinte (r,g,b,alpha) — variations de pelage. |
| CreatureSpawning[].Entities[].Biomes | — | Biomes spécifiques de l'entité (hérite du groupe). |
| CreatureSpawning[].Entities[].AllowInWater | false | Peut spawn dans l'eau. |
| CreatureSpawning[].Entities[].DelayMinMax | [-1,-1] (moteur : ∞) | Délai de réapparition [min, max] (min de jeu) ; -1/-1 = jamais de re-spawn automatique. |
| CreatureSpawning[].Entities[].Period | OBSOLÈTE | Always/Day/Night (remplacé par la gestion jour/nuit du moteur). |
| CreatureSpawning[].Entities[].Delay | OBSOLÈTE | Ancien délai unique. |
| CreatureSpawning[].Entities[].RestrictYMinMax | OBSOLÈTE | Ancienne restriction d'altitude (ignorée). |

## 1.22 SpawnZones (zones de spawn de créatures) et SpawnRateZones

| Propriété | Défaut moteur | Sens |
|---|---|---|
| SpawnZones[].SpawnAt | — | Position(s) "x, z" (ou POI) de la zone. |
| SpawnZones[].BiomesExcluded | — | Biomes exclus. |
| SpawnZones[].Radius | — | Rayon de la zone (m). |
| SpawnZones[].RadiusRandom | — | Variation aléatoire du rayon. |
| SpawnZones[].RateMultiplyerCenter | — | Multiplicateur de taux au CENTRE de la zone (1 = normal). |
| SpawnZones[].RateMultiplyerEdge | — | Multiplicateur au BORD ; interpole centre→bord. > 1 = couronne active. |
| SpawnZones[].SpawnOnlyIfPoiIsAlien | false | Zone active seulement si le POI ancré est alien. |
| SpawnZones[].Color | "0.2, 1.0, 0.2, 0.5" | Couleur de debug/overlay. |
| SpawnZones[].Entities[].Names | — | Entités autorisées (liste). |
| SpawnZones[].Entities[].Biomes | — | Biomes autorisés. |
| SpawnZones[].Entities[].Amount | — | Quantité. |
| SpawnZones[].Entities[].Color | cf. défaut | Teinte des entités. |
| SpawnZones[].Entities[].DelayMinMax | [min,max] | Délai de réapparition. |
| SpawnZones[].Entities[].Period | Always/Night/Day | Moment d'apparition. |
| SpawnZones[].Entities[].AllowInWater | false | Spawn aquatique. |
| SpawnRateZones[].SpawnAt / Radius / RadiusRandom / RateMultiplyerCenter / RateMultiplyerEdge / Color | idem | Zone qui MODIFIE le taux de spawn d'autres groupes. |
| SpawnRateZones[].AffectedGroups | — | Groupes d'entités affectés. |
| SpawnRateZones[].AffectEnemies | — | Affecte les hostiles. |
| SpawnRateZones[].AffectFriendly | — | Affecte les amicaux. |

## 1.23 TroopsTransportContent

| Propriété | Sens |
|---|---|
| TroopsTransportContent[].Name | Nom de l'unité débarquée par un Troop Transport. |
| TroopsTransportContent[].Amount | Nombre débarqué. |
---

# 2. playfield_dynamic.yaml (génération procédurale)

Classes moteur : `DynamicPlayfieldYaml` (+ `DynamicPlayfieldParams`,
`PlanetSizeData`, `PresetData`, `GrassItem`, `DecoItem`) et, pour les
espaces dynamiques, `DynamicSpacePlayfieldYaml` (+ `POIDesc`, `ResourceDesc`,
`POIStockDesc`, `DroneSpawningDesc`, `DroneBaseSetupDesc`, `PathwayPointDesc`,
`AsteroidFieldDesc`, `PositionDesc`, `CompoundDesc`).

## 2.1 Génération du système (Sectors.yaml dynamique / RandomPresets)

| Propriété | Sens |
|---|---|
| GenerationParams.MapScale | Échelle de la carte galactique. |
| GenerationParams.OneWayWarpProb | Probabilité d'un warp à sens unique. |
| GenerationParams.SolarSystemSqueezeMinMax | Compression [min,max] du système solaire. |
| GenerationParams.PlanetCountProbs | Probabilités du nombre de planètes par système. |
| GenerationParams.POICountProbs | Probabilités du nombre de secteurs POI. |
| GenerationParams.PlanetLists | Listes de planètes prédéfinies à piocher. |
| GenerationParams.POIs | POIs de système à générer. |
| GenerationParams.UniqueStarterPlanet | Planète de départ unique forcée. |
| GenerationParams.StarCount / NebulaCount / NebulaColors1..27 / NebulaPositionUpdate | Décor de fond : nombre d'étoiles/nébuleuses, palettes de couleurs. |
| GenerationParams.GalaxyMode / GalaxySpawnAmount / GalaxySpawnRadius | Paramètres de génération galactique. |
| GenerationParams.StarClass / StarClass_1..N / CompanionStarClass / UseDefaultStarDef | Définitions de classes d'étoiles (spectre, température, planètes permises). |
| GenerationParams.SolarSystemConfigSuffix | Suffixe de fichier SolarSystemConfig utilisé. |
| GenerationParams.StarterSystemName / StarterSystemStarClass / StarterSystemLYCoord | Système de départ (nom, classe, coordonnée en années-lumière). |
| GenerationParams.HabitableTemperate / HabitableHot / HabitableCold / HabitableZone / InnerSystem / OuterSystem | Répartition des zones habitables/intérieures/extérieures du système. |
| GenerationParams.SectorsPerLY / RangeLY / RangeAU / RangeKM / CostPerLY / CostPerAU / CostPerKM | Échelles de distances et coûts de warp. |
| GenerationParams.WarpAccept / FuelAccept / O2Accept / MoneyCard / Credits / (noms d'items)... | Ressources acceptées / référencées par la génération (prix, carburant). |

## 2.2 GenerationParams.PlanetTypes / MoonTypes / OrbitTypes / StationTypes / WarpTargetOrbitTypes / POITypes

Chaque type est un bloc `Name:` (clé = nom du type). Clés communes :

| Propriété | Sens |
|---|---|
| Name | Nom du type (clé du bloc). |
| Color | Couleur du corps/secteur sur la carte. |
| Icon | Icône sur la carte (POITypes/StationTypes). |
| Placement | Règle de placement dans le système. |
| Playfields | Liste des playfields candidats pour ce type. |
| PlayfieldLevel | Niveau du playfield généré. |
| HasOrbit | Génère une orbite. |
| HasTerrain | Corps avec terrain (vs station/espace). |
| Faction | Faction propriétaire. |
| FactionAvoid | Factions à éviter au placement. |
| MoonProb (PlanetTypes) | Probabilité d'avoir une lune. |
| MoonType (PlanetTypes) | Type de lune à générer. |
| MoonOrbitType (PlanetTypes) | Type d'orbite de la lune. |
| OrbitType (PlanetTypes) | Type d'orbite de la planète. |
| Climate | Climat (poids de sélection). |
| ForcePlanetType | Force ce type de planète. |
| ForceSizeClass | Force la classe de taille (2..5). |
| Distance | Distance au soleil (OrbitTypes/MoonTypes/StationTypes). |

## 2.3 Paramètres de planète générée (DynamicPlayfieldParams)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| PlanetSize.SizeRange / SizeProbs | — | Plage de tailles et probabilités associées. |
| TemperatureMin / TemperatureMax / TemperatureNight / TemperatureMinMax | — | Plages de températures tirées. |
| TemperatureDay | — | Plage de température de jour. |
| PlanetAxis | — | Axe de rotation tiré. |
| HumidityMin / HumidityMax / HumidityMinMax | — | Plages d'humidité. |
| Radiation | — | Plage de radiation. |
| SeaLevel / TerrainLevel | — | Plages de niveau de mer/terrain. |
| BaseLevel | [0, 511] | Plage du niveau de base. |
| LandWaterRatio | — | Plage du ratio terre/eau. |
| GlobalTemperatureStops | — | Points de rupture de la rampe de température globale. |
| TemperatureHeightRange / TemperatureGradientRange / TemperatureNoiseFac | — | Gradient de température selon altitude + bruit. |
| HumidityHeightFac / HumidityNoiseFac | — | Idem pour l'humidité. |
| Presets | — | Presets de végétation (cf. 1.8). |
| Biomes | — | Biomes (DCClusterData, cf. 1.9). |
| TerrainHeightMapMax | 511 | Hauteur max de heightmap. |
| GroundShapes / TemperatureMasks / HumidityMasks | — | Stamps de relief et masques climatiques. |
| IsStampPlayfield | — | Marque un playfield « à stamps ». |
| GravityMinMax | [0,0] | Plage de gravité. |
| AtmosphereDensityMinMax / AtmosphereO2MinMax | [0,0] | Plages d'atmosphère. |
| Water | — | Types d'eau possibles (liste). |
| Music | — | Musiques possibles (liste). |
| AtmoBreathableProb | — | Probabilité d'atmosphère respirable. |
| WaterProb | — | Probabilité de présence d'eau. |
| GroundFogProb | — | Probabilité de fog au sol. |
| GroundFogIntensityRange / GroundFogHeightRange | [0,0] | Plages du fog au sol. |
| AtmosphereFogRange | [0,0] | Plage du fog d'atmosphère. |
| PvPProb | — | Probabilité PvP du playfield généré. |
| PlayfieldLevelOverride | — | Niveau de playfield imposé [min,max]. |
| BiomeStampTries | 20 | Essais de stamps de biome. |

## 2.4 Espace dynamique (playfield_*space*.yaml → DynamicSpacePlayfieldYaml)

| Propriété | Défaut moteur | Sens |
|---|---|---|
| Gravity | 0 | Gravité (0 en espace). |
| AtmosphereEnabled | True | Atmosphère (fog) rendue. |
| PvPProb | — | Probabilité PvP. |
| UseFixed | — | Référence un playfield fixe à copier. |
| PlayfieldType | Space | Type (Space/Sun). |
| Description / PlanetType / Music / Skybox / SunFlare / Stars / Nebula / Difficulty / TemperatureDay | cf. statique | Idem statique (listes acceptées). |
| Radiation | — | Plage de radiation. |
| AsteroidField | — | Bloc champ d'astéroïdes : Position (PosXZMinMax, PosYMax, PosMultiplier, RadialInfo). |
| Resources[] | — | Astéroïdes-ressources de l'orbite (ResourceDesc) : Name, DisplayName, CountMinMax, Probability, Position (PosXZMinMax, PosYMax, PosMultiplier), Pos, Rot, Properties (Key/Value). `RegenerateAfter` (Value de Properties) = régénération en minutes ; 0/absent/négatif = jamais. |
| POIs[] | — | POIs d'espace (POIDesc) : Type (prefab), Name[], FieldName[], GroupName, DisplayName, CountMinMax, Position, Probability, RadiusMinMax, SpawnResource[], ResourceDistance, POIDistance, SpawnPOINear, BaseField, RandomRotation, InitPower, LevelModMinMax, IsCompoundSubDesc, Compound (CountMinMax, Probability, Name[], DistanceMinMax, Rotate), NoShieldReload, Properties, Mode, SubMode, Pos, Rot, Faction, FactionTerritory, SpaceDefenseOverrideDefaults, SpaceDefenseProbability, SpaceDefensePriceMinMax, FieldNameFogColor. |
| DroneSpawning[] | — | (DroneSpawningDesc) Name[], Faction, Count, Radius, Properties. |
| DroneBaseSetup[] | — | Bases spatiales : FreeDrones (DroneDutyDesc : Name[], Faction, CanNotBeControlledByMasterAI, POINameAsPositionRef[], Count, Radius, Properties), SpaceVessels (Name, Faction, CanNotBeControlledByMasterAI, FixedMaxSpeed, Mission, MissionDescription : DelayBetweenRespawnMinMax, DelayBeforeSelfDestructionMinMax, IsRespawnAfterDestruction, Position (PosXZMinMax, PosYMax, PosMultiplier), POINameAsPositionRef, RadiusMinMax, AvoidArea (POIName, Radius, Duration)), StockDescription (Name, AmountMinMax, ExtraMinMax, Type), CountMinMax, Probability. |
| FixedPlayerStart[] | — | Départs joueur (cf. 1.15). |
| AllowSV/CV/HV/BA + AllowBlueprint* + AllowBPFactory + DenyLeave* + DenyMicroWarp + AllowMaxCPUTier* | cf. 1.2 | Idem statique. |
| LandClaimZone / BaseAttackCount / TraderZone / RestrictToOrigin / Build / PfServerWeight / Instance | cf. statique | Idem statique. |

---

# 3. Sectors.yaml (galaxie : systèmes, secteurs, corps)

Lu par le chargeur de galaxie du moteur ; c'est LE fichier qui place tous
les playfields dans l'espace 3D.

| Clé | Sens |
|---|---|
| GalaxyMode | true = carte galactique multi-systèmes (warp inter-systèmes). |
| Sectors | Liste de secteurs libres « vides » (jamais vide dans RE2-FR : `[]` = aucune). |
| SolarSystems[].Name | Nom du système solaire. |
| SolarSystems[].Coordinates | Position du système dans la galaxie `[x, y, z]` (unités = secteurs). |
| SolarSystems[].StarClass | Classe d'étoile du système (ex. GStartingSystem, K, Sol...). |
| SolarSystems[].HideFromMap | Système masqué sur la carte. |
| SolarSystems[].HideFromSearch | Système introuvable par la recherche. |
| SolarSystems[].Sectors[].Coordinates | Position du secteur dans le système `[x, y, z]`. |
| SolarSystems[].Sectors[].SectorMapType | Icône/role carte : None, Planet, Moon, Station, AsteroidField, WarpTarget, GasGiant, Sun... |
| SolarSystems[].Sectors[].Color | Couleur du marqueur (`'r,g,b : r,g,b : r,g,b'` = dégradé d'atmosphère). |
| SolarSystems[].Sectors[].Deny | Interdit de warp/entrée vers ce secteur (RE2 : zones interdites). |
| SolarSystems[].Sectors[].Playfields | Liste de quintuples `['x, y, z', Nom, Playfield, faction, mod, extra, taille]` : [0] position relative du playfield, [1] nom affiché du corps, [2] dossier du playfield (Playfields/<Playfield>), [3] multiplicateur/force de faction (ex. 'Alien:2') ou '', [4] modificateur de niveau (LevelMod) ou '', [5] couleur de planète (géantes gazeuses) ou classe d'étoile ('K'), [6] taille/échelle du corps ('10'..'12' observés). |

NB : tout playfield référencé ici doit exister dans `Playfields/<nom>/`.
Une entrée de quintuple peut être commentée : le corps n'existe alors pas.

---

# 4. gameoptions.yaml (options de partie du scénario)

Modèle moteur `GameOptionsYamlData.Dataset` — les descriptions ci-dessous
sont la traduction des doc-strings d'Eleon (`[PackageHelper]`). Le premier
dataset dont `ValidFor` correspond aux conditions (Survival/Creative/Freedom/
Debug × SP/MP) est utilisé ; dataset sans `ValidFor` = défaut universel.

| Clé | Défaut moteur | Sens |
|---|---|---|
| Options[].ValidFor | — | Conditions d'application : sous-ensemble de {Survival, Creative, Freedom, Debug} ∪ {SP, MP}. |
| DecayTime | 24 | Heures de jeu avant suppression d'une structure joueur sans cœur ou < 10 blocs non visitée (0 = désactivé). |
| WipeTime | — | Heures de jeu avant suppression de TOUTE structure joueur non visitée (0 = désactivé). |
| ProtectTime | 48 | Durée de la protection hors-ligne (heures temps réel). |
| ProtectDelay | 300 | Délai avant activation de la protection hors-ligne (s temps réel). |
| MaxStructures | 200 | Nombre max de structures par playfield (limite dure 255). |
| AntiGriefDistancePvE | 30 | Distance (m) autour d'une base où une autre faction ne peut pas construire en PvE (0 = désactivé). |
| AntiGriefDistancePvP | 300 | Idem en PvP (recommandé pour éviter le grief pendant l'offline protection). |
| AntiGriefOresDistance | 30 | Distance (m) autour des gisements où aucune base adverse ne peut être posée (0 = désactivé). |
| AntiGriefOresZone | PvE | Playfields où AntiGriefOresDistance s'applique (PvE/PvP/All). |
| EnableTrading | All | Types de commerce autorisés (GlobalVirtual est déprécié). |
| EnableMaxBlockCount | True | Active les limites de blocs (dont MaxCount armes) — garde : (Survival\|Freedom && EnableMaxBlockCount) \|\| ForceMaxCount. |
| EnableVolumeWeight | False | Active volume/poids. |
| EnableCPUPoints | False | Active le système CPU (expérimental Eleon). |
| EnableUnlockCheckInBPF | True | Vérifie le déblocage dans la factory de blueprint. |
| AutoMinerDepletion | True | Les automineurs épuisent les gisements. |
| GroundedStructureSpawn | True | Les blueprints SV/BA doivent être posés au sol. |
| TurretUndergroundCheck | — | Désactive les tourelles posées sous le terrain/eau. |
| OriginDefault | "Neutral" | Origin par défaut. |
| OriginAccessOthers | True | Autorise les alliances/jointures entre Origins. |
| OriginAutoAlliance | True | Factions alliées par défaut dans le même Origin. |
| FriendlyFireInPvP | True | False = les alliés ne s'endommagent pas (structures) même en PvP. |
| PlayerSafeZoneHours | — (YamlIgnore) | Heures de jeu sans spawn d'ennemis (déprécié). |
| MaxSpawnedEnemies | 50 | Nombre max de PNJ autour d'un joueur. |
| DespawnEscapePod | — | Si false, la capsule ne despawn pas (dormir la nuit en SP). |
| RegeneratePOIs | — | true = autorise la régénération des POI (commande console `regenerate`). |
| FOWTransparency | — | Transparence du brouillard de guerre (0..100). |
| DSLUnloadSecs | 30 | Délai avant déchargement d'une structure sans joueur (0 = désactivé). |
| DSLDistancePlanet | 1200 (min 600) | Distance d'invisibilité/déchargement d'une structure au sol. |
| DSLDistanceSpace | 3000 (min 1500) | Idem en espace. |
| ForcePvP | — | Force PvP partout. |
| OriginFactionStart | — | Le joueur rejoint une faction d'Origin par défaut (coop). |
| IsManagedScenario | — | Scénario « managé » (scores, stats, timers). |
| ThrustersNeedOpenSpace | — | Un propulseur exige de l'espace libre derrière lui. |
| DisableProximityLog | — | Désactive le bouton de log de proximité dans le registre. |
| UndergroundBpSpawn | Always | Permission de spawn de blueprint sous le terrain. |
| CustomPlayerTab | — | Onglet personnalisé du menu joueur (URL). |
| ClientPrivacy | True | Réglages de confidentialité client. |
| EnableDecoKnockDown | True | Les décors peuvent être renversés. |
| GameSpecialScenarioType | "Standard" | Id de scénario spécial. |
| SuppressFreshStartRespawn | — | Supprime l'option « Fresh Start » au respawn. |
| DiffEscapePodContent | Medium | Contenu de départ (Easy/Normal/Hard). |
| DiffPlayerProgression | Normal | Vitesse de progression (XP). |
| DiffDegradationSpeed | Normal | Vitesse d'usure des outils/armes. |
| DiffPlayerBackpackDrop | DropEverything | Mode de drop du sac à la mort. |
| DiffSpawnLocal | Always | Affiche « Spawn Local » à la mort. |
| DiffFoodConsumption | Normal | Vitesse de consommation de nourriture. |
| DiffOxygenConsumption | Normal | Vitesse de consommation d'O2. |
| DiffRadiationTemperature | Normal | Impact température/radiation. |
| DiffAmountOfOre | Normal | Quantité de minerai par gisement. |
| DiffNumberOfDeposits | Normal | Nombre de gisements par planète. |
| DiffAttackStrength | Medium | Difficulté des ennemis. |
| DiffEnemySpawnRate | Normal (YamlIgnore) | Taux de spawn des PNJ planétaires. |
| DiffDronePresence | Normal | Nombre de drones présents. |
| DiffDroneBaseAttack | Normal | Fréquence des attaques de base. |
| DiffConstrCraftTime | Normal | Vitesse de craft des constructeurs. |
| DiffBpProdTime | Normal | Vitesse de la factory de blueprint et du repair bay. |

RE2-FR : 4 datasets (Survival/MP, Survival/SP, Creative/MP, Creative/SP),
`EnableMaxBlockCount: True` dans les 4.

## 4.1 SharedData/Content/Extras/LoadingScreenshots/LoadingScreenConfig.yaml

Écran de chargement personnalisé du scénario (exemple de RE2-FR) :

| Clé | Sens |
|---|---|
| Title | Titre superposé (balises rich-text Unity `<b>`, `<size>`, `<#rrggbb>`, `<indent>`). |
| Body | Corps de texte multi-lignes (syntaxe bloc YAML ; mêmes balises). |
| FirstPic | Première image imposée de la séquence (nom sans extension, .jpg ajouté). |
| ShowWith | Liste d'images avec lesquelles afficher le texte (déf. toutes). |
| StandardShowTime | Durée d'affichage de chaque image (s ; défaut moteur 10). |
| ShowTimes | Durées spécifiques par image (`nom: secondes`). |

---

# 5. Fichiers ECF — Content/Configuration/

Les ECF sont des blocs `{ Type Id: N, Name: X ... }` suivis de propriétés,
fermés par `}`. Un `+` devant le type (`{ +Item Id: 2 ...`) = patch de la
config de base (le moteur réapplique les patchs vanilla puis du scénario) ;
un bloc scénario SANS `+` REMPLACE la déclaration vanilla équivalente.
Les clés inconnues sont ignorées silencieusement (jamais de crash).

Familles numérotées : les clés suffixées `_N` / `N` (Item_1..N, Option_1..N,
Variable_N, SlotN, MeshN, Group_N, Name_N, DamageMultiplier_N,
BlastDamageMultiplier_N, AITask-N, AITarget-N, StarClass_N, NebulaColorsN,
Focused_blockname_N, Mesh-Damage-N) sont des TABLEAUX : le glossaire les
documente une fois sous leur forme familiale.

## 5.0 Propriétés communes (tous ECF)

| Propriété | Sens |
|---|---|
| Name / Name_N | Nom d'affichage ou d'identification (Name_N = noms multiples d'un même objet). |
| Id | Identifiant numérique (espace d'ids SÉPARÉ blocs/items : un Block Id 978 et un Item Id 978 coexistent). |
| Class | Famille fonctionnelle (Item : Ranged, LauncherSS, melee... ; Block : Hull, Device...). |
| Category | Catégorie d'inventaire/construction (Ingredients, Components, Weapons...). |
| EssentialCategory | Catégorie « essentielle » (données de survie). |
| Info | Texte d'info multi-lignes affiché dans le jeu (description détaillée). |
| Description | Description courte (StatusEffects, Factions, Tokens). |
| CustomIcon | Utilise l'icône d'un autre item/block. |
| MarketPrice | Prix unitaire de référence (stations de commerce ; l'item au meilleur coût/contenu est choisi automatiquement pour un même usage). |
| Mass / Volume | Masse (kg) / volume (L) — actifs si EnableVolumeWeight. |
| ShowUser | Affiche le nom de l'objet à l'utilisateur (HUD). |
| TechTreeParent / TechTreeNames | Arbre technologique : parent + liste des noms de nœuds. |
| UnlockLevel / UnlockCost | Niveau joueur et crédits de déblocage. |
| IsDuplicateable | Dupliquable en factory de blueprint. |
| AllowedInBlueprint | Autorisé dans les blueprints. |
| AllowAt | Restriction d'usage : NoPvP / NoPvE. |
| AllowPlacingAt | Placement autorisé : NoPvP / NoPvE / zones (hérite GlobalDefsConfig). |
| AllowRemote | Utilisable depuis un drone joueur. |
| BaseItem | true = matière de base sans template (le Deconstructor ne décompose pas plus loin). |
| GlobalRef | Référence globale à un autre objet. |
| DropMeshfile | Modèle 3D de l'objet posé au sol. |
| Meshfile / Mesh / MeshN | Modèle(s) 3D. |
| Mesh-Damage-1..4 | Modèles d'états endommagés (niveau 1 à 4). |
| DropOnDeath | false = l'objet n'est pas lâché à la mort du joueur (objets de quête). |
| LifetimeOnDrop | Durée de vie au sol en secondes (déf. 200). Ne pas augmenter sans raison (perf). |
| PickupToToolbar | Ramassage direct dans la barre d'outils. |
| Candrop | Peut être lâché. |
| CustomIcon / Icon / MapIcon / MapName / LabelName / LabelColor / LabelSize | Icônes et libellés (carte, HUD). |
| Sound / SoundOpen / SoundClose / SoundRotate / SoundOnEnter / CastSound | Sons. |
| XpFactor | Multiplicateur d'XP. |
| RpFactor / RPFactor / ReturnFactor | Facteurs de réputation/retour. |
| Discovery / DiscoveryFac | Élément découvert (code) ; Facteur de découverte (télécommande/scan). |
| Color_N / RGB_N / Saturation_N | Variantes multiples (tableaux de couleurs/saturations, ex. TextureTable). |

## 5.1 BlocksConfig.ecf (blocs)

| Propriété | Sens |
|---|---|
| Id | Id du bloc (espace séparé des items). |
| Name | Nom du bloc (clé de référence par Templates/Containers/POIs). |
| Class | Type de bloc : Hull*, Device, Decoration, Terrain (roche), Plant... |
| Category | Onglet du constructeur. |
| Mass / Volume | Masse (kg) et volume (L) par bloc. |
| HitPoints / MaxHealth | Points de vie du bloc (HitPoints ; MaxHealth pour entités). |
| RepairToTemplate | Template utilisé par Réparer-2-Template. |
| RepairCount / RepairPoints / RepairPerSecond | Coût/vitesse de réparation. |
| RepairDisabled / NoRepairInputItem | Réparation interdite / sans objet en entrée. |
| IsRepairToBlueprint | Variante R2T. |
| UpgradeTo / DowngradeTo / AllowDowngrade | Bloc d'upgrade / downgrade cible. |
| SfxUpgrade / SfxUpgradeErr / SfxDowngrade | Sons d'upgrade. |
| TemplateRoot | Racine de template (famille de blocs partageant le template — remonte aux ChildBlocks). |
| ChildBlocks / ChildShapes | Blocs/shapes enfants (la famille remonte pour MaxCount). |
| ParentBlocks | Blocs parents. |
| Shape | Shape physique (fichier .shape). |
| Model | Modèle 3D. |
| IsOxygenTight | Bloc étanche à l'oxygène. |
| IsDeco | Bloc décoratif (ramassable, cassable facilement). |
| IsTerrainDecoration | Décor de terrain (le Deconstructor/casse le terrain). |
| CanPickup / PickupTarget / PickupToToolbar | Ramassage (vers quel bloc). |
| CanDecorateOnSlopes / RotateToGround / RotateSpeed / RotSpeed | Pose sur pentes et rotation. |
| IsColorable / CanSetColor / BlockColor | Colorabilité (couleur par défaut). |
| IsTextureable / Texture / TextureTable | Texturabilité (table de textures). |
| IsGPUInstance | Rendu instancié GPU (perf). |
| BigDecorationRadius | Rayon de « gros décor » (grands props). |
| IsActivateable / IsActivateableInCP / IsActivatedOnPlace | Bloc activable (et depuis le panneau de contrôle) / activé à la pose. |
| IsLockable / IsAccessible | Verrouillable / accessible. |
| CanPlayersSpawnOn / PlayerStart | Point de spawn joueur autorisé. |
| AllowPlacingAt | Contrainte de placement. |
| CheckObstructed / AboveTerrainCheck / Voxelize / OccupySizeInBlocks | Contrôles de pose (obstruction, au-dessus du terrain, voxélisation, taille occupée). |
| SizeInBlocks / SizeInBlocksLocked / BlockSizeScale | Taille en blocs (et verrouillage d'échelle). |
| SymType | Symétrie (None, Mirror, Rotate...). |
| Collide | Collision activée. |
| Transparent / Turbidity / TurbidityColor / WaterColor / Specular | Rendu vitre/eau (transparence, turbidité, couleur d'eau, spéculaire). |
| IsPhysicsColliders / StabilitySupport / StepHeight | Colliders physiques, support de stabilité, hauteur de marche. |
| IsTrapDoor / IsRetractable / MirrorTo / PanelAngle / DoorClosesOnPower / PlayerTriggersOpen / DialogueState / DialogueSingleUserAccess | Portes/trappes/panneaux interactifs (états, déclencheurs, dialogues). |
| IndexName | Nom d'index (sélection de variante). |
| ShowBlockName / ShowUser | Affichage du nom (HUD/copy-paste). |
| Info | Description multi-lignes. |
| MaxCount | Limite de blocs PAR STRUCTURE (tête de famille via TemplateRoot/ChildBlocks) ; actif si (Survival\|Freedom && EnableMaxBlockCount) \|\| ForceMaxCount. |
| ForceMaxCount | Force la limite même hors garde vanilla. |
| AllowedInBlueprint / IsDuplicateable | cf. communes. |
| BlastDamage / BlastRadius / BlastParticleIndex / BlastParticleName / BlastShieldDamage / BlastShieldDamagePenFac | Dégâts d'explosion du bloc (charge) : rayon, particules, dégâts bouclier. |
| BlastDamageMultiplier_1..8 / DamageMultiplier_1..10 / DamageMultiplier_Group | Multiplicateurs de dégâts par catégorie de munition (index = id de catégorie). |
| ExplosionHardness / Hardness | Résistance à l'explosion / à l'outil. |
| EnergyIn / EnergyInIdle / EnergyOut | Consommation/production énergétique (idle = veille). |
| CPUIn / CPUOut | Coût CPU (si EnableCPUPoints). |
| ThrusterForce / ThrusterBoosterFactor / IsBlocksThrusters / HVEngineForce / HVEngineDampCoef / HVEngineDampPow | Propulsion (poussée, booster, moteurs HV). |
| Coûts de construction/réparation | Noms d'INGRÉDIENTS en clés : SteelPlate, SteelPlateArmored, TitanPlates, GlassPlate, PlasticMaterial, Electronics, Computer, Motor, CannonBase... (ex. `SteelPlate: 4`) — c'est la base des coûts de craft/réparation des blocs. |
| EnergyDynamicGroup | Groupe énergétique dynamique (blocs partageant leur énergie). |
| GridSize | Taille de grille (multi-tailles de blocs). |
| IsUsingCPUSystem | Le bloc est soumis au système CPU. |
| UseCockpitCamera / HideShapesWindow | Caméra cockpit / masquage de la fenêtre de shapes. |
| SpawnClass | Classe de spawn (utilisée par les spawners). |
| RepFac | Facteur de réputation (réduction de perte). |
| Repairs / ForceNoPvEDamage / ForceSpawnOnGround | Nombre de réparations possibles ; aucun dégât PvE ; spawn forcé au sol. |
| Torque / RotSpeed / RotateSpeedMovement | Rotation (RCS, ailerons). |
| GravityGeneratorRadius / ShieldCapacity / ShieldRecharge / ShieldCooldown / ShieldHitCooldown / ShieldPerCrystal / ShieldMultiplier / ShieldCapacityBonus / ShieldRechargeBonus / ShieldDamagePenFac | Générateur de gravité et blocs de bouclier (capacité, recharge, cooldowns, bonus, pénalisation). |
| AmmoType / AmmoCapacity / ReloadDelay / ROF / Range / RangeSpace / Damage / Homing / MicroWarpCooldown | Armes montées (type de munition, cadence, portée sol/espace, dégâts, autoguidage). |
| TurretTargetIgnore / TurretRadar / SensorType / ScanElevation / ScanWater | Tourelles : cibles ignorées, radar, capteurs d'élévation/eau. |
| JumpgateDiameter / JumpgateBaseScale / JumpgateEffectEnabled / OmitCone / VisibleDistance | Portails (dimensions, effet, visibilité). |
| Teleporter / TeleportCooldown | (variante) téléporteur. |
| SolarPanelEfficiency / IsSolarPanel | Panneaux solaires. |
| FuelAccept / FuelCapacity / FuelValue / WarpAccept / O2Accept / O2Capacity / O2Value / ConsumeFuelO2 | Carburants/gaz acceptés et capacités (hydrogène, pentaxid, O2). |
| ItemsPerHour / ItemStorageLimit / ItemPerAU / VolumeCapacity / MaxVolumeCapacity | Génération/stockage d'items (mining, O2, stockage). |
| AutoMinerFactor / AutoMinerCore / MiningEnabled | Automineurs. |
| CropType / CropYield / GrowthRate / GrowthTimeInfo / FertileLevel / fertile_level / IsPlant / DontDecayFood / FoodDecayTime / FoodDecayedItem | Agriculture et périssables. |
| OnDeath / OnHarvest / ParticleName / ParticleOnDeath / ParticleOffset / DecoParticle / SpawnParticle / SpawnParticleNodeName / SpawnSfx / DestroyBlock | Effets et harvest à la destruction. |
| OnHarvest (drops) / DropOnDestroy_N / DropInventoryEntity / DropInventoryItem / LootList / LootListOnDeath | Loot (listes). |
| SfxActivate / SfxBuffActivate / Sound / SoundOpen / SoundClose / SoundRotate | Sons. |
| CostPerAU/KM/LY / RangeAU/KM/LY / Mod.RangeLY | Radar/warp drive (portées et coûts). |
| Radiation / AddRadiation / Temperature / AddTemperature / TemperatureGain / Heat / Cold / IsIgnoreLC | Climat émis par le bloc (radiation, température) et interaction land claim. |
| IsEnemy / Faction / TraderEntity / TraderType / NPCName / NPCModelRotation / CModelRotation | Blocs-PNJ et marchands. |
| DrillMode / DrillAttachment / MeleeWeaponIndex / RangedWeaponIndex / WeaponItem / WeaponItemRotation / YawRotation / CameraShake / Zoom / ZoomIn / ZoomOut / ZoomOverlay / RedDot / Crosshair / IsShootThroughCrosshair / PfxMuzzle / Tracer* / Recoil* / BulletSpread / RaySpread / BulletsPerShot / Bullet_use_per_shot / UseSingleMagazine / AmmoUnlimited / Automatic / AutoReload / HoldType | Armes portatives et viseurs (cf. ItemsConfig, mêmes sens). |
| HUD/Audio divers : HudInfo, SfxLoop, SfxBegin, SfxReload, SfxNoAmmo, SfxStop, SfxDeath, SfxHurt, SfxJammed, SfxRandom, SfxRandomTime, SfxAnimationEvent0/1 | Sons d'animation/arme. |
| ExplosionHardness (voir haut), DeconOverride (voir Templates), ClusterScale (voir playfield) | |
| ADB* (ADBActionRadius, ADBDockingSpeedFac, ADBDroneAmmoType, ADBDroneType, ADBMaxActiveDrone, ADBMaxReserve, ADBMaxSpawner) | Advanced Drone Bay : rayon d'action, vitesse d'amarrage, munitions/type de drones, max actifs/réserve/spawner. |
| ElevMinMax | Plage d'élévation (portes). |
| IsDestructible / Demolish / RemoveOnSI / RemoveOnUse / DestroyOnClose / DestroyBlock / CollapseIfUnsupported | Destruction/déconstruction. |
| PlanetType / SurfaceCategory / surface_category | Catégories de surface (bruit de pas, impact). |
| createslight / CreatesLight / Luminosity / LightColor / FadingEnabled / LightRange / LightIntensity | Éclairage émis. |
| WindSpeed / Turbulence | Interaction vent. |
| DepositName / ResourceMining | (mineurs) nom du gisement. |
| TerrainId / TerrainId2 / UnderTerrainId / Name2 | Variantes de terrain (blocs de terrain multi-états). |
| OpenContainer / IsKeepContainers / IsLockable | Conteneurs ouverts au spawn. |
| CropYield / OnHarvest | cf. agriculture. |
| EraVariants / VariantOf | (RE2) variantes de blocs. |

## 5.2 ItemsConfig.ecf (objets/inventaire)

Armes : la classe définit le modèle de dégâts.
- `Class: Ranged` → les dégâts viennent de l'arme ; la munition ne porte que masse/volume/coût.
- `Class: LauncherSS` → dégâts ET BlastDamage viennent de la munition (bloc enfant `Class: Projectile`) ; BlastDamage s'ajoute à la base pour le bloc du CENTRE uniquement : `(Damage + BlastDamage) - (BlastDamage / BlastRadius)`.

| Propriété | Sens |
|---|---|
| Id / Name / Ref | Id, nom, et Ref = item parent (hérite des propriétés non redéclarées). |
| Class | Ranged, LauncherSS, Melee, Tool, etc. |
| Category / EssentialCategory | cf. communes (Food et Medical exigent FoodP + SurvC ; Weapons/Components exigent SurvC..AdvC). |
| HoldType | Animation de port : 0 non défini, 14 pistolet, 15 fusil, 16 fusil + tir faible (Survival Tool, Multitool, Drill), 17 arc, 20 mêlée. |
| Damage | Dégâts de base (arme) ou par munition (Projectile). |
| DamageMultiplier_1..N / DamageMultiplier_Group | Multiplicateurs par catégorie de bloc cible. |
| BlastDamage / BlastRadius / BlastDamageMultiplier_N | Dégâts d'explosion (cf. formule ci-dessus). |
| BlastShieldDamage / BlastShieldDamagePenFac | Dégâts aux boucliers. |
| ShieldDamagePenFac | Pénetration du bouclier. |
| Range / RangeSpace | Portée au sol / en espace. |
| ROF | Cadence (coups/s ; les Sfx doivent durer plus court). |
| ReloadDelay / AutoReload / UseSingleMagazine / AmmoUnlimited | Rechargement. |
| AmmoCapacity | Chargeur (max 500 tourelles/armes montées). |
| AmmoType / Bullet_use_per_shot / BulletsPerShot / RaySpread / BulletSpread | Munitions et dispersion. |
| Durability | Durabilité (max 5000 armes portatives) ; DurabilityBreaksAfter = usure. |
| DegradationProb / DegradationFac / RepairCount / RepairPoints / RepairDisabled / NoRepairInputItem | Usure et réparation des outils. |
| Mod.Damage / Mod.BlastDamage / Mod.Recoil / Mod.ReloadDelay / Mod.BulletSpread / Mod.RangeLY | Modificateurs appliqués quand l'item sert de MOD (kit d'upgrade). |
| UpgradeTo / AdvancedUpgradeKit / SmallUpgradeKit / LargeUpgradeKit / LaserKit / HeavyWeaponKit / PistolKit / RifleKit / ShotgunKit / SniperKit / AllowUpgrade | Kits d'upgrade d'armes (T1→T2...). |
| DrillMode / DrillAttachment / HarvestSupport / MiningEnabled | Modes du foret (dégât/collecte). |
| TerrainMode / FlattenTerrain / TerrainFillerBlock | Outils de terrain (filler/flattening). |
| Automatic / Recoil / RecoilLocation / RecoilRotation / CameraShake / ForceMuzzleAiming / IsShootThroughCrosshair | Tir (recul, camera, viseur). |
| Tracer / TracerPerBullet / TracerIsBeam / TracerSpeed | Traceurs. |
| PfxMuzzle / Particles / ParticleTransform / ParticleOffset / DecalGroup / DecalMode / DecoMode | Effets de tir/impact. |
| Crosshair / Zoom / ZoomIn / ZoomOut / ZoomOverlay / RedDot / ScopeOverlay | Viseurs. |
| SfxBegin / SfxLoop / SfxReload / SfxNoAmmo / SfxStop / SfxJammed / SfxHurt / SfxDeath / SfxStamina / SfxRandom / SfxRandomTime / SfxAnimationEvent0/1 / SfxDowngrade / SfxUpgrade / SfxUpgradeErr / SfxAlert / SfxAlertTime | Sons (durée SfxBegin > ROF pour les automatiques). |
| MeleeAttackDistance / IsRanged / IsAntiInfantryWeapon / MaxFireAngle / Homing / HomingSpeed / AttackType | Combat rapproché/missiles. |
| AmmoType (projectile) : Damage, BlastDamage... définis dans l'enfant `Class: Projectile` | |
| StackSize / Canhold / ItemsOnEnterGame | Empilage, portage, items donnés à l'entrée en jeu. |
| AddFood / AddHealth / AddOxygen / AddStamina / AddTemperature / AddRadiation / Oxygen / Radiation / Heat / Cold | Consommables (nourriture, soin, O2, stamina, climat). |
| Buff / Buff_chance / BuffMod / Debuff / DebuffIf / BuffIf / BuffNameActivate / BuffNamesActivate / DebuffNamesActivate / OnExpired / OnExpiredSound / OnDebuffSound / RemoveOnUse | Effets de statut. Format BuffMod : `"StatusID, DuréeFactor, ValeurFactor, PreventsOnExpired(true/false)"` — DuréeFactor modifie la durée active (0 = inchangé), ValeurFactor modifie l'intensité de tous les effets (même calcul), PreventsOnExpired=true annule les effets d'expiration (ex. Pansement empêche la Sepsis quand la Plaie infectée expire). |
| SlotItems / NrSlots / Armor / Oxygen / Radiation / Heat / Cold / PowerFac / SpeedFac / StaminaFac / JetpackFac / JumpFac / PiercingFac / FoodFac / FallDamageFac / RadiationImmunityShot | Armures et boosters : les boosters DOIVENT être dans SlotItems de l'armure (max 15 entrées — attention : modifier SlotItems change tous les boosts des sauvegardes existantes, qui ne stockent qu'un index). Fac = multiplicateurs d'attributs (jetpack : sans armure 2.5/tick, avec 5×JetpackFac ; stamina : base 20/s en course ; food : base 70 min ; PiercingFac exige `isPiercing: true` dans StatusEffects.ecf). |
| IsNightVisionItem / IsOreScannerItem / IsRadarItem / IsEquippableWithoutLocker / IsKeepContainers | Casques spéciaux/scanner/radar. |
| Focused_blockname_1..N | Listes de blocs ciblés par les scanners (nom de bloc par index). |
| O2Value / O2Content / O2Capacity / FuelValue / FuelCapacity | Contenus (bouteilles, bidons). |
| FoodDecayTime / FoodDecayedItem / DontDecayFood | Périssables. |
| LifetimeOnDrop / DropOnDeath / Candrop / DropMeshfile / PickupToToolbar / ItemOnPickup | cf. communes. |
| CanPickup / PickupTarget | Ramassage d'items au sol. |
| Marketplace : SellingGoods / SellingText / Discount / OverrideTradingConstraints / Lvl1MinPrice..Lvl10MaxPrice / SDPriceMin..SDProbabilityMax / SDScenarioGroup | Commerçants (offres, texte, remises par réputation, prix de corruption spatiale). |
| RadialMenu / RadialDesc / RadialIcon / RadialText | Menus radiaux (multitool...). |
| AimingLocation / AimingRotation / CrouchingLocation/Rotation / RunningLocation/Rotation / StandingLocation/Rotation / WalkMovement / RunMovement / RecoilLocation/Rotation / HeadTransform / ParticleTransform | Positions/poses du modèle à la main (IK). |
| Meshfile / Mesh / MeshFP (first person) / MeshHelmet / Model / ModelType / ModelOffset / ModelScaleLocked | Modèles 3D. |
| HeadTransform etc. cf. EClass. | |
| HoldType (voir haut), AmmoUnlimited, AutoFill (remplissage auto), AutoReload | |
| Entity / EntityName / PrefabEntity / PropHead | Variante entité/objet posé. |
| IsSolarPanel / SolarPanelEfficiency | (variante item). |
| RecipeName / CraftTime (via Templates) | Nom de recette. |
| SpeedSpace | Vitesse du projectile en espace. |
| Speed | Vitesse du projectile. |
| Ballistic | Munition balistique (physique vs énergie). |
| PenetrationDepth | Profondeur de pénétration (perforation de blocs). |
| AllowSpace | Utilisable dans l'espace. |
| IgnoreAtmo | Fonctionne sans atmosphère (espace). |
| RadiationShielding / RadiationImmunityShot | Protection/immunisation contre les radiations. |
| ShowObjectTime / InfoPopup / OpenPopup | Popups temporisés. |
| Credits / MoneyCard / GoldCoins (items) | Devises. |
| XpFactor / RpFactor | cf. communes. |

## 5.3 Templates.ecf (recettes)

Structure d'un template :
```
{ Template Name: X          # ou { +Template Name: X } = patch base
  BaseItem: true            # matière de base (pas de décomposition au-delà)
  CraftTime: 10             # secondes
  OutputCount: 2            # quantité produite
  Target: "SurvC,SmallC,HoverC,BaseC,LargeC,AdvC"   # constructeurs où visible
  DeconOverride: Continue   # comportement au Deconstructor
  TemplateRoot: X           # racine de famille (repair)
  { Child Inputs            # ingrédients : Nom: quantité
    IronIngot: 5
  }
  { Outputs                 # sorties multiples optionnelles
    Output: Item, Count: N
  }
}
```

| Propriété | Sens |
|---|---|
| Template Name | Nom du template = nom de l'item produit (clé). |
| BaseItem | true = matière de base, jamais décomposée par le Deconstructor (même si flag posé, la R2T ne l'utilise pas si NoRepairInputItem). |
| CraftTime | Durée de fabrication (s). |
| OutputCount | Quantité produite par craft. |
| Target | Constructeurs où la recette est visible : SurvC, SmallC, HoverC, BaseC, LargeC, AdvC, Deconstructor. `Target: ""` se lit AVEC les guillemets ('""' = non vide → visible UNIQUEMENT du Deconstructor). |
| DeconOverride | Comportement du Deconstructor : Continue (continue à décomposer), Stop, Hide. |
| TemplateRoot | Racine de la famille de blocs (repair R2T ; remonte aux ChildBlocks pour MaxCount). |
| Child Inputs | Bloc d'ingrédients `NomItem: quantité` (les recettes cachées de l'auteur ne doivent jamais être touchées — `generated_names()` ne lit que la section marquée). |
| Outputs / Output / Count | Sorties multiples. |
| RepairToTemplate / IsRepairToBlueprint / RepairCount / RepairPoints / RepairPerSecond / RepairDisabled / NoRepairInputItem | Réparation R2T. |
| Next_N / NextIf_N / Option_N / OptionIf_N / OptionExecute_N / OptionNext_N / Variable_N | Variantes conditionnelles de recettes (même moteur de scripting que Dialogues, cf. 5.11). |
| UpgradeTo | Recette d'upgrade. |

## 5.4 BlockGroupsConfig.ecf (budgets de groupes)

| Propriété | Sens |
|---|---|
| Blocks | Liste de blocs du groupe (remontée par familles pour MaxCount). |
| MaxCount | Budget du groupe nommé (limite PAR STRUCTURE du total du groupe) ; complément des MaxCount par tête de famille ; les 6 familles d'armes CV sans MaxCount ne sont limitées QUE par leurs budgets de groupe. |

## 5.5 Containers.ecf (conteneurs prédéfinis)

| Propriété | Sens |
|---|---|
| Container Id / Name_N | Id et liste de noms du conteneur. |
| Size | Taille (slots). |
| Count | Nombre de conteneurs de ce type à remplir. |
| Group_N / Name_N | Groupes/noms d'items placés. |
| SfxOpen / SfxClose / DestroyOnClose | Sons et destruction à la fermeture. |

## 5.6 LootGroups.ecf (loot)

| Propriété | Sens |
|---|---|
| LootGroup Id / Name | Id/nom du groupe de loot. |
| Item_N | Items du groupe : `Item_1: "Nom, Prob: x, MinMax: [a,b]"` (probabilité + plage de quantité). |
| Count | Nombre d'items tirés. |

## 5.7 Factions.ecf (factions)

| Propriété | Sens |
|---|---|
| Id / Name / Abbrev / HideAbbrev | Id, nom, abréviation (affichée ou masquée). |
| Color | Couleur de la faction (carte/HUD). |
| Description | Description. |
| Reputation | Réputation initiale. |
| Friendly / Unfriendly / FriendlyToPlayers / ForceAttack | Relations initiales. |
| Discovery / OmitMapLegend | Découverte / légende carte. |
| ClaimTerritory | Revendique les territoires. |
| NPC | Faction PNJ. |

## 5.8 DefReputation.ecf (actions de réputation)

| Propriété | Sens |
|---|---|
| (factions en clés : ARC, Abyssal, Colonists, Epsilon, Farr, Ghyst, Pirates, Polaris, Rados, Serdu, Talon, Tesch, Trader, Wastelanders, Xenu, Zirax, Eden_Defender...) | Factions RE2 concernées par chaque règle. |
| Order | Ordre d'application de la règle. |
| AttackedMember / KilledMember / AttackedPredator / AttackedPrey / ShieldAttacked / DestroyBlock / PlantDestroy / PlantHarvest / OreMined / OpenContainer / StructSpawnedInTerritory / StructStayInTerritory / OutsideHostileTerritory | Événements qui modifient la réputation (attaque, meurtre, minage, pillage, construction en territoire...). |

## 5.9 FactionWarfare.ecf (guerre de factions / points de commandement)

| Propriété | Sens |
|---|---|
| ID / Name / Category / ClassName | Règle de warfare. |
| Faction / IsInGroups / UsageType | Faction et usage. |
| AttackType | Type d'attaque (aérienne, terrestre...). |
| CommandPointsLvl1 / CommandPointsPerLevel | Points de commandement par niveau. |
| CountLvl1 / CountPerLevel / MinCount / MaxLevel / LevelOnLvl1 / LevelPerParentLevel | Progression du spawn d'unités. |
| OptimalCount / RequestedUnitStrengthMultiplier / MinimalBaseStrength / TargetBaseStrengthToPriceMultiplier | Force des unités demandées et prix. |
| PlayFieldLvl1Min/Max, PlayFieldLvl5Min/Max, PlayFieldLvl10Min/Max | Plages par niveau de playfield. |
| HoursAtRep0 / HoursAtRepMax / HoursAtPlayfieldLvl1 / HoursAtPlayfieldLvlMax | Durées selon réputation/niveau. |
| Lvl1MinPrice..Lvl10MaxPrice / MaxPriceMultiplier | Prix de corruption par réputation. |
| SDPriceMin/Max, SDProbabilityMin/Max, SDScenarioGroup, ScenarioGroup | Défenses spatiales (prix, probabilité, groupe de scénario). |
| EnableSpaceDefense / EnableSpaceDefenseLog | Défenses spatiales activées. |
| PlayerAttackMaxCountFrequencySpawned / PlayerAttackMaxCountPOISpawned | Limites d'attaques joueur. |

## 5.10 GalaxyConfig.ecf (galaxie, étoiles, nébuleuses)

| Propriété | Sens |
|---|---|
| Name / Description / GalaxyMode | Définitions de la galaxie. |
| GalaxySpawnAmount / GalaxySpawnRadius / SectorsPerLY / HabitableZone / HabitableTemperate / HabitableHot / HabitableCold / InnerSystem / OuterSystem | Paramètres de génération galactique (zones habitables, systèmes). |
| StarClass / StarClass_1..N / CompanionStarClass / UseDefaultStarDef | Classes d'étoiles (température, planètes permises, compagnon). |
| Age / Mass / Radius / SurfaceTemperature / SizeClass / Shape / Color / ColorName / LightColor / Luminosity / Model / ModelBrightness / ModelColor / ModelColor2 / ModelCoronaSpikesSize / ModelFlareBrightness / ModelNoiseTiling / ModelPlasmaArcsSize | Physique et rendu des étoiles. |
| NebulaColors1..27 / NebulaColorIndex / NebulaCount / NebulaSpawnCount | Palettes et densités de nébuleuses. |
| Center / Position / Probability / Radius / RadiusMinMax / FlattenFac / ClusterProb / ClusterRange / TotalSpawnCount / Other_1..N | Placement des étoiles (centre galactique, probabilités, aplatissement, clusters). |
| LabelName / LabelColor / LabelSize | Étiquettes de la carte galactique. |
| Faction / HideFromMap / HideFromSearch | Contrôle d'accès. |
| SolarSystemConfigSuffix / StarterSystemName / StarterSystemStarClass / StarterSystemLYCoord | Config de système et système de départ. |

## 5.11 EClassConfig.ecf (classes d'entités PNJ/monstres)

Structure : `{ Entity Name: Zirax` (+ sous-blocs `{ Child 0 ... }` pour les
sensors/behaviors). Clés principales :

| Propriété | Sens |
|---|---|
| Entity Name / Class / EntityType / EntityClass | Nom et type d'entité (EntityType : Animal, Human, Alien, Robot, Bird, Bug...). |
| Parent | Classe parente (héritage des propriétés). |
| Faction / IsEnemy | Faction, hostilité. |
| MaxHealth / HitPoints | Vie. |
| Mass / Weight | Masse. |
| Mesh / MeshDead / MeshN / MeshFP / MeshHelmet | Modèles (vivant, mort, variantes, vue 1re personne). |
| ModelType / Material / BlockColor / BlockName / SurfaceCategory | Rendu/matériau. |
| Prefab / POIType | Prefab associé (drônes de base...). |
| Speed / SpeedCalm / SpeedAlerted / SpeedAttack / SpeedFlee / SpeedCircle / WanderSpeed / NightWanderSpeed / ApproachSpeed / NightApproachSpeed / PanicSpeed / JumpHeight / StepHeight | Vitesse par état (calme, alerté, attaque, fuite) et mobilité. |
| AllowWander / LifeCycleWandering / NavigateInWater / NavigateBreakDoors / IsAmphibian / AllowInSpawners / AllowUserInstantiate | Comportements de déplacement/instance. |
| ViewRange / ViewAngle / VisibleDistance / VisibleTypes / VisibleSubTypes / TargetableTypes / AttackableTypes / SensorType / ScanElevation / ScanWater | Perception (portée, angle, types visés). |
| AITask-N / AITarget-N | Tâches d'IA et cibles (indexées : Idle, Wander, Chase, Attack, Flee, Return...). |
| BehaviorName / MainBehavior | Script de comportement. |
| AlertLevel1/2/3 / AlertLevelDrop / AlertLevel2SwithToOnDmg(+IncludeGroup) / AlertLevel3SwithToOnDmg(+IncludeGroup) | Seuils d'alerte et bascules sous dégâts. |
| AlertAddFromVisionMovement / AlertAddFromVisionMinNoMovement / AlertAddFromAutoAlert / AlertFromFriendDeath / AlertMitigationFactor / AlertVisionMaxSpeed / NoiseAlertMultiplier / NoiseMaxDistance / MinDistanceToAutoAlert | Montée/descente d'alerte (vision, bruit, mort d'un allié). |
| FearSensor / Fear* (FearDrop, FearDropPerFriend, FearDropMaxFromFriends, FearFromDamageMultiplier, FearFromEnemy, FearFromFriendDeath, FearFromNoiseMaxDistance, FearFromNoiseMultiplier, FearPropagationDamageMultiplier, MaxFear, MaxFriendDistance, MinDistanceToFearAnEnemy) | Système de peur (fuite panique). |
| AttackOptimalDistance / AttackApproachTarget / AttackMaxCount / AttackWaitAfterAttack / AttackRandomDirection / AttackWidthAngle / AttackRoarBeforeAttack / AttackUseRetreatRoar / AttackOnFriendDamage / BasicAttackStances / UseMeleeAttack / MeleeAttackDistance / MinimalDistanceToTarget / IsRanged / IsAttackJumping / IsHunting / IsScavenger | Combat IA (distances optimales/minimales d'attaque). |
| SearchAdvanceTime / SearchWaitTime / SearchRandomDistanceMult | Recherche de cible (avance, attente, dispersion aléatoire). |
| DamageAlertMultiplier | Montée d'alerte supplémentaire sur dégâts reçus. |
| AvatarController | Contrôleur d'animation du modèle (corps/rig). |
| MovementController | Contrôleur de déplacement spécifique. |
| PushFactor | Force de poussée (collision avec les joueurs). |
| MeleeWeaponIndex / RangedWeaponIndex / WeaponAtAlert / HandItem | Armes de l'entité. |
| FireWeaponDurationMultiplier / FireWeaponBlendInTime / MotionAnimationSpeedMultiplier / BarkingState | Animations d'attaque. |
| HeadTransform / RightHandJointName / LeftHandJointName / NPCModelRotation / PlayerBikeHandPos | Ancrages de modèle. |
| ItemsOnEnterGame / ItemOnPickup / DropInventoryEntity / DropInventoryItem / LootListOnDeath / RpFactor / XpFactor | Inventaire/loot/XP/réputation. |
| SfxAlert / SfxAlertTime / SfxDeath / SfxHurt / SfxHurtSmall / SfxRandom / SfxRandomTime / SfxSpawn / SfxStamina / SfxAnimationEvent0..N / SoundAlert / SoundAlertTime / SoundDeath / SoundHurt / SoundRandom / SoundRandomTime | Sons d'entité. |
| HudInfo / DisplayDistance / DisplayHungerBar / DisplayThirstBar / DisplayIsAttacking / DisplayIsHidden / DisplayAmbushGO / DisplayClosestWaterGO / ShowInDistance | HUD (domestication, état). |
| HungerLevelIncreaseRate / ThirstLevelIncreaseRate | Famiflauge. |
| GroupLeaderPriority / MaxCountInGroup / PoolCount / SpawnInSameDirection / SpawnYAdd / SpawnNodeName / SpawnParticle / SpawnParticleNodeName / SpawnSfx | Spawn en groupe. |
| TimeStayAfterDeath / ParticleOnDeath / FadingEnabled / Lod0Distance / UpdateClusterInfo | Mort/rendu. |
| AsteroidBlockValueType / DroneType / UseProxy / TickIfLead / TimeBetweeenTicks / ReturnHome / HintReturnHome / IdleMaxWaitTime / MaxOwnerReputation / Use (réputation) | Divers IA/réputation. |
| AllowUserInstantiate / AllowInSpawners | Utilisation en spawner/factory. |

## 5.12 EGroupsConfig.ecf (groupes d'entités)

| Propriété | Sens |
|---|---|
| (nom de groupe en clé) | Chaque bloc `{ NomGroupe }` contient des enfants `{ Child N # commentaire }` : entités membres avec leur poids/probabilité (N = index). |
| SpawnInSameDirection | Membres spawnés dans la même direction. |
| TotalHorror / TotalSpawnCount | Limites du groupe. |

Les noms de groupes (Crawler, ZiraxMale, TalonGuardianGroup...) sont
référencés par CreatureSpawning/SpawnZones/EClass.

### Enfants « sensor/comportement » (Child N dans EGroups/EClass)

Les blocs enfants portent des capteurs et comportements paramétrables :

| Enfant/Clé | Sens |
|---|---|
| AlertSensor | Capteur d'alerte (distance/type d'événements qui déclenchent l'alerte). |
| VisionSensor | Capteur de vision (portée, angle, cibles). |
| FearSensor | Capteur de peur (déclencheurs de fuite). |
| HideSensor / BodySensor / DebugSensor / GroupDirectionSensor / StuckSensor / TargetSensor | Capteurs divers (cachette, corps, debug, direction de groupe, blocage, cible). |
| EventAgentSpawner | Agent de spawn d'événements. |
| MainBehavior | Comportement principal (script IA). |
| Inputs | Entrées de configuration du comportement. |
| Unit1..Unit6 | Unités composant le groupe (par index). |
| InventoryItem1..5 | Items donnés/portés. |
| VariableOverride | Surcharge de variables IA. |
| DropOnDestroy_N / DropOnHarvest / PlantDestroy / PlantHarvest / PlantGrowing / CropsGrown | Drops à la destruction/récolte, croissance des plantes. |
| Immunity0 | Immunités. |
| Hints / Map | Indices et carte. |
| StarRegion_N | Région stellaire (définition de zone galactique). |
| Territory_N | Territoire nommé (ex. Dronelands, Solitude, Outlaw Space). |
| BaseAttack_TimeBetweenAttacks / BaseAttack_TargetBaseSuitability / BaseAttack_ScenarioPrice | Paramètres des attaques de base (intervalle, éligibilité, prix). |

## 5.13 StatusEffects.ecf (effets de statut)

| Propriété | Sens |
|---|---|
| Type | Category de l'effet (Health, Food, Oxygen, Temperature, Radiation, Buff...). |
| Name / Icon / Description | Identité visuelle. |
| Stat / Amount / Rate / SetValue / ModifyMaxValue / NumberOperationType | Cible statistique, valeur, taux, opération (add/multiply/set). |
| Duration | Durée (s) ; Stack = empilable ; Mutex = exclusion mutuelle. |
| BuffIf / DebuffIf / Requires / RequiresAll | Conditions d'application. |
| Evolves / NextIsWorse | Évolution de l'effet (ex. Plaie infectée → Sepsis). |
| OnExpired / OnExpiredSound / OnDebuffSound / CastSound / Actions / DebuffActions | Effets d'expiration/actions. |
| IsPiercing | Buff de type perforant (utilisé par PiercingFac des armures). |

## 5.14 MaterialConfig.ecf (matériaux de terrain/blocs)

| Propriété | Sens |
|---|---|
| (nom de matériau en clé) | Chaque bloc `{ NomMatériau }` : propriétés physiques. |
| Hardness / ExplosionHardness | Résistance outil/explosion. |
| HitPoints / Mass | Vie et masse. |
| collidable / liquid / stability_glue | Collision, fluide, colle de stabilité. |
| lightopacity | Opacité à la lumière. |
| fertile_level | Fertilité (plantation). |
| O2Content | Contenu en O2 (gaz). |
| damage_category / particle_category / particle_destroy_category / stepsound / surface_category | Sons de pas, particules, catégories de dégâts. |
| plant | Matériau végétal. |

NB : les matériaux HumanSoft/CreatureSoft/Mechanical/DronePlanet/Player NE
sont déclarés NULLE PART (vanilla 37, RE2 86, ATL 55) — les vérifier = faux
positifs (fiche cerveau).

## 5.15 DamageMultiplierConfig.ecf

| Propriété | Sens |
|---|---|
| DamageMultiplier_1..10 / BlastDamageMultiplier_1..8 | Multiplicateurs de dégâts par catégorie d'arme/munition contre les matériaux (index = catégorie). |

## 5.16 TokenConfig.ecf (jetons spéciaux)

| Propriété | Sens |
|---|---|
| Id / Description / CustomIcon / MarketPrice / DropOnDeath / RemoveOnUse | Jetons de quête (consommés à l'usage, non lâchés à la mort). |

## 5.17 GlobalDefsConfig.ecf (défauts globaux)

| Propriété | Sens |
|---|---|
| Mass / Volume / MarketPrice / AllowPlacingAt | Valeurs par défaut pour tout objet qui ne les déclare pas. |

## 5.18 TraderNPCConfig.ecf (marchands)

| Propriété | Sens |
|---|---|
| NPC Name / Trader Name | Nom du marchand. |
| SellingGoods / SellingText | Marchandise vendue / texte de vente. |
| Discount / Item1..Item41 | Remises et items en vente (liste indexée). |
---

# 6. terrain.ecf (un par playfield, sous Playfields/<Nom>/)

Définit les MATÉRIAUX DE TEXTURE du terrain : chaque bloc racine
`{ Material Name: N NomTexture }` = une texture principale, et ses
`{ Child N # NomSousTexture }` = les transitions/mélanges possibles.

## 6.1 Bloc racine Material

| Propriété | Sens |
|---|---|
| Material Name | Index + nom de la texture principale (ex. `1 AridTex`). |
| HeightMapMax | Hauteur max de la heightmap où cette texture s'applique. |
| SplatMap_1 / SplatMap_2 | Fichiers de splatmap contrôlant le mélange des textures. |
| ClusterScale | Échelle des taches de mélange. |
| DominantLayer | Couche dominante du mélange. |
| HeightOffset / HeightContrast / HeightMapMax | Réglages de la réponse en altitude. |
| TCOwnCol | Texture-coordinate / couleur propre. |

## 6.2 Enfants Child (textures de mélange)

| Propriété | Sens |
|---|---|
| Child N | Index du mélange (le commentaire `# Grass02` = nom lisible). |
| Name / Name2 | Textures primaires du mélange (la 2e sert de variante). |
| Brightness / Brightness2 | Luminosité de la texture. |
| Saturation / Saturation2 | Saturation. |
| RGB / RGB2 | Multiplicateurs de couleur `(r, g, b)`. |
| AddCol | Ajout de couleur global. |
| Smoothness | Lissage/brillance (valeurs négatives = mat). |
| ReliefStrength / NormalStrength | Force du relief parallaxe / intensité des normales. |
| Interpolation | Douceur de la transition vers les textures voisines (0..1). |
| GeoStrength | Influence géométrique du mélange (déformation visible). |
| DistanceResample | Rééchantillonnage à distance (réduit le scintillement). |
| UVScale / ResampleFac | Échelle UV et facteur de rééchantillonnage. |
| HeightOffset / HeightContrast | Réglage de la pente en hauteur pour ce mélange. |
| TerrainId / TerrainId2 | Ids de matériau physiques associés (blocs cassés/son). |
| UnderTerrainId | Matériau sous la surface (en creusant). |
| DistantScale / NearScale | Échelle du mélange vu de loin/près. |

---

# 7. Prefabs .epb (blueprints/POI binaires)

Format binaire (parseur complet : `core/epb_blueprint.py` ; référence
lecture/écriture : `rea-epd/EPBHandler/EPD.EPB/EPBParser.cs`).

## 7.1 Header — EnumProperties (enum moteur `BlueprintHeader.EnumProperties`)

Clés du dictionnaire de propriétés binaires (type déclaré par entrée) :

| Id | Clé | Type | Sens |
|---|---|---|---|
| 1 | AddDigoutBox | bool | Boîte de déblais : creuse un volume + garde-fou anti-ensevelissement (pivot corrompu = POI enseveli ; cf. panneau meta de l'éditeur). |
| 2 | FlattenTerrain | bool | Aplatit le terrain sous le prefab. |
| 3 | GroundYOffset | int | Décalage vertical (blocs) du prefab par rapport au sol. |
| 4 | RotationToFaceNorth | int | Rotation (degrés) pour « face au nord ». |
| 5 | Powered | bool | Structure alimentée à la pose. |
| 6 | Rotation | int | Rotation d'orientation (ancien champ). |
| 7 | GroupName | string | Nom de GROUPE du prefab (clé des POIs.Random[].GroupName ; = clé de groupe des 842 faux positifs si on lit aussi Tags). |
| 8 | ChangedBuild | int | Build du jeu de la dernière modification. |
| 9 | ChangedDate | long | Date de la dernière modification (epoch). |
| 10 | CreatorPlayerName | string | Créateur. |
| 11 | CreatorPlayerId | string | Id du créateur. |
| 12 | ChangedPlayerName | string | Dernier modificateur. |
| 13 | ChangedPlayerId | string | Id du dernier modificateur. |
| 14 | CameraYOffset | float | Décalage caméra Y (menu blueprint). |
| 15 | CameraZOffset | float | Décalage caméra Z. |
| 16 | DisplayName | string | Nom affiché (liste de blueprints, HUD). |
| 17 | GroundYOffsetFloat | float | Décalage vertical fin. |
| 18 | PivotPoint | Vector3 | PIVOT du remblai/flatten — pivot corrompu = POI enseveli (le remblai suit le pivot ; bouton « Réinitialiser le pivot (0) » de l'éditeur). |
| 19 | KeepTopSoil | bool | Conserve la couche de surface lors du flatten. |
| 20 | RotationSensitivity | int | Sensibilité de rotation en jeu. |
| 21 | Tags | string | Tags du prefab (2e clé de groupe : les lire AVEC GroupName, sinon faux positifs). |
| 22 | RLInContainer | ? | Reservation/lien conteneur entrant. |
| 23 | RLOutContainer | ? | Reservation/lien conteneur sortant. |
| 24 | CntBlueprintParts | int | Nombre de sous-parties (prefab composé). |
| 25 | BlockSize | int | Taille de bloc (unité) du prefab. |
| 26 | FlattenTerrainCircleSmooth | bool | Le flatten utilise un lissage circulaire. |

## 7.2 En-tête dérivé (champs BlueprintHeader du moteur)

| Champ | Sens |
|---|---|
| PrefabType | Masque de bits : 1 = blueprint joueur, 2 = ?, 4 = ?, 8 = ?, 16 = ? (filtres du menu : les valeurs 1/2/4/8/16 délimitent BA/SV/HV/CV/parties). |
| FileSize / FileName | Taille et nom du fichier. |
| Statistics (BlockStatistics) | cntLights, cntDoors, cntBlockEntities, cntBlockModels, cntSolid, cntTriangles, cntTrianglesReal, cntTeleporters, cntSpawnPointsUnlocked, cntSpawnPointsLocked, bAdminCore, bKeepContainers. |
| AttDefValues | Valeurs d'attaque/défense (v26+) : ArtilleryAttack/ArtilleryDefenseValue, InfantryAttack/InfantryDefenseValue (v28+ : booléens). |
| BlockIdMapping | Table de remappage d'ids (roundtrip vérifié par l'éditeur). |

## 7.3 Sections binaires

| Section | Sens |
|---|---|
| Header (magic 2022986309) | Version + propriétés ci-dessus ; navigation par répertoire central (les écarts de version décalent tout le header). |
| BlockTypes | Types de blocs utilisés. |
| Blocks | Blocs : position, rotation, couleur (+ données par cellule). |
| BlockTag* (Bool/Colour/Float/Position/String/UInt32) | Tags par bloc (états, couleurs spéciales...). |
| DeviceGroup | Groupes de dispositifs. |
| MetaTags | Dictionnaire de métadonnées (cf. 7.1, types String/Bool/Int/Float/Vector3/Long). |
| Statistics | Statistiques calculées (cf. 7.2). |

Pièges connus (fiches cerveau) : lire le bitmask comme des ids = faux (ids
par NOM) ; count==0 sans trailer pour les block groups ; champs v5 ;
matrice DENSE v<=4 ; bourrage après EOCD ; `PK` à zéro en v<=22 ; 9 prefabs
v<=3 illisibles (format non cartographié).

---

# 8. Extras/PDA/PDA.yaml (missions et dialogues PDA)

Le modèle d'exécution est `Eleon.PdaScript` (Chapters→Tasks→Actions,
récompenses, triggers) — classes Action/Chapter/Dialog/Task + actions
spécifiques : InventoryContains, InventoryOpened, ItemsPickedUp, NearPoi,
NearResource, NearUnit, Signal, Timer, ToolbarContains, WaveAttack.
Les clés ci-dessous sont celles observées dans le PDA.yaml de RE2-FR.

## 8.1 Chapitres

| Propriété | Sens |
|---|---|
| Chapters | Racine : liste de chapitres (clé = id du chapitre). |
| Chapters.*.ChapterTitle / Description | Titre et description. |
| Chapters.*.Category | Catégorie (Main, Visual, Freelancer...). |
| Chapters.*.PlayerLevel / PlayerCredits / Faction / ReputationLevel | Conditions d'activation (niveau, crédits, faction, réputation). |
| Chapters.*.Visibility / VisibleOnStartPlayfieldTypes | Visibilité et types de playfields où elle est visible au départ. |
| Chapters.*.PlayfieldTypes | Types de playfields où la mission s'affiche (Planet, Moon, Space...). |
| Chapters.*.Activatable / AutoActivateOnGameStart | Chapitre activable manuellement / activé au démarrage. |
| Chapters.*.NoSkip / SkipMessage / ActivateChapterOnSkip | Empêcher le saut / message de saut / chapitre activé au saut. |
| Chapters.*.HideTasks | Masque la liste des tâches. |
| Chapters.*.PictureFile | Image du chapitre. |
| Chapters.*.Group | Groupe de missions (regroupement visuel). |
| Chapters.*.StartMessage / CompletedMessage | Messages d'activation et de complétion (format `dlg;NomDialogue` suivi d'une barre verticale, pour ouvrir un dialogue). |
| Chapters.*.Comment | Commentaire interne (invisible). |
| Creator | Auteur du chapitre/scénario (métadonnée). |
| Chapters.*.Prerequisites / Dependencies / RewardedChapters / Dialogs | Prérequis, dépendances, chapitres qui la récompensent, dialogues rattachés. |
| Chapters.*.ChapterActivation | Activation par trigger (HighPrio, Check, PopupActivatesChapter, NoSkip, NotifyMessage, MessageTime, Names, NamesRequired, Types, Amount, Value, Required, TriggerDistance, GuidingDistance). |
| Chapters.*.RepeatConditions | Répétition : NumRepeats, DelaySeconds, Delay, DelayAdd, NoReminder. |
| Chapters.*.Rewards | Récompenses de chapitre : `Type:` (ex. Item, Credits, XP, Reputation...) + `Count:` (+ Item/Count/Meta). |
| Chapters.*.ActivateChapterOnCompletion | Chapitre activé automatiquement à la complétion de celui-ci. |
| Chapters.*.Tasks | Liste des tâches. |

## 8.2 Tâches

| Propriété | Sens |
|---|---|
| Tasks.*.TaskTitle / Headline | Titre (clé) et en-tête affiché. |
| Tasks.*.Description | Texte de la tâche. |
| Tasks.*.StartMessage / CompletedMessage | Messages début/fin. |
| Tasks.*.StartDelay | Délai avant activation. |
| Tasks.*.PictureFile | Image. |
| Tasks.*.HasUniqueItems | Les items requis sont uniques (non consommables partagés). |
| Tasks.*.OnlyVisibleWhenRewarded | Tâche visible seulement si récompensée. |
| Tasks.*.RewardedTasks | Tâches récompensées à la complétion. |
| Tasks.*.OnActivatePlayerOps / OnCompletePlayerOps | Opérations JOUEUR à l'activation/complétion : InventoryOp (add/remove items). |
| Tasks.*.OnActivateUIOps / OnCompleteUIOps | Opérations UI (popup, menus). |
| Tasks.*.OnActivatePlayfieldOps / OnCompletePlayfieldOps | Opérations PLAYFIELD : SpawnOPV, SpawnDrone, SpawnTroopTransport, DevicePowerMulti, ReplaceStructureStandingIn. |
| Tasks.*.OnCompletePdaDataOps | Opérations PDA (activer chapitres...). |
| Tasks.*.OnCompleteSignal | Envoi d'un signal : Name, Type. |
| Tasks.*.Actions | Actions à accomplir (cf. 8.3). |

## 8.3 Actions (checkpoints)

| Propriété | Sens |
|---|---|
| Actions.*.ActionTitle / Description | Nom et texte de l'action. |
| Actions.*.Check | Type de vérification (catalogue : ArmorEquipped, BiomeChanged, BlockDestroyed, BlocksPlaced, DeviceNamePowered, DeviceUsed, EnterPlayfield, EnterPOI, EnterElevator, Kill, ItemsCollected, InventoryContains, InventoryOpened, ItemsPickedUp, NearPoi, NearResource, NearUnit, SignalReceived, Timer, ToolbarContains, WaveAttack, WaitFor..., etc.). |
| Actions.*.Check.Names / NamesRequired / Types / Amount / Value / Required | Paramètres du check (noms d'entités/blocs, types, quantités). |
| Actions.*.Check.TriggerDistance / GuidingDistance | Distances de déclenchement et de guidage (flèche PDA). |
| Actions.*.IsOrdered / IsOptional / AllowManualCompletion / Required | Ordre imposé, optionnelle, complétion manuelle. |
| Actions.*.Names | Liste de cibles (POI/entités/blocs). |
| Actions.*.Amount | Quantité. |
| Actions.*.CompletedMessage | Message de fin d'action. |
| Rewards (dans Actions aussi) | Récompense d'action : Type, Count, Item, Faction, Meta. |

## 8.4 Dialogues (Dialogues.ecf + PDA.csv)

| Propriété | Sens |
|---|---|
| Dialogs | Liste de dialogues par NPC (PDA.yaml). |
| Dialogues.ecf : NPCName | Id du dialogue = nom du PNJ. |
| Dialogues.ecf : Globals | Variables globales du dialogue. |
| Dialogues.ecf : Functions (fn1..fnN) | Fonctions : blocs de nœuds. |
| Node : Input | Texte d'entrée (ce que « dit » le PNJ ; localisation via PDA.csv). |
| Node : Output / Output_N | Réponses joueur possibles. |
| Node : Option_N / OptionIf_N / OptionNext_N / OptionExecute_N | Options de réponse : texte, condition, nœud suivant, action à l'exécution. |
| Node : Next_N / NextIf_N | Transitions automatiques : nœud suivant + condition. |
| Node : Execute / Execute_N | Actions à l'exécution du nœud (donner items, XP, ouvrir PDA, spawn...). |
| Node : Variable_N | Variables locales de dialogue. |
| Node : BarkingState | Répliques « en passant » (non-dialogue). |

Le contenu textuel est localisé dans `Extras/Localization.csv` et
`Content/Configuration/Dialogues.csv` (clé = nom de dialogue/nœud).

---

# 9. Valeurs et pièges transverses (annexes)

| Piège | Détail |
|---|---|
| `Target: ""` | Se lit AVEC les guillemets : '""' est une chaîne NON vide (Deconstructor uniquement). Toujours `strip('"')` avant test. |
| « Multiplyer » | Orthographe du moteur ET des yamls (RateMultiplyerCenter/Edge) : ne jamais corriger. |
| MinMax | `[a, b]` : si un seul élément `[n]`, min = max = n. |
| RegenerateAfter (Resources espace) | Garde `RegisterCommand() > 0` : 0/absent/négatif = JAMAIS de régénération ; s'applique aux POI ET aux champs d'astéroïdes espace ; unité = minutes (720/180). |
| DroneProb | Probabilité 0..1 ; 0 = aucun drone (6890 occurrences RE2). |
| MaxCount | Limite PAR STRUCTURE sur la TÊTE de famille (remontée TemplateRoot/ChildBlocks) ; BlockGroups.ecf = budgets de groupes nommés ; garde `(Survival\|Freedom && EnableMaxBlockCount) \|\| ForceMaxCount`. |
| Blocs vs items | Espaces d'Ids SÉPARÉS (Item Id 978 ≠ Block Id 978) — toujours deux tables. |
| Factions/spawn | SpawnPOINear exige que la cible soit déclarée AVANT (ordre du fichier). |
| Config de base | La config du scénario REMPLACE la vanille : rédéclarer explicitement pour neutraliser les patchs (+Block/+Item) de base. |
| JAMAIS de fusion ECF | 47 clés dupliquées légitimes dans GalaxyConfig — la dédup détruit des étoiles. |
| Ne jamais réécrire un ECF via parse+render | Perte de blocs ; ajouter en TEXTE BRUT, backups centraux. |
| Localisation | Tous les textes (Info, Description, PDA) passent par Extras/Localization.csv et Dialogues.csv — la clé du texte = nom de l'objet/dialogue. |

---

# 10. Annexe — noms employés COMME DONNÉES (à ne pas confondre avec des propriétés)

Certains ECF utilisent des NOMS D'OBJETS en position de clé. Ce ne sont pas des
propriétés interprétées par le moteur mais des données (ingrédients, membres de
groupes, factions). Les listes ci-dessous sont exhaustives pour RE2-FR.

## 10.1 Templates.ecf — noms de produits/ingrédients (231)

Clés des blocs `{ Template Name: X }` et des ingrédients dans `{ Child Inputs }`
(ex. `IronIngot: 5`) et sorties `{ Outputs }` :

AdrenalineShot AdvancedUpgradeKit AkuaWine AlienOrganism AlienSpikeLemon AlienThorn AlienTooth AluminiumCoil AluminiumOre AluminiumPowder AntennaBlocks AntiRadiationOintment AntiToxicInjection AntiToxicPills AntibioticInjection AntibioticOintment AntimatterConverter AssaultRifle AutoMinerCore Bandages Berries BioFuel Bone Bread BrokenDomeGenerator CapacitorComponent Cement Cheese Chemicals CobaltAlloy CobaltIngot CobaltOre CommunicationEquipment Computer ConfettiMossScrapings Coolant CopperIngot CopperOre Core CrushedStone Curry DataCore DetectorCV DrillAttachment DurianRoot Eden_Deuterium Eden_DeuteriumFuel Eden_DiamondCut Eden_DroneSalvageProcessor Eden_Electromagnet Eden_GaussRail Eden_HydroponicsEmpty Eden_IceCerulianDust Eden_IceDense Eden_IceFerrite Eden_IceHeavy Eden_IceHydronite Eden_IceNitronite Eden_IceRich Eden_IceTerrarite Eden_MagmaciteIngot Eden_MagmaciteOre Eden_MagmacitePlate Eden_ModularPulseLaserLensLarge Eden_ModularPulseLaserLensSmall Eden_OreDenseT1Ingot Eden_OreDenseT2Ingot Eden_OreDenseT3Ingot Eden_OreDenseT4Ingot Eden_OreDenseT5Ingot Eden_PalladiumIngot Eden_PalladiumOre Eden_PlasmaCoil Eden_Polymer Eden_PowerRegulator Eden_Semiconductor Eden_TungstenIngot Eden_TungstenOre Eden_TurretMissileLight_Ammo Eden_Voidium Egg Electronics EnergyCell EnergyCellLarge EnergyDrink EnergyMatrix ErestrumGel ErestrumIngot ErestrumOre Fertilizer Fiber Filters FireMossScrapings Flour FluxCoil Fruit FruitJuice FuelTankMSLarge FusionCell GlassPlate GoldCoins GoldIngot GoldOre Grain Graphite GrowingPot HeatExchanger HeavyWeaponKit HeliumBottle HerbalLeaves HoverbikeHowler HoverbikeHunter HoverbikeSpeedstar HoverbikeWasp HullLargeBlocks HullSmallBlocks HumanNPCBlocks HydrogenBottle IceBlocks IronIngot IronOre Jerky LargeOptronicBridge LargeOptronicMatrix LargeUpgradeKit LaserKit LaserPistol MagnesiumOre MagnesiumPowder Meat MechanicalComponents MedicalCast MetalPieces Milk MinigunEpic MiningEquipment MoneyCard Motor MultiTool MushroomBrown NCPowder Nanotubes NaturalStimulant NaturalSweetener NeodymiumIngot NeodymiumOre NitrogenBottle NutrientSolution OpticalFiber Oscillator OxygenBottleLarge OxygenBottleSmall OxygenStation OxygenTankMS PentaxidCrystal PentaxidElement PentaxidOre PentaxidTank PhoenixFernFonds Pistol PistolKit PlantProtein PlasmaConverter PlasticMaterial PlatinBar PlatinOre PlatinOunce PlayerBike PlayerBikeKit PowerCoil PromethiumOre PromethiumPellets QuantumProcessor RCSBlockMS RadiationImmunityShot RadiationPills RadiationShielding RawDiamond ReactorCore RifleKit Robotics RockDust RocketLauncher RocketLauncherEpic RottenFood Salt SathiumIngot SathiumOre SentryGunBlocks Shotgun ShotgunKit SiliconIngot SiliconOre SmallOptronicBridge SmallOptronicMatrix SmallUpgradeKit Sniper SniperKit SpareParts Spice Steak SteelPlate SteelPlateArmored StomachPills Sugarcane Sulfur Superconductor ThrusterComponents ThrusterMSDirectional ThrusterMSRoundBlocks ThrusterSVRoundBlocks TitanOre TitanPlates TitanRods ToxicWaste TurretMSProjectileBlocks TurretRadar Varonroot Vegetables VentilatorBlocks WarpDrive WaterBottle WaterJug WoodLogs WoodPlanks XenoBlock XenoSubstrate XenonBottle ZascosiumAlloy ZascosiumIngot ZascosiumOre

## 10.2 EGroupsConfig.ecf — groupes d'entités (92)

Noms des blocs groupes (référencés par CreatureSpawning/SpawnZones/EClass) :

AlienAssassinGrey AlienAssassinInfected AlienAssassinRed AlienBug01Old AlienBug02Group AlienBug03Group AnnoyingMosquito_Gray AnnoyingMosquito_Green AnnoyingMosquito_Primitive AnnoyingMosquito_Red AssaultCyborg AssaultCyborgCommando AssaultCyborgDamaged AssaultCyborgDamagedRandom AssaultCyborgSentinel AssaultMech CaveWormGreen CaveWormGrey CaveWormWhite Crawler Creepy DamagedCyborg Eden_CrystalSlugBlue Eden_CrystalSlugOrange Eden_Dissolver Eden_InfectedPlantMonster Eden_LegacyOverseer Eden_PolarisMiningDrone Eden_PolarisSalvageDrone Eden_ZiraxInfectedGreenEasy Eden_ZiraxMiningDrone Eden_ZiraxSalvageDrone Fish GlidingOverseer GolemDesert GolemIce GolemSwamp Hexapod HexapodInfected LizardMule LizardMuleBaby Mechanoid MegalonopsBrown MegalonopsGrey Otyugh Overseer Oviraptor OviraptorBaby Pangolin Parasaur ParasaurBaby PlantMonster Raptor RaptorNight RipperDog ScraperDrone_Army ScraperDrone_Blue Slime SlimeWhite SoldierAlienAssaultRifle SoldierAlienInfected SoldierAlienShotgun SoldierHumanMale2Infected SoldierHumanMaleInfected SpawnInSameDirection Spinosaurus TalonGuardian TalonGuardianCrossbowGroup TalonGuardianGroup TalonGuardianInfectedBlue TalonGuardianInfectedCrossbow TalonGuardianInfectedGreen TalonGuardianInfectedRed TalonGuardianShamanBaseAttack Telluropod TotalHorror Triceratops WoodWalker WormDesert WormDesertLarge ZiraxInfectedBlue ZiraxInfectedCommander ZiraxInfectedGreen ZiraxInfectedPurple ZiraxInfectedRed ZiraxInfectedYellow ZiraxLaser ZiraxMale ZiraxMinigun ZiraxRocket ZiraxShotgun ZiraxSniper

## 10.3 DefReputation.ecf — clés de premier niveau (31)

Mélange de NOMS DE FACTIONS (ARC, Abyssal, Colonists, Epsilon, Farr, Ghyst,
Pirates, Polaris, Rados, Serdu, Talon, Tesch, Trader, Wastelanders, Xenu,
Zirax, Eden_Defender) et d'ÉVÉNEMENTS de réputation (AttackedMember,
KilledMember, DestroyBlock, PlantHarvest, OreMined, OpenContainer...) —
sémantique des événements en 5.8.

ARC Abyssal AttackedMember AttackedPredator AttackedPrey Colonists DestroyBlock Eden_Defender Epsilon Farr Ghyst KilledMember OpenContainer Order OreMined OutsideHostileTerritory Pirates PlantDestroy PlantHarvest Polaris Rados Serdu ShieldAttacked StructSpawnedInTerritory StructStayInTerritory Talon Tesch Trader Wastelanders Xenu Zirax

## 10.4 Containers.ecf / LootGroups.ecf / TokenConfig.ecf

- Containers : noms multiples `Name_0..N` et groupes `Group_0..N` (items placés) ; props réelles : Size, Count, SfxOpen, SfxClose, DestroyOnClose.
- LootGroups : items `Item_0..N` (prob + plage) ; prop réelle : Count.
- TokenConfig : aucune clé-donnée.
## 10.5 GalaxyConfig.ecf — familles indexées

StarClass_1..13, Other_1..10, NebulaColors1..27 : définitions multiples de classes
d'étoiles, positions alternatives et palettes de nébuleuses (cf. 5.10).
## 10.6 ItemsConfig.ecf — familles indexées

Focused_blockname_1..133 (scanners), Item1..41 (marchands), Lvl1MinPrice..Lvl10MaxPrice
(prix par réputation), SDPriceMin..SDProbabilityMax (défenses spatiales), Slot1..5 (armure),
DamageMultiplier_1..8, BlastDamageMultiplier_1..5, Mesh-Damage-1..4, Mod.* (modificateurs).
## 10.7 BlocksConfig.ecf — familles indexées

Mesh-Damage-1..4 (états endommagés), DamageMultiplier_1..10 / _Group, BlastDamageMultiplier_1..8,
Variable_1..N / Option_* / Next* (variantes conditionnelles, moteur de scripting Dialogues).
