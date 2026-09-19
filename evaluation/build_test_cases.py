"""Build a reproducible *seed* benchmark from the organization snapshot.

The generated cases are deliberately synthetic perturbations of canonical
records.  They are useful for regression testing, but must be reviewed and
supplemented with real search logs before threshold tuning is considered
production evidence.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from preprocessing.normalize import normalize_name, to_search_key


REQUIRED_COLUMNS = (
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

OUTPUT_COLUMNS = (
    "test_id",
    "query_name",
    "query_id",
    "province_name",
    "organization_type",
    "expected_organization_id",
    "expected_match_status",
    "expected_management",
    "scenario",
    "dataset_split",
)


def _split_for(key: str) -> str:
    """Keep every mutation of one organization in the same data split."""

    bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 10
    return "DEV" if bucket < 7 else "TEST"


def _sample(frame: pd.DataFrame, count: int, seed: int) -> pd.DataFrame:
    if frame.empty:
        return frame
    work = frame.copy()
    work["_evaluation_split"] = work.organization_id.map(_split_for)
    requested = min(count, len(work))
    dev_target = min(round(requested * 0.7), requested)
    test_target = requested - dev_target
    parts: list[pd.DataFrame] = []
    for split, target, offset in (
        ("DEV", dev_target, 0),
        ("TEST", test_target, 1),
    ):
        pool = work[work._evaluation_split.eq(split)]
        if target:
            parts.append(
                pool.sample(n=min(target, len(pool)), random_state=seed + offset)
            )
    result = pd.concat(parts) if parts else work.iloc[0:0]
    if len(result) < requested:
        remaining = work.drop(index=result.index)
        result = pd.concat(
            [
                result,
                remaining.sample(
                    n=requested - len(result), random_state=seed + 2
                ),
            ]
        )
    return result.drop(columns="_evaluation_split")


def _one_typo(search_key: str) -> str:
    characters = list(search_key)
    for index in range(len(characters) - 1, 0, -1):
        if characters[index].isalnum() and characters[index - 1].isalnum():
            characters[index - 1], characters[index] = (
                characters[index],
                characters[index - 1],
            )
            candidate = "".join(characters)
            if candidate != search_key:
                return candidate
    return search_key + "x"


def _drop_middle_word(search_key: str) -> str:
    words = search_key.split()
    if len(words) < 3:
        return search_key
    del words[len(words) // 2]
    return " ".join(words)


def _two_typos(search_key: str) -> str:
    """Make two deterministic substitutions without changing token count."""

    characters = list(search_key)
    positions = [
        index
        for index, character in enumerate(characters)
        if character.isalpha()
    ]
    if len(positions) < 4:
        return _one_typo(search_key + "x")
    for index in (positions[len(positions) // 3], positions[-2]):
        characters[index] = "x" if characters[index] != "x" else "z"
    return "".join(characters)


def build_cases(
    data: pd.DataFrame,
    per_scenario: int = 20,
    aliases: pd.DataFrame | None = None,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    counter = 0

    def add(
        *,
        scenario: str,
        query_name: str = "",
        query_id: str = "",
        province_name: str = "",
        organization_type: str = "",
        expected_organization_id: str = "",
        expected_match_status: str,
        expected_management: str = "",
        split_key: str | None = None,
        dataset_split: str | None = None,
    ) -> None:
        nonlocal counter
        counter += 1
        key = split_key or f"fixed:{scenario}:{counter}"
        records.append(
            {
                "test_id": f"TC-{counter:05d}",
                "query_name": query_name,
                "query_id": query_id,
                "province_name": province_name,
                "organization_type": organization_type,
                "expected_organization_id": expected_organization_id,
                "expected_match_status": expected_match_status,
                "expected_management": expected_management,
                "scenario": scenario,
                "dataset_split": dataset_split or _split_for(key),
            }
        )

    # Deterministic transformations use globally unique search keys so their
    # expected organization is unambiguous without context.
    key_counts = data.groupby("organization_name_search_key")[
        "organization_id"
    ].transform("size")
    unique = data[key_counts == 1].copy()

    for management, seed in (("BCA", 11), ("BQP", 12)):
        id_pool = unique[unique.management.eq(management)]
        for _, row in _sample(id_pool, per_scenario // 2, seed).iterrows():
            add(
                scenario=f"exact_id_{management.lower()}",
                query_id=row.organization_id,
                expected_organization_id=row.organization_id,
                expected_match_status="EXACT_ID_MATCH",
                expected_management=row.management,
                split_key=row.organization_id,
            )

    for _, row in _sample(unique, per_scenario, 12).iterrows():
        add(
            scenario="exact_canonical_name",
            query_name=row.organization_name,
            expected_organization_id=row.organization_id,
            expected_match_status="EXACT_NAME_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    uppercase_pool = unique[
        unique.organization_name.str.upper() != unique.organization_name
    ]
    for _, row in _sample(uppercase_pool, per_scenario, 13).iterrows():
        add(
            scenario="uppercase",
            query_name=row.organization_name.upper(),
            expected_organization_id=row.organization_id,
            expected_match_status="NORMALIZED_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    lowercase_pool = unique[
        unique.organization_name.str.lower() != unique.organization_name
    ]
    for _, row in _sample(lowercase_pool, per_scenario, 14).iterrows():
        add(
            scenario="lowercase",
            query_name=row.organization_name.lower(),
            expected_organization_id=row.organization_id,
            expected_match_status="NORMALIZED_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    accent_pool = unique[
        unique.organization_name_normalized
        != unique.organization_name_search_key
    ]
    for _, row in _sample(accent_pool, per_scenario, 15).iterrows():
        add(
            scenario="without_diacritics",
            query_name=row.organization_name_search_key,
            expected_organization_id=row.organization_id,
            expected_match_status="SEARCH_KEY_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    for _, row in _sample(unique, per_scenario, 16).iterrows():
        query = "  " + "   ".join(row.organization_name.split()) + "  "
        add(
            scenario="extra_whitespace",
            query_name=query,
            expected_organization_id=row.organization_id,
            expected_match_status="NORMALIZED_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    punctuation_pool = unique[
        unique.organization_name.str.contains(r"[-–—/,.;:]", regex=True)
    ]
    for _, row in _sample(punctuation_pool, per_scenario, 17).iterrows():
        query = row.organization_name.replace("-", ",").replace("–", ",")
        if query == row.organization_name:
            query = row.organization_name.replace("/", " - ").replace(";", ",")
        add(
            scenario="punctuation_variant",
            query_name=query,
            expected_organization_id=row.organization_id,
            expected_match_status="NORMALIZED_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    fuzzy_pool = unique[
        unique.organization_name_search_key.str.len().ge(12)
        & unique.organization_name_search_key.str.split().str.len().ge(3)
    ]
    for _, row in _sample(fuzzy_pool, per_scenario, 18).iterrows():
        add(
            scenario="single_character_typo",
            query_name=_one_typo(row.organization_name_search_key),
            expected_organization_id=row.organization_id,
            expected_match_status="FUZZY_CANDIDATES",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    for _, row in _sample(fuzzy_pool, per_scenario, 19).iterrows():
        add(
            scenario="missing_word",
            query_name=_drop_middle_word(row.organization_name_search_key),
            expected_organization_id=row.organization_id,
            expected_match_status="FUZZY_CANDIDATES",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    for _, row in _sample(fuzzy_pool, per_scenario, 20).iterrows():
        add(
            scenario="extra_word",
            query_name=row.organization_name_search_key + " don vi",
            expected_organization_id=row.organization_id,
            expected_match_status="FUZZY_CANDIDATES",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    multi_typo_pool = fuzzy_pool[
        fuzzy_pool.organization_name_search_key.str.len().ge(25)
    ]
    for _, row in _sample(multi_typo_pool, per_scenario, 24).iterrows():
        add(
            scenario="multi_character_typo",
            query_name=_two_typos(row.organization_name_search_key),
            expected_organization_id=row.organization_id,
            expected_match_status="FUZZY_CANDIDATES",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    if aliases is not None and not aliases.empty:
        alias_cases = aliases.merge(
            data[
                [
                    "organization_id",
                    "province_name",
                    "organization_type_code",
                    "management",
                ]
            ],
            on="organization_id",
            how="inner",
            validate="many_to_one",
        )
        for _, row in _sample(alias_cases, per_scenario, 25).iterrows():
            add(
                scenario="alias_abbreviation",
                query_name=row.alias_name,
                province_name=row.province_name,
                expected_organization_id=row.organization_id,
                expected_match_status="ALIAS_MATCH",
                expected_management=row.management,
                split_key=row.organization_id,
            )

    # Exact-name collisions exercise both unresolved and context-resolved paths.
    duplicate_groups = [
        group
        for _, group in data.groupby("organization_name", sort=True)
        if len(group) > 1
    ]
    duplicate_representatives = pd.DataFrame(
        [
            group.sort_values("organization_id").iloc[0]
            for group in duplicate_groups
        ]
    )
    selected_duplicate_ids = set(
        _sample(duplicate_representatives, per_scenario, 23).organization_id
    )
    selected_duplicate_groups = [
        group
        for group in duplicate_groups
        if group.sort_values("organization_id").iloc[0].organization_id
        in selected_duplicate_ids
    ]
    for group in selected_duplicate_groups:
        name = str(group.iloc[0].organization_name)
        add(
            scenario="same_name_ambiguous",
            query_name=name,
            expected_match_status="AMBIGUOUS_MATCH",
            split_key=f"ambiguous:{name}",
        )
        row = group.sort_values("organization_id").iloc[0]
        add(
            scenario="same_name_with_province",
            query_name=name,
            province_name=row.province_name,
            expected_organization_id=row.organization_id,
            expected_match_status="EXACT_NAME_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    provinces = sorted(data.province_name.unique())
    for _, row in _sample(unique, per_scenario, 21).iterrows():
        wrong_province = next(
            province for province in provinces if province != row.province_name
        )
        add(
            scenario="wrong_province",
            query_name=row.organization_name,
            province_name=wrong_province,
            expected_match_status="NOT_FOUND",
            split_key=row.organization_id,
        )

    parent_ids = set(data.parent_organization_id) - {""}
    parent_pool = unique[unique.organization_id.isin(parent_ids)]
    for _, row in _sample(parent_pool, per_scenario, 22).iterrows():
        add(
            scenario="parent_organization",
            query_name=row.organization_name,
            province_name=row.province_name,
            expected_organization_id=row.organization_id,
            expected_match_status="EXACT_NAME_MATCH",
            expected_management=row.management,
            split_key=row.organization_id,
        )

    unknown_queries = (
        "to chuc hoan toan khong ton tai xyz 987",
        "cong an thanh pho khong ton tai",
        "cong an huyen khong co that",
        "doi canh sat don vi ao",
        "phong tham muu dia phuong xyz",
        "ban chi huy quan su huyen khong ton tai",
        "bo chi huy quan su tinh gia dinh",
        "cuc quan ly nghiep vu khong co",
        "hoc vien quan su ao 123",
        "don bien phong cua khau khong ton tai",
    )
    for index, query in enumerate(unknown_queries):
        add(
            scenario="unknown_organization",
            query_name=query,
            expected_match_status="NOT_FOUND",
            dataset_split="DEV" if index < 7 else "TEST",
        )

    # Both splits must exercise input rejection independently.
    for split in ("DEV", "TEST"):
        add(
            scenario="short_query",
            query_name="x",
            expected_match_status="INVALID_INPUT",
            dataset_split=split,
        )
        add(
            scenario="empty_query",
            query_name="",
            expected_match_status="INVALID_INPUT",
            dataset_split=split,
        )

    result = pd.DataFrame.from_records(records, columns=OUTPUT_COLUMNS)
    return result.sort_values("test_id").reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/dataset.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/test/matching_test_cases.csv"),
    )
    parser.add_argument("--per-scenario", type=int, default=20)
    parser.add_argument(
        "--aliases",
        type=Path,
        default=Path("data/test/aliases.csv"),
        help="Reviewed/test-only alias registry used to generate alias cases.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = pd.read_csv(args.dataset, dtype=str, keep_default_na=False)
    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError(f"dataset is missing columns: {missing}")

    # Refuse to generate expectations from inconsistent precomputed fields.
    normalized_ok = data.apply(
        lambda row: normalize_name(row.organization_name)
        == row.organization_name_normalized,
        axis=1,
    )
    search_key_ok = data.apply(
        lambda row: to_search_key(row.organization_name)
        == row.organization_name_search_key,
        axis=1,
    )
    if not normalized_ok.all() or not search_key_ok.all():
        raise ValueError(
            "source normalization differs from the runtime pipeline; audit first"
        )

    aliases = None
    if args.aliases.is_file():
        aliases = pd.read_csv(args.aliases, dtype=str, keep_default_na=False)
    cases = build_cases(
        data,
        per_scenario=args.per_scenario,
        aliases=aliases,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cases.to_csv(args.output, index=False, encoding="utf-8")
    print(f"wrote {len(cases)} seed cases to {args.output}")
    print(cases.groupby(["dataset_split", "scenario"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
