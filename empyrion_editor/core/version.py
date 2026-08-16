"""
Version de l'application et configuration du depot GitHub pour la verification
de mise a jour.

A CHAQUE NOUVELLE VERSION DISTRIBUEE : incremente APP_VERSION ci-dessous (ex:
"1.0.0" -> "1.1.0"), puis cree une Release GitHub avec un tag identique
(ex: "v1.1.0") -- c'est ce tag que le verificateur de mise a jour compare.

QUAND TU CREES TON DEPOT GITHUB : remplace GITHUB_REPO ci-dessous par son adresse
(ex: "Daflo/empyrion-scenario-editor"). Tant que ce champ reste vide, la
verification de mise a jour se desactive silencieusement -- rien n'est casse.
"""

APP_VERSION = "1.0.0"

# Adresse du depot GitHub au format "utilisateur/nom-du-depot", utilisee pour
# verifier les mises a jour via l'API des Releases GitHub. Laisser vide ("")
# desactive proprement la verification (aucune erreur, juste ignoree).
GITHUB_REPO = ""


def is_update_check_configured() -> bool:
    return bool(GITHUB_REPO.strip())
