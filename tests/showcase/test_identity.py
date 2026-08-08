import pytest

from scoutlens.showcase.builder import normalize_identity_text
from scoutlens.showcase.validation import _validate_identity_text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("L. Modri\\u0107", "L. Modrić"),
        ("\\u00c1. Correa", "Á. Correa"),
        ("Atl\\u00e9tico Madrid", "Atlético Madrid"),
        ("K. Sig\\u00fe\\u00f3rsson", "K. Sigþórsson"),
        ("plain name", "plain name"),
        ("", ""),
        ("no backslash here", "no backslash here"),
    ],
)
def test_normalize_identity_text_decodes_valid_escapes(value: str, expected: str) -> None:
    assert normalize_identity_text(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "C:\\work\\reports",
        "trailing backslash \\",
        "\\uzzzz",
        "mailto:user@example.com",
        "mixed \\u12G4 hex",
        "\\u00",  # incomplete escape
        "\\u000G",  # non-hex digit
    ],
)
def test_normalize_identity_text_preserves_ordinary_backslashes_and_malformed_text(value: str) -> None:
    assert normalize_identity_text(value) == value


def test_normalize_identity_text_leaves_unicode_characters_untouched() -> None:
    assert normalize_identity_text("Modrić · İstanbul") == "Modrić · İstanbul"


@pytest.mark.parametrize(
    ("item", "base"),
    [
        ({"display_name": "L. Modri\\u0107", "competition": None}, "i"),
        (
            {
                "display_name": "A. Player",
                "competition": {"name": "Spanish first division", "country": "Spain"},
                "period_contexts": {
                    "a": {"teams": [{"name": "Atl\\u00e9tico Madrid"}]},
                    "b": {"teams": [{"name": "Atl\\u00e9tico Madrid"}]},
                },
            },
            "i",
        ),
        (
            {
                "display_name": "A. Player",
                "competition": {"name": "Sp\\u00e0nish first division", "country": "Spain"},
                "period_contexts": {},
            },
            "i",
        ),
        (
            {
                "display_name": "A. Player",
                "competition": {"name": "Spanish first division", "country": "Sp\\u00e0in"},
                "period_contexts": {},
            },
            "i",
        ),
        ({"display_name": "N. Neighbor", "teams": [{"name": "Legan\\u00e9s"}]}, "n"),
    ],
)
def test_validation_rejects_literal_escapes_in_identity_fields(item: dict, base: str) -> None:
    with pytest.raises(ValueError, match="literal \\\\uXXXX escape text must be normalized"):
        _validate_identity_text(item, base)


@pytest.mark.parametrize(
    "item",
    [
        {"display_name": "L. Modrić", "competition": None},
        {
            "display_name": "Á. Correa",
            "competition": {"name": "Spanish first division", "country": "Spain"},
            "period_contexts": {"a": {"teams": [{"name": "Atlético Madrid"}]}},
        },
        {"display_name": "N. Neighbor", "teams": [{"name": "Leganés"}]},
    ],
)
def test_validation_accepts_normalized_identity_fields(item: dict) -> None:
    _validate_identity_text(item, "fixture")


def test_normalized_names_are_consistent_across_index_profile_and_neighbor_shapes() -> None:
    player = normalize_identity_text("\\u00c1. Correa")
    team = normalize_identity_text("Atl\\u00e9tico Madrid")
    _validate_identity_text(
        {
            "display_name": player,
            "competition": {"name": "Spanish first division", "country": "Spain"},
            "period_contexts": {
                "a": {"teams": [{"name": team}]},
                "b": {"teams": [{"name": team}]},
            },
        },
        "profile",
    )
    _validate_identity_text(
        {"display_name": player, "competition": {"name": "Spanish first division", "country": "Spain"}, "teams": [{"name": team}]},
        "index",
    )
