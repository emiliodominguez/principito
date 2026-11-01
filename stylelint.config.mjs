const kebabCase = "^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$";

export default {
	extends: ["stylelint-config-standard-scss"],
	customSyntax: "postcss-scss",
	ignoreFiles: ["**/node_modules/**", "dist/**", ".astro/**"],
	rules: {
		"selector-class-pattern": kebabCase,
		"selector-pseudo-class-no-unknown": [true, { ignorePseudoClasses: ["global"] }],
		"custom-property-pattern": kebabCase,
		"keyframes-name-pattern": kebabCase,
		"scss/dollar-variable-pattern": kebabCase,
		"at-rule-disallowed-list": ["import"],
		"property-disallowed-list": ["background"],
		"declaration-no-important": true,
		"color-named": "never",
		"media-feature-range-notation": null,
		"no-descending-specificity": null,
		"value-keyword-case": ["lower", { ignoreKeywords: ["optimizeLegibility"], ignoreProperties: ["font-family"] }],
	},
};
