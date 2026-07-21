# notebooks/

Exploratory only. The rule (see
[`../docs/project-charter.md`](../docs/project-charter.md)):

> Notebooks ask questions. Modules produce answers reproducibly.

A notebook here may explore distributions, visualize specific cases, or
test a hypothesis quickly. It must not be the canonical implementation of
ingestion, minutes reconstruction, feature engineering, splitting,
similarity, or metrics — that logic belongs in `src/scoutlens/`, covered by
tests, and imported into the notebook. Not populated yet — profiling and
validation so far have been done directly against `src/` modules.
