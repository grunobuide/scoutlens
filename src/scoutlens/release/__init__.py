"""Release-candidate identity: what exactly is being frozen.

`scoutlens-jtt.7.1` asks for a manifest recording the code, schema, dataset,
config, input and dependency identities of one candidate. `manifest` computes
it, so the answer comes from the tree rather than from someone's memory of it.

It computes and prints. It freezes nothing, tags nothing and publishes nothing —
those are decisions, and a decision a script can take by accident is a decision
nobody made.

`manifest` is deliberately **not** re-exported here. Importing it from this
`__init__` makes `python -m scoutlens.release.manifest` emit a `RuntimeWarning`
about a double import, and that command is the one this project tells a reviewer
to run. `scoutlens.explanations.adapters` records the same trap for the same
reason. Import from the module.
"""

from __future__ import annotations

__all__: list[str] = []
