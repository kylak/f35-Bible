# AKJV → USFM (script DeepSeek)

Convertit le texte plat de la Bible **American King James Version** en USFM 3.0.
Script : `akjv2usfm.py` (Python 3, sans dépendances).

## Utilisation

```sh
unzip ../BibleAKJV_AllIn1Text.zip
python3 akjv2usfm.py AkjvAllIn1Text.txt
```

Par défaut, produit `akjv-usfm.zip` contenant `01-GEN.usfm` … `67-REV.usfm`.

## Options

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

## Notes

- Gère les titres de livres/chapitres (dont `++Isaiah 2`), les versets coupés
  sur deux lignes, et la normalisation NBSP/fins de ligne.
- Vérifie en fin de conversion le compte de versets de chaque livre
  (référence KJV : 66 livres, 1189 chapitres, 31102 versets).
