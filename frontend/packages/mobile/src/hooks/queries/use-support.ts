import Constants from "expo-constants";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userGet, userPost } from "@/lib/api";

export type BugReportStatus = "open" | "investigating" | "resolved" | "wont_fix";

export interface MyBugReport {
  id: number;
  title: string;
  description: string;
  category: string;
  status: BugReportStatus;
  admin_note: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface BugReportInput {
  title: string;
  description: string;
  category: "bug" | "data" | "billing" | "feature" | "other";
  route?: string;
  error_fingerprint?: string;
}

export function useMyBugReports(enabled = true) {
  return useQuery<MyBugReport[]>({
    queryKey: ["my-bug-reports"],
    queryFn: () => userGet<MyBugReport[]>("/api/support/bug-reports"),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateBugReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: BugReportInput) =>
      userPost<MyBugReport>("/api/support/bug-reports", {
        ...input,
        app_version: Constants.expoConfig?.version ?? "dev",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-bug-reports"] }),
  });
}
