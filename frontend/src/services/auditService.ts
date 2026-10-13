import { apiClient } from "./api";
import { AuditLogListResponse } from "../types/audit";

export const auditService = {
  async getAuditLogs(
    limit: number = 50,
    skip: number = 0
  ): Promise<AuditLogListResponse> {
    const response = await apiClient.get<AuditLogListResponse>("/audit-logs", {
      params: { limit, skip },
    });
    return response.data;
  },
};
