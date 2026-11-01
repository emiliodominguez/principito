import type { Scene } from "three";
import {
	Color,
	DynamicDrawUsage,
	Euler,
	type Group,
	InstancedMesh,
	type Material,
	Matrix4,
	Mesh,
	type MeshStandardMaterial,
	Quaternion,
	Vector3,
} from "three";

import { poseNoise } from "#story/cadence";
import { STAR_FIELD, type StarPlacement } from "#story/star-field";

const up = new Vector3();
const pivotPoint = new Vector3();
const position = new Vector3();
const scale = new Vector3();
const swing = new Quaternion();
const turn = new Quaternion();
const orientation = new Quaternion();
const matrix = new Matrix4();
const euler = new Euler();
const threadScale = new Vector3();

/**
 * Only the stars composed for the opening show their threads. The rest are seen from all
 * over the story, where a thread would stop short in mid-air and read as a stray line.
 */
const THREADED_STARS = 12;

interface StarState extends StarPlacement {
	/** Which star mesh this instance belongs to, and its slot. */
	readonly mesh: 0 | 1;
	readonly slot: number;
	readonly index: number;
	readonly phase: number;
	readonly frequency: number;
	/** Second at which it was last touched. */
	touched: number;
	/** Strength of the most recent touch. */
	impulse: number;
}

/** Gold paper stars on threads, instanced, each swaying at its own pace. */
export class HangingStars {
	readonly stars: StarState[] = [];

	private readonly meshes: readonly [InstancedMesh, InstancedMesh];
	private readonly threads: InstancedMesh;

	constructor(scene: Scene, source: Group, limit: number) {
		const placed = STAR_FIELD.slice(0, limit);
		const pieces = { a: find(source, "star_a"), b: find(source, "star_b"), thread: find(source, "thread") };
		const counts = [0, 0];
		this.stars = placed.map((star, index) => {
			const mesh = index % 3 === 2 ? 1 : 0;
			const slot = counts[mesh] ?? 0;
			counts[mesh] = slot + 1;
			return {
				...star,
				mesh,
				slot,
				index,
				phase: poseNoise(index, 1) * Math.PI * 2,
				frequency: 0.16 + poseNoise(index, 2) * 0.14,
				touched: -100,
				impulse: 0,
			};
		});
		this.meshes = [this.instanced(pieces.a, counts[0] ?? 0, scene), this.instanced(pieces.b, counts[1] ?? 0, scene)];
		const linen = pieces.thread.material as MeshStandardMaterial;
		linen.transparent = true;
		linen.opacity = 0.6;
		linen.depthWrite = false;
		this.threads = new InstancedMesh(pieces.thread.geometry, linen, THREADED_STARS);
		this.threads.instanceMatrix.setUsage(DynamicDrawUsage);
		this.threads.frustumCulled = false;
		scene.add(this.threads);
		const tint = new Color();
		for (const star of this.stars) {
			tint.setHSL(0.125 + poseNoise(star.index, 3) * 0.012, 1, 0.5 + poseNoise(star.index, 4) * 0.08).lerp(tint.clone().set(0xffffff), 0.72);
			this.meshes[star.mesh].setColorAt(star.slot, tint);
		}
		this.pose(0);
	}

	/**
	 * Fades the threads. They belong to the opening: seen from the flight, thread this long would cross the whole frame.
	 * @param amount Visibility, 0 to 1.
	 */
	fadeThreads(amount: number): void {
		this.threads.visible = amount > 0;
		(this.threads.material as MeshStandardMaterial).opacity = 0.6 * amount;
	}

	/**
	 * Gives a star a push.
	 * @param star The star.
	 * @param seconds The current time.
	 * @param strength Radians of swing.
	 */
	touch(star: StarState, seconds: number, strength = 0.2): void {
		if (seconds - star.touched < 0.8) return;
		star.touched = seconds;
		star.impulse = strength;
	}

	/**
	 * Recomputes star transforms.
	 * @param seconds Stage time.
	 */
	pose(seconds: number): void {
		for (const star of this.stars) {
			const drift = Math.sin(seconds * star.frequency * Math.PI * 2 + star.phase) * star.sway;
			const since = seconds - star.touched;
			const push = since >= 0 && since < 6 ? star.impulse * Math.exp(-since * 0.9) * Math.sin(since * 3.4) : 0;
			// A longer thread needs less angle for the same movement at the star.
			const angle = (drift + push) * Math.min(1, 16 / star.thread);
			pivotPoint.set(star.x, star.y + star.thread, star.z);
			swing.setFromAxisAngle(up.set(0, 0, 1), angle);
			position.set(0, -star.thread, 0).applyQuaternion(swing).add(pivotPoint);
			euler.set(star.tilt, star.yaw + Math.sin(seconds * star.frequency * 2.2 + star.phase) * 0.34 + push * 3, star.roll + angle);
			turn.setFromEuler(euler);
			orientation.copy(turn);
			scale.setScalar(star.size);
			this.meshes[star.mesh].setMatrixAt(star.slot, matrix.compose(position, orientation, scale));
			if (star.index < THREADED_STARS) {
				// Tied at the star's top point, so the thread never crosses its face.
				threadScale.set(0.0036, (star.thread - star.size * 0.92) * 0.9985, 0.0036);
				this.threads.setMatrixAt(star.index, matrix.compose(pivotPoint, swing, threadScale));
			}
		}
		for (const mesh of this.meshes) mesh.instanceMatrix.needsUpdate = true;
		this.threads.instanceMatrix.needsUpdate = true;
	}

	/**
	 * Builds one instanced mesh from a source mesh.
	 * @param mesh The source.
	 * @param count Instance count.
	 * @param scene Destination scene.
	 * @returns The instanced mesh.
	 */
	private instanced(mesh: Mesh, count: number, scene: Scene): InstancedMesh {
		const instanced = new InstancedMesh(mesh.geometry, mesh.material as Material, Math.max(1, count));
		instanced.instanceMatrix.setUsage(DynamicDrawUsage);
		instanced.frustumCulled = false;
		scene.add(instanced);
		return instanced;
	}
}

/**
 * Finds a named mesh inside a loaded model.
 * @param root The model root.
 * @param name The node name.
 * @returns The mesh.
 */
function find(root: Group, name: string): Mesh {
	const found = root.getObjectByName(name);
	if (found instanceof Mesh) return found;
	throw new Error(`model is missing mesh ${name}`);
}
