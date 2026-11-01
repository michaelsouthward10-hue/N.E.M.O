(() => {
  try {
    if (localStorage.getItem("mythos-theme") === "odin") {
      document.documentElement.dataset.theme = "odin";
    }
  } catch { /* Private browsing can disable storage; the parchment theme remains. */ }
})();

