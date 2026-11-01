import type { Catalogue } from "./en";

export const es: Catalogue = {
	meta: {
		lang: "es",
		title: "El Principito: un libro de papel",
		description: "Un cuento interactivo en stop-motion inspirado en El Principito, hecho de papel y luz suave. Desplazate para leer.",
	},
	ui: {
		skipToStory: "Saltar al cuento",
		chapters: "Capítulos",
		chapterLabel: "Capítulo {number}: {title}",
		loading: "Preparando el escenario",
		loadingChapter: "Trayendo el próximo decorado",
		scrollHint: "Desplazate para empezar",
		soundOn: "Activar el sonido",
		soundOff: "Silenciar el sonido",
		bookMode: "Leer como libro",
		filmMode: "Ver como película",
		language: "English",
		languageLabel: "Read in English",
		fallbackNotice: "Este dispositivo muestra la edición ilustrada.",
		colophon: "Un homenaje a Antoine de Saint-Exupéry.",
		restart: "Volver al principio",
	},
	hotspots: {
		rose: "Tocar la rosa",
		stars: "Hacer sonar las estrellas",
	},
	chapters: {
		universe: {
			title: "El universo",
			alt: "Un títere de papel, un niño de pelo dorado y abrigo verde, señala una estrella dorada con su bufanda amarilla al viento.",
			beats: {
				opening: "Todos los grandes fueron niños alguna vez…",
				remember: "Solo unos pocos lo recuerdan.",
			},
		},
		planet: {
			title: "El planeta diminuto",
			alt: "El niño está de pie sobre un planeta diminuto de arcilla, con volcanes pequeños, una silla y una rosa bajo vidrio.",
			beats: {
				small: "Su mundo entero era tan chico que podía cruzarlo antes de la cena.",
				chores: "Tres volcanes para deshollinar. Una silla para mover, cada vez que quería otro atardecer.",
			},
		},
		rose: {
			title: "La rosa",
			alt: "El niño se arrodilla junto a una rosa roja bajo una campana de vidrio.",
			beats: {
				arrival: "Una mañana, se abrió algo que él no había plantado.",
				care: "Era solo una rosa. Le dio una campana de vidrio contra el frío y todas sus tardes.",
				yours: "Nadie le había dicho que cuidar algo es la forma en que se vuelve tuyo.",
			},
		},
		journey: {
			title: "El viaje",
			alt: "Sosteniendo los hilos de una bandada de pájaros de papel, el niño flota entre planetas de papel suspendidos.",
			beats: {
				leave: "Pero un mundo pequeño puede guardar una pregunta muy grande.",
				wind: "Así que se agarró del viento y soltó su casa.",
				planets: "Pasó junto a cien planetas de papel, cada uno ocupado consigo mismo.",
			},
		},
		fox: {
			title: "El zorro",
			alt: "En una colina dorada y tranquila, el niño se sienta y le tiende la mano a un zorro de arcilla.",
			beats: {
				waiting: "En una colina tranquila, alguien esperaba que le preguntaran.",
				closer: "No tan cerca. Solo un poquito más, cada día.",
				silence: "Después, durante un largo rato, nadie dijo nada.",
			},
		},
		finale: {
			title: "Lo que importa",
			alt: "El niño mira hacia arriba desde muy lejos mientras las estrellas de papel dorado llenan el cielo.",
			beats: {
				distance: "Nunca fue el tamaño del mundo.",
				unseen: "Lo que más importa es lo que no se puede ver.",
				look: "Mirá para arriba esta noche.",
			},
		},
	},
};
