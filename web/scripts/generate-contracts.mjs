import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const schemaPath = resolve(
  webRoot,
  "..",
  "src",
  "scoutlens",
  "showcase",
  "schemas",
  "showcase-1.0.0.schema.json",
);
const outputPath = resolve(webRoot, "src", "contracts", "generated", "showcase.ts");
const schemaOutputPath = resolve(webRoot, "src", "contracts", "generated", "showcase.schema.json");
const schemaSource = await readFile(schemaPath, "utf8");
const schema = JSON.parse(schemaSource);
const generated = await compile(schema, "ShowcaseArtifact", {
  bannerComment: [
    "/** Generated from src/scoutlens/showcase/schemas/showcase-1.0.0.schema.json.",
    " * Do not edit by hand; run pnpm contracts:generate.",
    " */",
  ].join("\n"),
  cwd: dirname(schemaPath),
  unreachableDefinitions: true,
});

if (process.argv.includes("--check")) {
  const current = await readFile(outputPath, "utf8").catch(() => "");
  const currentSchema = await readFile(schemaOutputPath, "utf8").catch(() => "");
  if (current !== generated || currentSchema !== schemaSource) {
    throw new Error("Generated TypeScript contract is stale; run pnpm contracts:generate");
  }
  console.log("Generated TypeScript contract is current");
} else {
  await mkdir(dirname(outputPath), { recursive: true });
  await rm(outputPath, { force: true });
  await writeFile(outputPath, generated, "utf8");
  await writeFile(schemaOutputPath, schemaSource, "utf8");
  console.log(`Generated ${outputPath}`);
}
