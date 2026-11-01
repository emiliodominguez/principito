// Turns Blender's raw output into browser assets, one set per performance tier:
// meshopt-compressed GLBs with KTX2 textures, WebP backdrops, and the fps/clip manifest.
import { copyFile, mkdir, readdir, readFile, stat, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";

import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, EXTMeshoptCompression, KHRTextureBasisu } from "@gltf-transform/extensions";
import { dedup, prune, quantize, reorder, simplify, weld } from "@gltf-transform/functions";
import { encodeToKTX2 } from "ktx2-encoder";
import { MeshoptDecoder, MeshoptEncoder, MeshoptSimplifier } from "meshoptimizer";
import sharp from "sharp";

const BUILD = "blender/.build";
const TIERS = {
	high: { texture: 3072, simplify: 1 },
	medium: { texture: 1536, simplify: 0.7 },
	low: { texture: 512, simplify: 0.45 },
};
const BACKDROP_WIDTH = { high: 3072, medium: 2048, low: 1280 };
// Quantizing recentres a mesh and moves the correction onto its node. Instanced meshes use the raw
// geometry and never see that node, so these must keep their authored coordinates.
const INSTANCED = new Set(["stars", "birds"]);
const filter = process.argv.slice(2);

/**
 * Decodes an image for the KTX2 encoder.
 * @param {Uint8Array} buffer Encoded image.
 * @returns {Promise<{data: Uint8Array, width: number, height: number}>} Raw RGBA pixels.
 */
async function imageDecoder(buffer) {
	const { data, info } = await sharp(buffer).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
	return { data: new Uint8Array(data), width: info.width, height: info.height };
}

/**
 * Re-encodes every texture in a document to KTX2 at the tier's size.
 * Colour and normals keep UASTC quality; the ORM map is mostly flat, so it drops one size further.
 * @param {import("@gltf-transform/core").Document} document The glTF document.
 * @param {number} limit Maximum edge length.
 * @returns {Promise<void>}
 */
async function compressTextures(document, limit) {
	document.createExtension(KHRTextureBasisu).setRequired(true);
	const root = document.getRoot();
	const normals = new Set(root.listMaterials().map((material) => material.getNormalTexture()));
	const colors = new Set(root.listMaterials().map((material) => material.getBaseColorTexture()));
	for (const texture of root.listTextures()) {
		const isColor = colors.has(texture);
		const isNormal = normals.has(texture);
		const size = isColor || isNormal ? limit : Math.max(256, limit / 2);
		const metadata = await sharp(texture.getImage()).metadata();
		const png = await sharp(texture.getImage()).resize(Math.min(size, metadata.width)).png().toBuffer();
		const encoded = await encodeToKTX2(new Uint8Array(png), {
			isUASTC: true,
			uastcLDRQualityLevel: 1,
			// FAST skips the slow rate-distortion pass, for quick looks while iterating.
			enableRDO: !process.env.FAST,
			rdoQualityLevel: isNormal ? 1 : 2,
			generateMipmap: true,
			needSupercompression: true,
			isKTX2File: true,
			isNormalMap: isNormal,
			isSetKTX2SRGBTransferFunc: isColor,
			isPerceptual: isColor,
			imageDecoder,
			enableDebug: false,
		});
		texture.setImage(encoded).setMimeType("image/ktx2");
	}
}

/**
 * Removes animation channels that hold a node at its rest transform for a whole clip.
 * Blender's sampled export writes every bone into every clip, but clips here play layered
 * (body, scarf, face), and a channel holding rest in one clip would be averaged against the
 * real motion in another. Stripping them leaves each clip touching only what it moves.
 * @param document The glTF document.
 * @returns {void}
 */
function stripRestChannels(document) {
	const tolerance = 0.0005;
	for (const clip of document.getRoot().listAnimations()) {
		for (const channel of clip.listChannels()) {
			const node = channel.getTargetNode();
			const sampler = channel.getSampler();
			if (!node || !sampler) continue;
			const path = channel.getTargetPath();
			const rest = path === "rotation" ? node.getRotation() : path === "translation" ? node.getTranslation() : node.getScale();
			const output = sampler.getOutput();
			let moves = false;
			const element = [];
			for (let i = 0; i < output.getCount() && !moves; i++) {
				output.getElement(i, element);
				moves = element.some((value, axis) => Math.abs(value - rest[axis]) > tolerance);
			}
			if (!moves) {
				clip.removeChannel(channel);
				channel.dispose();
			}
		}
	}
}

/**
 * Optimizes one GLB for one tier.
 * @param {NodeIO} io The configured reader and writer.
 * @param {string} path Source GLB.
 * @param {string} tier Tier name.
 * @returns {Promise<void>}
 */
async function optimizeModel(io, path, tier) {
	const document = await io.read(path);
	const settings = TIERS[tier];
	stripRestChannels(document);
	// Blender's specular setting would otherwise turn every material into the costlier MeshPhysicalMaterial.
	for (const extension of document.getRoot().listExtensionsUsed()) {
		if (extension.extensionName === "KHR_materials_specular" || extension.extensionName === "KHR_materials_ior") extension.dispose();
	}
	const steps = [dedup(), weld()];
	if (settings.simplify < 1) steps.push(simplify({ simplifier: MeshoptSimplifier, ratio: settings.simplify, error: 0.004 }));
	steps.push(
		prune({ keepAttributes: true, keepLeaves: true }),
		reorder({ encoder: MeshoptEncoder }),
		...(INSTANCED.has(basename(path, ".glb")) ? [] : [quantize({ quantizeNormal: 12, quantizeTexcoord: 14 })]),
	);
	await document.transform(...steps);
	await compressTextures(document, settings.texture);
	document.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
	const out = join("public/models", tier);
	await mkdir(out, { recursive: true });
	const target = join(out, basename(path));
	await io.write(target, document);
	console.log(tier, basename(path), `${((await stat(target)).size / 1048576).toFixed(2)} MB`);
}

/**
 * Converts painted backdrops and paper layers to WebP for each tier.
 * @returns {Promise<void>}
 */
async function optimizeBackdrops() {
	const directory = join(BUILD, "backgrounds");
	for (const file of await readdir(directory)) {
		const name = basename(file, ".png");
		if (filter.length > 0 && !filter.includes(name) && !filter.includes("backdrops")) continue;
		for (const [tier, width] of Object.entries(BACKDROP_WIDTH)) {
			const out = join("public/backgrounds", tier);
			await mkdir(out, { recursive: true });
			const meta = await sharp(join(directory, file)).metadata();
			await sharp(join(directory, file))
				.resize(Math.min(meta.hasAlpha ? Math.round(width * 0.67) : width, meta.width))
				.webp({ quality: 84, alphaQuality: 90, effort: 5 })
				.toFile(join(out, `${name}.webp`));
		}
	}
}

/**
 * Merges per-asset manifests into the module the engine imports.
 * @returns {Promise<void>}
 */
async function writeManifest() {
	const directory = join(BUILD, "manifest");
	const merged = {};
	for (const file of await readdir(directory)) merged[basename(file, ".json")] = JSON.parse(await readFile(join(directory, file), "utf8"));
	await writeFile("src/story/assets-manifest.json", `${JSON.stringify(merged, null, "\t")}\n`);
}

await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready, MeshoptSimplifier.ready]);
const io = new NodeIO()
	.registerExtensions(ALL_EXTENSIONS)
	.registerDependencies({ "meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder });

await mkdir("public/basis", { recursive: true });
for (const file of ["basis_transcoder.js", "basis_transcoder.wasm"])
	await copyFile(join("node_modules/three/examples/jsm/libs/basis", file), join("public/basis", file));

for (const file of await readdir(join(BUILD, "glb"))) {
	const name = basename(file, ".glb");
	if (filter.length > 0 && !filter.includes(name)) continue;
	for (const tier of Object.keys(TIERS)) await optimizeModel(io, join(BUILD, "glb", file), tier);
}
await optimizeBackdrops();
await writeManifest();
