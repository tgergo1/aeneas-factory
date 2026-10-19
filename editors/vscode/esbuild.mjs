// Bundles the extension (Node, for the extension host) and the 3D viewer (browser, for its webview).
import * as esbuild from "esbuild";

const production = process.argv.includes("--production");
const watch = process.argv.includes("--watch");

const builds = [
  { entryPoints: ["src/extension.ts"], outfile: "dist/extension.js", platform: "node", format: "cjs", external: ["vscode"] },
  { entryPoints: ["media/glb-viewer.ts"], outfile: "dist/glb-viewer.js", platform: "browser", format: "iife" },
];

for (const b of builds) {
  const options = { ...b, bundle: true, target: "es2022", sourcemap: !production, minify: production, logLevel: "warning" };
  if (watch) {
    await (await esbuild.context(options)).watch();
  } else {
    await esbuild.build(options);
  }
}
