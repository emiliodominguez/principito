# The Little Prince: a paper storybook

An interactive, scroll-driven stop-motion film about a boy on a very small planet, built from Blender scripts and shown in the browser. Everything you see is procedural: puppets, sets, paintings, and the sound. There is no authored art in this repository, only the code that makes it.

An unofficial homage to the book by Antoine de Saint-Exupéry. Narration is an original short telling, in English and Spanish.

## Running it

Deployed on Vercel with Web Analytics.

Requires Node 26.12.1, pnpm 12.8.1, and for rebuilding assets, Blender 5.4 at `/Applications/Blender.app`.

```sh
pnpm install
pnpm dev            # http://localhost:4321
pnpm check          # format, lint, types, unit tests, production build
pnpm build          # static site in dist/
```

Built assets are committed under `public/`, so Blender is only needed to change them.

```sh
pnpm assets                       # everything: about 3 minutes on an M1 Pro
pnpm assets:blender prince fox    # rebuild named assets
pnpm assets:optimize prince fox   # recompress named assets for all tiers
```

URL switches: `?mode=book` or `?mode=film`, `?tier=high|medium|low`, `?gpu=any` (allows software rendering) and `?debug` (exposes `window.__story` for capture and tests). `/es/` is the Spanish edition.

## How it is made

### One timeline, derived from scroll

The page is a tall spacer. `ScrollDirector` turns scroll into a story position, and every visual is a pure function of that position and the stage clock. Nothing accumulates, so scrubbing backward lands on exactly the same picture, which `scripts/verify-scroll.sh` checks by comparing pixels.

```
scroll -> ScrollDirector -> story position -> CameraController (shot tracks, responsive solve)
                                           -> Chapter.update (blocking, poses)
                                           -> look track (lights, backdrop)
                                           -> StoryOverlay (narration, navigation)
```

- `src/story/` holds the domain, free of Three.js: the shot list and lighting plot (`chapters.ts`), timeline maths, animation time and world layout.
- `src/engine/` holds rendering, scene, input, assets, audio and performance.
- `src/chapters/` holds one class per chapter. A chapter loads its set and maps its local `t` to state. It never touches the renderer or the DOM.

### Puppet motion

Clips are authored at 12 frames per second in `blender/animations.py` and glide between frames at display rate, because stepped motion read as dropped frames on screen. Scroll-driven clips are seeked by position, so scrubbing backward shows the same pose, and looping clips follow a continuous clock. Faces and hands are replacement parts: bones keyed to scale 0 or 1 that snap, as an animator swaps a mouth. The birds' wingbeats step the same way.

### Responsive cinematography

Shots do not store camera positions. Each states what must stay in frame (`fit`) and where it sits on screen (`placeX`, `placeY`), with an optional portrait variant. `solveShot` derives the distance from the real aspect ratio and safe-area insets, and wide and tall compositions blend continuously rather than switching at a breakpoint.

### Blender pipeline

`blender/generate_assets.py` rebuilds everything from an empty scene:

1. **Sculpt** (`sculpt.py`, `characters.py`, `fox.py`, `set_pieces.py`): forms are voxel-fused, then worked by hand-like operations such as thumb dents, warps and creases.
2. **Materials** (`materials.py`, `textures.py`, `paper_craft.py`): the crumple comes from a simulated fold field of thousands of straight V-creases, because smooth noise only ever looks like lumpy clay. Grass and leaves are real cut sheets.
3. **Bake** (`bake.py`): each piece is decimated and baked from its high mesh into a hand-assigned atlas rectangle, and occlusion is baked across the assembled puppet with replacement parts moved out of the way.
4. **Rig and animate** (`animations.py`): capsule-distance skinning, world-axis pose library, stepped clips.
5. **Export and compress** (`export.py`, `scripts/optimize-assets.mjs`): removes animation channels that sit at rest, so layered clips do not average each other, then writes three tiers with meshopt geometry and KTX2 textures.

Painted backdrops and cut-paper sheets are computed in numpy (`backgrounds.py`) and shipped as WebP.

### Editions

Without JavaScript or WebGL, or with `prefers-reduced-motion`, the page is an illustrated book: the same text in the document, set with stills captured from the film. Three.js is only requested in film mode. A reader can switch at any time, and the choice is remembered.

Sound is synthesized with Web Audio, so it needs no files or licences. It starts muted and only begins inside a click.

## Verification

```sh
pnpm check                                       # static checks, 39 unit tests, build
BASE_URL=http://localhost:4322 scripts/verify-app.sh     # end to end against `astro preview`
BASE_URL=http://localhost:4322 scripts/verify-scroll.sh  # forward and backward frames match
BASE_URL=http://localhost:4322 scripts/measure-gpu.sh    # true frame cost, GPU included
BASE_URL=http://localhost:4322 scripts/measure-cold.sh   # main-thread stalls on a first scroll
scripts/capture-stills.sh                        # regenerate the illustrated edition
```

The browser scripts use `agent-browser`. Most need to run outside any sandbox that blocks Chromium. See [docs/results.md](docs/results.md) for the latest numbers.
