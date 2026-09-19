"""Hugging Face Spaces Application — Organization Matching Registry (BCA / BQP).

Strict Deterministic Binary Search (100% Match or UNKNOWN).
Native ZeroGPU & Hugging Face Spaces compatibility.
"""

from __future__ import annotations

from pathlib import Path
import html
import pandas as pd
import gradio as gr

from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from search.organization_search import OrganizationSearchService
from preprocessing.normalize import normalize_name, to_search_key

# ── 1. Load Dataset into In-Memory Repository ──────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_PATH = _PROJECT_ROOT / "data" / "dataset.csv"
ALIASES_PATH = _PROJECT_ROOT / "data" / "test" / "aliases.csv"

print("[INFO] Loading dataset into memory...")
df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False)
rows = df.to_dict("records")

aliases = []
if ALIASES_PATH.is_file():
    aliases = pd.read_csv(ALIASES_PATH, dtype=str, keep_default_na=False).to_dict("records")

repo = InMemoryOrganizationRepository(rows, aliases)

total_orgs = len(df)
bca_count = int((df["management"] == "BCA").sum())
bqp_count = int((df["management"] == "BQP").sum())
province_count = int(df["province_name"].nunique())
provinces = [""] + sorted([p for p in df["province_name"].unique() if p])
type_codes = [""] + sorted([t for t in df["organization_type_code"].unique() if t])

print(f"[INFO] Registry loaded: {total_orgs:,} organizations ({bca_count:,} BCA, {bqp_count:,} BQP)")

TYPE_CODE_LABELS = {
    "POLICE_PROVINCE": "Công an tỉnh/TP",
    "POLICE_DEPARTMENT": "Phòng ban CA tỉnh",
    "POLICE_DISTRICT": "Công an huyện/quận",
    "POLICE_DISTRICT_DEPT": "Đội CA huyện/quận",
    "POLICE_PRISON": "Trại giam",
    "POLICE_HOSPITAL": "Bệnh viện CA",
    "MILITARY_PROVINCE": "Bộ CHQS tỉnh/TP",
    "MILITARY_DEPARTMENT": "Phòng ban QS tỉnh",
    "MILITARY_DISTRICT": "Ban CHQS huyện/quận",
    "MILITARY_DISTRICT_DEPT": "Đội QS huyện/quận",
    "MILITARY_BORDER_CMD": "Đồn Biên phòng - BCH",
    "MILITARY_BORDER_POST": "Đồn Biên phòng - Trạm",
    "MILITARY_BORDER_SQUADRON": "Đồn BP - Đại đội",
    "MILITARY_HOSPITAL": "Bệnh viện QY",
    "MILITARY_REGION": "Quân khu",
    "MILITARY_SERVICE": "Quân chủng/Binh chủng",
    "ACADEMY": "Học viện",
    "UNIVERSITY": "Đại học / Trường",
    "GENERAL_DEPARTMENT": "Tổng cục/Cục trực thuộc",
    "MINISTRY_DEPARTMENT": "Cục Bộ",
}

STATUS_INFO = {
    "EXACT_ID_MATCH": "Khớp chính xác mã ID",
    "EXACT_NAME_MATCH": "Khớp chính xác tên tổ chức",
    "NORMALIZED_MATCH": "Khớp tên sau chuẩn hóa",
    "SEARCH_KEY_MATCH": "Khớp không dấu (Search Key)",
    "ALIAS_MATCH": "Khớp tên viết tắt / Tên gọi khác",
    "RESOLVED": "Khớp chính xác",
    "NOT_FOUND": "Không có dữ liệu",
    "INVALID_INPUT": "Dữ liệu không hợp lệ",
}

# ── ZeroGPU Support ──────────────────────────────────────────────────────────
try:
    import spaces
except ImportError:
    spaces = None

if spaces is not None:
    @spaces.GPU
    def _zero_gpu_check():
        return True

def _gpu_decorator(func):
    if spaces is not None:
        return spaces.GPU(func)
    return func


# ── 2. Strict Binary Search Logic ─────────────────────────────────────────────

@_gpu_decorator
def search_organization_ui(org_name, org_id, province, org_type):
    org_name = (org_name or "").strip()
    org_id = (org_id or "").strip()
    province = province if province else None
    org_type = org_type if org_type else None

    if not org_name and not org_id:
        return """
        <div class="result-card">
            <div class="banner banner-warn">
                ⚠️ <strong>Vui lòng nhập Tên tổ chức hoặc Mã tổ chức (ID) để bắt đầu tra cứu.</strong>
            </div>
        </div>
        """

    # Strict deterministic service (no fuzzy guessing, no candidates)
    config = MatchingConfig(strict_mode=True)
    service = OrganizationSearchService(repo, config)

    res = service.search_organization(
        organization_id=org_id or None,
        organization_name=org_name or None,
        province_name=province,
        organization_type=org_type,
    )

    is_matched = bool(res.get("management"))
    status = "MATCH_100" if is_matched else "UNKNOWN"
    match_status = res.get("match_status", "UNKNOWN")
    norm_val = normalize_name(org_name) if org_name else "—"
    search_key_val = to_search_key(org_name) if org_name else "—"

    html_out = ['<div class="result-container">']

    # ── CASE 1: MATCH_100 (ĐÚNG 100%) ──
    if is_matched:
        mgmt = res.get("management", "N/A")
        is_bca = mgmt == "BCA"
        is_bqp = mgmt == "BQP"
        badge_cls = "badge-bca" if is_bca else ("badge-bqp" if is_bqp else "badge-bca")
        mgmt_name = "Bộ Công an" if is_bca else ("Bộ Quốc phòng" if is_bqp else mgmt)
        info_label = STATUS_INFO.get(match_status, match_status)
        type_code = res.get("organization_type_code", "")
        type_label = TYPE_CODE_LABELS.get(type_code, type_code or "—")

        html_out.append(f"""
        <div class="result-card">
            <div class="badge-header">
                <div class="badge-subtitle">KẾT LUẬN CƠ QUAN QUẢN LÝ</div>
                <div class="{badge_cls}">{html.escape(mgmt)}</div>
                <div class="badge-label">{html.escape(mgmt_name)}</div>
                <div style="margin-top: 10px;">
                    <span class="status-chip chip-resolved">✅ ĐÚNG 100% — {html.escape(info_label)}</span>
                </div>
            </div>

            <div class="section-title">📋 Chi tiết tổ chức xác định</div>
            <div class="info-table">
                <div class="info-row">
                    <span class="info-k">Mã tổ chức</span>
                    <span class="info-v mono">{html.escape(res.get('organization_id') or '—')}</span>
                </div>
                <div class="info-row">
                    <span class="info-k">Tên chính thức</span>
                    <span class="info-v bold">{html.escape(res.get('organization_name') or '—')}</span>
                </div>
                <div class="info-row">
                    <span class="info-k">Tỉnh / Thành phố</span>
                    <span class="info-v">{html.escape(res.get('province_name') or 'Trung ương / Toàn quốc')}</span>
                </div>
                <div class="info-row">
                    <span class="info-k">Loại tổ chức</span>
                    <span class="info-v">{html.escape(type_label)} <code class="type-code">({html.escape(type_code)})</code></span>
                </div>
                <div class="info-row">
                    <span class="info-k">Cơ quan chủ quản</span>
                    <span class="info-v" style="color: {'#60A5FA' if is_bca else '#34D399'}; font-weight: 700;">
                        {html.escape(mgmt)} — {html.escape(mgmt_name)}
                    </span>
                </div>
            </div>
        </div>
        """)

    # ── CASE 2: UNKNOWN (KHÔNG CÓ DỮ LIỆU) ──
    else:
        html_out.append(f"""
        <div class="result-card">
            <div style="text-align: center; margin-bottom: 12px;">
                <span class="status-chip chip-notfound">❌ UNKNOWN (Không có dữ liệu)</span>
            </div>
            <div class="banner banner-danger">
                ❌ <strong>Không có dữ liệu cho đơn vị này:</strong> Hệ thống không tìm thấy tổ chức nào khớp chính xác 100% trong cơ sở dữ liệu BCA / BQP.
            </div>
            <div style="font-size: 13px; color: #9CA3AF; margin-top: 10px; line-height: 1.6;">
                💡 <strong>Nguyên tắc tìm kiếm (Strict Deterministic):</strong>
                <ul style="margin-left: 20px;">
                    <li>Hệ thống chỉ kết luận khi khớp chính xác 100% (qua Tên, Mã ID, Tên không dấu hoặc Tên viết tắt).</li>
                    <li>Tuyệt đối không phỏng đoán hay đưa ra ứng viên xấp xỉ nhằm đảm bảo tính an toàn dữ liệu.</li>
                    <li>Vui lòng kiểm tra lại chính tả hoặc mở "Tra cứu nâng cao" để nhập trực tiếp mã tổ chức (nếu có).</li>
                </ul>
            </div>
        </div>
        """)

    # ── PIPELINE TRACE ──
    is_matched = status == "MATCH_100"
    decision_text = f"{status}"
    if res.get("management"):
        decision_text += f" → {res.get('management')}"
    else:
        decision_text += " → Không có dữ liệu"

    html_out.append(f"""
    <div class="result-card" style="margin-top: 14px;">
        <div class="section-title">🔬 Pipeline Trace (Luồng xử lý chi tiết)</div>
        <div class="trace-step">
            <div class="trace-dot active"></div>
            <div class="trace-k">1. Query đầu vào:</div>
            <div class="trace-v mono">{html.escape(org_name or org_id or '—')}</div>
        </div>
        <div class="trace-step">
            <div class="trace-dot active"></div>
            <div class="trace-k">2. Normalization:</div>
            <div class="trace-v mono">{html.escape(norm_val)}</div>
        </div>
        <div class="trace-step">
            <div class="trace-dot active"></div>
            <div class="trace-k">3. Search Key:</div>
            <div class="trace-v mono">{html.escape(search_key_val)}</div>
        </div>
        <div class="trace-step">
            <div class="trace-dot {'active' if is_matched else 'inactive'}"></div>
            <div class="trace-k">4. Strict Match:</div>
            <div class="trace-v mono">{'HIT (100% - ' + html.escape(match_status) + ')' if is_matched else 'MISS (No exact match)'}</div>
        </div>
        <div class="trace-step">
            <div class="trace-dot inactive"></div>
            <div class="trace-k">5. Fuzzy Match:</div>
            <div class="trace-v mono" style="color: #9CA3AF;">DISABLED (Strict Mode: 100% or Unknown)</div>
        </div>
        <div class="trace-step">
            <div class="trace-dot active"></div>
            <div class="trace-k">6. Kết luận:</div>
            <div class="trace-v bold" style="color: {'#60A5FA' if is_matched else '#F87171'};">{html.escape(decision_text)}</div>
        </div>
    </div>
    """)

    html_out.append("</div>")
    return "\n".join(html_out)


# ── 3. Gradio Interface with Custom Dark Theme ────────────────────────────────

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

body, .gradio-container {
    font-family: 'Inter', sans-serif !important;
    background: #0B0F19 !important;
    color: #E5E7EB !important;
}

.stat-banner {
    display: flex;
    justify-content: space-around;
    background: rgba(26, 31, 43, 0.7);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 12px 20px;
    margin-bottom: 18px;
    text-align: center;
}
.stat-item {
    font-size: 13px;
    color: #9CA3AF;
}
.stat-item strong {
    color: #60A5FA;
    font-size: 16px;
    display: block;
}

.result-container {
    animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
}

.result-card {
    background: rgba(26, 31, 43, 0.75);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 14px;
}

.badge-header {
    text-align: center;
    padding: 10px 0 18px;
}
.badge-subtitle {
    font-size: 12px;
    color: #9CA3AF;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.badge-bca {
    display: inline-block;
    background: linear-gradient(135deg, #2563EB, #3B82F6);
    color: #fff;
    font-size: 2.2rem;
    font-weight: 800;
    padding: 8px 36px;
    border-radius: 14px;
    letter-spacing: 3px;
    box-shadow: 0 4px 25px rgba(37,99,235,0.5);
}
.badge-bqp {
    display: inline-block;
    background: linear-gradient(135deg, #059669, #10B981);
    color: #fff;
    font-size: 2.2rem;
    font-weight: 800;
    padding: 8px 36px;
    border-radius: 14px;
    letter-spacing: 3px;
    box-shadow: 0 4px 25px rgba(5,150,105,0.5);
}
.badge-label {
    color: #E5E7EB;
    font-size: 15px;
    font-weight: 600;
    margin-top: 8px;
}

.status-chip {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}
.chip-resolved {
    background: rgba(16,185,129,0.15);
    color: #34D399;
    border: 1px solid rgba(16,185,129,0.3);
}
.chip-notfound, .chip-invalid {
    background: rgba(239,68,68,0.15);
    color: #F87171;
    border: 1px solid rgba(239,68,68,0.3);
}

.section-title {
    font-size: 15px;
    font-weight: 700;
    color: #F3F4F6;
    margin-bottom: 12px;
}

.info-table {
    border-top: 1px solid rgba(255,255,255,0.06);
}
.info-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-size: 14px;
}
.info-k { color: #9CA3AF; }
.info-v { color: #F3F4F6; text-align: right; }
.info-v.bold { font-weight: 600; }
.info-v.mono { font-family: monospace; }
.type-code { font-size: 12px; color: #9CA3AF; }

.banner {
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.5;
    margin-bottom: 14px;
}
.banner-warn {
    background: rgba(245,158,11,0.1);
    border-left: 4px solid #F59E0B;
    color: #FBBF24;
}
.banner-danger {
    background: rgba(239,68,68,0.1);
    border-left: 4px solid #EF4444;
    color: #F87171;
}

.trace-step {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    font-size: 13px;
}
.trace-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}
.trace-dot.active { background: #10B981; box-shadow: 0 0 6px rgba(16,185,129,0.6); }
.trace-dot.inactive { background: rgba(255,255,255,0.2); }
.trace-k { color: #9CA3AF; min-width: 130px; }
.trace-v { color: #E5E7EB; }
.trace-v.mono { font-family: monospace; }
.trace-v.bold { font-weight: 700; }
"""

with gr.Blocks(title="Tra cứu Tổ chức BCA / BQP (Strict Mode)", css=CUSTOM_CSS, theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate")) as demo:
    gr.HTML("""
    <div style="text-align: center; padding: 16px 0 10px;">
        <h1 style="font-size: 2rem; font-weight: 800; background: linear-gradient(135deg, #4F8BF9, #7C3AED, #EC4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🏛️ Tra cứu Tổ chức — BCA / BQP
        </h1>
        <p style="color: #9CA3AF; font-size: 14px; margin-top: 4px;">
            Hệ thống Strict Deterministic Search: Đúng 100% hoặc Unknown (Không phỏng đoán mờ)
        </p>
    </div>
    """)

    gr.HTML(f"""
    <div class="stat-banner">
        <div class="stat-item"><strong>{total_orgs:,}</strong>Tổ chức trong Registry</div>
        <div class="stat-item"><strong>{province_count}</strong>Tỉnh / Thành phố</div>
        <div class="stat-item"><strong style="color: #60A5FA;">{bca_count:,}</strong>Bộ Công an (BCA)</div>
        <div class="stat-item"><strong style="color: #34D399;">{bqp_count:,}</strong>Bộ Quốc phòng (BQP)</div>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=4):
            input_name = gr.Textbox(
                label="🔍 Tên tổ chức cần tra cứu",
                placeholder="Ví dụ: Công an tỉnh Thái Bình, Bộ CHQS tỉnh Quảng Ninh, cong an tinh thai binh...",
                lines=1,
            )
        with gr.Column(scale=1):
            btn_search = gr.Button("🔍 Tra cứu ngay", variant="primary", scale=1)

    with gr.Accordion("🔧 Tra cứu nâng cao (Lọc theo ID, Tỉnh/TP, Loại)", open=False):
        with gr.Row():
            input_id = gr.Textbox(label="Mã tổ chức (ID)", placeholder="VD: BCA-PROVINCE-002153")
            input_province = gr.Dropdown(label="Tỉnh / Thành phố", choices=provinces, value="")
            input_type = gr.Dropdown(label="Loại tổ chức", choices=type_codes, value="")

    gr.Examples(
        examples=[
            ["Công an tỉnh Thái Bình"],
            ["Bộ Chỉ huy Quân sự tỉnh Quảng Ninh"],
            ["cong an tinh thai binh"],
            ["BCHQS huyện Sóc Sơn"],
            ["Học viện Cảnh sát nhân dân"],
            ["Học viện Kỹ thuật Quân sự"],
            ["Đơn vị không có thật 123"],
        ],
        inputs=[input_name],
        label="💡 Thử nhanh các ví dụ mẫu",
    )

    output_html = gr.HTML(label="Kết quả tra cứu")

    # Wire event handlers
    btn_search.click(
        fn=search_organization_ui,
        inputs=[input_name, input_id, input_province, input_type],
        outputs=[output_html],
    )
    input_name.submit(
        fn=search_organization_ui,
        inputs=[input_name, input_id, input_province, input_type],
        outputs=[output_html],
    )
    input_id.submit(
        fn=search_organization_ui,
        inputs=[input_name, input_id, input_province, input_type],
        outputs=[output_html],
    )


if __name__ == "__main__":
    demo.launch()
