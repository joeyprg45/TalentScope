import type { SavedReport } from "@/lib/types";

const STORAGE_KEY = "talentscope_reports";
const MAX_REPORTS = 50;

export function loadReports(): SavedReport[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as SavedReport[];
  } catch {
    return [];
  }
}

export function saveReport(data: {
  type: "assignment" | "skill";
  title: string;
  markdown: string;
}): SavedReport {
  const report: SavedReport = {
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    ...data,
  };
  const existing = loadReports();
  const updated = [report, ...existing].slice(0, MAX_REPORTS);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  return report;
}
