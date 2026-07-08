import { supabase } from "@/integrations/supabase/client";

export type FinanceTransactionInput = {
  merchant: string;
  amount: number;
  category: string;
  transaction_type: string;
  transaction_date?: string | null;
  currency?: string;
  source?: string;
  email_subject?: string | null;
  raw_text?: string | null;
};

export async function getFinanceTransactions(userId: string) {
  const { data, error } = await supabase
    .from("finance_transactions" as any)
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function addFinanceTransaction(userId: string, tx: FinanceTransactionInput) {
  const { data, error } = await supabase
    .from("finance_transactions" as any)
    .insert({
      user_id: userId,
      merchant: tx.merchant,
      amount: tx.amount,
      currency: tx.currency ?? "PKR",
      transaction_type: tx.transaction_type,
      category: tx.category,
      transaction_date: tx.transaction_date ?? new Date().toISOString(),
      source: tx.source ?? "manual",
      email_subject: tx.email_subject ?? null,
      raw_text: tx.raw_text ?? null,
    })
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function updateFinanceTransaction(
  id: string,
  userId: string,
  tx: Partial<FinanceTransactionInput>,
) {
  const { data, error } = await supabase
    .from("finance_transactions" as any)
    .update(tx)
    .eq("id", id)
    .eq("user_id", userId)
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function deleteFinanceTransaction(id: string, userId: string) {
  const { error } = await supabase
    .from("finance_transactions" as any)
    .delete()
    .eq("id", id)
    .eq("user_id", userId);

  if (error) throw error;
  return true;
}