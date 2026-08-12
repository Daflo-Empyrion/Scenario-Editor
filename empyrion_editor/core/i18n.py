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
