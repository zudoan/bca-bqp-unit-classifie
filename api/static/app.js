/**
 * Organization Matching Registry — Frontend Application Logic
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

    // Sidebar & Config
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    const cfgScorer = document.getElementById('cfgScorer');
    const cfgThreshold = document.getElementById('cfgThreshold');
    const cfgThresholdVal = document.getElementById('cfgThresholdVal');
    const cfgTopK = document.getElementById('cfgTopK');
    const cfgTopKVal = document.getElementById('cfgTopKVal');

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
        'EXACT_ID_MATCH': { label: 'Khớp chính xác mã ID (100%)', chipClass: 'chip-resolved', isExact: true },
        'EXACT_NAME_MATCH': { label: 'Khớp chính xác tên (100%)', chipClass: 'chip-resolved', isExact: true },
        'NORMALIZED_MATCH': { label: 'Khớp tên sau chuẩn hóa (100%)', chipClass: 'chip-resolved', isExact: true },
        'SEARCH_KEY_MATCH': { label: 'Khớp không dấu / Search Key (100%)', chipClass: 'chip-resolved', isExact: true },
        'ALIAS_MATCH': { label: 'Khớp tên viết tắt / Tên gọi khác (100%)', chipClass: 'chip-resolved', isExact: true },
        'RESOLVED': { label: 'Khớp chính xác (100%)', chipClass: 'chip-resolved', isExact: true },
        'FUZZY_CANDIDATES': { label: 'So khớp mờ / Fuzzy Matching', chipClass: 'chip-fuzzy', isExact: false },
        'AMBIGUOUS_MATCH': { label: 'Trùng tên — Cần thêm ngữ cảnh', chipClass: 'chip-ambiguous', isExact: false },
        'NOT_FOUND': { label: 'Không tìm thấy', chipClass: 'chip-notfound', isExact: false },
        'INVALID_INPUT': { label: 'Dữ liệu đầu vào không hợp lệ', chipClass: 'chip-invalid', isExact: false },
    };

    // ── Sliders ──────────────────────────────────────────────────────────────
    cfgThreshold.addEventListener('input', () => {
        cfgThresholdVal.textContent = cfgThreshold.value;
    });

    cfgTopK.addEventListener('input', () => {
        cfgTopKVal.textContent = cfgTopK.value;
    });

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
            fuzzy_scorer: cfgScorer.value,
            fuzzy_threshold: parseFloat(cfgThreshold.value),
            fuzzy_top_k: parseInt(cfgTopK.value, 10),
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
            renderResults(data, payload, normRes);
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

    // ── Render Helpers ───────────────────────────────────────────────────────

    function renderResults(data, reqPayload, normData) {
        const status = data.match_status;
        let html = '';

        // Deterministic Match
        const isDeterministic = [
            'EXACT_ID_MATCH',
            'EXACT_NAME_MATCH',
            'NORMALIZED_MATCH',
            'SEARCH_KEY_MATCH',
            'ALIAS_MATCH',
            'RESOLVED'
        ].includes(status);

        if (isDeterministic) {
            html += renderDeterministicCard(data, status);
        } else if (status === 'FUZZY_CANDIDATES') {
            html += renderFuzzyCard(data, reqPayload);
        } else if (status === 'AMBIGUOUS_MATCH') {
            html += renderAmbiguousCard(data);
        } else if (status === 'NOT_FOUND') {
            html += renderNotFoundCard(data, reqPayload);
        } else if (status === 'INVALID_INPUT') {
            html += renderInvalidInputCard(data);
        } else {
            html += `<div class="glass-card"><p>Trạng thái: ${escapeHtml(status)}</p></div>`;
        }

        // Candidates list
        if (data.candidates && data.candidates.length > 0) {
            html += renderCandidatesSection(data.candidates, status);
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

    function renderDeterministicCard(data, status) {
        const isBCA = data.management === 'BCA';
        const isBQP = data.management === 'BQP';
        const badgeClass = isBCA ? 'badge-bca' : (isBQP ? 'badge-bqp' : 'badge-bca');
        const mgmtFull = isBCA ? 'Bộ Công an' : (isBQP ? 'Bộ Quốc phòng' : (data.management || 'Chưa xác định'));

        const info = STATUS_INFO[status] || { label: status, chipClass: 'chip-resolved' };
        const score = data.match_score != null ? Math.round(data.match_score) : 100;
        const typeLabel = TYPE_CODE_LABELS[data.organization_type_code] || data.organization_type_code || '—';

        return `
            <div class="glass-card">
                <div class="result-badge-section">
                    <div class="management-subtitle">KẾT LUẬN CƠ QUAN QUẢN LÝ</div>
                    <div class="${badgeClass}">${escapeHtml(data.management || 'N/A')}</div>
                    <div class="management-label">${escapeHtml(mgmtFull)}</div>
                    <div style="margin-top: 0.85rem;">
                        <span class="status-chip ${info.chipClass}">✅ ${escapeHtml(info.label)}</span>
                    </div>
                </div>

                <div class="detail-header">
                    <h3>📋 Chi tiết tổ chức xác định</h3>
                    <span style="font-size: 0.85rem; color: #9CA3AF;">Độ khớp: <strong style="color: #34D399; font-size: 1rem;">${score}%</strong></span>
                </div>

                <div class="score-bar-container">
                    <div class="score-bar-track">
                        <div class="score-bar-fill" style="width: ${score}%; background: #34D399;"></div>
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

    function renderFuzzyCard(data, reqPayload) {
        const candidates = data.candidates || [];
        const top1 = candidates.length > 0 ? candidates[0] : null;

        const top1Score = data.top1_score != null ? Math.round(data.top1_score) : (top1 && top1.score != null ? Math.round(top1.score) : 0);
        const top2Score = data.top2_score != null ? Math.round(data.top2_score) : null;
        const margin = data.score_margin != null ? data.score_margin : (top2Score != null ? (top1Score - top2Score).toFixed(1) : null);

        let top1Html = '';
        if (top1) {
            const isBCA = top1.management === 'BCA';
            const isBQP = top1.management === 'BQP';
            const badgeClass = isBCA ? 'badge-bca' : (isBQP ? 'badge-bqp' : 'badge-bca');
            const mgmtFull = isBCA ? 'Bộ Công an' : (isBQP ? 'Bộ Quốc phòng' : (top1.management || 'Chưa xác định'));
            const typeLabel = TYPE_CODE_LABELS[top1.organization_type_code] || top1.organization_type_code || '—';

            top1Html = `
                <div class="result-badge-section" style="padding: 1.5rem 1rem 1rem;">
                    <div class="management-subtitle">GỢI Ý CƠ QUAN QUẢN LÝ (TOP 1 ỨNG VIÊN)</div>
                    <div class="${badgeClass}">${escapeHtml(top1.management || 'N/A')}</div>
                    <div class="management-label">${escapeHtml(mgmtFull)}</div>
                    <div style="margin-top: 0.85rem;">
                        <span class="status-chip chip-fuzzy">🔍 FUZZY TOP-1 (${top1Score}%)</span>
                    </div>
                </div>

                <div class="safety-banner">
                    ⚡ <strong>So khớp mờ (Fuzzy Match):</strong> Không có khớp chính xác 100%. 
                    Tìm thấy <strong>${candidates.length}</strong> ứng viên có điểm tương đồng ≥ ${reqPayload.fuzzy_threshold}%.
                    <br>• Điểm cao nhất: <strong>${top1Score}%</strong> 
                    ${top2Score ? `• Top-2: <strong>${top2Score}%</strong>` : ''} 
                    ${margin !== null ? `• Chênh lệch điểm (Margin): <strong>${margin}</strong> điểm` : ''}
                </div>

                <div class="detail-header">
                    <h3>🎯 Ứng viên phù hợp nhất (Top 1)</h3>
                    <span style="font-size: 0.85rem; color: #9CA3AF;">Độ khớp: <strong style="color: #FBBF24; font-size: 1rem;">${top1Score}%</strong></span>
                </div>

                <div class="score-bar-container">
                    <div class="score-bar-track">
                        <div class="score-bar-fill" style="width: ${top1Score}%; background: #FBBF24;"></div>
                    </div>
                </div>

                <div style="margin-top: 1.25rem;">
                    <div class="info-row">
                        <span class="info-label">Mã tổ chức</span>
                        <span class="info-value mono">${escapeHtml(top1.organization_id || '—')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Tên tổ chức chính thức</span>
                        <span class="info-value">${escapeHtml(top1.organization_name || '—')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Tỉnh / Thành phố</span>
                        <span class="info-value">${escapeHtml(top1.province_name || 'Trung ương / Toàn quốc')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Loại tổ chức</span>
                        <span class="info-value">${escapeHtml(typeLabel)} <code style="font-size: 0.75rem; color: #9CA3AF;">(${escapeHtml(top1.organization_type_code || '')})</code></span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Cơ quan chủ quản dự kiến</span>
                        <span class="info-value" style="color: ${isBCA ? '#60A5FA' : '#34D399'}; font-weight: 700;">
                            ${escapeHtml(top1.management || '—')} — ${escapeHtml(mgmtFull)}
                        </span>
                    </div>
                </div>
            `;
        }

        return `
            <div class="glass-card">
                ${top1Html}
            </div>
        `;
    }

    function renderAmbiguousCard(data) {
        const candidates = data.candidates || [];
        return `
            <div class="glass-card">
                <div style="text-align: center; margin-bottom: 1.25rem;">
                    <span class="status-chip chip-ambiguous">⚠️ AMBIGUOUS_MATCH (Trùng tên — Cần thêm ngữ cảnh)</span>
                </div>
                <div class="safety-banner">
                    ⚠️ <strong>Phát hiện ${candidates.length} tổ chức trùng tên:</strong> 
                    Hệ thống không tự ý suy diễn để bảo đảm tính an toàn dữ liệu.
                    <br>Vui lòng mở mục <strong>"Tra cứu nâng cao"</strong> và chọn thêm <strong>Tỉnh / Thành phố</strong> hoặc <strong>Loại tổ chức</strong> để phân định chính xác.
                </div>
            </div>
        `;
    }

    function renderNotFoundCard(data, reqPayload) {
        const reasonText = {
            'ORGANIZATION_ID_NOT_FOUND': 'Mã tổ chức không tồn tại trong Registry.',
            'DETERMINISTIC_MATCH_CONTEXT_MISMATCH': 'Tìm thấy tên tổ chức nhưng tỉnh/loại tổ chức không khớp với điều kiện lọc.',
            'NO_CANDIDATE_ABOVE_FUZZY_THRESHOLD': `Không có ứng viên nào đạt ngưỡng điểm tối thiểu (${reqPayload.fuzzy_threshold}%).`,
        }[data.reason] || data.reason || 'Không tìm thấy kết quả nào phù hợp trong Registry.';

        return `
            <div class="glass-card">
                <div style="text-align: center; margin-bottom: 1.25rem;">
                    <span class="status-chip chip-notfound">❌ NOT FOUND (Không tìm thấy)</span>
                </div>
                <div class="safety-banner-red">
                    ❌ <strong>Không tìm thấy:</strong> ${escapeHtml(reasonText)}
                </div>
                <div style="font-size: 0.88rem; color: #9CA3AF; margin-top: 0.75rem; line-height: 1.6;">
                    💡 <strong>Gợi ý tra cứu:</strong>
                    <ul style="margin-left: 1.5rem; margin-top: 0.35rem;">
                        <li>Kiểm tra lại chính tả hoặc thử nhập từ khóa ngắn gọn hơn (VD: "Công an Thái Bình" thay vì tên quá dài).</li>
                        <li>Hạ ngưỡng Fuzzy (thanh gạt ở menu bên trái, VD: 75 hoặc 80) để nới lỏng mức độ khớp.</li>
                        <li>Nếu bạn biết Mã tổ chức (ID), hãy mở mục "Tra cứu nâng cao" và nhập trực tiếp mã.</li>
                    </ul>
                </div>
            </div>
        `;
    }

    function renderInvalidInputCard(data) {
        const errorList = data.errors && data.errors.length > 0 
            ? data.errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')
            : `<li>${escapeHtml(data.reason || 'Dữ liệu đầu vào không hợp lệ.')}</li>`;

        return `
            <div class="glass-card">
                <div style="text-align: center; margin-bottom: 1.25rem;">
                    <span class="status-chip chip-invalid">🚫 INVALID INPUT (Dữ liệu không hợp lệ)</span>
                </div>
                <div class="safety-banner-red">
                    🚫 Yêu cầu tra cứu không hợp lệ:
                    <ul style="margin-left: 1.5rem; margin-top: 0.35rem;">
                        ${errorList}
                    </ul>
                </div>
            </div>
        `;
    }

    function renderCandidatesSection(candidates, status) {
        const title = status === 'EXACT_NAME_MATCH' || status === 'EXACT_ID_MATCH'
            ? 'Ứng viên khớp chính xác'
            : 'Danh sách ứng viên tương tự';

        const cardsHtml = candidates.map((c, idx) => {
            const score = c.score != null ? Math.round(c.score) : '—';
            let scoreClass = 'score-high';
            if (typeof score === 'number') {
                if (score < 80) scoreClass = 'score-low';
                else if (score < 90) scoreClass = 'score-medium';
            }

            const typeLabel = TYPE_CODE_LABELS[c.organization_type_code] || c.organization_type_code || '';
            const isBCA = c.management === 'BCA';
            const isBQP = c.management === 'BQP';
            const mgmtBadge = c.management ? `
                <span style="display: inline-block; padding: 0.15rem 0.5rem; border-radius: 6px; font-size: 0.72rem; font-weight: 700; background: ${isBCA ? 'rgba(37,99,235,0.2)' : 'rgba(5,150,105,0.2)'}; color: ${isBCA ? '#60A5FA' : '#34D399'}; border: 1px solid ${isBCA ? 'rgba(37,99,235,0.4)' : 'rgba(5,150,105,0.4)'}; margin-left: 0.5rem;">
                    ${escapeHtml(c.management)}
                </span>
            ` : '';

            return `
                <div class="candidate-card">
                    <div class="candidate-top">
                        <div>
                            <span class="candidate-rank">#${idx + 1}</span>
                            <span class="candidate-name">${escapeHtml(c.organization_name || '—')}</span>
                            ${mgmtBadge}
                            <div class="candidate-meta">
                                Mã: <code>${escapeHtml(c.organization_id || '—')}</code> 
                                ${c.province_name ? `• Tỉnh: <strong>${escapeHtml(c.province_name)}</strong>` : ''} 
                                ${typeLabel ? `• Loại: <em>${escapeHtml(typeLabel)}</em>` : ''}
                                ${c.matched_on ? `• Khớp trên: <code>${escapeHtml(c.matched_on)}</code>` : ''}
                            </div>
                        </div>
                        <div class="candidate-score">
                            <div class="score-num ${scoreClass}">${score}${typeof score === 'number' ? '%' : ''}</div>
                            <div style="font-size: 0.7rem; color: #6B7280;">Điểm khớp</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="glass-card" style="margin-top: 1.25rem;">
                <div class="detail-header">
                    <h3>👥 ${title} (${candidates.length})</h3>
                </div>
                <div>
                    ${cardsHtml}
                </div>
            </div>
        `;
    }

    function renderPipelineTrace(data, reqPayload, normData) {
        const normText = normData ? normData.normalized : '—';
        const searchKey = normData ? normData.search_key : '—';

        const isExact = [
            'EXACT_ID_MATCH',
            'EXACT_NAME_MATCH',
            'NORMALIZED_MATCH',
            'SEARCH_KEY_MATCH',
            'ALIAS_MATCH'
        ].includes(data.match_status);

        const isFuzzy = data.match_status === 'FUZZY_CANDIDATES' || data.match_status === 'AMBIGUOUS_MATCH';

        const mgmtConclusion = data.management 
            ? ` → ${escapeHtml(data.management)}` 
            : (data.candidates && data.candidates.length > 0 && data.candidates[0].management ? ` → ${escapeHtml(data.candidates[0].management)} (Dự kiến)` : '');

        return `
            <div class="glass-card" style="margin-top: 1.25rem;">
                <div class="pipeline-toggle" id="pipelineToggle">
                    <span class="chevron">▶</span>
                    <span>🔬 Pipeline Trace (Xem luồng xử lý chi tiết)</span>
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
                        <div class="pipeline-dot ${isExact ? 'pipeline-dot-active' : 'pipeline-dot-inactive'}"></div>
                        <div class="pipeline-label">4. Exact Match:</div>
                        <div class="pipeline-value">${isExact ? `${escapeHtml(data.match_status)} (HIT 100%)` : 'MISS'}</div>
                    </div>
                    <div class="pipeline-step">
                        <div class="pipeline-dot ${isFuzzy ? 'pipeline-dot-active' : 'pipeline-dot-inactive'}"></div>
                        <div class="pipeline-label">5. Fuzzy Match:</div>
                        <div class="pipeline-value">
                            ${isFuzzy ? `${escapeHtml(reqPayload.fuzzy_scorer)} (Threshold: ${reqPayload.fuzzy_threshold}%, Top-K: ${reqPayload.fuzzy_top_k})` : 'SKIPPED (Exact hit)'}
                        </div>
                    </div>
                    <div class="pipeline-step">
                        <div class="pipeline-dot pipeline-dot-active"></div>
                        <div class="pipeline-label">6. Decision:</div>
                        <div class="pipeline-value" style="color: #60A5FA; font-weight: 700;">
                            ${escapeHtml(data.match_status)}${mgmtConclusion}
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
