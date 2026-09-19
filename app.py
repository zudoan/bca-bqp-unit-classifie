"""Hugging Face Spaces Application — Organization Matching Registry (BCA / BQP).

Powered by Gradio + Matching Engine. Native ZeroGPU & Hugging Face Spaces compatibility.
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
    "EXACT_ID_MATCH": ("Khớp chính xác mã ID (100%)", "chip-resolved"),
    "EXACT_NAME_MATCH": ("Khớp chính xác tên (100%)", "chip-resolved"),
    "NORMALIZED_MATCH": ("Khớp tên sau chuẩn hóa (100%)", "chip-resolved"),
    "SEARCH_KEY_MATCH": ("Khớp không dấu / Search Key (100%)", "chip-resolved"),
    "ALIAS_MATCH": ("Khớp tên viết tắt / Tên gọi khác (100%)", "chip-resolved"),
    "RESOLVED": ("Khớp chính xác (100%)", "chip-resolved"),
    "FUZZY_CANDIDATES": ("So khớp mờ / Fuzzy Matching", "chip-fuzzy"),
    "AMBIGUOUS_MATCH": ("Trùng tên — Cần thêm ngữ cảnh", "chip-ambiguous"),
    "NOT_FOUND": ("Không tìm thấy", "chip-notfound"),
    "INVALID_INPUT": ("Dữ liệu đầu vào không hợp lệ", "chip-invalid"),
}


# ── 2. Search Logic ───────────────────────────────────────────────────────────

def search_organization_ui(org_name, org_id, province, org_type, scorer, threshold, top_k):
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

    # Build per-request service with chosen fuzzy config
    config = MatchingConfig(
        fuzzy_scorer=scorer or "WRatio",
        fuzzy_minimum_score=float(threshold),
        fuzzy_top_k=int(top_k),
    )
    service = OrganizationSearchService(repo, config)

    res = service.search_organization(
        organization_id=org_id or None,
        organization_name=org_name or None,
        province_name=province,
        organization_type=org_type,
    )

    status = res.get("match_status", "UNKNOWN")
    norm_val = normalize_name(org_name) if org_name else "—"
    search_key_val = to_search_key(org_name) if org_name else "—"

    # Enrich candidates with management
    candidates = res.get("candidates") or []
    for c in candidates:
        cid = c.get("organization_id")
        if cid:
            try:
                c["management"] = repo.get_management(cid)
            except Exception:
                c["management"] = None

    is_deterministic = status in {
        "EXACT_ID_MATCH", "EXACT_NAME_MATCH", "NORMALIZED_MATCH",
        "SEARCH_KEY_MATCH", "ALIAS_MATCH", "RESOLVED"
    }

    html_out = ['<div class="result-container">']

    # ── CASE A: DETERMINISTIC MATCH ──
    if is_deterministic:
        mgmt = res.get("management", "N/A")
        is_bca = mgmt == "BCA"
        is_bqp = mgmt == "BQP"
        badge_cls = "badge-bca" if is_bca else ("badge-bqp" if is_bqp else "badge-bca")
        mgmt_name = "Bộ Công an" if is_bca else ("Bộ Quốc phòng" if is_bqp else mgmt)
        info_label, chip_cls = STATUS_INFO.get(status, (status, "chip-resolved"))
        type_code = res.get("organization_type_code", "")
        type_label = TYPE_CODE_LABELS.get(type_code, type_code or "—")

        html_out.append(f"""
        <div class="result-card">
            <div class="badge-header">
                <div class="badge-subtitle">KẾT LUẬN CƠ QUAN QUẢN LÝ</div>
                <div class="{badge_cls}">{html.escape(mgmt)}</div>
                <div class="badge-label">{html.escape(mgmt_name)}</div>
                <div style="margin-top: 10px;">
                    <span class="status-chip {chip_cls}">✅ {html.escape(info_label)}</span>
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

    # ── CASE B: FUZZY CANDIDATES ──
    elif status == "FUZZY_CANDIDATES":
        top1 = candidates[0] if candidates else None
        top1_score = res.get("top1_score") or (top1.get("score") if top1 else 0)
        top2_score = res.get("top2_score")
        margin = res.get("score_margin")

        top1_html = ""
        if top1:
            top1_mgmt = top1.get("management") or "N/A"
            is_bca = top1_mgmt == "BCA"
            is_bqp = top1_mgmt == "BQP"
            badge_cls = "badge-bca" if is_bca else ("badge-bqp" if is_bqp else "badge-bca")
            mgmt_name = "Bộ Công an" if is_bca else ("Bộ Quốc phòng" if is_bqp else top1_mgmt)
            type_code = top1.get("organization_type_code", "")
            type_label = TYPE_CODE_LABELS.get(type_code, type_code or "—")

            top1_html = f"""
            <div class="badge-header">
                <div class="badge-subtitle">GỢI Ý CƠ QUAN QUẢN LÝ (TOP 1 ỨNG VIÊN)</div>
                <div class="{badge_cls}">{html.escape(top1_mgmt)}</div>
                <div class="badge-label">{html.escape(mgmt_name)}</div>
                <div style="margin-top: 10px;">
                    <span class="status-chip chip-fuzzy">🔍 FUZZY TOP-1 ({top1_score}%)</span>
                </div>
            </div>

            <div class="banner banner-warn">
                ⚡ <strong>So khớp mờ (Fuzzy Match):</strong> Không có khớp chính xác 100%. 
                Tìm thấy <strong>{len(candidates)}</strong> ứng viên có điểm tương đồng ≥ {threshold}%.
                <br>• Điểm cao nhất: <strong>{top1_score}%</strong>
                {f' • Top-2: <strong>{top2_score}%</strong>' if top2_score else ''}
                {f' • Cách biệt: <strong>{margin} điểm</strong>' if margin is not None else ''}
            </div>

            <div class="section-title">🎯 Ứng viên phù hợp nhất (Top 1)</div>
            <div class="info-table">
                <div class="info-row">
                    <span class="info-k">Mã tổ chức</span>
                    <span class="info-v mono">{html.escape(top1.get('organization_id') or '—')}</span>
                </div>
                <div class="info-row">
                    <span class="info-k">Tên chính thức</span>
                    <span class="info-v bold">{html.escape(top1.get('organization_name') or '—')}</span>
                </div>
                <div class="info-row">
                    <span class="info-k">Tỉnh / Thành phố</span>
                    <span class="info-v">{html.escape(top1.get('province_name') or 'Trung ương / Toàn quốc')}</span>
                </div>
                <div class="info-row">
                    <span class="info-k">Loại tổ chức</span>
                    <span class="info-v">{html.escape(type_label)} <code class="type-code">({html.escape(type_code)})</code></span>
                </div>
                <div class="info-row">
                    <span class="info-k">Cơ quan chủ quản dự kiến</span>
                    <span class="info-v" style="color: {'#60A5FA' if is_bca else '#34D399'}; font-weight: 700;">
                        {html.escape(top1_mgmt)} — {html.escape(mgmt_name)}
                    </span>
                </div>
            </div>
            """

        html_out.append(f"""
        <div class="result-card">
            {top1_html}
        </div>
        """)

    # ── CASE C: AMBIGUOUS MATCH ──
    elif status == "AMBIGUOUS_MATCH":
        html_out.append(f"""
        <div class="result-card">
            <div style="text-align: center; margin-bottom: 12px;">
                <span class="status-chip chip-ambiguous">⚠️ AMBIGUOUS_MATCH (Trùng tên — Cần thêm ngữ cảnh)</span>
            </div>
            <div class="banner banner-warn">
                ⚠️ <strong>Phát hiện {len(candidates)} tổ chức trùng tên:</strong> 
                Hệ thống không tự ý suy diễn để bảo đảm an toàn dữ liệu. 
                Vui lòng mở mục "Tra cứu nâng cao" và chọn thêm <strong>Tỉnh / Thành phố</strong> hoặc <strong>Loại tổ chức</strong> để phân định chính xác.
            </div>
        </div>
        """)

    # ── CASE D: NOT FOUND ──
    elif status == "NOT_FOUND":
        reason = res.get("reason", "")
        reason_map = {
            "ORGANIZATION_ID_NOT_FOUND": "Mã tổ chức không tồn tại trong Registry.",
            "DETERMINISTIC_MATCH_CONTEXT_MISMATCH": "Tìm thấy tên tổ chức nhưng tỉnh/loại tổ chức không khớp với điều kiện lọc.",
            "NO_CANDIDATE_ABOVE_FUZZY_THRESHOLD": f"Không có ứng viên nào đạt ngưỡng điểm tối thiểu ({threshold}%).",
        }
        reason_text = reason_map.get(reason, reason or "Không tìm thấy kết quả nào phù hợp trong Registry.")
        html_out.append(f"""
        <div class="result-card">
            <div style="text-align: center; margin-bottom: 12px;">
                <span class="status-chip chip-notfound">❌ NOT FOUND (Không tìm thấy)</span>
            </div>
            <div class="banner banner-danger">
                ❌ <strong>Không tìm thấy:</strong> {html.escape(reason_text)}
            </div>
            <div style="font-size: 13px; color: #9CA3AF; margin-top: 10px; line-height: 1.6;">
                💡 <strong>Gợi ý:</strong>
                <ul style="margin-left: 20px;">
                    <li>Kiểm tra lại chính tả hoặc nhập từ khóa ngắn gọn hơn (VD: "Công an Thái Bình").</li>
                    <li>Hạ ngưỡng Fuzzy (thanh gạt ở mục Nâng cao, VD: 75 hoặc 80).</li>
                </ul>
            </div>
        </div>
        """)

    # ── CASE E: INVALID INPUT ──
    elif status == "INVALID_INPUT":
        errs = res.get("errors") or [res.get("reason") or "Dữ liệu không hợp lệ."]
        err_items = "".join([f"<li>{html.escape(e)}</li>" for e in errs])
        html_out.append(f"""
        <div class="result-card">
            <div style="text-align: center; margin-bottom: 12px;">
                <span class="status-chip chip-invalid">🚫 INVALID INPUT (Dữ liệu không hợp lệ)</span>
            </div>
            <div class="banner banner-danger">
                <ul>{err_items}</ul>
            </div>
        </div>
        """)

    # ── CANDIDATES SECTION ──
    if candidates and len(candidates) > 0:
        c_cards = []
        for idx, c in enumerate(candidates, 1):
            sc = c.get("score")
            sc_str = f"{round(sc)}%" if sc is not None else "—"
            c_mgmt = c.get("management")
            mgmt_badge = ""
            if c_mgmt:
                is_bca_c = c_mgmt == "BCA"
                mgmt_badge = f"""
                <span class="badge-mini {'bca' if is_bca_c else 'bqp'}">{html.escape(c_mgmt)}</span>
                """
            t_label = TYPE_CODE_LABELS.get(c.get("organization_type_code", ""), c.get("organization_type_code", ""))

            c_cards.append(f"""
            <div class="cand-card">
                <div class="cand-top">
                    <div>
                        <span class="cand-rank">#{idx}</span>
                        <span class="cand-name">{html.escape(c.get('organization_name') or '—')}</span>
                        {mgmt_badge}
                        <div class="cand-meta">
                            Mã: <code>{html.escape(c.get('organization_id') or '—')}</code>
                            {f" • Tỉnh: <strong>{html.escape(c.get('province_name'))}</strong>" if c.get('province_name') else ''}
                            {f" • Loại: <em>{html.escape(t_label)}</em>" if t_label else ''}
                            {f" • Khớp: <code>{html.escape(c.get('matched_on'))}</code>" if c.get('matched_on') else ''}
                        </div>
                    </div>
                    <div class="cand-score">
                        <div class="cand-num">{sc_str}</div>
                        <div class="cand-score-label">Điểm khớp</div>
                    </div>
                </div>
            </div>
            """)

        html_out.append(f"""
        <div class="result-card" style="margin-top: 14px;">
            <div class="section-title">👥 Danh sách ứng viên ({len(candidates)})</div>
            {''.join(c_cards)}
        </div>
        """)

    # ── PIPELINE TRACE SECTION ──
    decision_text = f"{status}"
    if res.get("management"):
        decision_text += f" → {res.get('management')}"
    elif candidates and candidates[0].get("management"):
        decision_text += f" → {candidates[0].get('management')} (Dự kiến)"

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
            <div class="trace-dot {'active' if is_deterministic else 'inactive'}"></div>
            <div class="trace-k">4. Exact Match:</div>
            <div class="trace-v mono">{'HIT (100%)' if is_deterministic else 'MISS'}</div>
        </div>
        <div class="trace-step">
            <div class="trace-dot {'active' if not is_deterministic else 'inactive'}"></div>
            <div class="trace-k">5. Fuzzy Match:</div>
            <div class="trace-v mono">{scorer} (Threshold: {threshold}%, Top-K: {top_k})</div>
        </div>
        <div class="trace-step">
            <div class="trace-dot active"></div>
            <div class="trace-k">6. Kết luận:</div>
            <div class="trace-v bold" style="color: #60A5FA;">{html.escape(decision_text)}</div>
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
.chip-fuzzy {
    background: rgba(245,158,11,0.15);
    color: #FBBF24;
    border: 1px solid rgba(245,158,11,0.3);
}
.chip-ambiguous {
    background: rgba(249,115,22,0.15);
    color: #FB923C;
    border: 1px solid rgba(249,115,22,0.3);
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

.cand-card {
    background: rgba(15, 18, 28, 0.6);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.cand-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}
.cand-rank { color: #60A5FA; font-weight: 700; font-size: 15px; }
.cand-name { font-weight: 600; font-size: 14px; color: #F3F4F6; margin-left: 6px; }
.cand-meta { font-size: 12px; color: #9CA3AF; margin-top: 4px; }
.cand-score { text-align: right; min-width: 60px; }
.cand-num { font-size: 16px; font-weight: 700; color: #34D399; }
.cand-score-label { font-size: 10px; color: #6B7280; }

.badge-mini {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    margin-left: 6px;
}
.badge-mini.bca { background: rgba(37,99,235,0.25); color: #93C5FD; border: 1px solid rgba(37,99,235,0.4); }
.badge-mini.bqp { background: rgba(5,150,105,0.25); color: #6EE7B7; border: 1px solid rgba(5,150,105,0.4); }

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

with gr.Blocks(title="Tra cứu Tổ chức BCA / BQP", css=CUSTOM_CSS, theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate")) as demo:
    gr.HTML("""
    <div style="text-align: center; padding: 16px 0 10px;">
        <h1 style="font-size: 2rem; font-weight: 800; background: linear-gradient(135deg, #4F8BF9, #7C3AED, #EC4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🏛️ Tra cứu Tổ chức — BCA / BQP
        </h1>
        <p style="color: #9CA3AF; font-size: 14px; margin-top: 4px;">
            Nhập tên hoặc mã tổ chức → Entity Resolution (Exact / Fuzzy Matching) → Kết luận cơ quan chủ quản BCA hay BQP
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
                placeholder="Ví dụ: Công an tỉnh Thái Bình, Bộ CHQS tỉnh Quảng Ninh, Cong an Thanh pho Ha Noi...",
                lines=1,
            )
        with gr.Column(scale=1):
            btn_search = gr.Button("🔍 Tra cứu ngay", variant="primary", scale=1)

    with gr.Accordion("🔧 Tra cứu nâng cao & Cấu hình Matching Engine", open=False):
        with gr.Row():
            input_id = gr.Textbox(label="Mã tổ chức (ID nếu biết)", placeholder="VD: BCA-PROVINCE-002153")
            input_province = gr.Dropdown(label="Tỉnh / Thành phố", choices=provinces, value="")
            input_type = gr.Dropdown(label="Loại tổ chức", choices=type_codes, value="")

        with gr.Row():
            cfg_scorer = gr.Dropdown(
                label="Thuật toán Fuzzy",
                choices=["WRatio", "ratio", "token_sort_ratio", "token_set_ratio"],
                value="WRatio",
            )
            cfg_threshold = gr.Slider(label="Ngưỡng Fuzzy tối thiểu (%)", minimum=50, maximum=100, value=85, step=5)
            cfg_top_k = gr.Slider(label="Số ứng viên tối đa (Top-K)", minimum=1, maximum=20, value=5, step=1)

    gr.Examples(
        examples=[
            ["Công an tỉnh Thái Bình"],
            ["Bộ Chỉ huy Quân sự tỉnh Quảng Ninh"],
            ["Cong an Thanh pho Ha Noi"],
            ["Đồn Biên phòng cửa khẩu Lào Cai"],
            ["Học viện Cảnh sát nhân dân"],
            ["Học viện Kỹ thuật Quân sự"],
        ],
        inputs=[input_name],
        label="💡 Thử nhanh các ví dụ mẫu",
    )

    output_html = gr.HTML(label="Kết quả tra cứu")

    # Wire event handlers
    btn_search.click(
        fn=search_organization_ui,
        inputs=[input_name, input_id, input_province, input_type, cfg_scorer, cfg_threshold, cfg_top_k],
        outputs=[output_html],
    )
    input_name.submit(
        fn=search_organization_ui,
        inputs=[input_name, input_id, input_province, input_type, cfg_scorer, cfg_threshold, cfg_top_k],
        outputs=[output_html],
    )
    input_id.submit(
        fn=search_organization_ui,
        inputs=[input_name, input_id, input_province, input_type, cfg_scorer, cfg_threshold, cfg_top_k],
        outputs=[output_html],
    )


if __name__ == "__main__":
    demo.launch()
