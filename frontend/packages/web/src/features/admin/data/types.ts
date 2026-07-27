// Admin API DTOs — mirror backend app/schemas/admin.py.

export interface AdminMe {
  user_id: string;
  email: string;
  roles: string[];
  permissions: string[];
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface UserListItem {
  id: string;
  email: string | null;
  display_name: string | null;
  plan: string;
  account_status: string;
  created_at: string | null;
  last_sign_in_at: string | null;
}

export interface UserActivity {
  available: boolean;
  counts: Record<string, number>;
}

export interface AdminNote {
  id: number;
  author_id: string | null;
  note: string;
  created_at: string;
}

export interface UserDetail {
  id: string;
  email: string | null;
  display_name: string | null;
  plan: string;
  account_status: string;
  status_reason: string | null;
  status_changed_at: string | null;
  plan_selected_at: string | null;
  created_at: string | null;
  last_sign_in_at: string | null;
  email_confirmed_at: string | null;
  activity: UserActivity;
  roles: string[];
  notes: AdminNote[];
}

export interface RoleAssignmentInfo {
  id: number;
  role_slug: string;
  granted_by: string | null;
  granted_at: string;
  revoked_at: string | null;
  revoked_by: string | null;
  reason: string | null;
}

export interface RoleInfo {
  slug: string;
  name: string;
  description: string | null;
  permissions: string[];
}

export interface PermissionInfo {
  slug: string;
  description: string | null;
}

export interface AdminListItem {
  user_id: string;
  email: string | null;
  roles: string[];
  first_granted_at: string | null;
}

export interface FlagInfo {
  key: string;
  type: "bool" | "int" | "string" | "enum";
  value: unknown;
  allowed: unknown | null;
  enabled: boolean;
  description: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export interface AuditEntry {
  id: number;
  actor_user_id: string | null;
  actor_email: string | null;
  actor_roles: string[];
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  target_user_id: string | null;
  before: unknown | null;
  after: unknown | null;
  reason: string | null;
  request_id: string | null;
  ip: string | null;
  status: string;
  created_at: string;
}

export interface MetricBlock {
  available: boolean;
  data: Record<string, unknown>;
}

export interface OverviewResponse {
  users: MetricBlock;
  tiers: MetricBlock;
  engagement: MetricBlock;
  recent_actions: AuditEntry[];
}
