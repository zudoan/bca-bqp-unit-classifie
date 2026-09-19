"""Context-based candidate blocking for the fuzzy stage."""

from __future__ import annotations

from dataclasses import dataclass

from .models import AliasRecord, OrganizationRecord
from .repository import OrganizationRepository


@dataclass(frozen=True, slots=True)
class CandidatePool:
    organizations: tuple[OrganizationRecord, ...]
    aliases: tuple[AliasRecord, ...]


class CandidateGenerator:
    def __init__(self, repository: OrganizationRepository) -> None:
        self.repository = repository

    def generate(
        self,
        province_name: str | None = None,
        organization_type_code: str | None = None,
    ) -> CandidatePool:
        """Block by provided context, then fetch aliases only for that block."""

        organizations = tuple(
            self.repository.list_candidates(
                province_name=province_name,
                organization_type_code=organization_type_code,
            )
        )
        aliases = tuple(
            self.repository.list_aliases(
                [organization.organization_id for organization in organizations]
            )
        )
        return CandidatePool(organizations=organizations, aliases=aliases)
