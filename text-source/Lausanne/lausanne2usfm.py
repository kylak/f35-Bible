#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
lausanne2usfm.py — convertit la Bible de Lausanne (fichier plat « Bk C:V texte »)
au format USFM 3.0.

Correspondances de balisage :
    ¶            -> \p          (nouveau paragraphe)
    [mot]        -> \add mot\add*   (mot suppléé par le traducteur)
    {note}       -> \f + \ft note\f*  (note marginale : rendu alternatif)
    (Ps 22:18)   -> \x - \xt Ps 22:18\x*   (renvoi scripturaire ; désactivable)

Usage :
    python3 lausanne2usfm.py SOURCE.txt -o dossier_sortie
    python3 lausanne2usfm.py SOURCE.txt -o out --keep-refs      # renvois laissés en texte
    python3 lausanne2usfm.py SOURCE.txt -o out --paratext       # noms de fichiers Paratext
    python3 lausanne2usfm.py SOURCE.txt -o out --single         # un seul fichier global
"""

import argparse
import os
import re
import sys
import unicodedata

# ---------------------------------------------------------------------------
# Table des livres : code source -> (n° USFM, ID USFM, nom français, abréviation)
# ---------------------------------------------------------------------------
BOOKS = [
    ("Gen", 1,  "GEN", "Genèse",                   "Gn"),
    ("Exo", 2,  "EXO", "Exode",                    "Ex"),
    ("Lev", 3,  "LEV", "Lévitique",                "Lv"),
    ("Num", 4,  "NUM", "Nombres",                  "Nb"),
    ("Deu", 5,  "DEU", "Deutéronome",              "Dt"),
    ("Jos", 6,  "JOS", "Josué",                    "Jos"),
    ("Jdg", 7,  "JDG", "Juges",                    "Jg"),
    ("Rut", 8,  "RUT", "Ruth",                     "Rt"),
    ("1Sa", 9,  "1SA", "1 Samuel",                 "1S"),
    ("2Sa", 10, "2SA", "2 Samuel",                 "2S"),
    ("1Ki", 11, "1KI", "1 Rois",                   "1R"),
    ("2Ki", 12, "2KI", "2 Rois",                   "2R"),
    ("1Ch", 13, "1CH", "1 Chroniques",             "1Ch"),
    ("2Ch", 14, "2CH", "2 Chroniques",             "2Ch"),
    ("Ezr", 15, "EZR", "Esdras",                   "Esd"),
    ("Neh", 16, "NEH", "Néhémie",                  "Né"),
    ("Est", 17, "EST", "Esther",                   "Est"),
    ("Job", 18, "JOB", "Job",                      "Jb"),
    ("Psa", 19, "PSA", "Psaumes",                  "Ps"),
    ("Pro", 20, "PRO", "Proverbes",                "Pr"),
    ("Ecc", 21, "ECC", "Ecclésiaste",              "Ec"),
    ("Sol", 22, "SNG", "Cantique des cantiques",   "Ct"),
    ("Isa", 23, "ISA", "Ésaïe",                    "Es"),
    ("Jer", 24, "JER", "Jérémie",                  "Jr"),
    ("Lam", 25, "LAM", "Lamentations",             "Lm"),
    ("Eze", 26, "EZK", "Ézéchiel",                 "Ez"),
    ("Dan", 27, "DAN", "Daniel",                   "Dn"),
    ("Hos", 28, "HOS", "Osée",                     "Os"),
    ("Joe", 29, "JOL", "Joël",                     "Jl"),
    ("Amo", 30, "AMO", "Amos",                     "Am"),
    ("Oba", 31, "OBA", "Abdias",                   "Ab"),
    ("Jon", 32, "JON", "Jonas",                    "Jon"),
    ("Mic", 33, "MIC", "Michée",                   "Mi"),
    ("Nah", 34, "NAM", "Nahum",                    "Na"),
    ("Hab", 35, "HAB", "Habakuk",                  "Ha"),
    ("Zep", 36, "ZEP", "Sophonie",                 "So"),
    ("Hag", 37, "HAG", "Aggée",                    "Ag"),
    ("Zec", 38, "ZEC", "Zacharie",                 "Za"),
    ("Mal", 39, "MAL", "Malachie",                 "Ml"),
    ("Mat", 41, "MAT", "Matthieu",                 "Mt"),
    ("Mar", 42, "MRK", "Marc",                     "Mc"),
    ("Luk", 43, "LUK", "Luc",                      "Lc"),
    ("Joh", 44, "JHN", "Jean",                     "Jn"),
    ("Act", 45, "ACT", "Actes",                    "Ac"),
    ("Rom", 46, "ROM", "Romains",                  "Rm"),
    ("1Co", 47, "1CO", "1 Corinthiens",            "1Co"),
    ("2Co", 48, "2CO", "2 Corinthiens",            "2Co"),
    ("Gal", 49, "GAL", "Galates",                  "Ga"),
    ("Eph", 50, "EPH", "Éphésiens",                "Ep"),
    ("Phi", 51, "PHP", "Philippiens",              "Ph"),
    ("Col", 52, "COL", "Colossiens",               "Col"),
    ("1Th", 53, "1TH", "1 Thessaloniciens",        "1Th"),
    ("2Th", 54, "2TH", "2 Thessaloniciens",        "2Th"),
    ("1Ti", 55, "1TI", "1 Timothée",               "1Tm"),
    ("2Ti", 56, "2TI", "2 Timothée",               "2Tm"),
    ("Tit", 57, "TIT", "Tite",                     "Tt"),
    ("Phm", 58, "PHM", "Philémon",                 "Phm"),
    ("Heb", 59, "HEB", "Hébreux",                  "Hé"),
    ("Jam", 60, "JAS", "Jacques",                  "Jc"),
    ("1Pe", 61, "1PE", "1 Pierre",                 "1P"),
    ("2Pe", 62, "2PE", "2 Pierre",                 "2P"),
    ("1Jo", 63, "1JN", "1 Jean",                   "1Jn"),
    ("2Jo", 64, "2JN", "2 Jean",                   "2Jn"),
    ("3Jo", 65, "3JN", "3 Jean",                   "3Jn"),
    ("Jud", 66, "JUD", "Jude",                     "Jude"),
    ("Rev", 67, "REV", "Apocalypse",               "Ap"),
]
BOOKMAP = {src: (num, uid, name, abbr) for src, num, uid, name, abbr in BOOKS}
ORDER = {src: i for i, (src, *_rest) in enumerate(BOOKS)}

LINE_RE = re.compile(r"^(\S+)\s+(\d+):(\d+)\s+(.*)$")
# Un renvoi = parenthèse contenant « Abrév C:V » et rien d'autre que des refs.
XREF_RE = re.compile(
    r"\((?:Chap\.\s*)?"                                # (Chap. 17:12)
    r"((?:\d\s?)?[A-ZÉ][a-zé]{1,4}\.?\s*\d+\s*[: ]\s*\d+"   # Ps 22:18, Deut.32:35, Za 12 10
    r"(?:\s*[-–]\s*\d+)?"                             # …-11  (intervalle)
    r"(?:\s*[;,]\s*(?:(?:\d\s?)?[A-ZÉ][a-zé]{1,4}\.?\s*)?"
    r"\d+(?::\d+)?(?:,\d+)?)*)(\.?)\)"                # …; Lév 19:18 / …:10,18
)

# Numéro de verset alternatif imprimé en tête de verset par la Lausanne :
# « (13:1) Ensuite le peuple partit… » (numérotation hébraïque).
VA_RE = re.compile(r"^\((\d+:\d+)\)\s*")

# Numéro hébraïque signalé en cours de verset, et non en tête.
VA_MID_RE = re.compile(r"\((\d+:\d+)\)")

# Renvois que le motif général ne reconnaît pas (format irrégulier).
REF_EXTRA = {
    ("MAT", 12, 21, "Es 42:1, etc."),
    ("ROM", 11, 4, "1R 19:10,18"),
    ("ROM", 13, 9, "Ex 20"),
}

# Ouvertures de proposition : une parenthèse qui commence ainsi est une
# incise du texte original, pas une glose du traducteur.
CLAUSE_RE = re.compile(
    r"^(or|car|et|mais|ce qui|ce que|c'est|celui|celle|ceux|il|ils|elle|elles"
    r"|je|tu|nous|vous|qui|que|quand|parce|afin|non|savoir|dit-il|s'il|selon"
    r"|comme|d'après|voici|lorsque|puis|alors|au moment|à savoir|\d)\b", re.I)


ELISION_RE = re.compile(r"^(?:[dlnmtsj]'|qu'|jusqu'|c')", re.I)


# Mots-vedettes que la reprise automatique tronque : la glose porte sur une
# expression entière, pas sur le seul mot qui précède la parenthèse.
KEYWORD_OVERRIDES = {
    ("GEN", 24, 10, "Mésopotamie"): "Aram des deux fleuves",
    ("DEU", 23, 4, "Mésopotamie"): "Aram des fleuves",
    ("JDG", 3, 8, "Mésopotamie"): "Aram des deux fleuves",
    ("1CH", 19, 6, "Mésopotamie"): "Aram des deux fleuves",
    ("1CO", 16, 22, "le Seigneur vient"): "Maran atha",
    # gloses portant sur deux termes reliés par « et »
    ("EXO", 17, 7, "tentation et contestation"): "Massa et Mériba",
    ("EXO", 28, 30, "lumières et perfections"): "Ourim et Thoummim",
    ("DEU", 33, 8, "perfections et lumières"): "Thummim et Ourim",
    ("EZR", 2, 63, "lumières et perfections"): "Ourim et Thoummim",
    ("NEH", 7, 65, "lumières et perfections"): "Ourim et Thoummim",
    ("GEN", 16, 13, "tu es le Dieu de ma vision"): "Atta-el-roï",
    ("GAL",  5,  8, "qui vous anime"): "La persuasion",
    # capitale seulement due à la position en tête de phrase : le lemme
    # doit être le même partout pour un même mot.
    ("MRK",  3, 28, "en vérité"): "amen",
    ("LUK",  4, 24, "en vérité"): "amen",
    ("JHN",  1, 51, "en vérité, en vérité"): "amen, amen",
}


def gloss_note(chapter, verse, keyword, gloss, formula="deux-points"):
    """Fabrique une note de bas de page sans appel de note pour une glose."""
    kw = ELISION_RE.sub("", keyword).strip(" ,.;:!?«»\u2013\u2014()")
    body = re.sub(r"^c'est-à-dire\s+", "", gloss.strip())
    low = body.lower()
    if low.startswith(("ou ", "héb.", "heb.", "grec,", "et de même")):
        lead = body                       # « ou chose », « Héb. de nombres »
    elif not kw:
        lead = body
    elif formula == "cad":
        lead = "c.-à-d. " + body
    elif formula == "signifie":
        lead = "signifie « %s »" % body.rstrip(".")
    elif formula == "sens":
        lead = "a le sens de « %s »" % body.rstrip(".")
    elif formula == "signification":
        lead = "a la signification de « %s »" % body.rstrip(".")
    else:                                 # deux-points : neutre
        lead = ": " + body
    if not lead.endswith((".", "!", "?", "»")):
        lead += "."
    if formula in ("signifie", "sens", "signification") and not lead.endswith("."):
        lead += "."
    parts = [r"\f -", r"\fr %d.%d" % (chapter, verse)]
    if kw and any(ch.isalpha() for ch in kw):
        parts.append(r"\fq %s" % kw)
    parts.append(r"\ft %s\f*" % lead)
    return " ".join(parts)


def looks_like_gloss(content):
    """Heuristique : glose d'un mot translittéré ou d'un nom propre."""
    return len(content.split()) <= 3 and not CLAUSE_RE.match(content)


def read_source(path):
    """Lit le fichier source. cp1252 par défaut, avec repli UTF-8."""
    raw = open(path, "rb").read()
    for enc in ("cp1252", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("Impossible de décoder le fichier source.")
    # Le fichier mêle CRLF, LF, CR et NEL (U+0085) comme fins de ligne.
    return [l.strip() for l in re.split(r"\r\n|\n|\r|\x85", text) if l.strip()]


def convert_inline(text, keep_refs=False, brackets=False, xo=None,
                   glosses=None, adds=None, gloss_notes=False, ref=None,
                   formula="deux-points", book_uid=None, va_notes=False,
                   drop_va=False):
    """Convertit le balisage interne d'un verset en marqueurs USFM."""
    # 1. Notes marginales {…} -> note de bas de page.
    #    On protège d'abord leur contenu pour que les crochets qu'elles
    #    renferment ne soient pas transformés en \add.
    notes = []

    def stash(m):
        notes.append(m.group(1).strip())
        return "\x00%d\x00" % (len(notes) - 1)

    text = re.sub(r"\{([^{}]*)\}", stash, text)

    # 2. Mots suppléés [mot] -> \add mot\add*
    #    Avec --brackets on laisse les crochets tels quels, comme dans
    #    l'édition imprimée de 1872.
    if not brackets:
        text = re.sub(r"\[([^\[\]]*)\]", r"\\add \1\\add*", text)

    # 3. Renvois scripturaires (Ps 22:18) -> \x - \xt Ps 22:18\x*
    if not keep_refs:
        origin = (r"\xo %s " % xo) if xo else ""
        text = XREF_RE.sub(
            lambda m: r"\x - %s\xt %s\x*%s" % (origin, m.group(1).strip(),
                                                m.group(2)), text)

    # 3 ter. Renvois de format irrégulier, désignés un à un.
    if not keep_refs and ref is not None and book_uid is not None:
        for bk, c, v, content in REF_EXTRA:
            if (bk, c, v) == (book_uid, ref[0], ref[1]):
                origin = (r"\xo %d.%d " % ref) if xo else ""
                text = text.replace(
                    "(%s)" % content,
                    r"\x - %s\xt %s\x*" % (origin, content))

    # 3 quater. Numéro hébraïque en cours de verset.
    if drop_va:
        text = re.sub(r"\s*\(\d+:\d+\)\s*", " ", text)
    if va_notes and ref is not None:
        text = VA_MID_RE.sub(
            lambda m: r"\f - \fr %d.%d \ft Ici commence le verset %s de "
                      r"l'hébreu.\f*" % (ref[0], ref[1], m.group(1)), text)
        text = re.sub(r"\s+(\\f - \\fr)", r"\1", text)

    # 3 bis. Gloses du traducteur -> \it …\it* (italique dans l'imprimé).
    if glosses is not None:
        def mark(m):
            inner = m.group(1).strip()
            # une note {…} a pu être mise de côté à l'intérieur de la
            # parenthèse : on la neutralise pour la comparaison.
            key = re.sub(r"\x00\d+\x00", "", inner).strip()
            if key in (adds or ()):
                return r"\add (%s)\add*" % inner
            if key not in glosses:
                return m.group(0)
            if not gloss_notes:
                return r"\it (%s)\it*" % inner
            stashed = "".join(re.findall(r"\x00\d+\x00", inner))
            # on remonte jusqu'au dernier mot réel : les notes mises de côté
            # et les guillemets ne sont pas des mots-vedettes.
            head = re.sub(r"\x00\d+\x00", " ", text[:m.start()])
            # Une glose redoublée (« en vérité, en vérité ») glose un mot
            # lui-même redoublé dans le texte (« Amen, amen ») : on reprend
            # autant de mots qu'il y a de segments identiques.
            segs = [x.strip() for x in key.split(",")]
            want = len(segs) if len(segs) > 1 and len(
                {x.lower() for x in segs}) == 1 else 1
            toks = []
            for tok in reversed(head.split()):
                cand = tok.strip(" .;:!?«»\"\u2013\u2014")
                if any(ch.isalpha() for ch in cand):
                    toks.append(cand)
                    if len(toks) >= want:
                        break
                elif toks:
                    break
            prev = " ".join(reversed(toks)).strip(" ,")
            prev = KEYWORD_OVERRIDES.get((book_uid, ref[0], ref[1], key), prev)
            return gloss_note(ref[0], ref[1], prev, key, formula) + stashed

        text = re.sub(r"\(([^()]*)\)", mark, text)
        if gloss_notes:
            # pas d'appel de note : on supprime l'espace qui précédait la
            # parenthèse pour ne pas laisser de blanc double.
            text = re.sub(r"\s+(\\f -)", r"\1", text)

    # 4. Réinjection des notes.
    def unstash(m):
        return r"\f + \ft %s\f*" % notes[int(m.group(1))]

    text = re.sub(r"\x00(\d+)\x00", unstash, text)

    return re.sub(r"\s+", " ", text).strip()


def build_book(src_code, verses, project, keep_refs=False, sd_workaround=False,
               brackets=False, blank_lines=False, xo=False, no_va=False,
               gloss_index=None, add_index=None, paren_log=None, gloss_notes=False,
               formula="deux-points", va_notes=False, drop_va_books=()):
    """verses : liste de (chapitre, verset, texte brut) triée."""
    num, uid, name, abbr = BOOKMAP[src_code]
    out = []
    out.append(r"\id %s %s" % (uid, project))
    out.append(r"\ide UTF-8")
    out.append(r"\h %s" % name)
    out.append(r"\toc1 %s" % name)
    out.append(r"\toc2 %s" % name)
    out.append(r"\toc3 %s" % abbr)
    out.append(r"\mt1 %s" % name.upper())

    drop_va = uid in drop_va_books or "ALL" in drop_va_books
    cur_chapter = None
    for chapter, verse, raw in verses:
        if chapter != cur_chapter:
            out.append(r"\c %d" % chapter)
            # Contournement d'un bogue de usfmtc < 0.4.4 (embarqué dans
            # PTXprint <= 3.0.17) : au passage d'un chapitre à l'autre, le
            # numéro de verset n'est pas remis à zéro, ce qui produit une
            # RefRange invalide. Un marqueur de « section » après le \c force
            # le recalcul de la référence. \sd est un simple séparateur.
            if sd_workaround and chapter > 1:
                out.append(r"\sd")
            cur_chapter = chapter
            need_para = True
        else:
            need_para = False

        body = raw.strip()

        # Numéro de verset alternatif -> \va …\va*
        alt = ""
        m_alt = VA_RE.match(body)
        if m_alt and drop_va:
            body = body[m_alt.end():].strip()      # numéro simplement supprimé
            m_alt = None
        if m_alt and not no_va:
            alt = r"\va %s\va* " % m_alt.group(1)
            body = body[m_alt.end():].strip()

        starts_para = body.startswith("¶")
        if starts_para:
            body = body[1:].strip()

        # Un \c doit toujours être suivi d'un marqueur de paragraphe
        # avant le premier \v : on en insère un même sans ¶ dans la source.
        if starts_para or need_para:
            # \b insère une ligne vide ; USFM interdit de l'employer avant
            # le premier paragraphe d'un chapitre.
            if blank_lines and not need_para:
                out.append(r"\b")
            out.append(r"\p")

        if paren_log is not None:
            # les parenthèses situées dans une note {…} ne sont pas balisées
            scan = re.sub(r"\{[^{}]*\}", "", body)
            for mm in re.finditer(r"\(([^()]*)\)", scan):
                inner = mm.group(1).strip()
                if VA_RE.match("(%s)" % inner) or XREF_RE.match("(%s)" % inner):
                    continue
                before = scan[:mm.start()].split()
                prev = before[-1] if before else ""
                paren_log.append((uid, chapter, verse, inner, prev,
                                  "glose" if looks_like_gloss(inner) else "incise"))

        gl = ad = None
        if gloss_index is not None:
            gl = gloss_index.get((uid, chapter, verse), set())
            ad = add_index.get((uid, chapter, verse), set()) if add_index else set()

        body = convert_inline(body, keep_refs=keep_refs, brackets=brackets,
                              xo=("%d:%d" % (chapter, verse)) if xo else None,
                              glosses=gl, adds=ad, gloss_notes=gloss_notes,
                              ref=(chapter, verse), formula=formula,
                              book_uid=uid,
                              va_notes=va_notes and not drop_va,
                              drop_va=drop_va)

        # ¶ en cours de verset -> \p sur sa propre ligne.
        parts = [p.strip() for p in body.split("¶")]
        out.append((r"\v %d %s%s" % (verse, alt, parts[0])).rstrip())
        for extra in parts[1:]:
            if blank_lines:
                out.append(r"\b")
            out.append(r"\p")
            if extra:
                out.append(extra)

    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Convertit la Bible de Lausanne en USFM 3.0.")
    ap.add_argument("source", help="fichier texte source (Bk C:V texte)")
    ap.add_argument("-o", "--output", default="usfm", help="dossier de sortie")
    ap.add_argument("--project", default="Bible de Lausanne (1872)",
                    help="libellé placé après \\id")
    ap.add_argument("--keep-refs", action="store_true",
                    help="laisser les renvois scripturaires en texte au lieu de \\x")
    ap.add_argument("--paratext", action="store_true",
                    help="nommer les fichiers à la mode Paratext (01GENLau.SFM)")
    ap.add_argument("--abbrev", default="Lau", help="sigle du projet pour --paratext")
    ap.add_argument("--front-as-frt", action="store_true",
                    help="écrire la préface comme livre FRT plutôt que XXA")
    ap.add_argument("--front-intro", metavar="LIVRE",
                    help="insérer la préface (--front) en introduction du livre "
                         "indiqué, ex. GEN ou JHN, au lieu d'un livre FRT")
    ap.add_argument("--front", metavar="FICHIER",
                    help="copier une préface (livre FRT) dans le dossier de "
                         "sortie")
    ap.add_argument("--list-parens", metavar="FICHIER",
                    help="écrire un TSV de toutes les parenthèses à relire")
    ap.add_argument("--glosses", metavar="FICHIER",
                    help="TSV de relecture : les lignes marquées « glose » "
                         "seront mises en \\it")
    ap.add_argument("--gloss-formula", default="deux-points",
                    choices=["deux-points", "cad", "signifie", "sens",
                             "signification"],
                    help="libellé des notes de glose")
    ap.add_argument("--drop-va", metavar="LIVRES", default="ALL",
                    help="supprimer la versification annexe dans ces livres "
                         "(codes séparés par des virgules, ALL par défaut ; "
                         "NONE pour la conserver partout)")
    ap.add_argument("--va-notes", action="store_true",
                    help="renvoyer en note les numéros hébraïques situés en "
                         "cours de verset")
    ap.add_argument("--gloss-notes", action="store_true",
                    help="renvoyer les gloses en note de bas de page, sans "
                         "appel de note dans le texte")
    ap.add_argument("--no-va", action="store_true",
                    help="laisser les numéros de verset alternatifs en texte")
    ap.add_argument("--brackets", action="store_true",
                    help="garder les crochets [ ] au lieu de \\add")
    ap.add_argument("--blank-lines", action="store_true",
                    help="insérer un \\b (ligne vide) entre les paragraphes")
    ap.add_argument("--xo", action="store_true",
                    help="ajouter la référence d'origine (\\xo) dans les renvois")
    ap.add_argument("--sd-workaround", action="store_true",
                    help="insérer un \\sd après chaque \\c (PTXprint <= 3.0.17)")
    ap.add_argument("--single", action="store_true",
                    help="tout écrire dans un seul fichier")
    args = ap.parse_args()

    lines = read_source(args.source)

    books = {}
    unknown = set()
    bad = 0
    for line in lines:
        m = LINE_RE.match(line)
        if not m:
            bad += 1
            continue
        code, ch, vs, txt = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        if code not in BOOKMAP:
            unknown.add(code)
            continue
        books.setdefault(code, []).append((ch, vs, txt))

    if bad:
        print("  %d ligne(s) non reconnue(s), ignorée(s)." % bad, file=sys.stderr)
    if unknown:
        print("  code(s) de livre inconnu(s) : %s" % ", ".join(sorted(unknown)), file=sys.stderr)

    gloss_index = add_index = None
    if args.glosses:
        gloss_index = {}
        add_index = {}
        with open(args.glosses, encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 6:
                    continue
                kind = parts[5].strip().lower()
                key = (parts[0], int(parts[1]), int(parts[2]))
                if kind == "glose":
                    gloss_index.setdefault(key, set()).add(parts[3])
                elif kind == "ajout":
                    add_index.setdefault(key, set()).add(parts[3])

    paren_log = [] if args.list_parens else None

    os.makedirs(args.output, exist_ok=True)
    ordered = sorted(books, key=lambda c: ORDER[c])

    written, total_verses = [], 0
    chunks = []
    for code in ordered:
        verses = sorted(books[code])
        total_verses += len(verses)
        usfm = build_book(code, verses, args.project, keep_refs=args.keep_refs,
                          sd_workaround=args.sd_workaround,
                          brackets=args.brackets, blank_lines=args.blank_lines,
                          xo=args.xo, no_va=args.no_va,
                          gloss_index=gloss_index, add_index=add_index,
                          paren_log=paren_log,
                          gloss_notes=args.gloss_notes,
                          formula=args.gloss_formula,
                          va_notes=args.va_notes,
                          drop_va_books=() if args.drop_va.upper() == "NONE"
                          else tuple(x.strip().upper()
                                     for x in args.drop_va.split(",")
                                     if x.strip()))
        chunks.append(usfm)
        if args.single:
            continue
        num, uid, _name, _abbr = BOOKMAP[code]
        if args.paratext:
            fname = "%02d%s%s.SFM" % (num, uid, args.abbrev)
        else:
            fname = "%02d-%s.usfm" % (num, uid)
        path = os.path.join(args.output, fname)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(usfm)
        written.append(fname)

    if args.single:
        path = os.path.join(args.output, "lausanne.usfm")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(chunks))
        written.append("lausanne.usfm")

    if args.front and not args.front_intro:
        # XXA est un code de « matériel supplémentaire » : PTXprint le
        # propose dans la liste des livres et le compose comme les autres,
        # avec son propre titre. Un livre FRT, lui, serait ignoré.
        code = "FRT" if args.front_as_frt else "XXA"
        num = "A0" if args.front_as_frt else "94"
        name = ("%s%s%s.SFM" % (num, code, args.abbrev)) if args.paratext \
            else "%s-%s.usfm" % (num, code)
        body = []
        for line in open(args.front, encoding="utf-8"):
            line = line.rstrip("\n")
            if line.startswith("\\periph") and not args.front_as_frt:
                continue
            body.append(re.sub(r"^\\id\s+\w+", r"\\id %s" % code, line))
        with open(os.path.join(args.output, name), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(body).rstrip("\n") + "\n")
        written.insert(0, name)
        print("préface écrite -> %s (livre %s)" % (name, code))

    if args.front and args.front_intro:
        # PTXprint ne compose pas un livre FRT posé dans le dossier ; on
        # replie donc la préface dans l'introduction d'un livre imprimé.
        target = args.front_intro.upper()
        intro = []
        for line in open(args.front, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if re.match(r"\\(id|ide|h\d?|toc\d|periph|rem)\b", line):
                continue
            intro.append(re.sub(r"^\\mt(\d?)", r"\\imt\1", line))
        hit = None
        for fname in os.listdir(args.output):
            if ("-%s." % target) in fname or fname[2:5] == target:
                hit = fname
                break
        if hit is None:
            raise SystemExit("livre introuvable pour --front-intro : %s" % target)
        path = os.path.join(args.output, hit)
        txt = open(path, encoding="utf-8").read().split("\n")
        cut = next(i for i, l in enumerate(txt) if l.startswith("\\c "))
        txt[cut:cut] = intro + [r"\ie"]
        open(path, "w", encoding="utf-8", newline="\n").write("\n".join(txt))
        print("préface insérée en introduction de %s (%s)" % (target, hit))

    if paren_log is not None:
        with open(args.list_parens, "w", encoding="utf-8", newline="\n") as fh:
            for row in paren_log:
                fh.write("\t".join(str(x) for x in row) + "\n")
        print("%d parenthèses listées -> %s" % (len(paren_log), args.list_parens))

    print("%d livre(s), %d verset(s) -> %s" % (len(ordered), total_verses, args.output))


if __name__ == "__main__":
    main()
