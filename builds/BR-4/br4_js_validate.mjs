// BR-4 — runs the CF worker's pure validator against a local descriptor, offline.
// Extracts the const block + pure validator functions from the CURRENT
// workers/github-app-advisory/index.js at runtime (no edit to index.js, no stale
// copy -> zero drift). NEVER calls the live worker /run.
//
//   node br4_js_validate.mjs <descriptor.json> <index.js>
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [descPath, indexPath] = process.argv.slice(2);
const src = readFileSync(indexPath, "utf8").split("\n");

const firstFn = src.findIndex((l) => /^(async )?function /.test(l));
const constBlock = src.slice(0, firstFn).join("\n");

const vStart = src.findIndex((l) => l.startsWith("function validSha256("));
const vEnd = src.findIndex((l) => l.startsWith("async function readArtifactDescriptor"));
const valBlock = src.slice(vStart, vEnd).join("\n");

const mod = constBlock + "\n" + valBlock +
  "\nexport { validateArtifactDescriptor, validSha256, validHex, optionalString };\n";
const dir = mkdtempSync(join(tmpdir(), "br4-"));
const modPath = join(dir, "lifted.mjs");
writeFileSync(modPath, mod);

const { validateArtifactDescriptor } = await import(pathToFileURL(modPath).href);
const descriptor = JSON.parse(readFileSync(descPath, "utf8"));
const res = validateArtifactDescriptor(descriptor, {});
console.log(JSON.stringify({ ok: res.failures.length === 0, failures: res.failures }));
