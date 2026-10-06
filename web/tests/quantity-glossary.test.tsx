/**
 * The per-section quantity disclosure (`scoutlens-9a3.19`, closing 9a3.2 AC5).
 *
 * "Inline summaries and expanded explanations expose identical semantics to
 * visual, keyboard and screen-reader users; tooltip-only access is
 * prohibited." Rendered here, the claim is structural: one native
 * `<details>`, whose `<summary>` names exactly the terms the body defines, and
 * whose body is the registry record verbatim - no second wording to drift.
 * The keyboard and accessibility-tree half is in e2e/quantity-explainers.spec.ts.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { QuantityGlossary, quantityTag } from "@/components/quantity-glossary";
import {
  ExplanationNotFoundError,
  explainQuantity,
  quantityExplanationKeys,
  type QuantityId,
} from "@/content/evidence-explanations";

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#x27;");
}

const ALL = quantityExplanationKeys();

describe("QuantityGlossary", () => {
  const html = renderToStaticMarkup(<QuantityGlossary ids={ALL} />);

  it("is one native disclosure, closed by default, with no hover-only content", () => {
    expect(html.match(/<details/g)).toHaveLength(1);
    expect(html).toMatch(/^<details class="quantity-glossary" data-quantity-glossary="true">/);
    expect(html).not.toMatch(/<details[^>]* open/);
    expect(html.match(/<summary>/g)).toHaveLength(1);
    expect(html).not.toMatch(/\btitle=|role="tooltip"|onmouseover/i);
  });

  it("names in its summary exactly the terms its body defines", () => {
    const summary = /<summary>(.*?)<\/summary>/s.exec(html)?.[1] ?? "";
    const defined = [...html.matchAll(/<dt>(.*?)<\/dt>/g)].map((match) => match[1]);
    expect(defined).toEqual(ALL.map((id) => escapeHtml(explainQuantity(id).term)));
    for (const term of defined) {
      expect(summary).toContain(term);
    }
  });

  it("expands to the registry record verbatim, all five parts, for every quantity", () => {
    for (const id of ALL) {
      const explanation = explainQuantity(id);
      const entry = new RegExp(`<div data-quantity-explainer="${id}">(.*?)</div>`, "s").exec(html)?.[1] ?? "";
      expect(entry, `${id} has no entry`).not.toBe("");
      for (const part of ["plain_meaning", "calculation_summary", "scale_direction", "interpretation_boundary"] as const) {
        expect(entry, `${id}.${part}`).toContain(
          `data-explanation-part="${part}"${part === "interpretation_boundary" ? ' class="quantity-glossary__boundary"' : ""}>${escapeHtml(explanation[part])}</dd>`,
        );
      }
      expect(entry).toContain(`href="https://github.com/grunobuide/scoutlens/blob/main/${explanation.source_link}"`);
    }
  });

  it("refuses an id the registry does not define", () => {
    expect(() => renderToStaticMarkup(<QuantityGlossary ids={["no_such_quantity" as QuantityId]} />)).toThrow(
      ExplanationNotFoundError,
    );
  });

  it("tags an element with the ids it is given, space-separated", () => {
    expect(quantityTag("rank_interval", "resampled_recall")).toBe("rank_interval resampled_recall");
  });
});
