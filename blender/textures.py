"""Procedural source images computed in numpy: fold fields, watercolour, paper.

Everything is seeded and tileable where it needs to be, and results are cached in
blender/.build because a rebuild otherwise repeats a lot of identical arithmetic.
"""

import math
import os

import bpy
import numpy as np

BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".build")


def _wrap(delta):
    """Shortest signed distance on the unit torus, which is what makes the fields tile."""
    return (delta + 0.5) % 1.0 - 0.5


def fold_field(size=1536, seed=3):
    """Simulate a crushed sheet as a sum of straight V-shaped creases at many scales.

    Returns height and crease-line maps. A crumple really is a network of straight
    ridges meeting at vertices, so unlike any smooth noise this keeps flat facets
    and sharp lines even after being blurred into a normal map.
    """
    path = os.path.join(BUILD_DIR, f"fold_v2_{size}_{seed}.npz")
    if os.path.exists(path):
        cached = np.load(path)
        return cached["height"], cached["lines"]
    gen = np.random.default_rng(seed)
    grid = np.linspace(0.0, 1.0, size, endpoint=False)
    x, y = np.meshgrid(grid, grid)
    height = np.zeros((size, size), dtype=np.float32)
    for count, length, amplitude in ((16, 0.75, 1.0), (70, 0.34, 0.5), (240, 0.15, 0.22), (800, 0.06, 0.08)):
        window = int(min(size, length * 3.2 * size))
        half = window // 2
        for _ in range(count):
            cx, cy = gen.uniform(0, 1, 2)
            angle = gen.uniform(0, math.pi)
            nx, ny = math.cos(angle), math.sin(angle)
            # Restrict work to a tile around the crease; indices wrap for seamlessness.
            ci, cj = int(cx * size), int(cy * size)
            rows = (np.arange(ci - half, ci + half) % size)[:, None]
            cols = np.arange(cj - half, cj + half) % size
            dx = _wrap(y[rows, cols] - cx)
            dy = _wrap(x[rows, cols] - cy)
            distance = dx * nx + dy * ny
            along = -dx * ny + dy * nx
            taper = np.clip(1.0 - (np.maximum(np.abs(dx), np.abs(dy)) / (half / size)) ** 4, 0.0, 1.0)
            mask = np.exp(-((along / (length * 0.55)) ** 2) - (distance / (length * 0.5)) ** 2) * taper
            sign = gen.choice([-1.0, 1.0])
            height[rows, cols] += (sign * amplitude * np.sqrt(distance * distance + 1.5e-6) * mask / length * 0.5).astype(np.float32)
    height -= height.min()
    height /= height.max()

    def laplacian(field):
        return np.roll(field, 1, 0) + np.roll(field, -1, 0) + np.roll(field, 1, 1) + np.roll(field, -1, 1) - 4.0 * field

    curvature = laplacian(height)
    scale = np.percentile(np.abs(curvature), 99.3)
    lines = np.clip(np.abs(curvature) / scale, 0.0, 1.0).astype(np.float32)
    os.makedirs(BUILD_DIR, exist_ok=True)
    np.savez_compressed(path, height=height, lines=lines)
    return height, lines


def float_image(name, channels):
    """Create a float Blender image whose R, G and B come from the given arrays."""
    existing = bpy.data.images.get(name)
    if existing is not None:
        return existing
    height, width = channels[0].shape
    image = bpy.data.images.new(name, width, height, alpha=False, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    rgba = np.ones((height, width, 4), dtype=np.float32)
    for index in range(3):
        rgba[..., index] = channels[index % len(channels)]
    image.pixels.foreach_set(rgba.ravel())
    image.pack()
    return image


def fold_image():
    """The shared fold field as an image: R height, G crease lines."""
    height, lines = fold_field()
    return float_image("fold_field", [height, lines, height])


def fractal(size, beta, seed, wide=1):
    """Tileable 1/f^beta noise by spectral synthesis, normalized to 0..1. Shape (size, size * wide)."""
    gen = np.random.default_rng(seed)
    fy = np.fft.fftfreq(size)[:, None] * size
    fx = np.fft.rfftfreq(size * wide)[None, :] * size * wide / wide
    radius = np.sqrt(fx * fx + fy * fy)
    radius[0, 0] = 1.0
    spectrum = radius ** (-beta / 2.0)
    phase = gen.uniform(0, math.tau, spectrum.shape)
    field = np.fft.irfft2(spectrum * np.exp(1j * phase), s=(size, size * wide))
    field = field - field.min()
    return field / field.max()
