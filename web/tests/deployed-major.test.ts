/**
 * The served major and the pinned payload must be the same major
 * (`scoutlens-qop.6.6.4`).
 *
 * They drifted once: `qop.6.6.2` repinned to v2 while the consumer still
 * served v1, and CI went red because a clean clone hydrates whatever the pin
 * names, so the build was serving a manifest whose 1,257 profiles nobody could
 * fetch. Nothing in the type system connects a TypeScript constant to a JSON
 * file two directories up, so this test is the connection.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { ACTIVE_SHOWCASE_MAJOR, showcaseBaseUrl } from "@/contracts/showcase-repository";

const PIN = JSON.parse(
  readFileSync(resolve(__dirname, "..", "..", "config", "showcase-payload-pack.json"), "utf8"),
) as { schema_version: string; dataset_version: string };

describe("the served major follows the payload pin", () => {
  it("serves the major the pin hydrates", () => {
    const pinnedMajor = Number(PIN.schema_version.split(".")[0]);
    expect(ACTIVE_SHOWCASE_MAJOR).toBe(pinnedMajor);
  });

  it("reads assets from that major's directory", () => {
    expect(showcaseBaseUrl()).toBe(`/showcase/v${ACTIVE_SHOWCASE_MAJOR}/`);
  });

  it("agrees with the dataset the pin names", () => {
    // The pin states the major twice - once as its own schema, once in the
    // dataset prefix. Both must point at what the site serves, or one of them
    // is describing a dataset that is not being published.
    expect(PIN.dataset_version).toMatch(
      new RegExp(`^wyscout-2017-18-v${ACTIVE_SHOWCASE_MAJOR}-`),
    );
  });
});
