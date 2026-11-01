export const siteUrl = Deno.env.get("MYTHOS_SITE_URL") || "https://mythoslibrary.com";
export const corsHeaders = {
  "Access-Control-Allow-Origin": siteUrl,
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Vary": "Origin",
};

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });
}

export async function requireUser(request: Request) {
  const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2.57.0");
  const authorization = request.headers.get("Authorization");
  if (!authorization) throw new Error("Please sign in first.");
  const client = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: authorization } }, auth: { persistSession: false },
  });
  const { data, error } = await client.auth.getUser();
  if (error || !data.user || !data.user.email_confirmed_at) throw new Error("Confirm your email address and sign in again.");
  return data.user;
}

