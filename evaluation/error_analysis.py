"""Classify benchmark failures by the pipeline layer that should be fixed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def classify(row: pd.Series) -> str:
    if (
        str(row.get("expected_management", ""))
        and row.get("actual_management", "")
        != row.get("expected_management", "")
        and row.get("actual_organization_id", "")
        == row.get("expected_organization_id", "")
    ):
        return "MANAGEMENT_LOOKUP_ERROR"
    status_correct = row.actual_match_status == row.expected_match_status
    id_correct = (
        not row.expected_organization_id
        or row.actual_organization_id == row.expected_organization_id
        or row.expected_organization_id in str(row.candidate_ids).split("|")
    )
    if status_correct and id_correct:
        return "OK"
    scenario = str(row.scenario)
    if "alias" in scenario or "abbreviation" in scenario:
        return "ALIAS_MISSING"
    if scenario == "wrong_province":
        return "WRONG_PROVINCE"
    if scenario == "same_name_ambiguous":
        return "SAME_NAME_AMBIGUITY"
    if scenario in {"short_query", "empty_query"}:
        return "QUERY_TOO_SHORT"
    if scenario == "unknown_organization":
        return "UNKNOWN_FALSE_MATCH"
    if scenario == "parent_organization":
        return "PARENT_CONFUSION"
    if scenario in {"uppercase", "lowercase", "without_diacritics", "extra_whitespace", "punctuation_variant"}:
        return "NORMALIZATION_ERROR"
    if "typo" in scenario or scenario in {"missing_word", "extra_word"}:
        if row.actual_match_status in {
            "EXACT_ID_MATCH",
            "EXACT_NAME_MATCH",
            "NORMALIZED_MATCH",
            "SEARCH_KEY_MATCH",
            "ALIAS_MATCH",
        }:
            return "WRONG_DETERMINISTIC_MATCH"
        if row.actual_match_status == "FUZZY_MATCH":
            return "FUZZY_FALSE_POSITIVE"
        return "TYPO_ERROR"
    return "UNCLASSIFIED"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("evaluation/reports/predictions.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/reports/error_analysis.csv"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    predictions = pd.read_csv(
        args.predictions, dtype=str, keep_default_na=False
    )
    predictions["error_category"] = predictions.apply(classify, axis=1)
    errors = predictions[predictions.error_category.ne("OK")].copy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    errors.to_csv(args.output, index=False, encoding="utf-8")
    summary = errors.groupby("error_category").size().sort_values(ascending=False)
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    print(f"wrote {len(errors)} errors to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
