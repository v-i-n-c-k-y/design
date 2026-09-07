# Design

Trois effets de pixelisation, du plus simple au plus construit.

| Dossier | Fichier | Effet |
|---------|---------|-------|
| `riso/` | `riso.py` | Trame halftone en une encre |
| `boats/` | `boat.py` | Pavage regulier en tuiles "bateau", duotone risograph |
| `boats/` | `fleet.py` | Pavage par croissance, couleurs de la photo |
| `cloth/` | `index.html` | Couverture de survie en mylar, WebGL interactif |
| `cloth/` | `specimens.html` | Planche d'essais : six films aux raideurs et iridescences differentes |

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

Une couverture de survie en mylar, simulee et rendue dans le navigateur. La
feuille se souleve sous le curseur et claque au clic, comme le fait le film
aluminise quand on le touche. Pas de dependance a installer : ouvrez
`cloth/index.html` dans un navigateur, three.js et cannon-es viennent du CDN.

## Principe

**La forme vient de la physique.** Une grille de 30 x 30 particules cannon-es,
tenue par trois familles de contraintes de distance : les liens en lignes et en
colonnes empechent le film de s'etirer, les diagonales l'empechent de cisailler
-- ce qui sinon le plisserait en losanges -- et des liens souples qui enjambent
le voisin immediat lui donnent sa raideur en flexion. Cette troisieme famille
est ce qui separe une soie qui coule d'un film qui tient ses plis : une
contrainte de distance resiste a l'etirement, mais pas du tout au pliage. Seuls
les quatre coins sont fixes, le reste pend sous une gravite douce. Une feuille parfaitement plane n'ayant aucune
raison de flamber d'un cote plutot que de l'autre, un souffle de bruit sur les
positions de depart tranche pour elle.

Rien n'entre en collision ici : le film n'est mu que par ses contraintes et par
les forces du curseur. La broadphase est donc remplacee par une classe vide,
sans quoi mille corps seraient testes deux a deux a chaque pas, pour rien.

**Les deux gestes partagent une meme gaussienne.** Le survol maintient une force
sous le curseur, le clic delivre la meme forme en une seule impulsion.

**Le relief fin est une carte de normales.** La simulation porte les grands
plis ; ce qu'elle ne peut pas porter, c'est le froissage laisse par le pliage en
pochette. Il est donc peint separement, par un bruit fractal *ridged* -- replie
autour de zero puis eleve au cube, ce qui transforme des collines lisses en
aretes vives -- puis derive en normales. Son intensite tient dans une seule
constante, `CLOTH.crinkle`.

**Le materiau est metallique pur**, sans texture de couleur : pour un metal la
teinte se regle par la reflectance, et celle-ci est celle de l'or. Ce qu'on voit
est donc surtout le reflet de l'environnement, et changer d'environnement suffit
a deplacer la couverture. La page en propose deux.

*Plein air* est un ciel construit en demi-flottant plutot que peint sur un
canvas : un canvas plafonne a 255, donc un soleil dessine dessus ne peut pas
etre plus lumineux que le ciel autour et ne jette aucun eclat. En virgule
flottante il le domine de deux ordres de grandeur, et c'est cela qui fait
etinceler le metal dehors. Trois autres traits font l'exterieur : le ciel occupe
tout l'hemisphere haut au lieu d'une lampe ponctuelle, il palit vers l'horizon,
et surtout la ligne d'horizon coupe net entre ciel et neve -- c'est elle qu'on
lit dans les plis d'un miroir et rien d'autre ne dit aussi vite "dehors". Le
soleil se tient derriere la camera, si bien qu'on voit son reflet dans le film
plutot que son disque.

*Abri* garde la piece d'origine, peinte a la main dans un canvas
equirectangulaire : une cle blanc chaud, une large bande ambree, un debord d'or
profond, et une seule retombee froide sans laquelle l'or s'aplatit en orange.

Les deux passent par `PMREMGenerator`. Basculer de l'une a l'autre echange
l'environnement, le fond, le jeu de lumieres, l'exposition -- le ciel est cent
fois plus lumineux qu'une lampe -- et la rugosite, car un miroir parfait sous ce
ciel devient illisible. Une carte d'epaisseur procedurale alimente
l'iridescence, tenue basse : trop forte, elle vire au vert et mange l'or.

Tous les reglages tiennent dans l'objet `CLOTH` en tete de script : taille de la
grille, masse, gravite, amortissement, force du survol, impulsion du clic, et
le relief residuel. Le releve affiche des valeurs reelles : le point de contact
en centimetres sur un panneau de 210 x 160 cm, et la fleche mesuree sur la
simulation.

## Planche d'essais

`cloth/specimens.html` met six fois le meme film cote a cote, dans une matrice :
en colonnes trois raideurs en flexion (8, 60, 400 N), en lignes deux niveaux
d'iridescence (0,15 et 0,85). Les six partent du meme pli initial et subissent
la meme brise, de sorte que ce qui les separe est bien le seul parametre que
l'axe annonce. La fleche affichee sous chaque tuile est mesuree sur la
simulation : la colonne souple monte a plusieurs fois la valeur de la colonne
raide, sans qu'on ait a y toucher.

Les six sont rendus dans **un seul contexte WebGL**. Les navigateurs en limitent
le nombre bien en dessous de ce qu'exigerait une grille de canvas separes, donc
la page tient un canvas unique en position fixe et dessine chaque echantillon
dans le rectangle de sa tuile, au ciseau. Les rectangles sont relus a chaque
image, ce qui fait suivre le defilement sans code supplementaire.

Une scene unique porte les six films, espaces de quatorze unites : chaque camera
ne voit que le sien, les autres tombent hors du champ. Les lumieres sont
directionnelles, donc une seule installation eclaire tout le monde quel que soit
l'endroit ou chaque film se trouve.

Les deux pages sont autonomes et se dupliquent quelques fonctions -- la piece
reflechie, les cartes de relief. C'est le prix pour que chaque fichier s'ouvre
seul dans un navigateur, sans serveur ni module a resoudre.
