#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
add_italics.py — reporte les italiques de la KJV 2006 sur le texte AKJV.

L'AKJV (American King James Version) ne marque pas les mots ajoutés par le
traducteur (les mots en italique de la KJV). Ce script reprend les marques
d'italique (\add … \add*) des fichiers USFM de la KJV 2006
(eng-kjv2006_usfm.zip) et les projette sur le texte USFM de l'AKJV
(akjv-usfm.zip), en tenant compte des modernisations opérées par l'AKJV
(art→are, thou→you, cometh→comes, upon→on, …).

Usage :
    python3 add_italics.py                        # -> akjv-with-italics-usfm.zip
    python3 add_italics.py -o out.zip             # zip nommé « out.zip »
    python3 add_italics.py --no-zip -o usfm/      # dossier
    python3 add_italics.py --single -o akjv.usfm  # un seul fichier
    python3 add_italics.py --report rapport.tsv   # compte-rendu des écarts
"""

import argparse
import difflib
import os
import re
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Balisage de la KJV 2006 : une marque USFM commence par \ suivi d'un nom.
# ---------------------------------------------------------------------------
MARK = re.compile(r"\\([A-Za-z+][A-Za-z0-9+*]*)")

# Marques qui marquent une plage d'italique (mots « ajoutés » par le
# traducteur). La KJV 2006 utilise \add … \add* et \+add … \+add* (ce dernier
# à l'intérieur des paroles du Christ, \wj … \wj*).
ADD_OPEN = ("add", "+add")
ADD_CLOSE = ("add*", "+add*")
# Marques dont le contenu fait partie du texte (mots, nom divin, …).
KEEP = ("w", "wj", "nd", "+w", "tl", "k", "xt", "+nd", "nd")
KEEP_CLOSE = ("w*", "wj*", "nd*", "+w*", "tl*", "k*", "xt*", "+nd*")


def kjv_parse(body):
    """Décode le corps d'un verset KJV en une liste de mots.

    Renvoie une liste de tuples (mot brut, italique). Les marques Strong
    (\w … \w*), le nom divin (\nd … \nd*), les paroles du Christ
    (\wj … \wj*) et les notes (\f … \f*) sont éliminées.
    """
    toks = []
    i, n = 0, len(body)
    italic = False
    wmode = False
    while i < n:
        c = body[i]
        if c == "\\":
            m = MARK.match(body, i)
            if not m:
                toks.append(("\\", italic))
                i += 1
                continue
            name = m.group(1)
            i = m.end()
            if name == "f":
                depth = 1
                while i < n and depth:
                    mm = MARK.match(body, i)
                    if mm:
                        nn = mm.group(1)
                        if nn == "f":
                            depth += 1
                        elif nn == "f*":
                            depth -= 1
                        i = mm.end()
                    else:
                        i += 1
                continue
            if name == "f*":
                continue
            if name in ADD_OPEN:
                italic = True
                continue
            if name in ADD_CLOSE:
                italic = False
                continue
            if name in ("w", "+w"):
                wmode = True
                continue
            if name in ("w*", "+w*"):
                wmode = False
                continue
            # Autres marques (\p, \q1, \c, \v, …) : aucun texte à conserver.
            continue
        if wmode and c == "|":
            # Attribut (\w mot|strong="H1234") : à ignorer jusqu'à la marque
            # de fermeture.
            while i < n and body[i] != "\\":
                i += 1
            continue
        if c == "\u00b6":            # ¶ (début de paragraphe KJV)
            i += 1
            continue
        toks.append((c, italic))
        i += 1

    words = []
    curw, curit = [], False
    for ch, it in toks:
        if ch.isspace():
            if curw:
                words.append(("".join(curw), curit))
                curw, curit = [], False
        else:
            curw.append(ch)
            curit = curit or it
    if curw:
        words.append(("".join(curw), curit))
    return words


# ---------------------------------------------------------------------------
# Formes modernisées : l'AKJV remplace les formes archaïques de la KJV.
# ---------------------------------------------------------------------------
SPECIAL = {
    "art": ["are"], "thou": ["you"], "ye": ["you"], "thee": ["you"],
    "thy": ["your"], "thine": ["your", "yours"], "thyself": ["yourself"],
    "hath": ["has"], "hast": ["have"], "doth": ["does"], "saith": ["says", "said"],
    "doeth": ["does"], "goeth": ["goes"], "wilt": ["will"], "shalt": ["shall"],
    "wast": ["were"], "wert": ["were"], "canst": ["can"], "mine": ["my", "mine"],
    "unto": ["to"], "upon": ["on"], "withal": ["with"],
    "yea": ["yea", "yes"], "nay": ["nay", "no"], "whence": ["whence"],
    "thence": ["there", "thence"], "hither": ["here"], "whoso": ["who", "whoever"],
    "wherefore": ["why", "wherefore"], "wherewith": ["wherewith"],
    "pulse": ["vegetables", "pulse"],
    "whatsoever": ["whatever", "whatsoever"],
    "morter": ["mortar"], "carcases": ["carcasses", "carcases"],
    "odours": ["odors", "odours"], "armour": ["armor", "armour"],
    "vail": ["veil"], "enquire": ["inquire", "enquire"],
    "enquired": ["inquired", "enquired"], "shewed": ["showed", "shewed"],
    "shewing": ["showing", "shewing"], "fulfil": ["fulfill", "fulfil"],
    "spake": ["spoke"], "baken": ["baked"], "dwelt": ["dwelled", "dwelt"],
    "nought": ["nought", "nothing"], "verily": ["verily", "truly"],
    "ish-bosheth": ["ishbosheth", "ish-bosheth"],
    "epistle": ["letter", "epistle"],
}
# Deuxième personne du singulier (thou …-est) -> forme moderne.
EST_SPECIAL = {
    "gavest": ["gave"], "saidst": ["said"], "sayest": ["say"],
    "shewest": ["show"], "meanest": ["mean"], "comest": ["come"],
    "bearest": ["bear", "bore"], "belongest": ["belong"],
}
# Archaïsmes rendus par plusieurs mots dans l'AKJV : toutes les formes doivent
# passer en italique ensemble.
PHRASES = {
    "whence": ["from", "where"],
    "wherewith": ["with", "which"],
    "henceforth": ["from", "now", "on"],
    "forasmuch": ["for", "as", "much"],
}


def _thirdsg(base):
    """3e personne du singulier moderne d'un infinitif donné (come→comes)."""
    if not base:
        return []
    if base in ("do", "doe"):
        return ["does"]
    if base in ("go", "goe"):
        return ["goes"]
    if base in ("have", "hav"):
        return ["has"]
    if base == "say":
        return ["says"]
    if base.endswith(("s", "x", "z", "ch", "sh", "o")):
        return [base + "es"]
    if base.endswith("y") and len(base) > 1 and base[-2] not in "aeiou":
        return [base[:-1] + "ies"]
    return [base + "s"]


def _modern_verbs(word):
    """Formes modernes des verbes KJV en -eth/-th (3e p.) et -est (2e p.)."""
    out = []
    if word.endswith(("eth", "th")):
        bases = []
        if word.endswith("eth"):
            bases.append(word[:-3])          # doeth -> do
        if word.endswith("th"):
            bases.append(word[:-2])          # maketh -> make
        if word.endswith("teth"):
            bases.append(word[:-4])          # sitteth -> sit
        for b in bases:
            out.extend(_thirdsg(b))
    if word.endswith("est") and len(word) > 3:
        base = word[:-3]                     # meanest -> mean
        out.append(base)
        if base == "shew":
            out.append("show")
    return out


def modernize(word):
    """Candidats (formes normalisées) de la traduction AKJV d'un mot KJV.

    Renvoie une liste de mots AKJV plausibles pour un mot KJV donné
    (archaïsme ou variante orthographique). Le mot lui-même est toujours
    proposé.
    """
    n = norm(word)
    cands = [n]
    if n in SPECIAL:
        cands.extend(SPECIAL[n])
    if n in EST_SPECIAL:
        cands.extend(EST_SPECIAL[n])
    cands.extend(_modern_verbs(n))
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def norm(word):
    """Normalise un mot : minuscules, apostrophe droite, ponctuation ôtée."""
    word = word.replace("\u2019", "'")
    return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word).lower()


# ---------------------------------------------------------------------------
# Lecture des deux archives.
# ---------------------------------------------------------------------------
def read_books_akjv(zf):
    """zip KJV -> dict code -> dict (chapitre, verset) -> texte brut."""
    books = {}
    for fname in zf.namelist():
        if not fname.lower().endswith(".usfm"):
            continue
        curc = None
        for line in zf.read(fname).decode("utf-8").splitlines():
            line = line.strip()
            m = re.match(r"^\\id ([A-Z0-9]{3})", line)
            if m:
                code = m.group(1)
                books.setdefault(code, {})
                continue
            m = re.match(r"^\\c (\d+)", line)
            if m:
                curc = int(m.group(1))
                continue
            m = re.match(r"^\\v (\d+) (.*)$", line)
            if m:
                books[code][(curc, int(m.group(1)))] = m.group(2)
    return books


def read_books_kjv(zf):
    """zip AKJV -> dict code -> dict (chapitre, verset) -> [(mot, italique)]."""
    books = {}
    for fname in zf.namelist():
        if not fname.lower().endswith(".usfm"):
            continue
        curc = None
        for line in zf.read(fname).decode("utf-8").splitlines():
            line = line.strip()
            m = re.match(r"^\\id ([A-Z0-9]{3})", line)
            if m:
                code = m.group(1)
                books.setdefault(code, {})
                continue
            m = re.match(r"^\\c (\d+)", line)
            if m:
                curc = int(m.group(1))
                continue
            m = re.match(r"^\\v (\d+) (.*)$", line)
            if m:
                books[code][(curc, int(m.group(1)))] = kjv_parse(m.group(2))
    return books


# ---------------------------------------------------------------------------
# Alignement d'un verset et marquage des italiques.
# ---------------------------------------------------------------------------
_LEAD_PUNCT = re.compile(r"^[^A-Za-z0-9']+")
_TRAIL_PUNCT = re.compile(r"[^A-Za-z0-9']+$")


def _strip_punct(word):
    """Sépare la ponctuation collée aux bords d'un mot (l'apostrophe
    ' reste dans le mot) et renvoie (ponctuation avant, mot, ponctuation après)."""
    lead = _LEAD_PUNCT.match(word).group(0) if _LEAD_PUNCT.match(word) else ""
    tail = _TRAIL_PUNCT.search(word).group(0) if _TRAIL_PUNCT.search(word) else ""
    end = len(word) - len(tail) if tail else len(word)
    return lead, word[len(lead):end], tail


def render_run(run):
    """Écrit une suite de mots en italique en sortant la ponctuation des
    bords du balisage, en gardant groupés les mots consécutifs sans
    ponctuation, et en préservant les espaces simples du texte."""
    out, cur, cur_lead = [], [], ""
    def flush(tail=""):
        nonlocal cur, cur_lead
        if cur:
            out.append(cur_lead + r"\add %s\add*" % " ".join(cur) + tail)
        elif tail:
            out.append(tail)
        cur, cur_lead = [], ""
    for k, w in enumerate(run):
        lead, stem, tail = _strip_punct(w)
        if not stem:                                   # mot purement ponctué
            flush()
            if out:
                out.append(" ")
            out.append(lead + tail)
            continue
        if lead and cur:                               # ponctuation avant -> coupure
            flush()
            if out:
                out.append(" ")
            cur_lead = lead
        elif not cur:                                  # début de suite
            if out:
                out.append(" ")
            cur_lead = lead
        cur.append(stem)
        if tail:                                       # ponctuation après -> fin de suite
            flush(tail)
    flush()
    return "".join(out)


def align_verse(kjv_words, akjv_text):
    """Renvoie le texte AKJV du verset, muni des \add … \add*.

    kjv_words : liste de (mot, italique) de la KJV ;
    akjv_text : texte brut du verset AKJV.
    """
    akjv_raw = akjv_text.split()
    if not kjv_words:
        return akjv_text
    a = [norm(w) for w, _ in kjv_words]
    b = [norm(w) for w in akjv_raw]
    a_len, b_len = len(a), len(b)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)

    # Passe 0 : archaïsmes rendus par plusieurs mots (whence -> "from where",
    # forasmuch -> "for as much"…). Les positions visées sont réservées avant
    # la passe 1 pour que celle-ci ne leur associe pas un mot isolé commun
    # (ex. « as » de "for as much").
    akjv_italic = set()
    phrase_used = set()
    for ki, (w, it) in enumerate(kjv_words):
        if not it:
            continue
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
                akjv_italic.add(best_p + k)
                phrase_used.add(best_p + k)

    # Passe 1 : correspondance exacte des blocs communs.
    used = [False] * len(b)
    orphaned = set()
    for i, j, size in sm.get_matching_blocks():
        for k in range(size):
            if j + k in phrase_used:
                orphaned.add(i + k)
                continue
            if kjv_words[i + k][1]:       # mot KJV en italique
                akjv_italic.add(j + k)
            used[j + k] = True

    # Passe 2 : mots italiques KJV dont l'équivalent exact n'existe pas dans
    # l'AKJV (modernisations art/are, thou/you, -eth/-s…). On cherche la
    # forme moderne correspondante dans l'écart d'alignement voisin.
    unmatched = [not u for u in used]
    for ki, (w, it) in enumerate(kjv_words):
        if not it:
            continue
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
        if phrase:                                # rendu sur plusieurs mots
            plen = len(phrase)
            plo = max(0, int(expected) - 3)
            phi = min(b_len - plen + 1, int(expected) + 4)
            best_p = None
            for j in range(plo, phi):
                if all(not used[j + k] and (j + k) not in akjv_italic
                       and b[j + k] == phrase[k] for k in range(plen)):
                    if best_p is None or abs(j - expected) < abs(best_p - expected):
                        best_p = j
            if best_p is not None:
                for k in range(plen):
                    akjv_italic.add(best_p + k)
                continue
        cands = set(modernize(w))
        best, best_d = None, None
        lo = max(0, int(expected) - 3)
        hi = min(b_len, int(expected) + 4)
        for j in range(lo, hi):
            if not unmatched[j] or j in akjv_italic:
                continue
            if b[j] in cands:
                d = abs(j - expected)
                if best is None or d < best_d:
                    best, best_d = j, d
        if best is not None:
            akjv_italic.add(best)

    # Reconstruction avec regroupement des italiques consécutifs.
    # La ponctuation collée aux bords d'un mot sort du balisage \add … \add*
    # (l'apostrophe ' reste attachée au mot) ; un mot du milieu d'une suite
    # qui porte une ponctuation impose une coupure de la suite.
    parts, i = [], 0
    while i < len(akjv_raw):
        if i in akjv_italic:
            j = i
            while j < len(akjv_raw) and j in akjv_italic:
                j += 1
            parts.append(render_run(akjv_raw[i:j]))
            i = j
        else:
            parts.append(akjv_raw[i])
            i += 1
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Traitement d'un livre AKJV : seul le texte des versets change.
# ---------------------------------------------------------------------------
def process_book(code, akjv_lines, kjv_verses, report):
    """akjv_lines : lignes brutes du fichier USFM AKJV (avec fins de ligne)."""
    out = []
    curc = None
    mapped = skipped = 0
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
            kw = kjv_verses.get(key)
            if kw is None:
                skipped += 1
                if report is not None:
                    report.write("%s\t%s\tverset KJV absent\n"
                                 % (code, ".".join(map(str, key))))
                out.append(line)
                continue
            body = m.group(2)
            new_body = align_verse(kw, body)
            mapped += 1
            out.append("\\v %d %s\n" % (vs, new_body))
            continue
        out.append(line)
    return out, mapped, skipped


def main():
    ap = argparse.ArgumentParser(
        description="Reporte les italiques (\\add) de la KJV 2006 sur le "
                    "texte USFM de l'AKJV.")
    ap.add_argument("--akjv", default=None,
                    help="archive USFM AKJV (défaut : "
                         "../1. convert-to-UFSM/akjv-usfm.zip)")
    ap.add_argument("--kjv", default=None,
                    help="archive USFM KJV 2006 (défaut : "
                         "../../kjv/eng-kjv2006_usfm.zip)")
    ap.add_argument("-o", "--output", default="akjv-with-italics-usfm.zip",
                    help="fichier .zip (défaut : "
                         "akjv-with-italics-usfm.zip), fichier .usfm (avec "
                         "--single) ou dossier (avec --no-zip)")
    ap.add_argument("--no-zip", action="store_true",
                    help="écrire les fichiers USFM dans un dossier au lieu "
                         "d'un .zip")
    ap.add_argument("--single", action="store_true",
                    help="tout écrire dans un seul fichier")
    ap.add_argument("--report", metavar="FICHIER",
                    help="écrire un rapport des versets sans contrepartie KJV")
    ap.add_argument("--quiet", action="store_true",
                    help="ne rien afficher d'autre que l'issue")
    args = ap.parse_args()

    akjv_path = args.akjv or os.path.join(
        SCRIPT_DIR, "..", "1. convert-to-UFSM", "akjv-usfm.zip")
    kjv_path = args.kjv or os.path.join(
        SCRIPT_DIR, "..", "..", "kjv", "eng-kjv2006_usfm.zip")

    if not os.path.exists(akjv_path):
        raise SystemExit("Fichier introuvable : %s" % akjv_path)
    if not os.path.exists(kjv_path):
        raise SystemExit("Fichier introuvable : %s" % kjv_path)

    with zipfile.ZipFile(akjv_path) as zak:
        with zipfile.ZipFile(kjv_path) as zkv:
            akjv_books = read_books_akjv(zak)
            kjv_books = read_books_kjv(zkv)

            report = open(args.report, "w", encoding="utf-8",
                          newline="\n") if args.report else None
            if report is not None:
                report.write("# livre\tchapitre.verset\tdétail\n")

            entries, chunks = [], []
            total_mapped = total_skipped = 0
            for fname in sorted(zak.namelist()):
                if not fname.lower().endswith(".usfm"):
                    continue
                mf = re.match(r"^(\d+)-([A-Z0-9]+)\.usfm$", fname)
                code = mf.group(2) if mf else "???"
                lines = zak.read(fname).decode("utf-8").splitlines(True)
                kv = kjv_books.get(code, {})
                new_lines, mapped, skipped = process_book(
                    code, lines, kv, report)
                total_mapped += mapped
                total_skipped += skipped
                content = "".join(new_lines)
                if args.single:
                    chunks.append(content)
                else:
                    entries.append((fname, content))

            if report is not None:
                report.close()

            if args.single:
                out_path = args.output or "akjv-with-italics.usfm"
                if not out_path.lower().endswith((".usfm", ".sfm")):
                    out_path = os.path.join(out_path, "akjv-with-italics.usfm")
                os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n".join(chunks))
                written = [os.path.basename(out_path)]
            elif args.no_zip:
                out_path = args.output or "akjv-with-italics"
                os.makedirs(out_path, exist_ok=True)
                for fname, content in entries:
                    with open(os.path.join(out_path, fname), "w",
                              encoding="utf-8", newline="\n") as fh:
                        fh.write(content)
                written = [f for f, _ in entries]
            else:
                out_path = args.output or "akjv-with-italics-usfm.zip"
                if not out_path.lower().endswith(".zip"):
                    out_path += ".zip"
                with zipfile.ZipFile(out_path, "w",
                                     zipfile.ZIP_DEFLATED) as zf:
                    for fname, content in entries:
                        zf.writestr(fname, content)
                written = [f for f, _ in entries]

    if not args.quiet:
        print("%d livre(s), %d verset(s) -> %s"
              % (len(entries) if entries else 1, total_mapped, out_path))
        for f in written:
            print("  " + f)
        if total_skipped:
            print("  %d verset(s) AKJV sans contrepartie KJV" % total_skipped,
                  file=sys.stderr)


if __name__ == "__main__":
    main()
