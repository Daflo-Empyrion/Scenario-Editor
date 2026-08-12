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
