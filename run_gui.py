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
Lance l'interface graphique de l'editeur de scenario Empyrion.

UTILISATION :
    python run_gui.py

DIAGNOSTIC ARGOS (version installee) : ESE_ARGOS_SELFTEST=<chemin.log>
declenche la chaine hors ligne complete SANS interface (estimation pip,
installation du moteur embarque, traduction reelle si une paire en<->fr
est deja sur disque), ecrit le journal puis termine -- code 0 si tout
fonctionne, 1 sinon. Sans cette variable d'environnement, l'appli se lance
normalement en mode graphique.
"""
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Executable construit par PyInstaller (voir empyrion_editor.spec) : 'core' et
    # 'gui' sont deja compiles dans l'archive et directement importables, aucune
    # recherche de dossier necessaire -- la detection ci-dessous ne s'applique
    # qu'a une execution depuis les sources.
    pass
else:
    _ici = Path(__file__).resolve().parent
    _candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
    for _c in _candidats:
        if (_c / "core" / "scanner.py").exists():
            sys.path.insert(0, str(_c))
            break
    else:
        print("ERREUR : impossible de trouver le dossier 'core'.")
        sys.exit(1)


def _argos_selftest() -> bool:
    """Consomme l'execution (sys.exit) si ESE_ARGOS_SELFTEST est posee."""
    import traceback
    log_path = os.environ.get("ESE_ARGOS_SELFTEST")
    if not log_path:
        return False
    lines = []

    def say(msg):
        lines.append(str(msg))

    ok = False
    try:
        from core import argos_provider
        say(f"frozen={getattr(sys, 'frozen', False)} exe={sys.executable}")
        say(f"moteur disponible avant : {argos_provider.is_engine_available()}")
        if not argos_provider.is_engine_available():
            say(f"estimation dry-run : "
                f"{argos_provider.estimate_engine_download_bytes()} octets")
            ok = argos_provider.install_engine(progress_cb=say)
            say(f"install_engine -> {ok}")
        else:
            ok = True
        if ok:
            # Sonde torch : dans l'exe, l'ordre d'initialisation de torch a
            # montre une divergence (AttributeError 'autograd' au premier
            # import) -- on dresse l'etat exact des modules en cas d'echec.
            try:
                import torch
                say(f"torch {torch.__version__} importe OK")
            except Exception:
                say("sonde import torch ECHEC :")
                say(traceback.format_exc())
            finally:
                import sys as _sysmod
                _t = _sysmod.modules.get("torch")
                say(f"torch dans sys.modules : {_t is not None}")
                if _t is not None:
                    say(f"torch.__dict__['autograd'] present : "
                        f"{'autograd' in vars(_t)}")
                    say(f"'torch.autograd' dans sys.modules : "
                        f"{'torch.autograd' in _sysmod.modules}")
            codes = sorted(argos_provider.installed_pair_codes())
            say(f"paires sur disque : {codes}")
            pair = next(((s, tt) for (s, tt) in codes if tt == "fr"), None)
            if pair:
                original = "Hello world, this is a real translation test."
                out = argos_provider.translate_offline(original, pair[0], pair[1])
                say(f"traduction reelle {pair[0]}->{pair[1]} : {out!r}")
                ok = bool(out.strip()) and out.strip() != original
            else:
                say("aucune paire vers fr sur disque : traduction non testee")
        if ok:
            from importlib.metadata import version as _pkg_version
            say(f"argostranslate {_pkg_version('argostranslate')} importe OK")
    except Exception as e:
        say(f"EXCEPTION: {e!r}")
        say(traceback.format_exc())
        ok = False
    content = "\n".join(lines)
    try:
        Path(log_path).write_text(content, encoding="utf-8")
    except OSError:
        import tempfile
        Path(tempfile.gettempdir(), "ese_argos_selftest.log").write_text(
            content, encoding="utf-8")
    sys.exit(0 if ok else 1)


from gui.main_window import main

if __name__ == "__main__":
    if not _argos_selftest():
        main()
