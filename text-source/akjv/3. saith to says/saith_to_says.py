#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
saith_to_says.py — AKJV : « said » → « says » quand la KJV a « saith ».

L'AKJV rend systématiquement l'archaïsme « saith » de la KJV par « said »
(elle n'emploie jamais « says »). Ce script repasse sur le texte AKJV avec
italiques (sortie d'add_italics.py, dossier « 2. adding italics ») et
remplace chaque « said » — qu'il soit dans une plage \add … \add* (italique)
ou non — par « says », uniquement lorsque le mot KJV correspondant du verset
est « saith ». Les « said » qui correspondent à un « said » ou « saidst » de
la KJV sont laissés tels quels.

L'alignement KJV ↔ AKJV reprend la logique d'add_italics.py (blocs communs
de difflib, puis recherche des formes modernisées dans les écarts), étendue à
tous les mots ; la ponctuation collée aux mots n'est jamais touchée.

Usage (depuis ce dossier « 3. saith to says ») :
    python3 saith_to_says.py                        # -> akjv-with-italics-says-usfm.zip
    python3 saith_to_says.py -i out.zip -o o2.zip
    python3 saith_to_says.py --no-zip -o usfm/      # dossier
    python3 saith_to_says.py --single -o akjv.usfm  # un seul fichier
    python3 saith_to_says.py --report rapport.tsv   # liste des versets modifiés

Contrôles :
  * pour chaque verset réécrit, on vérifie qu'en retirant les marques \add du
    nouveau texte on retrouve exactement les mots du texte d'entrée, à
    l'exception des « said » → « says » attendus ;
  * en fin de traitement, on re-parcourt la sortie : plus aucun « said » ne
    doit correspondre à un « saith » de la KJV, et chaque « saith » de la KJV
    doit correspondre à un « says » de l'AKJV.
Toute différence interrompt le traitement.
"""

import argparse
import difflib
import os
import re
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# add_italics.py vit dans le dossier « 2. adding italics » (chemin relatif au
# script, donc valable quelle que soit la façon de lancer ce script).
_ITALICS_DIR = os.path.join(SCRIPT_DIR, "..", "2. adding italics")
for _p in (SCRIPT_DIR, _ITALICS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from add_italics import MARK, norm, kjv_parse, modernize, PHRASES  # noqa: E402

# ---------------------------------------------------------------------------
# Découpage d'un verset AKJV (texte brut + \add … \add*).
# ---------------------------------------------------------------------------
_ADD_OPEN = ("add", "+add")
_ADD_CLOSE = ("add*", "+add*")


def tokenize(body):
    """Découpe le corps d'un verset AKJV en mots.

    Renvoie (words, spans, ital) :
      words : mots normalisés (minuscules, ponctuation des bords ôtée) ;
      spans : bornes (début, fin) de chaque mot dans body ;
      ital  : drapeau « dans une plage \add … \add* ».
    """
    words, spans, ital = [], [], []
    i, n = 0, len(body)
    italic = False
    while i < n:
        if body[i] == "\\":
            m = MARK.match(body, i)
            if m:
                name = m.group(1)
                i = m.end()
                if name in _ADD_OPEN:
                    italic = True
                elif name in _ADD_CLOSE:
                    italic = False
                continue
            i += 1
            continue
        j = i
        while j < n and body[j] != "\\":
            j += 1
        for w in re.finditer(r"\S+", body[i:j]):
            start = i + w.start()
            end = i + w.end()
            words.append(norm(w.group(0)))
            spans.append((start, end))
            ital.append(italic)
        i = j
    return words, spans, ital


_CORE_LEAD = re.compile(r"^[^A-Za-z0-9']+")
_CORE_TAIL = re.compile(r"[^A-Za-z0-9']+$")


def core_span(tok):
    """Bornes du noyau alphabétique d'un jeton (ponctuation des bords exclue,
    apostrophe incluse). Permet de remplacer le mot sans toucher à la
    ponctuation collée."""
    lead = _CORE_LEAD.match(tok)
    tail = _CORE_TAIL.search(tok)
    lo = lead.end() if lead else 0
    hi = tail.start() if tail else len(tok)
    return lo, hi


# ---------------------------------------------------------------------------
# Alignement KJV ↔ AKJV : position AKJV -> position KJV.
# ---------------------------------------------------------------------------
def map_words(kjv_words, akjv_words):
    """Renvoie {position AKJV: position KJV} pour chaque mot AKJV associé à un
    mot KJV (tous les mots, italiques ou non).

    Reproduit l'alignement d'add_italics.align_verse (passe des suites
    « whence → from where », blocs communs, puis modernisations isolées), en
    le généralisant à l'ensemble des mots afin de retrouver, pour chaque mot
    AKJV, le mot KJV dont il est la modernisation.
    """
    a = [norm(w) for w, _ in kjv_words]
    b = [norm(w) for w, _ in akjv_words]
    a_len, b_len = len(a), len(b)
    if not a_len or not b_len:
        return {}
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    src = {}
    used = [False] * len(b)

    # Passe 0 : archaïsmes rendus par plusieurs mots (whence → from where…).
    phrase_used = set()
    for ki, (w, _it) in enumerate(kjv_words):
        phrase = PHRASES.get(norm(w))
        if not phrase:
            continue
        plen = len(phrase)
        expected = ki * b_len / a_len
        plo = max(0, int(expected) - 3)
        phi = min(b_len - plen + 1, int(expected) + 4)
        best_p = None
        for j in range(plo, phi):
            if all(b[j + k] == phrase[k] and (j + k) not in phrase_used
                   for k in range(plen)):
                if best_p is None or abs(j - expected) < abs(best_p - expected):
                    best_p = j
        if best_p is not None:
            for k in range(plen):
                src[best_p + k] = ki
                phrase_used.add(best_p + k)

    # Passe 1 : blocs communs (mots identiques dans les deux textes).
    orphaned = set()
    for i, j, size in sm.get_matching_blocks():
        for k in range(size):
            if j + k in phrase_used:
                orphaned.add(i + k)
                continue
            src[j + k] = i + k
            used[j + k] = True

    # Passe 2 : mots KJV sans équivalent exact (saith → said, thou → you,
    # -eth → -s…), cherchés dans l'écart d'alignement voisin.
    unmatched = [not u for u in used]
    for ki, (w, _it) in enumerate(kjv_words):
        in_block = False
        for i, j, size in sm.get_matching_blocks():
            if i <= ki < i + size:
                in_block = True
                break
        if in_block and ki not in orphaned:
            continue
        n = norm(w)
        phrase = PHRASES.get(n)
        expected = ki * b_len / a_len
        if phrase:
            plen = len(phrase)
            plo = max(0, int(expected) - 3)
            phi = min(b_len - plen + 1, int(expected) + 4)
            best_p = None
            for j in range(plo, phi):
                if all(not used[j + k] and (j + k) not in src
                       and b[j + k] == phrase[k] for k in range(plen)):
                    if best_p is None or abs(j - expected) < abs(best_p - expected):
                        best_p = j
            if best_p is not None:
                for k in range(plen):
                    src[best_p + k] = ki
                continue
        cands = set(modernize(w))
        best, best_d = None, None
        lo = max(0, int(expected) - 3)
        hi = min(b_len, int(expected) + 4)
        for j in range(lo, hi):
            if not unmatched[j] or j in src:
                continue
            if b[j] in cands:
                d = abs(j - expected)
                if best is None or d < best_d:
                    best, best_d = j, d
        if best is not None:
            src[best] = ki
    return src


# ---------------------------------------------------------------------------
# Réécriture d'un verset.
# ---------------------------------------------------------------------------
def rewrite(body, kjv_words):
    """Remplace « said » par « says » dans le verset quand le mot KJV
    correspondant est « saith » (que le mot soit en italique ou non).

    Renvoie (nouveau texte, nombre de remplacements). Lève une exception si le
    texte produit ne correspond pas exactement à l'entrée modulo les
    remplacements attendus.
    """
    words, spans, _ital = tokenize(body)
    if not words or not kjv_words:
        return body, 0
    src = map_words(kjv_words, list(zip(words, [False] * len(words))))
    repl = []
    for j, ki in src.items():
        if words[j] == "said" and norm(kjv_words[ki][0]) == "saith":
            repl.append(j)
    if not repl:
        return body, 0

    expected = list(words)
    for j in repl:
        expected[j] = "says"
    for j in sorted(repl, reverse=True):
        start, end = spans[j]
        tok = body[start:end]
        lo, hi = core_span(tok)
        new = "Says" if tok[:1].isupper() else "says"
        body = body[:start + lo] + new + body[start + hi:]

    got, _, _ = tokenize(body)
    if got != expected:
        raise RuntimeError(
            "contrôle interne échoué : %r != %r" % (got, expected))
    if len(re.findall(r"\\add(?!\*)", body)) != len(re.findall(r"\\add\*", body)):
        raise RuntimeError("marques \\add déséquilibrées dans : %r" % body)
    return body, len(repl)


def verify(body, kjv_words):
    """Contrôle final sur la sortie : chaque « saith » de la KJV doit
    correspondre à un « says » de l'AKJV, et plus aucun « said » de l'AKJV ne
    doit correspondre à un « saith ». Renvoie le nombre d'écarts."""
    words, _, _ = tokenize(body)
    if not words or not kjv_words:
        return 0
    src = map_words(kjv_words, list(zip(words, [False] * len(words))))
    by_kjv = {}
    for j, ki in src.items():
        by_kjv.setdefault(ki, []).append(j)
    bad = 0
    for ki, (w, _it) in enumerate(kjv_words):
        if norm(w) == "saith":
            js = by_kjv.get(ki)
            if not js or any(words[j] != "says" for j in js):
                bad += 1
    return bad


# ---------------------------------------------------------------------------
# Traitement d'un livre AKJV : seuls les versets peuvent changer.
# ---------------------------------------------------------------------------
def process_book(code, akjv_lines, kjv_verses, report, stats):
    """akjv_lines : lignes brutes du fichier USFM AKJV (avec fins de ligne)."""
    out = []
    curc = None
    for line in akjv_lines:
        stripped = line.strip()
        m = re.match(r"^\\c (\d+)", stripped)
        if m:
            curc = int(m.group(1))
            out.append(line)
            continue
        m = re.match(r"^\\v (\d+) (.*)$", stripped)
        if m:
            vs = int(m.group(1))
            key = (curc, vs)
            body = m.group(2)
            kjv_words = kjv_verses.get(key)
            if kjv_words is None:
                stats["skipped"] += 1
                if report is not None:
                    report.write("%s\t%s\tverset KJV absent\n"
                                 % (code, ".".join(map(str, key))))
                out.append(line)
                continue
            stats["verses"] += 1
            new_body, nb = rewrite(body, kjv_words)
            if nb:
                stats["changed"] += 1
                stats["words"] += nb
                if report is not None:
                    report.write("%s\t%s\t%d mot(s) remplacé(s)\n"
                                 % (code, ".".join(map(str, key)), nb))
            bad = verify(new_body, kjv_words)
            if bad:
                stats["verify_bad"] += bad
                stats["verify_refs"].append(
                    "%s %s (%d écart(s))" % (code, ".".join(map(str, key)), bad))
            out.append("\\v %d %s\n" % (vs, new_body))
            continue
        out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Remplace « said » par « says » dans le texte AKJV "
                    "(italique ou non) quand le mot KJV correspondant est "
                    "« saith ».")
    ap.add_argument("-i", "--input", default=None,
                    help="archive AKJV avec italiques (défaut : "
                         "akjv-with-italics-usfm.zip)")
    ap.add_argument("--kjv", default=None,
                    help="archive KJV 2006 (défaut : "
                         "../../kjv/eng-kjv2006_usfm.zip)")
    ap.add_argument("-o", "--output",
                    default="akjv-with-italics-says-usfm.zip",
                    help="fichier .zip (défaut : "
                         "akjv-with-italics-says-usfm.zip), fichier .usfm "
                         "(avec --single) ou dossier (avec --no-zip)")
    ap.add_argument("--no-zip", action="store_true",
                    help="écrire les fichiers USFM dans un dossier au lieu "
                         "d'un .zip")
    ap.add_argument("--single", action="store_true",
                    help="tout écrire dans un seul fichier")
    ap.add_argument("--report", metavar="FICHIER",
                    help="écrire un rapport des versets modifiés (et des "
                         "versets sans contrepartie KJV)")
    ap.add_argument("--quiet", action="store_true",
                    help="ne rien afficher d'autre que l'issue")
    args = ap.parse_args()

    in_path = args.input or os.path.join(_ITALICS_DIR,
                                         "akjv-with-italics-usfm.zip")
    kjv_path = args.kjv or os.path.join(SCRIPT_DIR, "..", "..", "kjv",
                                        "eng-kjv2006_usfm.zip")

    if not os.path.exists(in_path):
        raise SystemExit("Fichier introuvable : %s" % in_path)
    if not os.path.exists(kjv_path):
        raise SystemExit("Fichier introuvable : %s" % kjv_path)

    with zipfile.ZipFile(in_path) as zin:
        with zipfile.ZipFile(kjv_path) as zkv:
            kjv_books = {}
            for fname in zkv.namelist():
                if not fname.lower().endswith(".usfm"):
                    continue
                curc = None
                for line in zkv.read(fname).decode("utf-8").splitlines():
                    line = line.strip()
                    m = re.match(r"^\\id ([A-Z0-9]{3})", line)
                    if m:
                        code = m.group(1)
                        kjv_books.setdefault(code, {})
                        continue
                    m = re.match(r"^\\c (\d+)", line)
                    if m:
                        curc = int(m.group(1))
                        continue
                    m = re.match(r"^\\v (\d+) (.*)$", line)
                    if m:
                        kjv_books[code][(curc, int(m.group(1)))] = \
                            kjv_parse(m.group(2))

            report = open(args.report, "w", encoding="utf-8",
                          newline="\n") if args.report else None
            if report is not None:
                report.write("# livre\tchapitre.verset\tdétail\n")

            entries, chunks = [], []
            stats = {"verses": 0, "changed": 0, "words": 0, "skipped": 0,
                     "verify_bad": 0, "verify_refs": []}
            for fname in sorted(zin.namelist()):
                if not fname.lower().endswith(".usfm"):
                    continue
                mf = re.match(r"^(\d+)-([A-Z0-9]+)\.usfm$", fname)
                code = mf.group(2) if mf else "???"
                lines = zin.read(fname).decode("utf-8").splitlines(True)
                new_lines = process_book(code, lines,
                                         kjv_books.get(code, {}),
                                         report, stats)
                content = "".join(new_lines)
                if args.single:
                    chunks.append(content)
                else:
                    entries.append((fname, content))

            if report is not None:
                report.close()

            if stats["verify_bad"]:
                raise SystemExit(
                    "contrôle final échoué : %d écart(s), ex. %s"
                    % (stats["verify_bad"], ", ".join(stats["verify_refs"][:5])))

            if args.single:
                out_path = args.output or "akjv-with-italics-says.usfm"
                if not out_path.lower().endswith((".usfm", ".sfm")):
                    out_path = os.path.join(out_path,
                                            "akjv-with-italics-says.usfm")
                os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n".join(chunks))
                written = [os.path.basename(out_path)]
            elif args.no_zip:
                out_path = args.output or "akjv-with-italics-says"
                os.makedirs(out_path, exist_ok=True)
                for fname, content in entries:
                    with open(os.path.join(out_path, fname), "w",
                              encoding="utf-8", newline="\n") as fh:
                        fh.write(content)
                written = [f for f, _ in entries]
            else:
                out_path = args.output or "akjv-with-italics-says-usfm.zip"
                if not out_path.lower().endswith(".zip"):
                    out_path += ".zip"
                with zipfile.ZipFile(out_path, "w",
                                     zipfile.ZIP_DEFLATED) as zf:
                    for fname, content in entries:
                        zf.writestr(fname, content)
                written = [f for f, _ in entries]

    if not args.quiet:
        print("%d livre(s), %d verset(s) -> %s"
              % (len(entries) if entries else 1, stats["verses"], out_path))
        for f in written:
            print("  " + f)
        print("  %d mot(s) remplacé(s) dans %d verset(s) — contrôle : OK"
              % (stats["words"], stats["changed"]))
        if stats["skipped"]:
            print("  %d verset(s) AKJV sans contrepartie KJV" % stats["skipped"],
                  file=sys.stderr)


if __name__ == "__main__":
    main()
