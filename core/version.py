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
Version de l'application et configuration du depot GitHub pour la verification
de mise a jour.

A CHAQUE NOUVELLE VERSION DISTRIBUEE : incremente APP_VERSION ci-dessous (ex:
"1.0.0" -> "1.1.0"), puis cree une Release GitHub avec un tag identique
(ex: "v1.1.0") -- c'est ce tag que le verificateur de mise a jour compare.

QUAND TU CREES TON DEPOT GITHUB : remplace GITHUB_REPO ci-dessous par son adresse
(ex: "Daflo/empyrion-scenario-editor"). Tant que ce champ reste vide, la
verification de mise a jour se desactive silencieusement -- rien n'est casse.
"""

APP_VERSION = "1.4.0"

# Adresse du depot GitHub au format "utilisateur/nom-du-depot", utilisee pour
# verifier les mises a jour via l'API des Releases GitHub. Laisser vide ("")
# desactive proprement la verification (aucune erreur, juste ignoree).
GITHUB_REPO = "Daflo-Empyrion/Scenario-Editor"


def is_update_check_configured() -> bool:
    return bool(GITHUB_REPO.strip())
