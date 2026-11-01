"""The miniature world: hanging stars and threads first, the planet and sets after."""

import math
import os

import numpy as np

import bpy

import animations
import bake
import backgrounds
import export
import fox
import materials
import set_pieces
from generate_common import write_manifest
from sculpt import crumple, get_normals, get_verts, join, lathe, mesh_object, normalize, paint, rng, set_verts, smooth_path, smoothstep, solidify, srgb, sweep, wave_field

HERE = os.path.dirname(os.path.abspath(__file__))
TEXTURES = os.path.join(HERE, ".build", "textures")

GOLD_LIGHT = srgb("#FFE27A")
GOLD = srgb("#F8C63E")
GOLD_DEEP = srgb("#DE8E24")
GOLD_PEAK = srgb("#FFF3C4")


def star_outline(points, inner, radius, seed):
    """Alternating tip and notch positions, nudged by hand so no two arms match."""
    gen = rng(seed)
    outline = []
    for i in range(points * 2):
        angle = math.pi / 2 + i * math.pi / points + gen.uniform(-0.035, 0.035)
        length = radius * (1.0 if i % 2 == 0 else inner) * gen.uniform(0.95, 1.05)
        outline.append((math.cos(angle) * length, gen.uniform(-0.02, 0.02) * radius, math.sin(angle) * length))
    return np.array(outline)


def star_facets(outline, peak_height, tessellation):
    """Build a folded star: two facets per arm, front and back, with hard creases.

    Each triangle gets its own vertices, so creases stay sharp, and `tessellation`
    subdivides facets for the high mesh that carries the painted gradient.
    """
    count = len(outline)
    tip_bend = outline.copy()
    for i in range(0, count, 2):
        tip_bend[i, 1] += 0.05 * np.linalg.norm(outline[i])
    verts, faces, tones = [], [], []
    for side in (-1.0, 1.0):
        peak = np.array([0.0, side * peak_height, 0.0])
        for i in range(count):
            a = tip_bend[i]
            b = tip_bend[(i + 1) % count]
            bright = (i % 2 == 0) == (side < 0)
            # A flat triangle, tessellated as a barycentric grid.
            start = len(verts)
            rows = tessellation + 1
            index = {}
            for j in range(rows):
                for k in range(rows - j):
                    l = tessellation - j - k
                    position = (peak * l + a * j + b * k) / tessellation
                    index[(j, k)] = len(verts)
                    verts.append(position)
                    tones.append((bright, l / tessellation))
            for j in range(rows - 1):
                for k in range(rows - 1 - j):
                    if side < 0:
                        faces.append((index[(j, k)], index[(j + 1, k)], index[(j, k + 1)]))
                    else:
                        faces.append((index[(j, k)], index[(j, k + 1)], index[(j + 1, k)]))
                    if (j, k + 1) in index and (j + 1, k + 1) in index:
                        if side < 0:
                            faces.append((index[(j + 1, k)], index[(j + 1, k + 1)], index[(j, k + 1)]))
                        else:
                            faces.append((index[(j + 1, k)], index[(j, k + 1)], index[(j + 1, k + 1)]))
            del start
    return np.array(verts), faces, tones


def build_star(name, seed, inner=0.42, peak=0.17):
    """A folded gold star: painted facets over a real relief."""
    outline = star_outline(5, inner, 1.0, seed)
    verts, faces, tones = star_facets(outline, peak, 22)
    gen = rng(seed + 1)
    # Wear the sheet a little: long soft warps, so light rolls across each facet.
    verts = verts + normalize(verts + 1e-6) * 0.0
    high = mesh_object(f"{name}_high", verts, faces, smooth=False)
    colors = []
    wash = gen.uniform(-1, 1)
    for bright, height in tones:
        base = GOLD_LIGHT if bright else GOLD_DEEP
        peak_mix = height**2.2 * 0.4
        colors.append(base * (1 - peak_mix) + GOLD_PEAK * peak_mix)
    paint(high, np.array(colors) * (1.0 + 0.03 * wash))
    high.data.materials.append(materials.foil(f"{name}_foil"))
    verts, faces, _ = star_facets(outline, peak, 1)
    low = mesh_object(name, verts, faces, smooth=False)
    return high, low


def build_stars():
    """Paper stars and their threads, exported together for instancing."""
    star_a_high, star_a = build_star("star_a", 11)
    star_b_high, star_b = build_star("star_b", 23, inner=0.38, peak=0.2)
    jobs = [
        {"name": "star_a", "high": star_a_high, "low": star_a, "rect": (0.0, 0.0, 0.5, 1.0), "tris": 0, "extrusion": 0.02, "ray": 0.08, "angle": 25.0},
        {"name": "star_b", "high": star_b_high, "low": star_b, "rect": (0.5, 0.0, 1.0, 1.0), "tris": 0, "extrusion": 0.02, "ray": 0.08, "angle": 25.0},
    ]
    mesh = bake.bake_asset("stars", jobs, TEXTURES, size=512, metallic=0.8, separate=True)
    thread = sweep("thread", [[0.0, 0.0, 0.0], [0.0015, 0.0, -0.5], [0.0, 0.0, -1.0]], 1.0, sides=4, cap_start=False, cap_end=False)
    paint(thread, np.ones((len(thread.data.vertices), 3)))
    thread.data.materials.append(materials.bake_free_thread())
    export.export_glb("stars", [*mesh, thread])


def soften(samples):
    """Smooth a height profile, since feet should ride over dents rather than drop into each one."""
    values = np.asarray(samples)
    padded = np.pad(values, 3, mode="edge")
    return [round(float(v), 4) for v in np.convolve(padded, np.ones(7) / 7, mode="valid")]


def planet_profile(planet):
    """Radius of the bare planet along the Prince's walking line, at each 0.02 radians from the crown."""
    samples = []
    for step in range(56):
        angle = step * 0.02
        origin = np.array([math.sin(angle), 0.0, math.cos(angle)]) * 9.0
        hit, location, _, _ = planet.ray_cast(origin.tolist(), (-origin).tolist())
        samples.append(float(np.linalg.norm(location)) if hit else 3.2)
    return soften(samples)


def hill_profile(hill):
    """Height of the bare hill along the line the Prince and fox stand on, every 0.1 from x = -2."""
    samples = []
    for step in range(61):
        origin = (-2.0 + step * 0.1, -1.25, 20.0)
        hit, location, _, _ = hill.ray_cast(origin, (0.0, 0.0, -1.0))
        samples.append(float(location[2]) if hit else 1.7)
    return soften(samples)


def build_asteroid():
    """The planet, its volcanoes, chair and plants as one static GLB."""
    pieces = {
        "planet": set_pieces.build_asteroid(),
        "volcano_a": set_pieces.build_volcano("volcano_a", 0.86, 3.5, 0.62, 0.42, True),
        "volcano_b": set_pieces.build_volcano("volcano_b", 1.2, 4.0, 0.5, 0.36, True),
        "volcano_c": set_pieces.build_volcano("volcano_c", 0.78, 4.7, 0.42, 0.33, False),
        "chair": set_pieces.build_chair(0.55, 2.9),
    }
    pieces["vegetation"], pieces["bark"] = set_pieces.build_vegetation()
    layout = {
        "planet": ((0.0, 0.0, 0.75, 1.0), 26000, 0.08, 0.3),
        "vegetation": ((0.75, 0.625, 1.0, 1.0), 16000, 0.02, 0.06),
        "bark": ((0.75, 0.5, 1.0, 0.625), 2400, 0.03, 0.09),
        "volcano_a": ((0.75, 0.25, 0.875, 0.5), 2200, 0.05, 0.14),
        "volcano_b": ((0.875, 0.25, 1.0, 0.5), 2000, 0.05, 0.14),
        "volcano_c": ((0.75, 0.0, 0.875, 0.25), 1800, 0.05, 0.14),
        "chair": ((0.875, 0.0, 1.0, 0.25), 1400, 0.02, 0.06),
    }
    jobs = [{"name": n, "high": pieces[n], "rect": r, "tris": t, "extrusion": e, "ray": d} for n, (r, t, e, d) in layout.items()]
    # Measured on the bare planet: casting against the finished set would stand him on the grass tips.
    write_manifest("asteroid", {"groundStep": 0.02, "ground": planet_profile(pieces["planet"])})
    mesh = bake.bake_asset("asteroid", jobs, TEXTURES, size=2560, exclude_occlusion=("vegetation",))
    for group in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(group)
    for piece in pieces.values():
        bpy.data.objects.remove(piece)
    export.export_glb("asteroid", [mesh])


def build_rose():
    """The rose with its rig, plus the bare glass dome (its material is made at runtime)."""
    pieces = set_pieces.build_rose()
    jobs = [
        {"name": "bloom", "high": pieces["bloom"], "rect": (0.0, 0.0, 0.75, 1.0), "tris": 6000, "extrusion": 0.015, "ray": 0.04},
        {"name": "stem", "high": pieces["stem"], "rect": (0.75, 0.5, 1.0, 1.0), "tris": 700, "extrusion": 0.015, "ray": 0.04},
        {"name": "leaves", "high": pieces["leaves"], "rect": (0.75, 0.25, 1.0, 0.5), "tris": 800, "extrusion": 0.015, "ray": 0.04},
        {"name": "mound", "high": pieces["mound"], "rect": (0.75, 0.0, 1.0, 0.25), "tris": 3000, "extrusion": 0.03, "ray": 0.09},
    ]
    mesh = bake.bake_asset("rose", jobs, TEXTURES, size=1024)
    table = animations.rose_skeleton()
    armature = animations.build_armature("rose_rig", table, mesh)
    animations.skin_rose(mesh, table)
    animations.rose_clips(armature)
    write_manifest("rose", {"fps": animations.FPS, "clips": {"idle": 48, "touched": 24}})
    for piece in pieces.values():
        bpy.data.objects.remove(piece)
    dome = set_pieces.dome_mesh()
    export.export_glb("rose", [armature, mesh, dome], animated=True)


def build_fox():
    """The fox, baked and rigged."""
    body = fox.build_body()
    parts = fox.build_face(body)
    layout = {
        "body": (body, (0.0, 0.0, 1.0, 0.875), 19000, 0.03, 0.09),
        "nose": (parts["nose"], (0.0, 0.875, 0.125, 1.0), 150, 0.01, 0.03),
        "eye_L": (parts["eye_L"], (0.125, 0.875, 0.25, 1.0), 120, 0.01, 0.03),
        "eye_R": (parts["eye_R"], (0.25, 0.875, 0.375, 1.0), 120, 0.01, 0.03),
        "lid_L": (parts["lid_L"], (0.375, 0.875, 0.5, 1.0), 80, 0.01, 0.03),
        "lid_R": (parts["lid_R"], (0.5, 0.875, 0.625, 1.0), 80, 0.01, 0.03),
    }
    jobs = [{"name": n, "high": o, "rect": r, "tris": t, "extrusion": e, "ray": d} for n, (o, r, t, e, d) in layout.items()]
    mesh = bake.bake_asset("fox", jobs, TEXTURES, size=2560, exclude_occlusion=("eye_L", "eye_R", "lid_L", "lid_R"))
    table = fox.skeleton()
    armature = animations.build_armature("fox_rig", table, mesh)
    fox.skin(mesh, table)
    lengths = fox.clips(armature)
    bpy.data.objects.remove(body)
    for part in parts.values():
        bpy.data.objects.remove(part)
    export.export_glb("fox", [armature, mesh], animated=True)
    write_manifest("fox", {"fps": animations.FPS, "clips": lengths})


def build_hill():
    """The fox's knoll and its apple tree."""
    pieces = set_pieces.build_fox_hill()
    jobs = [
        {"name": "hill", "high": pieces["hill"], "rect": (0.0, 0.0, 0.75, 1.0), "tris": 16000, "extrusion": 0.09, "ray": 0.3},
        {"name": "tree", "high": pieces["tree"], "rect": (0.75, 0.8125, 1.0, 1.0), "tris": 3000, "extrusion": 0.03, "ray": 0.09},
        {"name": "canopy", "high": pieces["canopy"], "rect": (0.75, 0.5, 1.0, 0.75), "tris": 14000, "extrusion": 0.02, "ray": 0.06},
        {"name": "apples", "high": pieces["apples"], "rect": (0.75, 0.75, 1.0, 0.8125), "tris": 1200, "extrusion": 0.02, "ray": 0.06},
        {"name": "meadow", "high": pieces["meadow"], "rect": (0.75, 0.0, 1.0, 0.5), "tris": 20000, "extrusion": 0.02, "ray": 0.06},
    ]
    write_manifest("fox_hill", {"groundStart": -2.0, "groundStep": 0.1, "ground": hill_profile(pieces["hill"])})
    mesh = bake.bake_asset("fox_hill", jobs, TEXTURES, size=2560, exclude_occlusion=("meadow", "canopy"))
    for group in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(group)
    for piece in pieces.values():
        bpy.data.objects.remove(piece)
    export.export_glb("fox_hill", [mesh])


def build_bird():
    """Folded-paper birds with a real silhouette. Wing positions are replacement meshes, as in the rest of the film."""
    meshes = []
    for name, lift in (("bird_up", 0.55), ("bird_mid", 0.08), ("bird_down", -0.42)):
        verts = [
            (0.0, -0.62, 0.0),  # beak
            (-0.08, -0.12, -0.03),
            (0.08, -0.12, -0.03),
            (0.0, 0.12, 0.05),  # back
            (-0.15, 0.56, 0.0),  # tail
            (0.15, 0.56, 0.0),
            (0.0, 0.42, 0.02),
            (-0.84, 0.3, lift),  # wing tips
            (0.84, 0.3, lift),
            (-0.42, 0.34, lift * 0.45),
            (0.42, 0.34, lift * 0.45),
        ]
        faces = [(0, 1, 3), (0, 3, 2), (1, 7, 9), (1, 9, 3), (2, 3, 10), (2, 10, 8), (3, 4, 6), (3, 6, 5)]
        bird = mesh_object(name, np.array(verts), faces, smooth=False)
        paint(bird, np.tile(srgb("#F1E7D0"), (len(verts), 1)))
        bird.data.materials.append(materials.flat_paper("#F1E7D0"))
        meshes.append(bird)
    export.export_glb("birds", meshes)


def lantern(name, seed, radius, pleats, stripes, colors):
    """A folded honeycomb paper ball: a sphere of pleats, painted in bands."""
    rows, columns = 300, 900
    latitude = np.linspace(-math.pi / 2 + 0.01, math.pi / 2 - 0.01, rows)[:, None]
    azimuth = np.linspace(0.0, math.tau, columns, endpoint=False)[None, :]
    directions = np.stack([np.cos(latitude) * np.cos(azimuth), np.cos(latitude) * np.sin(azimuth), np.sin(latitude) * np.ones_like(azimuth)], axis=-1).reshape(-1, 3)
    faces = []
    for i in range(rows - 1):
        for j in range(columns):
            a = i * columns + j
            b = i * columns + (j + 1) % columns
            faces.append((a, b, b + columns, a + columns))
    flat_lat = np.repeat(latitude[:, 0], columns)
    flat_az = np.tile(azimuth[0], rows)
    # Sharp V pleats, in the way a honeycomb paper ball is folded, fading out toward the poles.
    wave = np.abs(((flat_az * pleats / math.pi) % 2.0) - 1.0)
    depth = 1.0 + 0.085 * (wave - 0.5) * np.cos(flat_lat) ** 0.6
    verts = directions * (depth * radius)[:, None]
    sphere = mesh_object(name, verts, faces)
    normals = get_normals(sphere)
    verts = crumple(verts, normals, 40, radius * 0.3, radius * 0.005, 6.0, seed)
    set_verts(sphere, verts)
    band_position = (flat_lat / math.pi + 0.5) * stripes + 0.06 * wave_field(directions, 4.0, seed + 1)
    band = np.floor(band_position).astype(int) % len(colors)
    palette = np.array([srgb(c) for c in colors])
    color = palette[band] * (0.66 + 0.46 * wave)[:, None]
    paint(sphere, color)
    sphere.data.materials.append(materials.crumpled(f"{name}_paper", tile=1.4 / radius, folds=0.6, fibre_strength=1.0, line_dark=0.28, line_rub=0.26))
    return sphere


def ring_card(name, inner, outer, tilt, color):
    """A flat cut-card ring for a planet."""
    profile = [(inner, 0.0), (outer, 0.0)]
    ring = lathe(name, smooth_path(np.array(profile), 6), 120)
    verts = get_verts(ring)
    jitter = wave_field(verts, 9.0, 66)
    radial = normalize(verts * np.array([1.0, 1.0, 0.0]))
    verts += radial * (jitter * 0.01 * outer * smoothstep(inner * 1.02, inner, np.hypot(verts[:, 0], verts[:, 1])))[:, None]
    c, s = math.cos(tilt), math.sin(tilt)
    set_verts(ring, verts @ np.array([[1, 0, 0], [0, c, -s], [0, s, c]]).T)
    solidify(ring, 0.02, 0.0)
    count = len(ring.data.vertices)
    paint(ring, np.broadcast_to(srgb(color), (count, 3)))
    ring.data.materials.append(materials.card(f"{name}_card"))
    return ring


def build_paper_planets():
    """The planets of the journey, each a differently folded paper ball."""
    pieces = {
        "planet_ochre": lantern("planet_ochre", 601, 1.0, 11, 7, ("#D9A93F", "#E8C877", "#B9812E")),
        "planet_rose": lantern("planet_rose", 611, 0.8, 9, 5, ("#B75C55", "#E6B8A0", "#8F3F42")),
        "planet_sea": lantern("planet_sea", 621, 1.25, 14, 9, ("#4E8E94", "#BFD6C7", "#2D6A73")),
        "planet_moss": lantern("planet_moss", 631, 0.62, 8, 4, ("#7FA257", "#CFD49A")),
        "planet_cream": lantern("planet_cream", 641, 0.9, 12, 3, ("#EFE3C6", "#D8C69D")),
    }
    ringed = lantern("planet_ring", 651, 0.72, 10, 5, ("#C78A4B", "#EBCF9F"))
    ring = ring_card("ring_card", 1.02, 1.5, 0.42, "#F0DFB8")
    pieces["planet_ring"] = join([ringed, ring], "planet_ring")
    pieces["planet_ring"].data.materials.append(materials.card("planet_ring_card"))
    rects = [(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 1.0, 0.5), (0.0, 0.5, 0.5, 1.0), (0.5, 0.5, 0.75, 0.75), (0.75, 0.5, 1.0, 0.75), (0.5, 0.75, 1.0, 1.0)]
    jobs = []
    for (name, high), rect in zip(pieces.items(), rects):
        # Free the name first: Blender would otherwise call the exported mesh "planet_ochre.001".
        high.name = f"{name}_high"
        low = high.copy()
        low.data = high.data.copy()
        link_object(low)
        low = decimated(low, 4200)
        low.name = name
        jobs.append({"name": name, "high": high, "low": low, "rect": rect, "tris": 0, "extrusion": 0.03, "ray": 0.1})
    meshes = bake.bake_asset("paper_planets", jobs, TEXTURES, size=2560, separate=True, smooth_unwrap=True)
    export.export_glb("paper_planets", meshes)


def link_object(obj):
    """Link a copied object into the scene."""
    bpy.context.scene.collection.objects.link(obj)


def decimated(obj, target):
    """Collapse-decimate an object in place."""
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if tris > target:
        modifier = obj.modifiers.new("reduce", "DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = target / tris
        from sculpt import apply_modifiers

        apply_modifiers(obj)
    return obj


REGISTRY = {
    "backdrops": backgrounds.build_backdrops,
    "stars": build_stars,
    "asteroid": build_asteroid,
    "rose": build_rose,
    "fox": build_fox,
    "fox_hill": build_hill,
    "birds": build_bird,
    "paper_planets": build_paper_planets,
}
