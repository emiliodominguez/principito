import type { ChapterDefinition, ChapterSpan } from "./types";

/**
 * Limits a value to the range 0 to 1.
 * @param value The input.
 * @returns The clamped value.
 */
export function clamp01(value: number): number {
	return Math.min(1, Math.max(0, value));
}

/**
 * Linear interpolation.
 * @param a Start.
 * @param b End.
 * @param t Position.
 * @returns The interpolated value.
 */
export function lerp(a: number, b: number, t: number): number {
	return a + (b - a) * t;
}

/**
 * Position of a value within a range, clamped to 0 to 1.
 * @param value The input.
 * @param from Range start.
 * @param to Range end.
 * @returns Normalized progress through the range.
 */
export function progressIn(value: number, from: number, to: number): number {
	return to === from ? (value >= to ? 1 : 0) : clamp01((value - from) / (to - from));
}

/**
 * Hermite smoothstep over a range.
 * @param from Range start.
 * @param to Range end.
 * @param value The input.
 * @returns A smooth 0 to 1 ramp.
 */
export function smoothstep(from: number, to: number, value: number): number {
	const t = progressIn(value, from, to);
	return t * t * (3 - 2 * t);
}

/**
 * Lays chapters end to end on a 0 to 1 story timeline, proportional to their scroll length.
 * @param chapters The chapter definitions in reading order.
 * @returns Each chapter's span.
 */
export function layoutChapters(chapters: readonly ChapterDefinition[]): ChapterSpan[] {
	const total = chapters.reduce((sum, chapter) => sum + chapter.length, 0);
	let cursor = 0;
	return chapters.map((chapter, index) => {
		const start = cursor / total;
		cursor += chapter.length;
		return { id: chapter.id, index, start, end: cursor / total };
	});
}

/**
 * Finds the chapter that owns a story position. Positions on a boundary belong to the later chapter.
 * @param spans The chapter layout.
 * @param progress Story position.
 * @returns The owning span.
 */
export function spanAt(spans: readonly ChapterSpan[], progress: number): ChapterSpan {
	const found = spans.find((span) => progress < span.end);
	const last = spans.at(-1);
	if (found) return found;
	if (!last) throw new RangeError("story has no chapters");
	return last;
}

/** A smooth curve through keyed vectors, evaluated with no overshoot between keys. */
export interface VectorTrack {
	readonly size: number;
	/**
	 * Evaluates the curve.
	 * @param t Position along the keys.
	 * @param out Destination array.
	 * @returns The destination.
	 */
	sample(t: number, out: Float64Array): Float64Array;
}

/**
 * Computes Fritsch-Carlson slopes, which keep a cubic from overshooting its keys.
 * The camera therefore settles on a shot instead of drifting past it and returning.
 * @param times Strictly increasing key times.
 * @param values One value per key.
 * @returns One slope per key.
 */
function monotoneSlopes(times: readonly number[], values: readonly number[]): number[] {
	const count = times.length;
	const secants: number[] = [];
	for (let i = 0; i < count - 1; i++) {
		secants.push(((values[i + 1] ?? 0) - (values[i] ?? 0)) / ((times[i + 1] ?? 0) - (times[i] ?? 0)));
	}
	// The first and last keys are at rest: the film eases in, and never stops dead at the end of the scroll.
	const slopes: number[] = [0];
	for (let i = 1; i < count - 1; i++) {
		const before = secants[i - 1] ?? 0;
		const after = secants[i] ?? 0;
		slopes.push(before * after <= 0 ? 0 : (before + after) / 2);
	}
	slopes.push(0);
	for (let i = 0; i < count - 1; i++) {
		const secant = secants[i] ?? 0;
		if (secant === 0) {
			slopes[i] = 0;
			slopes[i + 1] = 0;
			continue;
		}
		const a = (slopes[i] ?? 0) / secant;
		const b = (slopes[i + 1] ?? 0) / secant;
		const length = Math.hypot(a, b);
		if (length > 3) {
			slopes[i] = (3 * a * secant) / length;
			slopes[i + 1] = (3 * b * secant) / length;
		}
	}
	return slopes;
}

/**
 * Builds a monotone cubic track through keyed vectors.
 * @param times Strictly increasing key times.
 * @param vectors One equally long vector per key.
 * @returns The track.
 */
export function createTrack(times: readonly number[], vectors: readonly (readonly number[])[]): VectorTrack {
	const size = vectors[0]?.length ?? 0;
	const channels: number[][] = [];
	for (let channel = 0; channel < size; channel++) {
		channels.push(
			monotoneSlopes(
				times,
				vectors.map((vector) => vector[channel] ?? 0),
			),
		);
	}
	const lastIndex = times.length - 1;

	function sample(t: number, out: Float64Array): Float64Array {
		let index = 0;
		while (index < lastIndex - 1 && t >= (times[index + 1] ?? 0)) index++;
		const start = times[index] ?? 0;
		const end = times[Math.min(index + 1, lastIndex)] ?? start;
		const width = end - start;
		const u = width > 0 ? clamp01((t - start) / width) : 0;
		const u2 = u * u;
		const u3 = u2 * u;
		const a = vectors[index];
		const b = vectors[Math.min(index + 1, lastIndex)];
		for (let channel = 0; channel < size; channel++) {
			const slopes = channels[channel];
			const p0 = a?.[channel] ?? 0;
			const p1 = b?.[channel] ?? 0;
			const m0 = (slopes?.[index] ?? 0) * width;
			const m1 = (slopes?.[Math.min(index + 1, lastIndex)] ?? 0) * width;
			out[channel] = (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1;
		}
		return out;
	}

	return { size, sample };
}
