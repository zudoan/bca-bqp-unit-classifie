#!/usr/bin/env python3
"""Load the organization CSV through staging, validation, and master upsert.

The loader is deliberately independent from the matching engine.  It preserves
the nine source fields in ``staging_organizations``, validates a complete batch,
and only then promotes canonical organizations in one transaction.

Examples:

    python database/load_data.py --dsn "$DATABASE_URL"
    python database/load_data.py --dsn "postgresql://user:pass@localhost/db" \
        --csv data/dataset.csv

Exit codes:
    0: completed, or an identical completed source was skipped
    1: configuration/database/import error
    2: source rows were staged but failed validation
"""

from __future__ import print_function

import argparse
import csv
import hashlib
import json
import os
import sys
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


EXPECTED_COLUMNS: Tuple[str, ...] = (
    "organization_id",
    "organization_name",
    "organization_name_normalized",
    "organization_name_search_key",
    "organization_type_code",
    "organization_level",
    "parent_organization_id",
    "province_name",
    "management",
)

REQUIRED_COLUMNS: Tuple[str, ...] = (
    "organization_id",
    "organization_name",
    "organization_name_normalized",
    "organization_name_search_key",
    "organization_type_code",
    "organization_level",
    "province_name",
    "management",
)

CsvRecord = Tuple[int, Tuple[str, ...]]

CHILD_ORGANIZATION_LEVELS: Tuple[str, ...] = (
    "DISTRICT",
    "DISTRICT_DEPARTMENT",
    "PROVINCE_DEPARTMENT",
    "PROVINCE_BORDER",
    "BORDER_POST",
    "BORDER_SQUADRON",
)


class CsvStructureError(ValueError):
    """Raised when a CSV cannot be represented by the required nine columns."""


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _default_project_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import an organization registry CSV into PostgreSQL safely."
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN. Defaults to the DATABASE_URL environment variable.",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        default=_default_project_path("data", "dataset.csv"),
        help="Source CSV path (default: data/dataset.csv).",
    )
    parser.add_argument(
        "--schema-file",
        type=Path,
        default=Path(__file__).resolve().with_name("schema.sql"),
        help="DDL file used to create the tables.",
    )
    parser.add_argument(
        "--indexes-file",
        type=Path,
        default=Path(__file__).resolve().with_name("indexes.sql"),
        help="DDL file used to create the indexes.",
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Do not execute schema.sql and indexes.sql before importing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess a source even when its SHA-256 batch already completed.",
    )
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=1000,
        help="Rows per executemany call (default: 1000).",
    )
    args = parser.parse_args(argv)
    if not args.dsn:
        parser.error("--dsn is required when DATABASE_URL is not set")
    return args


def connect_database(dsn: str) -> Any:
    """Connect with psycopg 3 when available, otherwise psycopg2."""
    try:
        import psycopg  # type: ignore
    except ImportError:
        try:
            import psycopg2  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL driver not installed. Install 'psycopg[binary]' "
                "(preferred) or 'psycopg2-binary'."
            ) from exc
        return psycopg2.connect(dsn)
    return psycopg.connect(dsn)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_organization_name(value: str) -> str:
    """Apply the Version 1 canonical-name normalization contract.

    NFKC makes compatibility forms deterministic, punctuation becomes a word
    boundary, and all Unicode whitespace collapses.  Keeping this computation
    in the importer prevents a source-provided normalized column from silently
    becoming the matching key of record.
    """
    compatible = unicodedata.normalize("NFKC", value).lower()
    without_punctuation = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in compatible
    )
    return " ".join(without_punctuation.split())


def remove_vietnamese_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    # Vietnamese đ/Đ does not decompose under NFD.
    without_marks = without_marks.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFC", without_marks)


def build_search_key(value: str) -> str:
    return remove_vietnamese_diacritics(normalize_organization_name(value))


def read_source_csv(path: Path) -> List[CsvRecord]:
    """Read the UTF-8 CSV and reject structural loss before touching the DB."""
    if not path.is_file():
        raise CsvStructureError("CSV file does not exist: {0}".format(path))

    records: List[CsvRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        actual_columns = tuple(reader.fieldnames or ())
        if actual_columns != EXPECTED_COLUMNS:
            missing = [column for column in EXPECTED_COLUMNS if column not in actual_columns]
            unexpected = [column for column in actual_columns if column not in EXPECTED_COLUMNS]
            details = []
            if missing:
                details.append("missing={0}".format(missing))
            if unexpected:
                details.append("unexpected={0}".format(unexpected))
            if not missing and not unexpected:
                details.append("column order does not match the registry contract")
            raise CsvStructureError(
                "Invalid CSV header ({0}). Expected exactly: {1}".format(
                    "; ".join(details), ", ".join(EXPECTED_COLUMNS)
                )
            )

        # row_number starts at 2 because the header occupies the first CSV row.
        # It is a logical CSV record number; quoted embedded newlines remain one row.
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise CsvStructureError(
                    "CSV row {0} contains more than nine fields".format(row_number)
                )
            missing_values = [column for column in EXPECTED_COLUMNS if row[column] is None]
            if missing_values:
                raise CsvStructureError(
                    "CSV row {0} has missing fields: {1}".format(
                        row_number, ", ".join(missing_values)
                    )
                )

            values = tuple(row[column] for column in EXPECTED_COLUMNS)
            for column, value in zip(EXPECTED_COLUMNS, values):
                if "\x00" in value:
                    raise CsvStructureError(
                        "CSV row {0}, column {1} contains a NUL byte, which "
                        "PostgreSQL text cannot store".format(row_number, column)
                    )
            records.append((row_number, values))

    if not records:
        raise CsvStructureError("CSV contains a header but no organization rows")
    return records


def execute_sql_file(connection: Any, path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError("SQL file does not exist: {0}".format(path))
    sql = path.read_text(encoding="utf-8")
    if not sql.strip():
        raise ValueError("SQL file is empty: {0}".format(path))
    with connection.cursor() as cursor:
        cursor.execute(sql)


def initialize_database(connection: Any, schema_path: Path, indexes_path: Path) -> None:
    """Run idempotent DDL scripts, each of which owns its transaction."""
    connection.autocommit = True
    try:
        execute_sql_file(connection, schema_path)
        execute_sql_file(connection, indexes_path)
    finally:
        connection.autocommit = False


def prepare_import_batch(
    cursor: Any,
    source_path: Path,
    source_sha256: str,
    source_size: int,
    force: bool,
) -> Tuple[str, bool, Optional[Dict[str, Any]]]:
    """Create/lock a batch and report whether a completed checksum can skip."""
    proposed_batch_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO public.organization_import_batches (
            import_batch_id,
            source_filename,
            source_sha256,
            source_size_bytes,
            status
        )
        VALUES (%s, %s, %s, %s, 'STAGING')
        ON CONFLICT (source_sha256) DO NOTHING
        RETURNING import_batch_id
        """,
        (proposed_batch_id, str(source_path), source_sha256, source_size),
    )
    inserted = cursor.fetchone()
    if inserted is not None:
        return str(inserted[0]), False, None

    # ON CONFLICT waits for a concurrent transaction touching the same checksum.
    # FOR UPDATE then serializes a retry/force import of that source.
    cursor.execute(
        """
        SELECT
            import_batch_id,
            status,
            total_rows,
            valid_rows,
            invalid_rows,
            promoted_rows,
            completed_at
        FROM public.organization_import_batches
        WHERE source_sha256 = %s
        FOR UPDATE
        """,
        (source_sha256,),
    )
    existing = cursor.fetchone()
    if existing is None:
        raise RuntimeError("could not acquire import batch for source checksum")

    batch_id = str(existing[0])
    if existing[1] == "COMPLETED" and not force:
        summary = {
            "status": existing[1],
            "total_rows": existing[2],
            "valid_rows": existing[3],
            "invalid_rows": existing[4],
            "promoted_rows": existing[5],
            "completed_at": existing[6].isoformat() if existing[6] else None,
        }
        return batch_id, True, summary

    # A retry reuses the checksum's audit batch and replaces only its own staging
    # rows.  No other source batch or master record is deleted.
    cursor.execute(
        "DELETE FROM public.staging_organizations WHERE import_batch_id = %s",
        (batch_id,),
    )
    cursor.execute(
        """
        UPDATE public.organization_import_batches
        SET source_filename = %s,
            source_size_bytes = %s,
            status = 'STAGING',
            total_rows = 0,
            valid_rows = 0,
            invalid_rows = 0,
            promoted_rows = 0,
            error_summary = '[]'::JSONB,
            started_at = CURRENT_TIMESTAMP,
            completed_at = NULL
        WHERE import_batch_id = %s
        """,
        (str(source_path), source_size, batch_id),
    )
    return batch_id, False, None


def stage_records(
    cursor: Any,
    import_batch_id: str,
    records: Sequence[CsvRecord],
    batch_size: int,
) -> None:
    insert_sql = """
        INSERT INTO public.staging_organizations (
            organization_id,
            organization_name,
            organization_name_normalized,
            organization_name_search_key,
            organization_type_code,
            organization_level,
            parent_organization_id,
            province_name,
            management,
            import_batch_id,
            row_number
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for offset in range(0, len(records), batch_size):
        parameters = []
        for row_number, values in records[offset : offset + batch_size]:
            parameters.append(values + (import_batch_id, row_number))
        cursor.executemany(insert_sql, parameters)

    cursor.execute(
        """
        UPDATE public.organization_import_batches
        SET total_rows = %s,
            status = 'VALIDATING'
        WHERE import_batch_id = %s
        """,
        (len(records), import_batch_id),
    )


def append_validation_error(
    cursor: Any,
    import_batch_id: str,
    error_code: str,
    predicate_sql: str,
) -> int:
    """Append a fixed validation code to all batch rows matching a fixed rule."""
    statement = """
        UPDATE public.staging_organizations AS staging
        SET validation_errors = staging.validation_errors || %s::JSONB
        WHERE staging.import_batch_id = %s
          AND ({predicate})
    """.format(predicate=predicate_sql)
    cursor.execute(statement, (json.dumps([error_code]), import_batch_id))
    return int(cursor.rowcount)


def validate_source_normalization(
    cursor: Any,
    import_batch_id: str,
    records: Sequence[CsvRecord],
    batch_size: int,
) -> None:
    """Recompute normalization and flag source columns that do not match it."""
    mismatches: List[Tuple[str, str, int]] = []
    name_index = EXPECTED_COLUMNS.index("organization_name")
    normalized_index = EXPECTED_COLUMNS.index("organization_name_normalized")
    search_key_index = EXPECTED_COLUMNS.index("organization_name_search_key")

    for row_number, values in records:
        canonical_name = values[name_index]
        computed_normalized = normalize_organization_name(canonical_name)
        computed_search_key = build_search_key(canonical_name)
        errors = []
        if values[normalized_index] != computed_normalized:
            errors.append("NORMALIZED_NAME_MISMATCH")
        if values[search_key_index] != computed_search_key:
            errors.append("SEARCH_KEY_MISMATCH")
        if errors:
            mismatches.append((json.dumps(errors), import_batch_id, row_number))

    update_sql = """
        UPDATE public.staging_organizations
        SET validation_errors = validation_errors || %s::JSONB
        WHERE import_batch_id = %s
          AND row_number = %s
    """
    for offset in range(0, len(mismatches), batch_size):
        cursor.executemany(update_sql, mismatches[offset : offset + batch_size])


def validate_staging(
    cursor: Any,
    import_batch_id: str,
    records: Sequence[CsvRecord],
    batch_size: int,
) -> Dict[str, Any]:
    """Apply deterministic batch validation and retain every row-level error."""
    cursor.execute(
        """
        UPDATE public.staging_organizations
        SET validation_status = 'PENDING',
            validation_errors = '[]'::JSONB
        WHERE import_batch_id = %s
        """,
        (import_batch_id,),
    )

    validate_source_normalization(
        cursor, import_batch_id, records, batch_size
    )

    for column in REQUIRED_COLUMNS:
        append_validation_error(
            cursor,
            import_batch_id,
            "MISSING_{0}".format(column.upper()),
            "NULLIF(btrim(staging.{0}), '') IS NULL".format(column),
        )

    append_validation_error(
        cursor,
        import_batch_id,
        "INVALID_MANAGEMENT",
        "NULLIF(btrim(staging.management), '') IS NOT NULL "
        "AND btrim(staging.management) NOT IN ('BCA', 'BQP')",
    )
    append_validation_error(
        cursor,
        import_batch_id,
        "SELF_PARENT_REFERENCE",
        "NULLIF(btrim(staging.organization_id), '') IS NOT NULL "
        "AND btrim(staging.parent_organization_id) = "
        "btrim(staging.organization_id)",
    )
    child_levels_sql = ", ".join(
        "'{0}'".format(level) for level in CHILD_ORGANIZATION_LEVELS
    )
    append_validation_error(
        cursor,
        import_batch_id,
        "PARENT_REQUIRED",
        "btrim(staging.organization_level) IN ({0}) "
        "AND NULLIF(btrim(staging.parent_organization_id), '') IS NULL".format(
            child_levels_sql
        ),
    )
    append_validation_error(
        cursor,
        import_batch_id,
        "DUPLICATE_ORGANIZATION_ID_IN_BATCH",
        """
        NULLIF(btrim(staging.organization_id), '') IS NOT NULL
        AND btrim(staging.organization_id) IN (
            SELECT btrim(duplicates.organization_id)
            FROM public.staging_organizations AS duplicates
            WHERE duplicates.import_batch_id = staging.import_batch_id
              AND NULLIF(btrim(duplicates.organization_id), '') IS NOT NULL
            GROUP BY btrim(duplicates.organization_id)
            HAVING count(*) > 1
        )
        """,
    )
    append_validation_error(
        cursor,
        import_batch_id,
        "PARENT_ORGANIZATION_NOT_FOUND",
        """
        NULLIF(btrim(staging.parent_organization_id), '') IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM public.staging_organizations AS staged_parent
            WHERE staged_parent.import_batch_id = staging.import_batch_id
              AND btrim(staged_parent.organization_id) =
                  btrim(staging.parent_organization_id)
        )
        AND NOT EXISTS (
            SELECT 1
            FROM public.organizations AS master_parent
            WHERE master_parent.organization_id =
                  btrim(staging.parent_organization_id)
        )
        """,
    )

    cursor.execute(
        """
        UPDATE public.staging_organizations
        SET validation_status = CASE
            WHEN jsonb_array_length(validation_errors) = 0 THEN 'VALID'
            ELSE 'INVALID'
        END
        WHERE import_batch_id = %s
        """,
        (import_batch_id,),
    )
    cursor.execute(
        """
        SELECT
            count(*) FILTER (WHERE validation_status = 'VALID') AS valid_rows,
            count(*) FILTER (WHERE validation_status = 'INVALID') AS invalid_rows
        FROM public.staging_organizations
        WHERE import_batch_id = %s
        """,
        (import_batch_id,),
    )
    counts = cursor.fetchone()
    valid_rows = int(counts[0])
    invalid_rows = int(counts[1])

    cursor.execute(
        """
        SELECT errors.error_code, count(*) AS affected_rows
        FROM public.staging_organizations AS staging
        CROSS JOIN LATERAL jsonb_array_elements_text(
            staging.validation_errors
        ) AS errors(error_code)
        WHERE staging.import_batch_id = %s
        GROUP BY errors.error_code
        ORDER BY errors.error_code
        """,
        (import_batch_id,),
    )
    error_summary = [
        {"code": row[0], "affected_rows": int(row[1])}
        for row in cursor.fetchall()
    ]

    next_status = "VALIDATION_FAILED" if invalid_rows else "PROMOTING"
    cursor.execute(
        """
        UPDATE public.organization_import_batches
        SET valid_rows = %s,
            invalid_rows = %s,
            status = %s,
            error_summary = %s::JSONB,
            completed_at = CASE
                WHEN %s = 'VALIDATION_FAILED' THEN CURRENT_TIMESTAMP
                ELSE NULL
            END
        WHERE import_batch_id = %s
        """,
        (
            valid_rows,
            invalid_rows,
            next_status,
            json.dumps(error_summary),
            next_status,
            import_batch_id,
        ),
    )
    return {
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "error_summary": error_summary,
    }


def promote_to_master(cursor: Any, import_batch_id: str, valid_rows: int) -> int:
    """Upsert a fully valid batch and return the number of changed master rows."""
    cursor.execute("SET CONSTRAINTS organizations_parent_fk DEFERRED")
    cursor.execute(
        """
        WITH changed AS (
            INSERT INTO public.organizations AS target (
                organization_id,
                organization_name,
                normalized_name,
                search_key,
                organization_type_code,
                organization_level,
                parent_organization_id,
                province_name,
                management
            )
            SELECT
                btrim(staging.organization_id),
                btrim(staging.organization_name),
                btrim(staging.organization_name_normalized),
                btrim(staging.organization_name_search_key),
                btrim(staging.organization_type_code),
                btrim(staging.organization_level),
                NULLIF(btrim(staging.parent_organization_id), ''),
                btrim(staging.province_name),
                btrim(staging.management)
            FROM public.staging_organizations AS staging
            WHERE staging.import_batch_id = %s
              AND staging.validation_status = 'VALID'
            ORDER BY staging.row_number
            ON CONFLICT (organization_id) DO UPDATE
            SET organization_name = EXCLUDED.organization_name,
                normalized_name = EXCLUDED.normalized_name,
                search_key = EXCLUDED.search_key,
                organization_type_code = EXCLUDED.organization_type_code,
                organization_level = EXCLUDED.organization_level,
                parent_organization_id = EXCLUDED.parent_organization_id,
                province_name = EXCLUDED.province_name,
                management = EXCLUDED.management,
                updated_at = CURRENT_TIMESTAMP
            WHERE (
                target.organization_name,
                target.normalized_name,
                target.search_key,
                target.organization_type_code,
                target.organization_level,
                target.parent_organization_id,
                target.province_name,
                target.management
            ) IS DISTINCT FROM (
                EXCLUDED.organization_name,
                EXCLUDED.normalized_name,
                EXCLUDED.search_key,
                EXCLUDED.organization_type_code,
                EXCLUDED.organization_level,
                EXCLUDED.parent_organization_id,
                EXCLUDED.province_name,
                EXCLUDED.management
            )
            RETURNING 1
        )
        SELECT count(*) FROM changed
        """,
        (import_batch_id,),
    )
    changed_rows = int(cursor.fetchone()[0])

    cursor.execute(
        """
        UPDATE public.organization_import_batches
        SET status = 'COMPLETED',
            promoted_rows = %s,
            completed_at = CURRENT_TIMESTAMP
        WHERE import_batch_id = %s
        """,
        (valid_rows, import_batch_id),
    )
    return changed_rows


def import_records(
    connection: Any,
    source_path: Path,
    source_sha256: str,
    source_size: int,
    records: Sequence[CsvRecord],
    batch_size: int,
    force: bool,
) -> Dict[str, Any]:
    with connection.cursor() as cursor:
        import_batch_id, skipped, previous = prepare_import_batch(
            cursor,
            source_path,
            source_sha256,
            source_size,
            force,
        )
        if skipped:
            result = {
                "import_batch_id": import_batch_id,
                "source_sha256": source_sha256,
                "status": "COMPLETED",
                "skipped": True,
                "reason": "identical source checksum was already completed",
            }
            result.update(previous or {})
            return result

        stage_records(cursor, import_batch_id, records, batch_size)
        validation = validate_staging(
            cursor, import_batch_id, records, batch_size
        )
        if validation["invalid_rows"]:
            return {
                "import_batch_id": import_batch_id,
                "source_sha256": source_sha256,
                "status": "VALIDATION_FAILED",
                "skipped": False,
                "total_rows": len(records),
                "valid_rows": validation["valid_rows"],
                "invalid_rows": validation["invalid_rows"],
                "error_summary": validation["error_summary"],
            }

        changed_rows = promote_to_master(
            cursor, import_batch_id, int(validation["valid_rows"])
        )
        return {
            "import_batch_id": import_batch_id,
            "source_sha256": source_sha256,
            "status": "COMPLETED",
            "skipped": False,
            "total_rows": len(records),
            "valid_rows": validation["valid_rows"],
            "invalid_rows": 0,
            "promoted_rows": validation["valid_rows"],
            "master_rows_changed": changed_rows,
        }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    source_path = args.csv_path.resolve()

    try:
        records = read_source_csv(source_path)
        source_sha256 = file_sha256(source_path)
        source_size = source_path.stat().st_size
        connection = connect_database(args.dsn)
    except Exception as exc:
        print("Import setup failed: {0}".format(exc), file=sys.stderr)
        return 1

    try:
        if not args.skip_init:
            initialize_database(
                connection,
                args.schema_file.resolve(),
                args.indexes_file.resolve(),
            )

        try:
            result = import_records(
                connection,
                source_path,
                source_sha256,
                source_size,
                records,
                args.batch_size,
                args.force,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if result["status"] == "VALIDATION_FAILED":
            print(
                "No master rows were changed. Inspect staging_organizations "
                "for this import_batch_id.",
                file=sys.stderr,
            )
            return 2
        return 0
    except Exception as exc:
        print("Import failed; transaction rolled back: {0}".format(exc), file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
