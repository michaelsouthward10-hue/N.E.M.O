import Stripe from "https://esm.sh/stripe@18.5.0?target=denonext";
import { corsHeaders, json, requireUser, siteUrl } from "../_shared/http.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json({ error: "Method not allowed." }, 405);
  try {
    const user = await requireUser(request);
    const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, { httpClient: Stripe.createFetchHttpClient() });
    const admin = (await import("https://esm.sh/@supabase/supabase-js@2.57.0")).createClient(
      Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
    const { data: existing } = await admin.from("memberships").select("stripe_customer_id,status,current_period_end").eq("user_id", user.id).maybeSingle();
    if (existing && ["active", "trialing"].includes(existing.status) && Date.parse(existing.current_period_end) > Date.now()) {
      return json({ error: "Your membership is already active. Manage it from your account." }, 409);
    }
    let customerId = existing?.stripe_customer_id;
    if (!customerId) {
      const customer = await stripe.customers.create({ email: user.email!, metadata: { supabase_user_id: user.id } }, { idempotencyKey: `mythos-customer-${user.id}` });
      customerId = customer.id;
    }
    const session = await stripe.checkout.sessions.create({
      mode: "subscription", customer: customerId!, client_reference_id: user.id,
      line_items: [{ price: Deno.env.get("STRIPE_PRICE_ID")!, quantity: 1 }],
      subscription_data: { metadata: { supabase_user_id: user.id } },
      success_url: `${siteUrl}/account/?membership=success`, cancel_url: `${siteUrl}/membership/?membership=cancelled`,
      allow_promotion_codes: false,
    }, { idempotencyKey: `mythos-checkout-${user.id}-${Math.floor(Date.now() / 60000)}` });
    return json({ url: session.url });
  } catch (error) {
    console.error("Checkout request failed", error);
    return json({ error: error instanceof Error ? error.message : "Checkout could not be started." }, 400);
  }
});

