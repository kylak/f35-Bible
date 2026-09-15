#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
html2usfm.py — Convertit une page HTML de traduction (ex. galates.html)
en fichier USFM 3.0 utilisable dans Paratext / PTX Print.

Conventions reconnues dans le HTML source
-----------------------------------------
  <span class="verses">03</span>            ->  \\v 3
  <span class="verses">ch.3</span>          ->  \\c 3
  <span class="RP-ponctuation">…</span>     ->  IGNORÉ      (ponctuation R.P.)
  <span class="ma-ponctuation">…</span>     ->  CONSERVÉ    (votre ponctuation)
        (une balise qui porte les DEUX classes est conservée :
         c'est une ponctuation sur laquelle vous êtes d'accord avec R.P.)
  <span class="majuscule">…</span>          ->  \\zmaj …\\zmaj*  (gras, police réduite)
        (marqueur personnalisé dans le namespace réservé « z » :
         à déclarer côté PTX Print par \\Marker zmaj / \\StyleType character)
  [mot]                                     ->  \\add mot\\add*   (italiques)
  {mot}                                     ->  note de bas de page
  title="…"  (infobulle)                    ->  note de bas de page
  <br>                                      ->  nouveau paragraphe \\m
  &emsp; (cadratin d'alinéa)                ->  nouveau paragraphe \\p

Usage
-----
  python3 html2usfm.py galates.html -o 48GALfr.usfm     (aucune dépendance)
  python3 html2usfm.py galates.html -o 48GALfr.usfm --formatage
  python3 html2usfm.py galates.html --id GAL --nom "Galates" \\
          --titre "Épître aux Galates" --num-livre 48 --code-projet fr
"""

import argparse
import os
import re
import sys
import zipfile
from html.parser import HTMLParser


EMSP = "\u2003"          # &emsp;
NBSP = "\u00a0"          # &nbsp;
SENTINELLE = "\x00"      # sert à protéger les notes pendant les regex


# --------------------------------------------------------------------------
#  Outils
# --------------------------------------------------------------------------
# Balises sans contenu, et balises dont on ignore complètement le contenu.
VIDES = {"br", "img", "hr", "meta", "link", "input", "col", "area",
         "base", "embed", "param", "track", "wbr", "source"}
IGNOREES = {"script", "style", "head", "nav", "header", "audio",
            "figure", "figcaption"}


def est_ponctuation_rp_seule(classes):
    """Vrai si la balise est de la ponctuation R.P. que VOUS n\'avez pas retenue."""
    return "RP-ponctuation" in classes and "ma-ponctuation" not in classes


# --------------------------------------------------------------------------
#  Convertisseur
# --------------------------------------------------------------------------
class ConvertisseurUSFM:

    def __init__(self, opts):
        self.o = opts
        self.sortie = []          # lignes USFM finales
        self.lignes = []          # lignes du paragraphe courant
        self.courante = ""        # ligne en cours de construction
        self.marqueur = None      # marqueur de paragraphe en attente ('p' / 'm')
        self.demarre = False      # on n'écrit qu'à partir de "ch.1"
        self.chapitre = 0
        self.verset = 0
        self.ouverts = []         # marqueurs de caractère ouverts (\bd, \em…)
        self.nb_notes = 0
        self.nb_versets = 0

    # ---------------------------------------------------------------- texte
    def ajoute(self, txt):
        if not txt:
            return
        txt = txt.replace(NBSP, " ").replace("\n", " ").replace("\t", " ")

        # Le cadratin marque un alinéa : nouveau paragraphe indenté.
        if EMSP in txt:
            morceaux = txt.split(EMSP)
            for i, m in enumerate(morceaux):
                if i > 0:
                    if not self.courante.strip() and not self.lignes:
                        self.marqueur = "p"      # alinéa -> \p
                    else:
                        self.courante += " "
                self.ajoute_brut(m)
            return
        self.ajoute_brut(txt)

    def ajoute_brut(self, txt):
        if not txt:
            return
        # {alternative} -> note de bas de page
        txt = re.sub(r"\{([^{}]*)\}", lambda m: self.note(m.group(1)), txt)
        if not self.courante.strip() and not txt.strip():
            return
        self.courante += txt

    # ---------------------------------------------------------------- notes
    def note(self, texte):
        """Fabrique une note de bas de page USFM."""
        texte = re.sub(r"\s+", " ", texte).strip()
        if not texte:
            return ""
        self.nb_notes += 1
        ref = "%d:%d" % (self.chapitre, self.verset)
        return " \\f %s \\fr %s \\ft %s\\f* " % (self.o.appel_note, ref, texte)

    # --------------------------------------------------- marqueurs caractère
    def ouvre_marqueur(self, m):
        if m in self.ouverts:        # pas d'imbrication d'un même marqueur
            return False
        self.ouverts.append(m)
        self.courante += "\\%s " % m
        return True

    def ferme_marqueur(self):
        if self.ouverts:
            m = self.ouverts.pop()
            self.courante = self.courante.rstrip() + "\\%s*" % m

    def _fermer_tous(self):
        return "".join("\\%s*" % m for m in reversed(self.ouverts))

    def _rouvrir_tous(self):
        return "".join("\\%s " % m for m in self.ouverts)

    # ----------------------------------------------------------- structure
    def pousse_ligne(self):
        if self.courante.strip():
            self.lignes.append(self.courante.rstrip() + self._fermer_tous())
        self.courante = ""

    def nouveau_verset(self, num):
        self.pousse_ligne()
        self.verset = num
        self.nb_versets += 1
        self.courante = "\\v %d %s" % (num, self._rouvrir_tous())

    def nouveau_paragraphe(self, marqueur):
        self.vide_paragraphe()
        self.marqueur = marqueur

    def vide_paragraphe(self):
        self.pousse_ligne()
        if not self.lignes:
            return
        self.sortie.append("\\" + (self.marqueur or "p"))
        for ligne in self.lignes:
            ligne = self.nettoie(ligne)
            if ligne:
                self.sortie.append(ligne)
        self.lignes = []
        self.marqueur = None

    def nouveau_chapitre(self, num):
        self.vide_paragraphe()
        self.chapitre = num
        self.verset = 0
        self.sortie.append("\\c %d" % num)
        self.marqueur = "p"

    # ------------------------------------------------------------ nettoyage
    def nettoie(self, ligne):
        """Espaces, crochets -> \\add, en protégeant le contenu des notes."""
        notes = []

        def protege(m):
            notes.append(m.group(0))
            return "%s%d%s" % (SENTINELLE, len(notes) - 1, SENTINELLE)

        ligne = re.sub(r"\\f .*?\\f\*", protege, ligne)

        # [mot] -> \add mot\add*
        rempl = r"\\add [\1]\\add*" if self.o.garder_crochets else r"\\add \1\\add*"
        if not self.o.sans_add:
            ligne = re.sub(r"\[([^\[\]\\]*?)\]", rempl, ligne)

        ligne = re.sub(r"[ \t]+", " ", ligne).strip()

        # Normalisation typographique française — désactivée par défaut,
        # pour ne surtout pas toucher à VOTRE ponctuation.
        if self.o.espaces_ponctuation:
            ligne = re.sub(r"\s+([,.·])", r"\1", ligne)
            ligne = re.sub(r"\s*([;:!?»])", NBSP + r"\1", ligne)

        # Les crochets à l'intérieur des notes (facultatif)
        if self.o.crochets_notes and not self.o.sans_add:
            notes = [re.sub(r"\[([^\[\]\\]*?)\]", rempl, n) for n in notes]

        def restaure(m):
            return notes[int(m.group(1))]

        ligne = re.sub(SENTINELLE + r"(\d+)" + SENTINELLE, restaure, ligne)
        ligne = re.sub(r"\s+", " ", ligne).strip()
        return ligne

    # ---------------------------------------------------------------- final
    def entete(self):
        o = self.o
        e = [
            "\\id %s %s" % (o.id, o.titre),
            "\\usfm 3.0",
            "\\ide UTF-8",
            "\\h %s" % o.nom,
            "\\toc1 %s" % o.titre,
            "\\toc2 %s" % o.nom,
            "\\toc3 %s" % o.abrev,
            "\\mt1 %s" % o.titre,
        ]
        return e

    def convertit(self, html_txt):
        analyseur = AnalyseurHTML(self)
        analyseur.feed(html_txt)
        analyseur.close()
        self.vide_paragraphe()
        return "\n".join(self.entete() + self.sortie) + "\n"


# --------------------------------------------------------------------------
#  Analyseur HTML (module standard html.parser : aucune dépendance externe)
# --------------------------------------------------------------------------
class AnalyseurHTML(HTMLParser):
    """Parcourt le HTML en flux et pilote le convertisseur.

    Une pile de balises ouvertes permet de savoir quand refermer un
    marqueur de caractère, quand sortir d'une zone ignorée (ponctuation
    R.P.) et quand poser une note d'infobulle. Les balises mal fermées
    du HTML source sont tolérées.
    """

    def __init__(self, conv):
        super().__init__(convert_charrefs=True)
        self.c = conv
        self.pile = []        # balises ouvertes
        self.saut = 0         # profondeur de zone ignorée
        self.capture = None   # texte d'un <span class="verses">

    # ------------------------------------------------------------ ouverture
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        c = self.c

        # Attributs : on fusionne les doublons (certaines balises du HTML
        # source portent deux fois style=, ex. "bold" puis "color: red").
        a = {}
        for cle, val in attrs:
            cle = cle.lower()
            val = val or ""
            a[cle] = a[cle] + ";" + val if cle in a else val

        if tag == "br":
            if c.demarre and not self.saut and self.capture is None:
                c.nouveau_paragraphe("m")
            return
        if tag in VIDES:
            return

        entree = {"nom": tag, "ferme": 0, "note": None,
                  "saut": False, "verses": False}
        self.pile.append(entree)

        if self.saut or tag in IGNOREES:
            entree["saut"] = True
            self.saut += 1
            return

        classes = set(a.get("class", "").split())

        # --- ponctuation R.P. que vous n'avez pas retenue : on saute
        if est_ponctuation_rp_seule(classes):
            entree["saut"] = True
            self.saut += 1
            return

        # --- numéro de verset ou de chapitre : on met son texte de côté
        if "verses" in classes:
            entree["verses"] = True
            self.capture = ""
            return

        if tag == "p" and c.demarre:
            c.nouveau_paragraphe("p")

        # --- infobulle title="…" -> note de bas de page
        if a.get("title") and c.demarre:
            entree["note"] = a["title"]

        # --- classe "majuscule" -> marqueur utilisateur \zmaj (gras + petit)
        if "majuscule" in classes and c.demarre:
            entree["ferme"] += c.ouvre_marqueur("zmaj")

        # --- mise en forme facultative
        if c.o.formatage and c.demarre:
            st = a.get("style", "").lower()
            if "bold" in st or tag in ("b", "strong"):
                entree["ferme"] += c.ouvre_marqueur("bd")
            if "underline" in st:
                entree["ferme"] += c.ouvre_marqueur("em")
            if "italic" in st or tag in ("i", "em"):
                entree["ferme"] += c.ouvre_marqueur("it")

    # -------------------------------------------------------------- fermeture
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VIDES:
            return
        # On cherche la balise ouvrante correspondante en remontant la pile ;
        # tout ce qui est resté ouvert au-dessus est refermé au passage.
        for i in range(len(self.pile) - 1, -1, -1):
            if self.pile[i]["nom"] == tag:
                while len(self.pile) > i:
                    self.ferme(self.pile.pop())
                return
        # balise fermante orpheline (HTML mal formé) : on l'ignore

    def ferme(self, entree):
        c = self.c
        if entree["saut"]:
            self.saut -= 1
            return
        if entree["verses"]:
            self.numero(self.capture or "")
            self.capture = None
            return
        for _ in range(entree["ferme"]):
            c.ferme_marqueur()
        if entree["note"]:
            c.courante += c.note(entree["note"])

    # ------------------------------------------------------------ numérotage
    def numero(self, brut):
        c = self.c
        brut = brut.strip()
        m_ch = re.match(r"^ch\.?\s*(\d+)", brut, re.I)
        if m_ch:
            c.demarre = True
            c.nouveau_chapitre(int(m_ch.group(1)))
            return
        m_v = re.match(r"^0*(\d+)", brut)
        if m_v and c.demarre:
            c.nouveau_verset(int(m_v.group(1)))
            return
        if c.demarre:
            c.ajoute(brut)

    # ------------------------------------------------------------------ texte
    def handle_data(self, data):
        if self.capture is not None:
            self.capture += data
            return
        if self.saut:
            return
        if self.c.demarre:
            self.c.ajoute(data)

    def handle_comment(self, data):
        pass    # les commentaires HTML ne sont pas traduits


# --------------------------------------------------------------------------
#  Ligne de commande
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Convertit une page HTML de traduction en USFM (PTX Print).")
    ap.add_argument("source", help="fichier HTML d'entrée (ex. galates.html)")
    ap.add_argument("-o", "--sortie", help="fichier USFM de sortie")
    ap.add_argument("--id", default="GAL", help="code de livre USFM (défaut : GAL)")
    ap.add_argument("--nom", default="Galates", help="nom courant du livre")
    ap.add_argument("--titre", default="Épître aux Galates", help="titre principal")
    ap.add_argument("--abrev", default="Ga", help="abréviation (\\toc3)")
    ap.add_argument("--num-livre", default="48",
                    help="numéro de livre pour le nom de fichier (défaut : 48)")
    ap.add_argument("--code-projet", default="fr",
                    help="code projet pour le nom de fichier (défaut : fr)")
    ap.add_argument("--appel-note", default="+", choices=["+", "-"],
                    help="appel de note : + (numéroté) ou - (aucun)")
    ap.add_argument("--formatage", action="store_true",
                    help="convertir gras/souligné en \\bd et \\em")
    ap.add_argument("--garder-crochets", action="store_true",
                    help="garder les crochets visibles à l'intérieur de \\add")
    ap.add_argument("--sans-add", action="store_true",
                    help="ne pas convertir les crochets en \\add")
    ap.add_argument("--crochets-notes", action="store_true",
                    help="convertir aussi les crochets à l'intérieur des notes")
    ap.add_argument("--espaces-ponctuation", action="store_true",
                    help="normaliser les espaces avant ; : ! ? (typographie française)")
    ap.add_argument("--zip", dest="zip", metavar="FICHIER.zip", nargs="?",
                    const=True, default=True,
                    help="nom de l'archive zip à créer (défaut : le nom du .usfm)")
    ap.add_argument("--sans-zip", dest="zip", action="store_const", const=False,
                    help="ne pas créer d'archive zip")
    ap.add_argument("--sans-usfm", action="store_true",
                    help="ne garder que l'archive zip (supprime le .usfm à côté)")
    o = ap.parse_args()

    if not o.sortie:
        o.sortie = "%s%s%s.usfm" % (o.num_livre, o.id, o.code_projet)

    with open(o.source, encoding="utf-8") as f:
        html_txt = f.read()

    conv = ConvertisseurUSFM(o)
    usfm = conv.convertit(html_txt)

    with open(o.sortie, "w", encoding="utf-8") as f:
        f.write(usfm)
    print("Écrit : %s" % os.path.abspath(o.sortie))

    if o.zip:
        nom_zip = o.zip if isinstance(o.zip, str) else \
            os.path.splitext(o.sortie)[0] + ".zip"
        with zipfile.ZipFile(nom_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(o.sortie, arcname=os.path.basename(o.sortie))
        print("Écrit : %s" % os.path.abspath(nom_zip))
        if o.sans_usfm:
            os.remove(o.sortie)

    print("  %d chapitre(s), %d verset(s), %d note(s) de bas de page."
          % (conv.chapitre, conv.nb_versets, conv.nb_notes))


if __name__ == "__main__":
    main()
