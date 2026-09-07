#!/usr/bin/env python3
"""Transforme une photo en impression style risograph."""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

# Couleurs classiques d'encres risograph (R, G, B)
RISO_COLORS = {
    "red": (255, 72, 72),
    "blue": (0, 120, 191),
    "green": (0, 169, 92),
    "yellow": (255, 232, 0),
    "pink": (255, 72, 176),
    "orange": (255, 108, 47),
    "teal": (0, 131, 138),
    "black": (35, 31, 32),
    "gold": (187, 139, 65),
    "purple": (118, 60, 135),
}


def parse_color(color_str: str) -> tuple[int, int, int]:
    """Parse un nom de couleur ou un code hex en tuple RGB."""
    if color_str.lower() in RISO_COLORS:
        return RISO_COLORS[color_str.lower()]
    hex_str = color_str.lstrip("#")
    if len(hex_str) == 6:
        try:
            r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass
    print(f"Couleur invalide: {color_str}")
    print(f"Couleurs disponibles: {', '.join(RISO_COLORS.keys())} ou code hex (#RRGGBB)")
    sys.exit(1)


def halftone(gray: np.ndarray, dot_size: int, angle: float) -> np.ndarray:
    """Genere un masque de trame halftone a partir d'une image en niveaux de gris."""
    h, w = gray.shape
    # Creer une grille de coordonnees
    y_coords, x_coords = np.mgrid[0:h, 0:w]

    # Rotation des coordonnees pour l'angle de trame
    angle_rad = np.radians(angle)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    x_rot = x_coords * cos_a + y_coords * sin_a
    y_rot = -x_coords * sin_a + y_coords * cos_a

    # Position dans la cellule de trame (0 a 1)
    x_cell = (x_rot % dot_size) / dot_size - 0.5
    y_cell = (y_rot % dot_size) / dot_size - 0.5

    # Distance au centre de la cellule (forme le point circulaire)
    dist = np.sqrt(x_cell ** 2 + y_cell ** 2)

    # Rayon du point proportionnel a l'intensite (inverser: sombre = gros point)
    intensity = 1.0 - gray / 255.0
    radius = np.sqrt(intensity) * 0.7

    # Le pixel est "imprime" si la distance est inferieure au rayon
    mask = (dist < radius).astype(np.float32)

    return mask


def add_grain(mask: np.ndarray, amount: float = 0.03) -> np.ndarray:
    """Ajoute un grain subtil typique du risograph."""
    noise = np.random.normal(0, amount, mask.shape).astype(np.float32)
    result = np.clip(mask + noise, 0, 1)
    return result


def riso_print(
    image_path: str,
    color: tuple[int, int, int],
    output_path: str,
    dot_size: int = 8,
    contrast: float = 1.2,
    angle: float = 45.0,
) -> None:
    """Transforme une image en impression risograph."""
    img = Image.open(image_path).convert("RGB")

    # Ajuster le contraste
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    # Convertir en niveaux de gris
    gray = np.array(img.convert("L"), dtype=np.float32)

    # Generer la trame halftone
    mask = halftone(gray, dot_size, angle)

    # Ajouter du grain
    mask = add_grain(mask)

    # Appliquer la couleur riso
    h, w = mask.shape
    result = np.full((h, w, 4), 255, dtype=np.uint8)  # fond blanc avec alpha

    r, g, b = color
    result[:, :, 0] = (255 - mask * (255 - r)).astype(np.uint8)
    result[:, :, 1] = (255 - mask * (255 - g)).astype(np.uint8)
    result[:, :, 2] = (255 - mask * (255 - b)).astype(np.uint8)
    result[:, :, 3] = 255

    output = Image.fromarray(result, "RGBA")
    output.save(output_path)
    print(f"Image risograph sauvegardee: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Transforme une photo en impression risograph")
    parser.add_argument("image", help="Chemin vers l'image source")
    parser.add_argument("--color", "-c", default="blue", help="Couleur: nom ou code hex (defaut: blue)")
    parser.add_argument("--output", "-o", default="riso_output.png", help="Fichier de sortie (defaut: riso_output.png)")
    parser.add_argument("--dot-size", "-d", type=int, default=8, help="Taille des points de trame (defaut: 8)")
    parser.add_argument("--contrast", type=float, default=1.2, help="Facteur de contraste (defaut: 1.2)")
    parser.add_argument("--angle", type=float, default=45.0, help="Angle de la trame en degres (defaut: 45)")

    args = parser.parse_args()

    if not Path(args.image).exists():
        print(f"Fichier introuvable: {args.image}")
        sys.exit(1)

    color = parse_color(args.color)
    riso_print(args.image, color, args.output, args.dot_size, args.contrast, args.angle)


if __name__ == "__main__":
    main()
