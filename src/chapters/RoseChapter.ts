import { Group, Mesh, Quaternion, Vector3 } from "three";

import { dressMeshes } from "#engine/Puppet";
import { PuppetRig } from "#engine/StopMotionController";
import { createGlass } from "#shaders/glass";
import { frameAtProgress, frameInCycle } from "#story/cadence";
import { progressIn } from "#story/timeline";
import { PLANET_RADIUS, ROSE_ANGLE, WALK_END_ANGLE } from "#story/world";

import { Chapter, type Moment } from "./Chapter";
import { type PlanetPivot, planetPivot } from "./planet-pose";

const FEET = new Vector3();
const FACING = new Quaternion();
const BLOOM = new Vector3();
const LAMP = new Vector3();
const UP = new Vector3(0, 1, 0);
/** The warm lamp sits low and to the front of the bloom. */
const LAMP_OFFSET = new Vector3(0.5, -0.1, 1.5);
/** How far along the planet one full walk cycle carries him. */
const STRIDE = 0.15;
/** Rest heading of the walk: three-quarters toward camera, heading for the rose. */
const WALK_HEADING = 1.05;

/** Chapter 3: he walks across his world, kneels, and the rose fills the frame. */
export class RoseChapter extends Chapter {
	private pivot: PlanetPivot | undefined;
	private readonly rose = new Group();
	private rig: PuppetRig | undefined;
	private touchedAt = -100;

	/** Plants the rose and sets the dome over it. */
	override async prepare(): Promise<void> {
		const { stage } = this;
		const model = await stage.model("rose");
		const dome = model.scene.getObjectByName("dome");
		if (dome) dome.removeFromParent();
		dressMeshes(model.scene, stage.uniforms, stage.settings.shadowSize > 0);
		this.rose.add(model.scene);
		if (dome instanceof Mesh) {
			const glass = createGlass();
			dome.material = glass;
			dome.renderOrder = 5;
			this.rose.add(dome);
		}
		this.rig = new PuppetRig(model.scene, model.animations);
		this.pivot = planetPivot(stage.props, stage.scene);
		this.pivot.group.add(this.rose);
		// Seated on the measured ground, a touch low, so the mound beds into the surface all the way round.
		this.rose.position.set(Math.sin(ROSE_ANGLE), Math.cos(ROSE_ANGLE), 0).multiplyScalar(this.pivot.groundRadius(ROSE_ANGLE) - 0.055);
		this.rose.quaternion.setFromUnitVectors(UP, this.rose.position.clone().normalize());
	}

	/**
	 * The chapter's blocking: walk, kneel, reach. Everything is derived from `t`.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	override update(t: number, moment: Moment): void {
		const { pivot, rig } = this;
		if (!pivot || !rig) return;
		const touched = moment.seconds - this.touchedAt;
		if (touched >= 0 && touched < 2) rig.pose("touched", touched * 12);
		else rig.pose("idle", moment.clock % 48);
		rig.commit();

		if (!moment.owner) return;
		const { prince } = this.stage;
		const walking = progressIn(t, 0.0, 0.3);
		const angle = walking * WALK_END_ANGLE;
		pivot.set(angle, 0);
		const facing = progressIn(t, 0.3, 0.36);
		const heading = WALK_HEADING + (1.38 - WALK_HEADING) * facing;
		pivot.standing(angle, heading, angle, FEET, FACING);
		prince.place(FEET, FACING);
		if (t < 0.01) prince.rig.pose("stand", moment.clock % 36);
		else if (walking < 1) prince.rig.pose("walk", frameInCycle(angle / STRIDE, 12));
		else if (t < 0.44) prince.rig.pose("kneel", frameAtProgress(progressIn(t, 0.31, 0.43), 20));
		else if (t < 0.6) prince.rig.pose("kneel_idle", moment.clock % 36);
		else prince.rig.pose("reach", frameAtProgress(progressIn(t, 0.6, 0.86), 30));
	}

	/**
	 * Follows the bloom once the planet has settled for this frame.
	 */
	override afterPose(): void {
		if (!this.pivot) return;
		BLOOM.set(Math.sin(ROSE_ANGLE), Math.cos(ROSE_ANGLE), 0)
			.multiplyScalar(PLANET_RADIUS + 0.75)
			.applyQuaternion(this.pivot.group.quaternion);
		this.stage.lighting.placeLamp(LAMP.copy(BLOOM).add(LAMP_OFFSET));
	}

	/**
	 * Reports where the bloom is.
	 * @param id The hotspot.
	 * @returns The bloom's world position.
	 */
	override hotspot(id: string): Vector3 | undefined {
		return id === "rose" ? BLOOM : undefined;
	}

	/**
	 * Lets the rose answer a touch.
	 * @param id The hotspot.
	 * @param seconds The time of the touch.
	 */
	override activate(id: string, seconds: number): void {
		if (id === "rose") this.touchedAt = seconds;
	}
}
