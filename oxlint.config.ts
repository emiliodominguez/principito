import { defineConfig } from "oxlint";

export default defineConfig({
	plugins: ["typescript", "import", "oxc", "unicorn"],
	ignorePatterns: ["**/node_modules/**", "dist/**", ".astro/**", "public/**", "blender/**"],
	categories: { correctness: "error", suspicious: "error", perf: "error" },
	rules: {
		"func-style": ["error", "declaration", { allowArrowFunctions: true }],
		eqeqeq: ["error", "always"],
		"no-var": "error",
		"prefer-const": "error",
		"no-unused-vars": "error",
		"typescript/consistent-type-imports": "error",
		"typescript/no-explicit-any": "error",
		"typescript/no-non-null-assertion": "error",
		"unicorn/prefer-node-protocol": "error",
	},
	overrides: [
		{
			// The render path allocates nothing per frame, so it deliberately reuses module-level scratch objects.
			files: ["src/engine/**", "src/chapters/**"],
			rules: { "oxc/no-map-spread": "off", "unicorn/no-array-sort": "off", "no-await-in-loop": "off" },
		},
		{
			// Stylesheets are side-effect imports by nature.
			files: ["**/*.astro"],
			rules: { "import/no-unassigned-import": "off" },
		},
		{
			files: ["scripts/**"],
			rules: { "no-console": "off", "no-await-in-loop": "off" },
		},
	],
});
