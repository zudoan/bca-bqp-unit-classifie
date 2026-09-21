"""Deterministic matching for the generated acronym dataset.

``data/acronym.csv`` is intentionally kept separate from the small curated
alias table. It contains hundreds of thousands of generated spellings, so it
is indexed for exact search-key lookup only and is never added to the fuzzy
candidate pool.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from preprocessing.normalize import to_search_key

from .models import OrganizationRecord
from .repository import OrganizationRepository


class AcronymDatasetError(ValueError):
    """Raised when an acronym dataset cannot be linked safely to the registry."""


class AcronymMatcher:
    """Index acronym aliases and resolve them to canonical organizations."""

    def __init__(
        self,
        repository: OrganizationRepository,
        records: Iterable[Mapping[str, Any]],
    ) -> None:
        self.repository = repository
        self._aliases: dict[str, str | tuple[str, ...]] = {}
        canonical_labels: dict[str, str] = {}
        self.row_count = 0
        self.conflicting_alias_count = 0

        for row_number, row in enumerate(records, start=2):
            alias = _required_value(row, "alias", row_number)
            label = _required_value(row, "label", row_number)
            alias_key = to_search_key(alias)
            if not alias_key:
                raise AcronymDatasetError(
                    f"acronym row {row_number}: alias has no searchable characters"
                )

            # Reuse one string object per label. This matters for a large file
            # in which every canonical label occurs in many generated rows.
            label = canonical_labels.setdefault(label, label)
            existing = self._aliases.get(alias_key)
            if existing is None:
                self._aliases[alias_key] = label
            elif isinstance(existing, str):
                if existing != label:
                    self._aliases[alias_key] = (existing, label)
                    self.conflicting_alias_count += 1
            elif label not in existing:
                self._aliases[alias_key] = (*existing, label)
            self.row_count += 1

        self._organizations_by_label: dict[
            str, tuple[OrganizationRecord, ...]
        ] = {}
        missing_labels: list[str] = []
        for label in canonical_labels:
            organizations = tuple(repository.find_by_exact_name(label))
            if organizations:
                self._organizations_by_label[label] = organizations
            else:
                missing_labels.append(label)

        if missing_labels:
            examples = ", ".join(repr(label) for label in missing_labels[:5])
            suffix = "" if len(missing_labels) <= 5 else ", ..."
            raise AcronymDatasetError(
                f"{len(missing_labels)} acronym label(s) do not exist exactly in "
                f"the organization registry: {examples}{suffix}"
            )

        self.label_count = len(canonical_labels)

    @classmethod
    def from_csv(
        cls,
        repository: OrganizationRepository,
        path: str | Path,
    ) -> "AcronymMatcher":
        """Load a UTF-8 ``alias,label`` CSV without materializing a DataFrame."""

        dataset_path = Path(path)
        try:
            handle = dataset_path.open(
                "r", encoding="utf-8-sig", newline=""
            )
        except OSError as error:
            raise AcronymDatasetError(
                f"cannot open acronym dataset {dataset_path}: {error}"
            ) from error

        with handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing_columns = {"alias", "label"} - fields
            if missing_columns:
                names = ", ".join(sorted(missing_columns))
                raise AcronymDatasetError(
                    f"acronym dataset is missing required column(s): {names}"
                )
            return cls(repository, reader)

    @property
    def alias_count(self) -> int:
        """Number of unique accent-insensitive alias keys in the index."""

        return len(self._aliases)

    def match(self, organization_name: str) -> tuple[OrganizationRecord, ...]:
        labels = self._aliases.get(to_search_key(organization_name))
        if labels is None:
            return ()
        selected_labels = (labels,) if isinstance(labels, str) else labels

        by_id: dict[str, OrganizationRecord] = {}
        for label in selected_labels:
            for organization in self._organizations_by_label[label]:
                by_id[organization.organization_id] = organization
        return tuple(by_id[key] for key in sorted(by_id))


def _required_value(
    row: Mapping[str, Any], field_name: str, row_number: int
) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise AcronymDatasetError(
            f"acronym row {row_number}: {field_name} must be a non-empty string"
        )
    return value.strip()
