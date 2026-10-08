import type { ResearchExperiment, ResearchMetric } from "@/contracts/generated/showcase";
import { explainMetric, explainQuantity, type QuantityId } from "@/content/evidence-explanations";

const repositoryRoot = "https://github.com/grunobuide/scoutlens/blob/main/";

/**
 * The `data-quantity` value for an element that prints one or more registry
 * quantities. Typed, so a surface cannot tag a number with an id the registry
 * does not define.
 */
export function quantityTag(...ids: ReadonlyArray<QuantityId>): string {
  return ids.join(" ");
}

/**
 * The `data-metric` value for an element that prints research metrics
 * (`scoutlens-9a3.32`): `experiment_id:metric_id`, the key the registry's
 * per-experiment explanations use, because one metric id can mean a different
 * population on another experiment.
 */
export function metricTag(
  ...items: ReadonlyArray<{ experiment: Pick<ResearchExperiment, "experiment_id">; metric: Pick<ResearchMetric, "metric_id"> }>
): string {
  return items.map(({ experiment, metric }) => `${experiment.experiment_id}:${metric.metric_id}`).join(" ");
}

/**
 * What the research metrics a section prints mean (`scoutlens-9a3.32`).
 *
 * The same disclosure as {@link QuantityGlossary}, over the metric registry:
 * each entry is `explainMetric` for that metric as its own experiment computed
 * it, all five parts, so a section that quotes a metric outside its experiment
 * card - the landing hero's confound - explains it where it is quoted.
 */
export function MetricGlossary({
  items,
}: {
  items: ReadonlyArray<{ experiment: Pick<ResearchExperiment, "experiment_id">; metric: ResearchMetric }>;
}) {
  const entries = items.map(({ experiment, metric }) => ({
    tag: metricTag({ experiment, metric }),
    term: metric.label,
    explanation: explainMetric(metric, experiment.experiment_id),
  }));
  return (
    <details className="quantity-glossary" data-quantity-glossary>
      <summary>
        What these numbers mean:{" "}
        <span className="quantity-glossary__terms">{entries.map((entry) => entry.term).join(", ")}</span>
      </summary>
      <dl>
        {entries.map(({ tag, term, explanation }) => (
          <div key={tag} data-metric-explainer={tag}>
            <dt>{term}</dt>
            <dd data-explanation-part="plain_meaning">{explanation.plain_meaning}</dd>
            <dd data-explanation-part="calculation_summary">{explanation.calculation_summary}</dd>
            <dd data-explanation-part="scale_direction">{explanation.scale_direction}</dd>
            <dd data-explanation-part="interpretation_boundary" className="quantity-glossary__boundary">
              {explanation.interpretation_boundary}
            </dd>
            <dd data-explanation-part="source_link">
              <a href={`${repositoryRoot}${explanation.source_link}`}>
                Method source: {explanation.source_link.split("#", 1)[0]?.replace(/^docs\//, "")}
              </a>
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

/**
 * What the numbers in one section mean (`scoutlens-9a3.19`).
 *
 * One native disclosure per section, listing every quantity the section
 * prints. The summary is the inline variant and names each term; the expanded
 * body is the registry record, verbatim, so what a sighted, keyboard or
 * screen-reader user can reach is the same text by the same route - a
 * `<summary>` is focusable and toggles with Enter or Space, and nothing here
 * depends on hover.
 *
 * Every id resolves through `explainQuantity`, which throws for an unknown one:
 * a section cannot ship a number whose explanation is missing.
 */
export function QuantityGlossary({ ids }: { ids: ReadonlyArray<QuantityId> }) {
  const explanations = ids.map((id) => explainQuantity(id));
  return (
    <details className="quantity-glossary" data-quantity-glossary>
      <summary>
        What these numbers mean:{" "}
        <span className="quantity-glossary__terms">
          {explanations.map((explanation) => explanation.term).join(", ")}
        </span>
      </summary>
      <dl>
        {explanations.map((explanation) => (
          <div key={explanation.key} data-quantity-explainer={explanation.key}>
            <dt>{explanation.term}</dt>
            <dd data-explanation-part="plain_meaning">{explanation.plain_meaning}</dd>
            <dd data-explanation-part="calculation_summary">{explanation.calculation_summary}</dd>
            <dd data-explanation-part="scale_direction">{explanation.scale_direction}</dd>
            <dd data-explanation-part="interpretation_boundary" className="quantity-glossary__boundary">
              {explanation.interpretation_boundary}
            </dd>
            <dd data-explanation-part="source_link">
              <a href={`${repositoryRoot}${explanation.source_link}`}>
                Method source: {explanation.source_link.split("#", 1)[0]?.replace(/^docs\//, "")}
              </a>
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
