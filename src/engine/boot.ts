import { StoryApp } from "./StoryApp";

/**
 * Starts film mode. If WebGL fails at any point, the reader drops back to the
 * illustrated book, which is already fully present in the document.
 * @returns When the opening is on screen.
 */
export async function boot(): Promise<void> {
	const root = document.documentElement;
	const canvas = document.querySelector<HTMLCanvasElement>("[data-canvas]");
	const probe = document.querySelector<HTMLElement>("[data-safe-area]");
	const track = document.querySelector<HTMLElement>("[data-track]");
	const loader = document.querySelector<HTMLElement>("[data-loader]");
	const meter = document.querySelector<HTMLElement>("[data-loader-meter]");
	if (!canvas || !probe || !track) return;
	try {
		const app = new StoryApp(root, canvas, probe, track);
		await app.start((share) => {
			meter?.style.setProperty("--loaded", String(share));
		});
		root.dataset["stage"] = "ready";
		loader?.setAttribute("aria-hidden", "true");
	} catch (error: unknown) {
		console.error("story.boot_failed", error);
		root.dataset["mode"] = "book";
		root.dataset["capable"] = "no";
	}
}
