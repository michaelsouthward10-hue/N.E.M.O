# Mythos Fellow Scholar membership: setup and launch

The website pages and server-side integration are in place. Membership cannot take payments until its owner-configured services below are connected. Keep this file and the provider dashboards private to the site owner; never commit live credentials.

## What the feature does

- Accounts use Supabase email/password sign-in with email confirmation.
- Stripe Checkout offers a server-configured recurring £3 GBP monthly price. Stripe’s Customer Portal handles card updates and cancellation.
- A signed Stripe webhook updates membership access in Supabase. The browser cannot grant itself membership.
- Active scholars can select the Odin theme and open private wallpaper download links.
- Scholar profiles use illustrated god and goddess portraits rather than personal photo uploads. Athena is the starter portrait; quiz experience unlocks more portraits, an active membership unlocks Odin, and a future newsletter integration can unlock Hera.
- The current Athena quiz awards 20 XP per correct answer and a 10 XP completion bonus, once per user per UTC day. Levels require 100 XP. The database scores submitted answers and tracks the daily attempt.
- Active scholars can submit one story per UTC calendar month. The database enforces the limit. Stories remain private while pending; an editor changes the status to `approved` to publish or `needs_revision` to return a story to its author.
- Readers do not need an account. Story text is inserted as text, not interpreted as HTML.

## 1. Create and configure Supabase

Create a Supabase project in the site owner’s account. Apply `supabase/migrations/202610080001_fellow_scholar_membership.sql` using the Supabase CLI or SQL editor. The migration creates the profiles, memberships, story wall, private wallpaper bucket, access policies, and Stripe synchronization function.

In Supabase Authentication settings:

1. Enable email/password sign-in and email confirmation.
2. Set the site URL to `https://mythoslibrary.com`.
3. Add `https://mythoslibrary.com/account/` to the allowed redirect URLs.
4. Configure the confirmation email so its link returns to the account page.

Upload wallpapers to the private `scholar-wallpapers` bucket. For each file, insert one corresponding row into `public.scholar_wallpapers` with its title, tradition, release month, orientation (`desktop` or `mobile`), and exact object path. Only active members can read the metadata or download a short-lived signed URL.

For a live site, the Supabase project needs to remain available. Supabase currently lists its Pro plan at $25/month; confirm the current plan and project-pause rules in the owner’s dashboard before launch. A free project is suitable for initial setup, but can pause after inactivity.

## 2. Create the Stripe plan

In Stripe, create a product named **Fellow Scholar** and a recurring price of **£3 GBP every month**. Enable Stripe’s Customer Portal and choose the billing and cancellation options to offer members. Start in Stripe test mode and complete test purchases before changing to live mode.

Create a webhook endpoint for the Supabase function URL:

`https://YOUR_PROJECT_REF.supabase.co/functions/v1/stripe-webhook`

Subscribe it to `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`. Copy its signing secret. Do not put the Stripe secret key or webhook signing secret in the website folder, GitHub Pages settings, or browser source.

## 3. Set Supabase function secrets and deploy

Set these secrets in the Supabase project’s Edge Function secrets. Use values from the Supabase and Stripe owner dashboards:

| Secret | Value |
| --- | --- |
| `STRIPE_SECRET_KEY` | Stripe restricted or secret API key; begin with a test-mode key |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for this exact webhook endpoint |
| `STRIPE_PRICE_ID` | The monthly £3 GBP recurring Stripe price ID |
| `MYTHOS_SITE_URL` | `https://mythoslibrary.com` |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase publishable/anon key, for verifying a signed-in request |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role secret, backend only |

Deploy `create-checkout`, `create-customer-portal`, and `stripe-webhook`. Keep JWT verification enabled for the first two authenticated functions and disabled only for `stripe-webhook`; that endpoint verifies Stripe’s signature itself.

## 4. Connect the public pages

Copy the Supabase project URL and publishable/anon key into `website/membership-config.js`. Those two values are intended to be public. Never copy `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, or `SUPABASE_SERVICE_ROLE_KEY` there.

Deploy the website over HTTPS. Before activating sign-up, verify the exact Supabase URL and keys, confirmation email, redirects, Stripe test checkout, billing portal, webhook delivery, story moderation, and wallpaper downloads. Switch Stripe to live mode only after the owner has reviewed their account, product description, refund/cancellation policies, and applicable tax settings.

## 5. Editorial review

Review submissions in Supabase Studio under `public.scholar_stories`. Set `status` to `approved` to publish a story, `needs_revision` to let its author edit and resubmit, or `rejected` to keep it off the public wall. A member can read their own submission status; anonymous readers can see only approved stories.

The submission form asks authors to confirm that they can share the work and grants Mythos permission to display it while leaving ownership with the author. Before launch, publish a privacy notice and complete terms covering moderation, removal requests, payment, cancellation, refunds, and the site operator’s contact details.

## Files in the implementation

- `website/membership/`: sign-up, sign-in, and membership details.
- `website/account/`: membership state, billing portal, theme, and art-card library.
- `website/scholar-stories/`: public story wall and member submission form.
- `supabase/functions/`: Checkout, billing portal, and signed Stripe webhook.
- `supabase/migrations/`: database tables, policies, and membership sync.

