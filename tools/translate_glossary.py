# -*- coding: utf-8 -*-
"""Genere data/ecf_header_glossary.en.json : traduction EN du glossaire FR
(OPT-006, demande du 10/09/2026). Utilise le traducteur deja embarque
(core/translation.py -- Google via deep-translator) ; les titres de sections
et les explications sont traduits, les TERMES (cles de recherche, ex
'AllowPlacingAt') restent tels quels. Reprise sur incident : les resultats
sont memorises dans data/ecf_header_glossary.en.json au fil de l'eau, un
second appel ne traduit que le manquant. Necessite : reseau + Options >
Traduction en ligne activee.

UTILISATION : python tools/translate_glossary.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SRC = ROOT / "data" / "ecf_header_glossary.json"
DEST = ROOT / "data" / "ecf_header_glossary.en.json"


def main() -> int:
    from core.translation import translate_text
    source = json.loads(SRC.read_text(encoding="utf-8"))
    try:
        out = json.loads(DEST.read_text(encoding="utf-8"))
    except Exception:
        out = {}

    def _is_garbage(text: str) -> bool:
        """Pages d'erreur HTML/Google recues a la place d'une traduction
        (observe en reel le 10/09/2026 : 'Error 500 (Server Error)!!1...')."""
        if not text:
            return True
        lowered = text.lower()
        return ("that's an error" in lowered or "error 5" in lowered
                or "google.com" in lowered or "<html" in lowered)

    def translate_safe(text: str) -> str:
        for attempt in range(3):
            try:
                result = translate_text(text, target="en")
            except Exception as e:
                print(f"  tentative {attempt+1} echouee : {e}", flush=True)
                time.sleep(5 * (attempt + 1))
                continue
            if not _is_garbage(result):
                return result
            print("  reponse invalide (page d'erreur), nouvelle tentative...",
                  flush=True)
            time.sleep(5 * (attempt + 1))
        raise RuntimeError("traduction impossible apres 3 tentatives")

    total = done = 0
    for gk, sections in source.items():
        out_sections = out.setdefault(gk, [])
        for si, (title, entries) in enumerate(sections):
            while len(out_sections) <= si:
                out_sections.append(["", []])
            if si < len(out_sections):
                if not out_sections[si][0]:
                    try:
                        out_sections[si][0] = translate_safe(title)
                    except Exception as e:
                        out_sections[si][0] = title  # repli FR
                        print(f"titre non traduit : {e}")
            out_entries = out_sections[si][1]
            for ei, (term, explanation) in enumerate(entries):
                total += 1
                while len(out_entries) <= ei:
                    out_entries.append([term, ""])
                if out_entries[ei][1]:
                    continue  # deja traduit (reprise)
                try:
                    out_entries[ei][0] = term
                    out_entries[ei][1] = translate_safe(explanation)
                except Exception as e:
                    print(f"[{total}] ECHEC '{term}': {e}")
                    continue
                done += 1
                if done % 10 == 0:
                    DEST.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
                    print(f"{done} traduites...", flush=True)
                time.sleep(0.3)  # aimable avec le service de traduction
    DEST.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"termine : {done} nouvelles traductions, fichier : {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
