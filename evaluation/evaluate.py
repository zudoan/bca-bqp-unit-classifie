"""Evaluate the resolver without conflating entity and management metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from matching.fuzzy_match import SUPPORTED_SCORERS
from matching.models import DETERMINISTIC_MATCH_STATUSES
from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from search.organization_search import OrganizationSearchService


RESOLVED_STATUSES = {status.value for status in DETERMINISTIC_MATCH_STATUSES}


def _optional(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text if text else None


def load_service(
    dataset_path: Path,
    aliases_path: Path | None,
    scorer: str,
    threshold: float,
    top_k: int,
) -> OrganizationSearchService:
    organizations = pd.read_csv(
        dataset_path, dtype=str, keep_default_na=False
    ).to_dict("records")
    aliases: Iterable[dict[str, str]] = ()
    if aliases_path and aliases_path.is_file():
        aliases = pd.read_csv(
            aliases_path, dtype=str, keep_default_na=False
        ).to_dict("records")
    repository = InMemoryOrganizationRepository(organizations, aliases)
    return OrganizationSearchService(
        repository,
        MatchingConfig(
            fuzzy_scorer=scorer,
            fuzzy_minimum_score=threshold,
            fuzzy_top_k=top_k,
        ),
    )


def evaluate_cases(
    cases: pd.DataFrame,
    service: OrganizationSearchService,
) -> pd.DataFrame:
    predictions: list[dict[str, Any]] = []
    for row in cases.itertuples(index=False):
        result = service.search_organization(
            organization_id=_optional(row.query_id),
            organization_name=_optional(row.query_name),
            province_name=_optional(row.province_name),
            organization_type=_optional(row.organization_type),
        )
        candidates = result.get("candidates", [])
        predictions.append(
            {
                **row._asdict(),
                "actual_match_status": result["match_status"],
                "actual_organization_id": result.get("organization_id", ""),
                "actual_management": result.get("management", ""),
                "candidate_ids": "|".join(
                    candidate["organization_id"] for candidate in candidates
                ),
                "candidate_scores": "|".join(
                    str(candidate.get("score", "")) for candidate in candidates
                ),
                "top1_score": result.get("top1_score", ""),
                "score_margin": result.get("score_margin", ""),
                "reason": result.get("reason", ""),
            }
        )
    return pd.DataFrame.from_records(predictions)


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def calculate_metrics(predictions: pd.DataFrame) -> dict[str, Any]:
    total = len(predictions)
    status_correct = predictions.actual_match_status.eq(
        predictions.expected_match_status
    )
    actual_resolved = predictions.actual_match_status.isin(RESOLVED_STATUSES)
    expected_id_present = predictions.expected_organization_id.ne("")
    organization_correct = predictions.actual_organization_id.eq(
        predictions.expected_organization_id
    ) & expected_id_present

    wrong_auto_match = actual_resolved & ~organization_correct
    expected_unresolved = predictions.expected_match_status.isin(
        {"AMBIGUOUS_MATCH", "NOT_FOUND", "INVALID_INPUT", "FUZZY_CANDIDATES"}
    ) & ~expected_id_present
    unsafe_unresolved_resolution = expected_unresolved & actual_resolved

    deterministic_expected = predictions.expected_match_status.isin(
        RESOLVED_STATUSES
    )
    deterministic_correct = deterministic_expected & organization_correct

    fuzzy = predictions.expected_match_status.eq("FUZZY_CANDIDATES")

    def candidate_at_k(candidate_text: str, expected_id: str, k: int) -> bool:
        if not candidate_text or not expected_id:
            return False
        return expected_id in candidate_text.split("|")[:k]

    top_recall: dict[str, float | None] = {}
    fuzzy_count = int(fuzzy.sum())
    for k in (1, 3, 5):
        hits = sum(
            candidate_at_k(candidates, expected_id, k)
            for candidates, expected_id in zip(
                predictions.loc[fuzzy, "candidate_ids"],
                predictions.loc[fuzzy, "expected_organization_id"],
            )
        )
        top_recall[f"fuzzy_top_{k}_recall"] = _rate(hits, fuzzy_count)

    correctly_resolved = deterministic_correct
    management_correct = predictions.actual_management.eq(
        predictions.expected_management
    )

    scenario_detection: dict[str, float | None] = {}
    for status, label in (
        ("AMBIGUOUS_MATCH", "ambiguous_detection_accuracy"),
        ("NOT_FOUND", "not_found_detection_accuracy"),
        ("INVALID_INPUT", "invalid_input_detection_accuracy"),
    ):
        mask = predictions.expected_match_status.eq(status)
        scenario_detection[label] = _rate(
            int((mask & predictions.actual_match_status.eq(status)).sum()),
            int(mask.sum()),
        )

    return {
        "cases": total,
        "status_accuracy": _rate(int(status_correct.sum()), total),
        "exact_resolution_accuracy": _rate(
            int(deterministic_correct.sum()), int(deterministic_expected.sum())
        ),
        **top_recall,
        "false_match_rate": _rate(
            int(wrong_auto_match.sum()), int(actual_resolved.sum())
        ),
        "unsafe_resolution_rate_on_unresolved_queries": _rate(
            int(unsafe_unresolved_resolution.sum()), int(expected_unresolved.sum())
        ),
        **scenario_detection,
        "management_lookup_accuracy_given_correct_resolution": _rate(
            int((correctly_resolved & management_correct).sum()),
            int(correctly_resolved.sum()),
        ),
        "end_to_end_correct_rate": _rate(
            int((deterministic_correct & management_correct).sum()), total
        ),
        "auto_resolution_coverage": _rate(int(actual_resolved.sum()), total),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/dataset.csv"))
    parser.add_argument(
        "--test-cases",
        type=Path,
        default=Path("data/test/matching_test_cases.csv"),
    )
    parser.add_argument(
        "--aliases", type=Path, default=Path("data/test/aliases.csv")
    )
    parser.add_argument("--split", choices=("DEV", "TEST", "ALL"), default="DEV")
    parser.add_argument("--scorer", choices=SUPPORTED_SCORERS, default="WRatio")
    parser.add_argument(
        "--threshold",
        type=float,
        default=MatchingConfig().fuzzy_minimum_score,
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--all-scorers", action="store_true")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("evaluation/reports/predictions.csv"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = pd.read_csv(args.test_cases, dtype=str, keep_default_na=False)
    if args.split != "ALL":
        cases = cases[cases.dataset_split.eq(args.split)].copy()

    scorers = SUPPORTED_SCORERS if args.all_scorers else (args.scorer,)
    summaries: list[dict[str, Any]] = []
    for scorer in scorers:
        service = load_service(
            args.dataset,
            args.aliases,
            scorer,
            args.threshold,
            args.top_k,
        )
        predictions = evaluate_cases(cases, service)
        metrics = calculate_metrics(predictions)
        summaries.append(
            {
                "split": args.split,
                "scorer": scorer,
                "threshold": args.threshold,
                "top_k": args.top_k,
                **metrics,
            }
        )
        if not args.all_scorers:
            args.predictions.parent.mkdir(parents=True, exist_ok=True)
            predictions.to_csv(args.predictions, index=False, encoding="utf-8")

    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
