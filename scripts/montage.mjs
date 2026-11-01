// Tiles captures into one sheet: scripts/montage.mjs <out.png> <columns> <tile-width> <files...>
import sharp from "sharp";

const [output, columnArg, widthArg, ...files] = process.argv.slice(2);
const columns = Number(columnArg);
const width = Number(widthArg);
const first = await sharp(files[0]).metadata();
const height = Math.round((width * first.height) / first.width);
const rows = Math.ceil(files.length / columns);
const tiles = await Promise.all(
	files.map(async (file, index) => ({
		input: await sharp(file).resize(width, height).toBuffer(),
		left: (index % columns) * (width + 4),
		top: Math.floor(index / columns) * (height + 4),
	})),
);
await sharp({ create: { width: columns * (width + 4), height: rows * (height + 4), channels: 3, background: "#000" } })
	.composite(tiles)
	.png()
	.toFile(output);
console.log(output);
