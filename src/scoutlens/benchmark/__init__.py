"""Preregistered player-disjoint representation benchmark (scoutlens-qop).

The confirmatory benchmark that decides whether a learned fingerprint
representation earns its place over the frozen Baseline B cosine metric.
`scoutlens-qop.1` freezes the protocol; `qop.2`/`qop.3` run against it and
`qop.4` decides KEEP or DROP.

Nothing in this package fits a model. It defines the population, the
player-disjoint split, the frozen feature sets, the decision thresholds and
the fail-closed guard that keeps the test split shut until the protocol hash
is on the record.
"""
