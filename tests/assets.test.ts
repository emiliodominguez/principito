import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import manifest from "#story/assets-manifest.json" with { type: "json" };
import { CHAPTERS } from "#story/chapters";

const TIERS = ["high", "medium", "low"];
const CHAPTER_FILES = ["UniverseChapter", "AsteroidChapter", "RoseChapter", "JourneyChapter", "FoxChapter", "FinaleChapter"];

/**
 * Reads a chapter's source.
 * @param name The chapter's file name.
 * @returns Its text.
 */
function source(name: string): string {
	return readFileSync(resolve("src/chapters", `${name}.ts`), "utf8");
}

describe("the contract between Blender and the story", () => {
	it("only asks puppets for clips that were exported", () => {
		const known = new Set([manifest.prince, manifest.fox, manifest.rose].flatMap((asset) => Object.keys(asset.clips)));
		const requested = CHAPTER_FILES.flatMap((name) => [...source(name).matchAll(/rig\.pose\("(\w+)"/g)].map((match) => match[1] ?? ""));
		expect(requested.length).toBeGreaterThan(10);
		for (const clip of requested) expect(known.has(clip), clip).toBe(true);
	});

	it("scrubs one-shot clips through exactly their real length", () => {
		const lengths: Record<string, number> = { ...manifest.prince.clips, ...manifest.fox.clips };
		for (const name of CHAPTER_FILES) {
			for (const match of source(name).matchAll(/rig\.pose\("(\w+)", frameAtProgress\([^;]*?, (\d+)\)\)/g)) {
				expect(Number(match[2]), `${name} ${match[1]}`).toBe(lengths[match[1] ?? ""]);
			}
		}
	});

	it("measures the bare ground the puppets stand on", () => {
		for (const profile of [manifest.asteroid.ground, manifest.fox_hill.ground]) {
			expect(profile.length).toBeGreaterThan(40);
			expect(profile.every(Number.isFinite)).toBe(true);
			const steps = profile.slice(1).map((value, index) => Math.abs(value - (profile[index] ?? 0)));
			expect(Math.max(...steps)).toBeLessThan(0.08);
		}
	});

	it("ships every model and painting a chapter declares, in every tier", () => {
		for (const tier of TIERS) {
			for (const asset of CHAPTERS.flatMap((chapter) => chapter.assets)) {
				const found =
					existsSync(resolve(`public/models/${tier}/${asset}.glb`)) || existsSync(resolve(`public/backgrounds/${tier}/${asset}.webp`));
				expect(found, `${tier}/${asset}`).toBe(true);
			}
		}
	});

	it("ships a still for every chapter in both aspect ratios", () => {
		for (const chapter of CHAPTERS) {
			for (const shape of ["wide", "tall"]) expect(existsSync(resolve(`public/fallback/${chapter.id}-${shape}.webp`)), chapter.id).toBe(true);
		}
	});
});
