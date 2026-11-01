import { Quaternion, Vector3 } from "three";

import { frameAtProgress } from "#story/cadence";
import { progressIn } from "#story/timeline";
import { PLANET_RADIUS } from "#story/world";

import { Chapter, type Moment } from "./Chapter";

const FEET = new Vector3(0, PLANET_RADIUS, 0);
const FACING = new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), -0.06);

/** Chapter 1: the Prince points at a star, then lowers his hand as the frame opens up. */
export class UniverseChapter extends Chapter {
	/** The opening needs only what the stage already loaded. */
	override prepare(): Promise<void> {
		this.ready = true;
		return Promise.resolve();
	}

	/**
	 * Holds the pointing pose, then scrubs the arm down near the end of the chapter.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	override update(t: number, moment: Moment): void {
		if (!moment.owner) return;
		const { prince } = this.stage;
		prince.place(FEET, FACING);
		const lowering = progressIn(t, 0.66, 0.98);
		if (lowering <= 0) {
			prince.rig.pose("point", moment.clock % 24);
		} else {
			prince.rig.pose("lower_arm", frameAtProgress(lowering, 20));
		}
	}
}
