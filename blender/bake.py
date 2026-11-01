"""Atlas baking: transfer each piece's sculpt and shader detail onto a game-ready mesh.

Each asset has one atlas. Pieces get a hand-assigned rectangle, so the face earns
more texels than the back of a boot, and each low mesh is baked only from its own
high mesh, which stops the hair ray-casting into the head. Occlusion is baked last
across the joined result, so contact shadows do cross piece boundaries.
"""

import os

import bpy
import numpy as np

from sculpt import apply_modifiers, get_verts, relax, set_verts


def select_only(objs, active):
    """Select exactly these objects and set the active one."""
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active


def unwrap(obj, rect, island_margin=0.006, angle=72.0, smooth_first=True):
    """Smart-project a mesh and fit its UVs into an atlas rectangle (u0, v0, u1, v1)."""
    # Islands are cut on a smoothed copy of the shape. Unwrapping the crumpled surface directly
    # shatters it into thousands of specks, because every fold looks like a hard edge.
    sculpted = get_verts(obj)
    if smooth_first:
        relax(obj, 40, 0.8)
    select_only([obj], obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=np.radians(angle), island_margin=island_margin, area_weight=0.6, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    set_verts(obj, sculpted)
    place_uvs(obj, rect)


def place_uvs(obj, rect):
    """Rescale existing 0..1 UVs into an atlas rectangle."""
    layer = obj.data.uv_layers.active.data
    uv = np.empty(len(layer) * 2, dtype=np.float32)
    layer.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    low, high = uv.min(axis=0), uv.max(axis=0)
    uv = (uv - low) / np.maximum(high - low, 1e-6)
    u0, v0, u1, v1 = rect
    uv = uv * np.array([u1 - u0, v1 - v0]) + np.array([u0, v0])
    layer.foreach_set("uv", uv.ravel())


def bake_target(name):
    """A material holding only an image node, which Cycles writes the bake into."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    node = material.node_tree.nodes.new("ShaderNodeTexImage")
    node.name = "target"
    material.node_tree.nodes.active = node
    return material


def new_image(name, size, data=False, fill=(0.0, 0.0, 0.0, 1.0)):
    """Create a blank bake image. Data images (normal, roughness) skip colour management."""
    image = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    image.colorspace_settings.name = "Non-Color" if data else "sRGB"
    image.generated_color = fill
    image.pixels.foreach_set(np.tile(fill, size * size).astype(np.float32))
    return image


def configure_cycles(samples):
    """Set the render engine used for baking."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.render.bake.margin = 10
    scene.render.bake.margin_type = "EXTEND"


def bake_pass(low, high, image, kind, filters=None, extrusion=0.018, ray=0.05):
    """Bake one map from a high mesh onto the active low mesh."""
    target = low.data.materials[0].node_tree.nodes["target"]
    target.image = image
    select_only([low, high], low)
    bake = bpy.context.scene.render.bake
    bake.use_clear = False
    bake.use_selected_to_active = True
    bake.cage_extrusion = extrusion
    bake.max_ray_distance = ray
    bake.use_pass_direct = False
    bake.use_pass_indirect = False
    bake.use_pass_color = True
    bpy.ops.object.bake(type=kind)


def bake_piece(low, high, images, extrusion=0.018, ray=0.05):
    """Bake colour, roughness and normal for one piece."""
    bake_pass(low, high, images["color"], "DIFFUSE", extrusion=extrusion, ray=ray)
    bake_pass(low, high, images["roughness"], "ROUGHNESS", extrusion=extrusion, ray=ray)
    bpy.context.scene.render.bake.normal_space = "TANGENT"
    bake_pass(low, high, images["normal"], "NORMAL", extrusion=extrusion, ray=ray)


def bake_occlusion(obj, image, samples=48):
    """Bake ambient occlusion across a joined low mesh."""
    scene = bpy.context.scene
    scene.cycles.samples = samples
    # Occlusion stays local: only near contact should darken, not the whole far side of the puppet.
    scene.world = bpy.data.worlds.get("occlusion") or bpy.data.worlds.new("occlusion")
    scene.world.light_settings.distance = 0.32
    target = obj.data.materials[0].node_tree.nodes["target"]
    target.image = image
    select_only([obj], obj)
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.use_clear = True
    bpy.ops.object.bake(type="AO")
    scene.cycles.samples = 2


def pixels(image):
    """Read an image into a (H, W, 4) float array."""
    width, height = image.size
    out = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(out)
    return out.reshape(height, width, 4)


def write_png(image, data, path):
    """Store an array in an image and save it as PNG."""
    image.pixels.foreach_set(np.asarray(data, dtype=np.float32).ravel())
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    return image


def fill_misses(color, iterations=10):
    """Heal pixels no ray reached. They bake pure black, which would read as holes in the paper."""
    rgb = color[..., :3]
    hole = rgb.max(axis=-1) < 0.012
    near = np.zeros_like(hole)
    for axis in (0, 1):
        for shift in (-3, 3):
            near |= ~np.roll(hole, shift, axis)
    hole &= near
    for _ in range(iterations):
        known = (~hole).astype(np.float32)
        total = np.zeros_like(rgb)
        weight = np.zeros_like(known)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            total += np.roll(rgb * known[..., None], shift, axis)
            weight += np.roll(known, shift, axis)
        solved = hole & (weight > 0)
        rgb[solved] = total[solved] / weight[solved][..., None]
        hole = hole & ~solved
    return color


def finalize(name, images, occlusion, out_dir, metallic=None, tint_occlusion=0.35):
    """Combine baked maps: multiply a little occlusion into colour and pack an ORM map."""
    os.makedirs(out_dir, exist_ok=True)
    color = fill_misses(pixels(images["color"]))
    ao = pixels(occlusion)[..., 0]
    color[..., :3] *= (1.0 - tint_occlusion + tint_occlusion * ao)[..., None]
    roughness = pixels(images["roughness"])[..., 0]
    orm = np.ones_like(color)
    orm[..., 0] = ao
    orm[..., 1] = roughness
    orm[..., 2] = 0.0 if metallic is None else metallic
    final_color = write_png(images["color"], color, os.path.join(out_dir, f"{name}_color.png"))
    final_normal = write_png(images["normal"], pixels(images["normal"]), os.path.join(out_dir, f"{name}_normal.png"))
    final_orm = write_png(images["roughness"], orm, os.path.join(out_dir, f"{name}_orm.png"))
    return {"color": final_color, "normal": final_normal, "orm": final_orm}


def glb_material(name, maps):
    """Build a Principled material wired so the glTF exporter emits one ORM texture."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    bsdf = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Specular IOR Level"].default_value = 0.4

    color = tree.nodes.new("ShaderNodeTexImage")
    color.image = maps["color"]
    tree.links.new(color.outputs["Color"], bsdf.inputs["Base Color"])

    orm = tree.nodes.new("ShaderNodeTexImage")
    orm.image = maps["orm"]
    orm.image.colorspace_settings.name = "Non-Color"
    split = tree.nodes.new("ShaderNodeSeparateColor")
    tree.links.new(orm.outputs["Color"], split.inputs[0])
    tree.links.new(split.outputs["Green"], bsdf.inputs["Roughness"])
    tree.links.new(split.outputs["Blue"], bsdf.inputs["Metallic"])

    group = bpy.data.node_groups.get("glTF Material Output")
    if group is None:
        group = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        group.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    output = tree.nodes.new("ShaderNodeGroup")
    output.node_tree = group
    tree.links.new(split.outputs["Red"], output.inputs["Occlusion"])

    normal_image = tree.nodes.new("ShaderNodeTexImage")
    normal_image.image = maps["normal"]
    normal_image.image.colorspace_settings.name = "Non-Color"
    normal_map = tree.nodes.new("ShaderNodeNormalMap")
    tree.links.new(normal_image.outputs["Color"], normal_map.inputs["Color"])
    tree.links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    return material


def piece_vertices(obj, piece):
    """Indices of a joined mesh's vertices that came from a named piece."""
    group = obj.vertex_groups.get(f"piece:{piece}")
    if group is None:
        return np.empty(0, dtype=np.int64)
    return np.array([v.index for v in obj.data.vertices if any(link.group == group.index for link in v.groups)], dtype=np.int64)


def bake_asset(name, pieces, out_dir, size=2048, metallic=None, samples=2, exclude_occlusion=(), separate=False, smooth_unwrap=False):
    """Bake a list of pieces into one atlas and return the joined low mesh.

    Each piece is a dict of high, tris and rect, and may set extrusion, ray and
    keep_uv. The low meshes come back joined and carrying a single atlas material.
    """
    from sculpt import decimate

    configure_cycles(samples)
    images = {
        "color": new_image(f"{name}_color", size, fill=(0.0, 0.0, 0.0, 1.0)),
        "roughness": new_image(f"{name}_roughness", size, data=True, fill=(0.6, 0.6, 0.6, 1.0)),
        "normal": new_image(f"{name}_normal", size, data=True, fill=(0.5, 0.5, 1.0, 1.0)),
    }
    target = bake_target(f"{name}_target")
    lows = []
    for piece in pieces:
        high = piece["high"]
        low = piece.get("low") or decimate(high, piece["tris"])
        low.data.materials.clear()
        low.data.materials.append(target)
        low.vertex_groups.new(name=f"piece:{piece.get('name', high.name)}").add(list(range(len(low.data.vertices))), 1.0, "REPLACE")
        for key in list(low.data.color_attributes.keys()):
            low.data.color_attributes.remove(low.data.color_attributes[key])
        if piece.get("keep_uv"):
            place_uvs(low, piece["rect"])
        else:
            unwrap(low, piece["rect"], angle=piece.get("angle", 72.0), smooth_first=smooth_unwrap or piece.get("low") is None)
        bake_piece(low, high, images, extrusion=piece.get("extrusion", 0.018), ray=piece.get("ray", 0.05))
        lows.append(low)

    highs = [piece["high"] for piece in pieces]
    for high in highs:
        high.hide_render = True
    if separate:
        # Instanced props stay as separate meshes over one shared atlas.
        occlusion = new_image(f"{name}_ao", size, data=True, fill=(1.0, 1.0, 1.0, 1.0))
        maps = finalize(name, images, occlusion, out_dir, metallic=metallic, tint_occlusion=0.0)
        material = glb_material(name, maps)
        for low in lows:
            low.data.materials.clear()
            low.data.materials.append(material)
        for high in highs:
            bpy.data.objects.remove(high)
        return lows
    joined = keep_join(lows, name)
    occlusion = new_image(f"{name}_ao", size, data=True, fill=(1.0, 1.0, 1.0, 1.0))
    # Replacement parts come and go, so they must not leave shadows on what lies beneath them.
    verts = get_verts(joined)
    away = verts.copy()
    for index, piece in enumerate(exclude_occlusion):
        # Each to its own distant spot, or the removed parts would shadow one another out there.
        away[piece_vertices(joined, piece)] += np.array([0.0, -40.0 - 8.0 * index, 0.0])
    set_verts(joined, away)
    bake_occlusion(joined, occlusion)
    set_verts(joined, verts)
    maps = finalize(name, images, occlusion, out_dir, metallic=metallic)
    joined.data.materials.clear()
    joined.data.materials.append(glb_material(name, maps))
    return joined


def keep_join(objs, name):
    """Join low meshes, preserving UVs, custom attributes and the shared material."""
    for obj in objs:
        apply_modifiers(obj)
    select_only(objs, objs[0])
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    joined.data.name = name
    return joined
