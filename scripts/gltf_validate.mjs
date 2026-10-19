// Validate a glTF/GLB with the Khronos glTF-Validator; prints a JSON summary, exits 1 on errors.
// Usage: aen tool gltf-validator -- model.glb
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(process.env.AEN_NODE_MODULES + "/");
const validator = require("gltf-validator");
const file = process.argv[2];
const report = await validator.validateBytes(new Uint8Array(readFileSync(file)), { uri: file, maxIssues: 50 });
const i = report.issues;
console.log(JSON.stringify({ file, errors: i.numErrors, warnings: i.numWarnings, infos: i.numInfos,
  vertices: report.info?.totalVertexCount, triangles: report.info?.totalTriangleCount,
  messages: i.messages.filter(m => m.severity === 0).slice(0, 10).map(m => `${m.code}: ${m.message}`) }, null, 2));
process.exit(i.numErrors ? 1 : 0);
