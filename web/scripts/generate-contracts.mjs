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

function normalizeTuplesForTypeGeneration(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeTuplesForTypeGeneration);
  }
  if (value === null || typeof value !== "object") {
    return value;
  }

  if ("prefixItems" in value) {
    if (!Array.isArray(value.prefixItems) || value.items !== false) {
      throw new Error("Tuple schemas must declare prefixItems with items: false");
    }
    const { prefixItems } = value;
    const rest = Object.fromEntries(
      Object.entries(value).filter(([key]) => key !== "prefixItems" && key !== "items"),
    );
    return {
      ...normalizeTuplesForTypeGeneration(rest),
      items: prefixItems.map(normalizeTuplesForTypeGeneration),
      additionalItems: false,
    };
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, child]) => [key, normalizeTuplesForTypeGeneration(child)]),
  );
}

// json-schema-to-typescript consumes draft-07 tuple syntax. Keep the published
// 2020-12 schema intact and adapt only the compiler input.
const typeGenerationSchema = normalizeTuplesForTypeGeneration(schema);
const generated = await compile(typeGenerationSchema, "ShowcaseArtifact", {
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
