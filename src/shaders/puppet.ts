import type { Color, IUniform, MeshStandardMaterial } from "three";

/** Uniforms shared by every puppet material. */
export interface PuppetUniforms {
	readonly uRim: IUniform<Color>;
}

/**
 * Adds the soft scatter paper fibres give at grazing angles, which keeps a silhouette
 * from reading as a hard CG surface.
 * @param material The material to patch.
 * @param uniforms The shared uniforms.
 */
export function makePuppetMaterial(material: MeshStandardMaterial, uniforms: PuppetUniforms): void {
	material.onBeforeCompile = (shader) => {
		Object.assign(shader.uniforms, uniforms);
		shader.fragmentShader = shader.fragmentShader
			.replace(
				"#include <common>",
				/* glsl */ `#include <common>
				uniform vec3 uRim;`,
			)
			.replace(
				"#include <lights_fragment_end>",
				/* glsl */ `#include <lights_fragment_end>
				float grazing = 1.0 - saturate(dot(normal, normalize(vViewPosition)));
				reflectedLight.indirectDiffuse += diffuseColor.rgb * uRim * grazing * grazing * grazing;`,
			);
	};
	material.customProgramCacheKey = () => "puppet";
}
