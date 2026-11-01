"""Small cut-paper parts made in bulk: grass blades, leaves, fur shingles.

Everything on the set is cut from the same stock as the Prince, so these are real flat
sheets rather than sculpted lumps. Parts are gathered into one mesh with a batch,
because hundreds of separate Blender objects would be slow for no benefit.
"""

import math

import numpy as np

from sculpt import mesh_object, normalize, paint, rng, smoothstep


class SheetBatch:
    """Collects grids of quads, each with its own colours, into a single mesh."""

    def __init__(self):
        self.verts = []
        self.colors = []
        self.faces = []
        self.count = 0

    def add_grid(self, points, colors):
        """Add an (rows, columns, 3) grid of points and matching colours."""
        rows, columns = points.shape[:2]
        base = self.count
        self.verts.append(points.reshape(-1, 3))
        self.colors.append(colors.reshape(-1, 3))
        for i in range(rows - 1):
            for j in range(columns - 1):
                a = base + i * columns + j
                self.faces.append((a, a + 1, a + columns + 1, a + columns))
        self.count += rows * columns

    def build(self, name):
        """Create the mesh object."""
        obj = mesh_object(name, np.vstack(self.verts), self.faces)
        paint(obj, np.vstack(self.colors))
        return obj


def blade(batch, root, up, lean, height, width, color_base, color_tip, seed):
    """One snipped blade: a pointed strip with a soft crease down its middle, bowed by its own weight."""
    gen = rng(seed)
    up = normalize(np.asarray(up, dtype=np.float64))
    lean = normalize(np.asarray(lean, dtype=np.float64) - up * float(np.dot(lean, up)))
    side = normalize(np.cross(up, lean))
    s = np.linspace(0.0, 1.0, 7)
    bow = gen.uniform(0.25, 0.7)
    spine = root + up[None, :] * (s * height)[:, None] + lean[None, :] * (s**2 * height * bow)[:, None] - up[None, :] * (s**3 * height * bow * 0.3)[:, None]
    half = width * (1.0 - s**1.6) * (0.75 + 0.25 * np.sin(s * math.pi))
    points = np.zeros((7, 3, 3))
    for j, v in enumerate((-1.0, 0.0, 1.0)):
        fold = lean * (0.0 if j == 1 else -0.35) * half[:, None]
        points[:, j] = spine + side[None, :] * (v * half)[:, None] + fold
    shade = (0.72 + 0.34 * s)[:, None, None]
    colors = (color_base[None, None, :] * (1 - s[:, None, None]) + color_tip[None, None, :] * s[:, None, None]) * shade
    batch.add_grid(points, np.broadcast_to(colors, (7, 3, 3)))


def tuft(batch, root, up, height, base_color, tip_color, seed, blades=7):
    """A clump of snipped blades fanned from one point."""
    gen = rng(seed)
    up = normalize(np.asarray(up, dtype=np.float64))
    helper = np.array([1.0, 0.0, 0.0]) if abs(up[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
    x = normalize(np.cross(up, helper))
    y = np.cross(up, x)
    for i in range(blades):
        angle = gen.uniform(0, math.tau)
        lean = x * math.cos(angle) + y * math.sin(angle)
        tone = gen.uniform(0.86, 1.1)
        blade(batch, root - up * 0.02, up, lean, height * gen.uniform(0.55, 1.1), height * gen.uniform(0.07, 0.11), base_color * tone, tip_color * tone, seed + i * 7 + 1)


def leaf(batch, center, outward, size, color, seed):
    """A folded paper leaf: an almond with a crease along its midrib, curling at the tip."""
    gen = rng(seed)
    outward = normalize(np.asarray(outward, dtype=np.float64))
    along = normalize(np.cross(outward, normalize(gen.normal(size=3))))
    side = np.cross(outward, along)
    s = np.linspace(-1.0, 1.0, 6)
    half = size * 0.42 * (1.0 - s**2) ** 0.7 + 0.002
    points = np.zeros((6, 3, 3))
    for j, v in enumerate((-1.0, 0.0, 1.0)):
        fold = outward * (size * 0.26 * abs(v) * (half / (size * 0.42)))[:, None]
        curl = -outward * (size * 0.32 * s**2)[:, None]
        points[:, j] = center + along[None, :] * (s * size)[:, None] + side[None, :] * (v * half)[:, None] + fold + curl
    shade = np.array([0.8, 1.0, 1.08])[None, :, None] * gen.uniform(0.9, 1.1)
    batch.add_grid(points, np.broadcast_to(color[None, None, :], (6, 3, 3)) * shade)


def shingle(batch, root, flow, normal, length, width, color, seed):
    """A torn scrap of paper laid over a surface like fur: pointed, tip lifted, edges uneven."""
    gen = rng(seed)
    side = normalize(np.cross(normal, flow))
    s = np.linspace(0.0, 1.0, 5)
    half = width * np.sin(np.minimum(s * 1.25 + 0.12, 1.0) * math.pi) ** 0.8 * (1.0 + gen.uniform(-0.2, 0.2, 5))
    half[-1] = 0.0015
    bend = gen.uniform(-0.25, 0.25)
    spine = root + flow[None, :] * (s * length)[:, None] + side[None, :] * (s**2 * length * bend)[:, None] + normal[None, :] * (0.002 + s**1.7 * length * 0.3)[:, None]
    points = np.zeros((5, 3, 3))
    for j, v in enumerate((-1.0, 0.0, 1.0)):
        points[:, j] = spine + side[None, :] * (v * half)[:, None] + normal[None, :] * (0.14 * half * (1.0 - abs(v)))[:, None]
    tone = (0.84 + 0.22 * smoothstep(0.0, 1.0, s))[:, None, None]
    batch.add_grid(points, np.broadcast_to(color[None, None, :], (5, 3, 3)) * tone)
