import { describe, expect, it } from "vitest";

import { formatRank, formatRankBound } from "@/components/rank-format";

// scoutlens-jtt.16 / D046. Rank bounds come from percentile interpolation and
// are legitimately fractional; rendering them raw printed the full binary
// expansion in the published Lab.

describe("formatRank", () => {
  it("collapses binary noise to one decimal place", () => {
    // The exact doubles observed in the published artifact.
    expect(formatRank(111.09999999999991)).toBe("111.1");
    expect(formatRank(91.57499999999993)).toBe("91.6");
    expect(formatRank(422.0999999999999)).toBe("422.1");
  });

  it("leaves whole ranks looking whole", () => {
    // Every already-integer rendering must be byte-identical to before the fix.
    expect(formatRank(1)).toBe("1");
    expect(formatRank(16)).toBe("16");
    expect(formatRank(1257)).toBe("1257");
  });

  it("keeps a clean fractional value intact", () => {
    expect(formatRank(130.2)).toBe("130.2");
    expect(formatRank(166.5)).toBe("166.5");
    expect(formatRank(6.4)).toBe("6.4");
  });

  it("rounds rather than truncates", () => {
    expect(formatRank(9.46)).toBe("9.5");
    expect(formatRank(9.44)).toBe("9.4");
  });

  it("drops a decimal that rounds away", () => {
    expect(formatRank(111.04)).toBe("111");
  });

  it("never emits an exponent or more than one decimal", () => {
    for (const value of [1, 6.4, 9.5, 111.09999999999991, 422.0999999999999, 1257]) {
      const rendered = formatRank(value);
      expect(rendered).not.toContain("e");
      const [, decimals = ""] = rendered.split(".");
      expect(decimals.length).toBeLessThanOrEqual(1);
    }
  });
});

describe("formatRankBound", () => {
  it("formats a present bound like formatRank", () => {
    expect(formatRankBound(111.09999999999991)).toBe("111.1");
    expect(formatRankBound(16)).toBe("16");
  });

  it("renders an em dash when the bound is absent", () => {
    expect(formatRankBound(null)).toBe("—");
    expect(formatRankBound(undefined)).toBe("—");
  });

  it("does not treat zero as absent", () => {
    expect(formatRankBound(0)).toBe("0");
  });
});
