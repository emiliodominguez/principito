import { CylinderGeometry, DoubleSide, Group, Mesh, MeshBasicMaterial, MirroredRepeatWrapping, Quaternion, Vector3 } from "three";

import { readProfile } from "#engine/ground";
import { dressMeshes, Puppet } from "#engine/Puppet";
import { frameAtProgress } from "#story/cadence";
import { progressIn, smoothstep } from "#story/timeline";
import manifest from "#story/assets-manifest.json" with { type: "json" };
import { FOX_HILL, FOX_LINE_Z } from "#story/world";

import { Chapter, type Moment } from "./Chapter";

const UP = new Vector3(0, 1, 0);
const FEET = new Vector3();
const FACING = new Quaternion();
/** Where the two meet, relative to the hill's centre. */
const PRINCE_X = -0.82;
const FOX_NEAR_X = 0.52;
/** Where he sits on each of the three days. */
const DAYS: readonly number[] = [2.5, 1.5, FOX_NEAR_X];
/** The two nights, at the darkest points of the chapter's light plot. */
const FIRST_NIGHT = 0.46;
const SECOND_NIGHT = 0.58;
/** How far his weight presses him into the ground. */
const SEATED_DEPTH = 0.02;
/** The knoll's sculpted radii, for working out the slope under him. */
const HILL_RADII = [4.4, 3.78, 1.76] as const;
const SLOPE = new Vector3();
const TURN = new Quaternion();

/** The cyclorama wraps the far side of the hill, leaving a gap on the side the camera arrives from. */
const ARC_LENGTH = 4.6;
const ARC_START = 2.9 - ARC_LENGTH / 2 + 0.5;
/** How far below the set the painted hills wait before they are needed. */
const FLAT_DROP = 34;

/** Chapter 5: a quiet hill, a fox who approaches, one held hand. */
export class FoxChapter extends Chapter {
	private fox: Puppet | undefined;
	private readonly set = new Group();
	private readonly flats: { sheet: Mesh; rest: number }[] = [];

	/** Builds the hill and the painted distance behind it. */
	override async prepare(): Promise<void> {
		const { stage } = this;
		const [hill, foxModel, far, near] = await Promise.all([
			stage.model("fox_hill"),
			stage.model("fox"),
			stage.painting("hills_far"),
			stage.painting("hills_near"),
		]);
		dressMeshes(hill.scene, stage.uniforms, stage.settings.shadowSize > 0, false);
		this.set.position.set(...FOX_HILL);
		this.set.add(hill.scene);
		// The painted hills are a curved cyclorama behind the knoll, so there is no sheet end to see from any shot.
		for (const [map, radius, y] of [
			[far, 42, -3],
			[near, 30, -3.4],
		] as const) {
			map.wrapS = MirroredRepeatWrapping;
			map.repeat.x = 3;
			map.needsUpdate = true;
			const arc = new CylinderGeometry(radius, radius, radius * 0.72, 72, 1, true, ARC_START, ARC_LENGTH);
			const sheet = new Mesh(arc, new MeshBasicMaterial({ map, alphaTest: 0.5, side: DoubleSide }));
			sheet.position.set(0, y, 0);
			this.set.add(sheet);
			this.flats.push({ sheet, rest: y });
		}
		stage.scene.add(this.set);
		stage.props.set("fox-ground", (x: number) => this.ground(x));
		this.fox = new Puppet(foxModel, stage.uniforms, stage.settings.shadowSize > 0);
		this.fox.root.scale.setScalar(1.05);
		stage.scene.add(this.fox.root);
	}

	/**
	 * The chapter's blocking.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	override update(t: number, moment: Moment): void {
		const { fox } = this;
		if (!fox) return;
		// Painted hills are flats, raised into place as the camera turns toward them.
		const raised = smoothstep(-0.32, -0.08, t);
		for (const flat of this.flats) flat.sheet.position.y = flat.rest - (1 - raised) * FLAT_DROP;
		this.directFox(Math.min(t, 1), moment);
		if (!moment.owner) return;
		const { prince } = this.stage;
		const x = FOX_HILL[0] + PRINCE_X;
		FEET.set(x, this.ground(PRINCE_X) - SEATED_DEPTH, FOX_HILL[2] + FOX_LINE_Z);
		// He arrives upright from the flight, and settles into the slope as he sits.
		const seated = progressIn(t, 0.04, 0.16);
		this.settle(PRINCE_X, 1.02, seated);
		prince.place(FEET, FACING);
		if (t < 0.16) prince.rig.pose("land_sit", frameAtProgress(progressIn(t, 0, 0.16), 24));
		else if (t < 0.5) prince.rig.pose("sit_idle", moment.clock % 36);
		else prince.rig.pose("sit_reach", frameAtProgress(progressIn(t, 0.5, 0.74), 40));
	}

	/**
	 * Seats a character into the slope of the hill, as a soft puppet settles, rather than upright on tilted ground.
	 * @param x Offset across the hill.
	 * @param heading Yaw of the character.
	 * @param amount How far into the slope, 0 to 1.
	 */
	private settle(x: number, heading: number, amount = 1): void {
		SLOPE.set(x / HILL_RADII[0] ** 2, (FEET.y - FOX_HILL[1]) / HILL_RADII[2] ** 2, FOX_LINE_Z / HILL_RADII[1] ** 2).normalize();
		SLOPE.lerp(UP, 1 - amount).normalize();
		FACING.setFromUnitVectors(UP, SLOPE).multiply(TURN.setFromAxisAngle(UP, heading));
	}

	/**
	 * Ground height on the line they stand on.
	 * @param x Offset across the hill.
	 * @returns World height.
	 */
	ground(x: number): number {
		const { fox_hill: profile } = manifest;
		return FOX_HILL[1] + readProfile(profile.ground, profile.groundStart, profile.groundStep, x);
	}

	/**
	 * Walks the fox in along the hill, step for step with scroll.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	private directFox(t: number, moment: Moment): void {
		const fox = this.fox;
		if (!fox) return;
		// He never crosses the hill on screen. Each time the light goes down a day passes, and when
		// it returns he is sitting a little nearer. These moments match the fox chapter's light plot.
		const day = t < FIRST_NIGHT ? 0 : t < SECOND_NIGHT ? 1 : 2;
		const x = DAYS[day] ?? FOX_NEAR_X;
		FEET.set(FOX_HILL[0] + x, this.ground(x) - SEATED_DEPTH, FOX_HILL[2] + FOX_LINE_Z);
		this.settle(x, -1.0);
		fox.place(FEET, FACING);
		if (t < 0.72) fox.rig.pose("sit_idle", moment.clock % 36);
		else if (t < 0.86) fox.rig.pose("nuzzle", frameAtProgress(progressIn(t, 0.72, 0.86), 30));
		else fox.rig.pose("rest", moment.clock % 36);
		fox.rig.overlay("face", moment.clock);
		fox.rig.commit();
	}
}
