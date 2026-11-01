import { type Catalogue, en } from "./en";
import { es } from "./es";

export type Locale = "en" | "es";

const catalogues: Record<Locale, Catalogue> = { en, es };

/**
 * Returns the catalogue for a locale.
 * @param locale The locale.
 * @returns Its strings.
 */
export function catalogueFor(locale: Locale): Catalogue {
	return catalogues[locale];
}

/**
 * Fills {placeholders} in a catalogue string.
 * @param template The string.
 * @param values Replacement values.
 * @returns The formatted string.
 */
export function format(template: string, values: Readonly<Record<string, string | number>>): string {
	return template.replaceAll(/\{(\w+)\}/g, (match, key: string) => String(values[key] ?? match));
}
