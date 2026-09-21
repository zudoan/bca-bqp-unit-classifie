"""Organization entity-resolution engine."""

from .acronym_match import AcronymDatasetError, AcronymMatcher
from .models import (
    AliasRecord,
    MatchCandidate,
    MatchResolution,
    MatchStatus,
    OrganizationRecord,
)
from .repository import (
    InMemoryOrganizationRepository,
    OrganizationRepository,
    SqlAlchemyOrganizationRepository,
)
from .resolver import MatchingConfig, OrganizationResolver

__all__ = [
    "AcronymDatasetError",
    "AcronymMatcher",
    "AliasRecord",
    "InMemoryOrganizationRepository",
    "MatchCandidate",
    "MatchResolution",
    "MatchStatus",
    "MatchingConfig",
    "OrganizationRecord",
    "OrganizationRepository",
    "OrganizationResolver",
    "SqlAlchemyOrganizationRepository",
]
