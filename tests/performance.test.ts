import { describe, expect, it, vi } from "vitest";

import { classifyDevice, PerformanceManager, settingsFor } from "#engine/PerformanceManager";

/**
 * Feeds frames of a fixed length.
 * @param manager The manager.
 * @param count How many frames.
 * @param milliseconds Frame length.
 * @param start Starting timestamp.
 * @returns The final timestamp.
 */
function feed(manager: PerformanceManager, count: number, milliseconds: number, start = 0): number {
	let now = start;
	for (let i = 0; i < count; i++) {
		now += milliseconds;
		manager.frame(now);
	}
	return now;
}

const base = { renderer: "Apple M1 Pro", maxTextureSize: 16384, deviceMemory: 8, cores: 8, coarsePointer: false };

describe("device tiers", () => {
	it("trusts a capable desktop GPU", () => {
		expect(classifyDevice(base)).toBe("high");
	});

	it("starts touch devices on the middle tier", () => {
		expect(classifyDevice({ ...base, renderer: "Apple GPU", coarsePointer: true })).toBe("medium");
	});

	it("sends software renderers and small devices to the lowest tier", () => {
		expect(classifyDevice({ ...base, renderer: "Google SwiftShader" })).toBe("low");
		expect(classifyDevice({ ...base, deviceMemory: 2 })).toBe("low");
		expect(classifyDevice({ ...base, maxTextureSize: 2048 })).toBe("low");
	});

	it("reduces cost monotonically from tier to tier", () => {
		const [high, medium, low] = [settingsFor("high"), settingsFor("medium"), settingsFor("low")];
		expect(high.shadowSize).toBeGreaterThan(medium.shadowSize);
		expect(medium.shadowSize).toBeGreaterThan(low.shadowSize);
		expect(high.fieldStars).toBeGreaterThan(medium.fieldStars);
		expect(medium.fieldStars).toBeGreaterThan(low.fieldStars);
	});
});

describe("adaptive resolution", () => {
	it("lowers resolution when frames run long", () => {
		const manager = new PerformanceManager();
		const listener = vi.fn();
		manager.onChange(listener);
		feed(manager, 120, 40);
		expect(listener).toHaveBeenCalled();
		expect(manager.stats().scale).toBeLessThan(1);
	});

	it("restores resolution once frames are fast again", () => {
		const manager = new PerformanceManager();
		const now = feed(manager, 120, 40);
		const dropped = manager.stats().scale;
		feed(manager, 800, 11, now);
		expect(manager.stats().scale).toBeGreaterThan(dropped);
	});

	it("does not react to a single stall", () => {
		const manager = new PerformanceManager();
		let now = feed(manager, 120, 16);
		now += 200;
		manager.frame(now);
		feed(manager, 120, 16, now);
		expect(manager.stats().scale).toBe(1);
	});

	it("ignores long gaps, which mean the page was idle rather than slow", () => {
		const manager = new PerformanceManager();
		feed(manager, 100, 1000);
		expect(manager.stats().scale).toBe(1);
	});
});
