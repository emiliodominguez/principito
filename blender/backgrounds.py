"""Painted backdrops and cut-paper layers, computed as images.

The set's backdrop is the mottled sky of the reference: deep teal at the edges,
dusty blue below, a pale scumbled cloud behind the Prince, and small stars printed
onto the paper. It is a painting on a wall, which is why real shadows land on it.
"""

import math
import os

import bpy
import numpy as np

from sculpt import smoothstep
from textures import fractal

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".build", "backgrounds")


def hex_rgb(value):
    """Convert #rrggbb to a display-referred float array; painting happens in display space."""
    text = value.lstrip("#")
    return np.array([int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4)])


def mix(a, b, t):
    """Per-pixel lerp between colours or colour fields."""
    t = np.asarray(t)[..., None]
    return np.asarray(a) * (1.0 - t) + np.asarray(b) * t


def save(name, rgb, alpha=None):
    """Write an array as a PNG through Blender."""
    os.makedirs(OUT_DIR, exist_ok=True)
    height, width = rgb.shape[:2]
    image = bpy.data.images.new(name, width, height, alpha=alpha is not None)
    rgba = np.ones((height, width, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(rgb, 0, 1)
    if alpha is not None:
        rgba[..., 3] = np.clip(alpha, 0, 1)
    image.pixels.foreach_set(rgba[::-1].ravel())
    image.filepath_raw = os.path.join(OUT_DIR, f"{name}.png")
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def star_mask(x, y, cx, cy, radius, angle):
    """Five-pointed star coverage for pixel coordinates."""
    dx, dy = x - cx, y - cy
    a = np.arctan2(dy, dx) - angle
    r = np.hypot(dx, dy)
    sector = math.tau / 5.0
    folded = np.abs(((a + sector / 2) % sector) - sector / 2)
    edge = radius * (0.42 + 0.58 * np.clip(1.0 - folded / (sector / 2), 0, 1) ** 1.6)
    return smoothstep(edge + 1.5, edge - 1.5, r)


def print_stars(canvas, seed, count, size_range, color, opacity, vertical=(0.04, 0.96)):
    """Stamp small stars onto the paper, sampling the sheet behind so they feel printed."""
    gen = np.random.default_rng(seed)
    height, width = canvas.shape[:2]
    for _ in range(count):
        radius = gen.uniform(*size_range)
        cx = gen.uniform(0.02, 0.98) * width
        cy = gen.uniform(*vertical) * height
        pad = int(radius) + 4
        x0, x1 = max(int(cx) - pad, 0), min(int(cx) + pad, width)
        y0, y1 = max(int(cy) - pad, 0), min(int(cy) + pad, height)
        ys, xs = np.mgrid[y0:y1, x0:x1]
        mask = star_mask(xs, ys, cx, cy, radius, gen.uniform(0, math.tau))
        canvas[y0:y1, x0:x1] = mix(canvas[y0:y1, x0:x1], color, mask * opacity * gen.uniform(0.6, 1.0))


def universe(name, deep, mid, dusty, pale, ochre_stars, seed=2):
    """Paint a full wrap of sky; horizontally tileable noise, composed glow at the centre."""
    size = 1536
    width = size * 2
    y, x = np.mgrid[0:size, 0:width]
    u, v = x / width, y / size

    masses = fractal(size, 3.3, seed, wide=2)
    drift = fractal(size, 2.6, seed + 1, wide=2)
    scuff = fractal(size, 1.5, seed + 2, wide=2)
    tooth = fractal(size, 0.5, seed + 3, wide=2)

    # Pigment: the wash settles deep at the corners and goes dusty toward the lower third.
    canvas = mix(deep, mid, smoothstep(0.34, 0.68, masses))
    canvas = mix(canvas, dusty, smoothstep(0.42, 0.95, v) * smoothstep(0.2, 0.7, drift) * 0.72)

    # A pale cloud of opaque gouache, off-centre and irregular.
    glow = np.exp(-(((u - 0.5) / 0.24) ** 2) - ((v - 0.5) / 0.40) ** 2)
    glow += 0.42 * np.exp(-(((u - 0.40) / 0.13) ** 2) - ((v - 0.14) / 0.14) ** 2)
    cloud = smoothstep(0.12, 1.05, glow + (masses - 0.5) * 1.05 + (drift - 0.5) * 0.5)
    canvas = mix(canvas, pale, cloud ** 1.25 * 0.74)

    # Dry-brush scumble: broken flecks of pale paint dragged around the cloud's edge.
    dragged = smoothstep(0.42, 0.72, scuff + (drift - 0.5) * 0.4)
    band = smoothstep(0.04, 0.3, cloud) * smoothstep(0.9, 0.35, cloud)
    canvas = mix(canvas, pale, dragged * band * 0.22)

    # Backruns: thin darker lines where a wash dried, tracing level sets of the masses.
    level = np.abs(((masses * 7.0) % 1.0) - 0.5)
    canvas *= (1.0 - 0.05 * smoothstep(0.05, 0.0, level) * (1.0 - cloud))[..., None]

    # Corners fall away, like the edge of the light on a real wall.
    fall = 1.0 - 0.34 * smoothstep(0.26, 0.5, np.hypot((u - 0.5) * 1.1, (v - 0.5) * 0.55))
    canvas *= fall[..., None]

    # Paper tooth and speckle.
    canvas *= (0.955 + 0.09 * tooth)[..., None]
    speck = np.random.default_rng(seed + 4).uniform(0, 1, (size, width))
    canvas *= (1.0 - 0.28 * (speck > 0.9975))[..., None]

    print_stars(canvas, seed + 5, 90, (3.0, 8.0), hex_rgb("#CFE0DA"), 0.26)
    print_stars(canvas, seed + 6, 44, (7.0, 15.0), hex_rgb("#A9C4C2"), 0.24)
    print_stars(canvas, seed + 7, 36, (7.0, 15.0), hex_rgb(ochre_stars), 0.8)
    save(name, canvas)


def paper_sheet(name, seed, width, height, shape, face, edge):
    """A cut-out sheet with a pale torn fibre rim: `shape` is a field that is positive inside."""
    y, x = np.mgrid[0:height, 0:width]
    u, v = x / width, y / height
    wobble = fractal(height, 2.2, seed, wide=max(1, width // height))
    fine = fractal(height, 1.3, seed + 1, wide=max(1, width // height))
    wobble = wobble[: height, : width]
    fine = fine[: height, : width]
    field = shape(u, v) + (wobble - 0.5) * 0.1 + (fine - 0.5) * 0.012
    alpha = smoothstep(0.0, 0.006, field)
    rim = smoothstep(0.0, 0.006, field) * smoothstep(0.03, 0.012, field)
    wash = fractal(height, 2.8, seed + 2, wide=max(1, width // height))[: height, : width]
    color = mix(face * 0.86, face * 1.06, smoothstep(0.3, 0.7, wash))
    color = mix(color, edge, rim * 0.9)
    color *= (0.96 + 0.08 * fine)[..., None]
    # Inner soft shading: card curves slightly away from the light at its lower edge.
    color *= (1.0 - 0.14 * smoothstep(0.35, 0.95, v))[..., None]
    save(name, color, alpha)


def build_backdrops():
    """Paint every backdrop and paper layer."""
    universe("universe", hex_rgb("#1F4D5A"), hex_rgb("#46777F"), hex_rgb("#5E8FA6"), hex_rgb("#C5D5C9"), "#6A7428")
    universe("dusk", hex_rgb("#2F4F57"), hex_rgb("#7A8476"), hex_rgb("#B58E62"), hex_rgb("#F0D9A8"), "#8A6A28", seed=12)

    def cloud(u, v):
        # Scallops: the union of a few circles, as scissors would cut a storybook cloud.
        lobes = [(0.2, 0.7, 0.13), (0.35, 0.56, 0.17), (0.52, 0.48, 0.2), (0.68, 0.58, 0.16), (0.82, 0.7, 0.12)]
        inside = np.full_like(u, -1.0)
        for cx, cy, radius in lobes:
            inside = np.maximum(inside, radius - np.hypot((u - cx), (v - cy) * 0.5))
        flat = np.minimum(inside + 0.2, (0.82 - v) * 0.5) - 0.2
        return np.minimum(inside, 0.82 - v) if flat is None else np.minimum(inside * 2.0, (0.84 - v))

    def far_hills(u, v):
        return (v - 0.48 - 0.1 * np.sin(u * 7.3 + 1.0) - 0.05 * np.sin(u * 15.0)) * 1.6

    def near_hills(u, v):
        return (v - 0.62 - 0.14 * np.sin(u * 4.1 + 2.2) - 0.03 * np.sin(u * 19.0)) * 1.6

    paper_sheet("hills_far", 43, 2048, 1024, far_hills, hex_rgb("#C49A6A"), hex_rgb("#F2DFB8"))
    paper_sheet("hills_near", 47, 2048, 1024, near_hills, hex_rgb("#9A6F47"), hex_rgb("#E4C78F"))
    paper_sheet("cloud_a", 31, 2048, 1024, cloud, hex_rgb("#7FA6A8"), hex_rgb("#E6EBDD"))
    paper_sheet("cloud_b", 37, 2048, 1024, cloud, hex_rgb("#4F7F88"), hex_rgb("#C4D8D0"))
    paper_sheet("cloud_c", 41, 2048, 1024, cloud, hex_rgb("#F1E4C8"), hex_rgb("#FFF8E6"))
