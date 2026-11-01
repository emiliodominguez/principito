import { Vector3 } from "three";

import { lerp, progressIn } from "#story/timeline";

import type { AudioDirector } from "./AudioDirector";
import type { Viewport } from "./ResponsiveComposition";
import type { SceneManager } from "./SceneManager";

const point = new Vector3();

interface HotspotButton {
	readonly element: HTMLButtonElement;
	readonly chapterId: string;
	readonly from: number;
	readonly to: number;
	readonly id: string;
}

/**
 * Reader input. Pointer position feeds parallax, hanging stars respond to a nearby
 * pointer or tap, and hotspots are real buttons laid over the 3D set, which keeps
 * them keyboard-reachable and readable by screen readers.
 */
export class InteractionManager {
	private readonly pointer = { x: 0, y: 0, screenX: -1000, screenY: -1000 };
	private readonly eased = { x: 0, y: 0 };
	private readonly buttons: HotspotButton[] = [];
	private tapX = -1000;
	private tapY = -1000;
	private tapPending = false;

	constructor(
		root: HTMLElement,
		private readonly manager: SceneManager,
		private readonly audio: AudioDirector,
		private readonly parallax: boolean,
	) {
		window.addEventListener("pointermove", (event) => this.onPointer(event), { passive: true });
		window.addEventListener("pointerdown", (event) => this.onTap(event), { passive: true });
		const spans = manager.spans;
		for (const element of root.querySelectorAll<HTMLButtonElement>("[data-hotspot]")) {
			const [chapterId = "", id = ""] = (element.dataset["hotspot"] ?? "").split(".");
			const span = spans.find((candidate) => candidate.id === chapterId);
			if (!span) continue;
			const from = lerp(span.start, span.end, Number(element.dataset["from"]));
			const to = lerp(span.start, span.end, Number(element.dataset["to"]));
			this.buttons.push({ element, chapterId, from, to, id });
			element.addEventListener("click", () => {
				const chapter = [...manager.chapters.values()].find((candidate) => candidate.definition.id === chapterId);
				chapter?.activate(id, performance.now() / 1000);
				this.audio.chime(id === "stars" ? 1 : 0.6);
			});
		}
	}

	/**
	 * Advances the pointer's eased value.
	 * @returns The eased pointer position.
	 */
	ease(): { x: number; y: number } {
		this.eased.x += (this.pointer.x - this.eased.x) * 0.07;
		this.eased.y += (this.pointer.y - this.eased.y) * 0.07;
		return this.eased;
	}

	/**
	 * Applies interaction for this frame: star touches and hotspot positions.
	 * @param progress Story position.
	 * @param viewport The viewport.
	 * @param seconds Stage time.
	 */
	update(progress: number, viewport: Viewport, seconds: number): void {
		const camera = this.manager.camera.camera;
		camera.updateMatrixWorld();
		const stars = this.manager.stage()?.stars;
		if (stars) {
			for (const star of stars.stars) {
				point.set(star.x, star.y, star.z).project(camera);
				if (point.z > 1) continue;
				const x = (point.x * 0.5 + 0.5) * viewport.width;
				const y = (0.5 - point.y * 0.5) * viewport.height;
				const near = Math.hypot(x - this.pointer.screenX, y - this.pointer.screenY) < 34;
				const tapped = this.tapPending && Math.hypot(x - this.tapX, y - this.tapY) < 42;
				if (near || tapped) {
					const fresh = seconds - star.touched > 0.8;
					stars.touch(star, seconds, tapped ? 0.3 : 0.16);
					if (fresh && tapped) this.audio.chime(0.5 + star.size);
				}
			}
		}
		this.tapPending = false;
		for (const button of this.buttons) {
			const chapter = [...this.manager.chapters.values()].find((candidate) => candidate.definition.id === button.chapterId);
			const position = chapter?.hotspot(button.id);
			const shown = position !== undefined && progressIn(progress, button.from, button.from + 0.002) > 0 && progress < button.to;
			button.element.dataset["active"] = shown ? "true" : "false";
			button.element.tabIndex = shown ? 0 : -1;
			if (!shown || !position) continue;
			point.copy(position).project(camera);
			const x = (point.x * 0.5 + 0.5) * viewport.width;
			const y = (0.5 - point.y * 0.5) * viewport.height;
			button.element.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
		}
	}

	/**
	 * Tracks the pointer.
	 * @param event The pointer event.
	 */
	private onPointer(event: PointerEvent): void {
		this.pointer.screenX = event.clientX;
		this.pointer.screenY = event.clientY;
		if (!this.parallax || event.pointerType === "touch") return;
		this.pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
		this.pointer.y = (event.clientY / window.innerHeight) * 2 - 1;
	}

	/**
	 * Records a tap for the next frame, so stars can answer it.
	 * @param event The pointer event.
	 */
	private onTap(event: PointerEvent): void {
		this.tapX = event.clientX;
		this.tapY = event.clientY;
		this.tapPending = true;
	}
}
