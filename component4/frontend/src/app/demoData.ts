import type { Alert, BatchActivity, Kpi } from "../types/analytics";

export const kpis: Kpi[] = [
  { label: "Total production", value: "1.24M", detail: "gloves this period", trend: "+8.4%", direction: "up", tone: "blue" },
  { label: "Total inspected", value: "1.18M", detail: "95.2% inspection coverage", trend: "+6.9%", direction: "up", tone: "teal" },
  { label: "Accepted gloves", value: "1.13M", detail: "95.5% of inspected", trend: "+2.1%", direction: "up", tone: "green" },
  { label: "Rejected gloves", value: "56,420", detail: "4.5% of inspected", trend: "-1.8%", direction: "down", tone: "red" },
  { label: "Overall rejection rate", value: "4.5%", detail: "target ≤ 5.0%", trend: "0.5% under target", direction: "down", tone: "green" },
  { label: "High-risk batches", value: "07", detail: "need attention today", trend: "2 new", direction: "up", tone: "amber" },
];

export const productionTrend = [
  { day: "01 Oct", produced: 158, rejected: 7.8 }, { day: "03 Oct", produced: 174, rejected: 8.2 },
  { day: "05 Oct", produced: 166, rejected: 6.4 }, { day: "07 Oct", produced: 188, rejected: 7.1 },
  { day: "09 Oct", produced: 181, rejected: 6.3 }, { day: "11 Oct", produced: 192, rejected: 7.4 },
  { day: "13 Oct", produced: 184, rejected: 6.1 },
];

export const defectDistribution = [
  { name: "Tear / hole", value: 34, color: "#d65b5b" },
  { name: "Contamination", value: 26, color: "#e2a12e" },
  { name: "Thin spot", value: 19, color: "#1d6b8f" },
  { name: "Shape variance", value: 12, color: "#168b87" },
  { name: "Other", value: 9, color: "#9aa8ba" },
];

export const gradeDistribution = [
  { grade: "Grade A", count: 784, percent: "66.4%", color: "#168b87" },
  { grade: "Grade B", count: 278, percent: "23.6%", color: "#1d6b8f" },
  { grade: "Grade C", count: 74, percent: "6.3%", color: "#e2a12e" },
  { grade: "Reject", count: 44, percent: "3.7%", color: "#d65b5b" },
];

export const batches: BatchActivity[] = [
  { id: "B-241013-07", line: "Line 04", produced: 18420, inspected: 18290, accepted: 17642, rejectionRate: 3.5, grade: "A", status: "Complete", time: "12 min ago" },
  { id: "B-241013-06", line: "Line 02", produced: 22100, inspected: 21880, accepted: 20760, rejectionRate: 5.1, grade: "B", status: "Review", time: "38 min ago" },
  { id: "B-241013-05", line: "Line 01", produced: 19840, inspected: 19710, accepted: 19184, rejectionRate: 2.7, grade: "A", status: "Complete", time: "1 hr ago" },
  { id: "B-241013-04", line: "Line 03", produced: 17600, inspected: 17420, accepted: 16430, rejectionRate: 5.7, grade: "C", status: "Review", time: "2 hrs ago" },
];

export const alerts: Alert[] = [
  { title: "Risk threshold exceeded", message: "B-241013-06 is trending above the 5% rejection target.", severity: "critical", time: "8 min ago", batch: "B-241013-06" },
  { title: "Contamination spike", message: "Line 03 recorded 18% more contamination defects than baseline.", severity: "warning", time: "42 min ago", batch: "B-241013-04" },
  { title: "Model refresh completed", message: "Quality risk model v2.4 is now scoring incoming batches.", severity: "info", time: "2 hrs ago" },
];
