"""Make command output able to carry the characters in the data.

A Windows console defaults to cp1252. The published data contains players
called Areola and Barak with their diacritics intact, the research copy uses em
dashes, and this repository is developed on Windows — so a command that prints
either dies with `UnicodeEncodeError` on the platform it was written on, and
nowhere else.

Reconfiguring is the fix rather than stripping the characters: a tool that
quietly renamed people, or flattened punctuation, to make its own output easier
would be a worse bug than the crash. `errors="replace"` keeps a genuinely
undecodable terminal from turning a display problem into a failure.

One definition, because there are now several entry points and a per-module
copy is a per-module chance to forget.
"""

from __future__ import annotations

import sys


def use_utf8_output() -> None:
    """Reconfigure stdout and stderr to UTF-8, tolerating streams that cannot."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # pragma: no cover - not a real tty
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - closed or oddly redirected
            pass


__all__ = ["use_utf8_output"]
