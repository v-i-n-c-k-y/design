#!/usr/bin/env python3
"""Pixelise une image en bateaux que l'on fait croitre au plus pres de l'image.

Meme tuile que boat.py -- trois triangles adjacents -- mais un pavage construit
autrement. La flotte grandit de proche en proche : a chaque etape on prend le
triangle voisin des bateaux deja formes qui a le moins de degres de liberte,
c'est-a-dire le moins de bateaux encore formables, et on lui donne celui dont la
couleur s'ecarte le moins de la surface recouverte. Servir le plus contraint en
premier est ce qui evite de laisser des triangles orphelins, et avant de retenir
un bateau on verifie qu'il n'en condamne aucun autour de lui. Le hasard ne sert
qu'a departager des bateaux exactement aussi proches.

Un bateau n'a qu'une couleur pour trois triangles : la moyenne de l'aire de
l'image qu'il recouvre, celle qui minimise l'ecart. Aucune palette n'intervient,
ni dans la croissance ni au rendu. Ce qui reste de cet ecart est la distance du
bateau a l'image, et leur cumul donne la proximite du pavage.

La maille est un quadrillage de rectangles cisaille en losanges, chaque losange
etant coupe en deux triangles isoceles. Un triangle est repere par (i, j, o) :
colonne, rangee, et orientation dans son losange. Avec l'angle par defaut de 60
degres les triangles sont equilateraux et les bateaux sont des trapezes.
"""

import argparse
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from boat import convex_hull, inset, tile_colors
from riso import parse_color

# Un triangle a au plus 3 voisins, donc au plus 3 paires de voisins et 6 chaines
MAX_FREEDOM = 9


def triangle_nodes(tri: tuple) -> tuple:
    """Les trois noeuds de la maille qui delimitent un triangle.

    Le losange (i, j) a pour coins les noeuds (i, j), (i+1, j), (i+1, j+1) et
    (i, j+1) ; sa diagonale le coupe en deux triangles isoceles.
    """
    i, j, o = tri
    if o == 0:
        return ((i, j), (i + 1, j), (i, j + 1))
    return ((i + 1, j), (i + 1, j + 1), (i, j + 1))


def neighbours(tri: tuple) -> tuple:
    """Les trois triangles partageant une arete avec celui-ci.

    Un triangle d'orientation 0 touche son jumeau dans le meme losange, celui du
    losange du dessus et celui du losange de gauche ; symetriquement pour l'autre.
    """
    i, j, o = tri
    if o == 0:
        return ((i, j, 1), (i, j - 1, 1), (i - 1, j, 1))
    return ((i, j, 0), (i, j + 1, 0), (i + 1, j, 0))


def mesh(width: float, height: float, side: float, angle: float) -> tuple[set, callable]:
    """Triangles couvrant l'image, et la position en pixels d'un noeud (i, j).

    Le noeud (0, 0) est le coin haut-gauche de l'image. Les rangees se decalent
    de `cos(angle)` cote a chaque descente : c'est le cisaillement qui transforme
    le quadrillage de rectangles en maille de losanges.
    """
    shear = side * math.cos(math.radians(angle))
    rise = side * math.sin(math.radians(angle))

    def pos(node):
        i, j = node
        return (i * side + j * shear, j * rise)

    tris = set()
    for j in range(-1, int(math.ceil(height / rise)) + 1):
        first = int(math.floor(-j * shear / side)) - 1
        last = int(math.ceil((width - j * shear) / side)) + 1
        for i in range(first, last):
            for o in (0, 1):
                corners = [pos(n) for n in triangle_nodes((i, j, o))]
                if (max(x for x, _ in corners) >= 0 and min(x for x, _ in corners) <= width
                        and max(y for _, y in corners) >= 0
                        and min(y for _, y in corners) <= height):
                    tris.add((i, j, o))
    return tris, pos


def possible_boats(tri: tuple, free: set) -> list:
    """Les bateaux encore formables autour de ce triangle : son degre de liberte.

    Un bateau est un triplet de triangles adjacents. Il n'y a que deux facons
    d'en batir un autour de `tri` : lui adjoindre deux de ses voisins, ou un
    voisin et un voisin de ce voisin. Deux voisins de `tri` ne se touchant
    jamais, ces triplets sont tous distincts.
    """
    near = [u for u in neighbours(tri) if u in free]
    boats = []
    for n, first in enumerate(near):
        boats.extend((tri, first, second) for second in near[n + 1:])
        boats.extend((tri, first, far) for far in neighbours(first)
                     if far in free and far != tri)
    return boats


def is_orphan(tri: tuple, free: set, taken=frozenset()) -> bool:
    """Ce triangle n'a-t-il plus aucun bateau formable ?

    Inutile d'enumerer ses bateaux : il est orphelin s'il n'a plus de voisin
    libre, ou s'il n'en a qu'un dont il est lui-meme le seul voisin libre.
    Au-dela, deux voisins libres suffisent deja a faire un bateau.
    """
    near = [u for u in neighbours(tri) if u in free and u not in taken]
    if len(near) != 1:
        return not near
    return not any(w in free and w not in taken and w != tri
                   for w in neighbours(near[0]))


def orphans_created(boat, free: set) -> int:
    """Combien de triangles ce bateau condamnerait a rester seuls.

    Seul le voisinage a deux pas du bateau peut changer de degre de liberte :
    les voisins directs perdent des issues, et leurs propres voisins peuvent
    basculer par ricochet.
    """
    taken = frozenset(boat)
    checked, count = set(), 0
    for tri in boat:
        for near in neighbours(tri):
            if near not in free or near in taken:
                continue
            for around in (near,) + neighbours(near):
                if around in free and around not in taken and around not in checked:
                    checked.add(around)
                    count += is_orphan(around, free, taken)
    return count


def boat_color(boat, colors: dict) -> tuple:
    """Couleur d'un bateau et sa distance a la surface qu'il recouvre.

    Un bateau n'a qu'une couleur pour trois triangles : la moyenne, qui est
    justement celle qui minimise l'ecart a l'image. La distance est ce qui reste,
    l'ecart moyen entre cette couleur unique et les couleurs sous-jacentes, en
    unites RGB. Plus elle est faible, plus le bateau colle a l'image.
    """
    size = len(boat)
    reds = greens = blues = 0.0
    for tri in boat:
        red, green, blue = colors[tri]
        reds += red
        greens += green
        blues += blue
    mean = (reds / size, greens / size, blues / size)
    return mean, sum(math.dist(colors[t], mean) for t in boat) / size


def next_triangle(pool, distance: dict) -> tuple:
    """Le triangle a servir dans le lot le moins libre.

    Second temps d'un double ordre : le lot est deja celui de degre de liberte
    minimal, on y prend le triangle dont le meilleur bateau s'ecarte le moins de
    l'image.
    """
    return min(pool, key=lambda t: (distance.get(t, 0.0), t[1], t[0], t[2]))


def grow_fleet(tris: set, colors: dict, rng) -> tuple[list, list]:
    """Fait croitre la flotte a partir du triangle en haut a gauche.

    On garde en parallele les bateaux formes et les triangles a proximite, ceux
    situes a deux pas d'un bateau. Ce sont exactement ceux dont le degre de
    liberte peut avoir change, donc les seuls a reclasser apres chaque bateau, et
    les seuls a verifier pour ne condamner personne.

    Le triangle suivant est choisi sur un double ordre : le seau de degre de
    liberte le plus faible d'abord, puis a degre egal la plus courte distance a
    l'image.
    """
    free = set(tris)
    nearby, freedom, distance = set(), {}, {}
    buckets = [set() for _ in range(MAX_FREEDOM + 1)]

    def rank(tri):
        """(Re)classe un triangle de la frontiere : degre de liberte et distance."""
        known = freedom.pop(tri, None)
        if known is not None:
            buckets[known].discard(tri)
        distance.pop(tri, None)
        if tri in nearby:
            options = possible_boats(tri, free)
            freedom[tri] = len(options)
            buckets[len(options)].add(tri)
            distance[tri] = min((boat_color(b, colors)[1] for b in options), default=0.0)

    boats, orphans = [], []
    while free:
        # Premier ordre : le seau de degre de liberte le plus faible.
        # Sans frontiere, on demarre : premier bateau ou nouvel ilot
        pool = next((b for b in buckets if b), free)
        tri = next_triangle(pool, distance)

        options = possible_boats(tri, free)
        if options:
            # On ecarte d'abord les bateaux qui condamneraient un voisin, et on
            # choisit ensuite le plus proche de l'image parmi ceux qui restent
            scored = [(orphans_created(b, free), boat_color(b, colors)[1], b)
                      for b in options]
            best = min((loss, dist) for loss, dist, _ in scored)
            tied = [b for loss, dist, b in scored
                    if loss == best[0] and dist <= best[1] + 1e-12]
            # Le hasard ne tranche qu'entre bateaux exactement aussi proches
            boat = list(tied[0] if len(tied) == 1 else rng.choice(tied))
            boats.append(boat)
        else:
            boat = [tri] + [u for u in neighbours(tri) if u in free]
            orphans.append(boat)

        for t in boat:
            free.discard(t)
            nearby.discard(t)
            rank(t)

        # Tous les triangles a deux pas du bateau : c'est exactement l'ensemble
        # dont le degre de liberte a pu changer
        touched = set()
        for t in boat:
            for u in neighbours(t):
                if u in free:
                    touched.add(u)
                    touched.update(w for w in neighbours(u) if w in free)
        nearby.update(touched)
        for t in touched:
            rank(t)

    return boats, orphans


def fleet_print(
    image_path: str,
    output_path: str,
    background: tuple[int, int, int],
    side: float = 32.0,
    angle: float = 60.0,
    gap: float = 2.0,
    contrast: float = 1.2,
    seed: int = 0,
    supersample: int = 2,
) -> None:
    """Transforme une image en flotte de bateaux."""
    img = Image.open(image_path).convert("RGB")
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    tris, pos = mesh(img.width, img.height, side, angle)
    order = sorted(tris)
    # Trois fois plus fin que pour les tuiles : ce sont les triangles qu'on compare
    sampled = tile_colors(img, [[pos(n) for n in triangle_nodes(t)] for t in order],
                          side, px_per_side=12.0)
    colors = {t: tuple(c) for t, c in zip(order, sampled)}

    boats, orphans = grow_fleet(tris, colors, random.Random(seed))

    ss = max(1, supersample)
    canvas = Image.new("RGB", (img.width * ss, img.height * ss), background)
    draw = ImageDraw.Draw(canvas)

    spread = 0.0
    for tile in boats + orphans:
        nodes = {n for t in tile for n in triangle_nodes(t)}
        poly = [pos(n) for n in convex_hull(list(nodes))]
        mean, dist = boat_color(tile, colors)
        # Les triangles ont tous la meme aire : la distance du pavage est la
        # moyenne des distances des tuiles, ponderee par leur nombre de triangles
        spread += dist * len(tile)

        shape = inset(poly, gap / 2)
        if shape is None:
            continue
        draw.polygon([(x * ss, y * ss) for x, y in shape],
                     fill=tuple(int(round(v)) for v in mean))

    if ss > 1:
        canvas = canvas.resize((img.width, img.height), Image.LANCZOS)
    canvas.save(output_path)

    loose = sum(len(o) for o in orphans)
    print(f"{len(boats)} bateaux")
    print(f"{loose} triangles orphelins sur {len(tris)} ({100 * loose / len(tris):.2f}%)")
    print(f"Proximite du pavage: {spread / len(tris):.2f} "
          f"(ecart RGB moyen a l'image, 0 = exact)")
    print(f"Image sauvegardee: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Pixelise une image en bateaux qui croissent au plus pres de l'image"
    )
    parser.add_argument("image", help="Chemin vers l'image source")
    parser.add_argument("--output", "-o", default="fleet_output.png", help="Fichier de sortie")
    parser.add_argument("--background", "-b", default="#ffffff",
                        help="Couleur du fond visible dans les jours (defaut: blanc)")
    parser.add_argument("--size", "-s", type=float, default=32.0,
                        help="Cote du triangle en pixels (defaut: 32)")
    parser.add_argument("--angle", "-a", type=float, default=60.0,
                        help="Angle de la maille en degres, 60 = equilateral (defaut: 60)")
    parser.add_argument("--gap", "-g", type=float, default=2.0,
                        help="Jour entre les tuiles en pixels (defaut: 2)")
    parser.add_argument("--contrast", type=float, default=1.0,
                        help="Facteur de contraste applique avant echantillonnage (defaut: 1.0)")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine pour departager les bateaux a egale distance (defaut: 0)")
    parser.add_argument("--supersample", type=int, default=2,
                        help="Facteur de surechantillonnage pour l'anticrenelage (defaut: 2)")

    args = parser.parse_args()

    if not Path(args.image).exists():
        print(f"Fichier introuvable: {args.image}")
        sys.exit(1)
    if args.size < 3:
        print("La taille du triangle doit etre d'au moins 3 pixels")
        sys.exit(1)
    if not 20.0 <= args.angle <= 160.0:
        print("L'angle de la maille doit etre compris entre 20 et 160 degres")
        sys.exit(1)

    fleet_print(
        args.image, args.output, parse_color(args.background),
        args.size, args.angle, args.gap, args.contrast, args.seed, args.supersample,
    )


if __name__ == "__main__":
    main()
