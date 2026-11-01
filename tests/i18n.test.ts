import { describe, expect, it } from "vitest";

import { en } from "#i18n/en";
import { es } from "#i18n/es";
import { format } from "#i18n/index";
import { CHAPTERS } from "#story/chapters";

/**
 * Lists every string path in a catalogue.
 * @param value The catalogue node.
 * @param prefix Path so far.
 * @returns The sorted paths.
 */
function paths(value: unknown, prefix = ""): string[] {
	if (typeof value === "string") return [prefix];
	return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => paths(child, prefix ? `${prefix}.${key}` : key));
}

describe("catalogues", () => {
	it("have identical shapes", () => {
		expect(paths(es).toSorted()).toEqual(paths(en).toSorted());
	});

	it("cover every beat and hotspot in the story", () => {
		for (const chapter of CHAPTERS) {
			for (const catalogue of [en, es]) {
				const beats = catalogue.chapters[chapter.id].beats as Readonly<Record<string, string>>;
				for (const beat of chapter.beats) expect(beats[beat.id], `${chapter.id}.${beat.id}`).toBeTruthy();
				for (const hotspot of chapter.hotspots) expect(hotspot.id in catalogue.hotspots).toBe(true);
			}
		}
	});

	it("keep narration short: an original telling, not a reproduction of the book", () => {
		for (const chapter of CHAPTERS) {
			for (const line of Object.values(en.chapters[chapter.id].beats)) expect(line.length).toBeLessThan(100);
		}
	});

	it("fill placeholders", () => {
		expect(format(en.ui.chapterLabel, { number: 2, title: "The rose" })).toBe("Chapter 2: The rose");
	});
});
