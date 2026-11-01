import { Group, Quaternion, Vector3 } from "three";

import { readProfile } from "#engine/ground";
import manifest from "#story/assets-manifest.json" with { type: "json" };

const UP = new Vector3(0, 1, 0);
const ROLL_AXIS = new Vector3(0, 0, 1);
const local = new Vector3();
const yaw = new Quaternion();
const tip = new Quaternion();

/**
 * The asteroid's rotation rig. `turn` is the planet rolling under the Prince's feet;
 * `spin` is its slow rotation about the crown, which leaves him where he stands.
 */
export class PlanetPivot {
	readonly group = new Group();
	readonly position = new Vector3();
	readonly rotation = new Quaternion();

	/**
	 * Ground radius at a point along the walking line.
	 * @param angle Radians from the crown.
	 * @returns Distance from the planet's centre.
	 */
	groundRadius(angle: number): number {
		return readProfile(manifest.asteroid.ground, 0, manifest.asteroid.groundStep, angle);
	}

	/**
	 * Sets the planet's orientation.
	 * @param turn Radians rolled toward the Prince.
	 * @param spin Radians about the crown.
	 */
	set(turn: number, spin: number): void {
		this.group.quaternion.setFromAxisAngle(ROLL_AXIS, turn);
		yaw.setFromAxisAngle(UP, spin);
		this.group.quaternion.multiply(yaw);
	}

	/**
	 * Works out a world placement for something standing on the planet's surface.
	 * @param angle Radians from the planet's crown toward its +X side.
	 * @param heading World yaw of the figure.
	 * @param turn The planet's current roll.
	 * @param position Receives the world position.
	 * @param rotation Receives the world orientation.
	 */
	standing(angle: number, heading: number, turn: number, position: Vector3, rotation: Quaternion): void {
		local.set(Math.sin(angle - turn), Math.cos(angle - turn), 0);
		position.copy(local).multiplyScalar(this.groundRadius(angle));
		tip.setFromUnitVectors(UP, local);
		yaw.setFromAxisAngle(UP, heading);
		rotation.copy(tip).multiply(yaw);
	}
}

/**
 * Fetches the shared planet rig, creating it for whichever chapter asks first.
 * @param props The stage's shared props.
 * @param parent Where the rig attaches.
 * @param parent.add Adds a child object.
 * @returns The rig.
 */
export function planetPivot(props: Map<string, unknown>, parent: { add(object: Group): unknown }): PlanetPivot {
	const existing = props.get("planet");
	if (existing instanceof PlanetPivot) return existing;
	const pivot = new PlanetPivot();
	parent.add(pivot.group);
	props.set("planet", pivot);
	return pivot;
}
