"""Canonical caveat copy shared by profile and research artifacts."""

from __future__ import annotations

CAVEATS: dict[str, dict[str, str]] = {
    "fingerprint_not_style_proof": {
        "severity": "critical",
        "message": "A stable event-derived fingerprint is evidence of individual signal, not proof of playing style.",
    },
    "similarity_not_recruitment": {
        "severity": "critical",
        "message": "Statistical proximity is descriptive and must not be read as a recruitment recommendation.",
    },
    "same_season_team_confound": {
        "severity": "critical",
        "message": "Same-season club continuity is a strong confound and can make identity retrieval easier.",
    },
    "small_transfer_sample": {
        "severity": "important",
        "message": "Transferred-player evidence is based on a small sample and has wide uncertainty.",
    },
    "provider_replication_lower_magnitude": {
        "severity": "important",
        "message": "The independent-provider replication is positive but lower in magnitude than the Wyscout result.",
    },
    "within_role_display_differs_from_global_model": {
        "severity": "context",
        "message": "Within-role percentiles aid display; cosine retrieval uses globally standardized values.",
    },
    "uncertainty_pending": {
        "severity": "important",
        "message": "Match-level sampling-stability intervals are not available in this dataset version.",
    },
    "uncertainty_sampling_only": {
        "severity": "important",
        "message": "Sampling intervals describe stability in observed matches, not causal or future-performance uncertainty.",
    },
    "goalkeeper_feature_coverage_weak": {
        "severity": "critical",
        "message": "The native 32-feature catalog is outfield-oriented and has weak goalkeeper-specific coverage.",
    },
}


def caveat(code: str, evidence_refs: list[str] | None = None) -> dict:
    definition = CAVEATS[code]
    return {
        "code": code,
        "severity": definition["severity"],
        "message": definition["message"],
        "evidence_refs": evidence_refs or [],
    }


def profile_caveats(role: str, uncertainty_status: str = "pending") -> list[dict]:
    codes = [
        "fingerprint_not_style_proof",
        "similarity_not_recruitment",
        "same_season_team_confound",
        "within_role_display_differs_from_global_model",
    ]
    codes.append("uncertainty_sampling_only" if uncertainty_status != "pending" else "uncertainty_pending")
    if role == "Goalkeeper":
        codes.append("goalkeeper_feature_coverage_weak")
    return [caveat(code) for code in codes]
