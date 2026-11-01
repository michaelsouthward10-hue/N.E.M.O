const config = window.MYTHOS_MEMBERSHIP;
const status = document.querySelector("[data-member-status]");
const ready = Boolean(config?.supabaseUrl && config?.supabaseAnonKey);
let createClient;
if (ready) ({ createClient } = await import("https://esm.sh/@supabase/supabase-js@2.57.0"));
export const client = ready ? createClient(config.supabaseUrl, config.supabaseAnonKey) : null;
const avatarNames = { athena: "Athena", zeus: "Zeus", poseidon: "Poseidon", artemis: "Artemis", apollo: "Apollo", odin: "Odin", hera: "Hera" };
const accountUrl = `${config?.siteUrl || "https://mythoslibrary.com"}/account/`;
const signInUrl = `${config?.siteUrl || "https://mythoslibrary.com"}/membership/#signin-form`;
const say = (message, error = false) => {
  if (status) { status.textContent = message; status.dataset.error = String(error); }
};
const friendlyError = (error) => error?.message || "Something went wrong. Please try again.";
export async function recordQuizAttempt(answers) {
  if (!client) return { state: "unavailable" };
  const { data: { user } } = await client.auth.getUser();
  if (!user) return { state: "signed-out" };
  const { data, error } = await client.rpc("submit_quiz_attempt", { p_quiz_id: "athena-olive-01", p_answers: answers });
  if (error) return { state: "error", message: friendlyError(error) };
  return { state: "saved", ...(Array.isArray(data) ? data[0] : data) };
}

function setAvatarFace(element, avatarId) {
  if (element) element.dataset.avatarFace = avatarNames[avatarId] ? avatarId : "athena";
}

async function renderProfileShortcut(session) {
  const shortcuts = document.querySelectorAll("[data-profile-shortcut]");
  if (!shortcuts.length) return;
  if (!session || !client) {
    shortcuts.forEach((link) => {
      link.href = signInUrl;
      link.setAttribute("aria-label", "Sign in or create a Scholar account");
      setAvatarFace(link.querySelector("[data-avatar-face]"), "athena");
      link.querySelector("[data-profile-label]").textContent = "Sign in";
      link.querySelector("[data-profile-detail]").textContent = "Scholar account";
    });
    return;
  }
  const [{ data: profile }, { data: membership }] = await Promise.all([
    client.from("member_profiles").select("display_name,avatar_id,experience").eq("user_id", session.user.id).maybeSingle(),
    client.from("memberships").select("status,current_period_end").eq("user_id", session.user.id).maybeSingle()
  ]);
  const xp = profile?.experience || 0;
  const level = Math.floor(xp / 100) + 1;
  const isMember = ["active", "trialing"].includes(membership?.status) && Date.parse(membership.current_period_end) > Date.now();
  shortcuts.forEach((link) => {
    link.href = accountUrl;
    link.setAttribute("aria-label", `Your Scholar profile, level ${level}`);
    setAvatarFace(link.querySelector("[data-avatar-face]"), profile?.avatar_id);
    link.querySelector("[data-profile-label]").textContent = profile?.display_name || "Scholar";
    link.querySelector("[data-profile-detail]").textContent = `Level ${level}${isMember ? " · Fellow Scholar" : ""}`;
  });
}

function renderAvatarCollection(profile) {
  const collection = document.querySelector("#avatar-collection");
  if (!collection) return;
  Promise.all([
    client.from("god_avatars").select("id,display_name,tradition,unlock_type,unlock_level").order("sort_order"),
    client.from("member_avatar_unlocks").select("avatar_id").eq("user_id", profile.user_id)
  ]).then(([{ data, error }, { data: unlockedRows, error: unlockError }]) => {
    if (error || unlockError || !data || !unlockedRows) { collection.textContent = "Your portraits will appear when the avatar library is connected."; return; }
    collection.replaceChildren();
    const unlockedIds = new Set(unlockedRows.map((row) => row.avatar_id));
    for (const avatar of data) {
      const unlocked = unlockedIds.has(avatar.id);
      const choice = document.createElement("button");
      choice.type = "button"; choice.className = `avatar-choice${unlocked ? "" : " is-locked"}${profile.avatar_id === avatar.id ? " is-selected" : ""}`;
      choice.disabled = !unlocked; choice.setAttribute("aria-pressed", String(profile.avatar_id === avatar.id));
      const portrait = document.createElement("span"); portrait.className = "avatar-art"; portrait.dataset.avatarFace = avatar.id; portrait.setAttribute("aria-hidden", "true");
      const name = document.createElement("strong"); name.textContent = avatar.display_name;
      const unlock = document.createElement("small");
      unlock.textContent = unlocked ? (avatar.unlock_type === "starter" ? "Your first portrait" : avatar.unlock_type === "level" ? `Level ${avatar.unlock_level}` : avatar.unlock_type === "membership" ? "Fellow Scholar" : "Newsletter") : avatar.unlock_type === "level" ? `Unlock at level ${avatar.unlock_level}` : avatar.unlock_type === "membership" ? "Membership portrait" : "Newsletter · coming soon";
      choice.append(portrait, name, unlock);
      if (unlocked) choice.addEventListener("click", async () => {
        const { error: saveError } = await client.from("member_profiles").update({ avatar_id: avatar.id }).eq("user_id", profile.user_id);
        if (saveError) { say(friendlyError(saveError), true); return; }
        profile.avatar_id = avatar.id;
        renderAvatarCollection(profile);
        await renderProfileShortcut((await client.auth.getSession()).data.session);
        const preview = document.querySelector("[data-profile-preview]");
        setAvatarFace(preview, avatar.id);
        say(`${avatar.display_name} is now your profile portrait.`);
      });
      collection.append(choice);
    }
    const selectedFace = document.querySelector("[data-profile-preview]");
    setAvatarFace(selectedFace, profile.avatar_id);
  });
}
const callFunction = async (name) => {
  const { data: { session } } = await client.auth.getSession();
  if (!session) throw new Error("Please sign in first.");
  const { data, error } = await client.functions.invoke(name);
  if (error) throw error;
  if (!data?.url || new URL(data.url).protocol !== "https:") throw new Error("The secure payment page could not be opened.");
  location.assign(data.url);
};

if (!ready) {
  document.querySelectorAll("[data-needs-backend]").forEach((element) => { element.disabled = true; });
  say("Member accounts are being prepared. Sign-up will open once the secure member service is configured.");
} else {
  const signUp = document.querySelector("#signup-form");
  signUp?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(signUp);
    const { error } = await client.auth.signUp({
      email: String(form.get("email")).trim(), password: String(form.get("password")),
      options: { data: { display_name: String(form.get("display_name")).trim() }, emailRedirectTo: `${config.siteUrl}/account/` }
    });
    say(error ? friendlyError(error) : "Check your inbox for the confirmation link, then return here to sign in.", Boolean(error));
  });

  const signIn = document.querySelector("#signin-form");
  signIn?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(signIn);
    const { error } = await client.auth.signInWithPassword({ email: String(form.get("email")).trim(), password: String(form.get("password")) });
    if (error) return say(friendlyError(error), true);
    location.assign(`${config.siteUrl}/account/`);
  });

  document.querySelector("#checkout-button")?.addEventListener("click", async () => {
    try { say("Opening secure checkout…"); await callFunction("create-checkout"); }
    catch (error) { say(friendlyError(error), true); }
  });
  document.querySelector("#portal-button")?.addEventListener("click", async () => {
    try { say("Opening subscription settings…"); await callFunction("create-customer-portal"); }
    catch (error) { say(friendlyError(error), true); }
  });
  document.querySelector("#signout-button")?.addEventListener("click", async () => {
    await client.auth.signOut(); location.assign(`${config.siteUrl}/membership/`);
  });

  const accountPanel = document.querySelector("[data-account-panel]");
  const storyGate = document.querySelector("[data-story-gate]");
  const renderAccount = async (session) => {
    if (!accountPanel && !storyGate) return;
    if (!session) {
      if (accountPanel) accountPanel.hidden = true;
      if (accountPanel) document.querySelector("#account-signin").hidden = false;
      if (storyGate) { storyGate.hidden = false; }
      return;
    }
    const [{ data: profile }, { data: subscription }, { data: { user } }] = await Promise.all([
      client.from("member_profiles").select("user_id,display_name,website_theme,avatar_id,experience,newsletter_subscribed").eq("user_id", session.user.id).maybeSingle(),
      client.from("memberships").select("status,current_period_end,cancel_at_period_end").eq("user_id", session.user.id).maybeSingle(),
      client.auth.getUser()
    ]);
    const active = ["active", "trialing"].includes(subscription?.status) && Date.parse(subscription.current_period_end) > Date.now();
    if (profile) {
      const xp = profile.experience || 0;
      const level = Math.floor(xp / 100) + 1;
      document.querySelector("#scholar-level")?.replaceChildren(document.createTextNode(String(level)));
      document.querySelector("#scholar-xp")?.replaceChildren(document.createTextNode(`${xp} XP`));
      document.querySelector("#xp-to-next")?.replaceChildren(document.createTextNode(level >= 5 ? "Your earned portrait collection is complete" : `${100 - (xp % 100)} XP to your next level`));
      const xpProgress = document.querySelector("#xp-progress");
      if (xpProgress) xpProgress.value = xp % 100;
      renderAvatarCollection(profile);
    }
    if (profile?.website_theme === "odin" && active) {
      document.documentElement.dataset.theme = "odin";
      localStorage.setItem("mythos-theme", "odin");
    }
    if (accountPanel) {
      accountPanel.hidden = false;
      document.querySelector("#account-signin").hidden = true;
      document.querySelector("[data-display-name]").textContent = profile?.display_name || user?.email || "Fellow Scholar";
      document.querySelector("[data-membership-state]").textContent = active ? `Fellow Scholar · ${subscription.cancel_at_period_end ? "ends " : "renews "}${new Date(subscription.current_period_end).toLocaleDateString()}` : "Membership inactive";
      const themeSelect = document.querySelector("#theme-choice");
      themeSelect.value = profile?.website_theme || "parchment";
      themeSelect.disabled = !active;
      document.querySelector("#portal-button").hidden = !subscription;
      document.querySelector("#checkout-button").hidden = active;
      document.querySelector("[data-account-upgrade]").hidden = active;
      if (active) {
        const { data: wallpapers } = await client.from("scholar_wallpapers").select("title,tradition,orientation,object_path,release_month").order("release_month", { ascending: false });
        const list = document.querySelector("#wallpaper-list");
        list.replaceChildren();
        for (const wallpaper of wallpapers || []) {
          const { data: file } = await client.storage.from("scholar-wallpapers").createSignedUrl(wallpaper.object_path, 120);
          if (!file?.signedUrl) continue;
          const item = document.createElement("a");
          item.className = "member-wallpaper"; item.href = file.signedUrl; item.target = "_blank"; item.rel = "noopener";
          const label = document.createElement("span"); label.textContent = `${wallpaper.title} · ${wallpaper.tradition} · ${wallpaper.orientation}`;
          item.append(label); list.append(item);
        }
        if (!list.childElementCount) list.textContent = "Your first art cards will appear here soon.";
      }
    }
    if (storyGate) {
      storyGate.hidden = active;
      document.querySelector("#story-form").hidden = !active;
      const { data: submissions } = await client.from("scholar_stories").select("id,title,status,submission_month,created_at").eq("user_id", session.user.id).order("created_at", { ascending: false });
      const currentMonth = new Date().toISOString().slice(0, 7);
      const submittedThisMonth = (submissions || []).some((story) => story.submission_month?.slice(0, 7) === currentMonth);
      document.querySelector("#story-form").hidden = !active || submittedThisMonth;
      const list = document.querySelector("#my-stories");
      list.replaceChildren();
      for (const story of submissions || []) {
        const item = document.createElement("div"); item.className = "submission-entry";
        const label = document.createElement("span"); label.textContent = `${story.title} — ${story.status.replaceAll("_", " ")}`; item.append(label);
        if (story.status === "needs_revision") {
          const edit = document.createElement("button"); edit.type = "button"; edit.className = "text-link"; edit.textContent = "Edit and resubmit";
          edit.addEventListener("click", async () => {
            const { data: fullStory } = await client.from("scholar_stories").select("id,title,tradition,region,story,source_notes").eq("id", story.id).maybeSingle();
            if (!fullStory) return say("This story is no longer available to edit.", true);
            const form = document.querySelector("#story-form");
            for (const field of ["title", "tradition", "region", "story", "source_notes"]) form.elements.namedItem(field).value = fullStory[field] || "";
            form.elements.namedItem("sharing_consent").checked = true;
            form.dataset.editingId = fullStory.id;
            form.querySelector("button[type=submit]").textContent = "Save and resubmit";
            form.hidden = false; form.scrollIntoView({ behavior: "smooth", block: "start" });
          });
          item.append(edit);
        }
        list.append(item);
      }
      if (active && submittedThisMonth) say("Your story for this month is in the review queue.");
    }
  };
  client.auth.getSession().then(({ data }) => {
    void renderAccount(data.session);
    void renderProfileShortcut(data.session);
  });
  client.auth.onAuthStateChange((_event, session) => {
    window.setTimeout(() => {
      void renderAccount(session);
      void renderProfileShortcut(session);
    }, 0);
  });
  document.addEventListener("mythos:profile-refresh", () => {
    void client.auth.getSession().then(({ data }) => {
      void renderProfileShortcut(data.session);
      void renderAccount(data.session);
    });
  });

  document.querySelector("#theme-choice")?.addEventListener("change", async (event) => {
    const theme = event.currentTarget.value;
    try {
      const { error } = await client.from("member_profiles").update({ website_theme: theme }).eq("user_id", (await client.auth.getUser()).data.user.id);
      if (error) throw error;
      localStorage.setItem("mythos-theme", theme);
      document.documentElement.dataset.theme = theme === "odin" ? "odin" : "";
      say("Your library theme has been saved.");
    } catch (error) { say(friendlyError(error), true); }
  });

  document.querySelector("#story-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const { data: { user } } = await client.auth.getUser();
    const storyValues = {
      title: String(form.get("title")).trim(), tradition: String(form.get("tradition")).trim(),
      region: String(form.get("region")).trim(), story: String(form.get("story")).trim(),
      source_notes: String(form.get("source_notes")).trim(), sharing_consent: form.get("sharing_consent") === "on"
    };
    const editingId = event.currentTarget.dataset.editingId;
    const { error } = editingId
      ? await client.from("scholar_stories").update({ title: storyValues.title, tradition: storyValues.tradition, region: storyValues.region, story: storyValues.story, source_notes: storyValues.source_notes }).eq("id", editingId)
      : await client.from("scholar_stories").insert(storyValues);
    if (error) return say(friendlyError(error), true);
    event.currentTarget.reset();
    delete event.currentTarget.dataset.editingId;
    say(`Thank you, ${user?.user_metadata?.display_name || "Fellow Scholar"}. Your story is awaiting editorial review.`);
    location.reload();
  });

  const storyWall = document.querySelector("#story-wall");
  if (storyWall) {
    client.from("scholar_stories").select("title,tradition,region,story,source_notes,byline,created_at").eq("status", "approved").order("created_at", { ascending: false }).limit(40).then(({ data, error }) => {
      if (error) { say("The Scholar Stories wall is temporarily unavailable.", true); return; }
      const empty = document.querySelector("[data-empty-wall]");
      if (!data?.length) return;
      empty.hidden = true;
      for (const story of data) {
        const article = document.createElement("article"); article.className = "public-story";
        const meta = document.createElement("p"); meta.className = "eyebrow"; meta.textContent = `${story.tradition}${story.region ? ` · ${story.region}` : ""}`;
        const title = document.createElement("h2"); title.textContent = story.title;
        const body = document.createElement("p"); body.textContent = story.story;
        const source = document.createElement("p"); source.className = "story-source"; source.textContent = story.source_notes ? `Sources & notes: ${story.source_notes}` : "A Fellow Scholar’s retelling.";
        const byline = document.createElement("p"); byline.className = "story-byline"; byline.textContent = `Shared by ${story.byline}`;
        article.append(meta, title, body, source, byline); storyWall.append(article);
      }
    });
  }
}

