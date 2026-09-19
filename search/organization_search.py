"""Public search facade: entity resolution followed by management lookup."""

from __future__ import annotations

from threading import RLock
from typing import Any

from matching.models import MatchCandidate, MatchResolution, MatchStatus
from matching.repository import OrganizationRepository
from matching.resolver import MatchingConfig, OrganizationResolver
from preprocessing.validate import InputValidationError, validate_search_input

from .management_lookup import RegistryDataError, lookup_management


class OrganizationSearchService:
    def __init__(
        self,
        repository: OrganizationRepository,
        matching_config: MatchingConfig | None = None,
    ) -> None:
        self.repository = repository
        self.resolver = OrganizationResolver(repository, matching_config)

    def search_organization(
        self,
        organization_id: object = None,
        organization_name: object = None,
        province_name: object = None,
        organization_type: object = None,
    ) -> dict[str, Any]:
        """Search the registry using the Version 1 request/response contract."""

        try:
            request = validate_search_input(
                organization_id=organization_id,
                organization_name=organization_name,
                province_name=province_name,
                organization_type=organization_type,
            )
        except InputValidationError as error:
            return {
                "match_status": MatchStatus.INVALID_INPUT.value,
                "errors": list(error.errors),
            }

        resolution = self.resolver.resolve(request)
        return self._serialize_resolution(resolution)

    def _serialize_resolution(
        self, resolution: MatchResolution
    ) -> dict[str, Any]:
        if resolution.is_resolved:
            organization = resolution.organization
            if organization is None:  # Defensive assertion for custom resolvers.
                raise RegistryDataError("resolved match has no organization")
            # This is intentionally the only management lookup in the pipeline,
            # and it occurs only after canonical organization resolution.
            management = lookup_management(
                self.repository, organization.organization_id
            )
            return {
                "match_status": resolution.match_status.value,
                "match_score": _display_score(resolution.match_score),
                "organization_id": organization.organization_id,
                "organization_name": organization.organization_name,
                "province_name": organization.province_name,
                "organization_type_code": organization.organization_type_code,
                "management": management,
            }

        result: dict[str, Any] = {
            "match_status": resolution.match_status.value,
        }
        if resolution.candidates:
            result["candidates"] = [
                _serialize_candidate(candidate)
                for candidate in resolution.candidates
            ]
        elif resolution.match_status in {
            MatchStatus.FUZZY_CANDIDATES,
            MatchStatus.AMBIGUOUS_MATCH,
            MatchStatus.NOT_FOUND,
        }:
            result["candidates"] = []

        if resolution.match_status == MatchStatus.FUZZY_CANDIDATES:
            scores = [candidate.score for candidate in resolution.candidates]
            result["top1_score"] = _display_score(scores[0])
            result["top2_score"] = (
                _display_score(scores[1]) if len(scores) > 1 else None
            )
            result["score_margin"] = (
                round(scores[0] - scores[1], 2) if len(scores) > 1 else None
            )
        if resolution.reason:
            result["reason"] = resolution.reason
        return result


def _serialize_candidate(candidate: MatchCandidate) -> dict[str, Any]:
    organization = candidate.organization
    return {
        "organization_id": organization.organization_id,
        "organization_name": organization.organization_name,
        "province_name": organization.province_name,
        "organization_type_code": organization.organization_type_code,
        "organization_level": organization.organization_level,
        "parent_organization_id": organization.parent_organization_id,
        "score": _display_score(candidate.score),
        "matched_on": candidate.matched_on,
    }


def _display_score(score: float | None) -> int | float | None:
    if score is None:
        return None
    if float(score).is_integer():
        return int(score)
    return round(float(score), 2)


_default_service: OrganizationSearchService | None = None
_default_service_lock = RLock()


def configure_repository(
    repository: OrganizationRepository,
    matching_config: MatchingConfig | None = None,
) -> OrganizationSearchService:
    """Configure the process-wide facade and return the created service."""

    service = OrganizationSearchService(repository, matching_config)
    configure_search_service(service)
    return service


def configure_search_service(service: OrganizationSearchService) -> None:
    global _default_service
    if not isinstance(service, OrganizationSearchService):
        raise TypeError("service must be an OrganizationSearchService")
    with _default_service_lock:
        _default_service = service


def search_organization(
    organization_id=None,
    organization_name=None,
    province_name=None,
    organization_type=None,
):
    """Version 1 core API.

    Configure it once with :func:`configure_repository`, normally using a
    :class:`matching.repository.SqlAlchemyOrganizationRepository`.
    """

    with _default_service_lock:
        service = _default_service
    if service is None:
        raise RuntimeError(
            "organization search is not configured; call configure_repository first"
        )
    return service.search_organization(
        organization_id=organization_id,
        organization_name=organization_name,
        province_name=province_name,
        organization_type=organization_type,
    )
