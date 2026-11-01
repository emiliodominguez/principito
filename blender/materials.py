"""Shader graphs for the physical stock of the set: pulp, crumpled tissue, card and foil.

These graphs are only ever evaluated by Cycles during baking. Their output lands in
colour, roughness and normal textures, which is what reaches the browser, so they
can be as expensive as the look requires.

Everything uses object-space coordinates, which means no detail depends on UV
layout and nothing shows a seam.
"""

import bpy

import textures
from sculpt import srgb


class Graph:
    """A thin wrapper over a material node tree that keeps graph-building terse."""

    def __init__(self, name):
        self.material = bpy.data.materials.new(name)
        self.material.use_nodes = True
        self.tree = self.material.node_tree
        self.bsdf = next(n for n in self.tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")

    def node(self, kind, **props):
        node = self.tree.nodes.new(kind)
        for key, value in props.items():
            setattr(node, key, value)
        return node

    def wire(self, source, target):
        self.tree.links.new(source, target)

    def coords(self):
        return self.node("ShaderNodeTexCoord").outputs["Object"]

    def scaled(self, vector, scale):
        mapping = self.node("ShaderNodeVectorMath", operation="SCALE")
        self.wire(vector, mapping.inputs[0])
        mapping.inputs["Scale"].default_value = scale
        return mapping.outputs[0]

    def noise(self, vector, scale, detail=6.0, roughness=0.55, distortion=0.0):
        node = self.node("ShaderNodeTexNoise")
        self.wire(vector, node.inputs["Vector"])
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = roughness
        node.inputs["Distortion"].default_value = distortion
        return node

    def math(self, operation, a, b=None, clamp=False):
        node = self.node("ShaderNodeMath", operation=operation, use_clamp=clamp)
        for socket, value in zip(node.inputs, (a, b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                socket.default_value = value
            else:
                self.wire(value, socket)
        return node.outputs[0]

    def ramp(self, value, stops, constant=False):
        node = self.node("ShaderNodeValToRGB")
        self.wire(value, node.inputs["Fac"])
        ramp = node.color_ramp
        if constant:
            ramp.interpolation = "CONSTANT"
        while len(ramp.elements) < len(stops):
            ramp.elements.new(0.5)
        for element, (position, shade) in zip(ramp.elements, stops):
            element.position = position
            element.color = (*shade, 1.0) if len(shade) == 3 else shade
        return node.outputs["Color"]

    def mix(self, blend, factor, a, b):
        node = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend, clamp_factor=True)
        for socket, value in zip((node.inputs["Factor"], node.inputs["A"], node.inputs["B"]), (factor, a, b)):
            if isinstance(value, (int, float)):
                socket.default_value = value
            elif isinstance(value, tuple):
                socket.default_value = value
            else:
                self.wire(value, socket)
        return node.outputs["Result"]

    def attribute(self, name="paint"):
        node = self.node("ShaderNodeVertexColor", layer_name=name)
        return node.outputs["Color"]

    def bump(self, height, strength, distance=0.02, normal=None):
        node = self.node("ShaderNodeBump")
        node.inputs["Strength"].default_value = strength
        node.inputs["Distance"].default_value = distance
        self.wire(height, node.inputs["Height"])
        if normal is not None:
            self.wire(normal, node.inputs["Normal"])
        return node.outputs[0]

    def finish(self, color, roughness, normal=None, metallic=0.0):
        if isinstance(color, tuple):
            self.bsdf.inputs["Base Color"].default_value = color
        else:
            self.wire(color, self.bsdf.inputs["Base Color"])
        if isinstance(roughness, (int, float)):
            self.bsdf.inputs["Roughness"].default_value = roughness
        else:
            self.wire(roughness, self.bsdf.inputs["Roughness"])
        self.bsdf.inputs["Metallic"].default_value = metallic
        if normal is not None:
            self.wire(normal, self.bsdf.inputs["Normal"])
        return self.material


def rgba(color):
    """Return a four-channel tuple for a linear colour array."""
    return (float(color[0]), float(color[1]), float(color[2]), 1.0)


def paper_fibre(graph, vector):
    """Fine pulp height: long stretched fibres over a soft tooth."""
    stretched = graph.node("ShaderNodeMapping")
    graph.wire(vector, stretched.inputs["Vector"])
    stretched.inputs["Scale"].default_value = (1.0, 7.0, 1.0)
    stretched.inputs["Rotation"].default_value = (0.3, 0.9, 0.5)
    fibres = graph.noise(stretched.outputs[0], 130.0, detail=7.0, roughness=0.6)
    tooth = graph.noise(vector, 420.0, detail=4.0, roughness=0.5)
    return graph.math("ADD", graph.math("MULTIPLY", fibres.outputs["Fac"], 0.6), graph.math("MULTIPLY", tooth.outputs["Fac"], 0.4))


def pulp(name):
    """Painted papier-mâché: the head and hands. Colour comes from the painted attribute."""
    graph = Graph(name)
    vector = graph.coords()
    painted = graph.attribute()
    lumps = graph.noise(vector, 26.0, detail=5.0, roughness=0.5)
    strokes_map = graph.node("ShaderNodeMapping")
    graph.wire(vector, strokes_map.inputs["Vector"])
    strokes_map.inputs["Scale"].default_value = (1.0, 1.3, 2.4)
    strokes_map.inputs["Rotation"].default_value = (0.2, 0.4, 0.6)
    strokes = graph.noise(strokes_map.outputs[0], 15.0, detail=8.0, roughness=0.6)
    fibre = paper_fibre(graph, vector)

    # Thin gouache: brush strokes lift and darken the colour without changing its hue much.
    tint = graph.ramp(strokes.outputs["Fac"], [(0.3, (0.93, 0.92, 0.90)), (0.7, (1.04, 1.03, 1.02))])
    color = graph.mix("MULTIPLY", 1.0, painted, tint)
    speck = graph.ramp(graph.noise(vector, 230.0, detail=3.0).outputs["Fac"], [(0.60, (1.0, 1.0, 1.0)), (0.72, (0.80, 0.74, 0.68))])
    color = graph.mix("MULTIPLY", 1.0, color, speck)

    height = graph.math("ADD", graph.math("MULTIPLY", fibre, 0.55), graph.math("MULTIPLY", lumps.outputs["Fac"], 0.75))
    height = graph.math("ADD", height, graph.math("MULTIPLY", strokes.outputs["Fac"], 0.35))
    normal = graph.bump(height, 0.85, 0.014)
    roughness = graph.math("ADD", 0.62, graph.math("MULTIPLY", strokes.outputs["Fac"], 0.22))
    return graph.finish(color, roughness, normal)


def fold_sample(graph, vector, tile):
    """Sample the simulated fold field in object space, box-projected so it never needs UVs."""
    node = graph.node("ShaderNodeTexImage", projection="BOX", projection_blend=0.3, extension="REPEAT", interpolation="Cubic")
    node.image = textures.fold_image()
    graph.wire(graph.scaled(vector, tile), node.inputs["Vector"])
    split = graph.node("ShaderNodeSeparateColor")
    graph.wire(node.outputs["Color"], split.inputs[0])
    return split.outputs[0], split.outputs[1]


def crumpled(name, tile=1.0, folds=1.0, fibre_strength=0.5, line_dark=0.5, line_rub=0.3, collage=None):
    """Crushed paper from the simulated fold field. Colour comes from the painted attribute.

    `tile` sets how many fold tiles fit per set unit, `folds` the relief, and the two
    line values how far dye has pooled in the valleys and rubbed off the ridges.
    `collage` is (scale, stops): overlapping torn sheets of colour, multiplied into the paint,
    with a raised step and a pale fibre rim wherever one sheet ends on top of another.
    """
    graph = Graph(name)
    vector = graph.coords()
    wander = graph.noise(vector, 3.0, detail=2.0)
    offset = graph.node("ShaderNodeVectorMath", operation="SCALE")
    graph.wire(wander.outputs["Color"], offset.inputs[0])
    offset.inputs["Scale"].default_value = 0.06
    shifted = graph.node("ShaderNodeVectorMath", operation="ADD")
    graph.wire(vector, shifted.inputs[0])
    graph.wire(offset.outputs[0], shifted.inputs[1])
    coords = shifted.outputs[0]

    broad_height, broad_lines = fold_sample(graph, coords, tile)
    fine_height, fine_lines = fold_sample(graph, coords, tile * 2.9)
    height = graph.math("ADD", graph.math("MULTIPLY", broad_height, 1.0), graph.math("MULTIPLY", fine_height, 0.28))
    fibre = paper_fibre(graph, vector)
    micro = graph.bump(fibre, fibre_strength, 0.009)
    painted = graph.attribute()
    if collage:
        scale, stops = collage
        field = graph.noise(coords, scale, detail=2.5, roughness=0.5, distortion=0.2)
        torn = graph.noise(vector, 60.0, detail=5.0, roughness=0.6)
        edge = graph.math("ADD", field.outputs["Fac"], graph.math("MULTIPLY", graph.math("SUBTRACT", torn.outputs["Fac"], 0.5), 0.022))
        sheets = graph.ramp(edge, stops, constant=True)
        shifted_edge = graph.math("ADD", edge, 0.007)
        beyond = graph.ramp(shifted_edge, stops, constant=True)
        difference = graph.node("ShaderNodeVectorMath", operation="DISTANCE")
        graph.wire(sheets, difference.inputs[0])
        graph.wire(beyond, difference.inputs[1])
        rim = graph.math("GREATER_THAN", difference.outputs["Value"], 0.01)
        painted = graph.mix("MULTIPLY", 1.0, painted, sheets)
        painted = graph.mix("MIX", graph.math("MULTIPLY", rim, 0.05), painted, (0.9, 0.87, 0.74, 1.0))
        layers = graph.node("ShaderNodeRGBToBW")
        graph.wire(sheets, layers.inputs[0])
        height = graph.math("ADD", height, graph.math("MULTIPLY", layers.outputs[0], 0.2))
    normal = graph.bump(height, min(folds, 1.0), 0.55 * max(folds, 1.0) / tile, micro)

    lines = graph.math("ADD", broad_lines, graph.math("MULTIPLY", fine_lines, 0.5))
    # Dye pools in the low side of each fold and rubs thin along the crest.
    shade = graph.ramp(broad_height, [(0.3, (0.74, 0.68, 0.58)), (0.5, (0.98, 0.98, 0.96)), (0.7, (1.12, 1.11, 1.05))])
    color = graph.mix("MULTIPLY", min(folds, 1.0), painted, shade)
    color = graph.mix("MULTIPLY", graph.math("MULTIPLY", lines, line_dark), color, (0.52, 0.46, 0.34, 1.0))
    color = graph.mix("SCREEN", graph.math("MULTIPLY", graph.math("MULTIPLY", fine_lines, fine_height), line_rub), color, (0.9, 0.85, 0.7, 1.0))
    mottling = graph.ramp(graph.noise(vector, 7.0, detail=7.0, roughness=0.62).outputs["Fac"], [(0.35, (0.90, 0.89, 0.85)), (0.65, (1.05, 1.04, 1.0))])
    color = graph.mix("MULTIPLY", 1.0, color, mottling)
    roughness = graph.math("ADD", 0.66, graph.math("MULTIPLY", fibre, 0.2))
    return graph.finish(color, roughness, normal)


def clay(name, thumb=0.6):
    """Modelling clay: soft lumps, smears from the tool, and patches of real fingerprint ridges."""
    graph = Graph(name)
    vector = graph.coords()
    painted = graph.attribute()
    lumps = graph.noise(vector, 13.0, detail=5.0, roughness=0.52)
    smear_map = graph.node("ShaderNodeMapping")
    graph.wire(vector, smear_map.inputs["Vector"])
    smear_map.inputs["Scale"].default_value = (1.0, 5.0, 1.6)
    smear_map.inputs["Rotation"].default_value = (0.5, 0.2, 1.1)
    smears = graph.noise(smear_map.outputs[0], 18.0, detail=4.0, roughness=0.5)

    # Fingerprints: warped rings, only where a mask says a finger pressed.
    rings = graph.node("ShaderNodeTexWave", wave_type="RINGS", rings_direction="SPHERICAL", wave_profile="SIN")
    warped = graph.noise(vector, 6.0, detail=2.0)
    offset = graph.node("ShaderNodeVectorMath", operation="SCALE")
    graph.wire(warped.outputs["Color"], offset.inputs[0])
    offset.inputs["Scale"].default_value = 0.32
    shifted = graph.node("ShaderNodeVectorMath", operation="ADD")
    graph.wire(vector, shifted.inputs[0])
    graph.wire(offset.outputs[0], shifted.inputs[1])
    graph.wire(shifted.outputs[0], rings.inputs["Vector"])
    rings.inputs["Scale"].default_value = 62.0
    rings.inputs["Distortion"].default_value = 3.0
    rings.inputs["Detail"].default_value = 2.0
    patch = graph.ramp(graph.noise(vector, 3.4, detail=2.0).outputs["Fac"], [(0.52, (0.0, 0.0, 0.0)), (0.6, (1.0, 1.0, 1.0))])
    print_height = graph.math("MULTIPLY", rings.outputs["Fac"], patch)

    height = graph.math("ADD", graph.math("MULTIPLY", lumps.outputs["Fac"], 1.0), graph.math("MULTIPLY", smears.outputs["Fac"], 0.32))
    height = graph.math("ADD", height, graph.math("MULTIPLY", print_height, 0.08 * thumb))
    normal = graph.bump(height, 0.62, 0.03)
    tone = graph.ramp(lumps.outputs["Fac"], [(0.35, (0.9, 0.89, 0.87)), (0.65, (1.05, 1.05, 1.04))])
    color = graph.mix("MULTIPLY", 1.0, painted, tone)
    color = graph.mix("MULTIPLY", graph.math("MULTIPLY", print_height, 0.14), color, (0.72, 0.68, 0.64, 1.0))
    roughness = graph.math("ADD", 0.56, graph.math("MULTIPLY", smears.outputs["Fac"], 0.26))
    return graph.finish(color, roughness, normal)


def foil(name):
    """Gold-leafed card for the stars: flat facets that flash as they turn."""
    graph = Graph(name)
    vector = graph.coords()
    fibre = paper_fibre(graph, vector)
    normal = graph.bump(fibre, 0.22, 0.006)
    painted = graph.attribute()
    # Baked as a dielectric: a metal has no diffuse colour for Cycles to bake. Metalness is added to the ORM map later.
    return graph.finish(painted, 0.36, normal)


def card(name):
    """Plain painted card or matte clay with very slight tooth: threads, buttons, small props."""
    graph = Graph(name)
    vector = graph.coords()
    fibre = paper_fibre(graph, vector)
    normal = graph.bump(fibre, 0.35, 0.008)
    painted = graph.attribute()
    return graph.finish(painted, 0.72, normal)


def gloss_bead(name):
    """Enamel beads for the eyes."""
    graph = Graph(name)
    return graph.finish(rgba(srgb("#14110F")), 0.22)


def bake_free_thread():
    """Pale linen thread: a flat material that needs no texture."""
    graph = Graph("thread")
    return graph.finish(rgba(srgb("#E9DFC2")), 0.9)


def flat_paper(color):
    """Plain untextured paper, for tiny things that never come near the lens."""
    graph = Graph("flat_paper")
    return graph.finish(rgba(srgb(color)), 0.85)
