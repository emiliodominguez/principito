"""The world's sculpted props: the asteroid and its miniatures, the rose, the fox's hill.

Everything starts from a coarse fused form, then gets pushed around by the same
hand-made operations as the puppets, and is painted per vertex before baking.
"""

import math

import numpy as np

import materials
from paper_craft import SheetBatch, leaf, tuft
from sculpt import (
    blob,
    crumple,
    fuse,
    get_normals,
    get_verts,
    icosphere,
    join,
    lathe,
    mesh_object,
    normalize,
    paint,
    relax,
    ribbon,
    rng,
    set_verts,
    smooth_path,
    smoothstep,
    solidify,
    srgb,
    sweep,
    thumb_dents,
    torn_edge,
    warp,
    wave_field,
)

PLANET_RADIUS = 3.2
ROSE_ANGLE = 0.86


GROUND = {"planet": None}


def on_ground(direction, offset=0.0):
    """The real surface along a direction from the planet's centre. The sculpt is lumpy, so nothing is planted on the ideal sphere."""
    direction = normalize(np.asarray(direction, dtype=np.float64))
    planet = GROUND["planet"]
    if planet is None:
        return direction * (PLANET_RADIUS + offset)
    hit, location, _, _ = planet.ray_cast((direction * 9.0).tolist(), (-direction).tolist())
    return direction * ((np.linalg.norm(location) if hit else PLANET_RADIUS) + offset)


def surface(angle, around=0.0, radius=PLANET_RADIUS):
    """A point on the planet: `angle` from the crown toward +X, `around` rotates about the crown axis."""
    # Blender coordinates: Z is up, Y is into the set (glTF -Z), X matches the runtime's X.
    direction = np.array([math.sin(angle) * math.cos(around), math.sin(angle) * math.sin(around), math.cos(angle)])
    return on_ground(direction, radius - PLANET_RADIUS)


def tilt_to(points, direction):
    """Rotate points authored around +Z so that +Z lands on `direction`."""
    z = normalize(np.asarray(direction, dtype=np.float64))
    helper = np.array([0.0, 1.0, 0.0]) if abs(z[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = normalize(np.cross(helper, z))
    y = np.cross(z, x)
    return np.asarray(points) @ np.stack([x, y, z], axis=0)


def planet_field(directions):
    """Radial height of the asteroid: lopsided lumps, shallow craters, volcano seats."""
    lumps = 0.16 * wave_field(directions, 1.6, 201) + 0.075 * wave_field(directions, 3.7, 202) + 0.028 * wave_field(directions, 9.0, 203)
    height = 1.0 + lumps / PLANET_RADIUS
    gen = rng(204)
    for _ in range(13):
        center = normalize(gen.normal(size=3))
        size = gen.uniform(0.1, 0.26)
        distance = np.arccos(np.clip(directions @ center, -1, 1)) / size
        bowl = np.exp(-(distance**2) * 1.7)
        lip = np.exp(-((distance - 1.15) ** 2) * 9.0)
        height += (-0.13 * bowl + 0.05 * lip) * size / 0.26 * 0.5
    return height


def build_asteroid():
    """A small clay world, dark teal below and warm mossy sand on top."""
    sphere = icosphere("asteroid", 7, 1.0)
    directions = normalize(get_verts(sphere))
    # The crown stays gently rounded, so the walkway across the top matches the runtime's spherical path.
    calm = smoothstep(0.92, 0.45, directions[:, 2])
    height = 1.0 + (planet_field(directions) - 1.0) * (0.22 + 0.78 * calm)
    # A level seat for the rose, so the mound and the rim of the bell can sit true.
    rose = np.array([math.sin(ROSE_ANGLE), 0.0, math.cos(ROSE_ANGLE)])
    seat = smoothstep(0.42, 0.26, np.arccos(np.clip(directions @ rose, -1.0, 1.0)))
    height = height * (1.0 - seat) + seat
    verts = directions * height[:, None] * PLANET_RADIUS
    set_verts(sphere, verts)
    planet = fuse([sphere], 0.021, "asteroid", 2)
    verts = get_verts(planet)
    normals = get_normals(planet)
    verts = thumb_dents(verts, normals, 260, 0.17, 0.034, 205)
    verts = warp(verts, 0.012, 11.0, 206)
    set_verts(planet, verts)

    directions = normalize(verts)
    up = directions[:, 2]
    # The torn sheets are cut by the shader. This paint only dims them toward the shadowed underside.
    fall = smoothstep(0.5, -0.35, up)[:, None]
    bottom = smoothstep(0.05, -0.7, up)[:, None]
    tone = np.ones_like(verts) * (1 - fall) + srgb("#8AA8A4")[None, :] * fall
    tone = tone * (1 - bottom) + srgb("#3F6E7A")[None, :] * bottom
    paint(planet, tone * (1.0 + 0.06 * wave_field(directions, 14.0, 209))[:, None])
    sheets = [
        (0.0, tuple(srgb("#7E9E50"))),
        (0.44, tuple(srgb("#8DAC5A"))),
        (0.52, tuple(srgb("#9CB662"))),
        (0.6, tuple(srgb("#CDB57A"))),
    ]
    GROUND["planet"] = planet
    planet.data.materials.append(materials.crumpled("planet_paper", tile=0.3, folds=0.6, fibre_strength=1.3, line_dark=0.2, line_rub=0.06, collage=(0.62, sheets)))
    return planet


def build_volcano(name, seat_angle, around, height, radius, active):
    """A little clay cone with a lip, seated on the planet."""
    profile = [
        (radius * 1.25, -0.08),
        (radius * 1.05, height * 0.1),
        (radius * 0.72, height * 0.48),
        (radius * 0.42, height * 0.86),
        (radius * 0.38, height * 1.0),
        (radius * 0.27, height * 1.02),
        (radius * 0.16, height * 0.7),
        (0.0, height * 0.66),
    ]
    cone = lathe(name, smooth_path(np.array(profile), 40), 64)
    cone = fuse([cone], 0.009, name, 3)
    verts = get_verts(cone)
    normals = get_normals(cone)
    verts = warp(verts, 0.016, 8.0, 210 + int(seat_angle * 10))
    verts = thumb_dents(verts, normals, 22, 0.045, 0.012, 213 + int(height * 100))
    set_verts(cone, verts)
    z = verts[:, 2] / height
    color = srgb("#8F7F72")[None, :] * (1 + 0.1 * wave_field(verts, 10.0, 214))[:, None]
    soot = smoothstep(0.6, 0.98, z)[:, None]
    color = color * (1 - soot) + srgb("#3F3A3D")[None, :] * soot
    if active:
        ember = smoothstep(0.9, 0.7, z) * smoothstep(radius * 0.33, radius * 0.18, np.hypot(verts[:, 0], verts[:, 1]))
        color = color * (1 - ember[:, None]) + srgb("#E2813A")[None, :] * ember[:, None]
    paint(cone, color)
    base = surface(seat_angle, around, PLANET_RADIUS - 0.03)
    set_verts(cone, tilt_to(get_verts(cone), base) + base)
    cone.data.materials.append(materials.crumpled(f"{name}_paper", tile=1.1, folds=0.85, fibre_strength=1.0, line_dark=0.45, line_rub=0.3))
    return cone


def build_chair(seat_angle, around):
    """The small wooden chair he moves for one more sunset. Pulp over wire, a bit wonky."""
    gen = rng(220)
    size = 0.3
    parts = []
    for x, y in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        top = 1.0 if y < 0 else 2.15
        parts.append(sweep("leg", [[x * 0.42 * size, y * 0.42 * size, 0.0], [x * 0.40 * size, y * 0.4 * size, top * size]], 0.032 * gen.uniform(0.9, 1.15), sides=8))
    seat = blob("seat", (0, 0, size * 1.02), (size * 0.55, size * 0.52, size * 0.075), 3)
    back = blob("back", (0, size * 0.4, size * 1.82), (size * 0.5, size * 0.07, size * 0.32), 3)
    parts.extend([seat, back])
    chair = fuse(parts, 0.0065, "chair", 2)
    verts = warp(get_verts(chair), 0.004, 16.0, 221)
    set_verts(chair, verts)
    paint(chair, np.broadcast_to(srgb("#A5693E"), verts.shape) * (1 + 0.14 * wave_field(verts, 22.0, 222))[:, None])
    base = surface(seat_angle, around, PLANET_RADIUS - 0.015)
    set_verts(chair, tilt_to(get_verts(chair), base) + base)
    chair.data.materials.append(materials.crumpled("chair_paper", tile=2.4, folds=0.6, fibre_strength=1.0, line_dark=0.35, line_rub=0.25))
    return chair


def planet_tree(leaves, trunks, seed, seat_angle, around):
    """A little baobab: a fat twisted-paper trunk with a few boughs and folded paper leaves at the tips."""
    gen = rng(seed)
    parts = [sweep("baobab", smooth_path(np.array([[0, 0, -0.08], [0.012, 0.01, 0.2], [0.0, -0.01, 0.46]]), 14), 0.075 + 0.055 * np.cos(np.linspace(0, 1.57, 14)), sides=14)]
    tips = []
    for k in range(6):
        a = k * 1.05 + gen.uniform(-0.2, 0.2)
        reach = gen.uniform(0.2, 0.3)
        tip = np.array([math.cos(a) * reach, math.sin(a) * reach, 0.56 + gen.uniform(0, 0.1)])
        parts.append(sweep("bough", smooth_path(np.array([[0, 0, 0.4], tip * np.array([0.5, 0.5, 0.92]), tip]), 8), np.linspace(0.042, 0.012, 8), sides=8))
        tips.append(tip)
    base = surface(seat_angle, around, PLANET_RADIUS - 0.04)
    tree = fuse(parts, 0.0072, f"baobab_{seed}", 2)
    verts = get_verts(tree)
    twist = np.sin(np.arctan2(verts[:, 1], verts[:, 0]) * 5.0 + verts[:, 2] * 11.0)
    verts = verts + normalize(verts * np.array([1.0, 1.0, 0.0])) * (0.012 * twist)[:, None]
    tone = srgb("#8B6A4A")[None, :] * (0.8 + 0.28 * (twist * 0.5 + 0.5))[:, None]
    paint(tree, tone)
    set_verts(tree, tilt_to(verts, base) + base)
    trunks.append(tree)
    for k, tip in enumerate(tips):
        world = tilt_to(tip[None, :], base)[0] + base
        for n in range(9):
            direction = normalize(gen.normal(size=3))
            tones = ("#6F9A4E", "#86A85A", "#5C8846")
            leaf(leaves, world + direction * 0.07, direction + normalize(base) * 0.7, gen.uniform(0.06, 0.1), srgb(tones[n % 3]), seed * 13 + k * 11 + n)


def build_vegetation():
    """Snipped paper grass and small baobabs, on the same stock as everything else."""
    gen = rng(230)
    sheets = SheetBatch()
    trunks = []
    greens = [("#55803F", "#92B25C"), ("#4C7A44", "#7FA653"), ("#638C45", "#A9BC63"), ("#46703F", "#739C4C")]
    for i in range(120):
        angle = gen.uniform(0.16, 1.8)
        around = gen.uniform(0, math.tau)
        position = surface(angle, around, PLANET_RADIUS - 0.02)
        base, tip = greens[i % 4]
        tuft(sheets, position, position, gen.uniform(0.15, 0.34), srgb(base) * 1.3, srgb(tip) * 1.3, 240 + i, blades=int(gen.integers(5, 9)))
    rose = surface(ROSE_ANGLE, 0.0, 1.0)
    tangent = normalize(np.cross(rose, np.array([0.0, 1.0, 0.0])))
    bitangent = np.cross(rose, tangent)
    for i in range(16):
        turn = i * math.tau / 16 + gen.uniform(-0.1, 0.1)
        direction = normalize(rose + (tangent * math.cos(turn) + bitangent * math.sin(turn)) * gen.uniform(0.24, 0.3))
        base, tip = greens[i % 4]
        tuft(sheets, on_ground(direction, -0.02), direction, gen.uniform(0.14, 0.24), srgb(base) * 1.3, srgb(tip) * 1.3, 960 + i, blades=6)
    for i, (angle, around) in enumerate(((1.0, 1.0), (1.3, 3.0), (0.86, 2.1), (1.3, 0.25))):
        planet_tree(sheets, trunks, 262 + i, angle, around)
    plants = sheets.build("vegetation_sheets")
    plants.data.materials.append(materials.crumpled("plant_paper", tile=5.0, folds=0.5, fibre_strength=1.0, line_dark=0.25, line_rub=0.25))
    bark = join(trunks, "vegetation_trunks")
    bark.data.materials.append(materials.crumpled("bark_paper", tile=3.0, folds=0.7, fibre_strength=1.0, line_dark=0.45, line_rub=0.25))
    return plants, bark


def petal_mesh(name, size, curl, cup, seed):
    """One rose petal: a rounded sheet, cupped, its lip rolled back."""
    gen = rng(seed)
    rows, cols = 22, 22
    verts = []
    for i in range(rows):
        s = i / (rows - 1)
        half = math.sin(math.pi * min(1.0, s * 0.92 + 0.08)) ** 0.62 * 0.55 * size
        for j in range(cols):
            t = j / (cols - 1) * 2 - 1
            x = t * half
            lift = s * size * 1.12
            bow = cup * (t * t) * size * 0.5 * (0.35 + s)
            roll = curl * size * (s**3.2) * (0.6 + 0.4 * t * t)
            verts.append((x, bow - roll * 0.9, lift - roll * 0.3 + 0.012 * math.sin(s * 9 + t * 3 + seed)))
    faces = []
    for i in range(rows - 1):
        for j in range(cols - 1):
            a = i * cols + j
            faces.append((a, a + cols, a + cols + 1, a + 1))
    petal = mesh_object(name, np.array(verts) + gen.normal(0, 0.0012, (rows * cols, 3)), faces)
    return petal


def place_petal(petal, turn, lean, height):
    """Rotate a petal to its position in the bloom."""
    verts = get_verts(petal)
    cl, sl = math.cos(lean), math.sin(lean)
    verts = verts @ np.array([[1, 0, 0], [0, cl, sl], [0, -sl, cl]]).T
    verts = verts + np.array([0.0, 0.0, 0.0])
    ct, st = math.cos(turn), math.sin(turn)
    verts = verts @ np.array([[ct, -st, 0], [st, ct, 0], [0, 0, 1]]).T
    set_verts(petal, verts + np.array([0.0, 0.0, height]))


def build_rose():
    """A single paper rose: spiralled petals, a bent stem, two leaves, each a part the rig can move."""
    gen = rng(280)
    bloom_height = 0.82
    rose_red = [srgb("#CC4A46"), srgb("#BE3F40"), srgb("#D85C50"), srgb("#AE3A3E")]
    petals = []
    total = 15
    for i in range(total):
        t = i / (total - 1)
        size = 0.11 + 0.23 * t**0.8
        turn = i * 2.399963 + gen.uniform(-0.15, 0.15)
        lean = 0.1 + 0.95 * t**1.5
        petal = petal_mesh(f"petal_{i}", size, 0.22 + 0.72 * t, 0.9 - 0.4 * t, 300 + i)
        place_petal(petal, turn, lean, bloom_height - 0.015 * t)
        verts = get_verts(petal)
        normals = get_normals(petal)
        verts = crumple(verts, normals, 14, 0.06, 0.0028, 5.0, 320 + i)
        set_verts(petal, verts)
        tone = rose_red[i % 4]
        depth = smoothstep(bloom_height + 0.02, bloom_height + 0.2, verts[:, 2])[:, None]
        colors = tone[None, :] * (0.82 + 0.34 * depth)
        solidify(petal, 0.005, 0.0)
        count = len(petal.data.vertices)
        paint(petal, np.resize(colors, (count, 3)))
        petals.append(petal)
    bloom = join(petals, "rose_bloom")
    bloom.data.materials.append(materials.crumpled("rose_paper", tile=5.0, folds=0.5, fibre_strength=0.8, line_dark=0.25, line_rub=0.12))

    stem_path = smooth_path(np.array([[0.0, 0.0, -0.03], [0.022, 0.012, 0.3], [-0.012, -0.012, 0.6], [0.0, 0.0, bloom_height + 0.02]]), 40)
    stem = sweep("stem", stem_path, np.linspace(0.021, 0.016, 40), sides=10)
    parts = [stem]
    for z, angle in ((0.29, 0.5), (0.47, 3.8), (0.2, 2.2)):
        thorn_dir = np.array([math.cos(angle), math.sin(angle), 0.2])
        base = np.array([0.012, 0.0, z])
        parts.append(sweep("thorn", [base, base + thorn_dir * 0.025, base + thorn_dir * 0.05], np.array([0.012, 0.007, 0.0015]), sides=6))
    sepal = blob("calyx", (0, 0, bloom_height - 0.02), (0.05, 0.05, 0.055), 3)
    parts.append(sepal)
    stem = fuse(parts, 0.0042, "rose_stem", 2)
    verts = get_verts(stem)
    paint(stem, np.broadcast_to(srgb("#4F7A3E"), verts.shape) * (1 + 0.1 * wave_field(verts, 22.0, 330))[:, None])
    stem.data.materials.append(materials.clay("stem_clay", thumb=0.15))

    leaves = []
    for i, (z, angle, length) in enumerate(((0.34, 0.3, 0.34), (0.52, 3.5, 0.28))):
        s = np.linspace(0.0, 1.0, 26)
        path = np.stack([s * length, np.zeros_like(s), 0.11 * length * np.sin(s * 2.4) - 0.07 * s * s], axis=1)
        widths = 0.1 * np.sin(s * math.pi) ** 0.8 * length / 0.3 + 0.002
        blade_part = ribbon(f"leaf_{i}", path, widths, across=9, ups=np.tile(np.array([0.0, 0.0, 1.0]), (26, 1)))
        verts = get_verts(blade_part)
        vein = np.abs(verts[:, 1]) / 0.1
        verts[:, 2] += 0.022 * vein - 0.008 * np.sin(verts[:, 0] * 36.0) * vein
        c, sn = math.cos(angle), math.sin(angle)
        verts = verts @ np.array([[c, -sn, 0], [sn, c, 0], [0, 0, 1]]).T + np.array([0.0, 0.0, z])
        set_verts(blade_part, verts)
        solidify(blade_part, 0.006, 0.0)
        count = len(blade_part.data.vertices)
        paint(blade_part, np.broadcast_to(srgb("#5E8C46"), (count, 3)))
        leaves.append(blade_part)
    leaf_part = join(leaves, "rose_leaves")
    leaf_part.data.materials.append(materials.crumpled("leaf_paper", tile=4.0, folds=0.5, fibre_strength=0.7, line_dark=0.3, line_rub=0.1))
    return {"bloom": bloom, "stem": stem, "leaves": leaf_part, "mound": build_rose_mound()}


def dome_mesh():
    """The glass bell: thin lathe with a small hand-pulled knob. Real thickness is left to the shader."""
    points = [(0.525, -0.1), (0.54, -0.02), (0.538, 0.03), (0.512, 0.06), (0.5, 0.12), (0.5, 0.7), (0.47, 0.95), (0.39, 1.14), (0.26, 1.28), (0.12, 1.355), (0.036, 1.38), (0.03, 1.4), (0.06, 1.44), (0.062, 1.48), (0.04, 1.51), (0.0, 1.52)]
    return lathe("dome", smooth_path(np.array(points), 80), 72)


def build_rose_mound():
    """A heaped ring of soil with a grooved seat, which the rim of the bell presses into."""
    mound = fuse([blob("rose_mound", (0, 0, -0.1), (0.68, 0.68, 0.175), 5)], 0.0075, "rose_mound", 2)
    verts = get_verts(mound)
    normals = get_normals(mound)
    # A groove where the rim of the bell presses in, with soil heaped against it on both sides.
    radial = np.hypot(verts[:, 0], verts[:, 1])
    verts[:, 2] += 0.022 * np.exp(-(((radial - 0.6) / 0.04) ** 2)) - 0.04 * np.exp(-(((radial - 0.525) / 0.026) ** 2))
    verts = warp(verts, 0.012, 12.0, 340)
    verts = thumb_dents(verts, normals, 40, 0.05, 0.008, 341)
    set_verts(mound, verts)
    paint(mound, srgb("#8DAC5A")[None, :] * (0.92 + 0.14 * smoothstep(-0.2, 0.1, verts[:, 2]))[:, None] * (1 + 0.06 * wave_field(verts, 16.0, 342))[:, None])
    mound.data.materials.append(materials.crumpled("mound_paper", tile=1.4, folds=0.72, fibre_strength=1.0, line_dark=0.26, line_rub=0.14))
    return mound


def build_meadow(hill_verts):
    """Dry paper grass and wheat over the knoll, kept clear of the line they stand on."""
    gen = rng(420)
    top = hill_verts[hill_verts[:, 2] > 0.5]
    sheets = SheetBatch()
    dry = [("#A8833B", "#E4C36E"), ("#8E8B46", "#CDBE68"), ("#B58F42", "#EBCF82"), ("#7F8444", "#B5B562")]
    made = 0
    while made < 240:
        spot = top[gen.integers(0, len(top))]
        if abs(spot[1] + 1.25) < 0.3 and abs(spot[0]) < 3.5:
            continue
        base, tip = dry[made % 4]
        tuft(sheets, spot, np.array([0.0, 0.0, 1.0]), gen.uniform(0.16, 0.4), srgb(base) * 1.3, srgb(tip) * 1.3, 430 + made, blades=int(gen.integers(5, 9)))
        made += 1
    wheat_gold = srgb("#E0BC62")
    for i in range(70):
        spot = top[gen.integers(0, len(top))]
        if abs(spot[1] + 1.25) < 0.4 and abs(spot[0]) < 3.5:
            continue
        height = gen.uniform(0.44, 0.74)
        lean = np.array([gen.uniform(-0.08, 0.08), gen.uniform(-0.08, 0.08), 0.0])
        stalk = np.array([spot + lean * s * s + np.array([0.0, 0.0, height * s]) for s in np.linspace(0, 1, 6)])
        points = np.stack([stalk + np.array([-0.006, 0.0, 0.0]), stalk + np.array([0.006, 0.0, 0.0])], axis=1)
        sheets.add_grid(points, np.broadcast_to(wheat_gold * 0.72, (6, 2, 3)))
        for k in range(9):
            at = stalk[-1] + np.array([0.0, 0.0, k * 0.022 - 0.02]) + lean * 0.3 * k * 0.1
            direction = normalize(np.array([math.cos(k * 2.4), math.sin(k * 2.4), 0.8]))
            leaf(sheets, at + direction * 0.018, -direction, 0.02, wheat_gold * gen.uniform(0.9, 1.08), 460 + i * 11 + k)
    meadow = sheets.build("meadow")
    meadow.data.materials.append(materials.crumpled("meadow_paper", tile=5.0, folds=0.5, fibre_strength=1.0, line_dark=0.25, line_rub=0.25))
    return meadow


def build_fox_hill():
    """A warm clay knoll on a floating base, with a small apple tree and paper grass."""
    r = 4.4
    base = icosphere("hill", 6, 1.0)
    directions = normalize(get_verts(base))
    profile = np.where(directions[:, 2] > 0, 0.40, 0.72)
    field = 0.06 * wave_field(directions, 2.3, 400) + 0.03 * wave_field(directions, 6.0, 401)
    verts = directions * (r * (1 + field))[:, None] * np.stack([np.ones(len(directions)), np.ones(len(directions)) * 0.86, profile], axis=1)
    set_verts(base, verts)
    hill = fuse([base], 0.03, "fox_hill", 2)
    verts = get_verts(hill)
    normals = get_normals(hill)
    verts = thumb_dents(verts, normals, 120, 0.3, 0.032, 402)
    verts = warp(verts, 0.012, 9.0, 403)
    set_verts(hill, verts)
    top = smoothstep(-0.2, 0.9, verts[:, 2])[:, None]
    tone = np.ones_like(verts) * top + srgb("#6E5A52")[None, :] * (1 - top)
    paint(hill, tone * (1 + 0.06 * wave_field(verts, 7.0, 405))[:, None])
    fields = [
        (0.0, tuple(srgb("#C4954A"))),
        (0.44, tuple(srgb("#D3A958"))),
        (0.54, tuple(srgb("#E2BF70"))),
    ]
    hill.data.materials.append(materials.crumpled("hill_paper", tile=0.28, folds=0.6, fibre_strength=1.3, line_dark=0.2, line_rub=0.06, collage=(0.5, fields)))

    # An old apple tree: twisted paper trunk, spreading boughs, clusters of folded leaves.
    gen = rng(408)
    _, ground, _, _ = hill.ray_cast((-1.9, 1.5, 20.0), (0.0, 0.0, -1.0))
    planted = np.array([-1.9, 1.5, ground[2] - 0.05])
    trunk = sweep("trunk", smooth_path(np.array([[0, 0, -0.14], [0.05, 0.02, 0.45], [-0.06, 0, 0.95], [0.04, 0.02, 1.32]]), 26), 0.1 + 0.11 * np.exp(-np.linspace(0, 5, 26)), sides=18)
    boughs = [trunk]
    ends = []
    for k, (a, z, length, rise) in enumerate(((0.3, 0.85, 0.95, 0.5), (2.2, 0.98, 0.9, 0.56), (3.9, 1.1, 0.8, 0.6), (5.3, 1.2, 0.72, 0.56), (1.2, 1.3, 0.55, 0.72))):
        tip = np.array([math.cos(a) * length, math.sin(a) * length, z + rise])
        mid = np.array([tip[0] * 0.5, tip[1] * 0.5, z + rise * 0.3])
        boughs.append(sweep(f"bough_{k}", smooth_path(np.array([[0, 0, z], mid, tip]), 14), np.linspace(0.075, 0.018, 14), sides=10))
        ends.append((tip, mid))
    tree = fuse(boughs, 0.0095, "tree", 2)
    verts = get_verts(tree)
    twist = np.sin(np.arctan2(verts[:, 1], verts[:, 0]) * 6.0 + verts[:, 2] * 9.0 + wave_field(verts, 3.0, 406) * 1.4)
    verts = verts + normalize(verts * np.array([1.0, 1.0, 0.0])) * (0.016 * twist * smoothstep(1.5, 0.3, verts[:, 2]))[:, None]
    paint(tree, srgb("#7E5A40")[None, :] * (0.7 + 0.42 * (twist * 0.5 + 0.5))[:, None])
    set_verts(tree, verts + planted)
    tree.data.materials.append(materials.crumpled("tree_paper", tile=2.2, folds=0.8, fibre_strength=1.0, line_dark=0.5, line_rub=0.3))

    foliage = SheetBatch()
    tones = ["#6B8C45", "#83A350", "#5A7D40", "#9FB05A", "#76964A"]
    lobes = [(tip, 0.42) for tip, _ in ends] + [(mid + np.array([0, 0, 0.16]), 0.34) for _, mid in ends]
    index = 0
    for center, radius in lobes:
        for _ in range(58):
            direction = normalize(gen.normal(size=3) * np.array([1.0, 1.0, 0.72]))
            where = center + direction * radius * gen.uniform(0.62, 1.05) + planted
            leaf(foliage, where, direction + np.array([0.0, 0.0, 0.5]), gen.uniform(0.075, 0.125), srgb(tones[index % 5]) * gen.uniform(0.88, 1.1), 700 + index)
            index += 1
    canopy = foliage.build("canopy_leaves")
    canopy.data.materials.append(materials.crumpled("canopy_paper", tile=4.0, folds=0.5, fibre_strength=1.0, line_dark=0.3, line_rub=0.25))
    apples = []
    for i in range(16):
        center, radius = lobes[i % len(lobes)]
        direction = normalize(gen.normal(size=3))
        apple = blob(f"apple_{i}", center + direction * radius * 1.04 + planted, (0.055, 0.055, 0.058), 2)
        paint(apple, np.broadcast_to(srgb("#B9443C"), (len(apple.data.vertices), 3)))
        apples.append(apple)
    fruit = join(apples, "apples")
    fruit.data.materials.append(materials.card("apple_paper"))
    return {"hill": hill, "tree": tree, "canopy": canopy, "apples": fruit, "meadow": build_meadow(get_verts(hill))}
