
//goal api

import { supabase } from "@/integrations/supabase/client";

// Get all goals of logged-in user

export async function getGoals() {
  // Check which user is logged in
  const {
    data: { user },
  } = await supabase.auth.getUser();

  //If no user is logged in return empty
  if (!user) return [];

  // Fetch goals from Supabase
  const { data, error } = await supabase
    .from("goals")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  if (error) {
    console.error("Error loading goals:", error);
    return [];
  }

  return data;
}


//add new goal 

export async function addGoal(goal: {
  name: string;
  target: number;
  saved?: number;
  emoji?: string;
  color?: string;
  ai?: string;
  target_date?: string;
}) {

  
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not logged in");
  }

  //insert
  const { data, error } = await supabase
    .from("goals")
    .insert({
      user_id: user.id,
      name: goal.name,
      target: goal.target,
      saved: goal.saved ?? 0,
      emoji: goal.emoji,
      color: goal.color,
      ai: goal.ai,
      target_date: goal.target_date,
    })
    .select()
    .single();

  if (error) {
    console.error("Error adding goal:", error);
    throw error;
  }

  return data;
}


//update goal

export async function updateGoal(
  id: string,
  updates: {
    name?: string;
    target?: number;
    saved?: number;
    emoji?: string;
    color?: string;
    ai?: string;
    target_date?: string;
  }
) {

  //update goal
  const { data, error } = await supabase
    .from("goals")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    console.error("Error updating goal:", error);
    throw error;
  }

  return data;
}


//delete goal

export async function deleteGoal(id: string) {
  const { error } = await supabase
    .from("goals")
    .delete()
    .eq("id", id);

  if (error) {
    console.error("Error deleting goal:", error);
    throw error;
  }

  return true;
}

// ======================================
// Add contribution to goal
// ======================================

export async function contributeToGoal(
  id: string,
  currentSaved: number,
  amount: number
) {
  const { data, error } = await supabase
    .from("goals")
    .update({
      saved: currentSaved + amount,
    })
    .eq("id", id)
    .select()
    .single();

  if (error) {
    console.error("Error adding contribution:", error);
    throw error;
  }

  return data;
}