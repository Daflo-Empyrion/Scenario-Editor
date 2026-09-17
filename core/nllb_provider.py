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
Moteur de traduction local NLLB-200 (Meta) via CTranslate2 : qualite
nettement superieure aux modeles Argos sur l'anglais familier, 100 % local.

Modeles proposes (convertis CTranslate2 int8, depots HuggingFace publics,
telecharges UNE fois vers ~/.empyrion_editor/nllb-<variante>) :
  - 600M distilled int8 (~630 Mo) : rapide, qualite tres bonne (defaut) ;
  - 1.3B distilled int8 (~1,4 Go) : un cran au-dessus, ~1,5x plus lent.

Inférence CPU : CTranslate2 n'acceleere pas les GPU AMD, et le modele est
quantifie pour tourner confortablement en CPU (vecu reel : 1-4 s par cellule
PDA, PDA complet ~2 h en batch nocturne).

Protocole NLLB verifie empiriquement (12/09/2026) : tokens source =
[codigo langue source] + sp.encode(texte) + ['</s>'] ; target_prefix =
[[codigo langue cible]] ; retirer le code cible et '</s>' en tete/queue de
la reponse. Sans l'EOS final, le modele boucle et produit du garbage.

LICENCE : les poids NLLB sont CC-BY-NC 4.0 (usage NON commercial -- ok pour
des scenarios gratuits, a rappeler dans l'assistant d'installation).
"""
import shutil
import threading
import urllib.request
from pathlib import Path
from typing import Dict, Tuple

import ctranslate2
import sentencepiece as spm

HOME_DIR = Path.home() / ".empyrion_editor"
# Codes de langue NLLB (format tresor) pour les langues du selecteur.
NLLB_CODES = {
    "fr": "fra_Latn", "en": "eng_Latn", "de": "deu_Latn", "es": "spa_Latn",
    "it": "ita_Latn", "ru": "rus_Cyrl", "pt": "por_Latn",
    "pt-BR": "por_Latn", "nl": "nld_Latn", "pl": "pol_Latn",
    "ja": "jpn_Jpan", "ko": "kor_Hang", "tr": "tur_Latn", "el": "ell_Grek",
    "vi": "vie_Latn", "zh-CN": "zho_Hans", "zh-TW": "zho_Hant",
}
DEFAULT_SOURCE_CODE = "eng_Latn"

_VARIANTS = {
    "600M": {"repo": "JustFrederik/nllb-200-distilled-600M-ct2-int8",
             "files": ("model.bin", "shared_vocabulary.txt",
                       "sentencepiece.bpe.model", "config.json"),
             "dir": HOME_DIR / "nllb-600M"},
    "1.3B": {"repo": "JustFrederik/nllb-200-distilled-1.3B-ct2-int8",
             "files": ("model.bin", "shared_vocabulary.txt",
                       "sentencepiece.bpe.model", "config.json"),
             "dir": HOME_DIR / "nllb-1.3B"},
}

_lock = threading.Lock()
_translators: Dict[str, tuple] = {}  # variante -> (Translator, sp)


def variant_dir(variant: str) -> Path:
    return _VARIANTS[variant]["dir"]


def is_installed(variant: str) -> bool:
    d = variant_dir(variant)
    return (d / "model.bin").is_file() and (d / "sentencepiece.bpe.model").is_file()


def download_and_install(variant: str, progress_cb=None) -> bool:
    """Telecharge les fichiers du depot HuggingFace de la variante et les
    extrait dans son dossier. Retourne True si le modele est utilisable."""
    def say(msg: str):
        if progress_cb:
            progress_cb(msg)

    spec = _VARIANTS[variant]
    dest: Path = spec["dir"]
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / "_download.zip"
    say(f"Telechargement du modele NLLB {variant}...")
    base = f"https://huggingface.co/{spec['repo']}/resolve/main/"
    with urllib.request.urlopen(base + "model.bin", timeout=120) as resp, \
            open(dest / "model.bin", "wb") as out:
        shutil.copyfileobj(resp, out, length=1024 * 1024)
    say("Telechargement du tokenizer...")
    for name in ("shared_vocabulary.txt", "sentencepiece.bpe.model", "config.json"):
        with urllib.request.urlopen(base + name, timeout=60) as resp, \
                open(dest / name, "wb") as out:
            out.write(resp.read())
    zip_path.unlink(missing_ok=True)
    say("Termine.")
    return is_installed(variant)


def _get_translator(variant: str):
    """Translator + SentencePiece charges une seule fois par variante
    (thread-safe ; le graphe NLLB se charge en < 1 s)."""
    with _lock:
        cached = _translators.get(variant)
        if cached is not None:
            return cached
        d = variant_dir(variant)
        translator = ctranslate2.Translator(str(d), device="cpu",
                                            inter_threads=4)
        sp = spm.SentencePieceProcessor(
            model_file=str(d / "sentencepiece.bpe.model"))
        _translators[variant] = (translator, sp)
        return translator, sp


def nllb_code(code: str) -> str:
    """Code ISO du selecteur -> code tresor NLLB (fra_Latn...). Inconnu ->
    anglais par defaut (jamais de crash pour une langue hors liste)."""
    return NLLB_CODES.get(code, DEFAULT_SOURCE_CODE)


def translate(text: str, source_code: str, target_code: str,
              variant: str = "600M") -> str:
    """Traduit un texte (SANS balises : le pipeline en amont envoie les
    fragments de texte libre, voir core/translation.py)."""
    translator, sp = _get_translator(variant)
    src = nllb_code(source_code)
    tgt = nllb_code(target_code)
    tokens = [src] + sp.encode(text, out_type=str) + ["</s>"]
    res = translator.translate_batch([tokens], target_prefix=[[tgt]],
                                     beam_size=4)
    out = res[0].hypotheses[0]
    if out and out[0] == tgt:
        out = out[1:]
    if out and out[-1] == "</s>":
        out = out[:-1]
    return sp.decode(out)
