"""The puppets. Proportions are measured from the art-direction reference.

Units are roughly set decimetres. The Prince stands 1.72 tall, faces -Y (+Z after
glTF conversion) with +X on the viewer's right. His head is 0.78 of that height,
which is what gives him the fragile, oversized look of the reference puppet.
"""

import math

import bpy
import numpy as np

import materials
from sculpt import (
    blob,
    closest_on_segments,
    crumple,
    frames_along,
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

HEAD_CENTER = np.array([0.0, 0.0, 1.33])
HEAD_RADII = np.array([0.315, 0.30, 0.39])

SKIN = srgb("#EDCFAC")
SKIN_SHADE = srgb("#D8AE86")
SKIN_ROSE = srgb("#D8927F")
OCHRE = [srgb("#EBBB4A"), srgb("#DDA93A"), srgb("#F2CB62"), srgb("#E3B244")]
OCHRE_DEEP = srgb("#A87620")
SCARF = srgb("#D8C237")
SCARF_DEEP = srgb("#9A8A1C")
COAT = srgb("#7FB653")
COAT_DEEP = srgb("#5A9440")
COAT_LINING = srgb("#2E6A30")

# The scarf tail's spine, shared by the sculpt and the bone chain that animates it.
SCARF_CONTROL = np.array(
    [
        [-0.16, 0.10, 0.90],
        [-0.36, 0.13, 0.86],
        [-0.62, 0.12, 0.96],
        [-0.86, 0.08, 1.12],
        [-1.14, 0.03, 1.14],
        [-1.42, 0.00, 1.09],
        [-1.68, -0.04, 1.13],
    ]
)


def egg(directions):
    """Map unit directions onto the head's egg: domed brow, tapering soft jaw, flattened face."""
    x, y, z = directions[:, 0], directions[:, 1], directions[:, 2]
    width = 1.0 + 0.11 * z - 0.13 * np.maximum(-z, 0.0) ** 2.2
    face = np.where(y < 0.0, 0.93, 1.03)
    return np.stack([x * HEAD_RADII[0] * width, y * HEAD_RADII[1] * width * face, z * HEAD_RADII[2]], axis=1) + HEAD_CENTER


def head_surface_point(verts, u, w):
    """Find the front-facing head vertex at a face position (u right, w up from head centre)."""
    target = np.array([u, HEAD_CENTER[2] + w])
    front = verts[:, 1] < 0.0
    candidates = np.nonzero(front)[0]
    distance = np.linalg.norm(verts[candidates][:, [0, 2]] - target, axis=1)
    return verts[candidates[np.argmin(distance)]]


def build_head():
    """Sculpt the head: one fused mass, then carve the plane of the face into it."""
    shell = icosphere("head_base", 6)
    set_verts(shell, egg(normalize(get_verts(shell))))
    neck = sweep("neck", [[0.0, 0.01, 0.70], [0.0, 0.0, 0.86], [0.0, -0.005, 1.04]], np.array([0.105, 0.098, 0.12]), sides=24)
    forms = [shell, neck]
    for side, turn in ((1.0, 0.25), (-1.0, -0.2)):
        rotation = _rotation_y(turn)
        forms.append(blob("ear", (side * 0.308, 0.035, 1.205), (0.042, 0.052, 0.085), 3, rotation))
    head = fuse(forms, 0.0058, "head", smooth_iterations=10)

    verts = get_verts(head)
    normals = get_normals(head)
    verts = warp(verts, 0.006, 3.2, 11)
    u = verts[:, 0] - 0.003
    w = verts[:, 2] - HEAD_CENTER[2]
    front = smoothstep(0.05, -0.12, verts[:, 1])

    # The two great planes of the face: a soft-edged recess around each eye, deliberately unequal.
    # The right-hand one has the crisp edge that sweeps down from the nose bridge in the reference.
    right_socket = ((u - 0.178) / 0.170) ** 2 + ((w + 0.005) / 0.235) ** 2
    left_socket = ((u + 0.175) / 0.165) ** 2 + ((w + 0.015) / 0.215) ** 2
    sweep_fade = smoothstep(-0.2, -0.04, w) * smoothstep(0.34, 0.2, u)
    recess = 0.021 * smoothstep(1.03, 0.92, right_socket) * sweep_fade + 0.008 * smoothstep(1.2, 0.72, left_socket)
    verts[:, 1] += recess * front

    # Nose: a long thin wedge rising out of the brow, sharpest near the tip.
    t = np.clip((0.075 - w) / 0.175, 0.0, 1.0)
    half_width = 0.012 + 0.034 * t
    ridge = np.clip(1.0 - (np.abs(u) / half_width) ** 1.6, 0.0, 1.0)
    profile = (0.012 + 0.082 * t**1.4) * smoothstep(1.0, 0.86, t) * smoothstep(0.0, 0.14, t)
    verts[:, 1] -= ridge * profile * front

    # A gentle plane change under the cheeks: the jaw line that wraps below the mouth.
    jaw = np.exp(-(((w + 0.285 + 1.3 * u * u) / 0.030) ** 2))
    verts[:, 1] += 0.005 * jaw * front

    # Mouth: a very shallow incised line with a slightly higher right corner.
    mouth_v = w + 0.215 - 0.5 * (u - 0.004) ** 2 - 0.08 * u
    mouth = np.exp(-((mouth_v / 0.0045) ** 2)) * smoothstep(0.052, 0.040, np.abs(u - 0.004))
    verts[:, 1] += 0.0035 * mouth * front

    # Hollow the ear bowls.
    for side in (1.0, -1.0):
        d = np.linalg.norm((verts - np.array([side * 0.335, 0.03, 1.205])) / np.array([0.05, 0.04, 0.062]), axis=1)
        verts[:, 0] -= side * 0.016 * smoothstep(1.0, 0.25, d)

    set_verts(head, verts)
    relax(head, 2, 0.4)
    verts = get_verts(head)
    normals = get_normals(head)
    set_verts(head, thumb_dents(verts, normals, 26, 0.042, 0.0028, 21))

    # Hand painting: warm base, a cooler shaded plane, rose nose tip, lips and ears.
    verts = get_verts(head)
    u = verts[:, 0] - 0.003
    w = verts[:, 2] - HEAD_CENTER[2]
    shade = 0.8 * smoothstep(1.02, 0.92, ((u - 0.178) / 0.170) ** 2 + ((w + 0.005) / 0.235) ** 2) * smoothstep(-0.28, -0.04, w)
    shade += 0.25 * smoothstep(1.2, 0.8, ((u + 0.175) / 0.165) ** 2 + ((w + 0.015) / 0.215) ** 2)
    color = SKIN[None, :] * (1 - shade[:, None] * 0.75) + SKIN_SHADE[None, :] * (shade[:, None] * 0.75)
    variation = wave_field(verts, 9.0, 5)[:, None]
    color = color * (1.0 + 0.04 * variation)
    nose = smoothstep(0.085, 0.01, np.linalg.norm(np.stack([u, (w + 0.09) * 0.62], axis=1), axis=1)) * smoothstep(0.0, -0.1, verts[:, 1])
    color = _blend(color, SKIN_ROSE, nose * 0.8)
    for side in (1.0, -1.0):
        ear = smoothstep(0.105, 0.03, np.linalg.norm((verts - np.array([side * 0.34, 0.03, 1.205])) * np.array([1.0, 1.0, 0.8]), axis=1))
        color = _blend(color, SKIN_ROSE, ear * 0.9)
        cheek = smoothstep(0.13, 0.0, np.linalg.norm(np.stack([u - side * 0.19, w + 0.14], axis=1), axis=1)) * smoothstep(0.0, -0.1, verts[:, 1])
        color = _blend(color, SKIN_ROSE, cheek * 0.16)
    paint(head, color)
    head.data.materials.append(materials.pulp("skin_pulp"))
    return head


def _blend(color, tint, amount):
    """Lerp per-vertex colours toward a tint."""
    return color * (1.0 - amount[:, None]) + tint[None, :] * amount[:, None]


def _rotation_y(angle):
    """Rotation matrix about Y."""
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _rotation_z(angle):
    """Rotation matrix about Z."""
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def hair_point(theta, phi, lift):
    """A point on the skull: theta runs around the face rim, phi back over the head."""
    direction = np.stack([np.cos(theta) * np.cos(phi), np.sin(phi), np.sin(theta) * np.cos(phi)], axis=-1)
    surface = egg(direction.reshape(-1, 3))
    outward = normalize(surface - HEAD_CENTER)
    return surface + outward * lift.reshape(-1, 1)


def hair_strip(name, seed, theta0, theta1, phi0, phi1, width, lift=0.012, curl=0.0, ruffle=0.02, samples=70):
    """One torn strip wrapped around the skull, ending in a ruffled curl."""
    gen = rng(seed)
    s = np.linspace(0.0, 1.0, samples)
    theta = theta0 + (theta1 - theta0) * s + 0.05 * np.sin(s * 5 + seed)
    phi = phi0 + (phi1 - phi0) * s + 0.06 * np.sin(s * 7 + seed * 2)
    lifted = lift + curl * s**3.0
    path = hair_point(theta, phi, lifted)
    outward = normalize(path - HEAD_CENTER)
    # Spiral the free end so it curls away from the skull.
    tangent = normalize(np.gradient(path, axis=0))
    side = normalize(np.cross(tangent, outward))
    roll = (0.35 + 0.5 * gen.uniform(-1, 1)) + 2.2 * s**2.5 * gen.choice([-1, 1])
    up = outward * np.cos(roll)[:, None] + side * np.sin(roll)[:, None]
    widths = width * (0.45 + 0.75 * np.sin(np.pi * s**0.75) ** 0.6)
    strip = ribbon(name, path, widths, across=9, edge=torn_edge(seed, 0.42, 26.0), ups=up)
    verts = get_verts(strip).reshape(samples, 9, 3)
    v = np.linspace(-1, 1, 9)[None, :]
    phase = gen.uniform(0, 6.28)
    frequency = gen.uniform(16.0, 26.0)
    frill = (ruffle * (0.3 + s[:, None] * 1.2)) * (np.abs(v) ** 1.5) * np.sin(s[:, None] * frequency + phase + v * 1.2)
    verts = verts + np.broadcast_to(up[:, None, :], verts.shape) * frill[..., None]
    set_verts(strip, verts.reshape(-1, 3))
    tone = OCHRE[seed % len(OCHRE)] * gen.uniform(0.9, 1.08)
    paint(strip, np.broadcast_to(tone, (samples * 9, 3)))
    return strip


def build_hair():
    """Torn ochre strips wrapped along the face rim, blooming into ruffles on the windward side."""
    # Under-layer: a dark rough cap so no skull shows between strips.
    cap = icosphere("hair_cap", 5)
    directions = normalize(get_verts(cap))
    set_verts(cap, egg(directions) + directions * 0.012)
    mesh = cap.data
    keep = (directions[:, 1] > -0.2 + 0.22 * np.maximum(0.0, -directions[:, 2]) * 3.0) & (directions[:, 2] > -0.42)
    faces = [p.vertices[:] for p in mesh.polygons if all(keep[list(p.vertices)])]
    verts = get_verts(cap)
    from_cap = mesh_object("hair_under", verts, faces)
    bpy.data.objects.remove(cap)
    paint(from_cap, np.broadcast_to(OCHRE_DEEP, (len(verts), 3)))
    pieces = [from_cap]
    seed = 100

    # Long strips hugging the rim: front silhouette from the right temple, over the crown, to the left.
    for i in range(22):
        phi = -0.17 + i * 0.115
        pieces.append(
            hair_strip(
                f"strip_{seed}",
                seed,
                0.1 + 0.33 * ((i * 7) % 5) / 4,
                2.3 + 0.75 * ((i * 3) % 7) / 6,
                phi,
                phi + 0.12,
                0.042 + 0.016 * (i % 3),
                lift=0.014 + 0.0045 * i + 0.012 * (i % 2),
                curl=0.06 + 0.02 * (i % 5),
                ruffle=0.04,
            )
        )
        seed += 1

    # The ruffled rosette: short layered curls crowding the upper left of the head.
    gen = rng(7)
    for i in range(26):
        theta = gen.uniform(1.2, 3.35)
        phi = gen.uniform(0.0, 0.8)
        pieces.append(
            hair_strip(
                f"curl_{seed}",
                seed,
                theta - gen.uniform(0.25, 0.6),
                theta + gen.uniform(0.25, 0.5),
                phi,
                phi + gen.uniform(-0.25, 0.25),
                gen.uniform(0.06, 0.1),
                lift=gen.uniform(0.02, 0.05),
                curl=gen.uniform(0.05, 0.14),
                ruffle=gen.uniform(0.03, 0.055),
                samples=46,
            )
        )
        seed += 1

    # Back of the head.
    for i in range(14):
        theta = gen.uniform(-0.2, 3.5)
        phi = gen.uniform(0.9, 1.5)
        pieces.append(hair_strip(f"back_{seed}", seed, theta, theta + 0.8, phi, phi + 0.5, 0.075, lift=0.02, curl=0.03, ruffle=0.018, samples=36))
        seed += 1

    hair = join(pieces, "hair")
    verts = get_verts(hair)
    normals = get_normals(hair)
    verts = crumple(verts, normals, 200, 0.05, 0.007, 6.0, 41)
    set_verts(hair, verts)
    solidify(hair, 0.006, 0.0)
    hair.data.materials.append(materials.crumpled("hair_paper", tile=2.0, folds=0.62, fibre_strength=0.9, line_dark=0.32, line_rub=0.4))
    return hair


def build_scarf():
    """Crepe collar wrapped around the neck, plus a long forked tail streaming to the viewer's left."""
    pieces = []
    gen = rng(5)

    # Collar: a thick crepe tube wound round the neck, fused, then pleated along the wrap.
    turns = 3.4
    t = np.linspace(0.0, 1.0, 420)
    angle = t * turns * math.tau + 0.6
    radius = 0.232 - 0.062 * t + 0.008 * np.sin(angle * 2.3)
    height = 0.79 + 0.165 * t + 0.016 * np.sin(angle + 1.0) + 0.012 * np.sin(angle * 0.37)
    wrap = np.stack([np.cos(angle) * radius, np.sin(angle) * radius * 0.93, height], axis=1)
    tube = sweep("collar_wrap", wrap, 0.046 + 0.008 * np.sin(angle * 0.9), 0.058 + 0.01 * np.sin(angle * 1.3), sides=14, up=(0.0, 0.0, 1.0))
    collar = fuse([tube], 0.0042, "collar", 3)
    verts = get_verts(collar)
    normals = get_normals(collar)
    bend = wave_field(verts, 9.0, 91)
    fold = np.sin(verts[:, 2] * 190.0 + bend * 4.5 + np.arctan2(verts[:, 1], verts[:, 0]) * 4.0)
    radial = normalize(verts * np.array([1.0, 1.0, 0.0]))
    depth = np.sign(fold) * np.abs(fold) ** 0.55 * (0.75 + 0.45 * wave_field(verts, 14.0, 92))
    verts += radial * (0.0115 * depth)[:, None]
    verts = crumple(verts, normals, 420, 0.05, 0.0055, 11.0, 93)
    set_verts(collar, verts)
    shading = (0.58 + 0.5 * np.clip(depth * 0.5 + 0.5, 0.0, 1.0))[:, None]
    paint(collar, np.broadcast_to(SCARF, verts.shape) * shading * (1.0 + 0.09 * wave_field(verts, 11.0, 94))[:, None])
    pieces.append(collar)

    # Tail: wide middle, twisting once, then forking.
    path = smooth_path(SCARF_CONTROL, 420)
    s = np.linspace(0.0, 1.0, len(path))
    roll = 0.25 + 0.95 * np.sin(s * math.pi * 1.2) ** 2
    up_axis = np.array([0.0, -1.0, 0.0])
    tangents = normalize(np.gradient(path, axis=0))
    ups = normalize(np.cross(tangents, up_axis))
    ups = ups * np.cos(roll)[:, None] + np.cross(tangents, ups) * np.sin(roll)[:, None]
    width = 0.03 + 0.12 * smoothstep(0.0, 0.42, s) ** 1.1 * smoothstep(1.0, 0.45, s) ** 0.8
    width = np.maximum(width * (1.0 + 0.0 * s), 0.0025)
    upper = ribbon("tail_upper", path, width, across=86, ups=ups, edge=torn_edge(3, 0.05, 30.0))
    _flute(upper, 86, 0.018, 12)
    paint(upper, np.broadcast_to(SCARF, (len(path) * 86, 3)))
    pieces.append(upper)

    branch = smooth_path(np.array([[-0.48, 0.14, 0.885], [-0.78, 0.10, 0.895], [-1.08, 0.06, 0.85], [-1.32, 0.04, 0.80], [-1.53, 0.02, 0.765]]), 280)
    s = np.linspace(0.0, 1.0, len(branch))
    width = 0.0025 + 0.065 * smoothstep(0.0, 0.3, s) * smoothstep(1.0, 0.25, s) ** 1.2
    tangents = normalize(np.gradient(branch, axis=0))
    ups = normalize(np.cross(tangents, up_axis)) * 0.92 + np.array([0.0, -0.3, 0.0])
    lower = ribbon("tail_lower", branch, width, across=36, ups=ups, edge=torn_edge(4, 0.05, 30.0))
    _flute(lower, 36, 0.010, 13)
    paint(lower, np.broadcast_to(SCARF * 0.93, (len(branch) * 36, 3)))
    pieces.append(lower)

    scarf = join(pieces, "scarf")
    verts = get_verts(scarf)
    normals = get_normals(scarf)
    tail = verts[:, 0] < -0.3
    verts = crumple(verts, normals, 150, 0.14, 0.020, 8.0, 51) * tail[:, None] + verts * (~tail)[:, None]
    verts = crumple(verts, normals, 420, 0.05, 0.0045, 8.0, 52) * tail[:, None] + verts * (~tail)[:, None]
    set_verts(scarf, verts)
    solidify(scarf, 0.006, 0.0)
    scarf.data.materials.append(materials.crumpled("scarf_paper", tile=1.5, folds=1.0, fibre_strength=0.3, line_dark=0.5, line_rub=0.34))
    return scarf


def _flute(strip, across, amount, seed):
    """Add long soft flutes across a strip so it billows instead of lying flat."""
    verts = get_verts(strip)
    grid = verts.reshape(-1, across, 3)
    v = np.linspace(-1, 1, across)
    field = wave_field(grid[:, across // 2], 6.0, seed)[:, None]
    tangents = normalize(np.gradient(grid[:, across // 2], axis=0))
    sides = normalize(grid[:, -1] - grid[:, 0])
    normal = normalize(np.cross(tangents, sides))
    offset = (amount * np.sin(v[None, :] * 3.4 + field * 2.4) * (1.0 + field * 0.6))[..., None] * normal[:, None, :]
    set_verts(strip, (grid + offset).reshape(-1, 3))


# Arm rest pose: hanging out from the shoulder. Sleeves are modelled straight here and posed by the rig.
SHOULDER = np.array([0.255, 0.0, 0.80])
ELBOW = np.array([0.455, 0.0, 0.63])
WRIST = np.array([0.655, 0.0, 0.455])
HAND_TIP = np.array([0.745, 0.0, 0.375])


def mirror_x(points, side):
    """Mirror points to a side (1 for +X)."""
    return np.asarray(points) * np.array([side, 1.0, 1.0])


def build_coat():
    """The green coat: one crumpled paper shell with bell sleeves, an open hem and frayed cuffs."""
    profile = np.array(
        [
            [0.150, 0.905],
            [0.215, 0.875],
            [0.262, 0.815],
            [0.272, 0.74],
            [0.268, 0.64],
            [0.272, 0.54],
            [0.288, 0.44],
            [0.308, 0.355],
            [0.332, 0.285],
        ]
    )
    profile = smooth_path(profile, 56)
    body = lathe("coat_body", profile, 96, squash=(1.0, 0.82))
    solidify(body, 0.016, 1.0)
    forms = [body]
    sleeve_axes = []
    for side in (1.0, -1.0):
        cuff_end = WRIST - normalize(WRIST - ELBOW) * 0.03
        path = smooth_path(mirror_x([SHOULDER - np.array([0.07, 0.0, -0.05]), SHOULDER, ELBOW, cuff_end], side), 60)
        s = np.linspace(0.0, 1.0, len(path))
        radii = 0.098 + 0.007 * s + 0.075 * smoothstep(0.35, 1.0, s) ** 1.6
        sleeve_axes.append((path.copy(), radii.copy()))
        sleeve = sweep("sleeve", path, radii, radii * 0.94, sides=44, cap_start=True, cap_end=False, up=(0.0, 1.0, 0.0))
        solidify(sleeve, 0.015, -1.0)
        forms.append(sleeve)
    coat = fuse(forms, 0.0058, "coat", smooth_iterations=5)

    verts = get_verts(coat)
    normals = get_normals(coat)

    # Lining is decided from the clean shell: anything inside a sleeve's mid-wall, or inside the hem.
    lining = np.zeros(len(verts))
    nearest_sleeve_distance = np.full(len(verts), np.inf)
    nearest_sleeve_radius = np.zeros(len(verts))
    nearest_sleeve_point = np.zeros_like(verts)
    for axis, radii in sleeve_axes:
        for i in range(0, len(axis), 2):
            d = np.linalg.norm(verts - axis[i], axis=1)
            closer = d < nearest_sleeve_distance
            nearest_sleeve_distance[closer] = d[closer]
            nearest_sleeve_radius[closer] = radii[i]
            nearest_sleeve_point[closer] = axis[i]
    lining = ((nearest_sleeve_distance < nearest_sleeve_radius - 0.0075) & (np.abs(verts[:, 0]) > 0.52)).astype(float)
    hem_radius = np.interp(verts[:, 2], profile[::-1, 1], profile[::-1, 0])
    body_radius = np.linalg.norm(verts[:, :2] * np.array([1.0, 1.0 / 0.82]), axis=1)
    lining = np.maximum(lining, ((body_radius < hem_radius + 0.008) & (verts[:, 2] < 0.74) & (np.abs(verts[:, 0]) < 0.34)).astype(float))

    # Fray the open edges by nibbling at them.
    wrist_points = [mirror_x(WRIST, s) for s in (1.0, -1.0)]
    for point in wrist_points:
        d = np.linalg.norm(verts - point, axis=1)
        edge = smoothstep(0.26, 0.20, d)
        verts += (normalize(verts - point) * (edge * 0.012 * wave_field(verts, 95.0, 77))[:, None])
    hem = smoothstep(0.34, 0.295, verts[:, 2])
    verts[:, 2] += hem * 0.012 * wave_field(verts, 60.0, 78)

    # The shell's two walls have opposite normals. Displacing along a direction that only depends on
    # position keeps them together, so the lining never pokes through the outside.
    outward = normalize(verts * np.array([1.0, 1.0 / 0.82, 0.0]))
    in_sleeve = (nearest_sleeve_distance < nearest_sleeve_radius + 0.03) & (np.abs(verts[:, 0]) > 0.27)
    outward[in_sleeve] = normalize(verts - nearest_sleeve_point)[in_sleeve]

    verts = warp(verts, 0.006, 3.0, 12)
    verts = crumple(verts, outward, 280, 0.12, 0.009, 12.0, 61)
    verts = crumple(verts, outward, 900, 0.05, 0.0026, 12.0, 65)
    verts = thumb_dents(verts, outward, 18, 0.07, 0.003, 62)

    # Pocket flaps: a raised card with a crisp lower edge on each side of the skirt.
    for side in (1.0, -1.0):
        across = np.abs(verts[:, 0] - side * 0.165) / 0.095
        down = (0.525 - verts[:, 2]) / 0.062
        flap = smoothstep(1.05, 0.95, across) * smoothstep(-0.05, 0.05, down) * smoothstep(1.03, 0.97, down + 0.25 * across * across) * smoothstep(0.0, -0.1, verts[:, 1])
        verts[:, 1] -= 0.008 * flap

    # Slack vertical folds down the skirt of the coat.
    folds = np.sin(np.arctan2(verts[:, 1], verts[:, 0]) * 7.0 + wave_field(verts, 4.0, 63) * 2.2)
    skirt = smoothstep(0.62, 0.35, verts[:, 2]) * smoothstep(0.33, 0.2, np.abs(verts[:, 0]) - 0.2 + 0.2)
    verts += outward * (folds * skirt * 0.012)[:, None]

    # Centre placket: a raised flap running down the front.
    flap = np.exp(-(((verts[:, 0] - 0.018 - 0.02 * np.sin(verts[:, 2] * 7.0)) / 0.0075) ** 2)) * smoothstep(0.0, -0.1, verts[:, 1])
    verts[:, 1] -= 0.0055 * flap * smoothstep(0.31, 0.36, verts[:, 2])
    set_verts(coat, verts)

    color = np.broadcast_to(COAT, verts.shape) * (1.0 + 0.06 * wave_field(verts, 7.0, 64))[:, None]
    color = _blend(color, COAT_DEEP, 0.4 * smoothstep(0.5, 0.3, verts[:, 2]))
    color = _blend(color, COAT_LINING, lining * 0.92)
    paint(coat, color)
    coat.data.materials.append(materials.crumpled("coat_paper", tile=1.35, folds=0.92, fibre_strength=1.2, line_dark=0.42, line_rub=0.46))
    return coat


def build_button(center, name):
    """A little brass-painted pulp button with a sewn dimple."""
    button = blob(name, center, (0.042, 0.016, 0.042), 4)
    verts = get_verts(button)
    radial = np.linalg.norm(verts[:, [0, 2]] - np.asarray(center)[[0, 2]], axis=1)
    verts[:, 1] += 0.006 * smoothstep(0.02, 0.005, radial)
    set_verts(button, verts)
    paint(button, np.broadcast_to(srgb("#A5853E"), (len(verts), 3)))
    return button


def build_hands():
    """Paper-pulp hands: a relaxed right, and a left with a replacement pointing version."""
    results = {}

    def finger(start, end, radius):
        path = smooth_path(np.array([start, (np.asarray(start) + np.asarray(end)) / 2 + np.array([0.0, -0.004, 0.0]), end]), 12)
        s = np.linspace(0, 1, 12)
        return sweep("finger", path, radius * (1.0 - 0.45 * s**2), sides=10)

    # Everything is authored in a local frame then moved to the wrist.
    direction = normalize(HAND_TIP - WRIST)
    side_axis = normalize(np.cross(direction, np.array([0.0, 1.0, 0.0])))

    def local(along, across, depth=0.0):
        return WRIST + direction * along + side_axis * across + np.array([0.0, depth, 0.0])

    def arm_stub(sign):
        start = mirror_x(WRIST - direction * 0.14, sign)
        end = mirror_x(WRIST + direction * 0.01, sign)
        return sweep("forearm", [start, (start + end) / 2, end], np.array([0.042, 0.040, 0.036]), sides=16)

    for key, sign in (("hand_relaxed_L", 1.0), ("hand_relaxed_R", -1.0)):
        palm = blob("palm", mirror_x(local(0.07, 0.0), sign), (0.078, 0.042, 0.078), 3, _align(mirror_x(direction, sign)))
        fingers = [finger(mirror_x(local(0.10, a), sign), mirror_x(local(0.185 - abs(a) * 0.5, a * 1.15), sign), 0.0185) for a in (-0.036, -0.012, 0.012, 0.036)]
        thumb = finger(mirror_x(local(0.04, 0.06), sign), mirror_x(local(0.105, 0.098), sign), 0.019)
        results[key] = fuse([palm, *fingers, thumb], 0.0042, key, 3)

    palm = blob("palm", local(0.07, 0.0), (0.075, 0.045, 0.075), 3, _align(direction))
    index = finger(local(0.10, 0.024), local(0.25, 0.028), 0.021)
    curled = [blob("knuckle", local(0.128, a, -0.016), (0.026, 0.022, 0.026), 3) for a in (-0.04, -0.012, 0.012)]
    thumb = finger(local(0.04, -0.062), local(0.11, -0.04, -0.03), 0.0195)
    results["hand_point_L"] = fuse([palm, index, *curled, thumb], 0.0042, "hand_point_L", 3)
    # Forearms are separate pieces, so a hand swap never collapses part of the arm with it.
    results["forearm_L"] = fuse([arm_stub(1.0)], 0.0042, "forearm_L", 2)
    results["forearm_R"] = fuse([arm_stub(-1.0)], 0.0042, "forearm_R", 2)

    material = materials.pulp("hand_pulp")
    for hand in results.values():
        verts = get_verts(hand)
        verts = warp(verts, 0.003, 22.0, 13)
        set_verts(hand, verts)
        tint = np.broadcast_to(SKIN, verts.shape) * (1.0 + 0.05 * wave_field(verts, 18.0, 14))[:, None]
        tip_distance = np.abs((verts - WRIST * 1.0) @ direction)
        paint(hand, _blend(tint, SKIN_ROSE, 0.18 * smoothstep(0.08, 0.18, tip_distance)))
        hand.data.materials.append(material)
    return results


def _align(direction):
    """Rotation that aligns local Z with a direction, keeping Y roughly fixed."""
    z = normalize(np.asarray(direction, dtype=np.float64))
    y = np.array([0.0, 1.0, 0.0])
    x = normalize(np.cross(y, z))
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def build_legs():
    """Cream trousers and small pulp boots."""
    pieces = {}
    for side, key in ((1.0, "L"), (-1.0, "R")):
        hip = np.array([side * 0.115, 0.0, 0.46])
        knee = np.array([side * 0.122, -0.006, 0.26])
        ankle = np.array([side * 0.122, 0.0, 0.12])
        trouser = sweep("trouser", smooth_path([hip, knee, ankle], 24), np.linspace(0.082, 0.062, 24), sides=20)
        shaft = sweep("boot_shaft", smooth_path([[side * 0.122, 0.0, 0.22], [side * 0.122, 0.0, 0.08]], 8), np.linspace(0.072, 0.078, 8), sides=20)
        foot = blob("foot", (side * 0.122, -0.052, 0.058), (0.078, 0.132, 0.058), 4)
        sole = blob("sole", (side * 0.122, -0.052, 0.018), (0.082, 0.138, 0.018), 4)
        boot = fuse([shaft, foot, sole], 0.0058, f"boot_{key}", 4)
        verts = get_verts(boot)
        set_verts(boot, warp(verts, 0.004, 9.0, 15 + int(side)))
        tone = np.broadcast_to(srgb("#7A4F2E"), verts.shape) * (1.0 + 0.1 * wave_field(verts, 14.0, 18))[:, None]
        tone = _blend(tone, srgb("#4A2F1E"), smoothstep(0.03, 0.02, verts[:, 2]))
        paint(boot, tone)
        boot.data.materials.append(materials.card(f"boot_{key}"))
        pieces[f"boot_{key}"] = boot

        trouser = fuse([trouser], 0.006, f"trouser_{key}", 3)
        verts = get_verts(trouser)
        normals = get_normals(trouser)
        verts = crumple(verts, normals, 40, 0.06, 0.004, 2.2, 19 + int(side))
        set_verts(trouser, verts)
        paint(trouser, np.broadcast_to(srgb("#E5D6B2"), verts.shape))
        trouser.data.materials.append(materials.crumpled(f"trouser_{key}", tile=1.2, folds=0.5, fibre_strength=0.9, line_dark=0.25, line_rub=0.2))
        pieces[f"trouser_{key}"] = trouser
    return pieces


def place_eye(head, name, u, w, radii):
    """Seat an oval enamel bead on the head surface."""
    point = head_surface_point(get_verts(head), u, w)
    bead = blob(name, point + np.array([0.0, 0.009, 0.0]), radii, 4)
    bead.data.materials.append(materials.gloss_bead(f"{name}_enamel"))
    return bead


def place_mouth(head, name, curve, thickness, color):
    """Lay a tiny tapered sliver across the face: a replacement mouth or closed eyelid."""
    verts = get_verts(head)
    points = []
    for u, w in curve:
        points.append(head_surface_point(verts, u, w) + np.array([0.0, -0.0015, 0.0]))
    path = smooth_path(np.array(points), 26)
    s = np.linspace(0.0, 1.0, len(path))
    sliver = sweep(name, path, thickness * (0.35 + 0.65 * np.sin(s * math.pi) ** 0.6), thickness * 0.6, sides=8)
    paint(sliver, np.broadcast_to(srgb(color), (len(get_verts(sliver)), 3)))
    sliver.data.materials.append(materials.card(f"{name}_paint"))
    return sliver


def build_stitches():
    """Pale running stitches down the placket and along the hem, the small thing that says tailor."""
    dashes = []

    def dash(start, end):
        dashes.append(sweep("stitch", np.array([start, (start + end) / 2 + np.array([0.0, -0.002, 0.0]), end]), 0.0036, sides=5))

    z = 0.74
    while z > 0.34:
        front = -0.82 * np.interp(z, [0.3, 0.45, 0.74], [0.335, 0.296, 0.28])
        x = 0.04 + 0.02 * math.sin(z * 7.0)
        dash(np.array([x, front, z]), np.array([x + 0.002, front, z - 0.022]))
        z -= 0.038
    for side in (1.0, -1.0):
        a = -math.pi / 2 - 0.85
        while a < -math.pi / 2 + 0.85:
            radius = 0.325
            dash(np.array([side * math.cos(a) * radius, math.sin(a) * radius * 0.84, 0.335]), np.array([side * math.cos(a + 0.05) * radius, math.sin(a + 0.05) * radius * 0.84, 0.335]))
            a += 0.09
    stitches = join(dashes, "stitches")
    paint(stitches, np.broadcast_to(srgb("#EDE3C4"), (len(stitches.data.vertices), 3)))
    stitches.data.materials.append(materials.card("stitch_thread"))
    return stitches


def build_prince():
    """Build every high-resolution piece of the Prince."""
    head = build_head()
    pieces = {"head": head, "hair": build_hair(), "scarf": build_scarf(), "coat": build_coat()}
    pieces.update(build_hands())
    pieces.update(build_legs())
    pieces["stitches"] = build_stitches()
    pieces["button_a"] = build_button((0.024, -0.238, 0.60), "button_a")
    pieces["button_b"] = build_button((0.020, -0.262, 0.42), "button_b")
    for button in ("button_a", "button_b"):
        pieces[button].data.materials.append(materials.card(f"{button}_brass"))
    pieces["eye_L"] = place_eye(head, "eye_L", 0.168, -0.004, (0.043, 0.024, 0.052))
    pieces["eye_R"] = place_eye(head, "eye_R", -0.170, -0.008, (0.041, 0.024, 0.050))
    return pieces


def build_replacements(head):
    """Replacement expressions seated on the finished head: closed lids and two mouths."""
    parts = {}
    for name, u, w in (("lid_L", 0.168, -0.004), ("lid_R", -0.170, -0.008)):
        curve = [(u - 0.046, w + 0.006), (u, w - 0.012), (u + 0.046, w + 0.006)]
        parts[name] = place_mouth(head, name, curve, 0.0085, "#2A1E18")
    rest = [(-0.046, -0.205), (-0.01, -0.214), (0.03, -0.212), (0.058, -0.2)]
    smile = [(-0.062, -0.192), (-0.03, -0.216), (0.018, -0.222), (0.056, -0.205), (0.074, -0.182)]
    parts["mouth_rest"] = place_mouth(head, "mouth_rest", rest, 0.0052, "#B5655A")
    parts["mouth_smile"] = place_mouth(head, "mouth_smile", smile, 0.0064, "#B5655A")
    return parts
