import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Contract-only tests for showcase 2.0.0 (scoutlens-qop.6.2, D047).
//
// These assert the *generated consumer* agrees with the producer's schema.
// They deliberately touch no component, no repository and no published
// artifact: this leaf freezes a contract, it does not render anything.

const here = dirname(fileURLToPath(import.meta.url));
const generatedDirectory = resolve(here, "..", "src", "contracts", "generated");
const schemaDirectory = resolve(here, "..", "..", "src", "scoutlens", "showcase", "schemas");

type Json = Record<string, unknown>;

const readJson = (path: string): Json => JSON.parse(readFileSync(path, "utf8")) as Json;

// The schema is read as plain JSON. These accessors cast once, here, rather
// than restating the schema as a TypeScript type — the schema is the thing
// under test, so mirroring it in types would test the mirror.
const defs = (schema: Json): Json => schema.$defs as Json;
const def = (schema: Json, name: string): Json => defs(schema)[name] as Json;
const props = (node: Json): Json => node.properties as Json;
const prop = (node: Json, key: string): Json => props(node)[key] as Json;
const required = (node: Json): string[] => node.required as string[];

const generatedV1 = readJson(resolve(generatedDirectory, "showcase.schema.json"));
const generatedV2 = readJson(resolve(generatedDirectory, "showcase-v2.schema.json"));
const producerV1 = readJson(resolve(schemaDirectory, "showcase-1.0.0.schema.json"));
const producerV2 = readJson(resolve(schemaDirectory, "showcase-2.0.0.schema.json"));

describe("generated consumer matches the producer", () => {
  it("ships the v1 schema byte-for-byte", () => {
    expect(generatedV1).toEqual(producerV1);
  });

  it("ships the v2 schema byte-for-byte", () => {
    expect(generatedV2).toEqual(producerV2);
  });

  it("keeps the two majors as separate artifacts", () => {
    expect(generatedV1.$id).not.toEqual(generatedV2.$id);
    expect(generatedV1.$id).toContain("showcase-1.0.0");
    expect(generatedV2.$id).toContain("showcase-2.0.0");
  });
});

describe("major-version compatibility", () => {
  const declaredVersion = (schema: Json): Json => prop(def(schema, "manifest"), "schema_version");

  it("accepts both known majors", () => {
    expect(declaredVersion(generatedV1)).toEqual({ const: "1.0.0" });
    expect(declaredVersion(generatedV2)).toEqual({ const: "2.0.0" });
  });

  it("pins each major with a const rather than a permissive pattern", () => {
    // A pattern would let an unknown major validate against the wrong rules.
    for (const schema of [generatedV1, generatedV2]) {
      expect(Object.keys(declaredVersion(schema))).toEqual(["const"]);
    }
  });

  it("keeps dataset versions of the two majors mutually exclusive", () => {
    const v1Pattern = def(generatedV1, "dataset_version").pattern as string;
    const v2Pattern = def(generatedV2, "dataset_version").pattern as string;
    expect(v1Pattern).not.toEqual(v2Pattern);

    const v1Example = "wyscout-2017-18-v1-0123456789ab";
    const v2Example = "wyscout-2017-18-v2-0123456789ab";
    expect(new RegExp(v1Pattern).test(v1Example)).toBe(true);
    expect(new RegExp(v1Pattern).test(v2Example)).toBe(false);
    expect(new RegExp(v2Pattern).test(v2Example)).toBe(true);
    expect(new RegExp(v2Pattern).test(v1Example)).toBe(false);
  });
});

describe("v1 remains immutable", () => {
  it("still names the score cosine_similarity", () => {
    const outcome = props(def(generatedV1, "retrieval_outcome"));
    expect(outcome).toHaveProperty("cosine_similarity");
    expect(outcome).not.toHaveProperty("similarity_score");
  });

  it("carries no representation concept at all", () => {
    expect(defs(generatedV1)).not.toHaveProperty("representation");
    expect(required(def(generatedV1, "manifest"))).not.toContain("representation_id");
  });
});

describe("v2 representation semantics", () => {
  it("renames the score so a weighted metric does not claim plain cosine", () => {
    for (const name of ["retrieval_outcome", "statistical_neighbor"]) {
      const properties = props(def(generatedV2, name));
      expect(properties).toHaveProperty("similarity_score");
      expect(properties).not.toHaveProperty("cosine_similarity");
    }
  });

  it("requires a representation id on every ranking-bearing block", () => {
    for (const name of [
      "retrieval_outcome",
      "statistical_neighbor",
      "evidence_item",
      "uncertainty_block",
      "rank_uncertainty",
      "neighbor_stability",
      "manifest",
    ]) {
      expect(required(def(generatedV2, name))).toContain("representation_id");
    }
  });

  it("fixes the ranking method and the uncertainty design", () => {
    const representation = def(generatedV2, "representation");
    expect(prop(representation, "ranking_method")).toEqual({
      const: "weighted_cosine_diagonal_v1",
    });
    expect(prop(representation, "uncertainty_design")).toEqual({
      const: "match_bootstrap_diagonal_v1",
    });
  });

  it("requires the weighted reconstruction fields on evidence", () => {
    const evidence = required(def(generatedV2, "evidence_item"));
    expect(evidence).toContain("feature_weight");
    expect(evidence).toContain("weighted_contribution");
  });

  it("pins the canonical feature set at 28, ordered and unique", () => {
    const representation = def(generatedV2, "representation");
    expect(prop(representation, "feature_count")).toEqual({ const: 28 });
    const order = prop(representation, "feature_order");
    expect(order.minItems).toBe(28);
    expect(order.maxItems).toBe(28);
    expect(order.uniqueItems).toBe(true);
  });

  it("retains frozen cosine as the declared audit baseline", () => {
    const audit = prop(def(generatedV2, "representation"), "audit_baseline");
    expect(prop(audit, "method")).toEqual({ const: "cosine_v1" });
    expect(prop(audit, "contract")).toEqual({ const: "scoutlens.showcase/1.0.0" });
  });

  it("admits no unknown fields anywhere in the representation", () => {
    // An optional-field workaround would let an ambiguous payload pass.
    expect(def(generatedV2, "representation").additionalProperties).toBe(false);
    expect(def(generatedV2, "representation_artifact").additionalProperties).toBe(false);
  });
});
