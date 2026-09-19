"""Known-alias matching, deliberately executed before fuzzy retrieval."""

from __future__ import annotations

from preprocessing.normalize import normalize_name, to_search_key

from .models import OrganizationRecord
from .repository import OrganizationRepository


class AliasMatcher:
    def __init__(self, repository: OrganizationRepository) -> None:
        self.repository = repository

    def match(self, organization_name: str) -> tuple[OrganizationRecord, ...]:
        organizations = self.repository.find_by_alias(
            normalize_name(organization_name),
            to_search_key(organization_name),
        )
        by_id = {
            organization.organization_id: organization
            for organization in organizations
        }
        return tuple(by_id[key] for key in sorted(by_id))
