"""Compute the release-candidate manifest.

    uv run --frozen python -m scoutlens.release.manifest

Prints canonical JSON naming every identity a reviewer needs to know what is
being frozen: the code commit and whether the tree was clean, the schema and
contract versions, the dataset version and its content-addressed pin, the
digests of the versioned configs, and the dependency lock identities for both
toolchains.

**It writes nothing and freezes nothing.** The output is recorded by hand into
`docs/release-candidate-v1.md`, because a candidate is a decision about a
specific commit and a decision a script can take by accident is a decision
nobody made.

**Digests, not timestamps.** Everything here is content-addressed or read from a
versioned file, so two runs on the same commit and the same tree agree. The one
field that cannot be: `git.dirty`, which is a fact about the working tree rather
than the commit, and is recorded precisely so a manifest taken from a dirty tree
cannot pass as one taken from a clean one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scoutlens.console import use_utf8_output
from scoutlens.explanations.adapters.protocol import ADAPTER_PROTOCOL_VERSION
from scoutlens.explanations.evals.corpus import CORPUS_VERSION
from scoutlens.explanations.policy import BUNDLE_SCHEMA_VERSION, OUTPUT_SCHEMA_VERSION
from scoutlens.explanations.prompt import PROMPT_CONTRACT_VERSION
from scoutlens.showcase.io import canonical_json_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Versioned inputs whose exact bytes decide what the pipeline computed.
CONFIG_FILES = (
    "config/experiment.json",
    "config/uncertainty.json",
    "config/uncertainty-diagonal.json",
    "config/showcase-payload-pack.json",
)

#: Dependency locks. Both toolchains, because the site and the science ship together.
LOCK_FILES = (
    "uv.lock",
    "pyproject.toml",
    "web/pnpm-lock.yaml",
    "web/package.json",
    "web/.node-version",
)

#: Published artifacts a reviewer should be able to pin independently.
ARTIFACT_FILES = (
    "public/showcase/v2/manifest.json",
    "public/showcase/v2/representation.json",
    "public/showcase/v2/players.index.json",
    "public/showcase/v2/feature-catalog.json",
    "public/showcase/v2/research-summary.json",
    "artifacts/ai-evals/grounded-explanations-v1.json",
)


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        return ""


def _digests(names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: _sha256(REPO_ROOT / name) for name in names}


def _project_version() -> str:
    import tomllib

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _showcase_identity() -> dict[str, Any]:
    manifest_path = REPO_ROOT / "public" / "showcase" / "v2" / "manifest.json"
    if not manifest_path.is_file():
        return {"available": False}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "contract": manifest.get("contract"),
        "schema_version": manifest.get("schema_version"),
        "dataset_version": manifest.get("dataset_version"),
        "representation_id": manifest.get("representation_id"),
    }


def _payload_pin() -> dict[str, Any]:
    pin_path = REPO_ROOT / "config" / "showcase-payload-pack.json"
    if not pin_path.is_file():
        return {"available": False}
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    archive = pin.get("archive", {})
    return {
        "available": True,
        "dataset_version": pin.get("dataset_version"),
        "schema_version": pin.get("schema_version"),
        "showcase_schema_version": pin.get("showcase_schema_version"),
        "archive_sha256": archive.get("sha256"),
        "archive_bytes": archive.get("bytes"),
        "path_count": pin.get("path_count"),
        "representation": pin.get("representation"),
    }


def build_manifest() -> dict[str, Any]:
    """Every identity that decides what this candidate is."""
    status = _git("status", "--porcelain")
    return {
        "contract": "scoutlens.release-candidate",
        "schema_version": "1.0.0",
        "generated_by": "uv run --frozen python -m scoutlens.release.manifest",
        "project_version": _project_version(),
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            # A fact about the tree, not the commit. Recorded so a manifest taken
            # from a dirty tree cannot pass as one taken from a clean one.
            "dirty": bool(status),
            "dirty_paths": sorted(line[3:] for line in status.splitlines()) if status else [],
        },
        "contracts": {
            "showcase": _showcase_identity(),
            "explanation_bundle_schema": BUNDLE_SCHEMA_VERSION,
            "explanation_output_schema": OUTPUT_SCHEMA_VERSION,
            "prompt_contract": PROMPT_CONTRACT_VERSION,
            "adapter_protocol": ADAPTER_PROTOCOL_VERSION,
            "eval_corpus": CORPUS_VERSION,
        },
        "payload_pin": _payload_pin(),
        "config_digests": _digests(CONFIG_FILES),
        "dependency_digests": _digests(LOCK_FILES),
        "artifact_digests": _digests(ARTIFACT_FILES),
        "runtime": {
            "requires_python": ">=3.11",
            "ci_python_versions": ["3.11", "3.14"],
            "node_version_file": (REPO_ROOT / "web" / ".node-version").read_text(encoding="utf-8").strip()
            if (REPO_ROOT / "web" / ".node-version").is_file()
            else None,
        },
    }


def manifest_digest(manifest: dict[str, Any]) -> str:
    """Digest over everything except the tree-state fields.

    `git.dirty` and `dirty_paths` describe the working copy rather than the
    candidate, so including them would make the digest of a commit depend on who
    happened to have an editor open. The commit itself stays in.
    """
    stable = json.loads(json.dumps(manifest))
    stable["git"].pop("dirty", None)
    stable["git"].pop("dirty_paths", None)
    return hashlib.sha256(canonical_json_bytes(stable)).hexdigest()


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args(argv)

    manifest = build_manifest()
    manifest["manifest_digest"] = manifest_digest(manifest)
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        sys.stdout.write(rendered)

    if manifest["git"]["dirty"]:
        print(
            "\nWARNING: the working tree is dirty, so this manifest does not describe "
            "a reproducible commit. A release candidate is frozen from a clean tree.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
