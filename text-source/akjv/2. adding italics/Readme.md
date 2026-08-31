# AKJV + italiques de la KJV (script DeepSeek)

Ajoute à l'AKJV les mots en italique de la KJV (les mots « ajoutés » par le
traducteur, non marqués dans le texte source de l'AKJV). Script :
`add_italics.py` (Python 3, sans dépendances).

## Principe

La KJV 2006 marque les italiques en USFM par `\add … \add*`. Pour chaque
verset, le script décode le balisage KJV (Strong `\w`, nom divin `\nd`,
paroles du Christ `\wj`, notes `\f`, pilcrow `¶`), aligne les mots du verset
KJV sur ceux du verset AKJV (`difflib.SequenceMatcher`), puis recopie les
marques `\add` sur le texte AKJV en tenant compte des modernisations de
l'AKJV :

| KJV        | AKJV                      |
| ---------- | ------------------------- |
| art        | are                       |
| thou / thee / ye | you                |
| thy / thine | your / yours            |
| hath / doth / saith | has / does / says / said |
| cometh, endureth, … (-eth) | comes, endures, … |
| unto / upon | to / on                  |
| thence / pulse | there / vegetables   |
| whence | from where (tous les mots) |
| wherewith | with which (tous les mots) |
| henceforth | from now on (tous les mots) |
| forasmuch | for as much (tous les mots) |

Quand l'AKJV rend un archaïsme par plusieurs mots (`whence` → *from where*,
`wherewith` → *with which*, `henceforth` → *from now on*,
`forasmuch` → *for as much*), **tous** ces mots passent en italique ensemble.

Seul le texte des versets est modifié ; l'en-tête et les marques `\c`/`\p`
de l'AKJV sont conservés tels quels.

La ponctuation collée à un mot italique reste **hors** du balisage
(`\add part\add*,` et non `\add part,\add*`) ; l'apostrophe `'` (ex.
`sons'`, `don't`) reste attachée au mot. Un mot du milieu d'une suite
italique portant une ponctuation impose la coupure de la suite
(`\add said he\add*, was`).

## Utilisation

```sh
python3 add_italics.py \
    --akjv ../1.\ convert-to-UFSM/akjv-usfm.zip \
    --kjv  ../../kjv/eng-kjv2006_usfm.zip
```

Par défaut, produit `akjv-with-italics-usfm.zip` (66 livres, mêmes noms de
fichiers que l'AKJV).

| Option                | Effet                                             |
| --------------------- | ------------------------------------------------- |
| `--akjv CHEMIN`       | archive USFM AKJV (défaut : `akjv-usfm.zip`)      |
| `--kjv CHEMIN`        | archive USFM KJV 2006 (défaut : `eng-kjv2006_usfm.zip`) |
| `-o, --output CHEMIN` | nom du `.zip` (extension ajoutée si absente)      |
| `--no-zip`            | écrire les fichiers USFM dans un dossier          |
| `--single`            | un seul fichier `akjv-with-italics.usfm`          |
| `--report FICHIER`    | rapport des versets sans contrepartie KJV         |
| `--quiet`             | sortie minimale                                   |

## Contrôles

En fin de traitement, on vérifie qu'en retirant toutes les marques `\add`
du fichier produit on retrouve exactement le texte AKJV d'origine
(66 livres, 1189 chapitres, 31102 versets, 0 écart).

Couverture : 26 997 des 26 998 mots italiques KJV retrouvés dans l'AKJV
(le seul écart, `[but]` en 1 Jn 2:23, est un ajout de traducteur supprimé
par l'AKJV, donc absent du verset).
