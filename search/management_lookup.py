"""Management lookup performed only after canonical entity resolution."""

from __future__ import annotations

from matching.repository import OrganizationRepository


VALID_MANAGEMENT_VALUES = frozenset({"BCA", "BQP"})


class RegistryDataError(RuntimeError):
    """Raised when a master record violates registry invariants."""


def lookup_management(
    repository: OrganizationRepository,
    organization_id: str,
) -> str:
    """Read and validate management for one resolved organization ID."""

    management = repository.get_management(organization_id)
    if management not in VALID_MANAGEMENT_VALUES:
        raise RegistryDataError(
            "resolved organization has invalid or missing management: "
            f"{organization_id}"
        )
    return management
