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
- **+ Block** — creates a brand new, entirely empty block (choose the kind: Block,
  Item...)
- **+ Property** — adds a property to the selected block; several pairs can be
  typed at once (`value, param1: X, param2: "Y,Z"`) to stay grouped on the same
  line as the game does
- **+ Row** (table mode only) — dedicated form (Type/Value/params), numbering and
  position calculated automatically

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
- **Operations**: Multiply, Add, Set to value, Clamp (min/max), Round
- **Optional filters**: by block kind (e.g. `+Container`), and/or by a specific
  list of identities (Id/Name separated by commas)
- **Recursive by default** — also descends into sub-blocks (notably *Child
  Items*); can be unchecked
- **Full review table** — the preview shows EVERY matching value (never
  truncated), one row per value, with a checkbox to include or exclude it and a
  **freely editable "After" column** before confirming: useful for a special
  case that needs to diverge from the general rule (e.g. `MaxCount` must stay
  at 1 on certain blocks due to a game engine limitation, even if the overall
  rule multiplies everything else by 2)
- **"Check all" / "Uncheck all"** buttons
- Integrates with the tab's normal **Undo (Ctrl+Z)** like any other edit

---

## 5. Editing a YAML file

Navigation tree on the left (key + preview), editable value panel on the right.

- **+ Entry** / **Delete selected entry**
- **Apply this value** — confirms the typed text (also automatically applied on
  selection change or save, no risk of losing an edit by forgetting)
- **Multi-line quoted strings**: a blank line inside quotes becomes an actual line
  break, for correct in-game display (common for playfield descriptions)

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
- **Default translation language...** — language used by the quick "Translate"
  button

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
  include it (no technical way to attach it automatically via a plain link)

---

## 18. Diagnostic scripts (command line)

Complements to the graphical interface, available two ways depending on how you
got the application:

### If you installed via the Windows installer
A single executable bundles every tool: `EmpyrionEditorCLI.exe`, installed
alongside the graphical app (same folder). From a terminal (Command Prompt or
PowerShell), in that installation folder:

```
EmpyrionEditorCLI.exe <command> [arguments...]
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

## 19. Known limitations

- No spreadsheet-style multi-line copy/paste for YAML (structure too nested)
- "Smart" merging (working-copy priority, completion) only exists for ECF and CSV
  — other formats are fully replaced during a file merge
- Translation requires an internet connection (Google Translate, free unofficial
  service — may temporarily block on very large volumes, see section 7)
