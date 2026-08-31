# AKJV — « said » → « says » (script `saith_to_says.py`)

L'AKJV rend systématiquement l'archaïsme « saith » de la KJV par « said »
(elle n'emploie jamais « says »). Pour rétablir le présent, `saith_to_says.py`
repasse sur le texte AKJV avec italiques (sortie d'`add_italics.py`, dans le
dossier `2. adding italics`) et remplace chaque « said » — qu'il soit dans une
plage `\add … \add*` (italique) ou non — par « says » **uniquement** lorsque
le mot KJV correspondant du verset est « saith ». Les « said » qui
correspondent à un « said » ou « saidst » de la KJV sont conservés.
L'alignement KJV ↔ AKJV reprend la même logique que `add_italics.py`, étendue
à tous les mots.

```sh
python3 saith_to_says.py
```

Par défaut, produit `akjv-with-italics-says-usfm.zip` (66 livres, mêmes noms
de fichiers).

| Option                | Effet                                             |
| --------------------- | ------------------------------------------------- |
| `-i, --input CHEMIN`  | archive AKJV avec italiques (défaut : `../2. adding italics/akjv-with-italics-usfm.zip`) |
| `--kjv CHEMIN`        | archive USFM KJV 2006 (défaut : `../../kjv/eng-kjv2006_usfm.zip`) |
| `-o, --output CHEMIN` | nom du `.zip` (extension ajoutée si absente)      |
| `--no-zip`            | écrire les fichiers USFM dans un dossier          |
| `--single`            | un seul fichier `akjv-with-italics-says.usfm`     |
| `--report FICHIER`    | rapport des versets modifiés (et sans contrepartie KJV) |
| `--quiet`             | sortie minimale                                   |

Dans les données actuelles, 1262 mots sont remplacés dans 1197 versets.
Exemples : « saith the LORD » → « says the LORD » (Gen 22:16, És 1:11…),
« he saith » → « he says » (Jn 1:51, Mc 14:30…), et les italiques ACT 1:4 et
ECC 4:8 « said he » → « says he », HEB 1:8 « he said » → « he says ».

Contrôles : pour chaque verset réécrit, on vérifie qu'en retirant les marques
`\add` du nouveau texte on retrouve exactement les mots du texte d'entrée, à
l'exception des « said » → « says » attendus ; en fin de traitement, on
revérifie la sortie entière : plus aucun « said » ne doit correspondre à un
« saith » de la KJV, et chaque « saith » de la KJV doit correspondre à un
« says » de l'AKJV (0 écart sinon).
