import type { TransactionRecord } from "../types/portal";

const HISTORY_KEY = "bca-bqp.portal.transactions";
const MAX_HISTORY_ITEMS = 100;

function parseStoredValue<T>(value: string | null): T | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export function loadTransactions(): TransactionRecord[] {
  const records = parseStoredValue<TransactionRecord[]>(localStorage.getItem(HISTORY_KEY));
  if (!Array.isArray(records)) return [];
  return records
    .filter((record) => record && typeof record.id === "string" && typeof record.userId === "string")
    .slice(0, MAX_HISTORY_ITEMS);
}

export function saveTransactions(records: TransactionRecord[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(records.slice(0, MAX_HISTORY_ITEMS)));
}

export function createTransactionId() {
  return typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `TX-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
