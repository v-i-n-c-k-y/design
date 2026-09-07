# Design

Trois effets de pixelisation, du plus simple au plus construit.

| Dossier | Fichier | Effet |
|---------|---------|-------|
| `riso/` | `riso.py` | Trame halftone en une encre |
| `boats/` | `boat.py` | Pavage regulier en tuiles "bateau", duotone risograph |
| `boats/` | `fleet.py` | Pavage par croissance, couleurs de la photo |
| `cloth/` | `index.html` | Couverture de survie en mylar, WebGL interactif |

`ressources/` porte l'image de test et le SVG dont sont tirees les encres du
degrade. Les rendus produits par les scripts ne sont pas versionnes.

## Installation

```bash
pip install Pillow numpy
```

Les scripts s'appellent en modules, depuis la racine du depot : `boats` importe
`riso` pour les encres et l'analyse des couleurs.

```bash
python -m riso.riso photo.jpg --color red -o output.png
python -m boats.boat photo.jpg -s 64 -g 5
python -m boats.fleet photo.jpg -s 64 -g 5
```

---

# Riso

Trame halftone : une photo, une encre.

## Utilisation

```bash
python -m riso.riso photo.jpg --color red -o output.png
```

### Arguments

| Argument | Description |
|----------|-------------|
| `image` | Chemin vers l'image source |
| `--color`, `-c` | Couleur d'impression. Nom (`red`, `blue`, `green`, `yellow`, `pink`, `orange`, `teal`, `black`, `gold`, `purple`) ou code hex (`#FF0000`) |
| `--output`, `-o` | Chemin du fichier de sortie (defaut: `riso_output.png`) |
| `--dot-size`, `-d` | Taille des points de trame (defaut: 8) |
| `--contrast` | Facteur de contraste, 1.0 = normal (defaut: 1.2) |
| `--angle` | Angle de la trame en degres (defaut: 45) |

### Exemples

```bash
# Impression bleue avec gros points
python -m riso.riso portrait.jpg -c blue -d 12

# Couleur personnalisee avec contraste fort
python -m riso.riso photo.jpg -c "#E84B20" --contrast 1.5

# Trame fine, angle different
python -m riso.riso photo.jpg -c teal -d 5 --angle 30
```

## Couleurs predefinies

Les couleurs reproduisent les encres classiques de risographie :

- `red` - Rouge Riso
- `blue` - Bleu Riso
- `green` - Vert Riso
- `yellow` - Jaune Riso
- `pink` - Rose fluorescent
- `orange` - Orange Riso
- `teal` - Bleu-vert
- `black` - Noir Riso
- `gold` - Or
- `purple` - Violet Riso

---

# Boat

Second effet : pixelisation en tuiles "bateau", chaque tuile etant la jonction de
trois triangles equilateraux.

## Principe

L'image est pavee d'un maillage de triangles equilateraux, partitionne en triplets
de triangles voisins. **Trois triangles connexes forment toujours un trapeze** --
c'est le seul triamant -- donc chaque triplet est un bateau, et chaque triangle
porte exactement la couleur de ses deux voisins. Chaque tuile prend la couleur
moyenne de l'image qu'elle recouvre, quantifiee sur une rampe d'encrage risograph.

Le pavage part d'un decoupage regulier en bandes horizontales, puis melange les
orientations : deux bateaux voisins forment six triangles, que l'on redecoupe au
hasard en deux triplets connexes. Comme tout triplet connexe est un bateau,
l'operation preserve le pavage a chaque etape -- il reste complet, sans trou ni
triangle orphelin, quel que soit le nombre de passes. Deux passes suffisent a
repartir les bateaux a peu pres egalement sur les six orientations possibles.

Un remplissage glouton (affecter chaque triangle a un bateau incomplet voisin ou
en ouvrir un nouveau) est plus direct mais laisse environ 0,5 % de triangles
orphelins, et un orphelin de taille 1 ou 2 ne peut jamais etre resorbe en
absorbant des tuiles completes -- une question de multiple de trois.

```bash
python -m boats.boat photo.jpg -c "#ff7aa2,#ffa26b" -s 64 -g 5 -o output.png
```

### Arguments

| Argument | Description |
|----------|-------------|
| `image` | Chemin vers l'image source |
| `--output`, `-o` | Chemin du fichier de sortie (defaut: `boat_output.png`) |
| `--colors`, `-c` | Encres separees par des virgules, noms ou codes hex (defaut: `#ff7aa2,#ffa26b`) |
| `--paper`, `-p` | Couleur du papier (defaut: blanc) |
| `--size`, `-s` | Cote du triangle en pixels (defaut: 32) |
| `--gap`, `-g` | Jour entre les tuiles en pixels (defaut: 2) |
| `--contrast` | Facteur de contraste, 1.0 = normal (defaut: 1.2) |
| `--levels`, `-l` | Nombre de niveaux d'encrage, papier compris (defaut: 6) |
| `--mix`, `-m` | Passes de melange des orientations, 0 = bateaux tous horizontaux (defaut: 8) |
| `--seed` | Graine du melange (defaut: 0) |
| `--no-dither` | Desactive le tramage ordonne entre niveaux |
| `--supersample` | Facteur de surechantillonnage pour l'anticrenelage (defaut: 2) |

Les niveaux forment une rampe : chaque encre monte en couverture a son tour, du
papier a la superposition complete. Avec deux encres et 6 niveaux, on va du blanc
a l'orange, puis au rose, puis a leur superposition.

### Exemples

```bash
# Duotone du degrade risograph-boat.svg
python -m boats.boat photo.jpg -s 64 -g 5

# Trois encres sur papier creme, tuiles jointives
python -m boats.boat photo.jpg -c pink,blue,black -p "#f4eadc" -l 8 -g 0

# Grosses tuiles, aplats francs sans tramage
python -m boats.boat photo.jpg -s 100 -l 4 --no-dither

# Pavage regulier, tous les bateaux horizontaux
python -m boats.boat photo.jpg -s 64 -g 5 --mix 0

# Autre tirage aleatoire des orientations
python -m boats.boat photo.jpg -s 64 -g 5 --seed 7
```

---

# Fleet

Meme tuile que `boats/boat.py` -- trois triangles adjacents -- mais un pavage construit
par croissance au lieu d'un decoupage regulier, et aucune palette : chaque bateau
prend la couleur moyenne de l'aire de l'image qu'il recouvre. Les bateaux
epousent les formes de l'image et ne s'alignent sur aucune grille.

## Principe

La maille est un quadrillage de rectangles cisaille en losanges, chaque losange
etant coupe en deux triangles isoceles. Un triangle est repere par `(i, j, o)` :
colonne, rangee, orientation dans son losange ; le noeud `(0, 0)` est le coin
haut-gauche de l'image. A 60 degres les triangles sont equilateraux et les
bateaux des trapezes ; a un autre angle, tout se cisaille.

La flotte part du triangle en haut a gauche et grandit de proche en proche :

1. `possible_boats(tri, free)` -- les bateaux encore formables autour d'un
   triangle. C'est son **degre de liberte**.
2. `boat_color(boat, colors)` -- la couleur d'un bateau et sa **distance** a
   l'image. Un bateau n'a qu'une couleur pour trois triangles : la moyenne de
   l'aire sous-jacente, celle qui minimise l'ecart. La distance est ce qui reste
   de cet ecart, en unites RGB.
3. `next_triangle(pool, distance)` -- le triangle a servir dans un lot de meme
   degre, celui dont le meilleur bateau s'ecarte le moins de l'image.
4. `orphans_created(boat, free)` -- combien de triangles ce bateau condamnerait.

Le choix du triangle suivant suit un **double ordre** : d'abord le degre de
liberte le plus faible, puis a degre egal la distance la plus faible. La
croissance garde en parallele les bateaux formes et les triangles **a
proximite**, ceux situes a deux pas d'un bateau : ce sont exactement ceux dont le
degre de liberte peut avoir change, donc les seuls a reclasser, et les seuls a
verifier avant de retenir un bateau.

Deux mesures reduisent les orphelins, chacune verifiee :

| | Orphelins | Proximite |
|---|---|---|
| Degre = nombre de voisins libres | 1,03 % | -- |
| Degre = nombre de bateaux formables | 0,52 % | 4,74 |
| ... et on refuse les bateaux qui en condamnent un | **0,21 %** | 4,93 |

Les 0,21 % restants sont tous *forces* : au moment du choix, aucun bateau
candidat ne les evitait. Servir un autre triangle du meme seau n'y change rien
non plus -- ce sont des poches enclavees dont le nombre de triangles n'est pas
multiple de trois, et aucun ordre local ne peut les resorber.

Le hasard n'intervient que pour departager des bateaux exactement a la meme
distance, dans les aplats.

Le cumul des distances donne la **proximite du pavage**, l'ecart RGB moyen entre
chaque triangle et la couleur du bateau qui le recouvre -- affiche a chaque
rendu. Sur l'image de test a cote de 64 pixels, la croissance guidee par la
couleur donne 4,93 la ou un decoupage regulier en bandes sur la meme maille
donne 6,71, soit 26 % de mieux.

Les rares triangles qu'on ne peut plus completer sont rendus tels quels, en
losange ou en simple triangle -- ils remplissent leur place, ce ne sont pas des
trous.

```bash
python -m boats.fleet photo.jpg -s 64 -g 5 -o output.png
```

### Arguments

| Argument | Description |
|----------|-------------|
| `image` | Chemin vers l'image source |
| `--output`, `-o` | Chemin du fichier de sortie (defaut: `fleet_output.png`) |
| `--background`, `-b` | Couleur du fond visible dans les jours (defaut: blanc) |
| `--size`, `-s` | Cote du triangle en pixels (defaut: 32) |
| `--angle`, `-a` | Angle de la maille en degres, 60 = equilateral (defaut: 60) |
| `--gap`, `-g` | Jour entre les tuiles en pixels (defaut: 2) |
| `--contrast` | Facteur de contraste applique avant echantillonnage (defaut: 1.0) |
| `--seed` | Graine pour departager les bateaux a egale distance (defaut: 0) |
| `--supersample` | Facteur de surechantillonnage pour l'anticrenelage (defaut: 2) |

### Exemples

```bash
# Mosaique fidele aux couleurs de la photo
python -m boats.fleet photo.jpg -s 64 -g 5

# Maille cisaillee, bateaux penches, trame fine
python -m boats.fleet photo.jpg -s 22 -a 75 -g 1

# Grosses tuiles detachees sur fond sombre
python -m boats.fleet photo.jpg -s 40 -g 3 -b "#1b1b2a"
```

---

# Cloth

Une couverture de survie en mylar, rendue en WebGL. La feuille se souleve sous
le curseur et claque au clic, comme le fait le film aluminise quand on le
touche. Pas de dependance a installer : ouvrez `cloth/index.html` dans un
navigateur, three.js vient du CDN.

## Principe

Le film est un plan de 200 x 200 segments dont la hauteur est calculee dans le
vertex shader, greffe sur un `MeshPhysicalMaterial` par `onBeforeCompile`. Trois
couches s'y additionnent :

- **Les plis.** Un bruit fractal *ridged* : on replie le bruit autour de zero
  puis on eleve le resultat a la puissance trois, ce qui transforme des collines
  lisses en aretes vives. Quatre octaves, chacune tournee par rapport a la
  precedente pour eviter les alignements sur les axes.
- **Le survol.** Une bosse gaussienne suit le curseur, doublee d'une vibration
  fine qui s'amortit avec la distance.
- **Les impacts.** Chaque clic pousse une onde dans un tableau de cinq, un front
  qui s'eloigne du point de contact et s'eteint en deux secondes.

Les normales sont analytiques : la hauteur est evaluee trois fois par sommet,
au point et a deux pas d'epsilon, et la normale sort du produit des derivees.
C'est ce qui donne des aretes nettes plutot que le rendu mou d'une normale
interpolee.

Le materiau est metallique pur, sans texture de couleur : ce qu'on voit est le
reflet de la piece. Elle est peinte a la main dans un canvas equirectangulaire
-- une bande froide, une bande ambree pour la face doree, un debord orange de
secours -- puis convolue par `PMREMGenerator`. Une carte d'epaisseur procedurale
alimente l'iridescence, sans quoi le film n'aurait qu'une seule teinte au lieu
du chatoiement du mylar.

Le releve affiche des valeurs reelles : le point de contact en centimetres sur
un panneau de 210 x 160 cm, et la fleche en millimetres.
