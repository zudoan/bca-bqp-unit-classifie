"""Organization entity-resolution engine."""

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
