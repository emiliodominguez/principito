import { Quaternion, Vector3 } from "three";

import { dressMeshes } from "#engine/Puppet";
import { WALK_END_ANGLE } from "#story/world";

import { Chapter, type Moment } from "./Chapter";
import { type PlanetPivot, planetPivot } from "./planet-pose";

const FEET = new Vector3();
const FACING = new Quaternion();
/** Spin before the chapter, so the far side of the planet arrives as the camera circles it. */
const START_SPIN = -1.1;
/** He turns slowly through the chapter, arriving already facing the way he is about to walk. */
const OPEN_HEADING = -0.06;
const WALK_START_HEADING = 1.05;

/** Chapter 2: the camera pulls away and the single set reveals itself as a planet. */
export class AsteroidChapter extends Chapter {
	private pivot: PlanetPivot | undefined;

	/** Brings the asteroid onto the set. */
	override async prepare(): Promise<void> {
		const { stage } = this;
		const model = await stage.model("asteroid");
		dressMeshes(model.scene, stage.uniforms, stage.settings.shadowSize > 0, false);
		this.pivot = planetPivot(stage.props, stage.scene);
		this.pivot.group.add(model.scene);
	}

	/**
	 * Rotates the planet with scroll.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	override update(t: number, moment: Moment): void {
		const pivot = this.pivot;
		if (!pivot) return;
		if (t <= 1) {
			pivot.set(0, START_SPIN * (1 - Math.max(0, t)));
		} else {
			// Later chapters may refine this, but a long jump must still land on a known orientation.
			pivot.set(WALK_END_ANGLE, 0);
		}
		if (moment.owner) {
			const { prince } = this.stage;
			pivot.standing(0, OPEN_HEADING + Math.max(0, t) * (WALK_START_HEADING - OPEN_HEADING), 0, FEET, FACING);
			prince.place(FEET, FACING);
			prince.rig.pose("stand", moment.clock % 36);
		}
	}
}
