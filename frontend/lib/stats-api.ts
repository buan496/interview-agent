import { request } from "@/lib/api-client";
import type { RadarItem, ReportListItem } from "@/lib/types";

export function getRadar() {
  return request<RadarItem[]>("/me/radar");
}

export function getReports() {
  return request<ReportListItem[]>("/me/reports");
}
