from __future__ import annotations

from pathlib import Path

import pandas as pd

from evaluation.build_test_cases import build_cases
from evaluation.error_analysis import classify
from evaluation.evaluate import calculate_metrics


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_seed_builder_covers_required_scenarios_in_both_splits():
    data = pd.read_csv(
        PROJECT_ROOT / "data" / "dataset.csv",
        dtype=str,
        keep_default_na=False,
    )
    aliases = pd.read_csv(
        PROJECT_ROOT / "data" / "test" / "aliases.csv",
        dtype=str,
        keep_default_na=False,
    )
    cases = build_cases(data, per_scenario=6, aliases=aliases)

    required = {
        "alias_abbreviation",
        "empty_query",
        "multi_character_typo",
        "same_name_ambiguous",
        "single_character_typo",
        "unknown_organization",
        "wrong_province",
    }
    for split in ("DEV", "TEST"):
        assert required <= set(cases.loc[cases.dataset_split.eq(split), "scenario"])

    labeled = cases[cases.expected_organization_id.ne("")]
    assert (
        labeled.groupby("expected_organization_id").dataset_split.nunique().max()
        == 1
    )


def test_metrics_distinguish_fuzzy_recall_from_auto_resolution():
    predictions = pd.DataFrame.from_records(
        [
            {
                "expected_match_status": "FUZZY_CANDIDATES",
                "actual_match_status": "FUZZY_CANDIDATES",
                "expected_organization_id": "ORG-2",
                "actual_organization_id": "",
                "expected_management": "BCA",
                "actual_management": "",
                "candidate_ids": "ORG-1|ORG-2",
            },
            {
                "expected_match_status": "NOT_FOUND",
                "actual_match_status": "NOT_FOUND",
                "expected_organization_id": "",
                "actual_organization_id": "",
                "expected_management": "",
                "actual_management": "",
                "candidate_ids": "",
            },
        ]
    )

    metrics = calculate_metrics(predictions)
    assert metrics["fuzzy_top_1_recall"] == 0.0
    assert metrics["fuzzy_top_3_recall"] == 1.0
    assert metrics["false_match_rate"] is None
    assert metrics["not_found_detection_accuracy"] == 1.0


def test_error_analysis_detects_management_lookup_error():
    row = pd.Series(
        {
            "expected_match_status": "EXACT_ID_MATCH",
            "actual_match_status": "EXACT_ID_MATCH",
            "expected_organization_id": "ORG-1",
            "actual_organization_id": "ORG-1",
            "expected_management": "BCA",
            "actual_management": "BQP",
            "candidate_ids": "",
            "scenario": "exact_id_bca",
        }
    )
    assert classify(row) == "MANAGEMENT_LOOKUP_ERROR"
