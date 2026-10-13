export interface AuditLogItem {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  ip_address?: string | null;
  status: string;
  details: Record<string, any>;
  created_at?: string | null;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
}
