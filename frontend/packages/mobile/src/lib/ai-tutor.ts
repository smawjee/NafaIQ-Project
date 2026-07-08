// Client for the AI tutor. Calls the `ask-tutor` Supabase Edge Function so the
// LOVABLE_API_KEY stays server-side. Replaces the web app's useServerFn(askTutor).
import { supabase } from "./supabase";

export type TutorMessage = { role: "user" | "assistant"; content: string };

export type AskTutorInput = {
  lessonTitle: string;
  section?: string;
  messages: TutorMessage[];
};

export async function askTutor(input: AskTutorInput): Promise<string> {
  const { data, error } = await supabase.functions.invoke<{ reply?: string }>("ask-tutor", {
    body: input,
  });
  if (error) return "Sorry, I couldn't reach the AI tutor just now. Please try again.";
  return data?.reply ?? "I'm not sure how to answer that — could you rephrase?";
}
