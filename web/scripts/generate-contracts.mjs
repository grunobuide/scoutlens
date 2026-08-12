import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const schemaDirectory = resolve(webRoot, "..", "src", "scoutlens", "showcase", "schemas");
const generatedDirectory = resolve(webRoot, "src", "contracts", "generated");

// One entry per supported major. v1 is the frozen cosine contract and its
// outputs must stay byte-identical; v2 is the diagonal-representation contract
// (D047) and is emitted alongside rather than replacing it, so a consumer can
// accept both majors without either type set shifting under it.
const CONTRACTS = [
  {
    schemaFile: "showcase-1.0.0.schema.json",
    typesFile: "showcase.ts",
    schemaOutFile: "showcase.schema.json",
    rootType: "ShowcaseArtifact",
  },
  {
    schemaFile: "showcase-2.0.0.schema.json",
    typesFile: "showcase-v2.ts",
    schemaOutFile: "showcase-v2.schema.json",
    rootType: "ShowcaseArtifactV2",
  },
];

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

async function buildContract({ schemaFile, rootType }) {
  const schemaPath = resolve(schemaDirectory, schemaFile);
  const schemaSource = await readFile(schemaPath, "utf8");
  const schema = JSON.parse(schemaSource);

  // json-schema-to-typescript consumes draft-07 tuple syntax. Keep the published
  // 2020-12 schema intact and adapt only the compiler input.
  const typeGenerationSchema = normalizeTuplesForTypeGeneration(schema);
  const generated = await compile(typeGenerationSchema, rootType, {
    bannerComment: [
      `/** Generated from src/scoutlens/showcase/schemas/${schemaFile}.`,
      " * Do not edit by hand; run pnpm contracts:generate.",
      " */",
    ].join("\n"),
    cwd: schemaDirectory,
    unreachableDefinitions: true,
  });

  return { schemaSource, generated };
}

const results = [];
for (const contract of CONTRACTS) {
  results.push({ contract, ...(await buildContract(contract)) });
}

if (process.argv.includes("--check")) {
  const stale = [];
  for (const { contract, schemaSource, generated } of results) {
    const typesPath = resolve(generatedDirectory, contract.typesFile);
    const schemaOutPath = resolve(generatedDirectory, contract.schemaOutFile);
    const currentTypes = await readFile(typesPath, "utf8").catch(() => "");
    const currentSchema = await readFile(schemaOutPath, "utf8").catch(() => "");
    if (currentTypes !== generated || currentSchema !== schemaSource) {
      stale.push(contract.schemaFile);
    }
  }
  if (stale.length > 0) {
    throw new Error(
      `Generated TypeScript contract is stale for ${stale.join(", ")}; run pnpm contracts:generate`,
    );
  }
  console.log("Generated TypeScript contracts are current");
} else {
  await mkdir(generatedDirectory, { recursive: true });
  for (const { contract, schemaSource, generated } of results) {
    const typesPath = resolve(generatedDirectory, contract.typesFile);
    const schemaOutPath = resolve(generatedDirectory, contract.schemaOutFile);
    await rm(typesPath, { force: true });
    await writeFile(typesPath, generated, "utf8");
    await writeFile(schemaOutPath, schemaSource, "utf8");
    console.log(`Generated ${typesPath}`);
  }
}
