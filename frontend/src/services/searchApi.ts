import type { RegistryStats, SearchRequest, SearchResponse } from "../types/search";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API === "true";

const stats: RegistryStats = {
  total: 14_303,
  bca: 9_689,
  bqp: 4_614,
  provinces: 63,
};

const mockOrganizations: SearchResponse[] = [
  {
    match_status: "EXACT_NAME_MATCH",
    match_score: 100,
    organization_id: "BCA-PROVINCE-002153",
    organization_name: "Công an tỉnh Thái Bình",
    province_name: "Thái Bình",
    organization_type_code: "POLICE_PROVINCE",
    paying_organization: "BCA",
    payroll_status: "Do BCA trả lương",
    management: "BCA",
  },
  {
    match_status: "EXACT_NAME_MATCH",
    match_score: 100,
    organization_id: "BQP-PROVINCE-001256",
    organization_name: "Bộ Chỉ huy Quân sự tỉnh Quảng Ninh",
    province_name: "Quảng Ninh",
    organization_type_code: "MILITARY_PROVINCE",
    paying_organization: "BQP",
    payroll_status: "Do BQP trả lương",
    management: "BQP",
  },
  {
    match_status: "EXACT_NAME_MATCH",
    match_score: 100,
    organization_id: "BCA-CENTRAL-000012",
    organization_name: "Học viện Cảnh sát nhân dân",
    province_name: "Hà Nội",
    organization_type_code: "MINISTRY_DEPARTMENT",
    paying_organization: "BCA",
    payroll_status: "Do BCA trả lương",
    management: "BCA",
  },
  {
    match_status: "EXACT_NAME_MATCH",
    match_score: 100,
    organization_id: "BQP-ACADEMY-014154",
    organization_name: "Học viện Kỹ thuật Quân sự",
    province_name: "Hà Nội",
    organization_type_code: "ACADEMY",
    paying_organization: "BQP",
    payroll_status: "Do BQP trả lương",
    management: "BQP",
  },
  {
    match_status: "ALIAS_MATCH",
    match_score: 100,
    organization_id: "BQP-DISTRICT-000196",
    organization_name: "Ban Chỉ huy Quân sự huyện Sóc Sơn",
    province_name: "Hà Nội",
    organization_type_code: "MILITARY_DISTRICT",
    paying_organization: "UBND Địa phương",
    payroll_status: "Không do BCA/BQP trả lương",
    management: "BQP",
  },
];

function searchKey(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLocaleLowerCase("vi")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function applyContext(result: SearchResponse, request: SearchRequest): SearchResponse {
  if (
    request.province_name &&
    result.province_name &&
    searchKey(request.province_name) !== searchKey(result.province_name)
  ) {
    return {
      match_status: "NOT_FOUND",
      candidates: [],
      reason: "DETERMINISTIC_MATCH_CONTEXT_MISMATCH",
    };
  }
  if (
    request.organization_type &&
    result.organization_type_code !== request.organization_type
  ) {
    return {
      match_status: "NOT_FOUND",
      candidates: [],
      reason: "DETERMINISTIC_MATCH_CONTEXT_MISMATCH",
    };
  }
  return result;
}

function delay(milliseconds: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal?.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Yêu cầu đã bị hủy", "AbortError"));
      },
      { once: true },
    );
  });
}

async function mockSearch(request: SearchRequest, signal?: AbortSignal): Promise<SearchResponse> {
  await delay(520, signal);

  const id = request.organization_id?.trim();
  const name = request.organization_name?.trim();

  if (!id && !name) {
    return {
      match_status: "INVALID_INPUT",
      errors: ["Vui lòng nhập tên hoặc mã tổ chức."],
    };
  }

  if (name && searchKey(name) === "cong an huyen chau thanh") {
    return {
      match_status: "AMBIGUOUS_MATCH",
      reason: "MULTIPLE_DETERMINISTIC_MATCHES",
      candidates: [
        {
          organization_id: "BCA-DISTRICT-010929",
          organization_name: "Công an huyện Châu Thành",
          province_name: "Tây Ninh",
          organization_type_code: "POLICE_DISTRICT",
          organization_level: "DISTRICT",
          score: 100,
          matched_on: "EXACT_NAME_MATCH",
        },
        {
          organization_id: "BCA-DISTRICT-011379",
          organization_name: "Công an huyện Châu Thành",
          province_name: "Long An",
          organization_type_code: "POLICE_DISTRICT",
          organization_level: "DISTRICT",
          score: 100,
          matched_on: "EXACT_NAME_MATCH",
        },
        {
          organization_id: "BCA-DISTRICT-012117",
          organization_name: "Công an huyện Châu Thành",
          province_name: "Trà Vinh",
          organization_type_code: "POLICE_DISTRICT",
          organization_level: "DISTRICT",
          score: 100,
          matched_on: "EXACT_NAME_MATCH",
        },
      ],
    };
  }

  const found = mockOrganizations.find(
    (item) =>
      (id && item.organization_id === id) ||
      (name && searchKey(item.organization_name || "") === searchKey(name)) ||
      (name && searchKey(name) === "bchqs huyen soc son" && item.organization_id === "BQP-DISTRICT-000196"),
  );

  if (!found) {
    return {
      match_status: "NOT_FOUND",
      candidates: [],
      reason: "NO_EXACT_MATCH",
    };
  }

  const status = id ? "EXACT_ID_MATCH" : found.match_status;
  return applyContext({ ...found, match_status: status }, request);
}

export async function searchOrganization(
  request: SearchRequest,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  if (USE_MOCK_API) {
    return mockSearch(request, signal);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/organizations/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    throw new Error(`API trả về mã lỗi ${response.status}`);
  }

  return response.json() as Promise<SearchResponse>;
}

export async function getRegistryStats(): Promise<RegistryStats> {
  if (USE_MOCK_API) return stats;

  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error();
    const data = await response.json() as { total_organizations: number };
    // Backend không có stats đầy đủ, dùng default + total từ health endpoint
    return { ...stats, total: data.total_organizations || stats.total };
  } catch {
    return stats;
  }
}

export const apiMode = USE_MOCK_API ? "mock" : "live";
