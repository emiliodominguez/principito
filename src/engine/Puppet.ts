import type { Quaternion, Vector3 } from "three";
import { Color, Group, type IUniform, Mesh, MeshStandardMaterial, type Object3D, SkinnedMesh } from "three";
import type { GLTF } from "three/addons/loaders/GLTFLoader.js";
import { clone as cloneSkeleton } from "three/addons/utils/SkeletonUtils.js";

import { makePuppetMaterial, type PuppetUniforms } from "#shaders/puppet";

import { PuppetRig } from "./StopMotionController";

/**
 * Creates the uniforms shared by all puppet materials.
 * @returns The uniforms.
 */
export function createPuppetUniforms(): PuppetUniforms & Record<string, IUniform> {
	return { uRim: { value: new Color(0.34, 0.4, 0.38) } };
}

/**
 * Prepares a loaded model's meshes for the stage.
 * @param root The model root.
 * @param uniforms Shared puppet uniforms.
 * @param shadows Whether meshes receive shadows.
 * @param cast Whether meshes cast them. Large sets often need not, since their occlusion is baked.
 */
export function dressMeshes(root: Object3D, uniforms: PuppetUniforms, shadows: boolean, cast = shadows): void {
	root.traverse((object) => {
		if (!(object instanceof Mesh)) return;
		object.castShadow = cast;
		object.receiveShadow = shadows;
		// Bind-pose bounds say nothing about where a posed skin is, so only skinned meshes skip culling.
		object.frustumCulled = !(object instanceof SkinnedMesh);
		if (object.material instanceof MeshStandardMaterial) {
			object.material.envMapIntensity = 0.42;
			makePuppetMaterial(object.material, uniforms);
		}
	});
}

/** A rigged character standing somewhere on the set. */
export class Puppet {
	readonly root = new Group();
	readonly rig: PuppetRig;

	constructor(model: GLTF, uniforms: PuppetUniforms, shadows: boolean) {
		const body = cloneSkeleton(model.scene);
		dressMeshes(body, uniforms, shadows);
		this.root.add(body);
		this.rig = new PuppetRig(body, model.animations);
	}

	/**
	 * Moves the puppet.
	 * @param position World position of its feet.
	 * @param rotation World orientation.
	 */
	place(position: Vector3, rotation: Quaternion): void {
		this.root.position.copy(position);
		this.root.quaternion.copy(rotation);
	}
}
