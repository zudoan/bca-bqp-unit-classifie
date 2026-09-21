import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import { GoogleIcon } from "./components/Icons";
import { AdminUsersPanel } from "./components/AdminUsersPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { LoginScreen } from "./components/LoginScreen";
import { logoutAccount, restoreSession } from "./services/authApi";
import { apiMode, getRegistryStats, processBatchFile, searchOrganization } from "./services/searchApi";
import {
  createTransactionId,
  loadTransactions,
  saveTransactions,
} from "./services/portalStore";
import type {
  BatchProcessSummary,
  OrganizationCandidate,
  RegistryStats,
  SearchRequest,
  SearchResponse,
} from "./types/search";
import type {
  PortalSession,
  PortalView,
  TransactionOutcome,
  TransactionRecord,
} from "./types/portal";

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
  ACRONYM_MATCH: "Khớp tên viết tắt từ bộ từ điển",
  FUZZY_MATCH: "Khớp gần đúng có độ tin cậy cao",
  FUZZY_CANDIDATES: "Các ứng viên gần đúng cần xác nhận",
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

function outcomeFromResponse(response: SearchResponse): TransactionOutcome {
  if (response.organization_id) return "SUCCESS";
  if (response.match_status === "AMBIGUOUS_MATCH" || response.match_status === "FUZZY_CANDIDATES") return "REVIEW";
  return "NOT_FOUND";
}

function App() {
  const [session, setSession] = useState<PortalSession | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [activeView, setActiveView] = useState<PortalView>("search");
  const [transactions, setTransactions] = useState<TransactionRecord[]>(() => loadTransactions());
  const [accountOpen, setAccountOpen] = useState(false);
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

  function updateTransactions(updater: (current: TransactionRecord[]) => TransactionRecord[]) {
    setTransactions((current) => {
      const updated = updater(current).slice(0, 100);
      saveTransactions(updated);
      return updated;
    });
  }

  function addTransaction(record: Omit<TransactionRecord, "id" | "userId" | "createdAt">) {
    if (!session) return;
    updateTransactions((current) => [{
      ...record,
      id: createTransactionId(),
      userId: session.userId,
      createdAt: new Date().toISOString(),
    }, ...current]);
  }

  useEffect(() => {
    let active = true;
    restoreSession()
      .then((restoredSession) => {
        if (active) setSession(restoredSession);
      })
      .catch(() => {
        if (active) setSession(null);
      })
      .finally(() => {
        if (active) setAuthReady(true);
      });
    getRegistryStats().then(setStats).catch(() => setStats(DEFAULT_STATS));
    return () => {
      active = false;
      abortRef.current?.abort();
    };
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
      addTransaction({
        type: "SEARCH",
        outcome: outcomeFromResponse(response),
        title: request.organization_name || request.organization_id || "Yêu cầu không có định danh",
        status: response.match_status,
        request,
        organizationId: response.organization_id,
        organizationName: response.organization_name,
        payingOrganization: response.paying_organization,
        payrollStatus: response.payroll_status,
        management: response.management,
        detail: response.reason || response.errors?.join(" "),
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const message = error instanceof Error ? error.message : "Không thể kết nối tới dịch vụ tra cứu.";
      setNetworkError(message);
      addTransaction({
        type: "SEARCH",
        outcome: "ERROR",
        title: request.organization_name || request.organization_id || "Yêu cầu không có định danh",
        status: "NETWORK_ERROR",
        request,
        detail: message,
      });
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

  function login(nextSession: PortalSession) {
    setSession(nextSession);
    setActiveView("search");
  }

  async function logout() {
    abortRef.current?.abort();
    try {
      await logoutAccount();
    } catch {
      // Clear the local view even when the backend is temporarily unavailable.
    }
    setAccountOpen(false);
    setSession(null);
    setActiveView("search");
    resetSearch();
  }

  function openHistoryReplay(request: SearchRequest) {
    setOrganizationName(request.organization_name || "");
    setOrganizationId(request.organization_id || "");
    setProvince(request.province_name || "");
    setOrganizationType(request.organization_type || "");
    setActiveView("search");
    void runSearch(request);
  }

  function recordBatch(transaction: BatchTransactionEvent) {
    addTransaction({
      type: "BATCH",
      outcome: transaction.error ? "ERROR" : "SUCCESS",
      title: transaction.filename,
      status: transaction.error ? "BATCH_ERROR" : "BATCH_COMPLETED",
      filename: transaction.filename,
      batchSummary: transaction.summary,
      detail: transaction.error || (transaction.summary ? `${transaction.summary.inputCount} dòng đã được xử lý` : undefined),
    });
  }

  function removeTransaction(id: string) {
    updateTransactions((current) => current.filter((record) => record.id !== id));
  }

  function clearUserTransactions() {
    if (!session || !window.confirm("Xóa toàn bộ lịch sử tra cứu của tài khoản này?")) return;
    updateTransactions((current) => current.filter((record) => record.userId !== session.userId));
  }

  if (!authReady) {
    return <main className="auth-loading-screen"><span className="spinner dark-spinner" /><strong>Đang kiểm tra phiên đăng nhập...</strong></main>;
  }
  if (!session) return <LoginScreen onLogin={login} />;

  const userTransactions = transactions.filter((record) => record.userId === session.userId);
  const viewTitle = activeView === "search"
    ? "Tra cứu tổ chức"
    : activeView === "history"
      ? "Lịch sử tra cứu"
      : "Quản lý người dùng";
  const viewCode = activeView === "search" ? "TRA CỨU TỔ CHỨC" : activeView === "history" ? "NHẬT KÝ TRA CỨU" : "QUẢN TRỊ TÀI KHOẢN";

  return (
    <div className="portal-shell">
      <Sidebar stats={stats} activeView={activeView} historyCount={userTransactions.length} isAdmin={session.role === "admin"} onNavigate={setActiveView} />

      <div className="portal-main">
        <header className="command-bar">
          <div className="mobile-brand">
            <span className="brand-seal"><GoogleIcon name="account_balance" size={22} filled /></span>
            <strong>Tra cứu BCA / BQP</strong>
          </div>
          <div className="breadcrumb" aria-label="Vị trí hiện tại">
            <span>Hệ thống định danh</span><i>/</i><strong>{viewTitle}</strong>
          </div>
          <div className="command-actions">
            <div className="runtime-status" title={apiMode === "mock" ? "Đang sử dụng dữ liệu mô phỏng" : "Đã kết nối máy chủ"}>
              <span className="runtime-dot" />
              {apiMode === "mock" ? "Môi trường trình diễn" : "Kết nối trực tuyến"}
            </div>
            <div className="account-menu">
              <button className="account-trigger" type="button" onClick={() => setAccountOpen((value) => !value)} aria-expanded={accountOpen}>
                <span className="account-avatar">{session.displayName.charAt(0).toLocaleUpperCase("vi")}</span>
                <div><strong>{session.displayName}</strong><small>{session.role === "admin" ? "Quản trị viên" : "Người dùng tra cứu"}</small></div>
                <GoogleIcon name="expand_more" size={18} />
              </button>
              {accountOpen && (
                <div className="account-dropdown">
                  <div><span className="account-avatar">{session.displayName.charAt(0).toLocaleUpperCase("vi")}</span><p><strong>{session.displayName}</strong><small>{session.email || `@${session.username}`}</small></p></div>
                  <button type="button" onClick={() => { setActiveView("history"); setAccountOpen(false); }}><GoogleIcon name="history" size={19} /> Lịch sử tra cứu</button>
                  {session.role === "admin" && <button type="button" onClick={() => { setActiveView("users"); setAccountOpen(false); }}><GoogleIcon name="manage_accounts" size={19} /> Quản lý người dùng</button>}
                  <button type="button" onClick={() => void logout()}><GoogleIcon name="logout" size={19} /> Đăng xuất</button>
                </div>
              )}
            </div>
          </div>
        </header>

        <nav className="mobile-view-tabs" aria-label="Chức năng">
          <button type="button" className={activeView === "search" ? "is-active" : ""} onClick={() => setActiveView("search")}><GoogleIcon name="manage_search" size={19} />Tra cứu</button>
          <button type="button" className={activeView === "history" ? "is-active" : ""} onClick={() => setActiveView("history")}><GoogleIcon name="history" size={19} />Lịch sử <span>{userTransactions.length}</span></button>
          {session.role === "admin" && <button type="button" className={activeView === "users" ? "is-active" : ""} onClick={() => setActiveView("users")}><GoogleIcon name="manage_accounts" size={19} />Người dùng</button>}
        </nav>

        <main className="workspace-main">
          <section className="page-heading">
            <div>
              <span className="section-code">{viewCode}</span>
              <h1>{activeView === "search" ? "Tra cứu và định danh tổ chức" : viewTitle}</h1>
              {activeView === "history" && <p>Kiểm tra các lần tra cứu và xử lý file của tài khoản {session.displayName}.</p>}
              {activeView === "users" && <p>Kiểm soát tài khoản, phân quyền và trạng thái truy cập hệ thống.</p>}
            </div>
          </section>

          {activeView === "search" ? (
            <>
              <BatchUploadPanel onTransaction={recordBatch} />

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
            </>
          ) : activeView === "history" ? (
            <HistoryPanel
              records={userTransactions}
              onReplay={openHistoryReplay}
              onRemove={removeTransaction}
              onClear={clearUserTransactions}
            />
          ) : (
            <AdminUsersPanel currentUserId={session.userId} />
          )}
        </main>

        <footer className="portal-footer">
          <span>Hệ thống tra cứu tổ chức BCA / BQP</span>
          <span>Nguồn dữ liệu: Danh mục tổ chức BCA/BQP · Ưu tiên khớp chính xác</span>
        </footer>
      </div>
    </div>
  );
}

interface BatchTransactionEvent {
  filename: string;
  summary?: BatchProcessSummary;
  error?: string;
}

function BatchUploadPanel({ onTransaction }: { onTransaction: (transaction: BatchTransactionEvent) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [columnName, setColumnName] = useState("");
  const [processing, setProcessing] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<BatchProcessSummary | null>(null);
  const [download, setDownload] = useState<{ url: string; filename: string } | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      if (download) URL.revokeObjectURL(download.url);
    };
  }, [download]);

  function selectFile(selected: File | null) {
    setError("");
    setSummary(null);
    if (download) {
      URL.revokeObjectURL(download.url);
      setDownload(null);
    }
    if (!selected) {
      setFile(null);
      return;
    }
    const extension = selected.name.split(".").pop()?.toLowerCase();
    if (!extension || !["xlsx", "xls", "docx", "pdf"].includes(extension)) {
      setFile(null);
      setError("Chỉ hỗ trợ file .xlsx, .xls, .docx hoặc .pdf.");
      return;
    }
    if (selected.size > 10 * 1024 * 1024) {
      setFile(null);
      setError("File vượt giới hạn 10 MB.");
      return;
    }
    setFile(selected);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0] || null);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    selectFile(event.dataTransfer.files?.[0] || null);
  }

  function triggerDownload(url: string, filename: string) {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  async function submitBatch(event: FormEvent) {
    event.preventDefault();
    if (!file || processing) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setProcessing(true);
    setError("");
    setSummary(null);
    try {
      const result = await processBatchFile(file, columnName, controller.signal);
      if (download) URL.revokeObjectURL(download.url);
      const url = URL.createObjectURL(result.blob);
      setDownload({ url, filename: result.filename });
      setSummary(result.summary);
      triggerDownload(url, result.filename);
      onTransaction({ filename: file.name, summary: result.summary });
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      const message = caught instanceof Error ? caught.message : "Không thể xử lý file.";
      setError(message);
      onTransaction({ filename: file.name, error: message });
    } finally {
      if (!controller.signal.aborted) setProcessing(false);
    }
  }

  return (
    <section className="desk-panel batch-panel" aria-labelledby="batch-title">
      <div className="batch-heading">
        <div className="batch-title-block">
          <span className="batch-icon"><GoogleIcon name="upload_file" size={25} /></span>
          <div><span className="section-code">ĐỐI CHIẾU HÀNG LOẠT</span><h2 id="batch-title">Đối chiếu danh sách từ Word / Excel / PDF</h2><p>Kết quả là tệp ZIP gồm hai danh sách.</p></div>
        </div>
        <span className="batch-limit">TỐI ĐA 10 MB · 5.000 DÒNG</span>
      </div>

      <form className="batch-form" onSubmit={submitBatch}>
        <label
          className={`file-dropzone ${dragActive ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
          onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
        >
          <input type="file" accept=".xlsx,.xls,.docx,.pdf,application/pdf" onChange={onFileChange} />
          <GoogleIcon name={file ? "description" : "cloud_upload"} size={29} />
          <span><strong>{file ? file.name : "Chọn hoặc kéo thả file vào đây"}</strong><small>{file ? `${(file.size / 1024).toLocaleString("vi-VN", { maximumFractionDigits: 0 })} KB` : "Excel .xlsx/.xls, Word .docx hoặc PDF .pdf"}</small></span>
        </label>

        <div className="batch-column-field">
          <label htmlFor="batch-column">Tên cột chứa đơn vị <span>(tùy chọn)</span></label>
          <input id="batch-column" value={columnName} onChange={(event) => setColumnName(event.target.value)} placeholder="Tự nhận diện: Tên đơn vị, Tên tổ chức..." />
          <small>Để trống nếu file chỉ có một cột hoặc dùng tiêu đề phổ biến.</small>
        </div>

        <button className="batch-submit" type="submit" disabled={!file || processing}>
          {processing ? <span className="spinner" /> : <GoogleIcon name="rule" size={20} />}
          {processing ? "Đang đối chiếu..." : "Phân loại và xuất kết quả"}
        </button>
      </form>

      {(error || summary) && (
        <div className={`batch-feedback ${error ? "is-error" : "is-success"}`} aria-live="polite">
          {error ? (
            <><GoogleIcon name="error" size={20} filled /><span>{error}</span></>
          ) : summary ? (
            <>
              <GoogleIcon name="task_alt" size={21} filled />
              <div><strong>Đã xử lý {formatNumber(summary.inputCount)} dòng</strong><span>{formatNumber(summary.paidCount)} được trả lương · {formatNumber(summary.notPaidCount)} không được trả lương · {formatNumber(summary.unresolvedCount)} chưa thể kết luận · Phương thức đọc: {summary.inputMode === "gemini-ocr" ? "Nhận dạng văn bản trong tài liệu" : summary.inputMode === "pdf-text" ? "Văn bản có sẵn trong PDF" : "Dữ liệu bảng"}</span></div>
              {download && <button type="button" onClick={() => triggerDownload(download.url, download.filename)}><GoogleIcon name="download" size={18} /> Tải lại ZIP</button>}
            </>
          ) : null}
        </div>
      )}
    </section>
  );
}

interface SidebarProps {
  stats: RegistryStats;
  activeView: PortalView;
  historyCount: number;
  isAdmin: boolean;
  onNavigate: (view: PortalView) => void;
}

function Sidebar({ stats, activeView, historyCount, isAdmin, onNavigate }: SidebarProps) {
  return (
    <aside className="portal-sidebar">
      <div className="sidebar-brand">
        <span className="brand-seal"><GoogleIcon name="account_balance" size={26} filled /></span>
        <div><strong>Định danh tổ chức</strong><span>HỆ THỐNG BCA · BQP</span></div>
      </div>

      <div className="sidebar-section">
        <span className="sidebar-label">Chức năng hệ thống</span>
        <nav className="sidebar-navigation">
          <button type="button" className={activeView === "search" ? "active-module" : ""} onClick={() => onNavigate("search")}><GoogleIcon name="manage_search" size={20} /><span>Tra cứu tổ chức</span><i>01</i></button>
          <button type="button" className={activeView === "history" ? "active-module" : ""} onClick={() => onNavigate("history")}><GoogleIcon name="history" size={20} /><span>Lịch sử tra cứu</span><i>{historyCount}</i></button>
          {isAdmin && <button type="button" className={activeView === "users" ? "active-module" : ""} onClick={() => onNavigate("users")}><GoogleIcon name="manage_accounts" size={20} /><span>Quản lý người dùng</span><i>QT</i></button>}
        </nav>
      </div>

      <div className="sidebar-section registry-summary">
        <span className="sidebar-label">Dữ liệu hệ thống</span>
        <dl>
          <div><dt>Tổng tổ chức</dt><dd>{formatNumber(stats.total)}</dd></div>
          <div><dt>Phạm vi BCA</dt><dd>{formatNumber(stats.bca)}</dd></div>
          <div><dt>Phạm vi BQP</dt><dd>{formatNumber(stats.bqp)}</dd></div>
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
        <div><strong>Đối chiếu an toàn</strong><small>Ưu tiên chính xác · Gần đúng khi đủ tin cậy</small></div>
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
        <div><span className="panel-index">01</span><div><span className="section-code">THÔNG TIN ĐỐI CHIẾU</span><h2 id="query-title">Điều kiện tra cứu</h2></div></div>
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
          <div className="query-section-title"><span>B</span><strong>Thông tin bổ sung</strong></div>
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

        <div className="form-actions">
          <button className="primary-action" type="submit" disabled={loading}>
            {loading ? <span className="spinner" /> : <GoogleIcon name="search" size={20} />}
            {loading ? "Đang đối chiếu..." : "Thực hiện tra cứu"}
          </button>
          {(organizationName || organizationId || province || organizationType || hasResult) && <button className="secondary-action" type="button" onClick={onReset}>Xóa điều kiện</button>}
        </div>
      </form>

      <div className="sample-queries">
        <div className="sample-heading"><span>Truy vấn mẫu</span><small>Chọn một mục để tra cứu nhanh</small></div>
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
        <OutputCaption status="LỖI" title="Kết quả định danh" />
        <div className="state-message"><span><GoogleIcon name="cloud_off" size={28} /></span><div><small>LỖI KẾT NỐI</small><h2>Chưa thể truy cập dịch vụ tra cứu</h2><p>{networkError}. Kiểm tra lại kết nối máy chủ hoặc thử lại sau.</p></div></div>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="desk-panel output-panel initial-output">
        <OutputCaption status="CHỜ" title="Kết quả định danh" />
        <div className="initial-sheet">
          <span className="sheet-mark">BCA / BQP</span>
          <div className="sheet-copy"><span className="section-code">CHỜ THÔNG TIN TRA CỨU</span><h2>Chưa có yêu cầu tra cứu</h2><p>Nhập tên hoặc mã tổ chức tại biểu mẫu bên trái. Phiếu kết quả ưu tiên kết luận đơn vị trả lương, sau đó hiển thị cơ quan quản lý.</p></div>
          <ol className="comparison-rules">
            <li><span>01</span><div><strong>Đối chiếu định danh</strong><small>Mã, tên chính thức, tên chuẩn hóa và tên gọi khác</small></div></li>
            <li><span>02</span><div><strong>Kiểm tra ngữ cảnh</strong><small>Địa phương và loại hình tổ chức</small></div></li>
            <li><span>03</span><div><strong>Tra cứu kết luận</strong><small>Đơn vị trả lương trước, phạm vi quản lý sau</small></div></li>
          </ol>
        </div>
      </section>
    );
  }

  if (result.match_status === "AMBIGUOUS_MATCH" || result.match_status === "FUZZY_CANDIDATES") {
    const isFuzzyReview = result.match_status === "FUZZY_CANDIDATES";
    return (
      <section className="desk-panel output-panel ambiguous-output">
        <OutputCaption status="RÀ SOÁT" title="Kết quả cần rà soát" />
        <div className="output-alert warning-alert"><GoogleIcon name="warning" size={23} filled /><div><strong>Chưa thể kết luận đơn vị trả lương và cơ quan quản lý</strong><span>{isFuzzyReview ? `${result.candidates?.length || 0} ứng viên gần đúng được tìm thấy. Hãy chọn đúng tổ chức.` : `${result.candidates?.length || 0} bản ghi có cùng tên. Chọn đúng địa phương hoặc bổ sung bộ lọc.`}</span></div></div>
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
        <OutputCaption status="KHÔNG CÓ" title="Kết quả định danh" />
        <div className="state-message"><span><GoogleIcon name="search_off" size={29} /></span><div><small>{invalid ? "DỮ LIỆU CHƯA HỢP LỆ" : "CHƯA CÓ KẾT QUẢ TIN CẬY"}</small><h2>{invalid ? "Yêu cầu tra cứu chưa hợp lệ" : "Không tìm thấy bản ghi đủ tin cậy"}</h2><p>{invalid ? result.errors?.join(" ") : result.reason === "DETERMINISTIC_MATCH_CONTEXT_MISMATCH" ? "Tên tổ chức tồn tại nhưng mâu thuẫn với địa phương hoặc loại tổ chức đã chọn." : `Danh mục tổ chức chưa có kết quả đủ tin cậy cho “${request?.organization_name || request?.organization_id || "truy vấn này"}”.`}</p><strong className="unknown-label">KẾT LUẬN: CHƯA XÁC ĐỊNH</strong></div></div>
      </section>
    );
  }

  const isBca = result.management === "BCA";
  const managementName = isBca ? "BỘ CÔNG AN" : "BỘ QUỐC PHÒNG";
  const payingOrganization = result.paying_organization || "CHƯA XÁC ĐỊNH CỤ THỂ";
  const usedFuzzy = result.match_status === "FUZZY_MATCH";

  return (
    <section className={`desk-panel output-panel resolved-output ${isBca ? "result-bca" : "result-bqp"}`}>
      <OutputCaption status="HOÀN TẤT" title="Phiếu kết quả định danh" />
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

        <div className="decision-stack">
          <div className="payroll-decision">
            <span>KẾT LUẬN</span>
            <strong>{payingOrganization}</strong>
            <h3>{result.payroll_status || "Chưa có trạng thái trả lương"}</h3>
            <i />
          </div>
          <div className="management-secondary">
            <span>PHẠM VI QUẢN LÝ</span>
            <strong>{result.management} · {managementName}</strong>
          </div>
        </div>
      </div>
    </section>
  );
}

function OutputCaption({ status, title }: { status: string; title: string }) {
  return <div className="panel-caption output-caption"><div><span className="panel-index">02</span><div><span className="section-code">KẾT QUẢ ĐỐI CHIẾU</span><h2>{title}</h2></div></div><span className="output-code">{status}</span></div>;
}

function LoadingResult() {
  return (
    <section className="desk-panel output-panel loading-output">
      <OutputCaption status="ĐANG XỬ LÝ" title="Đang xử lý yêu cầu" />
      <div className="loading-ledger">
        <div className="loading-status"><span className="spinner dark-spinner" /><div><strong>Đang đối chiếu danh mục tổ chức</strong><small>Vui lòng giữ nguyên điều kiện tra cứu...</small></div></div>
        {[68, 91, 76, 84, 60].map((width, index) => <span className="ledger-line" style={{ width: `${width}%` }} key={index} />)}
      </div>
    </section>
  );
}

function PipelinePanel({ result, loading, request }: { result: SearchResponse | null; loading: boolean; request: SearchRequest | null }) {
  const query = request?.organization_name || request?.organization_id || "";
  const isResolved = Boolean(result?.management);
  const isAmbiguous = result?.match_status === "AMBIGUOUS_MATCH" || result?.match_status === "FUZZY_CANDIDATES";
  const finished = Boolean(result);

  const steps = useMemo(() => [
    { code: "01", title: "Tiếp nhận truy vấn", value: query || "Chưa có dữ liệu", state: request ? "done" : "idle" },
    { code: "02", title: "Chuẩn hóa tên", value: request ? normalizePreview(query) || "Bỏ qua khi tra bằng mã" : "—", state: request ? "done" : "idle" },
    { code: "03", title: "Tạo khóa tìm kiếm", value: request ? searchKeyPreview(query) || "Tra cứu theo mã" : "—", state: request ? "done" : "idle" },
    { code: "04", title: "Đối chiếu tổ chức", value: loading ? "Đang đối chiếu" : isResolved ? STATUS_LABELS[result!.match_status] : isAmbiguous ? "Cần xác nhận kết quả" : finished ? "Chưa có kết quả đủ tin cậy" : "—", state: loading ? "active" : isResolved ? "done" : finished ? "failed" : "idle" },
    { code: "05", title: "Tra cứu trả lương", value: isResolved ? `${result!.paying_organization || "Chưa xác định cụ thể"} · ${result!.payroll_status || "Chưa có trạng thái"}` : finished ? "Không kết luận" : "—", state: isResolved ? "done" : finished ? "failed" : "idle" },
    { code: "06", title: "Tra cứu quản lý", value: isResolved ? `${result!.management} · ${result!.management === "BCA" ? "Bộ Công an" : "Bộ Quốc phòng"}` : finished ? "Không kết luận" : "—", state: isResolved ? "done" : finished ? "failed" : "idle" },
  ], [finished, isAmbiguous, isResolved, loading, query, request, result]);

  return (
    <section className="desk-panel audit-panel">
      <div className="audit-heading"><div><span className="section-code">QUY TRÌNH ĐỐI CHIẾU</span><h2>Các bước xử lý</h2></div><span>06 BƯỚC</span></div>
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
