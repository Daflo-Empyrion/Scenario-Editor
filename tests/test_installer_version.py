# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# Licence GPL-3 ou superieure (voir la tete de fichier des autres tests).

"""Garde-fou permanent : la version declaree dans installer.iss (MyAppVersion,
qui donne son nom a Setup-EmpyrionScenarioEditor-vX.Y.Z.exe) doit TOUJOURS
correspondre a APP_VERSION de core/version.py. Oubli signale le 31/08/2026 :
l'installeur v1.6.0 est sorti nomme v1.5.1 (la version etait codee en dur
deux fois, seul core/version.py avait ete incrementee)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_installer_version_matches_app_version():
    from core.version import APP_VERSION
    iss = (ROOT / "installer.iss").read_text(encoding='utf-8')
    match = re.search(r'#define MyAppVersion\s+"([^"]+)"', iss)
    assert match is not None, "MyAppVersion introuvable dans installer.iss"
    assert match.group(1) == APP_VERSION, (
        f"installer.iss declare MyAppVersion={match.group(1)} mais "
        f"core/version.py declare APP_VERSION={APP_VERSION} -- mets a jour "
        "les DEUX a chaque nouvelle version.")
