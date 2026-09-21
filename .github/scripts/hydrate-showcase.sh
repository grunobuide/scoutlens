#!/usr/bin/env bash
# Hydrate the pinned showcase payload, retrying a transient download.
#
# The payload is a ~23 MB release asset, and GitHub's asset CDN sometimes
# answers 504. That was not hypothetical when this script was written: the
# first CI run of scoutlens-jtt.6.3 (#113) failed exactly that way, on an asset
# that was present and intact.
#
# Retries are safe here because hydration is content-addressed and verified:
# `payload hydrate` checks the archive's sha256 against
# config/showcase-payload-pack.json and refuses anything that does not match.
# A retry can therefore fetch a truncated or corrupted body and still fail
# closed -- what it cannot do is quietly hydrate the wrong data.
#
# Only the *download* is worth retrying. A bad pin, a missing asset or a digest
# mismatch fails identically every time, so this gives up quickly rather than
# spending two minutes confirming a permanent failure three times.
set -euo pipefail

ATTEMPTS=3
BACKOFF_SECONDS=10

for attempt in $(seq 1 "${ATTEMPTS}"); do
  if uv run --frozen python -m scoutlens.showcase.payload hydrate; then
    exit 0
  fi

  if [ "${attempt}" -eq "${ATTEMPTS}" ]; then
    break
  fi

  delay=$((BACKOFF_SECONDS * attempt))
  echo "::warning::showcase hydration attempt ${attempt}/${ATTEMPTS} failed; retrying in ${delay}s"
  sleep "${delay}"
done

echo "::error::showcase hydration failed after ${ATTEMPTS} attempts." >&2
echo "If this is a 504 from the release CDN it is transient - re-run the job." >&2
echo "If it is a digest mismatch the pin and the published asset disagree," >&2
echo "which is a stop condition, not something to re-run: see scoutlens-jtt." >&2
exit 1
