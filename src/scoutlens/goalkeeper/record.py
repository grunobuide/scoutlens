"""Results recorded inside their evidence document, between markers.

`artifacts/` is ignored by allowlist and a modeling bead may not widen it, so
the goalkeeper gates keep their recorded runs in the evidence documents they
are reported in. A block is everything between a begin and an end marker on
their own lines; `replace` rewrites only those blocks and leaves the prose
around them alone.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

Markers = tuple[str, str]


def markers(name: str) -> Markers:
    return (f"<!-- {name}:begin -->", f"<!-- {name}:end -->")


def read(path: Path, block: Markers) -> str:
    begin, end = block
    text = path.read_text(encoding="utf-8")
    match = re.search(re.escape(begin) + r"\n(.*?)" + re.escape(end), text, flags=re.DOTALL)
    if match is None:
        raise ValueError(f"{path.name} has no {begin} ... {end} block")
    return match.group(1)


def read_json(path: Path, block: Markers) -> dict:
    body = read(path, block)
    return json.loads(body.removeprefix("```json\n").removesuffix("```\n"))


def json_body(value: dict) -> str:
    return "```json\n" + json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n```\n"


def replace(path: Path, bodies: dict[Markers, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for (begin, end), body in bodies.items():
        pattern = re.escape(begin) + r"\n.*?" + re.escape(end)
        if re.search(pattern, text, flags=re.DOTALL) is None:
            raise ValueError(f"{path.name} has no {begin} ... {end} block")
        replacement = f"{begin}\n{body}{end}"
        text = re.sub(pattern, lambda _match: replacement, text, count=1, flags=re.DOTALL)
    path.write_text(text, encoding="utf-8", newline="\n")
