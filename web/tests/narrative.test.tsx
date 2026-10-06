/**
 * The thesis and boundary constants are the frozen narrative's
 * (`scoutlens-9a3.18`, D066).
 *
 * docs/public-experience-narrative.md section 2 is the owner. These tests read
 * it, so a constant edited here without the document - or the document
 * without the constant - fails, and the only permitted difference is the one
 * the public identity contract allows: the display name.
 */

import { readdir, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ThesisStatement } from "@/components/thesis-statement";
import { BOUNDARY, DISPLAY_NAME, THESIS } from "@/content/narrative";

const NARRATIVE = resolve(__dirname, "..", "..", "docs", "public-experience-narrative.md");

/** The blockquote that follows a bold label in section 2, joined to one line. */
async function frozenQuote(label: string): Promise<string> {
  const lines = (await readFile(NARRATIVE, "utf8")).split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith(`**${label}`));
  expect(start, `section 2 has no "${label}" label`).toBeGreaterThan(-1);
  const quote: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith(">")) {
      quote.push(line.replace(/^>\s?/, ""));
    } else if (quote.length > 0) {
      break;
    }
  }
  return quote.join(" ").replace(/\s+/g, " ").trim();
}

describe("the shared thesis and boundary", () => {
  it("is section 2's thesis, with only the display name substituted", async () => {
    const frozen = await frozenQuote("Thesis");
    expect(frozen).toContain("ScoutLens");
    expect(THESIS).toBe(frozen.replace("ScoutLens", DISPLAY_NAME));
  });

  it("is section 2's boundary sentence, verbatim", async () => {
    expect(BOUNDARY).toBe(await frozenQuote("Boundary sentence"));
  });

  it("renders the two sentences adjacent, thesis first, and nothing else", () => {
    const html = renderToStaticMarkup(<ThesisStatement thesisClassName="a" boundaryClassName="b" />);
    expect(html).toBe(
      `<p class="a" data-thesis="true">${THESIS.replaceAll("'", "&#x27;")}</p>` +
        `<p class="b" data-thesis-boundary="true">${BOUNDARY}</p>`,
    );
  });

  it("is the only thesis and boundary wording left in the route sources", async () => {
    // The three wordings this replaced, one per route. A route that brings its
    // own back is a second thesis again.
    const retired = [
      "tests whether event-derived profiles can retrieve the same player",
      "Evidence of individual signal. Not proof of playing style.",
      "This is a statistical fingerprint",
    ];
    const app = resolve(__dirname, "..", "src", "app");
    const pages = (await readdir(app, { recursive: true, withFileTypes: true }))
      .filter((entry) => entry.isFile() && entry.name === "page.tsx")
      .map((entry) => join(entry.parentPath, entry.name));
    expect(pages.length).toBeGreaterThanOrEqual(3);
    for (const page of pages) {
      const source = await readFile(page, "utf8");
      for (const wording of retired) {
        expect(source, `${page} words its own thesis or boundary`).not.toContain(wording);
      }
      expect(source, `${page} must render the shared statement`).toContain("<ThesisStatement");
    }
  });
});
