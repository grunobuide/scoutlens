"""`config_sha256` hashes raw bytes, and that is load-bearing (`D061`).

`scoutlens-jtt.19` asked whether the artifact `_manifest` digests should
identify *content* rather than the checkout's line endings. They should, in the
abstract. They cannot here, and this file is why: the raw-byte value is already
embedded in a published, content-addressed release asset.

The chain, each link verified below:

    config/experiment.json  --raw sha256-->  producer.config_sha256
      in public/showcase/v2/manifest.json
      --sha256 of that file-->  manifest_sha256 in config/showcase-payload-pack.json
      --pins-->  the published archive that `payload hydrate` downloads

Normalising the digest changes the first link, so every link after it moves.
The cost is a dataset re-release — a new archive, a new pin, and a new dataset
identity in the case study and the v1.0.0 release notes — to change a provenance
field's encoding. That is why this is pinned rather than fixed.

The release-candidate manifest (`scoutlens.release.manifest`) *does* normalise,
and that is not an inconsistency: it was introduced after the publication and
nothing downstream of it is content-addressed. The two live side by side on
purpose, and `digest_mode` on the newer one says which is which.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from scoutlens.evaluation.run_manifest import CONFIG_PATH, sha256_file
from scoutlens.release.manifest import REPO_ROOT

PUBLISHED_MANIFEST = REPO_ROOT / "public" / "showcase" / "v2" / "manifest.json"
PAYLOAD_PACK = REPO_ROOT / "config" / "showcase-payload-pack.json"

requires_published = pytest.mark.skipif(
    not PUBLISHED_MANIFEST.is_file(),
    reason="requires the published showcase manifest",
)


def _raw(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalised(path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _crlf(path) -> str:
    """The raw digest a Windows checkout produces, computed on any checkout."""
    lf = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest()


def test_the_run_manifest_hashes_raw_bytes() -> None:
    """The behaviour this file exists to pin.

    If this fails because someone normalised the digest, read the module
    docstring before "fixing" the test: the published archive depends on this
    value, and changing it is a re-release, not a refactor.
    """
    assert sha256_file(CONFIG_PATH) == _raw(CONFIG_PATH)


@requires_published
def test_the_published_manifest_carries_the_raw_value() -> None:
    """The first link, and the one that makes this irreversible.

    The published value is the raw digest *of a CRLF checkout* - the Windows
    machine that exported it. The first version of this test compared it with
    the raw digest of whatever checkout ran the test, which is the same claim
    only on Windows: it passed there and failed on every Linux CI run, turning
    `main` red. That is the platform dependence this file documents, caught in
    the test written to document it. So the comparison is made against the CRLF
    form of the content, which every checkout can compute; on a CRLF checkout it
    is also the raw digest, and that is asserted too.
    """
    published = json.loads(PUBLISHED_MANIFEST.read_text(encoding="utf-8"))
    assert published["producer"]["config_sha256"] == _crlf(CONFIG_PATH), (
        "the published showcase manifest no longer matches the raw digest of a "
        "CRLF checkout of config/experiment.json; either the config changed "
        "without a re-export, or the digest policy changed without regenerating "
        "the payload"
    )
    if b"\r\n" in CONFIG_PATH.read_bytes():
        assert _raw(CONFIG_PATH) == _crlf(CONFIG_PATH)


@requires_published
def test_the_published_manifest_is_the_pinned_one() -> None:
    """The rest of the chain: manifest -> pin -> published archive."""
    pack = json.loads(PAYLOAD_PACK.read_text(encoding="utf-8"))
    assert _raw(PUBLISHED_MANIFEST) == pack["manifest_sha256"], (
        "public/showcase/v2/manifest.json is not the file config/"
        "showcase-payload-pack.json pins, so the published archive and the "
        "working tree disagree about the dataset"
    )
    assert pack["archive"]["sha256"], "the pack must name the published archive"


def test_the_platform_dependence_is_real_and_measured() -> None:
    """Not a theoretical concern: the two values genuinely differ here.

    On a checkout where they happen to coincide — any Linux one, or a Windows
    one with `core.autocrlf` off — this asserts nothing, which is honest. The
    point is that *when* they differ, the difference is the line endings and
    nothing else.
    """
    raw, normalised = _raw(CONFIG_PATH), _normalised(CONFIG_PATH)
    if raw == normalised:
        pytest.skip("this checkout stores the config with LF, so there is nothing to show")

    payload = CONFIG_PATH.read_bytes()
    assert b"\r\n" in payload, "the digests differ, so CRLF is the only candidate cause"
    # Same JSON, same values, different bytes: the digest moved and nothing else did.
    assert json.loads(payload) == json.loads(payload.replace(b"\r\n", b"\n"))
    assert raw != normalised


def test_the_release_manifest_still_normalises_and_says_so() -> None:
    """The two policies coexist deliberately; the newer one declares itself."""
    from scoutlens.release.manifest import DIGEST_MODE, TEXT_SUFFIXES, _sha256

    assert ".json" in TEXT_SUFFIXES
    assert _sha256(CONFIG_PATH) == _normalised(CONFIG_PATH)
    assert "normalis" in DIGEST_MODE.lower(), (
        "the release manifest must keep declaring how it digests, so the two "
        "policies are never confused for each other"
    )
