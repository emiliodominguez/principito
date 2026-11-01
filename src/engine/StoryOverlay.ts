import { lerp, progressIn, smoothstep } from "#story/timeline";
import type { Beat, ChapterDefinition, ChapterSpan } from "#story/types";

/** How much of a beat's span is spent fading, as a share of its length. */
const FADE = 0.2;

interface BeatElement {
	readonly element: HTMLElement;
	readonly from: number;
	readonly to: number;
	readonly fade: number;
	shown: number;
}

/**
 * Applies story position to the DOM: narration and chapter navigation.
 */
export class StoryOverlay {
	private readonly beats: BeatElement[] = [];
	private readonly links: readonly HTMLElement[];
	private current = -1;

	constructor(root: HTMLElement, chapters: readonly ChapterDefinition[], spans: readonly ChapterSpan[]) {
		chapters.forEach((chapter, index) => {
			const span = spans[index];
			if (!span) return;
			for (const beat of chapter.beats as readonly Beat[]) {
				const element = root.querySelector<HTMLElement>(`[data-beat="${chapter.id}.${beat.id}"]`);
				if (!element) continue;
				const from = lerp(span.start, span.end, beat.from);
				const to = lerp(span.start, span.end, beat.to);
				this.beats.push({ element, from, to, fade: (to - from) * FADE, shown: -1 });
			}
		});
		this.links = [...root.querySelectorAll<HTMLElement>("[data-chapter-link]")];
	}

	/**
	 * Updates narration and navigation.
	 * @param progress Story position.
	 * @param chapterIndex Index of the chapter on stage.
	 */
	update(progress: number, chapterIndex: number): void {
		for (const beat of this.beats) {
			const opening = progressIn(progress, beat.from, beat.from + beat.fade);
			const closing = 1 - progressIn(progress, beat.to - beat.fade, beat.to);
			const eased = smoothstep(0, 1, Math.min(opening, closing));
			const visible = Math.round(eased * 100) / 100;
			if (visible === beat.shown) continue;
			beat.shown = visible;
			beat.element.style.setProperty("--beat-reveal", String(visible));
			beat.element.dataset["active"] = visible > 0 ? "true" : "false";
		}
		if (chapterIndex !== this.current) {
			this.current = chapterIndex;
			this.links.forEach((link, index) => {
				if (index === chapterIndex) link.setAttribute("aria-current", "step");
				else link.removeAttribute("aria-current");
			});
		}
	}
}
