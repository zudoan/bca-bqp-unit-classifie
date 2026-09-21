import { useMemo, useState } from "react";
import { GoogleIcon } from "./Icons";
import type { SearchRequest } from "../types/search";
import type { TransactionRecord, TransactionType } from "../types/portal";

interface HistoryPanelProps {
  records: TransactionRecord[];
  onReplay: (request: SearchRequest) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
}

const OUTCOME_LABELS = {
  SUCCESS: "Hoàn tất",
  REVIEW: "Cần rà soát",
  NOT_FOUND: "Không tìm thấy",
  ERROR: "Thất bại",
};

const STATUS_LABELS: Record<string, string> = {
  EXACT_ID_MATCH: "Khớp chính xác theo mã",
  EXACT_NAME_MATCH: "Khớp chính xác theo tên",
  NORMALIZED_MATCH: "Khớp sau chuẩn hóa",
  SEARCH_KEY_MATCH: "Khớp theo khóa tìm kiếm",
  ALIAS_MATCH: "Khớp theo tên thay thế",
  ACRONYM_MATCH: "Khớp theo tên viết tắt",
  FUZZY_MATCH: "Khớp gần đúng",
  FUZZY_CANDIDATES: "Có nhiều kết quả gần đúng",
  AMBIGUOUS_MATCH: "Kết quả chưa rõ ràng",
  NOT_FOUND: "Không tìm thấy tổ chức",
  INVALID_INPUT: "Dữ liệu tra cứu chưa hợp lệ",
  NETWORK_ERROR: "Lỗi kết nối máy chủ",
  BATCH_ERROR: "Xử lý file thất bại",
  BATCH_COMPLETED: "Xử lý file hoàn tất",
};

function formatStatus(status: string) {
  return STATUS_LABELS[status] || "Trạng thái chưa xác định";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function escapeCsv(value: unknown) {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

function exportHistory(records: TransactionRecord[]) {
  const header = ["Thời gian", "Loại", "Nội dung", "Trạng thái", "Mã tổ chức", "Đơn vị trả lương", "Quản lý"];
  const rows = records.map((record) => [
    formatDate(record.createdAt),
    record.type === "SEARCH" ? "Tra cứu" : "Xử lý file",
    record.title,
    formatStatus(record.status),
    record.organizationId,
    record.payingOrganization,
    record.management,
  ]);
  const csv = `\ufeff${[header, ...rows].map((row) => row.map(escapeCsv).join(",")).join("\r\n")}`;
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `lich-su-tra-cuu-${new Date().toISOString().slice(0, 10)}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function HistoryPanel({ records, onReplay, onRemove, onClear }: HistoryPanelProps) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState<"ALL" | TransactionType>("ALL");
  const [selected, setSelected] = useState<TransactionRecord | null>(null);

  const filtered = useMemo(() => {
    const key = query.trim().toLocaleLowerCase("vi");
    return records.filter((record) => {
      if (type !== "ALL" && record.type !== type) return false;
      if (!key) return true;
      return [record.title, record.status, formatStatus(record.status), record.organizationId, record.organizationName, record.filename]
        .some((value) => value?.toLocaleLowerCase("vi").includes(key));
    });
  }, [query, records, type]);

  const successCount = records.filter((record) => record.outcome === "SUCCESS").length;
  const reviewCount = records.filter((record) => record.outcome === "REVIEW").length;
  const batchCount = records.filter((record) => record.type === "BATCH").length;

  return (
    <section className="history-workspace">
      <div className="history-metrics">
        <article><div><small>TỔNG LƯỢT TRA CỨU</small><strong>{records.length}</strong></div></article>
        <article><div><small>HOÀN TẤT</small><strong>{successCount}</strong></div></article>
        <article><div><small>CẦN RÀ SOÁT</small><strong>{reviewCount}</strong></div></article>
        <article><div><small>XỬ LÝ FILE</small><strong>{batchCount}</strong></div></article>
      </div>

      <div className="desk-panel history-panel">
        <div className="history-toolbar">
          <div><span className="section-code">HOẠT ĐỘNG GẦN ĐÂY</span><h2>Nhật ký tra cứu tài khoản</h2><p>Lưu tối đa 100 lượt tra cứu và xử lý file gần nhất trên trình duyệt này.</p></div>
          <div className="history-toolbar-actions">
            <button type="button" onClick={() => exportHistory(filtered)} disabled={!filtered.length}><GoogleIcon name="download" size={18} /> Xuất CSV</button>
            <button className="danger-button" type="button" onClick={onClear} disabled={!records.length}><GoogleIcon name="delete_sweep" size={18} /> Xóa lịch sử</button>
          </div>
        </div>

        <div className="history-filters">
          <label><GoogleIcon name="search" size={19} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm tên tổ chức, mã định danh hoặc tên file..." /></label>
          <div role="group" aria-label="Lọc loại lịch sử">
            {(["ALL", "SEARCH", "BATCH"] as const).map((value) => <button type="button" key={value} className={type === value ? "is-active" : ""} onClick={() => setType(value)}>{value === "ALL" ? "Tất cả" : value === "SEARCH" ? "Tra cứu" : "Xử lý file"}</button>)}
          </div>
          <span>{filtered.length} kết quả</span>
        </div>

        {filtered.length ? (
          <div className="history-table-wrap">
            <table className="history-table">
              <thead><tr><th>Thời gian</th><th>Hoạt động tra cứu</th><th>Kết quả</th><th>Thông tin đối chiếu</th><th aria-label="Thao tác" /></tr></thead>
              <tbody>
                {filtered.map((record) => (
                  <tr key={record.id}>
                    <td><span className="history-time">{formatDate(record.createdAt)}</span><small className="mono-text">{record.id.slice(0, 8).toUpperCase()}</small></td>
                    <td><span className={`transaction-icon is-${record.type.toLowerCase()}`}><GoogleIcon name={record.type === "SEARCH" ? "manage_search" : "upload_file"} size={19} /></span><div><strong>{record.title}</strong><small>{record.type === "SEARCH" ? "Tra cứu đơn vị" : record.filename || "Đối chiếu hàng loạt"}</small></div></td>
                    <td><span className={`outcome-badge is-${record.outcome.toLowerCase()}`}>{OUTCOME_LABELS[record.outcome]}</span><small>{formatStatus(record.status)}</small></td>
                    <td><strong>{record.organizationName || record.batchSummary ? record.organizationName || `${record.batchSummary?.inputCount || 0} dòng đầu vào` : "—"}</strong><small>{record.organizationId || record.detail || "Không có dữ liệu bổ sung"}</small></td>
                    <td><div className="history-row-actions"><button type="button" onClick={() => setSelected(record)} title="Xem chi tiết"><GoogleIcon name="visibility" size={18} /></button>{record.request && <button type="button" onClick={() => onReplay(record.request!)} title="Tra cứu lại"><GoogleIcon name="replay" size={18} /></button>}<button type="button" onClick={() => onRemove(record.id)} title="Xóa"><GoogleIcon name="delete" size={18} /></button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-history"><span><GoogleIcon name="history" size={32} /></span><h3>{records.length ? "Không có lịch sử phù hợp" : "Chưa có lịch sử tra cứu"}</h3><p>{records.length ? "Thử thay đổi từ khóa hoặc bộ lọc loại hoạt động." : "Các lần tra cứu và xử lý file sẽ xuất hiện tại đây."}</p></div>
        )}
      </div>

      {selected && (
        <div className="history-modal-backdrop" role="presentation" onMouseDown={() => setSelected(null)}>
          <section className="history-detail" role="dialog" aria-modal="true" aria-labelledby="history-detail-title" onMouseDown={(event) => event.stopPropagation()}>
            <header><div><span className="section-code">CHI TIẾT BẢN GHI</span><h2 id="history-detail-title">Chi tiết lịch sử tra cứu</h2></div><button type="button" onClick={() => setSelected(null)} aria-label="Đóng"><GoogleIcon name="close" size={20} /></button></header>
            <div className="detail-status"><span className={`transaction-icon is-${selected.type.toLowerCase()}`}><GoogleIcon name={selected.type === "SEARCH" ? "manage_search" : "upload_file"} size={22} /></span><div><strong>{selected.title}</strong><small>{formatDate(selected.createdAt)} · {OUTCOME_LABELS[selected.outcome]}</small></div></div>
            <dl>
              <div><dt>Mã bản ghi</dt><dd className="mono-text">{selected.id}</dd></div>
              <div><dt>Trạng thái hệ thống</dt><dd>{formatStatus(selected.status)}</dd></div>
              {selected.organizationId && <div><dt>Mã tổ chức</dt><dd className="mono-text">{selected.organizationId}</dd></div>}
              {selected.payingOrganization !== undefined && <div><dt>Đơn vị trả lương</dt><dd>{selected.payingOrganization || "Chưa xác định"}</dd></div>}
              {selected.payrollStatus && <div><dt>Trạng thái trả lương</dt><dd>{selected.payrollStatus}</dd></div>}
              {selected.management && <div><dt>Phạm vi quản lý</dt><dd>{selected.management}</dd></div>}
              {selected.batchSummary && <div><dt>Kết quả file</dt><dd>{selected.batchSummary.paidCount} được trả lương · {selected.batchSummary.notPaidCount} không được trả lương · {selected.batchSummary.unresolvedCount} chưa kết luận</dd></div>}
              {selected.detail && <div><dt>Ghi chú</dt><dd>{selected.detail}</dd></div>}
            </dl>
            <footer>{selected.request && <button type="button" onClick={() => { onReplay(selected.request!); setSelected(null); }}><GoogleIcon name="replay" size={18} /> Tra cứu lại</button>}<button type="button" onClick={() => setSelected(null)}>Đóng</button></footer>
          </section>
        </div>
      )}
    </section>
  );
}
