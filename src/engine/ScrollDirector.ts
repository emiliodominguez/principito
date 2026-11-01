import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { clamp01 } from "#story/timeline";

gsap.registerPlugin(ScrollTrigger);

/**
 * Connects the page scroll to story progress.
 *
 * The page is one tall spacer. ScrollTrigger reports where the reader is, and the
 * value passes through a short scrub, so a trackpad flick feels weighted. Nothing is
 * accumulated: progress is always derived from scroll position, which is what lets
 * the story run in either direction without drift.
 */
export class ScrollDirector {
	private readonly state = { progress: 0 };
	private readonly trigger: ScrollTrigger;
	private readonly tween: gsap.core.Tween;
	private target = 0;

	constructor(track: HTMLElement, reduced: boolean) {
		this.tween = gsap.to(this.state, {
			progress: 1,
			ease: "none",
			scrollTrigger: {
				trigger: track,
				start: "top top",
				end: "bottom bottom",
				scrub: reduced ? true : 0.55,
				onUpdate: (self) => {
					this.target = self.progress;
				},
			},
		});
		const trigger = this.tween.scrollTrigger;
		if (!trigger) throw new Error("scroll trigger was not created");
		this.trigger = trigger;
	}

	/**
	 * Current scrubbed story position.
	 * @returns Progress, 0 to 1.
	 */
	get progress(): number {
		return this.state.progress;
	}

	/**
	 * The unsmoothed position the scrub is heading to.
	 * @returns Progress, 0 to 1.
	 */
	get destination(): number {
		return this.target;
	}

	/**
	 * Scrolls the page to a story position.
	 * @param progress Story position, 0 to 1.
	 * @param instant Skip the glide.
	 */
	seek(progress: number, instant = false): void {
		const y = this.trigger.start + (this.trigger.end - this.trigger.start) * clamp01(progress);
		window.scrollTo({ top: y, behavior: instant ? "auto" : "smooth" });
		if (instant) {
			this.state.progress = clamp01(progress);
			this.target = this.state.progress;
		}
	}

	/** Recomputes scroll distances after a layout change. */
	refresh(): void {
		ScrollTrigger.refresh();
	}

	/** Detaches from the page. */
	dispose(): void {
		this.tween.kill();
		this.trigger.kill();
	}
}
