/**
 * Every CSS custom property the stylesheets read is defined (`scoutlens-uze.31`).
 *
 * A `var(--x)` with no definition and no fallback does not fail loudly: the
 * whole declaration is dropped at computed-value time and the property falls
 * back to inheritance or its initial value. Four rules read an `--ink-700` that
 * tokens.css never defined, so they silently took their parent's ink; the
 * Lab's method disclosure read `--border` and `--surface`, so the card it was
 * styled as rendered with no border and no background. Nothing noticed,
 * because nothing errs.
 */

import { readdir, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const STYLES = resolve(__dirname, "..", "src", "app", "styles");
const WEB = resolve(__dirname, "..");

/**
 * Properties defined at runtime rather than in a stylesheet, each with where
 * it is set. The test checks that place still sets it.
 */
const RUNTIME_DEFINED: Readonly<Record<string, { file: string; why: string }>> = {
  "--font-inter": { file: "src/app/layout.tsx", why: "next/font's `variable` class on <body>" },
  "--period-a-position": { file: "src/components/lab-explorer.tsx", why: "inline style on each fingerprint track" },
  "--period-b-position": { file: "src/components/lab-explorer.tsx", why: "inline style on each fingerprint track" },
};

async function stylesheets(): Promise<Array<{ name: string; text: string }>> {
  const names = (await readdir(STYLES)).filter((name) => name.endsWith(".css"));
  return Promise.all(names.map(async (name) => ({ name, text: await readFile(join(STYLES, name), "utf8") })));
}

describe("CSS custom properties", () => {
  it("reads none that is never defined", async () => {
    const sheets = await stylesheets();
    const defined = new Set(
      sheets.flatMap(({ text }) => [...text.matchAll(/(--[a-z0-9-]+)\s*:/gi)].map((match) => match[1])),
    );
    const undefinedUses: string[] = [];
    for (const { name, text } of sheets) {
      // A use with a fallback - var(--x, value) - degrades by design.
      for (const match of text.matchAll(/var\(\s*(--[a-z0-9-]+)\s*\)/gi)) {
        const property = match[1]!;
        if (!defined.has(property) && !(property in RUNTIME_DEFINED)) {
          undefinedUses.push(`${name}: ${property}`);
        }
      }
    }
    expect(undefinedUses).toEqual([]);
  });

  it("still sets every property it excuses as runtime-defined", async () => {
    for (const [property, { file }] of Object.entries(RUNTIME_DEFINED)) {
      const source = await readFile(join(WEB, file), "utf8");
      expect(source, `${file} no longer sets ${property}`).toContain(property);
    }
  });

  it("would catch an undefined property (non-vacuous)", () => {
    const text = ".probe { color: var(--never-defined); border-color: var(--line, #000); }";
    const uses = [...text.matchAll(/var\(\s*(--[a-z0-9-]+)\s*\)/gi)].map((match) => match[1]);
    expect(uses).toEqual(["--never-defined"]);
  });
});
