"""Digest d'un gros log : signatures groupees au lieu du texte entier.

Un log Unity/Empyrion de 1,5 Mo pese ~360 000 tokens : colle au contexte il
est coupe en route et noie la vraie erreur sous 14 000 lignes de routine. Le
digest groupe les lignes par signature (chiffres, hex et GUID neutralises),
donne le compte et la premiere/derniere occurrence, puis `--grep` ramene la
fenetre exacte a lire.

    python tools/logdigest.py "<log>"                  # top 15 signatures
    python tools/logdigest.py "<log>" --level ERR      # seulement -ERR-
    python tools/logdigest.py "<log>" --grep NullRef --context 5
    python tools/logdigest.py "<log>" --tail 40        # fin brute (crash)

Le fichier n'est jamais charge en entier : une ligne a la fois, seules les
signatures restent en memoire.
"""
import argparse
import re
from collections import Counter, deque
from pathlib import Path

MARKER = re.compile(r"-([A-Z]{2,4})-")
SIGNAL = re.compile(r"Exception|\bError\b|\bWarning\b|\bFATAL\b")
GUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
NUM = re.compile(r"\b\d+\b")


def normalise(line: str) -> str:
    """La ligne sans ce qui change d'une occurrence a l'autre."""
    return " ".join(NUM.sub("N", HEX.sub("H", GUID.sub("G", line))).split())


def signature(line: str, width: int = 110) -> str:
    """Le prefixe qui sert de cle de groupe (tronque : voir `queue variable`)."""
    return normalise(line)[:width]


def scan(path: Path, level: str = "") -> dict:
    groups: dict = {}                        # signature -> [n, premiere, derniere, exemple, queues]
    marks: Counter = Counter()
    lines = chars = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            lines += 1
            chars += len(line)
            for hit in MARKER.finditer(line):
                marks[hit.group(1)] += 1
            for hit in SIGNAL.finditer(line):
                marks[hit.group(0)] += 1
            if level and f"-{level.upper()}-" not in line:
                continue
            full = normalise(line)
            key, tail = full[:110], full[110:150]
            if key in groups:
                group = groups[key]
                group[0] += 1
                group[2] = n
                if len(group[4]) < 2:        # 2 suffit a signaler l'ambiguite
                    group[4].add(tail)
            else:
                groups[key] = [1, n, n, " ".join(line.split())[:170], {tail}]
    return {"lines": lines, "chars": chars, "marks": marks, "groups": groups}


def report(path: Path, data: dict, top: int) -> str:
    groups = data["groups"]
    marks = ", ".join(f"{k} {v}" for k, v in data["marks"].most_common(6)) or "aucun"
    out = [f"{path.name} | {data['lines']} lignes | {data['chars'] / 1024:.0f} Ko"
           f" | ~{data['chars'] // 4000} k tokens",
           f"niveaux : {marks}",
           f"{len(groups)} signatures distinctes, top {min(top, len(groups))}"]
    for key, (count, first, last, sample, tails) in sorted(
            groups.items(), key=lambda kv: -kv[1][0])[:top]:
        span = f"L{first}" if first == last else f"L{first}..L{last}"
        # une queue differente = plusieurs messages groupes : a ne pas lire comme un seul
        flag = "  [queue variable]" if len(tails) > 1 else ""
        out.append(f"{count:>6}x {span:<16} {key}{flag}")
        if count > 1:
            out.append(f"        « {sample} »")
    return "\n".join(out)


def grep(path: Path, pattern: str, context: int) -> int:
    """Les lignes qui matchent, numerotees, avec leur contexte (flux, pas de read())."""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        print(f"motif invalide : {exc}")
        return 2
    before: deque = deque(maxlen=context)
    pending = hits = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if rx.search(line):
                hits += 1
                if hits > 20:
                    print("... 20 correspondances affichees, affine le motif")
                    return 0
                for num, prev in before:
                    print(f"  {num:>7} {prev[:220]}")
                print(f"> {n:>7} {line[:220]}\n")
                pending = context
            elif pending:
                print(f"  {n:>7} {line[:220]}")
                pending -= 1
                if not pending:
                    print()
            before.append((n, line))
    if not hits:
        print("aucune correspondance")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--level", default="", help="ne garder que -ERR-, -WRN-...")
    ap.add_argument("--grep", default="", help="imprimer les lignes qui matchent")
    ap.add_argument("--context", type=int, default=2)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--tail", type=int, default=0, help="N dernieres lignes brutes")
    args = ap.parse_args()
    path = Path(args.log)
    if not path.is_file():
        print(f"fichier absent : {path}")
        return 2
    if args.grep:
        return grep(path, args.grep, args.context)
    data = scan(path, args.level)
    print(report(path, data, args.top))
    if args.tail:
        print(f"\n-- {args.tail} dernieres lignes --")
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh.read().splitlines()[-args.tail:]:
                print(line[:220])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
