"""Rigs, pose library and stepped clips.

Everything is animated the way a puppet is: at most 12 distinct poses per second,
held deliberately. Clips are authored as sparse key poses with a `step` that says
how many 12 fps frames each pose is held; frames in between snap to the nearest
stepped pose rather than gliding. A tiny seeded nudge per pose stands in for the
animator's hand. It is correlated and low in amplitude, so it reads as touch, never
as jitter.

Facial expressions and the pointing hand are replacement parts. Their bones are
keyed to scale 1 or 0, exactly as an animator swaps a mouth on the puppet between
frames, so an expression needs no morph targets.
"""

import math

import bpy
import mathutils
import numpy as np
from bpy_extras import anim_utils

from characters import ELBOW, HAND_TIP, SCARF_CONTROL, SHOULDER, WRIST, mirror_x
from sculpt import closest_on_segments, smooth_path

FPS = 12
SCARF_BONES = 8


def add_bones(armature_object, bones):
    """Create edit bones from (name, head, tail, parent) tuples."""
    bpy.context.view_layer.objects.active = armature_object
    bpy.ops.object.mode_set(mode="EDIT")
    edit = armature_object.data.edit_bones
    for name, head, tail, parent in bones:
        bone = edit.new(name)
        bone.head = mathutils.Vector(head)
        bone.tail = mathutils.Vector(tail)
        if parent:
            bone.parent = edit[parent]
    bpy.ops.object.mode_set(mode="OBJECT")


def prince_skeleton():
    """Bone table for the Prince, built on the sculpt's own landmarks."""
    table = [
        ("root", (0, 0, 0), (0, 0, 0.1), None),
        ("hips", (0, 0, 0.46), (0, 0, 0.60), "root"),
        ("spine", (0, 0, 0.60), (0, 0, 0.75), "hips"),
        ("chest", (0, 0, 0.75), (0, 0, 0.90), "spine"),
        ("neck", (0, 0, 0.90), (0, 0, 1.0), "chest"),
        ("head", (0, 0, 1.0), (0, 0, 1.7), "neck"),
    ]
    for side, tag in ((1.0, "L"), (-1.0, "R")):
        table.extend(
            [
                (f"upper_arm.{tag}", mirror_x(SHOULDER, side), mirror_x(ELBOW, side), "chest"),
                (f"forearm.{tag}", mirror_x(ELBOW, side), mirror_x(WRIST, side), f"upper_arm.{tag}"),
                (f"hand.{tag}", mirror_x(WRIST, side), mirror_x(HAND_TIP, side), f"forearm.{tag}"),
                (f"thigh.{tag}", (side * 0.115, 0, 0.46), (side * 0.122, -0.006, 0.26), "hips"),
                (f"shin.{tag}", (side * 0.122, -0.006, 0.26), (side * 0.122, 0, 0.09), f"thigh.{tag}"),
                (f"foot.{tag}", (side * 0.122, 0, 0.09), (side * 0.122, -0.17, 0.03), f"shin.{tag}"),
            ]
        )
    path = smooth_path(SCARF_CONTROL, SCARF_BONES + 1)
    for i in range(SCARF_BONES):
        table.append((f"scarf.{i + 1}", path[i], path[i + 1], "chest" if i == 0 else f"scarf.{i}"))
    for name, parent, head, tail in (
        ("fx.eyes_open", "head", (0, -0.32, 1.33), (0, -0.32, 1.38)),
        ("fx.eyes_closed", "head", (0, -0.33, 1.33), (0, -0.33, 1.38)),
        ("fx.mouth_rest", "head", (0, -0.3, 1.11), (0, -0.3, 1.14)),
        ("fx.mouth_smile", "head", (0, -0.31, 1.11), (0, -0.31, 1.14)),
        ("fx.hand_relaxed", "hand.L", mirror_x(WRIST, 1), mirror_x(HAND_TIP, 1)),
        ("fx.hand_point", "hand.L", mirror_x(WRIST, 1), mirror_x(HAND_TIP, 1)),
    ):
        table.append((name, head, tail, parent))
    return table


def capsule_weights(verts, bones, radii, falloff=5.0, limit=3):
    """Skin weights from distance to bone capsules: normalized inverse-power, top few bones only."""
    head = np.stack([b[0] for b in bones])
    tail = np.stack([b[1] for b in bones])
    distances = np.stack([closest_on_segments(verts, head[i], tail[i])[0] for i in range(len(bones))], axis=1)
    distances = np.maximum(distances - np.asarray(radii), 0.012)
    weights = distances**-falloff
    order = np.argsort(-weights, axis=1)
    trimmed = np.zeros_like(weights)
    rows = np.arange(len(verts))[:, None]
    trimmed[rows, order[:, :limit]] = weights[rows, order[:, :limit]]
    return trimmed / trimmed.sum(axis=1, keepdims=True)


def assign(obj, names, indices, weights):
    """Write a weight matrix into vertex groups for the given vertex indices."""
    for column, name in enumerate(names):
        group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        for vertex, weight in zip(indices, weights[:, column]):
            if weight > 0.003:
                group.add([int(vertex)], float(weight), "REPLACE")


def bone_ends(table, name):
    """Head and tail of a bone from the table."""
    entry = next(b for b in table if b[0] == name)
    return np.asarray(entry[1], dtype=np.float64), np.asarray(entry[2], dtype=np.float64)


def skin_prince(mesh, table):
    """Assign weights per puppet piece, using the piece groups that baking left on the mesh."""
    coords = np.array([v.co[:] for v in mesh.data.vertices])
    membership = {group.name[6:]: [] for group in mesh.vertex_groups if group.name.startswith("piece:")}
    index_to_name = {group.index: group.name[6:] for group in mesh.vertex_groups if group.name.startswith("piece:")}
    for vertex in mesh.data.vertices:
        for link in vertex.groups:
            if link.group in index_to_name:
                membership[index_to_name[link.group]].append(vertex.index)
    for group in [g for g in mesh.vertex_groups if g.name.startswith("piece:")]:
        mesh.vertex_groups.remove(group)

    def rigid(piece, bone):
        indices = membership.get(piece, [])
        assign(mesh, [bone], indices, np.ones((len(indices), 1)))

    def capsules(piece, names, radii, **options):
        indices = membership.get(piece, [])
        if not indices:
            return
        bones = [bone_ends(table, n) for n in names]
        assign(mesh, names, indices, capsule_weights(coords[indices], bones, radii, **options))

    for piece in ("hair", "eye_R", "eye_L"):
        rigid(piece, "head" if piece == "hair" else "fx.eyes_open")
    rigid("lid_L", "fx.eyes_closed")
    rigid("lid_R", "fx.eyes_closed")
    rigid("mouth_rest", "fx.mouth_rest")
    rigid("mouth_smile", "fx.mouth_smile")
    capsules("head", ["neck", "head"], [0.09, 0.26], falloff=8.0)
    capsules("button_a", ["spine", "chest"], [0.2, 0.2])
    capsules("button_b", ["hips", "spine"], [0.2, 0.2])
    arms = ["upper_arm.L", "forearm.L", "upper_arm.R", "forearm.R"]
    coat_bones = ["hips", "spine", "chest", *arms]
    indices = np.array(membership.get("coat", []))
    points = coat_points = coords[indices]
    weights = capsule_weights(points, [bone_ends(table, n) for n in coat_bones], [0.20, 0.20, 0.20, 0.09, 0.11, 0.09, 0.11], falloff=6.0, limit=4)
    # Sleeves own only what lies clear of the body, otherwise a raised arm tears the coat's flank away with it.
    body_edge = 0.25 + 0.07 * np.clip((0.55 - coat_points[:, 2]) / 0.25, 0.0, 1.0)
    clear = np.clip((np.abs(coat_points[:, 0]) - body_edge) / 0.09, 0.0, 1.0)
    clear = clear * clear * (3.0 - 2.0 * clear)
    weights[:, 3:] *= clear[:, None]
    weights /= weights.sum(axis=1, keepdims=True)
    assign(mesh, coat_bones, indices.tolist(), weights)
    capsules("stitches", ["hips", "spine", "chest"], [0.2, 0.2, 0.2])

    # Scarf: collar follows chest and neck, the tail follows its chain.
    indices = np.array(membership.get("scarf", []))
    tail_mask = coords[indices, 0] < -0.27
    collar_indices = indices[~tail_mask].tolist()
    tail_indices = indices[tail_mask].tolist()
    assign(mesh, ["chest", "neck"], collar_indices, capsule_weights(coords[collar_indices], [bone_ends(table, "chest"), bone_ends(table, "neck")], [0.2, 0.17]))
    names = [f"scarf.{i + 1}" for i in range(SCARF_BONES)]
    assign(mesh, names, tail_indices, capsule_weights(coords[tail_indices], [bone_ends(table, n) for n in names], [0.03] * SCARF_BONES, falloff=4.0, limit=4))

    for side in ("L", "R"):
        capsules(f"trouser_{side}", ["hips", f"thigh.{side}", f"shin.{side}"], [0.1, 0.06, 0.06], falloff=7.0)
        rigid(f"boot_{side}", f"foot.{side}")
    rigid("forearm_L", "forearm.L")
    rigid("forearm_R", "forearm.R")
    rigid("hand_relaxed_L", "fx.hand_relaxed")
    rigid("hand_relaxed_R", "hand.R")
    rigid("hand_point_L", "fx.hand_point")


def build_armature(name, table, mesh):
    """Create the armature, parent the mesh and bind it."""
    armature = bpy.data.armatures.new(name)
    armature_object = bpy.data.objects.new(name, armature)
    bpy.context.scene.collection.objects.link(armature_object)
    add_bones(armature_object, table)
    modifier = mesh.modifiers.new("skin", "ARMATURE")
    modifier.object = armature_object
    mesh.parent = armature_object
    # The glTF exporter only looks for clips on objects that have animation data.
    armature_object.animation_data_create()
    return armature_object


# --- Pose library --------------------------------------------------------------------------------
# Rotations are degrees about the armature's own axes: X (screen right), Y (into the set), Z (up).
# Writing them in world axes keeps poses readable and independent of bone roll.


def merge(*poses):
    """Layer pose dictionaries, later entries winning."""
    result = {}
    for pose in poses:
        result.update(pose)
    return result


STAND = {
    "upper_arm.L": (0, 28, 8),
    "forearm.L": (0, 8, 0),
    "upper_arm.R": (0, -28, -8),
    "forearm.R": (0, -8, 0),
    "head": (2, 0, -6),
    "fx.hand": "relaxed",
}

# The reference: arm flung up and out, one finger raised to a star, head turned a little toward it.
POINT = {
    "upper_arm.L": (0, -56, 0),
    "forearm.L": (0, -60, 0),
    "hand.L": (0, -8, 0),
    "upper_arm.R": (0, -26, -10),
    "forearm.R": (0, -10, 0),
    "chest": (0, 3, 4),
    "neck": (-2, 2, 4),
    "head": (-3, 4, 14),
    "fx.hand": "point",
}

LOOK_UP = merge(STAND, {"head": (-16, 0, -4), "neck": (-6, 0, 0)})

WALK_A = merge(
    STAND,
    {
        "thigh.L": (24, 0, 0),
        "shin.L": (-8, 0, 0),
        "thigh.R": (-22, 0, 0),
        "shin.R": (-28, 0, 0),
        "upper_arm.L": (-16, 26, 8),
        "upper_arm.R": (18, -26, -8),
        "spine": (3, 0, 4),
        "head": (0, 0, -6),
    },
)
WALK_B = merge(
    STAND,
    {
        "thigh.L": (-22, 0, 0),
        "shin.L": (-28, 0, 0),
        "thigh.R": (24, 0, 0),
        "shin.R": (-8, 0, 0),
        "upper_arm.L": (18, 26, 8),
        "upper_arm.R": (-16, -26, -8),
        "spine": (3, 0, -4),
        "head": (0, 0, 0),
    },
)
WALK_PASS = merge(STAND, {"shin.L": (-34, 0, 0), "thigh.L": (14, 0, 0), "shin.R": (0, 0, 0), "root.z": 0.02, "head": (2, 0, -3)})

KNEEL = merge(
    STAND,
    {
        "root.z": -0.215,
        "root.y": 0.03,
        "hips": (8, 0, 0),
        "spine": (10, 0, 0),
        "chest": (6, 0, 0),
        "neck": (6, 0, 0),
        "head": (10, 0, -6),
        "thigh.L": (82, 0, 0),
        "shin.L": (-92, 0, 0),
        "foot.L": (10, 0, 0),
        "thigh.R": (28, 0, 0),
        "shin.R": (-118, 0, 0),
        "foot.R": (92, 0, 0),
        "upper_arm.L": (34, 22, 6),
        "forearm.L": (46, 6, 0),
        "upper_arm.R": (12, -26, -8),
    },
)

# Leaning in with a hand held out toward the rose, or the fox.
REACH = merge(KNEEL, {"upper_arm.L": (0, -30, -62), "forearm.L": (0, -12, -22), "spine": (14, 0, -2), "head": (10, 0, 6), "fx.mouth": "smile"})

# Hanging from the bird strings: both hands up, legs dangling.
FLY = merge(
    STAND,
    {
        "upper_arm.L": (0, -72, 0),
        "forearm.L": (0, -40, 0),
        "hand.L": (0, -10, 0),
        "thigh.L": (10, 0, 0),
        "shin.L": (-24, 0, 0),
        "thigh.R": (-8, 0, 0),
        "shin.R": (-14, 0, 0),
        "head": (-13, 0, -4),
        "spine": (-3, 0, 0),
    },
)

SIT = merge(
    STAND,
    {
        "root.z": -0.335,
        "root.y": 0.09,
        "thigh.L": (84, -8, 0),
        "shin.L": (-26, 0, 0),
        "foot.L": (-30, 0, 0),
        "thigh.R": (82, 8, 0),
        "shin.R": (-34, 0, 0),
        "foot.R": (-24, 0, 0),
        "spine": (6, 0, 0),
        "chest": (4, 0, 0),
        "head": (5, 0, -10),
        "upper_arm.L": (30, 24, 4),
        "forearm.L": (34, 8, 0),
        "upper_arm.R": (24, -24, -4),
        "forearm.R": (30, -8, 0),
    },
)
SIT_REACH = merge(SIT, {"upper_arm.L": (0, -36, -62), "forearm.L": (0, -12, -22), "spine": (10, 0, -3), "head": (7, 0, 2), "fx.mouth": "smile"})

FINALE = merge(LOOK_UP, {"fx.mouth": "smile", "upper_arm.L": (0, 4, 6), "forearm.L": (0, -8, 0)})


def ease(t, power=2.2):
    """Ease-in-out on the key spacing. Applied to pose values, then stepped."""
    return t**power / (t**power + (1.0 - t) ** power)


def quat_world(euler_degrees):
    """World-axis rotation applied X, then Y, then Z."""
    x, y, z = (math.radians(a) for a in euler_degrees)
    return mathutils.Euler((x, y, z), "XYZ").to_quaternion()


# Limbs hang down, so a rotation that swings the chest forward swings them backward. Limb poses are
# written the way an animator thinks of them instead: positive X lifts the limb toward the front.
FRONT_POSITIVE = ("thigh", "shin", "foot", "upper_arm", "forearm", "hand")


def rotation_channels(pose):
    """Return only the bone-rotation entries of a pose, normalized to world-axis rotations."""
    channels = {}
    for key, value in pose.items():
        if key.startswith(("fx.", "root.")):
            continue
        if key.startswith(FRONT_POSITIVE):
            value = (-value[0], value[1], value[2])
        channels[key] = value
    return channels


def sample(keys, frame):
    """Evaluate key poses at a frame: world-axis quaternions plus root offsets and replacements."""
    frames = [k[0] for k in keys]
    index = max(0, min(np.searchsorted(frames, frame, side="right") - 1, len(keys) - 1))
    a_frame, a = keys[index]
    b_frame, b = keys[min(index + 1, len(keys) - 1)]
    t = 0.0 if b_frame == a_frame else min(1.0, (frame - a_frame) / (b_frame - a_frame))
    t = ease(t)
    from_pose = rotation_channels(a)
    to_pose = rotation_channels(b)
    rotations = {}
    for bone in set(from_pose) | set(to_pose):
        qa = quat_world(from_pose.get(bone, (0, 0, 0)))
        qb = quat_world(to_pose.get(bone, (0, 0, 0)))
        rotations[bone] = qa.slerp(qb, t)
    offset = {axis: a.get(f"root.{axis}", 0.0) * (1 - t) + b.get(f"root.{axis}", 0.0) * t for axis in "xyz"}
    swap = b if t > 0.5 else a
    return rotations, offset, swap.get("fx.hand", "relaxed"), swap.get("fx.mouth", "rest")


def channelbag_for(action, armature_object):
    """Create the action's slot and return its fcurve container."""
    slot = action.slots.new("OBJECT", armature_object.name)
    return anim_utils.action_ensure_channelbag_for_slot(action, slot)


def key_vector(bag, path, length, frames, values, group=None):
    """Write constant-interpolation keys for one array property."""
    for index in range(length):
        curve = bag.fcurves.new(path, index=index)
        curve.keyframe_points.add(len(frames))
        coords = np.empty(len(frames) * 2)
        coords[0::2] = frames
        coords[1::2] = [v[index] for v in values]
        curve.keyframe_points.foreach_set("co", coords)
        curve.keyframe_points.foreach_set("interpolation", [0] * len(frames))
        curve.update()


def bake_clip(armature_object, name, keys, length, step, face=None, nudge=0.35, seed=1, bones=None):
    """Bake key poses into a stepped action.

    Poses are evaluated every `step` frames and held, so a 12 fps timeline holds
    fewer unique drawings on slow beats, as hand animation does.
    """
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    bag = channelbag_for(action, armature_object)
    pose_bones = armature_object.pose.bones
    rests = {b.name: b.bone.matrix_local.to_quaternion() for b in pose_bones}
    all_bones = bones or [b.name for b in pose_bones if not b.name.startswith(("scarf.", "fx."))]
    frames = list(range(0, length + 1))
    held = [(f // step) * step for f in frames]
    gen = np.random.default_rng(seed)
    wobble = {b: gen.normal(0, 1, (length + 2, 3)) for b in all_bones}

    tracks = {b: [] for b in all_bones}
    root_track = []
    fx_track = {b: [] for b in ("fx.hand_relaxed", "fx.hand_point", "fx.mouth_rest", "fx.mouth_smile")}
    for pose_frame in held:
        rotations, offset, hand, mouth = sample(keys, pose_frame)
        for bone in all_bones:
            world = rotations.get(bone, mathutils.Quaternion())
            if nudge and bone in ("spine", "chest", "neck", "head", "upper_arm.L", "upper_arm.R"):
                shake = wobble[bone][pose_frame // step] * nudge
                world = quat_world(tuple(shake)) @ world
            rest = rests[bone]
            tracks[bone].append(tuple(rest.inverted() @ world @ rest))
        root_rest = rests["root"]
        root_track.append(tuple(root_rest.inverted() @ mathutils.Vector((offset["x"], offset["y"], offset["z"]))))
        fx_track["fx.hand_relaxed"].append(1.0 if hand == "relaxed" else 0.0)
        fx_track["fx.hand_point"].append(1.0 if hand == "point" else 0.0)
        fx_track["fx.mouth_rest"].append(1.0 if mouth == "rest" else 0.0)
        fx_track["fx.mouth_smile"].append(1.0 if mouth == "smile" else 0.0)

    for bone, values in tracks.items():
        key_vector(bag, f'pose.bones["{bone}"].rotation_quaternion', 4, frames, values)
    key_vector(bag, 'pose.bones["root"].location', 3, frames, root_track)
    for bone, values in fx_track.items():
        key_vector(bag, f'pose.bones["{bone}"].scale', 3, frames, [(v, v, v) for v in values])
    return action


def bake_scarf_clip(armature_object, name, length=48, step=2, amplitude=1.0, seed=8):
    """A travelling ripple down the scarf chain, each drawing held for two frames."""
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    bag = channelbag_for(action, armature_object)
    pose_bones = armature_object.pose.bones
    frames = list(range(0, length + 1))
    gen = np.random.default_rng(seed)
    for i in range(SCARF_BONES):
        bone = f"scarf.{i + 1}"
        rest = pose_bones[bone].bone.matrix_local.to_quaternion()
        values = []
        phase = gen.uniform(0, 0.3)
        reach = (0.35 + 0.65 * i / (SCARF_BONES - 1)) * amplitude
        for frame in frames:
            t = ((frame // step) * step) / length * math.tau * 2.0
            lift = math.sin(t - i * 0.85 + phase) * 7.5 * reach + math.sin(t * 0.5 - i * 0.4) * 3.0 * reach
            sway = math.sin(t * 0.5 - i * 0.6 + phase) * 6.0 * reach
            twist = math.sin(t - i * 0.7) * 5.0 * reach
            world = quat_world((twist, lift, sway))
            values.append(tuple(rest.inverted() @ world @ rest))
        key_vector(bag, f'pose.bones["{bone}"].rotation_quaternion', 4, frames, values)
    return action


def bake_face_clip(armature_object, name, blinks, length=96):
    """A looping blink track on the replacement eyes: two-frame closes, placed by hand."""
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    bag = channelbag_for(action, armature_object)
    frames = list(range(0, length + 1))
    closed = {f + d for f in blinks for d in (0, 1)}
    key_vector(bag, 'pose.bones["fx.eyes_open"].scale', 3, frames, [(0.0, 0.0, 0.0) if f in closed else (1.0, 1.0, 1.0) for f in frames])
    key_vector(bag, 'pose.bones["fx.eyes_closed"].scale', 3, frames, [(1.0, 1.0, 1.0) if f in closed else (0.0, 0.0, 0.0) for f in frames])
    return action


def rose_skeleton():
    """Stem, bloom, two leaves and five outer petal bones around the bloom."""
    table = [
        ("root", (0, 0, 0), (0, 0, 0.1), None),
        ("stem", (0, 0, 0.1), (0, 0, 0.78), "root"),
        ("bloom", (0, 0, 0.78), (0, 0, 1.05), "stem"),
        ("leaf.1", (0, 0, 0.34), (0.3, 0.09, 0.36), "stem"),
        ("leaf.2", (0, 0, 0.52), (-0.26, -0.1, 0.54), "stem"),
    ]
    for i in range(5):
        a = i * math.tau / 5
        table.append((f"petal.{i + 1}", (0, 0, 0.82), (math.cos(a) * 0.2, math.sin(a) * 0.2, 0.96), "bloom"))
    return table


def skin_rose(mesh, table):
    """Bind the rose: outer petals loosen toward their sector's bone, the heart stays with the bloom."""
    coords = np.array([v.co[:] for v in mesh.data.vertices])
    pieces = {g.index: g.name[6:] for g in mesh.vertex_groups if g.name.startswith("piece:")}
    groups = {}
    for vertex in mesh.data.vertices:
        for link in vertex.groups:
            if link.group in pieces:
                groups.setdefault(pieces[link.group], []).append(vertex.index)
    for group in [g for g in mesh.vertex_groups if g.name.startswith("piece:")]:
        mesh.vertex_groups.remove(group)
    stem = groups.get("stem", [])
    assign(mesh, ["stem"], stem, np.ones((len(stem), 1)))
    mound = groups.get("mound", [])
    assign(mesh, ["root"], mound, np.ones((len(mound), 1)))
    leaves = groups.get("leaves", [])
    assign(mesh, ["leaf.1", "leaf.2"], leaves, capsule_weights(coords[leaves], [bone_ends(table, "leaf.1"), bone_ends(table, "leaf.2")], [0.02, 0.02], falloff=8.0, limit=1))
    bloom = np.array(groups.get("bloom", []))
    points = coords[bloom]
    radial = np.hypot(points[:, 0], points[:, 1])
    influence = np.clip((radial - 0.05) / 0.14, 0.0, 1.0) ** 1.4
    azimuth = np.arctan2(points[:, 1], points[:, 0])
    names = ["bloom"] + [f"petal.{i + 1}" for i in range(5)]
    weights = np.zeros((len(bloom), 6))
    weights[:, 0] = 1.0 - influence
    for i in range(5):
        delta = np.angle(np.exp(1j * (azimuth - i * math.tau / 5)))
        share = np.clip(1.0 - np.abs(delta) / (math.tau / 5), 0.0, 1.0)
        weights[:, i + 1] = share * influence
    weights /= weights.sum(axis=1, keepdims=True)
    assign(mesh, names, bloom.tolist(), weights)


def rose_clips(armature_object):
    """A slow breath for the petals, and an answering shiver when she is touched."""
    pose_bones = armature_object.pose.bones
    for name, length, step, amount, speed in (("idle", 48, 1, 1.0, 1.0), ("touched", 24, 1, 3.4, 2.0)):
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        bag = channelbag_for(action, armature_object)
        frames = list(range(0, length + 1))
        for i in range(5):
            bone = f"petal.{i + 1}"
            rest = pose_bones[bone].bone.matrix_local.to_quaternion()
            a = i * math.tau / 5
            axis = (-math.sin(a), math.cos(a), 0.0)
            values = []
            for frame in frames:
                t = ((frame // step) * step) / length
                fade = math.sin(t * math.pi) if name == "touched" else 1.0
                angle = amount * fade * (2.4 + 2.2 * math.sin(t * math.tau * speed + i * 1.9))
                world = mathutils.Quaternion(axis, math.radians(angle))
                values.append(tuple(rest.inverted() @ world @ rest))
            key_vector(bag, f'pose.bones["{bone}"].rotation_quaternion', 4, frames, values)
        for bone, reach in (("bloom", 1.5), ("leaf.1", 3.5), ("leaf.2", 3.0)):
            rest = pose_bones[bone].bone.matrix_local.to_quaternion()
            values = []
            for frame in frames:
                t = ((frame // step) * step) / length
                fade = math.sin(t * math.pi) if name == "touched" else 1.0
                world = quat_world((reach * amount * fade * 0.6 * math.sin(t * math.tau * speed), 0.0, reach * amount * fade * math.cos(t * math.tau * speed)))
                values.append(tuple(rest.inverted() @ world @ rest))
            key_vector(bag, f'pose.bones["{bone}"].rotation_quaternion', 4, frames, values)


def prince_clips(armature_object):
    """Author every clip of the Prince. Names are the contract with the story engine."""
    clips = [
        ("point", [(0, POINT), (12, merge(POINT, {"head": (-4, 5, 11)})), (24, POINT)], 24, 3),
        ("lower_arm", [(0, POINT), (8, merge(POINT, {"upper_arm.L": (6, -18, 10), "forearm.L": (4, -16, 0), "fx.hand": "relaxed"})), (20, STAND)], 20, 1),
        ("stand", [(0, STAND), (18, merge(STAND, {"head": (0, 0, -9)})), (36, STAND)], 36, 3),
        ("walk", [(0, WALK_A), (3, WALK_PASS), (6, WALK_B), (9, merge(WALK_PASS, {"shin.L": (0, 0, 0), "shin.R": (-34, 0, 0), "thigh.R": (14, 0, 0), "thigh.L": (0, 0, 0)})), (12, WALK_A)], 12, 1),
        ("kneel", [(0, STAND), (10, merge(KNEEL, {"root.z": -0.12})), (20, KNEEL)], 20, 1),
        ("kneel_idle", [(0, KNEEL), (18, merge(KNEEL, {"head": (12, 0, -3)})), (36, KNEEL)], 36, 3),
        ("reach", [(0, KNEEL), (14, REACH), (30, merge(REACH, {"head": (12, 0, -14)}))], 30, 2),
        ("rise", [(0, REACH), (8, KNEEL), (22, FLY)], 22, 1),
        ("fly", [(0, FLY), (12, merge(FLY, {"thigh.L": (-10, 0, 0), "shin.L": (-20, 0, 0), "thigh.R": (10, 0, 0), "shin.R": (-30, 0, 0)})), (24, FLY)], 24, 2),
        ("land_sit", [(0, FLY), (10, STAND), (24, SIT)], 24, 1),
        ("sit_idle", [(0, SIT), (18, merge(SIT, {"head": (7, 0, -6)})), (36, SIT)], 36, 3),
        ("sit_reach", [(0, SIT), (20, SIT_REACH), (40, merge(SIT_REACH, {"head": (12, 0, -20)}))], 40, 2),
        ("stand_up", [(0, SIT_REACH), (24, FINALE)], 24, 1),
        ("look_up", [(0, FINALE), (18, merge(FINALE, {"head": (-20, 0, 2)})), (36, FINALE)], 36, 3),
    ]
    for index, (name, keys, length, _) in enumerate(clips):
        bake_clip(armature_object, name, keys, length, 1, nudge=0.0, seed=index + 1)
    bake_scarf_clip(armature_object, "scarf_flutter", 48, 1, 1.0)
    bake_scarf_clip(armature_object, "scarf_gust", 24, 1, 1.9, seed=9)
    bake_face_clip(armature_object, "face", [21, 62, 69])
    return {name: length for name, _, length, _ in clips}
