// Display formatting for resampled rank statistics (D046).
//
// Rank bounds come from percentile interpolation between order statistics, so
// they are legitimately fractional — the published artifact carries values like
// median 166.5 and interval 1–130.2, and 81% of published intervals have a
// non-integer bound. Interpolating them straight into a template prints the
// full binary expansion, because a value like 111.1 is not exactly
// representable in a double: "rank interval 1–111.09999999999991".
//
// One decimal place is the display precision. A trailing ".0" is trimmed so a
// whole rank reads as a whole number, which keeps every already-integer
// rendering byte-identical to before.
//
// Display only. The artifact is unchanged and remains the authority; nothing
// here rounds a stored value.

export function formatRank(value: number): string {
  const fixed = value.toFixed(1);
  return fixed.endsWith(".0") ? fixed.slice(0, -2) : fixed;
}

/** Same formatting where a bound may be absent; renders the em dash instead. */
export function formatRankBound(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : formatRank(value);
}
