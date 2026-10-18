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

"""DELEGATION a un LLM LOCAL (Unsloth Studio, http://127.0.0.1:8888/v1).

Sert a l'agent ZCode (ou en CLI) pour sous-traiter des taches textuelles a un
modele local gratuit et prive — chaque tache deleguee economise les tokens de
l'abonnement Zai. ZERO dependance (urllib), identifiants lus dans
~/.unsloth/studio/auth/.api_password (jamais dans le repo).

Capacites :
  - texte   : relecture, resume, traduction, tri, extraction...
  - VISION  : --image FICHIER (le modele charge doit etre multimodal, ex
    MiniCPM-V) : decrire/analyser une image ;
  - WEB     : --web URL (proxy du studio : fetch de la page, extraction du
    texte, question dessus) et --search "requete" (DuckDuckGo : resultats
    synthetises par le modele local).

Le contexte du modele charge (lu via /v1/models) borne l'entree (refus propre
+ consigne de decoupe) ET la sortie (max_tokens).

Usage :
  python tools/llm_delegate.py "Relis ce texte et corrige les coquilles: <texte>"
  python tools/llm_delegate.py -f dialogue.txt "Traduis en anglais le texte suivant"
  python tools/llm_delegate.py --image screenshot.png "Decris cette image"
  python tools/llm_delegate.py --web https://... "Resume en 5 puces"
  python tools/llm_delegate.py --search "empyrion yaml sectors" "Les 5 resultats les plus pertinents"
  python tools/llm_delegate.py --list / --load MODELE[:QUANT][:CTX]

La reponse du modele va sur STDOUT (pippable) ; le timing et l'usage de
jetons vont sur STDERR. Le code retour est 0 seulement si le modele a
effectivement repondu."""
from __future__ import annotations

import argparse
import base64
import html as html_mod
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8888"
AUTH_DIR = Path.home() / ".unsloth" / "studio" / "auth"
DEFAULT_MODEL = "lmstudio-community/gemma-4-12B-it-GGUF"

SYSTEM_PROMPT = (
    "Tu es un assistant d'execution silencieux integre a une chaine de "
    "traitement. Tu recois UNE tache et tu reponds EXACTEMENT ce qui est "
    "demande, sans preambule, sans conclusion, sans t'adresser a personne. "
    "Si la tache demande un format (liste, tableau, JSON), tu respectes ce "
    "format a la lettre. Reponds dans la langue de la tache.")


def _post(path: str, payload: dict, token: str | None = None,
          timeout: int = 600) -> tuple:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(
            {"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _get(path: str, token: str, timeout: int = 30) -> tuple:
    req = urllib.request.Request(
        BASE + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def get_token() -> str:
    """Login local (jeton ~1 h ; les appelants reessaient sur 401)."""
    pwd_file = AUTH_DIR / ".api_password"
    if not pwd_file.exists():
        sys.exit("Pas de ~/.unsloth/studio/auth/.api_password — "
                 "initialise le studio d'abord.")
    _, data = _post("/api/auth/login", {
        "username": "unsloth",
        "password": pwd_file.read_text(encoding="utf-8").strip()}, timeout=15)
    return data["access_token"]


def resolve_model(token: str, model: str | None = None) -> tuple:
    """(id, context_length) du modele a utiliser. Le serveur ne sert QUE le
    modele charge : si le modele demande n'est pas le charge, bascule sur le
    charge (mention sur stderr) — un sous-agent delegue, l'outil se
    debrouille."""
    _, data = _get("/v1/models", token)
    loaded = [m for m in data["data"] if m.get("loaded")]
    if not loaded:
        sys.exit("Aucun modele charge — ouvre Unsloth Studio et charge-en "
                 "un, ou utilise --load.")
    chosen = loaded[0]
    if model:
        by_id = {m["id"]: m for m in loaded}
        if model in by_id:
            chosen = by_id[model]
        else:
            print(f"[llm_delegate] {model} non charge, bascule sur "
                  f"{chosen['id']}", file=sys.stderr)
    return chosen["id"], int(chosen.get("context_length") or 8192)


def html_to_text(html: str) -> str:
    """HTML -> texte lisible (script/style/tags retires, entites decodees)."""
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = html_mod.unescape(text)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


def fetch_web(url: str, token: str, max_bytes: int = 2_000_000) -> str:
    """Page web via le proxy du studio -> TEXTE (consomme du contexte, pas
    des outils Zai)."""
    _, data = _post("/api/browser/fetch",
                    {"url": url, "max_bytes": max_bytes}, token, timeout=120)
    return html_to_text(data.get("html") or "")


def search_web(query: str, token: str) -> str:
    """Bing (page HTML) -> bloc 'titre - url - extrait' par resultat.
    DuckDuckGo renvoie un CAPTCHA au proxy du studio ; Bing passe."""
    _, data = _post("/api/browser/fetch", {
        "url": "https://www.bing.com/search?q=" + urllib.request.quote(query),
        "max_bytes": 1_000_000}, token, timeout=120)
    html = data.get("html") or ""
    lines = []
    for i, m in enumerate(re.finditer(
            r'<li class="b_algo".*?<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>'
            r'(.*?)</a></h2>(.*?)</li>', html, re.S)):
        url = _bing_real_url(m.group(1))
        title, rest = html_to_text(m.group(2)), m.group(3)
        snip = re.search(r"<p[^>]*>(.*?)</p>", rest, re.S)
        extra = html_to_text(snip.group(1)) if snip else ""
        lines.append(f"{i + 1}. {title}\n   {url}\n   {extra[:200]}")
        if len(lines) >= 10:
            break
    return "\n".join(lines) or html_to_text(html)[:2000]


def _bing_real_url(url: str) -> str:
    """Bing enveloppe les liens ('/ck/a?...&u=a1<base64>') : decodage."""
    url = html_mod.unescape(url)
    if "bing.com/ck/" not in url:
        return url
    m = re.search(r"[?&]u=a\d([A-Za-z0-9_\-=%]+)", url)
    if not m:
        return url
    b = m.group(1).replace("%3d", "=").replace("%3D", "=")
    b += "=" * (-len(b) % 4)
    try:
        return base64.urlsafe_b64decode(b).decode("utf-8", "replace")
    except Exception:
        return url


def ask(task: str, content: str = "", model: str | None = None,
        token: str | None = None, timeout: int = 1200,
        image: Path | None = None) -> str:
    """Une question, une reponse. `content` (fichier/stdin/web) est ajoute a
    la tache comme matiere a travailler ; `image` active la VISION (modele
    multimodal requis). Le contexte du modele charge (lu via /v1/models)
    borne l'entree (refus propre + consigne de decoupe) ET la sortie."""
    token = token or get_token()
    model, ctx = resolve_model(token, model)
    user = task if not content else f"{task}\n\n---\n{content}"
    # ~1 token pour 3.5 caracteres ; une image consomme un budget visuel fixe
    est_in = (len(user) + len(SYSTEM_PROMPT)) / 3.5 + (1600 if image else 0)
    budget_out = max(256, int(ctx - est_in - 64))
    if budget_out < 256 or est_in > ctx * 0.95:
        max_chars = int((ctx * 0.5) * 3.5)
        sys.exit(f"[llm_delegate] entree ~{est_in:.0f} tokens > contexte du "
                 f"modele ({ctx}). Decoupe la matiere en morceaux de "
                 f"~{max_chars:,} caracteres et delegue morceau par morceau.")
    if est_in > ctx * 0.8:
        print(f"[llm_delegate] entree ~{est_in:.0f}/{ctx} tokens : proche "
              "de la limite, reponse courte attendue", file=sys.stderr)
    if image is not None:
        b64 = base64.b64encode(image.read_bytes()).decode("ascii")
        mime = ("image/png" if image.suffix == ".png" else
                "image/webp" if image.suffix == ".webp" else "image/jpeg")
        user_content = [
            {"type": "text", "text": user},
            {"type": "image_url",
             "image_url": {"url": f"data:{mime};base64,{b64}"}}]
    else:
        user_content = user
    t0 = time.perf_counter()
    try:
        _, data = _post("/v1/chat/completions", {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": user_content}],
            "temperature": 0.2,
            "max_tokens": min(32768, budget_out),
        }, token, timeout)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return ask(task, content, model, get_token(), timeout, image)
        raise
    dt = time.perf_counter() - t0
    usage = data.get("usage", {})
    print(f"[llm_delegate {dt:.1f}s "
          f"in={usage.get('prompt_tokens', '?')} "
          f"out={usage.get('completion_tokens', '?')} tok "
          f"modele={data.get('model', model)}]", file=sys.stderr)
    return data["choices"][0]["message"]["content"]


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="Delegation a un LLM local")
    ap.add_argument("task", nargs="?", help="tache a deleguer")
    ap.add_argument("-f", "--file", help="fichier joins a la tache")
    ap.add_argument("-o", "--out", help="ecrire la reponse dans ce fichier")
    ap.add_argument("--model", default=None,
                    help="modele precis ; sinon celui qui est charge")
    ap.add_argument("--list", action="store_true",
                    help="lister les modeles disponibles/charges")
    ap.add_argument("--image", metavar="FICHIER",
                    help="image a analyser (vision, modele multimodal)")
    ap.add_argument("--web", metavar="URL",
                    help="fetcher la page web et la joindre a la tache")
    ap.add_argument("--search", metavar="REQUETE",
                    help="recherche DuckDuckgo jointe a la tache")
    ap.add_argument("--load", metavar="MODELE[:QUANT][:CTX]",
                    help="charger un modele avant de travailler")
    args = ap.parse_args(argv)

    token = get_token()
    if args.list:
        _, data = _get("/v1/models", token)
        for m in data["data"]:
            state = "CHARGE" if m.get("loaded") else m["status"]["value"]
            print(f"{state:10s} {m['id']:60s} {m.get('quant', '')}")
        return 0
    if args.load:
        # MODELE[:QUANT][:CTX] — CTX = contexte en tokens (max_seq_length) ;
        # 9472 par defaut = ajustement VRAM du studio, monter progressivement
        # (16384, 32768...) : au-dela de la VRAM le chargement echoue.
        parts = args.load.split(":")
        model = parts[0]
        payload = {"model_path": model}
        extra = [p for p in parts[1:] if p]
        if extra:
            payload["gguf_variant"] = extra[0]
        if len(extra) > 1 and extra[1].isdigit():
            payload["max_seq_length"] = int(extra[1])
        print(f"chargement de {model} {' '.join(extra)} (peut prendre "
              "plusieurs minutes)...", file=sys.stderr)
        _post("/api/inference/load", payload, token, timeout=900)
        print("modele charge.", file=sys.stderr)
    if not args.task:
        ap.error("precise une tache (ou --list/--load)")
    content = Path(args.file).read_text(encoding="utf-8") if args.file else (
        sys.stdin.read() if not sys.stdin.isatty() else "")
    if args.web:
        text = fetch_web(args.web, token)
        print(f"[llm_delegate] page fetchee : {len(text):,} caracteres",
              file=sys.stderr)
        content = (content + "\n\n" if content else "") + \
            f"PAGE WEB {args.web}\n{text}"
    if args.search:
        res = search_web(args.search, token)
        content = (content + "\n\n" if content else "") + \
            f"RESULTATS DE RECHERCHE ({args.search})\n{res}"
    image = Path(args.image) if args.image else None
    answer = ask(args.task, content, args.model, token, image=image)
    if args.out:
        Path(args.out).write_text(answer, encoding="utf-8")
        print(f"reponse ecrite dans {args.out}", file=sys.stderr)
    else:
        print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
