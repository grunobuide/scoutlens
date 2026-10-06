import { BOUNDARY, THESIS } from "@/content/narrative";

/**
 * The thesis and its boundary, as two adjacent paragraphs (`scoutlens-9a3.18`).
 *
 * A server component with no wrapper of its own, so each route keeps its own
 * typography by class name while every route prints the same two sentences in
 * the same order. Nothing may sit between them: section 2 of the narrative
 * makes the boundary part of the thesis, not a footnote to it.
 */
export function ThesisStatement({
  thesisClassName,
  boundaryClassName,
}: {
  thesisClassName: string;
  boundaryClassName: string;
}) {
  return (
    <>
      <p className={thesisClassName} data-thesis>
        {THESIS}
      </p>
      <p className={boundaryClassName} data-thesis-boundary>
        {BOUNDARY}
      </p>
    </>
  );
}
