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
Systeme de traduction de l'interface (FR/EN). Usage :

    from core.i18n import t
    label = QLabel(t("menu.file"))

La langue active est lue/ecrite via core.settings (persistee entre sessions). Bascule
en direct via set_language() -- les widgets deja crees doivent etre reconstruits ou
avoir leur texte reassigne manuellement pour refleter le changement (voir
gui/main_window.py, _apply_language()).
"""
from core import settings

# Format : "cle" -> {"fr": "...", "en": "..."}
STRINGS = {
    # --- Menu Fichier ---
    "menu.file": {"fr": "&Fichier", "en": "&File"},
    "menu.file.new_project": {"fr": "&Nouveau projet...", "en": "&New project..."},
    "menu.file.recent_projects": {"fr": "&Projets recents...", "en": "&Recent projects..."},
    "menu.file.save": {"fr": "&Enregistrer", "en": "&Save"},
    "menu.file.quit": {"fr": "&Quitter", "en": "&Quit"},

    # --- Menu Verification ---
    "menu.verification": {"fr": "&Verification", "en": "&Verification"},
    "menu.verification.check_refs": {"fr": "Verifier les references (Ref) de la copie de travail...",
                                      "en": "Check references (Ref) in the working copy..."},
    "menu.verification.pending": {"fr": "Blocs en attente (conflits d'Id)...",
                                   "en": "Pending blocks (Id conflicts)..."},
    "menu.verification.cross_refs": {"fr": "Verifier les references croisees "
                                            "(entre fichiers)...",
                                      "en": "Check cross-file references..."},

    "validation.menu_action": {"fr": "Valider les regles metier (Id, materiaux, "
                                    "conteneurs, doublons...)...",
                                "en": "Validate business rules (Id, materials, "
                                      "containers, duplicates...)..."},
    "validation.dialog_title": {"fr": "Validation du scenario", "en": "Scenario validation"},
    "validation.header": {"fr": "Validation du scenario : {root}", "en": "Scenario validation: {root}"},
    "validation.filter_errors": {"fr": "Erreurs", "en": "Errors"},
    "validation.filter_warnings": {"fr": "Avertissements", "en": "Warnings"},
    "validation.col_element": {"fr": "Element", "en": "Element"},
    "validation.col_code": {"fr": "Code", "en": "Code"},
    "validation.col_message": {"fr": "Message", "en": "Message"},
    "validation.n_issues": {"fr": "{n} probleme(s)", "en": "{n} issue(s)"},
    "validation.all_ok": {"fr": "Aucun probleme detecte -- le scenario est valide !",
                           "en": "No issues found -- scenario is valid!"},
    "validation.summary": {"fr": "{errors} erreur(s), {warnings} avertissement(s)",
                            "en": "{errors} error(s), {warnings} warning(s)"},
    "validation.close": {"fr": "Fermer", "en": "Close"},

    "canvas.no_selection": {"fr": "Clique une entite pour voir son detail.",
                             "en": "Click an entity to see its details."},
    "canvas.filters_label": {"fr": "Genres affiches", "en": "Shown kinds"},
    "canvas.n_shown": {"fr": "{n} entite(s) affichee(s)", "en": "{n} entitie(s) shown"},
    "canvas.n_without_position": {"fr": "{n} sans position exploitable (non affichees)",
                                   "en": "{n} without a usable position (not shown)"},
    "playfield.tab_canvas": {"fr": "Carte 2D", "en": "2D Map"},

    "poi_inspector.title": {"fr": "Inspecteur de POI", "en": "POI Inspector"},
    "poi_inspector.tab_detail": {"fr": "Detail par POI", "en": "Detail per POI"},
    "poi_inspector.tab_by_faction": {"fr": "Par faction", "en": "By faction"},
    "poi_inspector.col_name": {"fr": "Nom", "en": "Name"},
    "poi_inspector.col_faction": {"fr": "Faction", "en": "Faction"},
    "poi_inspector.col_count": {"fr": "Quantite", "en": "Count"},
    "poi_inspector.col_poi_count": {"fr": "Nombre de POI", "en": "POI count"},
    "poi_inspector.col_drones_est": {"fr": "Drones estimes", "en": "Estimated drones"},
    "poi_inspector.n_pois": {"fr": "{n} POI aleatoire(s) analyse(s)", "en": "{n} random POI analyzed"},
    "menu.tools.poi_inspector": {"fr": "Inspecteur de POI...", "en": "POI Inspector..."},

    "galaxy.title": {"fr": "Carte de la galaxie", "en": "Galaxy map"},
    "galaxy.not_found": {"fr": "Aucun fichier Sectors.yaml trouve dans ce scenario.",
                          "en": "No Sectors.yaml file found in this scenario."},
    "galaxy.n_systems": {"fr": "{n} systeme(s) solaire(s)", "en": "{n} solar system(s)"},
    "galaxy.n_sectors": {"fr": "{n} secteur(s) local(aux)", "en": "{n} local sector(s)"},
    "galaxy.tilt_label": {"fr": "Inclinaison (axe Y) :", "en": "Tilt (Y axis):"},
    "galaxy.role": {"fr": "role special", "en": "special role"},
    "galaxy.spectral": {"fr": "classe spectrale", "en": "spectral class"},
    "menu.tools.galaxy_viewer": {"fr": "Carte de la galaxie (Sectors.yaml)...",
                                  "en": "Galaxy map (Sectors.yaml)..."},

    "results_export.title": {"fr": "Exporter les resultats", "en": "Export results"},
    "results_export.done_title": {"fr": "Export termine", "en": "Export complete"},
    "results_export.done_msg": {"fr": "Resultats exportes vers :\n{path}",
                                 "en": "Results exported to:\n{path}"},
    "results_export.error": {"fr": "Impossible d'ecrire le fichier", "en": "Could not write file"},
    "results_window.btn_export": {"fr": "Exporter...", "en": "Export..."},
    "results_window.btn_refresh": {"fr": "Actualiser", "en": "Refresh"},

    "crossref.title": {"fr": "References croisees entre fichiers",
                        "en": "Cross-file references"},
    "crossref.intro": {"fr": "Verifie que ce qu'un fichier mentionne (un item, un "
                              "bloc, un jeton...) existe bien reellement ailleurs "
                              "dans le scenario. Coche les verifications voulues, "
                              "puis lance-les. Double-clique un resultat pour "
                              "ouvrir le fichier concerne et naviguer directement "
                              "jusqu'a l'endroit exact.",
                        "en": "Checks that whatever a file mentions (an item, a "
                              "block, a token...) genuinely exists elsewhere in "
                              "the scenario. Check the desired verifications, "
                              "then run them. Double-click a result to open the "
                              "relevant file and jump straight to the exact "
                              "spot."},
    "crossref.checks_label": {"fr": "Verifications a effectuer :",
                               "en": "Checks to perform:"},
    "crossref.btn_run": {"fr": "Lancer la verification", "en": "Run check"},
    "crossref.results_label": {"fr": "Resultats :", "en": "Results:"},
    "crossref.no_check_selected": {"fr": "Coche au moins une verification avant "
                                          "de lancer.",
                                    "en": "Check at least one verification before "
                                          "running."},
    "crossref.all_ok": {"fr": "Tout est coherent -- aucune reference cassee "
                               "trouvee parmi les verifications selectionnees.",
                         "en": "Everything is consistent -- no broken reference "
                               "found among the selected checks."},
    "crossref.issues_found": {"fr": "{n} probleme(s) trouve(s).",
                               "en": "{n} issue(s) found."},
    "crossref.more_issues": {"fr": " (affichage limite aux 500 premiers ; "
                                    "{n} de plus non affiches)",
                              "en": " (display limited to the first 500; {n} "
                                    "more not shown)"},

    # --- Menu Options ---
    "menu.options": {"fr": "&Options", "en": "&Options"},
    "menu.options.author": {"fr": "Nom pour les annotations...", "en": "Name for annotations..."},
    "menu.options.annotations": {"fr": "Annoter les modifications automatiquement",
                                  "en": "Automatically annotate changes"},
    "menu.options.language": {"fr": "Langue : Francais (clic pour English)",
                               "en": "Language: English (click for Francais)"},

    # --- Menu Aide ---
    "menu.help": {"fr": "&Aide", "en": "&Help"},
    "menu.help.wiki_app": {"fr": "Wiki de l'application (fonctions)...",
                            "en": "Application wiki (features)..."},
    "menu.help.wiki_empyrion": {"fr": "Wiki Empyrion (proprietes, fichiers, structure)...",
                                 "en": "Empyrion wiki (properties, files, structure)..."},
    "menu.help.privacy": {"fr": "Politique de confidentialite...", "en": "Privacy policy..."},
    "privacy.not_found": {"fr": "PRIVACY.md introuvable a cote de l'application.",
                           "en": "PRIVACY.md not found next to the application."},

    # --- Boutons communs (editeurs) ---
    "btn.save": {"fr": "Enregistrer (Ctrl+S)", "en": "Save (Ctrl+S)"},
    "btn.undo": {"fr": "Annuler (Ctrl+Z)", "en": "Undo (Ctrl+Z)"},
    "btn.add_block": {"fr": "Bloc", "en": "Block"},
    "btn.add_property": {"fr": "Propriete", "en": "Property"},
    "btn.add_row": {"fr": "Ligne", "en": "Row"},
    "btn.delete_selected_row": {"fr": "Ligne selectionnee", "en": "Selected row"},
    "btn.add_entry": {"fr": "Entree", "en": "Entry"},
    "btn.delete_selected_entry": {"fr": "Supprimer l'entree selectionnee", "en": "Delete selected entry"},
    "btn.filter_by_property": {"fr": "Filtrer par propriete...", "en": "Filter by property..."},
    "btn.transform": {"fr": "Transformation en masse...", "en": "Bulk transform..."},
    "playfield.tab_resources": {"fr": "Ressources", "en": "Resources"},
    "playfield.tab_poi": {"fr": "POI", "en": "POI"},
    "playfield.tab_creatures": {"fr": "Creatures", "en": "Creatures"},
    "playfield.tab_drones": {"fr": "Drones/Vaisseaux", "en": "Drones/Vessels"},
    "playfield.drone_stock_label": {"fr": "Garnison de la base de drones -- "
                                          "planete (DroneBaseSetup > Stock)",
                                     "en": "Drone base garrison -- planet "
                                           "(DroneBaseSetup > Stock)"},
    "playfield.free_drones_label": {"fr": "Drones de patrouille libres -- "
                                         "espace (FreeDrones)",
                                     "en": "Free patrol drones -- space "
                                           "(FreeDrones)"},
    "playfield.space_vessels_label": {"fr": "Vaisseaux spatiaux -- espace "
                                            "(SpaceVessels)",
                                       "en": "Space vessels -- space "
                                             "(SpaceVessels)"},
    "playfield.tab_spawn_zones": {"fr": "Zones de spawn", "en": "Spawn zones"},
    "playfield.tab_special_effects": {"fr": "Effets speciaux", "en": "Special effects"},
    "playfield.col_dronesminmax": {"fr": "DronesMinMax", "en": "DronesMinMax"},
    "playfield.col_spawnat": {"fr": "SpawnAt", "en": "SpawnAt"},
    "playfield.drone_spawning_label": {"fr": "Patrouilles de drones -- planete "
                                            "(DroneSpawning > Random)",
                                        "en": "Drone patrols -- planet "
                                              "(DroneSpawning > Random)"},
    "playfield.spawn_rate_zones_label": {"fr": "Modulation du taux d'apparition "
                                              "autour des POI (SpawnRateZones)",
                                          "en": "Spawn rate modulation around "
                                                "POI (SpawnRateZones)"},
    "playfield.spawn_zones_label": {"fr": "Creatures liees a un POI -- "
                                         "different de l'onglet Creatures, qui "
                                         "est par biome (SpawnZones)",
                                     "en": "Creatures tied to a POI -- "
                                           "different from the Creatures tab, "
                                           "which is per-biome (SpawnZones)"},
    "playfield.special_effects_local_label": {"fr": "Effets visuels locaux par "
                                                    "biome -- pollen, papillons... "
                                                    "(SpecialEffectsLocal)",
                                                "en": "Local visual effects per "
                                                      "biome -- pollen, "
                                                      "butterflies... "
                                                      "(SpecialEffectsLocal)"},
    "playfield.special_effects_global_label": {"fr": "Effets globaux -- meteo, "
                                                     "effets a plus grande "
                                                     "echelle (SpecialEffectsGlobal)",
                                                 "en": "Global effects -- "
                                                       "weather, larger-scale "
                                                       "effects "
                                                       "(SpecialEffectsGlobal)"},
    "playfield.tab_raw_yaml": {"fr": "YAML complet", "en": "Full YAML"},
    "playfield.btn_save": {"fr": "Enregistrer (Ctrl+S)", "en": "Save (Ctrl+S)"},
    "playfield.unsaved_changes": {"fr": "Modifications non enregistrees",
                                   "en": "Unsaved changes"},
    "playfield.random_resources_label": {"fr": "Ressources aleatoires (RandomResources)",
                                          "en": "Random resources (RandomResources)"},
    "playfield.asteroid_resources_label": {"fr": "Ressources d'asteroides (AsteroidResources)",
                                            "en": "Asteroid resources (AsteroidResources)"},
    "playfield.space_resources_label": {"fr": "Ressources spatiales -- asteroides (Resources, "
                                              "playfields espace uniquement)",
                                         "en": "Space resources -- asteroids (Resources, "
                                               "space playfields only)"},
    "playfield.col_name": {"fr": "Nom", "en": "Name"},
    "playfield.col_groupname": {"fr": "GroupName", "en": "GroupName"},
    "playfield.col_regen_after": {"fr": "RegenAfter (delai avant reapparition)",
                                   "en": "RegenAfter (respawn delay)"},
    "playfield.col_biome": {"fr": "Biome", "en": "Biome"},
    "playfield.count_label": {"fr": "{n} entree(s)", "en": "{n} entrie(s)"},
    "playfield.btn_add": {"fr": "+ Ajouter...", "en": "+ Add..."},
    "playfield.btn_remove": {"fr": "Supprimer la ligne selectionnee", "en": "Remove selected row"},
    "playfield.no_row_selected": {"fr": "Selectionne d'abord une ligne dans le tableau.",
                                   "en": "Select a row in the table first."},
    "playfield.confirm_remove": {"fr": "Supprimer definitivement '{name}' ?",
                                  "en": "Permanently remove '{name}'?"},
    "playfield.add_resource_title": {"fr": "Ajouter une ressource", "en": "Add a resource"},
    "playfield.resource_name_label": {"fr": "Ressource (bloc) :", "en": "Resource (block):"},
    "playfield.no_resources_found": {"fr": "Aucun bloc de type ressource (finissant par "
                                            "'Resource') trouve dans BlocksConfig.ecf.",
                                      "en": "No resource-type block (ending in "
                                            "'Resource') found in BlocksConfig.ecf."},
    "playfield.section_not_found": {"fr": "Section '{section}' introuvable dans ce fichier.",
                                     "en": "Section '{section}' not found in this file."},
    "playfield.complex_value_placeholder": {"fr": "[valeur structuree, voir YAML complet]",
                                             "en": "[structured value, see Full YAML]"},
    "playfield.existing_only_note": {"fr": "Modification des entrees deja presentes uniquement "
                                            "(delais, difficulte, distances, quantites...). "
                                            "L'ajout d'un nouveau POI/creature par selection de "
                                            "type n'est pas propose ici -- utilise l'onglet "
                                            "\"YAML complet\" ou EPD pour cela (voir le wiki "
                                            "Empyrion, section 5).",
                                      "en": "Editing of existing entries only (delays, "
                                            "difficulty, distances, quantities...). Adding a new "
                                            "POI/creature by picking a type isn't offered here -- "
                                            "use the \"Full YAML\" tab or EPD for that (see the "
                                            "Empyrion wiki, section 5)."},
    "transform.title": {"fr": "Transformation en masse", "en": "Bulk transform"},
    "transform.key_label": {"fr": "Cle de propriete :", "en": "Property key:"},
    "transform.key_placeholder": {"fr": "ex: param1, Count, Health",
                                   "en": "e.g. param1, Count, Health"},
    "transform.available_keys_label": {"fr": "Proprietes disponibles dans ce fichier "
                                              "(clic pour choisir) :",
                                        "en": "Properties available in this file "
                                              "(click to choose):"},
    "transform.op_label": {"fr": "Operation :", "en": "Operation:"},
    "transform.op_multiply": {"fr": "Multiplier", "en": "Multiply"},
    "transform.op_add": {"fr": "Ajouter", "en": "Add"},
    "transform.op_set": {"fr": "Fixer a une valeur", "en": "Set to value"},
    "transform.op_clamp": {"fr": "Plafonner (min/max)", "en": "Clamp (min/max)"},
    "transform.op_round": {"fr": "Arrondir", "en": "Round"},
    "transform.amount_label": {"fr": "Valeur :", "en": "Amount:"},
    "transform.enable_min": {"fr": "Min", "en": "Min"},
    "transform.min_label": {"fr": "Borne minimale :", "en": "Minimum bound:"},
    "transform.enable_max": {"fr": "Max", "en": "Max"},
    "transform.max_label": {"fr": "Borne maximale :", "en": "Maximum bound:"},
    "transform.ndigits_label": {"fr": "Decimales :", "en": "Decimal places:"},
    "transform.kind_label": {"fr": "Genre de bloc :", "en": "Block kind:"},
    "transform.all_kinds": {"fr": "(tous les genres)", "en": "(all kinds)"},
    "transform.ids_label": {"fr": "Identites cibles (optionnel) :",
                             "en": "Target identities (optional):"},
    "transform.ids_placeholder": {"fr": "ex: 5,6,7 (vide = tous)",
                                   "en": "e.g. 5,6,7 (empty = all)"},
    "transform.recursive_label": {"fr": "Chercher aussi dans les sous-blocs (ex: Child Items)",
                                   "en": "Also search sub-blocks (e.g. Child Items)"},
    "transform.report_label": {"fr": "Resultats (revue ligne par ligne avant application) :",
                                "en": "Results (row-by-row review before applying):"},
    "transform.col_block": {"fr": "Bloc", "en": "Block"},
    "transform.col_key": {"fr": "Cle", "en": "Key"},
    "transform.col_old": {"fr": "Avant", "en": "Before"},
    "transform.col_new": {"fr": "Apres (modifiable)", "en": "After (editable)"},
    "transform.btn_preview": {"fr": "Apercu", "en": "Preview"},
    "transform.btn_apply": {"fr": "Appliquer", "en": "Apply"},
    "transform.btn_apply_count": {"fr": "Appliquer ({count} coches)",
                                   "en": "Apply ({count} checked)"},
    "transform.error_no_key": {"fr": "La cle de propriete est obligatoire.",
                                "en": "The property key is required."},
    "transform.error_no_clamp_bound": {"fr": "Coche au moins Min ou Max pour "
                                              "l'operation Plafonner.",
                                        "en": "Check at least Min or Max for the "
                                              "Clamp operation."},
    "transform.no_changes": {"fr": "Aucune valeur ne correspond a ces reglages -- "
                                    "rien a modifier.",
                              "en": "No value matches these settings -- nothing "
                                    "to change."},
    "transform.skipped_non_numeric": {"fr": "{count} valeur(s) trouvee(s) mais non "
                                             "numerique(s) -> ignoree(s), non "
                                             "affichee(s) dans le tableau.",
                                       "en": "{count} value(s) found but not "
                                             "numeric -> skipped, not shown in "
                                             "the table."},
    "transform.applied_msg": {"fr": "{count} valeur(s) modifiee(s) et appliquee(s) "
                                     "au document. N'oublie pas d'enregistrer.",
                               "en": "{count} value(s) changed and applied to the "
                                     "document. Don't forget to save."},

    "btn.apply_value": {"fr": "Appliquer cette valeur", "en": "Apply this value"},
    "btn.cancel": {"fr": "Annuler", "en": "Cancel"},
    "btn.close": {"fr": "Fermer", "en": "Close"},

    # --- Menu contextuel copier/coller ---
    "ctx.copy": {"fr": "Copier", "en": "Copy"},
    "ctx.cut": {"fr": "Couper", "en": "Cut"},
    "ctx.paste": {"fr": "Coller", "en": "Paste"},
    "ctx.clear_content": {"fr": "Supprimer le contenu (vide la/les cellule(s))",
                           "en": "Clear content (empties the cell(s))"},
    "ctx.delete_rows": {"fr": "Supprimer la/les ligne(s) entiere(s)", "en": "Delete entire row(s)"},
    "ctx.translate_to": {"fr": "Traduire vers...", "en": "Translate to..."},
    "ctx.translate_selection_to": {"fr": "Traduire la selection vers...", "en": "Translate selection to..."},
    "ctx.bbcode": {"fr": "Mise en forme BBCode (couleur/gras/italique)...",
                   "en": "BBCode formatting (color/bold/italic)..."},

    # --- Dialogue Nouveau projet ---
    "newproj.title": {"fr": "Nouveau projet", "en": "New project"},
    "newproj.scenario_a": {"fr": "Scenario A (base) :", "en": "Scenario A (base):"},
    "newproj.scenario_a_placeholder": {"fr": "Dossier racine du scenario de base...",
                                        "en": "Root folder of the base scenario..."},
    "newproj.browse": {"fr": "Parcourir...", "en": "Browse..."},
    "newproj.merge_mode": {"fr": "Mode fusion (ajouter un second scenario source B)",
                            "en": "Merge mode (add a second source Scenario B)"},
    "newproj.scenario_b": {"fr": "Scenario B (source, optionnel) :", "en": "Scenario B (source, optional):"},
    "newproj.scenario_b_placeholder": {"fr": "Dossier racine du scenario B...",
                                        "en": "Root folder of Scenario B..."},
    "newproj.working_copy": {"fr": "Copie de travail (modifiable) :", "en": "Working copy (editable):"},
    "newproj.working_copy_placeholder": {"fr": "Nouvel emplacement pour la copie de travail...",
                                          "en": "New location for the working copy..."},
    "newproj.info": {"fr": "La copie de travail sera une copie physique complete du scenario A, creee\n"
                            "au nouvel emplacement choisi. Les scenarios A et B restent en lecture seule\n"
                            "et ne seront jamais modifies.",
                      "en": "The working copy will be a complete physical copy of Scenario A, created\n"
                            "at the new location you choose. Scenarios A and B stay read-only\n"
                            "and are never modified."},
    "newproj.choose_scenario_folder": {"fr": "Choisir un dossier de scenario", "en": "Choose a scenario folder"},
    "newproj.choose_parent_folder": {"fr": "Choisir le dossier PARENT de la copie de travail",
                                      "en": "Choose the PARENT folder of the working copy"},
    "err.missing_field": {"fr": "Champ manquant", "en": "Missing field"},
    "err.invalid_path": {"fr": "Chemin invalide", "en": "Invalid path"},
    "err.dest_exists": {"fr": "Destination existante", "en": "Destination already exists"},

    # --- Dialogue Projets recents ---
    "startup.title": {"fr": "Projets recents", "en": "Recent projects"},
    "startup.subtitle": {"fr": "Reprendre un projet existant, ou en creer un nouveau :",
                          "en": "Resume an existing project, or create a new one:"},
    "startup.open_selected": {"fr": "Ouvrir le projet selectionne", "en": "Open selected project"},
    "startup.remove": {"fr": "Retirer de la liste", "en": "Remove from list"},
    "startup.new_project": {"fr": "Nouveau projet...", "en": "New project..."},

    # --- Dialogue Dupliquer un bloc ---
    "dup.title": {"fr": "Dupliquer ce bloc", "en": "Duplicate this block"},
    "dup.current_block": {"fr": "Bloc actuel : Id={id}, Name={name}", "en": "Current block: Id={id}, Name={name}"},
    "dup.none_placeholder": {"fr": "(aucun)", "en": "(none)"},
    "dup.instructions": {"fr": "Renseigne un nouvel Id, un nouveau Name, ou les deux -- au moins une "
                                "valeur doit differer de l'original.",
                          "en": "Enter a new Id, a new Name, or both -- at least one "
                                "value must differ from the original."},

    # --- Barre de statut ---
    "status.no_project": {"fr": "Aucun projet ouvert -- Fichier > Nouveau projet...",
                           "en": "No project open -- File > New project..."},
    "status.nothing_to_save": {"fr": "Rien a enregistrer sur cet onglet.", "en": "Nothing to save on this tab."},
    "status.block_activated": {"fr": "Bloc active avec Id={id} dans {file}", "en": "Block activated with Id={id} in {file}"},
    "status.project_opened": {"fr": "Projet ouvert ({mode}) -- copie de travail : {path}",
                               "en": "Project opened ({mode}) -- working copy: {path}"},
    "status.project_resumed": {"fr": "Projet repris ({mode}) -- copie de travail : {path}",
                                "en": "Project resumed ({mode}) -- working copy: {path}"},
    "status.folder_merged": {"fr": "Dossier fusionne : {n} fichier(s) traites, {ecf} fichier(s) .ecf "
                                    "avec des changements, {csv} fichier(s) .csv completes "
                                    "({rows} ligne(s)), {conflicts} conflit(s) d'Id au total",
                              "en": "Folder merged: {n} file(s) processed, {ecf} .ecf file(s) "
                                    "with changes, {csv} .csv file(s) completed "
                                    "({rows} row(s)), {conflicts} Id conflict(s) in total"},
    "status.csv_merged_rows": {"fr": "Fusionne (CSV) dans la copie de travail : {file} -- "
                                      "{n} ligne(s) ajoutee(s)/completee(s) "
                                      "(les lignes deja presentes n'ont pas ete ecrasees)",
                                "en": "Merged (CSV) into working copy: {file} -- "
                                      "{n} row(s) added/completed "
                                      "(existing rows were not overwritten)"},
    "status.csv_merged_none": {"fr": "Fusionne (CSV) : {file} -- aucun changement (deja a jour)",
                                "en": "Merged (CSV): {file} -- no change (already up to date)"},
    "status.merged_working": {"fr": "Fusionne dans la copie de travail : {file} -- "
                                     "{new} bloc(s) nouveau(x), {changed} bloc(s) complete(s)",
                               "en": "Merged into working copy: {file} -- "
                                     "{new} new block(s), {changed} completed block(s)"},
    "status.id_conflicts_suffix": {"fr": ", {n} conflit(s) d'Id a revoir", "en": ", {n} Id conflict(s) to review"},
    "status.copied_to_working": {"fr": "Copie vers la copie de travail : {dest}", "en": "Copied to working copy: {dest}"},
    "status.block_duplicated": {"fr": "Bloc duplique ({details}) dans {file}", "en": "Block duplicated ({details}) in {file}"},
    "status.id_conflict_detected": {"fr": "Conflit d'Id detecte sur {file} -- bloc ajoute desactive",
                                     "en": "Id conflict detected on {file} -- block added disabled"},
    "status.block_added": {"fr": "Bloc ajoute dans {file}", "en": "Block added in {file}"},
    "status.block_merged": {"fr": "Bloc fusionne (complete) dans {file}", "en": "Block merged (completed) in {file}"},
    "status.row_added": {"fr": "Ligne '{key}' ajoutee dans {file}", "en": "Row '{key}' added in {file}"},
    "status.row_merged": {"fr": "Ligne '{key}' completee (cellules vides) dans {file}",
                           "en": "Row '{key}' completed (empty cells) in {file}"},
    "status.row_unchanged": {"fr": "Ligne '{key}' deja a jour dans {file} -- rien a changer",
                              "en": "Row '{key}' already up to date in {file} -- nothing to change"},
    "status.row_duplicated": {"fr": "Ligne dupliquee avec la cle '{key}' dans {file}",
                               "en": "Row duplicated with key '{key}' in {file}"},
    "status.entry_copied_root": {"fr": "Entree copiee dans {file} -- emplacement d'origine introuvable, "
                                        "ajoutee a la racine du fichier (a repositionner si besoin)",
                                  "en": "Entry copied in {file} -- original location not found, "
                                        "added at the file's root (reposition if needed)"},
    "status.entry_copied": {"fr": "Entree copiee dans {file} (meme emplacement)",
                             "en": "Entry copied in {file} (same location)"},
    "status.entry_duplicated": {"fr": "Entree dupliquee avec '{value}' dans {file}{note}",
                                 "en": "Entry duplicated with '{value}' in {file}{note}"},
    "status.row_translated": {"fr": "Ligne '{key}' ajoutee avec la traduction ({lang}) dans {file}",
                               "en": "Row '{key}' added with translation ({lang}) in {file}"},
    "status.cell_translated": {"fr": "Traduction ({lang}) ajoutee pour '{key}' dans {file}",
                                "en": "Translation ({lang}) added for '{key}' in {file}"},
    "status.cell_already_has_value": {"fr": "'{key}' avait deja une valeur dans la colonne {lang} -- "
                                             "rien change (copie de travail prioritaire)",
                                       "en": "'{key}' already had a value in the {lang} column -- "
                                             "nothing changed (working copy takes priority)"},
    "status.saved": {"fr": "Enregistre : {path}", "en": "Saved: {path}"},
    "status.mode_merge": {"fr": "FUSION", "en": "MERGE"},
    "status.mode_simple": {"fr": "edition simple", "en": "simple editing"},

    # --- Panneau de comparaison (blocs en attente) ---
    "pending.no_base_block": {"fr": "(bloc de base introuvable -- affichage du bloc en attente seul)",
                               "en": "(base block not found -- showing pending block only)"},
    "pending.read_error": {"fr": "(erreur de lecture du bloc)", "en": "(error reading the block)"},
    "pending.differences_header": {"fr": "Differences (- = valeur actuelle, + = valeur du bloc en attente) :",
                                    "en": "Differences (- = current value, + = pending block value):"},
    "pending.no_diff": {"fr": "Aucune difference de propriete detectee entre les deux (le conflit "
                               "vient uniquement du Name/CustomIcon/TemplateRoot different).",
                         "en": "No property difference detected between the two (the conflict "
                               "only comes from a different Name/CustomIcon/TemplateRoot)."},
    "pending.active_block_header": {"fr": "--- Bloc actuellement actif (Id existant) ---",
                                     "en": "--- Currently active block (existing Id) ---"},
    "pending.pending_block_header": {"fr": "--- Bloc en attente (ce que tu vas activer) ---",
                                      "en": "--- Pending block (what you're about to activate) ---"},
    "pending.suggestions_label": {"fr": "Id libres suggeres (au-dessus du maximum utilise dans le scenario) : {ids}",
                                   "en": "Free Id suggestions (above the highest used in the scenario): {ids}"},
    "status.entry_duplicated_note": {"fr": " (emplacement d'origine introuvable, ajoutee a la racine)",
                                      "en": " (original location not found, added at the root)"},
    "check.refs_broken_title": {"fr": "References cassees detectees", "en": "Broken references detected"},
    "check.refs_broken_msg": {"fr": "{n} reference(s) 'Ref' ne correspondent a aucun 'Name' existant "
                                     "dans la copie de travail (l'heritage attendu ne fonctionnera pas en jeu) :\n\n"
                                     "{details}{more}",
                               "en": "{n} 'Ref' reference(s) don't match any existing 'Name' "
                                     "in the working copy (the expected inheritance won't work in-game):\n\n"
                                     "{details}{more}"},
    "check.refs_more": {"fr": "\n... et {n} autre(s)", "en": "\n... and {n} more"},
    "dup.name_required_msg": {"fr": "Si tu abandonnes l'Id, il faut un nouveau Name pour identifier "
                                     "ce bloc (sinon impossible de le distinguer de l'original).",
                               "en": "If you drop the Id, a new Name is required to identify "
                                     "this block (otherwise it can't be distinguished from the original)."},
    "dup.no_change_msg": {"fr": "Indique un nouvel Id et/ou un nouveau Name, different de l'original.",
                           "en": "Enter a new Id and/or a new Name, different from the original."},
    "ecf.single_block_conflict_title": {"fr": "Conflit d'Id", "en": "Id conflict"},
    "ecf.single_block_conflict_msg": {"fr": "Ce bloc partage un Id deja utilise par un element DIFFERENT dans la "
                                             "copie de travail. Il n'a PAS ete fusionne -- ajoute en fin de fichier, "
                                             "desactive (commente), a traiter manuellement.",
                                       "en": "This block shares an Id already used by a DIFFERENT element in the "
                                             "working copy. It was NOT merged -- added at the end of the file, "
                                             "disabled (commented out), to be handled manually."},
    "ecf.header_property_tooltip": {"fr": "Propriete d'en-tete du bloc (ex: Id, Name)",
                                     "en": "Block header property (e.g. Id, Name)"},
    "bbcode.select_text_hint": {"fr": "Selectionne d'abord une portion de texte dans la zone ci-dessus.",
                                 "en": "Select a portion of text in the area above first."},
    "dup.new_id": {"fr": "Nouvel Id :", "en": "New Id:"},
    "dup.new_name": {"fr": "Nouveau Name :", "en": "New Name:"},
    "dup.remove_id": {"fr": "Abandonner l'Id sur le nouveau bloc (l'identifier seulement par Name -- "
                             "necessite un nouveau Name ci-dessus)",
                       "en": "Drop the Id on the new block (identify it by Name only -- "
                             "requires a new Name above)"},
    "dup.duplicate": {"fr": "Dupliquer", "en": "Duplicate"},
    "dup.name_required": {"fr": "Name requis", "en": "Name required"},
    "dup.no_change": {"fr": "Aucun changement", "en": "No change"},

    # --- Dialogue Blocs en attente ---
    "pending.title": {"fr": "Blocs en attente (conflits d'Id)", "en": "Pending blocks (Id conflicts)"},
    "pending.compare_label": {"fr": "Comparaison (bloc actuel dans la copie de travail vs bloc en attente) :",
                               "en": "Comparison (current block in working copy vs pending block):"},
    "pending.new_id_label": {"fr": "Nouvel Id a assigner :", "en": "New Id to assign:"},
    "pending.activate": {"fr": "Activer avec cet Id", "en": "Activate with this Id"},
    "pending.id_missing": {"fr": "Id manquant", "en": "Missing Id"},
    "pending.id_missing_msg": {"fr": "Indique un Id.", "en": "Enter an Id."},
    "pending.id_already_used": {"fr": "Id deja utilise", "en": "Id already in use"},
    "pending.id_already_used_confirm": {"fr": "L'Id {id} semble deja utilise ailleurs dans le scenario. Continuer quand meme ?",
                                         "en": "Id {id} seems to already be used elsewhere in the scenario. Continue anyway?"},

    # --- Dialogue Filtrer par propriete ---
    "propfilter.title": {"fr": "Filtrer par propriete", "en": "Filter by property"},
    "propfilter.instructions": {"fr": "Coche une ou plusieurs proprietes : seuls les blocs\n"
                                       "possedant TOUTES les proprietes cochees restent visibles\n"
                                       "dans l'arbre du fichier ouvert.",
                                 "en": "Check one or more properties: only blocks that\n"
                                       "have ALL checked properties stay visible\n"
                                       "in the open file's tree."},
    "propfilter.clear_all": {"fr": "Tout decocher (afficher tous les blocs)",
                              "en": "Uncheck all (show all blocks)"},

    # --- Titres generiques de messages ---
    "err.title": {"fr": "Erreur", "en": "Error"},
    "err.read_title": {"fr": "Erreur de lecture", "en": "Read error"},
    "err.no_project_title": {"fr": "Aucun projet", "en": "No project"},
    "err.no_project_msg": {"fr": "Ouvre d'abord un projet.", "en": "Open a project first."},
    "err.no_file_title": {"fr": "Aucun fichier", "en": "No file"},

    # --- Blocs en attente ---
    "pending.none_title": {"fr": "Blocs en attente", "en": "Pending blocks"},
    "pending.none_msg": {"fr": "Aucun bloc en attente (conflit d'Id) trouve dans la copie de travail.",
                          "en": "No pending block (Id conflict) found in the working copy."},
    "pending.not_found_msg": {"fr": "Le bloc en attente n'a plus ete retrouve (fichier modifie entre-temps ?).",
                               "en": "The pending block could no longer be found (was the file modified meanwhile?)."},
    "pending.cannot_activate_msg": {"fr": "Impossible d'activer ce bloc (motif 'Id:' introuvable dans son texte).",
                                     "en": "Could not activate this block ('Id:' pattern not found in its text)."},
    "pending.activation_error": {"fr": "Erreur pendant l'activation", "en": "Error during activation"},
    "pending.activated_title": {"fr": "Bloc active", "en": "Block activated"},
    "pending.activated_msg": {"fr": "Le bloc est maintenant actif avec Id={id} dans {file}.\n"
                                     "Pense a relancer la verification des references si ce bloc en concernait.",
                               "en": "The block is now active with Id={id} in {file}.\n"
                                     "Remember to re-run the reference check if this block was involved."},

    # --- Verification des references ---
    "check.no_ecf_found": {"fr": "Aucun fichier .ecf trouve dans Configuration.",
                            "en": "No .ecf file found in Configuration."},
    "check.verification_error": {"fr": "Erreur pendant la verification", "en": "Error during check"},
    "check.refs_title": {"fr": "Verification des references", "en": "Reference check"},
    "check.refs_ok": {"fr": "Aucune reference cassee trouvee sur {n} fichier(s) verifie(s).",
                       "en": "No broken reference found across {n} checked file(s)."},

    # --- Projets ---
    "err.create_project": {"fr": "Impossible de creer le projet", "en": "Could not create the project"},
    "recent.none_title": {"fr": "Aucun projet recent", "en": "No recent project"},
    "recent.none_msg": {"fr": "Aucun projet recent enregistre -- utilise 'Nouveau projet...'",
                         "en": "No recent project saved -- use 'New project...'"},
    "recent.resume_error": {"fr": "Impossible de reprendre ce projet", "en": "Could not resume this project"},
    "recent.resume_error_hint": {"fr": "Il a peut-etre ete deplace ou supprime.",
                                  "en": "It may have been moved or deleted."},

    # --- Fusion ---
    "merge.empty_folder_title": {"fr": "Dossier vide", "en": "Empty folder"},
    "merge.empty_folder_msg": {"fr": "Aucun fichier a fusionner dans ce dossier.",
                                "en": "No file to merge in this folder."},
    "merge.folder_error": {"fr": "Impossible de fusionner le dossier", "en": "Could not merge the folder"},
    "merge.file_error": {"fr": "Impossible de copier/fusionner {file}", "en": "Could not copy/merge {file}"},
    "merge.confirm_title": {"fr": "Confirmer", "en": "Confirm"},
    "merge.confirm_folder_msg": {"fr": "Fusionner {n} fichier(s) de '{folder}' (et sous-dossiers) vers la copie de travail ?",
                                  "en": "Merge {n} file(s) from '{folder}' (and subfolders) into the working copy?"},
    "merge.id_conflicts_title": {"fr": "Conflits d'Id detectes", "en": "Id conflicts detected"},
    "merge.id_conflicts_folder_msg": {"fr": "{n} bloc(s) au total n'ont pas ete fusionnes (Id partage "
                                             "avec un materiel different) -- ajoutes desactives dans leurs "
                                             "fichiers respectifs pour revue manuelle :\n\n{details}{more}",
                                       "en": "{n} block(s) in total were not merged (Id shared "
                                             "with different content) -- added disabled in their "
                                             "respective files for manual review:\n\n{details}{more}"},
    "merge.id_conflicts_file_msg": {"fr": "{n} bloc(s) partagent un Id deja utilise par un element "
                                           "DIFFERENT dans la copie de travail. Ils n'ont PAS ete fusionnes -- "
                                           "ajoutes en fin de fichier, desactives (commentes), a traiter "
                                           "manuellement (reassigner un Id libre) :\n\n{details}",
                                     "en": "{n} block(s) share an Id already used by a DIFFERENT "
                                           "element in the working copy. They were NOT merged -- "
                                           "added at the end of the file, disabled (commented out), to be "
                                           "handled manually (reassign a free Id):\n\n{details}"},
    "merge.id_conflicts_more": {"fr": "\n... et {n} autre(s)", "en": "\n... and {n} more"},

    # --- YAML : suppression d'entree ---
    "yaml.no_selection_title": {"fr": "Aucune selection", "en": "No selection"},
    "yaml.no_selection_msg": {"fr": "Selectionne d'abord une entree dans l'arbre.",
                               "en": "Select an entry in the tree first."},
    "yaml.confirm_delete": {"fr": "Supprimer '{name}' ?", "en": "Delete '{name}'?"},

    # --- ECF : selection/suppression de bloc ---
    "ecf.no_block_title": {"fr": "Aucun bloc", "en": "No block"},
    "ecf.no_block_msg": {"fr": "Selectionne d'abord un bloc dans l'arbre.",
                          "en": "Select a block in the tree first."},
    "ecf.confirm_delete_block": {"fr": "Supprimer le bloc {name} ?", "en": "Delete block {name}?"},
    "ecf.delete_block_action": {"fr": "Supprimer ce bloc", "en": "Delete this block"},

    # --- ECF : ajout bloc/propriete (QInputDialog) ---
    "ecf.add_property_title": {"fr": "Ajouter une propriete", "en": "Add a property"},
    "ecf.property_name_label": {"fr": "Nom de la propriete :", "en": "Property name:"},
    "ecf.property_value_label": {"fr": "Valeur de '{key}' :\n(pour ajouter d'autres proprietes sur la meme ligne, "
                                        "ex: Name_X -> param1/param2, tape 'valeur, param1: X, param2: \"Y,Z\"' "
                                        "-- guillemets obligatoires si une valeur contient une virgule)",
                                  "en": "Value of '{key}':\n(to add more properties on the same line, "
                                        "e.g. Name_X -> param1/param2, type 'value, param1: X, param2: \"Y,Z\"' "
                                        "-- quotes required if a value contains a comma)"},
    "ecf.add_block_title": {"fr": "Ajouter un bloc", "en": "Add a block"},

    "addblock.identity_title": {"fr": "Nouveau bloc/item -- identification", "en": "New block/item -- identity"},
    "addblock.identity_intro": {"fr": "Comment ce bloc/item doit-il etre identifie ?",
                                 "en": "How should this block/item be identified?"},
    "addblock.identity_id_and_name": {"fr": "Id + Name (le plus courant)",
                                       "en": "Id + Name (most common)"},
    "addblock.identity_name_only": {"fr": "Name seul (sans Id -- ex: blocs terrain historiques)",
                                     "en": "Name only (no Id -- e.g. legacy terrain blocks)"},
    "addblock.btn_next": {"fr": "Suivant...", "en": "Next..."},
    "addblock.table_title": {"fr": "Nouveau bloc/item", "en": "New block/item"},
    "addblock.template_table_title": {"fr": "Nouveau Template (recette de craft)",
                                       "en": "New Template (crafting recipe)"},
    "addblock.kind_label": {"fr": "Genre :", "en": "Kind:"},
    "addblock.name_label": {"fr": "Name :", "en": "Name:"},
    "addblock.id_placeholder": {"fr": "Nombre < {max}", "en": "Number < {max}"},
    "addblock.properties_label": {"fr": "Proprietes -- coche celles a inclure, modifie "
                                        "la valeur si besoin (valeur la plus frequente "
                                        "du fichier proposee par defaut) :",
                                   "en": "Properties -- check the ones to include, edit "
                                         "the value if needed (the file's most common "
                                         "value is suggested by default):"},
    "addblock.filter_placeholder": {"fr": "Filtrer les proprietes...", "en": "Filter properties..."},
    "addblock.col_property": {"fr": "Propriete", "en": "Property"},
    "addblock.col_value": {"fr": "Valeur", "en": "Value"},
    "addblock.ingredients_label": {"fr": "Ingredients (Child Inputs) :", "en": "Ingredients (Child Inputs):"},
    "addblock.col_ingredient": {"fr": "Item/Bloc", "en": "Item/Block"},
    "addblock.col_quantity": {"fr": "Quantite", "en": "Quantity"},
    "addblock.btn_add_ingredient": {"fr": "+ Ingredient", "en": "+ Ingredient"},
    "addblock.btn_remove_ingredient": {"fr": "Supprimer la ligne", "en": "Remove row"},
    "addblock.btn_validate": {"fr": "Creer", "en": "Create"},
    "addblock.id_not_numeric": {"fr": "L'Id doit etre un nombre entier.", "en": "Id must be an integer."},
    "addblock.id_too_high": {"fr": "L'Id doit etre inferieur a {max} (limite du jeu).",
                              "en": "Id must be below {max} (game limit)."},
    "addblock.id_duplicate": {"fr": "Cet Id est deja utilise dans ce fichier.",
                               "en": "This Id is already used in this file."},
    "addblock.err_kind_required": {"fr": "Le genre est obligatoire.", "en": "Kind is required."},
    "addblock.err_id_required": {"fr": "L'Id est obligatoire pour ce mode.", "en": "Id is required for this mode."},
    "addblock.err_name_required": {"fr": "Le Name est obligatoire pour ce mode.",
                                    "en": "Name is required for this mode."},
    "addblock.ask_template_title": {"fr": "Creer le Template associe ?", "en": "Create the associated Template?"},
    "addblock.ask_template_msg": {"fr": "Creer aussi la recette de craft (Template) pour "
                                        "'{name}' ?",
                                   "en": "Also create the crafting recipe (Template) for "
                                         "'{name}'?"},
    "addblock.templates_not_found_title": {"fr": "Templates.ecf introuvable",
                                            "en": "Templates.ecf not found"},
    "addblock.templates_not_found_msg": {"fr": "Aucun fichier Templates.ecf trouve dans ce "
                                                "scenario -- le bloc/item a bien ete cree, "
                                                "mais pas de Template associe.",
                                          "en": "No Templates.ecf file found in this "
                                                "scenario -- the block/item was created, "
                                                "but no associated Template."},
    "addblock.created_status": {"fr": "Bloc/item '{name}' cree dans {file}.",
                                 "en": "Block/item '{name}' created in {file}."},
    "addblock.template_created_status": {"fr": "Template '{name}' cree dans Templates.ecf.",
                                          "en": "Template '{name}' created in Templates.ecf."},
    "ecf.block_kind_label": {"fr": "Genre du bloc (ex: Block) :", "en": "Block kind (e.g. Block):"},
    "ecf.id_label": {"fr": "Id :", "en": "Id:"},
    "ecf.name_optional_label": {"fr": "Name (optionnel) :", "en": "Name (optional):"},
    "ecf.delete_property_action": {"fr": "Supprimer cette propriete", "en": "Delete this property"},
    "ctx.translate_cell_to": {"fr": "Traduire cette cellule vers... (-> copie de travail)",
                               "en": "Translate this cell to... (-> working copy)"},

    # --- Options : nom d'auteur ---
    "author.title": {"fr": "Nom pour les annotations", "en": "Name for annotations"},
    "author.label": {"fr": "Ce nom apparaitra dans les commentaires '# original: ... -- Mod par ...' :",
                      "en": "This name will appear in the traceability comments '# original: ... -- Mod by ...':"},

    # --- YAML : ajout d'entree ---
    "yaml.add_entry_title": {"fr": "Ajouter une entree", "en": "Add an entry"},
    "yaml.key_label": {"fr": "Cle (laisser vide pour un item de sequence) :",
                        "en": "Key (leave empty for a sequence item):"},
    "yaml.value_label": {"fr": "Valeur :", "en": "Value:"},
    "yaml.duplicate_action": {"fr": "Dupliquer avec une nouvelle cle/valeur vers la copie de travail...",
                               "en": "Duplicate with a new key/value to working copy..."},

    # --- Menu contextuel bloc ECF (vue comparative / source) ---
    "ecf.merge_block_action": {"fr": "Copier / fusionner ce bloc ({label}) vers la copie de travail",
                                "en": "Copy / merge this block ({label}) to working copy"},
    "ecf.duplicate_subblock_action": {"fr": "Dupliquer ce sous-bloc (dans le meme parent) vers la copie de travail...",
                                       "en": "Duplicate this sub-block (in the same parent) to working copy..."},
    "ecf.duplicate_block_action": {"fr": "Dupliquer avec un nouvel Id vers la copie de travail...",
                                    "en": "Duplicate with a new Id to working copy..."},

    # --- Menus contextuels fichier/ligne/entree (f-strings ratees a la premiere passe) ---
    "csv.copy_row_action": {"fr": "Copier cette ligne (cle '{key}') vers la copie de travail",
                             "en": "Copy this row (key '{key}') to working copy"},
    "csv.duplicate_row_action": {"fr": "Dupliquer avec une nouvelle cle vers la copie de travail...",
                                  "en": "Duplicate with a new key to working copy..."},
    "file.merge_action": {"fr": "Copier / fusionner '{name}' vers la copie de travail",
                           "en": "Copy / merge '{name}' to working copy"},
    "folder.merge_action": {"fr": "Fusionner le dossier '{name}' (et sous-dossiers) vers la copie de travail",
                             "en": "Merge folder '{name}' (and subfolders) to working copy"},
    "file.duplicate_action": {"fr": "Dupliquer '{name}' avec un nouveau nom vers la copie de travail...",
                               "en": "Duplicate '{name}' with a new name to working copy..."},
    "dupfile.title": {"fr": "Dupliquer le fichier", "en": "Duplicate file"},
    "dupfile.new_name_label": {"fr": "Nouveau nom de fichier (dans le meme dossier que l'original) :",
                                "en": "New filename (in the same folder as the original):"},
    "dupfile.exists_title": {"fr": "Fichier deja existant", "en": "File already exists"},
    "dupfile.exists_msg": {"fr": "'{name}' existe deja dans la copie de travail -- choisis un autre nom.",
                            "en": "'{name}' already exists in the working copy -- choose another name."},
    "status.file_duplicated": {"fr": "Fichier duplique sous le nom '{name}' dans la copie de travail",
                                "en": "File duplicated as '{name}' in the working copy"},
    "file.delete_action": {"fr": "Supprimer '{name}'", "en": "Delete '{name}'"},
    "folder.delete_action": {"fr": "Supprimer le dossier '{name}' (et son contenu)",
                              "en": "Delete folder '{name}' (and its content)"},
    "delete.confirm_file_msg": {"fr": "Supprimer definitivement '{name}' de la copie de travail ? "
                                       "Cette action est irreversible (le fichier original de Scenario "
                                       "A/B n'est pas touche, tu peux le refusionner si besoin).",
                                 "en": "Permanently delete '{name}' from the working copy? "
                                       "This action cannot be undone (the original file in Scenario "
                                       "A/B is untouched, you can merge it again if needed)."},
    "delete.confirm_folder_msg": {"fr": "Supprimer definitivement le dossier '{name}' et TOUT son contenu "
                                         "de la copie de travail ? Cette action est irreversible.",
                                   "en": "Permanently delete the folder '{name}' and ALL its content "
                                         "from the working copy? This action cannot be undone."},
    "status.file_deleted": {"fr": "'{name}' supprime de la copie de travail", "en": "'{name}' deleted from the working copy"},
    "status.folder_deleted": {"fr": "Dossier '{name}' supprime de la copie de travail",
                               "en": "Folder '{name}' deleted from the working copy"},
    "delete.error": {"fr": "Impossible de supprimer", "en": "Could not delete"},

    # --- Annulation globale (niveau espace de travail) ---
    "wsundo.button": {"fr": "Annuler la derniere action", "en": "Undo last action"},
    "wsundo.tooltip_empty": {"fr": "Rien a annuler pour l'instant", "en": "Nothing to undo yet"},
    "wsundo.tooltip_action": {"fr": "Annuler : {label}", "en": "Undo: {label}"},
    "wsundo.status_done": {"fr": "Annule : {label}", "en": "Undone: {label}"},
    "wsundo.merge_file": {"fr": "Copie/fusion de '{name}'", "en": "Copy/merge of '{name}'"},
    "wsundo.merge_folder": {"fr": "Fusion du dossier '{name}'", "en": "Merge of folder '{name}'"},
    "wsundo.duplicate_file": {"fr": "Duplication de fichier '{name}'", "en": "File duplication '{name}'"},
    "wsundo.delete_file": {"fr": "Suppression de '{name}'", "en": "Deletion of '{name}'"},
    "wsundo.delete_folder": {"fr": "Suppression du dossier '{name}'", "en": "Deletion of folder '{name}'"},
    "wsundo.duplicate_block": {"fr": "Duplication de bloc dans '{name}'", "en": "Block duplication in '{name}'"},
    "wsundo.copy_block": {"fr": "Copie de bloc dans '{name}'", "en": "Block copy in '{name}'"},
    "wsundo.copy_row": {"fr": "Copie de ligne dans '{name}'", "en": "Row copy in '{name}'"},
    "wsundo.duplicate_row": {"fr": "Duplication de ligne dans '{name}'", "en": "Row duplication in '{name}'"},
    "wsundo.copy_entry": {"fr": "Copie d'entree dans '{name}'", "en": "Entry copy in '{name}'"},
    "wsundo.duplicate_entry": {"fr": "Duplication d'entree dans '{name}'", "en": "Entry duplication in '{name}'"},
    "wsundo.translate_cell": {"fr": "Traduction dans '{name}'", "en": "Translation in '{name}'"},
    "wsundo.activate_pending": {"fr": "Activation de bloc en attente dans '{name}'", "en": "Pending block activation in '{name}'"},

    # --- Recherche CSV ---
    "search.no_results": {"fr": "Aucun resultat", "en": "No results"},
    "search.column_all": {"fr": "Toutes les colonnes", "en": "All columns"},
    "search.in_column_action": {"fr": "Rechercher dans '{name}'...", "en": "Search in '{name}'..."},
    "csv.search_placeholder": {"fr": "Rechercher... puis Entree", "en": "Search... then Enter"},
    "csv.search_scope_label": {"fr": "dans :", "en": "in:"},

    # --- Comparaison de scenarios ---
    "menu.file.compare": {"fr": "Comparer deux scenarios...", "en": "Compare two scenarios..."},
    "compare.title": {"fr": "Comparer deux scenarios", "en": "Compare two scenarios"},
    "compare.scenario_a": {"fr": "Scenario A (ancien / reference) :", "en": "Scenario A (old / reference):"},
    "compare.scenario_b": {"fr": "Scenario B (nouveau / mis a jour) :", "en": "Scenario B (new / updated):"},
    "compare.run": {"fr": "Comparer", "en": "Compare"},
    "compare.choose_folder": {"fr": "Choisir un dossier de scenario", "en": "Choose a scenario folder"},
    "compare.both_required": {"fr": "Choisis les deux dossiers de scenario a comparer.",
                               "en": "Choose both scenario folders to compare."},
    "compare.progress": {"fr": "Comparaison en cours...", "en": "Comparing..."},
    "compare.summary": {"fr": "{added} ajoute(s)   {removed} supprime(s)   {modified} modifie(s)   {unchanged} identique(s)",
                         "en": "{added} added   {removed} removed   {modified} modified   {unchanged} unchanged"},
    "compare.show_unchanged": {"fr": "Afficher aussi les fichiers identiques", "en": "Also show unchanged files"},
    "compare.export": {"fr": "Exporter le rapport...", "en": "Export report..."},
    "compare.export_title": {"fr": "Enregistrer le rapport de comparaison", "en": "Save comparison report"},
    "compare.export_done_title": {"fr": "Rapport exporte", "en": "Report exported"},
    "compare.export_done_msg": {"fr": "Rapport enregistre dans {path}", "en": "Report saved to {path}"},
    "compare.select_file_hint": {"fr": "Selectionne un fichier modifie dans l'arbre pour voir le detail.",
                                  "en": "Select a modified file in the tree to see the detail."},
    "compare.no_detail": {"fr": "(pas de detail disponible pour ce type de fichier -- "
                                 "contenu binaire ou format non structure)",
                           "en": "(no detail available for this file type -- "
                                 "binary content or unstructured format)"},
    "compare.error_title": {"fr": "Erreur de comparaison", "en": "Comparison error"},

    # --- Fusion desactivable ---
    "menu.options.merge_enabled": {"fr": "Autoriser la fusion (experimental, desactive par defaut)",
                                    "en": "Allow merging (experimental, disabled by default)"},
    "menu.options.online_translation": {"fr": "Traduction en ligne (Google Translate) -- envoie le "
                                              "texte a traduire a Google, voir PRIVACY.md",
                                         "en": "Online translation (Google Translate) -- sends the "
                                               "text to be translated to Google, see PRIVACY.md"},
    "merge.disabled_title": {"fr": "Fusion desactivee", "en": "Merging disabled"},
    "merge.disabled_msg": {"fr": "La fusion est desactivee par defaut (trop de cas particuliers pour "
                                  "etre fiable a 100%, risque de casser le scenario). Utilise plutot "
                                  "'Dupliquer', qui cree toujours une entree nouvelle et independante, "
                                  "sans risque d'ecraser quoi que ce soit.\n\n"
                                  "Tu peux reactiver la fusion dans Options si tu en as vraiment besoin.",
                            "en": "Merging is disabled by default (too many edge cases to be 100% "
                                  "reliable, risk of breaking the scenario). Use 'Duplicate' instead, "
                                  "which always creates a new, independent entry with no risk of "
                                  "overwriting anything.\n\n"
                                  "You can re-enable merging in Options if you really need it."},

    # --- Ouverture/changement du Scenario B a tout moment ---
    "menu.file.open_scenario_b": {"fr": "Ouvrir un Scenario B...", "en": "Open a Scenario B..."},
    "menu.file.change_scenario_b": {"fr": "Changer le Scenario B...", "en": "Change Scenario B..."},
    "menu.file.remove_scenario_b": {"fr": "Retirer le Scenario B", "en": "Remove Scenario B"},
    "scenariob.choose_folder": {"fr": "Choisir le dossier du Scenario B", "en": "Choose the Scenario B folder"},
    "scenariob.confirm_change_title": {"fr": "Changer le Scenario B", "en": "Change Scenario B"},
    "scenariob.confirm_change_msg": {"fr": "Remplacer le Scenario B actuel ('{old}') par '{new}' ?",
                                      "en": "Replace the current Scenario B ('{old}') with '{new}'?"},
    "scenariob.confirm_remove_title": {"fr": "Retirer le Scenario B", "en": "Remove Scenario B"},
    "scenariob.confirm_remove_msg": {"fr": "Retirer le Scenario B ('{name}') de ce projet ? "
                                            "La copie de travail n'est pas affectee.",
                                      "en": "Remove Scenario B ('{name}') from this project? "
                                            "The working copy is not affected."},
    "status.scenario_b_set": {"fr": "Scenario B defini : {name}", "en": "Scenario B set: {name}"},
    "status.scenario_b_removed": {"fr": "Scenario B retire", "en": "Scenario B removed"},

    # --- Desactivation manuelle de bloc (test d'elimination de causes) ---
    "ecf.disable_block_action": {"fr": "Desactiver ce bloc (test)", "en": "Disable this block (test)"},
    "ecf.confirm_disable_block": {"fr": "Desactiver '{name}' ? Le bloc sera commente (garde dans le fichier, "
                                         "inactif en jeu) -- reactivable a tout moment via 'Blocs desactives (test)'.",
                                   "en": "Disable '{name}'? The block will be commented out (kept in the "
                                         "file, inactive in-game) -- can be re-enabled anytime via "
                                         "'Disabled blocks (test)'."},
    "status.block_disabled": {"fr": "'{name}' desactive (commente)", "en": "'{name}' disabled (commented out)"},
    "ecf.disabled_blocks_menu": {"fr": "Blocs desactives (test)...", "en": "Disabled blocks (test)..."},
    "ecf.disabled_blocks_title": {"fr": "Blocs desactives (test)", "en": "Disabled blocks (test)"},
    "ecf.disabled_blocks_intro": {"fr": "Blocs actuellement desactives (commentes) dans ce fichier -- "
                                         "utile pour tester l'elimination de causes probables d'un bug. "
                                         "Selectionne-en un puis clique 'Reactiver' pour le remettre.",
                                   "en": "Blocks currently disabled (commented out) in this file -- "
                                         "useful for testing to eliminate probable causes of a bug. "
                                         "Select one then click 'Re-enable' to restore it."},
    "ecf.disabled_blocks_none": {"fr": "Aucun bloc desactive dans ce fichier.", "en": "No disabled blocks in this file."},
    "ecf.reactivate_block": {"fr": "Reactiver", "en": "Re-enable"},
    "status.block_reenabled": {"fr": "'{name}' reactive", "en": "'{name}' re-enabled"},

    # --- Menu Fichier : nouvelles entrees sauvegarde ---
    "menu.file.backup_scenario": {"fr": "Sauvegarder un scenario (avant mise a jour)...",
                                   "en": "Back up a scenario (before update)..."},
    "menu.file.repair_permissions": {"fr": "Reparer les permissions de la copie de travail",
                                      "en": "Repair working copy permissions"},
    "repair.no_project_msg": {"fr": "Ouvre d'abord un projet.", "en": "Open a project first."},
    "repair.done_title": {"fr": "Permissions reparees", "en": "Permissions repaired"},
    "repair.done_msg": {"fr": "La copie de travail est de nouveau entierement modifiable "
                              "(et supprimable).",
                         "en": "The working copy is fully writable (and deletable) again."},

    # --- Extraction des proprietes du scenario ---
    "menu.file.extract_properties": {"fr": "Extraire les proprietes du scenario...",
                                      "en": "Extract scenario properties..."},
    "extract.title": {"fr": "Extraire les proprietes", "en": "Extract properties"},
    "extract.source_label": {"fr": "Extraire depuis :", "en": "Extract from:"},
    "extract.source_working": {"fr": "La copie de travail", "en": "The working copy"},
    "extract.source_a": {"fr": "Scenario A", "en": "Scenario A"},
    "extract.source_b": {"fr": "Scenario B", "en": "Scenario B"},
    "extract.intro": {"fr": "Parcourt tous les fichiers .ecf et liste chaque propriete "
                             "utilisee (regroupees, ex: Name_0/Name_1... -> Name_N), avec "
                             "le nombre d'occurrences, les fichiers concernes, des exemples "
                             "de valeurs, et une description quand elle est connue. Cree un "
                             "fichier CSV modifiable dans l'appli -- utile comme glossaire de "
                             "travail, a completer avec tes propres notes (colonne 'Valeur "
                             "cible').",
                       "en": "Scans all .ecf files and lists every property used (grouped, "
                             "e.g. Name_0/Name_1... -> Name_N), with occurrence count, "
                             "files involved, example values, and a description when known. "
                             "Creates a CSV file editable in the app -- useful as a working "
                             "glossary, to fill in with your own notes ('Target value' "
                             "column)."},
    "extract.scanning": {"fr": "Analyse des fichiers ECF en cours...", "en": "Scanning ECF files..."},
    "extract.no_ecf_found": {"fr": "Aucun fichier .ecf trouve dans cette source.",
                              "en": "No .ecf files found in this source."},
    "extract.save_dialog_title": {"fr": "Enregistrer le glossaire des proprietes",
                                   "en": "Save the properties glossary"},
    "extract.done_title": {"fr": "Extraction terminee", "en": "Extraction complete"},
    "extract.done_msg": {"fr": "{count} proprietes distinctes extraites vers :\n{path}",
                          "en": "{count} distinct properties extracted to:\n{path}"},
    "extract.open_now": {"fr": "Ouvrir maintenant dans l'appli ?", "en": "Open it in the app now?"},

    # --- Tutoriels ---
    "menu.help.tutorials": {"fr": "Tutoriels...", "en": "Tutorials..."},
    "tutorials.dialog_title": {"fr": "Tutoriels", "en": "Tutorials"},
    "tutorials.list_title": {"fr": "Choisir un tutoriel", "en": "Choose a tutorial"},
    "tutorials.step_counter": {"fr": "Etape {current}/{total}", "en": "Step {current}/{total}"},
    "tutorials.btn_previous": {"fr": "\u2190 Precedent", "en": "\u2190 Previous"},
    "tutorials.btn_next": {"fr": "Suivant \u2192", "en": "Next \u2192"},
    "tutorials.select_prompt": {"fr": "Choisis un tutoriel dans la liste a gauche pour commencer.",
                                 "en": "Choose a tutorial from the list on the left to begin."},
    "tutorials.auto_open_banner": {"fr": "Bienvenue ! Ce tutoriel s'ouvre automatiquement au premier "
                                          "lancement. Tu peux le retrouver a tout moment via le menu "
                                          "<b>Aide &gt; Tutoriels...</b>",
                                    "en": "Welcome! This tutorial opens automatically on first launch. "
                                          "You can find it again anytime via <b>Help &gt; Tutorials...</b>"},
    "tutorials.dont_show_again": {"fr": "Ne plus afficher automatiquement au demarrage",
                                   "en": "Don't show automatically on startup"},

    "menu.help.check_updates": {"fr": "Verifier les mises a jour...",
                                 "en": "Check for updates..."},
    "menu.help.report_issue": {"fr": "Signaler un bug / une amelioration...",
                                "en": "Report a bug / suggest an improvement..."},
    "toolbar.report_issue": {"fr": "Signaler", "en": "Report"},
    "report.title": {"fr": "Signaler un bug ou une amelioration", "en": "Report a bug or improvement"},
    "report.not_configured": {"fr": "Cette fonctionnalite n'est pas encore configuree "
                                     "pour cette application (aucun depot GitHub "
                                     "renseigne).",
                               "en": "This feature isn't configured for this "
                                     "application yet (no GitHub repository set)."},
    "report.intro": {"fr": "Decris le probleme ou l'amelioration souhaitee. Ceci "
                            "ouvrira un formulaire GitHub pre-rempli dans ton "
                            "navigateur -- rien n'est envoye avant que tu cliques "
                            "toi-meme sur \"Submit\" sur la page GitHub.",
                      "en": "Describe the problem or improvement you'd like. This "
                            "will open a pre-filled GitHub form in your browser -- "
                            "nothing is sent until you click \"Submit\" yourself "
                            "on the GitHub page."},
    "report.type_label": {"fr": "Type :", "en": "Type:"},
    "report.type_bug": {"fr": "Bug", "en": "Bug"},
    "report.type_feature": {"fr": "Amelioration", "en": "Improvement"},
    "report.title_label": {"fr": "Titre :", "en": "Title:"},
    "report.title_placeholder": {"fr": "Resume en une phrase",
                                  "en": "One-sentence summary"},
    "report.description_label": {"fr": "Description :", "en": "Description:"},
    "report.description_placeholder": {"fr": "Que faisais-tu ? Que s'est-il passe ? "
                                              "Que t'attendais-tu a voir a la place ?",
                                        "en": "What were you doing? What happened? "
                                              "What did you expect instead?"},
    "report.screenshot_note": {"fr": "Capture d'ecran prise au moment du clic -- "
                                      "sera enregistree sur ton disque a l'envoi "
                                      "(jamais transmise automatiquement, GitHub "
                                      "ne le permet pas depuis un lien) ; il te "
                                      "suffira de la glisser-deposer dans le champ "
                                      "de description sur la page GitHub.",
                                "en": "Screenshot taken at the moment of the click "
                                      "-- will be saved to your disk when sending "
                                      "(never transmitted automatically, GitHub "
                                      "doesn't allow that via a link); just drag "
                                      "and drop it into the description field on "
                                      "the GitHub page."},
    "report.auto_included_label": {"fr": "Informations incluses automatiquement "
                                          "(lecture seule) :",
                                    "en": "Automatically included information "
                                          "(read-only):"},
    "report.recent_actions_label": {"fr": "Actions recentes", "en": "Recent actions"},
    "report.no_recent_actions": {"fr": "aucune action recente enregistree",
                                  "en": "no recent action recorded"},
    "report.tech_info_heading": {"fr": "Informations techniques",
                                  "en": "Technical information"},
    "report.screenshot_heading": {"fr": "Capture d'ecran", "en": "Screenshot"},
    "report.screenshot_instruction": {"fr": "Une capture d'ecran a ete enregistree "
                                             "localement -- glisse-la ici pour "
                                             "l'inclure dans ce rapport.",
                                       "en": "A screenshot was saved locally -- "
                                             "drag it here to include it in this "
                                             "report."},
    "report.btn_send": {"fr": "Ouvrir sur GitHub...", "en": "Open on GitHub..."},
    "report.error_missing_fields": {"fr": "Le titre et la description sont "
                                           "obligatoires.",
                                     "en": "Title and description are required."},
    "report.sent_msg": {"fr": "Le formulaire GitHub s'est ouvert dans ton "
                               "navigateur -- relis, glisse la capture d'ecran "
                               "enregistree ici :\n{path}\net clique \"Submit\" "
                               "sur la page pour envoyer.",
                         "en": "The GitHub form opened in your browser -- review "
                               "it, drag in the screenshot saved here:\n{path}\n"
                               "and click \"Submit\" on the page to send."},
    "menu.help.about": {"fr": "A propos...", "en": "About..."},
    "about.version": {"fr": "Version", "en": "Version"},
    "about.license_notice": {"fr": "Distribue sous licence GNU General Public "
                                    "License v3.0 (GPLv3). Ce logiciel est fourni "
                                    "sans aucune garantie ; voir le fichier LICENSE "
                                    "pour le texte complet.",
                              "en": "Distributed under the GNU General Public "
                                    "License v3.0 (GPLv3). This software comes "
                                    "with absolutely no warranty; see the LICENSE "
                                    "file for the full text."},
    "about.open_license_file": {"fr": "Ouvrir le fichier de licence (LICENSE)",
                                 "en": "Open license file (LICENSE)"},
    "update.title": {"fr": "Mise a jour", "en": "Update"},
    "update.available_title": {"fr": "Mise a jour disponible",
                                "en": "Update available"},
    "update.available_msg_html": {"fr": "Une nouvelle version ({version}) est disponible !<br><br>"
                                         "<a href=\"{url}\">{url}</a>",
                                   "en": "A new version ({version}) is available!<br><br>"
                                         "<a href=\"{url}\">{url}</a>"},
    "update.up_to_date": {"fr": "Tu utilises deja la derniere version.",
                           "en": "You're already using the latest version."},
    "update.not_configured": {"fr": "La verification de mise a jour n'est pas encore "
                                     "configuree pour cette application.",
                               "en": "Update checking isn't configured for this "
                                     "application yet."},

    "save.error_title": {"fr": "Erreur d'enregistrement", "en": "Save error"},
    "save.error_msg": {"fr": "Impossible d'enregistrer '{name}' :\n{error}\n\n"
                              "Si c'est une erreur de permission, essaie Fichier > "
                              "'Reparer les permissions de la copie de travail'.",
                        "en": "Could not save '{name}':\n{error}\n\n"
                              "If this is a permission error, try File > "
                              "'Repair working copy permissions'."},

    # --- Explication de l'en-tete ECF (glossaire) ---
    "ecf.header_toggle_show": {"fr": "Voir l'explication des proprietes de ce fichier",
                                "en": "Show property explanations for this file"},
    "ecf.header_toggle_hide": {"fr": "Masquer l'explication des proprietes",
                                "en": "Hide property explanations"},
    "ecf.header_none": {"fr": "Ce fichier ne contient pas de commentaires d'en-tete.",
                         "en": "This file has no header comments."},
    "ecf.header_glossary_intro": {"fr": "Explication clarifiee (pas une traduction mot a "
                                         "mot) des commentaires techniques presents en "
                                         "tete de ce fichier :",
                                   "en": "Clarified explanation (not a word-for-word "
                                         "translation) of the technical comments found "
                                         "at the top of this file:"},
    "ecf.header_raw_toggle": {"fr": "Voir le texte original (anglais)",
                               "en": "Show original text (English)"},
    "ecf.header_translate_btn": {"fr": "Traduire automatiquement en francais",
                                  "en": "Auto-translate to French"},
    "ecf.header_translating": {"fr": "Traduction en cours...", "en": "Translating..."},
    "ecf.header_translate_error": {"fr": "Echec de la traduction automatique : {error}",
                                    "en": "Automatic translation failed: {error}"},
    "ecf.col_property": {"fr": "Propriete", "en": "Property"},
    "ecf.col_value": {"fr": "Valeur", "en": "Value"},
    "ecf.col_type": {"fr": "Type", "en": "Type"},
    "ecf.col_item_value": {"fr": "Valeur", "en": "Value"},
    "btn.add_row_table": {"fr": "+ Ligne", "en": "+ Row"},
    "ecf.add_row_title": {"fr": "Ajouter une ligne", "en": "Add a row"},
    "ecf.add_row_type_label": {"fr": "Type :", "en": "Type:"},
    "ecf.add_row_value_label": {"fr": "Valeur :", "en": "Value:"},
    "ecf.add_row_value_required": {"fr": "Indique une valeur.", "en": "Enter a value."},
    "status.row_added_numbered": {"fr": "'{key}' ajoute (numerote automatiquement)",
                                   "en": "'{key}' added (automatically numbered)"},
    "menu.file.manage_saves": {"fr": "Gerer mes sauvegardes de partie...",
                                "en": "Manage my savegame backups..."},

    # --- Dialogue de sauvegarde generique (scenario ou partie) ---
    "backup.title_scenario": {"fr": "Sauvegarder un scenario", "en": "Back up a scenario"},
    "backup.title_savegame": {"fr": "Sauvegardes de partie", "en": "Savegame backups"},
    "backup.source_scenario": {"fr": "Dossier du scenario a sauvegarder :", "en": "Scenario folder to back up:"},
    "backup.source_savegame": {"fr": "Dossier de la partie a sauvegarder :", "en": "Savegame folder to back up:"},
    "backup.storage_folder": {"fr": "Dossier ou stocker les sauvegardes :", "en": "Folder to store backups in:"},
    "backup.label": {"fr": "Nom (optionnel, ex: 'avant maj 2.0') :", "en": "Name (optional, e.g. 'before update 2.0'):"},
    "backup.create": {"fr": "Sauvegarder maintenant", "en": "Back up now"},
    "backup.existing_list": {"fr": "Sauvegardes existantes :", "en": "Existing backups:"},
    "backup.restore": {"fr": "Restaurer cette sauvegarde...", "en": "Restore this backup..."},
    "backup.delete": {"fr": "Supprimer cette sauvegarde", "en": "Delete this backup"},
    "backup.open_folder": {"fr": "Ouvrir le dossier", "en": "Open folder"},
    "backup.compare_with": {"fr": "Comparer avec...", "en": "Compare with..."},
    "backup.none_yet": {"fr": "Aucune sauvegarde pour l'instant.", "en": "No backups yet."},
    "backup.source_required": {"fr": "Choisis le dossier a sauvegarder.", "en": "Choose the folder to back up."},
    "backup.storage_required": {"fr": "Choisis un dossier ou stocker les sauvegardes.",
                                 "en": "Choose a folder to store backups in."},
    "backup.created_title": {"fr": "Sauvegarde creee", "en": "Backup created"},
    "backup.created_msg": {"fr": "Sauvegarde creee avec succes dans :\n{path}",
                            "en": "Backup successfully created in:\n{path}"},
    "backup.error": {"fr": "Erreur pendant la sauvegarde", "en": "Error during backup"},
    "backup.select_one": {"fr": "Selectionne d'abord une sauvegarde dans la liste.",
                           "en": "Select a backup in the list first."},
    "backup.confirm_delete_title": {"fr": "Confirmer la suppression", "en": "Confirm deletion"},
    "backup.confirm_delete_msg": {"fr": "Supprimer definitivement la sauvegarde '{label}' ? "
                                         "Cette action est irreversible.",
                                   "en": "Permanently delete the backup '{label}'? "
                                         "This action cannot be undone."},
    "backup.restore_title": {"fr": "Restaurer la sauvegarde", "en": "Restore backup"},
    "backup.restore_destination": {"fr": "Dossier de destination (sera entierement remplace) :",
                                    "en": "Destination folder (will be entirely replaced):"},
    "backup.restore_warning": {"fr": "Le contenu actuel du dossier de destination sera ENTIEREMENT "
                                      "remplace par cette sauvegarde. Si le dossier de destination "
                                      "contient deja quelque chose, une sauvegarde de securite automatique "
                                      "sera creee avant, par precaution.",
                                "en": "The current content of the destination folder will be ENTIRELY "
                                      "replaced by this backup. If the destination folder already "
                                      "contains something, an automatic safety backup will be created "
                                      "first, just in case."},
    "backup.confirm_restore": {"fr": "Confirmer la restauration", "en": "Confirm restore"},
    "backup.restore_done_title": {"fr": "Restauration terminee", "en": "Restore complete"},
    "backup.restore_done_msg": {"fr": "Sauvegarde restauree avec succes dans :\n{path}",
                                 "en": "Backup successfully restored to:\n{path}"},
    "backup.restore_done_with_safety": {"fr": "\n\nUne sauvegarde de securite de l'ancien contenu "
                                                "a ete creee : '{label}'",
                                         "en": "\n\nA safety backup of the previous content "
                                               "was created: '{label}'"},
    "backup.restore_error": {"fr": "Erreur pendant la restauration", "en": "Error during restore"},

    # --- Format de diff ECF (reutilise par comparaison de scenarios + blocs en attente) ---
    "diff.new": {"fr": "(nouveau)", "en": "(new)"},
    "diff.removed": {"fr": "(supprime)", "en": "(removed)"},
    "diff.modified": {"fr": "(modifie)", "en": "(modified)"},
    "diff.new_property": {"fr": "(nouvelle propriete)", "en": "(new property)"},
    "diff.removed_property": {"fr": "(propriete supprimee)", "en": "(removed property)"},
    "diff.row_removed": {"fr": "- Ligne '{key}'  (supprimee)", "en": "- Row '{key}'  (removed)"},
    "diff.row_added": {"fr": "+ Ligne '{key}'  (nouvelle)", "en": "+ Row '{key}'  (new)"},
    "diff.row_modified": {"fr": "~ Ligne '{key}'  (modifiee)", "en": "~ Row '{key}'  (modified)"},
    "diff.yaml_removed": {"fr": "- {path}  (supprime)", "en": "- {path}  (removed)"},
    "diff.yaml_added": {"fr": "+ {path}: {value}  (nouveau)", "en": "+ {path}: {value}  (new)"},
    "report.title": {"fr": "Comparaison de scenarios", "en": "Scenario comparison"},
    "report.summary": {"fr": "Resume : {added} fichier(s) ajoute(s), {removed} supprime(s), "
                              "{modified} modifie(s), {unchanged} identique(s)",
                        "en": "Summary: {added} file(s) added, {removed} removed, "
                              "{modified} modified, {unchanged} unchanged"},
    "report.scenario_a_line": {"fr": "Scenario A (reference) : {name}  --  {path}",
                                "en": "Scenario A (reference): {name}  --  {path}"},
    "report.scenario_b_line": {"fr": "Scenario B (compare a A) : {name}  --  {path}",
                                "en": "Scenario B (compared to A): {name}  --  {path}"},
    "report.direction_note": {"fr": "Les differences ci-dessous sont exprimees du point de vue de B : "
                                     "'+' = ajoute dans B, '-' = present dans A mais absent de B (supprime), "
                                     "'~' = different entre A et B.",
                               "en": "The differences below are expressed from B's perspective: "
                                     "'+' = added in B, '-' = present in A but missing from B (removed), "
                                     "'~' = different between A and B."},
    "compare.direction_label": {"fr": "Comparaison de {name_b} par rapport a {name_a}",
                                 "en": "Comparing {name_b} against {name_a}"},
    "yaml.copy_entry_action": {"fr": "Copier cette entree ({label}) vers la copie de travail",
                                "en": "Copy this entry ({label}) to working copy"},
    "csv.duplicate_title": {"fr": "Dupliquer avec une nouvelle cle", "en": "Duplicate with a new key"},
    "csv.duplicate_current_key": {"fr": "Cle actuelle : '{key}'\n\nNouvelle cle :",
                                   "en": "Current key: '{key}'\n\nNew key:"},
    "yaml.duplicate_title": {"fr": "Dupliquer avec une nouvelle cle/valeur", "en": "Duplicate with a new key/value"},
    "yaml.duplicate_current_value": {"fr": "Valeur actuelle : '{value}'\n\nNouvelle valeur :",
                                      "en": "Current value: '{value}'\n\nNew value:"},

    # --- Panneaux du bas (arborescence des 3 scenarios) ---
    "panel.scenario_a": {"fr": "Scenario A (lecture seule)", "en": "Scenario A (read-only)"},
    "panel.working_copy": {"fr": "Copie de travail (modifiable)", "en": "Working copy (editable)"},
    "panel.scenario_b": {"fr": "Scenario B (lecture seule)", "en": "Scenario B (read-only)"},
    "panel.scenario_a_named": {"fr": "Scenario A (lecture seule) -- {name}", "en": "Scenario A (read-only) -- {name}"},
    "panel.working_copy_named": {"fr": "Copie de travail (modifiable) -- {name}", "en": "Working copy (editable) -- {name}"},
    "panel.scenario_b_named": {"fr": "Scenario B (lecture seule) -- {name}", "en": "Scenario B (read-only) -- {name}"},

    # --- Fenetres de progression ---
    "progress.please_wait": {"fr": "Veuillez patienter", "en": "Please wait"},

    # --- Suggestions Id (fenetre duplication) ---
    "dup.suggestions_label": {"fr": "Suggestions libres : {ids}", "en": "Free suggestions: {ids}"},

    # --- Fenetre resultat de traduction ---
    "trans.dialog_title": {"fr": "Traduction", "en": "Translation"},
    "trans.original_label": {"fr": "Original :", "en": "Original:"},
    "trans.translation_label": {"fr": "Traduction :", "en": "Translation:"},
    "trans.close_no_apply": {"fr": "Fermer (ne pas appliquer)", "en": "Close (don't apply)"},

    # --- Fenetre BBCode ---
    "bbcode.title": {"fr": "Mise en forme BBCode", "en": "BBCode formatting"},
    "bbcode.instructions": {"fr": "Selectionne une portion de texte ci-dessous, puis clique une "
                                   "couleur ou un style pour l'appliquer :",
                             "en": "Select a portion of text below, then click a "
                                   "color or a style to apply it:"},
    "bbcode.colors_label": {"fr": "Couleurs :", "en": "Colors:"},
    "bbcode.apply_to_cell": {"fr": "Appliquer a la cellule", "en": "Apply to cell"},
    "bbcode.bold": {"fr": "Gras", "en": "Bold"},
    "bbcode.italic": {"fr": "Italique", "en": "Italic"},
    "bbcode.underline": {"fr": "Souligne", "en": "Underline"},
    "trans.place_in": {"fr": "Placer dans {destination}", "en": "Place in {destination}"},
    "trans.replace_cell": {"fr": "Remplacer la cellule par ce texte", "en": "Replace the cell with this text"},

    # --- Duplication ---
    "dup.file_missing_title": {"fr": "Fichier absent", "en": "File missing"},
    "dup.file_missing_msg": {"fr": "{file} n'existe pas encore dans la copie de travail -- "
                                    "importe d'abord le fichier entier.",
                              "en": "{file} doesn't exist yet in the working copy -- "
                                    "import the whole file first."},
    "dup.block_error": {"fr": "Impossible de dupliquer ce bloc", "en": "Could not duplicate this block"},
    "dup.parent_not_found_title": {"fr": "Bloc parent introuvable", "en": "Parent block not found"},
    "dup.parent_not_found_msg": {"fr": "Ce bloc est imbrique dans un autre (ex: un 'Mode' dans un 'Item'), "
                                        "mais son parent n'existe pas encore dans {file} -- copie/fusionne "
                                        "d'abord le bloc parent avant de dupliquer ce sous-bloc.",
                                  "en": "This block is nested inside another (e.g. a 'Mode' inside an 'Item'), "
                                        "but its parent doesn't exist yet in {file} -- copy/merge "
                                        "the parent block first before duplicating this sub-block."},
    "dup.already_used_title": {"fr": "Deja utilise", "en": "Already in use"},
    "dup.already_used_msg": {"fr": "Cette identite (Id ou Name) est deja utilisee dans {file} -- "
                                    "choisis une autre valeur.",
                              "en": "This identity (Id or Name) is already used in {file} -- "
                                    "choose another value."},
    "copy.block_error": {"fr": "Impossible de copier ce bloc", "en": "Could not copy this block"},
    "copy.row_error": {"fr": "Impossible de copier cette ligne", "en": "Could not copy this row"},
    "dup.key_required_title": {"fr": "Cle requise", "en": "Key required"},
    "dup.key_required_msg": {"fr": "Une cle est necessaire pour identifier cette nouvelle ligne "
                                    "(1ere colonne du fichier).",
                              "en": "A key is required to identify this new row "
                                    "(the file's first column)."},
    "dup.row_error": {"fr": "Impossible de dupliquer cette ligne", "en": "Could not duplicate this row"},
    "dup.key_exists_title": {"fr": "Cle deja utilisee", "en": "Key already in use"},
    "dup.key_exists_msg": {"fr": "La cle '{key}' existe deja dans {file} -- choisis-en une autre.",
                            "en": "The key '{key}' already exists in {file} -- choose another one."},
    "copy.entry_error": {"fr": "Impossible de copier cette entree", "en": "Could not copy this entry"},
    "dup.value_required_title": {"fr": "Valeur requise", "en": "Value required"},
    "dup.value_required_msg": {"fr": "Une nouvelle cle/valeur est necessaire pour distinguer "
                                      "cette entree de l'originale.",
                                "en": "A new key/value is required to distinguish "
                                      "this entry from the original."},
    "dup.entry_error": {"fr": "Impossible de dupliquer cette entree", "en": "Could not duplicate this entry"},
    "dup.value_exists_title": {"fr": "Deja utilisee", "en": "Already in use"},
    "dup.value_exists_msg": {"fr": "'{value}' existe deja dans {file} -- choisis autre chose.",
                              "en": "'{value}' already exists in {file} -- choose something else."},

    # --- Traduction ---
    "trans.unavailable_title": {"fr": "Traduction indisponible", "en": "Translation unavailable"},
    "trans.unavailable_msg": {"fr": "La fonction de traduction n'a pas pu se charger.\n\n"
                                     "Detail technique : {error}\n\n"
                                     "Si tu utilises la version installee (executable), "
                                     "ceci est probablement un bug d'empaquetage -- merci "
                                     "de signaler ce detail exact. Si tu lances depuis les "
                                     "sources Python, essaie : pip install deep-translator",
                               "en": "The translation feature failed to load.\n\n"
                                     "Technical detail: {error}\n\n"
                                     "If you're using the installed version (executable), "
                                     "this is likely a packaging bug -- please report this "
                                     "exact detail. If running from Python sources, try: "
                                     "pip install deep-translator"},
    "trans.error_title": {"fr": "Erreur de traduction", "en": "Translation error"},
    "trans.error_msg": {"fr": "La traduction a echoue :\n{error}\n\nVerifie ta connexion internet.",
                         "en": "Translation failed:\n{error}\n\nCheck your internet connection."},
    "trans.apply_error": {"fr": "Impossible d'appliquer la traduction", "en": "Could not apply the translation"},

    # --- Traduction en lot (selection multiple) ---
    "trans.batch_title": {"fr": "Traduire la selection vers...", "en": "Translate selection to..."},
    "trans.batch_review_title": {"fr": "Revue des traductions", "en": "Review translations"},
    "trans.batch_review_intro": {"fr": "Verifie et ajuste si besoin, puis applique. Decoche les lignes a ignorer.",
                                  "en": "Review and adjust if needed, then apply. Uncheck rows to skip."},
    "trans.col_include": {"fr": "Inclure", "en": "Include"},
    "trans.col_key": {"fr": "Cle", "en": "Key"},
    "trans.col_original": {"fr": "Original", "en": "Original"},
    "trans.col_translated": {"fr": "Traduction", "en": "Translation"},
    "trans.check_all": {"fr": "Tout cocher", "en": "Check all"},
    "trans.uncheck_all": {"fr": "Tout decocher", "en": "Uncheck all"},
    "trans.apply_checked": {"fr": "Appliquer la selection ({count})", "en": "Apply selection ({count})"},
    "trans.no_cells_selected": {"fr": "Selectionne au moins une cellule contenant du texte.",
                                 "en": "Select at least one cell containing text."},
    "trans.translating_progress": {"fr": "Traduction en cours... ({done}/{total})",
                                    "en": "Translating... ({done}/{total})"},
    "trans.from_memory_badge": {"fr": " (memoire)", "en": " (memory)"},
    "status.batch_applied": {"fr": "{count} traduction(s) appliquee(s)", "en": "{count} translation(s) applied"},
    "trans.batch_some_failed": {"fr": "{count} traduction(s) ont echoue (surlignees en rouge, decochees par defaut) -- "
                                       "verifie ta connexion, le service de traduction est peut-etre temporairement bloque.",
                                 "en": "{count} translation(s) failed (highlighted in red, unchecked by default) -- "
                                       "check your connection, the translation service may be temporarily blocked."},
    "trans.batch_stopped_early_title": {"fr": "Arret automatique", "en": "Stopped automatically"},
    "trans.batch_stopped_early_msg": {"fr": "{failed} echecs consecutifs detectes (sur {done} cellules traitees, "
                                             "{remaining} restantes non tentees) -- le service de traduction semble "
                                             "bloque ou indisponible. Arret automatique pour ne pas t'en tenir "
                                             "rigueur inutilement. Les traductions deja reussies restent "
                                             "disponibles pour revue ci-apres.",
                                       "en": "{failed} consecutive failures detected (out of {done} cells "
                                             "processed, {remaining} remaining untried) -- the translation "
                                             "service seems blocked or unavailable. Stopped automatically. "
                                             "Translations already completed remain available for review below."},

    # --- Combler les langues manquantes ---
    "btn.fill_missing_translations": {"fr": "Combler les langues manquantes...", "en": "Fill missing translations..."},
    "trans.fill_missing_title": {"fr": "Combler les traductions manquantes", "en": "Fill missing translations"},
    "trans.fill_source_label": {"fr": "Langue source (deja remplie) :", "en": "Source language (already filled):"},
    "trans.fill_target_label": {"fr": "Langue cible (a completer) :", "en": "Target language (to complete):"},
    "trans.fill_scan_btn": {"fr": "Chercher les cellules manquantes", "en": "Find missing cells"},
    "trans.fill_none_found": {"fr": "Aucune cellule manquante trouvee pour cette combinaison -- "
                                     "cette colonne est deja complete (ou la langue source aussi est vide "
                                     "pour ces lignes).",
                               "en": "No missing cells found for this combination -- this column is "
                                     "already complete (or the source language is also empty for these rows)."},
    "trans.fill_found_count": {"fr": "{count} cellule(s) manquante(s) trouvee(s). Traduction en cours...",
                                "en": "{count} missing cell(s) found. Translating..."},
    "trans.col_row": {"fr": "Ligne", "en": "Row"},

    # --- Bouton traduction rapide ---
    "btn.quick_translate": {"fr": "Traduire", "en": "Translate"},
    "menu.options.default_language": {"fr": "Langue de traduction par defaut...", "en": "Default translation language..."},
    "trans.pick_default_language_title": {"fr": "Langue par defaut", "en": "Default language"},
    "trans.pick_default_language_label": {"fr": "Traduire vers (utilisee par le bouton 'Traduire' rapide) :",
                                           "en": "Translate to (used by the quick 'Translate' button):"},

    # --- Rechercher et remplacer (CSV) ---
    "btn.find_replace": {"fr": "Rechercher et remplacer...", "en": "Find and replace..."},
    "csv.find_replace_title": {"fr": "Rechercher et remplacer", "en": "Find and replace"},
    "csv.find_label": {"fr": "Rechercher :", "en": "Find:"},
    "csv.replace_label": {"fr": "Remplacer par :", "en": "Replace with:"},
    "csv.find_replace_column_label": {"fr": "Dans la colonne :", "en": "In column:"},
    "csv.find_replace_case_sensitive": {"fr": "Respecter la casse", "en": "Case sensitive"},
    "csv.find_replace_whole_word": {"fr": "Mot entier seulement", "en": "Whole word only"},
    "csv.find_replace_search_btn": {"fr": "Chercher les correspondances", "en": "Find matches"},
    "csv.find_replace_empty_search": {"fr": "Indique un texte a rechercher.", "en": "Enter text to search for."},
    "csv.find_replace_none_found": {"fr": "Aucune correspondance trouvee.", "en": "No matches found."},
    "csv.find_replace_review_title": {"fr": "Revue des remplacements", "en": "Review replacements"},
    "csv.find_replace_review_intro": {"fr": "Verifie et ajuste si besoin, puis applique. Decoche les lignes a ignorer.",
                                       "en": "Review and adjust if needed, then apply. Uncheck rows to skip."},
    "csv.col_after_replace": {"fr": "Apres remplacement", "en": "After replacement"},
    "status.find_replace_applied": {"fr": "{count} remplacement(s) applique(s)", "en": "{count} replacement(s) applied"},

    # --- Ouverture de fichiers ---
    "open.error": {"fr": "Impossible d'ouvrir {file}", "en": "Could not open {file}"},
    "open.not_supported_title": {"fr": "Non supporte", "en": "Not supported"},
    "open.not_supported_msg": {"fr": "Pas encore de vue pour les fichiers {ext}",
                                "en": "No viewer yet for {ext} files"},

    # --- Libelles communs ---
    "label.search": {"fr": "Rechercher :", "en": "Search:"},
    "label.value": {"fr": "Valeur :", "en": "Value:"},
    "label.key": {"fr": "Cle :", "en": "Key:"},

    # --- Etats de la copie de travail ---
    "status.editable": {"fr": "copie de travail -- modifiable", "en": "working copy -- editable"},
    "status.readonly": {"fr": "lecture seule", "en": "read-only"},
}


def get_language() -> str:
    return settings.get_language()


def set_language(lang: str) -> None:
    settings.set_language(lang)


def t(translation_key: str, **kwargs) -> str:
    """Traduit `translation_key` dans la langue active. Si la cle est absente, retourne
    la cle elle-meme (visible et sans plantage -- signale qu'une chaine reste a
    traduire). Le parametre s'appelle volontairement `translation_key` et non `key` :
    plusieurs chaines traduites ont elles-memes un placeholder nomme {key} (ex: la cle
    d'une ligne CSV), et un appel comme t("...", key=ma_valeur) entrerait sinon en
    collision avec le nom du premier parametre positionnel -- erreur reelle deja
    rencontree en production (TypeError: t() got multiple values for argument 'key')."""
    entry = STRINGS.get(translation_key)
    if entry is None:
        return translation_key
    lang = get_language()
    text = entry.get(lang, entry.get("fr", translation_key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
