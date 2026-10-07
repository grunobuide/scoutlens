/**
 * The forbidden-copy lists, shared by every surface that scans public text.
 *
 * `scoutlens-9a3.7` AC5 put these in `check-static-output.mjs`, which scans
 * the three prerendered routes. `scoutlens-9a3.29` moved them here because the
 * identity challenge's query, reveal and evidence states render on the client:
 * their text is not in any prerendered route, so the static check never saw
 * it. One list, imported by the static check, a vitest over the challenge view
 * and an e2e over the rendered states, so the three cannot drift apart.
 */

/**
 * Assertive phrasings of what the project may never claim, banned outside the
 * published claim boundaries (`research-summary.json`'s `unsupported_claims`).
 *
 * Each is the *affirmative* form. The negated forms the site does use - "not
 * proof of playing style", "it does not measure player quality, tactical fit or
 * recruitment value", "not a scouting model" - do not contain these substrings,
 * which is why the list is phrased this way rather than banning the topic
 * words. Banning "playing style" or "recruitment" outright would flag the
 * caveats, and a check that fights the caveats teaches people to delete them.
 *
 * The player-quality entries (`scoutlens-9a3.29`) follow the same rule. The
 * site says "not a player rating", "never a quality rating", "not quality
 * scores", "not a position-quality score" and - in every feature definition -
 * "not interpreted as better player quality". So the entries name the
 * assertion with its verb or its value ("is a better player", "player rating
 * of", "quality score of"), never the bare noun phrase, which every one of
 * those disclaimers contains. A direct negation ("is not a better player")
 * stays clean; an indirect one ("does not say whether he is a better player")
 * would trip, and should be reworded or published as a claim boundary.
 */
export const forbiddenClaims = [
  "proves playing style",
  "proven playing style",
  "similar playing style",
  "same playing style",
  "should sign",
  "should recruit",
  "recommended signing",
  "recommended transfer",
  "ideal replacement",
  "best replacement",
  "predicts transfer success",
  "predicts future performance",
  // scoutlens-9a3.29: player quality.
  "is a better player",
  "is the better player",
  "is the better of the two",
  "is the best player",
  "outperforms as a player",
  "player rating of",
  "quality score of",
  "talent grade of",
  "is rated as",
  "are rated as",
  "is a top prospect",
  "is an elite player",
  "is world-class",
  "is a world-class",
];

/**
 * Wording that would tell a reader the data is live.
 *
 * Q1 of `docs/public-understanding-check.md` blocks the gate if a reviewer
 * believes the data is current, and this is the machine-checkable half of that.
 * Every entry currently has zero occurrences across all three routes; they are
 * here to catch a future copy change, not to describe today's text. Note the
 * site legitimately writes "no live database", "no live LLM is required for any
 * current page" and "it is not current scouting information" - none of which
 * contain these phrases, which is why they are this specific.
 *
 * Matched on a trailing word boundary, not as a bare substring. The first run
 * of this check failed on `/science/` because "no live database" contains
 * "live data", and the sentence it flagged is the site correctly saying it has
 * no live database. A ban that fires on the disclaimer is worse than no ban:
 * the cheapest way to make it pass is to delete the reassurance.
 */
export const forbiddenCurrentness = [
  "real-time",
  "real time data",
  "live data",
  "up to date",
  "up-to-date",
  "current season",
  "this season's",
  "latest data",
  "latest season",
  "continuously updated",
  "updated daily",
  "updated weekly",
  "updated automatically",
];

/**
 * The text a scan reads: every published claim boundary removed, lower-cased.
 *
 * Removal is by exact string, so the disclaimers cannot satisfy - or trip - a
 * ban on the thing they disclaim. The boundaries render inside a single
 * element, so they survive as contiguous text in HTML and in `innerText`.
 */
export function scannableText(text, unsupportedClaims) {
  let scannable = text;
  for (const claim of unsupportedClaims) {
    scannable = scannable.split(claim).join(" ");
  }
  return scannable.toLowerCase();
}

/** The `forbiddenClaims` entries present in already-scannable text, as substrings. */
export function findForbiddenClaims(scannable) {
  return forbiddenClaims.filter((forbidden) => scannable.includes(forbidden));
}

/** The `forbiddenCurrentness` entries present in already-scannable text, on a trailing word boundary. */
export function findForbiddenCurrentness(scannable) {
  return forbiddenCurrentness.filter((forbidden) =>
    new RegExp(`${forbidden.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(scannable),
  );
}
