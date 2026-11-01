(() => {
  const root = document.documentElement;
  const validThemes = new Set(["odin", "norse"]);

  try {
    const savedTheme = localStorage.getItem("mythos-theme");
    if (validThemes.has(savedTheme)) root.dataset.theme = savedTheme;
  } catch { /* Private browsing can disable storage; the parchment theme remains. */ }

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
