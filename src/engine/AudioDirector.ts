import type { ChapterId } from "#story/types";

/** Relative loudness of each layer per chapter: wind, music, paper. */
const MIX: Readonly<Record<ChapterId, readonly [number, number, number]>> = {
	universe: [0.5, 0.5, 0.2],
	planet: [0.6, 0.55, 0.2],
	rose: [0.28, 0.75, 0.12],
	journey: [0.9, 0.5, 0.75],
	fox: [0.5, 0.35, 0.2],
	finale: [0.3, 0.9, 0.1],
};

/** A pentatonic set around A: consonant in any order, which suits music that never resolves. */
const SCALE = [220, 246.94, 277.18, 329.63, 369.99, 440, 493.88, 554.37, 659.25];

/**
 * The ambient score, synthesized in the browser, so there are no audio files and
 * nothing to license. It stays silent until the reader asks for it, which also
 * satisfies browser autoplay rules: the context only starts inside a click.
 */
export class AudioDirector {
	private context: AudioContext | undefined;
	private master: GainNode | undefined;
	private wind: GainNode | undefined;
	private music: GainNode | undefined;
	private paper: GainNode | undefined;
	private enabled = false;
	private chapter: ChapterId = "universe";
	private timer = 0;
	private step = 0;

	/**
	 * Turns the score on or off.
	 * @returns Whether sound is now on.
	 */
	toggle(): boolean {
		this.enabled = !this.enabled;
		if (this.enabled) {
			this.ensureGraph();
			void this.context?.resume();
			this.fadeMaster(0.7, 1.4);
			this.applyMix();
			this.timer = window.setInterval(() => this.nextNote(), 2600);
		} else {
			this.fadeMaster(0, 0.4);
			window.clearInterval(this.timer);
		}
		return this.enabled;
	}

	/**
	 * Crossfades to a chapter's mix.
	 * @param chapter The chapter on stage.
	 */
	setChapter(chapter: ChapterId): void {
		if (chapter === this.chapter) return;
		this.chapter = chapter;
		if (this.enabled) this.applyMix();
	}

	/**
	 * Rings a small star-like chime.
	 * @param strength Loudness, about 0 to 1.
	 */
	chime(strength: number): void {
		if (!this.enabled || !this.context || !this.master) return;
		const pitch = SCALE[Math.floor(Math.random() * SCALE.length)] ?? 440;
		this.bell(pitch * 4, 0.05 * Math.min(1, strength), 2.8, this.master);
	}

	/** Builds the audio graph the first time sound is requested. */
	private ensureGraph(): void {
		if (this.context) return;
		const context = new AudioContext();
		this.context = context;
		const master = context.createGain();
		master.gain.value = 0;
		master.connect(context.destination);
		this.master = master;

		const noise = this.noiseSource(context);
		const windFilter = context.createBiquadFilter();
		windFilter.type = "bandpass";
		windFilter.frequency.value = 340;
		windFilter.Q.value = 0.7;
		const sweep = context.createOscillator();
		sweep.frequency.value = 0.07;
		const sweepDepth = context.createGain();
		sweepDepth.gain.value = 170;
		sweep.connect(sweepDepth).connect(windFilter.frequency);
		sweep.start();
		this.wind = context.createGain();
		noise.connect(windFilter).connect(this.wind).connect(master);

		const rustle = context.createBiquadFilter();
		rustle.type = "highpass";
		rustle.frequency.value = 3200;
		this.paper = context.createGain();
		const flutter = context.createOscillator();
		flutter.type = "sawtooth";
		flutter.frequency.value = 5.3;
		const flutterDepth = context.createGain();
		flutterDepth.gain.value = 0.022;
		const paperLevel = context.createGain();
		paperLevel.gain.value = 0.022;
		flutter.connect(flutterDepth).connect(paperLevel.gain);
		flutter.start();
		noise.connect(rustle).connect(paperLevel).connect(this.paper).connect(master);

		this.music = context.createGain();
		const delay = context.createDelay(2);
		delay.delayTime.value = 0.61;
		const feedback = context.createGain();
		feedback.gain.value = 0.42;
		this.music.connect(master);
		this.music.connect(delay).connect(feedback).connect(delay);
		delay.connect(master);
		noise.start();
	}

	/**
	 * Creates a looping noise source shared by wind and paper.
	 * @param context The audio context.
	 * @returns The source node.
	 */
	private noiseSource(context: AudioContext): AudioBufferSourceNode {
		const length = context.sampleRate * 4;
		const buffer = context.createBuffer(1, length, context.sampleRate);
		const data = buffer.getChannelData(0);
		let brown = 0;
		for (let i = 0; i < length; i++) {
			brown = (brown + (Math.random() * 2 - 1) * 0.04) * 0.985;
			data[i] = brown * 2.4 + (Math.random() * 2 - 1) * 0.04;
		}
		const source = context.createBufferSource();
		source.buffer = buffer;
		source.loop = true;
		return source;
	}

	/** Plays one sparse note of the score. */
	private nextNote(): void {
		if (!this.context || !this.music) return;
		this.step += 1 + Math.floor(Math.random() * 3);
		const pitch = SCALE[(this.step * 3) % SCALE.length] ?? 220;
		this.bell(pitch, 0.07, 5, this.music);
		if (this.step % 4 === 0) this.bell((SCALE[this.step % 3] ?? 220) / 2, 0.05, 7, this.music);
	}

	/**
	 * Strikes a soft bell: two inharmonic partials with a slow decay.
	 * @param frequency Fundamental in hertz.
	 * @param level Peak gain.
	 * @param decay Seconds to fade.
	 * @param output Destination.
	 */
	private bell(frequency: number, level: number, decay: number, output: AudioNode): void {
		const context = this.context;
		if (!context) return;
		const now = context.currentTime;
		for (const [ratio, weight] of [
			[1, 1],
			[2.76, 0.28],
		] as const) {
			const oscillator = context.createOscillator();
			oscillator.frequency.value = frequency * ratio;
			const gain = context.createGain();
			gain.gain.setValueAtTime(0, now);
			gain.gain.linearRampToValueAtTime(level * weight, now + 0.015);
			gain.gain.exponentialRampToValueAtTime(0.0001, now + decay / ratio);
			oscillator.connect(gain).connect(output);
			oscillator.start(now);
			oscillator.stop(now + decay / ratio + 0.1);
		}
	}

	/**
	 * Fades the master level.
	 * @param level Target level.
	 * @param seconds Fade time.
	 */
	private fadeMaster(level: number, seconds: number): void {
		if (!this.master || !this.context) return;
		this.master.gain.setTargetAtTime(level, this.context.currentTime, seconds / 3);
	}

	/** Moves layer levels to the chapter's mix. */
	private applyMix(): void {
		const context = this.context;
		if (!context) return;
		const [wind, music, paper] = MIX[this.chapter];
		const now = context.currentTime;
		this.wind?.gain.setTargetAtTime(wind * 0.35, now, 1.2);
		this.music?.gain.setTargetAtTime(music, now, 1.2);
		this.paper?.gain.setTargetAtTime(paper, now, 1.2);
	}
}
