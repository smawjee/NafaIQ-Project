import { createFileRoute, Outlet } from "@tanstack/react-router";
import { AdminGuard } from "@/features/admin/components/AdminGuard";
import { AdminShell } from "@/features/admin/components/AdminShell";

export const Route = createFileRoute("/admin")({
  head: () => ({ meta: [{ title: "Admin — NafaIQ" }] }),
  component: AdminLayout,
});

function AdminLayout() {
  return (
    <AdminGuard>
      <AdminShell>
        <Outlet />
      </AdminShell>
    </AdminGuard>
  );
}
