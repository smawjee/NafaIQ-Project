import { supabase } from "@/integrations/supabase/client";


//get budget

export async function getBudgets() {
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("budgets")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  if (error) {
    console.error("Error loading budgets:", error);
    return [];
  }

  return data;
}

//add new budget

export async function addBudget(budget: {
  category: string;
  limit_amount: number;
  spent?: number;
  tip?: string;
}) {
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not logged in");
  }

  const { data, error } = await supabase
    .from("budgets")
    .insert({
      user_id: user.id,
      category: budget.category,
      limit_amount: budget.limit_amount,
      spent: budget.spent ?? 0,
      tip: budget.tip,
    })
    .select()
    .single();

  if (error) {
    console.error("Error adding budget:", error);
    throw error;
  }

  return data;
}


//update budget

export async function updateBudget(
  id: string,
  updates: {
    category?: string;
    limit_amount?: number;
    spent?: number;
    tip?: string;
  }
) {
  const { data, error } = await supabase
    .from("budgets")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    console.error("Error updating budget:", error);
    throw error;
  }

  return data;
}


//delete budget

export async function deleteBudget(id: string) {
  const { error } = await supabase
    .from("budgets")
    .delete()
    .eq("id", id);

  if (error) {
    console.error("Error deleting budget:", error);
    throw error;
  }

  return true;
}