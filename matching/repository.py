"""Registry repository abstractions and concrete adapters.

Matching methods never return the ``management`` field.  It is exposed through
the separate ``get_management`` lookup to make it difficult to accidentally
turn entity matching into BCA/BQP classification.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from preprocessing.normalize import normalize_name, to_search_key

from .models import AliasRecord, OrganizationRecord


@runtime_checkable
class OrganizationRepository(Protocol):
    def get_by_id(self, organization_id: str) -> OrganizationRecord | None: ...

    def find_by_exact_name(self, organization_name: str) -> Sequence[OrganizationRecord]: ...

    def find_by_normalized_name(self, normalized_name: str) -> Sequence[OrganizationRecord]: ...

    def find_by_search_key(self, search_key: str) -> Sequence[OrganizationRecord]: ...

    def find_by_alias(
        self, normalized_alias: str, alias_search_key: str
    ) -> Sequence[OrganizationRecord]: ...

    def list_candidates(
        self,
        province_name: str | None = None,
        organization_type_code: str | None = None,
    ) -> Sequence[OrganizationRecord]: ...

    def list_aliases(
        self, organization_ids: Sequence[str]
    ) -> Sequence[AliasRecord]: ...

    def get_management(self, organization_id: str) -> str | None: ...


class InMemoryOrganizationRepository:
    """Small deterministic repository for tests and local experimentation."""

    def __init__(
        self,
        organizations: Iterable[OrganizationRecord | Mapping[str, Any]],
        aliases: Iterable[AliasRecord | Mapping[str, Any]] = (),
        management_by_id: Mapping[str, str] | None = None,
    ) -> None:
        self._organizations: list[OrganizationRecord] = []
        self._by_id: dict[str, OrganizationRecord] = {}
        self._management_by_id: dict[str, str] = dict(management_by_id or {})
        self._by_name: dict[str, list[OrganizationRecord]] = defaultdict(list)
        self._by_normalized: dict[str, list[OrganizationRecord]] = defaultdict(list)
        self._by_search_key: dict[str, list[OrganizationRecord]] = defaultdict(list)

        for source in organizations:
            organization = (
                source
                if isinstance(source, OrganizationRecord)
                else OrganizationRecord.from_mapping(source)
            )
            if organization.organization_id in self._by_id:
                raise ValueError(
                    f"duplicate organization_id: {organization.organization_id}"
                )
            self._organizations.append(organization)
            self._by_id[organization.organization_id] = organization
            self._by_name[organization.organization_name].append(organization)
            self._by_normalized[organization.normalized_name].append(organization)
            self._by_search_key[organization.search_key].append(organization)
            if isinstance(source, Mapping) and source.get("management") is not None:
                self._management_by_id[organization.organization_id] = str(
                    source["management"]
                )

        self._aliases: list[AliasRecord] = []
        self._alias_by_normalized: dict[str, set[str]] = defaultdict(set)
        self._alias_by_search_key: dict[str, set[str]] = defaultdict(set)
        for source in aliases:
            alias = (
                source
                if isinstance(source, AliasRecord)
                else AliasRecord.from_mapping(source)
            )
            if alias.organization_id not in self._by_id:
                raise ValueError(
                    f"alias references unknown organization_id: {alias.organization_id}"
                )
            self._aliases.append(alias)
            self._alias_by_normalized[alias.normalized_alias].add(
                alias.organization_id
            )
            self._alias_by_search_key[alias.alias_search_key].add(
                alias.organization_id
            )

    def get_by_id(self, organization_id: str) -> OrganizationRecord | None:
        return self._by_id.get(organization_id)

    def find_by_exact_name(self, organization_name: str) -> Sequence[OrganizationRecord]:
        return tuple(self._by_name.get(organization_name, ()))

    def find_by_normalized_name(self, normalized_name: str) -> Sequence[OrganizationRecord]:
        return tuple(self._by_normalized.get(normalized_name, ()))

    def find_by_search_key(self, search_key: str) -> Sequence[OrganizationRecord]:
        return tuple(self._by_search_key.get(search_key, ()))

    def find_by_alias(
        self, normalized_alias: str, alias_search_key: str
    ) -> Sequence[OrganizationRecord]:
        organization_ids = self._alias_by_normalized.get(
            normalized_alias, set()
        ) | self._alias_by_search_key.get(alias_search_key, set())
        return tuple(self._by_id[item] for item in sorted(organization_ids))

    def list_candidates(
        self,
        province_name: str | None = None,
        organization_type_code: str | None = None,
    ) -> Sequence[OrganizationRecord]:
        province_key = to_search_key(province_name) if province_name else None
        type_key = organization_type_code.strip().upper() if organization_type_code else None
        return tuple(
            organization
            for organization in self._organizations
            if (
                province_key is None
                or to_search_key(organization.province_name or "") == province_key
            )
            and (
                type_key is None
                or organization.organization_type_code.strip().upper() == type_key
            )
        )

    def list_aliases(
        self, organization_ids: Sequence[str]
    ) -> Sequence[AliasRecord]:
        selected = set(organization_ids)
        return tuple(
            alias for alias in self._aliases if alias.organization_id in selected
        )

    def get_management(self, organization_id: str) -> str | None:
        return self._management_by_id.get(organization_id)


class SqlAlchemyOrganizationRepository:
    """SQLAlchemy Core adapter for the master registry tables.

    Imports are lazy so pure unit tests can use the in-memory adapter without a
    database driver.  ``from_engine`` reflects the two tables created by the
    database layer; callers may also pass pre-built SQLAlchemy ``Table`` objects.
    """

    def __init__(self, engine: Any, organizations_table: Any, aliases_table: Any) -> None:
        self.engine = engine
        self.organizations = organizations_table
        self.aliases = aliases_table
        self._normalized_column = self._first_column(
            organizations_table, "normalized_name", "organization_name_normalized"
        )
        self._search_key_column = self._first_column(
            organizations_table, "search_key", "organization_name_search_key"
        )

    @classmethod
    def from_engine(
        cls,
        engine: Any,
        organizations_table_name: str = "organizations",
        aliases_table_name: str = "organization_aliases",
        schema: str | None = None,
    ) -> "SqlAlchemyOrganizationRepository":
        try:
            from sqlalchemy import MetaData, Table
        except ImportError as error:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "SQLAlchemy is required for SqlAlchemyOrganizationRepository"
            ) from error
        metadata = MetaData()
        organizations = Table(
            organizations_table_name,
            metadata,
            schema=schema,
            autoload_with=engine,
        )
        aliases = Table(
            aliases_table_name,
            metadata,
            schema=schema,
            autoload_with=engine,
        )
        return cls(engine, organizations, aliases)

    @staticmethod
    def _first_column(table: Any, *names: str) -> Any:
        for name in names:
            if name in table.c:
                return table.c[name]
        raise ValueError(f"table {table.name!r} must contain one of {names!r}")

    def _organization_columns(self) -> list[Any]:
        table = self.organizations
        return [
            table.c.organization_id,
            table.c.organization_name,
            self._normalized_column.label("normalized_name"),
            self._search_key_column.label("search_key"),
            table.c.organization_type_code,
            table.c.organization_level,
            table.c.parent_organization_id,
            table.c.province_name,
        ]

    @staticmethod
    def _rows_to_organizations(rows: Iterable[Any]) -> tuple[OrganizationRecord, ...]:
        return tuple(OrganizationRecord.from_mapping(row._mapping) for row in rows)

    def get_by_id(self, organization_id: str) -> OrganizationRecord | None:
        from sqlalchemy import select

        statement = select(*self._organization_columns()).where(
            self.organizations.c.organization_id == organization_id
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).first()
        return OrganizationRecord.from_mapping(row._mapping) if row else None

    def _find_by_column(self, column: Any, value: str) -> Sequence[OrganizationRecord]:
        from sqlalchemy import select

        statement = select(*self._organization_columns()).where(column == value)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
        return self._rows_to_organizations(rows)

    def find_by_exact_name(self, organization_name: str) -> Sequence[OrganizationRecord]:
        return self._find_by_column(
            self.organizations.c.organization_name, organization_name
        )

    def find_by_normalized_name(self, normalized_name: str) -> Sequence[OrganizationRecord]:
        return self._find_by_column(self._normalized_column, normalized_name)

    def find_by_search_key(self, search_key: str) -> Sequence[OrganizationRecord]:
        return self._find_by_column(self._search_key_column, search_key)

    def find_by_alias(
        self, normalized_alias: str, alias_search_key: str
    ) -> Sequence[OrganizationRecord]:
        from sqlalchemy import or_, select

        statement = (
            select(*self._organization_columns())
            .select_from(
                self.organizations.join(
                    self.aliases,
                    self.organizations.c.organization_id
                    == self.aliases.c.organization_id,
                )
            )
            .where(
                or_(
                    self.aliases.c.normalized_alias == normalized_alias,
                    self.aliases.c.alias_search_key == alias_search_key,
                )
            )
            .distinct()
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
        return self._rows_to_organizations(rows)

    def list_candidates(
        self,
        province_name: str | None = None,
        organization_type_code: str | None = None,
    ) -> Sequence[OrganizationRecord]:
        from sqlalchemy import func, select

        base_statement = select(*self._organization_columns())
        if organization_type_code:
            base_statement = base_statement.where(
                func.upper(func.trim(self.organizations.c.organization_type_code))
                == organization_type_code.strip().upper()
            )
        statement = base_statement
        if province_name:
            # Portable case/space normalization. Accent-insensitive context is
            # verified below and has a safe fallback for DBs without unaccent.
            statement = statement.where(
                func.lower(func.trim(self.organizations.c.province_name))
                == normalize_name(province_name)
            )
        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
            if province_name and not rows:
                # ``province_name`` has no normalized companion column in V1.
                # Preserve accent-insensitive correctness by filtering the
                # already type-blocked set in Python when the portable SQL
                # predicate cannot represent the supplied spelling.
                rows = connection.execute(base_statement).all()
        organizations = self._rows_to_organizations(rows)
        if province_name:
            province_key = to_search_key(province_name)
            organizations = tuple(
                organization
                for organization in organizations
                if to_search_key(organization.province_name or "") == province_key
            )
        return organizations

    def list_aliases(
        self, organization_ids: Sequence[str]
    ) -> Sequence[AliasRecord]:
        if not organization_ids:
            return ()
        from sqlalchemy import select

        statement = select(self.aliases).where(
            self.aliases.c.organization_id.in_(tuple(organization_ids))
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
        return tuple(AliasRecord.from_mapping(row._mapping) for row in rows)

    def get_management(self, organization_id: str) -> str | None:
        from sqlalchemy import select

        statement = select(self.organizations.c.management).where(
            self.organizations.c.organization_id == organization_id
        )
        with self.engine.connect() as connection:
            value = connection.execute(statement).scalar_one_or_none()
        return str(value) if value is not None else None
