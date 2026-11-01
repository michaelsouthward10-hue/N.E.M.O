import Stripe from "https://esm.sh/stripe@18.5.0?target=denonext";
import { corsHeaders, json, requireUser, siteUrl } from "../_shared/http.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json({ error: "Method not allowed." }, 405);
  try {
    const user = await requireUser(request);
    const admin = (await import("https://esm.sh/@supabase/supabase-js@2.57.0")).createClient(
      Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
    const { data: membership, error } = await admin.from("memberships").select("stripe_customer_id").eq("user_id", user.id).maybeSingle();
    if (error || !membership?.stripe_customer_id) return json({ error: "No subscription is linked to this account yet." }, 404);
    const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, { httpClient: Stripe.createFetchHttpClient() });
    const portal = await stripe.billingPortal.sessions.create({ customer: membership.stripe_customer_id, return_url: `${siteUrl}/account/` });
    return json({ url: portal.url });
  } catch (error) {
    console.error("Customer portal request failed", error);
    return json({ error: error instanceof Error ? error.message : "Subscription settings could not be opened." }, 400);
  }
});

