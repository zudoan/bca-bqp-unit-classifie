"""Payroll lookup performed only after canonical entity resolution."""

from __future__ import annotations

from matching.models import PayrollInfo
from matching.repository import OrganizationRepository

from .management_lookup import RegistryDataError


def lookup_payroll(
    repository: OrganizationRepository,
    organization_id: str,
) -> PayrollInfo:
    """Read payroll facts without inferring missing values from management."""

    payroll = repository.get_payroll(organization_id)
    if payroll is None or not payroll.payroll_status.strip():
        raise RegistryDataError(
            "resolved organization has missing payroll data: "
            f"{organization_id}"
        )
    return payroll
