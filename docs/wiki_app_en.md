# Application Wiki — Empyrion Scenario Editor

Reference documentation for every function of the tool, organized by theme. For a
guided step-by-step walkthrough, see **Help > Tutorials...** in the application
instead — this wiki is meant to be searched for a specific point, not necessarily
read in order.

---

## 1. First launch and language

On the very first application startup (never again afterward), a bilingual screen
asks you to choose the interface language (Francais / English) — this choice is
applied immediately, and can be changed at any time afterward via the **FR/EN**
button at the top right of the main window. The choice is only asked once;
subsequent launches start directly in the chosen language.

Following this choice (and on every subsequent launch, unless disabled), the
**tutorials module** opens automatically with a banner reminding you it's
accessible at any time via **Help > Tutorials...**, and a checkbox
**"Don't show automatically on startup"** — once checked, automatic opening stops
permanently (re-enableable only by deleting the application's settings file).

---

## 2. Projects: creating, opening, the three-panel structure

### New project
**File > New project...** asks for three fields:
- **Scenario A** (required) — the source scenario folder, never modified
- **Scenario B** (optional) — a second reference scenario
- **Working copy destination** — where the editable copy will be created (must not
  already exist)

On creation, the tool copies Scenario A **fully and identically** into the
destination folder (all files, not just .ecf/.csv/.yaml). Nothing is invented or
transformed during the copy.

### Recent projects
**File > Recent projects...** (also automatically offered on startup) reopens an
existing project **without recopying** the working copy — your previous changes
stay intact. Useful for continuing work across multiple sessions.

### The three panels
- **Scenario A** (left) — the original source, **read-only**, never modified
- **Working copy** (center) — the only editable zone, all your work happens here
- **Scenario B** (right, optional) — a second reference source, also read-only

All three panels show the **exact folder structure on disk** — like a classic file
explorer, no artificial categorization.

### Managing Scenario B along the way
- **File > Open a Scenario B...** — appears when no B is active
- **File > Change Scenario B...** — same menu, automatically renamed once a B is
  active; asks for confirmation before replacing
- **File > Remove Scenario B** — disables the B panel; the working copy is never
  affected

---

## 3. Opening and navigating a file

**Double-click** any file in one of the three panels to open it in a new tab.
Files opened from Scenario A/B are **read-only**; those opened from the working
copy are **editable**. A tab already open for a file gets selected instead of
opening a duplicate.

Handled types: **.ecf** (blocks, items, config), **.yaml/.yml** (playfields,
planets...), **.csv** (translations, tables), **.txt** (plain text).

### The block tree (ECF)
- **Section groups**: if the source file uses separator comments
  (`# ===...===` / title / `# ===...===`), the tree shows bold category headers
  (visual markers only, not clickable)
- **Readable labels**: a `## ReadableName` comment right before a block shows in
  parentheses next to its technical identifier
- **Search**: by Id, Name, or CustomIcon, with next-result navigation (Enter)

---

## 4. Editing an ECF file

### The property table — two modes
- **Classic list mode** (majority of blocks) — one row per property, double-click
  the value to edit
- **Table mode** (repeating structures like *Child Items*, *LootGroups*,
  *DamageMultiplier*...) — automatically detects any sequence of numbered entries
  (`Name_0`, `Name_1`... or `Item_0`, whatever prefix the file uses), shows one
  column per parameter. The **"+ Row"** button replaces **"+ Property"** in this
  mode.

### Adding
- **+ Block** — guided multi-step creation: choose Id+Name or Name only, then
  a checkable property table drawn from the working file itself (sorted by
  real usage frequency, with the most common value suggested as a starting
  point) — a search box lets you filter properties when there are many. On
  validation, offers to directly create the associated **Template**
  (crafting recipe) if `Templates.ecf` exists in the scenario: same
  table-based mechanism, with the Name pre-filled to exactly match the
  block/item just created, and an **Ingredients** section where each row is
  picked from a dropdown (items and blocks genuinely defined in the
  scenario, never free text), with the same "Player-allowed blocks only"
  checkbox as for LootGroups.ecf. The Id is validated live against the game
  limit and existing duplicates in the file.
- **+ Property** — adds a property to the selected block; several pairs can be
  typed at once (`value, param1: X, param2: "Y,Z"`) to stay grouped on the same
  line as the game does
- **+ Row** (table mode only) — dedicated form (Type/Value/params), numbering and
  position calculated automatically. The Value field becomes a dropdown of
  the scenario's real items/blocks (ItemsConfig.ecf/BlocksConfig.ecf)
  rather than free text — available on **all table-mode files**, not just
  LootGroups.ecf; the field stays editable either way if the suggestions
  don't fit. "Player-allowed blocks only" checkbox to exclude POI-reserved
  blocks (those without an `AllowPlacingAt` property) — items are always
  shown, this concept only applies to blocks.

### Deleting and disabling
- **Delete** (right-click) — permanently removes the element, confirmation
  requested for an entire block
- **Disable this block (test)** (right-click a block) — comments the block out
  **at its exact position** (never moved), without deleting it; useful to isolate
  a crash cause by elimination
- **Disabled blocks (test)** (button) — lists all disabled blocks in the file,
  with **Re-enable** per entry

### Filtering and understanding
- **Filter by property...** — shows only blocks having (or not having) certain
  specific properties
- **"Show property explanations for this file" panel** (collapsible, below the
  file name) — hand-made clarified glossary for 17 files (BlocksConfig.ecf,
  ItemsConfig.ecf, Templates.ecf, GalaxyConfig.ecf, GlobalDefsConfig.ecf,
  LootGroups.ecf, MaterialConfig.ecf, StatusEffects.ecf, TokenConfig.ecf,
  TraderNPCConfig.ecf, BlockGroupsConfig.ecf, Containers.ecf,
  DamageMultiplierConfig.ecf, DefReputation.ecf, EGroupsConfig.ecf, Factions.ecf,
  FactionWarfare.ecf); for others, a button auto-translates the original text

### Automatic annotations
Every value change is annotated (if enabled in Options):
`# original: <old_value> -- Mod par <you>`.

### Bulk transform
**"Bulk transform..." button** (toolbar) — numerically modifies several values at
once, for a given property key (e.g. `param1`, `Count`, `HitPoints`):
- **Choosing the property** — type its name directly (autocomplete among keys
  actually present in the open file), or check it in the list just below the
  field, which also shows how many times each property occurs
- **Operations**: Multiply, Add, Set to value, Clamp (min/max), Round
- **Optional filters**: by block kind (e.g. `+Container`), and/or by a specific
  list of identities (Id/Name separated by commas)
- **Recursive by default** — also descends into sub-blocks (notably *Child
  Items*); can be unchecked
- **Full review table** — the preview shows EVERY matching value (never
  truncated), one row per value, each block identified by its **Id and Name
  together** when both exist (easier to recognize than a number alone), with a
  checkbox to include or exclude it and a **freely editable "After" column**
  before confirming: useful for a special case that needs to diverge from the
  general rule (e.g. `MaxCount` must stay at 1 on certain blocks due to a game
  engine limitation, even if the overall rule multiplies everything else by 2)
- **"Check all" / "Uncheck all"** buttons
- Integrates with the tab's normal **Undo (Ctrl+Z)** like any other edit

---

## 4bis. Special case -- Dialogues.ecf

Opening a file named exactly `Dialogues.ecf` automatically switches to a
two-tab container instead of plain ECF editing:

- **Dialogue browser** — structured, navigable, read-only view. Filterable
  list of all dialogues on the left; on the right, for the selected
  dialogue: NPC, displayed text, variables (with their type), executed
  scripts, automatic transitions (`Next_N`/`NextIf_N`) and player choices
  (`Option_N`/`OptionNext_N`/`OptionIf_N`/`OptionExecute_N`) -- every
  transition or choice target is **clickable**, navigating directly to the
  targeted dialogue without having to hunt for it in a list of several
  thousand entries. Broken targets (nonexistent dialogue) show in red;
  reserved sentinels (`End`, `GotoAndReset`, `Return`) are greyed out,
  non-clickable. A **"Referenced by (N)"** section lists every dialogue that
  leads to the one shown.
- **ECF Editing** — the same generic editor as any other .ecf file, for
  actual editing (the browser stays read-only). Both tabs share the same
  in-memory document; an edit made on the editing side is reflected in the
  browser automatically when switching back to it, or after saving.

---

## 5. Editing a YAML file

Navigation tree on the left (key + preview), editable value panel on the right.

- **+ Entry** / **Delete selected entry**
- **Apply this value** — confirms the typed text (also automatically applied on
  selection change or save, no risk of losing an edit by forgetting)
- **Multi-line quoted strings**: a blank line inside quotes becomes an actual line
  break, for correct in-game display (common for playfield descriptions)

### Structured playfield editing (Resources, POI, Creatures)
Any file named `playfield*.yaml` (planets: `playfield.yaml`,
`playfield_static.yaml`, `playfield_dynamic.yaml`) or `space*.yaml` (space
sectors: `space_dynamic.yaml`) automatically opens with a specialized
**4-tab editor**, instead of the generic YAML editor above. A
**"Save (Ctrl+S)"** button stays permanently visible at the top regardless of
the active tab -- along with an "Unsaved changes" indicator -- so you never
have to hunt for the save action in the "Full YAML" tab after editing from
another tab:
- **Resources** — three separate tables, each with its own add dropdown
  (never free text):
  - **Random resources** (`RandomResources`) and **Asteroid resources**
    (`AsteroidResources`) — planetary playfields, list populated from the
    project's real `*Resource` blocks in `BlocksConfig.ecf`
  - **Space resources** (`Resources`) — space playfields only, different
    structure (`AsteroidVoxel01/02/03<Material>` variants, readable name via
    `DisplayName`) — list populated with the same base material (Iron,
    Copper...) as planetary resources, **RegenAfter** column (respawn delay)
    directly editable
- **POI** and **Creatures** — table of already-present entries (delays,
  difficulty, distances, quantities...), columns sorted by usage frequency.
  **Editing only**: no adding a new POI/creature by picking a type, for lack
  of a reliable source to populate such a list (see the Empyrion wiki,
  section 5, for EPD if you need to go further on this specific point).
  - POI: **RegenAfter** column directly editable (nested inside `Properties`
    in the source file, exposed here as a proper column)
  - Creatures: **Biome** column (read-only) — essential once the same
    creature name appears in several different biome zones with different
    parameters, otherwise impossible to tell apart
  - Other nested structured values (e.g. `Position`) stay non-editable here,
    editable via the "Full YAML" tab
- **Drones/Vessels** — editing of already-present entries only, same
  reasoning as POI/Creatures (no reliable source for a dropdown of new
  types):
  - **Drone base garrison** (planet, `DroneBaseSetup > Stock`) — Name +
    Amount
  - **Free patrol drones** (space, `FreeDrones`) and **Space vessels**
    (space, `SpaceVessels`) — the module's richest structure (Faction,
    CountMinMax, Probability...), the most deeply nested fields
    (`MissionDescription`, `StockDescription`) stay non-editable here
  - Each table stays empty if not relevant for the type of playfield opened
    (same principle as the Resources tab)
- **Spawn zones** — editing of already-present entries only:
  - **Drone patrols** (planet, `DroneSpawning > Random`)
  - **Spawn rate modulation around POI** (`SpawnRateZones`)
  - **Creatures tied to a POI** (`SpawnZones`) — different from the
    Creatures tab, which organizes by biome rather than by POI; the
    `Entities` sub-list stays non-editable here, see "Full YAML"
- **Special effects** — purely cosmetic (pollen, butterflies, weather...),
  with no gameplay impact, but covered for complete consistency: **local
  effects per biome** (`SpecialEffectsLocal`) and **global effects**
  (`SpecialEffectsGlobal`)
- **Full YAML** — the same generic editor as above, for everything else in
  the playfield (atmosphere, sky, fog...) — shares the same document
  in memory as the structured views: a change made on one side is
  immediately visible when switching tabs.

---

## 6. Editing a CSV file

- **Search** with a scope selector ("in:" a specific column or all); right-click a
  column header to directly limit a search to it
- **+ Row** / **Selected row** (delete)
- **Clipboard** (right-click) — Copy, Cut, Paste, Clear content, works on a
  multi-selection like a spreadsheet
- The **delimiter** (`,` or `;`) and **line-ending style** are auto-detected and
  preserved

---

## 7. Translation

All functions below use Google Translate (`deep-translator` library, free,
requires an internet connection) and automatically protect BBCode and
placeholders (`{PlayerName}`, `%d`...) — never translated or broken.

### Translation memory
Fully automatic and invisible: once a text is translated to a given language, the
same translation is reused instantly (no new network call) if that exact text
appears again elsewhere — faster, and guarantees full consistency of the same word
throughout the file.

### Cell by cell
Right-click a cell > **"Translate to"** > choose a language — shows a before/after
preview, offers to replace the cell itself or the column matching the target
language on the same row if it already exists.

### Quick translation
**"Translate" button** (toolbar) — directly translates the current cell/selection
to the **default language** (Options > "Default translation language..."), no
submenu. Automatically switches to batch mode if multiple cells are selected.

### Batch (multi-selection)
Multi-select + right-click > **"Translate selection to..."** — progress bar, then
review table before applying.

### Filling missing translations
Dedicated button — choose a source column (filled) and a target column (to
complete); scans the whole file, only translates genuinely empty cells.

### Review table and failure handling
Every batch translation goes through a table (checkboxes, editable text before
confirming) — nothing is written without confirmation. On a very large batch, if
the service temporarily blocks, it stops **automatically after 5 consecutive
failures** with a clear message; translations already completed remain available;
failures are highlighted in red and unchecked by default.

---

## 8. Find and replace (CSV)

**"Find and replace..." button** — fixes text repeated in several places
(typically an approximate machine translation):
- **Find** / **Replace with**
- **In column** — a specific column or all
- **Case sensitive**
- **Whole word only** — avoids touching a word that only contains the searched
  text as a fragment

Just like translation, each match goes through the review table.

---

## 9. BBCode formatting

Right-click > **"BBCode formatting..."** — select a portion of text, click a color
(10-shade palette) or a style (Bold/Italic/Underline) to automatically wrap it in
the right tags (`[color=#FF0000]...[/color]`, `[b]...[/b]`...).

---

## 10. Copying, merging and duplicating from Scenario A or B

### Copy/merge
Right-click (file, folder, block, row, entry) > **"Copy / merge into working
copy"** — combines source content into the working copy. **Disabled by default**
(too many edge cases to be 100% reliable), re-enableable in **Options > "Allow
merging"**.

Behavior by file type:
- Existing **.ecf**: smart block-by-block merge — the working copy always takes
  priority (nothing overwritten), missing blocks/properties are added
- Existing **.csv**: merge by key (1st column) — an existing row is never
  overwritten, only empty cells are filled in, missing rows are added
- **Other formats** (yaml, txt...): simple copy that replaces the existing file

**Anti-collision safeguard**: if an Id is shared between two blocks with different
`Name`, the block is never blindly merged — it's added at the end of the file,
**disabled**, for manual review (see "Pending blocks" below).

### Duplicate
Right-click (file, block, row, entry) > **"Duplicate with a new Id/key..."** —
**always available**, systematically creates an **independent** copy (new
Id/name, free-Id suggestions provided), never overwriting anything. Also works on
blocks without an Id (identified only by `Name`), lets you drop the duplicate's
Id to identify it by Name only, and keeps a nested sub-block within the same
parent block.

### Undoing a merge/duplication
Global **"Undo last action"** button (top of the window, distinct from the
per-tab "Undo (Ctrl+Z)").

---

## 11. Verification

### Check references
**Verification > Check references** — checks that every `Ref:`, `TemplateRoot`
and similar reference points to an existing name.

### Pending blocks
**Verification > Pending blocks** — lists all blocks put on hold by the
anti-collision safeguard, with a detailed comparison (current block vs pending)
and free-Id suggestions to activate it properly.

### Cross-file references
**Verification > Check cross-file references...** — unlike "Check references"
above (which only looks at `Ref:` within ECF files), this checks that whatever
a file mentions **genuinely exists elsewhere** in the scenario. Three
independent checks, each individually toggleable:
- **Ref inheritance** — same as the classic check above, included here so
  everything can be checked in one place
- **Referenced items/blocks** — does every `Name_N` entry (Templates.ecf,
  Containers.ecf, LootGroups.ecf...) match an item or block that genuinely
  exists in ItemsConfig.ecf or BlocksConfig.ecf? (both files are checked
  together: a picked-up block becomes an item of the same name, they share
  the same namespace)
- **Tokens** — does every `Token:XXXX` reference match a token genuinely
  defined in TokenConfig.ecf?
- **Dialogues** — does every `Next_N`/`OptionNext_N` target (and its
  optional co-occurring `param1`) match a dialogue (`+Dialogue Name:`) that
  genuinely exists? Reserved dialogue-engine keywords (`End`,
  `GotoAndReset`, `Return`) and dynamic script-variable references
  (`@VariableName`, resolved at runtime) are never flagged -- only genuinely
  broken references are.

Every issue found shows the **full path** of the file involved —
**double-click a result to directly open the relevant file and jump to the
exact block/sub-block**, cell included, without having to search
for the problem yourself.

### Validate business rules
**Verification > Validate business rules...** — unlike the two checks above
(which focus on references), this one checks **values**: the game's Id
limit (8192, confirmed via official Eleon v1.17 patch notes), container
classes requiring `VolumeCapacity` (with `Ref:` inheritance resolution),
recognized materials and `HoldType`, unquoted commas in list properties
(`AllowPlacingAt`, `ChildBlocks`), `BlockColor` format, duplicate Id/Name,
and a few suspicious numeric values (negative or zero
`HitPoints`/`Mass`/`MaxCount`). Every rule is grounded in a direct check
against real game files or an official source -- never assumed.

Some rules (materials, `VolumeCapacity`, Name duplicates) only apply to
`BlocksConfig.ecf`, and `HoldType` only to `ItemsConfig.ecf` -- the same
word ("Material", "Class: Container"...) means something different
depending on the file (e.g. an entity's loot container in
`EClassConfig.ecf` doesn't follow the same rule as a block container),
confirmed directly against real game files before ruling out this
confusion.

Double-click a result to open the file and jump to the relevant block, same
as for cross-file references. An error/warning filter is available at the
top of the dialog.

### Potentially unused tokens
**Verification > Potentially unused tokens...** — a direct suggestion from
a community member (Begebum, Steam comment): lists tokens defined in
`TokenConfig.ecf` but never referenced (`Token:XXXX`) elsewhere in the
scenario. Purely informational, never an error — some tokens may be used
implicitly by the game without an explicit reference. Deliberately
restricted to tokens (unlike generic blocks/items, where a lack of
reference means nothing -- a basic building block doesn't need to be
"referenced" to be useful, it's simply placed in-game).

### Scenario health check
**Verification > Scenario health check...** — runs the 4 checks above in
one click and shows a consolidated summary (green/no issues or red/issue
count per category), with a "View details" button that opens the real full
window for that category. Doesn't reimplement any display — just a single
entry point for a quick status overview without opening 4 separate windows
one by one.

---

## 12. Backups

### Scenario backups
**File > Back up a scenario (before update)...** — a full copy before a Steam
Workshop update overwrites the scenario in place.

### Savegame backups
**File > Manage my savegame backups...** — same principle for game progress, with
**Restore** (a safety backup is automatically created before any restore).

The manager offers in both cases: Back up now, Restore, Open folder, Delete
(confirmation requested), and for scenarios only, **Compare with...** (directly
opens the comparison tool).

---

## 13. Comparing two scenarios

**File > Compare two scenarios...** — independent from the currently open
project, compares any two folders:
- Tree color-coded by status (added / removed / modified / unchanged)
- Precise change details (block-by-block for ECF, row-by-row for CSV, key-by-key
  for YAML)
- **Also show identical files** (checkbox)
- **Export report...** (complete text file)

---

## 13bis. Search across the whole scenario

**File > Search in scenario...** — unlike the existing searches (filter by
property in ECF, CSV search) which work within the open file, this one
scans **every file of the working copy** at once: ECF (kind, Id/Name, every
property including nested), playfield YAML (every entry), CSV (each row).
Double-click a result to directly open the relevant file and jump to the
exact block/entry -- same navigation mechanisms as the verification
windows.

Known limitation: CSV results open the relevant file without navigating to
the exact row (no row-selection mechanism currently built for the CSV
editor).

---

## 13ter. Creating a PDA mission

**File > New PDA mission...** — guided creation of a mission (a PDA Chapter
with its Task and objective), automatically locates
`Extras/PDA/PDA.yaml` and `PDA.csv` in the open scenario. Structure
confirmed on a real file (530 chapters, same authors as `Dialogues.ecf`):
Chapter > Task > Action.

Two objective types handled:
- **Kill enemies** — target creature/entity names (suggestions drawn from
  names already used elsewhere in the same `PDA.yaml`, free text also
  possible), required amount
- **Destroy a structure OR mine a resource** — same underlying game
  mechanism (`BlockDestroyed`): destroying an enemy base/ship's core and
  mining a resource are technically the same thing (a mined resource is a
  destroyed block). The **Types** field distinguishes the two (`CoreNPC`
  for an enemy structure, `IronResource`/`CopperResource`... for a
  resource) — suggestions drawn from Types already used in the same file.
  For mining specifically, the **Target names** field also automatically
  suggests real planetary resource blocks (`BlocksConfig.ecf`, e.g.
  `IronResource`) and space asteroid variants
  (`AsteroidVoxel01/02/03<Material>`, confirmed technical pattern from
  space playfields) — switches automatically based on the chosen objective
  type.

**Rewards**: XP, UP (skill points), Reputation (with faction choice), or
Item (dropdown populated with the scenario's real items/blocks, same
infrastructure as the Template ingredient picker, with the same
"Player-allowed blocks only" checkbox) — several rewards possible per
mission. For a money reward: pick **`MoneyCard`** if offered (automatically
placed at the top of the list when it exists in `ItemsConfig.ecf`) — 1 card
= 1 credit, confirmed on a real scenario file (`## Please do not rename -
referenced in code` comment right above its definition). <span
style="color:#7c859c"><i>The literal name "Credits" does NOT work despite
what the game's community wiki suggests — disproven on two real client logs
(v1.19.2): the reward is systematically rejected by the engine.</i></span>

**Repeatability** (single-tier missions only): "Repeatable mission"
checkbox, with number of repeats and delay before reactivation (in hours)
— matches the game's real `RepeatConditions` mechanism (repeats the SAME
objective/reward IDENTICALLY).

**Tiers** — **"+ Add a tier"**: for a staged mission with a DIFFERENT
objective/reward at each step (e.g. tier 1 = mine 1000 units -> reward X,
then tier 2 = mine 2000 units -> reward Y, etc.), each tier gets its own
title, description, objective and rewards. Real mechanism confirmed on an
actual in-game chain (50 -> 100 -> 35 kills across 3 successive chapters):
each tier becomes a **distinct PDA Chapter**, never a repeat of the same
chapter — the first is immediately available, each next one only activates
once the previous is rewarded (`RewardedChapters` + `Activatable:
WhenRewarded`). The "Repeatable mission" checkbox is automatically disabled
as soon as a second tier exists: the two mechanisms never combine in the
game.

Files are opened as **real tabs** of the working copy (never a direct disk
write) — nothing is saved until you click Save yourself on those two tabs.

<span style="color:#7c859c"><i>Assumed limitation ("Kill enemies" objective
only -- mining gets real suggestions, see above): target names specific to
a given blueprint (e.g. the custom name of a "core" block specific to one
particular enemy ship) are not automatically extracted from blueprint
files (`.epb`) -- same risk category as game saves (undocumented
proprietary binary format, no licensed reusable community tool). Only
names already used elsewhere in the same `PDA.yaml` are suggested; free
text remains always possible.</i></span>

---

## 14. Extracting scenario properties

**File > Extract scenario properties...** — scans every .ecf file from a source
(working copy, Scenario A or B) and builds a working CSV glossary:
- Every property, with occurrence count, files involved, example values, and an
  automatic description when recognized unambiguously
- Numbered keys (`Name_0`, `Name_1`...) are grouped under a generic entry
  (`Name_N`)
- An empty **"Target value"** column, to fill in as you work through your design

The resulting file opens automatically, directly editable.

---

## 15. Maintenance

### Repairing permissions
**File > Repair working copy permissions** — instantly unlocks a working copy
that's become impossible to modify/delete (read-only attribute inherited from the
source, common under Program Files). Every file save already attempts this repair
automatically in the background; this button is only useful in rare residual
cases.

---

## 16. Options

**Options** menu, global settings valid for all projects:
- **Name for annotations...** — name used in automatic comments
- **Automatically annotate changes** (checkbox)
- **Allow merging** (checkbox, disabled by default)
- **Online translation (Google Translate)** (checkbox, enabled by default) --
  uncheck to fully disable sending text to Google; see `PRIVACY.md`
- **Autosave (crash recovery)** (checkbox, enabled by default) -- see
  section 12bis below
- **Default translation language...** — language used by the quick "Translate"
  button

---

## 12bis. Autosave and crash recovery

Every 3 minutes, each modified-but-not-yet-saved tab is saved into a
recovery folder **separate** from the real working copy — never written to
the real scenario files until the user explicitly clicks Save. As soon as a
file is genuinely saved, its recovery snapshot is immediately removed.

If the application closes unexpectedly (crash, power loss...) while
recovery snapshots still exist for a scenario, a window offers to
**restore** them (writes directly to the real working-copy files, before
any tab is reopened) or **discard** them permanently -- on opening or
resuming that scenario.

Can be disabled via **Options > Autosave**.

---

## 16bis. Visual theme

**Options > Theme** — 8 selectable themes, switches immediately without
restarting:
- **Classic** — original theme (blue/navy admin dashboard), stays the
  default until another one is explicitly chosen
- **A — Mission control** — dark, cyan/amber, spaceship control panel feel
- **B — Drafting table** — light, technical blueprint blue
- **C — Engineering terminal** — warm dark, copper/teal
- **D — Night crystal** — dark, violet/cyan
- **E — Sun crystal** — light, violet/cyan
- **F — Dusk** — mid-tone slate, designed for comfortable multi-hour use
  (moderate contrast, off-white rather than pure white)
- **G — Mother-of-pearl** — light, iridescent multicolor gradient menu bar

<span style="color:#7c859c"><i>Assumed limitation: these themes are a
faithful color/gradient approximation of the original mockups, but without
the real frosted-glass background blur -- PyQt6 Widgets doesn't support it
natively (would require Windows 11's Acrylic/Mica API, or a rewrite in Qt
Quick/QML).</i></span>

---

## 17. Help

- **Help > Tutorials...** — built-in step-by-step tutorial module, navigable
  (Previous/Next), with at minimum "Create a block, step by step" and "Complete
  application walkthrough"
- **Help > Application wiki (functions)...** — this document
- **Help > Empyrion wiki (properties, files, structure)...** — documentation of
  the game itself (file structure, conventions, known pitfalls)
- **Help > Check for updates...** — manual check; an automatic, silent check
  also happens at startup (only shows something if an update genuinely exists)
- **Help > Report a bug / suggest an improvement...** — opens a pre-filled
  GitHub form in your browser (title, description, recent actions, technical
  info like version and OS); **nothing is sent automatically**, you must
  review and click "Submit" yourself on the GitHub page. A screenshot (taken
  the moment you click the menu) is saved locally to
  `~/.empyrion_editor/bug_reports/` — drag and drop it into the GitHub form to
  include it (no technical way to attach it automatically via a plain link).
  **Also directly accessible via the "Report" button in the top bar**, without
  going through this menu.
- **Help > About...** — application version, license notice, and the same
  clickable GPLv3 badge as the one in the top bar

### Direct shortcuts in the top bar
Besides the Help menu, two buttons stay permanently accessible at the top of
the main window, next to the FR/EN language button:
- **"Report" button** — direct shortcut to the bug report form
- **GPLv3 badge** — direct click-through to the official license text online

---

## 18. Diagnostic scripts (command line)

Complements to the graphical interface, available two ways depending on how you
got the application:

### If you installed via the Windows installer
A single executable bundles every tool: `EmpyrionEditorCLI.exe`, installed in a
`CLI\` subfolder of the installation directory (kept separate from the
graphical app to avoid any conflict between their respective internal files).
From a terminal (Command Prompt or PowerShell), in that subfolder:

```
CLI\EmpyrionEditorCLI.exe <command> [arguments...]
```

Run it with no argument to see the full list of available commands.

### If you're using the Python sources directly
Each tool also remains available as a standalone script, run from a terminal in
the project folder:

| Command (`EmpyrionEditorCLI.exe`) | Equivalent script (sources) | Usage |
|---|---|---|
| `verifier-ecf <file_or_folder>` | `python verifier_parser_ecf.py ...` | Checks round-trip (perfect fidelity) of one or more ECF files |
| `verifier-yaml <file_or_folder>` | `python verifier_parser_yaml.py ...` | Same for YAML |
| `verifier-csv <file_or_folder>` | `python verifier_parser_csv.py ...` | Same for CSV |
| `diagnostic-bloc <file.ecf> <Id>` | `python diagnostic_bloc.py ...` | Finds a specific block by Id, including within comments |
| `detecter-imbrication <file.ecf>` | `python detecter_imbrication_anormale.py ...` | Detects blocks that mistakenly "swallowed" the rest of the file |
| `diff <fileA.ecf> <fileB.ecf>` | `python diff_ecf.py ...` | Compares two ECF files, shows added/removed/modified blocks |
| `edit <file.ecf>` | `python edit_ecf.py ...` | Interactive command-line ECF editor |
| `merge <output.ecf> <source1> <source2>...` | `python merge_ecf.py ...` | Merges several ECF files by priority order |
| `transform` | `python transform_ecf.py` | Applies a bulk numeric transformation (multiply/add/set/cap) on a property, for a given block kind |

---

## 19. 2D map, POI inspector, and galaxy map

### 2D map of a playfield
First tab of the structured playfield editor (see section 8) — top-down
(X/Z axis) view of positionable entities: fixed POIs (draggable, with
direct YAML write-back), resolved random POIs (when they reference a fixed
POI via `SpawnPOINear`), player start points, drone patrols. Filter by
entity kind, mouse-wheel zoom.

Some entries deliberately have **no position shown** rather than a made-up
approximation: space resources (the `RadialInfo` field is not a direct
cartesian coordinate, confirmed on a real file), and most random POIs (they
most often reference another random POI rather than a fixed one, an
unresolved chain in this first version).

### POI inspector
**"POI Inspector..."** button above the POI tab's table — non-modal window
with two views: per-POI detail (count, estimated drones) and per-faction
aggregation (total estimated drones per faction on this playfield). Covers
random POIs only (fixed POIs don't have these count/probability fields).
Export and refresh available, same as the verification windows.

### Galaxy map
**File > Galaxy map (Sectors.yaml)...** — map of the scenario's solar
systems, automatically locates `Sectors/Sectors.yaml`. Purple for special
system roles (Gate, Anomaly, HomeSystem...), orange for genuine star
spectral classes (A, K2V, M2...); dot size proportional to the system's
local sector count. No warp routes are shown between systems: this data
isn't declared in `Sectors.yaml` (likely computed by the game engine from
proximity), impossible to reliably reconstruct.

**"Tilt (Y axis)"** slider below the map: the base view only shows X/Z
(top-down, galactic height ignored) -- increasing the tilt visually shifts
each system according to its real Y, useful when several systems close in
X/Z (e.g. along a beacon chain) overlap on screen despite very different
heights.

---

## 20. Known limitations

- No spreadsheet-style multi-line copy/paste for YAML (structure too nested)
- "Smart" merging (working-copy priority, completion) only exists for ECF and CSV
  — other formats are fully replaced during a file merge
- Translation requires an internet connection (Google Translate, free unofficial
  service — may temporarily block on very large volumes, see section 7)
