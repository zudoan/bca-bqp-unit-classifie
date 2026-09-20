import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { GoogleIcon } from "./components/Icons";
import { apiMode, getRegistryStats, searchOrganization } from "./services/searchApi";
import type {
  OrganizationCandidate,
  RegistryStats,
  SearchRequest,
  SearchResponse,
} from "./types/search";

const DEFAULT_STATS: RegistryStats = { total: 14_303, bca: 9_689, bqp: 4_614, provinces: 63 };

const PROVINCES = [
  "An Giang", "Bà Rịa - Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu", "Bắc Ninh",
  "Bến Tre", "Bình Định", "Bình Dương", "Bình Phước", "Bình Thuận", "Cà Mau", "Cần Thơ",
  "Cao Bằng", "Đà Nẵng", "Đắk Lắk", "Đắk Nông", "Điện Biên", "Đồng Nai", "Đồng Tháp",
  "Gia Lai", "Hà Giang", "Hà Nam", "Hà Nội", "Hà Tĩnh", "Hải Dương", "Hải Phòng", "Hậu Giang",
  "Hòa Bình", "Hưng Yên", "Khánh Hòa", "Kiên Giang", "Kon Tum", "Lai Châu", "Lâm Đồng",
  "Lạng Sơn", "Lào Cai", "Long An", "Nam Định", "Nghệ An", "Ninh Bình", "Ninh Thuận",
  "Phú Thọ", "Phú Yên", "Quảng Bình", "Quảng Nam", "Quảng Ngãi", "Quảng Ninh",
  "Quảng Trị", "Sóc Trăng", "Sơn La", "Tây Ninh", "Thái Bình", "Thái Nguyên", "Thanh Hóa",
  "Thành phố Hồ Chí Minh", "Thừa Thiên Huế", "Tiền Giang", "Trà Vinh", "Tuyên Quang",
  "Vĩnh Long", "Vĩnh Phúc", "Yên Bái",
];

const ORGANIZATION_TYPES = [
  ["POLICE_PROVINCE", "Công an tỉnh / thành phố"],
  ["POLICE_DEPARTMENT", "Phòng nghiệp vụ Công an tỉnh"],
  ["POLICE_DISTRICT", "Công an huyện / quận"],
  ["POLICE_DISTRICT_DEPT", "Đội nghiệp vụ Công an huyện"],
  ["POLICE_PRISON", "Trại giam"],
  ["POLICE_HOSPITAL", "Bệnh viện Công an"],
  ["MILITARY_PROVINCE", "Bộ Chỉ huy Quân sự tỉnh"],
  ["MILITARY_DEPARTMENT", "Phòng trực thuộc Bộ CHQS tỉnh"],
  ["MILITARY_DISTRICT", "Ban Chỉ huy Quân sự huyện"],
  ["MILITARY_DISTRICT_DEPT", "Ban trực thuộc Ban CHQS huyện"],
  ["MILITARY_BORDER_CMD", "Bộ Chỉ huy Bộ đội Biên phòng"],
  ["MILITARY_BORDER_POST", "Đồn / Trạm Biên phòng"],
  ["MILITARY_BORDER_SQUADRON", "Hải đội Biên phòng"],
  ["MILITARY_HOSPITAL", "Bệnh viện Quân y"],
  ["MILITARY_REGION", "Quân khu"],
  ["MILITARY_SERVICE", "Quân chủng / Binh chủng"],
  ["ACADEMY", "Học viện"],
  ["UNIVERSITY", "Trường đại học / cao đẳng"],
  ["GENERAL_DEPARTMENT", "Tổng cục / Cục trực thuộc"],
  ["MINISTRY_DEPARTMENT", "Đơn vị trực thuộc Bộ"],
] as const;

const TYPE_LABELS = Object.fromEntries(ORGANIZATION_TYPES);

const STATUS_LABELS: Record<string, string> = {
  EXACT_ID_MATCH: "Khớp chính xác mã tổ chức",
  EXACT_NAME_MATCH: "Khớp chính xác tên đăng ký",
  NORMALIZED_MATCH: "Khớp tên sau chuẩn hóa",
  SEARCH_KEY_MATCH: "Khớp khóa tìm kiếm không dấu",
  ALIAS_MATCH: "Khớp tên viết tắt / tên gọi khác",
  AMBIGUOUS_MATCH: "Nhiều tổ chức cùng thỏa điều kiện",
  NOT_FOUND: "Không tìm thấy kết quả",
  INVALID_INPUT: "Dữ liệu đầu vào chưa hợp lệ",
};

const EXAMPLES = [
  "Công an tỉnh Thái Bình",
  "Bộ Chỉ huy Quân sự tỉnh Quảng Ninh",
  "BCHQS huyện Sóc Sơn",
  "Công an huyện Châu Thành",
];

function normalizePreview(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("vi")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

function searchKeyPreview(value: string) {
  return normalizePreview(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d");
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("vi-VN").format(value);
}

function App() {
  const [organizationName, setOrganizationName] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [province, setProvince] = useState("");
  const [organizationType, setOrganizationType] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [lastRequest, setLastRequest] = useState<SearchRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [networkError, setNetworkError] = useState("");
  const [stats, setStats] = useState(DEFAULT_STATS);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getRegistryStats().then(setStats).catch(() => setStats(DEFAULT_STATS));
    return () => abortRef.current?.abort();
  }, []);

  const requestFromForm = (): SearchRequest => ({
    organization_name: organizationName.trim() || undefined,
    organization_id: organizationId.trim() || undefined,
    province_name: province || undefined,
    organization_type: organizationType || undefined,
  });

  async function runSearch(request: SearchRequest) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setNetworkError("");
    setResult(null);
    setLastRequest(request);

    try {
      const response = await searchOrganization(request, controller.signal);
      setResult(response);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setNetworkError(error instanceof Error ? error.message : "Không thể kết nối tới dịch vụ tra cứu.");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void runSearch(requestFromForm());
  }

  function chooseExample(example: string) {
    setOrganizationName(example);
    setOrganizationId("");
    setProvince("");
    setOrganizationType("");
    void runSearch({ organization_name: example });
  }

  function chooseCandidate(candidate: OrganizationCandidate) {
    setOrganizationId(candidate.organization_id);
    setOrganizationName(candidate.organization_name);
    setProvince(candidate.province_name || "");
    setOrganizationType(candidate.organization_type_code);
    void runSearch({ organization_id: candidate.organization_id });
  }

  function resetSearch() {
    abortRef.current?.abort();
    setOrganizationName("");
    setOrganizationId("");
    setProvince("");
    setOrganizationType("");
    setResult(null);
    setLastRequest(null);
    setNetworkError("");
    setLoading(false);
  }

  return (
    <div className="portal-shell">
      <Sidebar stats={stats} />

      <div className="portal-main">
        <header className="command-bar">
          <div className="mobile-brand">
            <span className="brand-seal"><GoogleIcon name="account_balance" size={22} filled /></span>
            <strong>Registry BCA / BQP</strong>
          </div>
          <div className="breadcrumb" aria-label="Vị trí hiện tại">
            <span>Hệ thống định danh</span><i>/</i><strong>Tra cứu tổ chức</strong>
          </div>
          <div className="runtime-status" title={apiMode === "mock" ? "Dữ liệu mô phỏng frontend" : "Đã kết nối backend"}>
            <span className="runtime-dot" />
            {apiMode === "mock" ? "Môi trường trình diễn" : "Kết nối trực tuyến"}
          </div>
        </header>

        <main className="workspace-main">
          <section className="page-heading">
            <div>
              <span className="section-code">ORG RESOLUTION · V1</span>
              <h1>Tra cứu và định danh tổ chức</h1>
              <p>Đối chiếu tên đơn vị với Master Registry trước khi xác định cơ quan quản lý BCA hoặc BQP.</p>
            </div>
            <div className="policy-mark">
              <span>Nguyên tắc kết luận</span>
              <strong>Khớp tuyệt đối</strong>
              <small>Không sử dụng suy đoán gần đúng</small>
            </div>
          </section>

          <RegistryStatsBar stats={stats} />

          <section className="registry-desk">
            <SearchPanel
              organizationName={organizationName}
              organizationId={organizationId}
              province={province}
              organizationType={organizationType}
              loading={loading}
              hasResult={Boolean(result || networkError)}
              onOrganizationName={setOrganizationName}
              onOrganizationId={setOrganizationId}
              onProvince={setProvince}
              onOrganizationType={setOrganizationType}
              onSubmit={handleSubmit}
              onExample={chooseExample}
              onReset={resetSearch}
            />

            <div className="output-stack" aria-live="polite" aria-busy={loading}>
              <ResultPanel
                result={result}
                loading={loading}
                networkError={networkError}
                request={lastRequest}
                onCandidate={chooseCandidate}
              />
              <PipelinePanel result={result} loading={loading} request={lastRequest} />
            </div>
          </section>
        </main>

        <footer className="portal-footer">
          <span>Hệ thống tra cứu tổ chức BCA / BQP</span>
          <span>Nguồn đối chiếu: Master Registry · Chế độ Strict Deterministic</span>
        </footer>
      </div>
    </div>
  );
}

function Sidebar({ stats }: { stats: RegistryStats }) {
  return (
    <aside className="portal-sidebar">
      <div className="sidebar-brand">
        <span className="brand-seal"><GoogleIcon name="account_balance" size={26} filled /></span>
        <div><strong>Định danh tổ chức</strong><span>BCA · BQP REGISTRY</span></div>
      </div>

      <div className="sidebar-section">
        <span className="sidebar-label">Chức năng đang sử dụng</span>
        <div className="active-module"><GoogleIcon name="manage_search" size={20} /><span>Tra cứu tổ chức</span><i>01</i></div>
      </div>

      <div className="sidebar-section registry-summary">
        <span className="sidebar-label">Hồ sơ dữ liệu</span>
        <dl>
          <div><dt>Tổng bản ghi</dt><dd>{formatNumber(stats.total)}</dd></div>
          <div><dt>Phạm vi địa phương</dt><dd>{stats.provinces}</dd></div>
          <div><dt>Cơ quan quản lý</dt><dd>02</dd></div>
        </dl>
      </div>

      <div className="sidebar-process">
        <span className="sidebar-label">Quy trình xác thực</span>
        <ol>
          <li><span>1</span><div><strong>Tiếp nhận</strong><small>Kiểm tra dữ liệu đầu vào</small></div></li>
          <li><span>2</span><div><strong>Định danh</strong><small>Đối chiếu thực thể tổ chức</small></div></li>
          <li><span>3</span><div><strong>Kết luận</strong><small>Tra cứu cơ quan quản lý</small></div></li>
        </ol>
      </div>

      <div className="sidebar-footer">
        <span className="runtime-dot" />
        <div><strong>Strict mode</strong><small>Fuzzy matching: OFF</small></div>
      </div>
    </aside>
  );
}

interface SearchPanelProps {
  organizationName: string;
  organizationId: string;
  province: string;
  organizationType: string;
  loading: boolean;
  hasResult: boolean;
  onOrganizationName: (value: string) => void;
  onOrganizationId: (value: string) => void;
  onProvince: (value: string) => void;
  onOrganizationType: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onExample: (value: string) => void;
  onReset: () => void;
}

function SearchPanel(props: SearchPanelProps) {
  const {
    organizationName, organizationId, province, organizationType, loading, hasResult,
    onOrganizationName, onOrganizationId, onProvince, onOrganizationType,
    onSubmit, onExample, onReset,
  } = props;

  return (
    <section className="desk-panel query-panel" aria-labelledby="query-title">
      <div className="panel-caption">
        <div><span className="panel-index">01</span><div><span className="section-code">QUERY PARAMETERS</span><h2 id="query-title">Điều kiện tra cứu</h2></div></div>
        <span className="required-note"><i>*</i> Bắt buộc</span>
      </div>

      <form onSubmit={onSubmit}>
        <div className="query-section">
          <div className="query-section-title"><span>A</span><strong>Thông tin định danh</strong></div>
          <div className="form-field form-field-primary">
            <label htmlFor="organization-name">Tên tổ chức <i>*</i></label>
            <div className="input-with-icon">
              <GoogleIcon name="search" size={21} />
              <input
                id="organization-name"
                value={organizationName}
                onChange={(event) => onOrganizationName(event.target.value)}
                placeholder="Nhập tên đầy đủ hoặc tên viết tắt"
                autoComplete="off"
              />
              {organizationName && (
                <button type="button" className="clear-field" onClick={() => onOrganizationName("")} aria-label="Xóa tên tổ chức"><GoogleIcon name="close" size={18} /></button>
              )}
            </div>
            <small>Có thể nhập tên có dấu, không dấu hoặc tên gọi đã đăng ký.</small>
          </div>
          <div className="form-field">
            <label htmlFor="organization-id">Mã tổ chức</label>
            <input id="organization-id" className="mono-input" value={organizationId} onChange={(event) => onOrganizationId(event.target.value)} placeholder="Ví dụ: BCA-PROVINCE-002153" />
          </div>
        </div>

        <div className="query-section context-section">
          <div className="query-section-title"><span>B</span><strong>Ngữ cảnh phân giải</strong></div>
          <div className="form-field">
            <label htmlFor="province">Tỉnh / Thành phố</label>
            <select id="province" value={province} onChange={(event) => onProvince(event.target.value)}>
              <option value="">Không giới hạn địa phương</option>
              {PROVINCES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="organization-type">Loại tổ chức</label>
            <select id="organization-type" value={organizationType} onChange={(event) => onOrganizationType(event.target.value)}>
              <option value="">Không giới hạn loại hình</option>
              {ORGANIZATION_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>

        <div className="query-policy"><GoogleIcon name="verified_user" size={20} /><p><strong>Chế độ xác định tuyệt đối.</strong> Nếu nhiều bản ghi cùng khớp, hệ thống yêu cầu thêm ngữ cảnh thay vì tự chọn một kết quả.</p></div>

        <div className="form-actions">
          <button className="primary-action" type="submit" disabled={loading}>
            {loading ? <span className="spinner" /> : <GoogleIcon name="search" size={20} />}
            {loading ? "Đang đối chiếu..." : "Thực hiện tra cứu"}
          </button>
          {(organizationName || organizationId || province || organizationType || hasResult) && <button className="secondary-action" type="button" onClick={onReset}>Xóa điều kiện</button>}
        </div>
      </form>

      <div className="sample-queries">
        <div className="sample-heading"><span>Truy vấn mẫu</span><small>Chọn để kiểm tra nhanh giao diện</small></div>
        <div className="sample-list">
          {EXAMPLES.map((example, index) => (
            <button type="button" key={example} onClick={() => onExample(example)}>
              <span>{String(index + 1).padStart(2, "0")}</span><strong>{example}</strong><GoogleIcon name="arrow_forward" size={17} />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function RegistryStatsBar({ stats }: { stats: RegistryStats }) {
  const items = [
    { code: "REG", value: formatNumber(stats.total), label: "Tổng tổ chức", icon: <GoogleIcon name="database" size={20} /> },
    { code: "BCA", value: formatNumber(stats.bca), label: "Bộ Công an", icon: <GoogleIcon name="local_police" size={20} /> },
    { code: "BQP", value: formatNumber(stats.bqp), label: "Bộ Quốc phòng", icon: <GoogleIcon name="shield" size={20} /> },
    { code: "LOC", value: String(stats.provinces), label: "Tỉnh, thành phố", icon: <GoogleIcon name="location_on" size={20} /> },
  ];

  return (
    <section className="registry-metrics" aria-label="Thống kê Master Registry">
      {items.map((item) => (
        <div className={`metric metric-${item.code.toLowerCase()}`} key={item.code}>
          <span className="metric-code">{item.code}</span>
          <span className="metric-icon">{item.icon}</span>
          <strong>{item.value}</strong>
          <small>{item.label}</small>
        </div>
      ))}
      <div className="metric-asof"><span>Dữ liệu hiện hành</span><strong>MASTER REGISTRY</strong></div>
    </section>
  );
}

interface ResultPanelProps {
  result: SearchResponse | null;
  loading: boolean;
  networkError: string;
  request: SearchRequest | null;
  onCandidate: (candidate: OrganizationCandidate) => void;
}

function ResultPanel({ result, loading, networkError, request, onCandidate }: ResultPanelProps) {
  if (loading) return <LoadingResult />;

  if (networkError) {
    return (
      <section className="desk-panel output-panel state-output error-output">
        <OutputCaption status="ERR" title="Kết quả định danh" />
        <div className="state-message"><span><GoogleIcon name="cloud_off" size={28} /></span><div><small>LỖI KẾT NỐI</small><h2>Chưa thể truy cập dịch vụ tra cứu</h2><p>{networkError}. Kiểm tra lại cấu hình API hoặc thử lại sau.</p></div></div>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="desk-panel output-panel initial-output">
        <OutputCaption status="---" title="Kết quả định danh" />
        <div className="initial-sheet">
          <span className="sheet-mark">BCA / BQP</span>
          <div className="sheet-copy"><span className="section-code">AWAITING QUERY</span><h2>Chưa có yêu cầu tra cứu</h2><p>Nhập tên hoặc mã tổ chức tại biểu mẫu bên trái. Phiếu kết quả sẽ thể hiện đầy đủ căn cứ định danh và cơ quan quản lý.</p></div>
          <ol className="comparison-rules">
            <li><span>01</span><div><strong>Đối chiếu định danh</strong><small>ID, tên chính thức, tên chuẩn hóa và alias</small></div></li>
            <li><span>02</span><div><strong>Kiểm tra ngữ cảnh</strong><small>Địa phương và loại hình tổ chức</small></div></li>
            <li><span>03</span><div><strong>Tra cứu quản lý</strong><small>Chỉ thực hiện sau khi đã xác định duy nhất</small></div></li>
          </ol>
        </div>
      </section>
    );
  }

  if (result.match_status === "AMBIGUOUS_MATCH") {
    return (
      <section className="desk-panel output-panel ambiguous-output">
        <OutputCaption status="REV" title="Kết quả cần rà soát" />
        <div className="output-alert warning-alert"><GoogleIcon name="warning" size={23} filled /><div><strong>Chưa thể kết luận cơ quan quản lý</strong><span>{result.candidates?.length || 0} bản ghi có cùng tên. Chọn đúng địa phương hoặc bổ sung bộ lọc.</span></div></div>
        <div className="candidate-table" role="list">
          <div className="candidate-table-head"><span>Tổ chức</span><span>Địa phương</span><span>Mã định danh</span><span /></div>
          {result.candidates?.map((candidate) => (
            <button role="listitem" type="button" key={candidate.organization_id} onClick={() => onCandidate(candidate)}>
              <span className="candidate-name"><GoogleIcon name="account_balance" size={18} /><strong>{candidate.organization_name}</strong></span>
              <span>{candidate.province_name || "—"}</span>
              <span className="mono-text">{candidate.organization_id}</span>
              <GoogleIcon name="arrow_forward" size={18} />
            </button>
          ))}
        </div>
      </section>
    );
  }

  if (result.match_status === "NOT_FOUND" || result.match_status === "INVALID_INPUT") {
    const invalid = result.match_status === "INVALID_INPUT";
    return (
      <section className="desk-panel output-panel state-output not-found-output">
        <OutputCaption status="N/A" title="Kết quả định danh" />
        <div className="state-message"><span><GoogleIcon name="search_off" size={29} /></span><div><small>{invalid ? "INVALID INPUT" : "NO DETERMINISTIC MATCH"}</small><h2>{invalid ? "Yêu cầu tra cứu chưa hợp lệ" : "Không tìm thấy bản ghi khớp tuyệt đối"}</h2><p>{invalid ? result.errors?.join(" ") : result.reason === "DETERMINISTIC_MATCH_CONTEXT_MISMATCH" ? "Tên tổ chức tồn tại nhưng mâu thuẫn với địa phương hoặc loại tổ chức đã chọn." : `Master Registry không có bản ghi chính xác cho “${request?.organization_name || request?.organization_id || "truy vấn này"}”.`}</p><strong className="unknown-label">KẾT LUẬN: UNKNOWN</strong></div></div>
      </section>
    );
  }

  const isBca = result.management === "BCA";
  const managementName = isBca ? "BỘ CÔNG AN" : "BỘ QUỐC PHÒNG";

  return (
    <section className={`desk-panel output-panel resolved-output ${isBca ? "result-bca" : "result-bqp"}`}>
      <OutputCaption status="OK" title="Phiếu kết quả định danh" />
      <div className="verified-banner"><span><GoogleIcon name="verified" size={18} filled /> ĐÃ XÁC THỰC</span><strong>{STATUS_LABELS[result.match_status]}</strong><small>Độ tin cậy {result.match_score || 100}%</small></div>

      <div className="identity-heading">
        <span className="identity-icon"><GoogleIcon name="account_balance" size={27} /></span>
        <div><span>TÊN TỔ CHỨC CHÍNH THỨC</span><h2>{result.organization_name}</h2><small className="mono-text">{result.organization_id}</small></div>
      </div>

      <div className="decision-layout">
        <dl className="record-details">
          <div><dt>Mã tổ chức</dt><dd className="mono-text">{result.organization_id}</dd></div>
          <div><dt>Địa phương</dt><dd><GoogleIcon name="location_on" size={17} /> {result.province_name || "Trung ương / Toàn quốc"}</dd></div>
          <div><dt>Loại tổ chức</dt><dd>{TYPE_LABELS[result.organization_type_code || ""] || result.organization_type_code}</dd></div>
          <div><dt>Mã phân loại</dt><dd className="mono-text">{result.organization_type_code}</dd></div>
          <div><dt>Phương thức khớp</dt><dd>{STATUS_LABELS[result.match_status]}</dd></div>
        </dl>

        <div className="management-decision">
          <span>KẾT LUẬN CƠ QUAN QUẢN LÝ</span>
          <strong>{result.management}</strong>
          <h3>{managementName}</h3>
          <i />
          <small>Tra cứu trực tiếp từ Master Registry sau khi hoàn tất định danh thực thể.</small>
        </div>
      </div>

      <div className="evidence-row">
        <div><span>Trạng thái hồ sơ</span><strong><GoogleIcon name="check_circle" size={16} filled /> Đã phân giải</strong></div>
        <div><span>Điểm đối chiếu</span><strong>{result.match_score || 100} / 100</strong></div>
        <div><span>Fuzzy matching</span><strong>Không sử dụng</strong></div>
      </div>
    </section>
  );
}

function OutputCaption({ status, title }: { status: string; title: string }) {
  return <div className="panel-caption output-caption"><div><span className="panel-index">02</span><div><span className="section-code">RESOLUTION OUTPUT</span><h2>{title}</h2></div></div><span className="output-code">{status}</span></div>;
}

function LoadingResult() {
  return (
    <section className="desk-panel output-panel loading-output">
      <OutputCaption status="RUN" title="Đang xử lý yêu cầu" />
      <div className="loading-ledger">
        <div className="loading-status"><span className="spinner dark-spinner" /><div><strong>Đang đối chiếu Master Registry</strong><small>Vui lòng giữ nguyên điều kiện tra cứu...</small></div></div>
        {[68, 91, 76, 84, 60].map((width, index) => <span className="ledger-line" style={{ width: `${width}%` }} key={index} />)}
      </div>
    </section>
  );
}

function PipelinePanel({ result, loading, request }: { result: SearchResponse | null; loading: boolean; request: SearchRequest | null }) {
  const query = request?.organization_name || request?.organization_id || "";
  const isResolved = Boolean(result?.management);
  const isAmbiguous = result?.match_status === "AMBIGUOUS_MATCH";
  const finished = Boolean(result);

  const steps = useMemo(() => [
    { code: "IN", title: "Tiếp nhận truy vấn", value: query || "Chưa có dữ liệu", state: request ? "done" : "idle" },
    { code: "NM", title: "Chuẩn hóa tên", value: request ? normalizePreview(query) || "Bỏ qua khi tra bằng ID" : "—", state: request ? "done" : "idle" },
    { code: "SK", title: "Sinh khóa tìm kiếm", value: request ? searchKeyPreview(query) || "Tra cứu khóa ID" : "—", state: request ? "done" : "idle" },
    { code: "ER", title: "Phân giải thực thể", value: loading ? "Đang đối chiếu" : isResolved ? STATUS_LABELS[result!.match_status] : isAmbiguous ? "Yêu cầu bổ sung ngữ cảnh" : finished ? "Không có khớp tuyệt đối" : "—", state: loading ? "active" : isResolved ? "done" : finished ? "failed" : "idle" },
    { code: "MG", title: "Tra cứu quản lý", value: isResolved ? `${result!.management} · ${result!.management === "BCA" ? "Bộ Công an" : "Bộ Quốc phòng"}` : finished ? "Không kết luận" : "—", state: isResolved ? "done" : finished ? "failed" : "idle" },
  ], [finished, isAmbiguous, isResolved, loading, query, request, result]);

  return (
    <section className="desk-panel audit-panel">
      <div className="audit-heading"><div><span className="section-code">PROCESS AUDIT</span><h2>Dấu vết xử lý</h2></div><span>05 GIAI ĐOẠN</span></div>
      <div className="audit-track">
        {steps.map((step, index) => (
          <div className={`audit-step is-${step.state}`} key={step.code}>
            <div className="audit-code">{step.state === "done" ? <GoogleIcon name="check" size={16} /> : step.code}</div>
            <div><strong>{step.title}</strong><span className="mono-text">{step.value}</span></div>
            {index < steps.length - 1 && <i />}
          </div>
        ))}
      </div>
    </section>
  );
}

export default App;
