---
title: Tra Cuu Bca Bqp
emoji: 🏛️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Organization Matching Registry — BCA / BQP

Version 1 resolves a user query to one canonical organization first, then performs a separate registry lookup for `management` (`BCA` or `BQP`). Fuzzy similarity never predicts the management authority.

The implementation guide, verified dataset audit, setup commands, matching contract, benchmark design, and acceptance gates are documented in [`docs/IMPLEMENTATION_GUIDE.vi.md`](docs/IMPLEMENTATION_GUIDE.vi.md).

## Core contract

```python
result = search_organization(
    organization_id=None,
    organization_name=None,
    province_name=None,
    organization_type=None,
)
```

Resolved deterministic matches return the canonical organization plus `management`. Unresolved deterministic collisions return `AMBIGUOUS_MATCH`; approximate results return `FUZZY_CANDIDATES`; neither unresolved response exposes or infers `management`.

## Local setup

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
docker compose up -d postgres
```

Run the test suite with:

```text
pytest
```

The audited CSV contains 500 semantically missing parent links and mostly reflects the pre-2025 district structure. The PostgreSQL loader therefore stages it but intentionally refuses to promote it unchanged. Use the in-memory repository for matching-engine development, or remediate/replace the source before master promotion.

Detailed setup, audit evidence, database commands, benchmark results, and release gates are in the implementation guide.
