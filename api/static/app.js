/**
 * Organization Matching Registry — Frontend Application Logic
 * Strict Deterministic Binary Search (100% Match or UNKNOWN)
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Elements ─────────────────────────────────────────────────────────────
    const orgNameInput = document.getElementById('orgNameInput');
    const orgIdInput = document.getElementById('orgIdInput');
    const provinceSelect = document.getElementById('provinceSelect');
    const typeSelect = document.getElementById('typeSelect');
    const searchBtn = document.getElementById('searchBtn');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const emptyState = document.getElementById('emptyState');

    // Sidebar
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    // Advanced filters
    const advancedToggle = document.getElementById('advancedToggle');
    const advancedFilters = document.getElementById('advancedFilters');

    // Stats
    const statTotal = document.getElementById('statTotal');
    const statProvinces = document.getElementById('statProvinces');
    const statBCA = document.getElementById('statBCA');
    const statBQP = document.getElementById('statBQP');

    // ── Organization Type Labels ─────────────────────────────────────────────
    const TYPE_CODE_LABELS = {
        'POLICE_PROVINCE': 'Công an tỉnh/TP',
        'POLICE_DEPARTMENT': 'Phòng ban CA tỉnh',
        'POLICE_DISTRICT': 'Công an huyện/quận',
        'POLICE_DISTRICT_DEPT': 'Đội CA huyện/quận',
        'POLICE_PRISON': 'Trại giam',
        'POLICE_HOSPITAL': 'Bệnh viện CA',
        'MILITARY_PROVINCE': 'Bộ CHQS tỉnh/TP',
        'MILITARY_DEPARTMENT': 'Phòng ban QS tỉnh',
        'MILITARY_DISTRICT': 'Ban CHQS huyện/quận',
        'MILITARY_DISTRICT_DEPT': 'Đội QS huyện/quận',
        'MILITARY_BORDER_CMD': 'Đồn Biên phòng - BCH',
        'MILITARY_BORDER_POST': 'Đồn Biên phòng - Trạm',
        'MILITARY_BORDER_SQUADRON': 'Đồn BP - Đại đội',
        'MILITARY_HOSPITAL': 'Bệnh viện QY',
        'MILITARY_REGION': 'Quân khu',
        'MILITARY_SERVICE': 'Quân chủng/Binh chủng',
        'ACADEMY': 'Học viện',
        'UNIVERSITY': 'Đại học / Trường',
        'GENERAL_DEPARTMENT': 'Tổng cục/Cục trực thuộc',
        'MINISTRY_DEPARTMENT': 'Cục Bộ',
    };

    const STATUS_INFO = {
        'EXACT_ID_MATCH': 'Khớp chính xác mã ID',
        'EXACT_NAME_MATCH': 'Khớp chính xác tên tổ chức',
        'NORMALIZED_MATCH': 'Khớp tên sau chuẩn hóa',
        'SEARCH_KEY_MATCH': 'Khớp không dấu (Search Key)',
        'ALIAS_MATCH': 'Khớp tên viết tắt / Tên gọi khác',
        'RESOLVED': 'Khớp chính xác',
        'NOT_FOUND': 'Không có dữ liệu',
        'INVALID_INPUT': 'Dữ liệu không hợp lệ',
    };

    // ── Mobile Sidebar Toggle ────────────────────────────────────────────────
    if (sidebarToggle && sidebar && sidebarBackdrop) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarBackdrop.classList.toggle('show');
        });

        sidebarBackdrop.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarBackdrop.classList.remove('show');
        });
    }

    // ── Advanced Filters Toggle ──────────────────────────────────────────────
    if (advancedToggle && advancedFilters) {
        advancedToggle.addEventListener('click', () => {
            advancedToggle.classList.toggle('open');
            advancedFilters.classList.toggle('show');
        });
    }

    // ── Fetch Registry Stats on Init ─────────────────────────────────────────
    async function loadStats() {
        try {
            const res = await fetch('/api/stats');
            if (!res.ok) return;
            const data = await res.json();

            if (statTotal) statTotal.textContent = Number(data.total).toLocaleString('vi-VN');
            if (statProvinces) statProvinces.textContent = Number(data.province_count).toLocaleString('vi-VN');
            if (statBCA) statBCA.textContent = Number(data.bca_count).toLocaleString('vi-VN');
            if (statBQP) statBQP.textContent = Number(data.bqp_count).toLocaleString('vi-VN');

            // Populate province options
            if (provinceSelect && Array.isArray(data.provinces)) {
                data.provinces.forEach(p => {
                    if (p) {
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.textContent = p;
                        provinceSelect.appendChild(opt);
                    }
                });
            }

            // Populate type options
            if (typeSelect && Array.isArray(data.type_codes)) {
                data.type_codes.forEach(t => {
                    if (t) {
                        const opt = document.createElement('option');
                        opt.value = t;
                        opt.textContent = `${t} (${TYPE_CODE_LABELS[t] || t})`;
                        typeSelect.appendChild(opt);
                    }
                });
            }
        } catch (err) {
            console.error('Lỗi khi tải thống kê registry:', err);
        }
    }

    loadStats();

    // ── Search Action ────────────────────────────────────────────────────────
    async function doSearch() {
        const orgName = orgNameInput.value.trim();
        const orgId = orgIdInput.value.trim();
        const province = provinceSelect.value || null;
        const orgType = typeSelect.value || null;

        if (!orgName && !orgId) {
            orgNameInput.focus();
            return;
        }

        // UI state: loading
        loading.classList.add('show');
        results.innerHTML = '';
        emptyState.style.display = 'none';
        searchBtn.disabled = true;

        const payload = {
            organization_name: orgName || null,
            organization_id: orgId || null,
            province_name: province,
            organization_type: orgType,
        };

        try {
            const [searchRes, normRes] = await Promise.all([
                fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                }),
                orgName ? fetch(`/api/normalize?q=${encodeURIComponent(orgName)}`).then(r => r.json()).catch(() => null) : Promise.resolve(null)
            ]);

            if (!searchRes.ok) {
                const errData = await searchRes.json().catch(() => ({}));
                throw new Error(errData.detail || `Lỗi server: ${searchRes.status}`);
            }

            const data = await searchRes.json();
            renderBinaryResults(data, payload, normRes);
        } catch (err) {
            renderError(err.message || 'Có lỗi xảy ra khi tra cứu.');
        } finally {
            loading.classList.remove('show');
            searchBtn.disabled = false;
        }
    }

    searchBtn.addEventListener('click', doSearch);

    orgNameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            doSearch();
        }
    });

    orgIdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            doSearch();
        }
    });

    // ── Quick Examples ───────────────────────────────────────────────────────
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const name = btn.getAttribute('data-name');
            if (name) {
                orgNameInput.value = name;
                orgIdInput.value = '';
                provinceSelect.value = '';
                typeSelect.value = '';
                doSearch();
            }
        });
    });

    // ── Render Helpers (Strict Binary) ───────────────────────────────────────

    function renderBinaryResults(data, reqPayload, normData) {
        let html = '';

        if (data.status === 'MATCH_100') {
            html += renderMatch100Card(data);
        } else {
            html += renderUnknownCard(data, reqPayload);
        }

        // Pipeline trace collapsible
        html += renderPipelineTrace(data, reqPayload, normData);

        results.innerHTML = html;

        // Attach event listener for pipeline toggle
        const pipeToggle = document.getElementById('pipelineToggle');
        const pipeContent = document.getElementById('pipelineContent');
        if (pipeToggle && pipeContent) {
            pipeToggle.addEventListener('click', () => {
                pipeToggle.classList.toggle('open');
                pipeContent.classList.toggle('show');
            });
        }
    }

    function renderMatch100Card(data) {
        const isBCA = data.management === 'BCA';
        const isBQP = data.management === 'BQP';
        const badgeClass = isBCA ? 'badge-bca' : (isBQP ? 'badge-bqp' : 'badge-bca');
        const mgmtFull = isBCA ? 'Bộ Công an' : (isBQP ? 'Bộ Quốc phòng' : (data.management || 'Chưa xác định'));
        const matchTypeLabel = STATUS_INFO[data.match_status] || data.match_status;
        const typeLabel = TYPE_CODE_LABELS[data.organization_type_code] || data.organization_type_code || '—';

        return `
            <div class="glass-card">
                <div class="result-badge-section">
                    <div class="management-subtitle">KẾT LUẬN CƠ QUAN QUẢN LÝ</div>
                    <div class="${badgeClass}">${escapeHtml(data.management || 'N/A')}</div>
                    <div class="management-label">${escapeHtml(mgmtFull)}</div>
                    <div style="margin-top: 0.85rem;">
                        <span class="status-chip chip-resolved">✅ ĐÚNG 100% — ${escapeHtml(matchTypeLabel)}</span>
                    </div>
                </div>

                <div class="detail-header">
                    <h3>📋 Chi tiết tổ chức xác định</h3>
                    <span style="font-size: 0.85rem; color: #34D399; font-weight: 700;">Độ chính xác: 100%</span>
                </div>

                <div class="score-bar-container">
                    <div class="score-bar-track">
                        <div class="score-bar-fill" style="width: 100%; background: #34D399;"></div>
                    </div>
                </div>

                <div style="margin-top: 1.25rem;">
                    <div class="info-row">
                        <span class="info-label">Mã tổ chức</span>
                        <span class="info-value mono">${escapeHtml(data.organization_id || '—')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Tên tổ chức chính thức</span>
                        <span class="info-value">${escapeHtml(data.organization_name || '—')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Tỉnh / Thành phố</span>
                        <span class="info-value">${escapeHtml(data.province_name || 'Trung ương / Toàn quốc')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Loại tổ chức</span>
                        <span class="info-value">${escapeHtml(typeLabel)} <code style="font-size: 0.75rem; color: #9CA3AF;">(${escapeHtml(data.organization_type_code || '')})</code></span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Cơ quan chủ quản</span>
                        <span class="info-value" style="color: ${isBCA ? '#60A5FA' : '#34D399'}; font-weight: 700;">
                            ${escapeHtml(data.management || '—')} — ${escapeHtml(mgmtFull)}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }

    function renderUnknownCard(data, reqPayload) {
        return `
            <div class="glass-card">
                <div style="text-align: center; margin-bottom: 1.25rem;">
                    <span class="status-chip chip-notfound">❌ UNKNOWN (Không có dữ liệu)</span>
                </div>
                <div class="safety-banner-red">
                    ❌ <strong>Không có dữ liệu cho đơn vị này:</strong> Hệ thống không tìm thấy tổ chức nào khớp chính xác 100% trong cơ sở dữ liệu BCA / BQP.
                </div>
                <div style="font-size: 0.88rem; color: #9CA3AF; margin-top: 0.75rem; line-height: 1.6;">
                    💡 <strong>Lưu ý về thuật toán:</strong>
                    <ul style="margin-left: 1.5rem; margin-top: 0.35rem;">
                        <li>Hệ thống áp dụng cơ chế <strong>Strict Deterministic Search</strong> — chỉ kết luận khi khớp chính xác 100%, tuyệt đối không phỏng đoán hay gợi ý gần đúng.</li>
                        <li>Kiểm tra lại chính tả của tên tổ chức (VD: "Công an tỉnh Thái Bình").</li>
                        <li>Nếu có Mã tổ chức (ID), hãy mở "Tra cứu nâng cao" và nhập trực tiếp mã.</li>
                    </ul>
                </div>
            </div>
        `;
    }

    function renderPipelineTrace(data, reqPayload, normData) {
        const normText = normData ? normData.normalized : '—';
        const searchKey = normData ? normData.search_key : '—';
        const isMatched = data.status === 'MATCH_100';

        return `
            <div class="glass-card" style="margin-top: 1.25rem;">
                <div class="pipeline-toggle" id="pipelineToggle">
                    <span class="chevron">▶</span>
                    <span>🔬 Pipeline Trace (Luồng xử lý chi tiết)</span>
                </div>
                <div class="pipeline-content" id="pipelineContent">
                    <div class="pipeline-step">
                        <div class="pipeline-dot pipeline-dot-active"></div>
                        <div class="pipeline-label">1. Input Query:</div>
                        <div class="pipeline-value">${escapeHtml(reqPayload.organization_name || reqPayload.organization_id || '—')}</div>
                    </div>
                    <div class="pipeline-step">
                        <div class="pipeline-dot pipeline-dot-active"></div>
                        <div class="pipeline-label">2. Normalization:</div>
                        <div class="pipeline-value">${escapeHtml(normText)}</div>
                    </div>
                    <div class="pipeline-step">
                        <div class="pipeline-dot pipeline-dot-active"></div>
                        <div class="pipeline-label">3. Search Key:</div>
                        <div class="pipeline-value">${escapeHtml(searchKey)}</div>
                    </div>
                    <div class="pipeline-step">
                        <div class="pipeline-dot ${isMatched ? 'pipeline-dot-active' : 'pipeline-dot-inactive'}"></div>
                        <div class="pipeline-label">4. Strict Match:</div>
                        <div class="pipeline-value">${isMatched ? `HIT (100% - ${escapeHtml(data.match_status)})` : 'MISS (No exact match)'}</div>
                    </div>
                    <div class="pipeline-step">
                        <div class="pipeline-dot pipeline-dot-inactive"></div>
                        <div class="pipeline-label">5. Fuzzy Match:</div>
                        <div class="pipeline-value" style="color: #9CA3AF;">DISABLED (Strict mode: 100% or Unknown)</div>
                    </div>
                    <div class="pipeline-step">
                        <div class="pipeline-dot pipeline-dot-active"></div>
                        <div class="pipeline-label">6. Kết luận:</div>
                        <div class="pipeline-value" style="color: ${isMatched ? '#60A5FA' : '#F87171'}; font-weight: 700;">
                            ${escapeHtml(data.status)} ${data.management ? `→ ${escapeHtml(data.management)}` : '→ Không có dữ liệu'}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function renderError(message) {
        results.innerHTML = `
            <div class="glass-card">
                <div class="safety-banner-red">
                    ❌ <strong>Đã xảy ra lỗi:</strong> ${escapeHtml(message)}
                </div>
            </div>
        `;
    }

    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
});
