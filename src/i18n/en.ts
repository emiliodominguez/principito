/** English is the source catalogue; other locales must match its shape exactly. */
export const en = {
	meta: {
		lang: "en",
		title: "The Little Prince: a paper storybook",
		description: "An interactive stop-motion storybook inspired by The Little Prince, made of paper and soft light. Scroll to read.",
	},
	ui: {
		skipToStory: "Skip to the story",
		chapters: "Chapters",
		chapterLabel: "Chapter {number}: {title}",
		loading: "Setting the stage",
		loadingChapter: "Bringing in the next set",
		scrollHint: "Scroll to begin",
		soundOn: "Turn sound on",
		soundOff: "Turn sound off",
		bookMode: "Read as a book",
		filmMode: "Watch as a film",
		language: "Español",
		languageLabel: "Leer en español",
		fallbackNotice: "This device is showing the illustrated edition.",
		colophon: "An homage to Antoine de Saint-Exupéry.",
		restart: "Back to the beginning",
	},
	hotspots: {
		rose: "Touch the rose",
		stars: "Ring the stars",
	},
	chapters: {
		universe: {
			title: "The universe",
			alt: "A paper puppet of a golden-haired boy in a green coat points at a gold star, his yellow scarf streaming behind him.",
			beats: {
				opening: "All grown-ups were once children…",
				remember: "Only a few of them remember.",
			},
		},
		planet: {
			title: "The tiny planet",
			alt: "The boy stands on a tiny clay planet with small volcanoes, a chair and a rose under glass.",
			beats: {
				small: "His whole world was small enough to cross before dinner.",
				chores: "Three volcanoes to sweep. One chair to move, whenever he wanted another sunset.",
			},
		},
		rose: {
			title: "The rose",
			alt: "The boy kneels beside a single red rose under a glass dome.",
			beats: {
				arrival: "One morning, something opened that he had not planted.",
				care: "She was only a rose. He gave her a glass dome against the cold, and all of his evenings.",
				yours: "Nobody had told him that looking after something is how it becomes yours.",
			},
		},
		journey: {
			title: "The journey",
			alt: "Holding the threads of a flock of paper birds, the boy drifts between suspended paper planets.",
			beats: {
				leave: "But a small world can hold a very large question.",
				wind: "So he took hold of the wind, and let go of home.",
				planets: "He passed a hundred paper planets, each one busy with itself.",
			},
		},
		fox: {
			title: "The fox",
			alt: "On a quiet golden hill, the boy sits and holds out his hand to a clay fox.",
			beats: {
				waiting: "On a quiet hill, someone was waiting to be asked.",
				closer: "Not too close. Only a little nearer, every day.",
				silence: "Then, for a long while, nobody said anything at all.",
			},
		},
		finale: {
			title: "What matters",
			alt: "The boy looks up from far away as gold paper stars fill the sky.",
			beats: {
				distance: "It was never the size of the world.",
				unseen: "What matters most is the part you cannot see.",
				look: "Look up tonight.",
			},
		},
	},
} as const;

/** Replaces string literal types with `string`, keeping the catalogue's shape. */
type Widen<T> = { readonly [K in keyof T]: T[K] extends string ? string : Widen<T[K]> };

export type Catalogue = Widen<typeof en>;
