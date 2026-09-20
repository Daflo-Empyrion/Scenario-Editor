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
Erreurs TYPEES des moteurs de traduction (v1.10.0, inspire du failover
de freellmapi) : la chaine de secours (core/translation.py) decide de la
bascule selon le TYPE de l'erreur, pas selon son texte.

Toutes heritent de RuntimeError : les tests existants (pytest.raises(
RuntimeError, match=...)) et l'interface (str(e) affiche) restent valides.

- QuotaExhaustedError : plafond du fournisseur (429/402/456) -> BASCULE
  vers le moteur suivant, et le moteur est mis au repos (cooldown).
- EngineUnavailableError : reseau tombe, 5xx, moteur/modele absent ->
  BASCULE.
- AuthError : cle refusee (401/403) -> NE BASCULE PAS (l'utilisateur a
  une mauvaise cle : le cacher derriere un autre moteur masquerait la
  cause) ; l'erreur remonte telle quelle.
"""


class EngineError(RuntimeError):
    """Base commune des erreurs de moteur de traduction."""


class QuotaExhaustedError(EngineError):
    """Plafond du fournisseur atteint (debit ou quota) -- basculable."""


class EngineUnavailableError(EngineError):
    """Moteur momentanement inutilisable (reseau, 5xx, absent) -- basculable."""


class AuthError(EngineError):
    """Cle API refusee -- JAMAIS de bascule silencieuse dessus."""


def is_fallback_worthy(exc: BaseException) -> bool:
    """Vrai si la chaine de secours doit passer au moteur suivant."""
    if isinstance(exc, AuthError):
        return False
    return isinstance(exc, (QuotaExhaustedError, EngineUnavailableError,
                            TimeoutError))
