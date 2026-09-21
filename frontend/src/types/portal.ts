import type { BatchProcessSummary, SearchRequest } from "./search";

export type UserRole = "admin" | "user";

export interface PortalSession {
  userId: string;
  username: string;
  displayName: string;
  email?: string;
  role: UserRole;
  isActive: boolean;
  createdAt: string;
  lastLoginAt: string | null;
}

export type PortalView = "search" | "history" | "users";
export type TransactionType = "SEARCH" | "BATCH";
export type TransactionOutcome = "SUCCESS" | "REVIEW" | "NOT_FOUND" | "ERROR";

export interface TransactionRecord {
  id: string;
  userId: string;
  createdAt: string;
  type: TransactionType;
  outcome: TransactionOutcome;
  title: string;
  status: string;
  request?: SearchRequest;
  organizationId?: string;
  organizationName?: string;
  payingOrganization?: string | null;
  payrollStatus?: string;
  management?: string;
  filename?: string;
  batchSummary?: BatchProcessSummary;
  detail?: string;
}
