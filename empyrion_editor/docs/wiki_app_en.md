# Application Wiki — Empyrion Scenario Editor

Documentation of every function of the tool, organized by topic.

---

## 1. The basics: projects and working copy

### New project
**File > New project...** — Choose a Scenario A (required), and if you want to merge two scenarios, check "Merge mode" and choose a Scenario B. Then pick a destination folder (must not already exist): this is your **working copy**.

On creation, the tool copies the **entire, exact** content of Scenario A into the destination folder (all files, not just .ecf/.csv/.yaml). Nothing is invented or transformed during the copy.

### Working copy vs sources
- **Scenario A / Scenario B**: shown at the bottom, **read-only**. These are your references, never modified by the tool.
- **Working copy**: shown in the middle, **editable**. This is the only place you edit, merge, or duplicate.

### Recent projects
**File > Recent projects...** (or automatically offered at startup) — resumes an existing project **without recopying** the working copy (your previous changes stay intact). Useful for continuing work across multiple sessions.

### Folder tree
All three panels (A, working copy, B) show **the exact folder structure from disk** — like a regular file explorer, no artificial categorization.

---

## 2. Merging from Scenario A or B

### Merging a whole file
Right-click a file in Scenario A or B > **"Copy / merge to working copy"**.

- If the file doesn't exist yet in the working copy: plain copy.
- If it's an existing **.ecf** file: smart per-block merge (see below).
- If it's an existing **.csv** file: merge by key (1st column) — the working copy is **always prioritized**: a row whose key already exists is never overwritten, only **empty** cells get filled in; missing rows are added.
- Other formats (yaml, txt...): plain copy that **replaces** the existing file (no smart merge for these formats).

### Merging a whole folder
Right-click **any folder** > "Merge this folder (and subfolders)" — applies the same logic to every file it contains, in a single action. A progress bar shows for large folders.

### ECF merge — how it works precisely
- The working copy is **prioritized**: its existing properties and blocks are never overwritten.
- Blocks and properties **missing** from the working copy are added.
- **Anti-collision safeguard**: if an Id is shared between two blocks whose `Name` differs (same Id, different content — happens between independent scenarios), the block is **never blindly merged**. It's added at the end of the file, **disabled** (commented out), for manual review (see "Pending blocks" below).

### Copying a single block / a single row
Right-click a block in the ECF tree, or a CSV row, in the Scenario A/B view > "Copy this block/row to working copy" — merges **only that element**, leaving the rest of the file untouched.

### Duplicating with a new identifier
Right-click a read-only ECF block or CSV row > "Duplicate with a new Id/key..." — unlike "copy/merge", this creates a **fully independent element** (no merge), letting you choose a new Id and/or a new Name (with free-Id suggestions). Handy to start from an existing block as a template for a new, distinct one (e.g. a variant of an item).

- Also works on blocks **without an Id** (identified only by `Name`) — a real case in some Empyrion files.
- You can also **drop the Id** on the duplicate, leaving it identified by Name only.
- If you duplicate a **nested sub-block** (e.g. a `Mode` inside an `Item`), it automatically stays **inside the same parent block** in the working copy (not orphaned at the root).
- Same logic available for YAML (duplicating an entry with a new key/value).

---

## 3. Editing the working copy

### ECF files
Double-click a `.ecf` in the working copy: opens a **comparison view** (your copy on the left, editable; Scenario A/B on the right, read-only, in tabs).

- **Double-click a value** in the property table to edit it.
- **+ Block** / **+ Property** to add.
- Right-click a property: **Delete**, **Translate to...**, **BBCode formatting...**
- Every value change is **automatically annotated**: `# original: <old_value> -- Mod by <you>` (configurable in **Options**).

### CSV files
Double-click a `.csv`: editable table.
- **+ Row** / **Delete selected row**.
- Right-click: Copy/Cut/Paste (Excel-compatible, tab-delimited), **Clear content** (empties the cell) vs **Delete entire row** (two distinct actions), Translate, BBCode.
- The **delimiter** (`,` or `;`) and **line-ending style** are auto-detected and preserved.

### YAML files
Double-click a `.yaml`/`.yml`: navigation tree on the left (key + preview), editable value panel on the right with an **"Apply this value"** button — better suited than in-cell editing given the nested structure of playfields.
- **+ Entry** / **Delete selected entry**.
- Translation and BBCode available on the value being edited.

### TXT files
Double-click a `.txt`: simple text editor. Native copy/cut/paste (Qt), plus translation and BBCode on a selection via right-click.

### Copy / Cut / Paste (CSV and ECF tables)
`Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Delete` work on tables, using an Excel-compatible format (tabs). The "Key" column of an ECF property table stays write-protected (can't be changed by an accidental paste).

---

## 4. Translation

Available everywhere you edit text (CSV, ECF, YAML, TXT), via right-click > **"Translate to..."**. Uses Google Translate (`deep-translator` library, free, requires an internet connection).

- **BBCode and placeholder protection**: tags (`[b]`, `[color=#RRGGBB]`...) and substitution tokens (`{PlayerName}`, `%d`, `%s`...) are automatically extracted before translation and reinserted in place — never translated or broken.
- **CSV translation targets the right column**: right-click a source cell (e.g. the `English` column) and pick the target language (e.g. `Francais`) — the result goes into the matching column (e.g. `Français`), not the source cell. Column matching is accent-insensitive and recognizes several naming conventions (ISO code, English name, native name).
- **From Scenario A/B (read-only)**: you can translate a source cell directly and the result gets applied to the matching cell in the **working copy**.
- The result window lets you **review and correct** the translation before applying it.

## 5. BBCode formatting

Right-click > **"BBCode formatting..."** opens a small window: select a portion of text with the mouse, click a color (10-swatch palette) or a style (Bold/Italic/Underline) to automatically wrap it in the right tags (`[color=#FF0000]...[/color]`, `[b]...[/b]`...).

---

## 6. Checks

### Check references (Verification menu)
Checks that every `Ref: X` matches an existing `Name: X` somewhere in the scenario — `Ref` is Empyrion's inheritance mechanism, a broken reference fails silently in-game (no error message, just missing properties). Run this after a merge.

### Pending blocks (Verification menu)
Lists every block put on hold (disabled) by the merge's anti-collision safeguard. For each one:
- **Detailed comparison** with the currently active block (property-by-property diff).
- **Free-Id suggestions** (computed above the highest Id currently used in the scenario).
- A button to **activate** the block with the chosen new Id — avoids editing the file by hand (real risk of breaking the structure if the closing `}` line stays commented out by mistake).

### Filter by property
In an ECF file view, the **"Filter by property..."** button lists every property that exists in the file (with its occurrence count); check one or more to filter the tree live (hides blocks that don't have all of them).

### Search
Every file view has a search bar (Id / Name / key / value depending on the format) with "next" navigation — essential once a file goes beyond a few hundred entries.

---

## 7. Options

**Options > Name for annotations...** — the name that appears in traceability comments (`Mod by <name>`).

**Options > Automatically annotate changes** — enables/disables automatic annotation.

**Language button (toolbar)** — switches the interface between French and English instantly, no restart needed. The choice is saved between sessions.

---

## 8. Diagnostic scripts (command line)

Useful alongside the interface, run from a terminal in the project folder:

- `verifier_parser_ecf.py <file_or_folder>` — checks round-trip fidelity (perfect reproduction) of one or more ECF files.
- `verifier_parser_yaml.py <file_or_folder>` — same for YAML.
- `verifier_parser_csv.py <file_or_folder>` — same for CSV.
- `diagnostic_bloc.py <file.ecf> <Id>` — looks for a specific block by Id, including inside comments (useful if a block seems to have disappeared).
- `detecter_imbrication_anormale.py <file.ecf>` — detects blocks that have mistakenly "swallowed" the rest of the file (typically after a manual edit that left a closing brace commented out).

---

## 9. Known limitations

- No spreadsheet-style multi-row copy/paste for YAML yet (the structure is too nested for that to make sense the same way).
- "Smart" merge (working-copy priority, gap-filling) only exists for ECF and CSV. Other formats (YAML, TXT...) are replaced entirely during a file merge.
- Translation requires an internet connection (Google Translate).
