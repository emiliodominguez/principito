/**
 * Reads a regularly spaced profile with linear interpolation.
 * @param samples The profile.
 * @param start Coordinate of the first sample.
 * @param step Spacing.
 * @param at Coordinate to read.
 * @returns The interpolated value.
 */
export function readProfile(samples: readonly number[], start: number, step: number, at: number): number {
	const position = Math.min(samples.length - 1.001, Math.max(0, (at - start) / step));
	const index = Math.floor(position);
	const a = samples[index] ?? 0;
	const b = samples[index + 1] ?? a;
	return a + (b - a) * (position - index);
}
