"""GLB export. Scene units, axes and clip names here are the contract with the runtime."""

import os

import bpy

from bake import select_only

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".build", "glb")


def export_glb(name, objects, animated=False):
    """Export objects to blender/.build/glb/<name>.glb, Y-up, with embedded textures."""
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.context.scene.render.fps = 12
    bpy.context.scene.render.fps_base = 1.0
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path = os.path.join(OUT_DIR, f"{name}.glb")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_image_format="AUTO",
        export_tangents=False,
        export_animations=animated,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_frame_step=1,
        export_optimize_animation_size=True,
        export_anim_slide_to_zero=False,
        export_skins=animated,
        export_morph=False,
        export_lights=False,
        export_cameras=False,
        export_extras=True,
    )
    return path


__all__ = ["export_glb", "select_only"]
