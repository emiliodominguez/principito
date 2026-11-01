import {
	CatmullRomCurve3,
	DoubleSide,
	DynamicDrawUsage,
	type Group,
	type Object3D,
	InstancedMesh,
	type Material,
	type MeshStandardMaterial,
	Matrix4,
	Mesh,
	MeshBasicMaterial,
	PlaneGeometry,
	Quaternion,
	type Texture,
	Vector3,
} from "three";

import { frameAtProgress, poseNoise } from "#story/cadence";
import { lerp, progressIn, smoothstep } from "#story/timeline";
import { FLIGHT_PATH, WALK_END_ANGLE } from "#story/world";

import { dressMeshes } from "#engine/Puppet";

import { Chapter, type Moment } from "./Chapter";
import { type PlanetPivot, planetPivot } from "./planet-pose";

const BIRDS = 9;
/** How far scenery travels to reach its mark. */
const SCENERY_TRAVEL = 30;
const KNEEL_HEADING = 1.38;
const SIT_HEADING = 1.02;
const FLIGHT_LANDING_X = -0.82;
/** The flight's average lens direction, which the composition below is written against. */
const CAMERA_RIGHT = new Vector3(0.6, 0, -0.8);
const CAMERA_AWAY = new Vector3(-0.8, 0, -0.6);
/** Cut paper sheets turn square to that lens. */
const SHEET_YAW = 0.93;
/** Nearly to the lens, so the raised arm stands clear of his head against the sky, as in the opening. */
const FLIGHT_HEADING = 1.2;
/** Distance from his feet up to the hands he hangs by. */
const HANGING_LENGTH = 1.7;
/** The flock floats this far above his fist, drifting slightly ahead of him. */
const FLOCK_HEIGHT = 1.2;
/** From the wrist bone to the middle of his palm, where the threads gather. */
const PALM_OFFSET = 0.09;
const FLOCK_LEAD = 0.5;
/** Wing frames in order: up, mid, down, mid. */
const WING_CYCLE: readonly number[] = [0, 1, 2, 1];
const UP = new Vector3(0, 1, 0);
const FEET = new Vector3();
const FACING = new Quaternion();
const TURN = new Quaternion();
const HAND = new Vector3();
const PIVOT = new Vector3();
const LEAD = new Vector3();
const threadTurn = new Quaternion();
const position = new Vector3();
const orientation = new Quaternion();
const scale = new Vector3();
const matrix = new Matrix4();
const direction = new Vector3();

/**
 * Suspended planets, composed around the flight: model, place along the path, then offsets to the
 * camera's right, up, and away from the lens, and a spin speed. A negative distance passes in front of
 * him, close to the lens and out of focus, which is what gives the flight its sense of depth.
 */
const PLANETS: ReadonlyArray<readonly [string, number, number, number, number, number]> = [
	["planet_ochre", 0.16, -1, 3.2, 5, 0.6],
	["planet_rose", 0.22, 2.5, -2.4, 7, 1],
	["planet_moss", 0.28, 1.5, 2.8, 3.5, 1.3],
	["planet_cream", 0.33, 1.2, -2.2, -4.5, 0.6],
	["planet_sea", 0.38, 0, -2.8, 9, 0.7],
	["planet_ring", 0.44, 2, 2.6, 5, 0.5],
	["planet_cream", 0.5, -1, -2.4, 4, 0.8],
	["planet_rose", 0.56, 3, 2, 8, 0.9],
	["planet_moss", 0.6, 0.6, 1.8, -4, 1.2],
	["planet_moss", 0.62, 0, -2.4, 3, 1.2],
	["planet_sea", 0.68, 2, 3.2, 10, 0.7],
	["planet_ochre", 0.74, 1, -2.6, 6, 0.6],
	["planet_ring", 0.8, 3, 2.2, 5, 0.5],
	["planet_cream", 0.86, 1.5, 3, 4.5, 0.8],
];

/** Flat cut paper layers well behind the action: painting, place along the path, right, up, away, width. */
const SHEETS: ReadonlyArray<readonly [string, number, number, number, number, number]> = [
	["cloud_b", 0.24, 1, -3.6, 13, 7],
	["cloud_a", 0.36, 3, 4, 12, 5],
	["cloud_b", 0.5, 2, 4.2, 14, 7],
	["cloud_a", 0.6, 4, -4, 12, 6],
	["cloud_c", 0.74, 3, 4.2, 12, 6],
	["cloud_a", 0.88, 4, -3.6, 13, 6],
];

/** Chapter 4: the flock lifts him away, and the set becomes a field of paper worlds. */
export class JourneyChapter extends Chapter {
	private pivot: PlanetPivot | undefined;
	private readonly curve = new CatmullRomCurve3(FLIGHT_PATH.map((point) => new Vector3(...point)));
	private readonly wings: InstancedMesh[] = [];
	private threads: InstancedMesh | undefined;
	private cord: MeshStandardMaterial | undefined;
	private readonly planetHomes: number[] = [];
	private readonly sheetHomes: number[] = [];
	private readonly planets: Group[] = [];
	private readonly sheets: Mesh[] = [];
	private palm: Object3D | undefined;

	/** Hangs the planets and clouds and builds the flock. */
	override async prepare(): Promise<void> {
		const { stage } = this;
		const [birds, worlds, ...paintings] = await Promise.all([
			stage.model("birds"),
			stage.model("paper_planets"),
			stage.painting("cloud_a"),
			stage.painting("cloud_b"),
			stage.painting("cloud_c"),
		]);
		const textures: Record<string, Texture | undefined> = { cloud_a: paintings[0], cloud_b: paintings[1], cloud_c: paintings[2] };
		dressMeshes(worlds.scene, stage.uniforms, false);
		for (const [name, along, right, up, away] of PLANETS) {
			const source = worlds.scene.getObjectByName(name);
			if (!source) continue;
			const copy = source.clone() as Group;
			this.curve.getPoint(along, position);
			position.addScaledVector(CAMERA_RIGHT, right).addScaledVector(UP, up).addScaledVector(CAMERA_AWAY, away);
			copy.position.copy(position);
			stage.scene.add(copy);
			this.planets.push(copy);
			this.planetHomes.push(position.y);
		}
		const plane = new PlaneGeometry(1, 0.5);
		for (const [name, along, right, up, away, width] of SHEETS) {
			const map = textures[name];
			if (!map) continue;
			this.curve.getPoint(along, position);
			position.addScaledVector(CAMERA_RIGHT, right).addScaledVector(UP, up).addScaledVector(CAMERA_AWAY, away);
			const sheet = new Mesh(plane, new MeshBasicMaterial({ map, alphaTest: 0.5, side: DoubleSide, color: 0xd8e4dd }));
			sheet.position.copy(position);
			sheet.scale.setScalar(width);
			sheet.rotation.y = SHEET_YAW;
			stage.scene.add(sheet);
			this.sheets.push(sheet);
			this.sheetHomes.push(position.y);
		}
		for (const name of ["bird_up", "bird_mid", "bird_down"]) {
			const bird = birds.scene.getObjectByName(name);
			if (bird instanceof Mesh) this.wings.push(this.flock(bird));
		}
		const starModel = await stage.model("stars");
		const thread = starModel.scene.getObjectByName("thread");
		if (thread instanceof Mesh) {
			// Its own material, so the flock's threads can fade as a set while staying tied at both ends.
			const cord = (thread.material as MeshStandardMaterial).clone();
			cord.transparent = true;
			cord.depthWrite = false;
			this.cord = cord;
			this.threads = new InstancedMesh(thread.geometry, cord, BIRDS);
			this.threads.instanceMatrix.setUsage(DynamicDrawUsage);
			this.threads.frustumCulled = false;
			stage.scene.add(this.threads);
		}
		stage.prince.root.traverse((object) => {
			if (object.name === "handL") this.palm = object;
		});
		this.pivot = planetPivot(stage.props, stage.scene);
	}

	/**
	 * Advances the flight.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	override update(t: number, moment: Moment): void {
		this.moveScenery(t);
		this.planets.forEach((planet, index) => {
			const row = PLANETS[index];
			planet.rotation.y = (Math.floor(moment.pose / 3) * 0.018 * (row?.[5] ?? 1) + index) % (Math.PI * 2);
		});
		const flock = t > -0.05 && t < 1.2;
		for (const mesh of [...this.wings, this.threads]) if (mesh) mesh.visible = flock;
		// The flock's path is smooth and belongs to the story, so everything hangs from this point rather than from a posed bone.
		const ground = this.stage.props.get("fox-ground");
		const landing = this.curve.points.at(-1);
		if (typeof ground === "function" && landing) landing.y = (ground as (x: number) => number)(FLIGHT_LANDING_X);
		this.curve.getPoint(progressIn(t, 0.1, 1), PIVOT).addScaledVector(UP, HANGING_LENGTH);
		if (!moment.owner) return;
		const { pivot } = this;
		const { prince } = this.stage;
		if (!pivot) return;
		pivot.set(WALK_END_ANGLE, 0);
		const rising = progressIn(t, 0, 0.1);
		const leaving = progressIn(t, 0.1, 1);
		if (leaving <= 0) {
			pivot.standing(WALK_END_ANGLE, KNEEL_HEADING, WALK_END_ANGLE, FEET, FACING);
			prince.rig.pose("rise", frameAtProgress(rising, 22));
		} else {
			const airborne = smoothstep(0, 0.12, leaving) * (1 - smoothstep(0.9, 1, leaving));
			// A pendulum: he trails a little behind the flock and keeps swinging under it, even when the reader
			// stops scrolling. Two slow unrelated periods keep it from looking mechanical.
			const swing = airborne * (0.09 + Math.sin(moment.seconds * 1.5) * 0.05 + Math.sin(moment.seconds * 0.83 + 1) * 0.025);
			FEET.copy(PIVOT)
				.addScaledVector(CAMERA_RIGHT, -Math.sin(swing) * HANGING_LENGTH)
				.addScaledVector(UP, -Math.cos(swing) * HANGING_LENGTH);
			const heading = lerp(lerp(KNEEL_HEADING, FLIGHT_HEADING, smoothstep(0, 0.12, leaving)), SIT_HEADING, smoothstep(0.9, 1, leaving));
			FACING.setFromAxisAngle(CAMERA_AWAY, swing).multiply(TURN.setFromAxisAngle(UP, heading));
			prince.rig.pose("fly", moment.clock % 24);
		}
		prince.place(FEET, FACING);
	}

	/**
	 * Brings the journey's scenery on like stage machinery, just as he lifts away: planets are
	 * lowered from above and clouds are raised from below. Until then they wait out of sight.
	 * @param t Chapter position.
	 */
	private moveScenery(t: number): void {
		const arrived = smoothstep(0.02, 0.26, t) * (1 - smoothstep(1.04, 1.5, t));
		this.planets.forEach((planet, index) => {
			planet.position.y = (this.planetHomes[index] ?? 0) + (1 - arrived) * SCENERY_TRAVEL;
			planet.visible = arrived > 0;
		});
		this.sheets.forEach((sheet, index) => {
			sheet.position.y = (this.sheetHomes[index] ?? 0) - (1 - arrived) * SCENERY_TRAVEL;
			sheet.visible = arrived > 0;
		});
	}

	/**
	 * Hangs the flock from his hand once it has been posed.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	override afterPose(t: number, moment: Moment): void {
		if (t > -0.05 && t < 1.2) this.flyFlock(t, moment);
	}

	/**
	 * Builds one instanced flock mesh.
	 * @param source The bird mesh.
	 * @returns The instanced mesh.
	 */
	private flock(source: Mesh): InstancedMesh {
		const mesh = new InstancedMesh(source.geometry, source.material as Material, BIRDS);
		mesh.instanceMatrix.setUsage(DynamicDrawUsage);
		mesh.frustumCulled = false;
		this.stage.scene.add(mesh);
		return mesh;
	}

	/**
	 * Places the flock above his raised hand, flapping in stepped replacement frames.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	private flyFlock(t: number, moment: Moment): void {
		const { wings, threads, palm } = this;
		if (wings.length < 3 || !threads || !palm) return;
		palm.updateWorldMatrix(true, false);
		HAND.set(0, PALM_OFFSET, 0).applyMatrix4(palm.matrixWorld);
		const arrival = 1 - smoothstep(0, 0.1, t);
		const departure = smoothstep(1.02, 1.2, t);
		// Threads are tied at both ends at all times. They appear and leave by fading, never by stopping short.
		if (this.cord) this.cord.opacity = 0.8 * (1 - smoothstep(0.2, 0.7, arrival)) * (1 - progressIn(t, 0.99, 1.05));
		LEAD.copy(PIVOT).addScaledVector(UP, FLOCK_HEIGHT).addScaledVector(CAMERA_RIGHT, FLOCK_LEAD);
		LEAD.addScaledVector(CAMERA_RIGHT, -arrival * 9 + departure * 14).addScaledVector(UP, arrival * 6 + departure * 6);
		orientation.setFromAxisAngle(UP, Math.atan2(CAMERA_RIGHT.x, CAMERA_RIGHT.z));
		for (let i = 0; i < BIRDS; i++) {
			// A tight bunch, as balloons gather above the hand that holds them.
			const spread = 0.14 + 0.2 * Math.sqrt(i);
			const around = i * 2.39996;
			const shown = WING_CYCLE[(moment.pose + i * 3) % 4] ?? 0;
			const bob = Math.sin(moment.seconds * 2.2 + i * 1.7) * 0.04;
			position
				.copy(LEAD)
				.addScaledVector(CAMERA_RIGHT, Math.cos(around) * spread)
				.addScaledVector(CAMERA_AWAY, Math.sin(around) * spread * 0.7)
				.addScaledVector(UP, (0.5 - spread) * 0.42 + Math.sin(around * 1.7) * 0.07 + bob);
			scale.setScalar(0.19 + poseNoise(i, 36) * 0.04);
			matrix.compose(position, orientation, scale);
			wings.forEach((mesh, frame) => mesh.setMatrixAt(i, frame === shown ? matrix : hidden()));
			direction.copy(HAND).sub(position);
			const length = direction.length();
			threadTurn.setFromUnitVectors(UP, direction.negate().normalize());
			scale.set(0.003, length, 0.003);
			threads.setMatrixAt(i, matrix.compose(position, threadTurn, scale));
		}
		for (const mesh of wings) mesh.instanceMatrix.needsUpdate = true;
		threads.instanceMatrix.needsUpdate = true;
	}
}

const HIDDEN = new Matrix4().makeScale(0, 0, 0);

/**
 * A matrix that collapses an instance, for whichever replacement frame is off.
 * @returns The zero-scale matrix.
 */
function hidden(): Matrix4 {
	return HIDDEN;
}
