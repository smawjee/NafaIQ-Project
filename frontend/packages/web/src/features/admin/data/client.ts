// Typed admin API functions. Thin wrappers over the shared JWT client — every
// call carries the Supabase session token; the backend authorizes server-side.
import { userGet, userPost, userPut, userDelete } from "@/lib/psx/client";
import type {
  AdminListItem,
  AdminMe,
  AuditEntry,
  FlagInfo,
  OverviewResponse,
  Page,
  PermissionInfo,
  RoleAssignmentInfo,
  RoleInfo,
  UserDetail,
  UserListItem,
} from "./types";

export const adminApi = {
  me: () => userGet<AdminMe>("/api/admin/me"),

  overview: () => userGet<OverviewResponse>("/api/admin/overview"),

  listUsers: (params: {
    query?: string;
    status?: string;
    plan?: string;
    sort?: string;
    order?: "asc" | "desc";
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== null) qs.set(k, String(v));
    });
    const s = qs.toString();
    return userGet<Page<UserListItem>>(`/api/admin/users${s ? `?${s}` : ""}`);
  },

  getUser: (id: string) => userGet<UserDetail>(`/api/admin/users/${id}`),

  userRoleHistory: (id: string) => userGet<RoleAssignmentInfo[]>(`/api/admin/users/${id}/roles`),

  changeStatus: (id: string, status: string, reason?: string) =>
    userPost(`/api/admin/users/${id}/status`, { status, reason }),

  changeTier: (id: string, plan: string, reason?: string) =>
    userPost(`/api/admin/users/${id}/tier`, { plan, reason }),

  addNote: (id: string, note: string) => userPost(`/api/admin/users/${id}/notes`, { note }),

  assignRole: (id: string, role_slug: string, reason?: string) =>
    userPost(`/api/admin/users/${id}/roles`, { role_slug, reason }),

  revokeRole: (id: string, roleSlug: string) =>
    userDelete(`/api/admin/users/${id}/roles/${roleSlug}`),

  listRoles: () => userGet<RoleInfo[]>("/api/admin/roles"),
  listPermissions: () => userGet<PermissionInfo[]>("/api/admin/permissions"),
  listAdmins: () => userGet<AdminListItem[]>("/api/admin/admins"),

  listFlags: () => userGet<FlagInfo[]>("/api/admin/flags"),
  updateFlag: (key: string, value: unknown, enabled?: boolean, reason?: string) =>
    userPut<FlagInfo>(`/api/admin/flags/${key}`, { value, enabled, reason }),

  listAudit: (params: {
    action?: string;
    target_user_id?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== null) qs.set(k, String(v));
    });
    const s = qs.toString();
    return userGet<Page<AuditEntry>>(`/api/admin/audit${s ? `?${s}` : ""}`);
  },

  marketData: () => userGet<Record<string, MetricBlockLike>>("/api/admin/market-data"),
  signals: () => userGet<Record<string, MetricBlockLike>>("/api/admin/signals"),
  aiOps: () => userGet<Record<string, MetricBlockLike>>("/api/admin/ai"),
  system: () => userGet<SystemHealth>("/api/admin/system"),
};

export interface MetricBlockLike {
  available: boolean;
  data: Record<string, unknown>;
}

export interface SystemHealth {
  database: { available: boolean };
  deployment: {
    process_role: string;
    scheduler_enabled: boolean;
    environment: string;
  };
}
