# Bible AKJV — conversion USFM

La **American King James Version** (AKJV), texte source : https://creationism.org/BibleAKJV/ (domaine public).
Il s'agit de la 5eme edition de l'AKJV, laquelle est basee sur la KJV (quelle edition de la KJV? le texte ne le dit pas, mais d'apres mes recherches, l'edition la plus proche est la 2006 Pure Cambridge Edition King James Version, donc j'imagine que ca devrait etre une edition tardive de la 1769 Cambridge).

## Organisation

- `BibleAKJV_AllIn1Text.zip` — texte plat (`C:V texte`)
- `BibleAKJV_AllIn1HTML.zip` — mêmes données en HTML
- `1. convert-to-UFSM/` — script `akjv2usfm.py` (Python 3, sans dépendances)

## Utilisation (script DeepSeek)

```sh
unzip BibleAKJV_AllIn1Text.zip
python3 1.\ convert-to-UFSM/akjv2usfm.py AkjvAllIn1Text.txt
```

Par défaut, produit `akjv-usfm.zip` contenant `01-GEN.usfm` … `67-REV.usfm`.

| Option                  | Effet                                                   |
| ----------------------- | ------------------------------------------------------- |
| `-o, --output CHEMIN`   | nom du `.zip` (extension ajoutée si absente)            |
| `--no-zip`              | écrire les fichiers USFM dans un dossier                |
| `--single`              | un seul fichier `akjv.usfm` (ou `-o fichier.usfm`)      |
| `--project LIBELLÉ`     | texte après `\id` (défaut : `American King James Version`) |
| `--paratext`            | noms Paratext (`01GENAKJV.SFM`) dans le zip             |
| `--abbrev SIGLE`        | sigle pour `--paratext` (défaut : `AKJV`)              |
| `--psalms-poetry`       | Psaumes en vers `\q1` plutôt qu'en prose `\p`           |
| `--sd-workaround`       | `\sd` après chaque `\c` (PTXprint ≤ 3.0.17)             |
| `--report FICHIER`      | rapport des lignes hors-texte                           |
| `--quiet`               | sortie minimale                                         |

Le script gère les titres de livres/chapitres (dont `++Isaiah 2`), les versets
coupés sur deux lignes, et vérifie en fin de conversion le compte de versets
de chaque livre (référence KJV : 66 livres, 1189 chapitres, 31102 versets).
