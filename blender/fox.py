"""The fox: a puppet built to stand beside the Prince.

He shares the Prince's language: an oversized simple head, wide-set bead eyes, and
crisp paper over a plain pulp form. He is sculpted already seated, pear-shaped, with
his tail curled round his side, so the sitting pose is the model itself rather than
something a rig has to fold a four-legged animal into. He stays seated throughout, and moves
as a patient animal does: head tilts, ear flicks, a stir of the tail, a slow lean forward.

He faces -Y like the Prince and sits about 1.1 tall to the ear tips.
"""

import math

import bpy
import numpy as np

import animations
import materials
from sculpt import (
    blob,
    crumple,
    fuse,
    get_normals,
    get_verts,
    paint,
    set_verts,
    smooth_path,
    smoothstep,
    srgb,
    sweep,
    thumb_dents,
    warp,
    wave_field,
)

ORANGE = srgb("#DE7E32")
ORANGE_DEEP = srgb("#C4652A")
CREAM = srgb("#F3E6CB")
DARK = srgb("#3C2A24")
HEAD = np.array([0.0, -0.1, 0.72])
TAIL_PATH = np.array([[0.0, 0.26, 0.1], [0.2, 0.31, 0.1], [0.36, 0.15, 0.12], [0.39, -0.08, 0.18], [0.31, -0.24, 0.33]])


def build_body():
    """Sculpt the whole puppet as one fused mass, then paint his markings."""
    forms = [
        blob("torso", (0, 0.02, 0.3), (0.2, 0.23, 0.3), 4),
        blob("belly", (0, 0.05, 0.15), (0.24, 0.26, 0.16), 4),
        blob("skull", HEAD, (0.225, 0.195, 0.175), 4),
        sweep("muzzle", smooth_path(np.array([[0, -0.22, 0.7], [0, -0.34, 0.67], [0, -0.46, 0.64]]), 12), np.linspace(0.105, 0.03, 12), np.linspace(0.082, 0.026, 12), sides=14),
    ]
    for side in (1.0, -1.0):
        forms.append(blob("haunch", (side * 0.17, 0.12, 0.13), (0.11, 0.17, 0.13), 3))
        forms.append(blob("hind_paw", (side * 0.17, -0.08, 0.04), (0.055, 0.09, 0.04), 3))
        forms.append(sweep("foreleg", smooth_path(np.array([[side * 0.085, -0.13, 0.3], [side * 0.085, -0.17, 0.16], [side * 0.085, -0.18, 0.04]]), 10), np.linspace(0.062, 0.05, 10), sides=12))
        forms.append(blob("fore_paw", (side * 0.085, -0.205, 0.035), (0.058, 0.075, 0.036), 3))
        # Cheek points, swept back like a storybook fox's ruff.
        forms.append(sweep("cheek", smooth_path(np.array([[side * 0.13, -0.1, 0.67], [side * 0.25, -0.09, 0.62], [side * 0.34, -0.07, 0.585]]), 10), np.linspace(0.085, 0.008, 10), np.linspace(0.06, 0.006, 10), sides=10))
        # Big broad ears.
        forms.append(sweep("ear", smooth_path(np.array([[side * 0.125, -0.08, 0.84], [side * 0.165, -0.075, 0.98], [side * 0.205, -0.06, 1.13]]), 12), np.linspace(0.095, 0.006, 12), np.linspace(0.036, 0.005, 12), sides=10))
    path = smooth_path(TAIL_PATH, 34)
    s = np.linspace(0.0, 1.0, 34)
    radius = 0.055 + 0.085 * np.sin(np.minimum(s * 1.25, 1.0) * math.pi) ** 0.7
    radius[-1] = 0.012
    forms.append(sweep("tail", path, radius, radius * 0.9, sides=16, up=(0.0, 0.0, 1.0)))

    body = fuse(forms, 0.0062, "fox_body", 8)
    verts = get_verts(body)
    normals = get_normals(body)
    verts = warp(verts, 0.006, 5.0, 501)
    verts = crumple(verts, normals, 260, 0.1, 0.008, 12.0, 503)
    verts = crumple(verts, normals, 700, 0.045, 0.0024, 12.0, 504)
    verts = thumb_dents(verts, normals, 16, 0.06, 0.003, 502)

    # Ear bowls.
    for side in (1.0, -1.0):
        bowl = np.linalg.norm((verts - np.array([side * 0.165, -0.11, 0.98])) / np.array([0.06, 0.03, 0.1]), axis=1)
        verts[:, 1] += 0.018 * smoothstep(1.0, 0.3, bowl)
    set_verts(body, verts)

    color = ORANGE[None, :] * (1 + 0.05 * wave_field(verts, 9.0, 505))[:, None]
    back = smoothstep(0.0, 0.25, verts[:, 1]) * smoothstep(0.1, 0.4, verts[:, 2])
    color = _blend(color, ORANGE_DEEP, back * 0.55)

    # Cream bib, cheeks, muzzle underside and tail tip, with clean painted edges.
    bib = smoothstep(0.012, -0.012, np.abs(verts[:, 0]) - (0.13 - 0.3 * np.maximum(0.0, 0.34 - verts[:, 2]))) * (verts[:, 1] < -0.06) * smoothstep(0.1, 0.13, verts[:, 2]) * smoothstep(0.56, 0.53, verts[:, 2])
    color = _blend(color, CREAM, bib)
    cheek = smoothstep(0.1, 0.13, np.abs(verts[:, 0])) * smoothstep(0.66, 0.63, verts[:, 2] - 0.3 * (np.abs(verts[:, 0]) - 0.2)) * smoothstep(0.54, 0.57, verts[:, 2])
    color = _blend(color, CREAM, cheek)
    muzzle = smoothstep(-0.24, -0.28, verts[:, 1]) * smoothstep(0.68, 0.66, verts[:, 2] + 0.22 * (verts[:, 1] + 0.3))
    color = _blend(color, CREAM, muzzle)
    tip = smoothstep(0.25, 0.3, verts[:, 2]) * smoothstep(0.19, 0.24, verts[:, 0]) * smoothstep(-0.12, -0.2, verts[:, 1])
    color = _blend(color, CREAM, tip)
    socks = smoothstep(0.11, 0.075, verts[:, 2]) * smoothstep(-0.13, -0.16, verts[:, 1])
    color = _blend(color, DARK, socks * 0.92)
    ears = smoothstep(1.02, 1.08, verts[:, 2])
    color = _blend(color, DARK, ears * 0.9)
    inner = smoothstep(0.03, 0.012, np.abs(np.abs(verts[:, 0]) - 0.165)) * smoothstep(0.9, 0.93, verts[:, 2]) * smoothstep(1.03, 1.0, verts[:, 2]) * smoothstep(-0.07, -0.11, verts[:, 1])
    color = _blend(color, srgb("#D79A86"), inner * 0.9)
    lip = np.exp(-(((verts[:, 2] - 0.615 + 0.24 * (verts[:, 1] + 0.46)) / 0.0042) ** 2)) * smoothstep(-0.3, -0.36, verts[:, 1])
    color = _blend(color, DARK, lip * 0.85)
    paint(body, color)
    body.data.materials.append(materials.crumpled("fox_paper", tile=1.35, folds=0.85, fibre_strength=1.1, line_dark=0.34, line_rub=0.36))
    return body


def _blend(color, tint, amount):
    """Lerp per-vertex colours toward a tint."""
    return color * (1.0 - amount[:, None]) + tint[None, :] * amount[:, None]


def front_point(verts, x, z):
    """The most forward surface vertex at a position on the face."""
    distance = np.linalg.norm(verts[:, [0, 2]] - np.array([x, z]), axis=1)
    near = verts[distance < 0.02]
    return near[np.argmin(near[:, 1])]


def build_face(body):
    """Nose and replacement eyes, seated on the sculpted head."""
    verts = get_verts(body)
    nose = blob("fox_nose", (0, -0.482, 0.648), (0.042, 0.034, 0.034), 3)
    nose.data.materials.append(materials.gloss_bead("fox_nose_enamel"))
    parts = {"nose": nose}
    for side, tag in ((1.0, "L"), (-1.0, "R")):
        point = front_point(verts, side * 0.115, 0.765)
        eye = blob(f"fox_eye_{tag}", point + np.array([0.0, 0.006, 0.0]), (0.034, 0.018, 0.042), 3)
        eye.data.materials.append(materials.gloss_bead(f"fox_eye_{tag}_enamel"))
        parts[f"eye_{tag}"] = eye
        arc = [front_point(verts, side * 0.115 + offset, 0.765 + drop) + np.array([0.0, -0.002, 0.0]) for offset, drop in ((-0.04, 0.006), (0.0, -0.01), (0.04, 0.006))]
        lid = sweep(f"fox_lid_{tag}", smooth_path(np.array(arc), 14), 0.007, sides=8)
        paint(lid, np.broadcast_to(DARK, (len(lid.data.vertices), 3)))
        lid.data.materials.append(materials.card(f"fox_lid_{tag}_paint"))
        parts[f"lid_{tag}"] = lid
    return parts


def skeleton():
    """Bone table: a small puppet armature."""
    table = [
        ("root", (0, 0, 0), (0, 0, 0.1), None),
        ("body", (0, 0.1, 0.08), (0, -0.06, 0.5), "root"),
        ("head", (0, -0.07, 0.52), (0, -0.1, 0.84), "body"),
        ("ear.L", (0.125, -0.08, 0.84), (0.205, -0.06, 1.13), "head"),
        ("ear.R", (-0.125, -0.08, 0.84), (-0.205, -0.06, 1.13), "head"),
        ("fore.L", (0.085, -0.13, 0.3), (0.085, -0.19, 0.03), "body"),
        ("fore.R", (-0.085, -0.13, 0.3), (-0.085, -0.19, 0.03), "body"),
        ("fx.eyes_open", (0, -0.3, 0.76), (0, -0.3, 0.82), "head"),
        ("fx.eyes_closed", (0, -0.31, 0.76), (0, -0.31, 0.82), "head"),
    ]
    tail = smooth_path(TAIL_PATH, 5)
    for i in range(4):
        table.append((f"tail.{i + 1}", tail[i], tail[i + 1], "body" if i == 0 else f"tail.{i}"))
    return table


def skin(mesh, table):
    """Bind the sculpt by capsule distance, with face parts bound rigidly."""
    coords = np.array([v.co[:] for v in mesh.data.vertices])
    pieces = {g.index: g.name[6:] for g in mesh.vertex_groups if g.name.startswith("piece:")}
    groups = {}
    for vertex in mesh.data.vertices:
        for link in vertex.groups:
            if link.group in pieces:
                groups.setdefault(pieces[link.group], []).append(vertex.index)
    for group in [g for g in mesh.vertex_groups if g.name.startswith("piece:")]:
        mesh.vertex_groups.remove(group)
    deforming = [b[0] for b in table if b[0] not in ("root", "fx.eyes_open", "fx.eyes_closed")]
    radii = {"body": 0.2, "head": 0.2, "ear.L": 0.03, "ear.R": 0.03, "fore.L": 0.05, "fore.R": 0.05}
    body = groups.get("body", [])
    points = coords[body]
    weights = animations.capsule_weights(points, [animations.bone_ends(table, n) for n in deforming], [radii.get(n, 0.07) for n in deforming], falloff=7.0, limit=3)
    # The head turns as one rigid form: everything above the neck follows it, with a short soft join.
    head_index = deforming.index("head")
    ear_columns = [deforming.index("ear.L"), deforming.index("ear.R")]
    above = np.clip((points[:, 2] - 0.5) / 0.05, 0.0, 1.0)
    ears = weights[:, ear_columns] * above[:, None]
    weights = weights * (1.0 - above[:, None])
    weights[:, ear_columns] += ears
    weights[:, head_index] += above - ears.sum(axis=1)
    weights = np.maximum(weights, 0.0)
    weights /= weights.sum(axis=1, keepdims=True)
    animations.assign(mesh, deforming, body, weights)
    for piece, bone in (("nose", "head"), ("eye_L", "fx.eyes_open"), ("eye_R", "fx.eyes_open"), ("lid_L", "fx.eyes_closed"), ("lid_R", "fx.eyes_closed")):
        indices = groups.get(piece, [])
        animations.assign(mesh, [bone], indices, np.ones((len(indices), 1)))


merge = animations.merge
SIT = {"head": (3, 0, 0), "ear.L": (0, 0, -3), "ear.R": (0, 0, 3)}
SIT_ALT = merge(SIT, {"tail.3": (0, 0, 7), "tail.4": (0, 0, 10)})
LOOK = merge(SIT, {"head": (1, 0, -12), "ear.L": (6, 0, -3)})
LEAN = merge(SIT, {"body": (15, 0, 0), "head": (13, 0, 5), "ear.L": (-14, 0, -12), "ear.R": (-14, 0, 12), "fore.L": (-12, 0, 0), "fore.R": (-12, 0, 0)})
NESTLE = merge(LEAN, {"head": (17, 0, 9), "tail.3": (0, 0, 9), "tail.4": (0, 0, 12)})


def clips(armature_object):
    """Author the fox's clips. Names are the contract with FoxChapter."""
    table = [
        ("sit_idle", [(0, SIT_ALT), (14, LOOK), (26, LOOK), (36, SIT)], 36, 3),
        ("nuzzle", [(0, SIT), (16, LEAN), (30, NESTLE)], 30, 2),
        ("rest", [(0, NESTLE), (18, merge(NESTLE, {"tail.3": (0, 0, -4), "tail.4": (0, 0, -6)})), (36, NESTLE)], 36, 3),
    ]
    for name, keys, length, _ in table:
        bake_fox_clip(armature_object, name, keys, length, 1)
    action = animations.bake_face_clip(armature_object, "face", [30, 74, 81])
    action.use_fake_user = True
    return {name: length for name, _, length, _ in table}


def bake_fox_clip(armature_object, name, keys, length, step):
    """Stepped clip over all deforming bones of the fox."""
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    bag = animations.channelbag_for(action, armature_object)
    pose_bones = armature_object.pose.bones
    rests = {b.name: b.bone.matrix_local.to_quaternion() for b in pose_bones}
    bones = [b.name for b in pose_bones if not b.name.startswith("fx.")]
    frames = list(range(0, length + 1))
    tracks = {b: [] for b in bones}
    root_track = []
    for frame in frames:
        pose_frame = (frame // step) * step
        rotations, offset, _, _ = animations.sample(keys, pose_frame)
        for bone in bones:
            world = rotations.get(bone, animations.mathutils.Quaternion())
            rest = rests[bone]
            tracks[bone].append(tuple(rest.inverted() @ world @ rest))
        root_rest = rests["root"]
        root_track.append(tuple(root_rest.inverted() @ animations.mathutils.Vector((offset["x"], offset["y"], offset["z"]))))
    for bone, values in tracks.items():
        animations.key_vector(bag, f'pose.bones["{bone}"].rotation_quaternion', 4, frames, values)
    animations.key_vector(bag, 'pose.bones["root"].location', 3, frames, root_track)
    return action
