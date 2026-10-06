/**
 * The one thesis and the one boundary sentence (`scoutlens-9a3.18`, D066).
 *
 * Frozen in docs/public-experience-narrative.md section 2 and rendered,
 * verbatim and adjacent, on the landing hero, the /science orientation and the
 * /lab intro. Each route used to word its own: three theses and three
 * boundaries, so the sentence a reader carried away depended on where they
 * came in.
 *
 * The only difference from the frozen text is the project's display name:
 * section 2 was written as "ScoutLens", and the public identity contract
 * permits that substitution and no other ("a name substitution only").
 * tests/narrative.test.ts holds these two strings to the document, so neither
 * can be edited here without the narrative owner editing section 2 first.
 */

export const DISPLAY_NAME = "Yumusarái Labs";

export const THESIS =
  "On the pitch, a player's actions leave a stable statistical fingerprint; " +
  `${DISPLAY_NAME} shows that fingerprint can find that same player again across two ` +
  "halves of one season — and shows the limits of that evidence rather than hiding them.";

/** Must render immediately after `THESIS`, with nothing between them (section 2). */
export const BOUNDARY =
  "This is evidence of individual signal — not proof of playing style, not a " +
  "recommendation, and not a prediction.";
