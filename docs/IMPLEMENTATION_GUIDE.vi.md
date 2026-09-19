# Hướng dẫn triển khai Organization Matching Registry — Version 1

## 1. Kết luận điều hành

Kiến trúc được đề xuất là đúng: hệ thống phải giải quyết hai câu hỏi theo hai lớp độc lập.

```mermaid
flowchart LR
    Q[Query] --> V[Validate + Normalize]
    V --> M[Entity Matching]
    M -->|resolved organization_id| L[Registry Lookup]
    L --> A[BCA hoặc BQP]
    M -->|ambiguous / fuzzy candidates / not found| U[Không lookup management]
```

Code trong repo hiện đã hiện thực hóa invariant này. `OrganizationRecord` dùng trong matching không chứa `management`; `management` chỉ được đọc bằng một operation riêng sau khi resolver đã trả về đúng một canonical `organization_id`.

Tuy nhiên, kết luận “dataset đủ điều kiện làm master hiện hành” cần sửa thành:

- **Đủ cho prototype/benchmark trên một snapshot cũ:** có điều kiện.
- **Đủ cho registry hiện hành năm 2026:** không.
- **Đủ để promote nguyên trạng vào master:** không; staging validation hiện cố ý chặn 500 dòng thiếu parent về mặt ngữ nghĩa.

Hai blocker dữ liệu là:

1. Có 500 `DISTRICT_DEPARTMENT` thiếu `parent_organization_id`, dù mỗi dòng có thể tìm thấy đúng một parent theo `parent name + province + management`.
2. Dataset dùng cấu trúc 63 tỉnh và nhiều tổ chức cấp huyện. Trong khi đó, Nghị quyết 202/2025/QH15 xác định 34 đơn vị hành chính cấp tỉnh; danh mục áp dụng thống nhất từ 01/07/2025 gồm 34 cấp tỉnh và 3.321 cấp xã. Bộ Công an cũng công bố đã giải thể 694 Công an cấp huyện và 5.916 đội từ 01/03/2025. Nguồn: [Nghị quyết 202/2025/QH15](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-quyet-so-202-2025-qh15-ve-sap-xep-don-vi-hanh-chinh-cap-tinh-119250612174148722.htm), [danh mục 34 tỉnh/thành](https://xaydungchinhsach.chinhphu.vn/bang-danh-muc-va-ma-so-cua-34-tinh-thanh-moi-cac-don-vi-hanh-chinh-cap-xa-moi-11925070418263625.htm), [thông tin tổ chức lại của Bộ Công an](https://bocongan.gov.vn/bai-viet/hoat-dong-cua-cong-an-cac-don-vi-dia-phuong-deu-dien-ra-on-dinh-khong-bi-gian-doan-co-ban-khong-co-vuong-mac-d2-t43825), [thông tin tổ chức lại của Bộ Quốc phòng](https://www.mod.gov.vn/home/detail?current=true&urile=wcm%3Apath%3A%2Fmod%2Fsa-mod-site%2Fsa-ttsk%2Fsa-tt-qpan%2Fthuong-tuong-vo-minh-luong-du-chi-dao-cong-bo-quyet-dinh-sap-nhap-to-chuc-lai-bo-chqs-cap-tinh-tai-quan-khu-7).

Vì vậy, bản hiện tại nên được trình bày là **matching engine hoàn chỉnh trên registry snapshot**, còn độ đúng “hiện hành” phụ thuộc vào một source registry mới có provenance và ngày hiệu lực.

## 2. Cấu trúc đã triển khai

```text
organization-matching/
├── data/
│   ├── dataset.csv
│   └── test/matching_test_cases.csv
├── database/
│   ├── schema.sql
│   ├── indexes.sql
│   └── load_data.py
├── preprocessing/
│   ├── normalize.py
│   └── validate.py
├── matching/
│   ├── models.py
│   ├── repository.py
│   ├── exact_match.py
│   ├── alias_match.py
│   ├── candidate_generator.py
│   ├── fuzzy_match.py
│   └── resolver.py
├── search/
│   ├── management_lookup.py
│   └── organization_search.py
├── evaluation/
│   ├── build_test_cases.py
│   ├── evaluate.py
│   └── error_analysis.py
├── tests/
├── compose.yaml
├── pyproject.toml
└── requirements.txt
```

## 3. Phase 1 — Khóa contract

### 3.1 Input

```python
search_organization(
    organization_id=None,
    organization_name=None,
    province_name=None,
    organization_type=None,
)
```

Quy tắc:

- Phải có `organization_id` hoặc `organization_name` sau khi trim.
- `province_name` và `organization_type` là context tùy chọn nhưng, khi đã cung cấp, được xem là ràng buộc strict. Resolver không bỏ qua context để lấy một match “gần đúng”.
- ID chạy trước tên. Nếu ID không tồn tại nhưng có tên, Version 1 tiếp tục thử tên theo đúng pipeline đã yêu cầu.
- `organization_type` được chuẩn hóa về uppercase code.
- Query ngắn vẫn được thử deterministic và alias; chỉ fuzzy bị chặn.
- `parent_organization_id` chưa có trong signature Version 1, nên không thể dùng làm input disambiguation. Nó chỉ xuất hiện trong candidate payload để người dùng phân biệt. Nếu muốn dùng parent làm context, đó là thay đổi contract Version 2.

### 3.2 Output đã resolve

```json
{
  "match_status": "SEARCH_KEY_MATCH",
  "match_score": 100,
  "organization_id": "...",
  "organization_name": "...",
  "province_name": "...",
  "organization_type_code": "...",
  "management": "BCA"
}
```

Chỉ năm deterministic status sau được phép có `management` trong Version 1:

```text
EXACT_ID_MATCH
EXACT_NAME_MATCH
NORMALIZED_MATCH
SEARCH_KEY_MATCH
ALIAS_MATCH
```

### 3.3 Output chưa resolve

```json
{
  "match_status": "FUZZY_CANDIDATES",
  "top1_score": 96,
  "top2_score": 88,
  "score_margin": 8,
  "candidates": [
    {
      "organization_id": "...",
      "organization_name": "...",
      "province_name": "...",
      "organization_type_code": "...",
      "organization_level": "...",
      "parent_organization_id": "...",
      "score": 96,
      "matched_on": "CANONICAL_SEARCH_KEY"
    }
  ]
}
```

`AMBIGUOUS_MATCH`, `FUZZY_CANDIDATES`, `NOT_FOUND`, `INVALID_INPUT` không chứa `management` và không gọi management lookup.

## 4. Phase 2 — Audit dữ liệu thật

### 4.1 Kết quả cấu trúc

| Kiểm tra | Kết quả |
|---|---:|
| Records | 14.303 |
| Columns | 9 |
| File size | 3.920.114 bytes |
| SHA-256 | `0959C42E38610BD50D3C9F51FCF4DEE2BCFFDC61D049C7FD4EB4014B1ECA8F29` |
| Encoding | UTF-8 BOM |
| Duplicate toàn dòng | 0 |
| Unique organization ID | 14.303 |
| Blank ngoài parent | 0 |
| Management BCA | 9.689 |
| Management BQP | 4.614 |
| Parent khác blank | 13.569 |
| Parent tham chiếu không tồn tại | 0 |
| Self-parent / cycle | 0 / 0 |
| Max hierarchy depth | 2 |

Khi đọc CSV bằng thư viện chuẩn, dùng `encoding="utf-8-sig"` để loại BOM khỏi header đầu tiên.

### 4.2 Collision

| Key | Unique | Nhóm trùng | Dòng thuộc nhóm trùng | Max group |
|---|---:|---:|---:|---:|
| Canonical name | 13.960 | 199 | 542 | 10 |
| Normalized name | 13.960 | 199 | 542 | 10 |
| Search key | 13.920 | 239 | 622 | 10 |

Có 40 nhóm search-key là collision thật do bỏ dấu, ví dụ `Phù Ninh/Phú Ninh`, `Tam Dương/Tam Đường`. Không có collision search-key trong cùng province ở snapshot này, nhưng không được biến tính chất tình cờ đó thành unique constraint vĩnh viễn.

### 4.3 Normalization

Toàn bộ 14.303 dòng khớp pipeline runtime; mismatch normalized và search key đều bằng 0.

```text
NFKC
→ casefold/lower
→ punctuation/symbol thành word boundary
→ trim + collapse whitespace
→ normalized_name
→ NFD + bỏ combining marks + đ→d
→ NFC
→ search_key
```

Normalization nằm tại `preprocessing/normalize.py` và phải là source of truth dùng cho import, canonical name, query và alias.

### 4.4 Hierarchy completeness — lỗi bị audit cũ bỏ sót

734 dòng có parent blank, nhưng chỉ khoảng 234 là root hợp lý. Có chính xác 500 dòng `DISTRICT_DEPARTMENT` thiếu parent:

| Nhóm | Số dòng |
|---|---:|
| BCA | 348 |
| BQP | 152 |
| Tổng | 500 |

Mỗi dòng có đúng một parent candidate nếu dùng `parent name + province + management`. Điều này chỉ đủ để tạo remediation proposal; không đủ thẩm quyền tự sửa master. Loader hiện gắn `PARENT_REQUIRED`, đánh batch thất bại và không promote bất kỳ dòng nào.

Quy trình sửa đúng:

1. Không sửa `data/dataset.csv`.
2. Xuất mapping `child_id → proposed_parent_id` kèm evidence.
3. Domain owner duyệt từng mapping hoặc duyệt theo rule có audit trail.
4. Lưu mapping đã duyệt như một source bổ sung/version mới.
5. Chạy lại import, rồi kiểm tra FK, management consistency, type hierarchy và cycle.

### 4.5 Temporal validity — blocker nếu gọi đây là registry hiện hành

- Dataset có 63 province labels; 30/63 nhãn không còn khớp exact danh mục 34 tỉnh/thành hiện hành.
- 6.188/14.303 dòng (43,26%) mang province label cũ.
- 11.805/14.303 dòng (82,54%) có level `DISTRICT` hoặc `DISTRICT_DEPARTMENT`.
- Riêng BCA có 8.125 dòng theo cấu trúc Công an huyện/đội cấp huyện cũ.
- Riêng BQP có 3.680 dòng theo cấu trúc Ban CHQS huyện/phòng ban cấp huyện cũ; Bộ Quốc phòng đã tổ chức lại và thành lập Ban Chỉ huy Phòng thủ khu vực trong mô hình hai cấp.

Để dùng nghiệp vụ thật, source mới cần tối thiểu:

```text
source_system
source_record_id
source_reference
registry_as_of_date
effective_from
effective_to
is_active
successor_organization_id
official_province_code
```

Không có các trường này, engine có thể trả lời đúng “dòng nào trong CSV giống query”, nhưng không chứng minh được “tổ chức nào đang tồn tại và thuộc ai quản lý tại ngày tra cứu”.

## 5. Phase 3–4 — Staging và master

Luồng import:

```text
CSV bytes
  ↓ checksum + batch lineage
staging_organizations (raw text)
  ↓ structural + semantic validation
VALIDATION_FAILED ──→ giữ nguyên staging để audit
  ↓ chỉ khi 100% valid
organizations (transactional upsert)
```

Các bảng đã có:

- `organization_import_batches`: checksum, trạng thái, row counts, error summary.
- `staging_organizations`: nguyên 9 field nguồn + batch ID, row number, imported time, validation status/errors.
- `organizations`: canonical registry.
- `organization_aliases`: known mappings.
- `matching_test_cases`: benchmark DEV/TEST.

Đặc tính quan trọng:

- Import cùng SHA-256 là idempotent.
- Staging giữ TEXT để dữ liệu xấu không bị mất trước khi audit.
- Nếu một dòng invalid, cả batch không promote; tránh master nửa sạch nửa bẩn.
- Self-FK là `DEFERRABLE INITIALLY DEFERRED`, phù hợp bulk import hierarchy trong một transaction.
- `management` có check constraint `BCA/BQP`.
- Alias unique theo `(organization_id, alias_search_key)`, nhưng alias/search key không unique toàn cục vì ambiguity là hợp lệ.

Validation hiện bao gồm:

```text
required fields
management domain
self parent
duplicate ID trong batch
parent FK tồn tại
parent required theo child level
source normalized_name khớp runtime normalization
source search_key khớp runtime normalization
```

Không thêm rule “parent và child phải cùng province”: audit có 46 cross-province links hợp lệ về cấu trúc hiện có.

## 6. Phase 5 — Normalization

```python
from preprocessing.normalize import normalize_name, to_search_key

normalize_name("  CÔNG  AN - Hà Nội ")
# "công an hà nội"

to_search_key("Đơn vị")
# "don vi"
```

Nguyên tắc:

- Không normalize original display name trong master.
- Không để database, import và query có ba implementation khác nhau.
- Punctuation được đổi thành khoảng trắng, không nối hai token.
- Unicode được normalize trước khi lowercase/casefold.
- Test Unicode phải chạy trong terminal UTF-8 (`PYTHONUTF8=1` trên Windows nếu cần).

## 7. Phase 6 — Alias registry

Alias là dữ liệu nghiệp vụ, không phải output do fuzzy “học” ra. Mỗi alias phải có owner, loại và provenance.

```text
ABBREVIATION
SHORT_NAME
FORMER_NAME
COMMON_NAME
```

Quy trình:

1. Thu thập alias từ văn bản chính thức hoặc review log tìm kiếm.
2. Normalize bằng cùng pipeline.
3. Kiểm tra alias collision toàn cục và theo province/type.
4. Cho phép alias trỏ tới nhiều organization; resolver phải trả ambiguous nếu context chưa đủ.
5. Đưa alias case vào DEV/TEST sau khi được duyệt.

Repo chưa tự sinh alias production từ chữ cái đầu vì cách đó tạo false positives. `data/test/aliases.csv` chứa 16 alias/abbreviation **chỉ dùng làm fixture benchmark** theo các mẫu trong requirement; không được import như alias production khi chưa có domain-owner sign-off.

## 8. Phase 7 — Index

Các index chính nằm trong `database/indexes.sql`:

```text
normalized_name
search_key
province_name
organization_type_code
management
parent_organization_id
(search_key, province_name)
(province_name, organization_type_code)
normalized_alias
alias_search_key
```

PostgreSQL lưu ý rằng primary key/unique constraint đã tự tạo unique index; không cần tạo trùng. Với B-tree nhiều cột, hiệu quả cao nhất thường đến từ điều kiện trên cột đứng bên trái, nên thứ tự composite index phải bám query thực tế. Tham khảo [PostgreSQL multicolumn indexes](https://www.postgresql.org/docs/18/indexes-multicolumn.html) và [unique indexes](https://www.postgresql.org/docs/18/indexes-unique.html).

Sau khi có traffic thật, chạy `EXPLAIN (ANALYZE, BUFFERS)` trước khi thêm index mới. Với 14.303 rows, chất lượng candidate quan trọng hơn micro-optimization.

## 9. Phase 8–16 — Resolver

### 9.1 Deterministic order

```text
1. Exact organization ID
2. Exact canonical name
3. Exact normalized name
4. Exact search key
5. Exact alias
6. Fuzzy candidates
```

Tại mỗi deterministic stage:

1. Lấy **tất cả** matches.
2. Áp province nếu user cung cấp.
3. Áp type nếu user cung cấp.
4. Còn 1 → resolve.
5. Còn nhiều → `AMBIGUOUS_MATCH` và dừng.
6. Có deterministic candidates nhưng context loại hết → `NOT_FOUND` với reason context mismatch; không bỏ context và không rơi xuống fuzzy.

Không có `LIMIT 1` ở bước identity resolution.

### 9.2 Candidate blocking

Fuzzy chỉ chạy sau khi deterministic và alias đều fail:

```text
all organizations
  ↓ province nếu có
  ↓ organization type nếu có
  ↓ fetch aliases chỉ cho block này
  ↓ RapidFuzz ranking
```

Không nhận `management` làm input Version 1, nên không block theo management. Điều này cố ý ngăn user hoặc caller biến management thành nhãn gợi ý cho classifier.

### 9.3 Fuzzy ranking

Version 1 hỗ trợ benchmark:

```text
ratio
WRatio
token_sort_ratio
token_set_ratio
```

RapidFuzz trả similarity 0–100; `process.extract` cũng hỗ trợ `limit` và `score_cutoff`. Tham khảo [RapidFuzz scorer API](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) và [process.extract](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html).

Engine hiện:

- So sánh query search key với canonical search key và alias search keys.
- Giữ score tốt nhất cho mỗi organization.
- Deduplicate theo organization ID.
- Sort score giảm dần, ID tăng dần để tie-break deterministic.
- Trả Top-K=5.
- Tính `top1`, `top2`, `margin` cho review.
- Không auto-resolve fuzzy.

Threshold 85 được dùng làm baseline ban đầu theo yêu cầu. Sau bước DEV tuning trên seed hiện có, config mặc định của prototype được khóa tạm ở `WRatio + cutoff 95`; giá trị này vẫn phải retune khi có alias thật và query log thật.

### 9.4 Lookup management

```text
MatchResolution.is_resolved
  ↓ organization_id
lookup_management(repository, organization_id)
  ↓ validate value ∈ {BCA, BQP}
serialize final result
```

Repository matching chỉ select các cột identity. `get_management()` là query riêng. SQLAlchemy adapter sử dụng API `select()`/connection execution kiểu 2.x, phù hợp [SQLAlchemy 2.0 querying guide](https://docs.sqlalchemy.org/en/20/orm/queryguide/index.html).

## 10. Phase 17 — Status model

```text
EXACT_ID_MATCH
EXACT_NAME_MATCH
NORMALIZED_MATCH
SEARCH_KEY_MATCH
ALIAS_MATCH
FUZZY_CANDIDATES
FUZZY_MATCH          # reserved, chưa dùng V1
AMBIGUOUS_MATCH
NOT_FOUND
INVALID_INPUT
```

`BCA`/`BQP` không phải match status.

## 11. Phase 18–20 — Benchmark, metrics, error analysis

### 11.1 Tạo seed benchmark

```powershell
python -m evaluation.build_test_cases `
  --dataset data/dataset.csv `
  --output data/test/matching_test_cases.csv `
  --per-scenario 20
```

File hiện có 330 cases, group-split theo organization ID để mutation của cùng một organization không rơi vào cả DEV và TEST. Mỗi scenario thông thường được stratify 70/30; các scenario invalid/unknown cũng xuất hiện ở cả hai split. Các scenario đã có:

```text
exact ID BCA/BQP
exact canonical name
uppercase/lowercase
không dấu
whitespace
punctuation
one-character typo
multi-character typo
missing/extra word
alias/abbreviation test fixture
same-name ambiguous
same name + province
wrong province
unknown organization
short/empty query
parent organization
```

Đây là synthetic seed, không phải gold set cuối. Alias/abbreviation fixture phải được thay/bổ sung bằng alias registry đã duyệt; typo thực tế phải lấy từ log đã ẩn danh.

### 11.2 Tune chỉ trên DEV

```powershell
python -m evaluation.evaluate --split DEV --all-scorers --threshold 85
python -m evaluation.evaluate --split DEV --scorer WRatio --threshold 95
```

Kết quả seed quan sát được:

| Config | DEV cases | Exact accuracy | Fuzzy Top-1 | Top-3 | Top-5 | Not-found accuracy |
|---|---:|---:|---:|---:|---:|---:|
| WRatio, 90 | 229 | 100% | 94,64% | 100% | 100% | 95,24% |
| WRatio, 95 | 229 | 100% | 87,50% | 92,86% | 92,86% | 100% |

Do V1 không auto-resolve fuzzy, threshold 95 giảm candidate rác mà không tạo wrong management answer trong seed này.

### 11.3 Chỉ mở TEST sau khi khóa config

Config chọn từ DEV: `WRatio`, cutoff 95, Top-K 5.

| Metric trên TEST seed | Kết quả |
|---|---:|
| Cases | 101 |
| Status accuracy | 100% |
| Exact resolution accuracy | 100% |
| Fuzzy Top-1 recall | 95,83% |
| Fuzzy Top-3 recall | 100% |
| Fuzzy Top-5 recall | 100% |
| Ambiguous detection | 100% |
| Not-found detection | 100% |
| False auto-match rate | 0% |
| Management accuracy sau correct resolution | 100% |

Không dùng các con số này để tuyên bố accuracy production: sample nhỏ, synthetic, cùng nguồn với registry và chưa có alias/user-log distribution.

### 11.4 Error analysis

```powershell
python -m evaluation.error_analysis `
  --predictions evaluation/reports/predictions.csv
```

Các category:

```text
NORMALIZATION_ERROR
ALIAS_MISSING
TYPO_ERROR
SAME_NAME_AMBIGUITY
WRONG_PROVINCE
PARENT_CONFUSION
FUZZY_FALSE_POSITIVE
UNKNOWN_FALSE_MATCH
QUERY_TOO_SHORT
```

Sửa đúng layer: alias fail thì bổ sung alias đã duyệt; không hạ fuzzy threshold toàn hệ thống.

### 11.5 Metric ưu tiên

Theo thứ tự:

1. False auto-match rate.
2. Unsafe resolution rate trên ambiguous/unknown queries.
3. Precision của resolved organization.
4. Ambiguous và not-found detection.
5. Top-3/Top-5 recall cho fuzzy review.
6. Coverage.

Coverage thấp nhưng precision cao phù hợp V1 hơn coverage cao và trả nhầm management.

## 12. Phase 21 — Test strategy

Chạy:

```powershell
python -m pytest -q
python -m pytest --cov=preprocessing --cov=matching --cov=search
```

Test suite bao phủ:

- Unicode/whitespace/punctuation/`đ` normalization.
- Exact ID/name/normalized/search key.
- Alias.
- Collision và strict context.
- Candidate blocking.
- Fuzzy Top-K/tie ordering/threshold.
- Query ngắn.
- Unresolved payload không có management.
- Management lookup chỉ xảy ra sau resolve.
- SQLAlchemy repository không select management ở matching query.

Pytest parameterization thích hợp để mở rộng bảng biến thể; xem [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html).

## 13. Cài đặt và chạy

### 13.1 Python

Python 3.11+:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Hoặc với `uv`:

```powershell
uv sync --extra dev
.venv\Scripts\Activate.ps1
```

### 13.2 PostgreSQL

```powershell
docker compose up -d postgres
```

DSN cho importer psycopg:

```powershell
$env:DATABASE_DSN = "postgresql://organization_user:organization_password@localhost:5432/organization_registry"
python database/load_data.py --dsn $env:DATABASE_DSN
```

PostgreSQL `COPY FROM STDIN` có thể thay `executemany` khi volume lớn hơn; với 14.303 dòng, correctness và row-level errors quan trọng hơn. Tham khảo [PostgreSQL COPY](https://www.postgresql.org/docs/18/sql-copy.html).

Với dataset hiện tại, kết quả đúng của importer là exit code 2/`VALIDATION_FAILED`, 500 `PARENT_REQUIRED`, và **0 master rows changed**. Đây là safety gate, không phải lỗi chương trình.

### 13.3 Chạy engine trực tiếp trên snapshot để phát triển

Trong khi chờ remediation/registry mới, có thể dùng in-memory repository cho demo logic:

```python
import pandas as pd

from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from search.organization_search import OrganizationSearchService

rows = pd.read_csv(
    "data/dataset.csv",
    dtype=str,
    keep_default_na=False,
).to_dict("records")

repository = InMemoryOrganizationRepository(rows)
service = OrganizationSearchService(
    repository,
    MatchingConfig(
        fuzzy_scorer="WRatio",
        fuzzy_minimum_score=95,
        fuzzy_top_k=5,
    ),
)

result = service.search_organization(
    organization_name="Cong an Thanh pho Ha Nio",
    province_name="Hà Nội",
)
```

### 13.4 Cấu hình PostgreSQL repository

```python
from sqlalchemy import create_engine

from matching.repository import SqlAlchemyOrganizationRepository
from matching.resolver import MatchingConfig
from search.organization_search import configure_repository, search_organization

engine = create_engine(
    "postgresql+psycopg://organization_user:organization_password@localhost:5432/organization_registry"
)
repository = SqlAlchemyOrganizationRepository.from_engine(engine)
configure_repository(
    repository,
    MatchingConfig(
        fuzzy_scorer="WRatio",
        fuzzy_minimum_score=95,
        fuzzy_top_k=5,
    ),
)

result = search_organization(
    organization_name="...",
    province_name="...",
)
```

## 14. Trình tự triển khai thực tế có acceptance gate

| Bước | Công việc | Gate để đi tiếp |
|---:|---|---|
| 1 | Audit cấu trúc CSV | Header/encoding/row count hợp lệ |
| 2 | Audit semantic và thời gian | Xác định snapshot/current-state rõ ràng |
| 3 | Load staging | Raw data + batch lineage giữ nguyên |
| 4 | Validate | 0 invalid hoặc có remediation được duyệt |
| 5 | Promote master | Transaction thành công, FK/cycle pass |
| 6 | Normalization | Import/query/alias dùng cùng function |
| 7 | Index deterministic fields | Query plan hợp lý |
| 8 | Exact ID/name | Không `LIMIT 1` khi tên có thể trùng |
| 9 | Normalized/search-key | Collision trả ambiguous |
| 10 | Curate alias | Provenance + collision review |
| 11 | Alias matching | Chạy trước fuzzy |
| 12 | Candidate blocking | Context strict, pool không rỗng ngoài ý muốn |
| 13 | Fuzzy Top-K | Không auto-resolve V1 |
| 14 | Resolver | Chỉ một canonical result mới là resolved |
| 15 | Management lookup | Chỉ gọi sau resolve |
| 16 | DEV benchmark | Chọn scorer/cutoff/margin |
| 17 | Khóa config | Không sửa theo TEST |
| 18 | TEST evaluation | Báo cả precision/FMR/coverage |
| 19 | Error analysis | Fix đúng layer |
| 20 | Integration test PostgreSQL | Schema/import/search chạy end-to-end |
| 21 | Data sign-off | Owner xác nhận validity/provenance |
| 22 | Release V1 | Monitoring và audit log sẵn sàng |

## 15. Definition of Done

### Engine V1

- API đúng signature.
- Deterministic pipeline đúng thứ tự.
- Alias trước fuzzy.
- Ambiguity không bị ép Top-1.
- Fuzzy chỉ trả candidate.
- Unresolved không có management.
- Unit/integration tests pass.
- Benchmark có DEV/TEST và error analysis.

### Registry dùng cho đồ án snapshot

- Gắn rõ `registry_as_of_date` và nguồn.
- 500 parent gaps đã được review/remediate hoặc scope tuyên bố không dùng hierarchy.
- Không gọi kết quả là trạng thái hiện hành 2026.

### Registry dùng nghiệp vụ hiện hành

- Có nguồn chính thức mới cho BCA và BQP.
- Có effective dates, active/inactive, successor links.
- Dùng danh mục địa giới/mã hành chính hiện hành.
- Alias former/current names được quản trị.
- Domain owner sign-off.
- Có real-query benchmark, privacy review và monitoring false matches.

## 16. Cách trình bày với giảng viên

Thông điệp ngắn gọn:

> Hệ thống không phân loại BCA/BQP từ chuỗi query. Nó thực hiện entity resolution để tìm canonical organization ID. Chỉ khi ID được resolve chắc chắn, hệ thống mới lookup cột `management` trong Organization Registry. Fuzzy chỉ hỗ trợ tìm candidate và Version 1 không tự động kết luận management từ fuzzy result.

Điểm mạnh của đồ án không nằm ở mô hình ML phức tạp, mà ở data contract, deterministic-first resolution, ambiguity safety, staging/master separation, benchmark có DEV/TEST và quản trị false match.
