# Empyrion Wiki — scenario structure and ECF/YAML properties

Based on community documentation (official Empyrion wiki on Fandom, Steam guides,
official forums, the eWCCT tool). The most specific pieces of information (exact values
of rare properties) always deserve in-game verification — community documentation
evolves with game updates and isn't always 100% current.

---

## 1. Structure of a scenario folder

```
MyScenario/
├── Content/
│   └── Configuration/       <- All gameplay .ecf files (see section 2)
├── Playfields/               <- One subfolder per playfield, with its .yaml
├── Prefabs/                  <- Blueprints (.epb) of custom POIs/ships
├── RandomPresets/             <- SolarSystemConfig.yaml files (procedural generation)
├── Sectors/                  <- Sectors.yaml (galaxy structure)
├── Extras/                   <- Dialogues.csv, Localization.csv, other CSVs
├── SharedData/                <- Content shared across sub-scenarios/DLC
├── gameoptions.yaml            <- Default game options
└── description.txt / Logos/   <- Scenario display metadata
```

**General rule (confirmed by several community guides)**: only the files you actually
modify need to be present in your scenario folder — any missing file simply falls back
to the base game (vanilla). That's why a "light" scenario sometimes contains only a
handful of files in `Content/Configuration`.

---

## 2. The .ecf files in `Content/Configuration`

| File | Content |
|---|---|
| `BlocksConfig.ecf` | All buildable blocks (structure, hitpoints, material, placement category...) |
| `ItemsConfig.ecf` | All objects: weapons, ammo, hand items, consumables -- **including vehicle/base-related items** (e.g. vehicle drills), not just player-carried items |
| `Templates.ecf` | Crafting recipes (which items produce which object, with which ingredients) |
| `Containers.ecf` | Default contents of containers (chests, bags...) |
| `LootGroups.ecf` | Loot groups used by POIs and randomly generated containers |
| `EClassConfig.ecf` | Entity classes (NPCs, creatures) |
| `EGroupsConfig.ecf` | Entity groups |
| `DefReputation.ecf` | Default reputation towards the different factions |
| `FactionWarfare.ecf` | Rules of war between factions |
| `MaterialConfig.ecf` | Material properties (resistance, etc.) |
| `StatusEffects.ecf` | Status effects (buffs/debuffs) |
| `TraderNPCConfig.ecf` | NPC trader configuration |
| `TokenConfig.ecf` | Lock tokens/codes used by doors, chests... (tied to the dialogue system) |
| `Dialogues.ecf` | NPC dialogue trees |
| `Dialogues.csv` / `Localization.csv` | Localized texts used by dialogues and the UI |
| `GalaxyConfig.ecf` | Global galaxy-generation parameters |
| `Config.ecf` (or `Config_Example.ecf`) | Light **override** file -- see section 4, limited use |

---

## 3. ECF file syntax

Eleon's proprietary format, **not JSON nor YAML** despite resembling both. An "object"
(block) is written between curly braces:

```
{ Block Id: 399, Name: ConcreteBlocks
  Material: concrete
  BlockColor: "170,170,170"
  Info: bkiBlockGroup, display: true
  IsOxygenTight: true, display: true
  HitPoints: 600, type: int, display: false
  Mass: 1100, type: float, display: true, formatter: Kilogram
  Volume: 10, type: float, display: true, formatter: Liter
  Category: BuildingBlocks
  ChildBlocks: "ConcreteFull, ConcreteThin, ConcreteExtended"
  UnlockCost: 0
  UnlockLevel: 1
}
```

Key points (source: Steam guide "Gentle guide to .ECF modding", confirmed by the
official forum):

- **`Id`** uniquely identifies the block/item within the file. Some real blocks have
  **no Id at all** and are identified only by `Name` -- a rarer but genuinely real
  convention (e.g. `{ Block Name: LegacyForcefield ...}`).
- **`Name`** is the internal name (not the in-game display name -- that comes from
  localization). **Never change the Id or Name of an existing block/item**: it breaks
  references in other files and in existing saves.
- **`Ref: OtherName`** makes a block/item inherit properties from another (inheritance
  mechanism) -- widely used to create variants (e.g. an "Epic" weapon that inherits from
  the base weapon and only redefines the stats that change).
- A property can have **sub-attributes** after a comma: `type` (int/float/string),
  `display` (true/false -- whether the tooltip is shown in-game), `formatter` (display
  unit: `Kilogram`, `Liter`, `Watt`, `ROF`...).
- Values containing a **comma** must be wrapped in quotes:
  `AllowPlacingAt: "Base,MS", display: true`. An unprotected comma breaks parsing.
- **Comments**: anything after a `#` on a line is ignored by the game.
- The **`+`** prefix before a block kind (`+Block`, `+Container`...) marks a **patch**
  that completes an existing definition of the same Id, rather than an independent new
  definition -- a common convention in large files edited over time.
- A syntax error (missing brace, unprotected comma, duplicate property) can prevent the
  entire file from loading, with a message in the game console (backtick key to open it)
  like "Ignored unknown parameter(s) in element...".

### Nested sub-blocks
An item can contain sub-blocks (e.g. `{ Mode Id: 0 ... }` for a weapon mode,
`{ Child Inputs ... }` for a recipe's ingredients). An item can have **several `Mode`**
entries to represent multiple firing modes (semi-auto/burst, etc.).

---

## 4. `Config.ecf` vs the dedicated files -- a common trap

Confirmed by numerous official discussion threads (this topic comes up very often):
**`Config.ecf` can ONLY override properties already present in
`Config_Example.ecf`** -- it isn't a universal override file. If you want to change a
property that doesn't exist in `Config_Example.ecf` (e.g. `AllowPlacingAt` for a given
block), you have to edit `BlocksConfig.ecf` (or the corresponding dedicated file)
directly, **not `Config.ecf`**. Trying to do so in `Config.ecf` produces a silent error
in-game ("Ignored unknown parameter(s)"), no crash, but no effect either.

Practical consequence: for most serious scenario mods, people edit the dedicated files
directly (`BlocksConfig.ecf`, `ItemsConfig.ecf`...) rather than `Config.ecf`.

---

## 5. The `.yaml` files (playfields)

Unlike `.ecf`, playfields use **real YAML** (indentation, `-` lists). Main file:
`playfield.yaml` (or `playfield_static.yaml` / `playfield_dynamic.yaml` depending on
type) in `Playfields/<PlayfieldName>/`.

### Adding a custom POI (based on the official "Customized POIs" guide)
1. Place the blueprint's `.epb` file in `Prefabs/`.
2. In the `playfield.yaml`, find the `POIs: ... Random:` section and add an entry:
```yaml
- GroupName: JunkT1
  CountMinMax: [4, 5]
  DroneProb: 0
  DronesMinMax: [0]
  ReserveCount: 0
  TroopTransport: False
  SpawnPOINear: [START]
  SpawnPOINearRange: [500, 1000]
  Properties:
    - Key: MapDistance
      Value: 600
    - Key: MapMarker
      Value: Neutral
    - Key: RegenAfter
      Value: 720
```
3. `GroupName` must match your blueprint's group name (a POI can only belong to **one**
   group).

**Important trap, confirmed by the official forum**: modifying a `playfield.yaml` only
affects **new games** (or playfields never visited in an existing save). A playfield
already generated in an ongoing save keeps its cached state -- changes to POIs on
planets/moons don't apply retroactively (unlike space playfields, which are more
flexible in this respect).

Lines marked "Please don't change" or "No functionality yet" in the file itself should
be avoided (info from the official wiki, "Customizing Solar Systems").

### For in-depth playfield editing: Empyrion Playfield Designer (EPD)
This built-in editor lets you open and directly edit a playfield's YAML (see
the application wiki's "Editing a YAML file" section), but stays far behind a dedicated tool
for anything involving **terrain** (textures, biomes) or **3D blueprint
preview**. For that level of detail, the community reference is **EPD
(Empyrion Playfield Designer)**, developed by jmcburn since 2018 and actively
maintained:
- Site: https://empyriontools.org/
- Terrain/texture editor per planet/moon (biomes, surface resources)
- Blueprint browser with **live 3D preview** at selection time (no more
  guessing among thousands of prefabs)
- "Preflight" check before saving
- Distributed under a CC BY-NC-ND license -- free and freely redistributable
  as-is, but without the right to share a modified version

---

## 6. RandomPresets / Sectors -- galaxy generation

- `RandomPresets/*.yaml` (`SolarSystemConfig.yaml` files) control the procedural
  generation of solar systems.
- `Sectors/Sectors.yaml` defines the galaxy structure (which sectors, which starting
  planets).
- `gameoptions.yaml` / `gameoptions_example.yaml`: default game options offered when
  starting a new game with this scenario.

Common community convention for a "light" scenario (just modified configs, not an
entirely custom world): copy these files as-is from the base game's "Default Random"
scenario, and only modify `Content/Configuration`.

---

## 7. Dialogues, Tokens and Localization

- **`Dialogues.ecf`** defines NPC and interactive block dialogue trees (code doors,
  panels...). A block can trigger a dialogue via the `ExecuteOnActivate` property in
  `BlocksConfig.ecf`.
- **`TokenConfig.ecf`** defines lock codes (1 to 9999) usable on doors and containers,
  tied to the dialogue system.
- **`Localization.csv`** contains the translated texts used by dialogues and the UI --
  typical structure: a `Key` column, then one column per language (`English`, `Deutsch`,
  `Français`...).
- Dialogues support dynamic variables (`{PlayerName}`) and advanced functions
  (`Execute`/`ExecuteEditor`, in simplified C#) for custom quest mechanics.

---

## 8. General points of caution when merging/modifying a scenario

1. **Always work on a copy**, never on vanilla files or an online scenario (confirmed
   by every community guide consulted).
2. **Never change the Id or Name** of a block/item already referenced elsewhere
   (recipes, loot tables, playfields) -- it breaks references.
3. An **unprotected comma** in a list-style value (`AllowPlacingAt: Base,MS` instead of
   `"Base,MS"`) is the syntax error most frequently reported on forums.
4. Check the in-game console (backtick key) after loading to spot parsing errors -- the
   game often points precisely to which element is problematic.
5. A playfield already visited in a save won't reload its POI changes -- test on a
   **new game**.
6. An Id shared between two different definitions (for example when merging two
   independent scenarios) is a real, well-documented source of conflicts -- this is
   exactly what this tool's anti-collision safeguard is designed to detect (see the
   application wiki).

---

## 9. Detailed ECF property glossary, by file

This section is generated from the glossary built into the application (menu
**Help > Application wiki**, section 4 -- property explanation panel visible
directly in every open ECF file). Built by direct analysis of the game files'
actual header comments, clarified (never a plain word-for-word translation).

### BlocksConfig.ecf

**General properties**

- `CustomIcon` -- Reuses an already-existing icon for in-game display.
- `PickupTarget` -- For a block that becomes a pickable item when destroyed (a bush, small rock...): the item it drops.
- `TemplateRoot` -- Which crafting recipe (Templates.ecf) to use for this sub-block.
- `UpgradeTo / DowngradeTo` -- Which block this one upgrades/downgrades into (base-tier progression system).
- `Place` -- How the block positions itself when placed: NoRotation (fixed), Face (auto-orients to the targeted surface), Free (any rotation).
- `Collide` -- Which object types collide with this block (player movement, bullets, rockets...). Removing 'movement' makes it walkable while staying hittable by weapons.
- `RemoveOnSI` -- Whether the block disappears when structural integrity gives way at this location.
- `IsActivateable` -- Whether the block can be activated/interacted with by the player (buttons, doors, switches...).
- `VolumeCapacity` -- Storage volume, required for any container-class block.
- `DropMeshfile` -- 3D model of the bag/container shown on the ground when this block is dropped (variant of the block's own model).
- `ShieldHitCooldown` -- Minimum time between two shield-hit visual/sound effects, to avoid spamming on rapid-fire weapons.

**Block mass**

- `Mass` -- Value given for a 1-meter block; the game auto-scales it: small grid (HV/SV) = value x0.125 (0.5m block), large grid (BA/CV) = value x8 (2m block).

**Common properties**

- `Material` -- Base material (concrete, metal, hullarmored, wood...) -- determines base look AND hit points/damage.
- `Category` -- Building-menu category (BuildingBlocks, Devices, Cockpits...).
- `Texture` -- List of 6 texture numbers, in order: top, bottom, north, south, west, east.
- `HitPoints` -- The block's health.
- `BlockColor` -- RGB color, e.g. "170,170,170".
- `AllowPlacingAt` -- Which structure types this block can be placed on (Base, MS, SS, GV, Terrain).

**Explosion codes**

- `BlastRadius / BlastDamage / BlastParticleIndex` -- Radius and intensity of area damage, and which visual effect to use (1-16).

**The Ref rule**

- `Ref` -- Inherits properties from another block/item (inheritance mechanism) -- very commonly used to create variants; can only point to a block already defined earlier in the file, never further down.

**Advanced properties**

- `ChildBlocks` -- Lists this block's shape variants (full, thin, slope, corner...). No new 3D models needed: the game engine already provides a standard shape library (right-click while placing) that automatically applies to any block family of the same material.
- `SymType` -- Shape symmetry type: 1=quarter-round (default), 2=corner, 3=sloped wall, 4=bevel corner (unusual default rotation).
- `Shape` -- The block's base shape.
- `IsPhysicsColliders` -- Fine physics collisions, sometimes disabled on very thin shapes (thin ramps) to avoid odd behavior.

**Dialogues**

- `ExecuteOnActivate` -- Which dialogue tree (Dialogues.ecf) triggers when this block is activated.

**Skills**

- `RequiredSkill / RequiredSkillLevel` -- Which skill and level are needed to place or use this block.

**Container classes**

- `Class: Container` -- Cargo, chest, fridge... requires VolumeCapacity.

**Symmetry**

- `SymType` -- See 'Advanced properties' above.

**Shaders**

- `CustomShader` -- Special visual shader for this block (glass, emissive, animated...).

**Exported properties**

- `type / display / formatter` -- Sub-attributes after a comma: value type (int/float/string), whether to show the tooltip in-game (true/false), display unit (Kilogram, Liter, Watt, ROF...).

### ItemsConfig.ecf

**General properties**

- `CustomIcon` -- Reuses an already-existing icon for in-game display.
- `AllowAt` -- Restricts usage, e.g. 'AllowAt: NoPvP' and 'AllowAt: NoPvE' to forbid an item depending on game mode.
- `MarketPrice` -- Price per unit for 'StationInterface' POIs. If several items fill the same role (e.g. 3 kinds of batteries for fuel), the cheapest one is automatically used.
- `LifetimeOnDrop` -- Seconds before a dropped item on the ground disappears (200s default). Only increase if truly necessary -- too many ground items hurts performance.
- `DropOnDeath` -- Set to 'False' so an important story item is never lost on player death (true by default).

**Effects (Buffs/Debuffs)**

- `BuffMod` -- Syntax: "StatusID, DurationFactor, IntensityFactor, CancelOnExpire(optional)". The duration/intensity factor modifies the effect's time/strength (0 = no change).
- `Cancel on expire` -- Boolean that prevents end-of-status effects if true -- e.g. a medicine that prevents an infected wound from turning into sepsis.

**Armor and boosters**

- `SlotItems` -- Max 15 entries per armor. Warning: changing this list affects boosters already active in existing games (stored as a plain INDEX into this list).
- `Armor` -- Extra hit points.
- `Oxygen` -- Extra oxygen volume.
- `Radiation / Heat / Cold` -- Protection up to this value.
- `PowerFac / SpeedFac / StaminaFac / JetpackFac / JumpFac / FoodFac` -- Multipliers for energy, speed, stamina, jetpack, jump, food consumption.

**Weapon types and damage**

- `Class: Ranged` -- Damage is defined on the weapon itself; the ammo type only carries stats (mass, volume, cost...).
- `Class: LauncherSS` -- Damage AND area damage (optional) defined on the ammo type (sub-entry 'Class: Projectile').
- `Area damage (Blast)` -- ADDS to base damage for the central block hit. Approximate formula: (Damage + BlastDamage) - (BlastDamage / BlastRadius).
- `Materials available for multipliers` -- head, body, dirt, stone, rock, metallight, metal, metalhard, woodsoft, wood, woodhard, concrete, hull, hullarmored, hullcombat, shield.
- `ShieldDamagePenFac / BlastShieldDamagePenFac` -- Percentage (0.0-1.0) of normal/area damage that passes through a shield.
- `BlastRadius / BlastDamage / BlastParticleIndex` -- Radius and intensity of area damage, and which visual effect to use (1-16).
- `Shields: special case` -- Area damage NEVER applies to a shield -- only base damage counts.
- `ShieldMultiplier` -- On a Class:ShieldGenerator (BlocksConfig.ecf), a free value reusable in a DamageMultiplier to specifically target this shield type.

**Categories**

- `Ingredients` -- Raw material with no recipe (picked up in the world).
- `Components` -- Processed material, with a recipe (Templates.ecf).

**Hold types (HoldType)**

- `0` -- Unspecified.
- `14` -- Pistol.
- `15` -- Rifle.
- `16` -- Rifle with a weaker firing animation (survival tool, multi-tool, drill).
- `17` -- Bow.
- `20` -- Melee.

**Miscellaneous**

- `AllowRemote` -- Allows/forbids use via player drone (true by default).
- `AmmoCapacity` -- Max 500 for all mounted turrets/weapons.
- `Durability` -- Max 5000 for hand-held weapons/tools.
- `AutoReload` -- Automatic reload (true by default).

### Templates.ecf

**Constructor abbreviations and time factor**

- `SuitC` -- Survival Constructor -- factor 1.8 (slowest).
- `SurvC` -- Portable Constructor -- factor 1.6.
- `SmallC` -- SV Constructor -- factor 1.4.
- `HoverC` -- HV Constructor -- factor 1.4.
- `BaseC` -- T0 Constructor -- factor 1.2.
- `LargeC` -- T1V2 Constructor -- factor 1 (reference).
- `AdvC` -- T2 Constructor -- factor 0.5 (fastest).
- `FoodP` -- Food Processor V2 -- factor 1.
- `Furn` -- Furnace -- factor 0.2.
- `(no tag)` -- Deconstructor -- factor 0.5.

**Recipe tips**

- `Free item` -- Set ALL Child Inputs lines to 0 -- NEVER remove the section entirely.
- `BaseItem: true` -- Defines the base tier for the blueprint factory, and serves as the reference for R2T repair.
- `Deconstructor` -- Breaks an item down until only BaseItem-tagged ingredients remain. E.g. iron ore (BaseItem) will never be recreated from an iron ingot.
- `DeconOverride: Continue` -- Allows the deconstructor to break the item down one further step.
- `DeconOverride: Stop` -- Prevents any deconstruction of this item.
- `T1-to-T2 limitation` -- Using a T1 device as an ingredient of a T2 device only works for unique devices (e.g. Constructor), not for block groups (e.g. Cockpits) -- don't use T1 as an ingredient in that case.

### BlockGroupsConfig.ecf

**Principle**

- `Purpose` -- Define a custom block group sharing a common limit -- useful for balancing, e.g., the total number of turrets.
- `Individual limit kept` -- Blocks in the group respect BOTH the group limit AND their own individual limit (defined in BlocksConfig.ecf).
- `Only works` -- On blocks that have an index (a numeric Id).
- `Informing the player` -- Add a matching line in Localization.csv (e.g. 'SVWeapons,Total SV Weapons {0},...') to show the limit in the UI -- nothing else to add in BlocksConfig.ecf.

**Example**

- `BlockGroup Name / MaxCount / Blocks` -- Group name, total limit, and comma-separated list of blocks involved.

### Containers.ecf

**Line format**

- `Syntax` -- "Group|Name_x" (x increments), data: "probability" [, xdata="quantity range"] (default 1,1).
- `Columns` -- Always use 8 columns currently (first number of the 'Size' line).
- `Total available` -- 1023 Ids max.

**Tokens in a loot table**

- `Syntax` -- Name_0: Token, param1: 1, param2: "meta=9992" -- the meta comes from TokenConfig.ecf.

**Tables for NPC spawners**

- `Usage` -- Enter the container's Id number (e.g. 255) in the dropdown next to spawn-entity.

**Growable crops (player planter)**

- `Fruit` -- AlienPalmTreeStage1, PearthingStage1
- `Vegetables` -- AlienPlantTube2Stage1, BulbShroomYoungStage1, DurianRoot, PumpkinStage1, TomatoStage1
- `Natural sweetener` -- AlienplantWormStage1
- `Buds` -- BigFlowerStage1
- `Spice` -- CobraLeavesPlantStage1
- `Natural stimulant` -- CoffeePlantStage1
- `Grains` -- CornStage1, WheatStage1
- `Pentaxid ore` -- CrystalsPyramidBlueStage1, CrystalsPyramidOrangeStage1, CrystalStraightStage1
- `Medicinal leaves` -- DesertPlant20Stage1
- `Berries` -- ElderberryStage1
- `Brown mushroom` -- MushroomBellBrown01Stage1
- `Fiber` -- SnakeweedStage1

### DamageMultiplierConfig.ecf

**Principle**

- `Purpose` -- Define reusable damage multiplier groups from ItemsConfig.ecf via 'DamageMultiplier_Group: GroupName'.
- `One method at a time` -- In ItemsConfig.ecf, use either DamageMultiplier_x OR DamageMultiplier_Group, not both.
- `Group of groups` -- A 'Collection' lets you combine several groups -- but a group of groups can't reference another one.

**Example: Pistol**

- `DamageMultiplier_1: 5, param1: head` -- x5 damage on the head.
- `DamageMultiplier_2: 0, param1: dirt|stone|...` -- No damage on these terrain/wall materials.
- `DamageMultiplier_3: 0, param1: shield` -- No damage on shields.

### DefReputation.ecf

**Principle**

- `Purpose` -- Lets you override the default reputation of all Origin factions toward NPC factions.

### EGroupsConfig.ecf

**Principle**

- `Factions` -- Creature factions are defined in EClassConfig.ecf, not here.
- `Battle Groups` -- Spawn together and interact as a team (AI behavior).

### FactionWarfare.ecf

**Space Base Defense (SBD)**

- `Scope` -- Global for a whole faction on a given POI -- can't configure a specific ship for a specific POI via SBD.
- `Excluding a POI from SBD` -- In the playfield yaml, use SpaceDefenseOverrideDefaults: True with SpaceDefenseProbability: 1.0 and SpaceDefensePriceMinMax: [30, 60] -- or set a precise probability (0-1) otherwise AI-managed.

**Zirax base attack (Survival)**

- `FactionSettings` -- Converts a level number into an attack-wave price.
- `Unit` -- Defines an individual unit usable in an attack scenario, sorted into a category (e.g. several minigun drone forces by difficulty).
- `Scenario` -- Defines the full composition of an attack -- usable automatically by the base-attack system, or manually via a PDA mission.

### Factions.ecf

**Required values**

- `Id` -- Must be unique, used in savegames -- changing it breaks existing games. Must be < 100, otherwise a PLAYER faction is created instead. Gaps in numbering are allowed.
- `FactionName` -- No spaces or special characters -- usable in localization. Used as a reference for playfields, POIs, etc.
- `Abbrev` -- Max 3 letters, avoid special characters.
- `Color` -- "R,G,B" -- divide the RGB value by 255 to get the expected float.
- `Description` -- Shown at the top of the list for NPC factions.

**Static factions**

- `Definition` -- Factions like Legacy or Alien -- reputation with them can't be improved.
- `Friendly: true` -- Always friendly -- DefReputation.ecf ignored, don't combine with 'Reputation: true'.
- `Unfriendly: true` -- Always hostile -- same rule.
- `Neither` -- The faction is neutral by default.

**Dynamic factions**

- `Definition` -- Factions like the Zirax -- reputation, own territory, can improve/degrade.
- `Reputation: true` -- Enables the DefReputation.ecf reputation matrix. Without it, the faction is statically hostile (unless FriendlyToPlayers is active).
- `ClaimTerritory: true` -- The faction can have a visual territory on planets (unrelated to galactic territories, handled in galaxy.ecf).

**Other settings**

- `OmitMapLegend` -- Hides the faction from map legends.
- `HideAbbrev` -- Hides the faction's abbreviation in the HUD.
- `Discovery` -- The faction becomes discoverable as soon as one of its POIs is discovered. Debug via console command 'faction discover <faction>'.
- `AttackNPC` -- This faction attacks other NPC factions that also have this option active.
- `ForceAttack` -- List of factions specifically attacked (can be asymmetric) -- overrides AttackNPC behavior.

**Good to know**

- `Don't mix` -- A faction is either static or dynamic -- never both.
- `Protected factions` -- Zirax, Talon, Alien, Polaris, Prey, Predator and Admin are handled internally (references/default values) and can't be customized.

**Faction warfare (summary)**

- `Galactic civilization (allied)` -- Zirax, Polaris, Trader, Colonists, Eden_Defender.
- `Enemies of all` -- Warlord, Alien, TheLegacy, Kriel, Eden_Drone, Eden_DroneHome, Pirates.
- `Mineable resources` -- Eden_Resource, Prey.
- `Hard-coded factions` -- Never modify these (except color) -- must be defined before any other faction in the file.

### GalaxyConfig.ecf

**Count limits**

- `Regions` -- From StarRegion_1 to StarRegion_99 max.
- `Territories` -- From Territory_1 to Territory_20 max, each able to have 1 to 10 additional 'Other_' factions (Other_1 to Other_10).
- `Star types (suntypes)` -- Unlimited.

**Binary star systems**

- `CompanionStarClass` -- Adds a decorative 2nd star (no gameplay) to a StarClass -- value must be a StarClass already defined in this file.

**Advanced configuration**

- `SolarSystemConfigSuffix` -- Forces use of a particular SolarSystemConfig<suffix>.yaml file instead of the default one for the star type.
- `Available star models` -- SunBlueGiant, SunWhiteDwarf, SunYellowWhite, SunYellow, SunRedGiant, SunRedDwarf, SunNeutron, BlackHole, SunGeneric. Only the visual model is limited to this list -- all other parameters (StarClass, color...) remain customizable.
- `Starting system` -- If the scenario doesn't use a fixed sectors.yaml with starting planets, a starting system can be defined in general settings. A sectors.yaml with starting planets takes priority over this entry if both exist.

**Internal units of measurement**

- `1 light-year (LJ)` -- = 10,000 AU = 100,000 sectors (simplified value for readability, not real astronomy).
- `1 AU` -- = 10 sectors.
- `Light-year coordinates` -- Territories, star position (sectors.yaml), galactic spawn radius, galaxy radius.
- `Sector coordinates` -- Zones around a star (e.g. HabitableCold), position of a planet/moon/station in sectors.yaml or SolarSystemConfig -- NOT in AU.

**Territories**

- `Available factions` -- Zirax, Talon, Polaris, Kriel, Pirates, Trader, UCH, Civilian, Alien.
- `Overlap` -- Multiple territories can exist for the same faction, even with overlapping coordinates/spheres.
- `Territory faction` -- Only its own POIs are placed in the territory by default; to allow others, use 'Other_' with a number, setting the probability from center to edge.

**Map labels (StarRegion)**

- `LabelName` -- Label text at this position.
- `LabelColor` -- Color, e.g. "0,1,0.67" or with transparency "1.0,0.0,0.0,0.2".
- `LabelSize` -- Label size.
- `LabelLYDistance` -- Distance (in light-years) beyond which the label hides.

**Nebulae**

- `NebulaSpawnCount` -- If defined in a StarRegion, disables random nebulae -- only those from regions using this property appear.
- `NebulaColorIndex` -- Chooses the nebula color in the matching NebulaColor gradient (up to 30 gradients possible).

**Seeing changes without relaunching**

- `Tip` -- Load a saved game, edit its Galaxyconfig.ecf in the save folder, then reload with the console command 'galaxy'.

**Hiding a solar system**

- `HideFromMap` -- Hides the system from the galaxy map.
- `HideFromSearch` -- The system stays visible on the map but no longer appears in search.

**Star settings (full example)**

- `Name` -- Star name -- customizable, or generic '<StarClass> Type Star'.
- `StarClass` -- Star class, 3-4 letters/digits.
- `Model` -- Visual model (default SunGeneric).
- `Probability` -- 0 to 1 -- overall probability this class exists in the galaxy (never set to 0).
- `SizeClass` -- 1 to 12 -- star and icon size, affects warp sector distance for large stars.
- `Color / LightColor / ModelColor / ModelColor2` -- Star colors (map, in-game appearance, internal color, corona).
- `ModelBrightness` -- 0.1 to 1.5 -- overall corona brightness (SunGeneric only).
- `SurfaceTemperature / Mass / Radius / Luminosity / Age` -- Purely informational, no gameplay effect.
- `InnerSystem / HabitableHot / HabitableTemperate / HabitableCold / OuterSystem` -- Distance ranges (in AU) defining each zone of the system -- later used in sectors.yaml to place planets.
- `GalaxySpawnRadius` -- Min/max distance (in light-years) from center for this star to appear.
- `GalaxySpawnAmount` -- Number of stars of this type placed in the galaxy -- set to 0 only if handled via REGIONS.
- `ClusterProb / ClusterRange` -- Probability (0-1) and position (0=edge, 1=center) of clustering.
- `Description` -- Short scientific/narrative description for the map.

### GlobalDefsConfig.ecf

**Principle**

- `Purpose` -- Define common values (e.g. a weapon's damage, a drone's hit points) ONCE here, then reuse them in any other ECF file -- changing the value here is enough to change it everywhere.
- `Usage` -- In another file (e.g. ItemsConfig.ecf), use 'GlobalRef: DefName' to reference this value.
- `Multiple References` -- A single block can use several GlobalDefs via GlobalRef_1 through GlobalRef_5.

### LootGroups.ecf

**Line format**

- `Syntax` -- Item_x: name, data: quantity[-range], xdata: probability (x increments per line; use quotes if the quantity is a range).

### MaterialConfig.ecf

**General notes**

- `hullarmored / hullcombat` -- Cannot be destroyed by most hand-held weapons.
- `Structural integrity (SI)` -- Current maximum length of a horizontal beam = 12 blocks.
- `stability_glue / mass` -- Determines the maximum number of aligned blocks that won't detach due to loss of structural integrity.

### StatusEffects.ecf

**General notes**

- `Basic injuries` -- Cover everything an enemy commonly inflicts.
- `Example: standard bleeding` -- Heals on its own without treatment, over 240 health points of duration.

### TokenConfig.ecf

**Principle**

- `Definition` -- A Token is an instance of the 'GenericToken' item that gains meaning in-game -- e.g. the code for a locked door, or a PDA quest/mission requiring this token to complete.
- `RemoveOnUse` -- If true, removes the token from the player's inventory as soon as it's used.
- `Optional` -- No need to define every token here, but if defined, its name and description will display correctly.

**Use cases**

- `1. Placing a token in a container` -- Console: 'give item Token 0001', then place it in a container and save the POI (currently only works with an admin core).
- `2. Giving via PDA` -- Use 'Token:0001' as a reward or inventory operation in a PDA mission.
- `3. Giving via dialogue` -- AddItem function, e.g. AddItem('KeyCardBlack', 3, 1234) gives 3 cards with Meta 1234.
- `4. Selling via a trader` -- Add the item to TraderNPCConfig.ecf using 'Token:0001' as the item name.
- `5. In a loot table` -- Same principle, use 'Token:0001' in LootGroups.ecf.

**Important**

- `'Token' item (Id 1305)` -- Only this specific item can receive a 4-digit Meta. No other 'keycard'-like object can have a Meta attached.
- `Hot reload` -- The console command 'token reload' applies changes from this file without relaunching the game.

### TraderNPCConfig.ecf

**Item format**

- `General syntax` -- Item name, sell price range, available stock range[, buy price range, max stock range].
- `Optional buy section` -- If omitted, the trader doesn't buy this item.
- `Price calculation` -- If the trader buys the item (max stock defined), the reference price corresponds to a current stock equal to half the max stock. More stock = lower price, less stock = higher price.
- `Sell only` -- If the trader only sells the item, price doesn't depend on stock.
- `Overlap allowed` -- The buy price can overlap the sell price -- the game still guarantees the trader at least a 5% margin.
- `Market factor (mf=)` -- Applies a factor to the base market price.
- `Example` -- Item1: "AutoMinerCore, mf=2.5-3.2, 10-50, mf=1.2-2.3, 55-150"

**Warning**

- `Default trader` -- Don't rename the trader provided by default.

---

## Sources consulted

- Official Empyrion wiki (Fandom) -- pages "Guide/Customized POIs",
  "Guide/Customizing Solar Systems", "Scenarios"
- Steam Community, guide "Gentle guide to .ECF modding" (zaphodikus et al.)
- Steam Community, guide "Custom Scenarios for Dummies"
- Steam Workshop, "Scenario for Custom Config Mods"
- Official Empyrion forums (empyriononline.com) -- threads on Config.ecf,
  ItemsConfig.ecf, terrain.ecf
- Steam Community discussions on ECF parsing errors
- Documentation of the community tool eWCCT (Empyrion Web Config Creator Tool) for the
  dialogue/token system
