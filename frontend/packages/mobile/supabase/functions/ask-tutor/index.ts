// Supabase Edge Function: ask-tutor (Deno runtime).
// Wraps the Lovable AI gateway so LOVABLE_API_KEY never ships in the app bundle.
// Port of the web app's TanStack server fn (../nafa-iq-zenith/src/lib/learn-ai.functions.ts).
//
// Deploy:
//   supabase functions deploy ask-tutor
//   supabase secrets set LOVABLE_API_KEY=your_key
//
// Call from the app via src/lib/ai-tutor.ts (supabase.functions.invoke).

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

type Msg = { role: "user" | "assistant"; content: string };
type Body = { lessonTitle: string; section?: string; messages: Msg[] };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

function valid(b: unknown): b is Body {
  const x = b as Body;
  return (
    !!x &&
    typeof x.lessonTitle === "string" &&
    x.lessonTitle.length > 0 &&
    Array.isArray(x.messages) &&
    x.messages.length > 0 &&
    x.messages.length <= 20 &&
    x.messages.every((m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
  );
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  const key = Deno.env.get("LOVABLE_API_KEY");
  if (!key) return json({ reply: "The AI tutor is not configured right now. Please try again later." });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json({ reply: "Invalid request." }, 400);
  }
  if (!valid(body)) return json({ reply: "Invalid request." }, 400);

  const system =
    `You are a friendly financial education tutor for NafaIQ, a Pakistan Stock Exchange app. ` +
    `The user is currently reading a lesson about "${body.lessonTitle}"` +
    (body.section ? ` (currently in the "${body.section}" section)` : "") +
    `. Keep answers concise (under 150 words), use simple language, and give Pakistan-specific ` +
    `examples where possible (use stocks like HBL, ENGRO, KSE-100). If asked about a topic ` +
    `unrelated to finance, politely redirect.`;

  try {
    const res = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}`, "Lovable-API-Key": key },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [{ role: "system", content: system }, ...body.messages],
      }),
    });

    if (res.status === 429)
      return json({ reply: "I'm getting a lot of questions right now — please wait a moment and try again." });
    if (res.status === 402)
      return json({ reply: "The AI tutor has run out of credits for now. Please try again later." });
    if (!res.ok) return json({ reply: "Sorry, I couldn't reach the AI tutor just now. Please try again." });

    const data = (await res.json()) as { choices?: { message?: { content?: string } }[] };
    const reply = data.choices?.[0]?.message?.content?.trim();
    return json({ reply: reply || "I'm not sure how to answer that — could you rephrase?" });
  } catch {
    return json({ reply: "Sorry, something went wrong reaching the AI tutor. Please try again." });
  }
});
