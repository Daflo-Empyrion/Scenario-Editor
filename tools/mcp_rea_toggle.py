"""Profil MCP leger pour les sessions courantes du projet.

Le serveur `rea` expose 207 outils (~3,4 M caracteres de schemas) : il pese
l'essentiel du contexte de demarrage. On le desactive par defaut et on le
reactive uniquement pour une session de reverse engineering.

Usage (depuis la racine du projet) :
    python tools/mcp_rea_toggle.py status
    python tools/mcp_rea_toggle.py off     # profil leger (defaut conseille)
    python tools/mcp_rea_toggle.py on      # reverse engineering

Le changement prend effet a la PROCHAINE session / au redemarrage de ZCode.
Le fichier utilisateur est sauvegarde (config.json.bak-mcp-<date>) avant
chaque ecriture ; l'ecriture est atomique.
"""
import datetime
import json
import os
import sys
from pathlib import Path

CONFIG = Path.home() / ".zcode" / "cli" / "config.json"
SERVER = "rea"


def _load() -> dict:
    with CONFIG.open(encoding="utf-8") as fh:
        return json.load(fh)


def _save(data: dict) -> None:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CONFIG.with_name(f"{CONFIG.name}.bak-mcp-{stamp}")
    backup.write_bytes(CONFIG.read_bytes())
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, CONFIG)


def main(argv: list[str]) -> int:
    action = (argv[1] if len(argv) > 1 else "status").lower()
    data = _load()
    server = data.get("mcp", {}).get("servers", {}).get(SERVER)
    if server is None:
        print(f"serveur '{SERVER}' absent de {CONFIG}")
        return 1
    enabled = server.get("enabled", True)
    if action == "status":
        state = "ON (contexte lourd)" if enabled else "OFF (profil leger)"
        print(f"{SERVER}: {state}")
        return 0
    if action not in ("on", "off"):
        print("usage: mcp_rea_toggle.py [status|on|off]")
        return 2
    server["enabled"] = action == "on"
    _save(data)
    print(f"{SERVER}: {'ON' if action == 'on' else 'OFF'} — "
          f"effectif a la prochaine session (redemarrer ZCode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
