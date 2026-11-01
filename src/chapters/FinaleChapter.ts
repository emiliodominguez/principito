import { Euler, InstancedMesh, Matrix4, Mesh, type MeshStandardMaterial, Quaternion, Vector3 } from "three";

import { frameAtProgress, poseNoise } from "#story/cadence";
import { progressIn, smoothstep } from "#story/timeline";
import { FOX_HILL, FOX_HILL_TOP, FOX_LINE_Z } from "#story/world";

import { Chapter, type Moment } from "./Chapter";

const UP = new Vector3(0, 1, 0);
const FEET = new Vector3();
const FACING = new Quaternion();
const CENTER = new Vector3(FOX_HILL[0], FOX_HILL[1] + 8.5, FOX_HILL[2] - 8);
const position = new Vector3();
const scale = new Vector3();
const orientation = new Quaternion();
const euler = new Euler();
const matrix = new Matrix4();

/** Chapter 6: the camera withdraws, and the sky fills with gold, one star at a time. */
export class FinaleChapter extends Chapter {
	private field: InstancedMesh | undefined;
	private gold: MeshStandardMaterial | undefined;
	private shown = -1;
	private rangAt = -100;
	private ringing = false;
	private lastPose = -1;

	/** Builds the field of distant stars. */
	override async prepare(): Promise<void> {
		const { stage } = this;
		const model = await stage.model("stars");
		const star = model.scene.getObjectByName("star_a");
		if (!(star instanceof Mesh)) return;
		// Lit from within, so the gold lifts as the sky darkens. Set up now, so nothing has to recompile mid-scene.
		const gold = star.material as MeshStandardMaterial;
		gold.emissive.set(0xffffff);
		gold.emissiveMap = gold.map;
		gold.emissiveIntensity = 0;
		gold.needsUpdate = true;
		this.gold = gold;
		this.field = new InstancedMesh(star.geometry, gold, stage.settings.fieldStars);
		this.field.count = 0;
		this.field.frustumCulled = false;
		stage.scene.add(this.field);
	}

	/**
	 * Reveals stars and brings the Prince to his feet.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	override update(t: number, moment: Moment): void {
		const { field } = this;
		if (!field) return;
		const reveal = progressIn(t, 0.14, 0.9);
		if (this.gold) this.gold.emissiveIntensity = smoothstep(0.3, 0.95, t) * 0.95;
		CENTER.y = FOX_HILL[1] + 7 + 16 * progressIn(t, 0.6, 0.86);
		const target = Math.floor(reveal ** 1.5 * field.instanceMatrix.count);
		const ringing = moment.seconds - this.rangAt < 3;
		if (target !== this.shown || (ringing && moment.pose !== this.lastPose) || this.ringing !== ringing) {
			this.shown = target;
			this.layOut(target, moment, ringing);
		}
		this.ringing = ringing;
		this.lastPose = moment.pose;
		if (!moment.owner) return;
		const { prince } = this.stage;
		const fox = this.stage.props.get("fox-ground");
		const ground = typeof fox === "function" ? (fox as (x: number) => number)(-0.82) : FOX_HILL[1] + FOX_HILL_TOP;
		FEET.set(FOX_HILL[0] - 0.82, ground, FOX_HILL[2] + FOX_LINE_Z);
		FACING.setFromAxisAngle(UP, 1.02 * (1 - progressIn(t, 0, 0.3)));
		prince.place(FEET, FACING);
		if (t < 0.22) prince.rig.pose("stand_up", frameAtProgress(progressIn(t, 0, 0.22), 24));
		else prince.rig.pose("look_up", moment.clock % 36);
	}

	/**
	 * Reports the final hotspot, which sits among the stars above the hill.
	 * @param id The hotspot.
	 * @returns A world position.
	 */
	override hotspot(id: string): Vector3 | undefined {
		return id === "stars" ? CENTER : undefined;
	}

	/**
	 * Sets every star ringing: a ripple through the field, and a push on the hanging ones.
	 * @param id The hotspot.
	 * @param seconds The time of the touch.
	 */
	override activate(id: string, seconds: number): void {
		if (id !== "stars") return;
		this.rangAt = seconds;
		const { stars } = this.stage;
		for (const star of stars.stars) {
			star.touched = -100;
			stars.touch(star, seconds + poseNoise(star.index, 41) * 0.6, 0.26);
		}
	}

	/**
	 * Writes field star transforms.
	 * @param count How many stars are lit.
	 * @param moment The moment being drawn.
	 * @param ringing Whether the ripple is running.
	 */
	private layOut(count: number, moment: Moment, ringing: boolean): void {
		const { field } = this;
		if (!field) return;
		field.count = count;
		const since = moment.seconds - this.rangAt;
		for (let i = 0; i < count; i++) {
			const a = poseNoise(i, 51) * Math.PI * 2;
			const b = poseNoise(i, 52);
			const reach = 8 + b * b * 52;
			const across = Math.cos(a) * reach * 1.5;
			const high = -4 + poseNoise(i, 53) * 62;
			const deep = -6 - poseNoise(i, 54) * 34;
			position.set(FOX_HILL[0] + across, FOX_HILL[1] + high, FOX_HILL[2] + deep);
			const distance = Math.hypot(across, high - 14);
			const ripple = ringing ? Math.max(0, 1 - Math.abs(since * 16 - distance) / 7) : 0;
			scale.setScalar((0.2 + poseNoise(i, 55) ** 2 * 0.85) * (1 + ripple * 0.7));
			// Turned toward the lens, so each reads as a star rather than an edge-on sliver.
			euler.set(0.3 * (poseNoise(i, 56) - 0.5), (poseNoise(i, 58) - 0.5) * 0.8 + ripple * 1.4, poseNoise(i, 57) * 1.2);
			orientation.setFromEuler(euler);
			field.setMatrixAt(i, matrix.compose(position, orientation, scale));
		}
		field.instanceMatrix.needsUpdate = true;
	}
}
