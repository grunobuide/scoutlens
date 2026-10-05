"""Goalkeeper-specific fingerprint family (`scoutlens-e87`).

The frozen 32-feature catalog is outfield-oriented, and the published caveat
`goalkeeper_feature_coverage_weak` says so. This package asks, in two gates,
whether the Wyscout event schema can do better for goalkeepers:

- **Gate 1 - observability** (`observability`): can at least three
  conceptually distinct goalkeeper behaviours be measured *directly*, with
  auditable event/tag denominators and enough support per goalkeeper-period?
  If not, the issue closes `NO_GO_OBSERVABILITY` without implementation.
- **Gate 2 - retrieval** (`protocol`): on GO, does adding the family to the
  frozen catalog improve goalkeeper identity retrieval enough to keep?

Gate 2's formulas, denominators, null handling, minimum support and decision
rule are frozen in `protocol.PROTOCOL` and must be on the decision ledger by
hash before any retrieval outcome is computed.

Nothing here changes the published catalog, the showcase artifacts or any
recorded result. A KEEP would do that, atomically, in its own change.
"""
