(() => {
  const root = document.documentElement;
  const validThemes = new Set(["odin", "norse"]);
  const realm = root.dataset.mythosRealm;

  try {
    const savedTheme = localStorage.getItem("mythos-theme");
    if (realm === "norse") {
      root.dataset.theme = "norse";
      localStorage.setItem("mythos-theme", "norse");
    } else if (realm === "greek") {
      delete root.dataset.theme;
      localStorage.removeItem("mythos-theme");
    } else if (realm === "selector") delete root.dataset.theme;
    else if (validThemes.has(savedTheme)) root.dataset.theme = savedTheme;
  } catch { /* Private browsing can disable storage; page realm styling still applies. */ }

  const applyTheme = (theme) => {
    if (validThemes.has(theme)) {
      root.dataset.theme = theme;
      try { localStorage.setItem("mythos-theme", theme); } catch { /* Theme still applies for this page. */ }
    } else if (theme === "default") {
      delete root.dataset.theme;
      try { localStorage.removeItem("mythos-theme"); } catch { /* Theme still resets for this page. */ }
    }
  };

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-mythos-theme]") : null;
    if (target) applyTheme(target.dataset.mythosTheme);
  });
})();

