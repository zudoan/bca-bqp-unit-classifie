"""
Organization Matching Registry — Streamlit UI
Giao diện tra cứu tổ chức thuộc phạm vi quản lý BCA / BQP.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so that `matching`, `search`, etc.
# are importable regardless of how Streamlit is launched.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from matching.repository import InMemoryOrganizationRepository
from matching.resolver import MatchingConfig
from preprocessing.normalize import normalize_name, to_search_key
from search.organization_search import OrganizationSearchService


# ═══════════════════════════════════════════════════════════════════════════
# Data & Service — cached so we only load once per Streamlit process.
# ═══════════════════════════════════════════════════════════════════════════

DATASET_PATH = _PROJECT_ROOT / "data" / "dataset.csv"
ALIASES_PATH = _PROJECT_ROOT / "data" / "test" / "aliases.csv"


@st.cache_data(show_spinner=False)
def load_dataframe() -> pd.DataFrame:
    return pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False)


@st.cache_resource(show_spinner=False)
def build_service(scorer: str, threshold: float, top_k: int) -> OrganizationSearchService:
    df = load_dataframe()
    rows = df.to_dict("records")
    aliases: list[dict] = []
    if ALIASES_PATH.is_file():
        aliases = pd.read_csv(ALIASES_PATH, dtype=str, keep_default_na=False).to_dict("records")
    repo = InMemoryOrganizationRepository(rows, aliases)
    return OrganizationSearchService(
        repo,
        MatchingConfig(
            fuzzy_scorer=scorer,
            fuzzy_minimum_score=threshold,
            fuzzy_top_k=top_k,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Page config
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Tra cứu Tổ chức — BCA / BQP",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════
# Custom CSS — premium dark-glass aesthetic
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
/* ── Import Google Font ────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="st-"], .stApp, p, h1, h2, h3, h4, h5, h6, label, input, button, select {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Bảo vệ icon font của Streamlit (expander chevron, tooltips, v.v.) */
[class*="material-symbols"],
[data-testid*="Icon"],
summary span {
    font-family: "Material Symbols Rounded", "Material Icons" !important;
}

code, pre {
    font-family: 'Consolas', 'Courier New', monospace !important;
}

/* ── Hero header ───────────────────────────────────────────────────────── */
.hero {
    text-align: center;
    padding: 2rem 1rem 1rem;
    margin-bottom: 1.5rem;
}
.hero h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #4F8BF9 0%, #7C3AED 50%, #EC4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
    letter-spacing: -0.5px;
}
.hero p {
    color: #9CA3AF;
    font-size: 1rem;
    font-weight: 400;
}

/* ── Glass card ────────────────────────────────────────────────────────── */
.glass-card {
    background: rgba(26, 31, 43, 0.65);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.25);
}

/* ── Result badge ─────────────────────────────────────────────────────── */
.badge-bca {
    display: inline-block;
    background: linear-gradient(135deg, #2563EB, #3B82F6);
    color: #fff;
    font-size: 2rem;
    font-weight: 800;
    padding: 0.5rem 2.5rem;
    border-radius: 12px;
    letter-spacing: 3px;
    box-shadow: 0 4px 20px rgba(37,99,235,0.45);
    animation: pulse-blue 2s infinite;
}
.badge-bqp {
    display: inline-block;
    background: linear-gradient(135deg, #059669, #10B981);
    color: #fff;
    font-size: 2rem;
    font-weight: 800;
    padding: 0.5rem 2.5rem;
    border-radius: 12px;
    letter-spacing: 3px;
    box-shadow: 0 4px 20px rgba(5,150,105,0.45);
    animation: pulse-green 2s infinite;
}
@keyframes pulse-blue {
    0%, 100% { box-shadow: 0 4px 20px rgba(37,99,235,0.45); }
    50% { box-shadow: 0 4px 35px rgba(37,99,235,0.7); }
}
@keyframes pulse-green {
    0%, 100% { box-shadow: 0 4px 20px rgba(5,150,105,0.45); }
    50% { box-shadow: 0 4px 35px rgba(5,150,105,0.7); }
}

/* ── Status chips ──────────────────────────────────────────────────────── */
.status-chip {
    display: inline-block;
    padding: 0.25rem 0.85rem;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.5px;
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
.chip-notfound {
    background: rgba(239,68,68,0.15);
    color: #F87171;
    border: 1px solid rgba(239,68,68,0.3);
}
.chip-invalid {
    background: rgba(239,68,68,0.15);
    color: #F87171;
    border: 1px solid rgba(239,68,68,0.3);
}

/* ── Info row ──────────────────────────────────────────────────────────── */
.info-row {
    display: flex;
    justify-content: space-between;
    padding: 0.6rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-size: 0.92rem;
}
.info-row:last-child { border-bottom: none; }
.info-label { color: #9CA3AF; font-weight: 500; }
.info-value { color: #F3F4F6; font-weight: 600; text-align: right; }

/* ── Score bar ─────────────────────────────────────────────────────────── */
.score-bar-track {
    background: rgba(255,255,255,0.06);
    border-radius: 8px;
    height: 10px;
    width: 100%;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.6s ease;
}

/* ── Candidate table ───────────────────────────────────────────────────── */
.candidate-card {
    background: rgba(26, 31, 43, 0.5);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s;
}
.candidate-card:hover {
    border-color: rgba(79,139,249,0.4);
}
.candidate-rank {
    color: #4F8BF9;
    font-weight: 700;
    font-size: 1.1rem;
}
.candidate-name {
    font-weight: 600;
    font-size: 1rem;
    color: #F3F4F6;
}
.candidate-meta {
    color: #9CA3AF;
    font-size: 0.82rem;
}

/* ── Pipeline step ─────────────────────────────────────────────────────── */
.pipeline-step {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0;
}
.pipeline-dot {
    width: 10px; height: 10px; border-radius: 50%;
    flex-shrink: 0;
}
.pipeline-dot-active { background: #10B981; box-shadow: 0 0 8px rgba(16,185,129,0.5); }
.pipeline-dot-inactive { background: rgba(255,255,255,0.15); }
.pipeline-label { font-size: 0.85rem; color: #9CA3AF; }
.pipeline-value { font-size: 0.85rem; color: #D1D5DB; font-weight: 500; font-family: 'Courier New', monospace !important; }

/* ── Sidebar branding ──────────────────────────────────────────────────── */
.sidebar-brand {
    text-align: center;
    padding: 0.5rem 0 1rem;
}
.sidebar-brand h3 {
    font-size: 1.1rem;
    font-weight: 700;
    color: #4F8BF9;
    margin-bottom: 0.2rem;
}
.sidebar-brand p {
    font-size: 0.78rem;
    color: #6B7280;
}

/* ── Hide Streamlit branding ───────────────────────────────────────────── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* ── Warnings/Alerts custom ────────────────────────────────────────────── */
.safety-banner {
    background: rgba(245,158,11,0.08);
    border-left: 4px solid #F59E0B;
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #FBBF24;
    margin-bottom: 1rem;
}
.safety-banner-red {
    background: rgba(239,68,68,0.08);
    border-left: 4px solid #EF4444;
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #F87171;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <h3>🏛️ Organization Registry</h3>
        <p>Hệ thống tra cứu BCA / BQP</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("##### ⚙️ Cấu hình Matching Engine")

    scorer = st.selectbox(
        "Thuật toán Fuzzy",
        options=["WRatio", "ratio", "token_sort_ratio", "token_set_ratio"],
        index=0,
        help="WRatio cho kết quả tốt nhất trên benchmark seed.",
    )
    threshold = st.slider(
        "Ngưỡng Fuzzy (cutoff)",
        min_value=50, max_value=100, value=85, step=5,
        help="Điểm tối thiểu để ứng viên xuất hiện trong kết quả.",
    )
    top_k = st.slider(
        "Số ứng viên tối đa (Top-K)",
        min_value=1, max_value=20, value=5,
        help="Số lượng ứng viên Fuzzy trả về.",
    )

    st.divider()

    # Quick stats
    df = load_dataframe()
    total = len(df)
    bca_count = int((df.management == "BCA").sum())
    bqp_count = int((df.management == "BQP").sum())
    province_count = df.province_name.nunique()

    col1, col2 = st.columns(2)
    col1.metric("Tổ chức", f"{total:,}")
    col2.metric("Tỉnh/TP", province_count)
    col1.metric("BCA", f"{bca_count:,}")
    col2.metric("BQP", f"{bqp_count:,}")

    st.divider()
    st.caption("Version 1.0 • Matching Engine trên registry snapshot")


# ═══════════════════════════════════════════════════════════════════════════
# Build service with sidebar config
# ═══════════════════════════════════════════════════════════════════════════

service = build_service(scorer, threshold, top_k)

# ═══════════════════════════════════════════════════════════════════════════
# Helper data for select boxes
# ═══════════════════════════════════════════════════════════════════════════

provinces_list = sorted(df.province_name.unique().tolist())
type_codes_list = sorted(df.organization_type_code.unique().tolist())

MATCH_STATUS_LABELS = {
    "EXACT_ID_MATCH": ("Khớp chính xác theo mã ID", "chip-resolved"),
    "EXACT_NAME_MATCH": ("Khớp chính xác theo tên", "chip-resolved"),
    "NORMALIZED_MATCH": ("Khớp sau chuẩn hoá", "chip-resolved"),
    "SEARCH_KEY_MATCH": ("Khớp search key (bỏ dấu)", "chip-resolved"),
    "ALIAS_MATCH": ("Khớp tên viết tắt / tên khác", "chip-resolved"),
    "FUZZY_CANDIDATES": ("Ứng viên tương tự (Fuzzy)", "chip-fuzzy"),
    "AMBIGUOUS_MATCH": ("Trùng tên — cần thêm ngữ cảnh", "chip-ambiguous"),
    "NOT_FOUND": ("Không tìm thấy", "chip-notfound"),
    "INVALID_INPUT": ("Dữ liệu đầu vào không hợp lệ", "chip-invalid"),
}

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


# ═══════════════════════════════════════════════════════════════════════════
# Hero
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="hero">
    <h1>Tra cứu Tổ chức BCA / BQP</h1>
    <p>Nhập tên hoặc mã tổ chức → Entity Resolution → Tra cứu cơ quan chủ quản</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Search form
# ═══════════════════════════════════════════════════════════════════════════

with st.container():
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    org_name = st.text_input(
        "🔍  Tên tổ chức",
        placeholder="Ví dụ: Công an tỉnh Thái Bình, Bộ CHQS tỉnh Quảng Ninh, ...",
        help="Có thể nhập có dấu, không dấu, viết tắt hoặc có lỗi chính tả.",
        key="org_name_input",
    )

    with st.expander("🔧 Tra cứu nâng cao", expanded=False):
        col_id, col_prov, col_type = st.columns(3)
        with col_id:
            org_id = st.text_input(
                "Mã tổ chức (ID)",
                placeholder="VD: BCA-PROVINCE-002153",
                help="Nếu biết chính xác mã, nhập vào đây để tra cứu ưu tiên.",
            )
        with col_prov:
            province_options = ["— Tất cả —"] + provinces_list
            province_choice = st.selectbox("Tỉnh / Thành phố", options=province_options)
        with col_type:
            type_options = ["— Tất cả —"] + [
                f"{code} ({TYPE_CODE_LABELS.get(code, code)})" for code in type_codes_list
            ]
            type_choice = st.selectbox("Loại tổ chức", options=type_options)

    # Large search button
    search_clicked = st.button(
        "🔍  Tra cứu",
        type="primary",
        use_container_width=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Perform search & display results
# ═══════════════════════════════════════════════════════════════════════════

def _score_bar_color(score: float) -> str:
    if score >= 95:
        return "linear-gradient(90deg, #10B981, #34D399)"
    if score >= 85:
        return "linear-gradient(90deg, #F59E0B, #FBBF24)"
    return "linear-gradient(90deg, #EF4444, #F87171)"


def render_resolved(result: dict) -> None:
    management = result.get("management", "")
    status = result["match_status"]
    status_label, status_class = MATCH_STATUS_LABELS.get(status, (status, "chip-resolved"))

    # Main badge
    badge_class = "badge-bca" if management == "BCA" else "badge-bqp"
    management_full = "Bộ Công an" if management == "BCA" else "Bộ Quốc phòng"

    st.markdown(f"""
    <div class="glass-card" style="text-align: center; padding: 2.5rem 2rem;">
        <p style="color: #9CA3AF; font-size: 0.9rem; margin-bottom: 0.75rem;">Cơ quan chủ quản</p>
        <div class="{badge_class}">{management}</div>
        <p style="color: #D1D5DB; font-size: 0.95rem; margin-top: 0.75rem;">{management_full}</p>
    </div>
    """, unsafe_allow_html=True)

    # Detail card
    org_type_raw = result.get("organization_type_code", "")
    org_type_label = TYPE_CODE_LABELS.get(org_type_raw, org_type_raw)
    score = result.get("match_score", 100)

    st.markdown(f"""
    <div class="glass-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <span style="font-size: 1.15rem; font-weight: 700; color: #F3F4F6;">📋 Chi tiết kết quả</span>
            <span class="status-chip {status_class}">{status_label}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Tên tổ chức</span>
            <span class="info-value">{result.get('organization_name', '')}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Mã tổ chức</span>
            <span class="info-value" style="font-family: 'Courier New', monospace !important;">{result.get('organization_id', '')}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Tỉnh / Thành phố</span>
            <span class="info-value">{result.get('province_name', '')}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Loại tổ chức</span>
            <span class="info-value">{org_type_label}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Điểm khớp</span>
            <span class="info-value">{score}</span>
        </div>
        <div style="margin-top: 0.75rem;">
            <div class="score-bar-track">
                <div class="score-bar-fill" style="width: {score}%; background: {_score_bar_color(score)};"></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_fuzzy(result: dict) -> None:
    candidates = result.get("candidates", [])

    st.markdown("""
    <div class="safety-banner">
        ⚠️ <strong>Không tìm thấy kết quả chính xác.</strong>
        Hệ thống đề xuất các ứng viên tương tự bên dưới.
        <strong>Hệ thống KHÔNG tự động gán BCA/BQP cho kết quả mờ</strong> — đây là thiết kế an toàn có chủ đích.
    </div>
    """, unsafe_allow_html=True)

    top1 = result.get("top1_score", "")
    top2 = result.get("top2_score", "")
    margin = result.get("score_margin", "")

    meta_parts = [f"Top-1: <strong>{top1}</strong>"]
    if top2:
        meta_parts.append(f"Top-2: <strong>{top2}</strong>")
    if margin is not None:
        meta_parts.append(f"Chênh lệch: <strong>{margin}</strong>")

    st.markdown(f"""
    <div class="glass-card" style="padding: 1rem 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <span style="font-size: 1.05rem; font-weight: 700; color: #FBBF24;">🎯 {len(candidates)} ứng viên tương tự</span>
            <span class="status-chip chip-fuzzy">FUZZY_CANDIDATES</span>
        </div>
        <p style="font-size: 0.82rem; color: #9CA3AF;">{"  •  ".join(meta_parts)}</p>
    </div>
    """, unsafe_allow_html=True)

    for idx, c in enumerate(candidates, 1):
        score = c.get("score", 0)
        org_type_raw = c.get("organization_type_code", "")
        org_type_label = TYPE_CODE_LABELS.get(org_type_raw, org_type_raw)
        bar_color = _score_bar_color(score)

        st.markdown(f"""
        <div class="candidate-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <span class="candidate-rank">#{idx}</span>
                    <span class="candidate-name" style="margin-left: 0.5rem;">{c.get('organization_name', '')}</span>
                    <div class="candidate-meta" style="margin-top: 0.3rem;">
                        {c.get('province_name', '')} • {org_type_label} • <code>{c.get('organization_id', '')}</code>
                    </div>
                </div>
                <div style="text-align: right; min-width: 80px;">
                    <span style="font-size: 1.2rem; font-weight: 700; color: {'#34D399' if score >= 95 else '#FBBF24' if score >= 85 else '#F87171'};">{score}</span>
                    <div class="score-bar-track" style="margin-top: 0.3rem;">
                        <div class="score-bar-fill" style="width: {score}%; background: {bar_color};"></div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_ambiguous(result: dict) -> None:
    candidates = result.get("candidates", [])

    st.markdown(f"""
    <div class="safety-banner">
        ⚠️ <strong>Phát hiện {len(candidates)} tổ chức trùng tên.</strong>
        Vui lòng chọn thêm <strong>Tỉnh/Thành phố</strong> hoặc <strong>Loại tổ chức</strong> trong phần "Tra cứu nâng cao" để phân biệt.
        <strong>Hệ thống KHÔNG đoán mà yêu cầu bạn phân biệt rõ ràng.</strong>
    </div>
    """, unsafe_allow_html=True)

    for idx, c in enumerate(candidates, 1):
        org_type_raw = c.get("organization_type_code", "")
        org_type_label = TYPE_CODE_LABELS.get(org_type_raw, org_type_raw)

        st.markdown(f"""
        <div class="candidate-card">
            <span class="candidate-rank">#{idx}</span>
            <span class="candidate-name" style="margin-left: 0.5rem;">{c.get('organization_name', '')}</span>
            <div class="candidate-meta" style="margin-top: 0.3rem;">
                {c.get('province_name', '')} • {org_type_label} • <code>{c.get('organization_id', '')}</code>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_not_found(result: dict) -> None:
    reason = result.get("reason", "")
    reason_text = {
        "ORGANIZATION_ID_NOT_FOUND": "Mã tổ chức không tồn tại trong Registry.",
        "DETERMINISTIC_MATCH_CONTEXT_MISMATCH": "Tìm thấy tên tổ chức nhưng tỉnh/loại tổ chức không khớp với dữ liệu đã cung cấp.",
        "NO_CANDIDATE_ABOVE_FUZZY_THRESHOLD": f"Không có ứng viên nào đạt ngưỡng điểm tối thiểu ({threshold}).",
    }.get(reason, reason or "Không tìm thấy kết quả nào phù hợp.")

    st.markdown(f"""
    <div class="safety-banner-red">
        ❌ <strong>Không tìm thấy.</strong> {reason_text}
    </div>
    """, unsafe_allow_html=True)


def render_invalid(result: dict) -> None:
    errors = result.get("errors", [])
    reason = result.get("reason", "")
    error_text = ""
    if errors:
        error_text = " • ".join(errors)
    elif reason:
        reason_text = {
            "QUERY_TOO_SHORT_FOR_FUZZY_MATCHING": "Chuỗi tìm kiếm quá ngắn để thực hiện so khớp mờ. Vui lòng nhập ít nhất 3 ký tự.",
        }.get(reason, reason)
        error_text = reason_text

    st.markdown(f"""
    <div class="safety-banner-red">
        ⛔ <strong>Dữ liệu đầu vào không hợp lệ.</strong> {error_text}
    </div>
    """, unsafe_allow_html=True)


def render_pipeline_trace(query_name: str | None, query_id: str | None, result: dict) -> None:
    """Show how the query was processed through the pipeline."""

    status = result["match_status"]
    steps = [
        ("Input Validation", "✅ Hợp lệ", True),
    ]

    if query_name:
        norm = normalize_name(query_name)
        skey = to_search_key(query_name)
        steps.append(("Normalized Name", norm, True))
        steps.append(("Search Key", skey, True))
    elif query_id:
        steps.append(("Organization ID", query_id, True))

    pipeline_stages = [
        ("EXACT_ID_MATCH", "Exact ID Match"),
        ("EXACT_NAME_MATCH", "Exact Name Match"),
        ("NORMALIZED_MATCH", "Normalized Match"),
        ("SEARCH_KEY_MATCH", "Search Key Match"),
        ("ALIAS_MATCH", "Alias Match"),
        ("FUZZY_CANDIDATES", "Fuzzy Matching"),
    ]

    found_stage = False
    for stage_status, stage_label in pipeline_stages:
        if stage_status == status:
            steps.append((stage_label, "⬅ Kết quả trả về tại bước này", True))
            found_stage = True
        elif not found_stage:
            steps.append((stage_label, "Không khớp → tiếp tục", False))

    html_steps = ""
    for label, value, active in steps:
        dot_class = "pipeline-dot-active" if active else "pipeline-dot-inactive"
        html_steps += f"""
        <div class="pipeline-step">
            <div class="pipeline-dot {dot_class}"></div>
            <span class="pipeline-label">{label}:</span>
            <span class="pipeline-value">{value}</span>
        </div>
        """

    with st.expander("🔬 Xem chi tiết quá trình xử lý (Pipeline Trace)", expanded=False):
        st.markdown(f"""
        <div class="glass-card" style="padding: 1.25rem;">
            {html_steps}
        </div>
        """, unsafe_allow_html=True)


# ── Main logic ─────────────────────────────────────────────────────────────

if search_clicked or (org_name and st.session_state.get("_last_query") != org_name):
    if not org_name and not org_id:
        st.warning("⚠️ Vui lòng nhập tên hoặc mã tổ chức để tra cứu.")
    else:
        query_province = None if province_choice == "— Tất cả —" else province_choice
        query_type = None
        if type_choice != "— Tất cả —":
            query_type = type_choice.split(" (")[0]  # Extract code from "CODE (Label)"

        with st.spinner("Đang tìm kiếm..."):
            result = service.search_organization(
                organization_id=org_id if org_id else None,
                organization_name=org_name if org_name else None,
                province_name=query_province,
                organization_type=query_type,
            )

        status = result["match_status"]
        st.session_state["_last_query"] = org_name

        # Route to appropriate renderer
        resolved_statuses = {
            "EXACT_ID_MATCH", "EXACT_NAME_MATCH", "NORMALIZED_MATCH",
            "SEARCH_KEY_MATCH", "ALIAS_MATCH",
        }

        if status in resolved_statuses:
            render_resolved(result)
        elif status == "FUZZY_CANDIDATES":
            render_fuzzy(result)
        elif status == "AMBIGUOUS_MATCH":
            render_ambiguous(result)
        elif status == "NOT_FOUND":
            render_not_found(result)
        elif status == "INVALID_INPUT":
            render_invalid(result)

        # Pipeline trace
        render_pipeline_trace(
            query_name=org_name if org_name else None,
            query_id=org_id if org_id else None,
            result=result,
        )

else:
    # Empty state / landing
    st.markdown("""
    <div class="glass-card" style="text-align: center; padding: 3rem 2rem;">
        <p style="font-size: 3rem; margin-bottom: 0.5rem;">🔍</p>
        <p style="color: #9CA3AF; font-size: 1rem;">
            Nhập tên tổ chức vào ô bên trên và nhấn <strong style="color: #4F8BF9;">Tra cứu</strong> để bắt đầu.
        </p>
        <p style="color: #6B7280; font-size: 0.82rem; margin-top: 0.5rem;">
            Hệ thống hỗ trợ: có dấu, không dấu, viết tắt, lỗi chính tả nhẹ.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Quick examples
    st.markdown("##### 💡 Thử nhanh")
    examples = [
        ("Công an tỉnh Thái Bình", "Thái Bình"),
        ("Bộ Chỉ huy Quân sự tỉnh Quảng Ninh", None),
        ("Cong an Thanh pho Ha Noi", "Hà Nội"),
    ]
    cols = st.columns(len(examples))
    for col, (name, prov) in zip(cols, examples):
        with col:
            label = name[:30] + "..." if len(name) > 30 else name
            if st.button(f"📌 {label}", key=f"ex_{name}", use_container_width=True):
                st.session_state["org_name_input"] = name
                st.rerun()
