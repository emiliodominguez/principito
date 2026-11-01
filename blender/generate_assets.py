"""Entry point: `pnpm assets:blender [-- name name ...]` rebuilds GLBs from nothing.

Run through Blender (see package.json). Each asset is built in a clean scene, so
one asset's failure or naming never touches another.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import addon_utils  # noqa: E402
import bpy  # noqa: E402

from generate_common import write_manifest  # noqa: E402


REPLACEMENT_PARTS = ("lid_L", "lid_R", "eye_L", "eye_R", "mouth_rest", "mouth_smile", "hand_point_L", "hand_relaxed_L", "hand_relaxed_R")


def clean_scene():
    """Reset Blender to an empty scene, keeping the add-ons baking and export depend on."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=False)
    addon_utils.enable("io_scene_gltf2", default_set=False)


def build_prince():
    """Sculpt, bake, rig, animate and export the Prince."""
    import animations
    import bake
    import characters
    import export

    pieces = characters.build_prince()
    head = pieces["head"]
    pieces.update(characters.build_replacements(head))
    rects = {
        "head": (0.0, 0.5, 0.5, 1.0, 9000),
        "coat": (0.5, 0.5, 1.0, 1.0, 17000),
        "scarf": (0.0, 0.0, 0.5, 0.5, 16000),
        "hair": (0.5, 0.125, 0.875, 0.5, 19000),
        "hand_relaxed_L": (0.875, 0.375, 1.0, 0.5, 1200),
        "hand_relaxed_R": (0.875, 0.25, 1.0, 0.375, 1200),
        "hand_point_L": (0.875, 0.125, 1.0, 0.25, 1400),
        "forearm_L": (0.875, 0.0, 0.9375, 0.0625, 260),
        "forearm_R": (0.9375, 0.0, 1.0, 0.0625, 260),
        "trouser_L": (0.5, 0.0, 0.625, 0.125, 900),
        "trouser_R": (0.625, 0.0, 0.75, 0.125, 900),
        "boot_L": (0.75, 0.0625, 0.8125, 0.125, 900),
        "boot_R": (0.8125, 0.0625, 0.875, 0.125, 900),
        "button_a": (0.75, 0.0, 0.78125, 0.03125, 120),
        "button_b": (0.78125, 0.0, 0.8125, 0.03125, 120),
        "eye_L": (0.8125, 0.0, 0.84375, 0.03125, 200),
        "eye_R": (0.84375, 0.0, 0.875, 0.03125, 200),
        "lid_L": (0.875, 0.09375, 0.90625, 0.125, 100),
        "lid_R": (0.90625, 0.09375, 0.9375, 0.125, 100),
        "mouth_rest": (0.9375, 0.09375, 0.96875, 0.125, 90),
        "mouth_smile": (0.96875, 0.09375, 1.0, 0.125, 90),
        "stitches": (0.875, 0.0625, 1.0, 0.09375, 900),
    }
    jobs = []
    for name, (u0, v0, u1, v1, tris) in rects.items():
        jobs.append({"name": name, "high": pieces[name], "rect": (u0, v0, u1, v1), "tris": tris, "extrusion": 0.045, "ray": 0.13})
    mesh = bake.bake_asset("prince", jobs, os.path.join(HERE, ".build", "textures"), size=3072, exclude_occlusion=REPLACEMENT_PARTS)
    table = animations.prince_skeleton()
    armature = animations.build_armature("prince_rig", table, mesh)
    animations.skin_prince(mesh, table)
    lengths = animations.prince_clips(armature)
    for piece in pieces.values():
        bpy.data.objects.remove(piece)
    export.export_glb("prince", [armature, mesh], animated=True)
    write_manifest("prince", {"fps": animations.FPS, "clips": lengths})


def main():
    """Build the requested assets, or all of them."""
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    import environments

    registry = {"prince": build_prince, **environments.REGISTRY}
    selected = arguments or list(registry)
    for name in selected:
        clean_scene()
        print(f"[assets] building {name}")
        registry[name]()
        print(f"[assets] finished {name}")


if __name__ == "__main__":
    main()
