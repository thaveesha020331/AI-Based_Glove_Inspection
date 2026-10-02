export type Severity = "critical" | "warning" | "info";
export type QualityGrade = "A" | "B" | "C" | "Reject";

export interface Kpi {
  label: string;
  value: string;
  detail: string;
  trend: string;
  direction: "up" | "down" | "neutral";
  tone: "blue" | "teal" | "green" | "amber" | "red";
}

export interface BatchActivity {
  id: string;
  line: string;
  produced: number;
  inspected: number;
  accepted: number;
  rejectionRate: number;
  grade: QualityGrade;
  status: "Complete" | "In progress" | "Review";
  time: string;
}

export interface Alert {
  title: string;
  message: string;
  severity: Severity;
  time: string;
  batch?: string;
}
