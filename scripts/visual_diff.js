const fs = require('fs');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch');

/**
 * Visual Diff Script (CommonJS version)
 * Compares two PNG images and produces a diff image and a mismatch percentage.
 * 
 * Usage: node visual_diff.js <img1> <img2> <diff_output> [threshold]
 */

const [img1Path, img2Path, diffPath, thresholdParam] = process.argv.slice(2);

if (!img1Path || !img2Path || !diffPath) {
    console.error('Usage: node visual_diff.js <img1> <img2> <diff_output> [threshold]');
    process.exit(1);
}

const threshold = parseFloat(thresholdParam || '0.1');

try {
    const img1Buffer = fs.readFileSync(img1Path);
    const img2Buffer = fs.readFileSync(img2Path);

    const img1 = PNG.sync.read(img1Buffer);
    const img2 = PNG.sync.read(img2Buffer);

    const { width, height } = img1;
    if (img2.width !== width || img2.height !== height) {
        console.error(`Dimension mismatch: Image1 is ${width}x${height}, Image2 is ${img2.width}x${img2.height}`);
        // Return 100% mismatch for logic consistency if dimensions differ
        console.log(JSON.stringify({
            mismatchPixels: width * height,
            totalPixels: width * height,
            mismatchPercentage: "100.00",
            diffPath: null,
            error: "dimension_mismatch"
        }));
        process.exit(0); // Exit 0 because we're providing JSON output
    }

    const diff = new PNG({ width, height });
    const numDiffPixels = pixelmatch(img1.data, img2.data, diff.data, width, height, { threshold });

    fs.writeFileSync(diffPath, PNG.sync.write(diff));

    const totalPixels = width * height;
    const mismatchPct = (numDiffPixels / totalPixels) * 100;

    console.log(JSON.stringify({
        mismatchPixels: numDiffPixels,
        totalPixels: totalPixels,
        mismatchPercentage: mismatchPct.toFixed(2),
        diffPath: diffPath
    }));

    process.exit(0);
} catch (error) {
    console.error(`Error comparing images: ${error.message}`);
    process.exit(1);
}
