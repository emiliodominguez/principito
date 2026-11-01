export type Tier = "high" | "medium" | "low";

/** Everything that varies between performance tiers. */
export interface TierSettings {
	readonly tier: Tier;
	readonly maxPixelRatio: number;
	/** Drawing-buffer budget: a very large screen gets a softer buffer, not a slower film. */
	readonly maxPixels: number;
	readonly samples: number;
	readonly shadowSize: number;
	readonly depthOfField: number;
	readonly hangingStars: number;
	readonly fieldStars: number;
	readonly parallax: boolean;
}

const SETTINGS: Readonly<Record<Tier, TierSettings>> = {
	high: {
		tier: "high",
		maxPixelRatio: 2,
		maxPixels: 4_200_000,
		samples: 2,
		shadowSize: 2048,
		depthOfField: 20,
		hangingStars: 64,
		fieldStars: 460,
		parallax: true,
	},
	medium: {
		tier: "medium",
		maxPixelRatio: 1.75,
		maxPixels: 2_400_000,
		samples: 0,
		shadowSize: 1024,
		depthOfField: 14,
		hangingStars: 40,
		fieldStars: 300,
		parallax: true,
	},
	low: {
		tier: "low",
		maxPixelRatio: 1.25,
		maxPixels: 1_200_000,
		samples: 0,
		shadowSize: 0,
		depthOfField: 0,
		hangingStars: 22,
		fieldStars: 140,
		parallax: false,
	},
};

/** Minimal device hints, separated out so detection stays testable without a browser. */
export interface DeviceHints {
	readonly renderer: string;
	readonly maxTextureSize: number;
	readonly deviceMemory: number | undefined;
	readonly cores: number;
	readonly coarsePointer: boolean;
}

/**
 * Chooses a starting tier from what the device says about itself.
 * @param hints Device capability hints.
 * @returns The tier.
 */
export function classifyDevice(hints: DeviceHints): Tier {
	const name = hints.renderer.toLowerCase();
	if (/swiftshader|llvmpipe|software|basic render/.test(name)) return "low";
	if (hints.maxTextureSize < 4096 || (hints.deviceMemory ?? 8) < 3 || hints.cores < 4) return "low";
	if (hints.coarsePointer) return "medium";
	if (/intel.*(hd|uhd) graphics/.test(name) || (hints.deviceMemory ?? 8) < 6) return "medium";
	return "high";
}

/**
 * Looks up a tier's settings.
 * @param tier The tier.
 * @returns Its settings.
 */
export function settingsFor(tier: Tier): TierSettings {
	return SETTINGS[tier];
}

/** Frames in the rolling window. */
const WINDOW = 90;

/** Rolling frame timing; lowers resolution when frames run long and restores it gently. */
export class PerformanceManager {
	private readonly samples: number[] = [];
	private scale = 1;
	private cooldown = 0;
	private last = 0;
	private readonly changeListeners = new Set<(scale: number) => void>();
	private droppedTo: number | undefined;

	/**
	 * Registers a resolution-change listener.
	 * @param listener Receives a 0.5 to 1 render scale.
	 */
	onChange(listener: (scale: number) => void): void {
		this.changeListeners.add(listener);
	}

	/**
	 * Records a rendered frame. Resolution follows the median frame, so one stall while
	 * something loads never changes it: only sustained slowness does.
	 * @param now Timestamp in milliseconds.
	 */
	frame(now: number): void {
		const delta = now - this.last;
		this.last = now;
		// A long gap means the tab slept or nothing needed drawing, which says nothing about the GPU.
		if (delta <= 0 || delta > 250) return;
		this.samples.push(delta);
		if (this.samples.length > WINDOW) this.samples.shift();
		if (this.cooldown > 0) {
			this.cooldown--;
			return;
		}
		if (this.samples.length < WINDOW) return;
		const median = this.samples.toSorted((x, y) => x - y)[Math.floor(WINDOW / 2)] ?? 0;
		if (median > 26 && this.scale > 0.6) {
			this.apply(Math.max(0.6, this.scale * 0.85));
		} else if (median < 14 && this.scale < 1) {
			this.apply(Math.min(1, this.scale * 1.1));
		}
	}

	/**
	 * Reports recent timing for the debug overlay and tests.
	 * @returns Average frame milliseconds and render scale.
	 */
	stats(): { averageMs: number; scale: number } {
		const averageMs = this.samples.reduce((sum, value) => sum + value, 0) / Math.max(1, this.samples.length);
		return { averageMs, scale: this.scale };
	}

	/**
	 * Applies a new render scale and waits for the change to take effect before judging again.
	 * @param scale New render scale.
	 */
	private apply(scale: number): void {
		this.scale = scale;
		this.droppedTo = scale;
		this.cooldown = 240;
		this.samples.length = 0;
		for (const listener of this.changeListeners) listener(this.droppedTo);
	}
}
