import Stripe from "https://esm.sh/stripe@18.5.0?target=denonext";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, { httpClient: Stripe.createFetchHttpClient() });
const cryptoProvider = Stripe.createSubtleCryptoProvider();
const allowedStatuses = new Set(["incomplete", "incomplete_expired", "trialing", "active", "past_due", "canceled", "unpaid", "paused"]);

Deno.serve(async (request) => {
  if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const signature = request.headers.get("stripe-signature");
  if (!signature) return new Response("Missing signature", { status: 400 });
  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(await request.text(), signature, Deno.env.get("STRIPE_WEBHOOK_SECRET")!, undefined, cryptoProvider);
  } catch (error) {
    console.error("Stripe signature verification failed", error);
    return new Response("Invalid signature", { status: 400 });
  }

  if (!["customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"].includes(event.type)) {
    return new Response(JSON.stringify({ received: true }), { headers: { "Content-Type": "application/json" } });
  }
  try {
    const subscription = event.data.object as Stripe.Subscription;
    const userId = subscription.metadata.supabase_user_id;
    const customerId = typeof subscription.customer === "string" ? subscription.customer : subscription.customer.id;
    const status = subscription.status;
    const billingPeriod = subscription.items.data[0];
    if (!billingPeriod) throw new Error("Subscription has no billable item.");
    if (!userId || !allowedStatuses.has(status)) throw new Error("Subscription metadata or status is invalid.");
    const admin = (await import("https://esm.sh/@supabase/supabase-js@2.57.0")).createClient(
      Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
    const { error } = await admin.rpc("sync_membership_from_stripe", {
      p_user_id: userId, p_customer_id: customerId, p_subscription_id: subscription.id,
      p_status: status, p_period_start: new Date(billingPeriod.current_period_start * 1000).toISOString(),
      p_period_end: new Date(billingPeriod.current_period_end * 1000).toISOString(),
      p_cancel_at_period_end: subscription.cancel_at_period_end, p_event_created: event.created,
    });
    if (error) throw error;
    return new Response(JSON.stringify({ received: true }), { headers: { "Content-Type": "application/json" } });
  } catch (error) {
    console.error("Stripe subscription sync failed; Stripe will retry", error);
    return new Response("Membership sync failed", { status: 500 });
  }
});

