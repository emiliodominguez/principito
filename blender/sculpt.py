"""Sculpting primitives: everything that shapes geometry before it is baked.

The puppets are papier-mâché, so a mesh here goes through the same steps a maker
would use: rough forms are fused together, the surface is pushed around by hand
(dents, lopsided silhouettes), and sheets are crumpled along random creases.
All randomness is seeded, so a rebuild reproduces the same objects.
"""

import math

import bmesh
import bpy
import numpy as np


def rng(seed):
    """Return a seeded numpy generator."""
    return np.random.default_rng(seed)


def normalize(v, axis=-1):
    """Normalize vectors along an axis, leaving zero vectors untouched."""
    length = np.linalg.norm(v, axis=axis, keepdims=True)
    return v / np.maximum(length, 1e-9)


def smoothstep(a, b, x):
    """Hermite step between a and b; works when a > b as well."""
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# --- Mesh <-> numpy ------------------------------------------------------------------------------


def link(obj, collection=None):
    """Link an object into a collection (scene root by default)."""
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_object(name, verts, faces, smooth=True):
    """Create and link a mesh object from vertex and face arrays."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(np.asarray(verts, dtype=np.float64).tolist(), [], [list(map(int, f)) for f in faces])
    mesh.update()
    if smooth:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        mesh.update()
    return link(bpy.data.objects.new(name, mesh))


def get_verts(obj):
    """Read vertex positions into an (N, 3) array."""
    count = len(obj.data.vertices)
    out = np.empty(count * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", out)
    return out.reshape(-1, 3)


def set_verts(obj, verts):
    """Write vertex positions from an (N, 3) array."""
    obj.data.vertices.foreach_set("co", np.asarray(verts, dtype=np.float64).ravel())
    obj.data.update()


def get_normals(obj):
    """Read smooth vertex normals into an (N, 3) array."""
    obj.data.update()
    count = len(obj.data.vertices)
    out = np.empty(count * 3, dtype=np.float32)
    obj.data.vertex_normals.foreach_get("vector", out)
    return out.reshape(-1, 3).astype(np.float64)


def paint(obj, colors, name="paint"):
    """Store per-vertex linear RGB as the attribute the shaders read as hand painting."""
    attribute = obj.data.color_attributes.get(name) or obj.data.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    rgba = np.ones((len(obj.data.vertices), 4), dtype=np.float32)
    rgba[:, :3] = colors
    attribute.data.foreach_set("color", rgba.ravel())


def srgb(hex_color):
    """Convert a #rrggbb string to a linear RGB array."""
    value = hex_color.lstrip("#")
    channel = np.array([int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return np.where(channel <= 0.04045, channel / 12.92, ((channel + 0.055) / 1.055) ** 2.4)


def apply_modifiers(obj):
    """Bake the modifier stack into the mesh without relying on UI context."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    old = obj.data
    obj.modifiers.clear()
    obj.data = mesh
    bpy.data.meshes.remove(old)
    return obj


def join(objs, name=None):
    """Join several objects into a new mesh object, consuming the inputs."""
    bm = bmesh.new()
    for obj in objs:
        temp = obj.data.copy()
        temp.transform(obj.matrix_world)
        bm.from_mesh(temp)
        bpy.data.meshes.remove(temp)
    mesh = bpy.data.meshes.new(name or objs[0].name)
    bm.to_mesh(mesh)
    bm.free()
    result = link(bpy.data.objects.new(name or objs[0].name, mesh))
    for obj in objs:
        data = obj.data
        bpy.data.objects.remove(obj)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    return result


def fuse(objs, voxel, name=None, smooth_iterations=8):
    """Fuse overlapping forms into one seamless surface, as if pressed together with wet pulp."""
    obj = join(objs if isinstance(objs, list) else [objs], name)
    remesh = obj.modifiers.new("fuse", "REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = voxel
    remesh.use_smooth_shade = True
    apply_modifiers(obj)
    if smooth_iterations:
        relax(obj, smooth_iterations)
    obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
    obj.data.update()
    return obj


def relax(obj, iterations=4, factor=0.5):
    """Laplacian smoothing, used to knock the stair-stepping out of voxel surfaces."""
    modifier = obj.modifiers.new("relax", "SMOOTH")
    modifier.factor = factor
    modifier.iterations = iterations
    return apply_modifiers(obj)


def solidify(obj, thickness, offset=-1.0):
    """Give a sheet real thickness."""
    modifier = obj.modifiers.new("solid", "SOLIDIFY")
    modifier.thickness = thickness
    modifier.offset = offset
    return apply_modifiers(obj)


def decimate(obj, target_tris):
    """Return a decimated copy with roughly target_tris triangles."""
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = obj.name + "_low"
    link(copy)
    tris = sum(len(p.vertices) - 2 for p in copy.data.polygons)
    if tris > target_tris:
        modifier = copy.modifiers.new("reduce", "DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = target_tris / tris
        apply_modifiers(copy)
    return copy


# --- Procedural surface fields -------------------------------------------------------------------


def wave_field(p, frequency, seed, components=18):
    """Smooth band-limited noise from random plane waves, around [-1, 1].

    Plane waves have no lattice, so even at low frequency the result never shows
    the grid alignment that gives away ordinary value noise.
    """
    gen = rng(seed)
    directions = normalize(gen.normal(size=(components, 3)))
    frequencies = frequency * gen.uniform(0.6, 1.5, components)
    phases = gen.uniform(0, math.tau, components)
    field = np.zeros(len(p))
    for direction, f, phase in zip(directions, frequencies, phases):
        field += np.sin(p @ direction * f + phase)
    return field / math.sqrt(components / 2.0)


def warp(verts, amount, frequency, seed):
    """Displace positions along a smooth vector field: the overall handmade lopsidedness."""
    offset = np.stack([wave_field(verts, frequency, seed + axis * 31) for axis in range(3)], axis=-1)
    return verts + offset * amount


def thumb_dents(verts, normals, count, radius, depth, seed, region=None):
    """Press shallow oval dents into a surface, like thumbs firming wet pulp."""
    gen = rng(seed)
    candidates = np.nonzero(region)[0] if region is not None else np.arange(len(verts))
    result = verts.copy()
    for index in gen.choice(candidates, size=min(count, len(candidates)), replace=False):
        center = verts[index]
        r = radius * gen.uniform(0.6, 1.4)
        stretch = normalize(gen.normal(size=3))
        delta = verts - center
        along = delta @ stretch
        distance2 = (delta * delta).sum(axis=1) + (along * along) * gen.uniform(0.0, 1.8)
        result -= normals * (depth * gen.uniform(0.5, 1.2) * np.exp(-distance2 / (r * r)))[:, None]
    return result


def crumple(verts, normals, count, radius, amplitude, sharpness, seed):
    """Fold a surface along many short random creases.

    Each crease is a soft step across a line, faded out with distance. A real
    crumple is a network of such folds rather than noise, which is why this
    produces flat facets meeting at ridges instead of a bumpy surface.
    """
    gen = rng(seed)
    result = verts.copy()
    picks = gen.integers(0, len(verts), count)
    for index in picks:
        center = verts[index]
        normal = normals[index]
        tangent = normalize(np.cross(normal, normalize(gen.normal(size=3))))
        delta = verts - center
        distance2 = (delta * delta).sum(axis=1)
        r = radius * gen.uniform(0.5, 1.5)
        mask = np.exp(-distance2 / (r * r))
        fold = np.tanh((delta @ tangent) * sharpness / r)
        result += normals * (amplitude * gen.uniform(0.4, 1.3) * gen.choice([-1, 1]) * mask * fold)[:, None]
    return result


# --- Mesh builders -------------------------------------------------------------------------------


def icosphere(name, subdivisions, radius=1.0):
    """Create an icosphere mesh object at the origin."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return link(bpy.data.objects.new(name, mesh))


def blob(name, center, radii, subdivisions=4, rotation=None):
    """An ellipsoid, the basic lump of pulp."""
    obj = icosphere(name, subdivisions)
    verts = get_verts(obj) * np.asarray(radii)
    if rotation is not None:
        verts = verts @ np.asarray(rotation).T
    set_verts(obj, verts + np.asarray(center))
    return obj


def frames_along(path, up=(0.0, 0.0, 1.0)):
    """Compute parallel-transported tangent, side and up frames along a polyline."""
    path = np.asarray(path, dtype=np.float64)
    tangents = normalize(np.gradient(path, axis=0))
    ups = np.zeros_like(path)
    current = np.asarray(up, dtype=np.float64)
    if abs(float(current @ tangents[0])) > 0.95:
        current = np.array([1.0, 0.0, 0.0])
    for i, tangent in enumerate(tangents):
        current = normalize(current - tangent * (current @ tangent))
        ups[i] = current
    sides = normalize(np.cross(tangents, ups))
    return tangents, sides, ups


def smooth_path(points, samples):
    """Resample control points into a smooth Catmull-Rom path."""
    points = np.asarray(points, dtype=np.float64)
    padded = np.vstack([2 * points[0] - points[1], points, 2 * points[-1] - points[-2]])
    segments = len(points) - 1
    out = []
    for s in np.linspace(0.0, segments - 1e-6, samples):
        i = int(s)
        t = s - i
        p0, p1, p2, p3 = padded[i], padded[i + 1], padded[i + 2], padded[i + 3]
        out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (3 * p1 - p0 - 3 * p2 + p3) * t * t * t))
    return np.array(out)


def sweep(name, path, radius_x, radius_y=None, sides=20, cap_start=True, cap_end=True, up=(0.0, 0.0, 1.0)):
    """Sweep an elliptical section along a path. Radii may be scalars or per-point arrays."""
    path = np.asarray(path, dtype=np.float64)
    n = len(path)
    rx = np.broadcast_to(radius_x, (n,)).astype(np.float64)
    ry = np.broadcast_to(radius_x if radius_y is None else radius_y, (n,)).astype(np.float64)
    _, side_axis, up_axis = frames_along(path, up)
    angles = np.linspace(0, math.tau, sides, endpoint=False)
    ring = np.stack([np.cos(angles), np.sin(angles)], axis=1)
    verts = (path[:, None, :] + side_axis[:, None, :] * rx[:, None, None] * ring[None, :, 0:1] + up_axis[:, None, :] * ry[:, None, None] * ring[None, :, 1:2]).reshape(-1, 3)
    faces = []
    for i in range(n - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    extra = []
    if cap_start:
        extra.append(path[0])
        faces.extend((len(verts), (j + 1) % sides, j) for j in range(sides))
    if cap_end:
        extra.append(path[-1])
        center = len(verts) + len(extra) - 1
        base = (n - 1) * sides
        faces.extend((center, base + j, base + (j + 1) % sides) for j in range(sides))
    if extra:
        verts = np.vstack([verts, np.array(extra)])
    return mesh_object(name, verts, faces)


def lathe(name, profile, segments=64, squash=(1.0, 1.0), close=False):
    """Revolve a (radius, z) profile around Z."""
    profile = np.asarray(profile, dtype=np.float64)
    angles = np.linspace(0, math.tau, segments, endpoint=False)
    verts = []
    for radius, z in profile:
        verts.extend((math.cos(a) * radius * squash[0], math.sin(a) * radius * squash[1], z) for a in angles)
    verts = np.array(verts)
    faces = []
    for i in range(len(profile) - 1):
        for j in range(segments):
            a = i * segments + j
            b = i * segments + (j + 1) % segments
            faces.append((a, a + segments, b + segments, b))
    if close:
        center = len(verts)
        verts = np.vstack([verts, [[0.0, 0.0, profile[-1, 1]]]])
        base = (len(profile) - 1) * segments
        faces.extend((center, base + (j + 1) % segments, base + j) for j in range(segments))
    return mesh_object(name, verts, faces)


def ribbon(name, path, widths, across=12, up=(0.0, 0.0, 1.0), twist=None, edge=None, ups=None):
    """Build a flat strip along a path. `edge(u, v)` nudges the outline to tear it."""
    path = np.asarray(path, dtype=np.float64)
    n = len(path)
    widths = np.broadcast_to(widths, (n,)).astype(np.float64)
    if ups is not None:
        tangents = normalize(np.gradient(path, axis=0))
        up_axis = normalize(ups - tangents * (ups * tangents).sum(axis=1, keepdims=True))
        side_axis = normalize(np.cross(tangents, up_axis))
    else:
        _, side_axis, up_axis = frames_along(path, up)
    if twist is not None:
        angle = np.broadcast_to(twist, (n,))[:, None]
        side_axis = side_axis * np.cos(angle) + up_axis * np.sin(angle)
    vs = np.linspace(-1, 1, across)
    verts = []
    for i in range(n):
        u = i / (n - 1)
        for v in vs:
            scale = widths[i] * (1.0 + (edge(u, v) if edge is not None else 0.0))
            verts.append(path[i] + side_axis[i] * v * scale)
    faces = []
    for i in range(n - 1):
        for j in range(across - 1):
            a = i * across + j
            faces.append((a, a + 1, a + across + 1, a + across))
    return mesh_object(name, np.array(verts), faces)


def torn_edge(seed, roughness=0.18, frequency=28.0):
    """Return an edge function that bites into a strip's outline like torn paper."""
    gen = rng(seed)
    phases = gen.uniform(0, math.tau, (2, 6))
    freqs = frequency * gen.uniform(0.3, 1.6, (2, 6))

    def edge(u, v):
        side = 0 if v < 0 else 1
        tear = sum(math.sin(u * f + p) for f, p in zip(freqs[side], phases[side])) / 3.0
        return tear * roughness * abs(v) ** 3

    return edge


def closest_on_segments(points, start, end):
    """Distance and parameter of each point against a capsule axis."""
    axis = end - start
    t = np.clip(((points - start) @ axis) / max(axis @ axis, 1e-9), 0, 1)
    return np.linalg.norm(points - (start + t[:, None] * axis), axis=1), t
