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

"""
MIROIR ANGLAIS du protocole de test manuel -- traduction des titres,
preconditions, etapes et resultats attendus de core/test_protocol.py.

FORMAT : EN = {id_du_cas: {"titre": ..., "pre": ..., "etapes": [...],
"attendu": ...}}. Regles :
- Un echange par Id de cas ; les champs absents retombent sur le FR.
- "etapes" : MEME NOMBRE d'etapes que le FR, MEME FORME (chaine ou dict).
  Les dict ne portent QUE "txt" : les commandes copiables ("cmd") restent
  dans le FR et sont reprises telles quelles (une commande console ne se
  traduit pas).
- Un test d'integrite (tests/test_protocole_cas.py) verifie la synchro :
  cas manquant, etape en trop/manquante ou forme divergente = echec.
"""
from __future__ import annotations

EN: dict = {
    # ---------------------------------------------------------------- PROJ
    "PROJ-001": {
        "titre": "New project: standard creation from Scenario A",
        "pre": "A valid Empyrion scenario folder is available (Scenario A) -- for example a copy of the game's Content/Scenarios/EmpyrionFrontier.",
        "etapes": [
            "Start the application: double-click its icon (desktop or Start menu > Empyrion Scenario Editor).",
            "In the menu bar at the very top of the window, click File, then New project...",
            "To the right of the Scenario A field, click the Browse button (the « ... » button), navigate to your scenario folder, select it, then click the Select Folder button.",
            "To the right of the Working copy field, click Browse, go where you want to create the project, type a folder name that DOES NOT EXIST YET (e.g. MyScenario-Work), then click Select Folder.",
            "Do NOT fill in the Scenario B field: it is optional and this test covers a project without B.",
            "Start the creation by clicking the Create button of the window.",
        ],
        "attendu": "The working copy is created and selected automatically; the central « Working copy » panel fills with the scenario tree; the original Scenario A is untouched (no file modified inside).",
    },
    "PROJ-002": {
        "titre": "New project: with optional Scenario B",
        "pre": "TWO DIFFERENT scenario folders (A and B) -- for example the game's EmpyrionFrontier and Atlantis.",
        "etapes": [
            "File > New project... (same opening as PROJ-001).",
            "Fill Scenario A with your first scenario (Browse button « ... » as in PROJ-001).",
            "Fill the Scenario B field with the SECOND scenario, different from the first.",
            "Fill the Working copy with a new folder name, then click Create.",
        ],
        "attendu": "All three panels are filled (A on the left, working copy in the center, B on the right); panel B's title carries the « read-only » mention.",
    },
    "PROJ-003": {
        "titre": "New project: refusal if the destination already exists",
        "etapes": [
            "File > New project...",
            "Fill Scenario A normally.",
            "For the Working copy, click Browse and VOLUNTARILY pick a folder that ALREADY EXISTS (for example the Scenario A folder itself).",
            "Click Create and observe.",
        ],
        "attendu": "A clear error message is shown (existing destination); nothing was written anywhere; the chosen folder is intact.",
    },
    "PROJ-004": {
        "titre": "Faithful copy: every scenario file is duplicated",
        "etapes": [
            "In Windows File Explorer, right-click the Scenario A folder > Properties: note the reported file and folder counts.",
            "Create a project from this scenario (PROJ-001).",
            "Right-click the working copy folder > Properties: compare the counts.",
        ],
        "attendu": "Same file count, same subfolders: the copy is a complete mirror of the scenario (not only the .ecf/.yaml/.csv files).",
    },
    "PROJ-005": {
        "titre": "Recent projects: offered at startup",
        "pre": "At least one project has already been created (PROJ-001).",
        "etapes": [
            "Close the application if open (X button at the top right of the window), then start it again.",
            "Watch the startup window (or screen) that appears before the main window.",
        ],
        "attendu": "The recent projects list is offered; the Open selection button reloads the chosen project (all three panels fill).",
    },
    "PROJ-006": {
        "titre": "Recent projects: reopening WITHOUT copying (work intact)",
        "pre": "An existing project whose saved modification is already visible on disk.",
        "etapes": [
            "Open a project, change a value in a tab (e.g. a block title), save with Ctrl+S (Ctrl and S keys together), then close the application.",
            "Start the application again and reopen the SAME project via Recent projects (PROJ-005).",
            "Reopen the modified file: double-click the file in the Working copy panel.",
        ],
        "attendu": "The previous modification is still there: the working copy was NOT copied over from Scenario A when reopened.",
    },
    "PROJ-007": {
        "titre": "Three panels: A/B read-only, center editable",
        "etapes": [
            "In the Scenario A panel (left), expand the tree (small arrows) then double-click BlocksConfig.ecf.",
            "Watch the opened tab: try the + Block button if visible, and look for a Save button.",
            "Close that tab (X on the tab), then double-click the SAME BlocksConfig.ecf file in the Working copy panel (center).",
            "Compare this tab's available buttons with the Scenario A tab's.",
        ],
        "attendu": "Scenario A: read-only tab (padlock prefix, no + Block / no saving). Working copy: editable tab (pencil prefix ✎, editing tools active).",
    },
    "PROJ-008": {
        "titre": "Exact disk tree in all 3 panels",
        "etapes": [
            "Place File Explorer and the application side by side (Windows key + Left arrow to dock Explorer on the left, then Windows key + Right arrow on the application).",
            "Compare, folder by folder, the Scenario A panel tree with the real disk content (subfolders and files).",
        ],
        "attendu": "The displayed tree matches the disk exactly: no invented category, no hidden or added file.",
    },
    "PROJ-009": {
        "titre": "Change Scenario B on the fly",
        "pre": "An open project with an active Scenario B (PROJ-002).",
        "etapes": [
            "File > Change Scenario B...",
            "In the folder picker, select a DIFFERENT scenario folder than the current one, then click Select Folder.",
            "A confirmation appears: read it, then confirm the replacement.",
        ],
        "attendu": "Confirmation is indeed requested; after validating, panel B shows the NEW scenario tree; the working copy did not move.",
    },
    "PROJ-010": {
        "titre": "Remove Scenario B",
        "pre": "An open project with an active Scenario B.",
        "etapes": [
            "File > Remove Scenario B.",
            "Watch the three panels after the operation.",
        ],
        "attendu": "Panel B greys out or disappears; the working copy and panel A are unchanged.",
    },
    "PROJ-011": {
        "titre": "Open a Scenario B when none is active",
        "pre": "An open project WITHOUT Scenario B (after PROJ-010 for example).",
        "etapes": [
            "File > Open a Scenario B...",
            "Select a scenario folder then click Select Folder.",
        ],
        "attendu": "Panel B activates and shows the chosen folder's content, read-only.",
    },
    "PROJ-012": {
        "titre": "First launch: language screen (once only)",
        "pre": "Simulate a very first launch: close the application, then rename the configuration folder (see the copyable path) by adding « -old » at the end.",
        "etapes": [
            {
                "txt": "Open the configuration folder in File Explorer: paste the path below into the Explorer address bar (the bar showing This PC) then press Enter. Rename .empyrion_editor to .empyrion_editor-old (right-click > Rename).",
            },
            "Start the application: the language choice screen appears (Français / English). Pick a language.",
            "Close then start the application a second time.",
        ],
        "attendu": "The language screen appears only on the FIRST launch; the choice applies immediately (whole UI in the chosen language) and is kept on the second launch.",
    },
    "PROJ-013": {
        "titre": "Automatic startup tutorial + don't show again",
        "etapes": [
            "When the application starts, let the tutorial open by itself (don't close it right away).",
            "In the tutorial window, tick « Don't show automatically at startup », then close the window.",
            "Close the application and start it again.",
        ],
        "attendu": "On the next start the tutorial no longer opens by itself; it stays available on demand via Help > Tutorials...",
    },
    "PROJ-014": {
        "titre": "FR/EN button: switch without losing work",
        "pre": "An open project with a tab holding an unsaved modification (tab title red with a pencil).",
        "etapes": [
            "Click the FR/EN button at the top right of the window.",
            "Watch the menus, the panels and the modified tab.",
        ],
        "attendu": "The whole interface switches to the other language; the modified tab stays open and still marked as modified (nothing is lost).",
    },
    "PROJ-015": {
        "titre": "New project: unwritable destination refused BEFORE copying",
        "pre": "A destination folder whose writing will fail (e.g. a path whose parent is actually a FILE, or a network folder without write permission).",
        "etapes": [
            "File > New project...",
            "Fill Scenario A normally.",
            "For the Working copy, type (or paste via Browse) the impossible destination you prepared.",
            "Click Create and observe.",
        ],
        "attendu": "Immediate error message « Destination folder not writable »; the copy did NOT start; no partial folder was created.",
    },
    # ---------------------------------------------------------------- OPEN
    "OPEN-001": {
        "titre": "Double-click working-copy file: editable tab",
        "etapes": [
            "In the central Working copy panel, expand the tree until you find BlocksConfig.ecf.",
            "Double-click BlocksConfig.ecf (two quick clicks).",
            "Watch the new tab's title and try clicking a block's property value in the table.",
        ],
        "attendu": "A tab opens, prefixed with the pencil ✎ (editable): values can be edited, the editing buttons (+ Block, + Property, Save) are active.",
    },
    "OPEN-002": {
        "titre": "Double-click Scenario A/B file: read-only",
        "etapes": [
            "In the Scenario A panel (left), find the SAME BlocksConfig.ecf file.",
            "Double-click it.",
            "Compare with the working-copy tab (OPEN-001): title prefix, available buttons, attempt to change a value.",
        ],
        "attendu": "The tab is prefixed with the padlock 🔒 (read-only): no modification possible, no saving.",
    },
    "OPEN-003": {
        "titre": "Already-open tab: reselect instead of duplicate",
        "etapes": [
            "Double-click BlocksConfig.ecf of the working copy once: the tab opens.",
            "Without closing that tab, double-click the SAME file in the tree a SECOND time.",
        ],
        "attendu": "The second double-click selects (brings to front) the already-open tab instead of opening a second copy: there are never two tabs for the same file.",
    },
    "OPEN-004": {
        "titre": "Closing a tab (X button)",
        "etapes": [
            "Open a tab (OPEN-001), then click the small X located on the tab itself (right of its title).",
            "Reopen the file by double-clicking: the displayed content is re-read from disk.",
        ],
        "attendu": "The tab closes cleanly; closing never touches the file on disk (no write).",
    },
    "OPEN-005": {
        "titre": "Search in the ECF tree (Id / Name / CustomIcon)",
        "etapes": [
            "In an open ECF tab, find the Search bar (input field above the block tree, on the left).",
            "Type the Id of a known block (a number, e.g. 1625) then press Enter.",
            "Press Enter again: the selection moves to the next match. Repeat once more.",
            "Try again searching a Name this time (text, e.g. Hull), then a CustomIcon.",
        ],
        "attendu": "The first Enter jumps to the first matching block (selected and visible), each further Enter moves to the next match, then wraps around to the start.",
    },
    "OPEN-006": {
        "titre": "Section groups shown as headers",
        "pre": "A file with ### separators (e.g. vanilla Containers.ecf).",
        "etapes": [
            "Double-click the file in the working copy to open it.",
            "Watch the top of the block tree: section titles (lines starting with ### in the file) appear at the head of groups.",
        ],
        "attendu": "Section titles are shown at the head of their group in the tree and are not clickable (they are separators, not blocks).",
    },
    "OPEN-007": {
        "titre": "## labels displayed next to the block",
        "pre": "A file with ## labels placed before a block.",
        "etapes": [
            "Open the file (double-click in the working copy).",
            "In the tree, find the block preceded by a ## label in the file.",
        ],
        "attendu": "The label name appears in parentheses next to the block's identifier in the tree.",
    },
    "OPEN-008": {
        "titre": "File header extracted and displayed",
        "etapes": [
            "Open BlocksConfig.ecf (double-click, working copy).",
            "Open the file's explanation panel: look for the help/explanation button or banner at the top of the tab (the file header is the # comment block at the very beginning).",
        ],
        "attendu": "The header documentation is displayed readably (text without the # marks) in the explanation panel.",
    },
    "OPEN-009": {
        "titre": "Unsupported file: built-in preview or clear message",
        "etapes": [
            "In the working copy, place (or find) an image (png/jpg) -- for example an icon texture -- then double-click it.",
            "Repeat with a PDF if you have one in the scenario (optional QtPdf module: without it, a message explains).",
            "Repeat with a file having neither parser nor viewer (game texture .dds, 3D model...): a clear message appears, this is intended.",
        ],
        "attendu": "Image or PDF: a read-only PREVIEW tab shows the content. Formats with neither parser NOR viewer: explicit message (no crash, no empty tab).",
    },
    "OPEN-010": {
        "titre": ".txt file: simple reading",
        "etapes": [
            "Double-click a .txt file of the scenario in the working copy.",
            "Compare the displayed content with the file opened in Windows Notepad (right-click the file > Open with > Notepad).",
        ],
        "attendu": "A text tab opens, content faithful to the file (read-only or basic working editing).",
    },
    "OPEN-011": {
        "titre": "Tab title: modification marker",
        "etapes": [
            "In an editable tab, change a value WITHOUT saving (double-click a table value, type something else, validate with Enter).",
            "Watch the tab title at the top.",
            "Save (Ctrl+S) then watch the title again.",
        ],
        "attendu": "Modified tab: pencil icon + filled dot + RED TAB TEXT, visible on every theme. After saving, the marker disappears.",
    },
    # ---------------------------------------------------------------- ECF
    "ECF-001": {
        "titre": "Property list view (values in a dropdown)",
        "etapes": [
            "Open the working copy's BlocksConfig.ecf (double-click).",
            "In the left tree, click ONCE on a standard block (e.g. a hull block) to select it: its properties show on the right, one row per property (key on the left, value on the right).",
            "Edit a value (double-click it): an EDITABLE dropdown opens with the values already seen in the file.",
            "Repeat on a block whose genre (Group) is UNIQUE in the file: the list must still offer values (global fallback pool).",
        ],
        "attendu": "One row per property, key on the left / value editable WITH A DROPDOWN of observed file values; even on a unique-genre block the list offers values (global pool -- v1.6.1 fix: empty list before).",
    },
    "ECF-002": {
        "titre": "Automatic table mode detection (Child Items)",
        "pre": "A block with numbered properties Name_0/Name_1... (e.g. vanilla containers).",
        "etapes": [
            "In the tree, select a block with a repetitive structure (its keys end in _0, _1, _2...).",
            "Watch the right panel: TABLE display (one column per parameter) instead of the list.",
            "Look for the + Row button under the table: it must be present and active.",
        ],
        "attendu": "The block displays as a table (one column per parameter), with an active + Row button.",
    },
    "ECF-003": {
        "titre": "Editing a value + session highlighting",
        "etapes": [
            "Double-click a value in the property table, replace it, validate with Enter.",
            "Watch the modified cell then the tab title.",
        ],
        "attendu": "The modified cell is highlighted (session trace); the tab title switches to modified state (pencil + dot + red text).",
    },
    "ECF-004": {
        "titre": "Ctrl+S saving + faithful round-trip",
        "etapes": [
            "Change a value then press Ctrl+S (Ctrl and S keys together).",
            {
                "txt": "Verify the file's faithfulness from a command line: copy one of the commands below and paste it in a command prompt (see CLI-001 to open one), replacing <file> with the path of the modified file (tip: Shift+right-click the file > Copy as path).",
            },
        ],
        "attendu": "Saving OK; the checker reports a faithful round-trip (re-read/rewrite) with no error.",
    },
    "ECF-005": {
        "titre": "Tab Ctrl+Z: undoing a modification",
        "etapes": [
            "Change a value (do not save).",
            "Click somewhere in the block TREE (so you are not typing in a field), then press Ctrl+Z.",
            "Repeat the test while the caret is INSIDE an input field: Ctrl+Z there undoes your typing (normal behavior), not the block modification.",
        ],
        "attendu": "The original value comes back and the modification marker disappears. In a text field, Ctrl+Z stays the typing undo (v1.6.1 fix: the shortcut was ambiguous and undid nothing).",
    },
    "ECF-006": {
        "titre": "Automatic annotation of modifications",
        "pre": "Options > Automatically annotate changes enabled, name configured (see OPT-001).",
        "etapes": [
            "Change a value, then save with Ctrl+S.",
            {
                "txt": "Open the raw file in Notepad to see the annotation: copy the command below in a command prompt (replace <file> with the real path), or open the file with Notepad by hand.",
            },
            "Re-edit the SAME property with another value, save, reopen the file.",
        ],
        "attendu": "The modified line carries a comment « # original: <old> -- Mod by <name> ». NORMAL BEHAVIOR: the annotation is written AT SAVE TIME only (nothing in the file until you save). Repeated edits of the SAME property REPLACE the previous note (no accumulation).",
    },
    "ECF-007": {
        "titre": "Disabling automatic annotations",
        "etapes": [
            "In the menu bar: Options > Automatically annotate changes (untick if ticked).",
            "Change a value, save (Ctrl+S), open the raw file (ECF-006 command).",
        ],
        "attendu": "No « # original » comment was added to the modified line.",
    },
    "ECF-008": {
        "titre": "+ Property: simple addition (dropdowns)",
        "etapes": [
            "Select a block in the tree, then click the + Property button (above the property table).",
            "In the dialog, observe: the KEY and the VALUE are EDITABLE dropdowns, pre-filled with keys/values already seen in the file.",
            "Pick a key/value pair that exists elsewhere in the file, then validate.",
        ],
        "attendu": "The property appears on the block, greyed/highlighted in the table, and the block is marked in the left tree (v1.6.1 fix: bare input fields with no list, no highlighting).",
    },
    "ECF-009": {
        "titre": "+ Property: several pairs on one line",
        "etapes": [
            "Click + Property on a block.",
            "In the value field, type several pairs respecting the game syntax: param1: 0.6, param2: \"1,3\" (comma-separated, quoted if the value contains a comma).",
            "Validate, then open the raw file (ECF-006): the pairs are on ONE line.",
        ],
        "attendu": "The pairs are grouped on a single line of the block, exactly as the game writes them.",
    },
    "ECF-010": {
        "titre": "+ Block: Id + Name choice",
        "etapes": [
            "Click the + Block button (above the tree or in the ECF tab toolbar).",
            "In the wizard, pick the WITH Id mode, type a free Id (number < 8192 not already used) and a free Name.",
            "Finish the wizard (Create button). Accept or dismiss the info-card proposal that may follow.",
        ],
        "attendu": "The block is created with the requested Id and Name; the wizard validates input live (8192 limit, duplicates forbidden).",
    },
    "ECF-011": {
        "titre": "+ Block: Name only (beyond the Id limit)",
        "etapes": [
            "Click + Block.",
            "Pick the Name ONLY mode (no Id), type a free Name and finish.",
        ],
        "attendu": "The block is created without an Id: it is identified by its Name only (blocks beyond the game's Id limit).",
    },
    "ECF-012": {
        "titre": "+ Block: file property table + dropdown menus",
        "etapes": [
            "Click + Block and watch the list of proposed properties in the wizard.",
            "Open the dropdown of a proposed VALUE.",
        ],
        "attendu": "Proposed properties come from the working file, sorted by usage; suggested values are real values already seen in the file.",
    },
    "ECF-013": {
        "titre": "+ Block: live Id validation (8192 / duplicate)",
        "etapes": [
            "In the + Block wizard (with Id mode), type an Id GREATER than 8192: watch the error message.",
            "Then type an Id already used by a block of the file: watch the error message.",
            "Try finishing the wizard in that state.",
        ],
        "attendu": "Visible error in both cases; creation is impossible while the Id is invalid.",
    },
    "ECF-014": {
        "titre": "+ Block: associated Template proposal",
        "pre": "Templates.ecf is present in the working copy.",
        "etapes": [
            "Create a block via + Block (ECF-010).",
            "At the end of the wizard, accept the proposal to create the associated Template (crafting recipe).",
            "In the following adjustment window, validate, then open Templates.ecf (double-click in the working copy) and find the created Template.",
        ],
        "attendu": "A Template with the same Name is created in Templates.ecf, with ingredients addable through an item-name dropdown.",
    },
    "ECF-015": {
        "titre": "+ Row: automatic numbering (Name_6 after Name_5)",
        "pre": "A block in table mode with Name_0..Name_5 (ECF-002).",
        "etapes": [
            "Select the table-mode block, click + Row.",
            "Pick the Name type in the offered list, type a simple value (a number, e.g. 5), validate.",
            "Repeat typing this time a value CONTAINING a comma or a space (e.g. stone, wood).",
            "Check the raw file (ECF-006) to see the writing.",
        ],
        "attendu": "The row is inserted with the next number (Name_6) at the right place. A value containing a comma or space is automatically QUOTED (otherwise split in two); a plain number stays unquoted.",
    },
    "ECF-016": {
        "titre": "+ Row: Type choice from the file's own prefixes",
        "etapes": [
            "On a block having Name_N AND Group_N, open + Row and watch the Type list.",
            "Compare the list with the prefixes actually present on the block.",
        ],
        "attendu": "Type offers the block's real prefixes (Name, Group...), not a fixed list.",
    },
    "ECF-017": {
        "titre": "Deleting a property (and Undo stays on the block)",
        "etapes": [
            "In the tree, scroll down to a block FAR from the beginning.",
            "Right-click one of the block's properties (in the tree) > Delete, confirm.",
            "Press Ctrl+Z (tab undo) and watch where the tree selection is.",
        ],
        "attendu": "The row disappears from the block, and undoing restores it WHILE STAYING positioned on the same block (v1.6.1 fix: after Undo the tree jumped back to the very beginning).",
    },
    "ECF-018": {
        "titre": "Deleting a block (confirmation requested)",
        "etapes": [
            "Right-click a tree block > Delete.",
            "A confirmation is requested: read it, then confirm.",
        ],
        "attendu": "The confirmation is shown; after confirming, the block disappears from the tree and from the file (Ctrl+S then verification possible via ECF-004).",
    },
    "ECF-019": {
        "titre": "Deactivate this block (test): comment at exact position",
        "etapes": [
            "Right-click a block > Deactivate this block (test).",
            "Save (Ctrl+S) then open the raw file (ECF-006).",
            "Search the block in the file (Ctrl+F in Notepad).",
        ],
        "attendu": "The block is commented out (deactivated) AT ITS ORIGINAL POSITION in the file: it was not moved to the end.",
    },
    "ECF-020": {
        "titre": "Deactivated blocks list + reactivation",
        "pre": "At least one block deactivated via ECF-019.",
        "etapes": [
            "Open the deactivated blocks list (button or menu of the ECF tab).",
            "Select the deactivated block and click Reactivate.",
            "Check the raw file (ECF-006).",
        ],
        "attendu": "The block comes back exactly in its original state and position in the file.",
    },
    "ECF-021": {
        "titre": "Filter by property",
        "etapes": [
            "In the ECF tab, launch Filter by property... (tab button/menu).",
            "Tick a common property (e.g. Mass) and apply.",
            "Watch the tree, then untick to go back to the full view.",
        ],
        "attendu": "The tree shows only blocks having (or not having, per the chosen option) the ticked property; going back to the full view restores everything.",
    },
    "ECF-022": {
        "titre": "Explanation panel: hand-made glossary",
        "etapes": [
            "Open BlocksConfig.ecf, expand the explanation panel (OPEN-008).",
            "Read a few glossary definitions (e.g. Id, Mass, HitPoints).",
        ],
        "attendu": "The glossary is written and clarified in French: this file is covered by the manual glossary (no rough automatic translation).",
    },
    "ECF-023": {
        "titre": "Explanation panel: automatic translation outside the glossary",
        "pre": "An ECF file NOT covered by the manual glossary.",
        "etapes": [
            "Open that file and its explanation panel.",
            "Click the panel's Translate automatically button.",
        ],
        "attendu": "The original text is translated on demand (or a clear error if online translation is disabled -- see TRAD-013).",
    },
    "ECF-024": {
        "titre": "Bulk transform: property choice (auto-completion that ticks)",
        "etapes": [
            "Launch Bulk transform... (ECF tab button/menu).",
            "In the property field, type the first letters of a common property (e.g. cra for CraftTime): an auto-completion suggestion appears.",
            "VALIDATE the suggestion with arrows + Enter, or by clicking it.",
            "Watch the checkbox list below. Then type a non-existing key (e.g. xxx): everything stays unticked.",
        ],
        "attendu": "Auto-completion offers the keys actually present; validating a suggestion AUTOMATICALLY TICKS the matching checkbox in the list below (v1.6.1 fix: you had to scroll and tick by hand). A non-existing key leaves everything unticked.",
    },
    "ECF-025": {
        "titre": "Bulk transform: the 5 operations",
        "etapes": [
            "In Bulk transform, pick a common numeric property (e.g. Mass) on a small selection of blocks.",
            "Apply the 5 operations successively: Multiply (factor 2), Add (+10), Set (=100), Cap (max 500), Round.",
            "After each operation, check the mathematical result on a few blocks (ECF-006 to open the file, or the tab's table).",
        ],
        "attendu": "Each operation produces the expected mathematical result in the file, only on the targeted blocks.",
    },
    "ECF-026": {
        "titre": "Bulk transform: full preview + editable After column",
        "etapes": [
            "Prepare a transform on a batch of blocks, then click Preview.",
            "In the preview table: untick ONE row, then double-click the After column value of ANOTHER row and correct it.",
            "Apply, then check the file: only the ticked rows changed, with your hand-corrected « After » value.",
        ],
        "attendu": "The preview is NOT truncated (all rows visible); only the ticked rows are written, with the « After » value possibly corrected by hand.",
    },
    "ECF-027": {
        "titre": "Bulk transform: genre + identities filters",
        "etapes": [
            "Apply a transform with a block GENRE filter (e.g. only blocks with Group: SVCargoContainer).",
            "Then apply a transform with a list of block IDENTITIES (specific names typed/chosen).",
            "Each time, check which blocks were modified.",
        ],
        "attendu": "Only blocks matching the filter (genre or identity list) are modified.",
    },
    "ECF-028": {
        "titre": "Bulk transform: Ctrl+Z undo",
        "etapes": [
            "Apply a bulk transform (ECF-025) without saving.",
            "Click in the tree then press Ctrl+Z.",
        ],
        "attendu": "All transformed values come back to their pre-operation state.",
    },
    "ECF-029": {
        "titre": "ECF header card: header translation",
        "etapes": [
            "In an ECF tab, find the button dedicated to header translation (near the explanation panel, cf. OPEN-008).",
            "Click it and watch the result.",
        ],
        "attendu": "The header (# comment block at the file start) is translated; or a clear error if online translation is disabled.",
    },
    "ECF-030": {
        "titre": "ECF merge (A to working copy): EDITABLE preview before writing",
        "pre": "Options > Allow merging enabled. The file ALREADY exists in the working copy (to get differences, first modify a block on the A side of a file, without copying it over).",
        "etapes": [
            "In the Scenario A panel, right-click an ECF file > merge into the working copy.",
            "Read the preview that opens: one row per difference (added block / added property / different value), with BEFORE and AFTER columns.",
            "Untick one row, then double-click the « After » column of another row and correct the value.",
            "Validate: watch the tab that opens by itself.",
        ],
        "attendu": "NOTHING is written before validation. On validation, only the TICKED rows are applied (with your « After » corrections); different values stay as the working copy's unless you ticked them. The file tab opens DIRECTLY positioned on the first merged block.",
    },
    "ECF-031": {
        "titre": "Property table: dropdown on every value",
        "pre": "An open ECF file with several same-genre blocks sharing a property (e.g. CraftTime).",
        "etapes": [
            "Select a block on the left, then in the table on the right click the VALUE of a property (e.g. CraftTime).",
            "Open the dropdown: it offers values actually observed in the file (frequency-sorted). Pick one.",
            "Repeat while TYPING a totally new value this time (free input) and validate with Enter.",
        ],
        "attendu": "The cell offers the file's observed values (frequency sort); free input stays possible; the change is applied to the block (highlighted row + up-to-date modification counter).",
    },
    # ---------------------------------------------------------------- DLG
    "DLG-001": {
        "titre": "Opening Dialogues.ecf: dedicated browser",
        "etapes": [
            "In the working copy, double-click Dialogues.ecf.",
            "Watch the tab's areas: dialogue tree on the left, selected dialogue content on the right, and the classic ECF editing stays available.",
        ],
        "attendu": "The dialogue browser is ADDED to the classic ECF editing (it does not replace it): dialogue tree + read/edit panel.",
    },
    "DLG-002": {
        "titre": "Navigating between dialogues (Next / OptionNext)",
        "pre": "Dialogues.ecf open in a tab: the LEFT column lists the dialogues (tree). Next/NextIf links are the nodes' « Next: » / « OptionNext: » fields, visible in the right panel.",
        "etapes": [
            "Double-click a dialogue in the left tree to display it on the right.",
            "In the right panel, find a node's « Next: » field: its value is the name of ANOTHER dialogue.",
            "Find that destination dialogue in the left tree (filter bar if needed), double-click it, and repeat the chain 2 or 3 times.",
        ],
        "attendu": "Each dialogue displays with its own nodes and texts; the left tree stays synchronized (no context loss). Navigation is MANUAL via the tree: links are not clickable in the right panel (possible evolution, see summary).",
    },
    "DLG-003": {
        "titre": "Editing a dialogue text",
        "etapes": [
            "In the right panel, change a dialogue text (add a word for example, or [b]...[/b] tags).",
            "Save (Ctrl+S), then check the file: ECF-006 (Notepad) or the verifier-ecf command of ECF-004.",
        ],
        "attendu": "The modified text is written faithfully to the file (round-trip), BBCode tags included.",
    },
    "DLG-004": {
        "titre": "Dialogue consistency: cross-reference check",
        "etapes": [
            "In the menu bar: Verification > Check cross-file references...",
            "Enable the Dialogues check (checkbox in the window), then run the analysis.",
            "Read the results (see VERIF-006 for the correction).",
        ],
        "attendu": "Orphan Next/OptionNext links (non-existing dialogue) are detected and listed.",
    },
    "DLG-005": {
        "titre": "Round-trip Dialogues.ecf without modification",
        "etapes": [
            "Open Dialogues.ecf, then immediately save without changing anything (Ctrl+S).",
            "Run the faithfulness check on the file: verifier-ecf command (see ECF-004).",
        ],
        "attendu": "The file is reproduced identically: no binary difference reported by the checker.",
    },

    # ---------------------------------------------------------------- YAML
    "YAML-001": {
        "titre": "Generic YAML: tree + value editing",
        "etapes": [
            "In the working copy, double-click a simple non-playfield YAML (for example a small scenario configuration YAML).",
            "Select an entry in the tree, change its value in the right-hand field, then click the Apply button.",
            "Open the last « Full YAML » tab of the same window to see the raw text.",
        ],
        "attendu": "The changed value appears in the tree AND in the raw YAML (last tab), without saving.",
    },
    "YAML-002": {
        "titre": "+ Entry / Delete selected entry",
        "etapes": [
            "Click the YAML editor's + Entry button: a new entry appears in the tree; fill its name/value.",
            "Select it then click Delete selected entry.",
            "Watch the tree and the Full YAML tab after each operation.",
        ],
        "attendu": "The add then the delete are reflected in the tree AND in the full YAML.",
    },
    "YAML-003": {
        "titre": "Automatic application of pending text",
        "etapes": [
            "Type a new value in the field WITHOUT clicking Apply, then click the tab's Save button directly.",
            "Repeat: type a value without Apply, then simply click ANOTHER entry in the tree.",
        ],
        "attendu": "The pending text is applied in both cases (at save time and on selection change): never lost by oversight.",
    },
    "YAML-004": {
        "titre": "Multiline strings with empty lines",
        "pre": "A playfield with a multiline Description.",
        "etapes": [
            "Open the playfield, Full YAML tab or Description field, and write a multi-line text with ONE EMPTY LINE in the middle.",
            "Save (Ctrl+S).",
            "Reopen the file in Notepad (ECF-006): the Description must contain the line breaks.",
        ],
        "attendu": "The empty line becomes a real line break in the file; the display stays correct in the editor (and in game for a description).",
    },
    "YAML-005": {
        "titre": "Faithful YAML round-trip",
        "etapes": [
            "Open any YAML and immediately save without changing anything (Ctrl+S).",
            {
                "txt": "Check faithfulness: command below (replace <file>), or compare bytes before/after with a copy made before saving.",
            },
        ],
        "attendu": "Identical file byte for byte (the checker confirms the round-trip).",
    },
    "YAML-006": {
        "titre": "Playfield: auto-switch to the structured editor (8 tabs)",
        "etapes": [
            "Double-click a playfield.yaml of the working copy (Playfields folder).",
            "Watch the tabs of the window that opens.",
        ],
        "attendu": "The structured editor opens with its 8 tabs: 2D map, Resources, POI, Creatures, Drones/Vessels, Spawn zones, Special effects, Full YAML.",
    },
    "YAML-007": {
        "titre": "Resources: add with a dropdown of real blocks",
        "etapes": [
            "In the open playfield, Resources tab, click + resource.",
            "In the new row, open the resource field's dropdown.",
        ],
        "attendu": "The list is populated with the scenario's REAL blocks (no blind typing); free input stays possible.",
    },
    "YAML-008": {
        "titre": "Resources: editable RegenAfter column",
        "etapes": [
            "Resources tab: double-click a resource's RegenAfter cell, change the value, validate.",
            "Save (Ctrl+S) then check in the Full YAML tab (or Notepad) that the value is in the right place.",
        ],
        "attendu": "The new RegenAfter value is written at the right place of the Resources section.",
    },
    "YAML-009": {
        "titre": "POI: table + NATIVELY deactivated entries (greyed, reactivable)",
        "etapes": [
            "POI tab: change a POI field, save, check the YAML.",
            "Spot the GREYED « (deactivated) ... » rows at the end of the table: these are entries commented out NATIVELY in the file (e.g. « # - GroupName: X » from RE2), not by the application.",
            "Right-click a greyed entry > Activate this entry.",
            "Save then check the raw YAML: the lines are no longer commented.",
            "Press Ctrl+Z: the operation must undo.",
        ],
        "attendu": "1) The modification is written correctly. 2) The file's commented entries appear GREYED with a counter (« N deactivated entry(ies) »). 3) « Activate » uncomments the lines: the entry becomes a real editable line on disk, undoable (Ctrl+Z) -- new in v1.6.1. Same mechanism in Resources/Creatures/Drones/Zones/Effects AND in the ECF tree (native commented blocks, e.g. « #{ +Block »).",
    },
    "YAML-010": {
        "titre": "Creatures: Biome column (editable + filter)",
        "etapes": [
            "Creatures tab: open the biome FILTER dropdown (above the table) and pick a biome: the table shows only that biome's creatures.",
            "Edit a creature's biome (dropdown of observed biomes), save, check the YAML.",
        ],
        "attendu": "The filter shows only the chosen biome's creatures. Editing rewrites the creature's « - Biomes: [...] » ZONE (the biome belongs to the zone, not the creature); a multi-biome zone is replaced by the chosen biome.",
    },
    "YAML-011": {
        "titre": "Drones / Vessels: working table",
        "etapes": [
            "Drones/Vessels tab: change an entry (e.g. a name or a number), save, check the Full YAML.",
        ],
        "attendu": "The modification is written correctly in the right section.",
    },
    "YAML-012": {
        "titre": "Spawn zones: working table",
        "etapes": [
            "Spawn zones tab: change an entry, save, check the Full YAML.",
        ],
        "attendu": "The modification is written correctly.",
    },
    "YAML-013": {
        "titre": "Special effects: working table",
        "etapes": [
            "Special effects tab: change an entry, save, check the Full YAML.",
        ],
        "attendu": "The modification is written correctly.",
    },
    "YAML-014": {
        "titre": "Full YAML: last tab shares the document",
        "etapes": [
            "Change a value in a structured tab (Resources, POI...), WITHOUT saving.",
            "Open the same window's Full YAML tab.",
        ],
        "attendu": "The raw YAML reflects the change IMMEDIATELY (preview refreshed on each structured edit): same in-memory document, no gap between views.",
    },
    "YAML-015": {
        "titre": "Playfield: tab Ctrl+Z + single annotation",
        "pre": "Options > Automatically annotate changes enabled.",
        "etapes": [
            "Change a value in a structured tab, then press Ctrl+Z (after clicking outside the field).",
            "Repeat: change then save (Ctrl+S) the SAME value 3 times in a row.",
            "Open the raw file (ECF-006) and find the annotated line.",
        ],
        "attendu": "Ctrl+Z restores the original value in the structured view AND the Full YAML. The annotation comment holds ONE SINGLE « # original: ... » note (v1.6.1 fix: notes accumulated until they broke the YAML with a fake key).",
    },
    "YAML-016": {
        "titre": "Resources: deleting a resource",
        "etapes": [
            "Resources tab: select a resource row and delete it (Delete button or Del key depending on the UI).",
            "Save then check the Full YAML: the Resources section.",
        ],
        "attendu": "The row is removed cleanly from the Resources section (no orphan comma nor leftover empty line).",
    },
    "YAML-017": {
        "titre": "space*.yaml recognized as a playfield",
        "etapes": [
            "Double-click a space*.yaml file of the working copy (space Playfields).",
        ],
        "attendu": "Switches to the structured editor (8 tabs) as for a planetary playfield*.yaml.",
    },
    "YAML-018": {
        "titre": "YAML: round-trip after structured editing",
        "etapes": [
            "Change a value via a structured tab, save (Ctrl+S).",
            {
                "txt": "Run the faithfulness check on the file (replace <file>):",
            },
        ],
        "attendu": "The checker confirms the YAML's faithfulness after the structured edit.",
    },
    # ---------------------------------------------------------------- MAP
    "MAP-001": {
        "titre": "2D map: display of positionable entities",
        "etapes": [
            "Open an RE2 playfield (e.g. Akua), 2D map tab.",
            "Spot: fixed POIs (filled points), player spawn points, and random POIs in a SpawnPOINear CHAIN (dashed circle = radius).",
        ],
        "attendu": "Fixed POIs, player spawns AND chained SpawnPOINear random POIs visible (approximate position inherited from their reference, dashed circle = radius; v1.6.1 fix: only the 1st POI appeared, NullPOI->R2AntennaStory->... chains were not resolved). A POI with no known reference stays « without position » (never invented).",
    },
    "MAP-002": {
        "titre": "Dragging a fixed POI + YAML writing",
        "etapes": [
            "On the 2D map, place the cursor ON a fixed POI point (the cursor changes), hold the left button and move the point elsewhere.",
            "Release: the point is at its new place.",
            "Save (Ctrl+S), then check in the Full YAML tab the moved POI's X/Z Position.",
            "Also note: a SIMPLE click without dragging does NOT mark the tab as modified.",
        ],
        "attendu": "The new coordinates are written in the POI's section. (v1.6.1 fix: left-drag was PANNING the map instead of moving the point; a plain click no longer marks the tab modified.)",
    },
    "MAP-003": {
        "titre": "Entity genre filters + zoom",
        "etapes": [
            "On the 2D map, tick/untick the genre filters successively (POI, creatures, resources... per the legend).",
            "Zoom with the mouse wheel (pointer over the map), zoom out, and pan the view.",
        ],
        "attendu": "Filters hide/show entity genres; zooming stays precise (no offset between the cursor and the points).",
    },
    "MAP-004": {
        "titre": "Entities without position: no invention",
        "pre": "A playfield with space resources, or random POIs with no known reference.",
        "etapes": [
            "Spot those entries on the map or in the legend (« without position » counter).",
            "Check in the YAML that no coordinate was added for them.",
        ],
        "attendu": "They deliberately have NO displayed position (no invented coordinate). A playfield WITHOUT a POIs section (some space*.yaml) lists 0 POI in the inspector: normal, the file has none.",
    },
    "MAP-005": {
        "titre": "POI Inspector: per-POI statistics",
        "pre": "A PLANETARY playfield with a POIs section (space ones may not have any -- see MAP-004).",
        "etapes": [
            "Open the playfield's POI tab.",
            "Click the POI Inspector... button above the table.",
        ],
        "attendu": "A NON-modal window lists random POIs with quantity and estimated drones.",
    },
    "MAP-006": {
        "titre": "POI Inspector: faction aggregation + export",
        "etapes": [
            "In the inspector (MAP-005), switch to the faction view (button/checkbox of the window).",
            "Click Export and pick a location for the text file.",
            "Open the exported file.",
        ],
        "attendu": "The per-faction drone total is consistent with the view; the export writes a complete, readable text file.",
    },
    "MAP-007": {
        "titre": "Galaxy map: auto-locating + display",
        "etapes": [
            "In the menu bar: Tools > Galaxy map (Sectors.yaml)...",
            "Watch the displayed systems and their colors.",
        ],
        "attendu": "Systems are found automatically and displayed; purple for special roles, orange for spectral classes.",
    },
    "MAP-008": {
        "titre": "Galaxy map: Y tilt slider",
        "etapes": [
            "In the galaxy map, find the Tilt (Y axis) slider.",
            "Increase it progressively (drag the slider right) and watch the map.",
        ],
        "attendu": "Systems shift according to their real Y: overlapping ones visually separate.",
    },
    "MAP-009": {
        "titre": "Galaxy map: read-only / edit mode",
        "etapes": [
            "Open the galaxy map WITHOUT ticking the permission checkbox, then try to drag a system.",
            "Tick « Allow moving systems », drag a system, then check Sectors.yaml (Full YAML or Notepad).",
            "Undo via the main window's global Undo button and check again.",
        ],
        "attendu": "1st case: read-only, no accidental editing. 2nd case: the new X/Z position is written into Sectors.yaml (Y kept, tilt pinned to 0), undoable via the global Undo button (new in v1.6.1).",
    },

    # ---------------------------------------------------------------- CSV
    "CSV-001": {
        "titre": "Opening working-copy CSV: editable table",
        "etapes": [
            "In the working copy, double-click Extras/Localization.csv.",
            "Watch the table: columns faithful to the file, editable cells (double-click).",
        ],
        "attendu": "The CSV opens as an editable table, with the same columns as the file (Key, English, French...).",
    },
    "CSV-002": {
        "titre": "Scenario A CSV: read-only + row copy",
        "etapes": [
            "Open the SAME Localization.csv from the Scenario A panel: it is read-only.",
            "Right-click a row > copy to the working copy: the row is copied (or merged by key).",
            "Repeat with a row whose key ALREADY exists in the working copy, all cells filled: a dialog EXPLAINS that nothing changed.",
        ],
        "attendu": "1st case: the row is copied into the working copy's CSV (or merged by key). 2nd case: explanatory dialog (merge mode = working copy has priority, cells already filled) instead of seemingly doing nothing.",
    },
    "CSV-003": {
        "titre": "+ Row / row deletion",
        "etapes": [
            "Click + Row, fill the new row's cells (at least the key).",
            "Select that row then delete it (button or right-click > Delete).",
            "Save and check the file (ECF-006 or verifier-csv).",
        ],
        "attendu": "The add and the delete both work and save correctly.",
    },
    "CSV-004": {
        "titre": "Multi-cell clipboard",
        "etapes": [
            "Select several cells (click then Shift+click, or drag), Copy (Ctrl+C).",
            "Click a destination cell and paste (Ctrl+V).",
            "Also test Cut (Ctrl+X) and Clear (Del key).",
        ],
        "attendu": "Spreadsheet behavior: the multi-selection is respected, pasting reproduces the cell block.",
    },
    "CSV-005": {
        "titre": "Search with scope (column / all)",
        "etapes": [
            "Run the CSV tab's search, look for a present text with the « all columns » scope.",
            "Run the same search limited to ONE column.",
            "Press Enter several times to chain the results.",
        ],
        "attendu": "Results respect the chosen scope; Enter moves to the next match.",
    },
    "CSV-006": {
        "titre": "Header right-click: search limited to the column",
        "etapes": [
            "Right-click a table COLUMN HEADER, run a search from the menu.",
        ],
        "attendu": "The search is pre-scoped to that column (scope already selected).",
    },
    "CSV-007": {
        "titre": "Find and replace with review",
        "etapes": [
            "Run Find and replace... and replace a text present several times.",
            "In the review window, examine the matches: untick one, apply.",
        ],
        "attendu": "Every match is listed and untickable: never a blind replace.",
    },
    "CSV-008": {
        "titre": "Replace: case sensitivity and whole word",
        "etapes": [
            "Enable « Match case » then test a replacement on a word and its derivative (e.g. Dos / Dossier).",
            "Enable « Whole word » and repeat: derivatives must no longer be touched.",
        ],
        "attendu": "The options filter matches correctly (exact case, whole word).",
    },
    "CSV-009": {
        "titre": "Faithful CSV round-trip (line endings preserved)",
        "etapes": [
            "Make a copy of the CSV before modification (Ctrl+C/Ctrl+V in Explorer).",
            "Open the CSV in the application and save without changing anything (Ctrl+S).",
            "Compare both files: right-click each > Properties (same size), or the verifier-csv command below.",
            {
                "txt": "Command check (replace <file>):",
            },
        ],
        "attendu": "Identical file after saving (line endings and structure preserved).",
    },
    "CSV-010": {
        "titre": "CSV tab Ctrl+Z",
        "etapes": [
            "Change a cell (double-click, change the value, Enter).",
            "Click in the table (outside the editing cell) then press Ctrl+Z.",
        ],
        "attendu": "The original value comes back. (v1.6.1 fix: same cause as ECF-005, ambiguous shortcut.)",
    },
    "CSV-011": {
        "titre": "Multiline cells displayed correctly",
        "pre": "A CSV with cells containing line breaks.",
        "etapes": [
            "Open the file and spot the multiline cells.",
            "Edit such a cell (double-click), validate without breaking the line breaks, save, check the file.",
        ],
        "attendu": "The content is faithful; editing does not break the file structure (no doubled CSV line).",
    },
    "CSV-012": {
        "titre": "Saving: BOM preserved when present",
        "pre": "A CSV starting with a BOM (3 invisible bytes EF BB BF -- frequent in game CSVs).",
        "etapes": [
            "Open + save the file without modification (Ctrl+S).",
            {
                "txt": "Check the first 3 bytes: copy the command below in a command prompt (replace <file>) -- it prints the first 3 bytes in hexadecimal.",
            },
        ],
        "attendu": "The first 3 bytes are still EF BB BF: the original BOM is preserved.",
    },
    # ---------------------------------------------------------------- TRAD
    "TRAD-001": {
        "titre": "Translation memory: instant reuse",
        "etapes": [
            "In a CSV tab, translate a cell (right-click > Translate to > a language, see TRAD-002).",
            "Find ANOTHER cell containing EXACTLY the same text (search bar) and translate it.",
        ],
        "attendu": "The second translation is instant (no network call) and identical to the first (it comes from the memory).",
    },
    "TRAD-002": {
        "titre": "Right-click > Translate to > language: before/after preview",
        "etapes": [
            "Right-click a cell > Translate to > pick a language in the submenu.",
            "Watch the preview window (before text / proposed text) and validate or cancel.",
        ],
        "attendu": "A before/after preview is offered BEFORE any replacement; cancelling changes nothing.",
    },
    "TRAD-003": {
        "titre": "Replacement in the target language column",
        "pre": "The CSV has a column of the target language (e.g. French).",
        "etapes": [
            "Pick a row whose TARGET column cell is empty.",
            "Translate the source cell (right-click > Translate to > that language).",
            "Watch the row after validating.",
        ],
        "attendu": "The translation lands in the target column (the empty cell is filled); the source cell stays intact.",
    },
    "TRAD-004": {
        "titre": "Quick Translate button: default language",
        "pre": "A default language configured in Options > Default translation language...",
        "etapes": [
            "Configure (or check) the default language in Options.",
            "Click the CSV tab toolbar's Translate button on a selected cell.",
        ],
        "attendu": "The translation goes straight to the configured language, without a language submenu.",
    },
    "TRAD-005": {
        "titre": "Batch translation: progress + review table",
        "etapes": [
            "Select several cells (drag or Shift+click), right-click > Translate selection to...",
            "During the batch: watch the progress bar, and move the window to check it stays responsive.",
            "At the end, go through the review (table of proposed translations) and click Apply.",
        ],
        "attendu": "Progress bar WITHOUT freezing the interface; review before applying; failures are marked red and unticked.",
    },
    "TRAD-006": {
        "titre": "Review: untick a row / edit the proposed text",
        "etapes": [
            "In a batch's review (TRAD-005), untick ONE row.",
            "Double-click another row's proposed text and correct it.",
            "Apply, then check the cells in the table.",
        ],
        "attendu": "Only the ticked rows are applied, with the corrected text for the one you edited.",
    },
    "TRAD-007": {
        "titre": "Automatic stop after 5 consecutive failures",
        "pre": "Network off or online translation unavailable (unplug the network or turn Wi-Fi off).",
        "etapes": [
            "Launch a LARGE translation batch with the network off.",
            "Watch the progress bar and the messages.",
        ],
        "attendu": "Automatic stop after 5 consecutive failures, clear message; already-successful translations stay in the review for applying.",
    },
    "TRAD-008": {
        "titre": "Fill missing languages: empty cells only",
        "etapes": [
            "Click the CSV tab's Fill missing languages... button.",
            "Pick the source and target languages, run.",
            "Go through the review and apply.",
        ],
        "attendu": "Only EMPTY target cells are translated; already-filled cells stay intact.",
    },
    "TRAD-009": {
        "titre": "BBCode and placeholder protection",
        "pre": "A cell with [b]...[/b] tags and a {PlayerName} or %s placeholder.",
        "etapes": [
            "Translate that cell (TRAD-002) and watch the proposed text in the preview.",
        ],
        "attendu": "Tags and placeholders remain EXACTLY identical in the result (same position, same spelling).",
    },
    "TRAD-010": {
        "titre": "Background batch: interface stayed fluid",
        "etapes": [
            "Launch a large translation batch (TRAD-005).",
            "During the batch: move the window, open a menu, resize the window, switch to another application and back.",
        ],
        "attendu": "The interface reacts immediately to every action (no freeze during network requests).",
    },
    "TRAD-011": {
        "titre": "Cancelling a running batch",
        "etapes": [
            "Launch a large batch, then click Cancel in the progress bar.",
        ],
        "attendu": "The batch stops between two cells; already-done translations stay in the review.",
    },
    "TRAD-012": {
        "titre": "Network unavailable: clear and bounded error",
        "pre": "Network off (or firewall blocking the application).",
        "etapes": [
            "Try translating a single cell: roughly time the wait.",
            "Then try a batch.",
        ],
        "attendu": "Explicit error within ~15 seconds maximum (no indefinite freeze); the batch stops cleanly.",
    },
    "TRAD-013": {
        "titre": "Online translation disabled: clear refusal, memory OK",
        "etapes": [
            "Untick Options > Online translation.",
            "Try translating a NEW text (never translated): PRIVACY.md message.",
            "Then try an ALREADY-translated text (in memory, TRAD-001).",
        ],
        "attendu": "New translation refused with the privacy message; the in-memory text stays usable (instant).",
    },
    "TRAD-014": {
        "titre": "Persisted memory: survives restart",
        "etapes": [
            "Translate a text, then close the application.",
            "Start again, reopen the CSV, re-translate the SAME text (new cell with the same content).",
        ],
        "attendu": "Translation reused from memory (instant, no network).",
    },
    "TRAD-015": {
        "titre": "ECF: translating a property via context menu",
        "etapes": [
            "In an ECF tab, right-click a textual value (e.g. an Info: or a displayed Name) > translate.",
        ],
        "attendu": "Before/after preview then correct replacement in the property.",
    },
    "TRAD-016": {
        "titre": "Corrupted memory: recovery without crash",
        "pre": "Corrupt the memory on purpose: close the application, open the folder below (Explorer address bar) and replace the whole file content by xxx.",
        "etapes": [
            {
                "txt": "Open the folder then the file (with Notepad):",
            },
            "Replace the whole content of translation_memory.json by xxx, save.",
            "Start the application and translate a text.",
        ],
        "attendu": "No crash: the memory restarts from zero and rebuilds (atomically rewritten file).",
    },

    # ---------------------------------------------------------------- FUS
    "FUS-001": {
        "titre": "Duplicating a block from Scenario A",
        "etapes": [
            "In the Scenario A panel, open BlocksConfig.ecf (it opens read-only).",
            "Right-click a block > Duplicate with a new Id...",
            "In the window, watch the proposed Ids and pick one.",
            "Validate, then find the duplicated block in the working copy (same file).",
        ],
        "attendu": "The block appears in the working copy, identical to the source block except the Id.",
    },
    "FUS-002": {
        "titre": "Duplication: free Id suggestions",
        "etapes": [
            "Open the duplication window (FUS-001) and watch the proposed Ids dropdown.",
            "Compare each proposed Id with existing Ids (search in the file).",
        ],
        "attendu": "Proposed Ids are free (no existing conflict) and under the game limit (8192).",
    },
    "FUS-003": {
        "titre": "Multi-variant duplication (ChildBlocks)",
        "pre": "A block with several ChildBlocks variants (sub-blocks in the tree).",
        "etapes": [
            "Right-click the parent block in A > Duplicate: the variants duplication window opens.",
            "Follow the dedicated window (choice of variants to duplicate, new Ids).",
            "In the working copy, compare the duplicated block and its variants with the original.",
        ],
        "attendu": "Variants are duplicated with consistent numbering (Name_0, Name_1... realigned).",
    },
    "FUS-004": {
        "titre": "Variants: associated Templates offered",
        "pre": "The source block has a Template in Templates.ecf.",
        "etapes": [
            "Duplicate the variants (FUS-003) and accept creating the associated Templates.",
            "Open the working copy's Templates.ecf and find the created Templates.",
        ],
        "attendu": "One Template per variant is created, with each variant's Name.",
    },
    "FUS-005": {
        "titre": "Adjusting created Templates (dedicated editor)",
        "etapes": [
            "In the Templates adjustment window (after duplication), change the craft time and the ingredient quantities.",
            "Validate, then watch the Templates.ecf tab (marked modified, not yet written).",
            "Save the tab (Ctrl+S) and check the disk (ECF-006).",
            "Also test Undo: Ctrl+Z once = one step (not the whole batch at once).",
        ],
        "attendu": "The adjusted values are in the Templates.ecf tab; the DISK only changes at save time (app model: in-memory editing in tabs). Ctrl+Z undoes ONE modification at a time -- intended, documented behavior.",
    },
    "FUS-006": {
        "titre": "Display name (Localization.csv): proposal after duplication",
        "etapes": [
            "Duplicate a block/item (FUS-001).",
            "Accept the display-name proposal, fill FR and EN, validate.",
            "Open the working copy's Extras/Localization.csv and find the added keys.",
        ],
        "attendu": "FR/EN names are added to Extras/Localization.csv (or the scenario's CSV), with the correct keys.",
    },
    "FUS-007": {
        "titre": "Display name: source pre-fill / vanilla fallback",
        "etapes": [
            "Duplicate a block from Scenario A whose Name has an entry in the scenario's Localization.csv: watch the proposed FR/EN pre-fill.",
            "Duplicate a block WITHOUT a scenario entry (vanilla block): watch the fallback from the built-in localization pack.",
        ],
        "attendu": "FR/EN fields are pre-filled with the source name (scenario first, vanilla otherwise) in the localization window offered after duplication.",
    },
    "FUS-008": {
        "titre": "Duplicating a CSV row from Scenario A (suggested key)",
        "etapes": [
            "In the CSV opened from the A panel, right-click a row > duplicate to the working copy.",
            "Watch the new-key field: it is PRE-FILLED with a free suggestion (base_2, base_3...).",
            "Change it if you want, validate, check the working copy's CSV.",
        ],
        "attendu": "The new-key field is PRE-FILLED with an editable free suggestion (v1.6.1 fix: empty field before).",
    },
    "FUS-009": {
        "titre": "Duplicating a YAML entry (suggested value)",
        "etapes": [
            "In a YAML opened from the A panel, right-click an entry > duplicate.",
            "Watch the new-value field: PRE-FILLED with a free suggestion.",
            "Validate and check the working copy's YAML.",
        ],
        "attendu": "The new-value field is PRE-FILLED with an editable free suggestion (v1.6.1 fix: empty field before).",
    },
    "FUS-010": {
        "titre": "ECF merge (option enabled): working-copy priority + preview",
        "pre": "Options > Allow merging enabled.",
        "etapes": [
            "Merge an ECF file of A already present (modified) into the working copy (right-click in A > merge).",
            "In the preview, watch the « different » rows: by default they are UNTICKED.",
            "Tick the row of a DIFFERENT property (to take the source value), then validate.",
        ],
        "attendu": "By default the working copy's values are KEPT (« different » rows unticked); only additions come from A. Ticking a « different » row takes the source value (explicit choice, editable). Validation opens the tab positioned on the merged block.",
    },
    "FUS-011": {
        "titre": "Merge: Id-collision guard rail",
        "pre": "In Scenario A, find (or create) a block whose Id already exists in the working copy but with a DIFFERENT Name.",
        "etapes": [
            "Right-click that block in A > merge/copy into the working copy.",
            "Open the working copy's file: the incoming block is added DEACTIVATED (commented) at the end of the file.",
            "Menu Verification > Pending blocks (Id conflicts)...: the block appears in the list.",
        ],
        "attendu": "The incoming block did NOT overwrite the existing one: added DEACTIVATED (commented) at the end of the file, listed in Pending blocks.",
    },
    "FUS-012": {
        "titre": "CSV merge: filling empty cells only",
        "etapes": [
            "Merge a CSV of A into the working copy (right-click in A > copy/merge to the working copy).",
            "Compare an editable row cell by cell.",
        ],
        "attendu": "Empty cells of the copy are filled from A; filled cells stay unchanged.",
    },
    "FUS-013": {
        "titre": "Global Undo last action button",
        "pre": "A merge/duplication/copy from A/B was just done (FUS-001 for example).",
        "etapes": [
            "Find the global Undo button (main window toolbar).",
            "Click it and watch the concerned files.",
        ],
        "attendu": "The operation is undone (files restored on disk); concerned tabs are closed or refreshed.",
    },
    "FUS-014": {
        "titre": "Sourceless Template: ALL other Templates' properties",
        "pre": "Templates.ecf contains at least one Template with an uncommon property (e.g. OutputCount).",
        "etapes": [
            "Duplicate a block WITHOUT a Template, accept the recipe proposal.",
            "Watch the properties list offered in the adjustment window.",
            "Compare with the properties actually present in Templates.ecf.",
        ],
        "attendu": "The list holds ALL properties observed on the file's other Templates (not only CraftTime/Target), each with its most common value.",
    },
    "FUS-015": {
        "titre": "Sourceless Template: property add via dropdown",
        "pre": "Template adjustment window open (block without source Template).",
        "etapes": [
            "Open the property-names dropdown, pick one.",
            "Open the associated values dropdown, pick one, validate.",
        ],
        "attendu": "Property addition goes through the same DROPDOWN form as the rest of the application (fixed in v1.6.1: it was a dialog without lists).",
    },
    "FUS-016": {
        "titre": "Sourceless Template: removing pre-filled properties",
        "pre": "Adjustment window open with several pre-filled properties.",
        "etapes": [
            "Select a property in the list, click « Remove property », validate the creation.",
            "Check Templates.ecf after creation (tab + disk after Ctrl+S).",
        ],
        "attendu": "The removed property does NOT appear on the created Template; the others are kept.",
    },
    "FUS-017": {
        "titre": "Template: dropdowns of common values and quantities",
        "pre": "Templates.ecf contains several Templates with varied values/quantities.",
        "etapes": [
            "In the adjustment window, open the value list of an existing property.",
            "Open the quantity list next to the ingredient add.",
        ],
        "attendu": "Both lists offer values/quantities actually observed in the file, frequency-sorted, with free input always possible.",
    },
    # ---------------------------------------------------------------- VERIF
    "VERIF-001": {
        "titre": "Check references (Ref:): detection",
        "pre": "A block with Ref: pointing to a missing name (e.g. Ref: NameThatDoesNotExist), SAVED (Ctrl+S).",
        "etapes": [
            "Save the modified file: the analysis reads the disk -- a prompt now offers to save modified tabs before the analysis (v1.6.1 fix: an unsaved edit was invisible).",
            "In the menu bar: Verification > Check working copy references (Ref)...",
            "Read the results (file + block given).",
        ],
        "attendu": "The orphan reference is reported with the file and the block. Deleting the VALUE of Ref is NOT a broken reference: no detection in that case, which is normal.",
    },
    "VERIF-002": {
        "titre": "References: double-click opens the file at the block",
        "etapes": [
            "In the Check references results window (VERIF-001), double-click a result.",
        ],
        "attendu": "The file opens in a tab, positioned on the involved block.",
    },
    "VERIF-003": {
        "titre": "References: Refresh + Export",
        "etapes": [
            "Fix one reported problem (without closing the results window), click Refresh.",
            "Then click Export, pick a location, open the exported report.",
        ],
        "attendu": "Results refresh (the fixed problem disappears); the export writes the full report as text.",
    },
    "VERIF-004": {
        "titre": "Cross-references: referenced items/blocks",
        "pre": "The checked convention: Name_N keys (e.g. Name_1:) whose VALUE is an item/block name. Simple test: in a block, add « Name_1: ItemThatDoesNotExist », save (Ctrl+S).",
        "etapes": [
            "Verification > Check cross-file references...",
            "Enable the items/blocks check (checkbox), run.",
            "Watch the result for ItemThatDoesNotExist.",
        ],
        "attendu": "ItemThatDoesNotExist is reported; an existing value (e.g. Name_1: SomeItem with SomeItem in ItemsConfig/BlocksConfig) is not.",
    },
    "VERIF-005": {
        "titre": "Cross-references: Token:XXXX tokens",
        "etapes": [
            "Verification > Check cross-file references..., enable the tokens check, run.",
            "Read the reported tokens and check one in TokenConfig.ecf.",
        ],
        "attendu": "Tokens REFERENCED but MISSING from TokenConfig.ecf are reported (real error). « Unused » tokens are INDICATIVE: a token consumed directly by the game (outside scenario files) will appear -- a triage tool, not an error list.",
    },
    "VERIF-006": {
        "titre": "Cross-references: Next/OptionNext dialogues + proposed FIX",
        "pre": "A Next_N/OptionNext_N reference pointing to a non-existing dialogue (typo or deleted dialogue).",
        "etapes": [
            "Verification > Check cross-file references..., enable the dialogues check, run.",
            "Double-click a broken result: a window EXPLAINS the problem and offers: replace with the closest name (suggested, editable via the existing-dialogues list), or delete the reference.",
            "Apply a fix, run the check again.",
            "Also test the « See in file » button: it navigates to the location without fixing.",
        ],
        "attendu": "The fix is written to disk (undoable via the global Undo button), the open tab is reloaded, and the re-run no longer shows the error.",
    },
    "VERIF-007": {
        "titre": "Business rules: Id limit 8192",
        "etapes": [
            "Create (or modify) a block with an Id GREATER than 8192 in the working copy, save (Ctrl+S).",
            "In the menu bar: Verification > Scenario health check... (business rules).",
            "Watch the result for that block.",
        ],
        "attendu": "The Id-limit overflow is reported.",
    },
    "VERIF-008": {
        "titre": "Business rules: containers without VolumeCapacity",
        "etapes": [
            "On a container requiring VolumeCapacity, delete that property (right-click > Delete), save.",
            "Run the health check (Verification > Scenario health check...).",
        ],
        "attendu": "The inconsistency (container without VolumeCapacity) is reported.",
    },
    "VERIF-009": {
        "titre": "Business rules: unknown materials and HoldType",
        "pre": "Material: tire in BlocksConfig.ecf AND HoldType: 99 in ItemsConfig.ecf (VOLUNTARY scope: each rule is only reliable in its confirmed file -- Material elsewhere means other concepts). Save both files.",
        "etapes": [
            "Run the validation (Verification > Scenario health check...). A save prompt for modified tabs is offered (v1.6.1).",
        ],
        "attendu": "Both unrecognized values are reported as warnings (they may be legitimate in a custom scenario).",
    },
    "VERIF-010": {
        "titre": "Business rules: unprotected commas",
        "etapes": [
            "Write a list value WITHOUT quotes in any property (e.g. SizeBlocks: 4,7 or TechTreeNames: Base,Capital Vessel), save, run the validation.",
            "Check the detection works across SEVERAL different keys (not just two).",
        ],
        "attendu": "Every unprotected comma is reported. (v1.6.1 fix: the rule now detects ANY value split in two by a comma, whatever the key.)",
    },
    "VERIF-011": {
        "titre": "Business rules: BlockColor format",
        "etapes": [
            "Set BlockColor: 170,170,170 WITHOUT quotes on a block, save, run the validation.",
        ],
        "attendu": "The incorrect format (values not protected by quotes) is reported.",
    },
    "VERIF-012": {
        "titre": "Business rules: Id/Name duplicates",
        "etapes": [
            "Deliberately create two blocks with the SAME Id in TWO different scenario files, save, run the validation.",
        ],
        "attendu": "The duplicate is reported with the involved files.",
    },
    "VERIF-013": {
        "titre": "Pending blocks: list + detailed comparison",
        "pre": "A pending block exists (first do FUS-011: merging a block whose Id already exists with a different Name).",
        "etapes": [
            "Menu Verification > Pending blocks (Id conflicts)...",
            "Select the pending block in the list.",
        ],
        "attendu": "Both versions (current active block vs deactivated pending block) are compared side by side clearly.",
    },
    "VERIF-014": {
        "titre": "Pending blocks: activation with a new Id",
        "pre": "A pending block exists (see VERIF-013).",
        "etapes": [
            "Menu Verification > Pending blocks..., select it.",
            "Choose the activation with a free Id AMONG THE DISPLAYED SUGGESTIONS.",
            "Confirm, then watch the file in the tab that opens.",
        ],
        "attendu": "The block is uncommented with the new Id; the open tab is reloaded automatically.",
    },
    "VERIF-015": {
        "titre": "Verification center: check everything at once",
        "etapes": [
            "Verification > Verification center (or the F5 key).",
            "Click the Check everything button.",
            "Watch the counters, then click a detail button.",
        ],
        "attendu": "The 5 families are re-run with counters; each detail button opens the matching verification window; the summary counts real problems (informative orphans excluded).",
    },

    # ---------------------------------------------------------------- SAUV
    "SAUV-001": {
        "titre": "Backing up a scenario (before update)",
        "etapes": [
            "File > Back up a scenario (before update)...",
            "Pick scenario A as source, a destination folder, run.",
            "Then open the backup manager (same menu, listing window) and watch.",
        ],
        "attendu": "A dated backup appears in the manager.",
    },
    "SAUV-002": {
        "titre": "Managing savegame backups: list (pre-filled folder)",
        "etapes": [
            "File > Manage my savegame backups...",
            "Watch the source field: pre-filled with the game's saves folder if it exists (Documents/Empyrion - Game Saves, editable).",
            "Repeat after changing the folder: it is remembered per type.",
        ],
        "attendu": "The window lists backups made BY THE APPLICATION; the source field is PRE-FILLED with the game's saves folder if present; storage folders are remembered per type (v1.6.1 fix).",
    },
    "SAUV-003": {
        "titre": "Restoring a backup + automatic safety backup",
        "etapes": [
            "In the manager (SAUV-002), select a backup and click Restore.",
            "After restoring, look in the storage folder for a safety backup created BEFORE the restore (carrying a safety/before-restore mention).",
        ],
        "attendu": "The restore applies; the before state is kept (automatic safety backup).",
    },
    "SAUV-004": {
        "titre": "Deleting a backup (confirmation)",
        "etapes": [
            "In the manager, select a test backup and click Delete.",
            "Confirm in the confirmation box.",
        ],
        "attendu": "Confirmation requested; effective deletion after confirming.",
    },
    "SAUV-005": {
        "titre": "Opening the backups folder",
        "etapes": [
            "In the manager, click Open folder.",
        ],
        "attendu": "Windows File Explorer opens at the right folder (the backups one).",
    },
    "SAUV-006": {
        "titre": "Compare with... a backup",
        "etapes": [
            "On a SCENARIO backup in the manager, click Compare with...",
        ],
        "attendu": "The comparison tool opens pre-filled with that backup (reference or modified side, depending on direction).",
    },
    "SAUV-007": {
        "titre": "Autosave: snapshot during an unsaved edit",
        "etapes": [
            "Change a file WITHOUT saving, wait for the autosave interval (a few dozen seconds).",
            {
                "txt": "Open the project's recovery folder: paste the path below into the Explorer address bar (replace <project-name>) -- hidden folder: enable View > Hidden items if needed.",
            },
        ],
        "attendu": "A snapshot file exists there, holding the UNSAVED version (protocol fix v1.6.1: exact path given -- the old steps only said ~/.empyrion_editor and users found nothing).",
    },
    "SAUV-008": {
        "titre": "Recovery at startup after a crash",
        "pre": "A recovery snapshot exists (SAUV-007). Close the application via Task Manager (Ctrl+Shift+Esc > right-click the application > End task: brutal kill, NOT a clean close).",
        "etapes": [
            "Start the application again.",
            "Reopen the SAME project (Recent projects).",
        ],
        "attendu": "The recovery dialog offers to restore the never-saved content (the SAUV-007 snapshot).",
    },
    "SAUV-009": {
        "titre": "Snapshot cleanup after saving",
        "etapes": [
            "Save the file that had a snapshot (Ctrl+S).",
            "Reopen the recovery folder (SAUV-007 path).",
        ],
        "attendu": "THAT file's snapshot is gone (the folder may remain, empty or with other files).",
    },
    "SAUV-010": {
        "titre": "Global undo: file restoration",
        "etapes": [
            "Do a duplication (FUS-001), then undo it via the global Undo button.",
            "Check the working copy's file (tab or Notepad).",
        ],
        "attendu": "The file is back to its pre-operation state (the duplicated block is gone).",
    },
    "SAUV-011": {
        "titre": "Atomic writing: crash during save",
        "pre": "Deliberately destructive test: on a TEST COPY only (never on your real project).",
        "etapes": [
            "Launch a scenario backup (large folder) and kill the process during the copy: Ctrl+Shift+Esc > Task Manager > right-click the application > End task.",
            "Start the application again, open the backups list (File > Back up / manager).",
        ],
        "attendu": "The backup does NOT appear in the list while incomplete (buffer folder *.inprogress, invisible and cleaned at the next attempt -- v1.6.1 fix: the truncated folder stayed in place). A restore also copies into a buffer BEFORE touching the destination: a crash during restore leaves the old content intact.",
    },
    "SAUV-012": {
        "titre": "Repairing working-copy permissions",
        "etapes": [
            "In Explorer: right-click the working copy folder > Properties > Security tab... or simpler: tick Read-only (Windows attribute) on the folder and apply.",
            "In the application: File > Repair working copy permissions.",
            "Check in Explorer that the attribute is gone.",
        ],
        "attendu": "Files become modifiable/deletable again (read-only attribute removed).",
    },
    # ---------------------------------------------------------------- COMP
    "COMP-001": {
        "titre": "Comparing two scenarios: colored tree",
        "etapes": [
            "File > Compare two scenarios...",
            "In the window, pick Scenario A (reference) on one side and a second scenario (modified) on the other (Browse buttons « ... »).",
            "Click Compare and watch the result tree.",
        ],
        "attendu": "Colored tree: added (green) / removed (red) / modified (orange) / identical (grey).",
    },
    "COMP-002": {
        "titre": "Comparison: per-filetype detail (+ added/removed content)",
        "etapes": [
            "In the comparison tree (COMP-001), click a modified ECF: the detail is block by block.",
            "Click a modified CSV: row by row detail; a modified YAML: key by key.",
            "Click an ADDED file (green) then a REMOVED one (red).",
        ],
        "attendu": "Precise detail for modified ECF/CSV/YAML; an ADDED or REMOVED file shows a (truncated) CONTENT PREVIEW instead of an empty message (v1.6.1 fix).",
    },
    "COMP-003": {
        "titre": "Also show identical files",
        "etapes": [
            "In the comparison window, tick « Also show identical files ».",
        ],
        "attendu": "The complete list appears, not only the differences.",
    },
    "COMP-004": {
        "titre": "Compare: exporting the report",
        "etapes": [
            "In the comparison window, click Export report, pick a location.",
            "Open the produced text file.",
        ],
        "attendu": "Complete text file written (atomically), readable, reproducing the difference tree.",
    },
    "COMP-005": {
        "titre": "Search across the whole scenario",
        "etapes": [
            "Tools > Search in scenario... (or Ctrl+Shift+F, or the toolbar).",
            "Type a known text (e.g. a block's Name), run the search.",
            "Watch the results: A / copy / B coverage, with files and location.",
        ],
        "attendu": "Results cover the three panels (A, working copy, B) with file and position of the found text.",
    },
    "COMP-006": {
        "titre": "Scenario search: opening a result",
        "etapes": [
            "Double-click a search result (COMP-005).",
        ],
        "attendu": "The file opens in a tab, at the found location.",
    },
    "COMP-007": {
        "titre": "PDA mission (old module): guided creation",
        "etapes": [
            "Tools > New PDA mission... (or Ctrl+M), follow the wizard to the creation (steps and Next button).",
        ],
        "attendu": "PDA files are created in the scenario, valid structure (checkable by opening PDA.yaml/PDA.csv).",
    },
    "COMP-008": {
        "titre": "PDA mission (old module): editing an existing mission",
        "etapes": [
            "Open an existing PDA mission (via the old PDA module), change a text or the mood, save.",
        ],
        "attendu": "Modification written faithfully; the mission stays loadable in game.",
    },
    "COMP-009": {
        "titre": "Extracting scenario properties",
        "etapes": [
            "File > Extract scenario properties...",
            "Run the extraction and open the produced CSV.",
        ],
        "attendu": "CSV generated: properties, occurrences, examples; numbered keys grouped (Name_N).",
    },
    "COMP-010": {
        "titre": "Search: regular expression mode",
        "etapes": [
            "Tools > Search in scenario...",
            "Tick Regular expression, search a pattern (e.g. Robo.*Dog).",
            "Then type an INVALID pattern (e.g. Robo([unclosed) and run again.",
        ],
        "attendu": "Regex patterns work on ECF/YAML/CSV; an invalid pattern shows an error message and KEEPS the previous search's results (list never emptied).",
    },

    # ---------------------------------------------------------------- TECH
    "TECH-001": {
        "titre": "Tech tree: categories, green tiles, adaptive layout",
        "etapes": [
            "Tools > Tech tree... (or Ctrl+T, or the toolbar).",
            "Compare with the game's F3 screen (same categories, same order).",
            "Watch the tiles under the icons (green, glossy effect).",
        ],
        "attendu": "Categories in game order (Base, CV, SV, HV, Misc, Tools, Weapons), Hidden never shown. Each icon set on a green button-style tile (gradient frame, glossy reflection).",
    },
    "TECH-002": {
        "titre": "Icons: scenario > built-in pack > generic",
        "etapes": [
            "WITHOUT a local itemicons folder: open the tech tree and check the icons come from the built-in pack.",
            "With SharedData/ItemIcons in the scenario: check a custom icon wins (place a test PNG icon named after an item).",
        ],
        "attendu": "Priority respected (scenario then built-in pack); otherwise generic icon (never an empty box nor a crash).",
    },
    "TECH-003": {
        "titre": "Simulated player level slider (REMOVED FEATURE)",
        "etapes": ["Feature removed at the user's request (protocol feedback v1.6.0). Mark as N/A."],
        "attendu": "N/A -- the feature no longer exists; the case is kept for numbering continuity.",
    },
    "TECH-004": {
        "titre": "Node tooltip",
        "etapes": [
            "In the tech tree, hold the mouse still over a node (without clicking) ~2 seconds.",
        ],
        "attendu": "A tooltip shows localized name, required level and cost.",
    },
    "TECH-005": {
        "titre": "Changing the required level (UnlockLevel)",
        "etapes": [
            "Grab an icon (hold left button) and drag it HORIZONTALLY to another level column, release.",
            "Check the file: the tree shows the modified file (TechTree tab, or disk after Ctrl+S).",
        ],
        "attendu": "UnlockLevel written to the right file (closest real column); the tree shows it live.",
    },
    "TECH-006": {
        "titre": "Changing the cost (UnlockCost)",
        "etapes": [
            "Click an icon: the card opens; click the cost value, change it, validate.",
            "Or: right-click the icon > change the cost.",
            "Check the file (tab or disk after Ctrl+S): UnlockCost.",
        ],
        "attendu": "UnlockCost updated correctly; the icon's badge and the card show the new value.",
    },
    "TECH-007": {
        "titre": "Guard rail: write refused if tab modified",
        "pre": "BlocksConfig.ecf open in a tab WITH an unsaved modification.",
        "etapes": [
            "From the tech tree, attempt a modification (icon drag, TECH-005) and dismiss the error box that appears.",
            "Then do another drag: the application must keep working.",
        ],
        "attendu": "The write is refused with a clear message, and the application KEEPS working normally afterwards (v1.6.1 fix: the error box destroyed the dragged item and the next mouse release crashed).",
    },
    "TECH-008": {
        "titre": "Auto-reload of the tab when unmodified",
        "pre": "BlocksConfig.ecf open in a tab WITHOUT modification.",
        "etapes": [
            "Change a level via the tech tree (TECH-005).",
            "Watch the open tab: it must show the new value.",
            "Then run a SEARCH in that tab (same word, twice: Enter, Enter).",
        ],
        "attendu": "The tab reloads automatically and shows the new value, and search still works after the reload (v1.6.1 fix: RuntimeError on every following search).",
    },
    "TECH-009": {
        "titre": "Move to a category (TechTreeNames)",
        "etapes": [
            "Right-click an item > Move to..., pick a category in the submenu.",
            "Check the file: TechTreeNames fully replaced, multiple values quoted.",
        ],
        "attendu": "TechTreeNames is replaced by the new category; multiple values quoted.",
    },
    "TECH-010": {
        "titre": "Changing the parent (pick mode) and root",
        "etapes": [
            "Right-click an item > Change parent: « pick » mode activates (banner if provided), click the new parent in the tree.",
            "Repeat while clicking a ROOT node to make it a root.",
        ],
        "attendu": "TechTreeParent written to the new parent; for a root, the property is DELETED (never left empty).",
    },
    "TECH-011": {
        "titre": "Global undo of a tree modification",
        "etapes": [
            "After a tree modification (TECH-005 to 010), click the main window's global Undo button.",
        ],
        "attendu": "The file is back to its previous state; the tree (reloaded) reflects it.",
    },
    "TECH-012": {
        "titre": "Previewing a new block in the tree (multiple moves)",
        "etapes": [
            "In the + Block wizard, click Preview in the tech tree...",
            "In the tree, move the surrounded icon: pick level/category/parent.",
            "Move it AGAIN several times (parent-pick mode is announced by an orange banner -- Esc to cancel).",
            "Validate the creation.",
        ],
        "attendu": "The preview block can be moved AS MANY TIMES as wanted; the chosen parent is honored in the result (v1.6.1 fix: pick mode silently activated and swallowed clicks).",
    },
    "TECH-013": {
        "titre": "Info card: Markdown export",
        "etapes": [
            "Open a block's info card (double-click in the ECF editor).",
            "Click the export button (next to the X), pick a .md file.",
            "Open the produced .md (Notepad or a Markdown editor).",
        ],
        "attendu": "Markdown file written, mirror of the card (description, stats, unlocking, crafting, price) without HTML tags; export confirmation.",
    },
    "TECH-014": {
        "titre": "Tech tree: unlock cost visible on every icon",
        "etapes": [
            "Tools > Tech tree...",
            "Watch the golden badge TOP LEFT of EVERY icon.",
            "Enlarge the window: icon and badge grow together.",
            "Hover an icon: the tooltip must confirm the same cost.",
        ],
        "attendu": "Every icon carries its UnlockCost (golden badge on a dark chip, TOP LEFT, font proportional to the icon); the number matches the tooltip.",
    },
    "TECH-015": {
        "titre": "Adaptive tree: levels 1 to 25 visible at any resolution",
        "etapes": [
            "Tools > Tech tree...",
            "Shrink the window to minimum, then maximize full screen (or on a second screen of another resolution).",
        ],
        "attendu": "The 9 milestones (Level 1 to Level 25) always remain ALL visible without horizontal scrolling; icons, tiles and badges grow/shrink with the window (min/max bounds to stay readable).",
    },
    "FICHE-001": {
        "titre": "Info card: opening by DOUBLE-clicking a block (ECF editor)",
        "etapes": [
            "In an ECF tab of the working copy, click ONCE a tree block: the card must not open.",
            "Then double-click the SAME block.",
        ],
        "attendu": "A single click does NOT open the card; only the double-click shows the floating card (COMPLETE view by default: every property, even « display: false »).",
    },
    "FICHE-002": {
        "titre": "Info card: COMPLETE view by default + translated labels and descriptions",
        "etapes": [
            "Open a known block's card (e.g. FuelTankMSLarge): ALL properties are visible, including « display: false » ones.",
            "Create or duplicate a block/Template, open its card BEFORE saving.",
            "Open the card of a SCENARIO block whose description exists in French in Extras/Localization.csv (even if its column header is called « French »).",
        ],
        "attendu": "COMPLETE view (default, request of 31/08/2026): all properties shown, « display: false » included. CREATED blocks: all their properties show, labels translated (Crafting time, Output quantity, Portable constructor for Target codes...) even if the game does not know the key. DESCRIPTION (Info) read from the SCENARIO's Localization.csv FR column first (« French » aliases recognized), fallback to the vanilla pack; ingredients confined to CRAFTING; no double colons.",
    },
    "FICHE-003": {
        "titre": "Info card: BBCode rendering in values",
        "pre": "A block with AllowPlacingAt (game color codes) or a BBCode Info:.",
        "etapes": [
            "Open its card (double-click) and watch the colored values.",
        ],
        "attendu": "The [c][RRGGBB]...[-][/c] codes render visually as in game (colors applied).",
    },
    "FICHE-004": {
        "titre": "Info card: moving and closing (toggle)",
        "etapes": [
            "Open a block's card by double-clicking, move it with the mouse (drag its title bar).",
            "Double-click the SAME block again: the card closes.",
            "Double-click ANOTHER block: it reopens on that one.",
        ],
        "attendu": "Double-clicking the already-shown block = the card closes (toggle); double-clicking another block = it reopens on that one, without losing its move.",
    },
    "FICHE-005": {
        "titre": "Info card: INLINE editing of a value (ECF editor)",
        "pre": "Working-copy ECF tab open.",
        "etapes": [
            "Double-click a block to open its card.",
            "Click a value (e.g. HitPoints): an EDITABLE dropdown appears (observed file values, frequency sort, visible arrow) with the current RAW value.",
            "Pick a proposed value OR type one freely, validate with Enter.",
            "Also test Esc while typing (cancels), then the tab undo (Ctrl+Z).",
        ],
        "attendu": "The file is modified (✎ * marker, modification counter up to date, origin annotation), the property table AND the card show the new value; tab undo goes back to the old value. Esc while typing cancels without writing. Without history for the key: plain free input.",
    },
    "FICHE-006": {
        "titre": "Info card: add / delete a property (dropdowns)",
        "etapes": [
            "Open a block's card, click « + Add a property »: the key and value combos offer the file's observed keys/values (free input possible).",
            "Fill and validate.",
            "Then right-click that new row > Delete this property.",
        ],
        "attendu": "The property is added to the block (visible card + table + file, undoable) then deleted. The opening-row properties (Id, Name) are never deletable.",
    },
    "FICHE-007": {
        "titre": "Info card: editable Template ingredients (quantities, add, delete)",
        "pre": "A block whose Template exists in Templates.ecf.",
        "etapes": [
            "Open the block's card, CRAFTING section.",
            "Click an ingredient quantity, change it, validate.",
            "Add an ingredient (« + Add an ingredient »): the combo offers item/block NAMES (ItemsConfig + BlocksConfig); type or pick one, enter a quantity, validate.",
            "Then delete it (right-click > Delete this ingredient).",
        ],
        "attendu": "Templates.ecf is updated (open tab: marked modified; otherwise direct disk write with global undo); the card refreshes quantities live.",
    },
    "FICHE-008": {
        "titre": "Info card editable from the tech TREE",
        "etapes": [
            "Tools > Tech tree...",
            "Plain click (no drag) on an icon: the card opens; double-click too.",
            "Change a value (e.g. the cost) and validate.",
            "Click the global Undo button.",
        ],
        "attendu": "The card opens on the node, complete and editable. Every modification writes the file (global undo recorded, open tab reloaded, tree and badge updated live); Undo restores the previous state. Dragging an icon does NOT open the card.",
    },
    "FICHE-009": {
        "titre": "Info card: « Game view (faithful F3) » / full view toggle",
        "etapes": [
            "Open the card of a real game block (with display attributes).",
            "Tick « Game view (faithful F3) » at the top of the card, then untick it.",
            "Export the card to Markdown in each mode (TECH-013) and compare the contents.",
        ],
        "attendu": "Ticked: the card falls back to the game's faithful F3 (« display: false » hidden). Unticked (default): everything visible. The Markdown export always reflects the displayed view.",
    },
    "FICHE-010": {
        "titre": "Info card: editing the DESCRIPTION (FR + EN, BBCode, translation)",
        "pre": "A block WITH a description (Info: property + Localization.csv row) and a block WITHOUT Info:.",
        "etapes": [
            "Open a block's card, click the PENCIL next to « Description ».",
            "Test the bar: bold/italic/underline (around the selection), color (palette -> [c][hex]...[-][/c]).",
            "Test translation: FR -> EN / EN -> FR buttons, and right-click in a field > Translate to...",
            "Edit, validate. Repeat on the block WITHOUT Info: (the window offers to CREATE the key).",
        ],
        "attendu": "The window pre-fills FR/EN from Localization.csv. The bar inserts BBCode in the ACTIVE editor (the one you clicked/caret-moved into), around the selection. Translation uses the existing mechanism (online engine, confirmation before replacement); without translation configured, buttons are greyed and right-click explains why. On validation: CSV updated (other columns preserved), card refreshed, undoable via the global Undo button. Block without Info:: property added + CSV row created.",
    },
    # ---------------------------------------------------------------- OPT
    "OPT-001": {
        "titre": "Options: name for annotations",
        "etapes": [
            "Options > Name for annotations..., type a recognizable name (e.g. David), validate.",
            "Change a value in an ECF tab, save (Ctrl+S), open the raw file (ECF-006).",
        ],
        "attendu": "New annotations carry the new name (« -- Mod by David »).",
    },
    "OPT-002": {
        "titre": "Options: allow merging (activation)",
        "etapes": [
            "Tick Options > Allow merging (experimental, disabled by default).",
            "Right-click a file of the A/B panels: merge actions appear.",
            "Untick the option: the actions disappear.",
        ],
        "attendu": "Merge actions appear in the context menu (and disappear when unticked).",
    },
    "OPT-003": {
        "titre": "Options: default translation language",
        "etapes": [
            "Options > Default translation language..., change the language, validate.",
            "In a CSV tab, click the quick Translate button on a cell.",
        ],
        "attendu": "The quick translation targets the configured language (TRAD-004).",
    },
    "OPT-004": {
        "titre": "Options: visual theme (hot change)",
        "etapes": [
            "Open a loaded session (project + several tabs), change the theme in Options > Theme.",
            "Watch: the interface repaints IN A SINGLE pass (no progressive sweep).",
            "Switch to the Verriere theme WITHOUT restarting, then switch back to another theme.",
        ],
        "attendu": "The theme applies immediately and persists across restart. v1.6.1 fix: intermediate repaints are frozen during the swap (no visible trail), and Verriere re-attempts the acrylic blur ON THEME CHANGE, not only at startup.",
    },
    "OPT-005": {
        "titre": "i18n: no raw key on screen (FR)",
        "etapes": [
            "Browse ALL menus (File, Options, Tools, Verification, Help) and the main windows in French.",
            "Look for suspicious texts like « menu.xxx » or « runner.xxx ».",
        ],
        "attendu": "No « menu.xxx »-like string nor missing text: everything is translated.",
    },
    "OPT-006": {
        "titre": "i18n: no raw key on screen (EN)",
        "etapes": [
            "Switch to English (FR/EN button), browse the same screens as in OPT-005.",
        ],
        "attendu": "Everything is translated to English, no FR key visible. (Known remainder: the card's property explanations stay FR -- postponed, large content work.)",
    },
    "OPT-007": {
        "titre": "Help: FR/EN wikis readable",
        "etapes": [
            "Help > Application wiki (features)..., in FR then EN (flip the FR/EN button between the two).",
            "Help > Empyrion wiki (properties, files, structure)..., in FR then EN.",
        ],
        "attendu": "The 4 wikis open in the expected language, up-to-date content.",
    },
    "OPT-008": {
        "titre": "Help: tutorials + privacy policy + about",
        "etapes": [
            "Help > Tutorials...: open the 3 tutorials.",
            "Help > Privacy policy... then Help > About...",
        ],
        "attendu": "The official GPLv3 text opens in English (the only legally binding version) with an explanatory NOTE shown in About (clarified v1.6.1).",
    },
    "OPT-009": {
        "titre": "i18n: standard Qt buttons in the chosen language",
        "etapes": [
            "In French, open a Yes/No confirmation box (e.g. duplication with recipe creation).",
            "Switch to English (FR/EN button) and reopen the same box.",
        ],
        "attendu": "Buttons show Oui/Non in French, Yes/No in English (never reversed nor forced English).",
    },
    "OPT-010": {
        "titre": "Automatic i18n audit without regression",
        "etapes": [
            {
                "txt": "From the repository root (developers), run:",
            },
        ],
        "attendu": "Return code 0: no missing t() key, no key without fr/en, no hardcoded displayed literal in gui/ and core/.",
    },

    # ---------------------------------------------------------------- CLI
    "CLI-001": {
        "titre": "CLI: verifier_parser_ecf + opening a command prompt",
        "etapes": [
            "Open a command prompt: Windows key + R, type cmd, press Enter (a black window opens).",
            {
                "txt": "INSTALLED APPLICATION version: paste the 1st command (replace <file> with the file path, Shift+right-click the file > Copy as path).",
            },
            {
                "txt": "REPOSITORY version (developers): paste the 2nd command from the repo root -- all CLI scripts are in cli/ (protocol fix v1.6.1).",
            },
        ],
        "attendu": "ECF round-trip verified (OK message), or clear listed errors.",
    },
    "CLI-002": {
        "titre": "CLI: verifier_parser_yaml",
        "etapes": [
            "Command prompt open (CLI-001), then:",
            {
                "txt": "Paste one of the commands (replace <file>) -- installed form then repository form (scripts in cli/, see CLI-001):",
            },
        ],
        "attendu": "YAML round-trip confirmed, or clear errors.",
    },
    "CLI-003": {
        "titre": "CLI: verifier_parser_csv",
        "etapes": [
            {
                "txt": "Paste one of the commands (replace <file>):",
            },
        ],
        "attendu": "CSV round-trip confirmed.",
    },
    "CLI-004": {
        "titre": "CLI: diagnostic_bloc",
        "etapes": [
            {
                "txt": "Search a block by Id, including in comments (replace <file> and <Id> -- e.g. 1625):",
            },
        ],
        "attendu": "The block is found and displayed, even when commented out (deactivated).",
    },
    "CLI-005": {
        "titre": "CLI: detecter_imbrication_anormale",
        "etapes": [
            {
                "txt": "On a healthy file, then on a crafted case (a block whose closing brace was deleted):",
            },
        ],
        "attendu": "No false detection on the healthy file; detection on the crafted case.",
    },
    "CLI-006": {
        "titre": "CLI: diff_ecf",
        "etapes": [
            "Make two copies of a file and modify a block in one (add a block in one of the two).",
            {
                "txt": "Compare the two versions (replace <versionA> and <versionB>):",
            },
        ],
        "attendu": "Added/deleted/modified blocks correctly listed.",
    },
    "CLI-007": {
        "titre": "CLI: edit_ecf interactive",
        "etapes": [
            {
                "txt": "Launch the interactive editor (replace <file>), browse the commands (built-in help), quit WITHOUT modifying (exit command given by the help, e.g. q):",
            },
        ],
        "attendu": "Working navigation, no accidental modification on exit.",
    },
    "CLI-008": {
        "titre": "CLI: merge_ecf",
        "etapes": [
            {
                "txt": "Merge two sources into an output (replace <output>, <source1>, <source2> -- on TEST COPIES), then verify the output (verifier-ecf):",
            },
        ],
        "attendu": "Merge conforming to the priorities; faithful output (verifier-ecf OK).",
    },
    "CLI-009": {
        "titre": "CLI: transform_ecf",
        "etapes": [
            "On a TEST COPY, prepare a transform (multiply a property x2): the command without arguments prints its detailed usage.",
            {
                "txt": "Run the transform (see printed usage), then verify the result (verifier-ecf):",
            },
        ],
        "attendu": "Transform applied only to the target blocks, valid file after checking.",
    },
    # ---------------------------------------------------------------- ROBU
    "ROBU-001": {
        "titre": "Closing without modification: immediate",
        "etapes": [
            "With no modified tab (all tab titles normal, none red), close the application (X at the top right).",
        ],
        "attendu": "Immediate close, no dialog.",
    },
    "ROBU-002": {
        "titre": "Closing with modified tabs: dialog",
        "etapes": [
            "Modify TWO files without saving (two red tabs), then close the application.",
            "Read the dialog: file list, Save all / Discard / Cancel buttons.",
            "Test the three buttons (restart the scenario each time).",
        ],
        "attendu": "APPLICATION-styled dialog listing the files: Save all (default) / Discard / Cancel -- Cancel brings you back into the application with nothing lost.",
    },
    "ROBU-003": {
        "titre": "Closing: failed save cancels the exit",
        "pre": "Make an open, modified file read-only at system level: right-click the file > Properties > tick Read-only (do it while the application is closed, then restart it with the file open and modified).",
        "etapes": [
            "Close the application and choose Save in the closing dialog.",
        ],
        "attendu": "Error shown for the failing file, the close is CANCELLED, the work stays open.",
    },
    "ROBU-004": {
        "titre": "Excepthook: dialog instead of a brutal crash",
        "etapes": [
            "Trigger an internal error (or wait for a real one): for example unplug a device during an operation, or report any abnormal behavior.",
        ],
        "attendu": "Dialog with expandable details and a Report button; the application does NOT close.",
    },
    "ROBU-005": {
        "titre": "Update check: silent + manual",
        "etapes": [
            "Start the application (silent automatic check at startup).",
            "Help > Check for updates... (manual).",
        ],
        "attendu": "Auto: nothing if no update; manual: a message even on equality/failure.",
    },
    "ROBU-006": {
        "titre": "Report button: pre-filled form",
        "etapes": [
            "Open the error dialog (ROBU-004) or Help > Report a bug / suggest an improvement..., click Report.",
            "Fill the form and click Send: the browser opens on GitHub.",
        ],
        "attendu": "The GitHub page opens pre-filled (title, description, technical info, screenshot to attach); nothing is sent automatically without you.",
    },
    "ROBU-007": {
        "titre": "Corrupted settings: startup anyway",
        "pre": "Close the app, open the folder below (hidden user-profile folder -- NOT the repo root; protocol fix v1.6.1) and replace settings.json's content by xxx.",
        "etapes": [
            {
                "txt": "Open the folder (Explorer address bar), open settings.json with Notepad, replace everything by xxx, save:",
            },
            "Start the application, check the options, change one option.",
        ],
        "attendu": "Normal startup (default values), settings rebuilt at the next write.",
    },
    "ROBU-008": {
        "titre": "Corrupted recent projects: empty list, no crash",
        "pre": "Close the app, corrupt projects.json (same folder as ROBU-007) by writing xxx into it.",
        "etapes": [
            {
                "txt": "Open the folder (Explorer address bar), open projects.json with Notepad, replace everything by xxx, save:",
            },
            "Start the application, open File > Recent projects...",
        ],
        "attendu": "Empty or partial list without a crash.",
    },
    "ROBU-009": {
        "titre": "Test protocol accessible in the application",
        "etapes": [
            "Help > Test protocol (tutorial / debugging)...",
            "Click « Start a test session... »: pick blank or resume, test case by case (steps, F1 to F4 verdicts).",
            "Browse the categories, filter by keyword, export the summary to Markdown/CSV.",
        ],
        "attendu": "The full step-by-step is available IN the application (embedded engine); verdicts are saved between launches; the export writes a complete summary. « Preparation » and « Expected result » bars READABLE on light AND dark themes (dark text on light background).",
    },

    # ---------------------------------------------------------------- BUILD
    "BUILD-001": {
        "titre": "Installer: clean installation",
        "pre": "The release's installer to test (Setup-EmpyrionScenarioEditor-vX.Y.Z.exe).",
        "etapes": [
            "Double-click the Setup on a clean machine (or VM) -- without Python installed.",
            "Follow the installation wizard (Next, Install, Finish).",
            "Start the application from the created shortcut (desktop or Start menu).",
        ],
        "attendu": "Installation without error; the application starts, everything works (wikis, icons, localization pack, embedded test protocol).",
    },
    "BUILD-002": {
        "titre": "Clean uninstallation",
        "etapes": [
            "Windows Settings > Apps > Empyrion Scenario Editor > Uninstall (or control panel).",
            "After uninstalling, check both locations: the Program Files folder, and the user's hidden folder (command below).",
            {
                "txt": "User data folder (must REMAIN):",
            },
        ],
        "attendu": "Complete uninstallation of program files; user data (~/.empyrion_editor) remains, documented.",
    },
    "BUILD-003": {
        "titre": "Embedded CLI: standalone EmpyrionEditorCLI",
        "etapes": [
            "Command prompt (CLI-001) WITHOUT Python installed (installer machine).",
            {
                "txt": "Run a command (replace <file>):",
            },
            "Run it WITHOUT arguments to see the command list.",
        ],
        "attendu": "Works without Python installed, results identical to the repository scripts.",
    },
    "BUILD-004": {
        "titre": "Update checker: release detection",
        "pre": "The <version> release is published on GitHub.",
        "etapes": [
            "With an OLDER version installed, start the application and wait a few seconds at startup.",
            "Then, with the up-to-date version, restart: no more proposal.",
        ],
        "attendu": "The <version> update is offered at startup (and not offered when already up to date).",
    },

    # ---------------------------------------------------------------- GUI
    "GUI-001": {
        "titre": "Theme H - Verriere neon: toggle and rendering",
        "etapes": [
            "Options > Theme > H - Verriere neon.",
            "Watch the colors (ocean black + cyan), the glass panels, the active buttons' gloss.",
            "Switch back to the previous theme then return.",
        ],
        "attendu": "Immediate toggle without restart; NEON selections (halo + trim + light text) in the tree and the table; other themes unchanged.",
    },
    "GUI-002": {
        "titre": "Verriere theme: Windows 11 acrylic blur",
        "pre": "Windows 11 22H2 minimum (build 22621) AND Windows transparency effects enabled (Settings > Personalization > Colors). Restart the application with theme H active.",
        "etapes": [
            "Place a COLORFUL window (browser, picture...) behind the editor.",
            "Watch the TITLE BAR: it shows the blurred background.",
            "Move the editor and watch that background change.",
            "Also change theme hot: Verriere re-attempts the blur without restart (see OPT-004).",
        ],
        "attendu": "The content BEHIND the window appears blurred (acrylic) -- most visible on the title bar; panels stay painted for readability. v1.6.1 FIX: DwmExtendFrameIntoClientArea(-1) was missing -- the backdrop attribute ALONE produces no visible effect (verified with side-by-side screenshots). Without support (Win10, remote desktop, transparency off): theme-painted background, nothing unreadable.",
    },
    "GUI-003": {
        "titre": "Toolbar: readable in ALL themes",
        "etapes": [
            "Switch successively to Classic (light), B, H themes (Options > Theme).",
            "Watch the 6 buttons of the top bar (Save, Search, Tree, Galaxy, PDA, Verification center).",
        ],
        "attendu": "Auto-painted buttons (accent-blue background, white icons + labels) readable on any background; on theme change, labels follow the language and theme.",
    },
    "GUI-004": {
        "titre": "Toolbar: the 6 buttons open the right windows",
        "etapes": [
            "With a project open, click successively Save, Search, Tech tree, Galaxy map, PDA missions, Verification center.",
            "For each, compare with the equivalent menu entry.",
        ],
        "attendu": "Each button opens exactly the same window as its menu entry.",
    },
    "GUI-005": {
        "titre": "Keyboard shortcuts displayed and working",
        "etapes": [
            "Open the Tools and Verification menus and read the shortcuts shown on the right of the labels.",
            "Test Ctrl+Shift+F (search), Ctrl+T (tree), Ctrl+G (galaxy), Ctrl+M (PDA), F5 (verification center) -- keys together.",
        ],
        "attendu": "All shortcuts are visible in their menu; the Verification center label was shortened so the F5 is no longer truncated (v1.6.1 fix).",
    },
    "GUI-006": {
        "titre": "Modification counter in the banner",
        "etapes": [
            "Modify 2 open files without saving.",
            "Watch the Working copy panel's label.",
            "Save each modified tab (Ctrl+S in each tab, or the toolbar's Save button) then watch again.",
        ],
        "attendu": "Label: « Working copy -- N modified file(s) » with the right count; back to « Working copy (editable) » after saving.",
    },
    "GUI-007": {
        "titre": "Status bar: persistent project summary",
        "etapes": [
            "Open a project, modify a file.",
            "Trigger a transient message (e.g. an action showing a message at the bottom of the window).",
        ],
        "attendu": "The « project - N modified » summary stays displayed on the RIGHT of the status bar, never overwritten by transient messages; it shows « No open project » without a project.",
    },
    "GUI-008": {
        "titre": "Loading box on long operations",
        "etapes": [
            "Resume a recent project (Recent projects).",
            "Run F5 (Verification center) then a global search (Ctrl+Shift+F).",
            "Watch the window bottom during each operation, and try clicking elsewhere.",
        ],
        "attendu": "Immediate « Processing... » box + hourglass cursor; clicking elsewhere is impossible during the operation; clean disappearance at the end (even on error).",
    },

    # ---------------------------------------------------------------- PDA2
    "PDA2-001": {
        "titre": "PDA editor: opening on a real scenario",
        "etapes": [
            "Open a project whose scenario contains Extras/PDA/PDA.yaml + PDA.csv (e.g. vanilla).",
            "Tools > PDA Editor (new).",
            "Watch the tree: chapters, then expand (small arrows) into tasks then actions.",
        ],
        "attendu": "The tree shows ALL chapters (titles resolved from PDA.csv, app language), expandable into tasks then actions (Check type label). Opening covered by the hourglass, no freeze.",
    },
    "PDA2-002": {
        "titre": "PDA editor: editing a chapter",
        "etapes": [
            "Select a chapter in the tree.",
            "Change the Required level, untick Non-skippable, edit the Description (FR text).",
            "Close the editor (X), watch the PDA.yaml tab (Ctrl+S to save) then the PDA.csv tab.",
        ],
        "attendu": "The PDA.yaml/PDA.csv tabs are marked modified; the YAML holds the changes (key deleted when unticked, except structural keys); the CSV holds the new text under a pda_XXXXXXX token, WITHOUT duplicate if the text already existed.",
    },
    "PDA2-003": {
        "titre": "PDA editor: actions of every Check type",
        "etapes": [
            "Select an action, change its type (e.g. WaitAction -> NearPoi).",
            "Fill the form fields (POI via the searchable list, distances).",
            "Add a « No objective (plain text) » action and an action of a type absent from the form.",
        ],
        "attendu": "The form follows the chosen type (specific fields confirmed on real files). Actions without a Check stay plain text. An unknown type stays editable (properties preserved).",
    },
    "PDA2-004": {
        "titre": "PDA editor: rewards, repetition, activations",
        "etapes": [
            "On a chapter: add an Item reward (MoneyCard at the head of suggestions) and a Faction reputation.",
            "Set the Repeat count.",
            "Add an activation (ChapterActivation): POI input, switch to an explicit Check (e.g. DialogOption) then back to implicit.",
            "Save and check the YAML (PDA.yaml tab).",
        ],
        "attendu": "Rewards in real shapes (Item+Count[+Meta] / Type+Count[+Faction]), RepeatConditions added/removed cleanly, ChapterActivation with first key « Names » or « Check » depending on the Check field (empty = the game's majority implicit form).",
    },
    "PDA2-005": {
        "titre": "PDA editor: creation, duplication, deletion, move",
        "etapes": [
            "Create a new chapter (+ buttons of the tree).",
            "Duplicate an existing chapter and compare both in the tree.",
            "Move (▲/▼ buttons) then delete after confirmation.",
        ],
        "attendu": "The duplicate re-tokenizes ALL its texts (independent titles/descriptions, CSV rows added) and inserts right after the original. Move and deletion (with confirmation) reflected in the tree and the YAML.",
    },
    "PDA2-006": {
        "titre": "PDA mission wizard (3 steps)",
        "etapes": [
            "PDA editor > Creation wizard...: fill step 1, move to step 2 (Next).",
            "Add 2 actions of different types with their quantities, move to step 3.",
            "Type titles/description + a reward, click Create chapter.",
        ],
        "attendu": "The chapter appears selected in the tree with configured task and actions; texts present in the CSV; YAML structure conforming (ChapterTitle/Category/NoSkip/Activatable/Visibility/PlayerLevel/Description + Tasks + Rewards). The typed title IS applied to ChapterTitle.",
    },
    "PDA2-007": {
        "titre": "PDA editor: scenario + vanilla suggestions",
        "etapes": [
            "Options: fill (or not) the game's Content folder (Steam install) via Options > Game folder (vanilla)...",
            "Open the PDA editor, open the POI/Playfields list of a NearPoi then a PlayfieldEntered.",
        ],
        "attendu": "Lists offer the open scenario's values COMPLETED by vanilla (POI, playfields, creatures) when the folder is set; without it, scenario values + already used in the PDA; free input always possible.",
    },
    "PDA2-008": {
        "titre": "PDA editor: changes visible in the YAML/CSV tabs",
        "etapes": [
            "Edit several elements in the PDA editor (text, list, reward), close the editor.",
            "Watch the PDA.yaml tab then the PDA.csv tab.",
        ],
        "attendu": "In PDA.yaml, the tree highlights (pale yellow background) modified entries; in PDA.csv, rows of created/modified tokens are highlighted the same way. Prefixed values (« mbox;20|pda_XXX ») show a green check and keep their prefix after editing.",
    },
    "PDA2-009": {
        "titre": "PDA editor: Undo button",
        "etapes": [
            "Edit a field, add then delete an activation, create a chapter.",
            "Click the « Undo » button several times in a row.",
        ],
        "attendu": "Each click restores the previous state of both in-memory files (deleted chapter reappears, field regains its value, the selected element stays relevant); the button greys out when the stack is empty. After closing, the tabs reflect the final state.",
    },
    "PDA2-010": {
        "titre": "PDA editor: reminder of last modifications on resume",
        "etapes": [
            "Make a few modifications, close the editor (the tabs stay modified, do not save yet).",
            "Save (Ctrl+S), close the application, restart, reopen the same scenario and the PDA editor.",
        ],
        "attendu": "A grey banner at the top of the editor recalls the previous session's last modifications (timestamped, label of each touched element); a complete journal is kept in ~/.empyrion_editor/pda_history.json (local, never versioned).",
    },
    "PDA2-011": {
        "titre": "PDA editor: readable translation button",
        "etapes": [
            "Select an action, watch the button to the right of each localized text field (Description, Completion message...).",
            "Click it, then right-click the field.",
        ],
        "attendu": "The button shows the application's qtawesome GLOBE (not a blue emoji square) and clicking it opens the token's all-languages editor; right-clicking the field always offers « Translate to... ».",
    },
    "PDA2-012": {
        "titre": "PDA editor: titles editable everywhere + nothing invisible",
        "etapes": [
            "Select a chapter, a task then an action: the TITLE is offered at the head of each panel (editable).",
            "Edit the chapter's title: the tree updates without losing the typing.",
            "Open a rich chapter/task from a real file (e.g. with OnComplete*Ops, PlayfieldTypes, VisibleOnStart...).",
        ],
        "attendu": "Everything visible: scalars and lists (Playfields, PlayfieldTypes, VisibleOnStart..., RewardedTasks/Chapters, signals) in the form; complex sections (On*Ops) shown as « Advanced (read-only) ». The chapter title typed in the wizard IS applied to ChapterTitle. Title editing: token kept, CSV text updated (no orphan key).",
    },
}


CATEGORY_LABELS_EN = {
    "PROJ": "1. Projects & panels",
    "OPEN": "2. Opening & navigation",
    "ECF": "3. ECF editing",
    "DLG": "4. Dialogues.ecf",
    "YAML": "5. YAML / Playfields editing",
    "MAP": "6. 2D map / POI / Galaxy",
    "CSV": "7. CSV editing",
    "TRAD": "8. Translation",
    "FUS": "9. Copy / merge / duplicate",
    "VERIF": "10. Checks",
    "SAUV": "11. Backups & recovery",
    "COMP": "12. Comparison / search / PDA",
    "TECH": "13. Tech tree & info card",
    "OPT": "14. Options & i18n",
    "CLI": "15. CLI",
    "ROBU": "16. Robustness",
    "BUILD": "17. Installer / build",
    "GUI": "18. Interface, toolbar & theme",
    "PDA2": "19. PDA editor (new module)",
}
