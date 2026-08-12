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

    # --- Boutons communs (editeurs) ---
    "btn.save": {"fr": "Enregistrer (Ctrl+S)", "en": "Save (Ctrl+S)"},
    "btn.undo": {"fr": "Annuler (Ctrl+Z)", "en": "Undo (Ctrl+Z)"},
    "btn.add_block": {"fr": "+ Bloc", "en": "+ Block"},
    "btn.add_property": {"fr": "+ Propriete", "en": "+ Property"},
    "btn.add_row": {"fr": "+ Ligne", "en": "+ Row"},
    "btn.delete_selected_row": {"fr": "- Ligne selectionnee", "en": "- Selected row"},
    "btn.add_entry": {"fr": "+ Entree", "en": "+ Entry"},
    "btn.delete_selected_entry": {"fr": "Supprimer l'entree selectionnee", "en": "Delete selected entry"},
    "btn.filter_by_property": {"fr": "Filtrer par propriete...", "en": "Filter by property..."},
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


def t(key: str, **kwargs) -> str:
    """Traduit `key` dans la langue active. Si la cle est absente, retourne la cle
    elle-meme (visible et sans plantage -- signale qu'une chaine reste a traduire)."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    lang = get_language()
    text = entry.get(lang, entry.get("fr", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
