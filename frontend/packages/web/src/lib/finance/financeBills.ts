import { supabase } from "@/integrations/supabase/client";

export type FinanceBillStatus = "UPCOMING" | "DUE SOON" | "PAID";

export type FinanceBill = {
  id: string;
  user_id: string;
  name: string;
  amount: number;
  currency: string;
  due_date: string | null;
  due_label: string | null;
  status: FinanceBillStatus;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FinanceBillInput = {
  name: string;
  amount: number;
  currency?: string;
  due_date?: string | null;
  due_label?: string | null;
  status?: FinanceBillStatus;
};

function normalizeBill(row: any): FinanceBill {
  return {
    ...row,
    amount: Number(row.amount),
  };
}

export async function getFinanceBills(userId: string) {
  const { data, error } = await supabase
    .from("finance_bills" as any)
    .select("*")
    .eq("user_id", userId)
    .neq("status", "PAID")
    .order("due_date", { ascending: true, nullsFirst: false })
    .order("created_at", { ascending: false });

  if (error) throw error;
  return (data ?? []).map(normalizeBill);
}

export async function addFinanceBill(userId: string, bill: FinanceBillInput) {
  const { data, error } = await supabase
    .from("finance_bills" as any)
    .insert({
      user_id: userId,
      name: bill.name,
      amount: bill.amount,
      currency: bill.currency ?? "PKR",
      due_date: bill.due_date ?? null,
      due_label: bill.due_label ?? null,
      status: bill.status ?? "UPCOMING",
    })
    .select()
    .single();

  if (error) throw error;
  return normalizeBill(data);
}

export async function markFinanceBillPaid(id: string, userId: string) {
  const { data, error } = await supabase
    .from("finance_bills" as any)
    .update({
      status: "PAID",
      paid_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("user_id", userId)
    .select()
    .single();

  if (error) throw error;
  return normalizeBill(data);
}

export async function deleteFinanceBill(id: string, userId: string) {
  const { error } = await supabase
    .from("finance_bills" as any)
    .delete()
    .eq("id", id)
    .eq("user_id", userId);

  if (error) throw error;
  return true;
}
