#!/usr/bin/env python3
"""Pixelise une image en tuiles "bateau" formees de trois triangles equilateraux."""

import argparse
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from riso import RISO_COLORS, parse_color

# Matrice de Bayer 4x4 ramenee dans [-0.5, 0.5[ pour le tramage ordonne
BAYER4 = (np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float32) + 0.5) / 16.0 - 0.5


def luminance(color: tuple[int, int, int]) -> float:
    """Luminance perceptuelle d'une couleur RGB."""
    r, g, b = color
    return 0.299 * r + 0.587 * g + 0.114 * b


def build_levels(paper: tuple[int, int, int], inks: list, n_levels: int) -> list:
    """Rampe d'encrage du papier vers la superposition complete des encres.

    Chaque encre monte en couverture a son tour, en chevauchant la precedente :
    papier -> encre claire -> les deux -> superposition dense. La couverture
    partielle correspond a une trame plus ou moins serree en risographie.
    """
    inks = sorted(inks, key=luminance, reverse=True)  # la plus claire imprime en premier
    k = len(inks)
    levels = []
    for i in range(n_levels):
        t = i / max(1, n_levels - 1)
        color = [float(v) for v in paper]
        for j, ink in enumerate(inks):
            start, end = j / (k + 1), (j + 2) / (k + 1)
            cover = min(1.0, max(0.0, (t - start) / (end - start)))
            for c in range(3):
                color[c] *= (255 - cover * (255 - ink[c])) / 255
        levels.append(tuple(int(round(v)) for v in color))
    return levels


def lattice(width: float, height: float, side: float) -> tuple[dict, float]:
    """Maille de triangles equilateraux couvrant la surface, avec une marge.

    Un sommet est repere par (rangee, colonne) entiers, les rangees impaires
    etant decalees d'un demi-cote. Chaque triangle est le triplet de ses sommets.
    """
    row_h = side * math.sqrt(3) / 2
    tris = {}
    for r in range(-2, int(math.ceil(height / row_h)) + 2):
        for i in range(-2, int(math.ceil(width / side)) + 2):
            # Le sommet oppose a la base tombe une colonne plus loin une rangee sur deux
            j = i if r % 2 == 0 else i + 1
            k = i + 1 if r % 2 == 0 else i
            tris[(r, i, "D")] = ((r, i), (r, i + 1), (r + 1, j))
            tris[(r, i, "U")] = ((r + 1, i), (r + 1, i + 1), (r, k))
    return tris, row_h


def vertex_key(vertex: tuple) -> tuple[int, int]:
    """Coordonnees entieres d'un sommet, en demi-cotes et en rangees.

    L'enveloppe convexe se calcule sur ces entiers : les produits vectoriels y
    sont exacts, donc les sommets alignes du grand cote d'un trapeze sont
    toujours elimines. En flottant ils survivaient parfois, et `inset` renvoyait
    alors None sur des cotes paralleles -- la tuile disparaissait.
    """
    r, i = vertex
    return (2 * i + (r % 2), r)


def vertex_pos(vertex: tuple, side: float, row_h: float) -> tuple[float, float]:
    """Position en pixels d'un sommet de la maille."""
    kx, ky = vertex_key(vertex)
    return (kx * side / 2, ky * row_h)


def strip_tiling(tris: dict, side: float, row_h: float, aligned: bool) -> tuple[list, dict]:
    """Pavage de depart : chaque bande horizontale est decoupee en triplets consecutifs.

    Trois triangles voisins forment toujours un trapeze, donc ce decoupage est
    valide par construction et ne laisse aucun triangle orphelin.

    Sans melange, on decale les bandes d'un demi-motif (`aligned` faux) : sinon un
    bateau et son inverse se soudent visuellement en hexagone. Avec melange c'est
    au contraire l'alignement qu'il faut, car ce sont precisement ces hexagones
    qui offrent d'autres decoupages.
    """
    by_row = {}
    for t in tris:
        by_row.setdefault(t[0], []).append(t)

    tiles, tile_of = [], {}
    for r, strip in sorted(by_row.items()):
        strip.sort(key=lambda t: sum(vertex_pos(v, side, row_h)[0] for v in tris[t]))
        for a in range(0 if aligned else r % 2, len(strip) - 2, 3):
            group = list(strip[a:a + 3])
            for t in group:
                tile_of[t] = len(tiles)
            tiles.append(group)
    return tiles, tile_of


def triangle_adjacency(tris: dict) -> dict:
    """Voisins par arete de chaque triangle de la maille."""
    edges = {}
    for tid, verts in tris.items():
        for a, b in ((verts[0], verts[1]), (verts[1], verts[2]), (verts[2], verts[0])):
            edges.setdefault(frozenset((a, b)), []).append(tid)
    adj = {t: [] for t in tris}
    for shared in edges.values():
        if len(shared) == 2:
            adj[shared[0]].append(shared[1])
            adj[shared[1]].append(shared[0])
    return adj


# Les 20 facons de choisir 3 triangles parmi les 6 d'une paire de bateaux
TRIPLE_MASKS = [(1 << i) | (1 << j) | (1 << k)
                for i in range(6) for j in range(i + 1, 6) for k in range(j + 1, 6)]
FULL_MASK = (1 << 6) - 1


def connected(mask: int, neighbours: list) -> bool:
    """Le sous-ensemble decrit par `mask` est-il connexe ?"""
    seen = mask & -mask
    while True:
        grown, rest = seen, seen
        while rest:
            bit = rest & -rest
            grown |= neighbours[bit.bit_length() - 1] & mask
            rest ^= bit
        if grown == seen:
            return seen == mask
        seen = grown


def mix_orientations(tiles: list, tile_of: dict, adj: dict, passes: int, rng) -> None:
    """Melange les orientations en recoupant des paires de bateaux voisins, sur place.

    Deux bateaux adjacents forment six triangles, que l'on redecoupe en deux
    triplets connexes tires au hasard. Comme tout triplet connexe est un trapeze,
    le pavage reste complet et exclusivement compose de bateaux : aucun triangle
    ne peut se retrouver orphelin, contrairement a un remplissage glouton.
    """
    # Les bouts de bande incomplets, hors du cadre, n'appartiennent a aucun bateau
    order = [t for t in adj if t in tile_of]
    for _ in range(passes):
        rng.shuffle(order)
        for tri in order:
            first = tile_of[tri]
            others = [tile_of[u] for u in adj[tri] if tile_of.get(u, first) != first]
            if not others:
                continue
            second = rng.choice(others)
            if len(tiles[first]) != 3 or len(tiles[second]) != 3:
                continue

            group = tiles[first] + tiles[second]
            index = {t: n for n, t in enumerate(group)}
            neighbours = [0] * 6
            for n, t in enumerate(group):
                for u in adj[t]:
                    if u in index:
                        neighbours[n] |= 1 << index[u]

            splits = [m for m in TRIPLE_MASKS
                      if connected(m, neighbours) and connected(FULL_MASK ^ m, neighbours)]
            mask = rng.choice(splits)
            tiles[first] = [group[n] for n in range(6) if mask >> n & 1]
            tiles[second] = [group[n] for n in range(6) if not mask >> n & 1]
            for t in tiles[first]:
                tile_of[t] = first
            for t in tiles[second]:
                tile_of[t] = second


def convex_hull(points: list) -> list:
    """Enveloppe convexe (parcours monotone d'Andrew), sommets alignes exclus."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and cross(out[-2], out[-1], p) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]

    return half(pts) + half(pts[::-1])


def boat_tiles(width: float, height: float, side: float,
               mix: int = 8, seed: int = 0) -> tuple[list, np.ndarray]:
    """Pave la surface de bateaux : des trapezes de trois triangles equilateraux.

    Trois triangles connexes de la maille forment toujours un trapeze -- c'est le
    seul triamant. N'importe quelle partition de la maille en triplets connexes
    donne donc un pavage de bateaux ; il reste a en choisir une qui varie les
    orientations, ce que fait `mix_orientations`.
    """
    tris, row_h = lattice(width, height, side)
    tiles, tile_of = strip_tiling(tris, side, row_h, aligned=mix > 0)
    if mix > 0:
        mix_orientations(tiles, tile_of, triangle_adjacency(tris),
                         mix, random.Random(seed))

    polys, coords = [], []
    for tile in tiles:
        keys = {vertex_key(v) for t in tile for v in tris[t]}
        poly = [(kx * side / 2, ky * row_h) for kx, ky in convex_hull(list(keys))]
        polys.append(poly)
        # Centre en unites de maille, pour echantillonner la trame dans l'espace
        # de l'image : un index de tuile serait correle a son orientation
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        coords.append((cx / side, cy / row_h))
    return polys, np.array(coords)


def signed_area(poly: list) -> float:
    """Aire signee d'un polygone (positive ou negative selon le sens de parcours)."""
    n = len(poly)
    return sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
               for i in range(n)) / 2


def inset(poly: list, amount: float):
    """Retracte un polygone convexe d'une distance constante sur chacun de ses cotes.

    Chaque cote est translate vers l'interieur le long de sa normale, puis les
    nouveaux sommets sont les intersections des cotes voisins : le jour est ainsi
    de meme largeur partout, contrairement a une homothetie.
    """
    if amount <= 0:
        return poly
    n = len(poly)
    orientation = 1.0 if signed_area(poly) > 0 else -1.0

    edges = []
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        length = math.hypot(ex, ey)
        if length < 1e-9:
            return None
        nx, ny = -ey / length * orientation, ex / length * orientation
        edges.append((x1 + nx * amount, y1 + ny * amount, ex, ey))

    out = []
    for i in range(n):
        px, py, ex, ey = edges[i - 1]
        qx, qy, fx, fy = edges[i]
        denom = ex * fy - ey * fx
        if abs(denom) < 1e-9:
            return None
        t = ((qx - px) * fy - (qy - py) * fx) / denom
        out.append((px + ex * t, py + ey * t))

    # La tuile a disparu si le retrait a retourne le polygone
    if signed_area(out) * orientation <= 0:
        return None
    return out


def tile_colors(img: Image.Image, tiles: list, side: float,
                px_per_side: float = 6.0) -> np.ndarray:
    """Couleur moyenne de l'image sous chaque tuile.

    Les tuiles entierement hors cadre recoivent la couleur moyenne de l'image,
    faute de pixels a echantillonner.
    """
    # L'echantillonnage n'a pas besoin de la pleine resolution : ~6 px par cote suffit
    scale = min(1.0, px_per_side / side)
    sw, sh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    small = np.array(img.resize((sw, sh), Image.LANCZOS), dtype=np.float64)

    ids = Image.new("I", (sw, sh), 0)
    draw = ImageDraw.Draw(ids)
    for i, poly in enumerate(tiles):
        draw.polygon([(x * scale, y * scale) for x, y in poly], fill=i + 1)
    ids = np.array(ids).ravel()

    n = len(tiles) + 1
    counts = np.bincount(ids, minlength=n).astype(np.float64)
    empty = counts == 0
    counts[empty] = 1.0
    means = np.stack([
        np.bincount(ids, weights=small[:, :, c].ravel(), minlength=n) / counts
        for c in range(3)
    ], axis=1)
    means[empty] = small.reshape(-1, 3).mean(axis=0)
    return means[1:]  # l'index 0 correspond aux pixels non couverts


def quantize(means: np.ndarray, coords: np.ndarray, levels: list, dither: bool) -> np.ndarray:
    """Associe a chaque tuile un niveau d'encre selon sa luminosite."""
    lums = means @ np.array([0.299, 0.587, 0.114])

    # Etale la plage utile de l'image sur toute la rampe d'encrage
    low, high = np.percentile(lums, [2, 98])
    if high - low < 1e-6:
        high = low + 1.0
    pos = (high - np.clip(lums, low, high)) / (high - low) * (len(levels) - 1)

    if dither:
        cells = np.floor(coords).astype(int)
        pos = pos + BAYER4[cells[:, 1] % 4, cells[:, 0] % 4]

    return np.clip(np.rint(pos), 0, len(levels) - 1).astype(int)


def boat_print(
    image_path: str,
    output_path: str,
    inks: list,
    paper: tuple[int, int, int],
    side: float = 32.0,
    gap: float = 2.0,
    contrast: float = 1.2,
    n_levels: int = 6,
    mix: int = 8,
    seed: int = 0,
    dither: bool = True,
    supersample: int = 2,
) -> None:
    """Transforme une image en mosaique de bateaux."""
    img = Image.open(image_path).convert("RGB")
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    tiles, coords = boat_tiles(img.width, img.height, side, mix, seed)
    means = tile_colors(img, tiles, side)
    levels = build_levels(paper, inks, n_levels)
    indices = quantize(means, coords, levels, dither)

    ss = max(1, supersample)
    canvas = Image.new("RGB", (img.width * ss, img.height * ss), paper)
    draw = ImageDraw.Draw(canvas)
    for poly, idx in zip(tiles, indices):
        shape = inset(poly, gap / 2)
        if shape is None:
            continue
        draw.polygon([(x * ss, y * ss) for x, y in shape], fill=levels[idx])

    if ss > 1:
        canvas = canvas.resize((img.width, img.height), Image.LANCZOS)
    canvas.save(output_path)
    print(f"{len(tiles)} tuiles, {len(levels)} niveaux d'encre")
    print(f"Image sauvegardee: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Pixelise une image en tuiles 'bateau' (trois triangles equilateraux)"
    )
    parser.add_argument("image", help="Chemin vers l'image source")
    parser.add_argument("--output", "-o", default="boat_output.png", help="Fichier de sortie")
    parser.add_argument("--colors", "-c", default="#ff7aa2,#ffa26b",
                        help="Encres separees par des virgules: noms ou codes hex")
    parser.add_argument("--paper", "-p", default="#ffffff", help="Couleur du papier (defaut: blanc)")
    parser.add_argument("--size", "-s", type=float, default=32.0,
                        help="Cote du triangle en pixels (defaut: 32)")
    parser.add_argument("--gap", "-g", type=float, default=2.0,
                        help="Jour entre les tuiles en pixels (defaut: 2)")
    parser.add_argument("--contrast", type=float, default=1.2, help="Facteur de contraste (defaut: 1.2)")
    parser.add_argument("--levels", "-l", type=int, default=6,
                        help="Nombre de niveaux d'encrage, papier compris (defaut: 6)")
    parser.add_argument("--mix", "-m", type=int, default=8,
                        help="Passes de melange des orientations, 0 = bateaux tous horizontaux (defaut: 8)")
    parser.add_argument("--seed", type=int, default=0, help="Graine du melange (defaut: 0)")
    parser.add_argument("--no-dither", action="store_true", help="Desactive le tramage ordonne")
    parser.add_argument("--supersample", type=int, default=2,
                        help="Facteur de suréchantillonnage pour l'anticrenelage (defaut: 2)")

    args = parser.parse_args()

    if not Path(args.image).exists():
        print(f"Fichier introuvable: {args.image}")
        sys.exit(1)
    if args.mix < 0:
        print("Le nombre de passes de melange ne peut pas etre negatif")
        sys.exit(1)
    if args.levels < 2:
        print("Il faut au moins 2 niveaux d'encrage")
        sys.exit(1)
    if args.size < 3:
        print("La taille du triangle doit etre d'au moins 3 pixels")
        sys.exit(1)

    inks = [parse_color(c.strip()) for c in args.colors.split(",") if c.strip()]
    if not inks:
        print(f"Aucune encre valide. Couleurs disponibles: {', '.join(RISO_COLORS.keys())}")
        sys.exit(1)

    boat_print(
        args.image, args.output, inks, parse_color(args.paper),
        args.size, args.gap, args.contrast, args.levels, args.mix, args.seed,
        not args.no_dither, args.supersample,
    )


if __name__ == "__main__":
    main()
