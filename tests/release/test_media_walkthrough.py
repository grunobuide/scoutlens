"""The committed walkthrough is held to what the documents say about it.

`scoutlens-jtt.20`. `web/scripts/capture-demo.mjs` checks the scenes against the
live site while it records; that needs a browser and the network, so it runs
when someone captures, not in CI. What CI can check offline is that the files
committed afterwards are the ones described, and still have the properties the
bead asked for:

- AC1: the video is 60-90 seconds - read from the WebM container itself, not
  from the note or the plan;
- AC2: the captions are a well-formed WebVTT text track, within the video;
- AC3: the scenes cover fingerprint, retrieval, neighbors, uncertainty and a
  caveat, and the caption cues are exactly the scenes the note lists;
- AC4: the frame is the 2x size the legibility argument depends on;
- and the note's digests and source commit describe these files, so the note
  cannot drift away from the media the way `scoutlens-jtt.22` found the stills
  had.
"""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass

import pytest

from scoutlens.release.manifest import REPO_ROOT

MEDIA = REPO_ROOT / "docs" / "media"
VIDEO = MEDIA / "lab-walkthrough.webm"
CAPTIONS = MEDIA / "lab-walkthrough.vtt"
NOTE = MEDIA / "README.md"
CASE_STUDY = REPO_ROOT / "docs" / "case-study.md"
SCRIPT = REPO_ROOT / "web" / "scripts" / "capture-demo.mjs"

REQUIRED_SURFACES = {"fingerprint", "retrieval", "neighbors", "uncertainty", "caveat"}
#: The script refuses a caption faster than this; the committed track must agree.
MAX_WORDS_PER_SECOND = 3


# --- a minimal WebM reader -------------------------------------------------
#
# Enough EBML to read the segment duration and the video track's pixel size.
# The bundled ffmpeg can probe a file, but a CI test should not depend on a
# browser download to read two numbers out of a container.

SEGMENT = 0x18538067
INFO = 0x1549A966
TIMECODE_SCALE = 0x2AD7B1
DURATION = 0x4489
TRACKS = 0x1654AE6B
TRACK_ENTRY = 0xAE
CODEC_ID = 0x86
VIDEO_SETTINGS = 0xE0
PIXEL_WIDTH = 0xB0
PIXEL_HEIGHT = 0xBA


def _vint(data: bytes, pos: int, *, keep_marker: bool) -> tuple[int, int, bool]:
    first = data[pos]
    length = 1
    mask = 0x80
    while length <= 8 and not first & mask:
        mask >>= 1
        length += 1
    if length > 8:
        raise ValueError(f"invalid EBML variable-length integer at byte {pos}")
    value = first if keep_marker else first & (mask - 1)
    for byte in data[pos + 1 : pos + length]:
        value = (value << 8) | byte
    unknown = not keep_marker and value == (1 << (7 * length)) - 1
    return value, pos + length, unknown


def _children(data: bytes, start: int, end: int):
    pos = start
    while pos < end:
        element, pos, _ = _vint(data, pos, keep_marker=True)
        size, pos, unknown = _vint(data, pos, keep_marker=False)
        stop = end if unknown else pos + size
        yield element, pos, stop
        pos = stop


def _child(data: bytes, start: int, end: int, element: int) -> tuple[int, int]:
    for found, child_start, child_end in _children(data, start, end):
        if found == element:
            return child_start, child_end
    raise AssertionError(f"EBML element {element:#x} not found")


def _uint(data: bytes, start: int, end: int) -> int:
    return int.from_bytes(data[start:end], "big")


@dataclass(frozen=True)
class WebM:
    seconds: float
    width: int
    height: int
    codec: str


def read_webm(raw: bytes) -> WebM:
    segment = _child(raw, 0, len(raw), SEGMENT)
    info = _child(raw, *segment, INFO)
    scale = 1_000_000
    duration = None
    for element, start, end in _children(raw, *info):
        if element == TIMECODE_SCALE:
            scale = _uint(raw, start, end)
        elif element == DURATION:
            duration = struct.unpack(">f" if end - start == 4 else ">d", raw[start:end])[0]
    assert duration is not None, "the WebM records no duration"
    tracks = _child(raw, *segment, TRACKS)
    entry = _child(raw, *tracks, TRACK_ENTRY)
    codec = raw[slice(*_child(raw, *entry, CODEC_ID))].decode("ascii")
    video = _child(raw, *entry, VIDEO_SETTINGS)
    return WebM(
        seconds=duration * scale / 1e9,
        width=_uint(raw, *_child(raw, *video, PIXEL_WIDTH)),
        height=_uint(raw, *_child(raw, *video, PIXEL_HEIGHT)),
        codec=codec,
    )


# --- a minimal WebVTT reader -----------------------------------------------

TIMING = re.compile(
    r"^(\d{2}):([0-5]\d):([0-5]\d)\.(\d{3}) --> (\d{2}):([0-5]\d):([0-5]\d)\.(\d{3})$"
)


@dataclass(frozen=True)
class Cue:
    id: str
    start: float
    end: float
    text: str


def _seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def read_webvtt(text: str) -> tuple[str, list[Cue]]:
    blocks = [block.split("\n") for block in text.strip("\n").split("\n\n")]
    header = "\n".join(blocks[0])
    assert blocks[0][0] == "WEBVTT", "a WebVTT file must start with WEBVTT"
    cues = []
    for lines in blocks[1:]:
        if lines[0].startswith("NOTE"):
            header += "\n" + "\n".join(lines)
            continue
        timing_at = 0 if TIMING.match(lines[0]) else 1
        assert timing_at < len(lines), f"cue without timing: {lines!r}"
        match = TIMING.match(lines[timing_at])
        assert match, f"malformed cue timing: {lines[timing_at]!r}"
        for line in lines[:timing_at] + lines[timing_at + 1 :]:
            # A browser reads "<" and "&" as cue markup and drops what follows.
            assert not re.search(r"[<&]|-->", line), f"unescaped WebVTT markup in {line!r}"
        cues.append(
            Cue(
                id=lines[0] if timing_at == 1 else "",
                start=_seconds(*match.groups()[:4]),
                end=_seconds(*match.groups()[4:]),
                text=" ".join(lines[timing_at + 1 :]),
            )
        )
    return header, cues


# --- the script's scene table, read as text ---------------------------------
#
# Not executed - it needs a browser - but read, so the committed captions can
# be checked against the table that is supposed to have written them.


@dataclass(frozen=True)
class Scene:
    id: str
    surfaces: frozenset[str]
    expect: tuple[str, ...]
    caption: str


STRING = r'"((?:[^"\\]|\\.)*)"'


def read_scene_table(source: str) -> list[Scene]:
    table = source.split("const SCENES = [", 1)[1].split("\n];", 1)[0]
    scenes = []
    for block in re.split(r"\n  \{\n", table)[1:]:
        surfaces = re.search(r"surfaces: \[([^\]]*)\]", block)
        expect = re.search(r"expect: \[(.*?)\]", block, flags=re.DOTALL)
        caption = re.search(r"caption:\s*" + STRING, block)
        identifier = re.search(r'id: "([^"]+)"', block)
        assert surfaces and expect and caption and identifier, f"unreadable scene:\n{block}"
        scenes.append(
            Scene(
                id=identifier.group(1),
                surfaces=frozenset(re.findall(STRING, surfaces.group(1))),
                expect=tuple(re.findall(STRING, expect.group(1))),
                caption=caption.group(1),
            )
        )
    assert scenes, "the script has no scene table"
    return scenes


#: The script's figure rule, ported: digits taken whole, so "4" is not "43.5".
FIGURE = re.compile(r"\d[\d,.]*(?:[–/-]\d[\d,.]*)?%?")


def figures(value: str) -> set[str]:
    return {token.rstrip(".,") for token in FIGURE.findall(value)}


# --- fixtures ----------------------------------------------------------------


@pytest.fixture(scope="module")
def scenes() -> list[Scene]:
    return read_scene_table(SCRIPT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def video() -> WebM:
    return read_webm(VIDEO.read_bytes())


@pytest.fixture(scope="module")
def captions() -> tuple[str, list[Cue]]:
    # Bytes, not text mode: the digest below is over the committed bytes, and a
    # CRLF checkout would be a different file (`.gitattributes` pins LF).
    return read_webvtt(CAPTIONS.read_bytes().decode("utf-8"))


@pytest.fixture(scope="module")
def note() -> str:
    return NOTE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def scene_table(note: str) -> dict[str, set[str]]:
    """The note's cue table: scene id -> the surfaces it shows."""
    rows = re.findall(r"^\| `([a-z-]+)` \| ([a-z, ]+) \|", note, flags=re.MULTILINE)
    assert rows, "the media note has no walkthrough cue table"
    return {cue: {surface.strip() for surface in shows.split(",")} for cue, shows in rows}


# --- AC1, AC4: the video ------------------------------------------------------


def test_the_video_is_sixty_to_ninety_seconds(video: WebM) -> None:
    assert 60 <= video.seconds <= 90, f"the walkthrough is {video.seconds:.2f}s"


def test_the_video_is_the_2x_frame_the_legibility_argument_needs(video: WebM) -> None:
    """800x540 CSS pixels at 2x. A 1x picture padded to this size - what
    Playwright's `recordVideo` produced - would also be 1600x1080, which is why
    the script asserts every screenshot's own size before encoding it; this
    checks the container agrees."""
    assert (video.width, video.height) == (1600, 1080)
    assert video.codec == "V_VP8"


def test_the_note_states_the_length_the_file_has(video: WebM, note: str) -> None:
    assert f"{video.seconds:.2f} s" in note, "the note's length is not the file's"
    rounded = f"{round(video.seconds)}-second"
    assert rounded in note, f"the note does not call it a {rounded} walkthrough"
    assert rounded in CASE_STUDY.read_text(encoding="utf-8"), (
        f"the case study does not call it a {rounded} walkthrough"
    )


def test_the_frame_geometry_is_the_one_the_capture_recorded(
    captions: tuple[str, list[Cue]], video: WebM, note: str
) -> None:
    """AC4: the viewport and the scaling, written by the script at capture time.

    The container alone cannot tell a 2x screenshot from a 1x picture padded to
    the same size. The caption header records the viewport and scale the
    capture used, and the smallest text it asserted, so the legibility argument
    in the note is tied to numbers the capture produced rather than retyped.
    """
    header, _ = captions
    frame = re.search(r"Frame: (\d+)x(\d+) CSS px at (\d+)x = (\d+)x(\d+)", header)
    assert frame, "the caption header does not record the frame geometry"
    css_w, css_h, scale, out_w, out_h = map(int, frame.groups())
    assert (css_w * scale, css_h * scale) == (out_w, out_h) == (video.width, video.height)
    smallest = re.search(r"Smallest asserted text: (\d+\.\d) px in an (\d+) px embed", header)
    assert smallest, "the caption header does not record the smallest asserted text"
    assert float(smallest.group(1)) >= 10, "text below the 10 px floor reached the video"
    assert f"renders at {smallest.group(1)} px there" in " ".join(note.split())
    assert f"{css_w}×{css_h} CSS px" in note


# --- AC2, AC3: the captions -----------------------------------------------------


def test_the_cues_are_ordered_and_inside_the_video(
    captions: tuple[str, list[Cue]], video: WebM
) -> None:
    _, cues = captions
    assert cues, "the caption track has no cues"
    previous_end = 0.0
    for cue in cues:
        assert cue.text, f"cue {cue.id} is empty"
        assert previous_end <= cue.start < cue.end, f"cue {cue.id} overlaps or runs backwards"
        previous_end = cue.end
    assert previous_end <= video.seconds + 0.001, "a caption outlasts the video"


def test_every_cue_is_readable_in_the_time_it_is_shown(captions: tuple[str, list[Cue]]) -> None:
    _, cues = captions
    for cue in cues:
        rate = len(cue.text.split()) / (cue.end - cue.start)
        assert rate <= MAX_WORDS_PER_SECOND, f"cue {cue.id} asks for {rate:.1f} words a second"


def test_the_cues_are_exactly_the_scenes_the_note_lists(
    captions: tuple[str, list[Cue]], scene_table: dict[str, set[str]]
) -> None:
    _, cues = captions
    assert [cue.id for cue in cues] == list(scene_table)


def test_the_scenes_cover_every_surface_ac3_names(scene_table: dict[str, set[str]]) -> None:
    shown = set().union(*scene_table.values())
    assert REQUIRED_SURFACES <= shown, f"not shown: {sorted(REQUIRED_SURFACES - shown)}"


# --- AC1: produced by the committed script ------------------------------------


def test_the_captions_are_the_ones_the_committed_script_writes(
    captions: tuple[str, list[Cue]], scenes: list[Scene]
) -> None:
    """A caption edited by hand, or a script changed without a re-capture, both
    leave the committed track describing something the script no longer does."""
    header, cues = captions
    assert "web/scripts/capture-demo.mjs" in header and SCRIPT.is_file()
    assert [(cue.id, cue.text) for cue in cues] == [(scene.id, scene.caption) for scene in scenes]


def test_the_note_lists_the_surfaces_the_script_declares(
    scenes: list[Scene], scene_table: dict[str, set[str]]
) -> None:
    assert {scene.id: set(scene.surfaces) for scene in scenes} == scene_table


def test_every_figure_a_caption_writes_is_asserted_on_screen(scenes: list[Scene]) -> None:
    """The script's own guard, re-run on the committed table: the video is
    illustration, never the source of a number."""
    for scene in scenes:
        unasserted = figures(scene.caption) - figures(" ".join(scene.expect))
        assert not unasserted, f"{scene.id} captions {sorted(unasserted)} without asserting them"


def test_no_caption_calls_the_weighted_score_a_cosine(captions: tuple[str, list[Cue]]) -> None:
    """D047. The site still says "cosine" in one drawer (`scoutlens-uze.25`);
    the captions must not repeat it."""
    _, cues = captions
    for cue in cues:
        assert "cosine" not in cue.text.lower(), f"cue {cue.id} says cosine"


# --- provenance -----------------------------------------------------------------


def test_the_note_records_the_digests_of_the_committed_files(note: str) -> None:
    for path in (VIDEO, CAPTIONS):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert f"{digest}  {path.name}" in note, (
            f"the note does not record the current digest of {path.name}; "
            f"the committed file hashes to {digest}"
        )


def test_the_captions_and_the_note_name_the_same_deployed_commit(
    captions: tuple[str, list[Cue]], note: str
) -> None:
    header, _ = captions
    commits = re.findall(r"deployed commit ([0-9a-f]{40})", header)
    assert len(commits) == 1, "the caption header does not name the deployed commit"
    walkthrough = note.split("## Walkthrough", 1)[1]
    assert f"`{commits[0]}`" in walkthrough, "the note's provenance names a different commit"
