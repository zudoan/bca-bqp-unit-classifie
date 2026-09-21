export type Management = "BCA" | "BQP";

export type MatchStatus =
  | "EXACT_ID_MATCH"
  | "EXACT_NAME_MATCH"
  | "NORMALIZED_MATCH"
  | "SEARCH_KEY_MATCH"
  | "ALIAS_MATCH"
  | "ACRONYM_MATCH"
  | "FUZZY_MATCH"
  | "FUZZY_CANDIDATES"
  | "AMBIGUOUS_MATCH"
  | "NOT_FOUND"
  | "INVALID_INPUT";

export interface SearchRequest {
  organization_id?: string;
  organization_name?: string;
  province_name?: string;
  organization_type?: string;
}

export interface OrganizationCandidate {
  organization_id: string;
  organization_name: string;
  province_name: string | null;
  organization_type_code: string;
  organization_level?: string | null;
  parent_organization_id?: string | null;
  score: number;
  matched_on: string;
}

export interface SearchResponse {
  match_status: MatchStatus;
  match_score?: number | null;
  organization_id?: string;
  organization_name?: string;
  province_name?: string | null;
  organization_type_code?: string;
  paying_organization?: string | null;
  payroll_status?: string;
  management?: Management;
  candidates?: OrganizationCandidate[];
  reason?: string;
  errors?: string[];
}

export interface RegistryStats {
  total: number;
  bca: number;
  bqp: number;
  provinces: number;
}

export interface BatchProcessSummary {
  inputCount: number;
  paidCount: number;
  notPaidCount: number;
  unresolvedCount: number;
  inputMode: "excel" | "word" | "pdf-text" | "gemini-ocr" | string;
}

export interface BatchProcessResult {
  blob: Blob;
  filename: string;
  summary: BatchProcessSummary;
}
