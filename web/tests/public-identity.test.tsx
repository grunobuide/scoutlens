import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SiteHeader } from "@/components/site-header";

/**
 * `scoutlens-vif.4`. The display brand is Yumusarái Labs; every technical
 * identifier stays `scoutlens`. Those are two different names on purpose, and
 * this file is the test that keeps them apart.
 *
 * The frozen fields come from `docs/public-identity-contract.md` §1, and the
 * do-not-rename inventory from §4. The interesting half is the second one: a
 * future "let's finish the rename" pass would look like tidying and would
 * break published deep links, import paths and artifact digests.
 */

const BRAND = "Yumusarái Labs";
const MONOGRAM = "YL";
const DESCRIPTOR = "Player Fingerprint Lab";
const SHORT_DESCRIPTOR = "Fingerprint Lab";

const RETIRED = "ScoutLens";

const REPO_ROOT = resolve("..");

describe("the frozen display identity", () => {
  it("names the brand with its accent in the header, exactly", () => {
    const markup = renderToStaticMarkup(<SiteHeader />);
    expect(markup).toContain(BRAND);
    expect(markup).not.toContain(RETIRED);
    // The accent is not decoration. `Yumusarai Labs` is the ASCII fallback for
    // places that cannot carry one; a rendered page is not such a place.
    expect(markup).not.toContain("Yumusarai Labs");
  });

  it("carries the monogram as decoration, so a screen reader hears the name once", () => {
    const markup = renderToStaticMarkup(<SiteHeader />);
    expect(markup).toContain(`aria-hidden="true"`);
    expect(markup).toContain(MONOGRAM);
    expect(markup).not.toContain("SL<");
    expect(markup).toContain(`aria-label="${BRAND} home"`);
  });

  it("keeps the descriptor unchanged, in both the places it appears", async () => {
    // The product is still the Player Fingerprint Lab. Only the publisher's
    // name changed, and none of these strings is the publisher: the landing
    // eyebrow carries the full descriptor, the nav and the /lab title carry
    // its short form. A rename that touched any of them renamed the product.
    const markup = renderToStaticMarkup(<SiteHeader />);
    expect(markup).toContain(SHORT_DESCRIPTOR);

    const landing = await readFile(resolve("src", "app", "page.tsx"), "utf8");
    expect(landing).toContain(`<p className="eyebrow">${DESCRIPTOR}</p>`);

    const lab = await readFile(resolve("src", "app", "lab", "page.tsx"), "utf8");
    expect(lab).toContain(`title: "${SHORT_DESCRIPTOR}",`);
  });

  // `layout.tsx` is read as source rather than imported: it calls
  // `next/font/local`, which only exists inside the Next build, so importing
  // it here would test the bundler rather than the metadata.
  it("uses the brand in the title default, the title template and applicationName", async () => {
    const layout = await readFile(resolve("src", "app", "layout.tsx"), "utf8");
    expect(layout).toContain(`default: "${BRAND} — Player Fingerprints",`);
    expect(layout).toContain(`template: "%s — ${BRAND}",`);
    expect(layout).toContain(`applicationName: "${BRAND}",`);
    expect(layout).not.toContain(RETIRED);
  });

  it("leaves the description alone: it describes the work, not the publisher", async () => {
    const layout = await readFile(resolve("src", "app", "layout.tsx"), "utf8");
    // The description is about the research, and a rename has no business in
    // it. Asserted by its exact text so a name cannot be slipped in later.
    expect(layout).toContain(
      '"An evidence-first exploration of stable statistical fingerprints in football event data."',
    );
  });
});

describe("the do-not-rename inventory", () => {
  it("keeps every technical identifier on scoutlens", async () => {
    // Each of these would break something real if renamed: published deep
    // links and release-asset URLs, the fail-closed contract string validated
    // at the web boundary, and the import path printed in the README as a
    // reproduction command.
    const [layout, science, story, packageJson] = await Promise.all([
      readFile(resolve("src", "app", "layout.tsx"), "utf8"),
      readFile(resolve("src", "app", "science", "page.tsx"), "utf8"),
      readFile(resolve("src", "components", "research-story.tsx"), "utf8"),
      readFile(resolve("package.json"), "utf8"),
    ]);

    expect(science).toContain("github.com/grunobuide/scoutlens");
    expect(story).toContain("github.com/grunobuide/scoutlens");
    expect(JSON.parse(packageJson).name).not.toContain("yumusarai");

    // The layout is the file that changed most; it must not have acquired a
    // technical rename along the way.
    expect(layout).not.toContain("yumusarai-labs");
  });

  it("keeps the artifact contract string, which is validated fail-closed", async () => {
    const manifest = JSON.parse(
      await readFile(resolve(REPO_ROOT, "public", "showcase", "v2", "manifest.json"), "utf8"),
    ) as { contract: string; source: { redistribution_note: string } };

    expect(manifest.contract).toBe("scoutlens.showcase");

    // The one reader-facing occurrence of the old name that this rename
    // cannot touch. It is baked into a content-addressed artifact whose
    // digest is pinned by config/showcase-payload-pack.json and belongs to an
    // already published release asset; rewording it would change the dataset
    // identity the case study and release manifest both quote.
    //
    // Contract §5: the standard is not "no old brand on the active surface",
    // which was never achievable, but "no *unexplained* old brand". This
    // assertion exists so that a future reader who finds that string on the
    // page finds this explanation with it, rather than filing it as a defect.
    expect(manifest.source.redistribution_note).toContain(RETIRED);
  });

  it("still pins the same dataset and representation", async () => {
    const pack = JSON.parse(
      await readFile(resolve(REPO_ROOT, "config", "showcase-payload-pack.json"), "utf8"),
    ) as { dataset_version: string; representation: { id: string } };

    expect(pack.dataset_version).toBe("wyscout-2017-18-v2-332766e3a822");
    expect(pack.representation.id).toBe("rep-f018e6041ccbad10");
  });
});

describe("the scientific surface is untouched by a rename", () => {
  it("does not put the brand anywhere near a claim, caveat or metric", async () => {
    // A rebrand has no business inside the evidence. If the brand appears in
    // any of these, a name-only replacement reached further than it should.
    for (const file of [
      resolve("src", "components", "research-story.tsx"),
      resolve("src", "components", "lab-explorer.tsx"),
      resolve("src", "content", "evidence-explanations.ts"),
    ]) {
      const source = await readFile(file, "utf8");
      expect(source, `${file} should not mention the display brand`).not.toContain(BRAND);
    }
  });

  it("leaves the fail-closed integrity message fail-closed", async () => {
    const source = await readFile(resolve("src", "content", "showcase-lab.ts"), "utf8");
    // The name in the sentence changed. The sentence's job did not: it still
    // says nothing was rendered, and the state is still retryable.
    expect(source).toContain(`"${BRAND} stopped before rendering any profile values.`);
    expect(source).toContain("This profile does not match the active manifest");
    expect(source).toContain("Integrity check failed");
  });
});
