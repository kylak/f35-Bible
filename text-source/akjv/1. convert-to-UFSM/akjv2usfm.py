#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
akjv2usfm.py — convertit la Bible American King James Version (AKJV)
au format USFM 3.0.

Le fichier source est un texte plat tel que celui fourni sur
creationism.org/BibleAKJV/ (« AkjvAllIn1Text.txt ») : chaque verset
occupe une ligne « C:V texte », les chapitres sont annoncés par des
titres (« Genesis, chapter 1 », sinon « ++Isaiah 2 » dans Ésaïe) et
les livres par des titres « The Book of … ». Quelques versets sont
coupés sur deux lignes ; le script recoud ces suites au verset
précédent.

Usage :
    python3 akjv2usfm.py SOURCE.txt                       # -> akjv-usfm.zip
    python3 akjv2usfm.py SOURCE.txt -o out.zip            # zip nommé « out.zip »
    python3 akjv2usfm.py SOURCE.txt -o usfm --no-zip      # dossier « usfm/ »
    python3 akjv2usfm.py SOURCE.txt --paratext            # noms Paratext dans le zip
    python3 akjv2usfm.py SOURCE.txt --single              # un seul fichier akjv.usfm
    python3 akjv2usfm.py SOURCE.txt --psalms-poetry       # \\q1 dans les Psaumes
    python3 akjv2usfm.py SOURCE.txt --report rapport.tsv  # lignes hors-texte
"""

import argparse
import os
import re
import sys
import zipfile

# ---------------------------------------------------------------------------
# Table des livres : nom source (titres de chapitre) -> USFM.
# (code source, titre du livre « The Book of … », n° USFM, ID, nom anglais,
#  abréviation, titre long)
# ---------------------------------------------------------------------------
BOOKS = [
    ("Genesis",           "The Book of Genesis",           1,  "GEN", "Genesis",           "Gen", "The First Book of Moses, called Genesis"),
    ("Exodus",            "The Book of Exodus",            2,  "EXO", "Exodus",            "Exo", "The Second Book of Moses, called Exodus"),
    ("Leviticus",         "The Book of Leviticus",         3,  "LEV", "Leviticus",         "Lev", "The Third Book of Moses, called Leviticus"),
    ("Numbers",           "The Book of Numbers",           4,  "NUM", "Numbers",           "Num", "The Fourth Book of Moses, called Numbers"),
    ("Deuteronomy",       "The Book of Deuteronomy",       5,  "DEU", "Deuteronomy",       "Deu", "The Fifth Book of Moses, called Deuteronomy"),
    ("Joshua",            "The Book of Joshua",            6,  "JOS", "Joshua",            "Jos", "The Book of Joshua"),
    ("Judges",            "The Book of Judges",            7,  "JDG", "Judges",            "Jdg", "The Book of Judges"),
    ("Ruth",              "The Book of Ruth",              8,  "RUT", "Ruth",              "Rut", "The Book of Ruth"),
    ("I Samuel",          "The Book of I Samuel",          9,  "1SA", "1 Samuel",          "1Sa", "The First Book of Samuel Otherwise Called the First Book of the Kings"),
    ("II Samuel",         "The Book of II Samuel",         10, "2SA", "2 Samuel",          "2Sa", "The Second Book of Samuel Otherwise Called the Second Book of the Kings"),
    ("I Kings",           "The Book of I Kings",           11, "1KI", "1 Kings",           "1Ki", "The First Book of the Kings, Commonly Called the Third Book of the Kings"),
    ("II Kings",          "The Book of II Kings",          12, "2KI", "2 Kings",           "2Ki", "The Second Book of the Kings, Commonly Called the Fourth Book of the Kings"),
    ("I Chronicles",      "The Book of I Chronicles",      13, "1CH", "1 Chronicles",      "1Ch", "The First Book of the Chronicles"),
    ("II Chronicles",     "The Book of II Chronicles",     14, "2CH", "2 Chronicles",      "2Ch", "The Second Book of the Chronicles"),
    ("Ezra",              "The Book of Ezra",              15, "EZR", "Ezra",              "Ezr", "Ezra"),
    ("Nehemiah",          "The Book of Nehemiah",          16, "NEH", "Nehemiah",          "Neh", "The Book of Nehemiah"),
    ("Esther",            "The Book of Esther",            17, "EST", "Esther",            "Est", "The Book of Esther"),
    ("Job",               "The Book of Job",               18, "JOB", "Job",               "Job", "The Book of Job"),
    ("Psalm",             "The Book of Psalms",            19, "PSA", "Psalms",            "Psa", "The Book of Psalms"),
    ("Proverbs",          "The Book of Proverbs",          20, "PRO", "Proverbs",          "Pro", "The Proverbs"),
    ("Ecclesiastes",      "The Book of Ecclesiastes",      21, "ECC", "Ecclesiastes",      "Ecc", "Ecclesiastes, or the Preacher"),
    ("Song of Solomon",   "The Book of Song of Songs",     22, "SNG", "Song of Solomon",   "Sng", "The Song of Solomon"),
    ("Isaiah",            "The Book of Isaiah",            23, "ISA", "Isaiah",            "Isa", "The Book of the Prophet Isaiah"),
    ("Jeremiah",          "The Book of Jeremiah",          24, "JER", "Jeremiah",          "Jer", "The Book of the Prophet Jeremiah"),
    ("Lamentations",      "The Book of Lamentations",      25, "LAM", "Lamentations",      "Lam", "The Lamentations of Jeremiah"),
    ("Ezekiel",           "The Book of Ezekiel",           26, "EZK", "Ezekiel",           "Ezk", "The Book of the Prophet Ezekiel"),
    ("Daniel",            "The Book of Daniel",            27, "DAN", "Daniel",            "Dan", "The Book of Daniel"),
    ("Hosea",             "The Book of Hosea",             28, "HOS", "Hosea",             "Hos", "Hosea"),
    ("Joel",              "The Book of Joel",              29, "JOL", "Joel",              "Jol", "Joel"),
    ("Amos",              "The Book of Amos",              30, "AMO", "Amos",              "Amo", "Amos"),
    ("Obadiah",           "The Book of Obadiah",           31, "OBA", "Obadiah",           "Oba", "Obadiah"),
    ("Jonah",             "The Book of Jonah",             32, "JON", "Jonah",             "Jon", "Jonah"),
    ("Micah",             "The Book of Micah",             33, "MIC", "Micah",             "Mic", "Micah"),
    ("Nahum",             "The Book of Nahum",             34, "NAM", "Nahum",             "Nam", "Nahum"),
    ("Habakkuk",          "The Book of Habakkuk",          35, "HAB", "Habakkuk",          "Hab", "Habakkuk"),
    ("Zephaniah",         "The Book of Zephaniah",         36, "ZEP", "Zephaniah",         "Zep", "Zephaniah"),
    ("Haggai",            "The Book of Haggai",            37, "HAG", "Haggai",            "Hag", "Haggai"),
    ("Zechariah",         "The Book of Zechariah",         38, "ZEC", "Zechariah",         "Zec", "Zechariah"),
    ("Malachi",           "The Book of Malachi",           39, "MAL", "Malachi",           "Mal", "Malachi"),
    ("Matthew",           "The Book of Matthew",           41, "MAT", "Matthew",           "Mat", "The Gospel According to Matthew"),
    ("Mark",              "The Book of Mark",              42, "MRK", "Mark",              "Mrk", "The Gospel According to Mark"),
    ("Luke",              "The Book of Luke",              43, "LUK", "Luke",              "Luk", "The Gospel According to Luke"),
    ("John",              "The Book of John",              44, "JHN", "John",              "Jhn", "The Gospel According to John"),
    ("Acts",              "The Book of Acts",              45, "ACT", "Acts",              "Act", "The Acts of the Apostles"),
    ("Romans",            "The Book of Romans",            46, "ROM", "Romans",            "Rom", "The Epistle of Paul the Apostle to the Romans"),
    ("I Corinthians",     "The Book of I Corinthians",     47, "1CO", "1 Corinthians",     "1Co", "The First Epistle of Paul the Apostle to the Corinthians"),
    ("II Corinthians",    "The Book of II Corinthians",    48, "2CO", "2 Corinthians",     "2Co", "The Second Epistle of Paul the Apostle to the Corinthians"),
    ("Galatians",         "The Book of Galatians",         49, "GAL", "Galatians",         "Gal", "The Epistle of Paul the Apostle to the Galatians"),
    ("Ephesians",         "The Book of Ephesians",         50, "EPH", "Ephesians",         "Eph", "The Epistle of Paul the Apostle to the Ephesians"),
    ("Philippians",       "The Book of Philippians",       51, "PHP", "Philippians",       "Php", "The Epistle of Paul the Apostle to the Philippians"),
    ("Colossians",        "The Book of Colossians",        52, "COL", "Colossians",        "Col", "The Epistle of Paul the Apostle to the Colossians"),
    ("I Thessalonians",   "The Book of I Thessalonians",   53, "1TH", "1 Thessalonians",   "1Th", "The First Epistle of Paul the Apostle to the Thessalonians"),
    ("II Thessalonians",  "The Book of II Thessalonians",  54, "2TH", "2 Thessalonians",   "2Th", "The Second Epistle of Paul the Apostle to the Thessalonians"),
    ("I Timothy",         "The Book of I Timothy",         55, "1TI", "1 Timothy",         "1Ti", "The First Epistle of Paul the Apostle to Timothy"),
    ("II Timothy",        "The Book of II Timothy",        56, "2TI", "2 Timothy",         "2Ti", "The Second Epistle of Paul the Apostle to Timothy"),
    ("Titus",             "The Book of Titus",             57, "TIT", "Titus",             "Tit", "The Epistle of Paul the Apostle to Titus"),
    ("Philemon",          "The Book of Philemon",          58, "PHM", "Philemon",          "Phm", "The Epistle of Paul the Apostle to Philemon"),
    ("Hebrews",           "The Book of Hebrews",           59, "HEB", "Hebrews",           "Heb", "The Epistle of Paul the Apostle to the Hebrews"),
    ("James",             "The Book of James",             60, "JAS", "James",             "Jas", "The General Epistle of James"),
    ("I Peter",           "The Book of I Peter",           61, "1PE", "1 Peter",           "1Pe", "The First Epistle General of Peter"),
    ("II Peter",          "The Book of II Peter",          62, "2PE", "2 Peter",           "2Pe", "The Second Epistle General of Peter"),
    ("I John",            "The Book of I John",            63, "1JN", "1 John",            "1Jn", "The First Epistle General of John"),
    ("II John",           "The Book of II John",           64, "2JN", "2 John",            "2Jn", "The Second Epistle of John"),
    ("III John",          "The Book of III John",          65, "3JN", "3 John",            "3Jn", "The Third Epistle of John"),
    ("Jude",              "The Book of Jude",              66, "JUD", "Jude",              "Jud", "The General Epistle of Jude"),
    ("Revelation",        "The Book of Revelation",        67, "REV", "Revelation",        "Rev", "The Revelation of St. John the Divine"),
]
BOOKMAP = {src: (num, uid, name, abbr, toc1) for src, _bh, num, uid, name, abbr, toc1 in BOOKS}
ORDER = {src: num for src, _bh, num, *_rest in BOOKS}

# Nombre de versets par livre (source de référence : la KJV 2006, qui suit
# la même numérotation que l'AKJV). Permet de vérifier l'intégrité du
# découpage à la fin de la conversion.
EXPECTED = {
    "GEN": 1533, "EXO": 1213, "LEV": 859, "NUM": 1288, "DEU": 959,
    "JOS": 658, "JDG": 618, "RUT": 85, "1SA": 810, "2SA": 695,
    "1KI": 816, "2KI": 719, "1CH": 942, "2CH": 822, "EZR": 280,
    "NEH": 406, "EST": 167, "JOB": 1070, "PSA": 2461, "PRO": 915,
    "ECC": 222, "SNG": 117, "ISA": 1292, "JER": 1364, "LAM": 154,
    "EZK": 1273, "DAN": 357, "HOS": 197, "JOL": 73, "AMO": 146,
    "OBA": 21, "JON": 48, "MIC": 105, "NAM": 47, "HAB": 56,
    "ZEP": 53, "HAG": 38, "ZEC": 211, "MAL": 55, "MAT": 1071,
    "MRK": 678, "LUK": 1151, "JHN": 879, "ACT": 1007, "ROM": 433,
    "1CO": 437, "2CO": 257, "GAL": 149, "EPH": 155, "PHP": 104,
    "COL": 95, "1TH": 89, "2TH": 47, "1TI": 113, "2TI": 83,
    "TIT": 46, "PHM": 25, "HEB": 303, "JAS": 108, "1PE": 105,
    "2PE": 61, "1JN": 105, "2JN": 13, "3JN": 14, "JUD": 25,
    "REV": 404,
}

# Titres de livre « The Book of … » -> code source, en tenant compte des
# écarts entre le titre du livre et le nom employé dans les titres de
# chapitre (Psalms->Psalm, Song of Songs->Song of Solomon).
BOOK_HEADER = {bh: src for src, bh, *_rest in BOOKS}

# ---------------------------------------------------------------------------
# Expressions régulières du balisage plat.
# ---------------------------------------------------------------------------
VERSE_RE = re.compile(r"^(\d+):(\d+)\s+(.*)$")
CHAPTER_RE = re.compile(r"^([A-Za-z][A-Za-z ]+),\s*chapter\s+(\d+)$")
CHAPTER_ALT_RE = re.compile(r"^\+\+([A-Za-z][A-Za-z ]+)\s+(\d+)$")   # ++Isaiah 2
SEPARATOR_RE = re.compile(r"^=+")
TESTAMENT_RE = re.compile(r"^(?:Start|End) of (?:Old|New) Testament")
END_BOOK_RE = re.compile(r"^End of .+")


def read_source(path):
    """Lit le fichier source (UTF-8, insensible aux fins de ligne).

    Le fichier mêle CRLF, LF, CR et NEL ; les espaces insécables (U+00A0)
    qui ornent les lignes décoratives sont normalisées en espaces simples.
    Renvoie la liste des lignes significatives, dans l'ordre.
    """
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("Impossible de décoder le fichier source.")
    lines = []
    for l in re.split(r"\r\n|\n|\r|\x85", text):
        l = l.replace("\xa0", " ").strip()
        if l:
            lines.append(l)
    return lines


def parse(source, report=None):
    """Découpe le fichier source en versets par livre.

    Renvoie (livres, stat, ordre) où livres est un dict code -> liste de
    (chapitre, verset, texte), stat un dict de statistiques et ordre la
    liste des codes dans l'ordre d'apparition.
    """
    lines = read_source(source)
    books = {}
    order = []                       # codes dans l'ordre d'apparition
    stat = {"total_lines": len(lines), "skipped": 0, "chapters": 0,
            "verses": 0, "joined": 0}
    current = None                   # code du livre en cours
    anomalies = []
    started = False
    line_no = 0
    for line in lines:
        line_no += 1
        # 1. Séparateurs décoratifs.
        if SEPARATOR_RE.match(line):
            stat["skipped"] += 1
            continue
        # 2. Grande coupure d'Ancien/Nouveau Testament.
        if TESTAMENT_RE.match(line):
            started = started or line.startswith("Start of")
            stat["skipped"] += 1
            continue
        if not started:
            stat["skipped"] += 1
            continue
        # 3. Titre de livre « The Book of … ».
        if line in BOOK_HEADER:
            current = BOOK_HEADER[line]
            if current not in order:
                order.append(current)
            books.setdefault(current, [])
            stat["skipped"] += 1
            continue
        # 4. Titre de chapitre — deux formes, la seconde (« ++Isaiah 2 »)
        #    propre à Ésaïe.
        m = CHAPTER_RE.match(line) or CHAPTER_ALT_RE.match(line)
        if m:
            name, chap = m.group(1), int(m.group(2))
            if current is None:
                if name in BOOKMAP:
                    current = name
                    order.append(current)
                    books.setdefault(current, [])
                else:
                    anomalies.append((line_no, "livre inconnu : " + line))
                    stat["skipped"] += 1
                    continue
            stat["chapters"] += 1
            continue
        # 5. Verset « C:V texte ».
        m = VERSE_RE.match(line)
        if m:
            if current is None:
                anomalies.append((line_no, "verset avant tout livre : " + line))
                stat["skipped"] += 1
                continue
            ch, vs = int(m.group(1)), int(m.group(2))
            txt = re.sub(r"\s+", " ", m.group(3)).strip()
            books[current].append((ch, vs, txt))
            stat["verses"] += 1
            continue
        # 6. « End of … » et autres lignes d'en-tête.
        if END_BOOK_RE.match(line):
            stat["skipped"] += 1
            continue
        # 7. Tout le reste : la fin d'un verset coupé sur deux lignes
        #    (le fichier en compte quelques-unes) ; on recoud le texte au
        #    verset précédent.
        if current is not None and books[current]:
            ch, vs, txt = books[current][-1]
            books[current][-1] = (ch, vs, txt + " " + line)
            stat["joined"] += 1
            continue
        stat["skipped"] += 1

    if report is not None:
        report.write("# ligne\texception\n")
        for ln, msg in anomalies:
            report.write("%d\t%s\n" % (ln, msg))
    return books, stat, order


def build_book(src, verses, project, poetry=False, sd_workaround=False):
    """verses : liste de (chapitre, verset, texte brut) triée."""
    num, uid, name, abbr, toc1 = BOOKMAP[src]
    para = r"\q1" if (poetry and uid == "PSA") else r"\p"
    out = [r"\id %s %s" % (uid, project),
           r"\usfm 3.0",
           r"\ide UTF-8",
           r"\h %s" % name,
           r"\toc1 %s" % toc1,
           r"\toc2 %s" % name,
           r"\toc3 %s" % abbr,
           r"\mt1 %s" % toc1.upper()]
    cur_chapter = None
    first = True
    for chapter, verse, raw in verses:
        if chapter != cur_chapter:
            out.append(r"\c %d" % chapter)
            if sd_workaround and not first:
                out.append(r"\sd")
            out.append(para)
            cur_chapter = chapter
        first = False
        body = raw.strip()
        if not body:
            continue
        out.append((r"\v %d %s" % (verse, body)).rstrip())
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="Convertit la Bible American King James Version "
                    "(fichier plat) en USFM 3.0.")
    ap.add_argument("source", help="fichier texte source (AkjvAllIn1Text.txt)")
    ap.add_argument("-o", "--output", default=None,
                    help="fichier .zip (défaut : akjv-usfm.zip), fichier "
                         ".usfm (avec --single) ou dossier (avec --no-zip)")
    ap.add_argument("--no-zip", action="store_true",
                    help="écrire les fichiers USFM dans un dossier au lieu "
                         "d'un .zip")
    ap.add_argument("--project", default="American King James Version",
                    help="libellé placé après \\id")
    ap.add_argument("--paratext", action="store_true",
                    help="nommer les fichiers à la mode Paratext "
                         "(01GENAKJV.SFM)")
    ap.add_argument("--abbrev", default="AKJV",
                    help="sigle du projet pour --paratext")
    ap.add_argument("--single", action="store_true",
                    help="tout écrire dans un seul fichier")
    ap.add_argument("--psalms-poetry", action="store_true",
                    help="poser les Psaumes en vers (\\q1) plutôt qu'en "
                         "prose (\\p)")
    ap.add_argument("--sd-workaround", action="store_true",
                    help="insérer un \\sd après chaque \\c "
                         "(PTXprint <= 3.0.17)")
    ap.add_argument("--report", metavar="FICHIER",
                    help="écrire un rapport des lignes hors-texte")
    ap.add_argument("--quiet", action="store_true",
                    help="ne rien afficher d'autre que l'issue")
    args = ap.parse_args()

    report = open(args.report, "w", encoding="utf-8", newline="\n") \
        if args.report else None
    books, stat, order = parse(args.source, report)
    if report is not None:
        report.close()

    ordered = sorted(books, key=lambda c: ORDER[c])

    # Mode de sortie : par défaut un .zip de tous les livres ; --single
    # écrit un unique fichier ; --no-zip écrit un fichier par livre dans un
    # dossier.
    zip_mode = not args.no_zip and not args.single
    if args.single:
        out_path = args.output or "akjv.usfm"
        if not out_path.lower().endswith((".usfm", ".sfm")):
            out_path = os.path.join(out_path, "akjv.usfm")
    elif zip_mode:
        out_path = args.output or "akjv-usfm.zip"
        if not out_path.lower().endswith(".zip"):
            out_path += ".zip"
    else:
        out_path = args.output or "usfm"

    written, total_verses = [], 0
    chunks = []
    entries = []
    problems = []
    for code in ordered:
        verses = sorted(books[code])
        total_verses += len(verses)
        # Contrôle de continuité : les versets recommencent à 1 à chaque
        # chapitre et croissent ensuite sans trou ni doublon.
        expected = 1
        cur_chapter = None
        for (ch, vs, _t) in verses:
            if ch != cur_chapter:
                expected, cur_chapter = 1, ch
            if vs != expected:
                problems.append((code, ch, vs,
                                 "verset attendu %d" % expected))
            expected = vs + 1
        # Contrôle d'intégrité : le total doit égaler celui de la KJV.
        _num, uid, _name, _abbr, _toc1 = BOOKMAP[code]
        if uid in EXPECTED and len(verses) != EXPECTED[uid]:
            problems.append((code, None, None,
                             "total %d versets, attendu %d"
                             % (len(verses), EXPECTED[uid])))
        usfm = build_book(code, verses, args.project,
                          poetry=args.psalms_poetry,
                          sd_workaround=args.sd_workaround)
        chunks.append(usfm)
        if args.single:
            continue
        num, uid, _name, _abbr, _toc1 = BOOKMAP[code]
        if args.paratext:
            fname = "%02d%s%s.SFM" % (num, uid, args.abbrev)
        else:
            fname = "%02d-%s.usfm" % (num, uid)
        entries.append((fname, usfm))

    if args.single:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(chunks))
        written.append(os.path.basename(out_path))
    elif zip_mode:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, content in entries:
                zf.writestr(fname, content)
        written = [f for f, _ in entries]
    else:
        os.makedirs(out_path, exist_ok=True)
        for fname, content in entries:
            with open(os.path.join(out_path, fname), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(content)
        written = [f for f, _ in entries]

    if problems:
        print("\nn.b. incohérences relevées :", file=sys.stderr)
        for code, ch, vs, msg in problems[:20]:
            if ch is None:
                print("  %s : %s" % (code, msg), file=sys.stderr)
            else:
                print("  %s %d.%d : %s" % (code, ch, vs, msg),
                      file=sys.stderr)
        if len(problems) > 20:
            print("  … et %d autre(s)" % (len(problems) - 20),
                  file=sys.stderr)

    if not args.quiet:
        print("%d livre(s), %d verset(s), %d chapitre(s), "
              "%d ligne(s) ignorée(s) -> %s"
              % (len(ordered), total_verses, stat["chapters"],
                 stat["skipped"], out_path))
        for f in written:
            print("  " + f)


if __name__ == "__main__":
    main()