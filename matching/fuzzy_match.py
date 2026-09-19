"""RapidFuzz ranking of a pre-blocked organization candidate pool."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence

from preprocessing.normalize import to_search_key

from .models import AliasRecord, MatchCandidate, OrganizationRecord


SUPPORTED_SCORERS = (
    "ratio",
    "WRatio",
    "token_sort_ratio",
    "token_set_ratio",
)


class FuzzyMatcher:
    """Rank candidates only; Version 1 never auto-resolves fuzzy output."""

    def __init__(
        self,
        scorer_name: str = "WRatio",
        minimum_score: float = 85.0,
        top_k: int = 5,
    ) -> None:
        if scorer_name not in SUPPORTED_SCORERS:
            raise ValueError(
                f"unsupported scorer {scorer_name!r}; choose one of {SUPPORTED_SCORERS}"
            )
        if not 0 <= minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        self.scorer_name = scorer_name
        self.minimum_score = float(minimum_score)
        self.top_k = top_k

    @staticmethod
    def _load_scorer(scorer_name: str) -> Callable[[str, str], float]:
        try:
            from rapidfuzz import fuzz
        except ImportError as error:  # pragma: no cover - environment dependent
            raise RuntimeError("RapidFuzz is required for fuzzy matching") from error
        return getattr(fuzz, scorer_name)

    def rank(
        self,
        query_name: str,
        organizations: Sequence[OrganizationRecord],
        aliases: Sequence[AliasRecord] = (),
    ) -> tuple[MatchCandidate, ...]:
        query_key = to_search_key(query_name)
        if not query_key or not organizations:
            return ()

        scorer = self._load_scorer(self.scorer_name)
        aliases_by_organization: dict[str, list[AliasRecord]] = defaultdict(list)
        for alias in aliases:
            aliases_by_organization[alias.organization_id].append(alias)

        ranked: list[MatchCandidate] = []
        for organization in organizations:
            best_score = float(scorer(query_key, organization.search_key))
            best_source = "CANONICAL_SEARCH_KEY"
            best_value = organization.search_key

            for alias in aliases_by_organization.get(
                organization.organization_id, ()
            ):
                score = float(scorer(query_key, alias.alias_search_key))
                if score > best_score:
                    best_score = score
                    best_source = "ALIAS_SEARCH_KEY"
                    best_value = alias.alias_name

            if best_score >= self.minimum_score:
                ranked.append(
                    MatchCandidate(
                        organization=organization,
                        score=round(best_score, 2),
                        matched_on=best_source,
                        matched_value=best_value,
                    )
                )

        ranked.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.organization.organization_id,
            )
        )
        return tuple(ranked[: self.top_k])
